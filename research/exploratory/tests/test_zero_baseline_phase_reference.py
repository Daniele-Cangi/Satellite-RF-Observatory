from itertools import product

import pytest

from research.exploratory import zero_baseline_phase_reference as study


def test_phase_label_requires_same_integer_at_both_extremes_on_both_bands():
    assert study.phase_label([[2.0, -3.01], [2.09, -2.91]]) == [2, -3]
    assert study.phase_label([[2.0, -3.0], [2.101, -3.0]]) is None
    assert study.phase_label([[2.0, -3.0], [3.0, -3.0]]) is None
    assert study.phase_label([[2.0, -.5]]) is None


def test_bias_and_mw_disagreement_without_using_code_in_anchor():
    pair = ('G01', 'G02')
    left = {key: {'reasons': [], 'fields': [20e6, 20e6, 100., 100.]}
            for key in product(pair, range(study.WINDOW_S))}
    right = {key: {'reasons': [], 'fields': [20e6, 20e6, 100., 100.]}
             for key in left}
    for time in range(study.WINDOW_S):
        left[pair[0], time]['fields'][2:] = [102.02, 99.01]
        if time < study.ANCHOR_S:
            left[pair[0], time]['reasons'] = ['MISSING_INVALID_C2W']
            left[pair[0], time]['fields'][1] = None
        else:
            left[pair[0], time]['fields'][:2] = [19_999_999.5] * 2
    scored = study.evaluate(pair, 0, left, right)
    assert scored['anchor_cycles'] == [2, -1]
    assert scored['held_mw_bias_cycles'] == pytest.approx(.01 + .5 * (-sum(study.MW_FIELD_ROW[:2])))
    assert scored['held_mw_nearest_integer'] == 4
    left[pair[0], study.ANCHOR_S]['fields'][2] += 1.
    assert study.evaluate(pair, 0, left, right)['status'] == 'HELD_PHASE_INCONSISTENT'
    left[pair[0], study.ANCHOR_S]['reasons'] = ['LOSS_OF_LOCK_L1C']
    flagged = study.evaluate(pair, 0, left, right)
    assert flagged['status'] == 'PHASE_GAP_OR_FLAG'
    assert flagged['held_unavailable_epochs'] == 1


def test_alignment_uses_external_satellites_and_physical_time_sign():
    pair = ('G01', 'G02')
    count = 5
    offset_s = .0004
    rate_hz = (1000., -2000.)
    true_cycles = [3., 6.]
    phases = [[cycle - offset_s * rate for cycle, rate in zip(true_cycles, rate_hz)]
              for _ in range(count)]
    epochs = [
        ({'fields': [0., 0., *(1.e8 + t * rate for rate in rate_hz)]}, None,
         {'fields': [0., 0., 1.e8, 1.e8]}, None)
        for t in range(count)
    ]
    offsets = {t: dict.fromkeys((*pair, 'G03', 'G04', 'G05'), offset_s) for t in range(count)}
    for row in offsets.values():
        row.update(dict.fromkeys(pair, 9.))
    aligned = study.align(phases, epochs, pair, 0, offsets, 1)
    assert all(row == pytest.approx(true_cycles) for row in aligned)
    offsets[2].pop('G03')
    assert study.align(phases, epochs, pair, 0, offsets, 1) is None
