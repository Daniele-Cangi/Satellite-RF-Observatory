"""Fixed out-of-basis validation of frozen slow-calibration estimators."""
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

ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT/'research/kinematic/slow_validation_plan.json'


def shape(case, tags):
    """Fixed shapes in receiver-tag time; no target geometry or fitted values."""
    u = (np.asarray(tags, float)+300)/300
    if case == 'nominal': return np.zeros_like(u)
    if case in ('shared_cubic', 'target_cubic'): return .1*u**3
    if case == 'shared_exponential': return .1*np.expm1(u)/np.expm1(1.)
    if case == 'shared_triangle': return .1*np.maximum(0., 1-abs(u-.5)/.3)
    if case == 'target_oscillation': return .05*np.sin(2*np.pi*1.3*u+.4)
    raise ValueError('unknown fixed validation case')


def data(d, case, error):
    count, nr = d['count'], d['nref']
    size = len(d['extended_covariance'])
    error = np.asarray(error, float)
    if error.shape != (size+7,) or not np.isfinite(error).all():
        raise ValueError('finite full raw and excluded perturbation required')
    codes, phases, refs, refphases = inputs(d, 'nominal')
    delay = shape(case, TIMES)
    codes[:, 0] += delay
    phases[:, 0] += delay
    if case.startswith('shared_'):
        refs[:, 0] += delay[:, None]
        refphases[:, 0] += delay[:, None]
    codes += error[:count].reshape(codes.shape)
    phases += error[count:2*count].reshape(phases.shape)
    refs += error[2*count:2*count+nr].reshape(refs.shape)
    stations = d['stations']+error[2*count+nr:2*count+nr+21].reshape(7, 3)
    refphases += error[2*count+nr+21:size].reshape(refphases.shape)
    return codes, phases, refs, refphases, stations


def evaluate(d, case, error, quadratic):
    codes, phases, refs, refphases, stations = data(d, case, error)
    calls = []
    def load():
        calls.append(True)
        return codes, phases
    function = fit_slow_calibration if quadratic else fit_shared_phase
    try:
        result = function(TIMES, stations, refs, refphases, d['extended_covariance'], load,
                           target='G08', references=REFERENCES)
    except ValueError as exc:
        return {'status': 'NUMERICAL_OR_INPUT_FAILURE', 'reason': str(exc), 'target_loader_calls': len(calls), 'real_rf_qualified': False}
    row = {'status': result['status'], 'reference_code_p': result['reference_code_p'],
           'reference_phase_p': result.get('reference_phase_p'), 'target_loader_calls': len(calls), 'real_rf_qualified': False}
    if not quadratic and 'downstream' in result:
        result['fit'] = result['downstream']['fit']
        result['fit_covariance'] = result['downstream']['compression']['covariance']
    if 'fit' in result:
        row['fit'] = summarize(result['fit'])
    if result['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
        return row
    station = receiver_positions()[7]
    clock = CLOCKS[7]
    extended = block_diag(result['fit_covariance'], d['excluded_covariance'])
    forecast = forecast_interval(result['fit'], 30, 60, station+error[-5:-2], clock+error[-7:-5],
                                 extended, calibration_status=CALIBRATION)
    forecast.pop('mapping')
    row['forecast_sha256_before_evaluation'] = hashlib.sha256(json.dumps(native(forecast), sort_keys=True, allow_nan=False).encode()).hexdigest()
    row['forecast'] = forecast
    truth, _ = inertial_observations([30., 60.], [station], [clock])
    delta = forecast['prediction'][6:]-np.array([truth[-1, 0], (truth[-1, 0]-truth[0, 0])/30])-error[-2:]
    row['excluded_error_code_m_rate_m_s'] = delta
    row['position_inside_local_radius'] = row['fit']['position_error_m'] <= row['fit']['local_position_radius95_m']
    row['excluded_inside_marginal_95_bands'] = abs(delta) <= 1.959963984540054*np.sqrt(np.diag(forecast['covariance_output'])[6:])
    return row


def run():
    plan = json.loads(PLAN.read_text())
    for name, expected in plan['frozen_sources_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
            raise ValueError('frozen estimator changed: '+name)
    d = design()
    d['excluded_covariance'] = block_diag(np.diag([4., .0001]), .25*np.eye(3), np.diag([400., 2e-4/900]))
    raw_covariance = block_diag(d['extended_covariance'], d['excluded_covariance'])
    zero = np.zeros(len(raw_covariance))
    modes = [('affine', False), ('quadratic', True)]
    fixed = {case: {name: evaluate(d, case, zero, q) for name, q in modes} for case in plan['cases']}
    rng = np.random.default_rng(plan['seed'])
    factor = np.linalg.cholesky(raw_covariance)
    trials = []
    for case in plan['noisy_cases']:
        for index in range(plan['draws_per_case']):
            error = factor@rng.normal(size=len(raw_covariance))
            trials.append({'case': case, 'index': index,
                           'raw_error_sha256': hashlib.sha256(error.astype('<f8').tobytes()).hexdigest(),
                           'fits': {name: evaluate(d, case, error, q) for name, q in modes}})
    allrows = [r for models in fixed.values() for r in models.values()]+[r for trial in trials for r in trial['fits'].values()]
    criteria = {
        'all_six_fixed_pairs_retained': len(fixed) == 6 and all(len(v) == 2 for v in fixed.values()),
        'all_eight_noise_pairs_retained': len(trials) == 8 and all(len(v['fits']) == 2 for v in trials),
        'rejections_have_no_forecast': all('forecast' not in r for r in allrows if r['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'),
        'reference_rejection_precedes_target': all(r['target_loader_calls'] == 0 for r in allrows if r['status'] in ('REFERENCE_CODE_REJECTED', 'REFERENCE_PHASE_RESIDUAL_REJECTED')),
        'no_numerical_failures': all(r['status'] != 'NUMERICAL_OR_INPUT_FAILURE' for r in allrows),
        'no_rf_qualification': all(not r['real_rf_qualified'] for r in allrows)}
    sources = list(plan['frozen_sources_sha256'])+['research/kinematic/slow_validation.py']
    return native({'schema': 'slow-calibration-out-of-basis-validation-v1', 'real_rf_qualified': False,
        'scope': 'Fixed synthetic out-of-basis validation, small paired sample, no real RF confirmation or population coverage claim.',
        'plan_sha256': hashlib.sha256(PLAN.read_bytes()).hexdigest(), 'plan': plan,
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'sources_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        'fixed_cases': fixed, 'noisy_trials': trials, 'criteria': criteria, 'criteria_pass': all(criteria.values())})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists(): parser.error('refusing to overwrite existing report')
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps(report['criteria'], indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
