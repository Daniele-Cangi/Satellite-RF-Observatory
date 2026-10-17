"""Retained weak-source execution, independent-information and recovery receipt."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study

PRODUCER='a52202088aa2204507e0e5d3f37fb489b31a0f80'
RESULT_SHA256='917202d0184c4bed1b8925d98818df6c4e0a14af1ad2b9eb2524f5dd001b3717'


def test_weak_source_receipt_preserves_boundaries_denominators_and_physical_recovery():
    payload=(study.baseline.BASE/'results/weak_source_physical_recovery_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    result=json.loads(gzip.decompress(payload));raw,data=study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path,wanted in result['source_sha256'].items():
        source=subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    assert result['schema']=='exposed-weak-source-physical-recovery-v1'
    assert result['all_predictions_before_scoring']
    assert result['archived_rf_state_used_only_for_local_response_and_after_fit_comparison']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'candidate_code_orbit_scoring','archived_rf_state_used_as_fit_seed','g12_state_accessed','oracle_tuning',
        'new_confirmation','physical_covariance_qualified','production_floors_changed',
        'independent_measurements_admitted','physical_probe_amplitudes_are_measured_errors','thresholds_selected_from_scores'))
    assert result['rank_rtols']==[1e-9,1e-10,1e-11] and result['probe_source_l2_m']==[.01,.1]
    prior_bytes=(study.baseline.BASE/'results/reference_source_separation_v1.json.gz').read_bytes()
    assert hashlib.sha256(prior_bytes).hexdigest()==result['prior_sha256']
    prior=json.loads(gzip.decompress(prior_bytes))
    candidates=result['candidates'];assert set(candidates)==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values())==440
    assert sum(c['prepared_arc_count'] for c in candidates.values())==63
    prepared=[]
    for candidate,c in candidates.items():
        assert c['windows']==prior['candidates'][candidate]['windows']
        for label,v in c['variants'].items():
            predictions=v['rf_predictions']
            if 'state_ecef_m_m_s' in v['fit']:
                assert v['cold_start_rf_initialization'] and v['target_weight_covariance_fixed_at_nominal']
            assert hashlib.sha256(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()).hexdigest()==v['prediction_sha256']
            assert study.baseline.score_rf(data,candidate,predictions)==v['rf_evaluation']
            assert study.score_mw(data,candidate,predictions)==v['mw_evaluation']
        if 'source_profile' not in c:continue
        prepared.append(candidate);assert 'preparation_failure' not in c
        assert all(r['reference']!=candidate and r['source_emission_relativity_linearized'] for r in c['reference_rows'])
        ranks=[c['stability']['thresholds'][str(t)]['rank'] for t in result['rank_rtols']]
        assert ranks==sorted(ranks)
        np.testing.assert_allclose(np.asarray(c['reference_model_state_map'])+c['candidate_model_state_map'],c['coupled_model_state_map'],atol=1e-9,rtol=1e-12)
        assert len(c['clock_endpoint_keys'])==len(set(map(tuple,c['clock_endpoint_keys'])))
        assert c['clock_derivative_ablation']['status']=='DIFFERENT_CALIBRATION_MODEL_NOT_EQUIVALENT_DATUM'
        assert {(p['mode'],p['source_l2_m'],p['sign']) for p in c['physical_probes']}=={
            (m,a,sign) for m in ('strong','weak') for a in (.01,.1) for sign in ((1.,-1.) if m=='weak' else (1.,))}
        for p in c['physical_probes']:
            np.testing.assert_allclose(np.linalg.norm(p['source_vector_m']),p['source_l2_m'],atol=1e-15,rtol=0)
            assert p['status'] in ('FINITE_PHYSICAL_INCREMENT_PREPARED','FINITE_PHYSICAL_PROBE_FAILED')
        for designs in c['independent_information'].values():
            for design in designs.values():
                assert design['independent_measurements_are_hypothetical']
                assert design['precision_is_source_information_diagnostic_not_added_to_rf_covariance']
                assert [g['sigma_m'] for g in design['grid']]==[.0001,.001,.01,.1,1.]
                for g in design['grid']:
                    if g['state_functional_status']=='UNRESOLVED_STATE_FUNCTIONAL':
                        assert not g['complete_state_precision_issued'] and not g['meets_1m_1mm_s_design_benchmark']
    assert prepared==['G05','G11','G19','G20','G21']
    for label,counts in result['fit_status_counts'].items():
        assert dict(Counter(c['variants'][label]['fit']['status'] for c in candidates.values()))==counts
    # Replay the adverse G19 source geometry and one retained finite physical
    # increment. Full cold-start trajectories are not rerun by this receipt.
    candidate='G19';c=candidates[candidate];rawcov=study.gnss_combinations.assumed_endpoint_covariance()
    network=study.network_clocks.fit(c['reference_rows'],raw_covariance=rawcov)
    profile,w=study.source_geometry.profile_sources(network,candidate,study.source_geometry.FAMILIES)
    assert (profile['resolved_rank'],profile['null_count'])==(c['source_profile']['resolved_rank'],c['source_profile']['null_count'])
    t=np.asarray(c['coupled_model_state_map'])
    modes,spectrum=study.source_geometry.weak_modes(w['design'],t,profile['original_weighted_source_scale_per_m'])
    assert modes['thresholds'].keys()==c['stability']['thresholds'].keys()
    for key,v in modes['thresholds'].items():
        assert v['rank']==c['stability']['thresholds'][key]['rank']
        np.testing.assert_allclose(v['position_gain_m_per_weighted_reference_norm'],c['stability']['thresholds'][key]['position_gain_m_per_weighted_reference_norm'],atol=1e-2,rtol=1e-3)
    probe=next(p for p in c['physical_probes'] if p['mode']=='weak' and p['source_l2_m']==.01 and p['sign']==1)
    assert probe['status']=='FINITE_PHYSICAL_INCREMENT_PREPARED'
    vector=np.asarray(probe['source_vector_m'])
    signals=[(b['rows'],np.asarray(p)) for b,p in zip(network['blocks'],probe['physical_increment_blocks'],strict=True)]
    linear=[(b['rows'],g@vector) for b,g in zip(network['blocks'],w['designs'],strict=True)]
    actual=study.source_geometry.known_source_recovery(c['reference_rows'],signals,linear,vector,t,spectrum,rawcov,candidate)
    for label,values in actual.items():
        stored=probe['recovery'][label]
        assert values['status']==stored['status'] and values['injected_functional_status']==stored['injected_functional_status']
        np.testing.assert_allclose(values['fitted_source_projection_m'],stored['fitted_source_projection_m'],atol=1e-5,rtol=1e-3)
    designs=study.source_geometry.independent_information(spectrum,t,w['columns'],c['clock_endpoint_source_map'],c['stability']['weak_direction_m_per_unit_l2_m'])
    for label,design in designs.items():
        stored=c['independent_information']['1e-10'][label]
        assert design['measurement_count']==stored['measurement_count']
        for a,b in zip(design['grid'],stored['grid'],strict=True):
            assert a['resolved_rank']==b['resolved_rank'] and a['state_functional_status']==b['state_functional_status']
            np.testing.assert_allclose(a['identified_projection_position_sigma_m'],b['identified_projection_position_sigma_m'],atol=1e-5,rtol=1e-3)
