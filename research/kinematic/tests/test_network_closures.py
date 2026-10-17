"""Network-closure information, withheld RF and full calibration/state coupling."""
from copy import deepcopy

import numpy as np
import pytest

from research.kinematic import network_clocks, network_closures as closures, gnss_combinations
from research.exploratory import reference_network_clocks as study
from research.kinematic.tests.test_temporal_shared_rf import prepared


def reference_rows():
    output = []
    for k in range(45):
        for i,s in enumerate('ABCDEF'):
            for j,q in enumerate('WXYZ'):
                if s == 'F' and q == 'W' and k % 3 == 1:
                    continue
                d = 1.+1e-6*(i+1)*(j+1)
                clock = d*(20*i+.01*(i+1)*k)-.1*(j-1.5)*k
                output.append({'station':s,'reference':q,'time_s':30.*k,
                    'segment':s+q,'base_segment':s+q,'geometry_free_phase_m':0.,
                    'clock_derivative':d,'code_m':clock,'phase_m':clock+20*i+7*j,
                    'mw_m':5*i+3*j})
    return output


def test_future_link_phase_and_gf_do_not_enter_predictions_or_support():
    rows = reference_rows()
    raw = gnss_combinations.assumed_endpoint_covariance()
    first = closures.prepare_future_links(rows,'TARGET',raw)
    assert first['status'] == 'FUTURE_LINK_PREDICTIONS_FROZEN'
    assert first['withheld_row_count'] > 0
    original = closures.score_future_links(first,rows)
    for item in original['increment_errors']:
        assert item['count'] > 0
        np.testing.assert_allclose(item['code_phase_rms_error_m'], 0., atol=1e-7)
    class Forbidden:
        def __float__(self):
            raise AssertionError('withheld GF decoded')
    changed = deepcopy(rows)
    for r in changed:
        if [r['station'],r['reference']] in [list(k) for k in first['held_links']] and r['time_s'] > first['training_stop_s']:
            delta = .2*np.sin(r['time_s']/200.)
            r['code_m'] += delta
            r['phase_m'] += delta
            r['geometry_free_phase_m'] = Forbidden()
            r['segment'] = 'forbidden-future-GF-segment'
    second = closures.prepare_future_links(changed,'TARGET',raw)
    assert first == second
    scored = closures.score_future_links(second,changed)
    for item in scored['increment_errors']:
        assert item['code_phase_rms_error_m'][1] > .005
        np.testing.assert_allclose(item['code_phase_rms_error_m'][0], item['code_phase_rms_error_m'][1], atol=1e-7)
    with pytest.raises(ValueError,match='candidate'):
        closures.prepare_future_links([{'reference':'TARGET','time_s':Forbidden()}],'TARGET',raw)


def test_full_response_and_clock_cycle_partition_match_dense_linear_transport(monkeypatch):
    rows = reference_rows()
    raw = gnss_combinations.assumed_endpoint_covariance()
    network = network_clocks.fit(rows,raw_covariance=raw)
    requests = [{('A',0.):1.},{('B',660.):1.},{('C',1320.):1.},
                {('D',900.):1/30.,('D',870.):-1/30.}]
    rng = np.random.default_rng(231)
    response = rng.normal(size=(6,4))
    result = closures.state_transfer(network,requests,'TARGET',response,np.arange(4))
    maps = network_clocks.observation_response(network,requests)
    full = np.column_stack([r[:,:len(b['rows'])]+r[:,len(b['rows']):2*len(b['rows'])]
                           for r,b in zip(maps,network['blocks'],strict=True)])
    expected = response @ full
    assert result['response_partition_identity_max'] < 1e-8
    fractions = [m['position_response_energy_fraction'] for m in result['modes'].values()]
    assert sum(fractions) == pytest.approx(1.,abs=1e-9)
    for name, item in result['modes'].items():
        delta = item['reference_change_m']
        assert np.sqrt(np.mean(delta**2)) == pytest.approx(closures.PROBE_RMS_M)
        np.testing.assert_allclose(item['linear_state_change_m_m_s'],expected @ delta,atol=1e-9)
        offset = 0
        for b in network['blocks']:
            count = len(b['rows']);q = closures.clock_basis(b)
            own = delta[offset:offset+count]
            if name == 'clock_blind':
                np.testing.assert_allclose(own,q @ (q.T @ own),atol=1e-10)
            else:
                np.testing.assert_allclose(q.T @ own,0.,atol=1e-10)
            offset += count
    poisoned = deepcopy(network)
    poisoned['blocks'][0]['rows'][0]['reference'] = 'TARGET'
    monkeypatch.setattr(network_clocks,'observation_response',lambda *a:pytest.fail('candidate reached arithmetic'))
    with pytest.raises(ValueError,match='candidate'):
        closures.state_transfer(poisoned,requests,'TARGET',response,np.arange(4))


