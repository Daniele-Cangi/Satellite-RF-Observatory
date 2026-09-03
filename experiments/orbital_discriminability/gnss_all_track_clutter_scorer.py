"""Closed identity-blind scorer for seven tracks with one clutter allowance.

The scorer knows opaque tracks, opaque hypotheses and hypothesis families. It
does not receive signal codes, orbit labels, reveal mappings, product data or
network access. Every hypothesis evaluates exactly six of seven tracks with
the same prefix-only nuisance and one explicit excluded-track budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import isfinite
import re
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_all_track_assignment_scorer as six_track,
)


SCORER_VERSION: Final = "gnss-all-track-one-clutter-scorer-v1"
OBSERVED_TRACK_COUNT: Final = 7
EVALUATED_TRACK_COUNT: Final = 6
CLUTTER_BUDGET: Final = 1
ORBITAL_HYPOTHESIS_COUNT: Final = 5_040
GEOMETRY_NULL_COUNT: Final = 5_040
AFFINE_NULL_COUNT: Final = 7
HYPOTHESIS_COUNT: Final = 10_087
METRIC_DECIMALS: Final = 6

FAMILY_ORBITAL: Final = "ORBITAL_INJECTION"
FAMILY_GEOMETRY_NULL: Final = "TIME_REVERSED_GEOMETRY_NULL"
FAMILY_AFFINE_NULL: Final = "PREFIX_AFFINE_ONLY_NULL"
FAMILIES: Final = (
    FAMILY_ORBITAL,
    FAMILY_GEOMETRY_NULL,
    FAMILY_AFFINE_NULL,
)

TRACK_ID_PATTERN: Final = re.compile(r"T_[0-9A-F]{16}")
HYPOTHESIS_ID_PATTERN: Final = re.compile(r"H_[0-9A-F]{16}")


class ClutterScorerError(ValueError):
    """The closed seven-track scoring surface is malformed."""


@dataclass(frozen=True, slots=True)
class OpaqueHypothesis:
    opaque_id: str
    family: str
    included_track_indices: tuple[int, ...]
    model_matrix_m: np.ndarray


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def _quantized(value: float) -> float:
    result = round(float(value), METRIC_DECIMALS)
    if not isfinite(result):
        raise ClutterScorerError("NONFINITE_SCORE_METRIC")
    return result


def _track_matrix(
    tracks_m: Mapping[str, Sequence[float]],
) -> tuple[tuple[str, ...], np.ndarray]:
    identifiers = tuple(sorted(tracks_m))
    if len(identifiers) != OBSERVED_TRACK_COUNT or any(
        TRACK_ID_PATTERN.fullmatch(value) is None for value in identifiers
    ):
        raise ClutterScorerError("OPAQUE_SEVEN_TRACK_SET_INVALID")
    rows = []
    for identifier in identifiers:
        row = np.asarray(tracks_m[identifier], dtype=np.float64)
        if row.shape != (six_track.RAW_EPOCHS,):
            raise ClutterScorerError("TRACK_SHAPE_INVALID")
        if not np.all(np.isfinite(row)):
            raise ClutterScorerError("TRACK_GAP_OR_NONFINITE")
        rows.append(row.copy())
    return identifiers, np.stack(rows)


def _validate_hypotheses(
    hypotheses: Sequence[OpaqueHypothesis],
) -> tuple[OpaqueHypothesis, ...]:
    values = tuple(hypotheses)
    if len(values) != HYPOTHESIS_COUNT:
        raise ClutterScorerError("OPAQUE_HYPOTHESIS_COUNT_INVALID")
    identifiers = [row.opaque_id for row in values]
    if len(set(identifiers)) != HYPOTHESIS_COUNT or any(
        HYPOTHESIS_ID_PATTERN.fullmatch(value) is None for value in identifiers
    ):
        raise ClutterScorerError("OPAQUE_HYPOTHESIS_IDS_INVALID")
    counts = {family: 0 for family in FAMILIES}
    for row in values:
        if row.family not in counts:
            raise ClutterScorerError("HYPOTHESIS_FAMILY_INVALID")
        counts[row.family] += 1
        indices = row.included_track_indices
        if (
            len(indices) != EVALUATED_TRACK_COUNT
            or tuple(sorted(indices)) != indices
            or len(set(indices)) != EVALUATED_TRACK_COUNT
            or min(indices) < 0
            or max(indices) >= OBSERVED_TRACK_COUNT
        ):
            raise ClutterScorerError("INCLUDED_TRACK_INDICES_INVALID")
        matrix = np.asarray(row.model_matrix_m, dtype=np.float64)
        if matrix.shape != (EVALUATED_TRACK_COUNT, six_track.RAW_EPOCHS):
            raise ClutterScorerError("HYPOTHESIS_MATRIX_SHAPE_INVALID")
        if not np.all(np.isfinite(matrix)):
            raise ClutterScorerError("HYPOTHESIS_MATRIX_NONFINITE")
    expected = {
        FAMILY_ORBITAL: ORBITAL_HYPOTHESIS_COUNT,
        FAMILY_GEOMETRY_NULL: GEOMETRY_NULL_COUNT,
        FAMILY_AFFINE_NULL: AFFINE_NULL_COUNT,
    }
    if counts != expected:
        raise ClutterScorerError("HYPOTHESIS_FAMILY_COUNTS_INVALID")
    return values


def _score_row(
    observed: np.ndarray,
    track_ids: Sequence[str],
    hypothesis: OpaqueHypothesis,
) -> dict[str, object]:
    included = hypothesis.included_track_indices
    excluded_index = next(
        index for index in range(OBSERVED_TRACK_COUNT) if index not in included
    )
    selected_observed = observed[np.asarray(included, dtype=np.int64)]
    model = np.asarray(hypothesis.model_matrix_m, dtype=np.float64)
    centered_observed = six_track._center_common_mode(selected_observed)
    centered_model = six_track._center_common_mode(model)
    _, metrics = six_track._prefix_project(centered_observed - centered_model)
    return {
        "opaque_id": hypothesis.opaque_id,
        "family": hypothesis.family,
        "excluded_opaque_track": track_ids[excluded_index],
        "prefix_rms_m": _quantized(metrics["prefix_rms_m"]),
        "heldout_max_track_peak_to_peak_m": _quantized(
            metrics["heldout_max_track_peak_to_peak_m"]
        ),
        "heldout_rms_m": _quantized(metrics["heldout_rms_m"]),
        "effective_prefix_parameter_count": 2 * (EVALUATED_TRACK_COUNT - 1),
    }


def _rank_key(row: Mapping[str, object]) -> tuple[float, float, str]:
    return (
        float(row["heldout_max_track_peak_to_peak_m"]),
        float(row["heldout_rms_m"]),
        str(row["opaque_id"]),
    )


def score_one_clutter_tracks(
    tracks_m: Mapping[str, Sequence[float]],
    hypotheses: Sequence[OpaqueHypothesis],
    *,
    pairwise_guard_m: float,
) -> dict[str, object]:
    """Score all predeclared six-of-seven hypotheses without identity input."""

    guard = float(pairwise_guard_m)
    if not isfinite(guard) or guard <= 0.0:
        raise ClutterScorerError("PAIRWISE_GUARD_INVALID")
    track_ids, observed = _track_matrix(tracks_m)
    surface = _validate_hypotheses(hypotheses)
    rows: list[dict[str, object]] = []
    try:
        for hypothesis in surface:
            rows.append(_score_row(observed, track_ids, hypothesis))
        rows.sort(key=_rank_key)
        by_family = {
            family: sorted(
                (row for row in rows if row["family"] == family), key=_rank_key
            )
            for family in FAMILIES
        }
        best_orbital, runner_orbital = by_family[FAMILY_ORBITAL][:2]
        alternatives = sorted(
            by_family[FAMILY_GEOMETRY_NULL] + by_family[FAMILY_AFFINE_NULL],
            key=_rank_key,
        )
        best_alternative = alternatives[0]
        best_orbital_residual = float(
            best_orbital["heldout_max_track_peak_to_peak_m"]
        )
        runner_orbital_residual = float(
            runner_orbital["heldout_max_track_peak_to_peak_m"]
        )
        best_alternative_residual = float(
            best_alternative["heldout_max_track_peak_to_peak_m"]
        )
        assignment_margin = _quantized(
            runner_orbital_residual - best_orbital_residual
        )
        orbital_vs_null_margin = _quantized(
            best_alternative_residual - best_orbital_residual
        )
        null_vs_orbital_margin = _quantized(
            best_orbital_residual - best_alternative_residual
        )

        if (
            best_orbital_residual <= guard
            and assignment_margin > guard
            and orbital_vs_null_margin > guard
        ):
            state = "ORBITAL_INJECTION_PREFERRED"
            preferred_family = FAMILY_ORBITAL
            best_global = best_orbital
        elif (
            best_alternative_residual <= guard
            and null_vs_orbital_margin > guard
        ):
            state = "NONORBITAL_FAMILY_PREFERRED"
            preferred_family = str(best_alternative["family"])
            best_global = best_alternative
        elif min(best_orbital_residual, best_alternative_residual) > guard:
            state = "NO_ADMISSIBLE_HYPOTHESIS"
            preferred_family = None
            best_global = rows[0]
        else:
            state = "AMBIGUOUS"
            preferred_family = None
            best_global = rows[0]

        track_hash = sha256(
            strict_json(
                {
                    identifier: [float(value) for value in observed[index]]
                    for index, identifier in enumerate(track_ids)
                }
            ).encode("ascii")
        ).hexdigest()
        all_scores_hash = sha256(strict_json(rows).encode("ascii")).hexdigest()
        receipt = {
            "schema": "gnss-all-track-one-clutter-score-receipt-v1",
            "scorer_version": SCORER_VERSION,
            "track_ids": list(track_ids),
            "observed_track_count": OBSERVED_TRACK_COUNT,
            "evaluated_track_count_per_hypothesis": EVALUATED_TRACK_COUNT,
            "clutter_budget": CLUTTER_BUDGET,
            "track_set_sha256": track_hash,
            "track_or_observation_values_persisted": 0,
            "opaque_hypothesis_count": len(rows),
            "family_counts": {
                family: len(by_family[family]) for family in FAMILIES
            },
            "all_scores_sha256": all_scores_hash,
            "top_scores": rows[:5],
            "family_best": {
                family: by_family[family][0] for family in FAMILIES
            },
            "best_global_opaque_id": best_global["opaque_id"],
            "best_orbital_opaque_id": best_orbital["opaque_id"],
            "runner_orbital_opaque_id": runner_orbital["opaque_id"],
            "best_alternative_opaque_id": best_alternative["opaque_id"],
            "orbital_assignment_margin_m": assignment_margin,
            "orbital_vs_best_null_margin_m": orbital_vs_null_margin,
            "best_null_vs_orbital_margin_m": null_vs_orbital_margin,
            "pairwise_guard_m": guard,
            "score_state": state,
            "preferred_family": preferred_family,
            "common_mode": "REMOVED_WITHIN_EACH_INCLUDED_SIX_TRACK_SET",
            "effective_prefix_parameter_count_per_hypothesis": 10,
            "prefix_indices_inclusive": [0, six_track.PREFIX_EPOCHS - 1],
            "heldout_indices_inclusive": [
                six_track.PREFIX_EPOCHS,
                six_track.RAW_EPOCHS - 1,
            ],
            "heldout_refit": False,
            "free_time_phase": False,
            "identity_reveal_performed": False,
            "metric_quantization_decimal_places": METRIC_DECIMALS,
        }
        strict_json(receipt)
        return receipt
    finally:
        observed.fill(0.0)


def receipt_sha256(receipt: Mapping[str, object]) -> str:
    return sha256(strict_json(receipt).encode("ascii")).hexdigest()
