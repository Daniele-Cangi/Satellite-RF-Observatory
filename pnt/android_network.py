"""GPS L1 fixed-site diagnostics connecting Android Raw to external RINEX."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import hashlib
from pathlib import Path

import numpy as np

from .android_raw import inspect_android_raw
from .fixed_site import evaluate_epoch, observation_epochs, read_station, validate_window
from .model import GPS_EPOCH, broadcast_navigation, day_context


def grid_codes(intake, day, start_s, stop_s):
    """Choose the closest C1C row within 1 ms, without rewriting its code/time.

    Preserve all candidate dispositions. Two source hardware epochs tied for
    closest distance are ambiguous; do not select by measurement magnitude.
    Reject a grid assembled across hardware epochs or clock discontinuities.
    """
    midnight = (day_context(day).day - GPS_EPOCH).days * 86400_000_000_000
    candidates, dispositions, counts = defaultdict(list), [], Counter()
    with localcontext() as context:
        context.prec = 40
        for row in intake['records']:
            item = {'source_line': row['source_line']}
            dispositions.append(item)
            if row['status'] != 'NORMALIZED' or row.get('signal') != 'C1C':
                item['status'] = 'NOT_NORMALIZED_C1C'
                item['intake_status'] = row['status']
                item['signal'] = row.get('signal')
                if 'reason' in row:
                    item['reason'] = row['reason']
            elif row['pseudorange_m'] <= 0:
                item['status'] = 'NONPOSITIVE_CODE'
            else:
                time = (Decimal(row['receiver_gpst_ns']) - midnight) / 1_000_000_000
                grid = int((time / 30).to_integral_value(rounding=ROUND_HALF_EVEN)) * 30
                offset = time - grid
                item.update(gpst_s=grid, time_offset_s=float(offset), satellite=row['satellite'])
                if not 0 <= time < 86400:
                    item['status'] = 'OUTSIDE_GPST_DAY'
                elif abs(offset) > Decimal('.001'):
                    item['status'] = 'OFF_GRID'
                elif not start_s <= grid < stop_s:
                    item['status'] = 'OUTSIDE_WINDOW'
                else:
                    candidates[grid, row['satellite']].append((abs(offset), row, item))
    selected = {}
    for key, choices in sorted(candidates.items()):
        minimum = min(choice[0] for choice in choices)
        nearest = [choice for choice in choices if choice[0] == minimum]
        if len(nearest) != 1:
            for _, _, item in choices:
                item['status'] = 'AMBIGUOUS_DUPLICATE'
            continue
        chosen = nearest[0]
        for choice in choices:
            choice[2]['status'] = 'SELECTED' if choice is chosen else 'FARTHER_GRID_CANDIDATE'
        selected[key] = chosen
    by_grid = defaultdict(list)
    for (grid, _), choice in selected.items():
        by_grid[grid].append(choice)
    for grid, choices in by_grid.items():
        hardware_epochs = {(row['source_values']['TimeNanos'],
                            row['source_values']['FullBiasNanos'], row['source_values']['BiasNanos'],
                            row['hardware_clock_discontinuity_count']) for _, row, _ in choices}
        if len(hardware_epochs) != 1:
            for _, _, item in choices:
                item['status'] = 'MIXED_HARDWARE_EPOCH'
            for key in [key for key in selected if key[0] == grid]:
                del selected[key]
    for item in dispositions:
        counts[item['status']] += 1
    codes = {key: (choice[1]['pseudorange_m'],) for key, choice in selected.items()}
    selected_rows = {key: choice[1]['source_line'] for key, choice in selected.items()}
    return codes, selected_rows, {'status_counts': dict(sorted(counts.items())),
                                  'row_dispositions': dispositions,
                                  'maximum_offset_s': .001,
                                  'selection': 'CLOSEST_C1C_ROW; TIES_AND_MIXED_HARDWARE_EPOCHS_EXCLUDED'}


def analyze_android(local_path, references, navigation_path, day_gpst, *, start_s=0, stop_s=86400,
                    local_ecef=None, position_source=None):
    """Use the existing clock/geometry/DD engine with explicitly single-band code.

    No position is inferred from victim PVT. Single-frequency ionosphere and
    signal group delay are uncorrected nuisances, not authenticated anomalies.
    """
    validate_window(start_s, stop_s)
    if not isinstance(position_source, str) or not position_source.strip():
        raise ValueError('explicit local antenna ECEF requires its source')
    position = np.asarray(local_ecef, dtype=float)
    if position.shape != (3,) or not np.isfinite(position).all() or not 6e6 < np.linalg.norm(position) < 7e6:
        raise ValueError('expected finite terrestrial local antenna ECEF coordinate')
    if (not isinstance(references, dict) or len(references) < 2 or
            any(not isinstance(name, str) or not name.strip() or name in ('local', 'navigation')
                for name in references)):
        raise ValueError('at least two named external receivers required; local/navigation are reserved')
    day = date.fromisoformat(day_gpst)
    context = day_context(day)
    intake = inspect_android_raw(local_path)
    local, source_lines, selection = grid_codes(intake, day, start_s, stop_s)
    sources = {'local': {**intake['source'], 'intake_coverage': intake['coverage'],
                         'antenna_ecef_m': position.tolist(), 'position_source': position_source,
                         'grid_selection': selection}}
    data, positions = {'local': local}, {'local': position}
    for name, path in sorted(references.items()):
        data[name], positions[name], sources[name] = read_station(path, day, signals=('C1C',))
    hashes = [source['sha256'] for source in sources.values()]
    markers = [sources[name]['marker_name'].strip().upper() for name in references]
    if len(set(hashes)) != len(hashes) or len(set(markers)) != len(markers):
        raise ValueError('reference files must represent distinct receivers, not duplicate files/markers')
    nav_data = Path(navigation_path).read_bytes()
    navigation, nav_counts = broadcast_navigation(nav_data)
    sources['navigation'] = {'file': Path(navigation_path).name,
                             'sha256': hashlib.sha256(nav_data).hexdigest(), 'record_status': nav_counts}
    epochs = []
    for time, observations in observation_epochs(data, start_s, stop_s):
        result = evaluate_epoch(time, observations, positions, navigation, context,
                                code_transform=lambda codes: {sv: code[0] for sv, code in codes.items()})
        result['local_source_lines'] = {sv: source_lines[time, sv] for sv in observations['local']}
        epochs.append(result)
    matched_counts = dict(sorted(Counter(epoch['matched']['status'] for epoch in epochs).items()))
    return {
        'schema': 'pnt-android-network-diagnostics-v1', 'day_gpst': day_gpst,
        'status': 'DIAGNOSTICS_AVAILABLE' if matched_counts.get('EVALUATED') else 'INSUFFICIENT_EVIDENCE',
        'window_gpst_s': [start_s, stop_s], 'sources': sources,
        'coverage': {'expected_epochs': len(epochs), 'matched_status_counts': matched_counts,
                     'standalone_status_counts': {
                         name: dict(sorted(Counter(epoch['standalone_receiver_fits'][name]['status']
                                                   for epoch in epochs).items())) for name in data}},
        'model': {'observables': 'GPS C1C ONLY; SINGLE_FREQUENCY',
                  'propagation': 'existing broadcast orbit/clock, emission/reception, Earth rotation and simple troposphere',
                  'uncorrected_nuisances': ['ionosphere', 'signal group delay and inter-receiver code biases'],
                  'grid': '30 s GPST; local offset <=1 ms; codes unchanged; model evaluated at grid epoch',
                  'local_clock': 'PER_ROW_ANDROID_CLOCK_SOLUTION; NOT_INDEPENDENT_TIME',
                  'position': 'explicit fixed antenna ECEF declaration; no survey verification or PVT-derived fit'},
        'assessments': dict.fromkeys(('RF_authenticity', 'spoofing', 'position_accuracy',
                                     'absolute_time', 'network_detection_gain'), 'NOT_ASSESSED'),
        'limits': [
            'No calibrated uncertainty budget, benign/attack labels, detector threshold or false-alarm estimate.',
            'Single-frequency residuals include uncorrected propagation and hardware effects.',
            'Receiver-derived GPST can be manipulated; this is not independent event alignment.',
            'Double differences cancel common clock offsets; regular remote receivers cannot authenticate local RF.',
            'Distinct reference files/markers do not establish independent providers, hardware or clocks.',
            'No interpolation or motion correction within the admitted 1 ms epoch offset.',
        ], 'epochs': epochs,
    }
