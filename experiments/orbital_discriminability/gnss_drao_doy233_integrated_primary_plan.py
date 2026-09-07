"""Freeze the integrated DRAO DOY233 primary without selecting an artifact.

This module compiles the already frozen model-side trajectories into a compact
opaque bundle and a separately sealed identity reveal.  It creates no gate,
performs no network request and has no observation-product locator.
"""

from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Final, Mapping, Sequence


PLAN_VERSION: Final = "drao-doy233-integrated-primary-plan-v1"
PLAN_NAME: Final = "GNSS_DRAO_DOY233_INTEGRATED_PRIMARY_PLAN.json"
REPORT_NAME: Final = "GNSS_DRAO_DOY233_INTEGRATED_PRIMARY_PLAN.md"
BUNDLE_NAME: Final = "GNSS_DRAO_DOY233_OPAQUE_PREDICTION_BUNDLE.json"
REVEAL_NAME: Final = "GNSS_DRAO_DOY233_IDENTITY_REVEAL.json"

REVIEW_NAME: Final = "POST_DRAO_DOY232_QUALIFICATION_CHANGE_OF_ABSTRACTION.json"
REVIEW_SHA256: Final = (
    "7c293462c0e0fe1602519eb339c8c96fc6aef7cc735d7c84e416eeb8d28c2934"
)
MODEL_NAME: Final = "GNSS_DRAO_STAGED_MODEL_ENVELOPE.json"
MODEL_SHA256: Final = (
    "12578d1ea24fef1d71875280e41588e8a96cba78b3c45f6f8787eab8599e4626"
)
CLUTTER_PLAN_NAME: Final = "GNSS_DRAO_ONE_CLUTTER_PROSPECTIVE_PLAN.json"
CLUTTER_PLAN_SHA256: Final = (
    "4d4b370b51486b0122c1138c26bb67d24b87629dfa85260f6e299feea172c244"
)
SCORER_NAME: Final = "gnss_all_track_clutter_scorer.py"
SCORER_SHA256: Final = (
    "ecdf2afffed80f279a23bcaa46a870b5acee3272709e166c8e9c2a97d1205033"
)

STATION: Final = "DRAO00CAN"
DOMES: Final = "40105M002"
DOY: Final = 233
RAW_START_GPS: Final = "2026-08-21T01:14:30 GPS"
RAW_STOP_GPS: Final = "2026-08-21T02:23:30 GPS"
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
MODEL_CODES: Final = ("G07", "G08", "G09", "G21", "G27", "G30")
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
PAIRWISE_GUARD_M: Final = 7_339.701234647398
MODEL_SIDE_ENVELOPE_M: Final = 881.9589614531837
CAPABILITY_RESERVE_M: Final = 2_506.0017238368005
COMBINED_ENVELOPE_M: Final = 3_387.960685289984
REMAINING_MARGIN_M: Final = 3_951.7405493574142
GEOMETRY_SEPARATION_M: Final = 49_090.48543325415
TRACK_ID_SALT: Final = "DRAO_DOY233_TRACK_REVEAL_V1"


class PlanError(ValueError):
    """A frozen input or generated prospective artifact is invalid."""


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


def object_sha256(value: object) -> str:
    return sha256(strict_json(value).encode("ascii")).hexdigest()


