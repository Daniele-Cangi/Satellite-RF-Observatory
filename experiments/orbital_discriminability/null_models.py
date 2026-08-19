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
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> FittedModel:
    fits = fit_station_nuisance(
        elapsed_s,
        observations_hz,
        orbital_predictions_hz,
        split,
        visibility_masks=visibility_masks,
    )
    prediction = {station: fit.prediction_hz for station, fit in fits.items()}
    rmse, count = _network_calibration_rmse(
        observations_hz, prediction, split, visibility_masks=visibility_masks
    )
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
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> tuple[FittedModel, ...]:
    """Fit non-redundant N0–N3 on one visibility-gated calibration prefix."""

    stations = sorted(observations_hz)
    if stations != sorted(orbital_predictions_hz) or len(stations) < 2:
        raise NuisanceError("null fitting requires identical distributed station IDs")
    if stations != sorted(visibility_masks):
        raise NuisanceError("null fitting requires matching visibility-mask station IDs")
    n3_mapping = {
        station: stations[(index + 1) % len(stations)]
        for index, station in enumerate(stations)
    }
    return (
        _fit_independent_constant(
            elapsed_s, observations_hz, split, visibility_masks=visibility_masks
        ),
        _fit_independent_affine(
            elapsed_s, observations_hz, split, visibility_masks=visibility_masks
        ),
        _fit_independent_quadratic(
            elapsed_s, observations_hz, split, visibility_masks=visibility_masks
        ),
        _fit_permuted_orbit(
            "N3_OBSERVER_GEOMETRY_PERMUTED",
            elapsed_s,
            observations_hz,
            orbital_predictions_hz,
            n3_mapping,
            split,
            visibility_masks=visibility_masks,
        ),
    )


def _fit_independent_constant(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> FittedModel:
    del elapsed_s
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    predictions: dict[str, tuple[float, ...]] = {}
    for station in sorted(observations_hz):
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        if observed.ndim != 1 or observed.size != split.sample_count:
            raise NuisanceError("N0 station series does not match the split")
        mask = _mask(visibility_masks[station], split.sample_count)
        valid = calibration[np.isfinite(observed[calibration]) & mask[calibration]]
        if valid.size < 1:
            raise NuisanceError("N0 requires a finite calibration sample per station")
        value = float(np.mean(observed[valid]))
        predictions[station] = tuple(value for _ in range(split.sample_count))
    rmse, count = _network_calibration_rmse(
        observations_hz, predictions, split, visibility_masks=visibility_masks
    )
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
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> FittedModel:
    zeros = {
        station: np.zeros(split.sample_count, dtype=np.float64)
        for station in observations_hz
    }
    fits = fit_station_nuisance(
        elapsed_s,
        observations_hz,
        zeros,
        split,
        visibility_masks=visibility_masks,
    )
    predictions = {station: fit.prediction_hz for station, fit in fits.items()}
    rmse, count = _network_calibration_rmse(
        observations_hz, predictions, split, visibility_masks=visibility_masks
    )
    return FittedModel(
        "N1_STATION_AFFINE",
        2 * len(predictions),
        predictions,
        rmse,
        count,
        "independent_station_affine",
    )


def _fit_independent_quadratic(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> FittedModel:
    times = np.asarray(elapsed_s, dtype=np.float64)
    if times.ndim != 1 or times.size != split.sample_count:
        raise NuisanceError("N2 time grid does not match the split")
    duration = float(times[-1] - times[0])
    if duration <= 0.0 or not np.all(np.isfinite(times)):
        raise NuisanceError("N2 requires a finite increasing time grid")
    normalized = (times - times[0]) / duration
    stations = sorted(observations_hz)
    predictions: dict[str, tuple[float, ...]] = {}
    for station in stations:
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        if observed.ndim != 1 or observed.size != split.sample_count:
            raise NuisanceError("N2 station series does not match the split")
        mask = _mask(visibility_masks[station], split.sample_count)
        calibration = np.asarray(split.calibration_indices, dtype=np.int64)
        valid = calibration[np.isfinite(observed[calibration]) & mask[calibration]]
        if valid.size < 3:
            raise NuisanceError("N2 requires three visible calibration samples per station")
        design = np.column_stack(
            (np.ones(valid.size), normalized[valid], np.square(normalized[valid]))
        )
        coefficients, *_ = np.linalg.lstsq(design, observed[valid], rcond=None)
        predicted = (
            coefficients[0]
            + coefficients[1] * normalized
            + coefficients[2] * np.square(normalized)
        )
        predictions[station] = _finite_tuple(predicted)
    rmse, count = _network_calibration_rmse(
        observations_hz, predictions, split, visibility_masks=visibility_masks
    )
    return FittedModel(
        "N2_STATION_QUADRATIC",
        3 * len(stations),
        predictions,
        rmse,
        count,
        "independent_station_quadratic",
    )


def _fit_permuted_orbit(
    name: str,
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    orbital_predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    mapping: Mapping[str, str],
    split: CalibrationSplit,
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> FittedModel:
    permuted = {
        station: orbital_predictions_hz[mapping[station]]
        for station in sorted(observations_hz)
    }
    fits = fit_station_nuisance(
        elapsed_s,
        observations_hz,
        permuted,
        split,
        visibility_masks=visibility_masks,
    )
    predictions = {station: fit.prediction_hz for station, fit in fits.items()}
    rmse, count = _network_calibration_rmse(
        observations_hz, predictions, split, visibility_masks=visibility_masks
    )
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
    *,
    visibility_masks: Mapping[str, tuple[bool, ...] | np.ndarray],
) -> tuple[float, int]:
    squared_sum = 0.0
    count = 0
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    for station in sorted(observations_hz):
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        predicted = np.asarray(predictions_hz[station], dtype=np.float64)
        if observed.shape != predicted.shape or observed.size != split.sample_count:
            raise NuisanceError("calibration series do not share one grid")
        mask = _mask(visibility_masks[station], split.sample_count)
        valid = calibration[np.isfinite(observed[calibration]) & mask[calibration]]
        if not np.all(np.isfinite(predicted)):
            raise NuisanceError("calibration prediction contains non-finite values")
        errors = observed[valid] - predicted[valid]
        squared_sum += float(np.dot(errors, errors))
        count += int(valid.size)
    if count == 0:
        raise NuisanceError("calibration contains no finite observations")
    return sqrt(squared_sum / count), count


def _mask(values: tuple[bool, ...] | np.ndarray, sample_count: int) -> np.ndarray:
    mask = np.asarray(values)
    if mask.shape != (sample_count,) or mask.dtype.kind != "b":
        raise NuisanceError("visibility mask must be one boolean value per sample")
    return mask.astype(bool, copy=False)


def _finite_tuple(values: np.ndarray) -> tuple[float, ...]:
    if not np.all(np.isfinite(values)):
        raise NuisanceError("null prediction produced a non-finite value")
    return tuple(float(value) for value in values)
