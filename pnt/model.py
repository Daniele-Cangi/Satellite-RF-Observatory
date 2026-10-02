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


def broadcast_navigation(data):
    """Adapt plain/gzipped RINEX 2 GPS NAV to the existing record parser."""
    decoded = gzip.decompress(data) if data.startswith(b'\x1f\x8b') else data
    lines = decoded.decode('ascii').splitlines()
    stop = next((i for i, line in enumerate(lines) if line[60:80].strip() == 'END OF HEADER'), None)
    if stop is None:
        raise ValueError('incomplete GPS navigation header')
    version = [line[:60] for line in lines[:stop] if line[60:80].strip() == 'RINEX VERSION / TYPE']
    if len(version) != 1 or not 2 <= float(version[0][:9]) < 3 or 'GPS NAV DATA' not in version[0]:
        raise ValueError('expected one RINEX 2 GPS navigation header')
    body = lines[stop + 1:]
    if not body or len(body) % 8:
        raise ValueError('truncated GPS navigation record')
    records, counts = defaultdict(list), Counter()
    for start in range(0, len(body), 8):
        block = body[start:start + 8]
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
        normalized = [prefix + block[0][22:]] + [' ' + line for line in block[1:]]
        record = parse_gps_record(normalized)
        if any(isinstance(value := getattr(record, field.name), (int, float)) and
               not math.isfinite(value) for field in fields(record)):
            raise ValueError('nonfinite GPS navigation value')
        counts['source_records'] += 1
        if record.sv_health != 0 or not 0 <= record.eccentricity < 1 or record.sqrt_a_m_sqrt <= 0:
            counts['unhealthy_or_invalid_records'] += 1
            continue
        records[record.satellite].append(record)
        counts['admitted_records'] += 1
    if not records:
        raise ValueError('no usable GPS navigation records')
    return records, dict(sorted(counts.items()))


def nearest_record(navigation, satellite, time_s, context):
    records = navigation.get(satellite, ())
    if not records:
        raise ValueError('MISSING_NAVIGATION')
    record = min(records, key=lambda r: abs((r.toc_gps - context.day).total_seconds() - time_s))
    age = abs((record.toc_gps - context.day).total_seconds() - time_s)
    # Accept a previous-week record only across a week boundary; age still
    # binds the absolute toc, and propagation uses the record's GPS week.
    toe = GPS_EPOCH + timedelta(seconds=record.gps_week * 604800 + record.toe_sow)
    if age > MAX_NAV_AGE_S or abs((toe - record.toc_gps).total_seconds()) > MAX_NAV_AGE_S:
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
