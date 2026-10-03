"""End-to-end Android/RINEX diagnostics with explicit synthetic physical cases."""

from decimal import Decimal, localcontext
import json
import subprocess
import sys

import pytest

from pnt.android_network import analyze_android, grid_codes
from pnt.android_raw import inspect_android_raw, WEEK_NS
from pnt.model import GPS_EPOCH, day_context
from pnt.tests.test_fixed_site import DAY, TIME, POSITIONS, observations, constellation, source_files
from research.exploratory.pnt_observation_pairing import reference_codes


FIELDS = ('Raw', 'TimeNanos', 'FullBiasNanos', 'BiasNanos', 'TimeOffsetNanos',
          'HardwareClockDiscontinuityCount', 'Svid', 'ConstellationType',
          'CarrierFrequencyHz', 'CodeType', 'State', 'ReceivedSvTimeNanos')


def write_android(path, codes, *, offset_ns=0):
    epoch_ns = (day_context(DAY).day - GPS_EPOCH).days * 86400_000_000_000 + TIME * 1_000_000_000
    rows = []
    with localcontext() as context:
        context.prec = 40
        for satellite, pair in codes.items():
            tx = (epoch_ns + offset_ns) % WEEK_NS - Decimal(str(pair[0])) / Decimal('0.299792458')
            rows.append(['Raw', str(1_000_000_000_000 + offset_ns), str(1_000_000_000_000 - epoch_ns),
                         '0', '0', '0', str(int(satellite[1:])), '1', '1575420000', 'C',
                         '16385', str(round(tx) % WEEK_NS)])
    path.write_text('# ' + ','.join(FIELDS) + '\n' +
                    '\n'.join(','.join(row) for row in rows) + '\n', encoding='ascii')


def sources(tmp_path, *, anomaly=0., clock=0., offset_ns=0):
    paths, nav = source_files(tmp_path)
    # Only C1C is present externally: missing C2W must not exclude valid L1.
    for name in ('A', 'B'):
        text = paths[name].read_text().replace('G    2 C1C C2W', 'G    1 C1C    ')
        text = '\n'.join(line[:19] if line.startswith('G') and len(line) < 60 else line
                         for line in text.splitlines()) + '\n'
        paths[name].write_text(text, encoding='ascii')
    data = observations(constellation(), local_shift=clock)['local']
    data['G02'] = tuple(value + anomaly for value in data['G02'])
    raw = tmp_path / 'local.txt'
    write_android(raw, data, offset_ns=offset_ns)
    return raw, {name: paths[name] for name in ('A', 'B')}, nav


def analyze(paths, *, stop=TIME + 90):
    return analyze_android(*paths, DAY.isoformat(), start_s=TIME, stop_s=stop,
                           local_ecef=POSITIONS['local'], position_source='synthetic known fixed point')


def test_android_single_band_pipeline_preserves_empty_epochs_and_source_binding(tmp_path):
    paths = sources(tmp_path)
    report = analyze(paths)
    assert report == analyze(paths)
    assert report['model']['observables'] == 'GPS C1C ONLY; SINGLE_FREQUENCY'
    assert report['coverage']['matched_status_counts'] == {'EVALUATED': 1, 'INSUFFICIENT_EVIDENCE': 2}
    assert [epoch['gpst_s'] for epoch in report['epochs']] == [TIME, TIME + 30, TIME + 60]
    epoch = report['epochs'][0]
    assert len(epoch['local_source_lines']) == 8
    assert max(map(abs, epoch['matched']['mean_double_difference_residuals_m'].values())) < .3
    assert set(report['assessments'].values()) == {'NOT_ASSESSED'}
    json.dumps(report, allow_nan=False)


def test_common_clock_mode_remains_visible_and_cancels_in_dd(tmp_path):
    first = analyze(sources(tmp_path))['epochs'][0]['matched']
    second = analyze(sources(tmp_path, clock=200.))['epochs'][0]['matched']
    assert second['local_minus_network_clock_m'] - first['local_minus_network_clock_m'] == pytest.approx(200., abs=.3)
    for satellite, value in first['mean_double_difference_residuals_m'].items():
        assert second['mean_double_difference_residuals_m'][satellite] == pytest.approx(value, abs=.6)
    assert second['receiver_fits']['A'] == first['receiver_fits']['A']


def test_satellite_specific_code_change_and_remote_independence(tmp_path):
    first = analyze(sources(tmp_path))['epochs'][0]['matched']
    changed = analyze(sources(tmp_path, anomaly=20.))['epochs'][0]['matched']
    assert changed['mean_double_difference_residuals_m']['G02'] - first['mean_double_difference_residuals_m']['G02'] == pytest.approx(20., abs=.6)
    assert changed['receiver_fits']['A'] == first['receiver_fits']['A']
    assert changed['receiver_fits']['B'] == first['receiver_fits']['B']


