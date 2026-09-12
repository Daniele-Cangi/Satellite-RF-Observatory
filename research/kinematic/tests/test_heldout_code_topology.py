"""Boundary and numerical tests for the target-free code-heldout topology audit."""
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic.five_root_feasibility import (
    fibonacci_directions, measurement_design, state_for)
from research.kinematic.heldout_code_topology import (
    fit_response, heldout_code_metric, load_plan)

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/"research/kinematic/heldout_code_topology_plan.json"


def test_plan_binds_closed_result_and_forbids_target_or_access():
    plan, digest, five_plan, five_result = load_plan(PLAN)
    assert len(digest) == 64
    assert five_result["status"] == "FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE"
    assert [row["station"] for row in plan["candidate_roots"]] == [
        "DRAO00CAN", "STJO00CAN", "YELL00CAN"]
    assert all(row["code_capability_status"] == "UNKNOWN_NOT_ACCESSED"
               for row in plan["candidate_roots"])
    assert plan["selection_boundary"]["target_identifier"] is None
    assert plan["selection_boundary"]["target_date"] is None
    assert not plan["selection_boundary"]["candidate_artifact_access"]
    assert not plan["selection_boundary"]["target_orbit_or_radius_constraint"]
    assert len(five_plan["fit_roots"]) == 5


def test_phase_failure_fields_are_not_required_by_code_contract():
    plan, *_ = load_plan(PLAN)
    excluded = plan["code_coordinate_contract"]["not_required_for_code_only_holdout"]
    assert "carrier-phase scale or phase-shift qualification" in excluded
    assert "LLI" in excluded
    assert plan["code_coordinate_contract"]["core"] == ["C1C", "C2W"]


def test_altered_predecessor_hash_is_rejected(tmp_path):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    plan["frozen_inputs"]["five_root_result_sha256"] = "0"*64
    altered = tmp_path/"plan.json"
    altered.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError, match="result hash mismatch"):
        load_plan(altered)


def test_heldout_metric_is_finite_and_preserves_unresolved_slack():
    plan, _, five_plan, _ = load_plan(PLAN)
    direction = fibonacci_directions(96)[27]
    motion = next(row for row in five_plan["synthetic_family"]["motion_templates"]
                  if row["name"] == "negative_tangent_1_4kms_inward_1")
    state = state_for(direction, 12e6, motion)
    stations = np.asarray([row["ecef_m"] for row in five_plan["fit_roots"]])
    response = fit_response(state, stations, measurement_design(five_plan), five_plan)
    heldout = np.asarray(plan["candidate_roots"][0]["ecef_m"])
    metric = heldout_code_metric(state, heldout, 60.0, response, plan)
    assert np.isfinite(list(metric.values())[:-1]).all()
    assert metric["conditional_gaussian_halfwidth95_m"] > 0
    assert isinstance(metric["positive_physical_slack"], bool)
