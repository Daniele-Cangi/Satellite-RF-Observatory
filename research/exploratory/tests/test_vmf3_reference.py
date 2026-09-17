import hashlib
import json
import subprocess

import numpy as np
import pytest

from research.exploratory import vmf3_reference_study as study

REPORT_HASHES = {'g14': 'aa9bf6ee7f6fbc8bf76576660118cde468f95e7e41ae0007c7ef13656b533dbd',
                 'g12': '6f5d01e84e9ccea9038959c862b1e2be043bd1e4835a9fb27cabe28a859f47af'}


def test_receiver_time_and_separate_mapping_components():
    class Provider:
        def antenna_state(self, sv, code, t):
            return t-.07, 0, np.array([26378137., 0, 0]), -.07
    class Weather:
        def evaluate(self, *args):
            self.request = args
            return np.array([1.2, 1.3, 2.1, .2])
    weather = Weather()
    clock = study.C * .001
    delays, details = study.components(Provider(), weather, 61286, 'G01', 2e7, 14100,
                                       np.array([6378137., 0, 0]), clock)
    assert weather.request[0] == 61286+(14100-.001-18)/86400
    assert delays['vmf3_full'] == pytest.approx(2.1*1.2+.2*1.3)
    assert delays['vmf3_mapping_only'] == pytest.approx(2.3*1.2+.1*1.3)
    assert 89 < details['elevation_deg'] <= 90


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_full_replay_exact_cohort_and_target_exclusion(tag, monkeypatch):
    raw = (study.BASE/f'results/{tag}_vmf3_reference_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == REPORT_HASHES[tag]
    expected = json.loads(raw)
    original = study.frame.AttitudeReference.antenna_state
    calls = []
    def guarded(self, sv, code, t):
        assert sv != self.attitude.target
        calls.append(sv)
        return original(self, sv, code, t)
    monkeypatch.setattr(study.frame.AttitudeReference, 'antenna_state', guarded)
    actual = study.run(tag)
    study.solid.compare_replay(actual, expected)
    assert calls
    assert actual['status_counts'] == {'CALIBRATION_QUALIFIED': 4}
    assert [c['mode'] for c in actual['cases']] == list(study.MODES)
    prior = json.loads((study.BASE/f'results/{tag}_ocean_pole_v1.json').read_bytes())
    baseline = next(c for c in prior['cases'] if c['mode'] == 'ocean_ce_plus_pole_2018')
    cohort = {(name, e['time_s'], sv) for name, cal in baseline['calibrations'].items()
              for e in cal['epochs'] for sv in e['references']}
    for case in actual['cases']:
        assert len(case['paths']) == len(cohort) == case['evaluated_path_count']
        assert {(p['station'], p['time_gpst_s'], p['reference']) for p in case['paths']} == cohort
        assert case['evaluated_path_count']+len(actual['omitted_paths']) == actual['observed_path_count']
        assert all(len(c['epochs']) == 11 for c in case['calibrations'].values())
    assert not actual['target_fit_performed'] and not actual['qualified_error_budget']


def test_failed_stations_stay_visible(monkeypatch):
    def fail(*args, **kwargs):
        raise ValueError('injected failure')
    monkeypatch.setattr(study.frame, 'calibrate_fixed', fail)
    report = study.run('g14')
    assert report['status_counts'] == {'CALIBRATION_NOT_QUALIFIED': 4}
    for case in report['cases']:
        assert set(case['calibrations']) == set(report['fit_stations'])
        assert all(c['status'] == 'ENGINEERING_FAILURE' for c in case['calibrations'].values())
        assert case['pooled_reference_rms_m'] is None


def test_scientific_source_input_and_benchmark_ancestry():
    root = study.frame.ROOT
    for commit in ('f15497f', 'b3d5866'):
        subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=root, check=True)
    benchmark_raw = (study.BASE/'results/vmf3_benchmark_v1.json').read_bytes()
    assert hashlib.sha256(benchmark_raw).hexdigest() == study.BENCHMARK_SHA
    benchmark = json.loads(benchmark_raw)
    for name, digest in benchmark['source_sha256'].items():
        blob = subprocess.check_output(['git', 'show', 'f15497f:research/exploratory/'+name], cwd=root)
        assert hashlib.sha256(blob).hexdigest() == digest
        assert hashlib.sha256((study.BASE/name).read_bytes()).hexdigest() == digest
    for tag, report_hash in REPORT_HASHES.items():
        raw = (study.BASE/f'results/{tag}_vmf3_reference_v1.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest() == report_hash
        report = json.loads(raw)
        for name, digest in report['sources_sha256'].items():
            blob = subprocess.check_output(['git', 'show', 'b3d5866:'+name], cwd=root)
            assert hashlib.sha256(blob).hexdigest() == digest
            assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest
    _, receipt = study.meteo.read_inputs()
    files = {'inputs/vmf3_grid/receipt.json': study.meteo.RECEIPT_SHA} | receipt['prior_sha256']
    for name, source in receipt['sources'].items():
        key = 'inputs/vmf3_grid/'+source.get('packed_file', name)
        files[key] = source.get('packed_sha256', source['sha256'])
    for name, digest in files.items():
        blob = subprocess.check_output(['git', 'show', 'f15497f:research/exploratory/'+name], cwd=root)
        assert hashlib.sha256(blob).hexdigest() == digest
        assert hashlib.sha256((study.BASE/name).read_bytes()).hexdigest() == digest
