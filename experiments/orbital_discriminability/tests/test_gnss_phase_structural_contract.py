from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from experiments.orbital_discriminability import (
    gnss_phase_structural_contract as contract,
)


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "GNSS_PHASE_STRUCTURAL_CONTRACT.md"


def test_contract_is_bound_to_selected_geometry_receipt() -> None:
    receipt = contract.verify_geometry_receipt(ROOT / contract.GEOMETRY_RECEIPT_NAME)

    assert receipt["selected_geometry"]["target"] == "G22"
    assert receipt["selected_geometry"]["reference"] == "G30"
    assert receipt["selected_geometry"]["doy"] == 220
    assert contract.contract()["source_geometry"]["commit"] == (
        "0a994396e8b286e040496113dbb40e0b6e8207ed"
    )


def test_qualification_and_primary_roles_are_distinct_and_unmaterialized() -> None:
    frozen = contract.contract()
    qualification = frozen["roles"]["qualification"]
    primary = frozen["roles"]["primary"]

    assert qualification["gps_doy"] == 216
    assert primary["gps_doy"] == 220
    assert qualification["access"] == "NEXT_REVIEW_MAY_AUTHORIZE_ONLY_THIS_PAIR"
    assert primary["access"] == "SEALED_UNDISCOVERED_UNAUTHORIZED"
    assert qualification["artifact_sha256"] is None
    assert primary["artifact_sha256"] is None
    assert set(qualification["predeclared_product_locators"]).isdisjoint(
        primary["predeclared_product_locators"]
    )


def test_windows_preserve_exact_grid_partition_and_geometry_selection() -> None:
    assert contract.QUALIFICATION_RAW_STOP_GPS - contract.QUALIFICATION_RAW_START_GPS == (
        timedelta(seconds=(contract.RAW_EPOCHS - 1) * contract.STEP_S)
    )
    assert contract.PRIMARY_RAW_STOP_GPS - contract.PRIMARY_RAW_START_GPS == (
        timedelta(seconds=(contract.RAW_EPOCHS - 1) * contract.STEP_S)
    )
    frozen = contract.contract()
    assert frozen["partition"]["calibration_raw_indices_inclusive"] == [1, 77]
    assert frozen["partition"]["heldout_raw_indices_inclusive"] == [78, 384]
    assert frozen["roles"]["qualification"]["raw_start_gps"] == (
        "2026-08-04T04:47:00 GPS"
    )
    assert frozen["roles"]["primary"]["raw_start_gps"] == (
        "2026-08-08T04:30:30 GPS"
    )


def test_structural_readiness_cannot_promote_phase_health_or_measurement() -> None:
    frozen = contract.contract()
    boundary = frozen["clause_boundary"]

    assert boundary["geometry_free_phase_health"]["state"] == (
        "NOT_EVALUATED_BY_STRUCTURAL_ONLY_CONTRACT"
    )
    assert boundary["measurement_admission"] == "NOT_EVALUATED"
    assert boundary["orbital_score"] == "NOT_EVALUATED"
    assert frozen["structural_scan"]["values_parsed_or_retained"] == 0
    assert frozen["structural_scan"]["phase_or_code_scalars_represented"] == 0
    assert "PHASE_SCALARS" in boundary["geometry_free_phase_health"]["reason"]


def test_field_roles_and_witness_rules_are_frozen_without_snr_rejection() -> None:
    frozen = contract.contract()

    assert frozen["field_roles"] == {
        "core_phase": ["L1C", "L2W"],
        "cycle_slip_and_structural_continuity": [
            "LLI_ON_L1C",
            "LLI_ON_L2W",
            "EXACT_30_SECOND_EPOCH_GRID",
        ],
        "same_path_code_witness": ["C1C", "C2W"],
        "optional_diagnostic": ["S1C", "S2W"],
    }
    code = frozen["structural_scan"]["same_path_code_rule"]
    assert code["fatal_at_every_epoch"] is False
    assert code["minimum_presence_fraction_per_station_satellite_field"] == 0.95
    assert code["required_raw_indices"] == [1, 77, 78, 384]
    assert "NEVER_FATAL" in frozen["structural_scan"]["optional_signal_strength_rule"]


def test_only_doy216_structure_can_be_authorized_next() -> None:
    boundary = contract.contract()["next_authority_boundary"]

    assert "DOY216" in boundary["maximum"]
    assert boundary["qualification_phase_values"] == "FORBIDDEN"
    assert boundary["primary_headers_or_payload"] == "FORBIDDEN"
    assert boundary["orbital_score"] == "FORBIDDEN"


def test_materialization_failure_cannot_become_structural_rejection() -> None:
    frozen = contract.contract()

    assert "GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED" in frozen["outcomes"]
    meaning = frozen["outcome_semantics"][
        "GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED"
    ]
    assert "NOT_EVALUATED" in meaning
    assert "REJECTED" not in meaning


def test_strict_contract_is_finite_and_documented() -> None:
    encoded = contract.strict_json(contract.contract())
    report = REPORT.read_text(encoding="utf-8")

    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert contract.contract_sha256() in report
    assert "STRUCTURE_READY_FOR_HEALTH_REVIEW" in report
    assert "no observation product" in report.lower()
