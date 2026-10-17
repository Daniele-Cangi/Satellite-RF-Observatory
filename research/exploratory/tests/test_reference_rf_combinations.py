"""Admitted raw RF, observable-specific support and combined forecast order."""
import numpy as np
import pytest
from copy import deepcopy
from scipy.linalg import block_diag

from research.exploratory import reference_network_clocks as study
from research.exploratory.tests.test_reference_state_validation import Forbidden, poison_products
from research.kinematic.tests.test_network_clocks import toy
from research.kinematic.tests.test_dynamic_fit import toy as target_arcs


def test_reference_raw_combinations_exclude_candidate_and_future_before_decoding():
    _,data = study.baseline.read_inputs()
    weather = study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    expected,failures = study.reference_rows(data,'G05',36060.,weather,continuity=True,combinations=True)
    data = poison_products(data,'G05')
    for es in data['observations'].values():
        for e in es:
            for q in e['if_code_m']:
                if q=='G05' or e['time_s']>36060.:
                    e['if_code_m'][q] = Forbidden()
    for item in data['phase']['stations'].values():
        for r in item['rows']:
            if r['reference']=='G05' or r['time_s']>36060.:
                for key in ('fields','code_m','phase_m','geometry_free_phase_m'):
                    r[key] = Forbidden()
    actual,bad = study.reference_rows(data,'G05',36060.,weather,continuity=True,combinations=True)
    assert actual==expected and bad==failures
    assert all(np.isfinite(r['mw_m']) for r in actual)


def test_mw_prediction_does_not_require_an_observed_epoch_clock():
    rows = toy()
    for r in rows:
        r['mw_m'] = 1. if r['station']=='A' else 2.
    missing = [r for r in rows if r['station']=='A' and r['time_s']==0.]
    remaining = [r for r in rows if r not in missing]
    ordered = []
    for r in missing:
        ordered.append(r)
        ordered.extend(remaining[:6]);remaining=remaining[6:]
    ordered.extend(remaining)
    result = study.held_out_links(ordered,raw_covariance=study.gnss_combinations.assumed_endpoint_covariance())
    assert result['status']=='RELATIVE_SHARED_PRODUCT_DIAGNOSTIC'
    actual = [r for r in result['rows'] if r['station']=='A' and r['time_s']==0.]
    assert len(actual)==3
    assert all(r['code_status']=='UNOBSERVED_CLOCK' and r['mw_status']=='EVALUATED' for r in actual)
    assert all(abs(r['mw_error_m'])<1e-7 for r in actual)


def test_target_combinations_do_not_decode_globally_excluded_rf():
    fields = [[26e6+i,26e6+i+2.,14e7+i,11e7+i] for i in range(3)]
    rows = [{'reference':'G05','time_s':30.*i,'status':'AVAILABLE','fields':f} for i,f in enumerate(fields)]
    rows += [{'reference':'G05','time_s':90.,'status':'AVAILABLE','fields':Forbidden()},
             {'reference':'G06','time_s':0.,'status':'AVAILABLE','fields':Forbidden()}]
    data = {'phase':{'stations':{'A':{'rows':rows}}}}
    arcs = [{'stations':['A'],'endpoint_gpst_s':60.,'tags_s':[-60.,-30.,0.],
        'codes_m':np.array([[study.gnss_combinations.values(f)[0]] for f in fields]),'covariance':np.eye(11)}]
    own = study.target_combinations(data,'G05',arcs,study.gnss_combinations.assumed_endpoint_covariance())
    assert own[0]['covariance'].shape==(13,13)
    assert own[0]['mw_rates_m_s'].shape==(2,1)
    np.linalg.cholesky(own[0]['covariance'])
    np.testing.assert_array_equal(own[0]['codes_m'],arcs[0]['codes_m'])


@pytest.mark.parametrize('mode',['combinations','temporal'])
def test_all_combination_models_finish_before_any_rf_or_oracle_score(monkeypatch,mode):
    events=[]
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:({},{'plan':{'references':['G05','G06']}}))
    monkeypatch.setattr(study.baseline,'build_arcs',lambda d,q,w:([
        {'candidate':q,'endpoint_gpst_s':36060.},{'candidate':q,'endpoint_gpst_s':36240.}],[]))
    monkeypatch.setattr(study,'calibrate',lambda *a,**k:({'blocks':[]},[],{'status':'CONDITIONAL_MODEL_ONLY'}))
    monkeypatch.setattr(study,'target_combinations',lambda d,q,a,c,**k:a)
    monkeypatch.setattr(study,'target_continuity',lambda d,q,a:(a,{}))
    monkeypatch.setattr(study,'attach',lambda n,a:(a,np.eye(1),{}))
    monkeypatch.setattr(study,'held_out_links',lambda *a,**k:{})
    monkeypatch.setattr(study,'information',lambda *a:{})
    if mode=='temporal':
        labels=('joint_independent','temporal_code','temporal_shared','temporal_without_cross')
        monkeypatch.setattr(study,'prepare_temporal',lambda d,q,a,w:(
            {label:(a,np.eye(1)) for label in labels},
            {label:{'calibration':{'status':'CONDITIONAL_MODEL_ONLY'}} for label in labels},{}))
    def fit(a,**kw):
        events.append('fit '+a[0]['candidate'])
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6),
                'conditional_global_covariance':np.eye(6),'scaled_condition':1.}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    monkeypatch.setattr(study,'predict_combinations',lambda *a:[])
    def score(*args):
        assert events[:8]==['fit G05']*4+['fit G06']*4
        events.append('score')
        return {}
    monkeypatch.setattr(study.baseline,'score_rf',score)
    monkeypatch.setattr(study,'score_mw',score)
    monkeypatch.setattr(study.baseline,'oracle',lambda *a:None)
    monkeypatch.setattr(study.baseline,'state_errors',lambda *a:{})
    result = study.run(**{mode:True})
    assert result['all_predictions_before_scoring']
    assert result['schema']==('exposed-temporal-shared-rf-v1' if mode=='temporal' else 'exposed-joint-rf-combinations-v1')
    assert not result['raw_covariance_qualified']


