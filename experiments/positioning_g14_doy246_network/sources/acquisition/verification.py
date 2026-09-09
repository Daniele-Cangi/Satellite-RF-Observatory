"""Post-freeze receiver/orbit comparison; never calls the positioning fit."""
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import hatanaka

from .context import Context
from .acquisition import digest, write_json, source_hashes, snapshot_sources, download, utc_now
from .calibration import observation_window, rotate_z, OMEGA, C
from .solver import interpolate_event


def compare_oracle(content, target, date_gpst, emission_s, xyz_fixed, B_m):
    times=[];xyz=[];header=[];epoch=None
    expected=[int(v) for v in date_gpst.split('-')]
    for line in content.splitlines():
        if line.startswith('*'):
            fields=line[1:].split()
            if list(map(int,fields[:3]))!=expected:
                raise ValueError('oracle epoch outside declared GPST date')
            epoch=int(fields[3])*3600+int(fields[4])*60+float(fields[5])
        elif line.startswith('P'+target):
            point=np.array([float(line[4+14*j:18+14*j]) for j in range(3)])*1000
            if epoch is None or not np.isfinite(point).all() or np.any(point==0):
                raise ValueError('missing or nonfinite oracle position')
            times.append(epoch);xyz.append(point)
        elif epoch is None:
            header.append(line)
    if not any(l.startswith('%c') and 'GPS' in l for l in header):
        raise ValueError('oracle is not explicitly GPS time')
    times=np.array(times);xyz=np.array(xyz)
    if len(times)<9 or np.any(np.diff(times)<=0) or not times[0]<=emission_s<=times[-1]:
        raise ValueError('oracle does not bracket emitted event with enough nodes')
    def interpolate(n):
        chosen=np.sort(np.argsort(abs(times-emission_s),kind='stable')[:n])
        nodes=(times[chosen]-emission_s)/900.;weights=np.ones(n)
        for i in range(n):
            for j in range(n):
                if i!=j:weights[i]*=-nodes[j]/(nodes[i]-nodes[j])
        return weights@xyz[chosen],times[chosen].tolist()
    oracle,nodes=interpolate(9);control,_=interpolate(8)
    estimate=rotate_z(np.array(xyz_fixed),-OMEGA*B_m/C)
    error=estimate-oracle
    return {'estimated_ecef_at_emission_m':estimate.tolist(),'oracle_ecef_at_emission_m':oracle.tolist(),'error_xyz_m':error.tolist(),'error_3d_m':float(np.linalg.norm(error)),'oracle_interpolation_control_m':float(np.linalg.norm(oracle-control)),'oracle_nodes_gpst_s':nodes,'oracle_header':header}


def verify(run_path):
    run=Path(run_path)
    if (run/'outcome.json').exists():
        return json.loads((run/'outcome.json').read_text())
    if not (run/'solution_freeze.json').exists():
        raise ValueError('oracle access forbidden before solution freeze')
    freeze=json.loads((run/'solution_freeze.json').read_text())
    if digest(run/'solution.json')!=freeze['solution_sha256']:
        raise ValueError('frozen solution changed')
    solution=json.loads((run/'solution.json').read_text())
    if source_hashes()!=solution['source_hashes']:
        raise ValueError('source changed since solution freeze')
    for name,expected in solution['input_hashes'].items():
        if digest(run/name)!=expected:raise ValueError('input changed since freeze: '+name)
    snapshot_sources(run, 'verification')
    plan=json.loads((run/'plan.json').read_text())
    context=Context(**solution['context'])
    if (run/'oracle_access.json').exists() or (run/'oracle_request.json').exists():
        raise ValueError('oracle already accessed without terminal; do not silently retry revealed event')
    gold_path=run/'heldout_reveal.json'
    if not gold_path.exists():
        structure=json.loads((run/'structure.json').read_text())
        name=plan['withheld_station'];info=structure['structures'][name]
        receipt=next(r for r in structure['receipts'] if r['station']==name)
        path=run/'raw_observations'/plan['observation_filename'].format(station=name)
        if digest(path)!=receipt['sha256']:raise ValueError('held-out observation changed')
        obs=observation_window(hatanaka.decompress(path.read_bytes(),strict=True).decode('ascii'),info['header'],info['gps_observation_types'],True,context)
        cal=json.loads((run/'calibration.json').read_text())[name]
        station=json.loads((run/'estimation/admitted.json').read_text())['stations'][name]['antenna_ecef_m']
        codes=np.array([[o['if_code_m'][context.target] for o in obs]])
        clocks=np.array([[e['clock_m'] for e in cal['epochs']]])
        times=np.array(context.times)-context.central_s
        event=interpolate_event(codes,clocks,np.array([station]),u0=solution['u0_relative_s'],times_s=times)
        control=interpolate_event(codes,clocks,np.array([station]),u0=solution['u0_relative_s'],degree=5,times_s=times)
        residual=float(event['z'][0]-solution['gold_prediction']['corrected_range_like_m'])
        interpolation=float(abs(event['z'][0]-control['z'][0]))
        passed=abs(residual)<=plan['confirmation']['holdout_absolute_limit_m'] and abs(residual)<=solution['gold_prediction']['band_3sigma_plus_systematic_m'] and interpolation<=2
        gold={'status':'HELD_OUT_RECEIVER_CONFIRMED' if passed else 'HELD_OUT_RECEIVER_REJECTED','residual_m':residual,'interpolation_control_m':interpolation,'reveal_utc':utc_now(),'solution_sha256':freeze['solution_sha256']}
        write_json(gold_path,gold,exclusive=True)
    else:
        gold=json.loads(gold_path.read_text())
    write_json(run/'oracle_request.json', {'url':plan['oracle_url'],'attempt_utc':utc_now(),
               'solution_sha256':freeze['solution_sha256']}, exclusive=True)
    data,receipt=download(plan['oracle_url'],20_000_000)
    (run/'oracle_after_freeze.SP3.gz').write_bytes(data)
    write_json(run/'oracle_access.json',receipt,exclusive=True)
    comparison=compare_oracle(gzip.decompress(data).decode('ascii'),context.target,context.date_gpst,solution['emission_seconds_since_gpst_midnight'],solution['xyz_m'],solution['B_m'])
    radius=solution['uncertainty']['total_95_outer_radius_m']
    oracle_pass=comparison['error_3d_m']<=plan['confirmation']['position_error_limit_m'] and comparison['error_3d_m']<=radius+10 and comparison['oracle_interpolation_control_m']<=10
    primary=solution['status_before_reveal']=='PRE_ORACLE_CRITERIA_MET' and gold['status']=='HELD_OUT_RECEIVER_CONFIRMED' and oracle_pass
    status='INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED' if primary else solution['status_before_reveal'] if solution['status_before_reveal']!='PRE_ORACLE_CRITERIA_MET' else 'CONFIRMATION_REJECTED'
    outcome={'experiment':plan['experiment'],'status':status,'primary_pass':primary,'comparison':comparison,'heldout':gold,'prospective_uncertainty_radius_m':radius,'solution_sha256':freeze['solution_sha256'],'freeze_utc':freeze['freeze_utc'],'oracle_access':receipt,'claim':plan['claim']}
    write_json(run/'outcome.json',outcome,exclusive=True)
    return outcome
