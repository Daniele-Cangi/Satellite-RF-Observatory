import hashlib
import json
import subprocess

import pytest

from research.exploratory import atmosphere_zenith_v2 as study


def test_unused_negative_mapping_coefficient():
    assert study.parse_weather(b'GANP 61288.50 .00123945 -.00020830 2.1342 .0626 936.30 17.28 9.08\n', 61288)[('GANP', 61288.5)] == (2.1342, .0626)


def compare(a, b):
    if isinstance(a, dict):
        assert a.keys() == b.keys()
        for k in a:
            compare(a[k], b[k])
    elif isinstance(a, list):
        assert len(a) == len(b)
        for x, y in zip(a, b):
            compare(x, y)
    elif isinstance(a, float):
        assert a == pytest.approx(b, abs=1e-8, rel=1e-12)
    else:
        assert a == b


def test_report_replay_and_complete_denominator():
    expected = json.loads((study.BASE / 'results/atmosphere_zenith_v2.json').read_bytes())
    compare(study.run(), expected)
    assert len(expected['rows']) == expected['expected_rows'] == 72
    assert len({(r['event'], r['station'], r['hour_utc']) for r in expected['rows']}) == 72
    assert expected['status_counts'] == {'compared_at_provider_height': 72}
    assert len(expected['coordinate_alignment']) == 14
    assert not expected['physical_error_bound']
    assert not expected['applied_to_production_estimator']


def test_missing_station_retained(monkeypatch):
    monkeypatch.setattr(study, 'STATIONS', (*study.STATIONS, 'NONE'))
    report = study.run()
    assert report['status_counts']['missing_coordinates'] == 8


def test_execution_commit_binding_and_preserved_failure():
    root = study.BASE.parents[1]
    report = json.loads((study.BASE / 'results/atmosphere_zenith_v2.json').read_bytes())
    subprocess.run(['git', 'merge-base', '--is-ancestor', '35e5734', 'HEAD'], cwd=root, check=True)
    for name, digest in ({'atmosphere_zenith_v2.py': report['source_sha256']} | report['input_sha256']).items():
        path = (study.BASE / name).resolve().relative_to(root).as_posix()
        blob = subprocess.check_output(['git', 'show', '35e5734:' + path], cwd=root)
        assert hashlib.sha256(blob).hexdigest() == digest
        assert hashlib.sha256((study.BASE / name).read_bytes()).hexdigest() == digest
    failure = json.loads((study.BASE / 'results/atmosphere_zenith_v1_failure.json').read_bytes())
    assert failure['scientific_report_written'] is False
    assert hashlib.sha256((study.BASE / 'atmosphere_zenith.py').read_bytes()).hexdigest() == failure['source_sha256']
