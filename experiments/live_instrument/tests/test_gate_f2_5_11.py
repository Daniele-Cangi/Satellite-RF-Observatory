"""Offline tests for the frozen Gate F2.5.10 failure attribution."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from hashlib import sha256
import inspect
import json
from pathlib import Path
import struct

from experiments.live_instrument import kiwi_gate_f2_5_11 as f2511


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-10-20260817T093414.925168Z.jsonl"
)


def _documents() -> tuple[dict[str, object], ...]:
    raw = OUTCOME_PATH.read_bytes()
    assert sha256(raw).hexdigest() == f2511.FROZEN_OUTCOME_ARTIFACT_SHA256
    return tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in raw.decode("utf-8").splitlines()
    )


def _atomic_receipts() -> tuple[dict[str, object], ...]:
    return tuple(
        item["payload"]
        for item in _documents()
        if item["event"] == "gate_f2_5_10_atomic_snd_branch_receipt"
    )


def test_frozen_outcome_has_exactly_two_failure_attribution_classes() -> None:
    attributions = f2511.aggregate_frozen_attributions(_atomic_receipts())

    assert len(attributions) == 12
    assert Counter(item.attribution for item in attributions) == {
        f2511.FailureAttribution.EXPLICIT_ATTEMPT_REJECTION: 4,
        f2511.FailureAttribution.POST_COMMAND_CAUSE_UNRESOLVED: 8,
    }
    assert not any(item.qualifying_iq_witness for item in attributions)


def test_all_eight_close_receipts_prove_an_empty_close_payload() -> None:
    closed = tuple(
        receipt
        for receipt in _atomic_receipts()
        if receipt["error_type"] == "_ObservedWebSocketClose"
    )
    assert len(closed) == 8
    assert f2511.EMPTY_CLOSE_ARTIFACT_SHA256 == sha256(b"CLOSE").hexdigest()
    assert f2511.EMPTY_CLOSE_ARTIFACT_SHA256 != sha256(
        b"CLOSE" + struct.pack(">H", 1005)
    ).hexdigest()

    for receipt in closed:
        close = receipt["transcript"]["events"][-1]
        attribution = f2511.attribute_branch_failure(receipt)
        assert close["kind"] == "WEBSOCKET_CLOSE_OBSERVED"
        assert close["artifact_hash"] == f2511.EMPTY_CLOSE_ARTIFACT_SHA256
        assert close["artifact_hash"] == receipt["incoming_frame_artifact_hashes"][-1]
        assert close["close_code"] == 1005
        assert attribution.close_status_semantics is (
            f2511.CloseStatusSemantics.EMPTY_PAYLOAD_LOCAL_SENTINEL
        )
        assert any("local no-status sentinel" in fact for fact in attribution.observed_facts)


def test_1005_is_not_promoted_to_a_peer_status_or_failure_cause() -> None:
    closed = next(
        receipt
        for receipt in _atomic_receipts()
        if receipt["error_type"] == "_ObservedWebSocketClose"
    )
    attribution = f2511.attribute_branch_failure(closed)

    assert attribution.attribution is f2511.FailureAttribution.POST_COMMAND_CAUSE_UNRESOLVED
    assert attribution.observed_boundary == (
        "AFTER_LOCAL_MOD_IQ_SEND_BEFORE_QUALIFYING_EVENT_TIME_IQ"
    )
    assert "an empty WebSocket close payload carries no peer status or reason" in (
        attribution.unresolved_receipt_cuts
    )
    assert "the failure cause is not attributable with this receipt" in (
        attribution.authorised_claims
    )
    assert "the close has a particular software, transport, policy, or hardware cause" in (
        attribution.unauthorised_claims
    )


def test_close_receipts_preserve_control_order_and_inbound_activity_only() -> None:
    closed = tuple(
        receipt
        for receipt in _atomic_receipts()
        if receipt["error_type"] == "_ObservedWebSocketClose"
    )
    required = (
        "WEBSOCKET_OPENED",
        "AUTH_SENT_REDACTED",
        "SAMPLE_RATE_OBSERVED",
        "CHANNEL_ALLOCATED_OBSERVED",
        "BADP_OK_OBSERVED",
        "MOD_IQ_SENT",
    )
    for receipt in closed:
        kinds = tuple(event["kind"] for event in receipt["transcript"]["events"])
        positions = tuple(kinds.index(kind) for kind in required)
        attribution = f2511.attribute_branch_failure(receipt)
        assert positions == tuple(sorted(positions))
        assert attribution.non_close_hashed_frame_count == receipt["incoming_frame_count"] - 1
        assert attribution.non_close_hashed_frame_count > 0
        assert "IQ_FRAME_OBSERVED" not in kinds


def test_hash_only_receipt_cannot_recover_snd_or_predicate_failures() -> None:
    closed = next(
        receipt
        for receipt in _atomic_receipts()
        if receipt["error_type"] == "_ObservedWebSocketClose"
    )
    attribution = f2511.attribute_branch_failure(closed)

    assert "incoming_frame_kinds" not in closed
    assert "nonqualifying_snd_receipts" not in closed
    assert "gps_seconds_present" not in closed
    assert "discarded_snd_gps_solution_ages_s" not in closed
    assert "the receipt cannot distinguish no SND frame from nonqualifying SND frames" in (
        attribution.unresolved_receipt_cuts
    )
    assert "no SND bytes or IQ samples arrived" in attribution.unauthorised_claims
    assert "GPS absence or stale GPS caused the missing readiness witness" in (
        attribution.unauthorised_claims
    )


def test_explicit_badp_is_scoped_to_the_observed_attempt() -> None:
    rejected = tuple(
        receipt for receipt in _atomic_receipts() if receipt["state"] == "CAPABILITY_REJECTED"
    )
    assert len(rejected) == 4
    for receipt in rejected:
        attribution = f2511.attribute_branch_failure(receipt)
        assert attribution.attribution is (
            f2511.FailureAttribution.EXPLICIT_ATTEMPT_REJECTION
        )
        assert attribution.observed_boundary == "SERVER_ADMISSION_RESPONSE"
        assert attribution.authorised_claims == (
            "this specific branch attempt was rejected before readiness",
        )
        assert "the endpoint universally lacks this capability" in (
            attribution.unauthorised_claims
        )


def test_unknown_close_hash_does_not_inherit_empty_payload_semantics() -> None:
    closed = next(
        receipt
        for receipt in _atomic_receipts()
        if receipt["error_type"] == "_ObservedWebSocketClose"
    )
    changed = deepcopy(closed)
    changed["transcript"]["events"][-1]["artifact_hash"] = "0" * 64
    attribution = f2511.attribute_branch_failure(changed)

    assert attribution.attribution is f2511.FailureAttribution.POST_COMMAND_CAUSE_UNRESOLVED
    assert attribution.close_status_semantics is (
        f2511.CloseStatusSemantics.NOT_RECOVERABLE_FROM_RECEIPT
    )
    assert not any("local no-status sentinel" in fact for fact in attribution.observed_facts)


def test_offline_audit_has_no_live_or_retry_entry_point() -> None:
    source = inspect.getsource(f2511)
    forbidden = (
        "import websocket",
        "import requests",
        "urlopen",
        "run_live",
        "run_reviewed_once",
        "create_connection",
    )
    assert not any(token in source for token in forbidden)
    assert not hasattr(f2511, "run")
    assert not hasattr(f2511, "main")
