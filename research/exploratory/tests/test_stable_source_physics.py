"""Portable precision and full-law checks for admitted differential rays."""
from decimal import Decimal
import numpy as np
import pytest
from research.exploratory import reference_network_clocks as study,reference_geometry as geometry
from research.exploratory.tests.test_weak_source_physics import real_case
from research.exploratory.tests.test_reference_state_validation import Forbidden


def make_ray(digits=50):
    data,provider,weather,station,q,code,t,xyz,mjd=real_case()
    return geometry.StableSourceRay(provider,weather,mjd,q,code,t,xyz,0.,digits=digits),(data,provider,weather,station,q,code,t,xyz,mjd)


def test_decimal_increments_converge_and_match_full_finite_products():
    ray,case=make_ray();data,provider,weather,station,q,code,t,xyz,mjd=case
    other=geometry.StableSourceRay(provider,weather,mjd,q,code,t,xyz,0.,digits=35)
    vector=np.array([.005,.01,-.02,.005,-.01,.005,0.,.03])
    np.testing.assert_allclose(ray.increment(vector),other.increment(vector),atol=1e-18,rtol=1e-14)
    np.testing.assert_array_equal(ray.increment(np.zeros(8)),np.zeros(3))
    maps=ray.mappings();central=ray.central_mappings()
    for field in ('wet_mapping','orbit_mapping','antenna_mapping','bias_code_mapping','bias_phase_mapping','bias_mw_mapping'):
        np.testing.assert_allclose(maps[field],central[field],atol=1e-14,rtol=1e-13)
    old=geometry.emitted_source_mappings(provider,weather,mjd,q,code,t,xyz,0.,complete=True)
    for key in ('orbit_mapping','antenna_mapping','bias_code_mapping','bias_phase_mapping'):
        np.testing.assert_allclose(maps[key],old[key],atol=1e-8,rtol=0)
    probe={'orbit':{q:vector[1:4]},'antenna':{q:vector[4:7]}}
    changed=geometry.physical_source_provider(provider,'G05',probe)
    def path(p,code,w):
        value=p.model(q,code,t,xyz,0.)[0];delay,_=study.baseline.day.atmosphere.components(p,w,mjd,q,code,t,xyz,0.)
        return value-delay['legacy_baseline']+delay['vmf3_full']
    shifted=study.wet.ShiftedWetWeather(weather,vector[0])
    finite=path(changed,code-vector[7],shifted)-path(provider,code,weather)
    assert ray.increment(vector)[1]==pytest.approx(finite,abs=3e-8)
    assert ray.increment(vector)[0]-ray.increment(vector)[1]==pytest.approx(vector[7],abs=1e-17)


def test_stable_even_curvature_survives_small_path_cancellation():
    ray,_=make_ray();gradient=np.asarray(ray.mappings()['antenna_mapping'])
    direction=np.cross(gradient,[1.,0.,0.]);direction/=np.linalg.norm(direction)
    even=[]
    for amplitude in (.01,.1):
        v=np.r_[0.,np.zeros(3),direction*amplitude,0.]
        plus=ray.increment(v,as_decimal=True)[1];minus=ray.increment(-v,as_decimal=True)[1]
        even.append(float((plus+minus)/2))
    assert even[0]>1e-13
    assert even[1]/even[0]==pytest.approx(100.,rel=1e-5)


def test_stable_clock_derivative_and_early_candidate_boundary():
    ray,case=make_ray();data,provider,weather,station,q,code,t,xyz,mjd=case
    def path(clock):
        value=provider.model(q,code,t,xyz,clock)[0];delay,_=study.baseline.day.atmosphere.components(provider,weather,mjd,q,code,t,xyz,clock)
        return value-delay['legacy_baseline']+delay['vmf3_full']
    finite=1+(path(1000.)-path(-1000.))/2000.
    assert ray.clock_coefficient()==pytest.approx(finite,abs=1e-11)
    with pytest.raises(ValueError,match='before decoding'):
        geometry.StableSourceRay(provider,weather,mjd,'G05',Forbidden(),Forbidden(),Forbidden(),Forbidden())
    with pytest.raises(ValueError,match='declared decimal'):
        geometry.StableSourceRay(provider,weather,mjd,q,code,t,xyz,0.,digits=16)


