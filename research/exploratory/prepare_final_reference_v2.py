"""Continue the same product selection with native clock 3.04 support."""
import argparse
import gzip
from datetime import datetime, timezone
from pathlib import Path
from positioning.acquisition import download
from . import prepare_final_reference as first
from .final_reference_clock import extract_clock
from .erp_polar_bound import pinned, strict_json

PLAN_SHA = '70a3a0306b8398ee02d88ee0ac584387ae40fb9a1594ca9382899d914864aa34'
RETAINED = {'orbit':'ffdf5305d45ed22a38cd1acd7bebf5c0e8e991dbb01aff5606c0ccef25043056',
            'clock':'28d9b276563af8aaa01a29a25133491067e08917778a0c9eb91ebfd1bb83ec8c'}


def prepare(work,output):
    plan = strict_json(pinned(first.BASE/'final_reference_plan_v2.json',PLAN_SHA))
    day = first.read_plan()
    first.baseline.inputs()
    refs,target,date = day['references'],day['target_excluded'],day['date_gpst']
    start,end = plan['window_gpst_s']
    output.mkdir(parents=True,exist_ok=False)
    sources = {p.relative_to(first.BASE.parents[1]).as_posix():first.sha(p.read_bytes())
               for directory in (first.BASE,first.BASE.parents[1]/'positioning')
               for p in sorted(directory.glob('*.py'))}
    receipt = {'schema':'final-reference-inputs-v2','plan_sha256':PLAN_SHA,
               'sources_sha256':sources,'products':{},'files':{},'failures':[]}
    for kind,name in plan['files'].items():
        try:
            url = plan['source_base']+name
            if kind in RETAINED:
                raw = pinned(work/name,RETAINED[kind])
                acquisition = {'url':url,'sha256':first.sha(raw),'bytes':len(raw),
                               'origin':'retained v1 download; local verification, not a new HTTP request',
                               'verified_utc':datetime.now(timezone.utc).isoformat()}
            else:
                raw,acquisition = download(url)
                first.write(work/name,raw)
            receipt['products'][kind] = acquisition
            decoded = gzip.decompress(raw).decode('ascii')
            receipt['products'][kind]['decoded_sha256'] = first.sha(decoded.encode('ascii'))
            if kind == 'orbit':
                selected = first.extract_references(decoded,refs,target)
            elif kind == 'clock':
                selected = extract_clock(decoded,refs,target,date,start,end)
            elif kind == 'bias':
                selected = first.extract_bias(decoded,refs,target)
            elif kind == 'attitude':
                selected = first.extract_attitude(decoded,refs,target,date,start,end)
            else:
                selected = decoded
            data = selected.encode('ascii')
            first.write(output/(kind+'.txt'),data)
            receipt['files'][kind+'.txt'] = first.sha(data)
        except Exception as error:
            receipt['failures'].append({'product':kind,'error':type(error).__name__+': '+str(error)})
            break
    first.write(output/'receipt.json',receipt)
    print(first.json.dumps({'files':receipt['files'],'failures':receipt['failures']},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    prepare(args.work,args.output)
