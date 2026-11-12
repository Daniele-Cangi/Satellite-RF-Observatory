"""Exploratory code-only DD contribution from a shared-antenna GPS recording."""

import argparse
from collections import Counter
import hashlib
from itertools import combinations
import math
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile

import numpy as np

from .integer_phase_feasibility import MW_FIELD_ROW
from .known_wide_lane import write
from .real_phase import parse_reference_fields
from .reference_mw_stability import complete_blocks

HOURS = (0, 12)
WINDOW_S = 300
STATIONS = ('WUT000POL', 'WUT100POL')
REFERENCES = tuple(f'G{number:02d}' for number in range(1, 33) if number != 12)
DATASET = 'https://doi.org/10.5281/zenodo.15118153'


def read_hour(cache, station, hour):
    stem = f'{station}_R_2024068'
    name = f'{stem}{hour:02d}00_01H_01S_MO.rnx'
    prefix = cache / (name + '.prefix')
    if prefix.is_file():
        raw = prefix.read_bytes()
    else:
        with ZipFile(cache / f'{stem}.zip') as archive:
            raw = archive.read(f'{stem}/{name}')
        boundary = re.search(fr'^> 2024 03 08 {hour:02d} 05\s+0\.0+'.encode(), raw, re.M)
        if boundary is None:
            raise ValueError(f'{name}: missing end of the selected RINEX window')
        raw = raw[:boundary.start()]
    source = {'member': name, 'window_sha256': hashlib.sha256(raw).hexdigest()}
    plan = {'references': REFERENCES, 'target_excluded': 'G12', 'step_s': 1,
            'date_gpst': '2024-03-08', 'start_gpst_s': hour * 3600, 'samples': WINDOW_S}
    parsed = parse_reference_fields(raw.decode('ascii'), plan)
    source['receiver'] = parsed['receiver']
    code = {(row['reference'], row['time_s']): row['fields'][:2]
            for row in parsed['rows'] if row['time_s'] % 30 == 0
            and all(value is not None and value > 0. for value in row['fields'][:2])}
    return source, code


def code_series(left, right):
    """Single receiver difference in MW cycles, with no carrier input."""
    return {key: math.fsum(float(weight) * (a - b)
                           for weight, a, b in zip(MW_FIELD_ROW[:2], left[key], right[key], strict=True))
            for key in left.keys() & right.keys()}


def summarize(hour, left, right):
    series = code_series(left, right)
    start = hour * 3600
    rows, counts = [], Counter()
    for q, p in combinations(REFERENCES, 2):
        points = [(t, series[q, t] - series[p, t]) for t in range(start, start + WINDOW_S, 30)
                  if (q, t) in series and (p, t) in series]
        full, partial = complete_blocks(points)
        counts.update(complete=len(full), partial=len(partial), missing=1-len(full)-len(partial))
        if full or partial:
            rows.append({'pair': [q, p], 'full': full, 'partial': partial})
    means = [block['mean_cycles'] for row in rows for block in row['full']]
    quantiles = [float(x) for x in np.quantile(np.abs(means), [.5, .95, 1.])] if means else None
    return {'hour_gpst': hour, 'block_counts': counts,
            'absolute_block_mean_median_p95_max_cycles': quantiles,
            'abs_block_mean_above_point_one_cycles': sum(abs(mean) > .1 for mean in means),
            'rows': rows}


def run(cache, output):
    windows = []
    for hour in HOURS:
        try:
            left_source, left = read_hour(cache, STATIONS[0], hour)
            right_source, right = read_hour(cache, STATIONS[1], hour)
        except (OSError, ValueError, KeyError, BadZipFile) as error:
            windows.append({'hour_gpst': hour, 'status': 'UNAVAILABLE', 'reason': str(error)})
        else:
            inputs = [
                {**source, 'code_m': [[sv, t, *code[sv, t]] for sv, t in sorted(code)]}
                for source, code in ((left_source, left), (right_source, right))
            ]
            windows.append({'status': 'MEASURED', 'inputs': inputs,
                            **summarize(hour, left, right)})
    write(output, {'dataset': DATASET, 'scope': 'code contribution only',
                   'station_order': STATIONS, 'gps_allowlist': REFERENCES,
                   'window_seconds': WINDOW_S, 'windows': windows})
    return windows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a fresh file')
    for window in run(args.cache, args.output):
        print({key: value for key, value in window.items() if key not in ('rows', 'inputs')})
