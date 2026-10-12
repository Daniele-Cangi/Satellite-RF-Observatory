"""Qualify exposed G12 hour and compare geometry with changing receiver paths.

Reuse the short-arc inverse; do not extend its quadratic trajectory to an hour.
All RF rejections remain visible. The target orbit and oracle are never opened.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

import numpy as np
from scipy.linalg import helmert

from .real_phase import BASE, digest
from .real_target_interval import CALIBRATION, TAGS, covariance, fit_case
from . import vmf3_grid_model as meteo
from .g12_bias_geometry import profile_bias, combine_profiles, derivative_profile
from ..kinematic.interval_fit import fit_intervals
from ..kinematic.synthetic import native

COMMON = ('ALGO00CAN','DRAO00CAN','AREQ00PER','BOGT00COL')
GLOBAL_STATIONS = COMMON+('STJO00CAN','BRAZ00BRA')


def station_selection(start):
    """Fixed exposed-coverage rule, never chosen by residual or oracle."""
    return ('ALGO00CAN','DRAO00CAN',
            'STJO00CAN' if start < 37800 else 'BRAZ00BRA',
            'AREQ00PER','BOGT00COL')


def global_profile(local, stations):
    """Map local zero-mean contrasts into a common six-receiver gauge."""
    local_basis=helmert(len(stations),full=False).T
    global_basis=helmert(len(GLOBAL_STATIONS),full=False).T
    indices=[GLOBAL_STATIONS.index(s) for s in stations]
    return np.asarray(local)@local_basis.T@global_basis[indices]


def profile_case(case,target,positions,stations):
    start=case['start_gpst_s']
    times=[start,start+30,start+60]
    rows={s:{r['time_s']:r for r in target['stations'][s]['rows']} for s in stations}
    code=np.array([[rows[s][t]['code_m'] for s in stations] for t in times])
    phase=np.array([[rows[s][t]['phase_m'] for s in stations] for t in times])
    xyz=np.array([positions[s][(start+60-36000)//30] for s in stations])
    delays=np.asarray(case['propagation_m'])
    rates=np.diff(phase,axis=0)/30-np.diff(delays,axis=0)/30
    whole,code_cov=covariance(len(stations))
    result={}
    for name,use_phase,cov in [('code_only',False,code_cov),('code_phase',True,whole)]:
        old=case['fits'][name]
        if old['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
            continue
        fit=fit_intervals(TAGS,xyz,code-delays,rates,np.asarray(case['clock_prior']),cov,
                         calibration_statuses=[CALIBRATION]*len(stations),include_phase=use_phase)
        if (fit['status'] != old['status'] or fit['fit_covariance_sha256'] != old['fit_covariance_sha256']
                or not np.allclose(fit['state'],old['state'],rtol=0,atol=1e-5)):
            raise ValueError('accepted short-arc fit is not reproducible')
        profile,_,slope=profile_bias(fit['data_jacobian'],cov,fit['parameter_scale'],len(stations))
        result[name]={'start_gpst_s':start,'stations':stations,
            'profile_per_m':global_profile(profile,stations).tolist(),
            'slope_profile_per_m_s':global_profile(slope,stations).tolist()}
        alternatives={}
        for factor in (.5,2.):
            alternate,_,alternate_slope=derivative_profile(fit,xyz,cov,use_phase,1e-5*factor)
            alternatives[str(factor)]={
                'profile_per_m':global_profile(alternate,stations).tolist(),
                'slope_profile_per_m_s':global_profile(alternate_slope,stations).tolist()}
        result[name]['derivative_step_alternatives']=alternatives
    return result


def run(clock_path):
    files={'target':BASE/'inputs/real_phase/g12_target_phase_v2.json',
           'baseline':BASE/'results/day_reference_v1.json',
           'positions':BASE/'inputs/day_reference/positions.json',
           'access':BASE/'real_target_phase_access_v2.json',
           'historical_rf':BASE/'results/real_target_interval_v2.json',
           'reference_phase_input':BASE/'inputs/real_phase/observations_gps_only_v2.json',
           'reference_clock':clock_path}
    raw={k:p.read_bytes() for k,p in files.items()}
    data={k:json.loads(v) for k,v in raw.items()}
    target,baseline,clock=data['target'],data['baseline'],data['reference_clock']
    if (target['target_state_accessed'] or baseline['target_orbit_accessed']
            or not baseline['calibration_complete']
            or target['access_sha256']!=digest(raw['access'])
            or data['historical_rf']['target_input_sha256']!=digest(raw['target'])
            or data['historical_rf']['baseline_sha256']!=digest(raw['baseline'])
            or clock['target_values_accessed'] or clock['target_excluded']!='G12'
            or clock['evaluation_after_gpst_s']!=36000
            or clock['input_sha256']!=digest(raw['reference_phase_input'])
            or clock['baseline_report_sha256']!=digest(raw['baseline'])):
        raise ValueError('full-hour reference calibration/input boundary differs')
    clocks={(r['station'],r['time_s']):r for r in clock['phase_clock_rates']}
    weather=meteo.WeatherGrid(meteo.read_inputs()[0])
    mjd=(datetime(2026,9,5)-datetime(1858,11,17)).days
    cases=[]
    profiles={'code_only':[],'code_phase':[]}
    for i in range(40):
        start=36000+90*i
        stations=station_selection(start)
        try:
            case=fit_case(target,baseline,clocks,data['positions'],start,weather,mjd,stations)
        except (ValueError,KeyError,IndexError) as error:
            case={'status':'CASE_FAILED','reason':str(error),'start_gpst_s':start}
        case.update(start_gpst_s=start,stations=stations)
        if case['status']=='EVALUATED':
            for name,profile in profile_case(case,target,data['positions'],stations).items():
                profiles[name].append(profile)
        cases.append(case)
        print(start,case['status'],{k:v['status'] for k,v in case.get('fits',{}).items()},flush=True)
    combined={}
    robustness={}
    for name,arcs in profiles.items():
        combined[name]={'constant':combine_profiles(arcs),
            'linear_drift':combine_profiles(arcs,linear_drift=True)} if len(arcs)>1 else None
        robustness[name]={}
        if len(arcs)>1:
            for factor in ('0.5','2.0'):
                alternate=[{'start_gpst_s':a['start_gpst_s'],
                    **a['derivative_step_alternatives'][factor]} for a in arcs]
                robustness[name][factor]={'constant':combine_profiles(alternate),
                    'linear_drift':combine_profiles(alternate,linear_drift=True)}
    return native({'schema':'exposed-g12-full-hour-v1',
        'scope':'Exposed-data qualification and local geometry diagnosis using unchanged 60 s fits, original 10 degree mask and covariance. Block-independent arc weights and shared constant/drifting effective station bias assumptions remain conditional. No physical covariance, target-orbit input or new confirmation.',
        'target_orbit_used':False,'oracle_error_used':False,'new_confirmation':False,
        'historical_code_floor_m':20.,'target_elevation_mask_deg':10.,
        'input_sha256':{k:digest(v) for k,v in raw.items()},
        'source_sha256':digest(Path(__file__).read_bytes()),
        'global_stations':GLOBAL_STATIONS,'cases':cases,'profiles':profiles,
        'case_status_counts':dict(Counter(c['status'] for c in cases)),
        'combined':combined,'finite_difference_robustness':robustness})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--clock-report',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('output exists; retain previous reports')
    result=run(args.clock_report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
