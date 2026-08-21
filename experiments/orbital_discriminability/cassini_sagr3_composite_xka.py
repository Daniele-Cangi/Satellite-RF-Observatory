"""Offline audit of the frozen Cassini SAGR3 DSS-25 X/Ka composition.

This module does not accept RSR headers, samples, amplitude, detector output, or
network input.  It asks a narrower question: can the already qualified DSS-25
X/Ka branches define a dispersive-free DSS-25 coordinate which can replace the
DSS-25 X term in the frozen DSS-25 minus DSS-65 observable?

The answer is deliberately split in two.  The algebra is valid for exact,
simultaneous sky-frequency coordinates.  The frozen aggregate header receipt
does not retain that time-varying carrier grid, and no IQ has been observed, so
the composition is not promoted to a physical measurement.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as geometry,
)


AUDIT_VERSION: Final = "cassini-sagr3-composite-xka-offline-audit-v1"
OUTCOME_NOT_ADMITTED: Final = "CASSINI_COMPOSITE_OBSERVABLE_NOT_ADMITTED"
COMPOSITION_ADMITTED: Final = "COMPOSITION_ALGEBRA_ADMITTED"
PLASMA_NOT_EVALUATED: Final = "PLASMA_MEASUREMENT_NOT_EVALUATED_WITHOUT_IQ"

PARENT_RECEIPTS: Final = {
    "CASSINI_SAGR3_DISTRIBUTED_HEADER_RECEIPT.json": (
        "20e8b62437eb4afa501a3b9a967c6817eb57bf0ac1d112a6c5fab79a3fdb6976"
    ),
    "CASSINI_SAGR3_TRANSITION_AUDIT_RECEIPT.json": (
        "34e269c054ce65aa67c4b2263b89d2aec37ed8d37dbdd85c9ba50b0e72d15265"
    ),
    "CASSINI_SAGR3_PRETRANSITION_OPEN_TERM_AUDIT_RECEIPT.json": (
        "ee2f5fe4ec719a4272ef09d42f666908d2bc99846bb3a6efa9cd337ebc3ddd3c"
    ),
    "CASSINI_SAGR3_DISTRIBUTED_GEOMETRY_RECEIPT.json": (
        "680615c660ca22e068d61c4715daa80d44f62f94dc9f79a0dedc9941b275d59e"
    ),
}

CONTROLLING_HELDOUT_PEAK_TO_PEAK_HZ: Final = 0.07231370056321107
TIMING_ENVELOPE_HZ: Final = 0.000007482903185973555


class CassiniCompositeXKaError(ValueError):
    """The frozen composite audit inputs are inconsistent."""


def composition_weights(
    x_carrier_hz: Sequence[float] | float,
    ka_carrier_hz: Sequence[float] | float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return weights which preserve a common fraction and cancel ``p/f^2``.

    For ``z(f) = g + p/f^2`` the returned weights satisfy, at every epoch,
    ``w_x + w_ka = 1`` and ``w_x/f_x^2 + w_ka/f_ka^2 = 0``.
    """

    x = np.asarray(x_carrier_hz, dtype=np.float64)
    ka = np.asarray(ka_carrier_hz, dtype=np.float64)
    try:
        x, ka = np.broadcast_arrays(x, ka)
    except ValueError as exc:
        raise CassiniCompositeXKaError(
            "X and Ka carrier coordinates are not broadcast-compatible"
        ) from exc
    if (
        not np.all(np.isfinite(x))
        or not np.all(np.isfinite(ka))
        or np.any(x <= 0.0)
        or np.any(ka <= 0.0)
    ):
        raise CassiniCompositeXKaError("carrier coordinates must be finite and positive")
    denominator = ka * ka - x * x
    if np.any(denominator == 0.0):
        raise CassiniCompositeXKaError("X and Ka carrier coordinates must differ")
    return -(x * x) / denominator, (ka * ka) / denominator


def compose_dss25_common_fraction(
    dss25_x_fraction: Sequence[float],
    dss25_ka_fraction: Sequence[float],
    x_carrier_hz: Sequence[float] | float,
    ka_carrier_hz: Sequence[float] | float,
) -> np.ndarray:
    """Compose the DSS-25 common fractional coordinate without fitting data."""

    x_fraction = _finite_vector("DSS-25 X fraction", dss25_x_fraction)
    ka_fraction = _finite_vector("DSS-25 Ka fraction", dss25_ka_fraction)
    if x_fraction.shape != ka_fraction.shape:
        raise CassiniCompositeXKaError("DSS-25 X and Ka arrays must be shape-matched")
    weight_x, weight_ka = composition_weights(x_carrier_hz, ka_carrier_hz)
    try:
        return weight_x * x_fraction + weight_ka * ka_fraction
    except ValueError as exc:
        raise CassiniCompositeXKaError(
            "carrier coordinate grid does not match the measurement grid"
        ) from exc


