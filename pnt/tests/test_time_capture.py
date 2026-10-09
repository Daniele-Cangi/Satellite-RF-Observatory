from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import queue
import socket
import struct
import threading
import time

import pytest

from pnt import time_capture, time_witness
from pnt.__main__ import main
from pnt.gnss_time import compare_receiver_capture
from pnt.nts import NTSError


NS = 10**9
MS = 10**6


def frame(payload, cls=1, message=0x21):
    body = bytes((cls, message)) + len(payload).to_bytes(2, 'little') + payload
    a = b = 0
    for byte in body:
        a = (a + byte) & 255
        b = (b + a) & 255
    return b'\xb5\x62' + body + bytes((a, b))


def packet(unix_ns):
    second, nano = divmod(unix_ns, NS)
    utc = datetime.fromtimestamp(second, timezone.utc)
    return frame(struct.pack('<IIiH6B', 1000, 999999999, nano, utc.year,
                             utc.month, utc.day, utc.hour, utc.minute, utc.second, 7))


def capture():
    return dict(capture_id='test-only', records=[], epoch_age={}, stream=dict(chunks=[]))


def options(port, **changes):
    args = dict(receiver_host='127.0.0.1', receiver_port=port,
                receiver_source='SYNTHETIC_LOOPBACK_TEST; no receiver or RF',
                server_error_ns=MS, rate_error_ppm=100, budget_source='synthetic assumptions',
                utc_error_ns=MS, utc_error_source='synthetic UTC bound', timeout_s=1,
                epoch_age_min_ns=0, epoch_age_max_ns=20 * MS,
                epoch_age_source='independent synthetic event schedule')
    args.update(changes)
    return args


@pytest.fixture
def rig(monkeypatch):
    """Real concurrent TCP reads, synthetic NTS time on a known counter map."""
    state = dict(offsets=[0, 10 * NS], calls=[], capture=None)
    outgoing, reader_ready = queue.Queue(), threading.Event()
    original_reader = time_capture._read_receiver

    def reader(sock, captured, stop, **kwargs):
        state['capture'] = captured
        reader_ready.set()
        return original_reader(sock, captured, stop, **kwargs)

    monkeypatch.setattr(time_capture, '_read_receiver', reader)
    anchor = time.monotonic_ns()
    utc_anchor = 1700000000 * NS

    def utc(counter):
        return utc_anchor + counter - anchor

    def probe(server, **kwargs):
        state['calls'].append(server)
        if server == 'failed':
            raise NTSError('synthetic endpoint failure')
        if server == 'interrupt':
            raise KeyboardInterrupt
        assert reader_ready.wait(2), 'reader did not start'
        sent = time.monotonic_ns()
        time.sleep(.04)  # Ensure the entire declared age bracket is after send.
        epoch = time.monotonic_ns()
        before = len(state['capture']['records'])
        data = b''.join(packet(utc(epoch) + offset) for offset in state['offsets'])
        outgoing.put([data[:3], data[3:19], data[19:]])
        deadline = time.monotonic() + 2
        while len(state['capture']['records']) < before + len(state['offsets']):
            assert time.monotonic() < deadline, 'receiver read did not complete'
            time.sleep(.001)
        time.sleep(.01)
        received = time.monotonic_ns()
        return dict(authentication='NTS_TLS13_AES_SIV_256', send_monotonic_ns=sent,
                    receive_monotonic_ns=received, server_receive_unix_ns=utc(sent + MS),
                    server_transmit_unix_ns=utc(sent + 2 * MS), monotonic_resolution_ns=1,
                    claim_start_monotonic_ns=received, claim_end_monotonic_ns=received,
                    host_claim_unix_ns=utc(received), host_claim_error_ns=1)

    monkeypatch.setattr(time_witness, 'probe', probe)
    with closing(socket.socket()) as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen()
        listener.settimeout(3)
        state['port'] = listener.getsockname()[1]

        def send():
            with closing(listener.accept()[0]) as connection:
                while (chunks := outgoing.get()) is not None:
                    for chunk in chunks:
                        connection.sendall(chunk)
                        time.sleep(.002)

        sender = threading.Thread(target=send, daemon=True)
        sender.start()
        try:
            yield state
        finally:
            outgoing.put(None)
            sender.join(3)
            assert not sender.is_alive()


