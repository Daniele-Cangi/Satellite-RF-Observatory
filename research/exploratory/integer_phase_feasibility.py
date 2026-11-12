"""Exposed GPS raw-phase wide-lane feasibility; never an integer fixing API.

No product, target state, geometry correction or orbital solution is read.
All four endpoints share signals C1C/C2W/L1C/L2W. DD removes separable biases;
an arbitrary remaining link bias destroys integer identifiability.
"""
from collections import Counter
from itertools import combinations
import gzip
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from research.kinematic import gnss_combinations as combo, phase_continuity

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT/'research/exploratory/inputs/real_phase/observations_gps_only_v2.json'
TARGET = ROOT/'research/exploratory/inputs/real_phase/g12_target_phase_v2.json'
EXPECTED = ('26152824138bb58c7af7f1db69019704e341eb87a7334a93fb33f9d345d44f92',
            '13a7ef0212957b876b02099f4d25a658d3211ef8698988dd5b72735ced24a14a')
WIDE_M = combo.C/(combo.F1_HZ-combo.F2_HZ)
NARROW_M = combo.C/(combo.F1_HZ+combo.F2_HZ)
MW_METRE_ROW = combo.transform()[3]/WIDE_M
MW_FIELD_ROW = MW_METRE_ROW*np.array([1.,1.,combo.C/combo.F1_HZ,combo.C/combo.F2_HZ])


def wide_lane(fields):
    """Uncorrected raw MW in wide-lane cycles, preserving its lattice.

    No C1C-to-C1W translation or target OSB is applied. Unknown code/phase
    hardware and multipath contributions remain explicit physical limitations.
    """
    x = np.asarray(fields, float)
    if x.shape != (4,) or not np.isfinite(x).all() or np.any(x == 0.) or np.any(x[:2] < 0.):
        raise ValueError('four finite nonzero raw fields and positive codes required')
    return math.fsum(float(a*b) for a,b in zip(MW_FIELD_ROW,x,strict=True))


def scalar_comparison(values, variance):
    """Exact 1-D equal-weight float and lattice alternatives, conditional IID.

    No physical uncertainty is inferred from the scatter. Candidate selection
    uses training only; free residual bias makes EVERY integer equally fitted.
    """
    y = np.asarray(values,float)
    if y.ndim != 1 or not len(y) or not np.isfinite(y).all() or not np.isfinite(variance) or variance <= 0.:
        raise ValueError('finite nonempty training vector and positive variance required')
    mean = float(np.mean(y))
    center = math.floor(mean)
    nearby = sorted(range(center-1,center+3),key=lambda n:((n-mean)**2,n))
    best,second = nearby[:2]
    scale = len(y)/variance
    radius = 2.*math.sqrt(variance/len(y))
    return {'training_count':len(y),'float_cycles':mean,'integer_hypothesis':best,
        'second_integer_hypothesis':second,
        'integer_minus_float_training_delta_q':scale*(best-mean)**2,
        'second_minus_best_training_delta_q':scale*((second-mean)**2-(best-mean)**2),
        'conditional_iid_mean_sigma_cycles':math.sqrt(variance/len(y)),
        'integer_interval_delta_q_le_4':[math.ceil(mean-radius),math.floor(mean+radius)],
        'training_scatter_rms_cycles':float(np.sqrt(np.mean((y-mean)**2))),
        'free_link_bias_identifiability':'ALL_INTEGERS_EQUIVALENT',
        'free_bias_for_best_cycles':mean-best,
        'free_bias_for_second_cycles':mean-second,
        'integer_fix_admitted':False}


def header_status(item):
    if item.get('status') != 'PARSED':
        return item.get('reason',item.get('status','UNSUPPORTED'))
    # Extractor has already applied declared scale factors. Do not apply them
    # again. Nonzero phase alignment is outside this minimal feasibility law.
    shifts = item.get('phase_shifts',{})
    if set(shifts) != {'L1C','L2W'}:
        return 'MISSING_PHASE_ALIGNMENT'
    if any(float(v['default_cycles']) != 0. or any(float(x) != 0. for x in v['satellite_overrides_cycles'].values())
           for v in shifts.values()):
        return 'NONZERO_PHASE_ALIGNMENT_UNSUPPORTED'
    legacy = item.get('legacy',{})
    if legacy.get('numeric_phase_unit') != 'carrier_cycles' or any(
            v != 1 for v in legacy.get('default_ambiguity_wavelength_divisor',{}).values()) or any(
            v != 1 for a in legacy.get('satellite_overrides',{}).values() for v in a.values()):
        return 'UNSUPPORTED_WAVELENGTH_FACTOR'
    return 'SUPPORTED_RAW_SIGNALS'


