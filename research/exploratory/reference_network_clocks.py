"""Exposed reference-only code/phase network calibration and RF refits.

Same 22 candidates and nominal preparation as reference-state v3. References
up to the last training endpoint calibrate a network; no candidate products,
RF or previous state enter its own network. This is conditional development,
not independent clock precision, an absolute datum, or a total error budget.
"""
import argparse
from collections import Counter
from datetime import datetime
import gzip
import inspect
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag

from . import reference_state_validation as baseline, reference_wet_fit as wet, reference_geometry
from ..kinematic import dynamic_fit, network_clocks, phase_continuity, gnss_combinations, temporal_contrasts, shared_rf_covariance, shared_error_structure, network_closures, source_geometry
from ..kinematic.synthetic import native


def reference_rows(data, candidate, stop, weather, centres=None, *, continuity=False, combinations=False,
                   source_geometry=False, zenith_wet_m=None, reference_sources=False, source_probe=None):
    """Identity/time filtering precedes numeric product and RF arithmetic.

    Phase/code bias is free per flag/gap/mask-contiguous segment. The optional
    GF witness splits a segment without repairing any observed phase value.
    """
    refs = [q for q in data['plan']['references'] if q != candidate]
    provider, corrections = baseline.subset_products(data, refs, candidate)
    if source_probe is not None:
        provider=reference_geometry.physical_source_provider(provider,candidate,source_probe)
        if zenith_wet_m is not None:raise ValueError('one wet source correction per intervention')
        zenith_wet_m=source_probe.get('wet',{})
    centres = {} if centres is None else centres
    codes = {s: {e['time_s']: {q: v for q, v in e['if_code_m'].items() if q in refs}
                 for e in epochs if e['time_s'] <= stop}
             for s, epochs in data['observations'].items()}
    mjd = (datetime.fromisoformat(data['plan']['date_gpst'])-datetime(1858, 11, 17)).days
    output, failures, previous, segments = [], Counter(), {}, Counter()
    for station, item in data['phase']['stations'].items():
        for row in item['rows']:
            q, t = row['reference'], row['time_s']
            if q not in refs or t > stop:
                continue
            key = station, q
            if row['status'] != 'AVAILABLE':
                failures['UNAVAILABLE_PHASE'] += 1
                continue
            xyz = np.asarray(data['positions'][station][int((t-36000)/30)], float)
            try:
                local_weather = weather if zenith_wet_m is None else wet.ShiftedWetWeather(weather,zenith_wet_m.get(station,0.))
                hardware_bias=(float(source_probe.get('bias',{}).get(station+'/'+q,0.)) if source_probe is not None else 0.)
                code = float(codes[station][t][q])+corrections[t, q]['if_code_change_m']-hardware_bias
                if provider.model(q, code, t, xyz, 0.)[1] < 10.:
                    failures['BELOW_MASK'] += 1
                    continue
                centre = centres.get((station, t), 0.)
                def model(clock):
                    value, _ = provider.model(q, code, t, xyz, clock)
                    delay, _ = baseline.day.atmosphere.components(provider, local_weather, mjd, q, code, t, xyz, clock)
                    return value-delay['legacy_baseline']+delay['vmf3_full']
                value = model(centre)
                derivative = (model(centre+1.)-model(centre-1.))/2.
                if previous.get(key) != t-30:
                    segments[key] += 1
                previous[key] = t
                record = {'station': station, 'reference': q, 'time_s': t,
                    'segment': f'{station}/{q}/{segments[key]}',
                    'code_m': code-value+derivative*centre,
                    'phase_m': float(row['phase_m'])-value+derivative*centre,
                    'clock_derivative': 1.+derivative,
                    'geometry_free_phase_m': float(row['geometry_free_phase_m'])}
                if source_geometry:
                    _,geometry = baseline.day.atmosphere.components(provider,local_weather,mjd,q,code,t,xyz,centre)
                    record.update(wet_mapping=geometry['mfw'],zenith_wet_m=geometry['zwd_m'],
                        elevation_deg=geometry['elevation_deg'],source_geometry_mjd_utc=geometry['mjd_utc'])
                if reference_sources:
                    record.update(native(reference_geometry.emitted_source_mappings(provider,local_weather,mjd,q,code,t,xyz,centre)))
                if combinations:
                    raw = gnss_combinations.values(row['fields'],code1_change_m=
                        (corrections[t,q]['if_code_change_m']-hardware_bias)/gnss_combinations.ALPHA)
                    if abs(raw[0]-code)>1e-5:
                        raise ValueError('raw/day IF code mismatch')
                    record['mw_m'] = raw[3]
                output.append(record)
            except (KeyError, ValueError) as error:
                failures[type(error).__name__+': '+str(error)] += 1
    return phase_continuity.segment(output) if continuity else output, dict(failures)


def calibrate(data, candidate, arcs, weather, *, phase_drift=False, centres=None, continuity=False, raw_covariance=None,
              source_geometry=False, zenith_wet_m=None, reference_sources=False, source_probe=None):
    stop = max(a['endpoint_gpst_s'] for a in arcs)
    centres, iterations = ({} if centres is None else centres), []
    for iteration in range(4):
        rows, failures = reference_rows(data, candidate, stop, weather, centres,
            continuity=continuity,combinations=raw_covariance is not None,
            **({'source_geometry':source_geometry,'zenith_wet_m':zenith_wet_m,'reference_sources':reference_sources,'source_probe':source_probe}
               if source_geometry or zenith_wet_m is not None or reference_sources or source_probe is not None else {}))
        network = network_clocks.fit(rows,phase_drift=phase_drift,raw_covariance=raw_covariance)
        updated = {(s, b['time_s']): b['parameters'][i]
                   for b in network['blocks'] for i, s in enumerate(b['stations'])}
        change = max(abs(v-centres.get(k, 0.)) for k, v in updated.items())
        iterations.append({'iteration': iteration, 'maximum_clock_change_m': change})
        print(candidate,'network drift='+str(phase_drift),'GF='+str(continuity),iterations[-1],flush=True)
        if change < 1e-5:
            break
        centres = updated
    else:
        raise ValueError('network observation-time recalibration did not converge')
    return network, rows, {'last_reference_training_gpst_s': stop,
        'row_count': len(rows), 'failures': failures, 'iterations': iterations,
        'station_count': len({r['station'] for r in rows}),
        'reference_count': len({r['reference'] for r in rows}),
        'segment_count': len(network['segments']),
        'phase_drift': phase_drift, 'geometry_free_segmentation': continuity,
        **({'continuity_witnesses': [
            {k:r[k] for k in ('station','reference','time_s','base_segment','segment','continuity')}
            for r in rows if r['continuity']['break']],
            'continuity_method_counts':dict(Counter(r['continuity']['method'] for r in rows))}
            if continuity else {}),
        'drift_coefficients_m_per_hour': {
            s: network['ambiguities_m'][j] for s,j in network['drift_index'].items()},
        'conditional_p': network['conditional_p'], 'weighted_cost': network['weighted_cost'],
        'residual_dof': network['residual_dof'],
        'status': 'CONDITIONAL_MODEL_REJECTED' if network['conditional_p'] < .01 else 'CONDITIONAL_MODEL_ONLY',
        'datum': network['datum'], 'fixed_reference_clock_datum_epochs': network['fixed_reference_clock_datum_epochs'],
        'receiver_clocks_m': [{'time_s': b['time_s'], 'stations': b['stations'],
            'values': b['parameters'][:len(b['stations'])], 'references': b['references'],
            'reference_error_m': b['reference_basis']@b['parameters'][len(b['stations']):]}
            for b in network['blocks']],
        'segments': network['segments'], 'ambiguities_m': network['ambiguities_m'],
        **({'raw_endpoint_covariance_m2':raw_covariance,
            'retained_combination_covariance_m2':network['combination_covariance'],
            'mw_float_bias_m':{s:network['ambiguities_m'][i] for s,i in network['mw_index'].items()},
            'mw_drift_m_per_hour':{s:network['ambiguities_m'][i] for s,i in network['mw_drift_index'].items()},
            'gf_model':'free link-epoch ionosphere; GF profiled out, not conditioned on as exact'}
            if raw_covariance is not None else {}),
        'residuals': network['residuals']}


def held_out_links(rows, *, phase_drift=False, continuity=False, raw_covariance=None):
    """Deterministic link-epoch withholding, never a source of tuned weights.

    Withholding an entire epoch cannot be predicted by free epoch clocks;
    report that structural failure instead of silently adding a time prior.
    """
    training = [r for i,r in enumerate(rows) if i%7]
    withheld = [r for i,r in enumerate(rows) if not i%7]
    if continuity:
        # Rebuild using only retained RF. Using the excluded phase's own GF
        # to select its ambiguity would leak it into the prediction/support.
        training = phase_continuity.segment(training)
    try:
        network = network_clocks.fit(training,phase_drift=phase_drift,raw_covariance=raw_covariance)
    except (ValueError,np.linalg.LinAlgError) as error:
        return {'status':'HELD_OUT_NETWORK_FAILED','reason':str(error),'withheld_count':len(withheld)}
    blocks = {b['time_s']:b for b in network['blocks']}
    segments = {s:i for i,s in enumerate(network['segments'])}
    records = []
    for r in withheld:
        record = {k:r[k] for k in ('time_s','station','reference','segment')}
        segment = phase_continuity.withheld_segment(r,training) if continuity else r['segment']
        record['predicted_segment'] = segment
        if raw_covariance is not None:
            if segment is None or segment not in network['mw_index']:
                record['mw_status'] = 'UNOBSERVED_SEGMENT'
            elif phase_drift and segment not in network['mw_drift_index']:
                record['mw_status'] = 'UNIDENTIFIABLE_MW_DRIFT'
            else:
                mw = network['ambiguities_m'][network['mw_index'][segment]]
                if segment in network['mw_drift_index']:
                    mw += network['ambiguities_m'][network['mw_drift_index'][segment]]*(
                        r['time_s']-network['segment_start_s'][segment])/3600.
                record.update(mw_status='EVALUATED',mw_error_m=r['mw_m']-mw)
        try:
            b = blocks[r['time_s']]
            i,j = b['stations'].index(r['station']),b['references'].index(r['reference'])
            clocks = b['parameters']
            predicted = r.get('clock_derivative',1.)*clocks[i]-b['reference_basis'][j]@clocks[len(b['stations']):]
        except (KeyError,ValueError):
            record.update(status='PARTIALLY_EVALUATED' if record.get('mw_status')=='EVALUATED' else 'UNOBSERVED_CLOCK_OR_SEGMENT',
                code_status='UNOBSERVED_CLOCK',phase_status='UNOBSERVED_CLOCK')
            records.append(record)
            continue
        # Code requires only the receiver/reference clocks. A missing phase
        # ambiguity or slope must not discard this supported observation.
        record.update(code_status='EVALUATED',code_error_m=r['code_m']-predicted)
        if segment is None:
            record.update(status='PARTIALLY_EVALUATED',phase_status='UNOBSERVED_CONTINUITY_SEGMENT')
        elif segment not in segments:
            record.update(status='PARTIALLY_EVALUATED',phase_status='UNOBSERVED_SEGMENT')
        elif phase_drift and segment not in network['drift_index']:
            record.update(status='PARTIALLY_EVALUATED',phase_status='UNIDENTIFIABLE_PHASE_DRIFT')
        else:
            ambiguity = network['ambiguities_m'][segments[segment]]
            if segment in network['drift_index']:
                ambiguity += network['ambiguities_m'][network['drift_index'][segment]]*(
                    r['time_s']-network['segment_start_s'][segment])/3600.
            record.update(status='EVALUATED',phase_status='EVALUATED',
                phase_error_m=r['phase_m']-predicted-ambiguity)
        if raw_covariance is not None and record['mw_status']!='EVALUATED' and record['status']=='EVALUATED':
            record['status'] = 'PARTIALLY_EVALUATED'
        records.append(record)
    return {'status':'RELATIVE_SHARED_PRODUCT_DIAGNOSTIC','rows':records,
        'status_counts':dict(Counter(r['status'] for r in records)),
        'code_status_counts':dict(Counter(r['code_status'] for r in records)),
        'phase_status_counts':dict(Counter(r['phase_status'] for r in records)),
        'code_error_m':baseline.interval.diagnostic.moments([r['code_error_m'] for r in records if r['code_status']=='EVALUATED']),
        'phase_error_m':baseline.interval.diagnostic.moments([r['phase_error_m'] for r in records if r['phase_status']=='EVALUATED']),
        **({'mw_status_counts':dict(Counter(r['mw_status'] for r in records)),
            'mw_error_m':baseline.interval.diagnostic.moments([r['mw_error_m'] for r in records if r['mw_status']=='EVALUATED']),
            'gf_prediction':'UNIDENTIFIABLE_WITH_FREE_LINK_EPOCH_IONOSPHERE'} if raw_covariance is not None else {}),
        'whole_time_block_prediction':'UNIDENTIFIABLE_WITH_FREE_EPOCH_CLOCKS',
        'segmentation_uses_withheld_phase':False,
        'future_clock_rule':'retain the fitted arc mean; no network future data or quadratic extrapolation'}


