"""Offline tests for Gate F2.5.2 atomic SND branch receipts."""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_2 as f252
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 16, 22, 0, tzinfo=timezone.utc)
ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)
STATUS = {"ext_api": "7", "version_maj": "1", "version_min": "800"}


class _Socket:
    def __init__(self, messages: list[bytes | Exception] | None = None) -> None:
        self.messages = list(messages or [])
        self.commands: list[str] = []
        self.closed = False

    def send(self, command: str) -> None:
        self.commands.append(command)

    def recv(self) -> bytes:
        if not self.messages:
            raise ConnectionError("fixture stream exhausted")
        value = self.messages.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    def close(self) -> None:
        self.closed = True


def _block(*, gps_valid: bool = True, sequence: int = 17) -> kiwi.IQBlock:
    return kiwi.IQBlock(
        NOW,
        NOW + timedelta(seconds=1),
        np.zeros(16, dtype=np.complex64),
        -80.0,
        0 if gps_valid else 255,
        gps_valid,
        False,
        sequence,
        NOW + timedelta(seconds=1, milliseconds=10),
    )


def _receipt(
    role: str,
    state: f252.BranchOpenState,
    *,
    channel_id: str | None = None,
    iq_frames: int = 0,
    disposition: f252.PairDisposition | None = None,
) -> f252.BranchOpenReceipt:
    ready = state is f252.BranchOpenState.READY
    stream_hash = ("a" if role == "reference" else "b") * 64 if iq_frames else None
    readiness_hash = ("c" if role == "reference" else "d") * 64 if ready else None
    error = None if ready else ("PermissionError" if state is f252.BranchOpenState.CAPABILITY_REJECTED else "TimeoutError")
    message = None if ready else ("public SND rejected" if state is f252.BranchOpenState.CAPABILITY_REJECTED else "socket timed out")
    return f252.BranchOpenReceipt(
        endpoint_identity="fixture.invalid:8073",
        role=role,
        state=state,
        started_at=NOW,
        completed_at=NOW + timedelta(milliseconds=10),
        attempted=True,
        websocket_opened=ready or iq_frames > 0,
        handshake_message_count=1 if ready or iq_frames > 0 else 0,
        handshake_hash=("e" if role == "reference" else "f") * 64 if ready or iq_frames > 0 else None,
        configuration_sent=ready or iq_frames > 0,
        sample_rate_hz=1000.0 if ready or iq_frames > 0 else None,
        channel_id=channel_id if ready else None,
        channel_id_basis="fixture channel allocation" if ready else None,
        iq_frame_count=iq_frames,
        iq_raw_bytes=32 * iq_frames,
        iq_stream_artifact_hash=stream_hash,
        readiness_frame_artifact_hash=readiness_hash,
        readiness_event_start=NOW if ready else None,
        readiness_event_end=NOW + timedelta(seconds=1) if ready else None,
        readiness_sequence=17 if ready else None,
        readiness_gps_solution_age_s=0 if ready else None,
        error_type=error,
        error_message=message,
        error_description_hash=("1" if role == "reference" else "2") * 64 if error else None,
        pair_disposition=disposition
        or (
            f252.PairDisposition.BRANCH_READY_UNCOMPOSED
            if ready
            else f252.PairDisposition.CLOSED_ON_BRANCH_FAILURE
        ),
    )


def _connection(role: str, channel_id: str, socket: _Socket | None = None) -> f24._ChannelConnection:
    return f24._ChannelConnection(
        ENDPOINT,
        role,
        1 if role == "reference" else 2,
        channel_id,
        "fixture channel allocation",
        socket or _Socket(),
        1000.0,
        STATUS,
        {"rx_chan": channel_id.removeprefix("rx:")},
        ("3" if role == "reference" else "4") * 64,
        [],
    )


def test_bootstrap_binds_f251_runtime_outcome_and_atomic_policy() -> None:
    receipt = f252.build_bootstrap_receipt(runtime_commit="a" * 40, created_at=NOW)
    value = strict_json_value(receipt)
    json.dumps(value, allow_nan=False)
    assert receipt.parent_runtime_commit == f252.PARENT_RUNTIME_COMMIT
    assert receipt.parent_outcome_commit == f252.PARENT_OUTCOME_COMMIT
    assert receipt.atomic_branch_receipts_required
    assert receipt.readiness_frame_hash_required
    assert receipt.stream_hash_before_decode_required
    assert receipt.raw_rf_persistence == "ZERO"
    assert receipt.transform_versions[-1] == f252.F252_TRANSFORM_VERSION


