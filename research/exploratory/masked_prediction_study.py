"""One exploratory native transfer comparison, using the existing RF scorer.

Run as a module with --output NEW_DIRECTORY --comparison ORIGINAL_SUPPORT_JSON.
All predictions are written before any held RF scoring or comparator access.
This is a calculation/report, not an experiment runner or production option.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

import numpy as np

from research.kinematic import masked_prediction, mask_consistent_prediction, gnss_combinations, network_closures
from research.exploratory.reference_network_clocks import native

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / 'research/exploratory/results/stable_source_differential_v1.json.gz'
INPUT_SHA = '56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020'


def write(path, value):
    raw = (json.dumps(native(value), allow_nan=False, separators=(',', ':')) + '\n').encode()
    if str(path).endswith('.gz'):
        raw = gzip.compress(raw, mtime=0)
    with path.open('xb') as handle:
        handle.write(raw)


def summarize(scored, comparison, *, primary_method='observed_coordinates'):
    result = {}
    methods = ('wet', 'observed_coordinates', 'whole_row_ablation') if primary_method=='observed_coordinates' else ('wet',primary_method)
    for method in methods:
        combined, folds = {}, {}
        for lag in ('30', '300'):
            pooled = []
            missing = 0
            for fold, support in comparison['support'][lag].items():
                index = {tuple((p[k] for k in ('station', 'reference', 'time_s'))):p['z']
                         for inc in scored[fold].get(method, {}).get('increment_errors', [])
                         if inc['lag_s'] == float(lag) for p in inc['rows']}
                absent = [key for key in support if tuple(key) not in index]
                values = [index[tuple(key)] for key in support if tuple(key) in index]
                missing += len(absent)
                pooled.extend(values)
                rms = np.sqrt(np.mean(np.asarray(values) ** 2, axis=0)) if values else None
                folds.setdefault(fold, {})[lag] = {'count':len(values), 'missing_keys':absent,
                    'code_phase_rms_m':rms}
            combined[lag] = {'count':len(pooled), 'missing_count':missing,
                'code_phase_rms_m':np.sqrt(np.mean(np.asarray(pooled) ** 2, axis=0)) if pooled else None}
        result[method] = {'pooled':combined, 'folds':folds}
    primary = result[primary_method]
    prior = comparison['direct_comparison']
    primary_rms = primary['pooled']['300']['code_phase_rms_m']
    complete = all(primary['pooled'][lag]['missing_count'] == 0 for lag in ('30','300'))
    checks = {'complete_support':complete,
        'primary_10_percent':complete and primary_rms is not None and float(primary_rms[1]) <= .9 * prior['models']['wet']['300']['phase_rms_m']}
    checks['original_wet_baseline_reproduced'] = all(
        result['wet']['pooled'][lag]['code_phase_rms_m'] is not None and
        np.allclose(result['wet']['pooled'][lag]['code_phase_rms_m'],
                    [prior['models']['wet'][lag]['code_rms_m'], prior['models']['wet'][lag]['phase_rms_m']],
                    rtol=1e-8, atol=1e-10) for lag in ('30','300'))
    checks['secondary'] = complete and all(
        primary['pooled'][lag]['code_phase_rms_m'] is not None and
        float(primary['pooled'][lag]['code_phase_rms_m'][axis]) <= 1.02 * min(
            model[lag][field] for model in prior['models'].values())
        for lag,axis,field in [('30',0,'code_rms_m'),('300',0,'code_rms_m'),('30',1,'phase_rms_m')])
    ratios = {fold:float(record['300']['code_phase_rms_m'][1]) / prior['by_fold'][fold]['wet']['300']['phase_rms_m']
              for fold,record in primary['folds'].items() if record['300']['code_phase_rms_m'] is not None}
    checks['at_least_four_folds_improve'] = sum(value < 1. for value in ratios.values()) >= 4
    checks['no_fold_over_ten_percent_worse'] = len(ratios) == 5 and max(ratios.values()) <= 1.1
    return {'methods':result, 'criteria':checks, 'passes_all':all(checks.values()), 'primary_fold_ratios':ratios}


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--comparison', type=Path)
    parser.add_argument('--mask-consistent', action='store_true',
                        help='one conditional wet-process correction trained on excluded errors')
    parser.add_argument('--diagnose-mask', action='store_true',
                        help='inspect original error/covariance images without correction or held scoring')
    args = parser.parse_args()
    if args.mask_consistent and args.diagnose_mask:
        parser.error('select prediction or diagnosis, not both')
    if not args.diagnose_mask and args.comparison is None:
        parser.error('--comparison is required for a predictive comparison')
    args.output.mkdir(exist_ok=False)
    raw = INPUT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA:
        raise ValueError('stable input hash mismatch; no prediction or score produced')
    data = json.loads(gzip.decompress(raw))
    start = time.perf_counter()
    operator_model = args.mask_consistent or args.diagnose_mask
    predictor = mask_consistent_prediction if operator_model else masked_prediction
    primary_method = 'covariance_diagnosis' if args.diagnose_mask else 'mask_consistent' if args.mask_consistent else 'observed_coordinates'
    producers = ['research/kinematic/'+predictor.__name__.split('.')[-1]+'.py',
                 'research/exploratory/masked_prediction_study.py']
    if operator_model:
        producers += ['research/kinematic/'+name+'.py' for name in
            ('network_clocks','network_closures','source_geometry','phase_continuity','gnss_combinations')]
    output = {'input_sha256':INPUT_SHA, 'implementation_revision':subprocess.check_output(
        ['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        'source_sha256':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in producers},
        'assisted_transfer':not operator_model, 'primary_method':primary_method,
        'prospective_confirmation':False, 'physical_covariance_qualified':False,
        'candidate_products_used':False, 'folds':{}}
    for fold, candidate in data['candidates'].items():
        if 'source_profile' not in candidate:
            continue
        print(fold, 'preparing', flush=True)
        options = {'diagnose_only':True} if args.diagnose_mask else {}
        output['folds'][fold] = predictor.prepare_future_links(
            candidate['reference_rows'], fold, gnss_combinations.assumed_endpoint_covariance(),**options)
        if args.diagnose_mask:
            baseline=output['folds'][fold]['baseline']
            output['folds'][fold]['baseline']={k:baseline[k] for k in (
                'status','training_stop_s','held_links','training_row_count','withheld_row_count') if k in baseline}
        print(fold, output['folds'][fold]['model_status'], flush=True)
    if args.diagnose_mask:
        output.update(diagnostic_only=True,held_scores_computed=False,correction_variance_fitted=False,
                      elapsed_seconds=time.perf_counter()-start)
        write(args.output/'covariance-diagnosis.json.gz',output)
        print('Covariance diagnosis saved; no new correction or held scoring.',flush=True)
        return
    output['all_predictions_fixed_before_scoring'] = True
    output['elapsed_before_scoring_seconds'] = time.perf_counter() - start
    write(args.output/'predictions-before-scoring.json.gz', output)
    # Only now open held observations for the native scorer and the old support.
    scored = {}
    for fold, record in output['folds'].items():
        methods = {'wet':record['baseline'], **record.get('variants', {})}
        scored[fold] = {label:network_closures.score_future_links(prediction, data['candidates'][fold]['reference_rows'])
                        for label,prediction in methods.items()}
    write(args.output/'native-scores.json.gz', scored)
    comparison_raw = args.comparison.read_bytes()
    comparison = json.loads(comparison_raw)
    summary = summarize(scored, comparison, primary_method=primary_method)
    summary.update(input_sha256=INPUT_SHA, comparison_sha256=hashlib.sha256(comparison_raw).hexdigest(),
                   elapsed_seconds=time.perf_counter()-start)
    write(args.output/'summary.json', summary)
    print(json.dumps(native(summary)), flush=True)


if __name__ == '__main__':
    main()
