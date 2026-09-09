import hashlib
import json
from types import SimpleNamespace

import pytest

from positioning.acquisition import write_json
from positioning.jobs import execute, status, dossier
from positioning.plans import make_plan, validate_plan
from positioning.__main__ import run_stage
from positioning.errors import ScientificRejection


def test_calendar_week_and_profile_are_explicit_and_reject_ignored_options():
    saturday = make_plan('G13', '2026-09-05')
    sunday = make_plan('G14', '2026-09-06')
    assert '/2434/' in saturday['oracle_url']
    assert '/2435/' in sunday['oracle_url']
    assert '2026249' in sunday['navigation_url']
    assert validate_plan(sunday) == sunday
    sunday['uncertainty']['nonlinear_margin_factor'] = 1.0
    with pytest.raises(ValueError, match='unsupported'):
        validate_plan(sunday)


@pytest.mark.parametrize('change', ['url', 'station', 'threshold', 'extra'])
def test_unsafe_or_unsupported_request_rejected_before_job_creation(tmp_path, change):
    plan = make_plan('G13', '2026-09-04')
    if change == 'url':
        plan['navigation_url'] = 'http://localhost/private'
    elif change == 'station':
        plan['fit_stations'][0] = '../../file'
    elif change == 'threshold':
        plan['confirmation']['uncertainty_radius_limit_m'] = 12000
    else:
        plan['target_orbit_prior'] = [1, 2, 3]
    path = tmp_path / 'plan.json'
    write_json(path, plan)
    with pytest.raises(ValueError):
        execute(path, tmp_path / 'run')
    assert not (tmp_path / 'run').exists()


def test_closed_job_stops_before_estimate_or_oracle_and_seals_download(tmp_path, monkeypatch):
    path = tmp_path / 'plan.json'; run = tmp_path / 'run'
    write_json(path, make_plan('G13', '2026-09-04'))
    called = []
    def child(command, **kwargs):
        called.append(command[3])
        assert command[3] == 'acquire'
        assert (run / 'request.json').exists()
        write_json(run / 'outcome.json', {'status': 'SOURCE_OR_MEASUREMENT_NOT_QUALIFIED',
                   'primary_pass': False, 'oracle_accessed': False})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr('positioning.jobs.subprocess.run', child)
    result = execute(path, run)
    assert result['state'] == 'COMPLETED'
    assert execute(path, run) == result
    assert called == ['acquire']
    document = dossier(run)
    assert document['estimated_ecef_at_emission_m'] is None
    assert document['observed_error_m'] is None
    for value in document['artifacts'].values():
        assert hashlib.sha256(value['content_utf8'].encode()).hexdigest() == value['sha256']
    (run / 'outcome.json').write_text('{}')
    with pytest.raises(ValueError, match='terminal artifact changed'):
        status(run)


def test_engineering_failure_is_not_a_scientific_outcome_or_silently_retried(tmp_path, monkeypatch):
    path = tmp_path / 'plan.json'; run = tmp_path / 'run'
    write_json(path, make_plan('G13', '2026-09-04'))
    monkeypatch.setattr('positioning.jobs.subprocess.run', lambda *a, **k: SimpleNamespace(returncode=1))
    assert execute(path, run)['state'] == 'FAILED'
    assert not (run / 'outcome.json').exists()
    assert dossier(run)['status'] == 'ENGINEERING_FAILURE'
    with pytest.raises(ValueError, match='already attempted'):
        execute(path, run)


def test_known_scientific_rejection_closes_before_oracle_but_bug_propagates(tmp_path, monkeypatch):
    args = SimpleNamespace(run=tmp_path)
    def rejected(*args):
        raise ScientificRejection('rank deficiency')
    monkeypatch.setattr('positioning.__main__.scientific_stage', rejected)
    result = run_stage('estimate', args)
    assert result['status'] == 'POSITION_NOT_IDENTIFIABLE'
    assert not result['oracle_access_attempted']
    assert not result['primary_pass']
    def bug(*args):
        raise ValueError('an unexpected programming or integrity defect')
    monkeypatch.setattr('positioning.__main__.scientific_stage', bug)
    with pytest.raises(ValueError, match='unexpected'):
        run_stage('estimate', args)
