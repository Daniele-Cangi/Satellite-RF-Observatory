"""Orbit-only selection of a new ALGO/MDO G22/G30 primary date.

This bounded screen accepts exactly three predeclared broadcast-navigation
products.  It has no RINEX observation-product input or discovery surface.
The closed DOY 219 ALGO/MDO experiment is never reopened or substituted.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
import importlib.metadata
import json
from math import sin
from pathlib import Path
import platform
import subprocess
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


SCREEN_VERSION: Final = "algo-mdo-next-primary-orbit-screen-v1"
RECEIPT_NAME: Final = "GNSS_INDEPENDENT_PAIR_NEXT_PRIMARY_SCREEN_RECEIPT.json"
OUTCOME_SELECTED: Final = "NEXT_PRIMARY_GEOMETRY_SELECTED"
OUTCOME_NONE: Final = "NO_NEW_INDEPENDENT_PAIR_GEOMETRY"

STEP_S: Final = 30
RAW_EPOCHS: Final = 139
FEATURE_EPOCHS: Final = 137
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 60
TARGET: Final = "G22"
REFERENCE: Final = "G30"
WRONG_ORBITS: Final = ("G01", "G14", "G17")
MODEL_SATELLITES: Final = (TARGET, REFERENCE, *WRONG_ORBITS)
CONSUMED_DOYS: Final = (217, 218, 219, 220)


@dataclass(frozen=True, slots=True)
class NavigationCandidate:
    doy: int
    gps_date: str
    name: str
    url: str


NAVIGATION_CANDIDATES: Final = (
    NavigationCandidate(
        221,
        "2026-08-09",
        "BRDM00DLR_S_20262210000_01D_MN.rnx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/221/"
        "BRDM00DLR_S_20262210000_01D_MN.rnx.gz",
    ),
    NavigationCandidate(
        222,
        "2026-08-10",
        "BRDM00DLR_S_20262220000_01D_MN.rnx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/222/"
        "BRDM00DLR_S_20262220000_01D_MN.rnx.gz",
    ),
    NavigationCandidate(
        223,
        "2026-08-11",
        "BRDM00DLR_S_20262230000_01D_MN.rnx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/223/"
        "BRDM00DLR_S_20262230000_01D_MN.rnx.gz",
    ),
)


@dataclass(frozen=True, slots=True)
class StationAuthority:
    station_id: str
    latitude_deg: float
    longitude_deg: float
    height_m: float
    measurement_root: str
    receiver: str
    antenna: str
    equipment_effective: str
    station_page_url: str
    station_page_sha256: str
    station_log_url: str
    station_log_sha256: str


STATIONS: Final = (
    StationAuthority(
        "ALGO00CAN",
        45.955800,
        -78.071368,
        200.8294485278988,
        "ALGO00CAN_40104M002",
        "SEPT POLARX5 - 5.3.2",
        "AOAD/M_T - NONE",
        "2026-03-25",
        "https://network.igs.org/ALGO00CAN",
        "419836c1c273c81e6ae52517fec37847953a6fe8362b2ec20b71e2e8eacf72db",
        "https://network.igs.org/api/public/download/ALGO00CAN.log?lower_case=1",
        "416fb5167b77cb97c9040b9c0e37b956c97b0b846401e5258909d8cd89c4dca8",
    ),
    StationAuthority(
        "MDO100USA",
        30.680511,
        -104.014994,
        2004.5,
        "MDO100USA_40442M012",
        "SEPT POLARX5 - 5.7.0",
        "JAVRINGANT_DM - SCIS",
        "2026-03-18",
        "https://network.igs.org/MDO100USA",
        "13bcebb278631aea7fa537eefd434fd91003c1491966412fcb463b325798e100",
        "https://network.igs.org/api/public/download/MDO100USA.log?lower_case=1",
        "5ebf294b0bc4b34ce10df283f2f118bfb7af0f02c41d09f12940bc9f05dd0b6f",
    ),
)


class NextPrimaryScreenError(ValueError):
    """The bounded model authority or numerical contract is invalid."""


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


def _station(authority: StationAuthority) -> geometry.Station:
    return geometry.Station(
        authority.station_id,
        authority.latitude_deg,
        authority.longitude_deg,
        authority.height_m,
        "UNKNOWN_NOT_REQUIRED_FOR_ORBIT_SCREEN",
        authority.receiver,
        authority.antenna,
        "ROBOT",
        authority.measurement_root,
        authority.station_page_url,
    )


def manifest() -> dict[str, object]:
    result = {
        "schema": "gnss-independent-pair-next-primary-screen-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "physical_question": (
            "DOES_A_NEW_ALGO_MDO_G22_RELATIVE_G30_PASS_HAVE_POSITIVE_"
            "HELDOUT_ORBITAL_DISCRIMINABILITY_AFTER_THE_FROZEN_PHYSICAL_ENVELOPE"
        ),
        "new_information": (
            "WHICH_ONE_OF_THREE_NEW_DATES_CAN_SUPPORT_A_DISTINCT_HELDOUT_"
            "REPETITION_WITHOUT_REOPENING_THE_CLOSED_DOY219_EXPERIMENT"
        ),
        "why_existing_cannot_answer": (
            "DOY219_TERMINATED_AT_ARTIFACT_MATERIALIZATION_AND_IS_IMMUTABLY_CLOSED"
        ),
        "minimum_experiment": (
            "ONE_ORBIT_ONLY_SWEEP_OF_THREE_PREDECLARED_BROADCAST_NAVIGATION_DAYS_"
            "FOR_THE_ALREADY_QUALIFIED_ALGO_MDO_GEOMETRY"
        ),
        "stop_condition": (
            "STOP_AFTER_ONE_RANKED_DATE_AND_WINDOW_OR_NO_POSITIVE_GEOMETRY_"
            "BEFORE_ANY_OBSERVATION_PRODUCT_ACCESS"
        ),
        "new_gate": False,
        "generic_framework": False,
        "closed_experiment": {
            "doy": 219,
            "terminal_outcome": "PRIMARY_ARTIFACT_MATERIALIZATION_FAILED",
            "reopened": False,
            "retried": False,
            "substituted": False,
        },
        "candidate_navigation": [
            asdict(candidate) for candidate in NAVIGATION_CANDIDATES
        ],
        "candidate_dates_predeclared_before_navigation_access": True,
        "stations": [asdict(station) for station in STATIONS],
        "hypotheses": {
            "orbital": f"BROADCAST_{TARGET}_RELATIVE_TO_{REFERENCE}",
            "prefix_affine": "ZERO_GEOMETRY_WITH_PREFIX_CONSTANT_RATE_ONLY",
            "wrong_orbits": list(WRONG_ORBITS),
        },
        "partition": {
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "feature_epochs": FEATURE_EPOCHS,
            "calibration_epochs": CALIBRATION_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "feature_raw_indices_inclusive": [1, 137],
            "calibration_feature_indices_inclusive": [0, 76],
            "heldout_feature_indices_inclusive": [77, 136],
        },
        "visibility": {
            "minimum_elevation_deg": geometry.MINIMUM_ELEVATION_DEG,
            "required_satellites": list(MODEL_SATELLITES),
            "required_stations": [station.station_id for station in STATIONS],
            "scope": "ALL_139_RAW_EPOCHS_JOINTLY_VISIBLE",
            "window_shortening": "FORBIDDEN",
        },
        "physical_envelope": {
            "same_terms_as_closed_algo_mdo_plan": True,
            "direct_station_time_offsets_s": [
                -envelope.MAX_STATION_EPOCH_ERROR_S,
                envelope.MAX_STATION_EPOCH_ERROR_S,
            ],
            "differential_troposphere_recomputed_per_window": True,
            "generic_four_link_terms_reused": True,
            "pairwise_multiplier": envelope.PAIRWISE_ENVELOPE_MULTIPLIER,
        },
        "selection_rule": [
            "STRICT_POSITIVE_REMAINING_PHYSICAL_MARGIN",
            "BEST_WINDOW_PER_PREDECLARED_DATE",
            "MAXIMUM_REMAINING_PHYSICAL_MARGIN",
            "MAXIMUM_CONTROLLING_HELDOUT_SEPARATION",
            "MAXIMUM_MINIMUM_MODEL_ELEVATION",
            "EARLIEST_GPS_START",
        ],
        "observation_boundary": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoder_present": False,
            "network_capability": False,
        },
        "prospective_plan_frozen": False,
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def parse_navigation_gzip(
    candidate: NavigationCandidate,
    payload: bytes,
) -> tuple[dict[str, tuple[geometry.GpsEphemeris, ...]], dict[str, object]]:
    if not payload:
        raise NextPrimaryScreenError(f"NAVIGATION_EMPTY_DOY_{candidate.doy}")
    compressed_sha256 = sha256(payload).hexdigest()
    try:
        raw = gzip.decompress(payload)
    except (EOFError, OSError) as exc:
        raise NextPrimaryScreenError(
            f"NAVIGATION_GZIP_INVALID_DOY_{candidate.doy}"
        ) from exc
    raw_sha256 = sha256(raw).hexdigest()
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise NextPrimaryScreenError(
            f"NAVIGATION_ASCII_INVALID_DOY_{candidate.doy}"
        ) from exc
    try:
        start = (
            next(
                index
                for index, line in enumerate(lines)
                if "END OF HEADER" in line
            )
            + 1
        )
    except StopIteration as exc:
        raise NextPrimaryScreenError(
            f"NAVIGATION_HEADER_INCOMPLETE_DOY_{candidate.doy}"
        ) from exc

    parsed: dict[str, list[geometry.GpsEphemeris]] = {}
    for index in range(start, len(lines)):
        if not lines[index].startswith("G"):
            continue
        if index + 7 >= len(lines):
            raise NextPrimaryScreenError(
                f"NAVIGATION_RECORD_TRUNCATED_DOY_{candidate.doy}"
            )
        record = geometry.parse_gps_record(lines[index : index + 8])
        if record.sv_health == 0 and 0.0 <= record.eccentricity < 1.0:
            parsed.setdefault(record.satellite, []).append(record)
    records = {
        satellite: tuple(sorted(values, key=lambda value: value.toc_gps))
        for satellite, values in parsed.items()
    }
    missing = set(MODEL_SATELLITES) - set(records)
    if missing:
        raise NextPrimaryScreenError(
            f"MODEL_SATELLITES_MISSING_DOY_{candidate.doy}_{'_'.join(sorted(missing))}"
        )
    authority = {
        **asdict(candidate),
        "compressed_bytes": len(payload),
        "compressed_sha256": compressed_sha256,
        "uncompressed_name": candidate.name.removesuffix(".gz"),
        "uncompressed_bytes": len(raw),
        "uncompressed_sha256": raw_sha256,
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }
    payload = b""
    raw = b""
    return records, authority


def gps_day_grid(candidate: NavigationCandidate) -> tuple[datetime, ...]:
    gps_midnight = datetime.fromisoformat(candidate.gps_date).replace(
        tzinfo=timezone.utc
    )
    first_utc = gps_midnight - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    return tuple(
        first_utc + timedelta(seconds=index * STEP_S) for index in range(2_880)
    )


def candidate_window_starts(mask: Sequence[bool]) -> tuple[int, ...]:
    values = np.asarray(mask, dtype=bool)
    if values.ndim != 1:
        raise NextPrimaryScreenError("INVALID_JOINT_VISIBILITY_MASK")
    starts: list[int] = []
    for segment_start, segment_stop in geometry.contiguous_true_segments(values):
        if segment_stop - segment_start < RAW_EPOCHS:
            continue
        starts.extend(range(segment_start, segment_stop - RAW_EPOCHS + 1))
    return tuple(starts)


def _position_series(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    utc_epochs: Sequence[datetime],
    offset_s: float,
) -> np.ndarray:
    result = np.full((len(utc_epochs), 3), np.nan, dtype=np.float64)
    for index, epoch in enumerate(utc_epochs):
        shifted = epoch + timedelta(seconds=offset_s)
        try:
            record = geometry.select_ephemeris(records[satellite], shifted)
            result[index] = geometry.broadcast_ecef(record, shifted)
        except (KeyError, geometry.GnssDoubleDifferenceError):
            continue
    return result


def _troposphere_term(
    elevations: Mapping[tuple[str, str], np.ndarray],
    feature: slice,
) -> dict[str, object]:
    left, right = (station.station_id for station in STATIONS)

    def mapping(station_id: str, satellite: str) -> np.ndarray:
        radians = np.radians(elevations[(station_id, satellite)])
        return 1.0 / np.maximum(
            np.sin(radians),
            sin(np.radians(geometry.MINIMUM_ELEVATION_DEG)),
        )

    left_shape = mapping(left, TARGET) - mapping(left, REFERENCE)
    right_shape = mapping(right, TARGET) - mapping(right, REFERENCE)
    maximum = 0.0
    controlling = None
    for left_ztd in (0.0, envelope.MAX_ZENITH_TROPOSPHERE_M):
        for right_ztd in (0.0, envelope.MAX_ZENITH_TROPOSPHERE_M):
            path = (left_ztd * left_shape - right_ztd * right_shape)[feature]
            bound = phase.phase_prefix_metrics(
                path,
                split=CALIBRATION_EPOCHS,
                step_s=STEP_S,
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


def rank_days(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    admitted = [
        dict(row)
        for row in rows
        if bool(row["joint_visibility_complete"])
        and float(row["remaining_physical_margin_m"]) > 0.0
    ]
    admitted.sort(
        key=lambda row: (
            -float(row["remaining_physical_margin_m"]),
            -float(row["controlling_heldout_separation_m"]),
            -float(row["minimum_model_elevation_deg"]),
            str(row["raw_start_gps"]),
        )
    )
    return admitted


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_gps(value: datetime) -> str:
    gps = value + timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    return gps.isoformat(timespec="seconds").replace("+00:00", " GPS")


def compile_day(
    candidate: NavigationCandidate,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
) -> dict[str, object]:
    if candidate.doy in CONSUMED_DOYS:
        raise NextPrimaryScreenError("CONSUMED_DATE_REENTERED")
    if set(MODEL_SATELLITES) - set(records):
        raise NextPrimaryScreenError("MODEL_SATELLITE_MISSING")

    utc_epochs = gps_day_grid(candidate)
    stations = tuple(_station(station) for station in STATIONS)
    station_ecef = {
        station.station_id: geometry.station_to_ecef(station)
        for station in stations
    }
    offsets = (
        -envelope.MAX_STATION_EPOCH_ERROR_S,
        0.0,
        envelope.MAX_STATION_EPOCH_ERROR_S,
    )
    position_cache: dict[tuple[str, float], np.ndarray] = {}

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, float(offset_s)
        if key not in position_cache:
            position_cache[key] = _position_series(
                records, satellite, utc_epochs, offset_s
            )
        return position_cache[key]

    for satellite in MODEL_SATELLITES:
        positions(satellite)
    for satellite in (TARGET, REFERENCE):
        for offset in offsets:
            positions(satellite, offset)

    elevations = {
        (station.station_id, satellite): geometry.elevation_deg(
            positions(satellite), station, station_ecef[station.station_id]
        )
        for station in stations
        for satellite in MODEL_SATELLITES
    }
    joint_visibility = np.ones(len(utc_epochs), dtype=bool)
    for values in elevations.values():
        joint_visibility &= np.isfinite(values)
        joint_visibility &= values >= geometry.MINIMUM_ELEVATION_DEG
    starts = candidate_window_starts(joint_visibility)

    left, right = (station.station_id for station in stations)

    def full_range_curve(
        target: str,
        left_offset_s: float = 0.0,
        right_offset_s: float = 0.0,
    ) -> np.ndarray:
        # Full-day arrays may contain NaNs where a broadcast ephemeris is
        # unavailable. Joint visibility excludes those epochs before scoring.
        left_target = np.linalg.norm(
            positions(target, left_offset_s) - station_ecef[left], axis=1
        )
        left_reference = np.linalg.norm(
            positions(REFERENCE, left_offset_s) - station_ecef[left], axis=1
        )
        right_target = np.linalg.norm(
            positions(target, right_offset_s) - station_ecef[right], axis=1
        )
        right_reference = np.linalg.norm(
            positions(REFERENCE, right_offset_s) - station_ecef[right], axis=1
        )
        return (left_target - left_reference) - (
            right_target - right_reference
        )

    nominal_curves = {
        satellite: full_range_curve(satellite) for satellite in (TARGET, *WRONG_ORBITS)
    }
    timing_curves = {
        (left_offset, right_offset): full_range_curve(
            TARGET, left_offset, right_offset
        )
        for left_offset in offsets
        for right_offset in offsets
    }
    projection_gain = envelope.affine_projection_peak_to_peak_gain(
        FEATURE_EPOCHS, CALIBRATION_EPOCHS, STEP_S
    )
    feature = slice(1, RAW_EPOCHS - 1)
    best: dict[str, object] | None = None
    best_ordering: tuple[float, float, float, int] | None = None

    for start in starts:
        raw = slice(start, start + RAW_EPOCHS)
        orbital = nominal_curves[TARGET][raw][feature]
        affine = phase.phase_prefix_metrics(
            orbital, split=CALIBRATION_EPOCHS, step_s=STEP_S
        )
        wrong_rows: list[dict[str, object]] = []
        for satellite in WRONG_ORBITS:
            score = phase.phase_prefix_metrics(
                orbital - nominal_curves[satellite][raw][feature],
                split=CALIBRATION_EPOCHS,
                step_s=STEP_S,
            )
            wrong_rows.append(
                {
                    "satellite": satellite,
                    "heldout_peak_to_peak_m": score["heldout_peak_to_peak_m"],
                    "heldout_rms_m": score["heldout_rms_m"],
                }
            )
        wrong_rows.sort(
            key=lambda row: (
                float(row["heldout_peak_to_peak_m"]), str(row["satellite"])
            )
        )
        controlling_wrong = wrong_rows[0]
        affine_separation = float(affine["heldout_peak_to_peak_m"])
        wrong_separation = float(controlling_wrong["heldout_peak_to_peak_m"])
        controlling_separation = min(affine_separation, wrong_separation)
        controlling_null = (
            "PREFIX_AFFINE"
            if affine_separation <= wrong_separation
            else f"WRONG_ORBIT_{controlling_wrong['satellite']}"
        )

        def window_curve(
            target_satellite: str,
            left_offset_s: float,
            right_offset_s: float,
        ) -> np.ndarray:
            if target_satellite != TARGET:
                raise NextPrimaryScreenError("TIMING_TARGET_CHANGED")
            return timing_curves[(left_offset_s, right_offset_s)][raw]

        window_elevations = {
            key: value[raw] for key, value in elevations.items()
        }
        terms = [
            phase.timing_term(window_curve, feature, target=TARGET),
            _troposphere_term(window_elevations, feature),
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
                -float(term["pairwise_contribution_m"]), str(term["term"])
            )
        )
        minimum_by_satellite = {
            satellite: float(
                min(
                    np.min(elevations[(left, satellite)][raw]),
                    np.min(elevations[(right, satellite)][raw]),
                )
            )
            for satellite in MODEL_SATELLITES
        }
        start_utc = utc_epochs[start]
        stop_utc = utc_epochs[start + RAW_EPOCHS - 1]
        row = {
            "doy": candidate.doy,
            "gps_date": candidate.gps_date,
            "raw_start_gps": _format_gps(start_utc),
            "raw_stop_gps": _format_gps(stop_utc),
            "raw_start_utc": _format_utc(start_utc),
            "raw_stop_utc": _format_utc(stop_utc),
            "heldout_start_gps": _format_gps(
                start_utc + timedelta(seconds=(1 + CALIBRATION_EPOCHS) * STEP_S)
            ),
            "joint_visibility_complete": True,
            "minimum_elevation_deg_by_model_satellite": minimum_by_satellite,
            "minimum_model_elevation_deg": min(minimum_by_satellite.values()),
            "prefix_affine": affine,
            "wrong_orbits": wrong_rows,
            "controlling_null": controlling_null,
            "controlling_heldout_separation_m": controlling_separation,
            "affine_projection_peak_to_peak_gain": projection_gain,
            "physical_terms": terms,
            **decision,
        }
        ordering = (
            float(row["remaining_physical_margin_m"]),
            float(row["controlling_heldout_separation_m"]),
            float(row["minimum_model_elevation_deg"]),
            -start,
        )
        if best_ordering is None or ordering > best_ordering:
            best = row
            best_ordering = ordering
    for values in position_cache.values():
        values.fill(0.0)
    return {
        "doy": candidate.doy,
        "gps_date": candidate.gps_date,
        "joint_visible_epoch_count": int(np.sum(joint_visibility)),
        "candidate_window_count": len(starts),
        "best_window": best,
        "day_admitted": (
            best is not None
            and float(best["remaining_physical_margin_m"]) > 0.0
        ),
    }


def compile_screen(
    payloads: Mapping[int, bytes],
) -> dict[str, object]:
    expected = {candidate.doy for candidate in NAVIGATION_CANDIDATES}
    if set(payloads) != expected:
        raise NextPrimaryScreenError("NAVIGATION_CANDIDATE_SET_CHANGED")
    navigation: list[dict[str, object]] = []
    days: list[dict[str, object]] = []
    for candidate in NAVIGATION_CANDIDATES:
        records, authority = parse_navigation_gzip(candidate, payloads[candidate.doy])
        navigation.append(authority)
        days.append(compile_day(candidate, records))
    ranking = rank_days(
        day["best_window"]
        for day in days
        if day["best_window"] is not None
    )
    result = {
        "schema": "gnss-independent-pair-next-primary-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "manifest_sha256": manifest_sha256(),
        "navigation": navigation,
        "day_results": days,
        "ranking": ranking,
        "selected": ranking[0] if ranking else None,
        "outcome": OUTCOME_SELECTED if ranking else OUTCOME_NONE,
        "observation_access": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "prospective_plan_frozen": False,
        "next_maximum": (
            "FREEZE_ONE_DISTINCT_PRIMARY_CONTRACT_BEFORE_OBSERVATION_ACCESS"
            if ranking
            else "STOP_NO_POSITIVE_NEW_GEOMETRY"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_DISCOVERY_OR_ACCESS",
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    Path(path).write_text(
        strict_json(value, pretty=True) + chr(10),
        encoding="utf-8",
        newline=chr(10),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--navigation-gzip", type=Path, action="append", required=True
    )
    parser.add_argument("--output", type=Path, default=Path(RECEIPT_NAME))
    args = parser.parse_args()
    supplied = {path.name: path for path in args.navigation_gzip}
    expected = {candidate.name: candidate for candidate in NAVIGATION_CANDIDATES}
    if len(supplied) != len(args.navigation_gzip) or set(supplied) != set(expected):
        raise SystemExit("SUPPLY_EXACTLY_THE_THREE_FROZEN_NAVIGATION_PRODUCTS")
    payloads = {
        expected[name].doy: path.read_bytes() for name, path in supplied.items()
    }
    try:
        receipt = compile_screen(payloads)
    finally:
        payloads.clear()
    _write_json(args.output, receipt)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
