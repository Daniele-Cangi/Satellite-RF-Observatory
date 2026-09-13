"""Real archived-data development: omit each calibration reference in turn.

Reads only admitted fit observations and reference-only navigation. No oracle,
historical solution or held-out target values enter this exploratory fit.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from positioning.calibration import calibrate_station, parse_reference_navigation, C
from positioning.context import Context
from positioning.errors import ScientificRejection
from positioning.solver import interpolate_event, solve


def load_inputs(archive):
    root = Path(archive)
    receipt = json.loads((root/'admission_receipt.json').read_bytes())
    paths = {'admitted_sha256': root/'estimation/admitted.json',
             'navigation_sha256': root/'estimation/reference_only.rnx'}
    buffers, hashes = {}, {}
    for key, path in paths.items():
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != receipt[key]:
            raise ValueError('archived input changed: ' + path.name)
        buffers[key], hashes[path.name] = content, digest
    admitted = json.loads(buffers['admitted_sha256'])
    context = Context(**admitted['context'])
    for station in admitted['stations'].values():
        if any(context.target in obs['if_code_m'] for obs in station['reference_observations']):
            raise ValueError('target contamination in calibration inputs')
    navigation = parse_reference_navigation(buffers['navigation_sha256'].decode('ascii'), context.target)
    return admitted, context, navigation, hashes


def remove_reference(observations, excluded):
    return [dict(obs, if_code_m={sv: code for sv, code in obs['if_code_m'].items()
                                if sv != excluded}) for obs in observations]


def fit_variant(admitted, context, calibration):
    names = admitted['fit_stations']
    if any(calibration[name]['status'] != 'CALIBRATION_QUALIFIED' for name in names):
        return {'status': 'CALIBRATION_REJECTED'}
    codes = np.array([admitted['stations'][name]['target_if_codes_m'] for name in names])
    positions = np.array([admitted['stations'][name]['antenna_ecef_m'] for name in names])
    clocks = np.array([[epoch['clock_m'] for epoch in calibration[name]['epochs']] for name in names])
    times = np.asarray(context.times)-context.central_s
    event = interpolate_event(codes, clocks, positions, times_s=times)
    control = interpolate_event(codes, clocks, positions, u0=event['u0'], degree=5, times_s=times)
    difference = float(np.max(np.abs(event['z']-control['z'])))
    if difference > 2:
        return {'status': 'INTERPOLATION_REJECTED', 'interpolation_control_max_m': difference}
    # Fixed weights isolate calibration choice; do not recompute historical
    # uncertainty or use historical fit/oracle values as seeds or a benchmark.
    fitted = solve(event['z'], event['positions'], np.eye(len(names))*20.**2)
    residual = float(np.max(np.abs(fitted['residuals'])))
    status = 'ESTIMATED' if not fitted['ambiguous'] and residual <= 100 else 'FIT_REJECTED'
    return {'status': status, 'xyz_m': fitted['q'][:3].tolist(), 'B_m': float(fitted['q'][3]),
            'u0_relative_s': float(event['u0']), 'fit_residual_max_m': residual,
            'interpolation_control_max_m': difference, 'ambiguous': bool(fitted['ambiguous']),
            'branches': fitted['branches']}


def run(archive, *, progress=None):
    start = time.perf_counter()
    admitted, context, navigation, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    baseline_cal = {}
    for name in names:
        station = admitted['stations'][name]
        baseline_cal[name] = calibrate_station(station['reference_observations'],
                                               np.array(station['antenna_ecef_m']), navigation, context)
    references = sorted({sv for cal in baseline_cal.values() for epoch in cal['epochs']
                         for sv in epoch['references']})
    cases, baseline = [], None
    # Complete leave-one-reference-out set, determined without variant results.
    for excluded in [None]+references:
        began = time.perf_counter()
        row = {'excluded_reference': excluded, 'delta_xyz_m': None,
               'displacement_from_baseline_m': None, 'delta_B_m': None,
               'emission_time_change_ns': None}
        calibration = dict(baseline_cal)
        try:
            if excluded is not None:
                for name in names:
                    if not any(excluded in epoch['references'] for epoch in baseline_cal[name]['epochs']):
                        continue
                    station = admitted['stations'][name]
                    calibration[name] = calibrate_station(remove_reference(station['reference_observations'], excluded),
                        np.array(station['antenna_ecef_m']), navigation, context)
            row['calibration'] = {}
            for name, cal in calibration.items():
                old = {epoch['time_s']: epoch for epoch in baseline_cal[name]['epochs']}
                changes = [epoch['clock_m']-old[epoch['time_s']]['clock_m']
                           for epoch in cal['epochs'] if epoch['time_s'] in old]
                row['calibration'][name] = {
                    'status': cal['status'], 'failures': cal['failures'],
                    'clock_change_max_abs_m': max(map(abs, changes), default=None),
                    'epochs': [{key: epoch[key] for key in ('time_s', 'references', 'clock_m',
                                'rms_m', 'split_clock_m', 'ground_offset_m')} for epoch in cal['epochs']],
                }
            row.update(fit_variant(admitted, context, calibration))
            if excluded is None and row['status'] == 'ESTIMATED':
                baseline = row
            if baseline is not None and row['status'] == 'ESTIMATED':
                if row['u0_relative_s'] != baseline['u0_relative_s']:
                    raise ValueError('comparison frame/event tag changed')
                delta = np.array(row['xyz_m'])-baseline['xyz_m']
                row.update(delta_xyz_m=delta.tolist(), displacement_from_baseline_m=float(np.linalg.norm(delta)),
                           delta_B_m=row['B_m']-baseline['B_m'],
                           emission_time_change_ns=(row['B_m']-baseline['B_m'])/C*1e9)
        except ScientificRejection as error:
            row.update(status='FIT_REJECTED', reason=str(error))
        except Exception as error:
            row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__+': '+str(error))
        row['runtime_seconds'] = time.perf_counter()-began
        cases.append(row)
        if progress:
            progress({key: row.get(key) for key in ('excluded_reference', 'status',
                      'displacement_from_baseline_m', 'reason')})
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__)]+[root/'positioning'/name for name in
               ('calibration.py', 'context.py', 'navigation.py', 'solver.py', 'errors.py')]
    return {'schema': 'exploratory-reference-sensitivity-v1',
            'scope': 'Development reuse of exposed real observations; not new confirmation or accuracy/coverage measurement.',
            'target': context.target, 'date_gpst': context.date_gpst, 'times_gpst_s': list(context.times),
            'fit_stations': names, 'input_sha256': hashes,
            'sources_sha256': {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in sources},
            'method': 'Baseline plus omission of every selected reference across all fit stations. Fixed target codes, roots, window and 20 m equal weights. Original calibration and fit checks retained. No historical solution, oracle, holdout or prospective uncertainty evaluation.',
            'frame': 'Same terrestrial axes at the shared u0; fitted emission time may change with B. Differences are state sensitivity, not same-time truth error.',
            'target_orbit_accessed': False, 'new_confirmation': False,
            'baseline_status': cases[0]['status'], 'case_count': len(cases),
            'status_counts': dict(Counter(row['status'] for row in cases)),
            'runtime_seconds': time.perf_counter()-start, 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('choose a new development output; existing results are preserved')
    result = run(args.archive, progress=lambda row: print(json.dumps(row), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
