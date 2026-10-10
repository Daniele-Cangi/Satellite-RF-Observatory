"""Offline GPS L1/L5 intake of Android GNSS Logger Raw measurements.

Normalize observations, not authenticity or incident labels. The clock solution
in each source row is used as supplied; it is not an independent time witness.
"""

from collections import Counter
import csv
from decimal import Decimal, DecimalException, InvalidOperation, localcontext
import gzip
import hashlib
import math
from pathlib import Path


WEEK_NS = 604800_000_000_000
LIGHT_SPEED = Decimal('299792458')
REQUIRED = {
    'Raw', 'TimeNanos', 'FullBiasNanos', 'BiasNanos', 'TimeOffsetNanos',
    'HardwareClockDiscontinuityCount', 'Svid', 'ConstellationType',
    'CarrierFrequencyHz', 'CodeType', 'State', 'ReceivedSvTimeNanos',
}


def _decimal(values, name, *, optional=False):
    value = values.get(name, '')
    if value == '' and optional:
        return None
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f'invalid {name}') from error
    if not result.is_finite():
        raise ValueError(f'nonfinite {name}')
    return result


def _integer(values, name):
    # Android's integer fields must never pass through float at GPS epoch scale.
    value = _decimal(values, name)
    if value != value.to_integral_value():
        raise ValueError(f'noninteger {name}')
    if not -(2**63) <= value < 2**63:
        raise ValueError(f'out-of-range integer {name}')
    return int(value)


def _number(values, name):
    value = _decimal(values, name, optional=True)
    if value is None:
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f'out-of-range {name}')
    return result


def _gps_row(values, line):
    """Retain even unsupported/unusable GPS rows, including their source fields."""
    row = {'source_line': line, 'source_values': values, 'status': 'NORMALIZED',
           'signal': None, 'pseudorange_m': None, 'receiver_gpst_ns': None,
           'adr_usable': False}
    prn = _integer(values, 'Svid')
    if not 1 <= prn <= 32:
        raise ValueError('GPS Svid outside 1..32')
    row['satellite'] = f'G{prn:02d}'
    state = _integer(values, 'State')
    discontinuity = _integer(values, 'HardwareClockDiscontinuityCount')
    if state < 0 or discontinuity < 0:
        raise ValueError('negative state or clock discontinuity count')
    row.update(state=state, hardware_clock_discontinuity_count=discontinuity)
    frequency = _number(values, 'CarrierFrequencyHz')
    # The tolerance accommodates float32 serialization of nominal frequencies.
    # CodeType is mandatory: frequency alone cannot identify a tracking code.
    code = values['CodeType']
    if frequency is not None and abs(frequency - 1575420000) <= 1000 and code == 'C':
        row['signal'] = 'C1C'
    elif frequency is not None and abs(frequency - 1176450000) <= 1000 and code in ('I', 'Q', 'X'):
        row['signal'] = 'C5' + code
    row.update(carrier_frequency_hz=frequency,
               cn0_db_hz=_number(values, 'Cn0DbHz'),
               pseudorange_rate_m_s=_number(values, 'PseudorangeRateMetersPerSecond'),
               pseudorange_rate_uncertainty_m_s=_number(values, 'PseudorangeRateUncertaintyMetersPerSecond'),
               adr_m=_number(values, 'AccumulatedDeltaRangeMeters'),
               adr_uncertainty_m=_number(values, 'AccumulatedDeltaRangeUncertaintyMeters'))
    adr = values.get('AccumulatedDeltaRangeState', '')
    adr_state = _integer(values, 'AccumulatedDeltaRangeState') if adr else None
    if adr_state is not None and adr_state < 0:
        raise ValueError('negative ADR state')
    row['adr_state'] = adr_state
    row['adr_usable'] = bool(
        adr_state is not None and adr_state & 1 and not adr_state & (2 | 4)
        and (not adr_state & 16 or adr_state & 8)
        and row['adr_m'] is not None and row['adr_uncertainty_m'] is not None
        and row['adr_uncertainty_m'] >= 0)
    if row['signal'] is None:
        row['status'] = 'UNSUPPORTED_GPS_SIGNAL'
        return row
    if not state & 1 or not state & (8 | 16384) or state & 16:
        row['status'] = 'UNRESOLVED_GPS_TRANSMIT_TIME'
        return row
    if values['FullBiasNanos'] == '':
        row['status'] = 'MISSING_FULL_BIAS'
        return row
    time = _integer(values, 'TimeNanos')
    bias = _integer(values, 'FullBiasNanos')
    tx = _integer(values, 'ReceivedSvTimeNanos')
    if not 0 <= tx < WEEK_NS:
        raise ValueError('GPS transmit TOW outside one week')
    with localcontext() as context:
        context.prec = 40
        fine_bias = _decimal(values, 'BiasNanos', optional=True)
        offset = _decimal(values, 'TimeOffsetNanos')
        rx = Decimal(time - bias) - (fine_bias or Decimal(0)) + offset
        if rx < 0:
            raise ValueError('receiver time predates GPS epoch')
        difference = (rx % WEEK_NS) - tx
        # Correct only the weekly transmit/reception rollover. Keep negative or
        # enormous ranges visible; do not repair a clock/measurement anomaly.
        if difference < -WEEK_NS // 2:
            difference += WEEK_NS
        elif difference > WEEK_NS // 2:
            difference -= WEEK_NS
        row['pseudorange_m'] = float(difference * LIGHT_SPEED / Decimal(1_000_000_000))
        row['receiver_gpst_ns'] = str(rx)
    row['bias_nanos_assumed_zero'] = fine_bias is None
    return row


