"""RINEX reference code -> clock fit -> excluded reference Doppler check.

Broadcast states are permitted only for NON-target references. This development
bridge does not qualify an instrument or provide a total real-RF error budget.
"""
from dataclasses import asdict
import hashlib

import numpy as np
from scipy.linalg import solve_triangular
from scipy.optimize import least_squares
from scipy.stats import chi2

from positioning.calibration import state_and_clock, rotate_z, troposphere
from positioning.context import Context
from positioning.navigation import parse_gps_record
from .receiver_time import C, OMEGA, cholesky_covariance
from .rinex_observations import GPS


def admit_navigation(content, *, target, references):
    """Strip excluded navigation payloads as text before any numeric parsing.

    RINEX 3.04/3.05 GPS-only navigation subset. Other constellations are rejected
    explicitly; unknown block lengths must not desynchronize admission.
    """
    if not GPS.fullmatch(target) or target in references or any(not GPS.fullmatch(s) for s in references):
        raise ValueError('invalid non-target reference list')
    lines = content.splitlines()
    if (not lines or lines[0][60:80].strip() != 'RINEX VERSION / TYPE'
            or lines[0][:9].strip() not in ('3.04', '3.05')
            or lines[0][20:21] != 'N' or lines[0][40:41] != 'G'):
        raise ValueError('require RINEX 3.04/3.05 GPS navigation subset')
    try:
        start = next(i for i, line in enumerate(lines) if line[60:80].strip() == 'END OF HEADER')+1
    except StopIteration as error:
        raise ValueError('navigation header is incomplete') from error
    kept = [lines[0], ' '*60+'END OF HEADER']
    records = {satellite: [] for satellite in references}
    if (len(lines)-start) % 8:
        raise ValueError('truncated navigation block')
    for i in range(start, len(lines), 8):
        block = lines[i:i+8]
        satellite = block[0][:3]
        if not GPS.fullmatch(satellite) or any(not line.startswith('    ') for line in block[1:]):
            raise ValueError('invalid GPS navigation block structure')
        if satellite == target or satellite not in references:
            continue
        # Reject internal blanks instead of allowing the older primitive to
        # shift subsequent numerical fields into their place.
        for row_index, line in enumerate(block):
            offset, count = (23, 3) if row_index == 0 else (4, 2 if row_index == 7 else 4)
            for field in range(count):
                raw = line[offset+19*field:offset+19*(field+1)].strip().replace('D', 'E')
                if not raw or not np.isfinite(float(raw)):
                    raise ValueError('missing/nonfinite required navigation field')
        week = float(block[5][42:61].replace('D', 'E'))
        health = float(block[6][23:42].replace('D', 'E'))
        if week != int(week) or health != int(health):
            raise ValueError('nonintegral navigation week or health')
        record = parse_gps_record(block)
        numbers = [value for value in asdict(record).values() if isinstance(value, (float, int))]
        if (not np.isfinite(numbers).all() or not 0 <= record.eccentricity < 1
                or record.sqrt_a_m_sqrt <= 0 or record.sv_health != 0
                or record.fit_interval_h is None or record.fit_interval_h <= 0
                or not 0 <= record.toe_sow < 604800):
            raise ValueError('unqualified reference navigation record')
        records[satellite].append(record)
        kept.extend(block)
    if any(not entries for entries in records.values()):
        raise ValueError('missing declared reference navigation')
    admitted = '\n'.join(kept)+'\n'
    return records, admitted