def test_common_raw_band_error_is_recalibrated_before_target_refitting():
    arcs,state,_ = target_arcs()
    raw = study.gnss_combinations.assumed_endpoint_covariance()
    rows=[]
    for a in arcs:
        a['clock_mean'] = np.column_stack([a['clock_mean'],np.zeros(6)])
        a['receiver_clock_basis'] = study.baseline.interval.clock_basis(a['tags_s'])
        a['satellite_clock_count'] = 3
        a['mw_rates_m_s'] = np.zeros((2,6))
        old = study.baseline.interval.joint_covariance(6,'shared_endpoints_added')
        a['covariance'] = block_diag(study.gnss_combinations.rf_covariance(a['tags_s'],6,raw),old[30:,30:])
        for dt in a['tags_s']:
            for i,s in enumerate(a['stations']):
                clock = a['clock_mean'][i,0]+dt*a['clock_mean'][i,1]
                for j,q in enumerate('XYZ'):
                    rows.append({'station':s,'reference':q,'time_s':a['endpoint_gpst_s']+dt,
                        'segment':f'{s}/{q}/{a["endpoint_gpst_s"]}',
                        'code_m':clock,'phase_m':clock+100*i+5*j,'mw_m':30*i+2*j})
    network = study.network_clocks.fit(rows,raw_covariance=raw)
    own,cov,_ = study.attach(network,arcs)
    baseline = study.dynamic_fit.fit(own,joint_covariance=cov)
    np.testing.assert_allclose(baseline['state_ecef_m_m_s'],state,atol=.1,rtol=0)
    # One metre in P1, shared by all reference links and the target receiver.
    # This is an injected sensitivity amplitude, never an uncertainty sigma.
    delta = study.gnss_combinations.transform()[:,0]
    changed=deepcopy(arcs)
    end=arcs[0]['endpoint_gpst_s']
    changed[0]['codes_m'][-1,0] += delta[0]
    changed[0]['mw_rates_m_s'][-1,0] += delta[3]/30.
    contaminated=deepcopy(rows)
    for r in contaminated:
        if r['station']=='A' and r['time_s']==end:
            r['code_m'] += delta[0]
            r['phase_m'] += delta[1]
            r['mw_m'] += delta[3]
    recalibrated = study.network_clocks.fit(contaminated,raw_covariance=raw)
    full,joint,_ = study.attach(recalibrated,changed)
    coupled = study.dynamic_fit.fit(full,joint_covariance=joint)
    target_only,old_cov,_ = study.attach(network,changed)
    incomplete = study.dynamic_fit.fit(target_only,joint_covariance=old_cov)
    assert np.linalg.norm(np.asarray(coupled['state_ecef_m_m_s'])[:3]-
                          np.asarray(incomplete['state_ecef_m_m_s'])[:3]) > .01
    assert not np.array_equal(full[0]['clock_mean'],target_only[0]['clock_mean'])


def test_unsupported_temporal_shape_retains_baseline_and_every_failed_variant(monkeypatch):
    from research.kinematic.tests.test_temporal_shared_rf import prepared
    arcs,_,_,network,_,_ = prepared()
    monkeypatch.setattr(study,'calibrate',lambda *a,**k:(network,[],{'status':'CONDITIONAL_MODEL_ONLY'}))
    monkeypatch.setattr(study,'target_combinations',lambda d,q,a,c:a)
    monkeypatch.setattr(study,'held_out_links',lambda *a,**k:{})
    monkeypatch.setattr(study,'target_continuity',lambda d,q,a:([
        {**r,'phase_increment_mask':np.ones((2,len(r['stations'])),dtype=bool)} for r in a],{}))
    def unsupported(rows):raise ValueError('no supported temporal lag')
    monkeypatch.setattr(study.temporal_contrasts,'estimate',unsupported)
    calibrated,records,model=study.prepare_temporal({},'G05',arcs,None)
    assert set(calibrated)=={'joint_independent'}
    assert model['preparation_status']=='TEMPORAL_COVARIANCE_PREPARATION_FAILED'
    for label in ('temporal_code','temporal_shared','temporal_without_cross'):
        assert records[label]['covariance_status']=='UNAVAILABLE'
        assert 'no supported temporal lag' in records[label]['reason']
