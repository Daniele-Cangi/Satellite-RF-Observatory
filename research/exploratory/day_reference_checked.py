"""Check the separately frozen analysis source before the unchanged day replay."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from . import day_reference as study
from .day_reference_inputs import load_basis
from .reference_product_discrepancy import extract_references

RUNNER_SHA = 'bc96b7ab08ee058ee47ce4f134e09074b9064b6d6a4287648cc4315c8fa99dea'


def run(progress=None):
    study.pinned(Path(study.__file__),RUNNER_SHA)
    return study.run(progress)


def audit_retained_sources(products,celestial):
    """Post-execution derivation check; does not reconstruct concurrent file changes."""
    study.pinned(Path(study.__file__),RUNNER_SHA)
    plan,_,_,_,receipt = study.inputs()
    _,timed,_,_,_,_,_ = load_basis(plan)
    orbit = timed['orbit']
    raw = study.pinned(products/orbit['source_url'].split('/')[-1],orbit['source_compressed_sha256'])
    derived = extract_references(gzip.decompress(raw).decode('ascii'),plan['references'],plan['target_excluded']).encode('ascii')
    expected = study.pinned(study.INPUTS/'timed/reference_orbit.txt',orbit['extract_sha256'])
    if derived != expected:
        raise ValueError('restricted orbit does not derive from pinned archive')
    for name,digest in receipt['celestial_raw_sha256'].items():
        study.pinned(celestial/name,digest)
    return {'schema':'day-reference-retained-source-audit-v1','after_execution':True,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'runner_sha256':RUNNER_SHA,'input_receipt_sha256':study.RECEIPT_SHA,
            'orbit_archive_sha256':orbit['source_compressed_sha256'],
            'rederived_orbit_sha256':hashlib.sha256(derived).hexdigest(),
            'rederived_orbit_matches':True,'retained_celestial_sha256':receipt['celestial_raw_sha256'],
            'scope':'Direct orbit derivation and retained celestial bytes; not retrospective proof of concurrent file immutability.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    result = run(lambda value: print(json.dumps(value),flush=True))
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
