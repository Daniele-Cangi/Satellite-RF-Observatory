"""An Internet NAV match during a logged attack must not become an allow verdict."""

from datetime import date, datetime, timedelta
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

import numpy as np
import pytest
from scipy.io import netcdf_file

from pnt.gfz_navbit import read_gfz_navbit_issues
from pnt.navigation_representation import qualify_navigation_records
from pnt.navigation_witness import group_issues, read_issues
from pnt.sfrbx import read_sfrbx_issues
from research.exploratory.pnt_observation_pairing import official_windows
from research.exploratory.pnt_rawx_recovery import GPS_EPOCH


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / 'fixtures/gfz20240911'
RESULT = ROOT / 'research/exploratory/results/pnt_gfz_recorded_attack_v1.json.gz'
PREVIOUS = ROOT / 'research/exploratory/results/pnt_navigation_jammertest_211_v1.json.gz'


def replay_recorded_attack(tmp_path):
    previous = json.loads(gzip.decompress(PREVIOUS.read_bytes()))
    original = previous['report']['sources']['local']
    captured = json.loads((FIXTURE.parent / 'sfrbx_jammertest_211.json').read_bytes())
    packet_path = tmp_path / 'retained-complete-cycles.ubx'
    packet_path.write_bytes(b''.join(bytes.fromhex(p['ubx_hex']) for p in captured['packets']))
    local, _ = read_sfrbx_issues(packet_path, captured['day_gpst'])
    complete = [c for c in original['cycles'] if c['status'] == 'DECODED_ISSUE']
    assert len(local) == len(complete) == 3
    assert original['sha256'] == captured['ubx_sha256']
    assert [i for c in complete for indices in c['packet_indices'].values() for i in indices] == [
        p['original_packet_index'] for p in captured['packets']]
    for row, cycle in zip(local, complete):
        row['sfrbx_cycle_index'] = cycle['index']
    provenance = json.loads((FIXTURE / 'provenance.json').read_bytes())
    license_info = provenance['jammertest']
    assert hashlib.sha256((FIXTURE / license_info['license_file']).read_bytes()).hexdigest() == license_info['license_sha256']
    external, sources = [], []
    for member in provenance['members']:
        rows, source = read_gfz_navbit_issues(FIXTURE / member['file'])
        assert all(source[key] == member[key] for key in ('sha256', 'bytes', 'netcdf_sha256', 'netcdf_bytes'))
        source['record_index_offset'] = len(external)
        for row in rows:
            row['index'] = len(external)
            external.append(row)
        sources.append(source)
    assert {s['satellite'] for s in sources} == {r['identity'][0] for r in local}
    noaa, noaa_source = read_issues(FIXTURE / provenance['noaa']['file'])
    assert noaa_source['sha256'] == provenance['noaa']['sha256']
    gfz = group_issues(external)
    return {'schema': 'pnt-gfz-recorded-attack-v1', 'regime': 'EXPLORATORY_EXPOSED_CASE',
            'source_provenance': provenance, 'external_sources': sources,
            'local_capture': {'sha256': original['sha256'], 'archive': previous['capture'],
                'retained_previous_report': PREVIOUS.name,
                'previous_report_sha256': hashlib.sha256(PREVIOUS.read_bytes()).hexdigest(),
                'counts': original['counts'], 'cycle_status_counts': original['cycle_status_counts'],
                'excluded_corrupt_packets': original['excluded_corrupt_packets'],
                'complete_cycles': complete,
                'replay_scope': 'All three complete cycles from nine unchanged captured UBX packets; full capture denominators retained in the unchanged previous report.'},
            'gfz_representation': qualify_navigation_records(local, {'GFZ': gfz}),
            'noaa_representation': qualify_navigation_records(local, {'NOAA': group_issues(noaa)}),
            'joint_representation': qualify_navigation_records(local, {'GFZ': gfz, 'NOAA': group_issues(noaa)}),
            'capture_association': json.loads((FIXTURE / 'capture_association.json').read_bytes()),
            'assessments': dict.fromkeys(('RF_authenticity', 'freshness', 'absolute_time',
                'source_independence', 'attack_attribution', 'P2_detection_benefit'), 'NOT_ASSESSED')}


