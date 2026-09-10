"""Bounded RINEX 3.04/3.05 GPS reference-only observation importer.

No receiver is physically qualified by parsing its header. An exact window and
reference list are inputs; excluded satellite values are never decoded.
"""
from datetime import date
import hashlib
import json
import re

import numpy as np

from positioning.calibration import antenna_position
from .clock_drift import local_gpst_seconds
from .doppler import admit_fields, convert_gps_if

GPS = re.compile(r'G(?:0[1-9]|[12][0-9]|3[0-2])')
REQUIRED = ('C1C', 'C2W', 'D1C', 'D2W', 'L1C', 'L2W')
METADATA = {
    'RINEX VERSION / TYPE', 'PGM / RUN BY / DATE', 'COMMENT', 'MARKER NAME',
    'MARKER NUMBER', 'MARKER TYPE', 'OBSERVER / AGENCY', 'REC # / TYPE / VERS',
    'ANT # / TYPE', 'APPROX POSITION XYZ', 'ANTENNA: DELTA H/E/N',
    'SYS / # / OBS TYPES', 'INTERVAL', 'TIME OF FIRST OBS', 'TIME OF LAST OBS',
    'RCV CLOCK OFFS APPL', 'SYS / PHASE SHIFT', 'SIGNAL STRENGTH UNIT',
    'GLONASS SLOT / FRQ #', 'GLONASS COD/PHS/BIS', 'LEAP SECONDS',
    '# OF SATELLITES', 'PRN / # OF OBS', 'END OF HEADER',
}


class RinexRejected(ValueError):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


def _time(parts, base_day, base_second):
    try:
        year, month, day, hour, minute = map(int, parts[:5])
        seconds = float(parts[5])
        if not 0 <= hour < 24 or not 0 <= minute < 60 or not 0 <= seconds < 60:
            raise ValueError('invalid time of day')
        return local_gpst_seconds(date(year, month, day).isoformat(),
                                  hour*3600+minute*60+seconds,
                                  base_day=base_day, base_second=base_second)
    except (ValueError, IndexError, TypeError) as error:
        raise RinexRejected('INVALID_GPST_EPOCH') from error


def _header(lines, base_day, base_second, step_s):
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