def compose_distributed_x_hz(
    dss25_x_fraction: Sequence[float],
    dss25_ka_fraction: Sequence[float],
    dss65_x_fraction: Sequence[float],
    x_carrier_hz: Sequence[float] | float,
    ka_carrier_hz: Sequence[float] | float,
) -> np.ndarray:
    """Return ``f_X * (DSS25_common - DSS65_X)`` on one explicit grid."""

    common = compose_dss25_common_fraction(
        dss25_x_fraction,
        dss25_ka_fraction,
        x_carrier_hz,
        ka_carrier_hz,
    )
    dss65 = _finite_vector("DSS-65 X fraction", dss65_x_fraction)
    if common.shape != dss65.shape:
        raise CassiniCompositeXKaError("DSS-25 and DSS-65 arrays must be shape-matched")
    x = np.asarray(x_carrier_hz, dtype=np.float64)
    try:
        result = x * (common - dss65)
    except ValueError as exc:
        raise CassiniCompositeXKaError(
            "X carrier coordinate grid does not match the measurement grid"
        ) from exc
    if not np.all(np.isfinite(result)):
        raise CassiniCompositeXKaError("composed observable is not finite")
    return np.asarray(result, dtype=np.float64)


def project_composite_prefix_affine(
    composite_hz: Sequence[float],
    *,
    calibration_records: int = geometry.PRETRANSITION_CALIBRATION_RECORDS,
    cadence_s: float = geometry.GRID_STEP_S,
) -> tuple[np.ndarray, Mapping[str, float]]:
    """Fit one constant+slope to the composite prefix and never refit suffix.

    No per-band affine is exposed: the nuisance projection occurs only after
    the three physical branches have been composed.
    """

    values = _finite_vector("composite curve", composite_hz)
    if calibration_records < 2 or calibration_records >= values.size:
        raise CassiniCompositeXKaError("invalid frozen calibration prefix")
    if not np.isfinite(cadence_s) or cadence_s <= 0.0:
        raise CassiniCompositeXKaError("cadence must be finite and positive")
    elapsed = np.arange(values.size, dtype=np.float64) * float(cadence_s)
    design = np.column_stack(
        (np.ones(calibration_records), elapsed[:calibration_records])
    )
    coefficients, *_ = np.linalg.lstsq(
        design, values[:calibration_records], rcond=None
    )
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[calibration_records:]
    metrics = {
        "peak_to_peak_hz": float(np.ptp(heldout)),
        "rms_hz": float(sqrt(float(np.mean(heldout * heldout)))),
        "maximum_absolute_hz": float(np.max(np.abs(heldout))),
        "calibration_prefix_rmse_hz": float(
            sqrt(float(np.mean(residual[:calibration_records] ** 2)))
        ),
    }
    return residual, metrics


