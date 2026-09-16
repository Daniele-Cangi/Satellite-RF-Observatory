from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from positioning.calibration import reference_model, calibrate_station
from research.exploratory import precise_reference_model as model
from research.exploratory import reference_time_alignment as study

ROOT = Path(__file__).resolve().parents[3]
ARCHIVES = {'g14': 'experiments/positioning_g14_doy246_network',
            'g12': 'research/exploratory/inputs/g12_doy248'}


def synthetic_provider():
    orbits = {float(t): {'G01': {'status': 'AVAILABLE', 'xyz_m': [26000000., 0., 0.]}}
              for t in range(0, 7201, 300)}
    clocks = {'G01': {float(t): {'clock_s': 1e-4, 'reported_sigma_s': None} for t in range(3000, 4201, 30)}}
    return model.PreciseReference(orbits, clocks, {'G01': {'if_pco_body_m': [0., 0., 0.]}}, 'G14')


def test_emission_clock_sign_closure_and_independent_reception_rotation(monkeypatch):
    provider = synthetic_provider()
    code, tag, receiver_clock = 20000000., 3600., 150.
    tx, clock, _, radial, closure = provider.emitted_state('G01', code, tag)
    assert tx == pytest.approx(tag-code/model.C-1e-4, abs=1e-11)
    assert clock == pytest.approx(1e-4, abs=1e-15)
    assert abs(closure) < .001
    monkeypatch.setattr(model, 'troposphere', lambda *args: (0., 30.))
    station = np.array([6378137., 0., 0.])
    actual, elevation = provider.model('G01', code, tag, station, receiver_clock)
    angle = model.OMEGA*(tag-receiver_clock/model.C-tx)
    inertial_receiver = np.array([station[0]*np.cos(angle), station[0]*np.sin(angle), 0.])
    expected = np.linalg.norm(radial-inertial_receiver)-model.C*1e-4
    assert actual == pytest.approx(expected, abs=1e-7)
    assert elevation == 30.


def test_orbit_interpolation_and_velocity_on_independent_circular_motion():
    provider = synthetic_provider()
    radius, omega = 26560000., 1.45e-4
    for t, record in provider.orbits.items():
        record['G01']['xyz_m'] = [radius*np.cos(omega*t), radius*np.sin(omega*t), 0.]
    t = 3617.3
    position, velocity = provider.orbit('G01', t)
    exact = radius*np.array([np.cos(omega*t), np.sin(omega*t), 0.])
    derivative = radius*omega*np.array([-np.sin(omega*t), np.cos(omega*t), 0.])
    assert np.linalg.norm(position-exact) < 1e-5
    assert np.linalg.norm(velocity-derivative) < 1e-7


def test_linear_clock_does_not_bridge_gaps_or_extrapolate():
    provider = synthetic_provider()
    provider.clocks['G01'][3630.]['clock_s'] += 3e-9
    assert provider.clock('G01', 3615.) == pytest.approx(1e-4+1.5e-9, abs=1e-16)
    del provider.clocks['G01'][3630.]
    for t in (3615., 2999., 4201.):
        with pytest.raises(ValueError, match='gap or extrapolation'):
            provider.clock('G01', t)
    provider.orbits[3600.]['G01']['status'] = 'INVALID_ORBIT'
    with pytest.raises(ValueError, match='stencil'):
        provider.orbit('G01', 3615.)
    with pytest.raises(ValueError, match='stencil'):
        provider.orbit('G01', -1.)
    with pytest.raises(ValueError, match='unadmitted'):
        provider.orbit('G14', 3615.)


def clock_fixture():
    folder = ROOT/'research/exploratory/inputs/timed_reference_products/g14'
    receipt = json.loads((folder/'receipt.json').read_bytes())
    return (folder/'reference_clock.txt').read_text(encoding='ascii'), receipt


