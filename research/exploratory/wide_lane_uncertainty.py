"""Exploratory uncertainty sensitivity for scalar wide-lane ambiguities."""

from collections import Counter
import gzip
import hashlib
from itertools import combinations
import json
import math
import subprocess

import numpy as np
from scipy.stats import t as student_t

from . import integer_phase_feasibility as base
from . import reference_mw_stability as stability

LEDGER = base.ROOT / 'research/exploratory/reference-arc-tracking-2026-11-11/decisions.json.gz'
LEDGER_SHA256 = 'b8014918a1964281c1d90d536927cab838a36bf0331b3362405b806edbf9417e'
MODELS = {'iid': 0., 'ar1_rho_0.5': .5}
BIAS_SCENARIOS = (0., .1, .25, .5)


def integer_support(mean, halfwidth, bias_bound):
    """Intersect the error interval enlarged by a bias bound with the integers."""
    if not math.isfinite(mean) or not math.isfinite(halfwidth) or halfwidth < 0.:
        raise ValueError('finite mean and nonnegative halfwidth required')
    if bias_bound is None:
        return {'status': 'UNBOUNDED_BIAS', 'count': None, 'range': None}
    if not math.isfinite(bias_bound) or bias_bound < 0.:
        raise ValueError('finite nonnegative bias bound required')
    # Include boundary integers even when the radius or an endpoint rounds inwards.
    radius = math.nextafter(halfwidth + bias_bound, math.inf)
    first = math.ceil(math.nextafter(mean - radius, -math.inf))
    last = math.floor(math.nextafter(mean + radius, math.inf))
    count = max(0, last - first + 1)
    return {'status': 'EMPTY' if count == 0 else 'SINGLETON' if count == 1 else 'MULTIPLE',
            'count': count, 'range': [first, last] if count else None}


def fit_model(blocks, held_starts, rho):
    """GLS with known correlation shape and unknown mean and variance scale."""
    starts = np.array([row['start_s'] for row in blocks])
    y = np.array([row['mean_cycles'] for row in blocks])
    lag = np.abs(starts[:, None] - starts) / stability.BLOCK_S
    correlation = rho ** lag
    ones = np.ones(len(y))
    inv_ones = np.linalg.solve(correlation, ones)
    mean_information = float(ones @ inv_ones)
    mean = float(inv_ones @ y / mean_information)
    residual = y - mean
    inv_residual = np.linalg.solve(correlation, residual)
    dof = len(y) - 1
    variance = float(residual @ inv_residual / dof)
    mean_se = math.sqrt(variance / mean_information)
    mean_halfwidth = float(student_t.ppf(.995, dof) * mean_se)

    forecasts = []
    for start in held_starts:
        cross = rho ** (np.abs(start - starts) / stability.BLOCK_S)
        inv_cross = np.linalg.solve(correlation, cross)
        prediction_variance_factor = (
            1. - cross @ inv_cross + (1. - cross @ inv_ones)**2 / mean_information
        )
        forecasts.append({
            'start_s': start,
            'mean_cycles': float(mean + cross @ inv_residual),
            'halfwidth_95_cycles': float(student_t.ppf(.975, dof)
                                         * math.sqrt(variance * prediction_variance_factor)),
        })

    return {'rho_per_300_s': rho, 'dof': dof, 'mean_cycles': mean,
            'scale_cycles': math.sqrt(variance), 'mean_se_cycles': mean_se,
            'mean_halfwidth_99_cycles': mean_halfwidth,
            'physical_integer_support': integer_support(mean, mean_halfwidth, None),
            'assumed_bias_support': [
                {'bias_bound_cycles': bound, **integer_support(mean, mean_halfwidth, bound)}
                for bound in BIAS_SCENARIOS
            ], 'forecasts': forecasts}


def index_decisions(decisions, plan, *, before_s=None):
    stations = set(plan['stations'])
    references = set(plan['references'])
    if 'G12' in references or plan['target_excluded'] in references:
        raise ValueError('target in reference allowlist')
    index = {}
    for row in decisions:
        if row['station'] not in stations or row['reference'] not in references:
            raise ValueError('unadmitted link in decision ledger')
        time = row['time_s']
        if before_s is not None and time >= before_s:
            continue
        key = (row['station'], row['reference'], time)
        if key in index:
            raise ValueError('duplicate decision epoch')
        index[key] = row
    return index


def endpoints(stations, satellites):
    a, b = stations
    q, p = satellites
    return ((a, q), (b, q), (a, p), (b, p))


def samples(index, links, time):
    return [index.get((*link, time)) for link in links]


def double_difference(rows):
    return math.fsum(sign * row['mw_cycles']
                     for sign, row in zip((1, -1, -1, 1), rows, strict=True))


