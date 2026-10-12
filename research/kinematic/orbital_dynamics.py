"""Declared central/J2 gravity in a uniformly rotating terrestrial frame.

Development models, not a qualified GNSS force model. No satellite state,
radius, energy or orbit product is supplied as a constraint.
"""
import numpy as np
from scipy.integrate import solve_ivp

from positioning.calibration import MU
from .receiver_time import C, OMEGA, rotate_z

# Nominal GRS80 dynamical form factor and equatorial radius (NRL Constants.m).
# MU is the existing GPS/GRS80 value; spin matches the existing RF convention.
J2 = 1.08263e-3
R_EARTH = 6378137.


def acceleration(state, *, j2=J2):
    """ECEF m/s^2, including Coriolis and centrifugal terms, constant spin."""
    r, v = np.asarray(state)[:3], np.asarray(state)[3:]
    radius = np.linalg.norm(r)
    if radius <= R_EARTH or not np.isfinite(state).all() or not np.isfinite(j2):
        raise ValueError('finite exterior-Earth state and gravity coefficient required')
    gravity = -MU*r/radius**3
    z2 = (r[2]/radius)**2
    zonal = 1.5*j2*MU*R_EARTH**2/radius**5*r*np.array([5*z2-1,5*z2-1,5*z2-3])
    spin = np.array([0.,0.,OMEGA])
    return gravity+zonal-2*np.cross(spin,v)-np.cross(spin,np.cross(spin,r))


def force_jacobian(state, *, j2=J2):
    """Derivative of [velocity, acceleration] in the same declared frame."""
    r = np.asarray(state)[:3]
    radius = np.linalg.norm(r)
    acceleration(state,j2=j2)  # Same finite/exterior-Earth domain.
    square = radius**2
    gradient = -MU/radius**3*np.eye(3)+3*MU/radius**5*np.outer(r,r)
    shape = 5*r[2]**2/square-np.array([1.,1.,3.])
    ds = 10*r[2]/square*np.array([0.,0.,1.])-10*r[2]**2/square**2*r
    gradient += 1.5*j2*MU*R_EARTH**2/radius**5*(
        np.diag(shape)-5*np.outer(r*shape,r)/square+np.outer(r,ds))
    gradient += np.diag([OMEGA**2,OMEGA**2,0.])
    jac = np.zeros((6,6))
    jac[:3,3:] = np.eye(3)
    jac[3:,:3] = gradient
    jac[3:,3:] = np.array([[0.,2*OMEGA,0.],[-2*OMEGA,0.,0.],[0.,0.,0.]])
    return jac


class Trajectory:
    """Dense forward/backward integration, epoch zero; forbid extrapolation."""
    def __init__(self, state, bounds, *, j2=J2, rtol=2e-12, sensitivities=False):
        state = np.asarray(state,float)
        lower,upper = map(float,bounds)
        if (state.shape!=(6,) or not np.isfinite(state).all() or
                not np.isfinite([lower,upper,rtol,j2]).all() or
                not lower<0<upper or rtol<=0):
            raise ValueError('six-state trajectory needs finite bounds spanning epoch zero')
        acceleration(state,j2=j2)
        self.lower,self.upper,self.sensitivities = lower,upper,sensitivities
        def rhs(t,y):
            motion = np.r_[y[3:6],acceleration(y[:6],j2=j2)]
            return np.r_[motion,(force_jacobian(y[:6],j2=j2)@y[6:].reshape(6,6)).ravel()] if sensitivities else motion
        initial = np.r_[state,np.eye(6).ravel()] if sensitivities else state
        atol = np.r_[np.full(3,1e-6),np.full(3,1e-9)]
        if sensitivities:
            atol = np.r_[atol,np.full(36,1e-13)]
        options = dict(method='DOP853',rtol=rtol,atol=atol,
                       dense_output=True,max_step=120.)
        self.backward = solve_ivp(rhs,[0,lower],initial,**options)
        self.forward = solve_ivp(rhs,[0,upper],initial,**options)
        if not self.backward.success or not self.forward.success:
            raise ValueError('orbital integration failed')

    def _dense(self, seconds):
        t = np.asarray(seconds,float)
        if not np.isfinite(t).all() or np.any(t<self.lower) or np.any(t>self.upper):
            raise ValueError('trajectory evaluation outside integrated bounds')
        flat = t.ravel()
        width = 42 if self.sensitivities else 6
        result = np.empty((len(flat),width))
        before = flat<0
        if before.any():
            result[before] = self.backward.sol(flat[before]).T
        if (~before).any():
            result[~before] = self.forward.sol(flat[~before]).T
        return result.reshape(t.shape+(width,))

    def __call__(self, seconds):
        return self._dense(seconds)[...,:6]

    def state_jacobian(self, seconds):
        if not self.sensitivities:
            raise ValueError('trajectory sensitivities not integrated')
        value = self._dense(seconds)
        return value[...,6:].reshape(value.shape[:-1]+(6,6))


