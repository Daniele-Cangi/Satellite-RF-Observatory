"""Leave-one-out physical boundaries and after-fit state evaluation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import pytest

from research.exploratory import reference_state_validation as study
from research.kinematic.synthetic import receiver_positions


class Forbidden:
    def __float__(self):
        raise AssertionError('excluded number used')
    def __array__(self, *args, **kwargs):
        raise AssertionError('excluded array used')


def poison_products(data, candidate):
    result = deepcopy(data)
    products = result['products']
    for key in ['orbit_extract', 'clock_extract', 'bias_extract', 'attitude_extract']:
        lines = []
        for line in products[key].splitlines():
            if key == 'orbit_extract' and line.startswith('P'+candidate):
                line = line[:4]+'forbidden'.ljust(42)+line[46:]
            if key == 'clock_extract' and line.startswith('AS ') and line[3:7].strip() == candidate:
                line = 'AS '+candidate+' forbidden'
            if key == 'bias_extract' and line[11:14] == candidate and line[1:5].strip() == 'OSB':
                line = line[:35]+'forbidden'
            if key == 'attitude_extract' and line.startswith(' ATT '+candidate):
                line = line[:23]+'forbidden'
            lines.append(line)
        products[key] = '\n'.join(lines)+'\n'
    # Keep identity/structure while poisoning every numeric antenna offset.
    lines, block = [], []
    for line in products['antenna_extract'].splitlines():
        if conventions_label(line) == 'START OF ANTENNA':
            block = [line]
        elif block:
            block.append(line)
            if conventions_label(line) == 'END OF ANTENNA':
                own = any(conventions_label(s) == 'TYPE / SERIAL NO' and s[20:40].strip() == candidate for s in block)
                lines.extend(('forbidden'.ljust(60)+s[60:]) if own and conventions_label(s) == 'NORTH / EAST / UP' else s for s in block)
                block = []
        else:
            lines.append(line)
    products['antenna_extract'] = '\n'.join(lines)+'\n'
    return result


def conventions_label(line):
    return line[60:].strip()


def test_candidate_products_and_rf_cannot_influence_reference_calibration():
    _, data = study.read_inputs()
    poisoned = poison_products(data, 'G05')
    for epochs in poisoned['observations'].values():
        for epoch in epochs:
            if 'G05' in epoch['if_code_m']:
                epoch['if_code_m']['G05'] = Forbidden()
    for item in poisoned['phase']['stations'].values():
        for row in item['rows']:
            if row['reference'] == 'G05':
                row['code_m'] = row['phase_m'] = Forbidden()
    weather = study.interval.shared.meteo.WeatherGrid(study.interval.shared.meteo.read_inputs()[0])
    expected = study.calibration_environment(data, 'G05', weather)
    actual = study.calibration_environment(poisoned, 'G05', weather)
    for environment in [expected, actual]:
        assert environment[0]('ALGO00CAN', 36060.)['status'] == 'CALIBRATION_QUALIFIED'
    assert expected[0]('ALGO00CAN', 36060.) == actual[0]('ALGO00CAN', 36060.)
    assert expected[1]('ALGO00CAN', 36060.) == actual[1]('ALGO00CAN', 36060.)
    with pytest.raises(ValueError):
        study.oracle(poisoned, 'G05')
    with pytest.raises(ValueError, match='before product decoding'):
        study.subset_products(data, ['G05'], 'G05')


def toy_data():
    names = list('ABCDEF')
    xyz = receiver_positions()[:6]
    state = np.array([26e6, 2e6, 4e6, -250., 1800., 500.])
    curve = study.dynamics.Trajectory(state, [-100., 100.])
    code = study.dynamics.predict_codes(curve, 0., [-60., -30., 0.], xyz, np.zeros((6, 2)), [70000., .1])
    phase = {'stations': {s: {'rows': [
        {'reference': 'G05', 'time_s': 36000.+30*i, 'status': 'AVAILABLE',
         'code_m': code[i, j], 'phase_m': code[i, j]+1000*j} for i in range(3)]+[
        {'reference': 'G05', 'time_s': 36090., 'status': 'AVAILABLE', 'code_m': Forbidden(), 'phase_m': Forbidden()}]}
        for j, s in enumerate(names)}}
    data = {'plan': {'stations': names}, 'phase': phase}
    def offset(s, t):
        return {'status': 'CALIBRATION_QUALIFIED', 'epochs': [{'clock_m': 0.}]}
    def rate(s, t):
        return {'status': 'ESTIMATED', 'rate_m_s': 0.}
    return data, (offset, rate, lambda s, t: xyz[names.index(s)]), state


def test_training_masks_and_arcs_do_not_access_candidate_future(monkeypatch):
    data, environment, _ = toy_data()
    monkeypatch.setattr(study, 'calibration_environment', lambda *args: environment)
    arcs, windows = study.build_arcs(data, 'G05', None)
    assert len(arcs) == 1
    assert len(windows) == 20 and windows[0]['status'] == 'PREPARED'
    assert len(arcs[0]['stations']) >= 5
    assert arcs[0]['endpoint_gpst_s'] == 36060.
    assert arcs[0]['satellite_clock_count'] == 3
    assert np.isfinite(arcs[0]['rates_m_s']).all()
    assert len(windows[0]['rf_geometry']['snapshots']) == 3


def test_reference_rejection_precedes_candidate_numeric_access(monkeypatch):
    data, environment, _ = toy_data()
    for item in data['phase']['stations'].values():
        for row in item['rows']:
            row['code_m'] = row['phase_m'] = Forbidden()
    bad = lambda *args: {'status': 'REJECTED', 'epochs': []}
    monkeypatch.setattr(study, 'calibration_environment', lambda *args: (bad, environment[1], environment[2]))
    arcs, windows = study.build_arcs(data, 'G05', None)
    assert not arcs and windows[0]['status'] == 'REFERENCE_CALIBRATION_REJECTED'


def test_reference_mask_precedes_weather_and_phase_numeric_access(monkeypatch):
    refs = ['G05', 'G06', 'G07', 'G08', 'G09', 'G10']
    times = [36000., 36030., 36060.]
    data = {'plan': {'references': refs, 'date_gpst': '2026-09-05'},
        'observations': {'A': [{'time_s': t, 'if_code_m': {q: 1000. for q in refs}} for t in times]},
        'positions': {'A': [[6378137., 0., 0.]]*3},
        'phase': {'stations': {'A': {'rows': [
            {'reference': q, 'time_s': t, 'status': 'AVAILABLE',
             'phase_m': Forbidden() if q in ('G05', 'G06') else 1000.+.001*(t-36000.)}
            for q in refs for t in times]}}}}
    class Provider:
        def model(self, q, code, t, station, clock):
            assert q != 'G05'
            return 1000., 2. if q == 'G06' else 30.
    corrections = {(t, q): {'if_code_change_m': 0.} for t in times for q in refs if q != 'G05'}
    monkeypatch.setattr(study, 'subset_products', lambda *args: (Provider(), corrections))
    seen = []
    def components(provider, weather, mjd, q, code, t, station, clock):
        assert q not in ('G05', 'G06')
        seen.append(q)
        return {'legacy_baseline': 0., 'vmf3_full': 0.}, {}
    monkeypatch.setattr(study.day.atmosphere, 'components', components)
    def qualify(observations, station, context, references, model):
        assert references[36060.] == ['G07', 'G08', 'G09', 'G10']
        return {'status': 'CALIBRATION_QUALIFIED', 'epochs': [{'clock_m': 0.}]}
    monkeypatch.setattr(study, 'calibrate_fixed', qualify)
    offset, rate, _ = study.calibration_environment(data, 'G05', None)
    assert offset('A', 36060.)['status'] == 'CALIBRATION_QUALIFIED'
    estimate = rate('A', 36060.)
    assert estimate['status'] == 'ESTIMATED' and estimate['reference_count'] == 4
    assert estimate['rate_m_s'] == pytest.approx(.001)
    assert seen


def test_ambiguous_rf_geometry_retains_both_branches_without_orbit_tiebreak(monkeypatch):
    monkeypatch.setattr(study, 'solve', lambda *args, **kwargs: {'branches': [
        {'q': [26e6, 0., 0., 0.]}, {'q': [-26e6, 0., 0., 0.]}]})
    record, selected = study.rf_geometry(np.zeros((3, 5)), np.zeros((3, 5)), np.ones((3, 5, 3)))
    assert record['status'] == 'RF_GEOMETRY_AMBIGUOUS' and not selected
    assert len(record['snapshots'][0]['branches']) == 2


def test_state_error_and_covariance_are_scored_at_matching_gpst():
    _, _, state = toy_data()
    fit = {'state_ecef_m_m_s': state, 'epoch_gpst_s': 36060., 'j2': study.dynamics.J2,
           'integrated_bounds_s': [-100., 500.], 'conditional_global_covariance': np.diag([100.]*3+[.01]*3)}
    arcs = [{'endpoint_gpst_s': 36060.}, {'endpoint_gpst_s': 36360.}]
    curve = study.dynamics.Trajectory(state, [-100., 500.])
    exact = lambda t: (curve(t-36060.), curve(t-36060.))
    evaluated = study.state_errors(fit, arcs, exact)
    assert evaluated['summary']['ALL']['count'] == 4
    assert evaluated['summary']['BEYOND_ALL_TRAINING']['count'] == 1
    assert evaluated['summary']['ALL']['position_error_m']['max_abs'] < 1e-5
    assert evaluated['summary']['ALL']['state_inside_formal_95_count'] == 4
    def displaced(t):
        value = curve(t-36060.)
        value[:3] += 1e6
        return value, value
    scored = study.state_errors(fit, arcs, displaced)
    assert scored['summary']['ALL']['position_inside_formal_95_count'] == 0
    assert scored['summary']['ALL']['state_inside_formal_95_count'] == 0
    assert study.state_errors({'status': 'NUMERICAL_FAILURE'}, arcs, exact)['status'] == 'FIT_UNAVAILABLE'


def test_rf_scoring_retains_missing_receiver_without_replacing_it():
    data, _, _ = toy_data()
    names = list('ABCDEF')
    for item in data['phase']['stations'].values():
        previous, future = item['rows'][-2:]
        future.update(code_m=10., phase_m=previous['phase_m']+3.)
    data['phase']['stations']['A']['rows'][-1].update(status='REJECTED', phase_m=Forbidden())
    predictions = [{'endpoint_gpst_s': 36060., 'status': 'PREDICTED', 'kind': 'BEYOND_ALL_TRAINING',
                    'fit_status': 'MODEL_REJECTED', 'stations': names, 'code_m': np.full(6, 8.),
                    'phase_rate_m_s': np.full(6, .05)},
                   {'endpoint_gpst_s': 36120., 'status': 'PREDICTION_FAILED'}]
    scored = study.score_rf(data, 'G05', predictions)
    summary = scored['summary']['ALL']
    assert summary['pair_status_counts'] == {'WITHHELD_UNAVAILABLE': 1, 'EVALUATED': 5}
    assert summary['code_residual_m']['rms'] == pytest.approx(2.)
    assert summary['phase_rate_residual_m_s']['rms'] == pytest.approx(.05)
    assert scored['windows'][1]['status'] == 'UNSCORED'


def test_oracles_open_after_all_fits_and_missing_oracle_is_retained(monkeypatch):
    events = []
    monkeypatch.setattr(study, 'read_inputs', lambda: ({}, {'plan': {'references': ['G05', 'G06']}}))
    monkeypatch.setattr(study, 'build_arcs', lambda data, q, weather: (
        [{'candidate': q}, {'candidate': q}], [{'status': 'PREPARED'}]))
    def fit(arcs, **kwargs):
        events.append('fit '+arcs[0]['candidate'])
        return {'status': 'MODEL_REJECTED', 'state_ecef_m_m_s': np.ones(6),
                'conditional_global_covariance': np.eye(6), 'scaled_condition': 1.}
    monkeypatch.setattr(study.dynamic_fit, 'fit', fit)
    monkeypatch.setattr(study.interval, 'predict', lambda *args: [])
    monkeypatch.setattr(study, 'score_rf', lambda *args: {'windows': []})
    def oracle(data, q):
        assert events[:2] == ['fit G05', 'fit G06']
        events.append('oracle '+q)
        if q == 'G05':
            raise ValueError('synthetic missing orbit')
        return lambda t: None
    monkeypatch.setattr(study, 'oracle', oracle)
    monkeypatch.setattr(study, 'state_errors', lambda *args: {'status': 'EVALUATED', 'rows': []})
    # Source hashes must still address real modules, not the injected test code.
    monkeypatch.setattr(study.inspect, 'getmodule', lambda f: study)
    result = study.run()
    assert events == ['fit G05', 'fit G06', 'oracle G05', 'oracle G06']
    assert result['candidates']['G05']['state_evaluation']['status'] == 'ORACLE_UNAVAILABLE'
    assert result['candidates']['G06']['state_evaluation']['status'] == 'EVALUATED'
    assert result['fit_status_counts'] == {'MODEL_REJECTED': 2}


def test_initial_preparation_failures_and_original_producer_are_preserved():
    raw = (study.BASE/'results/reference_state_validation_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '6c3762da503a7d8cee489c8e8b3d0ed2d1d8e89c0aefed9f366c620439f90206'
    report = json.loads(raw)
    name = 'research/exploratory/reference_state_validation.py'
    source = subprocess.check_output(['git', 'show', '6e4042d:'+name], cwd=study.BASE.parents[1])
    assert hashlib.sha256(source).hexdigest() == report['source_sha256'][name]
    assert report['fit_status_counts'] == {'INSUFFICIENT_PREPARED_ARCS': 17, 'BRANCH_SEARCH_INCOMPLETE': 5}
    failures = [w for result in report['candidates'].values() for w in result['windows']
                if w['status'] == 'PREPARATION_FAILED']
    assert len(failures) == 33
    assert {w['reason'] for w in failures} == {'outside bounded atmosphere domain'}


@pytest.mark.parametrize('version',[2,3])
def test_corrected_real_result_replays_rf_and_state_errors_without_refitting(version):
    raw, data = study.read_inputs()
    root = study.BASE.parents[1]
    result = json.loads((study.BASE/f'results/reference_state_validation_v{version}.json').read_bytes())
    assert result['input_sha256'] == {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()}
    for path, wanted in result['source_sha256'].items():
        # v2 retains its original interval-midpoint velocity initializer; the
        # active solver may evolve without rewriting that failed execution.
        producer = '9f61866' if version==2 else 'ac902e5'
        source = subprocess.check_output(['git','show',producer+':'+path],cwd=root)
        assert hashlib.sha256(source).hexdigest() == wanted
    assert not any(result[k] for k in ['candidate_orbit_used_in_fit', 'candidate_clock_used_in_fit',
        'candidate_bias_or_attitude_used_in_fit', 'g12_state_accessed', 'new_confirmation',
        'physical_covariance_qualified', 'production_floors_changed'])
    assert set(result['candidates']) == set(data['plan']['references'])
    expected_statuses = {'INSUFFICIENT_PREPARED_ARCS':17,'BRANCH_SEARCH_INCOMPLETE':4,'NUMERICAL_FAILURE':1}
    if version==3:
        expected_statuses = {'INSUFFICIENT_PREPARED_ARCS':17,'BRANCH_SEARCH_INCOMPLETE':5}
        previous = json.loads((study.BASE/'results/reference_state_validation_v2.json').read_bytes())
        assert result['input_sha256'] == previous['input_sha256']
        assert result['weather_receipt_sha256'] == previous['weather_receipt_sha256']
        assert result['selection'] == previous['selection'] and result['model'] == previous['model']
        for candidate,record in result['candidates'].items():
            assert record['windows'] == previous['candidates'][candidate]['windows']
    assert result['fit_status_counts'] == expected_statuses
    evaluated_count = 0
    for candidate, record in result['candidates'].items():
        assert len(record['windows']) == 20
        assert [w['start_gpst_s'] for w in record['windows']] == list(range(36000, 39600, 180))
        assert 'PREPARATION_FAILED' not in record['window_status_counts']
        assert study.score_rf(data, candidate, record['rf_predictions']) == record['rf_evaluation']
        fit = record['fit']
        if 'state_ecef_m_m_s' not in fit:
            assert record['state_evaluation']['status'] == 'FIT_UNAVAILABLE'
            continue
        assert fit['branch_failures'] and fit['residual_threshold_p'] == .01
        if version==3:
            assert all('exterior-Earth' in b['reason'] for b in fit['branch_failures'])
            for prediction in record['rf_predictions']:
                if prediction['status']=='PREDICTED':
                    assert np.min(prediction['elevation_deg'])>=10.
        # Reconstruct only evaluation epochs from retained preparation metadata;
        # neither calibration nor fitting is repeated in CI.
        arcs = [{'endpoint_gpst_s': w['start_gpst_s']+60} for w in record['windows'] if w['status'] == 'PREPARED']
        replay = study.state_errors(fit, arcs, study.oracle(data, candidate))
        expected = record['state_evaluation']
        assert len(replay['rows']) == len(expected['rows'])
        for a, b in zip(replay['rows'], expected['rows'], strict=True):
            assert a['gpst_s'] == b['gpst_s'] and a['kind'] == b['kind'] and a['status'] == b['status']
            assert a['position_error_m'] == pytest.approx(b['position_error_m'], abs=1e-4)
            assert a['velocity_error_m_s'] == pytest.approx(b['velocity_error_m_s'], abs=1e-7)
            assert a['position_inside_formal_95'] == b['position_inside_formal_95']
            assert a['state_inside_formal_95'] == b['state_inside_formal_95']
        assert replay['summary']['BEYOND_ALL_TRAINING']['count'] == 1
        evaluated_count += len(replay['rows'])
    assert evaluated_count == (108 if version==2 else 126)
    g11 = result['candidates']['G11']['fit']
    if version==2:
        # Preserve the failure, not an earlier smaller-cohort fit or lower mask.
        assert g11['status'] == 'NUMERICAL_FAILURE'
        assert any('9.996 deg' in b['reason'] for b in g11['branch_failures'])
    else:
        assert g11['status'] == 'BRANCH_SEARCH_INCOMPLETE'
        assert g11['branches'][0]['history']
