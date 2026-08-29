"""Offline tests for the bounded blind-orbit geometry screen."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_screen as screen,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / screen.RECEIPT_NAME
RECEIPT_SHA256 = "cddc9fcf0db1be7f55fde04f1bf51256c3a88edf2608871b3bc7e438bd167485"


def test_manifest_freezes_physical_question_and_zero_observation_boundary() -> None:
    value = screen.manifest(ROOT)
    assert value["scope"] == {
        "filename": screen.SCOPE_NAME,
        "canonical_sha256": screen.SCOPE_SHA256,
        "scope_commit": screen.SCOPE_COMMIT,
    }
    assert value["population"] == {
        "system": "GPS",
        "target": "G22",
        "reference": "G30",
        "alternatives": "ALL_HEALTHY_G01_TO_G32_EXCEPT_G22_AND_G30",
        "family_size": 5,
        "selection": "FOUR_SMALLEST_HELDOUT_SEPARATIONS_THEN_PRN",
        "nonpositive_alternative_may_be_discarded": False,
    }
    assert value["observation_boundary"] == {
        "product_locators": 0,
        "products_discovered": 0,
        "headers": 0,
        "payload_bytes": 0,
        "values": 0,
        "decoders": 0,
    }
    assert value["prospective_plan_frozen"] is False
    assert value["primary_selected"] is False
    assert value["new_gate"] is False


def test_navigation_scope_is_exactly_five_predeclared_noaa_days() -> None:
    assert tuple(candidate.doy for candidate in screen.NAVIGATION_CANDIDATES) == (
        224,
        225,
        226,
        227,
        228,
    )
    assert tuple(candidate.name for candidate in screen.NAVIGATION_CANDIDATES) == (
        "brdc2240.26n.gz",
        "brdc2250.26n.gz",
        "brdc2260.26n.gz",
        "brdc2270.26n.gz",
        "brdc2280.26n.gz",
    )
    assert all(
        candidate.provider == "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE"
        for candidate in screen.NAVIGATION_CANDIDATES
    )


def test_prefix_affine_is_calibration_only_and_absorbs_exact_affine_curve() -> None:
    elapsed = np.arange(screen.RAW_EPOCHS) * screen.STEP_S
    exact_affine = 17.0 - 0.125 * elapsed
    result = screen.prefix_affine_separation(exact_affine)
    assert result["prefix_constant_m"] == pytest.approx(17.0, abs=1.0e-10)
    assert result["prefix_rate_m_s"] == pytest.approx(-0.125, abs=1.0e-12)
    assert result["prefix_rmse_m"] == pytest.approx(0.0, abs=1.0e-10)
    assert result["heldout_peak_to_peak_m"] == pytest.approx(0.0, abs=1.0e-9)

    curved = exact_affine + 2.0e-4 * elapsed**2
    mismatch = screen.prefix_affine_separation(curved)
    assert mismatch["heldout_peak_to_peak_m"] > 100.0
    assert mismatch["heldout_rms_m"] > 0.0


def test_nearest_family_keeps_a_controlling_nonpositive_alternative() -> None:
    alternatives = [
        {"satellite": "G01", "heldout_peak_to_peak_m": 20_000.0},
        {"satellite": "G02", "heldout_peak_to_peak_m": 1_000.0},
        {"satellite": "G03", "heldout_peak_to_peak_m": 30_000.0},
        {"satellite": "G04", "heldout_peak_to_peak_m": 40_000.0},
        {"satellite": "G05", "heldout_peak_to_peak_m": 50_000.0},
    ]
    selected = screen.select_nearest_family(alternatives)
    assert tuple(row["satellite"] for row in selected) == (
        "G02",
        "G01",
        "G03",
        "G04",
    )
    assert selected[0]["heldout_peak_to_peak_m"] < screen.PAIRWISE_GUARD_M


def _window(
    *,
    start: int,
    maximum: float,
    minimum_margin: float,
    elevation: float,
    admitted: bool = True,
) -> dict[str, object]:
    return {
        "doy": 224,
        "start_index": start,
        "maximum_family_separation_m": maximum,
        "minimum_remaining_margin_m": minimum_margin,
        "minimum_combined_remaining_margin_m": minimum_margin,
        "minimum_time_shifted_elevation_deg": elevation,
        "robustly_admissible": admitted,
    }


def test_ranking_prefers_difficulty_before_margin_or_elevation() -> None:
    rows = [
        _window(start=1, maximum=18_000.0, minimum_margin=8_000.0, elevation=50.0),
        _window(start=2, maximum=17_000.0, minimum_margin=7_500.0, elevation=20.0),
        _window(start=3, maximum=16_000.0, minimum_margin=20_000.0, elevation=60.0, admitted=False),
    ]
    ranked = screen.rank_admissible_windows(rows)
    assert [row["start_index"] for row in ranked] == [2, 1]


def test_strict_json_refuses_nonfinite_numbers() -> None:
    with pytest.raises(ValueError):
        screen.strict_json({"bad": np.nan})
    parsed = json.loads(screen.strict_json({"guard": screen.PAIRWISE_GUARD_M}))
    assert parsed["guard"] == screen.PAIRWISE_GUARD_M


def test_incomplete_navigation_payload_set_is_rejected_before_parsing() -> None:
    with pytest.raises(
        screen.BlindAssignmentScreenError,
        match="NAVIGATION_PAYLOAD_SET_CHANGED",
    ):
        screen.compile_screen({}, ROOT)


def test_committed_receipt_freezes_geometry_without_measurement_authority() -> None:
    canonical = RECEIPT.read_bytes().replace(b"\r\n", b"\n")
    assert len(canonical) == 46_895
    assert screen.canonical_sha256(RECEIPT) == RECEIPT_SHA256
    value = json.loads(canonical)
    assert value["outcome"] == screen.OUTCOME_SHORTLISTED
    assert value["source_commit"] == (
        "0f08f0956fc24dcbe4eabb7fa08314b02a15b743"
    )
    assert value["selected"]["doy"] == 226
    assert value["selected"]["raw_start_gps"] == "2026-08-14T06:14:30 GPS"
    assert value["selected"]["heldout_start_gps"] == "2026-08-14T06:54:00 GPS"
    assert value["selected"]["raw_stop_gps"] == "2026-08-14T07:23:30 GPS"
    assert value["selected"]["candidate_family"] == [
        "G22",
        "G06",
        "G14",
        "G17",
        "G19",
    ]
    assert value["selected"]["minimum_combined_remaining_margin_m"] == (
        pytest.approx(11_424.01533014155)
    )
    assert value["selected"]["minimum_time_shifted_elevation_deg"] == (
        pytest.approx(15.01043286179639)
    )
    assert value["observation_access"] == {
        "consumed_outcomes_reopened": 0,
        "headers": 0,
        "payload_bytes": 0,
        "product_locators": 0,
        "products_discovered": 0,
        "values": 0,
    }
    assert value["orbital_scores_from_measurements"] == 0
    assert value["qualification_artifact_selected"] is False
    assert value["primary_selected"] is False
    assert value["prospective_plan_frozen"] is False
    assert value["maximum_authorized_claim"] is None
