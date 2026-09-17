import io
import json
import pytest
from research.exploratory import code_convention_audit as audit

HEADER="""#dP2026  9  3  0  0  0.00000000     289 d     IGc20 FIT AIUB
/* Rapid GNSS orbits and clocks for year-day 2026-246
/* PCV:IGS20_2425 OL/AL:FES2014b NONE YN ORB:CoN CLK:CoN
*  2026 9 3 0 0 0
"""
ERP="""VERSION 2
CODE RAPID GNSS ERP INFORMATION FOR (MIDDLE) DAY 246, 2026       04-SEP-26 16:18
---
NUTATION MODEL       : IAU2000R06               SUBDAILY POLE MODEL: DESAI2016
MJD X-P Y-P
units
NUMERIC BODY NOT INTERPRETED
"""


def test_declarations_resolve_only_ocean_cmc():
    sp3=audit.sp3_header(io.StringIO(HEADER),'2026-09-03')
    erp=audit.erp_header(ERP.encode(),'2026-09-03')
    d=audit.decision(sp3,erp)
    assert d['ocean_cmc_product_declaration_resolved']
    assert d['subdaily_model_required']=='DESAI2016'
    assert not d['atmospheric_loading_absence_inferred']
    assert not d['mean_pole_realization_qualified']
    assert not d['instantaneous_code_eop_reconstructed']


def test_header_iterator_stops_before_satellite_values():
    def lines():
        yield from HEADER.splitlines()
        raise AssertionError('satellite body entered')
    assert audit.sp3_header(lines(),'2026-09-03')['orbit_origin']=='CoN'


@pytest.mark.parametrize('old,new',[('FES2014b','OTHER'),('YN ORB','NN ORB'),('ORB:CoN','ORB:CoM'),('CLK:CoN','CLK:CoM')])
def test_incompatible_products_never_resolve_cmc(old,new):
    sp3=audit.sp3_header(io.StringIO(HEADER.replace(old,new)),'2026-09-03')
    assert not audit.decision(sp3,{'subdaily_pole_model':'DESAI2016'})['ocean_cmc_product_declaration_resolved']


@pytest.mark.parametrize('defect',['duplicate','flags','date','agency','epoch'])
def test_sp3_malformed_or_mismatched_rejected(defect):
    text=HEADER
    if defect=='duplicate':text=text.replace('*  2026',HEADER.splitlines()[2]+'\n*  2026')
    if defect=='flags':text=text.replace('YN ORB','XX ORB')
    if defect=='date':text=text.replace('#dP2026  9  3','#dP2026  9  4')
    if defect=='agency':text=text.replace('AIUB','OTHER')
    if defect=='epoch':text=text.replace('*  2026 9 3 0 0 0\n','')
    with pytest.raises(ValueError):audit.sp3_header(io.StringIO(text),'2026-09-03')


@pytest.mark.parametrize('old,new',[('VERSION 2','VERSION 1'),('DAY 246','DAY 248'),('RAPID','FINAL'),('SUBDAILY POLE MODEL:','UNKNOWN:')])
def test_erp_mismatches_rejected(old,new):
    with pytest.raises(ValueError):audit.erp_header(ERP.replace(old,new).encode(),'2026-09-03')


def test_evidence_tamper_rejected(tmp_path):
    path=tmp_path/'evidence';path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='hash differs'):audit.checked(path,'0'*64)


def test_frozen_report_replay():
    expected=json.loads((audit.BASE/'results/code_convention_audit_v1.json').read_bytes())
    assert audit.run()==expected
    assert len(expected['events'])==2
    assert all(e['decision']['ocean_cmc_product_declaration_resolved'] for e in expected['events'])
    assert not expected['target_states_parsed'] and not expected['eop_values_parsed']
