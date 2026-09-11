"""Fixed full-RINEX phase reference bridge study, synthetic only."""
import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy

from .phase_reference_bridge import calibrate_phase_references
from .reference_fixture import BASE_SECOND, CLOCK, DAY, REFERENCES, TARGET, TYPES, fixture_texts
from .rinex_phase_observations import RinexRejected, parse_reference_phase_file
from .synthetic import native

TAGS = np.arange(-330., 1., 30.)
REPLACEMENTS = {'D1C': 'C5X', 'D1W': 'L5X', 'D2W': 'S5X'}
PHASE_TYPES = tuple(REPLACEMENTS.get(name, name) for name in TYPES)
RAW_PAIR_COVARIANCE = np.array([[1., 0., .003, 0.], [0., 1., 0., -.001],
                                [.003, 0., .0001, 0.], [0., -.001, 0., .0001]])


def phase_fixture_texts():
    """Retain independent S2b generated phase/code values; remove Doppler fields.

    Replace unneeded D declarations with blank optional GPS fields, retaining
    the header continuation test. Target payload remains poisoned text.
    """
    observations, navigation = fixture_texts()
    rows = []
    for line in observations.splitlines():
        if line[60:80].strip() == 'SYS / # / OBS TYPES':
            for old, new in REPLACEMENTS.items():
                line = line.replace(old, new)
        if line[:3] in REFERENCES:
            for name in REPLACEMENTS:
                start = 3+16*TYPES.index(name)
                line = line[:start]+' '*16+line[start+16:]
        rows.append(line)
    return '\n'.join(rows)+'\n', navigation


def parse_fixture(content):
    return parse_reference_phase_file(content, target=TARGET, references=REFERENCES, tags_s=TAGS,
        step_s=30., base_day=DAY, base_second=BASE_SECOND,
        raw_covariance=np.kron(np.eye(len(TAGS)*len(REFERENCES)), RAW_PAIR_COVARIANCE))


def perturb(content, case):
    rows, epoch = [], -1
    for line in content.splitlines():
        if line.startswith('>'):
            epoch += 1
            if case == 'clock_reset' and epoch == 5:
                fields = line.split()
                fields[7] = '1'
                line = ' '.join(fields)
        if line[:3] in REFERENCES:
            for name in ('C1C', 'C2W', 'L1C', 'L2W'):
                start = 3+16*PHASE_TYPES.index(name)
                field = line[start:start+16]
                value = float(field[:14])
                if case == 'constant_ambiguities' and name.startswith('L'):
                    value += 3000 if name == 'L1C' else -5000
                if case == 'unflagged_cycle_slip' and line[:3] == 'G01' and epoch >= 5 and name == 'L1C':
                    value += 1
                if case == 'small_common_phase_drift' and name.startswith('L'):
                    frequency = 1575.42e6 if name == 'L1C' else 1227.60e6
                    value += .001*(epoch*30)*frequency/299792458.
                if case == 'code_clock_step' and line[:3] == 'G01' and epoch >= 5 and name.startswith('C'):
                    value += 300
                field = f'{value:14.3f}'+field[14:]
                if case == 'missing_phase' and line[:3] == 'G01' and epoch == 5 and name == 'L2W':
                    field = ' '*16
                if case == 'flagged_slip' and line[:3] == 'G01' and epoch == 5 and name == 'L1C':
                    field = field[:14]+'1 '
                line = line[:start]+field+line[start+16:]
        rows.append(line)
    return '\n'.join(rows)+'\n'


def evaluate(observations, navigation, case):
    try:
        parsed = parse_fixture(perturb(observations, case))
    except RinexRejected as error:
        return {'case': case, 'status': 'RINEX_REJECTED', 'reason': error.reason, 'real_rf_qualified': False}
    result = calibrate_phase_references(parsed, navigation, propagation='vacuum',
                                        max_age_s=100. if case == 'stale_navigation' else 7200.)
    return {'case': case, 'status': result['status'], 'calibration': result,
            'import_status': parsed['status'], 'real_rf_qualified': False}


