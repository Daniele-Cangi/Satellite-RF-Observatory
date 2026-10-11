"""Geometry information must survive nuisance elimination, scaling and replay."""
import hashlib
import json

import numpy as np
import pytest
from scipy.linalg import helmert, solve_triangular

from research.exploratory import g12_bias_geometry as study


def test_qr_profile_matches_gls_elimination_with_correlated_measurements():
    rng = np.random.default_rng(872)
    matrix = rng.normal(size=(25,25))
    covariance = matrix@matrix.T+np.eye(25)
    jacobian = rng.normal(size=(25,4))
    # Include the common code-level gauge among local state parameters.
    jacobian[:,0] = np.r_[np.ones(15),np.zeros(10)]
    profile, columns, slope = study.profile_bias(jacobian,covariance,np.ones(4),5)
    chol = np.linalg.cholesky(covariance)
    local = solve_triangular(chol,jacobian,lower=True)
    bias = solve_triangular(chol,columns,lower=True)
    residual = bias-local@np.linalg.lstsq(local,bias,rcond=None)[0]
    np.testing.assert_allclose(profile.T@profile,residual.T@residual,atol=1e-13)
    changed,_,_ = study.profile_bias(jacobian,covariance,np.array([1e3,.01,7.,3.]),5)
    np.testing.assert_allclose(changed.T@changed,profile.T@profile,atol=1e-13)
    assert columns.shape == (25,4) and slope.shape == (21,4)
    np.testing.assert_allclose(columns[:5].sum(axis=0),0,atol=1e-15)
    assert np.count_nonzero(columns[15:]) == 0


def test_disconnected_nuisance_design_is_not_repaired_with_a_floor():
    with pytest.raises(ValueError,match='rank deficient'):
        study.profile_bias(np.zeros((25,4)),np.eye(25),np.ones(4),5)


def test_geometry_rotation_lifts_a_mode_but_repetition_does_not():
    first = np.diag([1.,1.,1.,0.])
    second = np.diag([0.,1.,1.,1.])
    arcs = [{'start_gpst_s':0.,'profile_per_m':first},
            {'start_gpst_s':90.,'profile_per_m':second}]
    assert study.combine_profiles(arcs)['rank'] == 4
    arcs[1]['profile_per_m'] = first
    result = study.combine_profiles(arcs)
    assert result['rank'] == 3
    assert result['conditional_worst_contrast_sigma_m'] is None


def test_linear_bias_drift_includes_time_change_inside_each_arc():
    first,second = np.eye(4),2*np.eye(4)
    arcs = [{'start_gpst_s':0.,'profile_per_m':first,'slope_profile_per_m_s':-30*first},
            {'start_gpst_s':90.,'profile_per_m':second,'slope_profile_per_m_s':-10*second}]
    actual = study.combine_profiles(arcs,linear_drift=True)
    expected = np.vstack([np.column_stack([first,(-.5-30/90)*first]),
                          np.column_stack([second,(.5-10/90)*second])])
    np.testing.assert_allclose(actual['singular_per_m'],np.linalg.svd(expected,compute_uv=False))
    with pytest.raises(ValueError,match='distinct times'):
        study.combine_profiles(arcs[:1],linear_drift=True)


def test_uninformative_or_invalid_profile_never_becomes_a_bias_bound():
    assert study.information_summary(np.zeros((4,4)))['conditional_worst_contrast_sigma_m'] is None
    with pytest.raises(ValueError,match='finite'):
        study.information_summary([[float('nan')]])


def test_real_report_retains_coverage_rejections_and_weak_information():
    report = json.loads((study.BASE/'results/g12_bias_geometry_v1.json').read_bytes())
    previous = json.loads(study.REPORT.read_bytes())
    assert not report['target_orbit_used'] and not report['oracle_error_used']
    assert not report['new_confirmation']
    assert len(report['historical_outcomes']) == 40
    statuses = [r['status'] for r in report['historical_outcomes'] if r['model']=='code_phase']
    assert statuses.count('MODEL_REJECTED') == 15
    assert len(report['arcs']['code_phase']) == 5 and len(report['arcs']['code_only']) == 20
    assert report['common_available_gpst_s'] == list(range(37800,39601,30))
    assert len(report['structural_coverage']) == 121
    assert all(len(row['available_stations'])>=5 for row in report['structural_coverage'])
    assert report['coverage']['YELL00CAN']['row_count'] == 0
    phase = report['combined']['code_phase']['constant']
    assert phase['rank'] == 4 and phase['conditional_worst_contrast_sigma_m'] > 1e4
    assert report['combined']['code_only']['constant']['conditional_worst_contrast_sigma_m'] > 1e5
    for name,arcs in report['arcs'].items():
        for model,drift in [('constant',False),('linear_drift',True)]:
            actual = study.combine_profiles(arcs,linear_drift=drift)
            np.testing.assert_allclose(actual['singular_per_m'],report['combined'][name][model]['singular_per_m'],rtol=1e-12)
        for row in arcs:
            original = next(c for c in previous['cases'] if c['start_gpst_s']==row['start_gpst_s'])
            assert original['fits'][name]['status']=='CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
            assert row['original_augmented_rank'] == (38 if name=='code_only' else 39)
    for name,variants in report['finite_difference_robustness'].items():
        baseline=report['combined'][name]['constant']['conditional_worst_contrast_sigma_m']
        for variant in variants.values():
            assert abs(variant['constant']['conditional_worst_contrast_sigma_m']/baseline-1)<.02
    paths={'rf_report':study.REPORT,'target':study.TARGET,
           'positions':study.BASE/'inputs/day_reference/positions.json',
           'access':study.BASE/'real_target_phase_access_v2.json',
           'baseline':study.BASE/'results/day_reference_v1.json',
           'reference_phase':study.BASE/'results/reference_phase_clock_gps_only_v2.json',
           'previous_bias_report':study.BASE/'results/real_target_bias_identifiability_v1.json'}
    for name,path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == report['input_sha256'][name]
    target=json.loads(study.TARGET.read_bytes())
    assert target['access_sha256']==report['input_sha256']['access']


def test_target_input_mutation_stops_before_a_fit(tmp_path,monkeypatch):
    target=json.loads(study.TARGET.read_bytes())
    target['target_state_accessed']=True
    poison=tmp_path/'poison.json'
    poison.write_text(json.dumps(target),encoding='utf-8')
    monkeypatch.setattr(study,'TARGET',poison)
    def forbidden_fit(*args,**kwargs):
        raise AssertionError('fit must not start with a changed target input')
    monkeypatch.setattr(study,'fit_intervals',forbidden_fit)
    with pytest.raises(ValueError,match='boundary differs'):
        study.run()
