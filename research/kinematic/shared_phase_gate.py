"""Unused reference phase gate ahead of shared target/reference compression.

Synthetic geometry-subtracted residuals only. No phase refitting of clocks,
conditional covariance correction, RINEX admission or real RF qualification.
"""
import numpy as np
from scipy.linalg import solve_triangular
from scipy.stats import chi2

from .receiver_time import cholesky_covariance
from .phase_rates import interval_matrix
from .shared_calibration import compression, fit_shared


def fit_shared_phase(tags, stations, reference_codes, reference_phase_paths,
                     covariance, target_loader, *, target, references):
    references = tuple(references)
    if target in references or len(references) < 4 or len(set(references)) != len(references):
        raise ValueError('distinct non-target reference identities required')
    n, nr = len(stations), len(references)
    count, refcount = len(tags)*n, len(tags)*n*nr
    size = 2*count+refcount+3*n
    # Appended block: reference phase path residuals in metres, same row order
    # as reference codes. All cross blocks are retained, not replaced by zero.
    cholesky_covariance(covariance, size+refcount)
    cov = np.asarray(covariance, float)
    oldcov = cov[:size, :size].copy()
    c = compression(tags, n, nr, oldcov)
    codes = np.asarray(reference_codes, float)
    if codes.shape != (len(tags), n, nr) or not np.isfinite(codes).all():
        raise ValueError('finite complete reference code residuals required')
    clocks = c['reference_gain']@codes.ravel()
    predicted = c['reference_design']@clocks
    white = solve_triangular(c['reference_cholesky'], codes.ravel()-predicted, lower=True)
    code_cost = float(white@white)
    code_p = float(chi2.sf(code_cost, c['reference_dof']))
    result = {'real_rf_qualified': False, 'reference_code_p': code_p,
              'reference_code_cost': code_cost, 'clock_coefficients': clocks.reshape(n, 2)}
    if code_p < .01:
        return result | {'status': 'REFERENCE_CODE_REJECTED'}
    phases = np.asarray(reference_phase_paths, float)
    if phases.shape != codes.shape or not np.isfinite(phases).all():
        raise ValueError('finite complete reference phase residual endpoints required')
    difference = interval_matrix(tags, n*nr)
    mapping = np.zeros((len(difference), len(cov)))
    mapping[:, c['reference_slice']] = -difference@c['reference_design']@c['reference_gain']
    mapping[:, size:] = difference
    residual_cov = mapping@cov@mapping.T
    residual_cov = (residual_cov+residual_cov.T)/2
    residual = difference@(phases.ravel()-predicted)
    white = solve_triangular(cholesky_covariance(residual_cov, len(difference)), residual, lower=True)
    cost = float(white@white)
    p = float(chi2.sf(cost, len(difference)))
    fit_mapping = np.pad(c['transform'], ((0, 0), (0, refcount)))
    result.update(reference_phase_p=p, reference_phase_cost=cost, reference_phase_dof=len(difference),
                  phase_residuals_m_s=residual, phase_residual_covariance=residual_cov,
                  phase_residual_mapping=mapping,
                  phase_residual_fit_data_cross_covariance=mapping@cov@fit_mapping.T)
    if p < .01:
        return result | {'status': 'REFERENCE_PHASE_RESIDUAL_REJECTED'}
    # Preserve the previous fit and its marginal covariance exactly. Code gate
    # is checked again by the immutable downstream entry point, before loading.
    downstream = fit_shared(tags, stations, codes, oldcov, target_loader, target=target, references=references)
    return result | {'status': downstream['status'], 'downstream': downstream,
                     'scope': 'Synthetic unused reference phase gate. Clock fitted only to reference codes; target fit covariance remains unconditional. No global sequential test calibration or real RF admission.'}
