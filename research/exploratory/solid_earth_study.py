"""Reference-only solid Earth tide sensitivity; exposed events, no target fit."""
import argparse
from collections import Counter
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
import numpy as np
from . import station_frame_epoch as frame
from . import solid_earth_model as tide
from .reference_attitude_model import strict_json

BASE=Path(__file__).parent
INPUTS=BASE/'inputs/solid_earth'
RECEIPT_SHA='2c14975732fdca2a2c4885e0f46652b0464378abde00f025ab918e109974ace6'
FRAME_PINS={'g14': '1b6abc0d29a468941b47e90ca70880a156ae4e259dab9b3615ae4b7526190e6a', 'g12': '6fd24f5849a56df372ddf6a64323bcab08d38bbb03eb542d904fa03805af501e'}
MODES=('regularized','solid_earth','degree_only_control','midpoint_control',
       'permanent_removed_control','gpst_as_utc_control')


def celestial_inputs(tag):
    raw=frame.verified.pinned_bytes(INPUTS/'receipt.json',RECEIPT_SHA)
    receipt=strict_json(raw)
    if receipt['schema']!='solid-earth-inputs-v1' or receipt['target_states_accessed'] is not False or set(receipt['files'])!={'eop.txt','sun_moon.json'}:
        raise ValueError('unexpected celestial manifest')
    frame.verified.pinned_bytes(BASE/'prepare_solid_earth_inputs.py',receipt['producer_sha256'])
    buffers={name:frame.verified.pinned_bytes(INPUTS/name,h) for name,h in receipt['files'].items()}
    data=strict_json(buffers['sun_moon.json'])[tag]
    day,start={'g14':('2026-09-03',14100),'g12':('2026-09-05',37800)}[tag]
    expected=sorted({t+d for t in range(start,start+301,30) for d in (0,18)})
    if data['date_gpst']!=day or [s['time_gpst_s'] for s in data['samples']]!=expected:
        raise ValueError('celestial time grid differs')
    for sample in data['samples']:
        utc=datetime.fromisoformat(day)+timedelta(seconds=sample['time_gpst_s']-18)
        if sample['utc']!=utc.isoformat() or sample['tai_minus_utc_s']!=37:
            raise ValueError('celestial time convention differs')
        for body in ('sun','moon'):
            a=np.array(sample[body+'_ecef_m']); b=np.array(sample[body+'_icrs_m'])
            if a.shape!=(3,) or b.shape!=(3,) or not np.all(np.isfinite(a)) or not np.all(np.isfinite(b)):
                raise ValueError('invalid celestial vector')
            if abs(np.linalg.norm(a)-np.linalg.norm(b))>1e-3:
                raise ValueError('celestial rotation changed vector norm')
    return {s['time_gpst_s']:s for s in data['samples']}, {'celestial_receipt':hashlib.sha256(raw).hexdigest()} | receipt['files']


def compare_replay(a,b,key=None):
    if isinstance(b,dict):
        if set(a)!=set(b): raise ValueError('frame report keys differ')
        for k in b: compare_replay(a[k],b[k],k)
    elif isinstance(b,list):
        if len(a)!=len(b): raise ValueError('frame report length differs')
        for x,y in zip(a,b,strict=True): compare_replay(x,y,key)
    elif isinstance(b,float):
        tolerance=.003 if key in ('ground_offset_xyz_m','ground_offset_m') else 1e-7
        if not np.isfinite(a) or not np.isclose(a,b,rtol=1e-10,atol=tolerance):
            raise ValueError('frame report numerical mismatch: '+str(key))
    elif a!=b: raise ValueError('frame report metadata differs: '+str(key))


def displacements(xyz,sample):
    return tide.displacement_components(xyz,sample['sun_ecef_m'],sample['moon_ecef_m'],
                                       datetime.fromisoformat(sample['utc']),sample['tai_minus_utc_s'])


