"""Frozen, observation-blind plan for one distinct-pass GNSS replication."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


PLAN_VERSION: Final = "g22-g30-distinct-pass-replication-v1"
DURATION_RECEIPT_NAME: Final = "GNSS_PHASE_DURATION_SENSITIVITY_RECEIPT.json"
DURATION_RECEIPT_SHA256: Final = (
    "a81be2ddfb8d9455915118c74281f93dbf4919da3c140d58e18ebc4ccb4cee49"
)
PRIMARY_OUTCOME_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_PRIMARY_OUTCOME.json"
PRIMARY_OUTCOME_SHA256: Final = (
    "66adf39fa1b10cbf43bdb712ebf4d1f3d8f598203caaa8fa2a41601fea511f9d"
)
PRIMARY_OUTCOME_COMMIT: Final = "44cc76772f58355c5a0f0bf70fac3b51f9e1be07"
PRIMARY_PLAN_MANIFEST_SHA256: Final = (
    "0068385ef4aaf1014f0211efaa47da52da8c5fb18cf51377f4812434fd2b5f3c"
)

STEP_S: Final = 30
RAW_EPOCHS: Final = 139
FEATURE_EPOCHS: Final = 137
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 60
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 137)
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244

CONSUMED_DOYS: Final = (217, 220)
REPLICATION_DOY: Final = 219
SEALED_RESERVE_DOY: Final = 218
REPLICATION_RAW_START: Final = datetime(2026, 8, 7, 5, 46, tzinfo=timezone.utc)
RESERVE_RAW_START: Final = datetime(2026, 8, 6, 5, 50, tzinfo=timezone.utc)

ONE_MODEL_ENVELOPE_M: Final = 1188.851495144414
PAIRWISE_DECISION_GUARD_M: Final = 2377.702990288828
CONTROLLING_SEPARATION_M: Final = 8986.714337965008
REMAINING_PHYSICAL_MARGIN_M: Final = 6609.01134767618
ALTERNATIVE_ORBITS: Final = {
    "G01": 8986.714337965008,
    "G14": 59929.3302432223,
    "G17": 121986.514415665,
}


class RepeatedPassPlanError(ValueError):
    """The frozen source evidence or prospective boundary changed."""


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _gps(epoch: datetime) -> str:
    return epoch.isoformat(timespec="seconds").replace("+00:00", " GPS")


def _role(role: str, doy: int, start: datetime, access: str) -> dict[str, object]:
    stop = start + timedelta(seconds=(RAW_EPOCHS - 1) * STEP_S)
    feature_start = start + timedelta(seconds=STEP_S)
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
        "raw_start_gps": _gps(start),
        "raw_stop_gps": _gps(stop),
        "feature_start_gps": _gps(feature_start),
        "feature_stop_gps": _gps(stop - timedelta(seconds=STEP_S)),
        "heldout_start_gps": _gps(
            feature_start + timedelta(seconds=CALIBRATION_EPOCHS * STEP_S)
        ),
        "access": access,
    }


def plan() -> dict[str, object]:
    result = {
        "schema": "gnss-phase-repeated-pass-plan-v1",
        "plan_version": PLAN_VERSION,
        "physical_question": (
            "DOES_THE_FROZEN_G22_RELATIVE_G30_ORBITAL_PREFERENCE_REPEAT_ON_A_"
            "DISTINCT_UNOPENED_PASS_WITH_THE_SAME_TWO_INDEPENDENT_ROOTS"
        ),
        "new_information": "REPEATED_PASS_CONSISTENCY_NOT_A_DOY220_RESCORE",
        "why_existing_cannot_answer": "DOY220_CONTAINS_ONLY_ONE_PASS_REALIZATION",
        "routes": {
            "selected_same_roots_distinct_pass": {
                "independent": ["DATE", "PASS_GEOMETRY", "OBSERVATION_ARTIFACT"],
                "shared": ["STATION_PAIR", "RECEIVER_FAMILIES", "SCORER"],
                "information": "DIRECT_REPEATABILITY",
            },
            "deferred_new_station_pair": {
                "information": "HARDWARE_AND_GEOGRAPHY_GENERALIZATION",
                "cost": "NEW_DISCOVERY_AND_STRUCTURAL_QUALIFICATION",
            },
            "deferred_new_target_pair": {
                "information": "CROSS_TARGET_GENERALIZATION",
                "cost": "CHANGES_PHYSICAL_HYPOTHESIS_BEFORE_REPEATABILITY_TEST",
            },
        },
        "source_evidence": {
            "duration_receipt": DURATION_RECEIPT_NAME,
            "duration_receipt_canonical_sha256": DURATION_RECEIPT_SHA256,
            "primary_outcome": PRIMARY_OUTCOME_NAME,
            "primary_outcome_canonical_sha256": PRIMARY_OUTCOME_SHA256,
            "primary_outcome_commit": PRIMARY_OUTCOME_COMMIT,
            "primary_plan_manifest_sha256": PRIMARY_PLAN_MANIFEST_SHA256,
            "primary_terminal_result": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "primary_reopened_or_rescored": False,
        },
        "selection": {
            "rule": (
                "FIRST_UNOPENED_DATE_IN_PRE_OUTCOME_RANKING_AFTER_EXCLUDING_"
                "CONSUMED_QUALIFICATION_AND_PRIMARY"
            ),
            "pre_outcome_ranking": [220, 219, 218, 217],
            "excluded_consumed_dates": list(CONSUMED_DOYS),
            "replication_doy": REPLICATION_DOY,
            "sealed_reserve_doy": SEALED_RESERVE_DOY,
            "product_availability_used": False,
            "observation_information_used": False,
        },
        "roles": {
            "replication": _role(
                "DISTINCT_PASS_HELD_OUT_REPLICATION",
                REPLICATION_DOY,
                REPLICATION_RAW_START,
                "SEALED_UNDISCOVERED_UNAUTHORIZED",
            ),
            "reserve": _role(
                "SEALED_REPLICATION_RESERVE",
                SEALED_RESERVE_DOY,
                RESERVE_RAW_START,
                "SEALED_UNDISCOVERED_UNAUTHORIZED_NOT_A_RETRY",
            ),
        },
        "partition": {
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "feature_epochs": FEATURE_EPOCHS,
            "calibration_epochs": CALIBRATION_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "feature_raw_indices_inclusive": [1, 137],
            "calibration_raw_indices_inclusive": [1, 77],
            "heldout_raw_indices_inclusive": [78, 137],
        },
        "coordinate": {
            "core_phase": ["L1C", "L2W"],
            "ionosphere_free_coefficients": [2.5457277801631601, -1.5457277801631601],
            "order": "(GOLD_G22-GOLD_G30)-(NLIB_G22-NLIB_G30)",
            "unit": "METER_EQUIVALENT_CONTINUOUS_CARRIER_PHASE",
            "derivative": "NONE",
            "interpolation": "FORBIDDEN",
            "gap_bridging": "FORBIDDEN",
        },
        "measurement_admission": {
            "required": [
                "ALL_139_EPOCHS_BOTH_STATIONS",
                "L1C_L2W_ALL_FOUR_LINKS",
                "ZERO_LLI_ALL_FOUR_LINKS",
                "EXACT_30_SECOND_GRID",
                "TIME_OF_LAST_OBS_COVERS_WINDOW",
                "PRIOR_QUALIFIED_RECEIVER_CONFIGURATION_MATCHES",
            ],
            "same_path_code": {
                "fields": ["C1C", "C2W"],
                "minimum_fraction_per_link": CODE_MINIMUM_COVERAGE_FRACTION,
                "required_raw_indices": list(CODE_REQUIRED_RAW_INDICES),
                "may_adjust_score": False,
            },
            "geometry_free_second_difference_limit_m": (
                GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
            ),
            "optional": ["S1C", "S2W"],
        },
        "hypotheses": {
            "orbital": "BROADCAST_G22_RELATIVE_TO_G30",
            "prefix_affine": "ZERO_GEOMETRY_WITH_SAME_PREFIX_FIT",
            "wrong_orbits": list(ALTERNATIVE_ORBITS),
            "wrong_orbit_separations_m": ALTERNATIVE_ORBITS,
        },
        "scoring": {
            "nuisance": "CONSTANT_RATE_PREFIX_ONLY",
            "one_model_envelope_m": ONE_MODEL_ENVELOPE_M,
            "pairwise_guard_m": PAIRWISE_DECISION_GUARD_M,
            "controlling_separation_m": CONTROLLING_SEPARATION_M,
            "remaining_physical_margin_m": REMAINING_PHYSICAL_MARGIN_M,
            "suffix_refit": False,
            "free_time_phase": False,
            "threshold_change": False,
        },
        "outcomes": [
            "MEASUREMENT_INVALID",
            "NOT_DETECTABLE",
            "ORBITAL_MODEL_REPEATED_PASS_PREFERRED",
            "PREFIX_AFFINE_NULL_PREFERRED",
            "WRONG_ORBIT_G01_PREFERRED",
            "WRONG_ORBIT_G14_PREFERRED",
            "WRONG_ORBIT_G17_PREFERRED",
            "AMBIGUOUS",
        ],
        "claim_scope": {
            "positive": "TWO_DISTINCT_GOLD_NLIB_G22_G30_PASSES_PREFER_FROZEN_ORBIT",
            "forbidden": [
                "GENERAL_GNSS_IDENTITY",
                "INDEPENDENCE_FROM_SHARED_GOLD_NLIB_SYSTEMATICS",
                "CATALOG_WIDE_IDENTIFICATION",
                "UNCONSTRAINED_ORBIT_DETERMINATION",
            ],
        },
        "retry": {
            "attempts_per_locator": 1,
            "endpoint_substitution": False,
            "date_substitution": False,
            "reserve_on_failure": False,
        },
        "access": {
            "products_discovered": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
            "replication": "FORBIDDEN",
            "reserve": "FORBIDDEN",
            "next_maximum": "OFFLINE_DOY219_PREDICTION_AND_SEAL_ONLY",
        },
        "stop": "SEPARATE_REVIEW_BEFORE_ANY_DOY219_PRODUCT_DISCOVERY",
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(plan()).encode("ascii")).hexdigest()


def verify_sources(root: Path) -> tuple[Mapping[str, object], Mapping[str, object]]:
    duration_path = Path(root) / DURATION_RECEIPT_NAME
    primary_path = Path(root) / PRIMARY_OUTCOME_NAME
    if canonical_sha256(duration_path) != DURATION_RECEIPT_SHA256:
        raise RepeatedPassPlanError("DURATION_RECEIPT_CHANGED")
    if canonical_sha256(primary_path) != PRIMARY_OUTCOME_SHA256:
        raise RepeatedPassPlanError("PRIMARY_OUTCOME_CHANGED")
    duration = json.loads(duration_path.read_text(encoding="utf-8"))
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    ranking = [int(row["doy"]) for row in duration["diagnostic_date_ranking"]]
    if ranking != [220, 219, 218, 217]:
        raise RepeatedPassPlanError("PRE_OUTCOME_RANKING_CHANGED")
    if [doy for doy in ranking if doy not in CONSUMED_DOYS] != [219, 218]:
        raise RepeatedPassPlanError("REPLICATION_SELECTION_CHANGED")
    rows = {
        (int(row["doy"]), int(row["heldout_epochs"])): row
        for row in duration["duration_rows"]
    }
    replication = rows[(REPLICATION_DOY, HELDOUT_EPOCHS)]
    if replication["remaining_physical_margin_m"] != REMAINING_PHYSICAL_MARGIN_M:
        raise RepeatedPassPlanError("REPLICATION_MARGIN_CHANGED")
    if replication["wrong_orbit_null"]["controlling_alternative"] != "G01":
        raise RepeatedPassPlanError("REPLICATION_CONTROLLING_NULL_CHANGED")
    if primary.get("outcome") != "ORBITAL_MODEL_PREDICTIVELY_PREFERRED":
        raise RepeatedPassPlanError("PRIMARY_TERMINAL_RESULT_CHANGED")
    if primary.get("proof_plan_manifest_sha256") != PRIMARY_PLAN_MANIFEST_SHA256:
        raise RepeatedPassPlanError("PRIMARY_PLAN_BINDING_CHANGED")
    if primary.get("persistence", {}).get("observation_values") != 0:
        raise RepeatedPassPlanError("PRIMARY_PERSISTENCE_BOUNDARY_CHANGED")
    return duration, primary
