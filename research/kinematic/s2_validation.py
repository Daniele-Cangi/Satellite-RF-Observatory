"""Fixed S2a development study. Independent inertial generator; no RF access."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.optimize import brentq
from scipy.stats import chi2

from .clock_drift import fit_reference_clock
from .receiver_time import fit, noise_covariance, predict, quadratic_remainder
from .synthetic import native, receiver_positions

TIMES = np.arange(-300., 1., 30.)
STATE = np.array([26e6, 2e6, 4e6, -250., 2300., 500., -.52, -.04, -.08, -75000., -12.])
CLOCKS = np.column_stack([np.array([-20, 12, -8, 18, 3, -11, 7, 4])*1000.,
                          [-1.2, .4, -.8, 1.1, .3, -.6, .7, .2]])
JERK = np.array([-5e-5, 1e-4, 3e-5])


def inertial_observations(tags_s, stations, clocks, *, state=STATE, jerk=None):
    """Independent scalar light-cone solve in a uniformly rotating ECI frame.

    Does not call the predictor, its rotation or its implicit rate derivative.
    A five-point derivative of generated codes supplies instantaneous rates.
    These are invented positions and clocks, never a satellite ephemeris.
    """
    jerk = np.zeros(3) if jerk is None else np.asarray(jerk)

    def rotation(vector, seconds):
        theta = 7.2921151467e-5*seconds
        co, si = math.cos(theta), math.sin(theta)
        x, y, z = vector
        return np.array([co*x-si*y, si*x+co*y, z])

    def code_at(tag, station, clock):
        receiver_clock = clock[0]+clock[1]*tag
        receive = tag-receiver_clock/299792458.0
        receiver_eci = rotation(station, receive)

        def light_cone(tau):
            transmit = receive-tau
            position = state[:3]+transmit*state[3:6]+transmit**2/2*state[6:9]+transmit**3/6*jerk
            distance = np.linalg.norm(rotation(position, transmit)-receiver_eci)
            return 299792458.0*tau-distance

        tau = brentq(light_cone, 0., 2., xtol=5e-16, rtol=1e-14)
        return 299792458.0*tau+receiver_clock-state[9]-state[10]*(receive-tau)

    codes, rates = [], []
    h = .1
    for tag in tags_s:
        code_row, rate_row = [], []
        for station, clock in zip(stations, clocks, strict=True):
            samples = [code_at(tag+k*h, station, clock) for k in (-2, -1, 0, 1, 2)]
            code_row.append(samples[2])
            rate_row.append((samples[0]-8*samples[1]+8*samples[3]-samples[4])/(12*h))
        codes.append(code_row)
        rates.append(rate_row)
    return np.array(codes), np.array(rates)


def reference_calibrations(rng, *, noisy):
    """Invented reference clock residuals, not an ephemeris/RINEX calibrator."""
    covariance = 9*np.eye(len(TIMES)*4)
    means, covariances, results = [], [], []
    for clock in CLOCKS[:7]:
        rows = [{'satellite': f'G{prn:02}', 'tag_s': float(t),
                 'clock_m': float(clock[0]+clock[1]*t+(rng.normal(0, 3) if noisy else 0))}
                for t in TIMES for prn in range(1, 5)]
        result = fit_reference_clock(rows, covariance, target='G08')
        means.append(result['coefficients'])
        covariances.append(result['covariance'])
        results.append(result)
    joint = scipy.linalg.block_diag(*covariances)
    return np.array(means), joint, results


def forecast(result, seconds, station, clock):
    """Conditional position/velocity forecast; no holdout data consumed."""
    position_map = np.zeros((3, 11))
    velocity_map = np.zeros((3, 11))
    position_map[:, :3] = np.eye(3)
    position_map[:, 3:6] = seconds*np.eye(3)
    position_map[:, 6:9] = .5*seconds**2*np.eye(3)
    velocity_map[:, 3:6] = np.eye(3)
    velocity_map[:, 6:9] = seconds*np.eye(3)
    covariance = result['covariance_joint'][:11, :11]
    measurement = predict(result['state'], [seconds], [station], [clock])
    def radius(mapping):
        return float(np.sqrt(chi2.ppf(.95, 3)*np.linalg.eigvalsh(mapping@covariance@mapping.T)[-1]))
    return {'seconds': seconds, 'position_m': position_map@result['state'],
            'velocity_m_s': velocity_map@result['state'],
            'local_position_radius95_m': radius(position_map),
            'local_velocity_radius95_m_s': radius(velocity_map),
            'heldout_code_m': float(measurement['code_m'][0, 0]),
            'heldout_rate_m_s': float(measurement['rate_m_s'][0, 0])}


def evaluate(case):
    rng = np.random.default_rng(20260910)
    stations = receiver_positions()
    noisy = case == 'correlated_noise'
    jerk = JERK if case == 'unmodelled_jerk' else np.zeros(3)
    codes, rates = inertial_observations(TIMES, stations[:7], CLOCKS[:7], jerk=jerk)
    cov = noise_covariance(TIMES, 7)
    clock_mean, clock_cov, calibration = reference_calibrations(rng, noisy=noisy)
    if noisy:
        noise = np.linalg.cholesky(cov)@rng.normal(size=2*codes.size)
        codes += noise[:codes.size].reshape(codes.shape)
        rates += noise[codes.size:].reshape(rates.shape)
    if case == 'unreported_clock_step':
        # A mismodelled 300 m step in one station; no synthetic clock repair.
        codes[len(TIMES)//2:, 0] += 300
    row = {'case': case, 'seed': 20260910, 'reference_calibrations': calibration}
    try:
        result = fit(TIMES, stations[:7], codes, rates, cov, clock_mean, clock_cov)
        row['fit'] = result
        predictions = [forecast(result, t, stations[7], CLOCKS[7]) for t in (0., 30., 60.)]
        # Development-only seal before asking the generator for excluded data.
        encoded = json.dumps(native(predictions), sort_keys=True, allow_nan=False).encode()
        row['predictions_sha256_before_evaluation'] = hashlib.sha256(encoded).hexdigest()
        row['predictions'] = predictions
        true_codes, true_rates = inertial_observations([0., 30., 60.], stations[7:], CLOCKS[7:], jerk=jerk)
        evaluations = []
        for i, prediction in enumerate(predictions):
            t = prediction['seconds']
            position = STATE[:3]+t*STATE[3:6]+t*t/2*STATE[6:9]+t**3/6*jerk
            velocity = STATE[3:6]+t*STATE[6:9]+t*t/2*jerk
            evaluations.append({'seconds': t,
                'position_error_m': float(np.linalg.norm(prediction['position_m']-position)),
                'velocity_error_m_s': float(np.linalg.norm(prediction['velocity_m_s']-velocity)),
                'heldout_code_error_m': prediction['heldout_code_m']-float(true_codes[i, 0]),
                'heldout_rate_error_m_s': prediction['heldout_rate_m_s']-float(true_rates[i, 0])})
        row['evaluation'] = evaluations
    except (ValueError, RuntimeError) as error:
        row['failure'] = str(error)
    return row


def run():
    stations = receiver_positions()[:7]
    independent_codes, independent_rates = inertial_observations(TIMES, stations, CLOCKS[:7])
    modeled = predict(STATE, TIMES, stations, CLOCKS[:7])
    rotation_off = predict(STATE, TIMES, stations, CLOCKS[:7], omega=0.)
    diagnostics = {
        'independent_max_code_difference_m': float(np.max(abs(modeled['code_m']-independent_codes))),
        'independent_max_rate_difference_m_s': float(np.max(abs(modeled['rate_m_s']-independent_rates))),
        'rotation_omission_max_code_difference_m': float(np.max(abs(rotation_off['code_m']-independent_codes))),
        'light_time_interval_s': [float(modeled['light_time_s'].min()), float(modeled['light_time_s'].max())]}
    cases = [evaluate(case) for case in ('noiseless', 'correlated_noise', 'unmodelled_jerk', 'unreported_clock_step')]
    remainder = quadratic_remainder(float(np.linalg.norm(JERK)), 300.1,
                                     position_budget_m=20., velocity_budget_m_s=.05)
    criteria = {
        'independent_code_within_1mm': diagnostics['independent_max_code_difference_m'] < .001,
        'independent_rate_within_10um_s': diagnostics['independent_max_rate_difference_m_s'] < 1e-5,
        'all_four_cases_retained': len(cases) == 4 and all('fit' in row or 'failure' in row for row in cases),
        'noiseless_prediction_recovered': 'evaluation' in cases[0] and all(
            e['position_error_m'] < .1 and e['velocity_error_m_s'] < .001 for e in cases[0]['evaluation']),
        'noiseless_model_accepted': cases[0].get('fit', {}).get('status') == 'CONDITIONAL_MODEL_ACCEPTED',
        'jerk_model_rejected': cases[2].get('fit', {}).get('status') == 'MODEL_REJECTED',
        'clock_step_rejected': cases[3].get('fit', {}).get('status') == 'MODEL_REJECTED',
        'declared_jerk_exceeds_budget': remainder['status'] == 'TRUNCATION_BUDGET_EXCEEDED'}
    root = Path(__file__).resolve().parents[2]
    files = [root/'research/kinematic'/name for name in
             ('receiver_time.py', 'clock_drift.py', 'doppler.py', 's2_validation.py', 'synthetic.py', 'model.py')]
    files += [root/'positioning'/name for name in ('solver.py', 'calibration.py', 'errors.py')]
    return native({'schema': 'receiver-time-synthetic-study-v1',
        'scope': 'S2a vacuum synthetic validation only. Real RF integration and total error budget remain pending; no S3 admission.',
        'design': {'fit_tags_s': TIMES, 'state': STATE, 'receiver_clocks': CLOCKS,
                   'station_positions_m': receiver_positions(), 'jerk_stress_m_s3': JERK,
                   'noise': {'code_sigma_m': 20., 'rate_sigma_m_s': .05, 'temporal_s': 60.,
                             'code_rate_correlation': .2, 'shared_fraction': .15},
                   'reference_residual_sigma_m': 3., 'holdout_clock': 'known synthetic coefficients',
                   'time_convention': 'local GPST base aligned with ECEF axes; rate per receiver-tag second'},
        'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'diagnostics': diagnostics, 'taylor_remainder_not_estimator_bound': remainder,
        'criteria': criteria, 'criteria_pass': all(criteria.values()), 'cases': cases})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to overwrite an existing report')
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({'criteria': report['criteria'], 'diagnostics': report['diagnostics']}, indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
