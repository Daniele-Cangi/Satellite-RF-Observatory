from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_qualification_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]
SCREEN_RECEIPT = ROOT / plan.SCREEN_RECEIPT_NAME


def test_exact_screen_is_observation_blind_and_shortlist_is_unchanged() -> None:
    receipt = plan.verify_screen_receipt(SCREEN_RECEIPT)

    assert receipt["source_commit"] == plan.SCREEN_SOURCE_COMMIT
    assert not any(receipt["observation_access"].values())
    assert plan.canonical_sha256(SCREEN_RECEIPT) == plan.SCREEN_RECEIPT_SHA256


def test_wes_refusal_precedes_payload_and_forbids_signal_mapping() -> None:
    assessment = plan.candidate_assessment()[0]

    assert assessment["pair"] == ["DRAO00CAN", "WES200USA"]
    assert assessment["state"] == "CAPABILITY_REJECTED"
    assert assessment["evidence"]["wes_primary_feed"] == "RINEX_V2_ONLY"
    assert set(assessment["evidence"]["rinex3_head_status_by_doy"].values()) == {
        404
    }
    assert assessment["evidence"]["payload_bytes_accessed"] == 0
    assert "RINEX2" in assessment["forbidden_repair"]


def test_selected_roots_are_hardware_and_organisation_distinct() -> None:
    frozen = plan.plan()
    roots = frozen["selected_roots"]

    assert [item["station"] for item in roots] == ["ALGO00CAN", "MDO100USA"]
    assert len({item["domes"] for item in roots}) == 2
    assert len({item["receiver_serial"] for item in roots}) == 2
    assert len({item["antenna_serial"] for item in roots}) == 2
    assert len({item["agency"] for item in roots}) == 2
    assert len({item["primary_data_center"] for item in roots}) == 2
    assert frozen["candidate_assessment"][2]["remaining_physical_margin_m"] == (
        pytest.approx(47828.04192442695)
    )


def test_only_doy217_qualification_locators_enter_the_plan() -> None:
    frozen = plan.plan()
    qualification = frozen["qualification"]
    primary = frozen["future_primary_geometry"]

    assert qualification["doy"] == 217
    assert qualification["raw_start_gps"] == "2026-08-05T05:54:00 GPS"
    assert qualification["raw_stop_gps"] == "2026-08-05T07:03:00 GPS"
    assert all(item["body_bytes_accessed"] == 0 for item in qualification["products"])
    assert all("/217/" in item["url"] for item in qualification["products"])
    assert primary == {
        "doy": 219,
        "stations": ["ALGO00CAN", "MDO100USA"],
        "raw_start_gps": "2026-08-07T05:46:00 GPS",
        "raw_stop_gps": "2026-08-07T06:55:00 GPS",
        "product_locators": [],
        "product_discovery": "FORBIDDEN",
        "artifact_identity": "UNSELECTED_UNDISCOVERED_SEALED",
        "access": "FORBIDDEN",
    }
    assert "2026219" not in plan.strict_json(frozen)


def test_qualification_window_has_complete_joint_model_visibility() -> None:
    frozen = plan.plan()
    qualification = frozen["qualification"]

    assert qualification["minimum_joint_model_elevation_deg"] == pytest.approx(
        21.424674645
    )
    assert all(
        value >= 15.0
        for station in qualification[
            "minimum_elevation_deg_by_station_and_model"
        ].values()
        for value in station.values()
    )
    assert qualification["navigation_provenance"]["role"] == (
        "WINDOW_VISIBILITY_REGRESSION_ONLY"
    )


def test_field_roles_and_model_blind_boundary_are_exact() -> None:
    frozen = plan.plan()
    clauses = frozen["qualification_clauses"]
    execution = frozen["future_execution_boundary"]

    assert frozen["measurement_coordinate"]["core_phase"] == ["L1C", "L2W"]
    assert clauses["same_path_code"]["fields"] == ["C1C", "C2W"]
    assert clauses["optional_diagnostic"] == ["S1C", "S2W"]
    assert clauses["geometry_free_health"]["orbital_model_available"] is False
    assert execution["model_or_prediction_available_to_executor"] is False
    assert execution["failure_selects_fallback_pair_or_date"] is False
    assert execution["persisted_observation_values"] == 0
    assert execution["persisted_compressed_artifacts"] == 0


def test_plan_is_strict_json_and_access_is_zero() -> None:
    frozen = plan.plan()

    assert not any(frozen["access_at_freeze"].values())
    assert json.loads(plan.strict_json(frozen)) == frozen
    assert plan.manifest_sha256() == (
        "9f6d2ec41717666910b82e03341dbfc9ba6dd8285d481a93f0699e912206c3e4"
    )
    with pytest.raises(ValueError):
        plan.strict_json({"bad": float("nan")})
