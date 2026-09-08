"""Freeze one labelled-forward DRAO DOY238 plan and prediction bundle.

The compiler accepts only the exact broadcast-navigation model input already
admitted by the rank-2 physical envelope. It has no receiver artifact locator,
observation decoder or measurement scoring entry point.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_rank2_physical_envelope as envelope,
)
from experiments.orbital_discriminability import gnss_double_difference_screen as geometry


VERSION: Final = "gnss-drao-labelled-forward-doy238-integrated-plan-v1"
PLAN_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY238_INTEGRATED_PLAN.json"
REPORT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY238_INTEGRATED_PLAN.md"
BUNDLE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_DOY238_PREDICTION_BUNDLE.json"

ENVELOPE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_ENVELOPE.json"
ENVELOPE_SHA256: Final = "211542ab506e109e91aba754ad93ff32acab451e74d14ab1d4e42d5a9f36beb1"
REVIEW_NAME: Final = "POST_DRAO_LABELLED_FORWARD_STRUCTURAL_CHANGE_OF_ABSTRACTION.json"
REVIEW_SHA256: Final = "f0b80a51cea4b1d98c69d797dda2a3d4a8cc0281b72dc6bb281c425e76473dbe"

STATION: Final = "DRAO00CAN"
DOMES: Final = "40105M002"
DOY: Final = 238
CODEBOOK: Final = envelope.CODEBOOK
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
ONE_MODEL_BOUND_M: Final = 3_971.647488808212
DECISION_GUARD_M: Final = ONE_MODEL_BOUND_M
GEOMETRY_SEPARATION_M: Final = 36_418.37342430651
REQUIRED_3B_M: Final = 11_914.942466424636
REMAINING_MARGIN_M: Final = 24_503.430957881876


class IntegratedPlanError(ValueError):
    """Frozen input or generated prospective artifact is invalid."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def file_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def object_sha256(value: object) -> str:
    return sha256(strict_json(value).encode("ascii")).hexdigest()


def source_sha256() -> str:
    return sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def _read_exact(root: Path, name: str, digest: str) -> dict[str, object]:
    path = Path(root) / name
    if not path.is_file() or file_sha256(path) != digest:
        raise IntegratedPlanError(f"FROZEN_INPUT_CHANGED:{name}")
    value = json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise IntegratedPlanError(f"FROZEN_INPUT_NOT_OBJECT:{name}")
    return value


def validate_authority(root: Path) -> dict[str, object]:
    physical = _read_exact(root, ENVELOPE_NAME, ENVELOPE_SHA256)
    review = _read_exact(root, REVIEW_NAME, REVIEW_SHA256)
    if physical.get("outcome") != envelope.OUTCOME_ADMITTED:
        raise IntegratedPlanError("PHYSICAL_MARGIN_NOT_ADMITTED")
    if review.get("outcome") != "DRAO_CORE_STRUCTURE_PROVEN_TRANSFORM_RECEIPT_UNRESOLVED":
        raise IntegratedPlanError("CHANGE_OF_ABSTRACTION_NOT_FROZEN")
    if any(int(value) != 0 for value in physical["observation_access"].values()):
        raise IntegratedPlanError("PHYSICAL_ENVELOPE_USED_OBSERVATION")
    if physical.get("primary_selected") is not False:
        raise IntegratedPlanError("PHYSICAL_ENVELOPE_SELECTED_PRIMARY")
    return {
        ENVELOPE_NAME: ENVELOPE_SHA256,
        REVIEW_NAME: REVIEW_SHA256,
        "rank2_envelope_source_commit": physical["source_commit"],
        "doy237_disposition": review["artifact_disposition"]["role"],
    }


def _finite_curve(values: Sequence[object], satellite: str) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != RAW_EPOCHS or not all(isfinite(value) for value in result):
        raise IntegratedPlanError(f"PREDICTION_CURVE_INVALID:{satellite}")
    return result


