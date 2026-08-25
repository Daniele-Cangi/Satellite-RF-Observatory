"""Observation-blind screen for a station pair disjoint from GOLD/NLIB.

The only physical input is the exact-hash DOY 219 broadcast-navigation
authority already used by the frozen repeated-pass experiment. The bounded
station metadata set is frozen from official IGS station pages and logs.
Observation products, locators, headers and values are not accepted.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import timedelta
from hashlib import sha256
import importlib.metadata
import json
from math import sin
from pathlib import Path
import platform
import subprocess
import sys
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as envelope,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_phase_quotient_spike as phase,
)
from experiments.orbital_discriminability import (
    gnss_phase_repeated_pass as repeated,
)
from experiments.orbital_discriminability import (
    gnss_phase_repeated_pass_plan as frozen,
)


SCREEN_VERSION: Final = "g22-g30-independent-station-pair-screen-v1"
RECEIPT_NAME: Final = "GNSS_PHASE_INDEPENDENT_PAIR_SCREEN_RECEIPT.json"
OUTCOME_SHORTLISTED: Final = "INDEPENDENT_PAIR_GEOMETRY_SHORTLISTED"
OUTCOME_NONE: Final = "NO_INDEPENDENT_PAIR_GEOMETRY_ADMITTED"
METADATA_SNAPSHOT_DATE: Final = "2026-08-25"
MODEL_SATELLITES: Final = ("G22", "G30", "G01", "G14", "G17")
WRONG_ORBITS: Final = ("G01", "G14", "G17")
SHORTLIST_SIZE: Final = 3


@dataclass(frozen=True, slots=True)
class CandidateStation:
    station_id: str
    latitude_deg: float
    longitude_deg: float
    height_m: float
    domes: str
    receiver: str
    antenna: str
    equipment_effective: str
    station_page_url: str
    station_page_bytes: int
    station_page_sha256: str
    station_log_url: str
    station_log_bytes: int
    station_log_sha256: str
    station_log_prepared: str


CANDIDATES: Final = (
    CandidateStation(
        "DRAO00CAN",
        49.322600,
        -119.625000,
        542.0,
        "40105M002",
        "SEPT POLARX5 - 5.2.0",
        "TWIVC6050 - SCIS",
        "2021-09-02",
        "https://network.igs.org/DRAO00CAN",
        54_069,
        "fd8332bca07c76c4223401ea72887d444d241587a59bdb372679d4c1ff9d58ef",
        "https://network.igs.org/api/public/download/DRAO00CAN.log?lower_case=1",
        49_365,
        "2d738f85955f5896c999ed5c1cd42c034b825ccce1e153becc24210a015f9d3d",
        "2021-09-10",
    ),
    CandidateStation(
        "WES200USA",
        42.613336,
        -71.493328,
        85.0,
        "40440S020",
        "TRIMBLE ALLOY - 6.50",
        "TWIVC6150 - SCIS",
        "2026-07-15",
        "https://network.igs.org/WES200USA",
        43_414,
        "b130f9cdb1cea3702d14d9d674a75cbe5133aca0fc09bc67f95d9d5841f1e7a5",
        "https://network.igs.org/api/public/download/WES200USA.log?lower_case=1",
        45_228,
        "3afc9bfee52fe06e76cda8dbb2a75bcb4f68bbbb44f5e44b0ebb9c62f2115d76",
        "2026-07-20",
    ),
    CandidateStation(
        "ALGO00CAN",
        45.955800,
        -78.071368,
        200.8294485278988,
        "40104M002",
        "SEPT POLARX5 - 5.3.2",
        "AOAD/M_T - NONE",
        "2026-03-25",
        "https://network.igs.org/ALGO00CAN",
        44_181,
        "419836c1c273c81e6ae52517fec37847953a6fe8362b2ec20b71e2e8eacf72db",
        "https://network.igs.org/api/public/download/ALGO00CAN.log?lower_case=1",
        33_951,
        "416fb5167b77cb97c9040b9c0e37b956c97b0b846401e5258909d8cd89c4dca8",
        "2026-04-01",
    ),
    CandidateStation(
        "PIE100USA",
        34.301506,
        -108.118927,
        2347.7109,
        "40456M001",
        "SEPT POLARX5TR - 5.7.0",
        "ASH701945E_M - NONE",
        "2026-03-10",
        "https://network.igs.org/PIE100USA",
        42_899,
        "c70b6cd5783a49f232423c7feb60630f22c2b285ccbc30e093cfc9ed90f8a3e9",
        "https://network.igs.org/api/public/download/PIE100USA.log?lower_case=1",
        29_326,
        "de79c3d3f677bb6a8d61ab11fc0eee0215a39ef93d79668826cd2537248fe626",
        "2026-03-25",
    ),
    CandidateStation(
        "AMC400USA",
        38.803125,
        -104.524597,
        1911.3941,
        "40472S005",
        "SEPT POLARX5TR - 5.6.0",
        "TPSCR.G5C - NONE",
        "2025-08-28",
        "https://network.igs.org/AMC400USA",
        23_453,
        "8b5ee595c577a9387f467eeec32eb57835b06d9251355de914fd697fecd96df4",
        "https://network.igs.org/api/public/download/AMC400USA.log?lower_case=1",
        13_049,
        "c510f416437c2aa941b565b589159b3ca5447bcf51e21374246e49661c4f82c5",
        "2025-08-28",
    ),
    CandidateStation(
        "MDO100USA",
        30.680511,
        -104.014994,
        2004.5,
        "40442M012",
        "SEPT POLARX5 - 5.7.0",
        "JAVRINGANT_DM - SCIS",
        "2026-03-18",
        "https://network.igs.org/MDO100USA",
        33_744,
        "13bcebb278631aea7fa537eefd434fd91003c1491966412fcb463b325798e100",
        "https://network.igs.org/api/public/download/MDO100USA.log?lower_case=1",
        29_750,
        "5ebf294b0bc4b34ce10df283f2f118bfb7af0f02c41d09f12940bc9f05dd0b6f",
        "2026-03-18",
    ),
)


class IndependentPairScreenError(ValueError):
    """A frozen authority, station set or numerical invariant changed."""


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
        "python": platform.python_version(),
        "numpy": importlib.metadata.version("numpy"),
    }


def _station(candidate: CandidateStation) -> geometry.Station:
    return geometry.Station(
        candidate.station_id,
        candidate.latitude_deg,
        candidate.longitude_deg,
        candidate.height_m,
        "UNKNOWN_NOT_REQUIRED_FOR_GEOMETRY_SCREEN",
        candidate.receiver,
        candidate.antenna,
        "ROBOT",
        f"{candidate.station_id}_{candidate.domes}",
        candidate.station_page_url,
    )


def manifest() -> dict[str, object]:
    result = {
        "schema": "gnss-phase-independent-pair-screen-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "physical_question": (
            "DOES_THE_FROZEN_G22_RELATIVE_G30_GEOMETRY_RETAIN_POSITIVE_"
            "HELDOUT_DISCRIMINABILITY_ON_A_STATION_PAIR_DISJOINT_FROM_GOLD_NLIB"
        ),
        "new_information": (
            "WHETHER_THE_TWO_POSITIVE_GOLD_NLIB_PASSES_CAN_BE_CHALLENGED_"
            "OUTSIDE_THEIR_SHARED_HARDWARE_AND_GEOGRAPHY"
        ),
        "why_existing_cannot_answer": (
            "DOY220_AND_DOY219_SHARE_GOLD_NLIB_AND_CANNOT_EXCLUDE_PAIR_SPECIFIC_"
            "SYSTEMATICS"
        ),
        "minimum_experiment": (
            "ONE_BOUNDED_ORBIT_ONLY_RANKING_OF_SIX_PREDECLARED_IGS_ROOTS_"
            "BEFORE_ANY_OBSERVATION_PRODUCT_DISCOVERY"
        ),
        "stop_condition": (
            "STOP_AFTER_SHORTLIST_OR_NO_ADMISSIBLE_PAIR_BEFORE_CAPABILITY_"
            "QUALIFICATION"
        ),
        "metadata_snapshot_date": METADATA_SNAPSHOT_DATE,
        "metadata_scope": (
            "OFFICIAL_IGS_STATION_IDENTITY_GEOMETRY_AND_EQUIPMENT_ONLY"
        ),
        "candidate_root_state": (
            "CANDIDATE_SITE_ROOT_NOT_YET_CAPABILITY_QUALIFIED"
        ),
        "candidate_set": [asdict(candidate) for candidate in CANDIDATES],
        "selection_rule": [
            "STRICT_POSITIVE_PHYSICAL_MARGIN",
            "MAXIMUM_REMAINING_PHYSICAL_MARGIN",
            "MAXIMUM_MINIMUM_MODEL_ELEVATION",
            "LEXICAL_STATION_PAIR",
        ],
        "navigation": asdict(repeated.navigation_authority()),
        "grid": {
            "gps_date": repeated.navigation_authority().gps_date,
            "raw_start_gps": frozen.REPLICATION_RAW_START.isoformat(),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
            "feature_epochs": frozen.FEATURE_EPOCHS,
            "calibration_epochs": frozen.CALIBRATION_EPOCHS,
            "heldout_epochs": frozen.HELDOUT_EPOCHS,
        },
        "hypotheses": {
            "orbital": "BROADCAST_G22_RELATIVE_TO_G30",
            "prefix_affine": "ZERO_GEOMETRY_WITH_PREFIX_CONSTANT_RATE_ONLY",
            "wrong_orbits": list(WRONG_ORBITS),
        },
        "physical_envelope": {
            "same_terms_as_consumed_g22_g30_phase_experiment": True,
            "station_specific_recomputation": [
                "DIRECT_PLUS_MINUS_15_SECOND_TRAJECTORY",
                "DIFFERENTIAL_TROPOSPHERE",
            ],
            "generic_four_link_terms_reused": True,
            "pairwise_multiplier": envelope.PAIRWISE_ENVELOPE_MULTIPLIER,
        },
        "observation_boundary": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoder_present": False,
            "network_capability": False,
        },
        "not_a_plan_freeze": True,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def _positions(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    utc_epochs: Sequence,
    offset_s: float,
) -> np.ndarray:
    return np.asarray(
        [
            geometry.broadcast_ecef(
                geometry.select_ephemeris(
                    records[satellite],
                    epoch + timedelta(seconds=offset_s),
                ),
                epoch + timedelta(seconds=offset_s),
            )
            for epoch in utc_epochs
        ],
        dtype=np.float64,
    )


def troposphere_term(
    elevations: Mapping[tuple[str, str], np.ndarray],
    left: str,
    right: str,
    feature: slice,
) -> dict[str, object]:
    """Apply the frozen mapping without the legacy GOLD/NLIB name coupling."""

    def mapping(station_id: str, satellite: str) -> np.ndarray:
        radians = np.radians(elevations[(station_id, satellite)])
        return 1.0 / np.maximum(
            np.sin(radians),
            sin(np.radians(geometry.MINIMUM_ELEVATION_DEG)),
        )

    left_shape = mapping(left, "G22") - mapping(left, "G30")
    right_shape = mapping(right, "G22") - mapping(right, "G30")
    maximum = 0.0
    controlling = None
    for left_ztd in (0.0, envelope.MAX_ZENITH_TROPOSPHERE_M):
        for right_ztd in (0.0, envelope.MAX_ZENITH_TROPOSPHERE_M):
            path = (left_ztd * left_shape - right_ztd * right_shape)[feature]
            bound = phase.phase_prefix_metrics(
                path,
                split=frozen.CALIBRATION_EPOCHS,
                step_s=frozen.STEP_S,
            )["heldout_peak_to_peak_m"]
            if bound > maximum:
                maximum = float(bound)
                controlling = [left_ztd, right_ztd]
    return {
        "term": "DIFFERENTIAL_TROPOSPHERE",
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "zenith_delay_interval_m": [0.0, envelope.MAX_ZENITH_TROPOSPHERE_M],
        "controlling_station_zenith_delays_m": controlling,
        "heldout_peak_to_peak_bound_m": maximum,
        "basis": "CONSERVATIVE_ONE_OVER_SINE_MAPPING_IN_PHASE_RANGE_UNITS",
    }


def rank_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    admissible = [
        dict(row)
        for row in rows
        if bool(row["admissible_geometry"])
        and float(row["remaining_physical_margin_m"]) > 0.0
    ]
    admissible.sort(
        key=lambda row: (
            -float(row["remaining_physical_margin_m"]),
            -float(row["minimum_model_elevation_deg"]),
            tuple(str(item) for item in row["station_pair"]),
        )
    )
    return admissible[:SHORTLIST_SIZE]


def compile_screen_from_gzip(payload: bytes) -> dict[str, object]:
    records = repeated.parse_navigation_gzip(payload)
    return compile_screen(records)


def compile_screen(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
) -> dict[str, object]:
    if set(MODEL_SATELLITES) - set(records):
        raise IndependentPairScreenError("MODEL_SATELLITE_MISSING")
    stations = tuple(_station(candidate) for candidate in CANDIDATES)
    if len({station.measurement_root for station in stations}) != len(stations):
        raise IndependentPairScreenError("CANDIDATE_SITE_ROOTS_NOT_UNIQUE")
    if {"GOLD00USA", "NLIB00USA"} & {
        station.station_id for station in stations
    }:
        raise IndependentPairScreenError("CONSUMED_ROOT_REENTERED")

    gps_epochs = repeated.expected_raw_gps_epochs()
    utc_epochs = tuple(
        epoch - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
        for epoch in gps_epochs
    )
    position_cache: dict[tuple[str, float], np.ndarray] = {}

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, float(offset_s)
        if key not in position_cache:
            position_cache[key] = _positions(
                records,
                satellite,
                utc_epochs,
                offset_s,
            )
        return position_cache[key]

    station_ecef = {
        station.station_id: geometry.station_to_ecef(station)
        for station in stations
    }
    elevations = {
        (station.station_id, satellite): geometry.elevation_deg(
            positions(satellite),
            station,
            station_ecef[station.station_id],
        )
        for station in stations
        for satellite in MODEL_SATELLITES
    }

    def range_curve(
        left: str,
        right: str,
        target: str,
        left_offset_s: float = 0.0,
        right_offset_s: float = 0.0,
    ) -> np.ndarray:
        return phase.double_difference_range_m(
            phase.range_to_station_m(
                positions(target, left_offset_s),
                station_ecef[left],
            ),
            phase.range_to_station_m(
                positions("G30", left_offset_s),
                station_ecef[left],
            ),
            phase.range_to_station_m(
                positions(target, right_offset_s),
                station_ecef[right],
            ),
            phase.range_to_station_m(
                positions("G30", right_offset_s),
                station_ecef[right],
            ),
        )

    feature = slice(1, frozen.RAW_EPOCHS - 1)
    projection_gain = envelope.affine_projection_peak_to_peak_gain(
        frozen.FEATURE_EPOCHS,
        frozen.CALIBRATION_EPOCHS,
        frozen.STEP_S,
    )
    rows: list[dict[str, object]] = []
    for left_index, left_station in enumerate(stations):
        for right_station in stations[left_index + 1 :]:
            left = left_station.station_id
            right = right_station.station_id
            minimum_elevation = {
                satellite: float(
                    np.min(
                        np.minimum(
                            elevations[(left, satellite)],
                            elevations[(right, satellite)],
                        )
                    )
                )
                for satellite in MODEL_SATELLITES
            }
            actual_minimum = min(
                minimum_elevation["G22"],
                minimum_elevation["G30"],
            )
            model_minimum = min(minimum_elevation.values())
            orbital = range_curve(left, right, "G22")[feature]
            affine = phase.phase_prefix_metrics(
                orbital,
                split=frozen.CALIBRATION_EPOCHS,
                step_s=frozen.STEP_S,
            )
            wrong_orbits: list[dict[str, object]] = []
            for satellite in WRONG_ORBITS:
                alternative = range_curve(left, right, satellite)[feature]
                score = phase.phase_prefix_metrics(
                    orbital - alternative,
                    split=frozen.CALIBRATION_EPOCHS,
                    step_s=frozen.STEP_S,
                )
                wrong_orbits.append(
                    {
                        "satellite": satellite,
                        "minimum_elevation_deg": minimum_elevation[satellite],
                        "heldout_peak_to_peak_m": score[
                            "heldout_peak_to_peak_m"
                        ],
                        "heldout_rms_m": score["heldout_rms_m"],
                    }
                )
            wrong_orbits.sort(
                key=lambda row: (
                    float(row["heldout_peak_to_peak_m"]),
                    str(row["satellite"]),
                )
            )
            controlling_wrong = wrong_orbits[0]
            affine_separation = float(affine["heldout_peak_to_peak_m"])
            wrong_separation = float(
                controlling_wrong["heldout_peak_to_peak_m"]
            )
            controlling_separation = min(affine_separation, wrong_separation)
            controlling_null = (
                "PREFIX_AFFINE"
                if affine_separation <= wrong_separation
                else f"WRONG_ORBIT_{controlling_wrong['satellite']}"
            )

            def fixed_reference_curve(
                target_satellite: str,
                left_offset_s: float,
                right_offset_s: float,
            ) -> np.ndarray:
                return range_curve(
                    left,
                    right,
                    target_satellite,
                    left_offset_s,
                    right_offset_s,
                )

            terms = [
                phase.timing_term(
                    fixed_reference_curve,
                    feature,
                    target="G22",
                ),
                troposphere_term(elevations, left, right, feature),
                phase.quantization_term(projection_gain),
            ]
            terms.extend(
                phase.per_link_interval_term(definition, projection_gain)
                for definition in envelope.GENERIC_PATH_BOUNDS_M
            )
            decision = phase.combine_terms(controlling_separation, terms)
            for term in terms:
                term["pairwise_contribution_m"] = float(
                    envelope.PAIRWISE_ENVELOPE_MULTIPLIER
                    * float(term["heldout_peak_to_peak_bound_m"])
                )
            terms.sort(
                key=lambda term: (
                    -float(term["pairwise_contribution_m"]),
                    str(term["term"]),
                )
            )
            rows.append(
                {
                    "station_pair": [left, right],
                    "candidate_station_roots": [
                        left_station.measurement_root,
                        right_station.measurement_root,
                    ],
                    "root_state": (
                        "CANDIDATE_SITE_ROOTS_NOT_YET_CAPABILITY_QUALIFIED"
                    ),
                    "minimum_elevation_deg_by_model_satellite": minimum_elevation,
                    "actual_four_link_minimum_elevation_deg": actual_minimum,
                    "minimum_model_elevation_deg": model_minimum,
                    "prefix_affine": affine,
                    "wrong_orbits": wrong_orbits,
                    "controlling_null": controlling_null,
                    "controlling_heldout_separation_m": controlling_separation,
                    "affine_projection_peak_to_peak_gain": projection_gain,
                    "physical_terms": terms,
                    **decision,
                    "admissible_geometry": (
                        model_minimum >= geometry.MINIMUM_ELEVATION_DEG
                        and float(decision["remaining_physical_margin_m"]) > 0.0
                    ),
                }
            )

    shortlist = rank_rows(rows)
    result = {
        "schema": "gnss-phase-independent-pair-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "manifest_sha256": manifest_sha256(),
        "navigation": asdict(repeated.navigation_authority()),
        "candidate_set": [asdict(candidate) for candidate in CANDIDATES],
        "evaluated_pair_count": len(rows),
        "admitted_pair_count": sum(
            1 for row in rows if bool(row["admissible_geometry"])
        ),
        "evaluated_pairs": rows,
        "shortlist": shortlist,
        "selected_pair": shortlist[0] if shortlist else None,
        "outcome": OUTCOME_SHORTLISTED if shortlist else OUTCOME_NONE,
        "observation_access": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "metadata_access": {
            "station_pages_read": len(CANDIDATES),
            "station_logs_read": len(CANDIDATES),
            "station_page_or_log_bytes_persisted": 0,
            "frozen_fields_and_hashes_only": True,
        },
        "prospective_plan_frozen": False,
        "next_maximum": (
            "METADATA_ONLY_CAPABILITY_QUALIFICATION_OF_SELECTED_PAIR"
            if shortlist
            else "STOP_NO_PAIR"
        ),
        "stop": (
            "NO_OBSERVATION_PRODUCT_DISCOVERY_OR_ACCESS_BEFORE_SEPARATE_REVIEW"
        ),
    }
    strict_json(result)
    for values in position_cache.values():
        values.fill(0.0)
    return result


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        strict_json(value, pretty=True) + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--navigation-gzip", type=Path)
    parser.add_argument("--navigation-gzip-stdin", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(RECEIPT_NAME))
    args = parser.parse_args()
    if (args.navigation_gzip is None) == (not args.navigation_gzip_stdin):
        raise SystemExit("SUPPLY_EXACTLY_ONE_NAVIGATION_GZIP_INPUT")
    payload = (
        sys.stdin.buffer.read()
        if args.navigation_gzip_stdin
        else args.navigation_gzip.read_bytes()
    )
    try:
        receipt = compile_screen_from_gzip(payload)
    finally:
        payload = b""
    _write_json(args.output, receipt)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
