from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from research.exploratory import station_coordinates_v2 as audit
from research.exploratory import reference_residual_structure_v2 as guarded

ROOT = Path(__file__).resolve().parents[3]
INPUTS = ROOT/'research/exploratory/inputs'
ARCHIVES = {'g14': ROOT/'experiments/positioning_g14_doy246_network', 'g12': INPUTS/'g12_doy248'}


def test_text_allowlist_excludes_poisoned_satellite_and_nonfit_values():
    original = (INPUTS/'station_coordinates/g14/station_sinex.txt').read_text()
    poisoned = original.replace('-SOLUTION/ESTIMATE',
        '  9999 SATA_X G014 L1    1 26:246:43185 m    1 not-a-number NaN\n'
        '  9998 STAX   GOLD  A    2 26:246:43185 m    1 not-a-number NaN\n-SOLUTION/ESTIMATE')
    poisoned = poisoned.replace('%ENDSNX', '+SATELLITE/ID\n G014 corrupted target\n-SATELLITE/ID\n%ENDSNX')
    names = json.loads((INPUTS/'station_coordinates/g14/headers.json').read_bytes())['fit_stations']
    assert audit.extract_sinex(poisoned.splitlines(), names) == audit.extract_sinex(original.splitlines(), names)
    def header_only():
        yield 'ALGO'.ljust(60)+'MARKER NAME'
        yield ''.ljust(60)+'END OF HEADER'
        raise AssertionError('observation body accessed')
    assert audit.extract_header(header_only()) == {'MARKER NAME': ['ALGO'.ljust(60)]}


def sample():
    directory = INPUTS/'station_coordinates/g14'
    blocks = audit.parse_blocks((directory/'station_sinex.txt').read_text())
    header = json.loads((directory/'headers.json').read_bytes())['headers']['ALGO00CAN']
    # Invent a known equatorial marker and nonzero H/E/N to detect swapped axes.
    header['APPROX POSITION XYZ'] = ['6378137 0 0']
    header['ANTENNA: DELTA H/E/N'] = ['0.1 0.2 0.3']
    for i, s in enumerate(blocks['SITE/ECCENTRICITY']):
        if s[1:5] == 'ALGO':
            blocks['SITE/ECCENTRICITY'][i] = s[:46]+'  0.1000   0.3000   0.2000'
    for i, s in enumerate(blocks['SOLUTION/ESTIMATE']):
        if s[14:18] == 'ALGO':
            value = {'STAX': 6378138, 'STAY': 2, 'STAZ': 3}[s[7:13].strip()]
            blocks['SOLUTION/ESTIMATE'][i] = s[:47]+f'{value:21.14E} 1.000000E-03'
    return header, blocks


def compare_station(header, blocks, times=None):
    return audit.station_audit('ALGO00CAN', header, blocks, '2026-09-03',
                               times or [14100., 14400.], [6378137.1, .2, .3])


def test_marker_arp_axis_units_daily_selection_and_phase_separation():
    h, b = sample()
    r = compare_station(h, b)
    h['MARKER NAME'] = ['ALGO CACS station description']
    extended = compare_station(h, b)
    assert extended['arp_delta_enu_m'] == r['arp_delta_enu_m']
    assert extended['rinex_marker_name'] == 'ALGO CACS station description'
    assert r['solution_id'] == '2'
    assert r['coordinate_epoch'] == '26:246:43185'
    assert r['header_eccentricity_enu_m'] == [.2, .3, .1]
    assert r['sinex_eccentricity_enu_m'] == [.2, .3, .1]
    assert r['eccentricity_difference_norm_m'] == 0
    assert r['marker_delta_norm_m'] == pytest.approx(np.sqrt(14))
    assert r['arp_delta_enu_m'] == pytest.approx([2, 3, 1], abs=1e-6)
    assert r['phase_l1_pco_enu_m'] == [-.0005, .0007, .0918]
    assert not r['code_pco_qualified']
    # First-order range sign independently checked by finite difference.
    receiver = np.array(r['header_arp_ecef_m'])
    satellite = receiver+np.array([2e7, 1e7, 1e7])
    delta = np.array(r['sinex_arp_ecef_m'])-receiver
    projected = -(satellite-receiver)@delta/np.linalg.norm(satellite-receiver)
    actual = np.linalg.norm(satellite-receiver-delta)-np.linalg.norm(satellite-receiver)
    assert actual == pytest.approx(projected, abs=1e-6)


@pytest.mark.parametrize('defect', ['domes', 'antenna', 'ambiguous', 'epoch', 'unit', 'nonfinite', 'arp'])
def test_identity_epoch_and_vector_failures_are_rejected(defect):
    h, b = sample()
    if defect == 'domes': h['MARKER NUMBER'] = ['99999M999']
    if defect == 'antenna': h['ANT # / TYPE'] = [''.ljust(20)+'WRONG'.ljust(20)]
    if defect == 'ambiguous': b['SOLUTION/EPOCHS'] *= 2
    if defect in ('epoch', 'unit', 'nonfinite'):
        for i, s in enumerate(b['SOLUTION/ESTIMATE']):
            if s[14:18] == 'ALGO':
                if defect == 'epoch': s = s.replace('26:246:43185', '26:247:43185')
                if defect == 'unit': s = s[:40]+'mm  '+s[44:]
                if defect == 'nonfinite': s = s[:47]+'NaN 0.001'
                b['SOLUTION/ESTIMATE'][i] = s
    if defect == 'arp': h['ANTENNA: DELTA H/E/N'] = ['0.1 0.3 0.2']
    with pytest.raises(ValueError): compare_station(h, b)


