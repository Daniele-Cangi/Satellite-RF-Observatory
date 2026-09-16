"""Controlled clock-product perturbations on exposed real fit inputs.

The injected amplitudes are not measured product errors or uncertainty bounds.
No target orbit, heldout values or historical solution is read.
"""
import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from positioning.calibration import C, calibrate_station
from positioning.errors import ScientificRejection
from .reference_sensitivity import load_inputs, fit_variant


def shifted_navigation(navigation, references, metres, target):
    """Positive metres means an increase of af0 by metres / c, at every toc."""
    references = set(references)
    if target in navigation or target in references:
        raise ValueError('target navigation is forbidden')
    if not references <= navigation.keys() or not np.isfinite(metres):
        raise ValueError('invalid reference clock perturbation')
    return {sv: [replace(record, af0_s=record.af0_s + metres / C)
                 if sv in references else record for record in records]
            for sv, records in navigation.items()}


def paired_response(baseline, minus, plus, step):
    if step <= 0 or not np.isfinite(step):
        raise ValueError('positive finite step required')
    if any(row['status'] != 'ESTIMATED' for row in (baseline, minus, plus)):
        return {'status': 'NOT_COMPARABLE'}
    if any(row['u0_relative_s'] != baseline['u0_relative_s'] for row in (minus, plus)):
        return {'status': 'FRAME_TAG_CHANGED'}
    q0, qm, qp = [np.array(row['xyz_m'] + [row['B_m']]) for row in (baseline, minus, plus)]
    if not np.isfinite([q0, qm, qp]).all():
        raise ValueError('nonfinite fitted state')
    response = (qp - qm) / (2 * step)
    even = (qp + qm) / 2 - q0
    return {'status': 'COMPARABLE', 'xyz_response_m_per_m': response[:3].tolist(),
            'position_gain_m_per_m': float(np.linalg.norm(response[:3])),
            'B_response_m_per_m': float(response[3]),
            'even_position_response_m': float(np.linalg.norm(even[:3])),
            'even_B_response_m': float(even[3])}


def run(archive, *, progress=None):
    started = time.perf_counter()
    admitted, context, navigation, hashes = load_inputs(archive)
    names = admitted['fit_stations']

    def calibrate(name, nav):
        station = admitted['stations'][name]
        return calibrate_station(station['reference_observations'],
                                 np.array(station['antenna_ecef_m']), nav, context)

    baseline_cal = {name: calibrate(name, navigation) for name in names}
    # Include every observed reference with navigation, even if below the mask:
    # perturbations can change selection near a boundary.
    references = sorted({sv for name in names
                         for obs in admitted['stations'][name]['reference_observations']
                         for sv in obs['if_code_m'] if sv in navigation})
    configurations = [('baseline', [], 0.)]
    for label, refs in [(sv, [sv]) for sv in references] + [('all_references', references)]:
        configurations.extend((label, refs, step) for step in (-1., 1.))
    cases = []
    for label, refs, step in configurations:
        row = {'mode': label, 'perturbed_references': refs, 'clock_step_m': step}
        try:
            nav = shifted_navigation(navigation, refs, step, context.target)
            calibration = dict(baseline_cal)
            for name in names:
                if step and any(set(refs) & obs['if_code_m'].keys()
                                for obs in admitted['stations'][name]['reference_observations']):
                    calibration[name] = calibrate(name, nav)
            row['calibration'] = {}
            for name, cal in calibration.items():
                old = {epoch['time_s']: epoch for epoch in baseline_cal[name]['epochs']}
                row['calibration'][name] = {
                    'status': cal['status'], 'failures': cal['failures'],
                    'epochs': [{'time_s': epoch['time_s'], 'references': epoch['references'],
                                'clock_change_m': epoch['clock_m'] - old[epoch['time_s']]['clock_m'],
                                'selection_changed': epoch['references'] != old[epoch['time_s']]['references']}
                               for epoch in cal['epochs'] if epoch['time_s'] in old]}
            row.update(fit_variant(admitted, context, calibration))
        except ScientificRejection as error:
            row.update(status='FIT_REJECTED', reason=str(error))
        except Exception as error:
            row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__ + ': ' + str(error))
        cases.append(row)
        if progress:
            progress({key: row[key] for key in ('mode', 'clock_step_m', 'status')})
    pairs = []
    for index in range(1, len(cases), 2):
        minus, plus = cases[index:index + 2]
        pairs.append({'mode': minus['mode'], **paired_response(cases[0], minus, plus, 1.)})
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(__file__).with_name('reference_sensitivity.py')]
    sources += [root / 'positioning' / name for name in
                ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'exploratory-reference-clock-response-v1',
            'scope': 'Real archived observations with invented +/-1 m clock-product perturbations; development only.',
            'target': context.target, 'date_gpst': context.date_gpst,
            'fit_stations': names, 'references': references, 'input_sha256': hashes,
            'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sources},
            'method': 'af0 += step/c for all records of selected non-target references; full recalibration and inverse fit, fixed target codes and 20 m equal weights. Original gates retained.',
            'frame': 'Shared terrestrial axes at u0; fitted emission time can change with B.',
            'measured_product_error': False, 'is_accuracy_bound': False,
            'target_orbit_accessed': False, 'new_confirmation': False,
            'case_count': len(cases), 'status_counts': dict(Counter(row['status'] for row in cases)),
            'cases': cases, 'paired_responses': pairs,
            'runtime_seconds': time.perf_counter() - started}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved input archive')
    report = run(args.archive, progress=lambda row: print(json.dumps(row), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
