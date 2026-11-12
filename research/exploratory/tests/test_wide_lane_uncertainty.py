"""Uncertainty model identities and causal support at a held arc loss."""

import math

import pytest
from scipy.stats import t as student_t

from research.exploratory import reference_mw_stability as stability
from research.exploratory import wide_lane_uncertainty as uncertainty


def test_integer_support_propagates_bias_and_keeps_boundary_integers():
    support = uncertainty.integer_support
    assert support(1.01, .04, None)['status'] == 'UNBOUNDED_BIAS'
    assert support(1.01, .04, .1)['range'] == [1, 1]
    assert support(1.5, .5, 0.)['range'] == [1, 2]
    assert support(1.5, .1, .1)['status'] == 'EMPTY'
    with pytest.raises(ValueError, match='nonnegative bias'):
        support(1., .1, -.1)


def test_ar1_forecast_and_iid_limit_match_known_formulas():
    blocks = [{'start_s': 0, 'mean_cycles': 1.},
              {'start_s': 300, 'mean_cycles': 3.}]
    iid = uncertainty.fit_model(blocks, [600], 0.)
    assert iid['forecasts'][0]['halfwidth_95_cycles'] == pytest.approx(
        stability.block_model(blocks)['future_block_halfwidth_95_cycles'])
    ar1 = uncertainty.fit_model(blocks, [600], .5)
    assert ar1['mean_cycles'] == pytest.approx(2.)
    assert ar1['mean_se_cycles'] == pytest.approx(math.sqrt(3.))
    assert ar1['forecasts'][0]['mean_cycles'] == pytest.approx(2.5)
    assert ar1['forecasts'][0]['halfwidth_95_cycles'] == pytest.approx(
        student_t.ppf(.975, 1) * math.sqrt(3.75))


def test_prefix_is_frozen_and_held_loss_stops_all_models():
    plan = {'stations': ['A', 'B'], 'references': ['G01', 'G02'],
            'target_excluded': 'G12', 'start_gpst_s': 0, 'step_s': 30,
            'samples': 50, 'training_before_gpst_s': 900}
    rows = []
    for time in range(0, 1500, 30):
        for station, reference in uncertainty.endpoints(plan['stations'], plan['references']):
            witness = (station, reference) == ('A', 'G01')
            arc = None if witness and time == 1170 else 2 if witness and time > 1170 else 1
            rows.append({'station': station, 'reference': reference, 'time_s': time,
                         'arc': arc, 'status': 'ARC_BREAK' if arc is None else 'ARC_CONTINUES',
                         'mw_cycles': (1. + .02 * (time // 300)) if witness else 0.})
    frozen = uncertainty.prepare(plan, rows)
    assert len(frozen['records'][0]['prefix_blocks']) == 3
    assert len(frozen['held_block_starts_s']) == 2
    assert frozen == uncertainty.prepare(plan, [row for row in rows if row['time_s'] < 900])
    scored = uncertainty.score(frozen, rows, plan)
    assert scored['block_statuses'] == {'ARC_LOST': 1, 'AFTER_ARC_LOSS': 1}
    assert scored['records'][0]['blocks'][0]['loss']['time_s'] == 1170
    assert all(not counts for counts in scored['coverage'].values())
