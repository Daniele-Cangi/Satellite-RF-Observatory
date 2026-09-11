"""S2a vacuum, receiver-tagged kinematics. Not qualified for real RF estimation.

State: ECEF p0, v0, a0, satellite clock error b0, b1 (11 parameters).
Receiver clock error is affine in receiver-tag seconds, not in GPST seconds.
All times are small offsets from one declared integer GPST base epoch.
"""
import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import least_squares
from scipy.stats import chi2

from positioning.solver import solve

C = 299792458.0
OMEGA = 7.2921151467e-5


def rotate_z(vectors, angle):
    """Active rotation, positive counterclockwise around z; broadcasting allowed."""
    x, y, z = np.moveaxis(np.asarray(vectors), -1, 0)
    co, si = np.cos(angle), np.sin(angle)
    return np.stack([co*x-si*y, si*x+co*y, z], axis=-1)


def predict(state, tags_s, stations_m, receiver_clocks, *, omega=OMEGA):
    """Vacuum code and instantaneous d(code)/d(receiver tag), in m and m/s.

    receiver_clocks[j] = [offset_m, drift_m_per_tag_s]. Positive clock error
    means a clock ahead of GPST. No observed code determines the light time.
    omega=0 is an explicit synthetic ablation, never a data-driven correction.
    """
    state, tags, stations, clocks = [np.asarray(x, dtype=float) for x in
                                    (state, tags_s, stations_m, receiver_clocks)]
    if (state.shape != (11,) or tags.ndim != 1 or not len(tags)
            or stations.ndim != 2 or stations.shape[1] != 3 or not len(stations)
            or clocks.shape != (len(stations), 2)):
        raise ValueError('invalid state, tag, station or clock shape')
    if not all(np.isfinite(x).all() for x in (state, tags, stations, clocks)) or not np.isfinite(omega):
        raise ValueError('nonfinite observation-model input')
    if np.max(np.abs(tags)) > 86400 or np.any(np.abs(clocks[:, 1]) >= .01*C):
        raise ValueError('require local time offsets and monotone, slow receiver clocks')
    clock_r = clocks[None, :, 0] + tags[:, None]*clocks[None, :, 1]
    receive = tags[:, None] - clock_r/C
    tag_scale = 1-clocks[None, :, 1]/C

    def geometry(tau):
        transmit = receive-tau
        p = state[:3] + transmit[..., None]*state[3:6] + .5*transmit[..., None]**2*state[6:9]
        v = state[3:6] + transmit[..., None]*state[6:9]
        rotated = rotate_z(p, -omega*tau)
        delta = rotated-stations
        rho = np.linalg.norm(delta, axis=-1)
        if np.any(rho <= 1) or np.any(np.linalg.norm(v, axis=-1) >= .01*C):
            raise ValueError('invalid distance or non-slow trial trajectory')
        return transmit, rotated, rotate_z(v, -omega*tau), delta/rho[..., None], rho

    tau = np.zeros_like(receive)
    for _ in range(15):
        *_, rho = geometry(tau)
        updated = rho/C
        if np.max(np.abs(updated-tau)) < 2e-15:
            tau = updated
            break
        tau = updated
    else:
        raise ValueError('light-time iteration did not converge')
    transmit, rotated, velocity, unit, rho = geometry(tau)
    spin = omega*np.stack([-rotated[..., 1], rotated[..., 0], np.zeros_like(rho)], axis=-1)
    # Implicit derivative of c*(tr-ts)=|R(-omega*(tr-ts))*p(ts)-station|.
    satellite_radial = np.sum(unit*(velocity+spin), axis=-1)
    range_rate_gpst = np.sum(unit*velocity, axis=-1)/(1+satellite_radial/C)
    transmit_rate = (1-range_rate_gpst/C)*tag_scale
    code = rho+clock_r-state[9]-state[10]*transmit
    rate = range_rate_gpst*tag_scale+clocks[None, :, 1]-state[10]*transmit_rate
    return {'code_m': code, 'rate_m_s': rate, 'receive_s': receive,
            'transmit_s': transmit, 'light_time_s': tau}


def cholesky_covariance(covariance, size):
    covariance = np.asarray(covariance, dtype=float)
    if (covariance.shape != (size, size) or not np.isfinite(covariance).all()
            or not np.allclose(covariance, covariance.T, rtol=1e-12, atol=1e-12)):
        raise ValueError('finite symmetric covariance of the required size needed')
    try:
        return np.linalg.cholesky(covariance)
    except np.linalg.LinAlgError as error:
        raise ValueError('covariance must be positive definite') from error


def noise_covariance(tags_s, station_count, *, code_sigma_m=20., rate_sigma_m_s=.05,
                     temporal_s=60., code_rate_correlation=.2, shared_fraction=.15):
    """Declared synthetic covariance; ordering: all codes, then all rates.

    Each block is time-major/station-minor. Kronecker factors preserve temporal,
    receiver-shared and code/rate correlations. These are design assumptions.
    """
    t = np.asarray(tags_s, dtype=float)
    values = [code_sigma_m, rate_sigma_m_s, temporal_s, code_rate_correlation, shared_fraction]
    if (t.ndim != 1 or not len(t) or not np.isfinite(t).all() or np.any(np.diff(t) <= 0)
            or not isinstance(station_count, int) or station_count < 1
            or not np.isfinite(values).all() or min(values[:3]) <= 0
            or abs(code_rate_correlation) >= 1 or not 0 <= shared_fraction < 1):
        raise ValueError('invalid correlated-noise design')
    temporal = np.exp(-np.abs(t[:, None]-t[None, :])/temporal_s)
    receivers = (1-shared_fraction)*np.eye(station_count)+shared_fraction
    cross = code_rate_correlation*code_sigma_m*rate_sigma_m_s
    observable = [[code_sigma_m**2, cross], [cross, rate_sigma_m_s**2]]
    return np.kron(observable, np.kron(temporal, receivers))


