"""Receiver UTC claims associated with existing NTS capture records.

This imports a trusted collector's receipts; it does not acquire a receiver,
verify RF origin or authenticate a saved NTS report to a third party.
"""

from collections import Counter
from datetime import datetime, timezone
import struct

from .time_witness import _budgets, _integer, compare_bracket_claim, compare_claim


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{name} must be a nonempty string')
    return value


def decode_timeutc(packet):
    """Decode one exact UBX-NAV-TIMEUTC frame, including transport checksum.

    UTC calendar + signed nano refer to the navigation solution epoch, not
    host receipt. Validity and tAcc are receiver assertions, not independent
    authentication or a bound on error. Leap seconds are not mapped to POSIX.
    Layout: u-blox UBX-20033631 R05, section 3.15.22.1.
    """
    from research.exploratory.pnt_rawx_recovery import ubx_packets

    if len(packet) != 28 or packet[:6] != b'\xb5\x62\x01\x21\x14\x00':
        raise ValueError('one complete 20-byte UBX-NAV-TIMEUTC payload is required')
    _, _, payload = next(ubx_packets(packet))
    tow, accuracy, nano, year, month, day, hour, minute, second, valid = struct.unpack(
        '<IIiH6B', payload)
    if valid & 7 != 7:
        raise ValueError('receiver UTC/week/time-of-week validity is unresolved')
    if second == 60:
        raise ValueError('leap-second UTC cannot be represented by this POSIX comparison')
    if not 1999 <= year <= 2099 or not -10**9 <= nano <= 10**9 or tow >= 604800000:
        raise ValueError('receiver calendar, nano or iTOW is outside the supported range')
    instant = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    elapsed = instant - datetime(1970, 1, 1, tzinfo=timezone.utc)
    unix_ns = (elapsed.days * 86400 + elapsed.seconds) * 10**9 + nano
    return dict(unix_ns=unix_ns, iTOW_ms=tow, receiver_tAcc_ns=accuracy,
                nano=nano, utc_calendar=instant.isoformat(), validity_flags=valid,
                receiver_utc_standard=valid >> 4)


def receiver_claim(record, *, utc_error_ns, utc_error_source):
    """Adapt UBX receipt or an Android clock epoch to the witness counter.

    The independently supplied age interval covers solution-to-receipt latency
    (receiver processing, serialization, buffering and collector scheduling).
    Its units are host monotonic-counter nanoseconds, not receiver time. Never
    infer it from the receiver UTC, iTOW, tAcc or a fitted offset. Android
    clock epochs require their own explicit GNSS/boottime alignment bound.
    """
    _integer(utc_error_ns, 'utc_error_ns', 0)
    _text(utc_error_source, 'utc_error_source')
    if not isinstance(record, dict):
        raise ValueError('receiver capture record must be an object')
    if 'epoch_age_budget_violation' in record:
        reason = _text(record['epoch_age_budget_violation'], 'epoch_age_budget_violation')
        raise ValueError(f'known epoch-age budget violation: {reason}')
    if record.get('source_format') == 'ANDROID_RAW_CLOCK':
        from .android_time import android_clock_claim

        return android_clock_claim(record, utc_error_ns=utc_error_ns, utc_error_source=utc_error_source)
    if record.get('source_format') not in (None, 'UBX_NAV_TIMEUTC'):
        raise ValueError('unsupported receiver UTC source_format')
    packet = bytes.fromhex(_text(record.get('packet_hex'), 'packet_hex'))
    decoded = decode_timeutc(packet)
    capture_id = _text(record.get('capture_id'), 'capture_id')
    start = _integer(record.get('receipt_start_monotonic_ns'), 'receipt_start_monotonic_ns', 0)
    end = _integer(record.get('receipt_end_monotonic_ns'), 'receipt_end_monotonic_ns', start)
    age_min = _integer(record.get('epoch_age_min_monotonic_ns'), 'epoch_age_min_monotonic_ns', 0)
    age_max = _integer(record.get('epoch_age_max_monotonic_ns'), 'epoch_age_max_monotonic_ns', age_min)
    _text(record.get('epoch_age_source'), 'epoch_age_source')
    event_start = _integer(start - age_max, 'solution epoch start_monotonic_ns', 0)
    claim = dict(capture_id=capture_id, unix_ns=decoded['unix_ns'], error_ns=utc_error_ns,
                 start_monotonic_ns=event_start, end_monotonic_ns=end - age_min,
                 source='RECEIVER_REPORTED_UTC', utc_error_source=utc_error_source)
    return claim, decoded


def _adjacent_attempt_pairs(attempts):
    """Use retained order and endpoint names only, including failed attempts."""
    previous, pairs, unnamed = {}, [], []
    for index, attempt in enumerate(attempts):
        server = attempt.get('server')
        if not isinstance(server, str) or not server.strip():
            unnamed.append(index)
            previous.clear()  # An unidentified failure may belong to any endpoint.
            continue
        if server in previous:
            pairs.append(dict(before_attempt_index=previous[server], after_attempt_index=index, server=server))
        previous[server] = index
    return pairs, unnamed


