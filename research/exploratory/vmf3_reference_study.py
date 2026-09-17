"""Fixed-reference RF replay with coordinate-aware VMF3; exposed events only."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from positioning.calibration import C, OMEGA, geodetic, rotate_z, troposphere
from . import station_frame_epoch as frame
from . import solid_earth_study as solid
from . import vmf3_grid_model as meteo
from .erp_polar_bound import pinned, strict_json

BASE = Path(__file__).parent
MODES = ('legacy_baseline', 'vmf3_zenith_only', 'vmf3_mapping_only', 'vmf3_full')
BENCHMARK_SHA = '973d79b3cd5da1d1b94ba44399279b0d039a24aa1ee20acdb778e158272927ee'


def components(provider, weather, mjd_day, sv, code, t, station, clock):
    _, _, satellite, offset = provider.antenna_state(sv, code, t)
    tau = -clock/C-offset
    if not 0 < tau < 1:
        raise ValueError('invalid light time')
    rotated = rotate_z(satellite, -OMEGA*tau)
    old, elevation = troposphere(station, rotated)
    lat, lon, height, _ = geodetic(station)
    # Receiver-clock correction precedes GPST -> UTC conversion (18 s here).
    mjd = mjd_day + (t-clock/C-18)/86400
    mh, mw, dry, wet = weather.evaluate(mjd, math.degrees(lat), math.degrees(lon), float(height), elevation)
    simple_dry = 2.3*math.exp(-.000116*height)
    legacy_mapping = 1.001/math.sqrt(.002001+math.sin(math.radians(elevation))**2)
    delays = {'legacy_baseline': old, 'vmf3_zenith_only': (dry+wet)*legacy_mapping,
              'vmf3_mapping_only': simple_dry*mh+.1*mw, 'vmf3_full': dry*mh+wet*mw}
    return delays, {'elevation_deg': float(elevation), 'mjd_utc': mjd,
                    'mfh': float(mh), 'mfw': float(mw), 'zhd_m': float(dry), 'zwd_m': float(wet)}


def run(tag, progress=None):
    buffers, receipt = meteo.read_inputs()
    weather = meteo.WeatherGrid(buffers)
    benchmark = strict_json(pinned(BASE/'results/vmf3_benchmark_v1.json', BENCHMARK_SHA))
    if benchmark['qualified_count'] != benchmark['case_count'] or benchmark['case_count'] != 88:
        raise ValueError('unqualified original-routine comparison')
    for name, digest in benchmark['source_sha256'].items():
        pinned(BASE/name, digest)
    reports = {}
    for name, digest in receipt['prior_sha256'].items():
        reports[name] = strict_json(pinned(BASE/name, digest))
    prior = reports[f'results/{tag}_ocean_pole_v1.json']
    terrestrial = reports[f'results/{tag}_station_frame_epoch_v1.json']
    tides = reports[f'results/{tag}_solid_earth_v1.json']
    for name, digest in prior['sources_sha256'].items():
        pinned(frame.ROOT/name, digest)
    admitted, context, _, archive_hashes = frame.verified.load_inputs(frame.verified.paths(tag)['admission_receipt'].parent)
    rr = strict_json(pinned(frame.verified.paths(tag)['reference_report'], frame.verified.PINS[tag]['reference_report']))
    attitude_report = strict_json(pinned(frame.verified.paths(tag)['attitude_report'], frame.verified.PINS[tag]['attitude_report']))
    precise, corrections, ph = frame.guarded_products(context, rr['references'], frame.verified.INPUTS/f'timed_reference_products/{tag}',
                                                     frame.verified.INPUTS/f'reference_biases/{tag}', frame.verified.INPUTS/f'reference_antennas/{tag}')
    attitude, ah = frame.load_attitude(frame.verified.INPUTS/f'reference_attitudes/{tag}', context, rr['references'])
    if archive_hashes | ph | ah != attitude_report['input_sha256']:
        raise ValueError('paired reference inputs differ')
    provider = frame.AttitudeReference(precise, attitude)
    prior_case = next(c for c in prior['cases'] if c['mode'] == 'ocean_ce_plus_pole_2018')
    if prior['fit_stations'] != admitted['fit_stations'] or prior['times_gpst_s'] != list(context.times):
        raise ValueError('station/time cohort differs')
    positions = {}
    for model in terrestrial['station_models']:
        name = model['station']
        positions[name] = (np.array(model['positions']['final_transport']) +
                           np.array(tides['station_displacements_ecef_m'][name]['solid_earth']) +
                           np.array(prior['station_additional_displacements_ecef_m'][name]['ocean_ce_plus_pole_2018']))
        if positions[name].shape != (context.samples, 3) or not np.isfinite(positions[name]).all():
            raise ValueError('invalid station position sequence')
    if set(positions) != set(admitted['fit_stations']):
        raise ValueError('station positions incomplete')
    mjd_day = (datetime.fromisoformat(context.date_gpst)-datetime(1858, 11, 17)).days
    cases = []
    for mode in MODES:
        calibrations, paths = {}, []
        for name in admitted['fit_stations']:
            try:
                sequence = positions[name]
                base = sequence[0]
                delta = {t: p-base for t, p in zip(context.times, sequence, strict=True)}
                fixed = {e['time_s']: e['references'] for e in prior_case['calibrations'][name]['epochs']}
                observations = frame.translate_observations(admitted['stations'][name]['reference_observations'], corrections, context.target)
                def model(sv, code, t, station, clock):
                    xyz = station + delta[t]
                    value, elevation = provider.model(sv, code, t, xyz, clock)
                    if mode != 'legacy_baseline':
                        delays, _ = components(provider, weather, mjd_day, sv, code, t, xyz, clock)
                        value = value - delays['legacy_baseline'] + delays[mode]
                    return value, elevation
                cal = frame.calibrate_fixed(observations, base, context, fixed, model)
                calibrations[name] = cal
                if mode == 'legacy_baseline':
                    saved = {k: v for k, v in prior_case['calibrations'][name].items() if k != 'clock_change_m'}
                    solid.compare_replay(cal, saved)
                codes_by_time = {o['time_s']: o['if_code_m'] for o in observations}
                for epoch in cal['epochs']:
                    t = epoch['time_s']
                    for sv, residual in zip(epoch['references'], epoch['residuals_m'], strict=True):
                        delays, details = components(provider, weather, mjd_day, sv, codes_by_time[t][sv], t, base+delta[t], epoch['clock_m'])
                        paths.append({'station': name, 'time_gpst_s': t, 'reference': sv,
                                      'residual_m': residual, 'delay_change_m': float(delays[mode]-delays['legacy_baseline']), **details})
            except Exception as error:
                calibrations[name] = {'status': 'ENGINEERING_FAILURE', 'reason': type(error).__name__+': '+str(error), 'epochs': []}
        complete = all(c['status'] == 'CALIBRATION_QUALIFIED' for c in calibrations.values())
        residuals = [v for c in calibrations.values() for e in c['epochs'] for v in e['residuals_m']]
        case = {'mode': mode, 'status': 'CALIBRATION_QUALIFIED' if complete else 'CALIBRATION_NOT_QUALIFIED',
                'calibrations': calibrations, 'paths': paths, 'evaluated_path_count': len(residuals),
                'pooled_reference_rms_m': float(np.sqrt(np.mean(np.square(residuals)))) if complete else None}
        cases.append(case)
        if progress:
            progress({k: v for k, v in case.items() if k not in ('calibrations', 'paths')})
    dependencies = prior['sources_sha256'].copy()
    for name in ('vmf3_reference_study.py', 'vmf3_grid_model.py', 'benchmark_vmf3.py', 'erp_polar_bound.py'):
        dependencies['research/exploratory/'+name] = hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    return {'schema': 'vmf3-reference-study-v1', 'target_excluded': context.target, 'fit_stations': admitted['fit_stations'],
            'date_gpst': context.date_gpst, 'times_gpst_s': list(context.times), 'cases': cases,
            'status_counts': dict(Counter(c['status'] for c in cases)),
            'observed_path_count': prior['observed_path_count'], 'omitted_paths': prior['omitted_paths'],
            'input_sha256': archive_hashes | ph | ah, 'prior_sha256': receipt['prior_sha256'],
            'meteorology_receipt_sha256': meteo.RECEIPT_SHA, 'benchmark_sha256': BENCHMARK_SHA,
            'sources_sha256': dependencies, 'model': 'VMF3_OP 1 degree, original grid height transfer and separate dry/wet mapping',
            'target_fit_performed': False, 'target_orbit_accessed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False,
            'limitations': ['two exposed five-minute windows', 'no independent atmosphere truth', 'no gradients',
                            'no new RF time coverage', 'no covariance or position uncertainty qualification']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag', choices=('g14', 'g12'))
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = run(args.tag, lambda x: print(json.dumps(x), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(report, indent=2, allow_nan=False)+'\n')
