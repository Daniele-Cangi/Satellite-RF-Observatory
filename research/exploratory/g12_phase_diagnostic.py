"""Localize the rejected G12 phase fit, without refitting or changing weights.

Replay v4 on exposed training RF and match reference-only increments at exactly
the same stations/times. Contrast decompositions are descriptive ablations,
not independent clock truth, acceptance tests or a new reconstruction.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.linalg import solve_triangular

from . import g12_dynamic_fit as shared
from ..kinematic import dynamic_fit, orbital_dynamics as dynamics
from ..kinematic.synthetic import native

BASE = shared.BASE
FILES = {
    'fit': 'results/g12_dynamic_fit_v4.json',
    'hour': 'results/g12_full_hour_v1.json',
    'target': 'inputs/real_phase/g12_target_phase_v2.json',
    'access': 'real_target_phase_access_v2.json',
    'positions': 'inputs/day_reference/positions.json',
    'baseline': 'results/day_reference_v1.json',
    'reference_phase_input': 'inputs/real_phase/observations_gps_only_v2.json',
    'reference_clock': 'results/reference_phase_clock_full_hour_v1.json',
}


def moments(values):
    x = np.asarray(values, float)
    if not np.isfinite(x).all():
        raise ValueError('finite diagnostic values required')
    return {'count': x.size, 'mean': float(x.mean()) if x.size else None,
            'rms': float(np.sqrt(np.mean(x*x))) if x.size else None,
            'max_abs': float(np.max(np.abs(x))) if x.size else None}


def reference_index(clock):
    """Reject a target label before numeric access; never rescue a subset."""
    if clock['target_excluded'] != 'G12' or clock['target_values_accessed']:
        raise ValueError('reference-only clock boundary differs')
    diagnostics = clock['held_out_reference_diagnostics']
    if any(r['reference'] == 'G12' for r in diagnostics):
        raise ValueError('target in reference diagnostic before numeric access')
    estimates, rows = {}, {}
    for r in clock['phase_clock_rates']:
        key = r['station'], r['time_s']
        if key in estimates:
            raise ValueError('duplicate reference clock block')
        estimates[key] = r
    for r in diagnostics:
        key = r['station'], r['time_s'], r['reference']
        if key in rows:
            raise ValueError('duplicate held-out reference')
        rows[key] = r
    return estimates, rows


def matched_reference(index, station, endpoint):
    """Full estimates plus every reference slot across the two 30 s intervals."""
    estimates, rows = index
    times = [endpoint-30., endpoint]
    blocks = [estimates.get((station, t)) for t in times]
    retained = []
    references = sorted({q for s, t, q in rows if s == station and t in times})
    for q in references:
        pair = [rows.get((station, t, q)) for t in times]
        r = {'reference': q, 'endpoint_statuses': [
            p['status'] if p is not None else 'MISSING' for p in pair]}
        if all(p is not None and p['status'] == 'ESTIMATED' for p in pair):
            r.update(status='MATCHED',
                # Each endpoint's estimate excludes q, with its actual subset.
                leave_one_out_half_difference_error_m_s=(
                    pair[0]['error_m_s_median']-pair[1]['error_m_s_median'])/2.)
        else:
            r['status'] = 'UNSUPPORTED_REFERENCE_CONTRAST'
        retained.append(r)
    result = {'station': station, 'interval_endpoints_gpst_s': times,
              'references': retained}
    if any(b is None or b['estimators']['median']['status'] != 'ESTIMATED'
           for b in blocks):
        return {**result, 'status': 'REFERENCE_CLOCK_UNAVAILABLE'}
    rates = np.array([b['estimators']['median']['rate_m_s'] for b in blocks])
    if not np.isfinite(rates).all():
        raise ValueError('nonfinite reference clock estimate')
    result.update(status='MATCHED', median_rates_m_s=rates,
        half_difference_m_s=(rates[0]-rates[1])/2.,
        endpoint_reference_counts=[b['reference_count'] for b in blocks],
        endpoint_reference_sets=[sorted(q for s, t, q in rows
                                 if s == station and t == time) for time in times])
    return native(result)


def contrast_components(residual_rates, reference_half_difference):
    """Equal-weight spatial centering of the fixed temporal contrast.

    A linear additive clock and a constant phase ambiguity have zero second
    difference. The full replay below retains receive-time/light-time effects;
    this algebra alone is not an exact physical clock cancellation theorem.
    """
    r, c = np.asarray(residual_rates, float), np.asarray(reference_half_difference, float)
    if r.ndim != 2 or r.shape[0] != 2 or c.shape != (r.shape[1],) or not (
            np.isfinite(r).all() and np.isfinite(c).all()):
        raise ValueError('two complete finite intervals and matching references required')
    half_sum, half_difference = (r[0]+r[1])/2., (r[0]-r[1])/2.
    remaining = half_difference-c
    common = np.full(len(c), remaining.mean())
    return {'half_sum_m_s': half_sum, 'half_difference_m_s': half_difference,
            'reference_half_difference_m_s': c, 'remaining_m_s': remaining,
            'common_remaining_m_s': common, 'spatial_contrast_remaining_m_s': remaining-common}


def reference_forecast(index, station, endpoint):
    """Two fixed rules using only the first two reference increments.

    Later reference estimates are evaluation data, not absolute clock truth.
    No target observation participates in predictions or evaluation.
    """
    estimates, _ = index
    pair = [estimates.get((station, t)) for t in [endpoint-30., endpoint]]
    result = {'station': station, 'evaluation_gpst_s': endpoint+30.}
    if any(r is None or r['estimators']['median']['status'] != 'ESTIMATED' for r in pair):
        return {**result, 'status': 'TRAINING_REFERENCE_UNAVAILABLE'}
    first, second = [float(r['estimators']['median']['rate_m_s']) for r in pair]
    result.update(constant_prediction_m_s=(first+second)/2.,
                  linear_rate_prediction_m_s=2.*second-first)
    future = estimates.get((station, endpoint+30.))
    if future is None or future['estimators']['median']['status'] != 'ESTIMATED':
        return {**result, 'status': 'EVALUATION_REFERENCE_UNAVAILABLE'}
    actual = float(future['estimators']['median']['rate_m_s'])
    if not np.isfinite([first, second, actual]).all():
        raise ValueError('nonfinite reference forecast input')
    e0, e1 = actual-result['constant_prediction_m_s'], actual-result['linear_rate_prediction_m_s']
    return {**result, 'status': 'EVALUATED', 'reference_evaluation_m_s': actual,
            'constant_error_m_s': e0, 'linear_rate_error_m_s': e1,
            'linear_rate_worsened': abs(e1) > abs(e0)}


def replay_variant(fit, arcs, target, index, weather):
    prepared, names, _ = dynamic_fit.prepare(arcs, True)
    if fit['stations'] != names or len(prepared) != len(fit['arc_parameters']):
        raise ValueError('stored fit and admitted training arcs differ')
    curve = dynamics.Trajectory(fit['state_ecef_m_m_s'], fit['integrated_bounds_s'], j2=fit['j2'])
    epoch, windows, total_cost = fit['epoch_gpst_s'], [], 0.
    costs = dict.fromkeys(['code', 'phase', 'reference_clock', 'ground'], 0.)
    target_rows = {s: {r['time_s']: r for r in target['stations'][s]['rows']} for s in names}
    for a, p in zip(prepared, fit['arc_parameters'], strict=True):
        if p['endpoint_gpst_s'] != a['endpoint_gpst_s'] or p['stations'] != a['stations']:
            raise ValueError('stored local parameters are not aligned with the training arc')
        n, end = a['n'], a['endpoint_gpst_s']
        physical = np.r_[p['satellite_clock'], np.asarray(p['receiver_clocks']).ravel(),
                         np.asarray(p['station_corrections_m']).ravel()]
        value, pair = dynamic_fit.model(curve, a, physical/a['local_scale'],
                                       np.array(fit['bias_contrast_coefficients_m']), epoch)
        residual = a['observed']-value
        whitened = solve_triangular(a['chol'], residual, lower=True)
        lengths = [a['codes'].size, len(a['difference']), 2*n, 3*n]
        offset = 0
        for key, length in zip(costs, lengths, strict=True):
            costs[key] += float(whitened[offset:offset+length]@whitened[offset:offset+length])
            offset += length
        total_cost += float(whitened@whitened)
        rates = residual[a['codes'].size:a['codes'].size+len(a['difference'])].reshape(2, n)
        xyz = a['xyz']+np.array(p['station_corrections_m'])
        delay = shared.propagation_model(weather, a['stations'])(pair, xyz, epoch)['delay_m']
        delay_rates = np.diff(delay, axis=0)/30.
        references = [matched_reference(index, s, end) for s in a['stations']]
        intervals = []
        for i, s in np.ndindex(rates.shape):
            station = a['stations'][s]
            intervals.append({'station': station, 'interval_end_gpst_s': end-30.+30.*i,
                'residual_rate_m_s': float(rates[i, s]),
                'observed_rate_m_s': float(a['rates_m_s'][i, s]),
                'predicted_rate_m_s': float(a['rates_m_s'][i, s]-rates[i, s]),
                'propagation_rate_m_s': float(delay_rates[i, s])})
        phase_cov = np.asarray(a['covariance'])[a['codes'].size:a['codes'].size+2*n,
                                              a['codes'].size:a['codes'].size+2*n]
        half_sum = np.column_stack([np.eye(n), np.eye(n)])/2.
        half_diff = np.column_stack([np.eye(n), -np.eye(n)])/2.
        window = {'endpoint_gpst_s': end, 'stations': a['stations'],
                  'intervals': intervals, 'matched_references': references,
                  'half_sum_covariance': half_sum@phase_cov@half_sum.T,
                  'half_difference_covariance': half_diff@phase_cov@half_diff.T,
                  'half_sum_half_difference_covariance': half_sum@phase_cov@half_diff.T}
        if any(r['status'] != 'MATCHED' for r in references):
            window['status'] = 'REFERENCE_CONTRAST_UNAVAILABLE'
            windows.append(window)
            continue
        c = np.array([r['half_difference_m_s'] for r in references])
        components = contrast_components(rates, c)
        window.update(status='EVALUATED', components=components,
            propagation_half_difference_m_s=(delay_rates[0]-delay_rates[1])/2.)
        # Verify the sign and size of the reference shape ablation through the
        # complete observation model. Only the middle receiver-clock endpoint
        # moves (by 30*c m); fitted state, end clock, mean slope and ground stay fixed.
        paths = []
        for i, tag in enumerate(a['tags']):
            clocks = np.array(p['receiver_clocks'], float)
            clocks[:, 0] += clocks[:, 1]*tag+(30.*c if i == 1 else 0.)
            clocks[:, 1] = 0.
            changed = dynamics.predict_observations(curve, end-epoch, [tag], xyz, clocks, p['satellite_clock'])
            correction = shared.propagation_model(weather, a['stations'])(changed, xyz, epoch)['delay_m']
            paths.append((changed['code_m']+correction)[0])
        changed_rates = a['rates_m_s']-np.diff(np.array(paths), axis=0)/30.
        window['exact_reference_shape_ablation'] = contrast_components(changed_rates, np.zeros(n))
        window['ablation_minus_algebra_half_difference_m_s'] = (
            window['exact_reference_shape_ablation']['half_difference_m_s']-components['remaining_m_s'])
        window['target_phase_continuity'] = []
        for s in a['stations']:
            triad = [target_rows[s][end+t] for t in [-60., -30., 0.]]
            gf = np.array([r['geometry_free_phase_m'] for r in triad])
            window['target_phase_continuity'].append({'station': s, 'lli': [r['lli'] for r in triad],
                'geometry_free_second_difference_m': float(gf[2]-2.*gf[1]+gf[0])})
        windows.append(window)
    if not np.isclose(total_cost, fit['weighted_residual_cost'], rtol=1e-7, atol=1e-5):
        raise ValueError('v4 observation/cost replay differs from stored fit')
    good = [w for w in windows if w['status'] == 'EVALUATED']
    flatten = lambda key: [x for w in good for x in w['components'][key]]
    summary = {'window_status_counts': dict(Counter(w['status'] for w in windows)),
               'replayed_joint_cost': total_cost, 'cost_blocks': costs,
               'interval_residual_m_s': moments([r['residual_rate_m_s'] for w in windows for r in w['intervals']]),
               'contrasts': {k: moments(flatten(k)) for k in good[0]['components']} if good else {}}
    if good:
        remaining = np.array(flatten('remaining_m_s'))
        common = np.array(flatten('common_remaining_m_s'))
        summary['remaining_common_squared_fraction'] = float(common@common/(remaining@remaining)) if remaining@remaining else None
        summary['reference_shape_correlation'] = float(np.corrcoef(
            flatten('half_difference_m_s'), flatten('reference_half_difference_m_s'))[0, 1])
        summary['propagation_half_difference_m_s'] = moments([x for w in good for x in w['propagation_half_difference_m_s']])
        summary['exact_ablation_minus_algebra_m_s'] = moments([
            x for w in good for x in w['ablation_minus_algebra_half_difference_m_s']])
    return native({'original_fit_status': fit['status'], 'original_p_value': fit['conditional_residual_p'],
                   'original_branch_failures': fit['branch_failures'], 'windows': windows, 'summary': summary})


def run(data=None, raw=None):
    if data is None:
        raw = {k: (BASE/p).read_bytes() for k, p in FILES.items()}
        data = {k: json.loads(v) for k, v in raw.items()}
    report, clock = data['fit'], data['reference_clock']
    if (report['historical_fit_geometry_used'] or report['target_orbit_used'] or report['oracle_error_used']
            or report['new_confirmation'] or report['weather_receipt_sha256'] != shared.meteo.RECEIPT_SHA):
        raise ValueError('corrected exposed v4 boundary required')
    if raw is None or any(report['input_sha256'][k] != shared.digest(v) for k, v in raw.items() if k != 'fit'):
        raise ValueError('v4 input bytes differ')
    if (clock['input_sha256'] != shared.digest(raw['reference_phase_input'])
            or clock['baseline_report_sha256'] != shared.digest(raw['baseline'])
            or data['target']['target_state_accessed'] or data['baseline']['target_orbit_accessed']):
        raise ValueError('independent reference/target boundary differs')
    for module in [shared, dynamic_fit, dynamics]:
        p = Path(module.__file__)
        if report['source_sha256'][p.name] != shared.digest(p.read_bytes()):
            raise ValueError('v4 producer changed; replay from its recorded version')
    index = reference_index(clock)
    cases, selection = shared.cohort(data['hour'], 'code_phase')
    if any(report['variants']['code_phase_'+force]['cohort'] != native(selection) for force, _ in shared.FORCES):
        raise ValueError('inherited phase cohort differs')
    arcs = shared.training_arcs(cases, data['target'], data['positions'], data['baseline'], clock, 'code_phase')
    weather = shared.meteo.WeatherGrid(shared.meteo.read_inputs()[0])
    for arc in arcs:
        arc['propagation'] = shared.propagation_model(weather, arc['stations'])
    variants = {force: replay_variant(report['variants']['code_phase_'+force]['fit'], arcs,
                                     data['target'], index, weather) for force, _ in shared.FORCES}
    forecasts = [reference_forecast(index, s, a['endpoint_gpst_s']) for a in arcs for s in a['stations']]
    evaluated = [r for r in forecasts if r['status'] == 'EVALUATED']
    return native({'schema': 'exposed-g12-phase-localization-v1',
        'scope': 'Descriptive replay of the two rejected v4 phase variants on exposed training RF. Matched reference clock shapes share products; ablations do not refit or establish absolute clock truth, predictive uncertainty, acceptance or a new reconstruction.',
        'target_orbit_used': False, 'oracle_error_used': False, 'new_confirmation': False,
        'solver_changed': False, 'weights_changed': False, 'physical_covariance_qualified': False,
        'input_sha256': {k: shared.digest(v) for k, v in raw.items()},
        'source_sha256': {Path(__file__).name: shared.digest(Path(__file__).read_bytes())},
        'cohort': selection, 'variants': variants,
        'reference_forecast': {'rules': 'constant = (r1+r2)/2; linear-rate extrapolation = 2*r2-r1; evaluate r3. Reference-only, shared-product diagnostic, not independent truth.',
            'rows': forecasts, 'summary': {'status_counts': dict(Counter(r['status'] for r in forecasts)),
                'constant_error_m_s': moments([r['constant_error_m_s'] for r in evaluated]),
                'linear_rate_error_m_s': moments([r['linear_rate_error_m_s'] for r in evaluated]),
                'linear_rate_worsened_count': sum(r['linear_rate_worsened'] for r in evaluated)}}})


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
    print(json.dumps({k: v['summary'] for k, v in result['variants'].items()}), flush=True)
