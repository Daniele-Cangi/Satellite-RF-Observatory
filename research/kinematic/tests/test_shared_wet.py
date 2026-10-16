"""Shared wet paths, recalibration signs, marginalization and recovery."""
from copy import deepcopy

import numpy as np
import pytest

from research.exploratory import reference_wet_fit as study
from research.exploratory.tests.test_g12_dynamic_fit import SyntheticWeather
from research.kinematic.tests.test_clock_observations import curved_toy
from research.kinematic import dynamic_fit as solver, orbital_dynamics as dynamics


def wet_toy():
    arcs, state, bias = curved_toy()
    wet = np.linspace(-.02, .04, 6)
    curve = dynamics.Trajectory(state, [-100., 1900.])
    for index, a in enumerate(arcs):
        # Keep the invented geometry inside the unchanged 10-degree domain
        # throughout this longer synthetic trajectory.
        a['stations_m'] = a['stations_m'].copy()
        angle = np.deg2rad(15.)
        x, y = a['stations_m'][3, :2]
        a['stations_m'][3, :2] = [np.cos(angle)*x-np.sin(angle)*y, np.sin(angle)*x+np.cos(angle)*y]
        response = np.column_stack([-np.linspace(1.2, 3., 6),
            np.linspace(-.001, .001, 6)*(index+1), np.linspace(.0001, -.0002, 6)*(index+1)])
        true_clocks = a['clock_mean'].copy()
        a['clock_mean'] = true_clocks-response*wet[:, None]
        a['wet_clock_response'] = response
        a['propagation'] = study.propagation_model(SyntheticWeather(), a['stations'])
        pair = study.baseline.interval.clock_observations.predict(curve, a['endpoint_gpst_s']-36060.,
            a['tags_s'], a['stations_m'], true_clocks, [70000., .1, .0001], a['receiver_clock_basis'])
        path = pair['code_m']+a['propagation'](pair, a['stations_m'], 36060., wet_m=wet)['delay_m']
        a['codes_m'] = path+bias
        a['rates_m_s'] = np.diff(path, axis=0)/30.
    return arcs, state, bias, wet


def test_shared_wet_recovers_state_motion_bias_and_wet_without_a_prior():
    arcs, state, bias, wet = wet_toy()
    result = solver.fit(arcs)
    assert result['status'] == 'BRANCH_SEARCH_INCOMPLETE', result
    assert result['branch_failures']
    np.testing.assert_allclose(result['state_ecef_m_m_s'][:3], state[:3], atol=1.)
    np.testing.assert_allclose(result['state_ecef_m_m_s'][3:], state[3:], atol=.001)
    np.testing.assert_allclose(list(result['station_code_bias_m'].values()), bias, atol=.1)
    np.testing.assert_allclose(list(result['station_zenith_wet_correction_m'].values()), wet, atol=.01)
    assert result['weighted_residual_cost'] < 1e-7
    assert not result['physical_covariance_qualified']
    assert result['conditional_global_covariance'].shape == (17, 17)


def test_wet_column_changes_target_paths_and_reference_clock_observations():
    arcs, state, _, wet = wet_toy()
    prepared, _, _ = solver.prepare(arcs, True)
    a = prepared[1]
    local = np.r_[70000., .1, .0001, a['clocks'].ravel(), np.zeros(18)]/a['local_scale']
    curve = dynamics.Trajectory(state, [-100., 1900.], sensitivities=True)
    beta = np.r_[np.zeros(5), wet]
    value, pair = solver.model(curve, a, local, beta, 36060., derivatives=True)
    c, p = a['codes'].size, len(a['difference'])
    for j in range(6):
        step = np.eye(11)[5+j]*.01
        numerical = (solver.model(curve, a, local, beta+step, 36060.)[0]-
                     solver.model(curve, a, local, beta-step, 36060.)[0])/.02
        expected = np.zeros_like(value)
        path = np.zeros((3, 6)); path[:, j] = pair['wet_derivative'][:, j]
        expected[:c] = path.ravel()
        expected[c:c+p] = a['difference']@path.ravel()
        expected[c+p+3*j:c+p+3*j+3] = -a['wet_response'][j]
        np.testing.assert_allclose(numerical, expected, atol=5e-7, rtol=3e-4)
    assert np.isfinite(pair['initial_state_derivative']).all()


def test_observation_response_reconstructs_covariance_and_preserves_cross_arc_source():
    arcs, state, _, wet = wet_toy()
    prepared, names, _ = solver.prepare(arcs, True)
    scale = np.r_[solver.STATE_SCALE, np.full(5, 100.), np.ones(6)]
    local = [np.r_[70000., .1, .0001, a['clocks'].ravel(), np.zeros(18)]/a['local_scale'] for a in prepared]
    details = {}
    result = solver.linearize(np.r_[state, np.zeros(5), wet]/scale, local, prepared, scale,
        36060., [-100., 1900.], dynamics.J2, diagnostics=details)
    response = details['observation_response']
    recovered = sum(k@a['covariance']@k.T for a, k in zip(prepared, response, strict=True))
    np.testing.assert_allclose(recovered, result[3], rtol=2e-6, atol=.01)
    # One coherent clock error shared over all arcs is one column. Adding the
    # variances of its separate appearances would lose the cross terms.
    source = [np.r_[np.zeros(5*a['n']), np.column_stack([np.arange(a['n']),
        .001*np.arange(a['n'])**2, np.zeros(a['n'])]).ravel(), np.zeros(3*a['n'])] for a in prepared]
    coherent = sum(k@v for k, v in zip(response, source, strict=True))
    independent = sum(np.outer(k@v, k@v) for k, v in zip(response, source, strict=True))
    assert not np.allclose(np.outer(coherent, coherent), independent, rtol=.01, atol=.001)
    # The free wet parameter cannot increase conditional information at the
    # same geometry, compared with an exact wet correction.
    information = np.linalg.inv(result[3])
    conditional = np.linalg.inv(information[:11, :11])
    assert np.linalg.eigvalsh(result[3][:11, :11]-conditional)[0] > -.01


def test_incomplete_or_nonfinite_wet_response_fails_closed():
    arcs, _, _, _ = wet_toy()
    bad = deepcopy(arcs)
    bad[0].pop('wet_clock_response')
    with pytest.raises(ValueError, match='every arc'):
        solver.prepare(bad, True)
    arcs[0]['wet_clock_response'][0, 0] = np.nan
    with pytest.raises(ValueError, match='wet clock response'):
        solver.prepare(arcs, True)
