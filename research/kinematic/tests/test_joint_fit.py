"""Joint fit, residual distribution and held-out error covariance contracts."""
import numpy as np
import pytest
from scipy.linalg import block_diag

from research.kinematic.joint_fit import fit_joint, forecast_joint
from research.kinematic.joint_study import CALIBRATION, SECONDS, design, residual_moments, solve_data
from research.kinematic.receiver_time import fit
from research.kinematic.s2_validation import CLOCKS, JERK, STATE, TIMES, inertial_observations


@pytest.fixture(scope='module')
def context():
    d = design()
    d['nominal'] = solve_data(d, np.zeros(d['size']), d['joint'])
    return d


def test_joint_noiseless_physics_and_local_chi_square(context):
    result = context['nominal']
    assert result['status'] == 'CONDITIONAL_JOINT_MODEL_ACCEPTED'
    assert np.linalg.norm(result['state'][:3]-STATE[:3]) < .01
    assert result['rank'] == 46 and result['residual_dof'] == 143
    moments = residual_moments(result, context['joint'], context['joint'])
    assert moments['expected_cost'] == pytest.approx(143., abs=1e-6)
    assert moments['variance_cost'] == pytest.approx(286., abs=1e-5)
    np.testing.assert_allclose(result['data_gain']@result['data_jacobian'], np.eye(46), atol=2e-6)
    recovered = result['data_gain']@context['joint']@result['data_gain'].T
    sigma = np.sqrt(np.diag(result['covariance_joint']))
    np.testing.assert_allclose((recovered-result['covariance_joint'])/np.outer(sigma, sigma), 0, atol=1e-8)


def test_dropping_cross_blocks_miscalibrates_residual_cost(context):
    result = solve_data(context, np.zeros(context['size']), context['blocks'])
    moments = residual_moments(result, context['blocks'], context['joint'])
    assert abs(moments['expected_cost']-143) > 1
    assert abs(moments['variance_cost']-286) > 10


def test_s2a_limit_with_precise_ground_coordinates(context):
    d = context
    codes, rates = inertial_observations(TIMES, d['stations'][:7], CLOCKS[:7])
    obs = d['blocks'][:d['nobs'], :d['nobs']]
    clocks = d['blocks'][d['nobs']:d['nobs']+14, d['nobs']:d['nobs']+14]
    covariance = block_diag(obs, clocks, 1e-6*np.eye(21))
    old = fit(TIMES, d['stations'][:7], codes, rates, obs, CLOCKS[:7], clocks)
    new = fit_joint(TIMES, d['stations'][:7], codes, rates, CLOCKS[:7], covariance, calibration_statuses=[CALIBRATION]*7)
    assert new['status'] == 'CONDITIONAL_JOINT_MODEL_ACCEPTED'
    np.testing.assert_allclose(new['state'], old['state'], atol=.001, rtol=0)
    sigma = np.sqrt(np.diag(old['covariance_joint']))
    np.testing.assert_allclose((new['covariance_joint'][:25, :25]-old['covariance_joint'])/np.outer(sigma, sigma), 0, atol=2e-5)


@pytest.mark.parametrize('mode_index', [0, 1, 8])
def test_data_gain_matches_nonlinear_refit_with_uncertain_coordinates(context, mode_index):
    error = context['modes'][:context['size'], mode_index]*.1
    plus = solve_data(context, error, context['joint'])
    minus = solve_data(context, -error, context['joint'])
    expected = context['nominal']['data_gain']@error
    actual = (np.r_[plus['state'], plus['receiver_clocks'].ravel(), plus['stations_fitted_m'].ravel()]
              -np.r_[minus['state'], minus['receiver_clocks'].ravel(), minus['stations_fitted_m'].ravel()])/2
    assert plus['status'] == minus['status'] == 'CONDITIONAL_JOINT_MODEL_ACCEPTED'
    np.testing.assert_allclose(actual[:3], expected[:3], atol=.005, rtol=0)
    np.testing.assert_allclose(actual[3:9], expected[3:9], atol=1e-5, rtol=0)
    np.testing.assert_allclose(actual[25:], expected[25:], atol=1e-5, rtol=0)


