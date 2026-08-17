"""Offline post-commit seal tests for Gate F2.5.19."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5_14 as f2514
from experiments.live_instrument import kiwi_gate_f2_5_19 as f2519


AUTHORITY_ENVELOPE_HASH = (
    "b89c09209e83797b06c9730e001fd85c3a04ae77719412655dd0f9c877bdd80a"
)


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
        self.calls: list[tuple[str, str]] = []
        self.sockets: list[_RejectSocket] = []

    def __call__(self, endpoint: object, role: str):  # type: ignore[no-untyped-def]
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        self.calls.append((identity, role))
        socket = _RejectSocket()
        self.sockets.append(socket)
        return socket.connect


def test_authority_envelope_binds_exact_reviewed_commit_and_scope() -> None:
    envelope = f2519.build_authority_envelope()

    assert envelope.reviewed_f2518_commit == f2519.REVIEWED_F2518_COMMIT
    assert envelope.reviewed_control_surface_hash == (
        f2519.REVIEWED_CONTROL_SURFACE_HASH
    )
    assert envelope.receipt_hash == AUTHORITY_ENVELOPE_HASH
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.qualification_scope == "DIRECT_DUAL_SND_ONLY_STOP_BEFORE_DISCOVERY"
    assert envelope.retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.raw_rf_persistence == "ZERO"
    assert envelope.guard_order == (
        "EXPLICIT_AUTHORITY",
        "POST_COMMIT_SEAL",
        "TERMINAL_RECEIPT_OPEN",
        "CORRECTED_DIRECT_DUAL_SND",
    )


def test_causal_source_environment_and_git_seal_match() -> None:
    assessment = f2519.assess_gate_f2_5_19()

    assert assessment.exit is (
        f2519.F2519Exit.EXACT_CORRECTED_QUALIFICATION_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.f2518_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.causal_git_diff_clean
    assert assessment.causal_source_hashes_match
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.caller_overrides_removed
    assert not assessment.live_execution_authorised
    assert assessment.blockers == ()
    assert f2519.current_causal_source_sha256() == (
        f2519.EXPECTED_CAUSAL_SOURCE_SHA256
    )
    assert f2519.current_environment() == f2519.EXPECTED_ENVIRONMENT


def test_public_surface_refuses_before_connector_or_receipt_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_dir = f2519.default_receipt_path(f2519.REVIEWED_AT).parent
    before = tuple(path.name for path in receipt_dir.glob("gate-f2-5-19-*.jsonl"))

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("connector accessed before explicit authority")

    monkeypatch.setattr(f2519.websocket, "create_connection", forbidden)
    with pytest.raises(PermissionError, match="separate exact live"):
        f2519.run_reviewed_once()
    after = tuple(path.name for path in receipt_dir.glob("gate-f2-5-19-*.jsonl"))
    assert before == after


def test_synthetic_internal_seam_runs_exact_loop_and_terminal_receipt(
    tmp_path: Path,
) -> None:
    provider = _RejectProvider()
    receipt_path = tmp_path / "sealed-synthetic.jsonl"
    result = f2519._execute_with_dependencies(
        f2519.build_authority_envelope(),
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=receipt_path,
        mirror_sink=None,
    )

    semantic = result.physical_receipt.semantic_outcome
    assert semantic.outcome is f2514.CandidateLoopOutcome.NO_MULTI_CHANNEL_CAPABILITY
    assert len(result.physical_receipt.attempts) == len(f24.ordered_candidates())
    assert len(provider.calls) == 2 * len(f24.ordered_candidates())
    assert all(socket.closed for socket in provider.sockets)
    assert all(
        attempt.pre_setup_keepalive_count == 0
        for attempt in result.physical_receipt.attempts
    )
    assert result.receipt_artifact.state.value == "COMPLETE"
    documents = tuple(json.loads(line) for line in receipt_path.read_text().splitlines())
    assert documents[0]["event"] == "gate_f2_5_19_authority_envelope_frozen"
    assert documents[0]["payload"]["authority_envelope_hash"] == (
        AUTHORITY_ENVELOPE_HASH
    )
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert documents[-1]["payload"]["raw_rf_persistence"] == "ZERO"


def test_public_signature_exposes_no_execution_override() -> None:
    signature = inspect.signature(f2519.run_reviewed_once)
    parameters = tuple(signature.parameters.values())

    assert len(parameters) == 1
    assert parameters[0].name == "live_authorised"
    assert parameters[0].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[0].default is False


def test_seal_does_not_imply_or_consume_live_authority() -> None:
    assessment = f2519.assess_gate_f2_5_19()

    assert not assessment.live_execution_authorised
    assert assessment.envelope.authority_surface == (
        "run_reviewed_once(live_authorised=False)"
    )
    assert assessment.envelope.receipt_path_policy == (
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE"
    )
    assert assessment.envelope.stop_condition == (
        "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED"
    )
