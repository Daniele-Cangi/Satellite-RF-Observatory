"""Physical identifiability, excluded spatial transfer and calibration effects."""
from copy import deepcopy

import numpy as np
import pytest

from research.kinematic import shared_error_structure as model
from research.kinematic import gnss_combinations, network_clocks, orbital_dynamics
from research.exploratory import reference_network_clocks as study
from research.kinematic.tests.test_temporal_shared_rf import prepared


def rows(sign=1.):
    rng = np.random.default_rng(59031)
    output = []
    for k in range(180):
        common = rng.normal(size=(6, 2)) @ np.array([[1., -.15], [0., .3]])
        for i, station in enumerate('ABCDEF'):
            for j, reference in enumerate('QRSTUVWX'):
                z = common[i]*(1. if j % 2 == 0 else sign)+rng.normal(size=2)*[.8, .24]
                output.append({'station': station, 'reference': reference, 'time_s': k*30.,
                    'segment': station+reference, 'code_m': 50*i+z[0], 'phase_m': 20*i,
                    'mw_m': 100*i+z[1]})
    return output


def test_raw_covariance_allocation_has_constructive_psd_nonuniqueness():
    c = np.array([[.8, -.03], [-.03, .02]])
    result = model.raw_identifiability(c)
    h = result['contrast_transform']
    assert result['raw_mean_nullity'] == 2
    assert result['raw_covariance_nullity'] == 7
    assert result['separate_code_phase_covariance_nullity'] == 3
    assert result['augmented_mean_rank'] == 4
    for law in result['indistinguishable_laws'].values():
        raw = law['raw_increment_covariance_m2']
        assert min(np.linalg.eigvalsh(raw)) > -1e-12
        np.testing.assert_allclose(h @ raw @ h.T, c, atol=1e-12, rtol=0)
        for name in ('nondispersive_null_vector', 'ionosphere_null_vector'):
            null = result[name]
            np.testing.assert_allclose(h @ (raw+1e3*np.outer(null, null)) @ h.T, c, atol=1e-9, rtol=0)
    code, phase = [result['indistinguishable_laws'][k]['retained_if_mw_increment_covariance_m2'] for k in ('code_only', 'phase_only')]
    assert code[1, 1] == 0 and phase[0, 0] == 0
    assert phase[1, 1] > .01 and code[0, 0] > .01
    with pytest.raises(ValueError, match='PSD'):
        model.raw_identifiability(np.diag([1., -.01]))


@pytest.mark.parametrize('sign', [1., -1.])
def test_positive_and_anticorrelated_processes_have_different_excluded_transfer(sign):
    result = model.prepare(rows(sign), 'TARGET')
    own = model.evaluate(result['comparisons']['alternating/30s'])
    assert own['signed_transfer_improves_both_directions']
    if sign > 0:
        assert own['status'] == 'POSITIVE_DIFFERENTIAL_TRANSFER_SUPPORTED'
        assert own['positive_cross_moment_survives_training_block_deletions']
    else:
        assert own['status'] == 'POSITIVE_SHARED_STRUCTURE_UNQUALIFIED'
        assert max(own['training_moments']['cross_eigenvalues_m2']) < 0
        for direction in own['predictors'].values():
            np.testing.assert_array_equal(direction['positive_common_gain'], np.zeros((2, 2)))
    assert not own['physical_covariance_qualified']
    assert not own['raw_allocation_identifiable']
    for part in ('training_moments', 'validation_moments'):
        m = own[part]
        np.testing.assert_allclose(m['consensus_covariance_m2']-m['disagreement_covariance_m2'],
                                  m['cross_covariance_m2'], atol=1e-14, rtol=0)


