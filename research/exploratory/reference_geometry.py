"""Observation-free ENU directions from admitted reference products only."""
from functools import lru_cache

import numpy as np

from positioning.calibration import C, OMEGA, geodetic, rotate_z
from . import day_reference as day
from .real_phase import BASE


def vacuum_direction(provider, station, time_s, reference):
    """Nominal zero-receiver-clock vacuum ray; no measured code is consumed.

    Iterate geometric code consistently with the reference satellite clock and
    emission/Sagnac convention. These are descriptive calibration features,
    not independent orbit truth or a physical propagation/error bound.
    """
    code = 25e6
    for _ in range(8):
        _, clock, antenna, offset = provider.antenna_state(reference, code, time_s)
        if not 0 < -offset < 1:
            raise ValueError('invalid nominal reference light time')
        ray = rotate_z(antenna, OMEGA*offset)-station
        updated = np.linalg.norm(ray)-C*clock
        if abs(updated-code) <= 1e-6:
            lat, lon, _, up = geodetic(station)
            east = np.array([-np.sin(lon), np.cos(lon), 0.])
            north = np.cross(up, east)
            return np.array([east, north, up]) @ (ray/np.linalg.norm(ray))
        code = updated
    raise ValueError('nominal reference ray did not converge')


def environment(context):
    _, original, ctx, _, positions, _, report = context
    precise, _, hashes = day.frame.guarded_products(
        ctx, original['references'], day.INPUTS/'timed',
        BASE/'inputs/reference_biases/g12', BASE/'inputs/reference_antennas/g12')
    attitude, ah = day.frame.load_attitude(day.INPUTS/'attitude', ctx, original['references'])
    if hashes | ah != report['product_sha256']:
        raise ValueError('reference geometry products differ from calibration')
    provider = day.frame.AttitudeReference(precise, attitude)
    coordinates = {(s,t):np.asarray(positions[s][i])
                   for s in original['stations'] for i,t in enumerate(ctx.times)}

    @lru_cache(maxsize=20000)
    def direction(station, time_s, reference):
        if reference == ctx.target or reference not in original['references']:
            raise ValueError('target or unknown reference at geometry boundary')
        return vacuum_direction(provider, coordinates[station,time_s], time_s, reference)
    return direction