def test_ephemeral_hasher_is_length_delimited_and_never_stores_frames() -> None:
    hasher = f252._EphemeralSndHasher.create()
    first = b"SNDfirst"
    second = b"SNDsecond"
    assert hasher.observe_before_decode(first) == sha256(first).hexdigest()
    assert hasher.observe_before_decode(second) == sha256(second).hexdigest()
    expected = sha256(
        len(first).to_bytes(8, "big") + first + len(second).to_bytes(8, "big") + second
    ).hexdigest()
    assert hasher.stream_hash == expected
    assert hasher.frame_count == 2
    assert hasher.raw_bytes == len(first) + len(second)
    assert not hasattr(hasher, "frames")


def test_ready_branch_hashes_frame_before_decode_and_preserves_witness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_body = b"fixture-raw-iq"
    raw_frame = b"SND" + raw_body
    socket = _Socket(
        [
            b"MSG sample_rate=1000 audio_rate=12000 rx_chan=7",
            raw_frame,
        ]
    )
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)
    observed_before_decode = False
    original_observe = f252._EphemeralSndHasher.observe_before_decode

    def observe(self: f252._EphemeralSndHasher, frame: bytes) -> str:
        nonlocal observed_before_decode
        observed_before_decode = True
        return original_observe(self, frame)

    def decode(body: bytes, sample_rate: float, _arrival: datetime) -> kiwi.IQBlock:
        assert observed_before_decode
        assert body == raw_body
        assert sample_rate == 1000.0
        return _block()

    monkeypatch.setattr(f252._EphemeralSndHasher, "observe_before_decode", observe)
    monkeypatch.setattr(f252.kiwi, "_decode_iq_block", decode)
    result = f252._atomic_open_channel(ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan())

    assert result.connection is not None
    assert result.receipt.state is f252.BranchOpenState.READY
    assert result.receipt.channel_id == "rx:7"
    assert result.receipt.iq_frame_count == 1
    assert result.receipt.readiness_frame_artifact_hash == sha256(raw_frame).hexdigest()
    expected_stream = sha256(len(raw_frame).to_bytes(8, "big") + raw_frame).hexdigest()
    assert result.receipt.iq_stream_artifact_hash == expected_stream
    assert result.receipt.readiness_event_start == NOW
    assert result.receipt.readiness_sequence == 17
    assert "samples" not in json.dumps(strict_json_value(result.receipt), allow_nan=False)
    result.connection.close()
    assert socket.closed


def test_nonready_iq_is_hashed_even_when_transport_later_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_frame = b"SNDnonready"
    socket = _Socket(
        [
            b"MSG sample_rate=1000 rx_chan=8",
            raw_frame,
            ConnectionError("transport closed"),
        ]
    )
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)
    monkeypatch.setattr(f252.kiwi, "_decode_iq_block", lambda *_args, **_kwargs: _block(gps_valid=False))
    result = f252._atomic_open_channel(ENDPOINT, "perturbed", 10_000_000.0, STATUS, f2.MotherPlan())

    assert result.connection is None
    assert result.receipt.state is f252.BranchOpenState.QUALIFICATION_ERROR
    assert result.receipt.iq_frame_count == 1
    assert result.receipt.iq_stream_artifact_hash is not None
    assert result.receipt.readiness_frame_artifact_hash is None
    assert result.receipt.error_type == "ConnectionError"
    assert socket.closed


def test_snd_frame_before_sample_rate_is_hashed_then_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_frame = b"SNDpremature"
    socket = _Socket([raw_frame])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)
    result = f252._atomic_open_channel(ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan())
    assert result.receipt.state is f252.BranchOpenState.QUALIFICATION_ERROR
    assert result.receipt.iq_frame_count == 1
    assert result.receipt.iq_stream_artifact_hash is not None
    assert result.receipt.error_message == "SND frame preceded sample-rate negotiation"
    assert socket.closed


def test_explicit_public_access_refusal_is_branch_capability_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket([b"MSG badp=1"])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)
    result = f252._atomic_open_channel(ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan())
    assert result.receipt.state is f252.BranchOpenState.CAPABILITY_REJECTED
    assert result.receipt.iq_frame_count == 0
    assert result.receipt.error_description_hash is not None
    assert socket.closed


