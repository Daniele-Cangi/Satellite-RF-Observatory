"""Conditional polar-motion sensitivity, not a full CODE EOP reconstruction.
Bound all DESAI2016 phases instead of choosing an unvalidated phase convention.
Only daily polar offsets/rates are propagated; UT1/LOD and orbit rotations are not.
"""
import argparse
from datetime import datetime,timedelta
import hashlib
import json
import math
from pathlib import Path
import numpy as np

BASE=Path(__file__).parent
RECEIPT_SHA='9277ba942e8b57f99fa431f227c8e77ecf6675a98f0eb8902456390072023c15'
POLE_OPERATOR_M_PER_ARCSEC=.033


def strict_json(raw):
    def pairs(items):
        result={}
        for k,v in items:
            if k in result:raise ValueError('duplicate JSON key')
            result[k]=v
        return result
    def bad(value):raise ValueError('nonfinite JSON')
    def finite(value):
        x=float(value)
        if not math.isfinite(x):raise ValueError('nonfinite JSON')
        return x
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=bad,parse_float=finite)


def pinned(path,digest):
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('input hash differs: '+str(path))
    return raw


def parse_desai(raw):
    lines=raw.decode('utf-8').splitlines()
    if 'FORMAT VERSION: 2' not in lines or 'SUBDAILY ERP MODEL NAME: DESAI2016' not in lines:
        raise ValueError('DESAI2016 format required')
    unit=[s for s in lines if '(0.001 MAS)' in s]
    if len(unit)!=1 or unit[0].count('(0.001 MAS)')!=2 or '(0.001 MS)' not in unit[0]:raise ValueError('harmonic units differ')
    headers=[i for i,s in enumerate(lines) if 'XCOS' in s]
    if len(headers)!=1 or lines[headers[0]].split()!=['L',"L'",'F','D','O','T','XCOS','XSIN','YCOS','YSIN','UTCOS','UTSIN']:
        raise ValueError('harmonic columns differ')
    rows=[];keys=set()
    for line in lines[headers[0]+1:]:
        if not line.strip():continue
        fields=line.split()
        if len(fields)!=13:raise ValueError('invalid harmonic row')
        key=tuple(int(x) for x in fields[:6]);values=np.array([float(x) for x in fields[6:]])
        if key in keys or not np.all(np.isfinite(values)) or not .4<values[0]<1.4:
            raise ValueError('duplicate or invalid harmonic')
        keys.add(key);rows.append(values[1:5].reshape(2,2))
    if len(rows)!=159:raise ValueError('all 159 harmonics required')
    return np.array(rows)*1e-6  # microarcseconds -> arcseconds, no time units here


def phase_bound(matrices):
    a=np.asarray(matrices,dtype=float)
    if a.ndim!=3 or a.shape[1:]!=(2,2) or len(a)==0 or not np.all(np.isfinite(a)):
        raise ValueError('finite harmonic matrices required')
    # [dx,dy] = A_k [cos(phi_k),sin(phi_k)]; ||sum|| <= sum ||A_k||_2.
    return float(np.sum(np.linalg.svd(a,compute_uv=False)[:,0]))


def parse_erp(raw,date):
    lines=raw.decode('ascii').splitlines();expected=datetime.fromisoformat(date)
    if len(lines)!=7 or lines[0].strip()!='VERSION 2':raise ValueError('one daily ERP record required')
    if not lines[1].startswith(f'CODE RAPID GNSS ERP INFORMATION FOR (MIDDLE) DAY {expected.timetuple().tm_yday}, {expected.year} '):
        raise ValueError('ERP family/date differs')
    if 'SUBDAILY POLE MODEL: DESAI2016' not in lines[3]:raise ValueError('ERP subdaily model differs')
    if lines[4].split()[:14]!=['MJD','X-P','Y-P','UT1UTC','LOD','S-X','S-Y','S-UT','S-LD','NR','NF','NT','X-RT','Y-RT']:
        raise ValueError('ERP columns differ')
    units=lines[5].split()
    if units[:2]!=['E-6"','E-6"'] or units[8:10]!=['E-6"/D','E-6"/D']:raise ValueError('ERP polar units differ')
    row=np.array([float(x) for x in lines[6].split()])
    if len(row)!=23 or not np.all(np.isfinite(row)):raise ValueError('ERP row invalid')
    mjd=(expected-datetime(1858,11,17)).days+.5
    if row[0]!=mjd:raise ValueError('ERP epoch differs')
    return {'date':date,'epoch_mjd_utc':mjd,'pole_arcsec':(row[1:3]*1e-6).tolist(),
            'rate_arcsec_per_day':(row[12:14]*1e-6).tolist()}


