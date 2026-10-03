"""Exposed-case intake of one Internet provider's transmitted LNAV words."""

from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.io import netcdf_file

from pnt.lnav import decode_lnav_words
from pnt.navigation_representation import qualify_navigation_records
from pnt.navigation_witness import group_issues, read_issues
from pnt.sfrbx import GPS_EPOCH, bits, decode_issue
from pnt.tests.test_public_rf_navigation import FIXTURE as LOCAL, replay_monitor_messages


FIXTURE = Path(__file__).parent / 'fixtures' / 'gfz20130404'
RESULT = Path(__file__).resolve().parents[2] / 'research/exploratory/results/pnt_gfz_navigation_v1.json.gz'


def replay_gfz_intake():
    """Use the existing local replay, issue decoder and representation comparator.

    Select all three CEI subframes for every exposed local HOW cycle, including
    locally incomplete cycles. Source selection never depends on field agreement.
    This is fixture intake, not a general NetCDF adapter or production executor.
    """
    provenance = json.loads((FIXTURE / 'provenance.json').read_bytes())
    local_cycles, local = replay_monitor_messages()
    day = provenance['day_gpst']
    day_start = int((datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
                     - GPS_EPOCH).total_seconds()) % 604800
    starts = {cycle['satellite']: set() for cycle in local_cycles}
    for cycle in local_cycles:
        starts[cycle['satellite']].add(cycle['frame_start_sow'])
    assert {member['satellite'] for member in provenance['members']} == set(starts)
    inputs, frames, external = [], [], []
    for member in provenance['members']:
        packed = (FIXTURE / member['file']).read_bytes()
        assert len(packed) == member['bytes']
        assert hashlib.sha256(packed).hexdigest() == member['sha256']
        raw = gzip.decompress(packed)
        assert len(raw) == member['netcdf_bytes']
        assert hashlib.sha256(raw).hexdigest() == member['netcdf_sha256']
        satellite = member['satellite']
        with netcdf_file(io.BytesIO(raw), mmap=False) as source:
            variables = source.variables
            assert int(variables['version'].data) == 1
            assert int(variables['year'].data) == 2013
            assert int(variables['day_of_year'].data) == 94
            assert int(variables['gps_week'].data) == 1734
            assert f"G{int(variables['prn'].data):02d}" == satellite
            words = variables['navbits'].data.T
            times = variables['time'].data
            multiplicity = variables['multiplicity'].data
            assert words.shape == (14400, 10) and words.dtype.kind == 'i'
            assert times.shape == multiplicity.shape == (14400,)
            assert np.array_equal(times, np.arange(14400) * 6)
            assert np.all((words >= 0) & (words < 1 << 30))
            inputs.append(dict(member, subframes_in_file=len(times),
                multiplicity_counts={str(k): v for k, v in sorted(Counter(int(m) for m in multiplicity).items())},
                provider_history=source.history.decode('ascii')))
            wanted = {start + (sf - 1) * 6: (start, sf)
                      for start in starts[satellite] for sf in (1, 2, 3)}
            cycles = {}
            for index in np.flatnonzero(np.isin(times + day_start, list(wanted))):
                time = int(times[index])
                start, expected_sf = wanted[day_start + time]
                assert int(multiplicity[index]) > 0
                transmitted = [int(word) for word in words[index]]
                data = decode_lnav_words(transmitted)
                how, sf = bits(data, 24, 17), bits(data, 43, 3)
                assert data[0] == 0x8b and sf == expected_sf and how < 100800
                assert ((how - sf) * 6) % 604800 == start
                assert (how * 6 - 6) % 604800 == day_start + time
                entry = {'satellite': satellite, 'source_file': member['file'],
                         'source_row_index': int(index), 'provider_time_sod': time,
                         'provider_multiplicity': int(multiplicity[index]),
                         'frame_start_sow': start, 'subframe': sf,
                         'words_hex': [f'{word:08x}' for word in transmitted],
                         'data_hex': data.hex(), 'parity_status': 'PASS'}
                frames.append(entry)
                cycles.setdefault(start, {}).setdefault(sf, []).append(entry)
            assert set(cycles) == starts[satellite]
            for start, subframes in sorted(cycles.items()):
                assert set(subframes) == {1, 2, 3}
                assert all(len(entries) == 1 for entries in subframes.values())
                row = decode_issue(satellite, subframes, day, start)
                row['index'] = len(external)
                external.append(row)
    gfz = group_issues(external)
    noaa, _ = read_issues(LOCAL / 'brdc0940.13n.gz')
    return {'schema': 'pnt-gfz-navbit-intake-v1', 'regime': 'EXPLORATORY_EXPOSED_CASE',
            'source_provenance': provenance, 'retained_members': inputs,
            'selection': 'All SF1/2/3 at every HOW frame start in the exposed local replay; all local satellites retained.',
            'local_input': {'file': 'cttc20130404/navdata.json',
                            'sha256': hashlib.sha256((LOCAL / 'navdata.json').read_bytes()).hexdigest()},
            'local_cycle_counts': dict(sorted(Counter(c['status'] for c in local_cycles).items())),
            'local_cycles': local_cycles, 'external_frames': frames,
            'external_decoded_cycles': len(external),
            'gfz_representation': qualify_navigation_records(local, {'GFZ': gfz}),
            'gfz_and_noaa_representation': qualify_navigation_records(local, {'GFZ': gfz, 'NOAA': group_issues(noaa)}),
            'assessments': dict.fromkeys(('RF_authenticity', 'freshness', 'absolute_time',
                                         'source_independence', 'attack_attribution',
                                         'P2_detection_benefit'), 'NOT_ASSESSED')}


