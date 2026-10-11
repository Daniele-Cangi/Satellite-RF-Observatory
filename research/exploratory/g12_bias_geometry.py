"""Profile station-bias information across exposed G12 short-arc geometries.

Exploratory geometry diagnosis, not a bias fit or a physical uncertainty bound.
Reuse the original interval fits, covariance and target-independent calibration.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.linalg import helmert, qr, solve_triangular

from .real_phase import BASE, digest
from .real_target_bias_identifiability import REPORT, TARGET, bias_information
from .real_target_interval import CALIBRATION, TAGS, covariance
from ..kinematic.interval_fit import fit_intervals
from ..kinematic.synthetic import native
from ..kinematic.phase_rates import interval_matrix
from ..kinematic.receiver_time import central_jacobian, predict

RANK_RTOL = 1e-10


def profile_bias(jacobian, data_covariance, scale, station_count):
    """Whiten, then eliminate ALL arc-local state/clock/ground parameters by QR.

    The four remaining columns are zero-mean station biases, in metres. A common
    bias is a satellite-clock gauge. No normal-matrix subtraction or jitter.
    """
    jacobian, scale = np.asarray(jacobian, float), np.asarray(scale, float)
    chol = np.linalg.cholesky(data_covariance)
    design = solve_triangular(chol, jacobian*scale, lower=True)
    singular = np.linalg.svd(design, compute_uv=False)
    if len(singular) < len(scale) or singular[-1] <= singular[0]*RANK_RTOL:
        raise ValueError('arc-local nuisance design is rank deficient')
    basis = helmert(station_count, full=False).T
    columns = np.zeros((len(data_covariance), station_count-1))
    for i in range(len(TAGS)):
        columns[i*station_count:(i+1)*station_count] = basis
    weighted_bias = solve_triangular(chol, columns, lower=True)
    orthogonal, _ = qr(design, mode='full')
    complement = orthogonal[:, len(scale):].T
    slope = columns.copy()
    slope[:len(TAGS)*station_count] *= np.repeat(TAGS, station_count)[:, None]
    return (complement@weighted_bias, columns,
            complement@solve_triangular(chol, slope, lower=True))


def information_summary(profile):
    """Local bias-only information; covariance remains a conditional scenario."""
    matrix = np.asarray(profile, float)
    if matrix.ndim != 2 or matrix.shape[1] < 1 or not np.isfinite(matrix).all():
        raise ValueError('finite nonempty bias design required')
    _, singular, vh = np.linalg.svd(matrix, full_matrices=True)
    count = matrix.shape[1]
    rank = int(np.sum(singular > (singular[0]*RANK_RTOL if len(singular) else 0)))
    result = {'rank': rank, 'parameter_count': count,
              'singular_per_m': singular.tolist(), 'rank_relative_threshold': RANK_RTOL,
              'weakest_contrast_direction': vh[-1].tolist(),
              'conditional_worst_contrast_sigma_m': None}
    if rank == count:
        result['conditional_worst_contrast_sigma_m'] = float(1/singular[-1])
    return result


def combine_profiles(arcs, *, linear_drift=False):
    """Common bias, or common bias plus one drift per contrast over the span.

    Block-independent old weights are a comparison scenario, not an empirical
    temporal covariance. Arc-local states are NOT tied into a long polynomial.
    """
    if not arcs:
        raise ValueError('at least one admitted arc required')
    times = np.array([a['start_gpst_s']+60 for a in arcs], float)
    span = float(np.ptp(times))
    if linear_drift and span == 0:
        raise ValueError('distinct times required for drift diagnostic')
    profiles = [np.asarray(a['profile_per_m'], float) for a in arcs]
    if linear_drift:
        fraction = (times-times.mean())/span
        combined = np.vstack([np.column_stack([p, f*p+np.asarray(a['slope_profile_per_m_s'])/span])
                              for f,p,a in zip(fraction,profiles,arcs)])
    else:
        combined = np.vstack(profiles)
    return {'arc_count': len(arcs), 'endpoint_span_s': span,
            'bias_model': 'CONSTANT_PLUS_LINEAR_DRIFT' if linear_drift else 'CONSTANT',
            **information_summary(combined)}



def derivative_profile(fit, stations, data_covariance, use_phase, step):
    """Numerical robustness at the SAME fitted point, without another RF fit."""
    n = len(stations)
    scale = np.asarray(fit['parameter_scale'])
    physical = np.r_[fit['state'], fit['receiver_clocks'].ravel(),
                     fit['station_corrections_m'].ravel()]
    difference = interval_matrix(TAGS, n)
    def model(z):
        p = z*scale
        codes = predict(p[:11], TAGS, stations+p[11+2*n:].reshape(n,3),
                        p[11:11+2*n].reshape(n,2))['code_m'].ravel()
        return np.r_[codes, difference@codes if use_phase else [], p[11:]]
    jacobian = central_jacobian(model, physical/scale, step=step)/scale
    return profile_bias(jacobian, data_covariance, scale, n)


def run():
    files = {'rf_report': REPORT, 'target': TARGET,
             'positions': BASE/'inputs/day_reference/positions.json',
             'access': BASE/'real_target_phase_access_v2.json',
             'baseline': BASE/'results/day_reference_v1.json',
             'reference_phase': BASE/'results/reference_phase_clock_gps_only_v2.json',
             'previous_bias_report': BASE/'results/real_target_bias_identifiability_v1.json'}
    buffers = {name:path.read_bytes() for name,path in files.items()}
    data = {name:json.loads(raw) for name,raw in buffers.items()}
    frozen, target = data['rf_report'], data['target']
    if (frozen['target_input_sha256'] != digest(buffers['target'])
            or target['access_sha256'] != digest(buffers['access'])
            or frozen['baseline_sha256'] != digest(buffers['baseline'])
            or frozen['phase_clock_sha256'] != digest(buffers['reference_phase'])
            or frozen['target_orbit_accessed'] or target['target_state_accessed']
            or data['baseline']['target_orbit_accessed']
            or data['reference_phase']['target_values_accessed']
            or data['previous_bias_report']['frozen_rf_report_sha256'] != digest(buffers['rf_report'])):
        raise ValueError('historical input or target exclusion boundary differs')
    stations = tuple(frozen['stations'])
    n = len(stations)
    coverage = {}
    for station, source in target['stations'].items():
        rows = source.get('rows', [])
        available = [r['time_s'] for r in rows if r['status']=='AVAILABLE']
        coverage[station] = {'parse_status': source['status'], 'row_count':len(rows),
            'status_counts': dict(Counter(r['status'] for r in rows)),
            'available_gpst_s':available}
    common = sorted(set.intersection(*(set(coverage[s]['available_gpst_s']) for s in stations)))
    all_times = sorted(set.union(*(set(c['available_gpst_s']) for c in coverage.values())))
    structural = [{'time_gpst_s':t, 'available_stations':[s for s,c in coverage.items()
                    if t in c['available_gpst_s']]} for t in all_times]
    code_phase_variation = {}
    for station in stations:
        selected = [r for r in target['stations'][station]['rows'] if r['time_s'] in common]
        levels = np.array([r['code_m']-r['phase_m'] for r in selected])
        code_phase_variation[station] = {'first_gpst_s':selected[0]['time_s'],
            'last_gpst_s':selected[-1]['time_s'], 'sample_count':len(selected),
            'range_m':float(np.ptp(levels)), 'last_minus_first_m':float(levels[-1]-levels[0]),
            'relative_to_first_m':(levels-levels[0]).tolist()}
    rows = {s:{r['time_s']:r for r in target['stations'][s]['rows']} for s in stations}
    whole_cov, code_cov = covariance(n)
    arcs, retained = {'code_only':[], 'code_phase':[]}, []
    for case in frozen['cases']:
        start = case['start_gpst_s']
        times = [start,start+30,start+60]
        code = np.array([[rows[s][t]['code_m'] for s in stations] for t in times])
        phase = np.array([[rows[s][t]['phase_m'] for s in stations] for t in times])
        positions = np.array([data['positions'][s][(start+60-36000)//30] for s in stations])
        propagation = np.asarray(case['propagation_m'])
        clocks = np.asarray(case['clock_prior'])
        rates = np.diff(phase, axis=0)/30 - np.diff(propagation, axis=0)/30
        for name,use_phase,cov in [('code_only',False,code_cov),('code_phase',True,whole_cov)]:
            old = case['fits'][name]
            retained.append({'start_gpst_s':start, 'model':name, 'status':old['status']})
            if old['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
                continue
            fit = fit_intervals(TAGS, positions, code-propagation, rates, clocks, cov,
                    calibration_statuses=[CALIBRATION]*n, include_phase=use_phase)
            if (fit['status'] != old['status'] or fit['fit_covariance_sha256'] != old['fit_covariance_sha256']
                    or not np.allclose(fit['state'],old['state'],rtol=0,atol=1e-5)):
                raise ValueError('fit does not reproduce the historical RF case')
            profile, columns, slope = profile_bias(fit['data_jacobian'],cov,fit['parameter_scale'],n)
            alternatives = {}
            for factor in (.5, 2.):
                alt, _, alt_slope = derivative_profile(fit,positions,cov,use_phase,1e-5*factor)
                alternatives[str(factor)] = {'profile_per_m':alt.tolist(),
                                            'slope_profile_per_m_s':alt_slope.tolist()}
            arcs[name].append({'start_gpst_s':start, 'profile_per_m':profile.tolist(),
                'slope_profile_per_m_s':slope.tolist(), 'derivative_step_alternatives':alternatives,
                'position_response_per_m': (-fit['data_gain'][:3]@columns).tolist(),
                'original_augmented_rank':bias_information(fit,cov,n)['rank'],
                'single_arc':information_summary(profile)})
        print(start, 'profiled', flush=True)
    combined = {name:{'constant':combine_profiles(cases),
                       'linear_drift':combine_profiles(cases,linear_drift=True)}
                for name,cases in arcs.items()}
    robustness = {}
    for name,cases in arcs.items():
        robustness[name] = {}
        for factor in ('0.5','2.0'):
            alternative_arcs = [{'start_gpst_s':a['start_gpst_s'],
                                 **a['derivative_step_alternatives'][factor]} for a in cases]
            robustness[name][factor] = {'constant':combine_profiles(alternative_arcs),
                'linear_drift':combine_profiles(alternative_arcs,linear_drift=True)}
        result = combined[name]['constant']
        direction = np.asarray(result['weakest_contrast_direction'])
        pattern = helmert(n,full=False).T@direction
        result['weakest_station_contrast_pattern_max_abs_1'] = (pattern/np.max(np.abs(pattern))).tolist()
    return native({'schema':'exposed-g12-bias-geometry-v1',
        'scope':'Local profile information on exposed frozen RF geometries. Block-independent historical conditional weights; no physical bias amplitude, temporal covariance qualification or total position bound. Common bias is a clock gauge. All historical phase rejections retained.',
        'target_orbit_used':False, 'oracle_error_used':False, 'new_confirmation':False,
        'input_sha256':{name:digest(raw) for name,raw in buffers.items()},
        'source_sha256':digest(Path(__file__).read_bytes()),
        'stations':stations,'coverage':coverage,'common_available_gpst_s':common,
        'structural_coverage':structural,
        'target_code_minus_phase_variation':code_phase_variation,
        'historical_outcomes':retained,'arcs':arcs,'combined':combined,
        'finite_difference_robustness':robustness})


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('output already exists; retain previous reports')
    result=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
