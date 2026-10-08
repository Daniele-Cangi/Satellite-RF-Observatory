"""Read-only, single-exchange NTS client (RFC 8915, NTPv4 / AES-SIV-256).

Session secrets stay in memory. No clock discipline, certificate bypass,
plain-NTP fallback, polling, cookie persistence or automatic retries.
"""

import hashlib
import math
import os
import select
import socket
import ssl
import struct
import time


class NTSError(ValueError):
    """Unusable or unauthenticated exchange; messages contain no session secrets."""


def _record(kind, body=b'', critical=False):
    return struct.pack('!HH', kind | (0x8000 if critical else 0), len(body)) + body


def _ke_parameters(records):
    """Validate the complete, bounded NTS-KE response before using cookies."""
    if len(records) > 65536:
        raise NTSError('NTS-KE response exceeds 64 KiB')
    pos, seen, cookies, ended = 0, {}, [], False
    while pos < len(records):
        if pos + 4 > len(records) or ended:
            raise NTSError('invalid NTS-KE framing')
        raw_kind, length = struct.unpack_from('!HH', records, pos)
        kind, critical = raw_kind & 0x7fff, bool(raw_kind & 0x8000)
        pos += 4
        body = records[pos:pos + length]
        if len(body) != length:
            raise NTSError('truncated NTS-KE record')
        pos += length
        if kind in (2, 3):
            raise NTSError('NTS-KE server error or warning')
        if kind == 5:
            cookies.append(body)
        elif kind in (0, 1, 4, 6, 7):
            if kind in seen:
                raise NTSError('duplicate NTS-KE negotiation record')
            seen[kind] = body
            if kind == 0:
                if not critical or body:
                    raise NTSError('invalid NTS-KE end record')
                ended = True
            if kind == 1 and not critical:
                raise NTSError('noncritical next-protocol record')
        elif critical:
            raise NTSError('unknown critical NTS-KE record')
    if not ended or seen.get(1) != b'\x00\x00' or seen.get(4) != b'\x00\x0f' or not cookies:
        raise NTSError('NTPv4 / AES-SIV-256 negotiation incomplete')
    try:
        hostname = seen[6].decode('ascii') if 6 in seen else None
    except UnicodeError as error:
        raise NTSError('invalid negotiated NTP hostname') from error
    if hostname is not None and (not hostname or any(c.isspace() or ord(c) < 33 for c in hostname)):
        raise NTSError('invalid negotiated NTP hostname')
    port_body = seen.get(7, b'\x00\x7b')
    if len(port_body) != 2 or not (port := int.from_bytes(port_body, 'big')):
        raise NTSError('invalid negotiated NTP port')
    return hostname, port, cookies[0]


def _tls_call(connection, operation, deadline):
    from OpenSSL import SSL

    while True:
        if (remaining := deadline - time.monotonic()) <= 0:
            raise TimeoutError('NTS-KE deadline exceeded')
        try:
            return operation()
        except SSL.WantReadError:
            if not select.select([connection], [], [], remaining)[0]:
                raise TimeoutError('NTS-KE read timed out')
        except SSL.WantWriteError:
            if not select.select([], [connection], [], remaining)[1]:
                raise TimeoutError('NTS-KE write timed out')


