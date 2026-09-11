"""Synthetic reference-code clock compression with target cross covariance.

Input references are already geometry-subtracted code residuals. This module
does not qualify real navigation, phase continuity or propagation corrections.
"""
import numpy as np
from scipy.linalg import block_diag, solve_triangular
from scipy.stats import chi2

from .interval_fit import fit_intervals
from .phase_rates import interval_matrix
from .receiver_time import cholesky_covariance


def compression(tags, receiver_count, reference_count, raw_covariance):
    """Raw order: target code, target phase path, reference residual, ground.

    Targets: endpoint/receiver. References: endpoint/receiver/reference.
    Full rectangular transformation retains cross blocks with fitted clocks.
    """
    tags = np.asarray(tags, float)
    difference = interval_matrix(tags, receiver_count)
    if len(tags) < 3 or tags[-1] != 0 or not isinstance(reference_count, int) or reference_count < 4:
        raise ValueError('>=3 endpoints ending at zero and >=4 references required')
    count = len(tags)*receiver_count
    nref = count*reference_count
    size = 2*count+nref+3*receiver_count
    cholesky_covariance(raw_covariance, size)
    cov = np.asarray(raw_covariance, float)
    refslice = slice(2*count, 2*count+nref)
    h = np.zeros((nref, 2*receiver_count))
    for t, tag in enumerate(tags):
        for receiver in range(receiver_count):
            rows = slice((t*receiver_count+receiver)*reference_count, (t*receiver_count+receiver+1)*reference_count)
            h[rows, 2*receiver:2*receiver+2] = [1., tag]
    chol = np.linalg.cholesky(cov[refslice, refslice])
    whitened = solve_triangular(chol, h, lower=True)
    u, singular, vh = np.linalg.svd(whitened, full_matrices=False)
    if singular[-1] <= singular[0]*1e-10:
        raise ValueError('reference clock rank deficient')
    gain = ((vh.T/singular)@u.T)@solve_triangular(chol, np.eye(nref), lower=True)
    transform = block_diag(np.eye(count), difference, gain, np.eye(3*receiver_count))
    compressed = transform@cov@transform.T
    return {'transform': transform, 'covariance': (compressed+compressed.T)/2,
            'reference_gain': gain, 'reference_design': h, 'reference_cholesky': chol,
            'reference_slice': refslice, 'reference_dof': nref-2*receiver_count}


def fit_shared(tags, stations, reference_residuals, raw_covariance, target_loader, *, target, references):
    """Reference gate precedes target_loader; no target values needed for clocks.

    Reference identities are explicit and target excluded before numerical
    decoding. A passing synthetic code gate is NOT real RF qualification.
    """
    references = tuple(references)
    if target in references or len(references) < 4 or len(set(references)) != len(references):
        raise ValueError('distinct non-target reference identities required')
    n = len(stations)
    c = compression(tags, n, len(references), raw_covariance)
    residuals = np.asarray(reference_residuals, float)
    if residuals.shape != (len(tags), n, len(references)) or not np.isfinite(residuals).all():
        raise ValueError('finite complete reference clock residuals required')
    clocks = c['reference_gain']@residuals.ravel()
    whitened = solve_triangular(c['reference_cholesky'], residuals.ravel()-c['reference_design']@clocks, lower=True)
    cost = float(whitened@whitened)
    p = float(chi2.sf(cost, c['reference_dof']))
    result = {'real_rf_qualified': False, 'reference_p': p, 'reference_cost': cost,
              'reference_dof': c['reference_dof'], 'clock_coefficients': clocks.reshape(n, 2)}
    if p < .01:
        return result | {'status': 'REFERENCE_CODE_REJECTED'}
    codes, phase_paths = target_loader()
    phase_paths = np.asarray(phase_paths, float)
    if phase_paths.shape != (len(tags), n) or not np.isfinite(phase_paths).all():
        raise ValueError('finite complete target phase endpoints required')
    rates = (interval_matrix(tags, n)@phase_paths.ravel()).reshape(len(tags)-1, n)
    fit = fit_intervals(tags, stations, codes, rates, clocks.reshape(n, 2), c['covariance'],
                        calibration_statuses=['CONDITIONAL_CLOCK_MODEL_ACCEPTED']*n)
    return result | {'status': fit['status'], 'fit': fit, 'compression': c,
                     'scope': 'Synthetic geometry-subtracted reference codes, no reference phase gate or real RINEX admission. Full target/reference covariance compressed without residual-based rescaling.'}
