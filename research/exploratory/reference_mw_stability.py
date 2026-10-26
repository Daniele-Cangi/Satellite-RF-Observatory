"""Reference-only MW block stability and descriptive nonseparable changes.

No target input is opened. Prediction uses prefix data only. Post-score graph
projection diagnoses changes; it neither repairs observations nor sets integers.
"""
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from scipy.stats import t as student_t

from . import integer_phase_feasibility as base

BLOCK_S = 300.
STEP_S = 30.


def complete_blocks(points):
    """Absolute 300 s bins, exactly ten distinct 30 s endpoints per mean."""
    bins = {}
    for time,value in points:
        if not np.isfinite([time,value]).all() or time % STEP_S:
            raise ValueError('finite on-grid MW samples required')
        start = math.floor(time/BLOCK_S)*BLOCK_S
        own = bins.setdefault(start,{})
        if time in own:
            raise ValueError('duplicate block epoch')
        own[time] = value
    full,partial = [],[]
    for start,own in sorted(bins.items()):
        if sorted(own) == [start+i*STEP_S for i in range(10)]:
            full.append({'start_s':start,'mean_cycles':float(np.mean(list(own.values()))),'count':10})
        else:
            partial.append({'start_s':start,'count':len(own)})
    return full,partial


def block_model(blocks):
    """Nominal Student prediction for one FUTURE block, no physical coverage.

    Requires IID Gaussian stationary block means, an unqualified assumption.
    A constant DD bias remains confounded with the wide-lane integer.
    """
    n = len(blocks)
    if n<2:
        return {'status':'INSUFFICIENT_COMPLETE_PREFIX_BLOCKS','block_count':n}
    y = np.array([b['mean_cycles'] for b in blocks])
    sd = float(np.std(y,ddof=1))
    if not np.isfinite(sd) or sd<=0.:
        return {'status':'UNRESOLVED_PREFIX_SCATTER','block_count':n}
    halfwidth = float(student_t.ppf(.975,n-1)*sd*math.sqrt(1.+1./n))
    return {'status':'CONDITIONAL_BLOCK_PREDICTION','block_count':n,'dof':n-1,
        'mean_cycles':float(y.mean()),'block_sd_cycles':sd,
        'future_block_halfwidth_95_cycles':halfwidth,
        'iid_block_mean_sigma_cycles':sd/math.sqrt(n),
        'absolute_link_bias_bounded':False,'physical_coverage_qualified':False}


def dd_value(indices,stations,satellites,time):
    s,u = stations;q,p = satellites
    return math.fsum(sign*base.wide_lane(indices[a,b,time]['fields'])
                     for sign,(a,b) in zip((1,-1,-1,1),((s,q),(u,q),(s,p),(u,p)),strict=True))


def prepare(reference):
    """Reuse the existing admitted raw/GF prefix and all 4,851 DD controls."""
    cohort = reference['cohorts']['day']
    # The target map has no payload and no file access. The reused routine
    # filters forbidden identities before any RF/time arithmetic.
    dummy = {'stations':{s:{'status':'TARGET_NOT_READ'} for s in cohort['plan']['stations']}}
    frozen,indices = base.prepare(reference,dummy)
    frozen['records'] = [r for r in frozen['records'] if r['role']=='REFERENCE_CONTROL']
    frozen['inventory'] = {k:v for k,v in frozen['inventory'].items() if k.endswith('/reference')}
    frozen.update(schema='reference-mw-stability-predictions-v1',target_raw_observations_used=False,
                  block_s=BLOCK_S,block_model_physical_coverage_qualified=False)
    for record in frozen['records']:
        if record['status'] not in ('CONDITIONAL_WIDE_LANE_HYPOTHESES','NO_CONTIGUOUS_HELD_SUPPORT'):
            continue
        start,stop = record['training_start_s'],record['training_stop_s']
        points = [(t,dd_value(indices,record['stations'],record['satellites'],t))
                  for t in np.arange(start,stop+STEP_S,STEP_S)]
        blocks,partial = complete_blocks(points)
        record.update(prefix_blocks=blocks,partial_prefix_blocks=partial,block_model=block_model(blocks))
    return frozen,indices


def profile_changes(rows):
    """Unweighted descriptive receiver+satellite projection, no clock metrology.

    Gauge-independent fitted rows/residuals only. A nonseparable change survives
    this projection; leave-one-link-out residual is undefined on graph bridges.
    """
    if not rows:
        return {'status':'NO_COMPLETE_LINK_BLOCKS','rows':[]}
    stations = sorted({r['station'] for r in rows})
    satellites = sorted({r['reference'] for r in rows})
    design = np.zeros((len(rows),len(stations)+len(satellites)))
    for i,r in enumerate(rows):
        design[i,stations.index(r['station'])] = 1.
        design[i,len(stations)+satellites.index(r['reference'])] = 1.
    y = np.array([r['change_cycles'] for r in rows])
    u,s,_ = np.linalg.svd(design,full_matrices=False)
    rank = int(np.sum(s>np.finfo(float).eps*max(design.shape)*s[0]))
    u = u[:,:rank]
    predicted = u@(u.T@y)
    residual = y-predicted
    leverage = np.sum(u*u,axis=1)
    output = [{**r,'separable_change_cycles':float(p),'nonseparable_change_cycles':float(e),
        'leave_one_link_out_error_cycles':float(e/(1.-h)) if 1.-h>1e-10 else None,
        'leverage':float(h)} for r,p,e,h in zip(rows,predicted,residual,leverage,strict=True)]
    return {'status':'DESCRIPTIVE_CHANGE_PROJECTION','rank':rank,'parameter_count':design.shape[1],
        'independent_cycle_contrasts':len(rows)-rank,'rows':output,
        'orthogonality_inf':float(np.max(abs(design.T@residual))),
        'not_unique_physical_fault_attribution':True}


