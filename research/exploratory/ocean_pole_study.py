"""Bounded OTL/pole sensitivity on exposed references; CMC pairing unresolved."""
import argparse
from collections import Counter
from datetime import datetime,timedelta
import hashlib
import json
from pathlib import Path
import numpy as np
from . import solid_earth_study as solid
from . import ocean_pole_model as loading
from .reference_attitude_model import strict_json

BASE=Path(__file__).parent
INPUTS=BASE/'inputs/ocean_loading'
FRAME=solid.frame
PINS={'g14': '4b6c2d55466d0b6d339de1e5e0dd54dcb6e2b76e1edfc2a071461131e46bb6c8', 'g12': 'dc9c31237973776f287a44880a357d79d7bbea152c88632d8fba718c391af905'}
RECEIPT_SHA='166329316b9d5fb69872874de7cad8ab1f89958b299a26a79828456eb1d014ad'
MODES=('solid_earth_baseline','ocean_ce','pole_2018','ocean_ce_plus_pole_2018',
       'ocean_ce_plus_pole_2010_control','ocean_horizontal_sign_control')


def read_loading(tag):
    raw=FRAME.verified.pinned_bytes(INPUTS/'receipt.json',RECEIPT_SHA)
    receipt=strict_json(raw)
    if receipt['schema']!='ocean-loading-products-v1' or receipt['target_states_accessed'] is not False:
        raise ValueError('invalid loading receipt')
    hashes={'loading_receipt':RECEIPT_SHA}
    for name,key in [('prepare_ocean_loading.py','producer_sha256'),('ocean_pole_model.py','model_sha256')]:
        FRAME.verified.pinned_bytes(BASE/name,receipt[key])
    manifest=strict_json(FRAME.verified.pinned_bytes(BASE/'loading_reference/sources.json',receipt['source_receipt_sha256']))
    if {name:item['sha256'] for name,item in manifest.items()}!=receipt['build']['sources']:
        raise ValueError('HARDISP build sources differ')
    for name,item in manifest.items():FRAME.verified.pinned_bytes(BASE/'loading_reference'/name,item['sha256'])
    br=strict_json(FRAME.verified.pinned_bytes(INPUTS/'blq_receipt.json',receipt['blq_receipt_sha256']))
    stations,bound=loading.parse_blq(FRAME.verified.pinned_bytes(INPUTS/'fit_stations.BLQ',br['extract_sha256']).decode('ascii'))
    FRAME.verified.pinned_bytes(INPUTS/'hardisp_examples.json',receipt['examples_sha256'])
    products=strict_json(FRAME.verified.pinned_bytes(INPUTS/'hardisp_products.json',receipt['products_sha256']))
    if products['schema']!='hardisp-fit-products-v1' or products['cmc_applied'] is not False or products['target_states_accessed'] is not False:
        raise ValueError('invalid HARDISP convention')
    if len(products['benchmarks'])!=2 or not all(b['qualified_2_um'] for b in products['benchmarks']):
        raise ValueError('unqualified HARDISP benchmarks')
    if products['cmc_header_phase_free_norm_bound_m']!=bound:raise ValueError('CMC header differs')
    hashes.update({key:receipt[key] for key in ('source_receipt_sha256','blq_receipt_sha256','examples_sha256','products_sha256')})
    hashes['fit_stations_blq']=br['extract_sha256']
    return products,stations,hashes,receipt


