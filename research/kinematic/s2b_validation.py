"""Bounded RINEX/reference bridge validation; synthetic fixture data only."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from .reference_fixture import BASE_SECOND, CLOCK, DAY, REFERENCES, TAGS, TARGET, TYPES, fixture_texts
from .reference_bridge import calibrate_references, sample_covariance
from .rinex_observations import RinexRejected, parse_reference_observations

RAW_COVARIANCE = np.diag([1., 1., .01**2, .01**2])


def parse_fixture(text):
    return parse_reference_observations(text, target=TARGET, references=REFERENCES,
        tags_s=TAGS, step_s=30., base_day=DAY, base_second=BASE_SECOND, raw_covariance=RAW_COVARIANCE)


def perturb_observations(text, case):
    """Fixed adverse cases, preserving the planned tags, receivers and signals."""
    lines, epoch_index = [], -1
    for row in text.splitlines():
        if row.startswith('>'):
            epoch_index += 1
        if row.startswith('G01') and epoch_index >= 0:
            if case == 'reversed_doppler':
                for name in ('D1C', 'D2W'):
                    start = 3+16*TYPES.index(name)
                    row = row[:start]+f'{-float(row[start:start+14]):14.3f}'+row[start+14:]
            if case == 'code_clock_step' and epoch_index >= 6:
                for name in ('C1C', 'C2W'):
                    start = 3+16*TYPES.index(name)
                    row = row[:start]+f'{float(row[start:start+14])+300.:14.3f}'+row[start+14:]
            if case == 'missing_doppler' and epoch_index == 4:
                start = 3+16*TYPES.index('D2W')
                row = row[:start]+' '*16+row[start+16:]
        if case == 'receiver_reset' and row.startswith('>') and epoch_index == 4:
            # The epoch flag is column 32 in the generator's fixed layout.
            parts = row.split()
            parts[7] = '1'
            row = ' '.join(parts)
        lines.append(row)
    return '\n'.join(lines)+'\n'


def evaluate(observations, navigation, case):
    try:
        parsed = parse_fixture(perturb_observations(observations, case))
    except RinexRejected as error:
        return {'case': case, 'status': 'RINEX_REJECTED', 'reason': error.reason,
                'real_rf_qualified': False}
    result = calibrate_references(parsed, navigation, covariance=sample_covariance(parsed),
                                  propagation='vacuum', max_age_s=100. if case == 'stale_navigation' else 7200.)
    return {'case': case, 'import': parsed, 'calibration': result,
            'status': result['status'], 'real_rf_qualified': result['real_rf_qualified']}


def run():
    observations, navigation = fixture_texts()
    cases = [evaluate(observations, navigation, case) for case in (
        'nominal_quantized', 'reversed_doppler', 'code_clock_step', 'missing_doppler',
        'receiver_reset', 'stale_navigation')]
    nominal = cases[0]['calibration']
    clock_error = (np.array(nominal['clock_coefficients'])-CLOCK).tolist()
    # Changes to excluded numeric payloads must change raw hashes but not the
    # admitted reference observations, navigation or calibration coefficients.
    poisoned_obs = observations.replace('TARGET PAYLOAD MUST NEVER BE DECODED', 'nan inf 1e999 MALICIOUS NUMBERS')
    poisoned_nav = navigation.replace('POISONED TARGET FIELD', 'nan inf 1e999')
    poison = evaluate(poisoned_obs, poisoned_nav, 'nominal_quantized')
    equal_admitted = cases[0]['import']['admitted_observations_sha256'] == poison['import']['admitted_observations_sha256']
    equal_nav = nominal['admitted_navigation_sha256'] == poison['calibration']['admitted_navigation_sha256']
    criteria = {
        'nominal_reference_model_accepted': cases[0]['status'] == 'REFERENCE_MODEL_ACCEPTED',
        'clock_offset_within_1cm': abs(clock_error[0]) < .01,
        'clock_drift_within_10um_s': abs(clock_error[1]) < 1e-5,
        'unused_doppler_within_1mm_s': max(map(abs, nominal['doppler_residuals_m_s'])) < .001,
        'wrong_doppler_sign_rejected': cases[1]['status'] == 'REFERENCE_DOPPLER_REJECTED',
        'clock_step_rejected_before_doppler': cases[2]['status'] == 'REFERENCE_CODE_REJECTED'
            and 'doppler_p' not in cases[2]['calibration'],
        'missing_sample_stops_calibration': cases[3]['status'] == 'REFERENCE_WINDOW_REJECTED'
            and 'clock_coefficients' not in cases[3]['calibration'],
        'receiver_reset_rejected': cases[4]['status'] == 'RINEX_REJECTED',
        'stale_reference_rejected': cases[5]['status'] == 'REFERENCE_MODEL_UNAVAILABLE',
        'excluded_target_poisoning_invariant': equal_admitted and equal_nav
            and nominal['clock_coefficients'] == poison['calibration']['clock_coefficients'],
        'no_real_rf_qualification_claim': all(row['real_rf_qualified'] is False for row in cases)}
    root = Path(__file__).resolve().parents[2]
    files = [root/'research/kinematic'/name for name in (
        's2b_validation.py', 'reference_fixture.py', 'rinex_observations.py', 'reference_bridge.py',
        'doppler.py', 'clock_drift.py', 'receiver_time.py')]
    files += [root/'positioning'/name for name in ('calibration.py', 'navigation.py', 'context.py', 'solver.py', 'errors.py')]
    return {'schema': 'rinex-reference-bridge-synthetic-v1',
        'scope': 'S2b reference-only RINEX integration; no real receiver qualification, target fit or new satellite confirmation.',
        'design': {'day_gpst': DAY, 'base_second': BASE_SECOND, 'tags_s': TAGS.tolist(),
                   'references': REFERENCES, 'excluded_target': TARGET, 'receiver_clock_truth': CLOCK.tolist(),
                   'raw_covariance_order': ['C1C_m', 'C2W_m', 'D1C_Hz', 'D2W_Hz'],
                   'raw_covariance': RAW_COVARIANCE.tolist(), 'propagation': 'vacuum',
                   'reference_code_fit_p_threshold': .01, 'unused_doppler_p_threshold': .01},
        'fixture_sha256': {'observations': hashlib.sha256(observations.encode()).hexdigest(),
                          'navigation': hashlib.sha256(navigation.encode()).hexdigest()},
        'sources_sha256': {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'clock_error_m_and_m_s': clock_error, 'criteria': criteria, 'criteria_pass': all(criteria.values()),
        'cases': cases}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to overwrite an existing report')
    report = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    print(json.dumps({'criteria': report['criteria'], 'clock_error': report['clock_error_m_and_m_s']}, indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
