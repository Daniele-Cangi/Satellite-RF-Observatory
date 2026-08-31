from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

import pytest

from experiments.live_instrument.orbital_kernel import compute_orbital_state
from experiments.orbital_discriminability.meteor_m2_4_visibility_shortlist import (
    GEOMETRY_OUTCOME,
    NOMINAL_TLE,
    OVERALL_BLOCKED_OUTCOME,
    VisibilitySamples,
    _pass_groups,
    _sample_elevations,
    _segments_from_samples,
    _strict_hash,
    evaluate_meteor_m2_4_shortlist,
    YO3BN,
)


@pytest.fixture(scope="module")
def receipt() -> dict[str, object]:
    return evaluate_meteor_m2_4_shortlist()


def test_vectorized_elevation_matches_frozen_orbital_kernel() -> None:
    start = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
    samples = _sample_elevations(
        NOMINAL_TLE,
        YO3BN,
        start,
        start + timedelta(seconds=10),
        5.0,
    )

    scalar = compute_orbital_state(YO3BN, NOMINAL_TLE, start + timedelta(seconds=5))

    assert samples.elevation_deg[1] == pytest.approx(scalar.elevation_deg, abs=1e-10)


def test_both_occulted_breaks_pass_groups() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = tuple(start + timedelta(seconds=5 * index) for index in range(7))
    left = VisibilitySamples(timestamps, (6.0, 6.0, -3.0, -3.0, -3.0, 6.0, 6.0))
    right = VisibilitySamples(timestamps, (-3.0, 6.0, 6.0, -3.0, 6.0, 6.0, -3.0))

    groups = _pass_groups(_segments_from_samples(left, right))

    assert len(groups) == 2
    assert all(segment.state != "BOTH_OCCULTED" for group in groups for segment in group)


def test_shortlist_has_two_positive_passes_and_one_boundary(
    receipt: dict[str, object],
) -> None:
    assert receipt["geometry_outcome"] == GEOMETRY_OUTCOME
    shortlist = receipt["doncaster_bucharest_shortlist"]
    assert len(shortlist) == 3
    assert [item["classification"] for item in shortlist] == [
        "GEOMETRY_MARGIN_POSITIVE",
        "GEOMETRY_MARGIN_POSITIVE",
        "GEOMETRY_BOUNDARY_NOT_ADMITTED",
    ]
    assert shortlist[0]["robust_controlling_duration_s"] == 90.0
    assert shortlist[0]["maximum_per_root_event_time_error_s"] == 30.0
    assert shortlist[1]["robust_controlling_duration_s"] == 80.0
    assert shortlist[2]["minimum_dwell_margin_s"] == 0.0


def test_geometry_does_not_promote_an_unqualified_measurement_path(
    receipt: dict[str, object],
) -> None:
    assert receipt["outcome"] == OVERALL_BLOCKED_OUTCOME
    assert receipt["exact_blocker"]["type"] == "NO_PAIR_OF_MEASUREMENT_CAPABILITIES_ADMITTED"
    assert all(
        item["state"] == "CAPABILITY_DISCOVERED_NOT_ADMITTED"
        for item in receipt["bounded_capability_set"]
    )
    assert receipt["rf_connections"] == 0
    assert receipt["rf_bytes_accessed"] == 0
    assert receipt["observation_values_accessed"] == 0


def test_receipt_is_strict_json_and_hashes_are_reproducible(
    receipt: dict[str, object],
) -> None:
    json.dumps(receipt, sort_keys=True, allow_nan=False)
    assert receipt["plan_sha256"] == _strict_hash(receipt["plan"])
    omm = receipt["orbit_sources"]["current_omm_description"]
    assert omm["omm_sha256"] == _strict_hash(omm["omm"])