def held_out_support_correction(result, original_sha256, superseded_correction_sha256=None):
    """Invalidate singleton drift extrapolations in the immutable v1 receipt.

    Structural correction only: do not recompute or alter clocks, trajectories,
    covariance, candidate RF predictions, or CODE scores. No new fit or tuning.
    """
    candidates = {}
    for candidate, record in result['candidates'].items():
        if 'network_free_phase_drift' not in record:
            continue
        item = record['network_free_phase_drift']
        held = item['held_out_links']['rows']
        keys = {(r['station'],r['reference'],r['time_s']) for r in held}
        times = {}
        for r in item['calibration']['residuals']:
            if (r['station'],r['reference'],r['time_s']) not in keys:
                times.setdefault(r['segment'],set()).add(r['time_s'])
        invalid,valid_phase,valid_code,statuses,code_statuses,phase_statuses = [],[],[],Counter(),Counter(),Counter()
        for r in held:
            if r['status']=='EVALUATED' and len(times.get(r['segment'],set()))==1:
                invalid.append({**{k:r[k] for k in ('time_s','station','reference','segment')},
                    'invalidated_observable':'phase','retained_code_error_m':r['code_error_m']})
                statuses['PARTIALLY_EVALUATED'] += 1
                phase_statuses['UNIDENTIFIABLE_PHASE_DRIFT'] += 1
                code_statuses['EVALUATED'] += 1
                valid_code.append(r)
            else:
                statuses[r['status']] += 1
                code_statuses[r['status']] += 1
                phase_statuses[r['status']] += 1
                if r['status']=='EVALUATED':
                    valid_code.append(r)
                    valid_phase.append(r)
        candidates[candidate] = {'invalidated_rows':invalid,'status_counts':dict(statuses),
            'code_status_counts':dict(code_statuses),'phase_status_counts':dict(phase_statuses),
            'code_error_m':baseline.interval.diagnostic.moments([r['code_error_m'] for r in valid_code]),
            'phase_error_m':baseline.interval.diagnostic.moments([r['phase_error_m'] for r in valid_phase])}
    sources = [Path(__file__),Path(baseline.interval.diagnostic.__file__)]
    return native({'schema':'reference-network-heldout-support-correction-v2',
        'scope':'Invalidate only the phase observable in four v1 free-drift held-out rows whose segment has one training time. Retain their evaluable code errors and original code RMS. All orbit fits, clock estimates/covariances, candidate RF forecasts and CODE diagnostics remain the original execution. The superseded v1 correction discarded both observables.',
        'original_result_sha256':original_sha256,
        'superseded_correction_sha256':superseded_correction_sha256,
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'trajectories_or_candidate_predictions_changed':False,'new_fit_or_oracle_tuning':False,
        'candidates':candidates})


def linear_response(fit, arcs, joint):
    """Reuse the fitted GLS derivative, retaining full original data columns."""
    prepared,names,_ = dynamic_fit.prepare(arcs,True)
    scale = np.r_[dynamic_fit.STATE_SCALE,np.full(len(names)-1,100.)]
    point = np.r_[fit['state_ecef_m_m_s'],fit['bias_contrast_coefficients_m']]/scale
    locals_ = [np.r_[p['satellite_clock'],np.asarray(p['receiver_clocks']).ravel(),
        np.asarray(p['station_corrections_m']).ravel(),
        [p['mw_rate_bias_m_s'][i] for i in a['mw_indices']]]/a['local_scale']
        for p,a in zip(fit['arc_parameters'],prepared,strict=True)]
    details = {}
    _,_,_,cov,_,_ = dynamic_fit.linearize(point,locals_,prepared,scale,fit['epoch_gpst_s'],
        fit['integrated_bounds_s'],fit['j2'],joint_chol=dynamic_fit.joint_cholesky(prepared,joint),diagnostics=details)
    count = sum(a['full_observation_count'] for a in prepared)
    full = np.zeros((len(cov),count))
    at = 0
    for a,r in zip(prepared,details['observation_response'],strict=True):
        full[:,at+a['observation_indices']] = r
        at += a['full_observation_count']
    details['full_observation_response'] = full
    return details,cov,prepared


def information(fit, arcs, joint):
    if 'state_ecef_m_m_s' not in fit:
        return {'status':'FIT_UNAVAILABLE'}
    details,cov,prepared = linear_response(fit,arcs,joint)
    indices, at = [],0
    for a in prepared:
        indices.extend(at+a['ns']+1+3*np.arange(a['n']))
        at += len(a['local_scale'])
    cross = details['global_local_covariance'][:,indices]
    timing_cov = details['local_covariance'][np.ix_(indices,indices)]
    requirements = {}
    for sigma in (1e-5,1e-4,1e-3,1e-2):
        conditioned = cov-cross@np.linalg.solve(timing_cov+sigma**2*np.eye(len(indices)),cross.T)
        requirements[str(sigma)] = {
            'largest_position_sigma_m':np.sqrt(np.linalg.eigvalsh(conditioned[:3,:3])[-1]),
            'largest_velocity_sigma_m_s':np.sqrt(np.linalg.eigvalsh(conditioned[3:6,3:6])[-1])}
    return native({'status':'LOCAL_CONDITIONAL_SENSITIVITY_ONLY',
        'hypothetical_independent_interval_mean_clock_sigma_m_s':requirements,
        'measurement_count':len(indices),
        'measurement_requirement':'separate independent receiver interval mean-rate information, not another correlated GNSS product; no such measurements are admitted here'})


def clock_requests(arcs):
    requests = []
    for a in sorted(arcs,key=lambda a:a['endpoint_gpst_s']):
        t = a['endpoint_gpst_s']
        for s in a['stations']:
            requests.extend([{(s,t):1.},{(s,t):1/60.,(s,t-60):-1/60.},
                {(s,t-30):1/30.,(s,t-60):-1/60.,(s,t):-1/60.}])
    return requests


def attach(network, arcs):
    """Replace conditional clock data jointly; keep candidate RF/ground floors.

    The zero-mean reference-error datum is explicit in the network result.
    Its arbitrary common error has no inferred physical amplitude here.
    """
    arcs = [{**a} for a in sorted(arcs, key=lambda a: a['endpoint_gpst_s'])]
    requests = clock_requests(arcs)
    means, clock_covariance = network_clocks.clock_coefficients(network, requests)
    joint = block_diag(*[a['covariance'] for a in arcs])
    clock_indices, at, ct = [], 0, 0
    for a in arcs:
        n = len(a['stations'])
        a['clock_mean'] = means[ct:ct+3*n].reshape(n, 3)
        rf_count = 7*n if 'mw_rates_m_s' in a else 5*n
        indices = np.arange(at+rf_count, at+rf_count+3*n)
        clock_indices.extend(indices)
        own = np.array(a['covariance'], copy=True)
        own[rf_count:rf_count+3*n, rf_count:rf_count+3*n] = clock_covariance[ct:ct+3*n, ct:ct+3*n]
        a['covariance'] = own
        at += len(own)
        ct += 3*n
    joint[np.ix_(clock_indices, clock_indices)] = clock_covariance
    return arcs, joint, {'clock_mean': means, 'clock_covariance': clock_covariance,
        'clock_observation_indices': clock_indices,
        'maximum_offset_rate_correlation': float(max(abs(clock_covariance[i,j])/
            np.sqrt(clock_covariance[i,i]*clock_covariance[j,j])
            for i in range(0,len(means),3) for j in range(len(means)) if j%3)),
        'maximum_cross_arc_clock_covariance': float(max(
            np.max(np.abs(clock_covariance[:k,k:])) for k in np.cumsum([3*len(a['stations']) for a in arcs])[:-1]))}


def injection_checks(rows, arcs):
    """Recalibrate the full network after reference/receiver/link perturbations.

    Metre-scale injected signals are sensitivity tests, not physical sigmas.
    """
    nominal = network_clocks.fit(rows)
    requests = []
    last = max(a['endpoint_gpst_s'] for a in arcs)
    sites = sorted({r['station'] for r in rows if r['time_s'] == last})
    for s in sites:
        requests.append({(s,last): 1.})
    expected, _ = network_clocks.clock_coefficients(nominal, requests)
    station = sites[0]
    ref = next(r['reference'] for r in rows if r['time_s'] == last and r['station'] == station)
    checks = {}
    for label in ('reference_common', 'receiver_common', 'single_link_phase'):
        perturbed = []
        for row in rows:
            r = dict(row)
            affected = r['time_s'] == last and (r['reference'] == ref if label == 'reference_common'
                else r['station'] == station if label == 'receiver_common'
                else r['station'] == station and r['reference'] == ref)
            if affected:
                if label != 'single_link_phase':
                    r['code_m'] += 1.
                r['phase_m'] += 1.
            perturbed.append(r)
        fit = network_clocks.fit(perturbed)
        actual, _ = network_clocks.clock_coefficients(fit, requests)
        response = actual-expected
        checks[label] = {'epoch_gpst_s': last, 'station': station, 'reference': ref,
            'injected_m': 1., 'stations': sites, 'clock_change_m': response,
            'receiver_differential_change_m': response-response.mean(),
            'weighted_cost_change': fit['weighted_cost']-nominal['weighted_cost']}
    return checks


def target_continuity(data, candidate, arcs):
    """Assess only target epochs already in the RF training arcs.

    Globally excluded internal/future target phase is never used to construct
    a training mask. Codes remain observed even when an increment has a free
    unknown jump. Reference calibration is performed separately without it.
    """
    index, own, witnesses = baseline.phase_index(data), [], []
    for arc in sorted(arcs,key=lambda a:a['endpoint_gpst_s']):
        rows = []
        for s in arc['stations']:
            for dt in arc['tags_s']:
                t = arc['endpoint_gpst_s']+dt
                r = index[s][candidate,t]
                if r['status'] != 'AVAILABLE':
                    raise ValueError('prepared target phase became unavailable')
                rows.append({'station':s,'reference':candidate,'time_s':t,
                    'segment':f'{s}/{candidate}/{arc["endpoint_gpst_s"]}',
                    'geometry_free_phase_m':r['geometry_free_phase_m']})
        assessed = phase_continuity.segment(rows)
        by_key = {(r['station'],r['time_s']):r for r in assessed}
        mask = np.array([[not by_key[s,arc['endpoint_gpst_s']+t]['continuity']['break']
                          for s in arc['stations']] for t in arc['tags_s'][1:]],dtype=bool)
        own.append({**arc,'phase_increment_mask':mask})
        witnesses.extend(r for r in assessed if r['continuity']['break'])
    return own, {'witnesses':witnesses,'retained_increment_count':sum(int(a['phase_increment_mask'].sum()) for a in own),
        'total_increment_count':sum(a['phase_increment_mask'].size for a in own),
        'globally_withheld_target_phase_used':False,'target_codes_retained':True}


def target_combinations(data, candidate, arcs, raw_covariance, *, free_drift=False):
    """IF code/phase plus MW increments from the same admitted raw endpoints."""
    index,output = baseline.phase_index(data),[]
    for a in arcs:
        n = len(a['stations'])
        if len(a['tags_s'])!=3:
            raise ValueError('this study requires original three-endpoint arcs')
        epochs = []
        for t in a['tags_s']:
            own = []
            for s in a['stations']:
                r = index[s][candidate,a['endpoint_gpst_s']+t]
                if r['status']!='AVAILABLE':
                    raise ValueError('prepared target raw observations became unavailable')
                own.append(gnss_combinations.values(r['fields']))
            epochs.append(own)
        values = np.asarray(epochs)
        if not np.allclose(values[:,:,0],a['codes_m'],atol=1e-5,rtol=0):
            raise ValueError('raw/prepared target IF code mismatch')
        output.append({**a,'mw_rates_m_s':np.diff(values[:,:,3],axis=0)/30.,
            'mw_free_drift':free_drift,'covariance':block_diag(
                gnss_combinations.rf_covariance(a['tags_s'],n,raw_covariance),
                np.asarray(a['covariance'])[5*n:,5*n:])})
    return output


