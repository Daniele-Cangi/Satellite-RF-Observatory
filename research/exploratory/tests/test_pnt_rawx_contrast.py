import pytest

from research.exploratory.pnt_rawx_contrast import analyze


def row(time_s, local_change=0, remote_change=0):
    return {'time_s': time_s, 'satellite': 'G03',
            'local_l1_m': 1000 + local_change, 'local_l2_m': 995,
            'references': {name: {'c1c_m': 1000 + remote_change, 'c2w_m': 995}
                           for name in ('TRO1', 'KIRU')}}


def test_local_and_shared_changes_have_distinct_network_contrasts():
    windows = [{'test_id': 'local_event', 'start_gpst_s': 90, 'stop_gpst_s': 120},
               {'test_id': 'shared_event', 'start_gpst_s': 120, 'stop_gpst_s': 150}]
    rows = [row(t) for t in (0, 30, 60)] + [row(90, 20), row(120, 20, 20)]
    result = analyze(rows, windows)['groups']
    assert result['local_event']['modes']['local']['median_absolute_m'] == 20
    assert result['local_event']['modes']['network']['median_absolute_m'] == 0
    assert result['local_event']['modes']['combined']['median_absolute_m'] == 20
    assert result['shared_event']['modes']['local']['median_absolute_m'] == 20
    assert result['shared_event']['modes']['network']['median_absolute_m'] == 20
    assert result['shared_event']['modes']['combined']['median_absolute_m'] == 0
    assert result['outside_official_windows']['modes']['combined']['maximum_absolute_m'] == 0


def test_insufficient_outside_support_cannot_be_scored():
    with pytest.raises(ValueError, match='adequate outside-window support'):
        analyze([row(0), row(90, 20)],
                [{'test_id': 'event', 'start_gpst_s': 90, 'stop_gpst_s': 120}])
