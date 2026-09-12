"""Single-host queue bridge to the unchanged, staged positioning worker.

Only a trusted local operator runs this module. A hard supervisor crash may
leave a child alive: the expired queue claim blocks replacement dispatch until
inspection. Detected lease loss terminates the child process tree.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

from positioning.plans import validate_plan
from .requests import Conflict
from .workflow import _json, prepare_request, read_result


ROOT = Path(__file__).resolve().parents[1]
QUALIFICATION_DAYS = {
    '2026-08-28', '2026-08-29', '2026-08-30', '2026-08-31',
    '2026-09-08', '2026-09-09', '2026-09-10', '2026-09-11',
}


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _write(path, value):
    with path.open('xb') as handle:
        handle.write(_bytes(value))


def submit_request(store, owner, key, request, implementation):
    assessment = prepare_request(request)
    if assessment['status'] != 'PLAN_PREPARED':
        return assessment
    if assessment['plan']['date_gpst'] in QUALIFICATION_DAYS:
        return assessment | {
            'status': 'PREVIOUSLY_ACCESSED_EVENT', 'reason_code': 'CONSUMED_QUALIFICATION_DAY',
            'message': 'Giornata già usata per qualificazione: non può diventare un nuovo tentativo primario.',
            'plan': None,
        }
    return store.submit(owner, key, assessment['plan'], implementation=implementation,
                        purpose='prospective_attempt')


def _runtime_root(store, runs_root):
    root = Path(runs_root).resolve()
    if root.is_relative_to(ROOT) or store.path.resolve().is_relative_to(ROOT):
        raise ValueError('queue and runtime artifacts must be outside the source checkout')
    root.mkdir(parents=True, exist_ok=True)
    return root


def _request_directory(root, request_id):
    if str(uuid.UUID(request_id)) != request_id:
        raise ValueError('canonical request UUID required')
    path = root / request_id
    if path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('unsafe request directory')
    return path


def _check_checkout(implementation):
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, timeout=10).strip()
    dirty = subprocess.check_output(
        ['git', 'status', '--porcelain', '--untracked-files=all'], cwd=ROOT, text=True, timeout=10).strip()
    if actual != implementation or dirty:
        raise ValueError('worker requires the declared commit in a clean dedicated checkout')


def _validate_declaration(claim):
    declaration = claim['declaration']
    if _digest(_bytes(declaration)) != claim['declaration_hash']:
        raise ValueError('queue declaration hash mismatch')
    if declaration['purpose'] != 'prospective_attempt':
        raise ValueError('this executor does not dispatch availability or historical replay jobs')
    plan = validate_plan(declaration['plan'])
    if plan['date_gpst'] in QUALIFICATION_DAYS:
        raise ValueError('previously consumed qualification day cannot become a primary attempt')
    assessment = prepare_request({key: plan[key] for key in ('target', 'date_gpst', 'prior_access', 'profile')})
    if assessment['status'] != 'PLAN_PREPARED' or assessment['plan'] != plan:
        raise ValueError('request is closed or outside the general workflow profile')


def _start(plan_path, run_path, log):
    options = ({'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
               if os.name == 'nt' else {'start_new_session': True})
    return subprocess.Popen([sys.executable, '-m', 'positioning', 'run', str(plan_path), str(run_path)],
                            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                            stderr=subprocess.STDOUT, **options)


def _stop(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        result = subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                capture_output=True, timeout=15, check=False)
        if result.returncode and process.poll() is None:
            raise RuntimeError('child tree termination failed; operator inspection required')
    else:
        os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=15)


def _validated_result(directory, claim):
    """Bind worker evidence to this queue declaration, not only target/date."""
    declaration = _json((directory / 'declaration.json').read_bytes())
    if declaration != claim['declaration'] or _digest(_bytes(declaration)) != claim['declaration_hash']:
        raise ValueError('stored declaration differs from queue')
    execution = _json((directory / 'execution.json').read_bytes())
    if execution != {'request_id': claim['id'], 'declaration_hash': claim['declaration_hash'],
                     'implementation': declaration['implementation']}:
        raise ValueError('execution identity differs from queue')
    ended = _json((directory / 'exit.json').read_bytes())
    if ended['declaration_hash'] != claim['declaration_hash'] or ended['returncode'] not in (0, 1):
        raise ValueError('no recognized exited worker receipt')
    result = read_result(directory / 'run')
    expected_plan = _bytes(declaration['plan'])
    # jobs.execute seals request.json in the terminal artifact set.
    if result['evidence']['request_sha256'] != _digest(expected_plan):
        raise ValueError('sealed job belongs to another plan')
    if result['target'] != declaration['plan']['target'] or result['date_gpst'] != declaration['plan']['date_gpst']:
        raise ValueError('result belongs to another event')
    state = result['operational_state']
    if ended['returncode'] != (1 if state == 'FAILED' else 0):
        raise ValueError('process exit differs from sealed job state')
    return {'schema': 'satellite-rf-queued-result-v1', 'request_id': claim['id'],
            'declaration_hash': claim['declaration_hash'],
            'implementation': declaration['implementation'], 'result': result}


def run_once(store, runs_root, *, lease_seconds=60, heartbeat_seconds=10, max_runtime_seconds=5500):
    """Claim at most one request; renew while its isolated worker is alive."""
    if not 0 < heartbeat_seconds < lease_seconds / 2:
        raise ValueError('heartbeat must be positive and less than half the lease')
    if not 0 < max_runtime_seconds <= 7200:
        raise ValueError('runtime must be positive and bounded by two hours')
    root = _runtime_root(store, runs_root)
    claim = store.claim(lease_seconds=lease_seconds)
    if claim is None:
        return {'state': 'NO_DISPATCH', 'reason': 'Queue empty or another request running/under review.'}
    process, directory = None, None
    try:
        directory = _request_directory(root, claim['id'])
        # Existing artifacts mean a prior attempt, never permission to resume it.
        directory.mkdir(exist_ok=False)
        _validate_declaration(claim)
        _check_checkout(claim['declaration']['implementation'])
        _write(directory / 'declaration.json', claim['declaration'])
        _write(directory / 'plan.json', claim['declaration']['plan'])
        _write(directory / 'execution.json', {
            'request_id': claim['id'], 'declaration_hash': claim['declaration_hash'],
            'implementation': claim['declaration']['implementation'],
        })
        store.heartbeat(claim['id'], claim['lease_token'], lease_seconds=lease_seconds)
        store.reserve_event(claim['id'], claim['lease_token'])
        with (directory / 'runner.log').open('xb') as log:
            process = _start(directory / 'plan.json', directory / 'run', log)
            deadline = time.monotonic() + max_runtime_seconds
            while True:
                try:
                    code = process.wait(timeout=heartbeat_seconds)
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('worker exceeded the declared runtime limit')
                    _check_checkout(claim['declaration']['implementation'])
                    store.heartbeat(claim['id'], claim['lease_token'], lease_seconds=lease_seconds)
        _check_checkout(claim['declaration']['implementation'])
        store.heartbeat(claim['id'], claim['lease_token'], lease_seconds=lease_seconds)
        _write(directory / 'exit.json', {'returncode': code, 'declaration_hash': claim['declaration_hash']})
        document = _validated_result(directory, claim)
        _write(directory / 'result.json', document)
        store.finish(claim['id'], claim['lease_token'], state=document['result']['operational_state'],
                     result_hash=_digest(_bytes(document)))
        return {'id': claim['id'], 'state': document['result']['operational_state'],
                'result': document['result']}
    except BaseException as error:
        try:
            if process is not None:
                _stop(process)
        finally:
            store.quarantine(claim['id'], claim['lease_token'])
        reason = type(error).__name__ + ': ' + str(error)
        if directory is not None and directory.is_dir() and not directory.is_symlink():
            try:
                _write(directory / 'review.json', {'reason': reason})
            except OSError:
                pass  # Quarantine in SQLite remains authoritative even if disk is full.
        if not isinstance(error, Exception):
            raise
        return {'id': claim['id'], 'state': 'NEEDS_REVIEW',
                'reason': reason}


def request_status(store, owner, request_id, runs_root):
    row = store.get(owner, request_id)
    directory = _request_directory(_runtime_root(store, runs_root), request_id)
    if row['state'] in ('COMPLETED', 'FAILED'):
        content = (directory / 'result.json').read_bytes()
        if _digest(content) != row['result_hash']:
            raise ValueError('queued result changed')
        document = _validated_result(directory, row)
        if _json(content) != document:
            raise ValueError('queued result differs from scientific evidence')
        row['result'] = document['result']
    elif row['state'] == 'RUNNING':
        try:
            row['stage'] = _json((directory / 'run' / 'job.json').read_bytes()).get('stage')
        except (FileNotFoundError, ValueError):
            row['stage'] = None  # An advisory progress file may be mid-write.
    elif row['state'] == 'NEEDS_REVIEW':
        try:
            row['review'] = _json((directory / 'review.json').read_bytes())
        except (FileNotFoundError, ValueError):
            row['review'] = {'reason': 'Claim expired or supervisor interrupted; inspect artifacts and processes.'}
    return row


def reconcile(store, owner, request_id, runs_root):
    """Recover only an exited, sealed attempt. Never spawn or requeue anything."""
    row = store.get(owner, request_id)
    if row['state'] != 'NEEDS_REVIEW':
        raise Conflict('only a quarantined request can be reconciled')
    directory = _request_directory(_runtime_root(store, runs_root), request_id)
    document = _validated_result(directory, row)
    path = directory / 'result.json'
    if path.exists():
        if path.read_bytes() != _bytes(document):
            raise ValueError('existing publication differs; inspect without rewriting')
    else:
        _write(path, document)
    store.reconcile_result(request_id, row['declaration_hash'],
                           state=document['result']['operational_state'], result_hash=_digest(_bytes(document)))
    return request_status(store, owner, request_id, runs_root)
