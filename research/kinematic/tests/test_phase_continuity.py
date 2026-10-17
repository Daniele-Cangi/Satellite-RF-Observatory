"""Causal raw-frequency witnesses and retained-data GLS semantics."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.linalg import block_diag

from research.kinematic import phase_continuity as continuity, dynamic_fit
from research.kinematic.tests.test_dynamic_fit import toy
from research.kinematic.doppler import ALPHA, BETA


def rows():
    return [{'station':'A','reference':'G05','time_s':30.*i,'segment':'original',
             'geometry_free_phase_m':1000.+.00001*(30.*i)**2}
            for i in range(20)]


def test_causal_quadratic_and_warmup_keep_smooth_data_and_split_unflagged_step():
    smooth = rows()
    # Keep the warmup slope smaller than the wavelength threshold; thereafter
    # a quadratic predictor can distinguish this smooth curve from a jump.
    for r in smooth:
        r['geometry_free_phase_m'] *= .001
    original = deepcopy(smooth)
    expected = continuity.segment(smooth)
    assert smooth == original
    assert len({r['segment'] for r in expected})==1
    assert expected[10]['continuity']['method']=='QUADRATIC_PREVIOUS_TEN'
    assert expected[10]['continuity']['innovation_m']==pytest.approx(0.,abs=1e-12)
    for r in smooth[12:]:
        r['geometry_free_phase_m'] -= .425
    actual = continuity.segment(smooth)
    assert actual[:12]==expected[:12]
    assert [r['time_s'] for r in actual if r['continuity']['break']]==[360.]
    assert actual[12]['continuity']['innovation_m']==pytest.approx(-.425,abs=1e-12)
    assert actual[13]['continuity']['method']=='FIRST_DIFFERENCE_WARMUP'
    assert len({r['segment'] for r in actual})==2
    # No step amplitude is subtracted from any raw observation.
    assert [r['geometry_free_phase_m'] for r in actual]==[r['geometry_free_phase_m'] for r in smooth]


def test_missing_or_flag_segments_reset_and_heldout_payload_is_never_read():
    raw = rows()
    for r in raw:
        r['geometry_free_phase_m'] = 100.
    raw[6]['segment'] = 'flagged'
    result = continuity.segment(raw)
    assert result[6]['continuity']['method']=='NEW_SEGMENT'
    assert result[7]['continuity']['method']=='NEW_SEGMENT'
    excluded = raw[10]
    training = continuity.segment([r for i,r in enumerate(raw) if i!=10])
    class Forbidden:
        def __float__(self):
            raise AssertionError('withheld GF decoded')
    assert continuity.withheld_segment({**excluded,'geometry_free_phase_m':Forbidden()},training)
    with pytest.raises(ValueError,match='ordered unique'):
        continuity.segment([raw[0],raw[0]])


def test_dual_frequency_blind_mode_is_not_qualified_as_continuity():
    l1,l2 = continuity.C/continuity.F1_HZ,continuity.C/continuity.F2_HZ
    gf_jump = 77*l1-60*l2
    if_jump = ALPHA*77*l1+BETA*60*l2
    assert abs(gf_jump) < 1e-12
    assert if_jump > 14.
    raw = rows()
    for i,r in enumerate(raw):
        r['geometry_free_phase_m'] = 100.+(gf_jump if i>=12 else 0.)
        r['phase_m'] = if_jump if i>=12 else 0.
    assert not any(r['continuity']['break'] for r in continuity.segment(raw))


def test_free_unknown_increment_keeps_code_and_marginalizes_correlated_noise():
    arcs,state,_ = toy()
    full = dynamic_fit.fit(arcs)
    arcs[0]['phase_increment_mask'] = np.ones_like(arcs[0]['rates_m_s'],dtype=bool)
    arcs[0]['phase_increment_mask'][0,0] = False
    arcs[0]['rates_m_s'][0,0] += 1e6
    prepared,_,_ = dynamic_fit.prepare(arcs,True)
    a = prepared[0]
    assert len(a['difference'])==11
    assert len(a['observed'])==len(arcs[0]['covariance'])-1
    np.testing.assert_array_equal(a['observed'][:18],arcs[0]['codes_m'].ravel())
    kept = a['observation_indices']
    np.testing.assert_allclose(a['chol']@a['chol'].T,
        arcs[0]['covariance'][np.ix_(kept,kept)],atol=1e-12)
    covariance = block_diag(*[r['covariance'] for r in arcs])
    source = np.zeros(len(covariance))
    at = 0
    for arc in arcs:
        source[at+19] = .001
        at += len(arc['covariance'])
    source[18] = 2.  # Large correlation with the discarded increment.
    covariance += np.outer(source,source)
    indices,at = [],0
    for arc in prepared:
        indices.extend(at+arc['observation_indices'])
        at += arc['full_observation_count']
    chol = dynamic_fit.joint_cholesky(prepared,covariance)
    np.testing.assert_allclose(chol@chol.T,covariance[np.ix_(indices,indices)],atol=1e-12)
    fitted = dynamic_fit.fit(arcs,joint_covariance=covariance)
    np.testing.assert_allclose(fitted['state_ecef_m_m_s'],state,atol=.1,rtol=0)
    assert fitted['residual_dof']==full['residual_dof']-1
    delta = np.asarray(fitted['conditional_global_covariance'])-full['conditional_global_covariance']
    assert np.linalg.eigvalsh(delta[:3,:3])[-1] > 0
    # An infinite jump nuisance and dropping that row give the same GLS
    # information, including off-diagonal covariance with the retained row.
    c = np.array([[4.,-1.],[-1.,3.]])
    precision = np.linalg.inv(c)
    jump = np.array([[1.],[0.]])
    profiled = precision-precision@jump@np.linalg.inv(jump.T@precision@jump)@jump.T@precision
    np.testing.assert_allclose(profiled,[[0.,0.],[0.,1/3.]],atol=1e-15)
