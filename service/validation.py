"""Offline cohort accounting; never submit requests or authorize acquisition."""
from collections import Counter
import hashlib
from pathlib import Path
import re

from positioning.plans import validate_plan
from .workflow import _json
from .worker import request_status


def read_manifest(path):
    content = Path(path).read_bytes()
    document = _json(content)
    if document.get('schema') != 'satellite-rf-validation-cohort-v1':
        raise ValueError('unsupported cohort schema')
    if not re.fullmatch(r'[0-9a-f]{40}', document.get('implementation', '')):
        raise ValueError('cohort must pin a full implementation commit')
    cases = document.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('nonempty declared cohort required')
    ids, days = set(), set()
    for case in cases:
        if set(case) != {'id', 'plan'} or not isinstance(case['id'], str) or not case['id']:
            raise ValueError('invalid cohort case')
        plan = validate_plan(case['plan'])
        # A reference satellite in one attempt could be the next target on
        # the same day. This first cohort deliberately avoids that overlap.
        if case['id'] in ids or plan['date_gpst'] in days:
            raise ValueError('duplicate case or overlapping measurement day')
        ids.add(case['id'])
        days.add(plan['date_gpst'])
    return document, hashlib.sha256(content).hexdigest()


def report(manifest_path, store, owner, bindings, runs_root):
    """Account for every declared case using the queue's verified evidence.

    Bindings map case IDs to queue IDs. Absence means UNBOUND, not proof that
    no acquisition occurred elsewhere. Broken evidence remains in the count.
    Queue reads can quarantine expired claims, as ordinary status reads do.
    """
    manifest, digest = read_manifest(manifest_path)
    ids = {case['id'] for case in manifest['cases']}
    if not isinstance(bindings, dict) or set(bindings) - ids:
        raise ValueError('bindings include undeclared cases')
    if any(not isinstance(value, str) or not value for value in bindings.values()):
        raise ValueError('bindings require request IDs')
    if len(set(bindings.values())) != len(bindings):
        raise ValueError('one request cannot stand for multiple cases')
    rows = []
    for case in manifest['cases']:
        plan = case['plan']
        row = {'id': case['id'], 'target': plan['target'], 'date_gpst': plan['date_gpst'],
               'request_id': bindings.get(case['id']), 'state': 'UNBOUND',
               'result': None, 'reason': None}
        if row['request_id'] is not None:
            try:
                queued = request_status(store, owner, row['request_id'], runs_root)
                declaration = queued['declaration']
                if (declaration['plan'] != plan
                        or declaration['implementation'] != manifest['implementation']
                        or declaration['purpose'] != 'prospective_attempt'):
                    raise ValueError('request differs from declared cohort case')
                row['state'] = queued['state']
                row['result'] = queued.get('result')
                row['reason'] = queued.get('review')
            except (OSError, ValueError, KeyError, TypeError) as error:
                row['state'] = 'EVIDENCE_UNAVAILABLE_OR_INVALID'
                row['reason'] = type(error).__name__ + ': ' + str(error)
        rows.append(row)
    results = [row['result'] for row in rows if row['result'] is not None]
    verified = sum(result['verified'] for result in results)
    outcomes = Counter(result['scientific_status'] for result in results)
    metrics = {}
    for key in ('observed_error_m', 'prospective_uncertainty_radius_m'):
        values = [{'id': row['id'], 'value': row['result'][key]} for row in rows
                  if row['result'] is not None and row['result'][key] is not None]
        metrics[key] = {'observed_count': len(values), 'missing_count': len(rows) - len(values),
                        'values': values}
    return {
        'schema': 'satellite-rf-validation-report-v1', 'manifest_sha256': digest,
        'cohort_status': manifest.get('status'), 'implementation': manifest['implementation'],
        'planned_count': len(rows), 'bound_count': len(bindings),
        'sealed_terminal_count': len(results), 'verified_conditionally_count': verified,
        'state_counts': dict(Counter(row['state'] for row in rows)),
        'scientific_outcomes': dict(outcomes),
        'observed_verified_fraction_of_planned': verified / len(rows),
        'final_sample_fraction': verified / len(rows) if len(results) == len(rows) else None,
        'metrics': metrics, 'cases': rows,
        'acquisition_authorized': False, 'population_coverage_established': False,
        'runtime_seconds': None,
        'limitations': [
            'UNBOUND is a missing queue association, not evidence of no prior access.',
            'Conditional v1 outcomes do not qualify kinematic error transfer or population coverage.',
            'Availability and held-out evidence are retained per case; missing values are not zeros.',
            'Runtime is not yet measured by this cohort report; queue age is not compute time.',
            'A manifest hash identifies local bytes, not a trusted preregistration timestamp.',
        ],
    }
