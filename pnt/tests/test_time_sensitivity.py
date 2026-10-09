"""Interval limits and retained failures, using synthetic UTC/NTS cases."""

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from pnt.tests.test_gnss_time import MS, NS, COUNTER, inputs, compare, bracket_inputs, compare_bracket, utc_packet
from pnt.time_sensitivity import assess_time_sensitivity
from pnt.time_witness import compare_claim


def multi_epoch_inputs():
    """Three synthetic UTC epochs, each inside an adjacent NTS bracket."""
    witness, capture = bracket_inputs()
    records, attempts = [], []
    for seconds in range(3):
        record = copy.deepcopy(capture['records'][0])
        record['packet_hex'] = utc_packet(seconds * NS).hex()
        for name in ('receipt_start_monotonic_ns', 'receipt_end_monotonic_ns'):
            record[name] += seconds * NS
        records.append(record)
        for original in witness['attempts']:
            attempt = copy.deepcopy(original)
            for name in ('send_monotonic_ns', 'receive_monotonic_ns',
                         'server_receive_unix_ns', 'server_transmit_unix_ns'):
                attempt['exchange'][name] += seconds * NS
            attempts.append(attempt)
    witness['attempts'], capture['records'] = attempts, records
    return witness, capture


@pytest.mark.parametrize('offset', [-100 * MS, 100 * MS])
def test_constant_offset_is_locally_unobservable_but_external_control_separates(offset):
    baseline = compare_bracket(*multi_epoch_inputs())
    original = copy.deepcopy(baseline)
    report = assess_time_sensitivity(baseline, [offset], local_counter_resolution_ns=1)
    zero, shifted = report['offset_cases']
    assert zero['paired_pattern_counts']['NEITHER_INCONSISTENT'] == 2
    assert shifted['paired_pattern_counts']['EXTERNAL_ONLY_INCONSISTENT'] == 2
    assert shifted['paired_record_indices_by_pattern']['INSUFFICIENT_EVIDENCE'] == [0]
    assert shifted['record_pattern_counts']['ALL_INCONSISTENT'] == 3
    assert dict(baseline_pattern='NEITHER_INCONSISTENT', case_pattern='EXTERNAL_ONLY_INCONSISTENT', records=2) in shifted['paired_transition_counts']
    # Absolute offsets cannot alter a relative-clock measurement, even its gap.
    assert shifted['local_comparisons'][1]['claim_minus_local_prediction_ns'] == zero['local_comparisons'][1]['claim_minus_local_prediction_ns']
    assert shifted['local_comparisons'][2]['separation_ns'] == zero['local_comparisons'][2]['separation_ns'] == 0
    assert report['local_control']['absolute_utc_origin'] == 'UNKNOWN'
    assert baseline == original


def test_step_is_visible_to_both_controls_without_reanchoring_after_the_jump():
    baseline = compare_bracket(*multi_epoch_inputs())
    onset = COUNTER + NS + 50 * MS  # Exactly the second reported event midpoint.
    report = assess_time_sensitivity(baseline, [100 * MS], local_counter_resolution_ns=1,
                                     onset_monotonic_ns=onset)
    case = report['offset_cases'][1]
    assert case['applied_offset_ns_by_record'] == [0, 100 * MS, 100 * MS]
    assert case['paired_record_indices_by_pattern']['BOTH_INCONSISTENT'] == [1, 2]
    assert case['local_comparisons'][2]['anchor_source_index'] == 0
    assert case['local_comparisons'][2]['separation_ns'] > 90 * MS
    assert report['perturbation_profile']['onset_monotonic_ns'] == onset


@pytest.mark.parametrize('offset,pattern,external', [
    (-10 * MS, 'LOCAL_ONLY_INCONSISTENT', 'ALL_NOT_DISTINGUISHABLE'),
    (10 * MS, 'BOTH_INCONSISTENT', 'ALL_INCONSISTENT')])
def test_small_steps_retain_asymmetric_external_limits_and_local_only_cases(offset, pattern, external):
    baseline = compare_bracket(*multi_epoch_inputs())
    report = assess_time_sensitivity(baseline, [offset], local_counter_resolution_ns=1,
                                     onset_monotonic_ns=COUNTER + NS)
    case = report['offset_cases'][1]
    assert case['paired_record_indices_by_pattern'][pattern] == [1, 2]
    assert case['record_indices_by_pattern'][external] == ([0, 1, 2] if offset < 0 else [1, 2])


