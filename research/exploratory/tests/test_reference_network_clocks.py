"""Candidate/time boundaries and observation-derived network transport."""
import gzip
from collections import defaultdict
import hashlib
import json
import subprocess

import numpy as np
import pytest

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


@pytest.mark.parametrize('training_phase_level',[False,True])
def test_unobserved_phase_terms_preserve_supported_code(training_phase_level):
    rows = toy()
    for r in rows:
        if r['station']=='A' and r['reference']=='X' and (
                r['time_s']==240. or training_phase_level and r['time_s']==210.):
            r['segment'] = 'short AX'
    # Put the last sample in the deterministic holdout while the other one
    # trains the float level. The free slope has no observation.
    row = next(r for r in rows if r['segment']=='short AX' and r['time_s']==240.)
    rows.remove(row)
    rows.insert(0,row)
    result = study.held_out_links(rows,phase_drift=True)
    held = next(r for r in result['rows'] if r['segment']=='short AX' and r['time_s']==240.)
    assert held['status']=='PARTIALLY_EVALUATED'
    assert held['code_status']=='EVALUATED'
    assert held['code_error_m']==pytest.approx(0.,abs=1e-8)
    assert held['phase_status']==('UNIDENTIFIABLE_PHASE_DRIFT' if training_phase_level else 'UNOBSERVED_SEGMENT')
    assert 'phase_error_m' not in held


def test_heldout_correction_replays_without_changing_the_original_result():
    original = (study.baseline.BASE/'results/reference_network_clocks_v1.json.gz').read_bytes()
    result = json.loads(gzip.decompress(original))
    before = json.dumps(result,separators=(',',':'))
    previous_bytes = (study.baseline.BASE/'results/reference_network_clocks_heldout_correction_v1.json').read_bytes()
    previous = json.loads(previous_bytes)
    actual = study.held_out_support_correction(result,hashlib.sha256(original).hexdigest(),hashlib.sha256(previous_bytes).hexdigest())
    stored = json.loads((study.baseline.BASE/'results/reference_network_clocks_heldout_correction_v2.json').read_bytes())
    assert {k:v for k,v in actual.items() if k!='source_sha256'} == {
        k:v for k,v in stored.items() if k!='source_sha256'}
    for name,wanted in stored['source_sha256'].items():
        producer = subprocess.check_output(['git','show','2d4bc3a04cc737d65a82cc517bf2fde1a0937acb:'+name],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(producer).hexdigest()==wanted
    # The superseded correction remains byte/source bound; its four code
    # exclusions are diagnosed, not silently rewritten to the new counts.
    for name,wanted in previous['source_sha256'].items():
        original_source = subprocess.check_output(['git','show','b2998c65c2ca3519080393f56d2088a1210f1456:'+name],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(original_source).hexdigest() == wanted
    assert sum(c['code_error_m']['count'] for c in previous['candidates'].values())==3041
    assert json.dumps(result,separators=(',',':')) == before
    assert sum(len(c['invalidated_rows']) for c in actual['candidates'].values()) == 4
    assert sum(c['code_status_counts'].get('EVALUATED',0) for c in actual['candidates'].values()) == 3045
    assert sum(c['phase_status_counts'].get('EVALUATED',0) for c in actual['candidates'].values()) == 3041
    for q,c in actual['candidates'].items():
        assert c['code_error_m']==result['candidates'][q]['network_free_phase_drift']['held_out_links']['code_error_m']
    assert not actual['trajectories_or_candidate_predictions_changed']


@pytest.mark.parametrize('oracle_fails',[False,True])
@pytest.mark.parametrize('diagnostic_fails',[False,True])
def test_all_variants_precede_rf_and_product_scoring(monkeypatch,oracle_fails,diagnostic_fails):
    events = []
    monkeypatch.setattr(study.baseline,'read_inputs',lambda: ({},{'plan':{'references':['G05','G06']}}))
    arcs = lambda q:[{'candidate':q,'endpoint_gpst_s':36060.},{'candidate':q,'endpoint_gpst_s':36240.}]
    monkeypatch.setattr(study.baseline,'build_arcs',lambda data,q,weather:(arcs(q),[{'status':'PREPARED'}]))
    monkeypatch.setattr(study,'calibrate',lambda *args,**kwargs:({'blocks':[]},[],{'status':'CONDITIONAL_MODEL_REJECTED'}))
    monkeypatch.setattr(study,'attach',lambda network,arcs:(arcs,np.eye(1),{}))
    monkeypatch.setattr(study,'held_out_links',lambda *args,**kwargs:{})
    def diagnostic(*args):
        if diagnostic_fails:
            raise ValueError('synthetic network diagnostic failure')
        return {}
    monkeypatch.setattr(study,'injection_checks',diagnostic)
    monkeypatch.setattr(study,'information',lambda *args:{})
    def fit(arcs,**kwargs):
        events.append('fit '+arcs[0]['candidate'])
        assert set(kwargs) <= {'progress','joint_covariance'}
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6),
            'conditional_global_covariance':np.eye(6),'scaled_condition':1.}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    monkeypatch.setattr(study.baseline.interval,'predict',lambda *args:[])
    def score(data,q,predictions):
        count = 2 if diagnostic_fails else 3
        assert events[:2*count] == ['fit G05']*count+['fit G06']*count
        events.append('score '+q)
        return {}
    monkeypatch.setattr(study.baseline,'score_rf',score)
    def oracle(data,candidate):
        if oracle_fails and candidate=='G05':
            raise ValueError('synthetic unavailable oracle')
        return None
    monkeypatch.setattr(study.baseline,'oracle',oracle)
    monkeypatch.setattr(study.baseline,'state_errors',lambda *args:{})
    result = study.run()
    assert result['all_predictions_before_scoring']
    if diagnostic_fails:
        assert result['candidates']['G05']['variants']['network']['fit']['status']=='NETWORK_UNAVAILABLE'
        assert result['candidates']['G05']['network']['calibration']['status']=='NETWORK_FAILED'
    else:
        assert result['candidates']['G05']['variants']['network']['fit']['status'] == 'REFERENCE_CALIBRATION_MODEL_REJECTED'
        assert result['candidates']['G05']['variants']['network']['fit']['algebraic_target_fit_status'] == 'BRANCH_SEARCH_INCOMPLETE'
    if oracle_fails:
        assert result['candidates']['G05']['variants']['network_free_phase_drift']['state_evaluation']['status']=='ORACLE_UNAVAILABLE'


