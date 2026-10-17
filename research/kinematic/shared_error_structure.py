"""Identify differential spatial transfer without inventing a raw noise budget.

All fitting uses admitted references in the first two thirds of time. Future
reference group A can predict group B contemporaneously; this is conditional
cross-reference prediction, not a forecast with future RF unavailable.
"""
import hashlib

import numpy as np

from . import gnss_combinations, temporal_contrasts

LAGS = (30., 300.)
BLOCK_S = 300.


def raw_identifiability(contrast_covariance):
    """Construct indistinguishable PSD code-only/phase-only increment laws.

    The supplied PSD scale is a witness, never an estimate of shared raw noise.
    The covariance map has three observed moments and ten raw unknowns.
    """
    c = np.asarray(contrast_covariance, float)
    if (c.shape != (2, 2) or not np.isfinite(c).all()
            or not np.allclose(c, c.T, atol=1e-12, rtol=0)
            or np.linalg.eigvalsh(c)[0] < -1e-12):
        raise ValueError('a symmetric PSD contrast covariance is required')
    t = gnss_combinations.transform()
    h = np.vstack((t[0]-t[1], t[3]))
    laws = {}
    for label, indices in (('code_only', [0, 1]), ('phase_only', [2, 3])):
        inverse = np.linalg.inv(h[:, indices])
        raw = np.zeros((4, 4))
        raw[np.ix_(indices, indices)] = inverse @ c @ inverse.T
        laws[label] = {'raw_increment_covariance_m2': raw,
            'retained_if_mw_increment_covariance_m2': t[gnss_combinations.RETAINED] @ raw @ t[gnss_combinations.RETAINED].T}
    columns, separated = [], []
    for i in range(4):
        for j in range(i, 4):
            basis = np.zeros((4, 4))
            basis[i, j] = basis[j, i] = 1.
            mapped = h @ basis @ h.T
            columns.append(mapped[[0, 0, 1], [0, 1, 1]])
            if (i < 2) == (j < 2):
                separated.append(columns[-1])
    ionosphere = np.array([1., (gnss_combinations.F1_HZ/gnss_combinations.F2_HZ)**2,
                           -1., -(gnss_combinations.F1_HZ/gnss_combinations.F2_HZ)**2])
    return {'contrast_transform': h, 'raw_mean_nullity': 4-np.linalg.matrix_rank(h),
        'raw_covariance_nullity': 10-np.linalg.matrix_rank(np.asarray(columns).T),
        'separate_code_phase_covariance_nullity': 6-np.linalg.matrix_rank(np.asarray(separated).T),
        'witness_contrast_increment_covariance_m2': c, 'indistinguishable_laws': laws,
        'nondispersive_null_vector': np.ones(4), 'ionosphere_null_vector': ionosphere,
        'augmented_mean_rank': np.linalg.matrix_rank(np.vstack((h, t[1], t[2]))),
        'additional_information': 'Independent nondispersive IF-phase range/clock/propagation information and an ionospheric/GF constraint; the existing free clock/ionosphere nuisance values do not supply either.',
        'physical_covariance_qualified': False}


def partitions(rows):
    """Four fixed identity-only splits, retained regardless of outcomes."""
    refs = sorted({r['reference'] for r in rows})
    result = [('alternating', [refs[::2], refs[1::2]])]
    for seed in range(3):
        order = sorted(refs, key=lambda q: hashlib.sha256(f'spatial-{seed}/{q}'.encode('ascii')).digest())
        result.append((f'hash_{seed}', [sorted(order[::2]), sorted(order[1::2])]))
    return result


def _array(record):
    complete = [r for r in record['rows'] if r['status'] == 'EVALUATED']
    return np.array([r['time_s'] for r in complete]), np.asarray([r['split_contrasts_m'] for r in complete])


def _moments(x):
    a, b = x[:, 0].copy(), x[:, 1].copy()
    means = [a.mean(0), b.mean(0)]
    a -= means[0]
    b -= means[1]
    denominator = (len(a)-1)*a.shape[1]
    flat_a, flat_b = a.reshape(-1, 2), b.reshape(-1, 2)
    ca, cb = flat_a.T @ flat_a/denominator, flat_b.T @ flat_b/denominator
    cross = flat_a.T @ flat_b/denominator
    cross = (cross+cross.T)/2
    common, disagreement = (flat_a+flat_b)/2, (flat_a-flat_b)/2
    return {'split_mean_changes_m': means, 'split_covariance_m2': [ca, cb],
        'cross_covariance_m2': cross, 'cross_eigenvalues_m2': np.linalg.eigvalsh(cross),
        'consensus_covariance_m2': common.T @ common/denominator,
        'disagreement_covariance_m2': disagreement.T @ disagreement/denominator}, flat_a, flat_b


