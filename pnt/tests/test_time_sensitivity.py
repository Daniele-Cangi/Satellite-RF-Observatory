"""Interval limits and retained failures, using synthetic UTC/NTS cases."""

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from pnt.tests.test_gnss_time import MS, NS, inputs, compare, bracket_inputs, compare_bracket
from pnt.time_sensitivity import assess_time_sensitivity
from pnt.time_witness import compare_claim


@pytest.mark.parametrize('bracket', [False, True])
def test_exact_closed_interval_edges_and_one_ns_separation(bracket):
    witness, capture = bracket_inputs() if bracket else inputs()
    baseline = compare_bracket(witness, capture) if bracket else compare(witness, capture)
    kind = 'bracket_comparisons' if bracket else 'comparisons'
    key = 'bracket_status_counts' if bracket else 'comparison_status_counts'
    lower, upper = baseline['records'][0][kind][0]['claim_minus_witness_ns']
    lo, hi = -upper, -lower
    original = copy.deepcopy(baseline)
    report = assess_time_sensitivity(baseline, [lo - 1, lo, hi, hi + 1])
    assert report['baseline'] == original == baseline
    assert report['compatible_shift_intervals'] == [dict(
        source_index=0, comparison_kind=kind, comparison_index=0, compatible_shift_ns=[lo, hi])]
    assert [case[key] for case in report['offset_cases']] == [
        {'NOT_DISTINGUISHABLE': 1}, {'INCONSISTENT_WITH_WITNESS': 1},
        {'NOT_DISTINGUISHABLE': 1}, {'NOT_DISTINGUISHABLE': 1}, {'INCONSISTENT_WITH_WITNESS': 1}]
    assert baseline == original


def test_offsets_match_full_engine_recomparison_without_touching_receipts():
    witness, capture = inputs()
    baseline = compare(witness, capture)
    report = assess_time_sensitivity(baseline, [0, -NS, -MS, MS, NS])
    for case in report['offset_cases']:
        claim = dict(baseline['records'][0]['claim'])
        claim['unix_ns'] += case['utc_claim_offset_ns']
        direct = compare_claim(witness['attempts'][0]['exchange'], claim, **witness['assumptions'])
        assert case['comparison_status_counts'] == {direct['status']: 1}
    assert report['offset_cases'][1]['record_pattern_counts']['ALL_INCONSISTENT'] == 1
    assert report['offset_cases'][2]['record_pattern_counts']['ALL_NOT_DISTINGUISHABLE'] == 1
    assert report['assumptions']['rf_attack_simulation'] is False


def test_baseline_is_recomputed_instead_of_trusting_retained_verdicts():
    witness, capture = inputs()
    baseline = compare(witness, capture)
    saved = copy.deepcopy(baseline)
    saved['records'] = [{'status': 'ALLOW', 'witness_interval': {'lower_unix_ns': 0}}]
    saved['coverage'] = {'receiver_records': 999}
    report = assess_time_sensitivity(saved, [NS])
    assert report['baseline'] == baseline
    assert report['offset_cases'][0]['comparison_status_counts'] == {'NOT_DISTINGUISHABLE': 1}


def test_conflicting_endpoints_and_unsupported_records_remain_visible():
    witness, capture = inputs()
    conflicting = copy.deepcopy(witness['attempts'][0])
    conflicting['server'] = 'conflicting-source'
    for field in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
        conflicting['exchange'][field] += NS
    witness['attempts'].extend([dict(server='failed', status='WITNESS_UNAVAILABLE', reason='TimeoutError'),
                                conflicting])
    capture['records'].append({})
    report = assess_time_sensitivity(compare(witness, capture), [NS])
    assert report['baseline']['witness_report']['attempts'][1]['reason'] == 'TimeoutError'
    for case in report['offset_cases']:
        assert case['record_indices_by_pattern']['MIXED'] == [0]
        assert case['record_indices_by_pattern']['INSUFFICIENT_EVIDENCE'] == [1]
        assert case['comparison_status_counts'] == {
            'INSUFFICIENT_EVIDENCE': 4, 'INCONSISTENT_WITH_WITNESS': 1, 'NOT_DISTINGUISHABLE': 1}
        failed = next(e for e in case['endpoint_status_counts'] if e['server'] == 'failed')
        assert failed['status_counts'] == {'INSUFFICIENT_EVIDENCE': 2}


