"""Measured reference errors through the existing interval inverse.

Hybrid development experiment: synthetic trajectory, actual receiver geometry,
real reference error sequences. It is NOT an independent real-target solution.
Covariance is an explicit weighting scenario, never inferred from these errors.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag

from .real_phase import BASE, COHORTS, digest
from ..kinematic.interval_fit import fit_intervals, interval_output
from ..kinematic.interval_systematics import transport_systematics
from ..kinematic.phase_rates import interval_matrix
from ..kinematic.s2_validation import inertial_observations
from ..kinematic.synthetic import native

TAGS = np.arange(-300., 1., 30.)
CALIBRATION = 'CONDITIONAL_CLOCK_MODEL_ACCEPTED'


def design(stations):
    """An explicit conditional scenario, shared by both paired estimators."""
    n, count = len(stations), len(TAGS)*len(stations)
    direction = np.mean(stations/np.linalg.norm(stations, axis=1)[:, None], axis=0)
    direction /= np.linalg.norm(direction)
    tangent = np.cross([0., 0., 1.], direction)
    tangent /= np.linalg.norm(tangent)
    state = np.r_[26.6e6*direction, 3000*tangent, -.56*direction, 0., 0.]
    difference = interval_matrix(TAGS, n)
    # Reuse endpoint differencing: adjacent phase-rate errors are correlated.
    raw = block_diag(400*np.eye(count), .02**2*np.eye(count),
                     np.kron(np.eye(n), np.diag([4., .01**2])), .25*np.eye(3*n))
    transform = block_diag(np.eye(count), difference, np.eye(5*n))
    covariance = transform@raw@transform.T
    indices = np.r_[np.arange(count), np.arange(count+len(difference), len(covariance))]
    codes, _ = inertial_observations(TAGS, stations, np.zeros((n, 2)), state=state)
    return {'state': state, 'stations': stations, 'codes': codes,
            'rates': (difference@codes.ravel()).reshape(len(TAGS)-1, n),
            'covariance': covariance, 'code_indices': indices, 'count': count,
            'nrate': len(difference), 'size': len(covariance)}


def fit(d, error, phase):
    n, count, end = len(d['stations']), d['count'], d['count']+d['nrate']
    covariance = d['covariance'] if phase else d['covariance'][np.ix_(d['code_indices'], d['code_indices'])]
    return fit_intervals(TAGS, d['stations'], d['codes']+error[:count].reshape(len(TAGS), n),
                         d['rates']+error[count:end].reshape(len(TAGS)-1, n),
                         np.zeros((n, 2)), covariance,
                         calibration_statuses=[CALIBRATION]*n, include_phase=phase)


def state_metrics(delta):
    return {'position_t0_m': float(np.linalg.norm(delta[:3])),
            'velocity_t0_m_s': float(np.linalg.norm(delta[3:6])),
            'position_t_plus_60_m': float(np.linalg.norm(delta[:3]+60*delta[3:6]+1800*delta[6:9]))}


def summarize(result, truth):
    return {'status': result['status'], 'errors': state_metrics(result['state']-truth),
            'rank': result['rank'], 'scaled_condition': result['scaled_condition'],
            'conditional_residual_p': result['conditional_residual_p'],
            'branch_failures': result['branch_failures'], 'branch_ambiguity': result['branch_ambiguity'],
            'state': result['state']}


def window_errors(cohort, baseline, start):
    """Selection uses completeness only, no ranking by residual or fit success.

    Pick lexicographically first complete link at each parsed station; keep
    every station and reject the whole window if any has no complete link.
    All other references (>=4) estimate its common phase increment error.
    """
    plan = cohort['plan']
    times = start+np.arange(11)*30
    names = [s for s in plan['stations'] if cohort['stations'][s]['status'] == 'PARSED']
    choices, codes, phase, corrected = {}, [], [], []
    for station in names:
        rows = { (r['time_s'], r['reference']): r for r in cohort['stations'][station]['rows']
                 if r['status'] == 'AVAILABLE' and (station, r['time_s'], r['reference']) in baseline }
        candidates = [sv for sv in sorted(plan['references']) if all((t, sv) in rows for t in times)]
        if not candidates:
            return {'status': 'INCOMPLETE_STATION_WINDOW', 'station': station, 'start_gpst_s': start}
        sv = candidates[0]
        choices[station] = sv
        def residual(t, satellite):
            row = rows[(t, satellite)]
            code = baseline[(station, t, satellite)]['residual_m']
            return code, row['phase_m']-row['code_m']+code
        codes.append([residual(t, sv)[0] for t in times])
        rates, adjusted = [], []
        for a, b in zip(times, times[1:]):
            others = [r for r in plan['references'] if r != sv and (a, r) in rows and (b, r) in rows]
            if len(others) < 4:
                return {'status': 'INSUFFICIENT_OTHER_REFERENCES', 'station': station, 'time_s': b, 'start_gpst_s': start}
            value = (residual(b, sv)[1]-residual(a, sv)[1])/30
            common = np.mean([(residual(b, r)[1]-residual(a, r)[1])/30 for r in others])
            rates.append(value)
            adjusted.append(value-common)
        phase.append(rates); corrected.append(adjusted)
    return {'status': 'COMPLETE', 'start_gpst_s': start, 'stations': names, 'references': choices,
            'code_error_m': np.array(codes).T, 'raw_phase_error_m_s': np.array(phase).T,
            'other_reference_corrected_phase_error_m_s': np.array(corrected).T}


def run(inputs):
    output = {'schema': 'measured-reference-error-interval-transfer-v1', 'real_rf_qualified': False,
              'scope': 'Hybrid sensitivity, not target reconstruction: synthetic vacuum trajectory, actual station coordinates, measured reference error traces. Original code-clock fit includes the selected reference; no independent calibration claim.',
              'weight_scenario': {'code_sigma_m': 20., 'phase_endpoint_sigma_m': .02,
                                  'clock_offset_sigma_m': 2., 'clock_drift_sigma_m_s': .01, 'ground_sigma_m': .5},
              'cohorts': {}}
    for name, cohort in inputs['cohorts'].items():
        folder, _, report_file, _ = COHORTS[name]
        report = json.loads((BASE/'results'/report_file).read_bytes())
        baseline = {(r['station'], r['time_s'], r['reference']): r for r in report['rows']}
        positions = json.loads((BASE/'inputs'/folder/'positions.json').read_bytes())
        names = [s for s in cohort['plan']['stations'] if cohort['stations'][s]['status']=='PARSED']
        if len(names) < 5:
            output['cohorts'][name] = {'status': 'INSUFFICIENT_STATIONS', 'stations': names}
            continue
        stations = np.array([positions[s][0] for s in names])
        d = design(stations)
        nominal = {key: fit(d, np.zeros(d['size']), phase) for key, phase in [('code_only', False), ('code_phase', True)]}
        # Constant station-specific code offsets: phase increments cannot
        # directly observe them. Unit amplitudes are hypothetical, not bounds.
        modes = np.zeros((d['size'], len(names)))
        for j in range(len(names)):
            modes[j:d['count']:len(names), j] = 1.
        sensitivity = {}
        for key, r in nominal.items():
            ix = np.arange(d['size']) if key == 'code_phase' else d['code_indices']
            if r['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
                sensitivity[key] = {'status': r['status']}
                continue
            transfer = transport_systematics(r, d['covariance'][np.ix_(ix, ix)], modes[ix])
            sensitivity[key] = {'unit_station_offset_responses': [state_metrics(q) for q in transfer['parameter_bias_modes'].T],
                                'residual_noncentrality': transfer['residual_noncentrality']}
        cases = []
        split = cohort['plan']['training_before_gpst_s']
        for start in range(split, split+1800, 300):
            case = window_errors(cohort, baseline, start)
            if case['status'] != 'COMPLETE':
                cases.append(case); continue
            fits = {}
            for key, field, use_phase in [('code_only', 'raw_phase_error_m_s', False),
                    ('code_phase_raw', 'raw_phase_error_m_s', True),
                    ('code_phase_other_references', 'other_reference_corrected_phase_error_m_s', True)]:
                error = np.r_[case['code_error_m'].ravel(), case[field].ravel(), np.zeros(5*len(names))]
                try:
                    r = fit(d, error, use_phase)
                    fits[key] = summarize(r, d['state'])
                    # Future time prediction is genuinely after the fitted end;
                    # expected vacuum path is synthetic, not held-out real RF.
                    expected = interval_output(d['state'], 30., 60., stations[0], [0., 0.])
                    predicted = interval_output(r['state'], 30., 60., stations[0], [0., 0.])
                    fits[key]['synthetic_future_code_error_m'] = float(predicted[6]-expected[6])
                    fits[key]['synthetic_future_rate_error_m_s'] = float(predicted[7]-expected[7])
                except ValueError as error:
                    fits[key] = {'status': 'FIT_FAILED', 'reason': str(error)}
                print(name, start, key, fits[key]['status'], flush=True)
            cases.append({**case, 'fits': fits})
        output['cohorts'][name] = {'stations': names, 'synthetic_state': d['state'],
            'nominal': {k: summarize(r, d['state']) for k, r in nominal.items()},
            'constant_station_offset_1m': sensitivity, 'cases': cases,
            'real_excluded_receiver_prediction': 'NOT_EVALUATED; requires independent real-target calibration and propagation model'}
    return native(output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(json.loads(args.inputs.read_bytes()))
    result['input_sha256'] = digest(args.inputs.read_bytes())
    result['source_sha256'] = digest(Path(__file__).read_bytes())
    args.output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n', encoding='utf-8', newline='\n')
