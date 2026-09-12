"""Queue/legacy-worker integration with invented stage outputs, no RF access."""
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from positioning.acquisition import digest, write_json
from positioning.jobs import execute
from service import worker
from service.requests import Conflict, RequestStore


COMMIT = 'a' * 40


def request(target='G15', day='2026-09-01'):
    return {'target': target, 'date_gpst': day, 'profile': 'gps-code-network-v1',
            'prior_access': 'Invented offline queue integration fixture; not a real campaign.'}


@pytest.fixture
def queue(tmp_path):
    return RequestStore(tmp_path / 'queue.sqlite'), tmp_path / 'runs'


class Finished:
    def __init__(self, code):
        self.code = code

    def wait(self, timeout):
        return self.code

    def poll(self):
        return self.code


def install_stages(monkeypatch, *, kind='unavailable'):
    """Use jobs.execute itself; replace only scientific child processes."""
    calls = []
    monkeypatch.setattr(worker, '_check_checkout', lambda commit: None)

    def stage(command, **kwargs):
        name, run = command[3], Path(command[-1])
        calls.append(name)
        if kind == 'software_error':
            return SimpleNamespace(returncode=1)
        if kind == 'unavailable':
            write_json(run / 'outcome.json', {'status': 'SOURCE_UNAVAILABLE',
                       'primary_pass': False, 'reason': 'SIMULATED_SOURCE_UNAVAILABLE', 'stage': name})
        elif name == 'estimate':
            write_json(run / 'solution.json', {
                'xyz_m': [1., 2., 3.], 'frame': 'INVENTED_TEST_FRAME',
                'emission_seconds_since_gpst_midnight': 1.,
                'uncertainty': {'total_95_outer_radius_m': 50.},
            })
            write_json(run / 'solution_freeze.json', {'solution_sha256': digest(run / 'solution.json')})
        elif name == 'verify':
            assert (run / 'solution_freeze.json').is_file()
            write_json(run / 'outcome.json', {
                'status': 'INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED', 'primary_pass': True,
                'comparison': {'error_3d_m': 10., 'estimated_ecef_at_emission_m': [1., 2., 3.]},
                'prospective_uncertainty_radius_m': 50.,
                'heldout': {'status': 'HELD_OUT_RECEIVER_CONFIRMED'},
            })
        return SimpleNamespace(returncode=0)

    def start(plan, run, log):
        result = execute(plan, run)
        return Finished(1 if result['state'] == 'FAILED' else 0)

    monkeypatch.setattr('positioning.jobs.subprocess.run', stage)
    monkeypatch.setattr(worker, '_start', start)
    return calls


@pytest.mark.parametrize('kind,expected,stages', [
    ('unavailable', 'NOT_VERIFIABLE', ['acquire']),
    ('software_error', 'EXECUTION_FAILED', ['acquire']),
    ('synthetic_pass', 'VERIFIED_CONDITIONALLY', ['acquire', 'estimate', 'verify']),
])
def test_submit_dispatch_and_owner_result_use_existing_stages(queue, monkeypatch, kind, expected, stages):
    store, runs = queue
    calls = install_stages(monkeypatch, kind=kind)
    row = worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    assert worker.submit_request(store, 'alice', 'one', request(), COMMIT) == row
    dispatched = worker.run_once(store, runs)
    assert dispatched['result']['status'] == expected
    assert calls == stages
    current = worker.request_status(store, 'alice', row['id'], runs)
    assert current['result']['status'] == expected
    assert current['result']['verified'] is (kind == 'synthetic_pass')
    assert [event['state'] for event in current['events']] == ['QUEUED', 'RUNNING', current['state']]
    assert 'lease_token' not in json.dumps(current)
    with pytest.raises(KeyError):
        worker.request_status(store, 'bob', row['id'], runs)
    assert worker.run_once(store, runs)['state'] == 'NO_DISPATCH'
    assert calls == stages
    path = runs / row['id'] / 'result.json'
    path.write_text('{}')
    with pytest.raises(ValueError, match='queued result changed'):
        worker.request_status(store, 'alice', row['id'], runs)


def test_second_key_or_owner_cannot_repeat_an_attempted_target_day(queue, monkeypatch):
    store, runs = queue
    calls = install_stages(monkeypatch)
    worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    second = worker.submit_request(store, 'bob', 'different-key', request(), COMMIT)
    worker.run_once(store, runs)
    with pytest.raises(Conflict, match='already reserved'):
        worker.submit_request(store, 'bob', 'third-key', request(), COMMIT)
    assert worker.run_once(store, runs)['state'] == 'NEEDS_REVIEW'
    assert calls == ['acquire']
    assert 'already reserved' in worker.request_status(store, 'bob', second['id'], runs)['review']['reason']


