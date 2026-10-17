"""Network identifiability, covariance transport and physical error shapes."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.linalg import block_diag

from research.kinematic import network_clocks as solver


def toy():
    rows = []
    for t in (0.,30.,60.,180.,210.,240.):
        for i,s in enumerate('ABC'):
            for j,q in enumerate('XYZ'):
                # An incomplete but connected graph, with common reference
                # errors which a per-station median need not cancel equally.
                if (s,q) == ('C','X'):
                    continue
                receiver = 10*i+(.01+i*.003)*t+.00001*i*t*t
                reference = (j-1)*(.2+.001*t)
                rows.append(dict(station=s,reference=q,time_s=t,segment=s+q,
                    code_m=receiver-reference,phase_m=receiver-reference+100*i+5*j))
    return rows


def test_joint_profile_matches_dense_gls_with_cross_epoch_covariance():
    network = solver.fit(toy())
    blocks = network['blocks']
    a = np.column_stack([block_diag(*[b['a'] for b in blocks]),np.vstack([b['b'] for b in blocks])])
    sigma = np.concatenate([b['sigma'] for b in blocks])
    y = np.concatenate([b['y'] for b in blocks])/sigma
    u,s,v = np.linalg.svd(a/sigma[:,None],full_matrices=False)
    estimate = (v.T/s)@(u.T@y)
    covariance = (v.T/s**2)@v
    requests = [{('A',60.):1.},{('A',240.):1.},
        {('B',60.):1/60.,('B',0.):-1/60.}]
    actual,cov = solver.clock_coefficients(network,requests)
    transform = np.zeros((3,len(estimate)))
    offset = 0
    for b in blocks:
        for k,request in enumerate(requests):
            for j,station in enumerate(b['stations']):
                transform[k,offset+j] = request.get((station,b['time_s']),0.)
        offset += len(b['parameters'])
    np.testing.assert_allclose(actual,transform@estimate,atol=1e-8,rtol=0)
    np.testing.assert_allclose(cov,transform@covariance@transform.T,atol=1e-8,rtol=1e-7)
    assert cov[0,1] > 1.  # Shared float ambiguity, not independent epochs.
    assert network['unobservable_common_clock_modes'] == 6
    assert network['weighted_cost'] < 1e-12


def test_shared_reference_errors_do_not_become_differential_receiver_clocks():
    rows = toy()
    first = solver.fit(rows)
    changed = deepcopy(rows)
    for r in changed:
        if r['reference'] == 'Z' and r['time_s'] == 240.:
            r['code_m'] += 1.
            r['phase_m'] += 1.
    second = solver.fit(changed)
    requests = [{('A',240.):1.,('B',240.):-1.}, {('B',240.):1.,('C',240.):-1.}]
    a,_ = solver.clock_coefficients(first,requests)
    b,_ = solver.clock_coefficients(second,requests)
    np.testing.assert_allclose(a,b,atol=1e-9,rtol=0)
    for r in changed:
        if r['station'] == 'A' and r['time_s'] == 240.:
            r['code_m'] += 2.
            r['phase_m'] += 2.
    c,_ = solver.clock_coefficients(solver.fit(changed),requests)
    np.testing.assert_allclose(c-a,[2.,0.],atol=1e-9,rtol=0)


def test_unflagged_link_jump_is_not_silently_absorbed_as_a_network_clock():
    rows = toy()
    for r in rows:
        if r['station'] == 'A' and r['reference'] == 'Z' and r['time_s'] == 240.:
            r['phase_m'] += 1.
    network = solver.fit(rows)
    assert network['conditional_p'] < .01
    residuals = [r for r in network['residuals'] if r['time_s'] == 240.]
    worst = max(residuals,key=lambda r:abs(r['phase_residual_m']))
    assert (worst['station'],worst['reference']) == ('A','Z')
    assert abs(worst['phase_residual_m']) > .3


def test_disconnected_network_and_unobserved_future_are_explicit_failures():
    rows = [r for r in toy() if (r['station']=='A') == (r['reference']=='X')]
    with pytest.raises(ValueError,match='rank deficient'):
        solver.fit(rows)
    with pytest.raises(ValueError,match='not observed'):
        solver.clock_coefficients(solver.fit(toy()),[{('A',270.):1.}])
