"""Offline request-to-plan and sealed worker-result integration checks."""
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from positioning.acquisition import write_json
from positioning.jobs import execute
from positioning.plans import validate_plan
from service.__main__ import main
from service.workflow import capabilities, prepare_request, read_result


ROOT = Path(__file__).resolve().parents[2]
TODAY = date(2026, 9, 12)


def request(**changes):
    return dict(target='G15', date_gpst='2026-09-01',
                profile='gps-code-network-v1', prior_access='Offline software fixture only.') | changes


def test_minimal_request_builds_the_existing_fixed_profile_without_availability_claim():
    result = prepare_request(request(), today=TODAY)
    assert result['status'] == 'PLAN_PREPARED'
    plan = validate_plan(result['plan'])
    assert plan['target'] == 'G15' and plan['date_gpst'] == '2026-09-01'
    assert len(plan['network']['candidate_stations']) == 10
    assert plan['network']['fit_count'] == 7
    assert plan['withheld_station'] not in plan['network']['candidate_stations']
    assert result['availability'] == 'NOT_CHECKED'
    assert result['scientific_admission'] == 'NOT_EVALUATED'
    assert not result['observations_accessed'] and not result['target_orbit_accessed']
    assert capabilities()['automatic_execution_available'] is False


@pytest.mark.parametrize('changes,reason', [
    ({'target': 'ISS'}, 'TARGET_NOT_SUPPORTED'),
    ({'target': 'G33'}, 'TARGET_NOT_SUPPORTED'),
    ({'profile': 'kinematic'}, 'PROFILE_NOT_SUPPORTED'),
    ({'date_gpst': '2026-02-30'}, 'INVALID_DATE'),
    ({'date_gpst': '20260901'}, 'INVALID_DATE'),
    ({'date_gpst': '2022-11-26'}, 'DATE_NOT_SUPPORTED'),
    ({'date_gpst': '2026-09-12'}, 'HISTORICAL_DAY_REQUIRED'),
    ({'date_gpst': '2027-01-01'}, 'HISTORICAL_DAY_REQUIRED'),
    ({'prior_access': '  '}, 'PRIOR_ACCESS_REQUIRED'),
    ({'oracle_url': 'https://example.test'}, 'REQUEST_FIELDS'),
])
def test_unsupported_or_unsafe_request_does_not_produce_a_plan(changes, reason):
    result = prepare_request(request(**changes), today=TODAY)
    assert result['reason_code'] == reason
    assert result['plan'] is None


def test_closed_event_routes_to_original_evidence_without_new_plan():
    result = prepare_request(request(target='G14', date_gpst='2026-09-03'), today=TODAY)
    assert result['status'] == 'ARCHIVED_EVENT'
    assert result['plan'] is None
    assert (ROOT / result['archive_path'] / 'outcome.json').is_file()


def test_sealed_historical_pass_and_rejection_keep_scope_and_missing_metrics():
    passed = read_result(ROOT / 'experiments/positioning_g14_doy246_network')
    rejected = read_result(ROOT / 'experiments/positioning_g13_doy247_request')
    assert passed['status'] == 'VERIFIED_CONDITIONALLY' and passed['verified'] is True
    assert passed['observed_error_m'] == pytest.approx(31.016966131539373)
    assert passed['prospective_uncertainty_radius_m'] == pytest.approx(5755.157155537385)
    assert passed['inferred_position']['xyz_m'] != passed['estimated_ecef_at_emission_m']
    assert 'u0' in passed['inferred_position']['frame']
    assert not passed['is_live'] and not passed['population_coverage_established']
    assert rejected['operational_state'] == 'COMPLETED'
    assert rejected['status'] == 'NOT_VERIFIABLE' and not rejected['verified']
    assert rejected['inferred_position'] is None
    assert rejected['observed_error_m'] is None
    assert rejected['prospective_uncertainty_radius_m'] is None


