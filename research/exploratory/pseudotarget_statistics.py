"""Descriptive differential RF summaries; no independent-sample inference."""
from collections import Counter, defaultdict
from itertools import combinations
import numpy as np


def moments(values):
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {'count': 0, 'mean_m': None, 'rms_m': None, 'max_abs_m': None}
    return {'count': len(a), 'mean_m': float(a.mean()),
            'rms_m': float(np.sqrt(np.mean(a*a))), 'max_abs_m': float(abs(a).max())}


def correlation(pairs, minimum):
    if len(pairs) < minimum:
        return {'count': len(pairs), 'status': 'INSUFFICIENT_PAIRS', 'pearson': None}
    a = np.array(pairs, dtype=float)
    a -= a.mean(axis=0)
    den = float(np.linalg.norm(a[:, 0])*np.linalg.norm(a[:, 1]))
    if den < 1e-12:
        return {'count': len(pairs), 'status': 'ZERO_VARIANCE', 'pearson': None}
    return {'count': len(pairs), 'status': 'DESCRIPTIVE',
            'pearson': float(np.clip(a[:, 0]@a[:, 1]/den, -1, 1))}


def summarize(rows, plan):
    result = {}
    for model in plan['models']:
        good = [r for r in rows if r['models'].get(model, {}).get('status') == 'EVALUATED']
        links, blocks = defaultdict(dict), defaultdict(list)
        for r in good:
            value = r['models'][model]['error_m']
            links[(r['pseudo_target'], r['station'])][r['time_s']] = value
            blocks[(r['pseudo_target'], r['time_s'])].append(value)
        lag = []
        for (sv, station), series in sorted(links.items()):
            for dt in plan['lag_seconds']:
                pairs = [(v, series[t+dt]) for t, v in sorted(series.items()) if t+dt in series]
                lag.append({'pseudo_target': sv, 'station': station, 'lag_s': dt,
                            **correlation(pairs, plan['minimum_correlation_pairs'])})
        cross = []
        for sv in sorted({sv for sv, _ in links}):
            stations = sorted(s for v, s in links if v == sv)
            for a, b in combinations(stations, 2):
                x, y = links[(sv, a)], links[(sv, b)]
                pairs = [(x[t], y[t]) for t in sorted(x.keys() & y.keys())]
                cross.append({'pseudo_target': sv, 'stations': [a, b],
                              **correlation(pairs, plan['minimum_correlation_pairs'])})
        centered = [v-np.mean(values) for values in blocks.values() if len(values) >= 2 for v in values]
        result[model] = {
            'status_counts': dict(Counter(r['models'].get(model, {}).get('status', r['status']) for r in rows)),
            'raw_differential': moments([r['models'][model]['error_m'] for r in good]),
            'epoch_station_centered': moments(centered),
            'centered_block_count': sum(len(v) >= 2 for v in blocks.values()),
            'per_station': {s: moments([r['models'][model]['error_m'] for r in good if r['station'] == s])
                            for s in sorted({r['station'] for r in rows})},
            'per_pseudo_target': {s: moments([r['models'][model]['error_m'] for r in good if r['pseudo_target'] == s])
                                  for s in sorted({r['pseudo_target'] for r in rows})},
            'lag_correlations': lag, 'cross_station_correlations': cross}
    paired = [r for r in rows if all(r['models'].get(m, {}).get('status') == 'EVALUATED' for m in plan['models'])]
    result['paired'] = {'count': len(paired), 'models': {
        m: moments([r['models'][m]['error_m'] for r in paired]) for m in plan['models']}}
    return result
