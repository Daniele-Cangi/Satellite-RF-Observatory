"""Supported GPS Raw software challenge; not RF or physical budget validation."""
import copy
import json
from decimal import Decimal

import pytest

from pnt.android_raw import WEEK_NS, _gps_row, shift_android_raw_clock_capture
from pnt.gnss_time import compare_receiver_capture
from pnt.tests.test_android_time import inputs, compare, MS, NS
from pnt.tests.test_time_sensitivity_sessions import session
from pnt.tests.test_time_sensitivity import multi_epoch_inputs
from pnt.time_sensitivity import assess_time_sensitivity, assess_time_sensitivity_sessions


def challenge(source, offsets=(-100 * MS, 100 * MS), **options):
    return assess_time_sensitivity(source, android_raw_offsets_ns=offsets,
                                   local_counter_resolution_ns=1, **options)


@pytest.mark.parametrize('offset', [-100 * MS, 100 * MS])
@pytest.mark.parametrize('tow', [50 * MS, WEEK_NS - 50 * MS])
def test_week_wrap_preserves_parsed_range_and_shifts_actual_utc(offset, tow):
    witness, raw, _, _ = inputs()
    values = raw['records'][0]['source_values']
    rx = (int(values['TimeNanos']) - int(values['FullBiasNanos'])) % WEEK_NS
    delta = (tow + 70 * MS) % WEEK_NS - rx
    for row in raw['records']:
        v = row['source_values']
        v['FullBiasNanos'] = str(int(v['FullBiasNanos']) - delta)
        v['ReceivedSvTimeNanos'] = str(tow)
        v['BiasNanos'] = '0.25'
    original = compare(witness, raw)
    before = copy.deepcopy(original)
    derived, verification = shift_android_raw_clock_capture(original['receiver_capture'], offset)
    replay = compare_receiver_capture(witness, derived, utc_error_ns=MS, utc_error_source='synthetic')
    assert original == before
    for old, new, check in zip(original['records'], replay['records'], verification['checks']):
        assert new['claim']['unix_ns'] - old['claim']['unix_ns'] == offset
        assert new['claim']['start_monotonic_ns'] == old['claim']['start_monotonic_ns']
        assert new['claim']['error_ns'] == old['claim']['error_ns']
        assert check['status'] == 'PSEUDORANGE_PRESERVED'
    for old, new in zip(original['receiver_capture']['records'], derived['records']):
        a, b = old['source_values'], new['source_values']
        assert 0 <= int(b['ReceivedSvTimeNanos']) < WEEK_NS
        assert {k: v for k, v in a.items() if k not in ('FullBiasNanos', 'ReceivedSvTimeNanos')} == {
            k: v for k, v in b.items() if k not in ('FullBiasNanos', 'ReceivedSvTimeNanos')}
        normalized = _gps_row(b, new['source_line'])
        assert normalized['pseudorange_m'] == _gps_row(a, old['source_line'])['pseudorange_m']
        assert Decimal(normalized['receiver_gpst_ns']) - Decimal(_gps_row(a, old['source_line'])['receiver_gpst_ns']) == offset
    assert derived['android_intake']['original_source'] == original['receiver_capture']['android_intake']['source']
    assert 'source' not in derived['android_intake']


def test_replay_retains_inputs_failures_and_actual_derivatives_without_stored_verdicts():
    source = session('raw-challenge', repeats=2)
    source['witness_report']['attempts'].append(dict(server='failed-endpoint', status='TIMEOUT'))
    unusable = copy.deepcopy(source['receiver_capture']['records'][0])
    unusable['intake_status'] = 'UNSUPPORTED_GPS_SIGNAL'
    unusable['source_values']['CodeType'] = 'unsupported'
    source['receiver_capture']['records'].append(unusable)
    source.update(records=[], coverage={}, status='INVENTED_VERDICT')
    before = copy.deepcopy(source)
    report = challenge(source)
    assert source == before
    assert report['assumptions']['rf_attack_simulation'] is False
    assert report['assumptions']['calibrated'] is False
    assert report['assumptions']['source_admission_recomputed'] is True
    zero, *cases = report['offset_cases']
    for case in cases:
        assert case['local_status_counts'] == zero['local_status_counts']
        assert case['record_pattern_counts']['ALL_INCONSISTENT'] == 6
        assert case['record_pattern_counts']['INSUFFICIENT_EVIDENCE'] == 1
        assert case['paired_pattern_counts']['EXTERNAL_ONLY_INCONSISTENT'] == 4
        assert case['derived_receiver_capture']['records'][-1] == unusable
        assert report['baseline']['witness_report']['attempts'][-1]['status'] == 'TIMEOUT'
        replay = assess_time_sensitivity(dict(source, receiver_capture=case['derived_receiver_capture']), [0],
                                         local_counter_resolution_ns=1)
        for field in ('local_comparisons', 'comparison_status_counts', 'bracket_status_counts',
                      'paired_pattern_counts', 'record_indices_by_pattern'):
            assert replay['offset_cases'][0][field] == case[field]
    assert challenge(report['baseline']) == report


