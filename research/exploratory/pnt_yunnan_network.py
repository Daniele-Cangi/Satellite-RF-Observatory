"""Exposed Yunnan C1C comparison at native receiver epochs; no attack verdict."""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from pnt.fixed_site import evaluate_epoch, read_station
from pnt.model import broadcast_navigation, day_context
from pnt.ublox import pair_navigation, rawx_gps_l1
from .pnt_yunnan_intake import INPUTS, WINDOWS, load_streams


DAY = date(2023, 12, 21)
REFERENCE_FILES = {name: f'{name}00{country}_R_20233550000_01D_30S_MO.crx.gz'
                   for name, country in (('JFNG', 'CHN'), ('CUSV', 'THA'))}
NAV_FILE = 'brdc3550.23n.gz'
# One-second local sampling: only an unambiguous nearest native observation
# within half that interval. This is association, not a claimed error budget.
MAX_PAIR_OFFSET_S = 0.5


def paper_position():
    """WGS84 ECEF from published coordinate; never from the victim's PVT."""
    lat, lon = np.deg2rad([25.0571632, 102.6987051])
    a, e2, height = 6378137., 6.6943799901413165e-3, 1896.
    n = a / np.sqrt(1 - e2 * np.sin(lat)**2)
    return np.array([(n + height) * np.cos(lat) * np.cos(lon),
                     (n + height) * np.cos(lat) * np.sin(lon),
                     (n * (1 - e2) + height) * np.sin(lat)])


def nearest_native(times, grid, tolerance=MAX_PAIR_OFFSET_S):
    """Return one nearest source index, refusing ties and out-of-bound epochs."""
    index = bisect_left(times, grid)
    candidates = [i for i in (index - 1, index) if 0 <= i < len(times)]
    if not candidates:
        return None, 'MISSING_NATIVE_EPOCH'
    distance = min(abs(times[i] - grid) for i in candidates)
    if distance > tolerance:
        return None, 'OUTSIDE_NATIVE_ASSOCIATION_INTERVAL'
    chosen = [i for i in candidates if abs(abs(times[i] - grid) - distance) < 1e-9]
    if len(chosen) != 1:
        return None, 'AMBIGUOUS_NATIVE_EPOCH'
    selected = chosen[0]
    if ((selected and times[selected - 1] == times[selected]) or
            (selected + 1 < len(times) and times[selected + 1] == times[selected])):
        return None, 'AMBIGUOUS_NATIVE_EPOCH'
    return selected, 'ASSOCIATED'


def window_name(host_label):
    clock = host_label[11:]
    return next(name for name, start, stop in WINDOWS if start <= clock < stop)


def metric_summary(epochs):
    evaluated = [e for e in epochs if e['diagnostic']['matched']['status'] == 'EVALUATED']
    local, network, combined = [], [], []
    for epoch in evaluated:
        matched = epoch['diagnostic']['matched']
        pivot = matched['difference_reference_satellite']
        fits = matched['receiver_fits']
        local.append(max(abs(value - fits['local']['satellite_residuals_m'][pivot])
                         for value in fits['local']['satellite_residuals_m'].values()))
        network.append(matched['reference_disagreement']['CUSV/JFNG'][
            'max_absolute_satellite_difference_m'])
        combined.append(max(map(abs, matched['mean_double_difference_residuals_m'].values())))
    def describe(values):
        return None if not values else {'median_m': float(np.median(values)), 'maximum_m': max(values)}
    return {'selected_epochs': len(epochs), 'evaluated_matched_epochs': len(evaluated),
            'local_satellite_difference': describe(local),
            'remote_pair_disagreement': describe(network),
            'combined_mean_double_difference': describe(combined),
            'combined_residual_smaller_epochs': sum(c < l for c, l in zip(combined, local)),
            'combined_residual_larger_epochs': sum(c > l for c, l in zip(combined, local))}


