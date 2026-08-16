"""Gate F2.5.5: offline source-basis and SND control-receipt contract.

The gate is deliberately not a Kiwi runtime.  It specifies the minimum
material and ordered metadata required before another control-plane attempt
could be epistemically useful.  Import and evaluation perform no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import re
from typing import Sequence


F255_TRANSFORM_VERSION = "gate-f2.5.5-offline-source-and-control-contract-v1"
PARENT_GATE_COMMIT = "be5c9de8be906bcaf8bd4fcb04f065b4883285ff"
KIWI_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
KIWICLIENT_COMMIT = "4eb733e6b6147f7fbeb97ced64cdac029b202d18"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class F255Exit(str, Enum):
    SOURCE_BASIS_INCOMPLETE = "SOURCE_BASIS_INCOMPLETE"
    CONTROL_RECEIPT_SPEC_INCOMPLETE = "CONTROL_RECEIPT_SPEC_INCOMPLETE"
    CONTROL_SPEC_READY_FOR_IMPLEMENTATION_REVIEW = (
        "CONTROL_SPEC_READY_FOR_IMPLEMENTATION_REVIEW"
    )


class ControlOrigin(str, Enum):
    LOCAL_CLIENT = "LOCAL_CLIENT"
    REMOTE_ENDPOINT = "REMOTE_ENDPOINT"
    TRANSPORT = "TRANSPORT"


class ControlEventKind(str, Enum):
    WEBSOCKET_OPENED = "WEBSOCKET_OPENED"
    AUTH_COMMAND_RESULT = "AUTH_COMMAND_RESULT"
    CONFIG_COMMAND_RESULT = "CONFIG_COMMAND_RESULT"
    SERVER_FIELD_OBSERVED = "SERVER_FIELD_OBSERVED"
    IQ_FRAME_OBSERVED = "IQ_FRAME_OBSERVED"
    WEBSOCKET_CLOSE_OBSERVED = "WEBSOCKET_CLOSE_OBSERVED"
    TCP_LOSS_OBSERVED = "TCP_LOSS_OBSERVED"


class ServerField(str, Enum):
    BADP = "badp"
    TOO_BUSY = "too_busy"
    AUDIO_RATE = "audio_rate"
    SAMPLE_RATE = "sample_rate"
    CHANNEL_IDENTIFIER = "channel_identifier"
    SLOT_OR_USER_LIMIT = "slot_or_user_limit"


class ValueState(str, Enum):
    ZERO = "ZERO"
    NONZERO = "NONZERO"
    PRESENT = "PRESENT"
    POSITIVE_FINITE = "POSITIVE_FINITE"
    IDENTIFIER_PRESENT = "IDENTIFIER_PRESENT"


class CommandResult(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class TraceObservation(str, Enum):
    IQ_READY_OBSERVED = "IQ_READY_OBSERVED"
    SERVER_REFUSAL_SIGNAL_OBSERVED = "SERVER_REFUSAL_SIGNAL_OBSERVED"
    WEBSOCKET_CLOSED_WITHOUT_IQ = "WEBSOCKET_CLOSED_WITHOUT_IQ"
    TRANSPORT_LOST_WITHOUT_IQ = "TRANSPORT_LOST_WITHOUT_IQ"
    CONTROL_INCOMPLETE = "CONTROL_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class OfficialSourceRequirement:
    project: str
    repository: str
    commit: str
    required_locations: tuple[str, ...]
    retained_artifact_paths: tuple[str, ...] = ()
    retained_artifact_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.project or not self.repository or not self.required_locations:
            raise ValueError("source identity and required locations must be explicit")
        if not re.fullmatch(r"[0-9a-f]{40}", self.commit):
            raise ValueError("official source commit must be an exact 40-hex object id")
        if any(not SHA256_PATTERN.fullmatch(value) for value in self.retained_artifact_hashes):
            raise ValueError("retained source artifacts require SHA-256 hashes")

    @property
    def locally_reproducible(self) -> bool:
        return (
            len(self.retained_artifact_paths) == len(self.required_locations)
            and len(self.retained_artifact_hashes) == len(self.required_locations)
            and all(self.retained_artifact_paths)
            and all(not location.startswith("UNRESOLVED:") for location in self.required_locations)
        )


@dataclass(frozen=True, slots=True)
class ControlReceiptContract:
    required_event_kinds: tuple[ControlEventKind, ...]
    required_causal_distinctions: tuple[str, ...]
    persisted_fields_forbidden: tuple[str, ...]
    command_digest_scope: str
    maximum_authorised_claim: str

    @property
    def complete(self) -> bool:
        return (
            set(self.required_event_kinds) == set(ControlEventKind)
            and len(self.required_causal_distinctions) >= 5
            and {"password", "raw_msg", "rf_samples", "iq_samples", "waterfall"}
            <= set(self.persisted_fields_forbidden)
            and "credential-redacted" in self.command_digest_scope
        )


@dataclass(frozen=True, slots=True)
class F255Assessment:
    exit: F255Exit
    source_basis_reproducible: bool
    receipt_contract_complete: bool
    missing_source_material: tuple[str, ...]
    implementation_authorised: bool
    live_execution_authorised: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


def official_source_requirements() -> tuple[OfficialSourceRequirement, ...]:
    """Return the exact source obligations known from the frozen audits."""

    return (
        OfficialSourceRequirement(
            "KiwiSDR server",
            "https://github.com/jks-prv/KiwiSDR",
            KIWI_SERVER_COMMIT,
            (
                "rx/rx_sound_cmd.cpp:67-79",
                "rx/rx_sound_cmd.cpp:151-175",
                "rx/rx_sound.cpp:568-596",
                "rx/rx_sound.cpp:1082-1136",
            ),
        ),
        OfficialSourceRequirement(
            "kiwiclient",
            "https://github.com/jks-prv/kiwiclient",
            KIWICLIENT_COMMIT,
            ("UNRESOLVED:SND auth/MSG/control-state source location",),
        ),
    )


def control_receipt_contract() -> ControlReceiptContract:
    return ControlReceiptContract(
        required_event_kinds=tuple(ControlEventKind),
        required_causal_distinctions=(
            "local auth command send versus server field observation",
            "local configuration send versus first remote IQ witness",
            "ordered allowlisted server fields versus an aggregate handshake map",
            "WebSocket close frame versus TCP or library transport loss",
            "reference branch events versus perturbed branch events",
            "monotonic control time versus later RF event time",
        ),
        persisted_fields_forbidden=(
            "password",
            "raw_msg",
            "raw_command",
            "rf_samples",
            "iq_samples",
            "waterfall",
        ),
        command_digest_scope="credential-redacted canonical command kind and parameters",
        maximum_authorised_claim=(
            "which local action or remote/transport observation occurred first; "
            "never protocol conformance or RF absence by itself"
        ),
    )


def assess_gate_f2_5_5(
    requirements: Sequence[OfficialSourceRequirement] | None = None,
    contract: ControlReceiptContract | None = None,
) -> F255Assessment:
    requirements = tuple(
        official_source_requirements() if requirements is None else requirements
    )
    contract = contract or control_receipt_contract()
    missing = tuple(
        f"{item.project}:{location}"
        for item in requirements
        if not item.locally_reproducible
        for location in item.required_locations
    )
    source_complete = bool(requirements) and not missing
    if not source_complete:
        exit_state = F255Exit.SOURCE_BASIS_INCOMPLETE
    elif not contract.complete:
        exit_state = F255Exit.CONTROL_RECEIPT_SPEC_INCOMPLETE
    else:
        exit_state = F255Exit.CONTROL_SPEC_READY_FOR_IMPLEMENTATION_REVIEW
    return F255Assessment(
        exit=exit_state,
        source_basis_reproducible=source_complete,
        receipt_contract_complete=contract.complete,
        missing_source_material=missing,
        implementation_authorised=False,
        live_execution_authorised=False,
        authorised_claims=(
            "the control receipt schema preserves the missing causal distinctions",
            "the current official source basis is not locally reproducible",
        ),
        unauthorised_claims=(
            "the local client is conformant or nonconformant",
            "badp=0 is a sufficient authentication acknowledgement",
            "configuration sent means configuration accepted",
            "a future control trace establishes an RF or DDC outcome",
            "another live execution is authorised",
        ),
    )


@dataclass(frozen=True, slots=True)
class SndControlEventReceipt:
    branch_role: str
    ordinal: int
    monotonic_ns: int
    origin: ControlOrigin
    event_kind: ControlEventKind
    command_kind: str | None = None
    command_digest: str | None = None
    command_result: CommandResult | None = None
    server_field: ServerField | None = None
    value_state: ValueState | None = None
    numeric_value: float | None = None
    close_code: int | None = None
    detail_digest: str | None = None
    error_type: str | None = None

    def __post_init__(self) -> None:
        if self.branch_role not in {"reference", "perturbed"}:
            raise ValueError("control events require a frozen branch role")
        if self.ordinal < 0 or self.monotonic_ns < 0:
            raise ValueError("control ordering cannot be negative")
        for digest in (self.command_digest, self.detail_digest):
            if digest is not None and not SHA256_PATTERN.fullmatch(digest):
                raise ValueError("control artifacts require SHA-256 digests")
        if self.numeric_value is not None and not math.isfinite(self.numeric_value):
            raise ValueError("control receipt numeric metadata must be finite")

        command_event = self.event_kind in {
            ControlEventKind.AUTH_COMMAND_RESULT,
            ControlEventKind.CONFIG_COMMAND_RESULT,
        }
        command_metadata = (self.command_kind, self.command_digest, self.command_result)
        if command_event:
            if self.origin is not ControlOrigin.LOCAL_CLIENT or any(
                value is None for value in command_metadata
            ):
                raise ValueError("local command events require redacted command metadata")
            if self.event_kind is ControlEventKind.AUTH_COMMAND_RESULT:
                if self.command_kind != "auth_redacted":
                    raise ValueError("auth receipts may retain only the redacted command kind")
            elif self.command_kind not in {
                "audio_rate_ack",
                "squelch",
                "genattn",
                "gen",
                "ident_user",
                "mod_iq",
                "agc",
                "compression",
                "keepalive",
            }:
                raise ValueError("configuration command kind is not allowlisted")
            if (self.command_result is CommandResult.FAILED) != bool(self.error_type):
                raise ValueError("failed command results require one typed local error")
        elif any(value is not None for value in command_metadata):
            raise ValueError("only local command events may carry command metadata")

        server_event = self.event_kind is ControlEventKind.SERVER_FIELD_OBSERVED
        if server_event:
            if (
                self.origin is not ControlOrigin.REMOTE_ENDPOINT
                or self.server_field is None
                or self.value_state is None
            ):
                raise ValueError("remote server-field events require allowlisted metadata")
        elif any(
            value is not None
            for value in (self.server_field, self.value_state, self.numeric_value)
        ):
            raise ValueError("only remote server-field events may carry field metadata")

        if self.event_kind is ControlEventKind.IQ_FRAME_OBSERVED:
            if self.origin is not ControlOrigin.REMOTE_ENDPOINT or self.detail_digest is None:
                raise ValueError("an IQ witness requires a remote pre-decode artifact hash")
        elif self.event_kind is ControlEventKind.WEBSOCKET_CLOSE_OBSERVED:
            if self.origin is not ControlOrigin.TRANSPORT or self.close_code is None:
                raise ValueError("a WebSocket close witness requires its close code")
        elif self.event_kind is ControlEventKind.TCP_LOSS_OBSERVED:
            if self.origin is not ControlOrigin.TRANSPORT or not self.error_type:
                raise ValueError("TCP/library loss requires a typed transport error")
        elif self.event_kind is ControlEventKind.WEBSOCKET_OPENED:
            if self.origin is not ControlOrigin.TRANSPORT:
                raise ValueError("WebSocket opening is a transport observation")

        if (
            self.event_kind is not ControlEventKind.WEBSOCKET_CLOSE_OBSERVED
            and self.close_code is not None
        ):
            raise ValueError("only a WebSocket close frame may carry a close code")
        if self.error_type is not None and not (
            self.event_kind is ControlEventKind.TCP_LOSS_OBSERVED
            or (command_event and self.command_result is CommandResult.FAILED)
        ):
            raise ValueError("typed errors are limited to failed commands or transport loss")
        if self.detail_digest is not None and self.event_kind not in {
            ControlEventKind.IQ_FRAME_OBSERVED,
            ControlEventKind.WEBSOCKET_CLOSE_OBSERVED,
        }:
            raise ValueError("detail digests are limited to IQ or close artifacts")

        if self.server_field in {
            ServerField.AUDIO_RATE,
            ServerField.SAMPLE_RATE,
            ServerField.SLOT_OR_USER_LIMIT,
        }:
            if (
                self.value_state is not ValueState.POSITIVE_FINITE
                or self.numeric_value is None
                or self.numeric_value <= 0.0
            ):
                raise ValueError("rate and limit fields require a positive finite value")
        elif self.server_field is ServerField.BADP and self.value_state not in {
            ValueState.ZERO,
            ValueState.NONZERO,
        }:
            raise ValueError("badp is retained only as zero versus nonzero")
        elif (
            self.server_field is ServerField.TOO_BUSY
            and self.value_state is not ValueState.PRESENT
        ):
            raise ValueError("too_busy is retained only as presence")
        elif (
            self.server_field is ServerField.CHANNEL_IDENTIFIER
            and self.value_state is not ValueState.IDENTIFIER_PRESENT
        ):
            raise ValueError("channel identity retains presence, not raw identifier text")
        if self.server_field in {
            ServerField.BADP,
            ServerField.TOO_BUSY,
            ServerField.CHANNEL_IDENTIFIER,
        } and self.numeric_value is not None:
            raise ValueError("non-numeric server fields cannot retain numeric payloads")


@dataclass(frozen=True, slots=True)
class SndControlTrace:
    branch_role: str
    events: tuple[SndControlEventReceipt, ...]

    def __post_init__(self) -> None:
        if not self.events:
            raise ValueError("a control trace cannot be empty")
        if any(event.branch_role != self.branch_role for event in self.events):
            raise ValueError("a trace cannot mix reference and perturbed branches")
        if tuple(event.ordinal for event in self.events) != tuple(range(len(self.events))):
            raise ValueError("control event ordinals must be contiguous and ordered")
        times = tuple(event.monotonic_ns for event in self.events)
        if any(later < earlier for earlier, later in zip(times, times[1:])):
            raise ValueError("control event monotonic time runs backwards")
        if self.events[0].event_kind is not ControlEventKind.WEBSOCKET_OPENED:
            raise ValueError("a control trace must begin with WebSocket opening")
        auth_positions = [
            index
            for index, event in enumerate(self.events)
            if event.event_kind is ControlEventKind.AUTH_COMMAND_RESULT
        ]
        if auth_positions != [1]:
            raise ValueError("one redacted auth command result must follow WebSocket opening")
        auth_event = self.events[1]
        if auth_event.command_result is CommandResult.FAILED and len(self.events) > 2:
            raise ValueError("a failed auth send cannot be followed by remote or config events")

        sample_rate_positions = [
            index
            for index, event in enumerate(self.events)
            if event.event_kind is ControlEventKind.SERVER_FIELD_OBSERVED
            and event.server_field is ServerField.SAMPLE_RATE
        ]
        for index, event in enumerate(self.events):
            if (
                event.event_kind is ControlEventKind.CONFIG_COMMAND_RESULT
                and event.command_kind not in {"audio_rate_ack", "keepalive"}
                and not any(position < index for position in sample_rate_positions)
            ):
                raise ValueError("channel configuration requires a prior sample-rate witness")
        iq_positions = [
            index
            for index, event in enumerate(self.events)
            if event.event_kind is ControlEventKind.IQ_FRAME_OBSERVED
        ]
        successful_iq_tunes = [
            index
            for index, event in enumerate(self.events)
            if event.event_kind is ControlEventKind.CONFIG_COMMAND_RESULT
            and event.command_kind == "mod_iq"
            and event.command_result is CommandResult.SUCCEEDED
        ]
        if any(
            not any(tune < iq for tune in successful_iq_tunes)
            for iq in iq_positions
        ):
            raise ValueError("an IQ witness requires a prior successful mod_iq command")
        refusal_observed = any(
            event.event_kind is ControlEventKind.SERVER_FIELD_OBSERVED
            and (
                (
                    event.server_field is ServerField.BADP
                    and event.value_state is ValueState.NONZERO
                )
                or event.server_field is ServerField.TOO_BUSY
            )
            for event in self.events
        )
        if refusal_observed and iq_positions:
            raise ValueError("one trace cannot claim both refusal and IQ readiness")
        terminal = {
            ControlEventKind.WEBSOCKET_CLOSE_OBSERVED,
            ControlEventKind.TCP_LOSS_OBSERVED,
        }
        terminal_positions = [
            index for index, event in enumerate(self.events) if event.event_kind in terminal
        ]
        if terminal_positions and terminal_positions != [len(self.events) - 1]:
            raise ValueError("a trace has exactly one terminal transport observation")


def classify_trace(trace: SndControlTrace) -> TraceObservation:
    if any(
        event.event_kind is ControlEventKind.IQ_FRAME_OBSERVED
        for event in trace.events
    ):
        return TraceObservation.IQ_READY_OBSERVED
    if any(
        event.event_kind is ControlEventKind.SERVER_FIELD_OBSERVED
        and (
            (event.server_field is ServerField.BADP and event.value_state is ValueState.NONZERO)
            or event.server_field is ServerField.TOO_BUSY
        )
        for event in trace.events
    ):
        return TraceObservation.SERVER_REFUSAL_SIGNAL_OBSERVED
    terminal = trace.events[-1].event_kind
    if terminal is ControlEventKind.WEBSOCKET_CLOSE_OBSERVED:
        return TraceObservation.WEBSOCKET_CLOSED_WITHOUT_IQ
    if terminal is ControlEventKind.TCP_LOSS_OBSERVED:
        return TraceObservation.TRANSPORT_LOST_WITHOUT_IQ
    return TraceObservation.CONTROL_INCOMPLETE
