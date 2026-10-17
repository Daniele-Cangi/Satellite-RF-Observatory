"""Known-increment projection and complementary, joint observation laws."""
import numpy as np
import pytest
from scipy.linalg import block_diag,solve_triangular
from research.kinematic import source_geometry as s,network_clocks
from research.exploratory import reference_network_clocks as study
from research.kinematic.tests.test_source_separation import rows_with_sources


def fixture():
    rows,_,_=rows_with_sources();cov=study.gnss_combinations.assumed_endpoint_covariance()
    network=network_clocks.fit(rows,raw_covariance=cov);profile,w=s.profile_sources(network,'TARGET',s.FAMILIES)
    u,sv,v=np.linalg.svd(w['design'],full_matrices=False)
    return rows,cov,network,profile,w,{'u':u,'s':sv,'v':v,'rank':profile['resolved_rank']}


def test_projected_recovery_matches_full_fit_and_refuses_unidentified_functional():
    rows,cov,network,profile,w,spec=fixture();truth=spec['v'][0]*.01
    blocks=[g@truth for g in w['designs']]
    quick=s.recover_profiled_increment(s.profiled_increment(network,blocks),w['design'],spec,truth,np.zeros((6,len(truth))))
    signals=[(b['rows'],g) for b,g in zip(network['blocks'],blocks,strict=True)]
    old=s.known_source_recovery(rows,signals,signals,truth,np.zeros((6,len(truth))),{'projector':spec['v'][:spec['rank']].T@spec['v'][:spec['rank']]},cov,'TARGET')
    np.testing.assert_allclose(quick['fitted_source_projection_m'],old['linear_control']['fitted_source_projection_m'],atol=1e-7,rtol=1e-4)
    assert quick['status']=='IDENTIFIED_PROJECTION_RECOVERED' and quick['injected_functional_status']=='RECOVERED'
    truth=spec['v'][spec['rank']]*.01
    null=s.recover_profiled_increment(np.zeros(len(w['design'])),w['design'],spec,truth,np.zeros((6,len(truth))))
    assert null['injected_functional_status']=='UNIDENTIFIABLE_INJECTED_FUNCTIONAL'


def test_complementary_measurements_keep_free_offsets_and_absolute_rank_cuts():
    j=np.diag([100.,10.,3e-8,0.]);t=np.zeros((6,4));t[0,2]=10;t[1,3]=1;q=np.array([0,0,1.,0])
    cols=[('wet','S','Z'),('orbit','R','R'),('antenna','R','X'),('bias','S/R','IF_CODE')]
    result=s.complementary_source_information(j,cols,t,q,100.)
    assert len(result)==15
    all_sources=result['wet_orbit_antenna_bias'];direct=all_sources['independent']['grid']
    for a in direct:
        for tol,z in a['rank_cases'].items():
            assert z['absolute_singular_cut']==float(tol)*100 and z['complete_state_precision_issued']
    for a,b in zip(direct,direct[1:]):
        assert a['rank_cases']['1e-10']['identified_projection_position_sigma_m']<b['rank_cases']['1e-10']['identified_projection_position_sigma_m']
    free=all_sources['family_offset_free'];assert free['raw_measurement_count']==4 and free['retained_contrast_count']==0
    assert all(not g['rank_cases']['1e-10']['complete_state_precision_issued'] for g in free['grid'])


def test_joint_external_clock_information_matches_full_nuisance_projection():
    rows,cov,network,profile,w,spec=fixture();keys=[(station,b['time_s']) for b in network['blocks'] for station in b['stations']]
    sigma=.02;rho=.5;actual,meta=s.joint_external_clock_source_design(network,w['columns'],keys,sigma,'TARGET',epoch_correlation=rho)
    stations=sorted({a for a,b in keys});nb=len(network['ambiguities_m']);aa=[];bb=[];gg=[];ext=[];offset=[]
    for block,g in zip(network['blocks'],w['designs'],strict=True):
        def white(x):return solve_triangular(block['chol'],x,lower=True)
        aa.append(white(block['a']));bb.append(white(block['b']));gg.append(white(g))
        n=len(block['stations']);chol=np.linalg.cholesky(sigma**2*((1-rho)*np.eye(n)+rho*np.ones((n,n))))
        e=np.zeros((n,block['a'].shape[1]));e[:,:n]=np.eye(n);ext.append(solve_triangular(chol,e,lower=True))
        o=np.zeros((n,len(stations)))
        for i,station in enumerate(block['stations']):o[i,stations.index(station)]=1
        offset.append(solve_triangular(chol,o,lower=True))
    a=block_diag(*aa);e=block_diag(*ext);b=np.vstack(bb);g=np.vstack(gg);o=np.vstack(offset)
    nuisance=np.block([[a,b,np.zeros((len(a),len(stations)))],[e,np.zeros((len(e),nb)),o]])
    source=np.vstack([g,np.zeros((len(e),len(w['columns'])))])
    norms=np.linalg.norm(nuisance,axis=0);normalized=np.divide(nuisance,norms,out=np.zeros_like(nuisance),where=norms>0)
    u,sv,_=np.linalg.svd(normalized,full_matrices=False);rank=int(sum(sv>sv[0]*1e-12));expected=source-u[:,:rank]@(u[:,:rank].T@source)
    np.testing.assert_allclose(actual.T@actual,expected.T@expected,atol=1e-5,rtol=1e-6)
    assert meta['external_endpoint_count']==len(keys) and meta['instrument_offsets_profiled_without_prior']
    assert meta['external_source_shift_KG_not_treated_as_direct_observation']
    with pytest.raises(ValueError,match='candidate-excluding'):
        s.joint_external_clock_source_design({'blocks':[{'rows':[{'reference':'TARGET'}]}]},None,[],None,'TARGET')
