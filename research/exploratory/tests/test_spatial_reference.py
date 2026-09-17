import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from research.exploratory import spatial_reference as study
from research.exploratory import spatial_reference_checked as checked
from research.exploratory.solid_earth_study import compare_replay


def fixture():
    stations = [str(i) for i in range(7)]
    rows = [{'station':s,'time_s':t,'reference':sv,'residual_m':v}
            for s in stations for t in (0,30) for sv,v in [('G01',1.),('G02',-1.)]]
    return stations,rows


def test_held_out_receiver_and_future_rows_never_enter_training(monkeypatch):
    stations,rows = fixture()
    def predict(training,testing,model):
        assert {r['station'] for r in training}==set(stations)-{'0'}
        assert all(r['time_s']==0 for r in training)
        assert all(r['station']=='0' and r['time_s']==30 for r in testing)
        return {'model':model}
    monkeypatch.setattr(study,'predict_block',predict)
    for row in rows:
        if row['station']=='0' and row['time_s']==0:
            row['residual_m']=float('nan')  # excluded historical values are not read by fitting
    study.fold(rows,stations,'0',30,'shared_satellite')


def test_test_values_and_other_receivers_future_do_not_change_fitted_predictions():
    stations,rows = fixture()
    first = study.fold(rows,stations,'0',30,'shared_satellite')
    for row in rows:
        if row['station']=='0' or row['time_s']>=30:
            row['residual_m'] *= 7
    second = study.fold(rows,stations,'0',30,'shared_satellite')
    assert first['minimum_norm_coefficients_m']==second['minimum_norm_coefficients_m']
    assert [r['prediction_m'] for r in first['test_predictions']]==[r['prediction_m'] for r in second['test_predictions']]
    assert first['all_test_error_rms_m'] != second['all_test_error_rms_m']


def test_unseen_reference_keeps_entire_test_block_and_null_pooled_score():
    stations,rows = fixture()
    rows[-1]['reference']='G03'
    result = study.fold(rows,stations,'6',30,'shared_satellite')
    assert result['status_counts']=={'UNSEEN_TRAINING_SUPPORT':2}
    pooled = study.pool([result],2)
    assert pooled['test_count']==2 and pooled['predicted_count']==0
    assert pooled['all_test_error_rms_m'] is None and pooled['supported_zero_rms_m'] is None


def test_disconnected_training_graph_rejects_unidentifiable_new_contrast():
    stations,rows = fixture()
    for row in rows:
        if row['station'] in ('3','4','5'):
            row['reference']={'G01':'G03','G02':'G04'}[row['reference']]
        if row['station']=='6' and row['reference']=='G02':
            row['reference']='G03'
    result = study.fold(rows,stations,'6',30,'shared_satellite')
    assert result['rank']==2
    assert result['status_counts']=={'UNIDENTIFIABLE_PREDICTION':2}
    assert result['all_test_error_rms_m'] is None


def test_pool_rejects_duplicate_test_paths():
    stations,rows = fixture()
    result = study.fold(rows,stations,'0',30,'zero')
    with pytest.raises(ValueError,match='duplicated'):
        study.pool([result,result],4)


@pytest.mark.parametrize('mutation',['target','duplicate','missing_epoch'])
def test_input_rows_reject_invalid_cohort(mutation):
    _,day,reports=study.inputs(checked.PLAN_SHA)
    rows=copy.deepcopy(reports['rapid']['rows'])
    if mutation=='target':
        rows[0]['reference']=day['target_excluded']
    elif mutation=='duplicate':
        rows.append(rows[0])
    else:
        rows=[r for r in rows if (r['station'],r['time_s'])!=(day['stations'][0],day['start_gpst_s'])]
    with pytest.raises(ValueError):
        study.validate_rows(rows,day)


def test_changed_input_bytes_rejected(monkeypatch):
    original=Path.read_bytes
    def changed(path):
        return original(path)+(b'\n' if path==study.BASE/'results/day_reference_v1.json' else b'')
    monkeypatch.setattr(Path,'read_bytes',changed)
    with pytest.raises(ValueError):
        study.inputs(checked.PLAN_SHA)


def test_complete_replay_and_each_test_receiver_scored_once():
    raw=(study.BASE/'results/spatial_reference_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='376b4283c6451b5e3ce0f8927647f835db20d035a0d08012cf8bf6cf8106f035'
    expected=json.loads(raw)
    compare_replay(checked.run(),expected)
    for variant in expected['variants'].values():
        for model in variant.values():
            assert model['pooled']['test_count']==model['pooled']['predicted_count']==3942
            assert len(model['folds'])==7
            for fold in model['folds']:
                assert fold['excluded_station'] not in fold['training_stations']
                assert len(fold['training_stations'])==6
                assert fold['training_times_s']==list(range(36000,37800,30))
                assert fold['test_times_s']==list(range(37800,39601,30))
    assert not expected['physical_covariance_qualified'] and not expected['upstream_station_independence_established']


def test_all_executed_sources_including_wrapper_frozen_before_execution():
    root=study.BASE.parents[1]
    subprocess.run(['git','merge-base','--is-ancestor','a3283d9','HEAD'],cwd=root,check=True)
    for name in [*checked.SOURCES,'spatial_reference_checked.py','spatial_reference_plan.json']:
        frozen=subprocess.check_output(['git','show','a3283d9:research/exploratory/'+name],cwd=root)
        assert frozen==(study.BASE/name).read_bytes()


def test_changed_runner_rejected_before_fitting(monkeypatch):
    original=Path.read_bytes
    def changed(path):
        return original(path)+(b'\n' if path==Path(study.__file__) else b'')
    monkeypatch.setattr(Path,'read_bytes',changed)
    monkeypatch.setattr(study,'run',lambda *a:pytest.fail('modified source executed'))
    with pytest.raises(ValueError):
        checked.run()
