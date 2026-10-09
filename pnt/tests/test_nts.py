import datetime
import socket
import ssl
import struct
import threading

import pytest
from OpenSSL import SSL
from cryptography import x509
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.x509.oid import NameOID
from service_identity import VerificationError

from pnt import nts


KEY = bytes(range(32))
UID = bytes(range(32, 64))
ORIGIN = bytes(range(8))


def stamp(seconds):
    return struct.pack('!II', seconds + 2208988800, 0)


def response(*, uid=UID, origin=ORIGIN, header_byte=0x24, stratum=1, prefix_extra=b'', encrypted=None):
    header = bytearray(48)
    header[0:2] = bytes([header_byte, stratum])
    header[24:32] = origin
    header[32:40] = stamp(1700000000)
    header[40:48] = stamp(1700000001)
    prefix = bytes(header) + nts._extension(0x0104, uid) + prefix_extra
    cookies = nts._extension(0x0204, bytes(16)) if encrypted is None else encrypted
    # Construct a server packet independently of the client's authenticator
    # helper, including the RFC's exact associated-data and nonce boundaries.
    nonce = bytes(range(16))
    ciphertext = AESSIV(KEY).encrypt(cookies, [prefix, nonce])
    body = struct.pack('!HH', 16, len(ciphertext)) + nonce + ciphertext
    return prefix + struct.pack('!HH', 0x0404, len(body) + 4) + body


def test_authenticated_ntp_response_and_client_request():
    result = nts._response(response(), KEY, UID, ORIGIN, 0)
    assert result['server_receive_unix_ns'] == 1700000000000000000
    assert result['server_transmit_unix_ns'] == 1700000001000000000
    request, uid, origin = nts._request(bytes(16), KEY)
    assert len(uid) == 32 and len(origin) == 8 and request[40:48] == origin
    fields = list(nts._extensions(request, 48))
    assert [f[0] for f in fields] == [0x0104, 0x0204, 0x0404]
    body, pos = fields[-1][1:]
    assert AESSIV(KEY).decrypt(body[20:], [request[:pos], body[4:20]]) == b''
    _, fresh_uid, fresh_origin = nts._request(bytes(16), KEY)
    assert uid != fresh_uid and origin != fresh_origin


@pytest.mark.parametrize('mutation', ['header', 'tag', 'truncated', 'plain', 'replay', 'wrong_key', 'origin',
                                    'duplicate_uid', 'cookie_clear', 'missing_cookie', 'extra_cookie',
                                    'tail', 'leap', 'unsync', 'kod', 'version', 'extension_length'])
def test_response_rejects_tampering_replay_and_unqualified_time(mutation):
    packet, key, uid = response(), KEY, UID
    if mutation in ('header', 'tag'):
        altered = bytearray(packet)
        altered[35 if mutation == 'header' else -1] ^= 1
        packet = bytes(altered)
    elif mutation == 'truncated':
        packet = packet[:-1]
    elif mutation == 'plain':
        packet = packet[:48]
    elif mutation == 'replay':
        uid = bytes(32)
    elif mutation == 'wrong_key':
        key = bytes(32)
    elif mutation == 'origin':
        packet = response(origin=bytes(8))
    elif mutation == 'duplicate_uid':
        packet = response(prefix_extra=nts._extension(0x0104, UID))
    elif mutation == 'cookie_clear':
        packet = response(prefix_extra=nts._extension(0x0204, bytes(16)))
    elif mutation == 'missing_cookie':
        packet = response(encrypted=b'')
    elif mutation == 'extra_cookie':
        packet = response(encrypted=nts._extension(0x0204, bytes(16)) * 2)
    elif mutation == 'tail':
        packet += nts._extension(0x9999, bytes(16))
    elif mutation in ('leap', 'unsync', 'version'):
        packet = response(header_byte={'leap': 0x64, 'unsync': 0xe4, 'version': 0x1c}[mutation])
    elif mutation == 'kod':
        packet = response(stratum=0)
    else:
        packet = packet[:50] + b'\x00\x03' + packet[52:]
    with pytest.raises(nts.NTSError):
        nts._response(packet, key, uid, ORIGIN, 0)


def negotiation(cookie=bytes(16)):
    return (nts._record(1, b'\x00\x00', True) + nts._record(4, b'\x00\x0f')
            + nts._record(5, cookie) + nts._record(0, critical=True))


