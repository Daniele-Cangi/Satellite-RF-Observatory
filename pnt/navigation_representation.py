"""Resolve written NAV intervals to LNAV values without nearest-bit repair.

This is representation qualification, not authentication or source admission.
IS-GPS-200N tables 20-I/III bind binary scales/widths; RINEX 3.05 table A6
binds nominal URA metres. Unavailable or invalid metadata stays unqualified.
"""

from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
from math import ceil, floor

from .navigation_witness import FIELDS, INTEGER_FIELDS, group_issues, issue_intervals
from .sfrbx import ORBIT_FIELDS, PI, URA_METRES


# Reuse the decoder's field definitions, not a second independently maintained
# orbit layout. This describes encodable values, not orbit/model health.
BINARY_FIELDS = {name: (length, signed, power, angular)
                 for specs in ORBIT_FIELDS.values()
                 for name, _, length, signed, power, angular in specs}
BINARY_FIELDS.update(af0_s=(22, True, -31, False), af1_s_s=(16, True, -43, False),
                     af2_s_s2=(8, True, -55, False), tgd_s=(8, True, -31, False))


def field_candidates(name, interval):
    """Return all feasible encodings as compact bounds, never round to nearest.

    Closed intervals include boundary ties. Exact rational arithmetic avoids
    rounding at integer boundaries. For semicircles, pi lies between the
    decoder's truncated constant and its next decimal unit; the resulting
    value interval scales with the candidate, and zero is exactly zero.
    """
    lower, upper = interval
    if not lower.is_finite() or not upper.is_finite():
        raise ValueError('nonfinite navigation representation interval')
    result = {'written_interval': [str(lower), str(upper)]}
    if lower > upper:
        return dict(result, status='CONFLICTING_REPRESENTATIONS', candidate_count=0)
    with localcontext() as context:
        context.prec = 160  # Enough to serialize the finite rational scales exactly.
        if name == 'sv_accuracy_m':
            # 8192 is RINEX's unavailable-accuracy representation, not a
            # finite predicted accuracy or a receiver-exported index in metres.
            choices = [i for i, value in enumerate((*URA_METRES, Decimal(8192)))
                       if lower <= value <= upper]
            result.update(candidate_count=len(choices), candidate_indices=choices,
                          encoding='URA_INDEX_FROM_RINEX_NOMINAL_METRES')
            code = choices[0] if len(choices) == 1 else None
        else:
            if name in INTEGER_FIELDS:
                minimum, maximum = INTEGER_FIELDS[name]
                scale_lower = scale_upper = Fraction(1)
                angular = False
            else:
                width, signed, power, angular = BINARY_FIELDS[name]
                minimum = -(1 << (width - 1)) if signed else 0
                maximum = (1 << (width - int(signed))) - 1
                if name == 'toe_sow':
                    maximum = 604784 // 16
                binary_scale = Fraction(2) ** power
                scale_lower = binary_scale * (Fraction(PI) if angular else 1)
                scale_upper = (binary_scale * (Fraction(PI) + Fraction(10) ** PI.as_tuple().exponent)
                               if angular else scale_lower)
            # Division by a positive scale interval reverses which endpoint
            # is extremal for negative values. No written interval expansion.
            first = max(minimum, ceil(min(Fraction(lower) / scale_lower,
                                          Fraction(lower) / scale_upper)))
            last = floor(max(Fraction(upper) / scale_lower, Fraction(upper) / scale_upper))
            if maximum is not None:
                last = min(maximum, last)
            count = max(0, last - first + 1)
            result.update(candidate_count=count, encoded_bounds=[first, last] if count else None,
                          scale=str(Decimal(scale_lower.numerator) / Decimal(scale_lower.denominator)))
            if angular:
                result['scale_interval'] = [result['scale'],
                    str(Decimal(scale_upper.numerator) / Decimal(scale_upper.denominator))]
            else:
                result['numerical_bound'] = '0'
            code = first if count == 1 else None
        count = result['candidate_count']
        result['status'] = ('NO_BROADCAST_VALUE' if not count else
                            'AMBIGUOUS_REPRESENTATION' if count > 1 else 'UNIQUE_BROADCAST_VALUE')
        if code is not None:
            result['encoded_value'] = code
            if name == 'sv_accuracy_m' and code == 15:
                result['status'] = 'UNAVAILABLE_ACCURACY'
            elif name == 'tgd_s' and code == -128:
                result['status'] = 'UNAVAILABLE_GROUP_DELAY'
            elif name == 'codes_l2' and code in (0, 3):
                result['status'] = 'INVALID_L2_CODE_METADATA'
    return result


