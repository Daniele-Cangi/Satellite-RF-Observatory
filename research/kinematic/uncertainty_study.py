"""Fixed synthetic inverse-error study; no acquisitions, calibration tuning or oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from .clock_drift import fit_reference_clock
from .inverse_uncertainty import budget, linearize, output_values, vector
from .receiver_time import fit, noise_covariance, predict
from .s2_validation import CLOCKS, JERK, STATE, TIMES, inertial_observations, reference_calibrations
from .synthetic import native, receiver_positions

SECONDS = 60.
JERK_AXIS_BOUND = 2e-7  # Declared synthetic box, not an empirical satellite bound.


def setup():
    stations = receiver_positions()
    codes, rates = inertial_observations(TIMES, stations[:7], CLOCKS[:7])
    means, clock_cov, calibrations = reference_calibrations(np.random.default_rng(20260910), noisy=False)
    heldout = fit_reference_clock([
        {'satellite': f'G{prn:02}', 'tag_s': float(t), 'clock_m': float(CLOCKS[7, 0]+CLOCKS[7, 1]*t)}
        for t in TIMES for prn in range(1, 5)], 9*np.eye(4*len(TIMES)), target='G08')
    statuses = [row['status'] for row in calibrations]+[heldout['status']]
    if any(status != 'CONDITIONAL_CLOCK_MODEL_ACCEPTED' for status in statuses):
        raise ValueError('synthetic reference calibration rejected; stop before fit')
    cov = noise_covariance(TIMES, 7)
    result = fit(TIMES, stations[:7], codes, rates, cov, means, clock_cov)
    response = linearize(result, TIMES, stations[:7], cov, clock_cov, SECONDS,
                         stations[7], heldout['coefficients'], calibration_statuses=statuses)
    return dict(stations=stations, codes=codes, rates=rates, means=means, clock_cov=clock_cov,
                observation_cov=cov, result=result, response=response, heldout=heldout, statuses=statuses)


def covariance_cases(context):
    response = context['response']
    b, n = response['blocks'], response['input_size']
    base = np.zeros((n, n))
    base[b['observations'], b['observations']] = context['observation_cov']
    base[b['clock_means'], b['clock_means']] = context['clock_cov']
    expanded = base.copy()
    expanded[b['stations'], b['stations']] = .25*np.eye(21)
    expanded[b['heldout_station'], b['heldout_station']] = .25*np.eye(3)
    expanded[b['heldout_clock'], b['heldout_clock']] = context['heldout']['covariance']
    expanded[b['heldout_noise'], b['heldout_noise']] = [[400., .2], [.2, .0025]]
    common = np.zeros((n, 2))
    common[b['clock_means']] = np.tile(np.diag([5., .02]), (7, 1))
    common[b['heldout_clock']] = np.diag([5., .02])
    shared = expanded+common@common.T
    independent = expanded+np.diag(np.diag(common@common.T))
    return {'s2a_known_holdout': base, 'uncertain_stations_and_holdout': expanded,
            'shared_reference_clock_errors': shared, 'same_variances_without_correlations': independent}


def systematic_modes(context):
    """Fixed probes: supplied coordinate/clock bias, time convention, constant jerk.

    Generator differences are synthetic development diagnostics; they are not
    admissible orbit-derived corrections or error bounds for a real target.
    """
    response = context['response']
    b, n = response['blocks'], response['input_size']
    modes, direct = np.zeros((n, 6)), np.zeros((8, 6))
    names = ['station_0_x_2m', 'shared_reference_drift_0.02m_s', 'fit_time_basis_1ms',
             'constant_jerk_x', 'constant_jerk_y', 'constant_jerk_z']
    modes[b['stations'].start, 0] = 2.
    modes[b['clock_means'], 1] = np.tile([0., .02], 7)
    modes[b['heldout_clock'], 1] = [0., .02]
    plus = vector(predict(STATE, TIMES+.001, context['stations'][:7], CLOCKS[:7]))
    minus = vector(predict(STATE, TIMES-.001, context['stations'][:7], CLOCKS[:7]))
    modes[b['observations'], 2] = (plus-minus)/2
    for axis in range(3):
        jerk = np.eye(3)[axis]*JERK_AXIS_BOUND
        plus = np.concatenate([v.ravel() for v in inertial_observations(
            TIMES, context['stations'][:7], CLOCKS[:7], jerk=jerk)])
        minus = np.concatenate([v.ravel() for v in inertial_observations(
            TIMES, context['stations'][:7], CLOCKS[:7], jerk=-jerk)])
        modes[b['observations'], axis+3] = (plus-minus)/2
        hp = np.concatenate([v.ravel() for v in inertial_observations(
            [SECONDS], context['stations'][7:], CLOCKS[7:], jerk=jerk)])
        hm = np.concatenate([v.ravel() for v in inertial_observations(
            [SECONDS], context['stations'][7:], CLOCKS[7:], jerk=-jerk)])
        direct[:, axis+3] = -np.r_[jerk*SECONDS**3/6, jerk*SECONDS**2/2, (hp-hm)/2]
    return names, modes, direct


def refit_probe(context, mode, direct):
    """Central complete nonlinear refits at +/- one fixed mode, no truth seeds."""
    b = context['response']['blocks']
    outputs, statuses = [], []
    for sign in (1., -1.):
        obs = np.r_[context['codes'].ravel(), context['rates'].ravel()]+sign*mode[b['observations']]
        codes, rates = obs.reshape(2, len(TIMES), 7)
        stations = context['stations'][:7]+sign*mode[b['stations']].reshape(7, 3)
        means = context['means']+sign*mode[b['clock_means']].reshape(7, 2)
        result = fit(TIMES, stations, codes, rates, context['observation_cov'], means, context['clock_cov'])
        statuses.append(result['status'])
        outputs.append(output_values(result['state'], SECONDS,
            context['stations'][7]+sign*mode[b['heldout_station']],
            np.asarray(context['heldout']['coefficients'])+sign*mode[b['heldout_clock']])
            -sign*np.r_[np.zeros(6), mode[b['heldout_noise']]]+sign*direct)
    actual = (outputs[0]-outputs[1])/2
    expected = context['response']['mapping']@mode+direct
    return {'fit_statuses': statuses, 'nonlinear_central_response': actual,
            'linear_response': expected, 'difference': actual-expected}


def actual_jerk_case(context, jerk):
    """Fit actual independent cubic observations, not their local differences."""
    codes, rates = inertial_observations(TIMES, context['stations'][:7], CLOCKS[:7], jerk=jerk)
    result = fit(TIMES, context['stations'][:7], codes, rates, context['observation_cov'],
                 context['means'], context['clock_cov'])
    row = {'jerk_m_s3': jerk, 'status': result['status'], 'nominal_residual_p': result['nominal_residual_p']}
    if result['status'] != 'CONDITIONAL_MODEL_ACCEPTED':
        return row
    prediction = output_values(result['state'], SECONDS, context['stations'][7], CLOCKS[7])
    row['prediction_sha256_before_evaluation'] = hashlib.sha256(json.dumps(native(prediction),
        sort_keys=True, allow_nan=False).encode()).hexdigest()
    code, rate = inertial_observations([SECONDS], context['stations'][7:], CLOCKS[7:], jerk=jerk)
    truth = np.r_[STATE[:3]+SECONDS*STATE[3:6]+.5*SECONDS**2*STATE[6:9]+SECONDS**3/6*jerk,
                  STATE[3:6]+SECONDS*STATE[6:9]+SECONDS**2/2*jerk, code.ravel(), rate.ravel()]
    row['prediction'] = prediction
    row['output_error'] = prediction-truth
    row['direct_future_position_remainder_m'] = float(np.linalg.norm(SECONDS**3/6*jerk))
    return row


def run():
    context = setup()
    covariance = covariance_cases(context)
    names, modes, direct = systematic_modes(context)
    budgets = {name: budget(context['response'], cov, systematic_inputs=modes,
                           direct_output_errors=direct) for name, cov in covariance.items()}
    frozen = {'seconds': SECONDS, 'prediction': context['response']['nominal_output'],
              'budgets': budgets, 'mode_names': names, 'systematic_inputs': modes,
              'direct_output_errors': direct}
    seal = hashlib.sha256(json.dumps(native(frozen), sort_keys=True, allow_nan=False).encode()).hexdigest()
    # Only now run the nonlinear stress comparisons. Synthetic truth was used
    # above to design jerk probes; this seal is NOT a blinded real-data freeze.
    probes = {name: refit_probe(context, modes[:, i], direct[:, i]) for i, name in enumerate(names)}
    jerk_cases = {'declared_small_constant_jerk': actual_jerk_case(context, np.full(3, JERK_AXIS_BOUND)),
                  's2a_large_jerk': actual_jerk_case(context, JERK)}
    expected_jerk_error = (context['response']['mapping']@modes+direct)[:, 3:].sum(axis=1)
    small = jerk_cases['declared_small_constant_jerk']
    if 'output_error' in small:
        small['difference_from_affine_prediction'] = small['output_error']-expected_jerk_error
    old = budgets['s2a_known_holdout']['covariance_output']
    expanded = budgets['uncertain_stations_and_holdout']['covariance_output']
    criteria = {
        'nominal_fit_accepted': context['result']['status'] == 'CONDITIONAL_MODEL_ACCEPTED',
        'all_six_fixed_probes_retained': len(probes) == 6,
        'all_probe_fits_accepted': all(s == 'CONDITIONAL_MODEL_ACCEPTED' for p in probes.values() for s in p['fit_statuses']),
        'linear_refit_position_agrees_within_5cm': all(np.linalg.norm(p['difference'][:3]) < .05 for p in probes.values()),
        'linear_refit_velocity_agrees_within_1mm_s': all(np.linalg.norm(p['difference'][3:6]) < .001 for p in probes.values()),
        'linear_refit_holdout_code_agrees_within_1cm': all(abs(p['difference'][6]) < .01 for p in probes.values()),
        'linear_refit_holdout_rate_agrees_within_10um_s': all(abs(p['difference'][7]) < 1e-5 for p in probes.values()),
        'independent_extra_errors_do_not_reduce_variance': bool(np.all(np.diag(expanded) >= np.diag(old))),
        'small_actual_jerk_linear_position_within_5cm': 'output_error' in small and
            np.linalg.norm(small['difference_from_affine_prediction'][:3]) < .05,
        'large_jerk_stops_before_prediction': jerk_cases['s2a_large_jerk']['status'] == 'MODEL_REJECTED'
            and 'prediction' not in jerk_cases['s2a_large_jerk'],
        'no_real_rf_qualification': all(b['real_rf_qualified'] is False for b in budgets.values())}
    root = Path(__file__).resolve().parents[2]
    files = [root/'research/kinematic'/name for name in (
        'inverse_uncertainty.py', 'uncertainty_study.py', 'receiver_time.py', 's2_validation.py',
        'clock_drift.py', 'synthetic.py', 'model.py')]
    files += [root/'positioning'/name for name in ('solver.py', 'calibration.py', 'errors.py')]
    return native({'schema': 'inverse-uncertainty-synthetic-v1', 'real_rf_qualified': False,
        'design': {'fit_tags_s': TIMES, 'stations_m': context['stations'], 'synthetic_state': STATE,
                   'receiver_clocks': CLOCKS, 'jerk_axis_box_m_s3': JERK_AXIS_BOUND,
                   'coordinate_sigma_m': .5, 'shared_reference_offset_sigma_m': 5.,
                   'shared_reference_drift_sigma_m_s': .02,
                   'covariance_cases_sha256': {name: hashlib.sha256(json.dumps(native(cov),
                       separators=(',', ':'), allow_nan=False).encode()).hexdigest() for name, cov in covariance.items()},
                   'covariance_recipe': 'covariance_cases(setup()); source bytes recorded below; no sampling or fitted rescaling',
                   'calibration_statuses': context['statuses']},
        'scope': 'Synthetic local response diagnostics, fixed S2a weights. No calibrated test under added errors, full nonlinear envelope, general jerk bound or population coverage.',
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'nominal_fit': context['result'], 'prospective_local_budget': frozen,
        'budget_sha256_before_nonlinear_probes': seal, 'nonlinear_probes': probes,
        'actual_jerk_cases': jerk_cases,
        'criteria': criteria, 'criteria_pass': all(criteria.values())})


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
    print(json.dumps(report['criteria'], indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
