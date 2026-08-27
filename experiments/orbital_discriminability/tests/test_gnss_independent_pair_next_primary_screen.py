from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as screen,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / screen.RECEIPT_NAME


def test_scope_is_exact_new_dates_and_fixed_physical_hypothesis() -> None:
    assert tuple(candidate.doy for candidate in screen.NAVIGATION_CANDIDATES) == (
        221,
        222,
        223,
    )
    assert not (
        set(screen.CONSUMED_DOYS)
        & {candidate.doy for candidate in screen.NAVIGATION_CANDIDATES}
    )
    assert screen.TARGET == "G22"
    assert screen.REFERENCE == "G30"
    assert screen.WRONG_ORBITS == ("G01", "G14", "G17")
    assert tuple(station.station_id for station in screen.STATIONS) == (
        "ALGO00CAN",
        "MDO100USA",
    )
    assert len({station.measurement_root for station in screen.STATIONS}) == 2


def test_manifest_is_observation_blind_and_not_a_new_gate() -> None:
    manifest = screen.manifest()

    assert manifest["new_gate"] is False
    assert manifest["generic_framework"] is False
    assert manifest["prospective_plan_frozen"] is False
    assert manifest["closed_experiment"] == {
        "doy": 219,
        "terminal_outcome": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
        "reopened": False,
        "retried": False,
        "substituted": False,
    }
    assert manifest["observation_boundary"] == {
        "product_locators": 0,
        "products_discovered": 0,
        "headers": 0,
        "payload_bytes": 0,
        "values": 0,
        "decoder_present": False,
        "network_capability": False,
    }
    assert manifest["visibility"]["scope"] == (
        "ALL_139_RAW_EPOCHS_JOINTLY_VISIBLE"
    )
    assert len(screen.manifest_sha256()) == 64


def test_candidate_window_starts_respects_full_139_epoch_window() -> None:
    mask = np.zeros(400, dtype=bool)
    mask[10 : 10 + screen.RAW_EPOCHS - 1] = True
    mask[200 : 200 + screen.RAW_EPOCHS + 2] = True

    assert screen.candidate_window_starts(mask) == (200, 201, 202)


def test_candidate_window_starts_rejects_non_vector() -> None:
    with pytest.raises(screen.NextPrimaryScreenError):
        screen.candidate_window_starts(np.ones((2, 2), dtype=bool))


def test_rank_days_is_strict_positive_and_deterministic() -> None:
    rows = [
        {
            "doy": 221,
            "joint_visibility_complete": True,
            "remaining_physical_margin_m": 10.0,
            "controlling_heldout_separation_m": 20.0,
            "minimum_model_elevation_deg": 15.5,
            "raw_start_gps": "2026-08-09T01:00:00 GPS",
        },
        {
            "doy": 222,
            "joint_visibility_complete": True,
            "remaining_physical_margin_m": 10.0,
            "controlling_heldout_separation_m": 21.0,
            "minimum_model_elevation_deg": 15.1,
            "raw_start_gps": "2026-08-10T01:00:00 GPS",
        },
        {
            "doy": 223,
            "joint_visibility_complete": True,
            "remaining_physical_margin_m": 0.0,
            "controlling_heldout_separation_m": 100.0,
            "minimum_model_elevation_deg": 80.0,
            "raw_start_gps": "2026-08-11T01:00:00 GPS",
        },
    ]

    assert [row["doy"] for row in screen.rank_days(rows)] == [222, 221]


def test_navigation_set_and_nonfinite_json_are_rejected() -> None:
    with pytest.raises(
        screen.NextPrimaryScreenError,
        match="NAVIGATION_CANDIDATE_SET_CHANGED",
    ):
        screen.compile_screen({})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("inf")})


def _d(value: float) -> str:
    return f"{value:19.12E}".replace("E", "D")


def test_rinex2_parser_fixture_preserves_broadcast_fields() -> None:
    first = (
        f"{22:2d} {26:2d} {8:2d} {9:2d} {0:2d} {0:2d}{0.0:5.1f}"
        + _d(1.0e-4)
        + _d(2.0e-12)
        + _d(0.0)
    )
    rows = (
        (1.0, 20.0, 3.0e-9, 0.5),
        (1.0e-6, 0.01, 2.0e-6, 5153.7),
        (86400.0, 3.0e-7, 1.5, 4.0e-7),
        (0.9, 200.0, 0.7, -8.0e-9),
        (1.0e-10, 0.0, 2430.0, 0.0),
        (2.0, 0.0, -2.0e-9, 10.0),
        (86410.0, 4.0, 0.0, 0.0),
    )
    lines = [first, *("   " + "".join(_d(value) for value in row) for row in rows)]

    record = screen.parse_rinex2_gps_record(lines)

    assert record.satellite == "G22"
    assert record.toc_gps == datetime(2026, 8, 9, tzinfo=timezone.utc)
    assert record.af0_s == pytest.approx(1.0e-4)
    assert record.eccentricity == pytest.approx(0.01)
    assert record.sqrt_a_m_sqrt == pytest.approx(5153.7)
    assert record.gps_week == 2430
    assert record.sv_health == 0
    assert record.fit_interval_h == pytest.approx(4.0)


def test_manifest_round_trip_is_strict_json() -> None:
    assert json.loads(screen.strict_json(screen.manifest())) == screen.manifest()


def test_frozen_screen_receipt_selects_doy223_without_observation_access() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    assert screen.canonical_sha256(RECEIPT) == (
        "2e5af124d25475900eb8b8f88535bb5ac70da10f6f2f3a796fe6f66699b330b3"
    )
    assert receipt["source_commit"] == (
        "7a5d88633fdb086590eaf29c1fad2e6b4d3ead59"
    )
    assert receipt["source_sha256"] == (
        "e252a6ba4f573df3b286656db9116c3adb6d6ab63a0b355a812bd4134a54ac9a"
    )
    assert receipt["source_sha256"] == screen.source_sha256()
    assert receipt["manifest_sha256"] == screen.manifest_sha256()
    assert receipt["outcome"] == screen.OUTCOME_SELECTED
    assert [row["doy"] for row in receipt["ranking"]] == [223, 222, 221]
    assert all(day["candidate_window_count"] == 165 for day in receipt["day_results"])
    assert all(day["day_admitted"] for day in receipt["day_results"])

    selected = receipt["selected"]
    assert selected["raw_start_gps"] == "2026-08-11T05:24:00 GPS"
    assert selected["raw_stop_gps"] == "2026-08-11T06:33:00 GPS"
    assert selected["heldout_start_gps"] == "2026-08-11T06:03:00 GPS"
    assert selected["controlling_null"] == "WRONG_ORBIT_G14"
    assert selected["controlling_heldout_separation_m"] == pytest.approx(
        54990.701676848694
    )
    assert selected["pairwise_comparison_envelope_m"] == pytest.approx(
        3142.1641485601226
    )
    assert selected["remaining_physical_margin_m"] == pytest.approx(
        51848.53752828857
    )
    assert selected["minimum_model_elevation_deg"] == pytest.approx(
        22.66366007669533
    )
    assert not any(receipt["observation_access"].values())
    assert receipt["prospective_plan_frozen"] is False