def test_native_claim_failure_is_recomputed_instead_of_forcing_old_admission():
    source = session('out-of-range')
    report = challenge(source, [4 * 10**18])
    assert report['offset_cases'][1]['record_pattern_counts']['INSUFFICIENT_EVIDENCE'] == 3
    assert report['offset_cases'][1]['applied_offset_ns_by_record'] == [None] * 3
    assert report['offset_cases'][0]['record_pattern_counts']['ALL_NOT_DISTINGUISHABLE'] == 3


@pytest.mark.parametrize('options', [dict(offsets_ns=[MS]), dict(drift_rates_ppm=[1]),
    dict(onset_monotonic_ns=1), dict(evidence_availability=True), dict(android_clock_diagnostics=True)])
def test_conflicting_modes_fail_closed(options):
    with pytest.raises(ValueError, match='cannot be combined'):
        assess_time_sensitivity(session('conflict'), android_raw_offsets_ns=[MS], **options)


@pytest.mark.parametrize('offsets', [[], [1, 1], [True], [1.5]])
def test_explicit_distinct_integer_offsets_required(offsets):
    with pytest.raises(ValueError):
        challenge(session('invalid'), offsets)


def test_non_android_and_forged_normalization_are_rejected():
    witness, capture = multi_epoch_inputs()
    generic = compare_receiver_capture(witness, capture, utc_error_ns=MS, utc_error_source='synthetic')
    with pytest.raises(ValueError, match='Android'):
        challenge(generic)
    source = session('forged')
    source['receiver_capture']['records'][0]['source_values']['CodeType'] = 'unsupported'
    with pytest.raises(ValueError, match='disagrees'):
        challenge(source)


def test_session_summary_and_cli_reuse_fixed_original_support(monkeypatch, tmp_path):
    from pnt.__main__ import main
    sources = [session('first'), session('second')]
    report = assess_time_sensitivity_sessions(sources, android_raw_offsets_ns=iter([-100 * MS, 100 * MS]),
                                             local_counter_resolution_ns=1)
    assert report['totals']['common_clock_groups'] == 4
    assert report['rules']['perturbation'] == 'SUPPORTED_GPS_RAW_CLOCK_AND_TRANSMIT_TOW'
    for case in report['totals']['offset_cases'][1:]:
        assert case['methods']['external']['common_clock_groups'] == {'INCONSISTENT': 4}
        assert case['methods']['local']['common_clock_groups'] == {'NOT_DISTINGUISHABLE': 4}
    paths = [tmp_path / 'first.json', tmp_path / 'second.json']
    for path, source in zip(paths, sources):
        path.write_text(json.dumps(source), encoding='utf-8')
    output = tmp_path / 'report.json'
    monkeypatch.setattr('sys.argv', ['pnt', 'time-sensitivity', *(str(p) for p in paths),
        '--android-raw-clock-offset-ns', str(-100 * MS), '--android-raw-clock-offset-ns', str(100 * MS),
        '--local-counter-resolution-ns', '1', '--output', str(output)])
    main()
    cli = json.loads(output.read_text())
    cli.pop('sources')
    assert cli == report


