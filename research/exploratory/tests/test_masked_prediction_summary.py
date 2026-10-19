"""Missing predictions cannot shrink the original comparison denominator."""
from research.exploratory.masked_prediction_study import summarize


def test_absent_method_retains_every_required_pair_and_fails_acceptance():
    support = {lag:{'G01':[['A','G02',300.]]} for lag in ('30','300')}
    comparison = {'support':support, 'direct_comparison':{
        'models':{'wet':{lag:{'code_rms_m':1.,'phase_rms_m':.01} for lag in ('30','300')}},
        'by_fold':{}}}
    result = summarize({'G01':{}}, comparison)
    assert not result['passes_all']
    assert not result['criteria']['complete_support']
    assert not result['criteria']['primary_10_percent']
    for lag in ('30','300'):
        record = result['methods']['observed_coordinates']['pooled'][lag]
        assert record == {'count':0, 'missing_count':1, 'code_phase_rms_m':None}