def fit_predict(training, validation):
    """Freeze two directional predictors before excluded-B/A scoring."""
    times, x = _array(training)
    vt, vx = _array(validation)
    output = {'training': training, 'validation': validation,
              'status': 'INSUFFICIENT_SPLIT_SUPPORT', 'physical_covariance_qualified': False}
    if len(x) < 3 or len(vx) < 2:
        return output
    moments, a, b = _moments(x)
    if min(np.linalg.eigvalsh(c)[0] for c in moments['split_covariance_m2']) <= 0:
        output['status'] = 'SINGULAR_TRAINING_CONTRASTS'
        return output
    deletions = []
    for block in sorted(set(np.floor(times/BLOCK_S))):
        keep = np.floor(times/BLOCK_S) != block
        if sum(keep) >= 3:
            own, _, _ = _moments(x[keep])
            deletions.append({'block_start_s': block*BLOCK_S, 'retained_epochs': int(sum(keep)),
                'cross_eigenvalues_m2': own['cross_eigenvalues_m2']})
    output.update(status='PREDICTIONS_FROZEN', training_moments=moments,
        training_block_deletions=deletions, predictors={})
    cross = moments['cross_covariance_m2']
    admissible = bool(np.linalg.eigvalsh(cross)[0] >= 0 and all(
        np.linalg.eigvalsh(c-cross)[0] >= 0 for c in moments['split_covariance_m2']))
    # A rejected moment is retained verbatim. Zero is the independent model,
    # not a projection of its negative eigenvalues into a physical variance.
    shared = cross if admissible else np.zeros((2, 2))
    output.update(common_moment_admissible=admissible,
        positive_common_covariance_m2=shared)
    means = moments['split_mean_changes_m']
    for name, source, target, source_i, target_i in (
            ('A_to_B', a, b, 0, 1), ('B_to_A', b, a, 1, 0)):
        weight = 1/np.diag(moments['split_covariance_m2'][target_i])
        unconstrained = float(np.sum(source*target*weight)/np.sum(source**2*weight))
        positive = np.linalg.solve(moments['split_covariance_m2'][source_i], shared)
        gain = np.linalg.lstsq(source, target, rcond=None)[0]
        # Each direction uses only its source split's excluded values. No
        # target-split value enters that prediction and validation never refits.
        observed_source = vx[:, source_i]-means[source_i]
        predicted = {'independent': np.broadcast_to(means[target_i], observed_source.shape).copy(),
            'positive_common': means[target_i]+observed_source @ positive,
            'signed_cross_group': means[target_i]+observed_source @ gain}
        output['predictors'][name] = {'source_split': source_i, 'target_split': target_i,
            'positive_common_gain': positive, 'unconstrained_scalar_gain': unconstrained,
            'signed_gain': gain, 'validation_times_s': vt, 'predictions_m': predicted}
    return output


def evaluate(record):
    """Evaluate all frozen predictors on exactly their common support."""
    if record['status'] != 'PREDICTIONS_FROZEN':
        return record
    _, x = _array(record['validation'])
    moments, _, _ = _moments(x)
    scores = {}
    for name, model in record['predictors'].items():
        observed = x[:, model['target_split']]
        variance = np.diag(record['training_moments']['split_covariance_m2'][model['target_split']])
        baseline = np.mean((observed-model['predictions_m']['independent'])**2, axis=(1, 2))
        own = {}
        for label, predicted in model['predictions_m'].items():
            square = (observed-predicted)**2
            own[label] = {'mean_square_m2': square.mean(axis=(0, 1)),
                'training_scaled_loss': float(np.mean(square/variance)),
                'worse_epochs_than_independent': int(sum(square.mean(axis=(1, 2)) > baseline)),
                'epoch_count': len(x)}
        scores[name] = own
    deletions = record['training_block_deletions']
    stable_positive = bool(deletions and all(r['cross_eigenvalues_m2'][0] > 0 for r in deletions))
    supported = (record['training_moments']['cross_eigenvalues_m2'][0] > 0
        and moments['cross_eigenvalues_m2'][0] > 0 and stable_positive
        and record['common_moment_admissible']
        and all(s['positive_common']['training_scaled_loss'] < s['independent']['training_scaled_loss'] for s in scores.values()))
    return {**record, 'status': 'POSITIVE_DIFFERENTIAL_TRANSFER_SUPPORTED' if supported else 'POSITIVE_SHARED_STRUCTURE_UNQUALIFIED',
        'validation_moments': moments, 'scores': scores,
        'positive_cross_moment_survives_training_block_deletions': stable_positive,
        'signed_transfer_improves_both_directions': all(
            s['signed_cross_group']['training_scaled_loss'] < s['independent']['training_scaled_loss'] for s in scores.values()),
        'raw_allocation_identifiable': False, 'total_physical_budget_qualified': False}


def prepare(rows, candidate):
    # Admission precedes time/measurement arithmetic, including poison objects.
    if any(r['reference'] == candidate for r in rows):
        raise ValueError('candidate in its own shared-error references')
    if not rows:
        raise ValueError('nonempty admitted reference rows required')
    keys = [(r['station'], r['reference'], r['time_s']) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError('duplicate admitted reference row')
    start, stop = min(r['time_s'] for r in rows), max(r['time_s'] for r in rows)
    cut = start+2*(stop-start)/3
    output = {'training_start_s': start, 'training_stop_s': cut, 'validation_stop_s': stop,
              'comparisons': {}, 'physical_covariance_qualified': False}
    for name, groups in partitions(rows):
        for lag in LAGS:
            tr = temporal_contrasts.split_receiver_contrasts(rows, start, cut, groups=groups, lag=lag)
            va = temporal_contrasts.split_receiver_contrasts(rows, np.nextafter(cut, np.inf), stop, groups=groups, lag=lag)
            output['comparisons'][f'{name}/{int(lag)}s'] = fit_predict(tr, va)
    return output
