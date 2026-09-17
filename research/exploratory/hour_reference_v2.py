"""One-hour reference-only contrast prediction; not absolute future RF or position."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import numpy as np

from positioning.context import Context
from positioning.calibration import C, OMEGA, rotate_z, geodetic
from . import station_frame_epoch as frame
from . import vmf3_reference_study as atmosphere
from .reference_residual_structure_v2 import predict_block, describe
from .erp_polar_bound import pinned, strict_json

BASE = Path(__file__).parent
INPUTS = BASE/'inputs/hour_reference'
COMPATIBILITY_SHA = '66e2baf11a437092d5f151095033b15b2d2d6d28214efa460319acdd4533c3c4'


def source_bytes(path, digest):
    compatibility = strict_json(pinned(BASE/'inputs/hour_source_bytes/receipt.json', COMPATIBILITY_SHA))
    name = path.relative_to(frame.ROOT).as_posix()
    if name not in compatibility:
        return pinned(path, digest)
    entry = compatibility[name]
    if digest != entry['executed_sha256']:
        raise ValueError('source compatibility identity differs')
    original = pinned(BASE/entry['snapshot'], digest)
    raw = path.read_bytes()
    if hashlib.sha256(original.replace(b'\r\n', b'\n')).hexdigest() != entry['git_lf_sha256']:
        raise ValueError('invalid source compatibility evidence')
    if raw != original and raw != original.replace(b'\r\n', b'\n'):
        raise ValueError('source changed beyond declared line endings')
    return raw


RECEIPT_SHA = '691ef86e9814f5b50c504ea3ccf47a334e6ec9dfe524c340ad041762183a757f'


def inputs():
    receipt = strict_json(pinned(INPUTS/'receipt.json', RECEIPT_SHA))
    for path, digest in receipt['sources_sha256'].items():
        source_bytes(frame.ROOT/path, digest)
    buffers = {name: pinned(INPUTS/name, digest) for name, digest in receipt['files'].items()}
    plan = strict_json(pinned(BASE/'hour_reference_plan.json', receipt['plan_sha256']))
    ctx = Context(plan['target_excluded'], plan['date_gpst'], plan['start_gpst_s'], plan['samples'], plan['step_s'])
    obs, positions = strict_json(buffers['observations.json']), strict_json(buffers['positions.json'])
    if set(obs) != set(plan['stations']) or set(positions) != set(plan['stations']):
        raise ValueError('station cohort differs')
    for name in plan['stations']:
        if [e['time_s'] for e in obs[name]] != list(ctx.times) or np.shape(positions[name]) != (ctx.samples, 3):
            raise ValueError('epoch cohort differs')
        if any(not set(e['if_code_m']) <= set(plan['references']) for e in obs[name]) or ctx.target in plan['references']:
            raise ValueError('unadmitted reference')
    return plan, ctx, obs, positions, receipt


def run(progress=None):
    plan, ctx, observations, positions, receipt = inputs()
    precise, corrections, hashes = frame.guarded_products(ctx, plan['references'], INPUTS/'timed',
                        BASE/'inputs/reference_biases/g14', BASE/'inputs/reference_antennas/g14')
    attitude, ah = frame.load_attitude(INPUTS/'attitude', ctx, plan['references'])
    provider = frame.AttitudeReference(precise, attitude)
    weather = atmosphere.meteo.WeatherGrid(atmosphere.meteo.read_inputs()[0])
    calibrations, rows, omitted = {}, [], []
    for name in plan['stations']:
        try:
            sequence = np.array(positions[name]); base = sequence[0]
            deltas = dict(zip(ctx.times, sequence-base, strict=True))
            obs = frame.translate_observations(observations[name], corrections, ctx.target)
            fixed = {}
            for epoch in obs:
                t = epoch['time_s']; fixed[t] = []
                for sv, code in sorted(epoch['if_code_m'].items()):
                    try:
                        _, elevation = provider.model(sv, code, t, base+deltas[t], 0.)
                        if elevation < plan['minimum_elevation_deg']:
                            omitted.append({'station':name,'time_s':t,'reference':sv,'status':'BELOW_ELEVATION_MASK'})
                        else:
                            fixed[t].append(sv)
                    except Exception as error:
                        omitted.append({'station':name,'time_s':t,'reference':sv,'status':'MODEL_UNAVAILABLE','reason':str(error)})
            def model(sv, code, t, station, clock):
                xyz = station+deltas[t]
                value, elevation = provider.model(sv, code, t, xyz, clock)
                delay, _ = atmosphere.components(provider, weather, 61286, sv, code, t, xyz, clock)
                return value-delay['legacy_baseline']+delay['vmf3_full'], elevation
            cal = frame.calibrate_fixed(obs, base, ctx, fixed, model)
            calibrations[name] = cal
            codes = {e['time_s']:e['if_code_m'] for e in obs}
            for epoch in cal['epochs']:
                t = epoch['time_s']; xyz = base+deltas[t]
                lat, lon, _, up = geodetic(xyz)
                east = np.array([-math.sin(lon),math.cos(lon),0]); north = np.cross(up,east)
                basis = np.array([east,north,up])
                for sv, residual in zip(epoch['references'],epoch['residuals_m'],strict=True):
                    _, _, satellite, offset = provider.antenna_state(sv,codes[t][sv],t)
                    ray = rotate_z(satellite,-OMEGA*(-epoch['clock_m']/C-offset))-xyz
                    los = basis@(ray/np.linalg.norm(ray))
                    rows.append({'station':name,'time_s':t,'reference':sv,'residual_m':residual,
                                 'los_enu':los.tolist(),'elevation_deg':math.degrees(math.asin(los[2]))})
        except Exception as error:
            calibrations[name] = {'status':'ENGINEERING_FAILURE','reason':str(error),'epochs':[]}
            rows = [r for r in rows if r['station'] != name]
        if progress:
            progress({'station':name,'status':calibrations[name]['status']})
    complete = all(c['status']=='CALIBRATION_QUALIFIED' for c in calibrations.values())
    training = [r for r in rows if r['time_s'] < plan['training_before_gpst_s']]
    testing = [r for r in rows if r['time_s'] >= plan['training_before_gpst_s']]
    predictions = [predict_block(training,testing,m) for m in plan['models']] if complete else []
    return {'schema':'hour-reference-prediction-v2','source_compatibility_sha256':COMPATIBILITY_SHA,'plan':plan,'receipt_sha256':RECEIPT_SHA,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'calibrations':calibrations,'status_counts':dict(Counter(c['status'] for c in calibrations.values())),
            'observed_path_count':sum(len(e['if_code_m']) for obs in observations.values() for e in obs),
            'evaluated_path_count':len(rows),'omitted_paths':omitted,'rows':rows,
            'training_times':sorted({r['time_s'] for r in training}),'test_times':sorted({r['time_s'] for r in testing}),
            'predictions':predictions,'description':describe(rows,plan['stations'],plan['references']) if complete else None,
            'calibration_complete':complete,'product_sha256':hashes|ah,
            'meteorology_receipt_sha256':atmosphere.meteo.RECEIPT_SHA,
            'prediction_quantity':'station/epoch clock-free residual contrasts; receiver clocks recalibrated at test epochs',
            'target_fit_performed':False,'target_orbit_accessed':False,'new_confirmation':False,
            'physical_covariance_qualified':False,'absolute_future_rf_prediction':False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run(lambda value: print(json.dumps(value), flush=True))
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
