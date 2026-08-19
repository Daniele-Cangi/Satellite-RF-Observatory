"""Deterministic synthetic observations and the Gate G0 capability sweep."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Mapping

import numpy as np

from experiments.live_instrument.orbital_kernel import Observer, OrbitalElements, TLEElements

from .heldout import HeldoutPlan, HeldoutResult, evaluate_heldout
from .trajectory import (
    FrequencyTrajectoryEnvelope,
    OrbitalTrajectory,
    apply_carrier_hz,
    build_time_shift_frequency_envelope,
    sample_observer_network,
)


ISS_TLE = TLEElements(
    name="ISS (ZARYA) — fixed G0 synthetic geometry",
    line1="1 25544U 98067A   19343.69339541  .00001764  00000-0  38792-4 0  9991",
    line2="2 25544  51.6439 211.2001 0007417  17.6667  85.6398 15.50103472202482",
)
ISS_OMM = {
    "OBJECT_NAME": "ISS (ZARYA)",
    "OBJECT_ID": "1998-067A",
    "EPOCH": "2019-12-09T16:38:29.363423",
    "MEAN_MOTION": 15.501034720000002,
    "ECCENTRICITY": 0.0007417,
    "INCLINATION": 51.6439,
    "RA_OF_ASC_NODE": 211.2001,
    "ARG_OF_PERICENTER": 17.6667,
    "MEAN_ANOMALY": 85.6398,
    "EPHEMERIS_TYPE": 0,
    "CLASSIFICATION_TYPE": "U",
    "NORAD_CAT_ID": 25544,
    "ELEMENT_SET_NO": 999,
    "REV_AT_EPOCH": 20248,
    "BSTAR": 3.8792e-05,
    "MEAN_MOTION_DOT": 1.764e-05,
    "MEAN_MOTION_DDOT": 0.0,
}
ISS_PLAUSIBLE_MISMATCH_OMM = {
    **ISS_OMM,
    # A controlled adjacent-orbit stress, not an empirical error estimate.
    # The offsets correspond to a small along-track/plane mismatch while
    # retaining the same LEO regime and epoch.
    "MEAN_ANOMALY": ISS_OMM["MEAN_ANOMALY"] + 0.12,
    "RA_OF_ASC_NODE": ISS_OMM["RA_OF_ASC_NODE"] + 0.03,
    "MEAN_MOTION": ISS_OMM["MEAN_MOTION"] - 0.0002,
}
PASS_START = datetime(2019, 12, 9, 16, 38, 29, tzinfo=timezone.utc)
PASS_END = PASS_START + timedelta(minutes=5)
CADENCE_S = 5.0

COPENHAGEN = Observer(55.6761, 12.5683, 20.0)
LAYOUTS: dict[str, Observer] = {
    "LOCAL_10_KM": Observer(55.6761, 12.7283, 20.0),
    "REGIONAL_80_KM": Observer(55.6761, 13.8483, 20.0),
    "BERLIN": Observer(52.5200, 13.4050, 34.0),
    "EINDHOVEN": Observer(51.4416, 5.4697, 20.0),
}


@dataclass(frozen=True, slots=True)
class SyntheticScenario:
    elapsed_s: tuple[float, ...]
    trajectories: dict[str, OrbitalTrajectory]
    orbital_predictions_hz: dict[str, tuple[float, ...]]
    observations_hz: dict[str, tuple[float, ...]]
    carrier_hz: float
    noise_sigma_hz: float
    dropout_fraction: float
    generation: str
    prediction_elements: OrbitalElements
    truth_trajectories: dict[str, OrbitalTrajectory] | None = None


@dataclass(frozen=True, slots=True)
class DiscriminabilityCase:
    layout: str
    baseline_km: float
    carrier_hz: float
    frequency_resolution_hz: float
    maximum_clock_error_s: float
    outcome: str
    signature_span_hz: float
    detectability_threshold_hz: float
    detectability_margin_hz: float
    orbital_holdout_rmse_hz: float
    best_null_name: str
    best_null_holdout_rmse_hz: float
    preference_margin_hz: float
    plan_hash: str


def make_orbital_scenario(
    observers: Mapping[str, Observer],
    *,
    carrier_hz: float = 145_800_000.0,
    noise_sigma_hz: float = 0.2,
    dropout_fraction: float = 0.0,
    seed: int = 700,
    start_time: datetime = PASS_START,
    end_time: datetime = PASS_END,
    cadence_s: float = CADENCE_S,
) -> SyntheticScenario:
    trajectories = sample_observer_network(
        ISS_TLE,
        observers,
        start_time,
        end_time,
        cadence_s,
    )
    predictions = {
        station: apply_carrier_hz(trajectory.fractional_doppler, carrier_hz)
        for station, trajectory in trajectories.items()
    }
    elapsed = next(iter(trajectories.values())).elapsed_s
    observations = _orbital_observations(
        elapsed,
        predictions,
        noise_sigma_hz=noise_sigma_hz,
        dropout_fraction=dropout_fraction,
        seed=seed,
    )
    return SyntheticScenario(
        elapsed_s=elapsed,
        trajectories=trajectories,
        orbital_predictions_hz=predictions,
        observations_hz=observations,
        carrier_hz=float(carrier_hz),
        noise_sigma_hz=float(noise_sigma_hz),
        dropout_fraction=float(dropout_fraction),
        generation="orbital_geometry_plus_predeclared_station_affine_nuisance",
        prediction_elements=ISS_TLE,
    )


def make_orbital_model_mismatch_scenario(
    observers: Mapping[str, Observer],
    *,
    carrier_hz: float = 145_800_000.0,
    noise_sigma_hz: float = 0.2,
    seed: int = 701,
    start_time: datetime = PASS_START,
    end_time: datetime = PASS_END,
    cadence_s: float = CADENCE_S,
) -> SyntheticScenario:
    """Generate data from a nearby plausible orbit while scoring the nominal orbit."""

    nominal = sample_observer_network(
        ISS_TLE, observers, start_time, end_time, cadence_s
    )
    truth = sample_observer_network(
        ISS_PLAUSIBLE_MISMATCH_OMM, observers, start_time, end_time, cadence_s
    )
    predictions = {
        station: apply_carrier_hz(trajectory.fractional_doppler, carrier_hz)
        for station, trajectory in nominal.items()
    }
    truth_hz = {
        station: apply_carrier_hz(trajectory.fractional_doppler, carrier_hz)
        for station, trajectory in truth.items()
    }
    elapsed = next(iter(nominal.values())).elapsed_s
    observations = _orbital_observations(
        elapsed,
        truth_hz,
        noise_sigma_hz=noise_sigma_hz,
        dropout_fraction=0.0,
        seed=seed,
    )
    return SyntheticScenario(
        elapsed_s=elapsed,
        trajectories=nominal,
        orbital_predictions_hz=predictions,
        observations_hz=observations,
        carrier_hz=float(carrier_hz),
        noise_sigma_hz=float(noise_sigma_hz),
        dropout_fraction=0.0,
        generation="plausible_adjacent_orbit_truth_scored_against_nominal_orbit",
        prediction_elements=ISS_TLE,
        truth_trajectories=truth,
    )


def heldout_physical_context(
    scenario: SyntheticScenario,
    maximum_clock_error_s: float,
) -> tuple[
    dict[str, tuple[bool, ...]],
    dict[str, FrequencyTrajectoryEnvelope],
]:
    """Derive the visibility and direct timing envelope used by G0 scoring."""

    visibility = {
        station: trajectory.visibility_mask
        for station, trajectory in scenario.trajectories.items()
    }
    envelopes = {
        station: build_time_shift_frequency_envelope(
            scenario.prediction_elements,
            trajectory,
            scenario.carrier_hz,
            maximum_clock_error_s,
        )
        for station, trajectory in scenario.trajectories.items()
    }
    return visibility, envelopes


def make_nonorbital_observations(
    elapsed_s: tuple[float, ...],
    station_ids: tuple[str, ...],
    *,
    mode: str,
    amplitude_hz: float = 80.0,
) -> dict[str, tuple[float, ...]]:
    """Generate deterministic null-shaped data on an existing time grid."""

    times = np.asarray(elapsed_s, dtype=np.float64)
    normalized = (times - times[0]) / (times[-1] - times[0])
    if mode not in {"affine", "common_cubic"}:
        raise ValueError("mode must be 'affine' or 'common_cubic'")
    common = (
        np.zeros_like(times)
        if mode == "affine"
        else amplitude_hz * (np.square(normalized) - 0.65 * np.power(normalized, 3))
    )
    return {
        station: tuple(
            float(value)
            for value in (
                common
                + 17.0 * index
                + ((-1.0) ** index) * 0.035 * times
            )
        )
        for index, station in enumerate(sorted(station_ids))
    }


def add_holdout_curvature(
    scenario: SyntheticScenario,
    calibration_fraction: float,
    *,
    amplitude_hz: float,
) -> dict[str, tuple[float, ...]]:
    """Corrupt only the future suffix; useful for proving no holdout leakage."""

    observations = {
        station: np.asarray(values, dtype=np.float64).copy()
        for station, values in scenario.observations_hz.items()
    }
    start = int(np.ceil(len(scenario.elapsed_s) * calibration_fraction))
    holdout_count = len(scenario.elapsed_s) - start
    shape = amplitude_hz * np.square(np.linspace(0.0, 1.0, holdout_count))
    for index, station in enumerate(sorted(observations)):
        observations[station][start:] += ((-1.0) ** index) * shape
    return {
        station: tuple(float(value) for value in values)
        for station, values in observations.items()
    }


def run_discriminability_sweep(
    *,
    carriers_hz: tuple[float, ...] = (137_500_000.0, 435_000_000.0),
    resolutions_hz: tuple[float, ...] = (1.0, 5.0, 20.0, 100.0),
    clock_errors_s: tuple[float, ...] = (0.0, 1.0, 5.0, 30.0),
) -> tuple[DiscriminabilityCase, ...]:
    """Map geometry and measurement envelopes without touching a receiver."""

    all_observers = {"COPENHAGEN": COPENHAGEN, **LAYOUTS}
    all_trajectories = sample_observer_network(
        ISS_TLE,
        all_observers,
        PASS_START,
        PASS_END,
        CADENCE_S,
    )
    elapsed = all_trajectories["COPENHAGEN"].elapsed_s
    direct_clock_envelopes = {
        (float(carrier_hz), float(clock_error_s), station): (
            build_time_shift_frequency_envelope(
                ISS_TLE,
                trajectory,
                carrier_hz,
                clock_error_s,
            )
        )
        for carrier_hz in carriers_hz
        for clock_error_s in clock_errors_s
        for station, trajectory in all_trajectories.items()
    }
    cases: list[DiscriminabilityCase] = []
    for layout, second_observer in LAYOUTS.items():
        station_ids = ("COPENHAGEN", layout)
        trajectories = {station: all_trajectories[station] for station in station_ids}
        baseline_km = _haversine_km(COPENHAGEN, second_observer)
        for carrier_hz in carriers_hz:
            predictions = {
                station: apply_carrier_hz(
                    trajectories[station].fractional_doppler,
                    carrier_hz,
                )
                for station in station_ids
            }
            visibility = {
                station: trajectories[station].visibility_mask
                for station in station_ids
            }
            observations = _orbital_observations(
                elapsed,
                predictions,
                noise_sigma_hz=0.2,
                dropout_fraction=0.0,
                seed=700,
            )
            for resolution_hz in resolutions_hz:
                for clock_error_s in clock_errors_s:
                    clock_envelopes = {
                        station: direct_clock_envelopes[
                            (float(carrier_hz), float(clock_error_s), station)
                        ]
                        for station in station_ids
                    }
                    plan = HeldoutPlan(
                        frequency_resolution_hz=float(resolution_hz),
                        maximum_clock_error_s=float(clock_error_s),
                        orbital_prediction_uncertainty_hz=1.0,
                    )
                    result = evaluate_heldout(
                        elapsed,
                        observations,
                        predictions,
                        plan,
                        visibility_masks=visibility,
                        clock_envelopes_hz=clock_envelopes,
                    )
                    cases.append(
                        _case(
                            layout,
                            baseline_km,
                            carrier_hz,
                            resolution_hz,
                            clock_error_s,
                            result,
                        )
                    )
    return tuple(cases)


def _orbital_observations(
    elapsed_s: tuple[float, ...],
    predictions_hz: Mapping[str, tuple[float, ...]],
    *,
    noise_sigma_hz: float,
    dropout_fraction: float,
    seed: int,
) -> dict[str, tuple[float, ...]]:
    if noise_sigma_hz < 0.0 or not 0.0 <= dropout_fraction < 1.0:
        raise ValueError("noise and dropout bounds are invalid")
    times = np.asarray(elapsed_s, dtype=np.float64)
    rng = np.random.default_rng(seed)
    result: dict[str, tuple[float, ...]] = {}
    for index, station in enumerate(sorted(predictions_hz)):
        prediction = np.asarray(predictions_hz[station], dtype=np.float64)
        station_offset = 23.0 * index - 11.0
        station_drift = ((-1.0) ** index) * 0.018
        common_affine_transmitter_drift = 0.006 * times
        observed = (
            prediction
            + station_offset
            + station_drift * times
            + common_affine_transmitter_drift
            + rng.normal(0.0, noise_sigma_hz, size=times.size)
        )
        dropout_count = int(np.floor(dropout_fraction * times.size))
        if dropout_count:
            # Dropouts are confined to a deterministic subset but never the
            # entire calibration or held-out region.
            candidates = np.arange(2, times.size - 2)
            dropped = rng.choice(candidates, size=dropout_count, replace=False)
            observed[dropped] = np.nan
        result[station] = tuple(float(value) for value in observed)
    return result


def _case(
    layout: str,
    baseline_km: float,
    carrier_hz: float,
    resolution_hz: float,
    clock_error_s: float,
    result: HeldoutResult,
) -> DiscriminabilityCase:
    return DiscriminabilityCase(
        layout=layout,
        baseline_km=float(baseline_km),
        carrier_hz=float(carrier_hz),
        frequency_resolution_hz=float(resolution_hz),
        maximum_clock_error_s=float(clock_error_s),
        outcome=result.outcome,
        signature_span_hz=result.differential_signature_span_hz,
        detectability_threshold_hz=result.detectability_threshold_hz,
        detectability_margin_hz=result.detectability_margin_hz,
        orbital_holdout_rmse_hz=result.orbital_score.holdout_rmse_hz,
        best_null_name=result.best_null_name,
        best_null_holdout_rmse_hz=result.best_null_holdout_rmse_hz,
        preference_margin_hz=result.preference_margin_hz,
        plan_hash=result.plan_hash,
    )


def _haversine_km(left: Observer, right: Observer) -> float:
    earth_radius_km = 6_371.0088
    left_lat, right_lat = radians(left.latitude_deg), radians(right.latitude_deg)
    delta_lat = right_lat - left_lat
    delta_lon = radians(right.longitude_deg - left.longitude_deg)
    haversine = (
        sin(delta_lat / 2.0) ** 2
        + cos(left_lat) * cos(right_lat) * sin(delta_lon / 2.0) ** 2
    )
    return 2.0 * earth_radius_km * asin(sqrt(haversine))
