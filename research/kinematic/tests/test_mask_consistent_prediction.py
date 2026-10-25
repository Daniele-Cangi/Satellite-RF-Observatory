"""Actual exclusion, complete native response and correlated error images."""
from copy import deepcopy

import numpy as np
import pytest

from research.kinematic import mask_consistent_prediction as model, gnss_combinations
from research.kinematic.tests.test_source_geometry import wet_rows
from research.exploratory.reference_network_clocks import native


def rows():
    return [r for r in wet_rows() if r['time_s'] <= 690.]


def test_native_prediction_response_replays_and_matches_independent_refit():
    original = rows()
    held = next(r for r in original if r['station']=='A' and r['reference']=='W' and r['time_s']==600.)
    admitted = [r for r in original if not (r['station']=='A' and r['reference']=='W' and r['time_s']>300.)]
    raw = gnss_combinations.assumed_endpoint_covariance()
    training, network, workspace = model._fit(admitted, 'TARGET', raw)
    prefix = model._prefix(training, 300.)
    queries = [(held, model._segment(held, prefix)), ({**held,'reference':'UNOBSERVED'}, None)]
    predictions, response = model.prediction_response(network, workspace, queries, channels=(0,1))
    matrices = list(response)
    replay = sum(h@b['y'] for b,h in matrices)
    assert predictions[0]['status']=='PREDICTED'
    assert predictions[1]['status']=='UNOBSERVED_NETWORK_CLOCK'
    np.testing.assert_allclose(replay[:2],
        [predictions[0]['path_prediction_m'], predictions[0]['phase_prediction_m']], atol=2e-7, rtol=0)
    np.testing.assert_array_equal(replay[2:], 0.)
    changed = deepcopy(admitted)
    delta = {}
    for i,r in enumerate(changed):
        direction = np.array([np.sin(i),np.cos(.3*i),np.sin(.7*i)])*.001
        delta[r['station'],r['reference'],r['time_s']] = direction
        for j,k in enumerate(('code_m','phase_m','mw_m')):
            r[k] += direction[j]
    _, other, new_workspace = model._fit(changed, 'TARGET', raw)
    expected, _ = model.prediction_response(other, new_workspace, queries[:1], channels=(0,1))
    measured = np.array([expected[0]['path_prediction_m']-predictions[0]['path_prediction_m'],
                         expected[0]['phase_prediction_m']-predictions[0]['phase_prediction_m']])
    transported = sum(h[:2]@np.array([delta[r['station'],r['reference'],r['time_s']][j]
                      for j in range(3) for r in b['rows']]) for b,h in matrices)
    np.testing.assert_allclose(measured, transported, rtol=2e-5, atol=2e-8)


def test_covariance_image_preserves_correlation_and_rejects_unknown_component():
    c = np.array([[1.,.8],[.8,1.]])
    errors = np.array([1.,-1.])
    solved, whiten, rank = model.image_solve(c, errors)
    np.testing.assert_allclose(solved, np.linalg.solve(c,errors), atol=1e-12)
    np.testing.assert_allclose(whiten.T@c@whiten, np.eye(2), atol=1e-12)
    assert rank==2 and np.array([.5,.2])@solved == pytest.approx(1.5)
    assert np.array([.5,.2])@errors == pytest.approx(.3)  # Diagonal substitution differs.
    solved, _, rank = model.image_solve(np.ones((2,2)), [2.,2.])
    assert rank==1
    np.testing.assert_allclose(solved, [1.,1.], atol=1e-12)
    with pytest.raises(ValueError,match='outside'):
        model.image_solve(np.ones((2,2)), [1.,-1.])
    with pytest.raises(ValueError,match='semidefinite'):
        model.image_solve([[1.,2.],[2.,1.]], [1.,1.])


def test_prefix_likelihood_reports_zero_and_positive_process_variance():
    signal = np.linalg.cholesky(np.exp(-abs(np.subtract.outer(np.arange(20),np.arange(20)))/4.))
    noise = np.eye(20)*.001
    zero = model.fit_variance(np.zeros(20),noise,signal)
    assert zero['status']=='FITTED_ZERO_PREDICTIVE_VARIANCE'
    assert zero['variance_zenith_m2']==0.
    positive = model.fit_variance(np.sin(np.arange(20)/3.),noise,signal)
    assert positive['variance_zenith_m2']>0.
    assert positive['negative_twice_loglikelihood_change']<0.
    assert not positive['physical_wet_covariance_qualified']
    with pytest.raises(ValueError,match='no resolved'):
        model.fit_variance(np.zeros(20),noise,np.zeros((20,3)))


