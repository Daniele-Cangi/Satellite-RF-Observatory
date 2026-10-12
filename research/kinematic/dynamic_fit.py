"""Shared dynamic RF trajectory with free constant station-code contrasts.

Initialization consumes only training codes/reference clocks, never a caller's
state. All arc clocks/ground measurements retain their covariance. No bias or
target-state prior, covariance rescaling, silent fallback or outlier removal.
"""
import numpy as np
from scipy.linalg import helmert, qr, solve_triangular
from scipy.stats import chi2

from positioning.solver import solve
from . import orbital_dynamics as dynamics
from .receiver_time import central_jacobian, cholesky_covariance
from .phase_rates import interval_matrix
from .interval_fit import ACCEPTED_CALIBRATIONS

STATE_SCALE = np.r_[np.full(3,1e7),np.full(3,1e3)]
RTOL = 1e-10
# Numerical termination in the fixed, whitened joint-data metric. This is not
# an observation noise floor or residual/model acceptance threshold.
STEP_SIGMA_TOL = 1e-4


def prepare(arcs, phase):
    if not isinstance(phase,bool):
        raise ValueError('include_phase must be boolean')
    if not arcs or any(s not in ACCEPTED_CALIBRATIONS for a in arcs for s in a['calibration_statuses']):
        raise ValueError('qualified reference calibrations required before target decoding')
    names = sorted(set(s for a in arcs for s in a['stations']))
    if len(names)<5:
        raise ValueError('at least five distinct stations required')
    basis = helmert(len(names),full=False).T
    prepared,keys = [],set()
    for a in arcs:
        tags,xyz,clocks,codes = [np.asarray(a[k],float) for k in ['tags_s','stations_m','clock_mean','codes_m']]
        n = len(a['stations'])
        if (not np.isfinite(a['endpoint_gpst_s']) or tags.ndim!=1 or len(tags)<3 or tags[-1]!=0 or np.any(np.diff(tags)<=0)
                or len(set(a['stations']))!=n or n<5 or xyz.shape!=(n,3) or clocks.shape!=(n,2)
                or codes.shape!=(len(tags),n) or len(a['calibration_statuses'])!=n
                or not all(np.isfinite(x).all() for x in [tags,xyz,clocks,codes])):
            raise ValueError('complete finite dynamic RF arc required')
        own = {(s,float(a['endpoint_gpst_s']+t)) for s in a['stations'] for t in tags}
        if keys & own:
            raise ValueError('training arcs reuse target endpoint observations')
        keys |= own
        difference = interval_matrix(tags,n)
        rates = np.asarray(a['rates_m_s'],float) if phase else np.empty((0,n))
        if phase and (rates.shape!=(len(tags)-1,n) or not np.isfinite(rates).all()):
            raise ValueError('finite interval phase rates required')
        observed = np.r_[codes.ravel(),rates.ravel(),clocks.ravel(),np.zeros(3*n)]
        chol = cholesky_covariance(a['covariance'],len(observed))
        local_scale = np.r_[1e5,10.,np.tile([1000.,1.],n),np.full(3*n,1e5)]
        prepared.append({**a,'tags':tags,'xyz':xyz,'clocks':clocks,'codes':codes,'observed':observed,
            'chol':chol,'difference':difference,'local_scale':local_scale,
            'basis':basis[[names.index(s) for s in a['stations']]],'n':n,'phase':phase})
    prepared.sort(key=lambda a:a['endpoint_gpst_s'])
    return prepared,names,basis


def model(curve, arc, local, beta, epoch):
    n = arc['n']
    physical = local*arc['local_scale']
    pair = dynamics.predict_observations(curve,arc['endpoint_gpst_s']-epoch,arc['tags'],
        arc['xyz']+physical[2+2*n:].reshape(n,3),physical[2:2+2*n].reshape(n,2),physical[:2])
    path = pair['code_m'].ravel()
    # Constant code bias is absent from carrier increments.
    code = path+np.tile(arc['basis']@beta,len(arc['tags']))
    return np.r_[code,arc['difference']@path if arc['phase'] else [],physical[2:]],pair


