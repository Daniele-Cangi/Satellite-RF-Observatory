"""Local deterministic bias and residual detectability for interval fits.

Systematic amplitudes are declared inputs, not inferred or tuned from residuals.
Noncentral chi-square power is a local linear Gaussian diagnostic only.
"""
import numpy as np
from scipy.linalg import solve_triangular
from scipy.stats import chi2, ncx2

from .interval_fit import covariance_hash
from .receiver_time import cholesky_covariance


def transport_systematics(result, covariance, modes):
    """Columns are signed deterministic perturbations to the exact fit data.

    A unit column coefficient is the declared amplitude; a box coefficient
    lies in [-1,1]. Keep bias separate from stochastic covariance.
    """
    if result['status'] != 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED':
        raise ValueError('accepted interval fit required before systematic inputs')
    gain, jacobian = result['data_gain'], result['data_jacobian']
    size = gain.shape[1]
    chol = cholesky_covariance(covariance, size)
    if covariance_hash(covariance) != result['fit_covariance_sha256']:
        raise ValueError('systematic analysis changes frozen fit covariance')
    modes = np.asarray(modes, float)
    if modes.ndim != 2 or modes.shape[0] != size or not np.isfinite(modes).all():
        raise ValueError('finite systematic columns matching fit data required')
    bias = gain@modes
    residual = solve_triangular(chol, modes-jacobian@bias, lower=True)
    noncentrality = np.sum(residual**2, axis=0)
    threshold = chi2.isf(result['residual_threshold_p'], result['residual_dof'])
    return {'status': 'LOCAL_INTERVAL_SYSTEMATICS', 'real_rf_qualified': False,
            'parameter_bias_modes': bias, 'whitened_residual_modes': residual,
            'residual_noncentrality': noncentrality,
            'local_rejection_probability': ncx2.sf(threshold, result['residual_dof'], noncentrality),
            'local_expected_residual_cost': result['residual_dof']+noncentrality,
            'affine_box_parameter_component_bound': np.sum(abs(bias), axis=1),
            'affine_box_position_norm_bound_m': float(np.linalg.norm(bias[:3], axis=0).sum()),
            'affine_box_velocity_norm_bound_m_s': float(np.linalg.norm(bias[3:6], axis=0).sum()),
            'scope': 'Declared deterministic amplitudes, local linear Gaussian power, separate affine bias box. No empirically qualified amplitudes, nonlinear envelope or real RF qualification.'}


def forecast_systematics(forecast, extended_modes):
    """Use the forecast's signed error map, including minus excluded measurements.

    Covariance remains untouched. Fit and excluded errors may share the SAME
    coefficient; summing separate absolute bounds would lose cancellations.
    """
    if forecast['status'] != 'CONDITIONAL_INTERVAL_FORECAST':
        raise ValueError('accepted interval forecast required')
    mapping = forecast['mapping']
    modes = np.asarray(extended_modes, float)
    if modes.ndim != 2 or modes.shape[0] != mapping.shape[1] or not np.isfinite(modes).all():
        raise ValueError('finite extended systematic columns required')
    output = mapping@modes
    return {'output_bias_modes': output,
            'affine_box_output_component_bound': np.sum(abs(output), axis=1),
            'affine_box_position_norm_bound_m': float(np.linalg.norm(output[:3], axis=0).sum()),
            'affine_box_velocity_norm_bound_m_s': float(np.linalg.norm(output[3:6], axis=0).sum()),
            'real_rf_qualified': False}
