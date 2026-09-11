"""Ideal common-time kinematics; NOT a receiver-time RF/Doppler adapter.

Fixed receivers, Euclidean range, shared affine clock. No atmosphere, light-time,
Earth rotation, receiver calibration or temporal noise correlations. All local
covariances are conditional on supplied independent measurement noise.
"""
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import chi2

from positioning.solver import solve


def design(state, times, stations, *, quadratic=True):
    """Code/range-rate predictions and analytic derivatives (m, s, m/s)."""
    t = np.asarray(times, dtype=float)[:, None, None]
    state, stations = np.asarray(state), np.asarray(stations)
    acceleration = state[6:9] if quadratic else np.zeros(3)
    clock = 9 if quadratic else 6
    position = state[:3] + t*state[3:6] + .5*t*t*acceleration
    velocity = state[3:6] + t*acceleration
    delta = position-stations[None, :, :]
    distance = np.linalg.norm(delta, axis=2, keepdims=True)
    if np.any(distance <= 1):
        raise ValueError('trial trajectory intersects a receiver')
    unit = delta/distance
    radial_rate = np.sum(unit*velocity, axis=2, keepdims=True)
    gradient = (velocity-unit*radial_rate)/distance
    code_parts = [unit, t*unit]
    rate_parts = [gradient, unit+t*gradient]
    if quadratic:
        code_parts.append(.5*t*t*unit)
        rate_parts.append(t*unit+.5*t*t*gradient)
    ones = np.ones_like(distance)
    code_jac = np.concatenate(code_parts+[ones, t*ones], axis=2)
    rate_jac = np.concatenate(rate_parts+[0*ones, ones], axis=2)
    code = distance[:, :, 0]+state[clock]+t[:, :, 0]*state[clock+1]
    rate = radial_rate[:, :, 0]+state[clock+1]
    return code, rate, code_jac, rate_jac


