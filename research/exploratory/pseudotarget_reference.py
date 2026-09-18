"""Recalibrate receiver clocks without each exposed reference pseudo-target."""
from collections import Counter
from datetime import datetime
from functools import lru_cache
import hashlib
from pathlib import Path
import numpy as np

from . import day_reference as day
from .day_reference_checked import RUNNER_SHA
from .erp_polar_bound import pinned, strict_json
from .reference_residual_structure_v2 import groups, design, center_blocks
from .pseudotarget_statistics import summarize

BASE = Path(__file__).parent


def inputs(plan_sha):
    plan = strict_json(pinned(BASE/'pseudotarget_plan.json', plan_sha))
    pinned(Path(day.__file__), RUNNER_SHA)
    original, ctx, observations, positions, receipt = day.inputs()
    report = strict_json(pinned(BASE/'results/day_reference_v1.json', plan['baseline_report_sha256']))
    if report['plan'] != original or not report['calibration_complete'] or report['target_orbit_accessed'] is not False:
        raise ValueError('baseline report not qualified or plan differs')
    seen = set()
    for row in report['rows']:
        key = row['station'], row['time_s'], row['reference']
        if (key in seen or row['station'] not in original['stations'] or row['time_s'] not in ctx.times or
                row['reference'] not in original['references'] or row['reference'] == ctx.target):
            raise ValueError('unadmitted or duplicate reference path')
        seen.add(key)
    blocks = groups(report['rows'])
    if set(blocks) != {(s, t) for s in original['stations'] for t in ctx.times}:
        raise ValueError('incomplete baseline cohort')
    if any(len(ix) < 4 for ix in blocks.values()):
        raise ValueError('incomplete baseline reference block')
    return plan, original, ctx, observations, positions, receipt, report


def receiver_clock(codes, references, excluded, model, beta, plan):
    """Only admitted reference values enter the fixed point; no excluded access.

    model(sv, code, receiver_clock) returns range without additive receiver clock.
    The correction beta is subtracted from raw range-minus-model estimates.
    This deliberately omits the production SPP ground-coordinate qualification;
    EVALUATED means this bounded diagnostic passed its listed numerical checks.
    """
    refs = tuple(references)
    if excluded in refs or len(set(refs)) != len(refs):
        raise ValueError('pseudo-target or duplicate passed to calibration')
    if len(refs) < plan['minimum_remaining_references']:
        return {'status': 'INSUFFICIENT_REMAINING_REFERENCES'}
    if not set(refs) <= codes.keys() or not set(refs) <= beta.keys():
        return {'status': 'UNSUPPORTED_REFERENCE'}
    clock = 0.
    for iteration in range(plan['maximum_clock_iterations']):
        estimates = np.array([codes[sv]-model(sv, codes[sv], clock)-beta[sv] for sv in refs])
        if not np.isfinite(estimates).all():
            return {'status': 'NONFINITE_MODEL'}
        updated = float(estimates.mean())
        closure = abs(updated-clock)
        if closure <= plan['clock_closure_tolerance_m']:
            residuals = estimates-clock
            rms = float(np.sqrt(np.mean(residuals**2)))
            split = float(abs(estimates[::2].mean()-estimates[1::2].mean()))
            maximum = float(abs(residuals).max())
            status = 'EVALUATED' if (rms <= plan['maximum_reference_rms_m'] and
                maximum <= plan['maximum_reference_abs_m'] and split <= plan['maximum_split_clock_m']) else 'REFERENCE_DIAGNOSTIC_REJECTED'
            return {'status': status, 'clock_m': clock, 'clock_closure_m': closure,
                    'iterations': iteration+1, 'reference_count': len(refs),
                    'reference_rms_m': rms, 'reference_max_abs_m': maximum,
                    'split_clock_m': split, 'residuals_m': residuals.tolist()}
        clock = updated
    return {'status': 'CLOCK_NOT_CONVERGED', 'clock_closure_m': closure}


def fit_offsets(rows):
    columns = sorted({r['reference'] for r in rows})
    if len(columns) < 2:
        return {'status': 'TRAINING_NOT_IDENTIFIABLE', 'coefficients_m': {}}
    x, missing = design(rows, 'shared_satellite', columns)
    y = center_blocks([r['residual_m'] for r in rows], rows)
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    rank = int(np.sum(singular > singular[0]*1e-12)) if singular[0] else 0
    if missing.any() or rank != len(columns)-1:
        return {'status': 'TRAINING_NOT_IDENTIFIABLE', 'rank': rank, 'reference_count': len(columns), 'coefficients_m': {}}
    beta = vt[:rank].T@((u[:, :rank].T@y)/singular[:rank])
    beta -= beta.mean()
    return {'status': 'FITTED', 'rank': rank, 'reference_count': len(columns),
            'training_path_count': len(rows), 'coefficients_m': dict(zip(columns, map(float, beta)))}


