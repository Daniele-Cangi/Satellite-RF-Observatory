"""Offline Sun/Moon-only DE440s and IERS EOP extract. Optional skyfield==1.53.
No artificial-satellite states are loaded. Geometric simultaneous positions;
no observe()/apparent() light-time or aberration correction. Not a CODE ephemeris.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import numpy as np

KERNEL_SHA = 'c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2'
EOP_SHA = 'd7adc96fca77e27746586e8b7dd75376eebbc82ba5f65ced13379cf0ebd62327'


def prepare(raw_directory, output):
    from skyfield.api import load, load_file
    from skyfield.framelib import itrs
    from skyfield.data import iers
    root,output = Path(raw_directory),Path(output)
    if importlib.metadata.version('skyfield') != '1.53':
        raise ValueError('skyfield 1.53 required')
    for name,digest in [('de440s.bsp',KERNEL_SHA),('finals2000A.all',EOP_SHA)]:
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('raw source hash differs: '+name)
    raw=(root/'finals2000A.all').read_bytes()
    rows=[s for s in raw.decode('ascii').splitlines() if s[7:15].strip() and 61286<=float(s[7:15])<=61289]
    if len(rows)!=4 or any(s[16]!='I' or s[57]!='I' for s in rows):
        raise ValueError('four observed EOP days required')
    extracted=('\n'.join(rows)+'\n').encode('ascii')
    import io
    eop=iers.parse_x_y_dut1_from_finals_all(io.BytesIO(extracted))
    eph=load_file(str(root/'de440s.bsp'))
    events={}
    for tag,day,start in [('g14','2026-09-03',14100),('g12','2026-09-05',37800)]:
        samples=[]
        for seconds in sorted({t+d for t in range(start,start+301,30) for d in (0,18)}):
            utc=datetime.fromisoformat(day)+timedelta(seconds=seconds-18)
            mjd=(utc-datetime(1858,11,17)).total_seconds()/86400
            if not eop['utc_mjd'][0]<=mjd<=eop['utc_mjd'][-1]:
                raise ValueError('EOP extrapolation forbidden')
            dut1=float(np.interp(mjd,eop['utc_mjd'],eop['dut1']))
            ts=load.timescale(delta_t=69.184-dut1,builtin=True)
            iers.install_polar_motion_table(ts,eop)
            time=ts.from_datetime(utc.replace(tzinfo=timezone.utc))
            if abs((time.tt-time.tai)*86400-32.184)>1e-4 or abs(time.dut1-dut1)>1e-7:
                raise ValueError('time-scale mismatch')
            sample={'time_gpst_s':seconds,'utc':utc.isoformat(),'tai_minus_utc_s':37.,'ut1_minus_utc_s':dut1,
                    'xp_arcsec':float(np.interp(mjd,eop['utc_mjd'],eop['x_arcseconds'])),
                    'yp_arcsec':float(np.interp(mjd,eop['utc_mjd'],eop['y_arcseconds']))}
            for body in ('sun','moon'):
                vector=(eph[body]-eph['earth']).at(time)
                sample[body+'_ecef_m']=vector.frame_xyz(itrs).m.tolist()
                sample[body+'_icrs_m']=vector.position.m.tolist()
            samples.append(sample)
        events[tag]={'date_gpst':day,'samples':samples}
    eph.close()
    products={'eop.txt':extracted,'sun_moon.json':(json.dumps(events,indent=2,allow_nan=False)+'\n').encode()}
    receipt={'schema':'solid-earth-inputs-v1','target_states_accessed':False,
             'producer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'raw_sources':{'de440s.bsp':{'sha256':KERNEL_SHA,'url':'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp'},
                            'finals2000A.all':{'sha256':EOP_SHA,'url':'https://maia.usno.navy.mil/ser7/finals2000A.all'}},
             'versions':{k:importlib.metadata.version(k) for k in ('skyfield','jplephem','numpy','sgp4')},
             'conventions':'GPST-UTC=18 s; TAI-UTC=37 s; TT-UTC=69.184 s; observed Bulletin A UT1/xp/yp linearly interpolated; IAU2000A; dX/dY not applied; geometric simultaneous Sun/Moon DE440s -> ITRS',
             'files':{k:hashlib.sha256(v).hexdigest() for k,v in products.items()}}
    for name,data in products.items():
        with (output/name).open('xb') as stream: stream.write(data)
    with (output/'receipt.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(receipt,stream,indent=2); stream.write('\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('raw_directory'); p.add_argument('output')
    a=p.parse_args(); prepare(a.raw_directory,a.output)
