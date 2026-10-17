"""Nondispersive network closures and their complete calibration/state response.

Metre perturbations affect IF code and IF phase equally, leaving D/GF/MW
unchanged. Reference geometry, masks and observation-time linearization are
conditional. Measured closure scatter is never substituted for a raw floor.
"""
from collections import Counter
import hashlib

import numpy as np

from . import calibration_transfer, network_clocks, phase_continuity, temporal_contrasts, source_geometry

PROBE_RMS_M = .01  # coherent finite-difference amplitude, NOT a noise sigma
LAGS = (30., 300.)


def admit(rows, candidate):
    if any(r['reference'] == candidate for r in rows):
        raise ValueError('candidate in its own nondispersive reference network')
    if not rows:
        raise ValueError('nonempty admitted reference network required')


def clock_basis(block):
    m = len(block['rows'])
    a = block['a'][:m]
    # Reuse the existing residual-blind-subspace primitive, with raw link
    # metres as the Euclidean input coordinates. The datum is unchanged.
    return calibration_transfer.residual_blind_modes(a, np.zeros((1, m)))['reference_error_basis']


def closure_records(network, candidate):
    rows = [r for b in network['blocks'] for r in b['rows']]
    admit(rows, candidate)
    records, ranks = [], []
    for b in network['blocks']:
        m = len(b['rows'])
        q = clock_basis(b)
        residual = b['y']-b['a'] @ b['parameters']-b['b'] @ network['ambiguities_m']
        values = residual[:2*m].reshape(2, m).T
        cycle = values-q @ (q.T @ values)
        ranks.append({'time_s': b['time_s'], 'link_count': m, 'clock_rank': q.shape[1],
                      'cycle_rank': m-q.shape[1]})
        records.extend({k:r[k] for k in ('station', 'reference', 'time_s', 'segment')}
            | {'code_closure_m': v[0], 'phase_closure_m': v[1]}
            for r,v in zip(b['rows'], cycle, strict=True))
    translated = [{**r, 'code_m': r['code_closure_m'], 'phase_m': 0., 'mw_m': r['phase_closure_m']}
                  for r in records]
    variograms = temporal_contrasts.variograms(translated,
        min(r['time_s'] for r in records), max(r['time_s'] for r in records))
    return {'status': 'CONDITIONAL_CALIBRATED_CLOSURES', 'rows': records, 'epoch_ranks': ranks,
        'code_phase_variograms': [r for r in variograms if r['lag_s'] in LAGS],
        'float_biases_fitted_on_full_reference_window': True,
        'physical_nondispersive_covariance_qualified': False}


