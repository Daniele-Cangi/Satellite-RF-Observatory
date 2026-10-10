"""Synthetic multi-session accounting; no acquisition or RF performance claim."""

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from pnt.tests.test_android_time import inputs, compare, MS, NS
from pnt.time_sensitivity import assess_time_sensitivity, assess_time_sensitivity_sessions


def session(name, *, repeats=1):
    witness, raw, _, _ = inputs(bracket=True)
    original_row = raw['records'][0]
    original_attempts = witness['attempts']
    raw['records'], witness['attempts'] = [], []
    for second in range(3):
        for repeat in range(repeats):
            row = copy.deepcopy(original_row)
            row['source_line'] += second * repeats + repeat
            for field in ('TimeNanos', 'ChipsetElapsedRealtimeNanos'):
                row['source_values'][field] = str(int(row['source_values'][field]) + second * NS)
            raw['records'].append(row)
        for original in original_attempts:
            attempt = copy.deepcopy(original)
            attempt['exchange']['capture_id'] = name
            for field in ('send_monotonic_ns', 'receive_monotonic_ns',
                          'server_receive_unix_ns', 'server_transmit_unix_ns'):
                attempt['exchange'][field] += second * NS
            witness['attempts'].append(attempt)
    raw['source']['sha256'] = hashlib.sha256(('synthetic ' + name).encode()).hexdigest()
    witness['capture_id'] = witness['capture_context']['capture_id'] = name
    witness['acquisition']['ended_monotonic_ns'] += 3 * NS
    return compare(witness, raw, bracket_span_ns=200 * MS)


def aggregate(comparisons, offsets=(-100 * MS, 100 * MS)):
    return assess_time_sensitivity_sessions(comparisons, offsets, local_counter_resolution_ns=1)


