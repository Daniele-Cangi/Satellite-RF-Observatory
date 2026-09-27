"""Recover signal-identified GPS code and receiver clock jumps from JammerTest UBX.

Capture time is inferred from packet order and the observed 5 Hz cadence. It
is not an independent clock or a prospective attack label.
"""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import struct
import tarfile

import hatanaka

from research.exploratory.pnt_observation_pairing import (
    official_windows, pair, reference_codes, sha256,
)


GPS_EPOCH = datetime(1980, 1, 6)
RAWX = (0x02, 0x15)
GPS_SIGNALS = {0: 'L1 C/A', 3: 'L2 CL'}


def ubx_packets(content, corrupt=None):
    """Yield checksum-verified UBX packets; optionally count and skip damage.

    Recovery is explicit and never accepts a damaged packet as evidence.
    """
    offset = 0
    while (start := content.find(b'\xb5\x62', offset)) >= 0:
        if start + 8 > len(content):
            if corrupt is not None:
                corrupt['truncated_header'] += 1
                break
            raise ValueError('truncated UBX header')
        length = int.from_bytes(content[start + 4:start + 6], 'little')
        end = start + 8 + length
        if end > len(content):
            if corrupt is not None:
                corrupt['truncated_payload'] += 1
                offset = start + 1
                continue
            raise ValueError('truncated UBX payload')
        check_a = check_b = 0
        for byte in content[start + 2:end - 2]:
            check_a = (check_a + byte) & 0xff
            check_b = (check_b + check_a) & 0xff
        if content[end - 2:end] != bytes((check_a, check_b)):
            if corrupt is not None:
                corrupt['bad_checksum'] += 1
                offset = start + 1
                continue
            raise ValueError('UBX checksum mismatch')
        yield (content[start + 2], content[start + 3],
               memoryview(content)[start + 6:end - 2])
        offset = end


def rawx_epochs(content, corrupt=None):
    """Read GPS L1 C/A and L2 CL code only when RAWX marks pseudorange valid."""
    epochs, counts = [], Counter()
    for cls, message, payload in ubx_packets(content, corrupt):
        counts['ubx_packets'] += 1
        if (cls, message) == (0x01, 0x07):
            counts['nav_pvt_packets'] += 1
        if (cls, message) != RAWX:
            continue
        counts['rawx_packets'] += 1
        if len(payload) < 16 or payload[13] != 1:
            raise ValueError('unsupported RAWX header or version')
        tow, week = struct.unpack_from('<dH', payload)
        measurement_count = payload[11]
        if (len(payload) != 16 + 32 * measurement_count or
                not math.isfinite(tow) or not 0 <= tow < 604800):
            raise ValueError('invalid RAWX length or receiver time')
        measurements = {}
        for index in range(measurement_count):
            offset = 16 + 32 * index
            gnss, satellite, signal = payload[offset + 20:offset + 23]
            if gnss != 0 or signal not in GPS_SIGNALS:
                continue
            counts['gps_signal_records'] += 1
            if not payload[offset + 30] & 1:
                counts['invalid_pseudorange_flag'] += 1
                continue
            code = struct.unpack_from('<d', payload, offset)[0]
            if not math.isfinite(code) or code <= 0:
                counts['nonpositive_or_nonfinite_valid_flag_code'] += 1
                continue
            if code >= 100_000_000:
                # Keep the anomaly in the denominator; a range this large is
                # not a usable Earth-orbit GNSS pseudorange for pairing.
                counts['out_of_range_valid_flag_code'] += 1
                continue
            key = satellite, signal
            if key in measurements:
                raise ValueError('duplicate RAWX GPS satellite/signal')
            measurements[key] = code
            counts['valid_gps_signal_records'] += 1
        dual = {f'G{satellite:02d}': (measurements[satellite, 0], measurements[satellite, 3])
                for satellite in {sat for sat, signal in measurements if signal == 0}
                if (satellite, 3) in measurements}
        counts['dual_gps_measurements'] += len(dual)
        if dual:
            counts['dual_gps_packets'] += 1
        epochs.append({'receiver_time': GPS_EPOCH + timedelta(weeks=week, seconds=tow),
                       'clock_reset_flag': bool(payload[12] & 2), 'dual': dual})
    if not epochs:
        raise ValueError('no RAWX observations')
    return epochs, dict(sorted(counts.items()))