def parse_reference_observations(content, *, target, references, tags_s, step_s,
                                 base_day, base_second, raw_covariance):
    """Import exactly a predeclared reference-only window plus one predecessor.

    Return every missing/rejected required pair. Never select a better interval,
    replace references or inspect target/future numerical observation fields.
    Event/header changes within the scanned prefix reject the bounded file.
    """
    references = tuple(references)
    tags = np.asarray(tags_s, dtype=float)
    if (not GPS.fullmatch(target) or target in references or not references
            or len(set(references)) != len(references) or any(not GPS.fullmatch(s) for s in references)
            or tags.ndim != 1 or len(tags) < 3 or not np.isfinite(tags).all()
            or not np.isfinite(step_s) or step_s <= 0
            or np.any(np.abs(np.diff(tags)-step_s) > 1e-7)):
        raise RinexRejected('INVALID_REFERENCE_WINDOW_PLAN')
    # Validate the noise transformation even if every observation is missing.
    convert_gps_if([1., 1., 1., 1.], raw_covariance)
    lines = content.splitlines()
    start, headers, systems, first_time, identity, station = _header(lines, base_day, base_second, step_s)
    samples, rejections, seen_epochs = [], [], set()
    previous_good, last_time = {}, None
    i = start
    while i < len(lines):
        epoch = lines[i]
        i += 1
        if not epoch.startswith('>'):
            raise RinexRejected('EXPECTED_EPOCH_RECORD')
        fields = epoch[1:].split()
        if len(fields) not in (8, 9):
            raise RinexRejected('INVALID_EPOCH_RECORD')
        t = _time(fields[:6], base_day, base_second)
        # Stop at the first later tag before decoding any following payload.
        if t > tags[-1]+1e-7:
            break
        try:
            flag, count = int(fields[6]), int(fields[7])
        except ValueError as error:
            raise RinexRejected('INVALID_EPOCH_RECORD') from error
        if flag != 0:
            raise RinexRejected('EVENT_OR_HEADER_CHANGE:'+str(flag))
        if not 0 <= count <= 999 or i+count > len(lines):
            raise RinexRejected('TRUNCATED_OR_INVALID_EPOCH_BLOCK')
        if last_time is None and abs(t-first_time) > 1e-7:
            raise RinexRejected('FIRST_EPOCH_DIFFERS_FROM_HEADER')
        if last_time is not None and t <= last_time:
            raise RinexRejected('DUPLICATE_OR_UNORDERED_EPOCH')
        last_time = t
        if len(fields) == 9:
            try:
                offset = float(fields[8])
            except ValueError as error:
                raise RinexRejected('INVALID_REPORTED_CLOCK_OFFSET') from error
            if 'RCV CLOCK OFFS APPL' not in headers or not np.isfinite(offset):
                raise RinexRejected('UNQUALIFIED_REPORTED_CLOCK_OFFSET')
            # Unapplied reported offsets are metadata, never calibration inputs.
        wanted = np.flatnonzero(np.abs(tags-t) <= 1e-7)
        selected = len(wanted) == 1
        predecessor = abs(t-(tags[0]-step_s)) <= 1e-7
        if tags[0] <= t <= tags[-1] and not selected:
            raise RinexRejected('OFF_GRID_EPOCH_IN_PLANNED_WINDOW')
        block = lines[i:i+count]
        i += count
        satellite_rows = {}
        for record in block:
            satellite = record[:3]
            if not re.fullmatch(r'[GRECSJI][0-9]{2}', satellite) or satellite in satellite_rows:
                raise RinexRejected('INVALID_OR_DUPLICATE_SATELLITE_ROW')
            if satellite[0] not in systems or (headers['RINEX VERSION / TYPE'][0][40] == 'G' and satellite[0] != 'G'):
                raise RinexRejected('SATELLITE_SYSTEM_DIFFERS_FROM_HEADER')
            satellite_rows[satellite] = record
        if not selected and not predecessor:
            continue
        if selected:
            seen_epochs.add(int(wanted[0]))
        for satellite in references:
            record = satellite_rows.get(satellite)
            reason = []
            if record is None:
                reason = ['MISSING_REFERENCE_ROW']
            else:
                types = systems['G']['types']
                if record[3+16*len(types):].strip():
                    raise RinexRejected('EXCESS_OBSERVATION_PAYLOAD')
                raw = {name: record[3+16*j:3+16*(j+1)] for j, name in enumerate(types) if name in REQUIRED}
                # The first predecessor establishes field/lock eligibility; its
                # unknown predecessor is never used to admit a fitted sample.
                gap = step_s if predecessor else t-previous_good.get(satellite, float('-inf'))
                if np.isfinite(gap) and abs(gap-step_s) <= 1e-7:
                    gap = step_s
                admitted = admit_fields(raw, epoch_flag=flag, gap_s=gap, expected_step_s=step_s)
                reason = admitted['reasons']
            if reason:
                previous_good.pop(satellite, None)
                if selected:
                    rejections.append({'tag_s': float(t), 'satellite': satellite, 'reasons': reason})
                continue
            previous_good[satellite] = t
            if selected:
                values, covariance = convert_gps_if(admitted['values'], raw_covariance)
                samples.append({'tag_s': float(tags[wanted[0]]), 'satellite': satellite,
                                'code_m': float(values[0]), 'rate_m_s': float(values[1]),
                                'covariance': covariance.tolist()})
    for index in sorted(set(range(len(tags)))-seen_epochs):
        rejections.append({'tag_s': float(tags[index]), 'reasons': ['MISSING_PLANNED_EPOCH']})
    admitted_payload = {'samples': samples, 'rejections': rejections, 'references': references,
                        'tags_s': tags.tolist(), 'base_day': base_day, 'base_second': base_second,
                        'receiver_identity': identity, 'station_m': station.tolist()}
    admitted_hash = hashlib.sha256(json.dumps(admitted_payload, sort_keys=True, allow_nan=False).encode()).hexdigest()
    return {'status': 'REFERENCE_WINDOW_PARSED' if not rejections else 'REFERENCE_WINDOW_REJECTED',
            'target': target, 'references': list(references), 'tags_s': tags.tolist(),
            'base_day_gpst': base_day, 'base_second': base_second, 'step_s': step_s,
            'receiver_identity': identity, 'station_m': station.tolist(),
            'samples': samples, 'rejections': rejections,
            'source_sha256': hashlib.sha256(content.encode('utf-8')).hexdigest(),
            'admitted_observations_sha256': admitted_hash,
            'real_rf_qualified': False,
            'scope': 'Bounded GPS reference-only parse; header identity is not Doppler time-basis or receiver qualification.'}
