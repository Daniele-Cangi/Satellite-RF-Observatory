"""Non-probabilistic held-out discrimination for Gate G0."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Mapping

import numpy as np

from .nuisance import (
    CalibrationSplit,
    NuisanceError,
    affine_shape_residual,
    differential_network_heldout_rmse,
    make_calibration_split,
)
from .null_models import FittedModel, fit_frozen_nulls, fit_orbital_model


class G0Outcome(str, Enum):
    ORBITAL_SIGNATURE_BELOW_DETECTABILITY = "ORBITAL_SIGNATURE_BELOW_DETECTABILITY"
    ORBITAL_PREDICTION_REJECTED = "ORBITAL_PREDICTION_REJECTED"
    ORBITAL_MODEL_NOT_DISCRIMINATIVE = "ORBITAL_MODEL_NOT_DISCRIMINATIVE"
    ORBITAL_MODEL_PREDICTIVELY_PREFERRED = "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"


@dataclass(frozen=True, slots=True)
class HeldoutPlan:
    calibration_fraction: float = 0.2
    minimum_calibration_samples: int = 6
    minimum_holdout_samples: int = 16
    frequency_resolution_hz: float = 5.0
    minimum_signature_bins: float = 3.0
    maximum_clock_error_s: float = 1.0
    carrier_relative_uncertainty: float = 0.0
    orbital_prediction_uncertainty_hz: float = 1.0
    maximum_orbital_rmse_bins: float = 2.0
    minimum_preference_bins: float = 1.0

    def validate(self) -> None:
        finite_nonnegative = (
            self.maximum_clock_error_s,
            self.carrier_relative_uncertainty,
            self.orbital_prediction_uncertainty_hz,
        )
        finite_positive = (
            self.calibration_fraction,
            self.frequency_resolution_hz,
            self.minimum_signature_bins,
            self.maximum_orbital_rmse_bins,
            self.minimum_preference_bins,
        )
        if not all(isfinite(value) and value >= 0.0 for value in finite_nonnegative):
            raise NuisanceError("held-out uncertainty bounds must be finite and non-negative")
        if not all(isfinite(value) and value > 0.0 for value in finite_positive):
            raise NuisanceError("held-out scale and margin values must be finite and positive")
        if not 0.0 < self.calibration_fraction < 1.0:
            raise NuisanceError("calibration_fraction must be in (0, 1)")
        if self.minimum_calibration_samples < 3 or self.minimum_holdout_samples < 3:
            raise NuisanceError("held-out partitions require at least three samples")

    @property
    def plan_hash(self) -> str:
        self.validate()
        encoded = json.dumps(
            asdict(self),
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelScore:
    name: str
    model_family: str
    parameter_count: int
    calibration_rmse_hz: float
    holdout_rmse_hz: float
    holdout_valid_count: int


@dataclass(frozen=True, slots=True)
class HeldoutResult:
    outcome: str
    plan_hash: str
    split: CalibrationSplit
    station_ids: tuple[str, ...]
    most_discriminating_pair: tuple[str, str]
    differential_signature_span_hz: float
    detectability_threshold_hz: float
    detectability_margin_hz: float
    clock_uncertainty_hz: float
    carrier_uncertainty_hz: float
    orbital_uncertainty_hz: float
    orbital_tolerance_hz: float
    orbital_score: ModelScore
    null_scores: tuple[ModelScore, ...]
    best_null_name: str
    best_null_holdout_rmse_hz: float
    preference_margin_hz: float
    required_preference_margin_hz: float
    statement: str
    calibrated_probability_used: bool = False


def evaluate_heldout(
    elapsed_s: tuple[float, ...] | np.ndarray,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    orbital_predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    plan: HeldoutPlan,
) -> HeldoutResult:
    """Evaluate one frozen calibration-prefix/held-out experiment."""

    plan.validate()
    times = np.asarray(elapsed_s, dtype=np.float64)
    stations = tuple(sorted(observations_hz))
    if len(stations) < 2 or stations != tuple(sorted(orbital_predictions_hz)):
        raise NuisanceError("held-out evaluation requires identical multi-station IDs")
    if times.ndim != 1 or times.size < 3 or not np.all(np.isfinite(times)):
        raise NuisanceError("elapsed_s must be one finite vector")
    if not np.all(np.diff(times) > 0.0):
        raise NuisanceError("elapsed_s must be strictly increasing")
    for station in stations:
        observed = np.asarray(observations_hz[station], dtype=np.float64)
        prediction = np.asarray(orbital_predictions_hz[station], dtype=np.float64)
        if observed.shape != times.shape or prediction.shape != times.shape:
            raise NuisanceError("all station series must share the event-time grid")
        if not np.all(np.isfinite(prediction)):
            raise NuisanceError("orbital predictions must be finite")

    split = make_calibration_split(
        len(times),
        plan.calibration_fraction,
        minimum_calibration_samples=plan.minimum_calibration_samples,
        minimum_holdout_samples=plan.minimum_holdout_samples,
    )
    orbital = fit_orbital_model(
        times,
        observations_hz,
        orbital_predictions_hz,
        split,
    )
    nulls = fit_frozen_nulls(
        times,
        observations_hz,
        orbital_predictions_hz,
        split,
    )
    orbital_score = _score(orbital, observations_hz, split)
    null_scores = tuple(_score(model, observations_hz, split) for model in nulls)
    best_null = min(null_scores, key=lambda item: (item.holdout_rmse_hz, item.name))

    (
        pair,
        signature_span,
        clock_uncertainty,
        carrier_uncertainty,
    ) = _strongest_differential_signature(
        times,
        orbital_predictions_hz,
        split,
        plan,
    )
    orbital_uncertainty = 2.0 * plan.orbital_prediction_uncertainty_hz
    detectability_threshold = (
        plan.minimum_signature_bins * plan.frequency_resolution_hz
        + clock_uncertainty
        + carrier_uncertainty
        + orbital_uncertainty
    )
    detectability_margin = signature_span - detectability_threshold
    orbital_tolerance = (
        plan.maximum_orbital_rmse_bins * plan.frequency_resolution_hz
        + clock_uncertainty
        + carrier_uncertainty
        + orbital_uncertainty
    )
    preference_margin = best_null.holdout_rmse_hz - orbital_score.holdout_rmse_hz
    required_preference = plan.minimum_preference_bins * plan.frequency_resolution_hz

    if detectability_margin < 0.0:
        outcome = G0Outcome.ORBITAL_SIGNATURE_BELOW_DETECTABILITY
        statement = "the nonlinear differential orbital signature does not clear the frozen measurement envelope"
    elif orbital_score.holdout_rmse_hz > orbital_tolerance:
        outcome = G0Outcome.ORBITAL_PREDICTION_REJECTED
        statement = "the held-out observation lies outside the frozen orbital prediction tolerance"
    elif preference_margin < required_preference:
        outcome = G0Outcome.ORBITAL_MODEL_NOT_DISCRIMINATIVE
        statement = "the admissible orbital prediction does not beat every frozen null by one required margin"
    else:
        outcome = G0Outcome.ORBITAL_MODEL_PREDICTIVELY_PREFERRED
        statement = "the detectable orbital geometry predicts the holdout better than every frozen null"

    numeric = (
        signature_span,
        detectability_threshold,
        detectability_margin,
        clock_uncertainty,
        carrier_uncertainty,
        orbital_uncertainty,
        orbital_tolerance,
        orbital_score.holdout_rmse_hz,
        best_null.holdout_rmse_hz,
        preference_margin,
        required_preference,
    )
    if not all(isfinite(value) for value in numeric):
        raise NuisanceError("held-out evaluation produced a non-finite receipt scalar")
    return HeldoutResult(
        outcome=outcome.value,
        plan_hash=plan.plan_hash,
        split=split,
        station_ids=stations,
        most_discriminating_pair=pair,
        differential_signature_span_hz=signature_span,
        detectability_threshold_hz=detectability_threshold,
        detectability_margin_hz=detectability_margin,
        clock_uncertainty_hz=clock_uncertainty,
        carrier_uncertainty_hz=carrier_uncertainty,
        orbital_uncertainty_hz=orbital_uncertainty,
        orbital_tolerance_hz=orbital_tolerance,
        orbital_score=orbital_score,
        null_scores=null_scores,
        best_null_name=best_null.name,
        best_null_holdout_rmse_hz=best_null.holdout_rmse_hz,
        preference_margin_hz=preference_margin,
        required_preference_margin_hz=required_preference,
        statement=statement,
    )


def _score(
    model: FittedModel,
    observations_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
) -> ModelScore:
    holdout_rmse, valid_count = differential_network_heldout_rmse(
        observations_hz,
        model.prediction_hz,
        split,
    )
    return ModelScore(
        name=model.name,
        model_family=model.model_family,
        parameter_count=model.parameter_count,
        calibration_rmse_hz=model.calibration_rmse_hz,
        holdout_rmse_hz=holdout_rmse,
        holdout_valid_count=valid_count,
    )


def _strongest_differential_signature(
    times: np.ndarray,
    predictions_hz: Mapping[str, tuple[float, ...] | np.ndarray],
    split: CalibrationSplit,
    plan: HeldoutPlan,
) -> tuple[tuple[str, str], float, float, float]:
    stations = sorted(predictions_hz)
    holdout = np.asarray(split.holdout_indices, dtype=np.int64)
    ranked: list[tuple[float, tuple[str, str], float, float]] = []
    for left_index, left in enumerate(stations):
        left_values = np.asarray(predictions_hz[left], dtype=np.float64)
        left_slope = np.gradient(left_values, times, edge_order=2)
        for right in stations[left_index + 1 :]:
            right_values = np.asarray(predictions_hz[right], dtype=np.float64)
            right_slope = np.gradient(right_values, times, edge_order=2)
            differential = left_values - right_values
            shape = np.asarray(affine_shape_residual(times, differential, split))
            holdout_shape = shape[holdout]
            span = float(np.max(holdout_shape) - np.min(holdout_shape))
            clock_uncertainty = float(
                (
                    np.max(np.abs(left_slope[holdout]))
                    + np.max(np.abs(right_slope[holdout]))
                )
                * plan.maximum_clock_error_s
            )
            carrier_uncertainty = float(
                np.max(np.abs(differential[holdout]))
                * plan.carrier_relative_uncertainty
            )
            ranked.append(
                (
                    span - clock_uncertainty - carrier_uncertainty,
                    (left, right),
                    clock_uncertainty,
                    carrier_uncertainty,
                )
            )
    if not ranked:
        raise NuisanceError("no observer pair exists for differential evaluation")
    _, pair, clock_uncertainty, carrier_uncertainty = max(
        ranked,
        key=lambda item: (item[0], item[1]),
    )
    left_values = np.asarray(predictions_hz[pair[0]], dtype=np.float64)
    right_values = np.asarray(predictions_hz[pair[1]], dtype=np.float64)
    selected_shape = np.asarray(
        affine_shape_residual(times, left_values - right_values, split)
    )[holdout]
    span = float(np.max(selected_shape) - np.min(selected_shape))
    return pair, span, clock_uncertainty, carrier_uncertainty
