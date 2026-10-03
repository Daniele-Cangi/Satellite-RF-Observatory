"""Training-only transfer of external pair innovations to a later local recording."""

from collections import Counter
import math
from statistics import median

from .benchmark import fit_baselines, pair_values, score_epoch
from .fixed_site import evaluate_epoch, load_inputs, observation_epochs, validate_window


METHODS = ('local', 'unit_transfer', 'fitted_transfer')


def innovations(epoch, baselines, pairs):
    values = pair_values(epoch)
    return {pair: {mode: values[pair][mode] - baselines[pair]['centres_m'][mode]
                   for mode in ('local', 'network')}
            for pair in pairs}


def fit_transfer(training, baselines, minimum_epochs):
    """One zero-intercept slope, with each eligible epoch having equal weight.

    Pair-specific training medians remove static offsets. Pairs within an epoch
    share measurements: their count is not a sample size for uncertainty.
    """
    products, squares = [], []
    for epoch in training:
        row = score_epoch(epoch, baselines)
        if row['status'] != 'EVALUATED':
            continue
        values = innovations(epoch, baselines, row['scored_pairs']).values()
        values = list(values)
        products.append(sum(v['local'] * v['network'] for v in values) / len(values))
        squares.append(sum(v['network'] ** 2 for v in values) / len(values))
    result = {'status': 'INSUFFICIENT_TRAINING', 'eligible_training_epochs': len(products),
              'coefficient': None, 'mean_cross_product_m2': None,
              'mean_remote_square_m2': None}
    if len(products) < minimum_epochs:
        return result
    cross = sum(products) / len(products)
    square = sum(squares) / len(squares)
    result.update(mean_cross_product_m2=cross, mean_remote_square_m2=square)
    if square == 0:
        result['status'] = 'NO_REMOTE_TRAINING_VARIATION'
        return result
    coefficient = cross / square
    if not all(math.isfinite(v) for v in (cross, square, coefficient)):
        result['status'] = 'TRANSFER_FIT_FAILED'
        return result
    result.update(status='FITTED', coefficient=coefficient)
    return result


def transfer_epoch(epoch, baselines, fit):
    row = score_epoch(epoch, baselines)
    if row['status'] != 'EVALUATED':
        return row
    if fit['status'] != 'FITTED':
        row['status'] = fit['status']
        return row
    values = innovations(epoch, baselines, row['scored_pairs'])
    errors = {pair: {'local': v['local'],
                     'unit_transfer': v['local'] - v['network'],
                     'fitted_transfer': v['local'] - fit['coefficient'] * v['network']}
              for pair, v in values.items()}
    row['pair_innovations_m'] = values
    row['pair_errors_m'] = errors
    row['transfer_metrics'] = {
        method: {'mean_square_m2': sum(v[method] ** 2 for v in errors.values()) / len(errors),
                 'max_absolute_m': max(abs(v[method]) for v in errors.values())}
        for method in METHODS}
    return row


def summarize_transfer(rows):
    eligible = [row for row in rows if 'transfer_metrics' in row]
    metrics = {}
    if eligible:
        local_error = [row['transfer_metrics']['local']['mean_square_m2'] for row in eligible]
        local_mean = sum(local_error) / len(local_error)
        for method in METHODS:
            errors = [row['transfer_metrics'][method]['mean_square_m2'] for row in eligible]
            mean_square = sum(errors) / len(errors)
            metrics[method] = {
                'epoch_weighted_pair_rms_m': math.sqrt(mean_square),
                'mean_square_m2': mean_square,
                'median_epoch_max_absolute_m': median(
                    row['transfer_metrics'][method]['max_absolute_m'] for row in eligible),
                'fractional_mse_reduction_vs_local': 1 - mean_square / local_mean if local_mean else None,
                'improved_epochs_vs_local': sum(a < b for a, b in zip(errors, local_error)),
                'worsened_epochs_vs_local': sum(a > b for a, b in zip(errors, local_error)),
                'equal_epochs_vs_local': sum(a == b for a, b in zip(errors, local_error))}
    # Cardinality is visible both per epoch and in summaries. No normalization
    # claims these correlated pairs are independent or statistically comparable.
    by_count = {}
    for count in sorted({len(row['scored_pairs']) for row in eligible}):
        group = [row for row in eligible if len(row['scored_pairs']) == count]
        by_count[str(count)] = {
            'epochs': len(group),
            'rms_m': {method: math.sqrt(sum(row['transfer_metrics'][method]['mean_square_m2']
                                          for row in group) / len(group)) for method in METHODS}}
    return {'requested_epochs': len(rows), 'evaluated_epochs': len(eligible),
            'status_counts': dict(sorted(Counter(row['status'] for row in rows).items())),
            'metrics': metrics, 'by_scored_pair_count': by_count}


