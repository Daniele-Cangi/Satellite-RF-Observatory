import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import pytest

from research.exploratory import position_error_transfer_v2 as study
from research.exploratory import position_error_checked_v2 as checked
from research.exploratory.reference_residual_structure_v2 import design, center_blocks


@pytest.fixture(scope='module')
def context():
    return study.inputs(checked.PLAN_SHA)


@pytest.fixture(scope='module')
def operators(context):
    plan,_,train,test,blocks,_=context
    return {name:study.calibration_map(train,test,blocks,name)[0] for name in plan['models']}


def test_calibration_map_matches_direct_fit_and_reference_subtraction(context,operators):
    _,names,train,test,blocks,_=context
    m,n=len(blocks),len(test)
    raw=np.random.default_rng(731).normal(size=m+n+len(train))
    for method,mapping in operators.items():
        expected=[]
        coefficients={}
        for station in names:
            ix=[i for i,r in enumerate(train) if r['station']!=station]
            rows=[train[i] for i in ix]
            columns=sorted({r['reference'] for r in rows})
            x,_=design(rows,'shared_satellite',columns)
            y=center_blocks(raw[m+n+np.array(ix)],rows)
            beta=np.linalg.lstsq(x,y,rcond=1e-12)[0]
            coefficients[station]=dict(zip(columns,beta))
        for i,block in enumerate(blocks):
            ix=[j for j,r in enumerate(test) if (r['station'],r['time_s'])==block]
            value=raw[i]-raw[m+np.array(ix)].mean()
            if method=='shared_satellite':
                value+=np.mean([coefficients[block[0]][test[j]['reference']] for j in ix])
            expected.append(value)
        assert mapping@raw==pytest.approx(expected,abs=1e-11)


def test_heldout_training_columns_zero_and_epoch_means_blind(context,operators):
    _,_,train,test,blocks,_=context
    mapping=operators['shared_satellite'];start=len(blocks)+len(test)
    for i,(station,t) in enumerate(blocks):
        assert np.max(np.abs(mapping[i,start+np.array([j for j,r in enumerate(train) if r['station']==station])]))==0
    for indices in study.groups(train).values():
        assert np.max(np.abs(mapping[:,start+np.array(indices)].sum(axis=1)))<1e-13


def test_blind_modes_survive_correction_and_matched_errors_cancel(context,operators):
    plan,_,train,test,blocks,_=context
    cases={name:study.error_covariances(mapping,train,test,blocks,plan['origin_gpst_s']) for name,mapping in operators.items()}
    for name in ('reference_station_offset_1m','reference_station_ramp_1m_per_300s','reference_station_temporal_1m_tau60s'):
        assert cases['zero'][name]['reference_contrast_response_max']<1e-12
        np.testing.assert_allclose(cases['zero'][name]['code_covariance_m2'],cases['shared_satellite'][name]['code_covariance_m2'],atol=1e-12)
    for case in cases.values():
        assert np.max(np.abs(case['matched_station_offset_1m']['code_covariance_m2']))<1e-24
        assert np.linalg.eigvalsh(case['independent_raw_1m']['code_covariance_m2']).min()>=1-1e-12
    sat=cases['shared_satellite']['reference_satellite_offset_1m']['code_covariance_m2']
    assert np.max(np.abs(sat-sat[0,0]))<1e-12  # only common coefficient gauge remains


def test_geometry_gain_and_true_forward_epoch(context):
    plan,_,_,_,_,stations=context
    assert max(plan['evaluation_times_gpst_s'])==plan['origin_gpst_s']
    meta,gain,h,_=study.geometry(stations,26000000,4000,plan)
    assert meta['rank']==11
    np.testing.assert_allclose((gain@h)*study.SCALE[None,:]/study.SCALE[:,None],np.eye(11),atol=1e-7)
    below,_,_,_=study.geometry(stations,12000000,4000,plan)
    assert below['status']=='BELOW_SYNTHETIC_MASK'


def compare(actual,expected):
    # Finite-difference derivatives of 10^7-m ranges; no bit-identical LAPACK
    # promise across OS. Near-null sensitivities use an absolute 20-micrometre
    # tolerance. These tolerances are numerical, not physical uncertainty.
    if isinstance(expected,dict):
        assert actual.keys()==expected.keys()
        for key in expected: compare(actual[key],expected[key])
    elif isinstance(expected,list):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected): compare(a,b)
    elif isinstance(expected,float):
        assert actual==pytest.approx(expected,rel=3e-5,abs=2e-5)
    else:
        assert actual==expected


def test_full_replay_retains_all_six_designs_and_original_control():
    raw=(study.BASE/'results/position_error_v2.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='422f09adba2232aa704f5cd9e77272d16431cffc5a4311a198c4cb59d0dad84a'
    expected=json.loads(raw)
    compare(checked.run(),expected)
    assert len(expected['cases'])==6
    assert sum(c['status']=='LOCAL_LINEAR_RESPONSE' for c in expected['cases'])==5
    assert expected['plan']['weight_code_sigma_m']==20
    for case in expected['cases']:
        if case['models']:
            assert case['local_code_linearization_remainder_max_m']<1e-6
    assert not expected['real_target_fit'] and not expected['physical_covariance_qualified']


def test_frozen_versions_and_wrapper_ancestry():
    root=study.BASE.parents[1]
    for commit in ('dec7f4a','b2e7792'):
        subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=root,check=True)
    paths=[*checked.SOURCES,'research/exploratory/position_error_checked_v2.py','research/exploratory/position_error_plan_v2.json']
    for name in paths:
        assert subprocess.check_output(['git','show','b2e7792:'+name],cwd=root)==(root/name).read_bytes()
    old=json.loads((study.BASE/'results/position_error_v1.json').read_bytes())
    assert old['schema']=='position-error-transfer-v1' and len(old['cases'])==6


def test_changed_source_stops_before_geometry(monkeypatch):
    original=Path.read_bytes
    def changed(path):
        return original(path)+(b'\n' if path==Path(study.__file__) else b'')
    monkeypatch.setattr(Path,'read_bytes',changed)
    monkeypatch.setattr(study,'run',lambda *args:pytest.fail('modified implementation executed'))
    with pytest.raises(ValueError): checked.run()
