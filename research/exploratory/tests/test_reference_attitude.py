from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation

from research.exploratory import reference_attitude as study
from research.exploratory import reference_attitude_model as model
from research.exploratory.precise_reference_model import parse_orbit
from research.exploratory.reference_sensitivity import load_inputs

ROOT = Path(__file__).resolve().parents[3]
INPUTS = ROOT/'research/exploratory/inputs'
ARCHIVES = {'g14': ROOT/'experiments/positioning_g14_doy246_network', 'g12': INPUTS/'g12_doy248'}


def test_inverse_direction_and_sign_invariant_slerp():
    # ECEF -> body rotates +90 deg about Z: body X must map to ECEF -Y.
    q = [np.sqrt(.5), 0., 0., np.sqrt(.5)]
    a = model.Attitude({'G01': {0.: [1., 0., 0., 0.], 30.: q, 60.: (-np.array(q)).tolist()}}, 'G14')
    assert a.body_to_ecef('G01', 30.)@np.array([1., 0., 0.]) == pytest.approx([0., -1., 0.], abs=1e-14)
    assert a.body_to_ecef('G01', 15.)@np.array([1., 0., 0.]) == pytest.approx([np.sqrt(.5), -np.sqrt(.5), 0.], abs=1e-14)
    assert a.body_to_ecef('G01', 45.) == pytest.approx(a.body_to_ecef('G01', 30.), abs=1e-14)
    for t in (-1., 61., float('nan')):
        with pytest.raises(ValueError):
            a.body_to_ecef('G01', t)
    with pytest.raises(ValueError):
        a.body_to_ecef('G14', 30.)
    del a.samples['G01'][30.]
    a.body_to_ecef.cache_clear()
    with pytest.raises(ValueError, match='gap'):
        a.body_to_ecef('G01', 15.)


def attitude_fixture():
    p = INPUTS/'reference_attitudes/g14'
    meta = json.loads((p/'receipt.json').read_bytes())
    args = (meta['references'], 'G14', meta['date_gpst'], *meta['window_gpst_s'])
    return (p/'reference_attitude.obx').read_text(), args


def test_extract_discards_target_before_quaternion_conversion():
    text, args = attitude_fixture()
    lines = text.splitlines()
    index = next(i for i, s in enumerate(lines) if s.startswith('## '))
    parts = lines[index].split(); parts[-1] = str(int(parts[-1])+1)
    lines[index] = ' '.join(parts)
    lines.insert(index+1, ' ATT G14              4 this is not numeric')
    clean = model.extract_attitude('\n'.join(lines)+'\n', *args)
    assert clean == text
    with pytest.raises(ValueError, match='unadmitted'):
        model.parse_attitude('\n'.join(lines)+'\n', *args)


@pytest.mark.parametrize('change', ['quaternion', 'direction', 'timescale', 'count', 'duplicate', 'truncated', 'flags'])
def test_malformed_attitude_is_rejected(change):
    text, args = attitude_fixture()
    lines = text.splitlines(); index = next(i for i, s in enumerate(lines) if s.startswith(' ATT '))
    if change == 'quaternion':
        lines[index] = lines[index][:23]+' 2 0 0 0'
    elif change == 'flags':
        lines[index] = lines[index][:10]+'P'+lines[index][11:]
    elif change == 'direction':
        lines = [s.replace('ECEF --> SAT. BODY FRAME', 'BODY --> ECEF') for s in lines]
    elif change == 'timescale':
        lines = [s.replace('GPS', 'UTC') if 'TIME_SYSTEM' in s else s for s in lines]
    elif change == 'count':
        lines[index-1] = ' '.join(lines[index-1].split()[:-1]+['1'])
    elif change == 'duplicate':
        lines[index+1] = lines[index]
    else:
        lines.pop()
    with pytest.raises(ValueError):
        model.parse_attitude('\n'.join(lines)+'\n', *args)


@pytest.mark.parametrize('raw', ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '{"a":1e999}'])
def test_receipts_reject_ambiguous_or_nonfinite_json(raw):
    with pytest.raises(ValueError):
        model.strict_json(raw)


