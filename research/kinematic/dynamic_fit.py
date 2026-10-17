"""Shared dynamic RF trajectory with free constant station-code contrasts.

Initialization consumes only training codes/reference clocks, never a caller's
state. All arc clocks/ground measurements retain their covariance. No bias or
target-state prior, covariance rescaling, silent fallback or outlier removal.
"""
import numpy as np
from scipy.linalg import block_diag, helmert, qr, solve_triangular
from scipy.stats import chi2

from positioning.solver import solve
from . import orbital_dynamics as dynamics
from .receiver_time import cholesky_covariance
from .phase_rates import interval_matrix
from .interval_fit import ACCEPTED_CALIBRATIONS
from . import clock_observations

STATE_SCALE = np.r_[np.full(3,1e7),np.full(3,1e3)]
RTOL = 1e-10
# Numerical termination in the fixed, whitened joint-data metric. This is not
# an observation noise floor or residual/model acceptance threshold.
STEP_SIGMA_TOL = 1e-4


def prepare(arcs, phase):
    if not isinstance(phase,bool):
        raise ValueError('include_phase must be boolean')
    if not arcs or any(len(a['calibration_statuses'])!=len(a['stations']) or
                       any(s not in ACCEPTED_CALIBRATIONS for s in a['calibration_statuses']) for a in arcs):
        raise ValueError('qualified reference calibrations required before target decoding')
    names = sorted(set(s for a in arcs for s in a['stations']))
    if len(names)<5:
        raise ValueError('at least five distinct stations required')
    basis = helmert(len(names),full=False).T
    wet = ['wet_clock_response' in a for a in arcs]
    if any(wet) and not all(wet):
        raise ValueError('shared wet calibration response required for every arc')
    prepared,keys = [],set()
    for a in arcs:
        tags,xyz,clocks,codes = [np.asarray(a[k],float) for k in ['tags_s','stations_m','clock_mean','codes_m']]
        n = len(a['stations'])
        ns = a.get('satellite_clock_count',2)
        nc = clocks.shape[1] if clocks.ndim==2 else 0
        clock_basis = np.asarray(a.get('receiver_clock_basis',np.column_stack([np.ones(len(tags)),tags])),float)
        if (not np.isfinite(a['endpoint_gpst_s']) or tags.ndim!=1 or len(tags)<3 or tags[-1]!=0 or np.any(np.diff(tags)<=0)
                or len(set(a['stations']))!=n or n<5 or xyz.shape!=(n,3) or nc not in (2,3) or clocks.shape!=(n,nc)
                or ns not in (2,3) or clock_basis.shape!=(len(tags),nc) or not np.isfinite(clock_basis).all()
                or not np.array_equal(clock_basis[:,:2],np.column_stack([np.ones(len(tags)),tags]))
                or nc==3 and ('receiver_clock_basis' not in a or clock_basis[-1,2]!=0)
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
        mw = np.asarray(a.get('mw_rates_m_s',np.empty((0,n))),float)
        if mw.size and (not phase or mw.shape!=rates.shape or not np.isfinite(mw).all()):
            raise ValueError('finite MW interval rates alongside IF phase required')
        observed = np.r_[codes.ravel(),rates.ravel(),mw.ravel(),clocks.ravel(),np.zeros(3*n)]
        chol = cholesky_covariance(a['covariance'],len(observed))
        mask = np.asarray(a.get('phase_increment_mask',np.ones(rates.shape,dtype=bool)))
        if mask.dtype != np.bool_ or mask.shape != rates.shape:
            raise ValueError('boolean mask matching phase interval rates required')
        mw_mask = np.asarray(a.get('mw_increment_mask',mask if mw.size else np.empty(mw.shape,dtype=bool)))
        if mw_mask.dtype!=np.bool_ or mw_mask.shape!=mw.shape:
            raise ValueError('boolean mask matching MW interval rates required')
        mw_drift = a.get('mw_free_drift',False)
        if not isinstance(mw_drift,bool) or mw_drift and not mw.size:
            raise ValueError('MW free drift requires admitted MW observations')
        mw_indices = np.flatnonzero(mw_mask.any(axis=0)) if mw_drift else np.empty(0,dtype=int)
        # Profiling a completely free jump in an increment is exactly its
        # removal with the retained covariance's principal submatrix. In
        # particular a rejected increment must not condition its neighbor's
        # noise through the negative shared-endpoint covariance.
        indices = np.flatnonzero(np.r_[np.ones(codes.size,dtype=bool),mask.ravel(),mw_mask.ravel(),
                                      np.ones(clocks.size+3*n,dtype=bool)])
        if len(indices) != len(observed):
            covariance = np.asarray(a['covariance'])[np.ix_(indices,indices)]
            chol = cholesky_covariance(covariance,len(indices))
        if phase:
            difference = difference[mask.ravel()]
        full_count = len(observed)
        observed = observed[indices]
        response = np.asarray(a.get('wet_clock_response', np.zeros((n,nc))),float)
        if response.shape!=(n,nc) or not np.isfinite(response).all() or wet[0] and 'propagation' not in a:
            raise ValueError('finite station-wise wet clock response and propagation required')
        local_scale = np.r_[[1e5,10.,.1][:ns],np.tile([1000.,1.,1.][:nc],n),
                            np.full(3*n,1e5),np.ones(len(mw_indices))]
        prepared.append({**a,'tags':tags,'xyz':xyz,'clocks':clocks,'codes':codes,'observed':observed,
            'chol':chol,'difference':difference,'local_scale':local_scale,
            'basis':basis[[names.index(s) for s in a['stations']]],'n':n,'phase':phase,
            'ns':ns,'nc':nc,'clock_basis':clock_basis,'wet':wet[0],
            'mw_mask':mw_mask,'mw_indices':mw_indices,'mw':bool(mw.size),
            'observation_indices':indices,'full_observation_count':full_count,
            'wet_response':response,'station_indices':[names.index(s) for s in a['stations']]})
    prepared.sort(key=lambda a:a['endpoint_gpst_s'])
    return prepared,names,basis


def joint_cholesky(prepared, covariance):
    """Select retained data in a full chronological joint covariance."""
    count = sum(a['full_observation_count'] for a in prepared)
    chol = cholesky_covariance(covariance,count)
    indices, at = [], 0
    for a in prepared:
        indices.extend(at+a['observation_indices'])
        at += a['full_observation_count']
    return chol if len(indices)==count else cholesky_covariance(
        np.asarray(covariance)[np.ix_(indices,indices)],len(indices))


def model(curve, arc, local, beta, epoch, *, derivatives=False):
    n,ns,nc = arc['n'],arc['ns'],arc['nc']
    physical = local*arc['local_scale']
    end_ground = ns+nc*n+3*n
    xyz = arc['xyz']+physical[ns+nc*n:end_ground].reshape(n,3)
    pair = clock_observations.predict(curve,arc['endpoint_gpst_s']-epoch,arc['tags'],
        xyz,physical[ns:ns+nc*n].reshape(n,nc),physical[:ns],
        arc['clock_basis'] if nc!=2 else None)
    nb = arc['basis'].shape[1]
    wet = np.asarray(beta[nb:])[arc['station_indices']] if arc['wet'] else None
    if 'propagation' in arc:
        options = {'wet_m':wet} if arc['wet'] else {}
        correction = arc['propagation'](pair,xyz,epoch,derivatives=derivatives,**options)
        delay = np.asarray(correction['delay_m'],float)
        if delay.shape!=pair['code_m'].shape or not np.isfinite(delay).all():
            raise ValueError('finite propagation at the current fitted geometry required')
        pair['code_m'] = pair['code_m']+delay
        if derivatives:
            for key in ['initial_state_derivative','receiver_clock_derivative','station_derivative']:
                jac = np.asarray(correction[key],float)
                if jac.shape!=pair[key].shape or not np.isfinite(jac).all():
                    raise ValueError('finite propagation sensitivity of the required shape needed')
                pair[key] = pair[key]+jac
            if arc['wet']:
                jac = np.asarray(correction['wet_derivative'],float)
                if jac.shape!=delay.shape or not np.isfinite(jac).all():
                    raise ValueError('finite wet-path derivative required')
                pair['wet_derivative'] = jac
    path = pair['code_m'].ravel()
    # Constant code bias is absent from carrier increments.
    code = path+np.tile(arc['basis']@beta[:nb],len(arc['tags']))
    measurements = physical[ns:end_ground].copy()
    if arc['wet']:
        # Recalibrating the references at wet z gives c(z)=c(0)+R*z.
        # Thus c(0) observes the true receiver clock minus R*z. The same z
        # also changes the candidate path, with its own elevation mapping.
        measurements[:nc*n] -= (arc['wet_response']*wet[:,None]).ravel()
    mw = np.zeros(arc['mw_mask'].shape)
    mw[:,arc['mw_indices']] = physical[end_ground:]
    return np.r_[code,arc['difference']@path if arc['phase'] else [],mw[arc['mw_mask']],measurements],pair


def linearize(global_scaled, locals_scaled, arcs, global_scale, epoch, bounds, j2, *, diagnostics=None, joint_chol=None):
    physical = global_scaled*global_scale
    curve = dynamics.Trajectory(physical[:6],bounds,j2=j2,sensitivities=True)
    blocks = []
    for arc,local in zip(arcs,locals_scaled,strict=True):
        value,pair = model(curve,arc,local,physical[6:],epoch,derivatives=True)
        residual = solve_triangular(arc['chol'],value-arc['observed'],lower=True)
        count = arc['codes'].size
        ns,nc = arc['ns'],arc['nc']
        jac = np.zeros((len(value),len(local)))
        tx = pair['transmit_s']-(arc['endpoint_gpst_s']-epoch)
        jac[:count,:ns] = -clock_observations.satellite_basis(tx,ns).reshape(count,ns)*arc['local_scale'][:ns]
        row = np.arange(count)
        site = np.tile(np.arange(arc['n']),len(arc['tags']))
        rc = pair['receiver_clock_derivative'].ravel()
        for k in range(nc):
            col = ns+nc*site+k
            jac[row,col] = rc*np.repeat(arc['clock_basis'][:,k],arc['n'])*arc['local_scale'][col]
        for k in range(3):
            col = ns+nc*arc['n']+3*site+k
            jac[row,col] = pair['station_derivative'][...,k].ravel()*arc['local_scale'][col]
        state = np.zeros((len(value),6))
        state[:count] = pair['initial_state_derivative'].reshape(count,6)*global_scale[:6]
        if arc['phase']:
            stop = count+len(arc['difference'])
            jac[count:stop] = arc['difference']@jac[:count]
            jac[count:stop,0] = 0.  # Exact additive clock gauge.
            state[count:stop] = arc['difference']@state[:count]
        else:
            stop = count
        phase_stop = stop
        mw_sites = np.tile(np.arange(arc['n']),len(arc['tags'])-1)[arc['mw_mask'].ravel()] if arc['mw'] else []
        end_ground = ns+nc*arc['n']+3*arc['n']
        for j,s in enumerate(arc['mw_indices']):
            jac[stop:stop+len(mw_sites),end_ground+j] = (mw_sites==s)*arc['local_scale'][end_ground+j]
        stop += len(mw_sites)
        jac[stop:,ns:end_ground] = np.diag(arc['local_scale'][ns:end_ground])
        nb = arc['basis'].shape[1]
        bias = np.zeros((len(value),nb))
        bias[:count] = np.tile(arc['basis'],(len(arc['tags']),1))*global_scale[6:6+nb]
        shared = np.zeros((len(value),len(physical)-6-nb))
        if arc['wet']:
            columns = np.asarray(arc['station_indices'])
            shared[row,columns[site]] = pair['wet_derivative'].ravel()
            if arc['phase']:
                shared[count:phase_stop] = arc['difference']@shared[:count]
            for k in range(nc):
                shared[stop+nc*np.arange(arc['n'])+k,columns] = -arc['wet_response'][:,k]
            shared *= global_scale[6+nb:]
        weighted = lambda x:solve_triangular(arc['chol'],x,lower=True)
        nuisance = weighted(jac)
        singular = np.linalg.svd(nuisance,compute_uv=False)
        if singular[-1]<=singular[0]*RTOL:
            raise ValueError('rank-deficient local dynamic nuisance design')
        q,r = qr(nuisance,mode='economic')
        global_jac = weighted(np.column_stack([state,bias,shared]))
        blocks.append({'q':q,'r':r,'global':global_jac,'residual':residual,
                       'raw_local':jac,'raw_global':np.column_stack([state,bias,shared]),
                       'raw_residual':value-arc['observed'],
                       'reduced':global_jac-q@(q.T@global_jac),
                       'reduced_residual':residual-q@(q.T@residual)})
    if joint_chol is not None:
        # Reference clocks can share code/phase segment ambiguities across
        # arcs. Whiten the complete observation vector before profiling local
        # nuisance parameters; independent arc whitening would lose that
        # information and its signed offset/increment correlations.
        weighted = lambda x: solve_triangular(joint_chol, x, lower=True)
        nuisance = weighted(block_diag(*[b['raw_local'] for b in blocks]))
        global_jac = weighted(np.vstack([b['raw_global'] for b in blocks]))
        residual = weighted(np.concatenate([b['raw_residual'] for b in blocks]))
        q, r = qr(nuisance, mode='economic')
        if np.min(np.abs(np.diag(r))) <= np.max(np.abs(np.diag(r)))*RTOL:
            raise ValueError('rank-deficient joint dynamic nuisance design')
        reduced = global_jac-q@(q.T@global_jac)
        u, singular, vt = np.linalg.svd(reduced, full_matrices=False)
        if singular[-1] <= singular[0]*RTOL:
            raise ValueError('rank-deficient shared dynamic state/bias design')
        delta = -(vt.T/singular)@(u.T@(residual-q@(q.T@residual)))
        flat_delta = solve_triangular(r, -q.T@(residual+global_jac@delta))
        cuts = np.cumsum([len(a['local_scale']) for a in arcs])[:-1]
        local_delta = np.split(flat_delta, cuts)
        step_sigma = float(np.linalg.norm(global_jac@delta+nuisance@flat_delta))
        covariance = (vt.T/singular**2)@vt*global_scale[:,None]*global_scale[None,:]
        if diagnostics is not None:
            inverse = global_scale[:,None]*(vt.T/singular)@u.T
            raw_response = solve_triangular(joint_chol.T, inverse.T, lower=False).T
            cuts = np.cumsum([len(a['observed']) for a in arcs])[:-1]
            # Posterior local/global cross covariance supports explicit
            # hypothetical independent timing information requirements.
            scaled_cov = (vt.T/singular**2)@vt
            compensation = -solve_triangular(r,q.T@global_jac)
            inverse_r = solve_triangular(r,np.eye(len(r)))
            local_scale = np.concatenate([a['local_scale'] for a in arcs])
            local_cov = inverse_r@inverse_r.T+compensation@scaled_cov@compensation.T
            diagnostics.update(observation_response=np.split(raw_response,cuts,axis=1),
                scaled_singular_values=singular,
                local_covariance=local_cov*local_scale[:,None]*local_scale[None,:],
                global_local_covariance=(global_scale[:,None]*scaled_cov@compensation.T)*local_scale[None,:])
        return delta, local_delta, float(residual@residual), covariance, float(singular[0]/singular[-1]), step_sigma
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
    if diagnostics is not None:
        # Response to a change in the *raw observed vector*, after profiling
        # every local clock/ground parameter. This retains within-arc whitening
        # and can propagate a coherent source through all arcs without treating
        # repeated calibrations as independent measurements.
        inverse = global_scale[:,None]*(vt.T/singular)@u.T
        response,offset = [],0
        for a in arcs:
            count = len(a['observed'])
            response.append(inverse[:,offset:offset+count]@solve_triangular(a['chol'],np.eye(count),lower=True))
            offset += count
        diagnostics.update(observation_response=response,scaled_singular_values=singular)
    cost = sum(float(b['residual']@b['residual']) for b in blocks)
    return delta,local_delta,cost,covariance,float(singular[0]/singular[-1]),step_sigma


def cost(global_scaled,locals_scaled,arcs,global_scale,epoch,bounds,j2, *, joint_chol=None):
    physical = global_scaled*global_scale
    curve = dynamics.Trajectory(physical[:6],bounds,j2=j2,sensitivities=True)
    value, raw = 0., []
    for arc,local in zip(arcs,locals_scaled,strict=True):
        residual = model(curve,arc,local,physical[6:],epoch)[0]-arc['observed']
        raw.append(residual)
        r = solve_triangular(arc['chol'],residual,lower=True)
        value += float(r@r)
    if joint_chol is not None:
        r = solve_triangular(joint_chol,np.concatenate(raw),lower=True)
        return float(r@r)
    return value


def endpoint_code_rates(arc):
    """Quadratic derivative at the last training tag, not an interval midpoint.

    Subtract measured receiver clocks before differentiating. Constant station
    biases cancel; the unknown common satellite-clock rate is absorbed by the
    velocity seed's intercept. This noisier derivative is only an initializer,
    never an extra observation, prior or change to the fitted covariance.
    """
    tags = arc['tags'][-3:]
    span = -tags[0]  # prepare() requires increasing tags ending at zero.
    x = tags/span
    weights = np.linalg.solve(np.vstack([np.ones(3),x,x*x]),[0.,1./span,0.])
    corrected = arc['codes'][-3:]-arc['clock_basis'][-3:]@arc['clocks'].T
    return weights[:2]@(corrected[:2]-corrected[-1])


def initial(arc, seed, all_arcs, global_scale, epoch, bounds, j2):
    q = np.asarray(seed)
    unit = q[:3]-arc['xyz']
    unit /= np.linalg.norm(unit,axis=1)[:,None]
    rates = endpoint_code_rates(arc)
    velocity = np.linalg.lstsq(np.column_stack([unit,np.ones(len(unit))]),rates,rcond=None)[0][:3]
    physical = np.r_[q[:3],velocity,np.zeros(len(global_scale)-6)]
    curve = dynamics.Trajectory(physical[:6],bounds,j2=j2,sensitivities=True)
    locals_scaled = []
    for a in all_arcs:
        ns = a['ns']
        local = np.r_[np.zeros(ns),a['clocks'].ravel(),np.zeros(3*a['n']+len(a['mw_indices']))]/a['local_scale']
        value,pair = model(curve,a,local,physical[6:],epoch)
        tx = (pair['transmit_s']-(a['endpoint_gpst_s']-epoch)).ravel()
        clock = np.linalg.lstsq(clock_observations.satellite_basis(tx,ns),value[:a['codes'].size]-a['codes'].ravel(),rcond=None)[0]
        local[:ns] = clock/a['local_scale'][:ns]
        locals_scaled.append(local)
    return physical/global_scale,locals_scaled


def fit(arcs, *, include_phase=True, j2=dynamics.J2, max_iterations=25, progress=None, joint_covariance=None):
    if not isinstance(max_iterations,int) or max_iterations<1:
        raise ValueError('positive integer iteration budget required')
    prepared,names,basis = prepare(arcs,include_phase)
    # Matrix ordering is the concatenation of complete observed vectors in
    # chronological prepared-arc order. The historical block path is unchanged.
    joint_options = {} if joint_covariance is None else {'joint_chol':
        joint_cholesky(prepared,joint_covariance)}
    epoch = prepared[0]['endpoint_gpst_s']
    bounds = (min(a['endpoint_gpst_s']-epoch+a['tags'][0] for a in prepared)-2.,
              max(1.,max(a['endpoint_gpst_s']-epoch+30 for a in prepared)+2.))
    nb = len(names)-1
    global_scale = np.r_[STATE_SCALE,np.full(nb,100.),np.ones(len(names) if prepared[0]['wet'] else 0)]
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
                delta,local_delta,old_cost,cov,condition,step_sigma = linearize(global_point,locals_point,prepared,global_scale,epoch,bounds,j2,**joint_options)
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
                        new_cost = cost(proposed,proposed_locals,prepared,global_scale,epoch,bounds,j2,**joint_options)
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
            _,_,final_cost,cov,condition,_ = linearize(global_point,locals_point,prepared,global_scale,epoch,bounds,j2,**joint_options)
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
            'stations':names,'bias_contrast_coefficients_m':best['physical'][6:6+nb],
            'station_code_bias_m':dict(zip(names,basis@best['physical'][6:6+nb],strict=True)),
            **({'station_zenith_wet_correction_m':dict(zip(names,best['physical'][6+nb:],strict=True)),
                'wet_model':'free station-constant zenith wet corrections; reference recalibration linear response; no wet prior'} if prepared[0]['wet'] else {}),
            'arc_parameters':[{'endpoint_gpst_s':a['endpoint_gpst_s'],'stations':a['stations'],
                'satellite_clock':p[:a['ns']],'receiver_clocks':p[a['ns']:a['ns']+a['nc']*a['n']].reshape(a['n'],a['nc']),
                'station_corrections_m':p[a['ns']+a['nc']*a['n']:a['ns']+a['nc']*a['n']+3*a['n']].reshape(a['n'],3),
                **({'mw_rate_bias_m_s':[float(p[a['ns']+a['nc']*a['n']+3*a['n']+list(a['mw_indices']).index(s)])
                    if s in a['mw_indices'] else None for s in range(a['n'])]} if a.get('mw_free_drift',False) else {})}
                for a,p in zip(prepared,best['locals'],strict=True)],
            'conditional_global_covariance':best['covariance'],'weighted_residual_cost':best['cost'],
            'residual_dof':dof,'conditional_residual_p':p_value,'parameter_count':total_parameters,
            'scaled_condition':best['scaled_condition'],'branch_failures':failures,'branches':branches,
            'candidate_count':len(candidates),'physical_covariance_qualified':False,'j2':j2,
            'numerical_step_joint_sigma_tolerance':STEP_SIGMA_TOL,'residual_threshold_p':.01,
            'retained_phase_increment_count':sum(len(a['difference']) for a in prepared) if include_phase else 0,
            'total_phase_increment_count':sum((len(a['tags'])-1)*a['n'] for a in prepared) if include_phase else 0}
