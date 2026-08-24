"""Offline continuous-phase quotient spike on the closed G14/G17 fixture.

The compiler accepts only the exact broadcast-navigation artifact and the
frozen geometry-screen receipt. It has no observation-product input surface.
G14/G17 is historical mechanism-development material and can never be
promoted by this result.
"""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from math import sin, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as old
from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_orbit_pair_envelope as frozen
from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair


COMPILER_VERSION: Final = "gnss-continuous-phase-quotient-spike-v1"
TARGET: Final = frozen.TARGET
REFERENCE: Final = frozen.REFERENCE
WRONG_TARGET: Final = frozen.WRONG_TARGET
DOY: Final = frozen.DOY
OUTCOME_DISCRIMINATIVE: Final = "PHASE_QUOTIENT_MECHANISM_DISCRIMINATIVE"
OUTCOME_ENVELOPE_DOMINATES: Final = "PHASE_QUOTIENT_PHYSICAL_ENVELOPE_DOMINATES"
OUTCOME_WITNESS_INSUFFICIENT: Final = "PHASE_QUOTIENT_WITNESS_TOPOLOGY_INSUFFICIENT"
SYNTHETIC_LOS_ACCELERATION_M_S2: Final = 5.0e-5


class PhaseQuotientError(ValueError):
    """A frozen authority or numerical invariant is inadmissible."""


def phase_prefix_metrics(
    curve_m: Sequence[float],
    split: int = pair.CALIBRATION_EPOCHS,
    step_s: float = base.GRID_STEP_S,
) -> dict[str, float]:
    values = np.asarray(curve_m, dtype=np.float64)
    if values.ndim != 1 or values.size <= split or split < 2:
        raise PhaseQuotientError("invalid phase coordinate or prefix")
    if not np.all(np.isfinite(values)) or step_s <= 0.0:
        raise PhaseQuotientError("non-finite phase coordinate")
    elapsed = np.arange(values.size, dtype=np.float64) * step_s
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(design, values[:split], rcond=None)
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    calibration = residual[:split]
    heldout = residual[split:]
    return {
        "constant_m": float(coefficients[0]),
        "rate_m_s": float(coefficients[1]),
        "calibration_prefix_rmse_m": float(sqrt(float(np.mean(calibration**2)))),
        "heldout_peak_to_peak_m": float(np.ptp(heldout)),
        "heldout_rms_m": float(sqrt(float(np.mean(heldout**2)))),
    }


def double_difference_range_m(
    left_target_m: Sequence[float],
    left_reference_m: Sequence[float],
    right_target_m: Sequence[float],
    right_reference_m: Sequence[float],
) -> np.ndarray:
    arrays = [
        np.asarray(value, dtype=np.float64)
        for value in (
            left_target_m,
            left_reference_m,
            right_target_m,
            right_reference_m,
        )
    ]
    if any(array.shape != arrays[0].shape for array in arrays):
        raise PhaseQuotientError("range shapes differ")
    if arrays[0].ndim != 1 or not all(np.all(np.isfinite(array)) for array in arrays):
        raise PhaseQuotientError("invalid range coordinate")
    return (arrays[0] - arrays[1]) - (arrays[2] - arrays[3])


def range_to_station_m(position_m: np.ndarray, station_ecef_m: np.ndarray) -> np.ndarray:
    position = np.asarray(position_m, dtype=np.float64)
    station = np.asarray(station_ecef_m, dtype=np.float64)
    if position.ndim != 2 or position.shape[1] != 3 or station.shape != (3,):
        raise PhaseQuotientError("invalid position geometry")
    result = np.linalg.norm(position - station, axis=1)
    if not np.all(np.isfinite(result)):
        raise PhaseQuotientError("non-finite geometric range")
    return result


def per_link_interval_term(
    definition: Mapping[str, object],
    projection_gain: float,
) -> dict[str, object]:
    per_link = float(definition["per_link_path_bound_m"])
    if not np.isfinite(per_link) or per_link < 0.0:
        raise PhaseQuotientError("invalid per-link path interval")
    coordinate_amplitude = 4.0 * per_link
    return {
        **definition,
        "four_link_coordinate_amplitude_bound_m": coordinate_amplitude,
        "affine_projection_peak_to_peak_gain": projection_gain,
        "heldout_peak_to_peak_bound_m": coordinate_amplitude * projection_gain,
        "basis_phase_coordinate": (
            "FOUR_LINK_SIGNED_SUM_WITH_PER_LINK_INTERVAL_THEN_PREFIX_AFFINE_"
            "PROJECTION"
        ),
    }


