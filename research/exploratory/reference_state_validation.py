"""Exposed leave-one-satellite-out reconstruction, not prospective coverage.

Recalibrate with all other references; select geometry from RF snapshots, not
the candidate orbit. Fit every supported candidate before loading any candidate
orbit for scoring. Reuse the interval-clock solver, masks, floors and products.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json
import inspect
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.linalg import solve_triangular
from scipy.stats import chi2

from positioning.calibration import troposphere
from positioning.solver import solve
from . import day_reference as day, g12_interval_clocks as interval
from . import precise_reference_model as precise
from . import reference_attitude_model as attitude
from . import reference_code_bias as bias
from . import reference_conventions as conventions
from . import reference_product_discrepancy as sp3
from .reference_phase_clock import clock_rate
from .reference_time_alignment import calibrate_fixed
from .pseudotarget_checked_v2 import PLAN_SHA
from .erp_polar_bound import pinned
from ..kinematic import dynamic_fit, orbital_dynamics as dynamics
from ..kinematic.synthetic import native

BASE = day.BASE
SCENARIO = 'shared_endpoints_added'
PRODUCTS = {
    'timed_receipt': 'inputs/day_reference/timed/receipt.json',
    'orbit_extract': 'inputs/day_reference/timed/reference_orbit.txt',
    'clock_extract': 'inputs/day_reference/timed/reference_clock.txt',
    'bias_receipt': 'inputs/reference_biases/g12/receipt.json',
    'bias_extract': 'inputs/reference_biases/g12/reference_bias.bia',
    'antenna_receipt': 'inputs/reference_antennas/g12/receipt.json',
    'antenna_extract': 'inputs/reference_antennas/g12/reference_antenna.atx',
    'attitude_receipt': 'inputs/day_reference/attitude/receipt.json',
    'attitude_extract': 'inputs/day_reference/attitude/reference_attitude.obx',
}


def read_inputs():
    # Read the existing receipt chain without executing historical calibration
    # runners (which numerically parse all original reference products).
    receipt_raw = pinned(BASE/'inputs/day_reference/receipt.json', day.RECEIPT_SHA)
    receipt = json.loads(receipt_raw)
    raw = {'day_receipt': receipt_raw,
           'plan': pinned(BASE/'day_reference_plan.json', receipt['plan_sha256']),
           'observations': pinned(BASE/'inputs/day_reference/observations.json', receipt['files']['observations.json']),
           'positions': pinned(BASE/'inputs/day_reference/positions.json', receipt['files']['positions.json'])}
    raw['pseudo_plan'] = pinned(BASE/'pseudotarget_plan.json', PLAN_SHA)
    pseudo_plan = json.loads(raw['pseudo_plan'])
    raw['baseline'] = pinned(BASE/'results/day_reference_v1.json', pseudo_plan['baseline_report_sha256'])
    baseline = json.loads(raw['baseline'])
    raw['reference_clock'] = (BASE/'results/reference_phase_clock_full_hour_v1.json').read_bytes()
    clock = json.loads(raw['reference_clock'])
    raw['phase'] = pinned(BASE/'inputs/real_phase/observations_gps_only_v2.json', clock['input_sha256'])
    raw.update({key: pinned(BASE/path, baseline['product_sha256'][key]) for key, path in PRODUCTS.items()})
    data = {k: json.loads(raw[k]) for k in ['plan', 'observations', 'positions', 'phase']}
    phase, plan = data['phase']['cohorts']['day'], data['plan']
    if (plan['target_excluded'] != 'G12' or 'G12' in plan['references'] or len(set(plan['references'])) != len(plan['references'])
            or phase['plan'] != plan or phase['receipt_sha256'] != interval.shared.digest(receipt_raw)
            or baseline['plan'] != plan or baseline['target_orbit_accessed'] or not baseline['calibration_complete']
            or clock['baseline_report_sha256'] != interval.shared.digest(raw['baseline'])):
        raise ValueError('exposed reference input boundary differs')
    for key in ['timed_receipt', 'bias_receipt', 'antenna_receipt', 'attitude_receipt']:
        meta = json.loads(raw[key])
        if meta['target_excluded'] != 'G12' or meta['references'] != plan['references']:
            raise ValueError('original reference-product cohort differs')
    data['phase'] = phase
    data['products'] = {k: raw[k].decode('ascii') for k in PRODUCTS if k.endswith('_extract')}
    data['clock_window'] = json.loads(raw['timed_receipt'])['clock_window_gpst_s']
    data['attitude_window'] = json.loads(raw['attitude_receipt'])['window_gpst_s']
    return raw, data


def subset_products(data, refs, excluded):
    """Restrict identity as text before invoking the existing numeric parsers."""
    if excluded in refs or 'G12' in refs or not set(refs) <= set(data['plan']['references']):
        raise ValueError('excluded/unadmitted reference before product decoding')
    p, date = data['products'], data['plan']['date_gpst']
    start, stop = data['clock_window']
    antenna_text = conventions.extract_antex(p['antenna_extract'], refs, excluded)
    clock_text = precise.extract_clock(p['clock_extract'], refs, excluded, date, start, stop)
    attitude.validate_pair(clock_text, antenna_text, refs, excluded, date, start, stop)
    offsets = conventions.antenna_offsets(antenna_text, refs, excluded, date, start, 'IGS20_2425')
    if offsets != conventions.antenna_offsets(antenna_text, refs, excluded, date, stop, 'IGS20_2425'):
        raise ValueError('reference antenna assignment changes')
    records = bias.parse_bias(bias.extract_bias(p['bias_extract'], refs, excluded), refs, excluded, 'IGS20_2425')
    orbit = precise.parse_orbit(sp3.extract_references(p['orbit_extract'], refs, excluded), refs, excluded, date)
    clocks = precise.parse_clock(clock_text, refs, excluded, date, start, stop)
    a, b = data['attitude_window']
    samples = attitude.parse_attitude(attitude.extract_attitude(p['attitude_extract'], refs, excluded, date, a, b),
                                      refs, excluded, date, a, b)
    provider = attitude.AttitudeReference(precise.PreciseReference(orbit, clocks, offsets, excluded),
                                        attitude.Attitude(samples, excluded))
    midnight = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
    corrections = {(t, sv): bias.code_translation(records, sv, midnight+timedelta(seconds=t), offsets[sv]['svn'])
                   for t in range(36000, 39601, 30) for sv in refs}
    return provider, corrections


def phase_index(data):
    return {s: {(r['reference'], r['time_s']): r for r in item['rows']}
            for s, item in data['phase']['stations'].items()}


def coverage(data, excluded):
    rows = phase_index(data)
    result = []
    for start in range(36000, 39600, 180):
        stations = [s for s in data['plan']['stations'] if all(
            rows[s].get((excluded, start+t), {}).get('status') == 'AVAILABLE' for t in (0, 30, 60))]
        result.append({'start_gpst_s': start, 'rf_available_stations': stations,
                       'status': 'RF_COVERED' if len(stations) >= 5 else 'INSUFFICIENT_RF_STATIONS'})
    return result


def calibration_environment(data, excluded, weather):
    refs = [q for q in data['plan']['references'] if q != excluded]
    provider, corrections = subset_products(data, refs, excluded)
    # Filter candidate code before any translation or calibration arithmetic.
    observations = {s: {e['time_s']: {q: value for q, value in e['if_code_m'].items() if q in refs}
                        for e in epochs} for s, epochs in data['observations'].items()}
    rows = phase_index(data)
    mjd = (datetime.fromisoformat(data['plan']['date_gpst'])-datetime(1858, 11, 17)).days
    def xyz(s, t):
        return np.asarray(data['positions'][s][int((t-36000)/30)], float)
    @lru_cache(maxsize=100000)
    def model(s, t, q, code, clock):
        if q == excluded or q not in refs:
            raise ValueError('excluded satellite at calibration model boundary')
        value, elevation = provider.model(q, code, t, xyz(s, t), clock)
        delays, _ = day.atmosphere.components(provider, weather, mjd, q, code, t, xyz(s, t), clock)
        return value-delays['legacy_baseline']+delays['vmf3_full'], elevation
    def codes(s, t):
        return {q: v+corrections[t, q]['if_code_change_m'] for q, v in observations[s][t].items()}
    @lru_cache(maxsize=None)
    def offset(s, t):
        try:
            values = codes(s, t)
            selected = sorted(q for q, v in values.items() if model(s, t, q, v, 0.)[1] >= 10.)
            # Same reference residual, subset, rank and ground-coordinate checks
            # as the existing calibrator; qualify this single epoch explicitly.
            context = SimpleNamespace(target=excluded, samples=1)
            result = calibrate_fixed([{'time_s': t, 'if_code_m': values}], xyz(s, t), context, {t: selected},
                model_at)
            return result
        except (ValueError, KeyError) as error:
            return {'status': 'CALIBRATION_FAILED', 'reason': str(error), 'epochs': []}
    def model_at(q, code, t, station, clock):
        if q == excluded or q not in refs:
            raise ValueError('excluded satellite at ground-check model boundary')
        value, elevation = provider.model(q, code, t, station, clock)
        delays, _ = day.atmosphere.components(provider, weather, mjd, q, code, t, station, clock)
        return value-delays['legacy_baseline']+delays['vmf3_full'], elevation
    @lru_cache(maxsize=None)
    def rate(s, t):
        values, previous = codes(s, t), codes(s, t-30)
        estimates = []
        for q in refs:
            pair = [rows[s].get((q, when)) for when in (t-30, t)]
            if not all(r is not None and r['status'] == 'AVAILABLE' for r in pair) or q not in values or q not in previous:
                continue
            a, ea = model(s, t-30, q, previous[q], 0.)
            b, eb = model(s, t, q, values[q], 0.)
            if min(ea, eb) >= 10.:
                estimates.append({'reference': q, 'phase_minus_model_rate_m_s':
                    ((float(pair[1]['phase_m'])-b)-(float(pair[0]['phase_m'])-a))/30.})
        return clock_rate(estimates, excluded=excluded, estimator='median')
    return offset, rate, xyz


def rf_geometry(codes, clock_offsets, positions):
    """Existing RF snapshot primitive, unique exterior branch, fixed 10 deg mask.

    Retain snapshot branch terminals; no orbit, orbit-radius prior or reference
    target mask. The shared fitter later retains its own complete branch search.
    """
    angles, records = [], []
    for values, clock, xyz in zip(codes, clock_offsets, positions, strict=True):
        result = solve(values-clock, xyz, np.eye(len(xyz))*400., atmosphere=False)
        branches = [{**b, 'exterior': np.linalg.norm(b['q'][:3]) > dynamics.R_EARTH}
                    for b in result['branches']]
        records.append({'branches': branches})
        exterior = [b for b in branches if b['exterior']]
        if len(exterior) != 1:
            return {'status': 'RF_GEOMETRY_AMBIGUOUS', 'snapshots': records}, []
        angles.append([troposphere(s, np.asarray(exterior[0]['q'][:3]))[1] for s in xyz])
    elevations = np.asarray(angles)
    selected = np.flatnonzero(np.min(elevations, axis=0) >= 10.)
    return {'status': 'RF_MASK_EVALUATED', 'snapshots': records, 'elevation_deg': elevations}, selected


def build_arcs(data, excluded, weather):
    windows = coverage(data, excluded)
    if not any(w['status'] == 'RF_COVERED' for w in windows):
        return [], windows
    offset, rate, xyz = calibration_environment(data, excluded, weather)
    rows, arcs = phase_index(data), []
    for w in windows:
        if w['status'] != 'RF_COVERED':
            continue
        start, sites = w['start_gpst_s'], w['rf_available_stations']
        times = [start, start+30, start+60]
        try:
            calibrations = {s: [offset(s, t) for t in times] for s in sites}
            rates = {s: [rate(s, t) for t in times[1:]] for s in sites}
            w['calibration'] = {s: {'offset_statuses': [c['status'] for c in calibrations[s]],
                'rate_statuses': [r['status'] for r in rates[s]]} for s in sites}
            if any(c['status'] != 'CALIBRATION_QUALIFIED' for values in calibrations.values() for c in values) or any(
                    r['status'] != 'ESTIMATED' for values in rates.values() for r in values):
                w['status'] = 'REFERENCE_CALIBRATION_REJECTED'
                continue
            code = np.array([[rows[s][excluded, t]['code_m'] for s in sites] for t in times], float)
            clocks = np.array([[calibrations[s][i]['epochs'][0]['clock_m'] for s in sites] for i in range(3)])
            coordinates = np.array([[xyz(s, t) for s in sites] for t in times])
            geometry, ix = rf_geometry(code, clocks, coordinates)
            w['rf_geometry'] = geometry
            if len(ix) < 5:
                w['status'] = 'RF_MASK_UNSUPPORTED' if geometry['status'] == 'RF_MASK_EVALUATED' else geometry['status']
                continue
            names = [sites[i] for i in ix]
            phase = np.array([[rows[s][excluded, t]['phase_m'] for s in names] for t in times], float)
            means = np.array([[calibrations[s][-1]['epochs'][0]['clock_m'],
                (rates[s][0]['rate_m_s']+rates[s][1]['rate_m_s'])/2.,
                (rates[s][0]['rate_m_s']-rates[s][1]['rate_m_s'])/2.] for s in names])
            arcs.append({'stations': names, 'endpoint_gpst_s': start+60, 'tags_s': interval.shared.TAGS,
                'stations_m': coordinates[-1, ix], 'codes_m': code[:, ix], 'rates_m_s': np.diff(phase, axis=0)/30.,
                'clock_mean': means, 'receiver_clock_basis': interval.clock_basis(interval.shared.TAGS),
                'satellite_clock_count': 3, 'covariance': interval.joint_covariance(len(names), SCENARIO),
                'calibration_statuses': [interval.shared.CALIBRATION]*len(names),
                'propagation': interval.shared.propagation_model(weather, names)})
            w.update(status='PREPARED', stations=names)
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            w.update(status='PREPARATION_FAILED', reason=str(error))
    return arcs, windows


def oracle(data, candidate):
    """Evaluation only; no candidate clock/bias product is needed or parsed."""
    p, date, refs = data['products'], data['plan']['date_gpst'], [candidate]
    orbit = precise.parse_orbit(sp3.extract_references(p['orbit_extract'], refs, 'G12'), refs, 'G12', date)
    text = conventions.extract_antex(p['antenna_extract'], refs, 'G12')
    offsets = conventions.antenna_offsets(text, refs, 'G12', date, data['clock_window'][0], 'IGS20_2425')
    a, b = data['attitude_window']
    samples = attitude.parse_attitude(attitude.extract_attitude(p['attitude_extract'], refs, 'G12', date, a, b),
                                      refs, 'G12', date, a, b)
    provider = precise.PreciseReference(orbit, {candidate: {}}, offsets, 'G12')
    orientation = attitude.Attitude(samples, 'G12')
    def point(t):
        com, velocity = provider.orbit(candidate, t)
        pco = orientation.body_to_ecef(candidate, t)@np.asarray(offsets[candidate]['if_pco_body_m'])
        return com+pco, com, velocity, pco
    def state(t):
        position, com, velocity, _ = point(t)
        # Finite-difference only the metre-scale antenna displacement, keeping
        # the existing polynomial derivative for COM velocity.
        plus, minus = point(t+.5)[3], point(t-.5)[3]
        return np.r_[position, velocity+plus-minus], np.r_[com, velocity]
    return state


def state_errors(fit, arcs, truth):
    if 'state_ecef_m_m_s' not in fit:
        return {'status': 'FIT_UNAVAILABLE', 'rows': []}
    epoch = fit['epoch_gpst_s']
    curve = dynamics.Trajectory(fit['state_ecef_m_m_s'], fit['integrated_bounds_s'], j2=fit['j2'], sensitivities=True)
    covariance = np.asarray(fit['conditional_global_covariance'])[:6, :6]
    last = max(a['endpoint_gpst_s'] for a in arcs)
    times = sorted({a['endpoint_gpst_s']+delta for a in arcs for delta in (0., 30.)})
    rows = []
    for t in times:
        row = {'gpst_s': t, 'kind': 'BEYOND_ALL_TRAINING' if t > last else 'IN_TRAINING_SPAN'}
        try:
            actual, com = truth(t)
            estimated = curve(t-epoch)
            error = estimated-actual
            jac = curve.state_jacobian(t-epoch)
            cov = jac@covariance@jac.T
            np.linalg.cholesky(cov)
            pose = solve_triangular(np.linalg.cholesky(cov[:3, :3]), error[:3], lower=True)
            joint = solve_triangular(np.linalg.cholesky(cov), error, lower=True)
            row.update(status='EVALUATED', position_error_m=float(np.linalg.norm(error[:3])),
                velocity_error_m_s=float(np.linalg.norm(error[3:])), error_ecef_m_m_s=error,
                com_position_error_m=float(np.linalg.norm(estimated[:3]-com[:3])),
                conditional_position_mahalanobis_squared=float(pose@pose),
                conditional_state_mahalanobis_squared=float(joint@joint),
                position_inside_formal_95=bool(pose@pose <= chi2.ppf(.95, 3)),
                state_inside_formal_95=bool(joint@joint <= chi2.ppf(.95, 6)),
                formal_position_95_largest_axis_m=float(np.sqrt(np.linalg.eigvalsh(cov[:3, :3])[-1]*chi2.ppf(.95, 3))))
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            row.update(status='EVALUATION_FAILED', reason=str(error))
        rows.append(row)
    good = [r for r in rows if r['status'] == 'EVALUATED']
    return native({'status': 'EVALUATED' if good else 'EVALUATION_UNAVAILABLE', 'rows': rows,
        'summary': {kind: {'count': len(part := [r for r in good if kind == 'ALL' or r['kind'] == kind]),
            'position_error_m': interval.diagnostic.moments([r['position_error_m'] for r in part]),
            'velocity_error_m_s': interval.diagnostic.moments([r['velocity_error_m_s'] for r in part]),
            'position_inside_formal_95_count': sum(r['position_inside_formal_95'] for r in part),
            'state_inside_formal_95_count': sum(r['state_inside_formal_95'] for r in part)}
            for kind in ('ALL', 'IN_TRAINING_SPAN', 'BEYOND_ALL_TRAINING')}})


def score_rf(data, candidate, predictions):
    rows, output = phase_index(data), []
    for p in predictions:
        record = {'endpoint_gpst_s': p['endpoint_gpst_s'], 'prediction_status': p['status'], 'pairs': []}
        if p['status'] != 'PREDICTED':
            record['status'] = 'UNSCORED'
            output.append(record)
            continue
        end = p['endpoint_gpst_s']
        record.update(status='SCORED', kind=p['kind'], fit_status=p['fit_status'])
        for j, s in enumerate(p['stations']):
            previous, future = rows[s].get((candidate, end)), rows[s].get((candidate, end+30))
            if previous is None or future is None or previous['status'] != 'AVAILABLE' or future['status'] != 'AVAILABLE':
                record['pairs'].append({'station': s, 'status': 'WITHHELD_UNAVAILABLE'})
                continue
            record['pairs'].append({'station': s, 'status': 'EVALUATED',
                'code_residual_m': float(future['code_m'])-p['code_m'][j],
                'phase_rate_residual_m_s': (float(future['phase_m'])-float(previous['phase_m']))/30.-p['phase_rate_m_s'][j]})
        output.append(record)
    summary = {}
    for kind in ('ALL', 'TEMPORAL_HOLDOUT', 'BEYOND_ALL_TRAINING'):
        pairs = [pair for w in output if kind == 'ALL' or w.get('kind') == kind for pair in w['pairs']]
        good = [p for p in pairs if p['status'] == 'EVALUATED']
        summary[kind] = {'pair_status_counts': dict(Counter(p['status'] for p in pairs)),
            'code_residual_m': interval.diagnostic.moments([p['code_residual_m'] for p in good]),
            'phase_rate_residual_m_s': interval.diagnostic.moments([p['phase_rate_residual_m_s'] for p in good])}
    return native({'windows': output, 'summary': summary})


def run():
    raw, data = read_inputs()
    weather = interval.shared.meteo.WeatherGrid(interval.shared.meteo.read_inputs()[0])
    results, prepared = {}, {}
    for candidate in data['plan']['references']:
        print(candidate, 'preparing', flush=True)
        try:
            arcs, windows = build_arcs(data, candidate, weather)
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            arcs, windows = [], coverage(data, candidate)
            for window in windows:
                if window['status'] == 'RF_COVERED':
                    window.update(status='CANDIDATE_PREPARATION_FAILED', reason=str(error))
        prepared[candidate] = arcs
        fit = {'status': 'INSUFFICIENT_PREPARED_ARCS', 'arc_count': len(arcs)}
        if len(arcs) >= 2:
            try:
                fit = dynamic_fit.fit(arcs, include_phase=True, j2=dynamics.J2,
                                      progress=lambda r: print(candidate, r, flush=True))
            except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                fit = {'status': 'FIT_FAILED', 'reason': str(error)}
        results[candidate] = {'windows': native(windows), 'window_status_counts': dict(Counter(w['status'] for w in windows)),
            'fit': native(fit), 'observability': interval.observability(fit),
            'rf_predictions': interval.predict(fit, arcs, weather) if arcs else []}
        print(candidate, fit['status'], results[candidate]['window_status_counts'], flush=True)
    # All candidates' fits and RF predictions fixed before any scoring oracle.
    for candidate, result in results.items():
        result['rf_evaluation'] = score_rf(data, candidate, result['rf_predictions'])
        if 'state_ecef_m_m_s' not in result['fit']:
            result['state_evaluation'] = {'status': 'FIT_UNAVAILABLE', 'rows': []}
            continue
        try:
            result['state_evaluation'] = state_errors(result['fit'], prepared[candidate], oracle(data, candidate))
        except (ValueError, KeyError, np.linalg.LinAlgError) as error:
            result['state_evaluation'] = {'status': 'ORACLE_UNAVAILABLE', 'reason': str(error), 'rows': []}
    modules = [Path(m.__file__) for m in [interval, interval.shared, dynamic_fit, dynamics, interval.clock_observations,
        precise, attitude, bias, conventions, sp3, day.atmosphere, interval.shared.meteo]]
    modules += [Path(inspect.getmodule(f).__file__) for f in [clock_rate, calibrate_fixed, solve, troposphere]]
    return native({'schema': 'exposed-reference-state-validation-v1',
        'scope': 'All 22 original references; exposed RF-only geometry selection and leave-one-out recalibration. Candidate products excluded from numeric calibration/fitting; CODE COM/IF antenna-center trajectories opened only after all fits. Shared upstream products and conditional covariance prevent independent truth or coverage claims.',
        'candidate_orbit_used_in_fit': False, 'candidate_clock_used_in_fit': False,
        'candidate_bias_or_attitude_used_in_fit': False, 'g12_state_accessed': False,
        'oracle_opened_after_all_fits': True, 'new_confirmation': False, 'physical_covariance_qualified': False,
        'production_floors_changed': False, 'clock_covariance_scenario': SCENARIO,
        'model': 'unchanged central+J2, interval receiver clocks, free satellite curvature; inherited floors/mask/p=.01',
        'selection': '20 even chronological 60 s arcs per candidate, >=5 available receivers; all references recalibrated without candidate; three RF code snapshots require unique exterior branch and >=5 receivers above 10 deg; no replacements',
        'input_sha256': {k: interval.shared.digest(v) for k, v in raw.items()},
        'weather_receipt_sha256': interval.shared.meteo.RECEIPT_SHA,
        'source_sha256': {p.relative_to(BASE.parents[1]).as_posix(): interval.shared.digest(p.read_bytes())
                          for p in modules+[Path(__file__)]},
        'fit_status_counts': dict(Counter(r['fit']['status'] for r in results.values())), 'candidates': results})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; retain previous results')
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n')
