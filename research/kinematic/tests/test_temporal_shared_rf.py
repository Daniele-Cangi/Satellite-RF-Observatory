"""Raw-domain transport, temporal shape and unidentifiable shared components."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.linalg import block_diag, solve_triangular

from research.exploratory import reference_network_clocks as study
from research.kinematic import network_clocks, gnss_combinations as combo, shared_rf_covariance as transport, temporal_contrasts
from research.kinematic.tests.test_dynamic_fit import toy
from research.kinematic.tests.test_network_clocks import toy as reference_toy


def prepared():
    arcs,state,_ = toy()
    raw = combo.assumed_endpoint_covariance()
    rows = []
    for a in arcs:
        a['clock_mean'] = np.column_stack([a['clock_mean'],np.zeros(6)])
        a['receiver_clock_basis'] = study.baseline.interval.clock_basis(a['tags_s'])
        a['satellite_clock_count'] = 3
        a['mw_rates_m_s'] = np.zeros((2,6))
        a['covariance'] = block_diag(combo.rf_covariance(a['tags_s'],6,raw),
            study.baseline.interval.joint_covariance(6,'shared_endpoints_added')[30:,30:])
        for dt in a['tags_s']:
            for i,s in enumerate(a['stations']):
                clock = a['clock_mean'][i,0]+dt*a['clock_mean'][i,1]
                for j,q in enumerate('XYZ'):
                    rows.append({'station':s,'reference':q,'time_s':a['endpoint_gpst_s']+dt,
                        'segment':f'{s}/{q}', 'code_m':clock,'phase_m':clock+100*i+5*j,'mw_m':30*i+2*j})
    network = network_clocks.fit(rows,raw_covariance=raw)
    own,joint,metadata = study.attach(network,arcs)
    return own,state,raw,network,joint,metadata


def test_clock_observation_response_matches_dense_gls_and_noise_covariance():
    for drift in (False,True):
        rows = reference_toy()
        for r in rows:r['mw_m'] = 3.
        network = network_clocks.fit(rows,raw_covariance=combo.assumed_endpoint_covariance(),phase_drift=drift)
        blocks = network['blocks']
        design = np.column_stack([block_diag(*[b['a'] for b in blocks]),np.vstack([b['b'] for b in blocks])])
        c = block_diag(*[b['covariance'] for b in blocks]);chol = np.linalg.cholesky(c)
        u,s,vt = np.linalg.svd(solve_triangular(chol,design,lower=True),full_matrices=False)
        gain = (vt.T/s)@u.T@solve_triangular(chol,np.eye(len(c)),lower=True)
        requests = [{('A',60.):1.},{('B',240.):1.},{('A',240.):1/60.,('A',180.):-1/60.}]
        select = np.zeros((len(requests),len(gain)));at=0
        for b in blocks:
            for i,r in enumerate(requests):
                for j,station in enumerate(b['stations']):select[i,at+j] = r.get((station,b['time_s']),0.)
            at += len(b['parameters'])
        response = np.column_stack(network_clocks.observation_response(network,requests))
        np.testing.assert_allclose(response,select@gain,atol=2e-8,rtol=1e-6)
        _,expected = network_clocks.clock_coefficients(network,requests)
        np.testing.assert_allclose(response@c@response.T,expected,atol=1e-7,rtol=1e-7)


def test_structured_temporal_shared_covariance_matches_dense_raw_covariance(monkeypatch):
    arcs,state,raw,network,joint,meta = prepared()
    requests = study.clock_requests(arcs)
    before = joint.copy()
    _,identity,_ = transport.propagate(network,requests,arcs,joint,meta['clock_observation_indices'],'G05',raw)
    np.testing.assert_allclose(identity,joint,atol=2e-7,rtol=1e-7)
    own,actual,info = transport.propagate(network,requests,arcs,joint,meta['clock_observation_indices'],
        'G05',raw,code_rho=.4,receiver_fraction=.6)
    # Independent dense raw construction. Clock derivatives are checked
    # against full GLS separately above; raw covariance includes every
    # reference-target, same-receiver and cross-epoch term explicitly here.
    keys = [(r['station'],r['reference'],b['time_s']) for b in network['blocks'] for r in b['rows']]
    reference_count = len(keys)
    mapping = np.zeros((len(joint),4*(reference_count+sum(3*len(a['stations']) for a in arcs))))
    response = network_clocks.observation_response(network,requests)
    at=0
    t = combo.transform()[combo.RETAINED]
    for b,r in zip(network['blocks'],response,strict=True):
        m=len(b['rows'])
        rawmap=np.zeros((3*m,4*m))
        for k in range(3):
            for j in range(m):rawmap[k*m+j,4*j:4*j+4]=t[k]
        mapping[np.ix_(meta['clock_observation_indices'],np.arange(4*at,4*(at+m)))] = r@rawmap
        at+=m
    data_at=0
    for a in arcs:
        n=len(a['stations']);count=3*n
        endpoint=np.kron(np.eye(count),t)
        choose=[np.kron(np.eye(count),np.eye(3)[k:k+1]) for k in range(3)]
        difference=study.dynamic_fit.interval_matrix(a['tags_s'],n)
        rf=np.vstack([choose[0],difference@choose[1],difference@choose[2]])@endpoint
        mapping[data_at:data_at+7*n,4*at:4*(at+count)] = rf
        keys.extend((s,'G05',a['endpoint_gpst_s']+dt) for dt in a['tags_s'] for s in a['stations'])
        at+=count;data_at+=len(a['covariance'])
    rawcov=np.zeros((4*len(keys),4*len(keys)))
    for i,(s,q,time) in enumerate(keys):
        for j,(u,p,other) in enumerate(keys):
            weight=(.4 if (s,q)==(u,p) else 0.)+(.6 if s==u else 0.)
            temporal=.4**(abs(time-other)/30.)
            rawcov[4*i:4*i+2,4*j:4*j+2] = weight*temporal*raw[:2,:2]
            if time==other:rawcov[4*i+2:4*i+4,4*j+2:4*j+4] = weight*raw[2:,2:]
    expected=mapping@rawcov@mapping.T
    ground=np.flatnonzero(~mapping.any(axis=1))
    expected[np.ix_(ground,ground)] = joint[np.ix_(ground,ground)]
    np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=1e-7)
    np.testing.assert_array_equal(before,joint)
    np.linalg.cholesky(actual)
    assert info['maximum_rf_clock_correlation_before_ablation']>.01
    fitted=study.dynamic_fit.fit(own,joint_covariance=actual)
    np.testing.assert_allclose(fitted['state_ecef_m_m_s'],state,atol=.1,rtol=0)
    _,ablated,_=transport.propagate(network,requests,arcs,joint,meta['clock_observation_indices'],
        'G05',raw,code_rho=.4,receiver_fraction=.6,retain_cross=False)
    assert np.max(abs(ablated-actual))>.01
    np.linalg.cholesky(ablated)
    poisoned=deepcopy(network)
    poisoned['blocks'][0]['rows'][0]['reference']='G05'
    def forbidden(*args):raise AssertionError('candidate reached numerical response')
    monkeypatch.setattr(network_clocks,'observation_response',forbidden)
    with pytest.raises(ValueError,match='candidate RF'):
        transport.propagate(poisoned,requests,arcs,joint,meta['clock_observation_indices'],'G05',raw)


def contrast_rows():
    rng=np.random.default_rng(8701)
    rows=[]
    process=np.zeros((6,5,2))
    for k in range(450):
        process=.35*process+rng.normal(size=process.shape)*np.array([.7,.2])
        for i,s in enumerate('ABCDEF'):
            for j,q in enumerate('WXYZ'):
                z=process[i,0]+process[i,j+1]
                rows.append({'station':s,'reference':q,'time_s':30.*k,'segment':s+q,
                    'code_m':26e6+100*i+7*j+z[0],'phase_m':26e6+10*i+2*j,'mw_m':50*i+3*j+z[1]})
    return rows


def test_reference_temporal_fit_excludes_validation_and_preserves_clock_blind_mode():
    rows=contrast_rows();first=temporal_contrasts.estimate(rows)
    assert abs(first['code_endpoint_ar1_rho_30s']-.35)<.1
    assert not first['physical_temporal_covariance_qualified'] and not first['marginal_sigmas_rescaled']
    changed=deepcopy(rows)
    for r in changed:
        if r['time_s']>first['training_stop_s']:
            r['code_m']+=r['time_s']**2/1e5;r['mw_m']+=r['time_s']**2/1e6
    second=temporal_contrasts.estimate(changed)
    assert second['code_endpoint_ar1_rho_30s']==first['code_endpoint_ar1_rho_30s']
    assert second['validation']['temporal_normalized_loss']>first['validation']['temporal_normalized_loss']
    for r in changed:
        if r['time_s']<=first['training_stop_s']:
            r['code_m']+=.002*r['time_s'];r['phase_m']+=.002*r['time_s']
    third=temporal_contrasts.estimate(changed)
    np.testing.assert_allclose(third['code_endpoint_ar1_rho_30s'],first['code_endpoint_ar1_rho_30s'],atol=1e-7,rtol=0)
    assert first['split_training']['positive_semidefinite']


def test_negative_cross_split_moments_are_retained_not_forced_into_a_budget():
    rows=[]
    for k in range(40):
        for i,s in enumerate('ABC'):
            for j,q in enumerate('WXYZ'):
                z=(-1.)**k*(i-1)*(1 if j%2==0 else -1)
                rows.append({'station':s,'reference':q,'time_s':30.*k,'segment':s+q,
                    'code_m':z,'phase_m':0.,'mw_m':.3*z})
    result=temporal_contrasts.split_receiver_contrasts(rows,0.,1170.)
    assert result['cross_covariance_eigenvalues_m2'][0]<0
    assert not result['positive_semidefinite']
    assert not result['physical_receiver_covariance_qualified']
