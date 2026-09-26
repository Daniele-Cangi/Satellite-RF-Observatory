"""Post-fit diagnostic comparison of frozen G12 states to the historical SP3."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np

from experiments.positioning_g12_doy248.sources.verification.verification import compare_oracle
from .real_phase import BASE, digest
from ..kinematic.synthetic import native

REPORT = BASE/'results/real_target_interval_v2.json'
RECEIPT = BASE.parents[1]/'experiments/positioning_g12_doy248/oracle_access.json'


def moments(values):
    data = np.asarray(values, float)
    return {'count': len(data), 'rms_m': float(np.sqrt(np.mean(data*data))) if len(data) else None,
            'median_m': float(np.median(data)) if len(data) else None,
            'max_m': float(np.max(data)) if len(data) else None}


def run(oracle_path):
    report_bytes = REPORT.read_bytes()
    report = json.loads(report_bytes)
    receipt_bytes = RECEIPT.read_bytes()
    receipt = json.loads(receipt_bytes)
    oracle_bytes = oracle_path.read_bytes()
    if digest(oracle_bytes) != receipt['sha256']:
        raise ValueError('oracle bytes differ from historical receipt')
    if (report['target_orbit_accessed'] or report['physical_covariance_qualified']
            or report['status_counts'] != {'EVALUATED': 20}
            or len(report['cases']) != 20):
        raise ValueError('frozen RF report differs')
    content = gzip.decompress(oracle_bytes).decode('ascii')
    rows = []
    for case in report['cases']:
        t = case['start_gpst_s']+60
        fits = {}
        for name in ('code_only', 'code_phase'):
            fit = case['fits'][name]
            if fit['status'] not in {'CONDITIONAL_INTERVAL_MODEL_ACCEPTED', 'MODEL_REJECTED'}:
                fits[name] = {'status': fit['status'], 'oracle_error_m': None}
                continue
            # The inverse's ECEF p0 is at the GPST tag origin t. SP3 is sampled
            # at that same nominal GPST epoch, not at the earlier RF transmit.
            comparison = compare_oracle(content, 'G12', '2026-09-05', t,
                                        fit['state'][:3], 0.)
            fits[name] = {'status': fit['status'], 'oracle_error_m': comparison['error_3d_m'],
                          'error_xyz_m': comparison['error_xyz_m'],
                          'oracle_xyz_m': comparison['oracle_ecef_at_emission_m'],
                          'interpolation_control_m': comparison['oracle_interpolation_control_m'],
                          'oracle_nodes_gpst_s': comparison['oracle_nodes_gpst_s']}
        rows.append({'start_gpst_s': case['start_gpst_s'], 'position_epoch_gpst_s': t,
                     'fits': fits})
    accepted = [r for r in rows if r['fits']['code_phase']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED']
    rejected = [r for r in rows if r['fits']['code_phase']['status'] == 'MODEL_REJECTED']
    code_all = [r['fits']['code_only']['oracle_error_m'] for r in rows]
    code_paired = [r['fits']['code_only']['oracle_error_m'] for r in accepted]
    phase_paired = [r['fits']['code_phase']['oracle_error_m'] for r in accepted]
    return native({'schema': 'exploratory-real-target-oracle-v2',
        'scope': 'Post-frozen RF exploratory diagnostic against historical IGS rapid SP3. Shared upstream GNSS products are possible; this is not statistically independent truth or a physical uncertainty bound. Rejected phase fits are retained but not promoted.',
        'target_state_used_only_for_diagnostic': True,
        'frozen_rf_report_sha256': digest(report_bytes), 'historical_oracle_receipt_sha256': digest(receipt_bytes),
        'oracle_sha256': digest(oracle_bytes), 'oracle_url': receipt['url'],
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'counts': {'phase_status': dict(Counter(r['fits']['code_phase']['status'] for r in rows))},
        'summary': {'code_all': moments(code_all), 'code_on_phase_accepted': moments(code_paired),
                    'phase_accepted': moments(phase_paired),
                    'phase_rejected_diagnostic': moments([r['fits']['code_phase']['oracle_error_m'] for r in rejected]),
                    'paired_accepted_phase_better_count': sum(p < c for p, c in zip(phase_paired, code_paired)),
                    'paired_accepted_phase_worse_count': sum(p > c for p, c in zip(phase_paired, code_paired))},
        'cases': rows})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oracle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run(args.oracle)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, separators=(',', ':'), allow_nan=False)+'\n',
                           encoding='utf-8', newline='\n')
