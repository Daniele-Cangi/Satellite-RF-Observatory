"""Synthetic live files -> unchanged engine -> persisted PC result revisions."""
import copy
import csv
import hashlib
import io
import json
import subprocess
import sys
import zipfile

import pytest

from pnt.android_session import inspect_android_session, inspect_android_session_files
from pnt.session_monitor import AndroidSessionMonitor
from pnt.tests.test_time_availability import receipted_session
from pnt.tests.test_android_time import MS, OPTIONS
from pnt.time_sensitivity import assess_time_sensitivity, _method_outcomes


ANALYSIS = OPTIONS | dict(server_error_ns=MS, rate_error_ppm=100, budget_source='synthetic test only',
    monotonic_resolution_ns=1, counter_resolution_source='synthetic test only', bracket_span_ns=200*MS)


def native_data(*, two_endpoints=False, shifted=False):
    source = receipted_session('synthetic-monitor')
    witness = copy.deepcopy(source['witness_report'])
    identifier = witness['capture_id']
    witness['capture_context'].update(gnss_file=f'pnt-clock-{identifier}.txt', gnss_acquired_by_this_command=True,
                                      metadata=dict(Version='0.4.2', Evidence='SYNTHETIC_ONLY'))
    witness['assumptions'].update(server_error_ns=None, rate_error_ppm=None, calibrated=False)
    attempts = []
    for round_index, original in enumerate(witness['attempts']):
        for endpoint in range(2 if two_endpoints else 1):
            attempt = copy.deepcopy(original)
            attempt.update(round_index=round_index, scheduled_round_start_monotonic_ns=
                witness['acquisition']['started_monotonic_ns']+round_index*100*MS)
            attempt['exchange']['monotonic_resolution_ns'] = None
            if endpoint:
                attempt['server'] = attempt['exchange']['server'] = 'late-server'
                for name in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
                    attempt['exchange'][name] += 500*MS
                if round_index % 2:
                    attempt['finished_monotonic_ns'] += 200*MS
            attempts.append(attempt)
    witness['attempts'] = attempts
    witness['protocol'] = dict(endpoints=['synthetic-server', 'late-server'] if two_endpoints else ['synthetic-server'],
        rounds=6, attempts_per_endpoint=6, planned_attempts=len(attempts), interval_ns=100*MS,
        schedule='ROUND_START_OFFSETS', automatic_retries=False, execution='INDEPENDENT_ENDPOINTS_SPACED',
        missed_schedule='START_LATE_WITHOUT_REPLACEMENT')
    witness['acquisition'].update(state='FINISHED', terminal_reason='SCHEDULE_COMPLETED')
    witness['terminal'] = dict(reason='SCHEDULE_COMPLETED', counter_ns=witness['acquisition']['ended_monotonic_ns'],
                               authenticated_exchanges=len(attempts), unavailable_attempts=0)
    rows = source['receiver_capture']['records']
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    output.write('# Format,pnt-android-clock-collector-v1\n# CaptureId,'+identifier+'\n')
    output.write('# Metadata,Evidence,SYNTHETIC_ONLY\n')
    fields = ['Raw', 'CaptureId', 'EventIndex', 'CallbackStartElapsedRealtimeNanos', 'CallbackReadEndElapsedRealtimeNanos']
    fields += [k for k in rows[0]['source_values'] if k not in fields]
    output.write('# ')
    writer.writerow(fields)
    prefix = output.getvalue()
    pieces = []
    for index, row in enumerate(rows):
        values = dict(row['source_values'], Raw='Raw', EventIndex=str(index+1))
        if shifted and index:
            values['TimeNanos'] = str(int(values['TimeNanos'])+500*MS)
        output.write(f"# Event,{index+1},{values['CallbackStartElapsedRealtimeNanos']},{values['CallbackReadEndElapsedRealtimeNanos']},1\n")
        writer.writerow([values.get(k, '') for k in fields])
        pieces.append(output.getvalue().encode())
    output.write(f"# Terminal,SCHEDULE_COMPLETED,{witness['acquisition']['ended_monotonic_ns']},3,3\n")
    return prefix.encode(), pieces, output.getvalue().encode(), witness


def ongoing(witness, complete, active=None):
    partial = copy.deepcopy(witness)
    partial.pop('terminal')
    partial['acquisition'].update(state='IN_PROGRESS', ended_monotonic_ns=None)
    partial['acquisition'].pop('terminal_reason')
    for index, attempt in enumerate(partial['attempts']):
        if index < complete:
            continue
        attempt.pop('exchange')
        attempt.pop('finished_monotonic_ns')
        if index == active:
            attempt.update(status='WITNESS_UNAVAILABLE', reason='ATTEMPT_IN_PROGRESS')
        else:
            attempt.pop('started_monotonic_ns')
            attempt.update(status='NOT_ATTEMPTED', reason='SCHEDULE_NOT_STARTED')
    return partial


