import json
import numpy as np
import pytest
from research.exploratory import pseudotarget_reference as study
from research.exploratory.pseudotarget_statistics import correlation, summarize


@pytest.fixture
def plan():
    return json.loads((study.BASE/'pseudotarget_plan.json').read_bytes())


def test_excluded_code_never_read_by_clock_and_nonlinear_closure(plan):
    class Codes(dict):
        def __getitem__(self, key):
            assert key != 'P'
            return super().__getitem__(key)
    codes = Codes({s: 100. for s in ['A', 'B', 'C', 'D']}, P=float('nan'))
    def model(sv, code, clock):
        assert sv != 'P'
        return .001*clock
    result = study.receiver_clock(codes, ['A','B','C','D'], 'P', model,
                                  dict.fromkeys(['A','B','C','D'], 0.), plan)
    assert result['status'] == 'EVALUATED'
    assert result['clock_m'] == pytest.approx(100/1.001, abs=1e-6)
    with pytest.raises(ValueError):
        study.receiver_clock(codes, ['A','B','C','P'], 'P', model, {}, plan)


def test_correction_sign_and_failed_reference_support(plan):
    codes = dict.fromkeys(['A','B','C','D'], 100.)
    model = lambda *args: 0.
    result = study.receiver_clock(codes, list(codes), 'P', model, dict.fromkeys(codes, 2.), plan)
    assert result['clock_m'] == 98.
    assert study.receiver_clock(codes, ['A','B','C'], 'P', model, {}, plan)['status'] == 'INSUFFICIENT_REMAINING_REFERENCES'
    assert study.receiver_clock(codes, list(codes), 'P', model, {'A': 0.}, plan)['status'] == 'UNSUPPORTED_REFERENCE'
    assert study.receiver_clock(codes, list(codes), 'P', lambda *args: float('nan'), dict.fromkeys(codes, 0.), plan)['status'] == 'NONFINITE_MODEL'


def test_shared_offset_gauge_and_disconnected_training_rejection():
    rows = [{'station': 'S', 'time_s': t, 'reference': s, 'residual_m': v+10*t}
            for t in [0,1,2] for s,v in [('A',-2.),('B',0.),('C',2.)]]
    fit = study.fit_offsets(rows)
    assert fit['status'] == 'FITTED'
    assert fit['coefficients_m'] == pytest.approx({'A':-2.,'B':0.,'C':2.})
    rows = [{'station':'S','time_s':i,'reference':s,'residual_m':0.}
            for i, pair in enumerate([['A','B'],['C','D']]) for s in pair]
    assert study.fit_offsets(rows)['status'] == 'TRAINING_NOT_IDENTIFIABLE'


def test_temporal_statistics_use_exact_lags_and_keep_missing(plan):
    assert correlation([(1.,2.)]*10, 10)['status'] == 'ZERO_VARIANCE'
    rows = []
    for t in [0,30,90]:
        for s, value in [('S1',t/30+1),('S2',t/30-1)]:
            rows.append({'pseudo_target':'P','station':s,'time_s':t,'status':'ADMITTED',
                         'models':{m:{'status':'EVALUATED','error_m':value} for m in plan['models']}})
    rows.append({'pseudo_target':'P','station':'S1','time_s':120,'status':'PSEUDO_TARGET_NOT_ADMITTED','models':{}})
    result = summarize(rows, plan)
    assert result['zero']['epoch_station_centered']['rms_m'] == 1.
    assert result['zero']['status_counts']['PSEUDO_TARGET_NOT_ADMITTED'] == 1
    lag = next(r for r in result['zero']['lag_correlations'] if r['station']=='S1' and r['lag_s']==30)
    assert lag['count'] == 1 and lag['pearson'] is None
    assert result['paired']['count'] == 6
