"""Check verifier bytes independently before importing the frozen RF analysis."""
import argparse
import hashlib
import json
from pathlib import Path

PLAN_SHA = 'f50e887a78e9ad1f897ea00141e784761d3cdb60d2c4245c8df2a2746cdb8cd8'
SOURCES = {'research/exploratory/pseudotarget_reference.py': '24bd496c7d8f64b93af24f8df6a24553621da2a9c0abcf67b249f580a2dfb23a', 'research/exploratory/pseudotarget_statistics.py': '5ac481f2c8646e8b3f4f71dd478d87347a164870d97d20ac4412fadbe8bef7af', 'research/exploratory/day_reference_checked.py': 'f5f087d3fef0e326e5eedecb54604ec030d3e4cf97367b93f44574b123b23c06', 'research/exploratory/day_reference.py': 'bc96b7ab08ee058ee47ce4f134e09074b9064b6d6a4287648cc4315c8fa99dea', 'research/exploratory/erp_polar_bound.py': 'ec93926220d34042d20c4e89592d2095ecabc5dc205369f7dbf4ffffc6a8c9a5'}
ROOT = Path(__file__).resolve().parents[2]


def verify_sources():
    for name, digest in SOURCES.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
            raise ValueError('source hash mismatch: '+name)


def run(progress=None):
    verify_sources()
    from . import pseudotarget_reference as study
    return study.run(PLAN_SHA, progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run(lambda item: print(json.dumps(item), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as output:
        output.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