def _key_exchange(server, timeout_s, *, port=4460, ca_file=None):
    from OpenSSL import SSL, crypto
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    from service_identity.pyopenssl import verify_hostname

    context = SSL.Context(SSL.TLS_CLIENT_METHOD)
    context.set_min_proto_version(SSL.TLS1_3_VERSION)
    context.set_verify(SSL.VERIFY_PEER, lambda conn, cert, errno, depth, valid: bool(valid))
    # Use Python's platform trust store, including Windows roots. ca_file is an
    # explicit alternative trust root for loopback tests, never a bypass.
    roots = ssl.create_default_context(cafile=ca_file).get_ca_certs(binary_form=True)
    store = context.get_cert_store()
    for root in roots:
        store.add_cert(crypto.X509.from_cryptography(x509.load_der_x509_certificate(root)))
    context.set_alpn_protos([b'ntske/1'])
    deadline = time.monotonic() + timeout_s
    # create_connection() silently tries further DNS addresses after failures.
    # Select once so an unavailable address remains a failed endpoint attempt.
    family, socktype, protocol, _, address = socket.getaddrinfo(server, port, type=socket.SOCK_STREAM)[0]
    with socket.socket(family, socktype, protocol) as sock:
        sock.settimeout(timeout_s)
        try:
            sock.connect(address)
        except OSError as error:
            raise NTSError(f'NTS-KE connection to {address} failed: {type(error).__name__}') from error
        tcp_peer = sock.getpeername()
        sock.setblocking(False)
        connection = SSL.Connection(context, sock)
        connection.set_connect_state()
        connection.set_tlsext_host_name(server.encode('ascii'))
        _tls_call(connection, connection.do_handshake, deadline)
        verify_hostname(connection, server)
        if connection.get_alpn_proto_negotiated() != b'ntske/1':
            raise NTSError('NTS-KE ALPN not negotiated')
        request = _record(1, b'\x00\x00', True) + _record(4, b'\x00\x0f') + _record(0, critical=True)
        sent = 0
        while sent < len(request):
            sent += _tls_call(connection, lambda: connection.send(request[sent:]), deadline)
        data = bytearray()
        pos = 0
        while True:
            chunk = _tls_call(connection, lambda: connection.recv(4096), deadline)
            if not chunk:
                raise NTSError('NTS-KE closed before end record')
            data.extend(chunk)
            if len(data) > 65536:
                raise NTSError('NTS-KE response exceeds 64 KiB')
            while pos + 4 <= len(data):
                kind, length = struct.unpack_from('!HH', data, pos)
                if pos + 4 + length > len(data):
                    break
                pos += 4 + length
                if kind & 0x7fff == 0:
                    hostname, ntp_port, cookie = _ke_parameters(bytes(data))
                    label = b'EXPORTER-network-time-security'
                    c2s = connection.export_keying_material(label, 32, struct.pack('!HHB', 0, 15, 0))
                    s2c = connection.export_keying_material(label, 32, struct.pack('!HHB', 0, 15, 1))
                    certificate = connection.get_peer_certificate().to_cryptography().public_bytes(
                        Encoding.DER)
                    return (hostname, ntp_port, cookie, c2s, s2c,
                            hashlib.sha256(certificate).hexdigest(), (family, tcp_peer))


def _extension(kind, body):
    if len(body) % 4 or len(body) + 4 > 65535:
        raise NTSError('invalid extension length')
    return struct.pack('!HH', kind, len(body) + 4) + body


def _extensions(data, start=0):
    pos = start
    while pos < len(data):
        if pos + 4 > len(data):
            raise NTSError('truncated NTP extension')
        kind, length = struct.unpack_from('!HH', data, pos)
        if length < 4 or length % 4 or pos + length > len(data):
            raise NTSError('invalid NTP extension framing')
        yield kind, data[pos + 4:pos + length], pos
        pos += length


def _authenticated_extension(prefix, key, plaintext=b''):
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV

    nonce = os.urandom(16)
    ciphertext = AESSIV(key).encrypt(plaintext, [prefix, nonce])
    body = struct.pack('!HH', len(nonce), len(ciphertext)) + nonce + ciphertext
    body += b'\x00' * (-len(body) % 4)
    return _extension(0x0404, body)


