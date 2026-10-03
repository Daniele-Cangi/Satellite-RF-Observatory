"""Paired support, calibration isolation and the NAV-content blind mode."""

from dataclasses import replace
import gzip
import json
import subprocess
import sys

import pytest

from pnt.navigation_impact import compare_navigation
from pnt.tests.test_benchmark import recording
from pnt.tests.test_fixed_site import DAY, TIME, constellation, nav_text, rinex, POSITIONS, observations
from pnt.tests.test_navigation_witness import change


def run(paths, nav, cases, **options):
    return compare_navigation(paths['local'], nav, cases, {'W': nav}, DAY.isoformat(),
                              start_s=TIME, calibration_stop_s=TIME + 180, stop_s=TIME + 540,
                              minimum_calibration=5, **options)


def write_nav(tmp_path, name, navigation):
    path = tmp_path / (name + '.n')
    path.write_text(nav_text(navigation), encoding='ascii')
    return path


def test_common_nav_bias_adds_content_evidence_while_two_local_controls_remain_quiet(tmp_path):
    paths, nav = recording(tmp_path)
    biased = {sv: [replace(rows[0], af0_s=rows[0].af0_s + 2048 * 2**-31)]
              for sv, rows in constellation().items()}
    changed = write_nav(tmp_path, 'biased', biased)
    report = run(paths, nav, {'biased': (paths['local'], changed)})
    original, altered = report['cases']['original'], report['cases']['biased']
    assert report['status'] == 'EXPLORATORY_COMPARISON'
    assert report['parameters']['qualified_original_calibration_epochs'] == 5
    assert original['evaluation']['requested_epochs'] == altered['evaluation']['requested_epochs'] == 12
    assert altered['paired_evaluation']['comparable_epochs'] == 12
    assert altered['paired_evaluation']['witness_status_counts'] == {'DIFFERENT_FROM_EXTERNAL': 12}
    # Small numerical changes can cross a tight synthetic threshold. Retain
    # any such crossing instead of forcing a desired quiet-control outcome.
    assert altered['paired_evaluation']['witness_discordance_without_local_exceedance_epochs'] > 0
    final = altered['epochs'][-1]
    assert final['clock_change_from_original_m'] == pytest.approx(285.9049, abs=.005)
    assert final['max_residual_change_from_original_m'] < .005
    assert report['assessments']['recorded_RF_detection_gain'] == 'NOT_ASSESSED'
    assert original['external_files_equal_to_local_navigation'] == ['W']
    json.dumps(report, allow_nan=False)