def build_prediction_bundle(
    navigation_payload: bytes | bytearray, root: Path
) -> dict[str, object]:
    validate_authority(root)
    records, navigation = envelope.parse_navigation(navigation_payload)
    epochs = envelope.expected_utc_epochs()
    station = envelope.rank1._station()
    station_ecef = geometry.station_to_ecef(station)
    curves: dict[str, list[float]] = {}
    for satellite in CODEBOOK:
        ranges, _, positions = envelope.rank1._retarded_series(
            records[satellite], epochs, station_ecef, 0.0
        )
        curves[satellite] = _finite_curve(ranges, satellite)
        ranges.fill(0.0)
        positions.fill(0.0)
    bundle = {
        "schema": "gnss-drao-labelled-forward-doy238-prediction-bundle-v1",
        "role": "FROZEN_MODEL_ONLY_NOT_AVAILABLE_TO_MEASUREMENT_ADMISSION",
        "coordinate": "RETARDED_EARTH_ROTATION_CORRECTED_GEOMETRIC_RANGE_M",
        "grid": {
            "start_gps": "2026-08-26T04:50:00 GPS",
            "stop_gps": "2026-08-26T05:59:00 GPS",
            "heldout_start_gps": "2026-08-26T05:29:30 GPS",
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
        },
        "labelled_model_curves_m": dict(sorted(curves.items())),
        "null_construction": {
            "PREFIX_AFFINE_ONLY": "ZERO_MODEL_THEN_SAME_PREFIX_CONSTANT_AND_RATE_PROJECTION",
            "TIME_REVERSED_GEOMETRY": "REVERSE_EACH_NOMINAL_CURVE_ON_THE_FIXED_139_EPOCH_GRID",
        },
        "navigation": {
            "name": navigation["name"],
            "compressed_sha256": navigation["compressed_sha256"],
            "uncompressed_sha256": navigation["uncompressed_sha256"],
        },
        "identity_scope": {
            "labels_are_receiver_and_model_conditioned": True,
            "specific_satellite_identity_independently_established": False,
        },
        "observation_values": 0,
    }
    strict_json(bundle)
    return bundle


