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

from . import reference_state_validation as baseline
from ..kinematic import dynamic_fit, network_clocks
from ..kinematic.synthetic import native


def reference_rows(data, candidate, stop, weather, centres=None):
    """Identity/time filtering precedes numeric product and RF arithmetic.

    Phase/code bias is free per flag/gap/mask-contiguous segment. No unflagged
    jump repair is performed; its network residual remains in the result.
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
                code = float(codes[station][t][q])+corrections[t, q]['if_code_change_m']
                if provider.model(q, code, t, xyz, 0.)[1] < 10.:
                    failures['BELOW_MASK'] += 1
                    continue
                centre = centres.get((station, t), 0.)
                def model(clock):
                    value, _ = provider.model(q, code, t, xyz, clock)
                    delay, _ = baseline.day.atmosphere.components(provider, weather, mjd, q, code, t, xyz, clock)
                    return value-delay['legacy_baseline']+delay['vmf3_full']
                value = model(centre)
                derivative = (model(centre+1.)-model(centre-1.))/2.
                if previous.get(key) != t-30:
                    segments[key] += 1
                previous[key] = t
                output.append({'station': station, 'reference': q, 'time_s': t,
                    'segment': f'{station}/{q}/{segments[key]}',
                    'code_m': code-value+derivative*centre,
                    'phase_m': float(row['phase_m'])-value+derivative*centre,
                    'clock_derivative': 1.+derivative,
                    'geometry_free_phase_m': float(row['geometry_free_phase_m'])})
            except (KeyError, ValueError) as error:
                failures[type(error).__name__+': '+str(error)] += 1
    return output, dict(failures)


def calibrate(data, candidate, arcs, weather, *, phase_drift=False, centres=None):
    stop = max(a['endpoint_gpst_s'] for a in arcs)
    centres, iterations = ({} if centres is None else centres), []
    for iteration in range(4):
        rows, failures = reference_rows(data, candidate, stop, weather, centres)
        network = network_clocks.fit(rows,phase_drift=phase_drift)
        updated = {(s, b['time_s']): b['parameters'][i]
                   for b in network['blocks'] for i, s in enumerate(b['stations'])}
        change = max(abs(v-centres.get(k, 0.)) for k, v in updated.items())
        iterations.append({'iteration': iteration, 'maximum_clock_change_m': change})
        print(candidate,'network drift='+str(phase_drift),iterations[-1],flush=True)
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
        'phase_drift': phase_drift, 'drift_coefficients_m_per_hour': {
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
        'residuals': network['residuals']}


def held_out_links(rows, *, phase_drift=False):
    """Deterministic link-epoch withholding, never a source of tuned weights.

    Withholding an entire epoch cannot be predicted by free epoch clocks;
    report that structural failure instead of silently adding a time prior.
    """
    training = [r for i,r in enumerate(rows) if i%7]
    withheld = [r for i,r in enumerate(rows) if not i%7]
    try:
        network = network_clocks.fit(training,phase_drift=phase_drift)
    except (ValueError,np.linalg.LinAlgError) as error:
        return {'status':'HELD_OUT_NETWORK_FAILED','reason':str(error),'withheld_count':len(withheld)}
    blocks = {b['time_s']:b for b in network['blocks']}
    segments = {s:i for i,s in enumerate(network['segments'])}
    records = []
    for r in withheld:
        record = {k:r[k] for k in ('time_s','station','reference','segment')}
        if phase_drift and r['segment'] in segments and r['segment'] not in network['drift_index']:
            # A singleton training segment estimates only its phase level.
            # Omitting its zero design column does not measure its slope.
            record['status'] = 'UNIDENTIFIABLE_PHASE_DRIFT'
            records.append(record)
            continue
        try:
            b = blocks[r['time_s']]
            i,j = b['stations'].index(r['station']),b['references'].index(r['reference'])
            clocks = b['parameters']
            predicted = r.get('clock_derivative',1.)*clocks[i]-b['reference_basis'][j]@clocks[len(b['stations']):]
            ambiguity = network['ambiguities_m'][segments[r['segment']]]
            if r['segment'] in network['drift_index']:
                ambiguity += network['ambiguities_m'][network['drift_index'][r['segment']]]*(
                    r['time_s']-network['segment_start_s'][r['segment']])/3600.
            record.update(status='EVALUATED',code_error_m=r['code_m']-predicted,
                phase_error_m=r['phase_m']-predicted-ambiguity)
        except (KeyError,ValueError):
            record['status'] = 'UNOBSERVED_CLOCK_OR_SEGMENT'
        records.append(record)
    return {'status':'RELATIVE_SHARED_PRODUCT_DIAGNOSTIC','rows':records,
        'status_counts':dict(Counter(r['status'] for r in records)),
        'code_error_m':baseline.interval.diagnostic.moments([r['code_error_m'] for r in records if r['status']=='EVALUATED']),
        'phase_error_m':baseline.interval.diagnostic.moments([r['phase_error_m'] for r in records if r['status']=='EVALUATED']),
        'whole_time_block_prediction':'UNIDENTIFIABLE_WITH_FREE_EPOCH_CLOCKS',
        'future_clock_rule':'retain the fitted arc mean; no network future data or quadratic extrapolation'}


def held_out_support_correction(result, original_sha256):
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
        invalid,valid,statuses = [],[],Counter()
        for r in held:
            if r['status']=='EVALUATED' and len(times.get(r['segment'],set()))==1:
                invalid.append({k:r[k] for k in ('time_s','station','reference','segment')})
                statuses['UNIDENTIFIABLE_PHASE_DRIFT'] += 1
            else:
                statuses[r['status']] += 1
                if r['status']=='EVALUATED':
                    valid.append(r)
        candidates[candidate] = {'invalidated_rows':invalid,'status_counts':dict(statuses),
            'code_error_m':baseline.interval.diagnostic.moments([r['code_error_m'] for r in valid]),
            'phase_error_m':baseline.interval.diagnostic.moments([r['phase_error_m'] for r in valid])}
    sources = [Path(__file__),Path(baseline.interval.diagnostic.__file__)]
    return native({'schema':'reference-network-heldout-support-correction-v1',
        'scope':'Invalidate four v1 free-drift held-out link predictions whose segment has only one training time. Its phase slope is unidentifiable, not zero. All orbit fits, clock estimates/covariances, candidate RF forecasts and CODE diagnostics remain the original execution.',
        'original_result_sha256':original_sha256,
        'source_sha256':{p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'trajectories_or_candidate_predictions_changed':False,'new_fit_or_oracle_tuning':False,
        'candidates':candidates})


def information(fit, arcs, joint):
    if 'state_ecef_m_m_s' not in fit:
        return {'status':'FIT_UNAVAILABLE'}
    prepared,names,_ = dynamic_fit.prepare(arcs,True)
    scale = np.r_[dynamic_fit.STATE_SCALE,np.full(len(names)-1,100.)]
    point = np.r_[fit['state_ecef_m_m_s'],fit['bias_contrast_coefficients_m']]/scale
    locals_ = [np.r_[p['satellite_clock'],np.asarray(p['receiver_clocks']).ravel(),
        np.asarray(p['station_corrections_m']).ravel()]/a['local_scale']
        for p,a in zip(fit['arc_parameters'],prepared,strict=True)]
    details = {}
    _,_,_,cov,_,_ = dynamic_fit.linearize(point,locals_,prepared,scale,fit['epoch_gpst_s'],
        fit['integrated_bounds_s'],fit['j2'],joint_chol=np.linalg.cholesky(joint),diagnostics=details)
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


def attach(network, arcs):
    """Replace conditional clock data jointly; keep candidate RF/ground floors.

    The zero-mean reference-error datum is explicit in the network result.
    Its arbitrary common error has no inferred physical amplitude here.
    """
    arcs = [{**a} for a in sorted(arcs, key=lambda a: a['endpoint_gpst_s'])]
    requests = []
    for a in arcs:
        t = a['endpoint_gpst_s']
        for s in a['stations']:
            requests.extend([{(s, t): 1.}, {(s, t): 1/60., (s, t-60): -1/60.},
                {(s, t-30): 1/30., (s, t-60): -1/60., (s, t): -1/60.}])
    means, clock_covariance = network_clocks.clock_coefficients(network, requests)
    joint = block_diag(*[a['covariance'] for a in arcs])
    clock_indices, at, ct = [], 0, 0
    for a in arcs:
        n = len(a['stations'])
        a['clock_mean'] = means[ct:ct+3*n].reshape(n, 3)
        indices = np.arange(at+5*n, at+8*n)
        clock_indices.extend(indices)
        own = np.array(a['covariance'], copy=True)
        own[5*n:8*n, 5*n:8*n] = clock_covariance[ct:ct+3*n, ct:ct+3*n]
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


def run():
    raw, data = baseline.read_inputs()
    weather = baseline.interval.shared.meteo.WeatherGrid(baseline.interval.shared.meteo.read_inputs()[0])
    results, prepared = {}, {}
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
        if len(arcs) >= 2:
            centres = None
            for label,drift in [('network',False),('network_free_phase_drift',True)]:
                try:
                    network, rows, calibration = calibrate(data,candidate,arcs,weather,phase_drift=drift,centres=centres)
                    centres = {(s,b['time_s']):b['parameters'][i]
                        for b in network['blocks'] for i,s in enumerate(b['stations'])}
                    own,joint,transport = attach(network,arcs)
                    calibrated[label] = (own,joint)
                    record[label] = {'calibration':calibration,'transport':transport,
                        'held_out_links':held_out_links(rows,phase_drift=drift)}
                    if not drift:
                        record['injections'] = injection_checks(rows,arcs)
                except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                    record[label] = {'calibration':{'status':'NETWORK_FAILED','reason':str(error)}}
        for label in ('baseline','network','network_free_phase_drift'):
            own,joint = (arcs,None) if label=='baseline' else calibrated.get(label,(arcs,None))
            fit = {'status': 'INSUFFICIENT_PREPARED_ARCS', 'arc_count': len(arcs)}
            if len(arcs) >= 2:
                if label != 'baseline' and joint is None:
                    fit = {'status': 'NETWORK_UNAVAILABLE'}
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
            predictions = baseline.interval.predict(fit, own, weather) if own else []
            record['variants'][label] = {'fit': native(fit), 'observability': baseline.interval.observability(fit),
                'rf_predictions': predictions,
                'prediction_sha256': baseline.interval.shared.digest(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode())}
            if joint is not None:
                record['variants'][label]['information'] = information(fit,own,joint)
        results[candidate] = native(record)
    # All candidates' estimates, conditional covariance and predictions fixed
    # before opening any candidate products for dedicated scoring.
    for candidate, record in results.items():
        for variant in record['variants'].values():
            variant['rf_evaluation'] = baseline.score_rf(data,candidate,variant['rf_predictions'])
            variant['state_evaluation'] = {'status': 'FIT_UNAVAILABLE', 'rows': []}
            if 'state_ecef_m_m_s' in variant['fit']:
                try:
                    variant['state_evaluation'] = baseline.state_errors(variant['fit'],prepared[candidate],baseline.oracle(data,candidate))
                except (ValueError,KeyError,np.linalg.LinAlgError) as error:
                    variant['state_evaluation'] = {'status':'ORACLE_UNAVAILABLE','reason':str(error),'rows':[]}
    modules = [baseline, baseline.interval, baseline.interval.shared, dynamic_fit, network_clocks,
        baseline.dynamics, baseline.precise, baseline.attitude, baseline.bias, baseline.conventions,
        baseline.sp3, baseline.day, baseline.day.atmosphere, baseline.interval.shared.meteo]
    sources = [Path(m.__file__) for m in modules]+[Path(__file__),Path(inspect.getmodule(network_clocks.operators).__file__)]
    return native({'schema': 'exposed-reference-network-clocks-v1',
        'scope': 'Exposed paired 22-candidate/440-window development. Free network reference-clock errors, float segment code/phase biases, joint offset/increment/cross-arc covariance; zero-mean reference-error datum. Conditional measurement model only, not independent truth or absolute clock/total uncertainty qualification.',
        'candidate_products_used_in_own_fit': False, 'candidate_rf_used_in_own_network': False,
        'g12_state_accessed': False, 'oracle_tuning': False, 'all_predictions_before_scoring': True,
        'new_confirmation': False, 'physical_covariance_qualified': False, 'production_floors_changed': False,
        'reference_endpoint_weight_sigmas_m': {'code':20.,'phase':.02},
        'phase_bias_variants':'constant float per segment versus additional unpenalized link-linear drift in m/hour; no amplitude prior or oracle selection',
        'weather_receipt_sha256':baseline.interval.shared.meteo.RECEIPT_SHA,
        'execution_note':'Initial development run interrupted during G06 preparation after two G05 algebraic fits, before RF/CODE scoring, to include free phase drift and held-out network links. No completed artifact or historical outcome was replaced.',
        'unqualified_sources': ['common reference-clock datum','reference orbit/attitude/phase bias stability',
            'unflagged phase continuity','phase wind-up and receiver code/phase bias drift',
            'terrestrial coordinates/propagation/dynamics and shared reference-target covariance'],
        'input_sha256': {k:baseline.interval.shared.digest(v) for k,v in raw.items()},
        'source_sha256': {p.relative_to(baseline.BASE.parents[1]).as_posix():baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'fit_status_counts': {v:dict(Counter(r['variants'][v]['fit']['status'] for r in results.values())) for v in ('baseline','network','network_free_phase_drift')},
        'candidates': results})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; preserve previous results')
    result = run()
    payload = (json.dumps(result,separators=(',',':'),allow_nan=False)+'\n').encode()
    if args.output.suffix == '.gz':
        payload = gzip.compress(payload,mtime=0)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('xb') as stream:
        stream.write(payload)
