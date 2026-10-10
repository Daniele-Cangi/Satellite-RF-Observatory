"""ZIP -> existing engine -> phone projection; synthetic observations only."""
import copy
from contextlib import nullcontext
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from pnt.android_raw import inspect_android_raw, inspect_android_raw_bytes
from pnt.android_session import inspect_android_session, load_json, MAX_ARCHIVE_BYTES
from pnt.gnss_time import compare_receiver_capture
from pnt.tests.test_android_collector import FIXTURE, OPTIONS, inputs

ID = 'synthetic-ci'
RAW_NAME = f'pnt-clock-{ID}.txt'
NTS_NAME = f'pnt-nts-{ID}.json'
ANALYSIS = OPTIONS | dict(server_error_ns=1000, rate_error_ppm=100,
                         budget_source='synthetic uncalibrated test only',
                         monotonic_resolution_ns=1, counter_resolution_source='synthetic test only')


def native_witness():
    witness, _, _, _ = inputs()
    witness['capture_id'] = ID
    witness['capture_context'].update(capture_id=ID, gnss_file=RAW_NAME, gnss_acquired_by_this_command=True)
    witness['acquisition'].update(state='FINISHED', terminal_reason='USER_STOPPED')
    witness['assumptions'].update(server_error_ns=None, rate_error_ppm=None, calibrated=False)
    witness['protocol'] = dict(endpoints=['synthetic-server'], rounds=2, attempts_per_endpoint=2,
        planned_attempts=2, interval_ns=1, interval_s=1e-9, schedule='ROUND_START_OFFSETS', automatic_retries=False)
    exchange = witness['attempts'][0]['exchange']
    for index, attempt in enumerate(witness['attempts']):
        attempt.update(round_index=index, scheduled_round_start_monotonic_ns=
                       witness['acquisition']['started_monotonic_ns'] + index)
        attempt.update(started_monotonic_ns=exchange['send_monotonic_ns'] if index == 0
                       else exchange['receive_monotonic_ns'] + 1,
                       finished_monotonic_ns=exchange['receive_monotonic_ns'] + index * 1000)
        if attempt['status'] == 'FAILED':
            attempt['status'] = 'WITNESS_UNAVAILABLE'
        if 'exchange' in attempt:
            attempt['exchange'].update(capture_id=ID, monotonic_resolution_ns=None)
    witness['terminal'] = dict(reason='USER_STOPPED', counter_ns=witness['acquisition']['ended_monotonic_ns'],
        authenticated_exchanges=1, unavailable_attempts=1)
    return witness


def archive(tmp_path, *, raw=None, witness=None, omit_nts=False):
    data = FIXTURE.read_bytes() if raw is None else raw
    nts = native_witness() if witness is None else witness
    path = tmp_path / 'session.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(RAW_NAME, data)
        if not omit_nts:
            z.writestr(NTS_NAME, json.dumps(nts))
    return path, data, nts


