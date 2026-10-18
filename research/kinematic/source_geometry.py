"""Source-restricted reference information and joint calibration/state response.

One zenith wet residual per station is constant over the window. Geometry
comes from admitted mappings; coefficients and fixed-weight precision are
conditional, not measured weather errors or a physical covariance budget.
"""
import numpy as np
from scipy.linalg import solve_triangular

from . import network_clocks

PROBE_RMS_M = .01  # coherent STATION ZENITH amplitude, not link noise sigma
RTOL = 1e-10


def admit(network, candidate):
    rows = [r for b in network['blocks'] for r in b['rows']]
    if not rows or any(r['reference']==candidate for r in rows):
        raise ValueError('nonempty candidate-excluding source network required')
    return rows


def wet_design(block, names):
    """Positive model delay in code/phase, zero MW; metres per zenith metre."""
    m = len(block['rows'])
    result = np.zeros((len(block['y']),len(names)))
    for i,r in enumerate(block['rows']):
        mapping = float(r['wet_mapping'])
        if not np.isfinite(mapping) or mapping<=0:
            raise ValueError('finite positive admitted wet mapping required')
        result[i,names.index(r['station'])] = mapping
    result[m:2*m] = result[:m]
    return result


def profile_wet(network, candidate):
    """FWL source fit after ALL epoch clocks and global float biases.

Rank is resolved against the original weighted source scale, so a wholly
clock-blind source is not fitted by amplifying projection roundoff. No anchor,
ridge, residual rescaling, positivity clipping or arbitrary null completion.
"""
    rows = admit(network,candidate)
    names = sorted({r['station'] for r in rows})
    designs, originals, residuals = [], [], []
    for b in network['blocks']:
        g = wet_design(b,names)
        def whiten(x):
            return (solve_triangular(b['chol'],x,lower=True) if b['chol'] is not None else
                x/(b['sigma'][:,None] if x.ndim==2 else b['sigma']))
        originals.append(whiten(g))
        designs.append(whiten(g-b['a']@(b['gain']@g)))
        residuals.append(whiten(b['y']-b['a']@b['parameters']-b['b']@network['ambiguities_m']))
    design = np.vstack(designs)
    nuisance = network['profiled_ambiguity_left']
    design -= nuisance@(nuisance.T@design)
    residual = np.concatenate(residuals)
    u,s,vt = np.linalg.svd(design,full_matrices=False)
    reference_scale = np.linalg.svd(np.vstack(originals),compute_uv=False)[0]
    rank = int(np.count_nonzero(s>RTOL*reference_scale))
    result = {'stations':names,'parameter_units':'metres zenith wet residual',
        'source_shape':'one signed constant zenith residual per station',
        'source_count':len(names),'resolved_rank':rank,
        'profiled_singular_values_per_m':s,'unprofiled_singular_scale_per_m':reference_scale,
        'rank_rtol':RTOL,'clocks_and_all_float_biases_profiled':True,
        'physical_wet_model_qualified':False,'covariance_is_fixed_weight_precision_only':True}
    if rank!=len(names):
        return {**result,'status':'SOURCE_RANK_DEFICIENT','unresolved_source_basis':vt[rank:].T}
    inverse = vt.T/s
    estimate = inverse@(u.T@residual)
    minimum = {station:min(float(r['zenith_wet_m'])+estimate[i] for r in rows if r['station']==station)
        for i,station in enumerate(names)}
    remaining = residual-design@estimate
    return {**result,'status':'CONDITIONAL_SOURCE_FIT',
        'zenith_wet_correction_m':dict(zip(names,estimate,strict=True)),
        'conditional_parameter_covariance_m2':inverse@inverse.T,
        'weighted_cost_before':float(residual@residual),'weighted_cost_after':float(remaining@remaining),
        'minimum_reference_total_zenith_wet_m':minimum,
        'domain_status':'NEGATIVE_REFERENCE_TOTAL_WET' if min(minimum.values())<0 else 'NONNEGATIVE_REFERENCE_SAMPLES_ONLY'}


def clock_wet_response(network, requests, candidate, names):
    """Positive raw path error -> estimated clock data; includes bias refits."""
    admit(network,candidate)
    response = network_clocks.observation_response(network,requests)
    return sum(r@wet_design(b,names) for b,r in zip(network['blocks'],response,strict=True))


