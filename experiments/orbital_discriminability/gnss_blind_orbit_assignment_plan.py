"""Offline prospective plan for one bounded blind GPS orbit assignment.

The compiler binds only frozen aggregate artifacts.  It has no network client,
observation decoder, prediction payload, measurement value or scoring surface.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence

from experiments.orbital_discriminability import (
    gnss_amc_observer_primary_plan as amc,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as inherited,
)


PLAN_VERSION: Final = "gnss-bounded-blind-orbit-assignment-plan-v1"
OUTCOME: Final = "BLIND_ORBIT_ASSIGNMENT_PLAN_FROZEN"
RECEIPT_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_PLAN_RECEIPT.json"

PLAN_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_PRIMARY_PLAN.md"
PLAN_SHA256: Final = (
    "2cd8d31b81a1cb2d45fed03af28aa164bfbf54f86d440860dde11bda4683de62"
)
MAPPING_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_MAPPING_SEAL.json"
MAPPING_SHA256: Final = (
    "b719a2bf17e66fcafa3597c4018d6acd039bdac4e33ecb173795646ff47245db"
)
SCREEN_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_SCREEN_RECEIPT.json"
SCREEN_SHA256: Final = (
    "cddc9fcf0db1be7f55fde04f1bf51256c3a88edf2608871b3bc7e438bd167485"
)
METADATA_NAME: Final = amc.METADATA_NAME
METADATA_SHA256: Final = amc.METADATA_SHA256
QUALIFICATION_NAME: Final = amc.QUALIFICATION_NAME
QUALIFICATION_SHA256: Final = amc.QUALIFICATION_SHA256
QUALIFICATION_SUMMARY_NAME: Final = amc.QUALIFICATION_SUMMARY_NAME
QUALIFICATION_SUMMARY_SHA256: Final = amc.QUALIFICATION_SUMMARY_SHA256
QUALIFICATION_COVERAGE_NAME: Final = amc.QUALIFICATION_COVERAGE_NAME
QUALIFICATION_COVERAGE_SHA256: Final = amc.QUALIFICATION_COVERAGE_SHA256

STATION: Final = "AMC400USA"
TARGET: Final = "G22"
REFERENCE: Final = "G30"
CANDIDATE_FAMILY: Final = ("G22", "G06", "G14", "G17", "G19")
PRIMARY_PRODUCT: Final = "AMC400USA_R_20262260000_01D_30S_MO.crx.gz"
PRIMARY_GSSC_DIRECTORY: Final = "/gnss/data/daily/2026/226"
PRIMARY_GSSC_WEB_ROOT: Final = "https://gssc.esa.int/webftp/"
RAW_START_GPS: Final = "2026-08-14T06:14:30 GPS"
HELDOUT_START_GPS: Final = "2026-08-14T06:54:00 GPS"
RAW_STOP_GPS: Final = "2026-08-14T07:23:30 GPS"
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
STEP_S: Final = 30.0
PAIRWISE_GUARD_M: Final = amc.REVISED_PAIRWISE_GUARD_M
MINIMUM_COMBINED_MARGIN_M: Final = 11_424.01533014155
MINIMUM_SHIFTED_ELEVATION_DEG: Final = 15.01043286179639


class BlindOrbitPlanError(ValueError):
    """A frozen plan parent, mapping or numerical invariant changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def _read_strict_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise BlindOrbitPlanError(f"PARENT_NOT_OBJECT:{path.name}")
    return value


def _require_hash(root: Path, name: str, digest: str) -> Path:
    path = Path(root) / name
    if not path.is_file() or canonical_sha256(path) != digest:
        raise BlindOrbitPlanError(f"FROZEN_PARENT_CHANGED:{name}")
    return path


def _close(actual: object, expected: float, label: str) -> None:
    if not isclose(float(actual), expected, rel_tol=0.0, abs_tol=1.0e-9):
        raise BlindOrbitPlanError(f"FROZEN_NUMERICAL_VALUE_CHANGED:{label}")


