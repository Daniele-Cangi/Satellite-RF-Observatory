"""Captured LNAV/NAV cross-checks and malformed, partial and changed messages."""

from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
import struct
import subprocess
import sys

import pytest

from pnt.navigation_witness import inspect_navigation
from pnt.sfrbx import continuous_week, GPS_EPOCH, read_sfrbx_issues, reference_week


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/sfrbx_jammertest_211.json').read_text())
DAY = FIXTURE['day_gpst']
PACKETS = [bytes.fromhex(item['ubx_hex']) for item in FIXTURE['packets']]


def packet(payload, cls=2, message=19):
    body = bytes((cls, message)) + len(payload).to_bytes(2, 'little') + payload
    a = b = 0
    for byte in body:
        a = (a + byte) & 255
        b = (b + a) & 255
    return b'\xb5\x62' + body + bytes((a, b))


def set_bits(raw, offset, length, value):
    """Modify receiver-decoded data, preserving padding/parity; repair UBX only.

    These are software mutations, not synthesized valid over-the-air GPS words.
    """
    payload = bytearray(raw[6:-2])
    words = struct.unpack_from('<10I', payload, 8)
    data = int.from_bytes(b''.join(((w >> 6) & 0xffffff).to_bytes(3, 'big') for w in words), 'big')
    shift = 240 - offset - length
    data = (data & ~(((1 << length) - 1) << shift)) | ((value & ((1 << length) - 1)) << shift)
    for i, word in enumerate(words):
        digit = (data >> (24 * (9 - i))) & 0xffffff
        struct.pack_into('<I', payload, 8 + 4 * i, (word & 0xc000003f) | (digit << 6))
    return packet(bytes(payload))


def write(tmp_path, packets):
    path = tmp_path / 'capture.ubx'
    path.write_bytes(b''.join(packets))
    return path


def inspect(tmp_path, packets):
    path = write(tmp_path, packets)
    external = tmp_path / 'external.n'
    external.write_text(FIXTURE['external_rinex'], encoding='ascii')
    return inspect_navigation(path, {'NOAA': external}, DAY, local_format='ubx')


