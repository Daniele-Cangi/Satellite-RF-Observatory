from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_doy233_integrated_primary_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> dict[str, object]:
    value = json.loads(
        (ROOT / name).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    assert isinstance(value, dict)
    return value


def test_written_artifacts_match_deterministic_compiler() -> None:
    bundle, reveal = plan.build_prediction_artifacts(ROOT)
    compiled = plan.build_plan(ROOT)

    assert load(plan.BUNDLE_NAME) == bundle
    assert load(plan.REVEAL_NAME) == reveal
    assert load(plan.PLAN_NAME) == compiled
    assert compiled["frozen_artifacts"][plan.BUNDLE_NAME] == plan.object_sha256(bundle)
    assert compiled["frozen_artifacts"][plan.REVEAL_NAME] == plan.object_sha256(reveal)


def test_opaque_bundle_contains_no_satellite_identity() -> None:
    bundle = load(plan.BUNDLE_NAME)
    rendered = plan.strict_json(bundle)

    assert not any(code in rendered for code in plan.MODEL_CODES)
    assert bundle["identity_available_to_scorer"] is False
    assert len(bundle["opaque_model_curves_m"]) == 6
    assert all(len(values) == 139 for values in bundle["opaque_model_curves_m"].values())


def test_plan_freezes_physical_surface_without_artifact_selection() -> None:
    compiled = load(plan.PLAN_NAME)
    candidate = compiled["candidate"]
    admission = compiled["admission_before_score"]

    assert compiled["new_gate"] is False
    assert candidate["artifact_selected"] is False
    assert candidate["logical_product"] is None
    assert candidate["locator"] is None
    assert candidate["complete_artifact_sha256"] is None
    assert candidate["observation_access_authorized"] is False
    assert admission["complete_opaque_track_count"] == 7
    assert admission["same_path_witness"]["six_track_subsets_evaluated"] == 7
    assert admission["same_path_witness"]["every_possible_included_track_must_pass"] is True
    assert not any(compiled["access_at_freeze"].values())


def test_plan_preserves_heldout_and_null_symmetry() -> None:
    compiled = load(plan.PLAN_NAME)
    bundle = load(plan.BUNDLE_NAME)
    surface = bundle["surface"]

    assert compiled["candidate"]["window"]["prefix_epochs"] == 79
    assert compiled["candidate"]["window"]["heldout_epochs"] == 60
    assert surface["orbital_hypotheses"] == 5_040
    assert surface["time_reversed_geometry_nulls"] == 5_040
    assert surface["prefix_affine_nulls"] == 7
    assert compiled["nulls"]["same_calibration_and_heldout"] is True
    assert compiled["retry"]["after_complete_hash"] == 0


def test_track_blinding_is_deterministic_and_collision_free_for_gps_domain() -> None:
    identifiers = [plan.opaque_track_id(f"G{prn:02d}") for prn in range(1, 33)]

    assert len(set(identifiers)) == 32
    assert all(identifier.startswith("T_") and len(identifier) == 18 for identifier in identifiers)


def test_changed_frozen_input_is_refused(tmp_path: Path) -> None:
    for name in (
        plan.REVIEW_NAME,
        plan.MODEL_NAME,
        plan.CLUTTER_PLAN_NAME,
        plan.SCORER_NAME,
    ):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    (tmp_path / plan.MODEL_NAME).write_text("{}", encoding="ascii")

    with pytest.raises(plan.PlanError, match="FROZEN_INPUT_CHANGED"):
        plan.build_plan(tmp_path)
