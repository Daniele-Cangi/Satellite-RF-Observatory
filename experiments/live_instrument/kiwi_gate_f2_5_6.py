"""Gate F2.5.6: reproduce the pinned protocol source basis offline.

This module verifies a deliberately small server-source archive and records a
hash-only client audit.  It is not a Kiwi client and performs no network I/O.
The missing client license grant is an explicit retention boundary, not an
excuse to copy the source or to infer protocol behavior from memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import io
import json
from pathlib import Path
import re
from typing import Any, Mapping
import zipfile


F256_TRANSFORM_VERSION = "gate-f2.5.6-pinned-source-reproduction-v1"
F256_MANIFEST_SCHEMA = "gate-f2.5.6-source-manifest-v1"
PARENT_GATE_COMMIT = "593fae7fe58ea4b1de847390fb897e688abcf0ac"
KIWI_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
KIWICLIENT_COMMIT = "4eb733e6b6147f7fbeb97ced64cdac029b202d18"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MANIFEST_PATH = (
    Path(__file__).with_name("protocol_sources") / "gate_f2_5_6" / "manifest.json"
)


class F256Exit(str, Enum):
    SOURCE_BASIS_REPRODUCIBLE = "SOURCE_BASIS_REPRODUCIBLE"
    SOURCE_RETENTION_BLOCKED_BY_LICENSE = "SOURCE_RETENTION_BLOCKED_BY_LICENSE"
    SOURCE_ARTIFACT_INVALID = "SOURCE_ARTIFACT_INVALID"


@dataclass(frozen=True, slots=True)
class ArchiveVerification:
    valid: bool
    errors: tuple[str, ...]
    archive_sha256: str
    archive_size_bytes: int
    verified_members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class F256Assessment:
    exit: F256Exit
    server_source_reproducible: bool
    client_source_locations_resolved: bool
    client_source_reproducible: bool
    source_semantics_resolved: bool
    receipt_implementation_authorised: bool
    live_execution_authorised: bool
    artifact_errors: tuple[str, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


def _reject_nonfinite(token: str) -> None:
    raise ValueError(f"non-finite JSON constant is forbidden: {token}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key is forbidden: {key}")
        result[key] = value
    return result


def parse_manifest_strict(payload: bytes | str) -> dict[str, Any]:
    """Parse manifest JSON while rejecting non-finite values and duplicate keys."""

    text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    value = json.loads(
        text,
        parse_constant=_reject_nonfinite,
        object_pairs_hook=_unique_object,
    )
    if not isinstance(value, dict):
        raise ValueError("source manifest must be one JSON object")
    return value


def load_manifest_strict(path: Path = DEFAULT_MANIFEST_PATH) -> dict[str, Any]:
    return parse_manifest_strict(path.read_bytes())


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _repository(manifest: Mapping[str, Any], project: str) -> Mapping[str, Any]:
    repositories = manifest.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("manifest repositories must be a list")
    matches = [
        item
        for item in repositories
        if isinstance(item, dict) and item.get("project") == project
    ]
    if len(matches) != 1 or not isinstance(matches[0], dict):
        raise ValueError(f"manifest requires exactly one {project} repository")
    return matches[0]


def _validate_member_spec(member: Mapping[str, Any]) -> tuple[str, str | None, int, int]:
    path = member.get("path")
    digest = member.get("sha256")
    size = member.get("size_bytes")
    line_count = member.get("line_count")
    if not isinstance(path, str) or not path or path.startswith(("/", "\\")):
        raise ValueError("archive member path must be relative and non-empty")
    if ".." in Path(path).parts:
        raise ValueError(f"archive member escapes its root: {path}")
    if digest is not None and (
        not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest)
    ):
        raise ValueError(f"invalid member SHA-256: {path}")
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        raise ValueError(f"invalid member size: {path}")
    if not isinstance(line_count, int) or isinstance(line_count, bool) or line_count < 0:
        raise ValueError(f"invalid member line count: {path}")
    return path, digest, size, line_count


def verify_archive_bytes(
    archive_bytes: bytes,
    artifact_spec: Mapping[str, Any],
) -> ArchiveVerification:
    """Verify archive identity, exact membership and every retained source file."""

    errors: list[str] = []
    actual_digest = _sha256(archive_bytes)
    expected_digest = artifact_spec.get("sha256")
    expected_size = artifact_spec.get("size_bytes")
    if not isinstance(expected_digest, str) or not SHA256_PATTERN.fullmatch(
        expected_digest
    ):
        errors.append("manifest archive SHA-256 is invalid")
    elif actual_digest != expected_digest:
        errors.append("archive SHA-256 mismatch")
    if not isinstance(expected_size, int) or isinstance(expected_size, bool):
        errors.append("manifest archive size is invalid")
    elif len(archive_bytes) != expected_size:
        errors.append("archive byte count mismatch")

    raw_members = artifact_spec.get("members")
    member_specs: dict[str, tuple[str | None, int, int]] = {}
    if not isinstance(raw_members, list) or not raw_members:
        errors.append("manifest archive member list is missing")
    else:
        try:
            for raw_member in raw_members:
                if not isinstance(raw_member, dict):
                    raise ValueError("archive member specification must be an object")
                path, digest, size, line_count = _validate_member_spec(raw_member)
                if path in member_specs:
                    raise ValueError(f"duplicate archive member specification: {path}")
                member_specs[path] = (digest, size, line_count)
        except ValueError as exc:
            errors.append(str(exc))

    verified: list[str] = []
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("archive contains duplicate member names")
            if set(names) != set(member_specs):
                errors.append("archive membership differs from the manifest")
            for path, (digest, size, line_count) in member_specs.items():
                if path not in names:
                    continue
                data = archive.read(path)
                if len(data) != size:
                    errors.append(f"member byte count mismatch: {path}")
                if digest is None:
                    if not path.endswith("/") or data:
                        errors.append(f"unhashed member is not an empty directory: {path}")
                elif _sha256(data) != digest:
                    errors.append(f"member SHA-256 mismatch: {path}")
                if len(data.splitlines()) != line_count:
                    errors.append(f"member line count mismatch: {path}")
                if not any(error.endswith(path) for error in errors):
                    verified.append(path)
    except (zipfile.BadZipFile, RuntimeError, OSError) as exc:
        errors.append(f"archive cannot be read: {type(exc).__name__}")

    return ArchiveVerification(
        valid=not errors,
        errors=tuple(errors),
        archive_sha256=actual_digest,
        archive_size_bytes=len(archive_bytes),
        verified_members=tuple(verified),
    )


def verify_server_archive(
    manifest: Mapping[str, Any],
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> ArchiveVerification:
    server = _repository(manifest, "KiwiSDR server")
    artifact = server.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError("server repository requires one retained artifact")
    artifact_name = artifact.get("path")
    if not isinstance(artifact_name, str) or Path(artifact_name).name != artifact_name:
        raise ValueError("server artifact path must be one local filename")
    archive_bytes = manifest_path.parent.joinpath(artifact_name).read_bytes()
    return verify_archive_bytes(archive_bytes, artifact)


def _client_locations_resolved(client: Mapping[str, Any]) -> bool:
    files = client.get("audited_files")
    if not isinstance(files, list) or not files:
        return False
    required = {"kiwi/client.py", "kiwi/worker.py"}
    paths = {item.get("path") for item in files if isinstance(item, dict)}
    if not required <= paths:
        return False
    for item in files:
        if not isinstance(item, dict):
            return False
        if not SHA256_PATTERN.fullmatch(str(item.get("sha256", ""))):
            return False
        if not re.fullmatch(r"[0-9a-f]{40}", str(item.get("git_blob", ""))):
            return False
        spans = item.get("relevant_spans")
        if not isinstance(spans, list):
            return False
    client_py = next(item for item in files if item.get("path") == "kiwi/client.py")
    return bool(client_py.get("relevant_spans"))


def assess_gate_f2_5_6(
    manifest_path: Path = DEFAULT_MANIFEST_PATH,
) -> F256Assessment:
    """Assess the local source basis without contacting either repository."""

    try:
        manifest = load_manifest_strict(manifest_path)
        if manifest.get("schema_version") != F256_MANIFEST_SCHEMA:
            raise ValueError("unexpected source manifest schema")
        if manifest.get("outcome") != F256Exit.SOURCE_RETENTION_BLOCKED_BY_LICENSE:
            raise ValueError("manifest outcome differs from the frozen gate outcome")
        if manifest.get("frozen_parent_commit") != PARENT_GATE_COMMIT:
            raise ValueError("source manifest parent commit differs from the frozen gate")
        server = _repository(manifest, "KiwiSDR server")
        client = _repository(manifest, "kiwiclient")
        if server.get("commit") != KIWI_SERVER_COMMIT:
            raise ValueError("server source commit differs from the frozen commit")
        if client.get("commit") != KIWICLIENT_COMMIT:
            raise ValueError("client source commit differs from the frozen commit")
        archive = verify_server_archive(manifest, manifest_path)
        client_resolved = _client_locations_resolved(client)
        client_retained = (
            client.get("retention_state") == "RETAINED_WITH_LICENSE_EVIDENCE"
            and isinstance(client.get("artifact"), dict)
        )
        if not archive.valid or not client_resolved:
            return F256Assessment(
                exit=F256Exit.SOURCE_ARTIFACT_INVALID,
                server_source_reproducible=archive.valid,
                client_source_locations_resolved=client_resolved,
                client_source_reproducible=False,
                source_semantics_resolved=False,
                receipt_implementation_authorised=False,
                live_execution_authorised=False,
                artifact_errors=archive.errors
                + (() if client_resolved else ("client source locations invalid",)),
                authorised_claims=("the local source package failed verification",),
                unauthorised_claims=(
                    "the pinned protocol semantics are locally reproducible",
                    "the ordered receipt may be integrated",
                    "another live execution is authorised",
                ),
            )
        if client_retained:
            exit_state = F256Exit.SOURCE_BASIS_REPRODUCIBLE
        else:
            exit_state = F256Exit.SOURCE_RETENTION_BLOCKED_BY_LICENSE
        return F256Assessment(
            exit=exit_state,
            server_source_reproducible=True,
            client_source_locations_resolved=True,
            client_source_reproducible=client_retained,
            source_semantics_resolved=True,
            receipt_implementation_authorised=False,
            live_execution_authorised=False,
            artifact_errors=(),
            authorised_claims=(
                "badp=0 is the pinned server authentication-success value",
                "badp=5 is the pinned server no-multiple-connections value",
                "too_busy is an explicit server capacity response",
                "a tune command addresses conn->rx_channel at the per-channel DDC cut",
                "the official client source locations for ordered MSG and termination handling are resolved",
                "the full client source basis is not locally reproducible because no license grant was found",
            ),
            unauthorised_claims=(
                "badp=0 proves channel configuration or IQ readiness",
                "the eleven frozen closures have one inferred cause",
                "the frozen local client is conformant or nonconformant",
                "the ordered receipt may be integrated without another review",
                "another live execution is authorised",
            ),
        )
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return F256Assessment(
            exit=F256Exit.SOURCE_ARTIFACT_INVALID,
            server_source_reproducible=False,
            client_source_locations_resolved=False,
            client_source_reproducible=False,
            source_semantics_resolved=False,
            receipt_implementation_authorised=False,
            live_execution_authorised=False,
            artifact_errors=(f"{type(exc).__name__}: {exc}",),
            authorised_claims=("the local source package failed verification",),
            unauthorised_claims=(
                "the pinned protocol semantics are locally reproducible",
                "the ordered receipt may be integrated",
                "another live execution is authorised",
            ),
        )
