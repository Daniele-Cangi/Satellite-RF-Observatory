"""Clock-basis extension of the existing geometric light-time observation.

Receiver coefficients use a caller-declared basis at receiver tags. Satellite
curvature uses transmit GPST, with a linear endpoint tangent after the arc.
Neither clock changes the vacuum light-time equation or supplies target state.
"""
import numpy as np

from . import orbital_dynamics as dynamics


def satellite_basis(transmit_offset, count):
    x = np.asarray(transmit_offset, float)
    if count not in (2, 3):
        raise ValueError('linear or curved satellite clock required')
    columns = [np.ones_like(x), x]
    if count == 3:
        columns.append(np.minimum(x, 0.)**2)
    return np.stack(columns, axis=-1)


def predict(curve, endpoint, tags, xyz, receivers, satellite, basis=None):
    receivers, satellite = np.asarray(receivers, float), np.asarray(satellite, float)
    if basis is None and satellite.shape == (2,):
        return dynamics.predict_observations(curve, endpoint, tags, xyz, receivers, satellite)
    tags = np.asarray(tags, float)
    basis = np.column_stack([np.ones(len(tags)), tags]) if basis is None else np.asarray(basis, float)
    if (receivers.ndim != 2 or len(receivers) != len(xyz)
            or basis.shape != (len(tags), receivers.shape[1])
            or satellite.shape not in ((2,), (3,))
            or not all(np.isfinite(x).all() for x in (receivers, satellite, basis))):
        raise ValueError('finite clock coefficients and matching receiver basis required')
    clock = basis@receivers.T
    if len(tags) > 1 and (np.any(np.diff(tags) <= 0)
            or np.any(abs(np.diff(clock, axis=0)/np.diff(tags)[:, None]) >= .01*dynamics.C)):
        raise ValueError('monotone receiver clocks required')
    pieces = [dynamics.predict_observations(curve, endpoint, [t], xyz,
              np.column_stack([b, np.zeros(len(xyz))]), satellite[:2])
              for t, b in zip(tags, clock, strict=True)]
    pair = {key: np.concatenate([p[key] for p in pieces], axis=0) for key in pieces[0]}
    if len(satellite) == 3:
        x = pair['transmit_s']-endpoint
        extra_rate = 2*satellite[2]*np.minimum(x, 0.)
        pair['code_m'] -= satellite[2]*np.minimum(x, 0.)**2
        # Chain the extra transmit-clock slope through the existing implicit
        # light-time derivatives. Emission geometry itself is unchanged.
        pair['receiver_clock_derivative'] += extra_rate*(1-pair['range_receive_rate_m_s']/dynamics.C)/dynamics.C
        pair['station_derivative'] -= (extra_rate/dynamics.C)[..., None]*pair['unit_ray']/pair['light_time_denominator'][..., None]
        if 'initial_state_derivative' in pair:
            range_jac = pair['initial_state_derivative']/(1+satellite[1]/dynamics.C)
            pair['initial_state_derivative'] += (extra_rate/dynamics.C)[..., None]*range_jac
    return pair
