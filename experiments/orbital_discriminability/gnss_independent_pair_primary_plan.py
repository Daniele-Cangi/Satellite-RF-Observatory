"""Frozen observation-blind plan for one ALGO/MDO DOY219 primary.

This module names the two products and freezes the scientific comparison.  It
has no transport, RINEX decoder, observation-value input, or fallback search.
HTTP HEAD metadata is descriptive availability evidence, not artifact identity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


PLAN_VERSION: Final = "g22-g30-algo-mdo-doy219-primary-plan-v1"

SCREEN_RECEIPT_NAME: Final = "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
SCREEN_RECEIPT_SHA256: Final = (
    "24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c"
)
SCREEN_ROW_SHA256: Final = (
    "b3d7e99f188fcb2488a78d3035e90ab56b714a197bc86148e67079a7e8f4b90f"
)
SCREEN_SOURCE_COMMIT: Final = "5df12420b33c27b76748a7861ead69a9efffec70"

QUALIFICATION_OUTCOME_NAME: Final = (
    "GNSS_INDEPENDENT_PAIR_QUALIFICATION_OUTCOME.json"
)
QUALIFICATION_OUTCOME_SHA256: Final = (
    "cf26a411a0b77b79e951a21516c06333d26e7cc879f1dff09ce2e6eaa2fe3090"
)
QUALIFICATION_SOURCE_COMMIT: Final = (
    "6410ab195b2b6b535bcb57c357fce5300e8fffae"
)
QUALIFICATION_MANIFEST_SHA256: Final = (
    "7aee72bac1660518769240eca4fd627067877fba0cda0a56519e514bd51d7e24"
)

PRIMARY_DOY: Final = 219
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
FEATURE_EPOCHS: Final = 137
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 60
RAW_START: Final = datetime(2026, 8, 7, 5, 46, tzinfo=timezone.utc)
TARGET: Final = "G22"
REFERENCE: Final = "G30"
WRONG_ORBITS: Final = ("G01", "G14", "G17")

SCREEN_CONTROLLING_SEPARATION_M: Final = 51_370.2989916536
SCREEN_PAIRWISE_GUARD_M: Final = 3_542.2570672266515
SCREEN_REMAINING_MARGIN_M: Final = 47_828.04192442695
SCREEN_PREFIX_AFFINE_SEPARATION_M: Final = 148_023.9791073685
SCREEN_WRONG_ORBIT_SEPARATIONS_M: Final = {
    "G01": 62_887.71439189743,
    "G14": 51_370.2989916536,
    "G17": 192_076.63832227292,
}
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 137)


@dataclass(frozen=True, slots=True)
class ProductLocator:
    station: str
    name: str
    url: str
    head_status: int
    head_content_length: int
    head_etag: str
    head_last_modified: str
    head_requests: int = 1
    header_bytes_accessed: int = 0
    payload_bytes_accessed: int = 0
    observation_values_accessed: int = 0


PRODUCTS: Final = (
    ProductLocator(
        "ALGO00CAN",
        "ALGO00CAN_R_20262190000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/219/"
        "ALGO00CAN_R_20262190000_01D_30S_MO.crx.gz",
        200,
        4_320_264,
        '"41ec08-658934a2a4a08"',
        "Sun, 09 Aug 2026 01:38:07 GMT",
    ),
    ProductLocator(
        "MDO100USA",
        "MDO100USA_R_20262190000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/219/"
        "MDO100USA_R_20262190000_01D_30S_MO.crx.gz",
        200,
        3_559_665,
        '"3650f1-658855380e7c4"',
        "Sat, 08 Aug 2026 08:58:35 GMT",
    ),
)


class IndependentPairPrimaryPlanError(ValueError):
    """A frozen authority, geometry row, or proof boundary changed."""


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


def mapping_sha256(value: Mapping[str, object]) -> str:
    return sha256(strict_json(value).encode("ascii")).hexdigest()


def _gps(epoch: datetime) -> str:
    return epoch.isoformat(timespec="seconds").replace("+00:00", " GPS")


def plan() -> dict[str, object]:
    raw_stop = RAW_START + timedelta(seconds=(RAW_EPOCHS - 1) * STEP_S)
    feature_start = RAW_START + timedelta(seconds=STEP_S)
    feature_stop = raw_stop - timedelta(seconds=STEP_S)
    heldout_start = feature_start + timedelta(
        seconds=CALIBRATION_EPOCHS * STEP_S
    )
    result = {
        "schema": "gnss-independent-pair-primary-plan-v1",
        "plan_version": PLAN_VERSION,
        "state": "PRIMARY_PLAN_FROZEN_OBSERVATION_UNOPENED",
        "physical_question": (
            "DOES_THE_FROZEN_G22_RELATIVE_G30_BROADCAST_GEOMETRY_PREDICT_"
            "THE_HELDOUT_ALGO_MINUS_MDO_CONTINUOUS_PHASE_COORDINATE_BETTER_"
            "THAN_THE_FROZEN_PREFIX_AFFINE_AND_WRONG_ORBIT_ALTERNATIVES"
        ),
        "new_information": (
            "WHETHER_THE_PRIOR_GOLD_NLIB_RESULT_GENERALIZES_TO_TWO_DISTINCT_"
            "QUALIFIED_RECEIVER_ANTENNA_ORGANISATION_AND_INGEST_ROOTS"
        ),
        "why_existing_cannot_answer": (
            "DOY217_ALGO_MDO_ESTABLISHES_MEASUREMENT_CAPABILITY_ONLY_AND_"
            "GOLD_NLIB_REUSES_DIFFERENT_OBSERVER_ROOTS"
        ),
        "source_authorities": {
            "geometry_screen": {
                "name": SCREEN_RECEIPT_NAME,
                "canonical_sha256": SCREEN_RECEIPT_SHA256,
                "selected_row_sha256": SCREEN_ROW_SHA256,
                "source_commit": SCREEN_SOURCE_COMMIT,
            },
            "model_blind_qualification": {
                "name": QUALIFICATION_OUTCOME_NAME,
                "canonical_sha256": QUALIFICATION_OUTCOME_SHA256,
                "outcome": "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED",
                "source_commit": QUALIFICATION_SOURCE_COMMIT,
                "manifest_sha256": QUALIFICATION_MANIFEST_SHA256,
            },
        },
        "roles": {
            "primary": {
                "role": "DISTINCT_ROOT_HELDOUT_PRIMARY",
                "doy": PRIMARY_DOY,
                "stations": ["ALGO00CAN", "MDO100USA"],
                "candidate_station_roots": [
                    "ALGO00CAN_40104M002",
                    "MDO100USA_40442M012",
                ],
                "products": [asdict(product) for product in PRODUCTS],
                "product_identity_state": (
                    "FROZEN_LOCATOR_AND_DESCRIPTIVE_HEAD_FULL_HASH_UNKNOWN_"
                    "UNTIL_SINGLE_FUTURE_MATERIALIZATION"
                ),
                "raw_start_gps": _gps(RAW_START),
                "raw_stop_gps": _gps(raw_stop),
                "feature_start_gps": _gps(feature_start),
                "feature_stop_gps": _gps(feature_stop),
                "heldout_start_gps": _gps(heldout_start),
                "access": "SEALED_UNAUTHORIZED",
            },
            "fallback_or_reserve": None,
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
            "ionosphere_free_coefficients": [
                2.5457277801631601,
                -1.5457277801631601,
            ],
            "order": (
                "(ALGO_G22_MINUS_ALGO_G30)_MINUS_"
                "(MDO1_G22_MINUS_MDO1_G30)"
            ),
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
                "DOY217_QUALIFIED_RECEIVER_ANTENNA_CONFIGURATION_MATCHES",
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
            "wrong_orbits": list(WRONG_ORBITS),
        },
        "scoring": {
            "nuisance": "CONSTANT_AND_RATE_FIT_ON_CALIBRATION_PREFIX_ONLY",
            "suffix_refit": False,
            "free_time_phase": False,
            "same_grid_and_transform_for_all_hypotheses": True,
            "screen_prefix_affine_separation_m": (
                SCREEN_PREFIX_AFFINE_SEPARATION_M
            ),
            "screen_wrong_orbit_separations_m": (
                SCREEN_WRONG_ORBIT_SEPARATIONS_M
            ),
            "screen_controlling_null": "WRONG_ORBIT_G14",
            "screen_controlling_separation_m": (
                SCREEN_CONTROLLING_SEPARATION_M
            ),
            "pairwise_decision_guard_m": SCREEN_PAIRWISE_GUARD_M,
            "remaining_physical_margin_m": SCREEN_REMAINING_MARGIN_M,
            "threshold_change_after_freeze": False,
        },
        "outcomes": [
            "MEASUREMENT_INVALID",
            "NOT_DETECTABLE",
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "PREFIX_AFFINE_NULL_PREFERRED",
            "WRONG_ORBIT_G01_PREFERRED",
            "WRONG_ORBIT_G14_PREFERRED",
            "WRONG_ORBIT_G17_PREFERRED",
            "AMBIGUOUS",
        ],
        "claim_scope": {
            "positive": (
                "THE_FROZEN_G22_RELATIVE_G30_MODEL_PREDICTS_ONE_HELDOUT_"
                "ALGO_MDO_COORDINATE_BETTER_THAN_THE_FROZEN_NULLS"
            ),
            "forbidden": [
                "UNCONSTRAINED_ORBIT_DETERMINATION",
                "CATALOG_WIDE_IDENTITY",
                "GNSS_GENERALIZATION_BEYOND_THIS_PAIR_AND_WINDOW",
                "INDEPENDENCE_FROM_ALL_SHARED_GNSS_SYSTEMATICS",
            ],
        },
        "future_materialization": {
            "attempts_per_locator": 1,
            "complete_hash_before_header_or_decode": True,
            "head_metadata_is_artifact_identity": False,
            "endpoint_substitution": False,
            "date_substitution": False,
            "fallback_product": False,
            "retry_after_plan_freeze": False,
            "observation_values": "EPHEMERAL_RAM_ONLY",
            "persisted_observation_values": 0,
            "persisted_compressed_or_decoded_artifacts": 0,
        },
        "access_at_freeze": {
            "descriptive_head_requests": 2,
            "observation_headers_opened": 0,
            "observation_payload_bytes": 0,
            "observation_values": 0,
        },
        "next_maximum": (
            "OFFLINE_EXACT_HASH_NAVIGATION_PREDICTION_SEAL_BEFORE_ANY_"
            "PRIMARY_HEADER_OR_PAYLOAD_ACCESS"
        ),
        "stop": "STOP_BEFORE_PRIMARY_HEADER_OR_PAYLOAD_ACCESS_FOR_REVIEW",
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(plan()).encode("ascii")).hexdigest()


def verify_sources(root: Path) -> tuple[Mapping[str, object], Mapping[str, object]]:
    base = Path(root)
    screen_path = base / SCREEN_RECEIPT_NAME
    qualification_path = base / QUALIFICATION_OUTCOME_NAME
    if canonical_sha256(screen_path) != SCREEN_RECEIPT_SHA256:
        raise IndependentPairPrimaryPlanError("GEOMETRY_SCREEN_CHANGED")
    if canonical_sha256(qualification_path) != QUALIFICATION_OUTCOME_SHA256:
        raise IndependentPairPrimaryPlanError("QUALIFICATION_OUTCOME_CHANGED")
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    rows = [
        row
        for row in screen.get("evaluated_pairs", [])
        if row.get("station_pair") == ["ALGO00CAN", "MDO100USA"]
    ]
    if len(rows) != 1 or mapping_sha256(rows[0]) != SCREEN_ROW_SHA256:
        raise IndependentPairPrimaryPlanError("ALGO_MDO_GEOMETRY_ROW_CHANGED")
    row = rows[0]
    if (
        row.get("controlling_null") != "WRONG_ORBIT_G14"
        or row.get("controlling_heldout_separation_m")
        != SCREEN_CONTROLLING_SEPARATION_M
        or row.get("pairwise_comparison_envelope_m") != SCREEN_PAIRWISE_GUARD_M
        or row.get("remaining_physical_margin_m") != SCREEN_REMAINING_MARGIN_M
        or not row.get("admissible_geometry")
    ):
        raise IndependentPairPrimaryPlanError("ALGO_MDO_GEOMETRY_CHANGED")
    if (
        qualification.get("outcome")
        != "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
        or qualification.get("source_commit") != QUALIFICATION_SOURCE_COMMIT
        or qualification.get("manifest_sha256")
        != QUALIFICATION_MANIFEST_SHA256
        or any(qualification.get("future_primary_doy219_access", {}).values())
    ):
        raise IndependentPairPrimaryPlanError("QUALIFICATION_AUTHORITY_CHANGED")
    if any(product.payload_bytes_accessed for product in PRODUCTS):
        raise IndependentPairPrimaryPlanError("PRIMARY_PAYLOAD_WAS_ACCESSED")
    return screen, qualification
