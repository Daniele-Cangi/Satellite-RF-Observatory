"""Development comparison on original code observations and explicit software ramps."""

from collections import Counter, defaultdict
from itertools import combinations
import math
from statistics import median

import numpy as np

from positioning.calibration import reference_model
from research.exploratory.pnt_local_network import nearest_rank
from .fixed_site import (evaluate_epoch, ionosphere_free, load_inputs,
                         observation_epochs, validate_window)
from .model import nearest_record


MODES = ('local', 'network', 'combined', 'reference_disagreement')
SCENARIOS = ('local_satellite_ramp', 'local_geometry_ramp', 'local_common_clock_ramp',
             'shared_satellite_ramp', 'reference_satellite_ramp')


def pair_values(epoch):
    """All satellite pairs, avoiding dependence on a changing reference PRN."""
    matched = epoch['matched']
    if matched['status'] != 'EVALUATED':
        return {}
    fits = matched['receiver_fits']
    references = sorted(name for name in fits if name != 'local')
    values = {}
    for first, second in combinations(matched['satellites'], 2):
        difference = {name: fit['satellite_residuals_m'][first] - fit['satellite_residuals_m'][second]
                      for name, fit in fits.items()}
        remote = float(np.mean([difference[name] for name in references]))
        values[first + '/' + second] = {
            'local': difference['local'], 'network': remote,
            'combined': difference['local'] - remote,
            'reference_differences': {a + '/' + b: difference[a] - difference[b]
                                      for a, b in combinations(references, 2)}}
    return values


def fit_baselines(epochs, minimum_training):
    grouped = defaultdict(list)
    for epoch in epochs:
        for pair, values in pair_values(epoch).items():
            grouped[pair].append(values)
    return {pair: {'training_count': len(values),
                   'centres_m': {mode: median(value[mode] for value in values) for mode in MODES[:3]},
                   'reference_centres_m': {
                       names: median(value['reference_differences'][names] for value in values)
                       for names in values[0]['reference_differences']}}
            for pair, values in sorted(grouped.items()) if len(values) >= minimum_training}


def score_epoch(epoch, baselines):
    values = pair_values(epoch)
    supported = sorted(set(values) & set(baselines))
    result = {'gpst_s': epoch['gpst_s'], 'status': epoch['matched']['status'],
              'satellites': epoch['matched']['satellites'], 'scored_pairs': supported,
              'unsupported_pair_count': len(values) - len(supported),
              'excluded_satellites': epoch['excluded_satellites'],
              'fit_failures': {name: fit['reason'] for name, fit in epoch['matched']['receiver_fits'].items()
                               if 'reason' in fit}}
    if result['status'] != 'EVALUATED':
        return result
    # Six distinct pairs require at least four satellites. Pair scores remain
    # correlated: one epoch is one decision, never six independent incidents.
    if len(supported) < 6:
        result['status'] = 'INSUFFICIENT_TRAINED_PAIRS'
        return result
    result['scores_m'] = {
        mode: max(abs(values[pair][mode] - baselines[pair]['centres_m'][mode]) for pair in supported)
        for mode in MODES[:3]}
    result['scores_m']['reference_disagreement'] = max(
        abs(value - baselines[pair]['reference_centres_m'][names])
        for pair in supported for names, value in values[pair]['reference_differences'].items())
    fits = epoch['matched']['receiver_fits']
    result['clock_m'] = {name: fit['clock_m'] for name, fit in fits.items()}
    return result


def apply_thresholds(rows, thresholds):
    for row in rows:
        if row['status'] == 'EVALUATED':
            if thresholds is None:
                row['status'] = 'INSUFFICIENT_CALIBRATION'
            else:
                row['exceedances'] = {mode: row['scores_m'][mode] > thresholds[mode] for mode in MODES}


def summarize(rows):
    evaluated = [row for row in rows if 'exceedances' in row]
    return {'requested_epochs': len(rows), 'evaluated_epochs': len(evaluated),
            'status_counts': dict(sorted(Counter(row['status'] for row in rows).items())),
            'exceedances': {mode: sum(row['exceedances'][mode] for row in evaluated) for mode in MODES}}


