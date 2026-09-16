"""Satellite-RF Python adaptation of IERS DEHANTTIDEINEL and five helpers.

Not IERS software, distributed or endorsed by the IERS Conventions Center.
Original authors: V. Dehant, P. M. Mathews, J. Gipson and IERS maintainers.
See iers_reference/*.F for original source and intact IERS software license.
Changes: renamed/vectorized Python routines, explicit UTC/TAI input instead of
DAT/CAL2JD, validated finite vectors, component outputs and separate permanent
term. Original coefficients and all step-1/step-2 terms retained. No step-3
permanent-tide removal in the primary displacement (tide-free station input).
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import numpy as np

TABLE_PATH = Path(__file__).parent/'inputs/solid_earth/frequency_tables.json'
TABLE_SHA256 = '789c9e8d712b0a32ef6c7c0e9cf3c9719c97db516cc0c8a4c594fc45d6d210ce'


def frequency_tables():
    raw = TABLE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != TABLE_SHA256:
        raise ValueError('frequency tables changed')
    return {k: np.array(v) for k,v in json.loads(raw).items()}


def local_axes(xyz):
    xyz = np.asarray(xyz, dtype=float)
    if xyz.shape != (3,) or not np.all(np.isfinite(xyz)) or not 6e6 < np.linalg.norm(xyz) < 7e6:
        raise ValueError('finite terrestrial ECEF vector in metres required')
    r = np.linalg.norm(xyz)
    c, s = np.hypot(*xyz[:2])/r, xyz[2]/r
    if c < 1e-12:
        raise ValueError('polar station longitude is undefined')
    cl, sl = xyz[0]/(r*c), xyz[1]/(r*c)
    # Columns radial, north, east, using GEOCENTRIC latitude as in IERS.
    matrix = np.array([[c*cl,-s*cl,-sl],[c*sl,-s*sl,cl],[s,c,0.]])
    return s,c,sl,cl,matrix


def arguments(utc, tai_minus_utc):
    if utc.tzinfo is not None or not np.isfinite(tai_minus_utc) or not 10 <= tai_minus_utc <= 100:
        raise ValueError('naive UTC datetime and explicit finite TAI-UTC required')
    t = ((utc-datetime(2000,1,1,12)).total_seconds()+tai_minus_utc+32.184)/(86400*36525)
    hour = (utc-datetime(utc.year,utc.month,utc.day)).total_seconds()/3600
    s = 218.31664563+(481267.88194+(-.0014663889+.00000185139*t)*t)*t
    tau = hour*15+280.4606184+(36000.7700536+(.00038793-.0000000258*t)*t)*t-s
    s += (1.396971278+(.000308889+(.000000021+.000000007*t)*t)*t)*t
    h = 280.46645+(36000.7697489+(.00030322222+(.000000020-.00000000654*t)*t)*t)*t
    p = 83.35324312+(4069.01363525+(-.01032172222+(-.0000124991+.00000005263*t)*t)*t)*t
    z = 234.95544499+(1934.13626197+(-.00207561111+(-.00000213944+.00000001650*t)*t)*t)*t
    ps = 282.93734098+(1.71945766667+(.00045688889+(-.00000001778-.00000000334*t)*t)*t)*t
    return np.fmod([s,h,p,z,ps],360), np.fmod(tau,360)


def permanent_displacement(xyz):
    s,c,sl,cl,axes = local_axes(xyz)
    h2 = .6078-.0006*(1-1.5*c*c)
    l2 = .0847+.0002*(1-1.5*c*c)
    scale = -np.sqrt(5/(4*np.pi))*.31460
    return axes @ np.array([scale*h2*(1.5*s*s-.5),scale*l2*3*c*s,0])


def displacement_components(xyz, sun, moon, utc, tai_minus_utc):
    xyz = np.asarray(xyz,dtype=float)
    s,c,sl,cl,axes = local_axes(xyz)
    h2,l2 = .6078-.0006*(1-1.5*c*c), .0847+.0002*(1-1.5*c*c)
    h3,l3,re = .292,.015,6378136.6
    degree = np.zeros(3)
    diurnal = np.zeros(3)
    semidiurnal = np.zeros(3)
    latitude = np.zeros(3)
    for body,mass in [(sun,332946.0482),(moon,.0123000371)]:
        body = np.asarray(body,dtype=float)
        if body.shape != (3,) or not np.all(np.isfinite(body)) or np.linalg.norm(body) <= re:
            raise ValueError('finite external body ECEF vector in metres required')
        radius = np.linalg.norm(body)
        u = body/radius
        dot = np.dot(xyz/np.linalg.norm(xyz),u)
        fac = mass*re*(re/radius)**3
        p2 = 3*(h2/2-l2)*dot**2-h2/2
        p3 = 2.5*(h3-3*l3)*dot**3+1.5*(l3-h3)*dot
        degree += fac*(3*l2*dot*u+p2*axes[:,0])+fac*(re/radius)*(1.5*l3*(5*dot**2-1)*u+p3*axes[:,0])
        x,y,z = u
        a,b = x*sl-y*cl, x*cl+y*sl
        diurnal += axes @ np.array([-3*(-.0025)*s*c*fac*z*a,
                                    -3*(-.0007)*(c*c-s*s)*fac*z*a,
                                    -3*(-.0007)*s*fac*z*b])
        a2 = (x*x-y*y)*2*cl*sl-2*x*y*(cl*cl-sl*sl)
        b2 = (x*x-y*y)*(cl*cl-sl*sl)+2*x*y*2*cl*sl
        semidiurnal += axes @ np.array([-.75*(-.0022)*c*c*fac*a2,
                                         1.5*(-.0007)*s*c*fac*a2,
                                        -1.5*(-.0007)*c*fac*b2])
        dn = -3*.0012*s*s*fac*z*b-1.5*.0024*s*c*fac*b2
        de = 3*.0012*s*(c*c-s*s)*fac*z*a-1.5*.0024*s*s*c*fac*a2
        latitude += axes @ np.array([0,dn,de])
    angles,tau = arguments(utc,tai_minus_utc)
    tables = frequency_tables()
    fdiu,flong = np.zeros(3),np.zeros(3)
    for row in tables['STEP2DIU']:
        angle = np.deg2rad(tau+row[:5]@angles)+np.arctan2(xyz[1],xyz[0])
        si,co = np.sin(angle),np.cos(angle)
        dr = 2*s*c*(row[5]*si+row[6]*co)
        dn = (c*c-s*s)*(row[7]*si+row[8]*co)
        de = s*(row[7]*co-row[8]*si)
        fdiu += axes @ np.array([dr,dn,de])/1000
    for row in tables['STEP2LON']:
        angle = np.deg2rad(row[:5]@angles)
        si,co = np.sin(angle),np.cos(angle)
        dr = (3*s*s-1)/2*(row[5]*co+row[7]*si)
        dn = 2*s*c*(row[6]*co+row[8]*si)
        flong += axes @ np.array([dr,dn,0])/1000
    return {'degree_2_3':degree, 'anelastic_diurnal':diurnal,
            'anelastic_semidiurnal':semidiurnal,'latitude_dependence':latitude,
            'frequency_diurnal':fdiu,'frequency_long_period':flong}


def tide_displacement(xyz,sun,moon,utc,tai_minus_utc):
    return sum(displacement_components(xyz,sun,moon,utc,tai_minus_utc).values(),np.zeros(3))
