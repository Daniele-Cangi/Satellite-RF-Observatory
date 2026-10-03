"""An exposed RF baseline must retain conversion faults, not claim an attack."""

from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import gzip
import json
from pathlib import Path

from pnt.navigation_witness import inspect_navigation, group_issues, read_issues
from pnt.sfrbx import ORBIT_FIELDS, PI, bits, decode_issue


FIXTURE = Path(__file__).parent / 'fixtures' / 'cttc20130404'
RESULT = Path(__file__).resolve().parents[2] / 'research/exploratory/results/pnt_public_rf_navigation_v1.json.gz'


def retained_result():
    return json.loads(gzip.decompress(RESULT.read_bytes()))


def test_native_rf_export_retains_discrepancies_without_issuing_authenticity_verdict():
    report = inspect_navigation(FIXTURE / 'GSDR276o10.26N',
                                {'NOAA': FIXTURE / 'brdc0940.13n.gz'}, '2013-04-04')
    assert report == retained_result()['native_navigation_comparison']
    assert report['coverage']['status_counts'] == {'DIFFERENT_FROM_EXTERNAL': 5}
    assert all(row['witnesses']['NOAA']['matching_records'] == 1 for row in report['records'])
    assert report['assessments']['RF_authenticity'] == 'NOT_ASSESSED'
    assert report['assessments']['attack_attribution'] == 'NOT_ASSESSED'


def test_raw_rf_cycles_expose_export_errors_and_archive_precision_without_relaxing_comparator():
    messages = json.loads((FIXTURE / 'navdata.json').read_bytes())['messages']
    diagnostic = retained_result()['raw_bits_conversion_diagnostic']
    assert len(messages) == diagnostic['receiver_messages'] == 65
    assert Counter(c['status'] for c in diagnostic['cycles']) == {
        'DECODED_ISSUE': 10, 'INCOMPLETE_CYCLE': 5}
    native, _ = read_issues(FIXTURE / 'GSDR276o10.26N')
    exported = {row['identity']: row for row in native}
    archive, _ = read_issues(FIXTURE / 'brdc0940.13n.gz')
    archive = group_issues(archive)
    for cycle in diagnostic['cycles']:
        frames = {}
        for sf, indices in cycle['packet_indices'].items():
            frames[int(sf)] = []
            for index in indices:
                message = messages[index]
                assert message['index'] == index
                assert (message['system'], message['signal']) == ('G', '1C')
                assert f"G{message['prn']:02d}" == cycle['satellite']
                text = message['nav_message']
                assert len(text) == 300 and set(text) <= {'0', '1'}
                assert bytes.fromhex(message['udp_hex']).endswith(text.encode('ascii'))
                data = b''.join((int(text[i:i + 30], 2) >> 6).to_bytes(3, 'big')
                                for i in range(0, 300, 30))
                assert bits(data, 43, 3) == int(sf)
                assert ((bits(data, 24, 17) - int(sf)) * 6) % 604800 == cycle['frame_start_sow']
                frames[int(sf)].append({'data_hex': data.hex()})
        if cycle['status'] == 'INCOMPLETE_CYCLE':
            assert set(frames) != {1, 2, 3}
            continue
        row = decode_issue(cycle['satellite'], frames, '2013-04-04', cycle['frame_start_sow'])
        assert {name: str(value) for name, value in row['values'].items()} == cycle['raw_fields']
        values, written = row['values'], exported[row['identity']]['values']
        assert values['l2_p_flag'] == 0 and written['l2_p_flag'] == 1
        assert values['sv_accuracy_m'] == 2 and written['sv_accuracy_m'] == 0
        expected_l2 = 0 if cycle['satellite'] in {'G01', 'G11', 'G32'} else 1
        assert values['codes_l2'] == 1
        assert archive[row['identity']][0]['values']['codes_l2'] == expected_l2
        # The archive coordinate is descriptive evidence, never a new
        # acceptance tolerance. Reconstruct the nearest ICD integer without
        # changing the 27-field written-decimal comparator above.
        with localcontext() as context:
            context.prec = 80
            scales = {name: Decimal(2) ** power * (PI if angular else 1)
                      for specs in ORBIT_FIELDS.values()
                      for name, _, _, _, power, angular in specs}
            scales.update(af0_s=Decimal(2) ** -31, af1_s_s=Decimal(2) ** -43,
                          af2_s_s2=Decimal(2) ** -55, tgd_s=Decimal(2) ** -31)
            for name, scale in scales.items():
                coordinate = archive[row['identity']][0]['values'][name] / scale
                nearest = coordinate.to_integral_value(rounding=ROUND_HALF_EVEN)
                raw = (values[name] / scale).to_integral_value(rounding=ROUND_HALF_EVEN)
                assert nearest == raw
        if cycle['satellite'] == 'G32':
            assert values['sqrt_a_m_sqrt'] == Decimal('5153.7204875946044921875')
            assert archive[row['identity']][0]['values']['sqrt_a_m_sqrt'] == Decimal('5153.720487600')
