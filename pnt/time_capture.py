"""Read-only UBX/TCP and NTS collection on one host monotonic counter.

Transport receipts do not establish the navigation solution's age or RF origin.
The output reuses the receiver comparison report and its arithmetic replay.
"""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import select
import socket
import threading
import time
import uuid

from research.exploratory.pnt_rawx_recovery import ubx_packets
from .gnss_time import _text, compare_receiver_capture
from .time_witness import _integer, _new_report, _sample_schedule, _sampling_interval_ns


def _read_receiver(sock, capture, stop, *, max_bytes):
    """Bracket completion of each userspace read, including fragmented frames.

    select waits outside that bracket. These are not antenna, UART or kernel
    arrival timestamps: all upstream buffering belongs in the supplied age.
    Strict UBX framing stops on damage; every byte read remains in chunks.
    """
    pending, digest, counts = bytearray(), hashlib.sha256(), Counter()
    stream = capture['stream']
    stream.update(status='CAPTURE_COMPLETE', bytes_received=0)

    def retain(frame, chunk_index):
        receipt = stream['chunks'][chunk_index]
        capture['records'].append(dict(packet_hex=frame.hex(), capture_id=capture['capture_id'],
                                       final_chunk_index=chunk_index,
                                       receipt_start_monotonic_ns=receipt['start_monotonic_ns'],
                                       receipt_end_monotonic_ns=receipt['end_monotonic_ns'],
                                       **capture['epoch_age']))

    try:
        sock.setblocking(False)
        while not stop.is_set():
            if stream['bytes_received'] >= max_bytes or len(stream['chunks']) >= 4096:
                stream.update(status='RESOURCE_LIMIT', reason='byte or read-chunk limit reached')
                break
            if not select.select([sock], [], [], 0.05)[0]:
                continue
            start = time.monotonic_ns()
            try:
                data = sock.recv(min(4096, max_bytes - stream['bytes_received']))
            except BlockingIOError:
                continue
            end = time.monotonic_ns()
            if not data:
                stream['status'] = 'END_OF_STREAM'
                break
            digest.update(data)
            stream['bytes_received'] += len(data)
            chunk_index = len(stream['chunks'])
            stream['chunks'].append(dict(hex=data.hex(), start_monotonic_ns=start,
                                         end_monotonic_ns=end))
            pending.extend(data)
            while len(pending) >= 6:
                if pending[:2] != b'\xb5\x62':
                    raise ValueError('expected a pure UBX stream; no automatic resynchronization')
                size = 8 + int.from_bytes(pending[4:6], 'little')
                if len(pending) < size:
                    break
                frame = bytes(pending[:size])
                del pending[:size]
                # Retain even corrupt TIMEUTC packets: the existing decoder
                # will report insufficient evidence, never discard them.
                if frame[2:4] == b'\x01\x21':
                    retain(frame, chunk_index)
                cls, message, _ = next(ubx_packets(frame))
                counts[f'{cls:02x}/{message:02x}'] += 1
    except (OSError, ValueError) as error:
        stream.update(status='STREAM_ERROR', reason=str(error) if isinstance(error, ValueError)
                      else type(error).__name__)
    finally:
        if pending:
            stream['pending_hex'] = pending.hex()
            if (pending[:4] == b'\xb5\x62\x01\x21'
                    and (len(pending) < 6 or len(pending) < 8 + int.from_bytes(pending[4:6], 'little'))):
                retain(pending, len(stream['chunks']) - 1)
            if stream['status'] in ('CAPTURE_COMPLETE', 'END_OF_STREAM'):
                stream.update(status='TRUNCATED_STREAM', reason='incomplete UBX frame at capture end')
        stream.update(sha256=digest.hexdigest(), verified_packet_counts=dict(sorted(counts.items())),
                      stopped_monotonic_ns=time.monotonic_ns())


