from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_runner as runner,
)


ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / runner.RUNNER_SEAL_NAME
SEAL_SHA256 = "7d2b5db0cae2a4f4a500b95fcbf8107baf315d76a962ef62038429c4c057a4bf"


class Response:
    def __init__(self, payload: bytes):
        self.status = 200
        self.headers = {
            "Content-Length": str(len(payload)),
            "ETag": runner.ARTIFACT_ETAG,
            "Last-Modified": runner.ARTIFACT_LAST_MODIFIED,
            "Content-Type": runner.ARTIFACT_CONTENT_TYPE,
        }
        self._stream = BytesIO(payload)

    def geturl(self) -> str:
        return runner.ARTIFACT_URL

    def read(self, count: int) -> bytes:
        return self._stream.read(count)

    def __enter__(self) -> "Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_manifest_binds_one_artifact_and_grants_no_access() -> None:
    value = runner.runner_manifest(ROOT)

    assert value["state"] == "DRAO_DOY238_RUNNER_FROZEN_UNEXECUTED"
    assert value["selection"]["canonical_sha256"] == runner.SELECTION_SHA256
    assert value["selection"]["artifact"]["name"] == runner.ARTIFACT_NAME
    assert value["live_authority_granted_by_manifest"] is False
    assert not any(value["access_at_freeze"].values())
    assert value["transport"]["retry_after_complete_hash"] == 0
    assert value["transport"]["fallback"] is False


def test_post_commit_seal_binds_runner_selection_and_zero_access() -> None:
    value = runner.validate_seal(ROOT, SEAL, SEAL_SHA256)

    assert value["runner_source_commit"] == "8daa5727c0e0defbb0ef0fdccbe4f972fcbb1fa1"
    assert value["runner_source_canonical_sha256"] == runner.source_sha256()
    assert value["runner_manifest_sha256"] == runner.manifest_sha256(ROOT)
    assert value["selection_canonical_sha256"] == runner.SELECTION_SHA256
    assert value["live_authority_granted"] is False
    assert not any(value["access_at_seal"].values())


