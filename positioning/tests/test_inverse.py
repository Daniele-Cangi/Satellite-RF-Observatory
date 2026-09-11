from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import numpy as np
import pytest

from positioning.context import Context
from positioning.calibration import C, state_and_clock, strip_target_navigation, parse_reference_navigation
from positioning.qualification import scan_structure, select_window
from positioning.solver import solve, measurement_model, interpolate_event


@pytest.mark.parametrize('target',['G08','G12','G32'])
def test_target_poison_or_removal_leaves_admitted_navigation_identical(target):
    header=f"{'':60}END OF HEADER\n"
    excluded=target+' NOT NUMBERS\n'+'    poison\n'*7
    kept='G01 reference\n'+'    keep\n'*7
    assert strip_target_navigation(header+excluded+kept,target)==strip_target_navigation(header+kept,target)
    with pytest.raises(ValueError,match='target navigation'):
        parse_reference_navigation(header+excluded,target)


def circular_record():
    return SimpleNamespace(satellite='G01',gps_week=2435,toe_sow=0.,sqrt_a_m_sqrt=np.sqrt(26000000.),m0_rad=0.,delta_n_rad_s=0.,eccentricity=0.,argument_perigee_rad=0.,cus_rad=0.,cuc_rad=0.,crs_m=0.,crc_m=0.,i0_rad=0.,idot_rad_s=0.,cis_rad=0.,cic_rad=0.,omega0_rad=0.,omega_dot_rad_s=0.,toc_gps=Context('G12','2026-09-06').day,af0_s=.001,af1_s_s=1e-10,af2_s_s2=0.)


@pytest.mark.parametrize('days',[1,6,7])
def test_same_physical_time_across_day_and_gps_week_boundaries(days):
    from datetime import timedelta
    first=Context('G12','2026-09-06')
    second=Context('G12',(first.day+timedelta(days=days)).date().isoformat())
    record=circular_record()
    x0,c0=state_and_clock(record,days*86400+10,first)
    x1,c1=state_and_clock(record,10,second)
    np.testing.assert_allclose(x0,x1,atol=1e-8,rtol=0)
    assert c0==c1
    assert second.gps_week==2435+days//7


def test_configured_target_cannot_be_propagated():
    record=circular_record();record.satellite='G12'
    with pytest.raises(ValueError,match='forbidden'):
        state_and_clock(record,0,Context('G12','2026-09-07'))


def test_new_target_and_date_structure_remains_value_blind():
    from experiments.gnss_inverse_positioning.tests.test_qualification import rinex
    content=rinex().replace('2026 09 06','2026 09 07').replace('G08','G12')
    first=scan_structure(content,'G12','2026-09-07')
    second=scan_structure(content.replace('12345678.125','99999999.999'),'G12','2026-09-07')
    assert first==second and first['eligible_epoch_count']==1
    with pytest.raises(ValueError,match='date'):
        scan_structure(content,'G12','2026-09-06')


def test_support_window_never_bridges_a_missing_epoch():
    times=list(range(0,1200,30))+list(range(3000,4230,30))
    structures={n:{'epochs':[{'seconds_gpst':str(t),'eligible':True} for t in times]} for n in ['a','b']}
    selected=select_window(structures,41,30)['selected_seconds_gpst']
    assert selected[0]=='3000' and selected[-1]=='4200'


def test_seven_roots_recover_position_and_clock_without_orbital_seed():
    stations=np.array([[0.,0.,0.],[3e6,0,0],[0,4e6,0],[0,0,5e6],[-3e6,-2e6,1e6],[2e6,-4e6,0],[-2e6,3e6,-1e6]])
    truth=np.array([18e6,8e6,12e6,-345678.])
    observed=measurement_model(truth,stations,False)
    fit=solve(observed,stations,np.eye(7)*400,False)
    np.testing.assert_allclose(fit['q'],truth,atol=.001,rtol=0)


def test_independent_clock_changes_preserve_emitted_event():
    p=np.full((7,13),23000000.);clock=np.zeros_like(p)
    stations=np.array([[6370000.,100.*i,100.*i] for i in range(7)])
    times=np.arange(-180.,181.,30.)
    baseline=interpolate_event(p,clock,stations,times_s=times)
    offsets=np.arange(7)[:,None]*123456.
    changed=interpolate_event(p+offsets,clock+offsets,stations,time_offsets=offsets/C,times_s=times)
    assert abs(changed['u0']-baseline['u0'])<1e-13
    np.testing.assert_allclose(changed['z'],baseline['z'],atol=1e-7,rtol=0)
    np.testing.assert_allclose(changed['positions'],baseline['positions'],atol=1e-7,rtol=0)


def test_frozen_g08_position_unchanged_by_active_extraction():
    root=Path(__file__).resolve().parents[2]
    inp=json.loads((root/'experiments/gnss_inverse_positioning/event_2026249/frozen_solver_input.json').read_text())
    event=interpolate_event(inp['target_if_codes_m'],inp['receiver_clocks_m'],inp['station_ecef_m'])
    fit=solve(event['z'],event['positions'],np.array(inp['covariance_z_m2']))
    np.testing.assert_allclose(fit['q'],[5108535.290482933,-25703109.672031112,1963414.01644314,-106067.69157968106],atol=.001,rtol=0)


def test_coplanar_range_difference_rank_failure_is_explicit():
    stations=np.array([[0.,0.,0.],[1e6,0,0],[0,1e6,0],[1e6,1e6,0],[2e6,0,0]])
    truth=np.array([3e6,4e6,20e6,0.])
    with pytest.raises(ValueError,match='rank deficient'):
        solve(measurement_model(truth,stations,False),stations,np.eye(5),False)
