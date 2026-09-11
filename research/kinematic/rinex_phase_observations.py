"""Bounded GPS RINEX code/phase importer; no Doppler substitution.

Header checks are specialized from the immutable S2b parser, changing only
required signals. The earlier parser and its scientific receipts stay intact.
"""
import hashlib
import json
import re

import numpy as np

from positioning.calibration import antenna_position
from .doppler import ALPHA, BETA
from .inverse_uncertainty import validate_covariance
from .phase_rates import reference_phase_rates
from .rinex_observations import GPS, METADATA, RinexRejected, _time

REQUIRED = ('C1C', 'C2W', 'L1C', 'L2W')


def _phase_header(lines, base_day, base_second, step_s):
    headers, systems, pending = {}, {}, None
    if not lines or lines[0][60:80].strip() != 'RINEX VERSION / TYPE':
        raise RinexRejected('MISSING_RINEX_VERSION')
    if not any(line[60:80].strip() == 'END OF HEADER' for line in lines):
        raise RinexRejected('MISSING_END_OF_HEADER')
    for index, line in enumerate(lines):
        label, value = line[60:80].strip(), line[:60]
        if label not in METADATA:
            raise RinexRejected('UNQUALIFIED_HEADER:'+label)
        headers.setdefault(label, []).append(value)
        if label == 'SYS / # / OBS TYPES':
            system = value[:1]
            if system.strip():
                if pending is not None and len(systems[pending]['types']) != systems[pending]['count']:
                    raise RinexRejected('INCOMPLETE_OBSERVATION_TYPES')
                if system not in 'GRECSJI' or system in systems:
                    raise RinexRejected('DUPLICATE_OR_UNKNOWN_SYSTEM')
                try:
                    count = int(value[3:6])
                except ValueError as error:
                    raise RinexRejected('INVALID_OBSERVATION_COUNT') from error
                if not 1 <= count <= 99:
                    raise RinexRejected('INVALID_OBSERVATION_COUNT')
                systems[system] = {'count': count, 'types': []}
                pending = system
            elif pending is None or value[:7].strip():
                raise RinexRejected('ORPHAN_OBSERVATION_CONTINUATION')
            types = value[7:60].split()
            if any(not re.fullmatch(r'[CLDS][1-9][A-Z]', name) for name in types):
                raise RinexRejected('INVALID_OBSERVATION_TYPE')
            systems[pending]['types'].extend(types)
        elif label == 'END OF HEADER':
            break
    else:
        raise RinexRejected('MISSING_END_OF_HEADER')
    for system in systems.values():
        if len(system['types']) != system['count'] or len(set(system['types'])) != system['count']:
            raise RinexRejected('INCOMPLETE_OR_DUPLICATE_OBSERVATION_TYPES')
    mandatory = ('RINEX VERSION / TYPE', 'MARKER NAME', 'MARKER TYPE',
                 'REC # / TYPE / VERS', 'ANT # / TYPE', 'APPROX POSITION XYZ',
                 'ANTENNA: DELTA H/E/N', 'INTERVAL', 'TIME OF FIRST OBS')
    for label in mandatory:
        if len(headers.get(label, [])) != 1:
            raise RinexRejected('MISSING_OR_DUPLICATE_HEADER:'+label)
    for label in ('RCV CLOCK OFFS APPL', 'TIME OF LAST OBS'):
        if len(headers.get(label, [])) > 1:
            raise RinexRejected('DUPLICATE_HEADER:'+label)
    version = headers['RINEX VERSION / TYPE'][0]
    if version[:9].strip() not in ('3.04', '3.05') or version[20:21] != 'O' or version[40:41] not in ('G', 'M'):
        raise RinexRejected('UNSUPPORTED_OBSERVATION_FORMAT')
    if headers['MARKER TYPE'][0].strip() != 'GEODETIC':
        raise RinexRejected('NON_GEODETIC_RECEIVER')
    if headers.get('RCV CLOCK OFFS APPL', ['0'])[0].strip() != '0':
        raise RinexRejected('APPLIED_RECEIVER_CLOCK_CORRECTION')
    try:
        interval = float(headers['INTERVAL'][0])
    except ValueError as error:
        raise RinexRejected('INVALID_INTERVAL') from error
    if not np.isfinite(interval) or abs(interval-step_s) > 1e-7:
        raise RinexRejected('INTERVAL_DIFFERS_FROM_PLAN')
    first = headers['TIME OF FIRST OBS'][0]
    if first[48:51] != 'GPS':
        raise RinexRejected('NON_GPST_TIME_SYSTEM')
    if 'TIME OF LAST OBS' in headers and headers['TIME OF LAST OBS'][0][48:51] != 'GPS':
        raise RinexRejected('NON_GPST_TIME_SYSTEM')
    first_time = _time(first[:43].split(), base_day, base_second)
    gps_types = systems.get('G', {}).get('types', [])
    if not all(name in gps_types for name in REQUIRED):
        raise RinexRejected('MISSING_REQUIRED_GPS_SIGNALS')
    receiver = headers['REC # / TYPE / VERS'][0].ljust(60)
    identity = [receiver[i:i+20].strip() for i in (0, 20, 40)]
    if not all(identity):
        raise RinexRejected('INCOMPLETE_RECEIVER_IDENTITY')
    try:
        for label in ('APPROX POSITION XYZ', 'ANTENNA: DELTA H/E/N'):
            vector = np.array(headers[label][0].split(), dtype=float)
            if vector.shape != (3,) or not np.isfinite(vector).all():
                raise ValueError('bad station vector')
        station = antenna_position(headers)
        if not np.isfinite(station).all():
            raise ValueError('bad antenna coordinates')
    except (ValueError, ZeroDivisionError) as error:
        raise RinexRejected('INVALID_STATION_COORDINATES') from error
    return index+1, headers, systems, first_time, identity, station


