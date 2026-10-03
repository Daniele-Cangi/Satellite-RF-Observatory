"""Bit sensitivity, ambiguous archives and non-authenticating qualification."""

from copy import deepcopy
from decimal import Decimal, localcontext
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from pnt.navigation_representation import compare_fields, field_candidates, qualify_fields, qualify_navigation_records
from pnt.navigation_witness import inspect_navigation, group_issues
from pnt.sfrbx import ORBIT_FIELDS, bits, read_sfrbx_issues
from pnt.tests.test_sfrbx import DAY, FIXTURE, PACKETS, set_bits, write
from pnt.tests.test_public_rf_navigation import FIXTURE as RF_FIXTURE, replay_monitor_messages


def original(tmp_path):
    return read_sfrbx_issues(write(tmp_path, PACKETS[:3]), DAY)[0][0]


BIT_FIELDS = [(sf, name, offset, length)
              for sf, specs in ORBIT_FIELDS.items()
              for name, offset, length, *_ in specs if name != 'iode']
BIT_FIELDS += [(1, 'af0_s', 216, 22), (1, 'af1_s_s', 200, 16),
               (1, 'af2_s_s2', 192, 8), (1, 'tgd_s', 160, 8)]


@pytest.mark.parametrize('sf,name,offset,length', BIT_FIELDS)
def test_each_clock_orbit_and_delay_lsb_change_remains_a_content_difference(
        tmp_path, sf, name, offset, length):
    rows, source = read_sfrbx_issues(write(tmp_path, PACKETS[:3]), DAY)
    row = rows[0]
    data = bytes.fromhex(source['frames'][sf - 1]['data_hex'])
    changed = list(PACKETS[:3])
    # One data bit in the receiver-decoded payload, not a valid RF synthesis.
    changed[sf - 1] = set_bits(changed[sf - 1], offset, length, bits(data, offset, length) ^ 1)
    other = read_sfrbx_issues(write(tmp_path, changed), DAY)[0][0]
    comparison = compare_fields(qualify_fields(row['intervals']), qualify_fields(other['intervals']))
    assert comparison['status'] == 'DIFFERENT_BROADCAST_FIELDS'
    assert comparison['qualified_differing_fields'] == [name]
    assert comparison['unqualified_fields'] == []


def test_serialization_rounding_can_identify_one_value_but_trailing_zero_loss_cannot():
    precise = Decimal('5153.79886246')
    assert field_candidates('sqrt_a_m_sqrt', (precise - Decimal('5e-9'), precise + Decimal('5e-9')))[
        'status'] == 'UNIQUE_BROADCAST_VALUE'
    # Retained NOAA G32 value: neither its written interval nor a nearest-bit
    # repair establishes that the archive preserved the broadcast value.
    overprecise = Decimal('5153.720487600')
    result = field_candidates('sqrt_a_m_sqrt', (overprecise - Decimal('5e-10'), overprecise + Decimal('5e-10')))
    assert result['status'] == 'NO_BROADCAST_VALUE'
    assert result['candidate_count'] == 0
    assert 'encoded_value' not in result


def test_coarse_zero_af2_covers_every_encoding_without_hiding_one_bit_changes():
    result = field_candidates('af2_s_s2', (Decimal('-5e-13'), Decimal('5e-13')))
    assert result['status'] == 'AMBIGUOUS_REPRESENTATION'
    assert result['candidate_count'] == 256
    assert result['encoded_bounds'] == [-128, 127]
    assert 'encoded_value' not in result
    fine = field_candidates('af2_s_s2', (Decimal('-5e-30'), Decimal('5e-30')))
    assert fine['status'] == 'UNIQUE_BROADCAST_VALUE'
    assert fine['encoded_value'] == 0


def test_closed_boundaries_and_signed_width_do_not_round_away_ambiguity():
    with localcontext() as context:
        context.prec = 80
        step = Decimal(2) ** -31
        result = field_candidates('af0_s', (Decimal(0), step))
        assert result['candidate_count'] == 2 and result['encoded_bounds'] == [0, 1]
        halfway = field_candidates('af0_s', (step / 2, step / 2))
        assert halfway['status'] == 'NO_BROADCAST_VALUE'
        minimum = Decimal(-2**21) * step
        assert field_candidates('af0_s', (minimum, minimum))['encoded_value'] == -2**21
        assert field_candidates('af0_s', (minimum - step, minimum - step))['candidate_count'] == 0


