"""Descriptive broadcast/IGS product discrepancies, never estimator corrections."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import numpy as np

from positioning.calibration import C, state_and_clock
from .reference_sensitivity import load_inputs


def extract_references(text, references, target):
    """Strip all unselected state records as text, before numeric conversion.

    Output is a restricted extract, not a complete standards-compliant SP3 file.
    """
    references = set(references)
    if target in references:
        raise ValueError('target reference forbidden')
    return '\n'.join(line for line in text.splitlines()
                     if line.startswith(('#', '%c', '/*', '*')) or line == 'EOF'
                     or (line.startswith('P') and line[1:4] in references)) + '\n'


def parse_extract(text, references, target, date):
    references = set(references)
    if target in references:
        raise ValueError('target reference forbidden')
    lines = text.splitlines()
    if not lines or lines[0][:3] not in ('#cP', '#dP') or lines[-1] != 'EOF':
        raise ValueError('expected complete position-mode SP3 extract')
    expected_epochs = int(lines[0][32:39])
    time_headers = [line for line in lines if line.startswith('%c')]
    if not time_headers or time_headers[0][9:12] != 'GPS':
        raise ValueError('explicit GPS timescale required')
    epochs, current = {}, None
    for line in lines:
        if line.startswith('*'):
            fields = line[1:].split()
            if '-'.join(f'{int(v):02d}' for v in fields[:3]) != date:
                raise ValueError('SP3 epoch outside declared day')
            hour, minute, second = int(fields[3]), int(fields[4]), float(fields[5])
            if not (0 <= hour < 24 and 0 <= minute < 60 and 0 <= second < 60):
                raise ValueError('invalid GPS time')
            current = hour * 3600 + minute * 60 + second
            if epochs and current <= max(epochs):
                raise ValueError('duplicate or unordered epoch')
            epochs[current] = {}
        elif line.startswith('P'):
            sv = line[1:4]
            if sv == target or sv not in references:
                raise ValueError('unadmitted satellite record')
            if current is None or sv in epochs[current]:
                raise ValueError('missing epoch or duplicate satellite')
            values = np.array([float(line[4 + 14*j:18 + 14*j]) for j in range(4)])
            flags = line.ljust(80)
            reason = ('NONFINITE' if not np.isfinite(values).all() else
                      'MISSING_POSITION' if np.any(values[:3] == 0.) else
                      'MISSING_CLOCK' if abs(values[3]) >= 999999 else
                      'FLAGGED_PRODUCT' if any(flags[i] != ' ' for i in (74, 75, 78, 79)) else None)
            epochs[current][sv] = ({'status': reason} if reason else
                                    {'status': 'AVAILABLE', 'xyz_m': (values[:3]*1000).tolist(),
                                     'clock_s': float(values[3]*1e-6)})
    if len(epochs) != expected_epochs:
        raise ValueError('epoch count differs from header')
    return epochs


def run(archive, extract_path, receipt_path):
    admitted, context, nav, hashes = load_inputs(archive)
    refs = sorted({sv for name in admitted['fit_stations']
                   for obs in admitted['stations'][name]['reference_observations']
                   for sv in obs['if_code_m'] if sv in nav})
    content = Path(extract_path).read_bytes()
    receipt_bytes = Path(receipt_path).read_bytes()
    receipt = json.loads(receipt_bytes)
    if (receipt['extract_sha256'] != hashlib.sha256(content).hexdigest()
            or receipt['target_excluded'] != context.target or receipt['references'] != refs):
        raise ValueError('reference extract differs from admission receipt')
    epochs = parse_extract(content.decode('ascii'), refs, context.target, context.date_gpst)
    rows, common, complete = [], [], []
    for t, samples in epochs.items():
        block = []
        for sv in refs:
            row = {'time_gpst_s': t, 'reference': sv}
            sample = samples.get(sv, {'status': 'MISSING_SP3_RECORD'})
            row['status'] = sample['status']
            if sample['status'] == 'AVAILABLE':
                record = min(nav[sv], key=lambda r: abs(t - (r.toc_gps-context.day).total_seconds()))
                age = t - (record.toc_gps-context.day).total_seconds()
                row['broadcast_age_from_toc_s'] = age
                if abs(age) > 7200:
                    row['status'] = 'BROADCAST_TOO_OLD'
                else:
                    xyz, corrected_clock = state_and_clock(record, t, context)
                    polynomial = record.af0_s + record.af1_s_s*age + record.af2_s_s2*age**2
                    delta = xyz - np.array(sample['xyz_m'])
                    row.update(status='COMPARED', delta_xyz_m=delta.tolist(),
                               orbit_discrepancy_norm_m=float(np.linalg.norm(delta)),
                               clock_polynomial_minus_sp3_m=float(C*(polynomial-sample['clock_s'])),
                               broadcast_periodic_relativistic_term_m=float(C*(corrected_clock-polynomial)))
            block.append(row)
        valid = [r for r in block if r['status'] == 'COMPARED']
        # Use a fixed reference set for centered clock statistics and covariance.
        if len(valid) == len(refs):
            values = np.array([r['clock_polynomial_minus_sp3_m'] for r in block])
            mean = float(values.mean())
            centered = values - mean
            common.append({'time_gpst_s': t, 'mean_clock_discrepancy_m': mean})
            complete.append(centered)
            for row, value in zip(block, centered):
                row['ensemble_centered_clock_discrepancy_m'] = float(value)
        rows.extend(block)
    valid = [r for r in rows if r['status'] == 'COMPARED']
    def stats(values):
        return {'count': len(values), 'rms': float(np.sqrt(np.mean(np.square(values)))) if values else None,
                'maximum_absolute': float(np.max(np.abs(values))) if values else None}
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__), Path(__file__).with_name('reference_sensitivity.py')]
    sources += [root/'positioning'/p for p in ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'reference-product-discrepancy-v1', 'target': context.target,
            'date_gpst': context.date_gpst, 'references': refs, 'product_receipt': receipt,
            'input_sha256': hashes | {'reference_extract': hashlib.sha256(content).hexdigest(),
                                      'product_receipt': hashlib.sha256(receipt_bytes).hexdigest()},
            'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
            'scope': 'Descriptive same-epoch product comparison across one exposed day. No interpolation or fit corrections.',
            'limitations': ['Orbit reference-point/frame differences are not corrected.',
                           'Clock polynomials and SP3 fields compared without treating either as truth; periodic term reported separately.',
                           'Code-bias and clock datum alignment remain unqualified.',
                           'Epoch-wise ensemble centering removes a common component and induces correlations.',
                           'Sample covariance describes this day only, not physical error covariance or a 95% bound.'],
            'target_state_parsed': False, 'new_confirmation': False, 'qualified_error_budget': False,
            'epoch_count': len(epochs), 'case_count': len(rows),
            'status_counts': dict(Counter(r['status'] for r in rows)),
            'orbit_discrepancy_m': stats([r['orbit_discrepancy_norm_m'] for r in valid]),
            'raw_clock_discrepancy_m': stats([r['clock_polynomial_minus_sp3_m'] for r in valid]),
            'centered_clock_discrepancy_m': stats([r['ensemble_centered_clock_discrepancy_m'] for r in valid
                                                  if 'ensemble_centered_clock_discrepancy_m' in r]),
            'complete_epoch_count': len(complete), 'common_clock_by_epoch': common,
            'centered_clock_sample_covariance_m2': np.cov(np.array(complete), rowvar=False, ddof=1).tolist()
                                                  if len(complete) > 1 and len(refs) > 1 else None,
            'rows': rows}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'extract', 'receipt', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.archive.resolve()):
        parser.error('new output outside preserved archive required')
    result = run(args.archive, args.extract, args.receipt)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write('\n')
