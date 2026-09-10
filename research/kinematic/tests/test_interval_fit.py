"""Interval physics, paired information, covariance and admission boundaries."""
import numpy as np
import pytest
from scipy.linalg import block_diag

from research.kinematic.interval_fit import fit_intervals, forecast_interval, interval_output
from research.kinematic.interval_study import CALIBRATION, design, solve_data
from research.kinematic.joint_study import residual_moments
from research.kinematic.receiver_time import predict
from research.kinematic.s2_validation import CLOCKS, JERK, STATE, TIMES, inertial_observations


@pytest.fixture(scope='module')
def context():
    d = design()
    d['nominal'] = solve_data(d, np.zeros(d['size']))
    d['code_only'] = solve_data(d, np.zeros(d['size']), include_phase=False)
    return d


def test_independent_endpoint_physics_and_paired_information(context):
    d = context
    for r in (d['nominal'], d['code_only']):
        assert r['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
        assert np.linalg.norm(r['state'][:3]-STATE[:3]) < .01
        assert np.linalg.norm(r['state'][3:6]-STATE[3:6]) < .0001
        assert r['rank'] == 46 and not r['real_rf_qualified']
    assert d['nominal']['residual_dof'] == 136
    assert d['code_only']['residual_dof'] == 66
    for part in (slice(0, 3), slice(3, 6)):
        assert np.linalg.eigvalsh(d['nominal']['covariance_joint'][part, part])[-1] < np.linalg.eigvalsh(d['code_only']['covariance_joint'][part, part])[-1]


def test_interval_prediction_is_not_endpoint_instantaneous_rate(context):
    station = context['stations'][7]
    values = interval_output(STATE, 30., 60., station, CLOCKS[7])
    codes, rates = inertial_observations([30., 60.], [station], [CLOCKS[7]])
    assert values[6] == pytest.approx(codes[-1, 0], abs=1e-6)
    assert values[7] == pytest.approx((codes[-1, 0]-codes[0, 0])/30, abs=1e-7)
    assert abs(values[7]-rates[-1, 0]) > .1


def test_full_covariance_transport_and_local_cost(context):
    d, r = context, context['nominal']
    moments = residual_moments(r, d['covariance'], d['covariance'])
    assert moments['expected_cost'] == pytest.approx(r['residual_dof'], abs=1e-6)
    assert moments['variance_cost'] == pytest.approx(2*r['residual_dof'], abs=1e-5)
    sigma = np.sqrt(np.diag(r['covariance_joint']))
    recovered = r['data_gain']@d['covariance']@r['data_gain'].T
    np.testing.assert_allclose((recovered-r['covariance_joint'])/np.outer(sigma, sigma), 0, atol=1e-7)
    np.testing.assert_allclose(r['data_gain']@r['data_jacobian'], np.eye(46), atol=2e-5)
    c = d['covariance']
    phase_white = .01**2*d['difference']@d['difference'].T
    assert phase_white[0, 7] == pytest.approx(-.01**2/30**2)
    assert c[d['count'], d['count']+7] == pytest.approx(.01**2+phase_white[0, 7])
    assert c[0, d['count']] != 0  # code/phase correlation survives differencing
    assert c[d['count'], d['count']+d['nrate']+1] != 0  # shared drift calibration


def test_raw_covariance_mapping_monte_carlo(context):
    d = context
    # Independent sampling checks cross-block signs as well as diagonal errors.
    rng = np.random.default_rng(112)
    draw = rng.normal(size=(18000, len(d['raw_covariance'])))@np.linalg.cholesky(d['raw_covariance']).T
    selected = [0, d['count'], d['count']+7, d['count']+d['nrate']+1]
    mapped = draw@d['transform'][selected].T
    actual = np.cov(mapped, rowvar=False)
    expected = d['covariance'][np.ix_(selected, selected)]
    scale = np.sqrt(np.outer(np.diag(expected), np.diag(expected)))
    np.testing.assert_allclose((actual-expected)/scale, 0, atol=.035)


@pytest.mark.parametrize('kind', ['slip', 'jerk', 'wrong_observable'])
def test_fixed_model_failures_are_not_accepted(context, kind):
    r = solve_data(context, np.zeros(context['size']), phase_step_m=.5 if kind == 'slip' else 0,
                   jerk=JERK if kind == 'jerk' else None, instantaneous=kind == 'wrong_observable')
    assert r['status'] == 'MODEL_REJECTED'
    assert r['conditional_residual_p'] < .01


@pytest.mark.parametrize('status', ['REFERENCE_CODE_REJECTED', 'REFERENCE_PHASE_RESIDUAL_REJECTED', 'REFERENCE_MODEL_ACCEPTED'])
def test_calibration_guard_before_target_values(context, status):
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('target decoded')
    with pytest.raises(ValueError, match='reference calibration rejected'):
        fit_intervals(TIMES, context['stations'][:7], Forbidden(), Forbidden(), CLOCKS[:7],
                      context['covariance'], calibration_statuses=[status]*7)


@pytest.mark.parametrize('kind', ['instantaneous_shape', 'singular_covariance', 'missing_endpoint', 'wrong_covariance_size'])
def test_invalid_window_or_covariance(context, kind):
    d = context
    codes, rates = inertial_observations(TIMES, d['stations'][:7], CLOCKS[:7])
    phase = (d['difference']@codes.ravel()).reshape(len(TIMES)-1, 7)
    covariance = d['covariance'].copy()
    if kind == 'instantaneous_shape': phase = rates
    if kind == 'singular_covariance': covariance[0] = 0; covariance[:, 0] = 0
    if kind == 'missing_endpoint': codes = codes[:-1]
    if kind == 'wrong_covariance_size': covariance = covariance[:-1, :-1]
    with pytest.raises(ValueError):
        fit_intervals(TIMES, d['stations'][:7], codes, phase, CLOCKS[:7], covariance,
                      calibration_statuses=[CALIBRATION]*7)


def test_forecast_excludes_values_and_preserves_frozen_covariance(context):
    d = context
    extended = block_diag(d['covariance'], np.diag([4., .0001]), .25*np.eye(3), np.diag([400., 2e-4/900]))
    result = forecast_interval(d['nominal'], 30, 60, d['stations'][7], CLOCKS[7], extended, calibration_status=CALIBRATION)
    truth = interval_output(STATE, 30, 60, d['stations'][7], CLOCKS[7])
    np.testing.assert_allclose(result['prediction'], truth, atol=.001, rtol=0)
    np.testing.assert_allclose(result['covariance_output'], result['mapping']@extended@result['mapping'].T, atol=1e-8)
    extended[0, 0] += 1
    with pytest.raises(ValueError, match='frozen fit-data block'):
        forecast_interval(d['nominal'], 30, 60, d['stations'][7], CLOCKS[7], extended, calibration_status=CALIBRATION)


@pytest.mark.parametrize('status', ['MODEL_REJECTED', 'AMBIGUOUS', 'BRANCH_SEARCH_INCOMPLETE'])
def test_rejected_fit_cannot_forecast(context, status):
    with pytest.raises(ValueError, match='accepted interval fit'):
        forecast_interval({'status': status}, 30, 60, None, None, None, calibration_status=CALIBRATION)


def test_invalid_forecast_interval_and_calibration(context):
    with pytest.raises(ValueError, match='ordered interval'):
        interval_output(STATE, 60, 30, context['stations'][7], CLOCKS[7])
    with pytest.raises(ValueError, match='held-out calibration'):
        forecast_interval(context['nominal'], 30, 60, None, None, None, calibration_status='REFERENCE_PHASE_RESIDUAL_REJECTED')


def test_small_correlated_perturbation_matches_local_inverse_gain(context):
    d, nominal = context, context['nominal']
    error = np.zeros(d['size'])
    # Perturb one measured receiver-clock drift within its declared uncertainty.
    error[d['count']+d['nrate']+1] = .0001
    plus = solve_data(d, error)
    minus = solve_data(d, -error)
    assert plus['status'] == minus['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
    expected = nominal['data_gain'][:11]@error
    np.testing.assert_allclose((plus['state']-minus['state'])/2, expected, atol=.003, rtol=.003)


def test_code_only_does_not_decode_phase(context):
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('phase decoded in code-only fit')
    d = context
    codes, _ = inertial_observations(TIMES, d['stations'][:7], CLOCKS[:7])
    covariance = d['covariance'][np.ix_(d['code_indices'], d['code_indices'])]
    result = fit_intervals(TIMES, d['stations'][:7], codes, Forbidden(), CLOCKS[:7], covariance,
                           calibration_statuses=[CALIBRATION]*7, include_phase=False)
    np.testing.assert_array_equal(result['state'], d['code_only']['state'])
