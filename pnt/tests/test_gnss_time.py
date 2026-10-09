import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import struct

import pytest

from pnt.gnss_time import compare_receiver_capture, decode_timeutc
from pnt.time_witness import compare_claim


NS = 10**9
MS = 10**6
UTC = 1700000000 * NS
COUNTER = NS


def utc_packet(offset_ns=0, *, nano=None, valid=7, accuracy=900000000, tow=1000, second=None):
    seconds, fraction = divmod(50 * MS + offset_ns, NS)
    instant = datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc) + timedelta(seconds=seconds)
    payload = struct.pack('<IIiH6B', tow, accuracy, fraction if nano is None else nano,
                          instant.year, instant.month, instant.day, instant.hour, instant.minute,
                          instant.second if second is None else second, valid)
    body = b'\x01\x21\x14\x00' + payload
    first = second_checksum = 0
    for byte in body:
        first = (first + byte) & 255
        second_checksum = (second_checksum + first) & 255
    return b'\xb5\x62' + body + bytes((first, second_checksum))


def inputs(offset_ns=0, *, forward_ms=1, backward_ms=97):
    exchange = dict(authentication='NTS_TLS13_AES_SIV_256', capture_id='synthetic-common-counter',
                    send_monotonic_ns=COUNTER,
                    receive_monotonic_ns=COUNTER + (forward_ms + 2 + backward_ms) * MS,
                    server_receive_unix_ns=UTC + forward_ms * MS,
                    server_transmit_unix_ns=UTC + (forward_ms + 2) * MS,
                    monotonic_resolution_ns=1)
    witness = dict(schema='pnt-internet-time-v1',
                   assumptions=dict(server_error_ns=MS, rate_error_ppm=100),
                   attempts=[dict(server='synthetic-witness', status='AUTHENTICATED_EXCHANGE', exchange=exchange)])
    capture = dict(schema='pnt-gnss-utc-capture-v1', receiver_source='synthetic UBX; no physical receiver',
                   records=[dict(packet_hex=utc_packet(offset_ns).hex(), capture_id='synthetic-common-counter',
                                 receipt_start_monotonic_ns=COUNTER + 80 * MS,
                                 receipt_end_monotonic_ns=COUNTER + 82 * MS,
                                 epoch_age_min_monotonic_ns=30 * MS,
                                 epoch_age_max_monotonic_ns=32 * MS,
                                 epoch_age_source='independent synthetic event schedule')])
    return witness, capture


def compare(witness, capture, *, error_ns=MS):
    return compare_receiver_capture(witness, capture, utc_error_ns=error_ns,
                                    utc_error_source='uncalibrated synthetic UTC budget')


def bracket_inputs(offset_ns=0):
    witness, capture = inputs(offset_ns, backward_ms=17)
    first = witness['attempts'][0]
    first['exchange']['server'] = first['server']
    second = copy.deepcopy(first)
    for field in ('send_monotonic_ns', 'receive_monotonic_ns',
                  'server_receive_unix_ns', 'server_transmit_unix_ns'):
        second['exchange'][field] += 100 * MS
    witness['attempts'].append(second)
    return witness, capture


def compare_bracket(witness, capture):
    return compare_receiver_capture(witness, capture, utc_error_ns=MS,
                                    utc_error_source='uncalibrated synthetic UTC budget', bracket_span_ns=200 * MS)


@pytest.mark.parametrize('offset,status', [(0, 'NOT_DISTINGUISHABLE'),
                                         (NS, 'INCONSISTENT_WITH_WITNESS'),
                                         (-NS, 'INCONSISTENT_WITH_WITNESS')])
