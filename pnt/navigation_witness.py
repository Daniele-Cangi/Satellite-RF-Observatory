"""Compare decoded GPS navigation issues with explicitly supplied external files."""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
from pathlib import Path

from positioning.navigation import parse_gps_record
from .model import navigation_blocks, day_context
from .fixed_site import validate_window


# RINEX 2.11 table A4, excluding receiver-dependent transmission time and
# optional derived fit duration. Header ionosphere/UTC parameters are outside
# this first message comparison. Include fields the propagation model omits.
FIELDS = ('af0_s', 'af1_s_s', 'af2_s_s2', 'iode', 'crs_m', 'delta_n_rad_s', 'm0_rad',
          'cuc_rad', 'eccentricity', 'cus_rad', 'sqrt_a_m_sqrt', 'toe_sow',
          'cic_rad', 'omega0_rad', 'cis_rad', 'i0_rad', 'crc_m',
          'argument_perigee_rad', 'omega_dot_rad_s', 'idot_rad_s', 'codes_l2',
          'gps_week', 'l2_p_flag', 'sv_accuracy_m', 'sv_health', 'tgd_s', 'iodc')
INTEGER_FIELDS = {'iode': (0, 255), 'iodc': (0, 1023), 'gps_week': (0, None),
                  'codes_l2': (0, 3), 'l2_p_flag': (0, 1), 'sv_health': (0, 63)}
IDENTITY_FIELDS = ('gps_week', 'toe_sow', 'iode', 'iodc')


def read_issues(path):
    data = Path(path).read_bytes()
    records = []
    for index, block in enumerate(navigation_blocks(data)):
        # Keep fixed field positions, including blank fields: unlike orbit
        # fitting, comparison must not drop IODC, L2 flags or unhealthy records.
        text = [block[0][23 + i * 19:23 + (i + 1) * 19].strip() for i in range(3)]
        text += [line[4 + i * 19:4 + (i + 1) * 19].strip() for line in block[1:7] for i in range(4)]
        if any(not value for value in text):
            raise ValueError('navigation comparison requires all clock and orbit-1..6 fields')
        try:
            values = {name: Decimal(value.replace('D', 'E').replace('d', 'e'))
                      for name, value in zip(FIELDS, text)}
        except InvalidOperation as error:
            raise ValueError('invalid navigation decimal field') from error
        if not all(value.is_finite() for value in values.values()):
            raise ValueError('nonfinite navigation comparison field')
        for name, (lower, upper) in INTEGER_FIELDS.items():
            value = values[name]
            if value != int(value) or value < lower or (upper is not None and value > upper):
                raise ValueError(f'invalid integer navigation field: {name}')
        if not 0 <= values['toe_sow'] < 604800:
            raise ValueError('invalid navigation toe')
        try:
            parsed = parse_gps_record(block)
        except (IndexError, OverflowError) as error:
            raise ValueError('invalid navigation record structure') from error
        identity = (parsed.satellite, parsed.toc_gps.isoformat(),
                    *(values[name] for name in IDENTITY_FIELDS))
        intervals = {}
        for name, value in values.items():
            # Account only for rounding in the written decimal representation,
            # not physical error or GNSS authenticity. Integers are exact.
            half_unit = (Decimal(0) if name in INTEGER_FIELDS else
                         Decimal(5).scaleb(value.as_tuple().exponent - 1))
            intervals[name] = (value - half_unit, value + half_unit)
        records.append({'index': index, 'identity': identity, 'values': values,
                        'intervals': intervals, 'toc': parsed.toc_gps})
    return records, {'file': Path(path).name, 'sha256': hashlib.sha256(data).hexdigest(),
                     'decoded_records': len(records),
                     'unhealthy_records_retained': sum(row['values']['sv_health'] != 0 for row in records)}


def group_issues(records):
    grouped = defaultdict(list)
    for row in records:
        grouped[row['identity']].append(row)
    return grouped


def issue_intervals(records):
    """Intersect duplicate representations; incompatible duplicates stay conflicts."""
    return {name: (max(row['intervals'][name][0] for row in records),
                   min(row['intervals'][name][1] for row in records)) for name in FIELDS}


def conflicting_fields(intervals):
    return [name for name, (lower, upper) in intervals.items() if lower > upper]


