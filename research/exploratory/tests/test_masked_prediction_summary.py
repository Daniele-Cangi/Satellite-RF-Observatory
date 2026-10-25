"""Missing predictions cannot shrink the original comparison denominator."""
from research.exploratory.masked_prediction_study import summarize
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