def predict_combinations(fit, arcs, weather, *, zenith_wet_m=None):
    if zenith_wet_m is not None and 'state_ecef_m_m_s' in fit:
        own = [{**a,'propagation':wet.propagation_model(weather,a['stations'])} for a in arcs]
        predictions = wet.predict({**fit,'station_zenith_wet_correction_m':zenith_wet_m},own,weather)
    else:
        predictions = baseline.interval.predict(fit,arcs,weather)
    if 'state_ecef_m_m_s' not in fit:
        return predictions
    for p,a,parameters in zip(predictions,sorted(arcs,key=lambda a:a['endpoint_gpst_s']),fit['arc_parameters'],strict=True):
        if p['status']=='PREDICTED' and 'mw_rates_m_s' in a:
            p['mw_rate_m_s'] = parameters.get('mw_rate_bias_m_s',[0.]*len(a['stations']))
            p['mw_model'] = 'free training linear bias extrapolated unchanged' if a.get('mw_free_drift') else 'constant link bias'
            p['gf_prediction'] = 'UNIDENTIFIABLE_WITH_FREE_LINK_EPOCH_IONOSPHERE'
    return predictions


def score_mw(data, candidate, predictions):
    index,windows = baseline.phase_index(data),[]
    for p in predictions:
        record = {'endpoint_gpst_s':p['endpoint_gpst_s'],'kind':p.get('kind'),'pairs':[]}
        for i,s in enumerate(p.get('stations',[])):
            own = {'station':s,'status':'MW_NOT_PREDICTED'}
            if p.get('status')=='PREDICTED' and 'mw_rate_m_s' in p:
                if p['mw_rate_m_s'][i] is None:
                    own['status'] = 'UNIDENTIFIABLE_MW_DRIFT'
                else:
                    end = p['endpoint_gpst_s']
                    a,b = index[s].get((candidate,end)),index[s].get((candidate,end+30))
                    if a is None or b is None or a['status']!='AVAILABLE' or b['status']!='AVAILABLE':
                        own['status'] = 'WITHHELD_UNAVAILABLE'
                    else:
                        delta = (gnss_combinations.values(b['fields'])[3]-gnss_combinations.values(a['fields'])[3])/30.
                        own.update(status='EVALUATED',mw_rate_residual_m_s=delta-p['mw_rate_m_s'][i])
            record['pairs'].append(own)
        windows.append(record)
    summaries = {}
    for kind in ('ALL','TEMPORAL_HOLDOUT','BEYOND_ALL_TRAINING'):
        pairs = [p for w in windows if kind=='ALL' or w['kind']==kind for p in w['pairs']]
        summaries[kind] = {'status_counts':dict(Counter(p['status'] for p in pairs)),
            'mw_rate_residual_m_s':baseline.interval.diagnostic.moments([
                p['mw_rate_residual_m_s'] for p in pairs if p['status']=='EVALUATED'])}
    return {'windows':windows,'summary':summaries,
        'gf_prediction':'UNIDENTIFIABLE_WITH_FREE_LINK_EPOCH_IONOSPHERE'}


def prepare_temporal(data, candidate, arcs, weather):
    """Keep the reference estimator fixed; propagate new raw-noise hypotheses."""
    raw_covariance = gnss_combinations.assumed_endpoint_covariance()
    network,rows,calibration = calibrate(data,candidate,arcs,weather,continuity=True,raw_covariance=raw_covariance)
    own = target_combinations(data,candidate,arcs,raw_covariance)
    own,joint,transport = attach(network,own)
    own,target = target_continuity(data,candidate,own)
    for a in own:a['mw_increment_mask'] = a['phase_increment_mask'].copy()
    transport['target_continuity'] = target
    held = held_out_links(rows,continuity=True,raw_covariance=raw_covariance)
    calibrated = {'joint_independent':(own,joint)}
    records = {'joint_independent':{'calibration':calibration,'transport':transport,'held_out_links':held}}
    labels = ('temporal_code','temporal_shared','temporal_without_cross')
    model = {'status':'TEMPORAL_MODEL_UNAVAILABLE'}
    try:
        model = temporal_contrasts.estimate(rows)
        for label,fraction in (('temporal_code',0.),('temporal_shared',.5)):
            updated,covariance,propagation = shared_rf_covariance.propagate(network,clock_requests(own),own,
                joint,transport['clock_observation_indices'],candidate,raw_covariance,
                code_rho=model['code_endpoint_ar1_rho_30s'],receiver_fraction=fraction)
            calibrated[label] = updated,covariance
            records[label] = {'calibration':calibration,'held_out_links':held,
                'transport':{**transport,**propagation}}
        # The ablation changes only the RF/clock cross block, retaining both
        # marginal blocks and the same fitted reference estimator/parameters.
        updated,covariance = calibrated['temporal_shared']
        covariance = covariance.copy()
        rf,at = [],0
        for a in updated:
            rf.extend(at+np.arange(7*len(a['stations'])));at+=len(a['covariance'])
        clocks = transport['clock_observation_indices']
        covariance[np.ix_(rf,clocks)] = 0.
        covariance[np.ix_(clocks,rf)] = 0.
        own_ablation,at = [],0
        for a in updated:
            stop = at+len(a['covariance'])
            own_ablation.append({**a,'covariance':covariance[at:stop,at:stop].copy()});at=stop
        calibrated['temporal_without_cross'] = own_ablation,covariance
        records['temporal_without_cross'] = {**records['temporal_shared'],
            'transport':{**records['temporal_shared']['transport'],
                'reference_target_cross_covariance_retained':False,'counterfactual_independence_ablation':True}}
    except (ValueError,KeyError,np.linalg.LinAlgError) as error:
        model = {**model,
            'preparation_status':'TEMPORAL_COVARIANCE_PREPARATION_FAILED','reason':str(error)}
        for label in labels:
            if label not in calibrated:
                records[label] = {'calibration':calibration,'covariance_status':'UNAVAILABLE','reason':str(error)}
    return calibrated,records,model


def fixed_wet_propagation(weather, stations, corrections):
    propagation = wet.propagation_model(weather,stations)
    values = np.array([corrections.get(s,0.) for s in stations])
    def model(pair, xyz, epoch, *, derivatives=False):
        return propagation(pair,xyz,epoch,derivatives=derivatives,wet_m=values)
    return model


def target_wet_design(fitted, arcs, weather, names):
    """Current RF-only geometry, in full original target-data ordering."""
    prepared,_,_ = dynamic_fit.prepare(arcs,True)
    curve = baseline.dynamics.Trajectory(fitted['state_ecef_m_m_s'],fitted['integrated_bounds_s'],j2=fitted['j2'])
    designs = []
    for a,p in zip(prepared,fitted['arc_parameters'],strict=True):
        local = np.r_[p['satellite_clock'],np.asarray(p['receiver_clocks']).ravel(),
            np.asarray(p['station_corrections_m']).ravel()]/a['local_scale']
        _,pair = dynamic_fit.model(curve,a,local,fitted['bias_contrast_coefficients_m'],fitted['epoch_gpst_s'])
        xyz = a['xyz']+np.asarray(p['station_corrections_m'])
        propagation = wet.propagation_model(weather,a['stations'])
        mapping = (propagation(pair,xyz,fitted['epoch_gpst_s'],wet_m=np.ones(a['n']))['delay_m']-
            propagation(pair,xyz,fitted['epoch_gpst_s'])['delay_m'])
        code = np.zeros((a['codes'].size,len(names)))
        for j,station in enumerate(a['stations']):code[j::a['n'],names.index(station)] = mapping[:,j]
        g = np.zeros((a['full_observation_count'],len(names)))
        g[:len(code)] = code
        difference = dynamic_fit.interval_matrix(a['tags'],a['n'])
        g[len(code):len(code)+len(difference)] = difference@code
        designs.append(g)
    return np.vstack(designs)




def physical_source_rows(data,candidate,rows,network,weather):
    source_geometry.admit(network,candidate)
    provider,corrections=baseline.subset_products(data,[q for q in data['plan']['references'] if q!=candidate],candidate)
    codes={(s,e['time_s'],q):v for s,epochs in data['observations'].items() for e in epochs
        for q,v in e['if_code_m'].items() if q!=candidate and q in data['plan']['references']}
    centres={(s,b['time_s']):float(b['parameters'][i]) for b in network['blocks'] for i,s in enumerate(b['stations'])}
    mjd=(datetime.fromisoformat(data['plan']['date_gpst'])-datetime(1858,11,17)).days
    output=[]
    for r in rows:
        q,s,t=r['reference'],r['station'],r['time_s']
        if q==candidate:raise ValueError('candidate at physical source boundary')
        xyz=np.asarray(data['positions'][s][int((t-36000)/30)],float)
        code=float(codes[s,t,q])+corrections[t,q]['if_code_change_m']
        g=reference_geometry.emitted_source_mappings(provider,weather,mjd,q,code,t,xyz,centres[s,t],complete=True)
        output.append({**r,**native(g),'reference_clock_centre_m':centres[s,t]})
    return output,centres



