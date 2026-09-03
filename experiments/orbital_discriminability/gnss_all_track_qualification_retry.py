"""Bounded, non-overwriting parser-repair retry for ALGO DOY229.

This module preserves the first qualification outcome and reuses the repaired
structural scanner without changing its scientific contract.  Importing the
module, building its manifest and running its tests perform no network access.
"""

from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Iterable

from experiments.orbital_discriminability import (
    gnss_all_track_structural_qualification as qualification,
)


RETRY_SCHEMA: Final = "gnss-all-track-qualification-retry-v1"
RETRY_PLAN_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_PLAN.md"
RETRY_SEAL_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_SEAL.json"
RETRY_COVERAGE_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_COVERAGE.jsonl"
RETRY_STRUCTURE_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_STRUCTURE.json"
RETRY_REVEAL_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_REVEAL.json"
RETRY_OUTCOME_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_RETRY_OUTCOME.json"

HISTORICAL_OUTCOME_NAME: Final = qualification.OUTCOME_NAME
HISTORICAL_OUTCOME: Final = "QUALIFICATION_DESCRIPTION_ERROR"
HISTORICAL_REASON: Final = "ANTENNA_TYPE_CHANGED"
HISTORICAL_OUTCOME_CANONICAL_SHA256: Final = (
    "57f863b7047d8efe96e54111186cebb5d338a4d580045ef5a37b1847c5bf675b"
)
REPAIR_COMMIT: Final = "e4bf316c3c15728ad6821dedb25d41e0a3f44866"
ARTIFACT_SHA256: Final = (
    "88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24"
)

OUTPUT_NAMES: Final = (
    RETRY_COVERAGE_NAME,
    RETRY_STRUCTURE_NAME,
    RETRY_REVEAL_NAME,
    RETRY_OUTCOME_NAME,
)


class RetryAuthorityError(qualification.DescriptionError):
    """The offline retry seal or its immutable predecessor is invalid."""


def _root() -> Path:
    return Path(__file__).resolve().parent


def _read_json(path: Path) -> dict[str, object]:
    def reject_constant(token: str) -> None:
        raise RetryAuthorityError(f"NONFINITE_JSON_CONSTANT:{token}")

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"), parse_constant=reject_constant
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RetryAuthorityError(
            f"RETRY_AUTHORITY_UNREADABLE:{path.name}:{type(exc).__name__}"
        ) from exc
    if not isinstance(value, dict):
        raise RetryAuthorityError(f"RETRY_AUTHORITY_NOT_OBJECT:{path.name}")
    return value


def retry_source_sha256() -> str:
    return qualification.canonical_file_sha256(Path(__file__))


def retry_plan_sha256(root: Path | None = None) -> str:
    base = _root() if root is None else Path(root)
    return qualification.canonical_file_sha256(base / RETRY_PLAN_NAME)


def _historical_outcome(root: Path) -> dict[str, object]:
    path = root / HISTORICAL_OUTCOME_NAME
    if qualification.canonical_file_sha256(path) != HISTORICAL_OUTCOME_CANONICAL_SHA256:
        raise RetryAuthorityError("HISTORICAL_OUTCOME_HASH_CHANGED")
    value = _read_json(path)
    if value.get("outcome") != HISTORICAL_OUTCOME:
        raise RetryAuthorityError("HISTORICAL_OUTCOME_TERMINAL_CHANGED")
    if value.get("reason") != HISTORICAL_REASON:
        raise RetryAuthorityError("HISTORICAL_OUTCOME_REASON_CHANGED")
    if value.get("structure") != "NOT_EVALUATED":
        raise RetryAuthorityError("HISTORICAL_STRUCTURE_RECLASSIFIED")
    return value


