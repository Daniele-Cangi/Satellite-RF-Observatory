"""Development comparison of affine and quadratic shared path calibration."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag

from .interval_fit import forecast_interval
from .interval_study import CALIBRATION, summarize
from .s2_validation import CLOCKS, TIMES, inertial_observations
from .shared_phase_study import design, inputs, REFERENCES
from .shared_phase_gate import fit_shared_phase
from .slow_calibration import fit_slow_calibration
from .synthetic import native, receiver_positions

CASES = ('nominal', 'shared_curvature', 'target_only_curvature', 'shared_wave', 'reference_phase_slip')


def case_inputs(d, case):
    codes, phases, refs, refphases = inputs(d, case if case in ('shared_curvature', 'reference_phase_slip') else 'nominal')
    if case == 'target_only_curvature':
        delay = .1*(TIMES/300)**2
        codes[:, 0] += delay
        phases[:, 0] += delay
    if case == 'shared_wave':
        delay = .02*np.sin(2*np.pi*(TIMES+300)/600)
        codes[:, 0] += delay
        phases[:, 0] += delay
        refs[:, 0] += delay[:, None]
        refphases[:, 0] += delay[:, None]
    return codes, phases, refs, refphases


def evaluate(d, case, quadratic):
    codes, phases, refs, refphases = case_inputs(d, case)
    calls = []
    def load():
        calls.append(True)
        return codes, phases
    function = fit_slow_calibration if quadratic else fit_shared_phase
    result = function(TIMES, d['stations'], refs, refphases, d['extended_covariance'], load,
                       target='G08', references=REFERENCES)
    if not quadratic and 'downstream' in result:
        result['fit'] = result['downstream']['fit']
        result['fit_covariance'] = result['downstream']['compression']['covariance']
    result['target_loader_calls'] = len(calls)
    return result


def run():
    d = design()
    results = {case: {name: evaluate(d, case, quadratic) for name, quadratic in [('affine', False), ('quadratic', True)]} for case in CASES}
    rows = {}
    for case, models in results.items():
        rows[case] = {}
        for name, result in models.items():
            row = {k: result[k] for k in ('status', 'reference_code_p', 'target_loader_calls', 'real_rf_qualified')}
            row['reference_phase_p'] = result.get('reference_phase_p')
            if 'reference_coefficients' in result:
                row['reference_coefficients'] = result['reference_coefficients']
            if 'fit' in result:
                row['fit'] = summarize(result['fit'])
            if result['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
                extended = block_diag(result['fit_covariance'], np.diag([4., .0001]), .25*np.eye(3), np.diag([400., 2e-4/900]))
                station = receiver_positions()[7]
                forecast = forecast_interval(result['fit'], 30, 60, station, CLOCKS[7], extended, calibration_status=CALIBRATION)
                forecast.pop('mapping')
                row['forecast_sha256_before_evaluation'] = hashlib.sha256(json.dumps(native(forecast), sort_keys=True, allow_nan=False).encode()).hexdigest()
                row['forecast'] = forecast
                # Receiver-specific disturbances are absent on this excluded
                # receiver. Its calibration is independently assumed known to
                # the declared covariance, not derived from target observations.
                code, _ = inertial_observations([30., 60.], [station], [CLOCKS[7]])
                row['excluded_error_code_m_rate_m_s'] = forecast['prediction'][6:]-[code[-1, 0], (code[-1, 0]-code[0, 0])/30]
            rows[case][name] = row
    q = rows['shared_curvature']['quadratic']['fit']
    a = rows['shared_curvature']['affine']['fit']
    criteria = {
        'both_nominal_models_accepted': all(r['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED' for r in rows['nominal'].values()),
        'quadratic_shared_curvature_position_within_1cm': q['position_error_m'] < .01,
        'shared_curvature_error_reduced': q['position_error_m'] < a['position_error_m'],
        'quadratic_nominal_uncertainty_not_artificially_smaller': rows['nominal']['quadratic']['fit']['local_position_radius95_m'] >= rows['nominal']['affine']['fit']['local_position_radius95_m'],
        'slip_rejected_in_both_models_before_target': all(r['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED' and r['target_loader_calls'] == 0 for r in rows['reference_phase_slip'].values()),
        'all_fixed_pairs_retained': len(rows) == 5 and all(len(r) == 2 for r in rows.values()),
        'no_forecast_after_rejection': all('forecast' not in r for pair in rows.values() for r in pair.values() if r['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED')}
    root = Path(__file__).resolve().parents[2]
    prior = root/'research/kinematic/results/shared_phase_gate_study_v1.json'
    sources = list(json.loads(prior.read_text())['sources_sha256'])+['research/kinematic/slow_calibration.py', 'research/kinematic/slow_calibration_study.py']
    return native({'schema': 'slow-shared-path-calibration-development-v1', 'real_rf_qualified': False,
        'scope': 'Development on known synthetic curvature and fixed differential/wave stress cases. No independent confirmation, physical amplitude qualification or total coverage.',
        'design': {'cases': CASES, 'basis': '[1, t, (t/abs(first_tag))**2] per receiver',
                   'reference_phase_unused_for_fit': True, 'curvature_m': .1, 'wave_m': .02,
                   'tags_s': TIMES, 'threshold_p': .01, 'noise_draws': 0,
                   'excluded_interval_s': [30, 60], 'excluded_receiver_disturbance': 'none; calibration independently assumed'},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
        'cases': rows, 'criteria': criteria, 'criteria_pass': all(criteria.values())})


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
