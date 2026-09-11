"""Paired synthetic endpoint code / interval phase study; no real acquisition."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag
from scipy.stats import chi2

from .interval_fit import fit_intervals, forecast_interval
from .joint_study import compact, residual_moments
from .phase_rates import interval_matrix
from .s2_validation import CLOCKS, JERK, STATE, TIMES, inertial_observations
from .synthetic import native, receiver_positions

SEED = 20260912
TRIAL_COUNT = 4
CALIBRATION = 'CONDITIONAL_CLOCK_MODEL_ACCEPTED'


def design():
    """Fixed endpoint IF paths in metres, with full raw cross covariance.

    These are invented compressed calibrations, not output from a real receiver
    qualification. Phase ambiguity is constant; propagation is vacuum.
    """
    n, count = 7, len(TIMES)*7
    difference = interval_matrix(TIMES, n)
    raw = block_diag(400*np.eye(count), .01**2*np.eye(count),
                     np.kron(np.eye(n), np.diag([4., .01**2])), .25*np.eye(3*n))
    raw[:count, count:2*count] = .02*np.eye(count)
    raw[count:2*count, :count] = .02*np.eye(count)  # code/phase rho=.1
    modes = np.zeros((len(raw), 2*n))
    for j in range(n):
        modes[j:count:n, 2*j] = 5.
        modes[2*count+2*j, 2*j] = 4.
        modes[2*count+2*n+3*j, 2*j] = .2
        modes[j:count:n, 2*j+1] = TIMES*.01
        modes[count+j:2*count:n, 2*j+1] = TIMES*.01
        modes[2*count+2*j+1, 2*j+1] = .008
    raw += modes@modes.T
    transform = block_diag(np.eye(count), difference, np.eye(5*n))
    covariance = transform@raw@transform.T
    covariance = (covariance+covariance.T)/2
    indices = np.r_[np.arange(count), np.arange(count+len(difference), len(covariance))]
    return {'stations': receiver_positions(), 'difference': difference, 'raw_covariance': raw,
            'transform': transform, 'covariance': covariance, 'code_indices': indices,
            'count': count, 'nrate': len(difference), 'size': len(covariance)}


def solve_data(d, error, *, include_phase=True, jerk=None, phase_step_m=0., instantaneous=False):
    codes, instantaneous_rates = inertial_observations(TIMES, d['stations'][:7], CLOCKS[:7], jerk=jerk)
    phase_path = codes + np.arange(7)[None, :]*1234.  # constant arbitrary ambiguities
    phase_path[len(TIMES)//2:, 0] += phase_step_m
    rates = (d['difference']@phase_path.ravel()).reshape(len(TIMES)-1, 7)
    if instantaneous:
        rates = instantaneous_rates[1:]  # Deliberately wrong observable, retained stress case.
    count, end = d['count'], d['count']+d['nrate']
    codes += error[:count].reshape(codes.shape)
    rates += error[count:end].reshape(rates.shape)
    clocks = CLOCKS[:7]+error[end:end+14].reshape(7, 2)
    stations = d['stations'][:7]+error[end+14:].reshape(7, 3)
    covariance = d['covariance'] if include_phase else d['covariance'][np.ix_(d['code_indices'], d['code_indices'])]
    return fit_intervals(TIMES, stations, codes, rates, clocks, covariance,
                         calibration_statuses=[CALIBRATION]*7, include_phase=include_phase)


def summarize(result):
    report = compact(result)
    report.update(branch_candidates=result['branch_candidates'], branch_ambiguity=result['branch_ambiguity'],
                  branch_distinct_threshold_local_sigma=result['branch_distinct_threshold_local_sigma'])
    cov = result['covariance_joint']
    report.update(position_error_m=float(np.linalg.norm(result['state'][:3]-STATE[:3])),
                  velocity_error_m_s=float(np.linalg.norm(result['state'][3:6]-STATE[3:6])),
                  local_position_radius95_m=float(np.sqrt(chi2.ppf(.95, 3)*np.linalg.eigvalsh(cov[:3, :3])[-1])),
                  local_velocity_radius95_m_s=float(np.sqrt(chi2.ppf(.95, 3)*np.linalg.eigvalsh(cov[3:6, 3:6])[-1])))
    return report


def run():
    d = design()
    zero = np.zeros(d['size'])
    nominal = {name: solve_data(d, zero, include_phase=phase) for name, phase in [('code_only', False), ('code_phase', True)]}
    # The excluded receiver uses future endpoints 30 and 60 seconds, with an
    # explicitly independent calibration/noise block in this bounded study.
    heldout_noise = np.array([[400., .02/30], [.02/30, 2*.01**2/30**2]])
    extended = block_diag(d['covariance'], np.diag([4., .01**2]), .25*np.eye(3), heldout_noise)
    forecast = forecast_interval(nominal['code_phase'], 30., 60., d['stations'][7], CLOCKS[7],
                                 extended, calibration_status=CALIBRATION)
    forecast.pop('mapping')
    forecast_sha = hashlib.sha256(json.dumps(native(forecast), sort_keys=True, allow_nan=False).encode()).hexdigest()
    heldout_codes, _ = inertial_observations([30., 60.], d['stations'][7:], CLOCKS[7:])
    heldout_error = forecast['prediction'][6:]-np.array([heldout_codes[-1, 0], np.diff(heldout_codes[:, 0])[0]/30])
    trials = []
    rng = np.random.default_rng(SEED)
    for index in range(TRIAL_COUNT):
        error = np.linalg.cholesky(d['covariance'])@rng.normal(size=d['size'])
        trials.append({'index': index, 'fits': {name: summarize(solve_data(d, error, include_phase=phase))
                      for name, phase in [('code_only', False), ('code_phase', True)]}})
    stress = {
        'unflagged_phase_step_0_5m': summarize(solve_data(d, zero, phase_step_m=.5)),
        'unmodelled_jerk': summarize(solve_data(d, zero, jerk=JERK)),
        'instantaneous_rates_mislabelled_as_intervals': summarize(solve_data(d, zero, instantaneous=True))}
    moments = residual_moments(nominal['code_phase'], d['covariance'], d['covariance'])
    summaries = {name: summarize(r) for name, r in nominal.items()}
    criteria = {
        'both_nominal_models_accepted': all(r['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED' for r in nominal.values()),
        'both_noiseless_positions_within_1cm': all(r['position_error_m'] < .01 for r in summaries.values()),
        'both_noiseless_velocities_within_0_1mm_s': all(r['velocity_error_m_s'] < .0001 for r in summaries.values()),
        'phase_reduces_local_velocity_radius': summaries['code_phase']['local_velocity_radius95_m_s'] < summaries['code_only']['local_velocity_radius95_m_s'],
        'phase_reduces_local_position_radius': summaries['code_phase']['local_position_radius95_m'] < summaries['code_only']['local_position_radius95_m'],
        'linear_cost_mean_matches_dof': abs(moments['expected_cost']-nominal['code_phase']['residual_dof']) < 1e-6,
        'linear_cost_variance_matches_dof': abs(moments['variance_cost']-2*nominal['code_phase']['residual_dof']) < 1e-5,
        'all_fixed_trials_retained': len(trials) == TRIAL_COUNT,
        'phase_step_rejected': stress['unflagged_phase_step_0_5m']['status'] == 'MODEL_REJECTED',
        'jerk_rejected': stress['unmodelled_jerk']['status'] == 'MODEL_REJECTED',
        'wrong_instantaneous_observable_rejected': stress['instantaneous_rates_mislabelled_as_intervals']['status'] == 'MODEL_REJECTED'}
    criteria['excluded_interval_code_within_1cm'] = abs(heldout_error[0]) < .01
    criteria['excluded_interval_phase_within_0_1mm_s'] = abs(heldout_error[1]) < .0001
    root = Path(__file__).resolve().parents[2]
    sources = ['research/kinematic/'+name for name in ('interval_fit.py', 'interval_study.py', 'joint_fit.py',
               'joint_study.py', 'phase_rates.py', 'receiver_time.py', 'inverse_uncertainty.py',
               's2_validation.py', 'synthetic.py', 'model.py', 'clock_drift.py', 'doppler.py', 'rinex_observations.py')]
    sources += ['positioning/'+name for name in ('solver.py', 'calibration.py', 'navigation.py', 'context.py', 'errors.py')]
    return native({'schema': 'interval-inverse-synthetic-v1', 'real_rf_qualified': False,
        'scope': 'Invented IF paths and compressed reference calibrations. Local covariance, finite branches; no real RINEX target pipeline or total coverage.',
        'design': {'tags_s': TIMES, 'stations_m': d['stations'][:7], 'state': STATE, 'clocks': CLOCKS[:7],
                   'seed': SEED, 'trial_count': TRIAL_COUNT, 'raw_order': 'endpoint codes, endpoint IF phase paths in metres, receiver clocks, receiver ground coordinates',
                   'covariance_recipe': 'design() in source hash', 'raw_covariance_sha256': hashlib.sha256(d['raw_covariance'].astype('<f8').tobytes()).hexdigest()},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
        'nominal': summaries, 'trials': trials, 'stress': stress, 'local_linear_residual_moments': moments,
        'excluded_forecast': forecast, 'excluded_forecast_sha256_before_evaluation': forecast_sha,
        'excluded_evaluation_error_code_m_rate_m_s': heldout_error,
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