def daily_pole(erp,utc):
    start=datetime.fromisoformat(erp['date'])
    if utc.tzinfo is not None or not start<=utc<start+timedelta(days=1):raise ValueError('within-day naive UTC required')
    dt=(utc-start).total_seconds()/86400-.5
    return np.array(erp['pole_arcsec'])+dt*np.array(erp['rate_arcsec_per_day'])


def run():
    receipt=strict_json(pinned(BASE/'inputs/erp_polar/receipt.json',RECEIPT_SHA))
    source=receipt['desai_source']
    raw=pinned(BASE/'inputs/erp_polar/DESAI2016.SUB',source['sha256'])
    matrices=parse_desai(raw);bound=phase_bound(matrices)
    buffers={name:pinned(BASE/name,h) for name,h in receipt['local_sha256'].items()}
    prior=strict_json(buffers['inputs/solid_earth/sun_moon.json'])
    events=[]
    for tag,day,start in [('g14','2026-09-03',14100),('g12','2026-09-05',37800)]:
        erp=parse_erp(buffers[f'inputs/code_conventions/{tag}.erp'],day)
        event=prior[tag]
        if event['date_gpst']!=day:raise ValueError('prior day differs')
        by_time={s['time_gpst_s']:s for s in event['samples']}
        if len(by_time)!=len(event['samples']):raise ValueError('duplicate prior epoch')
        samples=[]
        for t in range(start,start+301,30):
            previous=by_time[t];utc=datetime.fromisoformat(day)+timedelta(seconds=t-18)
            if previous['utc']!=utc.isoformat():raise ValueError('GPST/UTC differs')
            daily=daily_pole(erp,utc);old=np.array([previous['xp_arcsec'],previous['yp_arcsec']])
            difference=float(np.linalg.norm(daily-old))
            samples.append({'gpst_s':t,'utc':utc.isoformat(),'code_daily_linear_pole_arcsec':daily.tolist(),
                            'previous_bulletin_a_pole_arcsec':old.tolist(),'daily_difference_norm_arcsec':difference,
                            'same_mean_pole_displacement_upper_m':POLE_OPERATOR_M_PER_ARCSEC*(difference+bound)})
        events.append({'event':tag,'erp':erp,'samples':samples,
                       'max_same_mean_pole_displacement_upper_m':max(s['same_mean_pole_displacement_upper_m'] for s in samples)})
    return {'schema':'erp-polar-bound-v1','events':events,'desai_harmonic_count':len(matrices),
            'desai_phase_free_polar_norm_upper_arcsec':bound,
            'desai_solid_pole_displacement_upper_m':POLE_OPERATOR_M_PER_ARCSEC*bound,
            'pole_operator_norm_upper_m_per_arcsec':POLE_OPERATOR_M_PER_ARCSEC,
            'input_sha256':receipt['local_sha256']|{'inputs/erp_polar/receipt.json':RECEIPT_SHA,'inputs/erp_polar/DESAI2016.SUB':source['sha256']},
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'conditional_on':['published DESAI2016 coefficient model','daily offset/rate linear model within its day',
                              'same secular/mean pole convention','IERS solid pole displacement equations'],
            'not_bounded':['actual Earth orientation error','different mean pole conventions','ocean pole tide',
                           'other subdaily terms','UT1 and celestial body rotation','total station motion','inverse satellite position error'],
            'desai_phases_reconstructed':False,'instantaneous_code_eop_qualified':False,
            'sp3_rotated_again':False,'target_states_accessed':False,'new_rf_accessed':False,
            'calibration_repeated':False,'new_confirmation':False,'production_changed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path)
    a=p.parse_args();result=run()
    with a.output.open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
