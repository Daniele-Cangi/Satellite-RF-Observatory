"""Frozen value-blind contract for the selected G22/G30 phase geometry.

This module does not discover or open an observation product.  It freezes the
only structural questions that may be asked of a later DOY 216 qualification
pair and keeps geometry-free phase health outside the value-blind boundary.
It is deliberately experiment-specific and is not a generic contract API.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


CONTRACT_VERSION: Final = "g22-g30-phase-structure-doy216-v1"
SOURCE_GEOMETRY_COMMIT: Final = "0a994396e8b286e040496113dbb40e0b6e8207ed"
GEOMETRY_RECEIPT_NAME: Final = "GNSS_PHASE_GEOMETRY_SCREEN_RECEIPT.json"
GEOMETRY_RECEIPT_SHA256: Final = (
    "228359ad8e65dfe0191562ca601c6f47dad44ab36bab07736c63e8f9188f293c"
)

STEP_S: Final = 30
RAW_EPOCHS: Final = 386
FEATURE_EPOCHS: Final = 384
CALIBRATION_FEATURE_EPOCHS: Final = 77
HELDOUT_FEATURE_EPOCHS: Final = 307
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 384)
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244

QUALIFICATION_RAW_START_GPS: Final = datetime(
    2026, 8, 4, 4, 47, 0, tzinfo=timezone.utc
)
QUALIFICATION_RAW_STOP_GPS: Final = datetime(
    2026, 8, 4, 7, 59, 30, tzinfo=timezone.utc
)
PRIMARY_RAW_START_GPS: Final = datetime(
    2026, 8, 8, 4, 30, 30, tzinfo=timezone.utc
)
PRIMARY_RAW_STOP_GPS: Final = datetime(
    2026, 8, 8, 7, 43, 0, tzinfo=timezone.utc
)

STRUCTURAL_STATES: Final = (
    "PRESENT",
    "BLANK",
    "TRAILING_FIELD_OMITTED",
    "CONTINUATION_SUPPORTED",
    "CONTINUATION_UNSUPPORTED",
    "RECORD_INVALID",
)
ALLOWED_OUTCOMES: Final = (
    "GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW",
    "GNSS_PHASE_STRUCTURE_REJECTED",
    "GNSS_PHASE_STRUCTURE_DESCRIPTION_ERROR",
    "GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED",
)


class PhaseStructuralContractError(ValueError):
    """The bounded phase-structure contract is internally inconsistent."""


def _gps(epoch: datetime) -> str:
    if epoch.tzinfo is None or epoch.utcoffset() is None:
        raise PhaseStructuralContractError("GPS_EPOCH_MUST_BE_TIMEZONE_AWARE")
    return epoch.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", " GPS"
    )


def _role(
    *,
    role: str,
    doy: int,
    raw_start: datetime,
    raw_stop: datetime,
    access: str,
) -> dict[str, object]:
    feature_start = raw_start + timedelta(seconds=STEP_S)
    feature_stop = raw_stop - timedelta(seconds=STEP_S)
    return {
        "role": role,
        "gps_doy": doy,
        "satellites": ["G22", "G30"],
        "stations": ["GOLD00USA", "NLIB00USA"],
        "predeclared_product_locators": [
            f"GOLD00USA_R_2026{doy:03d}0000_01D_30S_MO.crx.gz",
            f"NLIB00USA_R_2026{doy:03d}0000_01D_30S_MO.crx.gz",
        ],
        "product_identity_state": "LOCATOR_ONLY_NOT_MATERIALIZED_OR_HASH_BOUND",
        "artifact_sha256": None,
        "raw_start_gps": _gps(raw_start),
        "raw_stop_gps": _gps(raw_stop),
        "feature_start_gps": _gps(feature_start),
        "feature_stop_gps": _gps(feature_stop),
        "raw_epochs": RAW_EPOCHS,
        "feature_epochs": FEATURE_EPOCHS,
        "access": access,
    }


def contract() -> dict[str, object]:
    result = {
        "schema": "gnss-phase-structural-contract-v1",
        "contract_version": CONTRACT_VERSION,
        "source_geometry": {
            "commit": SOURCE_GEOMETRY_COMMIT,
            "receipt": GEOMETRY_RECEIPT_NAME,
            "receipt_sha256": GEOMETRY_RECEIPT_SHA256,
            "selected_target": "G22",
            "selected_reference": "G30",
            "controlling_null": "WRONG_ORBIT_G14",
        },
        "scope": (
            "VALUE_BLIND_STRUCTURE_ONLY_DOY216_QUALIFICATION_PAIR_"
            "NO_OBSERVATION_PRODUCT_ACCESS_IN_THIS_COMMIT"
        ),
        "roles": {
            "qualification": _role(
                role="INDEPENDENT_STRUCTURAL_QUALIFICATION_ONLY",
                doy=216,
                raw_start=QUALIFICATION_RAW_START_GPS,
                raw_stop=QUALIFICATION_RAW_STOP_GPS,
                access="NEXT_REVIEW_MAY_AUTHORIZE_ONLY_THIS_PAIR",
            ),
            "primary": _role(
                role="LATER_PROSPECTIVE_PRIMARY_CANDIDATE",
                doy=220,
                raw_start=PRIMARY_RAW_START_GPS,
                raw_stop=PRIMARY_RAW_STOP_GPS,
                access="SEALED_UNDISCOVERED_UNAUTHORIZED",
            ),
        },
        "partition": {
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "feature_epochs": FEATURE_EPOCHS,
            "calibration_feature_epochs": CALIBRATION_FEATURE_EPOCHS,
            "heldout_feature_epochs": HELDOUT_FEATURE_EPOCHS,
            "feature_raw_indices_inclusive": [1, 384],
            "calibration_raw_indices_inclusive": [1, 77],
            "heldout_raw_indices_inclusive": [78, 384],
        },
        "station_configuration": {
            "GOLD00USA": {
                "receiver": "JAVAD TRE_G3TH DELTA",
                "receiver_version": "4.2.03",
                "antenna": "AOAD/M_T NONE",
            },
            "NLIB00USA": {
                "receiver": "SEPT POLARX5TR",
                "receiver_version": "5.7.0",
                "antenna": "JAVRINGANT_DM SCIS",
            },
            "rule": (
                "QUALIFICATION_AND_ANY_LATER_PRIMARY_HEADERS_MUST_MATCH_THE_"
                "PREDECLARED_RECEIVER_AND_ANTENNA_CONFIGURATION"
            ),
        },
        "field_roles": {
            "core_phase": ["L1C", "L2W"],
            "cycle_slip_and_structural_continuity": [
                "LLI_ON_L1C",
                "LLI_ON_L2W",
                "EXACT_30_SECOND_EPOCH_GRID",
            ],
            "same_path_code_witness": ["C1C", "C2W"],
            "optional_diagnostic": ["S1C", "S2W"],
        },
        "header_admission": {
            "time_system": "GPS",
            "required": [
                "TIME OF FIRST OBS",
                "TIME OF LAST OBS",
                "INTERVAL",
                "REC # / TYPE / VERS",
                "ANT # / TYPE",
                "SYS / # / OBS TYPES",
                "RCV CLOCK OFFS APPL_OR_STANDARD_DEFAULT",
            ],
            "full_raw_window_coverage_required": True,
            "declared_interval_s": STEP_S,
            "event_time_bound_s": [-15.0, 15.0],
            "event_time_rule": (
                "STRUCTURE_PRESERVES_THE_EXISTING_HALF_CADENCE_BOUND_AND_"
                "CANNOT_TIGHTEN_ADC_TO_GPS_TIME"
            ),
        },
        "structural_scan": {
            "field_states": list(STRUCTURAL_STATES),
            "complete_window_scan": True,
            "stop_at_first_missing_field": False,
            "values_parsed_or_retained": 0,
            "phase_or_code_scalars_represented": 0,
            "segment_rule": {
                "interpolation": "FORBIDDEN",
                "gap_bridging": "FORBIDDEN",
                "required_joint_segment": "ENTIRE_PREDECLARED_386_EPOCH_WINDOW",
                "breaks": [
                    "MISSING_BLANK_OR_OMITTED_CORE_PHASE",
                    "NONZERO_OR_INVALID_LLI",
                    "MISSING_OR_OFF_GRID_EPOCH",
                    "EPOCH_FLAG_NOT_ZERO_INCLUDING_POWER_FAILURE",
                    "UNSUPPORTED_CONTINUATION",
                    "INVALID_RECORD",
                ],
            },
            "same_path_code_rule": {
                "fatal_at_every_epoch": False,
                "minimum_presence_fraction_per_station_satellite_field": (
                    CODE_MINIMUM_COVERAGE_FRACTION
                ),
                "required_raw_indices": list(CODE_REQUIRED_RAW_INDICES),
                "may_adjust_phase_score": False,
            },
            "optional_signal_strength_rule": (
                "S1C_S2W_NEVER_FATAL_WITHOUT_A_SEPARATE_QUANTITATIVE_RULE_"
                "AND_COHERENT_UNITS"
            ),
        },
        "clause_boundary": {
            "artifact_identity": "NOT_EVALUATED_UNTIL_COMPLETE_FILE_HASH",
            "header_and_field_topology": "EVALUABLE_BY_LATER_STRUCTURAL_SCAN",
            "lli_and_epoch_continuity": "EVALUABLE_BY_LATER_STRUCTURAL_SCAN",
            "geometry_free_phase_health": {
                "state": "NOT_EVALUATED_BY_STRUCTURAL_ONLY_CONTRACT",
                "future_frozen_second_difference_limit_m": (
                    GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                ),
                "reason": "REQUIRES_PHASE_SCALARS_DESPITE_ZERO_PERSISTENCE",
            },
            "measurement_admission": "NOT_EVALUATED",
            "orbital_score": "NOT_EVALUATED",
        },
        "outcomes": list(ALLOWED_OUTCOMES),
        "outcome_semantics": {
            "GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW": (
                "STRUCTURE_ONLY_PASSED_MEASUREMENT_AND_ORBITAL_CLAIMS_REMAIN_"
                "NOT_EVALUATED"
            ),
            "GNSS_PHASE_STRUCTURE_REJECTED": (
                "ONE_OR_MORE_STRUCTURAL_CLAUSES_FAILED_NO_PHASE_HEALTH_OR_"
                "ORBITAL_SCORE_MAY_RUN"
            ),
            "GNSS_PHASE_STRUCTURE_DESCRIPTION_ERROR": (
                "RECEIPT_OR_SOFTWARE_DESCRIPTION_FAILED_PHYSICAL_AND_"
                "STRUCTURAL_DECISIONS_REMAIN_NOT_EVALUATED"
            ),
            "GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED": (
                "ONE_OR_BOTH_EXACT_LOCATORS_COULD_NOT_BE_COMPLETELY_"
                "MATERIALIZED_STRUCTURE_AND_PHYSICAL_CLAUSES_REMAIN_NOT_EVALUATED"
            ),
        },
        "next_authority_boundary": {
            "maximum": (
                "BOUNDED_DISCOVERY_MATERIALIZATION_HASH_HEADER_AND_VALUE_"
                "BLIND_STRUCTURAL_SCAN_OF_THE_TWO_DOY216_LOCATORS_ONLY"
            ),
            "requires_review_before_execution": True,
            "qualification_phase_values": "FORBIDDEN",
            "primary_headers_or_payload": "FORBIDDEN",
            "orbital_score": "FORBIDDEN",
            "retry": "ONLY_BEFORE_COMPLETE_FILE_HASH_FOR_TRANSPORT_OR_DESCRIPTION_ERROR",
        },
        "access_at_freeze": {
            "observation_products_discovered": 0,
            "observation_products_materialized": 0,
            "headers_opened": 0,
            "observation_payload_bytes": 0,
            "observation_values_accessed": 0,
        },
        "forbidden": [
            "DOY220 primary discovery header or payload access",
            "phase or code scalar parsing under the structural-only authority",
            "geometry-free health inferred from field presence",
            "structural readiness promoted to measurement admission",
            "field threshold window satellite station or null changes after access",
            "new gate generic contract class or receiver catalog",
        ],
    }
    validate_contract(result)
    strict_json(result)
    return result


def validate_contract(value: Mapping[str, object]) -> None:
    roles = value["roles"]
    for role_name, start, stop in (
        ("qualification", QUALIFICATION_RAW_START_GPS, QUALIFICATION_RAW_STOP_GPS),
        ("primary", PRIMARY_RAW_START_GPS, PRIMARY_RAW_STOP_GPS),
    ):
        role = roles[role_name]
        if stop - start != timedelta(seconds=(RAW_EPOCHS - 1) * STEP_S):
            raise PhaseStructuralContractError(f"{role_name.upper()}_WINDOW_CHANGED")
        if role["raw_epochs"] != RAW_EPOCHS or role["feature_epochs"] != FEATURE_EPOCHS:
            raise PhaseStructuralContractError(f"{role_name.upper()}_EPOCH_COUNT_CHANGED")
        if role["artifact_sha256"] is not None:
            raise PhaseStructuralContractError("UNMATERIALIZED_ARTIFACT_HASH_INVENTED")
    if CALIBRATION_FEATURE_EPOCHS + HELDOUT_FEATURE_EPOCHS != FEATURE_EPOCHS:
        raise PhaseStructuralContractError("PARTITION_CHANGED")
    health = value["clause_boundary"]["geometry_free_phase_health"]
    if health["state"] != "NOT_EVALUATED_BY_STRUCTURAL_ONLY_CONTRACT":
        raise PhaseStructuralContractError("PHASE_HEALTH_PROMOTED_BY_STRUCTURE")
    if value["clause_boundary"]["measurement_admission"] != "NOT_EVALUATED":
        raise PhaseStructuralContractError("MEASUREMENT_PROMOTED_BY_STRUCTURE")
    if tuple(value["outcomes"]) != ALLOWED_OUTCOMES:
        raise PhaseStructuralContractError("OUTCOME_SET_CHANGED")
    if any(value["access_at_freeze"].values()):
        raise PhaseStructuralContractError("OBSERVATION_ACCESS_AT_FREEZE")


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def contract_sha256() -> str:
    return sha256(strict_json(contract()).encode("ascii")).hexdigest()


def verify_geometry_receipt(path: Path) -> dict[str, object]:
    canonical = Path(path).read_bytes().replace(b"\r\n", b"\n")
    if sha256(canonical).hexdigest() != GEOMETRY_RECEIPT_SHA256:
        raise PhaseStructuralContractError("GEOMETRY_RECEIPT_CHANGED")
    receipt = json.loads(canonical)
    selected = receipt.get("selected_geometry", {})
    if receipt.get("outcome") != "GNSS_PHASE_GEOMETRY_SELECTED":
        raise PhaseStructuralContractError("GEOMETRY_NOT_SELECTED")
    if (selected.get("target"), selected.get("reference"), selected.get("doy")) != (
        "G22",
        "G30",
        220,
    ):
        raise PhaseStructuralContractError("SELECTED_GEOMETRY_CHANGED")
    return receipt
