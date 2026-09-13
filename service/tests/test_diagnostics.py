"""Diagnostic summaries never substitute for a sealed scientific verdict."""
from collections import Counter
import json
from pathlib import Path

import pytest

from service import diagnostics
from service.__main__ import main
from service.workflow import read_result


ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT/'experiments/positioning_g14_doy246_network'
REPORT = ROOT/'research/exploratory/results/g14_reference_sensitivity_v1.json'


@pytest.mark.parametrize('target,inputs,expected,count', [
    ('g14', 'experiments/positioning_g14_doy246_network', 11.056944392283443, 21),
    ('g12', 'research/exploratory/inputs/g12_doy248', 26.505446392977714, 22),
])
def test_real_reports_bind_inputs_and_exclude_baseline_from_statistics(target, inputs, expected, count):
    result = diagnostics.summarize(ROOT/f'research/exploratory/results/{target}_reference_sensitivity_v1.json', ROOT/inputs)
    assert result['status'] == 'AVAILABLE'
    assert result['exclusion_count'] == result['compared_count'] == count
    assert result['displacement_m']['maximum'] == pytest.approx(expected)
    assert result['displacement_m']['minimum'] > 0
    assert len(result['cases']) == count and len(result['most_influential']) == 5
    assert not result['changes_scientific_verdict'] and not result['is_accuracy_bound']


def test_attach_preserves_verdict_and_all_original_fields_even_for_bad_diagnostic():
    scientific = read_result(ARCHIVE)
    for report in (None, REPORT, ROOT/'research/exploratory/results/g12_reference_sensitivity_v1.json'):
        enriched = diagnostics.attach(scientific, ARCHIVE, report)
        assert {key: enriched[key] for key in scientific} == scientific
    assert diagnostics.attach(scientific, ARCHIVE)['diagnostics']['reference_sensitivity']['status'] == 'NOT_COMPUTED'
    assert diagnostics.attach(scientific, ARCHIVE, ROOT/'missing.json')['diagnostics']['reference_sensitivity']['status'] == 'UNAVAILABLE'


def test_small_sensitivity_never_promotes_an_inconclusive_verdict():
    original = read_result(ARCHIVE) | {'status': 'INCONCLUSIVE', 'verified': False,
        'scientific_status': 'UNCERTAINTY_TOO_LARGE', 'prospective_uncertainty_radius_m': 12000.}
    enriched = diagnostics.attach(original, ARCHIVE, REPORT)
    assert enriched['diagnostics']['reference_sensitivity']['status'] == 'AVAILABLE'
    assert {key: enriched[key] for key in original} == original


def test_closed_source_failure_does_not_start_a_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics.subprocess, 'run', lambda *a, **k: pytest.fail('no admitted inputs'))
    assert diagnostics.compute(ROOT/'experiments/positioning_g13_doy247_request',
                               tmp_path/'unused.json')['status'] == 'UNAVAILABLE'
    assert not (tmp_path/'unused.json').exists()


def changed_report(tmp_path, change):
    document = json.loads(REPORT.read_bytes())
    change(document)
    path = tmp_path/'report.json'
    path.write_text(json.dumps(document), encoding='utf-8')
    return path


@pytest.mark.parametrize('change', [
    lambda doc: doc.update(target='G12'),
    lambda doc: doc.update(case_count=1),
    lambda doc: doc['cases'].pop(),
    lambda doc: doc['cases'][1].update(displacement_from_baseline_m=0),
    lambda doc: doc['cases'][1].update(u0_relative_s=999),
    lambda doc: doc['cases'][1].update(status='UNKNOWN'),
    lambda doc: doc.update(target_orbit_accessed=True),
    lambda doc: doc['cases'][1].update(displacement_from_baseline_m=float('nan')),
])
def test_contradictory_or_nonfinite_reports_are_visible_as_invalid(tmp_path, change):
    assert diagnostics.diagnostic(changed_report(tmp_path, change), ARCHIVE)['status'] == 'INVALID'


