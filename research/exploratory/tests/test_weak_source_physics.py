"""Complete emitted-source derivatives, physical interventions and exclusions."""
import numpy as np
import pytest
from research.exploratory import reference_network_clocks as study, reference_geometry as geometry
from research.exploratory.tests.test_reference_state_validation import Forbidden,poison_products


def real_case():
    _,data=study.baseline.read_inputs();candidate='G05';refs=[q for q in data['plan']['references'] if q!=candidate]
    provider,corrections=study.baseline.subset_products(data,refs,candidate)
    weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    station=next(iter(data['positions']));xyz=np.asarray(data['positions'][station][0]);t=36000.
    codes=next(e['if_code_m'] for e in data['observations'][station] if e['time_s']==t)
    q=next(q for q in refs if q in codes and provider.model(q,codes[q]+corrections[t,q]['if_code_change_m'],t,xyz,0.)[1]>10)
    code=float(codes[q])+corrections[t,q]['if_code_change_m'];mjd=(study.datetime.fromisoformat(data['plan']['date_gpst'])-study.datetime(1858,11,17)).days
    return data,provider,weather,station,q,code,t,xyz,mjd


def test_full_source_derivatives_match_finite_products_and_hardware_time_shift():
    data,provider,weather,station,q,code,t,xyz,mjd=real_case()
    maps=geometry.emitted_source_mappings(provider,weather,mjd,q,code,t,xyz,0.,complete=True)
    def path(p,code):
        value=p.model(q,code,t,xyz,0.)[0];delay,_=study.baseline.day.atmosphere.components(p,weather,mjd,q,code,t,xyz,0.)
        return value-delay['legacy_baseline']+delay['vmf3_full']
    for family,axes in [('orbit','RTN'),('antenna','XYZ')]:
        numeric=[]
        for j in range(3):
            d=np.eye(3)[j]*10.
            a=geometry.physical_source_provider(provider,'G05',{family:{q:d}})
            b=geometry.physical_source_provider(provider,'G05',{family:{q:-d}})
            numeric.append((path(a,code)-path(b,code))/20.)
            tx,_,r,_,_,_=a.precise.emitted_state(q,code,t)
            assert np.isfinite(r).all() and abs(tx-t)<1
        np.testing.assert_allclose(maps[family+'_mapping'],numeric,atol=1e-8,rtol=0)
    # Positive hardware correction subtracts IF bias before emission inference.
    phase=(path(provider,code-100.)-path(provider,code+100.))/200.
    np.testing.assert_allclose(maps['bias_phase_mapping'],phase,atol=1e-9,rtol=0)
    assert maps['bias_code_mapping']==pytest.approx(1+phase,abs=1e-9)
    for family in ('orbit','antenna'):
        with pytest.raises(ValueError,match='before decoding'):
            geometry.physical_source_provider(provider,'G05',{family:{'G05':Forbidden()}})
    with pytest.raises(ValueError,match='before decoding'):
        geometry.physical_source_provider(provider,'G05',{'bias':{station+'/G05':Forbidden()}})


def test_physical_intervention_respects_candidate_and_future_exclusion_and_raw_mw():
    data,provider,weather,station,q,code,t,xyz,mjd=real_case();stop=36060.
    probe={'orbit':{q:[.01,-.02,.005]},'antenna':{q:[-.01,.005,0.]},'wet':{station:.005},'bias':{station+'/'+q:.03}}
    first,failures=study.reference_rows(data,'G05',stop,weather,combinations=True,source_probe=probe)
    changed=poison_products(data,'G05')
    for epochs in changed['observations'].values():
        for e in epochs:
            for key in e['if_code_m']:
                if key=='G05' or e['time_s']>stop:e['if_code_m'][key]=Forbidden()
    for item in changed['phase']['stations'].values():
        for r in item['rows']:
            if r['reference']=='G05' or r['time_s']>stop:r['phase_m']=r['geometry_free_phase_m']=r['fields']=Forbidden()
    second,actual=study.reference_rows(changed,'G05',stop,weather,combinations=True,source_probe=probe)
    assert first==second and failures==actual
    base,_=study.reference_rows(data,'G05',stop,weather,combinations=True)
    predicted_mw=-study.gnss_combinations.transform()[3,0]*.03/study.gnss_combinations.ALPHA
    for a,b in zip(base,first,strict=True):
        expected=predicted_mw if a['station']==station and a['reference']==q else 0.
        assert b['mw_m']-a['mw_m']==pytest.approx(expected,abs=1e-7)