def coupled_response(state_response, clock_indices, clock_source, target_source, names):
    """Positive assumed wet MODEL correction changes data by minus each map.

Target-model columns include code metres and phase rates in their original
full-data ordering. Clock columns contain offset metres and interval m/s.
The same station vector crosses both paths; it is never duplicated as two
independent noise sources. No source covariance is assigned here.
"""
    response = np.asarray(state_response)[:6]
    reference = -response[:,clock_indices]@clock_source
    target = -response@target_source
    combined = reference+target
    matrices = {'reference_only':reference,'candidate_only':target,'coupled':combined}
    count = len(names)
    gains = {}
    for label,t in matrices.items():
        position = np.sqrt(count)*np.linalg.svd(t[:3],compute_uv=False)[0]
        velocity = np.sqrt(count)*np.linalg.svd(t[3:],compute_uv=False)[0]*1000
        gains[label] = {'maximum_position_gain_m_per_m_zenith_rms':position,
            'maximum_velocity_gain_mm_s_per_m_zenith_rms':velocity,
            'coherent_zenith_rms_m_for_1m_position':1/position if position>0 else None,
            'coherent_zenith_rms_m_for_1mm_s_velocity':1/velocity if velocity>0 else None}
    _,s,vt = np.linalg.svd(combined[:3],full_matrices=False)
    scale = max(np.linalg.svd(reference[:3],compute_uv=False)[0],
                np.linalg.svd(target[:3],compute_uv=False)[0])
    result = {'stations':names,'state_model_response_m_m_s_per_m_zenith':matrices,'gains':gains,
        'positive_source_is_assumed_model_delay_increase':True,
        'source_rms_is_station_zenith_amplitude_not_link_sigma':True,
        'physical_covariance_qualified':False,'rank_rtol':RTOL}
    if s[0]<=RTOL*scale:
        return {**result,'status':'NO_RESOLVED_SOURCE_POSITION_PROBE'}
    probe = vt[0]*PROBE_RMS_M*np.sqrt(count)
    return {**result,'status':'SOURCE_PROBE_PREPARED',
        'zenith_probe_m':dict(zip(names,probe,strict=True)),
        'zenith_probe_rms_m':float(np.sqrt(np.mean(probe**2))),
        'zenith_probe_peak_m':float(max(abs(probe))),
        'linear_probe_state_change_m_m_s':{k:t@probe for k,t in matrices.items()}}


FAMILIES = ('wet', 'orbit', 'antenna', 'bias')
PREDICTION_RTOL = 1e-8


def source_columns(rows, families):
    if not families or len(set(families))!=len(families) or not set(families)<=set(FAMILIES):
        raise ValueError('distinct admitted source families required')
    stations = sorted({r['station'] for r in rows})
    references = sorted({r['reference'] for r in rows})
    links = sorted({r['station']+'/'+r['reference'] for r in rows})
    return ([('wet',s,'Z') for s in stations] if 'wet' in families else [])+[
        (f,q,a) for f,axes in [('orbit','RTN'),('antenna','XYZ')] if f in families
        for q in references for a in axes]+([('bias',k,'IF_CODE') for k in links] if 'bias' in families else [])


def source_design(rows, columns, channels=3):
    """Metres of retained IF model per source metre; stable phase/MW already float.

    Legacy rows hold emission/clock fixed. Complete rows also carry the
    emitted-clock/relativity and P1 hardware response. Neither models antenna PCV.
    """
    m=len(rows);g=np.zeros((channels*m,len(columns)))
    index={tuple(c):j for j,c in enumerate(columns)}
    for i,r in enumerate(rows):
        for j,(family,key,axis) in enumerate(columns):
            value=0.
            if family=='wet' and key==r['station']:
                value=float(r['wet_mapping'])
                if value<=0:raise ValueError('positive admitted wet mapping required')
            if family in ('orbit','antenna') and key==r['reference']:
                value=float(r[family+'_mapping']['RTN'.index(axis) if family=='orbit' else 'XYZ'.index(axis)])
            if family=='bias' and key==r['station']+'/'+r['reference']:value=float(r.get('bias_code_mapping',1.))
            g[i,j]=value
            if family!='bias':g[m+i,j]=value
            elif key==r['station']+'/'+r['reference']:
                g[m+i,j]=float(r.get('bias_phase_mapping',0.))
                if channels==3:g[2*m+i,j]=float(r.get('bias_mw_mapping',0.))
    if not np.isfinite(g).all():raise ValueError('finite admitted source mappings required')
    # A new reference/link cannot silently receive a zero correction.
    for r in rows:
        for family,keys in [('wet',[(r['station'],'Z')]),('orbit',[(r['reference'],a) for a in 'RTN']),
                            ('antenna',[(r['reference'],a) for a in 'XYZ']),
                            ('bias',[(r['station']+'/'+r['reference'],'IF_CODE')])]:
            if any(c[0]==family for c in columns) and any((family,k,a) not in index for k,a in keys):
                raise ValueError('unseen source coordinate')
    return g


