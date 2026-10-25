"""Retained physical-operator design, immutable provenance and numerical replay."""
from collections import Counter
import gzip,hashlib,json,subprocess
import numpy as np
from research.exploratory import reference_network_clocks as study

PRODUCER='d71c322d19a6b77832e53bd6d422a3f588a768d6'
RESULT_SHA256='510327524edba59d8face5a081e8aecd3d0b600d5db2f6c655ad0497987a480b'


def test_physical_observable_receipt_keeps_real_operator_and_calibration_boundaries():
    payload=(study.baseline.BASE/'results/physical_observable_operators_v1.json.gz').read_bytes()
    assert hashlib.sha256(payload).hexdigest()==RESULT_SHA256
    subprocess.run(['git','merge-base','--is-ancestor',PRODUCER,'HEAD'],cwd=study.baseline.BASE.parents[1],check=True,capture_output=True)
    result=json.loads(gzip.decompress(payload));raw,data=study.baseline.read_inputs()
    assert result['input_sha256']=={k:hashlib.sha256(v).hexdigest() for k,v in raw.items()}
    for path,wanted in result['source_sha256'].items():
        source=subprocess.check_output(['git','show',PRODUCER+':'+path],cwd=study.baseline.BASE.parents[1])
        assert hashlib.sha256(source).hexdigest()==wanted
    for name,wanted in result['prior_sha256'].items():
        assert hashlib.sha256((study.baseline.BASE/'results'/name).read_bytes()).hexdigest()==wanted
    parent=json.loads(gzip.decompress((study.baseline.BASE/'results/stable_source_differential_v1.json.gz').read_bytes()))
    assert result['schema']=='exposed-physical-observable-operators-v1'
    assert result['information_target_is_fixed_nominal_rf_sensitivity_not_joint_state_covariance']
    assert result['range_is_conditional_flat_spacetime_rigid_earth_operator_not_slr_processing']
    assert not any(result[k] for k in ('candidate_products_used_in_own_network','candidate_rf_used_in_own_network',
        'new_rf_trajectory_fits','new_rf_or_mw_scoring','candidate_code_orbit_scoring','physical_covariance_qualified',
        'production_floors_changed','independent_measurements_admitted','g12_state_accessed','new_confirmation',
        'equipment_support_qualified','new_source_or_calibration_values_estimated'))
    candidates=result['candidates'];assert set(candidates)==set(parent['candidates'])==set(data['plan']['references'])
    assert sum(len(c['windows']) for c in candidates.values())==440
    assert sum(c['prepared_arc_count'] for c in candidates.values())==63
    assert dict(Counter(c['status'] for c in candidates.values()))==result['status_counts']
    assert dict(Counter(c['archived_nominal_fit_status'] for c in candidates.values()))==result['archived_nominal_fit_status_counts']
    specs=result['case_specifications'];assert len(specs)==212
    assert specs==study.native(study.source_geometry.physical_observable_case_specs())
    total=0;supported=[]
    for q,c in candidates.items():
        old=parent['candidates'][q]
        assert c['windows']==old['windows'] and c['prepared_arc_count']==old['prepared_arc_count']
        assert c['archived_nominal_fit_status']==old['archived_nominal_fit_status']
        if 'source_profile' not in old:
            assert c['status']=='INSUFFICIENT_PREPARED_ARCS';continue
        supported.append(q)
        assert c['status']=='PHYSICAL_OBSERVABLE_OPERATORS_PREPARED',c.get('reason')
        assert c['source_profile_is_unchanged_archive'] and c['source_profile']==old['source_profile']
        assert c['reference_matrix_replay_rank']==old['source_profile']['resolved_rank']
        np.testing.assert_array_equal(c['coupled_model_state_map'],old['coupled_model_state_map'])
        scheduled={(r['station'],r['reference'],r['time_s']) for r in old['reference_rows'] if r['time_s']%300==0}
        ranges=c['range_geometry_terminals']
        assert len(ranges)==len(scheduled) and {(r['station'],r['reference'],r['time_s']) for r in ranges}==scheduled
        assert all(r['reference']!=q for r in ranges)
        assert dict(Counter(r['status'] for r in ranges))==c['range_geometry_status_counts']
        for r in ranges:
            if r['status']=='TWO_WAY_GEOMETRY_FAILED':assert r['reason']
            else:
                assert r['status']=='TWO_WAY_GEOMETRY_PREPARED'
                assert not r['geometry']['equipment_or_independent_measurement_available']
        cat=c['observable_catalog'];h=np.asarray(cat['source_design']);b=np.asarray(cat['nuisance_design'])
        assert h.shape==(len(cat['readouts']),len(c['source_columns'])) and b.shape==(len(h),len(cat['nuisance_columns']))
        assert np.isfinite(h).all() and np.isfinite(b).all()
        assert cat['shared_origin_in_range_and_antenna'] and cat['hardware_components_not_direct_total_link_observations']
        assert cat['equipment_and_calibration_availability']=='NOT_ESTABLISHED' and not cat['independent_values_admitted']
        assert sum(r['family']=='range' for r in cat['readouts'])==sum(r['status']=='TWO_WAY_GEOMETRY_PREPARED' for r in ranges)
        assert sum(r['family']=='wet' for r in cat['readouts'])==len({(s,t) for s,r,t in scheduled})
        assert sum(r['family']=='antenna' for r in cat['readouts'])==6*len({r['reference'] for r in old['reference_rows']})
        gap=c['hardware_component_gap']
        assert gap['profiled_component_information_on_total_link_bias_rank']==0
        assert not gap['perfect_component_calibration_removes_link_remainder'] and not gap['component_values_admitted']
        assert gap['unrestricted_link_remainder_count']==sum(col[0]=='bias' for col in c['source_columns'])
        cases=c['operator_cases'];total+=len(cases);assert [z['specification'] for z in cases]==specs
        assert dict(Counter(z['status'] for z in cases))==c['operator_case_status_counts']
        for z in cases:
            assert z['status'] in ('PHYSICAL_OPERATOR_INFORMATION_EVALUATED','PHYSICAL_OPERATOR_CASE_FAILED')
            if z['status']=='PHYSICAL_OPERATOR_CASE_FAILED':assert z['reason'];continue
            assert not z['equipment_and_independence_qualified'] and not z['physical_covariance_qualified']
            assert z['calibration']['frequency_differences_remain_free'] and not z['calibration']['calibration_values_admitted']
            for tol,info in z['information'].items():
                assert info['absolute_singular_cut']==float(tol)*old['source_profile']['original_weighted_source_scale_per_m']
                if not info['complete_state_precision_issued']:assert not info['meets_1m_1mm_s_design_benchmark']
            if 'unresolved_direction' in z and z['unresolved_direction']['status']=='UNRESOLVED_DIRECTION_DIAGNOSTIC':
                d=z['unresolved_direction'];direction=np.asarray(d['source_direction_unit_l2'])
                assert np.linalg.norm(direction)>1-1e-12 and np.linalg.norm(direction)<1+1e-12
                np.testing.assert_allclose(np.asarray(c['coupled_model_state_map'])@direction*.01,d['local_state_change_m_m_s_at_1cm'],atol=1e-12,rtol=1e-12)
                assert d['algebraic_alias_is_not_a_physical_estimate']
    assert supported==['G05','G11','G19','G20','G21'] and total==1060
    # One adverse fold: reconstitute a real geometry row from raw admitted
    # products, the catalog and conditional information under both level laws.
    q='G19';c=candidates[q];old=parent['candidates'][q]
    provider,_=study.baseline.subset_products(data,[r for r in data['plan']['references'] if r!=q],q)
    r=next(r for r in c['range_geometry_terminals'] if r['status']=='TWO_WAY_GEOMETRY_PREPARED')
    xyz=np.asarray(data['positions'][r['station']][int((r['time_s']-36000)/30)],float)
    geometry=study.reference_geometry.two_way_range_geometry(provider,r['reference'],r['time_s']-.1,xyz)
    for field in ('orbit_mapping','body_mapping','optical_zenith_mapping','epoch_light_time_mapping','range_scale_mapping','vacuum_half_roundtrip_m'):
        np.testing.assert_allclose(geometry[field],r['geometry'][field],atol=1e-12,rtol=1e-12)
    catalog=study.source_geometry.complementary_observable_catalog(old['reference_rows'],c['source_columns'],c['range_geometry_terminals'],q)
    assert catalog['readouts']==c['observable_catalog']['readouts']
    np.testing.assert_array_equal(catalog['source_design'],c['observable_catalog']['source_design'])
    np.testing.assert_array_equal(catalog['nuisance_design'],c['observable_catalog']['nuisance_design'])
    network=study.network_clocks.fit(old['reference_rows'],raw_covariance=result['raw_endpoint_weight_covariance_m2'])
    blocks=[study.source_geometry.source_design(b['rows'],c['source_columns'],len(b['y'])//len(b['rows'])) for b in network['blocks']]
    reference=study.source_geometry.profiled_increment(network,blocks)
    for mode in ('relative','anchored_relative'):
        case=next(z for z in c['operator_cases'] if z['specification']['purpose']=='full_physical_readout_design' and
            z['specification']['observation_sigma_m']==.01 and z['specification']['rho']==.5 and
            z['specification']['calibration_mode']==mode and z['specification']['calibration_sigma_m']==.001)
        h,b,keys,noise=study.source_geometry.whiten_observable_catalog(catalog,('range','wet','antenna'),.5)
        extra,meta=study.source_geometry.profile_observable_calibration(h,b,keys,.01,mode,.001)
        replay=study.source_geometry.source_information_summary(np.vstack([reference,extra]),c['coupled_model_state_map'],c['prior_frozen_weak_direction_m_per_unit_l2_m'],c['source_profile']['original_weighted_source_scale_per_m'])
        for tol,z in replay.items():
            expected=case['information'][tol];assert z['resolved_rank']==expected['resolved_rank']
            assert z['complete_state_precision_issued']==expected['complete_state_precision_issued']
            assert z['meets_1m_1mm_s_design_benchmark']==expected['meets_1m_1mm_s_design_benchmark']
            np.testing.assert_allclose(z['identified_projection_position_sigma_m'],expected['identified_projection_position_sigma_m'],atol=1e-4,rtol=1e-3)
