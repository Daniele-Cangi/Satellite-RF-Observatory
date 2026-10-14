"""Exposed G12 refit with measured interval clocks and free common curvature.

Same eight phase arcs, target endpoints, RF floors and acceptance threshold as
v4. Two explicitly conditional reference-error scenarios, not a calibrated
physical covariance. No target orbit, clock product or historical state seed.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from scipy.linalg import block_diag

from . import g12_dynamic_fit as shared, g12_phase_diagnostic as diagnostic
from ..kinematic import dynamic_fit, clock_observations, orbital_dynamics as dynamics
from ..kinematic.phase_rates import interval_matrix
from ..kinematic.synthetic import native

FILES = diagnostic.FILES
SCENARIOS = ('independent_endpoints', 'shared_endpoints_added')


def clock_basis(tags):
    """[endpoint offset, 60 s mean rate, interval half-difference rate].

    Piecewise linear through [-60,-30,0]; future tags use the original mean
    rate, not a quadratic/trend extrapolation. No training value after tag 0.
    """
    tags = np.asarray(tags, float)
    shape = np.interp(tags, [-60., -30., 0.], [0., 30., 0.], left=0., right=0.)
    return np.column_stack([np.ones(len(tags)), tags, shape])


def joint_covariance(n, scenario):
    if scenario not in SCENARIOS:
        raise ValueError('declared clock covariance scenario required')
    # Three independent reference clock endpoint errors with sigma=sqrt(1800)*
    # .01 m yield rate covariance .01^2 [[4,-2],[-2,4]]. Transform to mean /
    # half-difference: diag(.01^2,3*.01^2). This preserves the historical mean
    # weight. It is an assumed endpoint model, NOT inferred from target residuals
    # or from overlapping-reference LOO scatter.
    clock = np.kron(np.eye(n), np.diag([4., .01**2, 3*.01**2]))
    if scenario == 'shared_endpoints_added':
        common = np.zeros((3*n, 2))
        common[1::3, 0] = .01
        common[2::3, 1] = np.sqrt(3)*.01
        clock += common@common.T
    difference = interval_matrix(shared.TAGS, n)
    phase = .02**2*difference@difference.T
    return block_diag(400*np.eye(3*n), phase, clock, .25*np.eye(3*n))


def training_arcs(data, cases, scenario):
    index, _ = diagnostic.reference_index(data['reference_clock'])
    arcs = shared.training_arcs(cases, data['target'], data['positions'],
                               data['baseline'], data['reference_clock'], 'code_phase')
    for a in arcs:
        rates = np.array([[index[s, a['endpoint_gpst_s']+t]['estimators']['median']['rate_m_s']
                           for t in (-30., 0.)] for s in a['stations']])
        a['clock_mean'] = np.column_stack([a['clock_mean'], (rates[:, 0]-rates[:, 1])/2.])
        a['receiver_clock_basis'] = clock_basis(a['tags_s'])
        a['satellite_clock_count'] = 3
        a['covariance'] = joint_covariance(len(a['stations']), scenario)
    return arcs


def predict(fitted, arcs, weather):
    if 'state_ecef_m_m_s' not in fitted:
        return [{'endpoint_gpst_s': a['endpoint_gpst_s'], 'status': 'FIT_UNAVAILABLE'} for a in arcs]
    epoch = fitted['epoch_gpst_s']
    curve = dynamics.Trajectory(fitted['state_ecef_m_m_s'], fitted['integrated_bounds_s'], j2=fitted['j2'])
    last = max(a['endpoint_gpst_s'] for a in arcs)
    predictions = []
    for a, p in zip(sorted(arcs, key=lambda a: a['endpoint_gpst_s']), fitted['arc_parameters'], strict=True):
        record = {'endpoint_gpst_s': a['endpoint_gpst_s'], 'withheld_gpst_s': a['endpoint_gpst_s']+30,
                  'kind': 'BEYOND_ALL_TRAINING' if a['endpoint_gpst_s']+30 > last else 'TEMPORAL_HOLDOUT',
                  'fit_status': fitted['status']}
        try:
            xyz = a['stations_m']+np.asarray(p['station_corrections_m'])
            pair = clock_observations.predict(curve, a['endpoint_gpst_s']-epoch, [0., 30.], xyz,
                       p['receiver_clocks'], p['satellite_clock'], clock_basis([0., 30.]))
            correction = shared.propagation_model(weather, a['stations'])(pair, xyz, epoch)
            path = pair['code_m']+correction['delay_m']
            record.update(status='PREDICTED', stations=a['stations'],
                code_m=path[1]+np.array([fitted['station_code_bias_m'][s] for s in a['stations']]),
                phase_rate_m_s=np.diff(path, axis=0)[0]/30., propagation_m=correction['delay_m'],
                elevation_deg=correction['elevation_deg'])
        except (ValueError, np.linalg.LinAlgError) as error:
            record.update(status='PREDICTION_FAILED', reason=str(error))
        predictions.append(record)
    return native(predictions)


def observability(fitted):
    if 'conditional_global_covariance' not in fitted:
        return {'status': 'FIT_UNAVAILABLE'}
    covariance = np.asarray(fitted['conditional_global_covariance'])
    def axes(block):
        return np.sqrt(np.linalg.eigvalsh(block)).tolist()
    return {'status': 'LOCAL_CONDITIONAL_ONLY', 'global_parameter_count': len(covariance),
            'position_1sigma_axes_m': axes(covariance[:3, :3]),
            'velocity_1sigma_axes_m_s': axes(covariance[3:6, 3:6]),
            'bias_contrast_1sigma_axes_m': axes(covariance[6:, 6:]),
            'scaled_condition': fitted['scaled_condition'], 'physical_covariance_qualified': False}


def read_inputs():
    raw = {k: (shared.BASE/p).read_bytes() for k, p in FILES.items()}
    data = {k: json.loads(v) for k, v in raw.items()}
    old, clock = data['fit'], data['reference_clock']
    if (old['historical_fit_geometry_used'] or any(old[k] for k in
            ['target_orbit_used', 'oracle_error_used', 'prior_target_state_used', 'new_confirmation'])
            or any(old['input_sha256'][k] != shared.digest(v) for k, v in raw.items() if k != 'fit')
            or old['weather_receipt_sha256'] != shared.meteo.RECEIPT_SHA
            or data['target']['target_state_accessed'] or data['baseline']['target_orbit_accessed']
            or not data['baseline']['calibration_complete']
            or data['target']['access_sha256'] != shared.digest(raw['access'])
            or clock['input_sha256'] != shared.digest(raw['reference_phase_input'])
            or clock['baseline_report_sha256'] != shared.digest(raw['baseline'])
            or clock['evaluation_after_gpst_s'] != 36000):
        raise ValueError('historical RF/reference boundary differs')
    diagnostic.reference_index(clock)
    return raw, data


def run():
    raw, data = read_inputs()
    cases, selection = shared.cohort(data['hour'], 'code_phase')
    if any(data['fit']['variants']['code_phase_'+force]['cohort'] != native(selection) for force, _ in shared.FORCES):
        raise ValueError('inherited phase cohort differs')
    weather = shared.meteo.WeatherGrid(shared.meteo.read_inputs()[0])
    results = {}
    for scenario in SCENARIOS:
        arcs = training_arcs(data, cases, scenario)
        for a in arcs:
            a['propagation'] = shared.propagation_model(weather, a['stations'])
        for force, j2 in shared.FORCES:
            label = scenario+'_'+force
            try:
                fitted = dynamic_fit.fit(arcs, j2=j2, progress=lambda r: print(label, r, flush=True))
            except (ValueError, KeyError, np.linalg.LinAlgError) as error:
                fitted = {'status': 'FIT_FAILED', 'reason': str(error)}
            predictions = predict(fitted, arcs, weather)
            results[label] = {'fit': native(fitted), 'observability': observability(fitted),
                'predictions': predictions,
                'frozen_prediction_sha256': shared.digest(json.dumps(predictions, separators=(',', ':'), allow_nan=False).encode())}
    # Every variant's predictions fixed before scoring any target future RF.
    for label, result in results.items():
        result['withheld'], result['summary'] = shared.score(result['predictions'], cases, data['target'], 'code_phase')
        force = 'central_j2' if label.endswith('central_j2') else 'central'
        old = data['fit']['variants']['code_phase_'+force]
        result['v4_same_cohort'] = {'fit_status': old['fit']['status'], 'summary': old['summary'],
                                  'observability': observability(old['fit'])}
    producers = [Path(m.__file__) for m in [shared, diagnostic, dynamic_fit, clock_observations, dynamics]]+[Path(__file__)]
    return native({'schema': 'exposed-g12-interval-clocks-v1',
        'scope': 'Exposed inherited eight-arc phase cohort; interval receiver clocks plus free satellite-clock curvature. Conditional covariance scenarios only; no physical accuracy, global uniqueness or confirmation claim.',
        'target_orbit_used': False, 'oracle_error_used': False, 'prior_target_state_used': False,
        'historical_fit_geometry_used': False, 'new_confirmation': False, 'physical_covariance_qualified': False,
        'production_floors_changed': False, 'historical_code_floor_m': 20., 'phase_endpoint_sigma_m': .02,
        'target_elevation_mask_deg': 10., 'residual_threshold_p': .01,
        'clock_model': {'receiver': '[endpoint offset m, mean rate m/s, interval half-difference m/s]; piecewise linear on three tags',
            'satellite': '[offset m, slope m/s, curvature coefficient m/s^2] at transmit GPST; curvature unpenalized',
            'future_receiver': 'original fitted mean rate; no clock contrast extrapolation',
            'future_satellite': 'linear tangent at arc endpoint; no curvature extrapolation',
            'reference_covariance': 'conditional iid endpoint sigma=sqrt(1800)*.01 m, giving mean variance .01^2 and half-difference variance 3*.01^2; endpoint offset independent with variance 4 m^2',
            'shared_sensitivity': 'add one common endpoint-error process of the same amplitude across stations per arc; full within-arc clock covariance retained',
            'unqualified': 'absolute/shared reference errors, offset-increment correlation, cross-arc correlation, force/propagation and bias stability; scenarios are not a physical error bound'},
        'cohort': selection, 'input_sha256': {k: shared.digest(v) for k, v in raw.items()},
        'weather_receipt_sha256': shared.meteo.RECEIPT_SHA,
        'source_sha256': {p.name: shared.digest(p.read_bytes()) for p in producers}, 'variants': results})


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
