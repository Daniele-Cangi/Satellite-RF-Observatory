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


def emitted_source_mappings(provider, weather, mjd_day, reference, code, tag_s, station, clock, *, complete=False):
    """Emitted APC source shapes, optionally including emission/clock response.

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
    result={'orbit_mapping':gradient@rotation@rtn,'antenna_mapping':gradient@rotation@body,
        'source_emission_gpst_s':tx,'source_light_time_s':tau}
    if complete:
        from .precise_reference_model import relativity_m
        from ..kinematic import gnss_combinations
        def state_at(t):
            r,v=provider.precise.orbit(reference,t)
            return r,v,provider.precise.clock(reference,t)+relativity_m(r,v)/C
        rm,vm,_=state_at(tx-.5);rp,vp,_=state_at(tx+.5)
        bdot=rtn_basis(rp,vp)-rtn_basis(rm,vm)
        # Keep clock/attitude derivatives inside the current 30 s interval.
        dt=min(.01,(tx%30)/2,(30-tx%30)/2)
        if dt<1e-6:raise ValueError('source derivative at interpolation knot')
        _,_,cm=state_at(tx-dt);_,_,cp=state_at(tx+dt)
        clock_rate=(cp-cm)/(2*dt)
        body_rate=(provider.attitude.body_to_ecef(reference,tx+dt,provider.step)-
            provider.attitude.body_to_ecef(reference,tx-dt,provider.step))/(2*dt)
        apc_velocity=velocity+body_rate@np.asarray(provider.precise.offsets[reference]['if_pco_body_m'])
        # d R(-Omega*tau)/d tx, since tau = tag-clock/C-tx.
        rotated_rate=rotation@apc_velocity+np.cross([0.,0.,OMEGA],rotated)
        path_rate=gradient@rotated_rate
        dc=-2*(velocity@rtn+com@bdot)/C**2
        dtx=-dc/(1+clock_rate)
        result['restricted_orbit_mapping']=result['orbit_mapping'].copy()
        result['orbit_mapping']+=(path_rate-C*clock_rate)*dtx-C*dc
        hardware_phase=(path_rate/C-clock_rate)/(1+clock_rate)
        result.update(bias_phase_mapping=float(hardware_phase),bias_code_mapping=float(1+hardware_phase),
            bias_mw_mapping=float(gnss_combinations.transform()[3,0]/gnss_combinations.ALPHA),
            source_clock_rate_s_s=float(clock_rate),source_emission_relativity_linearized=True)
    return result


def rtn_basis(com, velocity):
    radial=com/np.linalg.norm(com)
    normal=np.cross(com,velocity+np.cross([0.,0.,OMEGA],com))
    normal/=np.linalg.norm(normal)
    return np.column_stack([radial,np.cross(normal,radial),normal])


def physical_source_provider(provider, candidate, probe):
    """Perturb admitted reference products, recomputing velocity/relativity/tx.

    Constant RTN product-trajectory residuals need not themselves be a new
    gravitational orbit. Body offsets use admitted attitude at the new tx.
    """
    from .precise_reference_model import PreciseReference
    from .reference_attitude_model import AttitudeReference
    if provider.precise.target!=candidate:raise ValueError('candidate boundary mismatch')
    allowed=set(provider.precise.offsets)
    if not set(probe)<={'wet','orbit','antenna','bias'}:raise ValueError('unknown physical source family')
    if any(k.rsplit('/',1)[-1] not in allowed for k in probe.get('bias',{})):
        raise ValueError('candidate/unadmitted hardware source before decoding')
    for family in ('orbit','antenna'):
        if candidate in probe.get(family,{}) or not set(probe.get(family,{}))<=allowed:
            raise ValueError('candidate/unadmitted physical source before decoding')
    vectors={f:{q:np.asarray(v,float) for q,v in probe.get(f,{}).items()} for f in ('orbit','antenna')}
    if any(v.shape!=(3,) or not np.isfinite(v).all() for d in vectors.values() for v in d.values()):
        raise ValueError('finite three-dimensional source displacement required')
    class Perturbed(PreciseReference):
        @lru_cache(maxsize=16384)
        def displacement(self,q,t,count):
            r,v=provider.precise.orbit(q,t,count)
            return rtn_basis(r,v)@vectors['orbit'].get(q,np.zeros(3))
        def orbit(self,q,t,count=9):
            if q==candidate or q not in allowed:raise ValueError('candidate/unadmitted perturbed orbit')
            r,v=provider.precise.orbit(q,t,count)
            dp=self.displacement(q,t,count)
            dv=(self.displacement(q,t+.5,count)-self.displacement(q,t-.5,count))
            return r+dp,v+dv  # denominator 2*.5 seconds
    offsets={q:{**item,'if_pco_body_m':np.asarray(item['if_pco_body_m'])+vectors['antenna'].get(q,np.zeros(3))}
        for q,item in provider.precise.offsets.items()}
    precise=Perturbed(provider.precise.orbits,provider.precise.clocks,offsets,candidate)
    return AttitudeReference(precise,provider.attitude,provider.step,provider.z_only)
