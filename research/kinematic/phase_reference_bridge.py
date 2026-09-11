"""Code-only reference clock fit, followed by unused IF phase-increment test.

The common code/carrier baseline assumes first-order IF ionosphere removal,
constant ambiguities and no varying differential hardware/antenna terms.
This is a reference model consistency check, not receiver qualification.
"""
import hashlib

import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import least_squares
from scipy.stats import chi2

from positioning.context import Context
from .phase_rates import interval_matrix
from .receiver_time import cholesky_covariance
from .reference_bridge import admit_navigation, reference_code


def phase_residual_covariance(jac_code, jac_rate, covariance):
    """Rectangular code/rate blocks; include code-fitted clock and cross terms."""
    jc, jr, cov = [np.asarray(a, float) for a in (jac_code, jac_rate, covariance)]
    if (jc.ndim != 2 or jc.shape[1] != 2 or len(jc) < 3 or jr.ndim != 2 or jr.shape[1] != 2
            or not len(jr) or not np.isfinite(jc).all() or not np.isfinite(jr).all()):
        raise ValueError('two clock columns required')
    n, m = len(jc), len(jr)
    cholesky_covariance(cov, n+m)
    chol = cholesky_covariance(cov[:n, :n], n)
    whitened = solve_triangular(chol, jc, lower=True)
    u, singular, vh = np.linalg.svd(whitened, full_matrices=False)
    if not np.isfinite(whitened).all() or singular[-1] <= singular[0]*1e-10:
        raise ValueError('reference clock rank deficient')
    inverse = (vh.T/singular)@u.T
    gain = inverse@solve_triangular(chol, np.eye(n), lower=True)
    mapping = np.column_stack([-jr@gain, np.eye(m)])
    transported = mapping@cov@mapping.T
    return inverse@inverse.T, (transported+transported.T)/2


def calibrate_phase_references(parsed, navigation_text, *, propagation,
                               min_elevation_deg=10., max_age_s=7200.):
    result = {'real_rf_qualified': False, 'propagation': propagation,
              'scope': 'Code-fitted reference clock, unused interval phase test with local full covariance. No real receiver, reference-product or atmospheric qualification.'}
    if parsed['status'] != 'REFERENCE_PHASE_WINDOW_PARSED':
        return result | {'status': 'REFERENCE_PHASE_WINDOW_REJECTED', 'reasons': parsed.get('reasons', [])}
    samples, target = parsed['samples'], parsed['target']
    if any(row['satellite'] == target for row in samples):
        raise ValueError('target observation forbidden before reference numerics')
    tags, references = np.asarray(parsed['tags_s'], float), parsed['references']
    if (len(tags) < 3 or len(references) < 4 or len(set(references)) != len(references)
            or [(row['tag_s'], row['satellite']) for row in samples] != [(t, sv) for t in tags for sv in references]):
        raise ValueError('complete fixed reference endpoints required')
    difference = interval_matrix(tags, len(references))
    if (not np.array_equal(parsed['interval_start_s'], tags[:-1])
            or not np.array_equal(parsed['interval_end_s'], tags[1:])):
        raise ValueError('phase intervals differ from code endpoints')
    codes, rates = np.array([r['code_m'] for r in samples]), np.asarray(parsed['mean_phase_rate_m_s'], float)
    if rates.shape != (len(tags)-1, len(references)) or not np.isfinite(codes).all() or not np.isfinite(rates).all():
        raise ValueError('finite complete code/phase pairs required')
    rates = rates.ravel()
    covariance = np.asarray(parsed['covariance_code_phase_rate'], float)
    chol = cholesky_covariance(covariance, len(codes)+len(rates))[:len(codes), :len(codes)]
    if not np.isfinite(min_elevation_deg) or not -90 <= min_elevation_deg <= 90:
        raise ValueError('invalid elevation policy')
    context = Context(target, parsed['base_day_gpst'])
    records, admitted = admit_navigation(navigation_text, target=target, references=references)
    midpoint = (tags[0]+tags[-1])/2+parsed['base_second']
    selected = {sv: min(records[sv], key=lambda record: abs((record.toc_gps-context.day).total_seconds()-midpoint)) for sv in references}
    result['admitted_navigation_sha256'] = hashlib.sha256(admitted.encode()).hexdigest()
    result['admitted_observations_sha256'] = parsed['admitted_observations_sha256']
    result['reference_record_toc_gpst'] = {sv: record.toc_gps.strftime('%Y-%m-%d %H:%M:%S')+' GPST' for sv, record in selected.items()}

    def prediction(clock):
        return np.array([reference_code(selected[row['satellite']], row['tag_s'], np.asarray(parsed['station_m']), clock,
            context=context, base_second=parsed['base_second'], propagation=propagation, max_age_s=max_age_s) for row in samples])

    def model(clock):
        return prediction(clock)[:, 0]

    def jacobian(function, clock):
        perturb = np.diag([1., .001])
        return np.column_stack([(function(clock+d)-function(clock-d))/(2*d[i]) for i, d in enumerate(perturb)])

    try:
        initial = np.linalg.lstsq(np.column_stack([np.ones(len(codes)), [row['tag_s'] for row in samples]]), codes-model([0., 0.]), rcond=None)[0]
        fitted = least_squares(lambda clock: solve_triangular(chol, model(clock)-codes, lower=True), initial,
            jac=lambda clock: solve_triangular(chol, jacobian(model, clock), lower=True),
            x_scale=[1e4, 1.], max_nfev=50, ftol=1e-11, xtol=1e-11, gtol=1e-9)
        if not fitted.success or np.linalg.matrix_rank(fitted.jac) != 2:
            return result | {'status': 'REFERENCE_CLOCK_FIT_UNAVAILABLE'}
        predicted = prediction(fitted.x)
        if predicted[:, 1].min() < min_elevation_deg:
            return result | {'status': 'REFERENCE_ELEVATION_REJECTED', 'minimum_elevation_deg': float(predicted[:, 1].min())}
        code_cost = float(fitted.fun@fitted.fun)
        result.update(clock_coefficients=fitted.x, code_p=float(chi2.sf(code_cost, len(codes)-2)),
            code_residuals_m=codes-predicted[:, 0], code_dof=len(codes)-2,
            tag_interval_s=[tags[0], tags[-1]], base_day_gpst=parsed['base_day_gpst'], base_second=parsed['base_second'])
        if result['code_p'] < .01:
            return result | {'status': 'REFERENCE_CODE_REJECTED'}
        # Both phase and predicted baseline are differenced at identical endpoints.
        predicted_rate = difference@predicted[:, 0]
        jc = jacobian(model, fitted.x)
        jr = difference@jc
        clock_cov, residual_cov = phase_residual_covariance(jc, jr, covariance)
        residual = rates-predicted_rate
        whitened = solve_triangular(cholesky_covariance(residual_cov, len(rates)), residual, lower=True)
        phase_cost = float(whitened@whitened)
        phase_p = float(chi2.sf(phase_cost, len(rates)))
        return result | {'status': 'REFERENCE_PHASE_MODEL_ACCEPTED' if phase_p >= .01 else 'REFERENCE_PHASE_RESIDUAL_REJECTED',
            'clock_covariance': clock_cov, 'phase_p': phase_p, 'phase_cost': phase_cost,
            'phase_dof': len(rates), 'phase_residuals_m_s': residual,
            'phase_residual_covariance': residual_cov, 'predicted_mean_phase_rate_m_s': predicted_rate}
    except ValueError as error:
        return result | {'status': 'REFERENCE_MODEL_UNAVAILABLE', 'reason': str(error)}
