"""Reference exclusion, clock gauge and complete transfer failures."""
from copy import deepcopy
from types import SimpleNamespace
import json

import numpy as np
import pytest

from research.exploratory import reference_bias_transfer as study
from research.exploratory import reference_geometry as geometry


def synthetic():
    refs = ['P','A','B','C','D','E']
    stations = [f'S{i}' for i in range(6)]
    times = [0,30,60,90]
    rng = np.random.default_rng(72)
    rays = rng.normal(size=(6,3))
    rays[:,2] = abs(rays[:,2])
    rays /= np.linalg.norm(rays,axis=1)[:,None]
    lookup = dict(zip(refs,rays))
    codes = {(s,t):{sv:1e6+1000+lookup[sv]@np.array([.2,-.4,.7])*(i+1)
                   for sv in refs} for i,s in enumerate(stations) for t in times}
    baseline = {'rows':[{'station':s,'time_s':t,'reference':sv}
                        for s in stations for t in times for sv in refs]}
    plan = {'minimum_remaining_references':4,'maximum_clock_iterations':8,
            'clock_closure_tolerance_m':1e-6,'maximum_reference_rms_m':20.,
            'maximum_reference_abs_m':50.,'maximum_split_clock_m':30.}
    original = {'references':refs,'stations':stations,'training_before_gpst_s':60}
    context = (plan,original,SimpleNamespace(times=times),None,None,None,baseline)
    old = {'rows':[]}
    for q in refs:
        for s in stations:
            for t in (60,90):
                clock = np.mean([v-1e6 for sv,v in codes[s,t].items() if sv!=q])
                old['rows'].append({'pseudo_target':q,'station':s,'time_s':t,'status':'ADMITTED',
                    'models':{'zero':{'status':'EVALUATED','error_m':codes[s,t][q]-1e6-clock}}})
    return context,codes,lambda *args:1e6,lambda s,t,sv:lookup[sv],old


def test_direction_transfer_recovers_a_known_error_law_in_the_clock_datum():
    context,codes,model,direction,old = synthetic()
    result = study.evaluate(context,codes,model,direction,old)
    assert len(result['rows']) == 6*6*2
    assert all(f['rank']==18 for f in result['fits'])
    assert result['summary']['paired']['direction']['rms_m'] < 1e-7
    assert result['summary']['paired']['zero']['rms_m'] > .1


def test_poisoned_training_pseudotarget_and_future_values_cannot_train_coefficients():
    context,codes,model,direction,old = synthetic()
    first = study.evaluate(context,codes,model,direction,old,excluded_references=['P'])
    changed = deepcopy(codes)
    class Poison:
        def __float__(self):
            raise AssertionError('excluded training pseudo-target decoded')
        def __sub__(self, other):
            raise AssertionError('excluded training pseudo-target read')
    for (s,t),block in changed.items():
        if t<60:
            block['P'] = Poison()
        else:
            block.update({sv:Poison() for sv in block})
    altered = deepcopy(old)
    for row in altered['rows']:
        row['models']['zero']['error_m'] += 4000.
    def guarded_direction(s,t,sv):
        assert t>=60 or sv!='P'
        return direction(s,t,sv)
    second = study.evaluate(context,changed,model,guarded_direction,altered,excluded_references=['P'])
    assert first['fits'] == second['fits']
    for a,b in zip(first['rows'],second['rows'],strict=True):
        assert a['direction']['prediction_m'] == b['direction']['prediction_m']
        assert b['direction']['error_m']-a['direction']['error_m'] == pytest.approx(4000.)


def test_unidentifiable_direction_and_missing_station_do_not_receive_zero_corrections():
    rays = [[.6,0,.8],[-.6,0,.8],[0,.6,.8],[0,-.6,.8]]
    training = [{'station':'S','time_s':0,'reference':str(i),
                 'los_enu':r,'residual_m':r[0]} for i,r in enumerate(rays)]
    fit = study.fit_direction(training)
    assert fit['rank'] == 2
    assert study.predict_contrast(fit,'S',[0,0,1],rays)['status']=='UNIDENTIFIABLE_PREDICTION'
    assert study.predict_contrast(fit,'UNKNOWN',rays[0],rays)['status']=='UNSEEN_STATION'
    assert study.predict_contrast(fit,'S',rays[0],rays)['prediction_m']==pytest.approx(.6)


def test_any_training_block_failure_retains_the_fold_without_subset_rescue():
    context,codes,model,direction,old = synthetic()
    for row in context[-1]['rows'][:]:
        if row['station']=='S0' and row['time_s']==0 and row['reference'] in ['D','E']:
            context[-1]['rows'].remove(row)
    result = study.evaluate(context,codes,model,direction,old,excluded_references=['P'])
    assert result['fits'][0]['status']=='TRAINING_BLOCK_FAILURE'
    assert result['fits'][0]['failed_blocks'][0]['status']=='INSUFFICIENT_REMAINING_REFERENCES'
    assert len(result['rows'])==12
    assert all(r['direction']['status']=='TRAINING_BLOCK_FAILURE' for r in result['rows'])


