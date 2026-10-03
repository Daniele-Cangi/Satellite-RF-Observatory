"""An exposed RF baseline must retain conversion faults, not claim an attack."""

from collections import Counter
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import gzip
import json
from pathlib import Path

from pnt.navigation_witness import FIELDS, inspect_navigation, group_issues, read_issues
from pnt.sfrbx import ORBIT_FIELDS, PI, bits, decode_issue


FIXTURE = Path(__file__).parent / 'fixtures' / 'cttc20130404'
RESULT = Path(__file__).resolve().parents[2] / 'research/exploratory/results/pnt_public_rf_navigation_v1.json.gz'


def retained_result():
    return json.loads(gzip.decompress(RESULT.read_bytes()))


def replay_monitor_messages():
    """Reconstruct every cycle from ordered input, without saved-result groups."""
    messages = json.loads((FIXTURE / 'navdata.json').read_bytes())['messages']
    current, cycles, cei_indices = {}, [], []
    for index, message in enumerate(messages):
        assert message['index'] == index
        assert (message['system'], message['signal']) == ('G', '1C')
        satellite = f"G{message['prn']:02d}"
        text = message['nav_message']
        assert len(text) == 300 and set(text) <= {'0', '1'}
        assert bytes.fromhex(message['udp_hex']).endswith(text.encode('ascii'))
        data = b''.join((int(text[i:i + 30], 2) >> 6).to_bytes(3, 'big')
                        for i in range(0, 300, 30))
        how, sf = bits(data, 24, 17), bits(data, 43, 3)
        assert data[0] == 0x8b and sf in (1, 2, 3, 4, 5) and how < 100800
        start = ((how - sf) * 6) % 604800
        assert start % 30 == 0
        if sf in (4, 5):
            if satellite in current and current[satellite]['frame_start_sow'] != start:
                del current[satellite]
            continue
        cei_indices.append(index)
        if satellite not in current or current[satellite]['frame_start_sow'] != start:
            current[satellite] = {'satellite': satellite, 'frame_start_sow': start, 'frames': {}}
            cycles.append(current[satellite])
        current[satellite]['frames'].setdefault(sf, []).append({'index': index, 'data_hex': data.hex()})
    archive, _ = read_issues(FIXTURE / 'brdc0940.13n.gz')
    archive = group_issues(archive)
    replayed, records = [], []
    with localcontext() as context:
        context.prec = 80
        scales = {name: Decimal(2) ** power * (PI if angular else 1)
                  for specs in ORBIT_FIELDS.values()
                  for name, _, _, _, power, angular in specs}
        scales.update(af0_s=Decimal(2) ** -31, af1_s_s=Decimal(2) ** -43,
                      af2_s_s2=Decimal(2) ** -55, tgd_s=Decimal(2) ** -31)
        for cycle in cycles:
            frames = cycle['frames']
            info = {key: value for key, value in cycle.items() if key != 'frames'}
            info['packet_indices'] = {str(sf): [frame['index'] for frame in entries]
                                      for sf, entries in sorted(frames.items())}
            info['missing_subframes'] = [sf for sf in (1, 2, 3) if sf not in frames]
            info['conflicting_subframes'] = [sf for sf, entries in sorted(frames.items())
                                             if len({frame['data_hex'][12:] for frame in entries}) > 1]
            assert not info['conflicting_subframes']
            if info['missing_subframes']:
                info['status'] = 'INCOMPLETE_CYCLE'
            else:
                row = decode_issue(cycle['satellite'], frames, '2013-04-04', cycle['frame_start_sow'])
                row['index'] = len(records)
                records.append(row)
                values = row['values']
                matching = archive[row['identity']]
                assert len(matching) == 1
                written = matching[0]['values']
                quantization, different = {}, []
                for name in FIELDS:
                    if name in scales:
                        coordinate = written[name] / scales[name]
                        nearest = coordinate.to_integral_value(rounding=ROUND_HALF_EVEN)
                        raw = (values[name] / scales[name]).to_integral_value(rounding=ROUND_HALF_EVEN)
                        equal = nearest == raw
                        quantization[name] = {'archive_coordinate_lsb': str(coordinate),
                                              'archive_distance_from_integer_lsb': str(abs(coordinate - nearest)),
                                              'archive_nearest_integer': str(nearest), 'rf_integer': str(raw),
                                              'same_nearest_integer': equal}
                    else:
                        equal = values[name] == written[name]
                    if not equal:
                        different.append(name)
                info.update(status='DECODED_ISSUE', raw_fields={name: str(value) for name, value in values.items()},
                            matching_external_records=len(matching), archive_quantization_diagnostic=quantization,
                            nearest_integer_differing_fields=different)
            replayed.append(info)
    referenced = [index for cycle in replayed for indices in cycle['packet_indices'].values() for index in indices]
    assert len(set(referenced)) == len(referenced)
    assert sorted(referenced) == cei_indices
    return replayed, records


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
    replayed, rows = replay_monitor_messages()
    assert replayed == diagnostic['cycles']
    native, _ = read_issues(FIXTURE / 'GSDR276o10.26N')
    exported = {row['identity']: row for row in native}
    archive, _ = read_issues(FIXTURE / 'brdc0940.13n.gz')
    archive = group_issues(archive)
    for row in rows:
        values, written = row['values'], exported[row['identity']]['values']
        assert values['l2_p_flag'] == 0 and written['l2_p_flag'] == 1
        assert values['sv_accuracy_m'] == 2 and written['sv_accuracy_m'] == 0
        expected_l2 = 0 if row['identity'][0] in {'G01', 'G11', 'G32'} else 1
        assert values['codes_l2'] == 1
        assert archive[row['identity']][0]['values']['codes_l2'] == expected_l2
        if row['identity'][0] == 'G32':
            assert values['sqrt_a_m_sqrt'] == Decimal('5153.7204875946044921875')
            assert archive[row['identity']][0]['values']['sqrt_a_m_sqrt'] == Decimal('5153.720487600')
