"""Frozen-artifact tests for the single Gate F2.5.25 live outcome."""

from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
import math
from pathlib import Path


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-25-20260818T194244.943090Z.jsonl"
)
ARTIFACT_HASH = "921deca68780b6546d19d4f8be2cb3cbb0ed5c9710d333f5dd24bf5d799b7380"
PREFIX_HASH = "22dede9a078858af115eb2ba042d4bfd0e2893f931c061e51428fae7790c5890"
AUTHORITY_ENVELOPE_HASH = (
    "fa21168df4487508b63cba9aec1324c57a91c60e9e144d7d646a972a09a4953d"
)
CONFIRMATION_SURFACE_HASH = (
    "c4310059594402fdc8b4570e4391487242ee50b5af11ea9a186cd5d1c8f0dac8"
)
LIVE_SURFACE_HASH = (
    "34f641c54131b319e4fdb415f9daa0b6cdc94a9009fd7135df1c03d1777e7b80"
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


@lru_cache(maxsize=1)
def _documents() -> tuple[dict[str, object], ...]:
    assert sha256(OUTCOME_PATH.read_bytes()).hexdigest() == ARTIFACT_HASH
    return tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in OUTCOME_PATH.read_text(encoding="utf-8").splitlines()
    )


def _event(name: str) -> dict[str, object]:
    matches = tuple(item for item in _documents() if item["event"] == name)
    assert len(matches) == 1
    return matches[0]


def _branches() -> tuple[dict[str, object], ...]:
    payload = _event("gate_f2_5_25_phase_aware_control_receipt")["payload"]
    return tuple(item["integrated_receipt"] for item in payload["branch_controls"])


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
    terminal = _documents()[-1]
    payload = terminal["payload"]

    assert len(lines) == 9
    assert len(raw) == 857_267
    assert terminal["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert sha256(b"".join(lines[:-1])).hexdigest() == PREFIX_HASH
    assert payload["prefix_hash"] == PREFIX_HASH
    assert payload["event_line_count"] == 8
    assert payload["event_byte_count"] == 856_677
    assert payload["state"] == "COMPLETE"
    assert payload["retention_complete"] is True
    assert payload["error_count"] == 0
    assert payload["physical_decision_affected"] is False
    assert payload["raw_rf_persistence"] == "ZERO"


def test_authority_envelope_is_first_and_consumed_once() -> None:
    first = _documents()[0]
    payload = first["payload"]
    envelope = payload["authority_envelope"]

    assert first["event"] == "gate_f2_5_25_authority_envelope_frozen"
    assert payload["authority_envelope_hash"] == AUTHORITY_ENVELOPE_HASH
    assert payload["reviewed_confirmation_surface_hash"] == CONFIRMATION_SURFACE_HASH
    assert payload["reviewed_live_surface_hash"] == LIVE_SURFACE_HASH
    assert payload["separate_live_authority_asserted"] is True
    assert envelope["reviewed_f2524_commit"] == (
        "f08c4f2f8178a497c024dcc9f0cf64886e09d8ab"
    )
    assert envelope["confirmation_windows"] == 1
    assert envelope["prefreeze_retry_budget"] == 0
    assert envelope["postfreeze_retry_budget"] == 0
    assert envelope["stop_condition"] == "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW"


def test_two_channels_delivered_iq_but_neither_supplied_admissible_event_time() -> None:
    branches = _branches()

    assert {item["role"] for item in branches} == {"reference", "perturbed"}
    assert {item["observed_channel_id"] for item in branches} == {0, 1}
    assert {item["incoming_frame_count"] for item in branches} == {293, 295}
    assert all(item["state"] == "QUALIFICATION_ERROR" for item in branches)
    assert all(item["error_type"] == "TimeoutError" for item in branches)
    assert all(item["readiness_frame_artifact_hash"] is None for item in branches)

    expected_snd_counts = {"reference": 275, "perturbed": 274}
    for branch in branches:
        snd = tuple(
            item
            for item in branch["semantic_frame_receipts"]
            if item["frame_class"] == "SND"
        )
        assert len(snd) == expected_snd_counts[branch["role"]]
        assert all(item["snd_header_clause"] == "SATISFIED" for item in snd)
        assert all(item["sample_decode_clause"] == "SATISFIED" for item in snd)
        assert all(item["iq_mode_clause"] == "SATISFIED" for item in snd)
        assert not any(item["readiness_clause"] == "SATISFIED" for item in snd)

        missing_seconds = tuple(
            item for item in snd if item["gps_seconds_present_clause"] == "UNSATISFIED"
        )
        stale = tuple(
            item for item in snd if item["gps_age_within_limit_clause"] == "UNSATISFIED"
        )
        assert len(missing_seconds) == 1
        assert missing_seconds[0]["gps_solution_age_s"] == 0
        assert len(stale) == len(snd) - 1
        ages = tuple(item["gps_solution_age_s"] for item in stale)
        assert min(ages) == 92
        assert max(ages) == 103


def test_pair_availability_remains_unresolved_not_rejected() -> None:
    pair = _event("gate_f2_5_25_phase_aware_control_receipt")["payload"][
        "semantic_pair"
    ]

    assert pair["state"] == "QUALIFICATION_INCOMPLETE"
    assert pair["same_endpoint_clause"] == "SATISFIED"
    assert pair["separate_branch_receipts_clause"] == "SATISFIED"
    assert pair["reference_ready_clause"] == "QUALIFICATION_ERROR"
    assert pair["perturbed_ready_clause"] == "QUALIFICATION_ERROR"
    assert pair["distinct_connection_objects_clause"] == "NOT_EVALUATED"
    assert pair["distinct_channel_ids_clause"] == "NOT_EVALUATED"
    assert pair["event_time_overlap_clause"] == "NOT_EVALUATED"
    assert pair["separate_stream_sequences_clause"] == "NOT_EVALUATED"
    assert pair["statement"] == (
        "software or transport left corrected dual-SND availability unresolved"
    )


def test_prefreeze_outcome_blocks_every_physical_phase() -> None:
    outcome = _event("gate_f2_5_25_prefreeze_outcome")["payload"]
    states = {
        item["phase"]: item["state"] for item in outcome["phase_receipts"]
    }

    assert outcome["outcome"] == "QUALIFICATION_INCOMPLETE"
    assert outcome["plan"] is None
    assert outcome["authorised_claims"] == [
        "same-session dual-SND topology did not admit discovery"
    ]
    assert states == {
        "DIRECT_DUAL_SND_QUALIFICATION": "QUALIFICATION_ERROR",
        "ONE_TARGET_DISCOVERY": "NOT_EVALUATED",
        "DISTRIBUTED_RETUNE_QUALIFICATION": "NOT_EVALUATED",
        "PLAN_FREEZE": "NOT_EVALUATED",
        "ONE_CONFIRMATION": "NOT_EVALUATED",
    }
    assert not tuple(
        item
        for item in _documents()
        if item["event"] == "gate_f2_5_25_one_confirmation_outcome"
    )


def test_receipt_is_strict_finite_metadata_without_persisted_rf() -> None:
    documents = _documents()
    keys = set(_walk_keys(list(documents)))

    _assert_finite(list(documents))
    assert not keys & FORBIDDEN_RF_KEYS
