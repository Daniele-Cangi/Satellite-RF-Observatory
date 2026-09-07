"""One content-blind receipt replay for the exact frozen DRAO DOY232 artifact.

This is deliberately not a reusable downloader.  It can hash only the selected
compressed qualification artifact, cannot decode it, and persists the digest
before deleting the payload.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import BinaryIO, Final
from urllib.request import Request, urlopen


ARTIFACT_NAME: Final = "DRAO00CAN_R_20262320000_01D_30S_MO.crx.gz"
ARTIFACT_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/232/" + ARTIFACT_NAME
)
EXPECTED_BYTES: Final = 2_904_457
EXPECTED_ETAG: Final = '"2c5189-6598ad1ef8dbf"'
EXPECTED_LAST_MODIFIED: Final = "Fri, 21 Aug 2026 08:57:02 GMT"
AUTHORITY_NAME: Final = "GNSS_DRAO_DOY232_RECEIPT_REPLAY_AUTHORITY.json"
AUTHORITY_SHA256: Final = (
    "1d63f1b7f12b933ad67c19d8bbc0ee1a2f4510b475f32e28de901bd8b75f30f0"
)
BASE_COMMIT: Final = "1fabfb33e231e862e14812e12a414daba9dca1a3"
CHUNK_BYTES: Final = 64 * 1024

PREPARED = "DRAO_DOY232_RECEIPT_PREPARED_CLEANUP_PENDING"
FINAL = "DRAO_DOY232_RECEIPT_REPLAY_MATERIALIZED"
WriteReceipt = Callable[[Path, Mapping[str, object]], None]


class ReceiptReplayError(RuntimeError):
    """The bounded replay could not produce its exact integrity receipt."""


class FrozenIdentityError(ReceiptReplayError):
    """The response does not match frozen artifact identity metadata."""


class MaterializationError(ReceiptReplayError):
    """The complete compressed artifact could not be materialized."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    """Serialize only standard finite JSON scalars."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_runtime_binding(source_commit: str) -> None:
    """Bind network execution to the committed authority and source tree."""

    _validate_source_commit(source_commit)
    module_path = Path(__file__).resolve()
    authority_path = module_path.with_name(AUTHORITY_NAME)
    if file_sha256(authority_path) != AUTHORITY_SHA256:
        raise ReceiptReplayError("AUTHORITY_SHA256_CHANGED")
    repository = module_path.parents[2]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != source_commit:
        raise ReceiptReplayError("EXECUTED_SOURCE_COMMIT_IS_NOT_HEAD")
    dirty = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            str(module_path.relative_to(repository)),
            str(authority_path.relative_to(repository)),
        ],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if dirty:
        raise ReceiptReplayError("EXECUTION_BINDING_FILES_ARE_DIRTY")


