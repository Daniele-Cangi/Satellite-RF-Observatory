"""Integer information, nuisance invariance and actual held-value exclusion."""
from copy import deepcopy
import gzip
import hashlib
import json
import math
import subprocess

import numpy as np
import pytest

from research.exploratory import integer_phase_feasibility as study
from research.kinematic import gnss_combinations as combo


def fields(n1=0,n2=0,rho=22e6,iono=0.):
    factor=(combo.F1_HZ/combo.F2_HZ)**2
    return [rho+iono,rho+factor*iono,
            (rho-iono)/(combo.C/combo.F1_HZ)+n1,
            (rho-factor*iono)/(combo.C/combo.F2_HZ)+n2]


def item(rows):
    return {'status':'PARSED','rows':rows,
        'phase_shifts':{k:{'default_cycles':0.,'satellite_overrides_cycles':{}} for k in ('L1C','L2W')},
        'legacy':{'numeric_phase_unit':'carrier_cycles','default_ambiguity_wavelength_divisor':{'L1':1,'L2':1},
                  'satellite_overrides':{}}}


def toy():
    plan={'target_excluded':'G12','stations':['A','B'],'references':['G05','G06'],
          'training_before_gpst_s':300.,'start_gpst_s':0.,'step_s':30.,'samples':21}
    reference={'cohorts':{'day':{'plan':plan,'stations':{}}}}
    target={'stations':{}}
    for si,s in enumerate(plan['stations']):
        own=[];held=[]
        for t in range(0,601,30):
            for qi,q in enumerate(['G05','G06','G12']):
                r={'time_s':float(t),'status':'AVAILABLE','lli':['0','0'],
                   'fields':fields(n1=si*qi+2*qi,n2=qi,rho=22e6+100*t+1000*si,iono=3.+t/1000.)}
                r['target' if q=='G12' else 'reference']=q
                (held if q=='G12' else own).append(r)
        reference['cohorts']['day']['stations'][s]=item(own)
        target['stations'][s]=item(held)
    return reference,target


def test_raw_mw_integer_law_geometry_ionosphere_and_joint_ambiguity_null():
    for rho in (20e6,30e6):
        for iono in (0.,15.):
            assert study.wide_lane(fields(123,100,rho,iono))==pytest.approx(23.,abs=3e-8)
    a=np.asarray(fields(7,3));b=a+np.array([0.,0.,1.,1.])
    assert study.wide_lane(a)==pytest.approx(study.wide_lane(b),abs=3e-8)
    assert combo.values(b)[1]-combo.values(a)[1]==pytest.approx(study.NARROW_M,abs=3e-8)
    # Generic phase/code hardware offsets separable by receiver and satellite
    # cancel in DD, even though the undifferenced MW is not an integer.
    values=[]
    for s,q in ((0,0),(1,0),(0,1),(1,1)):
        f=np.asarray(fields(n1=s*q+3,n2=1))
        f+=np.array([.2,-.7,.13,-.21])*(s+2*q+1)
        values.append(study.wide_lane(f))
    assert sum(sign*y for sign,y in zip((1,-1,-1,1),values,strict=True))==pytest.approx(1.,abs=4e-8)


def test_scalar_integer_alternatives_and_free_bias_remain_distinct():
    r=study.scalar_comparison([3.01,2.99,3.02,2.98],.01)
    assert r['integer_hypothesis']==3
    assert r['integer_interval_delta_q_le_4']==[3,3]
    assert r['second_minus_best_training_delta_q']>100.
    assert not r['integer_fix_admitted']
    biased=study.scalar_comparison([3.37]*10,.01)
    assert biased['integer_minus_float_training_delta_q']>0.
    for n in (biased['integer_hypothesis'],biased['second_integer_hypothesis'],100):
        assert n+(biased['float_cycles']-n)==pytest.approx(biased['float_cycles'])
    assert biased['free_link_bias_identifiability']=='ALL_INTEGERS_EQUIVALENT'