def test_crashed_claim_blocks_replacement_after_expiry(tmp_path, monkeypatch):
    now = [100.]
    store = RequestStore(tmp_path / 'queue.sqlite', clock=lambda: now[0])
    row = worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    worker.submit_request(store, 'bob', 'two', request('G16'), COMMIT)
    store.claim(lease_seconds=10)  # Supervisor disappears here, no retry.
    now[0] += 11
    # Even without another dispatcher, an owner read reports the expired claim.
    assert store.get('alice', row['id'])['state'] == 'NEEDS_REVIEW'
    monkeypatch.setattr(worker, '_start', lambda *args: pytest.fail('must not start replacement'))
    assert worker.run_once(store, tmp_path / 'runs')['state'] == 'NO_DISPATCH'
    assert store.get('alice', row['id'])['state'] == 'NEEDS_REVIEW'
    with pytest.raises(FileNotFoundError):
        worker.reconcile(store, 'alice', row['id'], tmp_path / 'runs')


def test_lost_lease_stops_child_and_does_not_publish(tmp_path, monkeypatch):
    now = [100.]
    store = RequestStore(tmp_path / 'queue.sqlite', clock=lambda: now[0])
    row = worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    monkeypatch.setattr(worker, '_check_checkout', lambda commit: None)
    stopped = []

    class Running:
        def wait(self, timeout):
            now[0] += 11
            raise subprocess.TimeoutExpired('invented worker', timeout)

    process = Running()
    monkeypatch.setattr(worker, '_start', lambda *args: process)
    monkeypatch.setattr(worker, '_stop', lambda child: stopped.append(child))
    result = worker.run_once(store, tmp_path / 'runs', lease_seconds=10, heartbeat_seconds=2)
    assert result['state'] == 'NEEDS_REVIEW'
    assert stopped == [process]
    assert not (tmp_path / 'runs' / row['id'] / 'result.json').exists()


def test_heartbeat_renews_until_worker_finishes(queue, monkeypatch):
    store, runs = queue
    install_stages(monkeypatch)
    real_start = worker._start

    def start(*args):
        finished = real_start(*args)
        original_wait = finished.wait
        attempts = [0]

        def wait(timeout):
            attempts[0] += 1
            if attempts[0] <= 2:
                raise subprocess.TimeoutExpired('invented waiting worker', timeout)
            return original_wait(timeout)

        finished.wait = wait
        return finished

    heartbeats = []
    original = store.heartbeat
    monkeypatch.setattr(store, 'heartbeat', lambda *a, **k: (heartbeats.append(True), original(*a, **k)))
    monkeypatch.setattr(worker, '_start', start)
    worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    assert worker.run_once(store, runs)['state'] == 'COMPLETED'
    assert len(heartbeats) == 4  # Before launch, two renewals, before publication.


def test_recover_sealed_result_after_publication_crash_without_rerun(queue, monkeypatch):
    store, runs = queue
    calls = install_stages(monkeypatch)
    row = worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    monkeypatch.setattr(store, 'finish', lambda *a, **k: (_ for _ in ()).throw(OSError('simulated database failure')))
    assert worker.run_once(store, runs)['state'] == 'NEEDS_REVIEW'
    assert worker.reconcile(store, 'alice', row['id'], runs)['state'] == 'COMPLETED'
    assert calls == ['acquire']
    with pytest.raises(Conflict):
        worker.reconcile(store, 'alice', row['id'], runs)


def test_changed_plan_cannot_be_reconciled(queue, monkeypatch):
    store, runs = queue
    install_stages(monkeypatch)
    row = worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    monkeypatch.setattr(store, 'finish', lambda *a, **k: (_ for _ in ()).throw(OSError('publication crash')))
    worker.run_once(store, runs)
    path = runs / row['id'] / 'declaration.json'
    declaration = json.loads(path.read_bytes())
    declaration['plan']['prior_access'] = 'changed after execution'
    path.write_text(json.dumps(declaration))
    with pytest.raises(ValueError, match='stored declaration differs'):
        worker.reconcile(store, 'alice', row['id'], runs)
    assert store.get('alice', row['id'])['state'] == 'NEEDS_REVIEW'


def test_wrong_version_stops_before_launch(queue, monkeypatch):
    store, runs = queue
    worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    monkeypatch.setattr(worker, '_check_checkout', lambda commit: (_ for _ in ()).throw(ValueError('wrong version')))
    monkeypatch.setattr(worker, '_start', lambda *args: pytest.fail('version must be checked first'))
    assert worker.run_once(store, runs)['state'] == 'NEEDS_REVIEW'


def test_consumed_qualification_day_never_enters_queue(queue):
    store, runs = queue
    result = worker.submit_request(store, 'alice', 'one', request(day='2026-08-28'), COMMIT)
    assert result['status'] == 'PREVIOUSLY_ACCESSED_EVENT'
    assert store.claim() is None


def test_direct_legacy_replay_entry_is_not_dispatched(queue, monkeypatch):
    store, runs = queue
    plan = worker.prepare_request(request())['plan']
    store.submit('alice', 'one', plan, implementation=COMMIT, purpose='historical_replay')
    monkeypatch.setattr(worker, '_start', lambda *args: pytest.fail('replay must not become primary'))
    result = worker.run_once(store, runs)
    assert result['state'] == 'NEEDS_REVIEW'
    assert 'does not dispatch' in result['reason']


