"""Preflight provenance for the fixed 2026-09-03 arc producer; not a generic CLI."""
import argparse
from datetime import datetime
from pathlib import Path

from . import arc_reference as study
from . import prepare_arc_reference as frozen


def preflight():
    plan, _, _, _, receipt = study.inputs()
    day = datetime.fromisoformat(plan['date_gpst'])
    if (day-datetime(1858,11,17)).days != 61286 or plan['target_excluded'] != 'G14':
        raise ValueError('this frozen producer and weather model support only G14 on 2026-09-03')
    paths = study.frame.verified.paths('g14')
    admitted, _, _, _ = study.frame.verified.load_inputs(paths['admission_receipt'].parent)
    authoritative = {r['station']: r for r in admitted['observation_receipts']}
    for name in plan['stations']:
        filename = name+'_R_'+day.strftime('%Y%j')+'0000_01D_30S_MO.crx.gz'
        sidecar = study.strict_json((paths['admission_receipt'].parent/'raw_observations'/(filename+'.json')).read_bytes())
        expected = authoritative[name]
        for key in ('url','bytes','sha256','access_utc','http_status'):
            if sidecar.get(key) != expected[key] or receipt['observation_receipts'][name].get(key) != expected[key]:
                raise ValueError('observation sidecar differs from pinned admission: '+name)
        if receipt['observation_receipts'][name]['decoded_sha256'] != expected['decoded_sha256']:
            raise ValueError('decoded observation differs from pinned admission: '+name)
    prior = study.strict_json(study.pinned(paths['attitude_report'],study.frame.verified.PINS['g14']['attitude_report']))
    hashes = prior['input_sha256']
    for name,key in (
        ('timed_reference_products/g14/receipt.json','timed_receipt'),
        ('timed_reference_products/g14/reference_orbit.txt','orbit_extract'),
        ('reference_attitudes/g14/receipt.json','attitude_receipt'),
    ):
        study.pinned(study.BASE/'inputs'/name,hashes[key])
    study.pinned(study.INPUTS/'timed/reference_orbit.txt',hashes['orbit_extract'])


def prepare(work,products,celestial_raw,output):
    preflight()
    return frozen.prepare(work,products,celestial_raw,output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('work','products','celestial_raw','output'):
        parser.add_argument(name,type=Path)
    args = parser.parse_args()
    prepare(args.work,args.products,args.celestial_raw,args.output)
