"""Frozen non-orbital and geometry-destroying nulls for Gate G0."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Mapping

import numpy as np

from .nuisance import (
    CalibrationSplit,
    NuisanceError,
    fit_station_nuisance,
)


@dataclass(frozen=True, slots=True)
class FittedModel:
    name: str
    parameter_count: int
    prediction_hz: dict[str, tuple[float, ...]]
    calibration_rmse_hz: float
    calibration_valid_count: int
    model_family: str


def fit_orbital_model(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    orbital_predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> FittedModel:
    fits = fit_station_nuisance(
        elapsed_s,
        observations_hz,
        orbital_predictions_hz,
        split,
    )
    prediction = {station: fit.prediction_hz for station, fit in fits.items()}
    rmse, count = _network_calibration_rmse(observations_hz, prediction, split)
    return FittedModel(
        name="ORBITAL",
        parameter_count=2 * len(fits),
        prediction_hz=prediction,
        calibration_rmse_hz=rmse,
        calibration_valid_count=count,
        model_family="orbital_geometry_plus_station_affine_nuisance",
    )


def fit_frozen_nulls(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    orbital_predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> tuple[FittedModel, ...]:
    """Fit N0–N4 using the same calibration prefix and no holdout values."""

    stations = sorted(observations_hz)
    if stations != sorted(orbital_predictions_hz) or len(stations) < 2:
        raise NuisanceError("null fitting requires identical distributed station IDs")
    n3_mapping = {
        station: stations[(index + 1) % len(stations)]
        for index, station in enumerate(stations)
    }
    n4_order = list(reversed(stations))
    n4_mapping = {
        station: n4_order[index]
        for index, station in enumerate(stations)
    }
    return (
        _fit_independent_constant(elapsed_s, observations_hz, split),
        _fit_independent_affine(elapsed_s, observations_hz, split),
        _fit_common_cubic(elapsed_s, observations_hz, split),
        _fit_permuted_orbit(
            "N3_STATION_LABELS_PERMUTED",
            elapsed_s,
            observations_hz,
            orbital_predictions_hz,
            n3_mapping,
            split,
        ),
        _fit_permuted_orbit(
            "N4_OBSERVER_COORDINATES_PERMUTED",
            elapsed_s,
            observations_hz,
            orbital_predictions_hz,
            n4_mapping,
            split,
        ),
    )


def _fit_independent_constant(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> FittedModel:
    del elapsed_s
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    predictions: dict[str, tuple[float, ...]] = {}
    for station in sorted(observations_hz):
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        if observed.ndim != 1 or observed.size != split.sample_count:
            raise NuisanceError("N0 station series does not match the split")
        valid = calibration[np.isfinite(observed[calibration])]
        if valid.size < 1:
            raise NuisanceError("N0 requires a finite calibration sample per station")
        value = float(np.mean(observed[valid]))
        predictions[station] = tuple(value for _ in range(split.sample_count))
    rmse, count = _network_calibration_rmse(observations_hz, predictions, split)
    return FittedModel(
        "N0_STATION_CONSTANT",
        len(predictions),
        predictions,
        rmse,
        count,
        "independent_station_constant",
    )


def _fit_independent_affine(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> FittedModel:
    zeros = {
        station: np.zeros(split.sample_count, dtype=np.float64)
        for station in observations_hz
    }
    fits = fit_station_nuisance(elapsed_s, observations_hz, zeros, split)
    predictions = {station: fit.prediction_hz for station, fit in fits.items()}
    rmse, count = _network_calibration_rmse(observations_hz, predictions, split)
    return FittedModel(
        "N1_STATION_AFFINE",
        2 * len(predictions),
        predictions,
        rmse,
        count,
        "independent_station_affine",
    )


def _fit_common_cubic(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> FittedModel:
    times = np.asarray(elapsed_s, dtype=np.float64)
    if times.ndim != 1 or times.size != split.sample_count:
        raise NuisanceError("N2 time grid does not match the split")
    duration = float(times[-1] - times[0])
    if duration <= 0.0 or not np.all(np.isfinite(times)):
        raise NuisanceError("N2 requires a finite increasing time grid")
    normalized = (times - times[0]) / duration
    stations = sorted(observations_hz)
    parameter_count = 2 * len(stations) + 2
    rows: list[np.ndarray] = []
    values: list[float] = []
    for station_index, station in enumerate(stations):
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        if observed.ndim != 1 or observed.size != split.sample_count:
            raise NuisanceError("N2 station series does not match the split")
        for index in split.calibration_indices:
            if not np.isfinite(observed[index]):
                continue
            row = np.zeros(parameter_count, dtype=np.float64)
            row[2 * station_index] = 1.0
            row[2 * station_index + 1] = normalized[index]
            row[-2] = normalized[index] ** 2
            row[-1] = normalized[index] ** 3
            rows.append(row)
            values.append(float(observed[index]))
    if len(rows) < parameter_count:
        raise NuisanceError("N2 common smooth model is underdetermined")
    coefficients, *_ = np.linalg.lstsq(np.vstack(rows), np.asarray(values), rcond=None)
    predictions: dict[str, tuple[float, ...]] = {}
    for station_index, station in enumerate(stations):
        predicted = (
            coefficients[2 * station_index]
            + coefficients[2 * station_index + 1] * normalized
            + coefficients[-2] * np.square(normalized)
            + coefficients[-1] * np.power(normalized, 3)
        )
        predictions[station] = _finite_tuple(predicted)
    rmse, count = _network_calibration_rmse(observations_hz, predictions, split)
    return FittedModel(
        "N2_COMMON_CUBIC_PLUS_STATION_AFFINE",
        parameter_count,
        predictions,
        rmse,
        count,
        "common_smooth_temporal_component",
    )


def _fit_permuted_orbit(
    name: str,
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    orbital_predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    mapping: Mapping[str, str],
    split: CalibrationSplit,
) -> FittedModel:
    permuted = {
        station: orbital_predictions_hz[mapping[station]]
        for station in sorted(observations_hz)
    }
    fits = fit_station_nuisance(elapsed_s, observations_hz, permuted, split)
    predictions = {station: fit.prediction_hz for station, fit in fits.items()}
    rmse, count = _network_calibration_rmse(observations_hz, predictions, split)
    return FittedModel(
        name,
        2 * len(predictions),
        predictions,
        rmse,
        count,
        "geometry_destroying_station_permutation",
    )


def _network_calibration_rmse(
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> tuple[float, int]:
    squared_sum = 0.0
    count = 0
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    for station in sorted(observations_hz):
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        predicted = np.asarray(predictions_hz[station], dtype=np.float64)
        if observed.shape != predicted.shape or observed.size != split.sample_count:
            raise NuisanceError("calibration series do not share one grid")
        valid = calibration[np.isfinite(observed[calibration])]
        if not np.all(np.isfinite(predicted)):
            raise NuisanceError("calibration prediction contains non-finite values")
        errors = observed[valid] - predicted[valid]
        squared_sum += float(np.dot(errors, errors))
        count += int(valid.size)
    if count == 0:
        raise NuisanceError("calibration contains no finite observations")
    return sqrt(squared_sum / count), count


def _finite_tuple(values: np.ndarray) -> tuple[float, ...]:
    if not np.all(np.isfinite(values)):
        raise NuisanceError("null prediction produced a non-finite value")
    return tuple(float(value) for value in values)
