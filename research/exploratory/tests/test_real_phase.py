"""Active adapter: target exclusion, units, discontinuities and paired inputs."""
import hashlib
import json

import numpy as np
import pytest

from research.exploratory import real_phase as phase
from research.exploratory.real_phase_inverse import window_errors
from research.kinematic.tests.test_phase_transform_header_audit import _header, _scale, _wavelength


PLAN = {'date_gpst': '2026-09-08', 'step_s': 30, 'start_gpst_s': 0,
        'samples': 3, 'target_excluded': 'G12', 'references': ['G01']}


def observation(t, *, target='poison nan invalid', lli=' ', factor=1):
    values = [2.4e7, 2.4e7+2, 1.2e8, 9e7]
    record = 'G01'+''.join(f'{v*factor:14.3f}'+(lli if i >= 2 else ' ')+' ' for i, v in enumerate(values))
    return f'> 2026 09 08 00 {t//60:02d} {t%60:10.7f}  0  2\n'+record+'\nG12'+target+'\n'


def text(extra=(), **kwargs):
    headers = _header(extra)
    # Test helper's historical fixture uses a nonstandard version-column width.
    headers[0] = f"{'3.03':>9}{'':11}O{'BSERVATION DATA':<19}M{' (MIXED)':<19}RINEX VERSION / TYPE"
    return '\n'.join(headers)+'\n'+''.join(observation(t, **kwargs) for t in (0, 30, 60))


def test_reference_only_and_scaled_cycles():
    raw = phase.parse_reference_fields(text(extra=[_wavelength(1, 1)]), PLAN)
    poisoned = phase.parse_reference_fields(text(target='different forbidden bytes'), PLAN)
    assert raw['rows'] == poisoned['rows']
    scaled = phase.parse_reference_fields(text(extra=[_scale(10)], factor=10), PLAN)
    assert raw['rows'] == scaled['rows']
    assert len(raw['rows']) == 3 and all(r['reference'] == 'G01' for r in raw['rows'])
    with pytest.raises(ValueError, match='nonunit'):
        phase.parse_reference_fields(text(extra=[_wavelength(2, 1)]), PLAN)
    with pytest.raises(ValueError, match='target in reference'):
        phase.parse_reference_fields(text(), {**PLAN, 'references': ['G12']})


def test_lli_and_event_are_not_silently_repaired():
    parsed = phase.parse_reference_fields(text(lli='1'), PLAN)
    assert all(r['status'] == 'REJECTED' for r in parsed['rows'])
    assert all('phase_m' not in r for r in parsed['rows'])
    with pytest.raises(ValueError, match='event/header change'):
        phase.parse_reference_fields(text().replace('  0  2', '  1  2'), PLAN)


def test_window_excludes_selected_reference_from_phase_common():
    plan = {'stations': ['TEST'], 'references': [f'G{i:02}' for i in range(1, 6)]}
    rows, baseline = [], {}
    for t in range(0, 301, 30):
        for sv in plan['references']:
            # Station-common drift 2 m/s, selected-link additional 1 m/s.
            rate = 3 if sv == 'G01' else 2
            rows.append({'time_s': t, 'reference': sv, 'status': 'AVAILABLE',
                         'phase_m': 1e6+rate*t, 'code_m': 1e6})
            baseline[('TEST', t, sv)] = {'residual_m': 0.}
    cohort = {'plan': plan, 'stations': {'TEST': {'status': 'PARSED', 'rows': rows}}}
    result = window_errors(cohort, baseline, 0)
    np.testing.assert_allclose(result['raw_phase_error_m_s'], 3.)
    np.testing.assert_allclose(result['other_reference_corrected_phase_error_m_s'], 1.)
    assert result['references'] == {'TEST': 'G01'}
    # Missing one endpoint is not bridged; all candidates/other references fail.
    for row in rows:
        if row['time_s'] == 150:
            row['status'] = 'REJECTED'
    assert window_errors(cohort, baseline, 0)['status'] == 'INCOMPLETE_STATION_WINDOW'


def test_common_mode_requires_four_and_levels_do_not_cross_gap(tmp_path, monkeypatch):
    plan = {**PLAN, 'stations': ['TEST'], 'samples': 25, 'training_before_gpst_s': 360}
    rows = []
    baseline = []
    for t in range(0, 721, 30):
        row = {'station': 'TEST', 'reference': 'G01', 'time_s': t, 'residual_m': 1.}
        baseline.append(row)
        rows.append({'reference': 'G01', 'time_s': t, 'status': 'AVAILABLE' if t != 390 else 'REJECTED',
                     'code_m': 1e6, 'phase_m': 1e6+2+t, 'geometry_free_phase_m': t})
    (tmp_path/'results').mkdir()
    (tmp_path/'results'/'day_reference_v1.json').write_text(json.dumps({'rows': baseline}))
    monkeypatch.setattr(phase, 'BASE', tmp_path)
    data = {'cohorts': {'day': {'plan': plan, 'stations': {'TEST': {'status': 'PARSED', 'rows': rows}}}}}
    report = phase.analyze(data)['cohorts']['day']
    assert [r['time_s'] for r in report['series']] == [360]
    assert all(r['time_s'] not in (390, 420) for r in report['intervals'])
    assert report['summary']['phase_residual_m_differential']['count'] == 0
    assert report['failures']['UNBRIDGED_GAP'] == 1


def test_retained_results_keep_all_cases_and_worsening_outcomes():
    inputs_path = phase.BASE/'inputs/real_phase/observations.json'
    data = json.loads(inputs_path.read_bytes())
    for cohort in data['cohorts'].values():
        forbidden = cohort['plan']['target_excluded']
        assert all(r['reference'] != forbidden for station in cohort['stations'].values() for r in station['rows'])
    result = json.loads((phase.BASE/'results/real_phase_inverse_v1.json').read_bytes())
    assert result['input_sha256'] == hashlib.sha256(inputs_path.read_bytes()).hexdigest()
    assert not result['real_rf_qualified']
    cases = [r for c in result['cohorts'].values() for r in c['cases']]
    assert len(cases) == 12
    assert all(r['fits']['code_phase_raw']['status'] == 'MODEL_REJECTED' for r in cases)
    assert any(r['fits']['code_phase_other_references']['errors']['position_t0_m'] >
               r['fits']['code_only']['errors']['position_t0_m'] for r in cases)
    # A real held-out prediction must never be inferred from synthetic forecasts.
    assert all(c['real_excluded_receiver_prediction'].startswith('NOT_EVALUATED')
               for c in result['cohorts'].values())
