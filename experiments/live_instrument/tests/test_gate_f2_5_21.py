"""Offline post-commit seal tests for Gate F2.5.21."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_21 as f2521


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _RejectSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.closed = False
        self.consumed = False

    def connect(self, *args: object, **kwargs: object) -> "_RejectSocket":
        del args, kwargs
        return self

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, control_frame: bool = False) -> tuple[int, _Frame]:
        assert control_frame
        if self.consumed:
            raise ConnectionError("synthetic stream exhausted")
        self.consumed = True
        return websocket.ABNF.OPCODE_BINARY, _Frame(b"MSG badp=5")

    def close(self) -> None:
        self.closed = True


class _RejectProvider:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.sockets: list[_RejectSocket] = []

    def __call__(self, endpoint: object, role: str):  # type: ignore[no-untyped-def]
        del endpoint
        self.calls.append(role)
        socket = _RejectSocket()
        self.sockets.append(socket)
        return socket.connect


def test_authority_envelope_binds_exact_vertical_scope_and_hashes() -> None:
    envelope = f2521.build_authority_envelope()

    assert envelope.reviewed_f2520_commit == f2521.REVIEWED_F2520_COMMIT
    assert envelope.reviewed_control_surface_hash == (
        f2521.REVIEWED_CONTROL_SURFACE_HASH
    )
    assert envelope.reviewed_live_surface_hash == f2521.REVIEWED_LIVE_SURFACE_HASH
    assert envelope.receipt_hash == f2521.AUTHORITY_ENVELOPE_HASH
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.selected_endpoint_identity == "dl1bajkiwisdr.ddns.net:8074"
    assert envelope.experiment_scope == (
        "REQUALIFY_DISCOVER_WITNESS_RETUNE_FREEZE_ONE_A1_B_A2"
    )
    assert envelope.retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.stop_condition == "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW"
    assert envelope.raw_rf_persistence == "ZERO"


def test_causal_environment_live_surface_and_parent_seals_match() -> None:
    assessment = f2521.assess_gate_f2_5_21()

    assert assessment.exit is (
        f2521.F2521Exit.EXACT_PROSPECTIVE_INTERVENTION_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.f2520_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.causal_git_diff_clean
    assert assessment.causal_source_hashes_match
    assert assessment.live_surface_hash_matches
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.parent_outcome_hash_matches
    assert assessment.caller_overrides_removed
    assert not assessment.live_execution_authorised
    assert assessment.blockers == ()
    assert f2521.current_causal_source_sha256() == (
        f2521.EXPECTED_CAUSAL_SOURCE_SHA256
    )
    assert f2521.current_environment() == f2521.EXPECTED_ENVIRONMENT
    assert f2521.current_live_surface_hash() == f2521.REVIEWED_LIVE_SURFACE_HASH


def test_public_surface_refuses_before_receipt_or_connector_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_dir = f2521.default_receipt_path(f2521.REVIEWED_AT).parent
    before = tuple(path.name for path in receipt_dir.glob("gate-f2-5-21-*.jsonl"))

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("connector accessed before explicit authority")

    monkeypatch.setattr(f2521.websocket, "create_connection", forbidden)
    with pytest.raises(PermissionError, match="separate exact live"):
        f2521.run_reviewed_once()
    after = tuple(path.name for path in receipt_dir.glob("gate-f2-5-21-*.jsonl"))
    assert before == after


def test_synthetic_sealed_execution_contacts_only_the_selected_pair(
    tmp_path: Path,
) -> None:
    provider = _RejectProvider()
    receipt_path = tmp_path / "gate-f2-5-21-synthetic.jsonl"
    result = f2521._execute_reviewed(
        f2521.build_authority_envelope(),
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=receipt_path,
        mirror_sink=None,
    )

    assert provider.calls.count("reference") == 1
    assert provider.calls.count("perturbed") == 1
    assert len(provider.calls) == 2
    assert all(socket.closed for socket in provider.sockets)
    assert result.physical_result.outcome is f25.F25Outcome.QUALIFICATION_INCOMPLETE
    assert result.receipt_artifact.state.value == "COMPLETE"
    documents = tuple(json.loads(line) for line in receipt_path.read_text().splitlines())
    assert documents[0]["event"] == "gate_f2_5_21_authority_envelope_frozen"
    assert documents[0]["payload"]["authority_envelope_hash"] == (
        f2521.AUTHORITY_ENVELOPE_HASH
    )
    assert documents[1]["event"] == "gate_f2_5_20_prospective_envelope"
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert documents[-1]["payload"]["raw_rf_persistence"] == "ZERO"
    assert documents[-1]["payload"]["physical_decision_affected"] is False


def test_public_signature_exposes_only_the_authority_bit() -> None:
    signature = inspect.signature(f2521.run_reviewed_once)
    parameters = tuple(signature.parameters.values())

    assert len(parameters) == 1
    assert parameters[0].name == "live_authorised"
    assert parameters[0].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[0].default is False


def test_seal_is_offline_and_does_not_consume_authority() -> None:
    assessment = f2521.assess_gate_f2_5_21()

    assert not assessment.live_execution_authorised
    assert assessment.envelope.authority_surface == (
        "run_reviewed_once(live_authorised=False)"
    )
    assert assessment.envelope.receipt_path_policy == (
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE"
    )
    assert assessment.envelope.receipt_first_event == (
        "gate_f2_5_21_authority_envelope_frozen"
    )