def build_audit_receipt() -> dict[str, object]:
    """Build the deterministic metadata-only receipt from frozen aggregates."""

    parents = validate_parent_receipts()
    header = parents["CASSINI_SAGR3_DISTRIBUTED_HEADER_RECEIPT.json"]
    transition = parents["CASSINI_SAGR3_TRANSITION_AUDIT_RECEIPT.json"]
    open_terms = parents[
        "CASSINI_SAGR3_PRETRANSITION_OPEN_TERM_AUDIT_RECEIPT.json"
    ]

    products = {product["role"]: product for product in header["products"]}
    required_roles = {
        "MEASUREMENT_X_DSS25",
        "WITNESS_KA_DSS25",
        "MEASUREMENT_X_DSS65",
    }
    if set(products) != required_roles:
        raise CassiniCompositeXKaError("frozen three-product topology changed")
    if not all(
        header["clauses"][name]
        for name in (
            "all_streams_complete_and_continuous",
            "dss25_dss65_x_independent_receive_roots",
            "dss25_x_ka_distinct_receiver_channels",
            "dss25_x_ka_simultaneous",
        )
    ):
        raise CassiniCompositeXKaError("frozen topology clauses are not satisfied")
    if transition["pretransition_screen"]["records"] != geometry.PRETRANSITION_RECORDS:
        raise CassiniCompositeXKaError("pre-transition record count changed")
    if open_terms["outcome"] != "CASSINI_OPEN_TERM_BOUND_UNAVAILABLE":
        raise CassiniCompositeXKaError("authoritative open-term outcome changed")

    nominal_weight_x, nominal_weight_ka = composition_weights(
        geometry.X_BAND_HZ, geometry.KA_BAND_HZ
    )
    receipt: dict[str, object] = {
        "audit_version": AUDIT_VERSION,
        "audit_manifest_sha256": audit_manifest_sha256(),
        "scope": "FROZEN_AGGREGATE_METADATA_ONLY_NO_HEADER_REACCESS_NO_IQ",
        "outcome": OUTCOME_NOT_ADMITTED,
        "sub_outcomes": [
            COMPOSITION_ADMITTED,
            "DSS25_FIRST_ORDER_DISPERSIVE_CANCELLATION_STRUCTURALLY_VALID",
            PLASMA_NOT_EVALUATED,
            "PHYSICAL_NEGATIVE_NOT_INTERPRETABLE",
        ],
        "parent_receipts": {
            name: {"sha256": digest} for name, digest in PARENT_RECEIPTS.items()
        },
        "physical_question": (
            "Can simultaneous DSS-25 X/Ka define a first-order dispersive-free "
            "DSS-25 coordinate for the frozen DSS25-minus-DSS65 orbital test?"
        ),
        "maximum_authorized_claim": (
            "THE_COMPOSITION_IS_ALGEBRAICALLY_VALID_FOR_EXACT_SIMULTANEOUS_"
            "SKY_FREQUENCY_COORDINATES; NO_PLASMA_OR_RF_MEASUREMENT_WAS_EVALUATED"
        ),
        "observable": {
            "fractional_model": "z_station_band = g_station + p_station/f_band^2 + h_station_band",
            "dss25_common": "g25_hat = w25X*z25X + w25Ka*z25Ka",
            "distributed_x_hz": "C = fX*(g25_hat - z65X)",
            "weight_definition": {
                "w25X": "-fX^2/(fKa^2-fX^2)",
                "w25Ka": "fKa^2/(fKa^2-fX^2)",
                "w65X": -1.0,
            },
            "nominal_diagnostic_only": {
                "x_hz": geometry.X_BAND_HZ,
                "ka_hz": geometry.KA_BAND_HZ,
                "w25X": float(nominal_weight_x),
                "w25Ka": float(nominal_weight_ka),
            },
            "invariants": {
                "common_fraction_gain": "w25X + w25Ka = 1",
                "dss25_first_order_dispersive_gain": (
                    "w25X/fX^2 + w25Ka/fKa^2 = 0"
                ),
                "dss65_first_order_dispersive_gain": "-1/fX^2",
                "dss25_orbital_geometry_gain": 1.0,
                "dss65_orbital_geometry_gain": -1.0,
            },
        },
        "instantaneous_carrier_coordinate": {
            "required": (
                "EXACT_TIME_VARYING_X_AND_KA_SKY_FREQUENCY_ARRAYS_ON_THE_FROZEN_GRID"
            ),
            "state": "NOT_MATERIALIZED_FROM_PARENT_AGGREGATE_RECEIPTS",
            "nominal_weights_are_physical_admission": False,
            "reason": (
                "The aggregate header receipt retains finite-transform clauses and "
                "LO/DDC ranges, not the per-record carrier or polynomial grid."
            ),
        },
        "topology": {
            "shared_upstream": header["topology"]["shared_upstream"],
            "independent_receive_roots": header["topology"][
                "independent_x_receive_roots"
            ],
            "dss25_x_ka_are_distinct_channels_not_roots": True,
            "all_three_streams_continuous_and_simultaneous": True,
        },
        "projection": {
            "fit": "ONE_COMPOSITE_CONSTANT_PLUS_LINEAR_FIT_ON_PREFIX_ONLY",
            "calibration_records": geometry.PRETRANSITION_CALIBRATION_RECORDS,
            "holdout_records": geometry.PRETRANSITION_HOLDOUT_RECORDS,
            "per_band_affine": "PROHIBITED",
            "suffix_refit": "PROHIBITED",
        },
        "frozen_nulls": {
            "prefix_affine": {
                "heldout_peak_to_peak_hz": transition["pretransition_screen"][
                    "affine_null_heldout_peak_to_peak_hz"
                ],
                "inheritance": "UNCHANGED_BY_LINEAR_COMPOSITION_IDENTITY",
            },
            "saturn_barycenter_geometry_destroying": {
                "heldout_peak_to_peak_hz": CONTROLLING_HELDOUT_PEAK_TO_PEAK_HZ,
                "heldout_rms_hz": transition["pretransition_screen"][
                    "saturn_null_heldout_rms_hz"
                ],
                "heldout_max_abs_hz": transition["pretransition_screen"][
                    "saturn_null_heldout_max_abs_hz"
                ],
                "inheritance": "UNCHANGED_BY_LINEAR_COMPOSITION_IDENTITY",
            },
            "null_specific_transform_or_refit": "PROHIBITED",
        },
        "physical_ledger": [
            {
                "term": "DSS25_FIRST_ORDER_COLD_PLASMA",
                "state": "STRUCTURALLY_CANCELABLE_IF_EXACT_CARRIER_GRID_EXISTS",
                "measurement_state": "NOT_EVALUATED_WITHOUT_IQ",
            },
            {
                "term": "DSS65_FIRST_ORDER_COLD_PLASMA",
                "state": "UNRESOLVED",
                "reason": "DSS65 has X only in the frozen capability set",
            },
            {
                "term": "DIFFERENTIAL_TROPOSPHERE",
                "state": "UNRESOLVED",
                "reason": "nondispersive X/Ka composition does not cancel station differential",
            },
            {
                "term": "RECEIVER_PROPER_TIME_GRAVITY_DIFFERENTIAL",
                "state": "UNRESOLVED",
                "reason": "nondispersive station-rate differential survives",
            },
            {
                "term": "RELATIVISTIC_PROPAGATION_DIFFERENTIAL",
                "state": "UNRESOLVED",
                "reason": "parent audit has a model value but no admitted uncertainty bound",
            },
            {
                "term": "CROSS_BAND_AND_CROSS_STATION_RECEIVER_HARDWARE",
                "state": "UNRESOLVED",
                "coefficient": "w25X*h25X + w25Ka*h25Ka - h65X",
                "reason": "composition introduces a weighted DSS25 cross-band hardware term",
            },
        ],
        "controlling_geometry": {
            "heldout_peak_to_peak_hz": CONTROLLING_HELDOUT_PEAK_TO_PEAK_HZ,
            "timing_envelope_hz": TIMING_ENVELOPE_HZ,
            "can_increase_by_composition": False,
            "source": "FROZEN_PARENT_GEOMETRY_IDENTITY_NOT_RF_RECOMPUTATION",
        },
        "exact_blockers": [
            "EXACT_TIME_VARYING_X_KA_CARRIER_WEIGHT_GRID_NOT_RETAINED_IN_PARENT_RECEIPT",
            "DSS65_PLASMA_UNRESOLVED",
            "DIFFERENTIAL_TROPOSPHERE_UNRESOLVED",
            "RECEIVER_PROPER_TIME_GRAVITY_DIFFERENTIAL_UNRESOLVED",
            "RELATIVISTIC_PROPAGATION_DIFFERENTIAL_UNRESOLVED",
            "CROSS_BAND_AND_CROSS_STATION_HARDWARE_UNRESOLVED",
        ],
        "access": {
            "network": False,
            "header_reaccess": False,
            "iq_bytes_accessed": 0,
            "sample_or_amplitude_fields_represented": False,
            "detector_implemented": False,
        },
        "new_gate_created": False,
    }
    strict_json(receipt)
    return receipt


