"""Fixed synthetic delay/bias sensitivity study. No target RF access."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag

from .interval_fit import forecast_interval, interval_output
from .interval_study import CALIBRATION, design, solve_data, summarize
from .interval_systematics import forecast_systematics, transport_systematics
from .s2_validation import CLOCKS, TIMES
from .synthetic import native

NAMES = ('common_phase_drift_1mm_s', 'receiver0_common_path_curvature_10cm',
         'receiver0_phase_wave_2cm', 'receiver0_reference_clock_drift_1mm_s',
         'receiver0_constant_phase_5m', 'common_code_offset_10m')


def declared_modes(d):
    """Phenomenological templates, NOT a troposphere/receiver error envelope.

    Amplitudes and receiver identities fixed without target-state geometry.
    Only the common phase drift and common code offset extend to the excluded
    receiver. Receiver-specific effects are independent of that receiver.
    """
    count = d['count']
    raw = np.zeros((len(d['raw_covariance']), len(NAMES)))
    raw[count:2*count, 0] = np.repeat(TIMES*.001, 7)
    curve = .1*(TIMES/300)**2
    raw[:count:7, 1] = curve
    raw[count:2*count:7, 1] = curve
    raw[count:2*count:7, 2] = .02*np.sin(2*np.pi*(TIMES+300)/600)
    raw[2*count+1, 3] = .001
    raw[count:2*count:7, 4] = 5.
    raw[:count, 5] = 10.
    fit = d['transform']@raw
    extended = np.vstack([fit, np.zeros((7, len(NAMES)))])
    extended[-1, 0] = .001  # Excluded phase interval shares the same drift.
    extended[-2, 5] = 10.  # Excluded code shares the same common offset.
    return fit, extended


def run():
    d = design()
    nominal = solve_data(d, np.zeros(d['size']))
    modes, extended_modes = declared_modes(d)
    local = transport_systematics(nominal, d['covariance'], modes)
    extended_cov = block_diag(d['covariance'], np.diag([4., .01**2]), .25*np.eye(3),
                              [[400., .02/30], [.02/30, 2*.01**2/900]])
    forecast = forecast_interval(nominal, 30, 60, d['stations'][7], CLOCKS[7], extended_cov,
                                 calibration_status=CALIBRATION)
    out = forecast_systematics(forecast, extended_modes)
    rows = []
    for i, name in enumerate(NAMES):
        # Both signs retained. No retry or amplitude change after inspecting fit.
        plus, minus = [solve_data(d, sign*modes[:, i]) for sign in (1, -1)]
        actual = (plus['state']-minus['state'])/2
        row = {'name': name, 'plus': summarize(plus), 'minus': summarize(minus),
                     'central_state_response': actual,
                     'local_state_response': local['parameter_bias_modes'][:11, i],
                     'linearization_difference': actual-local['parameter_bias_modes'][:11, i]}
        if all(r['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED' for r in (plus, minus)):
            outputs = [interval_output(r['state'], 30, 60, d['stations'][7], CLOCKS[7]) for r in (plus, minus)]
            response = (outputs[0]-outputs[1])/2
            response[6:] -= extended_modes[-2:, i]
            row['central_forecast_error_response'] = response
            row['forecast_linearization_difference'] = response-out['output_bias_modes'][:, i]
        rows.append(row)
    criteria = {
        'nominal_accepted': nominal['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED',
        'all_six_modes_and_both_signs_retained': len(rows) == 6,
        'constant_phase_cancels_before_fit': np.max(abs(modes[:, 4])) < 1e-14,
        'constant_phase_has_nominal_rejection_probability': abs(local['local_rejection_probability'][4]-.01) < 1e-10,
        'all_local_diagnostics_finite': bool(np.isfinite(local['parameter_bias_modes']).all() and np.isfinite(local['local_rejection_probability']).all()),
        'both_sign_refits_within_1m_of_local_position_response': all(np.linalg.norm(r['linearization_difference'][:3]) < 1 for r in rows),
        'both_sign_refits_within_0_01m_s_of_local_velocity_response': all(np.linalg.norm(r['linearization_difference'][3:6]) < .01 for r in rows),
        'no_rf_qualification': not local['real_rf_qualified']}
    criteria['rejected_refits_have_no_forecast'] = all('central_forecast_error_response' not in r for r in rows
        if any(r[sign]['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED' for sign in ('plus', 'minus')))
    criteria['accepted_forecast_linearization_within_1cm_code_0_1mm_s_rate'] = all(
        abs(r['forecast_linearization_difference'][6]) < .01 and abs(r['forecast_linearization_difference'][7]) < .0001
        for r in rows if 'forecast_linearization_difference' in r)
    root = Path(__file__).resolve().parents[2]
    prior = json.loads((root/'research/kinematic/results/interval_inverse_study_v1.json').read_text())
    sources = list(prior['sources_sha256'])+['research/kinematic/interval_systematics.py', 'research/kinematic/systematics_study.py']
    return native({'schema': 'interval-systematics-synthetic-v1', 'real_rf_qualified': False,
        'scope': 'Fixed phenomenological bias templates, not physical amplitude qualification or total error envelope.',
        'design': {'names': NAMES, 'fit_modes': modes, 'extended_modes': extended_modes,
                   'coefficient_box': [-1, 1], 'forecast_endpoints_s': [30, 60],
                   'covariance': 'unchanged interval_study.design()', 'random_draws': 0},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in sources},
        'nominal': summarize(nominal), 'local': local, 'forecast_local': out,
        'signed_refits': rows, 'criteria': criteria, 'criteria_pass': all(criteria.values())})


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
