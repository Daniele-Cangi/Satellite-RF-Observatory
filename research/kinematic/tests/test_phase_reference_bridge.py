"""File-to-clock-to-unused-phase checks; no real RF qualification."""
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.doppler import ALPHA, BETA, F1_HZ, F2_HZ
from research.kinematic.receiver_time import C
from research.kinematic.phase_bridge_study import PHASE_TYPES, TAGS, evaluate, parse_fixture, perturb, phase_fixture_texts
from research.kinematic.phase_reference_bridge import calibrate_phase_references, phase_residual_covariance
from research.kinematic.reference_fixture import CLOCK, REFERENCES
from research.kinematic.rinex_phase_observations import RinexRejected


@pytest.fixture(scope='module')
def fixture():
    obs, nav = phase_fixture_texts()
    assert obs == (Path(__file__).parent/'fixtures/s2_phase_observations.rnx').read_text()
    return obs, nav, parse_fixture(obs)


def test_full_rinex_without_doppler_recovers_clock_and_phase_prediction(fixture):
    obs, nav, parsed = fixture
    assert not any(name.startswith('D') for name in PHASE_TYPES)
    assert parsed['covariance_code_phase_rate'].shape == (92, 92)
    result = calibrate_phase_references(parsed, nav, propagation='vacuum')
    assert result['status'] == 'REFERENCE_PHASE_MODEL_ACCEPTED'
    np.testing.assert_allclose(result['clock_coefficients'], CLOCK, atol=.001, rtol=0)
    assert max(abs(result['phase_residuals_m_s'])) < .0001
    assert result['code_dof'] == 46 and result['phase_dof'] == 44
    assert not result['real_rf_qualified']


