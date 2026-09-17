"""Reference calibration -> corrected code -> local synthetic position/motion."""
from pathlib import Path
import hashlib
import numpy as np

from .erp_polar_bound import pinned, strict_json
from .reference_residual_structure_v2 import center_blocks, design, groups
from ..kinematic.receiver_time import predict, central_jacobian

BASE = Path(__file__).parent
SCALE = np.r_[[1e7]*3,[1e3]*3,[1.]*3,1e5,10.]


def inputs(plan_sha):
    plan = strict_json(pinned(BASE/'position_error_plan.json',plan_sha))
    report = strict_json(pinned(BASE/'results/day_reference_v1.json',plan['reference_report_sha256']))
    positions = strict_json(pinned(BASE/'inputs/day_reference/positions.json',plan['station_positions_sha256']))
    names = report['plan']['stations']
    training = [r for r in report['rows'] if r['time_s']<plan['training_before_gpst_s']]
    testing = [r for r in report['rows'] if r['time_s'] in plan['evaluation_times_gpst_s']]
    blocks = [(s,t) for t in plan['evaluation_times_gpst_s'] for s in names]
    if set(groups(testing)) != set(blocks) or any(len(ix)<4 for ix in groups(testing).values()):
        raise ValueError('incomplete declared reference geometry')
    if any(r['reference']==report['plan']['target_excluded'] for r in training+testing):
        raise ValueError('excluded target in reference incidence')
    return plan,names,training,testing,blocks,np.array([positions[s][65] for s in names])


def calibration_map(training,testing,blocks,model):
    """Raw order: synthetic target codes, test reference errors, train errors.

    d = e_target - K_test e_test + mean(test features) C_other_train e_train.
    C is centered training least squares; each test receiver is excluded.
    """
    m,n,k = len(blocks),len(testing),len(training)
    mapping = np.zeros((m,m+n+k))
    mapping[:,:m] = np.eye(m)
    test_groups = groups(testing)
    metadata = []
    for i,block in enumerate(blocks):
        mapping[i,m+np.array(test_groups[block])] = -1/len(test_groups[block])
    if model=='zero':
        return mapping,metadata
    if model!='shared_satellite':
        raise ValueError('unknown correction model')
    for station in sorted({s for s,t in blocks}):
        indices = [i for i,r in enumerate(training) if r['station']!=station]
        rows = [training[i] for i in indices]
        columns = sorted({r['reference'] for r in rows})
        x,missing = design(rows,'shared_satellite',columns)
        u,s,vh = np.linalg.svd(x,full_matrices=False)
        rank = int(np.sum(s>s[0]*1e-12))
        basis = vh[:rank]
        coefficient_gain = (basis.T/s[:rank])@u[:,:rank].T
        # Explicitly center raw-error columns, not just observed residuals.
        coefficient_gain = center_blocks(coefficient_gain.T,rows).T
        station_test = [r for r in testing if r['station']==station]
        tx,unseen = design(station_test,'shared_satellite',columns)
        defect = np.linalg.norm(tx-(tx@basis.T)@basis,axis=1)
        if missing.any() or unseen.any() or np.any(defect>1e-9*np.maximum(1.,np.linalg.norm(tx,axis=1))):
            raise ValueError('unsupported shared prediction; no subset rescue')
        for i,block in enumerate(blocks):
            if block[0]!=station:
                continue
            refs = [testing[j]['reference'] for j in test_groups[block]]
            feature_mean = np.array([refs.count(sv)/len(refs) for sv in columns])
            mapping[i,m+n+np.array(indices)] = feature_mean@coefficient_gain
        metadata.append({'excluded_station':station,'training_count':len(rows),'rank':rank,
                         'reference_count':len(columns),'coefficient_gauge':'minimum Euclidean norm'})
    return mapping,metadata


def error_covariances(mapping,training,testing,blocks):
    """Declared additive unit scenarios. None is estimated from measured RMS."""
    m = len(blocks)
    names = sorted({s for s,t in blocks})
    refs = sorted({r['reference'] for r in training+testing})
    raw = [{'station':s,'time_s':t,'reference':None} for s,t in blocks]+testing+training
    n = len(raw)
    station = np.zeros((n,len(names)))
    satellite = np.zeros((n,len(refs)))
    matched = np.zeros_like(station)
    ramp = np.zeros_like(station)
    for i,row in enumerate(raw):
        j = names.index(row['station'])
        matched[i,j]=1
        if i>=m:
            station[i,j]=1
            ramp[i,j]=(row['time_s']-37950)/300
            satellite[i,refs.index(row['reference'])]=1
    factors = {'reference_station_offset_1m':station,'reference_station_ramp_1m_per_300s':ramp,
               'reference_satellite_offset_1m':satellite,'matched_station_offset_1m':matched}
    result = {'independent_raw_1m':{'code_covariance_m2':mapping@mapping.T,'reference_contrast_response_max':None}}
    for name,factor in factors.items():
        response = mapping@factor
        blind = max(float(np.abs(center_blocks(factor[m:m+len(testing)],testing)).max()),
                    float(np.abs(center_blocks(factor[m+len(testing):],training)).max()))
        result[name]={'code_covariance_m2':response@response.T,'reference_contrast_response_max':blind}
    # Common to all references at each station/epoch; independent stations,
    # exponential 60-second covariance in time. Target carries no matched mode.
    keys = sorted({(r['station'],r['time_s']) for r in testing+training})
    summed = np.zeros((m,len(keys)))
    index = {key:i for i,key in enumerate(keys)}
    for i,row in enumerate(raw[m:],m):
        summed[:,index[(row['station'],row['time_s'])]] += mapping[:,i]
    cov = np.array([[np.exp(-abs(t-u)/60) if s==r else 0. for r,u in keys] for s,t in keys])
    result['reference_station_temporal_1m_tau60s'] = {'code_covariance_m2':summed@cov@summed.T,
                                                    'reference_contrast_response_max':0.}
    return result


