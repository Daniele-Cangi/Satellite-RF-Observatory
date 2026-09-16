"""Conditional observation-time precise-reference recalibration on exposed data."""
import argparse
from collections import Counter
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from positioning.calibration import C, calibrate_station
from positioning.errors import ScientificRejection
from .precise_reference_model import PreciseReference, parse_clock, parse_orbit
from .reference_code_bias import parse_bias, code_translation, translate_observations
from .reference_conventions import antenna_offsets, radial_yaw_geometry
from .reference_sensitivity import load_inputs, fit_variant


def calibrate_fixed(observations, station, context, reference_sets, model):
    """Historical numerical checks with an explicit model and frozen reference sets.

    A precise elevation below the mask is a recorded failure, never a silent
    replacement/removal. This is an exploratory adapter, not a core-code edit.
    """
    epochs, failures = [], []
    for obs in observations:
        t, codes = obs['time_s'], obs['if_code_m']
        if context.target in codes:
            raise ValueError('target passed to reference calibration')
        refs = reference_sets.get(t, [])
        if len(refs) < 4 or not set(refs) <= codes.keys():
            failures.append(f'epoch {t}: missing fixed references')
            continue
        if any(model(sv, codes[sv], t, station, 0.)[1] < 10. for sv in refs):
            failures.append(f'epoch {t}: fixed reference below precise mask')
        clock = 0.
        for _ in range(4):
            estimates = np.array([codes[sv]-model(sv, codes[sv], t, station, clock)[0] for sv in refs])
            clock = float(estimates.mean())
        residuals = estimates-clock
        rms = float(np.sqrt(np.mean(residuals**2)))
        split = float(abs(estimates[::2].mean()-estimates[1::2].mean()))
        if np.max(np.abs(residuals)) > 50 or rms > 20 or split > 30:
            failures.append(f'epoch {t}: reference residual or subset clock threshold')
        def residual(v):
            return np.array([model(sv, codes[sv], t, station+v[:3], v[3])[0]+v[3]-codes[sv] for sv in refs])
        def jac(v):
            return np.column_stack([(residual(v+np.eye(4)[j])-residual(v-np.eye(4)[j]))/2 for j in range(4)])
        spp = least_squares(residual, np.array([0., 0., 0., clock]), jac=jac,
                            xtol=1e-11, ftol=1e-11, gtol=1e-8)
        rank, offset = np.linalg.matrix_rank(spp.jac), float(np.linalg.norm(spp.x[:3]))
        if not spp.success or rank != 4 or offset > 30:
            failures.append(f'epoch {t}: non-target ground-coordinate check')
        epochs.append({'time_s': t, 'clock_m': clock, 'references': refs,
                       'residuals_m': residuals.tolist(), 'rms_m': rms, 'split_clock_m': split,
                       'ground_offset_m': offset, 'ground_offset_xyz_m': spp.x[:3].tolist(),
                       'ground_fit_rank': int(rank)})
    return {'epochs': epochs, 'failures': failures,
            'status': 'CALIBRATION_QUALIFIED' if not failures and len(epochs) == context.samples else 'CALIBRATION_NOT_QUALIFIED'}


