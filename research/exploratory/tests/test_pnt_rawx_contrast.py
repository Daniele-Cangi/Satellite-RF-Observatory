import pytest

from research.exploratory.pnt_rawx_contrast import analyze


def row(time_s, local_change=0, remote_change=0, station_changes=None):
    station_changes = station_changes or {name: remote_change for name in ('TRO1', 'KIRU')}
    return {'time_s': time_s, 'satellite': 'G03',
            'local_l1_m': 1000 + local_change, 'local_l2_m': 995,
            'references': {name: {'c1c_m': 1000 + station_changes[name], 'c2w_m': 995}
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


def test_opposite_reference_changes_cannot_hide_behind_stable_median():
    windows = [{'test_id': 'event', 'start_gpst_s': 90, 'stop_gpst_s': 120}]
    rows = [row(t) for t in (0, 30, 60)] + [
        row(90, station_changes={'TRO1': 40, 'KIRU': -40})]
    event = analyze(rows, windows)['groups']['event']
    assert event['modes']['network']['median_absolute_m'] == 0
    assert event['reference_station_changes']['TRO1']['median_absolute_m'] == 40
    assert event['reference_station_changes']['KIRU']['median_absolute_m'] == 40
    assert event['reference_station_disagreement']['median_absolute_m'] == 80


def test_pre_event_baseline_does_not_use_post_event_rows():
    windows = [{'test_id': 'event', 'start_gpst_s': 90, 'stop_gpst_s': 120}]
    rows = [row(t) for t in (0, 30, 60)] + [row(90, 5), row(120, 100)]
    result = analyze(rows, windows, baseline_mode='pre-event')['groups']
    assert result['pre_event']['paired_count'] == 3
    assert result['event']['modes']['local']['median_absolute_m'] == 5
    assert result['post_event']['modes']['local']['median_absolute_m'] == 100
    assert result['outside_official_windows']['paired_count'] == 0
