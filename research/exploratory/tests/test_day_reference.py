import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from research.exploratory import day_reference as study
from research.exploratory import day_reference_checked as checked
from research.exploratory import day_reference_inputs as basis
from research.exploratory import solid_earth_study as comparison


def test_distinct_day_fixed_cohort_and_previous_overlap():
    plan,ctx,observations,positions,receipt = study.inputs()
    assert ctx.date_gpst == '2026-09-05' and ctx.target == 'G12'
    assert list(ctx.times) == list(range(36000,39601,30))
    assert plan['training_before_gpst_s'] == 37800
    assert len(plan['stations']) == 7 and len(plan['references']) == 22
    admitted,_,_,_,_,_,auxiliary = basis.load_basis(plan)
    assert auxiliary == receipt['auxiliary_provenance']
    for old in admitted['observation_receipts']:
        if old['station'] in plan['stations']:
            new = receipt['observation_receipts'][old['station']]
            assert all(new[k] == old[k] for k in old)
    fr = json.loads((study.BASE/'results/g12_station_frame_epoch_v1.json').read_bytes())
    so = json.loads((study.BASE/'results/g12_solid_earth_v1.json').read_bytes())
    oc = json.loads((study.BASE/'results/g12_ocean_pole_v1.json').read_bytes())
    for station in fr['station_models']:
        name = station['station']
        assert observations[name][60:71] == admitted['stations'][name]['reference_observations']
        xyz = (np.array(station['positions']['final_transport']) +
               np.array(so['station_displacements_ecef_m'][name]['solid_earth']) +
               np.array(oc['station_additional_displacements_ecef_m'][name]['ocean_ce_plus_pole_2018']))
        assert np.array(positions[name])[60:71] == pytest.approx(xyz,abs=2e-6,rel=0)


def test_changed_day_or_cohort_rejected_by_authoritative_basis():
    plan = basis.read_plan()
    with pytest.raises(ValueError,match='fixed distinct-day'):
        basis.load_basis(dict(plan,date_gpst='2026-09-03'))
    with pytest.raises(ValueError,match='fixed distinct-day'):
        basis.load_basis(dict(plan,stations=plan['stations'][:-1]))


@pytest.mark.parametrize('folder,filename', [
    ('reference_biases/g12','reference_bias.bia'),
    ('reference_antennas/g12','reference_antenna.atx'),
    ('timed_reference_products/g12','reference_orbit.txt'),
])
def test_changed_upstream_extract_and_receipt_rejected(monkeypatch,folder,filename):
    root = study.BASE/'inputs'/folder
    original = Path.read_bytes
    changed = original(root/filename)+b'\n'
    receipt = json.loads(original(root/'receipt.json'))
    if filename == 'reference_orbit.txt':
        receipt['orbit']['extract_sha256'] = hashlib.sha256(changed).hexdigest()
    else:
        receipt['extract_sha256'] = hashlib.sha256(changed).hexdigest()
    def replaced(path):
        if path == root/filename:
            return changed
        if path == root/'receipt.json':
            return json.dumps(receipt).encode()
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',replaced)
    with pytest.raises(ValueError):
        basis.load_basis(basis.read_plan())


def test_new_target_code_rejected_at_input_boundary(monkeypatch):
    original = study.pinned
    def replaced(path,digest):
        raw = original(path,digest)
        if path == study.INPUTS/'observations.json':
            value = json.loads(raw)
            next(iter(value.values()))[0]['if_code_m']['G12'] = 2e7
            return json.dumps(value).encode()
        return raw
    monkeypatch.setattr(study,'pinned',replaced)
    with pytest.raises(ValueError,match='unadmitted reference'):
        study.inputs()


def test_failed_calibrations_retained_without_predictions(monkeypatch):
    def failed(*args,**kwargs):
        return {'status':'CALIBRATION_NOT_QUALIFIED','epochs':[]}
    monkeypatch.setattr(study.frame,'calibrate_fixed',failed)
    report = study.run()
    assert report['status_counts'] == {'CALIBRATION_NOT_QUALIFIED':7}
    assert report['predictions'] == [] and not report['calibration_complete']


