"""One bounded local job, isolated stages, immutable terminal and portable dossier."""
import json
from pathlib import Path
import subprocess
import sys

from .acquisition import digest, snapshot_sources, source_hashes, utc_now, write_json
from .plans import validate_plan

ROOT = Path(__file__).resolve().parents[1]


def status(run_path):
    run = Path(run_path)
    if (run / 'terminal_receipt.json').exists():
        receipt = json.loads((run / 'terminal_receipt.json').read_text())
        for name, expected in receipt['artifacts'].items():
            path = run / name
            if path.resolve().is_relative_to(run.resolve()) is False or digest(path) != expected:
                raise ValueError('terminal artifact changed: ' + name)
    if (run / 'outcome.json').exists():
        return {'state': 'COMPLETED', 'outcome': json.loads((run / 'outcome.json').read_text())}
    if (run / 'job.json').exists():
        return json.loads((run / 'job.json').read_text())
    return {'state': 'NOT_STARTED'}


def dossier(run_path):
    run = Path(run_path)
    current = status(run)
    if current['state'] not in ('COMPLETED', 'FAILED'):
        raise ValueError('dossier requires a completed or failed job')
    plan = json.loads((run / 'request.json').read_text())
    outcome = current.get('outcome', {})
    comparison = outcome.get('comparison', {})
    solution = {}
    if (run / 'solution_freeze.json').exists():
        freeze = json.loads((run / 'solution_freeze.json').read_text())
        if digest(run / 'solution.json') != freeze['solution_sha256']:
            raise ValueError('frozen solution changed before dossier export')
        solution = json.loads((run / 'solution.json').read_text())
    files = sorted(p for p in run.glob('*.json')
                   if p.name not in ('dossier.json', 'terminal_receipt.json'))
    files += sorted((run / 'sources').rglob('*.py'))
    files += sorted((run / 'estimation').glob('*'))
    artifacts = {}
    for path in files:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(run.resolve()):
            raise ValueError('unsafe dossier input')
        raw = path.read_bytes()
        artifacts[path.relative_to(run).as_posix()] = {
            'sha256': digest(path), 'bytes': len(raw), 'content_utf8': raw.decode('utf-8'),
        }
    document = {
        'schema': 'satellite-rf-position-dossier-v1',
        'target': plan['target'], 'date_gpst': plan['date_gpst'],
        'job_state': current['state'], 'status': outcome.get('status', 'ENGINEERING_FAILURE'),
        'primary_pass': outcome.get('primary_pass', False),
        'inferred_position': ({'xyz_m': solution['xyz_m'], 'frame': solution['frame'],
                               'emission_seconds_since_gpst_midnight': solution['emission_seconds_since_gpst_midnight']}
                              if solution else None),
        'estimated_ecef_at_emission_m': comparison.get('estimated_ecef_at_emission_m'),
        'observed_error_m': comparison.get('error_3d_m'),
        'prospective_uncertainty_radius_m': outcome.get('prospective_uncertainty_radius_m',
                                  solution.get('uncertainty', {}).get('total_95_outer_radius_m')),
        'heldout': outcome.get('heldout'),
        'fit_stations': plan['fit_stations'], 'withheld_station': plan['withheld_station'],
        'claim': plan['claim'], 'prior_access': plan['prior_access'],
        'raw_data_note': 'Raw observations and oracle remain in the run directory; source URLs and hashes are in included receipts. This dossier embeds admission, code and result evidence.',
        'artifacts': artifacts,
    }
    # Exclusive first publication; later reads cannot silently regenerate changed evidence.
    destination = run / 'dossier.json'
    if destination.exists():
        existing = json.loads(destination.read_text())
        if existing != document:
            raise ValueError('dossier differs from terminal evidence')
    else:
        write_json(destination, document, exclusive=True)
    return document


def execute(plan_path, run_path):
    plan_path, run = Path(plan_path).resolve(), Path(run_path).resolve()
    plan_bytes = plan_path.read_bytes()
    validate_plan(json.loads(plan_bytes))
    if (run / 'request.json').exists():
        if (run / 'request.json').read_bytes() != plan_bytes:
            raise ValueError('request differs from the existing job')
        current = status(run)
        if current['state'] == 'COMPLETED' and (run / 'terminal_receipt.json').exists():
            dossier(run)
            return current
        raise ValueError('job already attempted; inspect its failure without automatic retry')
    if run.exists() and any(run.iterdir()):
        raise ValueError('new job requires an empty directory')
    run.mkdir(parents=True, exist_ok=True)
    with (run / 'request.json').open('xb') as handle:
        handle.write(plan_bytes)
    request_hash = digest(run / 'request.json')
    sources = snapshot_sources(run, 'job')
    record = {'state': 'RUNNING', 'stage': 'acquire', 'started_utc': utc_now(),
              'request_sha256': request_hash, 'sources': sources}
    write_json(run / 'job.json', record)
    (run / 'logs').mkdir()
    for stage in ('acquire', 'estimate', 'verify'):
        if source_hashes() != sources or digest(run / 'request.json') != request_hash:
            record.update(state='FAILED', reason='JOB_INPUT_OR_IMPLEMENTATION_CHANGED')
            break
        record.update(stage=stage, updated_utc=utc_now())
        write_json(run / 'job.json', record)
        command = [sys.executable, '-m', 'positioning', stage]
        if stage == 'acquire':
            command.append(str(run / 'request.json'))
        command.append(str(run))
        print(json.dumps({'stage': stage, 'state': 'RUNNING'}), flush=True)
        try:
            with (run / 'logs' / f'{stage}.log').open('xb') as log:
                result = subprocess.run(command, cwd=ROOT, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=1800, check=False)
            if result.returncode != 0:
                record.update(state='FAILED', reason='STAGE_PROCESS_FAILED', returncode=result.returncode)
                break
        except (OSError, subprocess.TimeoutExpired) as error:
            record.update(state='FAILED', reason=type(error).__name__)
            break
        if (run / 'outcome.json').exists():
            record.update(state='COMPLETED')
            break
    else:
        record.update(state='FAILED', reason='NO_TERMINAL_OUTCOME')
    record['finished_utc'] = utc_now()
    write_json(run / 'job.json', record)
    document = dossier(run)
    hashes = {name: value['sha256'] for name, value in document['artifacts'].items()}
    hashes['dossier.json'] = digest(run / 'dossier.json')
    write_json(run / 'terminal_receipt.json', {'artifacts': hashes, 'sealed_utc': utc_now()}, exclusive=True)
    return status(run)