def paths(tmp_path):
    return tmp_path/'pnt-clock-synthetic-monitor.txt', tmp_path/'pnt-nts-synthetic-monitor.json'


def put(raw, nts, data, witness):
    raw.write_bytes(data)
    nts.write_text(json.dumps(witness), encoding='utf-8')


def test_ongoing_intake_compares_completed_evidence_without_relaxing_closed_zip(tmp_path):
    _, pieces, _, witness = native_data()
    raw, nts = paths(tmp_path)
    partial = ongoing(witness, complete=1, active=1)
    put(raw, nts, pieces[0], partial)
    report = inspect_android_session_files(raw, nts, analysis_options=ANALYSIS)
    assert not report['issues']
    assert report['witness_report'] == partial
    assert report['witness_report']['acquisition']['ended_monotonic_ns'] is None
    assert not report['snapshot']['session_complete']
    assert not report['snapshot']['terminal_synthesized']
    assert report['snapshot']['active_nts_attempt_indices'] == [1]
    assert report['comparison']['coverage']['records_with_any_temporal_support'] == 0
    with pytest.raises(ValueError, match='not a closed'):
        assess_time_sensitivity(report, [0], local_counter_resolution_ns=1)
    archive = tmp_path/'partial.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(raw.name, raw.read_bytes())
        z.writestr(nts.name, nts.read_bytes())
    closed = inspect_android_session(archive, analysis_options=ANALYSIS)
    assert closed['comparison'] is None
    assert any('terminal missing' in issue for issue in closed['issues'])


def test_monitor_matches_direct_prefix_engine_and_retains_later_alarm_revision(tmp_path):
    _, pieces, _, witness = native_data(two_endpoints=True, shifted=True)
    raw, nts = paths(tmp_path)
    put(raw, nts, pieces[1], ongoing(witness, complete=7, active=7))
    output = tmp_path/'monitor'
    monitor = AndroidSessionMonitor(raw, nts, output, analysis_options=ANALYSIS, local_counter_resolution_ns=1)
    first = monitor.poll()
    before = json.loads((output/first['result']).read_bytes())
    assert before['record_outcomes']['1']['combined'] == 'INCONSISTENT'
    assert monitor.poll() is None  # No invented repeated delivery.
    put(raw, nts, pieces[1], ongoing(witness, complete=8))
    second = monitor.poll()
    after = json.loads((output/second['result']).read_bytes())
    assert after['record_outcomes']['1']['combined'] == 'INCONCLUSIVE'
    assert any(c['source_index'] == 1 and c['previous']['combined'] == 'INCONSISTENT'
               and c['current']['combined'] == 'INCONCLUSIVE' for c in after['revisions'])
    for receipt in (first, second):
        folder = output/receipt['result'].split('/')[0]
        direct = inspect_android_session_files(folder/raw.name, folder/nts.name, analysis_options=ANALYSIS)
        control = assess_time_sensitivity(direct['comparison'], [0], local_counter_resolution_ns=1)
        methods = _method_outcomes(control['offset_cases'][0], len(direct['comparison']['records']))
        saved = json.loads((output/receipt['result']).read_bytes())
        assert saved['record_outcomes'] == {str(i): {m: v[i] for m, v in methods.items()} for i in range(2)}
        timing = saved['timing']
        assert timing['read_started_ns'] <= timing['input_read_completed_ns'] <= timing['analysis_completed_ns'] <= receipt['result_published_monotonic_ns']
        for source in saved['source_members']:
            assert hashlib.sha256((folder/source['name']).read_bytes()).hexdigest() == source['sha256']
    summary = monitor.finish('TEST_COMPLETED')
    assert summary['updates'] == 2 and not summary['session_complete']
    assert not summary['phone_operator_alert_latency_measured']


