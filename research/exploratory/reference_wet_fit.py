"""Shared station wet-delay nuisance with leave-one-candidate-out clocks.

Exposed-data development: keep the 22 candidates and nominal RF preparation.
One free zenith wet correction per station spans every arc, with its response
through reference clock recalibration as well as the candidate path. No weather
accuracy prior, oracle tuning, residual scaling or G12 state access.
"""
import argparse
from collections import Counter
import inspect
import json
from pathlib import Path

import numpy as np
from scipy.linalg import helmert

from . import reference_state_validation as baseline
from ..kinematic import dynamic_fit, orbital_dynamics as dynamics
from ..kinematic.synthetic import native

STEP_M = .01  # differentiation step, NOT a wet-delay sigma


class ShiftedWetWeather:
    """Change only zenith wet metres; retain the admitted VMF3 mapping/grid."""
    def __init__(self, weather, metres):
        if not np.isfinite(metres):
            raise ValueError('finite zenith wet correction required')
        self.weather, self.metres = weather, metres

    def evaluate(self, *args):
        values = np.array(self.weather.evaluate(*args), float)
        values[3] += self.metres
        return values


def propagation_model(weather, names):
    """Reuse the existing full geometry/ground/clock propagation derivatives."""
    def correction(pair, xyz, epoch, *, derivatives=False, wet_m=None):
        wet = np.zeros(len(names)) if wet_m is None else np.asarray(wet_m, float)
        if wet.shape != (len(names),) or not np.isfinite(wet).all():
            raise ValueError('one finite zenith wet correction per station required')
        pieces = []
        for j, name in enumerate(names):
            own = {k: v[:, j:j+1] for k, v in pair.items()}
            shifted = baseline.interval.shared.propagation_model(ShiftedWetWeather(weather, wet[j]), [name])
            part = shifted(own, xyz[j:j+1], epoch, derivatives=derivatives)
            if derivatives:
                plus = baseline.interval.shared.propagation_model(ShiftedWetWeather(weather, wet[j]+1.), [name])
                part['wet_derivative'] = plus(own, xyz[j:j+1], epoch)['delay_m']-part['delay_m']
            pieces.append(part)
        return {k: np.concatenate([p[k] for p in pieces], axis=1) for k in pieces[0]}
    return correction


def clock_coefficients(environment, station, endpoint):
    offset, rate, _ = environment
    level = offset(station, endpoint)
    increments = [rate(station, endpoint+t) for t in (-30., 0.)]
    if level['status'] != 'CALIBRATION_QUALIFIED' or any(r['status'] != 'ESTIMATED' for r in increments):
        raise ValueError('wet-perturbed reference calibration rejected')
    a, b = [r['rate_m_s'] for r in increments]
    return np.array([level['epochs'][0]['clock_m'], (a+b)/2., (a-b)/2.])


def attach_wet_response(data, candidate, arcs, weather):
    # A uniform shift computes all station-wise derivatives at once: each
    # station's reference calibrator uses only that station's observations.
    env = {z: baseline.calibration_environment(data, candidate, ShiftedWetWeather(weather, z))
           for z in (-STEP_M, STEP_M)}
    records = []
    for arc in arcs:
        response = []
        for station, clock in zip(arc['stations'], arc['clock_mean'], strict=True):
            minus, plus = [clock_coefficients(env[z], station, arc['endpoint_gpst_s'])
                           for z in (-STEP_M, STEP_M)]
            response.append((plus-minus)/(2*STEP_M))
            records.append({'station': station, 'endpoint_gpst_s': arc['endpoint_gpst_s'],
                'response': response[-1], 'even_clock_coefficients': (plus+minus)/2-clock})
        arc['wet_clock_response'] = np.array(response)
        arc['propagation'] = propagation_model(weather, arc['stations'])
    return native(records)