def test_result_preserves_all_candidates_failures_covariances_and_scores():
    path = study.baseline.BASE/'results/reference_network_clocks_v1.json.gz'
    result = json.loads(gzip.decompress(path.read_bytes()))
    raw,data = study.baseline.read_inputs()
    assert result['input_sha256'] == {k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    root = study.baseline.BASE.parents[1]
    for name,wanted in result['source_sha256'].items():
        # Retain this completed producer as ancestry while active code adds
        # disconnected-graph checks and per-candidate oracle failure handling.
        original = subprocess.check_output(['git','show','197468e5aceadf9917e34a71dfdcef5bf9c2445f:'+name],cwd=root)
        assert hashlib.sha256(original).hexdigest() == wanted
    assert set(result['candidates']) == set(data['plan']['references'])
    assert sum(len(c['windows']) for c in result['candidates'].values()) == 440
    assert sum(w['status']=='PREPARED' for c in result['candidates'].values() for w in c['windows']) == 63
    assert not any(result[k] for k in ['candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'g12_state_accessed','oracle_tuning','new_confirmation','physical_covariance_qualified','production_floors_changed'])
    for candidate,c in result['candidates'].items():
        if 'network' in c:
            rows = c['network']['calibration']['residuals']
            held = {(r['time_s'],r['station'],r['reference']) for r in c['network']['held_out_links']['rows']}
            for withheld in (False,True):
                epochs = defaultdict(list)
                for r in rows:
                    if not withheld or (r['time_s'],r['station'],r['reference']) not in held:
                        epochs[r['time_s']].append(r)
                for own in epochs.values():
                    stations = sorted({r['station'] for r in own})
                    references = sorted({r['reference'] for r in own})
                    incidence = np.zeros((len(own),len(stations)+len(references)))
                    for i,r in enumerate(own):
                        incidence[i,stations.index(r['station'])] = 1.
                        incidence[i,len(stations)+references.index(r['reference'])] = -1.
                    assert np.linalg.matrix_rank(incidence) == incidence.shape[1]-1
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