def station_variants(regularized,solid_offsets,times,samples,usw):
    positions=np.array(regularized)
    if np.shape(usw)!=(len(times),3) or not np.all(np.isfinite(usw)):raise ValueError('invalid ocean time series')
    ocean=np.array([loading.ocean_ecef(v,x) for v,x in zip(usw,positions,strict=True)])
    wrong=np.array([loading.ocean_ecef([v[0],-v[1],-v[2]],x) for v,x in zip(usw,positions,strict=True)])
    poles={}
    for convention in ('2018','2010'):
        poles[convention]=np.array([loading.pole_ecef(x,datetime.fromisoformat(samples[t]['utc']),
                                   samples[t]['xp_arcsec'],samples[t]['yp_arcsec'],convention)
                                   for x,t in zip(positions,times,strict=True)])
    additions={'solid_earth_baseline':np.zeros_like(ocean),'ocean_ce':ocean,'pole_2018':poles['2018'],
               'ocean_ce_plus_pole_2018':ocean+poles['2018'],
               'ocean_ce_plus_pole_2010_control':ocean+poles['2010'],
               'ocean_horizontal_sign_control':wrong+poles['2018']}
    base=positions+np.array(solid_offsets)
    return {mode:base+d for mode,d in additions.items()}, {mode:d.tolist() for mode,d in additions.items()}


