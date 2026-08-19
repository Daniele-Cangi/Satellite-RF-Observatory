"""Offline synthetic tests for Gate F2.5.14."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import struct
from threading import Barrier, Lock

import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5_3_1 as f2531
from experiments.live_instrument import kiwi_gate_f2_5_12 as f2512
from experiments.live_instrument import kiwi_gate_f2_5_14 as f2514
from experiments.live_instrument.models import strict_json_value


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(
        self,
        frames: list[bytes | tuple[int, bytes] | Exception],
        *,
        barrier: Barrier | None = None,
    ) -> None:
        self.frames = list(frames)
        self.barrier = barrier
        self.sent: list[str] = []
        self.closed = False

    def connect(self, *args: object, **kwargs: object) -> "_Socket":
        del args, kwargs
        if self.barrier is not None:
            self.barrier.wait(timeout=2.0)
        return self

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, control_frame: bool = False) -> tuple[int, _Frame]:
        assert control_frame
        if not self.frames:
            raise ConnectionError("synthetic stream exhausted")
        item = self.frames.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            opcode, payload = item
        else:
            opcode, payload = websocket.ABNF.OPCODE_BINARY, item
        return opcode, _Frame(payload)

    def close(self) -> None:
        self.closed = True


class _Provider:
    def __init__(self, factory: object) -> None:
        self.factory = factory
        self.calls: list[tuple[str, str]] = []
        self.sockets: list[_Socket] = []
        self._lock = Lock()

    def __call__(self, endpoint: object, role: str):  # type: ignore[no-untyped-def]
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        with self._lock:
            self.calls.append((identity, role))
            socket = self.factory(endpoint, role)  # type: ignore[operator]
            self.sockets.append(socket)
        return socket.connect


def _msg(channel: int) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=12000"
    ).encode("ascii")


def _snd(*, sequence: int, gps_age_s: int = 5, gps_seconds: int = 100_000) -> bytes:
    return b"SND" + (
        struct.pack("<BI", 0x08, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", gps_age_s, 0, gps_seconds, 250_000_000)
        + struct.pack(">hhhh", 100, -100, 200, -200)
    )


def _ready_socket(role: str, *, barrier: Barrier | None = None, same_id: bool = False) -> _Socket:
    channel = 7 if role == "reference" or same_id else 8
    sequence = 17 if role == "reference" else 29
    return _Socket([_msg(channel), _snd(sequence=sequence)], barrier=barrier)


def _badp_socket() -> _Socket:
    return _Socket([b"MSG badp=5"])


def _close_socket(*, stale: bool = False) -> _Socket:
    frames: list[bytes | tuple[int, bytes]] = [_msg(7)]
    if stale:
        frames.append(_snd(sequence=17, gps_age_s=31))
    frames.append((websocket.ABNF.OPCODE_CLOSE, b""))
    return _Socket(frames)


def test_two_branches_are_started_concurrently_and_admitted_only_as_a_pair() -> None:
    endpoint = f24.ordered_candidates()[0]
    barrier = Barrier(2)
    provider = _Provider(
        lambda _endpoint, role: _ready_socket(role, barrier=barrier)
    )

    opened = f2514.open_dual_semantic_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )
    receipt = opened.receipt

    assert receipt.state is f2514.PairState.DUAL_READY
    assert receipt.direct_reference_attempted
    assert receipt.direct_perturbed_attempted
    assert receipt.distinct_connection_objects_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.distinct_channel_ids_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.event_time_overlap_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.separate_stream_sequences_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.separate_branch_receipts_clause is f2512.ClauseEvaluation.SATISFIED
    assert receipt.overlap_s is not None and receipt.overlap_s > 0.0
    assert opened.connections is not None
    assert not any(socket.closed for socket in provider.sockets)
    opened.close()
    assert all(socket.closed for socket in provider.sockets)


def test_explicit_control_rejection_closes_the_ready_peer_without_inference() -> None:
    endpoint = f24.ordered_candidates()[0]
    provider = _Provider(
        lambda _endpoint, role: _ready_socket(role)
        if role == "reference"
        else _badp_socket()
    )

    opened = f2514.open_dual_semantic_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    assert opened.connections is None
    assert opened.receipt.state is f2514.PairState.EXPLICIT_PAIR_REJECTED
    assert opened.receipt.reference_ready_clause is f2512.ClauseEvaluation.SATISFIED
    assert opened.receipt.perturbed_ready_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert opened.receipt.distinct_connection_objects_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert opened.receipt.distinct_channel_ids_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert all(socket.closed for socket in provider.sockets)


@pytest.mark.parametrize("stale", [False, True])
def test_close_without_readiness_remains_qualification_incomplete(stale: bool) -> None:
    endpoint = f24.ordered_candidates()[0]
    provider = _Provider(lambda _endpoint, _role: _close_socket(stale=stale))

    opened = f2514.open_dual_semantic_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    assert opened.receipt.state is f2514.PairState.QUALIFICATION_INCOMPLETE
    assert opened.receipt.reference_ready_clause is f2512.ClauseEvaluation.QUALIFICATION_ERROR
    for branch in opened.receipt.branch_receipts:
        assert branch.peer_close_status_code is None
        assert branch.close_payload_state is f2512.ClosePayloadState.EMPTY_NO_STATUS


def test_equal_channel_allocations_reject_topology_after_two_ready_streams() -> None:
    endpoint = f24.ordered_candidates()[0]
    provider = _Provider(
        lambda _endpoint, role: _ready_socket(role, same_id=True)
    )

    opened = f2514.open_dual_semantic_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    assert opened.receipt.state is f2514.PairState.TOPOLOGY_REJECTED
    assert opened.receipt.reference_ready_clause is f2512.ClauseEvaluation.SATISFIED
    assert opened.receipt.perturbed_ready_clause is f2512.ClauseEvaluation.SATISFIED
    assert opened.receipt.distinct_channel_ids_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert all(socket.closed for socket in provider.sockets)


def test_one_connection_object_cannot_masquerade_as_two_downstream_branches() -> None:
    endpoint = f24.ordered_candidates()[0]
    shared = _ready_socket("reference")
    provider = _Provider(lambda _endpoint, _role: shared)

    opened = f2514.open_dual_semantic_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    assert opened.receipt.state is not f2514.PairState.DUAL_READY
    assert opened.receipt.distinct_connection_objects_clause is not (
        f2512.ClauseEvaluation.SATISFIED
    )


def test_candidate_loop_preserves_order_stops_at_first_ready_and_is_terminal(tmp_path: Path) -> None:
    candidates = f24.ordered_candidates()
    first = f"{candidates[0].host.lower()}:{candidates[0].port}"

    def factory(endpoint: object, role: str) -> _Socket:
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        return _badp_socket() if identity == first else _ready_socket(role)

    provider = _Provider(factory)
    path = tmp_path / "receipt.jsonl"
    result = f2514.execute_candidate_loop_injected(
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=path,
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
    )
    assert len(result.physical_receipt.attempts) == 2
    assert tuple(item.endpoint_identity for item in result.physical_receipt.attempts) == (
        f24.ordered_candidate_identities()[:2]
    )
    assert len(provider.calls) == 4
    assert all(socket.closed for socket in provider.sockets)
    assert result.receipt_artifact.state is f2531.RetentionState.COMPLETE
    assert result.receipt_artifact.terminal_manifest_written
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["event"] == f"{f2514.EVENT_PREFIX}_execution_envelope"
    assert lines[-1]["event"] == f2531.TERMINAL_EVENT
    assert '"peer_close_status_code":1005' not in path.read_text(encoding="utf-8")


def test_no_multi_is_legal_only_after_two_direct_attempts_on_every_candidate(tmp_path: Path) -> None:
    provider = _Provider(lambda _endpoint, _role: _badp_socket())
    result = f2514.execute_candidate_loop_injected(
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=tmp_path / "negative.jsonl",
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.NO_MULTI_CHANNEL_CAPABILITY
    )
    assert len(result.physical_receipt.attempts) == len(f24.ordered_candidates())
    assert len(provider.calls) == 2 * len(f24.ordered_candidates())
    assert all(
        attempt.direct_reference_attempted and attempt.direct_perturbed_attempted
        for attempt in result.physical_receipt.attempts
    )
    with pytest.raises(ValueError, match="NO_ADMISSIBLE"):
        replace(
            result.physical_receipt,
            outcome=f2514.CandidateLoopOutcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY,
        )


def test_unresolved_attempt_prevents_no_multi_claim(tmp_path: Path) -> None:
    first_identity = f24.ordered_candidate_identities()[0]

    def factory(endpoint: object, _role: str) -> _Socket:
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        return _close_socket() if identity == first_identity else _badp_socket()

    result = f2514.execute_candidate_loop_injected(
        connector_provider=_Provider(factory),
        websocket_module=websocket,
        receipt_path=tmp_path / "incomplete.jsonl",
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.QUALIFICATION_INCOMPLETE
    )
    with pytest.raises(ValueError, match="NO_MULTI"):
        replace(
            result.physical_receipt,
            outcome=f2514.CandidateLoopOutcome.NO_MULTI_CHANNEL_CAPABILITY,
        )


def test_receipt_open_failure_cannot_change_the_physical_pair_decision(tmp_path: Path) -> None:
    path = tmp_path / "already-exists.jsonl"
    path.write_text("occupied", encoding="utf-8")
    provider = _Provider(lambda _endpoint, role: _ready_socket(role))

    result = f2514.execute_candidate_loop_injected(
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=path,
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
    )
    assert result.receipt_artifact.state is f2531.RetentionState.DESCRIPTIVE_ERROR
    assert not result.receipt_artifact.retention_complete
    assert path.read_text(encoding="utf-8") == "occupied"


def test_envelope_is_frozen_and_requires_post_commit_review() -> None:
    envelope = f2514.build_execution_envelope(
        created_at=datetime(2026, 8, 17, tzinfo=timezone.utc)
    )

    assert envelope.candidate_order == f24.ordered_candidate_identities()
    assert envelope.branch_roles == ("reference", "perturbed")
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.maximum_gps_solution_age_s == 30
    assert envelope.waterfall_semantics == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.post_commit_review_state == "REQUIRED_BEFORE_LIVE_AUTHORITY"
    with pytest.raises(FrozenInstanceError):
        envelope.prefreeze_retry_budget = 1  # type: ignore[misc]
    with pytest.raises(ValueError, match="concurrency envelope"):
        replace(envelope, attempts_per_candidate=2)


def test_module_has_no_connector_default_or_autonomous_live_surface() -> None:
    dual_signature = inspect.signature(f2514.open_dual_semantic_injected)
    loop_signature = inspect.signature(f2514.execute_candidate_loop_injected)
    source = inspect.getsource(f2514)

    assert dual_signature.parameters["connector_provider"].default is inspect.Parameter.empty
    assert dual_signature.parameters["websocket_module"].default is inspect.Parameter.empty
    assert loop_signature.parameters["connector_provider"].default is inspect.Parameter.empty
    assert loop_signature.parameters["websocket_module"].default is inspect.Parameter.empty
    assert "create_connection" not in source
    assert "import websocket" not in source
    assert not hasattr(f2514, "run")
    assert not hasattr(f2514, "main")


def test_strict_receipt_contains_no_rf_or_non_finite_value() -> None:
    endpoint = f24.ordered_candidates()[0]
    provider = _Provider(lambda _endpoint, role: _ready_socket(role))
    opened = f2514.open_dual_semantic_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    encoded = json.dumps(
        strict_json_value(opened.receipt),
        allow_nan=False,
        sort_keys=True,
    ).lower()
    opened.close()
    for forbidden in ("iq_samples", "raw_frame", "raw_body", "waterfall", "stft"):
        assert forbidden not in encoded
    assert '"raw_rf_persistence": "zero"' in encoded


def test_offline_assessment_stops_before_network_authority() -> None:
    assessment = f2514.assess_gate_f2_5_14()

    assert assessment.exit is (
        f2514.F2514Exit.DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE
    )
    assert assessment.two_branch_concurrency_materialized
    assert assessment.candidate_loop_materialized
    assert assessment.terminal_receipt_materialized
    assert assessment.exact_envelope_materialized
    assert assessment.post_commit_review_required
    assert not assessment.live_execution_authorised
    assert assessment.raw_rf_persistence == "ZERO"