def test_unobserved_future_network_clocks_are_not_extrapolated():
    rows = reference_rows()
    raw = gnss_combinations.assumed_endpoint_covariance()
    full = closures.prepare_future_links(rows,'TARGET',raw)
    selected = set(tuple(k) for k in full['held_links'])
    absent = [r for r in rows if r['time_s'] <= full['training_stop_s'] or (r['station'],r['reference']) in selected]
    result = closures.prepare_future_links(absent,'TARGET',raw)
    assert result['withheld_row_count'] > 0
    assert all(r['status']=='UNOBSERVED_NETWORK_CLOCK' for r in result['predictions'])
    assert len(result['predictions']) == result['withheld_row_count']


def test_constant_complete_graph_has_no_resolved_cycle_to_clock_state_response():
    rows = [r for r in reference_rows() if int(r['time_s']/30) % 3 != 1]
    raw = gnss_combinations.assumed_endpoint_covariance()
    network = network_clocks.fit(rows,raw_covariance=raw)
    requests = [{('A',0.):1.},{('B',900.):1.},{('C',1260.):1.}]
    state = np.random.default_rng(10).normal(size=(6,3))
    result = closures.state_transfer(network,requests,'TARGET',state,np.arange(3))
    assert result['modes']['cycle_visible']['status']=='NO_RESOLVED_POSITION_PROBE'
    assert result['modes']['cycle_visible']['position_response_energy_fraction'] < 1e-18


def test_nondispersive_probe_refits_reference_biases_and_trajectory():
    arcs,state,raw,network,joint,metadata = prepared()
    rows = [deepcopy(r) for b in network['blocks'] for r in b['rows'] if not (
        (r['station'],r['reference']) == ('F','Z') and r['time_s'] < 36100. or
        (r['station'],r['reference']) == ('C','Z') and 36200. < r['time_s'] < 36400.)]
    network = network_clocks.fit(rows,raw_covariance=raw)
    arcs,joint,metadata = study.attach(network,arcs)
    arcs[0]['phase_increment_mask'] = np.ones((2,6),dtype=bool)
    arcs[0]['phase_increment_mask'][0,0] = False
    arcs[0]['mw_increment_mask'] = arcs[0]['phase_increment_mask'].copy()
    fitted = study.dynamic_fit.fit(arcs,joint_covariance=joint)
    details,cov,own = study.linear_response(fitted,arcs,joint)
    response = details['full_observation_response']
    np.testing.assert_allclose(response @ joint @ response.T,cov,rtol=2e-5,atol=1e-3)
    assert np.count_nonzero(response[:,18]) == 0  # the excluded first phase increment
    transfer = closures.state_transfer(network,study.clock_requests(arcs),'TARGET',response,
                                      metadata['clock_observation_indices'])
    original = closures.closure_records(network,'TARGET')
    for name,mode in transfer['modes'].items():
        rows = [deepcopy(r) for b in network['blocks'] for r in b['rows']]
        for r,delta in zip(rows,mode['reference_change_m'],strict=True):
            r['code_m'] += delta
            r['phase_m'] += delta
        recalibrated = network_clocks.fit(rows,raw_covariance=raw)
        actual_closures = closures.closure_records(recalibrated,'TARGET')
        before = np.array([[r['code_closure_m'],r['phase_closure_m']] for r in original['rows']])
        after = np.array([[r['code_closure_m'],r['phase_closure_m']] for r in actual_closures['rows']])
        if name == 'clock_blind':
            assert np.max(abs(after-before)) < 1e-6
        else:
            assert np.max(abs(after-before)) > 1e-5
        changed,covariance,_ = study.attach(recalibrated,arcs)
        refitted = study.dynamic_fit.fit(changed,joint_covariance=covariance)
        delta = np.asarray(refitted['state_ecef_m_m_s'])-fitted['state_ecef_m_m_s']
        expected = mode['linear_state_change_m_m_s']
        np.testing.assert_allclose(delta[:3],expected[:3],atol=.1,rtol=.01)
        np.testing.assert_allclose(delta[3:],expected[3:],atol=1e-4,rtol=.02)
    assert not transfer['physical_covariance_qualified']
