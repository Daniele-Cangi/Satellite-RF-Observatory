"""Fixed paired synthetic experiment for the joint fit. No real data access."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag, solve_triangular

from .inverse_uncertainty import output_values
from .joint_fit import covariance_hash, fit_joint, forecast_joint, whitened_geometry
from .receiver_time import noise_covariance
from .s2_validation import CLOCKS, JERK, STATE, TIMES, inertial_observations
from .synthetic import native, receiver_positions

TRIAL_COUNT = 16
SEED = 20260911
SECONDS = 60.
CALIBRATION = 'CONDITIONAL_CLOCK_MODEL_ACCEPTED'


def design():
    """Assumed compressed Gaussian calibration data; no reference quality claim.

    Fourteen receiver-specific modes couple RF, reference clocks and surveyed
    coordinates. Fixed amplitudes do not use target state or observed residuals.
    Seven extra inputs describe excluded clock, coordinates and RF noise.
    """
    n, nt = 7, len(TIMES)
    nobs, size = 2*n*nt, 2*n*nt+5*n
    clock_cov = np.kron(np.eye(n), np.diag([4., .01**2]))
    covariance = block_diag(noise_covariance(TIMES, n), clock_cov, .25*np.eye(3*n),
                            np.diag([4., .01**2]), .25*np.eye(3), [[400., .2], [.2, .0025]])
    modes = np.zeros((size+7, 2*n+1))
    for station in range(n):
        modes[station:n*nt:n, 2*station] = 30.
        modes[nobs+2*station, 2*station] = 25.
        modes[nobs+2*n+3*station, 2*station] = 2.
        modes[station:n*nt:n, 2*station+1] = TIMES*.1
        modes[n*nt+station:nobs:n, 2*station+1] = .1
        modes[nobs+2*station+1, 2*station+1] = .08
        modes[nobs+2*n+3*station+1, 2*station+1] = 1.
    # A separate common reference-clock offset links the fit and held-out clock.
    modes[nobs:nobs+2*n:2, -1] = 5.
    modes[size, -1] = 5.
    covariance += modes@modes.T
    fit_cov = covariance[:size, :size].copy()
    blocks = block_diag(fit_cov[:nobs, :nobs], fit_cov[nobs:nobs+2*n, nobs:nobs+2*n],
                        fit_cov[nobs+2*n:, nobs+2*n:])
    return {'joint': fit_cov, 'blocks': blocks, 'extended': covariance,
            'modes': modes, 'nobs': nobs, 'size': size, 'stations': receiver_positions()}


def solve_data(d, error, covariance, *, jerk=None):
    codes, rates = inertial_observations(TIMES, d['stations'][:7], CLOCKS[:7], jerk=jerk)
    codes = codes+error[:codes.size].reshape(codes.shape)
    rates = rates+error[codes.size:d['nobs']].reshape(rates.shape)
    clocks = CLOCKS[:7]+error[d['nobs']:d['nobs']+14].reshape(7, 2)
    stations = d['stations'][:7]+error[d['nobs']+14:d['size']].reshape(7, 3)
    return fit_joint(TIMES, stations, codes, rates, clocks, covariance, calibration_statuses=[CALIBRATION]*7)


def residual_moments(result, fitted_covariance, true_covariance):
    """Exact quadratic-form moments for the local linear Gaussian problem."""
    j = result['data_jacobian']
    geometry = whitened_geometry(j, fitted_covariance, result['parameter_scale'])
    residual_map = np.eye(len(j))-j@geometry['gain']
    whitened = solve_triangular(np.linalg.cholesky(fitted_covariance),
                               residual_map@np.linalg.cholesky(true_covariance), lower=True)
    a = whitened.T@whitened
    return {'expected_cost': float(np.trace(a)), 'variance_cost': float(2*np.sum(a*a)),
            'chi_square_expected_cost': result['residual_dof'],
            'chi_square_variance_cost': 2*result['residual_dof']}


def compact(result):
    keep = ('status', 'state', 'station_corrections_m', 'conditional_residual_p', 'weighted_residual_cost',
            'residual_dof', 'rank', 'scaled_condition', 'found_branches', 'branch_failures', 'real_rf_qualified')
    return {**{key: result[key] for key in keep}, 'covariance_state_local': result['covariance_joint'][:11, :11]}


def run():
    d = design()
    zero = np.zeros(d['size'])
    nominal = {name: solve_data(d, zero, d[name]) for name in ('joint', 'blocks')}
    moments = {name: residual_moments(nominal[name], d[name], d['joint']) for name in nominal}
    baseline = forecast_joint(nominal['joint'], SECONDS, d['stations'][7], CLOCKS[7], d['extended'], calibration_status=CALIBRATION)
    rng = np.random.default_rng(SEED)
    draws = rng.normal(size=(TRIAL_COUNT, len(d['extended'])))@np.linalg.cholesky(d['extended']).T
    trials = []
    for index, error in enumerate(draws):
        fits = {name: solve_data(d, error, d[name]) for name in nominal}
        row = {'index': index, 'fits': {name: compact(fit) for name, fit in fits.items()}}
        fit = fits['joint']
        if fit['status'] == 'CONDITIONAL_JOINT_MODEL_ACCEPTED':
            clock = CLOCKS[7]+error[d['size']:d['size']+2]
            station = d['stations'][7]+error[d['size']+2:d['size']+5]
            forecast = forecast_joint(fit, SECONDS, station, clock, d['extended'], calibration_status=CALIBRATION)
            forecast.pop('mapping')
            row['forecast_sha256_before_evaluation'] = hashlib.sha256(json.dumps(native(forecast), sort_keys=True, allow_nan=False).encode()).hexdigest()
            row['forecast'] = forecast
            code, rate = inertial_observations([SECONDS], d['stations'][7:], CLOCKS[7:])
            truth = output_values(STATE, SECONDS, d['stations'][7], CLOCKS[7])
            truth[6:] = [code[0, 0], rate[0, 0]]+error[-2:]
            difference = forecast['prediction']-truth
            row['evaluation'] = {'output_error': difference, 'position_error_m': float(np.linalg.norm(difference[:3])),
                'position_inside_local_radius': bool(np.linalg.norm(difference[:3]) <= forecast['local_position_radius95_m'])}
        trials.append(row)
    stress = {}
    for name in ('joint', 'blocks'):
        step = zero.copy()
        step[:7*len(TIMES)].reshape(len(TIMES), 7)[len(TIMES)//2:, 0] = 300.
        stress[name] = {'clock_step': compact(solve_data(d, step, d[name])),
                        'large_jerk': compact(solve_data(d, zero, d[name], jerk=JERK))}
    criteria = {
        'nominal_both_accepted': all(r['status'] == 'CONDITIONAL_JOINT_MODEL_ACCEPTED' for r in nominal.values()),
        'noiseless_position_within_1cm': all(np.linalg.norm(r['state'][:3]-STATE[:3]) < .01 for r in nominal.values()),
        'joint_linear_cost_mean_matches_dof': abs(moments['joint']['expected_cost']-(2*7*len(TIMES)-11)) < 1e-6,
        'joint_linear_cost_variance_matches_chi_square': abs(moments['joint']['variance_cost']-2*(2*7*len(TIMES)-11)) < 1e-5,
        'all_fixed_paired_trials_retained': len(trials) == TRIAL_COUNT and all(len(row['fits']) == 2 for row in trials),
        'rejected_trials_have_no_forecast': all('forecast' not in row for row in trials if row['fits']['joint']['status'] != 'CONDITIONAL_JOINT_MODEL_ACCEPTED'),
        'joint_clock_step_rejected': stress['joint']['clock_step']['status'] == 'MODEL_REJECTED',
        'joint_large_jerk_rejected': stress['joint']['large_jerk']['status'] == 'MODEL_REJECTED',
        'no_rf_qualification': all(not row['fits']['joint']['real_rf_qualified'] for row in trials)}
    root = Path(__file__).resolve().parents[2]
    names = ['research/kinematic/'+name for name in ('joint_fit.py', 'joint_study.py', 'receiver_time.py',
        'inverse_uncertainty.py', 's2_validation.py', 'synthetic.py', 'model.py', 'clock_drift.py')]
    names += ['positioning/'+name for name in ('solver.py', 'calibration.py', 'errors.py')]
    baseline.pop('mapping')
    return native({'schema': 'joint-correlated-fit-synthetic-v1', 'real_rf_qualified': False,
        'scope': 'Synthetic fixed covariance/geometry study; compressed calibration data assumed admitted. Local linear chi-square moments are exact; nonlinear calibration/coverage and real RF qualification remain unproven.',
        'design': {'seed': SEED, 'trial_count': TRIAL_COUNT, 'fit_tags_s': TIMES, 'forecast_seconds': SECONDS,
                   'stations_m': d['stations'], 'state': STATE, 'clocks': CLOCKS,
                   'covariance_recipe': 'design() in the hashed joint_study.py; fixed before random draws',
                   'covariance_sha256': {k: covariance_hash(d[k]) for k in ('joint', 'blocks', 'extended')},
                   'shared_modes': d['modes'], 'large_jerk_m_s3': JERK, 'clock_step_m': 300.,
                   'residual_threshold_p': .01},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names},
        'nominal': {name: compact(r) for name, r in nominal.items()}, 'nominal_forecast': baseline,
        'local_linear_residual_moments': moments, 'trials': trials, 'stress': stress,
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
