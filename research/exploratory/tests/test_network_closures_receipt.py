"""Retain all terminals and replay conditional closures, predictions and gains."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study

PRODUCER = 'da8db1bedf17ef55ad6cfa65e42e588b0163ca42'
RESULT_SHA256 = '755d4ebf9377feb3d3e0bfd892e88b45b29529c6d432959e5a10a4c10e8592f6'


def test_nondispersive_receipt_preserves_sources_exclusions_and_complete_response():
    payload = (study.baseline.BASE/'results/nondispersive_network_closures_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    result = json.loads(gzip.decompress(payload))
    raw,data = study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path,wanted in result['source_sha256'].items():
        source = subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    assert result['schema']=='exposed-nondispersive-network-closures-v1'
    assert result['all_predictions_before_scoring']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'candidate_code_orbit_scoring','g12_state_accessed','oracle_tuning','new_confirmation',
        'physical_covariance_qualified','production_floors_changed','probe_amplitude_is_sigma'))
    assert result['reference_observation_time_linearization_fixed']
    candidates = result['candidates']
    assert set(candidates)==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values())==440
    assert sum(c['prepared_arc_count'] for c in candidates.values())==63
    assert sum(w['status']=='PREPARED' for c in candidates.values() for w in c['windows'])==63
    weights = study.gnss_combinations.assumed_endpoint_covariance()
    np.testing.assert_array_equal(result['raw_endpoint_weight_covariance_m2'],weights)
    for candidate,c in candidates.items():
        for label,v in c['variants'].items():
            predictions = v['rf_predictions']
            assert hashlib.sha256(json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()).hexdigest()==v['prediction_sha256']
            assert study.baseline.score_rf(data,candidate,predictions)==v['rf_evaluation']
            if 'state_ecef_m_m_s' in v['fit']:
                np.linalg.cholesky(v['fit']['conditional_global_covariance'])
                assert v['fit']['branch_failures']
        if 'state_transfer' not in c:
            continue
        rows = c['reference_rows']
        assert all(r['reference']!=candidate for r in rows)
        network = study.network_clocks.fit(rows,raw_covariance=weights)
        closure = study.network_closures.closure_records(network,candidate)
        assert closure['epoch_ranks']==c['closures']['epoch_ranks']
        for a,b in zip(closure['code_phase_variograms'],c['closures']['code_phase_variograms'],strict=True):
            assert a['count']==b['count'] and a['lag_s']==b['lag_s']
            np.testing.assert_allclose(a['semivariogram_m2'],b['semivariogram_m2'],atol=1e-7,rtol=1e-5)
        future = study.network_closures.prepare_future_links(rows,candidate,weights)
        future = study.network_closures.score_future_links(future,rows)
        stored = c['future_links']
        assert future['status']==stored['status']
        assert future['withheld_row_count']==stored['withheld_row_count']
        assert not stored['segmentation_uses_withheld_phase']
        assert future['held_links']==[tuple(k) for k in stored['held_links']]
        if 'prediction_status_counts' in future:
            assert future['prediction_status_counts']==stored['prediction_status_counts']
        for a,b in zip(future['predictions'],stored['predictions'],strict=True):
            assert a['status']==b['status']
            if a['status']=='PREDICTED':
                np.testing.assert_allclose(a['clock_prediction_m'],b['clock_prediction_m'],atol=1e-6,rtol=0)
        for a,b in zip(future.get('increment_errors',[]),stored.get('increment_errors',[]),strict=True):
            assert a['count']==b['count'] and a['lag_s']==b['lag_s']
            np.testing.assert_allclose(a['code_phase_rms_error_m'],b['code_phase_rms_error_m'],atol=1e-6,rtol=1e-5)
        requests = [{(s,t):coefficient for s,t,coefficient in own} for own in c['clock_requests']]
        state = np.asarray(c['state_response_to_clock_measurements'])
        replay = study.network_closures.state_transfer(network,requests,candidate,state,np.arange(state.shape[1]))
        maps = study.network_clocks.observation_response(network,requests)
        mapping = np.column_stack([r[:,:len(b['rows'])]+r[:,len(b['rows']):2*len(b['rows'])]
            for r,b in zip(maps,network['blocks'],strict=True)])
        for label,mode in c['state_transfer']['modes'].items():
            actual = replay['modes'][label]
            assert actual['status']==mode['status']
            for key in ('maximum_position_gain_m_per_m_reference_rms',
                        'maximum_velocity_gain_mm_s_per_m_reference_rms','position_response_energy_fraction'):
                np.testing.assert_allclose(actual[key],mode[key],atol=1e-8,rtol=1e-5)
            if mode['status']!='PROBE_PREPARED':
                continue
            # Singular-vector signs can vary across LAPACK builds. Verify the
            # retained physical probe and its response, not a chosen SVD sign.
            delta = np.asarray(mode['reference_change_m'])
            np.testing.assert_allclose(np.sqrt(np.mean(delta**2)),result['probe_rms_m'],atol=1e-12,rtol=0)
            np.testing.assert_allclose(state @ mapping @ delta,mode['linear_state_change_m_m_s'],atol=1e-5,rtol=1e-5)
            v = c['variants'][label]
            if 'probe' not in v:
                continue
            assert v['probe']['weights_and_covariance_preserved']
            if label=='clock_blind':
                assert max(v['probe']['calibrated_closure_change_max_m']) < 1e-5
            if 'state_ecef_m_m_s' in v['fit']:
                change = np.asarray(v['fit']['state_ecef_m_m_s'])-c['variants']['joint_independent']['fit']['state_ecef_m_m_s']
                np.testing.assert_allclose(change,v['probe']['finite_state_change_m_m_s'],atol=1e-9,rtol=0)
    for label,counts in result['fit_status_counts'].items():
        assert counts==dict(Counter(c['variants'][label]['fit']['status'] for c in candidates.values()))