def predict_observations(trajectory, endpoint_s, tags_s, stations, clocks, satellite_clock):
    """Vacuum code at receiver tags; clock [b0,b1] local to this arc endpoint.

    All times are GPST offsets from the trajectory epoch. Receiver-clock offsets
    and slopes are in metres / m per tag-second; satellite slopes use transmit
    GPST seconds. No observed code enters the light-time iteration.
    """
    tags,stations,clocks,clock = map(lambda x:np.asarray(x,float),
                                   (tags_s,stations,clocks,satellite_clock))
    if (tags.ndim!=1 or not len(tags) or stations.ndim!=2 or stations.shape[1]!=3
            or clocks.shape!=(len(stations),2) or clock.shape!=(2,)
            or not all(np.isfinite(x).all() for x in (tags,stations,clocks,clock))
            or not np.isfinite(endpoint_s) or np.any(abs(clocks[:,1])>=.01*C)):
        raise ValueError('finite dynamic observation geometry and monotone receiver clocks required')
    clock_r = clocks[None,:,0]+tags[:,None]*clocks[None,:,1]
    receive = endpoint_s+tags[:,None]-clock_r/C
    tau = np.zeros_like(receive)
    for _ in range(15):
        transmit = receive-tau
        states = trajectory(transmit)
        ray = rotate_z(states[...,:3],-OMEGA*tau)-stations
        rho = np.linalg.norm(ray,axis=-1)
        if np.any(rho<=1) or np.any(np.linalg.norm(states[...,3:],axis=-1)>=.01*C):
            raise ValueError('invalid distance or non-slow dynamic trajectory')
        updated = rho/C
        if np.max(abs(updated-tau))<2e-15:
            tau = updated
            break
        tau = updated
    else:
        raise ValueError('dynamic light time did not converge')
    transmit = receive-tau
    states = trajectory(transmit)
    rotated = rotate_z(states[...,:3],-OMEGA*tau)
    ray = rotated-stations
    rho = np.linalg.norm(ray,axis=-1)
    unit = ray/rho[...,None]
    velocity = rotate_z(states[...,3:],-OMEGA*tau)
    spin = OMEGA*np.stack([-rotated[...,1],rotated[...,0],np.zeros_like(rho)],axis=-1)
    denominator = 1+np.sum(unit*(velocity+spin),axis=-1)/C
    radial = np.sum(unit*velocity,axis=-1)/denominator
    result = {'code_m':rho+clock_r-clock[0]-clock[1]*(transmit-endpoint_s),
        'receive_s':receive,'transmit_s':transmit,'light_time_s':tau,
        'receiver_clock_derivative':1-(radial-clock[1]*(1-radial/C))/C,
        'station_derivative':-(1+clock[1]/C)*unit/denominator[...,None]}
    if getattr(trajectory,'sensitivities',False):
        # Partial state sensitivity at fixed emission time, then implicit light
        # time/clock differentiation. Never differentiate small phase values by
        # subtracting two already-differenced ~25 Mm paths.
        stm = trajectory.state_jacobian(transmit)[...,:3,:]
        rotated_stm = np.moveaxis(rotate_z(np.moveaxis(stm,-1,-2),-OMEGA*tau[...,None]),-2,-1)
        result['initial_state_derivative'] = (1+clock[1]/C)*np.einsum('...i,...ij->...j',unit,rotated_stm)/denominator[...,None]
    return result


def predict_codes(trajectory, endpoint_s, tags_s, stations, clocks, satellite_clock):
    """Code-only view of the shared dynamic light-time model, in metres."""
    return predict_observations(trajectory,endpoint_s,tags_s,stations,clocks,satellite_clock)['code_m']
