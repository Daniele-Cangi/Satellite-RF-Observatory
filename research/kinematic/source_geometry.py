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
