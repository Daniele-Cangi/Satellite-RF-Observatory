"""Receipt-gated replay agrees with direct prefixes; no alert latency claim."""

import copy
import json

import pytest

from pnt.tests.test_android_time import MS, NS
from pnt.tests.test_time_sensitivity_sessions import session
from pnt.time_sensitivity import assess_time_sensitivity, assess_time_sensitivity_sessions, _method_outcomes


def receipted_session(name='receipted', *, repeats=1):
    source = session(name, repeats=repeats)
    for row in source['receiver_capture']['records']:
        values = row['source_values']
        epoch = int(values['ChipsetElapsedRealtimeNanos'])
        values.update(CaptureId=name, CallbackStartElapsedRealtimeNanos=str(epoch + 10 * MS),
                      CallbackReadEndElapsedRealtimeNanos=str(epoch + 20 * MS))
    for attempt in source['witness_report']['attempts']:
        exchange = attempt['exchange']
        attempt.update(started_monotonic_ns=exchange['send_monotonic_ns'] - MS,
                       finished_monotonic_ns=exchange['receive_monotonic_ns'] + 30 * MS)
    return source


def assess(source, *, rates=None, offsets=()):
    return assess_time_sensitivity(source, offsets, drift_rates_ppm=rates,
                                   local_counter_resolution_ns=1, evidence_availability=True)


def at(history, elapsed):
    values = [t['outcome'] for t in history if t['available_elapsed_ns'] <= elapsed]
    return values[-1] if values else 'INSUFFICIENT_EVIDENCE'


def test_every_prefix_matches_direct_existing_engine_and_inputs_stay_identical():
    source = receipted_session(repeats=2)
    original = copy.deepcopy(source)
    result = assess(source, rates=[-500000, 500000])
    availability = result['evidence_availability']
    assert source == original
    assert {k: v for k, v in result.items() if k != 'evidence_availability'} == assess_time_sensitivity(
        source, drift_rates_ppm=[-500000, 500000], local_counter_resolution_ns=1)
    origin = availability['reference_monotonic_ns']
    times = {r['available_monotonic_ns'] for r in availability['receiver_receipts'] + availability['attempt_receipts']}
    # Probe both sides of every availability edge, including auth after receive.
    for cutoff in sorted(times | {t - 1 for t in times}):
        prefix = copy.deepcopy(source)
        for i, row in enumerate(prefix['receiver_capture']['records']):
            if availability['receiver_receipts'][i]['available_monotonic_ns'] > cutoff:
                row['intake_status'] = 'CALLBACK_NOT_YET_AVAILABLE'
        for i, attempt in enumerate(prefix['witness_report']['attempts']):
            if availability['attempt_receipts'][i]['available_monotonic_ns'] > cutoff:
                attempt['status'] = 'AUTHENTICATION_NOT_YET_COMPLETE'
        direct = assess_time_sensitivity(prefix, drift_rates_ppm=[-500000, 500000],
            onset_monotonic_ns=origin, local_counter_resolution_ns=1)
        for case, expected in zip(availability['offset_cases'], direct['offset_cases']):
            methods = _method_outcomes(expected, len(prefix['receiver_capture']['records']))
            for group, members in zip(case['clock_group_transitions'], availability['clock_group_record_indices']):
                for method, outcomes in methods.items():
                    states = {outcomes[i] for i in members}
                    outcome = next(iter(states)) if len(states) == 1 else 'MIXED_ROW_OUTCOMES'
                    assert at(group['methods'][method], cutoff - origin) == outcome


def test_authentication_completion_not_network_receipt_controls_availability():
    source = receipted_session()
    source['witness_report']['attempts'][3]['finished_monotonic_ns'] += 200 * MS
    report = assess(source, rates=[500000])
    availability = report['evidence_availability']
    origin = availability['reference_monotonic_ns']
    first = availability['offset_cases'][1]['first_new_inconsistency']['common_support']
    assert first['local']['available_elapsed_ns'] == NS + 20 * MS
    assert first['external']['available_elapsed_ns'] == NS + 300 * MS
    receive = source['witness_report']['attempts'][3]['exchange']['receive_monotonic_ns'] - origin
    history = availability['offset_cases'][1]['clock_group_transitions'][1]['methods']['external']
    assert at(history, receive) == 'INSUFFICIENT_EVIDENCE'
    assert at(history, NS + 300 * MS) == 'INCONSISTENT'