def collect_receiver_time(servers, *, receiver_host, receiver_port, receiver_source,
                          server_error_ns, rate_error_ppm, budget_source,
                          utc_error_ns, utc_error_source, timeout_s=5.0, ntp_era=0,
                          rounds=1, interval_s=1.0, max_bytes=1048576,
                          epoch_age_min_ns=None, epoch_age_max_ns=None, epoch_age_source=None,
                          bracket_span_ns=None):
    """Collect a declared schedule, then compare all retained records/attempts.

    Reads an explicitly configured TCP source without sending receiver commands.
    No file replay, reconnection, plain NTP, fitted latency or favorable selection.
    Age bounds are optional as a group; unknown age keeps data non-comparable.
    """
    witness = _new_report(servers, server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                          budget_source=budget_source, timeout_s=timeout_s, ntp_era=ntp_era)
    _text(receiver_host, 'receiver_host')
    _text(receiver_source, 'receiver_source')
    _integer(receiver_port, 'receiver_port', 1)
    if receiver_port > 65535:
        raise ValueError('receiver_port must be <= 65535')
    _integer(utc_error_ns, 'utc_error_ns', 0)
    _text(utc_error_source, 'utc_error_source')
    if bracket_span_ns is not None:
        _integer(bracket_span_ns, 'bracket_span_ns', 1)
    _sampling_interval_ns(rounds, interval_s)
    _integer(max_bytes, 'max_bytes', 1)
    if max_bytes > 16 * 1048576:
        raise ValueError('at most 16 MiB per capture')
    age = {}
    if any(v is not None for v in (epoch_age_min_ns, epoch_age_max_ns, epoch_age_source)):
        _integer(epoch_age_min_ns, 'epoch_age_min_ns', 0)
        _integer(epoch_age_max_ns, 'epoch_age_max_ns', epoch_age_min_ns)
        _text(epoch_age_source, 'epoch_age_source')
        age = dict(epoch_age_min_monotonic_ns=epoch_age_min_ns,
                   epoch_age_max_monotonic_ns=epoch_age_max_ns, epoch_age_source=epoch_age_source)
    capture_id = str(uuid.uuid4())
    capture = dict(schema='pnt-gnss-utc-capture-v1', capture_id=capture_id,
                   receiver_source=receiver_source, records=[], epoch_age=age,
                   receipt_semantics='USERSPACE_FINAL_BYTE_READ_COMPLETION',
                   stream=dict(host=receiver_host, port=receiver_port, chunks=[],
                               status='RECEIVER_UNAVAILABLE', max_bytes=max_bytes,
                               max_chunks=4096, receiver_commands_sent=0,
                               origin_authenticated=False, reconnects=0))
    witness['capture_id'] = capture_id
    stop, sock, reader = threading.Event(), None, None
    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            # Select one resolved address once, retaining connection failure.
            family, kind, protocol, _, address = socket.getaddrinfo(
                receiver_host, receiver_port, type=socket.SOCK_STREAM)[0]
            capture['stream']['selected_address'] = list(address)
            sock = socket.socket(family, kind, protocol)
            sock.settimeout(timeout_s)
            sock.connect(address)
            capture['stream']['peer_address'] = list(sock.getpeername())
            reader = pool.submit(_read_receiver, sock, capture, stop, max_bytes=max_bytes)
        except OSError as error:
            capture['stream']['reason'] = type(error).__name__
        try:
            acquisition = _sample_schedule(witness, servers, rounds=rounds, interval_s=interval_s,
                                           capture_id=capture_id)
        finally:
            stop.set()
            try:
                if reader is not None:
                    reader.result()
            finally:
                if sock is not None:
                    sock.close()
    report = compare_receiver_capture(witness, capture, utc_error_ns=utc_error_ns,
                                      utc_error_source=utc_error_source, bracket_span_ns=bracket_span_ns)
    acquisition.update(ended_monotonic_ns=time.monotonic_ns(), epoch_age_known=bool(age),
                       clock=time.get_clock_info('monotonic').implementation)
    report.update(regime='EXPLORATORY_LIVE_CAPTURE', acquisition=acquisition)
    return report
