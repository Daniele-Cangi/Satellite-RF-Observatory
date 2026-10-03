"""GPS L1 C/A LNAV issues from receiver-decoded UBX-RXM-SFRBX version 2.

u-blox exports de-inverted data after receiver parity processing. We check UBX
transport checksums, not the receiver's radio parity decision or RF origin.
Bit offsets below refer to the 240 data bits after stripping padding/parity,
MSB first (IS-GPS-200N figures 20-1 and tables 20-I/III).
"""

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
import hashlib
from pathlib import Path
import struct

from research.exploratory.pnt_rawx_recovery import ubx_packets
from .navigation_witness import FIELDS, IDENTITY_FIELDS


GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
# Decimal precision bounds only conversion of semicircles to radians. Binary
# scale factors are exact. This is not a physical comparison tolerance.
PI = Decimal('3.141592653589793238462643383279502884197169399375105820974944')
URA_METRES = tuple(Decimal(str(x)) for x in
                   (2, 2.8, 4, 5.7, 8, 11.3, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096))
# name, data-bit offset, length, signed, power of two, semicircles
ORBIT_FIELDS = {
    2: [('iode', 48, 8, False, 0, False), ('crs_m', 56, 16, True, -5, False),
        ('delta_n_rad_s', 72, 16, True, -43, True), ('m0_rad', 88, 32, True, -31, True),
        ('cuc_rad', 120, 16, True, -29, False), ('eccentricity', 136, 32, False, -33, False),
        ('cus_rad', 168, 16, True, -29, False), ('sqrt_a_m_sqrt', 184, 32, False, -19, False),
        ('toe_sow', 216, 16, False, 4, False)],
    3: [('cic_rad', 48, 16, True, -29, False), ('omega0_rad', 64, 32, True, -31, True),
        ('cis_rad', 96, 16, True, -29, False), ('i0_rad', 112, 32, True, -31, True),
        ('crc_m', 144, 16, True, -5, False), ('argument_perigee_rad', 160, 32, True, -31, True),
        ('omega_dot_rad_s', 192, 24, True, -43, True), ('idot_rad_s', 224, 14, True, -43, True)],
}
ANGULAR_FIELDS = {name for specs in ORBIT_FIELDS.values() for name, *rest in specs if rest[-1]}


def bits(data, offset, length, signed=False):
    value = (int.from_bytes(data, 'big') >> (240 - offset - length)) & ((1 << length) - 1)
    return value - (1 << length) if signed and value & (1 << (length - 1)) else value


def continuous_week(week10, day_gpst):
    """Resolve only the 1024-week era from the declared day, never system time."""
    anchor = (datetime.combine(date.fromisoformat(day_gpst), datetime.min.time(), timezone.utc)
              - GPS_EPOCH).days // 7
    delta = (week10 - anchor + 512) % 1024 - 512
    if delta == -512 or anchor + delta < 0:
        raise ValueError('ambiguous or pre-GPS navigation week')
    return anchor + delta


def reference_week(week, sow, frame_start):
    if not 0 <= sow < 604800:
        raise ValueError('invalid LNAV reference time')
    delta = sow - frame_start
    if abs(delta) == 302400:
        raise ValueError('ambiguous LNAV reference week')
    return week + (1 if delta < -302400 else -1 if delta > 302400 else 0)


