import numpy as np
import pytest

from research.kinematic.s2_validation import TIMES
from research.kinematic.shared_phase_study import design, REFERENCES
from research.kinematic.slow_calibration import fit_slow_calibration, quadratic_design
from research.kinematic.slow_calibration_study import evaluate, case_inputs


@pytest.fixture(scope='module')
def context():
    d = design()
    d['nominal'] = evaluate(d, 'nominal', True)
    return d


def test_reference_only_quadratic_recovery_and_uncertainty(context):
    r = evaluate(context, 'shared_curvature', True)
    assert r['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
    assert r['reference_coefficients'][0, 2] == pytest.approx(.1, abs=1e-8)
    from research.kinematic.s2_validation import STATE
    assert np.linalg.norm(r['fit']['state'][:3]-STATE[:3]) < .01
    # Deterministic amplitude does not change the declared covariance.
    np.testing.assert_array_equal(r['fit_covariance'], context['nominal']['fit_covariance'])
    assert r['reference_code_dof'] == 287 and r['reference_phase_dof'] == 280


def test_quadratic_projection_and_covariance_cross_terms(context):
    d, r = context, context['nominal']
    np.testing.assert_allclose(r['reference_gain']@r['reference_design'], np.eye(21), atol=1e-10)
    t, cov = r['transform'], d['extended_covariance']
    np.testing.assert_allclose(r['fit_covariance'], t@cov@t.T, atol=1e-9)
    assert np.max(abs(r['gate_fit_cross_covariance'])) > 1e-8
    selected = [0, 77, 147, 148]
    factor = t[selected]@np.linalg.cholesky(cov)
    rng = np.random.default_rng(522)
    draw = rng.normal(size=(12000, len(cov)))@factor.T
    expected = r['fit_covariance'][np.ix_(selected, selected)]
    sigma = np.sqrt(np.outer(np.diag(expected), np.diag(expected)))
    np.testing.assert_allclose((np.cov(draw, rowvar=False)-expected)/sigma, 0, atol=.04)


def test_slip_rejection_preserves_code_coefficients_and_never_loads_target(context):
    d = context
    _, _, refs, phases = case_inputs(d, 'reference_phase_slip')
    def forbidden():
        raise AssertionError('target loaded after failed phase gate')
    r = fit_slow_calibration(TIMES, d['stations'], refs, phases, d['extended_covariance'], forbidden,
                             target='G08', references=REFERENCES)
    assert r['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED'
    np.testing.assert_array_equal(r['reference_coefficients'], d['nominal']['reference_coefficients'])


def test_invalid_code_gate_precedes_phase_decoding(context):
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('phase decoded')
    d = context
    _, _, refs, _ = case_inputs(d, 'nominal')
    refs[len(TIMES)//2:, 0, 0] += 300.
    r = fit_slow_calibration(TIMES, d['stations'], refs, Forbidden(), d['extended_covariance'], None,
                             target='G08', references=REFERENCES)
    assert r['status'] == 'REFERENCE_CODE_REJECTED'
    assert 'reference_phase_p' not in r


@pytest.mark.parametrize('tags', [[-30, 0], [-60, -30, -30, 0], [-60, -30, 0, 30]])
def test_bad_time_basis_rejected(tags):
    with pytest.raises(ValueError):
        quadratic_design(tags, 7, 4)


@pytest.mark.parametrize('kind', ['target_reference', 'missing_phase', 'nonfinite_code', 'singular_covariance'])
def test_bad_inputs_stop_before_target(context, kind):
    d = context
    _, _, codes, phases = case_inputs(d, 'nominal')
    cov = d['extended_covariance'].copy()
    target = 'G01' if kind == 'target_reference' else 'G08'
    if kind == 'missing_phase': phases = phases[:-1]
    if kind == 'nonfinite_code': codes[0, 0, 0] = np.nan
    if kind == 'singular_covariance': cov[-1] = 0; cov[:, -1] = 0
    def forbidden():
        raise AssertionError('target loaded')
    with pytest.raises(ValueError):
        fit_slow_calibration(TIMES, d['stations'], codes, phases, cov, forbidden, target=target, references=REFERENCES)