def build_plan(bundle: Mapping[str, object], root: Path) -> dict[str, object]:
    authority = validate_authority(root)
    if set(bundle.get("labelled_model_curves_m", {})) != set(CODEBOOK):
        raise IntegratedPlanError("PREDICTION_CODEBOOK_CHANGED")
    plan = {
        "schema": VERSION,
        "state": "DRAO_DOY238_INTEGRATED_PLAN_FROZEN_ARTIFACT_UNSELECTED",
        "new_gate": False,
        "generic_framework": False,
        "physical_question": "DO_SIX_PREDECLARED_RECEIVER_LABELLED_DRAO_PHASE_PATHS_PREDICT_THE_HELDOUT_SUFFIX_BETTER_THAN_A_PREFIX_AFFINE_NULL_AND_TIME_REVERSED_GEOMETRY",
        "new_physical_information": "ONE_REAL_MODEL_CONDITIONED_FORWARD_ORBITAL_VERSUS_NULL_RESULT_FROM_AN_UNTOUCHED_OBSERVATION_ARTIFACT",
        "minimum_experiment": "ONE_EXACT_DOY238_DRAO_ARTIFACT_ONE_LOCAL_ADMISSION_SEQUENCE_ONE_HELDOUT_SCORE_OR_ONE_TYPED_PRE_SCORE_STOP",
        "candidate": {
            "station": STATION,
            "domes": DOMES,
            "gps_doy": DOY,
            "window": bundle["grid"],
            "orbit_codebook": list(CODEBOOK),
            "logical_product": "DRAO_DOY238_DAILY_30S_MIXED_GPS_OBSERVATION",
            "artifact_name": None,
            "locator": None,
            "artifact_sha256": None,
            "artifact_selected": False,
            "observation_access_authorized": False,
        },
        "prediction": {
            "bundle": BUNDLE_NAME,
            "bundle_sha256": object_sha256(bundle),
            "coordinate": bundle["coordinate"],
            "available_to_identity_topology_transform_or_witness_admission": False,
            "available_only_after_all_pre_score_clauses_pass": True,
        },
        "detectability": {
            "controlling_null": "TIME_REVERSED_GEOMETRY",
            "controlling_separation_m": GEOMETRY_SEPARATION_M,
            "one_model_bound_b_m": ONE_MODEL_BOUND_M,
            "required_separation_3b_m": REQUIRED_3B_M,
            "remaining_physical_margin_m": REMAINING_MARGIN_M,
            "numbers_may_change_after_artifact_selection": False,
        },
        "pre_score_clauses": {
            "identity": {
                "roots": [
                    "FROZEN_ARCHIVE_PRODUCT_AND_SITE_ID_DRAO00CAN",
                    "MARKER_NUMBER_DOMES_40105M002",
                    "SEPT_POLARX5_5_2_0",
                    "TWIVC6050_SCIS",
                    "FROZEN_GPS_WINDOW",
                ],
                "marker_name": "RETAIN_ACTUAL_VALUE_AS_DESCRIPTIVE_NOT_FATAL_BY_LITERAL_ALIAS",
                "conflict_or_incomplete": "PRIMARY_NOT_EVALUATED",
            },
            "record_topology": {
                "required_prns": list(CODEBOOK),
                "required_fields_each_epoch": ["L1C", "L2W", "C1C", "C2W"],
                "required_pairs": 834,
                "required_normal_epochs": RAW_EPOCHS,
                "lli": "L1C_AND_L2W_ZERO_OR_BLANK",
                "extra_tracks": "DESCRIPTIVE_NOT_FATAL_NOT_SCORED",
                "interpolation": False,
                "gap_bridging": False,
            },
            "transform_ledger": {
                "SYS_SCALE_FACTOR": "TYPED_EXPLICIT_RECORD_OR_SPEC_DEFINED_UNITY_ABSENCE_THEN_DIVIDE_STORED_VALUE_BY_FACTOR",
                "SYS_PHASE_SHIFT": "TYPED_EXPLICIT_RECORD_OR_SPEC_DEFINED_ABSENCE_STORED_PHASE_ALREADY_INCLUDES_DECLARED_CORRECTION_NEVER_APPLY_TWICE",
                "RCV_CLOCK_OFFS_APPL": "TYPED_EXPLICIT_OR_SPEC_DEFINED_ZERO_DEFAULT_WITH_EVENT_AND_OBSERVATION_CORRECTION_APPLIED_EXACTLY_ONCE",
                "absence_malformed_conflict_and_incomplete_coverage_are_DISTINCT": True,
                "unresolved": "PRIMARY_NOT_EVALUATED",
            },
            "model_blind_witnesses": {
                "prediction_available": False,
                "geometry_free_phase_second_difference_limit_m": 0.09514683639918244,
                "same_path_phase_minus_code_heldout_peak_to_peak_limit_m_per_track": 1250.0,
                "six_track_ensemble_centering": "C=I-(1/6)11T",
                "complete_window_required": True,
                "failure": "MEASUREMENT_INVALID",
            },
        },
        "measurement_coordinate": {
            "per_track": "IONOSPHERE_FREE_L1C_L2W_PHASE_RANGE_M",
            "spatial_operator": "ENSEMBLE_CENTER_ACROSS_SIX_LABELLED_TRACKS_AT_EACH_EPOCH",
            "calibration": "PER_TRACK_CONSTANT_AND_RATE_FIT_ON_PREFIX_INDICES_0_TO_78_ONLY",
            "heldout": "INDICES_79_TO_138_NO_REFIT",
            "clock_and_common_offset": "REMOVED_ONLY_BY_DECLARED_OPERATOR",
        },
        "hypotheses": {
            "ORBITAL": "FROZEN_LABELLED_NOMINAL_RANGE_CURVES",
            "PREFIX_AFFINE_ONLY": "ZERO_MODEL_WITH_IDENTICAL_PREFIX_PROJECTION",
            "TIME_REVERSED_GEOMETRY": "FROZEN_NOMINAL_CURVES_REVERSED_ON_COMPLETE_GRID_WITH_IDENTICAL_PREFIX_PROJECTION",
            "same_nuisance_data_and_holdout": True,
        },
        "decision": {
            "score": "MAXIMUM_ACROSS_SIX_TRACKS_OF_HELDOUT_RESIDUAL_PEAK_TO_PEAK_M_WITH_HELDOUT_RMS_AS_NONCONTROLLING_DIAGNOSTIC",
            "calibration_not_detectable": "ORBITAL_PREFIX_RESIDUAL_PEAK_TO_PEAK_EXCEEDS_B",
            "preference": "ONE_FAMILY_SCORE_IS_LOWER_THAN_EVERY_OTHER_FAMILY_BY_STRICTLY_MORE_THAN_B",
            "orbital_positive_requires": [
                "ORBITAL_HELDOUT_SCORE_NO_GREATER_THAN_B",
                "ORBITAL_PREFERENCE_MARGIN_STRICTLY_GREATER_THAN_B",
            ],
            "heldout_refit": False,
            "free_time_phase": False,
            "threshold_changes": False,
        },
        "outcomes": [
            "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "PRIMARY_NOT_EVALUATED",
            "MEASUREMENT_INVALID",
            "NOT_DETECTABLE",
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "ORBITAL_PREDICTION_REJECTED",
            "PREFIX_AFFINE_NULL_PREFERRED",
            "TIME_REVERSED_GEOMETRY_NULL_PREFERRED",
            "AMBIGUOUS",
        ],
        "execution_order": [
            "COMPLETE_ARTIFACT_HASH",
            "COMPOSITE_IDENTITY_RECEIPT",
            "COMPLETE_LABELLED_RECORD_TOPOLOGY",
            "TYPED_TRANSFORM_LEDGER",
            "NUMERIC_CONVERSION_IN_RAM",
            "MODEL_BLIND_PHYSICAL_WITNESSES",
            "PREDICTION_BUNDLE_RELEASE_TO_SCORER",
            "PREFIX_CALIBRATION",
            "ONE_HELDOUT_ORBITAL_VERSUS_NULL_SCORE",
            "ONE_TERMINAL_OUTCOME",
            "ZERO_VALUE_PERSISTENCE_AND_BUFFER_ERASURE",
        ],
        "retry": {
            "before_complete_hash": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "after_complete_hash": 0,
            "alternate_station_date_window_prn_feature_or_threshold": False,
        },
        "claim_scope": {
            "maximum_positive": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "specific_identity": "MODEL_CONDITIONED_NOT_INDEPENDENTLY_ESTABLISHED",
            "distributed_multi_root": False,
            "anomaly_or_orbit_determination": False,
        },
        "frozen_inputs": authority,
        "access_at_freeze": {
            "observation_locator_requests": 0,
            "observation_headers": 0,
            "observation_payload_bytes": 0,
            "observation_values": 0,
            "orbital_scores": 0,
        },
        "next_maximum": "IMPLEMENT_ONE_EXPERIMENT_SPECIFIC_EXECUTOR_THAT_REFUSES_WHILE_ARTIFACT_IDENTITY_IS_UNSELECTED",
        "stop": "STOP_BEFORE_DOY238_OBSERVATION_LOOKUP_SELECTION_HEADER_PAYLOAD_VALUE_OR_SCORE",
    }
    strict_json(plan)
    return plan


