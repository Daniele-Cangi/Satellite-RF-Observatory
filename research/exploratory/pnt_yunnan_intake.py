"""Describe the exposed Yunnan recording; no retiming, detector or network fit."""

import argparse
from collections import Counter
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tarfile


INPUTS = Path(__file__).with_name('inputs') / 'yunnan20231221'
WINDOWS = (
    ('before_first_table13_attack', '12:00:00', '12:32:30'),
    ('attack_1', '12:32:30', '12:37:00'),
    ('between_1_2', '12:37:00', '12:38:41'),
    ('attack_2', '12:38:41', '12:41:20'),
    ('between_2_3', '12:41:20', '12:44:05'),
    ('attack_3', '12:44:05', '12:55:50'),
    ('between_3_4', '12:55:50', '12:57:00'),
    ('attack_4_partial', '12:57:00', '13:00:00'),
    ('after_logged_disturbance', '18:00:00', '19:00:00'),
)


def describe_rawx(message, filename_label=None):
    """Keep receiver time and acquisition labels distinct; honor code validity."""
    label = filename_label or message['start_time']
    host = datetime.fromisoformat(label)
    gpst = datetime(1980, 1, 6) + timedelta(
        weeks=message['week'], seconds=message['rcvTow'])
    receiver_utc = gpst - timedelta(seconds=message['leapS'])
    signals, valid_l1, invalid_flagged_l1 = Counter(), 0, 0
    for index in range(1, message['numMeas'] + 1):
        suffix = f'_{index:02d}'
        gnss, signal = message['gnssId' + suffix], message['sigId' + suffix]
        signals[f'{gnss}:{signal}'] += 1
        code = message['prMes' + suffix]
        if gnss == 0 and signal == 0 and message['prValid' + suffix] == 1:
            if not isinstance(code, (int, float)) or not 0 < code < float('inf'):
                invalid_flagged_l1 += 1
            else:
                valid_l1 += 1
    grid_error_s = abs(message['rcvTow'] - round(message['rcvTow'] / 30) * 30)
    return {
        'host_label': label, 'message_start_time': message['start_time'],
        'receiver_gpst': gpst.isoformat(timespec='microseconds'),
        'host_minus_receiver_utc_s': (host - receiver_utc).total_seconds(),
        'receiver_declared_date_differs_from_host': receiver_utc.date() != host.date(),
        'receiver_clock_reset': message['clkReset'],
        'gps_l1_rows': signals['0:0'], 'gps_l1_prvalid_rows': valid_l1,
        'gps_l1_flagged_valid_but_invalid_value_rows': invalid_flagged_l1,
        'within_existing_1ms_grid': grid_error_s <= 0.001,
        'signal_counts': dict(sorted(signals.items())),
    }


def summarize(rows, expected):
    signals = Counter()
    for row in rows:
        signals.update(row['signal_counts'])
    return {
        'expected_host_seconds': expected, 'rawx_messages': len(rows),
        'missing_host_seconds': expected - len(rows),
        'filename_and_start_time_disagreements': sum(
            row['host_label'] != row['message_start_time'] for row in rows),
        'signal_counts': dict(sorted(signals.items())),
        'gps_l1_rows': sum(row['gps_l1_rows'] for row in rows),
        'gps_l1_prvalid_rows': sum(row['gps_l1_prvalid_rows'] for row in rows),
        'gps_l1_flagged_valid_but_invalid_value_rows': sum(
            row['gps_l1_flagged_valid_but_invalid_value_rows'] for row in rows),
        'epochs_with_fewer_than_four_valid_gps_l1': sum(
            row['gps_l1_prvalid_rows'] < 4 for row in rows),
        'clock_reset_messages': sum(row['receiver_clock_reset'] for row in rows),
        'receiver_date_differs_from_host_messages': sum(
            row['receiver_declared_date_differs_from_host'] for row in rows),
        'within_existing_1ms_grid_messages': sum(
            row['within_existing_1ms_grid'] for row in rows),
        'host_minus_receiver_utc_range_s': [
            min(row['host_minus_receiver_utc_s'] for row in rows),
            max(row['host_minus_receiver_utc_s'] for row in rows)],
    }


