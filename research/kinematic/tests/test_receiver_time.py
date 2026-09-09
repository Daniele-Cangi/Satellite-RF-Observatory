import hashlib
import json

import numpy as np
import pytest

from positioning.errors import ScientificRejection
from research.kinematic.clock_drift import admit_reference_rows, fit_reference_clock, local_gpst_seconds
from research.kinematic.doppler import ALPHA, BETA, F1_HZ, F2_HZ, admit_fields, convert_gps_if
from research.kinematic.receiver_time import C, fit, noise_covariance, predict, quadratic_remainder
from research.kinematic.s2_validation import (CLOCKS, STATE, TIMES, inertial_observations,
                                              reference_calibrations, run)
from research.kinematic.synthetic import receiver_positions


@pytest.fixture(scope='module')
def study():
    return run()


def test_independent_inertial_generator_and_inverse_recovery(study):
    assert study['criteria_pass'], study['criteria']
    assert study['diagnostics']['rotation_omission_max_code_difference_m'] > 10
    for row in study['cases']:
        serialized = json.dumps(row['predictions'], sort_keys=True, allow_nan=False).encode()
        assert hashlib.sha256(serialized).hexdigest() == row['predictions_sha256_before_evaluation']
        assert row['fit']['rank'] == 25
        assert not row['fit']['branch_failures']
    noiseless = study['cases'][0]['fit']
    np.testing.assert_allclose(noiseless['state'][9:], STATE[9:], atol=.001)
    np.testing.assert_allclose(noiseless['receiver_clocks'], CLOCKS[:7], atol=1e-5)


def test_rate_differentiates_receiver_tag_and_not_coordinate_seconds():
    # Artificially large oscillator drift magnifies an otherwise small factor.
    clocks = CLOCKS[:7].copy()
    clocks[:, 1] *= 1000
    t = np.array([-180., -30., 0.])
    predicted = predict(STATE, t, receiver_positions()[:7], clocks)
    independent = inertial_observations(t, receiver_positions()[:7], clocks)
    np.testing.assert_allclose(predicted['rate_m_s'], independent[1], atol=2e-6, rtol=0)
    plus = predict(STATE, t+.02, receiver_positions()[:7], clocks)['code_m']
    minus = predict(STATE, t-.02, receiver_positions()[:7], clocks)['code_m']
    np.testing.assert_allclose((plus-minus)/.04, predicted['rate_m_s'], atol=2e-6, rtol=0)
    assert np.all(predicted['transmit_s'] < predicted['receive_s'])


def test_stationary_geometry_has_analytically_known_clock_rate():
    state = STATE.copy()
    state[3:9] = 0
    clocks = CLOCKS[:7].copy()
    prediction = predict(state, [-200., 0.], receiver_positions()[:7], clocks, omega=0.)
    expected = clocks[:, 1]-state[10]*(1-clocks[:, 1]/C)
    np.testing.assert_allclose(prediction['rate_m_s'], np.broadcast_to(expected, (2, 7)), atol=1e-12)


def test_local_gpst_offsets_preserve_day_week_crossing_and_fraction():
    before = local_gpst_seconds('2026-09-12', 86399.999999, base_day='2026-09-13', base_second=0)
    after = local_gpst_seconds('2026-09-13', .000001, base_day='2026-09-13', base_second=0)
    assert abs(before+1e-6) < 1e-11
    assert after == 1e-6
    with pytest.raises(ValueError, match='nearby'):
        local_gpst_seconds('2026-09-20', 0., base_day='2026-09-13', base_second=0)
    with pytest.raises(ValueError, match='GPST'):
        local_gpst_seconds('2026-09-13', 86400., base_day='2026-09-13', base_second=0)


def clock_rows():
    return [{'satellite': f'G{prn:02}', 'tag_s': t, 'clock_m': 14000.+.73*t}
            for t in (-90., -60., -30., 0.) for prn in range(1, 5)]


