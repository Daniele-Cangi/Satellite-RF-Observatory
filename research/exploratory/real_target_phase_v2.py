"""GPS-only BOGT header admission for the separately declared exploratory v2."""
import argparse
import hashlib
import json
from pathlib import Path

import hatanaka

from . import real_phase as reference
from . import real_target_phase as target

BASE = Path(__file__).parent
ACCESS = BASE/'real_target_phase_access_v2.json'


def gps_only_phase_header(text):
    """Discard unused non-GPS phase-shift declarations, not GPS or body bytes."""
    retained = []
    current = None
    in_header = True
    for line in text.splitlines(keepends=True):
        label = line[60:80].strip() if in_header else ''
        if label == 'SYS / PHASE SHIFT':
            if line[:1].strip():
                current = line[0]
            if current is None:
                raise ValueError('orphan phase-shift continuation')
            if current != 'G':
                continue
        retained.append(line)
        if label == 'END OF HEADER':
            in_header = False
    if in_header:
        raise ValueError('missing end of header')
    return ''.join(retained)


def extract(cache, target_output, reference_output):
    access_bytes = ACCESS.read_bytes()
    access = json.loads(access_bytes)
    prior_target_bytes = (BASE/'inputs/real_phase/g12_target_phase.json').read_bytes()
    prior_reference_bytes = (BASE/'inputs/real_phase/observations.json').read_bytes()
    receipt_bytes = (BASE/'inputs/day_reference/receipt.json').read_bytes()
    if (reference.digest(prior_target_bytes) != access['previous_target_extract_sha256']
            or reference.digest(prior_reference_bytes) != access['previous_reference_extract_sha256']
            or reference.digest(receipt_bytes) != access['receipt_sha256']):
        raise ValueError('v2 inputs differ from access record')
    receipt = json.loads(receipt_bytes)
    source = receipt['observation_receipts']['BOGT00COL']
    raw = (cache/source['url'].split('/')[-1]).read_bytes()
    if reference.digest(raw) != source['sha256']:
        raise ValueError('BOGT compressed hash mismatch')
    decoded = hatanaka.decompress(raw, strict=True)
    if reference.digest(decoded) != source['decoded_sha256']:
        raise ValueError('BOGT decoded hash mismatch')
    original = decoded.decode('ascii')
    gps_only = gps_only_phase_header(original)
    plan = json.loads((BASE/'day_reference_plan.json').read_bytes())
    parsed_references = reference.parse_reference_fields(gps_only, plan)
    parsed_target = target.parse_target_fields(gps_only, plan)
    if plan['target_excluded'] != access['target'] or plan['date_gpst'] != access['date_gpst']:
        raise ValueError('target/epoch differs from access record')
    target_input = json.loads(prior_target_bytes)
    reference_input = json.loads(prior_reference_bytes)
    if target_input['stations']['BOGT00COL']['status'] != 'UNSUPPORTED_REFERENCE_PHASE' or reference_input['cohorts']['day']['stations']['BOGT00COL']['status'] != 'UNSUPPORTED':
        raise ValueError('BOGT was previously admitted')
    target_input.update(schema='exploratory-target-phase-input-v2',
                        access_sha256=reference.digest(access_bytes),
                        previous_target_input_sha256=reference.digest(prior_target_bytes),
                        gps_only_header_adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    target_input['stations']['BOGT00COL'] = {'status': 'PARSED', 'source': source,
                                            'header_adapter': 'GPS_PHASE_SHIFT_ONLY', **parsed_target}
    reference_input.update(schema='real-reference-phase-input-gps-only-bogt-v2',
                           previous_reference_input_sha256=reference.digest(prior_reference_bytes),
                           access_sha256=reference.digest(access_bytes))
    reference_input['cohorts']['day']['stations']['BOGT00COL'] = {
        'status': 'PARSED', 'source': source, 'header_adapter': 'GPS_PHASE_SHIFT_ONLY',
        **parsed_references}
    for output, item in ((target_output, target_input), (reference_output, reference_input)):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(item, separators=(',', ':'), allow_nan=False)+'\n',
                          encoding='utf-8', newline='\n')
    return {'BOGT_target_rows': len(parsed_target['rows']),
            'BOGT_reference_rows': len(parsed_references['rows'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--target-output', required=True, type=Path)
    parser.add_argument('--reference-output', required=True, type=Path)
    args = parser.parse_args()
    print(extract(args.cache, args.target_output, args.reference_output))