def load_products(context, refs, timed, biases, antennas):
    timed, biases, antennas = map(Path, (timed, biases, antennas))
    buffers = {'timed_receipt': (timed/'receipt.json').read_bytes(),
               'orbit_extract': (timed/'reference_orbit.txt').read_bytes(),
               'clock_extract': (timed/'reference_clock.txt').read_bytes(),
               'bias_receipt': (biases/'receipt.json').read_bytes(),
               'bias_extract': (biases/'reference_bias.bia').read_bytes(),
               'antenna_receipt': (antennas/'receipt.json').read_bytes(),
               'antenna_extract': (antennas/'reference_antenna.atx').read_bytes()}
    receipt = json.loads(buffers['timed_receipt'])
    for name in ('timed', 'bias', 'antenna'):
        meta = json.loads(buffers[name+'_receipt'])
        if meta['target_excluded'] != context.target or meta['references'] != refs:
            raise ValueError('product target or reference set differs')
        if name != 'timed' and (meta['model'] != 'IGS20_2425' or
                meta['extract_sha256'] != hashlib.sha256(buffers[name+'_extract']).hexdigest()):
            raise ValueError('bias/antenna input differs from receipt')
    date_tag = context.day.strftime('%Y%j')
    expected = {'orbit': f'COD0OPSRAP_{date_tag}0000_01D_05M_ORB.SP3.gz',
                'clock': f'COD0OPSRAP_{date_tag}0000_01D_30S_CLK.CLK.gz'}
    if receipt['date_gpst'] != context.date_gpst or receipt['product_family'] != 'COD0OPSRAP':
        raise ValueError('incompatible product date/family')
    for name in ('orbit', 'clock'):
        if (receipt[name]['extract_sha256'] != hashlib.sha256(buffers[name+'_extract']).hexdigest()
                or not receipt[name]['source_url'].endswith('/'+expected[name])):
            raise ValueError('timed input differs from receipt/paired series')
    bias_meta = json.loads(buffers['bias_receipt'])
    if not bias_meta['source_url'].endswith(f'/COD0OPSRAP_{date_tag}0000_01D_01D_OSB.BIA.gz'):
        raise ValueError('bias not from the paired CODE rapid series')
    start, end = receipt['clock_window_gpst_s']
    if not 0 <= start < context.times[0]-1 < context.times[-1]+1 < end < 86400:
        raise ValueError('clock window does not contain the observation window')
    offsets = antenna_offsets(buffers['antenna_extract'].decode('ascii'), refs, context.target,
                              context.date_gpst, start, 'IGS20_2425')
    at_end = antenna_offsets(buffers['antenna_extract'].decode('ascii'), refs, context.target,
                             context.date_gpst, end, 'IGS20_2425')
    if offsets != at_end:
        raise ValueError('antenna assignment changes within the evaluation window')
    records = parse_bias(buffers['bias_extract'].decode('ascii'), refs, context.target, 'IGS20_2425')
    corrections = {(t, sv): code_translation(records, sv, context.day+timedelta(seconds=t), offsets[sv]['svn'])
                   for t in context.times for sv in refs}
    orbits = parse_orbit(buffers['orbit_extract'].decode('ascii'), refs, context.target, context.date_gpst)
    clocks = parse_clock(buffers['clock_extract'].decode('ascii'), refs, context.target,
                         context.date_gpst, start, end)
    return PreciseReference(orbits, clocks, offsets, context.target), corrections, {
        key: hashlib.sha256(value).hexdigest() for key, value in buffers.items()}


def compare_fit(row, baseline):
    if row['status'] != 'ESTIMATED' or baseline['status'] != 'ESTIMATED':
        return {'comparison_status': 'NOT_COMPARABLE'}
    if row['u0_relative_s'] != baseline['u0_relative_s']:
        return {'comparison_status': 'FRAME_TAG_CHANGED'}
    delta = np.array(row['xyz_m'])-baseline['xyz_m']
    return {'comparison_status': 'COMPARABLE', 'delta_xyz_m': delta.tolist(),
            'displacement_m': float(np.linalg.norm(delta)), 'delta_B_m': row['B_m']-baseline['B_m']}


