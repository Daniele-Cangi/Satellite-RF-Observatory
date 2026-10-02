"""Comparison behavior: disjoint calibration, physical code modes and retained gaps."""

import json
import subprocess
import sys

import pytest

from pnt.benchmark import compare
from pnt.tests.test_fixed_site import (DAY, TIME, POSITIONS, constellation,
                                      nav_text, observations, rinex)


def recording(tmp_path, *, missing=None, evaluation_shift=0.):
    navigation = constellation()
    by_receiver = {name: {} for name in POSITIONS}
    for index, time in enumerate(range(TIME, TIME + 540, 30)):
        values = observations(navigation, time=time)
        for name, codes in values.items():
            # Small original code variability gives nonzero development
            # thresholds; it is neither an RF benign label nor a noise budget.
            delta = .02 * ((index % 6) - 2) * {'local': 1., 'A': .5, 'B': -.3}[name]
            codes['G02'] = tuple(code + delta for code in codes['G02'])
            if name == 'local' and time >= TIME + 360:
                codes['G04'] = tuple(code + evaluation_shift for code in codes['G04'])
            if missing != (name, time):
                by_receiver[name][time] = codes
    paths = {name: tmp_path / f'{name}.rnx' for name in POSITIONS}
    for name, path in paths.items():
        path.write_text(rinex(name, POSITIONS[name], by_receiver[name]), encoding='ascii')
    nav = tmp_path / 'broadcast.n'
    nav.write_text(nav_text(navigation), encoding='ascii')
    return paths, nav


def run(paths, nav, **options):
    return compare(paths['local'], {name: path for name, path in paths.items() if name != 'local'},
                   nav, DAY.isoformat(), start_s=TIME, train_stop_s=TIME + 180,
                   calibration_stop_s=TIME + 360, stop_s=TIME + 540,
                   minimum_calibration=5, amplitudes_m=(20.,), direction_ecef=(0., 1., 0.), **options)


def case(report, name):
    return next(row for row in report['cases'] if row['scenario'] == name)


def test_raw_code_modes_preserve_the_clock_blind_mode_and_reveal_remote_contamination(tmp_path):
    paths, nav = recording(tmp_path)
    report = run(paths, nav)
    assert report['status'] == 'EXPLORATORY_COMPARISON'
    assert report['original']['calibration']['evaluated_epochs'] == 6
    assert report['original']['evaluation']['evaluated_epochs'] == 6
    assert len(report['cases']) == 5
    original = report['original']['epochs'][-1]
    clock = case(report, 'local_common_clock_ramp')['epochs'][-1]
    assert clock['clock_change_m']['local'] == pytest.approx(20., abs=.001)
    assert clock['clock_change_m']['A'] == 0.
    assert clock['clock_change_m']['B'] == 0.
    for mode in ('local', 'combined'):
        assert clock['scores_m'][mode] == pytest.approx(original['scores_m'][mode], abs=.001)
    shared = case(report, 'shared_satellite_ramp')['epochs'][-1]
    assert shared['scores_m']['local'] > 19.
    assert shared['scores_m']['network'] > 19.
    assert shared['scores_m']['combined'] == pytest.approx(original['scores_m']['combined'], abs=.001)
    local = case(report, 'local_satellite_ramp')['epochs'][-1]
    assert local['scores_m']['combined'] > 19.
    assert local['scores_m']['network'] == original['scores_m']['network']
    fault = case(report, 'reference_satellite_ramp')['epochs'][-1]
    assert fault['scores_m']['local'] == original['scores_m']['local']
    assert fault['scores_m']['reference_disagreement'] > 19.
    assert fault['exceedances']['reference_disagreement']
    assert case(report, 'local_geometry_ramp')['epochs'][-1]['scores_m']['local'] > 1.
    assert report['assessments']['recorded_RF_detection_gain'] == 'NOT_ASSESSED'
    assert report['assessments']['absolute_time'] == 'INSUFFICIENT_EVIDENCE'
    json.dumps(report, allow_nan=False)


def test_evaluation_poisoning_cannot_change_baselines_thresholds_or_training_selected_satellite(tmp_path):
    paths, nav = recording(tmp_path)
    first = run(paths, nav)
    paths, nav = recording(tmp_path, evaluation_shift=500.)
    poisoned = run(paths, nav)
    assert poisoned['baselines'] == first['baselines']
    assert poisoned['thresholds_m'] == first['thresholds_m']
    assert poisoned['parameters']['satellite'] == first['parameters']['satellite']
    assert poisoned['original']['evaluation']['exceedances']['local'] == 6