def manifest(root: Path | None = None) -> dict[str, object]:
    """Return the bounded retry contract without opening the artifact."""

    base = _root() if root is None else Path(root)
    original = qualification.manifest()
    result = {
        "schema": RETRY_SCHEMA,
        "state": "BOUNDED_RETRY_FROZEN_OFFLINE",
        "new_gate_created": False,
        "physical_question": (
            "DOES_THE_FROZEN_ALGO_PRODUCT_MATERIALIZE_EXACTLY_SIX_COMPLETE_"
            "VALUE_BLIND_GPS_L1C_L2W_TRACKS"
        ),
        "historical_outcome": {
            "name": HISTORICAL_OUTCOME_NAME,
            "canonical_sha256": HISTORICAL_OUTCOME_CANONICAL_SHA256,
            "outcome": HISTORICAL_OUTCOME,
            "reason": HISTORICAL_REASON,
            "immutable": True,
            "structure": "NOT_EVALUATED",
        },
        "repair": {
            "commit": REPAIR_COMMIT,
            "scope": "RINEX_3_04_ANTENNA_2A20_DESCRIPTION_ONLY",
            "scientific_parameter_changes": 0,
        },
        "original_contract": {
            "plan_name": qualification.PLAN_NAME,
            "plan_canonical_sha256": qualification.canonical_file_sha256(
                base / qualification.PLAN_NAME
            ),
            "selection_name": qualification.SELECTION_NAME,
            "selection_canonical_sha256": qualification.canonical_file_sha256(
                base / qualification.SELECTION_NAME
            ),
            "scanner_source_canonical_sha256": qualification.source_sha256(),
            "header_parser_canonical_sha256": qualification.canonical_file_sha256(
                base / "gnss_observation_header.py"
            ),
            "structural_manifest_sha256": qualification.manifest_sha256(),
            "window_gps": original["window_gps"],
            "complete_track_count_required": original[
                "complete_track_count_required"
            ],
            "core_phase": original["core_phase"],
            "same_path_code_descriptive": original[
                "same_path_code_descriptive"
            ],
            "track_identity": original["track_identity"],
            "antenna_record_semantics": original["antenna_record_semantics"],
        },
        "retry_plan": {
            "name": RETRY_PLAN_NAME,
            "canonical_sha256": retry_plan_sha256(base),
        },
        "artifact": {
            "station": qualification.STATION,
            "name": qualification.PRODUCT_NAME,
            "url": qualification.PRODUCT_URL,
            "complete_file_bytes": qualification.EXPECTED_COMPRESSED_BYTES,
            "complete_file_sha256": ARTIFACT_SHA256,
            "identity_required_before_decompression": True,
        },
        "outputs": {
            "coverage": RETRY_COVERAGE_NAME,
            "structure": RETRY_STRUCTURE_NAME,
            "reveal": RETRY_REVEAL_NAME,
            "outcome": RETRY_OUTCOME_NAME,
            "all_distinct_from_historical": True,
        },
        "retry_policy": {
            "parser_repair_executions": 1,
            "maximum_transport_attempts_before_complete_hash": (
                qualification.MAX_TRANSPORT_ATTEMPTS
            ),
            "retryable_before_complete_hash": [
                "TIMEOUT",
                "TRANSPORT_INTERRUPTION",
            ],
            "retry_after_complete_hash": False,
            "alternate_product_url_station_date_or_window": False,
        },
        "forbidden": [
            "historical outcome overwrite or reclassification",
            "scientific threshold, field-role, window or count change",
            "PRN-conditioned membership",
            "observation scalar conversion or persistence",
            "measurement admission or orbital scoring",
            "primary or reserve selection",
        ],
        "current_stop": "SEPARATE_EXPLICIT_RETRY_AUTHORITY_REQUIRED",
    }
    qualification.strict_json(result)
    return result


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(
        qualification.strict_json(manifest(root)).encode("ascii")
    ).hexdigest()


