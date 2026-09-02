"""Tests for the bounded DORIS time-reference geometry screen."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import doris_forward_geometry_spike as base
from experiments.orbital_discriminability import doris_time_reference_geometry_screen as screen


RECEIPT = (
    Path(__file__).parents[1] / "DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_RECEIPT.json"
)


def _trajectory(satellite_id: str, radius_m: float) -> base.Sp3Trajectory:
    times = np.arange(0.0, 172_801.0, 60.0)
    angle = times * (2.0 * np.pi / 6_060.0)
    positions = np.column_stack(
        (radius_m * np.cos(angle), radius_m * np.sin(angle), np.zeros_like(angle))
    )
    angular_rate = 2.0 * np.pi / 6_060.0
    velocities = np.column_stack(
        (
            -radius_m * angular_rate * np.sin(angle),
            radius_m * angular_rate * np.cos(angle),
            np.zeros_like(angle),
        )
    )
    return base.Sp3Trajectory(
        satellite_id=satellite_id,
        start_tai=datetime(2026, 9, 1, tzinfo=timezone.utc),
        times_tai_s=times,
        positions_m=positions,
        velocities_mps=velocities,
        header="SYNTHETIC_TEST_ONLY",
    )


def test_scope_is_exactly_the_six_frozen_time_reference_pairs() -> None:
    receipt = screen.validate_topology_receipt()
    assert tuple(
        tuple(pair)
        for pair in receipt["time_reference_scope"][
            "bounded_pair_set_for_later_geometry_only_review"
        ]
    ) == screen.PAIRS
    assert len(screen.STATIONS) == 4
    assert len(screen.PAIRS) == 6


def test_conservative_cap_expands_for_normal_offset() -> None:
    radial = screen.conservative_visibility_cap_deg(
        station_radius_m=6_378_137.0,
        satellite_radius_ceiling_m=7_200_000.0,
        minimum_elevation_deg=10.0,
        normal_offset_deg=0.0,
    )
    tilted = screen.conservative_visibility_cap_deg(
        station_radius_m=6_378_137.0,
        satellite_radius_ceiling_m=7_200_000.0,
        minimum_elevation_deg=10.0,
        normal_offset_deg=0.2,
    )
    assert tilted > radial


def test_synthetic_day_closes_all_pairs_before_null_scoring() -> None:
    result = screen.evaluate_visibility(
        _trajectory("L74", 7_200_000.0),
        _trajectory("L74", 7_200_000.0),
        _trajectory("L98", 7_200_000.0),
    )
    assert result["outcome"] == screen.OUTCOME_NO_JOINT_VISIBILITY
    assert result["null_evaluation"]["state"] == (
        "NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW"
    )
    assert result["decision"]["shortlist"] == []
    rows = result["continuous_visibility_proof"]["pair_results"]
    assert len(rows) == 6
    assert all(row["continuous_impossibility_excess_deg"] > 0.0 for row in rows)
    assert all(row["joint_grid_sample_count"] == 0 for row in rows)


def test_nonpositive_effective_elevation_is_rejected() -> None:
    with pytest.raises(
        screen.DorisTimeReferenceGeometryError,
        match="NONPOSITIVE_RADIAL_ELEVATION_BOUND",
    ):
        screen.conservative_visibility_cap_deg(
            station_radius_m=6_378_137.0,
            satellite_radius_ceiling_m=7_200_000.0,
            minimum_elevation_deg=0.1,
            normal_offset_deg=0.2,
        )


def test_frozen_receipt_closes_measurement_access_without_scoring_nulls() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["outcome"] == screen.OUTCOME_NO_JOINT_VISIBILITY
    assert receipt["scope"]["rinex_artifact_access"] == "ZERO"
    assert receipt["scope"]["observation_values_access"] == "ZERO"
    assert receipt["scope"]["orbital_score"] == (
        "NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW"
    )
    assert receipt["decision"]["measurement_access_authorized"] is False
    assert receipt["decision"]["shortlist"] == []
    assert receipt["ephemeral_orbit_artifact_retention"] == (
        "ZERO_AFTER_HASHED_ANALYSIS"
    )


def test_screen_has_no_observation_or_network_surface() -> None:
    source = inspect.getsource(screen)
    for forbidden in (
        "requests",
        "urllib",
        "ftplib",
        "s3arx",
        "open_rinex",
        "pseudorange",
        "phase_values",
    ):
        assert forbidden not in source
    assert "print(" not in source


def test_receipt_is_source_bound_and_strict_json() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    # The binding is portable across Windows and Linux checkouts.
    source = Path(screen.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert receipt["screen_source_sha256"] == sha256(source).hexdigest()
    encoded = screen.strict_json(receipt)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