def test_shared_holdout_clock_covariance_and_frozen_fit_block(context):
    d = context
    forecast = forecast_joint(d['nominal'], SECONDS, d['stations'][7], CLOCKS[7],
                              d['extended'], calibration_status=CALIBRATION)
    independent = d['extended'].copy()
    independent[:d['size'], d['size']:] = 0
    independent[d['size']:, :d['size']] = 0
    other = forecast_joint(d['nominal'], SECONDS, d['stations'][7], CLOCKS[7], independent, calibration_status=CALIBRATION)
    np.testing.assert_array_equal(forecast['prediction'], other['prediction'])
    assert other['covariance_output'][6, 6] > forecast['covariance_output'][6, 6]+40
    changed = d['extended'].copy()
    changed[0, 0] += 1
    with pytest.raises(ValueError, match='frozen fit-data block'):
        forecast_joint(d['nominal'], SECONDS, d['stations'][7], CLOCKS[7], changed, calibration_status=CALIBRATION)


@pytest.mark.parametrize('kind', ['asymmetric', 'negative', 'singular', 'nonfinite', 'dimension'])
def test_joint_covariance_rejects_invalid_without_jitter(context, kind):
    d = context
    covariance = d['joint'].copy()
    if kind == 'asymmetric': covariance[0, 1] += 1
    if kind == 'negative': covariance[0, 0] = -1
    if kind == 'singular': covariance[0] = 0; covariance[:, 0] = 0
    if kind == 'nonfinite': covariance[0, 0] = np.nan
    if kind == 'dimension': covariance = covariance[:-1, :-1]
    codes, rates = inertial_observations(TIMES, d['stations'][:7], CLOCKS[:7])
    with pytest.raises(ValueError):
        fit_joint(TIMES, d['stations'][:7], codes, rates, CLOCKS[:7], covariance, calibration_statuses=[CALIBRATION]*7)


def test_reference_rejection_precedes_target_decoding(context):
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('target values consumed after reference rejection')
    with pytest.raises(ValueError, match='reference calibration rejected'):
        fit_joint(TIMES, context['stations'][:7], Forbidden(), Forbidden(), CLOCKS[:7],
                  context['joint'], calibration_statuses=['REFERENCE_CODE_REJECTED']*7)


@pytest.mark.parametrize('status', ['MODEL_REJECTED', 'AMBIGUOUS', 'BRANCH_SEARCH_INCOMPLETE'])
def test_fit_rejection_prevents_forecast(context, status):
    with pytest.raises(ValueError, match='accepted joint fit'):
        forecast_joint({**context['nominal'], 'status': status}, SECONDS,
                       context['stations'][7], CLOCKS[7], context['extended'], calibration_status=CALIBRATION)


def test_holdout_calibration_rejection_prevents_forecast(context):
    with pytest.raises(ValueError, match='held-out calibration'):
        forecast_joint(context['nominal'], SECONDS, context['stations'][7], CLOCKS[7],
                       context['extended'], calibration_status='REFERENCE_CODE_REJECTED')


@pytest.mark.parametrize('kind', ['step', 'jerk'])
def test_physical_mismatch_still_rejected(context, kind):
    error = np.zeros(context['size'])
    if kind == 'step':
        error[:7*len(TIMES)].reshape(len(TIMES), 7)[len(TIMES)//2:, 0] = 300
    result = solve_data(context, error, context['joint'], jerk=JERK if kind == 'jerk' else None)
    assert result['status'] == 'MODEL_REJECTED'


def test_declared_covariance_scale_is_not_reestimated_from_residuals(context):
    error = context['modes'][:context['size'], 0]*.2
    nominal = solve_data(context, error, context['joint'])
    enlarged = solve_data(context, error, 4*context['joint'])
    np.testing.assert_allclose(nominal['state'], enlarged['state'], rtol=0, atol=.002)
    assert enlarged['weighted_residual_cost'] == pytest.approx(nominal['weighted_residual_cost']/4, rel=1e-4)
    np.testing.assert_allclose(np.diag(enlarged['covariance_joint']),
                               4*np.diag(nominal['covariance_joint']), rtol=2e-5)