def test_clock_parser_preserves_missing_sigma_and_excludes_target_before_time_conversion():
    text, receipt = clock_fixture()
    refs, window = receipt['references'], receipt['clock_window_gpst_s']
    parsed = model.parse_clock(text, refs, 'G14', '2026-09-03', *window)
    assert parsed['G01'][13980.]['reported_sigma_s'] is None
    assert parsed['G01'][14100.]['reported_sigma_s'] is not None
    tainted = text+'AS G14  NOT NUMERIC\nAR ALGO NOT NUMERIC\n'
    assert model.extract_clock(tainted, refs, 'G14', '2026-09-03', *window) == text
    with pytest.raises(ValueError, match='unadmitted'):
        model.parse_clock(tainted, refs, 'G14', '2026-09-03', *window)
    with pytest.raises(ValueError, match='GPS'):
        model.parse_clock(text.replace('   GPS ', '   UTC ', 1), refs, 'G14', '2026-09-03', *window)
    # Two records at the same epoch could indicate a discontinuity: reject them.
    record = next(s for s in text.splitlines() if s.startswith('AS G01'))
    with pytest.raises(ValueError, match='duplicate/discontinuous'):
        model.parse_clock(text.replace(record, record+'\n'+record, 1), refs, 'G14', '2026-09-03', *window)


def test_sp3_next_midnight_allowed_but_target_state_rejected():
    folder = ROOT/'research/exploratory/inputs/timed_reference_products/g14'
    receipt = json.loads((folder/'receipt.json').read_bytes())
    text = (folder/'reference_orbit.txt').read_text(encoding='ascii')
    parsed = model.parse_orbit(text, receipt['references'], 'G14', '2026-09-03')
    assert len(parsed) == 289 and 86400. in parsed
    with pytest.raises(ValueError, match='unadmitted'):
        model.parse_orbit(text.replace('EOF', 'PG14 NOT NUMERIC\nEOF'), receipt['references'], 'G14', '2026-09-03')


def test_fixed_reference_adapter_matches_frozen_broadcast_calibration():
    admitted, context, navigation, _ = study.load_inputs(ROOT/ARCHIVES['g14'])
    station = admitted['stations']['ALGO00CAN']
    obs, xyz = station['reference_observations'], np.array(station['antenna_ecef_m'])
    baseline = calibrate_station(obs, xyz, navigation, context)
    sets = {e['time_s']: e['references'] for e in baseline['epochs']}
    def broadcast(sv, code, t, position, clock):
        record = min(navigation[sv], key=lambda r: abs(t-(r.toc_gps-context.day).total_seconds()))
        return reference_model(record, code, t, position, clock, context)
    actual = study.calibrate_fixed(obs, xyz, context, sets, broadcast)
    assert actual['status'] == baseline['status'] and actual['failures'] == baseline['failures']
    for a, b in zip(actual['epochs'], baseline['epochs']):
        assert a['references'] == b['references']
        assert a['clock_m'] == pytest.approx(b['clock_m'], abs=1e-7)
        assert a['ground_offset_m'] == pytest.approx(b['ground_offset_m'], abs=.001)
    missing = study.calibrate_fixed(obs, xyz, context, {}, broadcast)
    assert missing['status'] == 'CALIBRATION_NOT_QUALIFIED' and len(missing['failures']) == 11


def test_controls_hold_out_native_clock_samples():
    provider = synthetic_provider()
    provider.clocks['G01'][3630.]['clock_s'] += 1e-9
    rows = provider.withheld_node_controls(['G01'], 3600., 3660.)
    changed = next(r for r in rows if r['kind'] == 'CLOCK_NODE' and r['time_s'] == 3630.)
    assert changed['discrepancy_m'] == pytest.approx(-model.C*1e-9, abs=1e-10)
    assert all(r['discrepancy_m'] < 1e-8 for r in rows if r['kind'] == 'ORBIT_NODE' and r['status'] == 'COMPARED')


