"""Replay immutable temporal diagnostics and all retained RF terminals."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study

PRODUCER = 'dff8499198ee4212429bdedb3cae2c5c5ed920fa'
RESULT_SHA256 = '25ea2da175ab42c2c18be931112cdba011441fe38b9d8e2ed3dc9a44445af80a'


def test_temporal_receipt_preserves_sources_reference_only_shape_and_all_forecasts():
    payload = (study.baseline.BASE/'results/temporal_shared_rf_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    result = json.loads(gzip.decompress(payload))
    raw,data = study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for name,wanted in result['source_sha256'].items():
        source = subprocess.check_output(['git','show',PRODUCER+':'+name],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    assert result['schema']=='exposed-temporal-shared-rf-v1'
    assert result['all_predictions_before_scoring']
    assert result['temporal_model']['historical_marginal_weights_preserved']
    assert not result['temporal_model']['reference_estimator_weights_changed']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'g12_state_accessed','oracle_tuning','new_confirmation','physical_covariance_qualified',
        'production_floors_changed','raw_covariance_qualified','mw_bias_stability_qualified'))
    assert set(result['candidates'])==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in result['candidates'].values())==440
    assert sum(w['status']=='PREPARED' for c in result['candidates'].values() for w in c['windows'])==63
    for q,c in result['candidates'].items():
        baseline = c['variants']['joint_independent']
        for label,v in c['variants'].items():
            predictions=v['rf_predictions']
            serialized=json.dumps(predictions,separators=(',',':'),allow_nan=False).encode()
            assert hashlib.sha256(serialized).hexdigest()==v['prediction_sha256']
            assert study.baseline.score_rf(data,q,predictions)==v['rf_evaluation']
            # All four models retain constant MW bias and therefore identical
            # zero-rate forecasts. Their recorded MW evaluation is identical.
            assert v['mw_evaluation']==baseline['mw_evaluation']
            fit=v['fit']
            if 'state_ecef_m_m_s' not in fit:
                assert fit['status']=='INSUFFICIENT_PREPARED_ARCS'
                continue
            assert fit['status']=='BRANCH_SEARCH_INCOMPLETE'
            assert fit['branch_failures']
            branches=[b['branch'] for b in fit['branches']+fit['branch_failures']]
            assert len(branches)==len(set(branches))
            assert all('exterior-Earth' in b['reason'] for b in fit['branch_failures'])
            np.linalg.cholesky(fit['conditional_global_covariance'])
            assert v['state_evaluation']['summary']['BEYOND_ALL_TRAINING']['count']==1
            item=c[label]
            assert item['calibration']==c['joint_independent']['calibration']
            assert item['held_out_links']==c['joint_independent']['held_out_links']
            assert all(r['reference']!=q for r in item['calibration']['residuals'])
            np.testing.assert_array_equal(item['transport']['clock_mean'],c['joint_independent']['transport']['clock_mean'])
            np.linalg.cholesky(item['transport']['clock_covariance'])
            assert fit['retained_phase_increment_count']==item['transport']['target_continuity']['retained_increment_count']
        if 'temporal_model' not in c:
            continue
        model=c['temporal_model']
        assert model['status']=='REFERENCE_INFORMED_SENSITIVITY_ONLY'
        assert not model['physical_temporal_covariance_qualified']
        assert not model['marginal_sigmas_rescaled']
        # Constant segment ambiguities disappear from both differences, so
        # reference residual rows replay the original D/MW increment traces.
        rows=[{**r,'code_m':r['code_residual_m'],'phase_m':r['phase_residual_m'],'mw_m':r['mw_residual_m']}
              for r in c['joint_independent']['calibration']['residuals']]
        replay=study.temporal_contrasts.estimate(rows)
        np.testing.assert_allclose(replay['code_endpoint_ar1_rho_30s'],model['code_endpoint_ar1_rho_30s'],atol=1e-6,rtol=0)
        for part in ('training_variograms','validation_variograms'):
            for a,b in zip(replay[part],model[part],strict=True):
                assert a['count']==b['count'] and a['lag_s']==b['lag_s']
                np.testing.assert_allclose(a['semivariogram_m2'],b['semivariogram_m2'],atol=1e-8,rtol=1e-6)
        for part in ('split_training','split_validation'):
            a,b=replay[part],model[part]
            assert a['status_counts']==b['status_counts']
            assert q not in sum(b['reference_groups'],[])
            np.testing.assert_allclose(a['cross_covariance_m2'],b['cross_covariance_m2'],atol=1e-8,rtol=1e-6)
            assert b['positive_semidefinite']==bool(min(b['cross_covariance_eigenvalues_m2'])>=0)
        for label in ('temporal_code','temporal_shared','temporal_without_cross'):
            t=c[label]['transport']
            assert not t['reference_clock_estimator_refitted'] and not t['physical_covariance_qualified']
            assert t['reference_target_cross_covariance_retained']==(label!='temporal_without_cross')
            assert t['receiver_shared_variance_fraction']==(0. if label=='temporal_code' else .5)
        np.testing.assert_array_equal(c['temporal_shared']['transport']['clock_covariance'],
                                      c['temporal_without_cross']['transport']['clock_covariance'])
    for label,counts in result['fit_status_counts'].items():
        assert counts==dict(Counter(c['variants'][label]['fit']['status'] for c in result['candidates'].values()))
