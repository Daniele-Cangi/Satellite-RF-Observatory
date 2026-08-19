"""Offline post-commit authority-seal tests for Gate F2.5.33."""

from __future__ import annotations

from dataclasses import asdict, replace
import inspect
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_29 as f2529
from experiments.live_instrument import kiwi_gate_f2_5_32 as f2532
from experiments.live_instrument import kiwi_gate_f2_5_33 as f2533
from experiments.live_instrument.models import strict_json_value


class _RejectSocket:
    def __init__(self, channel: int) -> None:
        self.channel = channel
        self.sent: list[str] = []
        self.closed = False
        self.consumed = False
        self.timeout: float | None = None
        self.leases: list[f2529._InjectedFrameLease] = []

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        if self.consumed:
            raise ConnectionError("synthetic rejection transcript exhausted")
        self.consumed = True
        payload = bytearray(
            f"MSG badp=5 is_local={self.channel},0,0".encode()
        )
        lease = f2529._InjectedFrameLease(2, time.monotonic_ns(), payload)
        self.leases.append(lease)
        return 2, lease

    def close(self) -> None:
        self.closed = True


class _RejectProvider:
    def __init__(self) -> None:
        self.roles: list[str] = []
        self.sockets: list[_RejectSocket] = []

    def __call__(self, role: str) -> _RejectSocket:
        self.roles.append(role)
        socket = _RejectSocket(0 if role == "reference" else 1)
        self.sockets.append(socket)
        return socket


class _WireSocket:
    def __init__(self, payload: bytearray) -> None:
        self.payload = payload
        self.timeout: float | None = None
        self.sent: list[str] = []
        self.closed = False

    def settimeout(self, value: float) -> None:
        self.timeout = value

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, *, control_frame: bool):
        assert control_frame is True
        return 2, SimpleNamespace(data=self.payload)

    def close(self) -> None:
        self.closed = True


def test_envelope_binds_exact_commit_surface_scope_and_zero_retry() -> None:
    envelope = f2533.build_authority_envelope()

    assert envelope.reviewed_f2532_commit == f2533.REVIEWED_F2532_COMMIT
    assert envelope.reviewed_f2532_source_sha256 == f2533.REVIEWED_F2532_SOURCE_SHA256
    assert envelope.reviewed_f2532_plan_hash == f2533.REVIEWED_F2532_PLAN_HASH
    assert envelope.reviewed_f2532_integration_surface_hash == (
        f2533.REVIEWED_F2532_INTEGRATION_SURFACE_HASH
    )
    assert envelope.reviewed_live_surface_hash == f2533.EXPECTED_LIVE_SURFACE_HASH
    assert envelope.receipt_hash == f2533.AUTHORITY_ENVELOPE_HASH
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.outcome_windows == 1
    assert envelope.stop_condition == "FIRST_TERMINAL_OUTCOME"
    assert envelope.waterfall_role == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.ext_api_role == "DESCRIPTIVE_HINT_UNUSED"
    assert envelope.raw_rf_persistence == "ZERO"


def test_commit_source_plan_environment_and_live_surface_seals_match() -> None:
    assessment = f2533.assess()

    assert assessment.exit is f2533.F2533Exit.EXACT_RF_RESPONSE_READY_FOR_SEPARATE_AUTHORITY
    assert assessment.f2532_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.reviewed_source_git_diff_clean
    assert assessment.reviewed_source_hash_matches
    assert assessment.reviewed_plan_hash_matches
    assert assessment.reviewed_integration_surface_matches
    assert assessment.live_surface_hash_matches
    assert assessment.authority_envelope_hash_matches
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.caller_overrides_removed
    assert assessment.live_execution_authorised is False
    assert assessment.blockers == ()
    assert f2533.current_f2532_source_sha256() == f2533.REVIEWED_F2532_SOURCE_SHA256
    assert f2533.current_environment() == f2533.EXPECTED_ENVIRONMENT
    assert f2533.current_live_surface_hash() == f2533.EXPECTED_LIVE_SURFACE_HASH


def test_default_refusal_precedes_assessment_receipt_and_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_dir = f2533.default_receipt_path(f2533.REVIEWED_AT).parent
    before = tuple(receipt_dir.glob("gate-f2-5-33-*.jsonl"))

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("work occurred before explicit authority")

    monkeypatch.setattr(f2533, "assess", forbidden)
    monkeypatch.setattr(f2533.websocket, "create_connection", forbidden)
    with pytest.raises(PermissionError, match="separate exact live"):
        f2533.run_reviewed_once()
    after = tuple(receipt_dir.glob("gate-f2-5-33-*.jsonl"))
    assert before == after


def test_seal_mismatch_blocks_before_receipt_or_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = f2533.assess()
    blocked = replace(
        baseline,
        exit=f2533.F2533Exit.POST_COMMIT_SEAL_MISMATCH,
        blockers=("synthetic seal mismatch",),
    )
    receipt_dir = f2533.default_receipt_path(f2533.REVIEWED_AT).parent
    before = tuple(receipt_dir.glob("gate-f2-5-33-*.jsonl"))
    calls = 0

    def forbidden(*args: object, **kwargs: object) -> object:
        nonlocal calls
        del args, kwargs
        calls += 1
        raise AssertionError("connector entered after seal mismatch")

    monkeypatch.setattr(f2533, "assess", lambda: blocked)
    monkeypatch.setattr(f2533.websocket, "create_connection", forbidden)
    with pytest.raises(RuntimeError, match="synthetic seal mismatch"):
        f2533.run_reviewed_once(live_authorised=True)
    after = tuple(receipt_dir.glob("gate-f2-5-33-*.jsonl"))
    assert calls == 0
    assert before == after