def run():
    observations, navigation = phase_fixture_texts()
    names = ('nominal', 'constant_ambiguities', 'unflagged_cycle_slip', 'flagged_slip', 'missing_phase',
             'clock_reset', 'code_clock_step', 'stale_navigation', 'small_common_phase_drift')
    cases = {name: evaluate(observations, navigation, name) for name in names}
    nominal = cases['nominal']['calibration']
    error = np.asarray(nominal['clock_coefficients'])-CLOCK
    poisoned = evaluate(observations.replace('TARGET PAYLOAD MUST NEVER BE DECODED', 'nan inf 1e999'),
                        navigation.replace('POISONED TARGET FIELD', 'nan inf 1e999'), 'nominal')['calibration']
    criteria = {
        'nominal_without_doppler_accepted': cases['nominal']['status'] == 'REFERENCE_PHASE_MODEL_ACCEPTED',
        'clock_offset_within_1cm': abs(error[0]) < .01,
        'clock_drift_within_10um_s': abs(error[1]) < 1e-5,
        'interval_phase_prediction_within_0_1mm_s': max(abs(nominal['phase_residuals_m_s'])) < .0001,
        'constant_ambiguities_cancel': cases['constant_ambiguities']['status'] == 'REFERENCE_PHASE_MODEL_ACCEPTED',
        'unflagged_one_cycle_slip_rejected_by_reference_residuals': cases['unflagged_cycle_slip']['status'] == 'REFERENCE_PHASE_RESIDUAL_REJECTED',
        'phase_does_not_refit_code_clock': bool(np.array_equal(cases['unflagged_cycle_slip']['calibration']['clock_coefficients'], nominal['clock_coefficients'])),
        'flagged_slip_and_gap_stop_before_clock_fit': all(cases[name]['status'] == 'REFERENCE_PHASE_WINDOW_REJECTED'
            and 'clock_coefficients' not in cases[name]['calibration'] for name in ('flagged_slip', 'missing_phase')),
        'clock_reset_rejected': cases['clock_reset']['status'] == 'RINEX_REJECTED',
        'code_rejection_stops_before_phase_test': cases['code_clock_step']['status'] == 'REFERENCE_CODE_REJECTED'
            and 'phase_p' not in cases['code_clock_step']['calibration'],
        'stale_navigation_rejected': cases['stale_navigation']['status'] == 'REFERENCE_MODEL_UNAVAILABLE',
        'target_poisoning_preserves_admitted_inputs_and_clock': all(nominal[key] == poisoned[key] for key in
            ('admitted_navigation_sha256', 'admitted_observations_sha256')) and bool(np.array_equal(nominal['clock_coefficients'], poisoned['clock_coefficients'])),
        'all_nine_cases_retained_without_rf_claim': len(cases) == 9 and all(not r['real_rf_qualified'] for r in cases.values())}
    root = Path(__file__).resolve().parents[2]
    files = ['research/kinematic/'+name for name in ('phase_bridge_study.py', 'phase_reference_bridge.py',
        'rinex_phase_observations.py', 'phase_rates.py', 'reference_bridge.py', 'reference_fixture.py',
        'rinex_observations.py', 'doppler.py', 'receiver_time.py', 'inverse_uncertainty.py', 'clock_drift.py', 'synthetic.py', 'model.py')]
    files += ['positioning/'+name for name in ('solver.py', 'calibration.py', 'navigation.py', 'context.py', 'errors.py')]
    return native({'schema': 'rinex-phase-reference-bridge-synthetic-v1', 'real_rf_qualified': False,
        'scope': 'Full synthetic RINEX code/phase reference bridge. No target fit, new RF acquisition, universal slip detection or empirical error qualification.',
        'design': {'endpoint_tags_s': TAGS, 'references': REFERENCES, 'target': TARGET, 'base_day_gpst': DAY,
            'base_second': BASE_SECOND, 'raw_pair_order': ['C1C_m', 'C2W_m', 'L1C_cycles', 'L2W_cycles'],
            'raw_pair_covariance': RAW_PAIR_COVARIANCE, 'raw_temporal_design': 'independent endpoint/reference blocks',
            'code_and_phase_p_threshold': .01, 'propagation': 'vacuum', 'small_common_phase_drift_m_s': .001},
        'fixture_sha256': {'observations': hashlib.sha256(observations.encode()).hexdigest(), 'navigation': hashlib.sha256(navigation.encode()).hexdigest()},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__},
        'clock_error_m_and_m_s': error, 'criteria': criteria, 'criteria_pass': all(criteria.values()), 'cases': cases})


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
    print(json.dumps(report['criteria'], indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
