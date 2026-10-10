"""Signed UTC drift through the existing replay; no RF or live-latency claim."""

import copy
import json

import pytest

from pnt.tests.test_time_sensitivity import multi_epoch_inputs
from pnt.tests.test_time_sensitivity_sessions import session
from pnt.tests.test_gnss_time import MS, NS, compare_bracket
from pnt.time_sensitivity import assess_time_sensitivity, assess_time_sensitivity_sessions
from pnt.time_witness import compare_bracket_claim


def test_signed_drift_matches_direct_engine_with_exact_integer_midpoints():
    witness, capture = multi_epoch_inputs()
    baseline = compare_bracket(witness, capture)
    original = copy.deepcopy(baseline)
    first = baseline['records'][0]['claim']
    origin = (first['start_monotonic_ns'] + first['end_monotonic_ns']) // 2
    report = assess_time_sensitivity(baseline, drift_rates_ppm=[1, -1],
        onset_monotonic_ns=origin + 1, local_counter_resolution_ns=1)
    assert report['baseline'] == original == baseline
    assert report['offset_cases'][1]['applied_offset_ns_by_record'] == [0, 999, 1999]
    assert report['offset_cases'][2]['applied_offset_ns_by_record'] == [0, -999, -1999]
    for case in report['offset_cases']:
        for index, row in enumerate(baseline['records']):
            claim = dict(row['claim'], unix_ns=row['claim']['unix_ns'] + case['applied_offset_ns_by_record'][index])
            checks = []
            for pair in baseline['temporal_association']['attempt_pairs']:
                before, after = (witness['attempts'][pair[key]]['exchange']
                                 for key in ('before_attempt_index', 'after_attempt_index'))
                checks.append(compare_bracket_claim(before, after, claim, **witness['assumptions'],
                    max_span_ns=baseline['temporal_association']['maximum_span_ns'])['status'])
            pattern = case['record_indices_by_pattern']
            usable = set(checks) - {'INSUFFICIENT_EVIDENCE'}
            expected = ('ALL_INCONSISTENT' if usable == {'INCONSISTENT_WITH_WITNESS'} else
                        'ALL_NOT_DISTINGUISHABLE' if usable == {'NOT_DISTINGUISHABLE'} else 'MIXED')
            assert index in pattern[expected]
    zero = assess_time_sensitivity(baseline, [0], local_counter_resolution_ns=1)['offset_cases'][0]
    assert {k: v for k, v in report['offset_cases'][0].items() if k != 'utc_claim_drift_ppm'} == zero


def test_drift_summary_keeps_common_support_groups_and_nts_lookahead():
    source = session('drift', repeats=2)
    old = assess_time_sensitivity_sessions([source], [100 * MS], local_counter_resolution_ns=1)
    slow = assess_time_sensitivity_sessions([source], drift_rates_ppm=[5000, -5000], local_counter_resolution_ns=1)
    slow_cases = slow['sessions'][0]['summary']['offset_cases']
    assert slow_cases[1]['first_new_inconsistency']['common_support']['external']['applied_offset_ns'] == 5 * MS
    assert slow_cases[2]['first_new_inconsistency']['common_support']['external'] is None
    # Asymmetric synthetic intervals miss the negative slow ramp in this window.
    # A larger fixture-only challenge exercises look-ahead times in both signs.
    report = assess_time_sensitivity_sessions([source], drift_rates_ppm=[500000, -500000], local_counter_resolution_ns=1)
    summary = report['sessions'][0]['summary']
    assert summary['clock_group_record_indices'] == [[0, 1], [2, 3], [4, 5]]
    assert summary['common_clock_group_indices'] == old['sessions'][0]['summary']['common_clock_group_indices']
    for case in summary['offset_cases'][1:]:
        timing = case['first_new_inconsistency']['common_support']
        assert timing['local']['reported_epoch_elapsed_ns'] == NS
        assert timing['external']['reported_epoch_elapsed_ns'] == NS
        assert timing['external']['latest_used_nts_receive_elapsed_ns'] > NS
        assert timing['local']['latest_used_nts_receive_elapsed_ns'] is None
        assert abs(timing['external']['applied_offset_ns']) == 500 * MS
    assert all(value is None for scope in summary['offset_cases'][0]['first_new_inconsistency'].values()
               for value in scope.values())


