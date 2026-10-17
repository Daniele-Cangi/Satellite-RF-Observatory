"""Candidate/time boundaries and observation-derived network transport."""
import gzip
import hashlib
import json

import numpy as np

from research.exploratory import reference_network_clocks as study
from research.exploratory.tests.test_reference_state_validation import Forbidden, poison_products
from research.kinematic.tests.test_network_clocks import toy


def test_real_network_filters_candidate_products_rf_and_future_before_arithmetic():
    _,data = study.baseline.read_inputs()
    weather = study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    expected,failures = study.reference_rows(data,'G05',36060.,weather)
    poisoned = poison_products(data,'G05')
    for epochs in poisoned['observations'].values():
        for epoch in epochs:
            for q in epoch['if_code_m']:
                if q=='G05' or epoch['time_s']>36060.:
                    epoch['if_code_m'][q] = Forbidden()
    for item in poisoned['phase']['stations'].values():
        for row in item['rows']:
            if row['reference']=='G05' or row['time_s']>36060.:
                row['phase_m'] = row['code_m'] = row['geometry_free_phase_m'] = Forbidden()
    actual,actual_failures = study.reference_rows(poisoned,'G05',36060.,weather)
    assert actual == expected and actual_failures == failures
    assert {r['station'] for r in actual} == {'ALGO00CAN','AREQ00PER','BOGT00COL','BRAZ00BRA','DRAO00CAN','STJO00CAN'}


def test_free_phase_drift_is_an_unpenalized_stability_sensitivity():
    rows = toy()
    for r in rows:
        r['phase_m'] += .002*r['time_s']*(1 if r['station']=='A' else 0)
    fixed = study.network_clocks.fit(rows)
    free = study.network_clocks.fit(rows,phase_drift=True)
    requests = [{('A',60.):1/60.,('A',0.):-1/60.},
                {('A',240.):1/60.,('A',180.):-1/60.}]
    estimates,cov = study.network_clocks.clock_coefficients(free,requests)
    _,fixed_cov = study.network_clocks.clock_coefficients(fixed,requests)
    np.testing.assert_allclose(estimates,[.01,.01],atol=1e-8,rtol=0)
    assert np.linalg.eigvalsh(cov-fixed_cov)[-1] > .001**2
    assert free['weighted_cost'] < 1e-12


def test_network_clock_transport_keeps_arc_order_and_correlations():
    network = study.network_clocks.fit(toy())
    arcs = [{'stations':list('ABC'),'endpoint_gpst_s':t,
             'covariance':study.baseline.interval.joint_covariance(3,'shared_endpoints_added')}
            for t in (240.,60.)]
    own,joint,transport = study.attach(network,arcs)
    assert [a['endpoint_gpst_s'] for a in own] == [60.,240.]
    nobs = len(own[0]['covariance'])
    for i,a in enumerate(own):
        np.testing.assert_array_equal(joint[i*nobs:(i+1)*nobs,i*nobs:(i+1)*nobs],a['covariance'])
    indices = transport['clock_observation_indices']
    np.testing.assert_array_equal(joint[np.ix_(indices,indices)],transport['clock_covariance'])
    np.linalg.cholesky(joint)
    assert transport['maximum_cross_arc_clock_covariance'] > 1.
    # Neither the input arcs nor their conditional floors are modified.
    assert 'clock_mean' not in arcs[0]


