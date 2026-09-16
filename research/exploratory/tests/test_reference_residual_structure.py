from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from research.exploratory import reference_residual_structure as study

ROOT = Path(__file__).resolve().parents[3]
INPUTS = ROOT/'research/exploratory/inputs'
ARCHIVES = {'g14': ROOT/'experiments/positioning_g14_doy246_network', 'g12': INPUTS/'g12_doy248'}


def rows_at(times, station='A', refs=('G01', 'G02', 'G03', 'G04')):
    base = np.array([[1.,0.,0.], [0.,1.,0.], [0.,0.,1.], [-1.,0.,0.]])
    rows = []
    for t in times:
        angle = t*1e-3
        rotation = np.array([[np.cos(angle), -np.sin(angle), 0.], [np.sin(angle), np.cos(angle), 0.], [0.,0.,1.]])
        for i, sv in enumerate(refs):
            direction = rotation@base[i]
            rows.append({'station': station, 'time_s': float(t), 'reference': sv,
                         'los_enu': direction.tolist(), 'residual_m': float(direction@np.array([.5,-.3,.2])+t)})
    return rows


def test_direction_predicts_new_times_without_learning_from_test_values():
    train, test = rows_at([0,30,60]), rows_at([90,120])
    result = study.predict_block(train, test, 'station_direction')
    assert result['rank'] == 3 and result['predicted_count'] == 8
    assert result['minimum_norm_coefficients_m'] == pytest.approx([.5,-.3,.2], abs=1e-12)
    assert result['all_test_error_rms_m'] < 1e-12
    altered = deepcopy(test)
    for i, row in enumerate(altered):
        row['residual_m'] += 100*i
    changed = study.predict_block(train, altered, 'station_direction')
    assert changed['minimum_norm_coefficients_m'] == result['minimum_norm_coefficients_m']
    assert [r['prediction_m'] for r in changed['test_predictions']] == [r['prediction_m'] for r in result['test_predictions']]
    assert changed['all_test_error_rms_m'] > 10.


def test_common_clock_modes_are_unobservable_and_do_not_change_predictions():
    train, test = rows_at([0,30,60]), rows_at([90,120])
    baseline = study.predict_block(train, test, 'station_satellite')
    for row in train+test:
        row['residual_m'] += 1234.+row['time_s']**2
    shifted = study.predict_block(train, test, 'station_satellite')
    assert shifted['minimum_norm_coefficients_m'] == pytest.approx(baseline['minimum_norm_coefficients_m'], abs=1e-10)
    assert shifted['all_test_error_rms_m'] == pytest.approx(baseline['all_test_error_rms_m'], abs=1e-10)
    assert shifted['nullity'] == 1
    p = np.eye(4)-np.ones((4,4))/4
    # Arbitrarily large common error covariance disappears in residual space.
    assert p@(np.eye(4)+1e6*np.ones((4,4)))@p.T == pytest.approx(p, abs=1e-10)
    assert p[0,1]/p[0,0] == pytest.approx(-1./3)


def test_disconnected_training_gauges_make_cross_component_predictions_unidentifiable():
    training = rows_at([0,30], 'A', ('G01','G02'))+rows_at([0,30], 'B', ('G03','G04'))
    testing = rows_at([60], 'A', ('G01','G03'))
    result = study.predict_block(training, testing, 'shared_satellite')
    assert result['nullity'] == 2
    assert result['predicted_count'] == 0 and result['all_test_error_rms_m'] is None
    assert result['status_counts'] == {'UNIDENTIFIABLE_PREDICTION': 2}
    assert all(r['prediction_m'] is None for r in result['test_predictions'])


def test_new_link_does_not_get_an_invented_zero_bias():
    training = rows_at([0,30], refs=('G01','G02'))
    testing = rows_at([60], refs=('G01','G02','G03'))
    result = study.predict_block(training, testing, 'station_satellite')
    assert result['test_count'] == 3 and result['predicted_count'] == 0
    assert result['status_counts'] == {'UNSEEN_TRAINING_SUPPORT': 3}
    assert len(result['test_predictions']) == 3


def test_overlapping_train_test_times_are_rejected():
    with pytest.raises(ValueError, match='overlap'):
        study.predict_block(rows_at([0,30]), rows_at([30,60]), 'zero')