def test_descriptive_transport_text_cannot_become_capability_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket([ConnectionError("busy text inside a transport error")])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)
    result = f252._atomic_open_channel(ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan())
    assert result.receipt.state is f252.BranchOpenState.QUALIFICATION_ERROR
    assert result.receipt.error_type == "ConnectionError"


def test_partial_pair_preserves_ready_sibling_then_closes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_socket = _Socket()
    reference = f252._BranchOpenResult(
        _connection("reference", "rx:1", reference_socket),
        _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
    )
    perturbed = f252._BranchOpenResult(
        None,
        _receipt("perturbed", f252.BranchOpenState.CAPABILITY_REJECTED),
    )
    monkeypatch.setattr(
        f252,
        "_atomic_open_channel",
        lambda _endpoint, role, *_args: reference if role == "reference" else perturbed,
    )

    with pytest.raises(f252.AtomicDualOpenError) as caught:
        f252._atomic_open_dual(ENDPOINT, 10_000_000.0, STATUS, f2.MotherPlan())
    by_role = {item.role: item for item in caught.value.receipts}
    assert by_role["reference"].state is f252.BranchOpenState.READY
    assert by_role["reference"].pair_disposition is f252.PairDisposition.CLOSED_AFTER_PEER_FAILURE
    assert by_role["reference"].readiness_frame_artifact_hash is not None
    assert by_role["perturbed"].state is f252.BranchOpenState.CAPABILITY_REJECTED
    assert reference_socket.closed


def test_two_unique_ready_branches_are_composed_only_after_both_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = {
        "reference": f252._BranchOpenResult(
            _connection("reference", "rx:1"),
            _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        ),
        "perturbed": f252._BranchOpenResult(
            _connection("perturbed", "rx:2"),
            _receipt("perturbed", f252.BranchOpenState.READY, channel_id="rx:2", iq_frames=1),
        ),
    }
    monkeypatch.setattr(f252, "_atomic_open_channel", lambda _endpoint, role, *_args: results[role])
    dual, receipts = f252._atomic_open_dual(ENDPOINT, 10_000_000.0, STATUS, f2.MotherPlan())
    assert tuple(item.role for item in receipts) == f252.BRANCH_ROLES
    assert all(item.state is f252.BranchOpenState.READY for item in receipts)
    assert all(item.pair_disposition is f252.PairDisposition.ADMITTED_TO_PAIR for item in receipts)
    assert dual.reference.channel_id == "rx:1"
    assert dual.perturbed.channel_id == "rx:2"
    dual.close()


def test_duplicate_channel_identity_rejects_topology_without_erasing_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets = (_Socket(), _Socket())
    results = {
        "reference": f252._BranchOpenResult(
            _connection("reference", "rx:1", sockets[0]),
            _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        ),
        "perturbed": f252._BranchOpenResult(
            _connection("perturbed", "rx:1", sockets[1]),
            _receipt("perturbed", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        ),
    }
    monkeypatch.setattr(f252, "_atomic_open_channel", lambda _endpoint, role, *_args: results[role])
    with pytest.raises(f252.AtomicDualOpenError) as caught:
        f252._atomic_open_dual(ENDPOINT, 10_000_000.0, STATUS, f2.MotherPlan())
    assert all(
        item.pair_disposition is f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION
        for item in caught.value.receipts
    )
    assert all(item.readiness_frame_artifact_hash is not None for item in caught.value.receipts)
    assert all(socket.closed for socket in sockets)


def test_mixed_atomic_results_cannot_become_physical_multichannel_rejection() -> None:
    branch_receipts = (
        _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        _receipt("perturbed", f252.BranchOpenState.QUALIFICATION_ERROR),
    )
    base = f25.PhaseReceipt(
        "fixture.invalid:8073",
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        f25.F25PhaseState.UNSATISFIED,
        NOW,
        NOW,
        "aggregate fixture",
        ("9" * 64,),
        (),
        None,
        True,
        True,
    )
    decorated = f252._decorate_direct_result(base, branch_receipts)
    assert isinstance(decorated, f25.PhaseReceipt)
    assert decorated.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert decorated.direct_reference_opened
    assert not decorated.direct_perturbed_opened
    assert decorated.atomic_branch_receipts == branch_receipts
    assert f25.no_topology_outcome((decorated,)) is f25.F25Outcome.QUALIFICATION_INCOMPLETE
    strict_json_value(decorated)


def test_direct_qualification_uses_atomic_results_and_missing_status_bandwidth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch_receipts = (
        _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        _receipt("perturbed", f252.BranchOpenState.QUALIFICATION_ERROR),
    )
    monkeypatch.setattr(f252.f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: {"ext_api": "0"})
    monkeypatch.setattr(
        f252,
        "_atomic_open_dual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            f252.AtomicDualOpenError(branch_receipts, "fixture mixed outcome")
        ),
    )
    result = f252.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(result, f25.PhaseReceipt)
    assert result.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert result.direct_reference_attempted and result.direct_perturbed_attempted
    assert result.direct_reference_opened and not result.direct_perturbed_opened
    assert len(result.atomic_branch_receipts) == 2
    assert all(item.receipt_hash in result.artifact_hashes for item in branch_receipts)
    assert result.ext_api_hint is not None and not result.ext_api_hint.used_as_gate


