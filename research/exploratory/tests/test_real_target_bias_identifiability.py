"""The exposed G12 bias result retains its denominator and near-null modes."""
import hashlib
import json

from research.exploratory.real_phase import BASE


def test_free_bias_contrasts_do_not_become_a_position_bound():
    frozen_bytes = (BASE/'results/real_target_interval_v2.json').read_bytes()
    report = json.loads((BASE/'results/real_target_bias_identifiability_v1.json').read_bytes())
    assert report['frozen_rf_report_sha256'] == hashlib.sha256(frozen_bytes).hexdigest()
    assert not report['target_orbit_used'] and not report['oracle_error_used']
    assert len(report['cases']) == 20
    assert report['counts']['phase_fit_status'] == {
        'MODEL_REJECTED': 15, 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED': 5}
    code = [case['models']['code_only'] for case in report['cases']]
    phase = [case['models']['code_phase'] for case in report['cases']
             if case['models']['code_phase']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED']
    assert all(row['rank'] == 38 and row['parameter_count'] == 40 for row in code)
    assert all(row['rank'] == 39 and row['parameter_count'] == 40 for row in phase)
    assert all(row['formal_position_sigma_max_m'] is None for row in code+phase)
    assert all(max(item['position_t0_m_per_1m'] for item in row['omitted_bias_unit_responses'])
               > 69. for row in code+phase)
    for row in phase:
        assert len(row['near_null_directions']) == 1
        direction = row['near_null_directions'][0]
        assert abs(sum(direction['station_bias_contrast_m_per_unit_scaled_mode'])) < 1e-9
        assert direction['position_t0_m_per_1m_max_station_bias'] > 9.