def test_missing_association_bound_never_becomes_qualified_or_usable():
    witness, raw, _, _ = inputs()
    source = compare(witness, raw, epoch_alignment_error_ns=None, epoch_alignment_source=None)
    report = challenge(source)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    for case in report['offset_cases']:
        assert case['record_pattern_counts']['INSUFFICIENT_EVIDENCE'] == len(raw['records'])
        assert case['paired_pattern_counts']['INSUFFICIENT_EVIDENCE'] == len(raw['records'])
    assert report['assumptions']['calibrated'] is False


def test_partial_session_boundary_and_duplicate_identity_are_still_enforced():
    source = session('same-original')
    envelope = dict(schema='pnt-android-session-report-v1', comparison=source, issues=[],
                    snapshot=dict(session_complete=False))
    with pytest.raises(ValueError, match='closed Android'):
        challenge(envelope)
    with pytest.raises(ValueError, match='duplicate'):
        assess_time_sensitivity_sessions([source, copy.deepcopy(source)], android_raw_offsets_ns=[MS],
                                         local_counter_resolution_ns=1)


def test_zero_derivative_is_exact_and_clock_integer_overflow_fails_closed():
    source = session('zero-and-overflow')
    capture = source['receiver_capture']
    derived, checks = shift_android_raw_clock_capture(capture, 0)
    assert derived == capture
    assert len(checks['checks']) == len(capture['records'])
    with pytest.raises(ValueError, match='integer range'):
        challenge(source, [2**63])


@pytest.mark.parametrize('status', ['UNSUPPORTED_GPS_SIGNAL', 'UNRESOLVED_GPS_TRANSMIT_TIME',
                                    'INVALID_GPS_MEASUREMENT', 'INVALID_CONSTELLATION'])
def test_imported_unusable_label_cannot_hide_a_normalizable_gps_row(status):
    source = session('stale-unusable-label')
    source['receiver_capture']['records'][1]['intake_status'] = status
    before = copy.deepcopy(source)
    with pytest.raises(ValueError, match='disagrees'):
        challenge(source)
    assert source == before


def test_rechallenging_retained_derivative_preserves_original_digest():
    source = session('rechallenged')
    first = challenge(source, [100 * MS])['offset_cases'][1]['derived_receiver_capture']
    before = copy.deepcopy(first)
    replay = compare_receiver_capture(source['witness_report'], first, utc_error_ns=MS,
                                     utc_error_source='synthetic', bracket_span_ns=200 * MS)
    second = challenge(replay, [-100 * MS])['offset_cases'][1]['derived_receiver_capture']
    assert first == before
    assert second['android_intake']['original_source'] == source['receiver_capture']['android_intake']['source']
    assert 'source' not in second['android_intake']
    assert second['records'] == source['receiver_capture']['records']


@pytest.mark.parametrize('field,value,status', [
    ('CodeType', 'unsupported', 'UNSUPPORTED_GPS_SIGNAL'),
    ('State', '1', 'UNRESOLVED_GPS_TRANSMIT_TIME'),
    ('FullBiasNanos', '', 'MISSING_FULL_BIAS'),
    ('Svid', '99', 'INVALID_GPS_MEASUREMENT'),
    ('ConstellationType', 'NaN', 'INVALID_CONSTELLATION'),
])
def test_genuinely_unusable_rows_reparse_and_remain_unchanged(field, value, status):
    source = session('genuine-unusable')
    row = source['receiver_capture']['records'][1]
    row['source_values'][field] = value
    row['intake_status'] = status
    before = copy.deepcopy(source)
    result = challenge(source)
    assert source == before
    for case in result['offset_cases']:
        assert case['raw_clock_challenge']['checks'][1]['status'] == 'UNCHANGED_UNUSABLE_ROW'
        assert 1 in case['record_indices_by_pattern']['INSUFFICIENT_EVIDENCE']
        if case['utc_claim_offset_ns']:
            assert case['derived_receiver_capture']['records'][1] == row


def test_original_digest_is_not_replaced_by_later_source_metadata():
    capture = session('root-source')['receiver_capture']
    original = copy.deepcopy(capture['android_intake']['source'])
    capture['android_intake']['original_source'] = original
    capture['android_intake']['source'] = {'sha256': 'different-later-source'}
    derived, _ = shift_android_raw_clock_capture(capture, MS)
    assert derived['android_intake']['original_source'] == original
    assert 'source' not in derived['android_intake']