def test_target_payload_removed_before_numeric_clock_calibration():
    class Poison:
        def __float__(self):
            raise AssertionError('target numerical payload was accessed')
    poison = {'satellite': 'G08', 'tag_s': Poison(), 'clock_m': Poison()}
    rows = clock_rows()
    admitted = admit_reference_rows([poison]+rows, target='G08')
    assert admitted == rows
    covariance = np.eye(len(rows))
    calibrated = fit_reference_clock(admitted, covariance, target='G08')
    np.testing.assert_allclose(calibrated['coefficients'], [14000., .73], atol=1e-10)
    with pytest.raises(ValueError, match='target record forbidden'):
        fit_reference_clock([poison]+rows, np.eye(len(rows)+1), target='G08')


def test_reference_clock_step_and_shared_covariance_are_not_hidden():
    rows = clock_rows()
    independent = fit_reference_clock(rows, np.eye(len(rows)), target='G08')
    shared = fit_reference_clock(rows, np.eye(len(rows))+25., target='G08')
    assert shared['covariance'][0, 0] >= 25
    assert shared['covariance'][0, 0] > independent['covariance'][0, 0]*10
    for row in rows[-8:]:
        row['clock_m'] += 100
    stepped = fit_reference_clock(rows, np.eye(len(rows)), target='G08')
    assert stepped['status'] == 'CLOCK_MODEL_REJECTED'
    with pytest.raises(ValueError, match='four references'):
        fit_reference_clock(rows[::4], np.eye(4), target='G08')


def field(value, lli=' '):
    return f'{value:14.3f}'+lli+' '


def fields():
    return {'C1C': field(2e7), 'C2W': field(2e7), 'D1C': field(1234.),
            'D2W': field(987.), 'L1C': field(1e8), 'L2W': field(9e7)}


@pytest.mark.parametrize('doppler', [1000., -1000., 0.])
def test_doppler_sign_wavelength_and_first_order_ionosphere(doppler):
    # A common range rate has different Doppler values on L1 and L2.
    rate = -C/F1_HZ*doppler
    d2 = -rate*F2_HZ/C
    values = [2e7+12., 2e7+12.*F1_HZ**2/F2_HZ**2, doppler, d2]
    converted, covariance = convert_gps_if(values, np.eye(4))
    np.testing.assert_allclose(converted, [2e7, rate], atol=1e-8)
    assert np.linalg.eigvalsh(covariance).min() > 0
    # An ionospheric phase-rate term has opposite sign to code delay but the
    # same 1/f^2 dependence; the IF weights cancel it independently of sign.
    assert abs(ALPHA*(-.1)+BETA*(-.1*F1_HZ**2/F2_HZ**2)) < 1e-12


def test_code_doppler_covariance_keeps_cross_terms():
    covariance = np.eye(4)
    covariance[0, 2] = covariance[2, 0] = .6
    _, transformed = convert_gps_if([2e7, 2e7, 1000., 800.], covariance)
    assert transformed[0, 1] == pytest.approx(-.6*ALPHA**2*C/F1_HZ)


def test_generated_link_survives_rinex_field_rounding_and_if_conversion():
    codes, rates = inertial_observations([0.], receiver_positions()[:7], CLOCKS[:7])
    for code, rate in zip(codes[0], rates[0], strict=True):
        iono_m, iono_rate = 12., .07
        ratio = F1_HZ**2/F2_HZ**2
        row = {'C1C': field(code+iono_m), 'C2W': field(code+iono_m*ratio),
               'D1C': field(-(rate-iono_rate)*F1_HZ/C),
               'D2W': field(-(rate-iono_rate*ratio)*F2_HZ/C),
               'L1C': field(1e8), 'L2W': field(9e7)}
        admitted = admit_fields(row, epoch_flag=0, gap_s=30, expected_step_s=30)
        converted, _ = convert_gps_if(admitted['values'], np.eye(4))
        # Worst-case propagation of F14.3 quantization, not empirical margins.
        assert abs(converted[0]-code) <= .0005*(abs(ALPHA)+abs(BETA))+1e-8
        assert abs(converted[1]-rate) <= .0005*C*(abs(ALPHA)/F1_HZ+abs(BETA)/F2_HZ)+1e-8


