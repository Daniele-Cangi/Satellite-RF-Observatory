"""Header-only capability facts and simple neutral-delay sensitivity.

Header declarations are not receiver qualification. No orbit or RF values
are consumed. The neutral basis is a stated plane-parallel approximation,
not a weather model, fitted correction or empirical uncertainty floor.
"""
import hashlib
import json
import re

import numpy as np


def inspect_header(header):
    if not header:
        return {'status': 'HEADER_UNAVAILABLE', 'real_rf_qualified': False}
    types, current, expected = [], None, None
    for row in header.get('SYS / # / OBS TYPES', []):
        if row[:1].strip():
            if current == 'G' and len(types) != expected:
                raise ValueError('incomplete GPS observation declaration')
            current = row[:1]
            if current == 'G':
                if expected is not None:
                    raise ValueError('duplicate GPS observation declaration')
                expected = int(row[3:6])
        if current == 'G':
            types.extend(row[7:60].split())
    if expected is None or not 1 <= expected <= 99 or len(types) != expected or len(set(types)) != len(types):
        raise ValueError('incomplete or duplicate GPS observation declaration')
    if any(not re.fullmatch(r'[CLDS][1-9][A-Z]', name) for name in types):
        raise ValueError('invalid GPS observation type')
    receiver = header.get('REC # / TYPE / VERS', [])
    if len(receiver) != 1:
        raise ValueError('single receiver identity required')
    identity = [receiver[0].ljust(60)[i:i+20].strip() for i in (0, 20, 40)]
    doppler = all(name in types for name in ('C1C', 'C2W', 'D1C', 'D2W', 'L1C', 'L2W'))
    phase = all(name in types for name in ('C1C', 'C2W', 'L1C', 'L2W'))
    return {'status': 'HEADER_CAPABILITIES_ONLY', 'receiver_identity': identity,
            'gps_types': types, 'required_doppler_declared': doppler,
            'phase_difference_candidate': phase,
            'missing_doppler_fields': [name for name in ('D1C', 'D2W') if name not in types],
            'reported_interval': header.get('INTERVAL', []),
            'antenna_identity': header.get('ANT # / TYPE', []),
            'header_sha256': hashlib.sha256(json.dumps(header, sort_keys=True, allow_nan=False).encode()).hexdigest(),
            'unresolved': ['Doppler temporal response', 'phase continuity beyond LLI flags',
                           'antenna/code biases', 'reference orbit/clock errors',
                           'ground coordinate covariance', 'neutral/ionospheric residuals'],
            'real_rf_qualified': False}


def neutral_delay_basis(tags_s, elevation_deg):
    """Rows (epoch, reference), columns zenith offset [m], drift [m/tag-second].

    Common 1/sin(elevation) dry/wet mapping, restricted to >=10 degrees.
    Multiplying by a two-component zenith error gives a slant phase/code error
    in metres under the nondispersive approximation. Difference these rows for
    interval-mean phase rates; never add independent noise at every reference.
    """
    tags, elevation = np.asarray(tags_s, float), np.asarray(elevation_deg, float)
    if (tags.ndim != 1 or len(tags) < 2 or np.any(np.diff(tags) <= 0)
            or elevation.ndim != 2 or elevation.shape[0] != len(tags)
            or not all(np.isfinite(a).all() for a in (tags, elevation))
            or np.any((elevation < 10) | (elevation > 90))):
        raise ValueError('finite ordered tags and elevations in [10,90] degrees required')
    mapping = 1/np.sin(np.deg2rad(elevation))
    return np.column_stack([mapping.ravel(), (mapping*tags[:, None]).ravel()])
