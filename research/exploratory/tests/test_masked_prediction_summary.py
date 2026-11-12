"""Missing predictions cannot shrink the original comparison denominator."""
from research.exploratory.masked_prediction_study import summarize
from research.exploratory import masked_prediction_study as study
from research.kinematic import network_closures
from research.exploratory.reference_network_clocks import native
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


def test_diagnostic_entrypoint_writes_no_predictions_or_held_scores(tmp_path,monkeypatch):
    payload=gzip.compress(json.dumps({'candidates':{'CONTROL':{
        'source_profile':{},'reference_rows':[]}}}).encode(),mtime=0)
    archive=tmp_path/'input.gz'
    archive.write_bytes(payload)
    output=tmp_path/'diagnosis'
    monkeypatch.setattr(study,'INPUT',archive)
    monkeypatch.setattr(study,'INPUT_SHA',hashlib.sha256(payload).hexdigest())
    def prepare(rows,candidate,covariance,*,diagnose_only=False):
        assert candidate=='CONTROL' and diagnose_only
        return {'baseline':{'status':'FUTURE_LINK_PREDICTIONS_FROZEN','training_stop_s':60.},
                'model_status':'COVARIANCE_DIAGNOSTIC_COMPLETE','diagnostics':{}}
    def forbidden(*args,**kwargs):
        raise AssertionError('diagnosis accessed a scorer or predictive comparison')
    monkeypatch.setattr(study.mask_consistent_prediction,'prepare_future_links',prepare)
    monkeypatch.setattr(study.network_closures,'score_future_links',forbidden)
    monkeypatch.setattr(study,'summarize',forbidden)
    monkeypatch.setattr(sys,'argv',['study','--diagnose-mask','--output',str(output)])
    study.main()
    result=json.loads(gzip.decompress((output/'covariance-diagnosis.json.gz').read_bytes()))
    assert result['diagnostic_only'] and not result['held_scores_computed']
    assert not result['correction_variance_fitted']
    assert not (output/'predictions-before-scoring.json.gz').exists()
    assert not (output/'summary.json').exists()


def test_retained_covariance_diagnosis_identifies_positive_directions_cut_by_the_guard():
    path=study.ROOT/'research/exploratory/mask-consistent-errors-2026-10-25/covariance-diagnosis.json.gz'
    report=json.loads(gzip.decompress(path.read_bytes()))
    producer=report['implementation_revision']
    assert producer=='f3d40d2212d5ba2c780f8013c7d62713b5c54b0a'
    assert report['diagnostic_only'] and not report['held_scores_computed']
    assert not report['correction_variance_fitted']
    assert report['input_sha256']==study.INPUT_SHA
    for name,wanted in report['source_sha256'].items():
        source=subprocess.check_output(['git','show',producer+':'+name],cwd=study.ROOT)
        assert hashlib.sha256(source).hexdigest()==wanted
    first={'G05':'all_admitted','G11':'all_admitted','G19':None,'G20':'all_admitted','G21':'prefix'}
    assert set(report['folds'])==set(first)
    for fold,record in report['folds'].items():
        assert record['first_rejection_stage']==first[fold]
        assert not record['held_scores_computed'] and not record['correction_variance_fitted']
        assert 'variants' not in record
        for stage,d in record['diagnostics'].items():
            eigen=np.asarray(d['eigenvalues_m2'])
            components=np.asarray(d['error_eigen_components_m'])
            keep=eigen>d['eigenvalue_cut_m2']
            assert len(eigen)==len(components)==d['error_count']
            assert np.min(eigen)>0.
            assert keep.sum()==d['retained_rank']
            assert np.isclose(np.linalg.norm(components),d['error_norm_m'],rtol=1e-10)
            assert np.isclose(np.linalg.norm(components[~keep]),d['discarded_error_norm_m'],rtol=1e-6,atol=1e-10)
            assert d['operator_replay_max_abs_m']<5e-10
            if d['discarded_count']:
                assert not d['guard_accepts']
                assert d['positive_discarded_eigenvalues']==d['discarded_count']
                assert d['discarded_error_norm_m']>d['image_tolerance_m']
                assert d['operator_replay_l2_m']<1e-3*d['discarded_error_norm_m']
                assert 0.<d['discarded_error_factor_variance_m2']<d['eigenvalue_cut_m2']
                np.testing.assert_allclose(d['discarded_error_factor_variance_m2'],
                    d['discarded_error_gram_variance_m2'],rtol=1e-7,atol=1e-17)
            else:
                assert d['guard_accepts']


