"""Exploratory shared residual state, not a physical source/clock estimator.

Transfers MissNet's observed-coordinate update, not its EM/clustering machinery:
https://github.com/eXascaleInfolab/ImputeGAP/blob/a18d5c5f619d05dced8348619150b4a06e138f8d/imputegap/wrapper/AlgoPython/MissNet/main.py#L195-L217
One fixed rank-one model is fitted on prefix residuals. Historical network
weights, source null tests and production calibration are never modified.
"""
from collections import Counter

import numpy as np

from . import network_closures, network_clocks, phase_continuity, source_geometry


def fit_prefix(values, times):
    """Rank-one observed-entry ALS (20 steps), then prefix-only AR(1) moments.

    NaNs mean missing observations, not zero physical values. The zero-filled
    SVD is only an initialization for the observed-entry objective. Learned
    variances describe this predictive residual model, not RF uncertainty.
    """
    x = np.asarray(values, dtype=float)
    t = np.asarray(times, dtype=float)
    if (x.ndim != 2 or len(x) != len(t) or len(t) < 8 or x.shape[1] < 2
            or not np.isfinite(t).all() or np.any(np.diff(t) <= 0)
            or np.isinf(x).any()):
        raise ValueError('ordered finite times and sufficient prefix matrix required')
    mask = np.isfinite(x)
    if np.any(mask.sum(0) < 8) or np.any(mask.sum(1) < 2):
        raise ValueError('insufficient observed prefix coordinates')
    mean = np.nanmean(x, axis=0)
    y = np.where(mask, x - mean, 0.)
    u, s, _ = np.linalg.svd(y, full_matrices=False)
    state = u[:, 0] * s[0]
    if np.var(state) <= np.finfo(float).eps:
        raise ValueError('no resolved predictive residual mode')
    for _ in range(20):
        denominator = (mask * state[:, None] ** 2).sum(0)
        loading = (y * state[:, None]).sum(0) / np.maximum(denominator, 1e-30)
        denominator = (mask * loading ** 2).sum(1)
        state = (y * loading).sum(1) / np.maximum(denominator, 1e-30)
    scale = np.std(state)
    if scale <= np.finfo(float).eps:
        raise ValueError('unresolved latent scale')
    state, loading = state / scale, loading * scale
    consecutive = np.isclose(np.diff(t), 30., rtol=0., atol=1e-6)
    if np.count_nonzero(consecutive) < 4:
        raise ValueError('insufficient adjacent prefix epochs')
    a, b = state[:-1][consecutive], state[1:][consecutive]
    rho = float(np.clip(a @ b / max(float(a @ a), 1e-30), -.98, .98))
    process = max(float(np.mean((b - rho * a) ** 2)), 1e-6)
    error = np.where(mask, y - state[:, None] * loading, 0.)
    variance = (error ** 2).sum(0) / mask.sum(0)
    # Numerical positivity in a learned residual model, never a raw RF floor.
    variance = np.maximum(variance, np.nanvar(x, axis=0) * 1e-6 + 1e-18)
    return {'mean_m': mean, 'loading_m': loading, 'rho_30s': rho,
            'process_variance': process, 'observation_variance_m2': variance,
            'rank': 1, 'als_steps': 20, 'prefix_epochs': len(t)}


def filter_states(model, values, times, *, whole_row=False):
    """Causal scalar-state Gaussian update from available coordinates only.

    whole_row is a fixed ablation: discard an epoch with any missing channel,
    as in the inspected PyKalman standard correction. Parameters are identical.
    Gaps beyond 60 s reset the predictive state; no backward smoother is used.
    """
    x = np.asarray(values, dtype=float)
    t = np.asarray(times, dtype=float)
    loading = np.asarray(model['loading_m'])
    if (x.shape != (len(t), len(loading)) or not np.isfinite(t).all()
            or np.any(np.diff(t) <= 0) or np.isinf(x).any()
            or np.any(~np.isclose(np.diff(t) / 30., np.round(np.diff(t) / 30.)))):
        raise ValueError('ordered times and matching residual coordinates required')
    rho, q = model['rho_30s'], model['process_variance']
    stationary = q / (1. - rho ** 2)
    state, variance = 0., stationary
    states, counts = [], []
    for i, time in enumerate(t):
        if i and time - t[i - 1] > 60.:
            state, variance = 0., stationary
        elif i:
            power = rho ** int(round((time - t[i - 1]) / 30.))
            state, variance = power * state, power ** 2 * variance + stationary * (1 - power ** 2)
        observed = np.isfinite(x[i])
        if whole_row and not observed.all():
            observed[:] = False
        h = loading[observed]
        r = np.asarray(model['observation_variance_m2'])[observed]
        y = x[i, observed] - np.asarray(model['mean_m'])[observed]
        precision = 1. / variance + np.sum(h ** 2 / r)
        state = float((state / variance + np.sum(h * y / r)) / precision)
        variance = float(1. / precision)
        states.append(state)
        counts.append(int(observed.sum()))
    return np.asarray(states), counts


