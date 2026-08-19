"""Gate F2.5.17: phase-aware direct-SND control, offline only.

The old opener emitted a keepalive after every inbound control frame.  The
pinned server counts those commands and may classify an incompletely configured
SND connection as hung after the fifth one.  This successor waits for every
rate/allocation prerequisite, emits the exact required setup once, and only
then permits a time-paced keepalive.

The module has no connector default and no live entry point.  It retains local
send evidence separately from remote observations; local setup emission is not
represented as a server acknowledgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
import struct
import time
from typing import Callable, Sequence

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_2 as f252
from . import kiwi_gate_f2_5_7 as f257
from . import kiwi_gate_f2_5_8 as f258
from . import kiwi_gate_f2_5_12 as f2512
from . import kiwi_gate_f2_5_13 as f2513
from . import kiwi_probe as kiwi


F2517_TRANSFORM_VERSION = "gate-f2.5.17-phase-aware-snd-control-v1"
PARENT_GATE_COMMIT = "8cef46abe0e18528a9e1653401939c9c28b5e1c0"
PINNED_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
PINNED_HEADER_SHA256 = (
    "351e40f6a10940ad9239e99bd1d62b406d93d7dd50b8a8f7cd2974f76b549b64"
)
RAW_RF_PERSISTENCE = "ZERO"
CONTROL_TIMEOUT_S = 12.0
KEEPALIVE_INTERVAL_S = 1.0

CMD_FREQ = 0x01
CMD_MODE = 0x02
CMD_PASSBAND = 0x04
CMD_AGC = 0x08
CMD_AR_OK = 0x10
CMD_SND_ALL = CMD_FREQ | CMD_MODE | CMD_PASSBAND | CMD_AGC | CMD_AR_OK


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


PINNED_HEADER_PATH = (
    _repository_root()
    / "experiments"
    / "live_instrument"
    / "protocol_sources"
    / "gate_f2_5_17"
    / "rx_sound_cmd.h"
)
PINNED_MANIFEST_PATH = PINNED_HEADER_PATH.with_name("manifest.json")


class ControlPhase(str, Enum):
    AUTH_EMITTED_LOCAL = "AUTH_EMITTED_LOCAL"
    REQUIRED_METADATA_OBSERVED = "REQUIRED_METADATA_OBSERVED"
    REQUIRED_SETUP_EMITTED_LOCAL = "REQUIRED_SETUP_EMITTED_LOCAL"
    PERIODIC_KEEPALIVE_EMITTED_LOCAL = "PERIODIC_KEEPALIVE_EMITTED_LOCAL"
    FIRST_SND_READY_OBSERVED = "FIRST_SND_READY_OBSERVED"
    TERMINATED_BEFORE_READINESS = "TERMINATED_BEFORE_READINESS"


class F2517Exit(str, Enum):
    PHASE_AWARE_SND_CONTROL_MATERIALIZED_OFFLINE = (
        "PHASE_AWARE_SND_CONTROL_MATERIALIZED_OFFLINE"
    )


@dataclass(frozen=True, slots=True)
class ControlTransition:
    ordinal: int
    phase: ControlPhase
    elapsed_s: float
    local_command_hashes: tuple[str, ...]
    trigger_frame_artifact_hash: str | None

    def __post_init__(self) -> None:
        if self.ordinal < 0 or not math.isfinite(self.elapsed_s) or self.elapsed_s < 0.0:
            raise ValueError("control transition time and ordinal must be finite and non-negative")
        for digest in (*self.local_command_hashes, self.trigger_frame_artifact_hash):
            if digest is not None and (
                len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            ):
                raise ValueError("control transition artifacts require SHA-256")
        command_phases = {
            ControlPhase.AUTH_EMITTED_LOCAL,
            ControlPhase.REQUIRED_SETUP_EMITTED_LOCAL,
            ControlPhase.PERIODIC_KEEPALIVE_EMITTED_LOCAL,
        }
        if self.phase in command_phases and not self.local_command_hashes:
            raise ValueError("local command phases require command hashes")
        if self.phase not in command_phases and self.local_command_hashes:
            raise ValueError("remote/terminal phases cannot claim local commands")


@dataclass(frozen=True, slots=True)
class PinnedGuardSimulation:
    final_setup_mask: int
    keepalive_count: int
    setup_complete_command_index: int | None
    first_guard_exposure_command_index: int | None

    @property
    def setup_complete(self) -> bool:
        return self.final_setup_mask == CMD_SND_ALL

    @property
    def guard_exposed(self) -> bool:
        return self.first_guard_exposure_command_index is not None


@dataclass(frozen=True, slots=True)
class PhaseAwareBranchReceipt:
    integrated_receipt: f2513.IntegratedBranchReceipt
    transitions: tuple[ControlTransition, ...]
    control_plan_hash: str
    exact_required_setup_bits: tuple[str, ...]
    local_setup_emission_clause: f2512.ClauseEvaluation
    remote_setup_acknowledgement_clause: f2512.ClauseEvaluation
    pre_setup_keepalive_count: int
    post_setup_keepalive_count: int
    minimum_observed_keepalive_spacing_s: float | None
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2517_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if tuple(item.ordinal for item in self.transitions) != tuple(
            range(len(self.transitions))
        ):
            raise ValueError("control transitions must have contiguous ordinals")
        times = tuple(item.elapsed_s for item in self.transitions)
        if any(later < earlier for earlier, later in zip(times, times[1:])):
            raise ValueError("control transition time runs backwards")
        if not self.transitions or self.transitions[0].phase is not (
            ControlPhase.AUTH_EMITTED_LOCAL
        ):
            raise ValueError("phase-aware receipt must begin with local auth emission")
        setup = tuple(
            item
            for item in self.transitions
            if item.phase is ControlPhase.REQUIRED_SETUP_EMITTED_LOCAL
        )
        if len(setup) > 1:
            raise ValueError("required SND setup may be emitted only once")
        if self.pre_setup_keepalive_count != 0:
            raise ValueError("keepalive before local setup completion is forbidden")
        keepalives = tuple(
            item
            for item in self.transitions
            if item.phase is ControlPhase.PERIODIC_KEEPALIVE_EMITTED_LOCAL
        )
        if self.post_setup_keepalive_count != len(keepalives):
            raise ValueError("post-setup keepalive count diverges from transitions")
        if keepalives and not setup:
            raise ValueError("periodic liveness cannot precede local setup completion")
        if setup and keepalives and keepalives[0].ordinal < setup[0].ordinal:
            raise ValueError("periodic liveness must follow the setup transition")
        if len(keepalives) >= 2:
            spacing = min(
                later.elapsed_s - earlier.elapsed_s
                for earlier, later in zip(keepalives, keepalives[1:])
            )
            if self.minimum_observed_keepalive_spacing_s is None or not math.isclose(
                self.minimum_observed_keepalive_spacing_s, spacing, abs_tol=1e-9
            ):
                raise ValueError("keepalive spacing does not match the control ledger")
            if spacing < KEEPALIVE_INTERVAL_S:
                raise ValueError("keepalive cadence is faster than the frozen interval")
        elif self.minimum_observed_keepalive_spacing_s is not None:
            raise ValueError("spacing requires at least two keepalive transitions")
        if self.remote_setup_acknowledgement_clause is not (
            f2512.ClauseEvaluation.NOT_EVALUATED
        ):
            raise ValueError("this protocol exposes no remote setup acknowledgement")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.control_plan_hash != control_plan_hash():
            raise ValueError("phase-aware control plan changed")
        if self.exact_required_setup_bits != (
            "CMD_FREQ",
            "CMD_MODE",
            "CMD_PASSBAND",
            "CMD_AGC",
            "CMD_AR_OK",
        ):
            raise ValueError("pinned CMD_SND_ALL definition changed")
        ready = self.integrated_receipt.state is f258.F258BranchState.READY
        ready_phase = tuple(
            item
            for item in self.transitions
            if item.phase is ControlPhase.FIRST_SND_READY_OBSERVED
        )
        if ready and (len(setup) != 1 or len(ready_phase) != 1):
            raise ValueError("READY requires local setup and one observed SND readiness")
        if ready and self.local_setup_emission_clause is not (
            f2512.ClauseEvaluation.SATISFIED
        ):
            raise ValueError("READY requires satisfied local setup emission")
        if not ready and ready_phase:
            raise ValueError("failed branch cannot contain SND readiness")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(self)


@dataclass(slots=True)
class PhaseAwareOpenResult:
    connection: f24._ChannelConnection | None
    receipt: PhaseAwareBranchReceipt


@dataclass(frozen=True, slots=True)
class F2517Assessment:
    exit: F2517Exit
    pinned_header_hash_matches: bool
    cmd_snd_all_exactly_defined: bool
    frozen_failed_schedule_exceeded_guard: bool
    corrected_schedule_avoids_guard: bool
    keepalive_is_phase_and_time_gated: bool
    local_send_is_separate_from_remote_acknowledgement: bool
    connector_injection_required: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


def _command_hash(command: str) -> str:
    return sha256(command.encode("utf-8")).hexdigest()


def control_plan_hash() -> str:
    return f2._hash(
        {
            "version": F2517_TRANSFORM_VERSION,
            "parent": PARENT_GATE_COMMIT,
            "pinned_server_commit": PINNED_SERVER_COMMIT,
            "pinned_header_sha256": PINNED_HEADER_SHA256,
            "required_setup_mask": CMD_SND_ALL,
            "control_timeout_s": CONTROL_TIMEOUT_S,
            "keepalive_interval_s": KEEPALIVE_INTERVAL_S,
            "keepalive_gate": "AFTER_REQUIRED_SETUP_EMITTED_LOCAL_ONLY",
            "remote_setup_acknowledgement": "NOT_EXPOSED",
            "raw_rf_persistence": RAW_RF_PERSISTENCE,
        }
    )


def _header_is_exact() -> bool:
    if sha256(PINNED_HEADER_PATH.read_bytes()).hexdigest() != PINNED_HEADER_SHA256:
        return False
    text = PINNED_HEADER_PATH.read_text(encoding="utf-8")
    required = (
        "#define CMD_FREQ\t\t0x01",
        "#define CMD_MODE\t\t0x02",
        "#define CMD_PASSBAND\t0x04",
        "#define CMD_AGC\t\t\t0x08",
        "#define\tCMD_AR_OK\t\t0x10",
        "#define\tCMD_SND_ALL     (CMD_FREQ | CMD_MODE | CMD_PASSBAND | CMD_AGC | CMD_AR_OK)",
    )
    manifest = json.loads(PINNED_MANIFEST_PATH.read_text(encoding="utf-8"))
    return (
        all(item in text for item in required)
        and manifest["commit"] == PINNED_SERVER_COMMIT
        and manifest["sha256"] == PINNED_HEADER_SHA256
    )


def setup_commands(center_hz: float, audio_rate_hz: float) -> tuple[str, ...]:
    """Return the immutable one-shot setup with no liveness command."""

    if not math.isfinite(center_hz) or center_hz <= 0.0:
        raise ValueError("center frequency must be positive and finite")
    if not math.isfinite(audio_rate_hz) or audio_rate_hz <= 0.0:
        raise ValueError("audio rate must be positive and finite")
    commands = (
        f"SET AR OK in={int(audio_rate_hz)} out=44100",
        *tuple(
            command
            for command in f24._initial_channel_commands(center_hz)
            if command != "SET keepalive"
        ),
    )
    if "SET keepalive" in commands:
        raise RuntimeError("liveness command re-entered required setup")
    if len(commands) != len(set(commands)):
        raise RuntimeError("required setup contains a duplicate command")
    return commands


def validate_setup_commands(
    commands: Sequence[str], center_hz: float, audio_rate_hz: float
) -> None:
    if tuple(commands) != setup_commands(center_hz, audio_rate_hz):
        raise ValueError("setup commands were reordered, duplicated or modified")


def simulate_pinned_guard(commands: Sequence[str]) -> PinnedGuardSimulation:
    """Apply only the retained CMD_SND_ALL/keepalive guard semantics."""

    mask = 0
    keepalive_count = 0
    setup_complete_at: int | None = None
    guard_exposed_at: int | None = None
    for index, command in enumerate(commands):
        if command.startswith("SET mod="):
            mask |= CMD_FREQ | CMD_MODE | CMD_PASSBAND
        elif command.startswith("SET agc="):
            mask |= CMD_AGC
        elif command.startswith("SET AR OK "):
            mask |= CMD_AR_OK
        elif command == "SET keepalive":
            keepalive_count += 1
        if mask == CMD_SND_ALL and setup_complete_at is None:
            setup_complete_at = index
        if (
            keepalive_count > 4
            and mask != CMD_SND_ALL
            and guard_exposed_at is None
        ):
            guard_exposed_at = index
    return PinnedGuardSimulation(
        mask,
        keepalive_count,
        setup_complete_at,
        guard_exposed_at,
    )


def _record_transition(
    transitions: list[ControlTransition],
    phase: ControlPhase,
    started_mono: float,
    *,
    command_hashes: tuple[str, ...] = (),
    trigger_hash: str | None = None,
    now_mono: float | None = None,
) -> None:
    observed_mono = time.monotonic() if now_mono is None else now_mono
    transitions.append(
        ControlTransition(
            len(transitions),
            phase,
            max(0.0, observed_mono - started_mono),
            command_hashes,
            trigger_hash,
        )
    )


def _open_channel_phase_aware(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
    *,
    connector: Callable[..., object],
    websocket_module: object,
    semantic_frames: list[f2512.SemanticFrameReceipt],
    transitions: list[ControlTransition],
) -> f258._BranchOpenResult:
    if role not in f258.BRANCH_ROLES:
        raise ValueError("phase-aware SND opener requires one frozen branch role")
    if not _header_is_exact():
        raise RuntimeError("pinned CMD_SND_ALL header verification failed")

    started = datetime.now(timezone.utc)
    started_mono = time.monotonic()
    recorder = f258._WireRecorder.create(role)
    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, role))) & 0xFFFFFFFF
    ws: object | None = None
    sanitized_handshake: dict[str, str | None] = {}
    configured = False
    last_keepalive_mono: float | None = None
    try:
        ws = connector(
            f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
            timeout=8.0,
            origin=f"http://{endpoint.host}:{endpoint.port}",
            http_proxy_host=None,
            enable_multithread=True,
        )
        recorder.add(f257.WireEventKind.WEBSOCKET_OPENED)
        before = len(recorder.command_hashes)
        f258._send_command(
            ws,
            "SET auth t=kiwi p=",
            recorder,
            receipt_command="SET auth t=kiwi p=<redacted>",
            event=f257.WireEventKind.AUTH_SENT_REDACTED,
        )
        _record_transition(
            transitions,
            ControlPhase.AUTH_EMITTED_LOCAL,
            started_mono,
            command_hashes=tuple(recorder.command_hashes[before:]),
        )

        deadline = time.monotonic() + CONTROL_TIMEOUT_S
        while time.monotonic() < deadline:
            message = f2513._receive_data_frame_semantic(
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

                audio_event = f258._first_event(
                    recorder, f257.WireEventKind.AUDIO_RATE_OBSERVED
                )
                if (
                    not configured
                    and audio_event is not None
                    and f258._remote_prerequisites(recorder)
                ):
                    _record_transition(
                        transitions,
                        ControlPhase.REQUIRED_METADATA_OBSERVED,
                        started_mono,
                        trigger_hash=wire_hash,
                    )
                    commands = setup_commands(center_hz, float(audio_event.numeric_value))
                    validate_setup_commands(
                        commands, center_hz, float(audio_event.numeric_value)
                    )
                    before = len(recorder.command_hashes)
                    for command in commands:
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
                    last_keepalive_mono = time.monotonic()
                    _record_transition(
                        transitions,
                        ControlPhase.REQUIRED_SETUP_EMITTED_LOCAL,
                        started_mono,
                        command_hashes=tuple(recorder.command_hashes[before:]),
                        trigger_hash=wire_hash,
                        now_mono=last_keepalive_mono,
                    )
            elif tag == b"SND":
                sample_event = f258._first_event(
                    recorder, f257.WireEventKind.SAMPLE_RATE_OBSERVED
                )
                if sample_event is None or not configured:
                    raise RuntimeError("SND frame preceded the complete local setup")
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
                    _record_transition(
                        transitions,
                        ControlPhase.FIRST_SND_READY_OBSERVED,
                        started_mono,
                        trigger_hash=wire_hash,
                    )
                    transcript = recorder.transcript()
                    assert transcript is not None
                    assessment = f257.assess_branch_wire(transcript)
                    if assessment.state is not f257.BranchWireState.WIRE_READY:
                        raise RuntimeError("phase-aware transcript did not reach WIRE_READY")
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
                        "server is_local channel number observed before phase-aware mod_iq",
                        ws,
                        sample_rate,
                        status,
                        sanitized_handshake,
                        f2._hash(sanitized_handshake),
                        [],
                    )
                    return f258._BranchOpenResult(connection, receipt)

            now_mono = time.monotonic()
            if (
                configured
                and last_keepalive_mono is not None
                and now_mono - last_keepalive_mono >= KEEPALIVE_INTERVAL_S
            ):
                before = len(recorder.command_hashes)
                f258._send_command(ws, "SET keepalive", recorder)
                _record_transition(
                    transitions,
                    ControlPhase.PERIODIC_KEEPALIVE_EMITTED_LOCAL,
                    started_mono,
                    command_hashes=tuple(recorder.command_hashes[before:]),
                    now_mono=now_mono,
                )
                last_keepalive_mono = now_mono

        timeout = TimeoutError("phase-aware SND control deadline expired")
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
        _record_transition(
            transitions,
            ControlPhase.TERMINATED_BEFORE_READINESS,
            started_mono,
            trigger_hash=(
                semantic_frames[-1].artifact_hash if semantic_frames else None
            ),
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


def _phase_receipt(
    integrated: f2513.IntegratedBranchReceipt,
    transitions: tuple[ControlTransition, ...],
) -> PhaseAwareBranchReceipt:
    setup = tuple(
        item
        for item in transitions
        if item.phase is ControlPhase.REQUIRED_SETUP_EMITTED_LOCAL
    )
    keepalives = tuple(
        item
        for item in transitions
        if item.phase is ControlPhase.PERIODIC_KEEPALIVE_EMITTED_LOCAL
    )
    spacing = (
        min(
            later.elapsed_s - earlier.elapsed_s
            for earlier, later in zip(keepalives, keepalives[1:])
        )
        if len(keepalives) >= 2
        else None
    )
    setup_clause = (
        f2512.ClauseEvaluation.SATISFIED
        if setup
        else f2512.ClauseEvaluation.QUALIFICATION_ERROR
        if "LOCAL_SEND_ERROR_OBSERVED" in integrated.control_event_kinds
        else f2512.ClauseEvaluation.NOT_EVALUATED
    )
    return PhaseAwareBranchReceipt(
        integrated,
        transitions,
        control_plan_hash(),
        ("CMD_FREQ", "CMD_MODE", "CMD_PASSBAND", "CMD_AGC", "CMD_AR_OK"),
        setup_clause,
        f2512.ClauseEvaluation.NOT_EVALUATED,
        0,
        len(keepalives),
        spacing,
    )


def open_channel_phase_aware_injected(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
    *,
    connector: Callable[..., object],
    websocket_module: object,
) -> PhaseAwareOpenResult:
    """Run one phase-aware branch only through an injected connector."""

    semantic_frames: list[f2512.SemanticFrameReceipt] = []
    transitions: list[ControlTransition] = []
    result = _open_channel_phase_aware(
        endpoint,
        role,
        center_hz,
        status,
        mother,
        connector=connector,
        websocket_module=websocket_module,
        semantic_frames=semantic_frames,
        transitions=transitions,
    )
    integrated = f2513._integrate_receipt(result.receipt, tuple(semantic_frames))
    return PhaseAwareOpenResult(
        result.connection,
        _phase_receipt(integrated, tuple(transitions)),
    )


def assess_gate_f2_5_17() -> F2517Assessment:
    old_commands = (
        *f24._initial_channel_commands(10_000_000.0),
        *("SET keepalive",) * 14,
        "SET AR OK in=12000 out=44100",
    )
    corrected = (
        *setup_commands(10_000_000.0, 12_000.0),
        *("SET keepalive",) * 6,
    )
    old = simulate_pinned_guard(old_commands)
    new = simulate_pinned_guard(corrected)
    return F2517Assessment(
        F2517Exit.PHASE_AWARE_SND_CONTROL_MATERIALIZED_OFFLINE,
        sha256(PINNED_HEADER_PATH.read_bytes()).hexdigest() == PINNED_HEADER_SHA256,
        _header_is_exact() and CMD_SND_ALL == 0x1F,
        old.guard_exposed,
        new.setup_complete and not new.guard_exposed,
        True,
        True,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )
