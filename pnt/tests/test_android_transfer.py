"""Private HTTPS transport: exact native bytes -> existing monitor, synthetic only."""
import copy
import http.client
import json
import os
from pathlib import Path
import ssl
import socket
import subprocess
import threading
import time

import pytest

from pnt.android_transfer import AndroidReceiver, MAX_SNAPSHOT, lan_address, prepare_connection, serve_android
from pnt.tests.test_session_monitor import ANALYSIS, native_data, ongoing


@pytest.fixture
def receiver(tmp_path):
    directory = tmp_path/'receiver'
    config = prepare_connection(directory, '127.0.0.1', 8443)
    server = AndroidReceiver(('127.0.0.1', 0), directory, config,
        analysis_options=ANALYSIS, local_counter_resolution_ns=1)
    config['url'] = f'https://127.0.0.1:{server.server_port}'
    thread = threading.Thread(target=server.serve_forever, kwargs=dict(poll_interval=.02), daemon=True)
    thread.start()
    try:
        yield server, config
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
        assert not thread.is_alive()


def client_context(server):
    context = ssl.create_default_context(cafile=str(server.directory/'server-cert.pem'))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


def request(server, config, *, raw=None, witness=None, token=None, capture_id='synthetic-monitor', headers=None):
    context = client_context(server)
    client = http.client.HTTPSConnection('127.0.0.1', server.server_port, context=context, timeout=10)
    body = raw+json.dumps(witness).encode() if raw is not None else None
    fields = dict(Authorization='Bearer '+(token if token is not None else config['token']))
    if raw is not None:
        fields.update({'X-PNT-Capture-Id': capture_id, 'X-PNT-Raw-Bytes': str(len(raw)),
                       'Content-Type': 'application/octet-stream'})
    fields.update(headers or {})
    try:
        client.request('POST' if raw is not None else 'GET', '/snapshot' if raw is not None else '/health', body, fields)
        response = client.getresponse()
        return response.status, json.loads(response.read())
    finally:
        client.close()


def test_health_and_unauthorized_requests_never_start_monitor(receiver):
    server, config = receiver
    assert request(server, config)[1]['ready'] is True
    assert request(server, config, token='wrong')[0] == 401
    assert server.monitor is None
    assert not (server.directory/'inputs').exists()
    assert config['token'] not in (server.directory/'transport.jsonl').read_text()


def test_native_prefixes_reuse_monitor_and_preserve_exact_bytes_and_revisions(receiver):
    server, config = receiver
    _, pieces, closed, witness = native_data(two_endpoints=True, shifted=True)
    first = ongoing(witness, 7, active=7)
    status, receipt = request(server, config, raw=pieces[1], witness=first)
    assert status == 200 and receipt['stored'] and not receipt['session_complete']
    assert server.monitor.last_update['record_outcomes'][1]['combined'] == 'INCONSISTENT'
    folder = server.monitor.output/'update-00001'
    assert (folder/'pnt-clock-synthetic-monitor.txt').read_bytes() == pieces[1]
    assert json.loads((folder/'pnt-nts-synthetic-monitor.json').read_bytes()) == first
    assert request(server, config, raw=pieces[1], witness=first)[1]['update_index'] == 1
    assert request(server, config, raw=pieces[1], witness=ongoing(witness, 8))[0] == 200
    assert server.monitor.last_update['record_outcomes'][1]['combined'] == 'INCONCLUSIVE'
    assert server.monitor.last_update['revisions'][0]['previous'] is not None
    assert request(server, config, raw=closed, witness=witness)[1]['session_complete']
    assert server.monitor.updates == 3


def test_accepted_malformed_native_pair_clears_outcomes_and_retains_failure(receiver):
    server, config = receiver
    _, pieces, _, witness = native_data()
    assert request(server, config, raw=pieces[1], witness=ongoing(witness, 6))[0] == 200
    assert server.monitor.last_update['record_outcomes']
    status, receipt = request(server, config, raw=b'corrupt original bytes\n', witness={})
    assert status == 200 and receipt['status'] == 'INSUFFICIENT_EVIDENCE' and receipt['issues']
    assert server.monitor.last_update['record_outcomes'] == {}
    assert (server.monitor.output/'update-00002'/'pnt-clock-synthetic-monitor.txt').read_bytes() == b'corrupt original bytes\n'


@pytest.mark.parametrize('headers', [
    {'X-PNT-Capture-Id': '../elsewhere'}, {'X-PNT-Raw-Bytes': '-1'},
    {'Content-Length': str(MAX_SNAPSHOT+1)}, {'Transfer-Encoding': 'chunked'},
    {'Content-Type': 'text/plain'}])
def test_bad_framing_is_rejected_before_monitor(receiver, headers):
    server, config = receiver
    _, pieces, _, witness = native_data()
    assert request(server, config, raw=pieces[0], witness=ongoing(witness, 1), headers=headers)[0] == 400
    assert server.monitor is None


def test_different_capture_and_rewritten_history_cannot_hide_originals(receiver):
    server, config = receiver
    _, pieces, _, witness = native_data()
    first = ongoing(witness, 6)
    assert request(server, config, raw=pieces[1], witness=first)[0] == 200
    assert request(server, config, raw=pieces[1], witness=first, capture_id='different')[0] == 400
    assert server.monitor.updates == 1
    changed = copy.deepcopy(first)
    changed['attempts'][0]['exchange']['server_receive_unix_ns'] += 1
    receipt = request(server, config, raw=pieces[1], witness=changed)[1]
    assert receipt['issues'] and receipt['status'] == 'INSUFFICIENT_EVIDENCE'
    assert server.monitor.last_update['record_outcomes'] == {}
    original = server.monitor.output/'update-00001'/'pnt-nts-synthetic-monitor.json'
    assert json.loads(original.read_bytes()) == first