def test_default_report_preserves_originals_unknown_budgets_and_every_failure(tmp_path):
    path, raw, witness = archive(tmp_path)
    report = inspect_android_session(path)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['comparison'] is None and report['analysis_options'] is None
    assert report['intake'] == inspect_android_raw_bytes(raw, RAW_NAME, expected_capture_id=ID)
    assert report['witness_report'] == witness
    assert witness['attempts'][0]['exchange']['monotonic_resolution_ns'] is None
    assert report['witness_status_counts'] == {'AUTHENTICATED_EXCHANGE': 1, 'WITNESS_UNAVAILABLE': 1}
    assert len(report['sources']['members']) == 2
    assert report['sources']['archive']['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert report['sources']['members'][0]['sha256'] == hashlib.sha256(raw).hexdigest()
    assert 'independent_budget_qualification' in report['checks_not_performed']
    assert any('not been supplied' in reason for reason in report['issues'])
    assert path.read_bytes() and raw == FIXTURE.read_bytes()


def test_explicit_assumptions_reuse_exact_existing_comparison_and_replay(tmp_path):
    path, _, original = archive(tmp_path)
    options = copy.deepcopy(ANALYSIS)
    report = inspect_android_session(path, analysis_options=options)
    result = report['comparison']
    assert not report['issues']
    assert result['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'
    assert result['assumptions']['calibrated'] is False
    assert report['witness_report'] == original
    assert options == ANALYSIS
    assert compare_receiver_capture(result['witness_report'], result['receiver_capture'],
        utc_error_ns=ANALYSIS['utc_error_ns'], utc_error_source=ANALYSIS['utc_error_source']) == result
    unknown = inspect_android_session(path, analysis_options=ANALYSIS | {
        'epoch_alignment_error_ns': None, 'epoch_alignment_source': None})
    assert unknown['comparison']['coverage']['record_status_counts'] == {'INSUFFICIENT_EVIDENCE': 3}
    assert unknown['status'] == 'INSUFFICIENT_EVIDENCE'


def test_empty_and_partial_sessions_have_a_retained_report_but_no_comparison(tmp_path):
    empty = '\n'.join(line for line in FIXTURE.read_text().splitlines()
                      if not line.startswith('Raw,') and not line.startswith('# Event,')
                      and not line.startswith('# Terminal,')).encode()
    path, _, _ = archive(tmp_path, raw=empty, omit_nts=True)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['intake']['coverage']['status_counts']['raw_rows'] == 0
    assert result['comparison'] is None and result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert len(result['issues']) == 3
    plain = tmp_path / 'empty.txt'
    plain.write_bytes(empty)
    with pytest.raises(ValueError, match='no Android Raw'):
        inspect_android_raw(plain)  # Existing command remains fail-closed.


@pytest.mark.parametrize('mutate, expected', [
    (lambda w: w.update(capture_id='other'), 'capture ID'),
    (lambda w: w['capture_context'].update(gnss_file='other.txt'), 'capture context'),
    (lambda w: w['acquisition'].update(state='IN_PROGRESS'), 'terminal missing'),
    (lambda w: w.update(assumptions=None), 'assumptions'),
])
def test_invalid_or_unclosed_witness_is_visible_and_never_silently_compared(tmp_path, mutate, expected):
    witness = native_witness()
    mutate(witness)
    path, _, _ = archive(tmp_path, witness=witness)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['comparison'] is None
    assert any(expected in reason for reason in result['issues'])


def test_cross_session_raw_row_is_rejected_even_for_an_unsupported_constellation(tmp_path):
    lines = FIXTURE.read_text().splitlines()
    header = next(csv.reader([next(line[2:] for line in lines if line.startswith('# Raw,'))]))
    column = header.index('ConstellationType')
    foreign = next(line for line in lines if line.startswith('Raw,')
                   and next(csv.reader([line]))[column] != '1')
    raw = '\n'.join(line.replace('Raw,synthetic-ci,', 'Raw,other,', 1) if line == foreign else line
                    for line in lines).encode()
    path, _, _ = archive(tmp_path, raw=raw)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['intake'] is None and result['comparison'] is None
    assert 'capture ID' in result['issues'][0]


@pytest.mark.parametrize('member', ['../outside.txt', '/outside.txt', 'pnt-nts-other.json', RAW_NAME])
def test_archive_cannot_extract_paths_mix_sessions_or_replace_duplicate_members(tmp_path, member):
    path, _, _ = archive(tmp_path, omit_nts=True)
    with zipfile.ZipFile(path, 'a') as z:
        with pytest.warns(UserWarning) if member == RAW_NAME else nullcontext():
            z.writestr(member, '{}')
    with pytest.raises(ValueError):
        inspect_android_session(path)
    assert not (tmp_path.parent / 'outside.txt').exists()


def test_bounded_zip_json_and_options_reject_ambiguous_or_implicit_inputs(tmp_path):
    path = tmp_path / 'large.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr(RAW_NAME, b'0' * (MAX_ARCHIVE_BYTES + 1))
    with pytest.raises(ValueError, match='limit'):
        inspect_android_session(path)
    for data in ('{"utc_error_ns": 1, "utc_error_ns": 2}', '{"budget": NaN}'):
        with pytest.raises(ValueError):
            load_json(data)
    path, _, _ = archive(tmp_path)
    for bad in ({}, ANALYSIS | {'hidden_default': 1}, ANALYSIS | {'server_error_ns': True},
                ANALYSIS | {'monotonic_resolution_ns': 0}, ANALYSIS | {'utc_error_source': ''}):
        with pytest.raises(ValueError):
            inspect_android_session(path, analysis_options=bad)


def test_native_zip_does_not_bypass_its_size_limit_with_nested_gzip(tmp_path):
    path, _, _ = archive(tmp_path, raw=gzip.compress(FIXTURE.read_bytes()))
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['comparison'] is None
    assert result['intake'] is None and 'nested gzip' in result['issues'][0]


@pytest.mark.parametrize('change', ['drop_slot', 'round', 'scheduled_start', 'terminal_count'])
def test_deleted_failed_nts_slots_and_altered_schedule_accounting_never_compare(tmp_path, change):
    witness = native_witness()
    if change == 'drop_slot':
        witness['attempts'].pop()  # Remove exactly the failed slot, leaving a good exchange.
    elif change == 'round':
        witness['attempts'][1]['round_index'] = 0
    elif change == 'scheduled_start':
        witness['attempts'][1]['scheduled_round_start_monotonic_ns'] += 1
    else:
        witness['terminal']['unavailable_attempts'] = 0
    path, _, _ = archive(tmp_path, witness=witness)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['comparison'] is None and result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert any('accounting' in issue or 'slot' in issue for issue in result['issues'])
    assert result['witness_report'] == witness  # Corrupt/incomplete data remains visible.


@pytest.mark.parametrize('change', ['drop_row', 'drop_event', 'event_total', 'row_total'])
def test_raw_terminal_and_per_event_counts_cannot_conceal_removed_observations(tmp_path, change):
    lines = FIXTURE.read_text().splitlines()
    if change == 'drop_row':
        lines.remove(next(line for line in lines if line.startswith('Raw,')))
    elif change == 'drop_event':
        lines.remove(next(line for line in lines if line.startswith('# Event,')))
    else:
        i = next(i for i, line in enumerate(lines) if line.startswith('# Terminal,'))
        parts = lines[i].split(',')
        parts[3 if change == 'event_total' else 4] = '3'
        lines[i] = ','.join(parts)
    path, _, _ = archive(tmp_path, raw=('\n'.join(lines) + '\n').encode())
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['intake'] is not None and result['comparison'] is None
    assert any('accounting' in issue for issue in result['issues'])


def test_legacy_fixed_endpoint_contract_detects_an_entire_deleted_unattempted_endpoint(tmp_path):
    witness = native_witness()
    endpoints = ['ptbtime1.ptb.de', 'ptbtime2.ptb.de']
    witness['protocol'].update(endpoints=endpoints, planned_attempts=4)
    witness['capture_context']['metadata'] = dict(Version='0.3.0')
    original = copy.deepcopy(witness['attempts'][0])
    attempts = []
    for round_index in range(2):
        for server in endpoints:
            slot = copy.deepcopy(original)
            slot.update(server=server, round_index=round_index,
                        scheduled_round_start_monotonic_ns=witness['acquisition']['started_monotonic_ns'] + round_index)
            slot['exchange']['server'] = server
            if attempts:  # Native cancellation retains an unattempted suffix, never resumes.
                slot.update(status='NOT_ATTEMPTED', reason='USER_STOPPED')
                del slot['exchange']
                del slot['started_monotonic_ns']
                del slot['finished_monotonic_ns']
            attempts.append(slot)
    witness['attempts'] = attempts
    witness['terminal'].update(authenticated_exchanges=1, unavailable_attempts=0)
    del witness['protocol']['endpoints']
    del witness['protocol']['planned_attempts']
    path, _, _ = archive(tmp_path, witness=witness)
    intact = inspect_android_session(path, analysis_options=ANALYSIS)
    assert intact['comparison'] is not None and 'legacy 0.3.0' in intact['format_notes'][0]
    witness['attempts'] = [a for a in attempts if a['server'] == endpoints[0]]
    path, _, _ = archive(tmp_path, witness=witness)
    incomplete = inspect_android_session(path, analysis_options=ANALYSIS)
    assert incomplete['comparison'] is None
    assert any('slot accounting' in issue for issue in incomplete['issues'])


def test_java_generated_native_schedule_is_consumed_without_rewriting_metadata(tmp_path):
    raw_path, nts_path = os.environ.get('PNT_COLLECTOR_FIXTURE'), os.environ.get('PNT_NTS_CAPTURE_FIXTURE')
    if raw_path is None or nts_path is None:
        pytest.skip('Native producers run in the Android collector matrix')
    witness = json.loads(Path(nts_path).read_text())
    path, _, _ = archive(tmp_path, raw=Path(raw_path).read_bytes(), witness=witness)
    report = inspect_android_session(path)
    assert report['witness_report'] == witness
    assert len(report['issues']) == 1 and 'not been supplied' in report['issues'][0]
    assert report['format_notes'] == ['NTS schedule bound by protocol.endpoints']
    assert witness['protocol']['planned_attempts'] == len(witness['attempts']) == 4
    assert witness['protocol']['interval_ns'] == 1


@pytest.mark.parametrize('change', ['end_inside_exchange', 'exchange_before_capture',
                                   'exchange_after_attempt', 'failed_attempt_after_capture', 'unattempted_with_timestamps'])
def test_impossible_attempt_and_exchange_windows_remain_insufficient(tmp_path, change):
    witness = native_witness()
    good, failed = witness['attempts']
    if change == 'end_inside_exchange':
        end = good['exchange']['receive_monotonic_ns'] - 1
        witness['acquisition']['ended_monotonic_ns'] = end
        witness['terminal']['counter_ns'] = end
    elif change == 'exchange_before_capture':
        good['exchange']['send_monotonic_ns'] = witness['acquisition']['started_monotonic_ns'] - 1
    elif change == 'exchange_after_attempt':
        good['finished_monotonic_ns'] = good['exchange']['receive_monotonic_ns'] - 1
    elif change == 'failed_attempt_after_capture':
        failed['finished_monotonic_ns'] = witness['acquisition']['ended_monotonic_ns'] + 1
    else:
        failed['status'] = 'NOT_ATTEMPTED'
        witness['terminal']['unavailable_attempts'] = 0
    path, _, _ = archive(tmp_path, witness=witness)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['status'] == 'INSUFFICIENT_EVIDENCE' and result['comparison'] is None
    assert result['issues']
    assert result['witness_report'] == witness


@pytest.mark.parametrize('change', ['before_schedule', 'overlapping_attempt',
                                   'duplicate_exchange', 'resumed_after_unattempted'])
def test_schedule_and_sequential_attempt_order_cannot_duplicate_or_resume_evidence(tmp_path, change):
    witness = native_witness()
    good, failed = witness['attempts']
    if change == 'before_schedule':
        interval = failed['started_monotonic_ns'] - witness['acquisition']['started_monotonic_ns'] + 1
        witness['protocol'].update(interval_ns=interval, interval_s=interval / 1e9)
        failed['scheduled_round_start_monotonic_ns'] = witness['acquisition']['started_monotonic_ns'] + interval
    elif change == 'overlapping_attempt':
        failed['started_monotonic_ns'] = good['finished_monotonic_ns'] - 1
    elif change == 'duplicate_exchange':
        duplicate = copy.deepcopy(good)
        duplicate.update(round_index=failed['round_index'],
                         scheduled_round_start_monotonic_ns=failed['scheduled_round_start_monotonic_ns'])
        witness['attempts'][1] = duplicate
        witness['terminal'].update(authenticated_exchanges=2, unavailable_attempts=0)
    else:
        good.clear()
        good.update(server='synthetic-server', round_index=0, status='NOT_ATTEMPTED', reason='USER_STOPPED',
                    scheduled_round_start_monotonic_ns=witness['acquisition']['started_monotonic_ns'])
        witness['terminal']['authenticated_exchanges'] = 0
    path, _, _ = archive(tmp_path, witness=witness)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert result['status'] == 'INSUFFICIENT_EVIDENCE' and result['comparison'] is None
    assert any('precedes' in issue or 'prefix' in issue for issue in result['issues'])
    assert result['witness_report'] == witness


def test_early_stop_retains_future_unattempted_slots_without_rejecting_valid_prefix(tmp_path):
    witness = native_witness()
    good, failed = witness['attempts']
    witness['acquisition']['ended_monotonic_ns'] = good['finished_monotonic_ns']
    witness['terminal'].update(counter_ns=good['finished_monotonic_ns'], unavailable_attempts=0)
    interval = good['finished_monotonic_ns'] - witness['acquisition']['started_monotonic_ns'] + 1
    witness['protocol'].update(interval_ns=interval, interval_s=interval / 1e9)
    failed.clear()
    failed.update(server='synthetic-server', round_index=1, status='NOT_ATTEMPTED', reason='USER_STOPPED',
                  scheduled_round_start_monotonic_ns=witness['acquisition']['started_monotonic_ns'] + interval)
    path, _, _ = archive(tmp_path, witness=witness)
    result = inspect_android_session(path, analysis_options=ANALYSIS)
    assert not result['issues'] and result['comparison'] is not None
    assert result['witness_status_counts'] == {'AUTHENTICATED_EXCHANGE': 1, 'NOT_ATTEMPTED': 1}
    assert result['witness_report'] == witness


def test_cli_retains_insufficient_report_and_does_not_overwrite(tmp_path):
    path, _, _ = archive(tmp_path)
    report_path = tmp_path / 'pc-report.json'
    command = [sys.executable, '-m', 'pnt', 'android-session', str(path), '--output', str(report_path)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2 and report_path.exists()
    content = report_path.read_bytes()
    assert json.loads(content)['comparison'] is None
    assert 'Timing comparison not run' in result.stdout
    repeat = subprocess.run(command, capture_output=True, text=True)
    assert repeat.returncode == 2 and 'already exists' in repeat.stderr
    assert report_path.read_bytes() == content


@pytest.mark.skipif(os.environ.get('PNT_ANDROID_NTS_INTEGRATION') != '1',
                    reason='Python -> Java report roundtrip runs in Android collector CI')
def test_python_report_is_read_and_bound_by_the_native_phone_projection(tmp_path):
    path, raw, witness = archive(tmp_path)
    (tmp_path / RAW_NAME).write_bytes(raw)
    (tmp_path / NTS_NAME).write_text(json.dumps(witness), encoding='utf-8')
    report_path = tmp_path / 'python-session-report.json'
    report_path.write_text(json.dumps(inspect_android_session(path, analysis_options=ANALYSIS)), encoding='utf-8')
    env = os.environ.copy()
    env['PNT_SESSION_REPORT_FIXTURE'] = str(report_path)
    collector = Path(__file__).resolve().parents[1] / 'android-collector'
    gradle = 'gradlew.bat' if os.name == 'nt' else './gradlew'
    result = subprocess.run([str(collector / gradle), '--no-daemon', 'testDebugUnitTest', '--tests',
        'org.satelliterf.observatory.clock.SessionReportTest.pythonGeneratedReportRoundtrip'],
        cwd=collector, env=env, capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
