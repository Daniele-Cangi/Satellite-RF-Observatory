from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_drao_labelled_forward_doy234_runner as runner


ROOT = Path(__file__).resolve().parents[1]
SEAL = ROOT / runner.RUNNER_SEAL_NAME
SEAL_SHA256 = "cd083939e6d5e3f855521747f0d71f2661d0931a72cfab60fa55523dd2b467ca"


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


def test_manifest_binds_one_product_and_grants_no_access() -> None:
    value = runner.runner_manifest(ROOT)
    assert value["state"] == "DRAO_DOY234_RUNNER_FROZEN_UNEXECUTED"
    assert value["selection"]["artifact"]["name"] == runner.ARTIFACT_NAME
    assert value["live_authority_granted_by_manifest"] is False
    assert value["transport"]["retry_after_complete_hash"] == 0
    assert value["transport"]["fallback"] is False
    assert not any(value["access_at_freeze"].values())


def test_post_commit_seal_binds_runner_selection_and_zero_access() -> None:
    value = runner.validate_seal(ROOT, SEAL, SEAL_SHA256)
    assert value["runner_source_commit"] == "a26f2e7f2442f713e5a4c6e57789f1937388b7fa"
    assert value["runner_source_canonical_sha256"] == runner.source_sha256()
    assert value["runner_manifest_sha256"] == runner.manifest_sha256(ROOT)
    assert value["selection_canonical_sha256"] == runner.SELECTION_SHA256
    assert value["live_authority_granted"] is False
    assert not any(value["access_at_seal"].values())


def test_no_authority_means_no_network_or_receipt(tmp_path: Path, monkeypatch) -> None:
    called = False

    def forbidden() -> None:
        nonlocal called
        called = True

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


def test_hash_receipt_precedes_score_and_all_buffers_are_erased(tmp_path: Path, monkeypatch) -> None:
    compressed = bytearray(b"compressed")
    decoded = bytearray(b"decoded")
    coordinate = np.ones((139, 6), dtype=np.float64)
    seen: dict[str, object] = {}
    monkeypatch.setattr(runner, "validate_seal", lambda *args: {"runner_source_commit": "source"})
    monkeypatch.setattr(
        runner,
        "materialize",
        lambda: (compressed, {"complete_file_bytes": len(compressed), "complete_file_sha256": sha256(compressed).hexdigest(), "hash_persisted_before_decompression": False}),
    )

    def decode(payload: bytearray) -> bytearray:
        seen["receipt_before_decode"] = (tmp_path / runner.MATERIALIZATION_NAME).exists()
        return decoded

    class Scan:
        header = {"transforms": "typed"}

        def erase(self) -> None:
            seen["scan_erased"] = True

    monkeypatch.setattr(runner, "decompress_in_memory", decode)
    monkeypatch.setattr(runner.experiment, "scan_decoded", lambda *args, **kwargs: Scan())
    monkeypatch.setattr(runner.experiment, "admit_model_blind", lambda scan: ({"state": "ADMITTED"}, coordinate))
    monkeypatch.setattr(runner.experiment, "score", lambda values, root: {"outcome": "AMBIGUOUS"})
    result = runner.run_once(tmp_path, runner.AUTHORITY_TOKEN, tmp_path / "seal.json", "a" * 64)
    assert seen["receipt_before_decode"] is True
    assert result["outcome"] == "AMBIGUOUS"
    assert seen["scan_erased"] is True
    assert not any(compressed) and not any(decoded)
    assert np.count_nonzero(coordinate) == 0
    assert not (tmp_path / runner.ARTIFACT_NAME).exists()


def test_description_and_measurement_failures_remain_separate(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "validate_seal", lambda *args: {"runner_source_commit": "source"})
    monkeypatch.setattr(runner, "materialize", lambda: (_ for _ in ()).throw(runner.RunnerDescriptionError("SOFTWARE_DESCRIPTION_FAILED")))
    described = runner.run_once(tmp_path / "description", runner.AUTHORITY_TOKEN, tmp_path / "seal.json", "b" * 64)
    assert described["outcome"] == "PRIMARY_NOT_EVALUATED"
    assert described["reason_class"] == "DESCRIPTION_ERROR"

    compressed = bytearray(b"compressed")
    decoded = bytearray(b"decoded")
    monkeypatch.setattr(runner, "materialize", lambda: (compressed, {"complete_file_bytes": len(compressed), "complete_file_sha256": sha256(compressed).hexdigest(), "hash_persisted_before_decompression": False}))
    monkeypatch.setattr(runner, "decompress_in_memory", lambda payload: decoded)
    monkeypatch.setattr(runner.experiment, "scan_decoded", lambda *args, **kwargs: (_ for _ in ()).throw(runner.experiment.Doy234MeasurementInvalid("REQUIRED_PRN_MISSING")))
    invalid = runner.run_once(tmp_path / "measurement", runner.AUTHORITY_TOKEN, tmp_path / "seal.json", "c" * 64)
    assert invalid["outcome"] == "MEASUREMENT_INVALID"
    assert invalid["orbital_score"] == "NOT_EVALUATED"


def test_materialization_failure_is_distinct_and_authority_is_single_use(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(runner, "validate_seal", lambda *args: {"runner_source_commit": "source"})
    monkeypatch.setattr(runner, "materialize", lambda: (_ for _ in ()).throw(runner.ArtifactMaterializationFailed({"state": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED"})))
    result = runner.run_once(tmp_path, runner.AUTHORITY_TOKEN, tmp_path / "seal.json", "d" * 64)
    assert result["outcome"] == "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED"
    with pytest.raises(PermissionError, match="AUTHORITY_ALREADY_CONSUMED"):
        runner.run_once(tmp_path, runner.AUTHORITY_TOKEN, tmp_path / "seal.json", "d" * 64)


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        runner.strict_json({"bad": float("inf")})


def test_frozen_real_outcome_preserves_terminal_claim_and_zero_persistence() -> None:
    outcome_path = ROOT / runner.OUTCOME_NAME
    materialization_path = ROOT / runner.MATERIALIZATION_NAME
    outcome = runner._read_json(outcome_path)
    materialization = runner._read_json(materialization_path)

    assert runner.canonical_sha256(outcome_path) == "f499981c19540013f99695de2a39b996cb415075ff97ee6564cf15d6c6aef3d0"
    assert runner.canonical_sha256(materialization_path) == "d4b1d69458a332f385a0237c886e8f01d0f952eddeed5b4f4483d80b3621040e"
    assert outcome["outcome"] == "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    assert outcome["admission_receipt"]["structural_counts"] == {"PRESENT": 3336}
    assert outcome["score_receipt"]["best_family"] == "ORBITAL"
    assert outcome["score_receipt"]["heldout_refit"] is False
    assert outcome["score_receipt"]["free_time_phase"] is False
    assert outcome["score_receipt"]["preference_margin_m"] == pytest.approx(36207.12658968102)
    assert outcome["persistence"] == {
        "compressed_artifact": 0,
        "decoded_rinex": 0,
        "derived_series": 0,
        "observation_values": 0,
    }
    assert materialization["complete_file_bytes"] == 2850623
    assert materialization["complete_file_sha256"] == "5eb4c7f8b2fa3a0b2f3b4fe40de1f69a85a9150bd5eafd61667fc84bcf9e5335"
    assert materialization["hash_persisted_before_decompression"] is True
    assert not (ROOT / runner.ARTIFACT_NAME).exists()
