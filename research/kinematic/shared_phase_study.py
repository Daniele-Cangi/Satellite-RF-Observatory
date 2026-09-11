"""Fixed synthetic shared-calibration reference-phase gate study."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag

from .interval_study import summarize
from .s2_validation import TIMES
from .shared_calibration_study import REFERENCES, design as old_design, inputs as old_inputs
from .shared_phase_gate import fit_shared_phase
from .synthetic import native

CASES = ('nominal', 'shared_affine', 'target_only_affine', 'shared_curvature',
         'strong_shared_curvature', 'reference_phase_slip', 'constant_ambiguity', 'invalid_reference_step')


def design():
    d = old_design()
    oldsize, count, nr = len(d['covariance']), d['count'], d['nref']
    cov = block_diag(d['covariance'], .0001*np.eye(nr))
    phase_modes = d['shared_modes'][2*count:2*count+nr]
    cov[:oldsize, oldsize:] = d['shared_modes']@phase_modes.T
    cov[oldsize:, :oldsize] = cov[:oldsize, oldsize:].T
    cov[oldsize:, oldsize:] += phase_modes@phase_modes.T
    # Independent-band code/phase correlation 0.1 in addition to shared drift.
    cross = np.arange(nr)
    cov[2*count+cross, oldsize+cross] += .003
    cov[oldsize+cross, 2*count+cross] += .003
    return d | {'extended_covariance': cov}


def inputs(d, case):
    base = case if case in ('shared_affine', 'target_only_affine', 'shared_curvature', 'invalid_reference_step') else 'nominal'
    codes, phases, refs = old_inputs(d, base)
    _, _, reference_phases = old_inputs(d, 'nominal' if case == 'invalid_reference_step' else base)
    reference_phases += np.arange(28).reshape(1, 7, 4)*1234.
    if case == 'strong_shared_curvature':
        delay = (TIMES/300)**2  # 1 m fixed stress, retained alongside 0.1 m.
        codes[:, 0] += delay
        phases[:, 0] += delay
        refs[:, 0] += delay[:, None]
        reference_phases[:, 0] += delay[:, None]
    if case == 'reference_phase_slip':
        reference_phases[len(TIMES)//2:, 0, 0] += .5
    if case == 'constant_ambiguity':
        reference_phases += 5000.
    return codes, phases, refs, reference_phases


def evaluate(d, case):
    codes, phases, refs, refphases = inputs(d, case)
    calls = []
    def load():
        calls.append(True)
        return codes, phases
    result = fit_shared_phase(TIMES, d['stations'], refs, refphases, d['extended_covariance'], load,
                              target='G08', references=REFERENCES)
    result['target_loader_calls'] = len(calls)
    return result


def run():
    d = design()
    full = {case: evaluate(d, case) for case in CASES}
    cases = {}
    for name, result in full.items():
        row = {k: v for k, v in result.items() if k not in ('downstream', 'phase_residual_mapping',
               'phase_residual_covariance', 'phase_residual_fit_data_cross_covariance')}
        if 'downstream' in result:
            row['fit'] = summarize(result['downstream']['fit'])
        cases[name] = row
    criteria = {
        'nominal_accepted': full['nominal']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED',
        'shared_affine_accepted': full['shared_affine']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED',
        'constant_phase_ambiguity_accepted': full['constant_ambiguity']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED',
        'slip_stops_before_target': full['reference_phase_slip']['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED' and full['reference_phase_slip']['target_loader_calls'] == 0,
        'strong_curvature_stops_before_target': full['strong_shared_curvature']['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED' and full['strong_shared_curvature']['target_loader_calls'] == 0,
        'code_rejection_precedes_phase_test': full['invalid_reference_step']['status'] == 'REFERENCE_CODE_REJECTED' and 'reference_phase_p' not in full['invalid_reference_step'],
        'phase_does_not_change_clock': bool(np.array_equal(full['nominal']['clock_coefficients'], full['reference_phase_slip']['clock_coefficients'])),
        'accepted_gate_preserves_target_fit_covariance': bool(np.array_equal(full['nominal']['downstream']['compression']['covariance'], full['constant_ambiguity']['downstream']['compression']['covariance'])),
        'all_eight_cases_retained': len(cases) == 8}
    root = Path(__file__).resolve().parents[2]
    parent = root/'research/kinematic/results/shared_calibration_study_v1.json'
    sources = list(json.loads(parent.read_text())['sources_sha256'])+['research/kinematic/shared_phase_gate.py', 'research/kinematic/shared_phase_study.py']
    return native({'schema': 'shared-reference-phase-gate-synthetic-v1', 'real_rf_qualified': False,
        'design': {'cases': CASES, 'reference_phase_sigma_m': .01, 'independent_code_phase_correlation': .1,
                   'shared_random_drift_sigma_m_s': .01, 'phase_gate_threshold_p': .01,
                   'reference_phase_dof': 280, 'small_curvature_m': .1, 'strong_curvature_m': 1., 'slip_m': .5},
        'scope': 'Synthetic geometry-subtracted reference code and phase residuals, no real RINEX admission. Sequential tests and fit retain unconditional covariance; post-selection coverage unproven.',
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
        'cases': cases, 'criteria': criteria, 'criteria_pass': all(criteria.values())})


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