def verify_retry_authority(root: Path | None = None) -> dict[str, object]:
    """Verify every frozen input before a future network operation."""

    base = _root() if root is None else Path(root)
    qualification.verify_frozen_selection(base)
    _historical_outcome(base)
    seal = _read_json(base / RETRY_SEAL_NAME)
    current = manifest(base)

    if seal.get("schema") != "gnss-all-track-qualification-retry-seal-v1":
        raise RetryAuthorityError("RETRY_SEAL_SCHEMA_CHANGED")
    if seal.get("state") != "GNSS_ALL_TRACK_BOUNDED_RETRY_FROZEN_UNEXECUTED":
        raise RetryAuthorityError("RETRY_SEAL_STATE_CHANGED")
    if seal.get("repair_commit") != REPAIR_COMMIT:
        raise RetryAuthorityError("REPAIR_COMMIT_CHANGED")
    if seal.get("retry_manifest_sha256") != manifest_sha256(base):
        raise RetryAuthorityError("RETRY_MANIFEST_HASH_CHANGED")
    if seal.get("retry_executor_canonical_sha256") != retry_source_sha256():
        raise RetryAuthorityError("RETRY_EXECUTOR_HASH_CHANGED")
    if seal.get("historical_outcome") != current["historical_outcome"]:
        raise RetryAuthorityError("HISTORICAL_LINEAGE_CHANGED")
    if seal.get("original_contract") != current["original_contract"]:
        raise RetryAuthorityError("ORIGINAL_CONTRACT_LINEAGE_CHANGED")
    if seal.get("retry_plan") != current["retry_plan"]:
        raise RetryAuthorityError("RETRY_PLAN_LINEAGE_CHANGED")
    if seal.get("artifact") != current["artifact"]:
        raise RetryAuthorityError("RETRY_ARTIFACT_IDENTITY_CHANGED")
    if seal.get("outputs") != current["outputs"]:
        raise RetryAuthorityError("RETRY_OUTPUT_SET_CHANGED")
    return seal


def materialize_exact() -> tuple[bytearray, dict[str, object]]:
    """Materialize the one frozen artifact and enforce its complete identity."""

    payload, receipt = qualification.materialize(qualification.ProductLocator())
    observed_sha = str(receipt.get("complete_file_sha256", ""))
    if observed_sha != ARTIFACT_SHA256:
        payload[:] = b"\x00" * len(payload)
        raise qualification.MaterializationError(
            f"COMPLETE_FILE_SHA256_CHANGED:{observed_sha}:{ARTIFACT_SHA256}"
        )
    if receipt.get("complete_file_bytes") != qualification.EXPECTED_COMPRESSED_BYTES:
        payload[:] = b"\x00" * len(payload)
        raise qualification.MaterializationError("COMPLETE_FILE_BYTE_COUNT_CHANGED")
    receipt["matches_frozen_complete_identity"] = True
    return payload, receipt


