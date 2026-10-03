"""Held-out transfer: known shared signal, local-only changes, drift and gaps."""

import json
import subprocess
import sys

import pytest

from pnt.benchmark import fit_baselines
from pnt.transfer import fit_transfer, reference_transfer, summarize_transfer, transfer_epoch
from pnt.tests.test_benchmark import recording
from pnt.tests.test_fixed_site import DAY, TIME


def epoch(time, local, remote, *, extra=False):
    satellites = ['G01', 'G02', 'G03', 'G04'] + (['G05'] if extra else [])
    fits = {name: {'clock_m': 0., 'satellite_residuals_m': {
        sv: value if sv == 'G01' else 0. for sv in satellites}}
        for name, value in (('local', local), ('A', remote), ('B', remote))}
    return {'gpst_s': time, 'excluded_satellites': {},
            'matched': {'status': 'EVALUATED', 'satellites': satellites, 'receiver_fits': fits}}


def trained():
    rows = [epoch(i * 30, 2. * v, v) for i, v in enumerate((-2., -1., 0., 1., 2.))]
    baselines = fit_baselines(rows, 5)
    return baselines, fit_transfer(rows, baselines, 5)


def run(paths, nav, **options):
    return reference_transfer(paths['local'], {'A': paths['A'], 'B': paths['B']}, nav,
                              DAY.isoformat(), start_s=TIME, train_stop_s=TIME + 180,
                              stop_s=TIME + 540, minimum_fit_epochs=5, **options)


def test_known_shared_signal_is_predicted_with_fixed_training_coefficient():
    baselines, fit = trained()
    assert fit['coefficient'] == 2.
    rows = [transfer_epoch(epoch(300 + i * 30, 2 * v, v), baselines, fit)
            for i, v in enumerate((3., 4., 5.))]
    summary = summarize_transfer(rows)
    assert summary['evaluated_epochs'] == 3
    assert summary['metrics']['fitted_transfer']['epoch_weighted_pair_rms_m'] == 0.
    assert summary['metrics']['fitted_transfer']['fractional_mse_reduction_vs_local'] == 1.
    assert summary['metrics']['unit_transfer']['fractional_mse_reduction_vs_local'] == .75
    assert summary['metrics']['fitted_transfer']['improved_epochs_vs_local'] == 3
    assert summary['by_scored_pair_count']['6']['epochs'] == 3


def test_local_only_change_survives_and_reversed_transfer_is_retained_as_worse():
    baselines, fit = trained()
    local_only = transfer_epoch(epoch(300, 20., 0.), baselines, fit)
    assert local_only['pair_errors_m']['G01/G02']['fitted_transfer'] == 20.
    assert local_only['transfer_metrics']['local'] == local_only['transfer_metrics']['fitted_transfer']
    drift = summarize_transfer([transfer_epoch(epoch(330, -6., 3.), baselines, fit)])
    assert drift['metrics']['fitted_transfer']['fractional_mse_reduction_vs_local'] == -3.
    assert drift['metrics']['fitted_transfer']['worsened_epochs_vs_local'] == 1
    assert fit['coefficient'] == 2.


def test_untrained_pairs_do_not_enter_any_method_denominator():
    baselines, fit = trained()
    row = transfer_epoch(epoch(300, 6., 3., extra=True), baselines, fit)
    assert row['unsupported_pair_count'] == 4
    assert len(row['scored_pairs']) == 6
    assert set(row['pair_errors_m']) == set(row['scored_pairs'])
    assert summarize_transfer([row])['by_scored_pair_count']['6']['epochs'] == 1


def test_training_weights_epochs_equally_when_pair_cardinality_changes():
    baselines = fit_baselines([epoch(0, 0., 0., extra=True)], 1)
    fit = fit_transfer([epoch(30, 2., 1.), epoch(60, 4., 1., extra=True)], baselines, 2)
    # Three of six pairs carry the first signal; four of ten carry the
    # second. Equal epoch weighting gives (1 + 1.6) / (.5 + .4).
    assert fit['coefficient'] == pytest.approx(26. / 9.)
    assert fit['coefficient'] != pytest.approx(22. / 7.)  # equal pair weighting


