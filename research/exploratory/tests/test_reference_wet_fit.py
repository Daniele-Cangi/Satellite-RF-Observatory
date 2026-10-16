"""Reference-only wet response, full-chain checks and scoring chronology."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from research.exploratory import reference_wet_fit as study
from research.exploratory.tests.test_reference_state_validation import poison_products, Forbidden


def test_real_wet_recalibration_excludes_candidate_products_rf_and_future():
    _, data = study.baseline.read_inputs()
    weather = study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    station, endpoint = 'ALGO00CAN', 36060.
    nominal = study.clock_coefficients(study.baseline.calibration_environment(data, 'G05', weather), station, endpoint)
    def arc():
        return {'stations': [station], 'endpoint_gpst_s': endpoint, 'clock_mean': np.array([nominal])}
    first, second = arc(), arc()
    expected = study.attach_wet_response(data, 'G05', [first], weather)
    poisoned = poison_products(data, 'G05')
    for epochs in poisoned['observations'].values():
        for epoch in epochs:
            for q in list(epoch['if_code_m']):
                if q == 'G05' or epoch['time_s'] > endpoint:
                    epoch['if_code_m'][q] = Forbidden()
    for item in poisoned['phase']['stations'].values():
        for row in item['rows']:
            if row['reference'] == 'G05' or row['time_s'] > endpoint:
                row['code_m'] = row['phase_m'] = Forbidden()
    actual = study.attach_wet_response(poisoned, 'G05', [second], weather)
    assert actual == expected
    np.testing.assert_array_equal(first['wet_clock_response'], second['wet_clock_response'])
    # Check the full reference calibrator with a smaller derivative step, not
    # just the final target fit with a synthetic clock displacement.
    half = []
    for z in (-study.STEP_M/2, study.STEP_M/2):
        env = study.baseline.calibration_environment(data, 'G05', study.ShiftedWetWeather(weather, z))
        half.append(study.clock_coefficients(env, station, endpoint))
    derivative = (half[1]-half[0])/study.STEP_M
    np.testing.assert_allclose(derivative, first['wet_clock_response'][0], rtol=2e-3, atol=2e-6)
    assert first['wet_clock_response'][0, 0] < -1.
    assert abs(first['wet_clock_response'][0, 1]) > 1e-5


def test_all_fits_and_forecasts_precede_scoring_without_historical_state_seeds(monkeypatch):
    events = []
    monkeypatch.setattr(study.baseline, 'read_inputs', lambda: ({}, {'plan': {'references': ['G05', 'G06']}}))
    monkeypatch.setattr(study.baseline, 'build_arcs', lambda data, q, weather: (
        [{'candidate': q}, {'candidate': q}], [{'status': 'PREPARED'}]))
    monkeypatch.setattr(study, 'attach_wet_response', lambda *args: [])
    monkeypatch.setattr(study, 'linear_information', lambda *args: {})
    monkeypatch.setattr(study, 'predict', lambda *args: [])
    monkeypatch.setattr(study, 'calibration_check', lambda *args: {})
    def fit(arcs, **kwargs):
        assert set(kwargs) == {'progress'}
        events.append('fit '+arcs[0]['candidate'])
        return {'status': 'BRANCH_SEARCH_INCOMPLETE', 'state_ecef_m_m_s': np.zeros(6)}
    monkeypatch.setattr(study.dynamic_fit, 'fit', fit)
    def score(data, candidate, predictions):
        assert events[:4] == ['fit G05', 'fit G05', 'fit G06', 'fit G06']
        events.append('score '+candidate)
        return {}
    monkeypatch.setattr(study.baseline, 'score_rf', score)
    monkeypatch.setattr(study.baseline, 'oracle', lambda *args: None)
    monkeypatch.setattr(study.baseline, 'state_errors', lambda *args: {})
    result = study.run()
    assert len(events) == 8
    assert result['all_predictions_before_scoring'] and not result['wet_prior_used']
    assert result['fit_status_counts']['free_station_wet'] == {'BRANCH_SEARCH_INCOMPLETE': 2}


def test_perturbed_calibration_rejection_is_not_replaced_by_a_nominal_clock():
    environment = (lambda *args: {'status': 'REJECTED'}, lambda *args: {'status': 'ESTIMATED', 'rate_m_s': 0.}, None)
    with pytest.raises(ValueError, match='reference calibration rejected'):
        study.clock_coefficients(environment, 'A', 36060.)


def test_stored_result_keeps_support_provenance_and_replays_excluded_scores():
    path = study.baseline.BASE/'results/reference_wet_fit_v1.json'
    raw, data = study.baseline.read_inputs()
    result = json.loads(path.read_bytes())
    assert result['input_sha256'] == {k: hashlib.sha256(v).hexdigest() for k, v in raw.items()}
    root = study.baseline.BASE.parents[1]
    for source, wanted in result['source_sha256'].items():
        assert hashlib.sha256((root/source).read_bytes()).hexdigest() == wanted
    previous = json.loads((study.baseline.BASE/'results/reference_state_validation_v3.json').read_bytes())
    assert set(result['candidates']) == set(data['plan']['references'])
    assert result['fit_status_counts'] == {v: {'INSUFFICIENT_PREPARED_ARCS': 17, 'BRANCH_SEARCH_INCOMPLETE': 5}
        for v in ('fixed_vmf3', 'free_station_wet')}
    assert sum(w['status'] == 'PREPARED' for c in result['candidates'].values() for w in c['windows']) == 63
    assert not any(result[k] for k in ['candidate_products_used_in_own_fit', 'g12_state_accessed', 'oracle_tuning',
        'new_confirmation', 'physical_covariance_qualified', 'production_floors_changed', 'wet_prior_used'])
    for candidate, record in result['candidates'].items():
        assert len(record['windows']) == 20
        for actual, old in zip(record['windows'], previous['candidates'][candidate]['windows'], strict=True):
            # As in the existing snapshot tests, LAPACK can return different
            # duplicate/interior roots. Keep every new root in the artifact;
            # compare the actual support/mask, not bit-identical root metadata.
            assert {k: v for k, v in actual.items() if k != 'rf_geometry'} == {
                k: v for k, v in old.items() if k != 'rf_geometry'}
            if 'rf_geometry' in actual:
                assert actual['rf_geometry']['status'] == old['rf_geometry']['status']
                if actual['status'] == 'PREPARED':
                    assert all(sum(b['exterior'] for b in s['branches']) == 1
                               for s in actual['rf_geometry']['snapshots'])
                    np.testing.assert_allclose(actual['rf_geometry']['elevation_deg'],
                        old['rf_geometry']['elevation_deg'], rtol=0, atol=1e-8)
        for name, variant in record['variants'].items():
            prediction = json.dumps(variant['rf_predictions'], separators=(',', ':'), allow_nan=False).encode()
            assert hashlib.sha256(prediction).hexdigest() == variant['prediction_sha256']
            assert study.baseline.score_rf(data, candidate, variant['rf_predictions']) == variant['rf_evaluation']
            fit = variant['fit']
            if 'state_ecef_m_m_s' not in fit:
                continue
            assert fit['residual_threshold_p'] == .01 and fit['branch_failures']
            arcs = [{'endpoint_gpst_s': w['start_gpst_s']+60} for w in record['windows'] if w['status'] == 'PREPARED']
            replay = study.baseline.state_errors(fit, arcs, study.baseline.oracle(data, candidate))
            assert replay['summary']['BEYOND_ALL_TRAINING']['count'] == 1
            for actual, stored in zip(replay['rows'], variant['state_evaluation']['rows'], strict=True):
                assert actual['position_error_m'] == pytest.approx(stored['position_error_m'], abs=1e-4)
                assert actual['velocity_error_m_s'] == pytest.approx(stored['velocity_error_m_s'], abs=1e-7)
            variance = variant['information']['conditional_weak_variance_by_observation_family_m2']
            assert sum(variance.values()) == pytest.approx(variant['information']['weak_position_sigma_m']**2, rel=1e-5)
            if name == 'fixed_vmf3':
                old = previous['candidates'][candidate]['fit']
                np.testing.assert_allclose(fit['state_ecef_m_m_s'], old['state_ecef_m_m_s'], atol=1e-4, rtol=0)
            else:
                assert variant['calibration_check']['physical_domain_status'] == 'NEGATIVE_TOTAL_ZENITH_WET'
                assert variant['calibration_check']['negative_total_wet_stations']


def test_negative_wet_domain_and_full_calibration_disagreement_remain_visible(monkeypatch):
    from research.kinematic.synthetic import receiver_positions
    data = {'plan': {'date_gpst': '2026-09-05'}}
    arcs = [{'stations': ['A'], 'endpoint_gpst_s': 36060.,
        'stations_m': receiver_positions()[:1], 'clock_mean': np.zeros((1, 3)),
        'wet_clock_response': np.array([[-2., .001, .0002]])}]
    fit = {'station_zenith_wet_correction_m': {'A': -.2}}
    monkeypatch.setattr(study.baseline, 'calibration_environment', lambda *args: None)
    monkeypatch.setattr(study, 'clock_coefficients', lambda *args: np.array([.5, 0., 0.]))
    class Weather:
        def evaluate(self, *args):
            return [1., 1., 2.3, .1]
    checked = study.calibration_check(data, 'G05', arcs, fit, Weather())
    assert checked['negative_total_wet_stations'] == ['A']
    assert checked['physical_domain_status'] == 'NEGATIVE_TOTAL_ZENITH_WET'
    assert checked['minimum_total_zenith_wet_m']['A'] == pytest.approx(-.1)
    assert checked['rows'][0]['exact_minus_linear_clock_coefficients'][0] == pytest.approx(.1)
    assert fit['station_zenith_wet_correction_m']['A'] == -.2
