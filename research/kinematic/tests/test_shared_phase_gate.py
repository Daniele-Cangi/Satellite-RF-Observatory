import numpy as np
import pytest

from research.kinematic.s2_validation import TIMES
from research.kinematic.shared_calibration_study import REFERENCES, evaluate as old_evaluate
from research.kinematic.shared_phase_gate import fit_shared_phase
from research.kinematic.shared_phase_study import design, evaluate, inputs


@pytest.fixture(scope='module')
def context():
    d = design()
    d['nominal'] = evaluate(d, 'nominal')
    return d


def test_accepted_gate_preserves_existing_fit_and_covariance(context):
    d = context
    old = old_evaluate(d, 'nominal')
    new = d['nominal']
    assert new['reference_phase_dof'] == 280
    assert new['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
    assert new['target_loader_calls'] == 1
    np.testing.assert_array_equal(new['clock_coefficients'], old['clock_coefficients'])
    np.testing.assert_array_equal(new['downstream']['fit']['state'], old['fit']['state'])
    np.testing.assert_array_equal(new['downstream']['compression']['covariance'], old['compression']['covariance'])


@pytest.mark.parametrize('case', ['reference_phase_slip', 'strong_shared_curvature'])
def test_phase_failure_never_loads_target(context, case):
    d = context
    _, _, codes, phases = inputs(d, case)
    def forbidden():
        raise AssertionError('target loaded after phase rejection')
    result = fit_shared_phase(TIMES, d['stations'], codes, phases, d['extended_covariance'], forbidden,
                              target='G08', references=REFERENCES)
    assert result['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED'
    assert 'downstream' not in result
    if case == 'reference_phase_slip':
        np.testing.assert_array_equal(result['clock_coefficients'], d['nominal']['clock_coefficients'])


def test_code_failure_precedes_phase_decode(context):
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('reference phase decoded after code rejection')
    d = context
    _, _, codes, _ = inputs(d, 'invalid_reference_step')
    result = fit_shared_phase(TIMES, d['stations'], codes, Forbidden(), d['extended_covariance'], None,
                              target='G08', references=REFERENCES)
    assert result['status'] == 'REFERENCE_CODE_REJECTED'
    assert 'reference_phase_p' not in result


def test_constant_ambiguities_cancel(context):
    r = evaluate(context, 'constant_ambiguity')
    np.testing.assert_allclose(r['phase_residuals_m_s'], context['nominal']['phase_residuals_m_s'], atol=1e-9)
    np.testing.assert_array_equal(r['clock_coefficients'], context['nominal']['clock_coefficients'])


def test_full_gate_covariance_and_shared_target_cross_terms(context):
    d, r = context, context['nominal']
    g, c = r['phase_residual_mapping'], d['extended_covariance']
    f = np.pad(r['downstream']['compression']['transform'], ((0, 0), (0, d['nref'])))
    np.testing.assert_allclose(r['phase_residual_fit_data_cross_covariance'], g@c@f.T, atol=1e-12)
    assert np.max(abs(g@c@f.T)) > 1e-8
    # Independent raw draws projected into a small set of gate and fit outputs.
    selected = np.vstack([g[[0, 28]], f[[0, 77, 148]]])
    factor = selected@np.linalg.cholesky(c)
    rng = np.random.default_rng(121)
    draw = rng.normal(size=(12000, len(c)))@factor.T
    expected = selected@c@selected.T
    scale = np.sqrt(np.outer(np.diag(expected), np.diag(expected)))
    np.testing.assert_allclose((np.cov(draw, rowvar=False)-expected)/scale, 0, atol=.045)


@pytest.mark.parametrize('kind', ['missing_phase', 'nonfinite_phase', 'singular_covariance', 'target_in_references'])
def test_invalid_input_stops_before_target(context, kind):
    d = context
    _, _, codes, phases = inputs(d, 'nominal')
    cov = d['extended_covariance'].copy()
    refs = REFERENCES
    if kind == 'missing_phase': phases = phases[:-1]
    if kind == 'nonfinite_phase': phases[0, 0, 0] = np.nan
    if kind == 'singular_covariance': cov[-1] = 0; cov[:, -1] = 0
    if kind == 'target_in_references': refs = ('G08', *REFERENCES[1:])
    def forbidden():
        raise AssertionError('target loaded for invalid input')
    with pytest.raises(ValueError):
        fit_shared_phase(TIMES, d['stations'], codes, phases, cov, forbidden, target='G08', references=refs)
