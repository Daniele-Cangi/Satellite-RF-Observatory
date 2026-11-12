"""Conditional RF correction from genuinely excluded prediction errors.

Seven fixed link groups supply inner masked fits. Every error and the queried
outer error carries its own complete clock/float/wet response. Transport the
same admitted endpoint covariance through those maps, including cross-mask and
cross-time covariance. No scalar leverage shortcut or physical covariance claim.

One predictive hypothesis: independent station wet-path processes with a fixed
300 s exponential correlation. Only their common variance is estimated, using
prefix excluded errors. All admitted epochs condition the final Gaussian
prediction: this is conditional missing-link reconstruction, not forecasting
the whole network or a causal residual filter.
"""
from collections import Counter
import hashlib

import numpy as np
from scipy.linalg import eigh, solve_triangular
from scipy.optimize import minimize_scalar
from scipy.sparse import coo_matrix

from . import network_closures, network_clocks, phase_continuity, source_geometry

PSD_RTOL = 1e-10
CORRELATION_S = 300.


def link_group(row):
    key = row['station']+'/'+row['reference']
    return int.from_bytes(hashlib.sha256(key.encode('ascii')).digest()[:8], 'big') % 7


def prediction_response(network, workspace, queries, channels=(1,)):
    """Native predictions and a generator of exact raw-data response blocks.

    queries are (row, admitted-prefix segment); only geometry/identity is read.
    Output rows are query-major, then channels (0 code, 1 phase). Unsupported
    rows have zero placeholder response and MUST be removed by the caller.
    """
    records = [source_geometry.source_link_prediction(network, workspace, r, segment)
               for r, segment in queries]
    width = len(channels)
    count = len(queries)*width
    global_query = np.zeros((count, len(network['ambiguities_m'])))
    source_query = np.zeros((count, len(workspace['columns'])))
    local_query = [np.zeros((count, len(b['parameters']))) for b in network['blocks']]
    lookup = {b['time_s']: i for i, b in enumerate(network['blocks'])}
    for j, ((row, segment), record) in enumerate(zip(queries, records, strict=True)):
        if record['status'] != 'PREDICTED':
            continue
        bi = lookup[row['time_s']]
        b = network['blocks'][bi]
        a = np.zeros(len(b['parameters']))
        a[b['stations'].index(row['station'])] = row.get('clock_derivative', 1.)
        a[len(b['stations']):] = -b['reference_basis'][b['references'].index(row['reference'])]
        k = network['segments'].index(segment)
        g = source_geometry.source_design([row], workspace['columns'])
        for offset, channel in enumerate(channels):
            out = j*width+offset
            local_query[bi][out] = a
            global_query[out] = a@b['ambiguity_response']
            source_query[out] = g[channel]-a@workspace['clock_response'][bi]
            if channel == 1:
                global_query[out, k] += 1.
                source_query[out] -= workspace['ambiguity_response'][k]
    # Preserve the existing sequential source/nuisance rank decisions.
    u, s, vt = np.linalg.svd(workspace['design'], full_matrices=False)
    rank = len(workspace['columns'])-workspace['null'].shape[1]
    source_inverse = (vt[:rank].T/s[:rank])@u[:, :rank].T
    nuisance = network['profiled_ambiguity_left']
    source_inverse -= (source_inverse@nuisance)@nuisance.T

    def blocks():
        at = 0
        for b, local in zip(network['blocks'], local_query, strict=True):
            size = len(b['y'])
            project = np.eye(size)-b['a']@b['gain']
            weighted = (solve_triangular(b['chol'], project, lower=True) if b['chol'] is not None
                        else project/b['sigma'][:, None])
            beta = network['profiled_ambiguity_inverse']@nuisance[at:at+size].T@weighted
            source = source_inverse[:, at:at+size]@weighted
            yield b, local@b['gain']+global_query@beta+source_query@source
            at += size
    return records, blocks()


