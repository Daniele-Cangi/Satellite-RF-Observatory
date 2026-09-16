import numpy as np
import pytest

from research.exploratory import reference_ray_projection as study


def test_radial_shift_clock_sign_and_joint_cancellation(monkeypatch):
    monkeypatch.setattr(study, 'OMEGA', 0.)
    station = [6378137., 0., 0.]
    precise = [26000000., 0., 0.]
    result = study.project(station, [26000003., 0., 0.], precise, 3.)
    assert result['orbital_range_difference_m'] == 3.
    assert result['clock_range_difference_m'] == -3.
    assert result['joint_range_difference_m'] == 0.
    assert result['linear_projection_residual_m'] == 0.
    result = study.project(station, precise, precise, -2.)
    assert result['joint_range_difference_m'] == 2.


def test_transverse_displacement_keeps_second_order_range_response(monkeypatch):
    monkeypatch.setattr(study, 'OMEGA', 0.)
    distance = 20000000.
    result = study.project([6378137., 0., 0.], [6378137.+distance, 1000., 0.],
                           [6378137.+distance, 0., 0.], 0.)
    assert result['orbital_range_difference_m'] == pytest.approx(1000.**2/(2*distance), abs=1e-8)
    assert result['linear_projection_residual_m'] == result['orbital_range_difference_m']


def test_rotation_matches_independent_first_order_sagnac_and_vacuum_closure():
    station = np.array([6378137., 0., 0.])
    satellite = np.array([20000000., 15000000., 10000000.])
    result = study.project(station, satellite, satellite, 0.)
    actual = result['baseline_vacuum_flight_time_s']*study.C
    unrotated = np.linalg.norm(satellite-station)
    first_order = study.OMEGA/study.C*(satellite[0]*station[1]-satellite[1]*station[0])
    assert actual-unrotated == pytest.approx(first_order, abs=0.001)
    tau = result['baseline_vacuum_flight_time_s']
    theta = study.OMEGA*tau
    inertial_station = np.array([np.cos(theta)*station[0], np.sin(theta)*station[0], 0.])
    assert actual == pytest.approx(np.linalg.norm(satellite-inertial_station), abs=1e-7)
    assert result['joint_range_difference_m'] == 0.


@pytest.mark.parametrize('station,b,p,clock', [
    ([1., 2.], [1., 2., 3.], [1., 2., 3.], 0.),
    ([1., 2., 3.], [float('nan'), 2., 3.], [1., 2., 3.], 0.),
    ([1., 2., 3.], [1., 2., 3.], [1., 2., 3.], 0.),
    ([1., 2., 3.], [4., 5., 6.], [1., 2., 3.], float('inf')),
])
def test_invalid_rays_rejected(station, b, p, clock):
    with pytest.raises(ValueError):
        study.project(station, b, p, clock)


def test_bracket_preserves_exact_endpoints_and_rejects_extrapolation():
    assert study.bracket([0., 900., 1800.], 600., 900.) == [0., 900.]
    assert study.bracket([0., 900., 1800.], 900., 1200.) == [900., 1800.]
    with pytest.raises(ValueError):
        study.bracket([0., 900.], -1., 100.)
