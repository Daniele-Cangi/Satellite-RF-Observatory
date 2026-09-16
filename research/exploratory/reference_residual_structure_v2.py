"""Guarded v2 replay of exploratory reference contrasts; frozen v1 is preserved."""
import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import combinations
import json
from pathlib import Path

import numpy as np

from positioning.calibration import C, OMEGA, geodetic, rotate_z
from .reference_attitude import load_attitude
from .reference_attitude_model import AttitudeReference, guarded_products, strict_json
from .reference_code_bias import translate_observations
from .reference_sensitivity import load_inputs

MODELS = ('zero', 'shared_satellite', 'station_direction', 'station_satellite')


def groups(rows):
    result = defaultdict(list)
    for i, row in enumerate(rows):
        result[(row['station'], row['time_s'])].append(i)
    return result


def center_blocks(values, rows):
    result = np.array(values, dtype=float, copy=True)
    for indices in groups(rows).values():
        result[indices] -= result[indices].mean(axis=0)
    return result


def features(row, model):
    if model == 'zero':
        return {}
    if model == 'shared_satellite':
        return {row['reference']: 1.}
    if model == 'station_satellite':
        return {row['station']+'/'+row['reference']: 1.}
    if model == 'station_direction':
        return {row['station']+'/'+axis: value for axis, value in zip('ENU', row['los_enu'])}
    raise ValueError('unknown residual model')


def design(rows, model, columns):
    index = {key: i for i, key in enumerate(columns)}
    result = np.zeros((len(rows), len(columns)))
    missing = np.zeros(len(rows), dtype=bool)
    for i, row in enumerate(rows):
        for key, value in features(row, model).items():
            if key not in index:
                missing[i] = True
            else:
                result[i, index[key]] = value
    return center_blocks(result, rows), missing


def rms(values):
    return float(np.sqrt(np.mean(np.square(values)))) if len(values) else None


def predict_block(training, testing, model):
    """Fit only training values; report unseen support and unidentifiable predictions."""
    if not training or not testing:
        raise ValueError('nonempty disjoint time blocks required')
    if {r['time_s'] for r in training} & {r['time_s'] for r in testing}:
        raise ValueError('training/test time overlap')
    columns = sorted({key for row in training for key in features(row, model)})
    x, missing = design(training, model, columns)
    if missing.any():
        raise ValueError('internal training support error')
    y = center_blocks([r['residual_m'] for r in training], training)
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    rank = int(np.sum(singular > singular[0]*1e-12)) if len(singular) else 0
    basis = vt[:rank]
    beta = basis.T@((u[:, :rank].T@y)/singular[:rank]) if rank else np.zeros(len(columns))
    test_x, missing = design(testing, model, columns)
    test_y = center_blocks([r['residual_m'] for r in testing], testing)
    # A minimum-norm coefficient vector is not sufficient to identify a new ray.
    defect = np.linalg.norm(test_x-(test_x@basis.T)@basis, axis=1)
    rows = []
    for indices in groups(testing).values():
        status = ('UNSEEN_TRAINING_SUPPORT' if missing[indices].any() else
                  'UNIDENTIFIABLE_PREDICTION' if np.any(defect[indices] > 1e-9*np.maximum(1., np.linalg.norm(test_x[indices], axis=1))) else
                  'PREDICTED')
        for i in indices:
            row = {key: testing[i][key] for key in ('station', 'time_s', 'reference')}
            row.update(status=status, observed_contrast_m=float(test_y[i]), prediction_m=None,
                       error_m=None, rowspace_defect=float(defect[i]))
            if status == 'PREDICTED':
                row['prediction_m'] = float(test_x[i]@beta)
                row['error_m'] = float(test_y[i]-row['prediction_m'])
            rows.append(row)
    good = [r for r in rows if r['status'] == 'PREDICTED']
    station_scores = []
    for station in sorted({r['station'] for r in rows}):
        selected = [r for r in rows if r['station'] == station]
        supported = [r for r in selected if r['status'] == 'PREDICTED']
        station_scores.append({'station': station, 'test_count': len(selected), 'predicted_count': len(supported),
                               'supported_error_rms_m': rms([r['error_m'] for r in supported]),
                               'supported_zero_rms_m': rms([r['observed_contrast_m'] for r in supported])})
    return {'model': model, 'training_count': len(training), 'test_count': len(testing),
            'predicted_count': len(good), 'status_counts': dict(Counter(r['status'] for r in rows)),
            'columns': columns, 'minimum_norm_coefficients_m': beta.tolist(), 'rank': rank,
            'nullity': len(columns)-rank, 'singular_values': singular.tolist(),
            'retained_condition_number': float(singular[0]/singular[rank-1]) if rank else None,
            'training_error_rms_m': rms(y-x@beta), 'supported_test_error_rms_m': rms([r['error_m'] for r in good]),
            'supported_test_zero_rms_m': rms([r['observed_contrast_m'] for r in good]),
            'all_test_error_rms_m': rms([r['error_m'] for r in good]) if len(good) == len(testing) else None,
            'station_scores': station_scores, 'test_predictions': rows}


