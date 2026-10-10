"""Collector serialization/intake compatibility; every observation is synthetic."""
import copy
import json
import os
from pathlib import Path

import pytest

from pnt.android_raw import inspect_android_raw
from pnt.android_time import GPS_UNIX_EPOCH_NS, compare_android_time
from pnt.gnss_time import compare_receiver_capture


FIXTURE = Path(__file__).parent / 'fixtures/android_collector/synthetic-collector.txt'
OPTIONS = dict(association_source='synthetic same-phone/boot; not physical evidence',
               gps_utc_offset_seconds=18, time_scale_source='synthetic conversion',
               utc_error_ns=1000, utc_error_source='synthetic uncalibrated budget',
               epoch_alignment_error_ns=1000, epoch_alignment_source='synthetic association')


def inputs():
    raw = inspect_android_raw(FIXTURE)
    epoch = int(raw['records'][0]['source_values']['ChipsetElapsedRealtimeNanos'])
    # 0.25 ns BiasNanos uses the existing floor/ceil conversion, never float GPST.
    utc = 9007199254741003 + 1400000000000000000 - 1 + GPS_UNIX_EPOCH_NS - 18 * 10**9
    exchange = dict(authentication='NTS_TLS13_AES_SIV_256', capture_id='synthetic-phone',
                    counter_clock='CLOCK_BOOTTIME', server='synthetic-server',
                    send_monotonic_ns=epoch - 50_000_000,
                    receive_monotonic_ns=epoch + 50_000_000,
                    server_receive_unix_ns=utc - 49_000_000,
                    server_transmit_unix_ns=utc - 47_000_000,
                    monotonic_resolution_ns=1)
    witness = dict(schema='pnt-internet-time-v1', capture_id='synthetic-phone',
                   capture_context=dict(counter_clock='CLOCK_BOOTTIME', capture_id='synthetic-phone'),
                   acquisition=dict(started_monotonic_ns=epoch - 10**9, ended_monotonic_ns=epoch + 10**9),
                   assumptions=dict(server_error_ns=1000, rate_error_ppm=100),
                   attempts=[dict(server='synthetic-server', status='AUTHENTICATED_EXCHANGE', exchange=exchange),
                             dict(server='synthetic-server', status='FAILED', error='synthetic timeout')])
    return witness, raw, epoch, utc


def test_java_generated_output_matches_checked_in_synthetic_fixture():
    generated = os.environ.get('PNT_COLLECTOR_FIXTURE')
    if generated is None:
        pytest.skip('Java producer comparison runs in Android collector CI')
    assert Path(generated).read_bytes() == FIXTURE.read_bytes()


def test_existing_intake_retains_clock_metadata_empty_events_and_all_raw_accounting():
    _, raw, _, _ = inputs()
    assert raw['coverage']['status_counts'] == {
        'NORMALIZED': 3, 'UNSUPPORTED_CONSTELLATION': 1, 'raw_rows': 4}
    first, _, missing = raw['records']
    assert first['source_values']['TimeNanos'] == '9007199254741003'
    assert first['source_values']['FullBiasNanos'] == '-1400000000000000000'
    assert first['source_values']['CallbackStartElapsedRealtimeNanos'] == '123456790012346'
    assert first['source_values']['ElapsedRealtimeUncertaintyNanos'] == ''
    assert first['source_values']['HasElapsedRealtimeUncertaintyNanos'] == 'false'
    assert missing['source_values']['ChipsetElapsedRealtimeNanos'] == ''
    comments = raw['source']['comments']
    assert any(line.startswith('# Event,4,123456793012346,123456793012401,0,') for line in comments)
    assert '# Terminal,USER_STOPPED,123456794012345,4,4' in comments
    assert set(raw['assessments'].values()) == {'NOT_ASSESSED'}


def test_callback_timestamps_never_replace_missing_gnss_epoch_and_existing_replay_is_exact():
    witness, raw, epoch, utc = inputs()
    report = compare_android_time(witness, raw, **OPTIONS)
    assert report['coverage']['comparison_status_counts'] == {
        'INSUFFICIENT_EVIDENCE': 4, 'NOT_DISTINGUISHABLE': 2}
    assert report['records'][0]['claim']['unix_ns'] == utc
    assert report['records'][0]['claim']['start_monotonic_ns'] == epoch - 1000
    assert report['records'][2]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert 'claim' not in report['records'][2]
    restored = json.loads(json.dumps(report))
    assert compare_receiver_capture(restored['witness_report'], restored['receiver_capture'],
                                    utc_error_ns=1000, utc_error_source=OPTIONS['utc_error_source']) == report
    assert len(report['witness_report']['attempts']) == 2


def test_callback_latency_presence_flags_and_reported_sigmas_do_not_fit_admission_or_budgets():
    witness, raw, _, _ = inputs()
    baseline = compare_android_time(witness, raw, **OPTIONS)
    modified = copy.deepcopy(raw)
    for row in modified['records']:
        row['source_values'].update(CallbackStartElapsedRealtimeNanos='0',
                                   CallbackReadEndElapsedRealtimeNanos=str(2**63 - 1),
                                   HasElapsedRealtimeUncertaintyNanos='true',
                                   ElapsedRealtimeUncertaintyNanos='0', TimeUncertaintyNanos='0')
    report = compare_android_time(witness, modified, **OPTIONS)
    assert [row.get('claim') for row in report['records']] == [row.get('claim') for row in baseline['records']]
    assert report['coverage'] == baseline['coverage']
    unknown = compare_android_time(witness, modified, **(OPTIONS | dict(
        epoch_alignment_error_ns=None, epoch_alignment_source=None)))
    assert unknown['coverage']['record_status_counts'] == {'INSUFFICIENT_EVIDENCE': 3}
    assert unknown['receiver_capture']['reported_uncertainties_used_as_bounds'] is False
