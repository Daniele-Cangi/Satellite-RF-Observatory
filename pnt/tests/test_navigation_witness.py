"""Decoded-message comparison, issue coverage, conflicts and clock ambiguity."""

from dataclasses import replace
import gzip
import json
import subprocess
import sys

import pytest

from pnt.model import day_context, fit_clock
from pnt.navigation_witness import inspect_navigation
from pnt.tests.test_fixed_site import constellation, nav_text, observations, DAY, TIME, POSITIONS


def write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding='ascii')
    return path


def change(text, row, column, value, *, precision=12):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line[60:80].strip() == 'END OF HEADER') + 1
    offset = (22 if row == 0 else 3) + column * 19
    line = lines[start + row]
    lines[start + row] = line[:offset] + f'{value:19.{precision}E}' + line[offset + 19:]
    return '\n'.join(lines) + '\n'


def inspect(tmp_path, local_text, *external_texts):
    local = write(tmp_path, 'local.n', local_text)
    peers = {f'W{i}': write(tmp_path, f'witness{i}.n', text) for i, text in enumerate(external_texts)}
    return inspect_navigation(local, peers, DAY.isoformat())


def test_identical_message_content_with_different_transmission_times_is_compatible(tmp_path):
    original = nav_text(constellation())
    altered = change(original, 7, 0, 123456.)
    report = inspect(tmp_path, original, altered)
    assert report['coverage']['status_counts'] == {'COMPATIBLE_WITH_EXTERNAL': 8}
    assert report['coverage']['unique_external_file_hashes'] == 1
    assert report['coverage']['external_files_equal_to_local'] == []
    assert report['assessments']['RF_authenticity'] == 'NOT_ASSESSED'
    assert report['assessments']['source_independence'] == 'NOT_QUALIFIED'


def test_written_decimal_rounding_is_not_reported_as_a_payload_disagreement(tmp_path):
    original = change(nav_text(constellation()), 0, 0, 1.234567890123e-4)
    rounded = change(original, 0, 0, 1.234567890123e-4, precision=11)
    report = inspect(tmp_path, original, rounded)
    assert report['records'][0]['status'] == 'COMPATIBLE_WITH_EXTERNAL'
    different = change(original, 0, 0, 1.234567990123e-4, precision=11)
    report = inspect(tmp_path, original, different)
    assert report['records'][0]['status'] == 'DIFFERENT_FROM_EXTERNAL'
    assert report['records'][0]['witnesses']['W0']['differing_fields'] == ['af0_s']


@pytest.mark.parametrize('row,column,value,field', [(0, 0, 1e-6, 'af0_s'),
                                                  (2, 3, 6000., 'sqrt_a_m_sqrt'),
                                                  (5, 1, 3., 'codes_l2'),
                                                  (6, 1, 63., 'sv_health')])
def test_same_issue_different_fields_include_unhealthy_records_and_model_omissions(
        tmp_path, row, column, value, field):
    original = nav_text(constellation())
    report = inspect(tmp_path, change(original, row, column, value), original)
    assert report['records'][0]['status'] == 'DIFFERENT_FROM_EXTERNAL'
    peer = report['records'][0]['witnesses']['W0']
    assert peer['differing_fields'] == [field]
    assert field in peer['records'][0]['fields']
    assert report['coverage']['selected_local_records'] == 8
    if field == 'sv_health':
        assert report['sources']['local']['unhealthy_records_retained'] == 1


