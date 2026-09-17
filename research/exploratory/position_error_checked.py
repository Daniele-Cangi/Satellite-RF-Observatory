"""Check frozen additive-error transport sources before execution."""
import argparse
import json
from . import position_error_transfer as study
from .erp_polar_bound import pinned

PLAN_SHA = '64d904e3566c0b1668f260db690c216092430b13b86e9da03828d8a00293586e'
SOURCES = {'research/exploratory/position_error_transfer.py': 'fb311a0ceae1ca08da97e03af2effda8f68896386008fac6c7c6d1da3a9bf70e', 'research/exploratory/reference_residual_structure_v2.py': 'b003f35a71ac0ac14705876dcef621f03c8ec07ec9f4ecf033ecc731f197fd0d', 'research/exploratory/erp_polar_bound.py': 'ec93926220d34042d20c4e89592d2095ecabc5dc205369f7dbf4ffffc6a8c9a5', 'research/kinematic/receiver_time.py': '1228526c60d61fecb7576c0adc7ad6a0c6eda81a580dee455a8b4ad92da1b3c5'}


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
