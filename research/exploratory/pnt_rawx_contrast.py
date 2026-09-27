"""Exploratory same-episode GPS geometry-free contrast on exposed JammerTest RAWX.

L1/L2 tracking codes differ between local and remote receivers. Only their
within-satellite temporal changes are contrasted; no RF origin is authenticated.
"""

import argparse
from collections import Counter, defaultdict
from datetime import date
import hashlib
import json
import math
from pathlib import Path
from statistics import median
import tarfile

import hatanaka

from research.exploratory.pnt_observation_pairing import (
    official_windows, pair, reference_codes, sha256,
)
from research.exploratory.pnt_rawx_recovery import capture_grid, rawx_epochs


MODES = ('local', 'network', 'combined')


def window_id(time_s, windows):
    return next((window['test_id'] for window in windows
                 if window['start_gpst_s'] <= time_s < window['stop_gpst_s']),
                'outside_official_windows')


def nearest_rank(values, proportion):
    if not values or not 0 < proportion <= 1:
        raise ValueError('nonempty values and quantile proportion required')
    return sorted(values)[math.ceil(len(values) * proportion) - 1]


def absolute_summary(values):
    values = [abs(value) for value in values]
    return ({'median_absolute_m': median(values),
             'p90_absolute_m': nearest_rank(values, 0.9),
             'maximum_absolute_m': max(values)} if values else None)


def analyze(paired, windows, minimum_outside_per_satellite=3,
            baseline_mode='outside'):
    """Centre on exposed control rows, then compare the same paired changes."""
    if minimum_outside_per_satellite < 1:
        raise ValueError('positive baseline support required')
    if baseline_mode not in ('outside', 'pre-event'):
        raise ValueError('unsupported baseline mode')
    stations = sorted(paired[0]['references']) if paired else []
    if len(stations) < 2:
        raise ValueError('two external stations required')
    def group(time_s):
        if baseline_mode == 'pre-event':
            if time_s < windows[0]['start_gpst_s']:
                return 'pre_event'
            if time_s >= windows[-1]['stop_gpst_s']:
                return 'post_event'
        return window_id(time_s, windows)

    control_group = 'pre_event' if baseline_mode == 'pre-event' else 'outside_official_windows'
    outside = defaultdict(list)
    for row in paired:
        if group(row['time_s']) == control_group:
            outside[row['satellite']].append(row)
    supported = {satellite: rows for satellite, rows in outside.items()
                 if len(rows) >= minimum_outside_per_satellite}
    if not supported:
        raise ValueError('no satellite has adequate outside-window support')
    baseline = {}
    for satellite, rows in supported.items():
        baseline[satellite] = {
            'local': median(row['local_l1_m'] - row['local_l2_m'] for row in rows),
            'network': {station: median(row['references'][station]['c1c_m'] -
                                        row['references'][station]['c2w_m'] for row in rows)
                        for station in stations},
        }
    grouped, unsupported = defaultdict(list), Counter()
    for row in paired:
        group_name = group(row['time_s'])
        satellite = row['satellite']
        if satellite not in baseline:
            unsupported[group_name] += 1
            continue
        local = row['local_l1_m'] - row['local_l2_m'] - baseline[satellite]['local']
        station_changes = {station: row['references'][station]['c1c_m'] -
                           row['references'][station]['c2w_m'] -
                           baseline[satellite]['network'][station] for station in stations}
        network = median(station_changes.values())
        grouped[group_name].append({'time_s': row['time_s'], 'satellite': satellite,
                                    'local': local, 'network': network,
                                    'combined': local - network,
                                    'station_changes': station_changes,
                                    'station_disagreement': max(station_changes.values()) -
                                    min(station_changes.values())})
    summaries = {}
    groups = (['pre_event', *(window['test_id'] for window in windows), 'post_event',
               'outside_official_windows'] if baseline_mode == 'pre-event' else
              ['outside_official_windows', *(window['test_id'] for window in windows)])
    for group_name in groups:
        rows = grouped[group_name]
        modes = {mode: absolute_summary(row[mode] for row in rows)
                 for mode in MODES}
        summaries[group_name] = {'paired_count': len(rows),
                                 'paired_epoch_count': len({row['time_s'] for row in rows}),
                                 'unsupported_satellite_pairs': unsupported[group_name],
                                 'modes': modes,
                                 'reference_station_changes': {
                                     station: absolute_summary(row['station_changes'][station]
                                                               for row in rows)
                                     for station in stations},
                                 'reference_station_disagreement': absolute_summary(
                                     row['station_disagreement'] for row in rows)}
    baseline_description = ('per-satellite median of pre-event paired rows; '
                            'remote stations centred separately' if baseline_mode == 'pre-event'
                            else 'per-satellite median of scheduled-outside paired rows; '
                                 'remote stations centred separately')
    return {'baseline': baseline_description,
            'minimum_outside_per_satellite': minimum_outside_per_satellite,
            'supported_satellites': sorted(supported),
            'quantile': 'nearest-rank 90th percentile of absolute change',
            'reference_agreement_basis': ('range of separately centred reference-station '
                                          'frequency-difference changes on each matched '
                                          'satellite and epoch; a small network median alone '
                                          'does not establish station agreement'),
            'groups': summaries}