def run_stable_sources():
    """Stable physical increments and complementary hypothetical observables."""
    priors={}
    pins={'weak_source_physical_recovery_v1.json.gz':'917202d0184c4bed1b8925d98818df6c4e0a14af1ad2b9eb2524f5dd001b3717',
        'reference_source_separation_v1.json.gz':'a8caee27bbb751090ce4af25d384bc23bad8111e2d94fe76754834f937821467'}
    for name,sha in pins.items():
        payload=(baseline.BASE/'results'/name).read_bytes()
        if baseline.interval.shared.digest(payload)!=sha:raise ValueError('changed stable-source parent evidence')
        priors[name]=json.loads(gzip.decompress(payload))
    previous=priors['weak_source_physical_recovery_v1.json.gz'];separation=priors['reference_source_separation_v1.json.gz']
    raw,data=baseline.read_inputs();hashes={k:baseline.interval.shared.digest(v) for k,v in raw.items()}
    if previous['input_sha256']!=hashes or separation['input_sha256']!=hashes:raise ValueError('stable-source inputs changed')
    weather=baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    covariance=gnss_combinations.assumed_endpoint_covariance();results={}
    for candidate,old in previous['candidates'].items():
        print(candidate,'stable differential',flush=True)
        record={'windows':old['windows'],'prepared_arc_count':old['prepared_arc_count'],
            'archived_nominal_fit_status':old['archived_nominal_fit_status'],'status':'INSUFFICIENT_PREPARED_ARCS'};results[candidate]=record
        if 'source_profile' not in old:continue
        try:
            source_geometry.admit({'blocks':[{'rows':old['reference_rows']}]},candidate)
            provider,corrections=baseline.subset_products(data,[q for q in data['plan']['references'] if q!=candidate],candidate)
            codes={(s,e['time_s'],q):v for s,epochs in data['observations'].items() for e in epochs
                for q,v in e['if_code_m'].items() if q!=candidate and q in data['plan']['references']}
            mjd=(datetime.fromisoformat(data['plan']['date_gpst'])-datetime(1858,11,17)).days
            rows=[];frozen=[];contexts={};precision={};clock_change=0.;mapping_precision=0.;central_difference=0.
            for i,r in enumerate(old['reference_rows']):
                q,s,t=r['reference'],r['station'],r['time_s'];code=float(codes[s,t,q])+corrections[t,q]['if_code_change_m']
                xyz=np.asarray(data['positions'][s][int((t-36000)/30)],float);centre=r['reference_clock_centre_m']
                context=reference_geometry.StableSourceRay(provider,weather,mjd,q,code,t,xyz,centre);maps=native(context.mappings())
                new_clock=context.clock_coefficient();delta=new_clock-r['clock_derivative'];clock_change=max(clock_change,abs(delta))
                frozen.append({**r,**maps});rows.append({**r,**maps,'clock_derivative':new_clock,
                    'code_m':r['code_m']+delta*centre,'phase_m':r['phase_m']+delta*centre})
                key=s,q,t;contexts[key]=context
                if i%128==0:
                    other=reference_geometry.StableSourceRay(provider,weather,mjd,q,code,t,xyz,centre,digits=35)
                    precision[key]=other;check=other.mappings();central=context.central_mappings()
                    for field in ('wet_mapping','orbit_mapping','antenna_mapping','bias_code_mapping','bias_phase_mapping','bias_mw_mapping'):
                        mapping_precision=max(mapping_precision,float(np.max(np.abs(np.asarray(check[field])-maps[field]))))
                        central_difference=max(central_difference,float(np.max(np.abs(np.asarray(central[field])-maps[field]))))
                if i%1024==0:print(candidate,'stable rows',i,len(old['reference_rows']),flush=True)
            network=network_clocks.fit(rows,raw_covariance=covariance);profile,w=source_geometry.profile_sources(network,candidate,source_geometry.FAMILIES)
            old_net=network_clocks.fit(frozen,raw_covariance=covariance);frozen_profile,_=source_geometry.profile_sources(old_net,candidate,source_geometry.FAMILIES)
            columns=w['columns']
            if native(columns)!=old['source_profile']['columns']:raise ValueError('changed physical source-coordinate order')
            prior=separation['candidates'][candidate]
            requests=[{(s,t):coefficient for s,t,coefficient in own} for own in prior['clock_requests']]
            kg=sum(k@g for k,g in zip(network_clocks.observation_response(network,requests),w['designs'],strict=True))
            response=np.asarray(prior['full_state_observation_response']);gc=np.zeros((response.shape[1],len(columns)))
            stations=profile['wet']['stations'];target=np.asarray(prior['target_wet_model_design'])
            for j,col in enumerate(columns):
                if col[0]=='wet':gc[:,j]=target[:,stations.index(col[1])]
            tref=-response[:,prior['transport']['clock_observation_indices']]@kg;tcand=-response@gc;tmap=tref+tcand
            u,s,v=np.linalg.svd(w['design'],full_matrices=False);rank=profile['resolved_rank'];spectrum={'u':u,'s':s,'v':v,'rank':rank}
            direction=np.asarray(old['stability']['weak_direction_m_per_unit_l2_m']);scale=profile['original_weighted_source_scale_per_m']
            endpoints=old['clock_endpoint_keys']
            record.update(status='STABLE_DIFFERENTIAL_PREPARED',reference_rows=rows,source_profile=profile,
                frozen_historical_clock_profile=frozen_profile,maximum_clock_coefficient_change=clock_change,
                precision_check_keys=[list(k) for k in precision],precision_mapping_max_abs_35_minus50=mapping_precision,analytic_central_mapping_max_abs_difference=central_difference,
                reference_model_state_map=tref,candidate_model_state_map=tcand,coupled_model_state_map=tmap,
                prior_frozen_weak_direction_m_per_unit_l2_m=direction,clock_endpoint_keys=endpoints,
                reference_information=source_geometry.source_information_summary(s[:,None]*v,tmap,direction,scale),
                physical_probes=[],odd_even_probes=[])
            for planned in old['physical_probes']:
                vector=np.asarray(planned['source_vector_m']);probe=source_geometry.split_probe(columns,vector,candidate)
                item={k:planned[k] for k in ('mode','source_l2_m','sign')};item['source_vector_m']=vector;record['physical_probes'].append(item)
                try:
                    blocks=[];precision_difference=0.
                    for b in network['blocks']:
                        values=[]
                        for r in b['rows']:
                            q,s,t=r['reference'],r['station'],r['time_s'];key=s,q,t
                            local=[probe['wet'].get(s,0.),*probe['orbit'].get(q,[0.,0.,0.]),*probe['antenna'].get(q,[0.,0.,0.]),probe['bias'].get(s+'/'+q,0.)]
                            value=contexts[key].increment(local);values.append(value)
                            if key in precision:precision_difference=max(precision_difference,float(np.max(np.abs(value-precision[key].increment(local)))))
                        blocks.append(np.asarray(values).T.ravel())
                    physical=source_geometry.profiled_increment(network,blocks)
                    linear=source_geometry.profiled_increment(network,[g@vector for g in w['designs']])
                    intended=w['design']@vector
                    item.update(status='STABLE_FINITE_PHYSICAL_INCREMENT_PREPARED',physical_increment_blocks=blocks,
                        decimal35_minus50_max_abs_m=precision_difference,profiled_linear_weighted_norm=float(np.linalg.norm(intended)),
                        profiled_physical_weighted_norm=float(np.linalg.norm(physical)),
                        profiled_forward_defect_weighted_norm=float(np.linalg.norm(physical-intended)),
                        recovery={'linear_control':source_geometry.recover_profiled_increment(linear,w['design'],spectrum,vector,tmap),
                            'physical_increment':source_geometry.recover_profiled_increment(physical,w['design'],spectrum,vector,tmap)})
                except (ValueError,KeyError,np.linalg.LinAlgError) as error:item.update(status='STABLE_PHYSICAL_PROBE_FAILED',reason=str(error))
            for amplitude in source_geometry.PROBE_SOURCE_L2_M:
                pair=[p for p in record['physical_probes'] if p['mode']=='weak' and p['source_l2_m']==amplitude]
                if any(p['status']!='STABLE_FINITE_PHYSICAL_INCREMENT_PREPARED' for p in pair):
                    record['odd_even_probes'].append({'source_l2_m':amplitude,'status':'PAIRED_PHYSICAL_PROBE_UNAVAILABLE'});continue
                plus=next(p for p in pair if p['sign']>0);minus=next(p for p in pair if p['sign']<0)
                yp=source_geometry.profiled_increment(network,plus['physical_increment_blocks']);ym=source_geometry.profiled_increment(network,minus['physical_increment_blocks'])
                odd=(yp-ym)/2;even=(yp+ym)/2;truth=np.asarray(plus['source_vector_m']);linear=w['design']@truth
                record['odd_even_probes'].append({'source_l2_m':amplitude,'status':'STABLE_ODD_EVEN_EVALUATED',
                    'odd_weighted_norm':float(np.linalg.norm(odd)),'even_weighted_norm':float(np.linalg.norm(even)),
                    'odd_minus_linear_weighted_norm':float(np.linalg.norm(odd-linear)),
                    'odd_recovery':source_geometry.recover_profiled_increment(odd,w['design'],spectrum,truth,tmap)})
            print(candidate,'complementary source information',flush=True)
            record['complementary_source_information']=source_geometry.complementary_source_information(w['design'],columns,tmap,direction,scale)
            clock=[]
            for rho in (0.,.5):
                for sigma in (1e-4,1e-3,1e-2,1e-1,1.):
                    joint,meta=source_geometry.joint_external_clock_source_design(network,columns,endpoints,sigma,candidate,epoch_correlation=rho)
                    _,sj,vj=np.linalg.svd(joint,full_matrices=False);compressed=sj[:,None]*vj;designs={}
                    for families in ((),('wet',),('antenna',),('wet','antenna'),('wet','antenna','bias')):
                        h,count=source_geometry.source_measurement_design(columns,families,'independent')
                        designs['_'.join(families) or 'clock_only']={'direct_source_measurement_count':count,
                            'information':source_geometry.source_information_summary(np.vstack([compressed,h/sigma]),tmap,direction,scale)}
                    clock.append({'joint_clock_model':meta,'complementary_direct_source_observations':designs})
            record['joint_external_clock_information']=clock
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:record.update(status='STABLE_DIFFERENTIAL_PREPARATION_FAILED',reason=str(error))
    modules=[baseline,baseline.interval,baseline.interval.shared,reference_geometry,source_geometry,network_clocks,gnss_combinations,
        baseline.precise,baseline.attitude,baseline.conventions,baseline.sp3,baseline.day,baseline.day.atmosphere,baseline.interval.shared.meteo]
    sources=[Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema':'exposed-stable-source-differential-v1','prior_sha256':pins,'input_sha256':hashes,
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,'raw_endpoint_weight_covariance_m2':covariance,
        'decimal_digits':50,'precision_check_digits':35,'precision_check_row_stride':128,'analytic_source_derivative_central_check_step_m':1e-12,'emission_time_derivative_step_s':1e-8,
        'source_probe_directions_frozen_from_prior':True,'candidate_products_used_in_own_network':False,
        'candidate_rf_used_in_own_network':False,'candidate_code_orbit_scoring':False,'new_rf_trajectory_fits':False,'new_rf_or_mw_scoring':False,
        'archived_rf_state_used_only_for_local_response':True,'archived_rf_state_used_as_fit_seed':False,
        'physical_covariance_qualified':False,'production_floors_changed':False,'independent_measurements_admitted':False,
        'g12_state_accessed':False,'new_confirmation':False,'information_target_is_fixed_nominal_rf_sensitivity_not_joint_state_covariance':True,
        'status_counts':dict(Counter(c['status'] for c in results.values())),
        'archived_nominal_fit_status_counts':dict(Counter(c['archived_nominal_fit_status'] for c in results.values())),'candidates':results})

