from datetime import datetime,timezone
import hashlib
import json
import shutil
import subprocess
import numpy as np
import pytest
from research.exploratory import ocean_pole_model as model
from research.exploratory import ocean_pole_study as study
from research.exploratory import prepare_ocean_loading as prep

UTC=datetime(2020,1,1)


def test_pole_references_mas_year_units():
    assert model.pole_reference(UTC,'2018')==pytest.approx([.08854,.3897],abs=1e-12,rel=0)
    assert model.pole_reference(UTC,'2010')==pytest.approx([.175795,.346317],abs=1e-12,rel=0)

@pytest.mark.parametrize('latitude,longitude',[(0,0),(45,0),(45,90),(-45,120)])
def test_pole_zero_and_independent_spherical_formula(latitude,longitude):
    phi,lam=np.deg2rad([latitude,longitude]);r=6378137
    xyz=r*np.array([np.cos(phi)*np.cos(lam),np.cos(phi)*np.sin(lam),np.sin(phi)])
    ref=model.pole_reference(UTC)
    assert model.pole_ecef(xyz,UTC,*ref)==pytest.approx([0,0,0],abs=1e-15,rel=0)
    m1,m2=.1,-.2;theta=np.pi/2-phi
    radial=-.033*np.sin(2*theta)*(m1*np.cos(lam)+m2*np.sin(lam))
    south=-.009*np.cos(2*theta)*(m1*np.cos(lam)+m2*np.sin(lam))
    east=.009*np.cos(theta)*(m1*np.sin(lam)-m2*np.cos(lam))
    transform=np.array([[np.sin(theta)*np.cos(lam),np.cos(theta)*np.cos(lam),-np.sin(lam)],
                        [np.sin(theta)*np.sin(lam),np.cos(theta)*np.sin(lam),np.cos(lam)],
                        [np.cos(theta),-np.sin(theta),0.]])
    actual=model.pole_ecef(xyz,UTC,ref[0]+m1,ref[1]-m2)
    assert actual==pytest.approx(transform@np.array([radial,south,east]),abs=1e-14,rel=0)


def test_usw_to_ecef_sign_and_axis_order():
    assert model.ocean_ecef([.01,.02,.03],[6378137.,0,0])==pytest.approx([.01,-.03,-.02],abs=1e-12,rel=0)

@pytest.mark.parametrize('date,convention',[(datetime(2009,1,1),'2010'),(UTC.replace(tzinfo=timezone.utc),'2018'),(UTC,'unknown')])
def test_pole_unsupported_convention_rejected(date,convention):
    with pytest.raises(ValueError):model.pole_reference(date,convention)

@pytest.mark.parametrize('defect',['duplicate','missing','negative','nan','cmc'])
def test_blq_invalid_input_rejected(defect):
    text=(study.INPUTS/'fit_stations.BLQ').read_text(encoding='ascii')
    if defect=='duplicate':text+='\n'+text.split('  ALGO',1)[1].join(['  ALGO',''])
    if defect=='missing':text=text.replace('  ALGO\n','  XXXX\n')
    if defect=='negative':text=text.replace('.00514','-.00514')
    if defect=='nan':text=text.replace('.00514','nan')
    if defect=='cmc':text=text.replace('CMC:  NO','CMC: YES')
    with pytest.raises(ValueError):model.parse_blq(text)


def test_inputs_products_and_geographic_associations():
    products,stations,hashes,receipt=study.read_loading('g14')
    assert set(stations)==set(model.NAMES)
    assert products['cmc_applied'] is False
    assert len(products['benchmarks'])==2
    assert all(len(b['actual_usw_m'])==24 and b['qualified_2_um'] for b in products['benchmarks'])
    assert .019<products['cmc_header_phase_free_norm_bound_m']<.020
    for tag in ('g14','g12'):
        frame=json.loads((study.BASE/f'results/{tag}_station_frame_epoch_v1.json').read_bytes())
        for st in frame['station_models']:
            assert model.geographic_distance(st['positions']['final_transport'][0],stations[st['station'][:4]])<10000
    # Guard against the manifest newline normalization found in PR145.
    path='research/exploratory/loading_reference/sources.json'
    blob=subprocess.check_output(['git','show','HEAD:'+path],cwd=study.FRAME.ROOT)
    assert hashlib.sha256(blob).hexdigest()==receipt['source_receipt_sha256']


def test_loading_product_tamper_rejected(monkeypatch,tmp_path):
    for p in study.INPUTS.iterdir():(tmp_path/p.name).write_bytes(p.read_bytes())
    with (tmp_path/'hardisp_products.json').open('ab') as f:f.write(b' ')
    monkeypatch.setattr(study,'INPUTS',tmp_path)
    with pytest.raises(ValueError,match='pinned input differs'):study.read_loading('g14')

@pytest.mark.skipif(shutil.which('gfortran') is None,reason='optional HARDISP producer needs gfortran; pinned products still replayed')
def test_original_fortran_regenerates_benchmarks_and_all_station_series(tmp_path):
    exe,info=prep.build(tmp_path/'build')
    expected,stations,_,_=study.read_loading('g14')
    fixtures=json.loads((study.INPUTS/'hardisp_examples.json').read_bytes())
    for name,f in fixtures.items():
        actual=prep.series(exe,datetime(2009,6,25,1,10,45),f['six_lines'],24,3600)
        assert actual==pytest.approx(np.array(f['expected_usw_m']),abs=2e-6,rel=0)
    for event in expected['events'].values():
        for name,values in event['ocean_usw_m'].items():
            actual=prep.series(exe,datetime.fromisoformat(event['start_utc']),stations[name]['six_lines'])
            assert actual==pytest.approx(np.array(values),abs=2e-6,rel=0)

@pytest.mark.parametrize('tag',['g14','g12'])
def test_full_loading_study_replay(tag):
    expected=json.loads((study.BASE/f'results/{tag}_ocean_pole_v1.json').read_bytes())
    actual=study.run(tag)
    study.solid.compare_replay(actual,expected)
    assert actual['case_count']==6 and actual['status_counts']=={'CALIBRATION_QUALIFIED':6}
    for case in actual['cases']:
        assert case['evaluated_path_count']+len(actual['omitted_paths'])==actual['observed_path_count']
        assert len(case['calibrations'])==7 and all(len(c['epochs'])==11 for c in case['calibrations'].values())
    assert not actual['code_loading_frame_alignment_qualified'] and not actual['target_fit_performed']


def test_every_failed_station_remains_reported(monkeypatch):
    prior=json.loads((study.BASE/'results/g14_solid_earth_v1.json').read_bytes())
    monkeypatch.setattr(study.solid,'run',lambda tag:prior)
    def fail(*args,**kwargs):raise ValueError('injected loading calibration failure')
    monkeypatch.setattr(study.FRAME,'calibrate_fixed',fail)
    actual=study.run('g14')
    assert actual['status_counts']=={'CALIBRATION_NOT_QUALIFIED':6}
    for case in actual['cases']:
        assert case['pooled_reference_rms_m'] is None and len(case['calibrations'])==7
        assert all(c['status']=='ENGINEERING_FAILURE' for c in case['calibrations'].values())