@pytest.mark.parametrize('failure', ['failed_anchor', 'missing_association', 'known_age_violation'])
def test_offsets_cannot_manufacture_temporal_support(failure):
    witness, capture = bracket_inputs()
    if failure == 'failed_anchor':
        witness['attempts'].insert(1, dict(server='synthetic-witness', status='WITNESS_UNAVAILABLE',
                                           reason='TimeoutError'))
    elif failure == 'missing_association':
        del capture['records'][0]['capture_id']
    else:
        capture['records'][0]['epoch_age_budget_violation'] = 'known late receipt'
    report = assess_time_sensitivity(compare_bracket(witness, capture), [-NS, NS])
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['compatible_shift_intervals'] == []
    for case in report['offset_cases']:
        assert case['record_indices_by_pattern']['INSUFFICIENT_EVIDENCE'] == [0]
        assert set(case['comparison_status_counts']) == {'INSUFFICIENT_EVIDENCE'}
        assert set(case['bracket_status_counts']) == {'INSUFFICIENT_EVIDENCE'}


def test_android_unknown_alignment_remains_insufficient_at_every_offset():
    from pnt.tests.test_android_time import inputs as android_inputs, compare as android_compare

    witness, raw, _, _ = android_inputs(bracket=True)
    baseline = android_compare(witness, raw, epoch_alignment_error_ns=None,
                               epoch_alignment_source=None, bracket_span_ns=200 * MS)
    report = assess_time_sensitivity(baseline, [-NS, NS])
    assert report['baseline'] == baseline
    for case in report['offset_cases']:
        assert case['record_pattern_counts']['INSUFFICIENT_EVIDENCE'] == 8
        assert case['bracket_status_counts'] == {'INSUFFICIENT_EVIDENCE': 8}


@pytest.mark.parametrize('offsets', [[], [True], [1.5], [1, 1]])
def test_invalid_offset_grid_rejected(offsets):
    with pytest.raises(ValueError):
        assess_time_sensitivity(compare(*inputs()), offsets)


@pytest.mark.parametrize('change', ['schema', 'unknown_association', 'missing_span', 'missing_inputs'])
def test_missing_inputs_or_unknown_association_do_not_silently_fallback(change):
    baseline = compare_bracket(*bracket_inputs())
    if change == 'schema':
        baseline['schema'] = 'other-report'
    elif change == 'unknown_association':
        baseline['temporal_association']['method'] = 'other-method'
    elif change == 'missing_span':
        del baseline['temporal_association']['maximum_span_ns']
    else:
        del baseline['receiver_capture']
    with pytest.raises(ValueError):
        assess_time_sensitivity(baseline, [NS])


@pytest.mark.parametrize('available', [False, True])
def test_cli_offline_hashes_failure_reports_and_refuses_overwrite(monkeypatch, tmp_path, available):
    from pnt.__main__ import main
    from pnt import time_witness

    witness, capture = inputs()
    if not available:
        del capture['records'][0]['capture_id']
    source, output = tmp_path / 'comparison.json', tmp_path / 'sensitivity.json'
    source.write_text(json.dumps(compare(witness, capture)), encoding='utf-8')
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('offline sensitivity accessed network'))
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', str(source), '--offset-ns', str(-NS),
                                   '--output', str(output)])
    if available:
        main()
    else:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['source']['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert [case['utc_claim_offset_ns'] for case in report['offset_cases']] == [0, -NS]
    assert assess_time_sensitivity(report['baseline'], [-NS]) == {
        key: value for key, value in report.items() if key != 'source'}
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert output.read_bytes() == original


def test_android_time_sensitivity_runs_with_only_standard_library(tmp_path):
    from pnt.tests.test_android_time import inputs as android_inputs, compare as android_compare

    witness, raw, _, _ = android_inputs(bracket=True)
    source, output = tmp_path / 'comparison.json', tmp_path / 'sensitivity.json'
    source.write_text(json.dumps(android_compare(witness, raw, bracket_span_ns=200 * MS)), encoding='utf-8')
    script = """
import sys
class BlockOptional:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in ('numpy', 'scipy', 'hatanaka', 'OpenSSL', 'cryptography'):
            raise ImportError('optional dependency blocked: ' + fullname)
sys.meta_path.insert(0, BlockOptional())
from pnt.time_sensitivity import assess_time_sensitivity
from pnt.__main__ import main
main()
"""
    result = subprocess.run([sys.executable, '-c', script, 'time-sensitivity', str(source),
                             '--offset-ns', str(NS), '--output', str(output)], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['offset_cases'][1]['bracket_status_counts'] == {'INCONSISTENT_WITH_WITNESS': 8}
