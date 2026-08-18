"""Frozen-artifact tests for the single Gate F2.5.21 live outcome."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-21-20260818T111608.453433Z.jsonl"
)
ARTIFACT_HASH = "5307caa715a1f18199a5f933e16ad0c64fb0ce2cfa7753cd254e54e01e9b49fb"
PREFIX_HASH = "877c3973c5ec390777a3b7ade0d5af354206fa046fefefc3ebafe2d978c0e2b0"
AUTHORITY_ENVELOPE_HASH = (
    "9299f8da2d66efb4d0b06a288b151110bb38c75a5254bf903af8ea03e66510d7"
)
CONTROL_SURFACE_HASH = (
    "a823572e04063ff24e7030b2531dc2351c52e1efad2c260cb77589214018224d"
)
LIVE_SURFACE_HASH = (
    "fa4ab9e9dccd363b81f72998c89d3f986c1ed9506539d6a620a00822d443a315"
)
DISCOVERY_ARTIFACT_HASH = (
    "a7ed0ed8e619a33d90876404a1d469d68cd9fef2993a4c1ddea83f703d83d01e"
)
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


def _event(name: str) -> dict[str, object]:
    matches = _events(name)
    assert len(matches) == 1
    return matches[0]


def _walk_keys(value: object) -> tuple[str, ...]:
    if isinstance(value, dict):
        return tuple(str(key) for key in value) + tuple(
            key for item in value.values() for key in _walk_keys(item)
        )
    if isinstance(value, list):
        return tuple(key for item in value for key in _walk_keys(item))
    return ()


def _assert_finite(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_finite(item)
    elif isinstance(value, list):
        for item in value:
            _assert_finite(item)
    elif isinstance(value, float):
        assert math.isfinite(value)


def test_terminal_manifest_and_artifact_hash_are_complete() -> None:
    raw = OUTCOME_PATH.read_bytes()
    lines = raw.splitlines(keepends=True)
    documents = _documents()
    terminal = documents[-1]
    payload = terminal["payload"]

    assert len(lines) == 10
    assert len(raw) == 157_705
    assert terminal["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert sha256(b"".join(lines[:-1])).hexdigest() == PREFIX_HASH
    assert payload["prefix_hash"] == PREFIX_HASH
    assert payload["event_line_count"] == 9
    assert payload["event_byte_count"] == 157_115
    assert payload["state"] == "COMPLETE"
    assert payload["retention_complete"] is True
    assert payload["error_count"] == 0
    assert payload["physical_decision_affected"] is False
    assert payload["raw_rf_persistence"] == "ZERO"


def test_authority_envelope_is_first_and_exactly_consumed() -> None:
    first = _documents()[0]
    payload = first["payload"]

    assert first["event"] == "gate_f2_5_21_authority_envelope_frozen"
    assert payload["authority_envelope_hash"] == AUTHORITY_ENVELOPE_HASH
    assert payload["reviewed_control_surface_hash"] == CONTROL_SURFACE_HASH
    assert payload["reviewed_live_surface_hash"] == LIVE_SURFACE_HASH
    assert payload["separate_live_authority_asserted"] is True
    envelope = payload["authority_envelope"]
    assert envelope["reviewed_f2520_commit"] == (
        "92ef1e8500b6418f2ffe4c5232cbe010269b0178"
    )
    assert envelope["retry_budget"] == 0
    assert envelope["postfreeze_retry_budget"] == 0
    assert envelope["stop_condition"] == "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW"


def test_direct_dual_snd_topology_is_satisfied_without_status_or_waterfall() -> None:
    payload = _event("gate_f2_5_20_direct_dual_snd_qualification")["payload"]
    properties = dict(payload["properties"])
    branches = tuple(payload["atomic_branch_receipts"])

    assert payload["state"] == "SATISFIED"
    assert payload["endpoint_identity"] == "dl1bajkiwisdr.ddns.net:8074"
    assert payload["qualification_error_types"] == []
    assert properties["status_precondition"] == "NONE"
    assert properties["waterfall_requested"] == "FALSE"
    assert properties["ext_api_used_as_gate"] == "FALSE"
    assert properties["reference_channel_id"] == "rx:2"
    assert properties["perturbed_channel_id"] == "rx:1"
    assert properties["simultaneous_IQ_streams"] == "TRUE"
    assert properties["event_time_valid"] == "TRUE"
    assert properties["shared_clock_alignment"] == "TRUE"
    assert properties["both_streams_continuous"] == "TRUE"
    assert properties["both_streams_overflow_free"] == "TRUE"

    assert {branch["role"] for branch in branches} == {"reference", "perturbed"}
    assert {branch["observed_channel_id"] for branch in branches} == {1, 2}
    assert len({branch["ordered_receipt_hash"] for branch in branches}) == 2
    assert len({branch["readiness_frame_artifact_hash"] for branch in branches}) == 2
    assert all(branch["state"] == "READY" for branch in branches)
    assert all(branch["readiness_sequence"] == 2 for branch in branches)
    assert all(branch["readiness_gps_solution_age_s"] == 0 for branch in branches)
    assert all(branch["error_type"] is None for branch in branches)


def test_dual_pair_has_the_frozen_channel_boundary_and_event_time_overlap() -> None:
    payload = _event("gate_f2_5_20_phase_aware_control_receipt")["payload"]
    pair = payload["semantic_pair"]

    assert payload["control_plan_hash"] == (
        "c1a2d8fc139e6090ee70500f258b28c9160174a3411908d4b347c959cf6909fd"
    )
    assert payload["pre_setup_keepalive_count"] == 0
    assert payload["remote_setup_acknowledgement_clause"] == "NOT_EVALUATED"
    assert pair["state"] == "DUAL_READY"
    assert pair["center_hz"] == 16_683_606.560446203
    assert pair["overlap_s"] == 0.012584
    for clause in (
        "reference_ready_clause",
        "perturbed_ready_clause",
        "same_endpoint_clause",
        "distinct_connection_objects_clause",
        "distinct_channel_ids_clause",
        "separate_branch_receipts_clause",
        "separate_stream_sequences_clause",
        "event_time_overlap_clause",
    ):
        assert pair[clause] == "SATISFIED"


def test_discovery_failure_stops_before_retune_freeze_and_confirmation() -> None:
    discovery = _event("gate_f2_5_20_local_iq_feature_discovery")["payload"]
    blocked = tuple(
        item["payload"] for item in _events("gate_f2_5_20_phase_not_evaluated")
    )

    assert discovery["phase"] == "LOCAL_IQ_FEATURE_DISCOVERY"
    assert discovery["state"] == "UNSATISFIED"
    assert discovery["artifact_hashes"] == [DISCOVERY_ARTIFACT_HASH]
    assert discovery["qualification_error_types"] == []
    assert dict(discovery["properties"])["feature_discovery"] == "UNSATISFIED"
    assert discovery["statement"] == (
        "dual IQ exists but no frozen target/witness/delta envelope is available: "
        "prospective discovery contains fewer than two distinct stable structures"
    )
    assert [item["phase"] for item in blocked] == [
        "PER_CHANNEL_RETUNE_QUALIFICATION",
        "PLAN_FREEZE",
        "ONE_CONFIRMATION",
    ]
    assert all(item["state"] == "NOT_EVALUATED" for item in blocked)
    assert all(dict(item["properties"])["upstream_admission"] == "UNSATISFIED" for item in blocked)


def test_terminal_outcome_authorises_no_ddc_or_external_rf_claim() -> None:
    payload = _event("gate_f2_5_20_first_outcome")["payload"]
    states = {
        receipt["phase"]: receipt["state"] for receipt in payload["phase_receipts"]
    }

    assert payload["outcome"] == "NO_FALSIFIABLE_INTERVENTION"
    assert payload["plan_hash"] is None
    assert payload["physical_result"] is None
    assert payload["authorised_claims"] == [
        "an admitted dual-SND topology did not yield the frozen target/witness/retune envelope"
    ]
    assert payload["unauthorised_claims"] == [
        "ext_api proves simultaneous SND availability",
        "waterfall availability is required for multichannel qualification",
        "either DDC-boundary hypothesis is supported",
        "external RF proven",
    ]
    assert states == {
        "DIRECT_DUAL_SND_QUALIFICATION": "SATISFIED",
        "LOCAL_IQ_FEATURE_DISCOVERY": "UNSATISFIED",
        "PER_CHANNEL_RETUNE_QUALIFICATION": "NOT_EVALUATED",
        "PLAN_FREEZE": "NOT_EVALUATED",
        "ONE_CONFIRMATION": "NOT_EVALUATED",
    }


def test_receipt_is_strict_finite_metadata_without_persisted_rf() -> None:
    documents = _documents()
    keys = set(_walk_keys(list(documents)))

    _assert_finite(list(documents))
    assert not keys & FORBIDDEN_RF_KEYS