def run(inputs=INPUTS):
    streams, _ = load_streams(inputs)
    context = day_context(DAY)
    positions, references, sources = {'local': paper_position()}, {}, {}
    for name, filename in REFERENCE_FILES.items():
        codes, positions[name], sources[name] = read_station(inputs / filename, DAY, signals=('C1C',))
        references[name] = defaultdict(dict)
        for (time, sv), value in codes.items():
            references[name][time][sv] = value
        sources[name]['archive_path'] = '/bkg/gnss/data/daily/2023/355/' + filename
        sources[name]['distribution'] = 'https://gssc.esa.int/webftp/login.html'
        sources[name]['distance_to_paper_coordinate_m'] = float(np.linalg.norm(
            positions[name] - positions['local']))
    if len({source['marker_name'] for source in sources.values()}) != 2:
        raise ValueError('two distinct reference markers required')
    nav_bytes = (inputs / NAV_FILE).read_bytes()
    nav, counts = broadcast_navigation(nav_bytes)
    sources['navigation'] = {'file': NAV_FILE, 'sha256': hashlib.sha256(nav_bytes).hexdigest(),
                             'url': 'https://noaa-cors-pds.s3.amazonaws.com/rinex/2023/355/' + NAV_FILE,
                             'record_status': counts}
    sources['local'] = {'file': 'receiver_messages.tar.gz',
                        'sha256': hashlib.sha256((inputs / 'receiver_messages.tar.gz').read_bytes()).hexdigest(),
                        'antenna_ecef_m': positions['local'].tolist(),
                        'position_source': 'paper latitude/longitude/ellipsoidal height; survey error unspecified'}
    native, audit, navigation_pairs = [], [], {}
    for hour, kinds in streams.items():
        pairs = pair_navigation(kinds['NAV-PVT'].items(), kinds['NAV-CLOCK'].items())
        navigation_pairs[hour] = {'status_counts': dict(Counter(p['status'] for p in pairs)), 'epochs': pairs}
        for label, message in sorted(kinds['RXM-RAWX'].items()):
            parsed = rawx_gps_l1(message)
            time = (parsed['receiver_local_gpst'] - context.day).total_seconds()
            status = 'WITHIN_DECLARED_DAY' if 0 <= time < 86400 else 'OUTSIDE_DECLARED_DAY'
            audit.append({'source_label': label, 'week': parsed['week'], 'rcvTow': parsed['rcvTow'],
                          'message_start_time': message['start_time'], 'clock_reset': message['clkReset'],
                          'status': status, 'code_dispositions': parsed['dispositions']})
            if status == 'WITHIN_DECLARED_DAY':
                native.append((time, label, parsed, message['clkReset']))
    native.sort(key=lambda item: (item[0], item[1]))
    times = [row[0] for row in native]
    epochs = []
    for start, stop in ((14430, 18030), (36030, 39630)):
        for grid in range(start, stop, 30):
            index, status = nearest_native(times, grid)
            observations = {'local': {}, **{name: rows.get(grid, {}) for name, rows in references.items()}}
            receiver_times = {name: float(grid) for name in observations}
            epoch = {'reference_grid_gpst_s': grid, 'association_status': status}
            if index is not None:
                time, label, parsed, reset = native[index]
                # Keep the shared engine's tuple representation for C1C.
                observations['local'] = {sv: (code,) for sv, code in parsed['codes'].items()}
                receiver_times['local'] = time
                epoch.update(local_source_label=label, metadata_window=window_name(label),
                             local_minus_reference_tag_s=time - grid, local_clock_reset=reset)
            epoch['diagnostic'] = evaluate_epoch(
                grid, observations, positions, nav, context,
                code_transform=lambda codes: {sv: values[0] for sv, values in codes.items()},
                receiver_times=receiver_times)
            epochs.append(epoch)
    return {'schema': 'pnt-yunnan-native-network-v1', 'scope': 'EXPOSED_EXPLORATORY_DIAGNOSTIC',
            'day_gpst': DAY.isoformat(), 'sources': sources,
            'association': {'maximum_native_to_reference_tag_s': MAX_PAIR_OFFSET_S,
                            'interpolation': 'none; original code and measurement tag retained',
                            'rawx_to_navigation': 'NOT_ESTABLISHED; rcvTow and iTOW have different clock semantics',
                            'time_uncertainty': 'UNQUALIFIED; association interval is not physical timing accuracy'},
            'native_status_counts': dict(Counter(row['status'] for row in audit)),
            'navigation_pairing': navigation_pairs,
            'coverage': {'requested_reference_epochs': len(epochs),
                         'association_status_counts': dict(Counter(e['association_status'] for e in epochs)),
                         'matched_status_counts': dict(Counter(e['diagnostic']['matched']['status'] for e in epochs))},
            'comparison': {'metric': 'maximum absolute satellite difference relative to the minimum common GPS PRN',
                           'selection': 'identical common satellites and evaluated epochs for all three summaries',
                           'reference_grid_windows_gpst_s': [[14430, 18030], [36030, 39630]],
                           'unassigned_metadata_window_epochs': sum('metadata_window' not in e for e in epochs),
                           **metric_summary(epochs)},
            'table13_windows': {name: metric_summary([e for e in epochs if e.get('metadata_window') == name])
                                for name, _, _ in WINDOWS},
            'assessments': {'network_detection_gain': 'NOT_ASSESSED', 'rf_authenticity': 'NOT_ASSESSED',
                            'absolute_time': 'INSUFFICIENT_EVIDENCE', 'false_alarm_rate': 'NOT_ASSESSED'},
            'limits': ['Receiver time is not an independent acquisition clock; date excursions are never repaired.',
                       'Paper coordinate and native-to-grid time uncertainty are unqualified.',
                       'GPS C1C: ionosphere, TGD and receiver code biases remain uncorrected.',
                       'Distant witnesses do not qualify spatial transfer of local propagation errors.',
                       'Identical common satellites/epochs support diagnostic comparisons, not calibrated detection.',
                       'Table 13 records transmitter activity, not receiver attack success; outside intervals are not certified benign.',
                       'Distinct receivers share archive distribution and GNSS products; no independence or RF origin claim.'],
            'native_epoch_audit': audit, 'epochs': epochs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    encoded = (json.dumps(run(), indent=2, allow_nan=False) + '\n').encode('utf-8')
    with args.output.open('xb') as destination:
        destination.write(gzip.compress(encoded, mtime=0) if args.output.suffix == '.gz' else encoded)
