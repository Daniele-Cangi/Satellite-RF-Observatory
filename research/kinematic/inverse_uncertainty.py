"""Local S2 uncertainty transport for the fixed S2a estimator, not RF qualification.

Input perturbations mean errors in supplied observations/calibration/coordinates;
the final two entries mean errors in the subsequently observed held-out pair.
Output is [position(3), velocity(3), predicted-minus-observed code, rate].
No held-out measurement values enter this module. Correlated input errors use
a sandwich covariance; the old fit's residual p is not recalibrated by it.
"""
import numpy as np
from scipy.linalg import block_diag, solve_triangular
from scipy.stats import chi2, norm

from .receiver_time import central_jacobian, cholesky_covariance, predict


def vector(prediction):
    return np.r_[prediction['code_m'].ravel(), prediction['rate_m_s'].ravel()]


def layout(epoch_count, station_count):
    """Time-major/station-minor code, then rate; remaining blocks receiver-major."""
    lengths = [('observations', 2*epoch_count*station_count),
               ('clock_means', 2*station_count), ('stations', 3*station_count),
               ('heldout_clock', 2), ('heldout_station', 3), ('heldout_noise', 2)]
    result, start = {}, 0
    for name, length in lengths:
        result[name] = slice(start, start+length)
        start += length
    return result, start


def output_values(state, seconds, station, clock):
    """Position/velocity at GPST offset; held-out pair at receiver-tag offset."""
    return np.r_[state[:3]+seconds*state[3:6]+.5*seconds**2*state[6:9],
                 state[3:6]+seconds*state[6:9],
                 vector(predict(state, [seconds], [station], [clock]))]


def linearize(result, tags, stations, observation_covariance, clock_covariance,
              seconds, heldout_station, heldout_clock, *, calibration_statuses):
    """Gauss-Newton response about an accepted fit, weights held fixed.

    Clock calibration statuses must be supplied for every fit station AND the
    excluded station, from independent calibration. This does not certify their
    physical provenance. General covariance transport does not turn the S2a
    independent-data optimizer into a joint-correlated maximum-likelihood fit.
    """
    stations, tags = np.asarray(stations, float), np.asarray(tags, float)
    accepted = {'CONDITIONAL_CLOCK_MODEL_ACCEPTED', 'REFERENCE_MODEL_ACCEPTED'}
    if (stations.ndim != 2 or stations.shape[1] != 3 or len(stations) < 5
            or tags.ndim != 1 or len(tags) < 3 or tags[-1] != 0
            or np.any(np.diff(tags) <= 0)):
        raise ValueError('invalid fit geometry or tags')
    if (result['status'] != 'CONDITIONAL_MODEL_ACCEPTED'
            or len(calibration_statuses) != len(stations)+1
            or any(status not in accepted for status in calibration_statuses)):
        raise ValueError('accepted fit and all fit/held-out calibrations required')
    state = np.asarray(result['state'], float)
    clocks = np.asarray(result['receiver_clocks'], float)
    if state.shape != (11,) or clocks.shape != (len(stations), 2):
        raise ValueError('invalid fitted parameter shape')
    parameter = np.r_[state, clocks.ravel()]
    scale = np.r_[[1e7]*3, [1e3]*3, [1.]*3, 1e5, 10., np.tile([1000., 1.], len(stations))]
    blocks, size = layout(len(tags), len(stations))
    nobs = blocks['observations'].stop
    chol = block_diag(cholesky_covariance(observation_covariance, nobs),
                      cholesky_covariance(clock_covariance, clocks.size))

    def model(z):
        p = z*scale
        return np.r_[vector(predict(p[:11], tags, stations, p[11:].reshape(-1, 2))), p[11:]]

    j = solve_triangular(chol, central_jacobian(model, parameter/scale), lower=True)
    u, singular, vh = np.linalg.svd(j, full_matrices=False)
    if singular[-1] <= singular[0]*1e-10:
        raise ValueError('rank deficient local response')
    # Avoid normal-equation squaring of the already substantial condition number.
    gain = scale[:, None]*((vh.T/singular)@u.T)@solve_triangular(chol, np.eye(len(chol)), lower=True)
    response = np.zeros((len(parameter), size))
    response[:, :len(chol)] = gain
    station_j = central_jacobian(lambda s: vector(predict(
        state, tags, s.reshape(-1, 3), clocks)), stations.ravel(), step=1.)
    response[:, blocks['stations']] = -gain[:, :nobs]@station_j

    output_j = central_jacobian(lambda z: output_values(
        (z*scale)[:11], seconds, heldout_station, heldout_clock), parameter/scale)/scale
    mapping = output_j@response
    heldout_station = np.asarray(heldout_station, float)
    heldout_clock = np.asarray(heldout_clock, float)
    mapping[:, blocks['heldout_station']] = central_jacobian(lambda s: output_values(
        state, seconds, s, heldout_clock), heldout_station, step=1.)
    clock_scale = np.array([1000., 1.])
    mapping[:, blocks['heldout_clock']] = central_jacobian(lambda c: output_values(
        state, seconds, heldout_station, c*clock_scale), heldout_clock/clock_scale)/clock_scale
    mapping[6:, blocks['heldout_noise']] = -np.eye(2)
    return {'mapping': mapping, 'parameter_response': response, 'blocks': blocks,
            'input_size': size, 'nominal_output': output_values(state, seconds, heldout_station, heldout_clock),
            'scaled_condition': float(singular[0]/singular[-1]),
            'status': 'LOCAL_RESPONSE_AVAILABLE', 'real_rf_qualified': False}


