"""Chronological transfer to a receiver excluded from local correction training."""
import hashlib
from pathlib import Path
from collections import Counter
import numpy as np
from .erp_polar_bound import pinned, strict_json
from .reference_residual_structure_v2 import predict_block, rms, groups

BASE = Path(__file__).parent


def key(row):
    return row['station'],row['time_s'],row['reference']


def inputs(plan_sha):
    plan = strict_json(pinned(BASE/'spatial_reference_plan.json',plan_sha))
    day = strict_json(pinned(BASE/'day_reference_plan.json',plan['baseline_plan_sha256']))
    reports = {name:strict_json(pinned(BASE/meta['path'],meta['sha256'])) for name,meta in plan['reports'].items()}
    for report in reports.values():
        if report['plan'] != day or not report['calibration_complete'] or report['target_orbit_accessed'] is not False:
            raise ValueError('unqualified source report')
        validate_rows(report['rows'],day)
    if [key(r) for r in reports['rapid']['rows']] != [key(r) for r in reports['final']['rows']]:
        raise ValueError('product path cohorts differ')
    if plan['training_before_gpst_s'] != day['training_before_gpst_s']:
        raise ValueError('chronological split differs')
    return plan,day,reports


def validate_rows(rows,day):
    expected_times = list(range(day['start_gpst_s'],day['start_gpst_s']+day['samples']*day['step_s'],day['step_s']))
    if len({key(r) for r in rows}) != len(rows):
        raise ValueError('duplicate reference path')
    if {r['station'] for r in rows} != set(day['stations']):
        raise ValueError('station cohort differs')
    for row in rows:
        if row['reference'] == day['target_excluded'] or row['reference'] not in day['references']:
            raise ValueError('unadmitted reference')
        if not np.isfinite(row['residual_m']):
            raise ValueError('nonfinite residual')
    blocks = groups(rows)
    for station in day['stations']:
        if sorted(t for s,t in blocks if s==station) != expected_times:
            raise ValueError('incomplete station epoch sequence')
    if any(len(indices)<day['minimum_references'] for indices in blocks.values()):
        raise ValueError('incomplete reference block')


def fold(rows,stations,excluded,split,model):
    if excluded not in stations or len(stations)!=7:
        raise ValueError('seven declared stations required')
    training = [r for r in rows if r['station'] != excluded and r['time_s'] < split]
    testing = [r for r in rows if r['station'] == excluded and r['time_s'] >= split]
    train_stations = sorted({r['station'] for r in training})
    if train_stations != sorted(set(stations)-{excluded}) or not testing:
        raise ValueError('missing fold cohort')
    result = predict_block(training,testing,model)
    return {'excluded_station':excluded,'training_stations':train_stations,
            'training_times_s':sorted({r['time_s'] for r in training}),
            'test_times_s':sorted({r['time_s'] for r in testing}),**result}


def pool(folds,expected_count):
    predictions = [r for f in folds for r in f['test_predictions']]
    if len(predictions)!=expected_count or len({key(r) for r in predictions})!=expected_count:
        raise ValueError('pooled test paths missing or duplicated')
    good = [r for r in predictions if r['status']=='PREDICTED']
    supported = rms([r['error_m'] for r in good])
    baseline = rms([r['observed_contrast_m'] for r in good])
    return {'test_count':expected_count,'predicted_count':len(good),
            'status_counts':dict(Counter(r['status'] for r in predictions)),
            'all_test_zero_rms_m':rms([r['observed_contrast_m'] for r in predictions]),
            'all_test_error_rms_m':supported if len(good)==expected_count else None,
            'supported_error_rms_m':supported,'supported_zero_rms_m':baseline,
            'supported_improvement_percent':100*(1-supported/baseline) if baseline else None}


def run(plan_sha,progress=None):
    plan,day,reports = inputs(plan_sha)
    variants = {}
    for name,report in reports.items():
        rows = report['rows']
        test_count = sum(r['time_s']>=plan['training_before_gpst_s'] for r in rows)
        models = {}
        for model in plan['models']:
            folds = [fold(rows,day['stations'],station,plan['training_before_gpst_s'],model) for station in day['stations']]
            models[model] = {'folds':folds,'pooled':pool(folds,test_count)}
        variants[name] = models
        if progress:
            progress({'product':name,'shared_satellite':models['shared_satellite']['pooled']})
    return {'schema':'spatial-reference-transfer-v1','plan':plan,'plan_sha256':plan_sha,
            'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'variants':variants,'target_fit_performed':False,'target_orbit_accessed':False,
            'absolute_future_rf_prediction':False,'new_confirmation':False,'physical_covariance_qualified':False,
            'upstream_station_independence_established':False,
            'interpretation':'Pooled folds share training observations and are not independent trials; only local correction training excludes each receiver.'}
