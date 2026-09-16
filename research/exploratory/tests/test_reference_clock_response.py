from dataclasses import dataclass

import numpy as np
import pytest

from positioning.calibration import C
from research.exploratory import reference_clock_response as study


@dataclass(frozen=True)
class Record:
    af0_s: float
    orbit_value: float = 42.


def test_clock_shift_preserves_orbit_and_inputs_and_is_shared_across_records():
    records = [Record(0.), Record(1e-5)]
    nav = {'G01': records, 'G02': [Record(2e-5)]}
    shifted = study.shifted_navigation(nav, ['G01'], 1., 'G14')
    assert nav['G01'] == records
    for old, new in zip(records, shifted['G01']):
        assert new.af0_s - old.af0_s == pytest.approx(1 / C, rel=1e-10)
        assert new.orbit_value == old.orbit_value
    assert shifted['G02'] == nav['G02']


@pytest.mark.parametrize('nav,refs,step', [
    ({'G14': []}, [], 1.), ({'G01': []}, ['G14'], 1.),
    ({'G01': []}, ['G02'], 1.), ({'G01': []}, ['G01'], float('nan')),
])
def test_invalid_or_target_perturbations_are_rejected(nav, refs, step):
    with pytest.raises(ValueError):
        study.shifted_navigation(nav, refs, step, 'G14')


def test_centered_response_separates_odd_gain_from_even_nonlinearity():
    def row(q):
        return {'status': 'ESTIMATED', 'xyz_m': q[:3], 'B_m': q[3], 'u0_relative_s': 0.}
    baseline = row([10., 20., 30., 40.])
    minus, plus = row([8.5, 16., 30., 39.]), row([14.5, 24., 30., 43.])
    response = study.paired_response(baseline, minus, plus, 1.)
    assert response['position_gain_m_per_m'] == pytest.approx(5.)
    assert response['even_position_response_m'] == pytest.approx(1.5)
    assert response['B_response_m_per_m'] == pytest.approx(2.)
    assert response['even_B_response_m'] == pytest.approx(1.)
    minus['status'] = 'CALIBRATION_REJECTED'
    assert study.paired_response(baseline, minus, plus, 1.) == {'status': 'NOT_COMPARABLE'}
    minus['status'] = 'ESTIMATED'
    minus['u0_relative_s'] = 1.
    assert study.paired_response(baseline, minus, plus, 1.) == {'status': 'FRAME_TAG_CHANGED'}


def test_run_keeps_both_signs_and_all_failures(monkeypatch):
    from types import SimpleNamespace
    data = {'fit_stations': ['A'], 'stations': {'A': {'antenna_ecef_m': [0., 0., 0.],
            'reference_observations': [{'time_s': 0, 'if_code_m': {'G01': 1.}}]}}}
    context = SimpleNamespace(target='G14', date_gpst='2026-09-03')
    monkeypatch.setattr(study, 'load_inputs', lambda _: (data, context, {'G01': [Record(0.)]}, {}))
    def calibrate(obs, xyz, nav, ctx):
        if nav['G01'][0].af0_s > 0:
            raise RuntimeError('invented positive-step failure')
        return {'status': 'CALIBRATION_QUALIFIED', 'failures': [],
                'epochs': [{'time_s': 0, 'clock_m': 0., 'references': ['G01']}]}
    monkeypatch.setattr(study, 'calibrate_station', calibrate)
    monkeypatch.setattr(study, 'fit_variant', lambda *a: {'status': 'ESTIMATED',
                        'xyz_m': [1., 2., 3.], 'B_m': 0., 'u0_relative_s': 0.})
    report = study.run('unused')
    assert report['case_count'] == 5
    assert report['status_counts'] == {'ESTIMATED': 3, 'ENGINEERING_FAILURE': 2}
    assert all(pair['status'] == 'NOT_COMPARABLE' for pair in report['paired_responses'])
    assert all('gain' not in key for pair in report['paired_responses'] for key in pair)