def linearize(global_scaled, locals_scaled, arcs, global_scale, epoch, bounds, j2):
    physical = global_scaled*global_scale
    curve = dynamics.Trajectory(physical[:6],bounds,j2=j2)
    step = 1e-5
    plus = [dynamics.Trajectory(physical[:6]+e,bounds,j2=j2) for e in np.diag(STATE_SCALE*step)]
    minus = [dynamics.Trajectory(physical[:6]-e,bounds,j2=j2) for e in np.diag(STATE_SCALE*step)]
    blocks = []
    for arc,local in zip(arcs,locals_scaled,strict=True):
        value,pair = model(curve,arc,local,physical[6:],epoch)
        residual = solve_triangular(arc['chol'],value-arc['observed'],lower=True)
        jac = central_jacobian(lambda p:model(curve,arc,p,physical[6:],epoch)[0],local)
        count = arc['codes'].size
        jac[:,0] = 0.
        jac[:count,0] = -arc['local_scale'][0]
        # Satellite slope is linear at its transmit GPST, independent of light time.
        jac[:,1] = 0.
        slope = -(pair['transmit_s']-(arc['endpoint_gpst_s']-epoch)).ravel()*arc['local_scale'][1]
        jac[:count,1] = slope
        if arc['phase']:
            jac[count:count+len(arc['difference']),1] = arc['difference']@slope
        state = np.column_stack([(model(a,arc,local,physical[6:],epoch)[0]-
                                  model(b,arc,local,physical[6:],epoch)[0])/(2*step)
                                 for a,b in zip(plus,minus,strict=True)])
        bias = np.zeros((len(value),len(physical)-6))
        bias[:count] = np.tile(arc['basis'],(len(arc['tags']),1))*global_scale[6:]
        weighted = lambda x:solve_triangular(arc['chol'],x,lower=True)
        nuisance = weighted(jac)
        singular = np.linalg.svd(nuisance,compute_uv=False)
        if singular[-1]<=singular[0]*RTOL:
            raise ValueError('rank-deficient local dynamic nuisance design')
        q,r = qr(nuisance,mode='economic')
        global_jac = weighted(np.column_stack([state,bias]))
        blocks.append({'q':q,'r':r,'global':global_jac,'residual':residual,
                       'reduced':global_jac-q@(q.T@global_jac),
                       'reduced_residual':residual-q@(q.T@residual)})
    reduced = np.vstack([b['reduced'] for b in blocks])
    u,singular,vt = np.linalg.svd(reduced,full_matrices=False)
    rank = int(np.sum(singular>singular[0]*RTOL))
    if rank!=len(global_scaled):
        raise ValueError('rank-deficient shared dynamic state/bias design')
    residual = np.concatenate([b['reduced_residual'] for b in blocks])
    delta = -(vt.T/singular)@(u.T@residual)
    local_delta = [solve_triangular(b['r'],-b['q'].T@(b['residual']+b['global']@delta)) for b in blocks]
    step_sigma = float(np.sqrt(sum(np.linalg.norm(b['global']@delta+b['q']@(b['r']@d))**2
                      for b,d in zip(blocks,local_delta,strict=True))))
    covariance = (vt.T/singular**2)@vt*global_scale[:,None]*global_scale[None,:]
    cost = sum(float(b['residual']@b['residual']) for b in blocks)
    return delta,local_delta,cost,covariance,float(singular[0]/singular[-1]),step_sigma


def cost(global_scaled,locals_scaled,arcs,global_scale,epoch,bounds,j2):
    physical = global_scaled*global_scale
    curve = dynamics.Trajectory(physical[:6],bounds,j2=j2)
    value = 0.
    for arc,local in zip(arcs,locals_scaled,strict=True):
        r = solve_triangular(arc['chol'],model(curve,arc,local,physical[6:],epoch)[0]-arc['observed'],lower=True)
        value += float(r@r)
    return value


def initial(arc, seed, all_arcs, global_scale, epoch, bounds, j2):
    q = np.asarray(seed)
    unit = q[:3]-arc['xyz']
    unit /= np.linalg.norm(unit,axis=1)[:,None]
    rates = (arc['codes'][-1]-arc['codes'][-2])/(arc['tags'][-1]-arc['tags'][-2])-arc['clocks'][:,1]
    velocity = np.linalg.lstsq(np.column_stack([unit,np.ones(len(unit))]),rates,rcond=None)[0][:3]
    physical = np.r_[q[:3],velocity,np.zeros(len(global_scale)-6)]
    curve = dynamics.Trajectory(physical[:6],bounds,j2=j2)
    locals_scaled = []
    for a in all_arcs:
        local = np.r_[0.,0.,a['clocks'].ravel(),np.zeros(3*a['n'])]/a['local_scale']
        value,pair = model(curve,a,local,physical[6:],epoch)
        tx = (pair['transmit_s']-(a['endpoint_gpst_s']-epoch)).ravel()
        clock = np.linalg.lstsq(np.column_stack([np.ones(len(tx)),tx]),value[:a['codes'].size]-a['codes'].ravel(),rcond=None)[0]
        local[:2] = clock/a['local_scale'][:2]
        locals_scaled.append(local)
    return physical/global_scale,locals_scaled