def test_later_endpoint_disagreement_revises_earlier_alarm_without_voting():
    source = receipted_session()
    extra = copy.deepcopy(source['witness_report']['attempts'][3])
    before = copy.deepcopy(source['witness_report']['attempts'][2])
    for attempt in (before, extra):
        attempt['server'] = attempt['exchange']['server'] = 'other-synthetic-endpoint'
        for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
            attempt['exchange'][field] += 500 * MS
        attempt['finished_monotonic_ns'] += 300 * MS
    source['witness_report']['attempts'].extend([before, extra])
    report = assess(source, offsets=[500 * MS])['evidence_availability']
    case = report['offset_cases'][1]
    history = case['clock_group_transitions'][1]['methods']['external']
    assert [t['outcome'] for t in history] == ['INSUFFICIENT_EVIDENCE', 'INCONSISTENT', 'INCONCLUSIVE']
    assert case['first_new_inconsistency']['common_support']['external']['available_elapsed_ns'] == (
        source['witness_report']['attempts'][3]['finished_monotonic_ns'] - report['reference_monotonic_ns'])
    assert case['final_clock_group_outcomes']['common_support']['external']['INCONCLUSIVE'] == 1


def test_failed_slot_is_never_skipped_to_form_a_future_bracket():
    source = receipted_session()
    source['witness_report']['attempts'][3].update(status='WITNESS_UNAVAILABLE', reason='retained timeout')
    del source['witness_report']['attempts'][3]['exchange']
    source['witness_report']['attempts'].append(dict(server='synthetic-server', status='NOT_ATTEMPTED'))
    report = assess(source, rates=[500000])['evidence_availability']
    assert report['attempt_receipts'][3]['status'] == 'WITNESS_UNAVAILABLE'
    assert report['attempt_receipts'][-1]['available_monotonic_ns'] is None
    assert report['offset_cases'][1]['first_new_inconsistency']['common_support']['external']['clock_group_index'] == 2
    assert all(t['outcome'] == 'INSUFFICIENT_EVIDENCE' for t in
               report['offset_cases'][1]['clock_group_transitions'][1]['methods']['external'])


def test_slow_failed_endpoint_does_not_delay_another_endpoints_completed_evidence():
    source = receipted_session()
    epoch = int(source['receiver_capture']['records'][0]['source_values']['ChipsetElapsedRealtimeNanos'])
    source['witness_report']['attempts'].insert(0, dict(server='other-endpoint',
        status='WITNESS_UNAVAILABLE', reason='retained slow timeout',
        started_monotonic_ns=epoch - MS, finished_monotonic_ns=epoch + 4 * NS))
    result = assess(source, rates=[500000])['evidence_availability']
    first = result['offset_cases'][1]['first_new_inconsistency']['common_support']['external']
    assert first['available_elapsed_ns'] == NS + 100 * MS
    assert result['attempt_receipts'][0]['available_monotonic_ns'] - epoch == 4 * NS


def test_unknown_receipt_breaks_local_segment_and_auth_never_falls_back():
    source = receipted_session()
    del source['receiver_capture']['records'][0]['source_values']['CallbackReadEndElapsedRealtimeNanos']
    del source['witness_report']['attempts'][3]['finished_monotonic_ns']
    report = assess(source, rates=[500000])['evidence_availability']
    assert report['unknown_receiver_receipts'] == report['unknown_attempt_completion_receipts'] == 1
    assert report['offset_cases'][1]['clock_group_transitions'][0]['methods']['local'] == []
    assert report['offset_cases'][1]['first_new_inconsistency']['own_support']['local']['clock_group_index'] == 2
    assert all(t['outcome'] == 'INSUFFICIENT_EVIDENCE' for t in
               report['offset_cases'][1]['clock_group_transitions'][1]['methods']['external'])


