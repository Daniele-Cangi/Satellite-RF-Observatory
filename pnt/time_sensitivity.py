"""Offline sensitivity of decoded receiver UTC claims to software offsets."""

from collections import Counter
from datetime import datetime, timedelta, timezone
import re

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


def assess_time_sensitivity(comparison, offsets_ns=(), *, local_counter_resolution_ns=None,
                            onset_monotonic_ns=None, android_clock_diagnostics=False,
                            drift_rates_ppm=None):
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
    Signed integer drift rates change decoded UTC only, starting at an explicit
    onset or the first admitted event midpoint. Integer shifts truncate toward
    zero; no float epoch arithmetic, fit, budget change or live latency claim.
    """
    if isinstance(comparison, dict) and comparison.get('schema') == 'pnt-android-session-report-v1':
        issues = comparison.get('issues')
        if not isinstance(issues, list) or issues or not isinstance(comparison.get('comparison'), dict):
            raise ValueError('Android session report has no admitted comparison; retain its intake/budget issues')
        comparison = comparison['comparison']
    if (not isinstance(comparison, dict)
            or comparison.get('schema') != 'pnt-gnss-time-comparison-v1'
            or not isinstance(comparison.get('assumptions'), dict)):
        raise ValueError('an existing pnt-gnss-time-comparison-v1 report is required')
    offsets = list(offsets_ns)
    if drift_rates_ppm is not None and offsets:
        raise ValueError('choose constant/step offsets or drift rates, not both')
    if drift_rates_ppm is None and not offsets:
        raise ValueError('at least one explicit UTC claim offset is required')
    for offset in offsets:
        _integer(offset, 'UTC claim offset')
    if len(set(offsets)) != len(offsets):
        raise ValueError('UTC claim offsets must be distinct')
    offsets = [0] + [offset for offset in offsets if offset != 0]
    rates = None
    if drift_rates_ppm is not None:
        rates = list(drift_rates_ppm)
        if not rates:
            raise ValueError('at least one explicit UTC claim drift rate is required')
        for rate in rates:
            _integer(rate, 'UTC claim drift rate ppm')
        if len(set(rates)) != len(rates):
            raise ValueError('UTC claim drift rates must be distinct')
        rates = [0] + [rate for rate in rates if rate != 0]
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
    drift_origin = onset_monotonic_ns
    if rates is not None:
        domains = {(r['claim']['capture_id'], r['claim'].get('counter_clock'))
                   for r in baseline['records'] if 'claim' in r}
        if len(domains) > 1:
            raise ValueError('drift requires one reported capture/counter domain; no joined origin')
        if drift_origin is None:
            drift_origin = min(((r['claim']['start_monotonic_ns'] + r['claim']['end_monotonic_ns']) // 2
                                for r in baseline['records'] if 'claim' in r), default=None)
    windows = []
    for row in baseline['records']:
        for kind in KINDS:
            for index, result in enumerate(row.get(kind, [])):
                if result['status'] != 'INSUFFICIENT_EVIDENCE':
                    lower, upper = result['claim_minus_witness_ns']
                    windows.append(dict(source_index=row['source_index'], comparison_kind=kind,
                                        comparison_index=index, compatible_shift_ns=[-upper, -lower]))
    cases, baseline_paired = [], None
    specifications = [(offset, 0) for offset in offsets] if rates is None else [(0, rate) for rate in rates]
    for offset, rate in specifications:
        counts = {kind: Counter() for kind in KINDS}
        endpoints = {}
        patterns = {name: [] for name in ('INSUFFICIENT_EVIDENCE', 'ALL_NOT_DISTINGUISHABLE',
                                        'ALL_INCONSISTENT', 'MIXED')}
        claims, applied_offsets, external_patterns = [], [], []
        for row in baseline['records']:
            claim, applied = None, None
            if 'claim' in row:
                midpoint = (row['claim']['start_monotonic_ns'] + row['claim']['end_monotonic_ns']) // 2
                if rates is None:
                    applied = offset if onset_monotonic_ns is None or midpoint >= onset_monotonic_ns else 0
                else:
                    elapsed = max(0, midpoint - drift_origin)
                    applied = (1 if rate >= 0 else -1) * (abs(rate) * elapsed // 1000000)
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
        if rates is not None:
            cases[-1]['utc_claim_drift_ppm'] = rate
        if rates is not None or onset_monotonic_ns is not None or local_counter_resolution_ns is not None:
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
    if rates is not None:
        report['perturbation_profile'] = dict(mode='LINEAR_DRIFT_BY_REPORTED_EVENT_MIDPOINT',
            onset_monotonic_ns=drift_origin,
            onset_source='EXPLICIT_COUNTER' if onset_monotonic_ns is not None else 'FIRST_ADMITTED_EVENT_MIDPOINT',
            rounding='SIGNED_INTEGER_TRUNCATION_TOWARD_ZERO',
            clock_domains_joined=False, physical_rf_onset_known=False)
    elif onset_monotonic_ns is not None:
        report['perturbation_profile'] = dict(mode='STEP_BY_REPORTED_EVENT_MIDPOINT',
                                              onset_monotonic_ns=onset_monotonic_ns)
    elif local_counter_resolution_ns is not None:
        report['perturbation_profile'] = dict(mode='WHOLE_CAPTURE_CONSTANT')
    return report


_CLOCK_FIELDS = ('ChipsetElapsedRealtimeNanos', 'TimeNanos', 'FullBiasNanos',
                 'BiasNanos', 'HardwareClockDiscontinuityCount')
_METHODS = ('local', 'external', 'combined')
_COHERENT_PAIRED = {'BOTH_INCONSISTENT', 'LOCAL_ONLY_INCONSISTENT',
                    'EXTERNAL_ONLY_INCONSISTENT', 'NEITHER_INCONSISTENT'}


def _session_profile(baseline):
    """Compare numerical assumptions, retaining each session's provenance text."""
    capture = baseline['receiver_capture']
    records = capture['records']
    if any(r.get('source_format') != 'ANDROID_RAW_CLOCK' for r in records):
        raise ValueError('session summaries currently require Android Raw clock captures')
    profile = {name: baseline['assumptions'][name]
               for name in ('server_error_ns', 'rate_error_ppm', 'utc_error_ns')}
    profile['bracket_span_ns'] = baseline.get('temporal_association', {}).get('maximum_span_ns')
    profile['counter_clock'] = capture.get('counter_clock')
    for name in ('epoch_alignment_error_ns', 'gps_utc_offset_seconds'):
        values = set()
        for record in records:
            value = record.get(name)
            if value is not None and type(value) is not int:
                raise ValueError(f'invalid {name} in the session profile')
            values.add(value)
        if len(values) > 1:
            raise ValueError(f'session has multiple {name} values; no shared profile')
        if values:
            profile[name] = next(iter(values))
    resolutions = {
        a['exchange'].get('monotonic_resolution_ns') for a in baseline['witness_report']['attempts']
        if isinstance(a.get('exchange'), dict) and a.get('status') == 'AUTHENTICATED_EXCHANGE'} - {None}
    if any(type(value) is not int or value < 1 for value in resolutions):
        raise ValueError('invalid NTS counter resolution in the session profile')
    if resolutions:
        profile['nts_counter_resolutions_ns'] = sorted(resolutions)
    return profile