def test_unchanged_nav_cannot_expose_a_range_manipulation_and_cases_do_not_tune_thresholds(tmp_path):
    paths, nav = recording(tmp_path)
    first = run(paths, nav, {'same': (paths['local'], nav)})
    original_bytes = paths['local'].read_bytes()
    altered_paths, _ = recording(tmp_path, evaluation_shift=500.)
    changed = tmp_path / 'changed.rnx'
    changed.write_bytes(altered_paths['local'].read_bytes())
    paths['local'].write_bytes(original_bytes)
    report = run(paths, nav, {'ranges': (changed, nav)})
    assert report['thresholds_m'] == first['thresholds_m']
    assert report['cases']['original'] == first['cases']['original']
    for row, base in zip(report['cases']['ranges']['epochs'], report['cases']['original']['epochs']):
        if row['gpst_s'] >= TIME + 360:
            assert row['exceedances']['residual_spread_m']
        else:
            assert row['local_exceedance'] == base['local_exceedance']
    assert report['cases']['ranges']['paired_evaluation']['witness_status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 12}


def test_original_evaluation_poisoning_does_not_change_calibration(tmp_path):
    paths, nav = recording(tmp_path)
    first = run(paths, nav, {'same': (paths['local'], nav)})
    paths, nav = recording(tmp_path, evaluation_shift=500.)
    second = run(paths, nav, {'same': (paths['local'], nav)})
    assert second['thresholds_m'] == first['thresholds_m']
    assert second['parameters'] == first['parameters']


def test_unchanged_file_is_identical_and_gzip_does_not_change_model_outcomes(tmp_path):
    paths, nav = recording(tmp_path)
    zipped = tmp_path / 'broadcast.n.gz'
    zipped.write_bytes(gzip.compress(nav.read_bytes()))
    report = run(paths, nav, {'gzip': (paths['local'], zipped)})
    for base, candidate in zip(report['cases']['original']['epochs'], report['cases']['gzip']['epochs']):
        assert candidate == base


def test_missing_observation_breaks_clock_continuity_and_never_bridges_the_gap(tmp_path):
    paths, nav = recording(tmp_path, missing=('local', TIME + 240))
    report = run(paths, nav, {'same': (paths['local'], nav)})
    rows = report['cases']['same']['epochs']
    assert rows[8]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert rows[9]['control_status'] == 'INSUFFICIENT_CLOCK_CONTINUITY'
    assert 'clock_step_m' not in rows[9]['scores_m']
    assert rows[9]['local_exceedance'] is None
    assert rows[10]['paired_status'] == 'COMPARABLE'
    assert report['cases']['same']['paired_evaluation']['status_counts'] == {'COMPARABLE': 10, 'INSUFFICIENT_CONTROLS': 2}


def test_changed_support_is_inconclusive_instead_of_comparing_a_smaller_constellation(tmp_path):
    paths, nav = recording(tmp_path)
    missing = constellation()
    del missing['G02']
    changed = write_nav(tmp_path, 'missing', missing)
    report = run(paths, nav, {'missing': (paths['local'], changed)})
    candidate = report['cases']['missing']
    assert candidate['evaluation']['fit_status_counts'] == {'EVALUATED': 12}
    assert candidate['paired_evaluation']['status_counts'] == {'SUPPORT_CHANGED': 12}
    assert candidate['paired_evaluation']['comparable_epochs'] == 0
    assert candidate['epochs'][-1]['excluded_satellites']['G02'] == 'MISSING_NAVIGATION'
    assert 'clock_change_from_original_m' not in candidate['epochs'][-1]


def test_all_unhealthy_nav_is_retained_as_failed_coverage_without_original_nav_fallback(tmp_path):
    paths, nav = recording(tmp_path)
    unhealthy = {sv: [replace(rows[0], sv_health=1)] for sv, rows in constellation().items()}
    changed = write_nav(tmp_path, 'unhealthy', unhealthy)
    report = run(paths, nav, {'unhealthy': (paths['local'], changed)})
    candidate = report['cases']['unhealthy']
    assert candidate['sources']['navigation']['model_record_status']['unhealthy_or_invalid_records'] == 8
    assert candidate['evaluation']['fit_status_counts'] == {'INSUFFICIENT_EVIDENCE': 12}
    assert {row['status'] for row in candidate['navigation_comparison']} == {'DIFFERENT_FROM_EXTERNAL'}
    assert candidate['evaluation']['witness_status_counts'] == {'INSUFFICIENT_EVIDENCE': 12}


def test_unmatched_issue_is_missing_evidence_even_if_local_geometry_fits(tmp_path):
    paths, nav = recording(tmp_path)
    navigation = {sv: [replace(rows[0], iode=(rows[0].iode + 1) % 256)]
                  for sv, rows in constellation().items()}
    changed = write_nav(tmp_path, 'issue', navigation)
    report = run(paths, nav, {'issue': (paths['local'], changed)})
    assert report['cases']['issue']['paired_evaluation']['witness_status_counts'] == {'INSUFFICIENT_EVIDENCE': 12}


def test_only_used_navigation_records_contribute_to_epoch_witness_diagnostics(tmp_path):
    paths, nav = recording(tmp_path)
    text = nav.read_text()
    changed = change(text, 0, 0, 1e-6)
    # G01 is outside this recording's code support; its retained mismatch
    # cannot create evidence for fitted satellites G02..G08.
    navigation = constellation()
    data = {time: observations(navigation, time=time)['local'] for time in range(TIME, TIME + 540, 30)}
    for codes in data.values():
        del codes['G01']
    paths['local'].write_text(rinex('local', POSITIONS['local'], data), encoding='ascii')
    changed_path = tmp_path / 'unused.n'
    changed_path.write_text(changed, encoding='ascii')
    report = run(paths, nav, {'unused': (paths['local'], changed_path)})
    case = report['cases']['unused']
    assert case['navigation_comparison'][0]['status'] == 'DIFFERENT_FROM_EXTERNAL'
    assert case['paired_evaluation']['witness_status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 12}


def test_model_filtering_preserves_original_source_indices_and_retains_unused_bad_records(tmp_path):
    paths, nav = recording(tmp_path)
    unused = {'G09': [replace(constellation()['G01'][0], satellite='G09', sv_health=1)]}
    text = nav_text(unused) + '\n'.join(nav.read_text().splitlines()[2:]) + '\n'
    candidate = tmp_path / 'unhealthy-prefix.n'
    candidate.write_text(text, encoding='ascii')
    report = run(paths, nav, {'prefix': (paths['local'], candidate)})
    case = report['cases']['prefix']
    assert case['navigation_comparison'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert case['epochs'][-1]['navigation_record_indices'] == {f'G{i:02d}': i for i in range(1, 9)}
    assert case['paired_evaluation']['witness_status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 12}


def test_clock_comparison_rejects_changed_support_at_previous_epoch_too(tmp_path):
    paths, nav = recording(tmp_path)
    data = {time: observations(constellation(), time=time)['local'] for time in range(TIME, TIME + 540, 30)}
    del data[TIME + 240]['G02']
    changed = tmp_path / 'support.rnx'
    changed.write_text(rinex('local', POSITIONS['local'], data), encoding='ascii')
    report = run(paths, nav, {'support': (changed, nav)})
    rows = report['cases']['support']['epochs']
    assert rows[8]['paired_status'] == 'SUPPORT_CHANGED'
    assert rows[9]['satellites'] == report['cases']['original']['epochs'][9]['satellites']
    assert rows[9]['paired_status'] == 'SUPPORT_CHANGED'
    assert rows[10]['paired_status'] == 'COMPARABLE'


def test_witness_conflicts_cannot_be_overruled_by_matching_local_and_majority_sources(tmp_path):
    paths, nav = recording(tmp_path)
    changed = tmp_path / 'witness.n'
    changed.write_text(change(nav.read_text(), 0, 0, 1e-6), encoding='ascii')
    report = compare_navigation(paths['local'], nav, {'same': (paths['local'], nav)},
                                {'A': nav, 'B': nav, 'C': changed}, DAY.isoformat(),
                                start_s=TIME, calibration_stop_s=TIME + 180, stop_s=TIME + 540,
                                minimum_calibration=5)
    assert report['cases']['same']['paired_evaluation']['witness_status_counts'] == {'RECORD_CONFLICT': 12}


def test_clock_fit_failures_are_retained_for_every_case(tmp_path, monkeypatch):
    paths, nav = recording(tmp_path)
    def failed(*args, **kwargs):
        raise ValueError('deliberate model failure')
    monkeypatch.setattr('pnt.navigation_impact.fit_clock', failed)
    report = run(paths, nav, {'same': (paths['local'], nav)})
    assert report['status'] == 'INSUFFICIENT_CALIBRATION'
    assert report['thresholds_m'] is None
    for case in report['cases'].values():
        assert len(case['epochs']) == 18
        assert case['evaluation']['fit_status_counts'] == {'MODEL_FAILED': 12}


@pytest.mark.parametrize('options', [{'minimum_calibration': True}, {'proportion': float('nan')},
                                    {'proportion': 0.}, {'proportion': 1.1}])
def test_invalid_calibration_parameters_are_rejected(tmp_path, options):
    paths, nav = recording(tmp_path)
    with pytest.raises(ValueError, match='calibration'):
        compare_navigation(paths['local'], nav, {'same': (paths['local'], nav)}, {'W': nav}, DAY.isoformat(),
                           start_s=TIME, calibration_stop_s=TIME + 180, stop_s=TIME + 540, **options)


def test_insufficient_original_calibration_retains_every_case_without_threshold_fallback(tmp_path):
    paths, nav = recording(tmp_path)
    report = compare_navigation(paths['local'], nav, {'same': (paths['local'], nav)}, {'W': nav}, DAY.isoformat(),
                                start_s=TIME, calibration_stop_s=TIME + 180, stop_s=TIME + 540)
    assert report['thresholds_m'] is None
    assert report['status'] == 'INSUFFICIENT_CALIBRATION'
    assert all(row['local_exceedance'] is None for case in report['cases'].values() for row in case['epochs'])


def test_different_receiver_marker_is_not_silently_treated_as_a_paired_case(tmp_path):
    paths, nav = recording(tmp_path)
    with pytest.raises(ValueError, match='same receiver'):
        run(paths, nav, {'other': (paths['A'], nav)})


def test_cli_reproducible_output_and_no_overwrite_or_duplicate_case_names(tmp_path):
    paths, nav = recording(tmp_path)
    output = tmp_path / 'report.json'
    command = [sys.executable, '-m', 'pnt', 'navigation-compare', DAY.isoformat(), str(paths['local']), str(nav),
               '--case', 'same', str(paths['local']), str(nav), '--witness', f'W={nav}',
               '--start', str(TIME), '--calibration-stop', str(TIME + 180), '--stop', str(TIME + 540),
               '--minimum-calibration', '5', '--output', str(output)]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text()) == run(paths, nav, {'same': (paths['local'], nav)})
    before = output.read_bytes()
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert output.read_bytes() == before
    duplicate = command[:-2] + ['--case', 'same', str(paths['local']), str(nav), '--output', str(tmp_path / 'duplicate.json')]
    assert subprocess.run(duplicate, capture_output=True).returncode == 2
    assert not (tmp_path / 'duplicate.json').exists()