def test_control_failure_is_retained_without_mutating_target_inputs(monkeypatch):
    data, context, nav, hashes = study.load_inputs(ROOT/ARCHIVES['g14'])
    original = deepcopy(data)
    monkeypatch.setattr(study, 'load_inputs', lambda _: (data, context, nav, hashes))
    def empty():
        return {'status': 'CALIBRATION_QUALIFIED', 'failures': [], 'epochs': []}
    monkeypatch.setattr(study, 'calibrate_station', lambda *args: empty())
    def precise(self, sv, code, t, xyz, clock, count, step):
        if count == 7:
            raise ValueError('injected unavailable control stencil')
        return 0., 45.
    monkeypatch.setattr(model.PreciseReference, 'model', precise)
    def fixed(obs, xyz, ctx, sets, callback):
        callback('G01', 20000000., ctx.start_s, xyz, 0.)
        return empty()
    monkeypatch.setattr(study, 'calibrate_fixed', fixed)
    monkeypatch.setattr(study, 'fit_variant', lambda *args: {'status': 'ESTIMATED',
                        'xyz_m': [1., 2., 3.], 'B_m': 0., 'u0_relative_s': 0.})
    result = study.run('unused', ROOT/'research/exploratory/inputs/timed_reference_products/g14',
                      ROOT/'research/exploratory/inputs/reference_biases/g14',
                      ROOT/'research/exploratory/inputs/reference_antennas/g14')
    assert result['status_counts'] == {'ESTIMATED': 3, 'ENGINEERING_FAILURE': 1}
    assert result['cases'][2]['versus_primary']['comparison_status'] == 'NOT_COMPARABLE'
    assert data == original


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_reports_bind_inputs_sources_all_variants_and_all_observed_paths(tag):
    saved = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_time_alignment_v1.json').read_bytes())
    for path, digest in saved['sources_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    admitted, context, _, hashes = study.load_inputs(ROOT/ARCHIVES[tag])
    provider, _, products = study.load_products(context, saved['references'],
        ROOT/f'research/exploratory/inputs/timed_reference_products/{tag}',
        ROOT/f'research/exploratory/inputs/reference_biases/{tag}',
        ROOT/f'research/exploratory/inputs/reference_antennas/{tag}')
    assert saved['input_sha256'] == hashes | products
    assert saved['case_count'] == len(saved['cases']) == 4 == sum(saved['status_counts'].values())
    expected = {(name, obs['time_s'], sv) for name in admitted['fit_stations']
                for obs in admitted['stations'][name]['reference_observations'] for sv in obs['if_code_m']}
    assert expected == {(r['station'], r['time_s'], r['reference']) for r in saved['paths']}
    assert saved['path_count'] == len(expected) == sum(saved['path_status_counts'].values())
    for row in saved['cases'][1:]:
        expected_comparison = study.compare_fit(row, saved['cases'][0])
        for key, value in expected_comparison.items():
            assert row['versus_broadcast'][key] == (pytest.approx(value, rel=1e-12, abs=1e-10) if isinstance(value, (float, list)) else value)
    assert not any(saved[k] for k in ('target_orbit_accessed', 'target_clock_parsed', 'new_confirmation', 'qualified_error_budget', 'applied_to_production_estimator'))
    for row in saved['paths']:
        if row['status'] == 'EVALUATED':
            assert abs(row['emission_closure_m']) < .001
            p9, _ = provider.orbit(row['reference'], row['emission_gpst_s'], 9)
            p7, _ = provider.orbit(row['reference'], row['emission_gpst_s'], 7)
            assert row['orbit_9_minus_7_norm_m'] == pytest.approx(np.linalg.norm(p9-p7), abs=1e-6)
    controls = provider.withheld_node_controls(saved['references'], context.times[0], context.times[-1])
    assert len(controls) == len(saved['withheld_node_controls'])
    for actual, old in zip(controls, saved['withheld_node_controls']):
        assert actual.keys() == old.keys()
        for key, value in actual.items():
            assert old[key] == (pytest.approx(value, abs=1e-6) if isinstance(value, float) else value)