def test_failed_variants_are_kept_with_null_distance(tmp_path):
    def change(doc):
        doc['cases'][1].update(status='ENGINEERING_FAILURE', reason='Invented diagnostic error',
                               displacement_from_baseline_m=None)
        doc['status_counts'] = dict(Counter(row['status'] for row in doc['cases']))
    result = diagnostics.summarize(changed_report(tmp_path, change), ARCHIVE)
    assert result['status'] == 'PARTIAL' and result['exclusion_count'] == 21
    assert result['compared_count'] == 20 and result['cases'][0]['displacement_m'] is None
    assert result['cases'][0]['reason'] == 'Invented diagnostic error'


def test_unavailable_baseline_has_no_misleading_statistics(tmp_path):
    def change(doc):
        doc['baseline_status'] = doc['cases'][0]['status'] = 'FIT_REJECTED'
        for row in doc['cases']:
            row['displacement_from_baseline_m'] = None
        doc['status_counts'] = dict(Counter(row['status'] for row in doc['cases']))
    result = diagnostics.summarize(changed_report(tmp_path, change), ARCHIVE)
    assert result['status'] == 'BASELINE_UNAVAILABLE'
    assert result['displacement_m'] == {'minimum': None, 'median': None, 'maximum': None}
    assert result['compared_count'] == 0


def test_cli_attaches_existing_real_diagnostic_without_recalculation(capsys, monkeypatch):
    monkeypatch.setattr(diagnostics.subprocess, 'run', lambda *a, **k: pytest.fail('unexpected calculation'))
    assert main(['result', str(ARCHIVE), '--diagnostic', str(REPORT)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['verified'] is True
    assert result['diagnostics']['reference_sensitivity']['exclusion_count'] == 21


def test_compute_requires_terminal_and_external_new_output(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostics.subprocess, 'run', lambda *a, **k: pytest.fail('unexpected calculation'))
    with pytest.raises(FileNotFoundError):
        diagnostics.compute(tmp_path, tmp_path/'result.json')
    with pytest.raises(ValueError, match='outside'):
        diagnostics.compute(ARCHIVE, ARCHIVE/'development.json')
    existing = tmp_path/'existing.json'
    existing.write_text('{}')
    with pytest.raises(FileExistsError):
        diagnostics.compute(ARCHIVE, existing)


def test_compute_invokes_isolated_runner_and_returns_bound_summary(tmp_path, monkeypatch):
    output = tmp_path/'diagnostic.json'
    def child(command, **kwargs):
        assert command[1:3] == ['-m', 'research.exploratory.reference_sensitivity']
        assert Path(command[3]) == ARCHIVE.resolve() and kwargs['timeout'] == 600
        output.write_bytes(REPORT.read_bytes())
    monkeypatch.setattr(diagnostics.subprocess, 'run', child)
    assert diagnostics.compute(ARCHIVE, output)['status'] == 'AVAILABLE'


def test_pending_queue_does_not_read_diagnostic_and_owner_is_checked(tmp_path, capsys, monkeypatch):
    from service.requests import RequestStore
    from service.tests.test_worker import COMMIT, request
    from service.worker import submit_request
    queue, runs = tmp_path/'queue.sqlite', tmp_path/'runs'
    store = RequestStore(queue)
    row = submit_request(store, 'alice', 'one', request(), COMMIT)
    monkeypatch.setattr(diagnostics, 'diagnostic', lambda *a: pytest.fail('pending report must not be read'))
    arguments = ['request-status', row['id'], '--queue', str(queue), '--runs', str(runs),
                 '--diagnostic', str(REPORT), '--owner']
    assert main(arguments+['alice']) == 0
    response = json.loads(capsys.readouterr().out)
    assert response['state'] == 'QUEUED'
    assert response['diagnostics']['reference_sensitivity']['status'] == 'NOT_READY'
    with pytest.raises(KeyError):
        main(arguments+['bob'])