def test_later_nts_or_terminal_cannot_admit_epoch_wholly_after_its_own_callback(tmp_path):
    _, pieces, full, witness = native_data()
    raw, nts = paths(tmp_path)
    header = next(csv.reader([next(line[2:] for line in full.decode().splitlines() if line.startswith('# Raw,'))]))
    def future_epoch(data):
        output = io.StringIO()
        changed = False
        for line in data.decode().splitlines():
            if line.startswith('Raw,') and not changed:
                row = next(csv.reader([line]))
                receipt = int(row[header.index('CallbackReadEndElapsedRealtimeNanos')])
                row[header.index('ChipsetElapsedRealtimeNanos')] = str(receipt + 5 * MS)
                csv.writer(output, lineterminator='\n').writerow(row)
                changed = True
            else:
                output.write(line + '\n')
        return output.getvalue().encode()

    monitor = AndroidSessionMonitor(raw, nts, tmp_path/'monitor',
        analysis_options=ANALYSIS, local_counter_resolution_ns=1)
    snapshots = [(future_epoch(pieces[0]), ongoing(witness, complete=1)),
                 (future_epoch(pieces[0]), ongoing(witness, complete=2)),
                 (future_epoch(pieces[1]), ongoing(witness, complete=4)),
                 (future_epoch(full), witness)]
    for data, checkpoint in snapshots:
        put(raw, nts, data, checkpoint)
        report = inspect_android_session_files(raw, nts, analysis_options=ANALYSIS)
        assert not report['issues']  # The recording is retained; only the bad row is excluded.
        row = report['comparison']['records'][0]
        assert 'claim' not in row and 'wholly after its completed callback' in row['reason']
        control = assess_time_sensitivity(report['comparison'], [0], local_counter_resolution_ns=1)
        methods = _method_outcomes(control['offset_cases'][0], len(report['comparison']['records']))
        assert all(values[0] == 'INSUFFICIENT_EVIDENCE' for values in methods.values())
        receipt = monitor.poll()
        saved = json.loads((monitor.output/receipt['result']).read_bytes())
        assert set(saved['record_outcomes']['0'].values()) == {'INSUFFICIENT_EVIDENCE'}
        assert 'wholly after its completed callback' in saved['record_reasons']['0']
        assert (monitor.output/receipt['result']).parent.joinpath(raw.name).read_bytes() == data
    assert 'claim' in report['comparison']['records'][1]
    assert receipt['session_complete']
    archive = tmp_path/'closed.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(raw.name, raw.read_bytes())
        z.writestr(nts.name, nts.read_bytes())
    assert inspect_android_session(archive, analysis_options=ANALYSIS)['comparison'] == report['comparison']
    assert monitor.finish('REGRESSION_TEST_COMPLETED')['updates'] == 4


def test_unavailable_and_malformed_inputs_clear_current_results_and_recover(tmp_path):
    _, pieces, _, witness = native_data()
    raw, nts = paths(tmp_path)
    put(raw, nts, pieces[1], ongoing(witness, complete=4))
    monitor = AndroidSessionMonitor(raw, nts, tmp_path/'out', analysis_options=ANALYSIS, local_counter_resolution_ns=1)
    assert monitor.poll()['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'
    nts.unlink()
    assert monitor.poll()['status'] == 'INSUFFICIENT_EVIDENCE'
    assert monitor.last_update['record_outcomes'] == {}
    assert monitor.last_update['revisions']
    nts.write_text('{unfinished', encoding='utf-8')
    assert monitor.poll()['status'] == 'INSUFFICIENT_EVIDENCE'
    put(raw, nts, pieces[1], ongoing(witness, complete=4))
    assert monitor.poll()['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'
    raw.unlink()
    assert monitor.poll()['status'] == 'INSUFFICIENT_EVIDENCE'
    assert any('unavailable' in reason for reason in monitor.last_update['issues'])


@pytest.mark.parametrize('change', ['raw_truncated', 'completed_slot', 'protocol', 'context', 'acquisition'])
def test_history_cannot_silently_rewrite_inputs_already_used_for_a_result(tmp_path, change):
    _, pieces, _, witness = native_data()
    raw, nts = paths(tmp_path)
    previous = ongoing(witness, complete=4)
    put(raw, nts, pieces[1], previous)
    monitor = AndroidSessionMonitor(raw, nts, tmp_path/'out', analysis_options=ANALYSIS, local_counter_resolution_ns=1)
    monitor.poll()
    current = copy.deepcopy(previous)
    if change == 'raw_truncated':
        data = pieces[0]
    else:
        data = pieces[1]
        if change == 'completed_slot':
            current['attempts'][0]['exchange']['server_receive_unix_ns'] += 1
        elif change == 'protocol':
            current['protocol']['timeout_s'] = 20
        elif change == 'context':
            current['capture_context']['metadata']['SourceRevision'] = 'different'
        else:
            current['acquisition']['started_monotonic_ns'] -= 1
            for a in current['attempts']:
                a['scheduled_round_start_monotonic_ns'] -= 1
    put(raw, nts, data, current)
    assert monitor.poll()['status'] == 'INSUFFICIENT_EVIDENCE'
    assert monitor.last_update['record_outcomes'] == {}
    put(raw, nts, pieces[1], previous)
    assert monitor.poll()['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'


@pytest.mark.parametrize('change', ['no_completion', 'fake_terminal', 'same_endpoint_overlap', 'partial_callback'])
def test_invalid_live_checkpoint_never_manufactures_completed_evidence(tmp_path, change):
    _, pieces, _, witness = native_data()
    raw, nts = paths(tmp_path)
    partial, data = ongoing(witness, complete=4), pieces[1]
    if change == 'no_completion':
        partial['attempts'][3].pop('finished_monotonic_ns')
    elif change == 'fake_terminal':
        partial['acquisition']['ended_monotonic_ns'] = witness['acquisition']['ended_monotonic_ns']
    elif change == 'same_endpoint_overlap':
        partial = ongoing(witness, complete=1, active=1)
        partial['attempts'][2] = witness['attempts'][2]
    else:
        data = pieces[1].rsplit(b'Raw,', 1)[0]
    put(raw, nts, data, partial)
    report = inspect_android_session_files(raw, nts, analysis_options=ANALYSIS)
    assert report['comparison'] is None and report['issues']


def test_closed_file_result_is_identical_to_existing_zip_and_cli_measures_pc_publication(tmp_path):
    _, _, full, witness = native_data()
    raw, nts = paths(tmp_path)
    put(raw, nts, full, witness)
    archive = tmp_path/'closed.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr(raw.name, raw.read_bytes())
        z.writestr(nts.name, nts.read_bytes())
    report = inspect_android_session_files(raw, nts, analysis_options=ANALYSIS)
    assert report['snapshot']['session_complete']
    assert report['comparison'] == inspect_android_session(archive, analysis_options=ANALYSIS)['comparison']
    options, output = tmp_path/'options.json', tmp_path/'monitor'
    options.write_text(json.dumps(ANALYSIS), encoding='utf-8')
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw, nts)]
    cli = subprocess.run([sys.executable, '-m', 'pnt', 'android-monitor', str(raw), str(nts),
        '--analysis-options', str(options), '--local-counter-resolution-ns', '1', '--duration-s', '.1',
        '--output-directory', str(output)], text=True, capture_output=True)
    assert cli.returncode == 0, cli.stderr
    assert 'PC processing' in cli.stdout
    summary = json.loads((output/'summary.json').read_bytes())
    assert summary['session_complete'] and summary['updates'] == 1
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in (raw, nts)] == before
    repeat = subprocess.run(cli.args, capture_output=True)
    assert repeat.returncode == 2  # Earlier output cannot be replaced.


