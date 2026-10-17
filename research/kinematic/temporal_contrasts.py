"""Reference-only clock-free temporal contrasts, not a total noise budget.

D=IF code-IF phase and MW remove nondispersive geometry/clock and first-order
ionosphere. Segment differences remove constant float biases. Normalized
variograms estimate a sensitivity shape, never rescale historical IF floors.
"""
from collections import Counter, defaultdict

import numpy as np
from scipy.linalg import helmert
from scipy.optimize import minimize_scalar

LAGS = (30.,60.,90.,120.,300.)


def increments(rows, start, stop, lag):
    index = {(r['station'],r['reference'],r['time_s']):r for r in rows}
    output = []
    for r in rows:
        p = index.get((r['station'],r['reference'],r['time_s']-lag))
        if p is None or p['segment']!=r['segment'] or not start<=p['time_s']<r['time_s']<=stop:
            continue
        z = np.array([r['code_m']-r['phase_m']-p['code_m']+p['phase_m'],r['mw_m']-p['mw_m']])
        if not np.isfinite(z).all():
            raise ValueError('finite admitted code/phase/MW contrasts required')
        output.append({'station':r['station'],'reference':r['reference'],'time_s':r['time_s'],'z':z})
    return output


def variograms(rows, start, stop):
    output = []
    for lag in LAGS:
        own = increments(rows,start,stop,lag)
        z = np.array([r['z'] for r in own])
        output.append({'lag_s':lag,'count':len(own),
            'mean_difference_m':z.mean(axis=0) if len(z) else None,
            'semivariogram_m2':z.T@z/(2*len(z)) if len(z) else None})
    return output


def split_receiver_contrasts(rows, start, stop, *, groups=None, lag=30.):
    """Disjoint-reference estimates of receiver contrasts at a fixed lag.

    Free reference effects remove satellite-common changes. Missing/disconnected
    split graphs remain unsupported. Cross moments may be negative: do not
    project them into a positive physical receiver covariance.
    """
    sites = sorted({r['station'] for r in rows})
    refs = sorted({r['reference'] for r in rows})
    groups = [refs[::2],refs[1::2]] if groups is None else groups
    if (len(groups)!=2 or len(set(groups[0]) & set(groups[1]))
            or sorted(groups[0]+groups[1])!=refs or not np.isfinite(lag) or lag<=0):
        raise ValueError('two disjoint exhaustive reference groups and a positive lag required')
    if len(sites)<2:
        return {'status':'INSUFFICIENT_STATIONS','rows':[]}
    h = helmert(len(sites),full=False).T
    grouped = defaultdict(list)
    for r in increments(rows,start,stop,lag):
        grouped[r['time_s']].append(r)
    output = []
    for time,own in sorted(grouped.items()):
        fitted = []
        for group in groups:
            selected = [r for r in own if r['reference'] in group]
            qs = sorted({r['reference'] for r in selected})
            a = np.array([np.r_[h[sites.index(r['station'])],np.eye(len(qs))[qs.index(r['reference'])]] for r in selected])
            if not selected or np.linalg.matrix_rank(a)<a.shape[1]:
                break
            fitted.append(np.linalg.lstsq(a,np.array([r['z'] for r in selected]),rcond=None)[0][:len(sites)-1])
        output.append({'time_s':time,'status':'EVALUATED' if len(fitted)==2 else 'UNOBSERVED_SPLIT_CONTRAST',
            **({'split_contrasts_m':fitted} if len(fitted)==2 else {})})
    complete = [r['split_contrasts_m'] for r in output if r['status']=='EVALUATED']
    result = {'status':'RELATIVE_DISJOINT_REFERENCE_DIAGNOSTIC','stations':sites,
        'reference_groups':groups,'rows':output,
        'status_counts':dict(Counter(r['status'] for r in output)),
        'physical_receiver_covariance_qualified':False}
    if len(complete)>1:
        a,b = np.asarray(complete)[:,0],np.asarray(complete)[:,1]
        ma,mb = a.mean(axis=0),b.mean(axis=0)
        a,b = a-ma,b-mb
        c = np.einsum('tki,tkj->ij',a,b)/((len(a)-1)*(len(sites)-1))
        c = (c+c.T)/2
        result.update(cross_covariance_m2=c,cross_covariance_eigenvalues_m2=np.linalg.eigvalsh(c),
            split_mean_changes_m=[ma,mb],positive_semidefinite=bool(np.linalg.eigvalsh(c)[0]>=0),
            interpretation='Cross-split moment under disjoint-link assumptions, not independent trials or a finite raw shared-noise amplitude.')
    return result


def estimate(rows):
    if not rows:
        raise ValueError('admitted reference rows required')
    start,stop = min(r['time_s'] for r in rows),max(r['time_s'] for r in rows)
    cut = start+2*(stop-start)/3
    train,validation = variograms(rows,start,cut),variograms(rows,np.nextafter(cut,np.inf),stop)
    def ratios(records):
        if any(r['count']==0 for r in records[:4]):
            raise ValueError('insufficient reference pairs for fixed temporal lags')
        diagonal = np.array([np.diag(r['semivariogram_m2']) for r in records[:4]])
        if np.any(diagonal[0]<=0):
            raise ValueError('nonzero reference contrast variograms required')
        return diagonal/diagonal[0]
    observed = ratios(train)
    def prediction(rho):
        return np.array([sum(rho**j for j in range(k)) for k in range(1,5)])[:,None]
    def loss(rho,values):
        return float(np.mean((prediction(rho)-values)**2))
    optimum = minimize_scalar(lambda rho:loss(rho,observed),bounds=(0.,.99),method='bounded')
    rho = min((0.,float(optimum.x),.99),key=lambda x:loss(x,observed))
    try:
        held = ratios(validation)
        validation_loss = {'status':'EVALUATED','temporal_normalized_loss':loss(rho,held),
            'independent_normalized_loss':loss(0.,held)}
    except ValueError as error:
        validation_loss = {'status':'UNSUPPORTED_TEMPORAL_VALIDATION','reason':str(error)}
    return {'status':'REFERENCE_INFORMED_SENSITIVITY_ONLY','training_start_s':start,
        'training_stop_s':cut,'validation_stop_s':stop,'code_endpoint_ar1_rho_30s':rho,
        'training_normalized_loss':loss(rho,observed),'training_variograms':train,
        'validation_variograms':validation,'validation':validation_loss,
        'split_training':split_receiver_contrasts(rows,start,cut),
        'split_validation':split_receiver_contrasts(rows,np.nextafter(cut,np.inf),stop),
        'marginal_sigmas_rescaled':False,'physical_temporal_covariance_qualified':False,
        'phase_temporal_correlation_inferred':False,'hyperparameter_uncertainty_propagated':False,
        'caveat':'D/MW contrast shape includes bias/multipath/phase effects; common raw code AR(1) and receiver shared fraction are model assumptions, not identified physical components.'}
