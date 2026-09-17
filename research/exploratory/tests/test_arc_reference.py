import hashlib
import json
import subprocess

import numpy as np
import pytest

from research.exploratory import arc_reference as study
from research.exploratory import prepare_arc_reference_checked as preparation
from research.exploratory import solid_earth_study as comparison


def test_fixed_second_arc_and_transfer_training():
    plan, ctx, observations, positions, receipt = study.inputs()
    assert list(ctx.times) == list(range(18000,21601,30))
    assert plan['training_before_gpst_s'] == 19800
    assert len(observations) == 7
    for name in plan['stations']:
        assert [e['time_s'] for e in observations[name]] == list(ctx.times)
        assert np.shape(positions[name]) == (121,3)
        assert all('G14' not in e['if_code_m'] for e in observations[name])
    prior = study.transfer_training(plan)
    assert len(prior) == 3777
    assert sorted({r['time_s'] for r in prior}) == list(range(12600,14400,30))
    assert study.validate_auxiliary() == receipt['auxiliary_provenance']


def test_second_arc_cannot_train_on_future_values():
    plan = {'training_before_gpst_s':19800,
            'models':['zero','shared_satellite','station_direction','station_satellite']}
    def rows(times):
        return [{'station':'A','time_s':t,'reference':sv,'residual_m':value,
                 'los_enu':[0.5,0.5,0.7071067811865476]}
                for t in times for sv,value in [('G01',1.),('G02',-1.)]]
    current = rows([18000,18030,19800,19830])
    prior = rows([12600,12630])
    baseline = study.compare_models(current,plan,prior)
    changed = [dict(r,residual_m=100*r['residual_m']+23) if r['time_s']>=19800 else r for r in current]
    poisoned = study.compare_models(changed,plan,prior)
    for one, two in zip(baseline,poisoned,strict=True):
        for a,b in zip(one,two,strict=True):
            assert a['minimum_norm_coefficients_m'] == b['minimum_norm_coefficients_m']
            assert [r['prediction_m'] for r in a['test_predictions']] == [r['prediction_m'] for r in b['test_predictions']]
    changed_training = [dict(r,residual_m=10*r['residual_m']) if r['time_s']<19800 else r for r in current]
    local, transferred = study.compare_models(changed_training,plan,prior)
    assert local[1]['minimum_norm_coefficients_m'] != baseline[0][1]['minimum_norm_coefficients_m']
    assert transferred == baseline[1]
    with pytest.raises(ValueError,match='precede'):
        study.compare_models(current,plan,rows([18000]))


def test_target_rejected_before_second_arc_calibration(monkeypatch):
    original = study.pinned
    def poisoned(path,digest):
        raw = original(path,digest)
        if path == study.INPUTS/'observations.json':
            data = json.loads(raw)
            next(iter(data.values()))[0]['if_code_m']['G14'] = 2e7
            return json.dumps(data).encode()
        return raw
    monkeypatch.setattr(study,'pinned',poisoned)
    with pytest.raises(ValueError,match='unadmitted reference'):
        study.inputs()


def test_failed_second_arc_suppresses_both_predictions(monkeypatch):
    def fail(*args,**kwargs):
        return {'status':'CALIBRATION_NOT_QUALIFIED','epochs':[]}
    monkeypatch.setattr(study.frame,'calibrate_fixed',fail)
    report = study.run()
    assert report['status_counts'] == {'CALIBRATION_NOT_QUALIFIED':7}
    assert report['predictions'] == report['transferred_predictions'] == []
    assert not report['calibration_complete']


def test_second_arc_inputs_and_implementation_frozen_before_execution():
    _,_,_,_,receipt = study.inputs()
    root = study.frame.ROOT
    for commit in ('b611bdb','08792b9'):
        subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=root,check=True)
    plan = subprocess.check_output(['git','show','b611bdb:research/exploratory/arc_reference_plan.json'],cwd=root)
    assert hashlib.sha256(plan).hexdigest() == receipt['plan_sha256']
    assert plan == (study.BASE/'arc_reference_plan.json').read_bytes()
    for name,digest in receipt['files'].items():
        raw = subprocess.check_output(['git','show','08792b9:research/exploratory/inputs/arc_reference/'+name],cwd=root)
        assert hashlib.sha256(raw).hexdigest() == digest
    for name,digest in receipt['sources_sha256'].items():
        raw = subprocess.check_output(['git','show','b611bdb:'+name],cwd=root)
        actual = study.source_bytes(root/name,digest)
        assert raw.replace(b'\r\n',b'\n') == actual.replace(b'\r\n',b'\n')
    source = subprocess.check_output(['git','show','08792b9:research/exploratory/arc_reference.py'],cwd=root)
    assert source == (study.BASE/'arc_reference.py').read_bytes()