def test_day_plan_inputs_and_sources_frozen_before_execution():
    _,_,_,_,receipt = study.inputs()
    root = study.frame.ROOT
    for commit in ('736b536','6237b99'):
        subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=root,check=True)
    plan = subprocess.check_output(['git','show','736b536:research/exploratory/day_reference_plan.json'],cwd=root)
    assert hashlib.sha256(plan).hexdigest() == receipt['plan_sha256'] == basis.PLAN_SHA
    for name,digest in receipt['files'].items():
        raw = subprocess.check_output(['git','show','6237b99:research/exploratory/inputs/day_reference/'+name],cwd=root)
        assert hashlib.sha256(raw).hexdigest() == digest
    for name,digest in receipt['sources_sha256'].items():
        raw = subprocess.check_output(['git','show','736b536:'+name],cwd=root)
        actual = study.source_bytes(root/name,digest)
        assert raw.replace(b'\r\n',b'\n') == actual.replace(b'\r\n',b'\n')
    source = subprocess.check_output(['git','show','6237b99:research/exploratory/day_reference.py'],cwd=root)
    assert source == (study.BASE/'day_reference.py').read_bytes()


def test_complete_distinct_day_replay_and_chronological_predictions(monkeypatch):
    raw = (study.BASE/'results/day_reference_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'ff4caa87d4963524252437184ab67128b9a75beaf704b664dff1951350b33600'
    expected = json.loads(raw)
    antenna = study.frame.AttitudeReference.antenna_state
    components = study.atmosphere.components
    dates = set()
    def guarded_antenna(self,sv,code,t):
        assert sv != 'G12'
        return antenna(self,sv,code,t)
    def guarded_weather(provider,weather,mjd_day,*args):
        assert mjd_day == 61288
        dates.add(mjd_day)
        return components(provider,weather,mjd_day,*args)
    monkeypatch.setattr(study.frame.AttitudeReference,'antenna_state',guarded_antenna)
    monkeypatch.setattr(study.atmosphere,'components',guarded_weather)
    comparison.compare_replay(checked.run(),expected)
    assert dates == {61288}
    assert expected['status_counts'] == {'CALIBRATION_QUALIFIED':7}
    assert expected['training_times'] == list(range(36000,37800,30))
    assert expected['test_times'] == list(range(37800,39601,30))
    assert expected['evaluated_path_count']+len(expected['omitted_paths']) == expected['observed_path_count'] == 9009
    assert len(expected['omitted_paths']) == 935
    assert all(r['status']=='BELOW_ELEVATION_MASK' for r in expected['omitted_paths'])
    cohort = {(r['station'],r['time_s'],r['reference']) for r in expected['rows'] if r['time_s']>=37800}
    assert [r['model'] for r in expected['predictions']] == expected['plan']['models']
    for candidate in expected['predictions']:
        assert candidate['training_count'] == 4132 and candidate['test_count'] == 3942
        assert {(r['station'],r['time_s'],r['reference']) for r in candidate['test_predictions']} == cohort
    assert expected['predictions'][-1]['status_counts']['UNSEEN_TRAINING_SUPPORT'] == 1141
    assert expected['predictions'][-1]['all_test_error_rms_m'] is None
    assert not expected['physical_covariance_qualified'] and not expected['absolute_future_rf_prediction']
    assert hashlib.sha256((study.BASE/'day_reference.py').read_bytes()).hexdigest() == expected['source_sha256']


def test_checked_entry_point_frozen_before_retained_source_audit():
    root = study.frame.ROOT
    subprocess.run(['git','merge-base','--is-ancestor','5387ba3','HEAD'],cwd=root,check=True)
    source = subprocess.check_output(['git','show','5387ba3:research/exploratory/day_reference_checked.py'],cwd=root)
    assert source == Path(checked.__file__).read_bytes()
    audit = json.loads((study.BASE/'results/day_reference_source_audit_v1.json').read_bytes())
    _,_,_,_,receipt = study.inputs()
    _,timed,_,_,_,_,_ = basis.load_basis(basis.read_plan())
    assert audit['source_sha256'] == hashlib.sha256(source).hexdigest()
    assert audit['runner_sha256'] == checked.RUNNER_SHA
    assert audit['input_receipt_sha256'] == study.RECEIPT_SHA
    assert audit['after_execution'] and audit['rederived_orbit_matches']
    assert audit['orbit_archive_sha256'] == timed['orbit']['source_compressed_sha256']
    assert audit['rederived_orbit_sha256'] == receipt['files']['timed/reference_orbit.txt']
    assert audit['retained_celestial_sha256'] == receipt['celestial_raw_sha256']


def test_checked_entry_point_rejects_modified_runner_before_calibration(monkeypatch):
    original = Path.read_bytes
    def changed(path):
        return original(path)+(b'\n# changed implementation\n' if path == Path(study.__file__) else b'')
    def forbidden(*args,**kwargs):
        pytest.fail('modified runner reached calibration')
    monkeypatch.setattr(Path,'read_bytes',changed)
    monkeypatch.setattr(study,'run',forbidden)
    with pytest.raises(ValueError):
        checked.run()
