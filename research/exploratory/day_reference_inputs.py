"""Authoritative input chain for the fixed distinct-day reference experiment."""
from pathlib import Path

from . import station_frame_epoch as frame
from . import ocean_pole_study as loading
from .erp_polar_bound import pinned, strict_json

BASE = Path(__file__).parent
PLAN_SHA = '4fdcd32196b126d9d3bcaf05201c2d817dcea3ae3c434a3ed9130f80859cd4ac'


def read_plan():
    return strict_json(pinned(BASE/'day_reference_plan.json',PLAN_SHA))


def load_basis(plan):
    if plan != read_plan():
        raise ValueError('plan differs from fixed distinct-day experiment')
    tag = plan['archive_tag']
    paths = frame.verified.paths(tag)
    admitted, ctx, _, _ = frame.verified.load_inputs(paths['admission_receipt'].parent)
    if (plan['date_gpst'] != ctx.date_gpst or plan['target_excluded'] != ctx.target or
            plan['stations'] != admitted['fit_stations'] or ctx.target in plan['references']):
        raise ValueError('plan and pinned admission differ')
    prior = strict_json(pinned(paths['attitude_report'],frame.verified.PINS[tag]['attitude_report']))
    expected = prior['input_sha256']
    files = {
        f'inputs/timed_reference_products/{tag}/receipt.json':'timed_receipt',
        f'inputs/timed_reference_products/{tag}/reference_orbit.txt':'orbit_extract',
        f'inputs/reference_attitudes/{tag}/receipt.json':'attitude_receipt',
        f'inputs/reference_biases/{tag}/receipt.json':'bias_receipt',
        f'inputs/reference_biases/{tag}/reference_bias.bia':'bias_extract',
        f'inputs/reference_antennas/{tag}/receipt.json':'antenna_receipt',
        f'inputs/reference_antennas/{tag}/reference_antenna.atx':'antenna_extract',
    }
    buffers = {name:pinned(BASE/name,expected[key]) for name,key in files.items()}
    timed = strict_json(buffers[f'inputs/timed_reference_products/{tag}/receipt.json'])
    attitude = strict_json(buffers[f'inputs/reference_attitudes/{tag}/receipt.json'])
    for value in (timed,attitude):
        if (value['date_gpst'] != ctx.date_gpst or value['target_excluded'] != ctx.target or
                value['references'] != plan['references']):
            raise ValueError('reference product cohort differs')
    frame_data, frame_hashes = frame.read_frame()
    _, blq, loading_hashes, _ = loading.read_loading(tag)
    station_sha = frame.verified.PINS[tag]['station_report']
    stations = strict_json(pinned(paths['station_report'],station_sha))
    if {s['station'] for s in stations['stations']} != set(plan['stations']):
        raise ValueError('station model cohort differs')
    auxiliary = {'reference_inputs':{name:expected[key] for name,key in files.items()},
                 'admitted':frame.verified.PINS[tag]['admitted'],
                 'admission_receipt':frame.verified.PINS[tag]['admission_receipt'],
                 'attitude_report':frame.verified.PINS[tag]['attitude_report'],
                 'frame':frame_hashes,'loading':loading_hashes,'station_report':station_sha}
    return admitted,timed,attitude,frame_data,blq,stations,auxiliary