def test_weak_source_fits_and_all_predictions_precede_rf_scoring(monkeypatch):
    import gzip,json
    from pathlib import Path
    from research.kinematic.tests.test_source_geometry import source_arcs
    arcs,_,cov,network,_,_=source_arcs();rows=[r for b in network['blocks'] for r in b['rows']]
    for r in rows:
        r.update(orbit_mapping=[0.,0.,0.],antenna_mapping=[0.,0.,0.],geometry_free_phase_m=0.)
        r.setdefault('clock_derivative',1.)
    requests=study.clock_requests(arcs);dummy={}
    for q in ('G05','G11'):
        dummy[q]={'windows':[],'prepared_arc_count':len(arcs),'fit':{'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6).tolist()},
            'source_models':{'wet_orbit_antenna_bias':{}},'reference_rows':rows,
            'clock_requests':[[[s,t,k] for (s,t),k in r.items()] for r in requests],
            'full_state_observation_response':np.zeros((6,sum(len(a['covariance']) for a in arcs))).tolist(),
            'target_wet_model_design':np.zeros((sum(len(a['covariance']) for a in arcs),6)).tolist(),
            'transport':study.attach(network,arcs)[2]}
    dummy['G19']={'windows':[],'prepared_arc_count':0,'fit':{'status':'INSUFFICIENT_PREPARED_ARCS'}}
    raw={'plan':b'input'};original_digest=study.baseline.interval.shared.digest
    prior={'input_sha256':{k:original_digest(v) for k,v in raw.items()},'candidates':dummy}
    fake=gzip.compress(json.dumps(study.native(prior)).encode());original_read=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda p:fake if p.name=='reference_source_separation_v1.json.gz' else original_read(p))
    monkeypatch.setattr(study.baseline.interval.shared,'digest',lambda b:'a8caee27bbb751090ce4af25d384bc23bad8111e2d94fe76754834f937821467' if b==fake else original_digest(b))
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:(raw,{'plan':{'references':['G05','G11','G19']}}))
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'WeatherGrid',lambda *a:None)
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'read_inputs',lambda:({},{}))
    centres={(r['station'],r['time_s']):0. for r in rows}
    monkeypatch.setattr(study,'physical_source_rows',lambda *a:(rows,centres))
    monkeypatch.setattr(study,'reference_rows',lambda *a,**k:(rows,{}))
    monkeypatch.setattr(study,'calibrate',lambda *a,**k:(network,rows,{'status':'CONDITIONAL_MODEL_ONLY'}))
    monkeypatch.setattr(study.baseline,'build_arcs',lambda d,q,w:([{**a,'candidate':q} for a in arcs],[]))
    monkeypatch.setattr(study,'target_combinations',lambda d,q,a,c:a)
    monkeypatch.setattr(study,'target_continuity',lambda d,q,a:([{**r,'phase_increment_mask':np.ones((2,len(r['stations'])),bool)} for r in a],{}))
    def modes(j,t,scale):
        v=np.zeros(j.shape[1]);v[0]=1.
        return {'weak_direction_m_per_unit_l2_m':v,'strong_direction_m_per_unit_l2_m':v,
            'thresholds':{str(tol):{'rank':0} for tol in study.source_geometry.WEAK_RTOLS}},{}
    monkeypatch.setattr(study.source_geometry,'weak_modes',modes)
    monkeypatch.setattr(study.source_geometry,'independent_information',lambda *a:{})
    monkeypatch.setattr(study.source_geometry,'known_source_recovery',lambda *a:{})
    monkeypatch.setattr(study,'fixed_wet_propagation',lambda *a:None)
    monkeypatch.setattr(study,'predict_combinations',lambda *a,**k:[])
    events=[]
    def fit(a,**kwargs):
        assert set(kwargs)=={'joint_covariance','progress'};events.append(a[0]['candidate'])
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6)}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    def score(*a):
        events.append('score');return {}
    monkeypatch.setattr(study.baseline,'score_rf',score);monkeypatch.setattr(study,'score_mw',score)
    def forbidden(*a):raise AssertionError('CODE/oracle access')
    monkeypatch.setattr(study.baseline,'oracle',forbidden);monkeypatch.setattr(study.baseline,'state_errors',forbidden)
    result=study.run(weak_sources=True)
    assert events[:4]==['G05']*2+['G11']*2, {
        q:{'preparation':c.get('preparation_failure'),'probes':[(p['status'],p.get('reason')) for p in c.get('physical_probes',[])]}
        for q,c in result['candidates'].items()}
    assert result['all_predictions_before_scoring'] and not result['archived_rf_state_used_as_fit_seed']
    assert all('preparation_failure' not in result['candidates'][q] for q in ('G05','G11'))
    assert len(result['candidates']['G05']['physical_probes'])==6
