import json
import numpy as np
import pytest
from research.exploratory import pseudotarget_reference as study
from research.exploratory.pseudotarget_statistics import correlation, summarize


@pytest.fixture
def plan():
    return json.loads((study.BASE/'pseudotarget_plan.json').read_bytes())


def test_excluded_code_never_read_by_clock_and_nonlinear_closure(plan):
    class Codes(dict):
        def __getitem__(self, key):
            assert key != 'P'
            return super().__getitem__(key)
    codes = Codes({s: 100. for s in ['A', 'B', 'C', 'D']}, P=float('nan'))
    def model(sv, code, clock):
        assert sv != 'P'
        return .001*clock
    result = study.receiver_clock(codes, ['A','B','C','D'], 'P', model,
                                  dict.fromkeys(['A','B','C','D'], 0.), plan)
    assert result['status'] == 'EVALUATED'
    assert result['clock_m'] == pytest.approx(100/1.001, abs=1e-6)
    with pytest.raises(ValueError):
        study.receiver_clock(codes, ['A','B','C','P'], 'P', model, {}, plan)


def test_correction_sign_and_failed_reference_support(plan):
    codes = dict.fromkeys(['A','B','C','D'], 100.)
    model = lambda *args: 0.
    result = study.receiver_clock(codes, list(codes), 'P', model, dict.fromkeys(codes, 2.), plan)
    assert result['clock_m'] == 98.
    assert study.receiver_clock(codes, ['A','B','C'], 'P', model, {}, plan)['status'] == 'INSUFFICIENT_REMAINING_REFERENCES'
    assert study.receiver_clock(codes, list(codes), 'P', model, {'A': 0.}, plan)['status'] == 'UNSUPPORTED_REFERENCE'
    assert study.receiver_clock(codes, list(codes), 'P', lambda *args: float('nan'), dict.fromkeys(codes, 0.), plan)['status'] == 'NONFINITE_MODEL'


def test_shared_offset_gauge_and_disconnected_training_rejection():
    rows = [{'station': 'S', 'time_s': t, 'reference': s, 'residual_m': v+10*t}
            for t in [0,1,2] for s,v in [('A',-2.),('B',0.),('C',2.)]]
    fit = study.fit_offsets(rows)
    assert fit['status'] == 'FITTED'
    assert fit['coefficients_m'] == pytest.approx({'A':-2.,'B':0.,'C':2.})
    rows = [{'station':'S','time_s':i,'reference':s,'residual_m':0.}
            for i, pair in enumerate([['A','B'],['C','D']]) for s in pair]
    assert study.fit_offsets(rows)['status'] == 'TRAINING_NOT_IDENTIFIABLE'


def test_temporal_statistics_use_exact_lags_and_keep_missing(plan):
    assert correlation([(1.,2.)]*10, 10)['status'] == 'ZERO_VARIANCE'
    rows = []
    for t in [0,30,90]:
        for s, value in [('S1',t/30+1),('S2',t/30-1)]:
            rows.append({'pseudo_target':'P','station':s,'time_s':t,'status':'ADMITTED',
                         'models':{m:{'status':'EVALUATED','error_m':value} for m in plan['models']}})
    rows.append({'pseudo_target':'P','station':'S1','time_s':120,'status':'PSEUDO_TARGET_NOT_ADMITTED','models':{}})
    result = summarize(rows, plan)
    assert result['zero']['epoch_station_centered']['rms_m'] == 1.
    assert result['zero']['status_counts']['PSEUDO_TARGET_NOT_ADMITTED'] == 1
    lag = next(r for r in result['zero']['lag_correlations'] if r['station']=='S1' and r['lag_s']==30)
    assert lag['count'] == 1 and lag['pearson'] is None
    assert result['paired']['count'] == 6


def synthetic_context(plan):
    from types import SimpleNamespace
    ctx=SimpleNamespace(times=[0,30,60,90],target='REAL_TARGET')
    names=['S1','S2']; refs=['P','A','B','C','D','E']
    original={'stations':names,'references':refs,'training_before_gpst_s':60}
    rows=[{'station':s,'time_s':t,'reference':sv,'residual_m':float(i)}
          for s in names for t in ctx.times for i,sv in enumerate(refs)]
    codes={(s,t):{sv:20000000.+1000.+i for i,sv in enumerate(refs)} for s in names for t in ctx.times}
    return (plan,original,ctx,None,None,None,{'rows':rows}),codes


def test_full_synthetic_fold_excludes_training_pseudotarget_and_retains_slots(plan):
    import copy
    context,codes=synthetic_context(plan)
    model=lambda s,t,sv,code,clock:20000000.+.0001*clock
    first=study.evaluate(context,codes,model)
    changed=copy.deepcopy(codes)
    for (s,t),values in changed.items():
        if t<60: values['P']+=10000.
    second=study.evaluate(context,changed,model)
    a=next(f for f in first['fits'] if f['pseudo_target']=='P')
    b=next(f for f in second['fits'] if f['pseudo_target']=='P')
    assert a==b and 'P' not in a['coefficients_m']
    assert [r for r in first['rows'] if r['pseudo_target']=='P']==[r for r in second['rows'] if r['pseudo_target']=='P']
    assert len(first['rows'])==6*2*2
    assert first['summary']['paired']['count']==24
    for row in first['rows']:
        assert row['models']['zero']['status']=='EVALUATED'
        assert row['models']['shared_satellite']['status']=='EVALUATED'