def test_paired_clock_bias_and_interior_antenna_boundary():
    clock = (INPUTS/'timed_reference_products/g14/reference_clock.txt').read_text()
    antenna = (INPUTS/'reference_antennas/g14/reference_antenna.atx').read_text()
    meta = json.loads((INPUTS/'timed_reference_products/g14/receipt.json').read_bytes())
    args = (meta['references'], 'G14', '2026-09-03', *meta['clock_window_gpst_s'])
    model.validate_pair(clock, antenna, *args)
    with pytest.raises(ValueError, match='CODE.BIA'):
        model.validate_pair(clock.replace('CODE.BIA', 'OTHERBIA'), antenna, *args)
    lines = antenna.splitlines()
    i = next(i for i,s in enumerate(lines) if model.label(s) == 'VALID FROM')
    lines[i] = ' 2026 9 3 3 55 15'.ljust(60)+'VALID FROM'
    with pytest.raises(ValueError, match='boundary'):
        model.validate_pair(clock, '\n'.join(lines)+'\n', *args)


def test_sp3_clock_flags_do_not_invalidate_position_but_orbit_flags_do():
    p = INPUTS/'timed_reference_products/g14'
    meta = json.loads((p/'receipt.json').read_bytes())
    lines = (p/'reference_orbit.txt').read_text().splitlines()
    i = next(i for i,s in enumerate(lines) if s.startswith('PG01'))
    for offset, flag, expected in [(74, 'E', 'AVAILABLE'), (75, 'P', 'AVAILABLE'),
                                    (78, 'M', 'INVALID_ORBIT'), (79, 'P', 'INVALID_ORBIT')]:
        changed = lines.copy(); row = list(changed[i].ljust(80)); row[offset] = flag; changed[i] = ''.join(row)
        parsed = parse_orbit('\n'.join(changed)+'\n', meta['references'], 'G14', meta['date_gpst'])
        assert parsed[0.]['G01']['status'] == expected


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_product_rotation_points_body_z_at_nadir_and_controls_omit_nodes(tag):
    _, context, _, _ = load_inputs(ARCHIVES[tag])
    meta = json.loads((INPUTS/f'timed_reference_products/{tag}/receipt.json').read_bytes())
    refs = meta['references']
    precise, _, _ = model.guarded_products(context, refs, INPUTS/f'timed_reference_products/{tag}',
                                          INPUTS/f'reference_biases/{tag}', INPUTS/f'reference_antennas/{tag}')
    attitude, _ = study.load_attitude(INPUTS/f'reference_attitudes/{tag}', context, refs)
    for sv in refs:
        for t in attitude.samples[sv]:
            r, _ = precise.orbit(sv, t)
            rotation = attitude.body_to_ecef(sv, t)
            # Product convention cross-check, not a physical attitude bound.
            assert np.linalg.norm(rotation[:, 2]+r/np.linalg.norm(r)) < 1e-6
            assert np.linalg.det(rotation) == pytest.approx(1., abs=1e-14)
    controls = study.attitude_controls(attitude, precise, refs, context.times[0], context.times[-1])
    assert all(r['status'] == 'COMPARED' for r in controls)
    first = controls[0]; sv, t = first['reference'], float(first['time_s'])
    original = attitude.body_to_ecef(sv, t, 60).copy()
    attitude.samples[sv][t] = Rotation.from_euler('x', .1).as_quat(scalar_first=True).tolist()
    attitude.body_to_ecef.cache_clear()
    assert attitude.body_to_ecef(sv, t, 60) == pytest.approx(original, abs=1e-14)
    assert study.attitude_controls(attitude, precise, refs, context.times[0], context.times[-1])[0]['rotation_difference_rad'] > .01


def test_full_pco_range_sign_and_z_control(monkeypatch):
    class Precise:
        offsets = {'G01': {'if_pco_body_m': [1., 2., 3.]}}
        def emitted_state(self, *args):
            return 30., 0., np.array([26000000., 0., 0.]), None, 0., -.1
    attitude = model.Attitude({'G01': {30.: [np.sqrt(.5), 0., 0., np.sqrt(.5)]}}, 'G14')
    provider = model.AttitudeReference(Precise(), attitude)
    assert provider.antenna_state('G01', 1., 30.)[2] == pytest.approx([26000002., -1., 3.])
    z = model.AttitudeReference(Precise(), attitude, z_only=True)
    assert z.antenna_state('G01', 1., 30.)[2] == pytest.approx([26000000., 0., 3.])
    monkeypatch.setattr(model, 'troposphere', lambda *a: (0., 45.))
    actual, _ = provider.model('G01', 1., 30., np.array([6378000., 0., 0.]), 0.)
    theta = model.OMEGA*.1
    receiver = np.array([6378000.*np.cos(theta), 6378000.*np.sin(theta), 0.])
    assert actual == pytest.approx(np.linalg.norm(np.array([26000002., -1., 3.])-receiver), abs=1e-8)


