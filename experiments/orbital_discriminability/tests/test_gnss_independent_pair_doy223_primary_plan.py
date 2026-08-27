from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_primary_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


def test_sources_bind_selected_geometry_and_prior_qualification() -> None:
    screen, qualification = plan.verify_sources(ROOT)

    assert screen["outcome"] == "NEXT_PRIMARY_GEOMETRY_SELECTED"
    assert screen["selected"]["doy"] == 223
    assert qualification["outcome"] == (
        "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
    )


def test_primary_window_products_and_roots_are_frozen_without_access() -> None:
    frozen = plan.plan()
    primary = frozen["roles"]["primary"]

    assert primary["stations"] == ["ALGO00CAN", "MDO100USA"]
    assert primary["candidate_station_roots"] == [
        "ALGO00CAN_40104M002",
        "MDO100USA_40442M012",
    ]
    assert primary["raw_start_gps"] == "2026-08-11T05:24:00 GPS"
    assert primary["raw_stop_gps"] == "2026-08-11T06:33:00 GPS"
    assert primary["heldout_start_gps"] == "2026-08-11T06:03:00 GPS"
    assert [item["name"] for item in primary["products"]] == [
        "ALGO00CAN_R_20262230000_01D_30S_MO.crx.gz",
        "MDO100USA_R_20262230000_01D_30S_MO.crx.gz",
    ]
    assert all(len(item["mirrors"]) == 2 for item in primary["products"])
    assert all(item["complete_sha256"] is None for item in primary["products"])
    assert frozen["roles"]["fallback_or_reserve"] is None
    assert not any(frozen["access_at_freeze"].values())


def test_partition_coordinate_geometry_and_nulls_are_immutable() -> None:
    frozen = plan.plan()

    assert frozen["partition"] == {
        "step_s": 30,
        "raw_epochs": 139,
        "feature_epochs": 137,
        "calibration_epochs": 77,
        "heldout_epochs": 60,
        "feature_raw_indices_inclusive": [1, 137],
        "calibration_raw_indices_inclusive": [1, 77],
        "heldout_raw_indices_inclusive": [78, 137],
    }
    assert frozen["coordinate"]["order"] == (
        "(ALGO_G22_MINUS_ALGO_G30)_MINUS_(MDO1_G22_MINUS_MDO1_G30)"
    )
    assert frozen["hypotheses"]["wrong_orbits"] == ["G01", "G14", "G17"]
    assert frozen["scoring"]["suffix_refit"] is False
    assert frozen["scoring"]["free_time_phase"] is False
    assert frozen["scoring"]["screen_controlling_null"] == "WRONG_ORBIT_G14"
    assert frozen["scoring"]["screen_controlling_separation_m"] == pytest.approx(
        54_990.701676848694
    )
    assert frozen["scoring"]["pairwise_decision_guard_m"] == pytest.approx(
        3_142.1641485601226
    )
    assert frozen["scoring"]["remaining_physical_margin_m"] == pytest.approx(
        51_848.53752828857
    )


def test_transport_retry_exists_only_before_complete_hash_and_decode() -> None:
    transport = plan.plan()["transport_materialization"]

    assert transport["state_before_complete_hash"] == "MATERIALIZING"
    assert transport["max_attempts_per_mirror"] == 2
    assert transport["max_total_attempts_per_product"] == 4
    assert transport["maximum_wall_clock_s_per_product"] == 900
    assert transport["resume_allowed"] is True
    assert transport["resume_requires_same_mirror_and_stable_validator"] is True
    assert transport["cross_mirror_partial_append"] is False
    assert transport["complete_hash_before_header_or_decode"] is True
    assert transport["network_attempts_after_both_complete_hashes"] == 0
    assert transport["retry_after_header_or_decode_begins"] is False
    assert transport["retry_after_measurement_admission"] is False
    assert transport["scientific_retry_or_second_window"] is False


def test_materialization_failure_is_not_a_measurement_or_orbital_outcome() -> None:
    outcomes = plan.plan()["outcomes"]

    assert "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED" in outcomes
    assert "MEASUREMENT_INVALID" in outcomes
    assert outcomes.index("PRIMARY_ARTIFACT_MATERIALIZATION_FAILED") < outcomes.index(
        "MEASUREMENT_INVALID"
    )
    assert "ORBITAL_MODEL_PREDICTIVELY_PREFERRED" in outcomes


def test_plan_is_strict_json_and_stops_before_observation_request() -> None:
    frozen = plan.plan()

    assert frozen["next_maximum"] == (
        "OFFLINE_EXACT_HASH_DOY223_PREDICTION_SEAL_BEFORE_ANY_OBSERVATION_REQUEST"
    )
    assert frozen["stop"] == "STOP_BEFORE_ANY_OBSERVATION_REQUEST_FOR_REVIEW"
    assert frozen["new_gate"] is False
    assert frozen["generic_framework"] is False
    assert json.loads(plan.strict_json(frozen)) == frozen
    with pytest.raises(ValueError):
        plan.strict_json({"bad": float("nan")})