def geometry(stations,radius,speed,plan):
    direction = (stations/np.linalg.norm(stations,axis=1)[:,None]).mean(axis=0)
    direction /= np.linalg.norm(direction)
    tangent = np.cross([0.,0.,1.],direction); tangent /= np.linalg.norm(tangent)
    state = np.r_[radius*direction,speed*tangent,-plan['synthetic_inward_acceleration_m_s2']*direction,0.,0.]
    tags = np.array(plan['evaluation_times_gpst_s'])-37950
    def model(q):
        return predict(q,tags,stations,np.zeros((len(stations),2)))['code_m'].ravel()
    points = state[:3]+tags[:,None]*state[3:6]+.5*tags[:,None]**2*state[6:9]
    delta = points[:,None,:]-stations[None,:,:]
    up = stations/np.linalg.norm(stations,axis=1)[:,None]
    elevation = float(np.degrees(np.arcsin(np.clip(np.sum(delta/np.linalg.norm(delta,axis=2)[...,None]*up,axis=2),-1,1))).min())
    if elevation<plan['minimum_joint_elevation_deg']:
        return {'status':'BELOW_SYNTHETIC_MASK','minimum_elevation_deg':elevation},None,None,None
    h = central_jacobian(lambda z:model(z*SCALE),state/SCALE)/SCALE
    u,s,vh = np.linalg.svd(h*SCALE/plan['weight_code_sigma_m'],full_matrices=False)
    rank = int(np.sum(s>s[0]/plan['maximum_scaled_condition']))
    meta = {'minimum_elevation_deg':elevation,'rank':rank,'scaled_condition':float(s[0]/s[-1]),
            'synthetic_state':state.tolist()}
    if rank!=11:
        return meta|{'status':'RANK_NOT_QUALIFIED'},None,None,None
    gain = (SCALE[:,None]*((vh.T/s)@u.T))/plan['weight_code_sigma_m']
    return meta|{'status':'LOCAL_LINEAR_RESPONSE'},gain,h,(state,model)


def metrics(cov,offsets):
    result = {}
    for t in offsets:
        p = np.zeros((3,11)); p[:,:3]=np.eye(3); p[:,3:6]=t*np.eye(3); p[:,6:9]=.5*t*t*np.eye(3)
        c = p@cov@p.T
        result['position_t_plus_'+str(t)+'_m'] = float(np.sqrt(max(0.,np.linalg.eigvalsh((c+c.T)/2)[-1])))
    c = cov[3:6,3:6]
    result['velocity_t0_m_s'] = float(np.sqrt(max(0.,np.linalg.eigvalsh((c+c.T)/2)[-1])))
    return result


def run(plan_sha,progress=None):
    plan,names,train,test,blocks,stations = inputs(plan_sha)
    operators = {}
    for model in plan['models']:
        mapping,meta = calibration_map(train,test,blocks,model)
        operators[model] = (error_covariances(mapping,train,test,blocks),meta)
    cases = []
    for radius in plan['synthetic_geocentric_radii_m']:
        for speed in plan['synthetic_tangent_speeds_m_s']:
            meta,gain,h,nonlinear = geometry(stations,radius,speed,plan)
            row = {'radius_m':radius,'speed_m_s':speed,**meta,'models':{}}
            if gain is not None:
                baseline = plan['weight_code_sigma_m']**2*gain@gain.T
                row['independent_20m_control'] = metrics(baseline,plan['future_position_offsets_s'])
                state,model_fn = nonlinear
                # A small local numerical check, not a global nonlinear bound.
                perturb = .001*gain[:,0]
                row['local_code_linearization_remainder_max_m'] = float(np.abs(model_fn(state+perturb)-model_fn(state)-h@perturb).max())
                for name,(scenarios,_) in operators.items():
                    row['models'][name] = {}
                    for scenario in plan['error_scenarios']:
                        cov = scenarios[scenario]['code_covariance_m2']
                        transported = gain@cov@gain.T
                        row['models'][name][scenario] = {
                            'reference_contrast_response_max':scenarios[scenario]['reference_contrast_response_max'],
                            'unit_mode_principal_std':metrics(transported,plan['future_position_offsets_s']),
                            'control_plus_independent_mode_principal_std':metrics(baseline+transported,plan['future_position_offsets_s'])}
            cases.append(row)
            if progress:
                progress({'radius_m':radius,'speed_m_s':speed,'status':row['status']})
    return {'schema':'position-error-transfer-v1','plan':plan,'plan_sha256':plan_sha,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'stations':names,'training_reference_paths':len(train),'test_reference_paths':len(test),
            'synthetic_code_count':len(blocks),'calibration_operator_metadata':{k:v[1] for k,v in operators.items()},
            'cases':cases,'real_target_fit':False,'target_orbit_accessed':False,'physical_covariance_qualified':False,
            'real_uncertainty_floors_modified':False,'scope':'Conditional local synthetic sensitivity. Principal standard deviations under invented covariances, not physical error bounds or 95-percent coverage.'}
