"""Global holdout exclusion, calibration and historical-comparison boundaries."""
from copy import deepcopy
import json

import numpy as np
import pytest

from research.exploratory import g12_dynamic_fit as study


def inputs():
    paths = {'hour':'results/g12_full_hour_v1.json',
             'target':'inputs/real_phase/g12_target_phase_v2.json',
             'positions':'inputs/day_reference/positions.json',
             'baseline':'results/day_reference_v1.json',
             'clock':'results/reference_phase_clock_full_hour_v1.json'}
    return {k:json.loads((study.BASE/v).read_bytes()) for k,v in paths.items()}


def test_alternate_cohorts_preserve_outcomes_and_global_endpoint_exclusion():
    hour = inputs()['hour']
    for mode,count in [('code_only',17),('code_phase',8)]:
        cases,selection = study.cohort(hour,mode)
        assert len(cases)==count
        assert len(selection['retained_outcomes'])==40
        training = {tuple(k) for k in selection['training_keys']}
        excluded = {tuple(k) for k in selection['withheld_endpoint_keys']}
        assert not training & excluded
        assert len(training)==count*15 and len(excluded)==count*5
        for c,r in zip(hour['cases'],selection['retained_outcomes'],strict=True):
            assert c['status']==r['historical_status']
            assert c.get('fits',{}).get(mode,{}).get('status')==r['historical_fit_status']
            if r['selected']:
                assert r['index']%2==0


def test_training_excludes_all_future_values_and_historical_target_states():
    data = inputs()
    class Forbidden:
        def __float__(self):
            raise AssertionError('excluded value decoded')
        def __array__(self,*args,**kwargs):
            raise AssertionError('historical target state decoded')
    for mode in study.MODES:
        cases,selection = study.cohort(data['hour'],mode)
        expected = study.training_arcs(cases,data['target'],data['positions'],data['baseline'],data['clock'],mode)
        poisoned = deepcopy(data['target'])
        excluded = {tuple(k) for k in selection['withheld_endpoint_keys']}
        for s,v in poisoned['stations'].items():
            for r in v.get('rows',[]):
                if (s,r['time_s']) in excluded:
                    r['code_m']=r['phase_m']=Forbidden()
        for c in cases:
            for f in [c['provisional_code_fit'],*c['fits'].values()]:
                f['state']=Forbidden()
        actual = study.training_arcs(cases,poisoned,data['positions'],data['baseline'],data['clock'],mode)
        for a,b in zip(actual,expected,strict=True):
            for k in ['codes_m','rates_m_s','stations_m','clock_mean','covariance']:
                np.testing.assert_array_equal(a[k],b[k])


def test_calibration_rejection_precedes_target_value_access():
    data = inputs()
    cases,_ = study.cohort(data['hour'],'code_only')
    data['baseline']['calibrations'][cases[0]['stations'][0]]['status']='REJECTED'
    with pytest.raises(ValueError,match='before target decoding'):
        study.training_arcs(cases,{},data['positions'],data['baseline'],data['clock'],'code_only')


def test_unavailable_fit_retains_every_prediction_slot():
    data = inputs()
    cases,_ = study.cohort(data['hour'],'code_phase')
    arcs = study.training_arcs(cases,data['target'],data['positions'],data['baseline'],data['clock'],'code_phase')
    predictions = study.predict({'status':'NUMERICAL_FAILURE'},arcs,None)
    assert len(predictions)==8
    assert all(p['status']=='FIT_UNAVAILABLE' for p in predictions)
    scored,summary = study.score(predictions,cases,{},'code_phase')
    assert len(scored)==8 and summary['window_status_counts']=={'UNSCORED':8}
    assert summary['ALL']['pair_count']==0


def test_real_fit_retains_rejections_forecast_worsening_and_replayable_scores():
    data = inputs()
    report = json.loads((study.BASE/'results/g12_dynamic_fit_v3.json').read_bytes())
    assert not any(report[k] for k in ['target_orbit_used','oracle_error_used','prior_target_state_used',
                                       'physical_covariance_qualified','production_floors_changed','new_confirmation'])
    assert report['historical_code_floor_m']==20. and report['target_elevation_mask_deg']==10.
    assert report['input_sha256']['hour']==study.digest((study.BASE/'results/g12_full_hour_v1.json').read_bytes())
    assert set(report['variants'])=={m+'_'+f for m in study.MODES for f,_ in study.FORCES}
    for label,v in report['variants'].items():
        mode = 'code_phase' if label.startswith('code_phase') else 'code_only'
        cases,selection = study.cohort(data['hour'],mode)
        assert v['cohort']==json.loads(json.dumps(selection))
        fitted = v['fit']
        assert fitted['status']==('MODEL_REJECTED' if mode=='code_phase' else 'BRANCH_SEARCH_INCOMPLETE')
        assert len(fitted['branch_failures'])==1
        assert 'exterior-Earth' in fitted['branch_failures'][0]['reason']
        assert fitted['residual_threshold_p']==.01
        assert fitted['conditional_residual_p']<.01 if mode=='code_phase' else fitted['conditional_residual_p']>=.01
        assert sum(fitted['station_code_bias_m'].values())==pytest.approx(0.,abs=1e-10)
        assert all(p['status']=='PREDICTED' and np.min(p['elevation_deg'])>=10. for p in v['predictions'])
        predicted_bytes = json.dumps(v['predictions'],separators=(',',':'),allow_nan=False).encode()
        assert v['frozen_prediction_sha256']==study.digest(predicted_bytes)
        scored,summary = study.score(v['predictions'],cases,data['target'],mode)
        assert scored==v['withheld'] and summary==v['summary']
        assert summary['ALL']['pair_count']==(40 if mode=='code_phase' else 85)
        assert summary['BEYOND_ALL_TRAINING']['pair_count']==5
        assert sum(p['kind']=='BEYOND_ALL_TRAINING' for p in v['predictions'])==1
        assert summary['BEYOND_ALL_TRAINING']['code']['rms']>summary['BEYOND_ALL_TRAINING']['code']['old_same_cohort_rms']
    for version in [1,2]:
        first = json.loads((study.BASE/f'results/g12_dynamic_fit_v{version}.json').read_bytes())
        for force,_ in study.FORCES:
            v = first['variants']['code_phase_'+force]
            assert v['fit']['status']=='NUMERICAL_FAILURE'
            assert v['summary']['window_status_counts']=={'UNSCORED':8}
