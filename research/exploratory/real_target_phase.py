"""Sparse G12 observation extract under real_target_phase_access.json.

This separate access boundary exists because the historical reference extractor
is hash-bound and explicitly refuses the target. It reuses the same header,
time, ionosphere-free and Hatanaka primitives without changing that extractor.
No target orbit or clock product is loaded.
"""
import argparse
import hashlib
import json
from pathlib import Path

import hatanaka
import numpy as np

from . import real_phase as reference
from ..kinematic import phase_transform_header_audit as header
from ..kinematic.rinex_observations import _time
from ..kinematic.doppler import ALPHA, BETA, F1_HZ, F2_HZ
from ..kinematic.receiver_time import C

BASE = Path(__file__).parent
ACCESS = BASE/'real_target_phase_access.json'
STATIONS = ('ALGO00CAN', 'DRAO00CAN', 'STJO00CAN', 'BRAZ00BRA', 'AREQ00PER')


def parse_target_fields(text, plan):
    """Only G12's four declared fields are numerically decoded in the hour."""
    lines = text.splitlines()
    end = next((i for i, line in enumerate(lines)
                if line[60:80].strip() == 'END OF HEADER'), None)
    if end is None:
        raise ValueError('missing header end')
    headers, types = header._collect_headers(lines[:end+1])

    def one(name):
        values = headers.get(name, [])
        if len(values) != 1:
            raise ValueError('missing/duplicate '+name)
        return values[0]

    version = one('RINEX VERSION / TYPE')
    if version[:9].strip() not in ('3.03', '3.04', '3.05') or version[20] != 'O' or version[40] not in 'GM':
        raise ValueError('unsupported observation format')
    if float(one('INTERVAL')) != plan['step_s'] or one('TIME OF FIRST OBS')[48:51] != 'GPS':
        raise ValueError('interval/time system differs')
    if headers.get('RCV CLOCK OFFS APPL', ['0'])[0].strip() != '0':
        raise ValueError('applied receiver clock correction')
    gps = types.get('G', [])
    if not set(reference.REQUIRED) <= set(gps):
        raise ValueError('required signal pair unavailable')
    scales = header._parse_scale_factors(headers.get('SYS / SCALE FACTOR', []), gps)
    shifts = header._parse_phase_shifts(headers.get('SYS / PHASE SHIFT', []))
    legacy = header._parse_legacy_wavelength(headers.get('WAVELENGTH FACT L1/2', []))
    if any(v != 1 for v in legacy['default_ambiguity_wavelength_divisor'].values()) or any(
            v != 1 for item in legacy['satellite_overrides'].values() for v in item.values()):
        raise ValueError('nonunit legacy wavelength factor unsupported')
    header._external_corrections(headers)
    first = _time(one('TIME OF FIRST OBS')[:43].split(), plan['date_gpst'], 0)
    start = plan['start_gpst_s']
    stop = start+(plan['samples']-1)*plan['step_s']
    rows, previous, seen = [], None, set()
    i = end+1
    while i < len(lines):
        line = lines[i]; i += 1
        if not line.startswith('>'):
            raise ValueError('expected epoch record')
        fields = line[1:].split()
        if len(fields) not in (8, 9):
            raise ValueError('invalid epoch record')
        t = _time(fields[:6], plan['date_gpst'], 0)
        if t > stop:
            break
        flag, count = int(fields[6]), int(fields[7])
        if flag != 0:
            raise ValueError('event/header change in scanned prefix')
        if count < 0 or i+count > len(lines) or (previous is not None and t <= previous):
            raise ValueError('truncated/unordered observation block')
        if previous is None and t != first:
            raise ValueError('first epoch/header mismatch')
        previous = t
        block = lines[i:i+count]; i += count
        if t < start:
            continue
        if (t-start) % plan['step_s']:
            raise ValueError('off-grid observation')
        for record in block:
            if record[:3] != plan['target_excluded']:
                continue
            if t in seen:
                raise ValueError('duplicate target observation')
            seen.add(t)
            values, lli, reasons = [], [], []
            for name in reference.REQUIRED:
                field = record[3+16*gps.index(name):3+16*(gps.index(name)+1)].ljust(16)
                try:
                    value = float(field[:14])/scales[name]
                except ValueError:
                    value = float('nan')
                if not np.isfinite(value) or value == 0 or (name.startswith('C') and value < 0):
                    reasons.append('MISSING_INVALID_'+name)
                values.append(float(value) if np.isfinite(value) else None)
                if name.startswith('L'):
                    lli.append(field[14])
                    if field[14] not in (' ', '0'):
                        reasons.append('LOSS_OF_LOCK_'+name)
            row = {'time_s': t, 'target': plan['target_excluded'], 'fields': values,
                   'lli': lli, 'status': 'AVAILABLE' if not reasons else 'REJECTED',
                   'reasons': reasons}
            if not reasons:
                c1, c2, l1, l2 = values
                row.update(code_m=ALPHA*c1+BETA*c2,
                           phase_m=ALPHA*C/F1_HZ*l1+BETA*C/F2_HZ*l2,
                           geometry_free_phase_m=C/F1_HZ*l1-C/F2_HZ*l2)
            rows.append(row)
    return {'version': version[:9].strip(), 'receiver': one('REC # / TYPE / VERS').strip(),
            'scales': scales, 'phase_shifts': shifts, 'legacy': legacy, 'rows': rows}


def extract(cache, output):
    access_bytes = ACCESS.read_bytes()
    access = json.loads(access_bytes)
    receipt_bytes = (BASE/'inputs/day_reference/receipt.json').read_bytes()
    if reference.digest(receipt_bytes) != access['source']['receipt_sha256']:
        raise ValueError('receipt differs from access record')
    if reference.digest((BASE/'inputs/real_phase/observations.json').read_bytes()) != access['source']['reference_phase_input_sha256']:
        raise ValueError('reference extract differs from access record')
    receipt = json.loads(receipt_bytes)
    plan = json.loads((BASE/'day_reference_plan.json').read_bytes())
    if (plan['target_excluded'] != access['source']['target'] or plan['date_gpst'] != access['source']['date_gpst']
            or list(STATIONS) != access['reference_phase_supported_before_target_access']):
        raise ValueError('target/station selection differs from access record')
    result = {'schema': 'exploratory-target-phase-input-v1',
              'access_sha256': reference.digest(access_bytes), 'target_state_accessed': False,
              'stations': {s: {'status': 'UNSUPPORTED_REFERENCE_PHASE'} for s in plan['stations'] if s not in STATIONS}}
    for station in STATIONS:
        source = receipt['observation_receipts'][station]
        raw = (cache/source['url'].split('/')[-1]).read_bytes()
        if reference.digest(raw) != source['sha256']:
            raise ValueError('cached observation hash mismatch: '+station)
        decoded = hatanaka.decompress(raw, strict=True)
        if reference.digest(decoded) != source['decoded_sha256']:
            raise ValueError('decoded observation hash mismatch: '+station)
        try:
            result['stations'][station] = {'status': 'PARSED', 'source': source,
                                           **parse_target_fields(decoded.decode('ascii'), plan)}
        except ValueError as error:
            result['stations'][station] = {'status': 'UNSUPPORTED', 'source': source,
                                           'reason': str(error), 'rows': []}
        print(station, result['stations'][station]['status'], flush=True)
    result['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n',
                      encoding='utf-8', newline='\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    extract(args.cache, args.output)