def test_ke_endpoint_is_bound_to_authenticated_negotiation():
    endpoint = nts._record(6, b'other.example') + nts._record(7, struct.pack('!H', 8123))
    assert nts._ke_parameters(endpoint + negotiation())[:2] == ('other.example', 8123)
    assert nts._ke_parameters(nts._record(99, b'ignored') + negotiation())[:2] == (None, 123)


@pytest.mark.parametrize('cookie', [b'', b'x', b'opaque-cookie\x00', b'\x80' * 15, bytes(16), bytes(range(17))])
def test_opaque_cookie_bytes_are_preserved_and_padding_is_authenticated(cookie):
    negotiated = nts._ke_parameters(negotiation(cookie))[2]
    assert negotiated == cookie
    packet, _, _ = nts._request(negotiated, KEY)
    fields = list(nts._extensions(packet, 48))
    body, position = fields[1][1:]
    assert body[:len(cookie)] == cookie
    assert body[len(cookie):] == bytes(len(body) - len(cookie))
    assert len(body) >= 12 and len(body) % 4 == 0
    auth, auth_start = fields[-1][1:]
    assert AESSIV(KEY).decrypt(auth[20:], [packet[:auth_start], auth[4:20]]) == b''
    altered = bytearray(packet[:auth_start])
    altered[position + 4] ^= 1
    with pytest.raises(InvalidTag):
        AESSIV(KEY).decrypt(auth[20:], [bytes(altered), auth[4:20]])


@pytest.mark.parametrize('packet', [b'', negotiation()[:-1], negotiation() + b'\x00',
                                  nts._record(99, critical=True) + negotiation(),
                                  nts._record(4, b'\x00\x0f') + negotiation(),
                                  nts._record(2, b'\x00\x00') + negotiation(),
                                  negotiation().replace(b'\x00\x0f', b'\x00\x01'),
                                  nts._record(7, b'\x00') + negotiation(),
                                  bytes(65537)], ids=['empty', 'truncated', 'after-end', 'critical', 'duplicate',
                                                     'error', 'aead', 'port', 'oversize'])
def test_ke_rejects_invalid_or_unsupported_negotiation(packet):
    with pytest.raises(nts.NTSError):
        nts._ke_parameters(packet)


def test_explicit_ntp_era_is_independent_of_local_calendar(monkeypatch):
    monkeypatch.setattr(nts.time, 'time_ns', lambda: pytest.fail('claimant calendar must not choose era'))
    assert nts._timestamp_ns(stamp(1700000000), 1) - nts._timestamp_ns(stamp(1700000000), 0) == 2**32 * 10**9


@pytest.mark.parametrize('trusted,hostname,alpn,legacy_tls', [
    (True, 'localhost', True, False), (True, 'wrong.example', True, False),
    (False, 'localhost', True, False), (True, 'localhost', False, False),
    (True, 'localhost', True, True)])
def test_tls_chain_hostname_and_alpn_are_enforced(tmp_path, monkeypatch, trusted, hostname, alpn, legacy_tls):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'loopback root')])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
                   .serial_number(1).not_valid_before(now - datetime.timedelta(days=1))
                   .not_valid_after(now + datetime.timedelta(days=1))
                   .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
                   .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
                   .sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path / 'ca.pem', tmp_path / 'key.pem'
    cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2 if legacy_tls else ssl.TLSVersion.TLSv1_3
    if legacy_tls:
        context.maximum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(cert_file, key_file)
    if alpn:
        context.set_alpn_protocols(['ntske/1'])
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(5)
        # This fixture listens on IPv4. Do not depend on localhost DNS ordering
        # now that production intentionally makes only one TCP address attempt.
        resolver = socket.getaddrinfo

        def fixture_dns(host, port, **kwargs):
            if host == 'localhost' and port == listener.getsockname()[1]:
                return resolver('127.0.0.1', port, **kwargs)
            return resolver(host, port, **kwargs)

        monkeypatch.setattr(socket, 'getaddrinfo', fixture_dns)

        def serve():
            try:
                conn, _ = listener.accept()
                with conn, context.wrap_socket(conn, server_side=True) as tls:
                    tls.settimeout(5)
                    if tls.recv(4096):
                        # Exercise fragmented TLS application reads.
                        data = negotiation()
                        tls.sendall(data[:3])
                        tls.sendall(data[3:])
            except (OSError, ssl.SSLError):
                pass  # Expected when a client rejects the certificate.

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            if trusted and hostname == 'localhost' and alpn and not legacy_tls:
                parameters = nts._key_exchange('localhost', 5, port=listener.getsockname()[1], ca_file=str(cert_file))
                assert len(parameters[3]) == len(parameters[4]) == 32
                assert parameters[3] != parameters[4]
                assert parameters[0] is None
                assert parameters[6] == (socket.AF_INET, ('127.0.0.1', listener.getsockname()[1]))
            else:
                expected = (SSL.Error if not trusted or legacy_tls else
                            VerificationError if hostname != 'localhost' else nts.NTSError)
                with pytest.raises(expected):
                    nts._key_exchange('localhost', 5, port=listener.getsockname()[1],
                                      ca_file=str(cert_file) if trusted else None)
        finally:
            thread.join(timeout=6)
            assert not thread.is_alive()


