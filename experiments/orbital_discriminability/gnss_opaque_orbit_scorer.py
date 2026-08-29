"""Pure identity-blind scorer for one exact opaque trajectory bundle.

The scorer knows only six opaque identifiers, six same-grid arrays and the
frozen prefix/holdout rule.  It has no observation decoder, orbital compiler,
identity-reveal input, network client or write authority.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
import re
from typing import Final, Mapping, Sequence

import numpy as np


SCORER_VERSION: Final = "gnss-opaque-orbit-scorer-v1"
BUNDLE_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_OPAQUE_PREDICTIONS.json"
BUNDLE_CANONICAL_SHA256: Final = (
    "a36aed59f32ee9b409778e44a0b661aebbf83c0675c58473c6655ad562c82ee2"
)
BUNDLE_MANIFEST_SHA256: Final = (
    "0dbaa0339074529449a8aafdef39a500feea87d118dcaa0b1b0b86ae266a3186"
)
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
STEP_S: Final = 30.0
PAIRWISE_GUARD_M: Final = 7_339.701234647398
OPAQUE_ID_PATTERN: Final = re.compile(r"H_[0-9A-F]{16}")


class OpaqueOrbitScorerError(ValueError):
    """The sealed bundle or scoring input violates the frozen interface."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return sha256(payload).hexdigest()


def bundle_manifest_sha256(value: Mapping[str, object]) -> str:
    return sha256(strict_json(value).encode("ascii")).hexdigest()