def decode_issue(satellite, frames, day_gpst, frame_start, *, retain_unavailable=False):
    """Decode one complete same-cycle set; never borrow a missing subframe.

    Diagnostic retention of URA/TGD sentinels does not make them usable. All
    structural, issue-consistency and reference-time checks still apply.
    """
    one, two, three = (bytes.fromhex(frames[sf][0]['data_hex']) for sf in (1, 2, 3))
    iodc = bits(one, 70, 2) * 256 + bits(one, 168, 8)
    if not bits(two, 48, 8) == bits(three, 216, 8) == (iodc & 255):
        raise ValueError('inconsistent IODE/IODC')
    ura = bits(one, 60, 4)
    if ura == 15 and not retain_unavailable:
        raise ValueError('URA index 15 has no finite accuracy prediction')
    tgd = bits(one, 160, 8, True)
    if tgd == -128 and not retain_unavailable:
        raise ValueError('TGD unavailable sentinel')
    week = continuous_week(bits(one, 48, 10), day_gpst)
    with localcontext() as context:
        context.prec = 80
        values = {'iodc': Decimal(iodc), 'codes_l2': Decimal(bits(one, 58, 2)),
                  'sv_accuracy_m': Decimal(8192) if ura == 15 else URA_METRES[ura],
                  'sv_health': Decimal(bits(one, 64, 6)),
                  'l2_p_flag': Decimal(bits(one, 72, 1)), 'tgd_s': Decimal(tgd) * Decimal(2)**-31,
                  'af2_s_s2': Decimal(bits(one, 192, 8, True)) * Decimal(2)**-55,
                  'af1_s_s': Decimal(bits(one, 200, 16, True)) * Decimal(2)**-43,
                  'af0_s': Decimal(bits(one, 216, 22, True)) * Decimal(2)**-31}
        for sf, specs in ORBIT_FIELDS.items():
            data = two if sf == 2 else three
            for name, offset, length, signed, exponent, angular in specs:
                value = Decimal(bits(data, offset, length, signed)) * Decimal(2)**exponent
                values[name] = value * PI if angular else value
        toc_sow = bits(one, 176, 16) * 16
        toe_week = reference_week(week, int(values['toe_sow']), frame_start)
        toc_week = reference_week(week, toc_sow, frame_start)
        values['gps_week'] = Decimal(toe_week)
        toc = GPS_EPOCH + timedelta(weeks=toc_week, seconds=toc_sow)
        values = {name: values[name] for name in FIELDS}
        intervals = {name: (value - Decimal('1e-58'), value + Decimal('1e-58'))
                     if name in ANGULAR_FIELDS else (value, value) for name, value in values.items()}
    return {'identity': (satellite, toc.isoformat(), *(values[name] for name in IDENTITY_FIELDS)),
            'values': values, 'intervals': intervals, 'toc': toc}


