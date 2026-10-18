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


def _source_weather_fields(weather,mjd,latitude,longitude,height):
    """Fixed VMF3 grid fields for decimal ray arithmetic; frozen evaluator stays intact."""
    from datetime import datetime,timedelta
    import math
    # The original evaluator supplies admission checks and weighted height-
    # transferred zenith delays. Mapping fields below use its same four nodes.
    _,_,dry,wet=weather.evaluate(mjd,latitude,longitude,height,45.)
    lon=longitude%360;i=int(np.floor(89.5-latitude));j=int(np.floor(lon-.5))
    u,v=89.5-latitude-i,lon-.5-j
    weights=np.array([(1-u)*(1-v),(1-u)*v,u*(1-v),u*v]);indices=[(i,j),(i,j+1),(i+1,j),(i+1,j+1)]
    lo=np.floor(mjd*4)/4;hi=np.ceil(mjd*4)/4;fraction=0 if lo==hi else (mjd-lo)/(hi-lo)
    fields=np.array([weather.grids[lo][a,b]*(1-fraction)+weather.grids[hi][a,b]*fraction for a,b in indices])
    dt=datetime(1858,11,17)+timedelta(days=mjd);doy=dt.timetuple().tm_yday+mjd-np.floor(mjd)
    phase=doy/365.25*2*np.pi;seasonal=np.array([1,math.cos(phase),math.sin(phase),math.cos(2*phase),math.sin(2*phase)])
    bc=np.array([weather.harmonic_amplitudes(89.5-a,.5+b)@seasonal for a,b in indices])
    return {'weights':weights,'ah':fields[:,0],'aw':fields[:,1],'bh':bc[:,0],'bw':bc[:,1],
        'ch':bc[:,2],'cw':bc[:,3],'dry':float(dry),'wet':float(wet),'height':float(height)}


