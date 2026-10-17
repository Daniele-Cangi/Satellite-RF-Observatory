"""Temporal raw RF covariance through the fixed reference-clock estimator.

Build the covariance from raw-link and receiver-shared factors rather than a
huge raw-observation matrix. Preserve receiver/epoch, inter-arc, code/phase/MW
and reference-target cross terms. This is a declared partial sensitivity model;
it does not identify an absolute clock-like budget or refit reference weights.
"""
from collections import defaultdict

import numpy as np

from . import gnss_combinations, network_clocks


def propagate(network, requests, arcs, joint, clock_indices, candidate, raw_covariance,
              *, code_rho=0., receiver_fraction=0., retain_cross=True):
    if (not np.isfinite([code_rho,receiver_fraction]).all() or not 0<=code_rho<1
            or not 0<=receiver_fraction<1 or not isinstance(retain_cross,bool)):
        raise ValueError('strictly subunit temporal/shared fractions required')
    raw = np.asarray(raw_covariance,float)
    gnss_combinations.covariance(raw)
    if np.max(abs(raw[:2,2:]))>1e-15:
        raise ValueError('this temporal model requires separate code/phase raw noise blocks')
    transform = gnss_combinations.transform()[gnss_combinations.RETAINED]
    if any(r['reference']==candidate for b in network['blocks'] for r in b['rows']):
        raise ValueError('candidate RF in its own reference covariance')
    response = network_clocks.observation_response(network,requests)
    keys,raw_response = [],[]
    for b,r in zip(network['blocks'],response,strict=True):
        m = len(b['rows'])
        if r.shape[1]!=3*m:
            raise ValueError('joint IF/MW reference estimator required')
        keys.extend((row['station'],row['reference'],b['time_s']) for row in b['rows'])
        raw_response.append(np.einsum('ncm,cj->nmj',r.reshape(len(requests),3,m),transform))
    raw_response = np.concatenate(raw_response,axis=1)
    del response
    out = np.array(joint,float,copy=True)
    clock_indices = np.asarray(clock_indices,int)
    if len(clock_indices)!=len(requests):
        raise ValueError('clock indices and requests differ')
    target,rf_indices,at = {},[],0
    for a in arcs:
        n = len(a['stations'])
        if len(a['tags_s'])!=3 or len(a['covariance'])!=13*n:
            raise ValueError('three-endpoint IF/MW study arcs required')
        rf_indices.extend(at+np.arange(7*n))
        for e,dt in enumerate(a['tags_s']):
            for j,s in enumerate(a['stations']):
                indices,values = [at+e*n+j],[transform[0]]
                for k in range(2):
                    if e in (k,k+1):
                        sign = -1. if e==k else 1.
                        duration = a['tags_s'][k+1]-a['tags_s'][k]
                        indices.extend([at+3*n+k*n+j,at+5*n+k*n+j])
                        values.extend([sign*transform[1]/duration,sign*transform[2]/duration])
                key = (s,candidate,a['endpoint_gpst_s']+dt)
                if key in target:
                    raise ValueError('reused candidate raw endpoint')
                target[key] = (np.asarray(indices),np.asarray(values))
        at += len(a['covariance'])
    if out.shape!=(at,at):
        raise ValueError('joint covariance and arcs differ')
    rf_indices = np.asarray(rf_indices,int)
    noisy = np.r_[rf_indices,clock_indices]
    ground = np.setdiff1d(np.arange(at),noisy)
    if len(ground) and np.max(abs(out[np.ix_(noisy,ground)]))>1e-12:
        raise ValueError('unmodeled ground/RF covariance')
    out[noisy,:] = 0.
    out[:,noisy] = 0.
    links = defaultdict(lambda:{'reference':[],'target':[]})
    receivers = defaultdict(lambda:{'reference':[],'target':[]})
    for i,(s,q,t) in enumerate(keys):
        links[s,q]['reference'].append(i)
        receivers[s]['reference'].append(i)
    for key in target:
        s,q,_ = key
        links[s,q]['target'].append(key)
        receivers[s]['target'].append(key)
    def add(group,weight):
        if weight==0:
            return
        ref,own = group['reference'],group['target']
        times = sorted({keys[i][2] for i in ref}|{k[2] for k in own})
        time_index = {t:i for i,t in enumerate(times)}
        active = np.unique(np.r_[clock_indices if ref else np.array([],int),
            *[target[k][0] for k in own]]).astype(int)
        index = {r:i for i,r in enumerate(active)}
        clock_rows = [index[r] for r in clock_indices] if ref else []
        effect = np.zeros((len(active),len(times),4))
        for i in ref:
            effect[clock_rows,time_index[keys[i][2]],:] += raw_response[:,i,:]
        for k in own:
            rows,values = target[k]
            effect[[index[r] for r in rows],time_index[k[2]],:] += values
        delta = abs(np.subtract.outer(times,times))/30.
        code_kernel = code_rho**delta
        covariance = np.zeros((len(active),len(active)))
        for channels,kernel in (([0,1],code_kernel),([2,3],None)):
            factor = np.einsum('ntc,cb->ntb',effect[:,:,channels],np.linalg.cholesky(raw[np.ix_(channels,channels)]))
            for band in range(2):
                f = factor[:,:,band]
                covariance += (f if kernel is None else f@kernel)@f.T
        out[np.ix_(active,active)] += weight*covariance
    for group in links.values():
        add(group,1-receiver_fraction)
    for group in receivers.values():
        add(group,receiver_fraction)
    denominator = np.sqrt(out[rf_indices,rf_indices,None]*out[clock_indices,clock_indices][None,:])
    cross = out[np.ix_(rf_indices,clock_indices)]
    correlation = float(np.max(abs(cross)/denominator))
    if not retain_cross:
        out[np.ix_(rf_indices,clock_indices)] = 0.
        out[np.ix_(clock_indices,rf_indices)] = 0.
    out = (out+out.T)/2
    own,at = [],0
    for a in arcs:
        stop = at+len(a['covariance'])
        own.append({**a,'covariance':out[at:stop,at:stop].copy()})
        at = stop
    return own,out,{'code_ar1_rho_30s':code_rho,'receiver_shared_variance_fraction':receiver_fraction,
        'phase_temporal_model':'independent endpoints; contemporaneous receiver sharing as declared',
        'reference_clock_estimator_refitted':False,'physical_covariance_qualified':False,
        'reference_target_cross_covariance_retained':retain_cross,
        'counterfactual_independence_ablation':not retain_cross,
        'maximum_rf_clock_correlation_before_ablation':correlation,
        'clock_covariance':out[np.ix_(clock_indices,clock_indices)]}