def read_sfrbx_issues(path, day_gpst, *, recover_corrupt=False, representation_records=None):
    """Retain all GPS L1 frames and every cycle outcome, including incomplete sets.

    Same satellite + HOW frame start + uninterrupted occurrence binds a cycle.
    Returning to an old HOW cycle after another cycle starts a new occurrence,
    preventing stale subframe reuse. Invalid GPS frames also end that
    satellite's active occurrence. Within-cycle order need not be 1/2/3.

    An optional list collects representation rows, including unavailable
    metadata, in cycle order. Returned usable records and cycle outcomes stay
    unchanged. Separate indices bind each diagnostic to its original cycle
    and, when admitted, its written-decimal comparison record.
    """
    # Validate the caller's date even for files containing no GPS frames.
    date.fromisoformat(day_gpst)
    content = Path(path).read_bytes()
    damage, counts, unsupported = Counter(), Counter(), Counter()
    frame_log, cycles, current = [], [], {}
    for packet_index, (cls, message, payload) in enumerate(
            ubx_packets(content, damage if recover_corrupt else None)):
        counts['checksum_valid_ubx_packets'] += 1
        if (cls, message) != (2, 19):
            continue
        counts['sfrbx_packets'] += 1
        if len(payload) < 8:
            raise ValueError('truncated SFRBX header')
        gnss, sv, signal, _, words_count, _, version, _ = payload[:8]
        if len(payload) != 8 + words_count * 4:
            raise ValueError('invalid SFRBX length')
        if gnss != 0 or signal != 0:
            unsupported[f'gnss={gnss},signal={signal},version={version}'] += 1
            continue
        counts['gps_l1_ca_packets'] += 1
        entry = {'packet_index': packet_index, 'satellite': f'G{sv:02d}',
                 'header_hex': bytes(payload[:8]).hex(), 'payload_hex': bytes(payload[8:]).hex()}
        frame_log.append(entry)
        satellite = entry['satellite']
        if version != 2 or words_count != 10 or not 1 <= sv <= 32:
            entry['status'] = 'UNSUPPORTED_GPS_HEADER'
            current.pop(satellite, None)
            continue
        words = struct.unpack_from('<10I', payload, 8)
        data = b''.join(((word >> 6) & 0xffffff).to_bytes(3, 'big') for word in words)
        entry['data_hex'] = data.hex()
        how, subframe = bits(data, 24, 17), bits(data, 43, 3)
        entry.update(how_next_subframe_sow=how * 6, subframe=subframe,
                     alert_flag=bits(data, 41, 1), anti_spoof_flag=bits(data, 42, 1))
        if data[0] != 0x8b or subframe not in (1, 2, 3, 4, 5) or how >= 100800:
            entry['status'] = 'INVALID_TLM_HOW'
            current.pop(satellite, None)
            continue
        start = ((how - subframe) * 6) % 604800
        if start % 30:
            entry['status'] = 'INVALID_FRAME_PHASE'
            current.pop(satellite, None)
            continue
        entry['frame_start_sow'] = start
        if subframe in (4, 5):
            entry['status'] = 'NON_CEI_SUBFRAME'
            if satellite in current and current[satellite]['frame_start_sow'] != start:
                del current[satellite]
            continue
        if satellite not in current or current[satellite]['frame_start_sow'] != start:
            current[satellite] = {'index': len(cycles), 'satellite': satellite,
                                  'frame_start_sow': start, 'frames': {}}
            cycles.append(current[satellite])
        cycle = current[satellite]
        entry.update(status='CEI_SUBFRAME', cycle_index=cycle['index'])
        cycle['frames'].setdefault(subframe, []).append(entry)
    records, cycle_log = [], []
    for cycle in cycles:
        frames = cycle['frames']
        info = {key: value for key, value in cycle.items() if key != 'frames'}
        info['packet_indices'] = {str(sf): [entry['packet_index'] for entry in entries]
                                  for sf, entries in sorted(frames.items())}
        info['missing_subframes'] = [sf for sf in (1, 2, 3) if sf not in frames]
        info['conflicting_subframes'] = [sf for sf, entries in sorted(frames.items())
                                         if len({entry['data_hex'][12:] for entry in entries}) > 1]
        if info['conflicting_subframes']:
            info['status'] = 'CONFLICTING_SUBFRAMES'
        elif info['missing_subframes']:
            info['status'] = 'INCOMPLETE_CYCLE'
        else:
            row = None
            try:
                row = decode_issue(cycle['satellite'], frames, day_gpst, cycle['frame_start_sow'])
            except ValueError as error:
                info.update(status='UNUSABLE_ISSUE', reason=str(error))
            else:
                row.update(index=len(records), sfrbx_cycle_index=cycle['index'])
                records.append(row)
                info.update(status='DECODED_ISSUE', local_record_index=row['index'])
            if representation_records is not None:
                if row is None:
                    try:
                        row = decode_issue(cycle['satellite'], frames, day_gpst,
                                           cycle['frame_start_sow'], retain_unavailable=True)
                    except ValueError:
                        pass  # Structural failures stay unusable, never diagnostic admissions.
                if row is not None:
                    diagnostic = dict(row, index=len(representation_records),
                                      sfrbx_cycle_index=cycle['index'],
                                      written_decimal_record_index=info.get('local_record_index'))
                    if info['status'] == 'UNUSABLE_ISSUE':
                        diagnostic['written_decimal_rejection'] = info['reason']
                    representation_records.append(diagnostic)
        cycle_log.append(info)
    return records, {
        'file': Path(path).name, 'sha256': hashlib.sha256(content).hexdigest(),
        'format': 'UBX-RXM-SFRBX-v2-GPS-L1CA', 'decoded_records': len(records),
        'unhealthy_records_retained': sum(row['values']['sv_health'] != 0 for row in records),
        'counts': dict(sorted(counts.items())), 'excluded_corrupt_packets': dict(sorted(damage.items())),
        'recovery_enabled': recover_corrupt, 'unsupported_sfrbx_counts': dict(sorted(unsupported.items())),
        'frame_status_counts': dict(sorted(Counter(f['status'] for f in frame_log).items())),
        'cycle_status_counts': dict(sorted(Counter(c['status'] for c in cycle_log).items())),
        'frames': frame_log, 'cycles': cycle_log,
        'week_era_anchor_day_gpst': day_gpst,
        'limits': [
            'Only receiver-decoded GPS L1 C/A LNAV SFRBX version 2 is supported; other signals are counted.',
            'UBX transport checksums are checked; RF parity is receiver-reported, not independently rechecked.',
            'Padding/parity are stripped from already de-inverted receiver output; raw payloads are retained.',
            'A complete same-HOW-cycle set with consistent IODE/IODC is required; no cross-cycle borrowing.',
            'HOW, week and satellite identity are untrusted receiver/message declarations, not capture-time truth.',
            'The supplied GPST day resolves only the 1024-week era; it does not validate freshness or absolute time.',
            'Binary values are exact; semicircle conversion uses bounded decimal pi; URA uses ICD nominal metres.',
            'All decoded issues are retained, including toc outside the declared day; no capture-time selection.',
        ],
    }