class StableSourceRay:
    """Portable decimal evaluation of small admitted physical path increments.

    Product coefficients and meteorology remain the admitted binary64 inputs;
    extra precision resolves arithmetic, not physical accuracy. The same RTN
    product-error law, SLERP, emission and P1-only hardware convention apply.
    """
    def __init__(self,provider,weather,mjd_day,reference,code,tag_s,station,clock,*,digits=50):
        from decimal import Decimal,localcontext
        from scipy.spatial.transform import Rotation
        if reference==provider.precise.target or reference not in provider.precise.offsets:
            raise ValueError('candidate/unadmitted stable source before decoding')
        if provider.z_only:raise ValueError('complete body antenna source model required')
        if digits not in (35,50):raise ValueError('declared decimal precision required')
        self.digits=digits;self.D=Decimal;self.provider=provider;self.reference=reference
        self.localcontext=localcontext;self.coefficients={};self.clock_samples=provider.precise.clocks[reference]
        with localcontext() as ctx:
            ctx.prec=digits
            self.c=Decimal(C);self.omega=Decimal(OMEGA);self.tag=Decimal(float(tag_s));self.code=Decimal(float(code));self.clock=Decimal(float(clock))
            self.station=list(map(lambda v:Decimal(float(v)),station))
            lat,lon,height,up=geodetic(np.asarray(station,float));self.up=[Decimal(float(v)) for v in up]
            utc=mjd_day+(tag_s-clock/C-18)/86400.
            params=_source_weather_fields(weather,utc,np.degrees(lat),np.degrees(lon),float(height))
            self.weather_source=weather;self.weather_request=(utc,np.degrees(lat),np.degrees(lon),float(height))
            self.weather={k:([Decimal(float(v)) for v in value] if isinstance(value,(list,np.ndarray)) else Decimal(float(value))) for k,value in params.items()}
            tx=provider.antenna_state(reference,code,tag_s)[0];self.attitude_anchor=Decimal(tx)
            left=provider.step*np.floor(tx/provider.step);samples=provider.attitude.samples[reference]
            if left not in samples or left+provider.step not in samples:raise ValueError('stable attitude gap')
            a,b=Rotation.from_quat([samples[left],samples[left+provider.step]],scalar_first=True)
            self.angular=[Decimal(float(v)) for v in (a.inv()*b).as_rotvec()/provider.step]
            self.attitude=[[Decimal(float(v)) for v in row] for row in provider.attitude.body_to_ecef(reference,tx,provider.step)]
            pco=np.asarray(provider.precise.offsets[reference]['if_pco_body_m']).copy()
            if provider.z_only:pco[:2]=0.
            self.pco=[Decimal(float(v)) for v in pco]
            self.interval=(Decimal(float(left)),Decimal(float(left+provider.step)))
            self.base=self._path([Decimal(0)]*8)

    @staticmethod
    def _dot(a,b):return sum(x*y for x,y in zip(a,b,strict=True))
    @staticmethod
    def _cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    def _norm(self,a):return self._dot(a,a).sqrt()
    def _orbit(self,t):
        from decimal import ROUND_FLOOR
        D=self.D;center=int((t/D(300)+D('.5')).to_integral_value(rounding=ROUND_FLOOR))*300
        if center not in self.coefficients:
            anchor,c=self.provider.precise.coefficients(self.reference,float(center),9)
            self.coefficients[center]=([D(float(v)) for v in anchor],[[D(float(v)) for v in row] for row in c])
        anchor,c=self.coefficients[center];x=(t-D(center))/D(300)
        r=c[-1].copy();v=[D(0)]*3
        for row in c[-2::-1]:
            v=[v[j]*x+r[j] for j in range(3)];r=[r[j]*x+row[j] for j in range(3)]
        return [anchor[j]+r[j] for j in range(3)],[z/D(300) for z in v]
    def _rtn(self,t):
        r,v=self._orbit(t);rad=[z/self._norm(r) for z in r]
        inert=[v[0]-self.omega*r[1],v[1]+self.omega*r[0],v[2]]
        normal=self._cross(r,inert);nn=self._norm(normal);normal=[z/nn for z in normal]
        return list(zip(rad,self._cross(normal,rad),normal,strict=True))
    def _state(self,t,orbit):
        r,v=self._orbit(t)
        if any(orbit):
            b=self._rtn(t);lo=self._rtn(t-self.D('.5'));hi=self._rtn(t+self.D('.5'))
            r=[r[j]+self._dot(b[j],orbit) for j in range(3)]
            v=[v[j]+self._dot([hi[j][i]-lo[j][i] for i in range(3)],orbit) for j in range(3)]
        from decimal import ROUND_FLOOR
        left=int((t/self.D(30)).to_integral_value(rounding=ROUND_FLOOR))*30
        if left not in self.clock_samples or left+30 not in self.clock_samples:raise ValueError('stable clock gap')
        fraction=(t-self.D(left))/self.D(30)
        ca=self.D(self.clock_samples[left]['clock_s']);cb=self.D(self.clock_samples[left+30]['clock_s'])
        clock=ca+fraction*(cb-ca)-2*self._dot(r,v)/self.c**2
        return r,v,clock
    def _small_rotation(self,vector,angle):
        q=self._dot(angle,angle)
        if q>self.D('.01'):raise ValueError('stable rotation outside declared small-angle domain')
        sine=self.D(1);cosine=self.D('.5');a=sine;b=cosine
        for k in range(1,32):
            a*=-q/self.D((2*k)*(2*k+1));b*=-q/self.D((2*k+1)*(2*k+2))
            sine+=a;cosine+=b
            if max(abs(a),abs(b))<self.D(10)**(-self.digits):break
        else:raise ValueError('stable rotation series did not converge')
        cross=self._cross(angle,vector);cross2=self._cross(angle,cross)
        return [vector[j]+sine*cross[j]+cosine*cross2[j] for j in range(3)]
    def _atmosphere(self,sine,wet):
        p=self.weather;D=self.D
        if not D('.08')<=sine<=D('1.00000000000001'):raise ValueError('stable atmosphere outside domain')
        def cf(a,b,c):return (1+a/(1+b/(1+c)))/(sine+a/(sine+b/(sine+c)))
        mh=sum(p['weights'][i]*cf(p['ah'][i],p['bh'][i],p['ch'][i]) for i in range(4))
        mw=sum(p['weights'][i]*cf(p['aw'][i],p['bw'][i],p['cw'][i]) for i in range(4))
        mh+=(1/sine-cf(D('2.53e-5'),D('5.49e-3'),D('1.14e-3')))*p['height']/1000
        if p['wet']+wet<0:raise ValueError('negative stable total wet')
        return mh*p['dry']+mw*(p['wet']+wet)
    def _path(self,source):
        D=self.D;wet=source[0];orb=source[1:4];ant=source[4:7];bias=source[7]
        offset=-(self.code-bias)/self.c
        tolerance=D(10)**(-(self.digits-8))
        for _ in range(16):
            tx=self.tag+offset;r,v,clock=self._state(tx,orb);updated=-(self.code-bias)/self.c-clock
            if abs(updated-offset)<tolerance:offset=updated;break
            offset=updated
        else:raise ValueError('stable emission did not converge')
        return self._at_time(self.tag+offset,source)
    def _at_time(self,tx,source):
        D=self.D;wet=source[0];orb=source[1:4];ant=source[4:7];offset=tx-self.tag
        if not self.interval[0]<tx<self.interval[1]:raise ValueError('stable source crossed interpolation interval')
        r,v,clock=self._state(tx,orb)
        pco=[self.pco[j]+ant[j] for j in range(3)];body=[self._dot(row,pco) for row in self.attitude]
        body=self._small_rotation(body,[-z*(tx-self.attitude_anchor) for z in self.angular])
        apc=[r[j]+body[j] for j in range(3)];tau=-self.clock/self.c-offset
        if not 0<tau<1:raise ValueError('stable light time outside domain')
        mask_point=self._small_rotation(apc,[D(0),D(0),self.omega*offset])
        mask_ray=[mask_point[j]-self.station[j] for j in range(3)]
        if self._dot(mask_ray,self.up)/self._norm(mask_ray)<D(float(np.sin(np.radians(10.)))):
            raise ValueError('stable physical reference below original ten-degree mask')
        rotated=self._small_rotation(apc,[D(0),D(0),-self.omega*tau])
        ray=[rotated[j]-self.station[j] for j in range(3)];rho=self._norm(ray)
        atmosphere=self._atmosphere(self._dot(ray,self.up)/rho,wet)
        return ray,rho,clock,atmosphere,tx
    def increment(self,source,*,as_decimal=False):
        from ..kinematic import gnss_combinations
        with self.localcontext() as ctx:
            ctx.prec=self.digits
            s=[self.D(float(v)) if not isinstance(v,self.D) else v for v in source]
            if len(s)!=8 or not all(v.is_finite() for v in s):raise ValueError('finite eight-coordinate local source required')
            ray,rho,clock,atmosphere,_=self._path(s);a,r0,c0,t0,_=self.base
            dr=[ray[j]-a[j] for j in range(3)]
            distance=(2*self._dot(a,dr)+self._dot(dr,dr))/(rho+r0)
            phase=distance-self.c*(clock-c0)+atmosphere-t0
            mw=self.D(float(gnss_combinations.transform()[3,0]/gnss_combinations.ALPHA))*s[7]
            values=[phase+s[7],phase,mw]
            return values if as_decimal else np.array([float(v) for v in values])
    def central_mappings(self):
        with self.localcontext() as ctx:
            ctx.prec=self.digits;step=self.D('1e-12');columns=[]
            for j in range(8):
                d=[self.D(0)]*8;d[j]=step
                plus=self.increment(d,as_decimal=True);minus=self.increment([-v for v in d],as_decimal=True)
                columns.append([float((a-b)/(2*step)) for a,b in zip(plus,minus,strict=True)])
        g=np.array(columns).T
        return {'wet_mapping':float(g[0,0]),'orbit_mapping':g[0,1:4], 'antenna_mapping':g[0,4:7],
            'bias_code_mapping':float(g[0,7]),'bias_phase_mapping':float(g[1,7]),'bias_mw_mapping':float(g[2,7]),
            'source_emission_relativity_linearized':True,'source_mapping_method':'decimal50 central derivative, 1e-12 m step',
            'stable_decimal_digits':self.digits}

    def clock_coefficient(self):
        """Stable geometric derivative plus explicitly resolved weather-time term."""
        with self.localcontext() as ctx:
            ctx.prec=self.digits;ray,rho,_,_,_=self.base
            unit=[v/rho for v in ray];sine=self._dot(unit,self.up);h=self.D('1e-12')
            atmo_derivative=(self._atmosphere(sine+h,self.D(0))-self._atmosphere(sine-h,self.D(0)))/(2*h)
            gradient=[unit[j]+atmo_derivative*(self.up[j]-sine*unit[j])/rho for j in range(3)]
            rotated=[ray[j]+self.station[j] for j in range(3)]
            rate=[-self.omega*rotated[1]/self.c,self.omega*rotated[0]/self.c,self.D(0)]
            derivative=self._dot(gradient,rate)
            utc,lat,lon,height=self.weather_request;elevation=float(np.degrees(np.arcsin(np.clip(float(sine),-1.,1.))))
            def delay(mjd):
                mh,mw,dry,wet=self.weather_source.evaluate(mjd,lat,lon,height,elevation)
                return mh*dry+mw*wet
            time_rate=(delay(utc+1/86400.)-delay(utc-1/86400.))/2
            derivative-=self.D(float(time_rate))/self.c
            return float(1+derivative)

    def _gradient(self):
        ray,rho,_,_,_=self.base;unit=[v/rho for v in ray];sine=self._dot(unit,self.up);h=self.D('1e-12')
        derivative=(self._atmosphere(sine+h,self.D(0))-self._atmosphere(sine-h,self.D(0)))/(2*h)
        return [unit[j]+derivative*(self.up[j]-sine*unit[j])/rho for j in range(3)],sine
    def mappings(self):
        from ..kinematic import gnss_combinations
        with self.localcontext() as ctx:
            ctx.prec=self.digits;D=self.D;gradient,sine=self._gradient();tx=self.base[-1];zero=[D(0)]*8;dt=D('1e-8')
            lo=self._at_time(tx-dt,zero);hi=self._at_time(tx+dt,zero)
            rate=((hi[1]-lo[1])-self.c*(hi[2]-lo[2])+hi[3]-lo[3])/(2*dt)
            clock_rate=(hi[2]-lo[2])/(2*dt);com,velocity=self._orbit(tx)
            basis=self._rtn(tx);minus=self._rtn(tx-D('.5'));plus=self._rtn(tx+D('.5'))
            angle=[D(0),D(0),-self.omega*(-self.clock/self.c-(tx-self.tag))]
            orbit=[];antenna=[]
            for j in range(3):
                direction=[row[j] for row in basis];bdot=[plus[i][j]-minus[i][j] for i in range(3)]
                dc=-2*(self._dot(velocity,direction)+self._dot(com,bdot))/self.c**2
                orbit.append(float(self._dot(gradient,self._small_rotation(direction,angle))-rate*dc/(1+clock_rate)-self.c*dc))
                body=[row[j] for row in self.attitude]
                body=self._small_rotation(body,[-z*(tx-self.attitude_anchor) for z in self.angular])
                antenna.append(float(self._dot(gradient,self._small_rotation(body,angle))))
            phase=rate/(self.c*(1+clock_rate));wet=self._atmosphere(sine,D(1))-self._atmosphere(sine,D(0))
            return {'wet_mapping':float(wet),'orbit_mapping':orbit,'antenna_mapping':antenna,
                'bias_code_mapping':float(1+phase),'bias_phase_mapping':float(phase),
                'bias_mw_mapping':float(gnss_combinations.transform()[3,0]/gnss_combinations.ALPHA),
                'source_emission_relativity_linearized':True,'source_mapping_method':'decimal implicit emission and analytic geometric derivatives',
                'stable_decimal_digits':self.digits}
