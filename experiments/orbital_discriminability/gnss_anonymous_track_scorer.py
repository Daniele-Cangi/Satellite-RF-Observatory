"""Pure scorer for the closed anonymous-track synthetic mechanism spike.

The scorer receives two anonymous same-clock tracks and eleven opaque model
curves.  It has no code identity, PRN mapping, orbital compiler, observation
decoder, network client or write authority.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite, sqrt
import re
from typing import Final, Mapping, Sequence

import numpy as np


SCORER_VERSION: Final = "gnss-anonymous-track-spike-scorer-v1"
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
STEP_S: Final = 30.0
HYPOTHESIS_COUNT: Final = 11
OPAQUE_ID_PATTERN: Final = re.compile(r"H_[0-9A-F]{16}")


class AnonymousTrackScorerError(ValueError):
    """The closed synthetic scoring surface is malformed."""


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
        raise AnonymousTrackScorerError(f"{label}_SHAPE_INVALID")
    if not np.all(np.isfinite(result)):
        raise AnonymousTrackScorerError(f"{label}_GAP_OR_NONFINITE")
    return result


def _opaque_surface(
    hypotheses_m: Mapping[str, Sequence[float]],
) -> dict[str, np.ndarray]:
    if len(hypotheses_m) != HYPOTHESIS_COUNT:
        raise AnonymousTrackScorerError("OPAQUE_HYPOTHESIS_COUNT_CHANGED")
    identifiers = sorted(hypotheses_m)
    if any(OPAQUE_ID_PATTERN.fullmatch(value) is None for value in identifiers):
        raise AnonymousTrackScorerError("OPAQUE_HYPOTHESIS_ID_INVALID")
    arrays = {
        identifier: _finite_vector(hypotheses_m[identifier], "HYPOTHESIS")
        for identifier in identifiers
    }
    return arrays


def _prefix_metrics(residual: np.ndarray) -> dict[str, float]:
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    prefix_x = elapsed[:PREFIX_EPOCHS]
    prefix_y = residual[:PREFIX_EPOCHS]
    centered_x = prefix_x - float(np.mean(prefix_x))
    denominator = float(centered_x @ centered_x)
    if denominator <= 0.0:
        raise AnonymousTrackScorerError("PREFIX_TIME_BASIS_INVALID")
    rate = float(
        centered_x @ (prefix_y - float(np.mean(prefix_y))) / denominator
    )
    constant = float(np.mean(prefix_y)) - rate * float(np.mean(prefix_x))
    projected = residual - (constant + rate * elapsed)
    prefix = projected[:PREFIX_EPOCHS]
    heldout = projected[PREFIX_EPOCHS:]
    return {
        "prefix_constant_m": constant,
        "prefix_rate_m_s": rate,
        "prefix_rmse_m": sqrt(float(np.mean(prefix * prefix))),
        "heldout_peak_to_peak_m": float(np.ptp(heldout)),
        "heldout_rms_m": sqrt(float(np.mean(heldout * heldout))),
    }


def score_anonymous_pair(
    track_a_m: Sequence[float],
    track_b_m: Sequence[float],
    hypotheses_m: Mapping[str, Sequence[float]],
    *,
    pairwise_guard_m: float,
) -> dict[str, object]:
    """Score A-B with one identical prefix-only affine fit per opaque model."""

    guard = float(pairwise_guard_m)
    if not isfinite(guard) or guard < 0.0:
        raise AnonymousTrackScorerError("PAIRWISE_GUARD_INVALID")
    track_a = _finite_vector(track_a_m, "TRACK_A")
    track_b = _finite_vector(track_b_m, "TRACK_B")
    observed = track_a - track_b
    hypotheses = _opaque_surface(hypotheses_m)
    rows: list[dict[str, object]] = []
    for identifier in sorted(hypotheses):
        rows.append(
            {
                "opaque_id": identifier,
                **_prefix_metrics(observed - hypotheses[identifier]),
                "fitted_parameter_count": 2,
            }
        )
    rows.sort(
        key=lambda row: (
            float(row["heldout_peak_to_peak_m"]),
            float(row["heldout_rms_m"]),
            str(row["opaque_id"]),
        )
    )
    best, runner_up = rows[:2]
    preference_margin = float(runner_up["heldout_peak_to_peak_m"]) - float(
        best["heldout_peak_to_peak_m"]
    )
    preferred = preference_margin > guard
    coordinate_hash = sha256(
        strict_json([float(value) for value in observed]).encode("ascii")
    ).hexdigest()
    pair_hash = sha256(
        strict_json(
            {
                "track_a": [float(value) for value in track_a],
                "track_b": [float(value) for value in track_b],
            }
        ).encode("ascii")
    ).hexdigest()
    receipt = {
        "schema": "gnss-anonymous-track-score-receipt-v1",
        "scorer_version": SCORER_VERSION,
        "track_ids": ["TRACK_A", "TRACK_B"],
        "coordinate": "TRACK_A_MINUS_TRACK_B",
        "track_pair_sha256": pair_hash,
        "observed_coordinate_sha256": coordinate_hash,
        "track_or_observation_values_persisted": 0,
        "opaque_hypotheses": len(rows),
        "scores": rows,
        "best_opaque_id": str(best["opaque_id"]),
        "runner_up_opaque_id": str(runner_up["opaque_id"]),
        "preference_margin_m": preference_margin,
        "pairwise_guard_m": guard,
        "orbital_score_state": (
            "OPAQUE_HYPOTHESIS_PREFERRED" if preferred else "AMBIGUOUS"
        ),
        "prefix_indices_inclusive": [0, PREFIX_EPOCHS - 1],
        "heldout_indices_inclusive": [PREFIX_EPOCHS, RAW_EPOCHS - 1],
        "same_loop_parameter_count": 2,
        "heldout_refit": False,
        "free_time_phase": False,
        "identity_reveal_performed": False,
    }
    strict_json(receipt)
    track_a.fill(0.0)
    track_b.fill(0.0)
    observed.fill(0.0)
    for curve in hypotheses.values():
        curve.fill(0.0)
    return receipt


def receipt_sha256(receipt: Mapping[str, object]) -> str:
    return sha256(strict_json(receipt).encode("ascii")).hexdigest()
