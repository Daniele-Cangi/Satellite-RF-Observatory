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


def emitted_source_mappings(provider, weather, mjd_day, reference, code, tag_s, station, clock):
    """Emitted APC displacement shapes, at fixed admitted emission and clocks.

    RTN uses COM position and inertial velocity expressed in ECEF. Body PCO
    axes use the admitted attitude at emission. Rotate both to reception ECEF.
    Include the VMF3 elevation derivative. No product-error amplitude is known.
    """
    if reference==provider.precise.target or reference not in provider.precise.offsets:
        raise ValueError('candidate/unadmitted source geometry')
    tx,_,apc,offset=provider.antenna_state(reference,code,tag_s)
    com,velocity=provider.precise.orbit(reference,tx)
    radial=com/np.linalg.norm(com)
    inertial=velocity+np.cross([0.,0.,OMEGA],com)
    normal=np.cross(com,inertial);normal/=np.linalg.norm(normal)
    rtn=np.column_stack([radial,np.cross(normal,radial),normal])
    body=provider.attitude.body_to_ecef(reference,tx,provider.step)
    tau=-clock/C-offset
    if not 0<tau<1:raise ValueError('invalid source light time')
    rotation=np.column_stack([rotate_z(v,-OMEGA*tau) for v in np.eye(3)])
    rotated=rotation@apc;ray=rotated-station
    gradient=ray/np.linalg.norm(ray)
    lat,lon,height,_=geodetic(station)
    utc=mjd_day+(tag_s-clock/C-18)/86400.
    from positioning.calibration import troposphere
    def atmosphere(point):
        elevation=troposphere(station,point)[1]
        mh,mw,dry,wet=weather.evaluate(utc,np.degrees(lat),np.degrees(lon),float(height),elevation)
        return mh*dry+mw*wet
    for j in range(3):
        delta=np.eye(3)[j]  # one metre central elevation derivative
        gradient[j]+=(atmosphere(rotated+delta)-atmosphere(rotated-delta))/2.
    return {'orbit_mapping':gradient@rotation@rtn,'antenna_mapping':gradient@rotation@body,
        'source_emission_gpst_s':tx,'source_light_time_s':tau}
