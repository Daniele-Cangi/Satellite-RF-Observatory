"""Offline verification for the Gate F2.5.6 pinned-source reproduction."""

from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import zipfile

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_6 as f256


def _manifest() -> dict[str, object]:
    return f256.load_manifest_strict()


def _repo(manifest: dict[str, object], project: str) -> dict[str, object]:
    return next(
        item for item in manifest["repositories"] if item["project"] == project
    )


def test_current_source_basis_fails_closed_at_license_boundary() -> None:
    assessment = f256.assess_gate_f2_5_6()

    assert assessment.exit is f256.F256Exit.SOURCE_RETENTION_BLOCKED_BY_LICENSE
    assert assessment.server_source_reproducible
    assert assessment.client_source_locations_resolved
    assert not assessment.client_source_reproducible
    assert assessment.source_semantics_resolved
    assert not assessment.receipt_implementation_authorised
    assert not assessment.live_execution_authorised
    assert assessment.artifact_errors == ()


def test_server_archive_identity_members_and_source_bytes_are_exact() -> None:
    manifest = _manifest()
    verification = f256.verify_server_archive(manifest)
    server = _repo(manifest, "KiwiSDR server")
    expected = tuple(item["path"] for item in server["artifact"]["members"])

    assert verification.valid, verification.errors
    assert verification.archive_sha256 == (
        "d6a50adfce7f75133020de85635711dc6c2218e6f134d901ac13a450b57de7ea"
    )
    assert verification.archive_size_bytes == 59311
    assert set(verification.verified_members) == set(expected)


def test_archive_contains_only_allowlisted_server_material() -> None:
    manifest = _manifest()
    server = _repo(manifest, "KiwiSDR server")
    archive_path = f256.DEFAULT_MANIFEST_PATH.parent / server["artifact"]["path"]

    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()

    assert names == [
        "_LICENSE",
        "rx/",
        "rx/rx_cmd.cpp",
        "rx/rx_cmd.h",
        "rx/rx_server.cpp",
        "rx/rx_sound.cpp",
        "rx/rx_sound_cmd.cpp",
    ]
    assert all(not name.startswith("kiwi/") for name in names)


def test_client_source_is_hash_audited_but_not_retained() -> None:
    manifest = _manifest()
    client = _repo(manifest, "kiwiclient")
    source_dir = f256.DEFAULT_MANIFEST_PATH.parent

    assert client["retention_state"] == "NOT_RETAINED_NO_LICENSE_GRANT_FOUND"
    assert client["github_license_metadata"] is None
    assert {item["path"] for item in client["audited_files"]} >= {
        "kiwi/client.py",
        "kiwi/worker.py",
    }
    assert all(
        f256.SHA256_PATTERN.fullmatch(item["sha256"])
        for item in client["audited_files"]
    )
    retained_names = {
        path.relative_to(source_dir).as_posix()
        for path in source_dir.rglob("*")
        if path.is_file()
    }
    assert retained_names == {
        "kiwisdr-c40ecb471dced33689e335689f8ffd35a54f47fa.zip",
        "manifest.json",
    }


def test_exact_client_control_path_is_no_longer_unresolved() -> None:
    manifest = _manifest()
    client = _repo(manifest, "kiwiclient")
    client_py = next(
        item for item in client["audited_files"] if item["path"] == "kiwi/client.py"
    )

    assert "434-527" in client_py["relevant_spans"]
    assert "550-592" in client_py["relevant_spans"]
    assert "887-925" in client_py["relevant_spans"]
    assert not any(
        "UNRESOLVED" in span
        for item in client["audited_files"]
        for span in item["relevant_spans"]
    )


def test_source_findings_preserve_narrow_protocol_semantics() -> None:
    findings = {item["finding_id"]: item for item in _manifest()["source_findings"]}

    assert set(findings) == {
        "AUTH_GATE_ORDER",
        "BADP_SEMANTICS",
        "CHANNEL_ALLOCATION",
        "PER_CHANNEL_RETUNE",
        "SND_SETUP_AND_IQ",
        "CHANNEL_IDENTIFIER_GAP",
        "TERMINATION_DISTINCTION",
    }
    assert "badp=0" in findings["BADP_SEMANTICS"]["claim"]
    assert "conn->rx_channel" in findings["PER_CHANNEL_RETUNE"]["claim"]
    assert "is_local=channel" in findings["CHANNEL_IDENTIFIER_GAP"]["claim"]


def test_manifest_is_strict_json_and_records_zero_rf_persistence() -> None:
    raw = f256.DEFAULT_MANIFEST_PATH.read_text(encoding="utf-8")
    manifest = f256.parse_manifest_strict(raw)

    assert json.dumps(manifest, allow_nan=False)
    assert manifest["retention_policy"] == {
        "rf_persisted": False,
        "client_source_persisted": False,
        "credentials_persisted": False,
        "temporary_clones_must_be_destroyed_after_verification": True,
    }
    with pytest.raises(ValueError, match="non-finite"):
        f256.parse_manifest_strict('{"value": NaN}')
    with pytest.raises(ValueError, match="duplicate"):
        f256.parse_manifest_strict('{"value": 1, "value": 2}')


def test_archive_tamper_fails_without_changing_protocol_claims() -> None:
    manifest = _manifest()
    server = _repo(manifest, "KiwiSDR server")
    artifact = server["artifact"]
    archive_path = f256.DEFAULT_MANIFEST_PATH.parent / artifact["path"]
    tampered = archive_path.read_bytes() + b"tamper"

    verification = f256.verify_archive_bytes(tampered, artifact)

    assert not verification.valid
    assert "archive SHA-256 mismatch" in verification.errors
    assert "archive byte count mismatch" in verification.errors


def test_manifest_cannot_hide_an_extra_or_missing_archive_member() -> None:
    manifest = _manifest()
    server = _repo(manifest, "KiwiSDR server")
    artifact = deepcopy(server["artifact"])
    archive_path = f256.DEFAULT_MANIFEST_PATH.parent / artifact["path"]
    artifact["members"] = artifact["members"][:-1]

    verification = f256.verify_archive_bytes(archive_path.read_bytes(), artifact)

    assert not verification.valid
    assert "archive membership differs from the manifest" in verification.errors


def test_invalid_or_missing_artifact_never_authorises_implementation() -> None:
    missing_manifest = Path("manifest-that-does-not-exist-f256.json")

    assessment = f256.assess_gate_f2_5_6(missing_manifest)

    assert assessment.exit is f256.F256Exit.SOURCE_ARTIFACT_INVALID
    assert not assessment.receipt_implementation_authorised
    assert not assessment.live_execution_authorised


def test_module_has_no_network_or_runtime_entrypoint() -> None:
    source = inspect.getsource(f256)

    assert "import socket" not in source
    assert "import requests" not in source
    assert "urllib" not in source
    assert "websocket" not in source.lower()
    assert "if __name__" not in source
    assert not hasattr(f256, "run_live")
