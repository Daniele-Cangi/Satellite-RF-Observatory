"""Numerical shared-fit recovery and RF/calibration boundaries."""
from copy import deepcopy

import numpy as np
import pytest

from research.kinematic import dynamic_fit as solver, orbital_dynamics as dynamics
from research.kinematic.synthetic import receiver_positions
from research.exploratory.real_target_interval import TAGS, covariance, CALIBRATION


def toy():
    xyz = receiver_positions()[:6]
    names = list('ABCDEF')
    state = np.array([26e6,2e6,4e6,-250.,1800.,500.])
    curve = dynamics.Trajectory(state,[-100,1900])
    bias = np.array([-30.,10.,60.,-40.,20.,-20.])
    clocks = np.column_stack([np.arange(6)*10.,np.arange(6)*.001])
    arcs = []
    for endpoint in [0.,300.,900.,1800.]:
        codes = dynamics.predict_codes(curve,endpoint,TAGS,xyz,clocks,[70000.+endpoint*.1,.1])
        arcs.append({'stations':names,'tags_s':TAGS,'endpoint_gpst_s':36060+endpoint,
                     'stations_m':xyz,'clock_mean':clocks,'codes_m':codes+bias,
                     'rates_m_s':np.diff(codes,axis=0)/30.,'covariance':covariance(6)[0],
                     'calibration_statuses':[CALIBRATION]*6})
    return arcs,state,bias


def capture_snapshot_branches(monkeypatch):
    found = []
    original = solver.solve
    def recording(*args,**kwargs):
        result = original(*args,**kwargs)
        found.extend(range(len(result['branches'])))
        return result
    monkeypatch.setattr(solver,'solve',recording)
    return found


@pytest.mark.parametrize('tags', [[-60.,-30.,0.],[-120.,-75.,-20.,0.]])
def test_velocity_seed_uses_endpoint_derivative_and_subtracts_interval_clocks(tags):
    arcs,state,bias = toy()
    prepared,names,_ = solver.prepare(arcs,True)
    arc = prepared[0]
    tags = np.asarray(tags)
    unit = state[:3]-arc['xyz']
    unit /= np.linalg.norm(unit,axis=1)[:,None]
    expected = unit@state[3:]+.37  # Unknown common satellite-clock slope.
    curvature = np.linspace(.1,.6,len(names))
    # A non-linear receiver clock must be removed at each training epoch, not
    # represented by its last interval slope at the endpoint.
    basis = np.column_stack([np.ones(len(tags)),tags,np.where(tags==tags[-2],17.,0.)])
    clocks = np.column_stack([arc['clocks'],np.linspace(.2,1.2,len(names))])
    arc.update(tags=tags,clock_basis=basis,clocks=clocks,
        codes=27e6+bias+tags[:,None]*expected+.5*tags[:,None]**2*curvature+basis@clocks.T)
    np.testing.assert_allclose(solver.endpoint_code_rates(arc),expected,rtol=0,atol=1e-9)
    # Also exercise the actual seed path: it must use the endpoint derivative
    # and let the common clock slope remain free instead of shifting velocity.
    scale = np.r_[solver.STATE_SCALE,np.full(len(names)-1,100.)]
    seed,_ = solver.initial(arc,np.r_[state[:3],0.],[],scale,36060.,[-100.,1900.],dynamics.J2)
    np.testing.assert_allclose((seed*scale)[3:6],state[3:],rtol=0,atol=1e-6)


def test_noiseless_fit_recovers_shared_state_and_free_code_bias(monkeypatch):
    arcs,state,bias = toy()
    found = capture_snapshot_branches(monkeypatch)
    fitted = solver.fit(arcs)
    # Numerical root counts differ across LAPACK/platform builds. Every root
    # actually returned must appear exactly once as a candidate or failure.
    assert fitted['status']=='BRANCH_SEARCH_INCOMPLETE',fitted
    retained = [b['branch'] for b in fitted['branches']+fitted['branch_failures']]
    assert sorted(retained)==found
    assert fitted['branch_failures']
    assert all('exterior-Earth' in f['reason'] for f in fitted['branch_failures'])
    assert fitted['state_ecef_m_m_s'][:3]==pytest.approx(state[:3],abs=.1)
    assert fitted['state_ecef_m_m_s'][3:]==pytest.approx(state[3:],abs=1e-4)
    assert list(fitted['station_code_bias_m'].values())==pytest.approx(bias,abs=.1)
    assert fitted['weighted_residual_cost']<1e-6
    assert not fitted['physical_covariance_qualified']