def test_concurrent_tcp_capture_shared_counter_and_existing_replay(rig):
    report = time_capture.collect_receiver_time(['good'], **options(rig['port']))
    assert report['regime'] == 'EXPLORATORY_LIVE_CAPTURE'
    assert report['status'] == 'CONDITIONAL_TIME_DIAGNOSTIC'
    captured, witness = report['receiver_capture'], report['witness_report']
    assert report['coverage']['comparison_status_counts'] == {
        'INCONSISTENT_WITH_WITNESS': 1, 'NOT_DISTINGUISHABLE': 1}
    assert captured['capture_id'] == witness['capture_id']
    assert all(row['capture_id'] == captured['capture_id'] for row in captured['records'])
    assert witness['attempts'][0]['exchange']['capture_id'] == captured['capture_id']
    stream = b''.join(bytes.fromhex(chunk['hex']) for chunk in captured['stream']['chunks'])
    assert stream == b''.join(bytes.fromhex(record['packet_hex']) for record in captured['records'])
    assert hashlib.sha256(stream).hexdigest() == captured['stream']['sha256']
    assert captured['stream']['bytes_received'] == len(stream) == 56
    for record in captured['records']:
        receipt = captured['stream']['chunks'][record['final_chunk_index']]
        assert record['receipt_start_monotonic_ns'] == receipt['start_monotonic_ns']
        assert record['receipt_end_monotonic_ns'] == receipt['end_monotonic_ns']
    restored = json.loads(json.dumps(report))
    replay = compare_receiver_capture(restored['witness_report'], restored['receiver_capture'],
                                      utc_error_ns=MS, utc_error_source='synthetic UTC bound')
    assert replay['records'] == report['records']
    assert replay['coverage'] == report['coverage']
    assert replay['assumptions'] == report['assumptions']


def test_declared_rounds_keep_failed_endpoints_and_all_observations(rig):
    report = time_capture.collect_receiver_time(['good', 'failed'],
                                                **options(rig['port'], rounds=2, interval_s=.01))
    attempts = report['witness_report']['attempts']
    assert rig['calls'] == ['good', 'failed', 'good', 'failed']
    assert len(attempts) == 4
    assert [a['round_index'] for a in attempts] == [0, 0, 1, 1]
    assert [a['status'] for a in attempts] == ['AUTHENTICATED_EXCHANGE', 'WITNESS_UNAVAILABLE'] * 2
    assert all(a['reason'] == 'synthetic endpoint failure' for a in attempts[1::2])
    assert report['coverage']['receiver_records'] == 4
    assert report['coverage']['comparisons'] == 16
    assert report['coverage']['comparison_status_counts']['INSUFFICIENT_EVIDENCE'] >= 8
    assert report['witness_report']['protocol']['automatic_retries'] is False
    assert report['witness_report']['protocol']['attempts_per_endpoint'] == 2
    scheduled = attempts[2]['scheduled_round_start_monotonic_ns']
    assert scheduled - attempts[0]['scheduled_round_start_monotonic_ns'] == 10 * MS


def test_unknown_age_retains_packets_without_creating_comparisons(rig):
    report = time_capture.collect_receiver_time(['good'], **options(
        rig['port'], epoch_age_min_ns=None, epoch_age_max_ns=None, epoch_age_source=None))
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert len(report['receiver_capture']['records']) == 2
    assert report['acquisition']['epoch_age_known'] is False
    assert report['coverage']['comparison_status_counts'] == {'INSUFFICIENT_EVIDENCE': 2}


def test_interrupt_preserves_current_attempt_and_unstarted_schedule(rig):
    report = time_capture.collect_receiver_time(['interrupt', 'good'],
                                                **options(rig['port'], rounds=2))
    assert report['acquisition']['interrupted'] is True
    assert rig['calls'] == ['interrupt']
    attempts = report['witness_report']['attempts']
    assert len(attempts) == 4
    assert [a['status'] for a in attempts] == ['WITNESS_UNAVAILABLE'] + ['NOT_ATTEMPTED'] * 3
    assert all(a['reason'] == 'CAPTURE_INTERRUPTED' for a in attempts)


class Chunks:
    def __init__(self, pieces):
        self.pieces = iter(pieces)

    def setblocking(self, blocking):
        assert blocking is False

    def recv(self, maximum):
        result = next(self.pieces, b'')
        assert len(result) <= maximum
        return result


def read(monkeypatch, pieces, max_bytes=1048576):
    captured = capture()
    monkeypatch.setattr(time_capture.select, 'select', lambda readers, *args: (readers, [], []))
    time_capture._read_receiver(Chunks(pieces), captured, threading.Event(), max_bytes=max_bytes)
    return captured


def test_fragmentation_multiple_frames_and_ignored_messages_keep_exact_stream(monkeypatch):
    utc = packet(1700000000 * NS)
    other = frame(b'\xb5\x62noise', cls=2, message=0x10)
    captured = read(monkeypatch, [utc[:2], utc[2:13], utc[13:] + other + utc])
    assert [r['packet_hex'] for r in captured['records']] == [utc.hex(), utc.hex()]
    assert [r['final_chunk_index'] for r in captured['records']] == [2, 2]
    assert captured['stream']['verified_packet_counts'] == {'01/21': 2, '02/10': 1}
    assert captured['stream']['sha256'] == hashlib.sha256(utc + other + utc).hexdigest()


