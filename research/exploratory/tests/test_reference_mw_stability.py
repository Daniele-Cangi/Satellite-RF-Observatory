"""Reference-only temporal predictions, graph contrasts and disclosure order."""
from copy import deepcopy
import hashlib
import gzip
import math
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from research.exploratory import reference_mw_stability as study
from research.exploratory.tests.test_integer_phase_feasibility import item,fields


def reference_toy():
    plan={'target_excluded':'G12','stations':['A','B'],'references':['G05','G06'],
          'training_before_gpst_s':900.,'start_gpst_s':0.,'step_s':30.,'samples':61}
    stations={}
    for si,s in enumerate(plan['stations']):
        rows=[]
        for t in range(0,1801,30):
            for qi,q in enumerate(plan['references']):
                f=fields(n1=si*qi+3*qi,n2=qi,rho=22e6+100*t,iono=3.+t/1000.)
                f[0]+=.03*si*qi*np.sin(t/300.)
                rows.append({'reference':q,'time_s':float(t),'fields':f,'status':'AVAILABLE','lli':['0','0']})
        stations[s]=item(rows)
    return {'cohorts':{'day':{'plan':plan,'stations':stations}}}


def test_absolute_blocks_keep_partial_samples_visible_and_reject_duplicates():
    points=[(float(t),t/30.) for t in range(0,331,30)]
    full,partial=study.complete_blocks(points)
    assert full==[{'start_s':0.,'mean_cycles':4.5,'count':10}]
    assert partial==[{'start_s':300.,'count':2}]
    with pytest.raises(ValueError,match='duplicate'):
        study.complete_blocks(points+[points[0]])
    with pytest.raises(ValueError,match='on-grid'):
        study.complete_blocks([(1.,0.)])


def test_future_block_interval_includes_future_scatter_not_only_mean_precision():
    model=study.block_model([{'mean_cycles':y} for y in (0.,1.,2.)])
    assert model['dof']==2 and model['mean_cycles']==1.
    assert model['block_sd_cycles']==1.
    assert model['future_block_halfwidth_95_cycles']==pytest.approx(4.3026527299*np.sqrt(4/3),rel=1e-10)
    assert model['iid_block_mean_sigma_cycles']==pytest.approx(1/np.sqrt(3))
    assert not model['absolute_link_bias_bounded'] and not model['physical_coverage_qualified']
    assert study.block_model([{'mean_cycles':1.}])['status']=='INSUFFICIENT_COMPLETE_PREFIX_BLOCKS'
    assert study.block_model([{'mean_cycles':1.}]*3)['status']=='UNRESOLVED_PREFIX_SCATTER'


def test_separable_changes_cancel_in_cycles_and_nonseparable_probe_replays():
    rows=[{'station':s,'reference':q,'change_cycles':a+b}
          for s,a in [('A',0.),('B',1.)] for q,b in [('G05',.5),('G06',.7)]]
    p=study.profile_changes(rows)
    np.testing.assert_allclose([r['nonseparable_change_cycles'] for r in p['rows']],0.,atol=1e-14)
    rows[0]['change_cycles']+=.8
    p=study.profile_changes(rows)
    r={ (r['station'],r['reference']):r['nonseparable_change_cycles'] for r in p['rows']}
    assert r['A','G05']-r['B','G05']-r['A','G06']+r['B','G06']==pytest.approx(.8)
    assert p['rows'][0]['leave_one_link_out_error_cycles']==pytest.approx(.8)
    assert p['independent_cycle_contrasts']==1
    bridge=study.profile_changes(rows[:3])
    assert bridge['independent_cycle_contrasts']==0
    assert all(r['leave_one_link_out_error_cycles'] is None for r in bridge['rows'])


def test_reference_only_prefix_and_block_model_are_invariant_to_held_poison():
    reference=reference_toy()
    first,indices=study.prepare(reference)
    assert len(first['records'])==1
    assert first['records'][0]['block_model']['block_count']==3
    class Forbidden:
        def __float__(self):
            raise AssertionError('forbidden reference held value or target row')
    changed=deepcopy(reference)
    for station in changed['cohorts']['day']['stations'].values():
        for row in station['rows']:
            if row['time_s']>=900.:
                row['fields']=[Forbidden()]*4
        station['rows'].insert(0,{'reference':'G12','time_s':Forbidden(),'fields':Forbidden()})
    other,_=study.prepare(changed)
    assert first==other
    assert not first['target_raw_observations_used']
    before=deepcopy(first)
    scored=study.score(first,indices)
    assert scored['summary']['nominal_interval_scored_blocks']==3
    assert scored['summary']['all_reference_configurations']==1
    assert len(scored['records'][0]['partial_held_blocks'])==1
    study.diagnose_changes(first,indices)
    assert first==before