def test_brackets_add_record_coverage_without_changing_single_exchange_results(offset, status):
    witness, capture = bracket_inputs(offset)
    original = copy.deepcopy((witness, capture))
    single = compare(witness, capture)
    assert single['status'] == 'INSUFFICIENT_EVIDENCE'
    assert 'temporal_association' not in single
    assert 'bracket_comparisons' not in single['records'][0]
    result = compare_bracket(witness, capture)
    row = result['records'][0]
    assert row['comparisons'] == single['records'][0]['comparisons']
    assert row['bracket_comparisons'][0]['status'] == status
    assert result['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'
    assert result['coverage']['comparisons'] == 2
    assert result['coverage']['bracket_comparisons'] == 1
    assert result['coverage']['records_with_single_support'] == 0
    assert result['coverage']['records_with_bracket_support'] == 1
    assert result['coverage']['records_with_any_temporal_support'] == 1
    assert (witness, capture) == original
    restored = json.loads(json.dumps(result))
    assert compare_bracket(restored['witness_report'], restored['receiver_capture']) == result


def test_adjacent_endpoint_pairs_keep_failures_and_do_not_bridge_them():
    witness, capture = bracket_inputs()
    failed = dict(server='synthetic-witness', status='WITNESS_UNAVAILABLE', reason='test failure')
    witness['attempts'].insert(1, failed)
    result = compare_bracket(witness, capture)
    assert result['temporal_association']['attempt_pairs'] == [
        dict(before_attempt_index=0, after_attempt_index=1, server='synthetic-witness'),
        dict(before_attempt_index=1, after_attempt_index=2, server='synthetic-witness')]
    assert result['coverage']['bracket_status_counts'] == {'INSUFFICIENT_EVIDENCE': 2}
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['witness_report']['attempts'][1] == failed


def test_interleaved_endpoints_stay_separate_and_do_not_vote_on_contradictions():
    witness, capture = bracket_inputs()
    other = copy.deepcopy(witness['attempts'])
    for attempt in other:
        attempt['server'] = attempt['exchange']['server'] = 'other-endpoint'
        for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
            attempt['exchange'][field] += NS
    witness['attempts'] = [witness['attempts'][0], other[0], witness['attempts'][1], other[1]]
    result = compare_bracket(witness, capture)
    assert [(p['before_attempt_index'], p['after_attempt_index'])
            for p in result['temporal_association']['attempt_pairs']] == [(0, 2), (1, 3)]
    assert [c['status'] for c in result['records'][0]['bracket_comparisons']] == [
        'NOT_DISTINGUISHABLE', 'INCONSISTENT_WITH_WITNESS']
    assert result['coverage']['records_with_any_temporal_support'] == 1
    assert result['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'


@pytest.mark.parametrize('change', ['missing_name', 'bad_name', 'endpoint_mismatch', 'missing_exchange',
                                  'malformed_record', 'age_violation', 'malformed_age_violation'])
def test_invalid_bracket_inputs_remain_visible_and_cannot_create_support(change):
    witness, capture = bracket_inputs()
    if change in ('missing_name', 'bad_name'):
        witness['attempts'].insert(1, dict(server=None if change == 'missing_name' else [],
                                         status='WITNESS_UNAVAILABLE'))
    elif change == 'endpoint_mismatch':
        witness['attempts'][0]['exchange']['server'] = 'other-endpoint'
    elif change == 'missing_exchange':
        del witness['attempts'][0]['exchange']
    elif change == 'malformed_record':
        capture['records'][0] = None
    else:
        capture['records'][0]['epoch_age_budget_violation'] = (
            'independently observed scheduling overrun' if change == 'age_violation' else False)
    result = compare_bracket(witness, capture)
    assert result['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['coverage']['records_with_any_temporal_support'] == 0
    assert result['receiver_capture'] == capture
    assert result['witness_report'] == witness
    if change in ('missing_name', 'bad_name'):
        assert result['temporal_association']['attempt_pairs'] == []
        assert result['temporal_association']['unnamed_attempt_indices'] == [1]
    else:
        assert result['coverage']['bracket_status_counts'] == {'INSUFFICIENT_EVIDENCE': 1}


def test_cli_optional_brackets_replay_offline_and_keep_single_comparisons(monkeypatch, tmp_path, capsys):
    from pnt.__main__ import main
    from pnt import time_witness

    witness, capture = bracket_inputs()
    paths = [tmp_path / name for name in ('witness.json', 'receiver.json', 'comparison.json')]
    paths[0].write_text(json.dumps(witness), encoding='utf-8')
    paths[1].write_text(json.dumps(capture), encoding='utf-8')
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('offline replay accessed network'))
    monkeypatch.setattr('sys.argv', ['pnt', 'time-compare', str(paths[0]), str(paths[1]),
                                   '--utc-error-ns', str(MS), '--utc-error-source', 'test',
                                   '--bracket-span-ns', str(200 * MS), '--output', str(paths[2])])
    main()
    report = json.loads(paths[2].read_bytes())
    assert report['coverage']['comparison_status_counts'] == {'INSUFFICIENT_EVIDENCE': 2}
    assert report['coverage']['bracket_status_counts'] == {'NOT_DISTINGUISHABLE': 1}
    assert report['sources']['witness']['sha256'] == hashlib.sha256(paths[0].read_bytes()).hexdigest()
    assert 'Bracket comparisons' in capsys.readouterr().out
    saved = paths[2].read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert paths[2].read_bytes() == saved


@pytest.mark.parametrize('offset,status', [(0, 'NOT_DISTINGUISHABLE'),
                                         (NS, 'INCONSISTENT_WITH_WITNESS'),
                                         (-NS, 'INCONSISTENT_WITH_WITNESS')])
@pytest.mark.parametrize('forward,backward', [(1, 97), (49, 49), (97, 1)])
def test_receiver_solution_epoch_not_packet_receipt_and_clock_shift_detection(offset, status, forward, backward):
    witness, capture = inputs(offset, forward_ms=forward, backward_ms=backward)
    original_capture = copy.deepcopy(capture)
    report = compare(witness, capture)
    row = report['records'][0]
    assert row['claim']['unix_ns'] == UTC + 50 * MS + offset
    assert row['claim']['start_monotonic_ns'] == COUNTER + 48 * MS
    assert row['claim']['end_monotonic_ns'] == COUNTER + 52 * MS
    result = row['comparisons'][0]
    assert result['status'] == status
    if offset:
        assert result['separation_ns'] > 800 * MS
    else:
        assert result['claim_minus_witness_ns'][0] <= 0 <= result['claim_minus_witness_ns'][1]
    # Reuse the existing arithmetic after serialization; no new replay method.
    restored = json.loads(json.dumps(report))
    expected = compare_claim(restored['witness_report']['attempts'][0]['exchange'],
                             restored['records'][0]['claim'], server_error_ns=MS, rate_error_ppm=100)
    assert {key: result[key] for key in expected} == expected
    assert capture == original_capture == report['receiver_capture']
    assert row['receiver_utc']['receiver_tAcc_ns'] == 900000000
    assert row['claim']['error_ns'] == MS  # No implicit use of receiver accuracy.
    assert report['assumptions']['calibrated'] is False


@pytest.mark.parametrize('nano', [-NS, -1, 0, 1, NS])
def test_integer_calendar_conversion_preserves_signed_nanoseconds(nano):
    decoded = decode_timeutc(utc_packet(nano=nano, valid=0xf7))
    assert decoded['unix_ns'] == UTC + nano
    assert decoded['receiver_utc_standard'] == 15  # Unknown standard is retained, not authenticated.


@pytest.mark.parametrize('change', ['missing_capture', 'wrong_capture', 'missing_receipt', 'missing_age',
                                  'missing_age_source', 'negative_age', 'reversed_age', 'bool_age',
                                  'float_receipt', 'reversed_receipt', 'old_solution', 'late_receipt'])
def test_missing_or_misassociated_capture_is_retained_without_extrapolation(change):
    witness, capture = inputs()
    record = capture['records'][0]
    if change == 'missing_capture':
        del record['capture_id']
    elif change == 'wrong_capture':
        record['capture_id'] = 'another-boot-or-recording'
    elif change == 'missing_receipt':
        del record['receipt_start_monotonic_ns']
    elif change == 'missing_age':
        del record['epoch_age_max_monotonic_ns']
    elif change == 'missing_age_source':
        record['epoch_age_source'] = ''
    elif change == 'negative_age':
        record['epoch_age_min_monotonic_ns'] = -1
    elif change == 'reversed_age':
        record['epoch_age_max_monotonic_ns'] = 0
    elif change == 'bool_age':
        record['epoch_age_max_monotonic_ns'] = True
    elif change == 'float_receipt':
        record['receipt_start_monotonic_ns'] = float(record['receipt_start_monotonic_ns'])
    elif change == 'reversed_receipt':
        record['receipt_end_monotonic_ns'] = 0
    elif change == 'old_solution':
        record['epoch_age_max_monotonic_ns'] = 500 * MS
    else:
        record['receipt_end_monotonic_ns'] = COUNTER + 200 * MS
    report = compare(witness, capture)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['records'][0]['comparisons'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['receiver_capture']['records'][0] == record
    assert report['coverage']['receiver_records'] == report['coverage']['comparisons'] == 1


@pytest.mark.parametrize('change', ['checksum', 'truncated', 'extra_bytes', 'multiple_packets',
                                  'other_message', 'unresolved', 'leap_second', 'bad_nano', 'bad_tow', 'bad_hex'])
def test_unusable_utc_packets_remain_visible(change):
    witness, capture = inputs()
    packet = utc_packet()
    if change == 'checksum':
        packet = packet[:-1] + bytes((packet[-1] ^ 1,))
    elif change == 'truncated':
        packet = packet[:-1]
    elif change == 'extra_bytes':
        packet += b'\x00'
    elif change == 'multiple_packets':
        packet *= 2
    elif change == 'other_message':
        packet = b'\xb5\x62\x02' + packet[3:]
    elif change == 'unresolved':
        packet = utc_packet(valid=3)
    elif change == 'leap_second':
        packet = utc_packet(second=60)
    elif change == 'bad_nano':
        packet = utc_packet(nano=NS + 1)
    elif change == 'bad_tow':
        packet = utc_packet(tow=604800000)
    record = capture['records'][0]
    record['packet_hex'] = 'not-hex' if change == 'bad_hex' else packet.hex()
    report = compare(witness, capture)
    assert report['records'][0]['status'] == report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['coverage']['comparison_status_counts'] == {'INSUFFICIENT_EVIDENCE': 1}
    assert report['receiver_capture']['records'][0] == record


def test_delay_and_declared_utc_uncertainty_can_hide_a_clock_shift():
    witness, capture = inputs(-NS, backward_ms=2000)
    assert compare(witness, capture)['records'][0]['comparisons'][0]['status'] == 'NOT_DISTINGUISHABLE'
    witness, capture = inputs(NS)
    assert compare(witness, capture, error_ns=2 * NS)['records'][0]['comparisons'][0]['status'] == 'NOT_DISTINGUISHABLE'


def test_failed_and_conflicting_witnesses_stay_separate_with_all_records():
    witness, capture = inputs()
    shifted = copy.deepcopy(witness['attempts'][0])
    shifted['server'] = 'conflicting-synthetic-source'
    for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
        shifted['exchange'][field] += NS
    witness['attempts'].extend([dict(server='failed', status='WITNESS_UNAVAILABLE', reason='TimeoutError'), shifted])
    capture['records'].append({'packet_hex': utc_packet().hex()})  # Archived packet has no live association.
    report = compare(witness, capture)
    assert [result['status'] for result in report['records'][0]['comparisons']] == [
        'NOT_DISTINGUISHABLE', 'INSUFFICIENT_EVIDENCE', 'INCONSISTENT_WITH_WITNESS']
    assert report['coverage']['comparisons'] == 6
    assert report['coverage']['comparison_status_counts'] == {
        'NOT_DISTINGUISHABLE': 1, 'INCONSISTENT_WITH_WITNESS': 1, 'INSUFFICIENT_EVIDENCE': 4}
    assert report['witness_report']['attempts'][1]['reason'] == 'TimeoutError'
    assert report['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'  # No aggregate allow decision.


@pytest.mark.parametrize('change', ['schema', 'negative_budget', 'missing_budget', 'bad_receiver_source', 'bool_error'])
def test_invalid_report_or_uncertainty_contract_rejected(change):
    witness, capture = inputs()
    error = MS
    if change == 'schema':
        witness['schema'] = 'some-other-time-report'
    elif change == 'negative_budget':
        witness['assumptions']['rate_error_ppm'] = -1
    elif change == 'missing_budget':
        del witness['assumptions']['server_error_ns']
    elif change == 'bad_receiver_source':
        capture['receiver_source'] = ''
    else:
        error = True
    with pytest.raises(ValueError):
        compare(witness, capture, error_ns=error)


@pytest.mark.parametrize('available', [True, False])
def test_cli_offline_hashes_failure_report_and_no_overwrite(monkeypatch, tmp_path, available):
    from pnt.__main__ import main
    from pnt import time_witness

    witness, capture = inputs(NS)
    if not available:
        del capture['records'][0]['capture_id']
    paths = [tmp_path / name for name in ('witness.json', 'receiver.json', 'comparison.json')]
    paths[0].write_text(json.dumps(witness), encoding='utf-8')
    paths[1].write_text(json.dumps(capture), encoding='utf-8')
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('offline comparison accessed network'))
    monkeypatch.setattr('sys.argv', ['pnt', 'time-compare', str(paths[0]), str(paths[1]),
                                   '--utc-error-ns', str(MS), '--utc-error-source', 'synthetic assumption',
                                   '--output', str(paths[2])])
    if available:
        main()
    else:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
    report = json.loads(paths[2].read_text(encoding='utf-8'))
    assert report['sources']['receiver']['sha256'] == hashlib.sha256(paths[1].read_bytes()).hexdigest()
    assert report['sources']['witness']['sha256'] == hashlib.sha256(paths[0].read_bytes()).hexdigest()
    assert report['records'][0]['comparisons'][0]['status'] == (
        'INCONSISTENT_WITH_WITNESS' if available else 'INSUFFICIENT_EVIDENCE')
    original = paths[2].read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert paths[2].read_bytes() == original