def central_jacobian(function, point, step=1e-5):
    """Central differences in declared scaled coordinates, including at zero."""
    eye = np.eye(len(point))*step
    return np.column_stack([(function(point+d)-function(point-d))/(2*step) for d in eye])


def fit(tags_s, stations_m, codes_m, rates_m_s, covariance, clock_mean, clock_covariance):
    """Joint GLS with independent reference-derived Gaussian receiver-clock data.

    Fit target trajectory and clocks jointly, retaining their cross-covariances.
    Calibration data must be independent of target measurement errors under the
    supplied covariance model. No target state or caller-provided seed accepted.
    """
    t, stations, codes, rates, clocks = [np.asarray(x, dtype=float) for x in
                                       (tags_s, stations_m, codes_m, rates_m_s, clock_mean)]
    if (t.ndim != 1 or len(t) < 3 or np.any(np.diff(t) <= 0) or t[-1] != 0
            or stations.ndim != 2 or stations.shape[1] != 3 or len(stations) < 5
            or codes.shape != (len(t), len(stations)) or rates.shape != codes.shape
            or clocks.shape != (len(stations), 2)
            or not all(np.isfinite(x).all() for x in (t, stations, codes, rates, clocks))):
        raise ValueError('require finite common tags ending at zero, >=5 receivers and complete code/rate arrays')
    observed = np.r_[codes.ravel(), rates.ravel()]
    obs_chol = cholesky_covariance(covariance, len(observed))
    clock_chol = cholesky_covariance(clock_covariance, clocks.size)
    scale = np.r_[[1e7]*3, [1e3]*3, [1.]*3, 1e5, 10., np.tile([1000., 1.], len(stations))]
    clock_r = clocks[None, :, 0]+t[:, None]*clocks[None, :, 1]
    snapshot = solve(codes[-1]-clock_r[-1], stations, np.asarray(covariance)[
        codes.size-len(stations):codes.size, codes.size-len(stations):codes.size], atmosphere=False)

    def residual(z):
        physical = z*scale
        prediction = predict(physical[:11], t, stations, physical[11:].reshape(-1, 2))
        predicted = np.r_[prediction['code_m'].ravel(), prediction['rate_m_s'].ravel()]
        return np.r_[solve_triangular(obs_chol, predicted-observed, lower=True),
                     solve_triangular(clock_chol, physical[11:]-clocks.ravel(), lower=True)]

    fits, failures = [], []
    for branch in snapshot['branches']:
        q = np.asarray(branch['q'])
        unit = q[:3]-stations
        unit /= np.linalg.norm(unit, axis=1)[:, None]
        vc = np.linalg.lstsq(np.column_stack([unit, np.ones(len(unit))]),
                             rates[-1]-clocks[:, 1], rcond=None)[0]
        initial = np.r_[q[:3], vc[:3], np.zeros(3), -q[3], -vc[3], clocks.ravel()]
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
        raise ValueError('no converged receiver-time branch: '+str(failures))
    fits.sort(key=lambda row: row.fun@row.fun)
    result = fits[0]
    _, singular, vh = np.linalg.svd(result.jac, full_matrices=False)
    if singular[-1] <= singular[0]*1e-10:
        raise ValueError('receiver-time model rank deficient in scaled coordinates')
    covariance_joint = ((vh.T/singular**2)@vh)*scale[:, None]*scale[None, :]
    cost = float(result.fun@result.fun)
    dof = len(result.fun)-len(result.x)
    p = float(chi2.sf(cost, dof))
    ambiguous = any(float(other.fun@other.fun)-cost <= chi2.ppf(.95, len(scale)) for other in fits[1:])
    status = ('AMBIGUOUS' if ambiguous else 'BRANCH_SEARCH_INCOMPLETE' if failures else
              'MODEL_REJECTED' if p < .01 else 'CONDITIONAL_MODEL_ACCEPTED')
    return {'state': (result.x*scale)[:11], 'receiver_clocks': (result.x*scale)[11:].reshape(-1, 2),
            'covariance_joint': covariance_joint, 'status': status, 'nominal_residual_p': p,
            'weighted_residual_cost': cost, 'residual_dof': dof, 'rank': len(singular),
            'scaled_condition': float(singular[0]/singular[-1]), 'found_branches': len(fits),
            'branch_failures': failures,
            'scope': 'Vacuum synthetic model; local covariance conditional on declared correlated noise and independent clock calibration. No global or systematic-error bound.'}


def quadratic_remainder(jerk_bound_m_s3, seconds, *, position_budget_m, velocity_budget_m_s):
    """Taylor remainder bound about t0, NOT a fitted-state uncertainty envelope.

    Requires a bound on the ECEF third derivative throughout the interval, fixed
    independently of target confirmation. Include transmit times in the interval.
    """
    values = np.asarray([jerk_bound_m_s3, seconds, position_budget_m, velocity_budget_m_s], dtype=float)
    if not np.isfinite(values).all() or jerk_bound_m_s3 < 0 or min(values[2:]) <= 0:
        raise ValueError('finite nonnegative jerk and positive budgets required')
    dt = abs(float(seconds))
    position = jerk_bound_m_s3*dt**3/6
    velocity = jerk_bound_m_s3*dt**2/2
    return {'position_remainder_m': position, 'velocity_remainder_m_s': velocity,
            'status': 'TRUNCATION_BUDGET_EXCEEDED' if position > position_budget_m or velocity > velocity_budget_m_s
            else 'WITHIN_DECLARED_TAYLOR_BUDGET'}