def test_sessions_reuse_existing_replay_preserve_inputs_and_ignore_saved_verdicts(monkeypatch):
    sources = [session('first', repeats=2), session('second')]
    sources[0].update(status='FAKE_SUCCESS', records=[], coverage={'receiver_records': 999999})
    before = copy.deepcopy(sources)
    monkeypatch.setattr('pnt.time_witness.probe', lambda *a, **k: pytest.fail('unexpected network'))
    report = aggregate(iter(sources), iter([-100 * MS, 100 * MS]))
    assert sources == before
    assert report['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'
    assert report['totals']['sessions'] == 2
    assert report['totals']['receiver_records'] == 9
    assert report['totals']['reported_clock_groups'] == 6
    assert report['totals']['common_records'] == 6
    assert report['totals']['common_clock_groups'] == 4
    for source, result in zip(sources, report['sessions']):
        assert result['sensitivity'] == assess_time_sensitivity(source, [-100 * MS, 100 * MS],
                                                               local_counter_resolution_ns=1)
    assert aggregate([s['sensitivity']['baseline'] for s in report['sessions']]) == report
    for case in report['totals']['offset_cases']:
        for method in ('local', 'external', 'combined'):
            assert sum(case['methods'][method]['records'].values()) == 9
            assert sum(case['methods'][method]['common_records'].values()) == 6
            assert sum(case['methods'][method]['clock_groups'].values()) == 6
            assert sum(case['methods'][method]['common_clock_groups'].values()) == 4
    zero, minus, plus = report['totals']['offset_cases']
    assert zero['methods']['combined']['common_clock_groups'] == {'NOT_DISTINGUISHABLE': 4}
    for case in (minus, plus):
        assert case['methods']['local']['common_clock_groups'] == {'NOT_DISTINGUISHABLE': 4}
        assert case['methods']['external']['common_clock_groups'] == {'INCONSISTENT': 4}
        assert case['methods']['combined']['common_clock_groups'] == {'INCONSISTENT': 4}
    assert report['assumptions']['verified_benign_originals'] is False
    assert report['assumptions']['held_out_evaluation'] is False


def test_original_alarms_and_worsening_cases_are_not_counted_as_verified_false_alarms():
    source = session('original-discordance')
    source['receiver_capture']['records'][-1]['source_values']['TimeNanos'] = str(
        int(source['receiver_capture']['records'][-1]['source_values']['TimeNanos']) + 100 * MS)
    report = aggregate([source])
    zero, minus, plus = report['totals']['offset_cases']
    assert zero['methods']['combined']['common_clock_groups'] == {'INCONSISTENT': 1, 'NOT_DISTINGUISHABLE': 1}
    assert minus['methods']['external']['common_clock_groups'] == {'INCONSISTENT': 1, 'NOT_DISTINGUISHABLE': 1}
    assert plus['methods']['external']['common_clock_groups'] == {'INCONSISTENT': 2}
    assert report['sessions'][0]['summary']['common_clock_group_indices'] == [1, 2]


def test_failed_nts_and_empty_captures_remain_sessions_without_invented_settings():
    normal, failed, empty = [session(name) for name in ('normal', 'failed', 'empty')]
    for attempt in failed['witness_report']['attempts']:
        attempt.update(status='WITNESS_UNAVAILABLE', reason='synthetic timeout')
        del attempt['exchange']
    failed['witness_report']['attempts'].append(dict(server='synthetic-server', status='NOT_ATTEMPTED'))
    empty['receiver_capture']['records'] = []
    report = aggregate([failed, normal, empty])
    assert report['totals']['sessions'] == 3
    assert report['totals']['receiver_records'] == 6
    assert report['totals']['witness_status_counts'] == {
        'AUTHENTICATED_EXCHANGE': 12, 'WITNESS_UNAVAILABLE': 6, 'NOT_ATTEMPTED': 1}
    retained = report['sessions'][0]
    assert retained['sensitivity']['baseline']['witness_report'] == failed['witness_report']
    assert retained['summary']['common_record_indices'] == []
    assert report['sessions'][2]['summary']['reported_clock_groups'] == 0


def test_unknown_alignment_remains_insufficient_for_every_case():
    sources = [session('unknown-1'), session('unknown-2')]
    for source in sources:
        for record in source['receiver_capture']['records']:
            record['epoch_alignment_error_ns'] = record['epoch_alignment_source'] = None
    report = aggregate(sources)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['totals']['common_records'] == 0
    for case in report['totals']['offset_cases']:
        for method in case['methods'].values():
            assert method['records'] == {'INSUFFICIENT_EVIDENCE': 6}
            assert method['clock_groups'] == {'INSUFFICIENT_EVIDENCE': 6}


@pytest.mark.parametrize('status', [None, '', ['invalid']])
def test_attempts_without_valid_status_remain_visible_and_never_supply_support(status):
    source = session('missing-status')
    for attempt in source['witness_report']['attempts']:
        if status is None:
            del attempt['status']
        else:
            attempt['status'] = status
    result = aggregate([source])
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['totals']['witness_status_counts'] == {'MISSING_OR_INVALID_STATUS': 6}
    assert result['totals']['common_records'] == 0
    assert result['sessions'][0]['sensitivity']['baseline']['witness_report'] == source['witness_report']


def test_conflicting_endpoints_stay_inconclusive_on_the_fixed_common_denominator():
    source = session('disagreement')
    for original in list(source['witness_report']['attempts']):
        other = copy.deepcopy(original)
        other['server'] = other['exchange']['server'] = 'other-synthetic-server'
        for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
            other['exchange'][field] += NS
        source['witness_report']['attempts'].append(other)
    result = aggregate([source])
    assert result['totals']['common_clock_groups'] == 2
    zero = result['totals']['offset_cases'][0]
    assert zero['methods']['external']['common_clock_groups'] == {'INCONCLUSIVE': 2}
    assert zero['methods']['combined']['common_clock_groups'] == {'INCONCLUSIVE': 2}
    assert result['sessions'][0]['summary']['common_clock_group_indices'] == [1, 2]
    for case in result['totals']['offset_cases']:
        assert sum(case['methods']['combined']['common_clock_groups'].values()) == 2


def test_partial_clock_groups_and_missing_identity_never_vote_or_disappear():
    source = session('partial', repeats=2)
    source['receiver_capture']['records'][3]['intake_status'] = 'UNRESOLVED_GPS_TRANSMIT_TIME'
    source['receiver_capture']['records'][-1]['source_values'] = None
    report = aggregate([source])
    summary = report['sessions'][0]['summary']
    assert summary['receiver_records'] == 6
    assert summary['reported_clock_groups'] == 3
    assert summary['unidentified_record_indices'] == [5]
    assert summary['common_clock_group_indices'] == []
    assert report['totals']['unidentified_records'] == 1
    zero = summary['offset_cases'][0]
    assert zero['methods']['external']['clock_groups']['MIXED_ROW_OUTCOMES'] == 1
    assert zero['methods']['local']['clock_groups']['MIXED_ROW_OUTCOMES'] == 1


@pytest.mark.parametrize('change', ['capture_id', 'raw_hash'])
def test_duplicate_captures_cannot_be_counted_twice(change):
    first, second = session('first'), session('second')
    if change == 'capture_id':
        second['receiver_capture']['capture_id'] = first['receiver_capture']['capture_id']
    else:
        second['receiver_capture']['android_intake']['source']['sha256'] = first['receiver_capture']['android_intake']['source']['sha256']
    with pytest.raises(ValueError, match='duplicate'):
        aggregate([first, second])


@pytest.mark.parametrize('change', ['server_error_ns', 'rate_error_ppm', 'utc_error_ns', 'alignment', 'bracket', 'resolution'])
def test_different_numerical_profiles_cannot_be_pooled(change):
    first, second = session('first'), session('second')
    if change in ('server_error_ns', 'rate_error_ppm'):
        second['witness_report']['assumptions'][change] += 1
    elif change == 'utc_error_ns':
        second['assumptions'][change] += 1
    elif change == 'alignment':
        for record in second['receiver_capture']['records']:
            record['epoch_alignment_error_ns'] += 1
    elif change == 'bracket':
        second['temporal_association']['maximum_span_ns'] += 1
    else:
        second['witness_report']['attempts'][0]['exchange']['monotonic_resolution_ns'] += 1
    with pytest.raises(ValueError, match='timing profile'):
        aggregate([first, second])


@pytest.mark.parametrize('available', [True, False])
def test_cli_multi_session_is_offline_hashed_and_refuses_overwrite(monkeypatch, tmp_path, available):
    from pnt.__main__ import main

    paths = []
    for name in ('first', 'second'):
        source = session(name)
        if not available:
            for record in source['receiver_capture']['records']:
                record['epoch_alignment_error_ns'] = record['epoch_alignment_source'] = None
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(source), encoding='utf-8')
        paths.append(path)
    output = tmp_path / 'sessions.json'
    monkeypatch.setattr('pnt.time_witness.probe', lambda *a, **k: pytest.fail('unexpected network'))
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', *map(str, paths),
        '--offset-ns', str(100 * MS), '--local-counter-resolution-ns', '1', '--output', str(output)])
    if available:
        main()
    else:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
    report = json.loads(output.read_bytes())
    assert report['sources'] == [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
    assert aggregate([s['sensitivity']['baseline'] for s in report['sessions']], [100 * MS]) == {
        k: v for k, v in report.items() if k != 'sources'}
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert output.read_bytes() == before


def test_multi_session_android_replay_needs_only_standard_library(tmp_path):
    paths = []
    for name in ('first', 'second'):
        path = tmp_path / (name + '.json')
        path.write_text(json.dumps(session(name)), encoding='utf-8')
        paths.append(str(path))
    script = """
import sys
class BlockOptional:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in ('numpy', 'scipy', 'hatanaka', 'OpenSSL', 'cryptography'):
            raise ImportError('optional dependency blocked: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
from pnt.__main__ import main
main()
"""
    result = subprocess.run([sys.executable, '-c', script, 'time-sensitivity', *paths,
        '--offset-ns', str(100 * MS), '--local-counter-resolution-ns', '1',
        '--output', str(tmp_path / 'summary.json')], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_native_reports_reuse_their_comparison_without_trusting_saved_verdicts():
    sources = [session('first'), session('second')]
    envelopes = [dict(schema='pnt-android-session-report-v1', issues=[], comparison=s, status='FAKE_SUCCESS')
                 for s in sources]
    before = copy.deepcopy(envelopes)
    assert aggregate(envelopes) == aggregate(sources)
    assert envelopes == before
    assert assess_time_sensitivity(envelopes[0], [NS]) == assess_time_sensitivity(sources[0], [NS])


@pytest.mark.parametrize('issue', ['no_comparison', 'intake_failed'])
def test_native_reports_without_admitted_comparisons_abort_instead_of_dropping_the_session(issue):
    envelope = dict(schema='pnt-android-session-report-v1', comparison=session('failed-native'), issues=[])
    if issue == 'no_comparison':
        envelope['comparison'] = None
    else:
        envelope['issues'] = ['Raw terminal inconsistent']
    with pytest.raises(ValueError, match='no admitted comparison'):
        aggregate([session('normal'), envelope])


@pytest.mark.parametrize('extra', [[], ['--onset-monotonic-ns', '0'], ['--android-clock-diagnostics']])
def test_summary_options_never_invent_a_counter_budget_or_cross_session_onset(monkeypatch, tmp_path, extra):
    from pnt.__main__ import main

    source, output = tmp_path / 'input.json', tmp_path / 'summary.json'
    source.write_text(json.dumps(session('one')), encoding='utf-8')
    resolution = ['--local-counter-resolution-ns', '1'] if extra else []
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', str(source), '--session-summary',
        '--offset-ns', str(NS), '--output', str(output), *resolution, *extra])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()


def test_single_native_report_can_opt_in_to_summary_and_duplicate_json_keys_fail_closed(monkeypatch, tmp_path):
    from pnt.__main__ import main

    source, output = tmp_path / 'input.json', tmp_path / 'summary.json'
    envelope = dict(schema='pnt-android-session-report-v1', comparison=session('one'), issues=[])
    source.write_text(json.dumps(envelope), encoding='utf-8')
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', str(source), '--session-summary',
        '--offset-ns', str(NS), '--local-counter-resolution-ns', '1', '--output', str(output)])
    main()
    report = json.loads(output.read_bytes())
    assert report['totals']['sessions'] == 1
    assert report['sources'][0]['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report['sessions'][0]['sensitivity'] == assess_time_sensitivity(envelope, [NS], local_counter_resolution_ns=1)
    output.unlink()
    source.write_text('{"schema": "first", "schema": "second"}', encoding='utf-8')
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert not output.exists()
