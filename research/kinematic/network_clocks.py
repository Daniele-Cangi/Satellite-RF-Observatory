"""Code/phase network clocks with free reference clocks and float link biases.

Every epoch has its own receiver and reference-clock values. Reference errors
sum to zero to choose an additive-clock datum. Tiny geometry-time derivatives
are conditional on the reference model, not independent datum information.
Code and phase share clocks, but each admitted continuous link segment has an
unpenalized phase/code ambiguity. Supplied endpoint sigmas are weighting
assumptions, never a physical covariance inferred from small residuals.
"""
from collections import defaultdict

import numpy as np
from scipy.linalg import helmert, solve_triangular
from scipy.stats import chi2

from .calibration_transfer import operators
from . import gnss_combinations


def fit(rows, *, code_sigma_m=20., phase_sigma_m=.02, phase_drift=False, raw_covariance=None, reference_rotation=None):
    """Profile epoch clocks, then solve shared segment ambiguities by SVD.

    Rows contain already model-subtracted code/phase metres, a segment identity,
    and an optional receiver-clock derivative. No orbit or target identity is
    accepted here; admission and candidate exclusion belong to the caller.
    """
    if not rows or not all(np.isfinite(s) and s > 0 for s in (code_sigma_m, phase_sigma_m)):
        raise ValueError('nonempty network and positive endpoint sigmas required')
    keys = [(r['time_s'], r['station'], r['reference']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate network observation')
    combined = raw_covariance is not None
    channels = 3 if combined else 2
    endpoint_covariance = (gnss_combinations.covariance(raw_covariance)[np.ix_(
        gnss_combinations.RETAINED,gnss_combinations.RETAINED)] if combined else None)
    segments = sorted({r['segment'] for r in rows})
    segment_index = {s: i for i, s in enumerate(segments)}
    start = {s: min(r['time_s'] for r in rows if r['segment']==s) for s in segments}
    drifting = [s for s in segments if phase_drift and any(
        r['segment']==s and r['time_s']!=start[s] for r in rows)]
    mw_index = {s:len(segments)+i for i,s in enumerate(segments)} if combined else {}
    drift_index = {s: len(segments)+len(mw_index)+i for i,s in enumerate(drifting)}
    mw_drift_index = {s:2*len(segments)+len(drifting)+i for i,s in enumerate(drifting)} if combined else {}
    parameter_count = len(segments)+len(mw_index)+len(drifting)+len(mw_drift_index)
    grouped = defaultdict(list)
    for r in rows:
        if not np.isfinite([r['code_m'], r['phase_m'], r.get('clock_derivative', 1.)]).all():
            raise ValueError('finite network observations required')
        if combined and not np.isfinite(r['mw_m']):
            raise ValueError('finite admitted MW observation required')
        grouped[r['time_s']].append(r)
    blocks, reduced, values = [], [], []
    for time, own in sorted(grouped.items()):
        stations = sorted({r['station'] for r in own})
        refs = sorted({r['reference'] for r in own})
        if len(stations) < 2 or len(refs) < 2:
            raise ValueError(f'network lacks a station/reference contrast at {time}')
        graph = defaultdict(set)
        for row in own:
            s,q = ('station',row['station']),('reference',row['reference'])
            graph[s].add(q)
            graph[q].add(s)
        pending,seen = [next(iter(graph))],set()
        while pending:
            node = pending.pop()
            if node not in seen:
                seen.add(node)
                pending.extend(graph[node]-seen)
        if len(seen) != len(graph):
            raise ValueError('reference nuisance design rank deficient: disconnected clock network')
        datum = helmert(len(refs), full=False).T
        if reference_rotation is not None:
            if not np.isfinite(reference_rotation):raise ValueError('finite equivalent clock-basis angle required')
            rotation=np.eye(datum.shape[1]);c,s=np.cos(reference_rotation),np.sin(reference_rotation)
            for j in range(datum.shape[1]-1):
                rotation[:,j:j+2]=rotation[:,j:j+2]@np.array([[c,-s],[s,c]])
            datum=datum@rotation
        m, n = len(own), len(stations)
        a = np.zeros((channels*m, n+len(refs)-1))
        b = np.zeros((channels*m, parameter_count))
        for i, r in enumerate(own):
            a[i, stations.index(r['station'])] = r.get('clock_derivative', 1.)
            a[i, n:] = -datum[refs.index(r['reference'])]
            a[m+i] = a[i]
            b[m+i, segment_index[r['segment']]] = 1.
            if r['segment'] in drift_index:
                b[m+i, drift_index[r['segment']]] = (time-start[r['segment']])/3600.
            if combined:
                b[2*m+i,mw_index[r['segment']]] = 1.
                if r['segment'] in mw_drift_index:
                    b[2*m+i,mw_drift_index[r['segment']]] = (time-start[r['segment']])/3600.
        y = np.array([r['code_m'] for r in own]+[r['phase_m'] for r in own]+(
            [r['mw_m'] for r in own] if combined else []))
        sigma = np.r_[np.full(m, code_sigma_m), np.full(m, phase_sigma_m)]
        covariance = (np.kron(endpoint_covariance,np.eye(m)) if combined else np.diag(sigma**2))
        chol = np.linalg.cholesky(covariance) if combined else None
        whiten = (lambda x:solve_triangular(chol,x,lower=True)) if combined else (
            lambda x:x/sigma[:,None] if x.ndim==2 else x/sigma)
        # A disconnected bipartite graph has extra unobservable station
        # contrasts. Do not repair it by anchoring an arbitrary receiver.
        op = operators(a, a, covariance)
        gain, project = op['gain'], op['reference_residual']
        reduced.append(whiten(project@b))
        values.append(whiten(project@y))
        blocks.append({'time_s': time, 'stations': stations, 'references': refs,
            'reference_basis': datum, 'rows': own, 'a': a, 'b': b, 'y': y,
            'sigma':np.sqrt(covariance.diagonal()) if combined else sigma,
            'chol':chol,'covariance':covariance,'gain': gain, 'conditional_covariance':
            gain@covariance@gain.T if combined else (gain*sigma)@(gain*sigma).T,
            'ambiguity_response': -gain@b})
    design, y = np.vstack(reduced), np.concatenate(values)
    u, singular, vt = np.linalg.svd(design, full_matrices=False)
    if len(singular) != parameter_count or singular[-1] <= singular[0]*1e-10:
        raise ValueError('unobservable network segment ambiguity')
    ambiguities = (vt.T/singular)@(u.T@y)
    ambiguity_covariance = (vt.T/singular**2)@vt
    cost = 0.
    diagnostics = []
    for block in blocks:
        x = block['gain']@(block['y']-block['b']@ambiguities)
        residual = block['a']@x+block['b']@ambiguities-block['y']
        block['parameters'] = x
        weighted = (solve_triangular(block['chol'],residual,lower=True) if combined else residual/block['sigma'])
        cost += float(weighted@weighted)
        m = len(block['rows'])
        diagnostics.extend({'time_s': block['time_s'], 'station': r['station'],
            'reference': r['reference'], 'segment': r['segment'],
            'code_residual_m': residual[i], 'phase_residual_m': residual[m+i],
            **({'mw_residual_m':residual[2*m+i]} if combined else {})}
            for i, r in enumerate(block['rows']))
    dof = len(y)-parameter_count-sum(len(b['parameters']) for b in blocks)
    return {'blocks': blocks, 'segments': segments, 'ambiguities_m': ambiguities,
        'phase_drift': phase_drift, 'segment_start_s': start, 'drift_index': drift_index,
        'mw_index':mw_index,'mw_drift_index':mw_drift_index,
        'raw_covariance':raw_covariance,'combination_covariance':endpoint_covariance,
        'ambiguity_covariance': ambiguity_covariance,
        'profiled_ambiguity_inverse': vt.T/singular,
        'profiled_ambiguity_left': u,
        'weighted_cost': cost,
        'residual_dof': dof, 'conditional_p': float(chi2.sf(cost, dof)) if dof > 0 else None,
        'residuals': diagnostics, 'code_sigma_m': float(np.sqrt(endpoint_covariance[0,0])) if combined else code_sigma_m,
        'phase_sigma_m': float(np.sqrt(endpoint_covariance[1,1])) if combined else phase_sigma_m,
        'fixed_reference_clock_datum_epochs': len(blocks),
        'datum': 'zero mean reference-clock error at each epoch; not a physical bound'}


def clock_coefficients(network, requests):
    """Joint estimates/covariance for arbitrary linear receiver-clock contrasts.

    Each request is {(station, time_s): coefficient}. Reusing a clock endpoint
    or a shared ambiguity automatically retains signed cross covariance.
    """
    count, nb = len(requests), len(network['ambiguities_m'])
    estimate, independent, shared = np.zeros(count), np.zeros((count, count)), np.zeros((count, nb))
    remaining = [set(r) for r in requests]
    for block in network['blocks']:
        t, stations = block['time_s'], block['stations']
        transform = np.zeros((count, len(block['parameters'])))
        for i, request in enumerate(requests):
            for j, s in enumerate(stations):
                if (s, t) in request:
                    transform[i, j] = request[s, t]
                    remaining[i].remove((s, t))
        estimate += transform@block['parameters']
        independent += transform@block['conditional_covariance']@transform.T
        shared += transform@block['ambiguity_response']
    if any(remaining):
        raise ValueError('requested receiver clock is not observed by the network')
    covariance = independent+shared@network['ambiguity_covariance']@shared.T
    return estimate, (covariance+covariance.T)/2


def observation_response(network, requests):
    """Derivative of this fixed-weight estimator, including fitted biases.

    Returns one matrix per epoch, with columns in that block's code/phase/MW
    observation order. This transports arbitrary temporal/shared noise; it
    does not refit the estimator with a new covariance or infer noise scales.
    """
    count = len(requests)
    remaining = [set(r) for r in requests]
    transforms, shared = [], np.zeros((count,len(network['ambiguities_m'])))
    for b in network['blocks']:
        t = np.zeros((count,len(b['parameters'])))
        for i,r in enumerate(requests):
            for j,s in enumerate(b['stations']):
                if (s,b['time_s']) in r:
                    t[i,j] = r[s,b['time_s']]
                    remaining[i].remove((s,b['time_s']))
        transforms.append(t)
        shared += t@b['ambiguity_response']
    if any(remaining):
        raise ValueError('requested receiver clock is not observed by the network')
    # Apply the profiled SVD inverse directly. Multiplying C_beta by the
    # profiled design transpose forms inverse-normal-equation products and
    # can create spurious clock response to an exactly orthogonal link cycle.
    shared = shared@network['profiled_ambiguity_inverse']
    output = []
    at = 0
    for b,t in zip(network['blocks'],transforms,strict=True):
        project = np.eye(len(b['y']))-b['a']@b['gain']
        whiten = (lambda x:solve_triangular(b['chol'],x,lower=True)) if b['chol'] is not None else (
            lambda x:x/b['sigma'][:,None])
        stop = at+len(b['y'])
        output.append(t@b['gain']+shared@network['profiled_ambiguity_left'][at:stop].T@whiten(project))
        at = stop
    return output