def _validate_screen(path: Path) -> tuple[dict[str, object], Mapping[str, object]]:
    value = _read_strict_json(path)
    if value.get("outcome") != "BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED":
        raise BlindOrbitPlanError("SCREEN_OUTCOME_CHANGED")
    selected = value.get("selected")
    if not isinstance(selected, Mapping):
        raise BlindOrbitPlanError("SCREEN_SELECTION_MISSING")
    exact = {
        "doy": 226,
        "gps_date": "2026-08-14",
        "raw_start_gps": RAW_START_GPS,
        "heldout_start_gps": HELDOUT_START_GPS,
        "raw_stop_gps": RAW_STOP_GPS,
        "candidate_family": list(CANDIDATE_FAMILY),
    }
    if any(selected.get(key) != expected for key, expected in exact.items()):
        raise BlindOrbitPlanError("SCREEN_SELECTION_CHANGED")
    _close(
        selected.get("minimum_combined_remaining_margin_m"),
        MINIMUM_COMBINED_MARGIN_M,
        "MINIMUM_COMBINED_MARGIN",
    )
    _close(
        selected.get("minimum_time_shifted_elevation_deg"),
        MINIMUM_SHIFTED_ELEVATION_DEG,
        "MINIMUM_SHIFTED_ELEVATION",
    )
    if any(value.get("observation_access", {}).values()):
        raise BlindOrbitPlanError("SCREEN_OBSERVATION_BOUNDARY_CHANGED")
    if value.get("prospective_plan_frozen") is not False:
        raise BlindOrbitPlanError("SCREEN_ALREADY_PROMOTED")
    if value.get("primary_selected") is not False:
        raise BlindOrbitPlanError("SCREEN_ALREADY_SELECTED_PRIMARY")
    return value, selected


def _validate_mapping(path: Path) -> tuple[dict[str, object], tuple[str, ...]]:
    value = _read_strict_json(path)
    if value.get("schema") != "gnss-blind-orbit-assignment-mapping-seal-v1":
        raise BlindOrbitPlanError("MAPPING_SCHEMA_CHANGED")
    if value.get("created_before_primary_access") is not True:
        raise BlindOrbitPlanError("MAPPING_NOT_PREACCESS")
    if any(value.get("observation_access", {}).values()):
        raise BlindOrbitPlanError("MAPPING_OBSERVATION_BOUNDARY_CHANGED")
    blindness = value.get("blindness_semantics")
    if not isinstance(blindness, Mapping):
        raise BlindOrbitPlanError("BLINDNESS_SEMANTICS_MISSING")
    expected_blindness = {
        "adversarial_repository_secrecy_claimed": False,
        "mapping_may_enter_scorer_process": False,
        "mapping_may_enter_scorer_receipt_before_scoring": False,
        "mapping_reveal_condition": (
            "ONLY_AFTER_OPAQUE_SCORE_RECEIPT_HASH_IS_PERSISTED"
        ),
        "scorer_receives_only_opaque_identifiers": True,
        "state": "INTERFACE_BLINDNESS_NOT_REPOSITORY_SECRECY",
    }
    if dict(blindness) != expected_blindness:
        raise BlindOrbitPlanError("BLINDNESS_SEMANTICS_CHANGED")
    rows = value.get("mapping")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise BlindOrbitPlanError("MAPPING_ROWS_MISSING")
    if len(rows) != 6 or not all(isinstance(row, Mapping) for row in rows):
        raise BlindOrbitPlanError("MAPPING_CARDINALITY_CHANGED")
    identifiers = tuple(str(row["opaque_id"]) for row in rows)
    if len(set(identifiers)) != 6 or any(not value.startswith("H_") for value in identifiers):
        raise BlindOrbitPlanError("OPAQUE_IDENTIFIERS_INVALID")
    expected_models = {
        "G22_RELATIVE_TO_G30",
        "G06_RELATIVE_TO_G30",
        "G14_RELATIVE_TO_G30",
        "G17_RELATIVE_TO_G30",
        "G19_RELATIVE_TO_G30",
        "PREFIX_AFFINE_ONLY",
    }
    if {str(row["model"]) for row in rows} != expected_models:
        raise BlindOrbitPlanError("MAPPING_MODEL_SET_CHANGED")
    if sum(row.get("model_class") == "NON_ORBITAL_NULL" for row in rows) != 1:
        raise BlindOrbitPlanError("AFFINE_NULL_CARDINALITY_CHANGED")
    return value, tuple(sorted(identifiers))


