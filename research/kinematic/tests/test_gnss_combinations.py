"""Four-channel information conservation, raw-noise assumptions and MW fits."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.linalg import block_diag, solve_triangular

from research.kinematic import gnss_combinations as combo, network_clocks, dynamic_fit
from research.kinematic.tests.test_network_clocks import toy as network_rows
from research.kinematic.tests.test_dynamic_fit import toy as target_arcs


def test_transform_is_invertible_and_profiles_gf_without_false_noise_conditioning():
    t = combo.transform()
    assert np.linalg.matrix_rank(t)==4
    raw = combo.assumed_endpoint_covariance()
    c = combo.covariance(raw)
    np.testing.assert_allclose(c.diagonal()[:2],[400.,.0004],atol=1e-12)
    assert c[1,2]/np.sqrt(c[1,1]*c[2,2]) > .97
    # Free ionosphere lives in GF alone in this basis. Its GLS elimination
    # leaves the marginal covariance of IF code/phase and MW.
    precision = np.linalg.inv(c)
    h = np.eye(4)[:,2:3]
    profiled = precision-precision@h@np.linalg.solve(h.T@precision@h,h.T@precision)
    kept = combo.RETAINED
    expected = np.zeros((4,4))
    expected[np.ix_(kept,kept)] = np.linalg.inv(c[np.ix_(kept,kept)])
    np.testing.assert_allclose(profiled,expected,atol=1e-9,rtol=1e-8)
    # Arbitrary MW bias at each endpoint destroys its extra information too:
    # profiling GF and MW leaves precisely the old IF marginal likelihood.
    h = np.eye(4)[:,2:]
    profiled = precision-precision@h@np.linalg.solve(h.T@precision@h,h.T@precision)
    np.testing.assert_allclose(profiled[:2,:2],np.linalg.inv(c[:2,:2]),atol=1e-9)
    np.testing.assert_allclose(profiled[2:],0.,atol=1e-9)
    design = np.arange(12,dtype=float).reshape(4,3)+np.eye(4,3)
    np.testing.assert_allclose(design.T@np.linalg.solve(raw,design),
        (t@design).T@np.linalg.solve(c,t@design),rtol=1e-8)


def test_identical_if_floors_do_not_identify_the_mw_covariance():
    first = combo.covariance(combo.assumed_endpoint_covariance())
    second = combo.covariance(combo.assumed_endpoint_covariance(code_correlation=.5))
    np.testing.assert_allclose(first[:2,:2],second[:2,:2],atol=1e-12)
    assert second[3,3]>2*first[3,3]
    assert first[0,3]<0 and first[1,3]>0
    fields = [26e6,26e6+10.,26e6/(combo.C/combo.F1_HZ),26e6/(combo.C/combo.F2_HZ)]
    a = combo.values(fields)
    b = combo.values(fields,code1_change_m=1.)
    np.testing.assert_allclose(b-a,combo.transform()[:,0],atol=1e-8,rtol=0)
    with pytest.raises(ValueError):
        combo.assumed_endpoint_covariance(code_correlation=1.)


def test_mw_exposes_gf_null_slip_but_not_common_nondispersive_error():
    t = combo.transform()
    wavelengths = combo.C/np.array([combo.F1_HZ,combo.F2_HZ])
    exact_null = t@np.r_[0.,0.,wavelengths*np.array([77.,60.])]
    assert abs(exact_null[2])<1e-12
    np.testing.assert_allclose(exact_null[1],exact_null[3],atol=1e-12)
    assert exact_null[3]>14.
    near_null = t@np.r_[0.,0.,wavelengths*np.array([9.,7.])]
    assert abs(near_null[2])<.004 and near_null[3]>1.7
    # First-order ionosphere has opposite code/phase signs; geometry and
    # nondispersive common errors affect all four channels in metres.
    iono = np.array([1.,(combo.F1_HZ/combo.F2_HZ)**2,
                     -1.,-(combo.F1_HZ/combo.F2_HZ)**2])
    np.testing.assert_allclose((t@iono)[[0,1,3]],0.,atol=1e-14)
    np.testing.assert_allclose(t@np.ones(4),[1.,1.,0.,0.],atol=1e-14)


@pytest.mark.parametrize('drift',[False,True])
def test_network_joint_combinations_match_full_dense_gls(drift):
    rows = network_rows()
    for r in rows:
        r['mw_m'] = 2.*ord(r['station'])+ord(r['reference'])
        if drift:
            r['mw_m'] += .3*r['time_s']/3600.
            r['phase_m'] += .2*r['time_s']/3600.
    fit = network_clocks.fit(rows,raw_covariance=combo.assumed_endpoint_covariance(),phase_drift=drift)
    blocks = fit['blocks']
    design = np.column_stack([block_diag(*[b['a'] for b in blocks]),np.vstack([b['b'] for b in blocks])])
    c = block_diag(*[b['covariance'] for b in blocks])
    chol = np.linalg.cholesky(c)
    a = solve_triangular(chol,design,lower=True)
    y = solve_triangular(chol,np.concatenate([b['y'] for b in blocks]),lower=True)
    u,s,vt = np.linalg.svd(a,full_matrices=False)
    expected = (vt.T/s)@(u.T@y)
    cov = (vt.T/s**2)@vt
    requests = [{('A',60.):1.},{('B',240.):1.},{('A',240.):1/60.,('A',180.):-1/60.}]
    x,actual = network_clocks.clock_coefficients(fit,requests)
    mapping = np.zeros((len(requests),len(expected)))
    at = 0
    for b in blocks:
        for i,request in enumerate(requests):
            for j,station in enumerate(b['stations']):
                mapping[i,at+j] = request.get((station,b['time_s']),0.)
        at += len(b['parameters'])
    np.testing.assert_allclose(x,mapping@expected,atol=1e-7,rtol=0)
    np.testing.assert_allclose(actual,mapping@cov@mapping.T,rtol=2e-7,atol=1e-7)
    assert fit['weighted_cost']<1e-12


@pytest.mark.parametrize('free',[False,True])
def test_target_joint_mw_covariance_and_free_temporal_bias_recover_state(free):
    arcs,state,_ = target_arcs()
    for a in arcs:
        a['mw_rates_m_s'] = np.tile(np.arange(6)*.001 if free else np.zeros(6),(2,1))
        a['mw_free_drift'] = free
        a['covariance'] = block_diag(combo.rf_covariance(a['tags_s'],6,combo.assumed_endpoint_covariance()),
                                      a['covariance'][30:,30:])
        # A station with no admitted MW rate retains its code and IF phase;
        # its unobserved nuisance cannot be fixed to zero for forecasting.
        if free:
            a['mw_increment_mask'] = np.ones((2,6),dtype=bool)
            a['mw_increment_mask'][:,0] = False
    before = deepcopy(arcs)
    fitted = dynamic_fit.fit(arcs,joint_covariance=block_diag(*[a['covariance'] for a in arcs]))
    np.testing.assert_allclose(fitted['state_ecef_m_m_s'],state,rtol=0,atol=.1)
    assert fitted['weighted_residual_cost']<1e-6
    for a,p in zip(arcs,fitted['arc_parameters'],strict=True):
        assert np.asarray(p['station_corrections_m']).shape==(6,3)
        if free:
            assert p['mw_rate_bias_m_s'][0] is None
            np.testing.assert_allclose(p['mw_rate_bias_m_s'][1:],np.arange(1,6)*.001,atol=1e-7)
    for a,b in zip(arcs,before,strict=True):
        np.testing.assert_array_equal(a['covariance'],b['covariance'])


@pytest.mark.parametrize('cycles',[(77,60),(9,7)])
def test_joint_likelihood_does_not_automatically_repair_gf_null_slips(cycles):
    arcs,state,_ = target_arcs()
    for a in arcs:
        a['mw_rates_m_s'] = np.zeros((2,6))
        a['covariance'] = block_diag(combo.rf_covariance(a['tags_s'],6,
            combo.assumed_endpoint_covariance()),a['covariance'][30:,30:])
    delta = combo.transform()@np.r_[0.,0.,
        combo.C/np.array([combo.F1_HZ,combo.F2_HZ])*np.asarray(cycles)]
    assert abs(delta[2])<.004  # Below the existing GF witness threshold.
    arcs[0]['rates_m_s'][0,0] += delta[1]/30.
    arcs[0]['mw_rates_m_s'][0,0] += delta[3]/30.
    joint = block_diag(*[a['covariance'] for a in arcs])
    contaminated = dynamic_fit.fit(arcs,joint_covariance=joint)
    assert contaminated['status']=='MODEL_REJECTED'
    assert np.linalg.norm(np.asarray(contaminated['state_ecef_m_m_s'])[:3]-state[:3])>100.
    # A supported external boundary can use the existing free-jump path for
    # both IF and MW. This test supplies the known synthetic boundary, not an
    # automatic detector or an estimate from the contaminated target state.
    mask = np.ones((2,6),dtype=bool)
    mask[0,0] = False
    arcs[0]['phase_increment_mask'] = mask
    arcs[0]['mw_increment_mask'] = mask.copy()
    supported_boundary = dynamic_fit.fit(arcs,joint_covariance=joint)
    np.testing.assert_allclose(supported_boundary['state_ecef_m_m_s'],state,atol=.1,rtol=0)
    assert supported_boundary['weighted_residual_cost']<1e-6
