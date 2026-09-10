"""S2 joint Gaussian fit of RF pairs, reference clocks and ground coordinates.

Covariance is fixed BEFORE fitting, never estimated/rescaled from residuals.
Ground coordinates are nuisance parameters with terrestrial measurements.
The target has no trajectory/clock prior and initialization uses RF data only.
Chi-square calibration is exact for the local linear Gaussian problem, only
approximate for this nonlinear finite-branch solver. No real RF qualification.
"""
import hashlib

import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import least_squares
from scipy.stats import chi2

from positioning.solver import solve
from .inverse_uncertainty import output_values, validate_covariance, vector
from .receiver_time import central_jacobian, cholesky_covariance, predict

ACCEPTED_CALIBRATIONS = {'CONDITIONAL_CLOCK_MODEL_ACCEPTED', 'REFERENCE_MODEL_ACCEPTED'}


def covariance_hash(covariance):
    return hashlib.sha256(np.asarray(covariance, dtype='<f8').tobytes()).hexdigest()


def whitened_geometry(jacobian, covariance, scale):
    """SVD gain and covariance in physical units, no residual variance factor."""
    chol = cholesky_covariance(covariance, len(jacobian))
    scaled = solve_triangular(chol, jacobian*scale, lower=True)
    u, singular, vh = np.linalg.svd(scaled, full_matrices=False)
    if len(singular) < len(scale) or singular[-1] <= singular[0]*1e-10:
        raise ValueError('joint model rank deficient in scaled coordinates')
    inverse = scale[:, None]*((vh.T/singular)@u.T)
    gain = inverse@solve_triangular(chol, np.eye(len(chol)), lower=True)
    return {'gain': gain, 'covariance': inverse@inverse.T,
            'scaled_condition': float(singular[0]/singular[-1]),
            'whitened_basis': u, 'rank': len(singular)}


def fit_joint(tags_s, stations_m, codes_m, rates_m_s, clock_mean, covariance, *, calibration_statuses):
    """Data order: code, rate (time/receiver); clocks (receiver/2); ground (receiver/3).

    Ground offsets relative to supplied coordinates keep finite differences
    well-scaled. Positive coordinate residual means fitted minus reported.
    Rejected calibrations stop before decoding target measurement values.
    """
    if any(status not in ACCEPTED_CALIBRATIONS for status in calibration_statuses):
        raise ValueError('reference calibration rejected; no target fit')
    tags, stations, clocks = [np.asarray(a, float) for a in (tags_s, stations_m, clock_mean)]
    if (tags.ndim != 1 or len(tags) < 3 or tags[-1] != 0 or np.any(np.diff(tags) <= 0)
            or stations.ndim != 2 or stations.shape[1] != 3 or len(stations) < 5
            or clocks.shape != (len(stations), 2) or len(calibration_statuses) != len(stations)
            or not all(np.isfinite(a).all() for a in (tags, stations, clocks))):
        raise ValueError('finite tags ending at zero, >=5 stations and their clock calibrations required')
    codes, rates = np.asarray(codes_m, float), np.asarray(rates_m_s, float)
    n = len(stations)
    if codes.shape != (len(tags), n) or rates.shape != codes.shape or not all(np.isfinite(a).all() for a in (codes, rates)):
        raise ValueError('finite complete target code/rate window required')
    nobs = 2*codes.size
    observed = np.r_[codes.ravel(), rates.ravel(), clocks.ravel(), np.zeros(3*n)]
    covariance = validate_covariance(covariance, len(observed))
    chol = cholesky_covariance(covariance, len(observed))  # Strict SPD; no jitter/floors.
    clock_end = 11+2*n
    scale = np.r_[[1e7]*3, [1e3]*3, [1.]*3, 1e5, 10., np.tile([1000., 1.], n), np.full(3*n, 1e5)]
    # Scaled central steps are 1 m for ground, avoiding cancellation at ECEF magnitudes.

    def model(z):
        p = z*scale
        pair = predict(p[:11], tags, stations+p[clock_end:].reshape(n, 3), p[11:clock_end].reshape(n, 2))
        return np.r_[vector(pair), p[11:]]

    def residual(z):
        return solve_triangular(chol, model(z)-observed, lower=True)

    snapshot = solve(codes[-1]-clocks[:, 0], stations,
                     covariance[codes.size-n:codes.size, codes.size-n:codes.size], atmosphere=False)
    fits, failures = [], []
    for branch in snapshot['branches']:
        q = np.asarray(branch['q'])
        unit = q[:3]-stations
        unit /= np.linalg.norm(unit, axis=1)[:, None]
        vc = np.linalg.lstsq(np.column_stack([unit, np.ones(n)]), rates[-1]-clocks[:, 1], rcond=None)[0]
        initial = np.r_[q[:3], vc[:3], np.zeros(3), -q[3], -vc[3], clocks.ravel(), np.zeros(3*n)]
        try:
            result = least_squares(residual, initial/scale,
                jac=lambda z: central_jacobian(residual, z), max_nfev=150,
                ftol=1e-10, xtol=1e-11, gtol=1e-9)
        except ValueError as error:
            failures.append(str(error))
            continue
        if not result.success:
            failures.append(str(result.message))
        elif all(np.linalg.norm(result.x-other.x) > 1e-7 for other in fits):
            fits.append(result)
    if not fits:
        raise ValueError('no converged joint branch: '+str(failures))
    fits.sort(key=lambda r: r.fun@r.fun)
    result = fits[0]
    physical = result.x*scale
    jacobian = central_jacobian(model, result.x)/scale
    geometry = whitened_geometry(jacobian, covariance, scale)
    cost = float(result.fun@result.fun)
    dof = len(observed)-geometry['rank']
    p_value = float(chi2.sf(cost, dof))
    ambiguous = any(float(r.fun@r.fun)-cost <= chi2.ppf(.95, len(scale)) for r in fits[1:])
    status = ('AMBIGUOUS' if ambiguous else 'BRANCH_SEARCH_INCOMPLETE' if failures else
              'MODEL_REJECTED' if p_value < .01 else 'CONDITIONAL_JOINT_MODEL_ACCEPTED')
    return {'status': status, 'real_rf_qualified': False, 'state': physical[:11],
            'receiver_clocks': physical[11:clock_end].reshape(n, 2),
            'station_corrections_m': physical[clock_end:].reshape(n, 3),
            'stations_fitted_m': stations+physical[clock_end:].reshape(n, 3),
            'covariance_joint': geometry['covariance'], 'data_gain': geometry['gain'],
            'data_jacobian': jacobian, 'parameter_scale': scale,
            'fit_covariance_sha256': covariance_hash(covariance),
            'residual_dof': dof, 'rank': geometry['rank'], 'scaled_condition': geometry['scaled_condition'],
            'weighted_residual_cost': cost, 'conditional_residual_p': p_value,
            'whitened_residual': result.fun, 'residual_threshold_p': .01,
            'found_branches': len(fits), 'branch_failures': failures,
            'scope': 'Known fixed joint Gaussian covariance, local nonlinear chi-square approximation; finite branch search. No fitted error rescaling, global coverage or RF qualification.'}


