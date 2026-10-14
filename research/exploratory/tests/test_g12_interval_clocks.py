"""Same-cohort training boundaries for the interval-clock development fit."""
from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from research.exploratory import g12_interval_clocks as study


def test_real_training_uses_interval_references_but_no_target_or_clock_future():
    _, data = study.read_inputs()
    cases, selection = study.shared.cohort(data['hour'], 'code_phase')
    expected = study.training_arcs(data, cases, study.SCENARIOS[0])
    class Forbidden:
        def __float__(self):
            raise AssertionError('excluded numeric value used')
        def __array__(self, *args, **kwargs):
            raise AssertionError('historical geometry used')
    poisoned = deepcopy(data)
    excluded = {tuple(k) for k in selection['withheld_endpoint_keys']}
    for s, item in poisoned['target']['stations'].items():
        for row in item.get('rows', []):
            if (s, row['time_s']) in excluded:
                row['code_m'] = row['phase_m'] = Forbidden()
    for row in poisoned['reference_clock']['phase_clock_rates']:
        if (row['station'], row['time_s']) in excluded:
            row['estimators']['median']['rate_m_s'] = Forbidden()
    for case in cases:
        case['propagation_m'] = case['clock_prior'] = Forbidden()
        case['fits']['code_phase']['state'] = Forbidden()
    actual = study.training_arcs(poisoned, cases, study.SCENARIOS[0])
    assert len(actual) == 8
    for a, b in zip(actual, expected, strict=True):
        for key in ['codes_m', 'rates_m_s', 'clock_mean', 'receiver_clock_basis', 'covariance', 'stations_m']:
            np.testing.assert_array_equal(a[key], b[key])
        rates = np.diff(study.clock_basis(study.shared.TAGS)@a['clock_mean'].T, axis=0)/30.
        index, _ = study.diagnostic.reference_index(data['reference_clock'])
        reference = [[index[s, a['endpoint_gpst_s']+t]['estimators']['median']['rate_m_s']
                      for s in a['stations']] for t in (-30., 0.)]
        np.testing.assert_allclose(rates, reference, atol=1e-13)


def test_target_reference_and_bad_calibration_rejected_before_target_access():
    _, data = study.read_inputs()
    cases, _ = study.shared.cohort(data['hour'], 'code_phase')
    data['target'] = {}
    original = data['reference_clock']['held_out_reference_diagnostics'][0]['reference']
    data['reference_clock']['held_out_reference_diagnostics'][0]['reference'] = 'G12'
    with pytest.raises(ValueError, match='before numeric access'):
        study.training_arcs(data, cases, study.SCENARIOS[0])
    data['reference_clock']['held_out_reference_diagnostics'][0]['reference'] = original
    data['baseline']['calibrations'][cases[0]['stations'][0]]['status'] = 'REJECTED'
    with pytest.raises(ValueError, match='before target decoding'):
        study.training_arcs(data, cases, study.SCENARIOS[0])


def test_numerical_failures_keep_all_eight_forecast_slots():
    _, data = study.read_inputs()
    cases, _ = study.shared.cohort(data['hour'], 'code_phase')
    arcs = study.training_arcs(data, cases, study.SCENARIOS[0])
    predictions = study.predict({'status': 'NUMERICAL_FAILURE'}, arcs, None)
    assert len(predictions) == 8 and all(p['status'] == 'FIT_UNAVAILABLE' for p in predictions)
    _, summary = study.shared.score(predictions, cases, {}, 'code_phase')
    assert summary['window_status_counts'] == {'UNSCORED': 8}
    assert study.observability({'status': 'NUMERICAL_FAILURE'}) == {'status': 'FIT_UNAVAILABLE'}


def test_stored_real_result_retains_all_variants_failures_and_replayable_scores():
    raw, data = study.read_inputs()
    result = json.loads((study.shared.BASE/'results/g12_interval_clocks_v1.json').read_bytes())
    assert result['input_sha256'] == {k: study.shared.digest(v) for k, v in raw.items()}
    for module in [study, study.shared, study.diagnostic, study.dynamic_fit, study.clock_observations, study.dynamics]:
        p = Path(module.__file__)
        assert result['source_sha256'][p.name] == study.shared.digest(p.read_bytes())
    assert not any(result[k] for k in ['target_orbit_used', 'oracle_error_used', 'prior_target_state_used',
                                     'new_confirmation', 'physical_covariance_qualified', 'production_floors_changed'])
    assert len(result['cohort']['retained_outcomes']) == 40
    cases, _ = study.shared.cohort(data['hour'], 'code_phase')
    assert set(result['variants']) == {s+'_'+f for s in study.SCENARIOS for f, _ in study.shared.FORCES}
    for name, variant in result['variants'].items():
        fit = variant['fit']
        assert fit['status'] == 'BRANCH_SEARCH_INCOMPLETE'
        assert fit['candidate_count'] == 1 and len(fit['branch_failures']) == 1
        assert 'exterior-Earth' in fit['branch_failures'][0]['reason']
        assert fit['residual_dof'] == 165 and fit['residual_threshold_p'] == .01
        prediction_bytes = json.dumps(variant['predictions'], separators=(',', ':'), allow_nan=False).encode()
        assert study.shared.digest(prediction_bytes) == variant['frozen_prediction_sha256']
        rows, summary = study.shared.score(variant['predictions'], cases, data['target'], 'code_phase')
        assert rows == variant['withheld'] and summary == variant['summary']
        assert summary['ALL']['pair_count'] == 40 and summary['BEYOND_ALL_TRAINING']['pair_count'] == 5
        force = 'central_j2' if name.endswith('central_j2') else 'central'
        previous = data['fit']['variants']['code_phase_'+force]
        assert variant['v4_same_cohort']['summary'] == previous['summary']
        assert previous['fit']['status'] == 'MODEL_REJECTED'
        assert summary['ALL']['phase']['rms'] > previous['summary']['ALL']['phase']['rms']
        assert variant['observability']['position_1sigma_axes_m'][-1] > variant['v4_same_cohort']['observability']['position_1sigma_axes_m'][-1]