def linear_information(fit, arcs):
    """Conditional information and raw-data response, never oracle differences."""
    prepared, names, _ = dynamic_fit.prepare(arcs, True)
    wet = 'station_zenith_wet_correction_m' in fit
    scale = np.r_[dynamic_fit.STATE_SCALE, np.full(len(names)-1, 100.), np.ones(len(names) if wet else 0)]
    physical = np.r_[fit['state_ecef_m_m_s'], fit['bias_contrast_coefficients_m'],
        [fit['station_zenith_wet_correction_m'][s] for s in names] if wet else []]
    local = [np.r_[p['satellite_clock'], np.asarray(p['receiver_clocks']).ravel(),
                    np.asarray(p['station_corrections_m']).ravel()]/a['local_scale']
             for a, p in zip(prepared, fit['arc_parameters'], strict=True)]
    details = {}
    _, _, _, cov, _, _ = dynamic_fit.linearize(physical/scale, local, prepared, scale,
        fit['epoch_gpst_s'], fit['integrated_bounds_s'], fit['j2'], diagnostics=details)
    eigen, vectors = np.linalg.eigh(cov[:3, :3])
    axis = vectors[:, -1]
    variances = Counter()
    for a, response in zip(prepared, details['observation_response'], strict=True):
        n, c, p = a['n'], a['codes'].size, len(a['difference'])
        v = axis@response[:3]
        for label, indices in [('code', np.arange(c)), ('phase', np.arange(c, c+p)),
            ('clock_offset', np.arange(c+p, c+p+3*n, 3)),
            ('clock_mean_rate', np.arange(c+p+1, c+p+3*n, 3)),
            ('clock_contrast_rate', np.arange(c+p+2, c+p+3*n, 3)),
            ('ground', np.arange(c+p+3*n, len(v)))]:
            variances[label] += float(v[indices]@np.asarray(a['covariance'])[np.ix_(indices, indices)]@v[indices])
    info = {'weak_position_axis_ecef': axis, 'weak_position_sigma_m': np.sqrt(eigen[-1]),
        'conditional_weak_variance_by_observation_family_m2': dict(variances),
        'position_1sigma_axes_m': np.sqrt(eigen),
        'velocity_1sigma_axes_m_s': np.sqrt(np.linalg.eigvalsh(cov[3:6, 3:6])),
        'all_components_are_conditional': True}
    bias_stop = 6+len(names)-1
    direction = cov[:, :3]@axis/eigen[-1]
    info['weak_mode_per_m_position'] = {'state_ecef_m_m_s': direction[:6],
        'station_code_bias_m': dict(zip(names, helmert(len(names), full=False).T@direction[6:bias_stop], strict=True)),
        'delta_chi2': 1./eigen[-1]}
    bias_cov = cov[6:bias_stop, 6:bias_stop]
    precision = {}
    for sigma in (.01, .1, 1., 10.):
        measured = cov-cov[:, 6:bias_stop]@np.linalg.solve(bias_cov+sigma**2*np.eye(len(names)-1), cov[6:bias_stop, :])
        precision[str(sigma)] = {'largest_position_sigma_m': float(np.sqrt(np.linalg.eigvalsh(measured[:3, :3])[-1])),
            'largest_velocity_sigma_m_s': float(np.sqrt(np.linalg.eigvalsh(measured[3:6, 3:6])[-1]))}
    info['hypothetical_independent_code_bias_contrast_sigma_m'] = precision
    if wet:
        k = 6+len(names)-1
        wet_cov = cov[k:, k:]
        info.update(wet_1sigma_m=dict(zip(names, np.sqrt(np.diag(wet_cov)), strict=True)),
            weak_position_wet_correlation=dict(zip(names, axis@cov[:3, k:]/np.sqrt(eigen[-1]*np.diag(wet_cov)), strict=True)))
        # Profile a displacement of one metre along the weak position axis,
        # allowing all other parameters to compensate. This is a local mode,
        # not a second physical orbit or a physical uncertainty bound.
        info['weak_mode_per_m_position']['station_zenith_wet_m'] = dict(zip(names, direction[k:], strict=True))
        # A separately measured, correlated wet vector would add this information.
        # Show requirements rather than treating a hypothetical measurement as data.
        precision = {}
        for sigma in (.001, .01, .1, 1.):
            measured = cov-cov[:, k:]@np.linalg.solve(wet_cov+sigma**2*np.eye(len(names)), cov[k:, :])
            precision[str(sigma)] = {'largest_position_sigma_m': float(np.sqrt(np.linalg.eigvalsh(measured[:3, :3])[-1])),
                'largest_velocity_sigma_m_s': float(np.sqrt(np.linalg.eigvalsh(measured[3:6, 3:6])[-1]))}
        info['hypothetical_independent_wet_measurement_sigma_m'] = precision
    return native(info)


