"""Compile the final pre-ranked DRAO DOY234 prospective proof.

This one-use, observation-free compiler consumes only the exact broadcast NAV
already recorded by the original shortlist.  It recomputes the physical
envelope and freezes labelled model curves, nulls, transforms and decision
semantics before any DOY234 observation artifact is selected.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from math import isfinite
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_geometry_screen as screen,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_physical_envelope as physical,
)
from experiments.orbital_discriminability import gnss_double_difference_screen as geometry


VERSION: Final = "gnss-drao-labelled-forward-doy234-plan-v1"
PARENT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_GEOMETRY_SCREEN.json"
PARENT_SHA256: Final = "06161af57ada12e081faef7cf470e540ea5fff5dd7cf2f6614077b738852ed62"
DOY238_AUDIT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY238_OUTCOME_AUDIT.json"
DOY238_AUDIT_SHA256: Final = "efe0148bf94b5c00faca3e8576bf5966a12be62a73ef52931c5b0483552cf321"
ENVELOPE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_PHYSICAL_ENVELOPE.json"
BUNDLE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_PREDICTION_BUNDLE.json"
PLAN_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_INTEGRATED_PLAN.json"
REPORT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY234_INTEGRATED_PLAN.md"

RANK: Final = 3
DOY: Final = 234
GPS_DATE: Final = "2026-08-22"
STATION: Final = "DRAO00CAN"
DOMES: Final = "40105M002"
CODEBOOK: Final = ("G14", "G15", "G17", "G20", "G24", "G30")
GPS_START: Final = datetime(2026, 8, 22, 5, 5, 0, tzinfo=timezone.utc)
GPS_STOP: Final = datetime(2026, 8, 22, 6, 14, 0, tzinfo=timezone.utc)
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
EXPECTED_SCREEN_SEPARATION_M: Final = 36_208.70448109973
EXPECTED_SCREEN_TIMING_ENVELOPE_M: Final = 1_385.863580465115
EXPECTED_SCREEN_MINIMUM_ELEVATION_DEG: Final = 15.226519684082586

NAVIGATION_NAME: Final = "brdc2340.26n.gz"
NAVIGATION_BYTES: Final = 70_000
NAVIGATION_SHA256: Final = "bcb196bf8a2e44ad587a1af2bcd118df9d39c5ada4c81a291f3b85d58d6e84bd"
NAVIGATION_RAW_SHA256: Final = "afdf5ca23e33de17b6d056ca649b080e9d06841f541fa78afb5ec4640e0f1336"


class Doy234PlanError(ValueError):
    """A frozen authority, exact model input or invariant changed."""


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


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise Doy234PlanError(f"NOT_A_JSON_OBJECT:{Path(path).name}")
    return value


def _close(actual: float, expected: float, name: str) -> None:
    if not isfinite(actual) or abs(actual - expected) > 1.0e-9:
        raise Doy234PlanError(f"{name}_CHANGED")


def validate_authority(root: Path) -> dict[str, object]:
    root = Path(root)
    if canonical_sha256(root / PARENT_NAME) != PARENT_SHA256:
        raise Doy234PlanError("FROZEN_SHORTLIST_CHANGED")
    if canonical_sha256(root / DOY238_AUDIT_NAME) != DOY238_AUDIT_SHA256:
        raise Doy234PlanError("DOY238_CLOSING_AUDIT_CHANGED")
    parent = _read_json(root / PARENT_NAME)
    audit = _read_json(root / DOY238_AUDIT_NAME)
    shortlist = parent.get("shortlist")
    if parent.get("outcome") != screen.OUTCOME_SELECTED:
        raise Doy234PlanError("SHORTLIST_OUTCOME_CHANGED")
    if not isinstance(shortlist, list) or len(shortlist) != 3:
        raise Doy234PlanError("FROZEN_SHORTLIST_SIZE_CHANGED")
    selected = shortlist[RANK - 1]
    expected = {
        "doy": DOY,
        "gps_date": GPS_DATE,
        "raw_start_gps": "2026-08-22T05:05:00 GPS",
        "raw_stop_gps": "2026-08-22T06:14:00 GPS",
        "heldout_start_gps": "2026-08-22T05:44:30 GPS",
        "candidate_codebook": list(CODEBOOK),
        "controlling_null": "TIME_REVERSED_GEOMETRY",
    }
    for key, expected_value in expected.items():
        if selected.get(key) != expected_value:
            raise Doy234PlanError(f"RANK3_{key.upper()}_CHANGED")
    _close(
        float(selected["exact_controlling_separation_m"]),
        EXPECTED_SCREEN_SEPARATION_M,
        "SCREEN_SEPARATION",
    )
    _close(
        float(selected["direct_time_shift_envelope_m"]),
        EXPECTED_SCREEN_TIMING_ENVELOPE_M,
        "SCREEN_TIMING",
    )
    _close(
        float(selected["minimum_time_shifted_elevation_deg"]),
        EXPECTED_SCREEN_MINIMUM_ELEVATION_DEG,
        "SCREEN_ELEVATION",
    )
    if audit.get("state") != "DRAO_DOY238_CLOSED_DESCRIPTION_ERROR":
        raise Doy234PlanError("DOY238_NOT_CLOSED")
    return {
        PARENT_NAME: PARENT_SHA256,
        DOY238_AUDIT_NAME: DOY238_AUDIT_SHA256,
        "selection_rule": "ONLY_REMAINING_UNCONSUMED_MEMBER_OF_PRE_OBSERVATION_SHORTLIST",
        "doy237_reopened": False,
        "doy238_reopened": False,
    }


def manifest(root: Path) -> dict[str, object]:
    value = {
        "schema": f"{VERSION}-manifest",
        "authority": validate_authority(root),
        "physical_question": (
            "DO_THE_SIX_PREDECLARED_DOY234_RECEIVER_LABELLED_PATHS_PREDICT_"
            "THE_HELDOUT_SUFFIX_BETTER_THAN_AFFINE_AND_TIME_REVERSED_NULLS"
        ),
        "new_information": "ONE_INDEPENDENT_REAL_FORWARD_ORBITAL_VERSUS_NULL_EVENT",
        "geometry": {
            "station": STATION,
            "doy": DOY,
            "gps_date": GPS_DATE,
            "codebook": list(CODEBOOK),
            "start_gps": "2026-08-22T05:05:00 GPS",
            "stop_gps": "2026-08-22T06:14:00 GPS",
            "heldout_start_gps": "2026-08-22T05:44:30 GPS",
        },
        "navigation": {
            "name": NAVIGATION_NAME,
            "bytes": NAVIGATION_BYTES,
            "sha256": NAVIGATION_SHA256,
            "raw_sha256": NAVIGATION_RAW_SHA256,
            "role": "TRANSIENT_MODEL_ONLY",
        },
        "observation_access_at_freeze": 0,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def _navigation_candidate():
    matches = tuple(row for row in screen.NAVIGATION_CANDIDATES if row.doy == DOY)
    if len(matches) != 1 or matches[0].name != NAVIGATION_NAME:
        raise Doy234PlanError("NAVIGATION_CANDIDATE_CHANGED")
    return matches[0]


def parse_navigation(payload: bytes | bytearray):
    compressed = bytes(payload)
    if len(compressed) != NAVIGATION_BYTES:
        raise Doy234PlanError("NAVIGATION_COMPRESSED_BYTES_CHANGED")
    if sha256(compressed).hexdigest() != NAVIGATION_SHA256:
        raise Doy234PlanError("NAVIGATION_COMPRESSED_HASH_CHANGED")
    records, receipt = screen.parse_navigation_gzip(_navigation_candidate(), compressed)
    if receipt.get("uncompressed_sha256") != NAVIGATION_RAW_SHA256:
        raise Doy234PlanError("NAVIGATION_RAW_HASH_CHANGED")
    missing = sorted(set(CODEBOOK) - set(records))
    if missing:
        raise Doy234PlanError(f"CODEBOOK_EPHEMERIS_MISSING:{','.join(missing)}")
    return records, receipt


def expected_utc_epochs() -> tuple[datetime, ...]:
    start = GPS_START - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    stop = GPS_STOP - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    epochs = tuple(start + timedelta(seconds=index * STEP_S) for index in range(RAW_EPOCHS))
    if epochs[-1] != stop:
        raise Doy234PlanError("FROZEN_GRID_CHANGED")
    return epochs


def _finite_curve(values: Sequence[object], satellite: str) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != RAW_EPOCHS or not all(isfinite(value) for value in result):
        raise Doy234PlanError(f"PREDICTION_CURVE_INVALID:{satellite}")
    return result


def compile_proof(payload: bytes | bytearray, root: Path) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    authority = validate_authority(root)
    records, navigation = parse_navigation(payload)
    epochs = expected_utc_epochs()
    station = physical._station()
    station_ecef = geometry.station_to_ecef(station)
    retarded: dict[float, np.ndarray] = {}
    transmit: dict[tuple[str, float], tuple[datetime, ...]] = {}
    positions: dict[tuple[str, float], np.ndarray] = {}
    for offset in (0.0, *physical.TIMING_OFFSETS_S):
        rows = []
        for satellite in CODEBOOK:
            ranges, times, receive_frame = physical._retarded_series(
                records[satellite], epochs, station_ecef, offset
            )
            rows.append(ranges)
            transmit[(satellite, offset)] = times
            positions[(satellite, offset)] = receive_frame
        retarded[offset] = np.stack(rows)
    shifted = {
        (satellite, offset): retarded[offset][index]
        for offset in physical.TIMING_OFFSETS_S
        for index, satellite in enumerate(CODEBOOK)
    }
    comparison = screen.evaluate_codebook(
        {satellite: retarded[0.0][index] for index, satellite in enumerate(CODEBOOK)},
        shifted,
    )
    clock_paths = np.stack(
        [
            np.asarray(
                [
                    -geometry.SPEED_OF_LIGHT_M_S
                    * physical._clock_bias_s(
                        geometry.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in transmit[(satellite, 0.0)]
                ],
                dtype=np.float64,
            )
            for satellite in CODEBOOK
        ]
    )
    _, clock_metrics = physical._projected_metrics(physical._center(clock_paths))
    accuracy = {
        satellite: max(
            float(geometry.select_ephemeris(records[satellite], epoch).sv_accuracy_m)
            for epoch in epochs
        )
        for satellite in CODEBOOK
    }
    elevation = {
        offset: np.stack(
            [
                geometry.elevation_deg(positions[(satellite, offset)], station, station_ecef)
                for satellite in CODEBOOK
            ]
        )
        for offset in (0.0, *physical.TIMING_OFFSETS_S)
    }
    robust_elevation = np.min(np.stack(tuple(elevation.values())), axis=0)
    if np.any(robust_elevation <= 0.0) or not np.all(np.isfinite(robust_elevation)):
        raise Doy234PlanError("RETARDED_ELEVATION_INVALID")
    slant_upper = physical.ZENITH_DELAY_MAX_M / np.sin(np.radians(robust_elevation))
    tropo_bound, tropo_by_satellite = physical.transformed_box_peak_to_peak_bound(
        slant_upper
    )
    terms = [
        physical._term("EVENT_TIME_DIRECT_RETARDED_TRAJECTORY_ENVELOPE", float(comparison["direct_time_shift_envelope_m"]), "MODELED_DIRECT_TRAJECTORY_ENVELOPE", "T_PLUS_MINUS_15_S_ON_EACH_RETARDED_TRAJECTORY"),
        physical._term("BROADCAST_ORBIT_USER_RANGE_ACCURACY_FAMILY", 8.0 * max(accuracy.values()), "MODELED_CONSERVATIVE_INTERVAL", "EIGHT_TIMES_MAXIMUM_SELECTED_EPHEMERIS_SV_ACCURACY"),
        physical._term("OMITTED_BROADCAST_SATELLITE_CLOCK_NONAFFINITY", float(clock_metrics["heldout_max_track_peak_to_peak_m"]), "MODELED_FROM_BROADCAST_CLOCK_FIELDS", "AF0_AF1_AF2_AND_ECCENTRICITY_RELATIVITY"),
        physical._term("DIFFERENTIAL_TROPOSPHERE_RELAXED_BOX", tropo_bound, "MODELED_CONSERVATIVE_INTERVAL", "ZERO_TO_3_5_M_OVER_SIN_ELEVATION_BOX"),
        physical._term("STATION_DISPLACEMENT_EOP_AND_RELATIVITY", physical.STATION_EOP_RELATIVITY_BOUND_M, "MODELED_CONSERVATIVE_INTERVAL", "FROZEN_DRAO_COMMON_MODE_HELDOUT_INTERVAL"),
    ]
    model_side = sum(float(row["heldout_max_track_peak_to_peak_bound_m"]) for row in terms)
    one_model = model_side + physical.CAPABILITY_CONDITIONAL_RESERVE_M
    required = physical.DECISION_MULTIPLIER * one_model
    exact = float(comparison["exact_controlling_separation_m"])
    margin = exact - required
    outcome = (
        "DRAO_DOY234_PHYSICAL_MARGIN_ADMITTED"
        if margin > 0.0
        else "DRAO_DOY234_PHYSICAL_ENVELOPE_DOMINATES"
    )
    envelope = {
        "schema": "gnss-drao-labelled-forward-doy234-physical-envelope-v1",
        "outcome": outcome,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": {"python": platform.python_version(), "numpy": importlib.metadata.version("numpy")},
        "authority": authority,
        "navigation": navigation,
        "geometry": {
            "station": STATION,
            "doy": DOY,
            "gps_date": GPS_DATE,
            "codebook": list(CODEBOOK),
            "minimum_time_shifted_elevation_deg": float(np.min(robust_elevation)),
            "controlling_null": comparison["controlling_null"],
            "controlling_separation_m": exact,
        },
        "model_side_terms": terms,
        "event_time_metrics": comparison["direct_time_shift_rows"],
        "broadcast_sv_accuracy_m_by_satellite": accuracy,
        "satellite_clock_metrics": clock_metrics,
        "troposphere": {"heldout_box_bound_m_by_satellite": tropo_by_satellite, "heldout_max_track_peak_to_peak_bound_m": tropo_bound},
        "envelope": {
            "model_side_m": model_side,
            "conditional_measurement_reserve_m": physical.CAPABILITY_CONDITIONAL_RESERVE_M,
            "one_model_bound_b_m": one_model,
            "required_separation_3b_m": required,
            "controlling_separation_m": exact,
            "remaining_physical_margin_m": margin,
        },
        "observation_access": {"locators": 0, "headers": 0, "payload_bytes": 0, "values": 0, "scores": 0},
        "navigation_payloads_retained": 0,
    }
    bundle = {
        "schema": "gnss-drao-labelled-forward-doy234-prediction-bundle-v1",
        "role": "FROZEN_MODEL_ONLY_NOT_AVAILABLE_TO_MEASUREMENT_ADMISSION",
        "coordinate": "RETARDED_EARTH_ROTATION_CORRECTED_GEOMETRIC_RANGE_M",
        "grid": {"start_gps": "2026-08-22T05:05:00 GPS", "stop_gps": "2026-08-22T06:14:00 GPS", "heldout_start_gps": "2026-08-22T05:44:30 GPS", "step_s": STEP_S, "raw_epochs": RAW_EPOCHS, "prefix_epochs": PREFIX_EPOCHS, "heldout_epochs": HELDOUT_EPOCHS},
        "labelled_model_curves_m": {satellite: _finite_curve(retarded[0.0][index], satellite) for index, satellite in enumerate(CODEBOOK)},
        "null_construction": {"PREFIX_AFFINE_ONLY": "ZERO_MODEL_THEN_IDENTICAL_PREFIX_CONSTANT_RATE_PROJECTION", "TIME_REVERSED_GEOMETRY": "REVERSE_EACH_NOMINAL_CURVE_ON_FIXED_GRID"},
        "navigation": {"name": navigation["name"], "compressed_sha256": navigation["compressed_sha256"], "uncompressed_sha256": navigation["uncompressed_sha256"]},
        "observation_values": 0,
    }
    plan = {
        "schema": VERSION,
        "state": (
            "DRAO_DOY234_INTEGRATED_PLAN_FROZEN_ARTIFACT_UNSELECTED"
            if outcome == "DRAO_DOY234_PHYSICAL_MARGIN_ADMITTED"
            else "DRAO_DOY234_PLAN_BLOCKED_BY_PHYSICAL_ENVELOPE"
        ),
        "physical_question": manifest(root)["physical_question"],
        "new_physical_information": manifest(root)["new_information"],
        "candidate": {"station": STATION, "domes": DOMES, "doy": DOY, "codebook": list(CODEBOOK), "artifact_name": None, "locator": None, "artifact_sha256": None, "artifact_selected": False, "observation_access_authorized": False},
        "prediction": {"bundle": BUNDLE_NAME, "bundle_sha256": sha256(strict_json(bundle).encode("ascii")).hexdigest(), "available_before_admission": False},
        "detectability": envelope["envelope"],
        "transform_policy": {
            "REFERENCE_SIGNAL_BLANK_CORRECTION": "VALID_NO_NUMERIC_CORRECTION_APPLIED_AGAIN",
            "EXPLICIT_NUMERIC_CORRECTION": "VALIDATED_STORED_PHASE_ALREADY_INCLUDES_CORRECTION",
            "SYSTEM_ALIGNMENT_UNKNOWN_BLANK_RECORD": "PRIMARY_NOT_EVALUATED",
            "MALFORMED_CONFLICT_OR_INCOMPLETE": "PRIMARY_NOT_EVALUATED",
            "scale_factor": "DIVIDE_STORED_VALUE_BY_EXPLICIT_FACTOR_OR_UNITY",
            "receiver_clock": "APPLY_EVENT_AND_MEASUREMENT_CORRECTION_EXACTLY_ONCE_IF_FLAG_ZERO",
        },
        "admission": {"required_prns": list(CODEBOOK), "required_fields": ["L1C", "L2W", "C1C", "C2W"], "required_normal_epochs": RAW_EPOCHS, "lli": "ZERO_OR_BLANK", "geometry_free_second_difference_limit_m": 0.09514683639918244, "phase_minus_code_heldout_peak_to_peak_limit_m": 1250.0, "extra_tracks": "DESCRIPTIVE_NOT_SCORED"},
        "decision": {"families": ["ORBITAL", "PREFIX_AFFINE_ONLY", "TIME_REVERSED_GEOMETRY"], "score": "MAX_TRACK_HELDOUT_PEAK_TO_PEAK_M", "nuisance": "PER_TRACK_PREFIX_ONLY_CONSTANT_RATE", "guard_b_m": one_model, "preference": "STRICTLY_MORE_THAN_B", "orbital_positive_requires_score_at_most_b": True, "heldout_refit": False, "free_time_phase": False},
        "retry": {"before_complete_hash": ["TIMEOUT", "TRANSPORT_INTERRUPTION"], "after_complete_hash": 0, "fallback": False},
        "claim_scope": {"maximum_positive": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED", "specific_identity": "MODEL_CONDITIONED_NOT_INDEPENDENT", "distributed_multi_root": False},
        "outcomes": ["PRIMARY_ARTIFACT_MATERIALIZATION_FAILED", "PRIMARY_NOT_EVALUATED", "MEASUREMENT_INVALID", "NOT_DETECTABLE", "ORBITAL_MODEL_PREDICTIVELY_PREFERRED", "ORBITAL_PREDICTION_REJECTED", "PREFIX_AFFINE_NULL_PREFERRED", "TIME_REVERSED_GEOMETRY_NULL_PREFERRED", "AMBIGUOUS"],
        "frozen_inputs": authority,
        "observation_access_at_freeze": 0,
        "new_gate": False,
        "generic_framework": False,
    }
    for value in (envelope, bundle, plan):
        strict_json(value)
    for array in (*retarded.values(), clock_paths, robust_elevation, slant_upper):
        array.fill(0.0)
    for array in positions.values():
        array.fill(0.0)
    return envelope, bundle, plan


def render_report(envelope: Mapping[str, object], plan: Mapping[str, object]) -> str:
    bounds = envelope["envelope"]
    return f"""# DRAO labelled-forward DOY234 integrated plan