def prepare_future_links(rows, candidate, raw_covariance):
    """Keep native wet predictions; fit one masked phase-residual correction.

    The original hash/last-third exclusion precedes numeric RF access. Prefix
    parameters use only residuals on the final prefix continuity segment of
    each link. Later admitted channels can update the latent state only while
    that same segment continues. Held GF/phase/code/MW never enter the model.
    The underlying native calibration remains conditional on ALL admitted rows.
    """
    network_closures.admit(rows, candidate)
    baseline = network_closures.prepare_future_links(rows, candidate, raw_covariance,
                                                     source_families=('wet',))
    if baseline['status'] != 'FUTURE_LINK_PREDICTIONS_FROZEN':
        return {'baseline': baseline, 'model_status': 'BASELINE_FAILED'}
    cut, selected = baseline['training_stop_s'], set(map(tuple, baseline['held_links']))
    admitted = [r for r in rows if not (
        (r['station'], r['reference']) in selected and r['time_s'] > cut)]
    training = phase_continuity.segment(admitted)
    network = network_clocks.fit(training, raw_covariance=raw_covariance)
    _, workspace = source_geometry.profile_sources(network, candidate, ('wet',))
    prefix = {}
    for r in training:
        if r['time_s'] <= cut:
            prefix[r['station'], r['reference']] = r['segment']
    channels = sorted(prefix)
    times = sorted({r['time_s'] for r in training})
    time_index, channel_index = {v:i for i,v in enumerate(times)}, {v:i for i,v in enumerate(channels)}
    matrix = np.full((len(times), len(channels)), np.nan)
    for row in training:
        key = row['station'], row['reference']
        if row['segment'] != prefix.get(key):
            continue
        prediction = source_geometry.source_link_prediction(network, workspace, row, row['segment'])
        if prediction['status'] == 'PREDICTED':
            matrix[time_index[row['time_s']], channel_index[key]] = (
                row['phase_m'] - prediction['phase_path_prediction_m'])
    prefix_mask = np.asarray(times) <= cut
    eligible = np.isfinite(matrix[prefix_mask]).sum(0) >= 8
    active = [key for key, use in zip(channels, eligible, strict=True) if use]
    matrix = matrix[:, eligible]
    output = {'baseline': baseline, 'channels': active,
              'parameter_fit_uses_held_measurements': False,
              'physical_covariance_qualified': False, 'production_calibration_changed': False}
    try:
        model = fit_prefix(matrix[prefix_mask], np.asarray(times)[prefix_mask])
    except ValueError as error:
        unavailable = dict(baseline, predictions=[dict(p, status='UNSUPPORTED_PREFIX_MODEL')
            if p['status'] == 'PREDICTED' else dict(p) for p in baseline['predictions']])
        unavailable['prediction_status_counts'] = dict(Counter(p['status'] for p in unavailable['predictions']))
        return {**output, 'model_status': 'UNSUPPORTED_PREFIX_MODEL', 'reason': str(error),
                'variants':{label:unavailable for label in ('observed_coordinates', 'whole_row_ablation')}}
    output.update(model_status='PREDICTIVE_RESIDUAL_MODEL', model=model, variants={})
    for label, whole_row in [('observed_coordinates', False), ('whole_row_ablation', True)]:
        states, counts = filter_states(model, matrix, times, whole_row=whole_row)
        result = dict(baseline, predictions=[])
        for original in baseline['predictions']:
            item = dict(original)
            key = item['station'], item['reference']
            if item['status'] == 'PREDICTED':
                if key not in active or item['time_s'] not in time_index:
                    item.update(status='UNSUPPORTED_RESIDUAL_COORDINATE')
                else:
                    j, i = active.index(key), time_index[item['time_s']]
                    correction = float(model['mean_m'][j] + model['loading_m'][j] * states[i])
                    item['phase_path_prediction_m'] += correction
                    item['phase_prediction_m'] += correction
                    item['residual_correction_m'] = correction
            result['predictions'].append(item)
        result['prediction_status_counts'] = dict(Counter(p['status'] for p in result['predictions']))
        output['variants'][label] = result
        output[label + '_observed_counts'] = counts
    return output