def test_prepare_uses_no_held_rf_or_held_gf_and_keeps_every_configuration():
    reference,target=toy()
    first,indices=study.prepare(reference,target)
    assert len(first['records'])==3
    assert all(r['status']=='CONDITIONAL_WIDE_LANE_HYPOTHESES' for r in first['records'])
    scored=study.score(first,indices)
    assert all(r['integer_rms_cycles']<1e-7 for r in scored['records'])
    class Forbidden:
        def __float__(self):
            raise AssertionError('held numeric value used before scoring')
    changed=deepcopy((reference,target))
    for dataset in changed:
        stations=dataset['stations'] if 'stations' in dataset else dataset['cohorts']['day']['stations']
        for station in stations.values():
            for r in station['rows']:
                if r['time_s']>=300.:
                    r['fields']=[Forbidden()]*4
                    r['geometry_free_phase_m']=Forbidden()
    other,_=study.prepare(*changed)
    assert first==other
    assert not first['integer_fix_admitted'] and not first['target_products_used']


def test_header_flags_gaps_and_missing_prefix_have_no_rescue():
    reference,target=toy()
    # A half-cycle-flagged epoch ends all held support involving this link.
    target['stations']['B']['rows'][11]['lli']=['2','0']
    frozen,_=study.prepare(reference,target)
    assert all(r['future_tags']==[300.] for r in frozen['records'] if r['role']=='G12')
    reference,target=toy()
    target['stations']['B']['rows']=[r for r in target['stations']['B']['rows'] if r['time_s']>=300.]
    frozen,_=study.prepare(reference,target)
    assert all(r['status']=='NO_PREFIX_AT_BOUNDARY' for r in frozen['records'] if r['role']=='G12')
    reference,target=toy()
    target['stations']['A']['phase_shifts']['L1C']['default_cycles']=.25
    frozen,_=study.prepare(reference,target)
    assert frozen['inventory']['A/target']['header_status']=='NONZERO_PHASE_ALIGNMENT_UNSUPPORTED'
    assert all(r['status']=='NO_PREFIX_AT_BOUNDARY' for r in frozen['records'] if r['role']=='G12')


def test_unflagged_gf_null_slip_remains_a_held_failure_not_an_integer_repair():
    reference,target=toy()
    frozen,_=study.prepare(reference,target)
    for r in target['stations']['B']['rows']:
        if r['time_s']>=300.:
            r['fields'][2]+=77.;r['fields'][3]+=60.
    same,indices=study.prepare(reference,target)
    assert same==frozen
    result=study.score(same,indices)
    assert all(r['integer_rms_cycles']>16. for r in result['records'] if r['role']=='G12')


def test_unlisted_identity_is_removed_before_numeric_access():
    reference,target=toy()
    class Forbidden:
        def __float__(self):
            raise AssertionError('forbidden identity used')
    reference['cohorts']['day']['stations']['A']['rows'].insert(0,{'reference':'G12','time_s':Forbidden(),'fields':Forbidden()})
    frozen,_=study.prepare(reference,target)
    assert len(frozen['records'])==3


def test_training_gf_break_is_not_bridged_for_integer_averaging():
    reference,target=toy()
    for r in target['stations']['B']['rows']:
        if r['time_s']==270.:
            r['fields'][2]+=1.
    frozen,_=study.prepare(reference,target)
    assert all(r['status']=='NO_PREFIX_AT_BOUNDARY' for r in frozen['records'] if r['role']=='G12')