def run(tag,progress=None):
    products,blq,input_hashes,receipt=read_loading(tag)
    saved=strict_json(FRAME.verified.pinned_bytes(BASE/f'results/{tag}_solid_earth_v1.json',PINS[tag]))
    for path,digest in saved['sources_sha256'].items():FRAME.verified.pinned_bytes(FRAME.ROOT/path,digest)
    actual=solid.run(tag)
    solid.compare_replay(actual,saved)
    frame_report=strict_json(FRAME.verified.pinned_bytes(BASE/f'results/{tag}_station_frame_epoch_v1.json',solid.FRAME_PINS[tag]))
    admitted,context,_,archive_hashes=FRAME.verified.load_inputs(FRAME.verified.paths(tag)['admission_receipt'].parent)
    samples,_=solid.celestial_inputs(tag)
    event=products['events'][tag]
    if event['date_gpst']!=context.date_gpst or event['times_gpst_s']!=list(context.times) or set(event['ocean_usw_m'])!={n[:4] for n in admitted['fit_stations']}:
        raise ValueError('loading event grid or station set differs')
    expected=datetime.fromisoformat(context.date_gpst)+timedelta(seconds=context.times[0]-18)
    if event['start_utc']!=expected.isoformat():raise ValueError('loading UTC differs')
    rr=strict_json(FRAME.verified.pinned_bytes(FRAME.verified.paths(tag)['reference_report'],FRAME.verified.PINS[tag]['reference_report']))
    prior=strict_json(FRAME.verified.pinned_bytes(FRAME.verified.paths(tag)['attitude_report'],FRAME.verified.PINS[tag]['attitude_report']))
    precise,corrections,ph=FRAME.guarded_products(context,rr['references'],FRAME.verified.INPUTS/f'timed_reference_products/{tag}',
                      FRAME.verified.INPUTS/f'reference_biases/{tag}',FRAME.verified.INPUTS/f'reference_antennas/{tag}')
    attitude,ah=FRAME.load_attitude(FRAME.verified.INPUTS/f'reference_attitudes/{tag}',context,rr['references'])
    if archive_hashes|ph|ah!=prior['input_sha256']:raise ValueError('paired reference products differ')
    provider=FRAME.AttitudeReference(precise,attitude)
    baseline=next(c for c in actual['cases'] if c['mode']=='solid_earth')
    variants,offsets,identities={},{},[]
    for station in frame_report['station_models']:
        name=station['station'];xyz=station['positions']['final_transport'];local=blq[name[:4]]
        distance=loading.geographic_distance(xyz[0],local)
        if distance>10000:raise ValueError('BLQ geographic association exceeds 10 km: '+name)
        identities.append({'station':name,'domes':station['domes'],'blq_short_name':name[:4],
                           'blq_lon_lat_height':local['lon_lat_height'],'horizontal_separation_m':distance,
                           'association':'approximate geographic site, not a DOMES-labelled BLQ monument'})
        variants[name],offsets[name]=station_variants(xyz,actual['station_displacements_ecef_m'][name]['solid_earth'],
                                                     context.times,samples,event['ocean_usw_m'][name[:4]])
    cases=[]
    for mode in MODES:
        calibrations={}
        for name in admitted['fit_stations']:
            try:
                positions=variants[name][mode];base=positions[0]
                delta={t:p-base for t,p in zip(context.times,positions,strict=True)}
                fixed={e['time_s']:e['references'] for e in baseline['calibrations'][name]['epochs']}
                obs=FRAME.translate_observations(admitted['stations'][name]['reference_observations'],corrections,context.target)
                def model(sv,code,t,station,clock):return provider.model(sv,code,t,station+delta[t],clock)
                cal=FRAME.calibrate_fixed(obs,base,context,fixed,model)
                if cal['status']=='CALIBRATION_QUALIFIED':
                    cal['clock_change_m']=[e['clock_m']-b['clock_m'] for e,b in zip(cal['epochs'],baseline['calibrations'][name]['epochs'],strict=True)]
                calibrations[name]=cal
            except Exception as error:
                calibrations[name]={'status':'ENGINEERING_FAILURE','reason':type(error).__name__+': '+str(error),'epochs':[]}
        residuals=[v for cal in calibrations.values() for e in cal['epochs'] for v in e['residuals_m']]
        complete=all(c['status']=='CALIBRATION_QUALIFIED' for c in calibrations.values())
        case={'mode':mode,'status':'CALIBRATION_QUALIFIED' if complete else 'CALIBRATION_NOT_QUALIFIED','calibrations':calibrations,
              'evaluated_path_count':len(residuals),'pooled_reference_rms_m':float(np.sqrt(np.mean(np.square(residuals)))) if complete else None}
        if mode=='solid_earth_baseline' and complete:
            d=[abs(x-y) for name in admitted['fit_stations'] for e,b in zip(calibrations[name]['epochs'],baseline['calibrations'][name]['epochs'],strict=True)
               for x,y in zip(e['residuals_m'],b['residuals_m'],strict=True)]
            case['baseline_replay_max_abs_m']=max(d)
            if max(d)>1e-7:raise ValueError('solid Earth baseline changed')
        cases.append(case)
        if progress:progress({k:v for k,v in case.items() if k!='calibrations'})
    sources=actual['sources_sha256'].copy()
    for name in ('ocean_pole_study.py','ocean_pole_model.py','prepare_ocean_loading.py'):
        sources['research/exploratory/'+name]=hashlib.sha256((BASE/name).read_bytes()).hexdigest()
    for name,h in receipt['build']['sources'].items():sources['research/exploratory/loading_reference/'+name]=h
    return {'schema':'ocean-pole-study-v1','target_excluded':context.target,'date_gpst':context.date_gpst,
            'fit_stations':admitted['fit_stations'],'case_count':len(cases),'cases':cases,
            'status_counts':dict(Counter(c['status'] for c in cases)),
            'observed_path_count':actual['observed_path_count'],'omitted_paths':actual['omitted_paths'],
            'times_gpst_s':list(context.times),'station_additional_displacements_ecef_m':offsets,'station_associations':identities,
            'hardisp_benchmarks':products['benchmarks'],'cmc_phase_free_norm_bound_m':products['cmc_header_phase_free_norm_bound_m'],
            'input_sha256':actual['input_sha256']|input_hashes|{'solid_earth_report':PINS[tag]},'sources_sha256':sources,
            'model':'FES2014b HARDISP 342 harmonics CMC:NO + solid pole tide IERS 2018; 2010 pole control',
            'cmc_applied':False,'code_loading_frame_alignment_qualified':False,
            'unresolved':['CMC consistency with paired terrestrial SP3','actual CODE pole convention and EOP realization',
                          'ocean pole tide','atmospheric loading','seasonal motion','receiver code response','physical covariance'],
            'target_fit_performed':False,'target_orbit_accessed':False,'new_confirmation':False,
            'instantaneous_site_position_qualified':False,'qualified_error_budget':False,'applied_to_production_estimator':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tag',choices=('g14','g12'));p.add_argument('output',type=Path)
    a=p.parse_args();result=run(a.tag,lambda x:print(json.dumps(x),flush=True))
    with a.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