def test_complete_second_arc_replay_and_same_test_cohort(monkeypatch):
    raw = (study.BASE/'results/arc_reference_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '0068da07dbc9d5ed6841d0ebf2a297cfd9879151e03bd83ca60dfed358ed8920'
    expected = json.loads(raw)
    original = study.frame.AttitudeReference.antenna_state
    def guard(self,sv,code,t):
        assert sv != 'G14'
        return original(self,sv,code,t)
    monkeypatch.setattr(study.frame.AttitudeReference,'antenna_state',guard)
    comparison.compare_replay(study.run(),expected)
    assert expected['status_counts'] == {'CALIBRATION_QUALIFIED':7}
    assert expected['training_times'] == list(range(18000,19800,30))
    assert expected['test_times'] == list(range(19800,21601,30))
    assert expected['evaluated_path_count']+len(expected['omitted_paths']) == expected['observed_path_count'] == 7913
    assert all(r['status']=='BELOW_ELEVATION_MASK' for r in expected['omitted_paths'])
    cohort = {(r['station'],r['time_s'],r['reference']) for r in expected['rows'] if r['time_s']>=19800}
    prior = json.loads(study.pinned(study.BASE/expected['plan']['transfer_training_report'],expected['transfer_training_report_sha256']))
    for candidates in (expected['predictions'],expected['transferred_predictions']):
        assert [r['model'] for r in candidates] == expected['plan']['models']
        for candidate in candidates:
            assert candidate['test_count'] == 3446
            assert {(r['station'],r['time_s'],r['reference']) for r in candidate['test_predictions']} == cohort
    for old,new in zip(prior['predictions'],expected['transferred_predictions'],strict=True):
        assert old['columns'] == new['columns']
        assert old['minimum_norm_coefficients_m'] == new['minimum_norm_coefficients_m']
    assert expected['predictions'][-1]['status_counts']['UNSEEN_TRAINING_SUPPORT'] == 1093
    assert expected['transferred_predictions'][-1]['status_counts'] == {'UNSEEN_TRAINING_SUPPORT':3446}
    assert expected['transferred_predictions'][-1]['all_test_error_rms_m'] is None
    assert expected['transferred_predictions'][-1]['supported_test_error_rms_m'] is None
    assert not expected['physical_covariance_qualified'] and not expected['absolute_future_rf_prediction']
    assert hashlib.sha256((study.BASE/'arc_reference.py').read_bytes()).hexdigest() == expected['source_sha256']


def test_preparation_preflight_matches_authoritative_frozen_inputs():
    preparation.preflight()
    root = study.frame.ROOT
    subprocess.run(['git','merge-base','--is-ancestor','715069b','HEAD'],cwd=root,check=True)
    source = subprocess.check_output(['git','show','715069b:research/exploratory/prepare_arc_reference_checked.py'],cwd=root)
    assert source == (study.BASE/'prepare_arc_reference_checked.py').read_bytes()


@pytest.mark.parametrize('kind', ['observation','orbit','timed_receipt','attitude_receipt'])
def test_preparation_rejects_changed_upstream_inputs_before_work(monkeypatch,kind,tmp_path):
    from pathlib import Path
    paths = {
        'observation': study.frame.verified.paths('g14')['admission_receipt'].parent/'raw_observations/ALGO00CAN_R_20262460000_01D_30S_MO.crx.gz.json',
        'orbit': study.BASE/'inputs/timed_reference_products/g14/reference_orbit.txt',
        'timed_receipt': study.BASE/'inputs/timed_reference_products/g14/receipt.json',
        'attitude_receipt': study.BASE/'inputs/reference_attitudes/g14/receipt.json',
    }
    original = Path.read_bytes
    def changed(path):
        raw = original(path)
        if path != paths[kind]:
            return raw
        if kind == 'observation':
            value = json.loads(raw)
            value['sha256'] = '0'*64
            return json.dumps(value).encode()
        return raw+b' '
    def forbidden(*args,**kwargs):
        pytest.fail('producer reached before rejecting changed upstream input')
    monkeypatch.setattr(Path,'read_bytes',changed)
    monkeypatch.setattr(preparation.frozen,'prepare',forbidden)
    with pytest.raises(ValueError):
        preparation.prepare(tmp_path,tmp_path,tmp_path,tmp_path)
