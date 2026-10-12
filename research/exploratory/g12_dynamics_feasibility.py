"""Conditional observability of exposed G12 geometry with shared dynamics.

No dynamic RF fit is performed: evaluate a common trajectory from the first
accepted chronological code-only RF state, not a target orbit product. Profile
all local clock/ground parameters before assessing shared code-bias information.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

import numpy as np
from scipy.linalg import helmert, qr, solve_triangular

from .real_phase import BASE, digest
from .real_target_interval import TAGS, covariance
from .g12_bias_geometry import information_summary, RANK_RTOL
from ..kinematic import orbital_dynamics as dynamics
from ..kinematic.receiver_time import central_jacobian
from ..kinematic.phase_rates import interval_matrix
from ..kinematic.synthetic import native

STATE_SCALE = np.r_[np.full(3,1e7),np.full(3,1e3)]
ACCEPTED = 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'


def eliminate(nuisance, *arrays):
    """QR projection in whitened data space; never subtract normal matrices."""
    nuisance = np.asarray(nuisance,float)
    singular = np.linalg.svd(nuisance,compute_uv=False)
    if len(singular)<nuisance.shape[1] or singular[-1]<=singular[0]*RANK_RTOL:
        raise ValueError('dynamic nuisance geometry is rank deficient')
    q,_ = qr(nuisance,mode='full')
    complement = q[:,nuisance.shape[1]:].T
    return tuple(complement@a for a in arrays)


def arc_geometry(case, positions, model, trajectory, trajectories, steps, epoch):
    """Local clock/ground freedom remains unchanged; target acceleration is dynamic."""
    stations = case['stations']
    n = len(stations)
    old = case['fits'][model]
    end = case['start_gpst_s']+60
    xyz = np.array([positions[s][(end-36000)//30] for s in stations])
    local = np.r_[np.asarray(old['state'])[9:11],np.asarray(old['receiver_clocks']).ravel(),np.zeros(3*n)]
    scales = np.r_[1e5,10.,np.tile([1000.,1.],n),np.full(3*n,1e5)]
    difference = interval_matrix(TAGS,n)
    phase = model=='code_phase'
    whole,code_cov = covariance(n)
    cov = whole if phase else code_cov
    chol = np.linalg.cholesky(cov)
    def prediction(curve,physical):
        codes = dynamics.predict_codes(curve,end-epoch,TAGS,
                    xyz+physical[2+2*n:].reshape(n,3),physical[2:2+2*n].reshape(n,2),physical[:2]).ravel()
        return np.r_[codes,difference@codes if phase else [],physical[2:]]
    value = prediction(trajectory,local)
    # Independent calibration and terrestrial-coordinate measurement rows:
    # exactly the old data ordering, clock and ground prior uncertainties.
    nuisance = central_jacobian(lambda z:prediction(trajectory,z*scales),local/scales)
    # b0 is exactly additive, and cancels exactly in carrier increments. A
    # differenced ~25 Mm code must not create spurious information on its gauge.
    nuisance[:,0] = 0.
    nuisance[:3*n,0] = -scales[0]
    bias = np.zeros((len(value),5))
    basis = helmert(6,full=False).T
    global_names = ('ALGO00CAN','DRAO00CAN','AREQ00PER','BOGT00COL','STJO00CAN','BRAZ00BRA')
    mapped = basis[[global_names.index(s) for s in stations]]
    bias[:3*n] = np.tile(mapped,(3,1))
    slope = bias.copy()
    # Drift is code-only: no artificial code-bias drift in carrier increments.
    slope[:3*n] *= np.repeat(end-epoch+TAGS,n)[:,None]
    weighted = lambda x:solve_triangular(chol,x,lower=True)
    projected = {}
    for step in steps:
        plus,minus = trajectories[step]
        state = np.column_stack([(prediction(a,local)-prediction(b,local))/(2*step)
                                 for a,b in zip(plus,minus,strict=True)])
        state,b,drift = eliminate(weighted(nuisance),weighted(state),weighted(bias),weighted(slope))
        projected[str(step)] = {'state':state,'bias':b,'slope':drift}
    return projected


def combine(arcs, *, drift=False):
    states = np.vstack([a['state'] for a in arcs])
    biases = np.vstack([a['bias'] for a in arcs])
    if drift:
        span = max(a['end'] for a in arcs)-min(a['end'] for a in arcs)
        if span<=0:
            raise ValueError('distinct arc endpoints needed for drift')
        centre = np.mean([a['end'] for a in arcs])
        # Epoch shift/normalization keeps the definition identical to old profiles.
        biases = np.column_stack([biases,np.vstack([a['slope']-centre*a['bias'] for a in arcs])/span])
    profile, = eliminate(states,biases)
    return {'arc_count':len(arcs),'shared_trajectory_parameter_count':6,
            'bias_model':'CONSTANT_PLUS_LINEAR_DRIFT' if drift else 'CONSTANT',
            **information_summary(profile)}


def analyze(hour, positions, *, steps=(1e-5,), rtol=2e-12):
    candidates = [c for c in hour['cases'] if c['status']=='EVALUATED'
                  and c['fits']['code_only']['status']==ACCEPTED]
    if not candidates:
        raise ValueError('no accepted RF code anchor')
    anchor = min(candidates,key=lambda c:c['start_gpst_s'])
    epoch = anchor['start_gpst_s']+60
    seed = np.asarray(anchor['fits']['code_only']['state'])[:6]
    endpoints = [c['start_gpst_s']+60-epoch for c in hour['cases']]
    bounds = (min(-1.,min(endpoints)-62.),max(1.,max(endpoints)+32.))
    models,curves,integration_checks = {},{},{}
    for label,j2 in [('central',0.),('central_j2',dynamics.J2)]:
        trajectory = dynamics.Trajectory(seed,bounds,j2=j2,rtol=rtol)
        curves[label] = trajectory
        tighter = dynamics.Trajectory(seed,bounds,j2=j2,rtol=min(rtol/10,2e-13))
        difference = trajectory(endpoints)-tighter(endpoints)
        integration_checks[label] = {
            'tighter_rtol':min(rtol/10,2e-13),
            'max_endpoint_position_difference_m':float(np.max(np.linalg.norm(difference[:,:3],axis=1))),
            'max_endpoint_velocity_difference_m_s':float(np.max(np.linalg.norm(difference[:,3:],axis=1)))}
        shifted = {}
        for step in steps:
            plus = [dynamics.Trajectory(seed+e,bounds,j2=j2,rtol=rtol) for e in np.diag(STATE_SCALE*step)]
            minus = [dynamics.Trajectory(seed-e,bounds,j2=j2,rtol=rtol) for e in np.diag(STATE_SCALE*step)]
            shifted[step] = plus,minus
        retained,arc_profiles,defects = [],{str(s):{'code_only':[],'code_phase':[]} for s in steps},[]
        for case in hour['cases']:
            end = case['start_gpst_s']+60-epoch
            nominal = trajectory(end)
            statuses = {m:v['status'] for m,v in case.get('fits',{}).items()}
            retained.append({'start_gpst_s':case['start_gpst_s'],'status':case['status'],'fits':statuses})
            if case['status']!='EVALUATED':
                continue
            for model,old in case['fits'].items():
                if old['status']!=ACCEPTED:
                    continue
                state = np.asarray(old['state'])
                defect = {'start_gpst_s':case['start_gpst_s'],'model':model,
                    'position_difference_m':float(np.linalg.norm(nominal[:3]-state[:3])),
                    'velocity_difference_m_s':float(np.linalg.norm(nominal[3:]-state[3:6])),
                    'acceleration_difference_m_s2':float(np.linalg.norm(
                        dynamics.acceleration(state[:6],j2=j2)-state[6:9]))}
                defects.append(defect)
                try:
                    profiles = arc_geometry(case,positions,model,trajectory,shifted,steps,epoch)
                    for step,profile in profiles.items():
                        arc_profiles[step][model].append({'end':end,**profile})
                except ValueError as error:
                    defect.update(geometry_status='FAILED',reason=str(error))
                else:
                    defect['geometry_status']='EVALUATED'
            print(label,case['start_gpst_s'],statuses,flush=True)
        expected = Counter(d['model'] for d in defects)
        def summaries(arcs,model):
            if len(arcs)!=expected[model] or not arcs:
                return {'status':'GEOMETRY_BLOCK_FAILURE','expected_arc_count':expected[model],
                        'evaluated_arc_count':len(arcs)}
            return {'status':'EVALUATED','constant':combine(arcs),'linear_drift':combine(arcs,drift=True)}
        models[label] = {'retained_outcomes':retained,'rf_state_discrepancies':defects,
            'geometry_status_counts':dict(Counter(d['geometry_status'] for d in defects)),
            'finite_difference_profiles':{step:{m:summaries(arcs,m)
                    for m,arcs in groups.items()} for step,groups in arc_profiles.items()}}
    comparison = []
    for case,t in zip(hour['cases'],endpoints,strict=True):
        row = {'endpoint_gpst_s':epoch+t,'historical_case_status':case['status'],
            'position_difference_m':float(np.linalg.norm(curves['central'](t)[:3]-curves['central_j2'](t)[:3])),
            'velocity_difference_m_s':float(np.linalg.norm(curves['central'](t)[3:]-curves['central_j2'](t)[3:]))}
        if case['status']=='EVALUATED':
            stations = case['stations']
            xyz = np.array([positions[s][(epoch+t-36000)//30] for s in stations])
            old = case['provisional_code_fit']
            codes = [dynamics.predict_codes(curves[label],t,TAGS,xyz,
                        np.asarray(old['receiver_clocks']),np.asarray(old['state'])[9:11])
                     for label in ['central','central_j2']]
            gap = codes[1]-codes[0]
            row.update(code_difference_m=gap.tolist(),phase_rate_difference_m_s=(np.diff(gap,axis=0)/30.).tolist())
        else:
            row['observable_status']='HISTORICAL_CASE_UNAVAILABLE'
        comparison.append(row)
    return {'anchor_gpst_s':epoch,'anchor_selection':'first chronological accepted code-only RF arc',
            'anchor_rf_state_ecef_m_m_s':seed.tolist(),'integrated_bounds_s':bounds,
            'models':models,'central_vs_j2_same_seed':comparison,'integration_tolerance_comparison':integration_checks}


def run():
    files = {'hour':BASE/'results/g12_full_hour_v1.json',
             'positions':BASE/'inputs/day_reference/positions.json'}
    raw = {k:p.read_bytes() for k,p in files.items()}
    hour,positions = [json.loads(raw[k]) for k in ['hour','positions']]
    if (hour['target_orbit_used'] or hour['oracle_error_used'] or hour['new_confirmation']
            or digest(raw['positions'])!=hour['input_sha256']['positions']):
        raise ValueError('RF geometry or target boundary differs')
    result = analyze(hour,positions,steps=(.5e-5,1e-5,2e-5))
    return native({'schema':'exposed-g12-dynamics-feasibility-v1',
        'scope':'Local information at a propagated RF-only nominal geometry, not a dynamic RF fit. Old conditional independent-arc weights; central/J2 omissions and RF-seed uncertainty unqualified. No physical covariance, accuracy or new confirmation.',
        'target_orbit_used':False,'oracle_error_used':False,'dynamic_rf_fit_performed':False,
        'physical_covariance_qualified':False,'production_floors_changed':False,'new_confirmation':False,
        'input_sha256':{k:digest(v) for k,v in raw.items()},
        'source_sha256':{p.name:digest(p.read_bytes()) for p in [Path(__file__),Path(dynamics.__file__)]},
        'force_model':{'mu_m3_s2':dynamics.MU,'j2':dynamics.J2,'equatorial_radius_m':dynamics.R_EARTH,
                       'constant_spin_rad_s':dynamics.OMEGA,'integrator_rtol':2e-12},
        'baseline_independent_arcs':hour['combined'],**result})


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output exists; retain previous reports')
    result = run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        stream.write(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
