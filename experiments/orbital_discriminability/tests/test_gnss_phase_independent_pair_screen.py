from __future__ import annotations

import json

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_phase_independent_pair_screen as screen,
)


EXPECTED_CANDIDATES = (
    "DRAO00CAN",
    "WES200USA",
    "ALGO00CAN",
    "PIE100USA",
    "AMC400USA",
    "MDO100USA",
)


def test_candidate_set_is_exact_unique_and_disjoint_from_consumed_roots() -> None:
    identifiers = tuple(candidate.station_id for candidate in screen.CANDIDATES)
    roots = tuple(
        screen._station(candidate).measurement_root
        for candidate in screen.CANDIDATES
    )

    assert identifiers == EXPECTED_CANDIDATES
    assert len(set(identifiers)) == len(identifiers)
    assert len(set(roots)) == len(roots)
    assert not ({"GOLD00USA", "NLIB00USA"} & set(identifiers))
    assert all(
        len(candidate.station_page_sha256) == 64
        for candidate in screen.CANDIDATES
    )
    assert all(
        len(candidate.station_log_sha256) == 64
        for candidate in screen.CANDIDATES
    )


def test_manifest_has_no_observation_or_network_input_surface() -> None:
    manifest = screen.manifest()

    assert manifest["candidate_root_state"] == (
        "CANDIDATE_SITE_ROOT_NOT_YET_CAPABILITY_QUALIFIED"
    )
    assert manifest["observation_boundary"] == {
        "product_locators": 0,
        "products_discovered": 0,
        "headers": 0,
        "payload_bytes": 0,
        "values": 0,
        "decoder_present": False,
        "network_capability": False,
    }
    assert manifest["not_a_plan_freeze"] is True
    assert manifest["new_gate"] is False
    assert manifest["generic_framework"] is False
    assert len(screen.manifest_sha256()) == 64


def test_rank_is_strict_positive_then_margin_elevation_and_lexical() -> None:
    rows = [
        {
            "station_pair": ["B", "C"],
            "admissible_geometry": True,
            "remaining_physical_margin_m": 10.0,
            "minimum_model_elevation_deg": 20.0,
        },
        {
            "station_pair": ["A", "C"],
            "admissible_geometry": True,
            "remaining_physical_margin_m": 10.0,
            "minimum_model_elevation_deg": 21.0,
        },
        {
            "station_pair": ["A", "B"],
            "admissible_geometry": True,
            "remaining_physical_margin_m": 10.0,
            "minimum_model_elevation_deg": 21.0,
        },
        {
            "station_pair": ["D", "E"],
            "admissible_geometry": True,
            "remaining_physical_margin_m": 0.0,
            "minimum_model_elevation_deg": 80.0,
        },
        {
            "station_pair": ["E", "F"],
            "admissible_geometry": False,
            "remaining_physical_margin_m": 100.0,
            "minimum_model_elevation_deg": 80.0,
        },
    ]

    assert [row["station_pair"] for row in screen.rank_rows(rows)] == [
        ["A", "B"],
        ["A", "C"],
        ["B", "C"],
    ]


def test_troposphere_recomputation_has_no_legacy_station_name_coupling() -> None:
    count = 139
    epochs = np.arange(count, dtype=np.float64)
    elevations = {
        ("DRAO00CAN", "G22"): 35.0 + 0.03 * epochs,
        ("DRAO00CAN", "G30"): 50.0 - 0.02 * epochs,
        ("WES200USA", "G22"): 45.0 + 0.01 * epochs,
        ("WES200USA", "G30"): 60.0 - 0.015 * epochs,
    }

    term = screen.troposphere_term(
        elevations,
        "DRAO00CAN",
        "WES200USA",
        slice(1, count - 1),
    )

    assert term["term"] == "DIFFERENTIAL_TROPOSPHERE"
    assert term["heldout_peak_to_peak_bound_m"] > 0.0
    assert term["controlling_station_zenith_delays_m"] is not None


def test_invalid_navigation_and_nonfinite_json_are_rejected() -> None:
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("inf")})
    with pytest.raises(
        Exception,
        match="REPLICATION_NAVIGATION_GZIP_SIZE_CHANGED",
    ):
        screen.compile_screen_from_gzip(b"partial")


def test_manifest_round_trip_is_strict_json() -> None:
    assert json.loads(screen.strict_json(screen.manifest())) == screen.manifest()