def predict(fit, arcs, weather):
    predictions = baseline.interval.predict(fit, arcs, weather)
    if 'station_zenith_wet_correction_m' not in fit:
        return predictions
    curve = dynamics.Trajectory(fit['state_ecef_m_m_s'], fit['integrated_bounds_s'], j2=fit['j2'])
    for arc, parameters, record in zip(sorted(arcs, key=lambda a: a['endpoint_gpst_s']), fit['arc_parameters'], predictions, strict=True):
        if record['status'] != 'PREDICTED':
            continue
        xyz = arc['stations_m']+np.asarray(parameters['station_corrections_m'])
        pair = baseline.interval.clock_observations.predict(curve, arc['endpoint_gpst_s']-fit['epoch_gpst_s'], [0., 30.],
            xyz, parameters['receiver_clocks'], parameters['satellite_clock'], baseline.interval.clock_basis([0., 30.]))
        wet = [fit['station_zenith_wet_correction_m'][s] for s in arc['stations']]
        nominal = arc['propagation'](pair, xyz, fit['epoch_gpst_s'])['delay_m']
        actual = arc['propagation'](pair, xyz, fit['epoch_gpst_s'], wet_m=wet)['delay_m']
        change = actual-nominal
        record['code_m'] = np.asarray(record['code_m'])+change[1]
        record['phase_rate_m_s'] = np.asarray(record['phase_rate_m_s'])+np.diff(change, axis=0)[0]/30.
        record['propagation_m'] = actual
    return native(predictions)


