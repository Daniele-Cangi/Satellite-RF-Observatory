from pathlib import Path
import hashlib
import json

import numpy as np
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


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('tag,archive', [
    ('g14', 'experiments/positioning_g14_doy246_network'),
    ('g12', 'research/exploratory/inputs/g12_doy248'),
])
def test_saved_real_product_comparison_replays_and_preserves_denominator(tag, archive):
    inputs = ROOT / 'research/exploratory/inputs/reference_products' / tag
    saved = json.loads((ROOT / f'research/exploratory/results/{tag}_reference_product_discrepancy_v1.json').read_bytes())
    actual = study.run(ROOT / archive, inputs / 'reference_extract.txt', inputs / 'receipt.json')
    assert actual['input_sha256'] == saved['input_sha256']
    assert actual['sources_sha256'] == saved['sources_sha256']
    assert actual['case_count'] == actual['epoch_count'] * len(actual['references'])
    assert actual['status_counts'] == saved['status_counts']
    assert len(actual['rows']) == len(saved['rows']) == actual['case_count']
    for row, old in zip(actual['rows'], saved['rows']):
        assert row.keys() == old.keys()
        for key, value in row.items():
            # Subtracting ~26,000 km propagated coordinates exposes libm
            # roundoff. One micrometre remains below SP3 millimetre resolution.
            tolerance = 1e-6 if key in ('delta_xyz_m', 'orbit_discrepancy_norm_m') else 1e-8
            assert old[key] == (pytest.approx(value, rel=1e-10, abs=tolerance)
                                if isinstance(value, (float, list)) else value)
    covariance = np.array(actual['centered_clock_sample_covariance_m2'])
    np.testing.assert_allclose(covariance, saved['centered_clock_sample_covariance_m2'], rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(covariance.sum(axis=0), 0., atol=1e-12)
    assert np.linalg.eigvalsh(covariance).min() >= -1e-12
    assert not actual['target_state_parsed'] and not actual['qualified_error_budget']


def test_missing_sample_stays_in_denominator_and_cannot_change_centering_set(tmp_path):
    inputs = ROOT / 'research/exploratory/inputs/reference_products/g14'
    text = (inputs / 'reference_extract.txt').read_text()
    first = next(line for line in text.splitlines() if line.startswith('P'))
    content = text.replace(first + '\n', '', 1).encode('ascii')
    path = tmp_path / 'extract.txt'; path.write_bytes(content)
    receipt = json.loads((inputs / 'receipt.json').read_bytes())
    receipt_path = tmp_path / 'receipt.json'; receipt_path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='receipt'):
        study.run(ROOT / 'experiments/positioning_g14_doy246_network', path, receipt_path)
    receipt['extract_sha256'] = hashlib.sha256(content).hexdigest()
    receipt_path.write_text(json.dumps(receipt))
    result = study.run(ROOT / 'experiments/positioning_g14_doy246_network', path, receipt_path)
    assert result['case_count'] == 2016 and result['complete_epoch_count'] == 95
    assert result['status_counts']['MISSING_SP3_RECORD'] == 1
    assert all('ensemble_centered_clock_discrepancy_m' not in row for row in result['rows']
               if row['time_gpst_s'] == 0.)
