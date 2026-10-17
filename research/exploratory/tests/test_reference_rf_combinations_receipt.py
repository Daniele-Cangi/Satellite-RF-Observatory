"""Replay raw-combination scoring and the immutable numerical provenance."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study


PRODUCER = 'b23afe60d675f03d64f5917b23555a617e34eb40'
RESULT_SHA256 = 'a7b864b74b4952277f26f4a6a8b06680aae4c6e63d744ff8ff64fdeebd6e857c'


def test_joint_combinations_receipt_preserves_inputs_covariance_support_and_forecasts():
    path = study.baseline.BASE/'results/joint_rf_combinations_v1.json.gz'
    payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    result = json.loads(gzip.decompress(payload))
    raw,data = study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for name,wanted in result['source_sha256'].items():
        source = subprocess.check_output(['git','show',PRODUCER+':'+name],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    assert result['schema']=='exposed-joint-rf-combinations-v1'
    assert result['all_predictions_before_scoring'] and result['geometry_free_segmentation']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'g12_state_accessed','oracle_tuning','new_confirmation','physical_covariance_qualified',
        'production_floors_changed','raw_covariance_qualified','mw_bias_stability_qualified'))
    assert set(result['candidates'])==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in result['candidates'].values())==440
    assert sum(w['status']=='PREPARED' for c in result['candidates'].values() for w in c['windows'])==63
    labels = {'network_gf_segments','joint_independent','joint_free_drift','joint_correlated_code'}
    np.testing.assert_array_equal(result['combination_transform'],study.gnss_combinations.transform())
    for label,raw_covariance in result['raw_covariance_scenarios_m2'].items():
        expected = study.gnss_combinations.assumed_endpoint_covariance(
            code_correlation=.5 if label=='joint_correlated_code' else 0.)
        np.testing.assert_array_equal(raw_covariance,expected)
    for candidate,c in result['candidates'].items():
        assert set(c['variants'])==labels
        for label,v in c['variants'].items():
            predictions = v['rf_predictions']
            serialized = json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()
            assert hashlib.sha256(serialized).hexdigest()==v['prediction_sha256']
            assert study.baseline.score_rf(data,candidate,predictions)==v['rf_evaluation']
            assert study.score_mw(data,candidate,predictions)==v['mw_evaluation']
            fit = v['fit']
            if 'state_ecef_m_m_s' not in fit:
                assert fit['status']=='INSUFFICIENT_PREPARED_ARCS'
                continue
            np.linalg.cholesky(fit['conditional_global_covariance'])
            assert fit['status']=='BRANCH_SEARCH_INCOMPLETE'
            assert fit['branch_failures']
            assert all('exterior-Earth' in b['reason'] for b in fit['branch_failures'])
            retained = [b['branch'] for b in fit['branches']+fit['branch_failures']]
            assert len(retained)==len(set(retained))
            assert v['state_evaluation']['summary']['BEYOND_ALL_TRAINING']['count']==1
            calibration,transport,held = (c[label][k] for k in ('calibration','transport','held_out_links'))
            assert all(r['reference']!=candidate for r in calibration['residuals'])
            assert not held['segmentation_uses_withheld_phase']
            np.linalg.cholesky(transport['clock_covariance'])
            target = transport['target_continuity']
            assert not target['globally_withheld_target_phase_used'] and target['target_codes_retained']
            assert fit['retained_phase_increment_count']==target['retained_increment_count']
            assert fit['total_phase_increment_count']==target['total_increment_count']
            if label=='network_gf_segments':
                continue
            retained_covariance = study.gnss_combinations.covariance(
                result['raw_covariance_scenarios_m2'][label])[np.ix_(
                    study.gnss_combinations.RETAINED,study.gnss_combinations.RETAINED)]
            np.testing.assert_array_equal(calibration['retained_combination_covariance_m2'],retained_covariance)
            assert sum(held['mw_status_counts'].values())==sum(held['code_status_counts'].values())
            assert held['gf_prediction']=='UNIDENTIFIABLE_WITH_FREE_LINK_EPOCH_IONOSPHERE'
            for p,a in zip(predictions,fit['arc_parameters'],strict=True):
                if p['status']!='PREDICTED':
                    continue
                expected = a.get('mw_rate_bias_m_s',[0.]*len(p['stations']))
                assert p['mw_rate_m_s']==expected
    for label,counts in result['fit_status_counts'].items():
        assert counts==dict(Counter(c['variants'][label]['fit']['status'] for c in result['candidates'].values()))