def _validate_qualification(
    outcome_path: Path, summary_path: Path
) -> tuple[dict[str, object], dict[str, object]]:
    outcome = _read_strict_json(outcome_path)
    if outcome.get("outcome") != "AMC_OBSERVER_QUALIFICATION_PASSED":
        raise BlindOrbitPlanError("AMC_QUALIFICATION_OUTCOME_CHANGED")
    if any(outcome.get("primary_doy221_access", {}).values()):
        raise BlindOrbitPlanError("AMC_QUALIFICATION_REOPENED_OLD_PRIMARY")
    if outcome.get("orbital_scores_produced") != 0:
        raise BlindOrbitPlanError("AMC_QUALIFICATION_SCORED_ORBIT")
    clauses = outcome.get("clause_states", {})
    for clause in (
        "artifact_materialization_and_hash",
        "core_phase_and_lli",
        "header_configuration_and_window",
        "same_path_code_witness",
    ):
        if clauses.get(clause) != "SATISFIED":
            raise BlindOrbitPlanError(f"AMC_QUALIFICATION_CHANGED:{clause}")
    summary = _read_strict_json(summary_path)
    if summary.get("full_joint_window") is not True:
        raise BlindOrbitPlanError("AMC_QUALIFICATION_WINDOW_CHANGED")
    if summary.get("observation_values_parsed") != 0:
        raise BlindOrbitPlanError("AMC_QUALIFICATION_VALUE_BOUNDARY_CHANGED")
    if summary.get("geometry_free_phase_health") != (
        "NOT_EVALUATED_BY_VALUE_BLIND_AUTHORITY"
    ):
        raise BlindOrbitPlanError("AMC_QUALIFICATION_HEALTH_BOUNDARY_CHANGED")
    return outcome, summary


def validate_parents(root: Path) -> dict[str, dict[str, object]]:
    root = Path(root)
    screen_path = _require_hash(root, SCREEN_NAME, SCREEN_SHA256)
    mapping_path = _require_hash(root, MAPPING_NAME, MAPPING_SHA256)
    _require_hash(root, PLAN_NAME, PLAN_SHA256)
    _require_hash(root, METADATA_NAME, METADATA_SHA256)
    qualification_path = _require_hash(root, QUALIFICATION_NAME, QUALIFICATION_SHA256)
    summary_path = _require_hash(
        root, QUALIFICATION_SUMMARY_NAME, QUALIFICATION_SUMMARY_SHA256
    )
    _require_hash(root, QUALIFICATION_COVERAGE_NAME, QUALIFICATION_COVERAGE_SHA256)
    screen, _ = _validate_screen(screen_path)
    _, identifiers = _validate_mapping(mapping_path)
    qualification, _ = _validate_qualification(qualification_path, summary_path)
    return {
        SCREEN_NAME: {
            "canonical_sha256": SCREEN_SHA256,
            "outcome": screen["outcome"],
            "role": "FROZEN_ORBIT_ONLY_DIFFICULT_FAMILY_SELECTION",
        },
        MAPPING_NAME: {
            "canonical_sha256": MAPPING_SHA256,
            "opaque_identifier_count": len(identifiers),
            "role": "PREACCESS_MAPPING_OUTSIDE_SCORER_INTERFACE",
        },
        PLAN_NAME: {
            "canonical_sha256": PLAN_SHA256,
            "role": "IMMUTABLE_PROSPECTIVE_MARKDOWN",
        },
        METADATA_NAME: {
            "canonical_sha256": METADATA_SHA256,
            "role": "HISTORICAL_AMC_CONFIGURATION_DESCRIPTION",
        },
        QUALIFICATION_NAME: {
            "canonical_sha256": QUALIFICATION_SHA256,
            "outcome": qualification["outcome"],
            "role": "DISTINCT_VALUE_BLIND_TRANSFORM_QUALIFICATION_DOY222",
        },
        QUALIFICATION_SUMMARY_NAME: {
            "canonical_sha256": QUALIFICATION_SUMMARY_SHA256,
            "role": "STRUCTURAL_QUALIFICATION_SUMMARY_NOT_DOY226_HEALTH",
        },
        QUALIFICATION_COVERAGE_NAME: {
            "canonical_sha256": QUALIFICATION_COVERAGE_SHA256,
            "role": "STRUCTURAL_STATES_ONLY",
        },
    }