def forecast_joint(result, seconds, station, clock, covariance, *, calibration_status):
    """Prediction-error covariance includes cross blocks with held-out nuisances.

    Covariance order: exact fit-data block, then held-out clock(2), station(3),
    measurement noise(2). No held-out target value or residual-based correction.
    Fit parameters are held fixed: holdout calibration never enters the fit.
    """
    if result['status'] != 'CONDITIONAL_JOINT_MODEL_ACCEPTED' or calibration_status not in ACCEPTED_CALIBRATIONS:
        raise ValueError('accepted joint fit and held-out calibration required')
    size = result['data_gain'].shape[1]
    cov = validate_covariance(covariance, size+7)
    if covariance_hash(cov[:size, :size]) != result['fit_covariance_sha256']:
        raise ValueError('forecast covariance changes the frozen fit-data block')
    state, scale = np.asarray(result['state']), np.asarray(result['parameter_scale'])[:11]
    output_j = central_jacobian(lambda z: output_values(z*scale, seconds, station, clock), state/scale)/scale
    mapping = np.zeros((8, size+7))
    mapping[:, :size] = output_j@result['data_gain'][:11]
    clock, station = np.asarray(clock, float), np.asarray(station, float)
    clock_scale = np.array([1000., 1.])
    mapping[:, size:size+2] = central_jacobian(lambda c: output_values(
        state, seconds, station, c*clock_scale), clock/clock_scale)/clock_scale
    mapping[:, size+2:size+5] = central_jacobian(lambda s: output_values(state, seconds, s, clock), station, step=1.)
    mapping[6:, size+5:] = -np.eye(2)
    covariance_out = mapping@cov@mapping.T
    covariance_out = (covariance_out+covariance_out.T)/2
    return {'status': 'CONDITIONAL_JOINT_FORECAST', 'real_rf_qualified': False,
            'seconds': seconds, 'prediction': output_values(state, seconds, station, clock),
            'covariance_output': covariance_out, 'mapping': mapping,
            'local_position_radius95_m': float(np.sqrt(chi2.ppf(.95, 3)*max(0., np.linalg.eigvalsh(covariance_out[:3, :3])[-1]))),
            'scope': 'Unconditional local Gaussian prediction-error covariance before held-out target reveal. No conditional holdout correction or total nonlinear/systematic bound.'}