def reference_code(record, tag_s, station, receiver_clock, *, context, base_second,
                   propagation, max_age_s=7200.):
    """Code prediction with a retarded reference state and reference clock.

    receiver_clock=[offset, drift per receiver-tag second]. Neutral delay,
    when enabled, enters both the flight time and the received code.
    """
    if record.satellite == context.target:
        raise ValueError('target propagation forbidden at reference-model boundary')
    if record.sv_health != 0 or record.fit_interval_h is None or record.fit_interval_h <= 0:
        raise ValueError('unqualified reference navigation at numerical boundary')
    if propagation not in ('vacuum', 'nominal_troposphere'):
        raise ValueError('explicit supported propagation model required')
    if (not np.isfinite([tag_s, base_second, max_age_s, *receiver_clock]).all()
            or max_age_s <= 0 or abs(receiver_clock[1]) >= .01*C):
        raise ValueError('invalid reference model inputs')
    receiver_error = receiver_clock[0]+receiver_clock[1]*tag_s
    receive = tag_s-receiver_error/C
    tau = .08
    for _ in range(15):
        tx = base_second+receive-tau
        toc_age = tx-(record.toc_gps-context.day).total_seconds()
        toe_age = (context.gps_week-record.gps_week)*604800+context.sow_midnight+tx-record.toe_sow
        if max(abs(toc_age), abs(toe_age)) > min(max_age_s, record.fit_interval_h*1800):
            raise ValueError('reference navigation outside declared validity')
        position, satellite_clock = state_and_clock(record, tx, context)
        rotated = rotate_z(position, -OMEGA*tau)
        geometric_range = np.linalg.norm(rotated-station)
        delay, elevation = troposphere(station, rotated)
        if propagation == 'vacuum':
            delay = 0.
        updated = (geometric_range+delay)/C
        if abs(updated-tau) < 2e-14:
            return C*updated+receiver_error-C*satellite_clock, elevation
        tau = updated
    raise ValueError('reference light-time iteration did not converge')


def sample_covariance(parsed, *, common_code_sigma_m=0., common_rate_sigma_m_s=0.):
    """Explicit design covariance, not an empirical noise estimate.

    Preserves within-pair code/Doppler terms; optional common modes do not
    disappear when observations are averaged. No hidden temporal independence
    claim: callers may instead supply their complete covariance to calibration.
    """
    if not np.isfinite([common_code_sigma_m, common_rate_sigma_m_s]).all() or min(common_code_sigma_m, common_rate_sigma_m_s) < 0:
        raise ValueError('invalid common-mode noise')
    n = len(parsed['samples'])
    covariance = np.zeros((2*n, 2*n))
    for i, row in enumerate(parsed['samples']):
        pair = np.asarray(row['covariance'])
        cholesky_covariance(pair, 2)
        covariance[np.ix_([i, n+i], [i, n+i])] = pair
    covariance[:n, :n] += common_code_sigma_m**2
    covariance[n:, n:] += common_rate_sigma_m_s**2
    return covariance


def doppler_residual_covariance(jac_code, jac_rate, covariance):
    """Propagate code-only clock fitting into the unused Doppler residuals.

    Includes code/rate cross-covariance, not just Var(rate)+Var(prediction).
    K is the local GLS gain from code errors to clock coefficient errors.
    """
    n = len(jac_code)
    cholesky_covariance(covariance, 2*n)
    weighted = np.linalg.solve(covariance[:n, :n], jac_code)
    clock_cov = np.linalg.inv(jac_code.T@weighted)
    gain = clock_cov@weighted.T
    mapping = np.column_stack([-jac_rate@gain, np.eye(n)])
    return clock_cov, mapping@covariance@mapping.T