def inspect_android_raw(path):
    """Return source-bound GPS records and complete Raw-row accounting.

    Unknown constellations are counted, never interpreted with GPS timing.
    Invalid GPS values remain visible rather than aborting other measurements.
    Ambiguous headers or truncated rows reject the whole input.
    """
    path = Path(path)
    return inspect_android_raw_bytes(path.read_bytes(), path.name)


def inspect_android_raw_bytes(data, name, *, allow_empty=False, expected_capture_id=None):
    """Shared intake for retained files and ZIP members; no archive extraction.

    Empty native sessions can be reported explicitly, while the ordinary Raw
    command retains its rejection of recordings without measurements.
    """
    decoded = gzip.decompress(data) if data.startswith(b'\x1f\x8b') else data
    text = decoded.decode('utf-8-sig')
    header, comments, records = None, [], []
    counts, constellations, ignored, native_events = Counter(), Counter(), Counter(), Counter()
    for line, content in enumerate(text.splitlines(), 1):
        if not content.strip():
            continue
        if content.startswith('#'):
            if content.startswith('# Raw,'):
                candidate = next(csv.reader([content[2:]]))
                if (len(set(candidate)) != len(candidate) or not REQUIRED <= set(candidate)
                        or header is not None):
                    raise ValueError(f'line {line}: missing/duplicate/ambiguous Raw header')
                header = candidate
            else:
                comments.append(content)
            continue
        fields = next(csv.reader([content]))
        if fields[0] != 'Raw':
            ignored[fields[0]] += 1
            continue
        if header is None or len(fields) != len(header):
            raise ValueError(f'line {line}: Raw row without header or incorrect field count')
        values = dict(zip(header, fields))
        if expected_capture_id is not None and values.get('CaptureId') != expected_capture_id:
            raise ValueError(f'line {line}: Raw capture ID differs from the session')
        if expected_capture_id is not None:
            event = _integer(values, 'EventIndex')
            if event < 1:
                raise ValueError(f'line {line}: invalid native EventIndex')
            native_events[str(event)] += 1
        counts['raw_rows'] += 1
        constellations[values['ConstellationType']] += 1
        try:
            constellation = _integer(values, 'ConstellationType')
        except ValueError as error:
            records.append({'source_line': line, 'source_values': values,
                            'status': 'INVALID_CONSTELLATION', 'reason': str(error)})
            counts['INVALID_CONSTELLATION'] += 1
            continue
        if constellation != 1:
            counts['UNSUPPORTED_CONSTELLATION'] += 1
            continue
        try:
            row = _gps_row(values, line)
        except (ValueError, DecimalException, OverflowError) as error:
            row = {'source_line': line, 'source_values': values,
                   'status': 'INVALID_GPS_MEASUREMENT', 'reason': str(error)}
        records.append(row)
        counts[row['status']] += 1
    if header is None or (not counts['raw_rows'] and not allow_empty):
        raise ValueError('no Android Raw measurements')
    if allow_empty:
        counts['raw_rows'] += 0
    report = {
        'schema': 'pnt-android-raw-v1', 'status': 'OBSERVATION_INTAKE_ONLY',
        'source': {'name': name, 'size_bytes': len(data),
                   'sha256': hashlib.sha256(data).hexdigest(),
                   'decoded_sha256': hashlib.sha256(decoded).hexdigest(),
                   'comments': comments, 'columns': header},
        'coverage': {'status_counts': dict(sorted(counts.items())),
                     'constellation_counts': dict(sorted(constellations.items())),
                     'ignored_record_counts': dict(sorted(ignored.items()))},
        'conventions': {
            'clock': 'PER_ROW_ANDROID_CLOCK_SOLUTION; NOT_INDEPENDENT_TIME',
            'missing_bias_nanos': 'ZERO_WITH_EXPLICIT_ROW_FLAG',
            'pseudorange': '(TimeNanos-FullBiasNanos-BiasNanos+TimeOffsetNanos-TxTOW) modulo nearest GPS week',
            'bias_corrections': 'INTER_SIGNAL_BIASES_RETAINED_IN_SOURCE_FIELDS_NOT_APPLIED',
            'continuity': 'NO_JOINING_OR_SMOOTHING_ACROSS_ROWS_OR_CLOCK_DISCONTINUITIES',
            'signals': 'GPS_C1C_C5I_C5Q_C5X; NO_DUAL_FREQUENCY_COMBINATION_OR_RINEX_CONVERSION',
        },
        'assessments': dict.fromkeys(
            ('RF_authenticity', 'spoofing', 'position_accuracy', 'absolute_time',
             'independent_event_timing', 'network_benefit'), 'NOT_ASSESSED'),
        'records': records,
    }
    if expected_capture_id is not None:
        report['source']['native_event_row_counts'] = dict(sorted(native_events.items()))
    return report