def _read_strict_object(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise OpaqueOrbitScorerError("BUNDLE_NOT_OBJECT")
    return value


def load_exact_bundle(path: Path) -> dict[str, object]:
    path = Path(path)
    if path.name != BUNDLE_NAME or not path.is_file():
        raise OpaqueOrbitScorerError("BUNDLE_IDENTITY_CHANGED")
    if canonical_sha256(path) != BUNDLE_CANONICAL_SHA256:
        raise OpaqueOrbitScorerError("BUNDLE_CANONICAL_HASH_CHANGED")
    value = _read_strict_object(path)
    validate_bundle(value)
    return value


def validate_bundle(value: Mapping[str, object]) -> dict[str, np.ndarray]:
    if bundle_manifest_sha256(value) != BUNDLE_MANIFEST_SHA256:
        raise OpaqueOrbitScorerError("BUNDLE_MANIFEST_HASH_CHANGED")
    if set(value) != {"schema", "grid", "opaque_ids", "curves_m", "scoring"}:
        raise OpaqueOrbitScorerError("BUNDLE_SURFACE_CHANGED")
    if value.get("schema") != "gnss-blind-orbit-opaque-prediction-bundle-v1":
        raise OpaqueOrbitScorerError("BUNDLE_SCHEMA_CHANGED")
    expected_grid = {
        "time_system": "GPS",
        "epochs": RAW_EPOCHS,
        "step_s": STEP_S,
        "prefix_indices_inclusive": [0, PREFIX_EPOCHS - 1],
        "heldout_indices_inclusive": [PREFIX_EPOCHS, RAW_EPOCHS - 1],
    }
    if value.get("grid") != expected_grid:
        raise OpaqueOrbitScorerError("BUNDLE_GRID_CHANGED")
    expected_scoring = {
        "per_hypothesis_prefix_fit": ["CONSTANT", "LINEAR_RATE"],
        "per_hypothesis_parameter_count": 2,
        "pairwise_guard_m": PAIRWISE_GUARD_M,
        "metric_order": ["PEAK_TO_PEAK_M", "RMS_M", "OPAQUE_ID"],
        "heldout_refit": False,
        "free_time_phase": False,
        "time_warp": False,
    }
    if value.get("scoring") != expected_scoring:
        raise OpaqueOrbitScorerError("BUNDLE_SCORING_CHANGED")
    identifiers = value.get("opaque_ids")
    curves = value.get("curves_m")
    if not isinstance(identifiers, list) or len(identifiers) != 6:
        raise OpaqueOrbitScorerError("OPAQUE_ID_SET_CHANGED")
    if identifiers != sorted(identifiers) or len(set(identifiers)) != 6:
        raise OpaqueOrbitScorerError("OPAQUE_ID_ORDER_CHANGED")
    if any(OPAQUE_ID_PATTERN.fullmatch(value) is None for value in identifiers):
        raise OpaqueOrbitScorerError("OPAQUE_ID_FORMAT_CHANGED")
    if not isinstance(curves, Mapping) or set(curves) != set(identifiers):
        raise OpaqueOrbitScorerError("OPAQUE_CURVE_SET_CHANGED")
    arrays = {
        identifier: np.asarray(curves[identifier], dtype=np.float64)
        for identifier in identifiers
    }
    if any(array.shape != (RAW_EPOCHS,) for array in arrays.values()):
        raise OpaqueOrbitScorerError("OPAQUE_CURVE_SHAPE_CHANGED")
    if any(not np.all(np.isfinite(array)) for array in arrays.values()):
        raise OpaqueOrbitScorerError("OPAQUE_CURVE_NONFINITE")
    return arrays


def _finite_observation(values: Sequence[float]) -> np.ndarray:
    observed = np.asarray(values, dtype=np.float64)
    if observed.shape != (RAW_EPOCHS,):
        raise OpaqueOrbitScorerError("OBSERVED_COORDINATE_SHAPE_INVALID")
    if not np.all(np.isfinite(observed)):
        raise OpaqueOrbitScorerError("OBSERVED_COORDINATE_NONFINITE")
    return observed


def _prefix_fit_metrics(residual: np.ndarray) -> dict[str, float]:
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    prefix_x = elapsed[:PREFIX_EPOCHS]
    prefix_y = residual[:PREFIX_EPOCHS]
    x_mean = float(np.mean(prefix_x))
    y_mean = float(np.mean(prefix_y))
    centered_x = prefix_x - x_mean
    denominator = float(centered_x @ centered_x)
    if denominator <= 0.0:
        raise OpaqueOrbitScorerError("PREFIX_TIME_BASIS_INVALID")
    rate = float(centered_x @ (prefix_y - y_mean) / denominator)
    constant = y_mean - rate * x_mean
    projected = residual - (constant + rate * elapsed)
    heldout = projected[PREFIX_EPOCHS:]
    prefix = projected[:PREFIX_EPOCHS]
    return {
        "prefix_constant_m": constant,
        "prefix_rate_m_s": rate,
        "prefix_rmse_m": sqrt(float(np.mean(prefix * prefix))),
        "heldout_peak_to_peak_m": float(np.ptp(heldout)),
        "heldout_rms_m": sqrt(float(np.mean(heldout * heldout))),
    }


def score(
    observed_m: Sequence[float], bundle: Mapping[str, object]
) -> dict[str, object]:
    observed = _finite_observation(observed_m)
    curves = validate_bundle(bundle)
    rows = []
    for identifier in sorted(curves):
        rows.append(
            {
                "opaque_id": identifier,
                **_prefix_fit_metrics(observed - curves[identifier]),
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
    preferred = preference_margin > PAIRWISE_GUARD_M
    observed_hash = sha256(
        strict_json([float(value) for value in observed]).encode("ascii")
    ).hexdigest()
    receipt = {
        "schema": "gnss-opaque-orbit-score-receipt-v1",
        "scorer_version": SCORER_VERSION,
        "bundle_canonical_sha256": BUNDLE_CANONICAL_SHA256,
        "bundle_manifest_sha256": BUNDLE_MANIFEST_SHA256,
        "observed_coordinate_sha256": observed_hash,
        "observed_values_persisted": 0,
        "prefix_indices_inclusive": [0, PREFIX_EPOCHS - 1],
        "heldout_indices_inclusive": [PREFIX_EPOCHS, RAW_EPOCHS - 1],
        "scores": rows,
        "best_opaque_id": str(best["opaque_id"]),
        "runner_up_opaque_id": str(runner_up["opaque_id"]),
        "preference_margin_m": preference_margin,
        "pairwise_guard_m": PAIRWISE_GUARD_M,
        "opaque_outcome": (
            "OPAQUE_HYPOTHESIS_PREFERRED" if preferred else "AMBIGUOUS"
        ),
        "identity_reveal_performed": False,
        "same_loop_parameter_count": 2,
        "heldout_refit": False,
        "free_time_phase": False,
    }
    strict_json(receipt)
    observed.fill(0.0)
    for curve in curves.values():
        curve.fill(0.0)
    return receipt


def score_receipt_sha256(receipt: Mapping[str, object]) -> str:
    return sha256(strict_json(receipt).encode("ascii")).hexdigest()
