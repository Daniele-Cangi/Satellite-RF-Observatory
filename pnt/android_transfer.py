"""Explicit, bounded LAN transport into the existing AndroidSessionMonitor.

Research foreground receiver, not a public upload service or another detector.
TLS and a per-run credential protect transport; they do not attest GNSS evidence.
"""
import base64
import copy
import datetime
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import sys
import threading
import time

from .__main__ import write_report
from .android_session import _options
from .session_monitor import AndroidSessionMonitor
from .time_witness import _integer

MAX_SNAPSHOT = 32 * 1024 * 1024
MAX_RUN_BYTES = 128 * 1024 * 1024
MAX_REQUESTS = 256


def lan_address(address):
    value = ipaddress.IPv4Address(address)
    if not any(value in ipaddress.IPv4Network(n) for n in
               ('127.0.0.0/8', '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('bind must be an explicit loopback or private LAN IPv4 address')
    return str(value)


def prepare_connection(directory, address, port):
    """New private directory: share connection.json, never server-key.pem."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    address = lan_address(address)
    _integer(port, 'port', 1)
    if port > 65535:
        raise ValueError('port exceeds 65535')
    directory = Path(directory)
    if os.name == 'nt' and sys.version_info < (3, 13):
        raise ValueError('private receiver directory creation on Windows requires Python 3.13+')
    # Apply access control at creation, before any credential or native byte.
    # Python 3.13 also implements 0700 as a user/admin-only Windows DACL.
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'PNT private PC receiver')])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now-datetime.timedelta(minutes=5))
        .not_valid_after(now+datetime.timedelta(days=7))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address(address))]), critical=False)
        .sign(key, hashes.SHA256()))
    (directory/'server-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    (directory/'server-cert.pem').write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    for name in ('server-key.pem', 'server-cert.pem'):
        (directory/name).chmod(0o600)
    config = dict(schema='pnt-android-pc-connection-v1', url=f'https://{address}:{port}',
        token=secrets.token_hex(32), certificate_der=base64.b64encode(
            certificate.public_bytes(serialization.Encoding.DER)).decode('ascii'))
    write_report(config, directory/'connection.json')
    (directory/'connection.json').chmod(0o600)
    return config


class AndroidReceiver(HTTPServer):
    """One serialized connection/snapshot at a time; no shared-file read race."""
    def __init__(self, address, directory, config, *, analysis_options=None, local_counter_resolution_ns, on_update=None):
        _options(analysis_options)
        _integer(local_counter_resolution_ns, 'local_counter_resolution_ns', 1)
        self.directory, self.config = Path(directory), copy.deepcopy(config)
        self.options, self.resolution = copy.deepcopy(analysis_options), local_counter_resolution_ns
        self.on_update = on_update
        self.monitor, self.capture_id = None, None
        self.requests, self.received_bytes, self.accepted, self.failed = 0, 0, 0, 0
        self.fatal = None
        self.deadline = math.inf
        self.request_timer = None
        super().__init__(address, _Handler)
        self.timeout = .5
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.directory/'server-cert.pem', self.directory/'server-key.pem')
        self.socket = context.wrap_socket(self.socket, server_side=True, do_handshake_on_connect=False)

    def get_request(self):
        request, address = super().get_request()
        # Per-read socket timeouts alone permit an indefinitely trickling peer.
        # Bound handshake, headers and body together, including the run deadline.
        def expire():
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        self.request_timer = threading.Timer(max(.001, min(10, self.deadline-time.monotonic())), expire)
        self.request_timer.daemon = True
        self.request_timer.start()
        return request, address

    def close_request(self, request):
        if self.request_timer is not None:
            self.request_timer.cancel()
        super().close_request(request)

    def event(self, **values):
        with (self.directory/'transport.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(dict(pc_monotonic_ns=time.monotonic_ns(), **values), sort_keys=True)+'\n')

    def handle_error(self, request, client_address):
        self.failed += 1
        self.event(kind='CONNECTION_FAILED', reason='TLS_HTTP_OR_RESPONSE_DELIVERY_FAILED')

    def accept_snapshot(self, capture_id, raw, nts):
        if self.fatal:
            raise ValueError('receiver stopped after a storage/admission failure')
        if self.capture_id is not None and self.capture_id != capture_id:
            raise ValueError('receiver already bound to a different capture')
        if self.monitor is None:
            self.capture_id = capture_id
            inputs = self.directory/'inputs'
            inputs.mkdir()
            self.monitor = AndroidSessionMonitor(inputs/f'pnt-clock-{capture_id}.txt',
                inputs/f'pnt-nts-{capture_id}.json', self.directory/'monitor',
                analysis_options=self.options, local_counter_resolution_ns=self.resolution)
        # Working copies only. poll() retains changed native bytes and all issues;
        # handlers never run concurrently and poll runs only after both writes.
        try:
            self.monitor.raw_path.write_bytes(raw)
            self.monitor.nts_path.write_bytes(nts)
            receipt = self.monitor.poll()
            if receipt is not None and self.on_update is not None:
                self.on_update(receipt)
        except OSError as error:
            self.fatal = 'PC_STORAGE_OR_TRANSPORT_FAILED'
            self.monitor.invalidate(f'Native snapshot admission failed: {error}')
            raise
        self.accepted += 1
        self.event(kind='SNAPSHOT_RECEIVED', capture_id=capture_id, size_bytes=len(raw)+len(nts),
                   changed=receipt is not None, update_index=self.monitor.updates)
        return dict(schema='pnt-android-transfer-receipt-v1', capture_id=capture_id,
            stored=True, update_index=self.monitor.updates,
            status=self.monitor.last_update['status'], issues=self.monitor.last_update['issues'],
            session_complete=self.monitor.last_update['session_complete'],
            scope='TRANSPORT_RECEIPT_ONLY; NOT_A_PHONE_TIMING_OR_SECURITY_VERDICT')


class _Handler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self, *_):
        pass  # No credentials, untrusted paths or phone metadata in console logs.

    def reply(self, status, payload):
        body = json.dumps(payload, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def authorized(self):
        values = self.headers.get_all('Authorization', [])
        valid = len(values) == 1 and hmac.compare_digest(values[0].encode(),
            ('Bearer '+self.server.config['token']).encode())
        if not valid:
            self.server.failed += 1
            self.server.event(kind='REQUEST_REJECTED', reason='UNAUTHORIZED')
            self.reply(401, dict(error='UNAUTHORIZED'))
        return valid

    def do_GET(self):
        if not self.authorized():
            return
        if self.path != '/health':
            self.reply(404, dict(error='UNKNOWN_PATH'))
            return
        self.reply(200, dict(schema='pnt-android-transfer-receipt-v1', ready=True))

    def do_POST(self):
        server = self.server
        if not self.authorized():
            return
        server.requests += 1
        try:
            if self.path != '/snapshot' or self.headers.get('Transfer-Encoding') is not None:
                raise ValueError('unsupported path or transfer encoding')
            for field in ('Content-Length', 'X-PNT-Raw-Bytes', 'X-PNT-Capture-Id', 'Content-Type'):
                if len(self.headers.get_all(field, [])) != 1:
                    raise ValueError('missing or duplicate snapshot header')
            capture_id = self.headers['X-PNT-Capture-Id']
            if not re.fullmatch(r'[a-zA-Z0-9-]{1,80}', capture_id):
                raise ValueError('invalid capture ID')
            if self.headers['Content-Type'] != 'application/octet-stream':
                raise ValueError('unsupported content type')
            size, raw_size = int(self.headers['Content-Length']), int(self.headers['X-PNT-Raw-Bytes'])
            if not 0 < raw_size < size <= MAX_SNAPSHOT:
                raise ValueError('invalid or oversized snapshot length')
            if server.requests > MAX_REQUESTS or size > MAX_RUN_BYTES-server.received_bytes:
                raise ValueError('foreground receiver storage/request limit reached')
            if server.capture_id is not None and capture_id != server.capture_id:
                raise ValueError('receiver already bound to a different capture')
            try:
                body = self.rfile.read(size)
            except OSError:
                raise ValueError('incomplete or timed-out snapshot; no partial pair admitted') from None
            server.received_bytes += len(body)
            if len(body) != size:
                raise ValueError('truncated snapshot; no partial pair admitted')
            result = server.accept_snapshot(capture_id, body[:raw_size], body[raw_size:])
        except (ValueError, OSError) as error:
            server.failed += 1
            if isinstance(error, OSError):
                server.fatal = 'PC_STORAGE_OR_TRANSPORT_FAILED'
                if server.monitor:
                    server.monitor.invalidate(f'Native snapshot admission/retention failed: {error}')
            try:
                server.event(kind='REQUEST_REJECTED', reason=str(error))
            except OSError:
                server.fatal = 'PC_STORAGE_OR_TRANSPORT_FAILED'
                if server.monitor:
                    server.monitor.invalidate('Transport failure could not be recorded')
            self.reply(400, dict(error=str(error)))
            return
        self.reply(200, result)


def serve_android(directory, address, port, *, analysis_options=None,
                  local_counter_resolution_ns, duration_s=120, on_ready=None, on_update=None):
    if isinstance(duration_s, bool) or not isinstance(duration_s, (int, float)) or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError('duration_s must be finite and positive')
    _options(analysis_options)
    _integer(local_counter_resolution_ns, 'local_counter_resolution_ns', 1)
    config = prepare_connection(directory, address, port)
    reason = 'DURATION_LIMIT'
    with AndroidReceiver((address, port), directory, config, analysis_options=analysis_options,
                         local_counter_resolution_ns=local_counter_resolution_ns, on_update=on_update) as server:
        if on_ready is not None:
            on_ready(Path(directory)/'connection.json')
        deadline = time.monotonic()+duration_s
        server.deadline = deadline
        try:
            while time.monotonic() < deadline:
                server.handle_request()
                if server.fatal:
                    reason = server.fatal
                    break
                if server.monitor and server.monitor.last_update and server.monitor.last_update['session_complete']:
                    reason = 'SESSION_TERMINALS_OBSERVED'
                    break
        except KeyboardInterrupt:
            reason = 'USER_INTERRUPTED_RECEIVER'
        summary = dict(schema='pnt-android-transfer-summary-v1', stop_reason=reason,
            accepted_snapshots=server.accepted, rejected_requests=server.failed,
            received_bytes=server.received_bytes, capture_id=server.capture_id,
            scope='PRIVATE_FOREGROUND_LAN_TRANSPORT', phone_operator_alert_latency_measured=False,
            monitor=server.monitor.finish(reason) if server.monitor else None)
        write_report(summary, Path(directory)/'summary.json', durable=True)
        return summary
