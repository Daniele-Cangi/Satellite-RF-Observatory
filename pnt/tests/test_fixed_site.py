"""Behavioral tests: retained gaps, independent remote fits and blind clock mode."""

from dataclasses import replace
from datetime import date, timedelta
import gzip
import json
import subprocess
import sys

import numpy as np
import pytest

from positioning.calibration import OMEGA, reference_model
from research.exploratory.tests.test_pnt_texbat_clock_context import nav_source
from research.exploratory.pnt_observation_pairing import reference_codes
from pnt.fixed_site import analyze, evaluate_epoch
from pnt.model import broadcast_navigation, day_context, nearest_record


DAY = date(2012, 9, 14)
TIME = 28800
POSITIONS = {'local': np.array([6378137., 0., 0.]),
             'A': np.array([6378137., 1000., 500.]),
             'B': np.array([6378137., -1500., 250.])}


def constellation():
    context = day_context(DAY)
    base = broadcast_navigation(nav_source())[0]['G01'][0]
    return {f'G{prn:02d}': [replace(base, satellite=f'G{prn:02d}',
                                  toc_gps=context.day + timedelta(seconds=TIME),
                                  toe_sow=context.sow_midnight + TIME, af0_s=0.,
                                  af1_s_s=0., eccentricity=0., argument_perigee_rad=0.,
                                  omega0_rad=OMEGA * (context.sow_midnight + TIME),
                                  m0_rad=(prn - 4) * .09)]
            for prn in range(1, 9)}


def observations(navigation, *, time=TIME, local_shift=0.):
    context = day_context(DAY)
    result = {}
    for name, position in POSITIONS.items():
        clock = {'local': 100. + local_shift, 'A': 50., 'B': -20.}[name]
        result[name] = {}
        for sv, records in navigation.items():
            code = 25e6
            for _ in range(8):
                code = reference_model(records[0], code, time, position, clock, context)[0] + clock
            result[name][sv] = (code, code)
    return result


def test_physical_model_preserves_common_clock_while_differences_cancel_it():
    nav = constellation()
    first = evaluate_epoch(TIME, observations(nav), POSITIONS, nav, day_context(DAY))
    shifted = evaluate_epoch(TIME, observations(nav, local_shift=200.), POSITIONS, nav, day_context(DAY))
    for result, expected_clock in ((first, 100.), (shifted, 300.)):
        assert result['matched']['status'] == 'EVALUATED'
        assert result['matched']['receiver_fits']['local']['clock_m'] == pytest.approx(expected_clock, abs=1e-5)
        assert max(map(abs, result['matched']['mean_double_difference_residuals_m'].values())) < 1e-5
    assert shifted['matched']['receiver_fits']['A'] == first['matched']['receiver_fits']['A']
    assert shifted['matched']['receiver_fits']['B'] == first['matched']['receiver_fits']['B']
    assert shifted['matched']['local_minus_network_clock_m'] - first['matched']['local_minus_network_clock_m'] == pytest.approx(200., abs=1e-5)


def test_local_satellite_anomaly_is_not_absorbed_into_remote_fit():
    nav = constellation()
    values = observations(nav)
    original = evaluate_epoch(TIME, values, POSITIONS, nav, day_context(DAY))
    values['local']['G02'] = tuple(code + 20. for code in values['local']['G02'])
    changed = evaluate_epoch(TIME, values, POSITIONS, nav, day_context(DAY))
    assert changed['matched']['mean_double_difference_residuals_m']['G02'] == pytest.approx(20., abs=.001)
    assert changed['matched']['receiver_fits']['A'] == original['matched']['receiver_fits']['A']
    assert changed['matched']['receiver_fits']['B'] == original['matched']['receiver_fits']['B']


def test_opposing_remote_errors_remain_visible_even_when_the_mean_cancels():
    nav = constellation()
    values = observations(nav)
    for name, offset in (('A', 50.), ('B', -50.)):
        values[name]['G02'] = tuple(code + offset for code in values[name]['G02'])
    result = evaluate_epoch(TIME, values, POSITIONS, nav, day_context(DAY))['matched']
    assert abs(result['mean_double_difference_residuals_m']['G02']) < .001
    assert result['reference_disagreement']['A/B']['max_absolute_satellite_difference_m'] == pytest.approx(100., abs=.001)


def test_missing_network_retains_the_independent_local_diagnostic():
    nav = constellation()
    values = observations(nav)
    values['B'] = {}
    result = evaluate_epoch(TIME, values, POSITIONS, nav, day_context(DAY))
    assert result['standalone_receiver_fits']['local']['status'] == 'EVALUATED'
    assert result['matched']['status'] == 'INSUFFICIENT_EVIDENCE'
    assert result['matched']['satellites'] == []


