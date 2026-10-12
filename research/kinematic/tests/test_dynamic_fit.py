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


def test_noiseless_fit_recovers_shared_state_and_free_code_bias():
    arcs,state,bias = toy()
    fitted = solver.fit(arcs)
    # Snapshot multilateration also finds two interior-Earth roots. They cannot
    # be propagated, and their failure must keep the branch search incomplete.
    assert fitted['status']=='BRANCH_SEARCH_INCOMPLETE',fitted
    assert len(fitted['branch_failures'])==2
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


def test_rejected_calibration_stops_before_target_decoding():
    class Forbidden:
        def __array__(self,*args,**kwargs):
            raise AssertionError('target decoded')
    arcs,_,_ = toy()
    arcs[0]['calibration_statuses'][0]='REJECTED'
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
    def fail(*args):
        raise ValueError('synthetic shared design failure')
    monkeypatch.setattr(solver,'linearize',fail)
    fitted = solver.fit(arcs)
    assert fitted['status']=='NUMERICAL_FAILURE'
    assert fitted['candidate_count']==0
    assert fitted['branch_failures']
    assert any(f['reason']=='synthetic shared design failure' for f in fitted['branch_failures'])
    assert len(fitted['branch_failures'])==3
