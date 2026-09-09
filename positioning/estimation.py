"""Offline data-to-freeze pipeline; receives no held-out target or orbit."""
import json
from pathlib import Path
import sys
import numpy as np

from .context import Context
from .errors import ScientificRejection
from .network import effective_plan
from .acquisition import digest, write_json, source_hashes, snapshot_sources, utc_now
from .calibration import C, OMEGA, rotate_z, parse_reference_navigation, calibrate_station, reference_model
from .solver import interpolate_event, measurement_model, model_jacobian, solve, uncertainty_box, heldout_prediction, far_field_cost, CHI95


def native(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k:native(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [native(v) for v in value]
    return value


def reference_gradient(observations, calibration, station, navigation, context):
    gradients=[]
    for obs,epoch in zip(observations,calibration['epochs']):
        derivatives=[]
        for sv in epoch['references']:
            record=min(navigation[sv],key=lambda r:abs(obs['time_s']-(r.toc_gps-context.day).total_seconds()))
            p=obs['if_code_m'][sv]
            derivatives.append([-(reference_model(record,p,obs['time_s'],station+dx,epoch['clock_m'],context)[0]-reference_model(record,p,obs['time_s'],station-dx,epoch['clock_m'],context)[0])/2 for dx in np.eye(3)])
        gradients.append(np.mean(derivatives,axis=0))
    return np.array(gradients)


def estimate(run_path):
    run=Path(run_path)
    if (run/'solution_freeze.json').exists():
        raise ValueError('solution already frozen; cannot estimate again')
    if (run/'outcome.json').exists():
        return json.loads((run/'outcome.json').read_text())
    plan=json.loads((run/'plan.json').read_text())
    if digest(run/'plan.json')!=json.loads((run/'plan_freeze.json').read_text())['plan_sha256']:
        raise ValueError('plan hash mismatch')
    receipt=json.loads((run/'admission_receipt.json').read_text())
    admitted_path=run/'estimation/admitted.json'
    nav_path=run/'estimation/reference_only.rnx'
    if digest(admitted_path)!=receipt['admitted_sha256'] or digest(nav_path)!=receipt['navigation_sha256']:
        raise ValueError('admitted input hash mismatch')
    admitted=json.loads(admitted_path.read_text())
    if admitted['plan_sha256']!=digest(run/'plan.json'):
        raise ValueError('admission was produced for another plan')
    context=Context(**admitted['context'])
    if context.target!=plan['target'] or context.date_gpst!=plan['date_gpst']:
        raise ValueError('admitted context does not match frozen target/date')
    structure=json.loads((run/'structure.json').read_text())
    if 'network' in plan:
        if digest(run/'structure.json') != json.loads((run/'availability.json').read_text())['structure_sha256']:
            raise ValueError('network structure changed after availability')
        plan=effective_plan(plan,structure)
    support=structure['selection']['selected_seconds_gpst']
    if support is None or len(support)!=plan['selection']['support_epochs']:
        raise ValueError('no support block matching frozen selection')
    offset=(len(support)-context.samples)//2
    if tuple(float(v) for v in support[offset:offset+context.samples])!=context.times:
        raise ValueError('admitted window differs from central frozen support')
    names=plan['fit_stations']+[plan['withheld_station']]
    if admitted['fit_stations']!=plan['fit_stations'] or admitted['withheld_station']!=plan['withheld_station'] or set(admitted['stations'])!=set(names):
        raise ValueError('admitted receiver roles changed')
    if admitted['stations'][names[-1]]['target_if_codes_m'] is not None:
        raise ValueError('held-out target values cannot enter estimation')
    navigation=parse_reference_navigation(nav_path.read_text(),context.target)
    snapshot_sources(run, 'estimation')
    calibration={}
    for name in names:
        data=admitted['stations'][name]
        cal=calibrate_station(data['reference_observations'],np.array(data['antenna_ecef_m']),navigation,context)
        calibration[name]=cal
        print(json.dumps({'station':name,'status':cal['status'],'failures':cal['failures']}),flush=True)
    write_json(run/'calibration.json',calibration)
    if any(cal['status']!='CALIBRATION_QUALIFIED' for cal in calibration.values()):
        outcome={'status':'CALIBRATION_NOT_QUALIFIED','primary_pass':False,'oracle_accessed':False,'calibration_sha256':digest(run/'calibration.json')}
        write_json(run/'outcome.json',outcome,exclusive=True)
        return outcome
    n=len(plan['fit_stations']);m=context.samples
    codes=np.array([admitted['stations'][k]['target_if_codes_m'] for k in names[:n]])
    clocks=np.array([[e['clock_m'] for e in calibration[k]['epochs']] for k in names[:n]])
    positions=np.array([admitted['stations'][k]['antenna_ecef_m'] for k in names[:n]])
    gradients=[reference_gradient(admitted['stations'][k]['reference_observations'],calibration[k],np.array(admitted['stations'][k]['antenna_ecef_m']),navigation,context) for k in names]
    local_times=np.array(context.times)-context.central_s
    event=interpolate_event(codes,clocks,positions,times_s=local_times)
    control=interpolate_event(codes,clocks,positions,u0=event['u0'],degree=5,times_s=local_times)
    interpolation_difference=abs(event['z']-control['z'])
    if interpolation_difference.max()>2:
        outcome={'status':'SOURCE_OR_MEASUREMENT_NOT_QUALIFIED','reason':'INTERPOLATION_CONTROL','primary_pass':False,'oracle_accessed':False}
        write_json(run/'outcome.json',outcome,exclusive=True)
        return outcome
    z,stations=event['z'],event['positions']
    floor=float(plan['uncertainty']['code_sigma_floor_m'])
    initial=solve(z,stations,np.eye(n)*floor**2)
    q=initial['q']
    transform_jac=np.zeros((n,n*m))
    for i in range(n):
        for j in range(m):
            delta=np.zeros((n,m));delta[i,j]=1.
            ep=interpolate_event(codes+delta,clocks,positions,times_s=local_times)
            em=interpolate_event(codes-delta,clocks,positions,times_s=local_times)
            rp=ep['z']-measurement_model(q,ep['positions'])
            rm=em['z']-measurement_model(q,em['positions'])
            transform_jac[:,i*m+j]=(rp-rm)/2
    floor=max([floor]+[v for k in names[:n] for e in calibration[k]['epochs'] for v in [e['rms_m'],e['split_clock_m']]])
    cov_code=floor**2*transform_jac@transform_jac.T
    refs=sorted({sv for cal in calibration.values() for e in cal['epochs'] for sv in e['references']})
    common=np.zeros((n+1,len(refs)))
    clock_noise=[];ground_variance=[]
    ground_sigma=plan['uncertainty']['ground_coordinate_sigma_m']
    for i,name in enumerate(names):
        cal=calibration[name]
        weights=event['weights'][i] if i<n else np.eye(m)[m//2]
        for j,e in enumerate(cal['epochs']):
            for sv in e['references']:
                common[i,refs.index(sv)]-=weights[j]/len(e['references'])
        clock_noise.append(max(e['rms_m']**2/len(e['references']) for e in cal['epochs']))
        if i<n:
            gradient=weights@gradients[i]
            unit=(q[:3]-stations[i])/np.linalg.norm(q[:3]-stations[i])
            ground_variance.append(ground_sigma**2*float((unit-gradient)@(unit-gradient)))
    cov_reference=plan['uncertainty']['common_reference_sigma_m']**2*common@common.T
    covariance_z=cov_code+cov_reference[:n,:n]+np.diag(np.array(clock_noise[:n])+ground_variance)
    best=solve(z,stations,covariance_z)
    if best['ambiguous'] or np.max(abs(best['residuals']))>100:
        raise ScientificRejection('ambiguous or inadmissible target fit')
    far_cost=far_field_cost(z,stations,covariance_z,best['q'])
    if far_cost-best['cost']<=CHI95:
        raise ScientificRejection('infinite-range alternative inside confidence region')
    bias=plan['uncertainty']['per_root_systematic_envelope_m']
    uncertainty=uncertainty_box(z,stations,covariance_z,best,bias_m=bias,interior_samples=64,seed=2026250,margin=plan['uncertainty']['nonlinear_margin_factor'])
    gold_station=np.array(admitted['stations'][names[-1]]['antenna_ecef_m'])
    predicted,predicted_variance=heldout_prediction(best['q'],gold_station,best['covariance'])
    rotated=rotate_z(gold_station,OMEGA*predicted/C)
    gold_h=model_jacobian(best['q'],rotated[None,:])[0]
    h=model_jacobian(best['q'],stations)
    gain=best['covariance']@h.T@np.linalg.inv(covariance_z)
    unit=(best['q'][:3]-rotated)/np.linalg.norm(best['q'][:3]-rotated)
    gradient=gradients[-1][m//2]
    gold_var=plan['uncertainty']['code_sigma_floor_m']**2+cov_reference[n,n]+clock_noise[n]+ground_sigma**2*float((unit-gradient)@(unit-gradient))
    cross=float(gold_h@gain@cov_reference[:n,n])
    gold_sigma=float(np.sqrt(predicted_variance+gold_var-2*cross))
    gold_systematic=bias+max(abs(heldout_prediction(best['q']+np.array(probe['delta_q']),gold_station,best['covariance'])[0]-predicted) for probe in uncertainty['bias_probes'])
    status='PRE_ORACLE_CRITERIA_MET' if uncertainty['total_95_outer_radius_m']<=plan['confirmation']['uncertainty_radius_limit_m'] else 'UNCERTAINTY_TOO_LARGE'
    inputs=[run/'plan.json',run/'plan_freeze.json',run/'structure.json',run/'admission_receipt.json',admitted_path,nav_path,run/'calibration.json']
    if (run/'availability.json').exists():
        inputs.append(run/'availability.json')
    solution=native({'experiment':plan['experiment'],'target':context.target,'date_gpst':context.date_gpst,'context':context.__dict__,'status_before_reveal':status,'xyz_m':best['q'][:3],'B_m':best['q'][3],'u0_relative_s':event['u0'],'emission_seconds_since_gpst_midnight':context.central_s+event['u0']+best['q'][3]/C,'frame':'terrestrial axes fixed at u0; rotate to emission axes for comparison','fit':best,'covariance_z':covariance_z,'uncertainty':uncertainty,'uncertainty_scope':'conditional numerical envelope; finite probes do not certify global bounds or population coverage','interpolation_control_m':interpolation_difference,'far_field_chi_squared':far_cost,'effective_code_sigma_m':floor,'gold_prediction':{'corrected_range_like_m':predicted,'predictive_sigma_m':gold_sigma,'systematic_envelope_m':gold_systematic,'band_3sigma_plus_systematic_m':3*gold_sigma+gold_systematic},'source_hashes':source_hashes(),'input_hashes':{p.relative_to(run).as_posix():digest(p) for p in inputs},'target_orbit_accessed':False,'heldout_target_accessed':False,'environment':{'python':sys.version,'numpy':np.__version__}})
    write_json(run/'solution.json',solution,exclusive=True)
    write_json(run/'solution_freeze.json',{'solution_sha256':digest(run/'solution.json'),'freeze_utc':utc_now(),'target_orbit_accessed':False,'heldout_target_accessed':False},exclusive=True)
    return {'status':status,'xyz_m':solution['xyz_m'],'total_95_outer_radius_m':uncertainty['total_95_outer_radius_m'],'solution_sha256':digest(run/'solution.json')}