def render_report(plan: Mapping[str, object]) -> str:
    detectability = plan["detectability"]
    return f"""# DRAO labelled-forward DOY238 integrated plan

**{plan['state']}**

This is one prospective forward experiment, not a new gate. The prediction and
all decisions are frozen before selecting an observation artifact.

## Physical question

Do the six predeclared DRAO phase paths predict the untouched held-out suffix
better than a prefix-affine null and time-reversed geometry?

## Geometry and detectability

- observer: `{STATION}` / DOMES `{DOMES}`;
- window: `2026-08-26 04:50:00--05:59:00 GPS`;
- prefix/held-out: `{PREFIX_EPOCHS}/{HELDOUT_EPOCHS}` epochs;
- codebook: `{'/'.join(CODEBOOK)}`;
- controlling separation: `{detectability['controlling_separation_m']:.6f} m`;
- one-model bound `B`: `{detectability['one_model_bound_b_m']:.6f} m`;
- required `3B`: `{detectability['required_separation_3b_m']:.6f} m`;
- remaining physical margin: `{detectability['remaining_physical_margin_m']:.6f} m`.

## Single integrated boundary

The future executor must perform identity, topology, a typed RINEX transform
ledger and model-blind phase/code witnesses before releasing the frozen model
bundle to the scorer. `MARKER NAME` is retained descriptively but never tested
as a literal alias. Scale-factor absence, phase-shift absence, malformed
records and incomplete coverage remain distinct states.

Extra GPS tracks are descriptive. Missing or invalid G14/G15/G17/G20/G24/G30
is fatal. There is no interpolation, gap bridging, held-out refit, free time
phase or post-hash retry.

## Claim boundary

A positive result can support only `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` for
receiver-labelled, model-conditioned tracks. It cannot establish independent
satellite identity, a distributed anomaly or orbit determination.

No DRAO DOY238 observation artifact has been queried or selected. Stop before
every observation locator, header, payload byte, value or score.
"""


def _write_once(path: Path, content: str) -> None:
    if path.exists():
        raise IntegratedPlanError(f"REFUSE_OVERWRITE:{path.name}")
    path.write_text(content, encoding="ascii", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("navigation_gzip", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if args.navigation_gzip.name != envelope.NAVIGATION_NAME:
        raise SystemExit("SUPPLY_EXACT_FROZEN_DOY238_NAVIGATION_PRODUCT")
    root = args.output_dir
    bundle = build_prediction_bundle(args.navigation_gzip.read_bytes(), root)
    plan = build_plan(bundle, root)
    plan["source_commit"] = _git_commit()
    plan["source_sha256"] = source_sha256()
    plan["prediction"]["bundle_sha256"] = object_sha256(bundle)
    strict_json(plan)
    _write_once(root / BUNDLE_NAME, strict_json(bundle, pretty=True) + "\n")
    _write_once(root / PLAN_NAME, strict_json(plan, pretty=True) + "\n")
    _write_once(root / REPORT_NAME, render_report(plan))
    print(plan["state"])


if __name__ == "__main__":
    main()