def _method_outcomes(case, total):
    local = ['INSUFFICIENT_EVIDENCE'] * total
    external, combined = list(local), list(local)
    for row in case['local_comparisons']:
        local[row['source_index']] = ('INCONSISTENT' if row['status'] == 'INCONSISTENT_LOCAL_CONTINUITY'
                                     else row['status'])
    for pattern, indices in case['record_indices_by_pattern'].items():
        outcome = {'ALL_INCONSISTENT': 'INCONSISTENT', 'ALL_NOT_DISTINGUISHABLE': 'NOT_DISTINGUISHABLE',
                   'MIXED': 'INCONCLUSIVE', 'INSUFFICIENT_EVIDENCE': 'INSUFFICIENT_EVIDENCE'}[pattern]
        for index in indices:
            external[index] = outcome
    for pattern, indices in case['paired_record_indices_by_pattern'].items():
        outcome = ('NOT_DISTINGUISHABLE' if pattern == 'NEITHER_INCONSISTENT' else
                   'INCONSISTENT' if pattern in _COHERENT_PAIRED else
                   'INCONCLUSIVE' if pattern == 'EXTERNAL_DISAGREEMENT' else 'INSUFFICIENT_EVIDENCE')
        for index in indices:
            combined[index] = outcome
    return dict(local=local, external=external, combined=combined)