@pytest.mark.parametrize('change,reason', [
    ({'D1C': ' '*16}, 'MISSING_OR_INVALID_D1C'),
    ({'D2W': field(0.)}, 'MISSING_OR_INVALID_D2W'),
    ({'L1C': field(1e8, '1')}, 'PHASE_TRACKING_FLAG_L1C'),
    ({'L2W': field(9e7, '2')}, 'PHASE_TRACKING_FLAG_L2W'),
    ({'L1C': field(1e8, '4')}, 'PHASE_TRACKING_FLAG_L1C'),
])
def test_missing_and_tracking_flags_have_explicit_outcomes(change, reason):
    row = fields() | change
    admitted = admit_fields(row, epoch_flag=0, gap_s=30, expected_step_s=30)
    assert admitted['status'] == 'PAIR_NOT_ADMITTED'
    assert reason in admitted['reasons']
    assert 'values' not in admitted


def test_epoch_gap_and_phase_only_lli_policy():
    row = fields()
    row['D1C'] = field(1234., '1')  # LLI is not defined on Doppler.
    assert admit_fields(row, epoch_flag=0, gap_s=30, expected_step_s=30)['status'] == 'PAIR_FIELDS_ADMITTED'
    rejected = admit_fields(row, epoch_flag=1, gap_s=60, expected_step_s=30)
    assert set(rejected['reasons']) == {'NON_NORMAL_EPOCH', 'GAP_OR_UNKNOWN_PREDECESSOR'}


def test_clock_calibration_uncertainty_reaches_satellite_covariance():
    stations = receiver_positions()[:7]
    code, rate = inertial_observations(TIMES, stations, CLOCKS[:7])
    mean, clock_covariance, _ = reference_calibrations(np.random.default_rng(0), noisy=False)
    noise = noise_covariance(TIMES, 7)
    precise = fit(TIMES, stations, code, rate, noise, mean, clock_covariance)
    uncertain = fit(TIMES, stations, code, rate, noise, mean, clock_covariance*10000)
    assert np.trace(uncertain['covariance_joint'][:3, :3]) > np.trace(precise['covariance_joint'][:3, :3])*1.1
    assert np.linalg.norm(precise['covariance_joint'][:11, 11:]) > 0


def test_invalid_covariance_missing_data_and_geometry_fail_closed():
    stations = receiver_positions()[:7]
    observation = predict(STATE, TIMES, stations, CLOCKS[:7])
    cov = noise_covariance(TIMES, 7)
    arguments = [TIMES, stations, observation['code_m'], observation['rate_m_s'], cov, CLOCKS[:7], np.eye(14)]
    asymmetric = cov.copy()
    asymmetric[0, 1] += 1
    with pytest.raises(ValueError, match='symmetric covariance'):
        fit(*arguments[:4], asymmetric, *arguments[5:])
    with pytest.raises(ValueError, match='positive definite'):
        fit(*arguments[:4], cov*0, *arguments[5:])
    rates = observation['rate_m_s'].copy()
    rates[0, 0] = np.nan
    with pytest.raises(ValueError, match='finite common'):
        fit(*arguments[:3], rates, *arguments[4:])
    repeated = np.repeat(stations[:1], 7, axis=0)
    same = predict(STATE, TIMES, repeated, np.zeros((7, 2)))
    with pytest.raises((ValueError, ScientificRejection), match='rank deficient'):
        fit(TIMES, repeated, same['code_m'], same['rate_m_s'], cov, np.zeros((7, 2)), np.eye(14))


def test_taylor_remainder_is_prior_model_budget_not_fitted_covariance():
    bound = quadratic_remainder(.00012, -300.1, position_budget_m=20, velocity_budget_m_s=.05)
    assert bound['status'] == 'TRUNCATION_BUDGET_EXCEEDED'
    assert bound['velocity_remainder_m_s'] > 5
    assert bound['position_remainder_m'] > 500
    with pytest.raises(ValueError):
        quadratic_remainder(-1, 30, position_budget_m=20, velocity_budget_m_s=.05)