def test_missing_legacy_receipts_are_retained_as_insufficient_not_inferred_from_epoch():
    report = assess(session('legacy'), rates=[5000])['evidence_availability']
    assert report['unknown_receiver_receipts'] == 3
    assert report['unknown_attempt_completion_receipts'] == 6
    for case in report['offset_cases']:
        assert all(v is None for scope in case['first_new_inconsistency'].values() for v in scope.values())
        assert case['final_clock_group_outcomes']['own_support']['combined'] == {'INSUFFICIENT_EVIDENCE': 3}


def test_future_source_values_cannot_change_earlier_prefixes():
    source = receipted_session()
    original = assess(source, rates=[500000])['evidence_availability']
    source['receiver_capture']['records'][2]['source_values']['TimeNanos'] = 'broken future UTC'
    for attempt in source['witness_report']['attempts'][4:]:
        attempt['exchange']['server_receive_unix_ns'] += NS
        attempt['exchange']['server_transmit_unix_ns'] += NS
    poisoned = assess(source, rates=[500000])['evidence_availability']
    cutoff = NS + 500 * MS
    for old, new in zip(original['offset_cases'], poisoned['offset_cases']):
        for a, b in zip(old['clock_group_transitions'], new['clock_group_transitions']):
            for method in ('local', 'external', 'combined'):
                assert [t for t in a['methods'][method] if t['available_elapsed_ns'] <= cutoff] == [
                    t for t in b['methods'][method] if t['available_elapsed_ns'] <= cutoff]


def test_original_alarms_and_constant_relative_origin_are_not_new_local_detections():
    source = receipted_session()
    for row in source['receiver_capture']['records']:
        values = row['source_values']
        values['TimeNanos'] = str(int(values['TimeNanos']) + NS)
    report = assess(source, offsets=[500 * MS])['evidence_availability']
    assert report['offset_cases'][1]['first_new_inconsistency']['own_support']['external'] is None
    assert report['offset_cases'][1]['first_new_inconsistency']['own_support']['local'] is None


def test_callback_completion_and_event_window_both_bound_prefix_admission():
    source = receipted_session()
    row = source['receiver_capture']['records'][1]
    epoch = int(row['source_values']['ChipsetElapsedRealtimeNanos'])
    row['source_values']['CallbackStartElapsedRealtimeNanos'] = str(epoch)
    row['source_values']['CallbackReadEndElapsedRealtimeNanos'] = str(epoch)
    report = assess(source, rates=[500000])['evidence_availability']
    assert report['receiver_receipts'][1]['available_monotonic_ns'] == epoch + MS


def test_invalid_completion_stays_unknown_and_reordered_callbacks_fail_closed():
    source = receipted_session()
    source['witness_report']['attempts'][3]['finished_monotonic_ns'] = True
    report = assess(source, rates=[500000])['evidence_availability']
    assert report['unknown_attempt_completion_receipts'] == 1
    source['receiver_capture']['records'].reverse()
    with pytest.raises(ValueError, match='reordered'):
        assess(source, rates=[500000])
    with pytest.raises(ValueError, match='resolution'):
        assess_time_sensitivity(receipted_session(), [0], evidence_availability=True)


def test_cli_multi_session_availability_matches_api_with_separate_counter_origins(monkeypatch, tmp_path):
    from pnt.__main__ import main

    sources = [receipted_session('one'), receipted_session('two')]
    paths = [tmp_path/f'session-{i}.json' for i in range(2)]
    for path, source in zip(paths, sources):
        path.write_text(json.dumps(source), encoding='utf-8')
    output = tmp_path/'availability.json'
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', *(str(p) for p in paths),
        '--evidence-availability', '--drift-ppm', '500000', '--local-counter-resolution-ns', '1', '--output', str(output)])
    main()
    report = json.loads(output.read_bytes())
    assert {k: v for k, v in report.items() if k != 'sources'} == assess_time_sensitivity_sessions(
        sources, drift_rates_ppm=[500000], local_counter_resolution_ns=1, evidence_availability=True)