def test_recorded_attack_replay_retains_matching_messages_missing_issue_and_source_failures(tmp_path):
    report = replay_recorded_attack(tmp_path)
    saved = json.loads(gzip.decompress(RESULT.read_bytes()))
    # Full sequence association additionally needs the externally retained capture.
    association = saved['capture_association']
    assert report == saved
    assert report['local_capture']['cycle_status_counts'] == {'DECODED_ISSUE': 3, 'INCOMPLETE_CYCLE': 204}
    assert report['gfz_representation']['status_counts'] == {'SAME_BROADCAST_FIELDS': 2, 'MISSING_ISSUE': 1}
    assert report['noaa_representation']['status_counts'] == {'REPRESENTATION_UNQUALIFIED': 2, 'MISSING_ISSUE': 1}
    assert report['joint_representation']['status_counts'] == {'SAME_BROADCAST_FIELDS': 2, 'MISSING_ISSUE': 1}
    assert [r['satellite'] for r in report['gfz_representation']['records']] == ['G17', 'G21', 'G14']
    assert report['gfz_representation']['records'][-1]['toc_gpst'].startswith('2024-10-01')
    assert sum(s['subframes'] for s in report['external_sources']) == 43200
    assert sum(s['decoded_records'] for s in report['external_sources']) == 8637
    failed = [c for s in report['external_sources'] for c in s['cycles'] if c['status'] == 'UNUSABLE_ISSUE']
    assert len(failed) == 3 and {c['reason'] for c in failed} == {'inconsistent IODE/IODC'}
    assert association['method'] == 'PRECEDING_RAWX_INFERRED_5HZ_TICK'
    assert [r['scheduled_segment'] for r in association['cycles']] == ['pre-event', 'logged-ramp', 'logged-ramp']
    window_path = ROOT / association['official_window_file']
    assert hashlib.sha256(window_path.read_bytes()).hexdigest() == association['official_window_sha256']
    window = official_windows(json.loads(window_path.read_bytes()), date(2024, 9, 11))[0]
    assert (window['start_gpst_s'], window['stop_gpst_s']) == (
        association['ramp_start_gpst_s'], association['ramp_stop_gpst_s'])
    first = datetime.fromisoformat(association['first_receiver_time'])
    first_s = (first - datetime.combine(first.date(), datetime.min.time())).total_seconds()
    for cycle in association['cycles']:
        for anchor in cycle['anchors']:
            assert anchor['preceding_rawx_packet_index'] < anchor['sfrbx_packet_index'] < anchor['next_rawx_packet_index']
            assert round(first_s + anchor['capture_tick'] / association['rate_hz'], 3) == anchor['capture_gpst_s']
            tow, week = struct.unpack_from('<dH', bytes.fromhex(anchor['preceding_rawx_payload_hex']))
            assert (GPS_EPOCH + timedelta(weeks=week, seconds=tow)).isoformat() == anchor['receiver_time']
            time = anchor['capture_gpst_s']
            segment = 'pre-event' if time < window['start_gpst_s'] else (
                'logged-ramp' if time < window['stop_gpst_s'] else 'post-event')
            assert segment == cycle['scheduled_segment']
    assert set(report['assessments'].values()) == {'NOT_ASSESSED'}


def member_arrays():
    path = FIXTURE / 'NAVBIT-GPS-L1CA-2024-255-17-14400.nc.gz'
    with netcdf_file(io.BytesIO(gzip.decompress(path.read_bytes())), mmap=False) as source:
        return {name: variable.data.copy() for name, variable in source.variables.items()}


