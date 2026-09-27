"""Qualify simultaneous GPS code coverage for a fixed local RINEX receiver.

This is an exposed-data intake, not a detector or a claim that a RINEX marker
position is independently surveyed. It reuses the existing C1C/C2W reader and
three-receiver pairing; no event labels or thresholds are inferred.
"""

import argparse
from collections import Counter
from datetime import date
import json
import math
from pathlib import Path

import hatanaka

from research.exploratory.pnt_observation_pairing import pair, reference_codes, sha256


def station_header(content):
    """Read declared station identity and approximate XYZ, never ground truth."""
    fields = {}
    for line in content.splitlines():
        label = line[60:80].strip()
        if label in ('MARKER NAME', 'APPROX POSITION XYZ'):
            if label in fields:
                raise ValueError(f'duplicate RINEX {label}')
            fields[label] = line[:60].strip()
        if label == 'END OF HEADER':
            break
    else:
        raise ValueError('incomplete RINEX header')
    marker = fields.get('MARKER NAME', '').split()
    if not marker:
        raise ValueError('RINEX marker name required to distinguish receivers')
    xyz = fields.get('APPROX POSITION XYZ', '').split()
    if xyz:
        if len(xyz) != 3:
            raise ValueError('invalid approximate RINEX XYZ')
        coordinates = [float(value) for value in xyz]
        if not all(math.isfinite(value) for value in coordinates):
            raise ValueError('nonfinite approximate RINEX XYZ')
    else:
        coordinates = None
    return {'marker_name': marker[0], 'declared_approx_xyz_m': coordinates}


def read_station(path, day):
    content = hatanaka.decompress(Path(path).read_bytes(), strict=True).decode('ascii')
    header = station_header(content)
    rows, status = reference_codes(content, day)
    return rows, {'file': Path(path).name, 'sha256': sha256(path),
                  **header, 'code_status': status}


def coverage_runs(paired):
    """Represent all 30-second supported epochs without hiding long outages."""
    epochs = sorted({row['time_s'] for row in paired})
    runs = []
    for time_s in epochs:
        if runs and time_s == runs[-1]['last_gpst_s'] + 30:
            runs[-1]['last_gpst_s'] = time_s
            runs[-1]['epoch_count'] += 1
        else:
            runs.append({'first_gpst_s': time_s, 'last_gpst_s': time_s,
                         'epoch_count': 1})
    return runs


def run(local_path, references, day_gpst):
    if len(references) < 2 or len(set(references)) != len(references):
        raise ValueError('two named external stations required')
    day = date.fromisoformat(day_gpst)
    local, local_info = read_station(local_path, day)
    remote, info = {}, {}
    for name, path in sorted(references.items()):
        remote[name], info[name] = read_station(path, day)
    identities = [local_info, *info.values()]
    markers = [entry['marker_name'].upper() for entry in identities]
    hashes = [entry['sha256'] for entry in identities]
    if len(set(markers)) != len(markers) or len(set(hashes)) != len(hashes):
        raise ValueError('local and external files must represent distinct receivers')
    local_for_pair = {key: (0.0, float(key[0]), *codes)
                      for key, codes in local.items()}
    paired, missing = pair(local_for_pair, remote)
    epoch_sizes = Counter(row['time_s'] for row in paired)
    epochs = set(epoch_sizes)
    local_epochs = {time_s for time_s, _ in local}
    return {
        'schema': 'pnt-fixed-site-rinex-intake-v1',
        'day_gpst': day.isoformat(),
        'signals': 'GPS RINEX C1C/C2W at local and external receivers',
        'local': local_info,
        'references': info,
        'local_code_rows': len(local),
        'local_code_epochs': len(local_epochs),
        'paired_rows': len(paired),
        'paired_epochs': len(epochs),
        'local_epochs_without_pair': len(local_epochs - epochs),
        'paired_satellites_per_epoch': dict(sorted(Counter(epoch_sizes.values()).items())),
        'paired_satellites': sorted({row['satellite'] for row in paired}),
        'missing_simultaneous_satellite': missing,
        'paired_coverage_runs': coverage_runs(paired),
        'scope': ('Structural same-epoch/satellite availability only. RINEX approximate '
                  'coordinates are declarations, not independently surveyed truth. '
                  'Receiver GPST is not an independent capture clock. No event labels, '
                  'attack decision, RF authenticity or network detection gain.'),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('day_gpst')
    parser.add_argument('local_rinex', type=Path)
    parser.add_argument('station_a', type=Path)
    parser.add_argument('station_b', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    names = [path.name.split('_')[0] for path in (args.station_a, args.station_b)]
    if len(set(names)) != 2:
        parser.error('external station filenames must have distinct identifiers before underscore')
    report = run(args.local_rinex, dict(zip(names, (args.station_a, args.station_b))),
                 args.day_gpst)
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(report, destination, indent=2, allow_nan=False)
        destination.write('\n')
