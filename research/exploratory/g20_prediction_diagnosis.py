"""Diagnose the conserved G20 failure; do not fit another corrective model.

Three checks: signed correction/error decomposition; one predeclared prefix
mask/measurement intervention; complete held-increment source null response.
Uses exposed RF, fixed geometry, native fits and original comparison support.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np

from research.kinematic import network_clocks, network_closures, source_geometry, phase_continuity, gnss_combinations
from research.exploratory.reference_network_clocks import native

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT/'research/exploratory/results/stable_source_differential_v1.json.gz'
ORIGINAL = ROOT/'research/exploratory/missnet-transfer-2026-10-19'
SHA = '56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020'


def increment_map(scored, lag=300.):
    return {(r['station'], r['reference'], r['time_s']):float(r['z'][1])
            for inc in scored.get('increment_errors', []) if inc['lag_s'] == lag for r in inc['rows']}


def correction_decomposition(baseline, corrected, support):
    e = np.array([baseline[tuple(k)] for k in support])
    c = e - np.array([corrected[tuple(k)] for k in support])
    return {'count':len(e), 'baseline_rms_m':float(np.sqrt(np.mean(e*e))),
        'corrected_rms_m':float(np.sqrt(np.mean((e-c)**2))),
        'correction_rms_m':float(np.sqrt(np.mean(c*c))),
        'error_correction_mean_product_m2':float(np.mean(e*c)),
        'correction_energy_m2':float(np.mean(c*c)),
        'delta_mse_m2':float(np.mean(c*c)-2*np.mean(e*c)),
        'worse_absolute_error_count':int(np.count_nonzero(abs(e-c)>abs(e)))}


def fitted(rows):
    training = phase_continuity.segment(rows)
    net = network_clocks.fit(training, raw_covariance=gnss_combinations.assumed_endpoint_covariance())
    _, workspace = source_geometry.profile_sources(net, 'G20', ('wet',))
    return training, net, workspace


def forecast(fit, query):
    training, net, workspace = fit
    row = next((r for r in training if all(r[k] == query[k] for k in ('station','reference','time_s'))), None)
    segment = row['segment'] if row else phase_continuity.withheld_segment(query, training)
    return source_geometry.source_link_prediction(net, workspace, query, segment)


def phase_source_map(net, workspace, row, segment):
    """The existing source_link_prediction phase row, including nuisance refits."""
    index = next(i for i,b in enumerate(net['blocks']) if b['time_s'] == row['time_s'])
    b = net['blocks'][index]
    a = np.zeros(len(b['parameters']))
    a[b['stations'].index(row['station'])] = row.get('clock_derivative', 1.)
    a[len(b['stations']):] = -b['reference_basis'][b['references'].index(row['reference'])]
    g = source_geometry.source_design([row], workspace['columns'])[1]
    k = net['segments'].index(segment)
    h = g - a@workspace['clock_response'][index] - workspace['ambiguity_response'][k]
    nominal = float(a@b['parameters'] + net['ambiguities_m'][k])
    return h, nominal


def main():
    start = time.perf_counter()
    raw = ARCHIVE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise ValueError('stable input hash mismatch')
    scores_raw = (ORIGINAL/'native-scores.json.gz').read_bytes()
    scores = json.loads(gzip.decompress(scores_raw))['G20']
    prior = json.loads((ORIGINAL/'original-comparison.json').read_bytes())
    support = prior['support']['300']['G20']
    result = {'kind':'exposed diagnostic, not a new forecast model or physical qualification',
        'case':'G20, original 261 held 300-second phase increments',
        'base_revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'input_sha256':SHA, 'score_input_sha256':hashlib.sha256(scores_raw).hexdigest(),
        'decomposition':correction_decomposition(increment_map(scores['wet']), increment_map(scores['observed_coordinates']), support)}
    rows = json.loads(gzip.decompress(raw))['candidates']['G20']['reference_rows']
    network_closures.admit(rows, 'G20')
    baseline = scores['wet']
    cut, held = baseline['training_stop_s'], set(map(tuple, baseline['held_links']))
    admitted = [r for r in rows if not ((r['station'],r['reference']) in held and r['time_s'] > cut)]
    # Fixed before reading these new diagnostic outcomes: last prefix epoch and
    # exactly 300 s earlier; all original hash-selected links, no substitutions.
    t1 = max(r['time_s'] for r in admitted if r['time_s'] <= cut)
    t0 = t1 - 300.
    queries = [r for r in admitted if (r['station'],r['reference']) in held and r['time_s'] in (t0,t1)]
    keys = {(r['station'],r['reference'],r['time_s']) for r in queries}
    masked = [r for r in admitted if (r['station'],r['reference'],r['time_s']) not in keys]
    perturbed = deepcopy(admitted)
    for row in perturbed:
        if (row['station'],row['reference'],row['time_s']) in keys:
            delta = .01 if row['time_s'] == t1 else -.01
            row['code_m'] += delta
            row['phase_m'] += delta
    full_fit, probe_fit, mask_fit = fitted(admitted), fitted(perturbed), fitted(masked)
    records = []
    for station, reference in sorted(held):
        pair = [next((r for r in queries if (r['station'],r['reference'],r['time_s']) == (station,reference,t)),None) for t in (t0,t1)]
        item = {'station':station,'reference':reference,'times_s':[t0,t1]}
        if any(r is None for r in pair) or pair[0]['base_segment'] != pair[1]['base_segment']:
            records.append({**item,'status':'MISSING_OR_DISCONTINUOUS_PREFIX_PAIR'})
            continue
        predictions = [[forecast(fit,r) for r in pair] for fit in (full_fit, probe_fit, mask_fit)]
        item['prediction_statuses'] = [[p['status'] for p in ps] for ps in predictions]
        if any(p['status'] != 'PREDICTED' for ps in predictions for p in ps):
            records.append({**item,'status':'UNSUPPORTED_PREFIX_PREDICTION'})
            continue
        observed_increment = pair[1]['phase_m'] - pair[0]['phase_m']
        increments = [ps[1]['phase_prediction_m']-ps[0]['phase_prediction_m'] for ps in predictions]
        records.append({**item,'status':'DIAGNOSED',
            'observed_training_residual_increment_m':float(observed_increment-increments[0]),
            'masked_prediction_error_increment_m':float(observed_increment-increments[2]),
            'in_sample_residual_response_to_20mm_intervention_m':float(.02-(increments[1]-increments[0])),
            'masked_error_response_to_same_removed_intervention_m':.02})
    result['prefix_diagnostic'] = {'rule':'last prefix epoch and 300 s earlier, all original held links',
        'prefix_times_s':[t0,t1],'removed_rows':len(queries),'records':records,
        'probe':'numerical nondispersive +/-10mm code+phase intervention; GF/MW unchanged, not a physical noise realization',
        'future_held_values_used_in_new_fits':False}
    # Full-model coefficient aliases are not automatically missing information
    # about the predicted increment. Test the actual output map on original keys.
    training, net, _ = full_fit
    profile, w = source_geometry.profile_sources(net,'G20',source_geometry.FAMILIES)
    prefix = {}
    for r in training:
        if r['time_s'] <= cut:
            prefix[r['station'],r['reference'],r['base_segment']] = r['segment']
    row_index = {(r['station'],r['reference'],r['time_s']):r for r in rows}
    nulls, gains, checks = [], [], []
    _, s, vt = np.linalg.svd(w['design'], full_matrices=False)
    rank = profile['resolved_rank']
    for station, reference, t in support:
        maps = []
        for time in (t-300., t):
            row = row_index[station,reference,time]
            segment = prefix[station,reference,row['base_segment']]
            h, nominal = phase_source_map(net,w,row,segment)
            p = source_geometry.source_link_prediction(net,w,row,segment)
            checks.append(abs(nominal+h@w['theta']-p['phase_prediction_m']))
            maps.append(h)
        h = maps[1]-maps[0]
        nulls.append(float(np.linalg.norm(h@w['null'])))
        gains.append(float(np.linalg.norm((h@vt[:rank].T)/s[:rank])))
    result['source_output_information'] = {'source_count':profile['source_count'],'resolved_rank':rank,
        'null_count':profile['null_count'],'increment_count':len(support),
        'maximum_phase_increment_null_response_m_per_m_source_norm':max(nulls),
        'weighted_training_error_to_phase_increment_gain_m':{'min':min(gains),'median':float(np.median(gains)),'max':max(gains)},
        'maximum_native_prediction_map_replay_error_m':float(max(checks)),
        'numerical_rank_tolerance':source_geometry.RTOL,
        'physical_noise_covariance_qualified':False}
    covariance = gnss_combinations.covariance(gnss_combinations.assumed_endpoint_covariance())
    result['weighting_scenario'] = {'if_phase_endpoint_sigma_m':float(np.sqrt(covariance[1,1])),
        'independent_unobserved_endpoint_increment_sigma_m':float(np.sqrt(2*covariance[1,1])),
        'interpretation':'Only the existing independent-error weighting scenario; not a measured irreducible-error bound or qualified physical covariance.'}
    result['elapsed_seconds'] = time.perf_counter()-start
    target = ROOT/'data/g20-prediction-diagnosis.json'
    target.parent.mkdir(exist_ok=True)
    with target.open('x',encoding='utf8') as handle:
        json.dump(native(result),handle,indent=2,allow_nan=False)
        handle.write('\n')
    print(json.dumps(native(result),indent=2))


if __name__ == '__main__':
    main()
