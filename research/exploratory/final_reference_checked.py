"""Verify frozen comparison implementation before loading RF or product states."""
import argparse
import json
from pathlib import Path
from .erp_polar_bound import pinned
from . import final_reference as study

SOURCES = {'final_reference.py': '30c43e5126521186d64e9965f2e3bcd6a7d864b998bb4101796921988ace4e00', 'final_reference_products.py': 'a61a6f3f45f99cf5c1949a989381c9642cfc8eb13507bb24d1e820925e54d020'}


def run(progress=None):
    for name,digest in SOURCES.items():
        pinned(Path(__file__).parent/name,digest)
    return study.run(progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    result = run(lambda value:print(json.dumps(value),flush=True))
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
