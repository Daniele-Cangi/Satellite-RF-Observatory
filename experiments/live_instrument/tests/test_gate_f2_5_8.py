"""Offline synthetic-wire tests for Gate F2.5.8 receipt integration."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ast
import json
from pathlib import Path

import numpy as np
import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5_2 as f252
from experiments.live_instrument import kiwi_gate_f2_5_7 as f257
from experiments.live_instrument import kiwi_gate_f2_5_8 as f258
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64
ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)
STATUS = {"name": "fixture"}


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(
        self,
        frames: list[bytes | tuple[int, bytes] | Exception],
        *,
        fail_send_prefix: str | None = None,
    ) -> None:
        self.frames = list(frames)
        self.fail_send_prefix = fail_send_prefix
        self.sent: list[str] = []
        self.closed = False

    def send(self, command: str) -> None:
        if self.fail_send_prefix and command.startswith(self.fail_send_prefix):
            raise ConnectionError("synthetic send failure")
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


def _block(*, sequence: int = 17, gps_valid: bool = True) -> kiwi.IQBlock:
    return kiwi.IQBlock(
        NOW,
        NOW + timedelta(seconds=0.1),
        np.array([1 + 1j, 2 + 2j], dtype=np.complex64),
        -80.0,
        1,
        gps_valid,
        False,
        sequence,
        NOW,
    )


def _ready_transcript(role: str, channel: int, sequence: int = 17) -> f257.WireTranscript:
    kinds = f257.WireEventKind

    def event(ordinal: int, kind: f257.WireEventKind, **kwargs: object) -> f257.WireEvent:
        return f257.WireEvent(role, ordinal, ordinal, kind, **kwargs)

    return f257.WireTranscript(
        role,
        (
            event(0, kinds.WEBSOCKET_OPENED),
            event(1, kinds.AUTH_SENT_REDACTED),
            event(2, kinds.CHANNEL_ALLOCATED_OBSERVED, channel_id=channel),
            event(3, kinds.BADP_OK_OBSERVED),
            event(4, kinds.SAMPLE_RATE_OBSERVED, numeric_value=1000.0),
            event(5, kinds.MOD_IQ_SENT),
            event(6, kinds.IQ_FRAME_OBSERVED, artifact_hash=DIGEST, sequence=sequence),
        ),
    )


def _ready_receipt(role: str, channel: int) -> f258.F258BranchReceipt:
    transcript = _ready_transcript(role, channel)
    return f258.F258BranchReceipt(
        "fixture.invalid:8073",
        role,
        f258.F258BranchState.READY,
        NOW,
        NOW + timedelta(seconds=1),
        transcript,
        f257.assess_branch_wire(transcript),
        1,
        20,
        DIGEST,
        (DIGEST,),
        (DIGEST,),
        DIGEST,
        NOW,
        NOW + timedelta(seconds=0.1),
        17,
        1,
        None,
        None,
        f252.PairDisposition.BRANCH_READY_UNCOMPOSED,
    )


def _connection(role: str, channel: int, socket: _Socket) -> f24._ChannelConnection:
    return f24._ChannelConnection(
        ENDPOINT,
        role,
        channel,
        f"rx:{channel}",
        "fixture server channel",
        socket,
        1000.0,
        STATUS,
        {"badp": "0", "is_local_channel": str(channel)},
        DIGEST,
        [],
    )


def _full_msg(channel: int = 7) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=1000"
    ).encode("ascii")


def test_gate_authorises_only_the_offline_receipt_implementation() -> None:
    assessment = f258.assess_gate_f2_5_8()

    assert f258.PARENT_GATE_COMMIT == "bf2179396c2b8d90caa98ff23ad55f15f87bf10a"
    assert assessment.exit is f258.F258Exit.ORDERED_WIRE_RECEIPT_IMPLEMENTED
    assert assessment.receipt_implementation_complete
    assert assessment.ordered_field_receipts
    assert assessment.explicit_channel_identity
    assert assessment.configuration_after_remote_prerequisites
    assert assessment.first_iq_hashed_before_decode
    assert assessment.termination_classes_separate
    assert not assessment.live_execution_authorised


def test_failed_prior_gate_blocks_implementation_and_live() -> None:
    prior = replace(
        f257.assess_gate_f2_5_7(),
        exit=f257.F257Exit.PROTOCOL_WITNESS_INCOMPLETE,
        receipt_implementation_authorised=False,
    )

    assessment = f258.assess_gate_f2_5_8(prior)

    assert assessment.exit is f258.F258Exit.SERVER_WIRE_PREREQUISITE_FAILED
    assert not assessment.receipt_implementation_complete
    assert not assessment.live_execution_authorised


def test_ready_branch_waits_for_remote_prerequisites_and_hashes_before_decode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_snd = b"SNDsynthetic-iq"
    socket = _Socket([_full_msg(7), raw_snd])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)
    hashed_before_decode = False
    original = f258._EphemeralWireHasher.observe_before_analysis

    def observe(self: f258._EphemeralWireHasher, raw: bytes) -> str:
        nonlocal hashed_before_decode
        if raw == raw_snd:
            hashed_before_decode = True
        return original(self, raw)

    def decode(body: bytes, sample_rate: float, _arrival: datetime) -> kiwi.IQBlock:
        assert hashed_before_decode
        assert body == b"synthetic-iq"
        assert sample_rate == 1000.0
        return _block()

    monkeypatch.setattr(f258._EphemeralWireHasher, "observe_before_analysis", observe)
    monkeypatch.setattr(f258.kiwi, "_decode_iq_block", decode)

    result = f258._open_channel_ordered(
        ENDPOINT,
        "reference",
        10_000_000.0,
        STATUS,
        f2.MotherPlan(),
    )

    assert result.connection is not None
    receipt = result.receipt
    assert receipt.state is f258.F258BranchState.READY
    assert receipt.wire_assessment.state is f257.BranchWireState.WIRE_READY
    assert result.connection.channel_id == "rx:7"
    assert result.connection.channel_id_basis == (
        "server is_local channel number observed before mod_iq"
    )
    kinds = [event.kind for event in receipt.transcript.events]
    assert kinds.index(f257.WireEventKind.BADP_OK_OBSERVED) < kinds.index(
        f257.WireEventKind.MOD_IQ_SENT
    )
    assert kinds.index(f257.WireEventKind.CHANNEL_ALLOCATED_OBSERVED) < kinds.index(
        f257.WireEventKind.MOD_IQ_SENT
    )
    assert kinds.index(f257.WireEventKind.SAMPLE_RATE_OBSERVED) < kinds.index(
        f257.WireEventKind.MOD_IQ_SENT
    )
    assert kinds[-1] is f257.WireEventKind.IQ_FRAME_OBSERVED
    assert receipt.readiness_frame_artifact_hash == sha256(raw_snd).hexdigest()
    assert receipt.incoming_frame_count == 2
    assert receipt.raw_rf_persistence == "ZERO"
    result.connection.close()


def test_sample_and_channel_without_badp_never_send_mod_iq(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_payload = (1000).to_bytes(2, "big") + b"normal"
    socket = _Socket(
        [
            b"MSG is_local=7,0,0 sample_rate=1000",
            (websocket.ABNF.OPCODE_CLOSE, close_payload),
        ]
    )
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan()
    )

    assert result.connection is None
    assert result.receipt.state is f258.F258BranchState.QUALIFICATION_ERROR
    assert not any(command.startswith("SET mod=") for command in socket.sent)
    assert result.receipt.transcript.events[-1].kind is (
        f257.WireEventKind.WEBSOCKET_CLOSE_OBSERVED
    )
    assert result.receipt.transcript.events[-1].close_code == 1000


@pytest.mark.parametrize(
    "message",
    [b"MSG badp=5", b"MSG too_busy=8"],
)
def test_explicit_server_refusal_is_capability_rejected_without_configuration(
    monkeypatch: pytest.MonkeyPatch,
    message: bytes,
) -> None:
    socket = _Socket([message])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "perturbed", 10_000_000.0, STATUS, f2.MotherPlan()
    )

    assert result.receipt.state is f258.F258BranchState.CAPABILITY_REJECTED
    assert result.receipt.wire_assessment.state is f257.BranchWireState.SERVER_REJECTED
    assert not any(command.startswith("SET mod=") for command in socket.sent)


def test_malformed_server_field_is_qualification_error_not_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket([b"MSG badp=NaN"])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan()
    )

    assert result.receipt.state is f258.F258BranchState.QUALIFICATION_ERROR
    assert result.receipt.error_type == "ValueError"


def test_local_mod_send_error_is_ordered_and_not_remote_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket([_full_msg()], fail_send_prefix="SET mod=")
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan()
    )

    assert result.receipt.state is f258.F258BranchState.QUALIFICATION_ERROR
    assert result.receipt.error_type == "ConnectionError"
    assert result.receipt.transcript.events[-1].kind is (
        f257.WireEventKind.LOCAL_SEND_ERROR_OBSERVED
    )
    assert result.receipt.wire_assessment.state is (
        f257.BranchWireState.TERMINATED_WITHOUT_IQ
    )


def test_transport_loss_without_close_frame_stays_distinct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket([ConnectionError("synthetic TCP loss")])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan()
    )

    terminal = result.receipt.transcript.events[-1]
    assert terminal.kind is f257.WireEventKind.TRANSPORT_LOSS_OBSERVED
    assert terminal.error_type == "ConnectionError"
    assert terminal.close_code is None


def test_receive_timeout_is_not_renamed_transport_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket([websocket.WebSocketTimeoutException("synthetic timeout")])
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan()
    )

    terminal = result.receipt.transcript.events[-1]
    assert terminal.kind is f257.WireEventKind.CONTROL_TIMEOUT_OBSERVED
    assert terminal.error_type == "WebSocketTimeoutException"


def test_unknown_msg_value_is_hashed_then_destroyed_not_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    socket = _Socket(
        [
            b"MSG unknown=do-not-retain badp=5",
        ]
    )
    monkeypatch.setattr(websocket, "create_connection", lambda *_args, **_kwargs: socket)

    result = f258._open_channel_ordered(
        ENDPOINT, "reference", 10_000_000.0, STATUS, f2.MotherPlan()
    )
    encoded = json.dumps(strict_json_value(result.receipt), allow_nan=False)

    assert "do-not-retain" not in encoded
    assert result.receipt.incoming_frame_count == 1
    assert result.receipt.incoming_frame_artifact_hashes


def test_dual_composition_requires_distinct_server_channel_numbers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets = {role: _Socket([]) for role in ("reference", "perturbed")}
    results = {
        role: f258._BranchOpenResult(
            _connection(role, channel, sockets[role]),
            _ready_receipt(role, channel),
        )
        for role, channel in (("reference", 3), ("perturbed", 6))
    }
    monkeypatch.setattr(
        f258,
        "_open_channel_ordered",
        lambda _endpoint, role, *_args: results[role],
    )

    dual, receipts = f258._open_dual_ordered(
        ENDPOINT, 10_000_000.0, STATUS, f2.MotherPlan()
    )

    assert dual.reference.channel_id == "rx:3"
    assert dual.perturbed.channel_id == "rx:6"
    assert all(
        receipt.pair_disposition is f252.PairDisposition.ADMITTED_TO_PAIR
        for receipt in receipts
    )
    dual.close()


def test_same_server_channel_closes_both_and_refuses_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sockets = {role: _Socket([]) for role in ("reference", "perturbed")}
    results = {
        role: f258._BranchOpenResult(
            _connection(role, 3, sockets[role]),
            _ready_receipt(role, 3),
        )
        for role in ("reference", "perturbed")
    }
    monkeypatch.setattr(
        f258,
        "_open_channel_ordered",
        lambda _endpoint, role, *_args: results[role],
    )

    with pytest.raises(f258.OrderedDualOpenError) as caught:
        f258._open_dual_ordered(ENDPOINT, 10_000_000.0, STATUS, f2.MotherPlan())

    assert all(socket.closed for socket in sockets.values())
    assert all(
        receipt.pair_disposition
        is f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION
        for receipt in caught.value.receipts
    )


def test_receipt_schema_has_hashes_not_rf_or_credentials() -> None:
    fields = set(f258.F258BranchReceipt.__dataclass_fields__)

    assert not {
        "samples",
        "iq_samples",
        "raw_frames",
        "waterfall",
        "password",
        "raw_msg",
        "raw_command",
    } & fields
    encoded = json.dumps(
        strict_json_value(_ready_receipt("reference", 3)),
        allow_nan=False,
        sort_keys=True,
    )
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_module_has_no_import_time_io_cli_or_automatic_live_run() -> None:
    source = Path(f258.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]

    assert top_level_calls == []
    assert "if __name__" not in source
    assert "def run_live" not in source
    assert "urlopen" not in source