def capture_grid(epochs, day, rate_hz=5, tolerance_s=0.1,
                 infer_missing_packets=False):
    """Pair by monotonic packet order, retaining receiver-time discontinuities.

    An explicitly enabled short, integral receiver-time gap can account for
    missing RAWX packets. Large clock jumps never change the capture order.
    """
    if rate_hz != 5 or not 0 < tolerance_s < 0.1 + 1e-9:
        raise ValueError('unsupported capture cadence or grid tolerance')
    first = epochs[0]['receiver_time']
    if first.date() != day:
        raise ValueError('first receiver epoch does not anchor selected day')
    first_s = (first - datetime.combine(day, datetime.min.time())).total_seconds()
    selected, counts, jumps = {}, Counter(), []
    capture_tick = 0
    for index, epoch in enumerate(epochs):
        if index:
            before = epochs[index - 1]['receiver_time']
            delta = (epoch['receiver_time'] - before).total_seconds()
            if infer_missing_packets and 0.3 <= delta <= 1.0:
                ticks = round(delta * rate_hz)
                if abs(delta - ticks / rate_hz) <= 0.05:
                    counts['inferred_missing_rawx_packets'] += ticks - 1
                    capture_tick += ticks - 1
            capture_tick += 1
        capture_s = first_s + capture_tick / rate_hz
        if not 0 <= capture_s < 86400:
            raise ValueError('inferred capture time outside selected day')
        if index:
            if abs(delta - 1 / rate_hz) > 1:
                jumps.append({'capture_gpst_s': round(capture_s, 3),
                              'receiver_before': before.isoformat(),
                              'receiver_after': epoch['receiver_time'].isoformat(),
                              'receiver_jump_s': round(delta, 3)})
        grid = round(capture_s / 30) * 30
        distance = abs(capture_s - grid)
        if distance > tolerance_s or grid >= 86400:
            continue
        counts['near_grid_packets'] += 1
        for satellite, codes in epoch['dual'].items():
            key = grid, satellite
            candidate = (distance, capture_s, *codes)
            if key in selected:
                counts['repeated_grid_satellite'] += 1
            if key not in selected or candidate[:2] < selected[key][:2]:
                selected[key] = candidate
    counts['selected_grid_satellites'] = len(selected)
    counts['selected_epochs'] = len({time for time, _ in selected})
    if infer_missing_packets:
        counts['last_inferred_capture_gpst_s'] = round(first_s + capture_tick / rate_hz, 3)
    return selected, jumps, dict(sorted(counts.items()))


def run(archive, member, stations, day, windows_path, recover_corrupt=False):
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
    external, external_status = {}, {}
    for name, path in stations.items():
        decoded = hatanaka.decompress(Path(path).read_bytes(), strict=True).decode('ascii')
        external[name], external_status[name] = reference_codes(decoded, day)
    paired, missing = pair(local, external)
    first_s = (epochs[0]['receiver_time'] - datetime.combine(day, datetime.min.time())).total_seconds()
    counts = {window['test_id']: Counter() for window in windows}
    counts['outside_official_windows'] = Counter()
    def group(seconds):
        return next((window['test_id'] for window in windows
                     if window['start_gpst_s'] <= seconds < window['stop_gpst_s']),
                    'outside_official_windows')
    for index, epoch in enumerate(epochs):
        bucket = counts[group(first_s + index / 5)]
        bucket['rawx_packets'] += 1
        bucket['dual_gps_measurements'] += len(epoch['dual'])
        bucket['clock_reset_flags'] += epoch['clock_reset_flag']
    for row in paired:
        counts[group(row['time_s'])]['paired_rows'] += 1
    for window in windows:
        counts[window['test_id']]['paired_epochs'] = len({row['time_s'] for row in paired
            if group(row['time_s']) == window['test_id']})
    return {'schema': ('pnt-jammertest-rawx-recovery-v2' if recover_corrupt
                       else 'pnt-jammertest-rawx-recovery-v1'),
            'source': {'url': 'https://zenodo.org/records/15911589',
                       'archive_sha256': sha256(archive), 'member': member,
                       'member_sha256': hashlib.sha256(payload).hexdigest()},
            'rawx_protocol': 'https://content.u-blox.com/sites/default/files/documents/u-blox-F9-HPG-1.32_InterfaceDescription_UBX-22008968.pdf',
            'signals': {'local': 'GPS L1 C/A (gnssId 0, sigId 0), L2 CL (sigId 3), prValid',
                        'external': 'GPS C1C/C2W; L2 tracking code differs'},
            'time_basis': ('5 Hz packet order with short RAWX gaps inferred; anchored to '
                           'first pre-test receiver GPST; no independent capture clock'
                           if recover_corrupt else
                           '5 Hz packet order anchored to first pre-test receiver GPST; no independent capture clock'),
            'first_receiver_gpst': epochs[0]['receiver_time'].isoformat(),
            'last_receiver_gpst': epochs[-1]['receiver_time'].isoformat(),
            'last_inferred_capture_gpst_s': grid_status.get(
                'last_inferred_capture_gpst_s', round(first_s + (len(epochs) - 1) / 5, 3)),
            'endpoint_receiver_minus_inferred_s': round(
                (epochs[-1]['receiver_time'] - datetime.combine(day, datetime.min.time())).total_seconds()
                - grid_status.get('last_inferred_capture_gpst_s',
                                  first_s + (len(epochs) - 1) / 5), 3),
            'raw_status': raw_status, 'grid_status': grid_status,
            'receiver_time_discontinuities': jumps,
            'official_log': {'source_url': extract['source_url'],
                             'source_sha256': extract['source_sha256'],
                             'extract_sha256': sha256(windows_path)},
            'official_windows': windows,
            'window_coverage_by_inferred_capture_time':
                {key: dict(sorted(value.items())) for key, value in counts.items()},
            'stations': {name: {'file_sha256': hashes[name], 'status': external_status[name]}
                         for name in stations},
            'missing_simultaneous_satellite': missing,
            'paired_count': len(paired), 'paired_epoch_count': len({row['time_s'] for row in paired}),
            'scope': 'Recovered raw code and clock behavior; no detector threshold, attack attribution or independent absolute time.'}


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
    args = parser.parse_args()
    report = run(args.archive, args.rawx_member,
                 {args.station_a.name.split('_')[0]: args.station_a,
                  args.station_b.name.split('_')[0]: args.station_b},
                 args.day_gpst, args.windows, recover_corrupt=args.recover_corrupt)
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(report, destination, indent=2, allow_nan=False)
        destination.write('\n')
