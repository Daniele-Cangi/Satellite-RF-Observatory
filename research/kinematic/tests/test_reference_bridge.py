from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from positioning.context import Context
from research.kinematic import reference_bridge as bridge
from research.kinematic.reference_fixture import (BASE_SECOND, CLOCK, DAY, REFERENCES, STATION,
                                                  TAGS, TARGET, TYPES, fixture_texts, hline)
from research.kinematic.rinex_observations import RinexRejected, parse_reference_observations
from research.kinematic.s2b_validation import RAW_COVARIANCE, parse_fixture, perturb_observations, run

FIXTURES = Path(__file__).parent/'fixtures'


@pytest.fixture(scope='module')
def texts():
    return ((FIXTURES/'s2b_observations.rnx').read_text(), (FIXTURES/'s2b_navigation.rnx').read_text())


@pytest.fixture(scope='module')
def study():
    return run()


def test_committed_full_files_and_independent_clock_doppler_recovery(texts, study):
    assert texts == fixture_texts()
    assert study['criteria_pass'], study['criteria']
    nominal = study['cases'][0]
    assert len(nominal['import']['samples']) == 44
    assert nominal['import']['tags_s'] == TAGS.tolist()
    assert nominal['import']['receiver_identity'] == ['SYNTHETIC-001', 'INERTIAL-GENERATOR', '1']
    np.testing.assert_allclose(nominal['calibration']['clock_coefficients'], CLOCK, atol=.001)
    assert len(nominal['calibration']['doppler_residuals_m_s']) == 44
    assert nominal['real_rf_qualified'] is False


@pytest.mark.parametrize('label,value,reason', [
    ('SYS / SCALE FACTOR', 'G    10', 'UNQUALIFIED_HEADER'),
    ('SYS / DCBS APPLIED', 'G UNKNOWN', 'UNQUALIFIED_HEADER'),
    ('SYS / PCVS APPLIED', 'G UNKNOWN', 'UNQUALIFIED_HEADER'),
    ('ANTENNA: DELTA X/Y/Z', '1 2 3', 'UNQUALIFIED_HEADER'),
    ('RCV CLOCK OFFS APPL', '     1', 'APPLIED_RECEIVER_CLOCK_CORRECTION'),
    ('MARKER TYPE', 'SPACEBORNE', 'NON_GEODETIC_RECEIVER'),
    ('INTERVAL', '     1.000', 'INTERVAL_DIFFERS_FROM_PLAN'),
    ('REC # / TYPE / VERS', 'INCOMPLETE', 'INCOMPLETE_RECEIVER_IDENTITY'),
])
def test_semantic_header_changes_are_rejected(texts, label, value, reason):
    lines = [row for row in texts[0].splitlines() if row[60:80].strip() != label]
    index = next(i for i, row in enumerate(lines) if row[60:80].strip() == 'END OF HEADER')
    lines.insert(index, hline(value, label))
    with pytest.raises(RinexRejected, match=reason):
        parse_fixture('\n'.join(lines)+'\n')


def test_header_continuation_truncation_duplicates_and_timescale(texts):
    original = texts[0]
    missing_continuation = '\n'.join(row for row in original.splitlines()
        if not (row[:7] == ' '*7 and row[60:80].strip() == 'SYS / # / OBS TYPES'))+'\n'
    with pytest.raises(RinexRejected, match='OBSERVATION_TYPES'):
        parse_fixture(missing_continuation)
    with pytest.raises(RinexRejected, match='OBSERVATION_TYPES'):
        parse_fixture(original.replace('D2W ', 'D1C '))
    with pytest.raises(RinexRejected, match='NON_GPST'):
        parse_fixture(original.replace('GPS', 'UTC'))
    with pytest.raises(RinexRejected, match='MISSING_END_OF_HEADER'):
        parse_fixture(original.split('END OF HEADER')[0])


@pytest.mark.parametrize('flag', [1, 2, 3, 4, 5, 6])
def test_all_event_types_end_the_continuous_arc(texts, flag):
    lines = texts[0].splitlines()
    epochs = [i for i, row in enumerate(lines) if row.startswith('>')]
    parts = lines[epochs[4]].split()
    parts[7] = str(flag)
    lines[epochs[4]] = ' '.join(parts)
    with pytest.raises(RinexRejected, match='EVENT_OR_HEADER_CHANGE'):
        parse_fixture('\n'.join(lines))


def test_missing_epoch_and_missing_predecessor_are_not_synthesized(texts):
    lines = texts[0].splitlines()
    epochs = [i for i, row in enumerate(lines) if row.startswith('>')]
    without_epoch = lines[:epochs[5]]+lines[epochs[6]:]
    parsed = parse_fixture('\n'.join(without_epoch))
    assert parsed['status'] == 'REFERENCE_WINDOW_REJECTED'
    assert any('MISSING_PLANNED_EPOCH' in row['reasons'] for row in parsed['rejections'])
    # Keep the valid predecessor epoch but remove one required row from it.
    missing = lines.copy()
    parts = missing[epochs[0]].split()
    parts[8] = '4'
    missing[epochs[0]] = ' '.join(parts)
    del missing[epochs[0]+1]
    parsed = parse_fixture('\n'.join(missing))
    assert parsed['status'] == 'REFERENCE_WINDOW_REJECTED'
    assert any('GAP_OR_UNKNOWN_PREDECESSOR' in row['reasons'] for row in parsed['rejections'])


