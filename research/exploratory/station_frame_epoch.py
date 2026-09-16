"""Regularized IGc20 coordinate/velocity/PSD sensitivity on exposed references."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path

import numpy as np

from . import verified_station_replay as verified
from .reference_attitude import load_attitude
from .reference_attitude_model import AttitudeReference, guarded_products, strict_json
from .reference_code_bias import translate_observations
from .reference_time_alignment import calibrate_fixed
from .station_coordinates import basis, epoch, numbers, one

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT/'research/exploratory/inputs/station_frame'
RECEIPT_SHA256 = '816ed06832a3974e131c859229e154afac0909b99304e35281d3b8fd71d90ffb'
YEAR_SECONDS = 365.25*86400
MODES = ('header', 'catalog_linear_control', 'catalog_psd', 'final_static', 'final_transport')


def read_frame():
    raw = verified.pinned_bytes(FRAME/'receipt.json', RECEIPT_SHA256)
    receipt = strict_json(raw)
    names = {'IGC20.CRD', 'IGC20.VEL', 'IGC20.PSD', 'g14_apriori.txt', 'g12_apriori.txt'}
    if receipt['schema'] != 'station-frame-inputs-v1' or set(receipt['files']) != names or receipt.get('satellite_parameters_parsed') is not False:
        raise ValueError('unexpected terrestrial manifest')
    buffers = {name: verified.pinned_bytes(FRAME/name, receipt['files'][name]['extract_sha256']) for name in names}
    return {k: v.decode('ascii') for k, v in buffers.items()}, {'frame_receipt': hashlib.sha256(raw).hexdigest()} | {
        k: hashlib.sha256(v).hexdigest() for k, v in buffers.items()}


def catalog(text, name, domes, velocity=False):
    lines = text.splitlines()
    if 'LOCAL GEODETIC DATUM: IGc20_0' not in lines[2]:
        raise ValueError('catalog frame differs')
    if not velocity and 'EPOCH: 2020-01-01 00:00:00' not in lines[2]:
        raise ValueError('catalog epoch differs')
    rows = [s.split() for s in lines[6:] if len(s.split()) >= 7 and s.split()[1:3] == [name[:4], domes]]
    row = one(rows, 'catalog station/DOMES')
    if row[6] not in (('IC20', 'IT20') if velocity else ('IGC20', 'ITR20')):
        raise ValueError('unsupported catalogue coordinate provenance')
    return numbers(' '.join(row[3:6]), 3), row[6]


def psd_terms(text, name, domes):
    """Pair SINEX amplitude/time rows by station, point, quake, model and axis."""
    block, ids, params = None, [], {}
    for line in text.splitlines():
        if line.startswith('+'):
            block = line[1:]
        elif line.startswith('-'):
            block = None
        elif line.startswith(' '):
            if block == 'SITE/ID' and line[1:5] == name[:4]:
                ids.append(line)
            elif block == 'SOLUTION/ESTIMATE' and line[14:18] == name[:4]:
                row = line.split()
                parameter, point, when = row[1], row[3], row[5]
                if parameter[:4] not in ('ALOG', 'TLOG', 'AEXP', 'TEXP') or parameter[4:] not in ('_E', '_N', '_U'):
                    raise ValueError('unsupported PSD term')
                key = (point, when, parameter[1:])
                kind = parameter[0]
                if kind in params.setdefault(key, {}):
                    raise ValueError('duplicate PSD parameter')
                if row[6] != ('m' if kind == 'A' else 'y'):
                    raise ValueError('PSD unit differs')
                params[key][kind] = float(numbers(' '.join(row[8:10]), 2)[0])
    if not ids:
        if params:
            raise ValueError('PSD parameters without monument')
        return []
    site = one([s for s in ids if s[9:18] == domes], 'PSD monument')
    terms = []
    for (point, when, model_axis), pair in sorted(params.items()):
        if point != site[6:8].strip() or set(pair) != {'A', 'T'} or pair['T'] <= 0:
            raise ValueError('incomplete PSD pair or invalid relaxation time')
        terms.append({'epoch': when, 'model': model_axis[:3], 'axis': model_axis[-1],
                      'amplitude_m': pair['A'], 'tau_years': pair['T']})
    return terms


def psd_enu(terms, when):
    result = np.zeros(3)
    for term in terms:
        elapsed = (when-epoch(term['epoch'])).total_seconds()/YEAR_SECONDS
        if elapsed <= 0:
            continue
        ratio = elapsed/term['tau_years']
        if term['model'] == 'LOG':
            value = np.log1p(ratio)
        elif term['model'] == 'EXP':
            value = -np.expm1(-ratio)
        else:
            raise ValueError('unknown PSD model')
        result['ENU'.index(term['axis'])] += term['amplitude_m']*value
    return result


def marker_at(xyz, velocity, terms, when, include_psd=True):
    regular = xyz+velocity*((when-datetime(2020, 1, 1)).total_seconds()/YEAR_SECONDS)
    return regular+basis(regular).T@psd_enu(terms, when) if include_psd else regular


def arp(marker, eccentricity_enu):
    return marker+basis(marker).T@eccentricity_enu


def apriori(text, station):
    coordinates = []
    for axis in ('STAX', 'STAY', 'STAZ'):
        row = one([s.split() for s in text.splitlines() if s[14:18] == station['station'][:4] and
                   s[19:21].strip() == station['point'] and s[22:26].strip() == station['solution_id'] and
                   s[7:13].strip() == axis], 'daily a priori '+axis)
        if row[5] != station['coordinate_epoch'] or row[6] != 'm':
            raise ValueError('daily a priori epoch/unit differs')
        coordinates.append(float(numbers(' '.join(row[8:10]), 2)[0]))
    return np.array(coordinates)


def station_model(station, frame, day, times):
    name, domes = station['station'], station['domes']
    xyz, crd_flag = catalog(frame['IGC20.CRD'], name, domes)
    vel, vel_flag = catalog(frame['IGC20.VEL'], name, domes, velocity=True)
    terms = psd_terms(frame['IGC20.PSD'], name, domes)
    t0 = epoch(station['coordinate_epoch'])
    final = np.array(station['sinex_marker_ecef_m'])
    eccentricity = np.array(station['sinex_eccentricity_enu_m'])
    at0 = marker_at(xyz, vel, terms, t0)
    def position(mode, seconds):
        when = datetime.fromisoformat(day)+timedelta(seconds=seconds)
        if mode == 'header':
            return np.array(station['header_arp_ecef_m'])
        if mode == 'final_static':
            return np.array(station['sinex_arp_ecef_m'])
        if mode == 'final_transport':
            return arp(final+marker_at(xyz, vel, terms, when)-at0, eccentricity)
        if mode not in ('catalog_linear_control', 'catalog_psd'):
            raise ValueError('unknown station mode')
        return arp(marker_at(xyz, vel, terms, when, mode == 'catalog_psd'), eccentricity)
    midpoint = datetime.fromisoformat(day)+timedelta(seconds=float(np.mean(times)))
    detail = {'station': name, 'domes': domes, 'catalog_crd_flag': crd_flag, 'catalog_velocity_flag': vel_flag,
              'catalog_xyz_epoch2020_m': xyz.tolist(), 'velocity_m_per_julian_year': vel.tolist(), 'psd_terms': terms,
              'psd_at_event_enu_m': psd_enu(terms, midpoint).tolist(),
              'psd_at_event_norm_m': float(np.linalg.norm(psd_enu(terms, midpoint))),
              'catalog_at_daily_epoch_m': at0.tolist(),
              'daily_epoch_transport_m': (marker_at(xyz, vel, terms, midpoint)-at0).tolist(),
              'tag_18s_sensitivity_m': float(np.linalg.norm(marker_at(xyz, vel, terms, midpoint+timedelta(seconds=18))-
                                                            marker_at(xyz, vel, terms, midpoint))),
              'positions': {mode: [position(mode, t).tolist() for t in times] for mode in MODES}}
    return position, detail


def run(tag, progress=None):
    verification = verified.verify(tag)
    paths = verified.paths(tag)
    admitted, context, _, archive_hashes = verified.load_inputs(paths['admission_receipt'].parent)
    saved = {key: strict_json(verified.pinned_bytes(paths[key], verified.PINS[tag][key]))
             for key in ('station_report', 'attitude_report', 'reference_report')}
    frame, frame_hashes = read_frame()
    names = admitted['fit_stations']
    refs = saved['reference_report']['references']
    precise, corrections, product_hashes = guarded_products(context, refs,
        verified.INPUTS/f'timed_reference_products/{tag}', verified.INPUTS/f'reference_biases/{tag}',
        verified.INPUTS/f'reference_antennas/{tag}')
    attitude, attitude_hashes = load_attitude(verified.INPUTS/f'reference_attitudes/{tag}', context, refs)
    provider = AttitudeReference(precise, attitude)
    if saved['attitude_report']['input_sha256'] != archive_hashes | product_hashes | attitude_hashes:
        raise ValueError('paired reference products differ from pinned baseline')
    primary = one([r for r in saved['attitude_report']['cases'] if r['mode'] == 'full_pco_30s_attitude'], 'baseline')
    models, details = {}, []
    for st in saved['station_report']['stations']:
        models[st['station']], detail = station_model(st, frame, context.date_gpst, context.times)
        reference = apriori(frame[tag+'_apriori.txt'], st)
        delta = np.array(detail['catalog_at_daily_epoch_m'])-reference
        detail.update(daily_apriori_m=reference.tolist(), catalog_minus_daily_apriori_m=delta.tolist(),
                      catalog_minus_daily_apriori_norm_m=float(np.linalg.norm(delta)),
                      apriori_consistency='WITHIN_1_MM' if np.linalg.norm(delta) <= .001 else 'DIFFERS_OVER_1_MM')
        details.append(detail)
    cases = []
    for mode in MODES:
        calibrations = {}
        for name in names:
            try:
                obs = translate_observations(admitted['stations'][name]['reference_observations'], corrections, context.target)
                fixed = {e['time_s']: e['references'] for e in primary['calibration'][name]['epochs']}
                base = models[name](mode, context.times[0])
                offsets = {t: models[name](mode, t)-base for t in context.times}
                def model(sv, code, t, station, clock):
                    return provider.model(sv, code, t, station+offsets[t], clock)
                calibrations[name] = calibrate_fixed(obs, base, context, fixed, model)
            except Exception as error:
                calibrations[name] = {'status': 'ENGINEERING_FAILURE', 'reason': type(error).__name__+': '+str(error), 'epochs': []}
        residuals = [v for cal in calibrations.values() for e in cal['epochs'] for v in e['residuals_m']]
        complete = all(c['status'] == 'CALIBRATION_QUALIFIED' for c in calibrations.values())
        case = {'mode': mode, 'status': 'CALIBRATION_QUALIFIED' if complete else 'CALIBRATION_NOT_QUALIFIED',
                'calibrations': calibrations, 'evaluated_path_count': len(residuals),
                'pooled_reference_rms_m': float(np.sqrt(np.mean(np.square(residuals)))) if complete else None}
        if mode == 'header' and complete:
            delta = [abs(v-w) for name in names for e, old in zip(calibrations[name]['epochs'], primary['calibration'][name]['epochs'], strict=True)
                     for v, w in zip(e['residuals_m'], old['residuals_m'], strict=True)]
            case['baseline_residual_replay_max_abs_m'] = max(delta)
            if max(delta) > 1e-6:
                raise ValueError('reference baseline replay differs')
        cases.append(case)
        if progress:
            progress({k: v for k, v in case.items() if k != 'calibrations'})
    baseline = cases[0]['calibrations']
    for case in cases:
        for name, cal in case['calibrations'].items():
            if cal['status'] == baseline[name]['status'] == 'CALIBRATION_QUALIFIED':
                cal['clock_change_m'] = [e['clock_m']-b['clock_m'] for e, b in zip(cal['epochs'], baseline[name]['epochs'], strict=True)]
    sources = verification['sources_sha256'] | {'research/exploratory/station_frame_epoch.py': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    return {'schema': 'station-frame-epoch-v1', 'target_excluded': context.target, 'date_gpst': context.date_gpst,
            'fit_stations': names, 'input_sha256': verification['input_sha256'] | frame_hashes | product_hashes | attitude_hashes,
            'sources_sha256': sources, 'station_models': details, 'cases': cases,
            'status_counts': dict(Counter(c['status'] for c in cases)), 'case_count': len(cases),
            'observed_path_count': saved['reference_report']['observed_path_count'],
            'omitted_paths': saved['reference_report']['omitted_paths'],
            'time_convention': 'Elapsed Gregorian calendar seconds / 365.25 days; station epochs on the existing GPST calendar. 18 s tag sensitivity retained.',
            'frame_scope': 'IGc20_0 catalogue regularized coordinates; daily a-priori consistency checked, final/rapid realization errors not measured',
            'unmodelled': ['solid-Earth and pole tides', 'ocean and atmospheric loading', 'seasonal terms',
                          'receiver code antenna response', 'physical covariance and frame-realization errors'],
            'instantaneous_site_position_qualified': False, 'target_fit_performed': False, 'target_orbit_accessed': False,
            'new_confirmation': False, 'qualified_error_budget': False, 'applied_to_production_estimator': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', choices=('g14', 'g12'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run(args.tag, progress=lambda x: print(json.dumps(x), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
