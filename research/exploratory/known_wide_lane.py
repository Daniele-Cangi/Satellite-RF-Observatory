"""Calibrate a scalar MW double difference and score against independent labels."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random

from . import integer_phase_feasibility as phase
from .wide_lane_uncertainty import double_difference, integer_support


def measurement(row):
    mean, halfwidth = row['mean_cycles'], row['halfwidth_cycles']
    if not math.isfinite(mean) or not math.isfinite(halfwidth) or halfwidth < 0:
        raise ValueError('a finite mean and a nonnegative error halfwidth are required')
    return mean, halfwidth


def integer_label(value):
    if type(value) is not int or abs(value) >= 2**53:
        raise ValueError('ambiguity truth must be an integer exactly representable in binary64')
    return value


def bias_interval(anchors):
    """Intersect jointly bounded calibration intervals for one constant DD bias."""
    lower, upper = -math.inf, math.inf
    for anchor in anchors:
        mean, halfwidth = measurement(anchor)
        residual = mean - integer_label(anchor['integer'])
        low = math.nextafter(math.nextafter(residual, -math.inf) - halfwidth, -math.inf)
        high = math.nextafter(math.nextafter(residual, math.inf) + halfwidth, math.inf)
        lower, upper = max(lower, low), min(upper, high)
    if not anchors:
        return {'status': 'UNBOUNDED_BIAS', 'interval_cycles': None}
    if lower > upper:
        return {'status': 'INCONSISTENT_ANCHORS', 'interval_cycles': None}
    return {'status': 'BOUNDED', 'interval_cycles': [lower, upper]}


def check_transfer_bound(bound):
    if bound is not None and (not math.isfinite(bound) or bound < 0):
        raise ValueError('transfer bound must be nonnegative and finite or unknown')


def predict(row, calibration, transfer_bound):
    mean, halfwidth = measurement(row)
    check_transfer_bound(transfer_bound)
    interval = calibration['interval_cycles']
    if interval is None or transfer_bound is None:
        return integer_support(mean, halfwidth, None)
    lo, hi = interval
    center = (lo + hi) / 2
    corrected = mean - center
    radius = math.nextafter(max(center - lo, hi - center), math.inf)
    radius = math.nextafter(radius + transfer_bound, math.inf)
    radius = math.nextafter(radius + math.ulp(corrected), math.inf)
    return integer_support(corrected, halfwidth, radius)


def trial_prediction(row, calibration, bound, *, retain_measurement):
    if 'unavailable_reason' in row:
        reason = row['unavailable_reason']
        if not retain_measurement or not isinstance(reason, str) or not reason.strip():
            raise ValueError('an unavailable trial requires a reason in split qualification')
        if 'mean_cycles' in row or 'halfwidth_cycles' in row:
            raise ValueError('an unavailable trial cannot carry an admitted MW measurement')
        return {'id': row['id'], 'unavailable_reason': reason}
    result = {'id': row['id'], 'calibrated': predict(row, calibration, bound),
              'zero_bias': integer_support(*measurement(row), 0.)}
    if retain_measurement:
        result.update(mean_cycles=row['mean_cycles'], halfwidth_cycles=row['halfwidth_cycles'])
    return result


def predictions(groups, *, retain_measurement=False):
    """Compute decisions with calibration labels only; validation truth is separate."""
    seen = set()
    result = []
    for group in groups:
        anchors = group['anchors']
        trials = group['validation']
        for row in [*anchors, *trials]:
            if row['id'] in seen:
                raise ValueError('calibration and validation observation IDs must be disjoint and unique')
            seen.add(row['id'])
        if any('integer' in row for row in trials):
            raise ValueError('validation labels must be in the separate truth input')
        calibration = bias_interval(anchors)
        bound = group['transfer_bound_cycles']
        check_transfer_bound(bound)
        result.append({
            'id': group['id'], 'calibration': calibration, 'transfer_bound_cycles': bound,
            'anchor_ids': [row['id'] for row in anchors],
            'trials': [trial_prediction(row, calibration, bound, retain_measurement=retain_measurement)
                       for row in trials],
        })
    return result


def transfer_evidence(row, integer, calibration, bound):
    """Compare the held bias interval with a previously declared transfer envelope."""
    held_lo, held_hi = bias_interval([{**row, 'integer': integer}])['interval_cycles']
    result = {'held_bias_interval_cycles': [held_lo, held_hi],
              'status': 'UNQUALIFIED', 'bias_change_interval_cycles': None}
    initial = calibration['interval_cycles']
    if initial is None:
        return result
    delta_lo = math.nextafter(held_lo - initial[1], -math.inf)
    delta_hi = math.nextafter(held_hi - initial[0], math.inf)
    result['bias_change_interval_cycles'] = [delta_lo, delta_hi]
    if bound is not None:
        if delta_lo > bound or delta_hi < -bound:
            result['status'] = 'EXCEEDS_DECLARED_BOUND'
        elif -bound <= delta_lo and delta_hi <= bound:
            result['status'] = 'WITHIN_DECLARED_BOUND'
        else:
            result['status'] = 'INDETERMINATE'
    return result


def score(frozen, truth):
    scheduled = [row for group in frozen for row in group['trials']]
    expected = {row['id'] for row in scheduled if 'unavailable_reason' not in row}
    if not scheduled or expected != truth.keys():
        raise ValueError('truth must label every validation observation with a measurement exactly once')
    results = []
    for group in frozen:
        counts = {model: Counter() for model in ('calibrated', 'zero_bias')}
        transfer_counts = Counter()
        rows = []
        for row in group['trials']:
            if 'unavailable_reason' in row:
                for count in counts.values():
                    count['UNAVAILABLE'] += 1
                rows.append(dict(row))
                continue
            label = truth[row['id']]
            integer = None if label is None and 'mean_cycles' in row else integer_label(label)
            outcomes = {}
            for model, count in counts.items():
                support = row[model]
                status = support['status']
                if status == 'SINGLETON':
                    if integer is None:
                        status = 'UNLABELLED_SINGLETON'
                    else:
                        status = 'CORRECT_FIX' if support['range'][0] == integer else 'WRONG_FIX'
                count[status] += 1
                bounds = support['range']
                outcomes[model] = {
                    'status': status,
                    'contains_truth': None if integer is None or status == 'UNBOUNDED_BIAS' else bool(
                        bounds and bounds[0] <= integer <= bounds[1]
                    ),
                }
            if 'mean_cycles' in row:
                if integer is None:
                    transfer_counts['UNLABELLED'] += 1
                else:
                    transfer = transfer_evidence(row, integer, group['calibration'],
                                                 group['transfer_bound_cycles'])
                    outcomes['transfer'] = transfer
                    transfer_counts[transfer['status']] += 1
            rows.append({'id': row['id'], 'integer': integer, **outcomes})
        group_result = {'id': group['id'], 'counts': counts, 'trials': rows}
        if transfer_counts:
            group_result['transfer_counts'] = transfer_counts
        results.append(group_result)
    return results


def synthetic_trial(rng, identifier, bias, noise_halfwidth):
    """Forward raw GPS code/phase with separately generated integer truth."""
    f1, f2 = phase.combo.F1_HZ, phase.combo.F2_HZ
    c = phase.combo.C
    wavelength = c / (f1 - f2)
    integers = [(rng.randint(-40, 40), rng.randint(-40, 40)) for _ in range(4)]
    expected = sum(sign * (n1 - n2) for sign, (n1, n2) in
                   zip((1, -1, -1, 1), integers, strict=True))
    samples = []
    for _ in range(10):
        endpoints = []
        for i, (n1, n2) in enumerate(integers):
            delay = rng.uniform(20e6, 26e6)
            iono1 = rng.uniform(1., 15.)
            iono2 = iono1 * (f1 / f2)**2
            # One nonseparable code delay; other endpoint ranges and ionosphere cancel.
            shift = -wavelength * (bias + rng.uniform(-noise_halfwidth, noise_halfwidth)) if i == 0 else 0.
            fields = (delay + iono1 + shift, delay + iono2 + shift,
                      (delay - iono1) * f1 / c + n1, (delay - iono2) * f2 / c + n2)
            endpoints.append({'mw_cycles': phase.wide_lane(fields)})
        samples.append(double_difference(endpoints))
    # 1e-6 cycles covers rounding of the forward and reverse range arithmetic.
    return {'id': identifier, 'mean_cycles': math.fsum(samples) / len(samples),
            'halfwidth_cycles': noise_halfwidth + 1e-6}, expected


def synthetic():
    """Controlled cases specified independently of the measured MW values."""
    scenarios = (
        ('stable', .98, .03, .04),
        ('broad_transfer', .98, .03, 1.10),
        ('unknown_transfer', .98, .03, None),
        ('unmodelled_drift', 1.98, .03, .04),
        ('contradictory_calibration', .98, .03, .04),
        ('no_anchor', .98, .03, .04),
    )
    groups, truth = [], {}
    for index, (name, bias, noise, transfer) in enumerate(scenarios):
        anchor_rng = random.Random(2026111200 + index)
        validation_rng = random.Random(2026111300 + index)
        anchors, trials = [], []
        for number in range(0 if name == 'no_anchor' else 4):
            anchor_bias = 1.95 if name == 'contradictory_calibration' and number == 0 else .95
            row, label = synthetic_trial(anchor_rng, f'{name}-cal-{number}', anchor_bias, .02)
            anchors.append({**row, 'integer': label})
        for number in range(64):
            row, label = synthetic_trial(validation_rng, f'{name}-held-{number}', bias, noise)
            trials.append(row)
            truth[row['id']] = label
        groups.append({'id': name, 'anchors': anchors, 'transfer_bound_cycles': transfer,
                       'validation': trials})
    return groups, truth


def write(path, payload):
    raw = (json.dumps(payload, indent=2, allow_nan=False, sort_keys=True) + '\n').encode('utf-8')
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def assess(prediction_file, expected_sha, truth_file):
    raw = prediction_file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('predictions do not match the recorded SHA-256')
    frozen = json.loads(raw, object_pairs_hook=unique_keys)
    if frozen.get('schema') != 'wide-lane-held-predictions-v1':
        raise ValueError('split qualification predictions required')
    raw_truth = truth_file.read_bytes()
    truth = json.loads(raw_truth, object_pairs_hook=unique_keys)
    return {
        'evidence': frozen['evidence'], 'predictions_sha256': expected_sha,
        'truth_sha256': hashlib.sha256(raw_truth).hexdigest(),
        'groups': score(frozen['groups'], truth),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--measurements', type=Path, help='calibration and validation measurements as JSON')
    parser.add_argument('--truth', type=Path, help='separate validation integer labels as JSON')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--prepare-only', action='store_true', help='record held decisions without accessing truth')
    modes.add_argument('--score-predictions', type=Path, help='score an existing split qualification prediction file')
    parser.add_argument('--expected-predictions-sha256', help='prediction digest recorded before receiving truth')
    parser.add_argument('--output', type=Path, required=True, help='fresh result directory')
    args = parser.parse_args()
    if args.score_predictions is not None:
        if args.measurements is not None or args.truth is None or not args.expected_predictions_sha256:
            parser.error('scoring requires --truth and the recorded prediction SHA-256')
        result = assess(args.score_predictions, args.expected_predictions_sha256, args.truth)
        args.output.mkdir(parents=True, exist_ok=False)
        write(args.output / 'scores.json', result)
        return
    if args.expected_predictions_sha256:
        parser.error('the expected prediction digest is only used for split scoring')
    if args.prepare_only:
        if args.measurements is None or args.truth is not None:
            parser.error('preparation requires --measurements and forbids --truth')
    elif (args.measurements is None) != (args.truth is None):
        parser.error('provide both input files or omit both for the synthetic exercise')
    if args.measurements is None:
        groups, synthetic_truth = synthetic()
        evidence = 'synthetic'
        measurement_sha = None
    else:
        raw = args.measurements.read_bytes()
        groups = json.loads(raw, object_pairs_hook=unique_keys)
        evidence = 'caller_supplied'
        measurement_sha = hashlib.sha256(raw).hexdigest()
    frozen = predictions(groups, retain_measurement=args.prepare_only)
    if args.prepare_only and not any(group['trials'] for group in frozen):
        parser.error('preparation requires at least one scheduled validation trial')
    args.output.mkdir(parents=True, exist_ok=False)
    payload = {'evidence': evidence, 'measurements_sha256': measurement_sha, 'groups': frozen}
    if args.prepare_only:
        payload['schema'] = 'wide-lane-held-predictions-v1'
    prediction_sha = write(args.output / 'predictions.json', payload)
    if args.prepare_only:
        print(prediction_sha)
        return
    if args.truth is None:
        truth, truth_sha = synthetic_truth, None
    else:
        raw = args.truth.read_bytes()
        truth, truth_sha = json.loads(raw, object_pairs_hook=unique_keys), hashlib.sha256(raw).hexdigest()
    scored = score(frozen, truth)
    write(args.output / 'scores.json', {
        'evidence': evidence, 'predictions_sha256': prediction_sha,
        'truth_sha256': truth_sha, 'groups': scored,
    })
    for group in scored:
        print(group['id'], json.dumps(group['counts'], sort_keys=True))


if __name__ == '__main__':
    main()