def test_original_alarms_are_not_new_drift_detections():
    source = session('original-alarms')
    for row in source['receiver_capture']['records']:
        values = row['source_values']
        values['TimeNanos'] = str(int(values['TimeNanos']) + NS)
    report = assess_time_sensitivity_sessions([source], drift_rates_ppm=[5000, -5000], local_counter_resolution_ns=1)
    for case in report['sessions'][0]['summary']['offset_cases']:
        assert case['first_new_inconsistency']['own_support']['external'] is None
        assert case['first_new_inconsistency']['own_support']['combined'] is None


def test_failed_nts_and_unknown_association_cannot_gain_support_from_drift():
    source = session('unavailable')
    for row in source['receiver_capture']['records']:
        row['epoch_alignment_error_ns'] = None
    source['witness_report']['attempts'][1] = dict(server='synthetic-witness', status='WITNESS_UNAVAILABLE', reason='timeout')
    report = assess_time_sensitivity_sessions([source], drift_rates_ppm=[5000, -5000], local_counter_resolution_ns=1)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['sessions'][0]['sensitivity']['perturbation_profile']['onset_monotonic_ns'] is None
    assert report['totals']['witness_status_counts']['WITNESS_UNAVAILABLE'] == 1
    for case in report['sessions'][0]['summary']['offset_cases']:
        assert case['methods']['combined']['clock_groups'] == {'INSUFFICIENT_EVIDENCE': 3}
        assert all(value is None for scope in case['first_new_inconsistency'].values() for value in scope.values())


def test_each_session_has_its_own_origin_and_generator_rates_are_reusable():
    first, second = session('one'), session('two')
    shift = 10**18 + 123
    for row in second['receiver_capture']['records']:
        values = row['source_values']
        values['ChipsetElapsedRealtimeNanos'] = str(int(values['ChipsetElapsedRealtimeNanos']) + shift)
        for key in ('acquisition_start_monotonic_ns', 'acquisition_end_monotonic_ns'):
            row[key] += shift
    for attempt in second['witness_report']['attempts']:
        for key in ('send_monotonic_ns', 'receive_monotonic_ns'):
            attempt['exchange'][key] += shift
    report = assess_time_sensitivity_sessions([first, second], drift_rates_ppm=iter([5000, -5000]), local_counter_resolution_ns=1)
    a, b = [entry['sensitivity'] for entry in report['sessions']]
    assert b['perturbation_profile']['onset_monotonic_ns'] - a['perturbation_profile']['onset_monotonic_ns'] == shift
    assert [case['applied_offset_ns_by_record'] for case in a['offset_cases']] == [case['applied_offset_ns_by_record'] for case in b['offset_cases']]
    assert report['totals']['common_clock_groups'] == 4


@pytest.mark.parametrize('rates', [[], [True], [1.5], ['5000'], [5000, 5000]])
def test_invalid_rates_fail_closed(rates):
    with pytest.raises(ValueError):
        assess_time_sensitivity(session('invalid'), drift_rates_ppm=rates)


def test_drift_never_joins_counter_domains_or_combines_offset_families():
    source = session('mixed')
    source['receiver_capture']['records'][1]['capture_id'] = 'different-boot'
    with pytest.raises(ValueError, match='domain'):
        assess_time_sensitivity(source, drift_rates_ppm=[5000])
    with pytest.raises(ValueError, match='not both'):
        assess_time_sensitivity(session('offset-and-drift'), [0], drift_rates_ppm=[5000])


def test_cli_drift_summary_is_replayable_and_rejects_mixed_options(monkeypatch, tmp_path):
    from pnt.__main__ import main

    source, output = tmp_path/'source.json', tmp_path/'report.json'
    source.write_text(json.dumps(session('cli')), encoding='utf-8')
    args = ['pnt', 'time-sensitivity', str(source), '--session-summary', '--drift-ppm', '-5000',
            '--drift-ppm', '5000', '--local-counter-resolution-ns', '1', '--output', str(output)]
    monkeypatch.setattr('sys.argv', args)
    main()
    report = json.loads(output.read_bytes())
    expected = assess_time_sensitivity_sessions([json.loads(source.read_bytes())], drift_rates_ppm=[-5000, 5000], local_counter_resolution_ns=1)
    assert {k: v for k, v in report.items() if k != 'sources'} == expected
    output.unlink()
    monkeypatch.setattr('sys.argv', args + ['--offset-ns', '0'])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()
