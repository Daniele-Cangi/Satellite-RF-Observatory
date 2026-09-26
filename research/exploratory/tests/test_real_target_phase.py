"""Target-only read boundary and explicit RINEX failures."""
import json
import pytest

from research.exploratory.real_target_phase import parse_target_fields
from research.exploratory import real_target_phase as phase
from research.kinematic.tests.test_phase_transform_header_audit import _header, _wavelength


PLAN = {'date_gpst': '2026-09-08', 'step_s': 30, 'start_gpst_s': 0,
        'samples': 2, 'target_excluded': 'G12'}


def payload(t, reference='poison', lli=' '):
    values = [2.4e7, 2.4e7+2, 1.2e8, 9e7]
    target = 'G12'+''.join(f'{v:14.3f}'+(lli if i >= 2 else ' ')+' '
                           for i, v in enumerate(values))
    return f'> 2026 09 08 00 00 {t:10.7f}  0  2\nG01{reference}\n{target}\n'


def fixture(reference='poison', lli=' ', extra=()):
    lines = _header(extra)
    lines[0] = f"{'3.03':>9}{'':11}O{'BSERVATION DATA':<19}M{' (MIXED)':<19}RINEX VERSION / TYPE"
    return '\n'.join(lines)+'\n'+payload(0, reference, lli)+payload(30, reference, lli)


def test_only_g12_decoded_and_reference_poison_has_no_effect():
    a = parse_target_fields(fixture(), PLAN)
    b = parse_target_fields(fixture(reference='non numeric but different'), PLAN)
    assert a['rows'] == b['rows']
    assert [r['time_s'] for r in a['rows']] == [0, 30]
    assert all(r['target'] == 'G12' and r['status'] == 'AVAILABLE' for r in a['rows'])


def test_bad_lli_and_wavelength_fail_closed():
    rows = parse_target_fields(fixture(lli='1'), PLAN)['rows']
    assert all(r['status'] == 'REJECTED' and 'phase_m' not in r for r in rows)
    with pytest.raises(ValueError, match='nonunit'):
        parse_target_fields(fixture(extra=[_wavelength(2, 1)]), PLAN)
    with pytest.raises(ValueError, match='event/header change'):
        parse_target_fields(fixture().replace('  0  2', '  1  2'), PLAN)


def test_original_five_station_attempt_retains_all_failed_windows():
    report = json.loads((phase.BASE/'results/real_target_interval_v1.json').read_bytes())
    assert not report['target_orbit_accessed'] and not report['physical_covariance_qualified']
    assert len(report['cases']) == 20
    assert report['status_counts'] == {'TARGET_BELOW_ELEVATION_MASK': 3,
                                       'INCOMPLETE_TARGET_WINDOW': 17}
    assert all(case['station'] == 'STJO00CAN' for case in report['cases'])
    assert all(case['elevation_deg'] < 10. for case in report['cases'][:3])
