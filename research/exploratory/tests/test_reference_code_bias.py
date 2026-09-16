from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from research.exploratory import reference_code_bias as study

ROOT = Path(__file__).resolve().parents[3]
ARCHIVES = {'g14': 'experiments/positioning_g14_doy246_network',
            'g12': 'research/exploratory/inputs/g12_doy248'}


def fixture():
    folder = ROOT/'research/exploratory/inputs/reference_biases/g14'
    text = (folder/'reference_bias.bia').read_text(encoding='ascii')
    refs = json.loads((folder/'receipt.json').read_bytes())['references']
    return text, refs


def test_real_sign_scale_clock_datum_and_common_osb_shift():
    text, refs = fixture()
    records = study.parse_bias(text, refs, 'G14', 'IGS20_2425')
    when = study.parse_epoch('2026:246:14400')
    result = study.code_translation(records, 'G01', when, 'G080')
    assert result['dsb_c1w_minus_c1c_ns'] == pytest.approx(.9744, abs=1e-12)
    assert result['if_code_change_m'] == pytest.approx(study.ALPHA*study.C*.9744e-9, abs=1e-12)
    assert abs(result['clock_reference_if_closure_m']) < .0001
    shifted = [dict(r, value_ns=r['value_ns']+37.) for r in records]
    assert study.code_translation(shifted, 'G01', when, 'G080')['if_code_change_m'] == pytest.approx(result['if_code_change_m'], abs=1e-12)


def test_target_and_receiver_bias_filtered_before_numeric_conversion():
    text, refs = fixture()
    line = next(s for s in text.splitlines() if s.startswith(' OSB'))
    target = line[:11]+'G14'+line[14:70]+'NOT NUMERIC'.ljust(21)+line[91:]
    receiver = line[:15]+'RECEIVER1'+line[24:70]+'NOT NUMERIC'.ljust(21)+line[91:]
    tainted = text.replace('-BIAS/SOLUTION', target+'\n'+receiver+'\n-BIAS/SOLUTION')
    assert study.extract_bias(tainted, refs, 'G14') == text
    with pytest.raises(ValueError, match='unselected'):
        study.parse_bias(tainted, refs, 'G14', 'IGS20_2425')
    with pytest.raises(ValueError, match='target'):
        study.extract_bias(text, refs+['G14'], 'G14')


@pytest.mark.parametrize('old,new', [('TIME_SYSTEM                             G', 'TIME_SYSTEM                             U'),
                                   ('APC_MODEL                               IGS20_2425', 'APC_MODEL                               IGS20_2434'),
                                   ('G  C1W  C2W', 'G  C1C  C2W')])
def test_incompatible_conventions_rejected(old, new):
    text, refs = fixture()
    assert old in text
    with pytest.raises(ValueError):
        study.parse_bias(text.replace(old, new), refs, 'G14', 'IGS20_2425')


def test_validity_end_exclusive_missing_overlap_and_wrong_svn():
    text, refs = fixture()
    records = study.parse_bias(text, refs, 'G14', 'IGS20_2425')
    end = study.parse_epoch('2026:247:00000')
    study.code_translation(records, 'G01', end-timedelta(microseconds=1), 'G080')
    for rows, when, svn in [(records, end, 'G080'), (records[1:], end-timedelta(hours=1), 'G080'),
                            (records+records[:1], end-timedelta(hours=1), 'G080'),
                            (records, end-timedelta(hours=1), 'G063')]:
        with pytest.raises(ValueError, match='missing, overlapping or wrong-SVN'):
            study.code_translation(rows, 'G01', when, svn)


def test_translation_preserves_observations_and_rejects_target_and_gaps():
    observations = [{'time_s': 12, 'if_code_m': {'G01': 23000000.}}]
    original = deepcopy(observations)
    corrections = {(12, 'G01'): {'if_code_change_m': .75}}
    assert study.translate_observations(observations, corrections, 'G14')[0]['if_code_m']['G01'] == 23000000.75
    assert observations == original
    with pytest.raises(ValueError, match='target'):
        study.translate_observations(observations, corrections, 'G01')
    with pytest.raises(KeyError):
        study.translate_observations(observations, {}, 'G14')


def test_failures_retained_and_target_codes_unchanged(monkeypatch):
    admitted, context, nav, hashes = study.load_inputs(ROOT/ARCHIVES['g14'])
    original = deepcopy(admitted)
    monkeypatch.setattr(study, 'load_inputs', lambda _: (admitted, context, nav, hashes))
    calls = 0
    def calibrate(*args):
        nonlocal calls
        calls += 1
        if calls > len(admitted['fit_stations']):
            raise RuntimeError('injected calibration failure')
        return {'status': 'CALIBRATION_QUALIFIED', 'failures': [], 'epochs': []}
    monkeypatch.setattr(study, 'calibrate_station', calibrate)
    monkeypatch.setattr(study, 'fit_variant', lambda *args: {'status': 'ESTIMATED'})
    report = study.run(ROOT/ARCHIVES['g14'], ROOT/'research/exploratory/inputs/reference_biases/g14',
                       ROOT/'research/exploratory/inputs/reference_antennas/g14')
    assert report['status_counts'] == {'ESTIMATED': 1, 'ENGINEERING_FAILURE': 1}
    assert len(report['station_epoch_changes']) == 77
    assert all(r['status'] == 'MISSING_CALIBRATION_EPOCH' for r in report['station_epoch_changes'])
    assert admitted == original


@pytest.mark.parametrize('tag', ['g14', 'g12'])
def test_saved_trial_replay_inputs_sources_and_full_accounting(tag):
    saved = json.loads((ROOT/f'research/exploratory/results/{tag}_reference_code_bias_v1.json').read_bytes())
    result = study.run(ROOT/ARCHIVES[tag], ROOT/f'research/exploratory/inputs/reference_biases/{tag}',
                       ROOT/f'research/exploratory/inputs/reference_antennas/{tag}')
    def compare(old, new):
        if isinstance(new, dict):
            assert old.keys() == new.keys()
            for key in new:
                compare(old[key], new[key])
        elif isinstance(new, list):
            assert len(old) == len(new)
            for a, b in zip(old, new):
                compare(a, b)
        elif isinstance(new, float):
            # Nonlinear ground/target least-squares replays can differ across
            # BLAS/libm; 1 mm absolute for fitted metres, not product precision.
            assert old == pytest.approx(new, rel=1e-10, abs=.001)
        else:
            assert old == new
    compare(saved, result)
    for path, digest in result['sources_sha256'].items():
        assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == digest
    assert result['case_count'] == 2 == sum(result['status_counts'].values())
    assert len(result['translations']) == 11*len(result['references'])
    assert len(result['station_epoch_changes']) == 77
    assert not any(result[key] for key in ('target_bias_parsed', 'target_orbit_accessed', 'new_confirmation',
                                          'qualified_error_budget', 'applied_to_production_estimator'))
    for entry in result['translations']:
        assert entry['reference'] != result['target']
        assert entry['if_code_change_m'] == pytest.approx(study.ALPHA*study.C*1e-9*
            (entry['osb_ns']['C1W']-entry['osb_ns']['C1C']), abs=1e-12)
    if result['cases'][1].get('comparison_status') == 'COMPARABLE':
        assert result['cases'][1]['displacement_from_baseline_m'] == pytest.approx(
            np.linalg.norm(result['cases'][1]['delta_xyz_m']), abs=1e-12)
