"""Restricted source information, held-out isolation and both physical paths."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.linalg import block_diag, solve_triangular

from research.kinematic import network_clocks, network_closures, source_geometry as sources
from research.kinematic.synthetic import native
from research.kinematic.tests.test_network_closures import reference_rows
from research.kinematic.tests.test_temporal_shared_rf import prepared
from research.exploratory import reference_network_clocks as study


def wet_rows():
    rows = reference_rows()
    for r in rows:
        i,j = 'ABCDEF'.index(r['station']), 'WXYZ'.index(r['reference'])
        r['wet_mapping'] = 2.+.3*np.sin(r['time_s']/150.+.2*i+.5*j)+.03*(i+1)*(j+1)*r['time_s']/1000.
        r['zenith_wet_m'] = .15
    return rows


def test_profiled_source_fit_matches_dense_joint_gls_and_rejects_clock_alias():
    rows = [r for r in wet_rows() if r['time_s']<=330.]
    true = dict(zip('ABCDEF',np.linspace(-.04,.06,6),strict=True))
    for r in rows:
        r['code_m'] += r['wet_mapping']*true[r['station']]
        r['phase_m'] += r['wet_mapping']*true[r['station']]
    raw = study.gnss_combinations.assumed_endpoint_covariance()
    network = network_clocks.fit(rows,raw_covariance=raw)
    profile = sources.profile_wet(network,'TARGET')
    assert profile['status']=='CONDITIONAL_SOURCE_FIT'
    np.testing.assert_allclose(list(profile['zenith_wet_correction_m'].values()),list(true.values()),atol=1e-7,rtol=0)
    blocks = network['blocks']; names=profile['stations']
    design = np.column_stack([block_diag(*[b['a'] for b in blocks]),np.vstack([b['b'] for b in blocks]),
        np.vstack([sources.wet_design(b,names) for b in blocks])])
    chol = np.linalg.cholesky(block_diag(*[b['covariance'] for b in blocks]))
    u,s,vt = np.linalg.svd(solve_triangular(chol,design,lower=True),full_matrices=False)
    gain = (vt.T/s)@u.T
    expected = gain@solve_triangular(chol,np.concatenate([b['y'] for b in blocks]),lower=True)
    np.testing.assert_allclose(expected[-6:],list(true.values()),atol=1e-7,rtol=0)
    np.testing.assert_allclose(profile['conditional_parameter_covariance_m2'],(gain@gain.T)[-6:,-6:],atol=1e-5,rtol=1e-6)
    alias = [{**r,'wet_mapping':r['clock_derivative']} for r in rows]
    unavailable = sources.profile_wet(network_clocks.fit(alias,raw_covariance=raw),'TARGET')
    assert unavailable['status']=='SOURCE_RANK_DEFICIENT' and unavailable['resolved_rank']==0
    assert 'zenith_wet_correction_m' not in unavailable
    poisoned = deepcopy(network);poisoned['blocks'][0]['rows'][0]['reference']='TARGET'
    with pytest.raises(ValueError,match='candidate-excluding'):
        sources.profile_wet(poisoned,'TARGET')


def test_wet_future_prediction_omits_withheld_if_gf_and_preserves_missing_clocks():
    rows = wet_rows()
    for r in rows:
        z = .02*('ABCDEF'.index(r['station'])+1)
        r['code_m'] += r['wet_mapping']*z
        r['phase_m'] += r['wet_mapping']*z
    raw = study.gnss_combinations.assumed_endpoint_covariance()
    first = network_closures.prepare_future_links(rows,'TARGET',raw,wet_sources=True)
    assert first['status']=='FUTURE_LINK_PREDICTIONS_FROZEN'
    assert first['source_model']['status']=='CONDITIONAL_SOURCE_FIT'
    scored = network_closures.score_future_links(first,rows)
    for r in scored['increment_errors']:
        assert r['count']>0
        np.testing.assert_allclose(r['code_phase_rms_error_m'],0.,atol=2e-7,rtol=0)
    changed = deepcopy(rows);held=set(first['held_links'])
    class Forbidden:
        def __float__(self):raise AssertionError('withheld GF used')
    for r in changed:
        if (r['station'],r['reference']) in held and r['time_s']>first['training_stop_s']:
            r['code_m'] += .1*np.sin(r['time_s']/150.)
            r['phase_m'] -= .05*np.sin(r['time_s']/150.)
            r['geometry_free_phase_m']=Forbidden();r['segment']='forbidden future GF'
    second = network_closures.prepare_future_links(changed,'TARGET',raw,wet_sources=True)
    assert native(first)==native(second)
    scored = network_closures.score_future_links(second,changed)
    assert scored['increment_errors'][0]['code_phase_rms_error_m'][1]>.001
    # A source alias is an unavailable model, not a nominal-clock fallback.
    alias=[{**r,'wet_mapping':r['clock_derivative']} for r in rows]
    failed=network_closures.prepare_future_links(alias,'TARGET',raw,wet_sources=True)
    assert failed['status']=='HELD_OUT_SOURCE_UNOBSERVABLE' and not failed['predictions']


class ZeroWetWeather:
    def evaluate(self,mjd,lat,lon,height,elevation):
        return 0.,1./np.sin(np.radians(elevation)),0.,0.


def source_arcs():
    arcs,state,raw,network,_,_ = prepared()
    rows = [deepcopy(r) for b in network['blocks'] for r in b['rows']]
    for r in rows:
        i,j = 'ABCDEF'.index(r['station']), 'XYZ'.index(r['reference'])
        r.update(wet_mapping=2.+.3*np.sin((r['time_s']-36000)/150.+.2*i+.5*j),zenith_wet_m=.1)
    network=network_clocks.fit(rows,raw_covariance=raw)
    arcs,joint,metadata=study.attach(network,arcs)
    curve=study.baseline.dynamics.Trajectory(state,[-100.,1900.])
    for a in arcs:
        # The vacuum fixture's D ray is below the unchanged atmospheric mask.
        # Move the invented station, then regenerate its RF from the same truth.
        a['stations_m']=a['stations_m'].copy()
        angle=np.deg2rad(15.);x,y=a['stations_m'][3,:2]
        a['stations_m'][3,:2]=[np.cos(angle)*x-np.sin(angle)*y,np.sin(angle)*x+np.cos(angle)*y]
        endpoint=a['endpoint_gpst_s']-36060.
        pair=study.baseline.interval.clock_observations.predict(curve,endpoint,a['tags_s'],a['stations_m'],
            a['clock_mean'],[70000.+endpoint*.1,.1,0.],a['receiver_clock_basis'])
        a['codes_m']=pair['code_m']+np.array([-30.,10.,60.,-40.,20.,-20.])
        a['rates_m_s']=np.diff(pair['code_m'],axis=0)/30.
        a['propagation']=study.fixed_wet_propagation(ZeroWetWeather(),a['stations'],{})
    arcs[0]['phase_increment_mask']=np.ones((2,6),dtype=bool)
    arcs[0]['phase_increment_mask'][0,0]=False
    arcs[0]['mw_increment_mask']=arcs[0]['phase_increment_mask'].copy()
    return arcs,state,raw,network,joint,metadata


def test_source_response_matches_full_reference_and_candidate_refits():
    arcs,state,raw,network,joint,meta=source_arcs()
    weather=ZeroWetWeather()
    fitted=study.dynamic_fit.fit(arcs,joint_covariance=joint)
    details,_,_=study.linear_response(fitted,arcs,joint)
    response=details['full_observation_response'][:6]
    assert np.count_nonzero(response[:,18])==0
    names=sorted({r['station'] for b in network['blocks'] for r in b['rows']})
    reference=sources.clock_wet_response(network,study.clock_requests(arcs),'TARGET',names)
    target=study.target_wet_design(fitted,arcs,weather,names)
    result=sources.coupled_response(response,meta['clock_observation_indices'],reference,target,names)
    assert result['status']=='SOURCE_PROBE_PREPARED'
    z=result['zenith_probe_m'];vector=np.array([z[s] for s in names])
    matrices=result['state_model_response_m_m_s_per_m_zenith']
    np.testing.assert_allclose(matrices['coupled'],matrices['reference_only']+matrices['candidate_only'],atol=1e-12)
    rows=[{**r,'code_m':r['code_m']-r['wet_mapping']*z[r['station']],
        'phase_m':r['phase_m']-r['wet_mapping']*z[r['station']]} for b in network['blocks'] for r in b['rows']]
    recalibrated=network_clocks.fit(rows,raw_covariance=raw)
    changed,_,_=study.attach(recalibrated,arcs)
    for a,old in zip(changed,arcs,strict=True):a['covariance']=old['covariance']
    for label in ('reference_only','candidate_only','coupled'):
        own=[{**a} for a in (arcs if label=='candidate_only' else changed)]
        if label!='reference_only':
            for a in own:a['propagation']=study.fixed_wet_propagation(weather,a['stations'],z)
        actual=study.dynamic_fit.fit(own,joint_covariance=joint)
        delta=np.array(actual['state_ecef_m_m_s'])-fitted['state_ecef_m_m_s']
        expected=matrices[label]@vector
        np.testing.assert_allclose(delta[:3],expected[:3],atol=.02,rtol=.01)
        np.testing.assert_allclose(delta[3:],expected[3:],atol=2e-5,rtol=.02)
        predictions=study.predict_combinations(actual,own,weather,zenith_wet_m=z if label!='reference_only' else None)
        assert all(p['status']=='PREDICTED' for p in predictions)


def test_shared_receiver_clock_source_cancels_only_with_its_candidate_path():
    arcs,_,_,network,joint,meta=source_arcs()
    fitted=study.dynamic_fit.fit(arcs,joint_covariance=joint)
    details,_,prepared=study.linear_response(fitted,arcs,joint)
    response=details['full_observation_response'][:6]
    names=list('ABCDEF')
    clock_network=deepcopy(network)
    start=min(b['time_s'] for b in network['blocks'])
    for b in clock_network['blocks']:
        for r in b['rows']:
            # A time-constant station offset is already absorbed by free code
            # contrasts. A shared drift exercises the actual state coupling.
            r['wet_mapping']=r.get('clock_derivative',1.)*(1+(r['time_s']-start)/1800.)
    reference=sources.clock_wet_response(clock_network,study.clock_requests(arcs),'TARGET',names)
    curve=study.baseline.dynamics.Trajectory(fitted['state_ecef_m_m_s'],fitted['integrated_bounds_s'],j2=fitted['j2'],sensitivities=True)
    pieces=[]
    for a,p in zip(prepared,fitted['arc_parameters'],strict=True):
        local=np.r_[p['satellite_clock'],np.array(p['receiver_clocks']).ravel(),np.array(p['station_corrections_m']).ravel()]/a['local_scale']
        _,pair=study.dynamic_fit.model(curve,a,local,fitted['bias_contrast_coefficients_m'],fitted['epoch_gpst_s'],derivatives=True)
        code=np.zeros((a['codes'].size,6))
        clock_shape=1+(a['endpoint_gpst_s']+a['tags']-start)/1800.
        for j,s in enumerate(a['stations']):
            code[j::a['n'],names.index(s)]=pair['receiver_clock_derivative'][:,j]*clock_shape
        g=np.zeros((a['full_observation_count'],6));g[:len(code)]=code
        d=study.dynamic_fit.interval_matrix(a['tags'],a['n']);g[len(code):len(code)+len(d)]=d@code
        pieces.append(g)
    result=sources.coupled_response(response,meta['clock_observation_indices'],reference,np.vstack(pieces),names)
    maps=result['state_model_response_m_m_s_per_m_zenith']
    assert np.max(abs(maps['reference_only']))>1.
    assert np.max(abs(maps['coupled']))<1e-5
    assert result['status']=='NO_RESOLVED_SOURCE_POSITION_PROBE'