def fake_prior(monkeypatch, tmp_path):
    context = SimpleNamespace(target='G14', date_gpst='2026-09-03', times=[0., 30.])
    observations = [{'time_s': t, 'if_code_m': dict.fromkeys(['G01','G02','G03','G04'], 2e7)} for t in context.times]
    admitted = {'fit_stations': ['A'], 'stations': {'A': {'reference_observations': observations, 'antenna_ecef_m': [6378137.,0,0]}}}
    prior = {'schema': 'reference-attitude-v1', 'target': 'G14', 'date_gpst': context.date_gpst,
             'fit_stations': ['A'], 'references': ['G01','G02','G03','G04'], 'input_sha256': {}, 'sources_sha256': {},
             'target_orbit_accessed': False, 'target_attitude_parsed': False, 'new_confirmation': False,
             'qualified_error_budget': False, 'applied_to_production_estimator': False,
             'cases': [{'mode': 'full_pco_30s_attitude', 'status': 'ESTIMATED', 'calibration': {'A': {
                 'status': 'CALIBRATION_QUALIFIED', 'epochs': [{'time_s': t} for t in context.times]}}}]}
    monkeypatch.setattr(guarded, 'load_inputs', lambda _: (admitted, context, None, {}))
    monkeypatch.setattr(guarded, 'guarded_products', lambda *a: (None, {}, {}))
    monkeypatch.setattr(guarded, 'load_attitude', lambda *a: (None, {}))
    monkeypatch.setattr(guarded, 'translate_observations', lambda obs, *a: obs)
    return prior, admitted, tmp_path/'prior.json'


@pytest.mark.parametrize('flag', ['target_orbit_accessed', 'target_attitude_parsed', 'new_confirmation',
                                 'qualified_error_budget', 'applied_to_production_estimator', 'date_gpst'])
@pytest.mark.parametrize('value', [True, None, 0])
def test_v2_rejects_wrong_missing_or_nonboolean_boundary(monkeypatch, tmp_path, flag, value):
    prior, _, path = fake_prior(monkeypatch, tmp_path)
    if value is None: del prior[flag]
    else: prior[flag] = value
    path.write_text(json.dumps(prior))
    with pytest.raises(ValueError, match='binding'): guarded.prepare(None, None, None, None, None, path)


@pytest.mark.parametrize('count', [1, 3])
def test_v2_rejects_both_observation_length_mismatches(monkeypatch, tmp_path, count):
    prior, admitted, path = fake_prior(monkeypatch, tmp_path)
    obs = admitted['stations']['A']['reference_observations']
    admitted['stations']['A']['reference_observations'] = [deepcopy(obs[0]) for _ in range(count)]
    path.write_text(json.dumps(prior))
    with pytest.raises(ValueError, match='lengths'): guarded.prepare(None, None, None, None, None, path)


def compare(a, b, key=None):
    if isinstance(b, dict):
        assert a.keys() == b.keys()
        for k in b: compare(a[k], b[k], k)
    elif isinstance(b, list):
        assert len(a) == len(b)
        for x, y in zip(a, b, strict=True): compare(x, y, key)
    elif isinstance(b, float):
        assert a == pytest.approx(b, abs=1e-7 if key in ('pearson', 'lag_30s_pearson') else 1e-8, rel=1e-10)
    else:
        assert a == b


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_v2_report_replay_preserves_all_v1_results(tag):
    result = guarded.run(ARCHIVES[tag], INPUTS/f'timed_reference_products/{tag}', INPUTS/f'reference_biases/{tag}',
                         INPUTS/f'reference_antennas/{tag}', INPUTS/f'reference_attitudes/{tag}',
                         ROOT/f'research/exploratory/results/{tag}_reference_attitude_v1.json')
    saved = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_residual_structure_v2.json').read_bytes())
    compare(result, saved)
    old = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_residual_structure_v1.json').read_bytes())
    for k in ('reference_rows', 'omitted_paths', 'cases', 'descriptive', 'input_sha256'):
        compare(result[k], old[k])


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_station_report_replays_and_accounts_for_every_fit_station(tag):
    result = audit.run(INPUTS/f'station_coordinates/{tag}', ARCHIVES[tag]/'estimation/admitted.json',
                       ROOT/f'research/exploratory/results/{tag}_reference_residual_structure_v2.json')
    saved = json.loads((ROOT/f'research/exploratory/results/{tag}_station_coordinates_v2.json').read_bytes())
    compare(result, saved)
    assert result['station_count'] == len(result['stations']) == len(result['fit_stations']) == 7
    assert sum(result['status_counts'].values()) == 7
    assert all(s['station'] != 'GOLD00USA' for s in result['stations'])
    for s in result['stations']:
        if s['status'] == 'COMPARED':
            assert s['reference_ray_count'] == len(s['projections'])
            for t in {p['time_s'] for p in s['projections']}:
                assert sum(p['centered_range_change_m'] for p in s['projections'] if p['time_s'] == t) == pytest.approx(0, abs=1e-12)
    for path, digest in result['sources_sha256'].items(): assert audit.sha((ROOT/path).read_bytes()) == digest
