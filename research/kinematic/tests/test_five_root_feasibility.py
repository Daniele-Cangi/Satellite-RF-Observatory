"""Frozen-boundary regressions for the five-root offline feasibility audit."""
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.five_root_feasibility import (
    fibonacci_directions,
    load_plan,
    measurement_design,
    minimum_elevation_deg,
    state_for,
    strict_json,
)

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/"research/kinematic/five_root_feasibility_plan.json"


def test_plan_has_exact_five_roots_and_no_target_state():
    plan, digest = load_plan(PLAN)
    assert len(digest) == 64
    assert [row["station"] for row in plan["fit_roots"]] == [
        "ALGO00CAN", "BOGT00COL", "MKEA00USA", "PIE100USA", "GOLD00USA"]
    assert plan["target_state_exclusion"] == {
        "target_identifier": None,
        "target_date": None,
        "target_orbit_or_radius_constraint": False,
        "real_target_measurements": False,
        "geometry_family": "Explicitly synthetic broad geocentric shells and deterministic directions; shells are design probes, not a target prior.",
    }


def test_duplicate_root_coordinates_are_rejected(tmp_path):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    plan["fit_roots"][1]["ecef_m"] = plan["fit_roots"][0]["ecef_m"]
    altered = tmp_path/"plan.json"
    altered.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct coordinates"):
        load_plan(altered)


def test_fibonacci_grid_and_motion_are_deterministic():
    directions = fibonacci_directions(96)
    np.testing.assert_allclose(np.linalg.norm(directions, axis=1), 1.0, atol=1e-14)
    motion = {"tangent_1_speed_m_s": 4000.0, "tangent_2_speed_m_s": 0.0,
              "inward_acceleration_m_s2": 1.0}
    first = state_for(directions[7], 20e6, motion)
    second = state_for(directions[7], 20e6, motion)
    np.testing.assert_array_equal(first, second)
    assert np.dot(first[3:6], directions[7]) == pytest.approx(0.0, abs=1e-10)
    assert np.dot(first[6:9], directions[7]) == pytest.approx(-1.0, abs=1e-12)


def test_joint_visibility_uses_every_root_and_endpoint():
    plan, _ = load_plan(PLAN)
    stations = np.asarray([row["ecef_m"] for row in plan["fit_roots"]])
    state = np.r_[2.0*stations[0], np.zeros(8)]
    elevation = minimum_elevation_deg(state, [-30.0, 0.0], stations)
    assert elevation < 0.0


def test_measurement_design_shapes_and_strict_json():
    plan, _ = load_plan(PLAN)
    design = measurement_design(plan)
    assert design["count"] == 55
    assert design["nrate"] == 50
    assert design["covariance"].shape == (130, 130)
    assert len(design["code_indices"]) == 80
    assert np.linalg.eigvalsh(design["covariance"]).min() > 0
    with pytest.raises(ValueError):
        strict_json({"bad": np.float64(np.nan)})
