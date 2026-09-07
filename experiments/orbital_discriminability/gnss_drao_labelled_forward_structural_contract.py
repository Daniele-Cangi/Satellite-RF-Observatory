"""Freeze the unopened DRAO DOY237 labelled-forward structural contract.

This module has no network client, product locator, observation decoder,
measurement-value input or orbital scoring surface.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isclose
from pathlib import Path
import subprocess
from typing import Final, Mapping

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_physical_envelope as envelope,
)


CONTRACT_VERSION: Final = "gnss-drao-labelled-forward-structural-contract-v1"
CONTRACT_STATE: Final = "DRAO_LABELLED_FORWARD_STRUCTURAL_CONTRACT_FROZEN_UNOPENED"
MARKDOWN_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_CONTRACT.md"
MARKDOWN_SHA256: Final = "d4357f6eac7382bedd4bd7cf3ba2ed82fc767b0d742ef0c5cd0912f7ce0b849d"
ENVELOPE_NAME: Final = envelope.RECEIPT_NAME
ENVELOPE_SHA256: Final = "7aa7f2f28a23b4c55dc0f0e2348e53a84bceb6d7917dbacf0e6c74f1d5d72f91"
ROOT_METADATA_NAME: Final = "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
ROOT_METADATA_SHA256: Final = "24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c"
OUTPUT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_CONTRACT.json"

STATION: Final = "DRAO00CAN"
DOMES: Final = "40105M002"
SATELLITES: Final = envelope.CODEBOOK
RAW_START_GPS: Final = "2026-08-25T04:55:00 GPS"
RAW_STOP_GPS: Final = "2026-08-25T06:04:00 GPS"
HELDOUT_START_GPS: Final = "2026-08-25T05:34:30 GPS"
RAW_EPOCHS: Final = envelope.screen.RAW_EPOCHS
PREFIX_EPOCHS: Final = envelope.screen.PREFIX_EPOCHS
HELDOUT_EPOCHS: Final = envelope.screen.HELDOUT_EPOCHS
STEP_S: Final = envelope.screen.STEP_S

CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
OPTIONAL_DIAGNOSTICS: Final = ("S1C", "S2W")
ALLOWED_FIELD_STATES: Final = (
    "PRESENT",
    "BLANK",
    "TRAILING_FIELD_OMITTED",
    "CONTINUATION_SUPPORTED",
    "CONTINUATION_UNSUPPORTED",
    "RECORD_INVALID",
)


class DraoStructuralContractError(ValueError):
    """A frozen parent, structural clause or access boundary changed."""


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


def _reject_nonfinite(token: str) -> object:
    raise DraoStructuralContractError(f"NONFINITE_FROZEN_INPUT:{token}")


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"), parse_constant=_reject_nonfinite
    )
    if not isinstance(value, dict):
        raise DraoStructuralContractError(f"NOT_JSON_OBJECT:{Path(path).name}")
    return value


def verify_authorities(root: Path) -> dict[str, dict[str, object]]:
    base = Path(root)
    expected = {
        MARKDOWN_NAME: MARKDOWN_SHA256,
        ENVELOPE_NAME: ENVELOPE_SHA256,
        ROOT_METADATA_NAME: ROOT_METADATA_SHA256,
    }
    actual = {name: canonical_sha256(base / name) for name in expected}
    if actual != expected:
        changed = sorted(name for name in expected if actual.get(name) != expected[name])
        raise DraoStructuralContractError(
            f"FROZEN_AUTHORITY_CHANGED:{','.join(changed)}"
        )

    physical = _read_json(base / ENVELOPE_NAME)
    if physical.get("outcome") != envelope.OUTCOME_ADMITTED:
        raise DraoStructuralContractError("PHYSICAL_MARGIN_NOT_ADMITTED")
    if physical.get("geometry", {}).get("codebook") != list(SATELLITES):
        raise DraoStructuralContractError("PHYSICAL_CODEBOOK_CHANGED")
    if physical.get("geometry", {}).get("raw_start_gps") != RAW_START_GPS:
        raise DraoStructuralContractError("PHYSICAL_WINDOW_CHANGED")
    if any(int(value) != 0 for value in physical["observation_access"].values()):
        raise DraoStructuralContractError("PHYSICAL_AUDIT_USED_OBSERVATION")
    if physical.get("primary_selected") is not False:
        raise DraoStructuralContractError("PARENT_SELECTED_PRIMARY")

    metadata = _read_json(base / ROOT_METADATA_NAME)
    candidates = metadata.get("candidate_set")
    drao = [row for row in candidates if row.get("station_id") == STATION]
    if len(drao) != 1:
        raise DraoStructuralContractError("DRAO_ROOT_METADATA_MISSING")
    row = drao[0]
    expected_root = {
        "domes": DOMES,
        "receiver": "SEPT POLARX5 - 5.2.0",
        "antenna": "TWIVC6050 - SCIS",
        "station_log_sha256": "2d738f85955f5896c999ed5c1cd42c034b825ccce1e153becc24210a015f9d3d",
    }
    if any(row.get(key) != value for key, value in expected_root.items()):
        raise DraoStructuralContractError("DRAO_ROOT_METADATA_CHANGED")

    return {
        name: {
            "canonical_sha256": digest,
            "role": (
                "IMMUTABLE_HUMAN_CONTRACT"
                if name == MARKDOWN_NAME
                else "ADMITTED_PHYSICAL_ENVELOPE"
                if name == ENVELOPE_NAME
                else "INDEPENDENT_STATION_ROOT_METADATA"
            ),
        }
        for name, digest in expected.items()
    }


def contract(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    authorities = verify_authorities(base)
    physical = _read_json(base / ENVELOPE_NAME)
    physical_envelope = physical["envelope"]
    value = {
        "schema": "gnss-drao-labelled-forward-structural-contract-v1",
        "version": CONTRACT_VERSION,
        "state": CONTRACT_STATE,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "authorities": authorities,
        "physical_question": (
            "CAN_ONE_DRAO_DOY237_RINEX_OBSERVATION_PRESERVE_THE_SIX_"
            "PREDECLARED_LABELLED_PHASE_PATHS_OVER_THE_COMPLETE_FROZEN_WINDOW"
        ),
        "new_information_if_executed": (
            "WHETHER_THE_REAL_MEASUREMENT_PATH_HAS_THE_FIELD_TIME_AND_"
            "CONTINUITY_TOPOLOGY_REQUIRED_BY_THE_FIXED_SIX_TRACK_COORDINATE"
        ),
        "why_existing_cannot_answer": (
            "THE_ADMITTED_ORBIT_ONLY_ENVELOPE_HAS_NO_RECEIVER_HEADER_EPOCH_"
            "RECORD_OBSERVATION_IDENTITY_OR_LOSS_OF_LOCK_STATE"
        ),
        "minimum_experiment": (
            "ONE_COMPLETE_VALUE_BLIND_STRUCTURAL_SCAN_OF_ONE_LATER_SELECTED_"
            "DRAO_DOY237_30_SECOND_MIXED_OBSERVATION_PRODUCT"
        ),
        "stop_condition": (
            "ONE_STRUCTURAL_OUTCOME_WITH_ALL_PHYSICAL_AND_ORBITAL_CLAUSES_NOT_EVALUATED"
        ),
        "candidate": {
            "station": STATION,
            "domes": DOMES,
            "doy": envelope.DOY,
            "gps_date": envelope.GPS_DATE,
            "logical_product": "DRAO_DOY237_DAILY_30S_MIXED_GPS_OBSERVATION",
            "artifact_selected": False,
            "artifact_filename": None,
            "locator": None,
            "transport_bytes": None,
            "transport_sha256": None,
            "decoded_sha256": None,
            "network_authority": False,
            "payload_authority": False,
            "fallback_product": False,
            "possible_primary_only_after_integrated_proof_freeze": True,
        },
        "station_root": {
            "receiver_type": "SEPT POLARX5",
            "receiver_version": "5.2.0",
            "antenna_type": "TWIVC6050",
            "radome": "SCIS",
            "station_log_sha256": "2d738f85955f5896c999ed5c1cd42c034b825ccce1e153becc24210a015f9d3d",
            "header_must_match": True,
        },
        "window": {
            "time_system": "GPS",
            "raw_start": RAW_START_GPS,
            "raw_stop": RAW_STOP_GPS,
            "heldout_start": HELDOUT_START_GPS,
            "cadence_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "satellites": list(SATELLITES),
            "required_satellite_epoch_pairs": RAW_EPOCHS * len(SATELLITES),
            "event_time_bound_s": [-15.0, 15.0],
            "window_shortening": "FORBIDDEN",
        },
        "header_admission": {
            "container": "RINEX3_GPS_OBSERVATION",
            "gzip_allowed": True,
            "hatanaka_allowed": True,
            "complete_transport_hash_before_decompression": True,
            "complete_decoded_hash_before_record_traversal": True,
            "requires": [
                "MARKER_SITE_AND_DOMES_MATCH_DRAO00CAN_40105M002",
                "RECEIVER_MATCHES_SEPT_POLARX5_5_2_0",
                "ANTENNA_MATCHES_TWIVC6050_SCIS",
                "GPS_TIME_SYSTEM",
                "TIME_OF_FIRST_OBS_COVERS_WINDOW_START",
                "TIME_OF_LAST_OBS_COVERS_WINDOW_STOP",
                "INTERVAL_EQUALS_30_SECONDS",
                "GPS_DECLARATIONS_INCLUDE_L1C_L2W_C1C_C2W",
                "SCALE_PHASE_SHIFT_AND_CLOCK_OFFSET_SEMANTICS_SUPPORTED",
            ],
            "spec_defined_absence_is_not_unsupported_declaration": True,
        },
        "field_roles": {
            "core_phase_coordinate": list(CORE_PHASE),
            "cycle_slip_and_continuity": ["L1C_LLI", "L2W_LLI", "EPOCH_GRID"],
            "same_path_code_witness": list(SAME_PATH_CODE),
            "optional_diagnostics": list(OPTIONAL_DIAGNOSTICS),
        },
        "structural_scan": {
            "scope": "EVERY_REQUIRED_STATION_EPOCH_SATELLITE_FIELD_TUPLE",
            "complete_window_scan_even_after_first_failure": True,
            "allowed_field_states": list(ALLOWED_FIELD_STATES),
            "required_terminal_field_state": "PRESENT",
            "required_fields_each_satellite_epoch": list(CORE_PHASE + SAME_PATH_CODE),
            "lli_allowed_values_when_phase_present": [0, None],
            "normal_epoch_flag": 0,
            "exact_grid_required": True,
            "extra_tracks": "DESCRIPTIVE_NOT_FATAL_NOT_SCORED",
            "required_prn_substitution": "FORBIDDEN",
            "interpolation": "FORBIDDEN",
            "gap_bridging": "FORBIDDEN",
            "segment_reselection": "FORBIDDEN",
        },
        "physical_clauses_deferred_not_satisfied": {
            "geometry_free_phase_continuity": {
                "state": "NOT_EVALUATED",
                "future_limit_m": envelope.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
            },
            "phase_minus_code_same_path_witness": {
                "state": "NOT_EVALUATED",
                "future_per_track_peak_to_peak_limit_m": envelope.CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M,
            },
            "multipath_hardware_and_receiver_implementation": {
                "state": "NOT_EVALUATED",
                "future_common_mode_reserve_m": envelope.COMPLETE_CODE_WITNESS_RESERVE_M,
            },
            "orbital_affine_and_time_reversed_scores": {"state": "NOT_EVALUATED"},
            "thresholds_may_change_after_structure": False,
        },
        "physical_envelope_binding": {
            "parent_outcome": physical["outcome"],
            "retarded_controlling_null": physical["geometry"]["retarded_controlling_null"],
            "retarded_controlling_separation_m": physical_envelope[
                "retarded_controlling_separation_m"
            ],
            "one_model_bound_b_m": physical_envelope["one_model_bound_b_m"],
            "required_separation_3b_m": physical_envelope["required_separation_3b_m"],
            "remaining_physical_margin_m": physical_envelope[
                "remaining_physical_margin_m"
            ],
            "structure_alone_activates_conditional_reserve": False,
        },
        "future_structural_receipt": {
            "allowed": [
                "ARTIFACT_AND_HEADER_HASHES",
                "HEADER_CLAUSE_STATES",
                "FIELD_STATE_COUNTS",
                "LLI_STATE_COUNTS",
                "EPOCH_GRID_COVERAGE",
                "FIRST_AND_LAST_CONTIGUOUS_INDICES",
                "TYPED_REFUSAL_REASONS",
            ],
            "numeric_observation_values": 0,
            "derived_measurement_series": 0,
            "orbital_prediction_available_to_scanner": False,
            "orbital_scores": 0,
        },
        "future_outcomes": [
            "NO_DRAO_DOY237_ARTIFACT_SELECTED",
            "DRAO_STRUCTURE_ARTIFACT_MATERIALIZATION_FAILED",
            "DRAO_STRUCTURE_DESCRIPTION_ERROR",
            "DRAO_STRUCTURE_TOPOLOGY_REJECTED",
            "DRAO_LABELLED_FORWARD_STRUCTURE_READY_FOR_INTEGRATED_PROOF",
        ],
        "outcome_semantics": {
            "description_error": (
                "STRUCTURAL_AND_PHYSICAL_CLAUSES_NOT_EVALUATED_NO_MEASUREMENT_REJECTION"
            ),
            "topology_rejected": (
                "COMPLETE_ARTIFACT_PARSED_BUT_REQUIRED_HEADER_GRID_FIELD_OR_LLI_TOPOLOGY_FAILED"
            ),
            "ready": (
                "STRUCTURE_ONLY_READY_PHYSICAL_WITNESS_DETECTABILITY_AND_ORBITAL_SCORE_NOT_EVALUATED"
            ),
        },
        "retry_policy": {
            "before_complete_transport_hash": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "after_complete_transport_hash": 0,
            "after_decompression": 0,
            "fallback_date_endpoint_or_artifact": False,
        },
        "persistence": {
            "compressed_observation_after_outcome": 0,
            "decoded_observation_after_outcome": 0,
            "observation_values": 0,
            "derived_series": 0,
        },
        "access_at_freeze": {
            "network_requests": 0,
            "locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "observation_values": 0,
            "scores": 0,
        },
        "next_maximum": (
            "REVIEW_THEN_METADATA_ONLY_SELECT_AT_MOST_ONE_EXACT_DRAO_DOY237_ARTIFACT"
        ),
        "stop": "STOP_BEFORE_ANY_OBSERVATION_PRODUCT_LOOKUP_OR_ACCESS",
        "new_gate": False,
        "generic_framework": False,
    }
    _validate(value)
    strict_json(value)
    return value


def _validate(value: Mapping[str, object]) -> None:
    candidate = value["candidate"]
    access = value["access_at_freeze"]
    scan = value["structural_scan"]
    deferred = value["physical_clauses_deferred_not_satisfied"]
    binding = value["physical_envelope_binding"]
    persistence = value["persistence"]

    if candidate["artifact_selected"] or candidate["locator"] is not None:
        raise DraoStructuralContractError("ARTIFACT_SELECTED_AT_CONTRACT_FREEZE")
    if candidate["network_authority"] or candidate["payload_authority"]:
        raise DraoStructuralContractError("ACCESS_AUTHORITY_ENTERED_CONTRACT")
    if any(int(item) != 0 for item in access.values()):
        raise DraoStructuralContractError("OBSERVATION_ACCESS_AT_FREEZE")
    if any(int(item) != 0 for item in persistence.values()):
        raise DraoStructuralContractError("OBSERVATION_PERSISTENCE_AT_FREEZE")
    if scan["required_fields_each_satellite_epoch"] != list(
        CORE_PHASE + SAME_PATH_CODE
    ):
        raise DraoStructuralContractError("REQUIRED_FIELD_FAMILY_CHANGED")
    if scan["required_prn_substitution"] != "FORBIDDEN":
        raise DraoStructuralContractError("PRN_SUBSTITUTION_ALLOWED")
    if set(item["state"] for item in deferred.values() if isinstance(item, dict) and "state" in item) != {"NOT_EVALUATED"}:
        raise DraoStructuralContractError("PHYSICAL_CLAUSE_PREMATURELY_SATISFIED")
    if binding["structure_alone_activates_conditional_reserve"] is not False:
        raise DraoStructuralContractError("STRUCTURE_ACTIVATED_PHYSICAL_RESERVE")
    if not isclose(
        float(binding["retarded_controlling_separation_m"])
        - float(binding["required_separation_3b_m"]),
        float(binding["remaining_physical_margin_m"]),
        rel_tol=0.0,
        abs_tol=1.0e-9,
    ):
        raise DraoStructuralContractError("PHYSICAL_MARGIN_ARITHMETIC_CHANGED")


def contract_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(contract(root)).encode("ascii")).hexdigest()


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    if Path(path).exists():
        raise DraoStructuralContractError("CONTRACT_OUTPUT_ALREADY_EXISTS")
    Path(path).write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=root / OUTPUT_NAME)
    args = parser.parse_args()
    value = contract(root)
    _write_once(args.output, value)
    print(strict_json(value))


if __name__ == "__main__":
    main()
