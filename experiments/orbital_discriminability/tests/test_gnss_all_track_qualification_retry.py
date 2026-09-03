from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_all_track_qualification_retry as retry,
)
from experiments.orbital_discriminability import (
    gnss_all_track_structural_qualification as qualification,
)
from experiments.orbital_discriminability.tests.test_gnss_all_track_structural_qualification import (
    fixture,
)


ROOT = Path(retry.__file__).resolve().parent


def test_retry_manifest_changes_no_scientific_parameter() -> None:
    value = retry.manifest()
    original = qualification.manifest()

    assert value["new_gate_created"] is False
    assert value["repair"]["scientific_parameter_changes"] == 0
    assert value["original_contract"]["window_gps"] == original["window_gps"]
    assert value["original_contract"]["complete_track_count_required"] == 6
    assert value["original_contract"]["core_phase"] == ["L1C", "L2W"]
    assert value["original_contract"]["same_path_code_descriptive"] == [
        "C1C",
        "C2W",
    ]
    assert value["original_contract"]["track_identity"] == (
        "OPAQUE_FIRST_SEEN_ORDER_WITHIN_FROZEN_WINDOW"
    )
    assert value["historical_outcome"]["immutable"] is True


def test_retry_outputs_are_distinct_and_old_outcome_stays_authoritative() -> None:
    value = retry.manifest()
    outputs = {
        name for name in value["outputs"].values() if isinstance(name, str)
    }

    assert qualification.OUTCOME_NAME not in outputs
    assert len(outputs) == 4
    assert retry._historical_outcome(ROOT)["outcome"] == (
        "QUALIFICATION_DESCRIPTION_ERROR"
    )
    assert qualification.canonical_file_sha256(
        ROOT / qualification.OUTCOME_NAME
    ) == retry.HISTORICAL_OUTCOME_CANONICAL_SHA256


def test_retry_artifact_identity_is_exact_not_descriptive() -> None:
    artifact = retry.manifest()["artifact"]

    assert artifact == {
        "station": "ALGO00CAN",
        "name": "ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz",
        "url": (
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/229/"
            "ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz"
        ),
        "complete_file_bytes": 4_317_738,
        "complete_file_sha256": (
            "88aa876b787cac583345d512b2f705ec19062a5f71c38c3a4ae0da45f8095f24"
        ),
        "identity_required_before_decompression": True,
    }


def test_materialize_exact_erases_and_refuses_wrong_hash(monkeypatch) -> None:
    payload = bytearray(b"wrong complete artifact")
    receipt = {
        "complete_file_bytes": qualification.EXPECTED_COMPRESSED_BYTES,
        "complete_file_sha256": sha256(payload).hexdigest(),
    }

    monkeypatch.setattr(
        qualification, "materialize", lambda _locator: (payload, receipt)
    )

    with pytest.raises(
        qualification.MaterializationError, match="COMPLETE_FILE_SHA256_CHANGED"
    ):
        retry.materialize_exact()
    assert payload == bytearray(len(payload))


def test_retry_policy_is_bounded_before_hash_only() -> None:
    policy = retry.manifest()["retry_policy"]

    assert policy == {
        "parser_repair_executions": 1,
        "maximum_transport_attempts_before_complete_hash": 2,
        "retryable_before_complete_hash": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
        "retry_after_complete_hash": False,
        "alternate_product_url_station_date_or_window": False,
    }


def test_authority_binds_predecessor_repair_contract_plan_and_executor() -> None:
    seal = retry.verify_retry_authority()
    current = retry.manifest()

    assert seal["repair_commit"] == retry.REPAIR_COMMIT
    assert seal["historical_outcome"] == current["historical_outcome"]
    assert seal["original_contract"] == current["original_contract"]
    assert seal["retry_plan"] == current["retry_plan"]
    assert seal["artifact"] == current["artifact"]
    assert seal["outputs"] == current["outputs"]
    assert seal["retry_manifest_sha256"] == retry.manifest_sha256()
    assert seal["retry_executor_canonical_sha256"] == retry.retry_source_sha256()


def test_retry_runner_preserves_old_outcome_and_writes_only_new_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original_bytes = (ROOT / qualification.OUTCOME_NAME).read_bytes()
    decoded = fixture()
    fake_artifact = {
        "station": qualification.STATION,
        "product": qualification.PRODUCT_NAME,
        "url": qualification.PRODUCT_URL,
        "attempts": 1,
        "complete_file_bytes": qualification.EXPECTED_COMPRESSED_BYTES,
        "complete_file_sha256": retry.ARTIFACT_SHA256,
        "hash_completed_before_decompression": True,
        "matches_frozen_complete_identity": True,
    }

    monkeypatch.setattr(
        retry,
        "materialize_exact",
        lambda: (bytearray(b"compressed-placeholder"), fake_artifact.copy()),
    )
    monkeypatch.setattr(
        qualification, "_decompress", lambda _payload: bytearray(decoded)
    )

    outcome = retry.run_retry_once(tmp_path)

    assert outcome["outcome"] == "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_PASSED"
    assert (ROOT / qualification.OUTCOME_NAME).read_bytes() == original_bytes
    assert set(path.name for path in tmp_path.iterdir()) == set(retry.OUTPUT_NAMES)
    assert not (tmp_path / qualification.OUTCOME_NAME).exists()
    persisted = json.loads((tmp_path / retry.RETRY_OUTCOME_NAME).read_text())
    assert persisted["clause_states"]["measurement_admission"] == "NOT_EVALUATED"
    assert persisted["clause_states"]["orbital_score"] == "NOT_EVALUATED"
    assert persisted["clause_states"]["primary_selection"] == "NOT_EVALUATED"
    assert persisted["persistence"]["observation_values"] == 0

    with pytest.raises(retry.RetryAuthorityError, match="RETRY_OUTPUT_ALREADY_EXISTS"):
        retry.run_retry_once(tmp_path)


def test_description_failure_cannot_modify_physical_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        retry,
        "materialize_exact",
        lambda: (_ for _ in ()).throw(
            qualification.MaterializationError("FROZEN_ARTIFACT_UNAVAILABLE")
        ),
    )

    outcome = retry.run_retry_once(tmp_path)

    assert outcome["outcome"] == "QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED"
    assert outcome["structure"] == "NOT_EVALUATED"
    assert outcome["measurement_admission"] == "NOT_EVALUATED"
    assert outcome["orbital_score"] == "NOT_EVALUATED"
    assert outcome["primary_selection"] == "NOT_EVALUATED"
    assert outcome["observation_values_persisted"] == 0


def test_old_executor_remains_closed() -> None:
    with pytest.raises(
        qualification.DescriptionError,
        match="QUALIFICATION_EXECUTION_ALREADY_RECORDED",
    ):
        qualification.run_once(ROOT)