def prepare(reference, target):
    """Freeze DD hypotheses before any post-cut RF values or GF are used."""
    cohort = reference['cohorts']['day']
    plan = cohort['plan']
    if plan['target_excluded'] != 'G12' or 'G12' in plan['references']:
        raise ValueError('G12 must be excluded from reference identity allowlist')
    stations,refs = plan['stations'],plan['references']
    cut,step = plan['training_before_gpst_s'],plan['step_s']
    tags = [plan['start_gpst_s']+i*step for i in range(plan['samples'])]
    if step != phase_continuity.STEP_S or tags != sorted(set(tags)) or cut not in tags:
        raise ValueError('supported unique 30 s grid and boundary required')
    indices,inventory,training = {},{},[]
    # Input dictionaries contain observations/header metadata only. Iterate an
    # identity allowlist; unlisted/forbidden rows are skipped before RF access.
    for station in stations:
        for kind,item,allowed,label in (
            ('reference',cohort['stations'][station],set(refs),'reference'),
            ('target',target['stations'][station],{'G12'},'target')):
            status = header_status(item)
            counts = Counter()
            if status == 'SUPPORTED_RAW_SIGNALS':
                previous,segments = {},Counter()
                for row in item['rows']:
                    q = row[label]
                    if q not in allowed:
                        continue
                    t = row['time_s']
                    if t not in tags:
                        continue
                    key = station,q,t
                    if key in indices:
                        raise ValueError('duplicate admitted raw epoch')
                    if row['status'] != 'AVAILABLE' or row.get('lli') not in (['0','0'],[' ',' '],['0',' '],[' ','0']):
                        counts['REJECTED_FLAGS_OR_FIELDS'] += 1
                        continue
                    indices[key] = row
                    counts['AVAILABLE'] += 1
                    if t >= cut:
                        continue  # No held numeric phase/GF for training/support.
                    if previous.get(q) != t-step:
                        segments[q] += 1
                    previous[q] = t
                    fields = row['fields']
                    value = wide_lane(fields)
                    gf = float(fields[2])*combo.C/combo.F1_HZ-float(fields[3])*combo.C/combo.F2_HZ
                    training.append({'station':station,'reference':q,'time_s':t,
                        'segment':f'{station}/{q}/{segments[q]}','geometry_free_phase_m':gf,'mw_cycles':value})
            inventory[station+'/'+kind] = {'header_status':status,'counts':dict(counts)}
    training = phase_continuity.segment(sorted(training,key=lambda r:(r['station'],r['reference'],r['time_s'])))
    train = {(r['station'],r['reference'],r['time_s']):r for r in training}
    raw_variance = combo.assumed_endpoint_covariance()
    dd_variance = 4.*float(MW_METRE_ROW@raw_variance@MW_METRE_ROW)
    records = []
    # All receiver pairs and all reference/reference pairs are controls. Also
    # retain every G12/reference pair; no residual-based configuration selection.
    pairs = list(combinations(sorted(refs),2))+[('G12',q) for q in sorted(refs)]
    for s,u in combinations(stations,2):
        for q,p in pairs:
            endpoints = [(s,q),(u,q),(s,p),(u,p)]
            record = {'stations':[s,u],'satellites':[q,p],
                'role':'G12' if q=='G12' else 'REFERENCE_CONTROL','status':'NO_PREFIX_AT_BOUNDARY'}
            arc,previous_segment = [],None
            for t in (v for v in tags if v<cut):
                rows = [train.get((a,b,t)) for a,b in endpoints]
                if any(r is None for r in rows):
                    arc,previous_segment = [],None
                    continue
                segment = tuple(r['segment'] for r in rows)
                if segment != previous_segment:
                    arc = []
                previous_segment = segment
                value = math.fsum(sign*r['mw_cycles'] for sign,r in zip((1,-1,-1,1),rows,strict=True))
                arc.append((t,value))
            if len(arc)>=2:
                record.update(status='CONDITIONAL_WIDE_LANE_HYPOTHESES',
                    training_start_s=arc[0][0],training_stop_s=arc[-1][0],
                    comparison=scalar_comparison([v for _,v in arc],dd_variance),future_tags=[])
                for t in (v for v in tags if v>=cut):
                    if any((a,b,t) not in indices for a,b in endpoints):
                        break  # No bridge/restart using held phase or GF.
                    record['future_tags'].append(t)
                if not record['future_tags']:
                    record['status']='NO_CONTIGUOUS_HELD_SUPPORT'
            records.append(record)
    return {'schema':'integer-phase-feasibility-v1','target':'G12','cut_gpst_s':cut,
        'training_rule':'time < cut; latest GF-contiguous prefix ending at cut-step',
        'held_rule':'time >= cut; stop at first missing/flagged endpoint; held GF unused',
        'raw_signal_order':['C1C','C2W','L1C','L2W'],'wide_lane_m':WIDE_M,'narrow_lane_m':NARROW_M,
        'raw_endpoint_covariance_m2':raw_variance.tolist(),'dd_variance_cycles2':dd_variance,
        'physical_covariance_qualified':False,'target_products_used':False,
        'target_raw_observations_used':True,'target_state_estimated':False,
        'integer_fix_admitted':False,'inventory':inventory,'records':records},indices


