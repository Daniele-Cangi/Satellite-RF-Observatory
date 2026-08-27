"""Frozen observation-blind contract for one ALGO/MDO DOY223 primary.

The module binds the selected orbit geometry and the prior model-blind
qualification. It names two logical observation products but performs no
network request and has no observation decoder or value input.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


PLAN_VERSION: Final = "g22-g30-algo-mdo-doy223-primary-plan-v1"

SCREEN_RECEIPT_NAME: Final = (
    "GNSS_INDEPENDENT_PAIR_NEXT_PRIMARY_SCREEN_RECEIPT.json"
)
SCREEN_RECEIPT_SHA256: Final = (
    "2e5af124d25475900eb8b8f88535bb5ac70da10f6f2f3a796fe6f66699b330b3"
)
SCREEN_SELECTED_ROW_SHA256: Final = (
    "15b9d49ff9a35740f6fb72207bbec58ec2671d6d7ece890caaf26c10b12b0ac4"
)
SCREEN_SOURCE_COMMIT: Final = "7a5d88633fdb086590eaf29c1fad2e6b4d3ead59"

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

PRIMARY_DOY: Final = 223
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
FEATURE_EPOCHS: Final = 137
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 60
RAW_START: Final = datetime(2026, 8, 11, 5, 24, tzinfo=timezone.utc)
TARGET: Final = "G22"
REFERENCE: Final = "G30"
WRONG_ORBITS: Final = ("G01", "G14", "G17")

SCREEN_CONTROLLING_SEPARATION_M: Final = 54_990.701676848694
SCREEN_PAIRWISE_GUARD_M: Final = 3_142.1641485601226
SCREEN_REMAINING_MARGIN_M: Final = 51_848.53752828857
SCREEN_PREFIX_AFFINE_SEPARATION_M: Final = 123_441.4810635855
SCREEN_WRONG_ORBIT_SEPARATIONS_M: Final = {
    "G01": 55_330.087155858055,
    "G14": 54_990.701676848694,
    "G17": 194_596.73463905358,
}
SCREEN_MINIMUM_MODEL_ELEVATION_DEG: Final = 22.66366007669533

NAVIGATION_NAME: Final = "brdc2230.26n.gz"
NAVIGATION_COMPRESSED_BYTES: Final = 71_403
NAVIGATION_COMPRESSED_SHA256: Final = (
    "deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478"
)
NAVIGATION_UNCOMPRESSED_BYTES: Final = 298_710
NAVIGATION_UNCOMPRESSED_SHA256: Final = (
    "340bf5e84504420d6770476c8f3c9cda78722fcc283cd34385f47b77ba6f4d2e"
)

GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 137)


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    station: str
    name: str
    mirrors: tuple[str, ...]


PRODUCTS: Final = (
    ProductIdentity(
        "ALGO00CAN",
        "ALGO00CAN_R_20262230000_01D_30S_MO.crx.gz",
        (
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/223/"
            "ALGO00CAN_R_20262230000_01D_30S_MO.crx.gz",
            "https://cddis.nasa.gov/archive/gnss/data/daily/2026/223/26d/"
            "ALGO00CAN_R_20262230000_01D_30S_MO.crx.gz",
        ),
    ),
    ProductIdentity(
        "MDO100USA",
        "MDO100USA_R_20262230000_01D_30S_MO.crx.gz",
        (
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/223/"
            "MDO100USA_R_20262230000_01D_30S_MO.crx.gz",
            "https://cddis.nasa.gov/archive/gnss/data/daily/2026/223/26d/"
            "MDO100USA_R_20262230000_01D_30S_MO.crx.gz",
        ),
    ),
)


class Doy223PrimaryPlanError(ValueError):
    """A frozen geometry, qualification, or proof boundary changed."""


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
    payload = Path(path).read_bytes().replace(bytes((13, 10)), bytes((10,)))
    return sha256(payload).hexdigest()


def mapping_sha256(value: Mapping[str, object]) -> str:
    return sha256(strict_json(value).encode("ascii")).hexdigest()


def _gps(epoch: datetime) -> str:
    return epoch.isoformat(timespec="seconds").replace("+00:00", " GPS")


def _product(identity: ProductIdentity) -> dict[str, object]:
    return {
        "station": identity.station,
        "name": identity.name,
        "mirrors": list(identity.mirrors),
        "mirror_order_frozen": True,
        "logical_identity_frozen": True,
        "complete_bytes": None,
        "complete_sha256": None,
        "header_bytes_accessed": 0,
        "observation_values_accessed": 0,
    }


def plan() -> dict[str, object]:
    raw_stop = RAW_START + timedelta(seconds=(RAW_EPOCHS - 1) * STEP_S)
    feature_start = RAW_START + timedelta(seconds=STEP_S)
    feature_stop = raw_stop - timedelta(seconds=STEP_S)
    heldout_start = feature_start + timedelta(
        seconds=CALIBRATION_EPOCHS * STEP_S
    )
    result = {
        "schema": "gnss-independent-pair-doy223-primary-plan-v1",
        "plan_version": PLAN_VERSION,
        "state": "PRIMARY_PLAN_FROZEN_OBSERVATION_UNOPENED",
        "physical_question": (
            "DOES_THE_FROZEN_G22_RELATIVE_G30_BROADCAST_GEOMETRY_PREDICT_"
            "THE_HELDOUT_ALGO_MINUS_MDO_CONTINUOUS_PHASE_COORDINATE_BETTER_"
            "THAN_THE_FROZEN_PREFIX_AFFINE_AND_WRONG_ORBIT_ALTERNATIVES"
        ),
        "new_information": (
            "WHETHER_THE_G22_G30_ORBITAL_PREFERENCE_CAN_BE_OBSERVED_ON_A_"
            "NEW_ALGO_MDO_PASS_AFTER_THE_CLOSED_DOY219_TRANSPORT_OUTCOME"
        ),
        "why_existing_cannot_answer": (
            "DOY217_PROVED_CAPABILITY_ONLY_AND_DOY219_ENDED_BEFORE_ANY_"
            "MEASUREMENT_WAS_ADMITTED"
        ),
        "minimum_experiment": (
            "ONE_PREDECLARED_DOY223_ALGO_MDO_WINDOW_WITH_ONE_PREFIX_AND_ONE_"
            "HELDOUT_SUFFIX_COMPARED_TO_THE_EXISTING_FROZEN_NULLS"
        ),
        "stop_condition": "ONE_TERMINAL_OUTCOME_NO_SECOND_WINDOW",
        "source_authorities": {
            "geometry_screen": {
                "name": SCREEN_RECEIPT_NAME,
                "canonical_sha256": SCREEN_RECEIPT_SHA256,
                "selected_row_sha256": SCREEN_SELECTED_ROW_SHA256,
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
                "role": "DISTINCT_PASS_HELDOUT_PRIMARY",
                "doy": PRIMARY_DOY,
                "stations": ["ALGO00CAN", "MDO100USA"],
                "candidate_station_roots": [
                    "ALGO00CAN_40104M002",
                    "MDO100USA_40442M012",
                ],
                "products": [_product(product) for product in PRODUCTS],
                "product_identity_state": (
                    "FROZEN_LOGICAL_PRODUCT_AND_MIRROR_SET_COMPLETE_HASH_"
                    "UNKNOWN_UNTIL_MATERIALIZATION"
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
        "navigation_authority": {
            "name": NAVIGATION_NAME,
            "provider": "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
            "rinex_version": "2.11",
            "compressed_bytes": NAVIGATION_COMPRESSED_BYTES,
            "compressed_sha256": NAVIGATION_COMPRESSED_SHA256,
            "uncompressed_bytes": NAVIGATION_UNCOMPRESSED_BYTES,
            "uncompressed_sha256": NAVIGATION_UNCOMPRESSED_SHA256,
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
            "minimum_model_elevation_deg": (
                SCREEN_MINIMUM_MODEL_ELEVATION_DEG
            ),
            "threshold_change_after_freeze": False,
        },
        "transport_materialization": {
            "state_before_complete_hash": "MATERIALIZING",
            "predeclared_mirror_set_only": True,
            "mirror_order_frozen": True,
            "max_attempts_per_mirror": 2,
            "max_total_attempts_per_product": 4,
            "maximum_wall_clock_s_per_product": 900,
            "connect_timeout_s": 30,
            "idle_timeout_s": 180,
            "partial_file_location": "QUARANTINE_ONLY",
            "resume_allowed": True,
            "resume_requires_same_mirror_and_stable_validator": True,
            "cross_mirror_partial_append": False,
            "restart_with_next_frozen_mirror_within_budget": True,
            "complete_hash_before_header_or_decode": True,
            "retry_may_change_product_date_window_or_threshold": False,
            "first_complete_hash_defines_artifact_identity": True,
            "network_attempts_after_both_complete_hashes": 0,
            "retry_after_header_or_decode_begins": False,
            "retry_after_measurement_admission": False,
            "scientific_retry_or_second_window": False,
        },
        "outcomes": [
            "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "ARTIFACT_IDENTITY_CONFLICT",
            "PRIMARY_SOFTWARE_FAILURE",
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
        "access_at_freeze": {
            "observation_locator_requests": 0,
            "descriptive_head_requests": 0,
            "observation_headers_opened": 0,
            "observation_payload_bytes": 0,
            "observation_values": 0,
        },
        "persistence": {
            "observation_values": "EPHEMERAL_RAM_ONLY",
            "persisted_observation_values": 0,
            "persisted_compressed_or_decoded_artifacts": 0,
        },
        "next_maximum": (
            "OFFLINE_EXACT_HASH_DOY223_PREDICTION_SEAL_BEFORE_ANY_"
            "OBSERVATION_REQUEST"
        ),
        "stop": "STOP_BEFORE_ANY_OBSERVATION_REQUEST_FOR_REVIEW",
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(plan()).encode("ascii")).hexdigest()


def verify_sources(
    root: Path,
) -> tuple[Mapping[str, object], Mapping[str, object]]:
    base = Path(root)
    screen_path = base / SCREEN_RECEIPT_NAME
    qualification_path = base / QUALIFICATION_OUTCOME_NAME
    if canonical_sha256(screen_path) != SCREEN_RECEIPT_SHA256:
        raise Doy223PrimaryPlanError("GEOMETRY_SCREEN_CHANGED")
    if canonical_sha256(qualification_path) != QUALIFICATION_OUTCOME_SHA256:
        raise Doy223PrimaryPlanError("QUALIFICATION_OUTCOME_CHANGED")
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    qualification = json.loads(qualification_path.read_text(encoding="utf-8"))
    selected = screen.get("selected")
    if not isinstance(selected, dict):
        raise Doy223PrimaryPlanError("DOY223_SELECTION_MISSING")
    if mapping_sha256(selected) != SCREEN_SELECTED_ROW_SHA256:
        raise Doy223PrimaryPlanError("DOY223_SELECTION_CHANGED")
    if (
        screen.get("outcome") != "NEXT_PRIMARY_GEOMETRY_SELECTED"
        or selected.get("doy") != PRIMARY_DOY
        or selected.get("raw_start_gps") != _gps(RAW_START)
        or selected.get("controlling_null") != "WRONG_ORBIT_G14"
        or selected.get("controlling_heldout_separation_m")
        != SCREEN_CONTROLLING_SEPARATION_M
        or selected.get("pairwise_comparison_envelope_m")
        != SCREEN_PAIRWISE_GUARD_M
        or selected.get("remaining_physical_margin_m")
        != SCREEN_REMAINING_MARGIN_M
        or any(screen.get("observation_access", {}).values())
    ):
        raise Doy223PrimaryPlanError("DOY223_GEOMETRY_CHANGED")
    if (
        qualification.get("outcome")
        != "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
        or qualification.get("source_commit") != QUALIFICATION_SOURCE_COMMIT
        or qualification.get("manifest_sha256")
        != QUALIFICATION_MANIFEST_SHA256
        or any(qualification.get("future_primary_doy219_access", {}).values())
    ):
        raise Doy223PrimaryPlanError("QUALIFICATION_AUTHORITY_CHANGED")
    return screen, qualification
