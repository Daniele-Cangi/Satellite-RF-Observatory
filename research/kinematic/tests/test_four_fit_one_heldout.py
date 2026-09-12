"""Frozen boundaries for the four-fit/one-heldout topology audit."""
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.five_root_feasibility import fibonacci_directions, state_for
from research.kinematic.four_fit_one_heldout import (
    fit_response,
    load_plan,
    measurement_design,
    position_envelope,
)


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "research/kinematic/four_fit_one_heldout_plan.json"


def test_plan_binds_predecessors_and_all_five_partitions():
    plan, digest, five_plan, five_result, heldout_plan = load_plan(PLAN)
    assert len(digest) == 64
    assert five_result["synthetic_case_accounting"]["joint_visible"] == 181
    assert len(five_plan["fit_roots"]) == 5
    assert plan["root_allocation"]["partition_count"] == 5
    assert plan["root_allocation"]["fit_root_count"] == 4
    assert plan["root_allocation"]["heldout_root_count"] == 1
    assert heldout_plan["heldout_prediction"]["absolute_range_equivalent_limit_m"] == 100.0
    assert plan["selection_boundary"]["target_identifier"] is None
    assert plan["selection_boundary"]["target_date"] is None
    assert not plan["selection_boundary"]["target_orbit_or_radius_constraint"]
    assert not plan["selection_boundary"]["real_observation_values"]


def test_changed_predecessor_hash_is_rejected(tmp_path):
    plan = json.loads(PLAN.read_text())
    plan["frozen_inputs"]["five_root_result_sha256"] = "0" * 64
    changed = tmp_path / "plan.json"
    changed.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="five_root_result hash mismatch"):
        load_plan(changed)


def test_inherited_threshold_cannot_be_relaxed(tmp_path):
    plan = json.loads(PLAN.read_text())
    plan["measurement_design"]["absolute_heldout_range_equivalent_limit_m"] = 101.0
    changed = tmp_path / "plan.json"
    changed.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match="inherited measurement design differs"):
        load_plan(changed)


def test_four_root_temporal_design_and_local_response_are_finite():
    _, _, five_plan, _, _ = load_plan(PLAN)
    design = measurement_design(five_plan, 4)
    assert design["count"] == 44
    assert design["nrate"] == 40
    assert design["covariance"].shape == (104, 104)
    assert np.linalg.eigvalsh(design["covariance"]).min() > 0
    direction = fibonacci_directions(96)[27]
    motion = five_plan["synthetic_family"]["motion_templates"][1]
    state = state_for(direction, 20e6, motion)
    stations = np.asarray([row["ecef_m"] for row in five_plan["fit_roots"][:4]])
    response = fit_response(state, stations, design, five_plan)
    assert response["full_rank"]
    assert response["rank"] == response["parameter_count"] == 31
    metric = position_envelope(response, 60.0)
    assert np.isfinite(list(metric.values())).all()
    assert metric["conditional_local_position_envelope_m"] > 0