def test_stable_runner_excludes_own_values_and_performs_no_new_rf_fits_or_scores(monkeypatch):
    import gzip,json
    from pathlib import Path
    from research.exploratory.tests.test_reference_state_validation import poison_products
    raw,data=study.baseline.read_inputs();weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    rows,_=study.reference_rows(data,'G05',36060.,weather,continuity=True,combinations=True,source_geometry=True,reference_sources=True)
    for row in rows:row['reference_clock_centre_m']=0.
    network=study.network_clocks.fit(rows,raw_covariance=study.gnss_combinations.assumed_endpoint_covariance())
    profile,_=study.source_geometry.profile_sources(network,'G05',study.source_geometry.FAMILIES)
    vector=np.zeros(profile['source_count']);vector[0]=1.
    probes=[{'mode':mode,'source_l2_m':amplitude,'sign':sign,'source_vector_m':(vector*amplitude*sign).tolist()}
        for mode in ('strong','weak') for amplitude in (.01,.1) for sign in ((1.,-1.) if mode=='weak' else (1.,))]
    r=rows[0];endpoint=[r['station'],r['time_s']]
    digest=study.baseline.interval.shared.digest;hashes={k:digest(v) for k,v in raw.items()}
    previous={'input_sha256':hashes,'candidates':{'G04':{'windows':[],'prepared_arc_count':0,'archived_nominal_fit_status':'INSUFFICIENT_PREPARED_ARCS'},
        'G05':{'windows':[],'prepared_arc_count':2,'archived_nominal_fit_status':'BRANCH_SEARCH_INCOMPLETE',
            'source_profile':profile,'reference_rows':rows,'clock_endpoint_keys':[endpoint],
            'stability':{'weak_direction_m_per_unit_l2_m':vector.tolist()},'physical_probes':probes}}}
    separation={'input_sha256':hashes,'candidates':{'G05':{'clock_requests':[[endpoint+[1.]]],
        'full_state_observation_response':np.zeros((6,1)).tolist(),'transport':{'clock_observation_indices':[0]},
        'target_wet_model_design':np.zeros((1,len(profile['wet']['stations']))).tolist()}}}
    weak=gzip.compress(json.dumps(study.native(previous)).encode());older=gzip.compress(json.dumps(separation).encode());original_read=Path.read_bytes
    monkeypatch.setattr(Path,'read_bytes',lambda p:weak if p.name=='weak_source_physical_recovery_v1.json.gz' else (older if p.name=='reference_source_separation_v1.json.gz' else original_read(p)))
    monkeypatch.setattr(study.baseline.interval.shared,'digest',lambda b:'917202d0184c4bed1b8925d98818df6c4e0a14af1ad2b9eb2524f5dd001b3717' if b==weak else ('a8caee27bbb751090ce4af25d384bc23bad8111e2d94fe76754834f937821467' if b==older else digest(b)))
    poisoned=poison_products(data,'G05')
    for epochs in poisoned['observations'].values():
        for e in epochs:
            for key in e['if_code_m']:
                if key=='G05' or e['time_s']>36060.:e['if_code_m'][key]=Forbidden()
    monkeypatch.setattr(study.baseline,'read_inputs',lambda:(raw,poisoned))
    monkeypatch.setattr(study.source_geometry,'complementary_source_information',lambda *a:{})
    monkeypatch.setattr(study.source_geometry,'joint_external_clock_source_design',lambda n,c,*a,**k:(np.zeros((len(c),len(c))),{}))
    def forbidden(*a,**k):raise AssertionError('new RF fit/score or CODE state access')
    for owner,name in ((study.dynamic_fit,'fit'),(study.baseline,'score_rf'),(study,'score_mw'),(study.baseline,'oracle'),(study.baseline,'state_errors')):
        monkeypatch.setattr(owner,name,forbidden)
    result=study.run(stable_sources=True)
    assert result['candidates']['G05']['status']=='STABLE_DIFFERENTIAL_PREPARED',result['candidates']['G05'].get('reason')
    assert len(result['candidates']['G05']['physical_probes'])==6
    assert not result['new_rf_trajectory_fits'] and not result['new_rf_or_mw_scoring']
