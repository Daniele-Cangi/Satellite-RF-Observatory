"""Raw readout, shared COM origin and actual calibration-level information."""
import numpy as np
import pytest
from scipy.linalg import solve_triangular
from research.kinematic import source_geometry as s
from research.kinematic.gnss_combinations import ALPHA,BETA


def test_shared_origin_and_unique_station_wet_and_frequency_readouts():
    rows=[{'station':'S','reference':q,'time_s':t} for t in (36000.,36300.) for q in ('R1','R2')]
    cols=s.source_columns(rows,s.FAMILIES)
    geometry={'orbit_mapping':[.4,.5,.7],'body_mapping':[.2,.3,.9],
        'optical_zenith_mapping':2.,'epoch_light_time_mapping':1e-6,'range_scale_mapping':.8}
    ranges=[{**r,'status':'TWO_WAY_GEOMETRY_PREPARED','geometry':geometry} for r in rows]
    cat=s.complementary_observable_catalog(rows,cols,ranges,'TARGET');metadata=cat['readouts']
    assert sum(r['family']=='wet' for r in metadata)==2
    assert sum(r['family']=='antenna' for r in metadata)==12
    keys=cat['nuisance_columns'];origin=keys.index(('origin','R1','X'));frequency=keys.index(('frequency_difference','R1','X'))
    first=next(i for i,r in enumerate(metadata) if r['family']=='range' and r['key']=='S/R1')
    ant=[i for i,r in enumerate(metadata) if r['family']=='antenna' and r['key'].startswith('R1/X/')]
    assert cat['nuisance_design'][first,origin]==.2
    np.testing.assert_array_equal(cat['nuisance_design'][ant,origin],[-1.,-1.])
    np.testing.assert_allclose(cat['nuisance_design'][ant,frequency],[-BETA,ALPHA])
    np.testing.assert_allclose(np.array([ALPHA,BETA])@cat['nuisance_design'][ant,frequency],0.,atol=1e-14)
    from research.exploratory.tests.test_reference_state_validation import Forbidden
    with pytest.raises(ValueError,match='candidate-excluding'):
        s.complementary_observable_catalog([{'reference':'TARGET','station':'S','time_s':Forbidden()}],None,None,'TARGET')


def test_calibration_relative_levels_anchor_and_repetition_floor():
    keys=[('wet_zero',k,'Z') for k in ('A','B')]
    relative,meta=s.calibration_level_operator(keys,'relative');anchored,anchor_meta=s.calibration_level_operator(keys,'anchored_relative')
    np.testing.assert_allclose(relative@np.ones(2),0.,atol=1e-15)
    assert np.linalg.matrix_rank(anchored)==2 and meta['unobserved_level_null_count']==1
    assert anchor_meta['anchors']==[keys[0]]
    free,_=s.profile_observable_calibration(np.eye(2),np.eye(2),keys,.1,'relative',.01)
    np.testing.assert_allclose(free@np.ones(2),0.,atol=1e-12)
    for count in (1,100):
        h=np.ones((count,1));b=h.copy();one=[('wet_zero','A','Z')]
        z,_=s.profile_observable_calibration(h,b,one,.1,'free')
        assert np.linalg.norm(z)<1e-12
        z,_=s.profile_observable_calibration(h,b,one,.1,'absolute',.02)
        assert 1/np.linalg.norm(z)==pytest.approx(np.sqrt(.1**2/count+.02**2),rel=1e-12)


@pytest.mark.parametrize('rho',[0.,.5])
def test_raw_frequency_if_variance_and_origin_calibration_are_propagated(rho):
    h=np.ones((2,1));b=np.array([[-BETA,-1.],[ALPHA,-1.]])
    keys=[('frequency_difference','R','X'),('origin','R','X')]
    chol=np.linalg.cholesky(np.array([[1.,rho],[rho,1.]]));h=solve_triangular(chol,h,lower=True);b=solve_triangular(chol,b,lower=True)
    variance=.01**2*(ALPHA**2+BETA**2+2*ALPHA*BETA*rho)
    ideal,meta=s.profile_observable_calibration(h,b,keys,.01,'ideal')
    assert meta['frequency_differences_remain_free']
    assert 1/np.linalg.norm(ideal)**2==pytest.approx(variance,rel=1e-12)
    real,_=s.profile_observable_calibration(h,b,keys,.01,'absolute',.03)
    assert 1/np.linalg.norm(real)**2==pytest.approx(variance+.03**2,rel=1e-12)


def test_joint_nuisance_profile_matches_independent_schur_information_and_hardware_gap():
    h=np.array([[1.,2.],[2.,-.5],[.3,.2]]);b=np.array([[1.,.5],[0.,1.],[.2,2.]])
    keys=[('origin','R1','X'),('origin','R2','X')];sigma=.2;cal=.03
    actual,meta=s.profile_observable_calibration(h,b,keys,sigma,'anchored_relative',cal,response=True)
    c,_=s.calibration_level_operator(keys,'anchored_relative');bb=b.T@b/sigma**2+c.T@c/cal**2;cross=h.T@b/sigma**2
    expected=h.T@h/sigma**2-cross@np.linalg.solve(bb,cross.T)
    np.testing.assert_allclose(actual.T@actual,expected,atol=1e-11,rtol=1e-12)
    np.testing.assert_allclose(meta['source_to_nuisance_response'],-np.linalg.solve(bb,cross.T),atol=1e-12,rtol=1e-12)
    cols=[('bias',k,'IF_CODE') for k in ('A/R1','A/R2','B/R1','B/R2')];gap=s.hardware_component_gap(cols)
    a=gap['raw_p1_to_total_if_incidence'];n=len(gap['component_keys']);q=np.arange(1.,5.)
    total=np.column_stack([a,np.eye(4)]);component=np.column_stack([np.eye(n),np.zeros((n,4))]);gauge=np.r_[np.zeros(n),q]
    np.testing.assert_array_equal(total@gauge,q);np.testing.assert_array_equal(component@gauge,np.zeros(n))
    assert gap['profiled_component_information_on_total_link_bias_rank']==0


def test_matrix_projector_replays_existing_source_design_without_fitting_sources():
    from research.kinematic.tests.test_complementary_sources import fixture
    rows,cov,network,profile,work,spectrum=fixture()
    matrix=s.profiled_increment(network,work['designs'])
    np.testing.assert_allclose(matrix,work['design'],atol=1e-10,rtol=1e-12)
    direction=np.arange(matrix.shape[1],dtype=float)/100.
    vector=s.profiled_increment(network,[g@direction for g in work['designs']])
    np.testing.assert_allclose(matrix@direction,vector,atol=1e-10,rtol=1e-12)