def test_excluded_group_cannot_change_its_prediction_or_training_fit():
    original = rows()
    first = model.prepare(original, 'TARGET')
    poisoned = deepcopy(original)
    group_b = set(first['comparisons']['alternating/30s']['training']['reference_groups'][1])
    for row in poisoned:
        if row['time_s'] > first['training_stop_s'] and row['reference'] in group_b:
            station = 'ABCDEF'.index(row['station'])-2.5
            row['code_m'] += station*row['time_s']**2
            row['mw_m'] -= station*row['time_s']**2/3
    second = model.prepare(poisoned, 'TARGET')
    for lag in (30, 300):
        a, b = [r['comparisons'][f'alternating/{lag}s'] for r in (first, second)]
        np.testing.assert_array_equal(a['training_moments']['cross_covariance_m2'], b['training_moments']['cross_covariance_m2'])
        for direction in ('A_to_B', 'B_to_A'):
            for key in ('positive_common_gain', 'signed_gain'):
                np.testing.assert_array_equal(a['predictors'][direction][key], b['predictors'][direction][key])
        for label in ('independent', 'positive_common', 'signed_cross_group'):
            np.testing.assert_array_equal(a['predictors']['A_to_B']['predictions_m'][label],
                                          b['predictors']['A_to_B']['predictions_m'][label])
        assert model.evaluate(b)['scores']['A_to_B']['positive_common']['training_scaled_loss'] > 1e6
    class Forbidden:
        def __float__(self):
            raise AssertionError('candidate decoded')
    with pytest.raises(ValueError, match='candidate'):
        model.prepare([{'reference': 'TARGET', 'time_s': Forbidden()}], 'TARGET')


def test_disconnected_split_does_not_acquire_an_artificial_anchor():
    own = rows()
    own = [r for r in own if (r['station'] in 'ABC') == (r['reference'] in 'QRST')]
    result = model.prepare(own, 'TARGET')['comparisons']['alternating/30s']
    assert result['status'] == 'INSUFFICIENT_SPLIT_SUPPORT'
    assert result['training']['status_counts']['UNOBSERVED_SPLIT_CONTRAST'] > 0
    assert not result['physical_covariance_qualified']


def test_blind_nondispersive_errors_cancel_only_when_the_reference_chain_shares_them():
    arcs, state, raw, network, _, _ = prepared()
    reference_rows = [deepcopy(r) for b in network['blocks'] for r in b['rows']]
    common = deepcopy(arcs)
    def disturbance(station, time):
        return 4*('ABCDEF'.index(station)-2.5)*np.sin((time-36000)/300)
    for r in reference_rows:
        shift = disturbance(r['station'], r['time_s'])
        r['code_m'] += shift
        r['phase_m'] += shift
    for arc in common:
        shift = np.array([[disturbance(s, arc['endpoint_gpst_s']+dt) for s in arc['stations']] for dt in arc['tags_s']])
        arc['codes_m'] = arc['codes_m']+shift
        arc['rates_m_s'] = arc['rates_m_s']+np.diff(shift, axis=0)/30.
    recalibrated = network_clocks.fit(reference_rows, raw_covariance=raw)
    coupled, joint, _ = study.attach(recalibrated, common)
    recovered = study.dynamic_fit.fit(coupled, joint_covariance=joint)
    np.testing.assert_allclose(recovered['state_ecef_m_m_s'], state, atol=.1, rtol=0)
    # A link-dependent nondispersive perturbation can instead reproduce the
    # exact RF change of another admissible central+J2 trajectory. D/MW/GF
    # remain unchanged; independent reference data have no such perturbation.
    offset = np.array([100., -80., 50., .01, -.02, .015])
    old_curve = orbital_dynamics.Trajectory(state, [-100., 1900.])
    new_curve = orbital_dynamics.Trajectory(state+offset, [-100., 1900.])
    changed = deepcopy(arcs)
    for arc in changed:
        endpoint = arc['endpoint_gpst_s']-36060.
        args = (endpoint, arc['tags_s'], arc['stations_m'], arc['clock_mean'][:, :2], [70000.+endpoint*.1, .1])
        shift = orbital_dynamics.predict_codes(new_curve, *args)-orbital_dynamics.predict_codes(old_curve, *args)
        raw_shift = np.repeat(shift[..., None], 4, axis=-1)
        transformed = raw_shift @ gnss_combinations.transform().T
        np.testing.assert_allclose(transformed[..., 0]-transformed[..., 1], 0., atol=1e-12)
        np.testing.assert_allclose(transformed[..., 2:], 0., atol=1e-12)
        arc['codes_m'] = arc['codes_m']+shift
        arc['rates_m_s'] = arc['rates_m_s']+np.diff(shift, axis=0)/30.
    unshared, joint, _ = study.attach(network, changed)
    biased = study.dynamic_fit.fit(unshared, joint_covariance=joint)
    np.testing.assert_allclose(biased['state_ecef_m_m_s'], state+offset, atol=.1, rtol=0)
    assert np.linalg.norm(np.asarray(biased['state_ecef_m_m_s'])[:3]-state[:3]) > 130.
    assert not biased['physical_covariance_qualified']