def validate_parent_receipts() -> dict[str, dict[str, object]]:
    directory = Path(__file__).parent
    loaded: dict[str, dict[str, object]] = {}
    for name, expected_sha256 in PARENT_RECEIPTS.items():
        raw = (directory / name).read_bytes()
        actual = sha256(raw).hexdigest()
        if actual != expected_sha256:
            raise CassiniCompositeXKaError(
                f"frozen parent receipt hash changed: {name}"
            )
        loaded[name] = json.loads(
            raw,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    return loaded


def audit_manifest_sha256() -> str:
    manifest = {
        "audit_version": AUDIT_VERSION,
        "parent_receipts": PARENT_RECEIPTS,
        "nominal_x_hz": geometry.X_BAND_HZ,
        "nominal_ka_hz": geometry.KA_BAND_HZ,
        "records": geometry.PRETRANSITION_RECORDS,
        "calibration_records": geometry.PRETRANSITION_CALIBRATION_RECORDS,
        "holdout_records": geometry.PRETRANSITION_HOLDOUT_RECORDS,
        "composition": "DSS25_FIRST_ORDER_DISPERSIVE_FREE_MINUS_DSS65_X",
        "projection": "ONE_COMPOSITE_PREFIX_AFFINE_ONLY",
        "nulls": ["PREFIX_AFFINE", "SATURN_BARYCENTER_GEOMETRY_DESTROYING"],
        "forbidden": [
            "network access",
            "header reaccess",
            "RSR or IQ access",
            "amplitude diagnostics",
            "per-band affine nuisance",
            "suffix refit",
            "detector implementation",
            "plasma measurement claim",
        ],
    }
    return sha256(strict_json(manifest).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _finite_vector(name: str, values: Sequence[float]) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size == 0 or not np.all(np.isfinite(result)):
        raise CassiniCompositeXKaError(f"{name} must be a non-empty finite vector")
    return result


if __name__ == "__main__":
    print(strict_json(build_audit_receipt()))
