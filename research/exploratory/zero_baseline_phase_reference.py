"""A conditional wide-lane reference from shared-antenna carrier phase."""

import argparse
from collections import Counter
import hashlib
from itertools import combinations
import math
from pathlib import Path
from statistics import median

from ..kinematic.receiver_time import C
from .integer_phase_feasibility import MW_FIELD_ROW
from .known_wide_lane import write
from .real_phase import parse_reference_fields
from .wide_lane_uncertainty import integer_support
from .zero_baseline_dd_code import DATASET, HOURS, REFERENCES, STATIONS, WINDOW_S

# Sensitivity assumption per carrier in DD cycles, not a measured hardware bound.
PHASE_BOUND = .10
ANCHOR_S = 60
MW_STEP_S = 30
SIGNS = (1, -1, -1, 1)


def phase_label(samples):
    """Intersect the constant per-band integer implied by all phase samples."""
    integers = []
    for band in zip(*samples, strict=True):
        low, high = min(band), max(band)
        # The two extremes give the tightest intersection.
        lower = integer_support(high, PHASE_BOUND, 0.)['range']
        upper = integer_support(low, PHASE_BOUND, 0.)['range']
        if lower is None or upper is None or lower[0] != upper[0]:
            return None
        integers.append(lower[0])
    return integers


def read_window(cache, station, hour):
    name = f'{station}_R_2024068{hour:02d}00_01H_01S_MO.rnx.prefix'
    raw = (cache / name).read_bytes()
    plan = {'date_gpst': '2024-03-08', 'start_gpst_s': hour * 3600, 'samples': WINDOW_S,
            'step_s': 1, 'references': REFERENCES, 'target_excluded': 'G12'}
    parsed = parse_reference_fields(raw.decode('ascii'), plan)
    expected = {'default_cycles': 0., 'satellite_overrides_cycles': {}}
    if any(parsed['phase_shifts'].get(band) != expected
           for band in ('L1C', 'L2W')):
        raise ValueError(f'{name}: phase-shift convention differs')
    rows = {(row['reference'], row['time_s']): row for row in parsed['rows']}
    source = {'name': name, 'sha256': hashlib.sha256(raw).hexdigest(),
              'receiver': parsed['receiver']}
    return source, rows


def endpoints(left, right, pair, t):
    q, p = pair
    return (left.get((q, t)), right.get((q, t)), left.get((p, t)), right.get((p, t)))


def phase_observation(rows):
    if any(row is None or any(reason.startswith(('LOSS_OF_LOCK_', 'MISSING_INVALID_L'))
                             for reason in row['reasons']) for row in rows):
        return None
    return [math.fsum(sign * row['fields'][i] for sign, row in zip(SIGNS, rows, strict=True))
            for i in (2, 3)]


def code_observation(rows):
    fields = [row['fields'][:2] for row in rows]
    if any(value is None or value <= 0 for pair in fields for value in pair):
        return None
    return math.fsum(float(weight) * math.fsum(sign * row[i]
                     for sign, row in zip(SIGNS, fields, strict=True))
                     for i, weight in enumerate(MW_FIELD_ROW[:2]))


def clock_proxy(left, right):
    """Other-satellite C1C single differences in seconds, before DD."""
    offsets = {}
    for sv, time in sorted(left.keys() & right.keys()):
        a, b = (rows[sv, time]['fields'][0] for rows in (left, right))
        if a is not None and b is not None and a > 0. and b > 0.:
            offsets.setdefault(time, {})[sv] = (a - b) / C
    return offsets


def align(phases, epochs, pair, start, offsets, sign):
    """Move left phase to right reception epoch using between-satellite phase rate."""
    aligned = []
    for i in range(1, len(epochs) - 1):
        other = [value for sv, value in offsets.get(start + i, {}).items() if sv not in pair]
        if len(other) < 3:
            return None
        delay = sign * median(other)
        before, after = epochs[i - 1], epochs[i + 1]
        rates = [math.fsum((after[0]['fields'][band], -after[2]['fields'][band],
                           -before[0]['fields'][band], before[2]['fields'][band])) / 2
                 for band in (2, 3)]
        aligned.append([phase + delay * rate for phase, rate in zip(phases[i], rates, strict=True)])
    return aligned


