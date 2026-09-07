from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_doy232_qualification_contract as contract,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "GNSS_DRAO_DOY232_QUALIFICATION_CONTRACT.json"


def test_exact_model_and_metadata_authorities_are_unchanged() -> None:
    assert contract.verify_authorities(ROOT) == contract.contract()["authorities"]


def test_only_doy232_role_is_frozen_and_every_locator_is_absent() -> None:
    frozen = contract.contract()
    roles = frozen["roles"]

    assert roles["closed_doys"] == [230, 231]
    assert roles["qualification"]["doy"] == 232
    assert roles["qualification"]["artifact_locators"] == []
    assert roles["possible_primary"] == {
        "station": "DRAO00CAN",
        "doy": 233,
        "role": "UNSELECTED_UNFROZEN_UNAUTHORISED",
        "artifact_identity": "UNSELECTED",
        "artifact_locators": [],
        "access": "FORBIDDEN",
    }
    assert not any(frozen["access_at_freeze"].values())


def test_frozen_window_and_complete_six_track_topology() -> None:
    frozen = contract.contract()
    window = frozen["window"]
    clauses = frozen["clauses"]

    assert window["raw_start"] == "2026-08-20T01:19:00 GPS"
    assert window["raw_stop"] == "2026-08-20T02:28:00 GPS"
    assert window["raw_epochs"] == 139
    assert window["prefix_epochs"] == 79
    assert window["heldout_epochs"] == 60
    assert window["expected_link_epochs"] == 834
    assert clauses["complete_core_phase"]["fields"] == ["L1C", "L2W"]
    assert clauses["complete_same_path_code"]["fields"] == ["C1C", "C2W"]


def test_missing_code_epoch_cannot_activate_the_reserve() -> None:
    clause = contract.contract()["clauses"]["complete_same_path_code"]

    assert clause["required_fraction_each_satellite_field"] == 1.0
    assert clause["required_epoch_count_each_satellite_field"] == 139
    assert clause["missing_epoch_bound"] == 0
    assert clause["may_correct_or_replace_phase"] is False


def test_witness_limit_closes_exact_common_mode_component() -> None:
    frozen = contract.contract()
    witness = frozen["clauses"]["physical_same_path_witness"]
    envelope = frozen["envelope_binding"]

    assert witness["heldout_refit"] is False
    assert witness["per_track_heldout_peak_to_peak_limit_m"] == 1_250.0
    assert witness["common_mode_gain_upper_bound"] == 2.0
    assert (
        witness["per_track_heldout_peak_to_peak_limit_m"]
        * witness["common_mode_gain_upper_bound"]
        == envelope["complete_witness_component_m"]
        == 2_500.0
    )
    assert envelope["remaining_margin_m"] == pytest.approx(
        envelope["guard_m"]
        - envelope["model_side_m"]
        - envelope["conditional_reserve_m"]
    )


def test_transform_semantics_are_explicit_and_model_blind() -> None:
    frozen = contract.contract()
    transform = frozen["format_and_transform"]
    boundary = frozen["future_executor_boundary"]

    assert transform["phase_units"] == "CYCLES"
    assert transform["code_units"] == "METERS"
    assert transform["scale_factor_semantics"].startswith("APPLY_SYS_SCALE_FACTOR")
    assert "APPLY_DECLARED_SYS_PHASE_SHIFT" in transform["phase_shift_semantics"]
    assert transform["tgd_applied_to_carrier_phase"] is False
    assert boundary["orbital_model_available"] is False
    assert boundary["retained_model_curves_available"] is False
    assert boundary["predicted_assignment_available"] is False
    assert boundary["retry_after_complete_hash_or_decode"] == 0


def test_description_failure_is_not_a_physical_rejection() -> None:
    frozen = contract.contract()

    assert frozen["structural_receipt"][
        "description_error_changes_physical_decision"
    ] is False
    assert frozen["outcome_semantics"]["description_error"] == (
        "CLAUSES_NOT_EVALUATED_AND_NO_PHYSICAL_REJECTION"
    )
    assert "QUALIFICATION_DESCRIPTION_ERROR" in frozen["future_outcomes"]
    assert "QUALIFICATION_TOPOLOGY_REJECTED" in frozen["future_outcomes"]


def test_manifest_is_strict_and_stable() -> None:
    frozen = contract.contract()

    assert json.loads(contract.strict_json(frozen)) == frozen
    assert json.loads(MANIFEST.read_text(encoding="ascii")) == frozen
    assert contract.canonical_sha256(MANIFEST) == (
        "f0a02eb1d49b7ea01db6db263a1fb81af0d317fd959d1c78c3aece822c842df1"
    )
    assert contract.manifest_sha256() == (
        "667be5b59b9da90c11710c9c6ae4c3d6ff24b06d73ac0337136b4371e8051e72"
    )
    with pytest.raises(ValueError):
        contract.strict_json({"bad": float("nan")})
