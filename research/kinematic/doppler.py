"""Narrow GPS C1C/C2W/D1C/D2W RINEX-field adapter, not a file importer.

RINEX 3.05 sections 4.4, 6.7 and table 14: positive Doppler is approach;
LLI applies to phase fields only. See S2_MODEL.md for remaining qualification.
"""
import numpy as np

from .receiver_time import C, cholesky_covariance

F1_HZ, F2_HZ = 1575.42e6, 1227.60e6
ALPHA = F1_HZ**2/(F1_HZ**2-F2_HZ**2)
BETA = 1-ALPHA
# Input ordering C1C [m], C2W [m], D1C [Hz], D2W [Hz].
IF_TRANSFORM = np.array([[ALPHA, BETA, 0, 0],
                         [0, 0, -ALPHA*C/F1_HZ, -BETA*C/F2_HZ]])


def convert_gps_if(values, covariance):
    """Convert qualified dual-frequency values and propagate full covariance.

    Rate is negative wavelength times Doppler. Its instrument time basis and
    averaging interval still need receiver-specific qualification before fitting.
    """
    values = np.asarray(values, dtype=float)
    if values.shape != (4,) or not np.isfinite(values).all() or np.any(values[:2] <= 0):
        raise ValueError('require finite GPS codes in meters and Dopplers in Hz')
    cholesky_covariance(covariance, 4)
    return IF_TRANSFORM@values, IF_TRANSFORM@np.asarray(covariance)@IF_TRANSFORM.T


def admit_fields(fields, *, epoch_flag, gap_s, expected_step_s):
    """Conservative, explicit paired-row policy; no interpolation or signal swap.

    fields maps RINEX observation names to raw 16-character fields. Require the
    companion L1C/L2W phase solely to inspect flags; do not use their values in a
    motion solution. Missing/zero Doppler is not silently treated as zero speed.
    Absence of a reported slip does not certify continuous physical tracking.
    """
    reasons = []
    if (not np.isfinite([gap_s, expected_step_s]).all() or expected_step_s <= 0
            or gap_s != expected_step_s):
        reasons.append('GAP_OR_UNKNOWN_PREDECESSOR')
    if epoch_flag != 0:
        reasons.append('NON_NORMAL_EPOCH')
    parsed = {}
    for name in ('C1C', 'C2W', 'D1C', 'D2W', 'L1C', 'L2W'):
        raw = fields.get(name, '')
        if not isinstance(raw, str) or len(raw) > 16:
            reasons.append('MALFORMED_'+name)
            continue
        raw = raw.ljust(16)
        try:
            value = float(raw[:14])
        except ValueError:
            reasons.append('MISSING_OR_INVALID_'+name)
            continue
        if not np.isfinite(value) or value == 0 or (name.startswith('C') and value < 0):
            reasons.append('MISSING_OR_INVALID_'+name)
            continue
        parsed[name] = value
        if name.startswith('L'):
            flag = raw[14]
            if flag not in ' 01234567':
                reasons.append('INVALID_PHASE_LLI_'+name)
            elif flag not in ' 0':
                reasons.append('PHASE_TRACKING_FLAG_'+name)
    if reasons:
        return {'status': 'PAIR_NOT_ADMITTED', 'reasons': reasons}
    return {'status': 'PAIR_FIELDS_ADMITTED', 'reasons': [],
            'values': np.array([parsed[k] for k in ('C1C', 'C2W', 'D1C', 'D2W')]),
            'scope': 'Field-level check only; no receiver/header/propagation qualification.'}
