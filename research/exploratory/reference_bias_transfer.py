"""Cross-satellite directional calibration of exposed effective code biases.

Fit first-half references, excluding each pseudo-target from all calibration.
Evaluate later pseudo-target errors in the original reference-clock datum.
No real G12 measurement, state or oracle trains this descriptive model.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.linalg import helmert

from .real_phase import BASE, digest
from .pseudotarget_checked_v2 import PLAN_SHA
from . import pseudotarget_reference as pseudo
from .reference_residual_structure_v2 import groups, design, center_blocks
from . import reference_geometry
from ..kinematic.synthetic import native


def fit_direction(rows):
    if not rows:
        return {'status':'NO_TRAINING', 'columns':[]}
    columns = sorted({r['station']+'/'+axis for r in rows for axis in 'ENU'})
    x, missing = design(rows, 'station_direction', columns)
    if missing.any():
        raise ValueError('training direction support differs')
    y = center_blocks([r['residual_m'] for r in rows], rows)
    u, singular, vt = np.linalg.svd(x, full_matrices=False)
    rank = int(np.sum(singular > singular[0]*1e-12)) if len(singular) else 0
    basis = vt[:rank]
    beta = basis.T @ ((u[:,:rank].T @ y)/singular[:rank]) if rank else np.zeros(len(columns))
    return {'status':'FITTED', 'columns':columns, 'coefficients_m':beta.tolist(),
            'rowspace_basis':basis.tolist(), 'rank':rank, 'parameter_count':len(columns),
            'singular_values':singular.tolist(), 'training_path_count':len(rows),
            'training_contrast_rms_m':float(np.sqrt(np.mean((y-x@beta)**2)))}


def predict_contrast(fit, station, held_direction, remaining_directions):
    """Predict target minus remaining-reference mean, not an absolute site bias."""
    if fit['status'] != 'FITTED':
        return {'status':fit['status']}
    if not remaining_directions:
        return {'status':'INSUFFICIENT_REMAINING_GEOMETRY'}
    keys = [station+'/'+axis for axis in 'ENU']
    if not set(keys) <= set(fit['columns']):
        return {'status':'UNSEEN_STATION'}
    vector = np.zeros(len(fit['columns']))
    contrast = np.asarray(held_direction)-np.mean(remaining_directions, axis=0)
    vector[[fit['columns'].index(k) for k in keys]] = contrast
    basis = np.asarray(fit['rowspace_basis']).reshape(fit['rank'], len(vector))
    defect = float(np.linalg.norm(vector-(vector@basis.T)@basis))
    if defect > 1e-9*max(1.,np.linalg.norm(vector)):
        return {'status':'UNIDENTIFIABLE_PREDICTION', 'rowspace_defect':defect}
    return {'status':'PREDICTED', 'prediction_m':float(vector@fit['coefficients_m']),
            'rowspace_defect':defect}


def moments(values):
    a = np.asarray(values, float)
    return {'count':len(a), 'mean_m':float(a.mean()) if len(a) else None,
            'rms_m':float(np.sqrt(np.mean(a*a))) if len(a) else None,
            'max_abs_m':float(abs(a).max()) if len(a) else None}


def summarize(rows, stations):
    paired = [r for r in rows if r['direction']['status']=='PREDICTED']
    def scores(selected):
        return {'count':len(selected),
                'zero':moments([r['zero_error_m'] for r in selected]),
                'direction':moments([r['direction']['error_m'] for r in selected])}
    return {'slot_count':len(rows), 'status_counts':dict(Counter(r['direction']['status'] for r in rows)),
            'paired':scores(paired), 'per_station':{
                s:scores([r for r in paired if r['station']==s]) for s in stations}}


def evaluate(context, codes, model, direction, zero_report, progress=None, *, excluded_references=None):
    plan, original, ctx, _, _, _, baseline = context
    blocks = groups(baseline['rows'])
    refs_by_block = {key:tuple(sorted(baseline['rows'][i]['reference'] for i in ix))
                     for key,ix in blocks.items()}
    train_times = [t for t in ctx.times if t < original['training_before_gpst_s']]
    zero_beta = dict.fromkeys(original['references'], 0.)
    # Identical reference subsets use identical calibration, even across folds.
    calibration_cache = {}
    rows, fits = [], []
    exclusions = original['references'] if excluded_references is None else excluded_references
    if not set(exclusions) <= set(original['references']) or len(set(exclusions)) != len(exclusions):
        raise ValueError('unknown or duplicate reference fold')
    for excluded in exclusions:
        training, failures = [], []
        for station in original['stations']:
            for t in train_times:
                refs = tuple(sv for sv in refs_by_block[station,t] if sv != excluded)
                key = station,t,refs
                try:
                    if key not in calibration_cache:
                        calibration_cache[key] = pseudo.receiver_clock(
                            codes[station,t],refs,excluded,
                            lambda sv,code,clock:model(station,t,sv,code,clock),zero_beta,plan)
                    cal = calibration_cache[key]
                    if cal['status'] != 'EVALUATED':
                        failures.append({'station':station,'time_s':t,**cal})
                        continue
                    block = [{'station':station,'time_s':t,'reference':sv,'residual_m':value,
                              'los_enu':direction(station,t,sv).tolist()}
                             for sv,value in zip(refs,cal['residuals_m'],strict=True)]
                    training.extend(block)
                except (ValueError,KeyError,IndexError) as error:
                    failures.append({'station':station,'time_s':t,'status':'MODEL_FAILURE','reason':str(error)})
        fit = fit_direction(training) if not failures else {'status':'TRAINING_BLOCK_FAILURE','columns':[]}
        fits.append({'pseudo_target':excluded,**fit,'failed_blocks':failures})
        # Only now open later-time pseudo-target errors from the historical report.
        for old in zero_report['rows']:
            if old['pseudo_target'] != excluded:
                continue
            station,t = old['station'],old['time_s']
            zero = old['models'].get('zero',{})
            row = {'pseudo_target':excluded,'station':station,'time_s':t,
                   'zero_status':zero.get('status',old['status']),'zero_error_m':None}
            if row['zero_status'] != 'EVALUATED':
                row['direction'] = {'status':row['zero_status']}
            else:
                try:
                    refs = [sv for sv in refs_by_block[station,t] if sv != excluded]
                    held = direction(station,t,excluded)
                    prediction = predict_contrast(fit,station,held,
                        [direction(station,t,sv) for sv in refs])
                    if prediction['status']=='PREDICTED':
                        local = np.asarray([r['los_enu'] for r in training if r['station']==station])
                        prediction['nearest_training_angle_deg'] = float(np.degrees(np.arccos(
                            np.clip(np.max(local@held),-1.,1.))))
                        prediction['error_m'] = zero['error_m']-prediction['prediction_m']
                    row['direction'] = prediction
                except (ValueError,KeyError,IndexError) as error:
                    row['direction'] = {'status':'MODEL_FAILURE','reason':str(error)}
                row['zero_error_m'] = zero['error_m']
            rows.append(row)
        if progress:
            progress({'pseudo_target':excluded,'training':fit['status'],
                'rank':fit.get('rank'), 'test':dict(Counter(
                    r['direction']['status'] for r in rows if r['pseudo_target']==excluded))})
    return {'fits':fits,'rows':rows,'unique_training_calibration_blocks':len(calibration_cache),
            'summary':summarize(rows,original['stations'])}


def mode_projection(rows, stations, weights, references, times):
    weights = np.asarray(weights, float)
    if len(weights)!=len(stations) or abs(weights.sum())>1e-12 or not np.isclose(np.linalg.norm(weights),1.):
        raise ValueError('unit zero-mean station contrast required')
    index = {(r['pseudo_target'],r['time_s'],r['station']):r for r in rows}
    if len(index) != len(rows):
        raise ValueError('duplicate pseudo-target station/time row')
    blocks = []
    for sv in references:
        for t in times:
            selected = [index[sv,t,s] for s in stations]
            bad = [s for s,r in zip(stations,selected) if r['direction']['status']!='PREDICTED']
            row = {'pseudo_target':sv,'time_s':t,'status':'INSUFFICIENT_STATION_COVERAGE' if bad else 'EVALUATED',
                   'unavailable_stations':bad}
            if not bad:
                row.update(zero_m=float(weights @ [r['zero_error_m'] for r in selected]),
                    direction_m=float(weights @ [r['direction']['error_m'] for r in selected]))
            blocks.append(row)
    good = [r for r in blocks if r['status']=='EVALUATED']
    return {'stations':stations,'unit_station_weights':weights.tolist(),'blocks':blocks,
            'status_counts':dict(Counter(r['status'] for r in blocks)),
            'supported_references':dict(Counter(r['pseudo_target'] for r in good)),
            'zero':moments([r['zero_m'] for r in good]),
            'direction':moments([r['direction_m'] for r in good])}


def run():
    context = pseudo.inputs(PLAN_SHA)
    _, original, ctx, _, _, _, baseline = context
    files = {'baseline':BASE/'results/day_reference_v1.json',
             'pseudo_target':BASE/'results/pseudotarget_v1.json',
             'mode':BASE/'results/g12_full_hour_v1.json'}
    raw = {k:p.read_bytes() for k,p in files.items()}
    old = json.loads(raw['pseudo_target'])
    test_times = [t for t in ctx.times if t >= original['training_before_gpst_s']]
    keys = [(r['pseudo_target'],r['station'],r['time_s']) for r in old['rows']]
    expected = {(sv,s,t) for sv in original['references'] for s in original['stations'] for t in test_times}
    if (old['real_target_orbit_accessed'] or old['real_target_fit'] or
            old['baseline_plan'] != original or old['plan'] != context[0]
            or old['test_times_s'] != test_times or len(keys)!=len(set(keys)) or set(keys)!=expected):
        raise ValueError('historical pseudo-target boundary differs')
    codes, model = pseudo.environment(context)
    direction = reference_geometry.environment(context)
    result = evaluate(context,codes,model,direction,old,lambda r:print(json.dumps(r),flush=True))
    # This exposed G12 sensitivity defines a diagnostic score only; it never trains a fit.
    mode = json.loads(raw['mode'])
    if mode['target_orbit_used'] or mode['oracle_error_used'] or mode['new_confirmation']:
        raise ValueError('G12 diagnostic mode boundary differs')
    stations = mode['global_stations']
    vector = mode['combined']['code_phase']['constant']['weakest_contrast_direction']
    weights = helmert(len(stations),full=False).T @ vector
    projection = mode_projection(result['rows'],stations,weights,original['references'],old['test_times_s'])
    return native({'schema':'exposed-reference-bias-transfer-v1',
        'scope':'Exposed reference-only directional error-law transfer, with each pseudo-target excluded from first-half calibration and fitting. Fixed zero clock datum; known reference geometry and shared CODE products. No physical bias/position bound or new confirmation.',
        'real_target_measurements_used_for_calibration':False,'real_target_orbit_used':False,
        'target_mode_used_only_for_diagnostic_projection':True,'target_fit_performed':False,
        'physical_covariance_qualified':False,'production_floors_changed':False,'new_confirmation':False,
        'training_before_gpst_s':original['training_before_gpst_s'],
        'training_times_s':[t for t in ctx.times if t<original['training_before_gpst_s']],
        'test_times_s':old['test_times_s'],'references':original['references'],'stations':original['stations'],
        'input_sha256':{k:digest(v) for k,v in raw.items()},'reference_product_sha256':baseline['product_sha256'],
        'source_sha256':{p.name:digest(p.read_bytes()) for p in [Path(__file__),Path(reference_geometry.__file__)]},
        'mode_projection':projection,**result})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; retain previous reports')
    result = run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        f.write(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
