"""Local absolute-code-bias information on the exposed G12 RF geometry.

This reuses the existing interval solver's gain/Jacobian. Biases are analytic
columns, not fitted to the already revealed orbit. Formal variances remain
conditional on the v2 weighting scenario and cannot bound physical bias.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.linalg import helmert, solve_triangular

from .real_phase import BASE, digest
from .real_target_interval import CALIBRATION, TAGS, covariance
from ..kinematic.interval_fit import fit_intervals
from ..kinematic.synthetic import native

REPORT = BASE/'results/real_target_interval_v2.json'
TARGET = BASE/'inputs/real_phase/g12_target_phase_v2.json'


def bias_information(fit, data_covariance, station_count):
    """Compare omitted +1 m station modes with free zero-mean bias contrasts."""
    n, code_count = station_count, station_count*len(TAGS)
    data_size = len(data_covariance)
    responses = []
    for station in range(n):
        perturbation = np.zeros(data_size)
        perturbation[station:code_count:n] = 1.
        delta = fit['data_gain']@perturbation
        responses.append({'position_t0_m_per_1m': float(np.linalg.norm(delta[:3])),
                          'position_t_plus_30_m_per_1m': float(np.linalg.norm(
                              delta[:3]+30*delta[3:6]+450*delta[6:9]))})
    basis = helmert(n, full=False).T  # n by n-1, orthonormal and zero-mean.
    columns = np.zeros((data_size, n-1))
    for i in range(len(TAGS)):
        columns[i*n:(i+1)*n] = basis
    jacobian = np.column_stack([fit['data_jacobian'], columns])
    scales = np.r_[fit['parameter_scale'], np.full(n-1, 20.)]
    whitened = solve_triangular(np.linalg.cholesky(data_covariance),
                                jacobian*scales, lower=True)
    _, singular, vh = np.linalg.svd(whitened, full_matrices=False)
    rank = int(np.sum(singular > singular[0]*1e-10))
    result = {'rank': rank, 'parameter_count': len(scales),
              'measurement_count': data_size, 'formal_residual_dof': data_size-rank,
              'scaled_condition': float(singular[0]/singular[-1]),
              'smallest_scaled_singular': float(singular[-1]),
              'rank_relative_threshold': 1e-10,
              'omitted_bias_unit_responses': responses}
    near_null = []
    for index in range(rank, len(scales)):
        direction = vh[index]*scales
        station_bias = basis@direction[-(n-1):]
        amplitude = float(np.max(np.abs(station_bias)))
        near_null.append({'singular_over_largest': float(singular[index]/singular[0]),
                          'station_bias_contrast_m_per_unit_scaled_mode': station_bias.tolist(),
                          'position_t0_m_per_1m_max_station_bias':
                          float(np.linalg.norm(direction[:3])/amplitude) if amplitude > 1e-12 else None,
                          'velocity_t0_m_s_per_1m_max_station_bias':
                          float(np.linalg.norm(direction[3:6])/amplitude) if amplitude > 1e-12 else None})
    result['near_null_directions'] = near_null
    if rank == len(scales):
        scaled_cov = (vh.T/singular**2)@vh
        physical_cov = scaled_cov*scales[:, None]*scales[None, :]
        contrast_cov = basis@physical_cov[-(n-1):, -(n-1):]@basis.T
        result.update(formal_position_sigma_max_m=float(np.sqrt(np.linalg.eigvalsh(
                          physical_cov[:3, :3])[-1])),
                      formal_position_sigma_max_without_bias_m=float(np.sqrt(np.linalg.eigvalsh(
                          fit['covariance_joint'][:3, :3])[-1])),
                      formal_station_bias_contrast_sigma_max_m=float(np.sqrt(np.diag(contrast_cov).max())))
    else:
        result['formal_position_sigma_max_m'] = None
        result['formal_station_bias_contrast_sigma_max_m'] = None
    return result


def run():
    frozen_bytes = REPORT.read_bytes()
    frozen = json.loads(frozen_bytes)
    target_bytes = TARGET.read_bytes()
    target = json.loads(target_bytes)
    if (frozen['target_input_sha256'] != digest(target_bytes)
            or frozen['target_orbit_accessed'] or target['target_state_accessed']
            or frozen['status_counts'] != {'EVALUATED': 20}):
        raise ValueError('exposed RF inputs differ from frozen fit report')
    stations = tuple(frozen['stations'])
    positions = json.loads((BASE/'inputs/day_reference/positions.json').read_bytes())
    n = len(stations)
    whole_cov, code_cov = covariance(n)
    rows = {s: {r['time_s']: r for r in target['stations'][s]['rows']}
            for s in stations}
    cases = []
    for case in frozen['cases']:
        start = case['start_gpst_s']
        times = [start, start+30, start+60]
        code = np.array([[rows[s][t]['code_m'] for s in stations] for t in times])
        phase = np.array([[rows[s][t]['phase_m'] for s in stations] for t in times])
        station_xyz = np.array([positions[s][(start+60-36000)//30] for s in stations])
        propagation = np.asarray(case['propagation_m'])
        clock = np.asarray(case['clock_prior'])
        rates = np.diff(phase, axis=0)/30. - np.diff(propagation, axis=0)/30.
        outcomes = {}
        for name, use_phase, data_cov in (('code_only', False, code_cov),
                                           ('code_phase', True, whole_cov)):
            frozen_fit = case['fits'][name]
            if frozen_fit['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
                outcomes[name] = {'status': frozen_fit['status']}
                continue
            fit = fit_intervals(TAGS, station_xyz, code-propagation, rates,
                                clock, data_cov, calibration_statuses=[CALIBRATION]*n,
                                include_phase=use_phase)
            if (fit['status'] != frozen_fit['status']
                    or not np.allclose(fit['state'], frozen_fit['state'], rtol=0, atol=1e-5)
                    or fit['fit_covariance_sha256'] != frozen_fit['fit_covariance_sha256']):
                raise ValueError('fit differs from frozen RF report at '+str(start)
                    +': '+name+', '+fit['status']+'/'+frozen_fit['status']
                    +', max state difference '+str(float(np.max(np.abs(
                        fit['state']-np.asarray(frozen_fit['state']))))))
            outcomes[name] = {'status': fit['status'], **bias_information(fit, data_cov, n)}
        cases.append({'start_gpst_s': start, 'models': outcomes})
        print(start, outcomes['code_only']['rank'],
              outcomes['code_phase'].get('rank', 'REJECTED'), flush=True)
    return native({'schema': 'exposed-g12-absolute-code-bias-information-v1',
                   'scope': 'Local Jacobian and unit-bias response on already exposed RF fits. Zero-mean station bias contrasts only; common code level remains a satellite-clock gauge. Formal covariance uses the old conditional weights, not a measured physical bias amplitude or total position bound.',
                   'target_orbit_used': False, 'oracle_error_used': False,
                   'frozen_rf_report_sha256': digest(frozen_bytes),
                   'target_input_sha256': digest(target_bytes),
                   'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'counts': {'phase_fit_status': dict(Counter(c['models']['code_phase']['status'] for c in cases))},
                   'cases': cases})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n',
                           encoding='utf-8', newline='\n')