def correlation(a, b):
    if len(a) != len(b):
        raise ValueError('correlation samples must align')
    if len(a) < 3:
        return {'status': 'INSUFFICIENT_SAMPLES', 'n': len(a), 'pearson': None, 'sample_covariance_m2': None}
    a, b = np.asarray(a)-np.mean(a), np.asarray(b)-np.mean(b)
    aa, bb = float(a@a), float(b@b)
    if min(aa, bb) <= 1e-20:
        return {'status': 'DEGENERATE_SERIES', 'n': len(a), 'pearson': None, 'sample_covariance_m2': None}
    return {'status': 'DESCRIPTIVE_ONLY', 'n': len(a), 'pearson': float(np.clip(a@b/np.sqrt(aa*bb), -1., 1.)),
            'sample_covariance_m2': float(a@b/(len(a)-1))}


def describe(rows, stations, refs):
    series = defaultdict(dict)
    for row in rows:
        key, t = (row['station'], row['reference']), row['time_s']
        if t in series[key]:
            raise ValueError('duplicate residual sample')
        series[key][t] = row
    pairs, mean_energy, temporal_energy = [], 0., 0.
    for (station, sv), samples in sorted(series.items()):
        times = sorted(samples)
        values = np.array([samples[t]['residual_m'] for t in times])
        mean = float(values.mean())
        mean_energy += len(values)*mean**2
        temporal_energy += float(np.sum((values-mean)**2))
        adjacent = [(samples[t]['residual_m'], samples[t+30]['residual_m']) for t in times if t+30 in samples]
        a, b = (zip(*adjacent) if adjacent else ([], []))
        first, last = np.array(samples[times[0]]['los_enu']), np.array(samples[times[-1]]['los_enu'])
        pairs.append({'station': station, 'reference': sv, 'n': len(values), 'mean_m': mean,
                      'within_pair_rms_m': rms(values-mean), 'lag30': correlation(a, b),
                      'endpoint_direction_separation_deg': float(np.degrees(np.arctan2(np.linalg.norm(np.cross(first, last)), first@last)))})
    cross = []
    for sv in refs:
        for a, b in combinations(stations, 2):
            one, two = series.get((a, sv), {}), series.get((b, sv), {})
            times = sorted(one.keys() & two.keys())
            cross.append({'reference': sv, 'station_a': a, 'station_b': b, 'times_s': times,
                          **correlation([one[t]['residual_m'] for t in times], [two[t]['residual_m'] for t in times])})
    projection = [{'station': station, 'time_s': time, 'n': len(indices), 'rank': len(indices)-1,
                   'unit_independent_noise_residual_variance': 1.-1./len(indices),
                   'unit_independent_noise_off_diagonal_correlation': -1./(len(indices)-1)}
                  for (station, time), indices in groups(rows).items()]
    total = mean_energy+temporal_energy
    return {'pair_series': pairs, 'same_satellite_cross_station': cross,
            'raw_residual_rms_m': rms([r['residual_m'] for r in rows]),
            'pair_mean_energy_fraction': mean_energy/total if total else None,
            'within_pair_rms_m': float(np.sqrt(temporal_energy/len(rows))),
            'projection_blocks': projection, 'projected_dimension': sum(p['rank'] for p in projection),
            'removed_common_modes': len(projection),
            'physical_covariance': None, 'covariance_qualification': 'NOT_IDENTIFIED_BY_CENTERED_SHORT_WINDOWS'}


