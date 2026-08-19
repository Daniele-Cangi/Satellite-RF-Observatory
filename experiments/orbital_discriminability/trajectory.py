"""Deterministic multi-observer trajectories for Gate G0.

The existing orbital kernel remains the only propagation authority.  This
module samples it on an explicit event-time grid and derives fractional
Doppler before any carrier frequency is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import pairwise
from math import isfinite
from typing import Mapping

import numpy as np

from experiments.live_instrument.orbital_kernel import (
    SPEED_OF_LIGHT_KM_S,
    Observer,
    OrbitalElements,
    OrbitalKernelError,
    compute_orbital_state,
)


MAX_TRAJECTORY_SAMPLES = 20_000


class TrajectoryError(ValueError):
    """Raised when a G0 trajectory or comparison grid is invalid."""


@dataclass(frozen=True, slots=True)
class OrbitalTrajectory:
    observer: Observer
    timestamps: tuple[datetime, ...]
    elapsed_s: tuple[float, ...]
    elevation_deg: tuple[float, ...]
    azimuth_deg: tuple[float, ...]
    slant_range_km: tuple[float, ...]
    range_rate_km_s: tuple[float, ...]
    fractional_doppler: tuple[float, ...]
    fractional_slope_s_inv: tuple[float, ...]
    fractional_curvature_s2_inv: tuple[float, ...]
    visibility_mask: tuple[bool, ...]
    closest_approach_time: datetime
    range_rate_zero_crossings: tuple[datetime, ...]

    @property
    def sample_count(self) -> int:
        return len(self.timestamps)


@dataclass(frozen=True, slots=True)
class DifferentialTrajectory:
    left_id: str
    right_id: str
    timestamps: tuple[datetime, ...]
    elapsed_s: tuple[float, ...]
    fractional_doppler: tuple[float, ...]
    fractional_slope_s_inv: tuple[float, ...]
    fractional_curvature_s2_inv: tuple[float, ...]
    joint_visibility_mask: tuple[bool, ...]


@dataclass(frozen=True, slots=True)
class FractionalTrajectoryEnvelope:
    timestamps: tuple[datetime, ...]
    nominal: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    maximum_absolute_deviation: float
    member_count: int


@dataclass(frozen=True, slots=True)
class FrequencyTrajectoryEnvelope:
    timestamps: tuple[datetime, ...]
    nominal_hz: tuple[float, ...]
    lower_hz: tuple[float, ...]
    upper_hz: tuple[float, ...]
    maximum_absolute_deviation_hz: float
    member_count: int
    time_shift_bound_s: float | None = None


def sample_orbital_trajectory(
    orbital_elements: OrbitalElements,
    observer: Observer,
    start_time: datetime,
    end_time: datetime,
    cadence_s: float,
    *,
    minimum_elevation_deg: float = 0.0,
) -> OrbitalTrajectory:
    """Sample one observer-relative orbit on an inclusive deterministic grid."""

    start = _aware_utc(start_time, "start_time")
    end = _aware_utc(end_time, "end_time")
    cadence = _positive_finite(cadence_s, "cadence_s")
    if end <= start:
        raise TrajectoryError("end_time must be after start_time")
    if not isfinite(minimum_elevation_deg) or not -90.0 <= minimum_elevation_deg <= 90.0:
        raise TrajectoryError("minimum_elevation_deg must be finite and in [-90, 90]")

    duration_s = (end - start).total_seconds()
    sample_count = int(duration_s // cadence) + 1
    if sample_count < 3:
        raise TrajectoryError("trajectory requires at least three samples")
    if sample_count > MAX_TRAJECTORY_SAMPLES:
        raise TrajectoryError(
            f"trajectory exceeds the {MAX_TRAJECTORY_SAMPLES} sample safety limit"
        )
    timestamps = tuple(start + timedelta(seconds=index * cadence) for index in range(sample_count))
    elapsed = np.asarray(
        [(timestamp - timestamps[0]).total_seconds() for timestamp in timestamps],
        dtype=np.float64,
    )

    try:
        states = tuple(
            compute_orbital_state(observer, orbital_elements, timestamp)
            for timestamp in timestamps
        )
    except OrbitalKernelError as error:
        raise TrajectoryError(str(error)) from error

    elevation = np.asarray([state.elevation_deg for state in states], dtype=np.float64)
    azimuth = np.asarray([state.azimuth_deg for state in states], dtype=np.float64)
    ranges = np.asarray([state.range_km for state in states], dtype=np.float64)
    range_rates = np.asarray([state.range_rate_km_s for state in states], dtype=np.float64)
    fractional = -range_rates / SPEED_OF_LIGHT_KM_S
    slope = np.gradient(fractional, elapsed, edge_order=2)
    curvature = np.gradient(slope, elapsed, edge_order=2)
    _require_finite(
        elevation,
        azimuth,
        ranges,
        range_rates,
        fractional,
        slope,
        curvature,
    )

    closest_index = int(np.argmin(ranges))
    return OrbitalTrajectory(
        observer=observer,
        timestamps=timestamps,
        elapsed_s=_tuple(elapsed),
        elevation_deg=_tuple(elevation),
        azimuth_deg=_tuple(azimuth),
        slant_range_km=_tuple(ranges),
        range_rate_km_s=_tuple(range_rates),
        fractional_doppler=_tuple(fractional),
        fractional_slope_s_inv=_tuple(slope),
        fractional_curvature_s2_inv=_tuple(curvature),
        visibility_mask=tuple(bool(value >= minimum_elevation_deg) for value in elevation),
        closest_approach_time=timestamps[closest_index],
        range_rate_zero_crossings=_zero_crossings(timestamps, range_rates),
    )


def sample_observer_network(
    orbital_elements: OrbitalElements,
    observers: Mapping[str, Observer],
    start_time: datetime,
    end_time: datetime,
    cadence_s: float,
    *,
    minimum_elevation_deg: float = 0.0,
) -> dict[str, OrbitalTrajectory]:
    """Sample named observers without introducing a sensor registry."""

    if len(observers) < 2:
        raise TrajectoryError("a distributed trajectory requires at least two observers")
    if any(not str(name).strip() for name in observers):
        raise TrajectoryError("observer identifiers must be non-empty")
    return {
        str(name): sample_orbital_trajectory(
            orbital_elements,
            observer,
            start_time,
            end_time,
            cadence_s,
            minimum_elevation_deg=minimum_elevation_deg,
        )
        for name, observer in sorted(observers.items())
    }


def sample_orbital_ensemble(
    nominal_elements: OrbitalElements,
    alternative_elements: Mapping[str, OrbitalElements],
    observers: Mapping[str, Observer],
    start_time: datetime,
    end_time: datetime,
    cadence_s: float,
    *,
    minimum_elevation_deg: float = 0.0,
) -> tuple[dict[str, OrbitalTrajectory], dict[str, FractionalTrajectoryEnvelope]]:
    """Propagate a frozen nominal orbit and a caller-declared orbit ensemble.

    Alternatives may be adjacent element sets or controlled perturbations.  No
    numerical uncertainty is inferred from TLE age alone.
    """

    if not alternative_elements:
        raise TrajectoryError("an orbital envelope requires at least one alternative")
    nominal = sample_observer_network(
        nominal_elements,
        observers,
        start_time,
        end_time,
        cadence_s,
        minimum_elevation_deg=minimum_elevation_deg,
    )
    alternatives = {
        name: sample_observer_network(
            elements,
            observers,
            start_time,
            end_time,
            cadence_s,
            minimum_elevation_deg=minimum_elevation_deg,
        )
        for name, elements in sorted(alternative_elements.items())
    }
    envelopes = {
        station: build_fractional_envelope(
            nominal[station],
            tuple(network[station] for network in alternatives.values()),
        )
        for station in nominal
    }
    return nominal, envelopes


def build_fractional_envelope(
    nominal: OrbitalTrajectory,
    alternatives: tuple[OrbitalTrajectory, ...],
) -> FractionalTrajectoryEnvelope:
    if not alternatives:
        raise TrajectoryError("a fractional envelope requires at least one alternative")
    if any(item.timestamps != nominal.timestamps for item in alternatives):
        raise TrajectoryError("orbital envelope members must share one event-time grid")
    nominal_values = np.asarray(nominal.fractional_doppler, dtype=np.float64)
    members = np.vstack(
        (nominal_values, *(np.asarray(item.fractional_doppler) for item in alternatives))
    )
    if not np.all(np.isfinite(members)):
        raise TrajectoryError("orbital envelope contains a non-finite member")
    lower = np.min(members, axis=0)
    upper = np.max(members, axis=0)
    maximum_deviation = float(np.max(np.abs(members - nominal_values)))
    return FractionalTrajectoryEnvelope(
        nominal.timestamps,
        _tuple(nominal_values),
        _tuple(lower),
        _tuple(upper),
        maximum_deviation,
        len(alternatives) + 1,
    )


def apply_carrier_to_envelope(
    envelope: FractionalTrajectoryEnvelope,
    carrier_hz: float,
) -> FrequencyTrajectoryEnvelope:
    carrier = _positive_finite(carrier_hz, "carrier_hz")
    nominal = np.asarray(envelope.nominal) * carrier
    lower = np.asarray(envelope.lower) * carrier
    upper = np.asarray(envelope.upper) * carrier
    return FrequencyTrajectoryEnvelope(
        envelope.timestamps,
        _tuple(nominal),
        _tuple(lower),
        _tuple(upper),
        float(envelope.maximum_absolute_deviation * carrier),
        envelope.member_count,
    )


def build_time_shift_frequency_envelope(
    orbital_elements: OrbitalElements,
    nominal: OrbitalTrajectory,
    carrier_hz: float,
    maximum_clock_error_s: float,
) -> FrequencyTrajectoryEnvelope:
    """Bound timing error with direct trajectory samples at ``t ± Δt``.

    This is deliberately not a local derivative approximation.  The nominal
    event-time grid is propagated at both declared clock-error endpoints and
    the resulting frequency interval is retained sample by sample.
    """

    carrier = _positive_finite(carrier_hz, "carrier_hz")
    try:
        clock_error = float(maximum_clock_error_s)
    except (TypeError, ValueError) as error:
        raise TrajectoryError(
            "maximum_clock_error_s must be finite and non-negative"
        ) from error
    if not isfinite(clock_error) or clock_error < 0.0:
        raise TrajectoryError("maximum_clock_error_s must be finite and non-negative")

    nominal_hz = np.asarray(nominal.fractional_doppler, dtype=np.float64) * carrier
    if clock_error == 0.0:
        return FrequencyTrajectoryEnvelope(
            nominal.timestamps,
            _tuple(nominal_hz),
            _tuple(nominal_hz),
            _tuple(nominal_hz),
            0.0,
            1,
            0.0,
        )

    delta = timedelta(seconds=clock_error)
    try:
        shifted_fractional = np.asarray(
            [
                [
                    -compute_orbital_state(
                        nominal.observer,
                        orbital_elements,
                        timestamp + direction * delta,
                    ).range_rate_km_s
                    / SPEED_OF_LIGHT_KM_S
                    for timestamp in nominal.timestamps
                ]
                for direction in (-1, 1)
            ],
            dtype=np.float64,
        )
    except OrbitalKernelError as error:
        raise TrajectoryError(str(error)) from error
    shifted_hz = shifted_fractional * carrier
    members = np.vstack((nominal_hz, shifted_hz))
    _require_finite(members)
    lower = np.min(members, axis=0)
    upper = np.max(members, axis=0)
    return FrequencyTrajectoryEnvelope(
        nominal.timestamps,
        _tuple(nominal_hz),
        _tuple(lower),
        _tuple(upper),
        float(np.max(np.abs(members - nominal_hz))),
        3,
        clock_error,
    )


def differential_time_shift_uncertainty_hz(
    left: FrequencyTrajectoryEnvelope,
    right: FrequencyTrajectoryEnvelope,
    valid_mask: tuple[bool, ...] | np.ndarray,
) -> float:
    """Return the worst pairwise differential deviation inside two envelopes."""

    if left.timestamps != right.timestamps:
        raise TrajectoryError("time-shift envelopes must share one event-time grid")
    mask = np.asarray(valid_mask, dtype=bool)
    if mask.shape != (len(left.timestamps),) or not np.any(mask):
        raise TrajectoryError("time-shift uncertainty requires a non-empty valid mask")
    left_nominal = np.asarray(left.nominal_hz, dtype=np.float64)
    right_nominal = np.asarray(right.nominal_hz, dtype=np.float64)
    nominal = left_nominal - right_nominal
    lower = np.asarray(left.lower_hz, dtype=np.float64) - np.asarray(
        right.upper_hz, dtype=np.float64
    )
    upper = np.asarray(left.upper_hz, dtype=np.float64) - np.asarray(
        right.lower_hz, dtype=np.float64
    )
    values = np.maximum(np.abs(lower - nominal), np.abs(upper - nominal))
    if not np.all(np.isfinite(values)):
        raise TrajectoryError("time-shift uncertainty contains a non-finite value")
    return float(np.max(values[mask]))


def differential_trajectory(
    left_id: str,
    left: OrbitalTrajectory,
    right_id: str,
    right: OrbitalTrajectory,
) -> DifferentialTrajectory:
    """Subtract simultaneous observer trajectories on their exact time grid."""

    if left_id == right_id:
        raise TrajectoryError("differential trajectories require distinct observers")
    if left.timestamps != right.timestamps:
        raise TrajectoryError("observer trajectories must share the exact event-time grid")
    left_fractional = np.asarray(left.fractional_doppler)
    right_fractional = np.asarray(right.fractional_doppler)
    left_slope = np.asarray(left.fractional_slope_s_inv)
    right_slope = np.asarray(right.fractional_slope_s_inv)
    left_curvature = np.asarray(left.fractional_curvature_s2_inv)
    right_curvature = np.asarray(right.fractional_curvature_s2_inv)
    return DifferentialTrajectory(
        left_id=str(left_id),
        right_id=str(right_id),
        timestamps=left.timestamps,
        elapsed_s=left.elapsed_s,
        fractional_doppler=_tuple(left_fractional - right_fractional),
        fractional_slope_s_inv=_tuple(left_slope - right_slope),
        fractional_curvature_s2_inv=_tuple(left_curvature - right_curvature),
        joint_visibility_mask=tuple(
            left_visible and right_visible
            for left_visible, right_visible in zip(
                left.visibility_mask, right.visibility_mask, strict=True
            )
        ),
    )


def apply_carrier_hz(
    fractional_doppler: tuple[float, ...] | list[float] | np.ndarray,
    carrier_hz: float,
) -> tuple[float, ...]:
    """Scale a dimensionless geometric prediction into hertz."""

    carrier = _positive_finite(carrier_hz, "carrier_hz")
    values = np.asarray(fractional_doppler, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise TrajectoryError("fractional_doppler must be a finite non-empty vector")
    return _tuple(values * carrier)


def pairwise_differentials(
    trajectories: Mapping[str, OrbitalTrajectory],
) -> dict[tuple[str, str], DifferentialTrajectory]:
    """Return every deterministic observer pair in lexical order."""

    names = sorted(trajectories)
    if len(names) < 2:
        raise TrajectoryError("at least two trajectories are required")
    return {
        (left_name, right_name): differential_trajectory(
            left_name,
            trajectories[left_name],
            right_name,
            trajectories[right_name],
        )
        for left_index, left_name in enumerate(names)
        for right_name in names[left_index + 1 :]
    }


def _aware_utc(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise TrajectoryError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _positive_finite(value: float, name: str) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise TrajectoryError(f"{name} must be finite and positive") from error
    if not isfinite(numeric) or numeric <= 0.0:
        raise TrajectoryError(f"{name} must be finite and positive")
    return numeric


def _require_finite(*arrays: np.ndarray) -> None:
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise TrajectoryError("trajectory derivation produced a non-finite value")


def _tuple(values: np.ndarray) -> tuple[float, ...]:
    return tuple(float(value) for value in values)


def _zero_crossings(
    timestamps: tuple[datetime, ...],
    values: np.ndarray,
) -> tuple[datetime, ...]:
    crossings: list[datetime] = []
    for index, (left, right) in enumerate(pairwise(values)):
        if left == 0.0:
            crossings.append(timestamps[index])
            continue
        if left * right > 0.0:
            continue
        fraction = abs(float(left)) / (abs(float(left)) + abs(float(right)))
        interval = timestamps[index + 1] - timestamps[index]
        crossings.append(timestamps[index] + interval * fraction)
    return tuple(crossings)
