import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from research.exploratory import reference_conventions as study

ROOT = Path(__file__).resolve().parents[3]


def test_radial_offset_sign_and_zero_transverse_envelope():
    result = study.radial_yaw_geometry([0., 0., 0.], [26000000., 0., 0.], [0., 0., 2.], .08)
    assert result['radial_pco_range_change_m'] == pytest.approx(-2., abs=1e-8)
    assert result['yaw_range_change_min_m'] == pytest.approx(0., abs=1e-8)
    assert result['yaw_range_change_max_m'] == pytest.approx(0., abs=1e-8)


def test_yaw_envelope_contains_dense_independent_rotations():
    station = np.array([3000000., 4500000., 3500000.])
    precise = np.array([26000000., 1000000., 5000000.])
    pco = np.array([.394, .02, 1.43])
    tau = .075
    result = study.radial_yaw_geometry(station, precise, pco, tau)
    p = study.rotate_z(precise, -study.OMEGA*tau)
    z = -p/np.linalg.norm(p)
    x = np.cross(z, [0., 0., 1.]); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    baseline = np.linalg.norm(p+pco[2]*z-station)
    changes = []
    for angle in np.linspace(0., 2*np.pi, 10001):
        rotated_x = np.cos(angle)*x+np.sin(angle)*y
        rotated_y = -np.sin(angle)*x+np.cos(angle)*y
        changes.append(np.linalg.norm(p+pco[2]*z+pco[0]*rotated_x+pco[1]*rotated_y-station)-baseline)
    assert min(changes) >= result['yaw_range_change_min_m']-1e-8
    assert max(changes) <= result['yaw_range_change_max_m']+1e-8
    assert min(changes) == pytest.approx(result['yaw_range_change_min_m'], abs=1e-7)
    assert max(changes) == pytest.approx(result['yaw_range_change_max_m'], abs=1e-7)


def test_relativity_matches_eccentric_kepler_and_rotating_frame():
    a, e, anomaly, mu = 26560000., .02, .8, 3.986005e14
    rate = np.sqrt(mu/a**3)/(1-e*np.cos(anomaly))
    r = a*np.array([np.cos(anomaly)-e, np.sqrt(1-e*e)*np.sin(anomaly), 0.])
    v = a*rate*np.array([-np.sin(anomaly), np.sqrt(1-e*e)*np.cos(anomaly), 0.])
    expected = -2*np.sqrt(mu*a)*e*np.sin(anomaly)/study.C
    assert study.relativity_m(r, v) == pytest.approx(expected, abs=1e-12)
    rotating_v = v-np.cross([0., 0., study.OMEGA], r)
    assert study.relativity_m(r, rotating_v) == pytest.approx(expected, abs=1e-12)


@pytest.mark.parametrize('half', [3, 4])
def test_velocity_polynomial_derivative_and_missing_stencil(half):
    epochs = {t: {'G01': {'status': 'AVAILABLE', 'xyz_m': [26000000.+3*t+.001*t*t, 1000.-2*t, 0.]}}
              for t in np.arange(-4, 5)*900.}
    assert study.node_velocity(epochs, 'G01', 0., half) == pytest.approx([3., -2., 0.], abs=1e-9)
    epochs[900.]['G01']['status'] = 'FLAGGED_PRODUCT'
    with pytest.raises(ValueError, match='stencil'):
        study.node_velocity(epochs, 'G01', 0., half)
    with pytest.raises(ValueError, match='stencil'):
        study.node_velocity(epochs, 'G01', 100000., half)


def antenna_fixture():
    folder = ROOT/'research/exploratory/inputs/reference_antennas/g14'
    text = (folder/'reference_antenna.atx').read_text(encoding='ascii')
    receipt = json.loads((folder/'receipt.json').read_bytes())
    return text, receipt['references']


