"""Gate F2.5.8: ordered server-wire receipt integration, offline-reviewed.

The functions in this module are a disposable successor to the frozen F2.5.2
branch opener. Tests drive them with synthetic WebSocket frames. Importing and
assessing the gate perform no network activity; there is deliberately no live
runner or command-line entry point.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import math
import struct
import time

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_2 as f252
from . import kiwi_gate_f2_5_7 as f257
from . import kiwi_probe as kiwi


F258_TRANSFORM_VERSION = "gate-f2.5.8-ordered-wire-receipt-integration-v1"
PARENT_GATE_COMMIT = "bf2179396c2b8d90caa98ff23ad55f15f87bf10a"
BRANCH_ROLES = ("reference", "perturbed")
RAW_RF_PERSISTENCE = "ZERO"


class F258Exit(str, Enum):
    ORDERED_WIRE_RECEIPT_IMPLEMENTED = "ORDERED_WIRE_RECEIPT_IMPLEMENTED"
    SERVER_WIRE_PREREQUISITE_FAILED = "SERVER_WIRE_PREREQUISITE_FAILED"


class F258BranchState(str, Enum):
    READY = "READY"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class _ObservedWebSocketClose(RuntimeError):
    pass


class BranchCapabilityRejected(RuntimeError):
    """An explicit badp/too_busy response, never inferred from exception prose."""


@dataclass(slots=True)
class _EphemeralWireHasher:
    digest: object
    frame_count: int = 0
    raw_bytes: int = 0
    frame_hashes: list[str] | None = None

    @classmethod
    def create(cls) -> "_EphemeralWireHasher":
        return cls(sha256(), frame_hashes=[])

    def observe_before_analysis(self, raw_frame: bytes) -> str:
        frame_hash = sha256(raw_frame).hexdigest()
        self.digest.update(len(raw_frame).to_bytes(8, "big"))  # type: ignore[attr-defined]
        self.digest.update(raw_frame)  # type: ignore[attr-defined]
        self.frame_count += 1
        self.raw_bytes += len(raw_frame)
        assert self.frame_hashes is not None
        self.frame_hashes.append(frame_hash)
        return frame_hash

    @property
    def stream_hash(self) -> str | None:
        return self.digest.hexdigest() if self.frame_count else None  # type: ignore[attr-defined]


@dataclass(slots=True)
class _WireRecorder:
    role: str
    events: list[f257.WireEvent]
    incoming: _EphemeralWireHasher
    command_hashes: list[str]

    @classmethod
    def create(cls, role: str) -> "_WireRecorder":
        return cls(role, [], _EphemeralWireHasher.create(), [])

    def add(self, kind: f257.WireEventKind, **kwargs: object) -> None:
        self.events.append(
            f257.WireEvent(
                self.role,
                len(self.events),
                time.monotonic_ns(),
                kind,
                **kwargs,
            )
        )

    def transcript(self) -> f257.WireTranscript | None:
        if not self.events:
            return None
        return f257.WireTranscript(self.role, tuple(self.events))


@dataclass(frozen=True, slots=True)
class F258BranchReceipt:
    endpoint_identity: str
    role: str
    state: F258BranchState
    started_at: datetime
    completed_at: datetime
    transcript: f257.WireTranscript | None
    wire_assessment: f257.BranchWireAssessment | None
    incoming_frame_count: int
    incoming_raw_bytes: int
    incoming_stream_artifact_hash: str | None
    incoming_frame_artifact_hashes: tuple[str, ...]
    local_command_hashes: tuple[str, ...]
    readiness_frame_artifact_hash: str | None
    readiness_event_start: datetime | None
    readiness_event_end: datetime | None
    readiness_sequence: int | None
    readiness_gps_solution_age_s: int | None
    error_type: str | None
    error_description_hash: str | None
    pair_disposition: f252.PairDisposition
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F258_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if self.role not in BRANCH_ROLES:
            raise ValueError("ordered branch receipt requires one frozen role")
        if f2._utc(self.completed_at) < f2._utc(self.started_at):
            raise ValueError("ordered branch receipt time runs backwards")
        if self.incoming_frame_count != len(self.incoming_frame_artifact_hashes):
            raise ValueError("every incoming frame must have one pre-analysis hash")
        if self.incoming_frame_count == 0:
            if self.incoming_raw_bytes or self.incoming_stream_artifact_hash is not None:
                raise ValueError("empty wire receipt cannot claim an incoming artifact")
        elif self.incoming_raw_bytes <= 0 or self.incoming_stream_artifact_hash is None:
            raise ValueError("incoming wire frames require bytes and stream hash")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("RF persistence is forbidden")
        for digest in (
            *self.incoming_frame_artifact_hashes,
            *self.local_command_hashes,
            self.incoming_stream_artifact_hash,
            self.readiness_frame_artifact_hash,
            self.error_description_hash,
        ):
            if digest is not None and not f257.SHA256_PATTERN.fullmatch(digest):
                raise ValueError("ordered receipt artifacts require SHA-256")

        readiness = (
            self.readiness_frame_artifact_hash,
            self.readiness_event_start,
            self.readiness_event_end,
            self.readiness_sequence,
            self.readiness_gps_solution_age_s,
        )
        if self.state is F258BranchState.READY:
            if (
                self.transcript is None
                or self.wire_assessment is None
                or self.wire_assessment.state is not f257.BranchWireState.WIRE_READY
                or not all(value is not None for value in readiness)
                or self.error_type is not None
                or self.error_description_hash is not None
            ):
                raise ValueError("READY requires the complete ordered IQ witness chain")
            if f2._utc(self.readiness_event_end) < f2._utc(self.readiness_event_start):  # type: ignore[arg-type]
                raise ValueError("readiness event time runs backwards")
        else:
            if self.error_type is None or self.error_description_hash is None:
                raise ValueError("failed ordered branch requires a typed description")
            if any(value is not None for value in readiness):
                raise ValueError("failed ordered branch cannot claim IQ readiness")
            if self.pair_disposition is f252.PairDisposition.ADMITTED_TO_PAIR:
                raise ValueError("failed ordered branch cannot enter a pair")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(slots=True)
class _BranchOpenResult:
    connection: f24._ChannelConnection | None
    receipt: F258BranchReceipt


class OrderedDualOpenError(RuntimeError):
    def __init__(self, receipts: tuple[F258BranchReceipt, F258BranchReceipt], reason: str):
        self.receipts = receipts
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class F258Assessment:
    exit: F258Exit
    server_wire_prerequisite_satisfied: bool
    ordered_field_receipts: bool
    explicit_channel_identity: bool
    configuration_after_remote_prerequisites: bool
    first_iq_hashed_before_decode: bool
    termination_classes_separate: bool
    receipt_implementation_complete: bool
    live_execution_authorised: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


def _endpoint_identity(endpoint: kiwi.KiwiEndpoint) -> str:
    return f"{endpoint.host.lower()}:{endpoint.port}"


def _command_hash(command: str) -> str:
    return sha256(command.encode("utf-8")).hexdigest()


def _send_command(
    ws: object,
    command: str,
    recorder: _WireRecorder,
    *,
    receipt_command: str | None = None,
    event: f257.WireEventKind | None = None,
) -> None:
    try:
        ws.send(command)  # type: ignore[attr-defined]
    except Exception as error:
        recorder.add(
            f257.WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
            error_type=type(error).__name__,
        )
        raise
    recorder.command_hashes.append(_command_hash(receipt_command or command))
    if event is not None:
        recorder.add(event)


def _receive_data_frame(
    ws: object,
    recorder: _WireRecorder,
    websocket_module: object,
) -> bytes | None:
    opcode, frame = ws.recv_data_frame(control_frame=True)  # type: ignore[attr-defined]
    data = frame.data
    if opcode == websocket_module.ABNF.OPCODE_CLOSE:  # type: ignore[attr-defined]
        payload = bytes(data or b"")
        artifact_hash = recorder.incoming.observe_before_analysis(b"CLOSE" + payload)
        close_code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else 1005
        recorder.add(
            f257.WireEventKind.WEBSOCKET_CLOSE_OBSERVED,
            close_code=close_code,
            artifact_hash=artifact_hash,
        )
        raise _ObservedWebSocketClose(f"server sent WebSocket close code {close_code}")
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


def _map_server_fields(
    fields: tuple[f257.DecodedServerField, ...],
    recorder: _WireRecorder,
) -> None:
    for field in fields:
        if field.name == "badp":
            if field.state == "OK":
                recorder.add(f257.WireEventKind.BADP_OK_OBSERVED)
            else:
                recorder.add(
                    f257.WireEventKind.BADP_REJECTION_OBSERVED,
                    numeric_value=field.numeric_value,
                )
        elif field.name == "too_busy":
            recorder.add(
                f257.WireEventKind.TOO_BUSY_OBSERVED,
                numeric_value=field.numeric_value,
            )
        elif field.name == "is_local":
            recorder.add(
                f257.WireEventKind.CHANNEL_ALLOCATED_OBSERVED,
                channel_id=field.channel_id,
            )
        elif field.name == "audio_rate":
            recorder.add(
                f257.WireEventKind.AUDIO_RATE_OBSERVED,
                numeric_value=field.numeric_value,
            )
        elif field.name == "sample_rate":
            recorder.add(
                f257.WireEventKind.SAMPLE_RATE_OBSERVED,
                numeric_value=field.numeric_value,
            )


def _first_event(
    recorder: _WireRecorder,
    kind: f257.WireEventKind,
) -> f257.WireEvent | None:
    return next((event for event in recorder.events if event.kind is kind), None)


def _remote_prerequisites(recorder: _WireRecorder) -> bool:
    required = {
        f257.WireEventKind.BADP_OK_OBSERVED,
        f257.WireEventKind.CHANNEL_ALLOCATED_OBSERVED,
        f257.WireEventKind.SAMPLE_RATE_OBSERVED,
    }
    return required <= {event.kind for event in recorder.events}


def _terminal_recorded(recorder: _WireRecorder) -> bool:
    terminals = {
        f257.WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
        f257.WireEventKind.CONTROL_TIMEOUT_OBSERVED,
        f257.WireEventKind.WEBSOCKET_CLOSE_OBSERVED,
        f257.WireEventKind.TRANSPORT_LOSS_OBSERVED,
    }
    return bool(terminals & {event.kind for event in recorder.events})


def _is_transport_loss(error: Exception) -> bool:
    return isinstance(error, (ConnectionError, OSError)) or type(error).__name__ in {
        "WebSocketConnectionClosedException",
        "WebSocketProtocolException",
    }


def _failure_receipt(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    started: datetime,
    recorder: _WireRecorder,
    error: Exception,
) -> F258BranchReceipt:
    transcript = recorder.transcript()
    assessment = f257.assess_branch_wire(transcript) if transcript is not None else None
    description = {
        "endpoint": _endpoint_identity(endpoint),
        "role": role,
        "operation": "ordered_snd_branch_open",
        "error_type": type(error).__name__,
        "wire_state": assessment.state.value if assessment else "NO_WEBSOCKET_TRANSCRIPT",
    }
    return F258BranchReceipt(
        _endpoint_identity(endpoint),
        role,
        (
            F258BranchState.CAPABILITY_REJECTED
            if isinstance(error, BranchCapabilityRejected)
            else F258BranchState.QUALIFICATION_ERROR
        ),
        started,
        datetime.now(timezone.utc),
        transcript,
        assessment,
        recorder.incoming.frame_count,
        recorder.incoming.raw_bytes,
        recorder.incoming.stream_hash,
        tuple(recorder.incoming.frame_hashes or ()),
        tuple(recorder.command_hashes),
        None,
        None,
        None,
        None,
        None,
        type(error).__name__,
        f2._hash(description),
        f252.PairDisposition.CLOSED_ON_BRANCH_FAILURE,
    )


def _open_channel_ordered(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
) -> _BranchOpenResult:
    """Open one branch while preserving the server-defined causal order."""

    import websocket

    if role not in BRANCH_ROLES:
        raise ValueError("ordered SND opener requires a frozen branch role")
    started = datetime.now(timezone.utc)
    recorder = _WireRecorder.create(role)
    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, role))) & 0xFFFFFFFF
    ws: object | None = None
    sanitized_handshake: dict[str, str | None] = {}
    configured = False
    try:
        ws = websocket.create_connection(
            f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
            timeout=8.0,
            origin=f"http://{endpoint.host}:{endpoint.port}",
            http_proxy_host=None,
            enable_multithread=True,
        )
        recorder.add(f257.WireEventKind.WEBSOCKET_OPENED)
        _send_command(
            ws,
            "SET auth t=kiwi p=",
            recorder,
            receipt_command="SET auth t=kiwi p=<redacted>",
            event=f257.WireEventKind.AUTH_SENT_REDACTED,
        )
        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            message = _receive_data_frame(ws, recorder, websocket)
            if message is None or len(message) < 3:
                continue
            arrival = datetime.now(timezone.utc)
            tag, body = message[:3], message[3:]
            if tag == b"MSG":
                raw_frame = tag + body
                recorder.incoming.observe_before_analysis(raw_frame)
                fields = f257.decode_allowlisted_server_fields(
                    body[1:].decode("ascii", errors="replace")
                )
                _map_server_fields(fields, recorder)
                for field in fields:
                    if field.name == "badp":
                        sanitized_handshake["badp"] = str(int(field.numeric_value or 0.0))
                    elif field.name == "is_local":
                        sanitized_handshake["is_local_channel"] = str(field.channel_id)
                    elif field.numeric_value is not None:
                        sanitized_handshake[field.name] = str(field.numeric_value)
                badp_rejection = next(
                    (field for field in fields if field.name == "badp" and field.state != "OK"),
                    None,
                )
                too_busy = next((field for field in fields if field.name == "too_busy"), None)
                if badp_rejection is not None:
                    raise BranchCapabilityRejected(
                        f"server reported badp={int(badp_rejection.numeric_value or -1)}"
                    )
                if too_busy is not None:
                    raise BranchCapabilityRejected("server reported too_busy")
                audio_rate = next(
                    (field.numeric_value for field in fields if field.name == "audio_rate"),
                    None,
                )
                if audio_rate is not None:
                    _send_command(
                        ws,
                        f"SET AR OK in={int(audio_rate)} out=44100",
                        recorder,
                    )
                if _remote_prerequisites(recorder) and not configured:
                    for command in f24._initial_channel_commands(center_hz):
                        _send_command(
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
                raw_frame = tag + body
                frame_hash = recorder.incoming.observe_before_analysis(raw_frame)
                sample_event = _first_event(
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
                        artifact_hash=frame_hash,
                        sequence=block.sequence,
                    )
                    transcript = recorder.transcript()
                    assert transcript is not None
                    assessment = f257.assess_branch_wire(transcript)
                    if assessment.state is not f257.BranchWireState.WIRE_READY:
                        raise RuntimeError("ordered transcript did not reach WIRE_READY")
                    channel_event = _first_event(
                        recorder, f257.WireEventKind.CHANNEL_ALLOCATED_OBSERVED
                    )
                    assert channel_event is not None and channel_event.channel_id is not None
                    channel_id = f"rx:{channel_event.channel_id}"
                    receipt = F258BranchReceipt(
                        _endpoint_identity(endpoint),
                        role,
                        F258BranchState.READY,
                        started,
                        datetime.now(timezone.utc),
                        transcript,
                        assessment,
                        recorder.incoming.frame_count,
                        recorder.incoming.raw_bytes,
                        recorder.incoming.stream_hash,
                        tuple(recorder.incoming.frame_hashes or ()),
                        tuple(recorder.command_hashes),
                        frame_hash,
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
                    return _BranchOpenResult(connection, receipt)
            _send_command(ws, "SET keepalive", recorder)
        timeout = TimeoutError("ordered SND control deadline expired")
        recorder.add(
            f257.WireEventKind.CONTROL_TIMEOUT_OBSERVED,
            error_type=type(timeout).__name__,
        )
        raise timeout
    except Exception as error:
        if not _terminal_recorded(recorder):
            if type(error).__name__ == "WebSocketTimeoutException":
                recorder.add(
                    f257.WireEventKind.CONTROL_TIMEOUT_OBSERVED,
                    error_type=type(error).__name__,
                )
            elif _is_transport_loss(error):
                recorder.add(
                    f257.WireEventKind.TRANSPORT_LOSS_OBSERVED,
                    error_type=type(error).__name__,
                )
        if ws is not None:
            try:
                ws.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        return _BranchOpenResult(
            None,
            _failure_receipt(endpoint, role, started, recorder, error),
        )


def _open_dual_ordered(
    endpoint: kiwi.KiwiEndpoint,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
) -> tuple[f24._DualConnections, tuple[F258BranchReceipt, F258BranchReceipt]]:
    """Compose only two complete, distinct ordered server-wire branches."""

    results: dict[str, _BranchOpenResult] = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            role: pool.submit(
                _open_channel_ordered,
                endpoint,
                role,
                center_hz,
                status,
                mother,
            )
            for role in BRANCH_ROLES
        }
        for role in BRANCH_ROLES:
            results[role] = futures[role].result()

    receipts = tuple(results[role].receipt for role in BRANCH_ROLES)
    connections = tuple(results[role].connection for role in BRANCH_ROLES)
    if any(connection is None for connection in connections):
        adjusted: list[F258BranchReceipt] = []
        for connection, receipt in zip(connections, receipts):
            if connection is not None:
                connection.close()
                receipt = replace(
                    receipt,
                    pair_disposition=f252.PairDisposition.CLOSED_AFTER_PEER_FAILURE,
                )
            adjusted.append(receipt)
        raise OrderedDualOpenError(tuple(adjusted), "ordered dual-SND branch failed")  # type: ignore[arg-type]

    reference, perturbed = connections
    assert reference is not None and perturbed is not None
    pair = f257.assess_pair_wire(receipts[0].transcript, receipts[1].transcript)  # type: ignore[arg-type]
    if pair.state is not f257.PairWireState.DUAL_WIRE_READY:
        reference.close()
        perturbed.close()
        rejected = tuple(
            replace(
                receipt,
                pair_disposition=f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION,
            )
            for receipt in receipts
        )
        raise OrderedDualOpenError(rejected, pair.statement)  # type: ignore[arg-type]
    admitted = tuple(
        replace(receipt, pair_disposition=f252.PairDisposition.ADMITTED_TO_PAIR)
        for receipt in receipts
    )
    return f24._DualConnections(reference, perturbed), admitted  # type: ignore[return-value]


def assess_gate_f2_5_8(
    prerequisite: f257.F257Assessment | None = None,
) -> F258Assessment:
    prior = prerequisite or f257.assess_gate_f2_5_7()
    ready = (
        prior.exit is f257.F257Exit.SERVER_WIRE_CONTRACT_SUFFICIENT
        and prior.receipt_implementation_authorised
    )
    return F258Assessment(
        F258Exit.ORDERED_WIRE_RECEIPT_IMPLEMENTED
        if ready
        else F258Exit.SERVER_WIRE_PREREQUISITE_FAILED,
        ready,
        ready,
        ready,
        ready,
        ready,
        ready,
        ready,
        False,
        (
            "the offline successor preserves ordered allowlisted server fields",
            "mod_iq is delayed until badp=0, is_local channel and sample_rate are observed",
            "the first qualifying IQ frame is hashed before decode",
            "local send error, control timeout, WebSocket close and transport loss remain distinct",
        )
        if ready
        else ("the server-wire prerequisite failed closed",),
        (
            "the server acknowledged a configuration command",
            "the runtime has been exercised against a live endpoint",
            "the frozen historical closures have been reclassified",
            "a new live execution is authorised",
        ),
    )
