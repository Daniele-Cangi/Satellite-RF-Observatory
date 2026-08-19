"""Frozen-receipt tests for the single Gate F2.5.10 live outcome."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-10-20260817T093414.925168Z.jsonl"
)
ARTIFACT_HASH = "cb8e63dd0dfcf8affebf98bc63cf9fbae640f426383a9badb2670a33632b1f1d"
PREFIX_HASH = "58a3835a75b7c07faf39dbf7d41d126b43b425fe30bdeb362a6a7a6fb9dd6911"
ENVELOPE_HASH = "e35aedb598a19c9ce9262e990abec2ff2f90e9fcd1ac7ed2406c9c85f09106ab"
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


def test_artifact_manifest_and_prefix_are_complete() -> None:
    raw = OUTCOME_PATH.read_bytes()
    lines = raw.splitlines(keepends=True)
    documents = _documents()
    terminal = documents[-1]
    payload = terminal["payload"]

    assert len(lines) == 46
    assert len(raw) == 241_467
    assert terminal["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert sha256(b"".join(lines[:-1])).hexdigest() == PREFIX_HASH
    assert payload["prefix_hash"] == PREFIX_HASH
    assert payload["event_line_count"] == 45
    assert payload["event_byte_count"] == 240_876
    assert payload["state"] == "COMPLETE"
    assert payload["retention_complete"] is True
    assert payload["error_count"] == 0
    assert payload["raw_rf_persistence"] == "ZERO"


def test_envelope_is_the_first_event_and_binds_runtime_authority() -> None:
    first = _documents()[0]
    payload = first["payload"]

    assert first["event"] == "gate_f2_5_10_execution_envelope_frozen"
    assert payload["envelope_hash"] == ENVELOPE_HASH
    assert payload["authority_surface"] == "run_reviewed_once"
    assert payload["separate_live_authority_asserted"] is True
    assert payload["envelope"]["postfreeze_retry_budget"] == 0
    assert payload["envelope"]["raw_rf_persistence"] == "ZERO"
    bootstrap = _events("gate_f2_5_10_bootstrap_frozen")[0]["payload"]
    assert bootstrap["receipt"]["runtime_commit"] == (
        "d636981ab6c71f3ca6c673c5cff072ccd7025dcd"
    )


def test_one_terminal_outcome_is_qualification_incomplete() -> None:
    outcomes = _events("gate_f2_5_10_first_outcome")
    assert len(outcomes) == 1
    payload = outcomes[0]["payload"]

    assert payload["outcome"] == "QUALIFICATION_INCOMPLETE"
    assert payload["plan_hash"] is None
    assert payload["physical_result"] is None
    assert payload["evidence_receipt"]["measurement_roots"] == []
    assert payload["evidence_receipt"]["event_start"] == "2026-08-17T09:34:14.936660Z"
    assert payload["evidence_receipt"]["event_end"] == "2026-08-17T09:34:26.244308Z"
    assert payload["authorised_claims"] == [
        "qualification ended descriptively before physical capability availability was determined"
    ]


def test_every_candidate_received_one_real_dual_branch_attempt() -> None:
    atomics = tuple(item["payload"] for item in _events("gate_f2_5_10_atomic_snd_branch_receipt"))
    qualifications = tuple(
        item["payload"] for item in _events("gate_f2_5_10_direct_dual_snd_qualification")
    )
    endpoint_roles = Counter(
        (item["endpoint_identity"], item["role"]) for item in atomics
    )

    assert len(atomics) == 12
    assert len(qualifications) == 6
    assert len({item["endpoint_identity"] for item in atomics}) == 6
    assert all(count == 1 for count in endpoint_roles.values())
    assert all(item["direct_reference_attempted"] for item in qualifications)
    assert all(item["direct_perturbed_attempted"] for item in qualifications)
    assert Counter(item["state"] for item in qualifications) == {
        "QUALIFICATION_ERROR": 5,
        "UNSATISFIED": 1,
    }


def test_atomic_receipts_separate_rejection_from_close_without_readiness() -> None:
    atomics = tuple(item["payload"] for item in _events("gate_f2_5_10_atomic_snd_branch_receipt"))
    rejected = tuple(item for item in atomics if item["state"] == "CAPABILITY_REJECTED")
    closed = tuple(item for item in atomics if item["state"] == "QUALIFICATION_ERROR")

    assert len(rejected) == 4
    assert len(closed) == 8
    assert all(item["readiness_frame_artifact_hash"] is None for item in atomics)
    assert all(item["wire_assessment"]["state"] == "SERVER_REJECTED" for item in rejected)
    assert all(item["error_type"] == "BranchCapabilityRejected" for item in rejected)
    assert all(
        item["wire_assessment"]["state"] == "TERMINATED_WITHOUT_IQ"
        for item in closed
    )
    assert all(item["error_type"] == "_ObservedWebSocketClose" for item in closed)
    assert all(
        item["transcript"]["events"][-1]["kind"] == "WEBSOCKET_CLOSE_OBSERVED"
        and item["transcript"]["events"][-1]["close_code"] == 1005
        for item in closed
    )


def test_all_allocated_branches_sent_mod_iq_but_none_claims_iq_witness() -> None:
    atomics = tuple(item["payload"] for item in _events("gate_f2_5_10_atomic_snd_branch_receipt"))
    closed = tuple(item for item in atomics if item["state"] == "QUALIFICATION_ERROR")

    for receipt in closed:
        kinds = tuple(event["kind"] for event in receipt["transcript"]["events"])
        assert "CHANNEL_ALLOCATED_OBSERVED" in kinds
        assert "BADP_OK_OBSERVED" in kinds
        assert "SAMPLE_RATE_OBSERVED" in kinds
        assert "MOD_IQ_SENT" in kinds
        assert "IQ_FRAME_OBSERVED" not in kinds
        assert receipt["incoming_frame_count"] > 0
        assert receipt["incoming_raw_bytes"] > 0


def test_badp_codes_and_zero_retry_are_exact() -> None:
    atomics = tuple(item["payload"] for item in _events("gate_f2_5_10_atomic_snd_branch_receipt"))
    codes: list[tuple[str, str, float]] = []
    for receipt in atomics:
        for event in receipt["transcript"]["events"]:
            if event["kind"] == "BADP_REJECTION_OBSERVED":
                codes.append(
                    (
                        receipt["endpoint_identity"],
                        receipt["role"],
                        event["numeric_value"],
                    )
                )

    assert sorted(codes) == sorted(
        (
            ("g0ghk.uk:8050", "reference", 1.0),
            ("g0ghk.uk:8050", "perturbed", 1.0),
            ("kiwisdr2blair.ddns.net:8073", "perturbed", 5.0),
            ("kiwisdr.kfsdr.com:8074", "perturbed", 5.0),
        )
    )
    assert _events("gate_f2_5_10_prefreeze_retry") == ()


def test_every_downstream_phase_is_explicitly_not_evaluated() -> None:
    blocked = _events("gate_f2_5_10_phase_not_evaluated")
    assert len(blocked) == 24
    assert all(item["payload"]["state"] == "NOT_EVALUATED" for item in blocked)
    assert Counter(item["payload"]["phase"] for item in blocked) == {
        "LOCAL_IQ_FEATURE_DISCOVERY": 6,
        "PER_CHANNEL_RETUNE_QUALIFICATION": 6,
        "PLAN_FREEZE": 6,
        "ONE_CONFIRMATION": 6,
    }
    assert _events("gate_f2_5_10_plan_frozen") == ()
    assert _events("gate_f2_5_10_local_iq_feature_discovery") == ()
    assert _events("gate_f2_5_10_per_channel_retune_qualification") == ()


def test_frozen_json_contains_no_forbidden_rf_field() -> None:
    keys = set(_walk_keys(list(_documents())))
    assert not keys & FORBIDDEN_RF_KEYS
