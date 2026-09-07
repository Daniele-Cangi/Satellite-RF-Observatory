from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_doy232_receipt_replay as replay,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY = ROOT / "GNSS_DRAO_DOY232_RECEIPT_REPLAY_AUTHORITY.json"
RECEIPT = ROOT / "GNSS_DRAO_DOY232_RECEIPT_REPLAY.json"
SOURCE_COMMIT = "a" * 40


def authority() -> dict[str, object]:
    return json.loads(
        AUTHORITY.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )


def test_authority_changes_no_physics_and_authorizes_no_access() -> None:
    value = authority()

    assert value["outcome"] == "DRAO_DOY232_RECEIPT_REPLAY_AUTHORIZED_NOT_EXECUTED"
    assert value["new_gate"] is False
    assert value["physical_decision"] == "NOT_EVALUATED"
    assert value["physical_claims_authorized"] == []
    assert value["boundary"]["physical_parameters_changed"] is False
    assert value["boundary"]["receipt_replay_transport_attempts_authorized"] == 1
    assert value["access"]["observation_body_bytes"] == 0
    assert value["access"]["observation_headers_parsed"] == 0
    assert value["access"]["observation_values_accessed"] == 0
    assert value["access"]["primary_payload_bytes"] == 0


def test_authority_binds_exact_historical_artifacts() -> None:
    value = authority()["authority"]

    assert replay.AUTHORITY_SHA256 == replay.file_sha256(AUTHORITY)
    assert value["base_commit"] == "1fabfb33e231e862e14812e12a414daba9dca1a3"
    assert value["selection"]["sha256"] == replay.file_sha256(
        ROOT / value["selection"]["name"]
    )
    assert value["description_error"]["sha256"] == replay.file_sha256(
        ROOT / value["description_error"]["name"]
    )
    assert value["contract"]["sha256"] == replay.file_sha256(
        ROOT / value["contract"]["name"]
    )


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: bytes,
    *,
    headers: dict[str, str] | None = None,
    writer: replay.WriteReceipt = replay._atomic_receipt,
) -> tuple[dict[str, object], Path, Path]:
    monkeypatch.setattr(replay, "EXPECTED_BYTES", len(payload))
    monkeypatch.setattr(replay, "AUTHORITY_SHA256", "f" * 64)
    quarantine = tmp_path / "quarantine"
    receipt = tmp_path / "receipt.json"
    value = replay.materialize_stream(
        BytesIO(payload),
        status=200,
        final_url=replay.ARTIFACT_URL,
        headers=headers or {},
        quarantine_dir=quarantine,
        receipt_path=receipt,
        source_commit=SOURCE_COMMIT,
        writer=writer,
    )
    return value, quarantine, receipt


def test_missing_get_content_length_is_accepted_and_actual_count_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"opaque compressed fixture"
    value, quarantine, receipt = _run(tmp_path, monkeypatch, payload)

    assert value["outcome"] == replay.FINAL
    assert value["artifact"]["actual_complete_bytes"] == len(payload)
    assert value["artifact"]["complete_sha256"] == replay.sha256(payload).hexdigest()
    assert value["response_metadata"]["content_length"] == {
        "state": "ABSENT",
        "value": None,
    }
    assert value["cleanup"]["payload_retained"] is False
    assert not (quarantine / replay.ARTIFACT_NAME).exists()
    assert json.loads(receipt.read_text(encoding="ascii"))["outcome"] == replay.FINAL


def test_present_content_length_must_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(replay, "EXPECTED_BYTES", 5)
    monkeypatch.setattr(replay, "AUTHORITY_SHA256", "f" * 64)

    with pytest.raises(replay.FrozenIdentityError, match="GET_CONTENT_LENGTH_CHANGED"):
        replay.materialize_stream(
            BytesIO(b"abcde"),
            status=200,
            final_url=replay.ARTIFACT_URL,
            headers={"Content-Length": "4"},
            quarantine_dir=tmp_path / "quarantine",
            receipt_path=tmp_path / "receipt.json",
            source_commit=SOURCE_COMMIT,
        )

    assert not (tmp_path / "receipt.json").exists()
    assert not (tmp_path / "quarantine" / replay.ARTIFACT_NAME).exists()


def test_optional_descriptors_may_be_absent_but_must_match_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _run(tmp_path, monkeypatch, b"abc")
    with pytest.raises(replay.FrozenIdentityError, match="ETAG_CHANGED"):
        replay.validate_response_metadata(
            status=200,
            final_url=replay.ARTIFACT_URL,
            headers={"ETag": '"different"'},
        )