def run_weak_sources():
    """Weak source stability, finite physical recovery and information design."""
    prior_path=baseline.BASE/'results/reference_source_separation_v1.json.gz'
    prior_bytes=prior_path.read_bytes();prior_sha='a8caee27bbb751090ce4af25d384bc23bad8111e2d94fe76754834f937821467'
    if baseline.interval.shared.digest(prior_bytes)!=prior_sha:raise ValueError('changed source-separation evidence')
    prior=json.loads(gzip.decompress(prior_bytes));raw,data=baseline.read_inputs()
    if prior['input_sha256']!={k:baseline.interval.shared.digest(v) for k,v in raw.items()}:raise ValueError('weak-source inputs changed')
    weather=baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    covariance=gnss_combinations.assumed_endpoint_covariance();results={}
    labels=('weak_001m','weak_010m')
    for candidate,old in prior['candidates'].items():
        print(candidate,'weak sources',flush=True)
        record={'windows':old['windows'],'prepared_arc_count':old['prepared_arc_count'],
            'archived_nominal_fit_status':old['fit']['status'],'variants':{k:{'fit':{'status':'INSUFFICIENT_PREPARED_ARCS'},'rf_predictions':[]} for k in labels}}
        results[candidate]=record
        if 'source_models' not in old:continue
        try:
            nominal=network_clocks.fit(old['reference_rows'],raw_covariance=covariance)
            rows,centres=physical_source_rows(data,candidate,old['reference_rows'],nominal,weather)
            network=network_clocks.fit(rows,raw_covariance=covariance)
            profile,w=source_geometry.profile_sources(network,candidate,source_geometry.FAMILIES)
            requests=[{(s,t):coefficient for s,t,coefficient in own} for own in old['clock_requests']]
            operators=network_clocks.observation_response(network,requests)
            kg=sum(k@g for k,g in zip(operators,w['designs'],strict=True))
            response=np.asarray(old['full_state_observation_response']);gc=np.zeros((response.shape[1],len(w['columns'])))
            stations=profile['wet']['stations'];target=np.asarray(old['target_wet_model_design'])
            for j,col in enumerate(w['columns']):
                if col[0]=='wet':gc[:,j]=target[:,stations.index(col[1])]
            tref=-response[:,old['transport']['clock_observation_indices']]@kg;tcand=-response@gc;t=tref+tcand
            modes,spectrum=source_geometry.weak_modes(w['design'],t,profile['original_weighted_source_scale_per_m'])
            rotated=network_clocks.fit(rows,raw_covariance=covariance,reference_rotation=.37)
            rotated_profile,rw=source_geometry.profile_sources(rotated,candidate,source_geometry.FAMILIES)
            flat=[{**r,'clock_derivative':1.} for r in rows]
            flat_profile,fw=source_geometry.profile_sources(network_clocks.fit(flat,raw_covariance=covariance),candidate,source_geometry.FAMILIES)
            endpoints=sorted({k for request in requests for k in request})
            h=sum(k@g for k,g in zip(network_clocks.observation_response(network,[{key:1.} for key in endpoints]),w['designs'],strict=True))
            design={str(tol):source_geometry.independent_information({**spectrum,'rank':modes['thresholds'][str(tol)]['rank']},t,w['columns'],h,modes['weak_direction_m_per_unit_l2_m']) for tol in source_geometry.WEAK_RTOLS}
            record.update(reference_rows=rows,source_profile=profile,stability=modes,
                equivalent_clock_basis={'rank':rotated_profile['resolved_rank'],
                    'profiled_design_relative_difference':float(np.linalg.norm(rw['design']-w['design'])/np.linalg.norm(w['design']))},
                clock_derivative_ablation={'status':'DIFFERENT_CALIBRATION_MODEL_NOT_EQUIVALENT_DATUM',
                    'rank':flat_profile['resolved_rank'],'source_count':flat_profile['source_count']},
                independent_information=design,clock_endpoint_keys=endpoints,clock_endpoint_source_map=h,
                reference_model_state_map=tref,candidate_model_state_map=tcand,coupled_model_state_map=t,
                clock_source_map=kg,physical_probes=[])
            # Fresh preparation is used for every cold-start trajectory fit.
            arcs,windows=baseline.build_arcs(data,candidate,weather)
            if len(arcs)!=old['prepared_arc_count']:raise ValueError('changed candidate preparation support')
            own=target_combinations(data,candidate,arcs,covariance);own,joint,transport=attach(network,own)
            own,continuity=target_continuity(data,candidate,own)
            for a in own:a['mw_increment_mask']=a['phase_increment_mask'].copy()
            stop=max(a['endpoint_gpst_s'] for a in arcs)
            base_rows,base_failures=reference_rows(data,candidate,stop,weather,centres,continuity=True,combinations=True)
            keys=lambda rs:[(r['station'],r['reference'],r['time_s'],r['segment']) for r in rs]
            if keys(base_rows)!=keys(rows):raise ValueError('physical baseline support/segments changed')
            base_index={(r['station'],r['reference'],r['time_s']):r for r in base_rows}
            for mode in ('strong','weak'):
                direction=np.asarray(modes[mode+'_direction_m_per_unit_l2_m'])
                for amplitude in source_geometry.PROBE_SOURCE_L2_M:
                    for sign in ((1.,-1.) if mode=='weak' else (1.,)):
                        vector=direction*amplitude*sign;probe=source_geometry.split_probe(w['columns'],vector,candidate)
                        item={'mode':mode,'source_l2_m':amplitude,'sign':sign,'source_vector_m':vector}
                        record['physical_probes'].append(item)
                        try:
                            minimum={s:min(r['zenith_wet_m'] for r in rows if r['station']==s)+probe['wet'].get(s,0.) for s in stations}
                            item['minimum_reference_total_zenith_wet_m']=minimum
                            if min(minimum.values())<0:raise ValueError('negative total reference wet in declared finite probe')
                            changed,failures=reference_rows(data,candidate,stop,weather,centres,continuity=True,combinations=True,source_probe=probe)
                            if failures!=base_failures or keys(changed)!=keys(base_rows):raise ValueError('finite source support/segments changed')
                            changed_index={(r['station'],r['reference'],r['time_s']):r for r in changed}
                            signals=[];linear=[];physical_blocks=[];roundoff=0.
                            for b,g in zip(network['blocks'],w['designs'],strict=True):
                                values=[]
                                for r in b['rows']:
                                    key=r['station'],r['reference'],r['time_s'];a=base_index[key];z=changed_index[key]
                                    shift=(z['clock_derivative']-a['clock_derivative'])*centres[r['station'],r['time_s']]
                                    values.append([-(z['code_m']-a['code_m']-shift),-(z['phase_m']-a['phase_m']-shift),-(z['mw_m']-a['mw_m'])])
                                    roundoff=max(roundoff,32*np.finfo(float).eps*max(abs(a['phase_m']),abs(a['code_m']),3e7))
                                physical=np.asarray(values).T.ravel();physical_blocks.append(physical)
                                signals.append((b['rows'],physical));linear.append((b['rows'],g@vector))
                            item.update(status='FINITE_PHYSICAL_INCREMENT_PREPARED',physical_increment_blocks=physical_blocks,
                                forward_difference_roundoff_bound_per_observable_m=roundoff,
                                recovery=source_geometry.known_source_recovery(rows,signals,linear,vector,t,spectrum,covariance,candidate),
                                physical_update='COM position/velocity, relativistic clock, emission, Sagnac, admitted attitude, VMF3 and P1-only stable IF bias')
                            if mode=='weak' and sign>0:
                                label='weak_001m' if amplitude==.01 else 'weak_010m'
                                ref,newrows,cal=calibrate(data,candidate,arcs,weather,centres=centres,continuity=True,
                                    raw_covariance=covariance,source_probe=probe)
                                if keys(newrows)!=keys(base_rows):raise ValueError('recalibrated source support/segments changed')
                                trial,recomputed,meta=attach(ref,own)
                                for a,b in zip(trial,own,strict=True):
                                    a['covariance']=b['covariance'];a['propagation']=fixed_wet_propagation(weather,a['stations'],probe['wet'])
                                fitted=dynamic_fit.fit(trial,joint_covariance=joint,progress=lambda v:print(candidate,label,v,flush=True))
                                fitted['reference_calibration_status']=cal['status']
                                if cal['status']=='CONDITIONAL_MODEL_REJECTED':
                                    fitted['algebraic_target_fit_status']=fitted['status'];fitted['status']='REFERENCE_CALIBRATION_MODEL_REJECTED'
                                predictions=predict_combinations(fitted,trial,weather,zenith_wet_m=probe['wet'])
                                variant={'fit':fitted,'rf_predictions':predictions,'reference_calibration':cal,
                                    'target_weight_covariance_fixed_at_nominal':True,'cold_start_rf_initialization':True,
                                    'source_vector_m':vector,'linear_state_change_m_m_s':t@vector,
                                    'clock_change':meta['clock_mean']-transport['clock_mean'],
                                    'linear_clock_change':-kg@vector}
                                if 'state_ecef_m_m_s' in fitted:
                                    delta=np.asarray(fitted['state_ecef_m_m_s'])-np.asarray(old['fit']['state_ecef_m_m_s'])
                                    variant.update(finite_state_change_m_m_s=delta,finite_minus_linear_state_change_m_m_s=delta-t@vector)
                                record['variants'][label]=variant
                        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                            item.update(status='FINITE_PHYSICAL_PROBE_FAILED',reason=str(error))
                            if mode=='weak' and sign>0:
                                record['variants']['weak_001m' if amplitude==.01 else 'weak_010m']['fit']={'status':'FINITE_PHYSICAL_PROBE_FAILED','reason':str(error)}
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            record['preparation_failure']=str(error)
            for v in record['variants'].values():v['fit']={'status':'WEAK_SOURCE_PREPARATION_FAILED','reason':str(error)}
    # Every physical intervention, recovery and candidate prediction is fixed
    # before any dedicated RF/MW score. No CODE/oracle state is consumed.
    for candidate,c in results.items():
        for v in c['variants'].values():
            predictions=v['rf_predictions']
            v.update(prediction_sha256=baseline.interval.shared.digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()),
                rf_evaluation=baseline.score_rf(data,candidate,predictions),mw_evaluation=score_mw(data,candidate,predictions))
    modules=[baseline,baseline.interval,baseline.interval.shared,wet,reference_geometry,dynamic_fit,source_geometry,network_clocks,
        phase_continuity,gnss_combinations,baseline.precise,baseline.attitude,baseline.conventions,baseline.bias,baseline.sp3,
        baseline.day,baseline.day.atmosphere,baseline.interval.shared.meteo,baseline.dynamics,baseline.interval.clock_observations]
    sources=[Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema':'exposed-weak-source-physical-recovery-v1','prior_sha256':prior_sha,
        'scope':'Exposed weak combinations; equivalent-coordinate and clock-basis stability; finite physical incremental recovery; cold-start candidate probes; hypothetical independent source-information design.',
        'candidate_products_used_in_own_fit':False,'candidate_rf_used_in_own_network':False,'candidate_code_orbit_scoring':False,
        'archived_rf_state_used_only_for_local_response_and_after_fit_comparison':True,'archived_rf_state_used_as_fit_seed':False,
        'all_predictions_before_scoring':True,'g12_state_accessed':False,'oracle_tuning':False,'new_confirmation':False,
        'physical_covariance_qualified':False,'production_floors_changed':False,'independent_measurements_admitted':False,
        'physical_probe_amplitudes_are_measured_errors':False,'thresholds_selected_from_scores':False,
        'probe_source_l2_m':source_geometry.PROBE_SOURCE_L2_M,'rank_rtols':source_geometry.WEAK_RTOLS,
        'input_sha256':{k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,'raw_endpoint_weight_covariance_m2':covariance,
        'fit_status_counts':{label:dict(Counter(c['variants'][label]['fit']['status'] for c in results.values())) for label in labels},'candidates':results})


def run_separation():
    """Separate exposed wet, emitted reference APC shapes and stable IF bias.

    Fresh nominal cold-start RF fits provide only local response geometry.
    Unresolved source amplitudes never become candidate-state corrections.
    """
    raw,data=baseline.read_inputs()
    weather=baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    covariance=gnss_combinations.assumed_endpoint_covariance()
    models={'wet':('wet',),'wet_bias':('wet','bias'),
        'wet_orbit_bias':('wet','orbit','bias'),'wet_orbit_antenna_bias':source_geometry.FAMILIES}
    results={}
    for candidate in data['plan']['references']:
        print(candidate,'prepare source separation',flush=True)
        try:arcs,windows=baseline.build_arcs(data,candidate,weather)
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            arcs,windows=[],baseline.coverage(data,candidate)
            for w in windows:
                if w['status']=='RF_COVERED':w.update(status='CANDIDATE_PREPARATION_FAILED',reason=str(error))
        record={'windows':native(windows),'prepared_arc_count':len(arcs),
            'fit':{'status':'INSUFFICIENT_PREPARED_ARCS','arc_count':len(arcs)},'rf_predictions':[]}
        results[candidate]=record
        if len(arcs)<2:continue
        try:
            network,rows,calibration=calibrate(data,candidate,arcs,weather,continuity=True,
                raw_covariance=covariance,source_geometry=True,reference_sources=True)
            record.update(reference_rows=rows,calibration=calibration,source_models={},future_links={})
            workspaces={}
            for label,families in models.items():
                profile,workspace=source_geometry.profile_sources(network,candidate,families)
                record['source_models'][label]=profile;workspaces[label]=workspace
                record['future_links'][label]=network_closures.prepare_future_links(rows,candidate,covariance,source_families=families)
            own=target_combinations(data,candidate,arcs,covariance)
            own,joint,transport=attach(network,own)
            own,continuity=target_continuity(data,candidate,own)
            for a in own:a['mw_increment_mask']=a['phase_increment_mask'].copy()
            fitted=dynamic_fit.fit(own,joint_covariance=joint,progress=lambda r:print(candidate,r,flush=True))
            fitted['reference_calibration_status']=calibration['status']
            if calibration['status']=='CONDITIONAL_MODEL_REJECTED':
                fitted['algebraic_target_fit_status']=fitted['status'];fitted['status']='REFERENCE_CALIBRATION_MODEL_REJECTED'
            record.update(fit=fitted,rf_predictions=predict_combinations(fitted,own,weather),
                transport={**transport,'target_continuity':continuity})
            details,_,_=linear_response(fitted,own,joint);response=details['full_observation_response'][:6]
            requests=clock_requests(own);operators=network_clocks.observation_response(network,requests)
            stations=record['source_models']['wet']['wet']['stations']
            target=target_wet_design(fitted,own,weather,stations)
            record.update(full_state_observation_response=response,target_wet_model_design=target,
                clock_requests=[[[s,t,c] for (s,t),c in r.items()] for r in requests])
            for label,workspace in workspaces.items():
                profile=record['source_models'][label];columns=workspace['columns']
                kg=sum(k@g for k,g in zip(operators,workspace['designs'],strict=True))
                gc=np.zeros((response.shape[1],len(columns)))
                for j,c in enumerate(columns):
                    if c[0]=='wet':gc[:,j]=target[:,stations.index(c[1])]
                tref=-response[:,transport['clock_observation_indices']]@kg
                tcand=-response@gc;t=tref+tcand;null=workspace['null']
                ambiguity=t@null
                source_response={'reference_model_response':tref,'candidate_model_response':tcand,
                    'coupled_model_response':t,'clock_source_response':kg,
                    'candidate_nonwet_source_columns_zero':True,
                    'null_position_gain_m_per_source_l2_m':float(np.linalg.norm(ambiguity[:3],2)) if null.shape[1] else 0.,
                    'null_velocity_gain_mm_s_per_source_l2_m':float(np.linalg.norm(ambiguity[3:],2)*1000) if null.shape[1] else 0.,
                    'response_is_local_not_total_state_uncertainty':True}
                profile['state_response']=source_response
                if null.shape[1]:
                    _,_,v=np.linalg.svd(ambiguity[:3],full_matrices=False)
                    probe=null@v[0]*.01  # fixed 1 cm TOTAL Euclidean metre norm, not RMS or sigma
                    source_response.update(null_probe_m=probe,null_probe_source_l2_m=float(np.linalg.norm(probe)),
                        null_probe_weighted_training_residual_norm=float(np.linalg.norm(workspace['design']@probe)),
                        null_probe_linear_state_change_m_m_s=t@probe)
                    if label=='wet_orbit_antenna_bias':
                        corrected=[]
                        for b,g in zip(network['blocks'],workspace['designs'],strict=True):
                            change=g@probe;m=len(b['rows'])
                            corrected.extend({**r,'code_m':r['code_m']-change[i],
                                'phase_m':r['phase_m']-change[m+i],'mw_m':r['mw_m']-change[2*m+i]} for i,r in enumerate(b['rows']))
                        finite=network_clocks.fit(corrected,raw_covariance=covariance)
                        before,_=network_clocks.clock_coefficients(network,requests)
                        after,_=network_clocks.clock_coefficients(finite,requests)
                        source_response.update(fixed_geometry_reference_refit_clock_change=after-before,
                            fixed_geometry_reference_refit_minus_linear=after-before+kg@probe,
                            full_reference_observation_time_relinearized=False,
                            null_probe_is_observed_error=False)
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            record['preparation_failure']=str(error)
            if record['fit']['status']=='INSUFFICIENT_PREPARED_ARCS':record['fit']={'status':'SOURCE_SEPARATION_PREPARATION_FAILED','reason':str(error)}
    for candidate,record in results.items():
        for label,predictions in record.get('future_links',{}).items():
            record['future_links'][label]=network_closures.score_future_links(predictions,record['reference_rows'])
        predictions=record['rf_predictions']
        record.update(prediction_sha256=baseline.interval.shared.digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()),
            rf_evaluation=baseline.score_rf(data,candidate,predictions),mw_evaluation=score_mw(data,candidate,predictions))
    modules=[baseline,baseline.interval,baseline.interval.shared,wet,dynamic_fit,network_clocks,source_geometry,
        network_closures,reference_geometry,phase_continuity,gnss_combinations,temporal_contrasts,
        baseline.precise,baseline.attitude,baseline.bias,baseline.conventions,baseline.sp3,baseline.day,
        baseline.day.atmosphere,baseline.interval.shared.meteo,baseline.dynamics,baseline.interval.clock_observations]
    sources=[Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema':'exposed-reference-source-separation-v1','models':models,
        'scope':'Exposed joint source-shape identifiability, null-safe future reference transfer and local coupled RF-state response.',
        'candidate_products_used_in_own_fit':False,'candidate_rf_used_in_own_network':False,
        'all_predictions_before_scoring':True,'candidate_code_orbit_scoring':False,'g12_state_accessed':False,
        'oracle_tuning':False,'new_confirmation':False,'physical_covariance_qualified':False,
        'production_floors_changed':False,'source_estimates_used_as_candidate_corrections':False,
        'reference_orbit_shape_is_fixed_emission_apc_displacement':True,
        'reference_clock_relativity_and_emission_not_recomputed_for_source_shapes':True,
        'stable_bias_is_reference_link_if_code_only_after_phase_mw_float_profiling':True,
        'input_sha256':{k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,
        'raw_endpoint_weight_covariance_m2':covariance,
        'fit_status_counts':dict(Counter(c['fit']['status'] for c in results.values())),'candidates':results})