def compare_issue_records(selected, external):
    """Compare retained decoded issues with grouped witnesses, without time selection."""
    groups = group_issues(selected)
    outputs = []
    for row in selected:
        identity = row['identity']
        local_intervals = issue_intervals(groups[identity])
        local_conflicts = conflicting_fields(local_intervals)
        peers, common = {}, []
        for name, records in external.items():
            matching = records.get(identity, [])
            peer = {'matching_records': len(matching),
                    'records': [{'source_record_index': item['index'],
                                 'fields': {field: str(value) for field, value in item['values'].items()}}
                                for item in matching]}
            if not matching:
                peer['status'] = 'MISSING_ISSUE'
            else:
                intervals = issue_intervals(matching)
                conflicts = conflicting_fields(intervals)
                if conflicts:
                    peer.update(status='CONFLICTING_EXTERNAL_RECORDS', conflicting_fields=conflicts)
                else:
                    different = [field for field in FIELDS
                                 if max(local_intervals[field][0], intervals[field][0]) >
                                    min(local_intervals[field][1], intervals[field][1])]
                    peer.update(status='DIFFERENT_FIELDS' if different else 'COMPATIBLE_FIELDS',
                                differing_fields=different)
                    common.append(intervals)
            peers[name] = peer
        if local_conflicts:
            status = 'CONFLICTING_LOCAL_RECORDS'
        elif any(peer['status'] == 'CONFLICTING_EXTERNAL_RECORDS' for peer in peers.values()):
            status = 'EXTERNAL_RECORD_CONFLICT'
        elif not common:
            status = 'INSUFFICIENT_EVIDENCE'
        else:
            intersection = {field: (max(v[field][0] for v in common), min(v[field][1] for v in common))
                            for field in FIELDS}
            if conflicting_fields(intersection):
                status = 'EXTERNAL_RECORD_CONFLICT'
            else:
                # Compare with the intersection, not independent pairwise
                # overlaps that could conceal mutually inconsistent values.
                different = [field for field in FIELDS
                             if max(local_intervals[field][0], intersection[field][0]) >
                                min(local_intervals[field][1], intersection[field][1])]
                status = 'DIFFERENT_FROM_EXTERNAL' if different else 'COMPATIBLE_WITH_EXTERNAL'
        outputs.append({'local_record_index': row['index'], 'satellite': identity[0],
                        'toc_gpst': identity[1],
                        'issue': {field: str(row['values'][field]) for field in IDENTITY_FIELDS},
                        'status': status, 'local_conflicting_fields': local_conflicts,
                        'local_fields': {field: str(value) for field, value in row['values'].items()},
                        'witnesses': peers})
        if 'sfrbx_cycle_index' in row:
            outputs[-1]['sfrbx_cycle_index'] = row['sfrbx_cycle_index']
    return outputs


def inspect_navigation(local_path, witnesses, day_gpst, *, start_s=0, stop_s=86400,
                       local_format='rinex', recover_corrupt=False, qualify_lnav=False):
    """Report agreement/discordance on the same issue, never RF authenticity.

    Names declare supplied sources, not independent receivers or authorities.
    Unmatched issues and contradictory duplicates are retained, not replaced
    by the closest ephemeris or resolved by a majority vote.
    """
    validate_window(start_s, stop_s)
    if (not isinstance(witnesses, dict) or not witnesses or
            any(not isinstance(name, str) or not name.strip() or name == 'local' for name in witnesses)):
        raise ValueError('at least one named external navigation witness required; local is reserved')
    context = day_context(date.fromisoformat(day_gpst))
    if local_format == 'ubx':
        if (start_s, stop_s) != (0, 86400):
            raise ValueError('UBX comparison retains the whole capture; toc windows require RINEX')
        from .sfrbx import read_sfrbx_issues
        local, local_source = read_sfrbx_issues(local_path, day_gpst,
                                               recover_corrupt=recover_corrupt)
    elif local_format == 'rinex' and not recover_corrupt:
        local, local_source = read_issues(local_path)
    else:
        raise ValueError('local format must be rinex or ubx; recovery applies only to UBX')
    selected = (local if local_format == 'ubx' else
                [row for row in local if start_s <= (row['toc'] - context.day).total_seconds() < stop_s])
    sources, external = {'local': local_source}, {}
    for name, path in sorted(witnesses.items()):
        records, sources[name] = read_issues(path)
        external[name] = group_issues(records)
    outputs = compare_issue_records(selected, external)
    report = {'schema': 'pnt-navigation-witness-v1',
            'status': 'NAVIGATION_DIAGNOSTICS_AVAILABLE' if outputs else 'INSUFFICIENT_EVIDENCE',
            'day_gpst': day_gpst, 'window_gpst_s': [start_s, stop_s], 'sources': sources,
            'coverage': {'selected_local_records': len(outputs),
                         'local_records_outside_window': len(local) - len(selected),
                         'status_counts': dict(sorted(Counter(row['status'] for row in outputs).items())),
                         'unique_external_file_hashes': len({sources[name]['sha256'] for name in external}),
                         'external_files_equal_to_local': [name for name in external
                                                         if sources[name]['sha256'] == local_source['sha256']]},
            'records': outputs,
            'assessments': {'RF_authenticity': 'NOT_ASSESSED', 'attack_attribution': 'NOT_ASSESSED',
                            'absolute_time': 'INSUFFICIENT_EVIDENCE', 'source_independence': 'NOT_QUALIFIED'},
            'limits': [
                'This compares decoded navigation fields, not RF origin, pseudorange authenticity or receiver PVT.',
                'The same issue means satellite/toc/continuous week/toe/IODE/IODC; no nearest-issue fallback.',
                'Missing issues, local/external conflicts and uncovered intervals are retained without majority voting.',
                'Compatibility allows written-decimal rounding only; it is not a physical tolerance or authentication.',
                'Transmission time, derived fit duration, spare fields and ionosphere/UTC headers are not compared.',
                'Archive capture time and receiver clock are unqualified; agreement does not establish freshness.',
                'Source names and distinct bytes do not establish independent physical receivers or providers.',
                'Different fields can reflect conversion error, receiver fault, legitimate changes or manipulation.',
                'Attacks that preserve navigation content remain outside this diagnostic; a match is not an allow verdict.',
            ]}
    if local_format == 'ubx':
        report.update(schema='pnt-navigation-witness-v2', window_gpst_s=None,
                      selection='ALL_DECODED_UBX_ISSUES')
        report['coverage']['decoded_toc_outside_declared_day'] = sum(
            not 0 <= (row['toc'] - context.day).total_seconds() < 86400 for row in local)
        report['limits'].append(
            'UBX keeps every decoded issue, including toc outside the declared day; no capture-time window is inferred.')
    if qualify_lnav:
        from .navigation_representation import qualify_navigation_records
        report['written_decimal_schema'] = report['schema']
        report['schema'] = 'pnt-navigation-witness-v3'
        report['lnav_representation'] = qualify_navigation_records(selected, external)
    return report
