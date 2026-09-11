"""One-use runner for the final frozen DRAO DOY234 labelled-forward event.

This experiment-specific runner adds only exact-product transport, complete
hashing before decoding, typed outcomes and volatile-buffer erasure to the
already frozen DOY234 executor.  It is not a downloader or generic adapter.
"""

from __future__ import annotations

import argparse
import gc
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy234_executor as experiment,
)


RUNNER_VERSION: Final = "drao-labelled-forward-doy234-one-use-runner-v1"
SELECTION_NAME: Final = experiment.SELECTION_NAME
SELECTION_SHA256: Final = "ee0c34c788f24e518396d735235c2528de314015c3f319d193d43c1bfb297fde"
EXECUTOR_SEAL_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_EXECUTOR_MANIFEST.json"
EXECUTOR_SEAL_SHA256: Final = "42f8fb271bdb0d6d437cfa459578cd6c624832e61becfd58c9af2a04c094853d"
RUNNER_SEAL_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_RUNNER_SEAL.json"
AUTHORITY_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_AUTHORITY_CONSUMED.json"
MATERIALIZATION_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_MATERIALIZATION.json"
OUTCOME_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_OUTCOME.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_DRAO_LABELLED_FORWARD_DOY234_ONCE"

ARTIFACT_NAME: Final = "DRAO00CAN_R_20262340000_01D_30S_MO.crx.gz"
ARTIFACT_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/234/" + ARTIFACT_NAME
)
ARTIFACT_BYTES: Final = 2_850_623
ARTIFACT_ETAG: Final = '"2b7f3f-659d4b378b5bb"'
ARTIFACT_LAST_MODIFIED: Final = "Tue, 25 Aug 2026 01:05:39 GMT"
ARTIFACT_CONTENT_TYPE: Final = "application/x-gzip"
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 3_000_000


class RunnerDescriptionError(RuntimeError):
    """Software, authority or descriptive provenance prevented evaluation."""


class ArtifactMaterializationFailed(RuntimeError):
    """The exact artifact did not reach a complete-file hash."""

    def __init__(self, receipt: Mapping[str, object]):
        super().__init__("PRIMARY_ARTIFACT_MATERIALIZATION_FAILED")
        self.receipt = dict(receipt)


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


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise RunnerDescriptionError(f"NOT_A_JSON_OBJECT:{Path(path).name}")
    return value


def verify_selection(root: Path) -> dict[str, object]:
    path = Path(root) / SELECTION_NAME
    if canonical_sha256(path) != SELECTION_SHA256:
        raise RunnerDescriptionError("DRAO_DOY234_SELECTION_CHANGED")
    selection = _read_json(path)
    artifact = selection.get("artifact", {})
    http = selection.get("http_head_receipt", {})
    if (
        selection.get("state") != "DRAO_DOY234_ARTIFACT_SELECTED_UNOPENED"
        or artifact.get("name") != ARTIFACT_NAME
        or artifact.get("url") != ARTIFACT_URL
        or artifact.get("complete_sha256") is not None
        or artifact.get("body_access_authorized") is not False
        or int(http.get("content_length", -1)) != ARTIFACT_BYTES
        or http.get("etag") != ARTIFACT_ETAG
        or http.get("last_modified") != ARTIFACT_LAST_MODIFIED
        or http.get("content_type") != ARTIFACT_CONTENT_TYPE
    ):
        raise RunnerDescriptionError("DRAO_DOY234_SELECTION_STATE_CHANGED")
    return selection