@pytest.mark.parametrize('software_error', [False, True])
def test_prepared_plan_through_real_worker_with_simulated_source_failure(tmp_path, monkeypatch, software_error):
    plan = prepare_request(request(), today=TODAY)['plan']
    path, run = tmp_path / 'plan.json', tmp_path / 'run'
    write_json(path, plan)
    calls = []

    def child(command, **kwargs):
        calls.append(command[3])
        if not software_error:
            write_json(run / 'outcome.json', {
                'status': 'SOURCE_UNAVAILABLE', 'primary_pass': False,
                'reason': 'Simulated unavailable source', 'oracle_accessed': False,
            }, exclusive=True)
        return SimpleNamespace(returncode=1 if software_error else 0)

    monkeypatch.setattr('positioning.jobs.subprocess.run', child)
    execute(path, run)
    result = read_result(run)
    assert calls == ['acquire']
    assert not result['verified'] and result['inferred_position'] is None
    assert result['status'] == ('EXECUTION_FAILED' if software_error else 'NOT_VERIFIABLE')
    assert result['operational_state'] == ('FAILED' if software_error else 'COMPLETED')
    assert result['reason'] == ('STAGE_PROCESS_FAILED' if software_error else 'Simulated unavailable source')
    assert not (run / 'oracle_request.json').exists()
    (run / 'dossier.json').write_text('{}')
    with pytest.raises(ValueError, match='terminal artifact changed'):
        read_result(run)


def _sealed_document(tmp_path, **changes):
    source = ROOT / 'experiments/positioning_g14_doy246_network/dossier.json'
    document = json.loads(source.read_bytes()) | changes
    document.pop('artifacts', None)
    raw = json.dumps(document).encode()
    (tmp_path / 'dossier.json').write_bytes(raw)
    seal = {'artifacts': {'dossier.json': hashlib.sha256(raw).hexdigest()}}
    (tmp_path / 'terminal_receipt.json').write_text(json.dumps(seal))


def test_small_oracle_error_does_not_promote_excessive_uncertainty(tmp_path):
    _sealed_document(tmp_path, status='UNCERTAINTY_TOO_LARGE', primary_pass=False,
                     prospective_uncertainty_radius_m=12000, observed_error_m=0.01)
    result = read_result(tmp_path)
    assert result['status'] == 'INCONCLUSIVE' and not result['verified']
    assert result['prospective_uncertainty_radius_m'] == 12000


@pytest.mark.parametrize('changes', [
    {'status': 'NEW_UNREVIEWED_STATUS'}, {'primary_pass': False},
    {'job_state': 'RUNNING'}, {'heldout': None}, {'observed_error_m': float('nan')},
])
def test_unknown_contradictory_or_nonfinite_dossier_is_rejected(tmp_path, changes):
    _sealed_document(tmp_path, **changes)
    with pytest.raises(ValueError):
        read_result(tmp_path)


def test_unsealed_or_traversing_result_is_rejected_without_writing(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_result(tmp_path)
    assert list(tmp_path.iterdir()) == []
    (tmp_path / 'terminal_receipt.json').write_text(json.dumps({
        'artifacts': {'../outside.json': '0' * 64, 'dossier.json': '0' * 64},
    }))
    with pytest.raises(ValueError, match='unsafe sealed artifact'):
        read_result(tmp_path)


def test_cli_writes_consumable_plan_once_and_never_overwrites(tmp_path, capsys):
    output = tmp_path / 'plan.json'
    args = ['prepare', 'G15', '2026-09-01', '--prior-access', 'Offline fixture',
            '--plan-output', str(output)]
    assert main(args) == 0
    original = output.read_bytes()
    validate_plan(json.loads(original))
    assert json.loads(capsys.readouterr().out)['status'] == 'PLAN_PREPARED'
    with pytest.raises(FileExistsError):
        main(args)
    assert output.read_bytes() == original