def test_constant_code_bias_does_not_enter_carrier_increments():
    arcs,state,_ = toy()
    prepared,names,basis = solver.prepare(arcs,True)
    curve = dynamics.Trajectory(state,[-100,1900])
    a = prepared[0]
    local = np.r_[70000.,.1,a['clocks'].ravel(),np.zeros(3*a['n'])]/a['local_scale']
    zero,_ = solver.model(curve,a,local,np.zeros(5),36060.)
    changed,_ = solver.model(curve,a,local,np.arange(5)*100.,36060.)
    assert changed[a['codes'].size:]==pytest.approx(zero[a['codes'].size:],abs=0)
    assert (changed-zero)[:a['codes'].size].reshape(3,6)==pytest.approx(np.tile(basis@(np.arange(5)*100.),(3,1)),abs=1e-8)


def test_current_propagation_enters_both_code_and_interval_phase():
    arcs,state,_ = toy()
    prepared,_,_ = solver.prepare(arcs,True)
    a = prepared[0]
    curve = dynamics.Trajectory(state,[-100,1900])
    local = np.r_[70000.,.1,a['clocks'].ravel(),np.zeros(3*a['n'])]/a['local_scale']
    vacuum,_ = solver.model(curve,a,local,np.zeros(5),36060.)
    delay = np.tile(np.array([1.,3.,5.])[:,None],(1,a['n']))
    def propagation(pair,xyz,epoch,*,derivatives=False):
        return {'delay_m':delay}
    a['propagation']=propagation
    corrected,_ = solver.model(curve,a,local,np.zeros(5),36060.)
    count = a['codes'].size
    np.testing.assert_allclose((corrected-vacuum)[:count],delay.ravel(),atol=1e-8,rtol=0)
    np.testing.assert_allclose((corrected-vacuum)[count:count+len(a['difference'])],a['difference']@delay.ravel(),atol=1e-9,rtol=0)
    np.testing.assert_array_equal(corrected[count+len(a['difference']):],vacuum[count+len(a['difference']):])


def test_rejected_calibration_stops_before_target_decoding():
    class Forbidden:
        def __array__(self,*args,**kwargs):
            raise AssertionError('target decoded')
    arcs,_,_ = toy()
    arcs[0]['calibration_statuses'][0]='REJECTED'
    arcs[0]['codes_m']=Forbidden()
    with pytest.raises(ValueError,match='before target decoding'):
        solver.fit(arcs)


def test_incomplete_calibration_list_stops_before_target_decoding():
    class Forbidden:
        def __array__(self,*args,**kwargs):
            raise AssertionError('target decoded')
    arcs,_,_ = toy()
    arcs[0]['calibration_statuses']=[]
    arcs[0]['codes_m']=Forbidden()
    with pytest.raises(ValueError,match='before target decoding'):
        solver.fit(arcs)


def test_shared_fit_refuses_reused_training_endpoints_and_bad_covariance():
    arcs,_,_ = toy()
    with pytest.raises(ValueError,match='reuse target endpoint'):
        solver.prepare(arcs+[deepcopy(arcs[0])],True)
    arcs[0]['covariance']=np.zeros_like(arcs[0]['covariance'])
    with pytest.raises(ValueError,match='positive definite'):
        solver.prepare(arcs,True)


def test_failed_numerical_branches_are_retained_without_fallback(monkeypatch):
    arcs,_,_ = toy()
    found = capture_snapshot_branches(monkeypatch)
    def fail(*args):
        raise ValueError('synthetic shared design failure')
    monkeypatch.setattr(solver,'linearize',fail)
    fitted = solver.fit(arcs)
    assert fitted['status']=='NUMERICAL_FAILURE'
    assert fitted['candidate_count']==0
    assert fitted['branch_failures']
    assert any(f['reason']=='synthetic shared design failure' for f in fitted['branch_failures'])
    assert sorted(f['branch'] for f in fitted['branch_failures'])==found
