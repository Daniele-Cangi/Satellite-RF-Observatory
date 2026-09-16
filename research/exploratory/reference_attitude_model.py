"""Restricted CODE ORBEX attitudes and complete IF PCO, not code PCV calibration."""
from functools import lru_cache
import json
from pathlib import Path
import hashlib

import numpy as np
from scipy.spatial.transform import Rotation, Slerp

from positioning.calibration import C, OMEGA, rotate_z, troposphere
from .precise_reference_model import time_of
from .reference_conventions import extract_antex, label
from .reference_time_alignment import load_products


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON number: '+value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid,
                      parse_float=lambda s: finite_float(s))


def finite_float(value):
    number = float(value)
    if not np.isfinite(number):
        raise ValueError('nonfinite JSON number')
    return number


def validate_pair(clock_text, antenna_text, refs, target, day, start, end):
    header = clock_text.split('END OF HEADER', 1)[0].splitlines()
    dcbs = [s[:60].split() for s in header if s[60:].strip() == 'SYS / DCBS APPLIED' and s.startswith('G')]
    if len(dcbs) != 1 or dcbs[0][3:] != ['CODE.BIA', '@', 'ftp.aiub.unibe.ch/CODE/']:
        raise ValueError('paired GPS CODE.BIA clock convention required')
    if extract_antex(antenna_text, refs, target) != antenna_text:
        raise ValueError('unadmitted antenna data')
    # Check every boundary, including a change-and-change-back inside the window.
    for line in antenna_text.splitlines():
        if label(line) in ('VALID FROM', 'VALID UNTIL'):
            boundary = time_of(line[:60].split(), day)
            if start <= boundary <= end:
                raise ValueError('antenna validity boundary crosses evaluation window')


def guarded_products(context, refs, timed, biases, antennas):
    paths = {'timed_receipt': Path(timed)/'receipt.json',
             'bias_receipt': Path(biases)/'receipt.json',
             'antenna_receipt': Path(antennas)/'receipt.json',
             'clock_extract': Path(timed)/'reference_clock.txt',
             'antenna_extract': Path(antennas)/'reference_antenna.atx'}
    buffers = {key: p.read_bytes() for key, p in paths.items()}
    for key in ('timed_receipt', 'bias_receipt', 'antenna_receipt'):
        strict_json(buffers[key])
    receipt = strict_json(buffers['timed_receipt'])
    validate_pair(buffers['clock_extract'].decode('ascii'), buffers['antenna_extract'].decode('ascii'),
                  refs, context.target, context.date_gpst, *receipt['clock_window_gpst_s'])
    provider, corrections, hashes = load_products(context, refs, timed, biases, antennas)
    if any(hashes[key] != hashlib.sha256(value).hexdigest() for key, value in buffers.items()):
        raise ValueError('product changed between validation and loading')
    return provider, corrections, hashes


def extract_attitude(text, references, target, day, start, end):
    """Restrict IDs before reading quaternion values; rewrite counts/window explicitly."""
    if target in references or not references or len(set(references)) != len(references):
        raise ValueError('invalid attitude allowlist')
    if not 0 <= start < end <= 86400 or start % 30 or end % 30:
        raise ValueError('invalid attitude window')
    lines = text.splitlines()
    if lines[:2] != ['%=ORBEX  0.09', '%%'] or lines[-2:] != ['-EPHEMERIS/DATA', '%END_ORBEX']:
        raise ValueError('complete CODE ORBEX 0.09 required')
    desc_end = lines.index('-FILE/DESCRIPTION')
    if lines[2] != '+FILE/DESCRIPTION' or lines[desc_end+1] != '+SATELLITE/ID_AND_DESCRIPTION':
        raise ValueError('unsupported ORBEX block structure')
    ids_end = lines.index('-SATELLITE/ID_AND_DESCRIPTION')
    if lines[ids_end+1] != '+EPHEMERIS/DATA':
        raise ValueError('unsupported optional ORBEX blocks')
    identities = [s.strip() for s in lines[desc_end+2:ids_end]]
    if len(identities) != len(set(identities)) or not set(references) <= set(identities):
        raise ValueError('missing/duplicate ORBEX satellite identity')
    desc = {}
    for line in lines[3:desc_end]:
        key, value = line[:20].strip(), line[20:].strip()
        if key in desc:
            raise ValueError('duplicate ORBEX description')
        desc[key] = value
    for key, value in {'TIME_SYSTEM': 'GPS', 'FRAME_TYPE': 'ECEF', 'COORD_SYSTEM': 'IGC20',
                       'CREATED_BY': 'CODE IGS-AC', 'LIST_OF_REC_TYPES': 'ATT'}.items():
        if desc.get(key) != value:
            raise ValueError('unsupported ORBEX convention: '+key)
    if float(desc['EPOCH_INTERVAL']) != 30.:
        raise ValueError('native 30-second attitude required')
    if not time_of(desc['START_TIME'].split(), day) <= start < end <= time_of(desc['END_TIME'].split(), day):
        raise ValueError('attitude outside source window')
    if '*ATT RECORDS: ECEF --> SAT. BODY FRAME' not in lines:
        raise ValueError('explicit ECEF-to-body direction required')
    selected, epoch, rows, expected, last = [], None, [], None, None
    def flush():
        if epoch is None:
            return
        if len(rows) != expected or len({s[5:8] for s in rows}) != len(rows):
            raise ValueError('attitude epoch count/duplicate differs')
        if start <= epoch <= end:
            keep = [s for s in rows if s[5:8] in references and s[5:8] != target]
            # Numeric quaternion conversion happens later, on restricted records only.
            selected.append((epoch_line, keep))
    for line in lines[ids_end+2:-2]:
        if line.startswith('*') or not line.strip():
            continue
        if line.startswith('## '):
            flush()
            fields = line.split()
            epoch = time_of(fields[1:7], day)
            if (last is not None and epoch <= last) or epoch % 30:
                raise ValueError('unordered/off-grid attitude epoch')
            last, expected, rows, epoch_line = epoch, int(fields[7]), [], line
        elif line.startswith(' ATT ') and epoch is not None:
            rows.append(line)
        else:
            raise ValueError('unsupported attitude record')
    flush()
    if not selected:
        raise ValueError('empty attitude window')
    header = lines[:desc_end+1]
    for key, line_index in [('START_TIME', 0), ('END_TIME', -1)]:
        value = ' '.join(selected[line_index][0].split()[1:7])
        header = [f' {key:<19} {value}' if s[:20].strip() == key else s for s in header]
    result = header+['+SATELLITE/ID_AND_DESCRIPTION']+[' '+sv for sv in references]
    result += ['-SATELLITE/ID_AND_DESCRIPTION', '+EPHEMERIS/DATA', '*ATT RECORDS: ECEF --> SAT. BODY FRAME']
    for epoch_line, rows in selected:
        result.append(' '.join(epoch_line.split()[:7])+f' {len(rows)}')
        result.extend(rows)
    return '\n'.join(result+['-EPHEMERIS/DATA', '%END_ORBEX'])+'\n'


