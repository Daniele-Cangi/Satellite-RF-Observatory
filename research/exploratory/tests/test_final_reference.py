import copy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from research.exploratory import final_reference as study
from research.exploratory import final_reference_checked as checked
from research.exploratory import final_reference_products as products
from research.exploratory import final_reference_clock as clock
from research.exploratory import solid_earth_study as comparison


def clock_args():
    plan = json.loads((products.BASE/'day_reference_plan.json').read_bytes())
    return plan['references'],plan['target_excluded'],plan['date_gpst'],35880,39720


def test_native_clock_excludes_poisoned_target_and_receiver_before_epoch_parse():
    text = (products.INPUTS/'clock.txt').read_text()
    poison = 'AS G12       INVALID EPOCH AND CLOCK\nAR GOLD00USA INVALID EPOCH AND CLOCK\n'
    assert clock.extract_clock(text+poison,*clock_args()) == text
    with pytest.raises(ValueError,match='unadmitted'):
        clock.parse_clock(text+poison,*clock_args())
    result = clock.parse_clock(text,*clock_args())
    assert 'G12' not in result and len(result) == 22
    assert all(len(samples)==129 for samples in result.values())


@pytest.mark.parametrize('old,new', [('IGS20_2425','IGS14_0000'),('CODE.BIA','OTHER.BIA'),('C1W/C2W','C1C/C2W')])
def test_native_clock_rejects_incompatible_conventions(old,new):
    text = (products.INPUTS/'clock.txt').read_text().replace(old,new)
    with pytest.raises(ValueError):
        clock.parse_clock(text,*clock_args())


def test_native_clock_rejects_gap_duplicate_and_nonfinite():
    text = (products.INPUTS/'clock.txt').read_text()
    row = next(s for s in text.splitlines() if s.startswith('AS '))
    for changed in (text.replace(row+'\n','',1),text+row+'\n',text.replace(row,row[:row.index(row.split()[9])]+'NaN 0.0')):
        with pytest.raises(ValueError):
            clock.parse_clock(changed,*clock_args())


def test_paired_extract_and_self_consistent_receipt_change_is_rejected(monkeypatch):
    original = Path.read_bytes
    new = original(products.INPUTS/'bias.txt')+b'\n'
    receipt = json.loads(original(products.INPUTS/'receipt.json'))
    receipt['files']['bias.txt'] = hashlib.sha256(new).hexdigest()
    def replaced(path):
        if path == products.INPUTS/'bias.txt':
            return new
        if path == products.INPUTS/'receipt.json':
            return json.dumps(receipt).encode()
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',replaced)
    with pytest.raises(ValueError):
        products.inputs()


def test_failed_fixed_paths_are_not_reselected_or_scored(monkeypatch):
    prior = json.loads((products.BASE/'results/day_reference_v1.json').read_bytes())
    calls = []
    def failed(obs,base,ctx,fixed,model):
        name = prior['plan']['stations'][len(calls)]
        assert fixed == {e['time_s']:e['references'] for e in prior['calibrations'][name]['epochs']}
        calls.append(name)
        return {'status':'CALIBRATION_NOT_QUALIFIED','epochs':[],'failures':['fixed path unavailable']}
    monkeypatch.setattr(study.frame,'calibrate_fixed',failed)
    report = checked.run()
    assert len(calls)==7 and report['status_counts']=={'CALIBRATION_NOT_QUALIFIED':7}
    assert report['predictions']==[] and report['comparison'] is None
    assert report['rapid_training_to_final_test'] is None
    assert report['omitted_paths']==prior['omitted_paths']


def test_comparison_rejects_missing_path_instead_of_scoring_subset():
    prior = json.loads((products.BASE/'results/day_reference_v1.json').read_bytes())
    changed = copy.deepcopy(prior)
    changed['rows'].pop()
    with pytest.raises(ValueError,match='no matched-subset'):
        study.compare(prior,changed)


def test_checked_runner_rejects_change_before_execution(monkeypatch):
    original = Path.read_bytes
    def changed(path):
        return original(path)+(b'\n' if path == Path(study.__file__) else b'')
    monkeypatch.setattr(Path,'read_bytes',changed)
    monkeypatch.setattr(study,'run',lambda *a:pytest.fail('modified runner executed'))
    with pytest.raises(ValueError):
        checked.run()


def test_acquisition_failures_and_preexecution_freezes_remain():
    root = products.BASE.parents[1]
    for commit in ('5b20664','99c4f28','2441fd0','5799b2e'):
        subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=root,check=True)
    # Independent Git anchor also covers the actual documented CLI wrapper.
    # A wrapper cannot meaningfully authenticate itself with its own mutable
    # embedded hash; changing/bypassing its checks must instead fail this test.
    wrapper = subprocess.check_output(['git','show','5799b2e:research/exploratory/final_reference_checked.py'],cwd=root)
    assert wrapper == Path(checked.__file__).read_bytes()
    first = json.loads((products.BASE/'inputs/final_reference/receipt.json').read_bytes())
    second = json.loads((products.BASE/'inputs/final_reference_v2/receipt.json').read_bytes())
    assert first['failures'][0]['product']=='clock'
    assert second['failures'][0]['product']=='bias'
    *_,receipt,texts = products.inputs()
    for name,digest in receipt['files'].items():
        raw = subprocess.check_output(['git','show','5799b2e:research/exploratory/inputs/final_reference_v3/'+name],cwd=root)
        assert hashlib.sha256(raw).hexdigest()==digest
    for name,digest in checked.SOURCES.items():
        raw = subprocess.check_output(['git','show','5799b2e:research/exploratory/'+name],cwd=root)
        assert hashlib.sha256(raw).hexdigest()==digest
    assert 'G12' not in clock.parse_clock(texts['clock'],*clock_args())


def test_complete_fixed_rf_replay_without_target_states(monkeypatch):
    raw = (products.BASE/'results/final_reference_v1.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='51faab82e28ac2a82d1bf4814bfb9f15cb1c6712fb51e3bf555d67ea29f7aaf3'
    expected = json.loads(raw)
    antenna = study.frame.AttitudeReference.antenna_state
    def guarded(self,sv,code,t):
        assert sv != 'G12'
        return antenna(self,sv,code,t)
    monkeypatch.setattr(study.frame.AttitudeReference,'antenna_state',guarded)
    comparison.compare_replay(checked.run(),expected)
    assert expected['status_counts']=={'CALIBRATION_QUALIFIED':7}
    assert expected['evaluated_path_count']==8074 and len(expected['omitted_paths'])==935
    for candidate in expected['predictions']:
        assert candidate['training_count']==4132 and candidate['test_count']==3942
    assert expected['predictions'][-1]['all_test_error_rms_m'] is None
    assert expected['predictions'][-1]['status_counts']['UNSEEN_TRAINING_SUPPORT']==1141
    assert not expected['target_orbit_accessed'] and not expected['physical_covariance_qualified']
    assert expected['comparison']['identical_training_test_paths']
    assert expected['rapid_training_to_final_test']['predicted_count']==3942
