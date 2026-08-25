from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


def test_frozen_sources_bind_geometry_and_passed_qualification() -> None:
    screen, qualification = plan.verify_sources(ROOT)

    assert screen["outcome"] == "INDEPENDENT_PAIR_GEOMETRY_SHORTLISTED"
    assert qualification["outcome"] == (
        "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
    )
    assert not any(qualification["future_primary_doy219_access"].values())


def test_primary_products_are_frozen_by_metadata_without_body_access() -> None:
    frozen = plan.plan()
    primary = frozen["roles"]["primary"]

    assert primary["stations"] == ["ALGO00CAN", "MDO100USA"]
    assert primary["raw_start_gps"] == "2026-08-07T05:46:00 GPS"
    assert primary["raw_stop_gps"] == "2026-08-07T06:55:00 GPS"
    assert [item["head_content_length"] for item in primary["products"]] == [
        4_320_264,
        3_559_665,
    ]
    assert all(item["head_status"] == 200 for item in primary["products"])
    assert all(item["head_requests"] == 1 for item in primary["products"])
    assert all(item["header_bytes_accessed"] == 0 for item in primary["products"])
    assert all(item["payload_bytes_accessed"] == 0 for item in primary["products"])
    assert all(item["observation_values_accessed"] == 0 for item in primary["products"])
    assert frozen["roles"]["fallback_or_reserve"] is None


def test_partition_coordinate_and_nulls_are_immutable() -> None:
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
    assert frozen["coordinate"]["derivative"] == "NONE"
    assert frozen["hypotheses"]["wrong_orbits"] == ["G01", "G14", "G17"]
    assert frozen["scoring"]["suffix_refit"] is False
    assert frozen["scoring"]["free_time_phase"] is False
    assert frozen["scoring"]["screen_controlling_null"] == "WRONG_ORBIT_G14"
    assert frozen["scoring"]["remaining_physical_margin_m"] == pytest.approx(
        47_828.04192442695
    )


def test_future_materialization_has_no_retry_or_substitution() -> None:
    materialization = plan.plan()["future_materialization"]

    assert materialization["attempts_per_locator"] == 1
    assert materialization["retry_after_plan_freeze"] is False
    assert materialization["endpoint_substitution"] is False
    assert materialization["date_substitution"] is False
    assert materialization["complete_hash_before_header_or_decode"] is True
    assert materialization["persisted_observation_values"] == 0
    assert materialization["persisted_compressed_or_decoded_artifacts"] == 0


def test_plan_is_strict_json_and_stops_before_primary_access() -> None:
    frozen = plan.plan()

    assert frozen["access_at_freeze"] == {
        "descriptive_head_requests": 2,
        "observation_headers_opened": 0,
        "observation_payload_bytes": 0,
        "observation_values": 0,
    }
    assert frozen["stop"] == (
        "STOP_BEFORE_PRIMARY_HEADER_OR_PAYLOAD_ACCESS_FOR_REVIEW"
    )
    assert json.loads(plan.strict_json(frozen)) == frozen
    with pytest.raises(ValueError):
        plan.strict_json({"bad": float("nan")})
