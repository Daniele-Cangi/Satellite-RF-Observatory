"""Nonlinear clock geometry, joint endpoint errors and shared-state recovery."""
from copy import deepcopy

import numpy as np
import pytest

from research.kinematic import clock_observations as clocks, orbital_dynamics as dynamics, dynamic_fit
from research.kinematic.tests.test_dynamic_fit import toy
from research.exploratory import g12_interval_clocks as study
from research.exploratory.tests.test_g12_dynamic_fit import SyntheticWeather
from research.exploratory.g12_dynamic_fit import propagation_model


def curved_toy():
    arcs, state, bias = toy()
    curve = dynamics.Trajectory(state, [-100., 1900.])
    for a in arcs:
        a['clock_mean'] = np.column_stack([a['clock_mean'], np.linspace(-.01, .02, 6)])
        a['receiver_clock_basis'] = study.clock_basis(a['tags_s'])
        a['satellite_clock_count'] = 3
        a['covariance'] = study.joint_covariance(6, 'shared_endpoints_added')
        pair = clocks.predict(curve, a['endpoint_gpst_s']-36060., a['tags_s'], a['stations_m'],
                             a['clock_mean'], [70000., .1, .0001], a['receiver_clock_basis'])
        a['codes_m'] = pair['code_m']+bias
        a['rates_m_s'] = np.diff(pair['code_m'], axis=0)/30.
    return arcs, state, bias


def test_endpoint_covariance_keeps_overlap_and_shared_reference_errors():
    n = 5
    for scenario in study.SCENARIOS:
        whole = study.joint_covariance(n, scenario)
        np.linalg.cholesky(whole)
        phase = whole[3*n:5*n, 3*n:5*n]
        np.testing.assert_allclose(phase[:n, n:], -np.eye(n)*.02**2/900)
        clock = whole[5*n:8*n, 5*n:8*n]
        # Recover individual increment errors by an independent transform.
        transform = np.zeros((2*n, 3*n))
        for j in range(n):
            transform[2*j:2*j+2, 3*j+1:3*j+3] = [[1, 1], [1, -1]]
        rates = transform@clock@transform.T
        expected = .01**2*np.array([[4., -2.], [-2., 4.]])
        factor = 2 if scenario == 'shared_endpoints_added' else 1
        np.testing.assert_allclose(rates[:2, :2], factor*expected)
        np.testing.assert_allclose(rates[:2, 2:4], expected if factor == 2 else np.zeros((2, 2)))
        np.testing.assert_allclose(whole[:3*n, :3*n], 400*np.eye(3*n))
    with pytest.raises(ValueError, match='declared'):
        study.joint_covariance(n, 'tuned')


def test_clock_shapes_represent_measured_increments_without_trend_forecast():
    coefficients = np.array([[100., .02, .003]])
    values = study.clock_basis([-60., -30., 0., 30.])@coefficients.T
    np.testing.assert_allclose(np.diff(values[:, 0])/30., [.023, .017, .02], atol=1e-15)
    satellite = clocks.satellite_basis([-60., 0., 30.], 3)@np.array([100., .2, .001])
    np.testing.assert_allclose(satellite, [91.6, 100., 106.])


def test_curved_clock_derivatives_include_light_time_and_current_propagation():
    arcs, state, _ = curved_toy()
    prepared, _, _ = dynamic_fit.prepare(arcs, True)
    a = prepared[2]
    epoch = 36060.
    a['propagation'] = propagation_model(SyntheticWeather(), a['stations'])
    # Deliberately exaggerated curvature makes the implicit light-time chain
    # measurable in this numerical test; it is not a physical clock prior.
    physical = np.r_[70000., .1, 1000., a['clocks'].ravel(), np.zeros(3*a['n'])]
    def evaluate(seed, local, derivatives=False):
        curve = dynamics.Trajectory(seed, [-100., 1900.], sensitivities=derivatives)
        return dynamic_fit.model(curve, a, local/a['local_scale'], np.zeros(5), epoch, derivatives=derivatives)
    value, pair = evaluate(state, physical, True)
    count = a['codes'].size
    for k, h in enumerate([100., 100., 100., .01, .01, .01]):
        delta = np.eye(6)[k]*h
        numerical = (evaluate(state+delta, physical)[0][:count]-evaluate(state-delta, physical)[0][:count])/(2*h)
        np.testing.assert_allclose(pair['initial_state_derivative'].reshape(count, 6)[:, k], numerical, rtol=2e-5, atol=1e-6)
    for site in range(6):
        for k, h in enumerate([10., .1, .1]):
            delta = np.zeros(len(physical)); delta[3+3*site+k] = h
            numerical = (evaluate(state, physical+delta)[0][:count]-evaluate(state, physical-delta)[0][:count])/(2*h)
            expected = np.zeros((3, 6))
            expected[:, site] = pair['receiver_clock_derivative'][:, site]*a['clock_basis'][:, k]
            np.testing.assert_allclose(numerical, expected.ravel(), rtol=1e-6, atol=1e-7)
    for k in range(3):
        delta = np.zeros(len(physical)); delta[3+3*a['n']+k] = 10.
        numerical = (evaluate(state, physical+delta)[0][:count]-evaluate(state, physical-delta)[0][:count])/20.
        expected = np.zeros((3, 6))
        expected[:, 0] = pair['station_derivative'][:, 0, k]
        np.testing.assert_allclose(numerical, expected.ravel(), rtol=1e-6, atol=1e-7)
    tx = pair['transmit_s']-(a['endpoint_gpst_s']-epoch)
    for k, h in enumerate([1., .01, .0001]):
        delta = np.zeros(len(physical)); delta[k] = h
        numerical = (evaluate(state, physical+delta)[0][:count]-evaluate(state, physical-delta)[0][:count])/(2*h)
        np.testing.assert_allclose(numerical, -clocks.satellite_basis(tx, 3)[..., k].ravel(), rtol=1e-5, atol=3e-5)
    assert np.isfinite(value).all()


def test_curved_shared_fit_recovers_state_bias_and_retains_all_branches():
    arcs, state, bias = curved_toy()
    fitted = dynamic_fit.fit(arcs)
    assert fitted['status'] == 'BRANCH_SEARCH_INCOMPLETE', fitted
    assert fitted['branch_failures']
    assert fitted['state_ecef_m_m_s'][:3] == pytest.approx(state[:3], abs=.5)
    assert fitted['state_ecef_m_m_s'][3:] == pytest.approx(state[3:], abs=5e-4)
    assert list(fitted['station_code_bias_m'].values()) == pytest.approx(bias, abs=.5)
    assert fitted['weighted_residual_cost'] < 1e-6
    assert not fitted['physical_covariance_qualified']
    assert all(len(p['satellite_clock']) == 3 and p['receiver_clocks'].shape == (6, 3) for p in fitted['arc_parameters'])


def test_bad_clock_basis_and_nonmonotone_clock_fail_closed():
    arcs, state, _ = curved_toy()
    broken = deepcopy(arcs)
    broken[0]['receiver_clock_basis'][-1, 2] = 1.
    with pytest.raises(ValueError, match='complete finite'):
        dynamic_fit.prepare(broken, True)
    a = arcs[0]
    a['clock_mean'][0, 2] = dynamics.C
    with pytest.raises(ValueError, match='monotone'):
        clocks.predict(dynamics.Trajectory(state, [-100., 100.]), 0., a['tags_s'], a['stations_m'],
                       a['clock_mean'], [70000., .1, .001], a['receiver_clock_basis'])
