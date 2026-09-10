"""Physical error transport checks, not population-coverage validation."""
import numpy as np
import pytest

from research.kinematic.inverse_uncertainty import budget, linearize, validate_covariance
from research.kinematic.s2_validation import CLOCKS, JERK, TIMES
from research.kinematic.uncertainty_study import JERK_AXIS_BOUND, actual_jerk_case, covariance_cases, refit_probe, setup, systematic_modes


@pytest.fixture(scope='module')
def context():
    return setup()


def test_baseline_recovers_joint_fit_covariance(context):
    r = context['response']
    cov = covariance_cases(context)['s2a_known_holdout']
    recovered = r['parameter_response']@cov@r['parameter_response'].T
    expected = context['result']['covariance_joint']
    # Scale-aware comparison includes poorly conditioned radial/clock directions.
    sigma = np.sqrt(np.diag(expected))
    np.testing.assert_allclose((recovered-expected)/np.outer(sigma, sigma), 0, atol=2e-5)


def test_holdout_clock_and_measurement_noise_reach_prediction(context):
    r = context['response']
    b, n = r['blocks'], r['input_size']
    cov = np.zeros((n, n))
    cov[b['heldout_clock'].start+1, b['heldout_clock'].start+1] = .1**2
    out = budget(r, cov)['covariance_output']
    assert out[6, 6] == pytest.approx(36., rel=1e-4)
    assert out[7, 7] == pytest.approx(.01, rel=1e-4)
    np.testing.assert_array_equal(out[:6], 0)
    cov[b['heldout_noise'], b['heldout_noise']] = [[400., .2], [.2, .0025]]
    enlarged = budget(r, cov)['covariance_output']
    np.testing.assert_allclose(enlarged[6:, 6:]-out[6:, 6:], [[400., .2], [.2, .0025]])


def test_shared_clock_error_cancels_against_correlated_holdout(context):
    r = context['response']
    b, n = r['blocks'], r['input_size']
    mode = np.zeros(n)
    mode[b['clock_means']] = np.tile([100., 0.], 7)
    only_fit = r['mapping']@mode
    mode[b['heldout_clock']] = [100., 0.]
    shared = r['mapping']@mode
    assert abs(only_fit[6]) > 90
    assert abs(shared[6]) < .01
    # Retaining the cross block is essential; summing independent variances fails.
    joint = budget(r, np.outer(mode, mode))['covariance_output']
    independent = budget(r, np.diag(mode**2))['covariance_output']
    assert joint[6, 6] < independent[6, 6]*1e-6


def test_extra_independent_error_is_positive_semidefinite_increment(context):
    cases = covariance_cases(context)
    base = budget(context['response'], cases['s2a_known_holdout'])['covariance_output']
    enlarged = budget(context['response'], cases['uncertain_stations_and_holdout'])['covariance_output']
    delta = enlarged-base
    scale = np.sqrt(np.diag(enlarged))
    assert np.linalg.eigvalsh(delta/np.outer(scale, scale)).min() > -1e-9


@pytest.mark.parametrize('case', ['negative', 'asymmetric', 'indefinite', 'nonfinite', 'zero_cross', 'bad_shape'])
def test_invalid_covariance_rejected(case):
    cov = np.eye(3)
    if case == 'negative': cov[2, 2] = -1e-20
    if case == 'asymmetric': cov[0, 1] = .1
    if case == 'indefinite': cov[0, 1] = cov[1, 0] = 1.01
    if case == 'nonfinite': cov[0, 0] = np.nan
    if case == 'zero_cross': cov[0, 0], cov[0, 1] = 0., .01
    if case == 'bad_shape': cov = np.eye(2)
    with pytest.raises(ValueError):
        validate_covariance(cov, 3)


@pytest.mark.parametrize('fit_status,failed_index', [('MODEL_REJECTED', None), ('AMBIGUOUS', None),
    ('BRANCH_SEARCH_INCOMPLETE', None), ('CONDITIONAL_MODEL_ACCEPTED', 0), ('CONDITIONAL_MODEL_ACCEPTED', 7)])
def test_rejection_gate_includes_holdout_calibration(context, fit_status, failed_index):
    statuses = context['statuses'].copy()
    if failed_index is not None:
        statuses[failed_index] = 'REFERENCE_DOPPLER_REJECTED'
    with pytest.raises(ValueError, match='accepted fit'):
        linearize({**context['result'], 'status': fit_status}, TIMES, context['stations'][:7],
            context['observation_cov'], context['clock_cov'], 60., context['stations'][7], CLOCKS[7],
            calibration_statuses=statuses)


def test_affine_box_bound_covers_corners_and_includes_direct_truth_change(context):
    r = context['response']
    names, modes, direct = systematic_modes(context)
    out = budget(r, np.zeros((r['input_size'], r['input_size'])),
                 systematic_inputs=modes, direct_output_errors=direct)
    expected = r['mapping']@modes+direct
    np.testing.assert_allclose(out['systematic_output_modes'], expected)
    assert names[-1] == 'constant_jerk_z'
    assert np.linalg.norm(expected[:3, 3:]) > 20*np.linalg.norm(direct[:3, 3:])
    for signs in np.array(np.meshgrid(*[[-1., 1.]]*6)).T.reshape(-1, 6):
        error = expected@signs
        assert np.all(abs(error) <= out['affine_box_component_bound']+1e-10)
        assert np.linalg.norm(error[:3]) <= out['affine_box_position_norm_bound_m']+1e-10


@pytest.mark.parametrize('index', [0, 1, 2, 3, 4, 5])
def test_local_modes_agree_with_complete_nonlinear_refits(context, index):
    _, modes, direct = systematic_modes(context)
    result = refit_probe(context, modes[:, index], direct[:, index])
    assert result['fit_statuses'] == ['CONDITIONAL_MODEL_ACCEPTED']*2
    assert np.linalg.norm(result['difference'][:3]) < .05
    assert np.linalg.norm(result['difference'][3:6]) < .001
    assert abs(result['difference'][6]) < .01
    assert abs(result['difference'][7]) < 1e-5


def test_actual_cubic_generator_reveals_fit_distortion_not_just_future_remainder(context):
    _, modes, direct = systematic_modes(context)
    actual = actual_jerk_case(context, np.full(3, JERK_AXIS_BOUND))
    expected = (context['response']['mapping']@modes+direct)[:, 3:].sum(axis=1)
    assert actual['status'] == 'CONDITIONAL_MODEL_ACCEPTED'
    assert np.linalg.norm(actual['output_error'][:3]-expected[:3]) < .05
    assert np.linalg.norm(actual['output_error'][:3]) > 20*actual['direct_future_position_remainder_m']


def test_rejected_actual_motion_has_no_excluded_prediction(context):
    actual = actual_jerk_case(context, JERK)
    assert actual['status'] == 'MODEL_REJECTED'
    assert 'prediction' not in actual and 'output_error' not in actual


def test_fit_holdout_measurement_cross_covariance_is_used(context):
    r = context['response']
    mode = np.zeros(r['input_size'])
    mode[r['blocks']['observations'].start] = 20.
    predicted = r['mapping']@mode
    mode[r['blocks']['heldout_noise']] = predicted[6:]
    joint = budget(r, np.outer(mode, mode))['covariance_output']
    assert abs(joint[6, 6]) < 1e-10
    assert abs(joint[7, 7]) < 1e-10
