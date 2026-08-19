"""Offline post-commit authority-seal tests for Gate F2.5.36."""

from __future__ import annotations

from dataclasses import asdict, replace
import inspect
import json
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_33 as f2533
from experiments.live_instrument import kiwi_gate_f2_5_35 as f2535
from experiments.live_instrument import kiwi_gate_f2_5_36 as f2536
from experiments.live_instrument.tests.test_gate_f2_5_35 import _NegativeSocket


class _NegativeProvider:
    def __init__(self) -> None:
        self.roles: list[str] = []
        self.sockets: list[_NegativeSocket] = []

    def __call__(self, role: str) -> _NegativeSocket:
        self.roles.append(role)
        socket = _NegativeSocket(
            0 if role == "reference" else 1,
            0 if role == "reference" else 1_000_000,
        )
        self.sockets.append(socket)
        return socket


def test_envelope_binds_exact_audited_vertical_and_zero_retry() -> None:
    envelope = f2536.build_authority_envelope()

    assert envelope.reviewed_f2535_commit == f2536.REVIEWED_F2535_COMMIT
    assert envelope.reviewed_f2535_source_sha256 == (
        f2536.REVIEWED_F2535_SOURCE_SHA256
    )
    assert envelope.reviewed_f2532_plan_hash == f2536.REVIEWED_F2532_PLAN_HASH
    assert envelope.reviewed_discovery_surface_hash == (
        f2536.REVIEWED_DISCOVERY_SURFACE_HASH
    )
    assert envelope.reviewed_integration_surface_hash == (
        f2536.REVIEWED_INTEGRATION_SURFACE_HASH
    )
    assert envelope.reviewed_live_surface_hash == f2536.EXPECTED_LIVE_SURFACE_HASH
    assert envelope.receipt_hash == f2536.AUTHORITY_ENVELOPE_HASH
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.outcome_windows == 1
    assert envelope.stop_condition == "FIRST_TERMINAL_OUTCOME"
    assert envelope.audit_policy == "DECISION_FIRST_SCALAR_SIBLING_NONAUTHORITATIVE"
    assert envelope.receipt_content == "DECISION_PLUS_SCALAR_AUDIT_HASHES_ONLY"
    assert envelope.waterfall_role == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.ext_api_role == "DESCRIPTIVE_HINT_UNUSED"
    assert envelope.raw_rf_persistence == "ZERO"


def test_commit_source_plan_environment_and_surfaces_match() -> None:
    assessment = f2536.assess()

    assert assessment.exit is (
        f2536.F2536Exit.AUDITED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.f2535_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.reviewed_source_git_diff_clean
    assert assessment.reviewed_source_hash_matches
    assert assessment.reviewed_plan_hash_matches
    assert assessment.discovery_surface_matches
    assert assessment.integration_surface_matches
    assert assessment.connector_source_matches
    assert assessment.live_surface_hash_matches
    assert assessment.authority_envelope_hash_matches
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.caller_overrides_removed
    assert assessment.live_execution_authorised is False
    assert assessment.blockers == ()
    assert f2536.current_environment() == f2536.EXPECTED_ENVIRONMENT


def test_default_refusal_precedes_assessment_receipt_and_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_dir = f2536.default_receipt_path(f2536.REVIEWED_AT).parent
    before = tuple(receipt_dir.glob("gate-f2-5-36-*.jsonl"))

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("work occurred before explicit authority")

    monkeypatch.setattr(f2536, "assess", forbidden)
    monkeypatch.setattr(f2533, "_open_live_socket", forbidden)
    with pytest.raises(PermissionError, match="separate exact live"):
        f2536.run_reviewed_once()
    after = tuple(receipt_dir.glob("gate-f2-5-36-*.jsonl"))
    assert before == after


def test_seal_mismatch_blocks_before_receipt_or_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = f2536.assess()
    blocked = replace(
        baseline,
        exit=f2536.F2536Exit.POST_COMMIT_SEAL_MISMATCH,
        blockers=("synthetic seal mismatch",),
    )
    receipt_dir = f2536.default_receipt_path(f2536.REVIEWED_AT).parent
    before = tuple(receipt_dir.glob("gate-f2-5-36-*.jsonl"))
    connector_calls = 0

    def forbidden(*args: object, **kwargs: object) -> object:
        nonlocal connector_calls
        del args, kwargs
        connector_calls += 1
        raise AssertionError("connector entered after seal mismatch")

    monkeypatch.setattr(f2536, "assess", lambda: blocked)
    monkeypatch.setattr(f2533, "_open_live_socket", forbidden)
    with pytest.raises(RuntimeError, match="synthetic seal mismatch"):
        f2536.run_reviewed_once(live_authorised=True)
    after = tuple(receipt_dir.glob("gate-f2-5-36-*.jsonl"))
    assert connector_calls == 0
    assert before == after


def test_internal_seam_emits_authority_audited_outcome_and_terminal_manifest(
    tmp_path: Path,
) -> None:
    provider = _NegativeProvider()
    path = tmp_path / "audited-negative.jsonl"
    result = f2536._execute_with_dependencies(
        f2536.build_authority_envelope(),
        connector_provider=provider,
        receipt_path=path,
        mirror_sink=None,
    )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())

    assert result.authority_consumed is True
    assert result.authority_envelope_hash == f2536.AUTHORITY_ENVELOPE_HASH
    assert result.audited_result.physical_result.outcome == (
        "NO_FALSIFIABLE_INTERVENTION"
    )
    assert result.audited_result.discovery_audit is not None
    assert result.audited_result.discovery_audit.state is f2535.AuditState.COMPLETE
    audit = result.audited_result.discovery_audit.receipt
    assert audit is not None
    assert audit.decision_state == "NO_FEATURE_ADMITTED"
    assert audit.raw_peak_count == 0
    assert audit.admitted_feature_count == 0
    assert sorted(provider.roles) == ["perturbed", "reference"]
    assert all(socket.closed for socket in provider.sockets)
    assert documents[0]["event"] == "gate_f2_5_36_authority_envelope_frozen"
    assert documents[0]["payload"]["authority_envelope_hash"] == (
        f2536.AUTHORITY_ENVELOPE_HASH
    )
    assert [item["event"] for item in documents].count(
        "gate_f2_5_36_one_outcome"
    ) == 1
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert result.receipt_artifact.state.value == "COMPLETE"
    assert result.raw_rf_persistence == "ZERO"


