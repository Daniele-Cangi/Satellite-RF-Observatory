"""Offline request intake and sealed-result presentation for the general flow.

This module neither acquires observations nor runs an estimator. Planning a
supported request is distinct from source availability and scientific admission.
"""
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

from positioning.plans import POOL_PROFILE, make_network_plan, validate_plan


NETWORK = (
    'ALGO00CAN', 'AMC400USA', 'AREQ00PER', 'BOGT00COL', 'BRAZ00BRA',
    'DRAO00CAN', 'MKEA00USA', 'PIE100USA', 'STJO00CAN', 'YELL00CAN',
)
CLOSED_EVENTS = {
    ('G08', '2026-09-06'): 'experiments/gnss_inverse_positioning',
    ('G12', '2026-09-07'): 'experiments/positioning_g12_doy250',
    ('G12', '2026-09-05'): 'experiments/positioning_g12_doy248',
    ('G13', '2026-09-04'): 'experiments/positioning_g13_doy247_request',
    ('G14', '2026-09-03'): 'experiments/positioning_g14_doy246_network',
}
OUTCOMES = {
    'INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED':
        ('VERIFIED_CONDITIONALLY', 'Posizione storica verificata nelle condizioni dichiarate.'),
    'UNCERTAINTY_TOO_LARGE':
        ('INCONCLUSIVE', 'La stima supera il limite di incertezza dichiarato.'),
    'SOURCE_OR_MEASUREMENT_NOT_QUALIFIED':
        ('NOT_VERIFIABLE', 'Dati o calibrazione non soddisfano i requisiti del metodo.'),
    'SOURCE_UNAVAILABLE':
        ('NOT_VERIFIABLE', 'Le fonti richieste non sono disponibili.'),
    'POSITION_NOT_IDENTIFIABLE':
        ('INCONCLUSIVE', 'Le misure non determinano una posizione sufficientemente identificabile.'),
    'CONFIRMATION_REJECTED':
        ('NOT_CONFIRMED', 'La stima non supera i controlli indipendenti dichiarati.'),
    'ENGINEERING_FAILURE':
        ('EXECUTION_FAILED', 'Un errore di esecuzione richiede una diagnosi tecnica.'),
}


def capabilities():
    return {
        'schema': 'satellite-rf-capabilities-v1',
        'delivery': 'LOCAL_EXPERIMENTAL',
        'profile': POOL_PROFILE,
        'targets': 'GPS PRN G01..G32; receiver-labelled identities',
        'date_min_gpst': '2022-11-27',
        'time_scope': 'Completed historical GPST day; first qualifying window, not an arbitrary instant',
        'candidate_stations': list(NETWORK),
        'withheld_station': 'GOLD00USA',
        'source_availability': 'CHECKED_PER_REQUEST_AFTER_PLAN_FREEZE',
        'uncertainty_scope': 'CONDITIONAL_EVENT_ONLY',
        'population_coverage_established': False,
        'kinematic_profile_available': False,
        'live_position_available': False,
        'automatic_execution_available': True,
        'execution_mode': 'OPERATOR_STARTED_SINGLE_HOST_QUEUE_WORKER',
        'http_submission_available': False,
    }


def prepare_request(request, *, today=None):
    """Compile a small user request into the existing exact scientific plan."""
    result = {
        'schema': 'satellite-rf-request-assessment-v1',
        'status': 'INVALID_REQUEST', 'reason_code': None, 'message': None,
        'plan': None, 'archive_path': None,
        'observations_accessed': False, 'target_orbit_accessed': False,
        'availability': 'NOT_CHECKED', 'scientific_admission': 'NOT_EVALUATED',
    }

    def reject(status, code, message):
        return result | {'status': status, 'reason_code': code, 'message': message}

    if not isinstance(request, dict) or set(request) != {'target', 'date_gpst', 'prior_access', 'profile'}:
        return reject('INVALID_REQUEST', 'REQUEST_FIELDS',
                      'Specificare soltanto satellite, giorno GPST, profilo e accessi precedenti.')
    if request['profile'] != POOL_PROFILE:
        return reject('UNSUPPORTED_REQUEST', 'PROFILE_NOT_SUPPORTED',
                      'Il flusso iniziale supporta il profilo storico GPS con misure di codice.')
    target = request['target']
    if not isinstance(target, str) or not re.fullmatch(r'G(?:0[1-9]|[12][0-9]|3[0-2])', target):
        return reject('UNSUPPORTED_REQUEST', 'TARGET_NOT_SUPPORTED',
                      'Il dominio iniziale comprende le identità GPS da G01 a G32.')
    raw_day = request['date_gpst']
    try:
        if not isinstance(raw_day, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw_day):
            raise ValueError('noncanonical date')
        day = date.fromisoformat(raw_day)
    except ValueError:
        return reject('INVALID_REQUEST', 'INVALID_DATE', 'Usare un giorno valido nel formato YYYY-MM-DD GPST.')
    if day < date(2022, 11, 27):
        return reject('UNSUPPORTED_REQUEST', 'DATE_NOT_SUPPORTED',
                      'Questo profilo di prodotti supporta giorni dal 2022-11-27.')
    # UTC calendar cutoff is conservative at the GPST/UTC midnight boundary.
    if day >= (today if today is not None else datetime.now(timezone.utc).date()):
        return reject('DAY_NOT_COMPLETE', 'HISTORICAL_DAY_REQUIRED',
                      'Il flusso richiede un giorno storico completo; non fornisce posizioni live.')
    if (target, raw_day) in CLOSED_EVENTS:
        return result | {
            'status': 'ARCHIVED_EVENT', 'reason_code': 'CLOSED_EVENT',
            'message': 'Evento già concluso: consultare le prove originali senza avviare un nuovo tentativo.',
            'archive_path': CLOSED_EVENTS[target, raw_day],
        }
    prior = request['prior_access']
    if not isinstance(prior, str) or not prior.strip() or len(prior) > 4000:
        return reject('INVALID_REQUEST', 'PRIOR_ACCESS_REQUIRED',
                      'Dichiarare gli accessi precedenti; questa dichiarazione non certifica il blinding.')
    plan = make_network_plan(target, raw_day, NETWORK, prior_access=prior)
    validate_plan(plan)
    return result | {
        'status': 'PLAN_PREPARED', 'reason_code': 'AWAITING_SOURCE_CHECK',
        'message': 'Piano preparato. Disponibilità, calibrazione e verificabilità devono ancora essere valutate.',
        'plan': plan,
    }