def _request(cookie, key):
    uid, origin = os.urandom(32), os.urandom(8)
    header = bytes([0x23]) + bytes(39) + origin
    # Opaque NTS-KE cookies have no alignment constraint. Pad only the NTP
    # field (word boundary and 16-byte minimum), preserving every cookie byte.
    cookie_body = cookie + bytes(max(12, (len(cookie) + 3) // 4 * 4) - len(cookie))
    prefix = header + _extension(0x0104, uid) + _extension(0x0204, cookie_body)
    return prefix + _authenticated_extension(prefix, key), uid, origin


def _timestamp_ns(data, era):
    seconds, fraction = struct.unpack('!II', data)
    if not seconds and not fraction:
        raise NTSError('missing server timestamp')
    return ((era * 2**32 + seconds - 2208988800) * 10**9
            + fraction * 10**9 // 2**32)


def _response(packet, key, uid, origin, era):
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESSIV

    if len(packet) < 48:
        raise NTSError('short NTP response')
    fields = list(_extensions(packet, 48))
    identifiers = [body for kind, body, _ in fields if kind == 0x0104]
    authenticators = [(body, pos) for kind, body, pos in fields if kind == 0x0404]
    if identifiers != [uid] or len(authenticators) != 1 or fields[-1][0] != 0x0404:
        raise NTSError('missing authentication or wrong request identifier')
    if any(kind in (0x0204, 0x0304) for kind, _, _ in fields):
        raise NTSError('unencrypted server cookie or unexpected placeholder')
    body, position = authenticators[0]
    if len(body) < 4:
        raise NTSError('short NTS authenticator')
    nlen, clen = struct.unpack_from('!HH', body)
    cstart = 4 + (nlen + 3) // 4 * 4
    end = cstart + clen
    if not nlen or clen < 16 or end > len(body) or any(body[4 + nlen:cstart]) or any(body[end:]):
        raise NTSError('invalid NTS authenticator lengths or padding')
    try:
        plaintext = AESSIV(key).decrypt(body[cstart:end], [packet[:position], body[4:4 + nlen]])
    except InvalidTag as error:
        raise NTSError('NTS response authentication failed') from error
    encrypted = list(_extensions(plaintext))
    if sum(kind == 0x0204 for kind, _, _ in encrypted) != 1:
        raise NTSError('missing or excessive replacement cookies')
    if any(kind in (0x0104, 0x0304, 0x0404) for kind, _, _ in encrypted):
        raise NTSError('invalid encrypted NTS field')
    if packet[24:32] != origin:
        raise NTSError('wrong NTP origin timestamp')
    if packet[0] & 0x3f != 0x24 or packet[0] >> 6 != 0 or not 1 <= packet[1] <= 15:
        raise NTSError('unsupported mode/version, leap state, or unsynchronized server')
    received = _timestamp_ns(packet[32:40], era)
    transmitted = _timestamp_ns(packet[40:48], era)
    if transmitted < received:
        raise NTSError('server timestamps run backwards or cross unsupported era')
    return dict(server_receive_unix_ns=received, server_transmit_unix_ns=transmitted,
                stratum=packet[1], root_delay_raw=int.from_bytes(packet[4:8], 'big', signed=True),
                root_dispersion_raw=int.from_bytes(packet[8:12], 'big'),
                response_sha256=hashlib.sha256(packet).hexdigest())


def probe(server, *, timeout_s=5.0, ntp_era=0):
    """One authenticated exchange, paired with a bracketed host UTC reading.

    Bounds use monotonic time, not the potentially wrong host wall clock.
    The NTP era is explicit; it is never inferred from that wall clock.
    """
    if not math.isfinite(timeout_s) or timeout_s <= 0 or type(ntp_era) is not int or ntp_era < 0:
        raise ValueError('positive finite timeout and nonnegative integer NTP era required')
    from OpenSSL import SSL
    from service_identity import CertificateError, VerificationError

    try:
        host, port, cookie, c2s, s2c, certificate_hash, (tcp_family, tcp_peer) = _key_exchange(server, timeout_s)
    except (SSL.Error, CertificateError, VerificationError, UnicodeError) as error:
        raise NTSError(f'NTS-KE TLS/identity failure: {type(error).__name__}') from error
    request, uid, origin = _request(cookie, c2s)
    # Select one DNS endpoint; an unavailable first endpoint is retained rather
    # than hidden by polling or trying another address for a passing result.
    host_negotiated = host is not None
    if host_negotiated:
        family, socktype, protocol, _, address = socket.getaddrinfo(host, port, type=socket.SOCK_DGRAM)[0]
    else:
        # RFC 8915 §4.1.7: no server record means the actual TCP peer's IP,
        # including IPv6 scope/flow fields, with the negotiated/default UDP port.
        host = tcp_peer[0]
        family, socktype, protocol = tcp_family, socket.SOCK_DGRAM, 0
        address = (tcp_peer[0], port, *tcp_peer[2:])
    with socket.socket(family, socktype, protocol) as sock:
        sock.settimeout(timeout_s)
        sock.connect(address)
        sent = time.monotonic_ns()
        sock.send(request)
        packet = sock.recv(65536)
        claim_start = time.monotonic_ns()
        host_utc = time.time_ns()
        received = time.monotonic_ns()
        peer = sock.getpeername()
    result = _response(packet, s2c, uid, origin, ntp_era)
    result.update(server=server, ntp_host=host, ntp_port=port, peer_address=list(peer),
                  nts_ke_peer_address=list(tcp_peer), ntp_host_negotiated=host_negotiated,
                  authentication='NTS_TLS13_AES_SIV_256', certificate_sha256=certificate_hash,
                  ntp_era=ntp_era, send_monotonic_ns=sent, receive_monotonic_ns=received,
                  claim_start_monotonic_ns=claim_start, claim_end_monotonic_ns=received,
                  host_claim_unix_ns=host_utc,
                  monotonic_resolution_ns=max(1, math.ceil(time.get_clock_info('monotonic').resolution * 1e9)),
                  host_claim_error_ns=max(1, math.ceil(time.get_clock_info('time').resolution * 1e9)))
    return result