@pytest.mark.parametrize('name,value,status', [
    ('sv_accuracy_m', '0', 'NO_BROADCAST_VALUE'),  # Exported index is not nominal metres.
    ('sv_accuracy_m', '8192', 'UNAVAILABLE_ACCURACY'),
    ('codes_l2', '0', 'INVALID_L2_CODE_METADATA'),
    ('codes_l2', '3', 'INVALID_L2_CODE_METADATA'),
    ('tgd_s', '-0.000000059604644775390625', 'UNAVAILABLE_GROUP_DELAY'),
    ('toe_sow', '604800', 'NO_BROADCAST_VALUE'),
])
def test_invalid_or_unavailable_metadata_is_retained_without_qualification(name, value, status):
    value = Decimal(value)
    assert field_candidates(name, (value, value))['status'] == status


def test_nominal_ura_is_an_index_mapping_and_continuous_week_is_not_reduced():
    assert field_candidates('sv_accuracy_m', (Decimal('2.8'), Decimal('2.8')))['encoded_value'] == 1
    assert field_candidates('gps_week', (Decimal(2331), Decimal(2331)))['encoded_value'] == 2331
    with pytest.raises(ValueError, match='nonfinite'):
        field_candidates('af0_s', (Decimal('NaN'), Decimal(0)))


@pytest.mark.parametrize('name,first,second', [
    ('iode', 57, 56), ('iodc', 57, 313), ('gps_week', 2331, 2330),
    ('l2_p_flag', 0, 1), ('sv_health', 0, 1), ('codes_l2', 1, 2),
])
def test_all_integer_fields_keep_exact_content_instead_of_decimal_tolerance(name, first, second):
    left = field_candidates(name, (Decimal(first), Decimal(first)))
    right = field_candidates(name, (Decimal(second), Decimal(second)))
    assert left['status'] == right['status'] == 'UNIQUE_BROADCAST_VALUE'
    assert left['encoded_value'] == first and right['encoded_value'] == second


def test_missing_issues_conflicting_duplicates_and_witnesses_remain_visible(tmp_path):
    row = original(tmp_path)
    changed = read_sfrbx_issues(write(tmp_path, [set_bits(PACKETS[0], 216, 22, 1), *PACKETS[1:3]]), DAY)[0][0]
    changed['index'] = 1
    witnesses = {'original': group_issues([row]), 'changed': group_issues([changed]), 'missing': {}}
    report = qualify_navigation_records([row], witnesses)
    result = report['records'][0]
    assert result['status'] == 'EXTERNAL_RECORD_CONFLICT'
    assert result['joint_external_conflicting_fields'] == ['af0_s']
    assert result['witnesses']['missing']['status'] == 'MISSING_ISSUE'
    assert result['witnesses']['changed']['qualified_differing_fields'] == ['af0_s']
    duplicate = qualify_navigation_records([row], {'duplicates': group_issues([row, changed])})
    assert duplicate['records'][0]['status'] == 'EXTERNAL_RECORD_CONFLICT'
    assert duplicate['records'][0]['witnesses']['duplicates']['source_record_indices'] == [0, 1]
    local = qualify_navigation_records([row, changed], {'original': group_issues([row])})
    assert local['status_counts'] == {'CONFLICTING_LOCAL_RECORDS': 2}


def test_a_different_issue_is_not_substituted_and_an_ambiguous_source_stays_unqualified(tmp_path):
    row = original(tmp_path)
    other = deepcopy(row)
    other['identity'] = (*row['identity'][:2], Decimal(2332), *row['identity'][3:])
    missing = qualify_navigation_records([row], {'other_week': group_issues([other])})
    assert missing['status_counts'] == {'MISSING_ISSUE': 1}
    other['identity'] = row['identity']
    other['intervals']['af2_s_s2'] = (Decimal('-5e-13'), Decimal('5e-13'))
    ambiguous = qualify_navigation_records([row], {'coarse': group_issues([other])})
    assert ambiguous['status_counts'] == {'REPRESENTATION_UNQUALIFIED': 1}
    assert ambiguous['records'][0]['unqualified_fields'] == ['af2_s_s2']
    same = qualify_navigation_records([row], {'copy': group_issues([row])})
    assert same['status_counts'] == {'SAME_BROADCAST_FIELDS': 1}


