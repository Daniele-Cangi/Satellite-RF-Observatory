"""Replay exposed short-baseline evidence without changing the transfer method."""

from datetime import date
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from pnt.fixed_site import read_station
from pnt.transfer import reference_transfer


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / 'fixtures/wegener20240911'
RESULT = ROOT / 'research/exploratory/results/pnt_close_reference_transfer_2024255_v1.json.gz'
STATIONS = ('W181', 'W182', 'W183')
NAV = FIXTURE.parent / 'gfz20240911/brdc2550.24n.gz'


def evidence():
    return json.loads(gzip.decompress(RESULT.read_bytes()))


def observation_body(data):
    lines = data.splitlines(keepends=True)
    end = next(i + 1 for i, line in enumerate(lines)
               if line[60:80].strip() == b'END OF HEADER')
    return b''.join(lines[end:])


def test_original_sources_coordinate_boundary_and_failed_conversion_are_retained():
    report = evidence()
    receipt = json.loads((FIXTURE / 'provenance.json').read_bytes())
    assert hashlib.sha256((FIXTURE / 'provenance.json').read_bytes()).hexdigest() == report['input_provenance_sha256']
    assert hashlib.sha256(NAV.read_bytes()).hexdigest() == receipt['navigation']['sha256']
    for source in receipt['files']:
        data = (FIXTURE / source['file']).read_bytes()
        assert len(data) == source['bytes']
        assert hashlib.sha256(data).hexdigest() == source['sha256']
        assert hashlib.sha256(gzip.decompress(data)).hexdigest() == source['uncompressed_sha256']
    for station in STATIONS:
        qualified = receipt['qualification'][station]
        assert [s['file'][19:21] for s in qualified['raw_files']] == ['00', '08', '09', '10']
        assert all(s['crc_failures'] == 0 for s in qualified['raw_files'])
        _, position, _ = read_station(FIXTURE / (station + '_fixed.obs.gz'), date(2024, 9, 11))
        assert position == pytest.approx(qualified['receiver_setup_positions'][0]['ecef_m'], abs=0.000051, rel=0)
        assert qualified['receiver_setup_positions'][0]['hour_gpst'] == 0
        body = observation_body(gzip.decompress((FIXTURE / (station + '_fixed.obs.gz')).read_bytes()))
        for variant in receipt['conversion_variant_headers'][station].values():
            reconstructed = bytes.fromhex(variant['header_hex']) + body
            assert hashlib.sha256(reconstructed).hexdigest() == variant['plain_sha256']
    assert report['failed_coordinate_override_attempt']['status'] == 'ABORTED_CONFIGURATION_NOT_APPLIED'
    assert len(report['failed_coordinate_override_attempt']['completed_runs']) == 3
    assert len(report['preliminary_late_coordinate_variant']['runs']) == 6


def assert_replayed(actual, expected):
    if isinstance(expected, dict):
        assert actual.keys() == expected.keys()
        for key in expected:
            assert_replayed(actual[key], expected[key])
    elif isinstance(expected, list):
        assert len(actual) == len(expected)
        for a, b in zip(actual, expected):
            assert_replayed(a, b)
    elif isinstance(expected, float):
        assert actual == pytest.approx(expected, abs=2e-6, rel=1e-10)
    else:
        assert actual == expected


@pytest.mark.parametrize('window,bounds', [('A', (28800, 30600, 34200)), ('B', (34200, 36000, 39600))])
@pytest.mark.parametrize('station', STATIONS)
def test_real_short_baseline_transfer_replays_all_outcomes(station, window, bounds):
    expected = next(row['report'] for row in evidence()['primary']['runs']
                    if row['local'] == station and row['window'] == window)
    actual = reference_transfer(
        FIXTURE / (station + '_fixed.obs.gz'),
        {s: FIXTURE / (s + '_fixed.obs.gz') for s in STATIONS if s != station},
        NAV, '2024-09-11', start_s=bounds[0], train_stop_s=bounds[1], stop_s=bounds[2])
    assert_replayed(actual, expected)
    assert actual['fit']['eligible_training_epochs'] == 60
    assert actual['evaluation']['requested_epochs'] == 120
    assert actual['evaluation']['evaluated_epochs'] == (120 if window == 'A' else 119)
    assert actual['evaluation']['metrics']['unit_transfer']['fractional_mse_reduction_vs_local'] < 0
    assert actual['evaluation']['metrics']['fitted_transfer']['worsened_epochs_vs_local'] > 0
    if window == 'B':
        missing = actual['epochs'][-1]
        assert missing['gpst_s'] == 39570
        assert missing['status'] == 'INSUFFICIENT_EVIDENCE'
        assert 'transfer_metrics' not in missing
    assert actual['assessments']['recorded_RF_detection_gain'] == 'NOT_ASSESSED'
