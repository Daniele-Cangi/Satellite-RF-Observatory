"""Paired CODE attitude sensitivity on exposed reference-only observations."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from positioning.calibration import C, OMEGA, rotate_z, calibrate_station
from positioning.errors import ScientificRejection
from .reference_attitude_model import Attitude, AttitudeReference, guarded_products, parse_attitude, strict_json
from .reference_code_bias import translate_observations
from .reference_time_alignment import calibrate_fixed, compare_fit
from .reference_sensitivity import load_inputs, fit_variant


def load_attitude(directory, context, refs):
    directory = Path(directory)
    raw, receipt_raw = (directory/'reference_attitude.obx').read_bytes(), (directory/'receipt.json').read_bytes()
    meta = strict_json(receipt_raw)
    filename = f'COD0OPSRAP_{context.day.strftime("%Y%j")}0000_01D_30S_ATT.OBX.gz'
    if (meta['target_excluded'] != context.target or meta['references'] != refs or
            meta['date_gpst'] != context.date_gpst or meta['product_family'] != 'COD0OPSRAP' or
            meta['frame'] != 'IGC20' or meta['mapping'] != 'ECEF_TO_BODY' or
            not meta['source_url'].endswith('/'+filename) or
            meta['extract_sha256'] != hashlib.sha256(raw).hexdigest()):
        raise ValueError('attitude receipt/paired product differs')
    start, end = meta['window_gpst_s']
    if not start < context.times[0]-1 < context.times[-1]+1 < end:
        raise ValueError('attitude window does not contain observations')
    samples = parse_attitude(raw.decode('ascii'), refs, context.target, context.date_gpst, start, end)
    return Attitude(samples, context.target), {'attitude_extract': hashlib.sha256(raw).hexdigest(),
                                             'attitude_receipt': hashlib.sha256(receipt_raw).hexdigest()}


def attitude_controls(attitude, precise, refs, start, end):
    rows = []
    for sv in refs:
        for t in range(int(start)-30, int(end)+31, 30):
            if t % 60 != 30:
                continue
            row = {'reference': sv, 'time_s': t, 'status': 'UNAVAILABLE'}
            try:
                native = attitude.body_to_ecef(sv, float(t))
                thinned = attitude.body_to_ecef(sv, float(t), 60)
                pco = np.array(precise.offsets[sv]['if_pco_body_m'])
                row.update(status='COMPARED', rotation_difference_rad=float(Rotation.from_matrix(native.T@thinned).magnitude()),
                           pco_difference_m=float(np.linalg.norm((native-thinned)@pco)))
            except ValueError as error:
                row['reason'] = str(error)
            rows.append(row)
    return rows


def run(archive, timed, biases, antennas, attitudes, progress=None):
    admitted, context, navigation, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    refs = sorted({sv for name in names for obs in admitted['stations'][name]['reference_observations'] for sv in obs['if_code_m']})
    precise, corrections, product_hashes = guarded_products(context, refs, timed, biases, antennas)
    attitude, attitude_hashes = load_attitude(attitudes, context, refs)
    translated = {name: translate_observations(admitted['stations'][name]['reference_observations'], corrections, context.target) for name in names}
    broadcast = {name: calibrate_station(translated[name], np.array(admitted['stations'][name]['antenna_ecef_m']), navigation, context) for name in names}
    sets = {name: {e['time_s']: e['references'] for e in cal['epochs']} for name, cal in broadcast.items()}
    full, thinned, z_only = (AttitudeReference(precise, attitude), AttitudeReference(precise, attitude, 60),
                            AttitudeReference(precise, attitude, z_only=True))
    variants = [('radial_30s_clock', precise.model), ('full_pco_30s_attitude', full.model),
                ('control_full_pco_60s_attitude', thinned.model), ('control_body_z_only', z_only.model)]
    cases = []
    for mode, model in variants:
        row, calibration = {'mode': mode}, {}
        try:
            for name in names:
                station = np.array(admitted['stations'][name]['antenna_ecef_m'])
                calibration[name] = calibrate_fixed(translated[name], station, context, sets[name], model)
            row.update(calibration=calibration, **fit_variant(admitted, context, calibration))
        except ScientificRejection as error:
            row.update(status='FIT_REJECTED', reason=str(error), calibration=calibration)
        except Exception as error:
            row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__+': '+str(error), calibration=calibration)
        if cases:
            row['versus_radial'] = compare_fit(row, cases[0])
        if len(cases) >= 2:
            row['versus_full'] = compare_fit(row, cases[1])
        cases.append(row)
        if progress:
            progress({'mode': mode, 'status': row['status']})
    paths = []
    for name in names:
        station = np.array(admitted['stations'][name]['antenna_ecef_m'])
        baseline = {e['time_s']: e for e in cases[0]['calibration'].get(name, {}).get('epochs', [])}
        for obs in translated[name]:
            t = obs['time_s']
            for sv, code in sorted(obs['if_code_m'].items()):
                row = {'station': name, 'time_s': t, 'reference': sv, 'status': 'NOT_IN_BROADCAST_REFERENCE_SET'}
                if sv in sets[name].get(t, []):
                    row['status'] = 'UNAVAILABLE'
                    try:
                        tx, _, com, radial, _, offset = precise.emitted_state(sv, code, t)
                        rotation = attitude.body_to_ecef(sv, tx)
                        pco = np.array(precise.offsets[sv]['if_pco_body_m'])
                        complete = com+rotation@pco
                        body_z = com+rotation[:, 2]*pco[2]
                        tau = -baseline[t]['clock_m']/C-offset
                        def distance(point):
                            return np.linalg.norm(rotate_z(point, -OMEGA*tau)-station)
                        nadir = -com/np.linalg.norm(com)
                        row.update(status='EVALUATED', emission_gpst_s=tx,
                                   full_minus_radial_range_m=float(distance(complete)-distance(radial)),
                                   body_z_minus_radial_range_m=float(distance(body_z)-distance(radial)),
                                   transverse_range_m=float(distance(complete)-distance(body_z)),
                                   pco_ecef_m=(rotation@pco).tolist(),
                                   body_z_nadir_angle_rad=float(np.arctan2(np.linalg.norm(np.cross(rotation[:, 2], nadir)), rotation[:, 2]@nadir)))
                        try:
                            coarse = attitude.body_to_ecef(sv, tx, 60)
                            row.update(thinning_status='COMPARED',
                                       pco_30_minus_60_norm_m=float(np.linalg.norm((rotation-coarse)@pco)))
                        except ValueError as error:
                            row.update(thinning_status='UNAVAILABLE', thinning_reason=str(error))
                    except (ValueError, KeyError) as error:
                        row['reason'] = str(error)
                paths.append(row)
    controls = attitude_controls(attitude, precise, refs, context.times[0], context.times[-1])
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(__file__).with_name('reference_attitude_model.py')]
    sources += [Path(__file__).with_name(name+'.py') for name in
                ('reference_time_alignment', 'precise_reference_model', 'reference_code_bias', 'reference_conventions',
                 'reference_product_discrepancy', 'reference_ray_projection', 'reference_sensitivity')]
    sources += [root/'positioning'/name for name in ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'reference-attitude-v1', 'target': context.target, 'date_gpst': context.date_gpst,
            'references': refs, 'fit_stations': names, 'input_sha256': hashes | product_hashes | attitude_hashes,
            'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'scope': 'Exploratory paired CODE processing attitude, not independent physical attitude or code-response calibration.',
            'conventions': {'attitude': 'CODE ORBEX scalar-first ECEF-to-body; inverse maps ANTEX body PCO to ECEF; shortest-arc SLERP',
                'orbit_clock_bias': 'Unchanged paired precise 9-node orbit, 30 s clock, relativity and C1C-to-C1W bias model',
                'ray_comparison': 'Fixed radial-calibration receiver clock; geometric differences separate from full recalibration',
                'controls': '60 s attitude thinning and body-Z-only offset, each recalibrated/refitted; omitted native nodes',
                'unresolved': ['physical attitude errors', 'directional code antenna response and receiver biases',
                               'station frame and propagation', 'joint physical covariance and total uncertainty']},
            'target_orbit_accessed': False, 'target_attitude_parsed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False,
            'broadcast_selection_calibration': broadcast,
            'case_count': len(cases), 'status_counts': dict(Counter(r['status'] for r in cases)), 'cases': cases,
            'path_count': len(paths), 'path_status_counts': dict(Counter(r['status'] for r in paths)), 'paths': paths,
            'withheld_attitude_nodes': controls}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'timed', 'biases', 'antennas', 'attitudes', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved archive')
    result = run(args.archive, args.timed, args.biases, args.antennas, args.attitudes,
                 progress=lambda value: print(json.dumps(value), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
