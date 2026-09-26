import pytest

from research.exploratory import pnt_local_network as study
from research.exploratory.pseudotarget_reference import receiver_clock


def rows():
    result = []
    for time in range(10):
        for station, value in [('A', 1. + (time % 2) * 0.1),
                               ('B', 0.5), ('C', 0.7)]:
            result.append({'station': station, 'pseudo_target': 'G01',
                           'time_s': time, 'status': 'ADMITTED',
                           'models': {'zero': {'status': 'EVALUATED', 'error_m': value}}})
    return result


def test_simultaneous_witnesses_and_missing_status():
    data = rows()
    data.append({'station': 'B', 'pseudo_target': 'G02', 'time_s': 0,
                 'status': 'PSEUDO_TARGET_NOT_ADMITTED', 'models': {}})
    paired, failures = study.samples(data, 'A', ['A', 'B', 'C'])
    assert len(paired) == 10
    assert paired[0]['network_m'] == pytest.approx(0.6)
    assert paired[0]['combined_m'] == pytest.approx(0.4)
    assert failures['PSEUDO_TARGET_NOT_ADMITTED'] == 1
    data = [r for r in data if not (r['station'] == 'C' and r['time_s'] == 9)]
    paired, failures = study.samples(data, 'A', ['A', 'B', 'C'])
    assert len(paired) == 9
    assert failures['INSUFFICIENT_SIMULTANEOUS_WITNESSES'] == 1


def test_local_attack_network_blind_shared_error_cancels_and_time_unobserved():
    report = study.analyze(rows(), 'A', ['A', 'B', 'C'], train_before_s=5,
                           minimum_training_per_satellite=3, proportion=0.8,
                           perturbations_m=(10.,))
    clean = {mode: report['controls'][mode]['clean_test_alerts'] for mode in study.MODES}
    cases = {p['scenario']: p['test_alerts'] for p in report['perturbations']}
    assert cases['local_satellite_code']['local'] == 5
    assert cases['local_satellite_code']['network'] == clean['network']
    assert cases['local_satellite_code']['combined'] == 5
    assert cases['shared_satellite_code']['combined'] == clean['combined']
    assert cases['local_common_clock'] == clean


def test_receiver_clock_fit_absorbs_ideal_common_code_offset():
    references = ['G01', 'G02', 'G03', 'G04']
    codes = dict(zip(references, [100., 101., 99., 100.])) | {'P': 105.}
    plan = {'minimum_remaining_references': 4, 'maximum_clock_iterations': 4,
            'clock_closure_tolerance_m': 1e-9, 'maximum_reference_rms_m': 20.,
            'maximum_reference_abs_m': 50., 'maximum_split_clock_m': 30.}
    def residual(values):
        clock = receiver_clock(values, references, 'P', lambda *args: 0.,
                               dict.fromkeys(references, 0.), plan)
        assert clock['status'] == 'EVALUATED'
        return values['P'] - clock['clock_m']
    assert residual({key: value + 10. for key, value in codes.items()}) == pytest.approx(residual(codes))


def test_test_values_cannot_recalibrate_threshold_and_invalid_rows_fail():
    original = study.analyze(rows(), 'A', ['A', 'B', 'C'], train_before_s=5,
                             minimum_training_per_satellite=3)
    poisoned = rows()
    for row in poisoned:
        if row['station'] == 'A' and row['time_s'] >= 5:
            row['models']['zero']['error_m'] += 100.
    changed = study.analyze(poisoned, 'A', ['A', 'B', 'C'], train_before_s=5,
                            minimum_training_per_satellite=3)
    assert changed['controls']['local']['threshold_m'] == original['controls']['local']['threshold_m']
    with pytest.raises(ValueError, match='duplicate'):
        study.samples(rows() + [rows()[0]], 'A', ['A', 'B', 'C'])
    bad = rows()
    bad[0]['models']['zero']['error_m'] = float('nan')
    with pytest.raises(ValueError, match='nonfinite'):
        study.samples(bad, 'A', ['A', 'B', 'C'])


def test_tracked_exposed_source_has_full_rotation_and_no_target_fit():
    result = study.run()
    assert result['source_row_count'] == 9394
    assert result['test_count'] > 0
    assert len(result['station_rotations']) == 6
    assert result['source_status_counts']['PSEUDO_TARGET_NOT_ADMITTED'] == 5452
