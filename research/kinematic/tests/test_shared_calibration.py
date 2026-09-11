import numpy as np
import pytest

from research.kinematic.s2_validation import CLOCKS, TIMES
from research.kinematic.shared_calibration import compression, fit_shared
from research.kinematic.shared_calibration_study import REFERENCES, design, evaluate, inputs


@pytest.fixture(scope='module')
def context():
    d = design()
    d['compression'] = compression(TIMES, 7, 4, d['covariance'])
    return d


def test_gls_recovers_clock_and_shared_target_cross_covariance(context):
    d = context
    c = d['compression']
    np.testing.assert_allclose(c['reference_gain']@c['reference_design'], np.eye(14), atol=1e-11)
    _, _, references = inputs(d, 'nominal')
    np.testing.assert_allclose(c['reference_gain']@references.ravel(), CLOCKS[:7].ravel(), atol=1e-8)
    start = d['count']+70
    # A 0.01 m/s random drift is shared by phase and reference clock estimate.
    assert c['covariance'][d['count'], start+1] == pytest.approx(.0001, abs=1e-12)
    assert c['covariance'][0, start+1] == pytest.approx(-.03, abs=1e-12)


def test_compressed_covariance_against_raw_draws(context):
    d, c = context, context['compression']
    rng = np.random.default_rng(311)
    selected = [0, d['count'], d['count']+70+1]
    raw = rng.normal(size=(12000, len(d['covariance'])))@np.linalg.cholesky(d['covariance']).T
    actual = np.cov(raw@c['transform'][selected].T, rowvar=False)
    expected = c['covariance'][np.ix_(selected, selected)]
    scale = np.sqrt(np.outer(np.diag(expected), np.diag(expected)))
    np.testing.assert_allclose((actual-expected)/scale, 0, atol=.04)


def test_bad_reference_gate_does_not_call_target_loader(context):
    d = context
    _, _, refs = inputs(d, 'invalid_reference_step')
    def forbidden():
        raise AssertionError('target loader invoked after reference rejection')
    result = fit_shared(TIMES, d['stations'], refs, d['covariance'], forbidden, target='G08', references=REFERENCES)
    assert result['status'] == 'REFERENCE_CODE_REJECTED'
    assert 'fit' not in result


def test_target_reference_identity_rejected_before_numbers(context):
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('reference values decoded')
    with pytest.raises(ValueError, match='non-target'):
        fit_shared(TIMES, context['stations'], Forbidden(), None, None, target='G01', references=REFERENCES)


@pytest.mark.parametrize('kind', ['duplicate', 'short', 'singular', 'nonfinite'])
def test_invalid_compression_inputs(context, kind):
    tags = TIMES.copy()
    cov = context['covariance'].copy()
    nr = 4
    if kind == 'duplicate': tags[2] = tags[1]
    if kind == 'short': nr = 3
    if kind == 'singular': cov[0] = 0; cov[:, 0] = 0
    if kind == 'nonfinite': cov[0, 0] = np.nan
    with pytest.raises(ValueError):
        compression(tags, 7, nr, cov)


def test_shared_affine_reduces_bias_relative_to_same_target_only_delay(context):
    shared = evaluate(context, 'shared_affine')
    separate = evaluate(context, 'target_only_affine')
    from research.kinematic.s2_validation import STATE
    assert shared['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
    assert np.linalg.norm(shared['fit']['state'][:3]-STATE[:3]) < np.linalg.norm(separate['fit']['state'][:3]-STATE[:3])
    assert shared['clock_coefficients'][0, 1] == pytest.approx(CLOCKS[0, 1]+.01, abs=1e-9)
    np.testing.assert_array_equal(shared['compression']['covariance'], separate['compression']['covariance'])
