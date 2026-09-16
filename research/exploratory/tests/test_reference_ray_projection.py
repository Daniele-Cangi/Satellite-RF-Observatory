import numpy as np
import pytest
import json
from pathlib import Path

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


@pytest.mark.parametrize('tag,archive,total,projected', [
    ('g14', 'experiments/positioning_g14_doy246_network', 294, 131),
    ('g12', 'research/exploratory/inputs/g12_doy248', 308, 132),
])
def test_saved_projection_replays_all_paths_and_signed_station_means(tag, archive, total, projected):
    root = Path(__file__).resolve().parents[3]
    inputs = root/'research/exploratory/inputs/reference_products'/tag
    saved = json.loads((root/f'research/exploratory/results/{tag}_reference_ray_projection_v1.json').read_bytes())
    result = study.run(root/archive, inputs/'reference_extract.txt', inputs/'receipt.json')
    assert result['sources_sha256'] == saved['sources_sha256']
    assert result['input_sha256'] == saved['input_sha256']
    assert result['case_count'] == len(result['rows']) == total
    assert sum(result['status_counts'].values()) == total
    assert result['status_counts']['PROJECTED'] == projected
    assert result['target'] not in result['references']
    assert not result['target_state_parsed'] and not result['applied_to_estimator']
    assert not result['qualified_error_budget']
    assert len(saved['rows']) == total
    for row, old in zip(result['rows'], saved['rows']):
        assert row.keys() == old.keys()
        for key, value in row.items():
            tolerance = (1e-13 if key == 'baseline_vacuum_flight_time_s' else
                         1e-9 if key == 'broadcast_elevation_deg' else 1e-6)
            assert old[key] == (pytest.approx(value, rel=1e-12, abs=tolerance)
                                if isinstance(value, float) else value)
        if row['status'] == 'PROJECTED':
            assert row['joint_range_difference_m'] == pytest.approx(
                row['orbital_range_difference_m']+row['clock_range_difference_m'], abs=1e-12)
    for group in result['station_epoch_projections']:
        included = [r for r in result['rows'] if r['status'] == 'PROJECTED'
                    and r['station'] == group['station'] and r['time_gpst_s'] == group['time_gpst_s']]
        assert group['references'] == [r['reference'] for r in included]
        assert group['mean_joint_range_difference_m'] == pytest.approx(
            np.mean([r['joint_range_difference_m'] for r in included]), abs=1e-12)
