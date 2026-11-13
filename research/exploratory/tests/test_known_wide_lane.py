import pytest

from research.exploratory import known_wide_lane as known
from research.exploratory import zero_baseline_dd_code as code


def row(identifier, mean, halfwidth, **fields):
    return {'id': identifier, 'mean_cycles': mean, 'halfwidth_cycles': halfwidth, **fields}


def test_bias_intersection_preserves_signed_interval_and_boundary_integer():
    anchors = [row('a', -2.75, .125, integer=-3), row('b', 8.375, .125, integer=8)]
    calibration = known.bias_interval(anchors)
    assert calibration['interval_cycles'] == pytest.approx([.25, .375])
    trial = row('test', -3.5, .125)
    assert known.predict(trial, calibration, 0.)['range'] == [-4, -4]
    assert known.predict(trial, calibration, None)['status'] == 'UNBOUNDED_BIAS'


def test_validation_cannot_reuse_an_anchor_or_read_its_label():
    anchor = row('same', .95, .02, integer=0)
    group = {'id': 'group', 'anchors': [anchor], 'transfer_bound_cycles': .04,
             'validation': [row('same', 3.98, .03)]}
    with pytest.raises(ValueError, match='disjoint'):
        known.predictions([group])
    group['validation'] = [row('new', 3.98, .03, integer=3)]
    with pytest.raises(ValueError, match='separate truth'):
        known.predictions([group])
    group['validation'] = [row('new', 3.98, .03)]
    frozen = known.predictions([group])
    with pytest.raises(ValueError, match='every validation'):
        known.score(frozen, {})
    with pytest.raises(ValueError, match='must be an integer'):
        known.score(frozen, {'new': 3.0})


def test_forward_exercise_keeps_failed_transfers_and_abstentions():
    groups, truth = known.synthetic()
    frozen = known.predictions(groups)
    outcomes = known.score(frozen, truth)
    assert len(truth) == 384
    assert frozen[0]['calibration']['interval_cycles'][0] <= .95
    assert frozen[0]['calibration']['interval_cycles'][1] >= .95
    assert frozen[-2]['calibration']['status'] == 'INCONSISTENT_ANCHORS'
    assert {g['id']: g['counts']['calibrated'] for g in outcomes} == {
        'stable': {'CORRECT_FIX': 64},
        'broad_transfer': {'MULTIPLE': 64},
        'unknown_transfer': {'UNBOUNDED_BIAS': 64},
        'unmodelled_drift': {'WRONG_FIX': 64},
        'contradictory_calibration': {'UNBOUNDED_BIAS': 64},
        'no_anchor': {'UNBOUNDED_BIAS': 64},
    }
    assert outcomes[0]['counts']['zero_bias']['WRONG_FIX'] > 0


def test_zero_baseline_code_uses_signed_dd_and_preserves_missing_pairs():
    # Common satellite code ranges and a separable receiver term cancel in DD.
    times = range(0, 300, 30)
    left = {('G01', t): [21_000_004., 21_000_004.] for t in times}
    left.update({('G02', t): [23_000_003., 23_000_003.] for t in times})
    left.update({('G03', t): [25_000_003., 25_000_003.] for t in range(0, 270, 30)})
    right = {('G01', t): [21_000_000., 21_000_000.] for t in times}
    right.update({('G02', t): [23_000_000., 23_000_000.] for t in times})
    right.update({('G03', t): [25_000_000., 25_000_000.] for t in times})
    result = code.summarize(0, left, right)
    assert result['block_counts'] == {'complete': 1, 'partial': 2, 'missing': 462}
    full = result['rows'][0]
    assert full['pair'] == ['G01', 'G02']
    assert full['full'][0]['mean_cycles'] == pytest.approx(-1. / known.phase.WIDE_M)
    assert result['rows'][1]['partial'][0]['count'] == 9