def test_incomplete_stream_is_removed_without_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(replay, "EXPECTED_BYTES", 10)
    monkeypatch.setattr(replay, "AUTHORITY_SHA256", "f" * 64)
    quarantine = tmp_path / "quarantine"

    with pytest.raises(
        replay.MaterializationError, match="ACTUAL_COMPLETE_BYTE_COUNT_CHANGED"
    ):
        replay.materialize_stream(
            BytesIO(b"short"),
            status=200,
            final_url=replay.ARTIFACT_URL,
            headers={},
            quarantine_dir=quarantine,
            receipt_path=tmp_path / "receipt.json",
            source_commit=SOURCE_COMMIT,
        )

    assert not (quarantine / replay.ARTIFACT_NAME).exists()
    assert not (tmp_path / "receipt.json").exists()


def test_final_receipt_write_failure_preserves_prepared_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes = 0

    def fail_second_write(path: Path, value: Mapping[str, object]) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("simulated final receipt failure")
        replay._atomic_receipt(path, value)

    with pytest.raises(OSError, match="simulated final receipt failure"):
        _run(
            tmp_path,
            monkeypatch,
            b"digest survives",
            writer=fail_second_write,
        )

    receipt = json.loads((tmp_path / "receipt.json").read_text(encoding="ascii"))
    assert receipt["outcome"] == replay.PREPARED
    assert receipt["artifact"]["actual_complete_bytes"] == len(b"digest survives")
    assert receipt["artifact"]["complete_sha256"] == replay.sha256(
        b"digest survives"
    ).hexdigest()
    assert not (tmp_path / "quarantine" / replay.ARTIFACT_NAME).exists()


def test_prepared_receipt_can_be_finalized_without_network_or_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes = 0

    def fail_second_write(path: Path, value: Mapping[str, object]) -> None:
        nonlocal writes
        writes += 1
        if writes == 2:
            raise OSError("stop after cleanup")
        replay._atomic_receipt(path, value)

    with pytest.raises(OSError):
        _run(tmp_path, monkeypatch, b"opaque", writer=fail_second_write)

    result = replay.finalize_prepared_receipt(
        quarantine_dir=tmp_path / "quarantine",
        receipt_path=tmp_path / "receipt.json",
    )
    assert result["outcome"] == replay.FINAL
    assert result["cleanup"]["payload_retained"] is False
    assert result["access"]["decompression_attempted"] is False


def test_strict_json_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError):
        replay.strict_json({"bad": float("nan")})


def test_real_replay_receipt_freezes_integrity_and_cleanup() -> None:
    value = json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )

    assert value["outcome"] == replay.FINAL
    assert value["physical_decision"] == "NOT_EVALUATED"
    assert value["physical_claims_authorized"] == []
    assert value["artifact"]["actual_complete_bytes"] == 2_904_457
    assert value["artifact"]["expected_bytes"] == 2_904_457
    assert value["artifact"]["complete_sha256"] == (
        "fca688310e9bd48a70452e0f9409a24d4b036add44ee31024ca1d76e130fe8d3"
    )
    assert value["cleanup"] == {
        "artifact_unlinked": True,
        "payload_retained": False,
        "quarantine_directory_removed": True,
        "state": "CONFIRMED",
    }


def test_real_replay_receipt_preserves_scientific_seal() -> None:
    value = json.loads(RECEIPT.read_text(encoding="ascii"))
    access = value["access"]

    assert access["transport_attempts"] == 1
    assert access["compressed_artifact_bytes_hashed"] == 2_904_457
    assert access["decompression_attempted"] is False
    assert access["observation_headers_parsed"] == 0
    assert access["observation_values_accessed"] == 0
    assert access["primary_locators"] == 0
    assert access["primary_headers_parsed"] == 0
    assert access["primary_payload_bytes"] == 0
    assert access["primary_values_accessed"] == 0
    assert set(value["qualification_clauses"].values()) == {
        "COMPLETE_HASH_CAPTURED_PHYSICAL_ADMISSION_NOT_EVALUATED",
        "NOT_EVALUATED",
    }


def test_real_replay_receipt_binds_frozen_execution() -> None:
    value = json.loads(RECEIPT.read_text(encoding="ascii"))
    source_bytes = (ROOT / "gnss_drao_doy232_receipt_replay.py").read_bytes()
    executed_windows_bytes = source_bytes.replace(b"\r\n", b"\n").replace(
        b"\n", b"\r\n"
    )

    assert value["authority"]["authority_sha256"] == replay.file_sha256(AUTHORITY)
    assert value["authority"]["executed_source_commit"] == (
        "4a0777267cf57f84ac8dc7f2e3b33f9f02b8c785"
    )
    # The execution receipt intentionally hashes the actual Windows worktree
    # bytes. GitHub's Linux checkout uses LF for the same source commit, so the
    # regression reconstructs the recorded CRLF byte stream explicitly.
    assert value["authority"]["materializer_code_sha256"] == replay.sha256(
        executed_windows_bytes
    ).hexdigest()
    assert replay.file_sha256(RECEIPT) == (
        "10e6c002333080087c5d87787d74a7882175ae72f875f55162ee53653d3341b0"
    )