def test_antex_current_svn_units_and_reference_filter():
    text, refs = antenna_fixture()
    offsets = study.antenna_offsets(text, refs, 'G14', '2026-09-03', 13500., 'IGS20_2425')
    assert offsets['G01']['svn'] == 'G080'  # not the historical G063 assignment
    assert offsets['G03']['if_pco_body_m'] == pytest.approx([.394, 0., 1.48226], abs=1e-12)
    assert 'G14' not in offsets
    with pytest.raises(ValueError, match='target'):
        study.extract_antex(text, refs+['G14'], 'G14')
    # Excluded block contains nonnumeric PCO: extraction must not parse it.
    start = text.index(' '*60+'START OF ANTENNA')
    end = text.index('END OF ANTENNA', start)+len('END OF ANTENNA')
    block = text[start:end]+'\n'
    block = '\n'.join((s[:20]+'G14'.ljust(20)+s[40:] if study.label(s) == 'TYPE / SERIAL NO'
                       else 'NOT A NUMBER'.ljust(60)+s[60:] if study.label(s) == 'NORTH / EAST / UP'
                       else s) for s in block.splitlines())+'\n'
    assert study.extract_antex(text+block, refs, 'G14') == text
    with pytest.raises(ValueError, match='unselected'):
        study.antenna_offsets(text+block, refs, 'G14', '2026-09-03', 13500., 'IGS20_2425')


def test_antex_wrong_model_and_ambiguous_assignments_rejected():
    text, refs = antenna_fixture()
    with pytest.raises(ValueError, match='differs'):
        study.antenna_offsets(text, refs, 'G14', '2026-09-03', 13500., 'IGS20_2434')
    block_start = text.index(' '*60+'START OF ANTENNA')
    with pytest.raises(ValueError, match='ambiguous'):
        study.antenna_offsets(text+text[block_start:], refs, 'G14', '2026-09-03', 13500., 'IGS20_2425')


@pytest.mark.parametrize('tag,archive,count', [
    ('g14', 'experiments/positioning_g14_doy246_network', 131),
    ('g12', 'research/exploratory/inputs/g12_doy248', 132),
])
def test_replay_all_rows_hashes_accounting_and_convention_signs(tag, archive, count):
    saved = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_conventions_v1.json').read_bytes())
    result = study.run(ROOT/archive, ROOT/f'research/exploratory/inputs/reference_products/{tag}',
                       ROOT/f'research/exploratory/inputs/reference_antennas/{tag}')
    def compare(expected, actual):
        if isinstance(actual, dict):
            assert expected.keys() == actual.keys()
            for key in actual:
                compare(expected[key], actual[key])
        elif isinstance(actual, list):
            assert len(expected) == len(actual)
            for old, new in zip(expected, actual):
                compare(old, new)
        elif isinstance(actual, float):
            assert expected == pytest.approx(actual, rel=1e-12, abs=1e-6)
        else:
            assert expected == actual
    compare(saved, result)
    for source, digest in result['sources_sha256'].items():
        assert hashlib.sha256((ROOT/source).read_bytes()).hexdigest() == digest
    assert result['alignment_status_counts']['PARTIALLY_ALIGNED'] == count
    assert sum(result['alignment_status_counts'].values()) == result['case_count']
    assert not result['applied_to_estimator'] and not result['qualified_error_budget']
    for row in result['rows']:
        if row['alignment_status'] != 'PARTIALLY_ALIGNED':
            continue
        assert row['reference'] != result['target']
        assert row['relativity_model_change_m'] == pytest.approx(
            row['precise_periodic_relativity_m']-row['broadcast_periodic_relativity_m'], abs=1e-12)
        assert row['radial_aligned_joint_m'] == pytest.approx(row['joint_range_difference_m']
            -row['radial_pco_range_change_m']+row['relativity_model_change_m'], abs=1e-12)
        assert row['yaw_joint_min_m'] <= row['yaw_joint_max_m']
        assert abs(row['relativity_stencil_9_minus_7_m']) < .001