def test_unflagged_slip_now_rejected_without_using_phase_for_clock(fixture):
    obs, nav, parsed = fixture
    nominal = calibrate_phase_references(parsed, nav, propagation='vacuum')
    bad = evaluate(obs, nav, 'unflagged_cycle_slip')['calibration']
    assert bad['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED'
    assert bad['phase_p'] < .01
    np.testing.assert_array_equal(bad['clock_coefficients'], nominal['clock_coefficients'])


def test_constant_ambiguities_cancel_and_small_common_drift_is_not_claimed_detected(fixture):
    obs, nav, _ = fixture
    constant = evaluate(obs, nav, 'constant_ambiguities')['calibration']
    common = evaluate(obs, nav, 'small_common_phase_drift')['calibration']
    assert constant['status'] == 'REFERENCE_PHASE_MODEL_ACCEPTED'
    assert common['status'] == 'REFERENCE_PHASE_MODEL_ACCEPTED'
    assert max(abs(common['phase_residuals_m_s'])) > .0009


@pytest.mark.parametrize('case', ['flagged_slip', 'missing_phase'])
def test_phase_admission_failure_prevents_navigation_access(fixture, case):
    obs, _, _ = fixture
    parsed = parse_fixture(perturb(obs, case))
    class ForbiddenNavigation:
        def splitlines(self):
            raise AssertionError('navigation consumed after phase rejection')
    result = calibrate_phase_references(parsed, ForbiddenNavigation(), propagation='vacuum')
    assert result['status'] == 'REFERENCE_PHASE_WINDOW_REJECTED'
    assert 'clock_coefficients' not in result


@pytest.mark.parametrize('flag', [1, 2, 3, 4, 5, 6])
def test_event_flags_stop_file_import(fixture, flag):
    obs, _, _ = fixture
    reset = perturb(obs, 'clock_reset')
    rows = reset.splitlines()
    for i, row in enumerate(rows):
        if row.startswith('>') and row.split()[7] == '1':
            fields = row.split()
            fields[7] = str(flag)
            rows[i] = ' '.join(fields)
    with pytest.raises(RinexRejected, match='EVENT_OR_HEADER_CHANGE'):
        parse_fixture('\n'.join(rows)+'\n')


def test_bad_codes_stop_before_phase_test(fixture):
    obs, nav, _ = fixture
    result = evaluate(obs, nav, 'code_clock_step')['calibration']
    assert result['status'] == 'REFERENCE_CODE_REJECTED'
    assert 'phase_p' not in result


def test_target_and_future_poisoning_preserves_admitted_results(fixture):
    obs, nav, parsed = fixture
    rows = obs.splitlines()
    future = False
    for i, row in enumerate(rows):
        if row.startswith('>'):
            fields = row.split()
            future = fields[4:7] == ['12', '00', '30.0000000']
        if row.startswith('G08'):
            rows[i] = 'G08nan inf 1e999'
        if future and row[:3] in REFERENCES:
            rows[i] = row[:3]+'FUTURE NUMBERS MUST NOT BE DECODED'
    changed = parse_fixture('\n'.join(rows)+'\n')
    assert changed['admitted_observations_sha256'] == parsed['admitted_observations_sha256']
    first = calibrate_phase_references(parsed, nav, propagation='vacuum')
    second = calibrate_phase_references(changed, nav.replace('POISONED TARGET FIELD', 'nan inf'), propagation='vacuum')
    assert first['admitted_navigation_sha256'] == second['admitted_navigation_sha256']
    np.testing.assert_array_equal(first['clock_coefficients'], second['clock_coefficients'])


def test_numerical_reference_boundary_rejects_target_before_values(fixture):
    _, nav, parsed = fixture
    tampered = deepcopy(parsed)
    tampered['samples'][0] = {'satellite': 'G08', 'code_m': object()}
    with pytest.raises(ValueError, match='target observation forbidden'):
        calibrate_phase_references(tampered, nav, propagation='vacuum')


def test_stale_navigation_and_changed_interval_rejected(fixture):
    _, nav, parsed = fixture
    stale = calibrate_phase_references(parsed, nav, propagation='vacuum', max_age_s=100.)
    assert stale['status'] == 'REFERENCE_MODEL_UNAVAILABLE'
    changed = deepcopy(parsed)
    changed['interval_end_s'][0] += .1
    with pytest.raises(ValueError, match='intervals differ'):
        calibrate_phase_references(changed, nav, propagation='vacuum')


@pytest.mark.parametrize('change', ['missing_code', 'missing_epoch', 'duplicate_row', 'offgrid', 'applied_clock', 'scaling'])
def test_rinex_phase_structural_failures(fixture, change):
    obs, _, _ = fixture
    rows = obs.splitlines()
    if change == 'missing_code':
        i = next(i for i, row in enumerate(rows) if row.startswith('G01'))
        start = 3+16*PHASE_TYPES.index('C1C')
        rows[i] = rows[i][:start]+' '*16+rows[i][start+16:]
    elif change == 'missing_epoch':
        i = next(i for i, row in enumerate(rows) if row.startswith('>'))+6
        del rows[i:i+6]
    elif change == 'duplicate_row':
        i = next(i for i, row in enumerate(rows) if row.startswith('G02'))
        rows[i] = 'G01'+rows[i][3:]
    elif change == 'offgrid':
        i = [i for i, row in enumerate(rows) if row.startswith('>')][1]
        rows[i] = rows[i].replace('0.0000000', '1.0000000')
    elif change == 'applied_clock':
        i = next(i for i, row in enumerate(rows) if row[60:80].strip() == 'RCV CLOCK OFFS APPL')
        rows[i] = f'{1:6}'+rows[i][6:]
    else:
        rows.insert(1, ' '*60+'SYS / SCALE FACTOR')
    content = '\n'.join(rows)+'\n'
    if change in ('missing_code', 'missing_epoch'):
        assert parse_fixture(content)['status'] == 'REFERENCE_PHASE_WINDOW_REJECTED'
    else:
        with pytest.raises(RinexRejected):
            parse_fixture(content)


def test_rectangular_residual_covariance_matches_monte_carlo_with_cross_terms():
    rng = np.random.default_rng(20260912)
    n, m = 12, 8
    factor = rng.normal(size=(n+m, n+m))
    cov = factor@factor.T+np.eye(n+m)
    jc = np.column_stack([np.ones(n), np.linspace(-1, 0, n)])
    jr = np.column_stack([np.linspace(-.1, .1, m), np.ones(m)])
    clock_cov, residual_cov = phase_residual_covariance(jc, jr, cov)
    gain = np.linalg.solve(jc.T@np.linalg.solve(cov[:n, :n], jc), jc.T@np.linalg.inv(cov[:n, :n]))
    error = rng.normal(size=(60000, n+m))@np.linalg.cholesky(cov).T
    clocks = error[:, :n]@gain.T
    residual = error[:, n:]-clocks@jr.T
    empirical = np.cov(residual, rowvar=False)
    scale = np.sqrt(np.diag(residual_cov))
    np.testing.assert_allclose((empirical-residual_cov)/np.outer(scale, scale), 0, atol=.025)
    naive = cov[n:, n:]+jr@clock_cov@jr.T
    assert np.max(abs(naive-residual_cov)) > 1


def test_raw_code_phase_cross_covariance_survives_file_transform(fixture):
    _, _, parsed = fixture
    expected = -ALPHA**2*(C/F1_HZ)*.003/30+BETA**2*(C/F2_HZ)*.001/30
    assert parsed['covariance_code_phase_rate'][0, 48] == pytest.approx(expected, abs=1e-15)
    assert parsed['covariance_code_phase_rate'][4, 48] == pytest.approx(-expected, abs=1e-15)


@pytest.mark.parametrize('kind', ['clock_rank', 'nonfinite_rate'])
def test_invalid_clock_sensitivity_cannot_produce_phase_covariance(kind):
    jc = np.column_stack([np.ones(4), np.arange(4.)])
    jr = np.ones((3, 2))
    if kind == 'clock_rank': jc[:, 1] = 1
    else: jr[0, 0] = np.nan
    with pytest.raises(ValueError):
        phase_residual_covariance(jc, jr, np.eye(7))