def test_reference_cli_rejects_target_input_before_any_file_access(tmp_path):
    proc=subprocess.run([sys.executable,'-m','research.exploratory.real_phase','--reference-mw-stability',
                         '--inputs','missing-reference','--target-input','missing-target','--output',str(tmp_path/'out')],
                        capture_output=True,text=True,cwd=study.base.ROOT)
    assert proc.returncode!=0 and 'reference input only' in proc.stderr
    assert not (tmp_path/'out').exists()


def test_run_opens_no_target_input_and_saves_before_scoring(tmp_path,monkeypatch):
    source=tmp_path/'reference.json'
    source.write_text(json.dumps(reference_toy()))
    monkeypatch.setattr(study.base,'REFERENCE',source)
    monkeypatch.setattr(study.base,'EXPECTED',(hashlib.sha256(source.read_bytes()).hexdigest(),'target-not-read'))
    original_read=Path.read_bytes
    def guarded_read(path):
        if path.resolve()==study.base.TARGET.resolve():
            raise AssertionError('target file opened')
        return original_read(path)
    monkeypatch.setattr(Path,'read_bytes',guarded_read)
    actual=study.score
    output=tmp_path/'out'
    def guarded_score(frozen,indices):
        assert (output/'predictions-before-scoring.json.gz').exists()
        return actual(frozen,indices)
    monkeypatch.setattr(study,'score',guarded_score)
    result=study.run(source,output)
    assert not result['target_raw_observations_used']
    assert (output/'post-score-changes.json.gz').exists()
    with pytest.raises(FileExistsError):
        study.run(source,output)


def test_empty_reference_support_remains_an_explicit_terminal():
    result=study.diagnose_changes({'cut_gpst_s':900.},{})
    assert result['status']=='NO_ADMITTED_REFERENCE_OBSERVATIONS'
    assert not result['observations_repaired'] and result['blocks']==[]


def test_retained_reference_stability_replays_and_uses_only_reference_input():
    folder=study.base.ROOT/'research/exploratory/reference-mw-stability-2026-10-26'
    frozen=json.loads(gzip.decompress((folder/'predictions-before-scoring.json.gz').read_bytes()))
    scores=json.loads(gzip.decompress((folder/'scores.json.gz').read_bytes()))
    changes=json.loads(gzip.decompress((folder/'post-score-changes.json.gz').read_bytes()))
    producer='e803092f71cbc34a18c67add0e92e87c0403bf5f'
    assert frozen['implementation_revision']==producer
    for source,wanted in frozen['source_sha256'].items():
        raw=subprocess.check_output(['git','show',producer+':'+source],cwd=study.base.ROOT)
        if source=='requirements-positioning.txt':
            # Dependency text was checked out as CRLF when read; preserve its
            # exact evidence bytes and separately bind its Git text content.
            observed=(folder/'requirements-as-read.txt').read_bytes()
            assert hashlib.sha256(observed).hexdigest()==wanted
            assert observed.replace(b'\r\n',b'\n')==raw.replace(b'\r\n',b'\n')
        else:
            assert hashlib.sha256(raw).hexdigest()==wanted
    raw=study.base.REFERENCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==frozen['input_sha256']==study.base.EXPECTED[0]
    assert not frozen['target_raw_observations_used'] and not frozen['target_products_used']
    assert frozen['predictions_fixed_before_held_scoring'] and not frozen['prospective_confirmation']
    replay,indices=study.prepare(json.loads(raw))
    assert len(replay['records'])==len(frozen['records'])==4851
    from research.exploratory.tests.test_integer_phase_feasibility import assert_frozen_records
    for a,b in zip(replay['records'],frozen['records'],strict=True):
        assert a.keys()==b.keys()
        # Reuse exact scientific decision checks with tolerances only for
        # continuous reductions, including block moments and Student scales.
        extra={'block_model','prefix_blocks','partial_prefix_blocks'}
        assert_frozen_records([{k:v for k,v in a.items() if k not in extra}],
                              [{k:v for k,v in b.items() if k not in extra}])
        if 'block_model' in a:
            assert a['partial_prefix_blocks']==b['partial_prefix_blocks']
            for c,d in zip(a['prefix_blocks'],b['prefix_blocks'],strict=True):
                assert c['start_s']==d['start_s'] and c['count']==d['count']
                assert c['mean_cycles']==pytest.approx(d['mean_cycles'],abs=1e-10,rel=0)
            for k,v in a['block_model'].items():
                if isinstance(v,float):
                    assert v==pytest.approx(b['block_model'][k],abs=1e-10,rel=0)
                else:
                    assert v==b['block_model'][k]
    actual=study.score(replay,indices)
    assert actual['summary']==scores['summary']
    assert actual['summary']['original_reference_controls']['scored_configurations']==251
    assert actual['summary']['original_integer_held_mean_agreements']==220
    assert actual['summary']['nominal_interval_scored_blocks']==841
    assert actual['summary']['nominal_interval_covered_blocks']==765
    assert not actual['integer_fix_admitted']
    for a,b in zip(actual['records'],scores['records'],strict=True):
        assert a.keys()==b.keys()
        assert a['stations']==b['stations'] and a['satellites']==b['satellites'] and a['status']==b['status']
        if 'held_blocks' in a:
            assert a['block_model_status']==b['block_model_status']
            assert a['partial_held_blocks']==b['partial_held_blocks']
            for c,d in zip(a['held_blocks'],b['held_blocks'],strict=True):
                assert c['start_s']==d['start_s'] and c['count']==d['count']
                assert c.get('within_nominal_95')==d.get('within_nominal_95')
                np.testing.assert_allclose([c[k] for k in c if k.endswith('cycles')],
                                           [d[k] for k in c if k.endswith('cycles')],rtol=0,atol=1e-10)
    diagnosis=study.diagnose_changes(replay,indices)
    assert diagnosis['post_score_only'] and not diagnosis['observations_repaired']
    for a,b in zip(diagnosis['blocks'],changes['blocks'],strict=True):
        assert a['start_s']==b['start_s'] and a['status']==b['status']
        assert a.get('rank')==b.get('rank')
        for c,d in zip(a['rows'],b['rows'],strict=True):
            assert c['station']==d['station'] and c['reference']==d['reference']
            for k in c:
                if isinstance(c[k],float):
                    assert c[k]==pytest.approx(d[k],abs=1e-9,rel=0)
                else:
                    assert c[k]==d[k]