def _outcome_counts(values):
    return dict(sorted(Counter(values).items()))


def _summarize_session(sensitivity):
    baseline = sensitivity['baseline']
    records = baseline['receiver_capture']['records']
    groups, unidentified = {}, []
    for index, record in enumerate(records):
        values = record.get('source_values')
        if not isinstance(values, dict):
            values = {}
        key = tuple(values.get(name) for name in _CLOCK_FIELDS)
        if all(isinstance(value, str) and value.strip() for value in key):
            groups.setdefault(key, []).append(index)
        else:
            unidentified.append(index)
    group_indices = list(groups.values())
    original = _method_outcomes(sensitivity['offset_cases'][0], len(records))
    # Admission only: endpoint disagreement remains on this denominator. No
    # selection by alarm outcome, and no new support selected for a challenge.
    common = [i for i in range(len(records))
              if all(original[m][i] != 'INSUFFICIENT_EVIDENCE' for m in ('local', 'external'))]
    common_set = set(common)
    common_groups = [i for i, indices in enumerate(group_indices) if set(indices) <= common_set]
    cases = []
    for case in sensitivity['offset_cases']:
        methods = _method_outcomes(case, len(records))
        counts = {}
        for method, values in methods.items():
            group_values = []
            for indices in group_indices:
                outcomes = {values[i] for i in indices}
                group_values.append(next(iter(outcomes)) if len(outcomes) == 1 else 'MIXED_ROW_OUTCOMES')
            counts[method] = dict(records=_outcome_counts(values),
                                  common_records=_outcome_counts(values[i] for i in common),
                                  clock_groups=_outcome_counts(group_values),
                                  common_clock_groups=_outcome_counts(group_values[i] for i in common_groups))
        cases.append(dict(utc_claim_offset_ns=case['utc_claim_offset_ns'], methods=counts))
        if 'utc_claim_drift_ppm' in case:
            cases[-1]['utc_claim_drift_ppm'] = case['utc_claim_drift_ppm']
            cases[-1]['first_new_inconsistency'] = _first_drift_epochs(
                sensitivity, case, original, methods, group_indices, common_groups)
    return dict(receiver_records=len(records), reported_clock_groups=len(group_indices),
                clock_group_record_indices=group_indices, unidentified_record_indices=unidentified,
                common_record_indices=common, common_clock_group_indices=common_groups,
                witness_status_counts=_outcome_counts(
                    a['status'] if isinstance(a.get('status'), str) and a['status'].strip()
                    else 'MISSING_OR_INVALID_STATUS' for a in baseline['witness_report']['attempts']),
                offset_cases=cases)