def test_failed_variant_and_all_paths_are_retained(monkeypatch):
    admitted, context, nav, hashes = load_inputs(ARCHIVES['g14'])
    original = deepcopy(admitted)
    monkeypatch.setattr(study, 'load_inputs', lambda _: (admitted, context, nav, hashes))
    empty = {'status': 'CALIBRATION_QUALIFIED', 'epochs': [], 'failures': []}
    monkeypatch.setattr(study, 'calibrate_station', lambda *a: deepcopy(empty))
    def fixed(obs, station, context, sets, callback):
        if getattr(callback.__self__, 'step', None) == 60:
            raise ValueError('injected missing attitude')
        return deepcopy(empty)
    monkeypatch.setattr(study, 'calibrate_fixed', fixed)
    monkeypatch.setattr(study, 'fit_variant', lambda *a: {'status': 'ESTIMATED', 'xyz_m': [1.,2.,3.], 'B_m': 0., 'u0_relative_s': 0.})
    result = study.run(ARCHIVES['g14'], INPUTS/'timed_reference_products/g14', INPUTS/'reference_biases/g14',
                       INPUTS/'reference_antennas/g14', INPUTS/'reference_attitudes/g14')
    assert result['status_counts'] == {'ESTIMATED': 3, 'ENGINEERING_FAILURE': 1}
    assert result['cases'][2]['versus_full']['comparison_status'] == 'NOT_COMPARABLE'
    expected = {(name, o['time_s'], sv) for name in admitted['fit_stations']
                for o in admitted['stations'][name]['reference_observations'] for sv in o['if_code_m']}
    assert {(r['station'],r['time_s'],r['reference']) for r in result['paths']} == expected
    assert admitted == original


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_saved_full_replay_and_unchanged_radial_baseline(tag):
    path = ROOT/f'research/exploratory/results/{tag}_reference_attitude_v1.json'
    saved = json.loads(path.read_bytes())
    actual = study.run(ARCHIVES[tag], INPUTS/f'timed_reference_products/{tag}', INPUTS/f'reference_biases/{tag}',
                       INPUTS/f'reference_antennas/{tag}', INPUTS/f'reference_attitudes/{tag}')
    def compare(a, b):
        if isinstance(b, dict):
            assert a.keys() == b.keys()
            for key in b:
                compare(a[key], b[key])
        elif isinstance(b, list):
            assert len(a) == len(b)
            for x,y in zip(a,b):
                compare(x,y)
        elif isinstance(b, float):
            assert a == pytest.approx(b, abs=.001, rel=1e-12)
        else:
            assert a == b
    compare(saved, actual)
    # Geometric controls have stricter tolerances than the nonlinear fit replay.
    for old, new in zip(saved['paths'], actual['paths']):
        if new['status'] == 'EVALUATED':
            for key in ('full_minus_radial_range_m', 'body_z_minus_radial_range_m',
                        'transverse_range_m', 'pco_30_minus_60_norm_m', 'pco_ecef_m'):
                assert old[key] == pytest.approx(new[key], abs=2e-8, rel=0.)
            assert old['body_z_nadir_angle_rad'] == pytest.approx(new['body_z_nadir_angle_rad'], abs=1e-13, rel=0.)
    for old, new in zip(saved['withheld_attitude_nodes'], actual['withheld_attitude_nodes']):
        assert old['status'] == new['status'] == 'COMPARED'
        for key in ('rotation_difference_rad', 'pco_difference_m'):
            assert old[key] == pytest.approx(new[key], abs=1e-13, rel=0.)
    for path, digest in saved['sources_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    prior = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_time_alignment_v1.json').read_bytes())
    assert saved['cases'][0]['xyz_m'] == pytest.approx(prior['cases'][1]['xyz_m'], abs=.001, rel=0.)
    assert saved['path_status_counts'] == prior['path_status_counts']
    assert saved['case_count'] == len(saved['cases']) == 4
    assert saved['status_counts'] == {'ESTIMATED': 4}
    assert not any(saved[k] for k in ('target_orbit_accessed', 'target_attitude_parsed', 'new_confirmation', 'qualified_error_budget', 'applied_to_production_estimator'))
