from types import SimpleNamespace
import numpy as np
import pytest
from experiments.gnss_inverse_positioning.calibration import strip_target_navigation, parse_reference_navigation, state_and_clock, DAY
from experiments.gnss_inverse_positioning.solver import solve, measurement_model, interpolate_event


def test_target_navigation_can_be_poisoned_or_removed_without_changing_admitted_input():
    header = f"{'':60}END OF HEADER\n"
    target = "G08 POISONED TARGET STATE\n" + "    secret\n" * 7
    reference = "G01 REFERENCE\n" + "    retained\n" * 7
    assert strip_target_navigation(header + target + reference) == strip_target_navigation(header + reference)
    with pytest.raises(ValueError, match="target navigation"):
        parse_reference_navigation(header + target)


def test_reference_circular_orbit_and_clock_closed_form():
    record = SimpleNamespace(satellite="G01", toe_sow=0., sqrt_a_m_sqrt=np.sqrt(26000000.), m0_rad=0., delta_n_rad_s=0., eccentricity=0., argument_perigee_rad=0., cus_rad=0., cuc_rad=0., crs_m=0., crc_m=0., i0_rad=0., idot_rad_s=0., cis_rad=0., cic_rad=0., omega0_rad=0., omega_dot_rad_s=0., toc_gps=DAY, af0_s=0.001, af1_s_s=0., af2_s_s2=0.)
    x, clock = state_and_clock(record, 0.)
    np.testing.assert_allclose(x, [26000000., 0., 0.], atol=1e-8)
    assert clock == .001
    record.satellite = "G08"
    with pytest.raises(ValueError, match="forbidden"):
        state_and_clock(record, 0.)


def test_inverse_recovers_invented_position_with_large_unknown_clock_without_orbit_seed():
    stations = np.array([[0.,0.,0.], [3e6,0,0], [0,4e6,0], [0,0,5e6], [-3e6,-2e6,1e6]])
    truth = np.array([18e6, 8e6, 12e6, 234567.])
    z = measurement_model(truth, stations, atmosphere=False)
    fit = solve(z, stations, np.eye(5) * 400., atmosphere=False)
    np.testing.assert_allclose(fit["q"], truth, atol=.001, rtol=0)
    shifted = solve(z + 900000., stations, np.eye(5) * 400., atmosphere=False)
    np.testing.assert_allclose(shifted["q"][:3], truth[:3], atol=.001, rtol=0)
    assert abs(shifted["q"][3] - truth[3] - 900000.) < .001


def test_consistent_receiver_clock_change_leaves_xyz_inputs_invariant():
    p = np.full((5,11), 23000000.)
    clocks = np.zeros_like(p)
    stations = np.array([[6370000.,100.*i,100.*i] for i in range(5)])
    base = interpolate_event(p, clocks, stations)
    from experiments.gnss_inverse_positioning.calibration import C
    offsets = np.arange(5)[:, None] * 120000.
    changed = interpolate_event(p + offsets, clocks + offsets, stations, time_offsets=offsets/C)
    assert abs(changed["u0"] - base["u0"]) < 1e-14
    np.testing.assert_allclose(changed["z"], base["z"], atol=1e-8)
    np.testing.assert_allclose(changed["positions"], base["positions"], atol=1e-8)


def test_nonmonotone_emission_tags_reject_instead_of_time_warping():
    p = np.full((5,11), 23000000.)
    p[0,6] += 1e11
    with pytest.raises(ValueError, match="monotonically"):
        interpolate_event(p, np.zeros_like(p), np.zeros((5,3)))