@pytest.mark.parametrize('row,column,value', [(6, 3, 1.), (3, 0, 432000.)])
def test_changed_issue_identity_remains_unmatched_without_nearest_record_fallback(tmp_path, row, column, value):
    original = nav_text(constellation())
    report = inspect(tmp_path, change(original, row, column, value), original)
    assert report['records'][0]['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['records'][0]['witnesses']['W0']['status'] == 'MISSING_ISSUE'
    assert len(report['records']) == 8


def test_disagreeing_witnesses_are_not_resolved_by_matching_majority(tmp_path):
    original = nav_text(constellation())
    different = change(original, 0, 0, 1e-6)
    report = inspect(tmp_path, original, original, original, different)
    assert report['records'][0]['status'] == 'EXTERNAL_RECORD_CONFLICT'
    assert report['coverage']['unique_external_file_hashes'] == 2
    assert report['coverage']['external_files_equal_to_local'] == ['W0', 'W1']


@pytest.mark.parametrize('side', ['local', 'external'])
def test_conflicting_duplicate_issues_are_retained_without_picking_matching_variant(tmp_path, side):
    original = nav_text(constellation())
    changed = change(original, 0, 0, 1e-6)
    duplicate_block = '\n'.join(changed.splitlines()[2:10]) + '\n'
    duplicate = original + duplicate_block
    report = inspect(tmp_path, duplicate if side == 'local' else original,
                     duplicate if side == 'external' else original)
    status = 'CONFLICTING_LOCAL_RECORDS' if side == 'local' else 'EXTERNAL_RECORD_CONFLICT'
    assert report['records'][0]['status'] == status
    if side == 'local':
        assert report['coverage']['selected_local_records'] == 9
        assert report['records'][-1]['status'] == status
    else:
        assert report['records'][0]['witnesses']['W0']['matching_records'] == 2


def test_uncovered_file_and_requested_window_are_visible(tmp_path):
    original = nav_text(constellation())
    local = write(tmp_path, 'local.n', original)
    peer = write(tmp_path, 'witness.n', original)
    report = inspect_navigation(local, {'external': peer}, DAY.isoformat(), start_s=0, stop_s=TIME)
    assert report['status'] == 'INSUFFICIENT_EVIDENCE'
    assert report['coverage']['local_records_outside_window'] == 8
    assert report['records'] == []


@pytest.mark.parametrize('kind', ['nan', 'fractional_issue', 'missing_iodc', 'truncated'])
def test_invalid_navigation_input_fails_instead_of_discarding_records(tmp_path, kind):
    text = nav_text(constellation())
    if kind == 'nan':
        text = change(text, 0, 0, float('nan'))
    elif kind == 'fractional_issue':
        text = change(text, 6, 3, .5)
    elif kind == 'missing_iodc':
        lines = text.splitlines()
        lines[8] = lines[8][:60] + ' ' * 19
        text = '\n'.join(lines) + '\n'
    else:
        text = '\n'.join(text.splitlines()[:-1]) + '\n'
    with pytest.raises(ValueError):
        inspect(tmp_path, text, nav_text(constellation()))


def test_common_satellite_clock_forgery_can_be_absorbed_locally_but_fields_disagree(tmp_path):
    navigation = constellation()
    shift = 2048 * 2**-31
    forged = {sv: [replace(records[0], af0_s=records[0].af0_s + shift)]
              for sv, records in navigation.items()}
    data = observations(navigation)['local']
    codes = {sv: pair[0] for sv, pair in data.items()}
    original_fit = fit_clock(codes, POSITIONS['local'], {sv: r[0] for sv, r in navigation.items()},
                             TIME, day_context(DAY))
    forged_fit = fit_clock(codes, POSITIONS['local'], {sv: r[0] for sv, r in forged.items()},
                           TIME, day_context(DAY))
    assert forged_fit['clock_m'] - original_fit['clock_m'] == pytest.approx(285.904405, abs=1e-5)
    assert forged_fit['max_absolute_satellite_residual_m'] < .001
    report = inspect(tmp_path, nav_text(forged), nav_text(navigation))
    assert report['coverage']['status_counts'] == {'DIFFERENT_FROM_EXTERNAL': 8}
    assert all(row['witnesses']['W0']['differing_fields'] == ['af0_s'] for row in report['records'])
    assert report['assessments']['absolute_time'] == 'INSUFFICIENT_EVIDENCE'


def test_cli_handles_gzip_and_refuses_overwrite(tmp_path):
    text = nav_text(constellation()).encode('ascii')
    local = tmp_path / 'local.n.gz'
    local.write_bytes(gzip.compress(text))
    witness = tmp_path / 'external.n'
    witness.write_bytes(text)
    output = tmp_path / 'message.json'
    command = [sys.executable, '-m', 'pnt', 'navigation', DAY.isoformat(), str(local),
               '--witness', f'external={witness}', '--output', str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    original = output.read_bytes()
    assert json.loads(original)['coverage']['selected_local_records'] == 8
    assert subprocess.run(command, capture_output=True, text=True).returncode == 2
    assert output.read_bytes() == original