def quantization_term(projection_gain: float) -> dict[str, object]:
    alpha, beta = old.ionosphere_free_coefficients()
    per_link = 0.5 * old.RINEX_PHASE_QUANTIZATION_CYCLES * (
        abs(alpha) * base.SPEED_OF_LIGHT_M_S / old.GPS_L1_HZ
        + abs(beta) * base.SPEED_OF_LIGHT_M_S / old.GPS_L2_HZ
    )
    return per_link_interval_term(
        {
            "term": "RINEX_CARRIER_PHASE_QUANTIZATION",
            "state": "KNOWN_FORMAT_BOUND",
            "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
            "per_link_path_bound_m": per_link,
            "basis": (
                "HALF_RINEX_F14_3_CYCLE_QUANTIZATION_AFTER_IONOSPHERE_FREE_"
                "COMBINATION"
            ),
        },
        projection_gain,
    )


def timing_term(
    curve,
    feature: slice,
    target: str = TARGET,
) -> dict[str, object]:
    nominal = curve(target, 0.0, 0.0)[feature]
    maximum = 0.0
    controlling = None
    for left_offset in (-old.MAX_STATION_EPOCH_ERROR_S, old.MAX_STATION_EPOCH_ERROR_S):
        for right_offset in (
            -old.MAX_STATION_EPOCH_ERROR_S,
            old.MAX_STATION_EPOCH_ERROR_S,
        ):
            shifted = curve(target, left_offset, right_offset)[feature]
            bound = phase_prefix_metrics(shifted - nominal)[
                "heldout_peak_to_peak_m"
            ]
            if bound > maximum:
                maximum = float(bound)
                controlling = [left_offset, right_offset]
    return {
        "term": "STATION_EVENT_TIME",
        "state": "MODELED_DIRECT_TRAJECTORY_ENVELOPE",
        "provenance": "STRUCTURAL_HALF_CADENCE_BOUND",
        "parameter_interval_s": [
            -old.MAX_STATION_EPOCH_ERROR_S,
            old.MAX_STATION_EPOCH_ERROR_S,
        ],
        "controlling_station_offsets_s": controlling,
        "heldout_peak_to_peak_bound_m": maximum,
        "basis": "DIRECT_RANGE_TRAJECTORY_AT_T_PLUS_OR_MINUS_DELTA_T",
    }


def troposphere_term(
    elevation: Mapping[tuple[str, str], np.ndarray],
    feature: slice,
    target: str = TARGET,
    reference: str = REFERENCE,
) -> dict[str, object]:
    left, right = (station.station_id for station in base.STATIONS)

    def mapping(station_id: str, satellite: str) -> np.ndarray:
        radians = np.radians(elevation[(station_id, satellite)])
        return 1.0 / np.maximum(
            np.sin(radians), sin(np.radians(base.MINIMUM_ELEVATION_DEG))
        )

    left_shape = mapping(left, target) - mapping(left, reference)
    right_shape = mapping(right, target) - mapping(right, reference)
    maximum = 0.0
    controlling = None
    for left_ztd in (0.0, old.MAX_ZENITH_TROPOSPHERE_M):
        for right_ztd in (0.0, old.MAX_ZENITH_TROPOSPHERE_M):
            path = (left_ztd * left_shape - right_ztd * right_shape)[feature]
            bound = phase_prefix_metrics(path)["heldout_peak_to_peak_m"]
            if bound > maximum:
                maximum = float(bound)
                controlling = [left_ztd, right_ztd]
    return {
        "term": "DIFFERENTIAL_TROPOSPHERE",
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "zenith_delay_interval_m": [0.0, old.MAX_ZENITH_TROPOSPHERE_M],
        "controlling_station_zenith_delays_m": controlling,
        "heldout_peak_to_peak_bound_m": maximum,
        "basis": "CONSERVATIVE_ONE_OVER_SINE_MAPPING_IN_PHASE_RANGE_UNITS",
    }


