from datetime import datetime
import json
import numpy as np
import pytest
from research.exploratory import erp_polar_bound as study


def test_phase_bound_matches_analytic_single_harmonic():
    assert study.phase_bound([[[3.,0.],[0.,4.]]])==pytest.approx(4.)
    assert study.phase_bound([[[3.,0.],[4.,0.]]])==pytest.approx(5.)
    assert study.phase_bound([[[1.,0.],[0.,1.]]]*2)==pytest.approx(2.)


def test_bound_encloses_independent_phase_combinations():
    rng=np.random.default_rng(142)
    a=rng.normal(size=(8,2,2));bound=study.phase_bound(a)
    angles=rng.uniform(-np.pi,np.pi,size=(1000,8))
    vectors=np.stack([np.cos(angles),np.sin(angles)],axis=-1)
    result=np.einsum('kij,nkj->ni',a,vectors)
    assert np.max(np.linalg.norm(result,axis=1))<=bound


def test_pole_operator_global_bound_independent_formula():
    # Orthogonal longitude rotation and ECEF rotation do not change singular values.
    for theta in np.linspace(0,np.pi,301):
        a=np.array([[-.033*np.sin(2*theta),0],[-.009*np.cos(2*theta),0],[0,.009*np.cos(theta)]])
        assert np.linalg.norm(a,2)<=study.POLE_OPERATOR_M_PER_ARCSEC+1e-15
    assert np.linalg.norm(np.array([[-.033,0],[0,0],[0,.009/np.sqrt(2)]]),2)==pytest.approx(.033)


def test_daily_pole_units_rate_and_noon():
    raw=(study.BASE/'inputs/code_conventions/g14.erp').read_bytes()
    erp=study.parse_erp(raw,'2026-09-03')
    assert study.daily_pole(erp,datetime(2026,9,3,12))==pytest.approx([.208019,.338261],abs=1e-14)
    assert study.daily_pole(erp,datetime(2026,9,3,0))==pytest.approx([.2087925,.3385565],abs=1e-14)
    with pytest.raises(ValueError):study.daily_pole(erp,datetime(2026,9,4))


@pytest.mark.parametrize('old,new',[(b'E-6"/D',b'E-3"/D'),(b'61286.50',b'61287.50'),(b'DESAI2016',b'IERS2010'),(b'208019',b'NaN')])
def test_invalid_erp_rejected(old,new):
    raw=(study.BASE/'inputs/code_conventions/g14.erp').read_bytes().replace(old,new)
    with pytest.raises(ValueError):study.parse_erp(raw,'2026-09-03')


@pytest.mark.parametrize('defect',['missing','duplicate','units','nan'])
def test_invalid_spectrum_rejected(defect):
    text=(study.BASE/'inputs/erp_polar/DESAI2016.SUB').read_text(encoding='utf-8')
    if defect=='missing':text='\n'.join(text.splitlines()[:-1])
    if defect=='duplicate':text+=text.splitlines()[-1]+'\n'
    if defect=='units':text=text.replace('(0.001 MAS)','(MAS)')
    if defect=='nan':text=text.replace('1.267064','nan')
    with pytest.raises(ValueError):study.parse_desai(text.encode('utf-8'))


def test_pinned_input_tamper_rejected(tmp_path):
    p=tmp_path/'a';p.write_bytes(b'tampered')
    with pytest.raises(ValueError):study.pinned(p,'0'*64)


def test_report_replay():
    expected=json.loads((study.BASE/'results/erp_polar_bound_v1.json').read_bytes())
    assert study.run()==expected
    assert expected['desai_harmonic_count']==159
    assert len(expected['events'])==2
    assert all(len(e['samples'])==11 for e in expected['events'])
    assert not expected['instantaneous_code_eop_qualified']
