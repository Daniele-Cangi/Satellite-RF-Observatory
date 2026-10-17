"""Every calibration/state probe precedes excluded scoring; no CODE is read."""
import numpy as np

from research.exploratory import reference_network_clocks as study
from research.kinematic.tests.test_temporal_shared_rf import prepared


def test_all_state_probes_and_future_link_predictions_precede_scoring(monkeypatch):
    arcs,_,_,network,_,_ = prepared()
    rows = [r for b in network['blocks'] for r in b['rows']]
    events = []
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:({'plan':b'input'},{'plan':{'references':['G05','G11','G19']}}))
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'WeatherGrid',lambda *a:None)
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'read_inputs',lambda:({},{}))
    monkeypatch.setattr(study.baseline,'build_arcs',lambda d,q,w:([] if q=='G19' else [{**a,'candidate':q} for a in arcs],[{'status':'PREPARED'}]))
    monkeypatch.setattr(study,'calibrate',lambda *a,**k:(network,rows,{'status':'CONDITIONAL_MODEL_ONLY'}))
    monkeypatch.setattr(study,'target_combinations',lambda d,q,a,c:a)
    monkeypatch.setattr(study,'target_continuity',lambda d,q,a:([
        {**r,'phase_increment_mask':np.ones((2,len(r['stations'])),dtype=bool)} for r in a],{}))
    monkeypatch.setattr(study,'predict_combinations',lambda *a:[])
    monkeypatch.setattr(study.network_closures,'closure_records',lambda n,q:{'rows':[
        {'code_closure_m':0.,'phase_closure_m':0.} for b in n['blocks'] for r in b['rows']]})
    monkeypatch.setattr(study.network_closures,'prepare_future_links',lambda *a:{'status':'FUTURE_LINK_PREDICTIONS_FROZEN'})
    monkeypatch.setattr(study.network_closures,'state_transfer',lambda *a:{'modes':{
        label:{'status':'PROBE_PREPARED','reference_change_m':np.zeros(len(rows)),
               'linear_state_change_m_m_s':np.zeros(6)} for label in ('clock_blind','cycle_visible')}})
    monkeypatch.setattr(study,'linear_response',lambda f,a,c:({'full_observation_response':np.zeros((6,len(c)))},None,None))
    def fit(a,**kwargs):
        events.append('fit '+a[0]['candidate'])
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6)}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    def score(*args):
        assert events[:6] == ['fit G05']*3+['fit G11']*3
        events.append('score')
        return {}
    monkeypatch.setattr(study.network_closures,'score_future_links',score)
    monkeypatch.setattr(study.baseline,'score_rf',score)
    monkeypatch.setattr(study,'score_mw',score)
    def forbidden(*args):
        raise AssertionError('candidate CODE scoring entered')
    monkeypatch.setattr(study.baseline,'oracle',forbidden)
    monkeypatch.setattr(study.baseline,'state_errors',forbidden)
    result = study.run(closures=True)
    assert result['all_predictions_before_scoring']
    assert not result['candidate_code_orbit_scoring']
    assert set(result['candidates'])=={'G05','G11','G19'}
    assert result['candidates']['G19']['variants']['clock_blind']['fit']['status']=='INSUFFICIENT_PREPARED_ARCS'