def plan(root: Path) -> dict[str, object]:
    root = Path(root)
    parents = validate_parents(root)
    _, selected = _validate_screen(root / SCREEN_NAME)
    _, opaque_ids = _validate_mapping(root / MAPPING_NAME)
    alpha, beta = inherited.ionosphere_free_coefficients()
    result = {
        "schema": "gnss-blind-orbit-assignment-primary-plan-v1",
        "plan_version": PLAN_VERSION,
        "outcome": OUTCOME,
        "physical_question": (
            "CAN_AN_IDENTITY_BLIND_SCORER_PREFER_THE_G22_RELATIVE_G30_"
            "TRAJECTORY_WITHIN_THE_FROZEN_FIVE_ORBIT_FAMILY_AND_AFFINE_NULL"
        ),
        "new_information": (
            "WHETHER_REAL_HELDOUT_AMC_PHASE_SUPPORTS_ORBITALITY_AND_G22_"
            "SPECIFICITY_INSIDE_A_DIFFICULT_PREDECLARED_CANDIDATE_SET"
        ),
        "parents": parents,
        "observer": {
            "station": STATION,
            "latitude_deg": amc.STATION_LATITUDE_DEG,
            "longitude_deg": amc.STATION_LONGITUDE_DEG,
            "height_m": amc.STATION_HEIGHT_M,
            "receiver": "SEPT_POLARX5TR",
            "receiver_serial": "3013929",
            "receiver_version": "5.6.0",
            "antenna": "TPSCR.G5C NONE",
            "antenna_serial": "1364-10065",
            "role": "SAME_CHARACTERIZED_ROOT_NEW_ASSIGNMENT_QUESTION",
        },
        "primary_artifact": {
            "logical_product": PRIMARY_PRODUCT,
            "product_existence": "UNKNOWN_UNQUERIED",
            "directory_metadata_queried": False,
            "complete_sha256": "UNKNOWN_UNTIL_ONE_AUTHORIZED_MATERIALIZATION",
            "predeclared_body_transport": {
                "source": "GSSC_OFFICIAL_GLOBAL_DATA_CENTER",
                "web_root": PRIMARY_GSSC_WEB_ROOT,
                "directory": PRIMARY_GSSC_DIRECTORY,
                "filename": PRIMARY_PRODUCT,
                "maximum_attempts_before_complete_hash": 2,
                "retry_reasons": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
                "retry_after_complete_hash_or_decode": False,
            },
            "hash_before_header_or_record_decode": True,
            "fallback_product_date_station_window_or_archive": False,
        },
        "partition": {
            "time_system": "GPS",
            "raw_start": RAW_START_GPS,
            "raw_stop": RAW_STOP_GPS,
            "raw_epochs": RAW_EPOCHS,
            "cadence_s": STEP_S,
            "anchor_index": 0,
            "prefix_raw_indices_inclusive": [0, PREFIX_EPOCHS - 1],
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_raw_indices_inclusive": [PREFIX_EPOCHS, RAW_EPOCHS - 1],
            "heldout_start": HELDOUT_START_GPS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "window_shortening_interpolation_gap_bridging": "FORBIDDEN",
        },
        "measurement_packager": {
            "may_receive_prn_labels": True,
            "station_satellite_order": "AMC_G22_MINUS_AMC_G30",
            "per_satellite_phase_m": (
                "ALPHA*LAMBDA_L1*L1C_PLUS_BETA*LAMBDA_L2*L2W"
            ),
            "ionosphere_free_weights": {"L1C": alpha, "L2W": beta},
            "anchor": "SUBTRACT_RAW_INDEX_ZERO_ONLY",
            "output_to_scorer": "ONE_FINITE_UNLABELLED_COORDINATE_ARRAY",
            "may_select_model": False,
            "may_score": False,
        },
        "mapping_seal": {
            "filename": MAPPING_NAME,
            "canonical_sha256": MAPPING_SHA256,
            "opaque_ids": list(opaque_ids),
            "mapping_rows_exposed_in_plan_receipt": False,
            "mapping_may_enter_scorer_process": False,
            "mapping_reveal_condition": (
                "ONLY_AFTER_OPAQUE_SCORE_RECEIPT_HASH_IS_PERSISTED"
            ),
            "blindness_scope": "INTERFACE_NOT_ADVERSARIAL_REPOSITORY_SECRECY",
        },
        "scorer_contract": {
            "inputs": [
                "FINITE_UNLABELLED_OBSERVED_COORDINATE_139",
                "SIX_OPAQUE_MODEL_ARRAYS_139",
                "PREFIX_AND_HELDOUT_INDICES",
                "PAIRWISE_GUARD_M",
            ],
            "forbidden_inputs": [
                "SATELLITE_NAMES",
                "TARGET_ROLE",
                "MAPPING_SEAL_PATH_OR_CONTENT",
                "NAVIGATION_PARSER_OR_RECORDS",
                "OBSERVATION_DECODER_OR_PRODUCT_METADATA",
                "PRIMARY_OR_RESERVE_ROLE",
            ],
            "identical_loop_for_all_hypotheses": True,
            "per_hypothesis_prefix_fit": ["CONSTANT", "LINEAR_RATE"],
            "per_hypothesis_parameter_count": 2,
            "affine_null_model_array": "ZERO_ARRAY_IDENTICAL_INTERFACE",
            "heldout_refit": False,
            "free_time_phase": False,
            "time_warp": False,
            "interpolation": False,
            "candidate_dependent_complexity": False,
            "metric_order": ["PEAK_TO_PEAK_M", "RMS_M", "OPAQUE_ID"],
            "preference_rule": (
                "RUNNER_UP_MINUS_BEST_HELDOUT_PEAK_TO_PEAK_STRICTLY_"
                "GREATER_THAN_PAIRWISE_GUARD"
            ),
            "pairwise_guard_m": PAIRWISE_GUARD_M,
            "opaque_receipt_hash_before_mapping_reveal": True,
        },
        "admission": {
            "required_structure": [
                "EXACT_139_EPOCH_GPS_GRID_OR_DEVIATION_WITHIN_15_SECONDS",
                "NORMAL_EPOCH_FLAG_ZERO_AT_ALL_REQUIRED_EPOCHS",
                "L1C_L2W_C1C_C2W_PRESENT_ON_G22_AND_G30_AT_ALL_EPOCHS",
                "LLI_BLANK_OR_ZERO_ON_BOTH_PHASE_FIELDS_AT_ALL_EPOCHS",
                "HEADER_IDENTITY_INTERVAL_AND_TIME_OF_LAST_OBS_COVER_WINDOW",
                "NO_UNSUPPORTED_SCALE_PHASE_SHIFT_OR_TIME_TRANSFORM",
                "EVERY_TRANSFORM_INPUT_FINITE",
            ],
            "geometry_free_phase_health": {
                "maximum_absolute_second_difference_m": (
                    amc.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                ),
                "violation_outcome": "MEASUREMENT_INVALID",
            },
            "same_path_code_phase_witness": {
                "per_satellite_peak_to_peak_limit_m": (
                    amc.CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
                ),
                "missing_or_invalid_outcome": "MEASUREMENT_INVALID",
                "finite_over_limit_outcome": "NOT_DETECTABLE",
                "may_fit_or_select_model": False,
            },
            "event_time": {
                "maximum_absolute_grid_deviation_s": (
                    amc.MAXIMUM_EVENT_TIME_ERROR_S
                ),
                "direct_trajectory_envelope": True,
                "over_limit_outcome": "NOT_DETECTABLE",
            },
            "doy222_qualification_scope": (
                "PARSER_FIELD_FAMILY_AND_HISTORICAL_CONFIGURATION_ONLY_NOT_"
                "DOY226_EXISTENCE_COVERAGE_OR_HEALTH"
            ),
        },
        "detectability": {
            "candidate_family": list(CANDIDATE_FAMILY),
            "controlling_model": "PREFIX_AFFINE_ONLY",
            "controlling_model_only_separation_m": float(
                selected["affine_null"]["heldout_peak_to_peak_m"]
            ),
            "pairwise_guard_m": PAIRWISE_GUARD_M,
            "minimum_combined_remaining_margin_m": MINIMUM_COMBINED_MARGIN_M,
            "minimum_direct_shifted_elevation_deg": (
                MINIMUM_SHIFTED_ELEVATION_DEG
            ),
            "complete_window_required": True,
        },
        "terminal_outcomes": [
            "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "PRIMARY_DESCRIPTION_ERROR",
            "BLINDING_INVALID",
            "MEASUREMENT_INVALID",
            "NOT_DETECTABLE",
            "BOUNDED_TRUE_ORBIT_PREFERRED",
            "BOUNDED_ALTERNATIVE_ORBIT_PREFERRED",
            "FROZEN_AFFINE_NULL_PREFERRED",
            "AMBIGUOUS",
        ],
        "claim_scope": {
            "maximum_positive_claim": (
                "BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET"
            ),
            "not_targetless_identity": True,
            "not_free_orbit_recovery": True,
            "not_catalog_wide_uniqueness": True,
            "upstream_receiver_prn_correlation_remains": True,
        },
        "access_boundary": {
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
        },
        "next_maximum": "OFFLINE_OPAQUE_PREDICTION_BUNDLE_AND_SCORER_SEAL_REVIEW_ONLY",
        "stop": "DO_NOT_OPEN_PRIMARY_OR_BUILD_EXECUTOR",
        "new_gate_created": False,
        "generic_framework_created": False,
    }
    strict_json(result)
    return result


