"""Gate F2.5.13: inject semantic receipts into the ordered opener, offline.

The integration entry point has no connector default.  Tests must inject a
synthetic socket factory; this module cannot select or open a live endpoint by
itself.  The legacy F2.5.8 receipt remains an internal compatibility result and
is reduced to a hash plus allowlisted control facts at the new boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import math
import struct
import time
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_2 as f252
from . import kiwi_gate_f2_5_7 as f257
from . import kiwi_gate_f2_5_8 as f258
from . import kiwi_gate_f2_5_12 as f2512
from . import kiwi_probe as kiwi


F2513_TRANSFORM_VERSION = "gate-f2.5.13-injected-semantic-ordered-opener-v1"
PARENT_GATE_COMMIT = "1737f5b0dbc13c6ccec30e69255a1febc320e858"
RAW_RF_PERSISTENCE = "ZERO"


class F2513Exit(str, Enum):
    SEMANTIC_ORDERED_OPENER_INTEGRATED_OFFLINE = (
        "SEMANTIC_ORDERED_OPENER_INTEGRATED_OFFLINE"
    )


@dataclass(frozen=True, slots=True)
class F2513Assessment:
    exit: F2513Exit
    connector_injection_required: bool
    semantic_hashes_match_ordered_hashes: bool
    empty_close_has_no_peer_status: bool
    frozen_default_path_preserved: bool
    raw_rf_persistence: str
    live_execution_authorised: bool


@dataclass(frozen=True, slots=True)
class IntegratedBranchReceipt:
    endpoint_identity: str
    role: str
    state: f258.F258BranchState
    started_at: datetime
    completed_at: datetime
    control_event_kinds: tuple[str, ...]
    observed_channel_id: int | None
    semantic_frame_receipts: tuple[f2512.SemanticFrameReceipt, ...]
    incoming_frame_count: int
    local_command_hashes: tuple[str, ...]
    readiness_frame_artifact_hash: str | None
    readiness_event_start: datetime | None
    readiness_event_end: datetime | None
    readiness_sequence: int | None
    readiness_gps_solution_age_s: int | None
    close_payload_state: f2512.ClosePayloadState
    peer_close_status_code: int | None
    error_type: str | None
    error_description_hash: str | None
    pair_disposition: f252.PairDisposition
    ordered_receipt_hash: str
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2513_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if self.role not in {"reference", "perturbed"}:
            raise ValueError("integrated receipt requires one frozen branch role")
        if self.incoming_frame_count != len(self.semantic_frame_receipts):
            raise ValueError("every retained frame hash requires one semantic transition")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("RF persistence is forbidden")
        for digest in (
            self.ordered_receipt_hash,
            *self.local_command_hashes,
            self.readiness_frame_artifact_hash,
            self.error_description_hash,
        ):
            if digest is not None and (
                len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError("integrated receipt artifacts require SHA-256")

        close_receipts = tuple(
            receipt
            for receipt in self.semantic_frame_receipts
            if receipt.frame_class is f2512.FrameClass.CLOSE
        )
        if close_receipts:
            close = close_receipts[-1]
            if self.close_payload_state is not close.close_payload_state:
                raise ValueError("integrated close state must come from the semantic frame")
            if self.peer_close_status_code != close.peer_close_status_code:
                raise ValueError("integrated peer status must come from the semantic frame")
        elif (
            self.close_payload_state is not f2512.ClosePayloadState.NOT_APPLICABLE
            or self.peer_close_status_code is not None
        ):
            raise ValueError("receipt cannot claim an unobserved close")

        ready_frames = tuple(
            receipt
            for receipt in self.semantic_frame_receipts
            if receipt.readiness_clause is f2512.ClauseEvaluation.SATISFIED
        )
        readiness = (
            self.readiness_frame_artifact_hash,
            self.readiness_event_start,
            self.readiness_event_end,
            self.readiness_sequence,
            self.readiness_gps_solution_age_s,
        )
        if self.state is f258.F258BranchState.READY:
            if len(ready_frames) != 1 or any(value is None for value in readiness):
                raise ValueError("READY requires one matching semantic readiness frame")
            ready = ready_frames[0]
            if (
                self.readiness_frame_artifact_hash != ready.artifact_hash
                or self.readiness_event_start != ready.readiness_event_start
                or self.readiness_event_end != ready.readiness_event_end
                or self.readiness_sequence != ready.sequence
                or self.readiness_gps_solution_age_s != ready.gps_solution_age_s
            ):
                raise ValueError("ordered and semantic readiness facts diverged")
            if self.error_type is not None or self.error_description_hash is not None:
                raise ValueError("READY cannot contain a descriptive failure")
        else:
            if ready_frames or any(value is not None for value in readiness):
                raise ValueError("failed integrated branch cannot claim readiness")
            if self.error_type is None or self.error_description_hash is None:
                raise ValueError("failed integrated branch requires a typed description")

        if self.state is f258.F258BranchState.CAPABILITY_REJECTED:
            rejection_events = {
                f257.WireEventKind.BADP_REJECTION_OBSERVED.value,
                f257.WireEventKind.TOO_BUSY_OBSERVED.value,
            }
            if not rejection_events.intersection(self.control_event_kinds):
                raise ValueError("capability rejection requires an explicit control refusal")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(self)


@dataclass(slots=True)
class IntegratedOpenResult:
    connection: f24._ChannelConnection | None
    receipt: IntegratedBranchReceipt


def _receive_data_frame_semantic(
    ws: object,
    recorder: f258._WireRecorder,
    websocket_module: object,
    semantic_frames: list[f2512.SemanticFrameReceipt],
) -> bytes | None:
    opcode, frame = ws.recv_data_frame(control_frame=True)  # type: ignore[attr-defined]
    data = frame.data
    if opcode == websocket_module.ABNF.OPCODE_CLOSE:  # type: ignore[attr-defined]
        payload = bytes(data or b"")
        artifact_hash = recorder.incoming.observe_before_analysis(b"CLOSE" + payload)
        semantic = f2512.observe_close_frame(payload)
        if semantic.artifact_hash != artifact_hash:
            raise RuntimeError("close artifact hash diverged across receipt layers")
        semantic_frames.append(semantic)
        # The legacy internal transcript requires an integer. It is never
        # exposed by IntegratedBranchReceipt; semantic close state is canonical.
        legacy_close_code = (
            struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 1005
        )
        recorder.add(
            f257.WireEventKind.WEBSOCKET_CLOSE_OBSERVED,
            close_code=legacy_close_code,
            artifact_hash=artifact_hash,
        )
        raise f258._ObservedWebSocketClose(
            "peer close observed; status semantics are in the frame receipt"
        )
    if opcode not in {
        websocket_module.ABNF.OPCODE_TEXT,  # type: ignore[attr-defined]
        websocket_module.ABNF.OPCODE_BINARY,  # type: ignore[attr-defined]
    }:
        return None
    if isinstance(data, str):
        return data.encode("latin-1")
    if isinstance(data, (bytes, bytearray, memoryview)):
        return bytes(data)
    raise TypeError("WebSocket data frame has an unsupported payload type")


def _open_channel_ordered_semantic(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
    *,
    connector: Callable[..., object],
    websocket_module: object,
    semantic_frames: list[f2512.SemanticFrameReceipt],
) -> f258._BranchOpenResult:
    """Successor opener; the frozen F2.5.8 source remains untouched."""

    if role not in f258.BRANCH_ROLES:
        raise ValueError("ordered SND opener requires one frozen branch role")
    started = datetime.now(timezone.utc)
    recorder = f258._WireRecorder.create(role)
    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, role))) & 0xFFFFFFFF
    ws: object | None = None
    sanitized_handshake: dict[str, str | None] = {}
    configured = False
    try:
        ws = connector(
            f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
            timeout=8.0,
            origin=f"http://{endpoint.host}:{endpoint.port}",
            http_proxy_host=None,
            enable_multithread=True,
        )
        recorder.add(f257.WireEventKind.WEBSOCKET_OPENED)
        f258._send_command(
            ws,
            "SET auth t=kiwi p=",
            recorder,
            receipt_command="SET auth t=kiwi p=<redacted>",
            event=f257.WireEventKind.AUTH_SENT_REDACTED,
        )
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            message = _receive_data_frame_semantic(
                ws,
                recorder,
                websocket_module,
                semantic_frames,
            )
            if message is None:
                continue
            arrival = datetime.now(timezone.utc)
            wire_hash = recorder.incoming.observe_before_analysis(message)
            sample_event = f258._first_event(
                recorder, f257.WireEventKind.SAMPLE_RATE_OBSERVED
            )
            semantic = f2512.observe_data_frame(
                message,
                sample_rate_hz=(
                    float(sample_event.numeric_value)
                    if sample_event is not None
                    else math.nan
                ),
                arrival=arrival,
            )
            if semantic.artifact_hash != wire_hash:
                raise RuntimeError("data artifact hash diverged across receipt layers")
            semantic_frames.append(semantic)
            if len(message) < 3:
                continue

            tag, body = message[:3], message[3:]
            if tag == b"MSG":
                fields = f257.decode_allowlisted_server_fields(
                    body[1:].decode("ascii", errors="replace")
                )
                f258._map_server_fields(fields, recorder)
                for field in fields:
                    if field.name == "badp":
                        sanitized_handshake["badp"] = str(
                            int(field.numeric_value or 0.0)
                        )
                    elif field.name == "is_local":
                        sanitized_handshake["is_local_channel"] = str(field.channel_id)
                    elif field.numeric_value is not None:
                        sanitized_handshake[field.name] = str(field.numeric_value)
                badp_rejection = next(
                    (
                        field
                        for field in fields
                        if field.name == "badp" and field.state != "OK"
                    ),
                    None,
                )
                too_busy = next(
                    (field for field in fields if field.name == "too_busy"), None
                )
                if badp_rejection is not None:
                    raise f258.BranchCapabilityRejected(
                        f"server reported badp={int(badp_rejection.numeric_value or -1)}"
                    )
                if too_busy is not None:
                    raise f258.BranchCapabilityRejected("server reported too_busy")
                audio_rate = next(
                    (
                        field.numeric_value
                        for field in fields
                        if field.name == "audio_rate"
                    ),
                    None,
                )
                if audio_rate is not None:
                    f258._send_command(
                        ws,
                        f"SET AR OK in={int(audio_rate)} out=44100",
                        recorder,
                    )
                if f258._remote_prerequisites(recorder) and not configured:
                    for command in f24._initial_channel_commands(center_hz):
                        f258._send_command(
                            ws,
                            command,
                            recorder,
                            event=(
                                f257.WireEventKind.MOD_IQ_SENT
                                if command.startswith("SET mod=")
                                else None
                            ),
                        )
                    configured = True
            elif tag == b"SND":
                sample_event = f258._first_event(
                    recorder, f257.WireEventKind.SAMPLE_RATE_OBSERVED
                )
                if sample_event is None or not configured:
                    raise RuntimeError("SND frame preceded the complete ordered setup")
                sample_rate = float(sample_event.numeric_value)
                block = kiwi._decode_iq_block(body, sample_rate, arrival)
                if (
                    block.gps_timestamp_available
                    and block.gps_solution_age_s <= mother.maximum_gps_solution_age_s
                ):
                    recorder.add(
                        f257.WireEventKind.IQ_FRAME_OBSERVED,
                        artifact_hash=wire_hash,
                        sequence=block.sequence,
                    )
                    transcript = recorder.transcript()
                    assert transcript is not None
                    assessment = f257.assess_branch_wire(transcript)
                    if assessment.state is not f257.BranchWireState.WIRE_READY:
                        raise RuntimeError("ordered transcript did not reach WIRE_READY")
                    channel_event = f258._first_event(
                        recorder, f257.WireEventKind.CHANNEL_ALLOCATED_OBSERVED
                    )
                    assert channel_event is not None and channel_event.channel_id is not None
                    channel_id = f"rx:{channel_event.channel_id}"
                    receipt = f258.F258BranchReceipt(
                        f258._endpoint_identity(endpoint),
                        role,
                        f258.F258BranchState.READY,
                        started,
                        datetime.now(timezone.utc),
                        transcript,
                        assessment,
                        recorder.incoming.frame_count,
                        recorder.incoming.raw_bytes,
                        recorder.incoming.stream_hash,
                        tuple(recorder.incoming.frame_hashes or ()),
                        tuple(recorder.command_hashes),
                        wire_hash,
                        block.event_start,
                        block.event_end,
                        block.sequence,
                        block.gps_solution_age_s,
                        None,
                        None,
                        f252.PairDisposition.BRANCH_READY_UNCOMPOSED,
                    )
                    del block
                    connection = f24._ChannelConnection(
                        endpoint,
                        role,
                        token,
                        channel_id,
                        "server is_local channel number observed before mod_iq",
                        ws,
                        sample_rate,
                        status,
                        sanitized_handshake,
                        f2._hash(sanitized_handshake),
                        [],
                    )
                    return f258._BranchOpenResult(connection, receipt)
            f258._send_command(ws, "SET keepalive", recorder)

        timeout = TimeoutError("ordered SND control deadline expired")
        recorder.add(
            f257.WireEventKind.CONTROL_TIMEOUT_OBSERVED,
            error_type=type(timeout).__name__,
        )
        raise timeout
    except Exception as error:
        if not f258._terminal_recorded(recorder):
            if type(error).__name__ == "WebSocketTimeoutException":
                recorder.add(
                    f257.WireEventKind.CONTROL_TIMEOUT_OBSERVED,
                    error_type=type(error).__name__,
                )
            elif f258._is_transport_loss(error):
                recorder.add(
                    f257.WireEventKind.TRANSPORT_LOSS_OBSERVED,
                    error_type=type(error).__name__,
                )
        if ws is not None:
            try:
                ws.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        return f258._BranchOpenResult(
            None,
            f258._failure_receipt(endpoint, role, started, recorder, error),
        )


def _integrate_receipt(
    ordered: f258.F258BranchReceipt,
    semantic_frames: tuple[f2512.SemanticFrameReceipt, ...],
) -> IntegratedBranchReceipt:
    semantic_hashes = tuple(receipt.artifact_hash for receipt in semantic_frames)
    if semantic_hashes != ordered.incoming_frame_artifact_hashes:
        raise ValueError("ordered and semantic frame hashes diverged")

    events = ordered.transcript.events if ordered.transcript is not None else ()
    control_event_kinds = tuple(event.kind.value for event in events)
    channel_event = next(
        (
            event
            for event in events
            if event.kind is f257.WireEventKind.CHANNEL_ALLOCATED_OBSERVED
        ),
        None,
    )
    close_receipt = next(
        (
            receipt
            for receipt in reversed(semantic_frames)
            if receipt.frame_class is f2512.FrameClass.CLOSE
        ),
        None,
    )
    return IntegratedBranchReceipt(
        ordered.endpoint_identity,
        ordered.role,
        ordered.state,
        ordered.started_at,
        ordered.completed_at,
        control_event_kinds,
        channel_event.channel_id if channel_event is not None else None,
        semantic_frames,
        len(semantic_frames),
        ordered.local_command_hashes,
        ordered.readiness_frame_artifact_hash,
        ordered.readiness_event_start,
        ordered.readiness_event_end,
        ordered.readiness_sequence,
        ordered.readiness_gps_solution_age_s,
        (
            close_receipt.close_payload_state
            if close_receipt is not None
            else f2512.ClosePayloadState.NOT_APPLICABLE
        ),
        close_receipt.peer_close_status_code if close_receipt is not None else None,
        ordered.error_type,
        ordered.error_description_hash,
        ordered.pair_disposition,
        ordered.receipt_hash,
    )


def open_channel_semantic_injected(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
    *,
    connector: Callable[..., object],
    websocket_module: object,
) -> IntegratedOpenResult:
    """Run the ordered opener only through an explicitly injected connector."""

    semantic_frames: list[f2512.SemanticFrameReceipt] = []
    result = _open_channel_ordered_semantic(
        endpoint,
        role,
        center_hz,
        status,
        mother,
        connector=connector,
        websocket_module=websocket_module,
        semantic_frames=semantic_frames,
    )
    return IntegratedOpenResult(
        result.connection,
        _integrate_receipt(result.receipt, tuple(semantic_frames)),
    )


def assess_gate_f2_5_13() -> F2513Assessment:
    return F2513Assessment(
        F2513Exit.SEMANTIC_ORDERED_OPENER_INTEGRATED_OFFLINE,
        True,
        True,
        True,
        True,
        RAW_RF_PERSISTENCE,
        False,
    )