def test_missing_reference_retains_each_original_and_perturbed_epoch(tmp_path):
    paths, nav = recording(tmp_path, missing=('B', TIME + 390))
    report = run(paths, nav)
    assert report['original']['evaluation']['requested_epochs'] == 6
    assert report['original']['evaluation']['evaluated_epochs'] == 5
    for row in report['cases']:
        assert [epoch['gpst_s'] for epoch in row['epochs']] == list(range(TIME + 360, TIME + 540, 30))
        assert row['summary']['requested_epochs'] == 6
        assert row['summary']['evaluated_epochs'] == 5
        failed = row['epochs'][1]
        assert failed['status'] == 'INSUFFICIENT_EVIDENCE'
        assert 'B' in failed['fit_failures']


def test_unobserved_perturbation_is_inconclusive_instead_of_counted_as_a_miss(tmp_path):
    paths, nav = recording(tmp_path)
    report = run(paths, nav, satellite='G32')
    for name in ('local_satellite_ramp', 'shared_satellite_ramp', 'reference_satellite_ramp'):
        row = case(report, name)
        assert row['summary']['status_counts'] == {'PERTURBATION_OUTSIDE_MATCHED_SUPPORT': 6}
        assert row['summary']['evaluated_epochs'] == 0
        assert row['equal_observed_original_exceedance_counts'] is None


def test_insufficient_calibration_retains_original_coverage_without_fabricating_thresholds(tmp_path):
    paths, nav = recording(tmp_path)
    report = compare(paths['local'], {'A': paths['A'], 'B': paths['B']}, nav, DAY.isoformat(),
                     start_s=TIME, train_stop_s=TIME + 180, calibration_stop_s=TIME + 210,
                     stop_s=TIME + 540)
    assert report['status'] == 'INSUFFICIENT_CALIBRATION'
    assert report['thresholds_m'] is None
    assert report['cases'] == []
    assert len(report['original']['epochs']) == 18
    assert all('exceedances' not in row for row in report['original']['epochs'])


@pytest.mark.parametrize('failure', ['support_change', 'model_failure'])
def test_changed_support_and_perturbation_failure_cannot_reuse_original_decisions(tmp_path, monkeypatch, failure):
    from pnt import benchmark
    paths, nav = recording(tmp_path)
    original = benchmark.perturb
    def changed_support(values, scenario, *args):
        if scenario == 'local_satellite_ramp' and failure == 'model_failure':
            raise ValueError('injected propagation failure')
        changed = original(values, scenario, *args)
        if scenario == 'local_satellite_ramp':
            changed['local'].pop('G08')
        return changed
    monkeypatch.setattr(benchmark, 'perturb', changed_support)
    report = run(paths, nav)
    row = case(report, 'local_satellite_ramp')
    expected = 'MATCHED_SUPPORT_CHANGED' if failure == 'support_change' else 'PERTURBATION_FAILED'
    assert row['summary']['status_counts'] == {expected: 6}
    assert row['summary']['evaluated_epochs'] == 0
    assert row['original_on_same_support']['requested_epochs'] == 0
    assert all('exceedances' not in epoch for epoch in row['epochs'])
    if failure == 'model_failure':
        assert all(epoch['reason'] == 'injected propagation failure' for epoch in row['epochs'])


@pytest.mark.parametrize('options', [{'proportion': float('nan')}, {'amplitudes_m': (float('inf'),)},
                                     {'direction_ecef': (0., 0., 0.)}, {'satellite': 'G33'}])
def test_invalid_comparison_parameters_fail_before_loading_sources(options):
    with pytest.raises(ValueError):
        compare('missing', {}, 'missing', DAY.isoformat(), start_s=TIME, train_stop_s=TIME + 180,
                calibration_stop_s=TIME + 360, stop_s=TIME + 540, **options)


def test_a_single_evaluation_epoch_cannot_claim_both_ramp_endpoints():
    with pytest.raises(ValueError, match='at least two epochs'):
        compare('missing', {}, 'missing', DAY.isoformat(), start_s=TIME, train_stop_s=TIME + 180,
                calibration_stop_s=TIME + 360, stop_s=TIME + 390)


def test_cli_comparison_runs_the_real_pipeline_and_preserves_existing_report(tmp_path):
    paths, nav = recording(tmp_path)
    output = tmp_path / 'comparison.json'
    command = [sys.executable, '-m', 'pnt', 'compare', DAY.isoformat(), str(paths['local']), str(nav),
               '--reference', 'A=' + str(paths['A']), '--reference', 'B=' + str(paths['B']),
               '--start', str(TIME), '--train-stop', str(TIME + 180),
               '--calibration-stop', str(TIME + 360), '--stop', str(TIME + 540),
               '--minimum-calibration', '5', '--amplitude', '20', '--output', str(output)]
    completed = subprocess.run(command, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    first = output.read_bytes()
    assert json.loads(first)['status'] == 'EXPLORATORY_COMPARISON'
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert output.read_bytes() == first
