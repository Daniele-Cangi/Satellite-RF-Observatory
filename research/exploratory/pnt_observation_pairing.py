"""Pair public fixed-receiver GPS code with simultaneous external RINEX.

No attack label, orbit hypothesis, threshold or verdict is inferred here. In
particular the local CSV's L1/L2 fields do not establish the RINEX signal codes.
"""

import argparse
from collections import Counter
import csv
from datetime import date, datetime
import hashlib
import io
import json
import math
from pathlib import Path
import tarfile

import hatanaka


def local_codes(stream, day, tolerance_s=0.5):
    """Select the closest dual-code sample to each 30-second GPST grid point."""
    if not 0 < tolerance_s < 15:
        raise ValueError('grid tolerance must be in (0, 15) seconds')
    rows, counts = {}, Counter()
    reader = csv.DictReader(stream)
    needed = {'time', 'satellite', 'pseudorange_L1', 'pseudorange_L2'}
    if not needed <= set(reader.fieldnames or ()):
        raise ValueError('local observation columns missing')
    for row in reader:
        counts['source_rows'] += 1
        satellite = row['satellite']
        if not satellite.startswith('G'):
            counts['non_gps_rows'] += 1
            continue
        counts['gps_rows'] += 1
        if not (row['pseudorange_L1'] and row['pseudorange_L2']):
            counts['missing_dual_code'] += 1
            continue
        try:
            stamp = datetime.fromisoformat(row['time'])
            if stamp.tzinfo is not None or stamp.date() != day:
                counts['wrong_or_ambiguous_date'] += 1
                continue
            first, second = float(row['pseudorange_L1']), float(row['pseudorange_L2'])
            if not all(math.isfinite(v) and v > 0 for v in (first, second)):
                raise ValueError('invalid code')
        except (ValueError, TypeError):
            counts['invalid_time_or_code'] += 1
            continue
        seconds = stamp.hour * 3600 + stamp.minute * 60 + stamp.second + stamp.microsecond / 1e6
        grid = round(seconds / 30) * 30
        distance = abs(seconds - grid)
        if grid >= 86400 or distance > tolerance_s:
            counts['off_grid'] += 1
            continue
        counts['near_grid_rows'] += 1
        key = grid, satellite
        candidate = (distance, seconds, first, second)
        if key in rows:
            counts['repeated_grid_satellite'] += 1
        if key not in rows or candidate[:2] < rows[key][:2]:
            rows[key] = candidate
    counts['selected_grid_satellites'] = len(rows)
    counts['selected_epochs'] = len({time for time, _ in rows})
    return rows, dict(sorted(counts.items()))


