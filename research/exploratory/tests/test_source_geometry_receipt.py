"""Retain the physical-source execution and replay its fits' conditional maps."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study

PRODUCER = '4e42110c32f35ce406559d5056402050456b8911'
RESULT_SHA256 = '5bc2598b04ac628bd74d33a645019615cd2c23eb6112512a70c7727b9b8ed213'


def test_source_geometry_receipt_preserves_provenance_predictions_and_both_paths():
    payload=(study.baseline.BASE/'results/wet_source_coupling_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    result=json.loads(gzip.decompress(payload))
    raw,data=study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path,wanted in result['source_sha256'].items():
        source=subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    assert result['schema']=='exposed-wet-source-coupling-v1'
    assert result['all_predictions_before_scoring'] and result['target_weights_fixed_at_nominal']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'candidate_code_orbit_scoring','g12_state_accessed','oracle_tuning','new_confirmation',
        'physical_covariance_qualified','physical_wet_model_qualified','production_floors_changed',
        'source_estimates_used_as_candidate_corrections','probe_amplitude_is_sigma'))
    candidates=result['candidates']
    assert set(candidates)==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values())==440
    assert sum(c['prepared_arc_count'] for c in candidates.values())==63
    weights=study.gnss_combinations.assumed_endpoint_covariance()
    np.testing.assert_array_equal(result['raw_endpoint_weight_covariance_m2'],weights)
    for candidate,c in candidates.items():
        for variant in c['variants'].values():
            predictions=variant['rf_predictions']
            assert hashlib.sha256(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()).hexdigest()==variant['prediction_sha256']
            assert study.baseline.score_rf(data,candidate,predictions)==variant['rf_evaluation']
            assert study.score_mw(data,candidate,predictions)==variant['mw_evaluation']
            if 'state_ecef_m_m_s' in variant['fit']:
                np.linalg.cholesky(variant['fit']['conditional_global_covariance'])
                assert variant['fit']['branch_failures']
        if 'source_response' not in c:continue
        rows=c['reference_rows']
        assert all(r['reference']!=candidate and r['wet_mapping']>0 for r in rows)
        network=study.network_clocks.fit(rows,raw_covariance=weights)
        profile=study.source_geometry.profile_wet(network,candidate)
        stored=c['source_profile']
        assert profile['status']==stored['status'] and profile['resolved_rank']==stored['resolved_rank']
        if profile['status']=='CONDITIONAL_SOURCE_FIT':
            assert profile['domain_status']==stored['domain_status']
            np.testing.assert_allclose(list(profile['zenith_wet_correction_m'].values()),
                list(stored['zenith_wet_correction_m'].values()),atol=1e-6,rtol=1e-5)
            np.testing.assert_allclose(profile['conditional_parameter_covariance_m2'],
                stored['conditional_parameter_covariance_m2'],atol=1e-5,rtol=1e-5)
        names=profile['stations']
        requests=[{(s,t):coefficient for s,t,coefficient in own} for own in c['clock_requests']]
        assert c['clock_request_output_units']==['m','m/s','m/s']*(len(requests)//3)
        clock=study.source_geometry.clock_wet_response(network,requests,candidate,names)
        for k,tolerance in enumerate((1e-6,1e-9,1e-9)):
            np.testing.assert_allclose(clock[k::3],np.asarray(c['clock_source_response'])[k::3],
                atol=tolerance,rtol=1e-5)
        response=study.source_geometry.coupled_response(np.asarray(c['full_state_observation_response']),
            c['transport']['clock_observation_indices'],clock,np.asarray(c['target_source_model_design']),names)
        actual=c['source_response']
        assert response['status']==actual['status']
        for label,mapping in response['state_model_response_m_m_s_per_m_zenith'].items():
            for own,tolerance in ((slice(0,3),1e-7),(slice(3,6),1e-10)):
                np.testing.assert_allclose(mapping[own],np.asarray(actual['state_model_response_m_m_s_per_m_zenith'][label])[own],
                    atol=tolerance,rtol=1e-5)
        if actual['status']=='SOURCE_PROBE_PREPARED':
            # Use the retained physical probe; do not require a LAPACK sign.
            vector=np.array([actual['zenith_probe_m'][s] for s in names])
            np.testing.assert_allclose(np.sqrt(np.mean(vector**2)),result['probe_rms_m'],atol=1e-12,rtol=0)
            for label in ('reference_only','candidate_only','coupled'):
                expected=np.asarray(actual['state_model_response_m_m_s_per_m_zenith'][label])@vector
                np.testing.assert_allclose(expected,actual['linear_probe_state_change_m_m_s'][label],atol=1e-9,rtol=1e-9)
                v=c['variants'][label]
                if 'probe' not in v:continue
                assert v['probe']['target_weight_covariance_fixed_at_nominal']
                if 'state_ecef_m_m_s' in v['fit']:
                    change=np.asarray(v['fit']['state_ecef_m_m_s'])-c['variants']['joint_independent']['fit']['state_ecef_m_m_s']
                    np.testing.assert_allclose(change,v['probe']['finite_state_change_m_m_s'],atol=1e-9,rtol=0)
        for label,wet in (('clock_only',False),('wet_source',True)):
            future=study.network_closures.prepare_future_links(rows,candidate,weights,wet_sources=wet)
            future=study.network_closures.score_future_links(future,rows)
            stored=c['future_links'][label]
            assert future['status']==stored['status'] and future['withheld_row_count']==stored['withheld_row_count']
            assert not stored['segmentation_uses_withheld_phase']
            for a,b in zip(future['predictions'],stored['predictions'],strict=True):
                assert a['status']==b['status']
                if a['status']=='PREDICTED':
                    np.testing.assert_allclose(a.get('path_prediction_m',a['clock_prediction_m']),
                        b.get('path_prediction_m',b['clock_prediction_m']),atol=1e-6,rtol=0)
            for a,b in zip(future.get('increment_errors',[]),stored.get('increment_errors',[]),strict=True):
                assert a['lag_s']==b['lag_s'] and a['count']==b['count']
                np.testing.assert_allclose(a['code_phase_rms_error_m'],b['code_phase_rms_error_m'],atol=1e-6,rtol=1e-5)
    for label,counts in result['fit_status_counts'].items():
        assert counts==dict(Counter(c['variants'][label]['fit']['status'] for c in candidates.values()))
