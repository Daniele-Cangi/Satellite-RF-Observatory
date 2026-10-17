"""Joint source attribution, complete prediction estimability and withholding."""
from copy import deepcopy

import numpy as np
import pytest
from scipy.linalg import block_diag, solve_triangular

from research.kinematic import source_geometry as sources, network_clocks, network_closures
from research.kinematic.tests.test_source_geometry import wet_rows
from research.exploratory import reference_network_clocks as study


def rows_with_sources():
    rows=wet_rows()
    for r in rows:
        i='ABCDEF'.index(r['station']);j='WXYZ'.index(r['reference']);t=r['time_s']/300.
        r['orbit_mapping']=np.array([np.sin(t+.23*i+.2*j),np.cos(.7*t+.4*i),np.sin(.3*t+.13*i*j)])
        # Same emitted displacement in two fixed source frames: exact alias.
        r['antenna_mapping']=-r['orbit_mapping']
    columns=sources.source_columns(rows,sources.FAMILIES)
    theta=np.random.default_rng(234).normal(size=len(columns))*.01
    for r in rows:
        g=sources.source_design([r],columns)@theta
        r['code_m']+=g[0];r['phase_m']+=g[1]
    return rows,columns,theta


def test_joint_identified_fit_and_wet_precision_match_independent_dense_projection():
    rows,columns,true=rows_with_sources();rows=[r for r in rows if r['time_s']<=330.]
    raw=study.gnss_combinations.assumed_endpoint_covariance();network=network_clocks.fit(rows,raw_covariance=raw)
    result,w=sources.profile_sources(network,'TARGET',sources.FAMILIES)
    assert result['null_count']>=12 and result['wet']['resolved_rank']==6
    np.testing.assert_allclose(list(result['wet']['zenith_wet_correction_m'].values()),true[:6],atol=3e-6,rtol=0)
    # Independent dense full nuisance projection (all clocks, floats and sources).
    blocks=network['blocks'];chol=block_diag(*[b['chol'] for b in blocks])
    nuisance=np.column_stack([block_diag(*[b['a'] for b in blocks]),np.vstack([b['b'] for b in blocks]),
        np.vstack(w['designs'])[:,6:]])
    a=solve_triangular(chol,nuisance,lower=True)
    u,s,_=np.linalg.svd(a,full_matrices=False);u=u[:,s>1e-10*s[0]]
    wet=solve_triangular(chol,np.vstack(w['designs'])[:,:6],lower=True);wet-=u@(u.T@wet)
    _,s,v=np.linalg.svd(wet,full_matrices=False);cov=(v.T/s)@(v.T/s).T
    np.testing.assert_allclose(result['wet']['conditional_parameter_covariance_m2'],cov,rtol=1e-5,atol=1e-5)
    np.testing.assert_allclose(w['design']@w['null'],0.,atol=2e-9,rtol=0)
    assert not result['representative_is_physical_source_estimate']
    poisoned=deepcopy(network);poisoned['blocks'][0]['rows'][0]['reference']='TARGET'
    with pytest.raises(ValueError,match='candidate-excluding'):sources.profile_sources(poisoned,'TARGET',sources.FAMILIES)


def test_full_null_compensation_and_held_observation_poisoning():
    rows,_,_=rows_with_sources();raw=study.gnss_combinations.assumed_endpoint_covariance()
    first=network_closures.prepare_future_links(rows,'TARGET',raw,source_families=sources.FAMILIES)
    assert first['status']=='FUTURE_LINK_PREDICTIONS_FROZEN'
    predicted=[p for p in first['predictions'] if p['status']=='PREDICTED']
    assert predicted and first['source_model']['null_count']>=12
    scored=network_closures.score_future_links(first,rows)
    for lag in scored['increment_errors']:
        assert lag['count']>0
        np.testing.assert_allclose(lag['code_phase_rms_error_m'],0.,atol=3e-6,rtol=0)
    changed=deepcopy(rows);held=set(first['held_links'])
    class Forbidden:
        def __float__(self):raise AssertionError('withheld source-training value read')
    for r in changed:
        if (r['station'],r['reference']) in held and r['time_s']>first['training_stop_s']:
            r['code_m']=r['phase_m']=r['geometry_free_phase_m']=Forbidden();r['segment']='held GF forbidden'
    assert study.native(first)==study.native(network_closures.prepare_future_links(changed,'TARGET',raw,source_families=sources.FAMILIES))
    # Break a held APC mapping along an exact training orbit/antenna alias.
    for r in changed:
        if (r['station'],r['reference']) in held and r['time_s']>first['training_stop_s']:
            r['antenna_mapping']=r['antenna_mapping']+np.array([.1,0.,0.])
    failed=network_closures.prepare_future_links(changed,'TARGET',raw,source_families=sources.FAMILIES)
    assert any(p['status']=='UNIDENTIFIABLE_SOURCE_PREDICTION' for p in failed['predictions'])
    assert not any(p['status']=='PREDICTED' for p in failed['predictions'])


def test_wet_alias_with_reference_shape_is_retained_without_wet_correction():
    rows,_,_=rows_with_sources()
    for r in rows:r['wet_mapping']=r['orbit_mapping'][0]+3.
    network=network_clocks.fit(rows,raw_covariance=study.gnss_combinations.assumed_endpoint_covariance())
    # A station-independent orbit column need not absorb all station wet
    # coordinates; the common wet functional is nevertheless unidentifiable.
    for r in rows:r['orbit_mapping'][0]=r['wet_mapping']
    network=network_clocks.fit(rows,raw_covariance=study.gnss_combinations.assumed_endpoint_covariance())
    result,_=sources.profile_sources(network,'TARGET',('wet','orbit','bias'))
    assert result['wet']['status']=='WET_SOURCE_UNIDENTIFIABLE'
    assert result['wet']['resolved_rank']<6
    assert 'zenith_wet_correction_m' not in result['wet']