def test_all_variants_precede_rf_and_product_scoring(monkeypatch):
    events = []
    monkeypatch.setattr(study.baseline,'read_inputs',lambda: ({},{'plan':{'references':['G05','G06']}}))
    arcs = lambda q:[{'candidate':q,'endpoint_gpst_s':36060.},{'candidate':q,'endpoint_gpst_s':36240.}]
    monkeypatch.setattr(study.baseline,'build_arcs',lambda data,q,weather:(arcs(q),[{'status':'PREPARED'}]))
    monkeypatch.setattr(study,'calibrate',lambda *args,**kwargs:({'blocks':[]},[],{'status':'CONDITIONAL_MODEL_REJECTED'}))
    monkeypatch.setattr(study,'attach',lambda network,arcs:(arcs,np.eye(1),{}))
    monkeypatch.setattr(study,'held_out_links',lambda *args,**kwargs:{})
    monkeypatch.setattr(study,'injection_checks',lambda *args:{})
    monkeypatch.setattr(study,'information',lambda *args:{})
    def fit(arcs,**kwargs):
        events.append('fit '+arcs[0]['candidate'])
        assert set(kwargs) <= {'progress','joint_covariance'}
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6),
            'conditional_global_covariance':np.eye(6),'scaled_condition':1.}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    monkeypatch.setattr(study.baseline.interval,'predict',lambda *args:[])
    def score(data,q,predictions):
        assert events[:6] == ['fit G05']*3+['fit G06']*3
        events.append('score '+q)
        return {}
    monkeypatch.setattr(study.baseline,'score_rf',score)
    monkeypatch.setattr(study.baseline,'oracle',lambda *args:None)
    monkeypatch.setattr(study.baseline,'state_errors',lambda *args:{})
    result = study.run()
    assert result['all_predictions_before_scoring']
    assert result['candidates']['G05']['variants']['network']['fit']['status'] == 'REFERENCE_CALIBRATION_MODEL_REJECTED'
    assert result['candidates']['G05']['variants']['network']['fit']['algebraic_target_fit_status'] == 'BRANCH_SEARCH_INCOMPLETE'


def test_result_preserves_all_candidates_failures_covariances_and_scores():
    path = study.baseline.BASE/'results/reference_network_clocks_v1.json.gz'
    result = json.loads(gzip.decompress(path.read_bytes()))
    raw,data = study.baseline.read_inputs()
    assert result['input_sha256'] == {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    root = study.baseline.BASE.parents[1]
    for name,wanted in result['source_sha256'].items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest() == wanted
    assert set(result['candidates']) == set(data['plan']['references'])
    assert sum(len(c['windows']) for c in result['candidates'].values()) == 440
    assert sum(w['status']=='PREPARED' for c in result['candidates'].values() for w in c['windows']) == 63
    assert not any(result[k] for k in ['candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'g12_state_accessed','oracle_tuning','new_confirmation','physical_covariance_qualified','production_floors_changed'])
    for candidate,c in result['candidates'].items():
        for label,variant in c['variants'].items():
            payload = json.dumps(variant['rf_predictions'],separators=(',',':'),allow_nan=False).encode()
            assert hashlib.sha256(payload).hexdigest() == variant['prediction_sha256']
            assert study.baseline.score_rf(data,candidate,variant['rf_predictions']) == variant['rf_evaluation']
            if 'state_ecef_m_m_s' in variant['fit']:
                arcs = [{'endpoint_gpst_s':w['start_gpst_s']+60} for w in c['windows'] if w['status']=='PREPARED']
                replay = study.baseline.state_errors(variant['fit'],arcs,study.baseline.oracle(data,candidate))
                assert replay['summary']['BEYOND_ALL_TRAINING']['count'] == 1
                np.testing.assert_allclose([r['position_error_m'] for r in replay['rows']],
                    [r['position_error_m'] for r in variant['state_evaluation']['rows']],rtol=0,atol=1e-4)
                if label!='baseline':
                    requirements = variant['information']['hypothetical_independent_interval_mean_clock_sigma_m_s']
                    widths = [r['largest_position_sigma_m'] for r in requirements.values()]
                    assert all(0<x<=y for x,y in zip(widths,widths[1:]))
            if label=='baseline' or label not in c or 'transport' not in c[label]:
                continue
            cov = np.asarray(c[label]['transport']['clock_covariance'])
            np.linalg.cholesky(cov)
            assert c[label]['transport']['maximum_cross_arc_clock_covariance'] > 0
            assert c[label]['held_out_links']['whole_time_block_prediction'] == 'UNIDENTIFIABLE_WITH_FREE_EPOCH_CLOCKS'
