"""Offline dual-composition tests for Gate F2.5.18."""

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
from experiments.live_instrument import kiwi_gate_f2_5_12 as f2512
from experiments.live_instrument import kiwi_gate_f2_5_14 as f2514
from experiments.live_instrument import kiwi_gate_f2_5_17 as f2517
from experiments.live_instrument import kiwi_gate_f2_5_18 as f2518
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


def _snd(*, sequence: int, gps_seconds: int = 100_000) -> bytes:
    return b"SND" + (
        struct.pack("<BI", 0x08, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", 5, 0, gps_seconds, 250_000_000)
        + struct.pack(">hhhh", 100, -100, 200, -200)
    )


def _ready_socket(
    role: str, *, barrier: Barrier | None = None, same_id: bool = False
) -> _Socket:
    channel = 7 if role == "reference" or same_id else 8
    sequence = 17 if role == "reference" else 29
    return _Socket([_msg(channel), _snd(sequence=sequence)], barrier=barrier)


def _badp_socket() -> _Socket:
    return _Socket([b"MSG badp=5"])


def test_envelope_binds_corrected_control_and_zero_retry() -> None:
    envelope = f2518.build_execution_envelope(
        created_at=datetime(2026, 8, 18, tzinfo=timezone.utc)
    )

    assert envelope.parent_gate_commit == f2518.PARENT_GATE_COMMIT
    assert envelope.control_plan_hash == f2517.control_plan_hash()
    assert envelope.branch_composition == "TWO_THREADS_ONE_ENDPOINT_PHASE_AWARE_SND"
    assert envelope.maximum_parallel_branches == 2
    assert envelope.maximum_parallel_endpoints == 1
    assert envelope.attempts_per_candidate == 1
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.status_precondition == "NONE_BEFORE_DIRECT_SND"
    assert envelope.waterfall_precondition == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.post_commit_review_state == "REQUIRED_BEFORE_LIVE_AUTHORITY"
    with pytest.raises(FrozenInstanceError):
        envelope.prefreeze_retry_budget = 1  # type: ignore[misc]
    with pytest.raises(ValueError, match="control plan"):
        replace(envelope, control_plan_hash="0" * 64)


def test_two_corrected_branches_start_concurrently_and_form_one_pair() -> None:
    endpoint = f24.ordered_candidates()[0]
    barrier = Barrier(2)
    provider = _Provider(
        lambda _endpoint, role: _ready_socket(role, barrier=barrier)
    )

    opened = f2518.open_dual_phase_aware_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )
    receipt = opened.receipt

    assert receipt.semantic_pair.state is f2514.PairState.DUAL_READY
    assert receipt.semantic_pair.distinct_connection_objects_clause is (
        f2512.ClauseEvaluation.SATISFIED
    )
    assert receipt.semantic_pair.distinct_channel_ids_clause is (
        f2512.ClauseEvaluation.SATISFIED
    )
    assert receipt.semantic_pair.event_time_overlap_clause is (
        f2512.ClauseEvaluation.SATISFIED
    )
    assert receipt.pre_setup_keepalive_count == 0
    assert receipt.remote_setup_acknowledgement_clause is (
        f2512.ClauseEvaluation.NOT_EVALUATED
    )
    assert all(
        branch.local_setup_emission_clause is f2512.ClauseEvaluation.SATISFIED
        for branch in receipt.branch_controls
    )
    assert all("SET keepalive" not in socket.sent for socket in provider.sockets)
    assert opened.connections is not None
    opened.close()
    assert all(socket.closed for socket in provider.sockets)