def compare_receiver_capture(witness, capture, *, utc_error_ns, utc_error_source, bracket_span_ns=None):
    """Replay every supplied receiver record against every retained endpoint.

    Reuse compare_claim's causal intervals, capture-domain check and refusal
    to extrapolate. Optional two-sided brackets add constraints from adjacent
    attempts at the same endpoint. No failed attempt is skipped; endpoints
    stay separate, without quorum, post-fit correction or ALLOW verdict.
    """
    _integer(utc_error_ns, 'utc_error_ns', 0)
    _text(utc_error_source, 'utc_error_source')
    if bracket_span_ns is not None:
        _integer(bracket_span_ns, 'bracket_span_ns', 1)
    if (not isinstance(witness, dict) or witness.get('schema') != 'pnt-internet-time-v1'
            or not isinstance(witness.get('attempts'), list)
            or not all(isinstance(a, dict) for a in witness['attempts'])
            or not isinstance(witness.get('assumptions'), dict)):
        raise ValueError('an existing pnt-internet-time-v1 witness report is required')
    budgets = {name: witness['assumptions'].get(name)
               for name in ('server_error_ns', 'rate_error_ppm')}
    _budgets(**budgets)
    if (not isinstance(capture, dict) or capture.get('schema') != 'pnt-gnss-utc-capture-v1'
            or not isinstance(capture.get('records'), list)):
        raise ValueError('a pnt-gnss-utc-capture-v1 receiver capture is required')
    _text(capture.get('receiver_source'), 'receiver_source')
    rows, record_counts, comparison_counts = [], Counter(), Counter()
    pairs, unnamed = _adjacent_attempt_pairs(witness['attempts']) if bracket_span_ns is not None else ([], [])
    bracket_counts, support = Counter(), Counter()
    for index, record in enumerate(capture['records']):
        row = dict(source_index=index, status='INSUFFICIENT_EVIDENCE', comparisons=[])
        rows.append(row)
        try:
            claim, decoded = receiver_claim(record, utc_error_ns=utc_error_ns,
                                            utc_error_source=utc_error_source)
            row.update(status='UTC_CLAIM_AVAILABLE', claim=claim, receiver_utc=decoded)
        except ValueError as error:
            row['reason'] = str(error)
        record_counts[row['status']] += 1
        for attempt_index, attempt in enumerate(witness['attempts']):
            if 'reason' in row:
                result = dict(status='INSUFFICIENT_EVIDENCE', reason=row['reason'])
            elif (attempt.get('status') != 'AUTHENTICATED_EXCHANGE'
                  or not isinstance(attempt.get('exchange'), dict)):
                result = dict(status='INSUFFICIENT_EVIDENCE', reason='no authenticated exchange in this attempt')
            else:
                result = compare_claim(attempt['exchange'], claim, **budgets)
            row['comparisons'].append(dict(attempt_index=attempt_index, server=attempt.get('server'), **result))
            comparison_counts[result['status']] += 1
        if bracket_span_ns is not None:
            row['bracket_comparisons'] = []
            for pair in pairs:
                anchors = [witness['attempts'][pair[name]]
                           for name in ('before_attempt_index', 'after_attempt_index')]
                if 'reason' in row:
                    result = dict(status='INSUFFICIENT_EVIDENCE', reason=row['reason'])
                elif any(a.get('status') != 'AUTHENTICATED_EXCHANGE'
                         or not isinstance(a.get('exchange'), dict) for a in anchors):
                    result = dict(status='INSUFFICIENT_EVIDENCE', reason='no authenticated exchange in a bracket attempt')
                elif any(a['exchange'].get('server') != pair['server'] for a in anchors):
                    result = dict(status='INSUFFICIENT_EVIDENCE', reason='bracket endpoint differs from retained attempt')
                else:
                    result = compare_bracket_claim(anchors[0]['exchange'], anchors[1]['exchange'], claim,
                                                   max_span_ns=bracket_span_ns, **budgets)
                row['bracket_comparisons'].append(dict(**pair, **result))
                bracket_counts[result['status']] += 1
            single = any(c['status'] != 'INSUFFICIENT_EVIDENCE' for c in row['comparisons'])
            bracket = any(c['status'] != 'INSUFFICIENT_EVIDENCE' for c in row['bracket_comparisons'])
            support['records_with_single_support'] += single
            support['records_with_bracket_support'] += bracket
            support['records_with_any_temporal_support'] += single or bracket
    usable = sum(comparison_counts[s] for s in ('NOT_DISTINGUISHABLE', 'INCONSISTENT_WITH_WITNESS'))
    usable += sum(bracket_counts[s] for s in ('NOT_DISTINGUISHABLE', 'INCONSISTENT_WITH_WITNESS'))
    report = dict(schema='pnt-gnss-time-comparison-v1', regime='EXPLORATORY_CAPTURE_REPLAY',
                status='CONDITIONAL_TIME_DIAGNOSTIC' if usable else 'INSUFFICIENT_EVIDENCE',
                receiver_capture=capture, witness_report=witness, records=rows,
                assumptions=dict(**budgets, utc_error_ns=utc_error_ns, utc_error_source=utc_error_source,
                                 calibrated=False, trusted_collector_and_capture_receipts=True,
                                 receiver_tAcc_used_as_error_bound=False),
                coverage=dict(receiver_records=len(rows), witness_attempts=len(witness['attempts']),
                              comparisons=sum(comparison_counts.values()),
                              record_status_counts=dict(sorted(record_counts.items())),
                              comparison_status_counts=dict(sorted(comparison_counts.items()))))
    if bracket_span_ns is not None:
        report['temporal_association'] = dict(method='ADJACENT_SAME_ENDPOINT_BRACKETS',
                                             maximum_span_ns=bracket_span_ns, attempt_pairs=pairs,
                                             unnamed_attempt_indices=unnamed,
                                             counter_rate_budget_applies_across_span=True)
        report['coverage'].update(bracket_comparisons=sum(bracket_counts.values()),
                                  bracket_status_counts=dict(sorted(bracket_counts.items())),
                                  **{name: support[name] for name in (
                                      'records_with_single_support', 'records_with_bracket_support',
                                      'records_with_any_temporal_support')})
    return report