def _atomic_receipt(path: Path, value: Mapping[str, object]) -> None:
    """Replace a receipt atomically; never truncate the last valid receipt."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if temporary.exists():
        raise MaterializationError("RECEIPT_TEMPORARY_ALREADY_EXISTS")
    try:
        with temporary.open("x", encoding="ascii", newline="\n") as stream:
            stream.write(strict_json(value, pretty=True))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _header(headers: Mapping[str, str], name: str) -> str | None:
    value = headers.get(name)
    if value is None:
        value = headers.get(name.lower())
    if value is None:
        return None
    return str(value).strip()


def validate_response_metadata(
    *, status: int, final_url: str, headers: Mapping[str, str]
) -> dict[str, object]:
    """Validate descriptors without treating absent GET length as content loss."""

    if status != 200:
        raise FrozenIdentityError(f"HTTP_STATUS_CHANGED:{status}")
    if final_url != ARTIFACT_URL:
        raise FrozenIdentityError("FINAL_URL_CHANGED")

    content_encoding = _header(headers, "Content-Encoding")
    if content_encoding is not None and content_encoding.lower() != "identity":
        raise FrozenIdentityError("CONTENT_ENCODING_NOT_IDENTITY")

    content_length = _header(headers, "Content-Length")
    if content_length is None:
        length_receipt: dict[str, object] = {"state": "ABSENT", "value": None}
    else:
        try:
            parsed_length = int(content_length)
        except ValueError as exc:
            raise FrozenIdentityError("GET_CONTENT_LENGTH_NOT_INTEGER") from exc
        if parsed_length != EXPECTED_BYTES:
            raise FrozenIdentityError("GET_CONTENT_LENGTH_CHANGED")
        length_receipt = {"state": "PRESENT_AND_MATCHED", "value": parsed_length}

    etag = _header(headers, "ETag")
    if etag is not None and etag != EXPECTED_ETAG:
        raise FrozenIdentityError("ETAG_CHANGED")
    last_modified = _header(headers, "Last-Modified")
    if last_modified is not None and last_modified != EXPECTED_LAST_MODIFIED:
        raise FrozenIdentityError("LAST_MODIFIED_CHANGED")

    return {
        "content_encoding": {
            "state": "ABSENT" if content_encoding is None else "PRESENT_AND_IDENTITY",
            "value": content_encoding,
        },
        "content_length": length_receipt,
        "etag": {
            "state": "ABSENT" if etag is None else "PRESENT_AND_MATCHED",
            "value": etag,
        },
        "last_modified": {
            "state": "ABSENT" if last_modified is None else "PRESENT_AND_MATCHED",
            "value": last_modified,
        },
    }


def _validate_source_commit(source_commit: str) -> None:
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ValueError("SOURCE_COMMIT_MUST_BE_FULL_LOWERCASE_GIT_OID")


def _artifact_path(quarantine_dir: Path) -> Path:
    resolved_dir = quarantine_dir.resolve()
    artifact = (resolved_dir / ARTIFACT_NAME).resolve()
    if artifact.parent != resolved_dir or artifact.name != ARTIFACT_NAME:
        raise MaterializationError("UNSAFE_QUARANTINE_ARTIFACT_PATH")
    return artifact


def _stream_to_artifact(stream: BinaryIO, artifact: Path) -> tuple[int, str]:
    digest = sha256()
    count = 0
    with artifact.open("xb") as output:
        while chunk := stream.read(CHUNK_BYTES):
            if not isinstance(chunk, bytes):
                raise MaterializationError("RESPONSE_STREAM_RETURNED_NON_BYTES")
            output.write(chunk)
            digest.update(chunk)
            count += len(chunk)
        output.flush()
        os.fsync(output.fileno())
    if count != EXPECTED_BYTES:
        raise MaterializationError(
            f"ACTUAL_COMPLETE_BYTE_COUNT_CHANGED:{count}:{EXPECTED_BYTES}"
        )
    return count, digest.hexdigest()


def _base_receipt(
    *,
    source_commit: str,
    response_metadata: Mapping[str, object],
    actual_bytes: int,
    digest: str,
) -> dict[str, object]:
    return {
        "access": {
            "compressed_artifact_bytes_hashed": actual_bytes,
            "decompression_attempted": False,
            "observation_headers_parsed": 0,
            "observation_values_accessed": 0,
            "primary_headers_parsed": 0,
            "primary_locators": 0,
            "primary_payload_bytes": 0,
            "primary_values_accessed": 0,
            "transport_attempts": 1,
        },
        "artifact": {
            "actual_complete_bytes": actual_bytes,
            "complete_sha256": digest,
            "expected_bytes": EXPECTED_BYTES,
            "name": ARTIFACT_NAME,
            "role": "QUALIFICATION_ONLY_NEVER_SCORED_NEVER_PRIMARY",
            "url": ARTIFACT_URL,
        },
        "authority": {
            "authority_name": AUTHORITY_NAME,
            "authority_sha256": AUTHORITY_SHA256,
            "base_commit": BASE_COMMIT,
            "executed_source_commit": source_commit,
            "materializer_code_sha256": file_sha256(Path(__file__).resolve()),
        },
        "new_gate": False,
        "physical_claims_authorized": [],
        "physical_decision": "NOT_EVALUATED",
        "qualification_clauses": {
            "artifact_identity": (
                "COMPLETE_HASH_CAPTURED_PHYSICAL_ADMISSION_NOT_EVALUATED"
            ),
            "complete_core_phase": "NOT_EVALUATED",
            "complete_same_path_code": "NOT_EVALUATED",
            "cycle_slip_and_continuity": "NOT_EVALUATED",
            "header_identity_and_time": "NOT_EVALUATED",
            "physical_same_path_witness": "NOT_EVALUATED",
        },
        "response_metadata": dict(response_metadata),
        "schema": "gnss-drao-doy232-receipt-replay-v1",
    }


def materialize_stream(
    stream: BinaryIO,
    *,
    status: int,
    final_url: str,
    headers: Mapping[str, str],
    quarantine_dir: Path,
    receipt_path: Path,
    source_commit: str,
    writer: WriteReceipt = _atomic_receipt,
) -> dict[str, object]:
    """Hash the exact compressed stream, persist integrity, then remove it."""

    _validate_source_commit(source_commit)
    if AUTHORITY_SHA256 == "PENDING_FREEZE":
        raise ReceiptReplayError("AUTHORITY_SHA256_NOT_FROZEN")
    if receipt_path.exists():
        raise ReceiptReplayError("RECEIPT_ALREADY_EXISTS")
    metadata = validate_response_metadata(
        status=status, final_url=final_url, headers=headers
    )
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    artifact = _artifact_path(quarantine_dir)
    if artifact.exists():
        raise MaterializationError("QUARANTINE_ARTIFACT_ALREADY_EXISTS")

    prepared_written = False
    try:
        actual_bytes, digest = _stream_to_artifact(stream, artifact)
        receipt = _base_receipt(
            source_commit=source_commit,
            response_metadata=metadata,
            actual_bytes=actual_bytes,
            digest=digest,
        )
        receipt.update(
            {
                "cleanup": {
                    "artifact_unlinked": False,
                    "payload_retained": True,
                    "state": "PENDING",
                },
                "next_maximum": "COMPLETE_OFFLINE_CLEANUP_THEN_SEPARATE_REVIEW",
                "outcome": PREPARED,
                "stop": "NO_DECOMPRESSION_HEADER_VALUE_OR_PRIMARY_ACCESS",
            }
        )
        writer(receipt_path, receipt)
        prepared_written = True

        artifact.unlink()
        directory_removed = False
        try:
            quarantine_dir.rmdir()
            directory_removed = True
        except OSError:
            # An unrelated file may keep the directory alive; the RF artifact is gone.
            pass

        receipt["cleanup"] = {
            "artifact_unlinked": True,
            "payload_retained": False,
            "quarantine_directory_removed": directory_removed,
            "state": "CONFIRMED",
        }
        receipt["next_maximum"] = (
            "SEPARATE_REVIEW_THEN_MODEL_BLIND_DOY232_STRUCTURAL_QUALIFICATION"
        )
        receipt["outcome"] = FINAL
        writer(receipt_path, receipt)
        return receipt
    except Exception:
        if not prepared_written and artifact.exists():
            artifact.unlink()
            try:
                quarantine_dir.rmdir()
            except OSError:
                pass
        raise


def finalize_prepared_receipt(
    *,
    quarantine_dir: Path,
    receipt_path: Path,
    writer: WriteReceipt = _atomic_receipt,
) -> dict[str, object]:
    """Finish cleanup after a crash without network or content re-exposure."""

    value = json.loads(
        receipt_path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if value.get("outcome") != PREPARED:
        raise ReceiptReplayError("RECEIPT_IS_NOT_PREPARED")
    integrity = value.get("artifact", {})
    if not isinstance(integrity, dict) or not integrity.get("complete_sha256"):
        raise ReceiptReplayError("PREPARED_RECEIPT_HAS_NO_DIGEST")
    artifact = _artifact_path(quarantine_dir)
    if artifact.exists():
        artifact.unlink()
    directory_removed = False
    try:
        quarantine_dir.rmdir()
        directory_removed = True
    except OSError:
        pass
    value["cleanup"] = {
        "artifact_unlinked": True,
        "payload_retained": False,
        "quarantine_directory_removed": directory_removed,
        "state": "CONFIRMED",
    }
    value["next_maximum"] = (
        "SEPARATE_REVIEW_THEN_MODEL_BLIND_DOY232_STRUCTURAL_QUALIFICATION"
    )
    value["outcome"] = FINAL
    writer(receipt_path, value)
    return value


def execute_network(
    *, quarantine_dir: Path, receipt_path: Path, source_commit: str
) -> dict[str, object]:
    """Perform the one authorized exact-URL transport attempt."""

    _validate_runtime_binding(source_commit)
    request = Request(
        ARTIFACT_URL,
        headers={
            "Accept-Encoding": "identity",
            "User-Agent": "Satellite-RF-Observatory/1",
        },
        method="GET",
    )
    # S310 is inapplicable: ARTIFACT_URL is an immutable, exact HTTPS constant.
    with urlopen(request, timeout=120) as response:
        return materialize_stream(
            response,
            status=int(response.status),
            final_url=response.geturl(),
            headers=response.headers,
            quarantine_dir=quarantine_dir,
            receipt_path=receipt_path,
            source_commit=source_commit,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarantine", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument(
        "--finalize-prepared",
        action="store_true",
        help="perform cleanup only; never opens the network",
    )
    args = parser.parse_args()
    if args.finalize_prepared:
        result = finalize_prepared_receipt(
            quarantine_dir=args.quarantine, receipt_path=args.receipt
        )
    else:
        result = execute_network(
            quarantine_dir=args.quarantine,
            receipt_path=args.receipt,
            source_commit=args.source_commit,
        )
    print(strict_json(result))


if __name__ == "__main__":
    main()