def test_new_diagnostics_preserve_the_entire_old_ubx_report_and_out_of_day_issue(tmp_path):
    local = write(tmp_path, PACKETS)
    archive = tmp_path / 'archive.n'
    archive.write_text(FIXTURE['external_rinex'], encoding='ascii')
    old = inspect_navigation(local, {'archive': archive}, DAY, local_format='ubx')
    new = inspect_navigation(local, {'archive': archive}, DAY, local_format='ubx', qualify_lnav=True)
    assert new['schema'] == 'pnt-navigation-witness-v3'
    assert new['lnav_representation']['status_counts'] == {'MISSING_ISSUE': 2, 'REPRESENTATION_UNQUALIFIED': 1}
    assert new['lnav_representation']['records'][0]['unqualified_fields'] == ['af2_s_s2']
    assert new['records'][2]['toc_gpst'] == '2024-10-01T14:00:00+00:00'
    new['schema'] = new.pop('written_decimal_schema')
    del new['lnav_representation']
    assert new == old


def test_real_rf_native_export_stays_discordant_and_conversion_failures_are_separate(tmp_path):
    local, archive = RF_FIXTURE / 'GSDR276o10.26N', RF_FIXTURE / 'brdc0940.13n.gz'
    old = inspect_navigation(local, {'NOAA': archive}, '2013-04-04')
    new = inspect_navigation(local, {'NOAA': archive}, '2013-04-04', qualify_lnav=True)
    assert new['records'] == old['records']
    assert new['coverage']['status_counts'] == {'DIFFERENT_FROM_EXTERNAL': 5}
    assert new['lnav_representation']['status_counts'] == {'REPRESENTATION_UNQUALIFIED': 5}
    assert all('sv_accuracy_m' in row['unqualified_fields'] for row in new['lnav_representation']['records'])
    assert new['assessments']['attack_attribution'] == 'NOT_ASSESSED'
    output = tmp_path / 'qualified.json'
    command = [sys.executable, '-m', 'pnt', 'navigation', '2013-04-04', str(local),
               '--witness', f'NOAA={archive}', '--qualify-lnav', '--output', str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert json.loads(output.read_bytes()) == new
    assert 'REPRESENTATION_UNQUALIFIED' in first.stdout
    assert subprocess.run(command, capture_output=True, text=True).returncode == 2


def test_public_rf_raw_bits_do_not_inherit_exporter_errors_or_infer_archive_precision():
    from pnt.navigation_witness import read_issues
    _, rows = replay_monitor_messages()
    archive, _ = read_issues(RF_FIXTURE / 'brdc0940.13n.gz')
    report = qualify_navigation_records(rows, {'NOAA': group_issues(archive)})
    assert report['status_counts'] == {'REPRESENTATION_UNQUALIFIED': 10}
    assert len(report['records']) == 10
    for result in report['records']:
        assert 'af2_s_s2' in result['unqualified_fields']
        assert result['fields']['sv_accuracy_m']['status'] == 'SAME_ENCODED_VALUE'
        assert result['fields']['l2_p_flag']['status'] == 'SAME_ENCODED_VALUE'
        if result['satellite'] in {'G01', 'G11', 'G32'}:
            assert result['fields']['codes_l2']['external']['status'] == 'INVALID_L2_CODE_METADATA'
        if result['satellite'] == 'G32':
            assert result['fields']['sqrt_a_m_sqrt']['external']['status'] == 'NO_BROADCAST_VALUE'


def test_retained_representation_result_replays_from_exact_inputs():
    from pnt.navigation_witness import read_issues
    path = Path(__file__).resolve().parents[2] / 'research/exploratory/results/pnt_navigation_representation_v1.json.gz'
    saved = json.loads(gzip.decompress(path.read_bytes()))
    for filename, receipt in saved['inputs'].items():
        data = (Path(__file__).resolve().parents[2] / filename).read_bytes()
        assert len(data) == receipt['bytes']
        assert hashlib.sha256(data).hexdigest() == receipt['sha256']
    native = inspect_navigation(RF_FIXTURE / 'GSDR276o10.26N',
                                {'NOAA': RF_FIXTURE / 'brdc0940.13n.gz'}, '2013-04-04', qualify_lnav=True)
    cycles, rows = replay_monitor_messages()
    archive, _ = read_issues(RF_FIXTURE / 'brdc0940.13n.gz')
    assert saved['native_report'] == native
    assert saved['raw_bits_representation'] == qualify_navigation_records(rows, {'NOAA': group_issues(archive)})
    assert saved['receiver_cycle_counts'] == {'DECODED_ISSUE': 10, 'INCOMPLETE_CYCLE': 5}
