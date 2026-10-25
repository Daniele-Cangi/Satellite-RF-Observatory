"""Fixed-transmit range geometry; independence from RF values and clocks."""
import numpy as np
import pytest
from research.exploratory import reference_geometry as g
from research.exploratory.tests.test_weak_source_physics import real_case
from research.exploratory.tests.test_reference_state_validation import Forbidden


def test_two_way_moving_geometry_matches_independent_finite_fixed_transmit_paths(monkeypatch):
    data,provider,weather,station,q,code,t,xyz,mjd=real_case();tb=t-.1
    model=g.two_way_range_geometry(provider,q,tb,xyz);up=model['uplink_s'];down=model['downlink_s']
    tx=g.rotate_z(xyz,-g.OMEGA*up)
    def finite(orbit,reflector,epoch=0.):
        transmit=g.rotate_z(xyz,g.OMEGA*(-up+epoch));dt=epoch
        for _ in range(20):
            r,v=provider.precise.orbit(q,tb+dt)
            r=r+g.rtn_basis(r,v)@orbit+provider.attitude.body_to_ecef(q,tb+dt,provider.step)@reflector
            point=g.rotate_z(r,g.OMEGA*dt)
            updated=epoch+np.linalg.norm(point-transmit)/g.C-up
            if abs(updated-dt)<1e-17:dt=updated;break
            dt=updated
        r,v=provider.precise.orbit(q,tb+dt)
        point=g.rotate_z(r+g.rtn_basis(r,v)@orbit+provider.attitude.body_to_ecef(q,tb+dt,provider.step)@reflector,g.OMEGA*dt)
        tau=down
        for _ in range(20):
            new=np.linalg.norm(point-g.rotate_z(xyz,g.OMEGA*(dt+tau)))/g.C
            if abs(new-tau)<1e-17:tau=new;break
            tau=new
        return g.C/2*(dt+tau-down-epoch)
    for family in ('orbit','reflector'):
        for j in range(3):
            perturb=np.eye(3)[j]*5.;zero=np.zeros(3)
            plus=finite(perturb if family=='orbit' else zero,perturb if family=='reflector' else zero)
            minus=finite(-perturb if family=='orbit' else zero,-perturb if family=='reflector' else zero)
            expected=model['orbit_mapping' if family=='orbit' else 'body_mapping'][j]
            assert (plus-minus)/10==pytest.approx(expected,abs=1e-7)
    epoch=(finite(np.zeros(3),np.zeros(3),.1)-finite(np.zeros(3),np.zeros(3),-.1))/(.2*g.C)
    assert epoch==pytest.approx(model['epoch_light_time_mapping'],abs=1e-12)
    assert model['range_scale_mapping']*25e6==pytest.approx(model['vacuum_half_roundtrip_m'])
    assert model['optical_zenith_mapping']>1.
    assert g.C*(model['receive_gpst_s']-model['transmit_gpst_s'])/2==pytest.approx(model['vacuum_half_roundtrip_m'],abs=.002)
    def forbidden(*a,**k):raise AssertionError('two-way operator consumed RF or clock')
    monkeypatch.setattr(provider,'antenna_state',forbidden);monkeypatch.setattr(provider.precise,'clock',forbidden)
    np.testing.assert_array_equal(g.two_way_range_geometry(provider,q,tb,xyz)['orbit_mapping'],model['orbit_mapping'])
    with pytest.raises(ValueError,match='before decoding'):
        g.two_way_range_geometry(provider,provider.precise.target,Forbidden(),Forbidden())


def test_physical_runner_uses_archived_reference_rows_and_no_own_rf_or_new_fits(monkeypatch):
    import gzip,json
    from pathlib import Path
    from research.exploratory import reference_network_clocks as study
    from research.exploratory.tests.test_reference_state_validation import poison_products
    raw,data=study.baseline.read_inputs();weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    rows,_=study.reference_rows(data,'G05',36300.,weather,continuity=True,combinations=True,source_geometry=True,reference_sources=True)
    rows=[r for r in rows if r['time_s']==36300.]
    network=study.network_clocks.fit(rows,raw_covariance=study.gnss_combinations.assumed_endpoint_covariance())
    profile,w=study.source_geometry.profile_sources(network,'G05',study.source_geometry.FAMILIES)
    vector=np.zeros(len(w['columns']));vector[0]=1.
    digest=study.baseline.interval.shared.digest;hashes={k:digest(v) for k,v in raw.items()}
    parent={'input_sha256':hashes,'raw_endpoint_weight_covariance_m2':study.gnss_combinations.assumed_endpoint_covariance().tolist(),
        'candidates':{'G04':{'windows':[],'prepared_arc_count':0,'archived_nominal_fit_status':'INSUFFICIENT_PREPARED_ARCS'},
        'G05':{'windows':[],'prepared_arc_count':2,'archived_nominal_fit_status':'BRANCH_SEARCH_INCOMPLETE',
            'reference_rows':rows,'source_profile':profile,'coupled_model_state_map':np.zeros((6,len(vector))),
            'prior_frozen_weak_direction_m_per_unit_l2_m':vector}}}
    payload=gzip.compress(json.dumps(study.native(parent)).encode());read=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda p:payload if p.name=='stable_source_differential_v1.json.gz' else read(p))
    monkeypatch.setattr(study.baseline.interval.shared,'digest',lambda b:'56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020' if b==payload else digest(b))
    poisoned=poison_products(data,'G05');poisoned['observations']=Forbidden();poisoned['phase']=Forbidden()
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:(raw,poisoned))
    specs=study.source_geometry.physical_observable_case_specs()
    selected=[specs[0],next(z for z in specs if z['purpose']=='full_physical_readout_design' and z['rho']==.5 and z['calibration_mode']=='absolute' and z['calibration_sigma_m']==.001 and z['observation_sigma_m']==.01)]
    monkeypatch.setattr(study.source_geometry,'physical_observable_case_specs',lambda:selected)
    def forbidden(*a,**k):raise AssertionError('new RF/source fit or state score')
    for owner,name in ((study.dynamic_fit,'fit'),(study.baseline,'score_rf'),(study,'score_mw'),(study.baseline,'oracle'),(study.baseline,'state_errors'),(study.source_geometry,'profile_sources')):
        monkeypatch.setattr(owner,name,forbidden)
    result=study.run(physical_observables=True);case=result['candidates']['G05']
    assert case['status']=='PHYSICAL_OBSERVABLE_OPERATORS_PREPARED',case.get('reason')
    assert all(r['reference']!='G05' for r in case['range_geometry_terminals'])
    assert len(case['operator_cases'])==2 and all(z['status']=='PHYSICAL_OPERATOR_INFORMATION_EVALUATED' for z in case['operator_cases'])
    assert case['source_profile_is_unchanged_archive']
    assert not result['new_rf_trajectory_fits'] and not result['new_rf_or_mw_scoring'] and not result['new_source_or_calibration_values_estimated']