def image_solve(covariance, values, *, return_diagnostics=False):
    """Equilibrated PSD image solve with explicit numerical certification.

    Rank resolution follows floating-point backward error, not a fixed maximum
    covariance condition number. Diagonal scaling changes coordinates only;
    no ridge, raw-noise floor or process variance is added. Unresolved/null
    components of the supplied errors still fail rather than being filled.
    """
    c = np.asarray(covariance, float)
    y = np.asarray(values, float)
    if y.ndim != 1 or not len(y) or c.shape != (len(y), len(y)) or not np.isfinite(c).all() or not np.isfinite(y).all():
        raise ValueError('finite covariance and matching values required')
    eps = np.finfo(float).eps
    c = (c+c.T)/2
    # Zero diagonal coordinates retain unit scale and must pass the same PSD
    # and image checks; a negative variance is never repaired by scaling.
    if np.any(np.diag(c) < 0.):
        raise ValueError('prediction-error covariance is not positive semidefinite')
    scale = np.sqrt(np.where(np.diag(c)>0., np.diag(c), 1.))
    equilibrated = c/scale[:, None]/scale[None, :]
    eigen, vectors = eigh(equilibrated, check_finite=False)
    # Conservative dimension-dependent floating-point resolution for a dense
    # symmetric eigensolve. This is fixed before any corrected held scoring.
    resolution = 8.*eps*len(y)*max(float(np.max(abs(eigen))), np.finfo(float).tiny)
    if eigen[0] < -resolution:
        raise ValueError('prediction-error covariance is not positive semidefinite')
    keep = eigen > resolution
    if not keep.any():
        raise ValueError('no resolved prediction-error covariance image')
    u = vectors[:, keep]
    scaled_y = y/scale
    remainder = scale*(scaled_y-u@(u.T@scaled_y))
    if np.linalg.norm(remainder) > 1e-7*max(np.linalg.norm(y), 1e-8):
        raise ValueError('prediction errors outside the covariance image')
    whitening = u/scale[:, None]/np.sqrt(eigen[keep])
    solution = whitening@(whitening.T@y)
    # Certification is independent of the held RF scores. Refuse a numerically
    # inaccurate whitening or solve even if the spectral image test succeeded.
    defect = whitening.T@(c@whitening)-np.eye(int(keep.sum()))
    whitening_error = float(np.linalg.norm(defect, ord=np.inf))
    denominator = np.linalg.norm(c, ord=np.inf)*np.linalg.norm(solution, ord=np.inf)+np.linalg.norm(y, ord=np.inf)
    backward_error = float(np.linalg.norm(c@solution-y, ord=np.inf)/max(denominator, np.finfo(float).tiny))
    if not np.isfinite(whitening_error) or whitening_error > 1e-4:
        raise ValueError('prediction-error covariance whitening failed numerical accuracy check')
    if not np.isfinite(backward_error) or backward_error > 64.*eps*len(y):
        raise ValueError('prediction-error covariance solve failed backward-error check')
    diagnostics = {'solver':'equilibrated-machine-resolution-v2',
        'dimension':len(y), 'rank':int(keep.sum()),
        'equilibrated_eigenvalue_resolution':resolution,
        'equilibrated_minimum_eigenvalue':float(eigen[0]),
        'equilibrated_maximum_eigenvalue':float(eigen[-1]),
        'whitening_identity_inf_error':whitening_error,
        'whitening_identity_inf_limit':1e-4,
        'solve_relative_backward_error':backward_error,
        'solve_relative_backward_error_limit':64.*eps*len(y)}
    result = (solution, whitening, int(keep.sum()))
    return (*result, diagnostics) if return_diagnostics else result