def test_error_conditioning_matches_full_joint_gaussian_with_shared_calibration_noise():
    # Four actual excluded errors and a different outer error share raw noise.
    # The full raw covariance is an independent route to the expected answer.
    raw = np.diag([.2,.3,.4,.5,.6,.7])
    raw[0,1]=raw[1,0]=.1
    observed = np.array([[1.,-.4,0.,0.,.1,0.],[0.,1.,-.3,0.,0.,.2],
                         [.1,0.,1.,-.6,0.,0.],[0.,.2,0.,1.,-.1,0.]])
    outer = np.array([[-.1,0.,-.2,.3,0.,1.]])
    field = np.array([[1.,0.],[1.1,0.],[0.,1.],[0.,.8],[.5,.2],[.4,.6]])
    variance=.07
    full = raw+variance*(field@field.T)
    e=np.array([.02,-.03,.01,.04])
    expected=(outer@full@observed.T)@np.linalg.solve(observed@full@observed.T,e)
    actual, rank=model.condition_errors(e,observed@raw@observed.T,outer@raw@observed.T,
                                       observed@field,outer@field,variance)
    np.testing.assert_allclose(actual,expected,atol=1e-12,rtol=0)
    assert rank==4
    # Enlarging one process direction must not discard an unrelated, ordinary
    # noise direction by changing the numerical rank threshold.
    correction,rank=model.condition_errors(np.array([1.,2.]),np.eye(2),np.array([[0.,1.]]),
                                          np.array([[1.],[0.]]),np.zeros((1,1)),1e15)
    assert correction[0]==pytest.approx(2.) and rank==2


def test_outer_holdout_poisoning_and_actual_inner_group_exclusion(monkeypatch):
    original = rows()
    raw = gnss_combinations.assumed_endpoint_covariance()
    captured = []
    actual_fit = model._fit
    def capture(admitted,*args):
        captured.append([(r['station'],r['reference'],r['time_s']) for r in admitted])
        return actual_fit(admitted,*args)
    monkeypatch.setattr(model,'_fit',capture)
    first = model.prepare_future_links(original,'TARGET',raw)
    assert first['model_status']=='CONDITIONAL_MASK_CONSISTENT_MODEL',first.get('reason')
    inner_cut = first['inner_training_stop_s']
    for group, keys in enumerate(captured[:7]):
        assert not any(t>inner_cut and model.link_group({'station':s,'reference':q})==group for s,q,t in keys)
    assert first['maximum_absolute_off_diagonal_noise_covariance_m2']>0.
    class Forbidden:
        def __float__(self):
            raise AssertionError('outer held RF used')
    changed = deepcopy(original)
    held_links = set(map(tuple,first['baseline']['held_links']))
    for r in changed:
        if (r['station'],r['reference']) in held_links and r['time_s']>first['baseline']['training_stop_s']:
            for k in ('code_m','phase_m','mw_m','geometry_free_phase_m'):
                r[k]=Forbidden()
            r['segment']='forbidden-whole-data-GF'
    other = model.prepare_future_links(changed,'TARGET',raw)
    assert native(first)==native(other)
    with pytest.raises(ValueError,match='candidate'):
        model.prepare_future_links([{'reference':'TARGET','time_s':Forbidden()}],'TARGET',raw)


def test_failed_predictive_fit_does_not_silently_substitute_native_baseline(monkeypatch):
    def fail(*args):
        raise ValueError('forced covariance-model failure')
    monkeypatch.setattr(model,'fit_variance',fail)
    result = model.prepare_future_links(rows(),'TARGET',gnss_combinations.assumed_endpoint_covariance())
    assert result['model_status']=='UNSUPPORTED_MASK_CONSISTENT_MODEL'
    assert result['reason']=='forced covariance-model failure'
    original = result['baseline']['predictions']
    variant = result['variants']['mask_consistent']['predictions']
    assert len(original)==len(variant)
    assert any(p['status']=='PREDICTED' for p in original)
    assert all(p['status']!='PREDICTED' for p in variant)
