"""Retain source attribution execution, historical bytes and null-safe transfer."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study

PRODUCER='3e31526237c8047982e6630852fd457e299c0673'
RESULT_SHA256='a8caee27bbb751090ce4af25d384bc23bad8111e2d94fe76754834f937821467'


def test_source_separation_receipt_replays_joint_geometry_and_estimable_transfer():
    payload=(study.baseline.BASE/'results/reference_source_separation_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    result=json.loads(gzip.decompress(payload));raw,data=study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path,wanted in result['source_sha256'].items():
        source=subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    assert result['schema']=='exposed-reference-source-separation-v1' and result['all_predictions_before_scoring']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'candidate_code_orbit_scoring','g12_state_accessed','oracle_tuning','new_confirmation',
        'physical_covariance_qualified','production_floors_changed','source_estimates_used_as_candidate_corrections'))
    assert result['reference_orbit_shape_is_fixed_emission_apc_displacement']
    assert result['reference_clock_relativity_and_emission_not_recomputed_for_source_shapes']
    candidates=result['candidates'];assert set(candidates)==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values())==440
    assert sum(c['prepared_arc_count'] for c in candidates.values())==63
    assert dict(Counter(c['fit']['status'] for c in candidates.values()))==result['fit_status_counts']
    rawcov=study.gnss_combinations.assumed_endpoint_covariance()
    for candidate,c in candidates.items():
        predictions=c['rf_predictions']
        assert hashlib.sha256(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()).hexdigest()==c['prediction_sha256']
        assert study.baseline.score_rf(data,candidate,predictions)==c['rf_evaluation']
        assert study.score_mw(data,candidate,predictions)==c['mw_evaluation']
        if 'source_models' not in c:continue
        assert 'preparation_failure' not in c
        rows=c['reference_rows'];assert all(r['reference']!=candidate for r in rows)
        network=study.network_clocks.fit(rows,raw_covariance=rawcov)
        full='wet_orbit_antenna_bias';stored=c['source_models'][full]
        actual,w=study.source_geometry.profile_sources(network,candidate,study.source_geometry.FAMILIES)
        assert (actual['resolved_rank'],actual['null_count'],actual['wet']['status'])==(stored['resolved_rank'],stored['null_count'],stored['wet']['status'])
        np.testing.assert_allclose(actual['singular_values_per_m'],stored['singular_values_per_m'],atol=1e-8,rtol=1e-5)
        n=np.asarray(stored['unresolved_source_basis']);np.testing.assert_allclose(n@n.T,w['null']@w['null'].T,atol=1e-5,rtol=0)
        requests=[{(s,t):coefficient for s,t,coefficient in own} for own in c['clock_requests']]
        kg=sum(k@g for k,g in zip(study.network_clocks.observation_response(network,requests),w['designs'],strict=True))
        response=np.asarray(c['full_state_observation_response']);target=np.asarray(c['target_wet_model_design'])
        g=np.zeros((response.shape[1],len(w['columns'])))
        for j,col in enumerate(w['columns']):
            if col[0]=='wet':g[:,j]=target[:,actual['wet']['stations'].index(col[1])]
        t=-response[:,c['transport']['clock_observation_indices']]@kg-response@g
        retained=stored['state_response']
        np.testing.assert_allclose(t,retained['coupled_model_response'],atol=1e-7,rtol=1e-5)
        if actual['null_count']:
            probe=np.asarray(retained['null_probe_m'])
            np.testing.assert_allclose(np.linalg.norm(probe),.01,atol=1e-14,rtol=0)
            np.testing.assert_allclose(t@probe,retained['null_probe_linear_state_change_m_m_s'],atol=1e-8,rtol=1e-5)
            assert not retained['full_reference_observation_time_relinearized'] and not retained['null_probe_is_observed_error']
            for k,atol in enumerate((1e-6,1e-9,1e-9)):
                np.testing.assert_allclose(np.asarray(retained['fixed_geometry_reference_refit_minus_linear'])[k::3],0.,atol=atol,rtol=0)
        future=study.network_closures.prepare_future_links(rows,candidate,rawcov,source_families=study.source_geometry.FAMILIES)
        future=study.network_closures.score_future_links(future,rows);old=c['future_links'][full]
        assert future['status']==old['status'] and future['prediction_status_counts']==old['prediction_status_counts']
        assert len(future['level_errors'])==len(old['level_errors'])
        for a,b in zip(future['level_errors'],old['level_errors'],strict=True):
            assert (a['station'],a['reference'],a['time_s'])==(b['station'],b['reference'],b['time_s'])
            np.testing.assert_allclose([a['code_error_m'],a['phase_error_m']],[b['code_error_m'],b['phase_error_m']],atol=1e-5,rtol=1e-5)