def test_target_and_later_measurements_do_not_enter_admitted_payload(texts):
    original = parse_fixture(texts[0])
    lines = texts[0].splitlines()
    last_epoch = max(i for i, row in enumerate(lines) if row.startswith('>'))
    altered = '\n'.join(lines[:last_epoch+1])+ '\nTHIS LATER PAYLOAD IS NOT RINEX\n'
    altered = altered.replace('TARGET PAYLOAD MUST NEVER BE DECODED', 'nan infinity 1e999')
    parsed = parse_fixture(altered)
    assert parsed['source_sha256'] != original['source_sha256']
    assert parsed['admitted_observations_sha256'] == original['admitted_observations_sha256']
    with pytest.raises(RinexRejected, match='INVALID_REFERENCE_WINDOW_PLAN'):
        parse_reference_observations(texts[0], target=TARGET, references=REFERENCES+(TARGET,),
            tags_s=TAGS, step_s=30, base_day=DAY, base_second=BASE_SECOND, raw_covariance=RAW_COVARIANCE)


def test_mixed_rinex_304_skips_non_gps_payload_but_checks_declarations(texts):
    lines = texts[0].splitlines()
    lines[0] = lines[0].replace('3.05', '3.04')
    lines[0] = lines[0][:40]+'M'+lines[0][41:]
    header_end = next(i for i, row in enumerate(lines) if row[60:80].strip() == 'END OF HEADER')
    lines.insert(header_end, hline('R    1 C1C', 'SYS / # / OBS TYPES'))
    mixed = []
    for row in lines:
        if row.startswith('>'):
            parts = row.split()
            parts[8] = '6'
            row = ' '.join(parts)
        mixed.append(row)
        if row.startswith(TARGET):
            mixed.append('R01NONNUMERIC EXCLUDED NON-GPS PAYLOAD')
    parsed = parse_fixture('\n'.join(mixed))
    assert parsed['status'] == 'REFERENCE_WINDOW_PARSED'
    assert parsed['admitted_observations_sha256'] == parse_fixture(texts[0])['admitted_observations_sha256']
    inconsistent = [row for row in mixed if not row.startswith('R    1')]
    with pytest.raises(RinexRejected, match='SATELLITE_SYSTEM_DIFFERS_FROM_HEADER'):
        parse_fixture('\n'.join(inconsistent))


def test_navigation_poisoning_and_numerical_rechecks(texts):
    records, admitted = bridge.admit_navigation(texts[1], target=TARGET, references=REFERENCES)
    _, altered = bridge.admit_navigation(texts[1].replace('POISONED TARGET FIELD', 'nan 1e999'),
                                         target=TARGET, references=REFERENCES)
    assert admitted == altered and 'G08' not in admitted
    record = replace(records['G01'][0], satellite=TARGET)
    with pytest.raises(ValueError, match='target propagation forbidden'):
        bridge.reference_code(record, 0., STATION, CLOCK, context=Context(TARGET, DAY),
                              base_second=BASE_SECOND, propagation='vacuum')
    parsed = parse_fixture(texts[0])
    parsed['samples'][0] = {'satellite': TARGET, 'code_m': object(), 'rate_m_s': object()}
    with pytest.raises(ValueError, match='target observation forbidden'):
        bridge.calibrate_references(parsed, texts[1], covariance=None, propagation='vacuum')


def test_import_failure_stops_before_navigation_or_clock_fit(texts, monkeypatch):
    parsed = parse_fixture(perturb_observations(texts[0], 'missing_doppler'))
    def forbidden(*args, **kwargs):
        raise AssertionError('navigation must not be opened after an import rejection')
    monkeypatch.setattr(bridge, 'admit_navigation', forbidden)
    result = bridge.calibrate_references(parsed, 'NOT NAVIGATION', covariance=None, propagation='vacuum')
    assert result['status'] == 'REFERENCE_WINDOW_REJECTED'
    assert 'clock_coefficients' not in result


def test_wrong_doppler_cannot_be_absorbed_in_the_code_fitted_clock(study):
    good, bad = [row['calibration'] for row in study['cases'][:2]]
    assert good['clock_coefficients'] == bad['clock_coefficients']
    assert good['code_p'] == bad['code_p']
    assert bad['status'] == 'REFERENCE_DOPPLER_REJECTED'


