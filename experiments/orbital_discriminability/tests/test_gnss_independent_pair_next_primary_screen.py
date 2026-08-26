from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as screen,
)


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


def test_manifest_round_trip_is_strict_json() -> None:
    assert json.loads(screen.strict_json(screen.manifest())) == screen.manifest()
