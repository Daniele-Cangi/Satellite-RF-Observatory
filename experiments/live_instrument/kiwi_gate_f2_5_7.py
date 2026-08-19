"""Gate F2.5.7: client-source necessity and server-wire contract audit.

This is a gate-specific, offline model of the minimum SND control transcript.
It neither imports nor modifies the live Kiwi runtime.  The purpose is to
decide whether the physical DDC experiment needs a retained official client
implementation, or whether server-defined fields plus observable local sends
and remote IQ witnesses are sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Any, Iterable, Mapping, Sequence

from experiments.live_instrument import kiwi_gate_f2_5_6 as f256


F257_TRANSFORM_VERSION = "gate-f2.5.7-server-wire-necessity-audit-v1"
PARENT_GATE_COMMIT = "9bab5148b830c8a164f096d995e068f2626b1403"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class F257Exit(str, Enum):
    SERVER_WIRE_CONTRACT_SUFFICIENT = "SERVER_WIRE_CONTRACT_SUFFICIENT"
    CLIENT_SOURCE_REQUIRED = "CLIENT_SOURCE_REQUIRED"
    PROTOCOL_WITNESS_INCOMPLETE = "PROTOCOL_WITNESS_INCOMPLETE"


class WireEventKind(str, Enum):
    WEBSOCKET_OPENED = "WEBSOCKET_OPENED"
    AUTH_SENT_REDACTED = "AUTH_SENT_REDACTED"
    BADP_OK_OBSERVED = "BADP_OK_OBSERVED"
    BADP_REJECTION_OBSERVED = "BADP_REJECTION_OBSERVED"
    TOO_BUSY_OBSERVED = "TOO_BUSY_OBSERVED"
    CHANNEL_ALLOCATED_OBSERVED = "CHANNEL_ALLOCATED_OBSERVED"
    AUDIO_RATE_OBSERVED = "AUDIO_RATE_OBSERVED"
    SAMPLE_RATE_OBSERVED = "SAMPLE_RATE_OBSERVED"
    MOD_IQ_SENT = "MOD_IQ_SENT"
    IQ_FRAME_OBSERVED = "IQ_FRAME_OBSERVED"
    LOCAL_SEND_ERROR_OBSERVED = "LOCAL_SEND_ERROR_OBSERVED"
    CONTROL_TIMEOUT_OBSERVED = "CONTROL_TIMEOUT_OBSERVED"
    WEBSOCKET_CLOSE_OBSERVED = "WEBSOCKET_CLOSE_OBSERVED"
    TRANSPORT_LOSS_OBSERVED = "TRANSPORT_LOSS_OBSERVED"


class BranchWireState(str, Enum):
    WIRE_READY = "WIRE_READY"
    SERVER_REJECTED = "SERVER_REJECTED"
    CONTROL_ORDER_INVALID = "CONTROL_ORDER_INVALID"
    TERMINATED_WITHOUT_IQ = "TERMINATED_WITHOUT_IQ"
    WITNESS_INCOMPLETE = "WITNESS_INCOMPLETE"


class PairWireState(str, Enum):
    DUAL_WIRE_READY = "DUAL_WIRE_READY"
    ADMISSIBLE_TOPOLOGY_MISSING = "ADMISSIBLE_TOPOLOGY_MISSING"
    PAIR_SERVER_REJECTED = "PAIR_SERVER_REJECTED"
    PAIR_CONTROL_INVALID = "PAIR_CONTROL_INVALID"
    PAIR_WITNESS_INCOMPLETE = "PAIR_WITNESS_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class ClaimBridge:
    claim: str
    server_findings: tuple[str, ...]
    required_receipt_witnesses: tuple[WireEventKind, ...]
    official_client_source_required: bool
    maximum_authorised_claim: str


@dataclass(frozen=True, slots=True)
class DecodedServerField:
    name: str
    ordinal: int
    state: str
    numeric_value: float | None = None
    channel_id: int | None = None

    def __post_init__(self) -> None:
        if self.ordinal < 0:
            raise ValueError("decoded field ordinal cannot be negative")
        if self.numeric_value is not None and not math.isfinite(self.numeric_value):
            raise ValueError("decoded numeric values must be finite")
        if self.channel_id is not None and self.channel_id < 0:
            raise ValueError("channel identity cannot be negative")


@dataclass(frozen=True, slots=True)
class WireEvent:
    role: str
    ordinal: int
    monotonic_ns: int
    kind: WireEventKind
    numeric_value: float | None = None
    channel_id: int | None = None
    artifact_hash: str | None = None
    sequence: int | None = None
    close_code: int | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        if self.role not in {"reference", "perturbed"}:
            raise ValueError("wire events require a frozen branch role")
        if self.ordinal < 0 or self.monotonic_ns < 0:
            raise ValueError("wire event order and monotonic time cannot be negative")
        if self.numeric_value is not None and not math.isfinite(self.numeric_value):
            raise ValueError("wire numeric values must be finite")
        if self.channel_id is not None and self.channel_id < 0:
            raise ValueError("wire channel identity cannot be negative")
        if self.artifact_hash is not None and not SHA256_PATTERN.fullmatch(
            self.artifact_hash
        ):
            raise ValueError("wire artifacts require SHA-256")
        if self.sequence is not None and self.sequence < 0:
            raise ValueError("IQ sequence cannot be negative")

        if self.kind in {
            WireEventKind.AUDIO_RATE_OBSERVED,
            WireEventKind.SAMPLE_RATE_OBSERVED,
        }:
            if self.numeric_value is None or self.numeric_value <= 0.0:
                raise ValueError("rate observations require a positive finite value")
        elif self.kind is WireEventKind.BADP_REJECTION_OBSERVED:
            if self.numeric_value is None or not 1.0 <= self.numeric_value <= 12.0:
                raise ValueError("badp rejection requires a known non-zero code")
        elif self.kind is WireEventKind.TOO_BUSY_OBSERVED:
            if self.numeric_value is not None and self.numeric_value <= 0.0:
                raise ValueError("too_busy channel count must be positive when present")
        elif self.numeric_value is not None:
            raise ValueError("numeric value is not valid for this wire event")

        if self.kind is WireEventKind.CHANNEL_ALLOCATED_OBSERVED:
            if self.channel_id is None:
                raise ValueError("channel allocation requires the server channel number")
        elif self.channel_id is not None:
            raise ValueError("channel identity is limited to allocation events")

        if self.kind is WireEventKind.IQ_FRAME_OBSERVED:
            if self.artifact_hash is None or self.sequence is None:
                raise ValueError("IQ witness requires pre-decode hash and sequence")
        elif self.kind is WireEventKind.WEBSOCKET_CLOSE_OBSERVED:
            if self.close_code is None or self.artifact_hash is None:
                raise ValueError("WebSocket close requires code and hashed reason")
        elif self.artifact_hash is not None:
            raise ValueError("artifact hash is limited to IQ and close witnesses")

        typed_error_kinds = {
            WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
            WireEventKind.CONTROL_TIMEOUT_OBSERVED,
            WireEventKind.TRANSPORT_LOSS_OBSERVED,
        }
        if self.kind in typed_error_kinds:
            if not self.error_type:
                raise ValueError("control and transport failures require a typed local error")
        elif self.error_type is not None:
            raise ValueError("typed errors are limited to control or transport failures")
        if self.kind is not WireEventKind.IQ_FRAME_OBSERVED and self.sequence is not None:
            raise ValueError("sequence is limited to IQ witnesses")
        if self.kind is not WireEventKind.WEBSOCKET_CLOSE_OBSERVED and self.close_code is not None:
            raise ValueError("close code is limited to WebSocket close")


@dataclass(frozen=True, slots=True)
class WireTranscript:
    role: str
    events: tuple[WireEvent, ...]

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("wire transcript cannot be empty")
        if any(event.role != self.role for event in self.events):
            raise ValueError("wire transcript cannot mix branch roles")
        if tuple(event.ordinal for event in self.events) != tuple(range(len(self.events))):
            raise ValueError("wire ordinals must be contiguous")
        times = tuple(event.monotonic_ns for event in self.events)
        if any(later < earlier for earlier, later in zip(times, times[1:])):
            raise ValueError("wire monotonic time runs backwards")
        if self.events[0].kind is not WireEventKind.WEBSOCKET_OPENED:
            raise ValueError("wire transcript must begin at WebSocket open")
        if len(self.events) < 2 or self.events[1].kind not in {
            WireEventKind.AUTH_SENT_REDACTED,
            WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
        }:
            raise ValueError("auth success or its local send error must follow WebSocket open")
        terminals = {
            WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
            WireEventKind.CONTROL_TIMEOUT_OBSERVED,
            WireEventKind.WEBSOCKET_CLOSE_OBSERVED,
            WireEventKind.TRANSPORT_LOSS_OBSERVED,
        }
        terminal_positions = [
            index for index, event in enumerate(self.events) if event.kind in terminals
        ]
        if terminal_positions and terminal_positions != [len(self.events) - 1]:
            raise ValueError("transport termination must be the final wire event")


@dataclass(frozen=True, slots=True)
class BranchWireAssessment:
    role: str
    state: BranchWireState
    channel_id: int | None
    first_iq_sequence: int | None
    missing_witnesses: tuple[WireEventKind, ...]
    statement: str


@dataclass(frozen=True, slots=True)
class PairWireAssessment:
    state: PairWireState
    reference: BranchWireAssessment
    perturbed: BranchWireAssessment
    statement: str


@dataclass(frozen=True, slots=True)
class F257Assessment:
    exit: F257Exit
    server_source_reproducible: bool
    official_client_source_required: bool
    wire_contract_complete: bool
    receipt_implementation_authorised: bool
    live_execution_authorised: bool
    missing_server_findings: tuple[str, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


def claim_bridges() -> tuple[ClaimBridge, ...]:
    """Return only the Gate F2 claim bridges, not a generic protocol model."""

    return (
        ClaimBridge(
            "control session and server authentication outcome",
            ("AUTH_GATE_ORDER", "BADP_SEMANTICS"),
            (
                WireEventKind.WEBSOCKET_OPENED,
                WireEventKind.AUTH_SENT_REDACTED,
                WireEventKind.BADP_OK_OBSERVED,
                WireEventKind.BADP_REJECTION_OBSERVED,
                WireEventKind.TOO_BUSY_OBSERVED,
            ),
            False,
            "the pinned server accepted auth on this branch",
        ),
        ClaimBridge(
            "a distinct SND channel was allocated",
            ("CHANNEL_ALLOCATION", "CHANNEL_IDENTIFIER_GAP"),
            (WireEventKind.CHANNEL_ALLOCATED_OBSERVED,),
            False,
            "the pinned server reported one receive-channel number",
        ),
        ClaimBridge(
            "the local per-channel IQ command was sent",
            ("PER_CHANNEL_RETUNE",),
            (
                WireEventKind.AUDIO_RATE_OBSERVED,
                WireEventKind.SAMPLE_RATE_OBSERVED,
                WireEventKind.MOD_IQ_SENT,
            ),
            False,
            "the local send returned after addressing the branch; not remote acceptance",
        ),
        ClaimBridge(
            "the configured branch produced an IQ witness",
            ("SND_SETUP_AND_IQ",),
            (WireEventKind.IQ_FRAME_OBSERVED,),
            False,
            "one hashed, sequenced IQ frame arrived after the local IQ command",
        ),
        ClaimBridge(
            "transport termination remained descriptive",
            (),
            (
                WireEventKind.WEBSOCKET_CLOSE_OBSERVED,
                WireEventKind.TRANSPORT_LOSS_OBSERVED,
                WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
                WireEventKind.CONTROL_TIMEOUT_OBSERVED,
            ),
            False,
            "clean close and typed transport loss are distinct receipt alternatives",
        ),
    )


def decode_allowlisted_server_fields(body: str) -> tuple[DecodedServerField, ...]:
    """Decode a synthetic MSG body without retaining raw or unknown values."""

    decoded: list[DecodedServerField] = []
    for ordinal, pair in enumerate(body.split()):
        name, separator, raw_value = pair.partition("=")
        if not separator:
            raw_value = ""
        if name == "badp":
            try:
                code = int(raw_value)
            except ValueError as exc:
                raise ValueError("badp must be an integer") from exc
            if not 0 <= code <= 12:
                raise ValueError("badp is outside the pinned server range")
            decoded.append(
                DecodedServerField(
                    name,
                    ordinal,
                    "OK" if code == 0 else "REJECTED",
                    numeric_value=float(code),
                )
            )
        elif name == "too_busy":
            try:
                channels = int(raw_value)
            except ValueError as exc:
                raise ValueError("too_busy must expose a channel count") from exc
            if channels <= 0:
                raise ValueError("too_busy channel count must be positive")
            decoded.append(
                DecodedServerField(name, ordinal, "PRESENT", float(channels))
            )
        elif name == "is_local":
            parts = raw_value.split(",")
            if len(parts) != 3:
                raise ValueError("is_local must contain channel, locality and exemption")
            try:
                channel, locality, exemption = (int(value) for value in parts)
            except ValueError as exc:
                raise ValueError("is_local components must be integers") from exc
            if channel < 0 or locality not in {0, 1} or exemption not in {0, 1}:
                raise ValueError("is_local components are outside the pinned shape")
            decoded.append(
                DecodedServerField(name, ordinal, "CHANNEL_PRESENT", channel_id=channel)
            )
        elif name in {"audio_rate", "sample_rate"}:
            try:
                rate = float(raw_value)
            except ValueError as exc:
                raise ValueError(f"{name} must be numeric") from exc
            if not math.isfinite(rate) or rate <= 0.0:
                raise ValueError(f"{name} must be positive and finite")
            decoded.append(DecodedServerField(name, ordinal, "POSITIVE_FINITE", rate))
        elif name in {"rx_chans", "chan_no_pwd", "chan_no_pwd_true", "max_camp"}:
            try:
                limit = int(raw_value)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if limit < 0:
                raise ValueError(f"{name} cannot be negative")
            decoded.append(DecodedServerField(name, ordinal, "NONNEGATIVE", float(limit)))
    return tuple(decoded)


def assess_branch_wire(transcript: WireTranscript) -> BranchWireAssessment:
    kinds = tuple(event.kind for event in transcript.events)
    if any(
        kind in {
            WireEventKind.BADP_REJECTION_OBSERVED,
            WireEventKind.TOO_BUSY_OBSERVED,
        }
        for kind in kinds
    ):
        return BranchWireAssessment(
            transcript.role,
            BranchWireState.SERVER_REJECTED,
            None,
            None,
            (),
            "the server emitted an explicit refusal or capacity response",
        )

    required = (
        WireEventKind.BADP_OK_OBSERVED,
        WireEventKind.CHANNEL_ALLOCATED_OBSERVED,
        WireEventKind.SAMPLE_RATE_OBSERVED,
        WireEventKind.MOD_IQ_SENT,
        WireEventKind.IQ_FRAME_OBSERVED,
    )
    missing = tuple(kind for kind in required if kind not in kinds)
    positions = {
        kind: kinds.index(kind)
        for kind in required
        if kind in kinds
    }
    prerequisites = (
        WireEventKind.BADP_OK_OBSERVED,
        WireEventKind.CHANNEL_ALLOCATED_OBSERVED,
        WireEventKind.SAMPLE_RATE_OBSERVED,
    )
    if WireEventKind.MOD_IQ_SENT in positions and any(
        kind not in positions or positions[kind] > positions[WireEventKind.MOD_IQ_SENT]
        for kind in prerequisites
    ):
        return BranchWireAssessment(
            transcript.role,
            BranchWireState.CONTROL_ORDER_INVALID,
            None,
            None,
            missing,
            "the IQ command was sent before all remote auth/channel/rate witnesses",
        )
    if (
        WireEventKind.IQ_FRAME_OBSERVED in positions
        and (
            WireEventKind.MOD_IQ_SENT not in positions
            or positions[WireEventKind.MOD_IQ_SENT]
            > positions[WireEventKind.IQ_FRAME_OBSERVED]
        )
    ):
        return BranchWireAssessment(
            transcript.role,
            BranchWireState.CONTROL_ORDER_INVALID,
            None,
            None,
            missing,
            "an IQ frame cannot witness a later local IQ command",
        )
    if not missing:
        channel_event = next(
            event
            for event in transcript.events
            if event.kind is WireEventKind.CHANNEL_ALLOCATED_OBSERVED
        )
        iq_event = next(
            event
            for event in transcript.events
            if event.kind is WireEventKind.IQ_FRAME_OBSERVED
        )
        return BranchWireAssessment(
            transcript.role,
            BranchWireState.WIRE_READY,
            channel_event.channel_id,
            iq_event.sequence,
            (),
            "auth, channel, rate, local IQ send and later remote IQ are ordered",
        )
    if kinds[-1] in {
        WireEventKind.LOCAL_SEND_ERROR_OBSERVED,
        WireEventKind.CONTROL_TIMEOUT_OBSERVED,
        WireEventKind.WEBSOCKET_CLOSE_OBSERVED,
        WireEventKind.TRANSPORT_LOSS_OBSERVED,
    }:
        return BranchWireAssessment(
            transcript.role,
            BranchWireState.TERMINATED_WITHOUT_IQ,
            None,
            None,
            missing,
            "transport terminated before a complete IQ witness chain",
        )
    return BranchWireAssessment(
        transcript.role,
        BranchWireState.WITNESS_INCOMPLETE,
        None,
        None,
        missing,
        "the transcript ended without all required wire witnesses",
    )


def assess_pair_wire(
    reference: WireTranscript,
    perturbed: WireTranscript,
) -> PairWireAssessment:
    if reference.role != "reference" or perturbed.role != "perturbed":
        raise ValueError("pair assessment requires reference then perturbed")
    left = assess_branch_wire(reference)
    right = assess_branch_wire(perturbed)
    states = {left.state, right.state}
    if BranchWireState.SERVER_REJECTED in states:
        state = PairWireState.PAIR_SERVER_REJECTED
        statement = "at least one branch has an explicit server refusal"
    elif BranchWireState.CONTROL_ORDER_INVALID in states:
        state = PairWireState.PAIR_CONTROL_INVALID
        statement = "at least one branch violates the frozen control ordering"
    elif states == {BranchWireState.WIRE_READY}:
        if left.channel_id == right.channel_id:
            state = PairWireState.ADMISSIBLE_TOPOLOGY_MISSING
            statement = "two ready transcripts report the same server receive channel"
        else:
            state = PairWireState.DUAL_WIRE_READY
            statement = "two ordered IQ branches report distinct server receive channels"
    else:
        state = PairWireState.PAIR_WITNESS_INCOMPLETE
        statement = "one or both branches lack a complete wire witness chain"
    return PairWireAssessment(state, left, right, statement)


def _finding_ids(manifest: Mapping[str, Any]) -> frozenset[str]:
    findings = manifest.get("source_findings")
    if not isinstance(findings, list):
        return frozenset()
    return frozenset(
        item["finding_id"]
        for item in findings
        if isinstance(item, dict) and isinstance(item.get("finding_id"), str)
    )


def assess_gate_f2_5_7(
    *,
    source_assessment: f256.F256Assessment | None = None,
    available_server_findings: Iterable[str] | None = None,
    bridges: Sequence[ClaimBridge] | None = None,
) -> F257Assessment:
    source = source_assessment or f256.assess_gate_f2_5_6()
    selected_bridges = tuple(claim_bridges() if bridges is None else bridges)
    if available_server_findings is None:
        available = _finding_ids(f256.load_manifest_strict())
    else:
        available = frozenset(available_server_findings)
    required_findings = frozenset(
        finding for bridge in selected_bridges for finding in bridge.server_findings
    )
    missing = tuple(sorted(required_findings - available))
    client_required = any(
        bridge.official_client_source_required for bridge in selected_bridges
    )
    witness_union = {
        witness for bridge in selected_bridges for witness in bridge.required_receipt_witnesses
    }
    wire_complete = set(WireEventKind) <= witness_union and not missing

    if not source.server_source_reproducible or missing or not wire_complete:
        exit_state = F257Exit.PROTOCOL_WITNESS_INCOMPLETE
    elif client_required:
        exit_state = F257Exit.CLIENT_SOURCE_REQUIRED
    else:
        exit_state = F257Exit.SERVER_WIRE_CONTRACT_SUFFICIENT
    implementation_authorised = (
        exit_state is F257Exit.SERVER_WIRE_CONTRACT_SUFFICIENT
    )
    return F257Assessment(
        exit=exit_state,
        server_source_reproducible=source.server_source_reproducible,
        official_client_source_required=client_required,
        wire_contract_complete=wire_complete,
        receipt_implementation_authorised=implementation_authorised,
        live_execution_authorised=False,
        missing_server_findings=missing,
        authorised_claims=(
            "the server-defined wire contract is sufficient to implement an ordered local receipt",
            "the official client source is a reference implementation, not a physical evidence root",
            "badp=0, is_local channel identity, sample rate, local mod_iq send and later IQ must be separately observed",
            "a future receipt implementation may be prepared and tested offline",
        )
        if implementation_authorised
        else ("the wire/source prerequisites remain incomplete",),
        unauthorised_claims=(
            "the server acknowledged or accepted a configuration command",
            "a local send proves retune execution",
            "the frozen eleven closures now have one cause",
            "the current live runtime already implements this contract",
            "a new Kiwi connection or RF acquisition is authorised",
        ),
    )
