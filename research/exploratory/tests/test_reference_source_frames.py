"""Real admitted source frames, finite LOS derivatives and excluded identities."""
import numpy as np
import pytest

from positioning.calibration import C, OMEGA, rotate_z, geodetic, troposphere
from research.exploratory import reference_network_clocks as study, reference_geometry as geometry
from research.exploratory.tests.test_reference_state_validation import poison_products, Forbidden


def test_source_geometry_excludes_own_products_rf_and_future_before_arithmetic():
    _,data=study.baseline.read_inputs();weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    stop=36060.;first,failures=study.reference_rows(data,'G05',stop,weather,combinations=True,source_geometry=True,reference_sources=True)
    poisoned=poison_products(data,'G05')
    for epochs in poisoned['observations'].values():
        for e in epochs:
            for q in e['if_code_m']:
                if q=='G05' or e['time_s']>stop:e['if_code_m'][q]=Forbidden()
    for station in poisoned['phase']['stations'].values():
        for r in station['rows']:
            if r['reference']=='G05' or r['time_s']>stop:r['phase_m']=r['geometry_free_phase_m']=r['fields']=Forbidden()
    second,actual=study.reference_rows(poisoned,'G05',stop,weather,combinations=True,source_geometry=True,reference_sources=True)
    assert actual==failures and first==second and first
    for r in first:
        assert r['reference']!='G05' and r['time_s']<=stop
        assert np.isfinite(r['orbit_mapping']+r['antenna_mapping']).all()
        assert len(r['orbit_mapping'])==len(r['antenna_mapping'])==3


def test_emitted_source_maps_match_finite_full_range_and_vmf3_paths():
    _,data=study.baseline.read_inputs();refs=[q for q in data['plan']['references'] if q!='G05']
    provider,corrections=study.baseline.subset_products(data,refs,'G05')
    weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    station=next(iter(data['positions']));xyz=np.asarray(data['positions'][station][0]);t=36000.
    mjd=(study.datetime.fromisoformat(data['plan']['date_gpst'])-study.datetime(1858,11,17)).days
    codes=next(e['if_code_m'] for e in data['observations'][station] if e['time_s']==t)
    tested=0
    for q in refs:
        if q not in codes:continue
        code=codes[q]+corrections[t,q]['if_code_change_m']
        if provider.model(q,code,t,xyz,0.)[1]<10:continue
        maps=geometry.emitted_source_mappings(provider,weather,mjd,q,code,t,xyz,0.)
        tx,_,apc,offset=provider.antenna_state(q,code,t);com,vel=provider.precise.orbit(q,tx)
        r=com/np.linalg.norm(com);n=np.cross(com,vel+np.cross([0,0,OMEGA],com));n/=np.linalg.norm(n)
        bases={'orbit_mapping':np.column_stack([r,np.cross(n,r),n]),'antenna_mapping':provider.attitude.body_to_ecef(q,tx)}
        lat,lon,height,_=geodetic(xyz)
        def path(point):
            point=rotate_z(point,OMEGA*offset);elevation=troposphere(xyz,point)[1]
            mh,mw,dry,wet=weather.evaluate(mjd+(t-18)/86400,np.degrees(lat),np.degrees(lon),height,elevation)
            return np.linalg.norm(point-xyz)+dry*mh+wet*mw
        for name,basis in bases.items():
            expected=np.array([(path(apc+10*v)-path(apc-10*v))/20 for v in basis.T])
            np.testing.assert_allclose(maps[name],expected,atol=1e-8,rtol=0)
        tested+=1
        if tested==3:break
    assert tested==3
    with pytest.raises(ValueError,match='candidate'):
        geometry.emitted_source_mappings(provider,Forbidden(),mjd,'G05',Forbidden(),t,Forbidden(),Forbidden())


def test_all_source_and_nominal_predictions_precede_every_score(monkeypatch):
    from research.kinematic.tests.test_source_geometry import source_arcs
    arcs,_,raw,network,_,_=source_arcs();events=[]
    rows=[r for b in network['blocks'] for r in b['rows']]
    for r in rows:
        r.setdefault('geometry_free_phase_m',0.)
        t=(r['time_s']-36000)/300.;i='ABCDEF'.index(r['station'])
        r['orbit_mapping']=[np.sin(t+i),np.cos(t+.4*i),.1*i]
        r['antenna_mapping']=[-v for v in r['orbit_mapping']]
    network=study.network_clocks.fit(rows,raw_covariance=raw)
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:({'plan':b'input'},{'plan':{'references':['G05','G11','G19']}}))
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'WeatherGrid',lambda *a:None)
    monkeypatch.setattr(study.baseline.interval.shared.meteo,'read_inputs',lambda:({},{}))
    monkeypatch.setattr(study.baseline,'build_arcs',lambda d,q,w:([] if q=='G19' else [{**a,'candidate':q} for a in arcs],[{'status':'PREPARED'}]))
    monkeypatch.setattr(study,'calibrate',lambda *a,**k:(network,rows,{'status':'CONDITIONAL_MODEL_ONLY'}))
    monkeypatch.setattr(study,'target_combinations',lambda d,q,a,c:a)
    monkeypatch.setattr(study,'target_continuity',lambda d,q,a:([{**r,'phase_increment_mask':np.ones((2,len(r['stations'])),dtype=bool)} for r in a],{}))
    monkeypatch.setattr(study,'linear_response',lambda f,a,c:({'full_observation_response':np.zeros((6,len(c)))},None,None))
    monkeypatch.setattr(study,'target_wet_design',lambda f,a,w,n:np.zeros((sum(len(r['covariance']) for r in a),len(n))))
    monkeypatch.setattr(study,'predict_combinations',lambda *a,**k:[])
    def fit(a,**kwargs):
        assert set(kwargs)=={'joint_covariance','progress'}
        events.append('fit '+a[0]['candidate'])
        return {'status':'BRANCH_SEARCH_INCOMPLETE','state_ecef_m_m_s':np.zeros(6)}
    monkeypatch.setattr(study.dynamic_fit,'fit',fit)
    def score(*a):
        assert events[:2]==['fit G05','fit G11'];events.append('score');return {}
    monkeypatch.setattr(study.network_closures,'score_future_links',score)
    monkeypatch.setattr(study.baseline,'score_rf',score);monkeypatch.setattr(study,'score_mw',score)
    def forbidden(*a):raise AssertionError('CODE state scoring entered')
    monkeypatch.setattr(study.baseline,'oracle',forbidden);monkeypatch.setattr(study.baseline,'state_errors',forbidden)
    result=study.run(separate=True)
    assert result['all_predictions_before_scoring'] and not result['source_estimates_used_as_candidate_corrections']
    assert result['candidates']['G19']['fit']['status']=='INSUFFICIENT_PREPARED_ARCS'
    assert all('preparation_failure' not in result['candidates'][q] for q in ('G05','G11'))
