"""Same-phone Android GNSS clock claims and suspend-aware NTS acquisition.

A GNSS Logger file has no authenticated boot identity. Association is an
explicit trusted-collector assertion, never inferred from UTC agreement.
"""
from decimal import ROUND_CEILING
from pathlib import Path
import time
import uuid

from .android_raw import _decimal, _integer as _raw_integer
from .gnss_time import _text, compare_receiver_capture
from .nts import _capture_counter
from .time_witness import _integer, _new_report, _sample_schedule, _sampling_interval_ns

GPS_UNIX_EPOCH_NS = 315964800 * 10**9


def collect_android_time(servers, *, collector_source, server_error_ns, rate_error_ppm,
                         budget_source, rounds=10, interval_s=3.0, timeout_s=5.0, ntp_era=0):
    """Run on the GNSS Logger phone, during the same boot and recording."""
    report = _new_report(servers, server_error_ns=server_error_ns, rate_error_ppm=rate_error_ppm,
                         budget_source=budget_source, timeout_s=timeout_s, ntp_era=ntp_era)
    _text(collector_source, 'collector_source')
    _sampling_interval_ns(rounds, interval_s)
    clock_id = getattr(time, 'CLOCK_BOOTTIME', None)
    if clock_id is None:
        raise ValueError('CLOCK_BOOTTIME is required on the recording phone; no PC clock substitution')
    _capture_counter(clock_id)  # Fail before network if the platform cannot read this clock.
    capture_id = str(uuid.uuid4())
    report.update(capture_id=capture_id, regime='EXPLORATORY_ANDROID_TIME_ACQUISITION')
    report['capture_context'] = dict(counter_clock='CLOCK_BOOTTIME', collector_source=collector_source,
                                      capture_id=capture_id, gnss_acquired_by_this_command=False)
    try:
        report['capture_context']['boot_id'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError:
        report['capture_context']['boot_id'] = None
    report['acquisition'] = _sample_schedule(report, servers, rounds=rounds, interval_s=interval_s,
                                             capture_id=capture_id, clock_id=clock_id)
    if not any(a['status'] == 'AUTHENTICATED_EXCHANGE' for a in report['attempts']):
        report['status'] = 'INSUFFICIENT_EVIDENCE'
    return report


def android_clock_claim(record, *, utc_error_ns, utc_error_source):
    """Use clock epoch, not per-satellite TimeOffsetNanos or file receipt."""
    if record.get('intake_status') != 'NORMALIZED':
        raise ValueError('Android GPS Raw row is not qualified by the existing intake')
    if record.get('counter_clock') != 'CLOCK_BOOTTIME':
        raise ValueError('Android GNSS elapsed time requires CLOCK_BOOTTIME association')
    values = record.get('source_values')
    fields = ('TimeNanos', 'FullBiasNanos', 'BiasNanos', 'ChipsetElapsedRealtimeNanos',
              'HardwareClockDiscontinuityCount')
    if not isinstance(values, dict) or any(not isinstance(values.get(f), str) for f in fields):
        raise ValueError('original Android clock fields must be strings')
    epoch = _raw_integer(values, 'ChipsetElapsedRealtimeNanos')
    alignment = _integer(record.get('epoch_alignment_error_ns'), 'epoch_alignment_error_ns', 0)
    _text(record.get('epoch_alignment_source'), 'epoch_alignment_source')
    capture_id = _text(record.get('capture_id'), 'capture_id')
    offset = _integer(record.get('gps_utc_offset_seconds'), 'gps_utc_offset_seconds', 0)
    if offset > 127:
        raise ValueError('gps_utc_offset_seconds exceeds the supported range')
    _text(record.get('time_scale_source'), 'time_scale_source')
    count = _raw_integer(values, 'HardwareClockDiscontinuityCount')
    if count < 0:
        raise ValueError('negative hardware clock discontinuity count')
    start = _integer(epoch - alignment, 'GNSS epoch start', 0)
    end = epoch + alignment
    acquired_start = _integer(record.get('acquisition_start_monotonic_ns'), 'acquisition start', 0)
    acquired_end = _integer(record.get('acquisition_end_monotonic_ns'), 'acquisition end', acquired_start)
    if start < acquired_start or end > acquired_end:
        raise ValueError('Android epoch is outside the retained phone acquisition window')
    hardware_time = _raw_integer(values, 'TimeNanos')
    full_bias = _raw_integer(values, 'FullBiasNanos')
    bias = _decimal(values, 'BiasNanos')  # Missing fine bias is not silently zero.
    if bias.copy_abs() > 10**9:
        raise ValueError('Android fine bias is outside the supported range')
    # floor(integer - bias) = integer - ceil(bias), without epoch-scale
    # floating-point arithmetic or loss of a sub-nanosecond bias.
    ceiling = bias.to_integral_value(rounding=ROUND_CEILING)
    gpst_floor = hardware_time - full_bias - int(ceiling)
    if not 0 <= gpst_floor < 4 * 10**18:
        raise ValueError('Android GPS clock is outside the supported range')
    utc = gpst_floor + GPS_UNIX_EPOCH_NS - offset * 10**9
    rounding_error = int(bias != ceiling)
    claim = dict(capture_id=capture_id, counter_clock='CLOCK_BOOTTIME', unix_ns=utc,
                 error_ns=utc_error_ns + rounding_error, start_monotonic_ns=start, end_monotonic_ns=end,
                 source='ANDROID_RECEIVER_REPORTED_CLOCK_UTC', utc_error_source=utc_error_source)
    decoded = dict(receiver_gpst_floor_ns=gpst_floor, chipset_elapsed_realtime_ns=epoch,
                   hardware_clock_discontinuity_count=count, integer_conversion_error_ns=rounding_error,
                   gps_utc_offset_seconds=offset, time_scale_source=record['time_scale_source'],
                   receiver_reported_leap_second=values.get('LeapSecond'),
                   receiver_reported_bias_uncertainty_ns=values.get('BiasUncertaintyNanos'))
    return claim, decoded


def compare_android_time(witness, raw, *, association_source, gps_utc_offset_seconds, time_scale_source,
                         utc_error_ns, utc_error_source, epoch_alignment_error_ns=None,
                         epoch_alignment_source=None, bracket_span_ns=None):
    """Adapt existing Android GPS intake to the existing UTC comparison/replay."""
    _text(association_source, 'association_source')
    _integer(gps_utc_offset_seconds, 'gps_utc_offset_seconds', 0)
    if gps_utc_offset_seconds > 127:
        raise ValueError('gps_utc_offset_seconds exceeds the supported range')
    _text(time_scale_source, 'time_scale_source')
    if epoch_alignment_error_ns is not None or epoch_alignment_source is not None:
        _integer(epoch_alignment_error_ns, 'epoch_alignment_error_ns', 0)
        _text(epoch_alignment_source, 'epoch_alignment_source')
    if (not isinstance(witness, dict) or not isinstance(witness.get('capture_context'), dict)
            or witness['capture_context'].get('counter_clock') != 'CLOCK_BOOTTIME'
            or not isinstance(witness.get('acquisition'), dict)):
        raise ValueError('same-phone CLOCK_BOOTTIME acquisition is required')
    capture_id = _text(witness.get('capture_id'), 'witness capture_id')
    if witness['capture_context'].get('capture_id') != capture_id:
        raise ValueError('witness capture context differs from its capture_id')
    acquired = witness['acquisition']
    started = _integer(acquired.get('started_monotonic_ns'), 'acquisition start', 0)
    ended = _integer(acquired.get('ended_monotonic_ns'), 'acquisition end', started)
    if (not isinstance(raw, dict) or raw.get('schema') != 'pnt-android-raw-v1'
            or not isinstance(raw.get('records'), list)):
        raise ValueError('existing pnt-android-raw-v1 intake is required')
    capture = dict(schema='pnt-gnss-utc-capture-v1', receiver_source=association_source,
                   capture_id=capture_id, counter_clock='CLOCK_BOOTTIME', records=[],
                   association='CALLER_ASSERTED_SAME_ANDROID_DEVICE_AND_BOOT',
                   reported_uncertainties_used_as_bounds=False,
                   android_intake=dict(source=raw.get('source'), coverage=raw.get('coverage')))
    for row in raw['records']:
        if not isinstance(row, dict):
            raise ValueError('Android intake records must be objects')
        capture['records'].append(dict(
            source_format='ANDROID_RAW_CLOCK', capture_id=capture_id, counter_clock='CLOCK_BOOTTIME',
            source_line=row.get('source_line'), source_values=row.get('source_values'), intake_status=row.get('status'),
            gps_utc_offset_seconds=gps_utc_offset_seconds, time_scale_source=time_scale_source,
            epoch_alignment_error_ns=epoch_alignment_error_ns, epoch_alignment_source=epoch_alignment_source,
            acquisition_start_monotonic_ns=started, acquisition_end_monotonic_ns=ended))
    return compare_receiver_capture(witness, capture, utc_error_ns=utc_error_ns,
                                     utc_error_source=utc_error_source, bracket_span_ns=bracket_span_ns)