def test_training_failure_is_visible_without_rescuing_subset(plan):
    context,codes=synthetic_context(plan)
    context[-1]['rows']=[r for r in context[-1]['rows'] if r['reference'] in ['P','A','B','C']]
    context[1]['references']=['P','A','B','C']
    result=study.evaluate(context,codes,lambda *args:20000000.)
    assert all(f['status']=='TRAINING_BLOCK_FAILURE' for f in result['fits'])
    assert all(r['models']['zero']['status']=='INSUFFICIENT_REMAINING_REFERENCES' for r in result['rows'])
    assert result['summary']['paired']['count']==0


@pytest.fixture(scope='module')
def actual():
    import hashlib
    from research.exploratory import pseudotarget_checked_v2 as checked
    checked.verify_sources()
    raw=(study.BASE/'results/pseudotarget_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='d12c3d1b57520569b39c9faacb1c0089065f229d60ad87fa709806201f50c823'
    return json.loads(raw),study.inputs(checked.PLAN_SHA)


def compare(actual,expected):
    if isinstance(expected,dict):
        assert actual.keys()==expected.keys()
        for key in expected: compare(actual[key],expected[key])
    elif isinstance(expected,list):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected): compare(a,b)
    elif isinstance(expected,float):
        assert actual==pytest.approx(expected,rel=1e-9,abs=1e-8)
    else: assert actual==expected


def test_complete_report_summary_replay_and_cohort(actual):
    report,context=actual
    plan,original,ctx,*_=context
    compare(summarize(report['rows'],plan),report['summary'])
    keys={(r['pseudo_target'],r['station'],r['time_s']) for r in report['rows']}
    assert len(keys)==len(report['rows'])==22*7*61
    assert keys=={(sv,s,t) for sv in original['references'] for s in original['stations'] for t in ctx.times if t>=37800}
    assert len(report['fits'])==22
    assert all(f['pseudo_target'] not in f['coefficients_m'] for f in report['fits'])
    assert not report['real_target_fit'] and not report['real_target_orbit_accessed']
    assert not report['physical_covariance_qualified'] and not report['production_floors_changed']


def test_actual_nonlinear_recalibration_sample_for_every_receiver(actual):
    report,context=actual
    plan,original,ctx,_,_,_,baseline=context
    codes,model=study.environment(context)
    fits={f['pseudo_target']:f for f in report['fits']}
    for station in original['stations']:
        row=next(r for r in report['rows'] if r['station']==station and all(r['models'].get(m,{}).get('status')=='EVALUATED' for m in plan['models']))
        t,excluded=row['time_s'],row['pseudo_target']
        refs=sorted(r['reference'] for r in baseline['rows'] if r['station']==station and r['time_s']==t and r['reference']!=excluded)
        for method in plan['models']:
            beta=dict.fromkeys(original['references'],0.) if method=='zero' else fits[excluded]['coefficients_m']
            cal=study.receiver_clock(codes[(station,t)],refs,excluded,lambda sv,code,clock:model(station,t,sv,code,clock),beta,plan)
            assert cal['status']=='EVALUATED'
            assert cal['clock_m']==pytest.approx(row['models'][method]['clock_m'],rel=0,abs=1e-6)
            value=codes[(station,t)][excluded]
            error=value-model(station,t,excluded,value,cal['clock_m'])-cal['clock_m']
            assert error==pytest.approx(row['models'][method]['error_m'],rel=0,abs=1e-6)


def test_source_and_wrapper_freeze_and_changed_source_rejection(monkeypatch):
    import subprocess
    from pathlib import Path
    from research.exploratory import pseudotarget_checked as checked
    root=study.BASE.parents[1]
    subprocess.run(['git','merge-base','--is-ancestor','c9c3917','HEAD'],cwd=root,check=True)
    for name in [*checked.SOURCES,'research/exploratory/pseudotarget_checked.py','research/exploratory/pseudotarget_plan.json']:
        assert subprocess.check_output(['git','show','c9c3917:'+name],cwd=root)==(root/name).read_bytes()
    original=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda p: original(p)+(b'\n' if p==Path(study.__file__) else b''))
    monkeypatch.setattr(study,'run',lambda *args:pytest.fail('modified source executed'))
    with pytest.raises(ValueError): checked.run()


def test_bootstrap_verifier_is_checked_independently_before_analysis(monkeypatch):
    import subprocess
    from pathlib import Path
    from research.exploratory import pseudotarget_checked_v2 as checked
    root=study.BASE.parents[1]
    subprocess.run(['git','merge-base','--is-ancestor','1ec9ee8','HEAD'],cwd=root,check=True)
    name='research/exploratory/pseudotarget_checked_v2.py'
    assert subprocess.check_output(['git','show','1ec9ee8:'+name],cwd=root)==(root/name).read_bytes()
    assert 'research/exploratory/erp_polar_bound.py' in checked.SOURCES
    checked.verify_sources()
    monkeypatch.setattr(study,'run',lambda sha,progress:sha)
    assert checked.run()==checked.PLAN_SHA
    original=Path.read_bytes
    helper=root/'research/exploratory/erp_polar_bound.py'
    monkeypatch.setattr(Path,'read_bytes',lambda p: original(p)+(b'\n' if p==helper else b''))
    monkeypatch.setattr(study,'run',lambda *args:pytest.fail('unverified helper reached analysis'))
    with pytest.raises(ValueError,match='erp_polar_bound'): checked.run()