def _first_drift_epochs(sensitivity, case, original, methods, groups, common_groups):
    """First wholly ND -> inconsistent group, retaining NTS look-ahead metadata.

    This is offline event-time separation, not the time an online alert fired.
    Missing/mixed groups and original alarms are never promoted to detections.
    """
    baseline = sensitivity['baseline']
    origin = sensitivity['perturbation_profile']['onset_monotonic_ns']
    result = {scope: {method: None for method in _METHODS} for scope in ('own_support', 'common_support')}
    if origin is None:
        return result
    for scope, indices in (('own_support', range(len(groups))), ('common_support', common_groups)):
        for method in _METHODS:
            candidates = []
            for group_index in indices:
                members = groups[group_index]
                if not all(original[method][i] == 'NOT_DISTINGUISHABLE'
                           and methods[method][i] == 'INCONSISTENT' for i in members):
                    continue
                epochs = {(baseline['records'][i]['claim']['start_monotonic_ns']
                           + baseline['records'][i]['claim']['end_monotonic_ns']) // 2 for i in members}
                if len(epochs) != 1:
                    continue  # No single reported event time for this metadata group.
                epoch = next(iter(epochs))
                receipts = []
                if method != 'local':
                    for i in members:
                        for kind in KINDS:
                            for check in baseline['records'][i].get(kind, []):
                                if check['status'] == 'INSUFFICIENT_EVIDENCE':
                                    continue
                                anchors = ([check['attempt_index']] if kind == 'comparisons' else
                                           [check['before_attempt_index'], check['after_attempt_index']])
                                receipts.extend(baseline['witness_report']['attempts'][a]['exchange']['receive_monotonic_ns']
                                                for a in anchors)
                candidates.append((epoch, group_index, dict(clock_group_index=group_index,
                    reported_epoch_elapsed_ns=epoch - origin,
                    applied_offset_ns=case['applied_offset_ns_by_record'][members[0]],
                    latest_used_nts_receive_elapsed_ns=max(receipts) - origin if receipts else None)))
            if candidates:
                result[scope][method] = min(candidates, key=lambda candidate: candidate[:2])[2]
    return result


def assess_time_sensitivity_sessions(comparisons, offsets_ns=(), *, local_counter_resolution_ns,
                                     drift_rates_ppm=None):
    """Descriptive multi-session aggregation of the existing paired replay.

    Whole-capture offsets or drift from each session's first admitted epoch.
    Do not join counter domains, fit a budget or
    interpret original-log alarms as verified false alarms. Full per-session
    replays retain every failure; duplicate capture IDs/known Raw hashes cannot
    count as additional sessions. Metadata groups and sessions are not IID trials.
    """
    _integer(local_counter_resolution_ns, 'local_counter_resolution_ns', 1)
    comparisons, offsets = list(comparisons), list(offsets_ns)
    if drift_rates_ppm is not None:
        drift_rates_ppm = list(drift_rates_ppm)
    if not comparisons:
        raise ValueError('at least one comparison session is required')
    sessions, ids, raw_hashes, profile = [], set(), set(), None
    for comparison in comparisons:
        sensitivity = assess_time_sensitivity(comparison, offsets,
            local_counter_resolution_ns=local_counter_resolution_ns, drift_rates_ppm=drift_rates_ppm)
        baseline = sensitivity['baseline']
        capture = baseline['receiver_capture']
        capture_id = capture.get('capture_id')
        if not isinstance(capture_id, str) or not capture_id.strip():
            raise ValueError('session capture_id is required; no invented session identity')
        intake = capture.get('android_intake')
        source = intake.get('source') if isinstance(intake, dict) else None
        raw_hash = source.get('sha256') if isinstance(source, dict) else None
        if raw_hash is not None:
            if not isinstance(raw_hash, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', raw_hash):
                raise ValueError('Raw source hash must be a 64-digit hexadecimal SHA-256 when supplied')
            # Canonicalize the identity key only; retained source text is unchanged.
            raw_hash = raw_hash.lower()
        if capture_id in ids or (raw_hash is not None and raw_hash in raw_hashes):
            raise ValueError('duplicate capture ID or Raw source hash; not an additional session')
        ids.add(capture_id)
        if raw_hash is not None:
            raw_hashes.add(raw_hash)
        current = _session_profile(baseline)
        if profile is not None and any(profile[k] != current[k] for k in profile.keys() & current.keys()):
            raise ValueError('sessions do not share the same numerical timing profile; no pooling')
        # A capture with no rows or authenticated NTS exchange does not observe
        # every setting. Retain it without assigning other sessions' missing values.
        profile = dict(profile or {}, **current)
        sessions.append(dict(capture_id=capture_id, sensitivity=sensitivity,
                             summary=_summarize_session(sensitivity)))
    totals = dict(sessions=len(sessions), receiver_records=0, reported_clock_groups=0,
                  unidentified_records=0, common_records=0, common_clock_groups=0,
                  witness_status_counts={}, offset_cases=[])
    for case in sessions[0]['summary']['offset_cases']:
        totals['offset_cases'].append(dict(utc_claim_offset_ns=case['utc_claim_offset_ns'],
            methods={m: {unit: {} for unit in ('records', 'common_records', 'clock_groups', 'common_clock_groups')}
                     for m in _METHODS}))
        if 'utc_claim_drift_ppm' in case:
            totals['offset_cases'][-1]['utc_claim_drift_ppm'] = case['utc_claim_drift_ppm']
    for session in sessions:
        summary = session['summary']
        for name in ('receiver_records', 'reported_clock_groups'):
            totals[name] += summary[name]
        for target, source in (('unidentified_records', 'unidentified_record_indices'),
                               ('common_records', 'common_record_indices'),
                               ('common_clock_groups', 'common_clock_group_indices')):
            totals[target] += len(summary[source])
        totals['witness_status_counts'] = dict(Counter(totals['witness_status_counts'])
                                              + Counter(summary['witness_status_counts']))
        for total, case in zip(totals['offset_cases'], summary['offset_cases']):
            for method in _METHODS:
                for unit, counts in case['methods'][method].items():
                    total['methods'][method][unit] = dict(Counter(total['methods'][method][unit]) + Counter(counts))
    report = dict(schema='pnt-gnss-time-session-summary-v1', regime='EXPLORATORY_SOFTWARE_PERTURBATION',
                status='CONDITIONAL_TIME_DIAGNOSTIC' if totals['common_records'] else 'INSUFFICIENT_EVIDENCE',
                timing_profile=dict(profile, local_counter_resolution_ns=local_counter_resolution_ns),
                assumptions=dict(calibrated=False, verified_benign_originals=False, rf_attack_simulation=False,
                                 held_out_evaluation=False, sessions_and_clock_groups_are_not_independent_trials=True),
                rules=dict(perturbation='WHOLE_CAPTURE_DECODED_UTC_ONLY',
                           combined='EXISTING_PAIRED_PATTERN_REQUIRES_BOTH_METHODS',
                           disagreement='INCONCLUSIVE_WITHOUT_ENDPOINT_VOTE',
                           common_support='ZERO_CASE_NON_INSUFFICIENT_LOCAL_AND_EXTERNAL_FIXED_FOR_ALL_OFFSETS',
                           clock_groups='IDENTICAL_REPORTED_CLOCK_FIELDS; MIXED_ROW_OUTCOMES_NEVER_VOTE',
                           profile='MATCH_OBSERVED_SETTINGS_WITHOUT_FILLING_MISSING_SESSION_VALUES',
                           totals='DESCRIPTIVE_SUMS_WITHOUT_PERFORMANCE_OR_POPULATION_ESTIMATE'),
                sessions=sessions, totals=totals)
    if drift_rates_ppm is not None:
        report['rules']['perturbation'] = 'DECODED_UTC_LINEAR_DRIFT_FROM_EACH_SESSION_FIRST_ADMITTED_MIDPOINT'
        report['rules']['detection_timing'] = 'FIRST_NEW_INCONSISTENT_REPORTED_EPOCH; NTS_RECEIPTS_RETAINED; NOT_LIVE_ALERT_LATENCY'
    return report
