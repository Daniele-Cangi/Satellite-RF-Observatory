"""One-shot materialization boundary for the frozen DRAO DOY233 primary.

The scientific parser, admission rules and opaque scorer are already frozen in
``gnss_drao_doy233_integrated_primary``.  This module adds only the missing
one-use transport, pre-decode artifact receipt, typed failure boundary and RAM
cleanup.  It is not a reusable downloader or GNSS execution framework.
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
    gnss_drao_doy233_integrated_primary as primary,
)


RUNNER_VERSION: Final = "drao-doy233-one-shot-primary-runner-v1"
SELECTION_NAME: Final = "GNSS_DRAO_DOY233_PRIMARY_ARTIFACT_SELECTION.json"
SELECTION_SHA256: Final = (
    "4cc85f077feb7e784920494f2b56b83ce9b2e0d3bda703f7e937b180914d9ea3"
)
SEAL_NAME: Final = "GNSS_DRAO_DOY233_PRIMARY_RUNNER_SEAL.json"
MARKER_NAME: Final = "GNSS_DRAO_DOY233_PRIMARY_AUTHORITY_CONSUMED.json"
ARTIFACT_RECEIPT_NAME: Final = "GNSS_DRAO_DOY233_PRIMARY_MATERIALIZATION.json"
OUTCOME_NAME: Final = "GNSS_DRAO_DOY233_PRIMARY_OUTCOME.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_DRAO_DOY233_INTEGRATED_PRIMARY_ONCE"

ARTIFACT_NAME: Final = "DRAO00CAN_R_20262330000_01D_30S_MO.crx.gz"
ARTIFACT_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/233/" + ARTIFACT_NAME
)
ARTIFACT_BYTES: Final = 2_886_587
ARTIFACT_ETAG: Final = '"2c0bbb-6599ef1b69d62"'
ARTIFACT_LAST_MODIFIED: Final = "Sat, 22 Aug 2026 08:57:35 GMT"
ARTIFACT_CONTENT_TYPE: Final = "application/x-gzip"
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 3_000_000


class RunnerDescriptionError(RuntimeError):
    """Software, authority or descriptive provenance prevented evaluation."""


class ArtifactMaterializationFailed(RuntimeError):
    """The exact selected artifact was not completely materialized."""

    def __init__(self, reason: str, receipt: Mapping[str, object]):
        super().__init__(reason)
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


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(64 * 1024):
            digest.update(block)
    return digest.hexdigest()


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
        raise RunnerDescriptionError("DRAO_DOY233_SELECTION_CHANGED")
    value = _read_json(path)
    artifact = value.get("artifact", {})
    if (
        value.get("state") != "DRAO_DOY233_PRIMARY_ARTIFACT_SELECTED_UNOPENED"
        or artifact.get("name") != ARTIFACT_NAME
        or artifact.get("url") != ARTIFACT_URL
        or artifact.get("complete_sha256") is not None
        or artifact.get("body_access_authorized") is not False
    ):
        raise RunnerDescriptionError("DRAO_DOY233_SELECTION_STATE_CHANGED")
    return value


def runner_manifest(root: Path) -> dict[str, object]:
    selection = verify_selection(root)
    value = {
        "schema": "gnss-drao-doy233-primary-runner-manifest-v1",
        "version": RUNNER_VERSION,
        "state": "DRAO_DOY233_PRIMARY_RUNNER_FROZEN_UNEXECUTED",
        "selection": {
            "name": SELECTION_NAME,
            "canonical_sha256": SELECTION_SHA256,
            "artifact": selection["artifact"],
        },
        "frozen_core": {
            "plan_sha256": primary.PLAN_SHA256,
            "bundle_sha256": primary.BUNDLE_SHA256,
            "reveal_sha256": primary.REVEAL_SHA256,
            "scorer_sha256": primary.frozen.SCORER_SHA256,
        },
        "execution_order": [
            "ONE_USE_AUTHORITY_MARKER_BEFORE_NETWORK",
            "EXACT_SAME_LOCATOR_MATERIALIZATION",
            "COMPLETE_BYTE_COUNT_AND_SHA256_RECEIPT_PERSISTED",
            "IN_MEMORY_DECOMPRESSION",
            "ATTRIBUTABLE_HEADER_AND_ALL_TRACK_ADMISSION",
            "OPAQUE_SCORE_RECEIPT_HASH",
            "POST_HASH_IDENTITY_REVEAL",
            "ONE_TERMINAL_OUTCOME",
            "BUFFER_ZEROIZATION",
        ],
        "transport": {
            "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
            "retryable": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "resume_implemented": False,
            "complete_restart_same_locator_is_bounded": True,
            "retry_after_complete_hash": 0,
            "fallback": False,
        },
        "failure_semantics": {
            "ARTIFACT_MATERIALIZATION_FAILED": "PRIMARY_NOT_EVALUATED",
            "DESCRIPTION_ERROR": "PRIMARY_NOT_EVALUATED",
            "STRUCTURAL_OR_PHYSICAL_ADMISSION_FAILURE": "MEASUREMENT_INVALID",
        },
        "persistence": {
            "artifact_identity_and_hash_receipt": True,
            "terminal_outcome": True,
            "compressed_artifact": 0,
            "decoded_rinex": 0,
            "observation_values": 0,
            "derived_series": 0,
        },
        "access_at_freeze": {
            "network_requests": 0,
            "body_bytes": 0,
            "headers": 0,
            "observation_values": 0,
            "scores": 0,
        },
        "live_authority_granted": False,
        "new_gate": False,
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path) -> str:
    return sha256(strict_json(runner_manifest(root)).encode("ascii")).hexdigest()


def validate_seal(root: Path, seal_path: Path, expected_sha256: str) -> dict[str, object]:
    if len(expected_sha256) != 64 or canonical_sha256(seal_path) != expected_sha256:
        raise RunnerDescriptionError("PRIMARY_RUNNER_SEAL_SHA256_CHANGED")
    seal = _read_json(seal_path)
    if seal.get("state") != "DRAO_DOY233_PRIMARY_RUNNER_FROZEN_UNEXECUTED":
        raise RunnerDescriptionError("PRIMARY_RUNNER_SEAL_STATE_CHANGED")
    if seal.get("runner_source_canonical_sha256") != source_sha256():
        raise RunnerDescriptionError("PRIMARY_RUNNER_SOURCE_CHANGED")
    if seal.get("runner_manifest_sha256") != manifest_sha256(root):
        raise RunnerDescriptionError("PRIMARY_RUNNER_MANIFEST_CHANGED")
    if seal.get("selection_canonical_sha256") != SELECTION_SHA256:
        raise RunnerDescriptionError("PRIMARY_RUNNER_SELECTION_CHANGED")
    if seal.get("live_authority_granted") is not False:
        raise RunnerDescriptionError("PRIMARY_RUNNER_SEAL_GRANTED_LIVE_AUTHORITY")
    if any(seal.get("access_at_seal", {}).values()):
        raise RunnerDescriptionError("PRIMARY_RUNNER_SEAL_USED_OBSERVATION")
    return seal


def _header(response: object, name: str) -> str | None:
    value = response.headers.get(name)
    return None if value is None else str(value)


def _validate_response_identity(response: object) -> None:
    if int(response.status) != 200 or response.geturl() != ARTIFACT_URL:
        raise RunnerDescriptionError("PRIMARY_ARTIFACT_LOCATOR_CHANGED")
    expected = {
        "Content-Length": str(ARTIFACT_BYTES),
        "ETag": ARTIFACT_ETAG,
        "Last-Modified": ARTIFACT_LAST_MODIFIED,
        "Content-Type": ARTIFACT_CONTENT_TYPE,
    }
    actual = {name: _header(response, name) for name in expected}
    if actual != expected:
        raise RunnerDescriptionError("PRIMARY_HTTP_IDENTITY_CHANGED")


def materialize() -> tuple[bytearray, dict[str, object]]:
    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        payload = bytearray()
        try:
            request = Request(
                ARTIFACT_URL,
                headers={
                    "Accept-Encoding": "identity",
                    "User-Agent": "Satellite-RF-Observatory/DRAO-DOY233-primary",
                },
                method="GET",
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                _validate_response_identity(response)
                while block := response.read(64 * 1024):
                    payload.extend(block)
                    if len(payload) > MAX_COMPRESSED_BYTES:
                        raise RunnerDescriptionError("PRIMARY_COMPRESSED_SIZE_LIMIT")
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
        digest = sha256(payload).hexdigest()
        receipt = {
            "schema": "gnss-drao-doy233-primary-materialization-v1",
            "state": "PRIMARY_COMPLETE_HASH_RECORDED_BEFORE_DECODE",
            "artifact": ARTIFACT_NAME,
            "url": ARTIFACT_URL,
            "attempts": attempt,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": digest,
            "frozen_http_identity_matched": True,
            "hash_persisted_before_decompression": False,
            "retry_after_complete_hash": 0,
            "body_persisted": False,
        }
        strict_json(receipt)
        return payload, receipt
    receipt = {
        "schema": "gnss-drao-doy233-primary-materialization-failure-v1",
        "state": "ARTIFACT_MATERIALIZATION_FAILED",
        "artifact": ARTIFACT_NAME,
        "attempts": MAX_TRANSPORT_ATTEMPTS,
        "complete_file_bytes": None,
        "complete_file_sha256": None,
        "failures": failures,
        "retry_after_complete_hash": False,
    }
    raise ArtifactMaterializationFailed("ARTIFACT_MATERIALIZATION_FAILED", receipt)


def decompress_in_memory(payload: bytearray) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise RunnerDescriptionError("HATANAKA_DECOMPRESSION_DESCRIPTION_ERROR") from exc


def _write_json(path: Path, value: object, *, exclusive: bool = True) -> None:
    mode = "x" if exclusive else "w"
    with Path(path).open(mode, encoding="ascii", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def _not_evaluated(reason_class: str, reason: str) -> dict[str, object]:
    return {
        "schema": "gnss-drao-doy233-primary-outcome-v1",
        "outcome": "PRIMARY_NOT_EVALUATED",
        "reason_class": reason_class,
        "reason": reason,
        "clauses": {
            "artifact_complete_hash": "NOT_EVALUATED",
            "header_identity_and_time": "NOT_EVALUATED",
            "complete_seven_track_structure": "NOT_EVALUATED",
            "geometry_free_continuity": "NOT_EVALUATED",
            "same_path_witness_all_exclusions": "NOT_EVALUATED",
            "opaque_orbital_score": "NOT_EVALUATED",
        },
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
        raise PermissionError("DRAO_DOY233_PRIMARY_AUTHORITY_REQUIRED")
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    marker_path = output / MARKER_NAME
    outcome_path = output / OUTCOME_NAME
    if marker_path.exists() or outcome_path.exists():
        raise PermissionError("DRAO_DOY233_PRIMARY_AUTHORITY_ALREADY_CONSUMED")
    root = Path(__file__).resolve().parent
    seal = validate_seal(root, seal_path, expected_seal_sha256)
    marker = {
        "schema": "gnss-drao-doy233-primary-authority-consumed-v1",
        "state": "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK",
        "runner_seal_sha256": expected_seal_sha256,
        "runner_source_commit": seal["runner_source_commit"],
        "network_requests_before_marker": 0,
        "body_bytes_before_marker": 0,
        "observation_values_before_marker": 0,
    }
    _write_json(marker_path, marker)

    compressed: bytearray | None = None
    decoded: bytearray | None = None
    scan: primary.PrimaryScan | None = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materialize()
        artifact["hash_persisted_before_decompression"] = True
        _write_json(output / ARTIFACT_RECEIPT_NAME, artifact)
        decoded = decompress_in_memory(compressed)
        scan = primary._scan_decoded_fixture(
            decoded, artifact_site_id=primary.frozen.STATION
        )
        scientific = primary.execute_admitted_scan(scan, root)
        scan = None
        outcome = {
            "schema": "gnss-drao-doy233-primary-outcome-v1",
            "outcome": scientific["outcome"],
            "artifact": artifact,
            "artifact_receipt": {
                "name": ARTIFACT_RECEIPT_NAME,
                "canonical_sha256": canonical_sha256(
                    output / ARTIFACT_RECEIPT_NAME
                ),
            },
            "scientific_receipt": scientific,
            "runner_seal_sha256": expected_seal_sha256,
            "retry_after_complete_hash": 0,
            "persistence": {
                "compressed_artifact": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
                "derived_series": 0,
            },
        }
    except ArtifactMaterializationFailed as exc:
        outcome = _not_evaluated("ARTIFACT_MATERIALIZATION_FAILED", str(exc))
        outcome["materialization_receipt"] = exc.receipt
    except primary.PrimaryMeasurementInvalid as exc:
        outcome = {
            "schema": "gnss-drao-doy233-primary-outcome-v1",
            "outcome": "MEASUREMENT_INVALID",
            "reason_class": "STRUCTURAL_OR_PHYSICAL_ADMISSION_FAILURE",
            "reason": str(exc),
            "artifact": artifact,
            "orbital_score": "NOT_EVALUATED",
            "downstream_clauses": "NOT_EVALUATED",
            "observation_values_persisted": 0,
        }
    except (RunnerDescriptionError, primary.PrimaryDescriptionError) as exc:
        outcome = _not_evaluated("DESCRIPTION_ERROR", str(exc))
        outcome["artifact"] = artifact
    except Exception as exc:
        outcome = _not_evaluated(
            "DESCRIPTION_ERROR", f"{type(exc).__name__}:{exc}"
        )
        outcome["artifact"] = artifact
    finally:
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
    parser.add_argument(
        "--output-directory", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    if not args.execute_live or args.seal is None:
        raise SystemExit("SEPARATE_LIVE_AUTHORITY_AND_RUNNER_SEAL_REQUIRED")
    print(
        strict_json(
            run_once(
                args.output_directory,
                args.authority,
                args.seal,
                args.seal_sha256,
            )
        )
    )


if __name__ == "__main__":
    main()
