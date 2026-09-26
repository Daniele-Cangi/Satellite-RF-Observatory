"""Reference-only phase clock increments on the exposed September 5 cohort.

The original excluded G12 never enters the model, mask or calibration. Each
admitted reference is also left out of its own diagnostic prediction. This
measures a relative phase-clock error, not an absolute receiver-clock bound.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from functools import lru_cache
import hashlib
import json
from pathlib import Path

import numpy as np

from . import day_reference as day
from . import pseudotarget_reference as pseudo
from .real_phase import BASE, digest, moments
from .pseudotarget_checked_v2 import PLAN_SHA


def clock_rate(rows, *, excluded, estimator='mean', minimum_references=4):
    """Discard excluded row before any numeric access, with no replacement."""
    if estimator not in {'mean', 'median'}:
        raise ValueError('unknown reference clock estimator')
    admitted = [row for row in rows if row['reference'] != excluded]
    labels = [row['reference'] for row in admitted]
    if len(labels) < minimum_references:
        return {'status': 'INSUFFICIENT_REFERENCES', 'reference_count': len(labels)}
    if len(labels) != len(set(labels)):
        return {'status': 'DUPLICATE_REFERENCE', 'reference_count': len(labels)}
    values = np.array([float(row['phase_minus_model_rate_m_s']) for row in admitted])
    if not np.isfinite(values).all():
        return {'status': 'INVALID_REFERENCE_RATE', 'reference_count': len(labels)}
    estimate = float(np.mean(values) if estimator == 'mean' else np.median(values))
    return {'status': 'ESTIMATED', 'rate_m_s': estimate, 'estimator': estimator,
            'reference_count': len(labels),
            'reference_spread_rms_m_s': float(np.sqrt(np.mean((values-estimate)**2)))}


def model_environment(context):
    """The earlier precise reference chain, retaining elevation for admission."""
    _, original, ctx, observations, positions, _, report = context
    precise, corrections, hashes = day.frame.guarded_products(
        ctx, original['references'], day.INPUTS/'timed',
        BASE/'inputs/reference_biases/g12', BASE/'inputs/reference_antennas/g12')
    attitude, attitude_hashes = day.frame.load_attitude(
        day.INPUTS/'attitude', ctx, original['references'])
    if hashes | attitude_hashes != report['product_sha256']:
        raise ValueError('reference products changed')
    provider = day.frame.AttitudeReference(precise, attitude)
    weather = day.atmosphere.meteo.WeatherGrid(day.atmosphere.meteo.read_inputs()[0])
    mjd = (datetime.fromisoformat(ctx.date_gpst)-datetime(1858, 11, 17)).days
    codes = {(station, epoch['time_s']): epoch['if_code_m']
             for station in original['stations']
             for epoch in day.frame.translate_observations(
                 observations[station], corrections, ctx.target)}
    coordinates = {(station, t): np.asarray(positions[station][i])
                   for station in original['stations'] for i, t in enumerate(ctx.times)}

    @lru_cache(maxsize=100000)
    def model(station, t, reference):
        if reference == ctx.target or reference not in original['references']:
            raise ValueError('target or unknown reference at model boundary')
        code = codes[(station, t)][reference]
        xyz = coordinates[(station, t)]
        geometric, elevation = provider.model(reference, code, t, xyz, 0.)
        delays, _ = day.atmosphere.components(
            provider, weather, mjd, reference, code, t, xyz, 0.)
        return geometric-delays['legacy_baseline']+delays['vmf3_full'], elevation

    return model


def run():
    context = pseudo.inputs(PLAN_SHA)
    _, original, ctx, _, _, receipt, baseline = context
    source = (BASE/'inputs/real_phase/observations.json').read_bytes()
    phase = json.loads(source)['cohorts']['day']
    if (phase['plan'] != original or phase['receipt_sha256'] != baseline['receipt_sha256']
            or ctx.target != 'G12' or phase['plan']['target_excluded'] in phase['plan']['references']):
        raise ValueError('reference-only cohort differs from baseline')
    model = model_environment(context)
    blocks, failures, stations, model_failures = defaultdict(list), Counter(), {}, []
    for station in original['stations']:
        item = phase['stations'][station]
        if item['status'] != 'PARSED':
            stations[station] = {'status': item['status'], 'reason': item['reason']}
            failures['UNSUPPORTED_STATION'] += 1
            continue
        levels = {}
        for row in item['rows']:
            reference = row['reference']
            if reference == ctx.target or reference not in original['references']:
                raise ValueError('target/unadmitted numeric phase in reference extract')
            if row['status'] != 'AVAILABLE':
                failures['REJECTED_OBSERVATION'] += 1
                continue
            t = row['time_s']
            try:
                predicted, elevation = model(station, t, reference)
                if elevation < original['minimum_elevation_deg']:
                    failures['BELOW_ELEVATION_MASK'] += 1
                    continue
                levels[t, reference] = row['phase_m']-predicted
            except (KeyError, ValueError) as error:
                failures['REFERENCE_MODEL_FAILURE'] += 1
                model_failures.append({'station': station, 'time_s': t,
                                       'reference': reference, 'reason': str(error)})
                continue
        for (t, reference), value in levels.items():
            if t <= original['training_before_gpst_s'] or (t-original['start_gpst_s']) % original['step_s']:
                continue
            if (t-original['step_s'], reference) not in levels:
                failures['UNBRIDGED_REFERENCE_INTERVAL'] += 1
                continue
            rate = (value-levels[t-original['step_s'], reference])/original['step_s']
            blocks[station, t].append({'reference': reference,
                                       'phase_minus_model_rate_m_s': rate})
        stations[station] = {'status': 'EVALUATED', 'levels': len(levels),
                             'intervals': sum(len(rows) for (s, _), rows in blocks.items() if s == station)}
    leave_out, full_clock = [], []
    for (station, t), rows in sorted(blocks.items()):
        all_refs = {method: clock_rate(rows, excluded=ctx.target, estimator=method)
                    for method in ('mean', 'median')}
        full_clock.append({'station': station, 'time_s': t,
                           'reference_count': len(rows), 'estimators': all_refs})
        for held in rows:
            estimates = {method: clock_rate(rows, excluded=held['reference'], estimator=method)
                         for method in ('mean', 'median')}
            row = {'station': station, 'time_s': t, 'reference': held['reference'],
                   'status': estimates['mean']['status'],
                   'other_reference_count': estimates['mean']['reference_count']}
            if row['status'] == 'ESTIMATED':
                row['phase_minus_model_rate_m_s'] = held['phase_minus_model_rate_m_s']
                for method, estimate in estimates.items():
                    row['error_m_s_'+method] = held['phase_minus_model_rate_m_s']-estimate['rate_m_s']
                    row['other_reference_rate_m_s_'+method] = estimate['rate_m_s']
            else:
                failures['HELD_OUT_'+row['status']] += 1
            leave_out.append(row)
    summary = {'held_out': {method: moments([r['error_m_s_'+method] for r in leave_out
                                            if r['status'] == 'ESTIMATED'])
                            for method in ('mean', 'median')},
               'per_station': {s: {method: moments([r['error_m_s_'+method] for r in leave_out
                                                   if r['station'] == s and r['status'] == 'ESTIMATED'])
                                   for method in ('mean', 'median')}
                               for s in original['stations']},
               'unqualified_blocks': sum(r['estimators']['mean']['status'] != 'ESTIMATED' for r in full_clock),
               'held_out_count': len(leave_out)}
    return {'schema': 'reference-phase-clock-v1', 'scope': 'Exposed references only; precision products, atmosphere and phase header interpretation remain conditional. Held-out references use independently computed elevation, but share upstream products. No absolute clock or total covariance bound.',
            'target_excluded': ctx.target, 'target_values_accessed': False,
            'input_sha256': digest(source), 'baseline_report_sha256': digest((BASE/'results/day_reference_v1.json').read_bytes()),
            'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'stations': stations, 'failures': dict(failures),
            'model_failures': model_failures, 'summary': summary,
            'phase_clock_rates': full_clock, 'held_out_reference_diagnostics': leave_out}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n',
                           encoding='utf-8', newline='\n')
    print(json.dumps(result['summary']), flush=True)
