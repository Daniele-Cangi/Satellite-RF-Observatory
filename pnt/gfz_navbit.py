"""GPS LNAV content from a GFZ daily compressed NetCDF NavBit member.

This is one provider's already-filtered aggregate. File/message times are
declarations, not an independent acquisition clock or proof of freshness.
"""

from collections import Counter
from datetime import date, timedelta
import gzip
import hashlib
import io
from pathlib import Path

import numpy as np
from scipy.io import netcdf_file

from .lnav import decode_lnav_words
from .sfrbx import bits, decode_issue, GPS_EPOCH


def read_gfz_navbit_issues(path):
    """Return representation rows and retain every CEI cycle's outcome.

    Read one local NetCDF-v1 .nc.gz member, not an arbitrary tar extraction or
    a network stream. Validate declared layout/time ordering before selection.
    Invalid subframes, missing pieces and mixed IODE/IODC cannot be repaired or
    borrowed across cycles. Unavailable URA/TGD remain decoded diagnostics and
    must pass the existing representation qualifier before content comparison.
    """
    packed = Path(path).read_bytes()
    raw = gzip.decompress(packed)
    with netcdf_file(io.BytesIO(raw), mmap=False) as source:
        variables = source.variables
        required = ('version', 'year', 'day_of_year', 'gps_week', 'prn', 'nofsfr',
                    'navbits', 'time', 'multiplicity', 'gps_word')
        if any(name not in variables for name in required):
            raise ValueError('missing GFZ NavBit variable')
        scalars = {}
        for name in required[:6]:
            value = variables[name].data
            if value.shape != () or value.dtype.kind != 'i':
                raise ValueError('invalid GFZ integer scalar')
            scalars[name] = int(value)
        year, doy = scalars['year'], scalars['day_of_year']
        day = date(year, 1, 1) + timedelta(days=doy - 1)
        gps_days = (day - GPS_EPOCH.date()).days
        if (scalars['version'] != 1 or doy < 1 or day.year != year or gps_days < 0
                or scalars['gps_week'] != gps_days // 7 or not 1 <= scalars['prn'] <= 32):
            raise ValueError('invalid GFZ date/week/PRN/version metadata')
        count = scalars['nofsfr']
        words, times, multiplicity = (variables[name].data for name in ('navbits', 'time', 'multiplicity'))
        if (not 0 <= count <= 14400 or words.shape != (10, count)
                or times.shape != (count,) or multiplicity.shape != (count,)
                or variables['navbits'].dimensions != ('gps_word', 'time')
                or any(variables[name].dimensions != ('time',) for name in ('time', 'multiplicity'))
                or any(value.dtype.kind != 'i' for value in (words, times, multiplicity))
                or not np.array_equal(variables['gps_word'].data, np.arange(1, 11))):
            raise ValueError('invalid GFZ NavBit array layout')
        if (np.any(times < 0) or np.any(times >= 86400) or np.any(times % 6)
                or np.any(np.diff(times.astype(np.int64)) <= 0)):
            raise ValueError('invalid GFZ ordered subframe times')
        satellite, day_start = f"G{scalars['prn']:02d}", (gps_days % 7) * 86400
        groups, failures, statuses = {}, [], Counter()
        for index, (transmitted, time, multiple) in enumerate(zip(words.T, times, multiplicity)):
            time, multiple = int(time), int(multiple)
            sow = day_start + time
            start, expected_sf = sow // 30 * 30, sow // 6 % 5 + 1
            cycle = None
            if expected_sf in (1, 2, 3):
                cycle = groups.setdefault(start, {'index': len(groups), 'frame_start_sow': start,
                                                   'source_row_indices': [], 'frames': {}, 'invalid_rows': []})
                cycle['source_row_indices'].append(index)
            try:
                if multiple <= 0:
                    raise ValueError('nonpositive provider multiplicity')
                data = decode_lnav_words(transmitted)
                how, sf = bits(data, 24, 17), bits(data, 43, 3)
                if data[0] != 0x8b or sf != expected_sf or how >= 100800:
                    raise ValueError('invalid GFZ TLM/subframe phase')
                if (how * 6 - 6) % 604800 != sow:
                    raise ValueError('GFZ HOW/provider-time disagreement')
            except ValueError as error:
                statuses['INVALID_SUBFRAME'] += 1
                failures.append({'source_row_index': index, 'provider_time_sod': time,
                                 'provider_multiplicity': multiple, 'reason': str(error)})
                if cycle is not None:
                    cycle['invalid_rows'].append(index)
                continue
            statuses['PARITY_VALID_SUBFRAME'] += 1
            if cycle is not None:
                cycle['frames'][sf] = [{'data_hex': data.hex(), 'source_row_index': index}]
        records, cycles = [], []
        for cycle in groups.values():
            frames = cycle['frames']
            info = {key: value for key, value in cycle.items() if key != 'frames'}
            info['missing_subframes'] = [sf for sf in (1, 2, 3) if sf not in frames]
            if info['invalid_rows']:
                info['status'] = 'INVALID_CYCLE'
            elif info['missing_subframes']:
                info['status'] = 'INCOMPLETE_CYCLE'
            else:
                try:
                    row = decode_issue(satellite, frames, day.isoformat(), cycle['frame_start_sow'],
                                       retain_unavailable=True)
                except ValueError as error:
                    info.update(status='UNUSABLE_ISSUE', reason=str(error))
                else:
                    unavailable = []
                    if bits(bytes.fromhex(frames[1][0]['data_hex']), 60, 4) == 15:
                        unavailable.append('sv_accuracy_m')
                    if bits(bytes.fromhex(frames[1][0]['data_hex']), 160, 8, True) == -128:
                        unavailable.append('tgd_s')
                    row.update(index=len(records), gfz_cycle_index=cycle['index'])
                    records.append(row)
                    info.update(status='DECODED_UNAVAILABLE_METADATA' if unavailable else 'DECODED_ISSUE',
                                record_index=row['index'], unavailable_fields=unavailable)
            cycles.append(info)
        return records, {
            'file': Path(path).name, 'sha256': hashlib.sha256(packed).hexdigest(),
            'bytes': len(packed), 'netcdf_sha256': hashlib.sha256(raw).hexdigest(),
            'netcdf_bytes': len(raw), 'format': 'GFZ-GPS-L1CA-NavBit-NetCDF-v1',
            'day_gpst': day.isoformat(), 'gps_week': scalars['gps_week'], 'satellite': satellite,
            'subframes': count, 'decoded_records': len(records),
            'provider_history': source.history.decode('ascii') if hasattr(source, 'history') else None,
            'multiplicity_counts': {str(k): v for k, v in sorted(Counter(int(m) for m in multiplicity).items())},
            'frame_status_counts': dict(sorted(statuses.items())), 'failed_subframes': failures,
            'cycle_status_counts': dict(sorted(Counter(c['status'] for c in cycles).items())),
            'cycles': cycles,
            'limits': ['Provider-selected aggregate; receiver identity and upstream discarded frames are unavailable.',
                       'Parity and file/message time consistency do not establish RF origin or independent timing.',
                       'All daily CEI outcomes retained; no cross-cycle borrowing or silent repair.',
                       'Unavailable URA/TGD are diagnostic rows, not qualified representations or accuracy bounds.'],
        }
