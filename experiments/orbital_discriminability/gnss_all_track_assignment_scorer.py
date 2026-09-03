"""Pure identity-blind scorer for one synthetic all-track GNSS spike.

The scorer receives six anonymous tracks and 721 opaque model matrices.  It
has no signal identity, reveal table, orbital compiler, decoder, network
client, or write authority.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite, sqrt
import re
from typing import Final, Mapping, Sequence

import numpy as np


SCORER_VERSION: Final = "gnss-all-track-assignment-scorer-v2"
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
STEP_S: Final = 30.0
TRACK_COUNT: Final = 6
HYPOTHESIS_COUNT: Final = 721
METRIC_DECIMALS: Final = 6
TRACK_ID_PATTERN: Final = re.compile(r"T_[0-9A-F]{16}")
HYPOTHESIS_ID_PATTERN: Final = re.compile(r"H_[0-9A-F]{16}")


class AllTrackScorerError(ValueError):
    """The closed synthetic scoring surface is malformed."""


def _quantized(value: float) -> float:
    """Canonicalize derived score metrics without changing input coordinates."""

    result = round(float(value), METRIC_DECIMALS)
    if not isfinite(result):
        raise AllTrackScorerError("NONFINITE_SCORE_METRIC")
    return result


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def _finite_vector(values: Sequence[float], label: str) -> np.ndarray:
    result = np.array(values, dtype=np.float64, copy=True)
    if result.shape != (RAW_EPOCHS,):
        raise AllTrackScorerError(f"{label}_SHAPE_INVALID")
    if not np.all(np.isfinite(result)):
        raise AllTrackScorerError(f"{label}_GAP_OR_NONFINITE")
    return result


def _track_matrix(tracks_m: Mapping[str, Sequence[float]]) -> tuple[list[str], np.ndarray]:
    identifiers = sorted(tracks_m)
    if len(identifiers) != TRACK_COUNT or any(
        TRACK_ID_PATTERN.fullmatch(value) is None for value in identifiers
    ):
        raise AllTrackScorerError("OPAQUE_TRACK_SET_INVALID")
    matrix = np.stack(
        [_finite_vector(tracks_m[value], "TRACK") for value in identifiers]
    )
    return identifiers, matrix


def _hypothesis_surface(
    hypotheses_m: Mapping[str, Sequence[Sequence[float]]],
) -> dict[str, np.ndarray]:
    identifiers = sorted(hypotheses_m)
    if len(identifiers) != HYPOTHESIS_COUNT or any(
        HYPOTHESIS_ID_PATTERN.fullmatch(value) is None for value in identifiers
    ):
        raise AllTrackScorerError("OPAQUE_HYPOTHESIS_SET_INVALID")
    surface: dict[str, np.ndarray] = {}
    for identifier in identifiers:
        matrix = np.array(hypotheses_m[identifier], dtype=np.float64, copy=True)
        if matrix.shape != (TRACK_COUNT, RAW_EPOCHS):
            raise AllTrackScorerError("OPAQUE_HYPOTHESIS_SHAPE_INVALID")
        if not np.all(np.isfinite(matrix)):
            raise AllTrackScorerError("OPAQUE_HYPOTHESIS_NONFINITE")
        surface[identifier] = matrix
    return surface


def _center_common_mode(matrix: np.ndarray) -> np.ndarray:
    return matrix - np.mean(matrix, axis=0, keepdims=True)


def _prefix_project(residual: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    prefix_x = elapsed[:PREFIX_EPOCHS]
    centered_x = prefix_x - float(np.mean(prefix_x))
    denominator = float(centered_x @ centered_x)
    if denominator <= 0.0:
        raise AllTrackScorerError("PREFIX_TIME_BASIS_INVALID")
    projected = residual.copy()
    for row_index in range(TRACK_COUNT):
        prefix_y = residual[row_index, :PREFIX_EPOCHS]
        mean_y = float(np.mean(prefix_y))
        rate = float(centered_x @ (prefix_y - mean_y) / denominator)
        constant = mean_y - rate * float(np.mean(prefix_x))
        projected[row_index] -= constant + rate * elapsed
    prefix = projected[:, :PREFIX_EPOCHS]
    heldout = projected[:, PREFIX_EPOCHS:]
    metrics = {
        "prefix_rms_m": sqrt(float(np.mean(prefix * prefix))),
        "heldout_max_track_peak_to_peak_m": float(
            max(np.ptp(row) for row in heldout)
        ),
        "heldout_rms_m": sqrt(float(np.mean(heldout * heldout))),
    }
    return projected, metrics


def score_anonymous_tracks(
    tracks_m: Mapping[str, Sequence[float]],
    hypotheses_m: Mapping[str, Sequence[Sequence[float]]],
    *,
    pairwise_guard_m: float,
) -> dict[str, object]:
    """Score every opaque assignment after common-mode and prefix projection."""

    guard = float(pairwise_guard_m)
    if not isfinite(guard) or guard <= 0.0:
        raise AllTrackScorerError("PAIRWISE_GUARD_INVALID")
    track_ids, observed = _track_matrix(tracks_m)
    surface = _hypothesis_surface(hypotheses_m)
    centered_observed = _center_common_mode(observed)
    rows: list[dict[str, object]] = []
    for identifier in sorted(surface):
        centered_model = _center_common_mode(surface[identifier])
        _, metrics = _prefix_project(centered_observed - centered_model)
        rows.append(
            {
                "opaque_id": identifier,
                "prefix_rms_m": _quantized(metrics["prefix_rms_m"]),
                "heldout_max_track_peak_to_peak_m": _quantized(
                    metrics["heldout_max_track_peak_to_peak_m"]
                ),
                "heldout_rms_m": _quantized(metrics["heldout_rms_m"]),
                "effective_prefix_parameter_count": 2 * (TRACK_COUNT - 1),
            }
        )
    rows.sort(
        key=lambda row: (
            float(row["heldout_max_track_peak_to_peak_m"]),
            float(row["heldout_rms_m"]),
            str(row["opaque_id"]),
        )
    )
    best, runner_up = rows[:2]
    best_residual = float(best["heldout_max_track_peak_to_peak_m"])
    preference_margin = _quantized(
        float(runner_up["heldout_max_track_peak_to_peak_m"]) - best_residual
    )
    if best_residual > guard:
        state = "NO_ADMISSIBLE_OPAQUE_ASSIGNMENT"
    elif preference_margin > guard:
        state = "OPAQUE_ASSIGNMENT_PREFERRED"
    else:
        state = "AMBIGUOUS"
    full_score_hash = sha256(strict_json(rows).encode("ascii")).hexdigest()
    track_hash = sha256(
        strict_json(
            {
                identifier: [float(value) for value in observed[index]]
                for index, identifier in enumerate(track_ids)
            }
        ).encode("ascii")
    ).hexdigest()
    receipt = {
        "schema": "gnss-all-track-assignment-score-receipt-v1",
        "scorer_version": SCORER_VERSION,
        "track_ids": track_ids,
        "track_count": TRACK_COUNT,
        "track_set_sha256": track_hash,
        "track_or_observation_values_persisted": 0,
        "opaque_hypothesis_count": len(rows),
        "all_scores_sha256": full_score_hash,
        "top_scores": rows[:3],
        "best_opaque_id": str(best["opaque_id"]),
        "runner_up_opaque_id": str(runner_up["opaque_id"]),
        "best_heldout_max_track_peak_to_peak_m": best_residual,
        "preference_margin_m": preference_margin,
        "pairwise_guard_m": guard,
        "orbital_score_state": state,
        "common_mode": "REMOVED_BY_PER_EPOCH_TRACK_ENSEMBLE_CENTERING",
        "effective_prefix_parameter_count_per_hypothesis": 2 * (TRACK_COUNT - 1),
        "metric_quantization_decimal_places": METRIC_DECIMALS,
        "prefix_indices_inclusive": [0, PREFIX_EPOCHS - 1],
        "heldout_indices_inclusive": [PREFIX_EPOCHS, RAW_EPOCHS - 1],
        "heldout_refit": False,
        "free_time_phase": False,
        "identity_reveal_performed": False,
    }
    strict_json(receipt)
    observed.fill(0.0)
    centered_observed.fill(0.0)
    for matrix in surface.values():
        matrix.fill(0.0)
    return receipt


def receipt_sha256(receipt: Mapping[str, object]) -> str:
    return sha256(strict_json(receipt).encode("ascii")).hexdigest()