def test_navigation_health_internal_blanks_and_age_are_checked(texts):
    rows = texts[1].splitlines()
    first = next(i for i, row in enumerate(rows) if row.startswith('G01'))
    unhealthy = rows.copy()
    unhealthy[first+6] = unhealthy[first+6][:23]+f'{1.:19.12E}'+unhealthy[first+6][42:]
    with pytest.raises(ValueError, match='unqualified reference'):
        bridge.admit_navigation('\n'.join(unhealthy), target=TARGET, references=REFERENCES)
    missing = rows.copy()
    missing[first+1] = missing[first+1][:23]+' '*19+missing[first+1][42:]
    with pytest.raises(ValueError, match='required navigation field'):
        bridge.admit_navigation('\n'.join(missing), target=TARGET, references=REFERENCES)
    records, _ = bridge.admit_navigation(texts[1], target=TARGET, references=REFERENCES)
    stale_week = replace(records['G01'][0], gps_week=records['G01'][0].gps_week-1)
    with pytest.raises(ValueError, match='outside declared validity'):
        bridge.reference_code(stale_week, 0., STATION, CLOCK, context=Context(TARGET, DAY),
                              base_second=BASE_SECOND, propagation='vacuum')


def test_reference_residual_covariance_accounts_for_shared_code_rate_noise():
    rng = np.random.default_rng(20260910)
    n = 12
    t = np.linspace(-300, 0, n)
    hc = np.column_stack([np.ones(n), t])
    hr = np.column_stack([np.zeros(n), np.ones(n)])
    factor = rng.normal(size=(2*n, 2*n))
    covariance = factor@factor.T+np.eye(2*n)
    clock_cov, predicted = bridge.doppler_residual_covariance(hc, hr, covariance)
    errors = np.linalg.cholesky(covariance)@rng.normal(size=(2*n, 60000))
    # Empirical repeated code fits, then unused-rate errors; not samples from
    # the residual covariance formula being verified.
    wc = np.linalg.cholesky(covariance[:n, :n])
    clock_errors = np.linalg.lstsq(np.linalg.solve(wc, hc), np.linalg.solve(wc, errors[:n]), rcond=None)[0]
    residuals = errors[n:]-hr@clock_errors
    empirical = np.cov(residuals)
    assert np.linalg.norm(empirical-predicted)/np.linalg.norm(predicted) < .025
    naive = covariance[n:, n:]+hr@clock_cov@hr.T
    assert np.linalg.norm(naive-predicted) > .1


def test_common_reference_error_does_not_average_away(texts):
    parsed = parse_fixture(texts[0])
    independent = bridge.sample_covariance(parsed)
    common = bridge.sample_covariance(parsed, common_code_sigma_m=5.)
    n = len(parsed['samples'])
    assert np.ones(n)@(common[:n, :n]-independent[:n, :n])@np.ones(n)/n**2 == pytest.approx(25.)


def test_nominal_neutral_delay_changes_code_with_consistent_units(texts):
    records, _ = bridge.admit_navigation(texts[1], target=TARGET, references=REFERENCES)
    kwargs = {'context': Context(TARGET, DAY), 'base_second': BASE_SECOND}
    vacuum, elevation = bridge.reference_code(records['G01'][0], 0., STATION, CLOCK,
                                               propagation='vacuum', **kwargs)
    delayed, _ = bridge.reference_code(records['G01'][0], 0., STATION, CLOCK,
                                       propagation='nominal_troposphere', **kwargs)
    # Declared v1 sea-level mapping. The small additional difference is due to
    # the earlier emission during neutral propagation, not a free code offset.
    nominal_delay = 2.4*1.001/np.sqrt(.002001+np.sin(np.deg2rad(elevation))**2)
    assert delayed-vacuum == pytest.approx(nominal_delay, abs=1e-4)
    assert 2 < delayed-vacuum < 10


def test_gpst_day_week_crossing_preserves_fractional_tags(texts):
    lines = texts[0].splitlines()
    epoch_indices = [i for i, row in enumerate(lines) if row.startswith('>')]
    selected_tags = np.array([-60., -30., 0.])+.0000001
    base_day = '2026-09-13'
    header = lines[:epoch_indices[0]]
    for i, row in enumerate(header):
        if row[60:80].strip() == 'TIME OF FIRST OBS':
            header[i] = hline(''.join(f'{x:6d}' for x in (2026, 9, 12, 23, 58))+f'{30.0000001:13.7f}'+' '*5+'GPS', 'TIME OF FIRST OBS')
    body = []
    for k, tag in enumerate(np.r_[-90.0000000+.0000001, selected_tags]):
        epoch = datetime.fromisoformat(base_day)+timedelta(seconds=float(np.floor(tag)))
        seconds = epoch.second+(tag-np.floor(tag))
        body.append(f'> {epoch.year} {epoch.month:02} {epoch.day:02} {epoch.hour:02} {epoch.minute:02} {seconds:10.7f}  0  5')
        body.extend(lines[epoch_indices[k]+1:epoch_indices[k]+6])
    parsed = parse_reference_observations('\n'.join(header+body), target=TARGET, references=REFERENCES,
        tags_s=selected_tags, step_s=30, base_day=base_day, base_second=0, raw_covariance=RAW_COVARIANCE)
    assert parsed['status'] == 'REFERENCE_WINDOW_PARSED'
    assert parsed['tags_s'] == selected_tags.tolist()
