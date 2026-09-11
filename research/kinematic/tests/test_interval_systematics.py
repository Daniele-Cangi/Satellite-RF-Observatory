import numpy as np
import pytest
from scipy.linalg import block_diag

from research.kinematic.interval_fit import forecast_interval
from research.kinematic.interval_study import CALIBRATION, design, solve_data
from research.kinematic.interval_systematics import forecast_systematics, transport_systematics
from research.kinematic.s2_validation import CLOCKS
from research.kinematic.systematics_study import declared_modes


@pytest.fixture(scope='module')
def context():
    d = design()
    d['fit'] = solve_data(d, np.zeros(d['size']))
    return d


def test_absorbed_parameter_direction_has_bias_without_residual_power(context):
    d, r = context, context['fit']
    shift = np.zeros(46)
    shift[0] = 10.
    modes = (r['data_jacobian']@shift)[:, None]
    report = transport_systematics(r, d['covariance'], modes)
    np.testing.assert_allclose(report['parameter_bias_modes'][:, 0], shift, atol=1e-5)
    assert report['residual_noncentrality'][0] < 1e-12
    assert report['local_rejection_probability'][0] == pytest.approx(.01, abs=1e-10)


def test_constant_phase_cancels_and_scaling_is_quadratic(context):
    d = context
    modes, _ = declared_modes(d)
    assert np.max(abs(modes[:, 4])) < 1e-14
    a = transport_systematics(d['fit'], d['covariance'], modes)
    b = transport_systematics(d['fit'], d['covariance'], -2*modes)
    np.testing.assert_allclose(b['parameter_bias_modes'], -2*a['parameter_bias_modes'])
    np.testing.assert_allclose(b['residual_noncentrality'], 4*a['residual_noncentrality'])
    assert np.all(b['local_rejection_probability'] >= a['local_rejection_probability']-1e-12)


def test_affine_box_bounds_all_corners(context):
    d = context
    modes, _ = declared_modes(d)
    report = transport_systematics(d['fit'], d['covariance'], modes)
    for i in range(64):
        coefficients = np.array([1 if i & (1 << j) else -1 for j in range(6)])
        bias = report['parameter_bias_modes']@coefficients
        assert np.all(abs(bias) <= report['affine_box_parameter_component_bound']+1e-10)
        assert np.linalg.norm(bias[:3]) <= report['affine_box_position_norm_bound_m']+1e-10


@pytest.mark.parametrize('kind', ['nonfinite', 'shape', 'changed_covariance'])
def test_invalid_inputs_rejected(context, kind):
    d = context
    modes, _ = declared_modes(d)
    cov = d['covariance'].copy()
    if kind == 'nonfinite': modes[0, 0] = np.nan
    if kind == 'shape': modes = modes[:-1]
    if kind == 'changed_covariance': cov[0, 0] += 1
    with pytest.raises(ValueError):
        transport_systematics(d['fit'], cov, modes)


def test_rejected_fit_stops_before_input_decoding():
    class Forbidden:
        def __array__(self, *args, **kwargs):
            raise AssertionError('input decoded')
    with pytest.raises(ValueError, match='accepted interval fit'):
        transport_systematics({'status': 'MODEL_REJECTED'}, Forbidden(), Forbidden())


def test_shared_excluded_measurement_uses_signed_error_mapping(context):
    d = context
    covariance = block_diag(d['covariance'], np.eye(7))
    forecast = forecast_interval(d['fit'], 30, 60, d['stations'][7], CLOCKS[7], covariance,
                                 calibration_status=CALIBRATION)
    _, extended = declared_modes(d)
    original = forecast_systematics(forecast, extended)['output_bias_modes']
    independent = extended.copy()
    independent[-2:] = 0
    changed = forecast_systematics(forecast, independent)['output_bias_modes']
    assert original[7, 0] == pytest.approx(changed[7, 0]-.001)
    assert original[6, 5] == pytest.approx(changed[6, 5]-10)
    with pytest.raises(ValueError):
        forecast_systematics(forecast, extended[:-1])
    with pytest.raises(ValueError):
        forecast_systematics({'status': 'MODEL_REJECTED'}, None)


def test_declared_drift_local_gain_against_signed_refits(context):
    d = context
    modes, _ = declared_modes(d)
    local = transport_systematics(d['fit'], d['covariance'], modes)
    plus = solve_data(d, modes[:, 0])
    minus = solve_data(d, -modes[:, 0])
    np.testing.assert_allclose((plus['state']-minus['state'])/2,
                               local['parameter_bias_modes'][:11, 0], atol=.02, rtol=.01)
