"""Optional development diagnostics; never modify a sealed scientific verdict."""
from collections import Counter
import hashlib
import math
from pathlib import Path
import statistics
import subprocess
import sys

from .workflow import _json, read_result


STATUSES = {'ESTIMATED', 'CALIBRATION_REJECTED', 'INTERPOLATION_REJECTED',
            'FIT_REJECTED', 'ENGINEERING_FAILURE'}


def number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError('finite diagnostic number required')
    return value


def summarize(report_path, inputs_path):
    """Summarize a supplied report, matching exact admitted input bytes.

    Local input/report hashes provide integrity, not author authentication.
    Failures remain in the denominator; baseline is excluded from statistics.
    """
    raw = Path(report_path).read_bytes()
    report = _json(raw)
    root = Path(inputs_path)
    receipt = _json((root/'admission_receipt.json').read_bytes())
    buffers = {name: (root/'estimation'/name).read_bytes()
               for name in ('admitted.json', 'reference_only.rnx')}
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in buffers.items()}
    if (report['input_sha256'] != hashes or hashes['admitted.json'] != receipt['admitted_sha256']
            or hashes['reference_only.rnx'] != receipt['navigation_sha256']):
        raise ValueError('diagnostic belongs to different or changed inputs')
    admitted = _json(buffers['admitted.json'])
    context = admitted['context']
    times = [context['start_s']+i*context['step_s'] for i in range(context['samples'])]
    if (report['schema'] != 'exploratory-reference-sensitivity-v1'
            or report['target'] != context['target'] or report['date_gpst'] != context['date_gpst']
            or report['fit_stations'] != admitted['fit_stations'] or report['times_gpst_s'] != times
            or report['target_orbit_accessed'] is not False or report['new_confirmation'] is not False):
        raise ValueError('diagnostic context or scope differs')
    cases = report['cases']
    if not cases or type(report['case_count']) is not int or report['case_count'] != len(cases):
        raise ValueError('invalid diagnostic case count')
    baseline, variants = cases[0], cases[1:]
    references = {sv for cal in baseline['calibration'].values()
                  for epoch in cal['epochs'] for sv in epoch['references']}
    excluded = [row['excluded_reference'] for row in variants]
    counts = Counter(row['status'] for row in cases)
    if (baseline['excluded_reference'] is not None or None in excluded
            or len(set(excluded)) != len(excluded) or set(excluded) != references
            or set(counts)-STATUSES or dict(counts) != report['status_counts']
            or baseline['status'] != report['baseline_status']):
        raise ValueError('incomplete or contradictory diagnostic cases')
    measured = []
    rows = []
    for row in variants:
        displacement = None
        if baseline['status'] == row['status'] == 'ESTIMATED':
            if len(row['xyz_m']) != 3 or len(baseline['xyz_m']) != 3:
                raise ValueError('three position coordinates required')
            if number(row['u0_relative_s']) != number(baseline['u0_relative_s']):
                raise ValueError('comparison frame changed')
            displacement = math.dist([number(v) for v in row['xyz_m']],
                                     [number(v) for v in baseline['xyz_m']])
            if not math.isclose(displacement, number(row['displacement_from_baseline_m']),
                                rel_tol=1e-8, abs_tol=1e-6):
                raise ValueError('reported displacement differs from coordinates')
            measured.append(displacement)
        elif row['displacement_from_baseline_m'] is not None:
            raise ValueError('unavailable comparison must not have a displacement')
        rows.append({'excluded_reference': row['excluded_reference'], 'status': row['status'],
                     'displacement_m': displacement, 'reason': row.get('reason'),
                     'calibration_failures': {name: cal['failures'] for name, cal in row.get('calibration', {}).items()
                                              if cal['failures']}})
    status = ('BASELINE_UNAVAILABLE' if baseline['status'] != 'ESTIMATED' else
              'AVAILABLE' if len(measured) == len(variants) and variants else 'PARTIAL')
    runtime = number(report['runtime_seconds'])
    if runtime < 0:
        raise ValueError('negative diagnostic runtime')
    return {'schema': 'satellite-rf-reference-sensitivity-summary-v1', 'status': status,
            'target': report['target'], 'date_gpst': report['date_gpst'],
            'fit_stations': report['fit_stations'],
            'baseline_status': baseline['status'], 'case_count': len(cases),
            'exclusion_count': len(variants), 'compared_count': len(measured),
            'runtime_seconds': runtime,
            'exclusion_status_counts': dict(Counter(row['status'] for row in variants)),
            'displacement_m': {'minimum': min(measured) if measured else None,
                               'median': statistics.median(measured) if measured else None,
                               'maximum': max(measured) if measured else None},
            'most_influential': sorted((row for row in rows if row['displacement_m'] is not None),
                                       key=lambda row: (-row['displacement_m'], row['excluded_reference']))[:5],
            'cases': rows, 'report_sha256': hashlib.sha256(raw).hexdigest(), 'input_sha256': hashes,
            'changes_scientific_verdict': False, 'is_accuracy_bound': False,
            'message': 'Sensibilità esplorativa alle esclusioni dei riferimenti. Non è accuratezza, raggio al 95% o nuova conferma.',
            'comparison_scope': 'Stessi assi a u0; anche l’istante di emissione stimato può cambiare. Baseline di sviluppo a pesi fissi, distinta dalla soluzione scientifica.'}


def diagnostic(report_path, inputs_path):
    if report_path is None:
        return {'status': 'NOT_COMPUTED', 'message': 'Diagnostica non richiesta; nessun calcolo avviato.'}
    try:
        return summarize(report_path, inputs_path)
    except OSError as error:
        return {'status': 'UNAVAILABLE', 'message': str(error)}
    except (ValueError, KeyError, TypeError, IndexError, OverflowError) as error:
        return {'status': 'INVALID', 'message': str(error)}


def attach(result, run_path, report_path=None):
    summary = diagnostic(report_path, run_path)
    if summary.get('status') in ('AVAILABLE', 'PARTIAL', 'BASELINE_UNAVAILABLE'):
        if (summary['target'] != result['target'] or summary['date_gpst'] != result['date_gpst']
                or summary['fit_stations'] != result['fit_stations']):
            summary = {'status': 'INVALID', 'message': 'Diagnostica appartenente a un altro evento.'}
    return result | {'diagnostics': {'reference_sensitivity': summary}}


def compute(run_path, output):
    """Explicit, post-terminal calculation in a separate process, no acquisition."""
    root, output = Path(run_path).resolve(), Path(output).resolve()
    read_result(root)  # Only closed, sealed jobs may enter this service command.
    if output.is_relative_to(root):
        raise ValueError('diagnostic output must be outside the scientific run')
    if output.exists():
        raise FileExistsError('diagnostic output already exists')
    if not (root/'estimation/admitted.json').is_file():
        return {'status': 'UNAVAILABLE', 'message': 'La richiesta non dispone di input ammessi per questa diagnostica.'}
    subprocess.run([sys.executable, '-m', 'research.exploratory.reference_sensitivity',
                    str(root), str(output)], cwd=Path(__file__).resolve().parents[1],
                   check=True, timeout=600, stdout=subprocess.DEVNULL)
    return diagnostic(output, root)
