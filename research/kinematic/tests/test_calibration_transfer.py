"""Known-error injection, gauge cancellation and joint covariance regressions."""
import numpy as np
import pytest

from research.kinematic.calibration_transfer import operators, propagate, residual_blind_modes
from research.kinematic.calibration_transfer_study import study
from research.kinematic.phase_reference_bridge import phase_residual_covariance


def test_reference_offset_is_invisible_but_transfers_with_correct_sign():
    a = np.ones((4, 1))
    op = operators(a, np.ones((1, 1)), np.eye(4))
    injected = np.full(4, 100.)
    np.testing.assert_allclose(op['reference_residual']@injected, 0, atol=1e-12)
    np.testing.assert_allclose(op['reference_to_target']@injected, [-100.], atol=1e-12)
    np.testing.assert_allclose(op['joint_to_target']@np.r_[injected, 100.], 0, atol=1e-12)
    blind = residual_blind_modes(a, op['reference_to_target'])
    np.testing.assert_allclose(op['reference_residual']@blind['reference_error_basis'], 0, atol=1e-12)
    assert abs(blind['target_error_images'][0, 0]) == pytest.approx(.5)


def test_weighted_gain_matches_direct_perturbed_fit_and_target_prediction():
    a = np.column_stack([np.ones(7), np.arange(-3., 4.)])
    b = np.array([[1., 2.], [0., 1.]])
    weights = np.diag(np.arange(1., 8.)) + .2*np.ones((7, 7))
    op = operators(a, b, weights)
    theta, noise, target_noise = np.array([15., .2]), np.arange(7.)**2, np.array([2., 3.])
    chol = np.linalg.cholesky(weights)
    fit = np.linalg.lstsq(np.linalg.solve(chol, a), np.linalg.solve(chol, a@theta+noise), rcond=None)[0]
    np.testing.assert_allclose(op['joint_to_target']@np.r_[noise, target_noise],
                               b@theta+target_noise-b@fit, atol=1e-12)
    np.testing.assert_allclose(op['gain']@a, np.eye(2), atol=1e-12)


def test_shared_clock_gauge_cancels_for_multiple_target_observables():
    a = np.column_stack([np.ones(8), np.arange(8.)])
    b = np.array([[1., 3.], [0., 1.], [1., 15.]])
    op = operators(a, b, np.eye(8))
    gauge = np.array([1000., .25])
    np.testing.assert_allclose(op['joint_to_target']@np.r_[a@gauge, b@gauge], 0, atol=1e-10)


def test_matches_existing_phase_bridge_full_correlated_covariance():
    a = np.column_stack([np.ones(6), np.arange(6.)])
    b = np.array([[0., 1.], [0., 2.]])
    rng = np.random.default_rng(20260913)
    factor = rng.normal(size=(8, 8))
    cov = factor@factor.T + np.eye(8)
    old_clock, old_target = phase_residual_covariance(a, b, cov)
    op = operators(a, b, cov[:6, :6])
    np.testing.assert_allclose(propagate(op['gain'], cov[:6, :6]), old_clock, atol=1e-12)
    np.testing.assert_allclose(propagate(op['joint_to_target'], cov), old_target, atol=1e-12)


def test_semidefinite_common_mode_cancels_and_independence_does_not():
    op = operators(np.ones((4, 1)), np.ones((1, 1)), np.eye(4))
    assert propagate(op['joint_to_target'], np.ones((5, 5)))[0, 0] == pytest.approx(0, abs=1e-12)
    assert propagate(op['joint_to_target'], np.eye(5))[0, 0] == pytest.approx(1.25)


@pytest.mark.parametrize('cov', [None, np.eye(2), [[1., 2.], [0., 1.]],
                                [[1., 2.], [2., 1.]], [[1., float('nan')], [0., 1.]]])
def test_unknown_or_invalid_covariance_is_not_treated_as_zero(cov):
    mapping = np.ones((1, 3)) if np.array_equal(cov, np.eye(2)) else np.ones((1, 2))
    with pytest.raises(ValueError):
        propagate(mapping, cov)


def test_rank_deficient_fit_and_singular_weights_rejected():
    with pytest.raises(ValueError, match='rank deficient'):
        operators(np.ones((4, 2)), np.ones((1, 2)), np.eye(4))
    with pytest.raises(ValueError, match='positive definite'):
        operators(np.ones((4, 1)), np.ones((1, 1)), np.ones((4, 4)))


def test_study_quantifies_same_residuals_different_target_variance():
    result = study()
    examples = result['deterministic_examples']
    assert examples[0]['corrected_target_code_error_m'] == pytest.approx(-100.)
    assert examples[1]['corrected_target_phase_rate_error_m_s'] == pytest.approx(-.1)
    for row in examples:
        assert row['reference_residual_max_m'] < 1e-10
    assert result['blind_residual_max'] < 1e-10
    np.testing.assert_allclose([row['corrected_target_variance_m2'] for row in result['stochastic_examples']],
                               [37.25, 19.25, 1.25])
    for row in result['stochastic_examples']:
        np.testing.assert_allclose(row['reference_residual_variance_m2'], [.75]*4)
    assert not result['real_rf_qualified'] and not result['physical_amplitudes_established']


def test_saved_study_reproduces_computed_examples_with_portable_tolerance():
    import json
    from pathlib import Path
    saved = json.loads((Path(__file__).resolve().parents[1] /
                        'results/calibration_transfer_study_v1.json').read_bytes())
    fresh = study()
    assert saved['sources_sha256'] == fresh['sources_sha256']
    assert saved['scope'] == fresh['scope']
    for key in ('real_rf_qualified', 'target_orbit_accessed', 'physical_amplitudes_established',
                'population_coverage_established', 'blind_subspace_dimension'):
        assert saved[key] == fresh[key]
    for old, new in zip(saved['deterministic_examples'], fresh['deterministic_examples'], strict=True):
        assert old['case'] == new['case']
        for key in ('reference_residual_max_m', 'corrected_target_code_error_m',
                    'corrected_target_phase_rate_error_m_s'):
            assert old[key] == pytest.approx(new[key], abs=1e-10)
    for old, new in zip(saved['stochastic_examples'], fresh['stochastic_examples'], strict=True):
        assert old['shared_mode_correlation'] == new['shared_mode_correlation']
        assert old['corrected_target_variance_m2'] == pytest.approx(new['corrected_target_variance_m2'])
        np.testing.assert_allclose(old['reference_residual_variance_m2'],
                                   new['reference_residual_variance_m2'], atol=1e-12)
