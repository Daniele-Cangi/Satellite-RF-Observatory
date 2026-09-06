"""Freeze the model-blind DRAO DOY232 qualification boundary.

This module is an executable contract, not an observation executor.  It has no
network, locator, decoder, observation-value or orbital-model input surface.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


CONTRACT_VERSION: Final = "drao-doy232-qualification-contract-v1"
CONTRACT_STATE: Final = "DRAO_DOY232_QUALIFICATION_CONTRACT_FROZEN"

SCOPE_NAME: Final = "GNSS_DRAO_STAGED_MODEL_SCOPE.md"
SCOPE_SHA256: Final = (
    "f74894c7e12e311565ec4a7eb021d352527b3bc07bfdbc1df3df90611a9604a9"
)
MODEL_RESULT_NAME: Final = "GNSS_DRAO_STAGED_MODEL_ENVELOPE.json"
MODEL_RESULT_SHA256: Final = (
    "12578d1ea24fef1d71875280e41588e8a96cba78b3c45f6f8787eab8599e4626"
)
MODEL_SEAL_NAME: Final = "GNSS_DRAO_STAGED_MODEL_ENVELOPE_SEAL.json"
MODEL_SEAL_SHA256: Final = (
    "b942fde2366813346f476a58ec94b8bab170ef3b307c2ff229f4e2cb6e69554b"
)
ROOT_METADATA_NAME: Final = "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
ROOT_METADATA_SHA256: Final = (
    "24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c"
)

STATION: Final = "DRAO00CAN"
QUALIFICATION_DOY: Final = 232
POSSIBLE_PRIMARY_DOY: Final = 233
SATELLITES: Final = ("G07", "G08", "G09", "G21", "G27", "G30")
RAW_START: Final = datetime(2026, 8, 20, 1, 19, 0, tzinfo=timezone.utc)
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60

CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
OPTIONAL_DIAGNOSTICS: Final = ("S1C", "S2W")
L1_HZ: Final = 1_575_420_000.0
L2_HZ: Final = 1_227_600_000.0
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
IF_L1: Final = 2.5457277801631601
IF_L2: Final = -1.5457277801631601
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244
PER_TRACK_WITNESS_LIMIT_M: Final = 1_250.0
COMMON_MODE_WITNESS_RESERVE_M: Final = 2_500.0
MODEL_SIDE_ENVELOPE_M: Final = 881.9589614531837
CONDITIONAL_RESERVE_M: Final = 2_506.0017238368005
GUARD_M: Final = 7_339.701234647398
REMAINING_MARGIN_M: Final = 3_951.7405493574142


class DraoQualificationContractError(ValueError):
    """A frozen authority or qualification invariant changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    """Serialize finite contract data deterministically."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    """Hash repository text with CRLF normalized to LF."""

    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _gps(epoch: datetime) -> str:
    return epoch.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", " GPS"
    )


def contract() -> dict[str, object]:
    """Return the complete pre-artifact qualification contract."""

    raw_stop = RAW_START + timedelta(seconds=(RAW_EPOCHS - 1) * STEP_S)
    value: dict[str, object] = {
        "schema": "gnss-drao-doy232-qualification-contract-v1",
        "version": CONTRACT_VERSION,
        "state": CONTRACT_STATE,
        "new_gate": False,
        "physical_question": (
            "CAN_ONE_DISTINCT_DRAO_DOY232_ARTIFACT_PRESERVE_THE_SIX_TRACK_"
            "PHASE_COORDINATE_AND_CLOSE_THE_PREDECLARED_CAPABILITY_RESERVE_"
            "WITHOUT_RECEIVING_AN_ORBITAL_MODEL"
        ),
        "new_physical_information_if_executed": (
            "WHETHER_THE_DRAO_MEASUREMENT_PATH_CAN_MAKE_A_LATER_NEGATIVE_"
            "DOY233_ORBITAL_RESULT_INTERPRETABLE"
        ),
        "authorities": {
            SCOPE_NAME: SCOPE_SHA256,
            MODEL_RESULT_NAME: MODEL_RESULT_SHA256,
            MODEL_SEAL_NAME: MODEL_SEAL_SHA256,
            ROOT_METADATA_NAME: ROOT_METADATA_SHA256,
        },
        "roles": {
            "closed_doys": [230, 231],
            "qualification": {
                "station": STATION,
                "doy": QUALIFICATION_DOY,
                "role": "MODEL_BLIND_CAPABILITY_QUALIFICATION_NEVER_SCORED",
                "artifact_identity": "UNSELECTED",
                "artifact_locators": [],
            },
            "possible_primary": {
                "station": STATION,
                "doy": POSSIBLE_PRIMARY_DOY,
                "role": "UNSELECTED_UNFROZEN_UNAUTHORISED",
                "artifact_identity": "UNSELECTED",
                "artifact_locators": [],
                "access": "FORBIDDEN",
            },
        },
        "station_root": {
            "station": STATION,
            "domes": "40105M002",
            "receiver_type": "SEPT_POLARX5",
            "receiver_version": "5.2.0",
            "antenna_type": "TWIVC6050",
            "radome": "SCIS",
            "equipment_effective": "2021-09-02",
            "independent_metadata_sha256": (
                "2d738f85955f5896c999ed5c1cd42c034b825ccce1e153becc24210a015f9d3d"
            ),
            "artifact_header_must_match_independent_metadata": True,
            "unknown_or_conflicting_identity": "QUALIFICATION_TOPOLOGY_REJECTED",
        },
        "window": {
            "time_system": "GPS",
            "raw_start": _gps(RAW_START),
            "raw_stop": _gps(raw_stop),
            "cadence_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "satellites": list(SATELLITES),
            "expected_link_epochs": RAW_EPOCHS * len(SATELLITES),
            "event_time_bound_s": [-15.0, 15.0],
            "event_time_bound_may_be_reduced_by_qualification": False,
        },
        "format_and_transform": {
            "admitted_container": (
                "RINEX3_OBSERVATION_WITH_EXPLICIT_GPS_SIGNAL_IDENTITIES"
            ),
            "hatanaka_allowed": True,
            "gzip_allowed": True,
            "complete_compressed_hash_before_decode": True,
            "decoded_artifact_hash_required": True,
            "phase_units": "CYCLES",
            "code_units": "METERS",
            "l1_hz": L1_HZ,
            "l2_hz": L2_HZ,
            "l1_wavelength_m": SPEED_OF_LIGHT_M_S / L1_HZ,
            "l2_wavelength_m": SPEED_OF_LIGHT_M_S / L2_HZ,
            "ionosphere_free_coefficients": [IF_L1, IF_L2],
            "phase_coordinate_m": (
                "IF_L1*LAMBDA_L1*L1C+IF_L2*LAMBDA_L2*L2W"
            ),
            "same_path_code_coordinate_m": "IF_L1*C1C+IF_L2*C2W",
            "same_path_witness_m": "IF_PHASE_M-IF_CODE_M",
            "scale_factor_semantics": (
                "APPLY_SYS_SCALE_FACTOR_OR_SPEC_DEFINED_UNITY_IF_ABSENT"
            ),
            "phase_shift_semantics": (
                "APPLY_DECLARED_SYS_PHASE_SHIFT;UNSUPPORTED_IS_REJECTION"
            ),
            "receiver_clock_offset_semantics": (
                "PARSE_RCV_CLOCK_OFFS_APPL_AND_APPLY_ONLY_SPEC_DEFINED_"
                "EPOCH_TAG_SEMANTICS"
            ),
            "tgd_applied_to_carrier_phase": False,
            "optional_diagnostics": list(OPTIONAL_DIAGNOSTICS),
        },
        "clauses": {
            "artifact_identity": {
                "requires": [
                    "ONE_EXACT_DOY232_DRAO_OBSERVATION_ARTIFACT",
                    "FULL_BYTE_COUNT_AND_SHA256_BEFORE_DECODE",
                    "NO_FALLBACK_STATION_DATE_OR_SIGNAL_FAMILY",
                ],
                "state_at_freeze": "NOT_EVALUATED",
            },
            "header_identity_and_time": {
                "requires": [
                    "MARKER_AND_DOMES_MATCH_DRAO00CAN_40105M002",
                    "RECEIVER_AND_ANTENNA_MATCH_FROZEN_INDEPENDENT_METADATA",
                    "TIME_OF_FIRST_OBS_GPS_COVERS_WINDOW_START",
                    "TIME_OF_LAST_OBS_GPS_COVERS_WINDOW_STOP",
                    "INTERVAL_EQUALS_30_SECONDS",
                    "EXACT_SIGNAL_SCALE_PHASE_SHIFT_AND_CLOCK_OFFSET_SEMANTICS",
                ],
                "state_at_freeze": "NOT_EVALUATED",
            },
            "complete_core_phase": {
                "fields": list(CORE_PHASE),
                "required_fraction_each_satellite_field": 1.0,
                "required_epoch_count_each_satellite_field": RAW_EPOCHS,
                "nonzero_lli_breaks_track": True,
                "missing_blank_omitted_or_invalid_breaks_track": True,
                "interpolation": "FORBIDDEN",
                "gap_bridging": "FORBIDDEN",
                "state_at_freeze": "NOT_EVALUATED",
            },
            "complete_same_path_code": {
                "fields": list(SAME_PATH_CODE),
                "required_fraction_each_satellite_field": 1.0,
                "required_epoch_count_each_satellite_field": RAW_EPOCHS,
                "missing_epoch_bound": 0,
                "may_correct_or_replace_phase": False,
                "state_at_freeze": "NOT_EVALUATED",
            },
            "cycle_slip_and_continuity": {
                "lli_allowed_values": [0, None],
                "blank_lli_semantics": "ZERO_ONLY_WHEN_PHASE_FIELD_IS_PRESENT",
                "geometry_free_coordinate_m": "LAMBDA_L1*L1C-LAMBDA_L2*L2W",
                "maximum_absolute_second_difference_m": (
                    GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                ),
                "violation_selects_alternate_segment": False,
                "state_at_freeze": "NOT_EVALUATED",
            },
            "physical_same_path_witness": {
                "common_mode_operator": "C=I-(1/6)11T",
                "prefix_projection": (
                    "PER_TRACK_CONSTANT_PLUS_RATE_FIT_ON_FIRST_79_EPOCHS_ONLY"
                ),
                "heldout_refit": False,
                "per_track_heldout_peak_to_peak_limit_m": (
                    PER_TRACK_WITNESS_LIMIT_M
                ),
                "common_mode_gain_upper_bound": 2.0,
                "derived_common_mode_reserve_m": COMMON_MODE_WITNESS_RESERVE_M,
                "qualification_may_change_limit": False,
                "state_at_freeze": "NOT_EVALUATED",
            },
        },
        "structural_receipt": {
            "one_row_per_station_epoch_satellite_relevant_observable": True,
            "allowed_field_states": [
                "PRESENT",
                "BLANK",
                "TRAILING_FIELD_OMITTED",
                "CONTINUATION_SUPPORTED",
                "CONTINUATION_UNSUPPORTED",
                "RECORD_INVALID",
            ],
            "persisted_observation_values": 0,
            "persisted_derived_series": 0,
            "permitted_numeric_summaries": [
                "COUNTS",
                "MAX_ABS_GEOMETRY_FREE_SECOND_DIFFERENCE_M",
                "PER_TRACK_WITNESS_HELDOUT_PEAK_TO_PEAK_M",
            ],
            "description_error_changes_physical_decision": False,
        },
        "future_executor_boundary": {
            "orbital_model_available": False,
            "retained_model_curves_available": False,
            "predicted_assignment_available": False,
            "observation_values": "EPHEMERAL_RAM_ONLY_AFTER_SEPARATE_AUTHORITY",
            "artifact_payload_retained_after_run": 0,
            "retry_before_complete_hash": [
                "TIMEOUT",
                "TRANSPORT_INTERRUPTION",
                "DESCRIPTION_ERROR",
                "SERIALIZATION_ERROR",
                "SOFTWARE_TRANSFORM_ERROR",
            ],
            "retry_after_complete_hash_or_decode": 0,
            "qualification_failure_selects_fallback": False,
        },
        "envelope_binding": {
            "model_side_m": MODEL_SIDE_ENVELOPE_M,
            "conditional_reserve_m": CONDITIONAL_RESERVE_M,
            "complete_witness_component_m": COMMON_MODE_WITNESS_RESERVE_M,
            "guard_m": GUARD_M,
            "remaining_margin_m": REMAINING_MARGIN_M,
            "qualification_may_change_numbers": False,
            "all_clauses_required_to_activate_reserve": True,
        },
        "future_outcomes": [
            "NO_QUALIFICATION_ARTIFACT_AVAILABLE",
            "QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED",
            "QUALIFICATION_DESCRIPTION_ERROR",
            "QUALIFICATION_TOPOLOGY_REJECTED",
            "QUALIFICATION_PHYSICAL_WITNESS_REJECTED",
            "DRAO_QUALIFICATION_PASSED_PRIMARY_STILL_SEALED",
        ],
        "outcome_semantics": {
            "description_error": (
                "CLAUSES_NOT_EVALUATED_AND_NO_PHYSICAL_REJECTION"
            ),
            "topology_rejected": (
                "IDENTITY_HEADER_TIME_FORMAT_STRUCTURE_OR_CONTINUITY_FAILED"
            ),
            "physical_witness_rejected": (
                "COMPLETE_PATH_EXISTS_BUT_FROZEN_WITNESS_LIMIT_FAILED"
            ),
            "passed": (
                "EVERY_CLAUSE_SATISFIED_BUT_DOY233_REMAINS_UNSELECTED"
            ),
        },
        "access_at_freeze": {
            "qualification_locators": 0,
            "qualification_headers": 0,
            "qualification_payload_bytes": 0,
            "qualification_values": 0,
            "primary_locators": 0,
            "primary_headers": 0,
            "primary_payload_bytes": 0,
            "primary_values": 0,
        },
        "next_maximum": (
            "REVIEW_THEN_SELECT_AT_MOST_ONE_DOY232_ARTIFACT_WITHOUT_"
            "SELECTING_OR_ACCESSING_DOY233"
        ),
        "stop": "STOP_BEFORE_ANY_DRAO_OBSERVATION_LOCATOR_OR_ARTIFACT_ACCESS",
    }
    _validate(value)
    strict_json(value)
    return value


def _validate(value: Mapping[str, object]) -> None:
    roles = value["roles"]
    qualification = roles["qualification"]
    primary = roles["possible_primary"]
    access = value["access_at_freeze"]
    clauses = value["clauses"]
    envelope = value["envelope_binding"]

    if qualification["artifact_locators"] or primary["artifact_locators"]:
        raise DraoQualificationContractError("ARTIFACT_ENTERED_PRE_FREEZE_CONTRACT")
    if primary["access"] != "FORBIDDEN":
        raise DraoQualificationContractError("POSSIBLE_PRIMARY_NOT_SEALED")
    if any(int(item) != 0 for item in access.values()):
        raise DraoQualificationContractError("OBSERVATION_ACCESS_AT_FREEZE")
    if clauses["complete_same_path_code"][
        "required_fraction_each_satellite_field"
    ] != 1.0:
        raise DraoQualificationContractError("INCOMPLETE_CODE_WITNESS_ALLOWED")
    if clauses["complete_same_path_code"]["missing_epoch_bound"] != 0:
        raise DraoQualificationContractError("MISSING_CODE_EPOCH_ASSIGNED_A_BOUND")
    derived = (
        clauses["physical_same_path_witness"]["common_mode_gain_upper_bound"]
        * clauses["physical_same_path_witness"][
            "per_track_heldout_peak_to_peak_limit_m"
        ]
    )
    if derived != envelope["complete_witness_component_m"]:
        raise DraoQualificationContractError("WITNESS_RESERVE_TOPOLOGY_CHANGED")
    if abs(
        envelope["guard_m"]
        - envelope["model_side_m"]
        - envelope["conditional_reserve_m"]
        - envelope["remaining_margin_m"]
    ) > 1.0e-9:
        raise DraoQualificationContractError("FROZEN_MARGIN_ARITHMETIC_CHANGED")


def verify_authorities(root: Path) -> dict[str, str]:
    """Verify the four exact committed inputs without external I/O."""

    actual = {
        name: canonical_sha256(Path(root) / name)
        for name in contract()["authorities"]
    }
    if actual != contract()["authorities"]:
        raise DraoQualificationContractError("FROZEN_AUTHORITY_CHANGED")
    model = json.loads(
        (Path(root) / MODEL_RESULT_NAME).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if model.get("outcome") != "DRAO_MODEL_SIDE_ENVELOPE_ADMITTED":
        raise DraoQualificationContractError("MODEL_SIDE_NOT_ADMITTED")
    if any(model.get("observation_access", {}).values()):
        raise DraoQualificationContractError("MODEL_SIDE_USED_OBSERVATION")
    return actual


def manifest_sha256() -> str:
    return sha256(strict_json(contract()).encode("ascii")).hexdigest()


def main() -> None:
    print(strict_json(contract(), pretty=True))


if __name__ == "__main__":
    main()