def station_variants(positions,times,samples):
    primary=[]; degree=[]; shifted=[]
    for xyz,t in zip(positions,times,strict=True):
        components=displacements(xyz,samples[t])
        primary.append(sum(components.values(),np.zeros(3)))
        degree.append(components['degree_2_3'])
        shifted.append(sum(displacements(xyz,samples[t+18]).values(),np.zeros(3)))
    xyz=np.array(positions); primary=np.array(primary)
    midpoint=primary[len(times)//2]
    offsets={'regularized':np.zeros_like(xyz),'solid_earth':primary,'degree_only_control':np.array(degree),
             'midpoint_control':np.repeat(midpoint[None,:],len(times),axis=0),
             'permanent_removed_control':primary-np.array([tide.permanent_displacement(x) for x in xyz]),
             'gpst_as_utc_control':np.array(shifted)}
    return {mode:xyz+offset for mode,offset in offsets.items()}, {mode:offset.tolist() for mode,offset in offsets.items()}


def benchmark_comparisons():
    raw=frame.verified.pinned_bytes(INPUTS/'iers_examples.json','e139b4aee46198bc7b74f000794c45e108ec2a11f84761cd154f6c26f2eff468')
    results=[]
    for case in strict_json(raw):
        calculated=tide.tide_displacement(case['station'],case['sun'],case['moon'],datetime.fromisoformat(case['date']),case['tai_minus_utc'])
        error=float(np.max(np.abs(calculated-case['expected'])))
        results.append({'date':case['date'],'calculated_ecef_m':calculated.tolist(),
                        'published_ecef_m':case['expected'],'max_abs_difference_m':error,
                        'comparison':'MATCH_1_PM' if error<=1e-12 else 'PUBLISHED_EXAMPLE_MISMATCH'})
    return results


def run(tag,progress=None):
    samples,input_hashes=celestial_inputs(tag)
    raw=frame.verified.pinned_bytes(BASE/f'results/{tag}_station_frame_epoch_v1.json',FRAME_PINS[tag])
    saved=strict_json(raw)
    for path,digest in saved['sources_sha256'].items():
        frame.verified.pinned_bytes(frame.ROOT/path,digest)
    actual=frame.run(tag)
    compare_replay(actual,saved)
    admitted,context,_,archive_hashes=frame.verified.load_inputs(frame.verified.paths(tag)['admission_receipt'].parent)
    prior=strict_json(frame.verified.pinned_bytes(frame.verified.paths(tag)['attitude_report'],frame.verified.PINS[tag]['attitude_report']))
    # Use the full admitted reference set from the pinned reference report.
    rr=strict_json(frame.verified.pinned_bytes(frame.verified.paths(tag)['reference_report'],frame.verified.PINS[tag]['reference_report']))
    precise,corrections,product_hashes=frame.guarded_products(context,rr['references'],
        frame.verified.INPUTS/f'timed_reference_products/{tag}',frame.verified.INPUTS/f'reference_biases/{tag}',
        frame.verified.INPUTS/f'reference_antennas/{tag}')
    attitude,attitude_hashes=frame.load_attitude(frame.verified.INPUTS/f'reference_attitudes/{tag}',context,rr['references'])
    if archive_hashes|product_hashes|attitude_hashes != prior['input_sha256']:
        raise ValueError('paired products changed')
    provider=frame.AttitudeReference(precise,attitude)
    baseline=next(c for c in actual['cases'] if c['mode']=='final_transport')
    variants,offsets={},{}
    for station in actual['station_models']:
        name=station['station']
        variants[name],offsets[name]=station_variants(station['positions']['final_transport'],context.times,samples)
    cases=[]
    for mode in MODES:
        calibrations={}
        for name in admitted['fit_stations']:
            try:
                positions=variants[name][mode]; base=positions[0]
                delta={t:p-base for t,p in zip(context.times,positions,strict=True)}
                fixed={e['time_s']:e['references'] for e in baseline['calibrations'][name]['epochs']}
                obs=frame.translate_observations(admitted['stations'][name]['reference_observations'],corrections,context.target)
                def model(sv,code,t,station,clock):
                    return provider.model(sv,code,t,station+delta[t],clock)
                cal=frame.calibrate_fixed(obs,base,context,fixed,model)
                if cal['status']=='CALIBRATION_QUALIFIED':
                    cal['clock_change_m']=[e['clock_m']-b['clock_m'] for e,b in zip(cal['epochs'],baseline['calibrations'][name]['epochs'],strict=True)]
                calibrations[name]=cal
            except Exception as error:
                calibrations[name]={'status':'ENGINEERING_FAILURE','reason':type(error).__name__+': '+str(error),'epochs':[]}
        residuals=[v for cal in calibrations.values() for e in cal['epochs'] for v in e['residuals_m']]
        complete=all(c['status']=='CALIBRATION_QUALIFIED' for c in calibrations.values())
        case={'mode':mode,'status':'CALIBRATION_QUALIFIED' if complete else 'CALIBRATION_NOT_QUALIFIED',
              'calibrations':calibrations,'evaluated_path_count':len(residuals),
              'pooled_reference_rms_m':float(np.sqrt(np.mean(np.square(residuals)))) if complete else None}
        if mode=='regularized' and complete:
            differences=[abs(x-y) for name in admitted['fit_stations'] for e,b in zip(calibrations[name]['epochs'],baseline['calibrations'][name]['epochs'],strict=True)
                         for x,y in zip(e['residuals_m'],b['residuals_m'],strict=True)]
            case['baseline_replay_max_abs_m']=max(differences)
            if max(differences)>1e-7: raise ValueError('regularized baseline changed')
        cases.append(case)
        if progress: progress({k:v for k,v in case.items() if k!='calibrations'})
    sources=actual['sources_sha256'].copy()
    for name in ('solid_earth_study.py','solid_earth_model.py','prepare_solid_earth_inputs.py'):
        sources['research/exploratory/'+name]=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    source_receipt=strict_json(frame.verified.pinned_bytes(BASE/'iers_reference/sources.json','4d3408119d0e34b809fafb2da2a37f963b2d9ecdc464034354729cc3f9359203'))
    for name,record in source_receipt.items():
        frame.verified.pinned_bytes(BASE/'iers_reference'/name,record['sha256'])
        input_hashes['iers_'+name]=record['sha256']
    input_hashes['iers_examples']='e139b4aee46198bc7b74f000794c45e108ec2a11f84761cd154f6c26f2eff468'
    input_hashes['iers_source_receipt']='4d3408119d0e34b809fafb2da2a37f963b2d9ecdc464034354729cc3f9359203'
    input_hashes['frequency_tables']=hashlib.sha256(tide.TABLE_PATH.read_bytes()).hexdigest()
    input_hashes['regularized_report']=FRAME_PINS[tag]
    return {'schema':'solid-earth-study-v1','target_excluded':context.target,'date_gpst':context.date_gpst,
            'iers_example_comparisons':benchmark_comparisons(),
            'fit_stations':admitted['fit_stations'],'case_count':len(cases),'cases':cases,
            'status_counts':dict(Counter(c['status'] for c in cases)),
            'observed_path_count':actual['observed_path_count'],'omitted_paths':actual['omitted_paths'],
            'times_gpst_s':list(context.times),'station_displacements_ecef_m':offsets,
            'input_sha256':actual['input_sha256']|input_hashes,'sources_sha256':sources,
            'model':'IERS-derived DEHANTTIDEINEL step 1+2, permanent tide retained; evaluated at regularized ARP; displacement added to ECEF',
            'unmodelled':['pole tide','ocean tidal loading','atmospheric loading','seasonal station motion','receiver code antenna response','physical covariance'],
            'ephemeris_limit':'DE440s geometric Sun/Moon, IAU2000A ITRS, observed Bulletin A EOP; dX/dY omitted; not the CODE internal ephemeris',
            'target_fit_performed':False,'target_orbit_accessed':False,'new_confirmation':False,
            'instantaneous_site_position_qualified':False,'qualified_error_budget':False,'applied_to_production_estimator':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tag',choices=('g14','g12'));p.add_argument('output',type=Path)
    a=p.parse_args(); result=run(a.tag,lambda x:print(json.dumps(x),flush=True))
    with a.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