def calibrate_references(parsed, navigation_text, *, covariance, propagation,
                         min_elevation_deg=10., max_age_s=7200.):
    """Fit clocks to reference codes only; predict their unused Doppler.

    Every planned reference/epoch must survive import and calibration. Failure
    stops the arc; no station/satellite reselection, residual clipping or retry.
    """
    result = {'real_rf_qualified': False, 'propagation': propagation,
              'scope': 'Reference-only model consistency on supplied covariance; receiver conventions, reference-product errors and total RF budget remain unqualified.'}
    if parsed['status'] != 'REFERENCE_WINDOW_PARSED':
        return result | {'status': 'REFERENCE_WINDOW_REJECTED', 'rejections': parsed['rejections']}
    target = parsed['target']
    samples = parsed['samples']
    # Recheck exclusion BEFORE reading observation values or propagating records.
    if any(row['satellite'] == target for row in samples):
        raise ValueError('target observation forbidden at numerical reference boundary')
    tags = parsed['tags_s']
    references = parsed['references']
    expected = [(t, sv) for t in tags for sv in references]
    if (len(tags) < 3 or len(set(references)) < 4
            or [(row['tag_s'], row['satellite']) for row in samples] != expected):
        raise ValueError('require complete ordered epochs with four declared references')
    n = len(samples)
    covariance = np.asarray(covariance, dtype=float)
    chol = cholesky_covariance(covariance, 2*n)
    code_chol = chol[:n, :n]
    context = Context(target, parsed['base_day_gpst'])
    base_second = parsed['base_second']
    station = np.asarray(parsed['station_m'])
    if not np.isfinite(min_elevation_deg) or not -90 <= min_elevation_deg <= 90:
        raise ValueError('invalid elevation policy')
    records, admitted_navigation = admit_navigation(navigation_text, target=target, references=references)
    # Freeze one broadcast record per reference for this bounded arc and all
    # derivative stencils. Never switch ephemerides inside a derivative.
    midpoint = (tags[0]+tags[-1])/2+base_second
    selected = {sv: min(records[sv], key=lambda record: abs(
        (record.toc_gps-context.day).total_seconds()-midpoint)) for sv in references}
    code = np.array([row['code_m'] for row in samples])
    rate = np.array([row['rate_m_s'] for row in samples])
    if not np.isfinite(code).all() or not np.isfinite(rate).all():
        raise ValueError('nonfinite reference observations')
    result['admitted_navigation_sha256'] = hashlib.sha256(admitted_navigation.encode()).hexdigest()
    result['reference_record_toc_gpst'] = {sv: record.toc_gps.strftime('%Y-%m-%d %H:%M:%S')+' GPST'
                                           for sv, record in selected.items()}

    def prediction(clock, shift=0.):
        return np.array([reference_code(selected[row['satellite']], row['tag_s']+shift, station, clock,
            context=context, base_second=base_second, propagation=propagation, max_age_s=max_age_s)
            for row in samples])

    def codes(clock):
        return prediction(clock)[:, 0]

    def jacobian(function, clock):
        delta = np.diag([1., .001])
        return np.column_stack([(function(clock+d)-function(clock-d))/(2*d[i]) for i, d in enumerate(delta)])

    try:
        baseline = codes([0., 0.])
        initial = np.linalg.lstsq(np.column_stack([np.ones(n), [r['tag_s'] for r in samples]]),
                                  code-baseline, rcond=None)[0]
        fitted = least_squares(lambda clock: solve_triangular(code_chol, codes(clock)-code, lower=True),
            initial, jac=lambda clock: solve_triangular(code_chol, jacobian(codes, clock), lower=True),
            x_scale=[1e4, 1.], max_nfev=50, ftol=1e-11, xtol=1e-11, gtol=1e-9)
        if not fitted.success or np.linalg.matrix_rank(fitted.jac) != 2:
            return result | {'status': 'REFERENCE_CLOCK_FIT_UNAVAILABLE'}
        model = prediction(fitted.x)
        if np.any(model[:, 1] < min_elevation_deg):
            return result | {'status': 'REFERENCE_ELEVATION_REJECTED', 'minimum_elevation_deg': float(model[:, 1].min())}
        code_cost = float(fitted.fun@fitted.fun)
        result.update(clock_coefficients=fitted.x.tolist(), code_p=float(chi2.sf(code_cost, n-2)),
                      code_residuals_m=(code-model[:, 0]).tolist(),
                      tag_interval_s=[tags[0], tags[-1]], base_second=base_second,
                      base_day_gpst=parsed['base_day_gpst'])
        if result['code_p'] < .01:
            return result | {'status': 'REFERENCE_CODE_REJECTED'}

        def rates(clock):
            h = .1
            return (prediction(clock, -2*h)[:, 0]-8*prediction(clock, -h)[:, 0]
                    +8*prediction(clock, h)[:, 0]-prediction(clock, 2*h)[:, 0])/(12*h)

        predicted_rate = rates(fitted.x)
        clock_cov, rate_cov = doppler_residual_covariance(jacobian(codes, fitted.x),
                                                         jacobian(rates, fitted.x), covariance)
        whitened_rate = solve_triangular(cholesky_covariance(rate_cov, n), rate-predicted_rate, lower=True)
        rate_p = float(chi2.sf(float(whitened_rate@whitened_rate), n))
        return result | {'status': 'REFERENCE_MODEL_ACCEPTED' if rate_p >= .01 else 'REFERENCE_DOPPLER_REJECTED',
            'clock_covariance': clock_cov.tolist(), 'doppler_p': rate_p,
            'doppler_residuals_m_s': (rate-predicted_rate).tolist(),
            'doppler_residual_covariance': rate_cov.tolist()}
    except ValueError as error:
        return result | {'status': 'REFERENCE_MODEL_UNAVAILABLE', 'reason': str(error)}