def profile_sources(network, candidate, families):
    """Joint identifiable projection, conditional wet fit and nuisance response.

    The minimum Euclidean metre-norm representative is a computational device.
    A null coordinate is never asserted to be zero or physically estimated.
    Returned workspace is transient; result retains the source null space.
    """
    rows=admit(network,candidate);columns=source_columns(rows,families)
    designs=[];original=[];reduced=[];residual=[]
    for b in network['blocks']:
        g=source_design(b['rows'],columns,len(b['y'])//len(b['rows']))
        def w(x):return (solve_triangular(b['chol'],x,lower=True) if b['chol'] is not None else
            x/(b['sigma'][:,None] if x.ndim==2 else b['sigma']))
        designs.append(g);original.append(w(g));reduced.append(w(g-b['a']@(b['gain']@g)))
        residual.append(w(b['y']-b['a']@b['parameters']-b['b']@network['ambiguities_m']))
    j0=np.vstack(reduced);u0=network['profiled_ambiguity_left']
    beta=network['profiled_ambiguity_inverse']@(u0.T@j0)
    clocks=[b['gain']@(g-b['b']@beta) for b,g in zip(network['blocks'],designs,strict=True)]
    j=j0-u0@(u0.T@j0);y=np.concatenate(residual)
    u,s,vt=np.linalg.svd(j,full_matrices=j.shape[0]<j.shape[1])
    scale=np.linalg.svd(np.vstack(original),compute_uv=False)[0]
    rank=int(np.count_nonzero(s>RTOL*scale));basis=vt[:rank];null=vt[rank:].T
    theta=basis.T@((u[:,:rank].T@y)/s[:rank])
    remaining=y-j@theta
    result={'status':'CONDITIONAL_IDENTIFIED_SOURCE_PROJECTION','families':list(families),
        'columns':columns,'parameter_units':'metres in each declared source coordinate',
        'source_count':len(columns),'resolved_rank':rank,'null_count':len(columns)-rank,
        'rank_rtol':RTOL,'original_weighted_source_scale_per_m':scale,
        'singular_values_per_m':s,'unresolved_source_basis':null,
        'representative_m':theta,'representative_is_physical_source_estimate':False,
        'representative_convention':'minimum Euclidean metre norm; null amplitudes unassigned',
        'weighted_cost_before':float(y@y),'weighted_cost_after':float(remaining@remaining),
        'physical_source_covariance_qualified':False,'fixed_weight_precision_only':True}
    nw=sum(c[0]=='wet' for c in columns)
    if nw:
        wetj=j[:,:nw];other=j[:,nw:]
        if other.shape[1]:
            ou,os,_=np.linalg.svd(other,full_matrices=False)
            other_scale=np.linalg.svd(np.vstack(original)[:,nw:],compute_uv=False)[0]
            nr=int(np.count_nonzero(os>RTOL*other_scale));ou=ou[:,:nr]
            conditional=wetj-ou@(ou.T@wetj);wy=y-ou@(ou.T@y)
        else:conditional,wy=wetj,y
        wu,ws,wv=np.linalg.svd(conditional,full_matrices=False)
        wet_scale=np.linalg.svd(np.vstack(original)[:,:nw],compute_uv=False)[0]
        wrank=int(np.count_nonzero(ws>RTOL*wet_scale))
        wp={'status':'WET_CONDITIONALLY_IDENTIFIABLE' if wrank==nw else 'WET_SOURCE_UNIDENTIFIABLE',
            'stations':[c[1] for c in columns[:nw]],'resolved_rank':wrank,
            'singular_values_per_m':ws,'original_weighted_wet_scale_per_m':wet_scale,
            'joint_null_wet_projection_norm':float(np.linalg.norm(null[:nw],2)) if null.shape[1] else 0.}
        if wrank==nw:
            inv=wv.T/ws;z=inv@(wu.T@wy)
            minimum={c[1]:min(float(r['zenith_wet_m'])+z[i] for r in rows if r['station']==c[1]) for i,c in enumerate(columns[:nw])}
            wp.update(zenith_wet_correction_m=dict(zip(wp['stations'],z,strict=True)),
                conditional_parameter_covariance_m2=inv@inv.T,minimum_reference_total_zenith_wet_m=minimum,
                domain_status='NEGATIVE_REFERENCE_TOTAL_WET' if min(minimum.values())<0 else 'NONNEGATIVE_REFERENCE_SAMPLES_ONLY')
        result['wet']=wp
    return result,{'columns':columns,'theta':theta,'null':null,'designs':designs,'design':j,
        'clock_response':clocks,'ambiguity_response':beta}


def source_link_prediction(network, workspace, row, segment):
    """Only issue a held code/phase level when its complete map kills the null.

    Includes compensating clock and prefix float-bias refits, not merely G_held.
    No held observation value or GF witness is read here.
    """
    bidx=next((i for i,b in enumerate(network['blocks']) if b['time_s']==row['time_s']),None)
    if bidx is None:return {'status':'UNOBSERVED_NETWORK_CLOCK'}
    b=network['blocks'][bidx]
    try:
        i=b['stations'].index(row['station']);q=b['references'].index(row['reference'])
    except ValueError:return {'status':'UNOBSERVED_NETWORK_CLOCK'}
    if segment not in network['segments']:return {'status':'UNOBSERVED_PREFIX_PHASE'}
    try:g=source_design([row],workspace['columns'])
    except ValueError:return {'status':'UNSEEN_SOURCE_COORDINATE'}
    a=np.zeros(len(b['parameters']));a[i]=row.get('clock_derivative',1.)
    a[len(b['stations']):]=-b['reference_basis'][q]
    nuisance=a@workspace['clock_response'][bidx]
    k=network['segments'].index(segment)
    h=np.vstack([g[0]-nuisance,g[1]-nuisance-workspace['ambiguity_response'][k]])
    null=workspace['null']
    scales=np.maximum(1.,np.maximum(np.linalg.norm(g[:2],axis=1),np.linalg.norm(g[:2]-h,axis=1)))
    defect=np.linalg.norm(h@null,axis=1)/scales
    result={'code_phase_null_response_relative':defect,'prediction_rtol':PREDICTION_RTOL}
    if np.any(defect>PREDICTION_RTOL):return {**result,'status':'UNIDENTIFIABLE_SOURCE_PREDICTION'}
    clock=float(a@b['parameters']);change=h@workspace['theta']
    return {**result,'status':'PREDICTED','clock_prediction_m':clock,
        'path_prediction_m':float(clock+change[0]),
        'phase_prediction_m':float(clock+network['ambiguities_m'][k]+change[1]),
        'phase_path_prediction_m':float(clock+network['ambiguities_m'][k]+change[1])}


WEAK_RTOLS=(1e-9,1e-10,1e-11)
PROBE_SOURCE_L2_M=(.01,.1)


def split_probe(columns, vector, candidate):
    result={'wet':{},'orbit':{},'antenna':{},'bias':{}}
    for (family,key,axis),value in zip(columns,vector,strict=True):
        if family in ('orbit','antenna'):
            if key==candidate:raise ValueError('candidate physical product probe')
            result[family].setdefault(key,[0.,0.,0.])['RTN'.index(axis) if family=='orbit' else 'XYZ'.index(axis)]=float(value)
        else:result[family][key]=float(value)
    return result


def weak_modes(design, state_map, original_scale):
    """Compare subspaces, then select a state-relevant weak retained direction.

    All coordinates have the declared Euclidean metre metric. Orthogonal
    changes preserve it; thresholds are sensitivity cases, not score tuning.
    """
    u,s,v=np.linalg.svd(design,full_matrices=design.shape[0]<design.shape[1])
    t=np.asarray(state_map);cases={}
    for tol in WEAK_RTOLS:
        rank=int(sum(s>tol*original_scale));basis=v[:rank];null=v[rank:].T
        gain=(t@basis.T)/s[:rank]
        cases[str(tol)]={'rank':rank,'source_count':len(v),
            'position_gain_m_per_weighted_reference_norm':float(np.linalg.norm(gain[:3],2)),
            'velocity_gain_mm_s_per_weighted_reference_norm':float(np.linalg.norm(gain[3:],2)*1000),
            'null_state_map_norm':float(np.linalg.norm(t@null,2)) if null.shape[1] else 0.}
    rank=cases[str(RTOL)]['rank'];basis=v[:rank]
    weak=np.flatnonzero((s>RTOL*original_scale)&(s<1e-8*original_scale))
    if not len(weak):raise ValueError('no declared weak retained source band')
    gain=(t[:3]@v[weak].T)/s[weak]
    _,_,directions=np.linalg.svd(gain,full_matrices=False)
    q=(v[weak].T/s[weak])@directions[0];q/=np.linalg.norm(q)
    # Compare signs/permutation, orthogonal rotation and global m -> mm units.
    p=len(v);permutation=np.eye(p)[:,np.arange(p)[::-1]]
    permutation*=np.where(np.arange(p)%2,1.,-1.)
    rotation=np.eye(p);angle=.37
    for i in range(0,p-1,2):rotation[i:i+2,i:i+2]=[[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]
    checks={}
    nominal=basis.T@basis
    for label,change,unit in [('signed_permutation',permutation,1.),('orthogonal_rotation',rotation,1.),('millimetre_coordinates',np.eye(p),.001)]:
        _,ss,vv=np.linalg.svd(design@change*unit,full_matrices=False)
        rr=int(sum(ss>RTOL*original_scale*unit));bb=change@vv[:rr].T
        checks[label]={'rank':rr,'retained_projector_difference_norm':float(np.linalg.norm(bb@bb.T-nominal,2)),
            'scaled_singular_value_relative_max_difference':float(max(abs(ss/unit-s)/original_scale))}
    return {'thresholds':cases,'equivalent_coordinate_checks':checks,'weak_band_count':len(weak),
        'weak_band_upper_rtol':1e-8,'mode_selection_uses_held_scores':False,
        'weak_direction_m_per_unit_l2_m':q,'strong_direction_m_per_unit_l2_m':v[0],
        'weak_reference_weighted_signal_per_m':float(np.linalg.norm(design@q)),
        'weak_linear_state_response_per_m':t@q}, {'s':s,'v':v,'rank':rank,'projector':nominal}


def independent_information(spectrum, state_map, columns, clock_map, weak_direction):
    """Hypothetical independent measurements, never a physical covariance.

    Retain the declared reference information, then add measurements. Missing
    source directions are kept unresolved, not assigned zero uncertainty.
    Endpoint clock measurements are unique; derived intervals are not counted
    twice. Source sigma is a scenario, not an observed calibration accuracy.
    """
    s,v,rank=spectrum['s'],spectrum['v'],spectrum['rank']
    reference=s[:rank,None]*v[:rank];p=v.shape[1];identity=np.eye(p)
    families={f:identity[[i for i,c in enumerate(columns) if c[0]==f]] for f in FAMILIES}
    families.update(wet_and_orbit=np.vstack([families['wet'],families['orbit']]),
        all_source_coordinates=identity,receiver_clock_endpoints=np.asarray(clock_map),
        ideal_weak_functional=np.asarray(weak_direction)[None,:])
    t=np.asarray(state_map);result={}
    for label,h in families.items():
        grid=[]
        for sigma in (1e-4,1e-3,1e-2,1e-1,1.):
            a=np.vstack([reference,h/sigma])
            _,ss,vv=np.linalg.svd(a,full_matrices=a.shape[0]<p)
            rr=int(sum(ss>1e-12*ss[0]));null=vv[rr:].T
            inv=vv[:rr].T/ss[:rr]
            defect=float(np.linalg.norm(t@null,2)/max(1.,np.linalg.norm(t,2))) if null.shape[1] else 0.
            image=t@inv;cov=image@image.T
            pos=float(np.sqrt(max(0.,np.linalg.eigvalsh(cov[:3,:3])[-1])))
            vel=float(np.sqrt(max(0.,np.linalg.eigvalsh(cov[3:,3:])[-1]))*1000)
            q=np.asarray(weak_direction)
            qdef=float(np.linalg.norm(q@null)) if null.shape[1] else 0.
            grid.append({'sigma_m':sigma,'resolved_rank':rr,'source_count':p,
                'state_null_response_relative':defect,'state_functional_status':
                    'CONDITIONALLY_ESTIMABLE_AT_NUMERICAL_TOLERANCE' if defect<=1e-8 else 'UNRESOLVED_STATE_FUNCTIONAL',
                'identified_projection_position_sigma_m':pos,'identified_projection_velocity_sigma_mm_s':vel,
                'complete_state_precision_issued':defect<=1e-8,
                'weak_functional_sigma_m':float(np.linalg.norm(q@inv)) if qdef<=1e-8 else None,
                'weak_functional_null_response':qdef,
                'meets_1m_1mm_s_design_benchmark':defect<=1e-8 and pos<=1 and vel<=1})
        result[label]={'measurement_count':len(h),'independent_measurements_are_hypothetical':True,
            'precision_is_source_information_diagnostic_not_added_to_rf_covariance':True,'grid':grid}
    return result


def known_source_recovery(rows, physical_signal, linear_signal, truth, state_map, spectrum, raw_covariance, candidate):
    """Noiseless incremental networks, with physical and linear forward controls.

    Unknown real residuals/float levels are absent. Only the identifiable source
    projection is a recovery target. A failed physical shape recovery is kept.
    """
    admit({'blocks':[{'rows':rows}]},candidate)
    truth=np.asarray(truth);expected=spectrum['projector']@truth;t=np.asarray(state_map)
    result={}
    for label,signal in [('linear_control',linear_signal),('physical_increment',physical_signal)]:
        admit({'blocks':[{'rows':own} for own,_ in signal]},candidate)
        synthetic=[]
        for own,g in signal:
            m=len(own)
            synthetic.extend({**r,'code_m':g[i],'phase_m':g[m+i],'mw_m':g[2*m+i]} for i,r in enumerate(own))
        fitted=network_clocks.fit(synthetic,raw_covariance=raw_covariance)
        record,_=profile_sources(fitted,candidate,FAMILIES)
        estimate=np.asarray(record['representative_m']);error=estimate-expected
        relative=float(np.linalg.norm(error)/max(np.linalg.norm(expected),1e-30))
        direction=truth/np.linalg.norm(truth)
        functional_error=float(direction@error)
        functional_relative=abs(functional_error)/np.linalg.norm(truth)
        result[label]={'status':'IDENTIFIED_PROJECTION_RECOVERED' if relative<=1e-3 else 'IDENTIFIED_PROJECTION_RECOVERY_FAILED',
            'injected_functional_status':'RECOVERED' if functional_relative<=1e-3 else 'RECOVERY_FAILED',
            'injected_functional_error_m':functional_error,'injected_functional_relative_error':functional_relative,
            'relative_identified_source_error':relative,'identified_source_error_l2_m':float(np.linalg.norm(error)),
            'local_state_functional_error_m_m_s':t@error,'fitted_source_projection_m':estimate,
            'resolved_rank':record['resolved_rank'],'weighted_cost_after':record['weighted_cost_after']}
    return result


def profiled_increment(network, blocks):
    """Apply the existing clock/float residual projector to an increment."""
    if len(blocks)!=len(network['blocks']):raise ValueError('one increment per admitted epoch required')
    parts=[]
    for b,y in zip(network['blocks'],blocks,strict=True):
        y=np.asarray(y,float)
        if y.shape!=b['y'].shape or not np.isfinite(y).all():raise ValueError('finite admitted increment shape required')
        z=y-b['a']@(b['gain']@y)
        parts.append(solve_triangular(b['chol'],z,lower=True) if b['chol'] is not None else z/b['sigma'])
    y=np.concatenate(parts);u=network['profiled_ambiguity_left']
    return y-u@(u.T@y)


def recover_profiled_increment(projected, design, spectrum, truth, state_map):
    """Recover an identifiable projection without refitting unchanged nuisances."""
    u,s,v,rank=(spectrum[k] for k in ('u','s','v','rank'))
    estimate=v[:rank].T@((u[:,:rank].T@projected)/s[:rank]);truth=np.asarray(truth)
    expected=v[:rank].T@(v[:rank]@truth);error=estimate-expected
    relative=float(np.linalg.norm(error)/max(np.linalg.norm(expected),1e-30))
    scalar=float((truth/np.linalg.norm(truth))@error);functional_relative=abs(scalar)/np.linalg.norm(truth)
    null_response=float(np.linalg.norm(v[rank:]@truth)/np.linalg.norm(truth))
    remaining=projected-design@estimate
    return {'status':'IDENTIFIED_PROJECTION_RECOVERED' if relative<=1e-3 else 'IDENTIFIED_PROJECTION_RECOVERY_FAILED',
        'injected_functional_status':('UNIDENTIFIABLE_INJECTED_FUNCTIONAL' if null_response>1e-8 else ('RECOVERED' if functional_relative<=1e-3 else 'RECOVERY_FAILED')),
        'injected_functional_null_response':null_response,
        'identified_truth_projection_l2_m':float(np.linalg.norm(expected)),'injected_source_l2_m':float(np.linalg.norm(truth)),
        'relative_identified_source_error':relative,'injected_functional_relative_error':functional_relative,
        'injected_functional_error_m':scalar,'fitted_source_projection_m':estimate,
        'local_state_functional_error_m_m_s':np.asarray(state_map)@error,'weighted_cost_after':float(remaining@remaining)}


def source_information_summary(design,state_map,weak_direction,original_scale):
    """Absolute reference-scale cuts; unresolved directions stay unbounded.

    Three cuts are sensitivity cases on one SVD, with no sigma-dependent
    rescaling of the rank criterion when measurement precision changes.
    """
    _,s,v=np.linalg.svd(design,full_matrices=design.shape[0]<design.shape[1]);t=np.asarray(state_map);q=np.asarray(weak_direction);out={}
    for tol in WEAK_RTOLS:
        r=int(sum(s>tol*original_scale));null=v[r:].T;inv=v[:r].T/s[:r]
        defect=float(np.linalg.norm(t@null,2)/max(1.,np.linalg.norm(t,2))) if null.shape[1] else 0.
        image=t@inv;cov=image@image.T;qdef=float(np.linalg.norm(q@null)) if null.shape[1] else 0.
        pos=float(np.sqrt(max(0.,np.linalg.eigvalsh(cov[:3,:3])[-1])))
        vel=float(np.sqrt(max(0.,np.linalg.eigvalsh(cov[3:,3:])[-1]))*1000)
        out[str(tol)]={'resolved_rank':r,'source_count':v.shape[1],'absolute_singular_cut':tol*original_scale,
            'state_null_response_relative':defect,'complete_state_precision_issued':defect<=1e-8,
            'state_functional_status':'CONDITIONALLY_ESTIMABLE_AT_NUMERICAL_TOLERANCE' if defect<=1e-8 else 'UNRESOLVED_STATE_FUNCTIONAL',
            'identified_projection_position_sigma_m':pos,'identified_projection_velocity_sigma_mm_s':vel,
            'weak_functional_sigma_m':float(np.linalg.norm(q@inv)) if qdef<=1e-8 else None,
            'weak_functional_null_response':qdef,'meets_1m_1mm_s_design_benchmark':defect<=1e-8 and pos<=1 and vel<=1}
    return out


def source_measurement_design(columns,families,law):
    """Hypothetical source observations with stated correlations or free offsets."""
    from scipy.linalg import helmert
    p=len(columns);parts=[];count=0
    if law not in ('independent','family_common_half','family_offset_free'):raise ValueError('unknown external source law')
    for f in families:
        if f not in FAMILIES:raise ValueError('unknown external source family')
        axes=sorted({c[2] for c in columns if c[0]==f})
        for axis in axes:
            at=[i for i,c in enumerate(columns) if c[0]==f and c[2]==axis];h=np.eye(p)[at];count+=len(h)
            if law=='family_common_half':h=solve_triangular(np.linalg.cholesky(.5*np.eye(len(h))+.5*np.ones((len(h),len(h)))),h,lower=True)
            elif law=='family_offset_free':h=helmert(len(h),full=False)@h
            parts.append(h)
    return (np.vstack(parts) if parts else np.empty((0,p))),count


def complementary_source_information(design,columns,state_map,weak_direction,original_scale):
    """All family subsets; direct observations remain hypothetical, no priors."""
    from itertools import combinations
    _,s,v=np.linalg.svd(design,full_matrices=False);reference=s[:,None]*v
    out={}
    for size in range(1,len(FAMILIES)+1):
        for families in combinations(FAMILIES,size):
            label='_'.join(families);out[label]={}
            for law in ('independent','family_common_half','family_offset_free'):
                h,count=source_measurement_design(columns,families,law)
                out[label][law]={'raw_measurement_count':count,'retained_contrast_count':len(h),
                    'independent_external_values_admitted':False,'source_observation_law':law,
                    'grid':[{'sigma_m':sigma,'rank_cases':source_information_summary(np.vstack([reference,h/sigma]),state_map,weak_direction,original_scale)} for sigma in (1e-4,1e-3,1e-2,1e-1,1.)]}
    return out


def joint_external_clock_source_design(network,columns,endpoint_keys,sigma_m,candidate,*,epoch_correlation=0.):
    """Profile true external-clock rows with RF clocks and station offsets.

    External measurements observe receiver clocks, not K G source shifts.
    Their RF calibration noise and its coupling to sources are retained by
    joint profiling. A free instrument offset per station removes unsupported
    absolute calibration; same-epoch correlation is an explicit scenario.
    """
    admit(network,candidate)
    if not np.isfinite(sigma_m) or sigma_m<=0 or epoch_correlation not in (0.,.5):raise ValueError('declared external clock law required')
    keys=set(map(tuple,endpoint_keys))
    if len(keys)!=len(endpoint_keys):raise ValueError('unique external clock endpoints required')
    stations=sorted({s for s,t in keys});nb=len(network['ambiguities_m']);parts=[];sources=[];seen=set();raw_count=0
    for b in network['blocks']:
        m=len(b['rows']);g=source_design(b['rows'],columns,len(b['y'])//m)
        def w(x):return solve_triangular(b['chol'],x,lower=True) if b['chol'] is not None else x/b['sigma'][:,None]
        at=[(i,s) for i,s in enumerate(b['stations']) if (s,b['time_s']) in keys];k=len(at)
        a=np.vstack([w(b['a']),np.zeros((k,b['a'].shape[1]))])
        beta=np.zeros((len(a),nb+len(stations)));beta[:len(b['y']),:nb]=w(b['b'])
        source=np.vstack([w(g),np.zeros((k,len(columns)))])
        if k:
            ext=np.zeros((k,b['a'].shape[1]));offset=np.zeros((k,len(stations)))
            for row,(i,s) in enumerate(at):ext[row,i]=1.;offset[row,stations.index(s)]=1.;seen.add((s,b['time_s']))
            chol=np.linalg.cholesky(sigma_m**2*((1-epoch_correlation)*np.eye(k)+epoch_correlation*np.ones((k,k))))
            a[-k:]=solve_triangular(chol,ext,lower=True);beta[-k:,nb:]=solve_triangular(chol,offset,lower=True)
        q,_=np.linalg.qr(a,mode='reduced');parts.append(beta-q@(q.T@beta));sources.append(source-q@(q.T@source));raw_count+=k
    if seen!=keys:raise ValueError('external clock endpoint absent from admitted reference network')
    b=np.vstack(parts);g=np.vstack(sources);norms=np.linalg.norm(b,axis=0)
    normalized=np.divide(b,norms,out=np.zeros_like(b),where=norms>0)
    u,s,_=np.linalg.svd(normalized,full_matrices=False)
    rank=int(sum(s>1e-12*s[0]));u=u[:,:rank];j=g-u@(u.T@g)
    return j,{'external_endpoint_count':raw_count,'instrument_offset_stations':stations,'instrument_offsets_profiled_without_prior':True,
        'epoch_correlation':epoch_correlation,'sigma_m':sigma_m,'profiled_float_and_instrument_rank':rank,
        'nuisance_columns_normalized_before_rank_test':True,'nuisance_rank_rtol':1e-12,'float_and_instrument_count':b.shape[1],'external_measurements_observe_receiver_clocks':True,
        'external_source_shift_KG_not_treated_as_direct_observation':True,'external_values_admitted':False}