def qualify_fields(intervals):
    return {name: field_candidates(name, intervals[name]) for name in FIELDS}


def compare_fields(local, external):
    fields, different, unresolved = {}, [], []
    for name in FIELDS:
        left, right = local[name], external[name]
        if left['status'] != 'UNIQUE_BROADCAST_VALUE' or right['status'] != 'UNIQUE_BROADCAST_VALUE':
            status = 'UNQUALIFIED_REPRESENTATION'
            unresolved.append(name)
        else:
            equal = left['encoded_value'] == right['encoded_value']
            status = 'SAME_ENCODED_VALUE' if equal else 'DIFFERENT_ENCODED_VALUE'
            if not equal:
                different.append(name)
        fields[name] = {'status': status, 'local': left, 'external': right}
    return {'status': ('REPRESENTATION_UNQUALIFIED' if unresolved else
                       'DIFFERENT_BROADCAST_FIELDS' if different else 'SAME_BROADCAST_FIELDS'),
            'qualified_differing_fields': different, 'unqualified_fields': unresolved, 'fields': fields}


def qualify_navigation_records(selected, external):
    """Add representation evidence using the existing exact-issue boundary.

    Conflicting duplicate intervals and contradictory witnesses remain visible.
    Every matching witness participates in the joint intersection; no vote,
    alternate issue, source correction or inferred precision is introduced.
    """
    groups, outputs = group_issues(selected), []
    for row in selected:
        identity = row['identity']
        local_intervals = issue_intervals(groups[identity])
        local = qualify_fields(local_intervals)
        peers, common = {}, []
        local_conflicts = [name for name in FIELDS
                           if local[name]['status'] == 'CONFLICTING_REPRESENTATIONS']
        for name, grouped in external.items():
            records = grouped.get(identity, [])
            peer = {'source_record_indices': [item['index'] for item in records]}
            if not records:
                peer['status'] = 'MISSING_ISSUE'
            else:
                intervals = issue_intervals(records)
                peer.update(compare_fields(local, qualify_fields(intervals)))
                common.append(intervals)
            peers[name] = peer
        result = {'local_record_index': row['index'], 'satellite': identity[0], 'toc_gpst': identity[1],
                  'local_fields': local, 'local_conflicting_fields': local_conflicts, 'witnesses': peers}
        if not common:
            result['status'] = 'MISSING_ISSUE'
        else:
            intersection = {name: (max(interval[name][0] for interval in common),
                                   min(interval[name][1] for interval in common)) for name in FIELDS}
            joint = qualify_fields(intersection)
            result.update(compare_fields(local, joint))
            result['joint_external_conflicting_fields'] = [name for name in FIELDS
                                                          if joint[name]['status'] == 'CONFLICTING_REPRESENTATIONS']
            if result['joint_external_conflicting_fields']:
                result['status'] = 'EXTERNAL_RECORD_CONFLICT'
        if local_conflicts:
            result['status'] = 'CONFLICTING_LOCAL_RECORDS'
        if 'sfrbx_cycle_index' in row:
            result['sfrbx_cycle_index'] = row['sfrbx_cycle_index']
        if 'written_decimal_record_index' in row:
            result.update(representation_record_index=row['index'],
                          local_record_index=row['written_decimal_record_index'])
        if 'written_decimal_rejection' in row:
            result['written_decimal_rejection'] = row['written_decimal_rejection']
        outputs.append(result)
    return {'profile': 'GPS_LNAV_WRITTEN_INTERVALS_V2', 'records': outputs,
            'status_counts': dict(sorted(Counter(row['status'] for row in outputs).items())),
            'limits': [
                'This qualifies representations under written-decimal rounding, not source truth or RF origin.',
                'Every field needs one encodable value; zero/multiple candidates or unavailable metadata stay unqualified.',
                'No nearest-integer repair, inferred trailing-zero precision, exporter correction or physical tolerance.',
                'A uniquely different encoding is content discordance, not attack attribution; matching does not authenticate ranges.',
                'Continuous week is compared in the declared era; freshness and absolute time remain unverified.',
                'All 27 fields and missing/conflicting witnesses remain visible; source independence remains unqualified.',
            ]}