def test_internal_seam_emits_authority_first_and_exactly_one_outcome(
    tmp_path: Path,
) -> None:
    provider = _RejectProvider()
    path = tmp_path / "sealed-rejection.jsonl"
    result = f2533._execute_with_dependencies(
        f2533.build_authority_envelope(),
        connector_provider=provider,
        receipt_path=path,
        mirror_sink=None,
    )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())

    assert result.authority_consumed is True
    assert result.authority_envelope_hash == f2533.AUTHORITY_ENVELOPE_HASH
    assert result.physical_result.outcome == "CAPABILITY_REJECTED"
    assert result.physical_result.physical_hypothesis_state == "NOT_EVALUATED"
    assert sorted(provider.roles) == ["perturbed", "reference"]
    assert len(provider.sockets) == 2
    assert all(socket.closed for socket in provider.sockets)
    assert all(
        lease.released and lease.payload is None
        for socket in provider.sockets
        for lease in socket.leases
    )
    assert documents[0]["event"] == "gate_f2_5_33_authority_envelope_frozen"
    assert documents[0]["payload"]["authority_envelope_hash"] == (
        f2533.AUTHORITY_ENVELOPE_HASH
    )
    assert [item["event"] for item in documents].count(
        "gate_f2_5_33_one_outcome"
    ) == 1
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert result.receipt_artifact.state.value == "COMPLETE"
    assert result.raw_rf_persistence == "ZERO"


def test_live_adapter_transfers_and_relinquishes_mutable_frame_ownership() -> None:
    raw = bytearray(b"MSG synthetic=1")
    wire = _WireSocket(raw)
    adapted = f2533._LiveSocketAdapter(wire)

    adapted.settimeout(8.0)
    adapted.send("SET auth t=kiwi p=")
    opcode, lease = adapted.recv_data_frame(control_frame=True)
    assert opcode == 2
    assert raw == bytearray(len(raw))
    assert lease.take_payload() == b"MSG synthetic=1"
    assert lease.released and lease.payload is None
    adapted.close()
    adapted.close()
    assert wire.closed is True
    assert wire.timeout == 8.0


def test_partial_connector_failure_closes_peer_and_terminalizes_receipt(
    tmp_path: Path,
) -> None:
    reference = _RejectSocket(0)

    def provider(role: str) -> object:
        if role == "reference":
            return reference
        raise ConnectionError("synthetic peer connection failure")

    path = tmp_path / "partial-connect.jsonl"
    with pytest.raises(ConnectionError, match="synthetic peer"):
        f2533._execute_with_dependencies(
            f2533.build_authority_envelope(),
            connector_provider=provider,
            receipt_path=path,
            mirror_sink=None,
        )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())
    assert reference.closed is True
    assert documents[0]["event"] == "gate_f2_5_33_authority_envelope_frozen"
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"


def test_source_surface_and_environment_tamper_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f2533, "current_f2532_source_sha256", lambda: "0" * 64)
    source = f2533.assess()
    assert source.exit is f2533.F2533Exit.POST_COMMIT_SEAL_MISMATCH
    assert source.reviewed_source_hash_matches is False

    monkeypatch.undo()
    monkeypatch.setattr(f2533, "current_live_surface_hash", lambda: "1" * 64)
    surface = f2533.assess()
    assert surface.exit is f2533.F2533Exit.POST_COMMIT_SEAL_MISMATCH
    assert surface.live_surface_hash_matches is False

    monkeypatch.undo()
    monkeypatch.setattr(f2533, "current_environment", lambda: ())
    environment = f2533.assess()
    assert environment.exit is f2533.F2533Exit.POST_COMMIT_SEAL_MISMATCH
    assert environment.numerical_environment_matches is False


def test_public_surface_has_one_default_false_bit_and_strict_metadata() -> None:
    signature = inspect.signature(f2533.run_reviewed_once)
    parameters = tuple(signature.parameters.values())
    assessment = f2533.assess()
    encoded = f2533.strict_json(asdict(assessment))

    assert len(parameters) == 1
    assert parameters[0].name == "live_authorised"
    assert parameters[0].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[0].default is False
    assert set(f2533.__all__) == {
        "F2533Assessment",
        "F2533AuthorityEnvelope",
        "F2533Exit",
        "F2533RunResult",
        "assess",
        "build_authority_envelope",
        "run_reviewed_once",
        "strict_json",
    }
    strict_json_value(asdict(assessment))
    parsed = json.loads(encoded)
    assert parsed["live_execution_authorised"] is False
    assert parsed["raw_rf_persistence"] == "ZERO"
    assert "samples" not in encoded.lower()
    assert "stft" not in encoded.lower()
    assert '"waterfall":' not in encoded.lower()
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert f2532.TRANSFORM_VERSION in encoded