def validate_covariance(covariance, size):
    """Accept PSD (including exactly known inputs); validate in correlation units."""
    cov = np.asarray(covariance, float)
    if cov.shape != (size, size) or not np.isfinite(cov).all():
        raise ValueError('finite covariance of required size needed')
    diagonal = np.diag(cov)
    if np.any(diagonal < 0):
        raise ValueError('negative variance')
    zero = diagonal == 0
    if np.any(cov[zero] != 0) or np.any(cov[:, zero] != 0):
        raise ValueError('zero variance cannot have covariance')
    scale = np.sqrt(np.where(zero, 1., diagonal))
    correlation = cov/np.outer(scale, scale)
    if not np.allclose(correlation, correlation.T, rtol=0, atol=1e-12):
        raise ValueError('asymmetric covariance')
    if np.linalg.eigvalsh(correlation).min() < -1e-10:
        raise ValueError('covariance not positive semidefinite')
    return (cov+cov.T)/2


def budget(response, covariance, *, systematic_inputs=None, direct_output_errors=None):
    """Transport Gaussian covariance and separately a declared local affine box.

    Each systematic column is an input perturbation with coefficient in [-1,1].
    Direct columns share those SAME coefficients (e.g. negative future truth
    change for unmodelled jerk). Absolute component bounds are exact only for
    this affine box. Vector bounds use the triangle inequality, not corner
    sampling. No certification of nonlinear remainder or population coverage.
    """
    mapping, size = response['mapping'], response['input_size']
    cov = validate_covariance(covariance, size)
    transported = mapping@cov@mapping.T
    transported = (transported+transported.T)/2
    if systematic_inputs is None:
        systematic_inputs = np.zeros((size, 0))
    inputs = np.asarray(systematic_inputs, float)
    if inputs.ndim != 2 or inputs.shape[0] != size or not np.isfinite(inputs).all():
        raise ValueError('finite systematic input columns required')
    direct = np.zeros((8, inputs.shape[1])) if direct_output_errors is None else np.asarray(direct_output_errors, float)
    if direct.shape != (8, inputs.shape[1]) or not np.isfinite(direct).all():
        raise ValueError('direct output modes must match systematic columns')
    modes = mapping@inputs+direct
    radii = [float(np.sqrt(chi2.ppf(.95, 3)*max(0., np.linalg.eigvalsh(transported[s, s])[-1])))
             for s in (slice(0, 3), slice(3, 6))]
    return {'status': 'CONDITIONAL_LOCAL_BUDGET', 'real_rf_qualified': False,
            'covariance_output': transported, 'systematic_output_modes': modes,
            'local_gaussian_position_radius95_m': radii[0],
            'local_gaussian_velocity_radius95_m_s': radii[1],
            'heldout_marginal_gaussian_halfwidth95': norm.ppf(.975)*np.sqrt(np.maximum(0., np.diag(transported)[6:])),
            'affine_box_component_bound': np.sum(abs(modes), axis=1),
            'affine_box_position_norm_bound_m': float(np.linalg.norm(modes[:3], axis=0).sum()),
            'affine_box_velocity_norm_bound_m_s': float(np.linalg.norm(modes[3:6], axis=0).sum()),
            'scope': 'Local Gaussian transport and separate affine systematic box only. Fixed S2a weights; its residual p is not recalibrated for extra errors. No total nonlinear 95% bound or RF qualification.'}
