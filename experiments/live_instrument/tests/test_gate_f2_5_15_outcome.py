"""Frozen-artifact tests for the single Gate F2.5.15 live outcome."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-15-20260817T112702.764940Z.jsonl"
)
ARTIFACT_HASH = "ba77314fa10ea5ebc6fa3c29f9b4a9ebfdcf0b815d94fe77182a939b63e77619"
PREFIX_HASH = "9dd51ec1813427db243ee12bfba6a3790e90c0f61353fa0e9b643d4180d9d04a"
AUTHORITY_ENVELOPE_HASH = "4a1d4fc9d7dff2efc970502654113bb0396b5e9e91c01e8d8870243b92bf514e"
CONTROL_SURFACE_HASH = "9104f5ff98a5415a558112a38992d2d598b5f7c467c474198a080c96cf531bf0"
FORBIDDEN_RF_KEYS = {
    "blocks",
    "frames",
    "iq",
    "iq_array",
    "iq_samples",
    "raw_body",
    "raw_frame",
    "raw_frames",
    "samples",
    "stft",
    "waterfall",
}


def _documents() -> tuple[dict[str, object], ...]:
    assert sha256(OUTCOME_PATH.read_bytes()).hexdigest() == ARTIFACT_HASH
    return tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in OUTCOME_PATH.read_text(encoding="utf-8").splitlines()
    )


def _events(name: str) -> tuple[dict[str, object], ...]:
    return tuple(item for item in _documents() if item["event"] == name)


def _walk_keys(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, list):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def _pairs() -> tuple[dict[str, object], ...]:
    return tuple(item["payload"] for item in _events("gate_f2_5_15_candidate_pair"))


def _branches() -> tuple[dict[str, object], ...]:
    return tuple(branch for pair in _pairs() for branch in pair["branch_receipts"])


def test_terminal_manifest_and_artifact_hash_are_complete() -> None:
    raw = OUTCOME_PATH.read_bytes()
    lines = raw.splitlines(keepends=True)
    documents = _documents()
    terminal = documents[-1]
    payload = terminal["payload"]

    assert len(lines) == 9
    assert len(raw) == 318_154
    assert terminal["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert sha256(b"".join(lines[:-1])).hexdigest() == PREFIX_HASH
    assert payload["prefix_hash"] == PREFIX_HASH
    assert payload["event_line_count"] == 8
    assert payload["event_byte_count"] == 317_564
    assert payload["state"] == "COMPLETE"
    assert payload["retention_complete"] is True
    assert payload["error_count"] == 0
    assert payload["physical_decision_affected"] is False
    assert payload["raw_rf_persistence"] == "ZERO"


def test_authority_envelope_is_first_and_matches_the_consumed_authority() -> None:
    first = _documents()[0]
    payload = first["payload"]

    assert first["event"] == "gate_f2_5_15_authority_envelope_frozen"
    assert payload["authority_envelope_hash"] == AUTHORITY_ENVELOPE_HASH
    assert payload["execution_control_surface_hash"] == CONTROL_SURFACE_HASH
    assert payload["separate_live_authority_asserted"] is True
    assert payload["authority_envelope"]["reviewed_f2514_commit"] == (
        "d32dba647a9a49d8d980325567a0ae09f3a08c20"
    )
    assert payload["execution_envelope"]["prefreeze_retry_budget"] == 0
    assert payload["execution_envelope"]["postfreeze_retry_budget"] == 0


def test_one_terminal_outcome_is_qualification_incomplete() -> None:
    outcomes = _events("gate_f2_5_15_one_outcome")
    assert len(outcomes) == 1
    payload = outcomes[0]["payload"]

    assert payload["outcome"] == "QUALIFICATION_INCOMPLETE"
    assert payload["selected_endpoint_identity"] is None
    assert payload["stopped_after_first_outcome"] is True
    assert len(payload["attempts"]) == 6
    assert payload["raw_rf_persistence"] == "ZERO"


def test_every_candidate_received_exactly_two_direct_branch_attempts() -> None:
    pairs = _pairs()
    branches = _branches()
    endpoint_roles = Counter((item["endpoint_identity"], item["role"]) for item in branches)

    assert len(pairs) == 6
    assert len(branches) == 12
    assert len({item["endpoint_identity"] for item in pairs}) == 6
    assert all(item["direct_reference_attempted"] for item in pairs)
    assert all(item["direct_perturbed_attempted"] for item in pairs)
    assert all(count == 1 for count in endpoint_roles.values())
    assert Counter(item["state"] for item in pairs) == {
        "QUALIFICATION_INCOMPLETE": 5,
        "EXPLICIT_PAIR_REJECTED": 1,
    }


def test_semantic_receipts_prove_zero_snd_not_a_discarded_snd() -> None:
    branches = _branches()
    semantic = tuple(frame for branch in branches for frame in branch["semantic_frame_receipts"])
    snd = tuple(frame for frame in semantic if frame["frame_class"] == "SND")
    closed = tuple(item for item in branches if item["state"] == "QUALIFICATION_ERROR")

    assert snd == ()
    assert len(closed) == 8
    assert all(item["error_type"] == "_ObservedWebSocketClose" for item in closed)
    assert all(item["close_payload_state"] == "EMPTY_NO_STATUS" for item in closed)
    assert all(item["peer_close_status_code"] is None for item in closed)
    assert all(
        item["semantic_frame_receipts"][-1]["frame_class"] == "CLOSE"
        and item["semantic_frame_receipts"][-1]["frame_byte_count"] == 0
        for item in closed
    )


def test_allocated_branches_sent_mod_iq_but_never_claim_readiness() -> None:
    branches = _branches()
    allocated = tuple(item for item in branches if item["observed_channel_id"] is not None)

    assert len(allocated) == 8
    assert all("MOD_IQ_SENT" in item["control_event_kinds"] for item in allocated)
    assert all(item["readiness_frame_artifact_hash"] is None for item in allocated)
    assert all(item["readiness_sequence"] is None for item in allocated)


def test_only_explicit_badp_events_are_capability_rejections() -> None:
    rejected = tuple(item for item in _branches() if item["state"] == "CAPABILITY_REJECTED")

    assert len(rejected) == 4
    assert all(item["error_type"] == "BranchCapabilityRejected" for item in rejected)
    assert all("BADP_REJECTION_OBSERVED" in item["control_event_kinds"] for item in rejected)
    assert all(item["close_payload_state"] == "NOT_APPLICABLE" for item in rejected)


def test_no_pair_topology_clause_is_promoted_without_two_iq_roots() -> None:
    for pair in _pairs():
        assert pair["distinct_connection_objects_clause"] == "NOT_EVALUATED"
        assert pair["distinct_channel_ids_clause"] == "NOT_EVALUATED"
        assert pair["event_time_overlap_clause"] == "NOT_EVALUATED"
        assert pair["separate_stream_sequences_clause"] == "NOT_EVALUATED"
        assert pair["overlap_s"] is None


def test_frozen_json_contains_no_forbidden_rf_field_or_non_finite_number() -> None:
    documents = _documents()
    keys = set(_walk_keys(list(documents)))

    assert not keys & FORBIDDEN_RF_KEYS
