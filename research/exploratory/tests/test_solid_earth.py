from datetime import datetime,timedelta
import json
import numpy as np
import pytest
from research.exploratory import solid_earth_model as tide
from research.exploratory import solid_earth_study as study

CASES=json.loads((study.INPUTS/'iers_examples.json').read_bytes())

@pytest.mark.parametrize('case',CASES[:3],ids=lambda c:c['date'])
def test_iers_published_examples(case):
    result=tide.tide_displacement(case['station'],case['sun'],case['moon'],datetime.fromisoformat(case['date']),case['tai_minus_utc'])
    assert result==pytest.approx(case['expected'],abs=1e-12,rel=0)


def test_published_fourth_example_inconsistency_is_not_hidden():
    case=CASES[3]
    result=tide.tide_displacement(case['station'],case['sun'],case['moon'],datetime.fromisoformat(case['date']),37)
    # Published 2017 header repeats 2015 expected values, despite radically
    # different inputs. Keep it as an explicit mismatch, not a passed benchmark.
    assert case['expected']==pytest.approx(CASES[2]['expected'],abs=1e-16,rel=0)
    assert np.linalg.norm(result-case['expected'])>1.


def test_axes_permanent_term_and_component_accounting():
    case=CASES[0]; xyz=case['station']; utc=datetime.fromisoformat(case['date'])
    s,c,sl,cl,matrix=tide.local_axes(xyz)
    assert matrix.T@matrix==pytest.approx(np.eye(3),abs=1e-14,rel=0)
    expected_radial=-np.sqrt(5/(4*np.pi))*.31460*(.6078-.0006*(1-1.5*c*c))*(1.5*s*s-.5)
    assert (matrix.T@tide.permanent_displacement(xyz))[0]==pytest.approx(expected_radial,abs=1e-14,rel=0)
    terms=tide.displacement_components(xyz,case['sun'],case['moon'],utc,34)
    assert len(terms)==6 and all(np.linalg.norm(v)>0 for v in terms.values())
    assert sum(terms.values())==pytest.approx(case['expected'],abs=1e-12,rel=0)

@pytest.mark.parametrize('xyz',[[0,0,0],[6378,0,0],[0,0,6378137],[float('nan'),1,2],[1,2]])
def test_invalid_station_units_and_geometry_rejected(xyz):
    with pytest.raises(ValueError):tide.local_axes(xyz)


def test_celestial_time_grid_and_controls():
    samples,_=study.celestial_inputs('g14')
    assert samples[14100]['utc']=='2026-09-03T03:54:42'
    xyz=np.array([CASES[0]['station']]*11); times=list(range(14100,14401,30))
    positions,offsets=study.station_variants(xyz,times,samples)
    assert np.array_equal(positions['regularized'],xyz)
    assert positions['solid_earth']-positions['permanent_removed_control']==pytest.approx(np.array([tide.permanent_displacement(x) for x in xyz]),abs=1e-9,rel=0)
    assert offsets['midpoint_control'][0]==offsets['solid_earth'][5]==offsets['midpoint_control'][-1]
    assert not np.allclose(offsets['gpst_as_utc_control'],offsets['solid_earth'],atol=1e-7,rtol=0)
    a,_=tide.arguments(datetime(2026,9,3,23,59,59),37)
    b,_=tide.arguments(datetime(2026,9,4),37)
    assert np.max(np.abs((b-a+180)%360-180))<.001


def test_celestial_tamper_rejected(monkeypatch,tmp_path):
    for p in study.INPUTS.iterdir(): (tmp_path/p.name).write_bytes(p.read_bytes())
    with (tmp_path/'sun_moon.json').open('ab') as stream: stream.write(b' ')
    monkeypatch.setattr(study,'INPUTS',tmp_path)
    with pytest.raises(ValueError,match='pinned input differs'):study.celestial_inputs('g14')


def test_report_comparator_rejects_omission_and_metadata_change():
    with pytest.raises(ValueError):study.compare_replay({'a':[1.]},{'a':[1.,2.]})
    with pytest.raises(ValueError):study.compare_replay({'target':'G14'},{'target':'G12'})
    with pytest.raises(ValueError):study.compare_replay({'a':1.},{'a':1.01})

@pytest.mark.parametrize('tag',['g14','g12'])
def test_complete_study_replay(tag):
    expected=json.loads((study.BASE/f'results/{tag}_solid_earth_v1.json').read_bytes())
    actual=study.run(tag)
    study.compare_replay(actual,expected)
    assert actual['case_count']==6
    assert actual['status_counts']=={'CALIBRATION_QUALIFIED':6}
    for case in actual['cases']:
        assert case['evaluated_path_count']+len(actual['omitted_paths'])==actual['observed_path_count']
        assert len(case['calibrations'])==7
        assert all(len(c['epochs'])==11 for c in case['calibrations'].values())
    assert not actual['target_fit_performed'] and not actual['instantaneous_site_position_qualified']