def environment(context):
    plan, original, ctx, observations, positions, receipt, report = context
    precise, corrections, hashes = day.frame.guarded_products(ctx, original['references'], day.INPUTS/'timed',
        BASE/'inputs/reference_biases/g12', BASE/'inputs/reference_antennas/g12')
    attitude, ah = day.frame.load_attitude(day.INPUTS/'attitude', ctx, original['references'])
    provider = day.frame.AttitudeReference(precise, attitude)
    if hashes | ah != report['product_sha256']:
        raise ValueError('reference products differ from baseline')
    weather = day.atmosphere.meteo.WeatherGrid(day.atmosphere.meteo.read_inputs()[0])
    mjd = (datetime.fromisoformat(ctx.date_gpst)-datetime(1858, 11, 17)).days
    codes = {(s, e['time_s']): e['if_code_m'] for s in original['stations']
             for e in day.frame.translate_observations(observations[s], corrections, ctx.target)}
    coordinates = {(s, t): np.array(positions[s][i]) for s in original['stations'] for i, t in enumerate(ctx.times)}
    # Caching only identical evaluations; every changed clock is evaluated anew.
    @lru_cache(maxsize=100000)
    def model(station, time, sv, code, clock):
        if sv == ctx.target or sv not in original['references']:
            raise ValueError('unadmitted model reference')
        xyz = coordinates[(station, time)]
        value, _ = provider.model(sv, code, time, xyz, clock)
        delays, _ = day.atmosphere.components(provider, weather, mjd, sv, code, time, xyz, clock)
        return value-delays['legacy_baseline']+delays['vmf3_full']
    return codes, model


def evaluate(context, codes, model, progress=None):
    plan, original, ctx, _, _, receipt, report = context
    rows_by_block = {(s, t): [report['rows'][i] for i in ix] for (s, t), ix in groups(report['rows']).items()}
    refs_by_block = {key: tuple(sorted(r['reference'] for r in rows)) for key, rows in rows_by_block.items()}
    zero = {sv: 0. for sv in original['references']}
    @lru_cache(maxsize=None)
    def calibrate(s, t, excluded, corrections):
        refs = tuple(sv for sv in refs_by_block[(s, t)] if sv != excluded)
        return receiver_clock(codes[(s, t)], refs, excluded,
            lambda sv, code, clock: model(s, t, sv, code, clock), dict(corrections), plan)
    training_times = [t for t in ctx.times if t < original['training_before_gpst_s']]
    test_times = [t for t in ctx.times if t >= original['training_before_gpst_s']]
    outputs, fits = [], []
    for excluded in original['references']:
        training, failures = [], []
        for s in original['stations']:
            for t in training_times:
                try:
                    cal = calibrate(s, t, excluded, tuple(zero.items()))
                except Exception as error:
                    cal = {'status': 'MODEL_FAILURE', 'reason': str(error)}
                if cal['status'] != 'EVALUATED':
                    failures.append({'station': s, 'time_s': t, **cal})
                    continue
                refs = [sv for sv in refs_by_block[(s, t)] if sv != excluded]
                training.extend({'station': s, 'time_s': t, 'reference': sv, 'residual_m': residual}
                    for sv, residual in zip(refs, cal['residuals_m'], strict=True))
        fit = fit_offsets(training) if not failures else {'status': 'TRAINING_BLOCK_FAILURE', 'coefficients_m': {}}
        fits.append({'pseudo_target': excluded, **fit, 'failed_blocks': failures})
        for s in original['stations']:
            for t in test_times:
                row = {'pseudo_target': excluded, 'station': s, 'time_s': t, 'models': {}}
                if excluded not in refs_by_block[(s, t)]:
                    row['status'] = 'PSEUDO_TARGET_NOT_ADMITTED'
                    outputs.append(row)
                    continue
                row['status'] = 'ADMITTED'
                for method in plan['models']:
                    beta = zero if method == 'zero' else fit['coefficients_m']
                    if method != 'zero' and fit['status'] != 'FITTED':
                        row['models'][method] = {'status': fit['status']}
                        continue
                    try:
                        cal = dict(calibrate(s, t, excluded, tuple(beta.items())))
                        cal.pop('residuals_m', None)
                        if cal['status'] == 'EVALUATED':
                            # The excluded code/model is accessed only after the receiver clock is fixed.
                            value = codes[(s, t)][excluded]
                            cal['error_m'] = value-model(s, t, excluded, value, cal['clock_m'])-cal['clock_m']
                            if not np.isfinite(cal['error_m']):
                                raise ValueError('nonfinite excluded-code error')
                            baseline = rows_by_block[(s, t)]
                            own = next(r['residual_m'] for r in baseline if r['reference'] == excluded)
                            cal['additive_loo_control_m'] = own-np.mean([r['residual_m'] for r in baseline if r['reference'] != excluded])
                    except Exception as error:
                        cal = {'status': 'MODEL_FAILURE', 'reason': str(error)}
                    row['models'][method] = cal
                outputs.append(row)
        if progress:
            fold = [r for r in outputs if r['pseudo_target'] == excluded]
            progress({'pseudo_target': excluded, 'training': fit['status'],
                'test': {m: dict(Counter(r['models'].get(m, {}).get('status', r['status']) for r in fold)) for m in plan['models']}})
    return {'schema': 'reference-pseudotarget-v1', 'plan': plan,
            'baseline_plan': original, 'input_receipt_sha256': day.RECEIPT_SHA,
            'training_times_s': training_times, 'test_times_s': test_times,
            'fits': fits, 'rows': outputs, 'summary': summarize(outputs, plan),
            'pseudo_target_states_used_only_for_diagnostic_modeling': True,
            'real_target_fit': False, 'real_target_orbit_accessed': False,
            'physical_covariance_qualified': False, 'production_floors_changed': False,
            'scope': 'Exposed reference-only differential RF diagnostic. Pseudo-target absent from clock/offset calibration; its known state is used to evaluate residuals. Not independent positioning.'}


def run(plan_sha, progress=None):
    context = inputs(plan_sha)
    codes, model = environment(context)
    result = evaluate(context, codes, model, progress)
    return result | {'plan_sha256': plan_sha, 'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
