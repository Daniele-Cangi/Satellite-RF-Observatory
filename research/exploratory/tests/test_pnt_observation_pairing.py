from datetime import date
import io

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
    content = io.StringIO('time,satellite,pseudorange_L1,pseudorange_L2\n'
                          '2024-09-11 08:00:00.4,G01,21000000,21000005\n'
                          '2024-09-11 08:00:00.1,G01,21000001,21000006\n'
                          '2024-09-11 08:00:01.0,G01,21000002,21000007\n'
                          '2024-09-11 08:00:00.0,G02,21000000,\n'
                          '2024-09-11 08:00:00.0,E01,21000000,21000005\n')
    values, status = pairing.local_codes(content, DAY)
    assert values[(28800, 'G01')][2:] == (21000001., 21000006.)
    assert status['source_rows'] == 5
    assert status['repeated_grid_satellite'] == 1
    assert status['off_grid'] == 1
    assert status['missing_dual_code'] == 1


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
