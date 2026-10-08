"""Native signal identity, invalid codes and collection-order-independent NAV joins."""

from copy import deepcopy

import pytest

from pnt.ublox import pair_navigation, rawx_gps_l1


def raw(rows=None):
    rows = rows or [(0, 0, 1, 21e6, 1), (0, 3, 1, 22e6, 1), (2, 0, 1, 23e6, 1)]
    message = {'week': 2293, 'rcvTow': 360017.007, 'numMeas': len(rows)}
    for i, values in enumerate(rows, 1):
        for key, value in zip(('gnssId', 'sigId', 'svId', 'prMes', 'prValid'), values):
            message[f'{key}_{i:02d}'] = value
    return message


def test_signal_identity_and_original_receiver_time_are_preserved():
    message = raw()
    original = deepcopy(message)
    result = rawx_gps_l1(message)
    assert result['codes'] == {'G01': 21e6}
    assert result['receiver_local_gpst'].isoformat() == '2023-12-21T04:00:17.007000+00:00'
    assert result['rcvTow'] == message['rcvTow']
    assert message == original


def test_invalid_flags_values_and_duplicate_sv_are_all_visible():
    result = rawx_gps_l1(raw([(0, 0, 1, 21e6, 1), (0, 0, 1, 21e6, 1),
                               (0, 0, 2, float('nan'), 1), (0, 0, 3, 21e6, 0),
                               (0, 0, 4, 21e6, True), (0, 0, 33, 21e6, 1)]))
    assert not result['codes']
    assert result['status_counts'] == {'DUPLICATE_GPS_L1_SV': 2, 'INVALID_CODE_VALUE': 1,
                                      'CODE_NOT_VALID': 2, 'INVALID_GPS_SV': 1}
    assert len(result['dispositions']) == 6


@pytest.mark.parametrize('key,value', [('week', -1), ('rcvTow', float('nan')),
                                     ('rcvTow', 604800), ('numMeas', True)])
def test_malformed_native_epoch_is_not_replaced_by_collection_time(key, value):
    message = raw() | {key: value}
    with pytest.raises(ValueError, match='invalid native RAWX'):
        rawx_gps_l1(message)


def test_navigation_pairs_follow_declared_epochs_even_with_shifted_labels():
    pvt = [('host0', {'iTOW': 1000}), ('host1', {'iTOW': 2000})]
    clock = [('host0', {'iTOW': 0}), ('host1', {'iTOW': 1000}), ('host2', {'iTOW': 2000})]
    pairs = pair_navigation(pvt, clock)
    assert pairs[0]['status'] == 'MISSING_PVT'
    assert pairs[1] == {'iTOW': 1000, 'status': 'PAIRED',
                        'pvt_sources': ['host0'], 'clock_sources': ['host1']}
    assert pair_navigation(list(reversed(pvt)), list(reversed(clock))) == pairs


def test_duplicate_epochs_and_missing_messages_are_not_collapsed():
    result = pair_navigation([('p1', {'iTOW': 1000}), ('p2', {'iTOW': 1000}),
                              ('p3', {'iTOW': 2000})], [('c1', {'iTOW': 1000})])
    assert [p['status'] for p in result] == ['AMBIGUOUS_NAV_EPOCH', 'MISSING_CLOCK']
    assert result[0]['pvt_sources'] == ['p1', 'p2']
    with pytest.raises(ValueError, match='duplicate source'):
        pair_navigation([('same', {'iTOW': 1000}), ('same', {'iTOW': 2000})], [])


@pytest.mark.parametrize('tow', [-1, 604800000, 1000.0, True])
def test_navigation_timestamp_validation(tow):
    with pytest.raises(ValueError, match='invalid native NAV'):
        pair_navigation([('p', {'iTOW': tow})], [])
