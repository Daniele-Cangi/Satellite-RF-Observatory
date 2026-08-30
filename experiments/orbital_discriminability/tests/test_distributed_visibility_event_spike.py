from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from experiments.live_instrument.orbital_kernel import Observer
from experiments.orbital_discriminability.distributed_visibility_event_spike import (
    OUTCOME_ADMITTED,
    _state_segments,
    _strict_hash,
    evaluate_visibility_event_spike,
)
from experiments.orbital_discriminability.trajectory import OrbitalTrajectory


def _trajectory(elevations: tuple[float, ...]) -> OrbitalTrajectory:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    timestamps = tuple(start + timedelta(seconds=5 * i) for i in range(len(elevations)))
    zeros = tuple(0.0 for _ in elevations)
    return OrbitalTrajectory(
        observer=Observer(0.0, 0.0),
        timestamps=timestamps,
        elapsed_s=tuple(float(5 * i) for i in range(len(elevations))),
        elevation_deg=elevations,
        azimuth_deg=zeros,
        slant_range_km=tuple(1.0 for _ in elevations),
        range_rate_km_s=zeros,
        fractional_doppler=zeros,
        fractional_slope_s_inv=zeros,
        fractional_curvature_s2_inv=zeros,
        visibility_mask=tuple(value >= 0.0 for value in elevations),
        closest_approach_time=timestamps[len(timestamps) // 2],
        range_rate_zero_crossings=(),
    )


@pytest.fixture(scope="module")
def spike_receipt() -> dict[str, object]:
    return evaluate_visibility_event_spike()


def test_transition_band_is_excluded_and_segments_are_conservative() -> None:
    left = _trajectory((6.0, 6.0, 1.0, 6.0, 6.0))
    right = _trajectory((-3.0, -3.0, 1.0, 6.0, 6.0))

    segments = _state_segments(left, right)

    assert [segment.state for segment in segments] == [
        "LEFT_VISIBLE_RIGHT_OCCULTED",
        "EXCLUDED_TRANSITION_BAND",
        "BOTH_VISIBLE",
    ]
    assert [segment.conservative_duration_s for segment in segments] == [5.0, 0.0, 5.0]


def test_fixed_spike_admits_orbitality_but_not_specific_orbit_identity(
    spike_receipt: dict[str, object],
) -> None:
    assert spike_receipt["outcome"] == OUTCOME_ADMITTED
    selected = spike_receipt["selected_geometry"]
    assert selected["left"] == "DUBLIN_GEOMETRY"
    assert selected["right"] == "ROME_GEOMETRY"
    assert selected["topology"] == "LEFT_ONLY_TO_BOTH_TO_RIGHT_ONLY"
    assert selected["dwell_margin_s"] > 0.0
    assert selected["maximum_frame_cadence_s"] > 0.0
    assert spike_receipt["specific_orbit_identity_check"]["classification"] == (
        "SPECIFIC_ORBIT_NOT_DISCRIMINATIVE_AT_THIS_BOUND"
    )
    assert spike_receipt["network_connections"] == 0
    assert spike_receipt["rf_bytes_accessed"] == 0
    assert len(spike_receipt["plan_sha256"]) == 64


def test_plan_hash_is_strict_and_reproducible_without_repropagation(
    spike_receipt: dict[str, object],
) -> None:
    assert spike_receipt["plan_sha256"] == _strict_hash(spike_receipt["plan"])