def parse_attitude(text, refs, target, day, start, end):
    if extract_attitude(text, refs, target, day, start, end) != text:
        raise ValueError('unadmitted or noncanonical attitude extract')
    result, t = {sv: {} for sv in refs}, None
    for line in text.splitlines():
        if line.startswith('## '):
            t = time_of(line.split()[1:7], day)
        elif line.startswith(' ATT '):
            if line[8:22].strip() or line[22:23] != '4':
                raise ValueError('unsupported attitude fields')
            q = np.array([float(s) for s in line[23:].split()])
            if q.shape != (4,) or not np.isfinite(q).all() or abs(np.linalg.norm(q)-1.) > 1e-10:
                raise ValueError('invalid unit attitude quaternion')
            result[line[5:8]][t] = (q/np.linalg.norm(q)).tolist()
    return result


class Attitude:
    def __init__(self, samples, target):
        if target in samples:
            raise ValueError('target attitude is forbidden')
        self.samples, self.target = samples, target

    @lru_cache(maxsize=8192)
    def body_to_ecef(self, sv, t, step=30):
        if sv == self.target or sv not in self.samples or step not in (30, 60) or not np.isfinite(t):
            raise ValueError('invalid attitude request')
        samples = self.samples[sv]
        left = step*np.floor(t/step)
        if t == left and left in samples:
            rotation = Rotation.from_quat(samples[left], scalar_first=True)
        else:
            right = left+step
            if left not in samples or right not in samples:
                raise ValueError('attitude gap or extrapolation')
            knots = Rotation.from_quat([samples[left], samples[right]], scalar_first=True)
            # Shortest-arc SLERP is invariant under the q / -q representation.
            rotation = Slerp([0., float(step)], knots)(t-left)
        # CODE explicitly supplies ECEF -> body. PCO needs the inverse mapping.
        return rotation.as_matrix().T


class AttitudeReference:
    def __init__(self, precise, attitude, step=30, z_only=False):
        self.precise, self.attitude, self.step, self.z_only = precise, attitude, step, z_only

    @lru_cache(maxsize=16384)
    def antenna_state(self, sv, code, t):
        tx, clock, com, radial, closure, offset = self.precise.emitted_state(sv, code, t)
        rotation = self.attitude.body_to_ecef(sv, tx, self.step)
        pco = np.array(self.precise.offsets[sv]['if_pco_body_m'])
        if self.z_only:
            pco[:2] = 0.
        return tx, clock, com+rotation@pco, offset

    def model(self, sv, code, t, station, receiver_clock):
        _, clock, satellite, offset = self.antenna_state(sv, code, t)
        tau = -receiver_clock/C-offset
        if not 0 < tau < 1:
            raise ValueError('invalid reception/emission interval')
        rotated = rotate_z(satellite, -OMEGA*tau)
        trop, elevation = troposphere(station, rotated)
        return float(np.linalg.norm(rotated-station)-C*clock+trop), float(elevation)