@pytest.mark.parametrize('failure', ['sample_count', 'no_variation'])
def test_unqualified_fit_has_no_silent_unit_or_zero_coefficient_fallback(failure):
    rows = [epoch(i * 30, float(i), 0.) for i in range(5)]
    baselines = fit_baselines(rows, 5)
    fit = fit_transfer(rows, baselines, 6 if failure == 'sample_count' else 5)
    expected = 'INSUFFICIENT_TRAINING' if failure == 'sample_count' else 'NO_REMOTE_TRAINING_VARIATION'
    assert fit['status'] == expected
    assert fit['coefficient'] is None
    row = transfer_epoch(epoch(300, 20., 5.), baselines, fit)
    assert row['status'] == expected
    assert 'transfer_metrics' not in row
    assert summarize_transfer([row])['evaluated_epochs'] == 0


def test_actual_parser_to_model_transfer_and_evaluation_poisoning_invariance(tmp_path):
    paths, nav = recording(tmp_path)
    original = run(paths, nav)
    paths, nav = recording(tmp_path, evaluation_shift=500.)
    changed = run(paths, nav)
    assert original['status'] == 'EXPLORATORY_TRANSFER'
    assert original['training']['evaluated_epochs'] == 6
    assert original['evaluation']['evaluated_epochs'] == 12
    assert changed['baselines'] == original['baselines']
    assert changed['fit'] == original['fit']
    assert changed['training'] == original['training']
    assert changed['evaluation']['metrics']['fitted_transfer']['epoch_weighted_pair_rms_m'] > 100.
    assert changed['assessments']['recorded_RF_detection_gain'] == 'NOT_ASSESSED'
    assert changed['assessments']['absolute_time'] == 'INSUFFICIENT_EVIDENCE'
    json.dumps(changed, allow_nan=False)


def test_missing_reference_retains_the_epoch_and_same_support_for_all_methods(tmp_path):
    paths, nav = recording(tmp_path, missing=('B', TIME + 390))
    report = run(paths, nav)
    assert report['evaluation']['requested_epochs'] == 12
    assert report['evaluation']['evaluated_epochs'] == 11
    missing = next(row for row in report['epochs'] if row['gpst_s'] == TIME + 390)
    assert missing['status'] == 'INSUFFICIENT_EVIDENCE'
    assert 'transfer_metrics' not in missing
    assert 'B' in missing['fit_failures']
    for row in report['epochs']:
        if 'pair_errors_m' in row:
            assert set(row['pair_errors_m']) == set(row['scored_pairs'])
            assert all(set(value) == {'local', 'unit_transfer', 'fitted_transfer'}
                       for value in row['pair_errors_m'].values())


@pytest.mark.parametrize('options', [{'minimum_training': 0}, {'minimum_fit_epochs': True}])
def test_invalid_sample_configuration_is_rejected_before_reading_inputs(options):
    with pytest.raises(ValueError, match='positive integer'):
        reference_transfer('absent', {}, 'absent', DAY.isoformat(), start_s=TIME,
                           train_stop_s=TIME + 180, stop_s=TIME + 360, **options)


def test_cli_writes_a_complete_report_and_refuses_overwrite(tmp_path):
    paths, nav = recording(tmp_path)
    output = tmp_path / 'transfer.json'
    command = [sys.executable, '-m', 'pnt', 'transfer', DAY.isoformat(), str(paths['local']), str(nav),
               '--reference', f"A={paths['A']}", '--reference', f"B={paths['B']}",
               '--start', str(TIME), '--train-stop', str(TIME + 180), '--stop', str(TIME + 540),
               '--minimum-fit-epochs', '5', '--output', str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    contents = output.read_bytes()
    assert json.loads(contents)['evaluation']['requested_epochs'] == 12
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode == 2
    assert 'output already exists' in repeated.stderr
    assert output.read_bytes() == contents