def parse_reference_phase_file(content, *, target, references, tags_s, step_s,
                               base_day, base_second, raw_covariance):
    """Raw covariance order: endpoint/reference/[C1C,C2W,L1C,L2W].

    Planned tags are ALL interval endpoints, including the first one. No extra
    predecessor is needed for differences, and none is used to bridge a gap.
    Any event in the scanned prefix rejects the file before phase admission.
    """
    references, tags = tuple(references), np.asarray(tags_s, float)
    if (not GPS.fullmatch(target) or target in references or len(references) < 4
            or len(set(references)) != len(references) or any(not GPS.fullmatch(s) for s in references)
            or tags.ndim != 1 or len(tags) < 3 or not np.isfinite(tags).all()
            or not np.isfinite(step_s) or step_s <= 0
            or np.any(abs(np.diff(tags)-step_s) > 1e-7)):
        raise RinexRejected('INVALID_REFERENCE_PHASE_PLAN')
    count = len(tags)*len(references)
    covariance = validate_covariance(raw_covariance, 4*count)
    lines = content.splitlines()
    start, headers, systems, first, identity, station = _phase_header(lines, base_day, base_second, step_s)
    rows, samples, reasons = [], [], []
    seen, previous, i = set(), None, start
    while i < len(lines):
        epoch = lines[i]
        i += 1
        if not epoch.startswith('>'):
            raise RinexRejected('EXPECTED_EPOCH_RECORD')
        fields = epoch[1:].split()
        if len(fields) not in (8, 9):
            raise RinexRejected('INVALID_EPOCH_RECORD')
        tag = _time(fields[:6], base_day, base_second)
        if tag > tags[-1]+1e-7:
            break  # No future flags/payloads decoded.
        try:
            flag, number = int(fields[6]), int(fields[7])
        except ValueError as error:
            raise RinexRejected('INVALID_EPOCH_RECORD') from error
        if flag != 0:
            raise RinexRejected('EVENT_OR_HEADER_CHANGE:'+str(flag))
        if not 0 <= number <= 999 or i+number > len(lines):
            raise RinexRejected('TRUNCATED_OR_INVALID_EPOCH_BLOCK')
        if previous is None and abs(tag-first) > 1e-7:
            raise RinexRejected('FIRST_EPOCH_DIFFERS_FROM_HEADER')
        if previous is not None and tag <= previous:
            raise RinexRejected('DUPLICATE_OR_UNORDERED_EPOCH')
        previous = tag
        if len(fields) == 9:
            try:
                offset = float(fields[8])
            except ValueError as error:
                raise RinexRejected('INVALID_REPORTED_CLOCK_OFFSET') from error
            if not np.isfinite(offset) or 'RCV CLOCK OFFS APPL' not in headers:
                raise RinexRejected('UNQUALIFIED_REPORTED_CLOCK_OFFSET')
        matching = np.flatnonzero(abs(tags-tag) <= 1e-7)
        if tags[0] <= tag <= tags[-1] and len(matching) != 1:
            raise RinexRejected('OFF_GRID_EPOCH_IN_PLANNED_WINDOW')
        block, i = lines[i:i+number], i+number
        satellites = {}
        for line in block:
            sv = line[:3]
            if not re.fullmatch(r'[GRECSJI][0-9]{2}', sv) or sv in satellites:
                raise RinexRejected('INVALID_OR_DUPLICATE_SATELLITE_ROW')
            if sv[0] not in systems or (headers['RINEX VERSION / TYPE'][0][40] == 'G' and sv[0] != 'G'):
                raise RinexRejected('SATELLITE_SYSTEM_DIFFERS_FROM_HEADER')
            satellites[sv] = line
        if len(matching) != 1:
            continue
        idx = int(matching[0])
        seen.add(idx)
        for sv in references:
            record = satellites.get(sv)
            if record is None:
                reasons.append({'tag_s': float(tags[idx]), 'satellite': sv, 'reason': 'MISSING_REFERENCE_ROW'})
                continue
            types = systems['G']['types']
            if record[3+16*len(types):].strip():
                raise RinexRejected('EXCESS_OBSERVATION_PAYLOAD')
            raw = {name: record[3+16*j:3+16*(j+1)] for j, name in enumerate(types) if name in REQUIRED}
            rows.append({'satellite': sv, 'tag_s': float(tags[idx]), 'epoch_flag': 0, 'fields': raw})
            pair = []
            for name in REQUIRED[:2]:
                try:
                    value = float(raw[name][:14])
                except ValueError:
                    value = float('nan')
                if not np.isfinite(value) or value <= 0:
                    reasons.append({'tag_s': float(tags[idx]), 'satellite': sv, 'reason': 'MISSING_INVALID_CODE:'+name})
                pair.append(value)
            samples.append({'satellite': sv, 'tag_s': float(tags[idx]), 'code_m': ALPHA*pair[0]+BETA*pair[1]})
    reasons.extend({'tag_s': float(tags[idx]), 'reason': 'MISSING_PLANNED_ENDPOINT'} for idx in sorted(set(range(len(tags)))-seen))
    result = {'status': 'REFERENCE_PHASE_WINDOW_REJECTED', 'real_rf_qualified': False,
              'target': target, 'references': list(references), 'tags_s': tags.tolist(), 'step_s': step_s,
              'base_day_gpst': base_day, 'base_second': base_second, 'receiver_identity': identity,
              'station_m': station.tolist(), 'source_sha256': hashlib.sha256(content.encode()).hexdigest()}
    if reasons:
        return result | {'reasons': reasons}
    phase_indices = np.array([[4*i+2, 4*i+3] for i in range(count)]).ravel()
    phase = reference_phase_rates(rows, target=target, references=references, tags_s=tags,
                                   phase_covariance=covariance[np.ix_(phase_indices, phase_indices)])
    if phase['status'] != 'REFERENCE_PHASE_RATE_AVAILABLE':
        return result | {'reasons': phase['reasons']}
    code_transform = np.kron(np.eye(count), np.array([[ALPHA, BETA, 0., 0.]]))
    rate_transform = np.zeros((len(phase['mean_phase_rate_m_s'].ravel()), 4*count))
    rate_transform[:, phase_indices] = phase['transform_cycles_to_mean_rate']
    transform = np.vstack([code_transform, rate_transform])
    joint = transform@covariance@transform.T
    admitted = {'samples': samples, 'phase_sha256': phase['admitted_phase_sha256'],
                'receiver_identity': identity, 'station_m': station.tolist(), 'base_day': base_day,
                'base_second': base_second, 'covariance': joint.tolist()}
    return result | {'status': 'REFERENCE_PHASE_WINDOW_PARSED', 'samples': samples,
        'mean_phase_rate_m_s': phase['mean_phase_rate_m_s'], 'interval_start_s': tags[:-1], 'interval_end_s': tags[1:],
        'covariance_code_phase_rate': (joint+joint.T)/2,
        'admitted_observations_sha256': hashlib.sha256(json.dumps(admitted, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        'scope': 'Reference-only C1C/C2W plus L1C/L2W intervals. Full covariance retained; no RF qualification.'}