def diagnose_changes(frozen,indices):
    """Post-score block changes; never a source of new predictions or masks."""
    cut = frozen['cut_gpst_s']
    if not indices:
        return {'status':'NO_ADMITTED_REFERENCE_OBSERVATIONS','blocks':[],
                'post_score_only':True,'observations_repaired':False}
    links = sorted({(s,q) for s,q,t in indices})
    last = max(t for s,q,t in indices)
    baseline = {}
    for s,q in links:
        tags = [cut-BLOCK_S+i*STEP_S for i in range(10)]
        if all((s,q,t) in indices for t in tags):
            baseline[s,q] = float(np.mean([base.wide_lane(indices[s,q,t]['fields']) for t in tags]))
    blocks = []
    for start in np.arange(cut,last+STEP_S,BLOCK_S):
        tags = [start+i*STEP_S for i in range(10)]
        rows = []
        for s,q in links:
            if (s,q) in baseline and all((s,q,t) in indices for t in tags):
                mean = float(np.mean([base.wide_lane(indices[s,q,t]['fields']) for t in tags]))
                rows.append({'station':s,'reference':q,'prefix_last_block_mean_cycles':baseline[s,q],
                             'held_block_mean_cycles':mean,'change_cycles':mean-baseline[s,q]})
        blocks.append({'start_s':float(start),**profile_changes(rows)})
    return {'prefix_baseline_start_s':cut-BLOCK_S,'block_s':BLOCK_S,
        'support_rule':'complete raw/flag-valid blocks only; held GF not used to remove changes',
        'link_count_with_prefix_baseline':len(baseline),'blocks':blocks,
        'post_score_only':True,'observations_repaired':False}


def score(frozen,indices):
    native = base.score(frozen,indices)
    results = []
    for record,old in zip(frozen['records'],native['records'],strict=True):
        result = {k:record[k] for k in ('stations','satellites','status')}
        if record['status']=='CONDITIONAL_WIDE_LANE_HYPOTHESES':
            points = list(zip(record['future_tags'],old['held_values_cycles'],strict=True))
            blocks,partial = complete_blocks(points)
            model = record['block_model']
            result.update(block_model_status=model['status'],partial_held_blocks=partial,held_blocks=blocks)
            if model['status']=='CONDITIONAL_BLOCK_PREDICTION':
                for b in blocks:
                    error = b['mean_cycles']-model['mean_cycles']
                    b.update(error_cycles=error,within_nominal_95=bool(abs(error)<=model['future_block_halfwidth_95_cycles']))
        results.append(result)
    models = [r for r in results if r.get('block_model_status')=='CONDITIONAL_BLOCK_PREDICTION']
    blocks = [b for r in models for b in r['held_blocks']]
    agreements = sum(math.floor(r['mean_cycles']+.5)==p['comparison']['integer_hypothesis']
                     for p,r in zip(frozen['records'],native['records'],strict=True) if 'count' in r)
    summary = {'all_reference_configurations':len(results),
        'original_reference_controls':native['summary']['REFERENCE_CONTROL'],
        'original_integer_held_mean_agreements':agreements,
        'block_model_statuses':dict(Counter(r.get('block_model_status','NO_HELD_BASELINE') for r in results)),
        'block_models_with_held_blocks':sum(bool(r['held_blocks']) for r in models),
        'nominal_interval_scored_blocks':len(blocks),
        'nominal_interval_covered_blocks':sum(b['within_nominal_95'] for b in blocks),
        'overlapping_DD_blocks_not_independent':True,'physical_coverage_qualified':False}
    return {'schema':'reference-mw-stability-scores-v1','summary':summary,'records':results,
            'native_scalar_scores':native,'integer_fix_admitted':False,'target_raw_observations_used':False}


def run(reference_path,output):
    if reference_path.resolve()!=base.REFERENCE.resolve():
        raise ValueError('use the retained reference-only extract')
    raw = reference_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest!=base.EXPECTED[0]:
        raise ValueError('reference input hash mismatch')
    output.mkdir(exist_ok=False)
    frozen,indices = prepare(json.loads(raw))
    sources = ['research/exploratory/reference_mw_stability.py','research/exploratory/real_phase.py',
        'research/exploratory/integer_phase_feasibility.py','research/kinematic/gnss_combinations.py',
        'research/kinematic/phase_continuity.py','research/kinematic/doppler.py','research/kinematic/receiver_time.py',
        'requirements-positioning.txt']
    frozen.update(input_sha256=digest,implementation_revision=subprocess.check_output(
        ['git','rev-parse','HEAD'],cwd=base.ROOT,text=True).strip(),
        source_sha256={p:hashlib.sha256((base.ROOT/p).read_bytes()).hexdigest() for p in sources},
        predictions_fixed_before_held_scoring=True,prospective_confirmation=False)
    base.write(output/'predictions-before-scoring.json.gz',frozen)
    scored = score(frozen,indices)
    base.write(output/'scores.json.gz',scored)
    base.write(output/'post-score-changes.json.gz',diagnose_changes(frozen,indices))
    print(json.dumps(scored['summary']),flush=True)
    return scored
