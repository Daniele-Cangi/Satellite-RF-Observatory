"""Acquire one declared CODE final family, selecting references before parsing."""
import argparse
import gzip
import json
from pathlib import Path

from positioning.acquisition import download
from .day_reference_inputs import read_plan
from . import day_reference as baseline
from .reference_product_discrepancy import extract_references
from .precise_reference_model import extract_clock
from .reference_code_bias import extract_bias
from .reference_attitude_model import extract_attitude
from .prepare_day_reference import write, sha

BASE = Path(__file__).parent


def prepare(work, output):
    raw_plan = (BASE/'final_reference_plan.json').read_bytes()
    plan = json.loads(raw_plan)
    day = read_plan()
    baseline.inputs()
    if sha((BASE/'day_reference_plan.json').read_bytes()) != plan['baseline_plan_sha256']:
        raise ValueError('baseline plan differs')
    # No numeric target state is parsed, including from the downloaded mixed archives.
    refs, target, date = day['references'], day['target_excluded'], day['date_gpst']
    start, end = plan['window_gpst_s']
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=False)
    sources = {str(p.relative_to(BASE.parents[1])).replace('\\','/'):sha(p.read_bytes())
               for directory in (BASE, BASE.parents[1]/'positioning')
               for p in sorted(directory.glob('*.py'))}
    receipt = {'schema':'final-reference-inputs-v1','plan_sha256':sha(raw_plan),
               'sources_sha256':sources,'products':{},'files':{},'failures':[]}
    for kind, name in plan['files'].items():
        try:
            raw, acquisition = download(plan['source_base']+name)
            write(work/name,raw)
            decoded = gzip.decompress(raw).decode('ascii')
            if kind == 'orbit':
                selected = extract_references(decoded,refs,target)
            elif kind == 'clock':
                selected = extract_clock(decoded,refs,target,date,start,end)
            elif kind == 'bias':
                selected = extract_bias(decoded,refs,target)
            elif kind == 'attitude':
                selected = extract_attitude(decoded,refs,target,date,start,end)
            else:
                selected = decoded  # Earth orientation, no satellite states.
            data = selected.encode('ascii')
            write(output/(kind+'.txt'),data)
            receipt['products'][kind] = acquisition | {'decoded_sha256':sha(decoded.encode('ascii'))}
            receipt['files'][kind+'.txt'] = sha(data)
        except Exception as error:
            receipt['failures'].append({'product':kind,'error':type(error).__name__+': '+str(error)})
            break
    write(output/'receipt.json',receipt)
    print(json.dumps({'files':receipt['files'],'failures':receipt['failures']},indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    prepare(args.work,args.output)
