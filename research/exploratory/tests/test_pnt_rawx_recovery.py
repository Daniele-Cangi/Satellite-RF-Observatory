from datetime import date, datetime, timedelta
import struct

import pytest

from research.exploratory import pnt_rawx_recovery as recovery


def rawx_packet(tow, measurements):
    payload = bytearray(16 + 32 * len(measurements))
    struct.pack_into('<dH', payload, 0, tow, 2331)
    payload[11] = len(measurements)
    payload[13] = 1
    for index, (satellite, signal, code, valid) in enumerate(measurements):
        offset = 16 + 32 * index
        struct.pack_into('<d', payload, offset, code)
        payload[offset + 20:offset + 23] = bytes((0, satellite, signal))
        payload[offset + 30] = int(valid)
    frame = bytes((0xb5, 0x62, 0x02, 0x15)) + struct.pack('<H', len(payload)) + payload
    a = b = 0
    for byte in frame[2:]:
        a = (a + byte) & 0xff
        b = (b + a) & 0xff
    return frame + bytes((a, b))


def test_rawx_identifies_valid_signals_and_rejects_corrupt_packet():
    frame = rawx_packet(288000, [(3, 0, 21000000., True),
                                  (3, 3, 21000005., True),
                                  (4, 0, 0., False),
                                  (5, 0, 0., True)])
    epochs, status = recovery.rawx_epochs(b'ignored prefix' + frame)
    assert epochs[0]['receiver_time'] == datetime(2024, 9, 11, 8)
    assert epochs[0]['dual'] == {'G03': (21000000., 21000005.)}
    assert status['invalid_pseudorange_flag'] == 1
    assert status['nonpositive_or_nonfinite_valid_flag_code'] == 1
    assert status['dual_gps_measurements'] == 1
    broken = bytearray(frame)
    broken[-1] ^= 1
    with pytest.raises(ValueError, match='checksum'):
        recovery.rawx_epochs(broken)


def test_packet_order_preserves_capture_grid_across_receiver_time_jump():
    first = datetime(2024, 9, 11, 8)
    epochs = [{'receiver_time': first, 'dual': {'G03': (21000000., 21000005.)}},
              {'receiver_time': first - timedelta(hours=20),
               'dual': {'G03': (21000001., 21000006.)}}]
    selected, jumps, status = recovery.capture_grid(epochs, date(2024, 9, 11))
    assert selected[(28800, 'G03')][2:] == (21000000., 21000005.)
    assert status['selected_grid_satellites'] == 1
    assert len(jumps) == 1
    assert jumps[0]['receiver_jump_s'] == -72000.