def plan_manifest_sha256(root: Path) -> str:
    return sha256(strict_json(plan(root)).encode("ascii")).hexdigest()


def write_receipt(root: Path) -> dict[str, object]:
    root = Path(root)
    value = plan(root)
    receipt = {
        **value,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "plan_manifest_sha256": plan_manifest_sha256(root),
    }
    output = root / RECEIPT_NAME
    if output.exists():
        raise BlindOrbitPlanError("PLAN_RECEIPT_ALREADY_EXISTS")
    output.write_bytes((strict_json(receipt, pretty=True) + "\n").encode("ascii"))
    return receipt


def cli_summary(value: Mapping[str, object], *, receipt_written: bool) -> dict[str, object]:
    """Return only non-sensitive execution state for terminal output."""
    manifest_hash = value.get("plan_manifest_sha256")
    if not isinstance(manifest_hash, str):
        manifest_hash = sha256(strict_json(value).encode("ascii")).hexdigest()
    access = value.get("access_boundary")
    if not isinstance(access, Mapping):
        raise BlindOrbitPlanError("ACCESS_BOUNDARY_MISSING")
    return {
        "outcome": value.get("outcome"),
        "plan_manifest_sha256": manifest_hash,
        "receipt_written": receipt_written,
        "access_boundary": dict(access),
    }


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    value = write_receipt(root) if args.write else plan(root)
    print(strict_json(cli_summary(value, receipt_written=args.write)))


if __name__ == "__main__":
    main()
