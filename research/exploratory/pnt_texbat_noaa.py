"""Exposed-data TEXBAT ds7/cleanStatic contrast at simultaneous NOAA epochs.

This is a counterfactual measurement comparison, not an online detector or
authentication verdict. TEXBAT receiver time is anchored from a preattack
interval; it is not an independent absolute-time reference.
"""

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import gzip
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
from statistics import median

import hatanaka
import numpy as np
from scipy.io import loadmat


GPS_EPOCH = datetime(1980, 1, 6)
DAY = datetime(2012, 9, 14)
GPS_WEEK = 1705
ANCHOR_RRT = (20.0, 80.0)
PREATTACK_END_RRT = 110.0
TIME_PUSH_START_RRT = 150.0
MAX_GRID_OFFSET_S = 0.11  # 5 Hz TEXBAT sampling; nearest sample is ~0.03 s away.


def digest(data):
    return hashlib.sha256(data).hexdigest()


def channel_rows(data):
    """Load the 14-column public GRID log from its transposed MATLAB matrix."""
    matrix = loadmat(BytesIO(data), variable_names=['channel'])['channel']
    if matrix.ndim != 2 or matrix.shape[0] != 14:
        raise ValueError('expected 14-row TEXBAT channel matrix')
    rows = matrix.T
    if not np.isfinite(rows).all():
        raise ValueError('nonfinite TEXBAT channel value')
    return rows


def select_gps_code(rows):
    """Keep valid GPS L1 code keyed by 5 Hz RRT tick and PRN; retain exclusions."""
    selected, counts = {}, Counter()
    for row in rows:
        counts['source_rows'] += 1
        rrt, week, whole, fraction, code, valid, signal, prn = row[[1, 2, 3, 4, 7, 9, 12, 13]]
        if signal != 0 or prn != int(prn) or not 1 <= prn <= 32:
            counts['other_signal_or_prn'] += 1
            continue
        counts['gps_rows'] += 1
        if week != GPS_WEEK or valid != 1 or code <= 0:
            counts['invalid_code_or_time'] += 1
            continue
        if row[10] != 0:
            counts['selected_with_error_indicator'] += 1
        tick = round(rrt * 5)
        if abs(rrt - tick / 5) > 0.02:
            raise ValueError('TEXBAT RRT does not follow the 5 Hz grid')
        key = tick, int(prn)
        if key in selected:
            raise ValueError('duplicate TEXBAT RRT/PRN')
        selected[key] = (float(rrt), float(whole + fraction), float(code))
        counts['selected_code_rows'] += 1
    return selected, dict(sorted(counts.items()))


def preattack_anchor(clean, attack):
    """Anchor RRT to GPST only where both exposed recordings agree preattack."""
    offsets = []
    for key in clean.keys() & attack.keys():
        rrt, ort, code = clean[key]
        other_rrt, other_ort, other_code = attack[key]
        if ANCHOR_RRT[0] <= rrt < ANCHOR_RRT[1]:
            if abs(rrt - other_rrt) > 0.02 or abs(code - other_code) > 1e-6:
                raise ValueError('clean and ds7 disagree in preattack anchor interval')
            offsets.append(ort - rrt)
    if not offsets:
        raise ValueError('no matched preattack anchor samples')
    anchor = median(offsets)
    if max(abs(offset - anchor) for offset in offsets) > 0.01:
        raise ValueError('unstable preattack RRT-to-ORT anchor')
    return anchor, len(offsets)


def rinex2_c1(data, station):
    """Read GPS C1 at ordinary epochs of one NOAA gzip/Hatanaka RINEX 2.11 file."""
    content = hatanaka.decompress(gzip.decompress(data), strict=True).decode('ascii')
    return rinex2_c1_text(content, station)


