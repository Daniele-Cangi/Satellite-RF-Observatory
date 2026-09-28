"""Exposed TEXBAT/NOAA receiver-clock contrast using one broadcast orbit model.

The local-only and local-minus-network channels use the same GPS ephemerides,
fixed local coordinate, epochs and satellite set. No independent time witness,
prospective detector threshold or spoofing-attribution claim is supplied.
"""

import argparse
from collections import Counter, defaultdict
from datetime import timezone
import gzip
import json
import math
from pathlib import Path
from statistics import median
from types import SimpleNamespace

import hatanaka
import numpy as np

from positioning.calibration import antenna_position, reference_model
from positioning.navigation import parse_gps_record
from .pnt_texbat_noaa import (DAY, GPS_EPOCH, GPS_WEEK, channel_rows, digest,
                               paired_codes, preattack_anchor, rinex2_c1_text,
                               select_gps_code)


# Published cleanStatic mean ECEF solution, never fitted from attacked ds7.
# Lemmenes et al., ION GNSS+ 2016, Fig. 2. It is not a surveyed coordinate.
LOCAL_ECEF_M = np.array([-741992.74, -5462240.48, 3198027.11])
LOCAL_POSITION_SOURCE = 'https://radionavlab.ae.utexas.edu/images/stories/files/papers/LemmenesGNSSpaper.pdf'
SOURCE_DAY = DAY.date().isoformat()
SOW_MIDNIGHT = ((DAY - GPS_EPOCH).days % 7) * 86400
MAX_NAV_AGE_S = 7200


def broadcast_navigation(data):
    """Adapt a complete NOAA RINEX 2 GPS NAV file to the shared record parser."""
    lines = gzip.decompress(data).decode('ascii').splitlines()
    stop = next((i for i, line in enumerate(lines) if line[60:80].strip() == 'END OF HEADER'), None)
    if stop is None:
        raise ValueError('incomplete GPS navigation header')
    version = [line[:60] for line in lines[:stop] if line[60:80].strip() == 'RINEX VERSION / TYPE']
    if len(version) != 1 or not 2 <= float(version[0][:9]) < 3 or 'GPS NAV DATA' not in version[0]:
        raise ValueError('expected one RINEX 2 GPS navigation header')
    body = lines[stop + 1:]
    if not body or len(body) % 8:
        raise ValueError('truncated GPS navigation record')
    records, counts = defaultdict(list), Counter()
    for start in range(0, len(body), 8):
        block = body[start:start + 8]
        fields = block[0][:22].split()
        if len(fields) != 7 or any(not line.startswith('   ') for line in block[1:]):
            raise ValueError('invalid RINEX 2 GPS navigation block')
        prn, yy, month, day, hour, minute = (int(value) for value in fields[:6])
        second = float(fields[6])
        if not 1 <= prn <= 32 or not math.isfinite(second) or second != int(second):
            raise ValueError('unsupported GPS navigation epoch or PRN')
        year = 2000 + yy if yy < 80 else 1900 + yy
        prefix = f'G{prn:02d} {year:04d} {month:02d} {day:02d} {hour:02d} {minute:02d} {int(second):02d}'
        if len(prefix) != 23:
            raise ValueError('invalid GPS navigation epoch width')
        normalized = [prefix + block[0][22:]] + [' ' + line for line in block[1:]]
        record = parse_gps_record(normalized)
        counts['source_records'] += 1
        if record.sv_health != 0 or not 0 <= record.eccentricity < 1 or record.sqrt_a_m_sqrt <= 0:
            counts['unhealthy_or_invalid_records'] += 1
            continue
        records[record.satellite].append(record)
        counts['admitted_records'] += 1
    if not records:
        raise ValueError('no usable GPS navigation records')
    return records, dict(sorted(counts.items()))


def station_codes_and_position(data, station):
    """Decode one NOAA source once; retain C1 and its declared antenna point."""
    content = hatanaka.decompress(gzip.decompress(data), strict=True).decode('ascii')
    codes, counts = rinex2_c1_text(content, station)
    header = defaultdict(list)
    for line in content.splitlines():
        label = line[60:80].strip()
        header[label].append(line[:60])
        if label == 'END OF HEADER':
            break
    if any(len(header[key]) != 1 for key in ('APPROX POSITION XYZ', 'ANTENNA: DELTA H/E/N')):
        raise ValueError('ambiguous NOAA antenna coordinate')
    position = antenna_position(header)
    if not np.isfinite(position).all():
        raise ValueError('nonfinite NOAA antenna coordinate')
    return codes, position, counts


