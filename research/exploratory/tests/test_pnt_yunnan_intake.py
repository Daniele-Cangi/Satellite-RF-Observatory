from copy import deepcopy
import json
import tarfile

import pytest

from research.exploratory import pnt_yunnan_intake as intake


@pytest.fixture(scope='module')
def report():
    return intake.run()


def test_real_recording_retains_gaps_clock_excursions_and_unusable_codes(report):
    first, later = report['hours']['12'], report['hours']['18']
    assert (first['rawx_messages'], later['rawx_messages']) == (3600, 3524)
    assert later['missing_host_seconds'] == 76
    assert first['gps_l1_rows'] == 20408
    assert first['gps_l1_prvalid_rows'] == 18634
    assert first['gps_l1_flagged_valid_but_invalid_value_rows'] == 1774
    assert first['clock_reset_messages'] == 17
    assert first['receiver_date_differs_from_host_messages'] == 248
    assert first['epochs_with_fewer_than_four_valid_gps_l1'] == 520
    assert later['filename_and_start_time_disagreements'] == 17
    assert later['duplicate_start_time_values']['RXM-RAWX'] == 7
    assert later['pvt_clock_different_itow_on_same_host_label'] == 1581
    assert first['within_existing_1ms_grid_messages'] == 0
    assert later['within_existing_1ms_grid_messages'] == 0
    assert sum(w['rawx_messages'] for w in report['table13_windows'].values()) == 7124


def test_processed_arrays_cannot_be_used_as_synchronized_raw_observations(report):
    lengths = report['processed_pvt_array_lengths']
    assert (lengths['recordTime'], lengths['clkB'], lengths['gDOP']) == (3600, 3593, 3597)
    mapping = report['first_epoch_g31_mapping']
    assert mapping['processed_doMes_G1'] == mapping['native_phase_cycles']
    assert mapping['processed_cpMes_G1'] == mapping['native_doppler_hz']
    assert mapping['native_doppler_hz'] == -911.17236328125


def test_native_validity_and_time_are_not_repaired_to_force_grid_support():
    with tarfile.open(intake.INPUTS / 'receiver_messages.tar.gz', 'r:gz') as source:
        message = json.loads(source.extractfile(
            '12/RXM-RAWX/2023-12-21 12-00-00.json').read())
    original = deepcopy(message)
    row = intake.describe_rawx(message)
    assert row['receiver_gpst'] == '2023-12-21T04:00:17.007000'
    assert not row['within_existing_1ms_grid']
    assert message == original
    gps = [i for i in range(1, message['numMeas'] + 1)
           if message[f'gnssId_{i:02}'] == 0 and message[f'sigId_{i:02}'] == 0]
    message[f'prValid_{gps[0]:02}'] = 0
    message[f'prMes_{gps[1]:02}'] = float('nan')
    poisoned = intake.describe_rawx(message)
    assert poisoned['gps_l1_prvalid_rows'] == row['gps_l1_prvalid_rows'] - 2
    assert poisoned['gps_l1_flagged_valid_but_invalid_value_rows'] == 1
    assert poisoned['gps_l1_rows'] == row['gps_l1_rows']