def test_gfz_intake_reproduces_all_cycles_and_keeps_noaa_disagreement_visible():
    report = replay_gfz_intake()
    assert report == json.loads(gzip.decompress(RESULT.read_bytes()))
    assert report['local_cycle_counts'] == {'DECODED_ISSUE': 10, 'INCOMPLETE_CYCLE': 5}
    assert len(report['external_frames']) == 45 and report['external_decoded_cycles'] == 15
    assert report['gfz_representation']['status_counts'] == {'SAME_BROADCAST_FIELDS': 10}
    assert report['gfz_and_noaa_representation']['status_counts'] == {'EXTERNAL_RECORD_CONFLICT': 10}
    records = report['gfz_and_noaa_representation']['records']
    assert all(r['witnesses']['GFZ']['status'] == 'SAME_BROADCAST_FIELDS' for r in records)
    assert all(r['witnesses']['NOAA']['status'] == 'REPRESENTATION_UNQUALIFIED' for r in records)
    assert all(len(r['fields']) == 27 and not r['unqualified_fields']
               for r in report['gfz_representation']['records'])
    assert set(report['assessments'].values()) == {'NOT_ASSESSED'}


def transmitted_example():
    saved = json.loads(gzip.decompress(RESULT.read_bytes()))
    return [int(word, 16) for word in saved['external_frames'][0]['words_hex']]


def test_every_single_transmitted_bit_change_is_rejected_without_repair():
    words = transmitted_example()
    assert len(decode_lnav_words(words)) == 30
    for bit in range(300):
        changed = words.copy()
        changed[bit // 30] ^= 1 << (bit % 30)
        with pytest.raises(ValueError, match='parity failure|D29/D30 zero'):
            decode_lnav_words(changed)


@pytest.mark.parametrize('replacement', [-1, 1 << 30, 1.5, True, '1'])
def test_invalid_word_representation_cannot_be_truncated_or_coerced(replacement):
    words = transmitted_example()
    words[3] = replacement
    with pytest.raises(ValueError, match='unsigned 30-bit integer'):
        decode_lnav_words(words)


def test_truncation_and_double_deinversion_fail_closed():
    words = transmitted_example()
    with pytest.raises(ValueError, match='ten unsigned'):
        decode_lnav_words(words[:-1])
    data = decode_lnav_words(words)
    assert data != b''.join((word >> 6).to_bytes(3, 'big') for word in words)
    double = [int.from_bytes(data[i * 3:i * 3 + 3], 'big') << 6 | (word & 63)
              for i, word in enumerate(words)]
    with pytest.raises(ValueError, match='parity failure'):
        decode_lnav_words(double)