def prepare(archive, timed, biases, antennas, attitudes, prior_report):
    admitted, context, _, hashes = load_inputs(archive)
    names = admitted['fit_stations']
    refs = sorted({sv for name in names for obs in admitted['stations'][name]['reference_observations'] for sv in obs['if_code_m']})
    precise, corrections, products = guarded_products(context, refs, timed, biases, antennas)
    attitude, attitudes_hashes = load_attitude(attitudes, context, refs)
    provider = AttitudeReference(precise, attitude)
    prior_bytes = Path(prior_report).read_bytes()
    prior = strict_json(prior_bytes)
    root = Path(__file__).resolve().parents[2]
    if (prior['schema'] != 'reference-attitude-v1' or prior['target'] != context.target or
            prior.get('date_gpst') != context.date_gpst or
            any(prior.get(k) is not False for k in ('target_orbit_accessed', 'target_attitude_parsed',
                'new_confirmation', 'qualified_error_budget', 'applied_to_production_estimator')) or
            prior['fit_stations'] != names or prior['references'] != refs or
            prior['input_sha256'] != hashes | products | attitudes_hashes):
        raise ValueError('prior report/input binding differs')
    for path, digest in prior['sources_sha256'].items():
        source = (root/path).resolve()
        if not source.is_relative_to(root) or hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise ValueError('prior source binding differs')
    primary = [case for case in prior['cases'] if case['mode'] == 'full_pco_30s_attitude']
    if len(primary) != 1 or primary[0]['status'] != 'ESTIMATED':
        raise ValueError('one completed full-attitude calibration required')
    rows, omitted, max_replay = [], [], 0.
    for name in names:
        station = np.array(admitted['stations'][name]['antenna_ecef_m'])
        lat, lon, _, up = geodetic(station)
        east = np.array([-np.sin(lon), np.cos(lon), 0.])
        north = np.cross(up, east)
        basis = np.array([east, north, up])
        cal = primary[0]['calibration'][name]
        if cal['status'] != 'CALIBRATION_QUALIFIED' or [e['time_s'] for e in cal['epochs']] != list(context.times):
            raise ValueError('incomplete prior calibration')
        observations = translate_observations(admitted['stations'][name]['reference_observations'], corrections, context.target)
        if len(observations) != len(cal['epochs']):
            raise ValueError('observation/calibration lengths differ')
        for obs, epoch in zip(observations, cal['epochs'], strict=True):
            if obs['time_s'] != epoch['time_s'] or len(set(epoch['references'])) != len(epoch['references']) or len(epoch['references']) < 4:
                raise ValueError('invalid reference epoch')
            block, raw = [], []
            for sv, code in sorted(obs['if_code_m'].items()):
                row = {'station': name, 'time_s': obs['time_s'], 'reference': sv}
                if sv not in epoch['references']:
                    omitted.append(dict(row, status='NOT_IN_BROADCAST_REFERENCE_SET'))
                    continue
                clock = epoch['clock_m']
                predicted, elevation = provider.model(sv, code, obs['time_s'], station, clock)
                _, _, antenna, offset = provider.antenna_state(sv, code, obs['time_s'])
                ray = rotate_z(antenna, -OMEGA*(-clock/C-offset))-station
                los = ray/np.linalg.norm(ray)
                row.update(los_enu=(basis@los).tolist(), elevation_deg=elevation)
                raw.append(code-predicted)
                block.append(row)
            if len(block) != len(epoch['references']):
                raise ValueError('missing prior reference observation')
            residual = np.asarray(raw)-np.mean(raw)
            if len(epoch['references']) != len(epoch['residuals_m']):
                raise ValueError('reference/residual lengths differ')
            previous = dict(zip(epoch['references'], epoch['residuals_m'], strict=True))
            for row, value in zip(block, residual):
                max_replay = max(max_replay, abs(value-previous[row['reference']]))
                row['residual_m'] = float(value)
                rows.append(row)
    if max_replay > 1e-6:
        raise ValueError('reference residual replay differs')
    inputs = hashes | products | attitudes_hashes | {'prior_attitude_report': hashlib.sha256(prior_bytes).hexdigest()}
    return rows, omitted, context, names, refs, inputs, prior['sources_sha256'], max_replay