def evaluate(pair, start, left, right, *, offsets=None, sign=1):
    result = {'pair': pair}
    epochs = [endpoints(left, right, pair, t) for t in range(start, start + WINDOW_S)]
    phases = [phase_observation(rows) for rows in epochs]
    missing_prefix = phases[:ANCHOR_S].count(None)
    missing_held = phases[ANCHOR_S:].count(None)
    if missing_prefix or missing_held:
        return {**result, 'status': 'PHASE_GAP_OR_FLAG', 'prefix_unavailable_epochs': missing_prefix,
                'held_unavailable_epochs': missing_held}
    if offsets is None:
        prefix, held = phases[:ANCHOR_S], phases[ANCHOR_S:]
    else:
        aligned = align(phases, epochs, pair, start, offsets, sign)
        if aligned is None:
            return {**result, 'status': 'CLOCK_PROXY_UNAVAILABLE'}
        # Drop edge epochs; central differences never cross the split for the anchor.
        prefix, held = aligned[:ANCHOR_S - 2], aligned[ANCHOR_S - 1:]
    anchor = phase_label(prefix)
    if anchor is None:
        return {**result, 'status': 'NO_ANCHOR_SINGLETON'}
    if phase_label(held) != anchor:
        return {**result, 'status': 'HELD_PHASE_INCONSISTENT', 'anchor_cycles': anchor}
    integer = anchor[0] - anchor[1]
    times = range(start + ANCHOR_S, start + WINDOW_S, MW_STEP_S)
    code = [code_observation(endpoints(left, right, pair, t)) for t in times]
    if any(value is None for value in code):
        return {**result, 'status': 'HELD_CODE_UNAVAILABLE', 'anchor_cycles': anchor}
    observed = [sample[0] - sample[1] + term for sample, term in
                zip(phases[ANCHOR_S::MW_STEP_S], code, strict=True)]
    mean = math.fsum(observed) / len(observed)
    phase_rates = [abs(math.fsum((after[0]['fields'][band], -after[2]['fields'][band],
                                 -before[0]['fields'][band], before[2]['fields'][band])))
                   for before, after in zip(epochs, epochs[1:]) for band in (2, 3)]
    return {
        **result, 'status': 'SCORED', 'anchor_cycles': anchor, 'conditional_integer': integer,
        'max_abs_aligned_phase_residual_cycles': max(abs(sample[i] - anchor[i])
                                             for sample in (*prefix, *held) for i in (0, 1)),
        'max_abs_aligned_phase_wl_residual_cycles': max(abs(sample[0] - sample[1] - integer)
                                                for sample in (*prefix, *held)),
        'max_left_phase_rate_cycles_per_s': max(phase_rates),
        'held_code_mean_cycles': math.fsum(code) / len(code),
        'held_mw_bias_cycles': mean - integer,
        'held_mw_nearest_integer': round(mean),
    }


def summarize(rows):
    scored = [row for row in rows if row['status'] == 'SCORED']
    return {
        'status_counts': Counter(row['status'] for row in rows),
        'nearest_disagreements': sum(row['held_mw_nearest_integer'] != row['conditional_integer']
                                     for row in scored),
        'above_point_one': sum(abs(row['held_mw_bias_cycles']) > .1 for row in scored),
        'max_abs_bias_cycles': max((abs(row['held_mw_bias_cycles']) for row in scored), default=None),
        'max_abs_aligned_phase_residual_cycles': max(
            (row['max_abs_aligned_phase_residual_cycles'] for row in scored), default=None),
    }


def run(cache, output):
    windows = []
    for hour in HOURS:
        left_source, left = read_window(cache, STATIONS[0], hour)
        right_source, right = read_window(cache, STATIONS[1], hour)
        offsets = clock_proxy(left, right)
        pairs = list(combinations(REFERENCES, 2))
        start = hour * 3600
        rows = [evaluate(pair, start, left, right, offsets=offsets) for pair in pairs]
        control = [evaluate(pair, start, left, right) for pair in pairs]
        reversed_sign = [evaluate(pair, start, left, right, offsets=offsets, sign=-1)
                         for pair in pairs]
        windows.append({'hour_gpst': hour, 'sources': [left_source, right_source],
                        'summary': summarize(rows), 'unadjusted_summary': summarize(control),
                        'reversed_sign_summary': summarize(reversed_sign), 'rows': rows,
                        'unadjusted_rows': control, 'reversed_sign_rows': reversed_sign})
    early, late = [{row['pair']: row['held_mw_bias_cycles'] for row in window['rows']
                    if row['status'] == 'SCORED'} for window in windows]
    transfers = [{'pair': pair, 'delta_cycles': late[pair] - early[pair]}
                 for pair in sorted(early.keys() & late.keys())]
    distances = [abs(row['delta_cycles']) for row in transfers]
    result = {'dataset': DATASET, 'phase_bound_cycles': PHASE_BOUND, 'window_seconds': WINDOW_S,
              'anchor_seconds': ANCHOR_S, 'mw_step_seconds': MW_STEP_S, 'windows': windows,
              'transfer': {'rows': transfers, 'above_point_one': sum(x > .1 for x in distances),
                           'median_abs_cycles': median(distances) if distances else None,
                           'max_abs_cycles': max(distances, default=None)}}
    write(output, result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True, help='WUT RINEX window prefixes')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a fresh file')
    result = run(args.cache, args.output)
    for window in result['windows']:
        print(window['hour_gpst'], window['summary'])
    print('Between windows', result['transfer'])