def test_post_score_braz_g05_jump_and_flagged_reacquisitions_remain_visible():
    reference=json.loads(study.base.REFERENCE.read_bytes())['cohorts']['day']
    rows={r['time_s']:r for r in reference['stations']['BRAZ00BRA']['rows'] if r['reference']=='G05'}
    before,after=rows[39540.],rows[39570.]
    assert before['lli']==after['lli']==['0','0']
    mw_change=study.base.wide_lane(after['fields'])-study.base.wide_lane(before['fields'])
    gf_change=after['geometry_free_phase_m']-before['geometry_free_phase_m']
    assert mw_change==pytest.approx(-64.73627993091941,abs=1e-8)
    assert gf_change==pytest.approx(-15.877133559435606,abs=1e-8)
    witness=study.base.phase_continuity.segment([
        {'station':'BRAZ00BRA','reference':'G05','time_s':r['time_s'],'segment':'POST_SCORE_ONLY',
         'geometry_free_phase_m':r['geometry_free_phase_m']} for r in (before,after)])
    assert witness[-1]['continuity']['break']
    # Very large changes in separate block profiles can cross already flagged
    # gaps. They must not be called stable-bias drift or unflagged anomalies.
    areq={r['time_s']:r for r in reference['stations']['AREQ00PER']['rows'] if r['reference']=='G14'}
    assert areq[38040.]['status']=='REJECTED' and areq[38040.]['lli']==['1','1']
    stjo={r['time_s'] for r in reference['stations']['STJO00CAN']['rows'] if r['reference']=='G25'}
    assert any(t not in stjo for t in range(37770,38371,30))
    folder=study.base.ROOT/'research/exploratory/reference-mw-stability-2026-10-26'
    frozen=json.loads(gzip.decompress((folder/'predictions-before-scoring.json.gz').read_bytes()))
    scores=json.loads(gzip.decompress((folder/'scores.json.gz').read_bytes()))
    mismatches=[a for a,b in zip(frozen['records'],scores['native_scalar_scores']['records'],strict=True)
                if 'count' in b and math.floor(b['mean_cycles']+.5)!=a['comparison']['integer_hypothesis']]
    assert len(mismatches)==31
    assert sum('BRAZ00BRA' in a['stations'] and 'G05' in a['satellites'] for a in mismatches)==19