def test_ready_branch_receipts_survive_later_topology_capture_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branch_receipts = (
        _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        _receipt("perturbed", f252.BranchOpenState.READY, channel_id="rx:2", iq_frames=1),
    )
    dual = f24._DualConnections(
        _connection("reference", "rx:1"),
        _connection("perturbed", "rx:2"),
    )
    monkeypatch.setattr(f252.f25.kiwi, "fetch_kiwi_status", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(f252, "_atomic_open_dual", lambda *_args, **_kwargs: (dual, branch_receipts))
    monkeypatch.setattr(
        f252.f25.f24,
        "_capture_dual",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("topology capture timed out")),
    )
    result = f252.direct_dual_snd_qualification(ENDPOINT, f2.MotherPlan())
    assert isinstance(result, f25.PhaseReceipt)
    assert result.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert result.direct_reference_opened and result.direct_perturbed_opened
    assert result.atomic_branch_receipts == branch_receipts
    assert all(item.receipt_hash in result.artifact_hashes for item in branch_receipts)


def test_runner_delegates_frozen_atomic_bootstrap_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    sentinel = object()

    def delegated(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(f252.f25, "run_once", delegated)
    result = f252.run_once(runtime_commit="b" * 40, sink=lambda _line: None)
    assert result is sentinel
    assert captured["event_prefix"] == "gate_f2_5_2"
    assert captured["terminal_instrument"] == "gate-f2.5.2-atomic-dual-snd"
    assert captured["direct_qualifier"] is f252.direct_dual_snd_qualification
    assert isinstance(captured["bootstrap_receipt"], f252.F252BootstrapReceipt)


def test_runner_emits_each_atomic_branch_before_aggregate_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    branches = (
        _receipt("reference", f252.BranchOpenState.READY, channel_id="rx:1", iq_frames=1),
        _receipt("perturbed", f252.BranchOpenState.QUALIFICATION_ERROR),
    )
    base = f25.PhaseReceipt(
        "fixture.invalid:8073",
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        f25.F25PhaseState.QUALIFICATION_ERROR,
        NOW,
        NOW,
        "fixture indeterminate",
        (),
        (),
        None,
        True,
        True,
    )
    atomic = f252._decorate_direct_result(base, branches)
    assert isinstance(atomic, f25.PhaseReceipt)
    monkeypatch.setattr(f252.f24, "ordered_candidates", lambda: (ENDPOINT,))
    monkeypatch.setattr(f252, "direct_dual_snd_qualification", lambda *_args: atomic)
    lines: list[str] = []
    result = f252.run_once(runtime_commit="d" * 40, sink=lines.append)
    documents = tuple(json.loads(line) for line in lines)
    events = tuple(document["event"] for document in documents)
    atomic_indexes = tuple(
        index for index, event in enumerate(events) if event == "gate_f2_5_2_atomic_snd_branch_receipt"
    )
    aggregate_index = events.index("gate_f2_5_2_direct_dual_snd_qualification")
    assert len(atomic_indexes) == 2
    assert max(atomic_indexes) < aggregate_index
    assert tuple(documents[index]["payload"]["role"] for index in atomic_indexes) == f252.BRANCH_ROLES
    assert result.outcome is f25.F25Outcome.QUALIFICATION_INCOMPLETE


def test_source_has_no_waterfall_storage_or_network_on_import() -> None:
    source = Path(f252.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "open" not in called_names
    assert "write_text" not in called_attributes
    assert "write_bytes" not in called_attributes
    assert "_capture_waterfall" not in called_attributes
    assert source.index("observe_before_decode(raw_frame)") < source.index(
        "_decode_iq_block(body, sample_rate, arrival)"
    )
