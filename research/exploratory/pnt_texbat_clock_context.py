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
from pathlib import Path
from statistics import median
from types import SimpleNamespace

import hatanaka
import numpy as np

from positioning.calibration import antenna_position, reference_model
from pnt.model import broadcast_navigation, fit_clock
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
    """Reuse the shared fit while preserving this study's summary schema."""
    result = fit_clock(codes, position, records, tow - context.sow_midnight,
                       context, model=reference_model)
    return {key: result[key] for key in (
        'clock_m', 'median_absolute_satellite_residual_m',
        'max_absolute_satellite_residual_m')}


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
