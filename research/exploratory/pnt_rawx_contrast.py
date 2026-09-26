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


def analyze(paired, windows, minimum_outside_per_satellite=3):
    """Centre each observable on scheduled-outside rows, then compare changes."""
    if minimum_outside_per_satellite < 1:
        raise ValueError('positive baseline support required')
    stations = sorted(paired[0]['references']) if paired else []
    if len(stations) < 2:
        raise ValueError('two external stations required')
    outside = defaultdict(list)
    for row in paired:
        if window_id(row['time_s'], windows) == 'outside_official_windows':
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
        group = window_id(row['time_s'], windows)
        satellite = row['satellite']
        if satellite not in baseline:
            unsupported[group] += 1
            continue
        local = row['local_l1_m'] - row['local_l2_m'] - baseline[satellite]['local']
        network = median(row['references'][station]['c1c_m'] -
                         row['references'][station]['c2w_m'] -
                         baseline[satellite]['network'][station] for station in stations)
        grouped[group].append({'time_s': row['time_s'], 'satellite': satellite,
                               'local': local, 'network': network,
                               'combined': local - network})
    summaries = {}
    for group in ['outside_official_windows', *(window['test_id'] for window in windows)]:
        rows = grouped[group]
        modes = {}
        for mode in MODES:
            values = [abs(row[mode]) for row in rows]
            modes[mode] = ({'median_absolute_m': median(values),
                            'p90_absolute_m': nearest_rank(values, 0.9),
                            'maximum_absolute_m': max(values)} if values else None)
        summaries[group] = {'paired_count': len(rows),
                            'paired_epoch_count': len({row['time_s'] for row in rows}),
                            'unsupported_satellite_pairs': unsupported[group],
                            'modes': modes}
    return {'baseline': 'per-satellite median of scheduled-outside paired rows; '
                        'remote stations centred separately',
            'minimum_outside_per_satellite': minimum_outside_per_satellite,
            'supported_satellites': sorted(supported),
            'quantile': 'nearest-rank 90th percentile of absolute change',
            'groups': summaries}


def run(archive, member, stations, day, windows_path):
    day = date.fromisoformat(day)
    with Path(windows_path).open(encoding='utf-8') as source:
        extract = json.load(source)
    windows = official_windows(extract, day)
    with tarfile.open(archive, 'r:gz') as source:
        payload = source.extractfile(member).read()
    epochs, raw_status = rawx_epochs(payload)
    local, jumps, grid_status = capture_grid(epochs, day)
    hashes = {name: sha256(path) for name, path in stations.items()}
    if len(stations) < 2 or len(set(hashes.values())) != len(hashes):
        raise ValueError('two distinct external stations required')
    external = {}
    for name, path in stations.items():
        content = hatanaka.decompress(Path(path).read_bytes(), strict=True).decode('ascii')
        external[name], _ = reference_codes(content, day)
    paired, missing = pair(local, external)
    return {'schema': 'pnt-jammertest-rawx-contrast-v1',
            'source': {'url': 'https://zenodo.org/records/15911589',
                       'archive_sha256': sha256(archive), 'member': member,
                       'member_sha256': hashlib.sha256(payload).hexdigest(),
                       'station_sha256': hashes,
                       'official_log_source_url': extract['source_url'],
                       'official_log_source_sha256': extract['source_sha256'],
                       'official_log_extract_sha256': sha256(windows_path)},
            'time_basis': '5 Hz packet order anchored to first pre-test receiver GPST; not independent time',
            'signal_basis': 'local GPS L1 C/A minus L2 CL; remote C1C minus C2W; temporal changes only',
            'raw_status': raw_status, 'grid_status': grid_status,
            'receiver_time_discontinuity_count': len(jumps),
            'missing_simultaneous_satellite': missing,
            'total_paired_count': len(paired),
            'official_windows': windows,
            'contrast': analyze(paired, windows),
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
    args = parser.parse_args()
    report = run(args.archive, args.rawx_member,
                 {args.station_a.name.split('_')[0]: args.station_a,
                  args.station_b.name.split('_')[0]: args.station_b},
                 args.day_gpst, args.windows)
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(report, destination, indent=2, allow_nan=False)
        destination.write('\n')