def rinex2_c1_text(content, station):
    """Parse a decoded RINEX 2 file, allowing only comment-only splice events."""
    lines = iter(content.splitlines())
    header = defaultdict(list)
    for line in lines:
        label = line[60:80].strip()
        header[label].append(line[:60])
        if label == 'END OF HEADER':
            break
    else:
        raise ValueError('incomplete RINEX 2 header')
    version = header['RINEX VERSION / TYPE']
    if len(version) != 1 or not 2 <= float(version[0][:9]) < 3 or 'OBSERVATION DATA' not in version[0]:
        raise ValueError('expected one RINEX 2 observation header')
    if len(header['MARKER NAME']) != 1 or header['MARKER NAME'][0].strip().upper() != station:
        raise ValueError('unexpected NOAA station marker')
    first = header['TIME OF FIRST OBS']
    if len(first) != 1 or first[0][48:51] != 'GPS':
        raise ValueError('NOAA time scale is not uniquely GPST')
    clock = header['RCV CLOCK OFFS APPL']
    if len(clock) != 1 or int(clock[0]) != 0:
        raise ValueError('NOAA receiver clock correction requires interpretation')
    types_header = header['# / TYPES OF OBSERV']
    if not types_header:
        raise ValueError('missing RINEX 2 observation types')
    ntypes = int(types_header[0][:6])
    types = [line[start:start + 6].strip() for line in types_header for start in range(6, 60, 6)]
    if ntypes != len([item for item in types if item]) or 'C1' not in types:
        raise ValueError('invalid RINEX 2 GPS C1 observation types')
    c1_index = types.index('C1')
    rows, counts = {}, Counter()
    for line in lines:
        if not line.strip():
            continue
        if len(line) < 32:
            raise ValueError('short RINEX 2 epoch')
        flag, nsat = int(line[28:29]), int(line[29:32])
        if flag == 4 and not line[:26].strip():
            special = [next(lines, None) for _ in range(nsat)]
            if any(item is None or item[60:80].strip() != 'COMMENT' for item in special):
                raise ValueError('RINEX 2 header update needs interpretation')
            counts['comment_only_events'] += 1
            continue
        if flag != 0:
            raise ValueError('nonordinary RINEX 2 event requires interpretation')
        year, month, day, hour, minute = (int(line[a:b]) for a, b in ((1, 3), (4, 6), (7, 9), (10, 12), (13, 15)))
        year += 2000 if year < 80 else 1900
        second = float(line[15:26])
        if nsat < 0 or not math.isfinite(second):
            raise ValueError('invalid RINEX 2 epoch count or time')
        stamp = datetime(year, month, day, hour, minute) + timedelta(seconds=second)
        if stamp.date() != DAY.date() or (stamp - DAY).total_seconds() % 30 > 1e-3:
            raise ValueError('NOAA epoch outside selected 30-second GPST day')
        seconds = round((stamp - GPS_EPOCH).total_seconds() - GPS_WEEK * 604800)
        satellites = line[32:68]
        for _ in range(math.ceil(nsat / 12) - 1):
            continuation = next(lines, None)
            if continuation is None:
                raise ValueError('truncated RINEX 2 satellite list')
            satellites += continuation[32:68]
        satellite_ids = [satellites[i:i + 3] for i in range(0, nsat * 3, 3)]
        if len(satellite_ids) != nsat or len(set(satellite_ids)) != nsat:
            raise ValueError('invalid or duplicate RINEX 2 satellite list')
        counts['ordinary_epochs'] += 1
        for satellite in satellite_ids:
            records = [next(lines, None) for _ in range(math.ceil(ntypes / 5))]
            if any(record is None for record in records):
                raise ValueError('truncated RINEX 2 observation records')
            if not satellite.startswith('G') or not satellite[1:].isdigit():
                counts['non_gps_rows'] += 1
                continue
            counts['gps_rows'] += 1
            cell = records[c1_index // 5][16 * (c1_index % 5):16 * (c1_index % 5) + 14].strip()
            if not cell:
                counts['missing_c1'] += 1
                continue
            value = float(cell)
            if not math.isfinite(value) or value <= 0:
                counts['invalid_c1'] += 1
                continue
            key = seconds, int(satellite[1:])
            if key in rows:
                raise ValueError('duplicate NOAA epoch/PRN')
            rows[key] = value
    counts['selected_c1_rows'] = len(rows)
    return rows, dict(sorted(counts.items()))


def compare(clean, attack, references, anchor):
    """Compare matched local RF outputs on epochs observed by both witnesses."""
    if set(references) != {'TXAU', 'SAM2'}:
        raise ValueError('expected two distinct Austin witnesses')
    common = sorted(references['TXAU'].keys() & references['SAM2'].keys())
    changes = []
    counts = Counter()
    epochs = defaultdict(list)
    local_span = (max(min(rrt for rrt, _, _ in clean.values()), min(rrt for rrt, _, _ in attack.values())),
                  min(max(rrt for rrt, _, _ in clean.values()), max(rrt for rrt, _, _ in attack.values())))
    for tow, prn in common:
        counts['two_witness_c1_rows'] += 1
        target_rrt = tow - anchor
        if not local_span[0] - MAX_GRID_OFFSET_S <= target_rrt <= local_span[1] + MAX_GRID_OFFSET_S:
            counts['outside_local_recording_span'] += 1
            continue
        counts['two_witness_rows_in_local_span'] += 1
        tick = round(target_rrt * 5)
        key = tick, prn
        if key not in clean or key not in attack:
            counts['missing_local_clean_or_attack'] += 1
            continue
        rrt, _, clean_code = clean[key]
        attack_rrt, _, attack_code = attack[key]
        if max(abs(rrt - target_rrt), abs(attack_rrt - target_rrt)) > MAX_GRID_OFFSET_S:
            counts['outside_time_tolerance'] += 1
            continue
        change = attack_code - clean_code
        phase = ('preattack' if rrt < PREATTACK_END_RRT else
                 'takeover' if rrt < TIME_PUSH_START_RRT else 'time_push')
        epochs[phase, tow].append((prn, change))
        changes.append((phase, tow, prn, change))
    summary = {}
    per_epoch = []
    for phase in ('preattack', 'takeover', 'time_push'):
        values = [delta for label, _, _, delta in changes if label == phase]
        episode_epochs = sorted((tow, sorted(rows)) for (label, tow), rows in epochs.items() if label == phase)
        # Within-epoch satellite differences remove a receiver-wide offset.
        differences = [delta - rows[0][1] for _, rows in episode_epochs for _, delta in rows[1:]]
        for tow, rows in episode_epochs:
            per_epoch.append({
                'gpst_tow_s': tow, 'phase': phase, 'satellites': len(rows),
                'reference_prn': rows[0][0],
                'median_signed_local_code_change_m': median(delta for _, delta in rows),
                'median_absolute_satellite_difference_change_m':
                    median(abs(delta - rows[0][1]) for _, delta in rows[1:]) if len(rows) > 1 else None,
            })
        summary[phase] = {
            'epochs': len(episode_epochs), 'matched_satellite_rows': len(values),
            'reference_satellite_differences': len(differences),
            'median_signed_local_code_change_m': median(values) if values else None,
            'median_absolute_local_code_change_m': median(map(abs, values)) if values else None,
            'median_absolute_satellite_difference_change_m': median(map(abs, differences)) if differences else None,
            'max_absolute_satellite_difference_change_m': max(map(abs, differences)) if differences else None,
        }
    if not summary['preattack']['matched_satellite_rows'] or not summary['time_push']['matched_satellite_rows']:
        raise ValueError('both preattack and time-push matched observations required')
    counts['matched_rows'] = len(changes)
    counts['matched_epochs'] = len({tow for _, tow, _, _ in changes})
    return summary, dict(sorted(counts.items())), sorted(per_epoch, key=lambda row: row['gpst_tow_s'])


def run(clean_path, attack_path, txau_path, sam2_path):
    paths = {'cleanStatic': clean_path, 'ds7': attack_path, 'TXAU': txau_path, 'SAM2': sam2_path}
    contents = {name: Path(path).read_bytes() for name, path in paths.items()}
    clean, clean_counts = select_gps_code(channel_rows(contents['cleanStatic']))
    attack, attack_counts = select_gps_code(channel_rows(contents['ds7']))
    anchor, anchor_rows = preattack_anchor(clean, attack)
    txau, txau_counts = rinex2_c1(contents['TXAU'], 'TXAU')
    sam2, sam2_counts = rinex2_c1(contents['SAM2'], 'SAM2')
    result, pair_counts, per_epoch = compare(clean, attack, {'TXAU': txau, 'SAM2': sam2}, anchor)
    return {
        'schema': 'pnt-texbat-noaa-exploratory-v1',
        'scope': 'exposed counterfactual code contrast; no detection, attribution or absolute-time claim',
        'source_sha256': {name: digest(data) for name, data in contents.items()},
        'gpst_day': DAY.date().isoformat(), 'gps_week': GPS_WEEK,
        'anchor_rrt_s': list(ANCHOR_RRT), 'preattack_end_rrt_s': PREATTACK_END_RRT,
        'time_push_start_rrt_s': TIME_PUSH_START_RRT,
        'rrt_to_gpst_anchor_s': anchor, 'anchor_matched_rows': anchor_rows,
        'max_epoch_offset_s': MAX_GRID_OFFSET_S,
        'source_counts': {'cleanStatic': clean_counts, 'ds7': attack_counts,
                          'TXAU': txau_counts, 'SAM2': sam2_counts},
        'pairing_counts': pair_counts, 'contrast': result, 'per_epoch': per_epoch,
        'interpretation': [
            'At each matched epoch, subtracting the same external C1 from clean and ds7 leaves the local code change.',
            'Satellite differences use the lowest common PRN in each epoch as reference; a receiver-wide code shift cancels.',
            'The RRT-to-GPST anchor uses TEXBAT preattack ORT and is not an independent clock.',
            'TEXBAT cleanStatic and ds7 share a source recording; rows and epochs are correlated, not independent incidents.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('clean', 'attack', 'txau', 'sam2', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = run(args.clean, args.attack, args.txau, args.sam2)
    args.output.write_bytes((json.dumps(report, indent=2, sort_keys=True) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
