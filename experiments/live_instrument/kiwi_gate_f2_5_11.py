"""Gate F2.5.11: offline attribution of the frozen pre-readiness outcome.

This module consumes descriptive branch receipts only.  It has no live entry
point and deliberately does not change the F2.5.10 runner, its predicate, or
its frozen outcome.  Its narrow purpose is to separate an observed refusal
from a close whose cause the retained receipt cannot identify.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Mapping, Sequence


F2511_TRANSFORM_VERSION = "gate-f2.5.11-frozen-failure-attribution-v1"
FROZEN_OUTCOME_ARTIFACT_SHA256 = (
    "cb8e63dd0dfcf8affebf98bc63cf9fbae640f426383a9badb2670a33632b1f1d"
)

# _receive_data_frame() hashes b"CLOSE" + payload before interpreting it.
# Matching this digest therefore identifies the exact empty-payload encoding
# used by the frozen runtime without retaining the frame itself.
EMPTY_CLOSE_ARTIFACT_SHA256 = sha256(b"CLOSE").hexdigest()


class F2511Exit(str, Enum):
    FROZEN_FAILURE_BOUNDARY_ATTRIBUTED_CAUSE_UNRESOLVED = (
        "FROZEN_FAILURE_BOUNDARY_ATTRIBUTED_CAUSE_UNRESOLVED"
    )


class FailureAttribution(str, Enum):
    EXPLICIT_ATTEMPT_REJECTION = "EXPLICIT_ATTEMPT_REJECTION"
    POST_COMMAND_CAUSE_UNRESOLVED = "POST_COMMAND_CAUSE_UNRESOLVED"
    NO_FAILURE = "NO_FAILURE"
    OUTSIDE_FROZEN_AUDIT = "OUTSIDE_FROZEN_AUDIT"


class CloseStatusSemantics(str, Enum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPTY_PAYLOAD_LOCAL_SENTINEL = "EMPTY_PAYLOAD_LOCAL_SENTINEL"
    NOT_RECOVERABLE_FROM_RECEIPT = "NOT_RECOVERABLE_FROM_RECEIPT"


@dataclass(frozen=True, slots=True)
class BranchFailureAttribution:
    endpoint_identity: str
    role: str
    receipt_state: str
    attribution: FailureAttribution
    observed_boundary: str
    close_status_semantics: CloseStatusSemantics
    qualifying_iq_witness: bool
    non_close_hashed_frame_count: int
    observed_facts: tuple[str, ...]
    unresolved_receipt_cuts: tuple[str, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    transform_version: str = F2511_TRANSFORM_VERSION


_ORDERED_CONTROL_KINDS = (
    "WEBSOCKET_OPENED",
    "AUTH_SENT_REDACTED",
    "SAMPLE_RATE_OBSERVED",
    "CHANNEL_ALLOCATED_OBSERVED",
    "BADP_OK_OBSERVED",
    "MOD_IQ_SENT",
)

_CLOSE_UNRESOLVED_CUTS = (
    "non-close frame tags are not retained beside their hashes",
    "the receipt cannot distinguish no SND frame from nonqualifying SND frames",
    "GPS-seconds presence and GPS-solution age are absent for discarded SND frames",
    "local MOD_IQ_SENT has no receipt of remote application",
    "an empty WebSocket close payload carries no peer status or reason",
)

_CLOSE_UNAUTHORISED_CLAIMS = (
    "no SND bytes or IQ samples arrived",
    "the server rejected or applied the DDC command",
    "GPS absence or stale GPS caused the missing readiness witness",
    "the close has a particular software, transport, policy, or hardware cause",
    "the endpoint lacks simultaneous multichannel measurement capability",
)


def _events(receipt: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    transcript = receipt.get("transcript")
    if not isinstance(transcript, Mapping):
        return ()
    events = transcript.get("events")
    if not isinstance(events, Sequence) or isinstance(events, (str, bytes)):
        return ()
    return tuple(event for event in events if isinstance(event, Mapping))


def _ordered_subsequence(kinds: tuple[str, ...], required: tuple[str, ...]) -> bool:
    position = -1
    for required_kind in required:
        try:
            position = kinds.index(required_kind, position + 1)
        except ValueError:
            return False
    return True


def attribute_branch_failure(
    receipt: Mapping[str, object],
) -> BranchFailureAttribution:
    """Attribute only what one frozen atomic branch receipt establishes."""

    endpoint = str(receipt.get("endpoint_identity", ""))
    role = str(receipt.get("role", ""))
    state = str(receipt.get("state", ""))
    events = _events(receipt)
    kinds = tuple(str(event.get("kind", "")) for event in events)
    qualifying_iq = "IQ_FRAME_OBSERVED" in kinds
    incoming_count = int(receipt.get("incoming_frame_count", 0))

    if state == "READY" and qualifying_iq:
        return BranchFailureAttribution(
            endpoint,
            role,
            state,
            FailureAttribution.NO_FAILURE,
            "QUALIFYING_EVENT_TIME_IQ_OBSERVED",
            CloseStatusSemantics.NOT_APPLICABLE,
            True,
            incoming_count,
            ("the ordered receipt contains a qualifying IQ witness",),
            (),
            ("this branch reached the frozen readiness predicate",),
            ("the branch alone supports either DDC-boundary hypothesis",),
        )

    rejection_kinds = {
        "BADP_REJECTION_OBSERVED",
        "TOO_BUSY_OBSERVED",
    }
    if state == "CAPABILITY_REJECTED" and rejection_kinds.intersection(kinds):
        return BranchFailureAttribution(
            endpoint,
            role,
            state,
            FailureAttribution.EXPLICIT_ATTEMPT_REJECTION,
            "SERVER_ADMISSION_RESPONSE",
            CloseStatusSemantics.NOT_APPLICABLE,
            False,
            incoming_count,
            ("the server emitted an explicit refusal in this branch attempt",),
            (),
            ("this specific branch attempt was rejected before readiness",),
            (
                "the endpoint universally lacks this capability",
                "a later attempt would receive the same response",
                "either DDC-boundary hypothesis was evaluated",
            ),
        )

    close_event = next(
        (event for event in reversed(events) if event.get("kind") == "WEBSOCKET_CLOSE_OBSERVED"),
        None,
    )
    frozen_close = (
        state == "QUALIFICATION_ERROR"
        and receipt.get("error_type") == "_ObservedWebSocketClose"
        and close_event is not None
        and kinds
        and kinds[-1] == "WEBSOCKET_CLOSE_OBSERVED"
        and _ordered_subsequence(kinds, _ORDERED_CONTROL_KINDS)
        and not qualifying_iq
    )
    if frozen_close:
        close_hash = close_event.get("artifact_hash")
        empty_payload = close_hash == EMPTY_CLOSE_ARTIFACT_SHA256
        close_semantics = (
            CloseStatusSemantics.EMPTY_PAYLOAD_LOCAL_SENTINEL
            if empty_payload and close_event.get("close_code") == 1005
            else CloseStatusSemantics.NOT_RECOVERABLE_FROM_RECEIPT
        )
        observed = [
            "the WebSocket, auth send, sample rate, channel allocation and BADP_OK were observed",
            "MOD_IQ was sent locally after the remote prerequisites",
            "incoming frame bytes were hashed before allowlisted analysis",
            "the transcript ended without IQ_FRAME_OBSERVED",
        ]
        if close_semantics is CloseStatusSemantics.EMPTY_PAYLOAD_LOCAL_SENTINEL:
            observed.append(
                "the terminal artifact is the exact hash of b'CLOSE' with an empty payload"
            )
            observed.append(
                "1005 was the frozen recorder's local no-status sentinel, not a peer-supplied status"
            )
        non_close_count = max(0, incoming_count - 1)
        return BranchFailureAttribution(
            endpoint,
            role,
            state,
            FailureAttribution.POST_COMMAND_CAUSE_UNRESOLVED,
            "AFTER_LOCAL_MOD_IQ_SEND_BEFORE_QUALIFYING_EVENT_TIME_IQ",
            close_semantics,
            False,
            non_close_count,
            tuple(observed),
            _CLOSE_UNRESOLVED_CUTS,
            (
                "control-plane allocation and a local IQ command preceded an empty-payload close",
                "no qualifying event-time IQ witness entered the receipt",
                "the failure cause is not attributable with this receipt",
            ),
            _CLOSE_UNAUTHORISED_CLAIMS,
        )

    return BranchFailureAttribution(
        endpoint,
        role,
        state,
        FailureAttribution.OUTSIDE_FROZEN_AUDIT,
        "NOT_CLASSIFIED",
        CloseStatusSemantics.NOT_RECOVERABLE_FROM_RECEIPT,
        qualifying_iq,
        incoming_count,
        (),
        ("the branch does not match either frozen F2.5.10 failure shape",),
        ("this audit makes no additional claim about the branch",),
        ("the branch belongs to a known F2.5.10 failure class",),
    )


def aggregate_frozen_attributions(
    receipts: Sequence[Mapping[str, object]],
) -> tuple[BranchFailureAttribution, ...]:
    """Return one immutable attribution per atomic receipt, without replanning."""

    return tuple(attribute_branch_failure(receipt) for receipt in receipts)
