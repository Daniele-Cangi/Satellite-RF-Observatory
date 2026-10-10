"""Real loopback TLS/exporter/UDP interoperability with the native Java client.

Synthetic certificates, keys and time only. No public endpoint or RF evidence.
The Android CI enables this test; the ordinary Python suite needs no JDK/SDK.
"""
import datetime
import ipaddress
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import threading
import time

import pytest
from OpenSSL import SSL
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.ciphers.aead import AESSIV
from cryptography.x509.oid import NameOID

from pnt.nts import _tls_call


def record(kind, body=b'', critical=False):
    return struct.pack('!HH', kind | (0x8000 if critical else 0), len(body)) + body


def extension(kind, body):
    return struct.pack('!HH', kind, len(body) + 4) + body


def certificate(key, address):
    # A generated, explicitly trusted test root also supplies the leaf identity.
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'loopback test only')])
    now = datetime.datetime.now(datetime.timezone.utc)
    return (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(address))]),
                           critical=False).sign(key, hashes.SHA256()))


@pytest.mark.skipif(os.environ.get('PNT_ANDROID_NTS_INTEGRATION') != '1',
                    reason='Real native-client integration runs in Android collector CI')
def test_java_tls_identity_exporter_keys_udp_authentication_and_timeout(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    good = certificate(key, '127.0.0.1')
    wrong = certificate(key, '192.0.2.1')
    ca_file = tmp_path / 'test-ca.pem'
    # Both roots trusted: the wrong-IP case must fail identity, not chain trust.
    ca_file.write_bytes(good.public_bytes(serialization.Encoding.PEM)
                        + wrong.public_bytes(serialization.Encoding.PEM))
    servers, threads, errors, received = [], [], [], []
    cases = []

    def serve(mode, listener, udp, context):
        try:
            conn, _ = listener.accept()
            with conn:
                conn.setblocking(False)
                tls = SSL.Connection(context, conn)
                tls.set_accept_state()
                deadline = time.monotonic() + 5
                _tls_call(tls, tls.do_handshake, deadline)
                request = b''
                while len(request) < 16:
                    chunk = _tls_call(tls, lambda: tls.recv(16 - len(request)), deadline)
                    if not chunk:
                        return
                    request += chunk
                assert request == record(1, b'\0\0', True) + record(4, b'\0\x0f') + record(0, critical=True)
                response = (record(1, b'\0\0', True) + record(4, b'\0\x0f')
                            + record(5, bytes(16)) + record(7, struct.pack('!H', udp.getsockname()[1]))
                            + (record(6, b'127.0.0.1') if mode == 'valid_negotiated' else b'')
                            + record(0, critical=True))
                # Fragmented application reads exercise native readFully().
                for chunk in (response[:3], response[3:]):
                    offset = 0
                    while offset < len(chunk):
                        offset += _tls_call(tls, lambda: tls.send(chunk[offset:]), deadline)
                c2s = tls.export_keying_material(b'EXPORTER-network-time-security', 32, b'\0\0\0\x0f\0')
                s2c = tls.export_keying_material(b'EXPORTER-network-time-security', 32, b'\0\0\0\x0f\x01')
                assert c2s != s2c
            packet, peer = udp.recvfrom(65536)
            received.append(mode)
            uid = packet[52:84]
            cookie_kind, cookie_length = struct.unpack_from('!HH', packet, 84)
            assert cookie_kind == 0x0204
            auth_start = 84 + cookie_length
            auth_kind, auth_length, nonce_length, cipher_length = struct.unpack_from('!HHHH', packet, auth_start)
            assert auth_kind == 0x0404 and auth_start + auth_length == len(packet)
            nonce = packet[auth_start + 8:auth_start + 8 + nonce_length]
            cipher_start = auth_start + 8 + (nonce_length + 3) // 4 * 4
            assert AESSIV(c2s).decrypt(packet[cipher_start:cipher_start + cipher_length],
                                       [packet[:auth_start], nonce]) == b''
            if mode == 'silent_udp':
                return
            header = bytearray(48)
            header[0:2] = b'\x24\x01'
            header[24:32] = packet[40:48]
            header[32:40] = struct.pack('!II', 1700000000 + 2208988800, 0)
            header[40:48] = struct.pack('!II', 1700000001 + 2208988800, 0)
            prefix = bytes(header) + extension(0x0104, uid)
            nonce = bytes(range(16))
            ciphertext = AESSIV(s2c).encrypt(extension(0x0204, bytes(16)), [prefix, nonce])
            reply = prefix + extension(0x0404, struct.pack('!HH', 16, len(ciphertext)) + nonce + ciphertext)
            if mode == 'tampered_udp':
                reply = reply[:-1] + bytes([reply[-1] ^ 1])
            udp.sendto(reply, peer)
        except (SSL.Error, OSError):
            if mode in ('valid', 'valid_negotiated', 'tampered_udp', 'silent_udp'):
                errors.append(mode + ': unexpected server I/O failure')
        except Exception as error:
            errors.append(f'{mode}: {type(error).__name__}: {error}')

    try:
        for mode in ('valid', 'valid_negotiated', 'untrusted', 'wrong_identity', 'missing_alpn', 'legacy_tls',
                     'tampered_udp', 'silent_udp'):
            context = SSL.Context(SSL.TLS_SERVER_METHOD)
            context.set_min_proto_version(SSL.TLS1_3_VERSION)
            if mode == 'legacy_tls':
                # Deliberately incompatible test server; the client must reject it.
                context.set_min_proto_version(SSL.TLS1_2_VERSION)
                context.set_max_proto_version(SSL.TLS1_2_VERSION)
            context.use_certificate(wrong if mode == 'wrong_identity' else good)
            context.use_privatekey(key)
            if mode != 'missing_alpn':
                context.set_alpn_select_callback(lambda connection, protocols: b'ntske/1')
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            listener.settimeout(120)
            udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp.bind(('127.0.0.1', 0))
            udp.settimeout(5)
            servers.extend((listener, udp))
            cases.append(dict(name=mode, port=listener.getsockname()[1],
                              trusted=mode != 'untrusted', accepted=mode in ('valid', 'valid_negotiated')))
            if mode == 'valid_negotiated':
                cases[-1]['negotiated_host'] = '127.0.0.1'
            thread = threading.Thread(target=serve, args=(mode, listener, udp, context), daemon=True)
            threads.append(thread)
            thread.start()
        config = tmp_path / 'loopback.json'
        config.write_text(json.dumps(dict(ca_file=str(ca_file), cases=cases)))
        collector = Path(__file__).resolve().parents[1] / 'android-collector'
        wrapper = str(collector / ('gradlew.bat' if os.name == 'nt' else 'gradlew'))
        run = subprocess.run([wrapper, '--no-daemon', ':app:testDebugUnitTest', '--tests',
                              'org.satelliterf.observatory.clock.NtsClientTest.realTlsLoopbackEnforcesIdentityAlpnAndTlsFloor'],
                             cwd=collector, env=os.environ | {'PNT_NTS_LOOPBACK_CONFIG': str(config)},
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
        assert run.returncode == 0, run.stdout
        for thread in threads:
            thread.join(timeout=6)
        assert not any(thread.is_alive() for thread in threads)
        assert not errors, errors
        assert received == ['valid', 'valid_negotiated', 'tampered_udp', 'silent_udp']
    finally:
        for server in servers:
            server.close()
        for thread in threads:
            thread.join(timeout=1)