def test_first_tcp_address_failure_is_retained_without_trying_the_next(monkeypatch):
    from pnt.time_witness import collect

    contacts = []
    addresses = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, '', (ip, 4460))
                 for ip in ('192.0.2.10', '192.0.2.20')]

    class FailedSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, timeout):
            pass

        def close(self):
            pass

        def connect(self, address):
            contacts.append(address)
            raise ConnectionRefusedError('first address unavailable')

    monkeypatch.setattr(nts.socket, 'getaddrinfo', lambda *a, **k: addresses)
    monkeypatch.setattr(nts.socket, 'socket', lambda *a, **k: FailedSocket())
    report = collect(['multi.example'], server_error_ns=1000000, rate_error_ppm=100,
                     budget_source='test assumption')
    assert contacts == [('192.0.2.10', 4460)]
    assert len(report['attempts']) == 1
    failure = report['attempts'][0]
    assert failure['status'] == 'WITNESS_UNAVAILABLE'
    assert '192.0.2.10' in failure['reason'] and 'ConnectionRefusedError' in failure['reason']


@pytest.mark.parametrize('tcp_family,tcp_peer,negotiated_host', [
    (socket.AF_INET, ('192.0.2.10', 4460), None),
    (socket.AF_INET6, ('fe80::1234', 4460, 7, 12), None),
    (socket.AF_INET, ('192.0.2.10', 4460), 'redirect.example')])
def test_udp_uses_tcp_peer_unless_authenticated_negotiation_redirects(monkeypatch, tcp_family, tcp_peer, negotiated_host):
    contacts, resolutions, sockets = [], [], []
    udp_peer = ((tcp_peer[0], 8123, *tcp_peer[2:]) if negotiated_host is None else ('192.0.2.20', 8123))
    monkeypatch.setattr(nts, '_key_exchange', lambda *a, **k:
                        (negotiated_host, 8123, bytes(16), KEY, KEY, 'certificate', (tcp_family, tcp_peer)))

    def resolve(host, port, **kwargs):
        resolutions.append((host, port))
        if negotiated_host is None:
            pytest.fail('no second DNS lookup allowed for an omitted server record')
        return [(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP, '', udp_peer)]

    class ReplySocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, timeout):
            pass

        def connect(self, address):
            contacts.append(address)

        def send(self, packet):
            self.request = packet
            return len(packet)

        def recv(self, limit):
            uid = list(nts._extensions(self.request, 48))[0][1]
            return response(uid=uid, origin=self.request[40:48])

        def getpeername(self):
            return udp_peer

    monkeypatch.setattr(nts.socket, 'getaddrinfo', resolve)
    def create_socket(*args):
        sockets.append(args)
        return ReplySocket()

    monkeypatch.setattr(nts.socket, 'socket', create_socket)
    result = nts.probe('multi.example')
    assert contacts == [udp_peer]
    assert sockets[0][0] == (tcp_family if negotiated_host is None else socket.AF_INET)
    assert resolutions == ([] if negotiated_host is None else [('redirect.example', 8123)])
    assert result['nts_ke_peer_address'] == list(tcp_peer)
    assert result['peer_address'] == list(udp_peer)
    assert result['ntp_host_negotiated'] is (negotiated_host is not None)
    assert result['authentication'] == 'NTS_TLS13_AES_SIV_256'
