"""Synthetic reference-code calibration with shared quadratic path nuisance.

The extra coefficient is an additive path delay, NOT a quadratic physical clock.
Reference phases remain unused checks. No target data choose the basis.
"""
import numpy as np
from scipy.linalg import solve_triangular
from scipy.stats import chi2

from .interval_fit import fit_intervals
from .phase_rates import interval_matrix
from .receiver_time import cholesky_covariance


def quadratic_design(tags, receivers, references):
    tags = np.asarray(tags, float)
    interval_matrix(tags, receivers)
    if len(tags) < 4 or tags[-1] != 0 or tags[0] >= 0 or references < 4:
        raise ValueError('four endpoints ending at zero and four references required')
    basis = np.column_stack([np.ones(len(tags)), tags, (tags/abs(tags[0]))**2])
    h = np.zeros((len(tags)*receivers*references, 3*receivers))
    q = np.zeros((len(tags)*receivers, receivers))
    for i in range(len(tags)):
        for j in range(receivers):
            h[(i*receivers+j)*references:(i*receivers+j+1)*references, 3*j:3*j+3] = basis[i]
            q[i*receivers+j, j] = basis[i, 2]
    return h, q


def fit_slow_calibration(tags, stations, reference_codes, reference_phases, covariance,
                         target_loader, *, target, references):
    references = tuple(references)
    if target in references or len(set(references)) != len(references) or len(references) < 4:
        raise ValueError('distinct non-target references required')
    n, r = len(stations), len(references)
    nt, count = len(tags), len(tags)*n
    nref = count*r
    oldsize = 2*count+nref+3*n
    size = oldsize+nref
    cholesky_covariance(covariance, size)
    cov = np.asarray(covariance, float)
    refslice = slice(2*count, 2*count+nref)
    h, q = quadratic_design(tags, n, r)
    chol = np.linalg.cholesky(cov[refslice, refslice])
    u, singular, vh = np.linalg.svd(solve_triangular(chol, h, lower=True), full_matrices=False)
    if singular[-1] <= singular[0]*1e-10:
        raise ValueError('quadratic reference rank deficient')
    gain = ((vh.T/singular)@u.T)@solve_triangular(chol, np.eye(nref), lower=True)
    codes = np.asarray(reference_codes, float)
    if codes.shape != (nt, n, r) or not np.isfinite(codes).all():
        raise ValueError('finite complete reference codes required')
    coefficients = gain@codes.ravel()
    white = solve_triangular(chol, codes.ravel()-h@coefficients, lower=True)
    code_p = float(chi2.sf(white@white, nref-3*n))
    result = {'real_rf_qualified': False, 'reference_code_p': code_p,
              'reference_code_dof': nref-3*n, 'reference_coefficients': coefficients.reshape(n, 3)}
    if code_p < .01:
        return result | {'status': 'REFERENCE_CODE_REJECTED'}
    phases = np.asarray(reference_phases, float)
    if phases.shape != codes.shape or not np.isfinite(phases).all():
        raise ValueError('finite complete reference phases required')
    dref = interval_matrix(tags, n*r)
    gate = np.zeros((len(dref), size))
    gate[:, refslice] = -dref@h@gain
    gate[:, oldsize:] = dref
    gatecov = gate@cov@gate.T
    gatecov = (gatecov+gatecov.T)/2
    residual = dref@(phases.ravel()-h@coefficients)
    white = solve_triangular(cholesky_covariance(gatecov, len(dref)), residual, lower=True)
    phase_p = float(chi2.sf(white@white, len(dref)))
    result.update(reference_phase_p=phase_p, reference_phase_dof=len(dref))
    if phase_p < .01:
        return result | {'status': 'REFERENCE_PHASE_RESIDUAL_REJECTED'}
    dt = interval_matrix(tags, n)
    nrates = len(dt)
    # Correct target path by reference-only quadratic estimate. Clock offset
    # and drift enter as ordinary compressed observations; preserve all cross
    # terms between correction error, original target noise, clocks and ground.
    transform = np.zeros((count+nrates+5*n, size))
    transform[:count, :count] = np.eye(count)
    transform[:count, refslice] = -q@gain[2::3]
    transform[count:count+nrates, count:2*count] = dt
    transform[count:count+nrates, refslice] = -dt@q@gain[2::3]
    clockrows = np.array([[3*j, 3*j+1] for j in range(n)]).ravel()
    transform[count+nrates:count+nrates+2*n, refslice] = gain[clockrows]
    transform[-3*n:, 2*count+nref:oldsize] = np.eye(3*n)
    fitcov = transform@cov@transform.T
    fitcov = (fitcov+fitcov.T)/2
    target_codes, target_phases = [np.asarray(a, float) for a in target_loader()]
    if any(a.shape != (nt, n) or not np.isfinite(a).all() for a in (target_codes, target_phases)):
        raise ValueError('finite complete target endpoints required')
    correction = q@coefficients[2::3]
    corrected_codes = target_codes-correction.reshape(nt, n)
    corrected_rates = (dt@(target_phases.ravel()-correction)).reshape(nt-1, n)
    fit = fit_intervals(tags, stations, corrected_codes, corrected_rates,
                        coefficients[clockrows].reshape(n, 2), fitcov,
                        calibration_statuses=['CONDITIONAL_CLOCK_MODEL_ACCEPTED']*n)
    return result | {'status': fit['status'], 'fit': fit, 'fit_covariance': fitcov,
                     'transform': transform, 'reference_gain': gain,
                     'reference_design': h, 'gate_fit_cross_covariance': gate@cov@transform.T,
                     'scope': 'Synthetic reference-only quadratic shared path calibration, unchanged target trajectory model. All correction uncertainty retained; no real RF or post-selection coverage qualification.'}
