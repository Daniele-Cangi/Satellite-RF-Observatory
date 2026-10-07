"""Android clock precision, signal identity and visible invalid measurements."""

import csv
from decimal import Decimal
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from pnt.android_raw import inspect_android_raw, WEEK_NS


FIXTURE = Path(__file__).parent / 'fixtures/android20250730/pixel6_first_epoch.txt'
SOURCE = FIXTURE.read_bytes()
HEADER = SOURCE.decode().splitlines()[1][2:]
FIELDS = next(csv.reader([HEADER]))
FIRST = dict(zip(FIELDS, next(csv.reader([SOURCE.decode().splitlines()[2]]))))


def log(tmp_path, changes=None, *, rows=None):
    values = FIRST | (changes or {})
    path = tmp_path / 'android.txt'
    lines = [HEADER, *(','.join(row[field] for field in FIELDS)
                       for row in (rows if rows is not None else [values]))]
    path.write_text('# ' + '\n'.join(lines) + '\n', encoding='utf-8')
    return path


def test_real_epoch_retains_signal_identity_source_fields_and_unusable_phase():
    assert hashlib.sha256(SOURCE).hexdigest() == 'ce7af0eca97f72ffbf1370fe937faac890429a4cf43af4c8cc86743cb47408ed'
    report = inspect_android_raw(FIXTURE)
    assert report['coverage']['status_counts']['raw_rows'] == 49
    assert len(report['records']) == 8
    assert {r['signal'] for r in report['records']} == {'C1C', 'C5Q'}
    first = report['records'][0]
    assert first['pseudorange_m'] == pytest.approx(21099046.034373637, abs=1e-8)
    assert first['receiver_gpst_ns'] == '1437876922999948239.0'
    assert first['source_values'] == FIRST
    assert not first['adr_usable']  # State 16 alone is not valid carrier phase.
    assert set(report['assessments'].values()) == {'NOT_ASSESSED'}


def test_nanosecond_precision_and_fractional_bias_offset(tmp_path):
    original = inspect_android_raw(log(tmp_path))['records'][0]
    modified = inspect_android_raw(log(tmp_path, {
        'TimeNanos': str(int(FIRST['TimeNanos']) + 1),
        'BiasNanos': '0.25', 'TimeOffsetNanos': '0.125',
    }))['records'][0]
    assert modified['pseudorange_m'] - original['pseudorange_m'] == pytest.approx(
        .875 * .299792458, abs=1e-8)
    assert Decimal(modified['receiver_gpst_ns']) - Decimal(original['receiver_gpst_ns']) == Decimal('.875')


def test_week_rollover_and_negative_ranges_are_not_repaired(tmp_path):
    values = {'FullBiasNanos': str(-2000 * WEEK_NS), 'TimeNanos': '30000000',
              'ReceivedSvTimeNanos': str(WEEK_NS - 40000000)}
    row = inspect_android_raw(log(tmp_path, values))['records'][0]
    assert row['pseudorange_m'] == pytest.approx(.07 * 299792458)
    values['ReceivedSvTimeNanos'] = '40000000'
    row = inspect_android_raw(log(tmp_path, values))['records'][0]
    assert row['pseudorange_m'] == pytest.approx(-.01 * 299792458)


@pytest.mark.parametrize('state', ['0', '1', '25', '16384'])
def test_unresolved_time_remains_an_explicit_row(tmp_path, state):
    row = inspect_android_raw(log(tmp_path, {'State': state}))['records'][0]
    assert row['status'] == 'UNRESOLVED_GPS_TRANSMIT_TIME'
    assert row['pseudorange_m'] is None
    assert row['source_values']['State'] == state


@pytest.mark.parametrize('changes,status', [
    ({'FullBiasNanos': ''}, 'MISSING_FULL_BIAS'),
    ({'CodeType': ''}, 'UNSUPPORTED_GPS_SIGNAL'),
    ({'CarrierFrequencyHz': '1227600000', 'CodeType': 'L'}, 'UNSUPPORTED_GPS_SIGNAL'),
    ({'CarrierFrequencyHz': '1176450000', 'CodeType': 'C'}, 'UNSUPPORTED_GPS_SIGNAL'),
    ({'Cn0DbHz': 'NaN'}, 'INVALID_GPS_MEASUREMENT'),
    ({'TimeNanos': '1.5'}, 'INVALID_GPS_MEASUREMENT'),
    ({'TimeNanos': '1e1000'}, 'INVALID_GPS_MEASUREMENT'),
    ({'BiasNanos': '-1e1000'}, 'INVALID_GPS_MEASUREMENT'),
    ({'ReceivedSvTimeNanos': str(WEEK_NS)}, 'INVALID_GPS_MEASUREMENT'),
    ({'ConstellationType': 'NaN'}, 'INVALID_CONSTELLATION'),
])
def test_missing_unsupported_and_invalid_measurements_are_counted(tmp_path, changes, status):
    report = inspect_android_raw(log(tmp_path, changes))
    assert report['coverage']['status_counts'] == {status: 1, 'raw_rows': 1}
    assert report['records'][0]['status'] == status
    json.dumps(report, allow_nan=False)


def test_missing_optional_bias_explicit_and_clock_segments_not_merged(tmp_path):
    rows = [FIRST | {'BiasNanos': ''}, FIRST | {'HardwareClockDiscontinuityCount': '23'}]
    report = inspect_android_raw(log(tmp_path, rows=rows))
    assert report['records'][0]['bias_nanos_assumed_zero']
    assert [r['hardware_clock_discontinuity_count'] for r in report['records']] == [22, 23]
    assert len(report['records']) == 2  # Duplicates/epochs are not collapsed.


@pytest.mark.parametrize('state,usable', [('0', False), ('1', True), ('3', False),
                                         ('5', False), ('17', False), ('25', True)])
def test_phase_reset_slip_and_reported_half_cycle_ambiguity(tmp_path, state, usable):
    report = inspect_android_raw(log(tmp_path, {'AccumulatedDeltaRangeState': state}))
    assert report['records'][0]['adr_usable'] is usable


def test_non_gps_counted_without_guessing_constellation_time(tmp_path):
    report = inspect_android_raw(log(tmp_path, {'ConstellationType': '3'}))
    assert report['coverage']['status_counts'] == {'UNSUPPORTED_CONSTELLATION': 1, 'raw_rows': 1}
    assert report['records'] == []


@pytest.mark.parametrize('transform', [
    lambda content: content.replace('# Raw,', '# Missing,'),
    lambda content: content + content.splitlines()[0] + '\n',
    lambda content: content.replace(',IsFullTracking', ',State'),
    lambda content: content.rsplit(',', 1)[0] + '\n',
])
def test_ambiguous_header_or_truncated_rows_fail_closed(tmp_path, transform):
    path = log(tmp_path)
    path.write_text(transform(path.read_text()), encoding='utf-8')
    with pytest.raises(ValueError):
        inspect_android_raw(path)


def test_gzip_source_receipt_and_cli_no_overwrite(tmp_path):
    path = tmp_path / 'capture.txt.gz'
    path.write_bytes(gzip.compress(SOURCE, mtime=0))
    report = inspect_android_raw(path)
    assert report['source']['decoded_sha256'] == hashlib.sha256(SOURCE).hexdigest()
    assert report['source']['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    output = tmp_path / 'report.json'
    command = [sys.executable, '-m', 'pnt', 'android-raw', str(path), '--output', str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == report
    before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode != 0
    assert output.read_bytes() == before
