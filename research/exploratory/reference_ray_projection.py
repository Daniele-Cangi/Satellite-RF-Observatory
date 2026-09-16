"""Conditional raw-product range projections, not aligned measurement corrections."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from positioning.calibration import C, OMEGA, rotate_z, state_and_clock, troposphere
from .reference_product_discrepancy import parse_extract
from .reference_sensitivity import load_inputs


def project(station, broadcast, precise, clock_difference_m):
    """Both states at one emission epoch, rotated to ONE fixed reception frame.

    Baseline vacuum flight time is solved from broadcast geometry, then frozen
    for both products. No orbit interpolation or shifted-emission solution.
    """
    station, broadcast, precise = map(lambda x: np.asarray(x, dtype=float),
                                      (station, broadcast, precise))
    if any(x.shape != (3,) or not np.isfinite(x).all() for x in (station, broadcast, precise)):
        raise ValueError('finite xyz vectors required')
    if not np.isfinite(clock_difference_m):
        raise ValueError('finite clock difference required')
    tau = float(np.linalg.norm(broadcast-station)/C)
    for _ in range(10):
        distance = float(np.linalg.norm(rotate_z(broadcast, -OMEGA*tau)-station))
        next_tau = distance/C
        if abs(next_tau-tau) < 1e-14:
            tau = next_tau
            break
        tau = next_tau
    else:
        raise ValueError('baseline light time did not converge')
    b, p = [rotate_z(x, -OMEGA*tau) for x in (broadcast, precise)]
    br, pr = np.linalg.norm(b-station), np.linalg.norm(p-station)
    if br == 0 or pr == 0:
        raise ValueError('degenerate receiver path')
    orbital = float(br-pr)
    linear = float(np.dot((p-station)/pr, b-p))
    _, elevation = troposphere(station, b)
    return {'baseline_vacuum_flight_time_s': tau, 'broadcast_elevation_deg': float(elevation),
            'orbital_range_difference_m': orbital,
            'clock_range_difference_m': -float(clock_difference_m),
            'joint_range_difference_m': orbital-float(clock_difference_m),
            'linear_projection_residual_m': orbital-linear}


def bracket(times, start, end):
    times = sorted(times)
    if not times or not times[0] <= start <= end <= times[-1]:
        raise ValueError('SP3 epochs do not bracket archived window')
    return sorted({max(t for t in times if t <= start), min(t for t in times if t >= end)})


def run(archive, extract_path, receipt_path):
    admitted, context, nav, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    refs = sorted({sv for name in names for obs in admitted['stations'][name]['reference_observations']
                   for sv in obs['if_code_m'] if sv in nav})
    content, receipt_bytes = Path(extract_path).read_bytes(), Path(receipt_path).read_bytes()
    receipt = json.loads(receipt_bytes)
    if (receipt['extract_sha256'] != hashlib.sha256(content).hexdigest()
            or receipt['target_excluded'] != context.target or receipt['references'] != refs):
        raise ValueError('reference input differs from receipt')
    epochs = parse_extract(content.decode('ascii'), refs, context.target, context.date_gpst)
    times = bracket(epochs, context.times[0], context.times[-1])
    rows, groups = [], []
    for t in times:
        for name in names:
            station = admitted['stations'][name]
            observed = {sv for obs in station['reference_observations'] for sv in obs['if_code_m']}
            block = []
            for sv in refs:
                row = {'time_gpst_s': t, 'station': name, 'reference': sv}
                sample = epochs[t].get(sv, {'status': 'MISSING_SP3_RECORD'})
                row['status'] = 'NOT_OBSERVED_IN_ARCHIVED_WINDOW' if sv not in observed else sample['status']
                if row['status'] == 'AVAILABLE':
                    record = min(nav[sv], key=lambda r: abs(t-(r.toc_gps-context.day).total_seconds()))
                    age = t-(record.toc_gps-context.day).total_seconds()
                    if abs(age) > 7200:
                        row['status'] = 'BROADCAST_TOO_OLD'
                    else:
                        b, _ = state_and_clock(record, t, context)
                        polynomial = record.af0_s + record.af1_s_s*age + record.af2_s_s2*age**2
                        row.update(project(station['antenna_ecef_m'], b, sample['xyz_m'],
                                           C*(polynomial-sample['clock_s'])))
                        row['status'] = 'PROJECTED' if row['broadcast_elevation_deg'] >= 10. else 'BELOW_MASK'
                block.append(row)
            valid = [r for r in block if r['status'] == 'PROJECTED']
            group = {'time_gpst_s': t, 'station': name, 'references': [r['reference'] for r in valid],
                     'status': 'PROJECTED' if len(valid) >= 4 else 'INSUFFICIENT_REFERENCES'}
            if len(valid) >= 4:
                # Under fixed equal weights and unchanged code observations,
                # swapping broadcast -> precise changes fitted receiver clock
                # by mean(M_broadcast - M_precise). It is not recalibration.
                for key in ('orbital_range_difference_m', 'clock_range_difference_m', 'joint_range_difference_m'):
                    group['mean_'+key] = float(np.mean([r[key] for r in valid]))
            groups.append(group)
            rows.extend(block)
    valid = [r for r in rows if r['status'] == 'PROJECTED']
    def rms(key):
        return float(np.sqrt(np.mean([r[key]**2 for r in valid]))) if valid else None
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(__file__).with_name('reference_product_discrepancy.py'),
               Path(__file__).with_name('reference_sensitivity.py')]
    sources += [root/'positioning'/p for p in ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'reference-ray-projection-v1', 'target': context.target, 'date_gpst': context.date_gpst,
            'fit_stations': names, 'references': refs, 'emission_nodes_gpst_s': times,
            'input_sha256': hashes | {'reference_extract': hashlib.sha256(content).hexdigest(),
                                      'product_receipt': hashlib.sha256(receipt_bytes).hexdigest()},
            'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'scope': 'Raw-product geometric ray diagnostic at bracketing SP3 emission nodes, not RF measurements or estimator corrections.',
            'conventions': {'time': 'GPST; same emission node and frozen baseline reception axes',
                            'rotation': 'Rz(-OMEGA*tau), broadcast vacuum tau solved then shared',
                            'clock': 'Broadcast polynomial minus SP3 field; periodic relativity NOT included on either side',
                            'sign': 'model_broadcast - model_precise = range_b - range_p - c*(clock_b-clock_p)',
                            'unresolved': ['orbital reference points/antenna attitude', 'frame alignment',
                                           'signal biases and clock datum', 'differential periodic relativity',
                                           'media, observation-time interpolation and nonlinear recalibration']},
            'target_state_parsed': False, 'new_confirmation': False, 'qualified_error_budget': False,
            'applied_to_estimator': False, 'case_count': len(rows),
            'status_counts': dict(Counter(r['status'] for r in rows)),
            'rms_m': {key: rms(key) for key in ('orbital_range_difference_m', 'clock_range_difference_m',
                                               'joint_range_difference_m', 'linear_projection_residual_m')},
            'station_epoch_projections': groups, 'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'extract', 'receipt', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved archive')
    result = run(args.archive, args.extract, args.receipt)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