def combine_terms(
    controlling_separation_m: float,
    terms: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    contributions = [
        float(term["heldout_peak_to_peak_bound_m"]) for term in terms
    ]
    if (
        not np.isfinite(controlling_separation_m)
        or controlling_separation_m <= 0.0
        or not contributions
        or any(not np.isfinite(value) or value < 0.0 for value in contributions)
    ):
        raise PhaseQuotientError("invalid physical-envelope combination")
    one_model = float(sum(contributions))
    pairwise = float(old.PAIRWISE_ENVELOPE_MULTIPLIER * one_model)
    margin = float(controlling_separation_m - pairwise)
    return {
        "one_model_physical_envelope_m": one_model,
        "pairwise_comparison_envelope_m": pairwise,
        "remaining_physical_margin_m": margin,
        "negative_result_interpretable_if_future_measurement_admitted": margin > 0.0,
        "outcome": (
            OUTCOME_DISCRIMINATIVE if margin > 0.0 else OUTCOME_ENVELOPE_DOMINATES
        ),
    }


def witness_topology() -> dict[str, object]:
    return {
        "future_core_phase": ["L1C", "L2W"],
        "cycle_slip_and_continuity": {
            "LLI_ON_L1C_AND_L2W": "REQUIRED_BREAKS_SEGMENT",
            "GEOMETRY_FREE_PHASE_CONTINUITY": "REQUIRED_BREAKS_SEGMENT",
            "NO_INTERPOLATION_OR_GAP_BRIDGING": True,
        },
        "same_path_code": {
            "fields": ["C1C", "C2W"],
            "role": "PREDECLARED_ADMISSION_OR_REFUSAL_WITNESS_NOT_PHASE_CORRECTION",
            "fatal_every_epoch": False,
            "missing_quantitative_rule": "NOT_DETECTABLE",
        },
        "optional_diagnostic": {
            "fields": ["S1C", "S2W"],
            "fatal_without_quantitative_rule_and_coherent_units": False,
        },
        "suffix_rule": (
            "WITNESSES_MAY_APPLY_ONLY_FROZEN_HEALTH_OR_REFUSAL_RULES_AND_MAY_"
            "NOT_TUNE_THE_ORBITAL_SCORE"
        ),
    }


def synthetic_mismatch_stress() -> dict[str, object]:
    elapsed = np.arange(pair.FEATURE_EPOCHS, dtype=np.float64) * base.GRID_STEP_S
    mismatch = 0.5 * SYNTHETIC_LOS_ACCELERATION_M_S2 * elapsed**2
    score = phase_prefix_metrics(mismatch)
    return {
        "family": "CONSTANT_UNMODELED_LINE_OF_SIGHT_ACCELERATION",
        "generated_from_nominal_orbit": False,
        "acceleration_m_s2": SYNTHETIC_LOS_ACCELERATION_M_S2,
        "same_prefix_only_affine_projection": True,
        "heldout_peak_to_peak_m": score["heldout_peak_to_peak_m"],
        "heldout_rms_m": score["heldout_rms_m"],
        "survives_affine_null": score["heldout_peak_to_peak_m"] > 0.0,
    }


def manifest() -> dict[str, object]:
    alpha, beta = old.ionosphere_free_coefficients()
    return {
        "compiler_version": COMPILER_VERSION,
        "phase": "SPIKE",
        "physical_question": (
            "CAN_CONTINUOUS_IONOSPHERE_FREE_CARRIER_PHASE_PRESERVE_THE_FROZEN_"
            "ORBITAL_VERSUS_NULL_STRUCTURE_AFTER_THE_SAME_PHYSICAL_INTERVALS"
        ),
        "new_information": (
            "WHETHER_PREMATURE_TIME_DIFFERENTIATION_CAUSED_THE_CLOSED_"
            "FREQUENCY_COORDINATE_TO_LOSE_FALSIFICATION_POWER"
        ),
        "fixture": {
            "role": "HISTORICAL_DEVELOPMENT_ONLY_NEVER_PRIMARY",
            "doy": DOY,
            "target": TARGET,
            "reference": REFERENCE,
            "wrong_target": WRONG_TARGET,
            "screen_receipt_sha256": frozen.SCREEN_RECEIPT_SHA256,
        },
        "coordinate": {
            "units": "IONOSPHERE_FREE_CARRIER_DERIVED_RANGE_METERS",
            "weights": {"L1C": alpha, "L2W": beta},
            "weight_invariants": {
                "sum": alpha + beta,
                "first_order_dispersive_sum": (
                    alpha / old.GPS_L1_HZ**2 + beta / old.GPS_L2_HZ**2
                ),
            },
            "station_satellite_order": (
                "(GOLD_TARGET-GOLD_REFERENCE)-(NLIB_TARGET-NLIB_REFERENCE)"
            ),
            "time_derivative": "NONE",
            "prefix_nuisance": ["CONSTANT_AMBIGUITY", "CONSTANT_RANGE_RATE"],
            "suffix_refit": False,
        },
        "partition": frozen.manifest()["partition"],
        "nulls": ["PREFIX_AFFINE", "FROZEN_WRONG_ORBIT_G22"],
        "witness_topology": witness_topology(),
        "envelope": {
            "combination": "LINEAR_SUM_THEN_TWO_MODEL_PAIRWISE_NO_RSS",
            "unresolved_as_zero": False,
            "per_link_intervals": [
                dict(definition) for definition in old.GENERIC_PATH_BOUNDS_M
            ],
            "timing": "DIRECT_T_PLUS_OR_MINUS_DELTA_T_RANGE_TRAJECTORIES",
        },
        "forbidden": [
            "observation product discovery selection header or payload access",
            "new satellite station date signal or window selection",
            "retroactive promotion of G14 G17",
            "suffix nuisance fit",
            "measurement authorization",
            "generic framework or new gate",
        ],
    }


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def compile_mechanism(navigation: Path, screen_receipt: Path) -> dict[str, object]:
    authority = frozen.validate_navigation(navigation)
    frozen.validate_screen_receipt(screen_receipt)
    records = base.parse_gps_navigation(navigation)
    epochs = pair.gps_day_grid(authority)
    raw_start = frozen._gps_index(epochs, frozen.RAW_START_GPS)
    raw_stop = frozen._gps_index(epochs, frozen.RAW_STOP_GPS) + 1
    feature = slice(raw_start + 1, raw_stop - 1)
    if len(epochs[feature]) != pair.FEATURE_EPOCHS:
        raise PhaseQuotientError("frozen phase grid changed")

    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    positions: dict[tuple[str, float], np.ndarray] = {}

    def position(satellite: str, offset_s: float) -> np.ndarray:
        key = satellite, offset_s
        if key not in positions:
            shifted_epochs = tuple(
                epoch + timedelta(seconds=offset_s) for epoch in epochs
            )
            positions[key] = np.asarray(
                [
                    base.broadcast_ecef(
                        base.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in shifted_epochs
                ]
            )
        return positions[key]

    left, right = (station.station_id for station in base.STATIONS)

    def curve(target: str, left_offset_s: float, right_offset_s: float) -> np.ndarray:
        return double_difference_range_m(
            range_to_station_m(position(target, left_offset_s), station_ecef[left]),
            range_to_station_m(
                position(REFERENCE, left_offset_s), station_ecef[left]
            ),
            range_to_station_m(position(target, right_offset_s), station_ecef[right]),
            range_to_station_m(
                position(REFERENCE, right_offset_s), station_ecef[right]
            ),
        )

    nominal_full = curve(TARGET, 0.0, 0.0)
    alternative_full = curve(WRONG_TARGET, 0.0, 0.0)
    nominal = nominal_full[feature]
    alternative = alternative_full[feature]
    affine = phase_prefix_metrics(nominal)
    wrong = phase_prefix_metrics(nominal - alternative)
    controlling = min(
        affine["heldout_peak_to_peak_m"], wrong["heldout_peak_to_peak_m"]
    )
    controlling_null = (
        "PREFIX_AFFINE"
        if affine["heldout_peak_to_peak_m"] <= wrong["heldout_peak_to_peak_m"]
        else "FROZEN_WRONG_ORBIT_G22"
    )
    frequency_scale = -old.GPS_L1_HZ / base.SPEED_OF_LIGHT_M_S
    legacy_nominal = (
        frequency_scale
        * np.gradient(nominal_full, base.GRID_STEP_S, edge_order=2)
    )[feature]
    legacy_alternative = (
        frequency_scale
        * np.gradient(alternative_full, base.GRID_STEP_S, edge_order=2)
    )[feature]
    legacy_affine = pair.prefix_affine(legacy_nominal)
    legacy_wrong = pair.prefix_affine(legacy_nominal - legacy_alternative)
    legacy_controlling = min(
        legacy_affine["heldout_peak_to_peak_hz"],
        legacy_wrong["heldout_peak_to_peak_hz"],
    )
    if abs(legacy_controlling - frozen.FROZEN_CONTROLLING_SEPARATION_HZ) > 1e-6:
        raise PhaseQuotientError("phase derivative does not recover frozen Doppler")

    elevation = {
        (station.station_id, satellite): base.elevation_deg(
            position(satellite, 0.0),
            station,
            station_ecef[station.station_id],
        )
        for station in base.STATIONS
        for satellite in (TARGET, REFERENCE)
    }
    projection_gain = old.affine_projection_peak_to_peak_gain(
        pair.FEATURE_EPOCHS,
        pair.CALIBRATION_EPOCHS,
        base.GRID_STEP_S,
    )
    terms = [
        timing_term(curve, feature),
        troposphere_term(elevation, feature),
        quantization_term(projection_gain),
    ]
    terms.extend(
        per_link_interval_term(definition, projection_gain)
        for definition in old.GENERIC_PATH_BOUNDS_M
    )
    decision = combine_terms(controlling, terms)
    for term in terms:
        term["pairwise_contribution_m"] = float(
            old.PAIRWISE_ENVELOPE_MULTIPLIER
            * float(term["heldout_peak_to_peak_bound_m"])
        )
    terms.sort(
        key=lambda term: (-float(term["pairwise_contribution_m"]), str(term["term"]))
    )
    mismatch = synthetic_mismatch_stress()
    if not mismatch["survives_affine_null"]:
        raise PhaseQuotientError("synthetic mismatch became affine")

    result = {
        "schema": "gnss-continuous-phase-quotient-spike-receipt-v1",
        "compiler_version": COMPILER_VERSION,
        "manifest_sha256": manifest_sha256(),
        "navigation": {
            "name": authority.name,
            "bytes": authority.bytes,
            "sha256": authority.sha256,
        },
        "screen_receipt_sha256": frozen.SCREEN_RECEIPT_SHA256,
        "fixture_role": "HISTORICAL_DEVELOPMENT_ONLY_NEVER_PRIMARY",
        "geometry": {
            "doy": DOY,
            "target": TARGET,
            "reference": REFERENCE,
            "wrong_target": WRONG_TARGET,
            "feature_start_gps": "2026-08-08T05:07:30 GPS",
            "feature_stop_gps": "2026-08-08T08:19:00 GPS",
        },
        "coordinate": manifest()["coordinate"],
        "partition": manifest()["partition"],
        "null_scores": {
            "prefix_affine": affine,
            "wrong_orbit_g22": wrong,
            "controlling_null": controlling_null,
            "controlling_heldout_separation_m": controlling,
        },
        "legacy_frequency_regression": {
            "derivation": "NEGATIVE_L1_OVER_C_TIMES_CENTRAL_RANGE_DERIVATIVE",
            "prefix_affine_heldout_peak_to_peak_hz": legacy_affine[
                "heldout_peak_to_peak_hz"
            ],
            "g22_heldout_peak_to_peak_hz": legacy_wrong[
                "heldout_peak_to_peak_hz"
            ],
            "controlling_heldout_separation_hz": legacy_controlling,
            "frozen_expected_hz": frozen.FROZEN_CONTROLLING_SEPARATION_HZ,
            "absolute_error_hz": abs(
                legacy_controlling - frozen.FROZEN_CONTROLLING_SEPARATION_HZ
            ),
        },
        "affine_projection_peak_to_peak_gain": projection_gain,
        "physical_terms": terms,
        "synthetic_model_mismatch": mismatch,
        **decision,
        "interpretation": (
            "CONTINUOUS_PHASE_COORDINATE_RETAINS_POSITIVE_HISTORICAL_"
            "MECHANISM_MARGIN_NEW_CANDIDATE_SELECTION_STILL_REQUIRED"
            if decision["outcome"] == OUTCOME_DISCRIMINATIVE
            else "PHYSICAL_ENVELOPE_ABSORBS_THE_PHASE_COORDINATE"
        ),
        "observation_access": {
            "products_discovered": 0,
            "products_selected": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
        },
        "new_candidate_selected": False,
        "prospective_plan_frozen": False,
        "measurement_authorized": False,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("navigation", type=Path)
    parser.add_argument("screen_receipt", type=Path)
    print(strict_json(compile_mechanism(**vars(parser.parse_args()))))
