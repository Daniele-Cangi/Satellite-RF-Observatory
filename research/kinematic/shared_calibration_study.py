"""Fixed shared versus target-only delay study with explicit reference rows."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag

from .interval_study import summarize
from .s2_validation import CLOCKS, TIMES, inertial_observations
from .shared_calibration import compression, fit_shared
from .synthetic import native, receiver_positions

REFERENCES = ('G01', 'G02', 'G03', 'G04')


def design():
    n, count, nr = 7, len(TIMES)*7, len(TIMES)*7*4
    cov = block_diag(400*np.eye(count), .0001*np.eye(count), 9*np.eye(nr), .25*np.eye(3*n))
    modes = np.zeros((len(cov), n))
    for j in range(n):
        modes[j:count:n, j] = TIMES*.01
        modes[count+j:2*count:n, j] = TIMES*.01
        for t, tag in enumerate(TIMES):
            modes[2*count+(t*n+j)*4:2*count+(t*n+j+1)*4, j] = tag*.01
    cov += modes@modes.T
    return {'covariance': cov, 'count': count, 'nref': nr, 'stations': receiver_positions()[:7], 'shared_modes': modes}


def inputs(d, case):
    codes, _ = inertial_observations(TIMES, d['stations'], CLOCKS[:7])
    phases = codes+np.arange(7)[None, :]*1234.
    references = np.repeat((CLOCKS[:7, 0][None, :]+TIMES[:, None]*CLOCKS[:7, 1][None, :])[:, :, None], 4, axis=2)
    if case in ('shared_affine', 'target_only_affine'):
        delay = .01*TIMES
    elif case == 'shared_curvature':
        delay = .1*(TIMES/300)**2
    else:
        delay = np.zeros(len(TIMES))
    codes[:, 0] += delay
    phases[:, 0] += delay
    if case.startswith('shared_'):
        references[:, 0, :] += delay[:, None]
    if case == 'invalid_reference_step':
        references[len(TIMES)//2:, 0, 0] += 300.
    return codes, phases, references


def evaluate(d, case):
    codes, phases, references = inputs(d, case)
    return fit_shared(TIMES, d['stations'], references, d['covariance'], lambda: (codes, phases),
                       target='G08', references=REFERENCES)


def run():
    d = design()
    results = {name: evaluate(d, name) for name in ('nominal', 'shared_affine', 'target_only_affine', 'shared_curvature', 'invalid_reference_step')}
    compact = {}
    for name, result in results.items():
        row = {k: result[k] for k in ('status', 'real_rf_qualified', 'reference_p', 'reference_cost', 'reference_dof', 'clock_coefficients')}
        if 'fit' in result:
            row['fit'] = summarize(result['fit'])
        compact[name] = row
    c = results['nominal']['compression']
    start = d['count']+(len(TIMES)-1)*7
    cross = c['covariance'][:start, start:start+14]
    criteria = {
        'nominal_accepted': results['nominal']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED',
        'nominal_position_within_1cm': compact['nominal']['fit']['position_error_m'] < .01,
        'shared_affine_accepted': results['shared_affine']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED',
        'shared_affine_smaller_position_error_than_target_only': compact['shared_affine']['fit']['position_error_m'] < compact['target_only_affine']['fit']['position_error_m'],
        'shared_affine_clock_drift_recovered': abs(results['shared_affine']['clock_coefficients'][0, 1]-CLOCKS[0, 1]-.01) < 1e-9,
        'target_clock_cross_covariance_retained': bool(np.max(abs(cross)) > .01),
        'invalid_references_stop_before_target_fit': results['invalid_reference_step']['status'] == 'REFERENCE_CODE_REJECTED' and 'fit' not in results['invalid_reference_step'],
        'all_five_cases_retained': len(results) == 5}
    root = Path(__file__).resolve().parents[2]
    parent = root/'research/kinematic/results/interval_inverse_study_v1.json'
    sources = list(json.loads(parent.read_text())['sources_sha256'])+['research/kinematic/shared_calibration.py', 'research/kinematic/shared_calibration_study.py']
    return native({'schema': 'shared-reference-target-calibration-synthetic-v1', 'real_rf_qualified': False,
        'scope': 'Explicit invented geometry-subtracted reference code residuals; no real RINEX, reference phase gate or physical error qualification.',
        'design': {'tags_s': TIMES, 'references': REFERENCES, 'target': 'G08', 'receivers': 7,
                   'reference_sigma_m': 3., 'target_code_sigma_m': 20., 'target_phase_sigma_m': .01,
                   'shared_random_drift_sigma_m_s': .01, 'deterministic_affine_drift_m_s': .01,
                   'curvature_amplitude_m': .1, 'reference_step_m': 300., 'random_draws': 0,
                   'raw_order': 'target code, target phase path, reference clock residuals time/receiver/reference, ground'},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
        'compressed_covariance': c['covariance'], 'cases': compact, 'criteria': criteria, 'criteria_pass': all(criteria.values())})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to overwrite existing report')
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(report['criteria'], indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
