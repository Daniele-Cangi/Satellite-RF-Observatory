"""Gate F2.5.4: offline audit of the direct-SND control boundary.

This module does not open sockets or read the frozen outcome artifact.  It
accepts already-decoded receipt mappings and answers only questions supported
by the retained control-plane fields.  In particular, a locally sent command
is never treated as evidence that the remote endpoint accepted it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable, Mapping, Sequence

from . import kiwi_gate_f2_4 as f24


F254_TRANSFORM_VERSION = "gate-f2.5.4-offline-control-boundary-audit-v1"
PARENT_RUNTIME_COMMIT = "aec6da247aa6edb3e180aa848cc05aa2d7f49e2b"
PARENT_OUTCOME_COMMIT = "6776c19b97246822217f91612959c3a49174876e"
OUTCOME_ARTIFACT_HASH = "be4b10781928eb01a464175c9674681facca4aa30c6541a5e8ba8278ecd78ca5"
KIWI_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
KIWICLIENT_COMMIT = "4eb733e6b6147f7fbeb97ced64cdac029b202d18"
ATOMIC_BRANCH_EVENT = "gate_f2_5_3_1_atomic_snd_branch_receipt"
COMMON_CLIENT_ROOT = "local-client:kiwi_gate_f2_5_2._atomic_open_channel"


class ObservedControlStage(str, Enum):
    """Highest control-plane stage directly witnessed by one branch receipt."""

    WEBSOCKET_OPEN_NO_SERVER_MESSAGE = "WEBSOCKET_OPEN_NO_SERVER_MESSAGE"
    CONFIGURATION_SENT_EXPLICIT_REJECTION = "CONFIGURATION_SENT_EXPLICIT_REJECTION"
    CONFIGURATION_SENT_NO_IQ = "CONFIGURATION_SENT_NO_IQ"
    IQ_READY = "IQ_READY"
    RECEIPT_SHAPE_UNRESOLVED = "RECEIPT_SHAPE_UNRESOLVED"


class FailureAttribution(str, Enum):
    """Narrow attribution; values do not infer an unrecorded remote cause."""

    SERVER_REPORTED_CAPABILITY_REJECTION = "SERVER_REPORTED_CAPABILITY_REJECTION"
    TRANSPORT_TIMEOUT_BEFORE_HANDSHAKE = "TRANSPORT_TIMEOUT_BEFORE_HANDSHAKE"
    NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT = "NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT"
    NO_FAILURE = "NO_FAILURE"
    RECEIPT_INCONSISTENT = "RECEIPT_INCONSISTENT"


class SessionExit(str, Enum):
    """Offline exit decision for the frozen F2.5.3.1 evidence."""

    STOP_PENDING_CONTROL_DISCRIMINATORS = "STOP_PENDING_CONTROL_DISCRIMINATORS"
    PHYSICAL_EXPERIMENT_MAY_PROCEED = "PHYSICAL_EXPERIMENT_MAY_PROCEED"
    NO_CAPABILITY_ADMITTED = "NO_CAPABILITY_ADMITTED"
    CLIENT_CORRECTION_REQUIRED = "CLIENT_CORRECTION_REQUIRED"


class OfficialSourceBasisStatus(str, Enum):
    REFERENCED_BUT_NOT_PRESENT_IN_REPOSITORY = (
        "REFERENCED_BUT_NOT_PRESENT_IN_REPOSITORY"
    )


@dataclass(frozen=True, slots=True)
class BranchControlReceipt:
    endpoint_identity: str
    role: str
    state: str
    websocket_opened: bool
    handshake_message_count: int
    configuration_sent: bool
    sample_rate_hz: float | None
    iq_frame_count: int
    error_type: str | None

    def __post_init__(self) -> None:
        if not self.endpoint_identity:
            raise ValueError("endpoint identity is required")
        if self.role not in {"reference", "perturbed"}:
            raise ValueError("branch role must be reference or perturbed")
        if self.handshake_message_count < 0 or self.iq_frame_count < 0:
            raise ValueError("receipt counts cannot be negative")
        if self.state == "READY" and not (
            self.websocket_opened
            and self.configuration_sent
            and self.sample_rate_hz is not None
            and math.isfinite(self.sample_rate_hz)
            and self.sample_rate_hz > 0.0
            and self.iq_frame_count > 0
            and self.error_type is None
        ):
            raise ValueError("READY requires a configured positive-rate IQ witness")


@dataclass(frozen=True, slots=True)
class BranchProtocolAudit:
    endpoint_identity: str
    role: str
    observed_stage: ObservedControlStage
    attribution: FailureAttribution
    maximum_authorised_claim: str
    missing_discriminators: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProtocolSurfaceAudit:
    current_post_sample_command_kinds: tuple[str, ...]
    prior_single_channel_command_kinds: tuple[str, ...]
    shape_matches_prior_local_single_channel_path: bool
    official_source_basis: OfficialSourceBasisStatus
    official_source_commits: tuple[str, str]
    conformance_conclusion: str
    missing_control_receipt_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionProtocolAudit:
    branch_count: int
    endpoint_count: int
    configured_branch_count: int
    ready_branch_count: int
    iq_frame_count: int
    attribution_counts: tuple[tuple[str, int], ...]
    observed_stage_counts: tuple[tuple[str, int], ...]
    common_client_root: str
    endpoint_roots: tuple[str, ...]
    endpoint_failures_independent_for_client_hypothesis: bool
    exit: SessionExit
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    missing_control_discriminators: tuple[str, ...]


MISSING_CONTROL_DISCRIMINATORS = (
    "ordered auth outcome distinct from local auth command send",
    "ordered allowlisted MSG keys and state transitions",
    "ordered command-kind hashes, send times and send results",
    "WebSocket close frame code and reason distinct from TCP loss",
    "per-stage monotonic timestamps",
    "server-reported slot or user limit from the same handshake when present",
)


def branch_from_mapping(value: Mapping[str, object]) -> BranchControlReceipt:
    """Project one retained branch receipt onto its control-plane facts."""

    sample_rate = value.get("sample_rate_hz")
    return BranchControlReceipt(
        endpoint_identity=str(value["endpoint_identity"]),
        role=str(value["role"]),
        state=str(value["state"]),
        websocket_opened=bool(value["websocket_opened"]),
        handshake_message_count=int(value["handshake_message_count"]),
        configuration_sent=bool(value["configuration_sent"]),
        sample_rate_hz=None if sample_rate is None else float(sample_rate),
        iq_frame_count=int(value["iq_frame_count"]),
        error_type=(
            None if value.get("error_type") is None else str(value["error_type"])
        ),
    )


def atomic_branch_receipts(
    documents: Iterable[Mapping[str, object]],
) -> tuple[BranchControlReceipt, ...]:
    """Extract atomic branches from decoded JSONL documents without I/O."""

    receipts: list[BranchControlReceipt] = []
    for document in documents:
        if document.get("event") != ATOMIC_BRANCH_EVENT:
            continue
        payload = document.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("atomic branch event requires a mapping payload")
        receipts.append(branch_from_mapping(payload))
    return tuple(receipts)


def audit_branch(receipt: BranchControlReceipt) -> BranchProtocolAudit:
    """Attribute only what this receipt can discriminate."""

    if receipt.state == "READY" and receipt.iq_frame_count > 0:
        return BranchProtocolAudit(
            receipt.endpoint_identity,
            receipt.role,
            ObservedControlStage.IQ_READY,
            FailureAttribution.NO_FAILURE,
            "the branch reached hashed IQ readiness",
            (),
        )

    if receipt.error_type == "BranchCapabilityRejected":
        stage = (
            ObservedControlStage.CONFIGURATION_SENT_EXPLICIT_REJECTION
            if receipt.configuration_sent
            else ObservedControlStage.RECEIPT_SHAPE_UNRESOLVED
        )
        return BranchProtocolAudit(
            receipt.endpoint_identity,
            receipt.role,
            stage,
            FailureAttribution.SERVER_REPORTED_CAPABILITY_REJECTION,
            "the server reported a capability rejection for this branch attempt",
            ("ordered rejection relative to auth and configuration",),
        )

    if (
        receipt.error_type in {"WebSocketTimeoutException", "TimeoutError"}
        and receipt.websocket_opened
        and receipt.handshake_message_count == 0
        and not receipt.configuration_sent
    ):
        return BranchProtocolAudit(
            receipt.endpoint_identity,
            receipt.role,
            ObservedControlStage.WEBSOCKET_OPEN_NO_SERVER_MESSAGE,
            FailureAttribution.TRANSPORT_TIMEOUT_BEFORE_HANDSHAKE,
            "the WebSocket opened but no retained server MSG or IQ frame followed before timeout",
            ("server response versus silent transport after WebSocket open",),
        )

    if receipt.configuration_sent and receipt.iq_frame_count == 0:
        return BranchProtocolAudit(
            receipt.endpoint_identity,
            receipt.role,
            ObservedControlStage.CONFIGURATION_SENT_NO_IQ,
            FailureAttribution.NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT,
            "configuration commands were sent locally and no IQ frame was retained",
            MISSING_CONTROL_DISCRIMINATORS,
        )

    return BranchProtocolAudit(
        receipt.endpoint_identity,
        receipt.role,
        ObservedControlStage.RECEIPT_SHAPE_UNRESOLVED,
        FailureAttribution.RECEIPT_INCONSISTENT,
        "the retained fields do not support a narrower control-stage claim",
        MISSING_CONTROL_DISCRIMINATORS,
    )


def _counts(values: Sequence[Enum]) -> tuple[tuple[str, int], ...]:
    unique = sorted({value.value for value in values})
    return tuple((name, sum(value.value == name for value in values)) for name in unique)


def audit_session(receipts: Sequence[BranchControlReceipt]) -> SessionProtocolAudit:
    """Return the strongest exit decision justified by atomic branch receipts."""

    if not receipts:
        raise ValueError("a session audit requires at least one branch receipt")
    audits = tuple(audit_branch(receipt) for receipt in receipts)
    attributions = tuple(item.attribution for item in audits)
    stages = tuple(item.observed_stage for item in audits)
    ready = sum(item is FailureAttribution.NO_FAILURE for item in attributions)
    endpoints_in_receipts = {receipt.endpoint_identity for receipt in receipts}
    roles_by_endpoint = {
        endpoint: {
            receipt.role for receipt in receipts if receipt.endpoint_identity == endpoint
        }
        for endpoint in endpoints_in_receipts
    }
    ready_roles_by_endpoint = {
        endpoint: {
            receipt.role
            for receipt, item in zip(receipts, audits)
            if receipt.endpoint_identity == endpoint
            and item.attribution is FailureAttribution.NO_FAILURE
        }
        for endpoint in endpoints_in_receipts
    }
    dual_ready = any(
        roles == {"reference", "perturbed"}
        for roles in ready_roles_by_endpoint.values()
    )
    all_attempts_have_both_roles = all(
        roles == {"reference", "perturbed"} for roles in roles_by_endpoint.values()
    )
    explicit_rejections = sum(
        item is FailureAttribution.SERVER_REPORTED_CAPABILITY_REJECTION
        for item in attributions
    )
    if dual_ready:
        exit_state = SessionExit.PHYSICAL_EXPERIMENT_MAY_PROCEED
    elif explicit_rejections == len(receipts) and all_attempts_have_both_roles:
        exit_state = SessionExit.NO_CAPABILITY_ADMITTED
    else:
        exit_state = SessionExit.STOP_PENDING_CONTROL_DISCRIMINATORS

    endpoints = tuple(sorted({receipt.endpoint_identity for receipt in receipts}))
    missing = tuple(
        dict.fromkeys(
            discriminator
            for item in audits
            for discriminator in item.missing_discriminators
        )
    )
    return SessionProtocolAudit(
        branch_count=len(receipts),
        endpoint_count=len(endpoints),
        configured_branch_count=sum(receipt.configuration_sent for receipt in receipts),
        ready_branch_count=ready,
        iq_frame_count=sum(receipt.iq_frame_count for receipt in receipts),
        attribution_counts=_counts(attributions),
        observed_stage_counts=_counts(stages),
        common_client_root=COMMON_CLIENT_ROOT,
        endpoint_roots=tuple(f"kiwi-endpoint:{endpoint}" for endpoint in endpoints),
        endpoint_failures_independent_for_client_hypothesis=False,
        exit=exit_state,
        authorised_claims=(
            "local command transmission is distinct from remote command acceptance",
            "explicit server-reported rejection is narrower than multichannel absence",
            "post-configuration closure is not attributable with the retained receipt",
            "all endpoint attempts share one local client implementation root",
        ),
        unauthorised_claims=(
            "the client is conformant with the frozen official server version",
            "the client is nonconformant with the frozen official server version",
            "configuration_sent proves an accepted or valid remote setup",
            "the endpoints lack simultaneous SND capability",
            "the transport failures have one common remote cause",
            "an RF feature was absent",
        ),
        missing_control_discriminators=missing,
    )


def _command_kind(command: str) -> str:
    fields = command.split()
    if len(fields) < 2 or fields[0] != "SET":
        raise ValueError(f"unsupported command shape: {command!r}")
    return fields[1].split("=", 1)[0]


def protocol_surface_audit(center_hz: float = 10_000_000.0) -> ProtocolSurfaceAudit:
    """Compare local command shape without claiming official conformance."""

    current = tuple(
        _command_kind(command)
        for command in f24._initial_channel_commands(center_hz)
    )
    prior_single = (
        "squelch",
        "genattn",
        "gen",
        "ident_user",
        "mod",
        "agc",
        "compression",
        "keepalive",
    )
    return ProtocolSurfaceAudit(
        current_post_sample_command_kinds=current,
        prior_single_channel_command_kinds=prior_single,
        shape_matches_prior_local_single_channel_path=current == prior_single,
        official_source_basis=(
            OfficialSourceBasisStatus.REFERENCED_BUT_NOT_PRESENT_IN_REPOSITORY
        ),
        official_source_commits=(KIWI_SERVER_COMMIT, KIWICLIENT_COMMIT),
        conformance_conclusion=(
            "CONSISTENT_WITH_PRIOR_LOCAL_SINGLE_CHANNEL_PATH_"
            "NOT_OFFICIALLY_REPRODUCIBLE_FROM_THIS_REPOSITORY"
        ),
        missing_control_receipt_fields=MISSING_CONTROL_DISCRIMINATORS,
    )
