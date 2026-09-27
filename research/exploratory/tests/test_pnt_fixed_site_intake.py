from datetime import date
import hashlib
from pathlib import Path

import pytest

from research.exploratory import pnt_fixed_site_intake as intake


DAY = date(2024, 9, 11)


def rinex(marker, seconds=(0, 30, 90), *, omit=(), clock='GPS'):
    def header(value, label):
        return f'{value:<60}{label:<20}'

    lines = [header('     3.05           OBSERVATION DATA    M (MIXED)', 'RINEX VERSION / TYPE'),
             header(marker, 'MARKER NAME'),
             header('1202379.31 252474.65 6237786.54', 'APPROX POSITION XYZ'),
             header('G    2 C1C C2W', 'SYS / # / OBS TYPES'),
             header(f'  2024     9    11     0     0    0.0000000     {clock}',
                    'TIME OF FIRST OBS'),
             header('', 'END OF HEADER')]
    for second in seconds:
        satellites = [sat for sat in ('G01', 'G02') if (second, sat) not in omit]
        lines.append(f'> 2024 09 11 08 {second // 60:02d} {second % 60:02d}.0000000  0  {len(satellites)}')
        lines.extend(sat + f'{21000000.:14.3f}  ' + f'{21000005.:14.3f}  '
                     for sat in satellites)
    return '\n'.join(lines) + '\n'


def files(tmp_path, *, local_marker='LOCAL', missing_reference=()):
    paths = [tmp_path / name for name in ('local.rnx', 'station_a.rnx', 'station_b.rnx')]
    for path, marker, omitted in zip(paths, (local_marker, 'A', 'B'),
                                     ((), (), missing_reference)):
        path.write_text(rinex(marker, omit=omitted), encoding='ascii')
    return paths


def test_real_pairing_primitives_report_support_and_gaps(tmp_path):
    local, a, b = files(tmp_path, missing_reference=((30, 'G02'),))
    report = intake.run(local, {'A': a, 'B': b}, DAY.isoformat())
    assert report['local_code_rows'] == 6
    assert report['paired_rows'] == 5
    assert report['paired_epochs'] == 3
    assert report['local_epochs_without_pair'] == 0
    assert report['paired_satellites_per_epoch'] == {1: 1, 2: 2}
    assert report['missing_simultaneous_satellite'] == {'B': 1}
    assert report['paired_coverage_runs'] == [
        {'first_gpst_s': 28800, 'last_gpst_s': 28830, 'epoch_count': 2},
        {'first_gpst_s': 28890, 'last_gpst_s': 28890, 'epoch_count': 1},
    ]
    assert report['local']['marker_name'] == 'LOCAL'
    assert report['local']['declared_approx_xyz_m'] == [1202379.31, 252474.65, 6237786.54]
    assert len(report['local']['sha256']) == 64


def test_same_receiver_or_file_cannot_count_as_independent_station(tmp_path):
    local, a, b = files(tmp_path, local_marker='A')
    with pytest.raises(ValueError, match='distinct receivers'):
        intake.run(local, {'A': a, 'B': b}, DAY.isoformat())
    local.write_text(rinex('LOCAL'), encoding='ascii')
    b.write_bytes(a.read_bytes())
    with pytest.raises(ValueError, match='distinct receivers'):
        intake.run(local, {'A': a, 'B': b}, DAY.isoformat())


def test_ambiguous_time_and_missing_marker_fail_closed(tmp_path):
    local, a, b = files(tmp_path)
    local.write_text(rinex('LOCAL', clock='UTC'), encoding='ascii')
    with pytest.raises(ValueError, match='time scale'):
        intake.run(local, {'A': a, 'B': b}, DAY.isoformat())
    local.write_text(rinex(''), encoding='ascii')
    with pytest.raises(ValueError, match='marker name'):
        intake.run(local, {'A': a, 'B': b}, DAY.isoformat())


def test_descriptive_marker_names_remain_complete_and_distinct(tmp_path):
    local, a, b = files(tmp_path)
    local.write_text(rinex('SITE A'), encoding='ascii')
    a.write_text(rinex('SITE B'), encoding='ascii')
    report = intake.run(local, {'A': a, 'B': b}, DAY.isoformat())
    assert report['local']['marker_name'] == 'SITE A'
    assert report['references']['A']['marker_name'] == 'SITE B'


def test_digest_is_of_the_same_bytes_that_were_decoded(tmp_path, monkeypatch):
    path = tmp_path / 'local.rnx'
    source_bytes = rinex('LOCAL').encode('ascii')
    calls = []

    def read_once(self):
        calls.append(self)
        return source_bytes if len(calls) == 1 else rinex('CHANGED').encode('ascii')

    monkeypatch.setattr(Path, 'read_bytes', read_once)
    _, info = intake.read_station(path, DAY)
    assert calls == [path]
    assert info['sha256'] == hashlib.sha256(source_bytes).hexdigest()
