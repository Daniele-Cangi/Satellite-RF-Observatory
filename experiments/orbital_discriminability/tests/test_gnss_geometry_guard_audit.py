from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "GNSS_GEOMETRY_GUARD_AUDIT_RECEIPT.json"
HISTORICAL = ROOT / "GNSS_INDEPENDENT_QUALIFICATION_OUTCOME.json"


def test_no_candidate_is_promoted_without_frozen_pre_roll() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="ascii"))

    assert receipt["outcome"] == "NO_GEOMETRY_GUARDED_QUALIFICATION_ARTIFACT"
    assert receipt["selected_qualification_artifact"] is None
    assert receipt["candidate_dates_doy"] == [216, 217, 218, 219, 220]
    assert all(row["state"].startswith("NOT_ADMITTED_") for row in receipt["candidate_navigation"])
    assert receipt["frozen_requirements"] == {
        "allow_shortened_window": False,
        "candidate_satellites": ["G11", "G21"],
        "candidate_stations": ["GOLD00USA", "NLIB00USA"],
        "joint_visibility_guard_deg": 15.0,
        "preceding_guard_duration_s": 1800.0,
        "preceding_guard_minimum_elevation_deg": 15.0,
        "raw_epoch_count": 386,
        "sample_interval_s": 30.0,
    }


def test_geometry_guard_receipt_has_zero_observation_access() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="ascii"))

    assert receipt["observation_access"] == {
        "observation_artifacts_opened": 0,
        "observation_headers_opened": 0,
        "observation_payload_bytes": 0,
        "observation_values_accessed": 0,
        "primary_selected": False,
    }
    assert receipt["new_gate_created"] is False


def test_all_full_length_candidates_fail_only_the_pre_roll_cut() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="ascii"))
    full = [row for row in receipt["candidate_navigation"] if row["best_386_epoch_window"]]

    assert [row["doy"] for row in full] == [216, 219, 220]
    assert all(row["joint_segment_epochs"]["15_deg"] == 386 for row in full)
    assert all(
        row["best_386_epoch_window"]["preceding_30m_minimum_joint_elevation_deg"] < 15.0
        for row in full
    )
    assert all(row["affine_heldout_peak_to_peak_hz"] > 2_140.0 for row in full)


def test_historical_qualification_remains_closed() -> None:
    historical = json.loads(HISTORICAL.read_text(encoding="ascii"))

    assert historical["outcome"] == "GNSS_INDEPENDENT_QUALIFICATION_FAILED"
    assert historical["primary_selected"] is False
    assert historical["primary_accessed"] is False
