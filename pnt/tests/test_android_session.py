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
    for attempt in witness['attempts']:
        if 'exchange' in attempt:
            attempt['exchange'].update(capture_id=ID, monotonic_resolution_ns=None)
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
    assert report['intake'] == inspect_android_raw_bytes(raw, RAW_NAME)
    assert report['witness_report'] == witness
    assert witness['attempts'][0]['exchange']['monotonic_resolution_ns'] is None
    assert report['witness_status_counts'] == {'AUTHENTICATED_EXCHANGE': 1, 'FAILED': 1}
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