def excerpt(tmp_path, *, columns=(0, 1, 2, 3, 4, 5, 6, 7), scalar=None, damage=None,
            gps_word_type='i', gps_word_dimension='gps_word'):
    arrays = member_arrays()
    arrays['nofsfr'][...] = len(columns)
    arrays['navbits'] = arrays['navbits'][:, columns]
    for name in ('time', 'multiplicity'):
        arrays[name] = arrays[name][list(columns)]
    if scalar:
        for name, value in scalar.items():
            arrays[name][...] = value
    if damage:
        damage(arrays)
    stream = io.BytesIO()
    with netcdf_file(stream, 'w') as output:
        output.createDimension('gps_word', 10)
        output.createDimension('time', len(columns))
        if gps_word_dimension != 'gps_word':
            output.createDimension(gps_word_dimension, 10)
        for name, array in arrays.items():
            dimensions = ('gps_word', 'time') if name == 'navbits' else (
                (gps_word_dimension,) if name == 'gps_word' else ('time',) if array.ndim else ())
            variable = output.createVariable(name, gps_word_type if name == 'gps_word' else 'i', dimensions)
            variable.data[...] = array
        output.flush()
        raw = stream.getvalue()
    path = tmp_path / 'excerpt.nc.gz'
    path.write_bytes(gzip.compress(raw, mtime=0))
    return path


@pytest.mark.parametrize('coordinate', [
    {'gps_word_type': 'f'},
    {'gps_word_dimension': 'unrelated_axis'},
])
def test_word_coordinate_requires_integer_type_and_its_own_dimension(tmp_path, coordinate):
    # Keep labels 1..10 numerically correct: values alone must not admit a
    # floating coordinate or one attached to an unrelated NetCDF dimension.
    with pytest.raises(ValueError, match='array layout'):
        read_gfz_navbit_issues(excerpt(tmp_path, **coordinate))


@pytest.mark.parametrize('scalar', [{'version': 2}, {'day_of_year': 367}, {'gps_week': 2332}, {'prn': 0}])
def test_incompatible_source_metadata_is_rejected(tmp_path, scalar):
    with pytest.raises(ValueError, match='date/week/PRN/version'):
        read_gfz_navbit_issues(excerpt(tmp_path, scalar=scalar))


@pytest.mark.parametrize('columns,complete_indices', [
    ((0, 1, 2, 10, 11, 12), (0, 2)),
    ((5, 6, 7, 15, 16, 17), (1, 3)),
    ((3, 4), ()),  # Only SF4/SF5: every daily CEI is wholly absent.
])
def test_wholly_absent_cycles_remain_in_the_daily_denominator(tmp_path, columns, complete_indices):
    rows, source = read_gfz_navbit_issues(excerpt(tmp_path, columns=columns))
    assert len(rows) == len(complete_indices)
    assert len(source['cycles']) == 2880
    day_start = 3 * 86400  # Wednesday, 2024-09-11 GPST.
    assert [c['frame_start_sow'] for c in source['cycles']] == list(range(day_start, day_start + 86400, 30))
    assert [r['gfz_cycle_index'] for r in rows] == list(complete_indices)
    assert source['cycle_status_counts']['INCOMPLETE_CYCLE'] == 2880 - len(rows)
    for index, cycle in enumerate(source['cycles']):
        assert cycle['index'] == index
        if index in complete_indices:
            assert cycle['status'] == 'DECODED_ISSUE'
        else:
            assert cycle['status'] == 'INCOMPLETE_CYCLE'
            assert cycle['missing_subframes'] == [1, 2, 3]
            assert cycle['source_row_indices'] == cycle['invalid_rows'] == []
            assert 'record_index' not in cycle


def test_missing_subframe_cannot_borrow_the_next_cycles_piece(tmp_path):
    rows, source = read_gfz_navbit_issues(excerpt(tmp_path, columns=(0, 2, 3, 4, 5, 6, 7)))
    assert len(rows) == 1
    assert source['cycle_status_counts'] == {'INCOMPLETE_CYCLE': 2879, 'DECODED_ISSUE': 1}
    assert source['cycles'][0]['missing_subframes'] == [2]


