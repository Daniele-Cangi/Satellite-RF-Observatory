"""Offline sensitivity of decoded receiver UTC claims to software offsets."""

from collections import Counter
from datetime import datetime, timedelta, timezone

from .gnss_time import compare_receiver_capture
from .time_witness import _compare_interval, _elapsed_bounds, _integer


KINDS = ('comparisons', 'bracket_comparisons')


def _utc_month_span(claim):
    """Calendar domains of the original UTC interval, without float rounding.

    Leap seconds can occur at UTC month ends (RFC 3339 section 5.7). Without
    a qualified leap table, local POSIX continuity cannot bridge that boundary,
    even when no second=60 record survived. Do not infer a leap from residuals.
    """
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    months = []
    for value in (claim['unix_ns'] - claim['error_ns'], claim['unix_ns'] + claim['error_ns']):
        instant = epoch + timedelta(seconds=value // 10**9)
        months.append((instant.year, instant.month))
    return months


def _local_elapsed_checks(rows, claims, *, counter_resolution_ns, rate_error_ppm):
    """Fixed segment-anchor continuity; no external UTC or exchange inputs.

    A shared UTC origin is unobservable. Anchor error and current-claim error
    both propagate, with the same declared counter-rate/association bounds.
    Never reanchor to an inconsistent claim. Invalid records, changed capture
    domains, explicit hardware discontinuities, reordered counters and possible
    leap-second boundaries break a segment and remain visible. Boundary checks
    use original claims so perturbations cannot change admission or segmentation.
    Repeated anchor epochs add no elapsed evidence.
    """
    results, anchor, domain, previous_epoch = [], None, None, None
    for row, claim in zip(rows, claims):
        result = dict(source_index=row['source_index'], status='INSUFFICIENT_EVIDENCE')
        results.append(result)
        if claim is None:
            result['reason'] = row['reason']
            anchor, domain, previous_epoch = None, None, None
            continue
        current_domain = (claim['capture_id'], claim.get('counter_clock'), claim['source'],
                          row['receiver_utc'].get('hardware_clock_discontinuity_count'))
        epoch = (claim['start_monotonic_ns'] + claim['end_monotonic_ns']) // 2
        if domain == current_domain and previous_epoch is not None and epoch < previous_epoch:
            result['reason'] = 'reordered receiver counter; segment broken'
            anchor, domain, previous_epoch = None, None, None
            continue
        previous_epoch = epoch
        try:
            # Public replay rows retain the unshifted claim; standalone helper
            # callers may supply only their original claims.
            months = _utc_month_span(row.get('claim', claim))
        except (OverflowError, ValueError):
            result['reason'] = 'UTC calendar outside supported range; segment broken'
            anchor, domain, previous_epoch = None, None, None
            continue
        if months[0] != months[1]:
            result['reason'] = 'UTC uncertainty crosses a possible leap-second boundary; segment broken'
            anchor, domain, previous_epoch = None, None, None
            continue
        if anchor is None or domain != current_domain:
            anchor, domain = (row['source_index'], claim, months[0]), current_domain
            result['reason'] = 'segment anchor; no elapsed-time comparison'
            continue
        index, first, first_month = anchor
        if first_month != months[0]:
            anchor = (row['source_index'], claim, months[0])
            result['reason'] = 'UTC month boundary; leap-second continuity not qualified; new segment anchor'
            continue
        result['anchor_source_index'] = index
        if (claim['start_monotonic_ns'] == first['start_monotonic_ns']
                and claim['end_monotonic_ns'] == first['end_monotonic_ns']
                and claim['unix_ns'] == first['unix_ns']):
            result['reason'] = 'repeated segment anchor epoch; no elapsed-time comparison'
            continue
        # Reported midpoint order does not prove physical order when epoch
        # brackets overlap. Expand quantization first, retaining negative lags.
        minimum = claim['start_monotonic_ns'] - first['end_monotonic_ns'] - 2 * counter_resolution_ns
        maximum = claim['end_monotonic_ns'] - first['start_monotonic_ns'] + 2 * counter_resolution_ns
        elapsed_lower = (_elapsed_bounds(minimum, 0, rate_error_ppm)[0] if minimum >= 0 else
                         -_elapsed_bounds(-minimum, 0, rate_error_ppm)[1])
        elapsed_upper = _elapsed_bounds(maximum, 0, rate_error_ppm)[1]
        lower = first['unix_ns'] - first['error_ns'] + elapsed_lower
        upper = first['unix_ns'] + first['error_ns'] + elapsed_upper
        check = _compare_interval(dict(lower_unix_ns=lower, upper_unix_ns=upper, width_ns=upper - lower), claim)
        result.update(status='INCONSISTENT_LOCAL_CONTINUITY' if check['separation_ns'] else 'NOT_DISTINGUISHABLE',
                      conditional_on_declared_budgets=True,
                      local_predicted_utc_interval=check['witness_interval'],
                      claim_minus_local_prediction_ns=check['claim_minus_witness_ns'],
                      separation_ns=check['separation_ns'])
    return results


def _paired_pattern(local_status, external_pattern):
    if local_status == 'INSUFFICIENT_EVIDENCE' or external_pattern == 'INSUFFICIENT_EVIDENCE':
        return 'INSUFFICIENT_EVIDENCE'
    if external_pattern == 'MIXED':
        return 'EXTERNAL_DISAGREEMENT'
    local = local_status == 'INCONSISTENT_LOCAL_CONTINUITY'
    external = external_pattern == 'ALL_INCONSISTENT'
    return ('BOTH_INCONSISTENT' if local and external else 'LOCAL_ONLY_INCONSISTENT' if local else
            'EXTERNAL_ONLY_INCONSISTENT' if external else 'NEITHER_INCONSISTENT')


def _android_clock_diagnostics(baseline, local):
    """Decompose original admitted clocks using the existing local anchors.

    Reuse decoded GPST and integer parsing; no new time conversion, fitting,
    budget or verdict. Optional receiver uncertainty fields remain raw metadata.
    A hardware-clock/counter mismatch cannot identify which side is inaccurate.
    """
    from .android_raw import _integer as raw_integer

    fields = ('TimeUncertaintyNanos', 'BiasUncertaintyNanos', 'DriftNanosPerSecond',
              'DriftUncertaintyNanosPerSecond', 'ElapsedRealtimeUncertaintyNanos',
              'ChipsetElapsedRealtimeUncertaintyNanos')
    records, clocks, epochs = [], {}, set()
    for row, check in zip(baseline['records'], local):
        index = row['source_index']
        source = baseline['receiver_capture']['records'][index]
        result = dict(source_index=index, status='UNAVAILABLE', original_local_status=check['status'])
        records.append(result)
        if source.get('source_format') != 'ANDROID_RAW_CLOCK':
            result['reason'] = 'not an Android Raw clock record'
            continue
        values = source.get('source_values')
        if isinstance(values, dict):
            result['receiver_reported_metadata'] = {name: values.get(name) for name in fields}
        if 'claim' not in row:
            result['reason'] = row['reason']
            continue
        decoded = row['receiver_utc']
        hardware = raw_integer(values, 'TimeNanos')
        full_bias = raw_integer(values, 'FullBiasNanos')
        gpst = decoded['receiver_gpst_floor_ns']
        counter = decoded['chipset_elapsed_realtime_ns']
        clocks[index] = dict(hardware_time_ns=hardware, full_bias_ns=full_bias,
                             integer_bias_ns=hardware - full_bias - gpst,
                             counter_ns=counter, receiver_utc_ns=row['claim']['unix_ns'],
                             gps_utc_offset_ns=decoded['gps_utc_offset_seconds'] * 10**9)
        epochs.add((row['claim']['capture_id'], counter, gpst, decoded['hardware_clock_discontinuity_count']))
        result['status'] = 'ADMITTED_CLOCK_METADATA_ONLY'
    for result, check in zip(records, local):
        index, anchor = result['source_index'], check.get('anchor_source_index')
        if index not in clocks or anchor is None or check['status'] == 'INSUFFICIENT_EVIDENCE':
            continue
        current, first = clocks[index], clocks[anchor]
        changes = {name: current[name] - first[name] for name in current}
        result.update(status='COMPONENT_DECOMPOSITION', anchor_source_index=anchor,
                      changes_ns=changes,
                      receiver_minus_counter_change_ns=changes['receiver_utc_ns'] - changes['counter_ns'],
                      hardware_minus_counter_change_ns=changes['hardware_time_ns'] - changes['counter_ns'])
    return dict(scope='ORIGINAL_ADMITTED_ANDROID_CLOCKS',
                status_counts=dict(sorted(Counter(row['status'] for row in records).items())),
                distinct_admitted_clock_epochs=len(epochs),
                uses_existing_local_anchors=True, software_offsets_applied=False,
                reported_uncertainties_used_as_bounds=False, budgets_fitted=False,
                cause_attributed=False, records_are_not_independent_samples=True, records=records)


def assess_time_sensitivity(comparison, offsets_ns, *, local_counter_resolution_ns=None,
                            onset_monotonic_ns=None, android_clock_diagnostics=False):
    """Replay retained inputs, then shift only decoded UTC against fixed intervals.

    This measures conditional interval separation, not RF spoofing performance.
    Receipt counters, association, budgets, endpoint failures and decoded source
    bytes are unchanged. Stored verdicts are not used to construct the baseline.
    Every record remains in each case, including unsupported records; endpoints
    are counted separately and never vote. Zero is always included as a control.
    Optional local continuity and a step at a declared counter midpoint reuse
    this replay, with no independent absolute-time claim for the local channel.
    Optional Android component diagnostics describe original admitted clocks;
    they never change comparison support, budgets or software cases.
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
    if local_counter_resolution_ns is not None:
        _integer(local_counter_resolution_ns, 'local_counter_resolution_ns', 1)
    if onset_monotonic_ns is not None:
        _integer(onset_monotonic_ns, 'onset_monotonic_ns', 0)
    if type(android_clock_diagnostics) is not bool:
        raise ValueError('android_clock_diagnostics must be a boolean')
    if android_clock_diagnostics and local_counter_resolution_ns is None:
        raise ValueError('Android clock diagnostics require the explicit local counter resolution')
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
    cases, baseline_paired = [], None
    for offset in offsets:
        counts = {kind: Counter() for kind in KINDS}
        endpoints = {}
        patterns = {name: [] for name in ('INSUFFICIENT_EVIDENCE', 'ALL_NOT_DISTINGUISHABLE',
                                        'ALL_INCONSISTENT', 'MIXED')}
        claims, applied_offsets, external_patterns = [], [], []
        for row in baseline['records']:
            claim, applied = None, None
            if 'claim' in row:
                midpoint = (row['claim']['start_monotonic_ns'] + row['claim']['end_monotonic_ns']) // 2
                applied = offset if onset_monotonic_ns is None or midpoint >= onset_monotonic_ns else 0
                claim = dict(row['claim'], unix_ns=row['claim']['unix_ns'] + applied)
            claims.append(claim)
            applied_offsets.append(applied)
            usable_statuses = set()
            for kind in KINDS:
                for result in row.get(kind, []):
                    status = result['status']
                    if status != 'INSUFFICIENT_EVIDENCE':
                        status = _compare_interval(result['witness_interval'], claim)['status']
                        usable_statuses.add(status)
                    counts[kind][status] += 1
                    key = (kind, result.get('server'))
                    endpoints.setdefault(key, Counter())[status] += 1
            pattern = ('INSUFFICIENT_EVIDENCE' if not usable_statuses else
                       'ALL_NOT_DISTINGUISHABLE' if usable_statuses == {'NOT_DISTINGUISHABLE'} else
                       'ALL_INCONSISTENT' if usable_statuses == {'INCONSISTENT_WITH_WITNESS'} else 'MIXED')
            patterns[pattern].append(row['source_index'])
            external_patterns.append(pattern)
        cases.append(dict(
            utc_claim_offset_ns=offset,
            comparison_status_counts=dict(sorted(counts['comparisons'].items())),
            bracket_status_counts=dict(sorted(counts['bracket_comparisons'].items())),
            endpoint_status_counts=[dict(comparison_kind=kind, server=server,
                                         status_counts=dict(sorted(count.items())))
                                    for (kind, server), count in endpoints.items()],
            record_pattern_counts={name: len(indices) for name, indices in patterns.items()},
            record_indices_by_pattern=patterns))
        if onset_monotonic_ns is not None or local_counter_resolution_ns is not None:
            cases[-1]['applied_offset_ns_by_record'] = applied_offsets
        if local_counter_resolution_ns is not None:
            local = _local_elapsed_checks(baseline['records'], claims,
                                          counter_resolution_ns=local_counter_resolution_ns,
                                          rate_error_ppm=baseline['assumptions']['rate_error_ppm'])
            paired = {name: [] for name in ('INSUFFICIENT_EVIDENCE', 'EXTERNAL_DISAGREEMENT',
                                           'BOTH_INCONSISTENT', 'LOCAL_ONLY_INCONSISTENT',
                                           'EXTERNAL_ONLY_INCONSISTENT', 'NEITHER_INCONSISTENT')}
            paired_patterns = []
            for row, pattern in zip(local, external_patterns):
                outcome = _paired_pattern(row['status'], pattern)
                paired[outcome].append(row['source_index'])
                paired_patterns.append(outcome)
            if baseline_paired is None:
                baseline_paired = paired_patterns
            transitions = Counter(zip(baseline_paired, paired_patterns))
            cases[-1].update(local_comparisons=local,
                             local_status_counts=dict(sorted(Counter(row['status'] for row in local).items())),
                             paired_pattern_counts={name: len(indices) for name, indices in paired.items()},
                             paired_record_indices_by_pattern=paired,
                             paired_transition_counts=[dict(baseline_pattern=before, case_pattern=after, records=count)
                                                       for (before, after), count in sorted(transitions.items())])
    report = dict(
        schema='pnt-gnss-time-sensitivity-v1', regime='EXPLORATORY_SOFTWARE_PERTURBATION',
        status=baseline['status'], baseline=baseline,
        assumptions=dict(perturbation='DECODED_UTC_CLAIM_ONLY', retained_verdicts_used=False,
                         unchanged_association_and_budgets=True, calibrated=False,
                         rf_attack_simulation=False, endpoint_vote=False,
                         record_patterns_are_descriptive=True, records_are_not_independent_samples=True),
        compatible_shift_intervals=windows, offset_cases=cases)
    if local_counter_resolution_ns is not None:
        report['local_control'] = dict(method='ELAPSED_UTC_FROM_SEGMENT_ANCHOR',
                                       counter_resolution_ns=local_counter_resolution_ns,
                                       rate_error_ppm=baseline['assumptions']['rate_error_ppm'],
                                       uses_external_utc_or_exchanges=False,
                                       absolute_utc_origin='UNKNOWN', no_reanchor_on_inconsistency=True,
                                       independent_local_absolute_utc_control='NOT_EVALUATED',
                                       paired_patterns_are_descriptive=True)
    if android_clock_diagnostics:
        report['android_clock_diagnostics'] = _android_clock_diagnostics(baseline, cases[0]['local_comparisons'])
    if onset_monotonic_ns is not None:
        report['perturbation_profile'] = dict(mode='STEP_BY_REPORTED_EVENT_MIDPOINT',
                                              onset_monotonic_ns=onset_monotonic_ns)
    elif local_counter_resolution_ns is not None:
        report['perturbation_profile'] = dict(mode='WHOLE_CAPTURE_CONSTANT')
    return report
