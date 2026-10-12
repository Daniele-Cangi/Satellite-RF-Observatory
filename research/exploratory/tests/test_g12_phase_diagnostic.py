"""Physical contrast, missing-data and calibration boundaries for G12 replay."""
from copy import deepcopy
import json

import numpy as np
import pytest

from research.exploratory import g12_phase_diagnostic as study
from research.exploratory import g12_dynamic_fit as shared


def clock_block(station, time, rate):
    return {'station': station, 'time_s': time, 'reference_count': 5,
            'estimators': {'median': {'status': 'ESTIMATED', 'rate_m_s': rate}}}


def test_temporal_contrast_cancels_linear_clock_but_retains_curvature():
    # Independent endpoint construction: curvature is solely at the middle
    # sample, not a parameter derived from a target residual by the diagnostic.
    tags = np.array([-60., -30., 0.])
    slopes = np.array([.03, -.04, .02])
    shape = np.array([.006, -.003, .001])
    clocks = 100.+tags[:, None]*slopes
    clocks[1] += 30.*shape
    rates = np.diff(clocks, axis=0)/30.
    residual = rates-slopes
    result = study.contrast_components(residual, shape)
    np.testing.assert_allclose(result['half_difference_m_s'], shape, atol=1e-15)
    np.testing.assert_allclose(result['remaining_m_s'], 0., atol=1e-15)
    # Adding a common curvature leaves only that common mode after references.
    result = study.contrast_components(residual+np.array([[.002], [-.002]]), shape)
    np.testing.assert_allclose(result['common_remaining_m_s'], .002, atol=1e-15)
    np.testing.assert_allclose(result['spatial_contrast_remaining_m_s'], 0., atol=1e-15)


def test_reference_target_label_rejected_before_any_numeric_conversion():
    class Forbidden:
        def __float__(self):
            raise AssertionError('target numeric value accessed')
    clock = {'target_excluded': 'G12', 'target_values_accessed': False,
             'phase_clock_rates': [clock_block('S', 30., Forbidden())],
             'held_out_reference_diagnostics': [{'reference': 'G12',
                                                 'phase_minus_model_rate_m_s': Forbidden()}]}
    with pytest.raises(ValueError, match='before numeric access'):
        study.reference_index(clock)


def test_reference_missing_slots_and_rejections_remain_visible():
    estimates = {('S', t): clock_block('S', t, v) for t, v in [(30., .01), (60., .03)]}
    rows = {('S', 30., 'G05'): {'status': 'ESTIMATED', 'error_m_s_median': .0003},
            ('S', 60., 'G05'): {'status': 'ESTIMATED', 'error_m_s_median': -.0001},
            ('S', 30., 'G06'): {'status': 'ESTIMATED', 'error_m_s_median': .0002}}
    result = study.matched_reference((estimates, rows), 'S', 60.)
    assert result['status'] == 'MATCHED' and result['half_difference_m_s'] == pytest.approx(-.01)
    assert len(result['references']) == 2
    assert result['references'][0]['leave_one_out_half_difference_error_m_s'] == pytest.approx(.0002)
    assert result['references'][1]['status'] == 'UNSUPPORTED_REFERENCE_CONTRAST'
    assert result['references'][1]['endpoint_statuses'] == ['ESTIMATED', 'MISSING']
    estimates['S', 60.]['estimators']['median']['status'] = 'REJECTED'
    result = study.matched_reference((estimates, rows), 'S', 60.)
    assert result['status'] == 'REFERENCE_CLOCK_UNAVAILABLE'
    assert len(result['references']) == 2


def test_duplicate_reference_block_and_link_are_fail_closed():
    row = {'station': 'S', 'time_s': 30., 'reference': 'G05'}
    clock = {'target_excluded': 'G12', 'target_values_accessed': False,
             'phase_clock_rates': [clock_block('S', 30., .01)]*2,
             'held_out_reference_diagnostics': [row]}
    with pytest.raises(ValueError, match='duplicate reference clock'):
        study.reference_index(clock)
    clock['phase_clock_rates'] = clock['phase_clock_rates'][:1]
    clock['held_out_reference_diagnostics'] *= 2
    with pytest.raises(ValueError, match='duplicate held-out reference'):
        study.reference_index(clock)