def test_monitor_loop_delivers_revisions_before_session_terminals_and_preserves_options(tmp_path):
    from pnt.session_monitor import monitor_android_files

    _, pieces, full, witness = native_data(two_endpoints=True, shifted=True)
    raw, nts = paths(tmp_path)
    put(raw, nts, pieces[1], ongoing(witness, complete=7, active=7))
    delivered = []
    options = copy.deepcopy(ANALYSIS)
    def receive(receipt):
        delivered.append(receipt)
        if len(delivered) == 1:
            put(raw, nts, pieces[1], ongoing(witness, complete=8))
            options['utc_error_ns'] = 10**12  # Caller mutation cannot tune a running monitor.
        elif len(delivered) == 2:
            put(raw, nts, full, witness)
    summary = monitor_android_files(raw, nts, tmp_path/'loop', analysis_options=options,
        local_counter_resolution_ns=1, duration_s=5, poll_interval_s=.001, on_update=receive)
    assert summary['session_complete'] and summary['updates'] == 3
    assert summary['stop_reason'] == 'SESSION_TERMINALS_OBSERVED'
    assert delivered[0]['record_outcome_counts']['combined']['INCONSISTENT'] == 1
    assert delivered[1]['record_outcome_counts']['combined']['INCONCLUSIVE'] == 1
    assert json.loads((tmp_path/'loop/options.json').read_bytes())['analysis_options']['utc_error_ns'] == ANALYSIS['utc_error_ns']
    assert len((tmp_path/'loop/updates.jsonl').read_text().splitlines()) == 3


def test_unknown_budgets_and_deadline_retain_partial_result_without_success(tmp_path):
    prefix, _, _, witness = native_data()
    raw, nts = paths(tmp_path)
    put(raw, nts, prefix, ongoing(witness, complete=0))
    output = tmp_path/'monitor'
    cli = subprocess.run([sys.executable, '-m', 'pnt', 'android-monitor', str(raw), str(nts),
        '--local-counter-resolution-ns', '1', '--duration-s', '.01', '--poll-interval-s', '.01',
        '--output-directory', str(output)], text=True, capture_output=True)
    assert cli.returncode == 2
    summary = json.loads((output/'summary.json').read_bytes())
    assert summary['stop_reason'] == 'DURATION_LIMIT' and not summary['session_complete']
    update = json.loads((output/summary['last_result']).read_bytes())
    assert update['record_outcomes'] == {}
    assert any('not been supplied' in issue for issue in update['issues'])
