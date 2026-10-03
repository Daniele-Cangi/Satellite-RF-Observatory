"""GPS NAV interoperability must preserve message identity and every field."""

import gzip

import pytest

from pnt.model import broadcast_navigation, navigation_blocks
from pnt.navigation_witness import inspect_navigation, read_issues
from pnt.tests.test_fixed_site import DAY, constellation, header, nav_text
from pnt.tests.test_navigation_witness import change


def rinex3(text):
    # Independent fixture conversion: RINEX 2 clock columns start at 22,
    # RINEX 3 at 23; continuation columns move from 3 to 4.
    lines = text.splitlines()
    result = [header(f'{3.02:9.2f}{"":11}{"N: GNSS NAV DATA":20}G: GPS', 'RINEX VERSION / TYPE'),
              header('', 'END OF HEADER')]
    for start in range(2, len(lines), 8):
        prn = int(lines[start][:2])
        result.append(f'G{prn:02d} 2012 09 14 08 00 00' + lines[start][22:])
        result.extend(' ' + line for line in lines[start + 1:start + 8])
    return '\n'.join(result) + '\n'


@pytest.mark.parametrize('compressed', [False, True])
def test_rinex3_preserves_orbit_model_and_all_comparison_fields(tmp_path, compressed):
    text = change(change(nav_text(constellation()), 6, 1, 63.), 6, 3, 511.)
    original = tmp_path / 'original.n'
    original.write_bytes(text.encode('ascii'))
    converted = tmp_path / 'converted.rnx'
    data = rinex3(text).encode('ascii')
    converted.write_bytes(gzip.compress(data) if compressed else data)
    records2, _ = read_issues(original)
    records3, _ = read_issues(converted)
    assert records2 == records3
    assert broadcast_navigation(original.read_bytes()) == broadcast_navigation(converted.read_bytes())
    report = inspect_navigation(converted, {'archive': original}, DAY.isoformat())
    assert report['coverage']['status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 8}
    assert report['sources']['local']['unhealthy_records_retained'] == 1
    assert report['assessments']['source_independence'] == 'NOT_QUALIFIED'


@pytest.mark.parametrize('kind', ['mixed', 'galileo', 'observation', 'v4', 'duplicate_header',
                                  'foreign_record', 'prn', 'epoch', 'indent', 'truncated'])
def test_unsupported_or_malformed_rinex3_is_rejected_without_partial_success(kind):
    lines = rinex3(nav_text(constellation())).splitlines()
    if kind in {'mixed', 'galileo'}:
        lines[0] = lines[0][:40] + ('M' if kind == 'mixed' else 'E') + lines[0][41:]
    elif kind == 'observation':
        lines[0] = lines[0][:20] + 'O' + lines[0][21:]
    elif kind == 'v4':
        lines[0] = '     4.02' + lines[0][9:]
    elif kind == 'duplicate_header':
        lines.insert(1, lines[0])
    elif kind == 'foreign_record':
        lines[2] = 'E' + lines[2][1:]
    elif kind == 'prn':
        lines[2] = 'G33' + lines[2][3:]
    elif kind == 'epoch':
        lines[2] = lines[2][:12] + '32' + lines[2][14:]
    elif kind == 'indent':
        lines[3] = 'X' + lines[3][1:]
    else:
        lines.pop()
    with pytest.raises(ValueError):
        list(navigation_blocks(('\n'.join(lines) + '\n').encode('ascii')))


@pytest.mark.parametrize('row,column', [(0, i) for i in range(3)] +
                         [(row, i) for row in range(1, 7) for i in range(4)] + [(7, 0)])
def test_blank_required_rinex3_fields_cannot_shift_model_inputs(row, column):
    lines = rinex3(nav_text(constellation())).splitlines()
    offset = (23 if row == 0 else 4) + column * 19
    lines[2 + row] = lines[2 + row][:offset] + ' ' * 19 + lines[2 + row][offset + 19:]
    with pytest.raises(ValueError, match='required RINEX 3 GPS navigation field'):
        broadcast_navigation(('\n'.join(lines) + '\n').encode('ascii'))