def test_a_failed_fit_is_retained_instead_of_silently_removing_the_epoch(monkeypatch):
    from pnt import fixed_site
    nav = constellation()
    def failed(*args, **kwargs):
        raise ValueError('receiver clock fit did not converge')
    monkeypatch.setattr(fixed_site, 'fit_clock', failed)
    result = evaluate_epoch(TIME, observations(nav), POSITIONS, nav, day_context(DAY))
    assert result['matched']['status'] == 'MODEL_FAILED'
    assert result['matched']['receiver_fits']['local']['reason'] == 'receiver clock fit did not converge'
    assert result['standalone_receiver_fits']['local']['status'] == 'MODEL_FAILED'


def test_missing_and_stale_navigation_are_retained_as_exclusions():
    nav = constellation()
    values = observations(nav)
    del nav['G02']
    nav['G03'] = [replace(nav['G03'][0], toc_gps=nav['G03'][0].toc_gps - timedelta(hours=3))]
    result = evaluate_epoch(TIME, values, POSITIONS, nav, day_context(DAY))
    assert result['excluded_satellites']['local']['G02'] == 'MISSING_NAVIGATION'
    assert result['excluded_satellites']['local']['G03'] == 'STALE_OR_WRONG_WEEK_NAVIGATION'
    assert len(result['matched']['satellites']) == 6


def test_navigation_week_boundary_uses_absolute_toe_and_toc():
    context = day_context(date(2012, 9, 16))
    base = constellation()['G01'][0]
    record = replace(base, toc_gps=context.day, gps_week=context.gps_week - 1,
                     toe_sow=604784.)
    assert nearest_record({'G01': [record]}, 'G01', 0., context) is record
    with pytest.raises(ValueError, match='WRONG_WEEK'):
        nearest_record({'G01': [replace(record, gps_week=record.gps_week - 1)]}, 'G01', 0., context)


def header(value, label):
    return f'{value:<60}{label:<20}'


def rinex(marker, position, observations_by_time):
    lines = [header('     3.05           OBSERVATION DATA    G', 'RINEX VERSION / TYPE'),
             header(marker, 'MARKER NAME'),
             header(' '.join(map(str, position)), 'APPROX POSITION XYZ'),
             header('0.0 0.0 0.0', 'ANTENNA: DELTA H/E/N'),
             header('G    2 C1C C2W', 'SYS / # / OBS TYPES'),
             header('  2012     9    14     8     0    0.0000000     GPS', 'TIME OF FIRST OBS'),
             header('', 'END OF HEADER')]
    for time, codes in observations_by_time.items():
        lines.append(f'> 2012 09 14 {time // 3600:02d} {time // 60 % 60:02d} {time % 60:02d}.0000000  0  {len(codes)}')
        lines.extend(sv + ''.join(f'{value:14.3f}  ' for value in pair) for sv, pair in codes.items())
    return '\n'.join(lines) + '\n'


def nav_text(navigation):
    lines = [header('     2.11           N: GPS NAV DATA', 'RINEX VERSION / TYPE'), header('', 'END OF HEADER')]
    for records in navigation.values():
        r = records[0]
        lines.append(f'{int(r.satellite[1:]):2d} 12  9 14  8  0  0.0' + ''.join(f'{v:19.12E}' for v in (r.af0_s, r.af1_s_s, r.af2_s_s2)))
        rows = [(r.iode, r.crs_m, r.delta_n_rad_s, r.m0_rad),
                (r.cuc_rad, r.eccentricity, r.cus_rad, r.sqrt_a_m_sqrt),
                (r.toe_sow, r.cic_rad, r.omega0_rad, r.cis_rad),
                (r.i0_rad, r.crc_m, r.argument_perigee_rad, r.omega_dot_rad_s),
                (r.idot_rad_s, 1., r.gps_week, 0.),
                (r.sv_accuracy_m, r.sv_health, r.tgd_s, r.iode), (r.transmission_sow,)]
        lines.extend('   ' + ''.join(f'{v:19.12E}' for v in row) for row in rows)
    return '\n'.join(lines) + '\n'


def source_files(tmp_path):
    nav = constellation()
    data = observations(nav)
    paths = {name: tmp_path / f'{name}.rnx' for name in POSITIONS}
    for name, path in paths.items():
        path.write_text(rinex(name.upper(), POSITIONS[name], {TIME: data[name]}), encoding='ascii')
    nav_path = tmp_path / 'brdc.n.gz'
    nav_path.write_bytes(gzip.compress(nav_text(nav).encode('ascii')))
    return paths, nav_path


