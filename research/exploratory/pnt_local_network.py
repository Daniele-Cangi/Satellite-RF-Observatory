"""Exposed-data PNT contrast: fixed receiver, external witnesses, and their difference.

This consumes the existing excluded-reference pseudo-target report. Its orbit
model is a declared hypothesis, not an independent reconstruction or RF attack
recording. Additive perturbations below operate on calibrated residuals; they
test observable modes, not a receiver's complete tracking response.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
from statistics import median


BASE = Path(__file__).parent
SOURCE = BASE / 'results/pseudotarget_v1.json'
MODES = ('local', 'network', 'combined')
TRAIN_BEFORE_S = 38700  # 10:45 GPST; the source report covers 10:30–11:00.


def nearest_rank(values, proportion):
    """An explicitly empirical threshold, with no independence/coverage claim."""
    if not values or not 0 < proportion <= 1:
        raise ValueError('nonempty values and 0 < proportion <= 1 required')
    ordered = sorted(values)
    return ordered[math.ceil(proportion * len(ordered)) - 1]


def samples(rows, victim, stations, minimum_witnesses=2):
    """Pair only the same satellite and GPST epoch; keep failure counts."""
    if victim not in stations or minimum_witnesses < 1:
        raise ValueError('invalid receiver or witness requirement')
    values = {}
    failures = Counter()
    for row in rows:
        station, satellite, time = row['station'], row['pseudo_target'], row['time_s']
        if station not in stations:
            raise ValueError('unrecognized receiver')
        key = satellite, time, station
        if key in values:
            raise ValueError('duplicate pseudo-target observation')
        result = row.get('models', {}).get('zero', {})
        if result.get('status') == 'EVALUATED':
            value = float(result['error_m'])
            if not math.isfinite(value):
                raise ValueError('nonfinite pseudo-target residual')
            values[key] = value
        else:
            failures[result.get('status', row['status'])] += 1
    paired = []
    for satellite, time, station in sorted(values):
        if station != victim:
            continue
        witnesses = [values[(satellite, time, peer)] for peer in stations
                     if peer != victim and (satellite, time, peer) in values]
        if len(witnesses) < minimum_witnesses:
            failures['INSUFFICIENT_SIMULTANEOUS_WITNESSES'] += 1
            continue
        local, network = values[(satellite, time, victim)], median(witnesses)
        paired.append({'satellite': satellite, 'time_s': time,
                       'local_m': local, 'network_m': network,
                       'combined_m': local - network,
                       'witness_count': len(witnesses)})
    return paired, dict(sorted(failures.items()))


def analyze(rows, victim, stations, train_before_s=TRAIN_BEFORE_S,
            minimum_training_per_satellite=5, proportion=0.99,
            perturbations_m=(5., 10., 25.)):
    paired, failures = samples(rows, victim, stations)
    training = [r for r in paired if r['time_s'] < train_before_s]
    testing = [r for r in paired if r['time_s'] >= train_before_s]
    by_satellite = defaultdict(list)
    for row in training:
        by_satellite[row['satellite']].append(row)
    supported = {sv for sv, records in by_satellite.items()
                 if len(records) >= minimum_training_per_satellite}
    training = [r for r in training if r['satellite'] in supported]
    unsupported_test = sum(r['satellite'] not in supported for r in testing)
    testing = [r for r in testing if r['satellite'] in supported]
    if not training or not testing:
        raise ValueError('no supported chronological training/test pair')
    baseline = {sv: {mode: median(r[mode+'_m'] for r in records)
                     for mode in MODES}
                for sv, records in by_satellite.items() if sv in supported}
    def score(row, mode):
        return row[mode+'_m'] - baseline[row['satellite']][mode]
    thresholds = {mode: nearest_rank([abs(score(r, mode)) for r in training], proportion)
                  for mode in MODES}
    def count_alerts(rows, mode, shift=0.):
        return sum(abs(score(r, mode) + shift) > thresholds[mode] for r in rows)
    controls = {mode: {'threshold_m': thresholds[mode],
                       'training_alerts': count_alerts(training, mode),
                       'clean_test_alerts': count_alerts(testing, mode)}
                for mode in MODES}
    perturbations = []
    for offset in perturbations_m:
        if offset <= 0 or not math.isfinite(offset):
            raise ValueError('perturbation must be positive and finite')
        for scenario, shifts in (
            ('local_satellite_code', {'local': offset, 'network': 0., 'combined': offset}),
            ('shared_satellite_code', {'local': offset, 'network': offset, 'combined': 0.}),
            ('local_common_clock', dict.fromkeys(MODES, 0.)),
        ):
            perturbations.append({'scenario': scenario, 'offset_m': offset,
                                  'test_alerts': {mode: count_alerts(testing, mode, shifts[mode])
                                                  for mode in MODES}})
    return {'schema': 'pnt-local-network-exploratory-v1', 'victim': victim,
            'stations': list(stations), 'train_before_gpst_s': train_before_s,
            'threshold_method': f'nearest-rank training |score| at {proportion}',
            'minimum_training_per_satellite': minimum_training_per_satellite,
            'minimum_simultaneous_witnesses': 2,
            'source_row_count': len(rows), 'source_status_counts': dict(sorted(Counter(
                r.get('models', {}).get('zero', {}).get('status', r['status']) for r in rows).items())),
            'pairing_failures': failures, 'paired_count': len(paired),
            'training_count': len(training), 'test_count': len(testing),
            'unsupported_test_count': unsupported_test,
            'supported_satellites': sorted(supported),
            'test_witness_count_range': [min(r['witness_count'] for r in testing),
                                         max(r['witness_count'] for r in testing)],
            'controls': controls, 'perturbations': perturbations,
            'scope': ('Exposed reference-only GPS code; known reference orbits and site coordinates; '
                      'calibrated residual perturbations, not recorded spoofing; no independent absolute time.')}


def run(source=SOURCE, victim='ALGO00CAN'):
    source_bytes = Path(source).read_bytes()
    report = json.loads(source_bytes)
    if (report.get('schema') != 'reference-pseudotarget-v1' or
            report.get('real_target_fit') is not False or
            report.get('real_target_orbit_accessed') is not False):
        raise ValueError('source must be the excluded-reference exploratory report')
    stations = report['baseline_plan']['stations']
    primary = analyze(report['rows'], victim, stations)
    rotations = {}
    for station in stations:
        if station == victim:
            continue
        result = analyze(report['rows'], station, stations)
        rotations[station] = {'test_count': result['test_count'],
                              'clean_test_alerts': {mode: result['controls'][mode]['clean_test_alerts']
                                                    for mode in MODES},
                              'local_code_10m_test_alerts': next(p['test_alerts'] for p in result['perturbations']
                                  if p['scenario'] == 'local_satellite_code' and p['offset_m'] == 10.),
                              'shared_code_10m_test_alerts': next(p['test_alerts'] for p in result['perturbations']
                                  if p['scenario'] == 'shared_satellite_code' and p['offset_m'] == 10.)}
    return primary | {'source_sha256': hashlib.sha256(source_bytes).hexdigest(),
                      'station_rotations': rotations}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--victim', default='ALGO00CAN')
    args = parser.parse_args()
    result = run(victim=args.victim)
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        json.dump(result, output, indent=2, allow_nan=False)
        output.write('\n')
