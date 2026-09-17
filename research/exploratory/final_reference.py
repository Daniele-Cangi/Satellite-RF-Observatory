"""Fixed RF/path CODE rapid versus paired final products; no target fit."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import numpy as np

from positioning.calibration import C, OMEGA, rotate_z, geodetic
from . import station_frame_epoch as frame
from . import vmf3_reference_study as atmosphere
from .reference_residual_structure_v2 import predict_block, describe
from .hour_reference_v2 import COMPATIBILITY_SHA

from . import final_reference_products as selected
from .reference_residual_structure_v2 import center_blocks, rms, correlation


def run(progress=None):
    choice,plan,ctx,observations,positions,prior,receipt,texts = selected.inputs()
    provider,corrections = selected.products(choice,plan,ctx,texts)
    mjd_day = (datetime.fromisoformat(ctx.date_gpst)-datetime(1858,11,17)).days
    weather = atmosphere.meteo.WeatherGrid(atmosphere.meteo.read_inputs()[0])
    calibrations, rows, omitted = {}, [], prior['omitted_paths']
    for name in plan['stations']:
        try:
            sequence = np.array(positions[name]); base = sequence[0]
            deltas = dict(zip(ctx.times, sequence-base, strict=True))
            obs = frame.translate_observations(observations[name], corrections, ctx.target)
            fixed = {epoch['time_s']:epoch['references'] for epoch in prior['calibrations'][name]['epochs']}
            def model(sv, code, t, station, clock):
                xyz = station+deltas[t]
                value, elevation = provider.model(sv, code, t, xyz, clock)
                delay, _ = atmosphere.components(provider, weather, mjd_day, sv, code, t, xyz, clock)
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
    result = {'schema':'final-reference-prediction-v1','source_compatibility_sha256':COMPATIBILITY_SHA,'plan':plan,'receipt_sha256':selected.RECEIPT_SHA,'comparison_plan':choice,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'mjd_day':mjd_day,
            'calibrations':calibrations,'status_counts':dict(Counter(c['status'] for c in calibrations.values())),
            'observed_path_count':sum(len(e['if_code_m']) for obs in observations.values() for e in obs),
            'evaluated_path_count':len(rows),'omitted_paths':omitted,'rows':rows,
            'training_times':sorted({r['time_s'] for r in training}),'test_times':sorted({r['time_s'] for r in testing}),
            'predictions':predictions,'description':describe(rows,plan['stations'],plan['references']) if complete else None,
            'calibration_complete':complete,'product_sha256':receipt['files'],
            'meteorology_receipt_sha256':atmosphere.meteo.RECEIPT_SHA,
            'prediction_quantity':'station/epoch clock-free residual contrasts; receiver clocks recalibrated at test epochs',
            'target_fit_performed':False,'target_orbit_accessed':False,'new_confirmation':False,
            'physical_covariance_qualified':False,'absolute_future_rf_prediction':False}


    if complete:
        result['comparison'] = compare(prior,result)
        rapid_training = [r for r in prior['rows'] if r['time_s'] < plan['training_before_gpst_s']]
        result['rapid_training_to_final_test'] = predict_block(rapid_training,testing,'shared_satellite')
    else:
        result['comparison'] = None
        result['rapid_training_to_final_test'] = None
    return result


def key(row):
    return row['station'],row['time_s'],row['reference']


def compare(rapid,final):
    if [key(r) for r in rapid['rows']] != [key(r) for r in final['rows']]:
        raise ValueError('fixed path cohort changed; no matched-subset rescue')
    split = final['plan']['training_before_gpst_s']
    a = center_blocks([r['residual_m'] for r in rapid['rows']],rapid['rows'])
    b = center_blocks([r['residual_m'] for r in final['rows']],final['rows'])
    delta = b-a
    mask = np.array([r['time_s'] >= split for r in final['rows']])
    scores = []
    for old,new in zip(rapid['predictions'],final['predictions'],strict=True):
        if old['model'] != new['model'] or [key(r) for r in old['test_predictions']] != [key(r) for r in new['test_predictions']]:
            raise ValueError('prediction cohort differs')
        scores.append({'model':new['model'],'rapid_rms_m':old['all_test_error_rms_m'],
                       'final_rms_m':new['all_test_error_rms_m'],
                       'rapid_supported_count':old['predicted_count'],'final_supported_count':new['predicted_count']})
    stations = []
    for name in final['plan']['stations']:
        take = mask & np.array([r['station']==name for r in final['rows']])
        stations.append({'station':name,'test_count':int(take.sum()),'rapid_zero_rms_m':rms(a[take]),
                         'final_zero_rms_m':rms(b[take]),'final_minus_rapid_rms_m':rms(delta[take]),
                         'residual_correlation':correlation(a[take],b[take])})
    return {'identical_observed_paths':True,'identical_training_test_paths':True,
            'models':scores,'station_scores':stations,'test_final_minus_rapid_rms_m':rms(delta[mask]),
            'test_residual_correlation':correlation(a[mask],b[mask]),
            'quantity':'Centered final-minus-rapid residual contrast; paired-product sensitivity, not error against truth'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    result = run(lambda value:print(json.dumps(value),flush=True))
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