**{plan['state']}**

DOY234 was rank 3 in the original observation-free shortlist and is its only
unconsumed member. The exact-hash broadcast NAV preserves a controlling
separation of `{bounds['controlling_separation_m']:.6f} m` against
`3B = {bounds['required_separation_3b_m']:.6f} m`, leaving
`{bounds['remaining_physical_margin_m']:.6f} m`.

The frozen window is 2026-08-22 05:05:00--06:14:00 GPS, with prefix indices
0--78 and held-out indices 79--138 for G14/G15/G17/G20/G24/G30.

The transform policy now distinguishes a valid reference-signal record whose
numeric phase correction is blank from an entirely blank system-level record
whose alignment is unknown. Explicit numeric corrections are validated but
never applied twice. All thresholds, nulls and decision semantics remain
pre-observation.

No DOY234 observation artifact has been queried or selected.
"""


def _write_once(path: Path, content: str) -> None:
    if path.exists():
        raise Doy234PlanError(f"REFUSE_OVERWRITE:{path.name}")
    path.write_text(content, encoding="ascii", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("navigation_gzip", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if args.navigation_gzip.name != NAVIGATION_NAME:
        raise SystemExit("SUPPLY_EXACT_FROZEN_DOY234_NAVIGATION_PRODUCT")
    envelope, bundle, plan = compile_proof(args.navigation_gzip.read_bytes(), args.output_dir)
    _write_once(args.output_dir / ENVELOPE_NAME, strict_json(envelope, pretty=True) + "\n")
    _write_once(args.output_dir / BUNDLE_NAME, strict_json(bundle, pretty=True) + "\n")
    _write_once(args.output_dir / PLAN_NAME, strict_json(plan, pretty=True) + "\n")
    _write_once(args.output_dir / REPORT_NAME, render_report(envelope, plan))
    print(plan["state"])


if __name__ == "__main__":
    main()
