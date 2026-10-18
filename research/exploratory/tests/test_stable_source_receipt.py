"""Retained stable arithmetic and genuinely joint information-design receipt."""
from collections import Counter
import gzip,hashlib,json,subprocess
import numpy as np
from research.exploratory import reference_network_clocks as study

PRODUCER='e762b4b28e026ae1076f505779e9f77206ef7a35'
RESULT_SHA256='56b325ab32a679d89223b89bbe88633cd3850bdcf0cd605c18bea1bf62900020'


def test_stable_differential_receipt_preserves_physics_provenance_and_joint_observations():
    payload=(study.baseline.BASE/'results/stable_source_differential_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    subprocess.run(['git','merge-base','--is-ancestor',PRODUCER,'HEAD'],cwd=study.baseline.BASE.parents[1],check=True,capture_output=True)
    result=json.loads(gzip.decompress(payload));raw,data=study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path,wanted in result['source_sha256'].items():
        source=subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    for path,wanted in result['prior_sha256'].items():
        assert hashlib.sha256((study.baseline.BASE/'results'/path).read_bytes()).hexdigest()==wanted
    assert result['schema']=='exposed-stable-source-differential-v1'
    assert result['source_probe_directions_frozen_from_prior'] and result['archived_rf_state_used_only_for_local_response']
    assert result['information_target_is_fixed_nominal_rf_sensitivity_not_joint_state_covariance']
    assert not any(result[k] for k in ('candidate_products_used_in_own_network','candidate_rf_used_in_own_network',
        'candidate_code_orbit_scoring','new_rf_trajectory_fits','new_rf_or_mw_scoring','archived_rf_state_used_as_fit_seed',
        'physical_covariance_qualified','production_floors_changed','independent_measurements_admitted','g12_state_accessed','new_confirmation'))
    assert result['decimal_digits']==50 and result['precision_check_digits']==35 and result['precision_check_row_stride']==128
    candidates=result['candidates'];assert set(candidates)==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values())==440
    assert sum(c['prepared_arc_count'] for c in candidates.values())==63
    assert dict(Counter(c['status'] for c in candidates.values()))==result['status_counts']
    assert dict(Counter(c['archived_nominal_fit_status'] for c in candidates.values()))==result['archived_nominal_fit_status_counts']
    supported=[]
    for q,c in candidates.items():
        if 'source_profile' not in c:continue
        supported.append(q);assert c['status']=='STABLE_DIFFERENTIAL_PREPARED'
        assert all(r['reference']!=q and r['stable_decimal_digits']==50 for r in c['reference_rows'])
        assert len(c['precision_check_keys'])==(len(c['reference_rows'])+127)//128
        assert c['precision_mapping_max_abs_35_minus50']<1e-12
        assert c['analytic_central_mapping_max_abs_difference']<1e-12
        np.testing.assert_allclose(np.asarray(c['reference_model_state_map'])+c['candidate_model_state_map'],c['coupled_model_state_map'],atol=1e-9,rtol=1e-12)
        assert len(c['physical_probes'])==6 and len(c['odd_even_probes'])==2
        for p in c['physical_probes']:
            assert p['status'] in ('STABLE_FINITE_PHYSICAL_INCREMENT_PREPARED','STABLE_PHYSICAL_PROBE_FAILED')
            if p['status']=='STABLE_FINITE_PHYSICAL_INCREMENT_PREPARED':assert p['decimal35_minus50_max_abs_m']<1e-15
        assert len(c['complementary_source_information'])==15
        for laws in c['complementary_source_information'].values():
            assert set(laws)=={'independent','family_common_half','family_offset_free'}
            for design in laws.values():
                assert not design['independent_external_values_admitted']
                for grid in design['grid']:
                    for tol,info in grid['rank_cases'].items():
                        assert info['absolute_singular_cut']==float(tol)*c['source_profile']['original_weighted_source_scale_per_m']
                        if not info['complete_state_precision_issued']:assert not info['meets_1m_1mm_s_design_benchmark']
        assert len(c['joint_external_clock_information'])==10
        for clock in c['joint_external_clock_information']:
            meta=clock['joint_clock_model']
            assert meta['external_endpoint_count']==len(c['clock_endpoint_keys'])
            assert meta['external_measurements_observe_receiver_clocks'] and meta['instrument_offsets_profiled_without_prior']
            assert meta['external_source_shift_KG_not_treated_as_direct_observation'] and not meta['external_values_admitted']
    assert supported==['G05','G11','G19','G20','G21']
    # One adverse fold is enough for this offline numerical replay; the full
    # physical precision checks and all denominators remain in the artifact.
    q='G19';c=candidates[q];network=study.network_clocks.fit(c['reference_rows'],raw_covariance=result['raw_endpoint_weight_covariance_m2'])
    profile,w=study.source_geometry.profile_sources(network,q,study.source_geometry.FAMILIES)
    assert profile['resolved_rank']==c['source_profile']['resolved_rank']
    ancestor=json.loads(gzip.decompress((study.baseline.BASE/'results/reference_source_separation_v1.json.gz').read_bytes()))['candidates'][q]
    requests=[{(station,time):weight for station,time,weight in own} for own in ancestor['clock_requests']]
    kg=sum(k@g for k,g in zip(study.network_clocks.observation_response(network,requests),w['designs'],strict=True))
    response=np.asarray(ancestor['full_state_observation_response']);target=np.asarray(ancestor['target_wet_model_design'])
    gc=np.zeros((response.shape[1],len(w['columns'])))
    for index,col in enumerate(w['columns']):
        if col[0]=='wet':gc[:,index]=target[:,profile['wet']['stations'].index(col[1])]
    coupled=-response[:,ancestor['transport']['clock_observation_indices']]@kg-response@gc
    np.testing.assert_allclose(coupled,c['coupled_model_state_map'],atol=1e-7,rtol=1e-4)
    u,s,v=np.linalg.svd(w['design'],full_matrices=False);spec={'u':u,'s':s,'v':v,'rank':profile['resolved_rank']}
    probe=next(p for p in c['physical_probes'] if p['mode']=='weak' and p['source_l2_m']==.01 and p['sign']==1)
    assert probe['status']=='STABLE_FINITE_PHYSICAL_INCREMENT_PREPARED'
    provider,corrections=study.baseline.subset_products(data,[ref for ref in data['plan']['references'] if ref!=q],q)
    first=network['blocks'][0]['rows'][0];station,ref,time=first['station'],first['reference'],first['time_s']
    assert ref!=q
    code=next(epoch['if_code_m'][ref] for epoch in data['observations'][station] if epoch['time_s']==time)+corrections[time,ref]['if_code_change_m']
    xyz=np.asarray(data['positions'][station][int((time-36000)/30)],float)
    mjd=(study.datetime.fromisoformat(data['plan']['date_gpst'])-study.datetime(1858,11,17)).days
    weather=study.baseline.interval.shared.meteo.WeatherGrid(study.baseline.interval.shared.meteo.read_inputs()[0])
    ray=study.reference_geometry.StableSourceRay(provider,weather,mjd,ref,code,time,xyz,first['reference_clock_centre_m'])
    split=study.source_geometry.split_probe(w['columns'],probe['source_vector_m'],q)
    local=[split['wet'].get(station,0.),*split['orbit'].get(ref,[0.,0.,0.]),*split['antenna'].get(ref,[0.,0.,0.]),split['bias'].get(station+'/'+ref,0.)]
    m=len(network['blocks'][0]['rows']);stored=np.asarray(probe['physical_increment_blocks'][0])[np.arange(3)*m]
    np.testing.assert_allclose(ray.increment(local),stored,atol=1e-15,rtol=1e-12)
    projected=study.source_geometry.profiled_increment(network,probe['physical_increment_blocks'])
    replay=study.source_geometry.recover_profiled_increment(projected,w['design'],spec,np.asarray(probe['source_vector_m']),c['coupled_model_state_map'])
    assert replay['status']==probe['recovery']['physical_increment']['status']
    assert replay['injected_functional_status']==probe['recovery']['physical_increment']['injected_functional_status']
    np.testing.assert_allclose(replay['fitted_source_projection_m'],probe['recovery']['physical_increment']['fitted_source_projection_m'],atol=1e-5,rtol=1e-3)
    # Isolate arithmetic from the repaired clock derivative: old and stable
    # finite blocks pass through one frozen historical-clock projector.
    previous=json.loads(gzip.decompress((study.baseline.BASE/'results/weak_source_physical_recovery_v1.json.gz').read_bytes()))['candidates'][q]
    frozen=[]
    for stable,oldrow in zip(c['reference_rows'],previous['reference_rows'],strict=True):
        assert (stable['station'],stable['reference'],stable['time_s'])==(oldrow['station'],oldrow['reference'],oldrow['time_s'])
        frozen.append({**stable,'clock_derivative':oldrow['clock_derivative'],'code_m':oldrow['code_m'],'phase_m':oldrow['phase_m']})
    historical=study.network_clocks.fit(frozen,raw_covariance=result['raw_endpoint_weight_covariance_m2'])
    frozen_profile,frozen_work=study.source_geometry.profile_sources(historical,q,study.source_geometry.FAMILIES)
    assert frozen_profile['resolved_rank']==c['frozen_historical_clock_profile']['resolved_rank']
    oldprobe=next(p for p in previous['physical_probes'] if p['mode']=='weak' and p['source_l2_m']==.01 and p['sign']==1)
    linear=frozen_work['design']@probe['source_vector_m']
    ordinary=study.source_geometry.profiled_increment(historical,oldprobe['physical_increment_blocks'])
    stable=study.source_geometry.profiled_increment(historical,probe['physical_increment_blocks'])
    assert np.linalg.norm(ordinary-linear)>np.linalg.norm(linear)
    assert np.linalg.norm(stable-linear)<1e-3*np.linalg.norm(linear)
    assert np.linalg.norm(ordinary-linear)>1e6*np.linalg.norm(stable-linear)
    j,meta=study.source_geometry.joint_external_clock_source_design(network,w['columns'],c['clock_endpoint_keys'],.01,q,epoch_correlation=.5)
    h,count=study.source_geometry.source_measurement_design(w['columns'],('wet','antenna'),'independent')
    computed=study.source_geometry.source_information_summary(np.vstack([j,h/.01]),c['coupled_model_state_map'],c['prior_frozen_weak_direction_m_per_unit_l2_m'],profile['original_weighted_source_scale_per_m'])
    old=next(z for z in c['joint_external_clock_information'] if z['joint_clock_model']['epoch_correlation']==.5 and z['joint_clock_model']['sigma_m']==.01)['complementary_direct_source_observations']['wet_antenna']['information']
    for tol,z in computed.items():
        assert z['resolved_rank']==old[tol]['resolved_rank']
        assert z['complete_state_precision_issued']==old[tol]['complete_state_precision_issued']
        np.testing.assert_allclose(z['identified_projection_position_sigma_m'],old[tol]['identified_projection_position_sigma_m'],atol=1e-4,rtol=1e-3)
