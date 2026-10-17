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

    Orbit-like RTN and body PCO shapes shift emitted APC at fixed emission and
    clock. They are not complete orbit/relativity or frequency-dependent PCV laws.
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
            if family=='bias' and key==r['station']+'/'+r['reference']:value=1.
            g[i,j]=value
            if family!='bias':g[m+i,j]=value
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