def test_varying_sets_are_projected_before_fitting_and_zero_baseline_is_explicit():
    training = rows_at([0], refs=('G01','G02','G03'))+rows_at([30], refs=('G02','G03','G04'))
    truth = {'G01': 1., 'G02': -2., 'G03': 3., 'G04': -1.}
    testing = rows_at([60])
    for row in training+testing:
        row['residual_m'] = truth[row['reference']]+row['time_s']
    fitted = study.predict_block(training, testing, 'shared_satellite')
    assert fitted['rank'] == 3 and fitted['nullity'] == 1
    assert fitted['all_test_error_rms_m'] < 1e-12
    zero = study.predict_block(training, testing, 'zero')
    assert zero['rank'] == 0 and zero['columns'] == []
    assert zero['all_test_error_rms_m'] == zero['supported_test_zero_rms_m']


def test_descriptive_energy_accounting_and_missing_correlations():
    rows = rows_at([0,30,60])
    y = study.center_blocks([r['residual_m'] for r in rows], rows)
    for row, value in zip(rows, y):
        row['residual_m'] = float(value)
    result = study.describe(rows, ['A','B'], ['G01','G02','G03','G04'])
    total = np.mean(y*y)
    assert result['within_pair_rms_m']**2 == pytest.approx(total*(1-result['pair_mean_energy_fraction']), abs=1e-14)
    assert result['projected_dimension'] == 9 and result['removed_common_modes'] == 3
    assert result['physical_covariance'] is None
    assert len(result['same_satellite_cross_station']) == 4
    assert all(r['status'] == 'INSUFFICIENT_SAMPLES' for r in result['same_satellite_cross_station'])
    assert study.correlation([1,2,3], [-1,-2,-3])['pearson'] == pytest.approx(-1.)
    assert study.correlation([1,1,1], [2,3,4])['status'] == 'DEGENERATE_SERIES'


def test_failed_case_is_retained(monkeypatch):
    rows = rows_at(range(0, 301, 30))
    class Context:
        times = list(range(0, 301, 30))
        target = 'G14'
        date_gpst = '2026-09-03'
    monkeypatch.setattr(study, 'prepare', lambda *a: (rows, [], Context(), ['A'], ['G01','G02','G03','G04'], {}, {}, 0.))
    original = study.predict_block
    def broken(training, testing, model):
        if model == 'shared_satellite':
            raise ValueError('injected failure')
        return original(training, testing, model)
    monkeypatch.setattr(study, 'predict_block', broken)
    result = study.run(*([None]*6))
    assert result['case_count'] == 8
    assert result['status_counts'] == {'EVALUATED': 6, 'ENGINEERING_FAILURE': 2}
    assert all(c['reason'] == 'ValueError: injected failure' for c in result['cases'] if c['status'] == 'ENGINEERING_FAILURE')


@pytest.mark.parametrize('tag', ['g14','g12'])
def test_bound_reports_replay_all_cases_rows_and_denominators(tag):
    path = ROOT/f'research/exploratory/results/{tag}_reference_residual_structure_v1.json'
    saved = json.loads(path.read_bytes())
    actual = study.run(ARCHIVES[tag], INPUTS/f'timed_reference_products/{tag}', INPUTS/f'reference_biases/{tag}',
                       INPUTS/f'reference_antennas/{tag}', INPUTS/f'reference_attitudes/{tag}',
                       ROOT/f'research/exploratory/results/{tag}_reference_attitude_v1.json')
    def compare(a,b):
        if isinstance(b,dict):
            assert a.keys() == b.keys()
            for k in b:
                compare(a[k],b[k])
        elif isinstance(b,list):
            assert len(a) == len(b)
            for x,y in zip(a,b):
                compare(x,y)
        elif isinstance(b,float):
            assert a == pytest.approx(b, abs=1e-8, rel=1e-10)
        else:
            assert a == b
    compare(saved,actual)
    for path,digest in saved['sources_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    prior = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_attitude_v1.json').read_bytes())
    expected = {(r['station'],r['time_s'],r['reference']) for r in prior['paths']}
    assert {(r['station'],r['time_s'],r['reference']) for r in saved['reference_rows']+saved['omitted_paths']} == expected
    assert saved['observed_path_count'] == len(expected)
    assert saved['evaluated_path_count'] == len(saved['reference_rows'])
    assert saved['case_count'] == 8 and saved['status_counts'] == {'EVALUATED':8}
    for case in saved['cases']:
        assert not set(case['training_times_s']) & set(case['test_times_s'])
        assert case['test_count'] == sum(case['status_counts'].values()) == len(case['test_predictions'])
        assert case['training_count']+case['test_count'] == saved['evaluated_path_count']
    assert not any(saved[k] for k in ('target_fit_performed','target_orbit_accessed','new_confirmation','qualified_error_budget','applied_to_production_estimator'))