def prepare(plan, decisions):
    """Fit every DD using only the latest joint arc at the prefix boundary."""
    start = plan['start_gpst_s']
    step = plan['step_s']
    cut = plan['training_before_gpst_s']
    stop = start + (plan['samples'] - 1) * step
    if (step != stability.STEP_S or cut % stability.BLOCK_S
            or not start < cut <= stop or (cut - start) % step):
        raise ValueError('expected a 30 s grid with a 300 s aligned cut')
    index = index_decisions(decisions, plan, before_s=cut)
    held_starts = list(range(int(cut), int(stop - stability.BLOCK_S + step) + 1,
                             int(stability.BLOCK_S)))
    records = []
    for stations in combinations(plan['stations'], 2):
        for satellites in combinations(sorted(plan['references']), 2):
            links = endpoints(stations, satellites)
            rows = samples(index, links, cut - step)
            record = {'stations': stations, 'satellites': satellites}
            records.append(record)
            if any(row is None or row['arc'] is None for row in rows):
                record['status'] = 'NO_JOINT_ARC_AT_CUT'
                continue

            arcs = [row['arc'] for row in rows]
            points = []
            for time in range(int(cut - step), int(start) - 1, -int(step)):
                rows = samples(index, links, time)
                if any(row is None or row['arc'] != arc
                       for row, arc in zip(rows, arcs, strict=True)):
                    break
                points.append((time, double_difference(rows)))
            blocks, partial = stability.complete_blocks(reversed(points))
            support = stability.block_model(blocks)
            record.update(arcs=arcs, prefix_blocks=blocks, partial_prefix_blocks=partial,
                          status=support['status'])
            if support['status'] == 'CONDITIONAL_BLOCK_PREDICTION':
                record['models'] = {name: fit_model(blocks, held_starts, rho)
                                    for name, rho in MODELS.items()}
    return {'schema': 'wide-lane-uncertainty-prefix-v1', 'cut_gpst_s': cut,
            'held_block_starts_s': held_starts,
            'trailing_held_samples_outside_complete_blocks': (
                int((stop - cut) / step) + 1 - len(held_starts) * int(stability.BLOCK_S / step)
            ),
            'records': records, 'integer_fix_admitted': False,
            'physical_uncertainty_qualified': False}


def score_record(record, index, held_starts):
    links = endpoints(record['stations'], record['satellites'])
    arcs = record['arcs']
    loss = None
    scored = []
    for start in held_starts:
        block = {'start_s': start}
        scored.append(block)
        if loss is not None:
            block['status'] = 'AFTER_ARC_LOSS'
            continue
        values = []
        for time in range(start, start + int(stability.BLOCK_S), int(stability.STEP_S)):
            rows = samples(index, links, time)
            for link, row, arc in zip(links, rows, arcs, strict=True):
                if row is None or row['arc'] != arc:
                    loss = {'time_s': time, 'link': link,
                            'decision': 'MISSING_SAMPLE' if row is None else row['status']}
                    break
            if loss is not None:
                block.update(status='ARC_LOST', loss=loss)
                break
            values.append(double_difference(rows))
        if loss is not None:
            continue

        observed = math.fsum(values) / len(values)
        checks = {}
        for name, model in record['models'].items():
            forecast = next(row for row in model['forecasts'] if row['start_s'] == start)
            error = observed - forecast['mean_cycles']
            checks[name] = {'error_cycles': error,
                            'inside_95': abs(error) <= forecast['halfwidth_95_cycles']}
        block.update(status='SCORED', mean_cycles=observed, checks=checks)
    return scored


def score(frozen, decisions, plan):
    index = index_decisions(decisions, plan)
    coverage = {name: Counter() for name in MODELS}
    statuses = Counter()
    by_start = {start: Counter() for start in frozen['held_block_starts_s']}
    records = []
    for record in frozen['records']:
        if 'models' not in record:
            continue
        blocks = score_record(record, index, frozen['held_block_starts_s'])
        records.append({'stations': record['stations'], 'satellites': record['satellites'],
                        'blocks': blocks})
        for block in blocks:
            status = block['status']
            statuses[status] += 1
            by_start[block['start_s']][status] += 1
            for name, check in block.get('checks', {}).items():
                outcome = 'inside' if check['inside_95'] else 'outside'
                coverage[name][outcome] += 1
                by_start[block['start_s']][f'{name}_{outcome}'] += 1
    return {'schema': 'wide-lane-uncertainty-held-v1', 'records': records,
            'block_statuses': dict(statuses), 'coverage': coverage,
            'by_block_start_s': by_start}


def run(reference_path, output):
    if reference_path.resolve() != base.REFERENCE.resolve():
        raise ValueError('use the retained reference-only extract')
    raw = reference_path.read_bytes()
    ledger = LEDGER.read_bytes()
    input_hash = hashlib.sha256(raw).hexdigest()
    ledger_hash = hashlib.sha256(ledger).hexdigest()
    if input_hash != base.EXPECTED[0] or ledger_hash != LEDGER_SHA256:
        raise ValueError('reference input or arc ledger hash mismatch')

    plan = json.loads(raw)['cohorts']['day']['plan']
    replay = json.loads(gzip.decompress(ledger))
    if replay['input_sha256'] != input_hash:
        raise ValueError('arc ledger belongs to a different reference input')
    output.mkdir(exist_ok=False)
    frozen = prepare(plan, replay['decisions'])
    sources = ('research/exploratory/wide_lane_uncertainty.py',
               'research/exploratory/reference_mw_stability.py',
               'research/exploratory/real_phase.py')
    frozen.update(
        input_sha256=input_hash, arc_ledger_sha256=ledger_hash,
        implementation_revision=subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=base.ROOT, text=True).strip(),
        source_sha256={name: hashlib.sha256((base.ROOT / name).read_bytes()).hexdigest()
                       for name in sources},
        prospective_confirmation=False,
    )
    base.write(output / 'predictions-before-scoring.json.gz', frozen)
    scored = score(frozen, replay['decisions'], plan)
    base.write(output / 'scores.json.gz', scored)
    print(json.dumps({'prefix_statuses': Counter(row['status'] for row in frozen['records']),
                      'block_statuses': scored['block_statuses'],
                      'coverage': scored['coverage']}), flush=True)
    return scored