def reference_codes(content, day):
    """Read only C1C/C2W from a complete RINEX 3 daily observation file."""
    lines = iter(content.splitlines())
    types, system, headers = [], None, {}
    for line in lines:
        label = line[60:80].strip()
        if label in ('RINEX VERSION / TYPE', 'TIME OF FIRST OBS', 'RCV CLOCK OFFS APPL', 'SYS / SCALE FACTOR',
                     'SYS / DCBS APPLIED', 'SYS / PCVS APPLIED'):
            headers.setdefault(label, []).append(line[:60])
        if label == 'SYS / # / OBS TYPES':
            if line[:1].strip():
                system = line[0]
            if system == 'G':
                types.extend(line[7:60].split())
        if label == 'END OF HEADER':
            break
    else:
        raise ValueError('incomplete RINEX header')
    if not 3 <= float(headers.get('RINEX VERSION / TYPE', ['0'])[0][:9]) < 4:
        raise ValueError('expected RINEX 3 observations')
    if not {'C1C', 'C2W'} <= set(types):
        raise ValueError('external GPS C1C/C2W missing')
    if headers.get('TIME OF FIRST OBS', [''])[0][48:51] != 'GPS':
        raise ValueError('external time scale is not GPST')
    if any(key in headers for key in ('SYS / SCALE FACTOR', 'SYS / DCBS APPLIED', 'SYS / PCVS APPLIED')):
        raise ValueError('unqualified applied RINEX correction')
    if int(headers.get('RCV CLOCK OFFS APPL', ['0'])[0]) != 0:
        raise ValueError('external receiver clock correction already applied')
    indices = types.index('C1C'), types.index('C2W')
    rows, counts = {}, Counter()
    for line in lines:
        if not line.startswith('>'):
            raise ValueError('expected RINEX epoch header')
        fields = line[1:].split()
        if len(fields) not in (8, 9):
            raise ValueError('invalid RINEX epoch header')
        year, month, day_number, hour, minute = map(int, fields[:5])
        if date(year, month, day_number) != day:
            raise ValueError('external epoch outside selected GPST day')
        seconds = hour * 3600 + minute * 60 + float(fields[5])
        flag, record_count = int(fields[6]), int(fields[7])
        block = [next(lines, None) for _ in range(record_count)]
        if any(record is None for record in block):
            raise ValueError('truncated RINEX epoch')
        if flag != 0:
            raise ValueError('nonstandard RINEX epoch requires explicit interpretation')
        counts['ordinary_epochs'] += 1
        if abs(seconds - round(seconds / 30) * 30) > 1e-3:
            raise ValueError('external epoch off 30-second grid')
        seen = set()
        for record in block:
            satellite = record[:3]
            if satellite in seen:
                raise ValueError('duplicate satellite in RINEX epoch')
            seen.add(satellite)
            if not satellite.startswith('G'):
                continue
            counts['gps_rows'] += 1
            code = [record[3 + 16 * i:3 + 16 * i + 14].strip() for i in indices]
            if not all(code):
                counts['missing_dual_code'] += 1
                continue
            values = tuple(map(float, code))
            if not all(math.isfinite(v) and v > 0 for v in values):
                counts['invalid_dual_code'] += 1
                continue
            key = round(seconds), satellite
            if key in rows:
                raise ValueError('duplicate external GPS epoch/satellite')
            rows[key] = values
    counts['selected_grid_satellites'] = len(rows)
    return rows, dict(sorted(counts.items()))


def pair(local, references):
    """Retain numeric samples only when every distinct witness has that epoch/PRN."""
    if len(references) < 2 or len(set(references)) != len(references):
        raise ValueError('at least two distinct witnesses required')
    paired = []
    missing = Counter()
    for key, sample in sorted(local.items()):
        absent = [name for name, rows in references.items() if key not in rows]
        if absent:
            for name in absent:
                missing[name] += 1
            continue
        paired.append({'time_s': key[0], 'satellite': key[1],
                       'local_l1_m': sample[2], 'local_l2_m': sample[3],
                       'time_offset_s': sample[0],
                       'references': {name: {'c1c_m': rows[key][0], 'c2w_m': rows[key][1]}
                                      for name, rows in references.items()}})
    return paired, dict(sorted(missing.items()))


def sha256(path):
    with Path(path).open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def official_windows(extract, day):
    """Convert the official event log's CEST clock to seconds of this GPST day."""
    if (extract.get('schema') != 'pnt-jammertest-official-windows-v1' or
            extract.get('date') != day.isoformat() or
            extract.get('source_time_zone') != 'CEST (UTC+02:00)' or
            extract.get('gpst_minus_utc_seconds_on_date') != 18):
        raise ValueError('unqualified official event time scale or date')
    windows, previous_stop, ids = [], -1, set()
    for row in extract['rows']:
        if row['test_id'] in ids:
            raise ValueError('repeated official test identifier')
        ids.add(row['test_id'])
        def gps_seconds(key):
            clock = datetime.strptime(row[key], '%H:%M:%S')
            return clock.hour * 3600 + clock.minute * 60 + clock.second - 7200 + 18
        start, stop = gps_seconds('start_cest'), gps_seconds('stop_cest')
        if not 0 <= start < stop <= 86400 or start < previous_stop:
            raise ValueError('overlapping or invalid official event windows')
        windows.append({'source_row': row['source_row'], 'test_id': row['test_id'],
                        'name': row['name'], 'start_gpst_s': start, 'stop_gpst_s': stop})
        previous_stop = stop
    if not windows:
        raise ValueError('empty official event log')
    return windows