def test_captured_complete_issues_and_all_27_fields_match_separately_archived_nav(tmp_path):
    report = inspect(tmp_path, PACKETS)
    assert report['schema'] == 'pnt-navigation-witness-v2'
    assert report['selection'] == 'ALL_DECODED_UBX_ISSUES'
    assert report['window_gpst_s'] is None
    assert report['coverage']['status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 1, 'INSUFFICIENT_EVIDENCE': 2}
    assert report['sources']['local']['counts']['gps_l1_ca_packets'] == 9
    assert report['sources']['local']['cycle_status_counts'] == {'DECODED_ISSUE': 3}
    assert len(report['records'][0]['local_fields']) == 27
    assert report['records'][0]['witnesses']['NOAA']['differing_fields'] == []
    # The claimed future date is evidence, not a reason to exclude the issue.
    assert report['records'][2]['toc_gpst'] == '2024-10-01T14:00:00+00:00'
    assert report['coverage']['decoded_toc_outside_declared_day'] == 1
    assert report['records'][2]['witnesses']['NOAA']['status'] == 'MISSING_ISSUE'
    assert report['assessments']['RF_authenticity'] == 'NOT_ASSESSED'


def test_captured_bit_signs_scales_and_split_fields(tmp_path):
    rows, _ = read_sfrbx_issues(write(tmp_path, PACKETS[:3]), DAY)
    value = rows[0]['values']
    assert value['iodc'] == value['iode'] == 57
    assert value['af0_s'] == Decimal('0.00063017196953296661376953125')
    assert value['af1_s_s'] == Decimal('-0.0000000000110276232589967548847198486328125')
    assert value['sqrt_a_m_sqrt'] == Decimal('5153.798862457275390625')
    assert value['eccentricity'] == Decimal('0.013528208830393850803375244140625')
    assert value['m0_rad'] == pytest.approx(Decimal('3.049521126189682'), abs=Decimal('1e-15'))
    assert value['omega0_rad'] == pytest.approx(Decimal('-0.8446831862737585'), abs=Decimal('1e-15'))


@pytest.mark.parametrize('offset,length,value,field,expected', [
    (216, 22, -(1 << 21), 'af0_s', Decimal('-0.0009765625')),
    (200, 16, -32768, 'af1_s_s', Decimal('-0.0000000037252902984619140625')),
    (192, 8, -128, 'af2_s_s2', Decimal('-0.000000000000003552713678800500929355621337890625')),
    (58, 2, 2, 'codes_l2', Decimal(2)),
    (72, 1, 1, 'l2_p_flag', Decimal(1)),
])
def test_clock_and_flag_extremes_are_decoded_without_float_loss(tmp_path, offset, length, value, field, expected):
    packets = [set_bits(PACKETS[0], offset, length, value), *PACKETS[1:3]]
    rows, _ = read_sfrbx_issues(write(tmp_path, packets), DAY)
    assert rows[0]['values'][field] == expected
    report = inspect(tmp_path, packets)
    # This archive writes zero af2 as 0.000000000000D+00: the existing
    # decimal-precision interval cannot resolve even the largest LNAV af2.
    expected_fields = [] if field == 'af2_s_s2' else [field]
    assert report['records'][0]['witnesses']['NOAA']['differing_fields'] == expected_fields


def test_iodc_high_bits_are_not_dropped_and_health_is_retained(tmp_path):
    changed = set_bits(set_bits(PACKETS[0], 70, 2, 3), 64, 6, 63)
    rows, source = read_sfrbx_issues(write(tmp_path, [changed, *PACKETS[1:3]]), DAY)
    assert rows[0]['values']['iodc'] == 825
    assert source['unhealthy_records_retained'] == 1
    assert inspect(tmp_path, [changed, *PACKETS[1:3]])['records'][0]['status'] == 'INSUFFICIENT_EVIDENCE'


def test_incomplete_cycles_and_unmatched_issue_are_not_replaced(tmp_path):
    report = inspect(tmp_path, [*PACKETS[:2], *PACKETS[6:]])
    source = report['sources']['local']
    assert source['cycle_status_counts'] == {'DECODED_ISSUE': 1, 'INCOMPLETE_CYCLE': 1}
    assert source['cycles'][0]['missing_subframes'] == [3]
    assert len(source['frames']) == 5
    assert report['coverage']['status_counts'] == {'INSUFFICIENT_EVIDENCE': 1}


def test_cross_cycle_borrowing_and_return_to_an_old_cycle_are_blocked(tmp_path):
    changed_how = set_bits(PACKETS[1], 24, 17, 47397)  # Original 47392 + 5, next 30 s cycle.
    rows, source = read_sfrbx_issues(write(tmp_path, [PACKETS[0], changed_how, PACKETS[2]]), DAY)
    assert rows == []
    assert source['cycle_status_counts'] == {'INCOMPLETE_CYCLE': 3}


def test_order_within_same_cycle_can_change_without_using_receiver_pvt(tmp_path):
    report = inspect(tmp_path, list(reversed(PACKETS[:3])))
    assert report['coverage']['status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 1}


def test_non_cei_subframe_from_another_cycle_also_prevents_stale_borrowing(tmp_path):
    almanac = set_bits(set_bits(PACKETS[0], 43, 3, 4), 24, 17, 47399)
    rows, source = read_sfrbx_issues(write(tmp_path, [*PACKETS[:2], almanac, PACKETS[2]]), DAY)
    assert rows == []
    assert source['cycle_status_counts'] == {'INCOMPLETE_CYCLE': 2}
    assert source['frame_status_counts'] == {'CEI_SUBFRAME': 3, 'NON_CEI_SUBFRAME': 1}


@pytest.mark.parametrize('conflict', [False, True])
def test_repeated_subframes_stay_visible_and_conflicts_are_not_resolved(tmp_path, conflict):
    repeated = set_bits(PACKETS[0], 216, 22, 1) if conflict else PACKETS[0]
    rows, source = read_sfrbx_issues(write(tmp_path, [PACKETS[0], repeated, *PACKETS[1:3]]), DAY)
    assert len(source['frames']) == 4
    assert source['cycles'][0]['packet_indices']['1'] == [0, 1]
    assert source['cycle_status_counts'] == ({'CONFLICTING_SUBFRAMES': 1} if conflict else {'DECODED_ISSUE': 1})
    assert len(rows) == (0 if conflict else 1)


@pytest.mark.parametrize('which,offset,length,value,reason', [
    (1, 48, 8, 12, 'inconsistent IODE/IODC'),
    (0, 60, 4, 15, 'URA index 15'),
    (0, 160, 8, -128, 'TGD unavailable'),
    (1, 216, 16, 65535, 'invalid LNAV reference time'),
])
def test_unusable_complete_issues_remain_explicit(tmp_path, which, offset, length, value, reason):
    packets = list(PACKETS[:3]); packets[which] = set_bits(packets[which], offset, length, value)
    rows, source = read_sfrbx_issues(write(tmp_path, packets), DAY)
    assert rows == []
    assert source['cycles'][0]['status'] == 'UNUSABLE_ISSUE'
    assert reason in source['cycles'][0]['reason']


def test_unsupported_signal_is_counted_without_lnav_misinterpretation(tmp_path):
    payload = bytearray(PACKETS[0][6:-2]); payload[2] = 4
    rows, source = read_sfrbx_issues(write(tmp_path, [packet(bytes(payload))]), DAY)
    assert rows == []
    assert source['unsupported_sfrbx_counts'] == {'gnss=0,signal=4,version=2': 1}


@pytest.mark.parametrize('offset,length,value,status', [
    (0, 8, 0, 'INVALID_TLM_HOW'), (43, 3, 0, 'INVALID_TLM_HOW'),
    (24, 17, 100800, 'INVALID_TLM_HOW'), (24, 17, 47390, 'INVALID_FRAME_PHASE'),
])
def test_invalid_tlm_how_is_retained_without_decoding(tmp_path, offset, length, value, status):
    rows, source = read_sfrbx_issues(write(tmp_path, [set_bits(PACKETS[0], offset, length, value)]), DAY)
    assert rows == []
    assert source['frames'][0]['status'] == status


def test_checksum_damage_is_fail_closed_and_recovery_explicit(tmp_path):
    damaged = bytearray(PACKETS[0]); damaged[-1] ^= 1
    path = write(tmp_path, [bytes(damaged), *PACKETS[:3]])
    with pytest.raises(ValueError, match='checksum mismatch'):
        read_sfrbx_issues(path, DAY)
    rows, source = read_sfrbx_issues(path, DAY, recover_corrupt=True)
    assert len(rows) == 1
    assert source['excluded_corrupt_packets'] == {'bad_checksum': 1}
    assert source['counts']['gps_l1_ca_packets'] == 3


def test_invalid_sfrbx_payload_structure_fails_instead_of_disappearing(tmp_path):
    path = write(tmp_path, [packet(PACKETS[0][6:-6])])
    with pytest.raises(ValueError, match='length'):
        read_sfrbx_issues(path, DAY)


def test_padding_is_ignored_and_raw_payload_retained(tmp_path):
    changed = []
    for original in PACKETS[:3]:
        payload = bytearray(original[6:-2])
        for i in range(10): payload[11 + i * 4] ^= 0xc0
        changed.append(packet(bytes(payload)))
    report = inspect(tmp_path, changed)
    assert report['records'][0]['status'] == 'COMPATIBLE_WITH_EXTERNAL'
    assert report['sources']['local']['frames'][0]['payload_hex'] != PACKETS[0][14:-2].hex()


def test_week_rollover_uses_supplied_day_and_rejects_ambiguous_era():
    assert continuous_week(0, '2019-04-07') == 2048
    assert continuous_week(1023, '2019-04-07') == 2047
    with pytest.raises(ValueError, match='ambiguous'):
        continuous_week(0, (GPS_EPOCH + timedelta(weeks=512)).date().isoformat())
    assert reference_week(2048, 604784, 0) == 2047
    assert reference_week(2047, 0, 604770) == 2048
    with pytest.raises(ValueError, match='ambiguous'):
        reference_week(2331, 302400, 0)


def test_toc_window_cannot_hide_ubx_message_and_cli_refuses_overwrite(tmp_path):
    path = write(tmp_path, PACKETS)
    external = tmp_path / 'external.n'; external.write_text(FIXTURE['external_rinex'], encoding='ascii')
    with pytest.raises(ValueError, match='whole capture'):
        inspect_navigation(path, {'NOAA': external}, DAY, local_format='ubx', start_s=30)
    with pytest.raises(ValueError, match='recovery applies'):
        inspect_navigation(external, {'NOAA': external}, DAY, recover_corrupt=True)
    output = tmp_path / 'report.json'
    command = [sys.executable, '-m', 'pnt', 'navigation', DAY, str(path), '--local-format', 'ubx',
               '--witness', f'NOAA={external}', '--output', str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    raw = output.read_bytes()
    assert json.loads(raw)['coverage']['decoded_toc_outside_declared_day'] == 1
    assert subprocess.run(command, capture_output=True, text=True).returncode == 2
    assert output.read_bytes() == raw
