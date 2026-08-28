"""Offline prospective plan for the sealed AMC DOY221 observer replication.

This one-shot compiler binds only closed aggregate receipts and one immutable
Markdown plan.  It has no network client, observation decoder, primary payload
input, carrier-phase input, or scoring surface.
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
    gnss_double_difference_envelope as inherited,
)


PLAN_VERSION: Final = "amc-observer-doy221-prospective-plan-v1"
PLAN_NAME: Final = "AMC_OBSERVER_PRIMARY_PLAN.md"
PLAN_SHA256: Final = (
    "ee78c560725d3b73edd01303f5731afe7bd20ade8517556b6d12ed9227d5b3b6"
)
RECEIPT_NAME: Final = "AMC_OBSERVER_PRIMARY_PLAN_RECEIPT.json"
OUTCOME: Final = "AMC_OBSERVER_PRIMARY_PLAN_FROZEN"

GEOMETRY_NAME: Final = "GNSS_OBSERVER_TRANSFER_GEOMETRY_RECEIPT.json"
GEOMETRY_SHA256: Final = (
    "4982a32459d880a17abab9cf726ee6e8f6383e1d0b570abbf77fd07341d459d5"
)
METADATA_NAME: Final = "AMC_OBSERVER_REPLICATION_METADATA_REPORT.md"
METADATA_SHA256: Final = (
    "e0c8d9496448ead1ac5bfe07cd17a0f25623853c26c70b6f4a1edb32913929fa"
)
QUALIFICATION_NAME: Final = "AMC_OBSERVER_QUALIFICATION_OUTCOME.json"
QUALIFICATION_SHA256: Final = (
    "8c543bbd5d00128c70feab66574df4b878983f036daab932ba7cb6714ee829c4"
)
QUALIFICATION_SUMMARY_NAME: Final = "AMC_OBSERVER_QUALIFICATION_SUMMARY.json"
QUALIFICATION_SUMMARY_SHA256: Final = (
    "3e1be4ca9ef741690af99d6206ff94719fbae32b97fe6792034ac87ac9efca69"
)
QUALIFICATION_COVERAGE_NAME: Final = "AMC_OBSERVER_QUALIFICATION_COVERAGE.jsonl"
QUALIFICATION_COVERAGE_SHA256: Final = (
    "bfaccd2ca742f329fe56d6df5e88774c73790040eca2bee5eb3c6ca907718077"
)

STATION: Final = "AMC400USA"
STATION_LATITUDE_DEG: Final = 38.803125
STATION_LONGITUDE_DEG: Final = -104.524597
STATION_HEIGHT_M: Final = 1911.3941
TARGET: Final = "G22"
REFERENCE: Final = "G30"
WRONG_ORBITS: Final = ("G01", "G14", "G17")

PRIMARY_PRODUCT: Final = "AMC400USA_R_20262210000_01D_30S_MO.crx.gz"
PRIMARY_AUTHORITY_URL: Final = (
    "https://cddis.nasa.gov/archive/gnss/data/daily/2026/221/26d/" + PRIMARY_PRODUCT
)
PRIMARY_DESCRIPTIVE_BYTES: Final = 3_415_979
PRIMARY_DESCRIPTIVE_LAST_MODIFIED: Final = "2026-08-10 03:01:38"
PRIMARY_DIRECTORY_RESPONSE_SHA256: Final = (
    "1f30600686f3ae8e466bcc796e3538bcdf601d2d7e2d676f839357c320d600b5"
)
PRIMARY_GSSC_DIRECTORY: Final = "/gnss/data/daily/2026/221"
PRIMARY_GSSC_WEB_ROOT: Final = "https://gssc.esa.int/webftp/"

RAW_START_GPS: Final = "2026-08-09T05:41:30 GPS"
RAW_STOP_GPS: Final = "2026-08-09T06:50:30 GPS"
HELDOUT_START_GPS: Final = "2026-08-09T06:21:00 GPS"
RAW_EPOCHS: Final = 139
STEP_S: Final = 30.0
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
ANCHOR_INDEX: Final = 0
HELDOUT_START_INDEX: Final = 79
MAXIMUM_EVENT_TIME_ERROR_S: Final = 15.0

GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
CODE_CHIP_RATE_HZ: Final = 1_023_000.0
CODE_CHIP_RANGE_M: Final = SPEED_OF_LIGHT_M_S / CODE_CHIP_RATE_HZ
CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M: Final = 1_250.0
CODE_PHASE_COORDINATE_PTP_BOUND_M: Final = 2.0 * CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
PAIRWISE_MULTIPLIER: Final = inherited.PAIRWISE_ENVELOPE_MULTIPLIER

FROZEN_CONTROLLING_SEPARATION_M: Final = 162_247.192926376
FROZEN_AFFINE_RATE_M_S: Final = -410.277100928825
OLD_ONE_MODEL_ENVELOPE_M: Final = 1_173.850617323699
OLD_HARDWARE_TERM_M: Final = 4.0
REVISED_ONE_MODEL_ENVELOPE_M: Final = (
    OLD_ONE_MODEL_ENVELOPE_M - OLD_HARDWARE_TERM_M + CODE_PHASE_COORDINATE_PTP_BOUND_M
)
REVISED_PAIRWISE_GUARD_M: Final = PAIRWISE_MULTIPLIER * REVISED_ONE_MODEL_ENVELOPE_M
REVISED_REMAINING_MARGIN_M: Final = (
    FROZEN_CONTROLLING_SEPARATION_M - REVISED_PAIRWISE_GUARD_M
)


class AmcPlanError(ValueError):
    """A frozen parent, physical boundary, or plan invariant changed."""


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
        raise AmcPlanError(f"PARENT_NOT_OBJECT:{path.name}")
    return value


def _require_hash(root: Path, name: str, digest: str) -> Path:
    path = Path(root) / name
    if not path.is_file() or canonical_sha256(path) != digest:
        raise AmcPlanError(f"FROZEN_PARENT_CHANGED:{name}")
    return path


def _close(actual: object, expected: float, label: str) -> None:
    if not isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-9):
        raise AmcPlanError(f"FROZEN_GEOMETRY_CHANGED:{label}")


def _geometry_selection(geometry: Mapping[str, object]) -> Mapping[str, object]:
    shortlist = geometry.get("shortlist")
    if not isinstance(shortlist, Sequence) or isinstance(shortlist, (str, bytes)):
        raise AmcPlanError("GEOMETRY_SHORTLIST_MISSING")
    matches = [
        row
        for row in shortlist
        if isinstance(row, Mapping)
        and row.get("station_id") == STATION
        and row.get("doy") == 221
    ]
    if len(matches) != 1:
        raise AmcPlanError("FROZEN_AMC_SELECTION_NOT_UNIQUE")
    return matches[0]


def validate_parents(root: Path) -> dict[str, dict[str, object]]:
    root = Path(root)
    geometry_path = _require_hash(root, GEOMETRY_NAME, GEOMETRY_SHA256)
    _require_hash(root, METADATA_NAME, METADATA_SHA256)
    qualification_path = _require_hash(root, QUALIFICATION_NAME, QUALIFICATION_SHA256)
    summary_path = _require_hash(
        root, QUALIFICATION_SUMMARY_NAME, QUALIFICATION_SUMMARY_SHA256
    )
    _require_hash(root, QUALIFICATION_COVERAGE_NAME, QUALIFICATION_COVERAGE_SHA256)
    if PLAN_SHA256 == "TO_BE_FROZEN":
        raise AmcPlanError("PLAN_MARKDOWN_HASH_NOT_FROZEN")
    _require_hash(root, PLAN_NAME, PLAN_SHA256)

    geometry = _read_strict_json(geometry_path)
    if geometry.get("outcome") != "OBSERVER_TRANSFER_GEOMETRY_SHORTLISTED":
        raise AmcPlanError("GEOMETRY_OUTCOME_CHANGED")
    selected = _geometry_selection(geometry)
    exact = {
        "station_id": STATION,
        "doy": 221,
        "raw_start_gps": RAW_START_GPS,
        "raw_stop_gps": RAW_STOP_GPS,
        "heldout_start_gps": HELDOUT_START_GPS,
        "controlling_null": "FROZEN_AFFINE_NULL",
    }
    if any(selected.get(key) != value for key, value in exact.items()):
        raise AmcPlanError("FROZEN_AMC_SELECTION_CHANGED")
    _close(
        selected.get("controlling_heldout_separation_m"),
        FROZEN_CONTROLLING_SEPARATION_M,
        "CONTROLLING_SEPARATION",
    )
    _close(
        selected.get("frozen_affine_rate_m_s"),
        FROZEN_AFFINE_RATE_M_S,
        "AFFINE_RATE",
    )
    _close(
        selected.get("one_model_physical_envelope_m"),
        OLD_ONE_MODEL_ENVELOPE_M,
        "ONE_MODEL_ENVELOPE",
    )
    if geometry.get("prospective_plan_frozen") is not False:
        raise AmcPlanError("GEOMETRY_ALREADY_PROMOTED_TO_PLAN")
    if any(geometry.get("observation_access", {}).values()):
        raise AmcPlanError("GEOMETRY_OBSERVATION_BOUNDARY_CHANGED")

    qualification = _read_strict_json(qualification_path)
    if qualification.get("outcome") != "AMC_OBSERVER_QUALIFICATION_PASSED":
        raise AmcPlanError("QUALIFICATION_OUTCOME_CHANGED")
    if any(qualification.get("primary_doy221_access", {}).values()):
        raise AmcPlanError("PRIMARY_WAS_OPENED_DURING_QUALIFICATION")
    if qualification.get("orbital_scores_produced") != 0:
        raise AmcPlanError("QUALIFICATION_PRODUCED_ORBITAL_SCORE")
    clauses = qualification.get("clause_states", {})
    for clause in (
        "artifact_materialization_and_hash",
        "core_phase_and_lli",
        "header_configuration_and_window",
        "same_path_code_witness",
    ):
        if clauses.get(clause) != "SATISFIED":
            raise AmcPlanError(f"QUALIFICATION_CLAUSE_CHANGED:{clause}")

    summary = _read_strict_json(summary_path)
    if summary.get("full_joint_window") is not True:
        raise AmcPlanError("QUALIFICATION_WINDOW_CHANGED")
    if summary.get("observation_values_parsed") != 0:
        raise AmcPlanError("QUALIFICATION_VALUE_BOUNDARY_CHANGED")
    if summary.get("geometry_free_phase_health") != (
        "NOT_EVALUATED_BY_VALUE_BLIND_AUTHORITY"
    ):
        raise AmcPlanError("QUALIFICATION_HEALTH_BOUNDARY_CHANGED")

    return {
        GEOMETRY_NAME: {
            "canonical_sha256": GEOMETRY_SHA256,
            "outcome": geometry["outcome"],
            "role": "FROZEN_ORBIT_ONLY_SELECTION",
        },
        METADATA_NAME: {
            "canonical_sha256": METADATA_SHA256,
            "role": "FROZEN_PREACCESS_DESCRIPTION",
        },
        QUALIFICATION_NAME: {
            "canonical_sha256": QUALIFICATION_SHA256,
            "outcome": qualification["outcome"],
            "role": "DISTINCT_VALUE_BLIND_QUALIFICATION",
        },
        QUALIFICATION_SUMMARY_NAME: {
            "canonical_sha256": QUALIFICATION_SUMMARY_SHA256,
            "role": "STRUCTURAL_QUALIFICATION_SUMMARY",
        },
        QUALIFICATION_COVERAGE_NAME: {
            "canonical_sha256": QUALIFICATION_COVERAGE_SHA256,
            "role": "STRUCTURAL_STATES_ONLY",
        },
        PLAN_NAME: {
            "canonical_sha256": PLAN_SHA256,
            "role": "IMMUTABLE_PROSPECTIVE_MARKDOWN",
        },
    }


def _physical_terms(root: Path) -> list[dict[str, object]]:
    geometry = _read_strict_json(Path(root) / GEOMETRY_NAME)
    selected = _geometry_selection(geometry)
    result: list[dict[str, object]] = []
    replaced = 0
    for source in selected["physical_terms"]:
        term = dict(source)
        if term.get("term") == "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE":
            term = {
                "term": "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE",
                "state": "OBSERVABLE_WITH_FIXED_FULL_WINDOW_LIMIT",
                "provenance": "FROZEN_BEFORE_PRIMARY_ACCESS",
                "basis": (
                    "PER_SATELLITE_ANCHORED_IONOSPHERE_FREE_PHASE_MINUS_CODE_"
                    "PEAK_TO_PEAK_LIMIT"
                ),
                "code_chip_rate_hz": CODE_CHIP_RATE_HZ,
                "code_chip_range_m": CODE_CHIP_RANGE_M,
                "ionosphere_free_weighted_one_chip_upper_round_m": (
                    CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
                ),
                "per_satellite_peak_to_peak_limit_m": (
                    CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M
                ),
                "two_satellite_coordinate_peak_to_peak_bound_m": (
                    CODE_PHASE_COORDINATE_PTP_BOUND_M
                ),
                "heldout_peak_to_peak_bound_m": (CODE_PHASE_COORDINATE_PTP_BOUND_M),
                "pairwise_contribution_m": (
                    PAIRWISE_MULTIPLIER * CODE_PHASE_COORDINATE_PTP_BOUND_M
                ),
                "threshold_learned_from_primary": False,
                "witness_may_adjust_orbit_score": False,
            }
            replaced += 1
        result.append(term)
    if replaced != 1:
        raise AmcPlanError("HARDWARE_TERM_TOPOLOGY_CHANGED")
    return result


def plan(root: Path) -> dict[str, object]:
    parents = validate_parents(root)
    alpha, beta = inherited.ionosphere_free_coefficients()
    terms = _physical_terms(root)
    one_model = sum(float(term["heldout_peak_to_peak_bound_m"]) for term in terms)
    pairwise = PAIRWISE_MULTIPLIER * one_model
    margin = FROZEN_CONTROLLING_SEPARATION_M - pairwise
    _close(one_model, REVISED_ONE_MODEL_ENVELOPE_M, "REVISED_ONE_MODEL_ENVELOPE")
    _close(pairwise, REVISED_PAIRWISE_GUARD_M, "REVISED_PAIRWISE_GUARD")
    _close(margin, REVISED_REMAINING_MARGIN_M, "REVISED_MARGIN")
    if margin <= 0.0:
        raise AmcPlanError("REVISED_PHYSICAL_MARGIN_NOT_POSITIVE")

    value = {
        "schema": "amc-observer-primary-plan-v1",
        "plan_version": PLAN_VERSION,
        "outcome": OUTCOME,
        "physical_question": (
            "DOES_FROZEN_BROADCAST_G22_RELATIVE_TO_G30_GEOMETRY_PREDICT_"
            "THE_HELDOUT_AMC_SINGLE_OBSERVER_PHASE_COORDINATE_BETTER_THAN_"
            "THE_FROZEN_AFFINE_AND_WRONG_ORBIT_ALTERNATIVES"
        ),
        "new_information": (
            "WHETHER_THE_PIE_HELDOUT_ORBITAL_PREFERENCE_REPLICATES_ON_A_"
            "DISTINCT_OBSERVER_AND_PASS_WITHOUT_REUSING_THE_PIE_OUTCOME"
        ),
        "why_existing_results_cannot_answer": (
            "THE_REAL_GEOMETRY_RESULT_HAS_NO_MEASUREMENT_AND_THE_DOY221_"
            "QUALIFICATION_HAS_NO_ORBITAL_PREDICTION_OR_SCORE"
        ),
        "parents": parents,
        "observer": {
            "station": STATION,
            "latitude_deg": STATION_LATITUDE_DEG,
            "longitude_deg": STATION_LONGITUDE_DEG,
            "height_m": STATION_HEIGHT_M,
            "receiver": "SEPT POLARX5TR",
            "receiver_serial": "3013929",
            "receiver_version": "5.6.0",
            "antenna": "TPSCR.G5C NONE",
            "antenna_serial": "1364-10065",
            "role": "INDEPENDENT_OBSERVER_AND_PASS_REPLICATION_OF_PIE",
            "shared_receiver_family_with_pie": True,
            "independence_limit": (
                "DISTINCT_SERIAL_ANTENNA_MONUMENT_CLOCK_FIRMWARE_AND_PASS_BUT_"
                "SAME_POLARX5TR_RECEIVER_FAMILY"
            ),
        },
        "primary_artifact": {
            "logical_product": PRIMARY_PRODUCT,
            "authority_url": PRIMARY_AUTHORITY_URL,
            "preexisting_directory_description": {
                "bytes": PRIMARY_DESCRIPTIVE_BYTES,
                "last_modified": PRIMARY_DESCRIPTIVE_LAST_MODIFIED,
                "directory_response_sha256": PRIMARY_DIRECTORY_RESPONSE_SHA256,
                "directory_md5_field": "1",
                "directory_md5_field_is_checksum": False,
                "identity_authority": False,
            },
            "predeclared_body_transport": {
                "source": "GSSC_OFFICIAL_GLOBAL_DATA_CENTER",
                "web_root": PRIMARY_GSSC_WEB_ROOT,
                "directory": PRIMARY_GSSC_DIRECTORY,
                "filename": PRIMARY_PRODUCT,
                "maximum_attempts_before_complete_hash": 2,
                "retry_reasons": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
                "retry_after_complete_hash_or_decode": False,
            },
            "complete_sha256": "UNKNOWN_UNTIL_ONE_AUTHORIZED_MATERIALIZATION",
            "hash_before_header_or_record_decode": True,
            "fallback_product_date_station_or_window": False,
        },
        "partition": {
            "time_system": "GPS",
            "raw_start": RAW_START_GPS,
            "raw_stop": RAW_STOP_GPS,
            "raw_epochs": RAW_EPOCHS,
            "cadence_s": STEP_S,
            "anchor_index": ANCHOR_INDEX,
            "witness_prefix_raw_indices_inclusive": [0, 78],
            "witness_prefix_epochs": PREFIX_EPOCHS,
            "heldout_raw_indices_inclusive": [79, 138],
            "heldout_start": HELDOUT_START_GPS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "window_shortening_interpolation_gap_bridging": "FORBIDDEN",
        },
        "coordinate": {
            "per_satellite_phase_m": ("ALPHA*LAMBDA_L1*L1C_PLUS_BETA*LAMBDA_L2*L2W"),
            "ionosphere_free_weights": {"L1C": alpha, "L2W": beta},
            "station_satellite_order": "AMC_G22_MINUS_AMC_G30",
            "anchor": "SUBTRACT_RAW_INDEX_ZERO_ONLY",
            "unit": "METER_EQUIVALENT_CONTINUOUS_CARRIER_PHASE",
            "free_constant": False,
            "free_rate": False,
            "free_time_phase": False,
            "suffix_fit": False,
        },
        "hypotheses": {
            "orbital": "BROADCAST_G22_RELATIVE_TO_G30",
            "frozen_affine": {
                "zero_intercept_at_anchor": True,
                "rate_m_s": FROZEN_AFFINE_RATE_M_S,
                "rate_source": "TARGET_PREDICTION_ONLY_BEFORE_OBSERVATION",
            },
            "wrong_orbits_replacing_target_only": list(WRONG_ORBITS),
            "reference_remains": REFERENCE,
            "same_grid_anchor_transform_and_envelope": True,
        },
        "admission": {
            "required_structure": [
                "EXACT_139_EPOCH_GPS_GRID_OR_DEVIATION_WITHIN_15_SECOND_BOUND",
                "NORMAL_EPOCH_FLAG_ZERO_AT_ALL_REQUIRED_EPOCHS",
                "L1C_L2W_C1C_C2W_PRESENT_ON_G22_AND_G30_AT_ALL_EPOCHS",
                "LLI_BLANK_OR_ZERO_ON_BOTH_PHASE_FIELDS_AT_ALL_EPOCHS",
                "NO_UNSUPPORTED_SCALE_OR_TIME_TRANSFORM",
                "HEADER_IDENTITY_AND_TIME_OF_LAST_OBS_COVER_FROZEN_WINDOW",
            ],
            "geometry_free_phase_health": {
                "coordinate": "LAMBDA_L1_L1C_MINUS_LAMBDA_L2_L2W",
                "maximum_absolute_second_difference_m": (
                    GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                ),
                "evaluated_per_satellite_over_all_137_second_differences": True,
                "violation_outcome": "MEASUREMENT_INVALID",
            },
            "same_path_code_phase_witness": {
                "per_satellite_coordinate": (
                    "ANCHOR(IF_PHASE(L1C,L2W)-IF_CODE(C1C,C2W))"
                ),
                "required_coverage_fraction": 1.0,
                "peak_to_peak_limit_m": (CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M),
                "evaluated_on_prefix_and_heldout_without_threshold_change": True,
                "may_fit_or_select_orbit": False,
                "missing_or_invalid_outcome": "MEASUREMENT_INVALID",
                "finite_but_over_limit_outcome": "NOT_DETECTABLE",
            },
            "event_time": {
                "maximum_absolute_grid_deviation_s": MAXIMUM_EVENT_TIME_ERROR_S,
                "direct_trajectory_envelope_not_local_slope": True,
                "over_limit_outcome": "NOT_DETECTABLE",
            },
            "optional_signal_strength": ["S1C", "S2W"],
        },
        "physical_envelope": {
            "terms": terms,
            "old_geometry_one_model_envelope_m": OLD_ONE_MODEL_ENVELOPE_M,
            "old_unwitnessed_hardware_term_reused": False,
            "one_model_envelope_m": one_model,
            "pairwise_decision_guard_m": pairwise,
            "controlling_affine_separation_m": (FROZEN_CONTROLLING_SEPARATION_M),
            "remaining_margin_m": margin,
            "negative_result_interpretable_after_all_admission_clauses": True,
        },
        "scoring": {
            "observed_coordinate_anchor": "RAW_INDEX_ZERO_ONLY",
            "heldout_metric_order": ["PEAK_TO_PEAK_M", "RMS_M", "NAME"],
            "preference_rule": (
                "RUNNER_UP_MINUS_BEST_HELDOUT_PEAK_TO_PEAK_STRICTLY_GREATER_"
                "THAN_PAIRWISE_DECISION_GUARD"
            ),
            "nuisance_fit_parameters": 0,
            "prefix_may_fit_or_select_model": False,
            "heldout_may_change_threshold_model_or_transform": False,
        },
        "future_outcomes": [
            "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "PRIMARY_DESCRIPTION_ERROR",
            "MEASUREMENT_INVALID",
            "NOT_DETECTABLE",
            "AMC_HELD_OUT_ORBITAL_MODEL_PREFERRED",
            "FROZEN_AFFINE_NULL_PREFERRED",
            "WRONG_ORBIT_G01_PREFERRED",
            "WRONG_ORBIT_G14_PREFERRED",
            "WRONG_ORBIT_G17_PREFERRED",
            "AMBIGUOUS",
        ],
        "claim_scope": {
            "maximum_positive_claim": (
                "INDEPENDENT_OBSERVER_AND_PASS_REPLICATION_FOR_THIS_ORBIT_"
                "SIGNAL_FAMILY"
            ),
            "not_identity_evidence": True,
            "not_orbit_recovery": True,
            "not_generalized_beyond_amc_doy221": True,
            "shared_receiver_family_limits_hardware_diversity": True,
        },
        "access_boundary": {
            "this_plan_network_requests": 0,
            "primary_headers_opened": 0,
            "primary_payload_bytes": 0,
            "primary_observation_values": 0,
            "orbital_scores": 0,
            "executor_present": False,
            "execution_authority": False,
        },
        "next_maximum": "OFFLINE_EXACT_HASH_PREDICTION_SEAL_REVIEW_ONLY",
        "stop": "DO_NOT_OPEN_PRIMARY_OR_BUILD_EXECUTOR",
        "new_gate_created": False,
        "generic_framework_created": False,
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path) -> str:
    return sha256(strict_json(plan(root)).encode("ascii")).hexdigest()


def receipt(root: Path) -> dict[str, object]:
    return {
        "schema": "amc-observer-primary-plan-receipt-v1",
        "plan_version": PLAN_VERSION,
        "outcome": OUTCOME,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "plan_markdown": {
            "name": PLAN_NAME,
            "canonical_sha256": PLAN_SHA256,
        },
        "manifest_sha256": manifest_sha256(root),
        "plan": plan(root),
        "primary_access": {
            "headers": 0,
            "payload_bytes": 0,
            "observation_values": 0,
        },
        "orbital_scores_produced": 0,
        "next_authority": "OFFLINE_PREDICTION_SEAL_REVIEW_ONLY",
    }


def write_receipt(root: Path) -> Path:
    output = Path(root) / RECEIPT_NAME
    if output.exists():
        raise AmcPlanError("PLAN_RECEIPT_ALREADY_EXISTS")
    output.write_text(
        strict_json(receipt(root), pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    parser.add_argument("--write-receipt", action="store_true")
    args = parser.parse_args(argv)
    value = receipt(args.output_directory)
    output = None
    if args.write_receipt:
        output = write_receipt(args.output_directory)
    public_summary = {
        "outcome": value["outcome"],
        "manifest_sha256": value["manifest_sha256"],
        "primary_access": value["primary_access"],
        "orbital_scores_produced": value["orbital_scores_produced"],
        "next_authority": value["next_authority"],
        "receipt_written": output is not None,
        "receipt_name": output.name if output is not None else None,
    }
    print(strict_json(public_summary, pretty=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
