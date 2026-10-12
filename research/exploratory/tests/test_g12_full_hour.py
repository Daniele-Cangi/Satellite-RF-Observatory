"""Changing receiver subsets must preserve bias gauges and exposed failures."""
from collections import Counter
import hashlib
import json

import numpy as np
import pytest
from scipy.linalg import helmert

from research.exploratory import g12_full_hour as study


def test_subset_mapping_preserves_physical_differential_bias_and_local_gauge():
    rng = np.random.default_rng(146)
    local = rng.normal(size=(12, 4))
    global_coefficients = rng.normal(size=5)
    global_bias = helmert(6, full=False).T @ global_coefficients
    for start in (36000, 37800):
        stations = study.station_selection(start)
        indices = [study.GLOBAL_STATIONS.index(s) for s in stations]
        physical = global_bias[indices]
        local_contrasts = helmert(5, full=False) @ physical
        mapped = study.global_profile(local, stations)
        np.testing.assert_allclose(mapped @ global_coefficients,
                                   local @ local_contrasts, atol=1e-14)
        np.testing.assert_allclose(helmert(5, full=False) @ (physical + 19.),
                                   local_contrasts, atol=1e-14)


def test_unobserved_station_is_not_given_a_spurious_bias_constraint():
    early = study.global_profile(np.eye(4), study.station_selection(36000))
    late = study.global_profile(np.eye(4), study.station_selection(37800))
    partial = study.combine_profiles([
        {'start_gpst_s':37800, 'profile_per_m':late},
        {'start_gpst_s':37890, 'profile_per_m':late}])
    assert partial['rank'] == 4 and partial['parameter_count'] == 5
    assert partial['conditional_worst_contrast_sigma_m'] is None
    connected = study.combine_profiles([
        {'start_gpst_s':36000, 'profile_per_m':early},
        {'start_gpst_s':37800, 'profile_per_m':late}])
    assert connected['rank'] == 5
    assert set(study.station_selection(36000)) & set(study.station_selection(37800)) == set(study.COMMON)


def test_full_hour_clock_retains_original_diagnostics_exactly():
    old = json.loads((study.BASE/'results/reference_phase_clock_gps_only_v2.json').read_bytes())
    new = json.loads((study.BASE/'results/reference_phase_clock_full_hour_v1.json').read_bytes())
    assert new['evaluation_after_gpst_s'] == 36000
    assert new['exploratory_window_extension'] and not new['target_values_accessed']
    assert new['target_excluded'] == 'G12'
    for key in ('phase_clock_rates', 'held_out_reference_diagnostics'):
        assert [r for r in new[key] if r['time_s'] > 37800] == old[key]
    assert len(new['phase_clock_rates']) == 720
    assert new['stations']['YELL00CAN']['status'] != 'EVALUATED'
    assert new['failures']['REFERENCE_MODEL_FAILURE'] > 0
    assert new['summary']['held_out']['median']['max_abs'] > .02


def test_hour_retains_every_case_and_original_second_half_outcomes():
    result = json.loads((study.BASE/'results/g12_full_hour_v1.json').read_bytes())
    old = json.loads((study.BASE/'results/real_target_interval_v2.json').read_bytes())
    assert not result['target_orbit_used'] and not result['oracle_error_used']
    assert not result['new_confirmation']
    assert result['historical_code_floor_m'] == 20.
    assert result['target_elevation_mask_deg'] == 10.
    assert [c['start_gpst_s'] for c in result['cases']] == list(range(36000,39600,90))
    assert result['case_status_counts'] == dict(Counter(c['status'] for c in result['cases']))
    cases = {c['start_gpst_s']:c for c in result['cases']}
    for previous in old['cases']:
        current = cases[previous['start_gpst_s']]
        assert current['status'] == previous['status']
        for name, fit in previous.get('fits', {}).items():
            assert current['fits'][name]['status'] == fit['status']
            if 'state' in fit:
                np.testing.assert_allclose(current['fits'][name]['state'], fit['state'],
                                           rtol=0, atol=1e-5)
    for name, arcs in result['profiles'].items():
        admitted = [c['start_gpst_s'] for c in result['cases']
                    if c.get('fits', {}).get(name, {}).get('status') == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED']
        assert [a['start_gpst_s'] for a in arcs] == admitted
        for model, drift in [('constant',False), ('linear_drift',True)]:
            recomputed = study.combine_profiles(arcs, linear_drift=drift)
            saved = result['combined'][name][model]
            assert recomputed['rank'] == saved['rank']
            atol = 16*np.finfo(float).eps*recomputed['singular_per_m'][0]
            np.testing.assert_allclose(recomputed['singular_per_m'], saved['singular_per_m'],
                                       rtol=1e-12, atol=atol)
        for variant in result['finite_difference_robustness'][name].values():
            for model in ('constant', 'linear_drift'):
                baseline = result['combined'][name][model]['conditional_worst_contrast_sigma_m']
                assert abs(variant[model]['conditional_worst_contrast_sigma_m']/baseline - 1) < .02
    paths = {'target':'inputs/real_phase/g12_target_phase_v2.json',
             'baseline':'results/day_reference_v1.json',
             'positions':'inputs/day_reference/positions.json',
             'access':'real_target_phase_access_v2.json',
             'historical_rf':'results/real_target_interval_v2.json',
             'reference_phase_input':'inputs/real_phase/observations_gps_only_v2.json',
             'reference_clock':'results/reference_phase_clock_full_hour_v1.json'}
    for name, path in paths.items():
        assert hashlib.sha256((study.BASE/path).read_bytes()).hexdigest() == result['input_sha256'][name]


@pytest.mark.parametrize('mutation', ['target-access', 'wrong-clock-window'])
def test_invalid_access_or_calibration_window_stops_before_a_fit(tmp_path, monkeypatch, mutation):
    paths = ['inputs/real_phase/g12_target_phase_v2.json', 'results/day_reference_v1.json',
             'inputs/day_reference/positions.json', 'real_target_phase_access_v2.json',
             'results/real_target_interval_v2.json', 'inputs/real_phase/observations_gps_only_v2.json',
             'results/reference_phase_clock_full_hour_v1.json']
    for relative in paths:
        dest = tmp_path/relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((study.BASE/relative).read_bytes())
    if mutation == 'target-access':
        path = tmp_path/paths[0]
        data = json.loads(path.read_bytes())
        data['target_state_accessed'] = True
    else:
        path = tmp_path/paths[-1]
        data = json.loads(path.read_bytes())
        data['evaluation_after_gpst_s'] = 37800
    path.write_text(json.dumps(data), encoding='utf-8')
    monkeypatch.setattr(study, 'BASE', tmp_path)
    def forbidden_fit(*args, **kwargs):
        raise AssertionError('fit must not start outside the recorded input boundary')
    monkeypatch.setattr(study, 'fit_case', forbidden_fit)
    with pytest.raises(ValueError, match='boundary differs'):
        study.run(tmp_path/paths[-1])