def _read_exact(root: Path, name: str, digest: str) -> dict[str, object]:
    path = Path(root) / name
    if not path.is_file() or canonical_sha256(path) != digest:
        raise PlanError(f"FROZEN_INPUT_CHANGED:{name}")
    value = json.loads(
        path.read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise PlanError(f"FROZEN_INPUT_NOT_OBJECT:{name}")
    return value


def _opaque(prefix: str, text: str) -> str:
    return prefix + sha256(text.encode("ascii")).hexdigest()[:16].upper()


def opaque_track_id(prn: str) -> str:
    if len(prn) != 3 or not prn.startswith("G") or not prn[1:].isdigit():
        raise PlanError("TRACK_REVEAL_IDENTITY_INVALID")
    return _opaque("T_", f"{TRACK_ID_SALT}:{prn}")


def _finite_curve(values: Sequence[object], label: str) -> list[float]:
    result = [float(value) for value in values]
    if len(result) != RAW_EPOCHS or not all(isfinite(value) for value in result):
        raise PlanError(f"MODEL_CURVE_INVALID:{label}")
    return result


def build_prediction_artifacts(
    root: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    root = Path(root)
    model = _read_exact(root, MODEL_NAME, MODEL_SHA256)
    _read_exact(root, REVIEW_NAME, REVIEW_SHA256)
    _read_exact(root, CLUTTER_PLAN_NAME, CLUTTER_PLAN_SHA256)
    scorer_path = root / SCORER_NAME
    if canonical_sha256(scorer_path) != SCORER_SHA256:
        raise PlanError("FROZEN_ONE_CLUTTER_SCORER_CHANGED")

    try:
        retained = model["retained_model_curves"]
        raw_curves = retained[
            "retarded_earth_rotation_corrected_range_m_by_satellite"
        ]
    except (KeyError, TypeError) as exc:
        raise PlanError("MODEL_CURVE_LEDGER_MISSING") from exc
    if not isinstance(raw_curves, Mapping) or set(raw_curves) != set(MODEL_CODES):
        raise PlanError("MODEL_CODEBOOK_CHANGED")

    curves: dict[str, list[float]] = {}
    reveal_rows: list[dict[str, str]] = []
    for code in MODEL_CODES:
        opaque_id = _opaque("M_", f"DRAO_DOY233_RETARDED_RANGE:{code}")
        curves[opaque_id] = _finite_curve(raw_curves[code], code)
        reveal_rows.append({"opaque_model_id": opaque_id, "satellite": code})

    bundle = {
        "schema": "gnss-drao-doy233-opaque-prediction-bundle-v1",
        "coordinate": "RETARDED_EARTH_ROTATION_CORRECTED_RANGE_M",
        "grid": {
            "start_gps": RAW_START_GPS,
            "stop_gps": RAW_STOP_GPS,
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
        },
        "opaque_model_curves_m": dict(sorted(curves.items())),
        "surface": {
            "observed_tracks": 7,
            "included_tracks_per_hypothesis": 6,
            "clutter_budget": 1,
            "orbital_hypotheses": 5_040,
            "time_reversed_geometry_nulls": 5_040,
            "prefix_affine_nulls": 7,
            "total_hypotheses": 10_087,
            "orbital_constructor": "ALL_7_EXCLUSIONS_TIMES_ALL_6_FACTORIAL_ASSIGNMENTS",
            "geometry_null_constructor": "SAME_EXCLUSIONS_AND_ASSIGNMENTS_WITH_EACH_MODEL_CURVE_TIME_REVERSED",
            "affine_null_constructor": "ZERO_MODEL_MATRIX_FOR_EACH_EXCLUSION_WITH_PREFIX_AFFINE_PROJECTION",
        },
        "scorer": {
            "name": SCORER_NAME,
            "canonical_sha256": SCORER_SHA256,
            "pairwise_guard_m": PAIRWISE_GUARD_M,
            "heldout_refit": False,
            "free_time_phase": False,
        },
        "identity_available_to_scorer": False,
        "observation_values": 0,
    }
    reveal = {
        "schema": "gnss-drao-doy233-identity-reveal-v1",
        "model_mapping": reveal_rows,
        "track_identity_function": "T_ + FIRST_16_HEX(SHA256(TRACK_ID_SALT + ':' + PRN))",
        "track_id_salt": TRACK_ID_SALT,
        "reveal_only_after_opaque_score_receipt_hash": True,
        "expected_orbit_codebook": list(MODEL_CODES),
        "code_witness_is_same_receiver_not_independent_hardware": True,
    }
    if any(code in strict_json(bundle) for code in MODEL_CODES):
        raise PlanError("MODEL_IDENTITY_LEAKED_INTO_OPAQUE_BUNDLE")
    strict_json(bundle)
    strict_json(reveal)
    return bundle, reveal


def build_plan(root: Path) -> dict[str, object]:
    root = Path(root)
    bundle, reveal = build_prediction_artifacts(root)
    plan = {
        "schema": "gnss-drao-doy233-integrated-primary-plan-v1",
        "version": PLAN_VERSION,
        "state": "DRAO_DOY233_INTEGRATED_PRIMARY_PLAN_FROZEN_ARTIFACT_UNSELECTED",
        "new_gate": False,
        "physical_question": (
            "CAN_SIX_FROZEN_DRAO_ORBITAL_CURVES_BE_ASSIGNED_TO_SEVEN_"
            "ANONYMOUS_REAL_PHASE_TRACKS_WITH_ONE_SYMMETRIC_CLUTTER_"
            "ALLOWANCE_AND_PREDICT_THE_UNTOUCHED_SUFFIX_BETTER_THAN_"
            "THE_SAME_FREEDOM_AFFINE_AND_TIME_REVERSED_NULLS"
        ),
        "new_physical_information": (
            "A_REAL_PROSPECTIVE_TEST_OF_ANONYMOUS_ORBITAL_ASSIGNMENT_"
            "WITH_CODE_IDENTITY_REVEALED_ONLY_AFTER_THE_OPAQUE_SCORE_IS_HASHED"
        ),
        "why_existing_results_cannot_answer": (
            "THE_ONE_CLUTTER_RESULT_IS_SYNTHETIC_AND_THE_PRIOR_REAL_"
            "AMC_ASSIGNMENT_SELECTED_PRN_LABELLED_FIELDS_UPSTREAM"
        ),
        "minimum_experiment": (
            "ONE_DRAO_DOY233_ARTIFACT_ADMITTED_AND_SCORED_ONCE_OR_ONE_"
            "TYPED_NOT_EVALUATED_TERMINAL_BEFORE_SCORE"
        ),
        "stop_condition": (
            "STOP_NOW_BEFORE_LOCATOR_SELECTION_AND_LATER_STOP_AFTER_ONE_"
            "TERMINAL_PRIMARY_OUTCOME_WITH_ZERO_POST_HASH_RETRY"
        ),
        "candidate": {
            "station": STATION,
            "domes": DOMES,
            "gps_doy": DOY,
            "window": bundle["grid"],
            "orbit_codebook": list(MODEL_CODES),
            "logical_product": None,
            "locator": None,
            "complete_artifact_sha256": None,
            "artifact_selected": False,
            "observation_access_authorized": False,
        },
        "detectability": {
            "retarded_geometry_controlling_separation_m": GEOMETRY_SEPARATION_M,
            "model_side_envelope_m": MODEL_SIDE_ENVELOPE_M,
            "conditional_capability_reserve_m": CAPABILITY_RESERVE_M,
            "combined_conditional_envelope_m": COMBINED_ENVELOPE_M,
            "pairwise_guard_m": PAIRWISE_GUARD_M,
            "remaining_margin_m": REMAINING_MARGIN_M,
            "qualification_may_change_numbers": False,
        },
        "admission_before_score": {
            "identity": {
                "binding": [
                    "FUTURE_FROZEN_ARTIFACT_SITE_ID_DRAO00CAN",
                    "MARKER_NUMBER_DOMES_40105M002",
                    "FROZEN_DRAO_RECEIVER_AND_ANTENNA",
                ],
                "marker_name": "RETAINED_DESCRIPTIVE_CONSISTENCY_NOT_STANDALONE_KEY",
                "conflict": "IDENTITY_EVIDENCE_CONFLICT_OR_INCOMPLETE_NOT_EVALUATED",
            },
            "header": [
                "RINEX_3",
                "GPS_TIME",
                "TIME_OF_FIRST_AND_LAST_OBS_COVER_WINDOW",
                "INTERVAL_30_SECONDS",
                "EXPLICIT_SCALE_PHASE_SHIFT_AND_RECEIVER_CLOCK_SEMANTICS",
            ],
            "track_selection": (
                "ALL_GPS_TRACKS_WITH_COMPLETE_L1C_L2W_C1C_C2W_AND_ZERO_LLI_"
                "ON_ALL_139_EPOCHS_NO_PRN_FILTER"
            ),
            "complete_opaque_track_count": 7,
            "core_phase": list(CORE_PHASE),
            "same_path_code": list(SAME_PATH_CODE),
            "gap_bridging": False,
            "interpolation": False,
            "geometry_free_second_difference_limit_m": 0.09514683639918244,
            "same_path_witness": {
                "coordinate": "IF_PHASE_M_MINUS_IF_CODE_M",
                "six_track_subsets_evaluated": 7,
                "common_mode": "C=I-(1/6)11T_WITHIN_EACH_POSSIBLE_EXCLUSION",
                "prefix_projection": "CONSTANT_PLUS_RATE_FIRST_79_EPOCHS_ONLY",
                "heldout_peak_to_peak_limit_m_per_included_track": 1_250.0,
                "every_possible_included_track_must_pass": True,
            },
        },
        "execution_order": [
            "COMPLETE_ARTIFACT_HASH",
            "ATTRIBUTABLE_HEADER_IDENTITY_RECEIPT",
            "FULL_WINDOW_STRUCTURAL_ADMISSION",
            "MODEL_BLIND_PHASE_CODE_AND_CONTINUITY_WITNESSES",
            "PRE_SCORE_CODE_REVEAL_HASH_IN_RAM",
            "OPAQUE_ONE_CLUTTER_SCORE_RECEIPT",
            "OPAQUE_SCORE_RECEIPT_HASH",
            "CODE_AND_MODEL_IDENTITY_REVEAL",
            "ONE_TERMINAL_OUTCOME",
        ],
        "nulls": {
            "orbital": "ALL_EXCLUSIONS_AND_ALL_BIJECTIVE_ASSIGNMENTS",
            "geometry_destroying": "TIME_REVERSED_WITH_IDENTICAL_EXCLUSION_AND_ASSIGNMENT_FREEDOM",
            "non_orbital": "PREFIX_AFFINE_ONLY_FOR_EVERY_EXCLUSION",
            "same_calibration_and_heldout": True,
        },
        "outcomes": {
            "description_or_identity": "PRIMARY_NOT_EVALUATED",
            "measurement_invalid": "MEASUREMENT_INVALID",
            "measurement_not_detectable": "NOT_DETECTABLE",
            "orbital_concordant": "DRAO_ONE_CLUTTER_ORBIT_CODE_CONCORDANT",
            "orbital_discordant": "DRAO_ONE_CLUTTER_ORBIT_CODE_DISCORDANT",
            "non_orbital": "DRAO_NONORBITAL_NULL_SUPPORTED",
            "ambiguous": "AMBIGUOUS",
            "no_admissible_hypothesis": "NO_ADMISSIBLE_HYPOTHESIS",
        },
        "retry": {
            "before_complete_hash": "FUTURE_SELECTION_MAY_DECLARE_BOUNDED_TRANSPORT_ONLY",
            "after_complete_hash": 0,
            "alternate_station_date_window_or_feature": False,
        },
        "frozen_artifacts": {
            BUNDLE_NAME: object_sha256(bundle),
            REVEAL_NAME: object_sha256(reveal),
            REVIEW_NAME: REVIEW_SHA256,
            MODEL_NAME: MODEL_SHA256,
            CLUTTER_PLAN_NAME: CLUTTER_PLAN_SHA256,
            SCORER_NAME: SCORER_SHA256,
        },
        "access_at_freeze": {
            "locator_requests": 0,
            "headers": 0,
            "payload_bytes": 0,
            "observation_values": 0,
            "orbital_scores": 0,
        },
        "next_maximum": (
            "FREEZE_THE_EXPERIMENT_SPECIFIC_INTEGRATED_EXECUTOR_WITH_A_"
            "HARD_REFUSAL_WHILE_ARTIFACT_IDENTITY_IS_UNSELECTED"
        ),
    }
    strict_json(plan)
    return plan


def report(plan: Mapping[str, object]) -> str:
    detectability = plan["detectability"]
    return f"""# DRAO DOY233 integrated primary plan

**{plan['state']}**

This is the prospective proof boundary after the consumed DOY232 descriptive
failure. It creates no gate, selects no product or locator and authorizes zero
observation access.

## Physical question

Can six frozen DRAO orbital curves be assigned to seven anonymous real phase
tracks with one symmetric clutter allowance and predict an untouched suffix
better than affine and time-reversed alternatives with identical freedom?

The prior one-clutter result is synthetic. The real AMC blind assignment was
PRN-conditioned upstream. Only a new real, anonymous all-track primary can
answer this question.

## Frozen geometry and envelope

- observer: `{STATION}` / DOMES `{DOMES}`;
- window: `{RAW_START_GPS}`--`{RAW_STOP_GPS}`;
- grid: {RAW_EPOCHS} epochs at {STEP_S} s, prefix {PREFIX_EPOCHS}, held-out {HELDOUT_EPOCHS};
- orbital codebook: `{'/'.join(MODEL_CODES)}`;
- controlling retarded-geometry separation: `{detectability['retarded_geometry_controlling_separation_m']:.6f} m`;
- combined conditional envelope: `{detectability['combined_conditional_envelope_m']:.6f} m`;
- frozen guard: `{detectability['pairwise_guard_m']:.6f} m`;
- remaining margin: `{detectability['remaining_margin_m']:.6f} m`.

## Admission before score

The primary may score only after artifact identity, attributable header
identity, complete timing/structure, zero LLI, geometry-free continuity and
same-path phase/code witnesses pass. Exactly seven complete tracks enter; no
PRN subset is selected. Every one of the seven possible six-track exclusions
must satisfy the same 1,250 m per-track held-out witness bound after its own
six-track common-mode projection and prefix-only affine fit.

`MARKER NUMBER = {DOMES}` plus the future frozen artifact site ID and receiver/
antenna identity are binding. `MARKER NAME` is retained before decision as a
descriptive consistency field, not used alone as a station key. Incomplete or
conflicting identity evidence produces `PRIMARY_NOT_EVALUATED`, not physical
measurement rejection.

## Opaque comparison

The compact bundle contains six unlabeled range curves. The scorer enumerates
all 7 exclusions and all 6! assignments for both orbital and time-reversed
families, plus one affine null for every exclusion: 10,087 hypotheses. The
actual PRN-to-track witness is hashed before scoring but revealed only after
the opaque score receipt itself is persisted and hashed.

There is no held-out refit, free time phase, interpolation, gap bridging,
post-hash retry or replacement station/date/window.

## Stop

The DOY233 logical product, locator and complete-file hash remain unselected.
No header, payload byte or observation value has been accessed. The next
maximum action is the offline experiment-specific executor, which must refuse
execution until a later exact artifact selection and seal exist.
"""


def write(root: Path) -> None:
    root = Path(root)
    bundle, reveal = build_prediction_artifacts(root)
    plan = build_plan(root)
    outputs = {
        BUNDLE_NAME: strict_json(bundle, pretty=True) + "\n",
        REVEAL_NAME: strict_json(reveal, pretty=True) + "\n",
        PLAN_NAME: strict_json(plan, pretty=True) + "\n",
        REPORT_NAME: report(plan),
    }
    for name, text in outputs.items():
        (root / name).write_text(text, encoding="ascii", newline="\n")


def main() -> None:
    write(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
