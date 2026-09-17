"""Frozen entry point for the exposed-reference receiver-transfer experiment."""
import argparse
import json
from pathlib import Path
from . import spatial_reference as study
from .erp_polar_bound import pinned

PLAN_SHA = '4022c729d06798758c9159fdd0ec7bb54f9e27c6c8a9ed518966bbf2912eb596'
SOURCES = {'spatial_reference.py': '10469f6fb833d0125e046894469babb92b72a4dac31fbaa7869f1d7664e3c12d', 'reference_residual_structure_v2.py': 'b003f35a71ac0ac14705876dcef621f03c8ec07ec9f4ecf033ecc731f197fd0d', 'erp_polar_bound.py': 'ec93926220d34042d20c4e89592d2095ecabc5dc205369f7dbf4ffffc6a8c9a5'}


def run(progress=None):
    for name,digest in SOURCES.items():
        pinned(Path(__file__).parent/name,digest)
    return study.run(PLAN_SHA,progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    result = run(lambda value:print(json.dumps(value),flush=True))
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