def test_running_checkout_change_terminates_child(queue, monkeypatch):
    store, runs = queue
    worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    checks, stopped = [], []

    def check(commit):
        checks.append(commit)
        if len(checks) > 1:
            raise ValueError('checkout changed during execution')

    process = SimpleNamespace(wait=lambda timeout: (_ for _ in ()).throw(
        subprocess.TimeoutExpired('invented child', timeout)))
    monkeypatch.setattr(worker, '_check_checkout', check)
    monkeypatch.setattr(worker, '_start', lambda *args: process)
    monkeypatch.setattr(worker, '_stop', lambda child: stopped.append(child))
    assert worker.run_once(store, runs)['state'] == 'NEEDS_REVIEW'
    assert stopped == [process]


def test_runtime_limit_stops_a_stuck_child(queue, monkeypatch):
    store, runs = queue
    worker.submit_request(store, 'alice', 'one', request(), COMMIT)
    monkeypatch.setattr(worker, '_check_checkout', lambda commit: None)
    times = iter([0., 3.])
    monkeypatch.setattr(worker.time, 'monotonic', lambda: next(times))
    stopped = []
    process = SimpleNamespace(wait=lambda timeout: (_ for _ in ()).throw(
        subprocess.TimeoutExpired('invented child', timeout)))
    monkeypatch.setattr(worker, '_start', lambda *args: process)
    monkeypatch.setattr(worker, '_stop', lambda child: stopped.append(child))
    result = worker.run_once(store, runs, max_runtime_seconds=2)
    assert result['state'] == 'NEEDS_REVIEW' and 'runtime limit' in result['reason']
    assert stopped == [process]


def test_real_checkout_check_rejects_dirty_tree_and_wrong_commit(tmp_path, monkeypatch):
    repo = tmp_path / 'checkout'
    repo.mkdir()
    subprocess.run(['git', 'init', str(repo)], check=True, capture_output=True)
    (repo / 'source.py').write_text('value = 1\n')
    subprocess.run(['git', 'add', '.'], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=Offline test', '-c', 'user.email=test@example.invalid',
                    'commit', '-m', 'Synthetic source fixture'], cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    monkeypatch.setattr(worker, 'ROOT', repo)
    worker._check_checkout(commit)
    with pytest.raises(ValueError, match='declared commit'):
        worker._check_checkout(COMMIT)
    (repo / 'source.py').write_text('value = 2\n')
    with pytest.raises(ValueError, match='clean dedicated checkout'):
        worker._check_checkout(commit)


def test_native_running_process_can_be_stopped():
    options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
               if os.name == 'nt' else {'start_new_session': True})
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], **options)
    try:
        worker._stop(process)
        assert process.poll() is not None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_real_cli_queue_to_isolated_worker_to_result_with_offline_source(tmp_path):
    """Actual child processes; only acquisition in a disposable copy is replaced."""
    repo = tmp_path / 'checkout'
    repo.mkdir()
    for package in ('positioning', 'service'):
        (repo / package).mkdir()
        for source in (worker.ROOT / package).glob('*.py'):
            (repo / package / source.name).write_bytes(source.read_bytes())
    acquisition = repo / 'positioning' / 'acquisition.py'
    with acquisition.open('a', encoding='utf-8') as handle:
        handle.write('\n\n# Disposable test source: no network operation is possible here.\n'
                     'def acquire(plan_path, run_path, *, availability_only=False):\n'
                     '    from .errors import ScientificRejection\n'
                     '    raise ScientificRejection("SIMULATED_OFFLINE_SOURCE", status="SOURCE_UNAVAILABLE")\n')
    (repo / '.gitignore').write_text('__pycache__/\n')
    subprocess.run(['git', 'init'], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', 'add', '.'], cwd=repo, check=True, capture_output=True)
    subprocess.run(['git', '-c', 'user.name=Offline test', '-c', 'user.email=test@example.invalid',
                    'commit', '-m', 'Disposable offline worker fixture'], cwd=repo, check=True, capture_output=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    queue, runs = tmp_path / 'queue.sqlite', tmp_path / 'runs'

    def cli(*args):
        process = subprocess.run([sys.executable, '-m', 'service', *map(str, args)], cwd=repo,
                                 capture_output=True, timeout=45)
        assert process.returncode == 0, process.stderr.decode('utf-8', errors='replace')
        return json.loads(process.stdout.decode('utf-8'))

    submitted = cli('submit', 'G15', '2026-09-01', '--prior-access', 'Disposable offline fixture',
                    '--implementation', commit, '--key', 'one', '--owner', 'alice', '--queue', queue)
    assert submitted['state'] == 'QUEUED'
    completed = cli('work-once', '--queue', queue, '--runs', runs)
    assert completed['state'] == 'COMPLETED'
    result = cli('request-status', submitted['id'], '--owner', 'alice', '--queue', queue, '--runs', runs)
    assert result['result']['reason'] == 'SIMULATED_OFFLINE_SOURCE'
    assert result['result']['verified'] is False
    assert not (runs / submitted['id'] / 'run' / 'oracle_request.json').exists()
    assert cli('work-once', '--queue', queue, '--runs', runs)['state'] == 'NO_DISPATCH'
