"""Offline post-commit authority-seal tests for Gate F2.5.38."""

from __future__ import annotations

from dataclasses import asdict, replace
import inspect
import json
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_33 as f2533
from experiments.live_instrument import kiwi_gate_f2_5_37 as f2537
from experiments.live_instrument import kiwi_gate_f2_5_38 as f2538
from experiments.live_instrument.tests.test_gate_f2_5_37 import (
    _LeadingZeroPhaseSocket,
)


class _CorrectedProvider:
    def __init__(self) -> None:
        self.roles: list[str] = []
        self.sockets: list[_LeadingZeroPhaseSocket] = []

    def __call__(self, role: str) -> _LeadingZeroPhaseSocket:
        self.roles.append(role)
        socket = _LeadingZeroPhaseSocket(
            0 if role == "reference" else 1,
            role=role,
            hypothesis="upstream",
            arrival_offset_ns=0 if role == "reference" else 1_000_000,
        )
        self.sockets.append(socket)
        return socket


def test_envelope_binds_only_the_corrected_vertical_and_zero_retry() -> None:
    envelope = f2538.build_authority_envelope()

    assert envelope.reviewed_f2537_commit == f2538.REVIEWED_F2537_COMMIT
    assert envelope.reviewed_f2537_source_sha256 == (
        f2538.REVIEWED_F2537_SOURCE_SHA256
    )
    assert envelope.reviewed_f2537_plan_hash == f2538.REVIEWED_F2537_PLAN_HASH
    assert envelope.reviewed_continuity_surface_hash == (
        f2538.REVIEWED_CONTINUITY_SURFACE_HASH
    )
    assert envelope.reviewed_scope_surface_hash == (
        f2538.REVIEWED_SCOPE_SURFACE_HASH
    )
    assert envelope.reviewed_integration_surface_hash == (
        f2538.REVIEWED_INTEGRATION_SURFACE_HASH
    )
    assert envelope.reviewed_live_surface_hash == f2538.EXPECTED_LIVE_SURFACE_HASH
    assert envelope.receipt_hash == f2538.AUTHORITY_ENVELOPE_HASH
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.continuity_policy == (
        "ONE_F2527_RULE_FOR_INITIAL_AND_FULL_SESSION"
    )
    assert envelope.prefreeze_retry_budget == envelope.postfreeze_retry_budget == 0
    assert envelope.outcome_windows == 1
    assert envelope.stop_condition == "FIRST_TERMINAL_OUTCOME"
    assert envelope.receipt_content == "DECISION_PLUS_SCALAR_AUDIT_HASHES_ONLY"
    assert envelope.waterfall_role == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.ext_api_role == "DESCRIPTIVE_HINT_UNUSED"
    assert envelope.live_execution_authorised is False
    assert envelope.raw_rf_persistence == "ZERO"


