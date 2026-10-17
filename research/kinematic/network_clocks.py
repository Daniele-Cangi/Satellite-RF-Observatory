"""Code/phase network clocks with free reference clocks and float link biases.

Every epoch has its own receiver and reference-clock values. Reference errors
sum to zero only to choose a datum: a common epoch clock error is unobservable.
Code and phase share clocks, but each admitted continuous link segment has an
unpenalized phase/code ambiguity. Supplied endpoint sigmas are weighting
assumptions, never a physical covariance inferred from small residuals.
"""
from collections import defaultdict

import numpy as np
from scipy.linalg import helmert
from scipy.stats import chi2

from .calibration_transfer import operators


def fit(rows, *, code_sigma_m=20., phase_sigma_m=.02, phase_drift=False):
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
    segments = sorted({r['segment'] for r in rows})
    segment_index = {s: i for i, s in enumerate(segments)}
    start = {s: min(r['time_s'] for r in rows if r['segment']==s) for s in segments}
    drifting = [s for s in segments if phase_drift and any(
        r['segment']==s and r['time_s']!=start[s] for r in rows)]
    drift_index = {s: len(segments)+i for i,s in enumerate(drifting)}
    parameter_count = len(segments)+len(drifting)
    grouped = defaultdict(list)
    for r in rows:
        if not np.isfinite([r['code_m'], r['phase_m'], r.get('clock_derivative', 1.)]).all():
            raise ValueError('finite network observations required')
        grouped[r['time_s']].append(r)
    blocks, reduced, values = [], [], []
    for time, own in sorted(grouped.items()):
        stations = sorted({r['station'] for r in own})
        refs = sorted({r['reference'] for r in own})
        if len(stations) < 2 or len(refs) < 2:
            raise ValueError(f'network lacks a station/reference contrast at {time}')
        datum = helmert(len(refs), full=False).T
        m, n = len(own), len(stations)
        a = np.zeros((2*m, n+len(refs)-1))
        b = np.zeros((2*m, parameter_count))
        for i, r in enumerate(own):
            a[i, stations.index(r['station'])] = r.get('clock_derivative', 1.)
            a[i, n:] = -datum[refs.index(r['reference'])]
            a[m+i] = a[i]
            b[m+i, segment_index[r['segment']]] = 1.
            if r['segment'] in drift_index:
                b[m+i, drift_index[r['segment']]] = (time-start[r['segment']])/3600.
        y = np.array([r['code_m'] for r in own]+[r['phase_m'] for r in own])
        sigma = np.r_[np.full(m, code_sigma_m), np.full(m, phase_sigma_m)]
        # A disconnected bipartite graph has extra unobservable station
        # contrasts. Do not repair it by anchoring an arbitrary receiver.
        op = operators(a, a, np.diag(sigma**2))
        gain, project = op['gain'], op['reference_residual']
        reduced.append((project@b)/sigma[:, None])
        values.append((project@y)/sigma)
        blocks.append({'time_s': time, 'stations': stations, 'references': refs,
            'reference_basis': datum, 'rows': own, 'a': a, 'b': b, 'y': y,
            'sigma': sigma, 'gain': gain, 'conditional_covariance':
            (gain*sigma)@(gain*sigma).T, 'ambiguity_response': -gain@b})
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
        cost += float((residual/block['sigma'])@(residual/block['sigma']))
        m = len(block['rows'])
        diagnostics.extend({'time_s': block['time_s'], 'station': r['station'],
            'reference': r['reference'], 'segment': r['segment'],
            'code_residual_m': residual[i], 'phase_residual_m': residual[m+i]}
            for i, r in enumerate(block['rows']))
    dof = len(y)-parameter_count-sum(len(b['parameters']) for b in blocks)
    return {'blocks': blocks, 'segments': segments, 'ambiguities_m': ambiguities,
        'phase_drift': phase_drift, 'segment_start_s': start, 'drift_index': drift_index,
        'ambiguity_covariance': ambiguity_covariance, 'weighted_cost': cost,
        'residual_dof': dof, 'conditional_p': float(chi2.sf(cost, dof)) if dof > 0 else None,
        'residuals': diagnostics, 'code_sigma_m': code_sigma_m,
        'phase_sigma_m': phase_sigma_m,
        'unobservable_common_clock_modes': len(blocks),
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