def test_report_writes_frozen_predictions_before_held_numeric_access(tmp_path,monkeypatch):
    reference,target=toy()
    paths=[tmp_path/'reference.json',tmp_path/'target.json']
    for path,content in zip(paths,(reference,target),strict=True):
        path.write_text(json.dumps(content))
    monkeypatch.setattr(study,'REFERENCE',paths[0])
    monkeypatch.setattr(study,'TARGET',paths[1])
    monkeypatch.setattr(study,'EXPECTED',tuple(hashlib.sha256(p.read_bytes()).hexdigest() for p in paths))
    actual=study.score
    output=tmp_path/'output'
    def guarded(frozen,indices):
        assert (output/'predictions-before-scoring.json.gz').exists()
        return actual(frozen,indices)
    monkeypatch.setattr(study,'score',guarded)
    study.run(*paths,output)
    assert (output/'scores.json.gz').exists()
    with pytest.raises(FileExistsError):
        study.run(*paths,output)
    paths[0].write_bytes(b'not the admitted archive')
    with pytest.raises(ValueError,match='hash mismatch'):
        study.run(*paths,tmp_path/'invalid-output')
    assert not (tmp_path/'invalid-output').exists()


def test_retained_raw_integer_feasibility_replays_with_unchanged_inputs_and_sources():
    folder=study.ROOT/'research/exploratory/integer-phase-2026-10-26'
    frozen=json.loads(gzip.decompress((folder/'predictions-before-scoring.json.gz').read_bytes()))
    scores=json.loads(gzip.decompress((folder/'scores.json.gz').read_bytes()))
    assert frozen['implementation_revision']=='91582d5b6c926f3ff4f9ef40a582b755fc7dc11b'
    for source,wanted in frozen['source_sha256'].items():
        original=subprocess.check_output(['git','show',frozen['implementation_revision']+':'+source],cwd=study.ROOT)
        assert hashlib.sha256(original).hexdigest()==wanted
    for path,wanted in zip((study.REFERENCE,study.TARGET),study.EXPECTED,strict=True):
        assert hashlib.sha256(path.read_bytes()).hexdigest()==wanted==frozen['input_sha256'][path.name]
    assert frozen['predictions_fixed_before_held_scoring'] and not frozen['prospective_confirmation']
    assert not frozen['target_products_used'] and not frozen['integer_fix_admitted']
    assert frozen['target_raw_observations_used'] and not frozen['target_state_estimated']
    reference,target=[json.loads(p.read_bytes()) for p in (study.REFERENCE,study.TARGET)]
    replay,indices=study.prepare(reference,target)
    assert replay['records']==frozen['records']
    actual=study.score(replay,indices)
    assert actual['summary']==scores['summary']
    for a,b in zip(actual['records'],scores['records'],strict=True):
        assert a['status']==b['status'] and a['stations']==b['stations'] and a['satellites']==b['satellites']
        if 'count' in a:
            assert a['count']==b['count']
            np.testing.assert_allclose(a['held_values_cycles'],b['held_values_cycles'],rtol=0,atol=1e-10)
            for k in ('mean_cycles','float_rms_cycles','integer_rms_cycles','held_minus_training_mean_cycles'):
                assert a[k]==pytest.approx(b[k],abs=1e-10,rel=0)
    assert len(frozen['records'])==5313
    assert scores['summary']['G12']['configurations']==462
    assert scores['summary']['G12']['scored_configurations']==62
    assert scores['summary']['REFERENCE_CONTROL']['configurations']==4851
    assert scores['summary']['REFERENCE_CONTROL']['scored_configurations']==251
    for role,total in (('G12',62),('REFERENCE_CONTROL',251)):
        paired=[(a,b) for a,b in zip(frozen['records'],scores['records'],strict=True) if a['role']==role and 'count' in b]
        assert len(paired)==total
        assert all(a['comparison']['integer_interval_delta_q_le_4'][1]>a['comparison']['integer_interval_delta_q_le_4'][0]
                   for a,b in paired)
        agree=sum(math.floor(b['mean_cycles']+.5)==a['comparison']['integer_hypothesis'] for a,b in paired)
        assert agree==({'G12':62,'REFERENCE_CONTROL':220}[role])