def covariance_diagnostics(covariance, errors, factor, whitened_values):
    """Inspect the unchanged image rule and its independent raw-factor replay.

    C=F F.T, e=F whitened_y must have the same exact image for positive raw
    covariance. A cutoff can discard nonzero directions; matrix products and
    native predictions also have finite precision. Do not conflate these cases.
    No rank change, ridge, process fit or held score is performed here.
    """
    c, e, f = np.asarray(covariance,float), np.asarray(errors,float), np.asarray(factor,float)
    eigen, vectors = eigh((c+c.T)/2,check_finite=False)
    scale=max(float(eigen[-1]),np.finfo(float).tiny)
    cut=PSD_RTOL*scale
    keep=eigen>cut
    components=vectors.T@e
    retained=vectors[:,keep]
    remainder=e-retained@(retained.T@e)
    norm=float(np.linalg.norm(e))
    tail=float(np.linalg.norm(remainder))
    tolerance=1e-7*max(norm,1e-8)
    replay=f@np.asarray(whitened_values,float)
    replay_tail=replay-retained@(retained.T@replay)
    direction=remainder/tail if tail else np.zeros(len(e))
    factor_variance=float(np.linalg.norm(f.T@direction)**2)
    gram_variance=float(direction@c@direction)
    discarded=np.flatnonzero(~keep)
    strongest=discarded[np.argsort(abs(components[discarded]))[-8:][::-1]]
    return {'error_count':len(e),'retained_rank':int(keep.sum()),'discarded_count':int((~keep).sum()),
        'psd_rtol':PSD_RTOL,'eigenvalue_cut_m2':cut,'minimum_eigenvalue_m2':float(eigen[0]),
        'maximum_eigenvalue_m2':scale,'positive_discarded_eigenvalues':int(np.sum((eigen>0)&~keep)),
        'error_norm_m':norm,'discarded_error_norm_m':tail,'image_tolerance_m':tolerance,
        'guard_accepts':bool(keep.any() and eigen[0]>=-cut and tail<=tolerance),
        'operator_replay_max_abs_m':float(np.max(abs(e-replay))),
        'operator_replay_l2_m':float(np.linalg.norm(e-replay)),
        'replayed_error_discarded_norm_m':float(np.linalg.norm(replay_tail)),
        'discarded_error_factor_variance_m2':factor_variance,
        'discarded_error_gram_variance_m2':gram_variance,
        'discarded_error_factor_projection_m':float((f.T@direction)@whitened_values),
        'eigenvalues_m2':eigen,'error_eigen_components_m':components,
        'largest_discarded_error_modes':[{'index':int(i),'eigenvalue_m2':float(eigen[i]),
            'error_component_m':float(components[i]),
            'factor_variance_m2':float(np.linalg.norm(f.T@vectors[:,i])**2)} for i in strongest]}


def fit_variance(errors, noise, signal_factor):
    """One prefix-only marginal likelihood; variance zero is an explicit fit.

    The fixed broad log-variance search interval is numerical, not an RF floor
    or physical amplitude bound. A solution at its upper limit is unsupported.
    """
    _, whitening, rank, numerical = image_solve(noise, errors, return_diagnostics=True)
    z = whitening.T@errors
    design = whitening.T@signal_factor
    u, s, _ = np.linalg.svd(design, full_matrices=False)
    if not len(s) or s[0] < 1e-12:
        raise ValueError('no resolved dynamic wet response in prefix errors')
    energy = s*s
    projected = (u.T@z)**2
    def objective(variance):
        return float(np.sum(np.log1p(variance*energy)+projected/(1.+variance*energy)))
    optimum = minimize_scalar(lambda log_v: objective(np.exp(log_v)), bounds=(-32., 20.), method='bounded')
    if not optimum.success or optimum.x > 20.-1e-3:
        raise ValueError('predictive variance optimization unsupported')
    variance = float(np.exp(optimum.x)) if optimum.fun < objective(0.) else 0.
    return {'variance_zenith_m2': variance, 'sigma_zenith_m': float(np.sqrt(variance)),
            'status': 'POSITIVE_PREDICTIVE_VARIANCE' if variance else 'FITTED_ZERO_PREDICTIVE_VARIANCE',
            'prefix_error_count': len(errors), 'prefix_noise_image_rank': rank,
            'prefix_numerical_solve':numerical,
            'fixed_correlation_s': CORRELATION_S, 'log_variance_search': [-32., 20.],
            'negative_twice_loglikelihood_change': objective(variance)-objective(0.),
            'physical_wet_covariance_qualified': False}


