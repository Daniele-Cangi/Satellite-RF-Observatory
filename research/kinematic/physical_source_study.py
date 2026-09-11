"""Read-only historical header audit plus reference-only synthetic phase study."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np

from .doppler import F1_HZ as F1, F2_HZ as F2
from .phase_rates import interval_matrix, predict_interval_rate, reference_phase_rates
from .physical_sources import inspect_header, neutral_delay_basis
from .receiver_time import C
from .reference_fixture import REFERENCES, TARGET, independent_code
from .synthetic import native

TAGS = np.arange(-330., 1., 30.)


def fixture_rows():
    rows = []
    for tag in TAGS:
        for index, satellite in enumerate(REFERENCES):
            path = independent_code(tag, index)
            iono = 40.+.07*tag
            phases = [(path-iono)*F1/C+1000, (path-iono*(F1/F2)**2)*F2/C+2000]
            rows.append({'satellite': satellite, 'tag_s': float(tag), 'epoch_flag': 0,
                         'fields': {name: f'{value:14.3f}0 ' for name, value in zip(('L1C', 'L2W'), phases)}})
    rows.append({'satellite': TARGET, 'tag_s': 'POISON', 'fields': 'POISON'})
    rows.append({'satellite': REFERENCES[0], 'tag_s': 30., 'fields': 'POISON'})
    return rows


def evaluate(rows, covariance):
    return reference_phase_rates(rows, target=TARGET, references=REFERENCES, tags_s=TAGS, phase_covariance=covariance)


def run():
    root = Path(__file__).resolve().parents[2]
    archive = root/'experiments/positioning_g14_doy246_network/structure.json'
    # Read only stored structural metadata, not observations, fits or oracles.
    structures = json.loads(archive.read_text())['structures']
    inventory = {station: inspect_header(structure.get('header')) for station, structure in structures.items()}
    rows = fixture_rows()
    size = 2*len(TAGS)*len(REFERENCES)
    covariance = .01**2*np.eye(size)  # Invented phase uncertainty, not receiver specification.
    nominal = evaluate(rows, covariance)
    path = np.array([[independent_code(t, i) for i in range(4)] for t in TAGS])
    expected = predict_interval_rate(path, TAGS, 4)
    h = .1
    endpoint_rate = np.array([[(independent_code(t+h, i)-independent_code(t-h, i))/(2*h)
                               for i in range(4)] for t in TAGS[1:]])
    cases = {}
    for case in ('flagged_slip', 'missing_endpoint', 'clock_reset', 'unflagged_slip'):
        changed = deepcopy(rows)
        if case == 'missing_endpoint':
            del changed[5*4]
        elif case == 'clock_reset':
            changed[5*4]['epoch_flag'] = 1
        elif case == 'flagged_slip':
            field = changed[5*4]['fields']['L1C']
            changed[5*4]['fields']['L1C'] = field[:14]+'1 '
        else:
            for row in changed:
                if row['satellite'] == REFERENCES[0] and isinstance(row['tag_s'], float) and -180 <= row['tag_s'] <= 0:
                    field = row['fields']['L1C']
                    row['fields']['L1C'] = f'{float(field[:14])+1:14.3f}0 '
        outcome = evaluate(changed, covariance)
        cases[case] = {'status': outcome['status'], 'real_rf_qualified': outcome['real_rf_qualified']}
        if outcome['status'] == 'REFERENCE_PHASE_RATE_AVAILABLE':
            cases[case]['max_rate_change_m_s'] = float(np.max(abs(outcome['mean_phase_rate_m_s']-nominal['mean_phase_rate_m_s'])))
        else:
            cases[case]['reasons'] = outcome['reasons']
    # Invented geometry for neutral sensitivity, not selected using target orbit.
    elevations = np.array([15., 30., 50., 75.])[None, :]+(TAGS-TAGS[0])[:, None]*.01
    neutral = neutral_delay_basis(TAGS, elevations)
    rate_modes = interval_matrix(TAGS, 4)@neutral
    zenith_cov = np.diag([.05**2, 1e-4**2])
    neutral_rate_cov = rate_modes@zenith_cov@rate_modes.T
    # A common path delay affects both phases in metres; preserve all correlations.
    phase_neutral = np.repeat(neutral, 2, axis=0)*np.tile([F1/C, F2/C], len(neutral))[:, None]
    expanded = evaluate(rows, covariance+phase_neutral@zenith_cov@phase_neutral.T)
    noise_diag = np.diag(nominal['covariance_rate'])
    adjacent = nominal['covariance_rate'][0, 4]/np.sqrt(noise_diag[0]*noise_diag[4])
    missing = {station: r.get('missing_doppler_fields', []) for station, r in inventory.items()
               if r.get('status') != 'HEADER_UNAVAILABLE' and not r['required_doppler_declared']}
    criteria = {
        'all_eleven_archived_station_entries_retained': len(inventory) == 11,
        'historical_gold_missing_direct_doppler': 'GOLD00USA' in missing,
        'quantized_phase_mean_matches_reference_within_0_05mm_s': float(np.max(abs(nominal['mean_phase_rate_m_s']-expected))) < 5e-5,
        'adjacent_phase_rates_are_anticorrelated': abs(adjacent+.5) < 1e-12,
        'reported_slip_gap_reset_stop_arc': all(cases[k]['status'] == 'REFERENCE_PHASE_WINDOW_REJECTED' for k in ('flagged_slip', 'missing_endpoint', 'clock_reset')),
        'unreported_slip_is_not_falsely_claimed_detected': cases['unflagged_slip']['status'] == 'REFERENCE_PHASE_RATE_AVAILABLE'
            and cases['unflagged_slip']['max_rate_change_m_s'] > .01,
        'neutral_shared_covariance_matches_raw_phase_transport': bool(np.allclose(
            expanded['covariance_rate']-nominal['covariance_rate'], neutral_rate_cov, atol=1e-14)),
        'no_real_rf_qualification': all(not r['real_rf_qualified'] for r in inventory.values()) and not nominal['real_rf_qualified']}
    files = ['research/kinematic/'+name for name in ('physical_sources.py', 'phase_rates.py', 'physical_source_study.py',
        'reference_fixture.py', 'doppler.py', 'inverse_uncertainty.py', 'receiver_time.py', 'rinex_observations.py',
        'clock_drift.py', 'synthetic.py', 'model.py')]
    files += ['positioning/'+name for name in ('solver.py', 'calibration.py', 'context.py', 'navigation.py', 'errors.py')]
    return native({'schema': 'physical-source-audit-and-phase-study-v1', 'real_rf_qualified': False,
        'scope': 'Historical headers only; no real RF payload analysis. Alternative phase-increment adapter is not integrated into the Doppler importer or inverse fitter. Synthetic physical-error sensitivities, not empirical qualification.',
        'archive_source': {'path': archive.relative_to(root).as_posix(), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()},
        'sources_sha256': {name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
        'header_inventory': inventory, 'design': {'endpoint_tags_s': TAGS, 'references': REFERENCES, 'excluded_target': TARGET,
            'phase_sigma_cycles': .01, 'neutral_elevation_deg': elevations, 'zenith_error_covariance': zenith_cov},
        'diagnostics': {'direct_doppler_declared_count': sum(r.get('required_doppler_declared', False) for r in inventory.values()),
            'phase_candidate_count': sum(r.get('phase_difference_candidate', False) for r in inventory.values()),
            'max_phase_mean_error_m_s': float(np.max(abs(nominal['mean_phase_rate_m_s']-expected))),
            'max_mean_vs_instantaneous_endpoint_m_s': float(np.max(abs(expected-endpoint_rate))),
            'adjacent_rate_correlation': float(adjacent),
            'max_neutral_rate_sigma_m_s': float(np.sqrt(np.diag(neutral_rate_cov)).max())},
        'nominal': {k: v for k, v in nominal.items() if k != 'transform_cycles_to_mean_rate'},
        'stress_cases': cases, 'criteria': criteria, 'criteria_pass': all(criteria.values())})


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
    print(json.dumps({'criteria': report['criteria'], 'diagnostics': report['diagnostics']}, indent=2))
    raise SystemExit(0 if report['criteria_pass'] else 1)