def perturb(values, scenario, shift_m, satellite, reference, positions, navigation, time_s, context, direction):
    """Modify both raw codes equally; quality flags and tracking are not simulated."""
    changed = {name: dict(codes) for name, codes in values.items()}
    receivers = (list(values) if scenario == 'shared_satellite_ramp' else
                 [reference] if scenario == 'reference_satellite_ramp' else ['local'])
    for name in receivers:
        for sv, codes in values[name].items():
            if scenario.endswith('satellite_ramp') and sv != satellite:
                continue
            delta = shift_m
            if scenario == 'local_geometry_ramp':
                try:
                    record = nearest_record(navigation, sv, time_s, context)
                except ValueError:
                    continue  # Original evaluation retains the unusable NAV exclusion.
                code = ionosphere_free({sv: codes})[sv]
                original = reference_model(record, code, time_s, positions[name], 0., context)[0]
                displaced = reference_model(record, code, time_s,
                                            positions[name] + shift_m * direction, 0., context)[0]
                delta = displaced - original
            changed[name][sv] = tuple(value + delta for value in codes)
    return changed


def compare(local_path, references, navigation_path, day_gpst, *, start_s, train_stop_s,
            calibration_stop_s, stop_s, amplitudes_m=(2., 5., 10.), proportion=.95,
            minimum_training=5, minimum_calibration=20, direction_ecef=(1., 0., 0.),
            satellite=None, local_ecef=None, position_source=None):
    for first, second in ((start_s, train_stop_s), (train_stop_s, calibration_stop_s),
                          (calibration_stop_s, stop_s)):
        validate_window(first, second)
    if stop_s - calibration_stop_s < 60:
        raise ValueError('evaluation requires at least two epochs for a ramp')
    if (not 0 < proportion < 1 or
            any(not isinstance(n, int) or isinstance(n, bool) or n < 1
                for n in (minimum_training, minimum_calibration))):
        raise ValueError('invalid calibration proportion or minimum sample counts')
    amplitudes = list(amplitudes_m)
    if not amplitudes or any(not math.isfinite(value) or value <= 0 for value in amplitudes):
        raise ValueError('positive finite perturbation amplitudes required')
    if len(set(amplitudes)) != len(amplitudes):
        raise ValueError('duplicate perturbation amplitudes')
    direction = np.array(direction_ecef, dtype=float, copy=True)
    norm = np.linalg.norm(direction)
    if direction.shape != (3,) or not np.isfinite(direction).all() or not math.isfinite(norm) or norm == 0:
        raise ValueError('finite nonzero ECEF displacement direction required')
    direction /= norm
    if satellite is not None and satellite not in {f'G{prn:02d}' for prn in range(1, 33)}:
        raise ValueError('expected GPS perturbation satellite G01..G32')
    data, positions, navigation, context, sources = load_inputs(
        local_path, references, navigation_path, day_gpst,
        local_ecef=local_ecef, position_source=position_source)
    inputs = list(observation_epochs(data, start_s, stop_s))
    epochs = [evaluate_epoch(time_s, values, positions, navigation, context) for time_s, values in inputs]
    training = [epoch for epoch in epochs if epoch['gpst_s'] < train_stop_s]
    baselines = fit_baselines(training, minimum_training)
    if satellite is None:
        counts = Counter(sv for epoch in training if epoch['matched']['status'] == 'EVALUATED'
                         for sv in epoch['matched']['satellites'])
        satellite = min(counts, key=lambda sv: (-counts[sv], sv)) if counts else None
    original = [score_epoch(epoch, baselines) for epoch in epochs]
    calibration = [row for row in original if train_stop_s <= row['gpst_s'] < calibration_stop_s]
    eligible = [row for row in calibration if row['status'] == 'EVALUATED']
    thresholds = ({mode: nearest_rank([row['scores_m'][mode] for row in eligible], proportion)
                   for mode in MODES} if len(eligible) >= minimum_calibration else None)
    apply_thresholds(original, thresholds)
    testing = [row for row in original if row['gpst_s'] >= calibration_stop_s]
    original_by_time = {row['gpst_s']: row for row in testing}
    cases = []
    if thresholds is not None:
        reference = min(references)
        for amplitude in amplitudes:
            for scenario in SCENARIOS:
                rows = []
                for (time_s, values), epoch in zip(inputs, epochs):
                    if time_s < calibration_stop_s:
                        continue
                    base = original_by_time[time_s]
                    shift = amplitude * (time_s - calibration_stop_s) / max(30, stop_s - calibration_stop_s - 30)
                    if base['status'] != 'EVALUATED':
                        rows.append(dict(base))
                        continue
                    if scenario.endswith('satellite_ramp') and satellite not in base['satellites']:
                        row = dict(base)
                        row['status'] = 'PERTURBATION_OUTSIDE_MATCHED_SUPPORT'
                        row.pop('exceedances', None)
                        rows.append(row)
                        continue
                    try:
                        changed = perturb(values, scenario, shift, satellite, reference, positions,
                                          navigation, time_s, context, direction)
                        evaluated = evaluate_epoch(time_s, changed, positions, navigation, context)
                        row = score_epoch(evaluated, baselines)
                        if row['status'] == 'EVALUATED' and row['satellites'] != base['satellites']:
                            row['status'] = 'MATCHED_SUPPORT_CHANGED'
                    except ValueError as error:
                        row = {'gpst_s': time_s, 'status': 'PERTURBATION_FAILED', 'reason': str(error)}
                    row['ramp_shift_m'] = shift
                    if row['status'] == 'EVALUATED':
                        row['clock_change_m'] = {name: value - base['clock_m'][name]
                                                 for name, value in row['clock_m'].items()}
                    rows.append(row)
                apply_thresholds(rows, thresholds)
                comparable = [row for row in rows if 'exceedances' in row]
                originals = [original_by_time[row['gpst_s']] for row in comparable]
                summary = summarize(rows)
                controls = summarize(originals)
                comparison = {}
                for mode in MODES:
                    new = [row for row, base in zip(comparable, originals)
                           if row['exceedances'][mode] and not base['exceedances'][mode]]
                    comparison[mode] = {'new_exceedance_epochs': len(new),
                                        'first_new_exceedance_delay_s':
                                            new[0]['gpst_s'] - calibration_stop_s if new else None}
                local_count, combined_count = summary['exceedances']['local'], summary['exceedances']['combined']
                cases.append({'scenario': scenario, 'amplitude_m': amplitude,
                              'summary': summary, 'original_on_same_support': controls,
                              'changes_from_original': comparison,
                              'equal_observed_original_exceedance_counts':
                                  (controls['exceedances']['local'] == controls['exceedances']['combined']
                                   if comparable else None),
                              'combined_minus_local_exceedance_epochs': combined_count - local_count,
                              'epochs': rows})
    return {'schema': 'pnt-development-comparison-v1',
            'status': 'EXPLORATORY_COMPARISON' if thresholds is not None else 'INSUFFICIENT_CALIBRATION',
            'day_gpst': context.day.date().isoformat(), 'sources': sources,
            'parameters': {'boundaries_gpst_s': [start_s, train_stop_s, calibration_stop_s, stop_s],
                           'amplitudes_m': amplitudes, 'direction_ecef_unit': direction.tolist(),
                           'satellite': satellite, 'reference_fault_receiver': min(references),
                           'minimum_training_per_pair': minimum_training,
                           'minimum_calibration_epochs': minimum_calibration,
                           'calibration_quantile': proportion,
                           'ramp': 'zero at first evaluation epoch; full amplitude at last; codes modified before fit'},
            'method': 'training medians per satellite pair; max absolute pair innovation per epoch; '
                      'nearest-rank thresholds on separate calibration epochs; strict >; no evaluation retuning',
            'baselines': baselines, 'thresholds_m': thresholds,
            'original': {'training': summarize([row for row in original if row['gpst_s'] < train_stop_s]),
                         'calibration': summarize(calibration), 'evaluation': summarize(testing), 'epochs': original},
            'cases': cases,
            'assessments': {'recorded_RF_detection_gain': 'NOT_ASSESSED',
                            'absolute_time': 'INSUFFICIENT_EVIDENCE'},
            'limits': [
                'Original recordings have no certified benign/attack labels; exceedances are not measured false alarms.',
                'Software code ramps do not simulate RF capture, tracking, signal quality or navigation-bit manipulation.',
                'Calibration tail budget is shared; realized original exceedance counts can differ and are retained.',
                'All decisions use the same matched support; altered/unsupported support is retained as inconclusive.',
                'Satellite pairs and adjacent epochs are correlated; counts are not independent attack episodes.',
                'Clock changes are GNSS/model-derived; geometry differences cancel common receiver offsets.',
                'Reference disagreement is a separate diagnostic, not automatic validation or attribution.',
                'Coordinate, propagation, signal-bias and provider/clock independence limits of pnt analyze still apply.',
            ]}