def test_audited_outcome_json_contains_only_scalars_hashes_and_strict_numbers(
    tmp_path: Path,
) -> None:
    path = tmp_path / "strict-audit.jsonl"
    f2536._execute_with_dependencies(
        f2536.build_authority_envelope(),
        connector_provider=_NegativeProvider(),
        receipt_path=path,
        mirror_sink=None,
    )
    text = path.read_text()
    documents = tuple(
        json.loads(
            line,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
        for line in text.splitlines()
    )
    payload = documents[1]["payload"]

    assert payload["raw_rf_persistence"] == "ZERO"
    assert payload["physical_decision_affected_by_description"] is False
    assert payload["discovery_audit"]["physical_decision_affected"] is False
    assert payload["discovery_audit"]["receipt"]["candidate_arrays_persisted"] is False
    assert "NaN" not in text and "Infinity" not in text
    forbidden = ("samples", "iq_payload", "waterfall", "stft_matrix", "spectrum")
    assert all(key not in payload for key in forbidden)


def test_partial_connector_failure_closes_peer_and_terminalizes_receipt(
    tmp_path: Path,
) -> None:
    reference = _NegativeSocket(0)

    def provider(role: str) -> object:
        if role == "reference":
            return reference
        raise ConnectionError("synthetic peer connection failure")

    path = tmp_path / "partial-connect.jsonl"
    with pytest.raises(ConnectionError, match="synthetic peer"):
        f2536._execute_with_dependencies(
            f2536.build_authority_envelope(),
            connector_provider=provider,
            receipt_path=path,
            mirror_sink=None,
        )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())
    assert reference.closed is True
    assert documents[0]["event"] == "gate_f2_5_36_authority_envelope_frozen"
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"


def test_source_environment_and_live_surface_tamper_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f2536, "current_f2535_source_sha256", lambda: "0" * 64)
    source = f2536.assess()
    assert source.exit is f2536.F2536Exit.POST_COMMIT_SEAL_MISMATCH
    assert source.reviewed_source_hash_matches is False

    monkeypatch.undo()
    monkeypatch.setattr(f2536, "current_environment", lambda: (("python", "0"),))
    environment = f2536.assess()
    assert environment.exit is f2536.F2536Exit.POST_COMMIT_SEAL_MISMATCH
    assert environment.numerical_environment_matches is False

    monkeypatch.undo()
    monkeypatch.setattr(f2536, "current_live_surface_hash", lambda: "0" * 64)
    live = f2536.assess()
    assert live.exit is f2536.F2536Exit.POST_COMMIT_SEAL_MISMATCH
    assert live.live_surface_hash_matches is False


def test_live_signature_and_reused_connector_are_exactly_sealed() -> None:
    signature = inspect.signature(f2536.run_reviewed_once)

    assert tuple(signature.parameters) == ("live_authorised",)
    parameter = signature.parameters["live_authorised"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is False
    assert f2536.current_f2533_connector_source_sha256() == (
        f2536.REVIEWED_F2533_CONNECTOR_SOURCE_SHA256
    )
    assert f2536.current_live_surface_hash() == f2536.EXPECTED_LIVE_SURFACE_HASH
    assert f2536.strict_json(asdict(f2536.build_authority_envelope()))
