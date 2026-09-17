import hashlib
import json
import subprocess

import numpy as np
import pytest

from research.exploratory import hour_reference_v2 as study
from research.exploratory import hour_reference_checked as checked
from research.exploratory import solid_earth_study as comparison


def test_fixed_hour_inputs_and_old_overlap():
    plan, ctx, observations, positions, _ = study.inputs()
    assert list(ctx.times) == list(range(12600, 16201, 30))
    assert plan['training_before_gpst_s'] == 14400
    old, _, _, _ = study.frame.verified.load_inputs(study.frame.verified.paths('g14')['admission_receipt'].parent)
    fr = json.loads((study.BASE/'results/g14_station_frame_epoch_v1.json').read_bytes())
    so = json.loads((study.BASE/'results/g14_solid_earth_v1.json').read_bytes())
    oc = json.loads((study.BASE/'results/g14_ocean_pole_v1.json').read_bytes())
    for station in fr['station_models']:
        name = station['station']
        assert observations[name][50:61] == old['stations'][name]['reference_observations']
        xyz = (np.array(station['positions']['final_transport']) +
               np.array(so['station_displacements_ecef_m'][name]['solid_earth']) +
               np.array(oc['station_additional_displacements_ecef_m'][name]['ocean_ce_plus_pole_2018']))
        assert np.array(positions[name])[50:61] == pytest.approx(xyz, abs=2e-6, rel=0)


def test_target_code_rejected_at_input_boundary(monkeypatch):
    original = study.pinned
    def altered(path, digest):
        raw = original(path, digest)
        if path.name == 'observations.json':
            data = json.loads(raw)
            next(iter(data.values()))[0]['if_code_m']['G14'] = 2e7
            return json.dumps(data).encode()
        return raw
    monkeypatch.setattr(study, 'pinned', altered)
    with pytest.raises(ValueError, match='unadmitted reference'):
        study.inputs()


def test_future_values_do_not_fit_predictions():
    def rows(times):
        return [{'station':'A','time_s':t,'reference':sv,'residual_m':value,'los_enu':[1,0,0]}
                for t in times for sv,value in [('G01',1.),('G02',-1.)]]
    training, testing = rows([0,30]), rows([60,90])
    for model in ('zero','shared_satellite','station_direction','station_satellite'):
        one = study.predict_block(training, testing, model)
        changed = [dict(r,residual_m=r['residual_m']*100+37) for r in testing]
        two = study.predict_block(training, changed, model)
        assert one['minimum_norm_coefficients_m'] == two['minimum_norm_coefficients_m']
        assert [r['prediction_m'] for r in one['test_predictions']] == [r['prediction_m'] for r in two['test_predictions']]


def test_all_failed_stations_remain_reported(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError('injected failure')
    monkeypatch.setattr(study.frame, 'calibrate_fixed', fail)
    report = study.run()
    assert report['status_counts'] == {'ENGINEERING_FAILURE':7}
    assert len(report['calibrations']) == 7
    assert report['predictions'] == [] and not report['calibration_complete']


def test_frozen_input_and_producer_ancestry():
    root = study.frame.ROOT
    _, _, _, _, receipt = study.inputs()
    for commit in ('65f39d1','5a9cdc0'):
        subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=root,check=True)
    for name, digest in receipt['sources_sha256'].items():
        blob = subprocess.check_output(['git','show','65f39d1:'+name],cwd=root)
        compatibility = json.loads((study.BASE/'inputs/hour_source_bytes/receipt.json').read_bytes())
        if name in compatibility:
            entry = compatibility[name]
            snapshot = (study.BASE/entry['snapshot']).read_bytes()
            assert hashlib.sha256(snapshot).hexdigest() == digest
            assert snapshot.replace(b'\r\n',b'\n') == blob
            assert hashlib.sha256(blob).hexdigest() == entry['git_lf_sha256']
        else:
            assert hashlib.sha256(blob).hexdigest() == digest
    for name, digest in receipt['files'].items():
        blob = subprocess.check_output(['git','show','5a9cdc0:research/exploratory/inputs/hour_reference/'+name],cwd=root)
        assert hashlib.sha256(blob).hexdigest() == digest
    blob = subprocess.check_output(['git','show','65f39d1:research/exploratory/hour_reference_plan.json'],cwd=root)
    assert hashlib.sha256(blob).hexdigest() == receipt['plan_sha256']


@pytest.mark.parametrize('variant', ['crlf','lf','modified'])
def test_only_declared_line_ending_variants_accepted(variant, monkeypatch, tmp_path):
    receipt = json.loads((study.BASE/'inputs/hour_source_bytes/receipt.json').read_bytes())
    entry = receipt['positioning/acquisition.py']
    raw = (study.BASE/entry['snapshot']).read_bytes()
    if variant == 'lf':
        raw = raw.replace(b'\r\n',b'\n')
    if variant == 'modified':
        raw += b'\n# different code\n'
    path = tmp_path/'positioning/acquisition.py'
    path.parent.mkdir()
    path.write_bytes(raw)
    monkeypatch.setattr(study.frame,'ROOT',tmp_path)
    if variant == 'modified':
        with pytest.raises(ValueError,match='beyond declared line endings'):
            study.source_bytes(path,entry['executed_sha256'])
    else:
        assert study.source_bytes(path,entry['executed_sha256']) == raw


