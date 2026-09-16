from pathlib import Path

import pytest

from research.exploratory import reference_product_discrepancy as study


def fixture(clock=2., xyz=(12345., 23456., 34567.)):
    header = '#cP2026  9  3  0  0  0.00000000      96 ORBIT IGc20 HLM  IGS'
    header = header[:32] + f'{1:7d}' + header[39:]
    return (header + '\n%c G  cc GPS ccc\n*  2026  9  3  0  0  0.00000000\n'
            + 'PG01' + ''.join(f'{v:14.6f}' for v in (*xyz, clock)) + '\nEOF\n')


def parse(text):
    return study.parse_extract(text, ['G01'], 'G14', '2026-09-03')


def test_units_and_poisoned_target_exclusion_before_numeric_parse():
    content = fixture().replace('EOF', 'PG14 invalid target coordinates and clock\nEOF')
    clean = study.extract_references(content, ['G01'], 'G14')
    assert clean == fixture()
    assert parse(clean)[0]['G01'] == {'status': 'AVAILABLE',
                                    'xyz_m': [12345000., 23456000., 34567000.], 'clock_s': 2e-6}
    with pytest.raises(ValueError, match='unadmitted'):
        parse(content)
    with pytest.raises(ValueError, match='target'):
        study.extract_references(content, ['G14'], 'G14')


@pytest.mark.parametrize('text,status', [
    (fixture(clock=999999.999999), 'MISSING_CLOCK'),
    (fixture(xyz=(0., 0., 0.)), 'MISSING_POSITION'),
    (fixture(clock=float('nan')), 'NONFINITE'),
])
def test_unusable_records_remain_explicit(text, status):
    assert parse(text)[0]['G01'] == {'status': status}


@pytest.mark.parametrize('index', [74, 75, 78, 79])
def test_product_flags_are_not_silently_admitted(index):
    rows = fixture().splitlines()
    line = list(rows[3].ljust(80)); line[index] = 'P'; rows[3] = ''.join(line)
    assert parse('\n'.join(rows))[0]['G01']['status'] == 'FLAGGED_PRODUCT'


@pytest.mark.parametrize('transform', [
    lambda s: s.replace('GPS', 'UTC'),
    lambda s: s.replace('EOF', ''),
    lambda s: s.replace('*  2026  9  3', '*  2026  9  4'),
    lambda s: s.replace('EOF', s.splitlines()[3] + '\nEOF'),
    lambda s: s.replace('EOF', '*  2026  9  3  0  0  0.00000000\nEOF'),
])
def test_wrong_timescale_day_truncation_and_duplicates_rejected(transform):
    with pytest.raises(ValueError):
        parse(transform(fixture()))