def test_repaired_execution_preserves_original_support_and_replays_all_scores():
    folder=study.ROOT/'research/exploratory/mask-consistent-errors-2026-10-25/solver-repair-v2'
    prediction=json.loads(gzip.decompress((folder/'predictions-before-scoring.json.gz').read_bytes()))
    summary=json.loads((folder/'summary.json').read_bytes())
    producer=prediction['implementation_revision']
    assert producer=='5bb99767032d68174b2acdb726254b75991e79bf'
    for name,wanted in prediction['source_sha256'].items():
        source=subprocess.check_output(['git','show',producer+':'+name],cwd=study.ROOT)
        assert hashlib.sha256(source).hexdigest()==wanted
    raw=study.INPUT.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==prediction['input_sha256']==study.INPUT_SHA
    data=json.loads(gzip.decompress(raw))
    comparison_raw=(study.ROOT/'research/exploratory/missnet-transfer-2026-10-19/original-comparison.json').read_bytes()
    assert hashlib.sha256(comparison_raw).hexdigest()==summary['comparison_sha256']
    assert prediction['all_predictions_fixed_before_scoring']
    assert not any(prediction[k] for k in ('prospective_confirmation','physical_covariance_qualified','candidate_products_used'))
    first=json.loads(gzip.decompress((folder.parent/'predictions-before-scoring.json.gz').read_bytes()))
    replay={}
    scores=json.loads(gzip.decompress((folder/'native-scores.json.gz').read_bytes()))
    assert set(prediction['folds'])==set(first['folds'])=={'G05','G11','G19','G20','G21'}
    for fold,record in prediction['folds'].items():
        assert record['baseline']==first['folds'][fold]['baseline']
        methods={'wet':record['baseline'],**record['variants']}
        replay[fold]={label:network_closures.score_future_links(p,data['candidates'][fold]['reference_rows'])
                      for label,p in methods.items()}
        for label,score in replay[fold].items():
            for actual,stored in zip(score['increment_errors'],scores[fold][label]['increment_errors'],strict=True):
                assert actual['lag_s']==stored['lag_s'] and actual['count']==stored['count']
                assert [(r['station'],r['reference'],r['time_s']) for r in actual['rows']]==[
                    (r['station'],r['reference'],r['time_s']) for r in stored['rows']]
                np.testing.assert_allclose([r['z'] for r in actual['rows']],
                                           [r['z'] for r in stored['rows']],atol=1e-12,rtol=0)
                for field in ('code_phase_mean_error_m','code_phase_rms_error_m','code_phase_mean_outer_product_m2'):
                    np.testing.assert_allclose(actual[field],stored[field],atol=1e-12,rtol=0)
        if record['model_status']=='CONDITIONAL_MASK_CONSISTENT_MODEL':
            for quality in (record['model']['prefix_numerical_solve'],record['conditional_numerical_solve']):
                assert quality['solver']=='equilibrated-machine-resolution-v2'
                assert quality['whitening_identity_inf_error']<=quality['whitening_identity_inf_limit']
                assert quality['solve_relative_backward_error']<=quality['solve_relative_backward_error_limit']
            assert record['noise_image_rank']==record['admitted_error_count']
    actual=summarize(replay,json.loads(comparison_raw),primary_method='mask_consistent')
    assert actual['criteria']==summary['criteria']
    assert actual['passes_all']==summary['passes_all']
    for method in ('wet','mask_consistent'):
        for lag,count in (('30',1248),('300',874)):
            result=actual['methods'][method]['pooled'][lag]
            expected=summary['methods'][method]['pooled'][lag]
            assert result['count']==expected['count']
            assert result['missing_count']==expected['missing_count']
            assert result['count']+result['missing_count']==count
            np.testing.assert_allclose(result['code_phase_rms_m'],expected['code_phase_rms_m'],rtol=0,atol=1e-12)