def runner_manifest(root: Path) -> dict[str, object]:
    selection = verify_selection(root)
    if canonical_sha256(Path(root) / EXECUTOR_SEAL_NAME) != EXECUTOR_SEAL_SHA256:
        raise RunnerDescriptionError("DRAO_DOY234_EXECUTOR_SEAL_CHANGED")
    experiment.verify_frozen_inputs(root)
    value = {
        "schema": "gnss-drao-labelled-forward-doy234-runner-manifest-v1",
        "version": RUNNER_VERSION,
        "state": "DRAO_DOY234_RUNNER_FROZEN_UNEXECUTED",
        "physical_question": "DO_THE_SIX_FROZEN_LABELLED_PATHS_PREDICT_THE_HELDOUT_SUFFIX_BETTER_THAN_BOTH_FROZEN_NULLS",
        "new_information": "ONE_TERMINAL_REAL_DRAO_DOY234_ORBITAL_VERSUS_NULL_EVENT",
        "selection": {
            "name": SELECTION_NAME,
            "canonical_sha256": SELECTION_SHA256,
            "artifact": selection["artifact"],
            "http_head_receipt": selection["http_head_receipt"],
        },
        "frozen_executor": {
            "name": EXECUTOR_SEAL_NAME,
            "canonical_sha256": EXECUTOR_SEAL_SHA256,
            "plan_raw_sha256": experiment.PLAN_SHA256,
            "prediction_bundle_raw_sha256": experiment.BUNDLE_SHA256,
            "physical_envelope_raw_sha256": experiment.ENVELOPE_SHA256,
        },
        "execution_order": [
            "ONE_USE_AUTHORITY_CONSUMED_BEFORE_NETWORK",
            "EXACT_SAME_LOCATOR_COMPLETE_MATERIALIZATION",
            "FULL_BYTE_COUNT_AND_SHA256_RECEIPT_PERSISTED",
            "IN_MEMORY_DECOMPRESSION",
            "COMPOSITE_IDENTITY_AND_TYPED_TRANSFORM_LEDGER",
            "COMPLETE_SIX_PRN_TOPOLOGY",
            "MODEL_BLIND_PHYSICAL_WITNESSES",
            "FROZEN_PREDICTION_BUNDLE_RELEASE",
            "PREFIX_ONLY_ORBITAL_AND_NULL_SCORE",
            "ONE_TERMINAL_OUTCOME",
            "BUFFER_ZEROIZATION",
        ],
        "transport": {
            "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
            "retryable": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "same_locator_complete_restart_only": True,
            "retry_after_complete_hash": 0,
            "fallback": False,
        },
        "terminal_semantics": {
            "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED": "PHYSICAL_DECISION_NOT_EVALUATED",
            "PRIMARY_NOT_EVALUATED": "DESCRIPTION_OR_TRANSFORM_FAILURE",
            "MEASUREMENT_INVALID": "STRUCTURE_OR_MODEL_BLIND_WITNESS_FAILURE",
            "NOT_DETECTABLE": "ORBITAL_PREFIX_EXCEEDS_FROZEN_B",
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED": "MAXIMUM_AUTHORIZED_POSITIVE_CLAIM",
            "ORBITAL_PREDICTION_REJECTED": "FROZEN_ORBITAL_PREDICTION_DAMAGED",
            "PREFIX_AFFINE_NULL_PREFERRED": "FROZEN_AFFINE_ALTERNATIVE_PREFERRED",
            "TIME_REVERSED_GEOMETRY_NULL_PREFERRED": "FROZEN_GEOMETRY_ALTERNATIVE_PREFERRED",
            "AMBIGUOUS": "NO_FAMILY_UNIQUELY_PREFERRED",
        },
        "persistence": {
            "authority_materialization_and_terminal_receipts": True,
            "compressed_artifact": 0,
            "decoded_rinex": 0,
            "observation_values": 0,
            "derived_series": 0,
        },
        "access_at_freeze": {
            "network_requests": 0,
            "body_bytes": 0,
            "rinex_headers": 0,
            "observation_values": 0,
            "scores": 0,
        },
        "live_authority_granted_by_manifest": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path) -> str:
    return sha256(strict_json(runner_manifest(root)).encode("ascii")).hexdigest()


def validate_seal(root: Path, seal_path: Path, expected_sha256: str) -> dict[str, object]:
    if len(expected_sha256) != 64 or canonical_sha256(seal_path) != expected_sha256:
        raise RunnerDescriptionError("DRAO_DOY234_RUNNER_SEAL_CHANGED")
    seal = _read_json(seal_path)
    if seal.get("state") != "DRAO_DOY234_RUNNER_FROZEN_UNEXECUTED":
        raise RunnerDescriptionError("DRAO_DOY234_RUNNER_SEAL_STATE_CHANGED")
    if seal.get("runner_source_canonical_sha256") != source_sha256():
        raise RunnerDescriptionError("DRAO_DOY234_RUNNER_SOURCE_CHANGED")
    if seal.get("runner_manifest_sha256") != manifest_sha256(root):
        raise RunnerDescriptionError("DRAO_DOY234_RUNNER_MANIFEST_CHANGED")
    if seal.get("selection_canonical_sha256") != SELECTION_SHA256:
        raise RunnerDescriptionError("DRAO_DOY234_RUNNER_SELECTION_CHANGED")
    if seal.get("live_authority_granted") is not False:
        raise RunnerDescriptionError("DRAO_DOY234_SEAL_GRANTED_LIVE_AUTHORITY")
    if any(seal.get("access_at_seal", {}).values()):
        raise RunnerDescriptionError("DRAO_DOY234_SEAL_USED_OBSERVATION")
    return seal


