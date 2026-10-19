"""Partial-coordinate information, transfer support and admission boundaries."""
from copy import deepcopy

import numpy as np
import pytest

from research.kinematic import masked_prediction as predictor, gnss_combinations
from research.kinematic.tests.test_network_closures import reference_rows
from research.exploratory.reference_network_clocks import native


def test_partial_update_uses_other_channel_and_matches_scalar_gaussian():
    model = {'mean_m': np.zeros(2), 'loading_m': np.array([1., 2.]),
             'rho_30s': 0., 'process_variance': 1.,
             'observation_variance_m2': np.array([1., 1.])}
    state, count = predictor.filter_states(model, [[np.nan, 3.]], [0.])
    assert count == [1]
    assert state[0] == pytest.approx(6. / 5.)
    ablated, count = predictor.filter_states(model, [[np.nan, 3.]], [0.], whole_row=True)
    assert count == [0] and ablated[0] == 0.


def test_shared_mode_transfers_to_hidden_channel_without_retraining():
    rng = np.random.default_rng(924)
    times = np.arange(100) * 30.
    state = np.sin(np.arange(100) / 9.)
    loading = np.array([.02, -.03, .04])
    values = state[:, None] * loading + rng.normal(0., .0005, (100, 3))
    model = predictor.fit_prefix(values[:60], times[:60])
    hidden = values.copy()
    hidden[60:, 0] = np.nan
    predicted, _ = predictor.filter_states(model, hidden, times)
    ablated, _ = predictor.filter_states(model, hidden, times, whole_row=True)
    def mse(z):
        estimate = model['mean_m'][0] + z[60:] * model['loading_m'][0]
        return np.mean((estimate - values[60:, 0]) ** 2)
    assert mse(predicted) < .1 * mse(ablated)
    # No observations across a long gap: restart, not stale-state carryover.
    reset, _ = predictor.filter_states(model, np.vstack([values[0], [np.nan] * 3]), [0., 300.])
    assert reset[-1] == 0.


def test_missing_prefix_is_not_completed_as_an_arbitrary_source():
    with pytest.raises(ValueError, match='prefix'):
        predictor.fit_prefix(np.full((20, 3), np.nan), np.arange(20) * 30.)
    with pytest.raises(ValueError, match='mode'):
        predictor.fit_prefix(np.zeros((20, 3)), np.arange(20) * 30.)


def test_native_estimator_never_decodes_held_values_or_gf_segments():
    rows = reference_rows()
    for row in rows:
        row.update(wet_mapping=1.2 + .1 * np.sin(row['time_s'] / 200. + ord(row['station']) + ord(row['reference'])),
                   zenith_wet_m=.2)
        row['phase_m'] += .002 * (ord(row['station']) - 65) * np.sin(row['time_s'] / 140.)
    first = predictor.prepare_future_links(rows, 'TARGET', gnss_combinations.assumed_endpoint_covariance())
    assert first['model_status'] == 'PREDICTIVE_RESIDUAL_MODEL'
    class Forbidden:
        def __float__(self):
            raise AssertionError('held measurement decoded')
    changed = deepcopy(rows)
    for row in changed:
        if ((row['station'], row['reference']) in set(map(tuple, first['baseline']['held_links']))
                and row['time_s'] > first['baseline']['training_stop_s']):
            for key in ('code_m', 'phase_m', 'mw_m', 'geometry_free_phase_m'):
                row[key] = Forbidden()
            row['segment'] = 'forbidden-full-data-segment'
    second = predictor.prepare_future_links(changed, 'TARGET', gnss_combinations.assumed_endpoint_covariance())
    for label in first['variants']:
        assert native(first['variants'][label]) == native(second['variants'][label])
        assert len(first['variants'][label]['predictions']) == first['baseline']['withheld_row_count']
    # Candidate rejection must precede numeric access.
    with pytest.raises(ValueError, match='candidate'):
        predictor.prepare_future_links([{'reference':'TARGET', 'time_s':Forbidden()}], 'TARGET', None)
