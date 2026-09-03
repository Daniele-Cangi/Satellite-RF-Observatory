from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_all_track_qualification_retry as retry,
)
from experiments.orbital_discriminability import (
    gnss_all_track_structural_qualification as qualification,
)


ROOT = Path(retry.__file__).resolve().parent
OUTCOME = ROOT / retry.RETRY_OUTCOME_NAME
STRUCTURE = ROOT / retry.RETRY_STRUCTURE_NAME
REVEAL = ROOT / retry.RETRY_REVEAL_NAME
COVERAGE = ROOT / retry.RETRY_COVERAGE_NAME


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_retry_terminal_and_exact_artifact_identity_are_frozen() -> None:
    outcome = load(OUTCOME)

    assert outcome["outcome"] == "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED"
    assert outcome["artifact"]["attempts"] == 1
    assert outcome["artifact"]["complete_file_bytes"] == 4_317_738
    assert outcome["artifact"]["complete_file_sha256"] == retry.ARTIFACT_SHA256
    assert outcome["artifact"]["matches_frozen_complete_identity"] is True
    assert outcome["artifact"]["hash_completed_before_decompression"] is True
    assert outcome["persistence"] == {
        "compressed_artifact_bytes": 0,
        "decompressed_observation_bytes": 0,
        "observation_values": 0,
        "structural_receipts_only": True,
    }


def test_complete_grid_contains_seven_complete_tracks_not_six() -> None:
    outcome = load(OUTCOME)
    structure = load(STRUCTURE)

    assert outcome["clause_states"]["header_description"] == "SATISFIED"
    assert outcome["clause_states"]["complete_grid"] == "SATISFIED"
    assert outcome["clause_states"]["exact_six_complete_tracks"] == "UNSATISFIED"
    assert structure["epoch_grid_complete"] is True
    assert structure["epoch_present_count"] == 139
    assert structure["gps_tracks_seen"] == 11
    assert structure["complete_track_count"] == 7
    assert structure["complete_track_count_required"] == 6
    assert structure["complete_opaque_tracks"] == [
        "T001",
        "T003",
        "T004",
        "T005",
        "T006",
        "T007",
        "T009",
    ]
    assert structure["count_clause"] == "UNSATISFIED"
    assert structure["parser_issues"] == []


def test_reveal_cannot_remove_the_extra_complete_g11_track() -> None:
    reveal = load(REVEAL)

    assert reveal["complete_receiver_prns"] == [
        "G05",
        "G11",
        "G15",
        "G18",
        "G20",
        "G21",
        "G29",
    ]
    assert reveal["orbit_codebook"] == [
        "G05",
        "G15",
        "G18",
        "G20",
        "G21",
        "G29",
    ]
    assert reveal["codebook_relation"] == "DISCORDANT"
    assert reveal["membership_changed_by_reveal"] is False
    assert reveal["qualification_rescued_by_reveal"] is False


def test_receipt_hashes_and_historical_predecessor_are_immutable() -> None:
    assert qualification.canonical_file_sha256(OUTCOME) == (
        "233e34084c0ffe86749919dd3f9b73ff243f9a51f530749328a7456dc7ad828e"
    )
    assert qualification.canonical_file_sha256(STRUCTURE) == (
        "9eec2cbfc934c52b3ae592ff5570c83e82871d0f9ec87f29cb75bd5147b571cc"
    )
    assert qualification.canonical_file_sha256(REVEAL) == (
        "d071d9f75147d4247943d9f12d859f63a239b83e74ba2d7238becdc062493d00"
    )
    assert qualification.canonical_file_sha256(COVERAGE) == (
        "abf28fdc011a8e37844914b4ba660994c184457119031efe5b8b02d21a67b791"
    )
    assert qualification.canonical_file_sha256(
        ROOT / qualification.OUTCOME_NAME
    ) == retry.HISTORICAL_OUTCOME_CANONICAL_SHA256


def test_coverage_is_structural_only_and_strict_json_lines() -> None:
    raw = COVERAGE.read_bytes().replace(b"\r\n", b"\n")
    rows = [json.loads(line) for line in raw.splitlines()]

    assert len(rows) == 139 * 11 * 4
    assert b'"value"' not in raw
    assert b"NaN" not in raw
    assert b"Infinity" not in raw
    assert sum(row["state"] == "PRESENT" for row in rows) == 4_690
    assert sum(row["state"] == "BLANK" for row in rows) == 138
    assert sum(row["state"] == "FIELD_ABSENT" for row in rows) == 1_288


def test_physical_decisions_remain_outside_structural_refusal() -> None:
    outcome = load(OUTCOME)

    assert outcome["clause_states"]["measurement_admission"] == "NOT_EVALUATED"
    assert outcome["clause_states"]["orbital_score"] == "NOT_EVALUATED"
    assert outcome["clause_states"]["primary_selection"] == "NOT_EVALUATED"


def test_consumed_retry_refuses_before_materialization(monkeypatch) -> None:
    monkeypatch.setattr(
        retry,
        "materialize_exact",
        lambda: pytest.fail("consumed retry attempted another materialization"),
    )

    with pytest.raises(retry.RetryAuthorityError, match="RETRY_OUTPUT_ALREADY_EXISTS"):
        retry.run_retry_once(ROOT)