def fit(times, stations, codes, *, rates=None, code_sigma_m=20., rate_sigma_m_s=.05, quadratic=True):
    """Fit only the supplied observations; accepts no truth or orbital seed."""
    times, stations, codes = map(lambda a: np.asarray(a, dtype=float), (times, stations, codes))
    if (times.ndim != 1 or len(times)<3 or np.any(np.diff(times)<=0) or times[-1]!=0
            or stations.ndim != 2 or stations.shape[1]!=3 or len(stations)<5
            or codes.shape!=(len(times), len(stations))):
        raise ValueError('require ordered common times ending at zero and >=5 fixed receivers')
    if not all(np.isfinite(a).all() for a in (times, stations, codes)):
        raise ValueError('nonfinite measurement input')
    if not np.isfinite([code_sigma_m, rate_sigma_m_s]).all() or min(code_sigma_m,rate_sigma_m_s)<=0:
        raise ValueError('positive finite noise scales required')
    if rates is not None:
        rates = np.asarray(rates, dtype=float)
        if rates.shape != codes.shape or not np.isfinite(rates).all():
            raise ValueError('rate observations must match the codes')
    n = 11 if quadratic else 8
    scale = np.array([1e7]*3+[1e3]*3+([1.]*3 if quadratic else [])+[1e5,10.])
    # First obtain all found snapshot branches from the final fit epoch's codes.
    # The synthetic truth is never passed to this initializer.
    snapshot = solve(codes[-1],stations,np.eye(len(stations))*code_sigma_m**2,atmosphere=False)
    if rates is None:
        slopes = np.polyfit(times,codes,2)[1]
    else:
        slopes = rates[-1]

    def residual(state):
        code, rate, _, _ = design(state,times,stations,quadratic=quadratic)
        pieces = [(code-codes).ravel()/code_sigma_m]
        if rates is not None:
            pieces.append((rate-rates).ravel()/rate_sigma_m_s)
        return np.concatenate(pieces)

    def jacobian(state):
        _, _, code_jac, rate_jac = design(state,times,stations,quadratic=quadratic)
        pieces = [code_jac.reshape(-1,n)/code_sigma_m]
        if rates is not None:
            pieces.append(rate_jac.reshape(-1,n)/rate_sigma_m_s)
        return np.concatenate(pieces)

    fits = []
    for branch in snapshot['branches']:
        q = np.asarray(branch['q'])
        delta = q[:3]-stations
        unit = delta/np.linalg.norm(delta,axis=1)[:,None]
        velocity_clock = np.linalg.lstsq(np.column_stack([unit,np.ones(len(unit))]),slopes,rcond=None)[0]
        initial = np.r_[q[:3],velocity_clock[:3],np.zeros(3) if quadratic else [],q[3],velocity_clock[3]]
        result = least_squares(residual,initial,jac=jacobian,x_scale=scale,max_nfev=300,
                               ftol=1e-11,xtol=1e-11,gtol=1e-11)
        if result.success and np.isfinite(result.x).all():
            if all(np.linalg.norm((result.x-other.x)/scale)>1e-8 for other in fits):
                fits.append(result)
    if not fits:
        raise ValueError('no converged kinematic branch')
    fits.sort(key=lambda result:result.fun@result.fun)
    result = fits[0]
    cost = float(result.fun@result.fun)
    # Condition/rank is assessed in declared scaled parameter units.
    _, singular, vh = np.linalg.svd(jacobian(result.x)*scale,full_matrices=False)
    if len(singular)!=n or singular[-1]<=singular[0]*1e-10:
        raise ValueError('kinematic model is rank deficient in scaled coordinates')
    covariance = ((vh.T/singular**2)@vh)*scale[:,None]*scale[None,:]
    dof = len(result.fun)-n
    if dof <= 0:
        raise ValueError('positive residual degrees of freedom required')
    p_value = float(chi2.sf(cost,dof))
    ambiguous = any(float(other.fun@other.fun)-cost<=chi2.ppf(.95,n) for other in fits[1:])
    return {'state':result.x,'covariance':covariance,'quadratic':quadratic,
            'status':'AMBIGUOUS' if ambiguous else 'MODEL_REJECTED' if p_value<.01 else 'NOMINAL_MODEL_ACCEPTED',
            'weighted_residual_cost':cost,'residual_dof':dof,'nominal_residual_p':p_value,
            'scaled_condition':float(singular[0]/singular[-1]),'rank':n,
            'found_branches':len(fits),'code_sigma_m':code_sigma_m,'rate_sigma_m_s':rate_sigma_m_s,
            'scope':'Synthetic ideal common-time model; local IID-noise covariance, no systematic/truncation envelope or global branch guarantee.'}


def forecast(result, seconds, station):
    """Predict at a requested time without inspecting confirmation data."""
    state, covariance = result['state'],result['covariance']
    t = float(seconds)
    n = len(state)
    pos_map, vel_map = np.zeros((3,n)),np.zeros((3,n))
    pos_map[:,:3] = np.eye(3);pos_map[:,3:6] = t*np.eye(3)
    vel_map[:,3:6] = np.eye(3)
    if result['quadratic']:
        pos_map[:,6:9] = .5*t*t*np.eye(3);vel_map[:,6:9] = t*np.eye(3)
    pos_cov = pos_map@covariance@pos_map.T
    vel_cov = vel_map@covariance@vel_map.T
    code,rate,code_jac,rate_jac = design(state,[t],np.array([station]),quadratic=result['quadratic'])
    def radius(matrix):
        return float(np.sqrt(chi2.ppf(.95,3)*np.linalg.eigvalsh(matrix)[-1]))
    def band(jac,noise):
        h=jac[0,0]
        return float(3*np.sqrt(h@covariance@h+noise**2))
    return {'seconds':t,'position_m':pos_map@state,'velocity_m_s':vel_map@state,
            'local_position_radius95_m':radius(pos_cov),'local_velocity_radius95_m_s':radius(vel_cov),
            'heldout_code_m':float(code[0,0]),'heldout_rate_m_s':float(rate[0,0]),
            'heldout_code_band3sigma_m':band(code_jac,result['code_sigma_m']),
            'heldout_rate_band3sigma_m_s':band(rate_jac,result['rate_sigma_m_s'])}
