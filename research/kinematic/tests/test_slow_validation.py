import json
import numpy as np
import pytest

from research.kinematic.s2_validation import TIMES
from research.kinematic.shared_phase_study import design
from research.kinematic.slow_validation import PLAN, data, evaluate, shape


def test_fixed_plan_and_shapes_outside_quadratic_basis():
    plan = json.loads(PLAN.read_text())
    assert len(plan['cases']) == 6 and plan['draws_per_case']*len(plan['noisy_cases']) == 8
    assert plan['seed'] == 20260914
    basis = np.column_stack([np.ones(len(TIMES)), TIMES, TIMES**2])
    for case in plan['cases'][1:]:
        y = shape(case, TIMES)
        projection = basis@np.linalg.lstsq(basis, y, rcond=None)[0]
        assert np.linalg.norm(y-projection) > .001
    with pytest.raises(ValueError): shape('unknown', TIMES)


def test_target_only_and_shared_cases_have_same_target_data():
    d = design()
    zero = np.zeros(len(d['extended_covariance'])+7)
    shared = data(d, 'shared_cubic', zero)
    target = data(d, 'target_cubic', zero)
    np.testing.assert_array_equal(shared[0], target[0])
    np.testing.assert_array_equal(shared[1], target[1])
    assert np.max(abs(shared[2]-target[2])) == pytest.approx(.1, abs=1e-10)


def test_raw_ground_and_excluded_errors_not_injected_into_other_blocks():
    d = design()
    zero = np.zeros(len(d['extended_covariance'])+7)
    changed = zero.copy()
    changed[2*d['count']+d['nref']] = 2.
    changed[-7:] = 1.
    original = data(d, 'nominal', zero)
    perturbed = data(d, 'nominal', changed)
    for i in range(4): np.testing.assert_array_equal(original[i], perturbed[i])
    assert perturbed[4][0, 0]-original[4][0, 0] == 2.


@pytest.mark.parametrize('kind', ['shape', 'nonfinite'])
def test_bad_noise_vector_rejected(kind):
    d = design()
    error = np.zeros(len(d['extended_covariance'])+7)
    if kind == 'shape': error = error[:-1]
    if kind == 'nonfinite': error[0] = np.nan
    with pytest.raises(ValueError): data(d, 'nominal', error)


@pytest.mark.parametrize('quadratic', [False, True])
def test_rejected_reference_kept_without_forecast(quadratic):
    d = design()
    error = np.zeros(len(d['extended_covariance'])+7)
    for i in range(5, len(TIMES)):
        error[2*d['count']+i*28] = 300.
    row = evaluate(d, 'nominal', error, quadratic)
    assert row['status'] == 'REFERENCE_CODE_REJECTED'
    assert row['target_loader_calls'] == 0
    assert 'forecast' not in row and 'fit' not in row