def _write_json(path: Path, value: object) -> None:
    if path.exists():
        raise RetryAuthorityError(f"RETRY_OUTPUT_ALREADY_EXISTS:{path.name}")
    path.write_text(
        qualification.strict_json(value, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    if path.exists():
        raise RetryAuthorityError(f"RETRY_OUTPUT_ALREADY_EXISTS:{path.name}")
    path.write_text(
        "".join(qualification.strict_json(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _lineage(seal: dict[str, object], root: Path) -> dict[str, object]:
    return {
        "seal_name": RETRY_SEAL_NAME,
        "seal_canonical_sha256": qualification.canonical_file_sha256(
            root / RETRY_SEAL_NAME
        ),
        "source_commit": seal["source_commit"],
        "execution_commit": qualification._git_commit(),
        "retry_executor_canonical_sha256": retry_source_sha256(),
        "retry_manifest_sha256": manifest_sha256(root),
        "repair_commit": REPAIR_COMMIT,
        "historical_outcome": seal["historical_outcome"],
        "original_contract": seal["original_contract"],
        "retry_plan": seal["retry_plan"],
    }


def _failure_outcome(
    outcome: str,
    reason: str,
    *,
    lineage: dict[str, object],
    artifact: dict[str, object] | None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": RETRY_SCHEMA,
        "outcome": outcome,
        "reason": reason,
        "retry_lineage": lineage,
        "structure": "NOT_EVALUATED",
        "measurement_admission": "NOT_EVALUATED",
        "orbital_score": "NOT_EVALUATED",
        "primary_selection": "NOT_EVALUATED",
        "observation_values_parsed": 0,
        "observation_values_persisted": 0,
        "observation_artifact_bytes_persisted": 0,
    }
    if artifact is not None:
        result["artifact"] = artifact
    qualification.strict_json(result)
    return result


def run_retry_once(output_directory: Path) -> dict[str, object]:
    """Run one separately authorized retry; never touch the old outcome."""

    root = _root()
    directory = Path(output_directory)
    seal = verify_retry_authority(root)
    for name in OUTPUT_NAMES:
        if (directory / name).exists():
            raise RetryAuthorityError(f"RETRY_OUTPUT_ALREADY_EXISTS:{name}")
    historical_hash_before = qualification.canonical_file_sha256(
        root / HISTORICAL_OUTCOME_NAME
    )
    lineage = _lineage(seal, root)
    compressed = bytearray()
    decoded = bytearray()
    scan: qualification.StructuralScan | None = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materialize_exact()
        decoded = qualification._decompress(compressed)
        scan = qualification.scan_decoded(decoded)
        structure = qualification.evaluate(scan)

        _write_jsonl(directory / RETRY_COVERAGE_NAME, scan.coverage)
        coverage_sha = qualification.canonical_file_sha256(
            directory / RETRY_COVERAGE_NAME
        )
        structure["retry_lineage"] = lineage
        structure["coverage"] = {
            "name": RETRY_COVERAGE_NAME,
            "rows": len(scan.coverage),
            "sha256": coverage_sha,
        }
        _write_json(directory / RETRY_STRUCTURE_NAME, structure)
        structure_sha = qualification.canonical_file_sha256(
            directory / RETRY_STRUCTURE_NAME
        )
        reveal = qualification.reveal_after_structural_hash(scan, structure_sha)
        reveal["schema"] = "gnss-all-track-qualification-retry-reveal-v1"
        reveal["retry_lineage"] = lineage
        _write_json(directory / RETRY_REVEAL_NAME, reveal)
        reveal_sha = qualification.canonical_file_sha256(
            directory / RETRY_REVEAL_NAME
        )

        outcome = {
            "schema": RETRY_SCHEMA,
            "outcome": structure["outcome"],
            "retry_lineage": lineage,
            "artifact": artifact,
            "structure": {"name": RETRY_STRUCTURE_NAME, "sha256": structure_sha},
            "coverage": {"name": RETRY_COVERAGE_NAME, "sha256": coverage_sha},
            "reveal": {
                "name": RETRY_REVEAL_NAME,
                "sha256": reveal_sha,
                "created_after_structural_hash": True,
                "membership_changed": False,
            },
            "clause_states": {
                "header_description": "SATISFIED",
                "complete_grid": (
                    "SATISFIED" if structure["epoch_grid_complete"] else "UNSATISFIED"
                ),
                "exact_six_complete_tracks": structure["count_clause"],
                "same_path_code": "DESCRIPTIVE_NOT_ADMISSION_CLAUSE",
                "measurement_admission": "NOT_EVALUATED",
                "orbital_score": "NOT_EVALUATED",
                "primary_selection": "NOT_EVALUATED",
            },
            "persistence": {
                "compressed_artifact_bytes": 0,
                "decompressed_observation_bytes": 0,
                "observation_values": 0,
                "structural_receipts_only": True,
            },
        }
    except qualification.MaterializationError as exc:
        outcome = _failure_outcome(
            "QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED",
            str(exc),
            lineage=lineage,
            artifact=artifact,
        )
    except qualification.StructuralRefusal as exc:
        outcome = _failure_outcome(
            "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED",
            str(exc),
            lineage=lineage,
            artifact=artifact,
        )
        outcome["structure"] = "UNSATISFIED"
    except qualification.DescriptionError as exc:
        outcome = _failure_outcome(
            "QUALIFICATION_DESCRIPTION_ERROR",
            str(exc),
            lineage=lineage,
            artifact=artifact,
        )
    except Exception as exc:  # pragma: no cover - defensive typed boundary
        outcome = _failure_outcome(
            "QUALIFICATION_DESCRIPTION_ERROR",
            f"{type(exc).__name__}:{exc}",
            lineage=lineage,
            artifact=artifact,
        )
    finally:
        if scan is not None:
            scan.erase()
        decoded[:] = b"\x00" * len(decoded)
        compressed[:] = b"\x00" * len(compressed)
        gc.collect()

    if qualification.canonical_file_sha256(
        root / HISTORICAL_OUTCOME_NAME
    ) != historical_hash_before:
        raise RetryAuthorityError("HISTORICAL_OUTCOME_CHANGED_DURING_RETRY")
    _write_json(directory / RETRY_OUTCOME_NAME, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-authorized-retry", action="store_true")
    parser.add_argument(
        "--output-directory", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    if not args.execute_authorized_retry:
        raise SystemExit("EXPLICIT_BOUNDED_RETRY_AUTHORITY_REQUIRED")
    print(qualification.strict_json(run_retry_once(args.output_directory)))


if __name__ == "__main__":
    main()

