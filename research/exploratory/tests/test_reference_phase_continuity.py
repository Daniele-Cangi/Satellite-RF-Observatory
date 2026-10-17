"""Replay the continuity execution, its admitted witnesses and RF forecasts."""
from collections import Counter
import gzip
import hashlib
import json
import subprocess

import numpy as np

from research.exploratory import reference_network_clocks as study


def test_continuity_receipt_preserves_sources_support_witnesses_and_predictions():
    path = study.baseline.BASE/'results/reference_phase_continuity_v1.json.gz'
    raw_result = path.read_bytes()
    assert hashlib.sha256(raw_result).hexdigest()=='bcbac22d75371b372fa45e1c5b3ce8fca2aa91c316142a787a5af869cf75cd62'
    result = json.loads(gzip.decompress(raw_result))
    raw,data = study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for name,wanted in result['source_sha256'].items():
        producer = subprocess.check_output(['git','show','f132da4a94822562c95cc8c15f29007e057b024d:'+name],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(producer).hexdigest()==wanted
    assert set(result['candidates'])==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in result['candidates'].values())==440
    assert sum(w['status']=='PREPARED' for c in result['candidates'].values() for w in c['windows'])==63
    assert result['all_predictions_before_scoring']
    assert result['geometry_free_segmentation']
    assert not any(result[k] for k in ('candidate_products_used_in_own_fit','candidate_rf_used_in_own_network',
        'g12_state_accessed','oracle_tuning','new_confirmation','physical_covariance_qualified','production_floors_changed'))
    assert not result['continuity_rule']['physical_detection_qualified']
    index = study.baseline.phase_index(data)
    for candidate,c in result['candidates'].items():
        for label,v in c['variants'].items():
            assert study.baseline.score_rf(data,candidate,v['rf_predictions'])==v['rf_evaluation']
            payload = json.dumps(v['rf_predictions'],separators=(',',':'),allow_nan=False).encode()
            assert hashlib.sha256(payload).hexdigest()==v['prediction_sha256']
            if 'state_ecef_m_m_s' not in v['fit']:
                assert v['fit']['status']=='INSUFFICIENT_PREPARED_ARCS'
                continue
            assert v['fit']['status']=='BRANCH_SEARCH_INCOMPLETE'
            assert v['fit']['branch_failures']
            assert all('exterior-Earth' in b['reason'] for b in v['fit']['branch_failures'])
            assert v['fit']['candidate_count']==len(v['fit']['branches'])
            retained = [b['branch'] for b in v['fit']['branches']+v['fit']['branch_failures']]
            assert len(retained)==len(set(retained))
            assert v['state_evaluation']['summary']['BEYOND_ALL_TRAINING']['count']==1
            np.linalg.cholesky(v['fit']['conditional_global_covariance'])
            calibration = c[label]['calibration']
            assert all(r['reference']!=candidate for r in calibration['residuals'])
            assert not c[label]['held_out_links']['segmentation_uses_withheld_phase']
            if label=='network':
                continue
            rows = [{**r,'segment':r['segment'].rsplit('/gf',1)[0],
                'geometry_free_phase_m':index[r['station']][r['reference'],r['time_s']]['geometry_free_phase_m']}
                for r in calibration['residuals']]
            # Residuals use epoch order; causal state is separate per link.
            assessed = study.phase_continuity.segment(rows)
            expected = [{k:r[k] for k in ('station','reference','time_s','base_segment','segment','continuity')}
                        for r in assessed if r['continuity']['break']]
            key = lambda r:(r['station'],r['reference'],r['time_s'])
            assert [key(r) for r in sorted(expected,key=key)]==[
                key(r) for r in sorted(calibration['continuity_witnesses'],key=key)]
            for a,b in zip(sorted(expected,key=key),sorted(calibration['continuity_witnesses'],key=key),strict=True):
                assert a['segment']==b['segment'] and a['base_segment']==b['base_segment']
                assert a['continuity']['method']==b['continuity']['method']
                for field in ('innovation_m','threshold_m','elapsed_s','raw_change_m'):
                    np.testing.assert_allclose(a['continuity'][field],b['continuity'][field],atol=1e-7,rtol=0)
            arcs = [{'stations':w['stations'],'endpoint_gpst_s':w['start_gpst_s']+60,
                     'tags_s':[-60.,-30.,0.]} for w in c['windows'] if w['status']=='PREPARED']
            _,target = study.target_continuity(data,candidate,arcs)
            assert study.native(target)==c[label]['transport']['target_continuity']
            assert target['retained_increment_count']==v['fit']['retained_phase_increment_count']
            assert target['total_increment_count']==v['fit']['total_phase_increment_count']
    for label,counts in result['fit_status_counts'].items():
        assert counts==dict(Counter(c['variants'][label]['fit']['status'] for c in result['candidates'].values()))