def chosen_records(nav, prns, tow, context):
    """Use the nearest healthy toc per common satellite, within two hours."""
    t = tow - context.sow_midnight
    selected = {}
    for prn in sorted(prns):
        sv = f'G{prn:02d}'
        candidates = nav.get(sv, ())
        if not candidates:
            raise ValueError(f'{sv}: no healthy broadcast ephemeris')
        record = min(candidates, key=lambda candidate: abs((candidate.toc_gps - context.day).total_seconds() - t))
        age = abs((record.toc_gps - context.day).total_seconds() - t)
        if age > MAX_NAV_AGE_S or record.gps_week != GPS_WEEK:
            raise ValueError(f'{sv}: stale or wrong-week broadcast ephemeris')
        selected[prn] = record
    return selected


def fitted_clock(codes, position, records, tow, context):
    """Median common-mode code residual at a fixed coordinate, in metres."""
    if set(codes) != set(records) or len(codes) < 4:
        raise ValueError('incomplete common satellite set for clock fit')
    t = tow - context.sow_midnight
    clock = 0.0
    estimates = None
    for _ in range(6):
        estimates = np.array([codes[prn] - reference_model(records[prn], codes[prn], t,
                                                          position, clock, context)[0]
                              for prn in sorted(codes)])
        updated = float(np.median(estimates))
        if abs(updated - clock) < 1e-6:
            clock = updated
            break
        clock = updated
    else:
        raise ValueError('receiver clock fit did not converge')
    # Evaluate at the final clock, rather than retaining the previous iterate.
    estimates = np.array([codes[prn] - reference_model(records[prn], codes[prn], t,
                                                      position, clock, context)[0]
                          for prn in sorted(codes)])
    if not np.isfinite(estimates).all():
        raise ValueError('nonfinite clock residual')
    clock = float(np.median(estimates))
    return {'clock_m': clock, 'median_absolute_satellite_residual_m':
            float(np.median(np.abs(estimates - clock))),
            'max_absolute_satellite_residual_m': float(np.max(np.abs(estimates - clock)))}


def evaluate(paired, nav, positions):
    """Fit three receivers on identical satellites, then compare clock channels."""
    # This is a declared all-satellite broadcast hypothesis, not the inverse
    # experiment's target-state estimation. No PRN is excluded from propagation.
    context = SimpleNamespace(target='', day=DAY.replace(tzinfo=timezone.utc),
                              gps_week=GPS_WEEK, sow_midnight=SOW_MIDNIGHT)
    by_epoch = defaultdict(list)
    for row in paired:
        by_epoch[row['gpst_tow_s']].append(row)
    epochs = []
    for tow, rows in sorted(by_epoch.items()):
        phases = {row['phase'] for row in rows}
        if len(phases) != 1:
            raise ValueError('inconsistent TEXBAT segment within an epoch')
        prns = {row['prn'] for row in rows}
        records = chosen_records(nav, prns, tow, context)
        fits = {}
        for name in ('TXAU', 'SAM2', 'cleanStatic', 'ds7'):
            field = {'cleanStatic': 'clean_m', 'ds7': 'ds7_m'}.get(name, name + '_m')
            values = {row['prn']: row[field] for row in rows}
            station = positions[name] if name in positions else LOCAL_ECEF_M
            fits[name] = fitted_clock(values, station, records, tow, context)
        network_clock = (fits['TXAU']['clock_m'] + fits['SAM2']['clock_m']) / 2
        epochs.append({'gpst_tow_s': tow, 'phase': phases.pop(), 'satellites': len(prns),
                       'clock_fit': fits, 'network_clock_m': network_clock,
                       'reference_clock_disagreement_m':
                           fits['TXAU']['clock_m'] - fits['SAM2']['clock_m']})
    pre = [row for row in epochs if row['phase'] == 'preattack']
    attack = [row for row in epochs if row['phase'] == 'time_push']
    if len(pre) < 2 or not attack:
        raise ValueError('insufficient preattack or time-push epochs')
    def centered(name, network=False):
        def value(row):
            local = row['clock_fit'][name]['clock_m']
            return local - row['network_clock_m'] if network else local
        baseline = median(value(row) for row in pre)
        return [value(row) - baseline for row in epochs]
    for name in ('cleanStatic', 'ds7'):
        local = centered(name)
        combined = centered(name, network=True)
        for row, first, second in zip(epochs, local, combined):
            row.setdefault('centered_clock_m', {})[name] = {
                'local_only': first, 'local_minus_network': second}
    network_baseline = median(row['network_clock_m'] for row in pre)
    for row in epochs:
        row['network_only_centered_clock_m'] = row['network_clock_m'] - network_baseline
    def maximum(name, channel, rows):
        return max(abs(row['centered_clock_m'][name][channel]) for row in rows)
    return {
        'epochs': epochs,
        'summary': {
            'preattack_epochs': len(pre), 'time_push_epochs': len(attack),
            'clean_max_absolute_local_only_m': maximum('cleanStatic', 'local_only', epochs),
            'clean_max_absolute_local_minus_network_m': maximum('cleanStatic', 'local_minus_network', epochs),
            'time_push_max_absolute_ds7_local_only_m': maximum('ds7', 'local_only', attack),
            'time_push_max_absolute_ds7_local_minus_network_m': maximum('ds7', 'local_minus_network', attack),
            'max_absolute_reference_clock_disagreement_m':
                max(abs(row['reference_clock_disagreement_m']) for row in epochs),
        },
    }


