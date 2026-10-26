"""Reference-only temporal predictions, graph contrasts and disclosure order."""
from copy import deepcopy
import hashlib
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
