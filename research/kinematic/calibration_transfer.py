"""Local calibration error transport, with explicit reference/target coupling.

Inputs are declared Jacobians and covariance, never orbit products. This module
does not estimate a physical covariance or certify a nonlinear position bound.
"""
import numpy as np


def matrix(value, name):
    result = np.asarray(value, dtype=float)
    if result.ndim != 2 or min(result.shape) == 0 or not np.isfinite(result).all():
        raise ValueError(name + ' must be a finite nonempty matrix')
    return result


def covariance(value, size, *, positive_definite=False):
    cov = matrix(value, 'covariance')
    if cov.shape != (size, size):
        raise ValueError('covariance dimensions differ')
    scale = max(float(np.max(np.abs(cov))), np.finfo(float).tiny)
    if np.max(np.abs(cov-cov.T)) > 1e-12 * scale:
        raise ValueError('covariance must be symmetric')
    cov = (cov+cov.T)/2
    eig = np.linalg.eigvalsh(cov)
    if eig[0] < -1e-12 * scale or (positive_definite and eig[0] <= 0):
        raise ValueError('covariance must be positive ' + ('definite' if positive_definite else 'semidefinite'))
    return cov


def operators(reference_design, target_design, reference_weight_covariance):
    """GLS clock/nuisance fit and local corrected-target error mapping.

    y_ref=A theta+e_ref, y_target=B theta+e_target.
    Corrected error is e_target-B K e_ref; reference residual is (I-A K)e_ref.
    The weighting covariance is explicit and need not equal physical covariance.
    """
    a, b = matrix(reference_design, 'reference design'), matrix(target_design, 'target design')
    if a.shape[1] != b.shape[1] or a.shape[0] < a.shape[1]:
        raise ValueError('incompatible nuisance dimensions')
    cov = covariance(reference_weight_covariance, len(a), positive_definite=True)
    chol = np.linalg.cholesky(cov)
    whitened = np.linalg.solve(chol, a)
    u, singular, vh = np.linalg.svd(whitened, full_matrices=False)
    if singular[-1] <= singular[0]*1e-10:
        raise ValueError('reference nuisance design rank deficient or poorly scaled')
    gain = ((vh.T/singular)@u.T)@np.linalg.solve(chol, np.eye(len(a)))
    return {'gain': gain, 'reference_residual': np.eye(len(a))-a@gain,
            'reference_to_target': -b@gain,
            'joint_to_target': np.column_stack([-b@gain, np.eye(len(b))])}


def propagate(mapping, joint_covariance):
    """Transport supplied full covariance, including signed cross blocks.

    No unknown term is assigned zero; callers must supply the complete matrix
    and justify it separately. Semidefinite shared modes are allowed.
    """
    jac = matrix(mapping, 'mapping')
    cov = covariance(joint_covariance, jac.shape[1])
    result = jac@cov@jac.T
    if not np.isfinite(result).all():
        raise ValueError('covariance transport overflow')
    return (result+result.T)/2


def residual_blind_modes(reference_design, transfer):
    """Images of the fitted nuisance subspace, invisible to reference residuals.

    Columns of the returned input basis have unit Euclidean norm in reference
    observation coordinates. Inspect target rows separately if units differ.
    This diagnostic neither infers amplitudes nor certifies all blind modes.
    """
    a, transfer = matrix(reference_design, 'reference design'), matrix(transfer, 'transfer')
    if transfer.shape[1] != len(a) or len(a) < a.shape[1]:
        raise ValueError('incompatible reference dimensions')
    u, singular, _ = np.linalg.svd(a, full_matrices=False)
    if singular[-1] <= singular[0]*1e-10:
        raise ValueError('reference nuisance design rank deficient or poorly scaled')
    basis = u[:, :a.shape[1]]
    return {'reference_error_basis': basis, 'target_error_images': transfer@basis}
