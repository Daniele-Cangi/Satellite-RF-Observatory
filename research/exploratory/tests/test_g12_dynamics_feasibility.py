"""Shared-state profiling, clock gauge and retained scientific failures."""
import json

import numpy as np
import pytest

from research.exploratory import g12_dynamics_feasibility as study
from research.kinematic import orbital_dynamics as dynamics


def toy():
    names = ['ALGO00CAN','DRAO00CAN','STJO00CAN','AREQ00PER','BOGT00COL']
    xyz = np.array([[6.378e6,0,0],[0,6.378e6,0],[0,0,6.378e6],[-6.378e6,0,0],[0,-6.378e6,0]])
    seed = np.array([26e6,2e6,4e6,-250.,1800.,500.])
    curve = dynamics.Trajectory(seed,[-100,200])
    cases = []
    for start in [36000,36090]:
        state = curve(start-36000)
        state = np.r_[state,dynamics.acceleration(state),70000.,.1]
        fit = {'status':study.ACCEPTED,'state':state.tolist(),'receiver_clocks':np.zeros((5,2)).tolist()}
        cases.append({'start_gpst_s':start,'stations':names,'status':'EVALUATED',
                      'fits':{'code_only':fit,'code_phase':fit},'provisional_code_fit':fit})
    return {'cases':cases},{s:np.tile(p,(6,1)).tolist() for s,p in zip(names,xyz,strict=True)}


def test_qr_elimination_preserves_the_subspace_not_its_parameterization():
    rng = np.random.default_rng(9)
    nuisance = rng.normal(size=(15,4))
    bias = rng.normal(size=(15,5))
    transform = rng.normal(size=(4,4))
    first, = study.eliminate(nuisance,bias)
    second, = study.eliminate(nuisance@transform,bias)
    assert first.T@first==pytest.approx(second.T@second,abs=1e-12)
    null, = study.eliminate(nuisance,nuisance)
    assert np.linalg.norm(null)<1e-12
    with pytest.raises(ValueError,match='rank deficient'):
        study.eliminate(np.column_stack([nuisance,nuisance[:,0]]),bias)


def test_shared_state_profile_matches_full_joint_covariance_for_both_bias_models():
    rng = np.random.default_rng(112)
    arcs = [{'end':float(t),'state':rng.normal(size=(20,6)),'bias':rng.normal(size=(20,5)),
             'slope':rng.normal(size=(20,5))} for t in [0,90,180]]
    for drift in [False,True]:
        result = study.combine(arcs,drift=drift)
        state = np.vstack([a['state'] for a in arcs])
        bias = np.vstack([a['bias'] for a in arcs])
        if drift:
            bias = np.column_stack([bias,np.vstack([a['slope']-90*a['bias'] for a in arcs])/180])
        _,singular,vt = np.linalg.svd(np.column_stack([state,bias]),full_matrices=False)
        joint_covariance = (vt.T/singular**2)@vt
        expected = np.sqrt(np.linalg.eigvalsh(joint_covariance[6:,6:])[-1])
        assert result['conditional_worst_contrast_sigma_m']==pytest.approx(expected,rel=1e-12)
        assert result['parameter_count']==(10 if drift else 5)


def test_a_common_bias_on_the_local_receiver_subset_remains_a_clock_gauge():
    hour,positions = toy()
    case = hour['cases'][0]
    seed = np.asarray(case['fits']['code_only']['state'])[:6]
    step = 1e-5
    curve = dynamics.Trajectory(seed,[-100,200])
    plus = [dynamics.Trajectory(seed+e,[-100,200]) for e in np.diag(study.STATE_SCALE*step)]
    minus = [dynamics.Trajectory(seed-e,[-100,200]) for e in np.diag(study.STATE_SCALE*step)]
    # Global zero-mean pattern: all five present sites +1, absent BRAZ -5.
    pattern = np.array([1.,1.,1.,1.,1.,-5.])
    coefficients = study.helmert(6,full=False)@pattern
    for model in ['code_only','code_phase']:
        result = study.arc_geometry(case,positions,model,curve,{step:(plus,minus)},[step],36060)[str(step)]
        assert np.linalg.norm(result['bias']@coefficients)<1e-9
        assert result['state'].shape[1]==6 and result['bias'].shape[1]==5


def test_failed_geometry_is_retained_and_cannot_be_rescued_by_a_subset(monkeypatch):
    hour,positions = toy()
    def fail(*args):
        raise ValueError('synthetic geometry failure')
    monkeypatch.setattr(study,'arc_geometry',fail)
    result = study.analyze(hour,positions)
    for model in result['models'].values():
        assert len(model['retained_outcomes'])==2
        assert model['geometry_status_counts']=={'FAILED':4}
        for outcome in model['finite_difference_profiles']['1e-05'].values():
            assert outcome=={'status':'GEOMETRY_BLOCK_FAILURE','expected_arc_count':2,'evaluated_arc_count':0}


def test_retained_real_information_is_conditional_and_preserves_all_old_outcomes():
    report = json.loads((study.BASE/'results/g12_dynamics_feasibility_v1.json').read_bytes())
    old = json.loads((study.BASE/'results/g12_full_hour_v1.json').read_bytes())
    assert not report['target_orbit_used'] and not report['oracle_error_used']
    assert not report['dynamic_rf_fit_performed'] and not report['physical_covariance_qualified']
    assert not report['production_floors_changed'] and not report['new_confirmation']
    assert report['anchor_gpst_s']==36060
    assert report['anchor_rf_state_ecef_m_m_s']==old['cases'][0]['fits']['code_only']['state'][:6]
    for model in report['models'].values():
        assert len(model['retained_outcomes'])==40
        for stored,case in zip(model['retained_outcomes'],old['cases'],strict=True):
            assert stored['status']==case['status']
            assert stored['fits']=={m:f['status'] for m,f in case.get('fits',{}).items()}
        assert model['geometry_status_counts']=={'EVALUATED':45}
        for name,count in [('code_only',33),('code_phase',12)]:
            for step in model['finite_difference_profiles'].values():
                assert step[name]['status']=='EVALUATED'
                for bias in ['constant','linear_drift']:
                    result = step[name][bias]
                    assert result['arc_count']==count
                    assert result['rank']==result['parameter_count']
                    assert result['conditional_worst_contrast_sigma_m']==pytest.approx(1/result['singular_per_m'][-1])
            values = [step[name]['constant']['conditional_worst_contrast_sigma_m']
                      for step in model['finite_difference_profiles'].values()]
            assert max(values)/min(values)-1<1e-4
    assert len(report['central_vs_j2_same_seed'])==40
    assert sum('code_difference_m' in r for r in report['central_vs_j2_same_seed'])==34
    assert report['central_vs_j2_same_seed'][-1]['position_difference_m']>300.
    for name,path in [('hour','results/g12_full_hour_v1.json'),('positions','inputs/day_reference/positions.json')]:
        assert study.digest((study.BASE/path).read_bytes())==report['input_sha256'][name]
