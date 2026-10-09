"""Synthetic transport/clock cases; the public Raw fixture is not live NTS evidence."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from pnt import android_time, nts, time_witness
from pnt.__main__ import main
from pnt.android_raw import inspect_android_raw
from pnt.gnss_time import compare_receiver_capture


NS, MS = 10**9, 10**6
FIXTURE = Path(__file__).parent / 'fixtures/android20250730/pixel6_first_epoch.txt'
OPTIONS = dict(association_source='synthetic same-phone/boot association; not physical evidence',
               gps_utc_offset_seconds=18, time_scale_source='explicit synthetic conversion',
               utc_error_ns=MS, utc_error_source='uncalibrated synthetic UTC budget',
               epoch_alignment_error_ns=MS, epoch_alignment_source='synthetic timestamp association')


def inputs(*, bracket=False):
    raw = inspect_android_raw(FIXTURE)
    values = raw['records'][0]['source_values']
    epoch = int(values['ChipsetElapsedRealtimeNanos'])
    utc = int(values['TimeNanos']) - int(values['FullBiasNanos']) + android_time.GPS_UNIX_EPOCH_NS - 18 * NS
    exchange = dict(authentication='NTS_TLS13_AES_SIV_256', capture_id='synthetic-phone-boot',
                    counter_clock='CLOCK_BOOTTIME', server='synthetic-server',
                    send_monotonic_ns=epoch - 50 * MS,
                    receive_monotonic_ns=epoch + (-30 if bracket else 50) * MS,
                    server_receive_unix_ns=utc - 49 * MS, server_transmit_unix_ns=utc - 47 * MS,
                    monotonic_resolution_ns=1)
    witness = dict(schema='pnt-internet-time-v1', capture_id='synthetic-phone-boot',
                   capture_context=dict(counter_clock='CLOCK_BOOTTIME', capture_id='synthetic-phone-boot'),
                   acquisition=dict(started_monotonic_ns=epoch - 2 * NS, ended_monotonic_ns=epoch + 2 * NS),
                   assumptions=dict(server_error_ns=MS, rate_error_ppm=100),
                   attempts=[dict(server='synthetic-server', status='AUTHENTICATED_EXCHANGE', exchange=exchange)])
    if bracket:
        second = copy.deepcopy(witness['attempts'][0])
        for field in ('send_monotonic_ns', 'receive_monotonic_ns',
                      'server_receive_unix_ns', 'server_transmit_unix_ns'):
            second['exchange'][field] += 100 * MS
        witness['attempts'].append(second)
    return witness, raw, epoch, utc


def compare(witness, raw, **overrides):
    return android_time.compare_android_time(witness, raw, **{**OPTIONS, **overrides})


def test_public_intake_preserved_and_comparison_replays_with_existing_engine():
    witness, raw, epoch, utc = inputs()
    original = copy.deepcopy((witness, raw))
    result = compare(witness, raw)
    assert result['coverage']['receiver_records'] == len(raw['records']) == 8
    assert result['coverage']['comparison_status_counts'] == {'NOT_DISTINGUISHABLE': 8}
    assert result['receiver_capture']['android_intake']['source'] == raw['source']
    assert result['receiver_capture']['association'] == 'CALLER_ASSERTED_SAME_ANDROID_DEVICE_AND_BOOT'
    for index, row in enumerate(result['records']):
        assert row['claim']['unix_ns'] == utc
        assert row['claim']['start_monotonic_ns'] == epoch - MS
        assert row['claim']['end_monotonic_ns'] == epoch + MS
        assert result['receiver_capture']['records'][index]['source_values'] == raw['records'][index]['source_values']
    assert (witness, raw) == original
    restored = json.loads(json.dumps(result))
    assert compare_receiver_capture(restored['witness_report'], restored['receiver_capture'],
                                    utc_error_ns=MS, utc_error_source=OPTIONS['utc_error_source']) == result


@pytest.mark.parametrize('offset', [-NS, NS])
def test_clock_shift_remains_inconsistent_without_fitting_event_or_error_budgets(offset):
    witness, raw, _, utc = inputs()
    original = compare(witness, raw)
    for row in raw['records']:
        row['source_values']['TimeNanos'] = str(int(row['source_values']['TimeNanos']) + offset)
    result = compare(witness, raw)
    assert result['coverage']['comparison_status_counts'] == {'INCONSISTENT_WITH_WITNESS': 8}
    assert result['records'][0]['claim']['unix_ns'] == utc + offset
    for old, new in zip(original['records'], result['records']):
        for field in ('start_monotonic_ns', 'end_monotonic_ns', 'error_ns'):
            assert new['claim'][field] == old['claim'][field]


def test_file_wall_clock_per_satellite_offset_and_reported_sigmas_do_not_supply_timing_bounds():
    witness, raw, _, _ = inputs()
    original = compare(witness, raw)
    for row in raw['records']:
        row['source_values'].update(utcTimeMillis='0', TimeOffsetNanos='99999999999', LeapSecond='99',
                                    BiasUncertaintyNanos='999999999999', ElapsedRealtimeUncertaintyNanos='0')
    result = compare(witness, raw)
    assert [r['claim'] for r in result['records']] == [r['claim'] for r in original['records']]
    assert result['coverage'] == original['coverage']
    assert result['records'][0]['receiver_utc']['receiver_reported_leap_second'] == '99'
    assert result['receiver_capture']['reported_uncertainties_used_as_bounds'] is False


@pytest.mark.parametrize('bias,delta,error', [('0', 0, 0), ('1', -1, 0), ('0.25', -1, 1),
                                            ('-0.25', 0, 1), ('1e-1000', -1, 1)])
def test_sub_nanosecond_bias_conversion_has_integer_arithmetic_and_explicit_error(bias, delta, error):
    witness, raw, _, utc = inputs()
    raw['records'][0]['source_values']['BiasNanos'] = bias
    row = compare(witness, raw)['records'][0]
    assert row['claim']['unix_ns'] == utc + delta
    assert row['claim']['error_ns'] == MS + error
    assert row['receiver_utc']['integer_conversion_error_ns'] == error


@pytest.mark.parametrize('field,value', [
    ('ChipsetElapsedRealtimeNanos', ''), ('ChipsetElapsedRealtimeNanos', '-1'),
    ('ChipsetElapsedRealtimeNanos', '1.1'), ('ChipsetElapsedRealtimeNanos', str(2**63)),
    ('TimeNanos', ''), ('FullBiasNanos', ''), ('BiasNanos', ''), ('BiasNanos', 'NaN'),
    ('BiasNanos', '1e1000000'), ('HardwareClockDiscontinuityCount', '-1')])
def test_unusable_clock_field_is_retained_as_insufficient(field, value):
    witness, raw, _, _ = inputs()
    raw['records'][0]['source_values'][field] = value
    result = compare(witness, raw)
    assert len(result['records']) == 8
    assert result['records'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['records'][0]['comparisons'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['receiver_capture']['records'][0]['source_values'][field] == value


def test_missing_alignment_remains_unknown_and_outside_acquisition_is_not_associated():
    witness, raw, epoch, _ = inputs()
    unknown = compare(witness, raw, epoch_alignment_error_ns=None, epoch_alignment_source=None)
    assert unknown['status'] == 'INSUFFICIENT_EVIDENCE'
    assert unknown['coverage']['record_status_counts'] == {'INSUFFICIENT_EVIDENCE': 8}
    witness['acquisition']['ended_monotonic_ns'] = epoch
    assert compare(witness, raw)['status'] == 'INSUFFICIENT_EVIDENCE'


def test_unqualified_rows_and_clock_discontinuities_are_retained_without_joining():
    witness, raw, _, _ = inputs()
    raw['records'][0]['status'] = 'UNRESOLVED_GPS_TRANSMIT_TIME'
    raw['records'][1]['source_values']['HardwareClockDiscontinuityCount'] = '23'
    result = compare(witness, raw)
    assert result['records'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['records'][1]['receiver_utc']['hardware_clock_discontinuity_count'] == 23
    assert len(result['records']) == 8


def test_clock_domain_or_capture_mismatch_refuses_single_and_bracket_support():
    witness, raw, _, _ = inputs(bracket=True)
    result = compare(witness, raw, bracket_span_ns=200 * MS)
    assert result['coverage']['bracket_status_counts'] == {'NOT_DISTINGUISHABLE': 8}
    capture = result['receiver_capture']
    for changed in ('counter_clock', 'capture_id'):
        altered = copy.deepcopy(witness)
        for attempt in altered['attempts']:
            attempt['exchange'][changed] = 'different'
        replay = compare_receiver_capture(altered, capture, utc_error_ns=MS,
                                          utc_error_source=OPTIONS['utc_error_source'], bracket_span_ns=200 * MS)
        assert replay['status'] == 'INSUFFICIENT_EVIDENCE'
    altered = copy.deepcopy(witness)
    altered['attempts'][1]['exchange']['counter_clock'] = 'different'
    assert compare(altered, raw, bracket_span_ns=200 * MS)['status'] == 'INSUFFICIENT_EVIDENCE'
    witness['attempts'].insert(1, dict(server='synthetic-server', status='WITNESS_UNAVAILABLE', reason='failure'))
    failed = compare(witness, raw, bracket_span_ns=200 * MS)
    assert failed['coverage']['bracket_status_counts'] == {'INSUFFICIENT_EVIDENCE': 16}


@pytest.mark.parametrize('overrides', [dict(association_source=''), dict(gps_utc_offset_seconds=True),
                                     dict(gps_utc_offset_seconds=128), dict(time_scale_source=''),
                                     dict(epoch_alignment_error_ns=-1), dict(epoch_alignment_source=None),
                                     dict(epoch_alignment_error_ns=None), dict(utc_error_ns=-1)])
def test_invalid_independent_parameters_are_not_replaced_by_defaults(overrides):
    witness, raw, _, _ = inputs()
    with pytest.raises(ValueError):
        compare(witness, raw, **overrides)


def test_wrong_witness_platform_or_conflicting_context_is_not_accepted():
    witness, raw, _, _ = inputs()
    for field, value in [('counter_clock', 'CLOCK_MONOTONIC'), ('capture_id', 'other')]:
        altered = copy.deepcopy(witness)
        altered['capture_context'][field] = value
        with pytest.raises(ValueError):
            compare(altered, raw)


def fake_boottime(monkeypatch):
    clock = [NS]
    monkeypatch.setattr(nts.time, 'CLOCK_BOOTTIME', 7, raising=False)
    monkeypatch.setattr(nts.time, 'clock_getres', lambda clock_id: 2e-9, raising=False)
    monkeypatch.setattr(nts.time, 'clock_gettime_ns', lambda clock_id: clock[0], raising=False)
    monkeypatch.setattr(nts.time, 'sleep', lambda delay: clock.__setitem__(0, clock[0] + round(delay * NS)))
    return clock


def test_phone_schedule_uses_boottime_and_retains_failure_without_retry(monkeypatch):
    clock = fake_boottime(monkeypatch)
    calls = []

    def probe(server, **options):
        calls.append((server, options))
        sent = clock[0]
        clock[0] += 10 * MS
        if len(calls) == 2:
            raise nts.NTSError('synthetic transport failure')
        return dict(authentication='NTS_TLS13_AES_SIV_256', server=server, counter_clock='CLOCK_BOOTTIME',
                    send_monotonic_ns=sent, receive_monotonic_ns=clock[0], monotonic_resolution_ns=2,
                    server_receive_unix_ns=1700000000 * NS + sent + MS,
                    server_transmit_unix_ns=1700000000 * NS + sent + 2 * MS,
                    claim_start_monotonic_ns=clock[0], claim_end_monotonic_ns=clock[0],
                    host_claim_unix_ns=1700000000 * NS + clock[0], host_claim_error_ns=1)

    monkeypatch.setattr(time_witness, 'probe', probe)
    monkeypatch.setattr(nts.time, 'monotonic_ns', lambda: pytest.fail('wrong clock'))
    result = android_time.collect_android_time(['synthetic-server'], collector_source='synthetic collector',
                                               server_error_ns=MS, rate_error_ppm=100, budget_source='synthetic',
                                               rounds=3, interval_s=.1)
    assert [a['status'] for a in result['attempts']] == [
        'AUTHENTICATED_EXCHANGE', 'WITNESS_UNAVAILABLE', 'AUTHENTICATED_EXCHANGE']
    assert all(options['clock_id'] == 7 for _, options in calls)
    assert [a['scheduled_round_start_monotonic_ns'] for a in result['attempts']] == [NS, NS + 100 * MS, NS + 200 * MS]
    assert result['acquisition']['ended_monotonic_ns'] == NS + 210 * MS
    assert result['claim_source'] == 'HOST_WALL_CLOCK_NOT_GNSS'
    assert result['capture_context']['gnss_acquired_by_this_command'] is False
    assert result['attempts'][0]['exchange']['capture_id'] == result['capture_id']
    assert result['attempts'][0]['claim']['counter_clock'] == 'CLOCK_BOOTTIME'
    assert result['attempts'][0]['comparison']['status'] == 'NOT_DISTINGUISHABLE'


def test_phone_interruption_retains_all_declared_attempts(monkeypatch):
    fake_boottime(monkeypatch)

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(time_witness, 'probe', interrupt)
    result = android_time.collect_android_time(['a', 'b'], collector_source='synthetic', server_error_ns=MS,
                                               rate_error_ppm=100, budget_source='synthetic', rounds=2)
    assert result['acquisition']['interrupted'] is True
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert len(result['attempts']) == 4
    assert all(a['reason'] == 'CAPTURE_INTERRUPTED' for a in result['attempts'])
    assert [a['status'] for a in result['attempts']] == ['WITNESS_UNAVAILABLE'] + ['NOT_ATTEMPTED'] * 3


def test_unavailable_clock_refuses_before_network_with_no_pc_fallback(monkeypatch):
    monkeypatch.delattr(nts.time, 'CLOCK_BOOTTIME', raising=False)
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('network before validation'))
    with pytest.raises(ValueError, match='CLOCK_BOOTTIME'):
        android_time.collect_android_time(['a'], collector_source='synthetic', server_error_ns=MS,
                                          rate_error_ppm=100, budget_source='synthetic')


@pytest.mark.parametrize('options', [dict(rounds=0), dict(rounds=1001), dict(interval_s=0),
                                    dict(interval_s=float('nan')), dict(collector_source='')])
def test_invalid_collection_configuration_refuses_before_network(monkeypatch, options):
    fake_boottime(monkeypatch)
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('network before validation'))
    config = dict(collector_source='synthetic', server_error_ns=MS, rate_error_ppm=100, budget_source='synthetic')
    with pytest.raises(ValueError):
        android_time.collect_android_time(['a'], **{**config, **options})


def cli_arguments(witness, output):
    return ['pnt', 'android-time-compare', str(witness), str(FIXTURE),
            '--association-source', OPTIONS['association_source'], '--gps-utc-offset-seconds', '18',
            '--time-scale-source', OPTIONS['time_scale_source'], '--utc-error-ns', str(MS),
            '--utc-error-source', OPTIONS['utc_error_source'], '--output', str(output)]


def test_offline_cli_retains_unknown_timing_and_exact_source_hashes_without_overwriting(monkeypatch, tmp_path):
    witness, _, _, _ = inputs()
    source, output = tmp_path / 'witness.json', tmp_path / 'comparison.json'
    source.write_text(json.dumps(witness), encoding='utf-8')
    arguments = cli_arguments(source, output)
    monkeypatch.setattr(sys, 'argv', arguments)
    with pytest.raises(SystemExit) as exit_code:
        main()
    assert exit_code.value.code == 2
    original = output.read_bytes()
    report = json.loads(original)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['sources']['witness']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report['sources']['receiver']['sha256'] == hashlib.sha256(FIXTURE.read_bytes()).hexdigest()
    with pytest.raises(SystemExit):
        main()
    assert output.read_bytes() == original


def test_time_cli_runs_without_geometry_or_nts_dependencies(tmp_path):
    witness, _, _, _ = inputs()
    source, output = tmp_path / 'witness.json', tmp_path / 'comparison.json'
    source.write_text(json.dumps(witness), encoding='utf-8')
    arguments = cli_arguments(source, output) + ['--epoch-alignment-error-ns', str(MS),
                                                '--epoch-alignment-source', OPTIONS['epoch_alignment_source']]
    result = subprocess.run([sys.executable, '-S', '-m', 'pnt', *arguments[1:]],
                            cwd=Path(__file__).parents[2], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())['coverage']['comparison_status_counts'] == {'NOT_DISTINGUISHABLE': 8}


def test_phone_cli_saves_interrupted_attempts(monkeypatch, tmp_path):
    fake_boottime(monkeypatch)

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(time_witness, 'probe', interrupt)
    output = tmp_path / 'phone.json'
    monkeypatch.setattr(sys, 'argv', ['pnt', 'android-time-probe', '--server', 'synthetic-server',
                                    '--collector-source', 'synthetic', '--server-error-ns', str(MS),
                                    '--rate-error-ppm', '100', '--budget-source', 'synthetic',
                                    '--rounds', '2', '--output', str(output)])
    with pytest.raises(SystemExit) as exit_code:
        main()
    assert exit_code.value.code == 130
    assert len(json.loads(output.read_text())['attempts']) == 2