def load_streams(inputs=INPUTS):
    """Read retained native bytes by source identity, without joining streams."""
    archive = inputs / 'receiver_messages.tar.gz'
    streams = {hour: {kind: {} for kind in ('RXM-RAWX', 'NAV-PVT', 'NAV-CLOCK')}
               for hour in ('12', '18')}
    with tarfile.open(archive, 'r:gz') as source:
        for member in source:
            if not member.isfile():
                continue
            parts = member.name.split('/')
            message = json.loads(source.extractfile(member).read())
            if parts == ['processed', 'pvtSolution12.json']:
                processed_pvt = message
                continue
            hour, kind, filename = parts
            key = filename[:10] + ' ' + filename[11:-5].replace('-', ':')
            if key in streams[hour][kind]:
                raise ValueError('duplicate source filename within a message stream')
            streams[hour][kind][key] = message
    return streams, processed_pvt


def run(inputs=INPUTS):
    streams, processed_pvt = load_streams(inputs)
    all_rows, hours = [], {}
    for hour, kinds in streams.items():
        rows = [describe_rawx(message, key) for key, message in sorted(kinds['RXM-RAWX'].items())]
        all_rows.extend(rows)
        hours[hour] = summarize(rows, 3600)
        hours[hour]['message_counts'] = {kind: len(values) for kind, values in kinds.items()}
        hours[hour]['duplicate_start_time_values'] = {
            kind: sum(count - 1 for count in Counter(
                message['start_time'] for message in values.values()).values())
            for kind, values in kinds.items()}
        shared = kinds['NAV-PVT'].keys() & kinds['NAV-CLOCK'].keys()
        hours[hour]['pvt_clock_shared_host_labels'] = len(shared)
        hours[hour]['pvt_clock_different_itow_on_same_host_label'] = sum(
            kinds['NAV-PVT'][key]['iTOW'] != kinds['NAV-CLOCK'][key]['iTOW'] for key in shared)
    windows = {}
    for name, start, stop in WINDOWS:
        begin, end = (datetime.fromisoformat('2023-12-21 ' + value) for value in (start, stop))
        selected = [row for row in all_rows
                    if begin <= datetime.fromisoformat(row['host_label']) < end]
        windows[name] = {'host_interval_start': begin.isoformat(),
                         'host_interval_stop_exclusive': end.isoformat(),
                         **summarize(selected, int((end - begin).total_seconds()))}
    first = streams['12']['RXM-RAWX']['2023-12-21 12:00:00']
    excerpt = json.loads((inputs / 'processed_observation12_first_epoch.json').read_bytes())
    sample_index = next(i for i in range(1, first['numMeas'] + 1)
                        if first[f'gnssId_{i:02d}'] == 0 and first[f'svId_{i:02d}'] == 31
                        and first[f'sigId_{i:02d}'] == 0)
    suffix = f'_{sample_index:02d}'
    return {
        'scope': 'EXPOSED_RECORDING_QUALIFICATION',
        'paper': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC11220923/',
        'dataset': 'https://data.mendeley.com/datasets/nxk9r22wd6/3',
        'input_sha256': {name: hashlib.sha256((inputs / name).read_bytes()).hexdigest()
                         for name in ('receiver_messages.tar.gz',
                                      'processed_observation12_first_epoch.json')},
        'hours': hours, 'table13_windows': windows,
        'processed_pvt_array_lengths': {name: len(values)
                                        for name, values in processed_pvt.items()},
        'first_epoch_g31_mapping': {
            'native_phase_cycles': first['cpMes' + suffix],
            'native_doppler_hz': first['doMes' + suffix],
            'processed_doMes_G1': excerpt['doMes_G1'][30],
            'processed_cpMes_G1': excerpt['cpMes_G1'][30]},
        'limitations': [
            'Host clock timezone, synchronization and error are not independently qualified.',
            'Table 13 activity labels are not receiver capture/success labels.',
            'Before/between/after logged attacks are not certified benign intervals.',
            'Paper coordinates have no stated independent survey uncertainty.',
            'No native observation is retimed, rounded or interpolated onto the grid.',
            'GPS sigId 3 is L2C; it is not relabeled as C2W.',
            'Network observations, geometry, authenticity, false alarms and benefit are not assessed.',
        ],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = run()
    with args.output.open('x', encoding='utf-8', newline='\n') as destination:
        json.dump(report, destination, indent=2, allow_nan=False)
        destination.write('\n')
