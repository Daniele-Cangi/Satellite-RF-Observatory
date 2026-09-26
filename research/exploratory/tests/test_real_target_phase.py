"""Target-only read boundary and explicit RINEX failures."""
import hashlib
import json
import pytest

from research.exploratory.real_target_phase import parse_target_fields
from research.exploratory import real_target_phase as phase
from research.exploratory.real_target_phase_v2 import gps_only_phase_header
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


def test_gps_header_adapter_preserves_gps_and_body_but_rejects_bad_gps():
    original = fixture()
    end = next(line for line in original.splitlines(keepends=True) if 'END OF HEADER' in line)
    malformed_other = f"{'R L1C  0.00000  02 R01':60}SYS / PHASE SHIFT\n"
    dirty = original.replace(end, malformed_other+end)
    with pytest.raises(ValueError, match='PHASE_SHIFT'):
        parse_target_fields(dirty, PLAN)
    cleaned = gps_only_phase_header(dirty)
    assert cleaned == original
    assert parse_target_fields(cleaned, PLAN)['rows'] == parse_target_fields(original, PLAN)['rows']
    bad_gps = original.replace(end,
                               f"{'G L1C  0.00000  02 G01':60}SYS / PHASE SHIFT\n"
                               +end)
    with pytest.raises(ValueError, match='PHASE_SHIFT'):
        parse_target_fields(gps_only_phase_header(bad_gps), PLAN)


def test_v2_retains_all_fits_and_model_rejections():
    report = json.loads((phase.BASE/'results/real_target_interval_v2.json').read_bytes())
    target = json.loads((phase.BASE/'inputs/real_phase/g12_target_phase_v2.json').read_bytes())
    assert not report['target_orbit_accessed'] and not report['physical_covariance_qualified']
    assert report['historical_code_floor_m'] == 20.
    assert report['status_counts'] == {'EVALUATED': 20}
    assert target['stations']['BOGT00COL']['status'] == 'PARSED'
    assert target['stations']['YELL00CAN']['status'] == 'UNSUPPORTED_REFERENCE_PHASE'
    assert [case['fits']['code_phase']['status'] for case in report['cases']].count(
        'CONDITIONAL_INTERVAL_MODEL_ACCEPTED') == 5
    assert [case['fits']['code_phase']['status'] for case in report['cases']].count(
        'MODEL_REJECTED') == 15
    for case in report['cases']:
        assert case['fits']['code_only']['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED'
        for fit in case['fits'].values():
            assert ('withheld' in fit) == (fit['status'] == 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED')


def test_oracle_is_bound_to_frozen_rf_report_and_keeps_rejections():
    report_bytes = (phase.BASE/'results/real_target_interval_v2.json').read_bytes()
    comparison = json.loads((phase.BASE/'results/real_target_oracle_v2.json').read_bytes())
    assert comparison['frozen_rf_report_sha256'] == hashlib.sha256(report_bytes).hexdigest()
    assert comparison['target_state_used_only_for_diagnostic']
    assert len(comparison['cases']) == 20
    assert comparison['counts']['phase_status'] == {
        'MODEL_REJECTED': 15, 'CONDITIONAL_INTERVAL_MODEL_ACCEPTED': 5}
    assert comparison['summary']['paired_accepted_phase_better_count'] == 3
    assert comparison['summary']['paired_accepted_phase_worse_count'] == 2
    assert comparison['summary']['phase_accepted']['max_m'] > 120.
