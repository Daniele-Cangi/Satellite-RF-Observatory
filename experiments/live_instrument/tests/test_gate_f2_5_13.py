"""Synthetic-socket integration tests for Gate F2.5.13."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
import struct

import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5_8 as f258
from experiments.live_instrument import kiwi_gate_f2_5_12 as f2512
from experiments.live_instrument import kiwi_gate_f2_5_13 as f2513
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)
STATUS = {"name": "fixture"}


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(self, frames: list[bytes | tuple[int, bytes] | Exception]) -> None:
        self.frames = list(frames)
        self.sent: list[str] = []
        self.closed = False

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


class _Connector:
    def __init__(self, socket: _Socket):
        self.socket = socket
        self.calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def __call__(self, *args: object, **kwargs: object) -> _Socket:
        self.calls.append((args, kwargs))
        return self.socket


def _full_msg(channel: int = 7) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=12000"
    ).encode("ascii")


def _snd_message(
    *,
    flags: int = 0x08,
    sequence: int = 17,
    gps_age_s: int = 5,
    gps_seconds: int = 100_000,
    sample_bytes: bytes | None = None,
) -> bytes:
    if sample_bytes is None:
        sample_bytes = struct.pack(">hhhh", 100, -100, 200, -200)
    return b"SND" + (
        struct.pack("<BI", flags, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", gps_age_s, 0, gps_seconds, 250_000_000)
        + sample_bytes
    )


def _close(payload: bytes = b"") -> tuple[int, bytes]:
    return websocket.ABNF.OPCODE_CLOSE, payload


def _open(socket: _Socket) -> tuple[f2513.IntegratedOpenResult, _Connector]:
    connector = _Connector(socket)
    result = f2513.open_channel_semantic_injected(
        ENDPOINT,
        "reference",
        10_000_000.0,
        STATUS,
        f2.MotherPlan(),
        connector=connector,
        websocket_module=websocket,
    )
    return result, connector


def test_ready_snd_is_bound_to_the_ordered_control_path() -> None:
    msg = _full_msg(7)
    snd = _snd_message(sequence=23)
    socket = _Socket([msg, snd])
    result, connector = _open(socket)
    receipt = result.receipt

    assert len(connector.calls) == 1
    assert result.connection is not None
    assert receipt.state is f258.F258BranchState.READY
    assert receipt.observed_channel_id == 7
    assert receipt.incoming_frame_count == 2
    assert tuple(item.artifact_hash for item in receipt.semantic_frame_receipts) == (
        sha256(msg).hexdigest(),
        sha256(snd).hexdigest(),
    )
    assert receipt.readiness_frame_artifact_hash == sha256(snd).hexdigest()
    assert receipt.readiness_sequence == 23
    assert receipt.semantic_frame_receipts[-1].readiness_clause is (
        f2512.ClauseEvaluation.SATISFIED
    )
    assert "MOD_IQ_SENT" in receipt.control_event_kinds
    assert any(command.startswith("SET mod=iq ") for command in socket.sent)
    result.connection.close()


def test_no_snd_and_stale_snd_remain_distinct_after_ordered_integration() -> None:
    without_snd, _ = _open(_Socket([_full_msg(), _close()]))
    with_stale, _ = _open(
        _Socket([_full_msg(), _snd_message(gps_age_s=31), _close()])
    )

    no_snd_frames = tuple(
        item
        for item in without_snd.receipt.semantic_frame_receipts
        if item.frame_class is f2512.FrameClass.SND
    )
    stale_frames = tuple(
        item
        for item in with_stale.receipt.semantic_frame_receipts
        if item.frame_class is f2512.FrameClass.SND
    )
    assert no_snd_frames == ()
    assert len(stale_frames) == 1
    assert stale_frames[0].gps_age_within_limit_clause is (
        f2512.ClauseEvaluation.UNSATISFIED
    )
    assert stale_frames[0].readiness_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert without_snd.receipt.state is f258.F258BranchState.QUALIFICATION_ERROR
    assert with_stale.receipt.state is f258.F258BranchState.QUALIFICATION_ERROR


def test_missing_gps_seconds_survives_the_opener_as_its_own_clause() -> None:
    result, _ = _open(
        _Socket([_full_msg(), _snd_message(gps_seconds=0), _close()])
    )
    snd = next(
        item
        for item in result.receipt.semantic_frame_receipts
        if item.frame_class is f2512.FrameClass.SND
    )

    assert snd.gps_seconds_present_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert snd.gps_age_within_limit_clause is f2512.ClauseEvaluation.SATISFIED
    assert snd.readiness_clause is f2512.ClauseEvaluation.UNSATISFIED


def test_empty_close_omits_the_legacy_local_1005_from_integrated_json() -> None:
    result, _ = _open(_Socket([_full_msg(), _close()]))
    receipt = result.receipt
    encoded = json.dumps(strict_json_value(receipt), allow_nan=False, sort_keys=True)

    assert receipt.close_payload_state is f2512.ClosePayloadState.EMPTY_NO_STATUS
    assert receipt.peer_close_status_code is None
    assert "1005" not in encoded
    assert "EMPTY_NO_STATUS" in encoded
    assert receipt.error_type == "_ObservedWebSocketClose"


def test_real_peer_close_status_is_preserved_without_local_substitution() -> None:
    payload = struct.pack(">H", 1000) + b"normal"
    result, _ = _open(_Socket([_full_msg(), _close(payload)]))

    assert result.receipt.close_payload_state is f2512.ClosePayloadState.STATUS_PRESENT
    assert result.receipt.peer_close_status_code == 1000


def test_decode_failure_remains_qualification_error_and_not_rejection() -> None:
    result, _ = _open(
        _Socket([_full_msg(), _snd_message(sample_bytes=b"\x01")])
    )
    receipt = result.receipt
    snd = receipt.semantic_frame_receipts[-1]

    assert receipt.state is f258.F258BranchState.QUALIFICATION_ERROR
    assert receipt.error_type == "ValueError"
    assert snd.sample_decode_clause is f2512.ClauseEvaluation.QUALIFICATION_ERROR
    assert snd.readiness_clause is f2512.ClauseEvaluation.NOT_EVALUATED


def test_non_iq_snd_preserves_physical_clause_despite_legacy_typed_stop() -> None:
    result, _ = _open(_Socket([_full_msg(), _snd_message(flags=0)]))
    snd = result.receipt.semantic_frame_receipts[-1]

    assert result.receipt.state is f258.F258BranchState.QUALIFICATION_ERROR
    assert result.receipt.state is not f258.F258BranchState.CAPABILITY_REJECTED
    assert snd.iq_mode_clause is f2512.ClauseEvaluation.UNSATISFIED
    assert snd.sample_decode_clause is f2512.ClauseEvaluation.NOT_EVALUATED
    assert snd.readiness_clause is f2512.ClauseEvaluation.UNSATISFIED


def test_explicit_badp_remains_the_only_capability_rejection() -> None:
    result, _ = _open(_Socket([b"MSG badp=5"]))

    assert result.receipt.state is f258.F258BranchState.CAPABILITY_REJECTED
    assert "BADP_REJECTION_OBSERVED" in result.receipt.control_event_kinds
    assert result.receipt.semantic_frame_receipts[0].frame_class is f2512.FrameClass.MSG


def test_unknown_msg_content_is_not_exposed_by_the_integrated_receipt() -> None:
    secret = b"MSG unknown=do-not-retain badp=5"
    result, _ = _open(_Socket([secret]))
    encoded = json.dumps(strict_json_value(result.receipt), allow_nan=False)

    assert "do-not-retain" not in encoded
    assert result.receipt.semantic_frame_receipts[0].artifact_hash == sha256(secret).hexdigest()
    assert result.receipt.raw_rf_persistence == "ZERO"


def test_injected_connector_is_mandatory_and_no_live_entry_point_exists() -> None:
    signature = inspect.signature(f2513.open_channel_semantic_injected)
    source = inspect.getsource(f2513)

    assert signature.parameters["connector"].default is inspect.Parameter.empty
    assert signature.parameters["websocket_module"].default is inspect.Parameter.empty
    with pytest.raises(TypeError, match="connector"):
        f2513.open_channel_semantic_injected(
            ENDPOINT,
            "reference",
            10_000_000.0,
            STATUS,
            f2.MotherPlan(),
        )
    assert "create_connection" not in source
    assert "import websocket" not in source
    assert not hasattr(f2513, "run")
    assert not hasattr(f2513, "main")


def test_gate_assessment_stops_before_live_authority() -> None:
    assessment = f2513.assess_gate_f2_5_13()

    assert assessment.exit is (
        f2513.F2513Exit.SEMANTIC_ORDERED_OPENER_INTEGRATED_OFFLINE
    )
    assert assessment.connector_injection_required
    assert assessment.semantic_hashes_match_ordered_hashes
    assert assessment.empty_close_has_no_peer_status
    assert assessment.frozen_default_path_preserved
    assert assessment.raw_rf_persistence == "ZERO"
    assert not assessment.live_execution_authorised