@pytest.mark.parametrize('kind', ['bad_checksum', 'noise', 'partial_header', 'partial_payload'])
def test_stream_damage_is_retained_without_resynchronization(monkeypatch, kind):
    utc = packet(1700000000 * NS)
    data = {'bad_checksum': utc[:-1] + bytes((utc[-1] ^ 1,)) + utc,
            'noise': b'not UBX' + utc, 'partial_header': utc[:5], 'partial_payload': utc[:15]}[kind]
    captured = read(monkeypatch, [data])
    assert captured['stream']['status'] in ('STREAM_ERROR', 'TRUNCATED_STREAM')
    assert captured['stream']['chunks'][0]['hex'] == data.hex()
    assert captured['stream']['sha256'] == hashlib.sha256(data).hexdigest()
    assert len(captured['records']) == (0 if kind == 'noise' else 1)
    assert captured['stream']['verified_packet_counts'] == {}


def test_resource_limit_is_explicit_and_partial_packet_is_not_lost(monkeypatch):
    utc = packet(1700000000 * NS)
    captured = read(monkeypatch, [utc[:10]], max_bytes=10)
    assert captured['stream']['status'] == 'RESOURCE_LIMIT'
    assert captured['stream']['bytes_received'] == 10
    assert captured['records'][0]['packet_hex'] == utc[:10].hex()
    assert captured['stream']['pending_hex'] == utc[:10].hex()


def test_socket_error_after_good_data_keeps_data_and_failure(monkeypatch):
    class ErrorStream(Chunks):
        def recv(self, maximum):
            if (data := super().recv(maximum)):
                return data
            raise ConnectionResetError

    captured = capture()
    monkeypatch.setattr(time_capture.select, 'select', lambda readers, *args: (readers, [], []))
    time_capture._read_receiver(ErrorStream([packet(1700000000 * NS)]), captured,
                                threading.Event(), max_bytes=1048576)
    assert len(captured['records']) == 1
    assert captured['stream']['status'] == 'STREAM_ERROR'
    assert captured['stream']['reason'] == 'ConnectionResetError'


def test_receiver_connection_failure_and_nts_failure_are_both_reported(monkeypatch):
    addresses = []

    def resolve(*args, **kwargs):
        addresses.append(args)
        raise socket.gaierror

    def probe(*args, **kwargs):
        raise NTSError('synthetic NTS failure')

    monkeypatch.setattr(time_capture.socket, 'getaddrinfo', resolve)
    monkeypatch.setattr(time_witness, 'probe', probe)
    report = time_capture.collect_receiver_time(['failed'], **options(1234, rounds=2, interval_s=.001))
    assert len(addresses) == 1  # No receiver reconnect or alternative address.
    assert report['receiver_capture']['stream']['status'] == 'RECEIVER_UNAVAILABLE'
    assert report['receiver_capture']['records'] == []
    assert len(report['witness_report']['attempts']) == 2
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'


@pytest.mark.parametrize('change', [dict(receiver_host=''), dict(receiver_port=0),
                                  dict(receiver_port=65536), dict(receiver_source=''),
                                  dict(rounds=0), dict(rounds=True), dict(rounds=1001),
                                  dict(interval_s=0), dict(interval_s=float('nan')),
                                  dict(interval_s=1e-12), dict(max_bytes=0),
                                  dict(epoch_age_min_ns=None), dict(epoch_age_max_ns=-1),
                                  dict(epoch_age_source=''), dict(utc_error_ns=-1),
                                  dict(utc_error_source=''), dict(server_error_ns=-1)])
def test_invalid_configuration_fails_before_any_connection(monkeypatch, change):
    def forbidden(*args, **kwargs):
        pytest.fail('configuration validation must precede network access')

    monkeypatch.setattr(time_capture.socket, 'getaddrinfo', forbidden)
    with pytest.raises(ValueError):
        time_capture.collect_receiver_time(['good'], **options(1234, **change))


def cli_args(port, path):
    return ['pnt', 'time-capture', '--receiver-host', '127.0.0.1', '--receiver-port', str(port),
            '--receiver-source', 'SYNTHETIC_LOOPBACK_TEST; no RF', '--server', 'good',
            '--server-error-ns', str(MS), '--rate-error-ppm', '100',
            '--budget-source', 'synthetic', '--utc-error-ns', str(MS),
            '--utc-error-source', 'synthetic', '--output', str(path)]


def test_cli_saves_unknown_age_report_and_never_overwrites(rig, monkeypatch, tmp_path):
    output = tmp_path / 'capture.json'
    monkeypatch.setattr('sys.argv', cli_args(rig['port'], output))
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    saved = output.read_bytes()
    report = json.loads(saved)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert len(report['receiver_capture']['records']) == 2
    assert len(report['witness_report']['attempts']) == 1
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert output.read_bytes() == saved
    assert rig['calls'] == ['good']