def reference_transfer(local_path, references, navigation_path, day_gpst, *,
                       start_s, train_stop_s, stop_s, minimum_training=5,
                       minimum_fit_epochs=20, local_ecef=None, position_source=None):
    """Compare no correction, unit correction and a training-only learned slope.

    This predicts exposed original residual variation, not RF attacks. All
    methods use identical qualified pairs and eligible epochs. No detection
    threshold, evaluation tuning, reference selection or fallback is performed.
    """
    validate_window(start_s, train_stop_s)
    validate_window(train_stop_s, stop_s)
    if any(not isinstance(n, int) or isinstance(n, bool) or n < 1
           for n in (minimum_training, minimum_fit_epochs)):
        raise ValueError('positive integer training sample counts required')
    data, positions, navigation, context, sources = load_inputs(
        local_path, references, navigation_path, day_gpst,
        local_ecef=local_ecef, position_source=position_source)
    epochs = [evaluate_epoch(time_s, values, positions, navigation, context)
              for time_s, values in observation_epochs(data, start_s, stop_s)]
    training = [epoch for epoch in epochs if epoch['gpst_s'] < train_stop_s]
    baselines = fit_baselines(training, minimum_training)
    fit = fit_transfer(training, baselines, minimum_fit_epochs)
    rows = [transfer_epoch(epoch, baselines, fit) for epoch in epochs]
    return {
        'schema': 'pnt-reference-transfer-v1',
        'status': 'EXPLORATORY_TRANSFER' if fit['status'] == 'FITTED' else fit['status'],
        'day_gpst': context.day.date().isoformat(), 'sources': sources,
        'parameters': {'boundaries_gpst_s': [start_s, train_stop_s, stop_s],
                       'minimum_training_per_pair': minimum_training,
                       'minimum_fit_epochs': minimum_fit_epochs},
        'method': 'training medians per pair; one zero-intercept local-on-mean-remote slope; '
                  'equal epoch weighting; fixed later evaluation; no correction vs unit vs fitted transfer',
        'baselines': baselines, 'fit': fit,
        'training': summarize_transfer([row for row in rows if row['gpst_s'] < train_stop_s]),
        'evaluation': summarize_transfer([row for row in rows if row['gpst_s'] >= train_stop_s]),
        'epochs': rows,
        'assessments': {'recorded_RF_detection_gain': 'NOT_ASSESSED',
                        'absolute_time': 'INSUFFICIENT_EVIDENCE'},
        'limits': [
            'Original observations are already exposed and unlabeled; this is residual prediction, not benign truth.',
            'A smaller residual is not position accuracy, RF authenticity or detection benefit at equal false alarms.',
            'Local observations are admitted in supervised training; this is not target-independent calibration.',
            'A shared residual component can be physical, a model error or a common harmful manipulation.',
            'No adaptation uses evaluation values; a contaminated training interval can teach a harmful correction.',
            'One unconstrained slope is estimated; no noise floor, regularization or uncertainty bound is qualified.',
            'Pairs and adjacent epochs are correlated; cardinality groups are descriptive, not independent trials.',
            'Receivers, time windows and a common navigation product are not independent incidents.',
            'No reference is removed, downweighted or replaced based on evaluation behavior.',
            'Matched support, coordinate, signal, clock and model limitations of pnt analyze still apply.',
        ]}