def _json(content):
    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)

    def number(value):
        parsed = float(value)
        if not math.isfinite(parsed):
            raise ValueError('nonfinite JSON number')
        return parsed

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result

    return json.loads(content, parse_constant=constant, parse_float=number,
                      object_pairs_hook=unique)


def read_result(run_path):
    """Read a completed worker dossier, validating sealed bytes without writing.

    Local hashes detect changed artifacts; they do not authenticate the author,
    prove scientific correctness or provide an external trusted timestamp.
    """
    root = Path(run_path).resolve()
    receipt = _json((root / 'terminal_receipt.json').read_bytes())
    artifacts = receipt['artifacts']
    if 'dossier.json' not in artifacts:
        raise ValueError('terminal seal must include dossier.json')
    dossier_bytes = None
    details = {}
    for name, expected in artifacts.items():
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('unsafe sealed artifact: ' + name)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError('terminal artifact changed: ' + name)
        if name == 'dossier.json':
            dossier_bytes = content
        elif name in ('outcome.json', 'job.json'):
            details[name] = _json(content)
    document = _json(dossier_bytes)
    if document['schema'] != 'satellite-rf-position-dossier-v1':
        raise ValueError('unsupported dossier schema')
    scientific = document['status']
    if scientific not in OUTCOMES:
        raise ValueError('unmapped scientific outcome: ' + scientific)
    passed = scientific == 'INDEPENDENT_SATELLITE_POSITION_DEMONSTRATED'
    if document['primary_pass'] is not passed:
        raise ValueError('contradictory scientific outcome')
    state = 'FAILED' if scientific == 'ENGINEERING_FAILURE' else 'COMPLETED'
    if document['job_state'] != state:
        raise ValueError('contradictory operational state')
    outcome, job = details.get('outcome.json', {}), details.get('job.json', {})
    if outcome and (outcome.get('status') != scientific or outcome.get('primary_pass') is not passed):
        raise ValueError('dossier differs from sealed scientific outcome')
    position = document.get('inferred_position')
    radius = document.get('prospective_uncertainty_radius_m')
    error = document.get('observed_error_m')
    for metric in (radius, error):
        if metric is not None and (type(metric) not in (int, float) or metric < 0):
            raise ValueError('invalid result metric')
    if passed and (position is None or radius is None or error is None
                   or not isinstance(document.get('heldout'), dict)
                   or document['heldout'].get('status') != 'HELD_OUT_RECEIVER_CONFIRMED'):
        raise ValueError('passing dossier is missing evidence')
    status, message = OUTCOMES[scientific]
    return {
        'schema': 'satellite-rf-verification-result-v1',
        'status': status, 'message': message,
        'reason': outcome.get('reason', job.get('reason')),
        'failed_stage': outcome.get('stage', job.get('stage') if state == 'FAILED' else None),
        'scientific_status': scientific, 'operational_state': state,
        'target': document['target'], 'date_gpst': document['date_gpst'],
        'verified': passed, 'is_live': False,
        'inferred_position': position,
        'estimated_ecef_at_emission_m': document.get('estimated_ecef_at_emission_m'),
        'prospective_uncertainty_radius_m': radius, 'observed_error_m': error,
        'heldout': document.get('heldout'),
        'fit_stations': document['fit_stations'],
        'withheld_station': document['withheld_station'],
        'availability': document.get('availability'),
        'claim': document['claim'], 'prior_access': document['prior_access'],
        'uncertainty_scope': 'CONDITIONAL_EVENT_ONLY',
        'population_coverage_established': False,
        'evidence': {'dossier_sha256': hashlib.sha256(dossier_bytes).hexdigest(),
                     'request_sha256': artifacts.get('request.json'),
                     'sealed_artifact_count': len(artifacts)},
    }
