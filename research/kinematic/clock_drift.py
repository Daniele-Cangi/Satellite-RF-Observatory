"""Affine clock calibration from admitted NON-target reference residuals only.

The upstream residual generator, atmospheric treatment and covariance of real
reference products are not delivered here. This is a synthetic S2a boundary.
"""
from datetime import date
import re

import numpy as np
from scipy.linalg import solve_triangular
from scipy.stats import chi2

from .receiver_time import cholesky_covariance


def local_gpst_seconds(day, seconds_of_day, *, base_day, base_second):
    """Calendar arithmetic in GPST, including day/week crossings; no UTC conversion."""
    if (not isinstance(base_second, int) or not 0 <= base_second < 86400
            or not np.isfinite(seconds_of_day) or not 0 <= seconds_of_day < 86400):
        raise ValueError('valid seconds of GPST day and integer base second required')
    whole_days = (date.fromisoformat(day)-date.fromisoformat(base_day)).days
    result = whole_days*86400-base_second+float(seconds_of_day)
    if abs(result) > 86400:
        raise ValueError('use a nearby integer GPST base epoch')
    return result


def admit_reference_rows(rows, *, target):
    """Discard target-labelled payloads before inspecting their numeric fields."""
    if not re.fullmatch(r'G(?:0[1-9]|[12][0-9]|3[0-2])', target):
        raise ValueError('GPS target label required')
    return [row for row in rows if row['satellite'] != target]


def fit_reference_clock(rows, covariance, *, target):
    """GLS for B_receiver(T)=offset+drift*T from reference code-clock residuals.

    One station/continuous arc per call; covariance ordering matches rows. Rows
    contain satellite, tag_s, clock_m, after independently removing reference
    geometry/clock/propagation. Reject target again BEFORE any numerical access.
    Require >=3 epochs and >=4 distinct references at every epoch. No clipping.
    """
    if not re.fullmatch(r'G(?:0[1-9]|[12][0-9]|3[0-2])', target):
        raise ValueError('GPS target label required')
    if not rows or any(row['satellite'] == target for row in rows):
        raise ValueError('target record forbidden at numerical clock-calibration boundary')
    if any(not re.fullmatch(r'G(?:0[1-9]|[12][0-9]|3[0-2])', row['satellite']) for row in rows):
        raise ValueError('GPS reference labels required')
    t = np.array([float(row['tag_s']) for row in rows])
    y = np.array([float(row['clock_m']) for row in rows])
    if not np.isfinite(t).all() or not np.isfinite(y).all() or np.max(np.abs(t)) > 86400:
        raise ValueError('finite local reference clock samples required')
    epochs = np.unique(t)
    if len(epochs) < 3 or any(len({row['satellite'] for row in rows if float(row['tag_s']) == ti}) < 4 for ti in epochs):
        raise ValueError('require at least three epochs with four references each')
    if len({(row['satellite'], float(row['tag_s'])) for row in rows}) != len(rows):
        raise ValueError('duplicate reference clock sample')
    chol = cholesky_covariance(covariance, len(rows))
    design = np.column_stack([np.ones(len(t)), t])
    whitened = solve_triangular(chol, design, lower=True)
    values = solve_triangular(chol, y, lower=True)
    coefficients, _, rank, _ = np.linalg.lstsq(whitened, values, rcond=None)
    if rank != 2:
        raise ValueError('rank deficient clock arc')
    residual = whitened@coefficients-values
    cost = float(residual@residual)
    p = float(chi2.sf(cost, len(rows)-2))
    return {'coefficients': coefficients, 'covariance': np.linalg.inv(whitened.T@whitened),
            'tag_interval_s': [float(epochs[0]), float(epochs[-1])],
            'references': sorted({row['satellite'] for row in rows}),
            'nominal_residual_p': p, 'weighted_residual_cost': cost,
            'status': 'CLOCK_MODEL_REJECTED' if p < .01 else 'CONDITIONAL_CLOCK_MODEL_ACCEPTED',
            'scope': 'Affine clock on supplied reference residuals; no real calibration qualification or automatic extrapolation.'}
