"""Native decoded UBX fields: GPS L1 code admission and NAV epoch association.

Collection labels are source identities, never substitutes for receiver time.
RAWX rcvTow and NAV iTOW use different clocks; this module does not equate them.
"""

from collections import Counter, defaultdict
from datetime import timedelta
import math

from .model import GPS_EPOCH


def rawx_gps_l1(message):
    """Return native receiver-local epoch and C1C, retaining every L1 rejection."""
    week, tow, count = message['week'], message['rcvTow'], message['numMeas']
    if (type(week) is not int or not 0 <= week <= 65535 or
            isinstance(tow, bool) or not isinstance(tow, (int, float)) or
            not math.isfinite(tow) or not 0 <= tow < 604800 or
            type(count) is not int or not 0 <= count <= 255):
        raise ValueError('invalid native RAWX week, time or measurement count')
    rows = defaultdict(list)
    for index in range(1, count + 1):
        suffix = f'_{index:02d}'
        if message['gnssId' + suffix] == 0 and message['sigId' + suffix] == 0:
            sv = message['svId' + suffix]
            code = message['prMes' + suffix]
            reason = None
            if type(sv) is not int or not 1 <= sv <= 32:
                reason = 'INVALID_GPS_SV'
            elif type(message['prValid' + suffix]) is not int or message['prValid' + suffix] != 1:
                reason = 'CODE_NOT_VALID'
            elif (isinstance(code, bool) or not isinstance(code, (int, float)) or
                  not math.isfinite(code) or code <= 0):
                reason = 'INVALID_CODE_VALUE'
            rows[sv].append({'source_index': index, 'reason': reason, 'code': code})
    codes, dispositions = {}, []
    for sv, entries in rows.items():
        for row in entries:
            reason = 'DUPLICATE_GPS_L1_SV' if len(entries) != 1 else row['reason']
            dispositions.append({'source_index': row['source_index'],
                                 'status': reason or 'ADMITTED', 'sv_id': sv})
            if reason is None:
                codes[f'G{sv:02d}'] = row['code']
    return {'week': week, 'rcvTow': tow,
            'receiver_local_gpst': GPS_EPOCH + timedelta(weeks=week, seconds=tow),
            'codes': codes, 'dispositions': sorted(dispositions, key=lambda r: r['source_index']),
            'status_counts': dict(sorted(Counter(r['status'] for r in dispositions).items()))}


def pair_navigation(pvt_messages, clock_messages):
    """Join exact iTOW within one acquisition segment; reject ambiguous matches.

    Inputs are (source identity, decoded message) pairs. iTOW has no week;
    callers must supply one continuous segment shorter than a GPS week.
    Duplicate epochs stay ambiguous even if their values happen to agree.
    Time/fix flags are retained by the caller; matching does not validate time.
    """
    indices = []
    for messages in (pvt_messages, clock_messages):
        index = defaultdict(list)
        identities = set()
        for source, message in messages:
            if source in identities:
                raise ValueError('duplicate source identity within NAV stream')
            identities.add(source)
            tow = message['iTOW']
            if type(tow) is not int or not 0 <= tow < 604800000:
                raise ValueError('invalid native NAV iTOW')
            index[tow].append(source)
        indices.append(index)
    pvt, clock = indices
    result = []
    for tow in sorted(pvt.keys() | clock.keys()):
        first, second = pvt.get(tow, []), clock.get(tow, [])
        if len(first) > 1 or len(second) > 1:
            status = 'AMBIGUOUS_NAV_EPOCH'
        elif not first:
            status = 'MISSING_PVT'
        elif not second:
            status = 'MISSING_CLOCK'
        else:
            status = 'PAIRED'
        result.append({'iTOW': tow, 'status': status, 'pvt_sources': first, 'clock_sources': second})
    return result
