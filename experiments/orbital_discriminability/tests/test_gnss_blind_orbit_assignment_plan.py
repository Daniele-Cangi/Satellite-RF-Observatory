"""Offline tests for the frozen bounded blind-orbit prospective plan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


def test_plan_binds_frozen_parents_and_never_opens_the_primary() -> None:
    value = plan.plan(ROOT)

    assert value["outcome"] == "BLIND_ORBIT_ASSIGNMENT_PLAN_FROZEN"
    assert value["parents"][plan.SCREEN_NAME] == {
        "canonical_sha256": plan.SCREEN_SHA256,
        "outcome": "BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED",
        "role": "FROZEN_ORBIT_ONLY_DIFFICULT_FAMILY_SELECTION",
    }
    assert value["parents"][plan.MAPPING_NAME]["canonical_sha256"] == (
        plan.MAPPING_SHA256
    )
    assert value["parents"][plan.PLAN_NAME]["canonical_sha256"] == (
        plan.PLAN_SHA256
    )
    assert value["access_boundary"] == {
        "network_requests": 0,
        "product_locators_queried": 0,
        "primary_headers_opened": 0,
        "primary_payload_bytes": 0,
        "primary_observation_values": 0,
        "measurement_scores": 0,
        "prediction_bundle_present": False,
        "scorer_present": False,
        "executor_present": False,
        "execution_authority": False,
    }


def test_one_unknown_product_and_no_fallback_are_frozen() -> None:
    artifact = plan.plan(ROOT)["primary_artifact"]

    assert artifact["logical_product"] == plan.PRIMARY_PRODUCT
    assert artifact["product_existence"] == "UNKNOWN_UNQUERIED"
    assert artifact["directory_metadata_queried"] is False
    assert artifact["complete_sha256"] == (
        "UNKNOWN_UNTIL_ONE_AUTHORIZED_MATERIALIZATION"
    )
    assert artifact["fallback_product_date_station_window_or_archive"] is False
    assert artifact["predeclared_body_transport"]["maximum_attempts_before_complete_hash"] == 2
    assert artifact["predeclared_body_transport"]["retry_after_complete_hash_or_decode"] is False


def test_mapping_is_complete_unique_and_interface_blind() -> None:
    mapping, opaque_ids = plan._validate_mapping(ROOT / plan.MAPPING_NAME)
    value = plan.plan(ROOT)

    assert len(opaque_ids) == 6
    assert len(set(opaque_ids)) == 6
    assert set(value["mapping_seal"]["opaque_ids"]) == set(opaque_ids)
    assert value["mapping_seal"]["mapping_rows_exposed_in_plan_receipt"] is False
    assert value["mapping_seal"]["mapping_may_enter_scorer_process"] is False
    assert mapping["blindness_semantics"]["state"] == (
        "INTERFACE_BLINDNESS_NOT_REPOSITORY_SECRECY"
    )


def test_scorer_surface_contains_no_identity_or_decoder_input() -> None:
    value = plan.plan(ROOT)
    scorer = value["scorer_contract"]
    scorer_json = plan.strict_json(scorer)

    assert scorer["inputs"] == [
        "FINITE_UNLABELLED_OBSERVED_COORDINATE_139",
        "SIX_OPAQUE_MODEL_ARRAYS_139",
        "PREFIX_AND_HELDOUT_INDICES",
        "PAIRWISE_GUARD_M",
    ]
    assert "G22" not in scorer_json
    assert "G30" not in scorer_json
    assert plan.MAPPING_NAME not in scorer_json
    assert scorer["per_hypothesis_parameter_count"] == 2
    assert scorer["per_hypothesis_prefix_fit"] == ["CONSTANT", "LINEAR_RATE"]
    assert scorer["affine_null_model_array"] == "ZERO_ARRAY_IDENTICAL_INTERFACE"
    assert scorer["heldout_refit"] is False
    assert scorer["free_time_phase"] is False
    assert scorer["candidate_dependent_complexity"] is False


def test_partition_and_detectability_are_exactly_inherited() -> None:
    value = plan.plan(ROOT)

    assert value["partition"] == {
        "time_system": "GPS",
        "raw_start": plan.RAW_START_GPS,
        "raw_stop": plan.RAW_STOP_GPS,
        "raw_epochs": 139,
        "cadence_s": 30.0,
        "anchor_index": 0,
        "prefix_raw_indices_inclusive": [0, 78],
        "prefix_epochs": 79,
        "heldout_raw_indices_inclusive": [79, 138],
        "heldout_start": plan.HELDOUT_START_GPS,
        "heldout_epochs": 60,
        "window_shortening_interpolation_gap_bridging": "FORBIDDEN",
    }
    assert value["detectability"]["pairwise_guard_m"] == pytest.approx(
        7_339.701234647398
    )
    assert value["detectability"]["minimum_combined_remaining_margin_m"] == (
        pytest.approx(11_424.01533014155)
    )
    assert value["detectability"]["complete_window_required"] is True


def test_tampered_mapping_is_rejected_before_plan_compilation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping = json.loads((ROOT / plan.MAPPING_NAME).read_text(encoding="utf-8"))
    mapping["mapping"][1]["opaque_id"] = mapping["mapping"][0]["opaque_id"]
    monkeypatch.setattr(plan, "_read_strict_json", lambda _: mapping)

    with pytest.raises(plan.BlindOrbitPlanError, match="OPAQUE_IDENTIFIERS_INVALID"):
        plan._validate_mapping(Path("UNUSED_BY_PATCH"))


def test_strict_json_rejects_nonfinite_numbers() -> None:
    with pytest.raises(ValueError):
        plan.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        plan.strict_json({"bad": float("inf")})


def test_plan_manifest_is_deterministic() -> None:
    first = plan.plan_manifest_sha256(ROOT)
    second = plan.plan_manifest_sha256(ROOT)

    assert len(first) == 64
    assert first == second