def test_network_gap_does_not_erase_local_diagnostic(tmp_path):
    paths = sources(tmp_path)
    path = paths[1]['B']
    content = path.read_text().split('>')[0]  # Valid zero-epoch external file.
    path.write_text(content, encoding='ascii')
    report = analyze(paths)
    epoch = report['epochs'][0]
    assert epoch['standalone_receiver_fits']['local']['status'] == 'EVALUATED'
    assert epoch['matched']['status'] == 'INSUFFICIENT_EVIDENCE'


def test_same_signal_reader_does_not_require_or_substitute_second_band(tmp_path):
    paths = sources(tmp_path)
    content = paths[1]['A'].read_text()
    rows, counts = reference_codes(content, DAY, signals=('C1C',))
    assert len(rows) == 8 and all(len(pair) == 1 for pair in rows.values())
    with pytest.raises(ValueError, match='C1C/C2W missing'):
        reference_codes(content, DAY)
    with pytest.raises(ValueError, match='C5Q missing'):
        reference_codes(content, DAY, signals=('C5Q',))
    with pytest.raises(ValueError, match='C1C missing'):
        reference_codes(content.replace('C1C', 'C1W'), DAY, signals=('C1C',))


def test_unrequested_second_band_cannot_exclude_valid_first_band(tmp_path):
    paths, _ = source_files(tmp_path)
    content = paths['A'].read_text()
    poisoned = '\n'.join(line[:19] + f'{float("nan"):14.3f}  ' if line.startswith('G') and len(line) < 60
                         else line for line in content.splitlines()) + '\n'
    rows, _ = reference_codes(poisoned, DAY, signals=('C1C',))
    assert len(rows) == 8
    dual, counts = reference_codes(poisoned, DAY)
    assert not dual and counts['invalid_dual_code'] == 8


def test_offset_within_one_ms_is_reported_without_modifying_codes(tmp_path):
    paths = sources(tmp_path, offset_ns=500000)
    raw = inspect_android_raw(paths[0])
    codes, lines, selection = grid_codes(raw, DAY, TIME, TIME + 30)
    assert selection['status_counts'] == {'SELECTED': 8}
    assert all(item['time_offset_s'] == .0005 for item in selection['row_dispositions'])
    assert all(codes[TIME, row['satellite']][0] == row['pseudorange_m'] for row in raw['records'])


def test_off_grid_day_and_window_exclusions_remain_visible(tmp_path):
    path, _, _ = sources(tmp_path, offset_ns=2_000_000)
    raw = inspect_android_raw(path)
    assert grid_codes(raw, DAY, TIME, TIME + 30)[2]['status_counts'] == {'OFF_GRID': 8}
    path, _, _ = sources(tmp_path)
    raw = inspect_android_raw(path)
    assert grid_codes(raw, DAY, TIME + 30, TIME + 60)[2]['status_counts'] == {'OUTSIDE_WINDOW': 8}
    for row in raw['records']:
        row['receiver_gpst_ns'] = str(Decimal(row['receiver_gpst_ns']) + 86400_000_000_000)
    assert grid_codes(raw, DAY, TIME, TIME + 30)[2]['status_counts'] == {'OUTSIDE_GPST_DAY': 8}


def test_duplicates_and_mixed_clock_solutions_cannot_form_an_epoch(tmp_path):
    path, _, _ = sources(tmp_path)
    raw = inspect_android_raw(path)
    raw['records'].append(dict(raw['records'][0], source_line=100))
    codes, _, selection = grid_codes(raw, DAY, TIME, TIME + 30)
    assert len(codes) == 7
    assert selection['status_counts'] == {'AMBIGUOUS_DUPLICATE': 2, 'SELECTED': 7}
    raw['records'].pop()
    raw['records'][0]['hardware_clock_discontinuity_count'] = 1
    assert grid_codes(raw, DAY, TIME, TIME + 30)[2]['status_counts'] == {'MIXED_HARDWARE_EPOCH': 8}


def test_coordinate_provenance_and_duplicate_remote_receivers_required(tmp_path):
    paths = sources(tmp_path)
    with pytest.raises(ValueError, match='requires its source'):
        analyze_android(*paths, DAY.isoformat(), local_ecef=POSITIONS['local'])
    with pytest.raises(ValueError, match='terrestrial'):
        analyze_android(*paths, DAY.isoformat(), local_ecef=[0, 0, 0], position_source='invalid')
    paths[1]['B'].write_bytes(paths[1]['A'].read_bytes())
    with pytest.raises(ValueError, match='distinct receivers'):
        analyze(paths)


def test_cli_end_to_end_and_no_overwrite(tmp_path):
    raw, references, nav = sources(tmp_path)
    output = tmp_path / 'incident.json'
    command = [sys.executable, '-m', 'pnt', 'android-analyze', DAY.isoformat(), str(raw), str(nav),
               '--reference', 'A=' + str(references['A']), '--reference', 'B=' + str(references['B']),
               '--start', str(TIME), '--stop', str(TIME + 90), '--local-ecef', *map(str, POSITIONS['local']),
               '--position-source', 'synthetic fixed point', '--output', str(output)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = output.read_bytes()
    assert json.loads(report)['status'] == 'DIAGNOSTICS_AVAILABLE'
    assert subprocess.run(command, capture_output=True).returncode == 2
    assert output.read_bytes() == report