def test_complete_hour_replay_and_chronological_cohort(monkeypatch):
    raw = (study.BASE/'results/hour_reference_v2.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '778b805ef839952ddcdf719aab8d1dc51975a901f0091e82c23c1cbc35d2e586'
    expected = json.loads(raw)
    original = study.frame.AttitudeReference.antenna_state
    def guard(self, sv, code, t):
        assert sv != 'G14'
        return original(self, sv, code, t)
    monkeypatch.setattr(study.frame.AttitudeReference, 'antenna_state', guard)
    comparison.compare_replay(checked.run(), expected)
    assert expected['status_counts'] == {'CALIBRATION_QUALIFIED':7}
    assert expected['training_times'] == list(range(12600,14400,30))
    assert expected['test_times'] == list(range(14400,16201,30))
    assert expected['evaluated_path_count']+len(expected['omitted_paths']) == expected['observed_path_count'] == 8080
    cohort = {(r['station'],r['time_s'],r['reference']) for r in expected['rows'] if r['time_s'] >= 14400}
    for result in expected['predictions']:
        assert {(r['station'],r['time_s'],r['reference']) for r in result['test_predictions']} == cohort
        assert result['test_count'] == 3954
    assert expected['predictions'][-1]['status_counts']['UNSEEN_TRAINING_SUPPORT'] == 1964
    assert expected['predictions'][-1]['all_test_error_rms_m'] is None
    assert not expected['absolute_future_rf_prediction'] and not expected['physical_covariance_qualified']
    blob = subprocess.check_output(['git','show','65d41fa:research/exploratory/hour_reference_v2.py'],cwd=study.frame.ROOT)
    assert hashlib.sha256(blob).hexdigest() == expected['source_sha256']
    assert hashlib.sha256((study.BASE/'hour_reference_v2.py').read_bytes()).hexdigest() == expected['source_sha256']


def test_auxiliary_checks_frozen_before_replay():
    evidence = checked.validate_auxiliary()
    assert evidence['frame']['frame_receipt'] == study.frame.RECEIPT_SHA256
    assert evidence['loading']['loading_receipt'] == checked.loading.RECEIPT_SHA
    expected = json.loads((study.BASE/'results/hour_reference_v2.json').read_bytes())['product_sha256']
    for name, key in [('reference_biases/g14/receipt.json','bias_receipt'),
                      ('reference_biases/g14/reference_bias.bia','bias_extract'),
                      ('reference_antennas/g14/receipt.json','antenna_receipt'),
                      ('reference_antennas/g14/reference_antenna.atx','antenna_extract')]:
        assert evidence['auxiliary']['inputs/'+name] == expected[key]
    subprocess.run(['git','merge-base','--is-ancestor','bcf674d','HEAD'],cwd=study.frame.ROOT,check=True)
    blob = subprocess.check_output(['git','show','bcf674d:research/exploratory/hour_reference_checked.py'],cwd=study.frame.ROOT)
    assert blob == (study.BASE/'hour_reference_checked.py').read_bytes()


@pytest.mark.parametrize('folder,filename', [
    ('reference_biases/g14','reference_bias.bia'),
    ('reference_antennas/g14','reference_antenna.atx'),
])
def test_consistent_auxiliary_replacement_rejected_before_calibration(monkeypatch, folder, filename):
    from pathlib import Path
    root = study.BASE/'inputs'/folder
    original = Path.read_bytes
    changed = original(root/filename)+b'\n'
    receipt = json.loads(original(root/'receipt.json'))
    receipt['extract_sha256'] = hashlib.sha256(changed).hexdigest()
    def replaced(path):
        if path == root/filename:
            return changed
        if path == root/'receipt.json':
            return json.dumps(receipt).encode()
        return original(path)
    def forbidden(*args, **kwargs):
        pytest.fail('calibration reached before rejecting changed auxiliary files')
    monkeypatch.setattr(Path,'read_bytes',replaced)
    monkeypatch.setattr(study,'run',forbidden)
    with pytest.raises(ValueError):
        checked.run()


@pytest.mark.parametrize('folder', ['station_frame','ocean_loading'])
def test_station_input_root_receipts_are_already_pinned(monkeypatch, folder):
    from pathlib import Path
    original = Path.read_bytes
    target = study.BASE/'inputs'/folder/'receipt.json'
    def replaced(path):
        return original(path)+(b' ' if path == target else b'')
    monkeypatch.setattr(Path,'read_bytes',replaced)
    with pytest.raises(ValueError):
        checked.validate_auxiliary()