def condition_errors(errors, noise, cross, signal, target_signal, variance, *, return_diagnostics=False):
    """Joint conditional mean of the OUTER error, with its own response map."""
    solution, whitening, rank, numerical = image_solve(noise, errors, return_diagnostics=True)
    if variance:
        # Keep the original noise image: a strong process must not raise a
        # relative joint-covariance cutoff and erase other measured directions.
        original_z = whitening.T@errors
        z = original_z.copy()
        u, s, _ = np.linalg.svd(whitening.T@signal, full_matrices=False)
        projected = u.T@z
        z = z-u@projected+u@(projected/(1.+variance*s*s))
        response = variance*(s*s)*(u.T@z)
        residual = z+u@response-original_z
        denominator = (1.+variance*float(np.max(s*s, initial=0.)))*np.linalg.norm(z)+np.linalg.norm(original_z)
        error = float(np.linalg.norm(residual)/max(denominator,np.finfo(float).tiny))
        limit = 64.*np.finfo(float).eps*len(errors)
        if not np.isfinite(error) or error>limit:
            raise ValueError('conditional covariance solve failed backward-error check')
        numerical.update(conditional_relative_backward_error=error,
                         conditional_relative_backward_error_limit=limit)
        solution = whitening@z
    result = ((cross+variance*(target_signal@signal.T))@solution, rank)
    return (*result, numerical) if return_diagnostics else result


def _fit(rows, candidate, raw_covariance):
    training = phase_continuity.segment(rows)
    network = network_clocks.fit(training, raw_covariance=raw_covariance)
    _, workspace = source_geometry.profile_sources(network, candidate, ('wet',))
    return training, network, workspace


def _prefix(training, cut):
    return {(r['station'], r['reference'], r['base_segment']): r['segment']
            for r in training if r['time_s'] <= cut}


def _segment(row, prefix):
    return prefix.get((row['station'], row['reference'], row.get('base_segment', row['segment'])))


