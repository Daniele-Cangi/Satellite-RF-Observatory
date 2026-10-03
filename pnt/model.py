"""Reusable broadcast-model code diagnostics, including the common clock mode."""

from collections import Counter, defaultdict
from dataclasses import fields
from datetime import datetime, timedelta, timezone
import gzip
import math
from types import SimpleNamespace

import numpy as np

from positioning.calibration import reference_model
from positioning.navigation import parse_gps_record


GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
MAX_NAV_AGE_S = 7200


def day_context(day):
    midnight = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
    elapsed = (midnight - GPS_EPOCH).total_seconds()
    if elapsed < 0:
        raise ValueError('day predates GPS time')
    # All GPS orbits are explicitly admitted hypotheses in this consistency
    # diagnostic. This is not the inverse experiment's target-state fit.
    return SimpleNamespace(target='', day=midnight, gps_week=int(elapsed // 604800),
                           sow_midnight=elapsed % 604800)


def navigation_blocks(data):
    """Normalize plain/gzipped RINEX 2/3 GPS NAV without discarding fields.

    Mixed-constellation and RINEX 4 files are outside this adapter. Reject
    them rather than guessing record lengths or silently dropping messages.
    """
    decoded = gzip.decompress(data) if data.startswith(b'\x1f\x8b') else data
    lines = decoded.decode('ascii').splitlines()
    stop = next((i for i, line in enumerate(lines) if line[60:80].strip() == 'END OF HEADER'), None)
    if stop is None:
        raise ValueError('incomplete GPS navigation header')
    versions = [line[:60] for line in lines[:stop] if line[60:80].strip() == 'RINEX VERSION / TYPE']
    if len(versions) != 1:
        raise ValueError('expected one RINEX 2 GPS or RINEX 3 GPS navigation header')
    header = versions[0]
    version = float(header[:9])
    is_v2 = 2 <= version < 3 and 'GPS NAV DATA' in header
    is_v3 = 3 <= version < 4 and header[20:21] == 'N' and header[40:41] == 'G'
    if not (is_v2 or is_v3):
        raise ValueError('expected one RINEX 2 GPS or RINEX 3 GPS navigation header')
    body = lines[stop + 1:]
    if not body or len(body) % 8:
        raise ValueError('truncated GPS navigation record')
    for start in range(0, len(body), 8):
        block = body[start:start + 8]
        if is_v3:
            prefix = block[0][:23]
            if (not prefix.startswith('G') or len(prefix) != 23 or
                    not prefix[1:3].isdigit() or not 1 <= int(prefix[1:3]) <= 32 or
                    any(not line.startswith('    ') for line in block[1:])):
                raise ValueError('invalid RINEX 3 GPS navigation block')
            # Validate the fixed epoch separately from the floating clock
            # fields. Preserve every serialized digit for issue comparison.
            try:
                epoch = datetime.strptime(prefix[3:], ' %Y %m %d %H %M %S')
            except ValueError as error:
                raise ValueError('invalid RINEX 3 GPS navigation epoch') from error
            if prefix != 'G' + prefix[1:3] + epoch.strftime(' %Y %m %d %H %M %S'):
                raise ValueError('invalid RINEX 3 GPS navigation epoch width')
            yield block
            continue
        values = block[0][:22].split()
        if len(values) != 7 or any(not line.startswith('   ') for line in block[1:]):
            raise ValueError('invalid RINEX 2 GPS navigation block')
        prn, yy, month, day, hour, minute = (int(value) for value in values[:6])
        second = float(values[6])
        if not 1 <= prn <= 32 or not math.isfinite(second) or second != int(second):
            raise ValueError('unsupported GPS navigation epoch or PRN')
        year = 2000 + yy if yy < 80 else 1900 + yy
        prefix = f'G{prn:02d} {year:04d} {month:02d} {day:02d} {hour:02d} {minute:02d} {int(second):02d}'
        if len(prefix) != 23:
            raise ValueError('invalid GPS navigation epoch width')
        yield [prefix + block[0][22:]] + [' ' + line for line in block[1:]]


def indexed_broadcast_navigation(data, *, require_usable=True):
    """Admit model records and retain their original NAV indices for evidence binding."""
    records, counts, indices = defaultdict(list), Counter(), {}
    for index, normalized in enumerate(navigation_blocks(data)):
        record = parse_gps_record(normalized)
        if any(isinstance(value := getattr(record, field.name), (int, float)) and
               not math.isfinite(value) for field in fields(record)):
            raise ValueError('nonfinite GPS navigation value')
        counts['source_records'] += 1
        if record.sv_health != 0 or not 0 <= record.eccentricity < 1 or record.sqrt_a_m_sqrt <= 0:
            counts['unhealthy_or_invalid_records'] += 1
            continue
        records[record.satellite].append(record)
        indices[id(record)] = index
        counts['admitted_records'] += 1
    if require_usable and not records:
        raise ValueError('no usable GPS navigation records')
    return records, dict(sorted(counts.items())), indices


def broadcast_navigation(data):
    """Adapt RINEX 2/3 GPS NAV with the same model admission rules."""
    records, counts, _ = indexed_broadcast_navigation(data)
    return records, counts


def nearest_record(navigation, satellite, time_s, context):
    records = navigation.get(satellite, ())
    if not records:
        raise ValueError('MISSING_NAVIGATION')
    record = min(records, key=lambda r: abs((r.toc_gps - context.day).total_seconds() - time_s))
    age = abs((record.toc_gps - context.day).total_seconds() - time_s)
    # RINEX's continuous week belongs to toe, including at a week boundary.
    # Bound observation-to-toe directly: short toc age and toe-to-toc distance
    # do not together bound orbit age. A declared fit duration can tighten the
    # symmetric toe-age guard, but never extend our two-hour admission cap.
    toe = GPS_EPOCH + timedelta(seconds=record.gps_week * 604800 + record.toe_sow)
    toe_age = abs((toe - context.day).total_seconds() - time_s)
    orbit_age_limit = MAX_NAV_AGE_S
    if record.fit_interval_h is not None:
        if not math.isfinite(record.fit_interval_h) or record.fit_interval_h <= 0:
            raise ValueError('INVALID_NAVIGATION_FIT_INTERVAL')
        orbit_age_limit = min(orbit_age_limit, record.fit_interval_h * 1800)
    if (age > MAX_NAV_AGE_S or toe_age > orbit_age_limit or
            abs((toe - record.toc_gps).total_seconds()) > MAX_NAV_AGE_S):
        raise ValueError('STALE_OR_WRONG_WEEK_NAVIGATION')
    return record


def fit_clock(codes, position, records, time_s, context, *, model=reference_model):
    """Fixed-coordinate median clock plus satellite residuals; no uncertainty bound."""
    if set(codes) != set(records) or len(codes) < 4:
        raise ValueError('incomplete common satellite set for clock fit')
    if not np.isfinite([*codes.values(), *position]).all():
        raise ValueError('nonfinite clock fit input')
    satellites = sorted(codes)
    clock = 0.0
    for _ in range(6):
        estimates = np.array([codes[sv] - model(records[sv], codes[sv], time_s,
                                               position, clock, context)[0]
                              for sv in satellites])
        updated = float(np.median(estimates))
        if abs(updated - clock) < 1e-6:
            clock = updated
            break
        clock = updated
    else:
        raise ValueError('receiver clock fit did not converge')
    estimates = np.array([codes[sv] - model(records[sv], codes[sv], time_s,
                                           position, clock, context)[0]
                          for sv in satellites])
    if not np.isfinite(estimates).all():
        raise ValueError('nonfinite clock residual')
    clock = float(np.median(estimates))
    residuals = estimates - clock
    return {'clock_m': clock,
            'median_absolute_satellite_residual_m': float(np.median(np.abs(residuals))),
            'max_absolute_satellite_residual_m': float(np.max(np.abs(residuals))),
            'satellite_residuals_m': dict(zip(satellites, map(float, residuals)))}