def test_real_file_pipeline_retains_every_requested_epoch_and_is_reproducible(tmp_path):
    paths, nav = source_files(tmp_path)
    references = {name: path for name, path in paths.items() if name != 'local'}
    report = analyze(paths['local'], references, nav, DAY.isoformat(), start_s=TIME, stop_s=TIME + 90)
    assert report == analyze(paths['local'], references, nav, DAY.isoformat(), start_s=TIME, stop_s=TIME + 90)
    assert report['coverage'] == {'expected_epochs': 3,
                                  'matched_status_counts': {'EVALUATED': 1, 'INSUFFICIENT_EVIDENCE': 2},
                                  'standalone_status_counts': {name: {'EVALUATED': 1, 'INSUFFICIENT_EVIDENCE': 2} for name in paths}}
    assert [r['gpst_s'] for r in report['epochs']] == [TIME, TIME + 30, TIME + 60]
    assert report['assessments']['absolute_time']['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['assessments']['model_consistency'] == 'NOT_ASSESSED'
    assert len(report['sources']['local']['sha256']) == 64
    json.dumps(report, allow_nan=False)


def test_explicit_antenna_coordinate_requires_provenance(tmp_path):
    paths, nav = source_files(tmp_path)
    with pytest.raises(ValueError, match='requires its source'):
        analyze(paths['local'], {'A': paths['A'], 'B': paths['B']}, nav, DAY.isoformat(), local_ecef=POSITIONS['local'])
    report = analyze(paths['local'], {'A': paths['A'], 'B': paths['B']}, nav, DAY.isoformat(),
                     start_s=TIME, stop_s=TIME + 30, local_ecef=POSITIONS['local'], position_source='operator survey declaration')
    assert report['sources']['local']['position_source'] == 'operator survey declaration'


def test_repeated_receivers_and_invalid_coordinates_are_rejected(tmp_path):
    paths, nav = source_files(tmp_path)
    paths['B'].write_bytes(paths['A'].read_bytes())
    with pytest.raises(ValueError, match='distinct receivers'):
        analyze(paths['local'], {'A': paths['A'], 'B': paths['B']}, nav, DAY.isoformat())
    with pytest.raises(ValueError, match='terrestrial antenna'):
        analyze(paths['local'], {'A': paths['A'], 'B': paths['B']}, nav, DAY.isoformat(),
                local_ecef=[0., 0., 0.], position_source='invalid')


@pytest.mark.parametrize('epoch', ['> 2012 09 14 24 00 00.0000000 0 0',
                                  '> 2012 09 14 08 60 00.0000000 0 0',
                                  '> 2012 09 14 08 00 nan 0 0',
                                  '> 2012 09 14 08 00 00.0000000 0 -1',
                                  '> 2012 09 14 08 00 00.0000000 0 0\n> 2012 09 14 08 00 00.0000000 0 0'])
def test_invalid_and_duplicate_empty_epochs_cannot_silently_disappear(epoch):
    text = rinex('LOCAL', POSITIONS['local'], {}) + epoch + '\n'
    with pytest.raises(ValueError):
        reference_codes(text, DAY)


def test_nonfinite_navigation_and_ambiguous_signal_declarations_fail_closed():
    text = nav_text(constellation()).replace(f'{0.:19.12E}', f'{float("nan"):19.12E}', 1)
    with pytest.raises(ValueError, match='nonfinite'):
        broadcast_navigation(text.encode('ascii'))
    text = rinex('LOCAL', POSITIONS['local'], {}).replace('G    2 C1C C2W', 'G    3 C1C C2W')
    with pytest.raises(ValueError, match='count mismatch'):
        reference_codes(text, DAY)


def test_cli_creates_report_and_never_overwrites_existing_evidence(tmp_path):
    paths, nav = source_files(tmp_path)
    output = tmp_path / 'report.json'
    command = [sys.executable, '-m', 'pnt', 'analyze', DAY.isoformat(), str(paths['local']), str(nav),
               '--reference', 'A=' + str(paths['A']), '--reference', 'B=' + str(paths['B']),
               '--start', str(TIME), '--stop', str(TIME + 30), '--output', str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report_bytes = output.read_bytes()
    assert json.loads(report_bytes)['status'] == 'DIAGNOSTICS_AVAILABLE'
    repeated = subprocess.run(command, capture_output=True, text=True)
    assert repeated.returncode == 2
    assert 'already exists' in repeated.stderr
    assert output.read_bytes() == report_bytes
