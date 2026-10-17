"""Weak subspaces, equivalent clocks and independent-information estimability."""
import numpy as np
import pytest
from research.kinematic import source_geometry as s, network_clocks
from research.kinematic.tests.test_source_separation import rows_with_sources
from research.exploratory import reference_network_clocks as study


def test_threshold_sensitivity_and_equivalent_coordinates_preserve_declared_metric():
    j=np.diag([100.,10.,3e-8,0.]);t=np.zeros((6,4));t[0,2]=10;t[1,3]=1
    result,w=s.weak_modes(j,t,100.)
    assert [result['thresholds'][str(k)]['rank'] for k in s.WEAK_RTOLS]==[2,3,3]
    for check in result['equivalent_coordinate_checks'].values():
        assert check['rank']==3 and check['retained_projector_difference_norm']<1e-7
    q=result['weak_direction_m_per_unit_l2_m'];np.testing.assert_allclose(abs(q),[0,0,1,0],atol=1e-10)
    columns=[('wet','S','Z'),('orbit','R','R'),('antenna','R','X'),('bias','S/R','IF_CODE')]
    info=s.independent_information(w,t,columns,np.array([[0,0,0,1.]]),q)
    assert all(not g['complete_state_precision_issued'] for g in info['wet']['grid'])
    complete=info['all_source_coordinates']['grid']
    assert all(g['complete_state_precision_issued'] for g in complete)
    assert all(a['identified_projection_position_sigma_m']<b['identified_projection_position_sigma_m'] for a,b in zip(complete,complete[1:]))
    assert info['receiver_clock_endpoints']['measurement_count']==1
    with pytest.raises(ValueError,match='candidate'):s.split_probe([('orbit','TARGET','R')],[1.],'TARGET')


def test_equivalent_clock_basis_changes_neither_reference_fit_nor_source_space():
    rows,_,_=rows_with_sources();raw=study.gnss_combinations.assumed_endpoint_covariance()
    a=network_clocks.fit(rows,raw_covariance=raw);b=network_clocks.fit(rows,raw_covariance=raw,reference_rotation=.37)
    requests=[{('A',0.):1.},{('B',600.):1.}]
    xa,ca=network_clocks.clock_coefficients(a,requests);xb,cb=network_clocks.clock_coefficients(b,requests)
    np.testing.assert_allclose(xa,xb,atol=1e-7,rtol=0);np.testing.assert_allclose(ca,cb,atol=1e-8,rtol=1e-6)
    pa,wa=s.profile_sources(a,'TARGET',s.FAMILIES);pb,wb=s.profile_sources(b,'TARGET',s.FAMILIES)
    assert pa['resolved_rank']==pb['resolved_rank']
    np.testing.assert_allclose(wa['design'],wb['design'],atol=1e-8,rtol=1e-6)


def test_noiseless_incremental_recovery_excludes_unknown_real_background():
    rows,_,_=rows_with_sources();raw=study.gnss_combinations.assumed_endpoint_covariance()
    network=network_clocks.fit(rows,raw_covariance=raw);p,w=s.profile_sources(network,'TARGET',s.FAMILIES)
    u,sv,v=np.linalg.svd(w['design'],full_matrices=False);rank=p['resolved_rank']
    spec={'projector':v[:rank].T@v[:rank]};truth=v[0]*.01
    signals=[(b['rows'],g@truth) for b,g in zip(network['blocks'],w['designs'],strict=True)]
    result=s.known_source_recovery(rows,signals,signals,truth,np.zeros((6,len(truth))),spec,raw,'TARGET')
    assert all(r['injected_functional_status']=='RECOVERED' for r in result.values())
    assert all(r['relative_identified_source_error']<1e-3 for r in result.values())
    with pytest.raises(ValueError,match='candidate-excluding'):
        s.known_source_recovery([{'reference':'TARGET'}],[],[],None,None,None,None,'TARGET')
