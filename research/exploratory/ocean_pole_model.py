"""FES2014b local ocean loading and IERS solid-Earth pole displacement.
Pole equations follow IERS chapter 7 (2018 update), eqs. 21,25,26; the
post-2010 branch of IERS 2010 table 7.7 is an explicit convention control.
Ocean loading is relative to solid Earth (CMC:NO), not declared CODE-aligned.
"""
from datetime import datetime
import re
import numpy as np
from positioning.calibration import geodetic
from .station_coordinates import basis
from .solid_earth_model import local_axes

NAMES=('ALGO','BOGT','DRAO','MKEA','PIE1','STJO','YELL','BRAZ','AREQ')
CONSTITUENTS=('M2','S2','N2','K2','K1','O1','P1','Q1','Mf','Mm','Ssa')


def parse_blq(text):
    lines=text.splitlines()
    if '$$ Ocean tide model: FES2014b' not in lines or not any(s.startswith('$$ CMC:  NO') for s in lines):
        raise ValueError('FES2014b CMC:NO required')
    result={}
    for i,line in enumerate(lines):
        if line.startswith('$$') or not line.strip():continue
        name=line.strip()
        if name not in NAMES:continue
        if name in result:raise ValueError('duplicate BLQ station')
        if not lines[i+3].startswith('$$ '+name) or 'lon/lat:' not in lines[i+3]:
            raise ValueError('BLQ geographic identity missing')
        coordinates=np.array([float(x) for x in lines[i+3].split('lon/lat:')[1].split()])
        numbers=np.array([[float(x) for x in s.split()] for s in lines[i+4:i+10]])
        if coordinates.shape!=(3,) or numbers.shape!=(6,11) or not np.all(np.isfinite(numbers)) or not np.all(np.isfinite(coordinates)):
            raise ValueError('malformed BLQ coefficients')
        if np.any(numbers[:3]<0) or np.any(np.abs(numbers[3:])>180):raise ValueError('invalid BLQ amplitude/phase')
        if not -180<=coordinates[0]<=180 or not -90<coordinates[1]<90:raise ValueError('invalid BLQ coordinates')
        result[name]={'lon_lat_height':coordinates.tolist(),'amplitude_uws_m':numbers[:3].tolist(),
                      'lag_uws_deg':numbers[3:].tolist(),'six_lines':'\n'.join(lines[i+4:i+10])+'\n'}
    if set(result)!=set(NAMES):raise ValueError('missing fit-station BLQ coefficients')
    cmc=[]
    for line in lines:
        if line.startswith('$$ CMC frequ :'):
            row=line.split();cmc.append((row[4],np.array([float(x) for x in row[-6:]])))
    if tuple(x[0] for x in cmc)!=CONSTITUENTS or not all(np.all(np.isfinite(x[1])) for x in cmc):
        raise ValueError('invalid CMC header')
    # C*cos(angle)+S*sin(angle): norm <= Frobenius norm([C S]); sum over tides.
    cmc_bound=float(sum(np.linalg.norm(row) for _,row in cmc))
    return result,cmc_bound


def geographic_distance(xyz,blq):
    lat,lon,_,_=geodetic(xyz)
    blo,bla,_=blq['lon_lat_height'];bla,blo=np.deg2rad([bla,blo])
    hav=np.sin((lat-bla)/2)**2+np.cos(lat)*np.cos(bla)*np.sin((lon-blo)/2)**2
    return float(6371000*2*np.arcsin(np.sqrt(np.clip(hav,0,1))))


def ocean_ecef(usw,xyz):
    values=np.asarray(usw,dtype=float)
    if values.shape!=(3,) or not np.all(np.isfinite(values)):raise ValueError('finite U/S/W vector required')
    u,s,w=values
    return basis(xyz).T@np.array([-w,-s,u])


def pole_reference(utc,convention='2018'):
    if utc.tzinfo is not None or not datetime(2010,1,1)<=utc<datetime(2030,1,1):
        raise ValueError('supported pole interval is naive UTC 2010-2029')
    years=(utc-datetime(2000,1,1)).total_seconds()/(365.25*86400)
    if convention=='2018':return np.array([55.+1.677*years,320.5+3.460*years])/1000
    if convention=='2010':return np.array([23.513+7.6141*years,358.891-.6287*years])/1000
    raise ValueError('unknown pole convention')


def pole_ecef(xyz,utc,xp,yp,convention='2018'):
    if not np.all(np.isfinite([xp,yp])) or max(abs(xp),abs(yp))>2:
        raise ValueError('observed polar coordinates in arcseconds required')
    ref=pole_reference(utc,convention)
    m1,m2=xp-ref[0],-(yp-ref[1])
    s,c,sl,cl,axes=local_axes(xyz)
    a,b=m1*cl+m2*sl,m1*sl-m2*cl
    return axes@np.array([-.066*s*c*a,.009*(s*s-c*c)*a,.009*s*b])