def test_truncated_tls_upload_never_publishes_partial_pair(receiver):
    server, config = receiver
    rejected = threading.Event()
    original_event = server.event

    def observed(**values):
        original_event(**values)
        if values['kind'] == 'REQUEST_REJECTED':
            rejected.set()

    server.event = observed
    context = client_context(server)
    with context.wrap_socket(socket.create_connection(('127.0.0.1', server.server_port)), server_hostname='127.0.0.1') as client:
        headers = ('POST /snapshot HTTP/1.1\r\nHost: 127.0.0.1\r\n'
            f"Authorization: Bearer {config['token']}\r\n"
            'Content-Type: application/octet-stream\r\nContent-Length: 100\r\n'
            'X-PNT-Raw-Bytes: 20\r\nX-PNT-Capture-Id: synthetic-monitor\r\n\r\n')
        client.sendall(headers.encode()+b'only a prefix')
        client.shutdown(socket.SHUT_WR)
        assert rejected.wait(8)
    assert server.monitor is None and not (server.directory/'inputs').exists()
    events = [json.loads(line) for line in (server.directory/'transport.jsonl').read_text().splitlines()]
    assert any('no partial pair admitted' in event.get('reason', '') for event in events)


def test_incomplete_headers_cannot_hold_receiver_past_its_deadline(receiver):
    server, config = receiver
    context = client_context(server)
    server.deadline = time.monotonic()+.5
    with context.wrap_socket(socket.create_connection(('127.0.0.1', server.server_port)), server_hostname='127.0.0.1') as client:
        client.settimeout(2)
        client.sendall(b'POST /snapshot HTTP/1.1\r\nHost: 127.0.0.1\r\nAuthorization: ')
        started = time.monotonic()
        try:
            client.recv(1024)
        except (ConnectionError, ssl.SSLError):
            pass
        assert time.monotonic()-started < 2
    assert server.monitor is None


@pytest.mark.parametrize('address', ['0.0.0.0', '8.8.8.8', '169.254.1.1', '::1', 'localhost'])
def test_receiver_rejects_unspecified_public_and_non_ipv4_bind(address):
    with pytest.raises(ValueError):
        lan_address(address)


def test_duration_and_no_overwrite(tmp_path):
    directory = tmp_path/'run'
    # Port selected by OS only in this test; public CLI port must be explicit/known.
    from socket import socket
    with socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    summary = serve_android(directory, '127.0.0.1', port, duration_s=.01, local_counter_resolution_ns=1)
    assert summary['monitor'] is None and summary['accepted_snapshots'] == 0
    assert summary['stop_reason'] == 'DURATION_LIMIT'
    with pytest.raises(FileExistsError):
        prepare_connection(directory, '127.0.0.1', port)


@pytest.mark.skipif(os.environ.get('PNT_ANDROID_NTS_INTEGRATION') != '1',
                   reason='Native HTTPS transport integration runs in collector Linux/Windows CI')
def test_native_java_https_client_credentials_identity_and_transfer_worker(receiver, tmp_path):
    server, config = receiver
    _, _, raw, witness = native_data()
    witness['capture_context']['metadata']['Version'] = '0.5.0'
    raw_path, nts_path = tmp_path/'raw.txt', tmp_path/'nts.json'
    raw_path.write_bytes(raw)
    nts_path.write_text(json.dumps(witness))
    wrong = prepare_connection(tmp_path/'wrong-cert', '127.0.0.1', 8443)
    cases = {'good': config, 'credential': config | dict(token='0'*64),
             'pin': config | dict(certificate_der=wrong['certificate_der'])}
    # A server with an explicitly trusted certificate for another IP must still
    # fail the platform hostname check, even though its leaf pin is correct.
    identity = prepare_connection(tmp_path/'wrong-identity', '127.0.0.2', 8443)
    other = AndroidReceiver(('127.0.0.1', 0), tmp_path/'wrong-identity', identity, local_counter_resolution_ns=1)
    other_thread = threading.Thread(target=other.serve_forever, kwargs=dict(poll_interval=.02), daemon=True)
    other_thread.start()
    cases['identity'] = identity | dict(url=f'https://127.0.0.1:{other.server_port}')
    fixture = tmp_path/'fixture.json'
    fixture.write_text(json.dumps(dict(configs=cases, raw=str(raw_path), nts=str(nts_path),
        directory=str(tmp_path), capture_id='synthetic-monitor')))
    project = Path(__file__).resolve().parents[1]/'android-collector'
    command = str(project/'gradlew.bat') if os.name == 'nt' else './gradlew'
    try:
        result = subprocess.run([command, '--no-daemon', ':app:testDebugUnitTest', '--tests',
            'org.satelliterf.observatory.clock.PcConnectionTest'], cwd=project, capture_output=True,
            text=True, timeout=180, env=os.environ | dict(PNT_PC_CONNECTION_FIXTURE=str(fixture)))
        assert result.returncode == 0, result.stdout+result.stderr
        assert server.monitor.last_update['snapshot']['session_complete']
        assert (server.monitor.output/'update-00001'/'pnt-clock-synthetic-monitor.txt').read_bytes() == raw
        events = [json.loads(line) for line in (tmp_path/'pnt-transfer-synthetic-monitor.jsonl').read_text().splitlines()]
        assert any(event['outcome'] == 'ACKNOWLEDGED' for event in events)
        assert raw_path.read_bytes() == raw and json.loads(nts_path.read_bytes()) == witness
    finally:
        other.shutdown()
        other.server_close()
        other_thread.join(timeout=10)
