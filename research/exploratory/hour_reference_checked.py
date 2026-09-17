"""Verify auxiliary provenance before replaying the unchanged frozen v2 study."""
import argparse
import json
from pathlib import Path

from . import hour_reference_v2 as study
from . import ocean_pole_study as loading


AUXILIARY = {
    'inputs/reference_biases/g14/receipt.json': '3b046196eac4df4d41d1031cfbf38a451c7820d8fba83018d835205532cf25eb',
    'inputs/reference_biases/g14/reference_bias.bia': 'e7ceb3755416a060fd69f3f3f5e52f40f668253715346be5d8bc23bcb451478a',
    'inputs/reference_antennas/g14/receipt.json': 'b64ad15f1f08e0baccab18880b1b688e1bedb10daed72bf1bec729ab72456674',
    'inputs/reference_antennas/g14/reference_antenna.atx': '35ea3174f31acb3da95ffa487832f366ec830bbd63fe7906e5db2827b31fd47d',
}


def validate_auxiliary():
    # Validate frozen source bindings first, including the loaders and their pins.
    study.inputs()
    for name, digest in AUXILIARY.items():
        study.pinned(study.BASE/name, digest)
    # These loaders already pin their root receipts and all dependent artifacts.
    _, frame_hashes = study.frame.read_frame()
    _, _, loading_hashes, _ = loading.read_loading('g14')
    station_sha = study.frame.verified.PINS['g14']['station_report']
    study.pinned(study.frame.verified.paths('g14')['station_report'], station_sha)
    return {'auxiliary': AUXILIARY.copy(), 'frame': frame_hashes,
            'loading': loading_hashes, 'station_report': station_sha}


def run(progress=None):
    validate_auxiliary()
    return study.run(progress)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = run(lambda value: print(json.dumps(value), flush=True))
    with args.output.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