def run(archive, timed, biases, antennas, attitudes, prior_report):
    rows, omitted, context, names, refs, inputs, prior_sources, replay = prepare(archive, timed, biases, antennas, attitudes, prior_report)
    times = list(context.times)
    if len(times) != 11:
        raise ValueError('this exploratory comparison requires eleven epochs')
    folds = [('forward', times[:5], times[5:]), ('reverse_control', times[-5:], times[:-5])]
    cases = []
    for fold, train_times, test_times in folds:
        training = [r for r in rows if r['time_s'] in train_times]
        testing = [r for r in rows if r['time_s'] in test_times]
        for model in MODELS:
            row = {'fold': fold, 'model': model, 'training_times_s': train_times, 'test_times_s': test_times}
            try:
                row.update(status='EVALUATED', **predict_block(training, testing, model))
            except Exception as error:
                row.update(status='ENGINEERING_FAILURE', reason=type(error).__name__+': '+str(error))
            cases.append(row)
    root = Path(__file__).resolve().parents[2]
    source = Path(__file__)
    sources = prior_sources | {source.relative_to(root).as_posix(): hashlib.sha256(source.read_bytes()).hexdigest()}
    return {'schema': 'reference-residual-structure-v2', 'target_excluded': context.target, 'date_gpst': context.date_gpst,
            'fit_stations': names, 'references': refs, 'times_s': times, 'input_sha256': inputs, 'sources_sha256': sources,
            'scope': 'Exploratory reference-contrast predictability over two halves of an exposed five-minute window.',
            'method': {'projection': 'Per station/epoch P = I - 11.T/n removes the fitted common clock coordinate.',
                'models': 'zero; common satellite constants; station ENU-direction coefficients; station/satellite constants',
                'fitting': 'Unweighted least squares of projected residuals and features; SVD rcond 1e-12; no target values',
                'testing': 'First five epochs to last six, then last five to first six; coefficients fit on training only',
                'interpretation': 'Coefficients are descriptive, not antenna calibration. Test residuals are clock-free contrasts, not absolute predictions.',
                'correlations': 'Pair means and sample/lag correlations use the whole window descriptively; no population inference.',
                'limitations': ['short window and limited direction change', 'clock-centering induces dependence',
                    'antenna, site coordinates, multipath and media are not causally separated',
                    'common reference modes and target/reference coupling remain unidentified']},
            'target_fit_performed': False, 'target_orbit_accessed': False, 'new_confirmation': False,
            'qualified_error_budget': False, 'applied_to_production_estimator': False,
            'reference_residual_replay_max_abs_m': replay,
            'observed_path_count': len(rows)+len(omitted), 'evaluated_path_count': len(rows),
            'omitted_paths': omitted, 'reference_rows': rows, 'descriptive': describe(rows, names, refs),
            'case_count': len(cases), 'status_counts': dict(Counter(c['status'] for c in cases)), 'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'timed', 'biases', 'antennas', 'attitudes', 'prior_report', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('choose a new output outside the preserved archive')
    result = run(args.archive, args.timed, args.biases, args.antennas, args.attitudes, args.prior_report)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({'status_counts': result['status_counts'], 'evaluated_paths': result['evaluated_path_count']}))