def test_explicit_rejection_does_not_promote_pair_topology() -> None:
    endpoint = f24.ordered_candidates()[0]
    provider = _Provider(
        lambda _endpoint, role: _ready_socket(role)
        if role == "reference"
        else _badp_socket()
    )

    opened = f2518.open_dual_phase_aware_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    assert opened.connections is None
    assert opened.receipt.semantic_pair.state is f2514.PairState.EXPLICIT_PAIR_REJECTED
    assert opened.receipt.semantic_pair.reference_ready_clause is (
        f2512.ClauseEvaluation.SATISFIED
    )
    assert opened.receipt.semantic_pair.perturbed_ready_clause is (
        f2512.ClauseEvaluation.UNSATISFIED
    )
    assert opened.receipt.semantic_pair.distinct_channel_ids_clause is (
        f2512.ClauseEvaluation.NOT_EVALUATED
    )
    assert all(socket.closed for socket in provider.sockets)


def test_equal_server_channel_ids_reject_the_topology_after_readiness() -> None:
    endpoint = f24.ordered_candidates()[0]
    provider = _Provider(
        lambda _endpoint, role: _ready_socket(role, same_id=True)
    )

    opened = f2518.open_dual_phase_aware_injected(
        endpoint,
        connector_provider=provider,
        websocket_module=websocket,
    )

    assert opened.connections is None
    assert opened.receipt.semantic_pair.state is f2514.PairState.TOPOLOGY_REJECTED
    assert opened.receipt.semantic_pair.distinct_channel_ids_clause is (
        f2512.ClauseEvaluation.UNSATISFIED
    )
    assert opened.receipt.pre_setup_keepalive_count == 0


def test_candidate_loop_stops_at_first_ready_pair_and_closes_terminal_receipt(
    tmp_path: Path,
) -> None:
    candidates = f24.ordered_candidates()
    first_identity = f"{candidates[0].host.lower()}:{candidates[0].port}"
    second_identity = f"{candidates[1].host.lower()}:{candidates[1].port}"

    def factory(endpoint: object, role: str) -> _Socket:
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        return _badp_socket() if identity == first_identity else _ready_socket(role)

    provider = _Provider(factory)
    receipt_path = tmp_path / "gate-f2-5-18.jsonl"
    result = f2518.execute_candidate_loop_injected(
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=receipt_path,
    )

    semantic = result.physical_receipt.semantic_outcome
    assert semantic.outcome is f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
    assert semantic.selected_endpoint_identity == second_identity
    assert len(result.physical_receipt.attempts) == 2
    assert tuple(item.semantic_pair.endpoint_identity for item in result.physical_receipt.attempts) == (
        first_identity,
        second_identity,
    )
    assert len(provider.calls) == 4
    assert result.receipt_artifact.state.value == "COMPLETE"
    documents = tuple(json.loads(line) for line in receipt_path.read_text().splitlines())
    assert documents[0]["event"] == "gate_f2_5_18_execution_envelope"
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    encoded = json.dumps(strict_json_value(result.physical_receipt), allow_nan=False)
    assert '"raw_rf_persistence": "ZERO"' in encoded
    assert '"pre_setup_keepalive_count": 0' in encoded


def test_injected_dependencies_are_mandatory_and_gate_is_not_live() -> None:
    signature = inspect.signature(f2518.open_dual_phase_aware_injected)
    execution = inspect.signature(f2518.execute_candidate_loop_injected)
    source = inspect.getsource(f2518)
    assessment = f2518.assess_gate_f2_5_18()

    assert signature.parameters["connector_provider"].default is inspect.Parameter.empty
    assert signature.parameters["websocket_module"].default is inspect.Parameter.empty
    assert execution.parameters["receipt_path"].default is inspect.Parameter.empty
    assert "create_connection" not in source
    assert "import websocket" not in source
    assert not hasattr(f2518, "run")
    assert not hasattr(f2518, "main")
    assert assessment.exit is (
        f2518.F2518Exit.DUAL_PHASE_AWARE_ENVELOPE_MATERIALIZED_OFFLINE
    )
    assert assessment.two_branch_concurrency_materialized
    assert assessment.phase_aware_control_bound_to_both_branches
    assert assessment.pair_topology_preserved
    assert assessment.candidate_loop_materialized
    assert assessment.terminal_receipt_materialized
    assert assessment.post_commit_review_required
    assert not assessment.live_execution_authorised
    assert assessment.raw_rf_persistence == "ZERO"