def _embed(target, block, response, raw_index, output_indices):
    m = len(block['rows'])
    for channel in range(len(block['y'])//m):
        columns = [3*raw_index[r['station'], r['reference'], r['time_s']]+channel for r in block['rows']]
        target[np.ix_(output_indices, columns)] -= response[:, channel*m:(channel+1)*m]


def prepare_future_links(rows, candidate, raw_covariance, *, diagnose_only=False):
    """One fixed covariance-aware correction, preserving the native baseline.

    Outer held values are excluded before ANY segmentation/fit. Inner groups
    remove complete code/phase/MW/GF rows after 2/3 of the outer prefix. Queried
    inner phase labels are read only after fitting their excluding calibration.
    Their continuity is the existing admitted-prefix hypothesis, not held GF.
    """
    network_closures.admit(rows, candidate)
    baseline = network_closures.prepare_future_links(rows, candidate, raw_covariance, source_families=('wet',))
    if baseline['status'] != 'FUTURE_LINK_PREDICTIONS_FROZEN':
        return {'baseline': baseline, 'model_status': 'BASELINE_FAILED'}
    cut = baseline['training_stop_s']
    selected = set(map(tuple, baseline['held_links']))
    admitted = [r for r in rows if not ((r['station'], r['reference']) in selected and r['time_s'] > cut)]
    start = min(r['time_s'] for r in admitted)
    inner_cut = start+2*(cut-start)/3
    key = lambda r: (r['station'], r['reference'], r['time_s'])
    raw_index = {key(r): i for i, r in enumerate(admitted)}
    query = [r for r in admitted if r['time_s'] > inner_cut]
    queries_by_group = [[i for i, r in enumerate(query) if link_group(r) == g] for g in range(7)]
    a = np.zeros((len(query), 3*len(admitted)))
    errors = np.zeros(len(query))
    valid = np.zeros(len(query), bool)
    terminals = []
    for group, indices in enumerate(queries_by_group):
        try:
            own = [r for r in admitted if not (link_group(r) == group and r['time_s'] > inner_cut)]
            training, network, workspace = _fit(own, candidate, raw_covariance)
            prefix = _prefix(training, inner_cut)
            queries = [(query[i], _segment(query[i], prefix)) for i in indices]
            records, response = prediction_response(network, workspace, queries)
            supported = [j for j, r in enumerate(records) if r['status'] == 'PREDICTED']
            out = [indices[j] for j in supported]
            for block, matrix in response:
                _embed(a, block, matrix[supported], raw_index, out)
            for j in supported:
                i = indices[j]
                a[i, 3*raw_index[key(query[i])]+1] += 1.
                errors[i] = float(query[i]['phase_m'])-records[j]['phase_prediction_m']
                valid[i] = True
            terminals.append({'group': group, 'status': 'EVALUATED', 'training_rows': len(training),
                'query_status_counts': dict(Counter(r['status'] for r in records)),
                'queries': [{**{k: query[i][k] for k in ('station', 'reference', 'time_s')},
                             'status': r['status']} for i, r in zip(indices, records, strict=True)]})
        except (ValueError, np.linalg.LinAlgError) as error:
            terminals.append({'group': group, 'status': 'INNER_FIT_UNAVAILABLE', 'reason': str(error),
                'query_count': len(indices), 'queries': [
                    {**{k:query[i][k] for k in ('station','reference','time_s')},
                     'status':'INNER_FIT_UNAVAILABLE'} for i in indices]})
    output = {'baseline': baseline, 'inner_training_stop_s': inner_cut, 'inner_groups': terminals,
        'conditional_on_all_admitted_epochs': True, 'candidate_products_used': False,
        'physical_covariance_qualified': False, 'production_calibration_changed': False}
    variant = dict(baseline, predictions=[dict(p) for p in baseline['predictions']])
    try:
        if not valid.any():
            raise ValueError('no supported inner prediction errors')
        a = a[valid]
        errors = errors[valid]
        query = [r for r, use in zip(query, valid, strict=True) if use]
        times = sorted({r['time_s'] for r in admitted})
        stations = sorted({r['station'] for r in admitted})
        ti, si = {t: i for i, t in enumerate(times)}, {s: i for i, s in enumerate(stations)}
        state_index = lambda r: ti[r['time_s']]*len(stations)+si[r['station']]
        coordinates, columns, values = [], [], []
        for i, r in enumerate(admitted):
            for channel in (0, 1):
                coordinates.append(3*i+channel)
                columns.append(state_index(r))
                values.append(float(r['wet_mapping']))
        dynamic = coo_matrix((values, (coordinates, columns)),
            shape=(3*len(admitted), len(times)*len(stations))).tocsr()
        b = np.asarray(a@dynamic)
        training, network, workspace = _fit(admitted, candidate, raw_covariance)
        prefix = _prefix(training, cut)
        original = {key(r): r for r in rows}
        positions = [i for i, p in enumerate(variant['predictions']) if p['status'] == 'PREDICTED']
        held = [original[key(variant['predictions'][i])] for i in positions]
        records, responses = prediction_response(network, workspace,
            [(r, _segment(r, prefix)) for r in held], channels=(0, 1))
        if any(r['status'] != 'PREDICTED' for r in records):
            raise ValueError('native baseline operator support differs')
        h = np.zeros((2*len(held), 3*len(admitted)))
        for block, matrix in responses:
            _embed(h, block, matrix, raw_index, list(range(len(h))))
        bh = np.asarray(h@dynamic)
        for i, r in enumerate(held):
            bh[2*i:2*i+2, state_index(r)] += float(r['wet_mapping'])
        # Covariance is transported from the SAME admitted raw endpoints, so
        # shared calibration errors across masks and times are not independent.
        endpoint = network['blocks'][0]['covariance']
        m = len(network['blocks'][0]['rows'])
        chol = np.linalg.cholesky(endpoint[np.ix_([0, m, 2*m], [0, m, 2*m])])
        for first in range(0, len(admitted), 64):
            last = min(first+64, len(admitted))
            a[:, 3*first:3*last] = (a[:, 3*first:3*last].reshape(len(a), -1, 3)@chol).reshape(len(a), -1)
            h[:, 3*first:3*last] = (h[:, 3*first:3*last].reshape(len(h), -1, 3)@chol).reshape(len(h), -1)
        noise = a@a.T
        if diagnose_only:
            # These are admitted rows only. Replay error formation independently
            # before deleting F; no correction/process parameter is estimated.
            raw_values=np.asarray([[r[k] for k in ('code_m','phase_m','mw_m')] for r in admitted],float)
            whitened=solve_triangular(chol,raw_values.T,lower=True).T.ravel()
            prefix_rows=np.asarray([r['time_s']<=cut for r in query])
            output.update(model_status='COVARIANCE_DIAGNOSTIC_COMPLETE',
                diagnostic_only=True,correction_variance_fitted=False,held_scores_computed=False,
                diagnostics={'prefix':covariance_diagnostics(noise[np.ix_(prefix_rows,prefix_rows)],
                    errors[prefix_rows],a[prefix_rows],whitened),
                    'all_admitted':covariance_diagnostics(noise,errors,a,whitened)})
            output['first_rejection_stage']=next((stage for stage in ('prefix','all_admitted')
                if not output['diagnostics'][stage]['guard_accepts']),None)
            return output
        cross = h@a.T
        del a, h
        distance = abs(np.subtract.outer(times, times))
        kernel = np.kron(np.exp(-distance/CORRELATION_S), np.eye(len(stations)))
        latent = np.linalg.cholesky(kernel)
        signal, target_signal = b@latent, bh@latent
        prefix_rows = np.array([r['time_s'] <= cut for r in query])
        if prefix_rows.sum() < 8:
            raise ValueError('at least eight excluded prefix errors required')
        fitted = fit_variance(errors[prefix_rows], noise[np.ix_(prefix_rows, prefix_rows)], signal[prefix_rows])
        variance = fitted['variance_zenith_m2']
        correction, rank, numerical = condition_errors(errors,noise,cross,signal,target_signal,variance,
                                                     return_diagnostics=True)
        if not np.isfinite(correction).all():
            raise ValueError('nonfinite conditional correction')
        for j, i in enumerate(positions):
            p = variant['predictions'][i]
            p['path_prediction_m'] += float(correction[2*j])
            p['phase_path_prediction_m'] += float(correction[2*j+1])
            p['phase_prediction_m'] += float(correction[2*j+1])
            p.update(mask_consistent_code_correction_m=float(correction[2*j]),
                     mask_consistent_phase_correction_m=float(correction[2*j+1]))
        output.update(model_status='CONDITIONAL_MASK_CONSISTENT_MODEL', model=fitted,
            admitted_error_count=len(errors), noise_image_rank=rank,
            conditional_numerical_solve=numerical,
            maximum_absolute_off_diagonal_noise_covariance_m2=float(np.max(abs(noise-np.diag(noise.diagonal())))),
            excluded_phase_errors_m=errors,
            error_identities=[{k:r[k] for k in ('station', 'reference', 'time_s')} for r in query])
    except (ValueError, np.linalg.LinAlgError) as error:
        output.update(model_status='UNSUPPORTED_MASK_CONSISTENT_MODEL', reason=str(error))
        for p in variant['predictions']:
            if p['status'] == 'PREDICTED':
                p['status'] = 'UNSUPPORTED_MASK_CONSISTENT_MODEL'
    variant['prediction_status_counts'] = dict(Counter(p['status'] for p in variant['predictions']))
    output['variants'] = {'mask_consistent': variant}
    return output