def run_sources():
    """Restricted wet geometry, reference transfer and both physical paths."""
    raw,data = baseline.read_inputs()
    weather = baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    raw_covariance = gnss_combinations.assumed_endpoint_covariance()
    labels = ('joint_independent','reference_only','candidate_only','coupled')
    results = {}
    def estimate(candidate,label,own,joint,status,corrections=None):
        try:
            fitted = dynamic_fit.fit(own,joint_covariance=joint,
                progress=lambda r:print(candidate,label,r,flush=True))
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            fitted = {'status':'FIT_FAILED','reason':str(error)}
        fitted['reference_calibration_status'] = status
        if status=='CONDITIONAL_MODEL_REJECTED':
            fitted['algebraic_target_fit_status'] = fitted['status']
            fitted['status'] = 'REFERENCE_CALIBRATION_MODEL_REJECTED'
        predictions = (predict_combinations(fitted,own,weather) if corrections is None else
            predict_combinations(fitted,own,weather,zenith_wet_m=corrections))
        return {'fit':fitted,'rf_predictions':predictions,
            'prediction_sha256':baseline.interval.shared.digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode())}
    for candidate in data['plan']['references']:
        print(candidate,'prepare source geometry',flush=True)
        try:
            arcs,windows = baseline.build_arcs(data,candidate,weather)
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            arcs,windows = [],baseline.coverage(data,candidate)
            for w in windows:
                if w['status']=='RF_COVERED':w.update(status='CANDIDATE_PREPARATION_FAILED',reason=str(error))
        record = {'windows':native(windows),'prepared_arc_count':len(arcs),'variants':{
            label:{'fit':{'status':'INSUFFICIENT_PREPARED_ARCS','arc_count':len(arcs)},
                'rf_predictions':[],'prediction_sha256':baseline.interval.shared.digest(b'[]')} for label in labels}}
        results[candidate] = record
        if len(arcs)<2:continue
        try:
            network,rows,calibration = calibrate(data,candidate,arcs,weather,continuity=True,
                raw_covariance=raw_covariance,source_geometry=True)
            own = target_combinations(data,candidate,arcs,raw_covariance)
            own,joint,transport = attach(network,own)
            own,target = target_continuity(data,candidate,own)
            for a in own:a['mw_increment_mask'] = a['phase_increment_mask'].copy()
            profile = source_geometry.profile_wet(network,candidate)
            record.update(calibration=calibration,reference_rows=rows,source_profile=profile,
                transport={**transport,'target_continuity':target},future_links={
                    'clock_only':network_closures.prepare_future_links(rows,candidate,raw_covariance),
                    'wet_source':network_closures.prepare_future_links(rows,candidate,raw_covariance,wet_sources=True)})
            record['variants']['joint_independent'] = estimate(candidate,'joint_independent',own,joint,calibration['status'])
            fitted = record['variants']['joint_independent']['fit']
            if 'state_ecef_m_m_s' not in fitted:raise ValueError('nominal trajectory unavailable for source response')
            details,_,_ = linear_response(fitted,own,joint)
            response = details['full_observation_response'][:6]
            names = profile['stations']
            requests = clock_requests(own)
            clock_source = source_geometry.clock_wet_response(network,requests,candidate,names)
            target_source = target_wet_design(fitted,own,weather,names)
            combined = source_geometry.coupled_response(response,transport['clock_observation_indices'],clock_source,target_source,names)
            record.update(full_state_observation_response=response,clock_source_response=clock_source,
                target_source_model_design=target_source,
                target_source_design_units='code metres/zenith metre; IF phase-rate (m/s)/zenith metre; MW/clock/ground zero',
                clock_requests=[[[s,t,c] for (s,t),c in r.items()] for r in requests],
                clock_request_output_units=['m','m/s','m/s']*(len(requests)//3),source_response=combined)
            if combined['status']!='SOURCE_PROBE_PREPARED':
                for label in labels[1:]:record['variants'][label]['fit'] = {'status':'NO_RESOLVED_SOURCE_POSITION_PROBE'}
                continue
            probe = combined['zenith_probe_m']
            vector = np.array([probe[s] for s in names])
            ref_path = np.concatenate([(source_geometry.wet_design(b,names)@vector)[:len(b['rows'])] for b in network['blocks']])
            record['probe_reference_path_rms_m'] = float(np.sqrt(np.mean(ref_path**2)))
            record['probe_reference_path_peak_m'] = float(max(abs(ref_path)))
            recalibrated = None
            try:
                centres = {(s,b['time_s']):float(b['parameters'][j]) for b in network['blocks'] for j,s in enumerate(b['stations'])}
                recalibrated,newrows,recalibration = calibrate(data,candidate,arcs,weather,centres=centres,
                    continuity=True,raw_covariance=raw_covariance,source_geometry=True,zenith_wet_m=probe)
                keys = lambda own: [(r['station'],r['reference'],r['time_s'],r['segment']) for r in own]
                if keys(rows)!=keys(newrows):raise ValueError('reference support/segments changed under source probe')
                changed,recomputed,updated = attach(recalibrated,own)
                chol = np.linalg.cholesky(transport['clock_covariance'])
                difference = updated['clock_covariance']-transport['clock_covariance']
                relative = np.linalg.solve(chol,np.linalg.solve(chol,difference).T).T
                record['reference_source_calibration'] = {**recalibration,'support_and_segments_preserved':True,
                    'clock_measurement_change':updated['clock_mean']-transport['clock_mean'],
                    'fixed_linear_clock_change':-clock_source@vector,
                    'nominal_weight_whitened_clock_covariance_change_max':float(np.max(abs(relative))),
                    'minimum_reference_total_zenith_wet_m':{s:min(r['zenith_wet_m'] for r in newrows if r['station']==s) for s in names}}
                # Hold the declared trajectory weighting metric fixed. A new
                # noise law is not inferred from relinearized clock geometry.
                for a,nominal in zip(changed,own,strict=True):a['covariance'] = nominal['covariance']
            except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                recalibrated = None
                record['reference_source_calibration'] = {'status':'SOURCE_CALIBRATION_FAILED','reason':str(error)}
            for label in labels[1:]:
                reference = label!='candidate_only'
                candidate_path = label!='reference_only'
                if reference and recalibrated is None:
                    record['variants'][label]['fit'] = {'status':'SOURCE_CALIBRATION_FAILED',
                        'reason':record['reference_source_calibration']['reason']}
                    continue
                trial = [{**a} for a in (changed if reference else own)]
                if candidate_path:
                    for a in trial:a['propagation'] = fixed_wet_propagation(weather,a['stations'],probe)
                variant = estimate(candidate,label,trial,joint,
                    recalibration['status'] if reference else calibration['status'],probe if candidate_path else None)
                variant['probe'] = {'target_weight_covariance_fixed_at_nominal':True,
                    'reference_observation_time_relinearized':reference,
                    'candidate_wet_geometry_recomputed_each_trial':candidate_path,
                    'linear_state_change_m_m_s':combined['linear_probe_state_change_m_m_s'][label]}
                if 'state_ecef_m_m_s' in variant['fit']:
                    delta = np.asarray(variant['fit']['state_ecef_m_m_s'])-fitted['state_ecef_m_m_s']
                    variant['probe'].update(finite_state_change_m_m_s=delta,
                        finite_minus_linear_state_change_m_m_s=delta-combined['linear_probe_state_change_m_m_s'][label])
                record['variants'][label] = variant
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            record['preparation_failure'] = str(error)
            for v in record['variants'].values():
                if v['fit']['status']=='INSUFFICIENT_PREPARED_ARCS':
                    v['fit'] = {'status':'SOURCE_PREPARATION_UNAVAILABLE','reason':str(error)}
    # All fitted source models, finite interventions and predictions precede
    # both reference-link and candidate-RF scoring; no CODE scoring is called.
    for candidate,record in results.items():
        for label,predictions in record.get('future_links',{}).items():
            record['future_links'][label] = network_closures.score_future_links(predictions,record['reference_rows'])
        for variant in record['variants'].values():
            variant['rf_evaluation'] = baseline.score_rf(data,candidate,variant['rf_predictions'])
            variant['mw_evaluation'] = score_mw(data,candidate,variant['rf_predictions'])
    modules = [baseline,baseline.interval,baseline.interval.shared,wet,dynamic_fit,network_clocks,
        phase_continuity,gnss_combinations,temporal_contrasts,network_closures,source_geometry,
        baseline.dynamics,baseline.interval.clock_observations,baseline.precise,baseline.attitude,baseline.bias,
        baseline.conventions,baseline.sp3,baseline.day,baseline.day.atmosphere,baseline.interval.shared.meteo]
    sources = [Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema':'exposed-wet-source-coupling-v1',
        'scope':'Exposed constant station wet geometry; reference-only profile and future-link prediction; fixed coherent wet-model probe through calibration and candidate paths, separately and jointly.',
        'candidate_products_used_in_own_fit':False,'candidate_rf_used_in_own_network':False,
        'candidate_code_orbit_scoring':False,'g12_state_accessed':False,'oracle_tuning':False,
        'all_predictions_before_scoring':True,'new_confirmation':False,
        'physical_covariance_qualified':False,'physical_wet_model_qualified':False,
        'production_floors_changed':False,'target_weights_fixed_at_nominal':True,
        'source_estimates_used_as_candidate_corrections':False,
        'probe_rms_m':source_geometry.PROBE_RMS_M,'probe_amplitude_is_sigma':False,
        'probe_coordinates':'one coherent zenith-wet metre coordinate per reference station, not link metres',
        'raw_endpoint_weight_covariance_m2':raw_covariance,
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,
        'input_sha256':{k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'fit_status_counts':{label:dict(Counter(c['variants'][label]['fit']['status'] for c in results.values())) for label in labels},
        'candidates':results})


def run_closures():
    """Reference closures, future-link predictions and finite state responses."""
    raw,data = baseline.read_inputs()
    weather = baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    raw_covariance = gnss_combinations.assumed_endpoint_covariance()
    results = {}
    labels = ('joint_independent','clock_blind','cycle_visible')
    def estimate(candidate,label,own,joint,reference_status):
        try:
            fitted = dynamic_fit.fit(own,joint_covariance=joint,
                progress=lambda r:print(candidate,label,r,flush=True))
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            fitted = {'status':'FIT_FAILED','reason':str(error)}
        fitted['reference_calibration_status'] = reference_status
        if reference_status=='CONDITIONAL_MODEL_REJECTED':
            fitted['algebraic_target_fit_status'] = fitted['status']
            fitted['status'] = 'REFERENCE_CALIBRATION_MODEL_REJECTED'
        predictions = predict_combinations(fitted,own,weather)
        return {'fit':fitted,'rf_predictions':predictions,
            'prediction_sha256':baseline.interval.shared.digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode())}
    for candidate in data['plan']['references']:
        print(candidate,'prepare nondispersive closures',flush=True)
        try:
            arcs,windows = baseline.build_arcs(data,candidate,weather)
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            arcs,windows = [],baseline.coverage(data,candidate)
            for w in windows:
                if w['status']=='RF_COVERED':
                    w.update(status='CANDIDATE_PREPARATION_FAILED',reason=str(error))
        record = {'windows':native(windows),'prepared_arc_count':len(arcs),'variants':{
            label:{'fit':{'status':'INSUFFICIENT_PREPARED_ARCS','arc_count':len(arcs)},
                   'rf_predictions':[],'prediction_sha256':baseline.interval.shared.digest(b'[]')}
            for label in labels}}
        results[candidate] = record
        if len(arcs)<2:
            continue
        try:
            network,rows,calibration = calibrate(data,candidate,arcs,weather,continuity=True,raw_covariance=raw_covariance)
            own = target_combinations(data,candidate,arcs,raw_covariance)
            own,joint,transport = attach(network,own)
            own,target = target_continuity(data,candidate,own)
            for a in own:a['mw_increment_mask'] = a['phase_increment_mask'].copy()
            record.update(calibration=calibration,reference_rows=rows,transport={**transport,'target_continuity':target},
                closures=network_closures.closure_records(network,candidate),
                future_links=network_closures.prepare_future_links(rows,candidate,raw_covariance))
            record['variants']['joint_independent'] = estimate(candidate,'joint_independent',own,joint,calibration['status'])
            fitted = record['variants']['joint_independent']['fit']
            if 'state_ecef_m_m_s' not in fitted:
                raise ValueError('baseline trajectory unavailable for calibration/state response')
            details,_,_ = linear_response(fitted,own,joint)
            response = details['full_observation_response'][:6]
            requests = clock_requests(own)
            indices = transport['clock_observation_indices']
            record['state_response_to_clock_measurements'] = response[:,indices]
            record['clock_requests'] = [[[s,t,c] for (s,t),c in r.items()] for r in requests]
            partition = network_closures.state_transfer(network,requests,candidate,response,indices)
            record['state_transfer'] = partition
            original = np.array([[r['code_closure_m'],r['phase_closure_m']] for r in record['closures']['rows']])
            flat = [r for b in network['blocks'] for r in b['rows']]
            for label,mode in partition['modes'].items():
                if mode['status']!='PROBE_PREPARED':
                    record['variants'][label]['fit'] = {'status':'NO_RESOLVED_POSITION_PROBE'}
                    continue
                try:
                    perturbed = [{**r,'code_m':r['code_m']+float(delta),'phase_m':r['phase_m']+float(delta)}
                        for r,delta in zip(flat,mode['reference_change_m'],strict=True)]
                    recalibrated = network_clocks.fit(perturbed,raw_covariance=raw_covariance)
                    changed,covariance,updated = attach(recalibrated,own)
                    actual_closures = network_closures.closure_records(recalibrated,candidate)
                    actual = np.array([[r['code_closure_m'],r['phase_closure_m']] for r in actual_closures['rows']])
                    reference_status = 'CONDITIONAL_MODEL_REJECTED' if recalibrated['conditional_p'] < .01 else 'CONDITIONAL_MODEL_ONLY'
                    variant = estimate(candidate,label,changed,covariance,reference_status)
                    variant['probe'] = {'reference_observation_time_linearization_fixed':True,
                        'weights_and_covariance_preserved':bool(np.array_equal(joint,covariance)),
                        'clock_measurement_change_m':updated['clock_mean']-transport['clock_mean'],
                        'calibrated_closure_change_rms_m':np.sqrt(np.mean((actual-original)**2,axis=0)),
                        'calibrated_closure_change_max_m':np.max(abs(actual-original),axis=0),
                        'maximum_float_bias_change_m':float(max(abs(recalibrated['ambiguities_m']-network['ambiguities_m']))),
                        'reference_conditional_p':recalibrated['conditional_p'],
                        'reference_weighted_cost_change':recalibrated['weighted_cost']-network['weighted_cost']}
                    if 'state_ecef_m_m_s' in variant['fit']:
                        change = np.asarray(variant['fit']['state_ecef_m_m_s'])-fitted['state_ecef_m_m_s']
                        variant['probe'].update(finite_state_change_m_m_s=change,
                            finite_minus_linear_state_change_m_m_s=change-mode['linear_state_change_m_m_s'])
                    record['variants'][label] = variant
                except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                    record['variants'][label]['fit'] = {'status':'PROBE_FAILED','reason':str(error)}
        except (ValueError,KeyError,np.linalg.LinAlgError) as error:
            record['preparation_failure'] = str(error)
            for variant in record['variants'].values():
                if variant['fit']['status']=='INSUFFICIENT_PREPARED_ARCS':
                    variant['fit'] = {'status':'CLOSURE_PREPARATION_UNAVAILABLE','reason':str(error)}
    # Every estimate, response, finite probe and prediction is fixed before
    # excluded reference or candidate RF scoring. No candidate CODE is opened.
    for candidate,record in results.items():
        if 'future_links' in record:
            record['future_links'] = network_closures.score_future_links(record['future_links'],record['reference_rows'])
        for variant in record['variants'].values():
            variant['rf_evaluation'] = baseline.score_rf(data,candidate,variant['rf_predictions'])
            variant['mw_evaluation'] = score_mw(data,candidate,variant['rf_predictions'])
    modules = [baseline,baseline.interval,baseline.interval.shared,dynamic_fit,network_clocks,
        phase_continuity,gnss_combinations,temporal_contrasts,network_closures,
        baseline.dynamics,baseline.precise,baseline.attitude,baseline.bias,baseline.conventions,
        baseline.sp3,baseline.day,baseline.day.atmosphere,baseline.interval.shared.meteo]
    sources = [Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema':'exposed-nondispersive-network-closures-v1',
        'scope':'Exposed reference-only calibrated closure and conditional future-link IF prediction; reference-only coherent error sensitivities through recalibration and fresh trajectory fits.',
        'candidate_products_used_in_own_fit':False,'candidate_rf_used_in_own_network':False,
        'candidate_code_orbit_scoring':False,'g12_state_accessed':False,'oracle_tuning':False,
        'all_predictions_before_scoring':True,'new_confirmation':False,
        'physical_covariance_qualified':False,'production_floors_changed':False,
        'reference_observation_time_linearization_fixed':True,
        'probe_rms_m':network_closures.PROBE_RMS_M,'probe_amplitude_is_sigma':False,
        'raw_endpoint_weight_covariance_m2':raw_covariance,
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,
        'input_sha256':{k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'fit_status_counts':{label:dict(Counter(c['variants'][label]['fit']['status'] for c in results.values())) for label in labels},
        'candidates':results})


def run_structure():
    """Reference-only spatial qualification on the existing preparation cohort."""
    raw, data = baseline.read_inputs()
    weather = baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    results = {}
    for candidate in data['plan']['references']:
        print(candidate, 'prepare shared structure', flush=True)
        try:
            arcs, windows = baseline.build_arcs(data, candidate, weather)
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            arcs, windows = [], baseline.coverage(data, candidate)
            for w in windows:
                if w['status'] == 'RF_COVERED':
                    w.update(status='CANDIDATE_PREPARATION_FAILED', reason=str(error))
        record = {'windows': native(windows), 'prepared_arc_count': len(arcs),
                  'status': 'INSUFFICIENT_PREPARED_ARCS'}
        results[candidate] = record
        if len(arcs) < 2:
            continue
        try:
            rows, failures = reference_rows(data, candidate, max(a['endpoint_gpst_s'] for a in arcs),
                weather, continuity=True, combinations=True)
            # The common modeled range/clock term cancels algebraically. No
            # fitted reference mean or historical candidate state is required.
            admitted = [{k:r[k] for k in ('station', 'reference', 'time_s', 'segment', 'mw_m')}
                        | {'code_m':r['code_m']-r['phase_m'], 'phase_m':0.} for r in rows]
            record.update(status='REFERENCE_CONTRASTS_AVAILABLE', reference_rows=admitted,
                reference_preparation_failures=failures,
                structure=shared_error_structure.prepare(admitted, candidate))
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            record.update(status='REFERENCE_STRUCTURE_UNAVAILABLE', reason=str(error))
    # Every fold/partition predictor is frozen before excluded reference
    # scoring. Dedicated candidate RF and CODE scoring are never invoked.
    for record in results.values():
        if 'structure' in record:
            record['structure']['comparisons'] = {k:shared_error_structure.evaluate(v)
                for k,v in record['structure']['comparisons'].items()}
    modules = [baseline, baseline.interval, baseline.interval.shared, phase_continuity,
        gnss_combinations, temporal_contrasts, shared_error_structure, baseline.dynamics,
        baseline.precise, baseline.attitude, baseline.bias, baseline.conventions, baseline.sp3,
        baseline.day, baseline.day.atmosphere, baseline.interval.shared.meteo]
    sources = [Path(m.__file__) for m in modules]+[Path(__file__)]
    return native({'schema':'exposed-shared-error-structure-v1',
        'scope':'Exposed reference-only conditional cross-reference prediction; fixed GF masks and original snapshot preparation. No new orbital solution or prospective confirmation.',
        'candidate_products_used_in_own_fit':False, 'candidate_rf_used_in_own_network':False,
        'dedicated_candidate_rf_or_code_scoring':False, 'g12_state_accessed':False,
        'all_predictions_before_validation_scoring':True, 'oracle_tuning':False,
        'new_confirmation':False, 'physical_covariance_qualified':False,
        'production_floors_changed':False, 'new_candidate_trajectory_fit':False,
        'method':{'training_fraction':2/3, 'lags_s':shared_error_structure.LAGS,
            'delete_block_s':shared_error_structure.BLOCK_S,
            'models':['independent','positive_common','signed_cross_group'],
            'validation':'Contemporaneous excluded-reference group prediction at later epochs; future source-group RF is supplied, so this is not an RF-free temporal forecast.',
            'support_rule':'Positive cross eigenvalues in training and validation, all 300 s training block deletions positive, a PSD shared moment compatible with both split marginals and improved scaled validation loss in both directions. Descriptive conditional support, not a calibrated hypothesis test or physical raw covariance admission.'},
        'raw_identifiability':shared_error_structure.raw_identifiability(np.eye(2)),
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,
        'input_sha256':{k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'candidate_status_counts':dict(Counter(r['status'] for r in results.values())),
        'candidates':results})


def run(*, continuity=False, combinations=False, temporal=False, structure=False, closures=False, sources=False, separate=False, weak_sources=False, stable_sources=False):
    if stable_sources:
        return run_stable_sources()
    if weak_sources:
        return run_weak_sources()
    if separate:
        return run_separation()
    if sources:
        return run_sources()
    if closures:
        return run_closures()
    if structure:
        return run_structure()
    if temporal:
        continuity,combinations = True,True
    raw, data = baseline.read_inputs()
    weather = baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    results, prepared = {}, {}
    configurations = ([('network',False,False),('network_gf_segments',False,True),
                       ('network_gf_segments_free_phase_drift',True,True)] if continuity else
                      [('baseline',False,False),('network',False,False),('network_free_phase_drift',True,False)])
    raw_models = {}
    if combinations:
        continuity = True
        configurations = [('network_gf_segments',False,True),('joint_independent',False,True),
            ('joint_free_drift',True,True),('joint_correlated_code',False,True)]
        raw_models = {label:gnss_combinations.assumed_endpoint_covariance(code_correlation=rho)
                      for label,rho in [('joint_independent',0.),('joint_free_drift',0.),('joint_correlated_code',.5)]}
    if temporal:
        configurations = [(label,False,True) for label in (
            'joint_independent','temporal_code','temporal_shared','temporal_without_cross')]
        raw_models = {label:gnss_combinations.assumed_endpoint_covariance() for label,_,_ in configurations}
    for candidate in data['plan']['references']:
        print(candidate, 'prepare', flush=True)
        try:
            arcs, windows = baseline.build_arcs(data, candidate, weather)
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            arcs, windows = [], baseline.coverage(data, candidate)
            for w in windows:
                if w['status'] == 'RF_COVERED':
                    w.update(status='CANDIDATE_PREPARATION_FAILED', reason=str(error))
        prepared[candidate] = arcs
        record = {'windows': native(windows), 'variants': {}}
        calibrated = {}
        if len(arcs)>=2 and temporal:
            try:
                calibrated,records,model = prepare_temporal(data,candidate,arcs,weather)
                record.update(records)
                record['temporal_model'] = model
            except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                record['temporal_model'] = {'status':'REFERENCE_PREPARATION_FAILED','reason':str(error)}
        if len(arcs) >= 2 and not temporal:
            centres = None
            for label,drift,split in configurations:
                if label=='baseline':
                    continue
                try:
                    raw_covariance = raw_models.get(label)
                    network, rows, calibration = calibrate(data,candidate,arcs,weather,phase_drift=drift,
                        centres=centres,continuity=split,raw_covariance=raw_covariance)
                    centres = {(s,b['time_s']):b['parameters'][i]
                        for b in network['blocks'] for i,s in enumerate(b['stations'])}
                    own = target_combinations(data,candidate,arcs,raw_covariance,free_drift=drift) if raw_covariance is not None else arcs
                    own,joint,transport = attach(network,own)
                    if split:
                        own,target = target_continuity(data,candidate,own)
                        transport['target_continuity'] = target
                        for a in own:
                            if 'mw_rates_m_s' in a:
                                a['mw_increment_mask'] = a['phase_increment_mask'].copy()
                    calibrated[label] = (own,joint)
                    record[label] = {'calibration':calibration,'transport':transport,
                        'held_out_links':held_out_links(rows,phase_drift=drift,continuity=split,raw_covariance=raw_covariance)}
                    if not drift and not split:
                        record['injections'] = injection_checks(rows,arcs)
                except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                    # Publish a network only after its full preparation has
                    # succeeded. A later diagnostic error must not leave a
                    # cached calibration eligible for an orbit fit.
                    calibrated.pop(label,None)
                    failed = record.setdefault(label,{})
                    failed['calibration'] = {**failed.get('calibration',{}),
                        'status':'NETWORK_FAILED','reason':str(error)}
        for label,_,_ in configurations:
            own,joint = (arcs,None) if label=='baseline' else calibrated.get(label,(arcs,None))
            fit = {'status': 'INSUFFICIENT_PREPARED_ARCS', 'arc_count': len(arcs)}
            if len(arcs) >= 2:
                if label != 'baseline' and joint is None:
                    fit = {'status': 'COVARIANCE_UNAVAILABLE' if temporal and 'joint_independent' in calibrated else 'NETWORK_UNAVAILABLE'}
                else:
                    try:
                        options = {'joint_covariance': joint} if label != 'baseline' else {}
                        fit = dynamic_fit.fit(own, progress=lambda r: print(candidate,label,r,flush=True), **options)
                    except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                        fit = {'status': 'FIT_FAILED', 'reason': str(error)}
            if label != 'baseline' and label in record:
                calibration_status = record[label]['calibration']['status']
                fit['reference_calibration_status'] = calibration_status
                if calibration_status == 'CONDITIONAL_MODEL_REJECTED':
                    fit['algebraic_target_fit_status'] = fit['status']
                    fit['status'] = 'REFERENCE_CALIBRATION_MODEL_REJECTED'
            predictions = (predict_combinations(fit,own,weather) if combinations else baseline.interval.predict(fit, own, weather)) if own else []
            record['variants'][label] = {'fit': native(fit), 'observability': baseline.interval.observability(fit),
                'rf_predictions': predictions,
                'prediction_sha256': baseline.interval.shared.digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode())}
            if joint is not None:
                try:
                    record['variants'][label]['information'] = information(fit,own,joint)
                except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                    record['variants'][label]['information'] = {'status':'INFORMATION_FAILED','reason':str(error)}
        results[candidate] = native(record)
    # All candidates' estimates, conditional covariance and predictions fixed
    # before opening any candidate products for dedicated scoring.
    for candidate, record in results.items():
        for variant in record['variants'].values():
            variant['rf_evaluation'] = baseline.score_rf(data,candidate,variant['rf_predictions'])
            if combinations:
                variant['mw_evaluation'] = score_mw(data,candidate,variant['rf_predictions'])
            variant['state_evaluation'] = {'status': 'FIT_UNAVAILABLE', 'rows': []}
            if 'state_ecef_m_m_s' in variant['fit']:
                try:
                    variant['state_evaluation'] = baseline.state_errors(variant['fit'],prepared[candidate],baseline.oracle(data,candidate))
                except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                    variant['state_evaluation'] = {'status':'ORACLE_UNAVAILABLE','reason':str(error),'rows':[]}
    modules = [baseline, baseline.interval, baseline.interval.shared, dynamic_fit, network_clocks, phase_continuity,gnss_combinations,temporal_contrasts,shared_rf_covariance,
        baseline.dynamics, baseline.precise, baseline.attitude, baseline.bias, baseline.conventions,
        baseline.sp3, baseline.day, baseline.day.atmosphere, baseline.interval.shared.meteo]
    sources = [Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema': 'exposed-temporal-shared-rf-v1' if temporal else 'exposed-joint-rf-combinations-v1' if combinations else 'exposed-reference-phase-continuity-v1' if continuity else 'exposed-reference-network-clocks-v1',
        'scope': 'Exposed paired 22-candidate/440-window development. Free network reference-clock errors, float segment code/phase biases, joint offset/increment/cross-arc covariance; zero-mean reference-error datum. Optional joint IF/MW likelihood profiles free link-epoch ionosphere out of GF. Conditional measurement model only, not independent truth or absolute clock/total uncertainty qualification.',
        'candidate_products_used_in_own_fit': False, 'candidate_rf_used_in_own_network': False,
        'g12_state_accessed': False, 'oracle_tuning': False, 'all_predictions_before_scoring': True,
        'new_confirmation': False, 'physical_covariance_qualified': False, 'production_floors_changed': False,
        'reference_endpoint_weight_sigmas_m': {'code':20.,'phase':.02},
        'geometry_free_segmentation':continuity,
        **({'temporal_model':{'code_shape_source':'normalized D/MW variograms, first 2/3 reference times; last 1/3 validation only',
            'fit_lags_s':[30,60,90,120],'diagnostic_lag_s':300,'code_rho_range':[0,.99],
            'phase_endpoint_correlation':0.,'receiver_shared_fraction_sensitivity':.5,
            'historical_marginal_weights_preserved':True,'physical_covariance_qualified':False,
            'reference_estimator_weights_changed':False,'reference_target_cross_ablation_retained':True,
            'hyperparameter_uncertainty_propagated':False}}
           if temporal else {}),
        **({'raw_covariance_scenarios_m2':raw_models,'combination_transform':gnss_combinations.transform(),
            'raw_channel_order':['P1_m','P2_m','phase1_m','phase2_m'],
            'combination_order':['IF_code_m','IF_phase_m','GF_phase_m','MW_m'],
            'gf_model':'free link-epoch ionosphere; profile GF and retain marginal IF/MW covariance',
            'raw_covariance_qualified':False,'mw_bias_stability_qualified':False}
            if combinations else {}),
        **({'continuity_rule':{'source':phase_continuity.SOURCE,'history':phase_continuity.HISTORY,
            'warmup':'first difference','threshold':'1.5*(lambda2-lambda1)*(1-.5*exp(-dt/60))',
            'maximum_gap_s':phase_continuity.MAX_GAP_S,'physical_detection_qualified':False,
            'integer_slip_repair':False,'heldout_own_phase_used_for_segmentation':False}}
           if continuity else {}),
        'phase_bias_variants':('Constant reference IF-phase/MW segment biases and constant candidate MW arc bias in every variant; only covariance hypotheses change.' if temporal else 'Reference IF-phase and MW constant segment biases versus additional unpenalized linear drifts in m/hour. Candidate MW constant arc bias (zero rate) versus free receiver/arc MW rate; candidate IF code bias remains constant. No amplitude prior or oracle selection.' if combinations else 'constant float per segment versus additional unpenalized link-linear drift in m/hour; no amplitude prior or oracle selection'),
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,
        'execution_note':('New exploratory temporal/shared covariance comparison. Reference means retain fixed historical weights; full linearized estimator response including ambiguities transports declared raw covariance into RF and clock data. Receiver fraction .5 is an unqualified sensitivity, not a fitted positive shared component. All variants retained; historical artifacts unchanged.' if temporal else 'New exploratory joint IF/GF/MW comparison: refreshed GF baseline, independent equal-band raw noise with constant or free-linear biases, and code-correlation sensitivity rho=0.5. All variants retained; historical network and continuity artifacts unchanged.' if combinations else 'New exploratory continuity comparison, all variants retained; historical network v1 and corrections unchanged.' if continuity else 'Initial development run interrupted during G06 preparation after two G05 algebraic fits, before RF/CODE scoring, to include free phase drift and held-out network links. No completed artifact or historical outcome was replaced.'),
        'unqualified_sources': ['common reference-clock datum','reference orbit/attitude/phase bias stability',
            'unflagged phase continuity','phase wind-up and receiver code/phase bias drift',
            'terrestrial coordinates/propagation/dynamics and shared reference-target covariance',
            *(['raw inter-band, temporal and inter-link noise covariance; MW bias stability'] if combinations else [])],
        'input_sha256': {k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256': {p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'fit_status_counts': {v:dict(Counter(r['variants'][v]['fit']['status'] for r in results.values())) for v,_,_ in configurations},
        'candidates': results})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--continuity',action='store_true',help='compare geometry-free segmentation through reference and target paths')
    parser.add_argument('--combinations',action='store_true',help='joint IF/GF/MW raw-covariance and temporal-bias comparison')
    parser.add_argument('--temporal',action='store_true',help='reference-informed temporal shape and shared raw RF covariance transport')
    parser.add_argument('--structure',action='store_true',help='qualify shared differential error structure on excluded references')
    parser.add_argument('--closures',action='store_true',help='nondispersive calibrated network closures and complete state response')
    parser.add_argument('--sources',action='store_true',help='station wet source geometry through reference and candidate paths')
    parser.add_argument('--separate',action='store_true',help='joint wet, emitted reference orbit/antenna shapes and stable bias identifiability')
    parser.add_argument('--stable-sources',action='store_true',help='stable differential source recovery and complementary independent-observation designs')
    parser.add_argument('--weak-sources',action='store_true',help='weak-source stability, finite physical recovery and hypothetical independent information')
    args = parser.parse_args()
    if args.stable_sources and (args.weak_sources or args.separate or args.sources or args.closures or args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--stable-sources is a separate differential and source-information analysis')
    if args.weak_sources and (args.separate or args.sources or args.closures or args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--weak-sources is a separate physical recovery analysis')
    if args.separate and (args.sources or args.closures or args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--separate is a separate joint source analysis')
    if args.sources and (args.closures or args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--sources is a separate source-geometry analysis')
    if args.closures and (args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--closures is a separate calibration/state-response analysis')
    if args.structure and (args.temporal or args.combinations or args.continuity):
        parser.error('--structure is a separate reference-only analysis')
    if args.output.exists():
        parser.error('output exists; preserve previous results')
    result = run(continuity=args.continuity,combinations=args.combinations,temporal=args.temporal,structure=args.structure,closures=args.closures,sources=args.sources,separate=args.separate,weak_sources=args.weak_sources,stable_sources=args.stable_sources)
    payload = (json.dumps(result,separators=(',',':'),allow_nan=False)+'\n').encode()
    if args.output.suffix == '.gz':
        payload = gzip.compress(payload,mtime=0)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(payload)