def test_reference_predictions_ignore_future_and_failures_are_retained():
    estimates = {('S', t): clock_block('S', t, v) for t, v in [(30., .01), (60., .03), (90., .02)]}
    original = study.reference_forecast((estimates, {}), 'S', 60.)
    assert original['constant_prediction_m_s'] == pytest.approx(.02)
    assert original['linear_rate_prediction_m_s'] == pytest.approx(.05)
    estimates['S', 90.] = clock_block('S', 90., .5)
    changed = study.reference_forecast((estimates, {}), 'S', 60.)
    for key in ['constant_prediction_m_s', 'linear_rate_prediction_m_s']:
        assert original[key] == changed[key]
    del estimates['S', 90.]
    missing = study.reference_forecast((estimates, {}), 'S', 60.)
    assert missing['status'] == 'EVALUATION_REFERENCE_UNAVAILABLE'
    assert missing['linear_rate_prediction_m_s'] == original['linear_rate_prediction_m_s']
    del estimates['S', 30.]
    assert study.reference_forecast((estimates, {}), 'S', 60.)['status'] == 'TRAINING_REFERENCE_UNAVAILABLE'


def test_real_replay_preserves_rejection_covariance_and_excludes_target_future():
    raw = {k: (study.BASE/p).read_bytes() for k, p in study.FILES.items()}
    data = {k: json.loads(v) for k, v in raw.items()}
    selection = data['fit']['variants']['code_phase_central_j2']['cohort']
    future_keys = {tuple(k) for k in selection['withheld_endpoint_keys']}
    class Forbidden:
        def __float__(self):
            raise AssertionError('target future value decoded')
    poisoned = deepcopy(data)
    for s, item in poisoned['target']['stations'].items():
        for r in item.get('rows', []):
            if (s, r['time_s']) in future_keys:
                for key in ['code_m', 'phase_m', 'geometry_free_phase_m']:
                    r[key] = Forbidden()
    # The old fitted geometries/corrections must remain irrelevant to this replay.
    for case in poisoned['hour']['cases']:
        case['propagation_m'] = case['elevation_deg'] = case['clock_prior'] = Forbidden()
    result = study.run(poisoned, raw)
    stored = json.loads((study.BASE/'results/g12_phase_diagnostic_v1.json').read_bytes())
    assert result['cohort'] == stored['cohort']
    for force in ['central', 'central_j2']:
        variant = result['variants'][force]
        assert variant['original_fit_status'] == 'MODEL_REJECTED'
        assert variant['original_p_value'] < .01
        assert variant['original_branch_failures'] == stored['variants'][force]['original_branch_failures']
        assert len(variant['windows']) == 8
        assert variant['summary']['interval_residual_m_s']['count'] == 80
        assert variant['summary']['contrasts']['remaining_m_s']['count'] == 40
        assert variant['summary']['replayed_joint_cost'] == pytest.approx(
            data['fit']['variants']['code_phase_'+force]['fit']['weighted_residual_cost'], abs=1e-5)
        for window in variant['windows']:
            # Independently derived from three iid .02 m endpoints at 30 s:
            # half-sum variance = sigma²/(2*dt²); half-difference = 3*sigma²/(2*dt²).
            np.testing.assert_allclose(window['half_sum_covariance'], np.eye(5)*.02**2/(2*30**2))
            np.testing.assert_allclose(window['half_difference_covariance'], np.eye(5)*3*.02**2/(2*30**2))
            np.testing.assert_allclose(window['half_sum_half_difference_covariance'], 0., atol=1e-20)
        for key in ['half_difference_m_s', 'remaining_m_s', 'spatial_contrast_remaining_m_s']:
            assert variant['summary']['contrasts'][key]['rms'] == pytest.approx(
                stored['variants'][force]['summary']['contrasts'][key]['rms'], abs=1e-8)
        assert variant['summary']['exact_ablation_minus_algebra_m_s']['max_abs'] < 2e-8
    forecast = result['reference_forecast']['summary']
    assert forecast['status_counts'] == {'EVALUATED': 40}
    assert forecast['linear_rate_worsened_count'] == 28
    assert forecast['linear_rate_error_m_s']['rms'] > forecast['constant_error_m_s']['rms']
    assert not any(result[k] for k in ['target_orbit_used', 'oracle_error_used', 'new_confirmation',
                                      'solver_changed', 'weights_changed', 'physical_covariance_qualified'])
