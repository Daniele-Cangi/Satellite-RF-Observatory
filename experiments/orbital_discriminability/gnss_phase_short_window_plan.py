"""Frozen G22/G30 short-window qualification and primary proof plan.

This experiment-specific module performs no discovery and opens no observation
product.  It binds two distinct, still-unopened dates to the already frozen
broadcast-only duration result and defines the measurement/held-out boundary
that a later implementation must obey.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


PLAN_VERSION: Final = "g22-g30-phase-short-window-proof-v1"
DURATION_RECEIPT_NAME: Final = "GNSS_PHASE_DURATION_SENSITIVITY_RECEIPT.json"
DURATION_RECEIPT_SHA256: Final = (
    "a81be2ddfb8d9455915118c74281f93dbf4919da3c140d58e18ebc4ccb4cee49"
)
DURATION_SOURCE_COMMIT: Final = (
    "6da19a8404db1313e10c0bfc3209737d78013cd7"
)
DURATION_OUTCOME_COMMIT: Final = (
    "0cbc366b8e02f5398d45eaaa99ac8dcf7d963ca4"
)

STEP_S: Final = 30
RAW_EPOCHS: Final = 139
FEATURE_EPOCHS: Final = 137
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 60
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 137)
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244

QUALIFICATION_DOY: Final = 217
PRIMARY_DOY: Final = 220
QUALIFICATION_RAW_START: Final = datetime(
    2026, 8, 5, 5, 54, 0, tzinfo=timezone.utc
)
PRIMARY_RAW_START: Final = datetime(
    2026, 8, 8, 5, 42, 0, tzinfo=timezone.utc
)

PRIMARY_ONE_MODEL_ENVELOPE_M: Final = 1192.1168692918313
PRIMARY_PAIRWISE_DECISION_GUARD_M: Final = 2384.2337385836627
PRIMARY_CONTROLLING_SEPARATION_M: Final = 8857.431880665245
PRIMARY_REMAINING_PHYSICAL_MARGIN_M: Final = 6473.198142081582

ALTERNATIVE_ORBITS: Final = {
    "G01": 8857.431880665245,
    "G14": 60003.29156747623,
    "G17": 122006.60516244936,
}


class ShortWindowPlanError(ValueError):
    """The frozen proof boundary or source receipt changed."""


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _gps(epoch: datetime) -> str:
    return epoch.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", " GPS"
    )


def _role(
    *, role: str, doy: int, raw_start: datetime, access: str
) -> dict[str, object]:
    raw_stop = raw_start + timedelta(seconds=(RAW_EPOCHS - 1) * STEP_S)
    feature_start = raw_start + timedelta(seconds=STEP_S)
    feature_stop = raw_stop - timedelta(seconds=STEP_S)
    heldout_start = feature_start + timedelta(
        seconds=CALIBRATION_EPOCHS * STEP_S
    )
    return {
        "role": role,
        "doy": doy,
        "stations": ["GOLD00USA", "NLIB00USA"],
        "target": "G22",
        "reference": "G30",
        "predeclared_product_locators": [
            f"GOLD00USA_R_2026{doy:03d}0000_01D_30S_MO.crx.gz",
            f"NLIB00USA_R_2026{doy:03d}0000_01D_30S_MO.crx.gz",
        ],
        "product_identity_state": "LOCATOR_ONLY_NOT_DISCOVERED_OR_MATERIALIZED",
        "artifact_sha256": None,
        "raw_start_gps": _gps(raw_start),
        "raw_stop_gps": _gps(raw_stop),
        "feature_start_gps": _gps(feature_start),
        "feature_stop_gps": _gps(feature_stop),
        "heldout_start_gps": _gps(heldout_start),
        "raw_epochs": RAW_EPOCHS,
        "feature_epochs": FEATURE_EPOCHS,
        "access": access,
    }


def plan() -> dict[str, object]:
    result = {
        "schema": "gnss-phase-short-window-proof-plan-v1",
        "plan_version": PLAN_VERSION,
        "physical_question": (
            "CAN_A_QUALIFIED_69_MINUTE_G22_G30_CONTINUOUS_PHASE_"
            "MEASUREMENT_PREFER_THE_FROZEN_ORBIT_ON_AN_UNOPENED_PRIMARY_DATE"
        ),
        "source_duration_result": {
            "receipt": DURATION_RECEIPT_NAME,
            "receipt_canonical_sha256": DURATION_RECEIPT_SHA256,
            "calculation_source_commit": DURATION_SOURCE_COMMIT,
            "outcome_commit": DURATION_OUTCOME_COMMIT,
            "outcome": "PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE",
        },
        "role_selection": {
            "qualification_reason": (
                "DOY217_HAS_THE_LARGEST_REMAINING_MARGIN_AT_THE_SHORTEST_"
                "FROZEN_DURATION_AND_IS_DISTINCT_FROM_PRIMARY"
            ),
            "primary_reason": (
                "DOY220_HAS_THE_LARGEST_FOUR_LINK_GUARD_AT_THE_SHORTEST_"
                "FROZEN_DURATION"
            ),
            "infrastructure_availability_used": False,
            "observation_values_used": False,
            "reserve": None,
        },
        "roles": {
            "qualification": _role(
                role="INDEPENDENT_MEASUREMENT_QUALIFICATION_ONLY",
                doy=QUALIFICATION_DOY,
                raw_start=QUALIFICATION_RAW_START,
                access="NEXT_REVIEW_MAY_AUTHORIZE_ONLY_THIS_DATE",
            ),
            "primary": _role(
                role="HELD_OUT_ORBITAL_PRIMARY",
                doy=PRIMARY_DOY,
                raw_start=PRIMARY_RAW_START,
                access="SEALED_UNDISCOVERED_UNAUTHORIZED",
            ),
        },
        "partition": {
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "raw_elapsed_s": (RAW_EPOCHS - 1) * STEP_S,
            "feature_epochs": FEATURE_EPOCHS,
            "feature_raw_indices_inclusive": [1, 137],
            "calibration_epochs": CALIBRATION_EPOCHS,
            "calibration_raw_indices_inclusive": [1, 77],
            "heldout_epochs": HELDOUT_EPOCHS,
            "heldout_raw_indices_inclusive": [78, 137],
            "holdout_may_refit_nuisance": False,
        },
        "measurement_coordinate": {
            "core_phase": ["L1C", "L2W"],
            "ionosphere_free_coefficients": [
                2.5457277801631601,
                -1.5457277801631601,
            ],
            "station_satellite_order": (
                "(GOLD_G22_MINUS_GOLD_G30)_MINUS_"
                "(NLIB_G22_MINUS_NLIB_G30)"
            ),
            "unit": "METER_EQUIVALENT_CONTINUOUS_CARRIER_PHASE",
            "derivative": "NONE",
            "interpolation": "FORBIDDEN",
            "gap_bridging": "FORBIDDEN",
        },
        "qualification": {
            "header_configuration_must_match": {
                "GOLD00USA": {
                    "receiver": "JAVAD TRE_G3TH DELTA",
                    "receiver_version": "4.2.03",
                    "antenna": "AOAD/M_T NONE",
                },
                "NLIB00USA": {
                    "receiver": "SEPT POLARX5TR",
                    "receiver_version": "5.7.0",
                    "antenna": "JAVRINGANT_DM SCIS",
                },
            },
            "required_structure": [
                "ALL_139_EPOCHS_PRESENT_ON_BOTH_STATIONS",
                "L1C_AND_L2W_PRESENT_ON_ALL_FOUR_LINKS",
                "ZERO_LLI_ON_BOTH_PHASE_FIELDS_ALL_FOUR_LINKS",
                "EXACT_30_SECOND_GRID",
                "TIME_OF_LAST_OBS_COVERS_FROZEN_WINDOW",
            ],
            "same_path_code_witness": {
                "fields": ["C1C", "C2W"],
                "minimum_presence_fraction_per_link": (
                    CODE_MINIMUM_COVERAGE_FRACTION
                ),
                "required_raw_indices": list(CODE_REQUIRED_RAW_INDICES),
                "may_adjust_phase_score": False,
            },
            "geometry_free_health": {
                "maximum_absolute_second_difference_m": (
                    GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                ),
                "evaluated_without_orbital_prediction": True,
            },
            "optional_diagnostic": ["S1C", "S2W"],
            "pass_authorizes": "PRIMARY_PLAN_SEAL_REVIEW_ONLY",
            "failure_authorizes_substitution": False,
        },
        "primary_hypotheses": {
            "orbital": "BROADCAST_G22_RELATIVE_TO_G30",
            "prefix_affine": "ZERO_GEOMETRIC_CURVE_WITH_SAME_PREFIX_FIT",
            "wrong_orbits": list(ALTERNATIVE_ORBITS),
            "wrong_orbit_predicted_separations_m": ALTERNATIVE_ORBITS,
        },
        "scoring": {
            "per_hypothesis_nuisance": (
                "CONSTANT_PLUS_RATE_FIT_ON_FIXED_77_EPOCH_PREFIX_ONLY"
            ),
            "heldout_metrics": ["PEAK_TO_PEAK_M", "RMS_M"],
            "orbital_calibration_peak_to_peak_admission_m": (
                PRIMARY_ONE_MODEL_ENVELOPE_M
            ),
            "heldout_preference_margin_required_m": (
                PRIMARY_PAIRWISE_DECISION_GUARD_M
            ),
            "frozen_controlling_predicted_separation_m": (
                PRIMARY_CONTROLLING_SEPARATION_M
            ),
            "frozen_remaining_physical_margin_m": (
                PRIMARY_REMAINING_PHYSICAL_MARGIN_M
            ),
            "suffix_refit": "FORBIDDEN",
            "free_time_phase": "FORBIDDEN",
            "threshold_change_after_qualification": "FORBIDDEN",
        },
        "qualification_outcomes": [
            "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED",
            "GNSS_SHORT_WINDOW_QUALIFICATION_FAILED",
            "GNSS_SHORT_WINDOW_ARTIFACT_MATERIALIZATION_FAILED",
            "GNSS_SHORT_WINDOW_DESCRIPTION_ERROR",
        ],
        "future_primary_outcomes": [
            "MEASUREMENT_INVALID",
            "NOT_DETECTABLE",
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "PREFIX_AFFINE_NULL_PREFERRED",
            "WRONG_ORBIT_G01_PREFERRED",
            "WRONG_ORBIT_G14_PREFERRED",
            "WRONG_ORBIT_G17_PREFERRED",
            "AMBIGUOUS",
        ],
        "access_boundary": {
            "observation_products_discovered": 0,
            "observation_headers_opened": 0,
            "observation_payload_bytes": 0,
            "observation_values_accessed": 0,
            "primary_access": "FORBIDDEN",
            "next_maximum": (
                "BOUNDED_QUALIFICATION_PRODUCT_DISCOVERY_MATERIALIZATION_HASH_"
                "STRUCTURE_AND_MODEL_BLIND_HEALTH_ONLY"
            ),
        },
        "stop_condition": (
            "STOP_AFTER_QUALIFICATION_OUTCOME_PRIMARY_REQUIRES_SEPARATE_REVIEW"
        ),
        "new_gate_created": False,
        "generic_framework_created": False,
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(plan()).encode("ascii")).hexdigest()


def verify_duration_receipt(path: Path) -> Mapping[str, object]:
    if canonical_sha256(path) != DURATION_RECEIPT_SHA256:
        raise ShortWindowPlanError("DURATION_RECEIPT_CHANGED")
    receipt = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )
    if receipt.get("outcome") != "PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE":
        raise ShortWindowPlanError("SHORT_WINDOW_NOT_AVAILABLE")
    if receipt.get("shortest_available_heldout_epochs") != HELDOUT_EPOCHS:
        raise ShortWindowPlanError("HELDOUT_DURATION_CHANGED")
    if any(receipt.get("observation_access", {}).values()):
        raise ShortWindowPlanError("SOURCE_RECEIPT_USED_OBSERVATIONS")
    if any(value is not None for value in receipt.get("candidate_roles", {}).values()):
        raise ShortWindowPlanError("SOURCE_RECEIPT_ALREADY_ASSIGNED_ROLES")
    rows = {
        (row["doy"], row["heldout_epochs"]): row
        for row in receipt["duration_rows"]
    }
    qualification = rows[(QUALIFICATION_DOY, HELDOUT_EPOCHS)]
    primary = rows[(PRIMARY_DOY, HELDOUT_EPOCHS)]
    if qualification["remaining_physical_margin_m"] <= 0.0:
        raise ShortWindowPlanError("QUALIFICATION_GEOMETRY_NOT_POSITIVE")
    if primary["remaining_physical_margin_m"] != PRIMARY_REMAINING_PHYSICAL_MARGIN_M:
        raise ShortWindowPlanError("PRIMARY_MARGIN_CHANGED")
    if primary["wrong_orbit_null"]["controlling_alternative"] != "G01":
        raise ShortWindowPlanError("PRIMARY_CONTROLLING_NULL_CHANGED")
    return receipt
