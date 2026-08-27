"""Offline observer-transfer mechanism spike.

This module tests whether a single unseen GNSS observer can preserve a frozen
target-minus-reference orbital distinction after one fixed ambiguity anchor.
It accepts only two already frozen aggregate outcome receipts.  It has no
observation-product, locator, station-catalogue, header, or measurement-value
input surface.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from math import sin, sqrt
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.live_instrument.orbital_kernel import (
    Observer,
    OrbitalElements,
    compute_orbital_state,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as inherited,
)


COMPILER_VERSION: Final = "gnss-observer-transfer-spike-v1"
RECEIPT_NAME: Final = "GNSS_OBSERVER_TRANSFER_SPIKE_RECEIPT.json"
PRIMARY_OUTCOME_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_PRIMARY_OUTCOME.json"
PRIMARY_OUTCOME_SHA256: Final = (
    "66adf39fa1b10cbf43bdb712ebf4d1f3d8f598203caaa8fa2a41601fea511f9d"
)
REPEATED_OUTCOME_NAME: Final = "GNSS_PHASE_REPEATED_PASS_OUTCOME.json"
REPEATED_OUTCOME_SHA256: Final = (
    "629865857ccc3b17c54db14aefee60fe26eaf9b0c5ded7525c07bcdba30399da"
)

OUTCOME_DISCRIMINATIVE: Final = "OBSERVER_TRANSFER_MECHANISM_DISCRIMINATIVE"
OUTCOME_ENVELOPE_INSUFFICIENT: Final = (
    "OBSERVER_TRANSFER_ENVELOPE_INSUFFICIENT"
)
OUTCOME_FORBIDDEN_NUISANCE: Final = (
    "OBSERVER_TRANSFER_REQUIRES_FORBIDDEN_NUISANCE"
)

SAMPLE_COUNT: Final = 139
STEP_S: Final = 30.0
WITNESS_PREFIX_EPOCHS: Final = 79
CONFIRMATION_EPOCHS: Final = 60
CONFIRMATION_START: Final = WITNESS_PREFIX_EPOCHS
ANCHOR_INDEX: Final = 0
MINIMUM_ELEVATION_DEG: Final = 15.0
MAXIMUM_EVENT_TIME_ERROR_S: Final = 15.0
SYNTHETIC_START: Final = datetime(2026, 1, 1, 3, 25, tzinfo=timezone.utc)
SYNTHETIC_OBSERVER: Final = Observer(45.0, 10.0, 100.0)
SYNTHETIC_OBSERVER_ID: Final = "SYNTHETIC_C_NO_CAPABILITY_ROLE"


class ObserverTransferError(ValueError):
    """The spike authority, algebra, or numerical boundary is invalid."""


def _synthetic_omm(
    name: str,
    catalog_id: int,
    mean_anomaly_deg: float,
    raan_deg: float,
    mean_motion_rev_day: float,
) -> dict[str, object]:
    return {
        "OBJECT_NAME": name,
        "OBJECT_ID": f"2099-{catalog_id - 90000:03d}A",
        "EPOCH": "2026-01-01T00:00:00.000000",
        "MEAN_MOTION": mean_motion_rev_day,
        "ECCENTRICITY": 0.01,
        "INCLINATION": 55.0,
        "RA_OF_ASC_NODE": raan_deg,
        "ARG_OF_PERICENTER": 0.0,
        "MEAN_ANOMALY": mean_anomaly_deg,
        "EPHEMERIS_TYPE": 0,
        "CLASSIFICATION_TYPE": "U",
        "NORAD_CAT_ID": catalog_id,
        "ELEMENT_SET_NO": 1,
        "REV_AT_EPOCH": 1,
        "BSTAR": 0.0,
        "MEAN_MOTION_DOT": 0.0,
        "MEAN_MOTION_DDOT": 0.0,
    }


SYNTHETIC_MODELS: Final = {
    "TARGET_ORBIT": _synthetic_omm("SYNTHETIC_TARGET", 90001, 0.0, 20.0, 2.0056),
    "REFERENCE_ORBIT": _synthetic_omm(
        "SYNTHETIC_REFERENCE", 90002, 8.0, 20.0, 2.0056
    ),
    "WRONG_ORBIT_1": _synthetic_omm(
        "SYNTHETIC_WRONG_1", 90003, 0.35, 20.1, 2.0054
    ),
    "WRONG_ORBIT_2": _synthetic_omm(
        "SYNTHETIC_WRONG_2", 90004, -0.55, 19.8, 2.0060
    ),
}


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
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def dependency_versions() -> dict[str, str]:
    return {
        "numpy": np.__version__,
        "python": platform.python_version(),
        "skyfield": importlib.metadata.version("skyfield"),
    }


def validate_prior_evidence(primary_path: Path, repeated_path: Path) -> dict[str, object]:
    expected = (
        (
            Path(primary_path),
            PRIMARY_OUTCOME_NAME,
            PRIMARY_OUTCOME_SHA256,
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        ),
        (
            Path(repeated_path),
            REPEATED_OUTCOME_NAME,
            REPEATED_OUTCOME_SHA256,
            "ORBITAL_MODEL_REPEATED_PASS_PREFERRED",
        ),
    )
    result: dict[str, object] = {}
    for path, name, digest, outcome in expected:
        if path.name != name or not path.is_file():
            raise ObserverTransferError(f"PRIOR_EVIDENCE_MISSING:{name}")
        if canonical_sha256(path) != digest:
            raise ObserverTransferError(f"PRIOR_EVIDENCE_HASH_CHANGED:{name}")
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
        if value.get("outcome") != outcome:
            raise ObserverTransferError(f"PRIOR_EVIDENCE_OUTCOME_CHANGED:{name}")
        access = value.get("observation_access", {})
        if not isinstance(access, Mapping):
            raise ObserverTransferError(f"PRIOR_EVIDENCE_ACCESS_INVALID:{name}")
        result[name] = {
            "canonical_sha256": digest,
            "outcome": outcome,
            "claim_scope": value.get("claim_scope"),
            "role": "AGGREGATE_CLOSED_EVIDENCE_NO_VALUES_REOPENED",
        }
    return result


def _finite_vector(values: Sequence[float], label: str) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size < 3 or not np.all(np.isfinite(result)):
        raise ObserverTransferError(f"INVALID_{label.upper()}")
    return result


def anchored_coordinate(values: Sequence[float], anchor_index: int = ANCHOR_INDEX) -> np.ndarray:
    result = _finite_vector(values, "coordinate")
    if anchor_index != ANCHOR_INDEX:
        raise ObserverTransferError("ANCHOR_MUST_BE_FROZEN_SAMPLE_ZERO")
    return result - result[ANCHOR_INDEX]


def single_observer_quotient_m(
    target_phase_m: Sequence[float],
    reference_phase_m: Sequence[float],
) -> np.ndarray:
    target = _finite_vector(target_phase_m, "target_phase")
    reference = _finite_vector(reference_phase_m, "reference_phase")
    if target.shape != reference.shape:
        raise ObserverTransferError("PHASE_SHAPES_DIFFER")
    return target - reference


def frozen_adversarial_affine_null(
    target_prediction_m: Sequence[float],
    elapsed_s: Sequence[float],
) -> tuple[np.ndarray, float]:
    """Freeze the strongest zero-intercept affine mimic from prediction only."""

    target = anchored_coordinate(target_prediction_m)
    elapsed = _finite_vector(elapsed_s, "elapsed")
    if elapsed.shape != target.shape or elapsed[0] != 0.0:
        raise ObserverTransferError("INVALID_AFFINE_GRID")
    denominator = float(np.dot(elapsed, elapsed))
    if denominator <= 0.0:
        raise ObserverTransferError("DEGENERATE_AFFINE_GRID")
    rate = float(np.dot(elapsed, target) / denominator)
    return rate * elapsed, rate


def separation_metrics(
    left_m: Sequence[float],
    right_m: Sequence[float],
    confirmation_start: int = CONFIRMATION_START,
) -> dict[str, float]:
    left = anchored_coordinate(left_m)
    right = anchored_coordinate(right_m)
    if left.shape != right.shape or not 1 <= confirmation_start < left.size:
        raise ObserverTransferError("INVALID_CONFIRMATION_PARTITION")
    residual = (left - right)[confirmation_start:]
    return {
        "heldout_peak_to_peak_m": float(np.ptp(residual)),
        "heldout_rms_m": float(sqrt(float(np.mean(residual**2)))),
        "heldout_maximum_absolute_m": float(np.max(np.abs(residual))),
    }


def score_without_nuisance_fit(
    observed_m: Sequence[float],
    models_m: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    if not models_m:
        raise ObserverTransferError("NO_FROZEN_MODELS")
    scores = {
        name: separation_metrics(observed_m, curve)
        for name, curve in sorted(models_m.items())
    }
    ordered = sorted(
        scores.items(),
        key=lambda item: (float(item[1]["heldout_peak_to_peak_m"]), item[0]),
    )
    return {
        "best_model": ordered[0][0],
        "scores": scores,
        "nuisance_parameters_fit_from_observation": 0,
    }


def per_link_interval_term(definition: Mapping[str, object]) -> dict[str, object]:
    per_link = float(definition["per_link_path_bound_m"])
    if not np.isfinite(per_link) or per_link < 0.0:
        raise ObserverTransferError("INVALID_PER_LINK_INTERVAL")
    result = dict(definition)
    if result.get("term") == "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE":
        result.update(
            {
                "state": "REQUIRES_PREDECLARED_C_PREFIX_ADMISSION",
                "provenance": (
                    "LEARNABLE_ON_C_WITNESS_PREFIX_ONLY_NOT_TRANSFERRED_FROM_AB"
                ),
            }
        )
    result.update(
        {
            "two_link_coordinate_amplitude_bound_m": 2.0 * per_link,
            "anchor_peak_to_peak_gain": 2.0,
            "heldout_peak_to_peak_bound_m": 4.0 * per_link,
            "basis_phase_coordinate": (
                "TWO_LINK_TARGET_MINUS_REFERENCE_INTERVAL_WITH_FIXED_ANCHOR_"
                "CONSTANT_DROPPING_OUT_OF_PEAK_TO_PEAK"
            ),
        }
    )
    return result


def quantization_term() -> dict[str, object]:
    alpha, beta = inherited.ionosphere_free_coefficients()
    per_link = 0.5 * inherited.RINEX_PHASE_QUANTIZATION_CYCLES * (
        abs(alpha) * 299_792_458.0 / inherited.GPS_L1_HZ
        + abs(beta) * 299_792_458.0 / inherited.GPS_L2_HZ
    )
    return per_link_interval_term(
        {
            "term": "RINEX_CARRIER_PHASE_QUANTIZATION",
            "state": "KNOWN_FORMAT_BOUND",
            "provenance": "INDEPENDENT_OF_FUTURE_C_OBSERVATION",
            "per_link_path_bound_m": per_link,
            "basis": "HALF_RINEX_F14_3_CYCLE_QUANTIZATION_AFTER_IF_COMBINATION",
        }
    )


def combine_envelope(
    controlling_separation_m: float,
    terms: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    contributions = [float(term["heldout_peak_to_peak_bound_m"]) for term in terms]
    if (
        not np.isfinite(controlling_separation_m)
        or controlling_separation_m <= 0.0
        or not contributions
        or any(not np.isfinite(value) or value < 0.0 for value in contributions)
    ):
        raise ObserverTransferError("INVALID_PHYSICAL_ENVELOPE")
    one_model = float(sum(contributions))
    pairwise = float(inherited.PAIRWISE_ENVELOPE_MULTIPLIER * one_model)
    margin = float(controlling_separation_m - pairwise)
    return {
        "one_model_physical_envelope_m": one_model,
        "pairwise_comparison_envelope_m": pairwise,
        "remaining_physical_margin_m": margin,
        "maximum_future_one_model_measurement_envelope_m": max(0.0, margin / 2.0),
        "negative_result_interpretable_if_future_capability_admitted": margin > 0.0,
        "outcome": (
            OUTCOME_DISCRIMINATIVE if margin > 0.0 else OUTCOME_ENVELOPE_INSUFFICIENT
        ),
    }


def manifest() -> dict[str, object]:
    alpha, beta = inherited.ionosphere_free_coefficients()
    return {
        "compiler_version": COMPILER_VERSION,
        "phase": "SPIKE",
        "physical_question": (
            "CAN_A_FROZEN_ORBIT_FAMILY_PREDICT_AN_UNSEEN_OBSERVER_TARGET_"
            "MINUS_REFERENCE_PHASE_COORDINATE_WITHOUT_A_FREE_RATE"
        ),
        "new_information": (
            "WHETHER_ONE_NEW_OBSERVER_CAN_TEST_SPATIAL_TRANSFER_WITH_FEWER_"
            "MEASUREMENT_ROOTS_THAN_A_SECOND_COMPLETE_PAIR"
        ),
        "coordinate": {
            "units": "IONOSPHERE_FREE_CARRIER_DERIVED_RANGE_METERS",
            "weights": {"L1C": alpha, "L2W": beta},
            "station_satellite_order": "C_TARGET_MINUS_C_REFERENCE",
            "fixed_anchor_index": ANCHOR_INDEX,
            "anchor_role": "REMOVE_ONE_CONSTANT_INTEGER_AMBIGUITY_ONLY",
            "free_rate": False,
            "suffix_fit": False,
            "time_derivative": "NONE",
        },
        "partition": {
            "epochs": SAMPLE_COUNT,
            "cadence_s": STEP_S,
            "witness_prefix_epochs": WITNESS_PREFIX_EPOCHS,
            "confirmation_epochs": CONFIRMATION_EPOCHS,
            "witness_prefix_may_fit_or_select_orbit": False,
            "witness_prefix_may_apply_predeclared_admission_rules": True,
        },
        "receiver_clock_ledger": {
            "common_same_receiver_clock": "CANCELS_IN_SIMULTANEOUS_SATELLITE_DIFFERENCE",
            "signal_specific_hardware": "DOES_NOT_CANCEL_AND_REQUIRES_ADMISSION_BOUND",
            "satellite_clock_difference": "MODELED_INTERVAL_NOT_ZERO",
        },
        "nulls": {
            "affine": (
                "ZERO_INTERCEPT_RATE_CHOSEN_FROM_TARGET_PREDICTION_BEFORE_"
                "OBSERVATION_TO_MAXIMIZE_NULL_COMPETITIVENESS"
            ),
            "wrong_orbits": ["WRONG_ORBIT_1", "WRONG_ORBIT_2"],
            "same_anchor_grid_and_receiver_transform": True,
        },
        "synthetic_fixture": {
            "role": "MECHANISM_ONLY_NEVER_CAPABILITY_NEVER_PRIMARY",
            "observer_id": SYNTHETIC_OBSERVER_ID,
            "observer_coordinates_are_candidate_selection": False,
            "start_utc": SYNTHETIC_START.isoformat(),
            "model_family": "DETERMINISTIC_SYNTHETIC_GNSS_LIKE_SGP4_OMM",
        },
        "forbidden": [
            "real station date product locator header or observation selection",
            "free receiver rate or time phase",
            "suffix nuisance fit",
            "reuse rescore or reopen consumed GOLD NLIB observations",
            "repair or retry consumed ALGO MDO primaries",
            "measurement authorization",
            "new gate or generic framework",
        ],
    }


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def _grid() -> tuple[datetime, ...]:
    return tuple(
        SYNTHETIC_START + timedelta(seconds=index * STEP_S)
        for index in range(SAMPLE_COUNT)
    )


def compile_mechanism(primary_path: Path, repeated_path: Path) -> dict[str, object]:
    prior = validate_prior_evidence(primary_path, repeated_path)
    epochs = _grid()
    elapsed = np.arange(SAMPLE_COUNT, dtype=np.float64) * STEP_S
    state_cache: dict[tuple[str, float], tuple[np.ndarray, np.ndarray]] = {}

    def states(name: str, offset_s: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        key = name, float(offset_s)
        if key not in state_cache:
            elements: OrbitalElements = SYNTHETIC_MODELS[name]
            sampled = tuple(
                compute_orbital_state(
                    SYNTHETIC_OBSERVER,
                    elements,
                    epoch + timedelta(seconds=offset_s),
                )
                for epoch in epochs
            )
            state_cache[key] = (
                np.asarray([item.range_km * 1000.0 for item in sampled]),
                np.asarray([item.elevation_deg for item in sampled]),
            )
        return state_cache[key]

    def quotient(name: str, offset_s: float = 0.0) -> np.ndarray:
        target_range, _ = states(name, offset_s)
        reference_range, _ = states("REFERENCE_ORBIT", offset_s)
        return single_observer_quotient_m(target_range, reference_range)

    target = quotient("TARGET_ORBIT")
    wrong_1 = quotient("WRONG_ORBIT_1")
    wrong_2 = quotient("WRONG_ORBIT_2")
    affine, affine_rate = frozen_adversarial_affine_null(target, elapsed)
    models = {
        "TARGET_ORBIT": target,
        "FROZEN_AFFINE_NULL": affine,
        "WRONG_ORBIT_1": wrong_1,
        "WRONG_ORBIT_2": wrong_2,
    }
    null_scores = {
        name: separation_metrics(target, curve)
        for name, curve in models.items()
        if name != "TARGET_ORBIT"
    }
    controlling_name, controlling_score = min(
        null_scores.items(),
        key=lambda item: (float(item[1]["heldout_peak_to_peak_m"]), item[0]),
    )
    controlling = float(controlling_score["heldout_peak_to_peak_m"])

    target_anchored = anchored_coordinate(target)
    timing_candidates = []
    for offset in (-MAXIMUM_EVENT_TIME_ERROR_S, MAXIMUM_EVENT_TIME_ERROR_S):
        delta = anchored_coordinate(quotient("TARGET_ORBIT", offset)) - target_anchored
        timing_candidates.append(
            (float(np.ptp(delta[CONFIRMATION_START:])), float(offset))
        )
    timing_bound, timing_offset = max(timing_candidates)
    timing = {
        "term": "STATION_C_EVENT_TIME",
        "state": "MODELED_DIRECT_TRAJECTORY_ENVELOPE",
        "provenance": "STRUCTURAL_HALF_CADENCE_BOUND",
        "parameter_interval_s": [
            -MAXIMUM_EVENT_TIME_ERROR_S,
            MAXIMUM_EVENT_TIME_ERROR_S,
        ],
        "controlling_offset_s": timing_offset,
        "heldout_peak_to_peak_bound_m": timing_bound,
        "basis": "COMMON_C_TIMESTAMP_SHIFT_APPLIED_DIRECTLY_TO_BOTH_TRAJECTORIES",
    }

    _, target_elevation = states("TARGET_ORBIT")
    _, reference_elevation = states("REFERENCE_ORBIT")
    mapping_shape = (
        1.0
        / np.maximum(
            np.sin(np.radians(target_elevation)),
            sin(np.radians(MINIMUM_ELEVATION_DEG)),
        )
        - 1.0
        / np.maximum(
            np.sin(np.radians(reference_elevation)),
            sin(np.radians(MINIMUM_ELEVATION_DEG)),
        )
    )
    troposphere_curve = anchored_coordinate(
        inherited.MAX_ZENITH_TROPOSPHERE_M * mapping_shape
    )
    troposphere = {
        "term": "STATION_C_DIFFERENTIAL_TROPOSPHERE",
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_FUTURE_C_OBSERVATION",
        "zenith_delay_interval_m": [0.0, inherited.MAX_ZENITH_TROPOSPHERE_M],
        "heldout_peak_to_peak_bound_m": float(
            np.ptp(troposphere_curve[CONFIRMATION_START:])
        ),
        "basis": "CONSERVATIVE_ONE_OVER_SINE_TARGET_MINUS_REFERENCE_MAPPING",
    }

    terms = [timing, troposphere, quantization_term()]
    terms.extend(per_link_interval_term(item) for item in inherited.GENERIC_PATH_BOUNDS_M)
    decision = combine_envelope(controlling, terms)
    for term in terms:
        term["pairwise_contribution_m"] = float(
            inherited.PAIRWISE_ENVELOPE_MULTIPLIER
            * float(term["heldout_peak_to_peak_bound_m"])
        )
    terms.sort(
        key=lambda item: (-float(item["pairwise_contribution_m"]), str(item["term"]))
    )

    common_receiver_clock = 50.0 + 0.02 * elapsed + 3.0 * np.sin(elapsed / 400.0)
    clocked = single_observer_quotient_m(
        states("TARGET_ORBIT")[0] + common_receiver_clock,
        states("REFERENCE_ORBIT")[0] + common_receiver_clock,
    )
    receiver_clock_error = float(np.max(np.abs(clocked - target)))

    mismatch_score = score_without_nuisance_fit(wrong_1, models)
    mismatch = {
        "truth_family": "WRONG_ORBIT_1",
        "generated_from_nominal_target": False,
        "same_fixed_anchor_and_zero_observation_fit": True,
        "best_model": mismatch_score["best_model"],
        "target_residual": mismatch_score["scores"]["TARGET_ORBIT"],
        "truth_residual": mismatch_score["scores"]["WRONG_ORBIT_1"],
        "target_not_automatically_preferred": (
            mismatch_score["best_model"] == "WRONG_ORBIT_1"
        ),
    }

    minimum_elevation = float(
        min(
            np.min(states(name)[1])
            for name in (
                "TARGET_ORBIT",
                "REFERENCE_ORBIT",
                "WRONG_ORBIT_1",
                "WRONG_ORBIT_2",
            )
        )
    )
    if minimum_elevation < MINIMUM_ELEVATION_DEG:
        raise ObserverTransferError("SYNTHETIC_JOINT_VISIBILITY_CHANGED")
    if receiver_clock_error > 1e-6:
        raise ObserverTransferError("COMMON_RECEIVER_CLOCK_DID_NOT_CANCEL")
    if not mismatch["target_not_automatically_preferred"]:
        raise ObserverTransferError("TARGET_MODEL_PREFERRED_SYNTHETIC_MISMATCH")

    outcome = str(decision["outcome"])
    if manifest()["coordinate"]["free_rate"] is not False:
        outcome = OUTCOME_FORBIDDEN_NUISANCE
    result = {
        "schema": "gnss-observer-transfer-spike-receipt-v1",
        "compiler_version": COMPILER_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "manifest_sha256": manifest_sha256(),
        "prior_evidence": prior,
        "fixture_role": "SYNTHETIC_MECHANISM_ONLY_NEVER_CAPABILITY_NEVER_PRIMARY",
        "synthetic_geometry": {
            "observer_id": SYNTHETIC_OBSERVER_ID,
            "observer_coordinates_are_candidate_selection": False,
            "start_utc": SYNTHETIC_START.isoformat(),
            "stop_utc": epochs[-1].isoformat(),
            "minimum_all_model_elevation_deg": minimum_elevation,
            "minimum_required_elevation_deg": MINIMUM_ELEVATION_DEG,
            "model_elements": SYNTHETIC_MODELS,
        },
        "coordinate": manifest()["coordinate"],
        "partition": manifest()["partition"],
        "receiver_clock_cancellation": {
            "maximum_absolute_numerical_error_m": receiver_clock_error,
            "common_clock_curve_contains_constant_rate_and_non_affine_terms": True,
            "signal_specific_hardware_cancels": False,
        },
        "null_scores": {
            **null_scores,
            "frozen_affine_rate_m_s": affine_rate,
            "affine_rate_source": "TARGET_PREDICTION_ONLY_BEFORE_OBSERVATION",
            "controlling_null": controlling_name,
            "controlling_heldout_separation_m": controlling,
        },
        "physical_terms": terms,
        "synthetic_model_mismatch": mismatch,
        **decision,
        "outcome": outcome,
        "interpretation": (
            "ONE_ANCHOR_OBSERVER_TRANSFER_RETAINS_POSITIVE_SYNTHETIC_MARGIN_"
            "FUTURE_CANDIDATE_AND_CAPABILITY_STILL_REQUIRED"
            if outcome == OUTCOME_DISCRIMINATIVE
            else "OBSERVER_TRANSFER_NOT_READY_FOR_CANDIDATE_SELECTION"
        ),
        "observation_access": {
            "real_stations_selected": 0,
            "products_discovered": 0,
            "products_selected": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
        },
        "future_capability_selected": False,
        "prospective_plan_frozen": False,
        "measurement_authorized": False,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    if path.exists():
        raise ObserverTransferError("SPIKE_RECEIPT_ALREADY_EXISTS")
    path.write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--primary-outcome",
        type=Path,
        default=root / PRIMARY_OUTCOME_NAME,
    )
    parser.add_argument(
        "--repeated-outcome",
        type=Path,
        default=root / REPEATED_OUTCOME_NAME,
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = compile_mechanism(args.primary_outcome, args.repeated_outcome)
    if args.output is None:
        print(strict_json(result))
    else:
        _write_json(args.output, result)


if __name__ == "__main__":
    main()
