"""Predeclared nuisance transforms for Gate G0.

Only a station-local offset and affine drift may be estimated.  Fits use a
calibration prefix and are then applied unchanged to the held-out suffix.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite, sqrt
from typing import Mapping

import numpy as np


class NuisanceError(ValueError):
    """Raised when a nuisance fit would be underdetermined or leak holdout data."""


@dataclass(frozen=True, slots=True)
class CalibrationSplit:
    sample_count: int
    calibration_count: int
    holdout_count: int
    calibration_indices: tuple[int, ...]
    holdout_indices: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class NuisanceFit:
    offset_hz: float
    drift_hz_s: float
    prediction_hz: tuple[float, ...]
    calibration_rmse_hz: float
    calibration_valid_count: int


def make_calibration_split(
    sample_count: int,
    calibration_fraction: float,
    *,
    minimum_calibration_samples: int = 3,
    minimum_holdout_samples: int = 8,
) -> CalibrationSplit:
    if sample_count <= 0:
        raise NuisanceError("sample_count must be positive")
    if not isfinite(calibration_fraction) or not 0.0 < calibration_fraction < 1.0:
        raise NuisanceError("calibration_fraction must be finite and in (0, 1)")
    calibration_count = max(
        int(minimum_calibration_samples),
        int(ceil(sample_count * calibration_fraction)),
    )
    holdout_count = sample_count - calibration_count
    if holdout_count < minimum_holdout_samples:
        raise NuisanceError("insufficient independent holdout samples")
    return CalibrationSplit(
        sample_count=sample_count,
        calibration_count=calibration_count,
        holdout_count=holdout_count,
        calibration_indices=tuple(range(calibration_count)),
        holdout_indices=tuple(range(calibration_count, sample_count)),
    )


def fit_affine_nuisance(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observed_hz: tuple[float, ...] | np.ndarray,
    physical_prediction_hz: tuple[float, ...] | np.ndarray,
    split: CalibrationSplit,
) -> NuisanceFit:
    """Fit observed minus physical prediction on calibration data only."""

    times, observed, physical = _coerce_equal(elapsed_s, observed_hz, physical_prediction_hz)
    if len(times) != split.sample_count:
        raise NuisanceError("calibration split does not match the series length")
    residual = observed - physical
    calibration = np.asarray(split.calibration_indices, dtype=np.int64)
    valid = calibration[np.isfinite(residual[calibration])]
    if valid.size < 2:
        raise NuisanceError("affine nuisance requires two finite calibration samples")
    design = np.column_stack((np.ones(valid.size), times[valid] - times[0]))
    coefficients, *_ = np.linalg.lstsq(design, residual[valid], rcond=None)
    offset, drift = (float(coefficients[0]), float(coefficients[1]))
    prediction = physical + offset + drift * (times - times[0])
    calibration_error = observed[valid] - prediction[valid]
    return NuisanceFit(
        offset_hz=offset,
        drift_hz_s=drift,
        prediction_hz=_finite_tuple(prediction),
        calibration_rmse_hz=_rmse_finite(calibration_error),
        calibration_valid_count=int(valid.size),
    )


def fit_station_nuisance(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    physical_predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> dict[str, NuisanceFit]:
    if set(observations_hz) != set(physical_predictions_hz):
        raise NuisanceError("observations and predictions require identical station IDs")
    if len(observations_hz) < 2:
        raise NuisanceError("distributed fitting requires at least two stations")
    return {
        station: fit_affine_nuisance(
            elapsed_s,
            observations_hz[station],
            physical_predictions_hz[station],
            split,
        )
        for station in sorted(observations_hz)
    }


def affine_shape_residual(
    elapsed_s: tuple[float, ...] | np.ndarray,
    values: tuple[float, ...] | np.ndarray,
    split: CalibrationSplit,
) -> tuple[float, ...]:
    """Remove an affine calibration-prefix extrapolation from a finite shape."""

    times, series, zero = _coerce_equal(elapsed_s, values, np.zeros(len(values)))
    fit = fit_affine_nuisance(times, series, zero, split)
    return tuple(float(value) for value in series - np.asarray(fit.prediction_hz))


def heldout_rmse(
    observed_hz: tuple[float, ...] | np.ndarray,
    prediction_hz: tuple[float, ...] | np.ndarray,
    split: CalibrationSplit,
) -> tuple[float, int]:
    observed = np.asarray(observed_hz, dtype=np.float64)
    prediction = np.asarray(prediction_hz, dtype=np.float64)
    if observed.ndim != 1 or prediction.shape != observed.shape:
        raise NuisanceError("observed and predicted series must be equal one-dimensional vectors")
    if observed.size != split.sample_count or not np.all(np.isfinite(prediction)):
        raise NuisanceError("series does not match the split or prediction is non-finite")
    holdout = np.asarray(split.holdout_indices, dtype=np.int64)
    valid = holdout[np.isfinite(observed[holdout])]
    if valid.size == 0:
        raise NuisanceError("held-out interval contains no finite observations")
    return _rmse_finite(observed[valid] - prediction[valid]), int(valid.size)


def network_heldout_rmse(
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> tuple[float, int]:
    if set(observations_hz) != set(predictions_hz):
        raise NuisanceError("network observations and predictions require identical station IDs")
    squared_sum = 0.0
    sample_total = 0
    for station in sorted(observations_hz):
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        prediction = np.asarray(predictions_hz[station], dtype=np.float64)
        if observed.shape != prediction.shape or observed.size != split.sample_count:
            raise NuisanceError("network series do not share the calibration grid")
        holdout = np.asarray(split.holdout_indices, dtype=np.int64)
        valid = holdout[np.isfinite(observed[holdout])]
        if not np.all(np.isfinite(prediction)):
            raise NuisanceError("network prediction contains non-finite values")
        errors = observed[valid] - prediction[valid]
        squared_sum += float(np.dot(errors, errors))
        sample_total += int(valid.size)
    if sample_total == 0:
        raise NuisanceError("network holdout contains no finite observations")
    return sqrt(squared_sum / sample_total), sample_total


def differential_network_heldout_rmse(
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> tuple[float, int]:
    """Score station-pair differences so common transmitter drift cancels."""

    stations = sorted(observations_hz)
    if stations != sorted(predictions_hz) or len(stations) < 2:
        raise NuisanceError("differential scoring requires identical multi-station IDs")
    squared_sum = 0.0
    sample_total = 0
    holdout = np.asarray(split.holdout_indices, dtype=np.int64)
    for left_index, left in enumerate(stations):
        left_observed = np.asarray(observations_hz[left], dtype=np.float64)
        left_predicted = np.asarray(predictions_hz[left], dtype=np.float64)
        for right in stations[left_index + 1 :]:
            right_observed = np.asarray(observations_hz[right], dtype=np.float64)
            right_predicted = np.asarray(predictions_hz[right], dtype=np.float64)
            if not (
                left_observed.shape
                == left_predicted.shape
                == right_observed.shape
                == right_predicted.shape
                == (split.sample_count,)
            ):
                raise NuisanceError("differential series do not share the calibration grid")
            if not (
                np.all(np.isfinite(left_predicted))
                and np.all(np.isfinite(right_predicted))
            ):
                raise NuisanceError("differential prediction contains non-finite values")
            valid_mask = np.isfinite(left_observed[holdout]) & np.isfinite(
                right_observed[holdout]
            )
            valid = holdout[valid_mask]
            observed_difference = left_observed[valid] - right_observed[valid]
            predicted_difference = left_predicted[valid] - right_predicted[valid]
            errors = observed_difference - predicted_difference
            squared_sum += float(np.dot(errors, errors))
            sample_total += int(valid.size)
    if sample_total == 0:
        raise NuisanceError("differential holdout contains no simultaneous finite observations")
    return sqrt(squared_sum / sample_total), sample_total


def _coerce_equal(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observed_hz: tuple[float, ...] | np.ndarray,
    prediction_hz: tuple[float, ...] | np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    times = np.asarray(elapsed_s, dtype=np.float64)
    observed = np.asarray(observed_hz, dtype=np.float64)
    prediction = np.asarray(prediction_hz, dtype=np.float64)
    if times.ndim != 1 or observed.shape != times.shape or prediction.shape != times.shape:
        raise NuisanceError("time, observation and prediction must be equal one-dimensional vectors")
    if times.size < 3 or not np.all(np.isfinite(times)) or not np.all(np.diff(times) > 0.0):
        raise NuisanceError("elapsed_s must be finite, strictly increasing and contain three samples")
    if not np.all(np.isfinite(prediction)):
        raise NuisanceError("physical prediction must be finite")
    return times, observed, prediction


def _finite_tuple(values: np.ndarray) -> tuple[float, ...]:
    if not np.all(np.isfinite(values)):
        raise NuisanceError("nuisance prediction produced a non-finite value")
    return tuple(float(value) for value in values)


def _rmse_finite(values: np.ndarray) -> float:
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise NuisanceError("RMSE requires finite values")
    return float(np.sqrt(np.mean(np.square(values))))