def test_mode_projection_cancels_common_clock_and_never_renormalizes_missing_stations():
    stations = [f'S{i}' for i in range(6)]
    weights = np.array([1.,-1.,0,0,0,0])/np.sqrt(2)
    rows = [{'pseudo_target':'P','station':s,'time_s':t,'zero_error_m':2*i+1000.,
             'direction':{'status':'PREDICTED','error_m':float(i)+2000.}}
            for t in [0,30] for i,s in enumerate(stations)]
    rows[-1]['direction']={'status':'UNIDENTIFIABLE_PREDICTION'}
    result = study.mode_projection(rows,stations,weights,['P'],[0,30])
    assert result['status_counts']=={'EVALUATED':1,'INSUFFICIENT_STATION_COVERAGE':1}
    assert result['blocks'][0]['zero_m']==pytest.approx(-np.sqrt(2))
    assert result['blocks'][0]['direction_m']==pytest.approx(-1/np.sqrt(2))
    assert 'zero_m' not in result['blocks'][1]
    with pytest.raises(ValueError,match='duplicate'):
        study.mode_projection(rows+[rows[0]],stations,weights,['P'],[0,30])


def test_vacuum_direction_uses_no_observation_and_preserves_sagnac_sign():
    class Provider:
        def antenna_state(self, sv, code, t):
            clock = 1e-5
            return 0.,clock,np.array([26e6,0,0]),-code/geometry.C-clock
    ray = geometry.vacuum_direction(Provider(),np.array([6378137.,0,0]),0.,'P')
    assert np.linalg.norm(ray)==pytest.approx(1.,abs=1e-14)
    assert ray[0]<0 and abs(ray[1])<1e-14 and ray[2]>.999


def test_geometry_rejects_real_target_before_provider_access(monkeypatch):
    monkeypatch.setattr(geometry.day.frame,'guarded_products',lambda *a:(None,None,{}))
    monkeypatch.setattr(geometry.day.frame,'load_attitude',lambda *a:(None,{}))
    class Forbidden:
        def antenna_state(self,*a):
            pytest.fail('unadmitted geometry reached reference provider')
    monkeypatch.setattr(geometry.day.frame,'AttitudeReference',lambda *a:Forbidden())
    context = (None,{'references':['G05'],'stations':['S']},
               SimpleNamespace(target='G12',times=[0]),None,
               {'S':[[6378137.,0,0]]},None,{'product_sha256':{}})
    direction = geometry.environment(context)
    for excluded in ['G12','UNKNOWN']:
        with pytest.raises(ValueError,match='geometry boundary'):
            direction('S',0,excluded)


def test_real_transfer_retains_degradation_all_slots_and_sparse_mode_coverage():
    result = json.loads((study.BASE/'results/reference_bias_transfer_v1.json').read_bytes())
    old = json.loads((study.BASE/'results/pseudotarget_v1.json').read_bytes())
    assert not result['real_target_measurements_used_for_calibration']
    assert not result['real_target_orbit_used'] and not result['target_fit_performed']
    assert result['target_mode_used_only_for_diagnostic_projection']
    assert not result['physical_covariance_qualified'] and not result['production_floors_changed']
    assert len(result['fits'])==22 and all(f['rank']==21 for f in result['fits'])
    assert all(not f['failed_blocks'] for f in result['fits'])
    summary = study.summarize(result['rows'],result['stations'])
    assert summary==result['summary']
    assert summary['status_counts']=={'PSEUDO_TARGET_NOT_ADMITTED':5452,'PREDICTED':3942}
    assert {(r['pseudo_target'],r['station'],r['time_s']) for r in result['rows']} == {
        (r['pseudo_target'],r['station'],r['time_s']) for r in old['rows']}
    assert summary['paired']['direction']['rms_m'] > summary['paired']['zero']['rms_m']
    assert sum(v['direction']['rms_m']>v['zero']['rms_m'] for v in summary['per_station'].values())==4
    p = result['mode_projection']
    assert p['status_counts']=={'INSUFFICIENT_STATION_COVERAGE':1310,'EVALUATED':32}
    assert p['supported_references']=={'G05':19,'G11':13}
    assert p['direction']['rms_m']>p['zero']['rms_m']
    replay = study.mode_projection(result['rows'],p['stations'],p['unit_station_weights'],
                                   result['references'],result['test_times_s'])
    assert replay['status_counts']==p['status_counts']
    assert replay['supported_references']==p['supported_references']
    for actual,stored in zip(replay['blocks'],p['blocks'],strict=True):
        assert {k:v for k,v in actual.items() if k not in ['zero_m','direction_m']} == {
            k:v for k,v in stored.items() if k not in ['zero_m','direction_m']}
        if actual['status']=='EVALUATED':
            for key in ['zero_m','direction_m']:
                assert actual[key]==pytest.approx(stored[key],rel=1e-12,abs=1e-12)
    for key in ['zero','direction']:
        assert replay[key]==pytest.approx(p[key],rel=1e-12,abs=1e-12)
    for name,path in [('baseline','day_reference_v1.json'),('pseudo_target','pseudotarget_v1.json'),('mode','g12_full_hour_v1.json')]:
        assert study.digest((study.BASE/'results'/path).read_bytes())==result['input_sha256'][name]