def run(archive, member, stations, day, windows_path, recover_corrupt=False,
        baseline_mode='outside'):
    day = date.fromisoformat(day)
    with Path(windows_path).open(encoding='utf-8') as source:
        extract = json.load(source)
    windows = official_windows(extract, day)
    with tarfile.open(archive, 'r:gz') as source:
        payload = source.extractfile(member).read()
    corrupt = Counter() if recover_corrupt else None
    epochs, raw_status = rawx_epochs(payload, corrupt)
    if corrupt is not None:
        raw_status['corrupt_ubx_packets_skipped'] = dict(sorted(corrupt.items()))
    local, jumps, grid_status = capture_grid(
        epochs, day, infer_missing_packets=recover_corrupt)
    hashes = {name: sha256(path) for name, path in stations.items()}
    if len(stations) < 2 or len(set(hashes.values())) != len(hashes):
        raise ValueError('two distinct external stations required')
    external = {}
    for name, path in stations.items():
        content = hatanaka.decompress(Path(path).read_bytes(), strict=True).decode('ascii')
        external[name], _ = reference_codes(content, day)
    paired, missing = pair(local, external)
    return {'schema': 'pnt-jammertest-rawx-contrast-v3',
            'source': {'url': 'https://zenodo.org/records/15911589',
                       'archive_sha256': sha256(archive), 'member': member,
                       'member_sha256': hashlib.sha256(payload).hexdigest(),
                       'station_sha256': hashes,
                       'official_log_source_url': extract['source_url'],
                       'official_log_source_sha256': extract['source_sha256'],
                       'official_log_extract_sha256': sha256(windows_path)},
            'time_basis': ('5 Hz packet order with short RAWX gaps inferred; anchored to first '
                           'pre-test receiver GPST; not independent time' if recover_corrupt else
                           '5 Hz packet order anchored to first pre-test receiver GPST; not independent time'),
            'signal_basis': 'local GPS L1 C/A minus L2 CL; remote C1C minus C2W; temporal changes only',
            'raw_status': raw_status, 'grid_status': grid_status,
            'receiver_time_discontinuity_count': len(jumps),
            'missing_simultaneous_satellite': missing,
            'total_paired_count': len(paired),
            'official_windows': windows,
            'contrast': analyze(paired, windows, baseline_mode=baseline_mode),
            'scope': 'Exposed attack recording, outside-window baseline also exposed; descriptive change, not calibrated detection, RF attribution or independent absolute time.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('rawx_member')
    parser.add_argument('day_gpst')
    parser.add_argument('station_a', type=Path)
    parser.add_argument('station_b', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--windows', type=Path, required=True)
    parser.add_argument('--recover-corrupt', action='store_true',
                        help='Count and skip damaged UBX packets; infer short RAWX gaps')
    parser.add_argument('--baseline', choices=('outside', 'pre-event'), default='outside')
    args = parser.parse_args()
    report = run(args.archive, args.rawx_member,
                 {args.station_a.name.split('_')[0]: args.station_a,
                  args.station_b.name.split('_')[0]: args.station_b},
                 args.day_gpst, args.windows, recover_corrupt=args.recover_corrupt,
                 baseline_mode=args.baseline)
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(report, destination, indent=2, allow_nan=False)
        destination.write('\n')
