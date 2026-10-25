"""Missing predictions cannot shrink the original comparison denominator."""
from research.exploratory.masked_prediction_study import summarize
from research.exploratory import masked_prediction_study as study
from research.kinematic import network_closures
import gzip
import hashlib
import json
import numpy as np
import subprocess
import sys
import pytest


@pytest.mark.parametrize('method',['observed_coordinates','mask_consistent'])
def test_absent_method_retains_every_required_pair_and_fails_acceptance(method):
    support = {lag:{'G01':[['A','G02',300.]]} for lag in ('30','300')}
    comparison = {'support':support, 'direct_comparison':{
        'models':{'wet':{lag:{'code_rms_m':1.,'phase_rms_m':.01} for lag in ('30','300')}},
        'by_fold':{}}}
    result = summarize({'G01':{}}, comparison,primary_method=method)
    assert not result['passes_all']
    assert not result['criteria']['complete_support']
    assert not result['criteria']['primary_10_percent']
    for lag in ('30','300'):
        record = result['methods'][method]['pooled'][lag]
        assert record == {'count':0, 'missing_count':1, 'code_phase_rms_m':None}


def test_optimized_python_cannot_stamp_unrelated_input_as_original_archive(tmp_path):
    wrong = tmp_path/'wrong.gz'
    wrong.write_bytes(b'not the stable source archive')
    output = tmp_path/'output'
    script = ("from pathlib import Path; import sys; "
              "from research.exploratory import masked_prediction_study as s; "
              f"s.INPUT=Path({str(wrong)!r}); "
              f"sys.argv=['study','--output',{str(output)!r},'--comparison','unused']; s.main()")
    process = subprocess.run([sys.executable, '-O', '-c', script], capture_output=True, text=True)
    assert process.returncode != 0 and 'stable input hash mismatch' in process.stderr
    assert not (output/'predictions-before-scoring.json.gz').exists()


def test_small_successful_subset_cannot_pass_full_support_primary_or_secondary():
    support={lag:{'G01':[['A','G02',300.],['A','G03',300.]]} for lag in ('30','300')}
    prior={'models':{'wet':{lag:{'code_rms_m':1.,'phase_rms_m':.01} for lag in ('30','300')}},
           'by_fold':{'G01':{'wet':{'300':{'phase_rms_m':.01}}}}}
    comparison={'support':support,'direct_comparison':prior}
    partial={'increment_errors':[{'lag_s':float(lag),'rows':[
        {'station':'A','reference':'G02','time_s':300.,'z':[0.,.001]}]} for lag in ('30','300')]}
    result=summarize({'G01':{'mask_consistent':partial}},comparison,primary_method='mask_consistent')
    assert result['methods']['mask_consistent']['pooled']['300']['count']==1
    assert not any(result['criteria'][key] for key in ('complete_support','primary_10_percent','secondary'))


def test_retained_mask_consistent_execution_replays_without_refitting():
    folder=study.ROOT/'research/exploratory/mask-consistent-errors-2026-10-25'
    prediction=json.loads(gzip.decompress((folder/'predictions-before-scoring.json.gz').read_bytes()))
    producer=prediction['implementation_revision']
    assert producer=='12a427af47e773a91949a7b38a4524a5890d7300'
    for path,wanted in prediction['source_sha256'].items():
        original=subprocess.check_output(['git','show',producer+':'+path],cwd=study.ROOT)
        assert hashlib.sha256(original).hexdigest()==wanted
    raw=study.INPUT.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==prediction['input_sha256']==study.INPUT_SHA
    data=json.loads(gzip.decompress(raw))
    comparison_path=study.ROOT/'research/exploratory/missnet-transfer-2026-10-19/original-comparison.json'
    comparison=json.loads(comparison_path.read_bytes())
    expected=json.loads((folder/'summary-complete-support.json').read_bytes())
    assert hashlib.sha256(comparison_path.read_bytes()).hexdigest()==expected['comparison_sha256']
    assert set(prediction['folds'])=={'G05','G11','G19','G20','G21'}
    assert prediction['all_predictions_fixed_before_scoring']
    assert not any(prediction[k] for k in ('prospective_confirmation','physical_covariance_qualified','candidate_products_used'))
    stored_scores=json.loads(gzip.decompress((folder/'native-scores.json.gz').read_bytes()))
    replay={}
    for fold,record in prediction['folds'].items():
        methods={'wet':record['baseline'],**record['variants']}
        replay[fold]={label:network_closures.score_future_links(p,data['candidates'][fold]['reference_rows'])
                      for label,p in methods.items()}
        for label,score in replay[fold].items():
            for actual,stored in zip(score['increment_errors'],stored_scores[fold][label]['increment_errors'],strict=True):
                assert actual['lag_s']==stored['lag_s'] and actual['count']==stored['count']
                assert [(r['station'],r['reference'],r['time_s']) for r in actual['rows']]==[
                    (r['station'],r['reference'],r['time_s']) for r in stored['rows']]
                np.testing.assert_allclose([r['z'] for r in actual['rows']],[r['z'] for r in stored['rows']],atol=1e-12,rtol=0)
        if fold!='G19':
            assert record['model_status']=='UNSUPPORTED_MASK_CONSISTENT_MODEL'
            assert record['reason']=='prediction errors outside the covariance image'
        assert len(record['inner_groups'])==7
    result=summarize(replay,comparison,primary_method='mask_consistent')
    assert result['criteria']==expected['criteria'] and not result['passes_all']
    for method in ('wet','mask_consistent'):
        for lag in ('30','300'):
            a,b=result['methods'][method]['pooled'][lag],expected['methods'][method]['pooled'][lag]
            assert a['count']==b['count'] and a['missing_count']==b['missing_count']
            np.testing.assert_allclose(a['code_phase_rms_m'],b['code_phase_rms_m'],atol=1e-12,rtol=0)
    assert result['methods']['wet']['pooled']['300']['count']==874
    assert result['methods']['mask_consistent']['pooled']['300']['count']==38
    assert result['methods']['mask_consistent']['pooled']['300']['missing_count']==836
    # Preserve the initial reporting defect; it never made passes_all true.
    first=json.loads((folder/'summary.json').read_bytes())
    assert first['criteria']['primary_10_percent'] and not first['passes_all']
    assert not expected['criteria']['primary_10_percent'] and expected['scoring_only_correction']
