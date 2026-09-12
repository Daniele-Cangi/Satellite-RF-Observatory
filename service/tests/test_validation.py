"""Cohort denominators and evidence binding, using invented observations only."""
from copy import deepcopy
import json

import pytest

from positioning.plans import make_network_plan
from service import worker
from service.requests import RequestStore
from service.validation import read_manifest, report
from service.workflow import NETWORK
from service.tests.test_worker import COMMIT, install_stages


@pytest.fixture
def cohort(tmp_path):
    cases = [{'id': str(i), 'plan': make_network_plan('G15', day, NETWORK,
              prior_access='Invented offline validation fixture.')} for i, day in enumerate(
                  ('2026-09-01', '2026-09-02', '2026-08-27'))]
    document = {'schema': 'satellite-rf-validation-cohort-v1', 'status': 'TEST_ONLY',
                'implementation': COMMIT, 'cases': cases}
    path = tmp_path / 'cohort.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    return path, document, RequestStore(tmp_path / 'queue.sqlite'), tmp_path / 'runs'


def test_unbound_cases_are_not_reported_as_completed_failures(cohort):
    path, document, store, runs = cohort
    result = report(path, store, 'owner', {}, runs)
    assert result['planned_count'] == 3
    assert result['state_counts'] == {'UNBOUND': 3}
    assert result['sealed_terminal_count'] == 0
    assert result['final_sample_fraction'] is None
    assert result['metrics']['observed_error_m']['missing_count'] == 3
    assert not result['acquisition_authorized']


@pytest.mark.parametrize('kind,verified', [('synthetic_pass', 1), ('unavailable', 0),
                                          ('software_error', 0)])
def test_sealed_results_pending_and_cancelled_remain_in_denominator(cohort, monkeypatch, kind, verified):
    path, document, store, runs = cohort
    install_stages(monkeypatch, kind=kind)
    first = store.submit('owner', 'a', document['cases'][0]['plan'],
                         implementation=COMMIT, purpose='prospective_attempt')
    worker.run_once(store, runs)
    second = store.submit('owner', 'b', document['cases'][1]['plan'],
                          implementation=COMMIT, purpose='prospective_attempt')
    store.cancel('owner', second['id'])
    bindings = {'0': first['id'], '1': second['id']}
    result = report(path, store, 'owner', bindings, runs)
    assert result['planned_count'] == 3 and result['sealed_terminal_count'] == 1
    assert result['verified_conditionally_count'] == verified
    assert result['observed_verified_fraction_of_planned'] == verified / 3
    assert result['final_sample_fraction'] is None
    assert result['state_counts']['CANCELLED'] == result['state_counts']['UNBOUND'] == 1
    (runs / first['id'] / 'result.json').write_text('{}')
    broken = report(path, store, 'owner', bindings, runs)
    assert broken['sealed_terminal_count'] == 0
    assert broken['state_counts']['EVIDENCE_UNAVAILABLE_OR_INVALID'] == 1
    assert broken['planned_count'] == 3


@pytest.mark.parametrize('change', ['plan', 'implementation', 'purpose', 'owner'])
def test_wrong_binding_cannot_contribute_evidence(cohort, change):
    path, document, store, runs = cohort
    plan = deepcopy(document['cases'][0]['plan'])
    if change == 'plan':
        plan['prior_access'] = 'Different exposure declaration'
    row = store.submit('owner', 'a', plan, implementation='b' * 40 if change == 'implementation' else COMMIT,
                       purpose='historical_replay' if change == 'purpose' else 'prospective_attempt')
    result = report(path, store, 'other' if change == 'owner' else 'owner', {'0': row['id']}, runs)
    assert result['state_counts']['EVIDENCE_UNAVAILABLE_OR_INVALID'] == 1


def test_overlapping_days_and_undeclared_or_duplicate_bindings_rejected(cohort):
    path, document, store, runs = cohort
    with pytest.raises(ValueError, match='undeclared'):
        report(path, store, 'owner', {'extra': 'x'}, runs)
    with pytest.raises(ValueError, match='multiple'):
        report(path, store, 'owner', {'0': 'x', '1': 'x'}, runs)
    document['cases'][1]['plan'] = deepcopy(document['cases'][0]['plan'])
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match='overlapping'):
        read_manifest(path)


def test_checked_in_candidate_has_24_distinct_days_and_fixed_profile():
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'research/validation/g3_v1_candidate.json'
    document, digest = read_manifest(path)
    assert len(document['cases']) == 24 and len(digest) == 64
    assert document['status'] == 'CANDIDATE_NOT_ADMITTED'
    assert {case['plan']['target'] for case in document['cases']} == {'G01', 'G09', 'G17', 'G25'}
    assert all(case['plan']['profile'] == 'gps-code-network-v1' for case in document['cases'])


def test_complete_sample_reports_fraction_without_population_claim(cohort, monkeypatch):
    path, document, store, runs = cohort
    bindings = {}
    for i, case in enumerate(document['cases']):
        install_stages(monkeypatch, kind='synthetic_pass' if i == 0 else 'unavailable')
        row = store.submit('owner', case['id'], case['plan'],
                           implementation=COMMIT, purpose='prospective_attempt')
        worker.run_once(store, runs)
        bindings[case['id']] = row['id']
    result = report(path, store, 'owner', bindings, runs)
    assert result['final_sample_fraction'] == 1 / 3
    assert result['sealed_terminal_count'] == 3
    assert result['metrics']['observed_error_m'] == {
        'observed_count': 1, 'missing_count': 2, 'values': [{'id': '0', 'value': 10.}]}
    assert not result['population_coverage_established']


def test_cli_empty_cohort_report_does_not_dispatch(cohort, capsys):
    from service.__main__ import main
    path, document, store, runs = cohort
    bindings = path.parent / 'bindings.json'
    bindings.write_text('{}')
    assert main(['validation-report', str(path), '--bindings', str(bindings),
                 '--queue', str(store.path), '--runs', str(runs), '--owner', 'owner']) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['planned_count'] == 3 and result['bound_count'] == 0
    assert not runs.exists()
