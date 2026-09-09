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
    job = json.loads((run / 'job.json').read_text()) if (run / 'job.json').exists() else None
    if job and job['state'] == 'FAILED':
        return job
    if (run / 'outcome.json').exists():
        return {'state': 'COMPLETED', 'outcome': json.loads((run / 'outcome.json').read_text())}
    if job:
        return job
    if (run / 'availability.json').exists():
        report = json.loads((run / 'availability.json').read_text())
        return {'state': 'AVAILABLE_FOR_CALIBRATION' if report['ready_for_calibration'] else 'UNAVAILABLE',
                'availability': report}
    return {'state': 'NOT_STARTED'}


def dossier(run_path):
    run = Path(run_path)
    current = status(run)
    if current['state'] not in ('COMPLETED', 'FAILED'):
        raise ValueError('dossier requires a completed or failed job')
    destination = run / 'dossier.json'
    if destination.exists():
        if not (run / 'terminal_receipt.json').exists():
            raise ValueError('existing dossier has no terminal seal; inspect interrupted publication')
        # Read the sealed schema as published, even after exporter upgrades.
        # status() above verifies its bytes and every included frozen artifact.
        return json.loads(destination.read_text())
    plan = json.loads((run / 'request.json').read_text())
    outcome = current.get('outcome', {})
    availability = json.loads((run / 'availability.json').read_text()) if (run / 'availability.json').exists() else None
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
    files += sorted((run / 'raw_observations').glob('*.json'))
    files += sorted((run / 'logs').glob('*.log'))
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
        'fit_stations': (availability['selected_fit_stations'] if availability else plan['fit_stations']),
        'withheld_station': plan['withheld_station'], 'availability': availability,
        'claim': plan['claim'], 'prior_access': plan['prior_access'],
        'raw_data_note': 'Raw observations and oracle remain in the run directory; source URLs and hashes are in included receipts. This dossier embeds admission, code and result evidence.',
        'artifacts': artifacts,
    }
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
        # A standalone availability check may be promoted without changing the
        # frozen declaration or source implementation; no estimator has run yet.
        if not (run / 'availability.json').exists() or not (run / 'plan_freeze.json').exists():
            raise ValueError('new job requires an empty directory or a frozen availability check')
        freeze = json.loads((run / 'plan_freeze.json').read_text())
        report = json.loads((run / 'availability.json').read_text())
        if ((run / 'plan.json').read_bytes() != plan_bytes or freeze['sources'] != source_hashes()
                or freeze['plan_sha256'] != digest(plan_path) or report['plan_sha256'] != digest(plan_path)
                or report['structure_sha256'] != digest(run / 'structure.json')
                or (run / 'admission_receipt.json').exists() or (run / 'solution_freeze.json').exists()):
            raise ValueError('prepared availability changed or estimation already started')
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