def calibration_check(data, candidate, arcs, fit, weather):
    """Full recalibration at the inferred wet values; no feedback or retuning."""
    if 'station_zenith_wet_correction_m' not in fit:
        return {'status': 'FIT_UNAVAILABLE', 'rows': []}
    environments = {s: baseline.calibration_environment(data, candidate, ShiftedWetWeather(weather, z))
                    for s, z in fit['station_zenith_wet_correction_m'].items()}
    rows, wet_levels = [], {}
    mjd = (baseline.datetime.fromisoformat(data['plan']['date_gpst'])-baseline.datetime(1858, 11, 17)).days
    for arc in arcs:
        for j, s in enumerate(arc['stations']):
            record = {'station': s, 'endpoint_gpst_s': arc['endpoint_gpst_s']}
            z = fit['station_zenith_wet_correction_m'][s]
            lat, lon, height, _ = baseline.interval.shared.geodetic(arc['stations_m'][j])
            levels = [weather.evaluate(mjd+(arc['endpoint_gpst_s']+t-18.)/86400.,
                np.degrees(lat), np.degrees(lon), height, 90.)[3]+z for t in (-60., -30., 0., 30.)]
            wet_levels[s] = min(wet_levels.get(s, np.inf), min(levels))
            try:
                actual = clock_coefficients(environments[s], s, arc['endpoint_gpst_s'])
                predicted = arc['clock_mean'][j]+arc['wet_clock_response'][j]*z
                record.update(status='EVALUATED', exact_minus_linear_clock_coefficients=actual-predicted)
            except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                record.update(status='CALIBRATION_REJECTED', reason=str(error))
            rows.append(record)
    return native({'status': 'DIAGNOSTIC_ONLY', 'rows': rows,
        'status_counts': dict(Counter(r['status'] for r in rows)),
        'minimum_total_zenith_wet_m': wet_levels,
        'physical_domain_status': 'NEGATIVE_TOTAL_ZENITH_WET' if min(wet_levels.values()) < 0. else 'NONNEGATIVE_TOTAL_ZENITH_WET_ONLY',
        'negative_total_wet_stations': [s for s, z in wet_levels.items() if z < 0.]})


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
            for window in windows:
                if window['status'] == 'RF_COVERED':
                    window.update(status='CANDIDATE_PREPARATION_FAILED', reason=str(error))
        record = {'windows': native(windows), 'window_status_counts': dict(Counter(w['status'] for w in windows)), 'variants': {}}
        prepared[candidate] = arcs
        # Refit the baseline from RF as well: no historical fitted state seeds
        # either variant. Both use exactly the same preparation/support.
        for variant in ('fixed_vmf3', 'free_station_wet'):
            fit = {'status': 'INSUFFICIENT_PREPARED_ARCS', 'arc_count': len(arcs)}
            variant_record = {}
            if len(arcs) >= 2:
                try:
                    if variant == 'free_station_wet':
                        variant_record['clock_recalibration_response'] = attach_wet_response(data, candidate, arcs, weather)
                    fit = dynamic_fit.fit(arcs, progress=lambda r: print(candidate, variant, r, flush=True))
                except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                    fit = {'status': 'FIT_FAILED', 'reason': str(error)}
            variant_record.update(fit=native(fit), rf_predictions=predict(fit, arcs, weather) if arcs else [])
            variant_record['prediction_sha256'] = baseline.interval.shared.digest(json.dumps(
                variant_record['rf_predictions'], separators=(',', ':'), allow_nan=False).encode())
            if 'state_ecef_m_m_s' in fit:
                try:
                    variant_record['information'] = linear_information(fit, arcs)
                except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                    variant_record['information'] = {'status': 'INFORMATION_FAILED', 'reason': str(error)}
            if variant == 'free_station_wet':
                variant_record['calibration_check'] = calibration_check(data, candidate, arcs, fit, weather)
            record['variants'][variant] = variant_record
            print(candidate, variant, fit['status'], flush=True)
        results[candidate] = record
    # All new estimates, covariances and predictions precede all scoring.
    for candidate, record in results.items():
        for variant in record['variants'].values():
            variant['rf_evaluation'] = baseline.score_rf(data, candidate, variant['rf_predictions'])
            variant['state_evaluation'] = {'status': 'FIT_UNAVAILABLE', 'rows': []}
            if 'state_ecef_m_m_s' in variant['fit']:
                try:
                    variant['state_evaluation'] = baseline.state_errors(variant['fit'], prepared[candidate], baseline.oracle(data, candidate))
                except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                    variant['state_evaluation'] = {'status': 'ORACLE_UNAVAILABLE', 'reason': str(error), 'rows': []}
    modules = [baseline, baseline.interval, baseline.interval.shared, dynamic_fit, dynamics,
        baseline.interval.clock_observations, baseline.precise, baseline.attitude, baseline.bias,
        baseline.conventions, baseline.sp3, baseline.day, baseline.day.atmosphere, baseline.interval.shared.meteo]
    sources = ([Path(m.__file__) for m in modules]+[Path(__file__)]+
        [Path(inspect.getmodule(f).__file__) for f in [baseline.clock_rate, baseline.calibrate_fixed, baseline.solve, baseline.troposphere]])
    return native({'schema': 'exposed-reference-shared-wet-fit-v1',
        'scope': 'Exposed 22-candidate/440-window fixed preparation; fixed VMF3 vs free station wet corrections, shared through reference calibration and candidate paths. Local conditional covariance, not a total error budget or independent CODE truth.',
        'candidate_products_used_in_own_fit': False, 'g12_state_accessed': False, 'oracle_tuning': False,
        'all_predictions_before_scoring': True, 'new_confirmation': False, 'physical_covariance_qualified': False,
        'production_floors_changed': False, 'wet_prior_used': False,
        'wet_assumption': 'one signed zenith wet residual per station constant across the training hour and forecasts; linearized reference recalibration, exact VMF3 mapping at current candidate geometry; full recalibration check retained',
        'differentiation_step_m': STEP_M,
        'input_sha256': {k: baseline.interval.shared.digest(v) for k, v in raw.items()},
        'weather_receipt_sha256': baseline.interval.shared.meteo.RECEIPT_SHA,
        'source_sha256': {p.relative_to(baseline.BASE.parents[1]).as_posix(): baseline.interval.shared.digest(p.read_bytes()) for p in sources},
        'fit_status_counts': {v: dict(Counter(r['variants'][v]['fit']['status'] for r in results.values())) for v in ('fixed_vmf3', 'free_station_wet')},
        'candidates': results})


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