def _header(response: object, name: str) -> str | None:
    value = response.headers.get(name)
    return None if value is None else str(value)


def _validate_response_identity(response: object) -> None:
    if int(response.status) != 200 or response.geturl() != ARTIFACT_URL:
        raise RunnerDescriptionError("DRAO_DOY234_ARTIFACT_LOCATOR_CHANGED")
    expected = {
        "Content-Length": str(ARTIFACT_BYTES),
        "ETag": ARTIFACT_ETAG,
        "Last-Modified": ARTIFACT_LAST_MODIFIED,
        "Content-Type": ARTIFACT_CONTENT_TYPE,
    }
    if {name: _header(response, name) for name in expected} != expected:
        raise RunnerDescriptionError("DRAO_DOY234_HTTP_IDENTITY_CHANGED")


def materialize() -> tuple[bytearray, dict[str, object]]:
    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        payload = bytearray()
        try:
            request = Request(
                ARTIFACT_URL,
                headers={
                    "Accept-Encoding": "identity",
                    "User-Agent": "Satellite-RF-Observatory/DRAO-DOY234-primary",
                },
                method="GET",
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                _validate_response_identity(response)
                while block := response.read(64 * 1024):
                    payload.extend(block)
                    if len(payload) > MAX_COMPRESSED_BYTES:
                        raise RunnerDescriptionError("DRAO_DOY234_COMPRESSED_SIZE_LIMIT")
        except RunnerDescriptionError:
            payload[:] = b"\x00" * len(payload)
            raise
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            payload[:] = b"\x00" * len(payload)
            failures.append(f"{type(exc).__name__}:{exc}")
            continue
        if len(payload) != ARTIFACT_BYTES:
            actual = len(payload)
            payload[:] = b"\x00" * len(payload)
            failures.append(f"COMPLETE_BYTE_COUNT_CHANGED:{actual}:{ARTIFACT_BYTES}")
            continue
        receipt = {
            "schema": "gnss-drao-labelled-forward-doy234-materialization-v1",
            "state": "DRAO_DOY234_COMPLETE_HASH_RECORDED_BEFORE_DECODE",
            "artifact": ARTIFACT_NAME,
            "url": ARTIFACT_URL,
            "attempts": attempt,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": sha256(payload).hexdigest(),
            "frozen_http_identity_matched": True,
            "hash_persisted_before_decompression": False,
            "retry_after_complete_hash": 0,
            "body_persisted": False,
        }
        strict_json(receipt)
        return payload, receipt
    raise ArtifactMaterializationFailed(
        {
            "schema": "gnss-drao-labelled-forward-doy234-materialization-failure-v1",
            "state": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "artifact": ARTIFACT_NAME,
            "attempts": MAX_TRANSPORT_ATTEMPTS,
            "complete_file_bytes": None,
            "complete_file_sha256": None,
            "failures": failures,
            "retry_after_complete_hash": False,
        }
    )


def decompress_in_memory(payload: bytearray) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise RunnerDescriptionError("HATANAKA_DECOMPRESSION_DESCRIPTION_ERROR") from exc


def _write_json(path: Path, value: object) -> None:
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def _not_evaluated(reason_class: str, reason: str) -> dict[str, object]:
    return {
        "schema": "gnss-drao-labelled-forward-doy234-outcome-v1",
        "outcome": "PRIMARY_NOT_EVALUATED",
        "reason_class": reason_class,
        "reason": reason,
        "physical_decision": "NOT_EVALUATED",
        "observation_values_persisted": 0,
    }


def run_once(
    output_directory: Path,
    authority_token: str,
    seal_path: Path,
    expected_seal_sha256: str,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("DRAO_DOY234_ONE_USE_AUTHORITY_REQUIRED")
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    authority_path = output / AUTHORITY_NAME
    outcome_path = output / OUTCOME_NAME
    if authority_path.exists() or outcome_path.exists():
        raise PermissionError("DRAO_DOY234_ONE_USE_AUTHORITY_ALREADY_CONSUMED")
    root = Path(__file__).resolve().parent
    seal = validate_seal(root, seal_path, expected_seal_sha256)
    _write_json(
        authority_path,
        {
            "schema": "gnss-drao-labelled-forward-doy234-authority-consumed-v1",
            "state": "DRAO_DOY234_ONE_USE_AUTHORITY_CONSUMED_BEFORE_NETWORK",
            "runner_seal_sha256": expected_seal_sha256,
            "runner_source_commit": seal["runner_source_commit"],
            "network_requests_before_authority_receipt": 0,
            "body_bytes_before_authority_receipt": 0,
            "observation_values_before_authority_receipt": 0,
        },
    )

    compressed: bytearray | None = None
    decoded: bytearray | None = None
    scan: experiment.ForwardScan | None = None
    coordinate = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materialize()
        artifact["hash_persisted_before_decompression"] = True
        materialization_path = output / MATERIALIZATION_NAME
        _write_json(materialization_path, artifact)
        decoded = decompress_in_memory(compressed)
        scan = experiment.scan_decoded(decoded, archive_site_id=experiment.frozen.STATION)
        admission, coordinate = experiment.admit_model_blind(scan)
        score = experiment.score(coordinate, root)
        outcome = {
            "schema": "gnss-drao-labelled-forward-doy234-outcome-v1",
            "outcome": score["outcome"],
            "artifact": artifact,
            "artifact_receipt": {
                "name": MATERIALIZATION_NAME,
                "canonical_sha256": canonical_sha256(materialization_path),
            },
            "identity_and_transform_receipt": scan.header,
            "admission_receipt": admission,
            "score_receipt": score,
            "runner_seal_sha256": expected_seal_sha256,
            "retry_after_complete_hash": 0,
            "claim_scope": {
                "maximum_positive": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
                "specific_satellite_identity": "NOT_ESTABLISHED_INDEPENDENTLY",
                "distributed_multi_root": False,
                "orbit_determination": False,
            },
            "persistence": {
                "compressed_artifact": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
                "derived_series": 0,
            },
        }
    except ArtifactMaterializationFailed as exc:
        outcome = _not_evaluated("ARTIFACT_MATERIALIZATION_FAILED", str(exc))
        outcome["outcome"] = "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED"
        outcome["materialization_receipt"] = exc.receipt
    except experiment.Doy234MeasurementInvalid as exc:
        outcome = {
            "schema": "gnss-drao-labelled-forward-doy234-outcome-v1",
            "outcome": "MEASUREMENT_INVALID",
            "reason_class": "STRUCTURAL_OR_MODEL_BLIND_ADMISSION_FAILURE",
            "reason": str(exc),
            "artifact": artifact,
            "orbital_score": "NOT_EVALUATED",
            "downstream_clauses": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except (RunnerDescriptionError, experiment.Doy234DescriptionError) as exc:
        outcome = _not_evaluated("DESCRIPTION_ERROR", str(exc))
        outcome["artifact"] = artifact
    except Exception as exc:
        outcome = _not_evaluated("DESCRIPTION_ERROR", f"{type(exc).__name__}:{exc}")
        outcome["artifact"] = artifact
    finally:
        if coordinate is not None:
            coordinate.fill(0.0)
        if scan is not None:
            scan.erase()
        for payload in (decoded, compressed):
            if payload is not None:
                payload[:] = b"\x00" * len(payload)
        gc.collect()
    strict_json(outcome)
    _write_json(outcome_path, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--seal", type=Path)
    parser.add_argument("--seal-sha256", default="")
    parser.add_argument("--output-directory", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if not args.execute_live or args.seal is None:
        raise SystemExit("DRAO_DOY234_FROZEN_RUNNER_AND_ONE_USE_AUTHORITY_REQUIRED")
    print(strict_json(run_once(args.output_directory, args.authority, args.seal, args.seal_sha256)))


if __name__ == "__main__":
    main()
