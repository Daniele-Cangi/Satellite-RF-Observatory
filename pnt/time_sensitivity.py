"""Offline sensitivity of decoded receiver UTC claims to software offsets."""

from collections import Counter

from .gnss_time import compare_receiver_capture
from .time_witness import _compare_interval, _integer


KINDS = ('comparisons', 'bracket_comparisons')


def assess_time_sensitivity(comparison, offsets_ns):
    """Replay retained inputs, then shift only decoded UTC against fixed intervals.

    This measures conditional interval separation, not RF spoofing performance.
    Receipt counters, association, budgets, endpoint failures and decoded source
    bytes are unchanged. Stored verdicts are not used to construct the baseline.
    Every record remains in each case, including unsupported records; endpoints
    are counted separately and never vote. Zero is always included as a control.
    """
    if (not isinstance(comparison, dict)
            or comparison.get('schema') != 'pnt-gnss-time-comparison-v1'
            or not isinstance(comparison.get('assumptions'), dict)):
        raise ValueError('an existing pnt-gnss-time-comparison-v1 report is required')
    offsets = list(offsets_ns)
    if not offsets:
        raise ValueError('at least one explicit UTC claim offset is required')
    for offset in offsets:
        _integer(offset, 'UTC claim offset')
    if len(set(offsets)) != len(offsets):
        raise ValueError('UTC claim offsets must be distinct')
    offsets = [0] + [offset for offset in offsets if offset != 0]
    span = None
    if 'temporal_association' in comparison:
        association = comparison['temporal_association']
        if (not isinstance(association, dict)
                or association.get('method') != 'ADJACENT_SAME_ENDPOINT_BRACKETS'):
            raise ValueError('unsupported temporal association; no fallback')
        span = _integer(association.get('maximum_span_ns'), 'maximum_span_ns', 1)
    assumptions = comparison['assumptions']
    baseline = compare_receiver_capture(
        comparison.get('witness_report'), comparison.get('receiver_capture'),
        utc_error_ns=assumptions.get('utc_error_ns'),
        utc_error_source=assumptions.get('utc_error_source'), bracket_span_ns=span)
    windows = []
    for row in baseline['records']:
        for kind in KINDS:
            for index, result in enumerate(row.get(kind, [])):
                if result['status'] != 'INSUFFICIENT_EVIDENCE':
                    lower, upper = result['claim_minus_witness_ns']
                    windows.append(dict(source_index=row['source_index'], comparison_kind=kind,
                                        comparison_index=index, compatible_shift_ns=[-upper, -lower]))
    cases = []
    for offset in offsets:
        counts = {kind: Counter() for kind in KINDS}
        endpoints = {}
        patterns = {name: [] for name in ('INSUFFICIENT_EVIDENCE', 'ALL_NOT_DISTINGUISHABLE',
                                        'ALL_INCONSISTENT', 'MIXED')}
        for row in baseline['records']:
            usable_statuses = set()
            for kind in KINDS:
                for result in row.get(kind, []):
                    status = result['status']
                    if status != 'INSUFFICIENT_EVIDENCE':
                        claim = dict(row['claim'], unix_ns=row['claim']['unix_ns'] + offset)
                        status = _compare_interval(result['witness_interval'], claim)['status']
                        usable_statuses.add(status)
                    counts[kind][status] += 1
                    key = (kind, result.get('server'))
                    endpoints.setdefault(key, Counter())[status] += 1
            pattern = ('INSUFFICIENT_EVIDENCE' if not usable_statuses else
                       'ALL_NOT_DISTINGUISHABLE' if usable_statuses == {'NOT_DISTINGUISHABLE'} else
                       'ALL_INCONSISTENT' if usable_statuses == {'INCONSISTENT_WITH_WITNESS'} else 'MIXED')
            patterns[pattern].append(row['source_index'])
        cases.append(dict(
            utc_claim_offset_ns=offset,
            comparison_status_counts=dict(sorted(counts['comparisons'].items())),
            bracket_status_counts=dict(sorted(counts['bracket_comparisons'].items())),
            endpoint_status_counts=[dict(comparison_kind=kind, server=server,
                                         status_counts=dict(sorted(count.items())))
                                    for (kind, server), count in endpoints.items()],
            record_pattern_counts={name: len(indices) for name, indices in patterns.items()},
            record_indices_by_pattern=patterns))
    return dict(
        schema='pnt-gnss-time-sensitivity-v1', regime='EXPLORATORY_SOFTWARE_PERTURBATION',
        status=baseline['status'], baseline=baseline,
        assumptions=dict(perturbation='DECODED_UTC_CLAIM_ONLY', retained_verdicts_used=False,
                         unchanged_association_and_budgets=True, calibrated=False,
                         rf_attack_simulation=False, endpoint_vote=False,
                         record_patterns_are_descriptive=True, records_are_not_independent_samples=True),
        compatible_shift_intervals=windows, offset_cases=cases)
