"""Non-target IF carrier-phase interval rates: not instantaneous Doppler.

No automatic substitution in RINEX Doppler admission or the joint estimator.
LLI/event checks catch reported discontinuities, not every undetected slip.
Units: input L1C/L2W cycles, output mean phase-path rate m/receiver-tag second.
"""
import hashlib
import json

import numpy as np

from .doppler import ALPHA, BETA, F1_HZ as F1, F2_HZ as F2
from .inverse_uncertainty import validate_covariance
from .receiver_time import C
from .rinex_observations import GPS


def interval_matrix(tags_s, reference_count):
    tags = np.asarray(tags_s, float)
    if (tags.ndim != 1 or len(tags) < 2 or not np.isfinite(tags).all()
            or np.any(np.diff(tags) <= 0) or not isinstance(reference_count, int) or reference_count < 1):
        raise ValueError('ordered finite endpoint tags and positive reference count required')
    difference = np.zeros((len(tags)-1, len(tags)))
    for i, dt in enumerate(np.diff(tags)):
        difference[i, i:i+2] = [-1/dt, 1/dt]
    return np.kron(difference, np.eye(reference_count))


def reference_phase_rates(rows, *, target, references, tags_s, phase_covariance):
    """Admit a complete fixed grid of raw RINEX phase fields for references only.

    Drop target/unlisted satellites before reading tags or numeric payloads.
    Covariance order is epoch/reference/band(L1C,L2W), in cycles squared.
    Data outside the fixed endpoint window are not decoded. No interpolation,
    gap bridging, phase unwrapping, slip repair or receiver-clock fitting.
    """
    references = tuple(references)
    tags = np.asarray(tags_s, float)
    if (not GPS.fullmatch(target) or target in references or len(references) < 4
            or len(set(references)) != len(references)
            or any(not GPS.fullmatch(s) for s in references)):
        raise ValueError('four distinct non-target GPS references required')
    differencing = interval_matrix(tags, len(references))
    if np.any(np.abs(np.diff(tags)-np.diff(tags)[0]) > 1e-7):
        raise ValueError('fixed regular reference endpoint grid required')
    admitted, reasons = {}, []
    for row in rows:
        satellite = row['satellite']
        if satellite not in references:  # Target exclusion before numeric decoding.
            continue
        tag = float(row['tag_s'])
        if not np.isfinite(tag):
            raise ValueError('nonfinite reference tag')
        if tag < tags[0]-1e-7 or tag > tags[-1]+1e-7:
            continue
        matching = np.flatnonzero(abs(tags-tag) <= 1e-7)
        if len(matching) != 1:
            raise ValueError('off-grid reference epoch')
        key = (int(matching[0]), satellite)
        if key in admitted:
            raise ValueError('duplicate reference phase row')
        admitted[key] = None
        if row['epoch_flag'] != 0:
            reasons.append({'key': key, 'reason': 'EVENT_OR_CLOCK_RESET'})
            continue
        values = []
        for name in ('L1C', 'L2W'):
            field = row['fields'].get(name, '').ljust(16)
            try:
                value = float(field[:14])
            except ValueError:
                value = float('nan')
            if len(field) > 16 or not np.isfinite(value) or value == 0 or field[14] not in (' ', '0'):
                reasons.append({'key': key, 'reason': 'MISSING_INVALID_PHASE_OR_LOCK_FLAG:'+name})
            values.append(value)
        admitted[key] = values
    ordered = [(i, satellite) for i in range(len(tags)) for satellite in references]
    reasons.extend({'key': key, 'reason': 'MISSING_PLANNED_ENDPOINT'} for key in ordered if key not in admitted)
    if reasons:
        return {'status': 'REFERENCE_PHASE_WINDOW_REJECTED', 'reasons': reasons, 'real_rf_qualified': False}
    covariance = validate_covariance(phase_covariance, 2*len(ordered))
    phases = np.array([admitted[key] for key in ordered]).ravel()
    combination = np.kron(np.eye(len(ordered)), np.array([[ALPHA*C/F1, BETA*C/F2]]))
    transform = differencing@combination
    rate = transform@phases
    rate_covariance = transform@covariance@transform.T
    canonical = {'references': references, 'tags_s': tags.tolist(), 'phases_cycles': phases.tolist()}
    return {'status': 'REFERENCE_PHASE_RATE_AVAILABLE', 'real_rf_qualified': False,
            'references': list(references), 'interval_start_s': tags[:-1], 'interval_end_s': tags[1:],
            'mean_phase_rate_m_s': rate.reshape(len(tags)-1, len(references)),
            'covariance_rate': (rate_covariance+rate_covariance.T)/2,
            'transform_cycles_to_mean_rate': transform,
            'admitted_phase_sha256': hashlib.sha256(json.dumps(canonical, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            'scope': 'Ionosphere-free phase increment per receiver-tag interval; not instantaneous Doppler or code derivative. Unknown slips, multipath, antenna, reference and atmosphere errors remain unqualified.'}


def predict_interval_rate(phase_path_m, tags_s, reference_count):
    """Apply the SAME interval observable to a declared carrier-path model."""
    difference = interval_matrix(tags_s, reference_count)
    phase = np.asarray(phase_path_m, float)
    if phase.shape != (len(tags_s), reference_count) or not np.isfinite(phase).all():
        raise ValueError('finite modelled carrier path at every endpoint required')
    return (difference@phase.ravel()).reshape(len(tags_s)-1, reference_count)
