"""Prepare the fixed distinct-day reference hour; never parse target states."""
import argparse
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path

import hatanaka
import numpy as np

from positioning.acquisition import download
from positioning.calibration import observation_window
from positioning.context import Context
from positioning.qualification import scan_structure
from . import station_frame_epoch as frame
from . import prepare_solid_earth_inputs as celestial
from . import prepare_ocean_loading as ocean
from . import ocean_pole_model as loading
from . import solid_earth_study as solid
from .precise_reference_model import extract_clock
from .reference_attitude_model import extract_attitude
from .erp_polar_bound import pinned, strict_json
from .day_reference_inputs import read_plan, load_basis, PLAN_SHA

BASE = Path(__file__).parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2, allow_nan=False)+'\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(raw)


def prepare(work, products, celestial_raw, output):
    from skyfield.api import load, load_file
    from skyfield.framelib import itrs
    from skyfield.data import iers
    import importlib.metadata
    if importlib.metadata.version('skyfield') != '1.53':
        raise ValueError('skyfield 1.53 required')
    plan = read_plan()
    tag = plan['archive_tag']
    admitted, timed, att, terrestrial, blq, prior, auxiliary = load_basis(plan)
    ctx = Context(plan['target_excluded'], plan['date_gpst'], plan['start_gpst_s'], plan['samples'], plan['step_s'])
    refs = plan['references']
    if plan['stations'] != admitted['fit_stations'] or ctx.target in refs:
        raise ValueError('fixed cohort differs')
    work.mkdir(parents=True, exist_ok=True)
    observations, acquisition = {}, {}
    authoritative = {r['station']:r for r in admitted['observation_receipts']}
    day_tag = datetime.fromisoformat(ctx.date_gpst).strftime('%Y%j')
    for name in plan['stations']:
        filename = name+'_R_'+day_tag+'0000_01D_30S_MO.crx.gz'
        old_receipt = authoritative[name]
        if old_receipt['url'].split('/')[-1] != filename:
            raise ValueError('observation date or station differs')
        path = work/filename
        if not path.exists():
            raw, _ = download(old_receipt['url'])
            write(path, raw)
        raw = pinned(path, old_receipt['sha256'])
        decoded = hatanaka.decompress(raw, strict=True)
        if sha(decoded) != old_receipt['decoded_sha256']:
            raise ValueError('decoded bytes differ from pinned admission')
        structure = scan_structure(decoded.decode('ascii'), ctx.target, ctx.date_gpst)
        obs = observation_window(decoded.decode('ascii'), structure['header'], structure['gps_observation_types'], False, ctx)
        for epoch in obs:
            epoch['if_code_m'] = {sv: value for sv, value in epoch['if_code_m'].items() if sv in refs}
        observations[name] = obs
        acquisition[name] = old_receipt | {'decoded_sha256': sha(decoded), 'status': 'EXTRACTED'}
        print(name, len(obs), flush=True)
    write(output/'observations.json', observations)
    for folder in ('timed', 'attitude'):
        (output/folder).mkdir(parents=True, exist_ok=True)
    start, end = ctx.times[0]-120, ctx.times[-1]+120
    for kind in ('orbit', 'clock'):
        source = timed[kind]
        raw = pinned(products/source['source_url'].split('/')[-1], source['source_compressed_sha256'])
        extract = (pinned(BASE/f'inputs/timed_reference_products/{tag}/reference_orbit.txt',source['extract_sha256']) if kind == 'orbit' else
                   extract_clock(gzip.decompress(raw).decode('ascii'), refs, ctx.target, ctx.date_gpst, start, end).encode())
        timed[kind]['extract_sha256'] = sha(extract)
        write(output/'timed'/f'reference_{kind}.txt', extract)
    timed['clock_window_gpst_s'] = [start, end]
    write(output/'timed/receipt.json', timed)
    raw = pinned(products/att['source_url'].split('/')[-1], att['source_compressed_sha256'])
    extracted = extract_attitude(gzip.decompress(raw).decode('ascii'), refs, ctx.target, ctx.date_gpst, start, end).encode()
    att.update(extract_sha256=sha(extracted), window_gpst_s=[start, end])
    write(output/'attitude/reference_attitude.obx', extracted)
    write(output/'attitude/receipt.json', att)
    # Extend the same regularized ARP, DE440s solid tide, HARDISP and pole recipe.
    pinned(celestial_raw/'de440s.bsp', celestial.KERNEL_SHA)
    eop_raw = pinned(celestial_raw/'finals2000A.all', celestial.EOP_SHA)
    eop = iers.parse_x_y_dut1_from_finals_all(io.BytesIO(eop_raw))
    eph = load_file(str(celestial_raw/'de440s.bsp'))
    samples = []
    for t in ctx.times:
        utc = datetime.fromisoformat(ctx.date_gpst)+timedelta(seconds=t-18)
        mjd = (utc-datetime(1858,11,17)).total_seconds()/86400
        if not eop['utc_mjd'][0] <= mjd <= eop['utc_mjd'][-1]:
            raise ValueError('EOP does not bracket the fixed epoch')
        dut1 = float(np.interp(mjd, eop['utc_mjd'], eop['dut1']))
        ts = load.timescale(delta_t=69.184-dut1, builtin=True)
        iers.install_polar_motion_table(ts, eop)
        tm = ts.from_datetime(utc.replace(tzinfo=timezone.utc))
        samples.append({'utc': utc.isoformat(), 'tai_minus_utc_s': 37,
                        'sun_ecef_m': (eph['sun']-eph['earth']).at(tm).frame_xyz(itrs).m.tolist(),
                        'moon_ecef_m': (eph['moon']-eph['earth']).at(tm).frame_xyz(itrs).m.tolist(),
                        'xp_arcsec': float(np.interp(mjd,eop['utc_mjd'],eop['x_arcseconds'])),
                        'yp_arcsec': float(np.interp(mjd,eop['utc_mjd'],eop['y_arcseconds']))})
    eph.close()
    exe, build = ocean.build(work/'hardisp-build')
    positions = {}
    for st in prior['stations']:
        name = st['station']
        position, _ = frame.station_model(st, terrestrial, ctx.date_gpst, ctx.times)
        usw = ocean.series(exe, datetime.fromisoformat(samples[0]['utc']), blq[name[:4]]['six_lines'], ctx.samples)
        sequence = []
        for t, sample, ocean_value in zip(ctx.times, samples, usw, strict=True):
            xyz = position('final_transport', t)
            tide = sum(solid.displacements(xyz, sample).values(), np.zeros(3))
            pole = loading.pole_ecef(xyz, datetime.fromisoformat(sample['utc']), sample['xp_arcsec'], sample['yp_arcsec'], '2018')
            sequence.append((xyz+tide+loading.ocean_ecef(ocean_value, xyz)+pole).tolist())
        positions[name] = sequence
    write(output/'positions.json', positions)
    deps = {p.relative_to(frame.ROOT).as_posix(): sha(p.read_bytes()) for folder in (BASE, frame.ROOT/'positioning') for p in folder.glob('*.py')}
    receipt = {'schema':'day-reference-input-v1', 'auxiliary_provenance':auxiliary, 'plan_sha256':PLAN_SHA, 'sources_sha256':deps,
               'observation_receipts':acquisition, 'station_model':'same final_transport+solid Earth+HARDISP CMC:NO+2018 pole recipe as PR150',
               'celestial_raw_sha256':{'de440s.bsp':celestial.KERNEL_SHA,'finals2000A.all':celestial.EOP_SHA},
               'hardisp_build':build, 'target_orbit_accessed':False,
               'files':{p.relative_to(output).as_posix():sha(p.read_bytes()) for p in output.rglob('*') if p.is_file()}}
    write(output/'receipt.json', receipt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work', 'products', 'celestial_raw', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    prepare(args.work, args.products, args.celestial_raw, args.output)
