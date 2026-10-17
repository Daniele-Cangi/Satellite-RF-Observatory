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

from . import reference_state_validation as baseline, reference_wet_fit as wet
from ..kinematic import dynamic_fit, network_clocks, phase_continuity, gnss_combinations, temporal_contrasts, shared_rf_covariance, shared_error_structure, network_closures, source_geometry
from ..kinematic.synthetic import native


def reference_rows(data, candidate, stop, weather, centres=None, *, continuity=False, combinations=False,
                   source_geometry=False, zenith_wet_m=None):
    """Identity/time filtering precedes numeric product and RF arithmetic.

    Phase/code bias is free per flag/gap/mask-contiguous segment. The optional
    GF witness splits a segment without repairing any observed phase value.
    """
    refs = [q for q in data['plan']['references'] if q != candidate]
    provider, corrections = baseline.subset_products(data, refs, candidate)
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
                code = float(codes[station][t][q])+corrections[t, q]['if_code_change_m']
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
                if combinations:
                    raw = gnss_combinations.values(row['fields'],code1_change_m=
                        corrections[t,q]['if_code_change_m']/gnss_combinations.ALPHA)
                    if abs(raw[0]-code)>1e-5:
                        raise ValueError('raw/day IF code mismatch')
                    record['mw_m'] = raw[3]
                output.append(record)
            except (KeyError, ValueError) as error:
                failures[type(error).__name__+': '+str(error)] += 1
    return phase_continuity.segment(output) if continuity else output, dict(failures)


def calibrate(data, candidate, arcs, weather, *, phase_drift=False, centres=None, continuity=False, raw_covariance=None,
              source_geometry=False, zenith_wet_m=None):
    stop = max(a['endpoint_gpst_s'] for a in arcs)
    centres, iterations = ({} if centres is None else centres), []
    for iteration in range(4):
        rows, failures = reference_rows(data, candidate, stop, weather, centres,
            continuity=continuity,combinations=raw_covariance is not None,
            **({'source_geometry':source_geometry,'zenith_wet_m':zenith_wet_m}
               if source_geometry or zenith_wet_m is not None else {}))
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


def run(*, continuity=False, combinations=False, temporal=False, structure=False, closures=False, sources=False):
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
    args = parser.parse_args()
    if args.sources and (args.closures or args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--sources is a separate source-geometry analysis')
    if args.closures and (args.structure or args.temporal or args.combinations or args.continuity):
        parser.error('--closures is a separate calibration/state-response analysis')
    if args.structure and (args.temporal or args.combinations or args.continuity):
        parser.error('--structure is a separate reference-only analysis')
    if args.output.exists():
        parser.error('output exists; preserve previous results')
    result = run(continuity=args.continuity,combinations=args.combinations,temporal=args.temporal,structure=args.structure,closures=args.closures,sources=args.sources)
    payload = (json.dumps(result,separators=(',',':'),allow_nan=False)+'\n').encode()
    if args.output.suffix == '.gz':
        payload = gzip.compress(payload,mtime=0)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(payload)