def test_commit_source_plan_environment_and_all_surfaces_match() -> None:
    assessment = f2538.assess()

    assert assessment.exit is (
        f2538.F2538Exit.CORRECTED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.f2537_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.reviewed_source_git_diff_clean
    assert assessment.reviewed_source_hash_matches
    assert assessment.reviewed_plan_hash_matches
    assert assessment.continuity_surface_matches
    assert assessment.scope_surface_matches
    assert assessment.integration_surface_matches
    assert assessment.connector_source_matches
    assert assessment.live_surface_hash_matches
    assert assessment.authority_envelope_hash_matches
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.caller_overrides_removed
    assert assessment.live_execution_authorised is False
    assert assessment.blockers == ()
    assert assessment.raw_rf_persistence == "ZERO"


def test_default_refusal_precedes_assessment_receipt_and_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_dir = f2538.default_receipt_path(f2538.REVIEWED_AT).parent
    before = tuple(receipt_dir.glob("gate-f2-5-38-*.jsonl"))

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("work occurred before explicit authority")

    monkeypatch.setattr(f2538, "assess", forbidden)
    monkeypatch.setattr(f2533, "_open_live_socket", forbidden)
    with pytest.raises(PermissionError, match="separate exact live"):
        f2538.run_reviewed_once()
    after = tuple(receipt_dir.glob("gate-f2-5-38-*.jsonl"))
    assert before == after


def test_seal_mismatch_blocks_before_receipt_or_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = f2538.assess()
    blocked = replace(
        baseline,
        exit=f2538.F2538Exit.POST_COMMIT_SEAL_MISMATCH,
        blockers=("synthetic seal mismatch",),
    )
    receipt_dir = f2538.default_receipt_path(f2538.REVIEWED_AT).parent
    before = tuple(receipt_dir.glob("gate-f2-5-38-*.jsonl"))
    connector_calls = 0

    def forbidden(*args: object, **kwargs: object) -> object:
        nonlocal connector_calls
        del args, kwargs
        connector_calls += 1
        raise AssertionError("connector entered after seal mismatch")

    monkeypatch.setattr(f2538, "assess", lambda: blocked)
    monkeypatch.setattr(f2533, "_open_live_socket", forbidden)
    with pytest.raises(RuntimeError, match="synthetic seal mismatch"):
        f2538.run_reviewed_once(live_authorised=True)
    after = tuple(receipt_dir.glob("gate-f2-5-38-*.jsonl"))
    assert connector_calls == 0
    assert before == after


def test_internal_seam_emits_one_corrected_outcome_and_terminal_manifest(
    tmp_path: Path,
) -> None:
    provider = _CorrectedProvider()
    path = tmp_path / "corrected-positive.jsonl"
    original_continuity = f2537.f2531._continuity
    result = f2538._execute_with_dependencies(
        f2538.build_authority_envelope(),
        connector_provider=provider,
        receipt_path=path,
        mirror_sink=None,
    )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())
    physical = result.corrected_result.physical_result

    assert result.authority_consumed
    assert result.authority_envelope_hash == f2538.AUTHORITY_ENVELOPE_HASH
    assert physical.outcome == "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    assert physical.physical_hypothesis_state == physical.outcome
    assert physical.discovery is not None
    assert physical.discovery.state == "ONE_FEATURE_ADMITTED"
    assert all(item.state == "SATISFIED" for item in physical.session_continuity)
    assert all(
        item.timestamp_step_violation_count == 0
        for item in physical.session_continuity
    )
    assert result.corrected_result.discovery_audit is not None
    assert physical.cleanup.all_iq_zeroized
    assert f2537.f2531._continuity is original_continuity
    assert sorted(provider.roles) == ["perturbed", "reference"]
    assert all(socket.closed for socket in provider.sockets)
    assert documents[0]["event"] == "gate_f2_5_38_authority_envelope_frozen"
    assert documents[0]["payload"]["authority_envelope_hash"] == (
        f2538.AUTHORITY_ENVELOPE_HASH
    )
    assert [item["event"] for item in documents].count(
        "gate_f2_5_38_one_outcome"
    ) == 1
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert result.receipt_artifact.state.value == "COMPLETE"
    assert result.raw_rf_persistence == "ZERO"


def test_corrected_outcome_is_strict_scalar_json_without_rf_payload(
    tmp_path: Path,
) -> None:
    path = tmp_path / "strict-corrected.jsonl"
    f2538._execute_with_dependencies(
        f2538.build_authority_envelope(),
        connector_provider=_CorrectedProvider(),
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
    reference = _LeadingZeroPhaseSocket(0, role="reference")

    def provider(role: str) -> object:
        if role == "reference":
            return reference
        raise ConnectionError("synthetic peer connection failure")

    path = tmp_path / "partial-connect.jsonl"
    with pytest.raises(ConnectionError, match="synthetic peer"):
        f2538._execute_with_dependencies(
            f2538.build_authority_envelope(),
            connector_provider=provider,
            receipt_path=path,
            mirror_sink=None,
        )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())
    assert reference.closed
    assert documents[0]["event"] == "gate_f2_5_38_authority_envelope_frozen"
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"


@pytest.mark.parametrize(
    ("attribute", "replacement", "field"),
    (
        ("current_f2537_source_sha256", lambda: "0" * 64, "reviewed_source_hash_matches"),
        ("current_continuity_surface_hash", lambda: "0" * 64, "continuity_surface_matches"),
        ("current_scope_surface_hash", lambda: "0" * 64, "scope_surface_matches"),
        ("current_integration_surface_hash", lambda: "0" * 64, "integration_surface_matches"),
        ("current_environment", lambda: (("python", "0"),), "numerical_environment_matches"),
        ("current_live_surface_hash", lambda: "0" * 64, "live_surface_hash_matches"),
    ),
)
def test_source_environment_and_surface_tamper_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    attribute: str,
    replacement: object,
    field: str,
) -> None:
    monkeypatch.setattr(f2538, attribute, replacement)
    assessment = f2538.assess()

    assert assessment.exit is f2538.F2538Exit.POST_COMMIT_SEAL_MISMATCH
    assert getattr(assessment, field) is False


def test_live_signature_connector_and_hashes_are_exactly_sealed() -> None:
    signature = inspect.signature(f2538.run_reviewed_once)

    assert tuple(signature.parameters) == ("live_authorised",)
    parameter = signature.parameters["live_authorised"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is False
    assert f2538.current_f2533_connector_source_sha256() == (
        f2538.REVIEWED_F2533_CONNECTOR_SOURCE_SHA256
    )
    assert f2538.current_live_surface_hash() == f2538.EXPECTED_LIVE_SURFACE_HASH
    assert f2538.build_authority_envelope().receipt_hash == (
        f2538.AUTHORITY_ENVELOPE_HASH
    )
    assert f2538.strict_json(asdict(f2538.build_authority_envelope()))