def fit(arcs, *, include_phase=True, j2=dynamics.J2, max_iterations=25, progress=None):
    if not isinstance(max_iterations,int) or max_iterations<1:
        raise ValueError('positive integer iteration budget required')
    prepared,names,basis = prepare(arcs,include_phase)
    epoch = prepared[0]['endpoint_gpst_s']
    bounds = (min(a['endpoint_gpst_s']-epoch+a['tags'][0] for a in prepared)-2.,
              max(1.,max(a['endpoint_gpst_s']-epoch+30 for a in prepared)+2.))
    global_scale = np.r_[STATE_SCALE,np.full(len(names)-1,100.)]
    first = prepared[0]
    n = first['n']
    snapshot = solve(first['codes'][-1]-first['clocks'][:,0],first['xyz'],
                     np.asarray(first['covariance'])[first['codes'].size-n:first['codes'].size,
                                                    first['codes'].size-n:first['codes'].size],atmosphere=False)
    candidates,failures = [],[]
    for index,branch in enumerate(snapshot['branches']):
        history = []
        try:
            global_point,locals_point = initial(first,branch['q'],prepared,global_scale,epoch,bounds,j2)
            converged = False
            for iteration in range(max_iterations):
                delta,local_delta,old_cost,cov,condition,step_sigma = linearize(global_point,locals_point,prepared,global_scale,epoch,bounds,j2)
                history.append({'iteration':iteration,'cost':old_cost,'proposed_step_joint_sigma':step_sigma})
                if progress:
                    progress({'branch':index,'iteration':iteration,'cost':old_cost,'step_sigma':step_sigma})
                if step_sigma<STEP_SIGMA_TOL:
                    converged = True
                    break
                accepted = False
                for attempt in range(12):
                    alpha = 2.**(-attempt)
                    proposed = global_point+alpha*delta
                    proposed_locals = [p+alpha*d for p,d in zip(locals_point,local_delta,strict=True)]
                    try:
                        new_cost = cost(proposed,proposed_locals,prepared,global_scale,epoch,bounds,j2)
                    except ValueError as error:
                        history[-1].setdefault('invalid_trials',[]).append({'alpha':alpha,'reason':str(error)})
                        continue
                    if new_cost<=old_cost:
                        accepted = True
                        global_point,locals_point = proposed,proposed_locals
                        break
                if not accepted:
                    raise ValueError('dynamic line search failed')
                history[-1].update(alpha=alpha,new_cost=new_cost)
                if alpha==1. and old_cost-new_cost<1e-9*max(1.,old_cost):
                    converged = True
                    break
            if not converged:
                raise ValueError('dynamic iteration limit reached')
            _,_,final_cost,cov,condition,_ = linearize(global_point,locals_point,prepared,global_scale,epoch,bounds,j2)
            candidates.append({'branch':index,'cost':final_cost,'physical':global_point*global_scale,
                               'locals':[p*a['local_scale'] for p,a in zip(locals_point,prepared,strict=True)],
                               'covariance':cov,'scaled_condition':condition,'history':history})
        except (ValueError,np.linalg.LinAlgError) as error:
            failures.append({'branch':index,'reason':str(error),'history':history})
    if not candidates:
        return {'status':'NUMERICAL_FAILURE','branch_failures':failures,'candidate_count':0}
    candidates.sort(key=lambda c:c['cost'])
    best = candidates[0]
    total_parameters = len(global_scale)+sum(len(a['local_scale']) for a in prepared)
    dof = sum(len(a['observed']) for a in prepared)-total_parameters
    if dof<=0:
        raise ValueError('positive residual degrees of freedom required')
    p_value = float(chi2.sf(best['cost'],dof))
    joint_chol = np.linalg.cholesky(best['covariance'])
    branches = [{'branch':c['branch'],'cost':c['cost'],'state_ecef_m_m_s':c['physical'][:6],
                 'distance_in_global_sigma':float(np.linalg.norm(solve_triangular(joint_chol,c['physical']-best['physical'],lower=True))),
                 'history':c['history']} for c in candidates]
    ambiguous = any(c['cost']-best['cost']<=chi2.ppf(.95,len(global_scale)) and
                    b['distance_in_global_sigma']>.1 for c,b in zip(candidates[1:],branches[1:],strict=True))
    status = 'MODEL_REJECTED' if p_value<.01 else 'AMBIGUOUS' if ambiguous else 'BRANCH_SEARCH_INCOMPLETE' if failures else 'CONDITIONAL_DYNAMIC_MODEL_ACCEPTED'
    return {'status':status,'epoch_gpst_s':epoch,'integrated_bounds_s':bounds,'state_ecef_m_m_s':best['physical'][:6],
            'stations':names,'bias_contrast_coefficients_m':best['physical'][6:],
            'station_code_bias_m':dict(zip(names,basis@best['physical'][6:],strict=True)),
            'arc_parameters':[{'endpoint_gpst_s':a['endpoint_gpst_s'],'stations':a['stations'],
                'satellite_clock':p[:2],'receiver_clocks':p[2:2+2*a['n']].reshape(a['n'],2),
                'station_corrections_m':p[2+2*a['n']:].reshape(a['n'],3)} for a,p in zip(prepared,best['locals'],strict=True)],
            'conditional_global_covariance':best['covariance'],'weighted_residual_cost':best['cost'],
            'residual_dof':dof,'conditional_residual_p':p_value,'parameter_count':total_parameters,
            'scaled_condition':best['scaled_condition'],'branch_failures':failures,'branches':branches,
            'candidate_count':len(candidates),'physical_covariance_qualified':False,'j2':j2,
            'numerical_step_joint_sigma_tolerance':STEP_SIGMA_TOL,'residual_threshold_p':.01}