def run(archive, member, stations, day, windows_path=None):
    """Return a compact report, not the paired raw observations."""
    if len(stations) < 2:
        raise ValueError('two external stations required')
    hashes = {name: sha256(path) for name, path in stations.items()}
    if len(set(hashes.values())) != len(hashes):
        raise ValueError('identical external observation files are one witness')
    day = date.fromisoformat(day)
    with tarfile.open(archive, 'r:gz') as source:
        prefix = member.rsplit('/', 1)[0]
        metadata = json.load(source.extractfile(prefix + '/scenario.json'))
        if (metadata['date'] != day.isoformat() or metadata['attack_type'] != 'Spoofing' or
                'stationary' not in prefix or not member.endswith('/rinex.csv')):
            raise ValueError('selected source is not stationary spoofing on the declared day')
        with io.TextIOWrapper(source.extractfile(member), encoding='utf-8-sig', newline='') as data:
            local, local_status = local_codes(data, day)
    remote, external_status = {}, {}
    for name, path in stations.items():
        decoded = hatanaka.decompress(Path(path).read_bytes(), strict=True).decode('ascii')
        remote[name], external_status[name] = reference_codes(decoded, day)
    paired, missing = pair(local, remote)
    event_coverage = None
    if windows_path is not None:
        with Path(windows_path).open(encoding='utf-8') as source:
            extract = json.load(source)
        windows = official_windows(extract, day)
        counts = Counter()
        epochs = {window['test_id']: set() for window in windows}
        for row in paired:
            match = next((window for window in windows
                          if window['start_gpst_s'] <= row['time_s'] < window['stop_gpst_s']), None)
            key = match['test_id'] if match else 'outside_official_windows'
            counts[key] += 1
            if match:
                epochs[key].add(row['time_s'])
        event_coverage = {'source_url': extract['source_url'],
                          'source_sha256': extract['source_sha256'],
                          'extract_sha256': sha256(windows_path),
                          'sheet': extract['sheet'],
                          'conversion': 'CEST - 2 hours + 18 seconds = GPST (2024-09-11)',
                          'windows': windows,
                          'paired_rows_by_receiver_time': dict(sorted(counts.items())),
                          'paired_epochs_by_receiver_time':
                          {key: len(value) for key, value in epochs.items()},
                          'qualification': 'Window overlap uses receiver-derived time; not independent attack truth.'}
    return {'schema': 'pnt-exposed-observation-pairing-v1',
            'source': {'url': 'https://zenodo.org/records/15911589',
                       'archive_sha256': sha256(archive), 'member': member,
                       'scenario_id': metadata['scenario_id'],
                       'declared_attack_log': metadata.get('attack_log', [])},
            'date_gpst': day.isoformat(), 'local_time_interpretation':
            'CSV time provisionally treated as GPST; derived from receiver, not an independent clock.',
            'local_signals': 'unqualified dataset pseudorange_L1/pseudorange_L2 labels',
            'external_signals': 'RINEX GPS C1C/C2W',
            'local_status': local_status,
            'stations': {name: {'file_sha256': hashes[name], 'status': external_status[name]}
                         for name, path in stations.items()},
            'missing_simultaneous_satellite': missing,
            'paired_count': len(paired),
            'paired_epoch_count': len({r['time_s'] for r in paired}),
            'paired_satellites': sorted({r['satellite'] for r in paired}),
            'first_paired_gpst_s': min((r['time_s'] for r in paired), default=None),
            'last_paired_gpst_s': max((r['time_s'] for r in paired), default=None),
            'maximum_selected_time_offset_s': max((r['time_offset_s'] for r in paired), default=None),
            'official_event_coverage': event_coverage,
            'scope': 'Pairing and provisional official-window overlap only; no independent time, signal equivalence, detector score or attack outcome.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('scenario_member')
    parser.add_argument('day_gpst')
    parser.add_argument('station_a', type=Path)
    parser.add_argument('station_b', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--windows', type=Path, help='Extracted official CEST event windows')
    args = parser.parse_args()
    result = run(args.archive, args.scenario_member,
                  {args.station_a.name.split('_')[0]: args.station_a,
                   args.station_b.name.split('_')[0]: args.station_b}, args.day_gpst,
                  windows_path=args.windows)
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(result, destination, indent=2, allow_nan=False)
        destination.write('\n')
