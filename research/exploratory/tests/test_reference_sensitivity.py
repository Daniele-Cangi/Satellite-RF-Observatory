"""Development-input isolation and complete accounting of variant failures."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from research.exploratory import reference_sensitivity as study


ROOT = Path(__file__).resolve().parents[3]
ARCHIVE = ROOT/'experiments/positioning_g14_doy246_network'


def test_exclusion_preserves_original_measurements():
    source = [{'time_s': 0, 'if_code_m': {'G01': 12., 'G02': 14.}}]
    old = deepcopy(source)
    assert study.remove_reference(source, 'G01')[0]['if_code_m'] == {'G02': 14.}
    assert source == old


def test_input_loader_needs_no_oracle_or_historical_solution(tmp_path):
    (tmp_path/'estimation').mkdir()
    for name in ('admission_receipt.json', 'estimation/admitted.json', 'estimation/reference_only.rnx'):
        (tmp_path/name).write_bytes((ARCHIVE/name).read_bytes())
    admitted, context, navigation, hashes = study.load_inputs(tmp_path)
    assert context.target == 'G14' and context.target not in navigation
    assert admitted['stations'][admitted['withheld_station']]['target_if_codes_m'] is None
    assert len(hashes) == 2
    with (tmp_path/'estimation/admitted.json').open('ab') as output:
        output.write(b' ')
    with pytest.raises(ValueError, match='changed'):
        study.load_inputs(tmp_path)


def test_calibration_failures_do_not_turn_into_estimates():
    assert study.fit_variant({'fit_stations': ['A']}, None,
                              {'A': {'status': 'CALIBRATION_NOT_QUALIFIED'}}) == {'status': 'CALIBRATION_REJECTED'}


def test_failed_variants_are_kept_and_inputs_unchanged(monkeypatch):
    admitted, context, navigation, hashes = study.load_inputs(ARCHIVE)
    admitted['fit_stations'] = admitted['fit_stations'][:1]
    name = admitted['fit_stations'][0]
    for obs in admitted['stations'][name]['reference_observations']:
        obs['if_code_m'] = {'G01': 12., 'G02': 14.}
    original = deepcopy(admitted)
    monkeypatch.setattr(study, 'load_inputs', lambda path: (admitted, context, navigation, hashes))

    def calibrate(observations, *args):
        if 'G02' not in observations[0]['if_code_m']:
            raise RuntimeError('invented runtime error')
        refs = sorted(observations[0]['if_code_m'])
        return {'status': 'CALIBRATION_QUALIFIED' if len(refs) == 2 else 'CALIBRATION_NOT_QUALIFIED',
                'failures': [] if len(refs) == 2 else ['invented source rejection'],
                'epochs': [{'time_s': context.start_s, 'clock_m': 0., 'references': refs,
                            'rms_m': 1., 'split_clock_m': 1., 'ground_offset_m': 1.}]}

    monkeypatch.setattr(study, 'calibrate_station', calibrate)
    def fit(data, context, calibration):
        if calibration[name]['status'] != 'CALIBRATION_QUALIFIED':
            return {'status': 'CALIBRATION_REJECTED'}
        return {'status': 'ESTIMATED', 'xyz_m': [1., 2., 3.], 'B_m': 0., 'u0_relative_s': 0.}
    monkeypatch.setattr(study, 'fit_variant', fit)
    result = study.run('unused')
    assert result['case_count'] == 3
    assert result['status_counts'] == {'ESTIMATED': 1, 'CALIBRATION_REJECTED': 1, 'ENGINEERING_FAILURE': 1}
    assert all(row['displacement_from_baseline_m'] is None for row in result['cases'][1:])
    assert admitted == original


def test_saved_real_development_result_preserves_sources_and_denominator():
    result = json.loads((ROOT/'research/exploratory/results/g14_reference_sensitivity_v1.json').read_bytes())
    for name, expected in result['sources_sha256'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
    for name, expected in result['input_sha256'].items():
        assert hashlib.sha256((ARCHIVE/'estimation'/name).read_bytes()).hexdigest() == expected
    assert result['case_count'] == len(result['cases']) == sum(result['status_counts'].values())
    assert result['cases'][0]['excluded_reference'] is None
    assert len({row['excluded_reference'] for row in result['cases']}) == result['case_count']
    references = {sv for cal in result['cases'][0]['calibration'].values()
                  for epoch in cal['epochs'] for sv in epoch['references']}
    assert {row['excluded_reference'] for row in result['cases'][1:]} == references
    assert not result['target_orbit_accessed'] and not result['new_confirmation']