def test_no_authority_means_no_network_or_receipt(tmp_path: Path, monkeypatch) -> None:
    called = False

    def forbidden(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("network used")

    monkeypatch.setattr(runner, "materialize", forbidden)
    with pytest.raises(PermissionError, match="ONE_USE_AUTHORITY_REQUIRED"):
        runner.run_once(tmp_path, "", tmp_path / "seal.json", "0" * 64)
    assert called is False
    assert list(tmp_path.iterdir()) == []


def test_exact_payload_is_hashed_without_persistence(monkeypatch) -> None:
    payload = b"x" * runner.ARTIFACT_BYTES
    monkeypatch.setattr(runner, "urlopen", lambda *args, **kwargs: Response(payload))

    materialized, receipt = runner.materialize()
    try:
        assert receipt["complete_file_bytes"] == runner.ARTIFACT_BYTES
        assert receipt["complete_file_sha256"] == sha256(payload).hexdigest()
        assert receipt["hash_persisted_before_decompression"] is False
        assert receipt["body_persisted"] is False
    finally:
        materialized[:] = b"\x00" * len(materialized)


def test_hash_receipt_precedes_decode_score_and_buffer_erasure(
    tmp_path: Path, monkeypatch
) -> None:
    compressed = bytearray(b"compressed")
    decoded = bytearray(b"decoded")
    coordinate = np.ones((139, 6), dtype=np.float64)
    seen: dict[str, object] = {}

    monkeypatch.setattr(
        runner,
        "validate_seal",
        lambda *args: {"runner_source_commit": "source"},
    )
    monkeypatch.setattr(
        runner,
        "materialize",
        lambda: (
            compressed,
            {
                "complete_file_bytes": len(compressed),
                "complete_file_sha256": sha256(compressed).hexdigest(),
                "hash_persisted_before_decompression": False,
            },
        ),
    )

    def decode(payload: bytearray) -> bytearray:
        seen["receipt_before_decode"] = (
            tmp_path / runner.MATERIALIZATION_NAME
        ).exists()
        return decoded

    class Scan:
        header = {"transforms": "typed"}

        def erase(self) -> None:
            seen["scan_erased"] = True

    monkeypatch.setattr(runner, "decompress_in_memory", decode)
    monkeypatch.setattr(
        runner.experiment,
        "scan_decoded_fixture",
        lambda *args, **kwargs: Scan(),
    )
    monkeypatch.setattr(
        runner.experiment,
        "admit_model_blind",
        lambda scan: ({"state": "ADMITTED"}, coordinate),
    )
    monkeypatch.setattr(
        runner.experiment,
        "score_admitted_coordinate",
        lambda values, root: {"outcome": "AMBIGUOUS"},
    )

    result = runner.run_once(
        tmp_path,
        runner.AUTHORITY_TOKEN,
        tmp_path / "seal.json",
        "a" * 64,
    )

    assert seen["receipt_before_decode"] is True
    assert result["outcome"] == "AMBIGUOUS"
    assert seen["scan_erased"] is True
    assert set(compressed) == {0}
    assert set(decoded) == {0}
    assert np.count_nonzero(coordinate) == 0
    assert not (tmp_path / runner.ARTIFACT_NAME).exists()


def test_description_failure_is_not_measurement_invalid(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        runner,
        "validate_seal",
        lambda *args: {"runner_source_commit": "source"},
    )
    monkeypatch.setattr(
        runner,
        "materialize",
        lambda: (_ for _ in ()).throw(
            runner.RunnerDescriptionError("SOFTWARE_DESCRIPTION_FAILED")
        ),
    )

    result = runner.run_once(
        tmp_path,
        runner.AUTHORITY_TOKEN,
        tmp_path / "seal.json",
        "b" * 64,
    )

    assert result["outcome"] == "PRIMARY_NOT_EVALUATED"
    assert result["reason_class"] == "DESCRIPTION_ERROR"
    assert result["physical_decision"] == "NOT_EVALUATED"


def test_measurement_failure_cannot_produce_orbital_score(
    tmp_path: Path, monkeypatch
) -> None:
    compressed = bytearray(b"compressed")
    decoded = bytearray(b"decoded")
    monkeypatch.setattr(
        runner,
        "validate_seal",
        lambda *args: {"runner_source_commit": "source"},
    )
    monkeypatch.setattr(
        runner,
        "materialize",
        lambda: (
            compressed,
            {
                "complete_file_bytes": len(compressed),
                "complete_file_sha256": sha256(compressed).hexdigest(),
                "hash_persisted_before_decompression": False,
            },
        ),
    )
    monkeypatch.setattr(runner, "decompress_in_memory", lambda payload: decoded)
    monkeypatch.setattr(
        runner.experiment,
        "scan_decoded_fixture",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            runner.experiment.ForwardMeasurementInvalid("REQUIRED_PRN_MISSING")
        ),
    )

    result = runner.run_once(
        tmp_path,
        runner.AUTHORITY_TOKEN,
        tmp_path / "seal.json",
        "c" * 64,
    )

    assert result["outcome"] == "MEASUREMENT_INVALID"
    assert result["orbital_score"] == "NOT_EVALUATED"
    assert result["observation_values_persisted"] == 0


def test_materialization_failure_is_distinct_and_terminal(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        runner,
        "validate_seal",
        lambda *args: {"runner_source_commit": "source"},
    )
    monkeypatch.setattr(
        runner,
        "materialize",
        lambda: (_ for _ in ()).throw(
            runner.ArtifactMaterializationFailed(
                {"state": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED"}
            )
        ),
    )

    result = runner.run_once(
        tmp_path,
        runner.AUTHORITY_TOKEN,
        tmp_path / "seal.json",
        "d" * 64,
    )

    assert result["outcome"] == "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED"
    assert result["physical_decision"] == "NOT_EVALUATED"


def test_consumed_authority_blocks_second_attempt(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / runner.AUTHORITY_NAME).write_text("{}", encoding="ascii")
    monkeypatch.setattr(
        runner,
        "validate_seal",
        lambda *args: {"runner_source_commit": "source"},
    )

    with pytest.raises(PermissionError, match="AUTHORITY_ALREADY_CONSUMED"):
        runner.run_once(
            tmp_path,
            runner.AUTHORITY_TOKEN,
            tmp_path / "seal.json",
            "e" * 64,
        )


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        runner.strict_json({"bad": float("inf")})
