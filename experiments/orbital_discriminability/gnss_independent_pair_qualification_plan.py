"""Offline proof boundary for ALGO/MDO measurement qualification.

The module freezes one model-blind qualification role after metadata-only
admission. It has no transport, decoder or observation-value input surface and
does not name or discover a DOY 219 primary product.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping


PLAN_VERSION: Final = "g22-g30-algo-mdo-doy217-qualification-plan-v1"
SCREEN_RECEIPT_NAME: Final = "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
SCREEN_RECEIPT_SHA256: Final = (
    "24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c"
)
SCREEN_SOURCE_COMMIT: Final = (
    "5df12420b33c27b76748a7861ead69a9efffec70"
)
METADATA_SNAPSHOT_DATE: Final = "2026-08-25"

QUALIFICATION_DOY: Final = 217
PRIMARY_GEOMETRY_DOY: Final = 219
STEP_S: Final = 30
RAW_EPOCHS: Final = 139
FEATURE_EPOCHS: Final = 137
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 60
QUALIFICATION_RAW_START: Final = datetime(
    2026, 8, 5, 5, 54, 0, tzinfo=timezone.utc
)
PRIMARY_GEOMETRY_RAW_START: Final = datetime(
    2026, 8, 7, 5, 46, 0, tzinfo=timezone.utc
)

TARGET: Final = "G22"
REFERENCE: Final = "G30"
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
OPTIONAL_DIAGNOSTIC: Final = ("S1C", "S2W")
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 137)
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244


@dataclass(frozen=True, slots=True)
class ProductMetadata:
    station: str
    name: str
    url: str
    http_status: int
    content_length: int
    etag: str
    last_modified: str
    body_bytes_accessed: int = 0


@dataclass(frozen=True, slots=True)
class HardwareRoot:
    station: str
    domes: str
    agency: str
    primary_data_center: str
    receiver_type: str
    receiver_serial: str
    receiver_firmware: str
    receiver_installed: str
    antenna_type: str
    antenna_serial: str
    antenna_installed: str
    clock: str


PRODUCTS: Final = (
    ProductMetadata(
        "ALGO00CAN",
        "ALGO00CAN_R_20262170000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/217/"
        "ALGO00CAN_R_20262170000_01D_30S_MO.crx.gz",
        200,
        4_305_409,
        '"41b201-6586b10a8ad64"',
        "Fri, 07 Aug 2026 01:38:44 GMT",
    ),
    ProductMetadata(
        "MDO100USA",
        "MDO100USA_R_20262170000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/217/"
        "MDO100USA_R_20262170000_01D_30S_MO.crx.gz",
        200,
        3_560_934,
        '"3655e6-65856e80dc6c3"',
        "Thu, 06 Aug 2026 01:35:43 GMT",
    ),
)

ROOTS: Final = (
    HardwareRoot(
        "ALGO00CAN",
        "40104M002",
        "NRCAN_CANADIAN_GEODETIC_SURVEY",
        "CDDIS",
        "SEPT_POLARX5",
        "3015995",
        "5.3.2",
        "2026-03-25T19:19Z",
        "AOAD/M_T_NONE",
        "303",
        "2012-12-20T17:00Z",
        "INTERNAL",
    ),
    HardwareRoot(
        "MDO100USA",
        "40442M012",
        "MCDONALD_OBSERVATORY_WITH_JPL_OPERATIONAL_CONTACT",
        "JPL",
        "SEPT_POLARX5",
        "3013421",
        "5.7.0",
        "2026-03-18T14:57Z",
        "JAVRINGANT_DM_SCIS",
        "02134",
        "2020-10-31T00:00Z",
        "INTERNAL",
    ),
)

QUALIFICATION_MINIMUM_ELEVATION_DEG: Final = {
    "ALGO00CAN": {
        "G22": 41.473463389,
        "G30": 32.325449829,
        "G01": 50.820111376,
        "G14": 59.871452741,
        "G17": 39.976328514,
    },
    "MDO100USA": {
        "G22": 51.469239905,
        "G30": 51.146998618,
        "G01": 21.424674645,
        "G14": 57.223583167,
        "G17": 70.992058270,
    },
}


class IndependentPairPlanError(ValueError):
    """The frozen screen, metadata selection or proof boundary changed."""


def strict_json(value: object, *, pretty: bool = False) -> str:
    """Serialize a finite plan deterministically."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    """Hash text after the repository CRLF-to-LF convention."""

    payload = Path(path).read_bytes().replace(bytes((13, 10)), bytes((10,)))
    return sha256(payload).hexdigest()


def _gps(epoch: datetime) -> str:
    """Render a timezone-aware instant as a GPS-labelled grid coordinate."""

    return epoch.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", " GPS"
    )


def candidate_assessment() -> list[dict[str, object]]:
    """Return the frozen metadata-only disposition of the screen shortlist."""

    return [
        {
            "screen_rank": 1,
            "pair": ["DRAO00CAN", "WES200USA"],
            "remaining_physical_margin_m": 92649.07149262926,
            "state": "CAPABILITY_REJECTED",
            "reason": "WES_RINEX3_REQUIRED_SIGNAL_IDENTITY_UNAVAILABLE",
            "evidence": {
                "wes_primary_feed": "RINEX_V2_ONLY",
                "wes_primary_data_center": "NOAA_CORS",
                "rinex3_head_status_by_doy": {
                    "216": 404,
                    "217": 404,
                    "218": 404,
                },
                "payload_bytes_accessed": 0,
            },
            "forbidden_repair": (
                "POST_HOC_RINEX2_L1_L2_TO_L1C_L2W_SIGNAL_MAPPING"
            ),
        },
        {
            "screen_rank": 2,
            "pair": ["DRAO00CAN", "ALGO00CAN"],
            "remaining_physical_margin_m": 75312.29846400935,
            "state": "CAPABILITY_METADATA_AVAILABLE_NOT_SELECTED",
            "reason": (
                "LARGER_MARGIN_BUT_MORE_SHARED_CANADIAN_FEDERAL_"
                "INSTITUTIONAL_LINEAGE_THAN_ALGO_MDO"
            ),
            "rinex3_doy217_head_status": [200, 200],
            "payload_bytes_accessed": 0,
        },
        {
            "screen_rank": 3,
            "pair": ["ALGO00CAN", "MDO100USA"],
            "remaining_physical_margin_m": 47828.04192442695,
            "state": "QUALIFICATION_ROLE_SELECTED",
            "reason": (
                "POSITIVE_COMPLETE_MARGIN_PLUS_DISTINCT_DOMES_SERIALS_"
                "AGENCIES_AND_PRIMARY_DATA_CENTERS"
            ),
            "rinex3_doy217_head_status": [200, 200],
            "payload_bytes_accessed": 0,
        },
    ]


def plan() -> dict[str, object]:
    """Build and validate the complete offline qualification proof boundary."""

    qualification_stop = QUALIFICATION_RAW_START + timedelta(
        seconds=(RAW_EPOCHS - 1) * STEP_S
    )
    primary_geometry_stop = PRIMARY_GEOMETRY_RAW_START + timedelta(
        seconds=(RAW_EPOCHS - 1) * STEP_S
    )
    result = {
        "schema": "gnss-independent-pair-qualification-plan-v1",
        "plan_version": PLAN_VERSION,
        "physical_question": (
            "CAN_ALGO_MDO_PRESERVE_THE_FROZEN_G22_RELATIVE_G30_"
            "CONTINUOUS_PHASE_COORDINATE_REQUIRED_FOR_A_HELDOUT_STATION_TEST"
        ),
        "new_information": (
            "WHETHER_THE_ORBITALLY_DISCRIMINATIVE_ALGO_MDO_GEOMETRY_HAS_A_"
            "MEASUREMENT_VALID_MODEL_BLIND_PHASE_PATH"
        ),
        "source_screen": {
            "receipt": SCREEN_RECEIPT_NAME,
            "canonical_sha256": SCREEN_RECEIPT_SHA256,
            "source_commit": SCREEN_SOURCE_COMMIT,
            "outcome": "INDEPENDENT_PAIR_GEOMETRY_SHORTLISTED",
        },
        "metadata_snapshot_date": METADATA_SNAPSHOT_DATE,
        "candidate_assessment": candidate_assessment(),
        "selection_rule": [
            "REJECT_IF_REQUIRED_RINEX_SIGNAL_IDENTITY_IS_UNAVAILABLE",
            "REQUIRE_STRICT_POSITIVE_COMPLETE_PHYSICAL_MARGIN",
            "PREFER_DISTINCT_HARDWARE_ORGANISATION_AND_DATA_LINEAGE",
            "DO_NOT_INSPECT_OBSERVATION_BODY_OR_VALUE",
        ],
        "selected_roots": [asdict(root) for root in ROOTS],
        "qualification": {
            "role": "MODEL_BLIND_MEASUREMENT_CAPABILITY_ONLY",
            "doy": QUALIFICATION_DOY,
            "stations": [root.station for root in ROOTS],
            "products": [asdict(product) for product in PRODUCTS],
            "product_identity_state": (
                "LOCATOR_AND_HTTP_METADATA_ONLY_COMPLETE_HASH_UNKNOWN"
            ),
            "raw_start_gps": _gps(QUALIFICATION_RAW_START),
            "raw_stop_gps": _gps(qualification_stop),
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "minimum_elevation_deg_by_station_and_model": (
                QUALIFICATION_MINIMUM_ELEVATION_DEG
            ),
            "minimum_joint_model_elevation_deg": min(
                value
                for station in QUALIFICATION_MINIMUM_ELEVATION_DEG.values()
                for value in station.values()
            ),
            "navigation_provenance": {
                "name": "BRDM00DLR_S_20262170000_01D_MN.rnx",
                "gzip_bytes": 1_352_449,
                "gzip_sha256": (
                    "8cbfca665122e6920f5f9ca224de9f83f267144d963240b0c3de9d36cde0ee8e"
                ),
                "raw_bytes": 8_362_647,
                "raw_sha256": (
                    "40c5c1619f6d5cb1a9cb00b33025529d81f826ee1e9fb60738f0193e992325b9"
                ),
                "role": "WINDOW_VISIBILITY_REGRESSION_ONLY",
            },
        },
        "future_primary_geometry": {
            "doy": PRIMARY_GEOMETRY_DOY,
            "stations": [root.station for root in ROOTS],
            "raw_start_gps": _gps(PRIMARY_GEOMETRY_RAW_START),
            "raw_stop_gps": _gps(primary_geometry_stop),
            "product_locators": [],
            "product_discovery": "FORBIDDEN",
            "artifact_identity": "UNSELECTED_UNDISCOVERED_SEALED",
            "access": "FORBIDDEN",
        },
        "measurement_coordinate": {
            "target": TARGET,
            "reference": REFERENCE,
            "core_phase": list(CORE_PHASE),
            "ionosphere_free_coefficients": [
                2.5457277801631601,
                -1.5457277801631601,
            ],
            "station_satellite_order": (
                "(ALGO_G22_MINUS_ALGO_G30)_MINUS_"
                "(MDO1_G22_MINUS_MDO1_G30)"
            ),
            "unit": "METER_EQUIVALENT_CONTINUOUS_CARRIER_PHASE",
            "derivative": "NONE",
            "interpolation": "FORBIDDEN",
            "gap_bridging": "FORBIDDEN",
        },
        "qualification_clauses": {
            "header": [
                "RINEX_3_OR_4_EXPLICIT_OBSERVABLE_IDENTITY",
                "EXPECTED_RECEIVER_SERIAL_FIRMWARE_AND_ANTENNA",
                "TIME_OF_FIRST_OBS_COVERS_FROZEN_START",
                "TIME_OF_LAST_OBS_COVERS_FROZEN_STOP",
                "GPS_TIME_SYSTEM_AND_EXACT_30_SECOND_GRID",
            ],
            "core": [
                "ALL_139_EPOCHS_PRESENT_ON_BOTH_STATIONS",
                "L1C_AND_L2W_PRESENT_ON_ALL_FOUR_LINKS",
                "ZERO_LLI_ON_BOTH_PHASE_FIELDS_ALL_FOUR_LINKS",
                "NO_INTERPOLATION_OR_GAP_BRIDGING",
            ],
            "geometry_free_health": {
                "maximum_absolute_second_difference_m": (
                    GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                ),
                "orbital_model_available": False,
                "may_fit_or_score_orbit": False,
            },
            "same_path_code": {
                "fields": list(SAME_PATH_CODE),
                "minimum_presence_fraction_per_link": (
                    CODE_MINIMUM_COVERAGE_FRACTION
                ),
                "required_raw_indices": list(CODE_REQUIRED_RAW_INDICES),
                "may_adjust_phase": False,
            },
            "optional_diagnostic": list(OPTIONAL_DIAGNOSTIC),
        },
        "future_execution_boundary": {
            "complete_hash_before_decode": True,
            "maximum_transport_attempts_per_locator": 2,
            "resume_allowed_only_before_complete_hash": True,
            "model_or_prediction_available_to_executor": False,
            "decoded_values": "EPHEMERAL_RAM_ONLY",
            "persisted_observation_values": 0,
            "persisted_compressed_artifacts": 0,
            "failure_selects_fallback_pair_or_date": False,
        },
        "qualification_outcomes": [
            "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED",
            "GNSS_INDEPENDENT_PAIR_QUALIFICATION_FAILED",
            "GNSS_INDEPENDENT_PAIR_ARTIFACT_MATERIALIZATION_FAILED",
            "GNSS_INDEPENDENT_PAIR_DESCRIPTION_ERROR",
        ],
        "access_at_freeze": {
            "qualification_observation_body_bytes": 0,
            "qualification_headers_opened": 0,
            "qualification_values_accessed": 0,
            "primary_product_locators": 0,
            "primary_headers_opened": 0,
            "primary_payload_bytes": 0,
            "primary_values_accessed": 0,
        },
        "next_maximum": (
            "SEPARATELY_AUTHORISED_COMPLETE_MATERIALIZATION_AND_MODEL_BLIND_"
            "QUALIFICATION_OF_THE_TWO_DOY217_PRODUCTS_ONLY"
        ),
        "stop_condition": (
            "STOP_BEFORE_ANY_OBSERVATION_BODY_ACCESS_FOR_PLAN_REVIEW"
        ),
        "new_gate_created": False,
        "generic_framework_created": False,
    }
    _validate_plan(result)
    strict_json(result)
    return result


def _validate_plan(value: Mapping[str, object]) -> None:
    """Reject accidental fallback, primary locator or observation access."""

    qualification = value["qualification"]
    primary = value["future_primary_geometry"]
    access = value["access_at_freeze"]
    if [item["station"] for item in qualification["products"]] != [
        "ALGO00CAN",
        "MDO100USA",
    ]:
        raise IndependentPairPlanError("QUALIFICATION_PRODUCTS_CHANGED")
    if any("/217/" not in item["url"] for item in qualification["products"]):
        raise IndependentPairPlanError("QUALIFICATION_DATE_CHANGED")
    if primary["product_locators"] or primary["product_discovery"] != "FORBIDDEN":
        raise IndependentPairPlanError("PRIMARY_PRODUCT_ENTERED_PLAN")
    if any(int(item) != 0 for item in access.values()):
        raise IndependentPairPlanError("OBSERVATION_ACCESS_BEFORE_REVIEW")
    if value["future_execution_boundary"]["failure_selects_fallback_pair_or_date"]:
        raise IndependentPairPlanError("POST_FAILURE_FALLBACK_ENABLED")


def manifest_sha256() -> str:
    """Return the immutable plan hash."""

    return sha256(strict_json(plan()).encode("ascii")).hexdigest()


def verify_screen_receipt(path: Path) -> Mapping[str, object]:
    """Verify that selection descends from the exact observation-blind screen."""

    if Path(path).name != SCREEN_RECEIPT_NAME:
        raise IndependentPairPlanError("SCREEN_RECEIPT_NAME_CHANGED")
    if canonical_sha256(path) != SCREEN_RECEIPT_SHA256:
        raise IndependentPairPlanError("SCREEN_RECEIPT_CHANGED")
    receipt = json.loads(
        Path(path).read_text(encoding="utf-8"),
        parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
    )
    if receipt.get("outcome") != "INDEPENDENT_PAIR_GEOMETRY_SHORTLISTED":
        raise IndependentPairPlanError("SCREEN_OUTCOME_CHANGED")
    if any(receipt.get("observation_access", {}).values()):
        raise IndependentPairPlanError("SCREEN_USED_OBSERVATION")
    shortlist = [item["station_pair"] for item in receipt["shortlist"]]
    if shortlist != [
        ["DRAO00CAN", "WES200USA"],
        ["DRAO00CAN", "ALGO00CAN"],
        ["ALGO00CAN", "MDO100USA"],
    ]:
        raise IndependentPairPlanError("SCREEN_SHORTLIST_CHANGED")
    return receipt


def main() -> None:
    """Print the strict plan without performing I/O beyond stdout."""

    print(strict_json(plan(), pretty=True))


if __name__ == "__main__":
    main()
