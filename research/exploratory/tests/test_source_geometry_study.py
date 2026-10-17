"""Admitted geometry, source signs and complete scoring chronology."""
import numpy as np

from research.exploratory import reference_network_clocks as study
from research.exploratory.tests.test_reference_state_validation import poison_products, Forbidden
from research.kinematic.tests.test_source_geometry import source_arcs


def test_reference_wet_geometry_and_model_change_exclude_candidate_and_future():
    _,data=study.baseline.read_inputs()
    weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    stop=36060.
    first,failures=study.reference_rows(data,'G05',stop,weather,combinations=True,source_geometry=True)
    poisoned=poison_products(data,'G05')
    for epochs in poisoned['observations'].values():
        for e in epochs:
            for q in e['if_code_m']:
                if q=='G05' or e['time_s']>stop:e['if_code_m'][q]=Forbidden()
    for station in poisoned['phase']['stations'].values():
        for r in station['rows']:
            if r['reference']=='G05' or r['time_s']>stop:
                r['phase_m']=r['geometry_free_phase_m']=r['fields']=Forbidden()
    second,actual=study.reference_rows(poisoned,'G05',stop,weather,combinations=True,source_geometry=True)
    assert actual==failures and first==second
    stations={r['station'] for r in first}
    minus,_=study.reference_rows(data,'G05',stop,weather,combinations=True,zenith_wet_m={s:-.01 for s in stations})
    plus,_=study.reference_rows(data,'G05',stop,weather,combinations=True,zenith_wet_m={s:.01 for s in stations})
    assert len(first)==len(minus)==len(plus)>0
    for r,a,b in zip(first,minus,plus,strict=True):
        assert r['reference']!='G05' and r['time_s']<=stop
        assert r['wet_mapping']>1 and r['zenith_wet_m']>=0
        np.testing.assert_allclose((b['code_m']-a['code_m'])/.02,-r['wet_mapping'],atol=1e-6,rtol=1e-5)
        assert a['mw_m']==b['mw_m']==r['mw_m']


def test_source_calibrations_fits_and_predictions_all_precede_scoring(monkeypatch):
    arcs,_,_,network,_,_=source_arcs()
    rows=[r for b in network['blocks'] for r in b['rows']]
    names=list('ABCDEF');events=[]
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:({'plan':b'input'},{'plan':{'references':['G05','G11','G19']}}))
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'WeatherGrid',lambda *a:None)
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'read_inputs',lambda:({},{}))
    monkeypatch.setattr(study.baseline,'build_arcs',lambda d,q,w:([] if q=='G19' else [{**a,'candidate':q} for a in arcs],[{'status':'PREPARED'}]))
    monkeypatch.setattr(study,'calibrate',lambda *a,**k:(network,rows,{'status':'CONDITIONAL_MODEL_ONLY'}))
    monkeypatch.setattr(study,'target_combinations',lambda d,q,a,c:a)
    monkeypatch.setattr(study,'target_continuity',lambda d,q,a:([
        {**r,'phase_increment_mask':np.ones((2,len(r['stations'])),dtype=bool)} for r in a],{}))
    monkeypatch.setattr(study.source_geometry,'profile_wet',lambda *a:{'stations':names})
    monkeypatch.setattr(study.network_closures,'prepare_future_links',lambda *a,**k:{'status':'FUTURE_LINK_PREDICTIONS_FROZEN'})
    monkeypatch.setattr(study,'linear_response',lambda f,a,c:({'full_observation_response':np.zeros((6,len(c)))},None,None))
    monkeypatch.setattr(study,'target_wet_design',lambda f,a,w,n:np.zeros((sum(len(r['covariance']) for r in a),len(n))))
    monkeypatch.setattr(study.source_geometry,'coupled_response',lambda *a:{'status':'SOURCE_PROBE_PREPARED',
        'zenith_probe_m':dict.fromkeys(names,0.),'linear_probe_state_change_m_m_s':{
            k:np.zeros(6) for k in ('reference_only','candidate_only','coupled')}})
    monkeypatch.setattr(study,'fixed_wet_propagation',lambda *a:None)
    monkeypatch.setattr(study,'predict_combinations',lambda *a,**k:[])
    def fit(a,**kwargs):
        assert set(kwargs)=={'joint_covariance','progress'}
        events.append('fit '+a[0]['candidate'])
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6)}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    def score(*a):
        assert events[:8]==['fit G05']*4+['fit G11']*4
        events.append('score');return {}
    monkeypatch.setattr(study.network_closures,'score_future_links',score)
    monkeypatch.setattr(study.baseline,'score_rf',score)
    monkeypatch.setattr(study,'score_mw',score)
    def forbidden(*a):raise AssertionError('CODE state scoring entered')
    monkeypatch.setattr(study.baseline,'oracle',forbidden)
    monkeypatch.setattr(study.baseline,'state_errors',forbidden)
    result=study.run(sources=True)
    assert result['all_predictions_before_scoring'] and not result['source_estimates_used_as_candidate_corrections']
    assert all(v['fit']['status']=='INSUFFICIENT_PREPARED_ARCS' for v in result['candidates']['G19']['variants'].values())
