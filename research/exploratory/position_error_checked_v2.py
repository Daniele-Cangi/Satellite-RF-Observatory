"""Check frozen additive-error transport sources before execution."""
import argparse
import json
from . import position_error_transfer_v2 as study
from .erp_polar_bound import pinned

PLAN_SHA = '7080b3146512ee231486fe637f9c876e32c0ea96c127eeffb6526fe3729758ed'
SOURCES = {'research/exploratory/position_error_transfer_v2.py': 'e24581e4e3450869902ff388aef2f4639bd59087095e7e9f9b95ea50f3a3cdf5', 'research/exploratory/reference_residual_structure_v2.py': 'b003f35a71ac0ac14705876dcef621f03c8ec07ec9f4ecf033ecc731f197fd0d', 'research/exploratory/erp_polar_bound.py': 'ec93926220d34042d20c4e89592d2095ecabc5dc205369f7dbf4ffffc6a8c9a5', 'research/kinematic/receiver_time.py': '1228526c60d61fecb7576c0adc7ad6a0c6eda81a580dee455a8b4ad92da1b3c5'}


def run(progress=None):
    for name,digest in SOURCES.items():
        pinned(study.BASE.parents[1]/name,digest)
    return study.run(PLAN_SHA,progress)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=study.Path)
    args=parser.parse_args()
    result=run(lambda value:print(json.dumps(value),flush=True))
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