def score(frozen,indices):
    """Held descriptive errors of the frozen float and integer hypotheses.

    Overlapping DD configurations share endpoints: do not pool their likelihoods
    or count their hypothesis comparisons as independent scientific trials.
    """
    results = []
    for record in frozen['records']:
        result = {k:record[k] for k in ('stations','satellites','role','status')}
        if record['status']=='CONDITIONAL_WIDE_LANE_HYPOTHESES':
            s,u = record['stations'];q,p = record['satellites']
            values = [math.fsum(sign*wide_lane(indices[a,b,t]['fields'])
                       for sign,(a,b) in zip((1,-1,-1,1),((s,q),(u,q),(s,p),(u,p)),strict=True))
                      for t in record['future_tags']]
            c = record['comparison']
            y = np.asarray(values)
            result.update(count=len(y),mean_cycles=float(y.mean()),
                float_rms_cycles=float(np.sqrt(np.mean((y-c['float_cycles'])**2))),
                integer_rms_cycles=float(np.sqrt(np.mean((y-c['integer_hypothesis'])**2))),
                held_minus_training_mean_cycles=float(y.mean()-c['float_cycles']),
                held_values_cycles=values)
        results.append(result)
    summary = {}
    for role in ('G12','REFERENCE_CONTROL'):
        own = [r for r in results if r['role']==role]
        scored = [r for r in own if 'count' in r]
        summary[role] = {'configurations':len(own),'statuses':dict(Counter(r['status'] for r in own)),
            'integer_held_rms_better_count':sum(r['integer_rms_cycles']<r['float_rms_cycles'] for r in scored),
            'scored_configurations':len(scored),'correlated_comparisons_not_independent_trials':True}
    return {'schema':'integer-phase-feasibility-scores-v1','summary':summary,'records':results,
        'integer_fix_admitted':False,'target_state_estimated':False,
        'wide_lane_observes_only_N1_minus_N2':True,
        'equal_integer_shift_IF_phase_m':NARROW_M,
        'free_link_bias_model':'y=N_w+b_dd+error; N_w+k,b_dd-k is exactly invariant'}


def write(path,value):
    raw = (json.dumps(value,allow_nan=False,separators=(',',':'))+'\n').encode()
    if path.suffix=='.gz':
        raw = gzip.compress(raw,mtime=0)
    with path.open('xb') as handle:
        handle.write(raw)


def run(reference_path,target_path,output):
    """Called by the existing real_phase report CLI; fresh evidence directory."""
    if (reference_path.resolve(),target_path.resolve()) != (REFERENCE.resolve(),TARGET.resolve()):
        raise ValueError('use the two retained exposed raw-phase extracts')
    reference_path,target_path = reference_path.resolve(),target_path.resolve()
    raws = [p.read_bytes() for p in (reference_path,target_path)]
    hashes = [hashlib.sha256(b).hexdigest() for b in raws]
    if tuple(hashes)!=EXPECTED:
        raise ValueError('retained raw-phase input hash mismatch')
    output.mkdir(exist_ok=False)
    frozen,indices = prepare(*(json.loads(raw) for raw in raws))
    sources = ['research/exploratory/integer_phase_feasibility.py','research/exploratory/real_phase.py',
               'research/kinematic/gnss_combinations.py','research/kinematic/phase_continuity.py',
               'research/kinematic/doppler.py','research/kinematic/receiver_time.py']
    frozen.update(input_sha256=dict(zip((p.name for p in (reference_path,target_path)),hashes,strict=True)),
        implementation_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        predictions_fixed_before_held_scoring=True,prospective_confirmation=False)
    write(output/'predictions-before-scoring.json.gz',frozen)
    scored = score(frozen,indices)
    write(output/'scores.json.gz',scored)
    print(json.dumps(scored['summary']),flush=True)
    return scored