def test_parity_damage_invalidates_whole_cei_cycle_and_stays_visible(tmp_path):
    def damage(arrays):
        arrays['navbits'][2, 0] ^= 1 << 12
    rows, source = read_gfz_navbit_issues(excerpt(tmp_path, damage=damage))
    assert len(rows) == 1
    assert source['cycle_status_counts'] == {'INVALID_CYCLE': 1, 'DECODED_ISSUE': 1, 'INCOMPLETE_CYCLE': 2878}
    assert source['failed_subframes'][0]['source_row_index'] == 0
    assert 'parity failure' in source['failed_subframes'][0]['reason']


def test_duplicate_provider_times_are_not_silently_collapsed(tmp_path):
    def damage(arrays):
        arrays['time'][1] = arrays['time'][0]
    with pytest.raises(ValueError, match='ordered subframe times'):
        read_gfz_navbit_issues(excerpt(tmp_path, damage=damage))


def test_zero_multiplicity_is_retained_as_invalid_without_accepting_the_cycle(tmp_path):
    def damage(arrays):
        arrays['multiplicity'][0] = 0
    rows, source = read_gfz_navbit_issues(excerpt(tmp_path, damage=damage))
    assert len(rows) == 1
    assert source['cycle_status_counts']['INVALID_CYCLE'] == 1
    assert source['failed_subframes'][0]['reason'] == 'nonpositive provider multiplicity'


def encode_test_words(data):
    """Produce parity for a software fixture mutation, not an RF transmission.

    Parity correctness is independently covered by the real-word regressions.
    Word 2/10's non-information data bits solve their required zero parity tails.
    """
    from pnt.lnav import _MASKS
    words, previous = [], 0
    for index in range(10):
        value = int.from_bytes(data[index * 3:index * 3 + 3], 'big')
        for tail in range(4) if index in (1, 9) else (None,):
            candidate = value if tail is None else (value & ~3) | tail
            parity = 0
            for bit, mask in _MASKS:
                parity = parity << 1 | (((candidate & mask).bit_count() & 1) ^ (previous >> bit & 1))
            if tail is None or parity & 3 == 0:
                word = ((candidate ^ (0xffffff if previous & 1 else 0)) << 6) | parity
                words.append(word)
                previous = parity & 3
                break
        else:
            raise AssertionError('no valid non-information-bit tail')
    return words


@pytest.mark.parametrize('offset,width,value,field,status', [
    (60, 4, 15, 'sv_accuracy_m', 'UNAVAILABLE_ACCURACY'),
    (160, 8, 128, 'tgd_s', 'UNAVAILABLE_GROUP_DELAY'),
])
def test_unavailable_metadata_remains_a_diagnostic_not_a_qualified_issue(tmp_path, offset, width, value, field, status):
    from pnt.lnav import decode_lnav_words
    from pnt.navigation_representation import qualify_fields
    def damage(arrays):
        data = decode_lnav_words(arrays['navbits'][:, 0])
        numeric = int.from_bytes(data, 'big')
        shift = 240 - offset - width
        changed = ((numeric & ~(((1 << width) - 1) << shift)) | value << shift).to_bytes(30, 'big')
        arrays['navbits'][:, 0] = encode_test_words(changed)
    rows, source = read_gfz_navbit_issues(excerpt(tmp_path, columns=(0, 1, 2), damage=damage))
    assert len(rows) == 1
    assert source['cycle_status_counts'] == {'DECODED_UNAVAILABLE_METADATA': 1, 'INCOMPLETE_CYCLE': 2879}
    assert source['cycles'][0]['unavailable_fields'] == [field]
    assert qualify_fields(rows[0]['intervals'])[field]['status'] == status