def run(clean_path, attack_path, txau_path, sam2_path, nav_path):
    paths = {'cleanStatic': clean_path, 'ds7': attack_path, 'TXAU': txau_path,
             'SAM2': sam2_path, 'broadcast_nav': nav_path}
    sources = {name: Path(path).read_bytes() for name, path in paths.items()}
    clean, clean_counts = select_gps_code(channel_rows(sources['cleanStatic']))
    attack, attack_counts = select_gps_code(channel_rows(sources['ds7']))
    anchor, anchor_rows = preattack_anchor(clean, attack)
    txau, txau_pos, txau_counts = station_codes_and_position(sources['TXAU'], 'TXAU')
    sam2, sam2_pos, sam2_counts = station_codes_and_position(sources['SAM2'], 'SAM2')
    paired, pairing_counts = paired_codes(clean, attack, {'TXAU': txau, 'SAM2': sam2}, anchor)
    nav, nav_counts = broadcast_navigation(sources['broadcast_nav'])
    results = evaluate(paired, nav, {'TXAU': txau_pos, 'SAM2': sam2_pos})
    return {
        'schema': 'pnt-texbat-network-clock-exploratory-v1',
        'scope': 'exposed broadcast-model receiver-clock contrast; no absolute-time or detection-gain claim',
        'source_sha256': {name: digest(data) for name, data in sources.items()},
        'local_fixed_ecef_m': LOCAL_ECEF_M.tolist(),
        'local_position_source': LOCAL_POSITION_SOURCE,
        'local_position_status': 'published cleanStatic mean solution; not independent survey',
        'noaa_antenna_ecef_m': {'TXAU': txau_pos.tolist(), 'SAM2': sam2_pos.tolist()},
        'gps_week': GPS_WEEK, 'gpst_day': SOURCE_DAY,
        'rrt_to_gpst_anchor_s': anchor, 'anchor_matched_rows': anchor_rows,
        'source_counts': {'cleanStatic': clean_counts, 'ds7': attack_counts,
                          'TXAU': txau_counts, 'SAM2': sam2_counts, 'broadcast_nav': nav_counts},
        'pairing_counts': dict(sorted(pairing_counts.items())),
        'model': {'source': 'NOAA composite GPS RINEX 2 broadcast NAV',
                  'orbit_and_clock': 'shared positioning.calibration reference_model, nearest healthy toc <= 7200 s',
                  'code': 'GPS L1 code/C1, no TGD or inter-receiver bias correction',
                  'receiver_clock': 'median code-minus-model across identical common PRNs; 6 iterations',
                  'network_clock': 'mean of separately fitted TXAU and SAM2 receiver clocks',
                  'baseline': 'median of two source-defined preattack 30-second epochs'},
        **results,
        'interpretation': [
            'The network channel provides stable contemporaneous clock context but is GNSS-derived, not an independent absolute-time witness.',
            'The ds7 time push is already apparent in the local-only modeled clock; incremental network detection is not demonstrated here.',
            'cleanStatic is a correlated exposed counterfactual, not a representative false-alarm population.',
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('clean', 'attack', 'txau', 'sam2', 'navigation', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = run(args.clean, args.attack, args.txau, args.sam2, args.navigation)
    args.output.write_bytes((json.dumps(report, indent=2, sort_keys=True) + '\n').encode('utf-8'))


if __name__ == '__main__':
    main()