def run(archive, timed, biases, antennas, progress=None):
    admitted, context, navigation, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    refs = sorted({sv for name in names for obs in admitted['stations'][name]['reference_observations'] for sv in obs['if_code_m']})
    provider, corrections, product_hashes = load_products(context, refs, timed, biases, antennas)
    translated = {name: translate_observations(admitted['stations'][name]['reference_observations'], corrections, context.target) for name in names}
    cases = []
    configurations = [('bias_corrected_broadcast', None, None), ('precise_9_nodes_30s_clock', 9, 30),
                      ('control_7_nodes_30s_clock', 7, 30), ('control_9_nodes_60s_clock', 9, 60)]
    reference_sets = {}
    for mode, count, step in configurations:
        row, calibration = {'mode': mode}, {}
        try:
            for name in names:
                station = np.array(admitted['stations'][name]['antenna_ecef_m'])
                if count is None:
                    calibration[name] = calibrate_station(translated[name], station, navigation, context)
                    reference_sets[name] = {e['time_s']: e['references'] for e in calibration[name]['epochs']}
                else:
                    def model(sv, code, t, xyz, clock):
                        return provider.model(sv, code, t, xyz, clock, count, step)
                    calibration[name] = calibrate_fixed(translated[name], station, context, reference_sets[name], model)
            row.update(calibration=calibration, **fit_variant(admitted, context, calibration))
        except ScientificRejection as error:
            row.update(status='FIT_REJECTED', reason=str(error), calibration=calibration)
        except Exception as error:
            row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__+': '+str(error), calibration=calibration)
        if cases:
            row['versus_broadcast'] = compare_fit(row, cases[0])
        if len(cases) >= 2:
            row['versus_primary'] = compare_fit(row, cases[1])
        cases.append(row)
        if progress:
            progress({'mode': mode, 'status': row['status']})
    paths = []
    primary = cases[1]
    for name in names:
        station = np.array(admitted['stations'][name]['antenna_ecef_m'])
        fitted = {e['time_s']: e for e in primary['calibration'].get(name, {}).get('epochs', [])}
        for obs in translated[name]:
            t = obs['time_s']
            for sv, code in sorted(obs['if_code_m'].items()):
                row = {'station': name, 'time_s': t, 'reference': sv, 'status': 'NOT_IN_BROADCAST_REFERENCE_SET'}
                if sv in reference_sets.get(name, {}).get(t, []):
                    row['status'] = 'MISSING_PRECISE_CALIBRATION'
                    if t in fitted:
                        clock = fitted[t]['clock_m']
                        tx, sat_clock, com, _, closure, offset = provider.emitted_state(sv, code, t)
                        p9, _ = provider.orbit(sv, tx, 9)
                        p7, _ = provider.orbit(sv, tx, 7)
                        tau = -clock/C-offset
                        row.update(status='EVALUATED', emission_gpst_s=tx, reception_gpst_s=t-clock/C,
                                   emission_offset_from_tag_s=offset, corrected_if_code_m=code,
                                   emission_closure_m=closure, satellite_clock_with_relativity_s=sat_clock,
                                   orbit_9_minus_7_norm_m=float(np.linalg.norm(p9-p7)),
                                   **radial_yaw_geometry(station, com, provider.offsets[sv]['if_pco_body_m'], tau))
                        try:
                            row.update(clock_thinning_control_status='COMPARED',
                                       clock_30_minus_60_m=C*(provider.clock(sv, tx, 30)-provider.clock(sv, tx, 60)))
                        except ValueError:
                            row['clock_thinning_control_status'] = 'UNAVAILABLE'
                paths.append(row)
    controls = provider.withheld_node_controls(refs, context.times[0], context.times[-1])
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(__file__).with_name('precise_reference_model.py')]
    sources += [Path(__file__).with_name(name+'.py') for name in
                ('reference_code_bias', 'reference_conventions', 'reference_product_discrepancy',
                 'reference_ray_projection', 'reference_sensitivity')]
    sources += [root/'positioning'/name for name in ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'reference-time-alignment-v1', 'target': context.target, 'date_gpst': context.date_gpst,
            'references': refs, 'fit_stations': names, 'input_sha256': hashes | product_hashes,
            'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'scope': 'Conditional CODE rapid observation-time recalibration: satellite code bias, radial PCO, periodic relativity; incomplete physical uncertainty.',
            'conventions': {'time': 'GPST; solve t_tx + clock(t_tx) = t_tag - corrected_IF_code/c',
                'orbit': 'CODE rapid IGc20; 9-node degree-8 interpolation at 300 s spacing; no extrapolation',
                'clock': 'paired CODE rapid 30 s linear interpolation plus -2*r.v/c^2; missing sigma is unknown, not zero',
                'antenna': 'IGS20_2425 IF radial PCO; nadir body Z assumed, transverse yaw only bounded',
                'bias': 'paired CODE rapid satellite C1C-to-C1W difference; target codes fixed',
                'calibration': 'reference sets frozen from bias-corrected broadcast; historical residual/rank/ground thresholds',
                'controls': '7 orbit nodes and 60 s thinned clocks each recalibrated/refitted; withheld native-node prediction',
                'unresolved': ['actual attitude and code antenna response', 'station frame and media consistency',
                    'receiver-dependent biases and physical error covariance', 'absolute clock datum implications for emission time']},
            'target_orbit_accessed': False, 'target_clock_parsed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False,
            'case_count': len(cases), 'status_counts': dict(Counter(r['status'] for r in cases)), 'cases': cases,
            'path_count': len(paths), 'path_status_counts': dict(Counter(r['status'] for r in paths)), 'paths': paths,
            'withheld_node_controls': controls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'timed', 'biases', 'antennas', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved archive')
    result = run(args.archive, args.timed, args.biases, args.antennas,
                 progress=lambda value: print(json.dumps(value), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
