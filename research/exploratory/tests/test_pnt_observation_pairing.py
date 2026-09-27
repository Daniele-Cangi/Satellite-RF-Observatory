from datetime import date
import io
import json
from pathlib import Path

import pytest

from research.exploratory import pnt_observation_pairing as pairing


DAY = date(2024, 9, 11)


def rinex(*, flag=0, time_scale='GPS', extra_header=''):
    def header(value, label):
        return f'{value:<60}{label:<20}'
    first = '  2024     9    11     0     0    0.0000000     ' + time_scale
    assert first[48:51] == time_scale
    satellite = 'G01' + f'{21000000.:14.3f}  ' + f'{21000005.:14.3f}  '
    return '\n'.join([header('     3.05           Observation data    M (MIXED)', 'RINEX VERSION / TYPE'),
                      header('G    2 C1C C2W', 'SYS / # / OBS TYPES'),
                      header(first, 'TIME OF FIRST OBS'), extra_header,
                      header('', 'END OF HEADER'),
                      f'> 2024 09 11 08 00  0.0000000  {flag}  1', satellite])


def test_local_grid_selection_reports_missing_and_repeats():
    content = io.StringIO('time,satellite,pseudorange_L1,pseudorange_L2,snr_L1,snr_L2\n'
                          '2024-09-11 08:00:00.4,G01,21000000,21000005,45,43\n'
                          '2024-09-11 08:00:00.1,G01,21000001,21000006,45,43\n'
                          '2024-09-11 08:00:01.0,G01,21000002,21000007,45,43\n'
                          '2024-09-11 08:00:00.0,G02,21000000,,45,\n'
                          '2024-09-11 08:00:00.0,E01,21000000,21000005,45,43\n'
                          '2024-09-11 08:00:00.0,G03,21000000,85000000,21000001,\n')
    values, status = pairing.local_codes(content, DAY)
    assert values[(28800, 'G01')][2:] == (21000001., 21000006.)
    assert status['source_rows'] == 6
    assert status['repeated_grid_satellite'] == 1
    assert status['off_grid'] == 1
    assert status['missing_dual_code'] == 1
    assert status['ambiguous_dual_code_columns'] == 1
    assert (28800, 'G03') not in values


def test_external_parser_and_two_station_pairing():
    values, status = pairing.reference_codes(rinex(), DAY)
    assert status['selected_grid_satellites'] == 1
    assert values[(28800, 'G01')] == (21000000., 21000005.)
    local = {(28800, 'G01'): (0.1, 28800.1, 21000001., 21000006.),
             (28830, 'G01'): (0.1, 28830.1, 21000001., 21000006.)}
    paired, missing = pairing.pair(local, {'TRO1': values, 'KIRU': values})
    assert len(paired) == 1
    assert paired[0]['references']['KIRU']['c1c_m'] == 21000000.
    assert missing == {'KIRU': 1, 'TRO1': 1}
    with pytest.raises(ValueError, match='two distinct'):
        pairing.pair(local, {'TRO1': values})


def test_reference_time_and_header_changes_fail_closed():
    with pytest.raises(ValueError, match='time scale'):
        pairing.reference_codes(rinex(time_scale='UTC'), DAY)
    with pytest.raises(ValueError, match='nonstandard'):
        pairing.reference_codes(rinex(flag=4), DAY)
    correction = f'{"G  1  1.0 C1C":<60}{"SYS / SCALE FACTOR":<20}'
    with pytest.raises(ValueError, match='unqualified applied'):
        pairing.reference_codes(rinex(extra_header=correction), DAY)


def test_official_cest_windows_convert_to_gpst_and_reject_ambiguity():
    extract = json.loads((Path(__file__).parents[1] / 'inputs' /
                          'pnt_jammertest_windows.json').read_text(encoding='utf-8'))
    windows = pairing.official_windows(extract, DAY)
    assert [(w['test_id'], w['start_gpst_s'], w['stop_gpst_s']) for w in windows] == [
        ('2.1.3', 28865, 29765),
        ('2.1.2', 30028, 30928),
        ('2.1.4', 31235, 32135),
    ]
    changed = {**extract, 'source_time_zone': 'UTC'}
    with pytest.raises(ValueError, match='time scale'):
        pairing.official_windows(changed, DAY)
    changed = {**extract, 'rows': [*extract['rows']]}
    changed['rows'][1] = {**changed['rows'][1], 'start_cest': '10:10:00'}
    with pytest.raises(ValueError, match='overlapping'):
        pairing.official_windows(changed, DAY)


def test_segmented_coverage_does_not_merge_gap_into_benign_control():
    windows = [{'test_id': 'first', 'start_gpst_s': 30, 'stop_gpst_s': 60},
               {'test_id': 'second', 'start_gpst_s': 90, 'stop_gpst_s': 120}]
    local = {(t, 'G01'): None for t in (0, 30, 60, 90, 120)}
    local[(90, 'G02')] = None
    paired = [{'time_s': t, 'satellite': 'G01'} for t in (0, 60, 90, 120)]
    intervals = pairing.segmented_coverage(local, paired, windows)
    assert [(row['kind'], row['test_id'], row['local_dual_rows'], row['paired_rows'])
            for row in intervals] == [
                ('pre_event', None, 1, 1),
                ('official_window', 'first', 1, 0),
                ('between_events', None, 1, 1),
                ('official_window', 'second', 2, 1),
                ('post_event', None, 1, 1),
            ]
    assert intervals[3]['paired_satellites'] == ['G01']
    assert intervals[3]['local_epochs'] == intervals[3]['paired_epochs'] == 1