def prepare_future_links(rows, candidate, raw_covariance, *, wet_sources=False, source_families=None):
    """Remove fixed links in the last third before GF/ambiguity/clock fitting.

    Predictions use other links at the excluded epoch, not a clock forecast.
    Held-out GF never selects a segment. Constant prefix ambiguity is only a
    declared continuity hypothesis; increments do not require its level.
    """
    admit(rows, candidate)
    if wet_sources and source_families is not None:
        raise ValueError('select one source model')
    cut = min(r['time_s'] for r in rows)+2*(max(r['time_s'] for r in rows)-min(r['time_s'] for r in rows))/3
    links = sorted({(r['station'], r['reference']) for r in rows})
    selected = [k for k in links if int.from_bytes(hashlib.sha256(('/'.join(k)).encode('ascii')).digest()[:8], 'big') % 7 == 0]
    held = [r for r in rows if (r['station'],r['reference']) in selected and r['time_s'] > cut]
    training = [r for r in rows if not ((r['station'],r['reference']) in selected and r['time_s'] > cut)]
    # base_segment strips any previous full-data GF assessment before replay.
    training = phase_continuity.segment(training)
    output = {'training_stop_s': cut, 'held_links': selected,
        'training_row_count': len(training), 'withheld_row_count': len(held),
        'segmentation_uses_withheld_phase': False, 'predictions': [],
        'conditional_on_original_timing_and_reference_masks': True}
    try:
        fitted = network_clocks.fit(training, raw_covariance=raw_covariance)
        if source_families is not None:
            source,workspace=source_geometry.profile_sources(fitted,candidate,source_families)
            output['source_model']=source
        if wet_sources:
            source = source_geometry.profile_wet(fitted,candidate)
            output['source_model'] = source
            if source['status']!='CONDITIONAL_SOURCE_FIT':
                return {**output,'status':'HELD_OUT_SOURCE_UNOBSERVABLE'}
            coefficients = source['zenith_wet_correction_m']
            corrected = [{**r,'code_m':r['code_m']-r['wet_mapping']*coefficients[r['station']],
                'phase_m':r['phase_m']-r['wet_mapping']*coefficients[r['station']]} for r in training]
            fitted = network_clocks.fit(corrected,raw_covariance=raw_covariance)
    except (ValueError, np.linalg.LinAlgError) as error:
        return {**output, 'status': 'HELD_OUT_NETWORK_FAILED', 'reason': str(error)}
    blocks = {b['time_s']: b for b in fitted['blocks']}
    prefix = {}
    for r in training:
        if r['time_s'] <= cut:
            prefix[r['station'],r['reference'],r.get('base_segment',r['segment'])] = r
    for r in held:
        base = r.get('base_segment', r['segment'])
        item = {k:r[k] for k in ('station','reference','time_s')}
        item['base_segment'] = base
        if source_families is not None:
            last=prefix.get((r['station'],r['reference'],base))
            prediction=source_geometry.source_link_prediction(fitted,workspace,r,None if last is None else last['segment'])
            output['predictions'].append({**item,**prediction,'continuity_after_prefix_observed':False})
            continue
        try:
            b = blocks[r['time_s']]
            i,j = b['stations'].index(r['station']), b['references'].index(r['reference'])
            predicted = r.get('clock_derivative',1.)*b['parameters'][i]-b['reference_basis'][j] @ b['parameters'][len(b['stations']):]
        except (KeyError, ValueError):
            output['predictions'].append({**item, 'status': 'UNOBSERVED_NETWORK_CLOCK'})
            continue
        item.update(status='PREDICTED', clock_prediction_m=float(predicted), phase_prediction_m=None,
                    continuity_after_prefix_observed=False)
        if wet_sources:
            item['wet_prediction_m'] = float(r['wet_mapping']*coefficients[r['station']])
            predicted += item['wet_prediction_m']
            item['path_prediction_m'] = float(predicted)
        last = prefix.get((r['station'],r['reference'],base))
        if last is not None:
            segment = last['segment']
            item.update(prefix_segment=segment, prefix_last_time_s=last['time_s'],
                phase_prediction_m=float(predicted+fitted['ambiguities_m'][fitted['segments'].index(segment)]))
        output['predictions'].append(item)
    return {**output, 'status': 'FUTURE_LINK_PREDICTIONS_FROZEN',
        'prediction_status_counts': dict(Counter(r['status'] for r in output['predictions']))}


def score_future_links(prepared, rows):
    if prepared['status'] != 'FUTURE_LINK_PREDICTIONS_FROZEN':
        return prepared
    index = {(r['station'],r['reference'],r['time_s']):r for r in rows}
    errors, levels = [], []
    for p in prepared['predictions']:
        if p['status'] != 'PREDICTED':
            continue
        r = index[p['station'],p['reference'],p['time_s']]
        predicted = p.get('path_prediction_m',p['clock_prediction_m'])
        errors.append({**p, 'segment':p['base_segment'],
            'code_m': r['code_m']-predicted, 'phase_m': 0.,
            'mw_m': r['phase_m']-p.get('phase_path_prediction_m',predicted)})
        levels.append({**p, 'code_error_m': r['code_m']-predicted,
            'phase_error_m': None if p['phase_prediction_m'] is None else r['phase_m']-p['phase_prediction_m']})
    results = []
    if errors:
        start, stop = min(r['time_s'] for r in errors), max(r['time_s'] for r in errors)
        for lag in LAGS:
            pairs = temporal_contrasts.increments(errors, start, stop, lag)
            z = np.array([r['z'] for r in pairs])
            results.append({'lag_s': lag, 'count': len(z), 'rows': pairs,
                'code_phase_mean_error_m': z.mean(0) if len(z) else None,
                'code_phase_rms_error_m': np.sqrt(np.mean(z*z,axis=0)) if len(z) else None,
                'code_phase_mean_outer_product_m2': z.T @ z/len(z) if len(z) else None})
    return {**prepared, 'status': 'CONDITIONAL_FUTURE_LINK_EVALUATED', 'level_errors': levels,
        'increment_errors': results, 'whole_network_future_prediction': 'UNIDENTIFIABLE_FREE_EPOCH_CLOCKS',
        'physical_covariance_qualified': False}