def test_bad_initial_anchor_retains_local_only_disagreement_on_unchanged_later_epochs():
    witness, capture = multi_epoch_inputs()
    capture['records'][0]['packet_hex'] = utc_packet(NS).hex()
    report = assess_time_sensitivity(compare_bracket(witness, capture), [0], local_counter_resolution_ns=1)
    case = report['offset_cases'][0]
    assert case['paired_record_indices_by_pattern']['LOCAL_ONLY_INCONSISTENT'] == [1, 2]
    assert case['record_indices_by_pattern']['ALL_INCONSISTENT'] == [0]
    assert case['local_comparisons'][1]['anchor_source_index'] == 0
    assert dict(baseline_pattern='LOCAL_ONLY_INCONSISTENT', case_pattern='LOCAL_ONLY_INCONSISTENT', records=2) in case['paired_transition_counts']


def test_local_control_does_not_use_external_time_or_authentication_status():
    witness, capture = multi_epoch_inputs()
    baseline = compare_bracket(witness, capture)
    reference = assess_time_sensitivity(baseline, [100 * MS], local_counter_resolution_ns=1)
    for attempt in witness['attempts']:
        attempt['status'] = 'WITNESS_UNAVAILABLE'
        attempt['reason'] = 'synthetic outage'
        del attempt['exchange']
    missing = assess_time_sensitivity(compare_bracket(witness, capture), [100 * MS], local_counter_resolution_ns=1)
    for original, outage in zip(reference['offset_cases'], missing['offset_cases']):
        assert original['local_comparisons'] == outage['local_comparisons']
        assert outage['paired_pattern_counts']['INSUFFICIENT_EVIDENCE'] == 3
    assert missing['status'] == 'INSUFFICIENT_EVIDENCE'


def test_external_disagreement_cannot_be_counted_as_external_only_gain():
    witness, capture = multi_epoch_inputs()
    for original in list(witness['attempts']):
        other = copy.deepcopy(original)
        other['server'] = other['exchange']['server'] = 'conflicting-endpoint'
        for name in ('server_receive_unix_ns', 'server_transmit_unix_ns'):
            other['exchange'][name] += NS
        witness['attempts'].append(other)
    report = assess_time_sensitivity(compare_bracket(witness, capture), [0], local_counter_resolution_ns=1)
    assert report['offset_cases'][0]['paired_record_indices_by_pattern']['EXTERNAL_DISAGREEMENT'] == [1, 2]
    assert report['offset_cases'][0]['paired_pattern_counts']['EXTERNAL_ONLY_INCONSISTENT'] == 0


@pytest.mark.parametrize('change', ['invalid_record', 'different_capture', 'reordered_counter'])
def test_local_quality_boundaries_break_the_segment_visibly(change):
    witness, capture = multi_epoch_inputs()
    if change == 'invalid_record':
        capture['records'][1] = {}
    elif change == 'different_capture':
        capture['records'][1]['capture_id'] = 'different-boot'
    else:
        capture['records'][1], capture['records'][2] = capture['records'][2], capture['records'][1]
    report = assess_time_sensitivity(compare_bracket(witness, capture), [0], local_counter_resolution_ns=1)
    local = report['offset_cases'][0]['local_comparisons']
    assert local[2]['status'] == 'INSUFFICIENT_EVIDENCE'
    if change == 'reordered_counter':
        assert 'reordered' in local[2]['reason']
    else:
        assert 'anchor' in local[2]['reason']


def test_hardware_discontinuity_and_repeated_epoch_do_not_manufacture_elapsed_support():
    from pnt.tests.test_android_time import inputs as android_inputs, compare as android_compare

    witness, raw, _, _ = android_inputs(bracket=True)
    report = assess_time_sensitivity(android_compare(witness, raw, bracket_span_ns=200 * MS),
                                     [NS], local_counter_resolution_ns=1)
    assert report['offset_cases'][1]['local_status_counts'] == {'INSUFFICIENT_EVIDENCE': 8}
    baseline = compare_bracket(*multi_epoch_inputs())
    # The pure local control consumes decoded receiver metadata, never NTS.
    from pnt.time_sensitivity import _local_elapsed_checks
    rows = baseline['records']
    for index, row in enumerate(rows):
        row['receiver_utc']['hardware_clock_discontinuity_count'] = index
    local = _local_elapsed_checks(rows, [r['claim'] for r in rows], counter_resolution_ns=1, rate_error_ppm=100)
    assert all(r['status'] == 'INSUFFICIENT_EVIDENCE' for r in local)


@pytest.mark.parametrize('options', [dict(local_counter_resolution_ns=0), dict(local_counter_resolution_ns=True),
                                    dict(onset_monotonic_ns=-1), dict(onset_monotonic_ns=1.5)])
def test_invalid_local_or_step_parameters_rejected(options):
    with pytest.raises(ValueError):
        assess_time_sensitivity(compare(*inputs()), [NS], **options)


