"""Frozen-artifact tests for the single Gate F2.5.19 live outcome."""

from __future__ import annotations

from hashlib import sha256
import json
import math
from pathlib import Path


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-19-20260818T102026.214534Z.jsonl"
)
ARTIFACT_HASH = "ab2ea016e60ca100d665310f520dbec022c206c3d42f1f92a7b55f5d0b684a47"
PREFIX_HASH = "4fa1e8aee9882d45cd6986c67e287f5be36ff9af470dae96a07b69cb8a80a15c"
AUTHORITY_ENVELOPE_HASH = (
    "b89c09209e83797b06c9730e001fd85c3a04ae77719412655dd0f9c877bdd80a"
)
CONTROL_SURFACE_HASH = (
    "c7b12943feb2ea2ba8ef3f9970a6a145d22cad711146d02bdfba3da75cfe1da6"
)
CONTROL_PLAN_HASH = (
    "c1a2d8fc139e6090ee70500f258b28c9160174a3411908d4b347c959cf6909fd"
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


def _event(name: str) -> dict[str, object]:
    matches = tuple(item for item in _documents() if item["event"] == name)
    assert len(matches) == 1
    return matches[0]


def _candidate_payload() -> dict[str, object]:
    return _event("gate_f2_5_19_candidate_pair")["payload"]


def _branches() -> tuple[dict[str, object], ...]:
    return tuple(
        control["integrated_receipt"]
        for control in _candidate_payload()["branch_controls"]
    )


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

    assert len(lines) == 4
    assert len(raw) == 186_920
    assert terminal["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
    assert sha256(b"".join(lines[:-1])).hexdigest() == PREFIX_HASH
    assert payload["prefix_hash"] == PREFIX_HASH
    assert payload["event_line_count"] == 3
    assert payload["event_byte_count"] == 186_330
    assert payload["state"] == "COMPLETE"
    assert payload["retention_complete"] is True
    assert payload["error_count"] == 0
    assert payload["physical_decision_affected"] is False
    assert payload["raw_rf_persistence"] == "ZERO"


def test_authority_envelope_is_first_and_exactly_consumed() -> None:
    first = _documents()[0]
    payload = first["payload"]

    assert first["event"] == "gate_f2_5_19_authority_envelope_frozen"
    assert payload["authority_envelope_hash"] == AUTHORITY_ENVELOPE_HASH
    assert payload["execution_control_surface_hash"] == CONTROL_SURFACE_HASH
    assert payload["separate_live_authority_asserted"] is True
    assert payload["execution_envelope"]["control_plan_hash"] == CONTROL_PLAN_HASH
    assert payload["execution_envelope"]["attempts_per_candidate"] == 1
    assert payload["execution_envelope"]["prefreeze_retry_budget"] == 0
    assert payload["execution_envelope"]["postfreeze_retry_budget"] == 0
    assert payload["execution_envelope"]["waterfall_precondition"] == (
        "ABSENT_FROM_CAUSAL_PATH"
    )


def test_one_attempt_stops_on_the_first_dual_semantic_pair() -> None:
    payload = _event("gate_f2_5_19_one_outcome")["payload"]
    semantic = payload["semantic_outcome"]

    assert len(payload["attempts"]) == 1
    assert semantic["outcome"] == "DUAL_SEMANTIC_PAIR_READY"
    assert semantic["selected_endpoint_identity"] == "dl1bajkiwisdr.ddns.net:8074"
    assert semantic["stopped_after_first_outcome"] is True
    assert len(semantic["attempts"]) == 1
    assert semantic["raw_rf_persistence"] == "ZERO"


def test_pair_satisfies_only_the_frozen_multichannel_topology() -> None:
    pair = _candidate_payload()["semantic_pair"]

    assert pair["state"] == "DUAL_READY"
    assert pair["center_hz"] == 16_683_606.560446203
    assert pair["direct_reference_attempted"] is True
    assert pair["direct_perturbed_attempted"] is True
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
    assert pair["overlap_s"] == 0.024835
    assert pair["raw_rf_persistence"] == "ZERO"


def test_two_distinct_iq_readiness_roots_are_observed() -> None:
    branches = _branches()

    assert {branch["role"] for branch in branches} == {"reference", "perturbed"}
    assert {branch["observed_channel_id"] for branch in branches} == {0, 1}
    assert len({branch["ordered_receipt_hash"] for branch in branches}) == 2
    assert len({branch["readiness_frame_artifact_hash"] for branch in branches}) == 2
    assert all(branch["state"] == "READY" for branch in branches)
    assert all(branch["pair_disposition"] == "ADMITTED_TO_PAIR" for branch in branches)
    assert all(branch["readiness_sequence"] == 2 for branch in branches)
    assert all(branch["readiness_gps_solution_age_s"] == 0 for branch in branches)
    assert all(branch["error_type"] is None for branch in branches)

    for branch in branches:
        snd = tuple(
            frame
            for frame in branch["semantic_frame_receipts"]
            if frame["frame_class"] == "SND"
        )
        assert len(branch["semantic_frame_receipts"]) == 21
        assert [frame["sequence"] for frame in snd] == [1, 2]
        assert [frame["disposition"] for frame in snd] == [
            "SND_NOT_ADMITTED",
            "READINESS_ADMITTED",
        ]
        assert snd[0]["gps_seconds_present_clause"] == "UNSATISFIED"
        assert snd[1]["gps_seconds_present_clause"] == "SATISFIED"
        assert snd[1]["iq_mode_clause"] == "SATISFIED"
        assert snd[1]["readiness_clause"] == "SATISFIED"


def test_phase_aware_control_has_no_keepalive_before_readiness() -> None:
    controls = _candidate_payload()["branch_controls"]
    expected_phases = [
        "AUTH_EMITTED_LOCAL",
        "REQUIRED_METADATA_OBSERVED",
        "REQUIRED_SETUP_EMITTED_LOCAL",
        "FIRST_SND_READY_OBSERVED",
    ]

    assert _candidate_payload()["pre_setup_keepalive_count"] == 0
    assert _candidate_payload()["remote_setup_acknowledgement_clause"] == (
        "NOT_EVALUATED"
    )
    for control in controls:
        assert control["control_plan_hash"] == CONTROL_PLAN_HASH
        assert control["local_setup_emission_clause"] == "SATISFIED"
        assert control["pre_setup_keepalive_count"] == 0
        assert control["post_setup_keepalive_count"] == 0
        assert control["remote_setup_acknowledgement_clause"] == "NOT_EVALUATED"
        assert [transition["phase"] for transition in control["transitions"]] == (
            expected_phases
        )


def test_receipt_is_strict_finite_metadata_without_persisted_rf() -> None:
    documents = _documents()
    keys = set(_walk_keys(list(documents)))

    _assert_finite(list(documents))
    assert not keys & FORBIDDEN_RF_KEYS