def state_transfer(network, requests, candidate, state_response, clock_indices):
    rows = [r for b in network['blocks'] for r in b['rows']]
    admit(rows, candidate)
    response = network_clocks.observation_response(network, requests)
    nondispersive = np.column_stack([r[:,:len(b['rows'])]+r[:,len(b['rows']):2*len(b['rows'])]
        for b,r in zip(network['blocks'],response,strict=True)])
    transfer = np.asarray(state_response)[:6,clock_indices] @ nondispersive
    blind = np.empty_like(transfer)
    at = 0
    for b in network['blocks']:
        m = len(b['rows']); q = clock_basis(b)
        blind[:,at:at+m] = (transfer[:,at:at+m] @ q) @ q.T
        at += m
    visible = transfer-blind
    count = len(rows)
    modes = {}
    total_position_gain = np.linalg.svd(transfer[:3],compute_uv=False)[0]
    for name, t in (('clock_blind',blind), ('cycle_visible',visible)):
        _, singular, vt = np.linalg.svd(t[:3], full_matrices=False)
        gain = np.sqrt(count)*singular[0]
        velocity_gain = np.sqrt(count)*np.linalg.svd(t[3:6],compute_uv=False)[0]*1000.
        energy = float(np.sum(t[:3]**2)/np.sum(transfer[:3]**2)) if np.sum(transfer[:3]**2) else 0.
        if singular[0] <= 1e-10*total_position_gain:
            modes[name] = {'status': 'NO_RESOLVED_POSITION_PROBE',
                'maximum_position_gain_m_per_m_reference_rms': gain,
                'maximum_velocity_gain_mm_s_per_m_reference_rms': velocity_gain,
                'position_response_energy_fraction': energy}
            continue
        probe = vt[0].copy()
        at = 0
        for b in network['blocks']:
            m = len(b['rows']); q = clock_basis(b)
            projected = q @ (q.T @ probe[at:at+m])
            probe[at:at+m] = projected if name == 'clock_blind' else probe[at:at+m]-projected
            at += m
        norm = np.linalg.norm(probe)
        if norm <= 1e-8:
            modes[name] = {'status': 'NO_RESOLVED_POSITION_PROBE',
                'maximum_position_gain_m_per_m_reference_rms': gain,
                'maximum_velocity_gain_mm_s_per_m_reference_rms': velocity_gain,
                'position_response_energy_fraction': energy}
            continue
        probe *= PROBE_RMS_M*np.sqrt(count)/norm
        modes[name] = {'status':'PROBE_PREPARED', 'reference_change_m': probe, 'linear_state_change_m_m_s': transfer @ probe,
            'reference_rms_m': float(np.sqrt(np.mean(probe**2))), 'reference_peak_m': float(max(abs(probe))),
            'maximum_position_gain_m_per_m_reference_rms': gain,
            'maximum_velocity_gain_mm_s_per_m_reference_rms': velocity_gain,
            'coherent_reference_rms_m_for_1m_position': 1/gain if gain > 0 else None,
            'coherent_reference_rms_m_for_1mm_s_velocity': 1/velocity_gain if velocity_gain > 0 else None,
            'position_response_energy_fraction': energy}
    return {'status': 'CONDITIONAL_REFERENCE_ONLY_ERROR_RESPONSE', 'modes': modes,
        'reference_row_keys': [[r[k] for k in ('station','reference','time_s')] for r in rows],
        'response_orthogonality_max': float(np.max(abs(blind @ visible.T))),
        'response_partition_identity_max': float(np.max(abs(transfer @ transfer.T-blind @ blind.T-visible @ visible.T))),
        'reference_only_target_coupling': 'Candidate RF is unperturbed; a shared physical receiver-clock disturbance requires its matching candidate response and can cancel.',
        'reference_rms_is_coherent_sensitivity_amplitude_not_sigma': True,
        'position_response_rank_rtol': 1e-10,
        'physical_covariance_qualified': False}