def test_local_interval_edges_include_error_of_both_epochs_and_counter_quantization():
    from pnt.time_sensitivity import _local_elapsed_checks

    rows = [dict(source_index=i, receiver_utc={}) for i in range(2)]
    claims = [dict(capture_id='synthetic', counter_clock='synthetic-counter', source='synthetic',
                   unix_ns=1000, error_ns=7, start_monotonic_ns=0, end_monotonic_ns=0),
              dict(capture_id='synthetic', counter_clock='synthetic-counter', source='synthetic',
                   unix_ns=2021, error_ns=10, start_monotonic_ns=1000, end_monotonic_ns=1000)]
    check = _local_elapsed_checks(rows, claims, counter_resolution_ns=2, rate_error_ppm=0)
    assert check[1]['local_predicted_utc_interval']['upper_unix_ns'] == 2011
    assert check[1]['status'] == 'NOT_DISTINGUISHABLE'  # Claim lower edge touches 2011.
    claims[1]['unix_ns'] += 1
    check = _local_elapsed_checks(rows, claims, counter_resolution_ns=2, rate_error_ppm=0)
    assert check[1]['status'] == 'INCONSISTENT_LOCAL_CONTINUITY'
    assert check[1]['separation_ns'] == 1


def test_overlapping_epoch_brackets_allow_negative_physical_elapsed_time():
    from pnt.time_sensitivity import _local_elapsed_checks

    rows = [dict(source_index=i, receiver_utc={}) for i in range(2)]
    claims = [dict(capture_id='synthetic', counter_clock='synthetic-counter', source='synthetic',
                   unix_ns=1000, error_ns=0, start_monotonic_ns=100, end_monotonic_ns=200),
              dict(capture_id='synthetic', counter_clock='synthetic-counter', source='synthetic',
                   unix_ns=970, error_ns=0, start_monotonic_ns=150, end_monotonic_ns=250)]
    check = _local_elapsed_checks(rows, claims, counter_resolution_ns=1, rate_error_ppm=0)
    assert check[1]['local_predicted_utc_interval']['lower_unix_ns'] == 948
    assert check[1]['status'] == 'NOT_DISTINGUISHABLE'


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
    report = assess_time_sensitivity(baseline, [-NS, NS], local_counter_resolution_ns=1)
    assert report['baseline'] == baseline
    for case in report['offset_cases']:
        assert case['record_pattern_counts']['INSUFFICIENT_EVIDENCE'] == 8
        assert case['bracket_status_counts'] == {'INSUFFICIENT_EVIDENCE': 8}
        assert case['local_status_counts'] == {'INSUFFICIENT_EVIDENCE': 8}


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


@pytest.mark.parametrize('paired', [False, True])
def test_android_time_sensitivity_runs_with_only_standard_library(tmp_path, paired):
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
    options = ['--local-counter-resolution-ns', '1', '--onset-monotonic-ns', '0'] if paired else []
    result = subprocess.run([sys.executable, '-c', script, 'time-sensitivity', str(source),
                             '--offset-ns', str(NS), '--output', str(output), *options], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['offset_cases'][1]['bracket_status_counts'] == {'INCONSISTENT_WITH_WITNESS': 8}
    if paired:
        assert report['offset_cases'][1]['local_status_counts'] == {'INSUFFICIENT_EVIDENCE': 8}


@pytest.mark.parametrize('available', [False, True])
def test_cli_paired_step_is_offline_replayable_and_retains_unknown_alignment(monkeypatch, tmp_path, available):
    from pnt.__main__ import main
    from pnt import time_witness

    witness, capture = multi_epoch_inputs()
    if not available:
        for record in capture['records']:
            del record['capture_id']
    baseline = compare_bracket(witness, capture)
    source, output = tmp_path / 'comparison.json', tmp_path / 'paired.json'
    source.write_text(json.dumps(baseline), encoding='utf-8')
    onset = COUNTER + NS
    monkeypatch.setattr(time_witness, 'probe', lambda *a, **k: pytest.fail('offline paired test accessed network'))
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', str(source), '--offset-ns', str(100 * MS),
                                   '--local-counter-resolution-ns', '1', '--onset-monotonic-ns', str(onset),
                                   '--output', str(output)])
    if available:
        main()
    else:
        with pytest.raises(SystemExit) as error:
            main()
        assert error.value.code == 2
    report = json.loads(output.read_text(encoding='utf-8'))
    assert assess_time_sensitivity(report['baseline'], [100 * MS], local_counter_resolution_ns=1,
                                    onset_monotonic_ns=onset) == {k: v for k, v in report.items() if k != 'source'}
    if available:
        assert report['offset_cases'][1]['paired_pattern_counts']['BOTH_INCONSISTENT'] == 2
    else:
        assert report['offset_cases'][1]['paired_pattern_counts']['INSUFFICIENT_EVIDENCE'] == 3
    original = output.read_bytes()
    with pytest.raises(SystemExit):
        main()
    assert output.read_bytes() == original
