"""Exposed G12 shared RF fit; alternate arcs keep holdouts globally excluded.

Four development variants: code / code+phase, central / central+J2. Historical
qualification is exposed and conditional. No target orbit or prior state seeds
the fit, no rejected arc is substituted, and no covariance is rescaled.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path

import numpy as np

from positioning.calibration import geodetic, troposphere
from .real_phase import BASE, digest
from .real_target_interval import TAGS, CALIBRATION, covariance, TargetBelowMask
from . import vmf3_grid_model as meteo
from ..kinematic import dynamic_fit, orbital_dynamics as dynamics
from ..kinematic.synthetic import native

ACCEPTED = 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
MODES = ('code_only','code_phase')
FORCES = (('central',0.),('central_j2',dynamics.J2))


def propagation_model(weather, names):
    """VMF3 at the current trial geometry; no cached target-derived correction.

    Differentiate only metre-scale delays, then chain through geometric light
    time/clock sensitivities. The final mask and bounded weather domain remain
    unchanged. This declared model still adds delay to vacuum light time.
    """
    mjd_day = (datetime(2026,9,5)-datetime(1858,11,17)).days
    def correction(pair, xyz, epoch, *, derivatives=False):
        shape = pair['code_m'].shape
        delay,elevations = np.empty(shape),np.empty(shape)
        state_j = np.empty(shape+(6,)) if derivatives else None
        ground_j = np.empty(shape+(3,)) if derivatives else None
        clock_j = np.empty(shape) if derivatives else None
        for i,j in np.ndindex(shape):
            emitted,station = pair['emission_position_m'][i,j],xyz[j]
            receive = epoch+pair['receive_s'][i,j]
            def value(p,s,t):
                _,elevation = troposphere(s,p)
                if elevation<10.:
                    raise TargetBelowMask(names[j],elevation)
                lat,lon,height,_ = geodetic(s)
                mh,mw,dry,wet = weather.evaluate(mjd_day+(t-18.)/86400.,
                    math.degrees(lat),math.degrees(lon),float(height),elevation)
                return dry*mh+wet*mw,elevation
            delay[i,j],elevations[i,j] = value(emitted,station,receive)
            if not derivatives:
                continue
            # Small corrections can be differentiated without cancellation of
            # the ~25 Mm vacuum path. Geometry and weather both participate.
            de,ds = np.empty(3),np.empty(3)
            for k in range(3):
                e = np.eye(3)[k]
                de[k] = (value(emitted+100*e,station,receive)[0]-value(emitted-100*e,station,receive)[0])/200.
                ds[k] = (value(emitted,station+e,receive)[0]-value(emitted,station-e,receive)[0])/2.
            dt = value(emitted,station,receive+.5)[0]-value(emitted,station,receive-.5)[0]
            velocity = pair['emission_velocity_m_s'][i,j]
            spin = dynamics.OMEGA*np.array([-emitted[1],emitted[0],0.])
            drift = velocity+spin
            unit,denominator = pair['unit_ray'][i,j],pair['light_time_denominator'][i,j]
            emitted_ground = np.outer(drift,unit)/(dynamics.C*denominator)
            emitted_receive = velocity-drift*pair['range_receive_rate_m_s'][i,j]/dynamics.C
            state_j[i,j] = de@pair['emission_initial_state_derivative'][i,j]
            ground_j[i,j] = ds+de@emitted_ground
            clock_j[i,j] = -(de@emitted_receive+dt)/dynamics.C
        result = {'delay_m':delay,'elevation_deg':elevations}
        if derivatives:
            result.update(initial_state_derivative=state_j,station_derivative=ground_j,
                          receiver_clock_derivative=clock_j)
        return result
    return correction


def cohort(hour, mode):
    """Fixed chronological even-index rule; retain every inherited outcome."""
    retained,selected = [],[]
    for index,case in enumerate(hour['cases']):
        if case['start_gpst_s']!=36000+90*index or len(hour['cases'])!=40:
            raise ValueError('historical forty-window chronology differs')
        status = case.get('fits',{}).get(mode,{}).get('status')
        use = index%2==0 and case['status']=='EVALUATED' and status==ACCEPTED
        retained.append({'index':index,'start_gpst_s':case['start_gpst_s'],
            'historical_status':case['status'],'historical_fit_status':status,
            'selected':use,'selection_reason':'ALTERNATE_WINDOW_RESERVED' if index%2 else
                'INHERITED_ACCEPTED' if use else 'INHERITED_UNAVAILABLE_OR_REJECTED'})
        if use:
            selected.append(case)
    training = {(s,c['start_gpst_s']+t) for c in selected for s in c['stations'] for t in (0,30,60)}
    withheld = {(s,c['start_gpst_s']+90) for c in selected for s in c['stations']}
    if training & withheld:
        raise ValueError('excluded endpoints overlap shared-fit training observations')
    return selected,{'rule':'even chronological indices; inherited accepted status; no replacement',
        'retained_outcomes':retained,'training_keys':sorted(training),'withheld_endpoint_keys':sorted(withheld)}


def training_arcs(cases, target, positions, baseline, reference_clock, mode):
    """Decode only three training endpoints; historical fitted states unused."""
    clocks = {(r['station'],r['time_s']):r for r in reference_clock['phase_clock_rates']}
    # Validate the independent calibrations for the complete cohort first.
    for c in cases:
        for s in c['stations']:
            if baseline['calibrations'][s]['status']!='CALIBRATION_QUALIFIED' or any(
                    clocks[s,c['start_gpst_s']+t]['estimators']['median']['status']!='ESTIMATED' for t in (30,60)):
                raise ValueError('reference calibration rejected before target decoding')
    names = set(s for c in cases for s in c['stations'])
    rows = {s:{r['time_s']:r for r in target['stations'][s]['rows']} for s in names}
    arcs = []
    for c in cases:
        start,names = c['start_gpst_s'],c['stations']
        selected = [[rows[s][start+t] for s in names] for t in (0,30,60)]
        if any(r['status']!='AVAILABLE' for part in selected for r in part):
            raise ValueError('historically admitted training window unavailable')
        codes = np.array([[r['code_m'] for r in part] for part in selected])
        rates = np.diff(np.array([[r['phase_m'] for r in part] for part in selected]),axis=0)/30. if mode=='code_phase' else []
        clock_mean = np.array([[next(e['clock_m'] for e in baseline['calibrations'][s]['epochs']
                            if e['time_s']==start+60),
                            np.mean([clocks[s,start+t]['estimators']['median']['rate_m_s'] for t in (30,60)])]
                            for s in names])
        whole,code_cov = covariance(len(names))
        arcs.append({'stations':names,'endpoint_gpst_s':start+60,'tags_s':TAGS,
            'stations_m':np.array([positions[s][(start+60-36000)//30] for s in names]),
            'clock_mean':clock_mean,'codes_m':codes,'rates_m_s':rates,
            'calibration_statuses':[CALIBRATION]*len(names),
            'covariance':whole if mode=='code_phase' else code_cov})
    return arcs


def predict(fitted, arcs, weather):
    """All excluded predictions and VMF3 paths before reading held-out RF."""
    if 'state_ecef_m_m_s' not in fitted:
        return [{'endpoint_gpst_s':a['endpoint_gpst_s'],'status':'FIT_UNAVAILABLE'} for a in arcs]
    epoch = fitted['epoch_gpst_s']
    curve = dynamics.Trajectory(fitted['state_ecef_m_m_s'],fitted['integrated_bounds_s'],j2=fitted['j2'])
    last_training = max(a['endpoint_gpst_s'] for a in arcs)
    predictions = []
    for a,p in zip(sorted(arcs,key=lambda a:a['endpoint_gpst_s']),fitted['arc_parameters'],strict=True):
        record = {'endpoint_gpst_s':a['endpoint_gpst_s'],'withheld_gpst_s':a['endpoint_gpst_s']+30,
            'kind':'BEYOND_ALL_TRAINING' if a['endpoint_gpst_s']+30>last_training else 'TEMPORAL_HOLDOUT',
            'fit_status':fitted['status']}
        try:
            xyz = a['stations_m']+np.asarray(p['station_corrections_m'])
            pair = dynamics.predict_observations(curve,a['endpoint_gpst_s']-epoch,[0.,30.],xyz,
                        p['receiver_clocks'],p['satellite_clock'])
            correction = propagation_model(weather,a['stations'])(pair,xyz,epoch)
            delays,elevations = correction['delay_m'],correction['elevation_deg']
            record.update(status='PREDICTED',stations=a['stations'],
                code_m=pair['code_m'][1]+delays[1]+np.array([fitted['station_code_bias_m'][s] for s in a['stations']]),
                phase_rate_m_s=(np.diff(pair['code_m'],axis=0)[0]+np.diff(delays,axis=0)[0])/30.,
                propagation_m=delays,elevation_deg=elevations)
        except (ValueError,np.linalg.LinAlgError) as error:
            record.update(status='PREDICTION_FAILED',reason=str(error))
        predictions.append(record)
    return native(predictions)


def score(predictions, cases, target, mode):
    """Score fixed predictions, keeping rejected fits and worsening pairs visible."""
    names = {s for p in predictions if p['status']=='PREDICTED' for s in p['stations']}
    rows = {s:{r['time_s']:r for r in target['stations'][s]['rows']} for s in names}
    by_end = {c['start_gpst_s']+60:c for c in cases}
    retained = []
    for p in predictions:
        r = {'endpoint_gpst_s':p['endpoint_gpst_s'],'prediction_status':p['status']}
        if p['status']!='PREDICTED':
            retained.append({**r,'status':'UNSCORED'})
            continue
        end = p['endpoint_gpst_s']
        old = {v['station']:v for v in by_end[end]['fits'][mode]['withheld']}
        pairs = []
        try:
            for j,s in enumerate(p['stations']):
                future,previous = rows[s][end+30],rows[s][end]
                if future['status']!='AVAILABLE' or previous['status']!='AVAILABLE':
                    raise ValueError('excluded observation unavailable')
                code = future['code_m']-p['code_m'][j]
                rate = (future['phase_m']-previous['phase_m'])/30.-p['phase_rate_m_s'][j]
                pairs.append({'station':s,'code_residual_m':code,'phase_rate_residual_m_s':rate,
                    'old_code_residual_m':old[s]['code_residual_m'],
                    'old_phase_rate_residual_m_s':old[s]['phase_rate_residual_m_s'],
                    'code_worsened':abs(code)>abs(old[s]['code_residual_m']),
                    'phase_worsened':abs(rate)>abs(old[s]['phase_rate_residual_m_s'])})
        except (ValueError,KeyError) as error:
            r.update(status='WITHHELD_UNAVAILABLE',reason=str(error))
        else:
            r.update(status='SCORED',kind=p['kind'],fit_status=p['fit_status'],pairs=pairs)
        retained.append(r)
    summary = {'window_status_counts':dict(Counter(r['status'] for r in retained)),
               'predictions_for_rejected_models_are_diagnostic':True}
    for kind in ['ALL','TEMPORAL_HOLDOUT','BEYOND_ALL_TRAINING']:
        pairs = [p for r in retained if r['status']=='SCORED' and (kind=='ALL' or r['kind']==kind) for p in r['pairs']]
        group = {'pair_count':len(pairs)}
        if pairs:
            for name,field in [('code','code_residual_m'),('phase','phase_rate_residual_m_s')]:
                group[name] = {'rms':float(np.sqrt(np.mean([p[field]**2 for p in pairs]))),
                    'old_same_cohort_rms':float(np.sqrt(np.mean([p['old_'+field]**2 for p in pairs]))),
                    'worsened_pair_count':sum(p[name+'_worsened'] for p in pairs)}
        summary[kind] = group
    return native(retained),summary


def run():
    files = {'hour':BASE/'results/g12_full_hour_v1.json',
        'target':BASE/'inputs/real_phase/g12_target_phase_v2.json',
        'access':BASE/'real_target_phase_access_v2.json',
        'positions':BASE/'inputs/day_reference/positions.json',
        'baseline':BASE/'results/day_reference_v1.json',
        'reference_phase_input':BASE/'inputs/real_phase/observations_gps_only_v2.json',
        'reference_clock':BASE/'results/reference_phase_clock_full_hour_v1.json'}
    raw = {k:p.read_bytes() for k,p in files.items()}
    data = {k:json.loads(v) for k,v in raw.items()}
    hour,target,baseline,clock = [data[k] for k in ['hour','target','baseline','reference_clock']]
    if (hour['target_orbit_used'] or hour['oracle_error_used'] or hour['new_confirmation']
            or any(hour['input_sha256'][k]!=digest(raw[k]) for k in files if k!='hour')
            or target['target_state_accessed'] or target['access_sha256']!=digest(raw['access'])
            or baseline['target_orbit_accessed'] or not baseline['calibration_complete']
            or clock['target_values_accessed'] or clock['target_excluded']!='G12'
            or clock['evaluation_after_gpst_s']!=36000
            or clock['input_sha256']!=digest(raw['reference_phase_input'])
            or clock['baseline_report_sha256']!=digest(raw['baseline'])):
        raise ValueError('historical RF or independent reference input boundary differs')
    weather = meteo.WeatherGrid(meteo.read_inputs()[0])
    results,selections = {},{}
    for mode in MODES:
        cases,selection = cohort(hour,mode)
        arcs = training_arcs(cases,target,data['positions'],baseline,clock,mode)
        for arc in arcs:
            arc['propagation'] = propagation_model(weather,arc['stations'])
        selections[mode] = cases
        for force,j2 in FORCES:
            label = mode+'_'+force
            def progress(r):
                print(label,r,flush=True)
            try:
                fitted = dynamic_fit.fit(arcs,include_phase=mode=='code_phase',j2=j2,progress=progress)
            except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                fitted = {'status':'FIT_FAILED','reason':str(error)}
            predictions = predict(fitted,arcs,weather)
            results[label] = {'fit':native(fitted),'cohort':selection,'predictions':predictions,
                'frozen_prediction_sha256':digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode())}
    # All four variants have fixed predictions before any held-out value is scored.
    for label,result in results.items():
        mode = 'code_phase' if label.startswith('code_phase') else 'code_only'
        result['withheld'],result['summary'] = score(result['predictions'],selections[mode],target,mode)
    producers = [Path(__file__),Path(dynamic_fit.__file__),Path(dynamics.__file__)]
    return native({'schema':'exposed-g12-shared-dynamic-fit-v2',
        'scope':'RF-only shared dynamic fit with free constant differential station code bias and conditional independent-arc weights. Exposed historical qualifications; mostly temporal holdouts and one beyond-all-training endpoint per estimator. Force, atmosphere, clock, bias stability and joint physical covariance unqualified.',
        'target_orbit_used':False,'oracle_error_used':False,'prior_target_state_used':False,
        'historical_fit_geometry_used':False,
        'physical_covariance_qualified':False,'production_floors_changed':False,'new_confirmation':False,
        'historical_code_floor_m':20.,'target_elevation_mask_deg':10.,
        'training_propagation':'VMF3 recomputed at the current shared trial geometry, with state/clock/ground derivatives',
        'superseded_independence_claim':{'reports':['g12_dynamic_fit_v1.json','g12_dynamic_fit_v2.json','g12_dynamic_fit_v3.json'],
            'reason':'Historical RF-fitted propagation entered preprocessing. No known target orbit was used, but prior_target_state_used=False understated that dependence. Old bytes/results remain historical diagnostics, not evidence for a fit independent of prior target geometry.'},
        'input_sha256':{k:digest(v) for k,v in raw.items()},
        'weather_receipt_sha256':meteo.RECEIPT_SHA,
        'source_sha256':{p.name:digest(p.read_bytes()) for p in producers},'variants':results})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; retain previous results')
    result = run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
