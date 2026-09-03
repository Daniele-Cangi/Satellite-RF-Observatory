"""Orbit-only screen for one six-track identity-blind GNSS vertical.

The compiler accepts exactly five predeclared GPS broadcast-navigation files.
It has no observation locator, observation parser, measurement values or
primary-selection authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
from itertools import combinations, permutations
import json
from math import sqrt
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_all_track_assignment_spike as mechanism,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)


SCREEN_VERSION: Final = "gnss-all-track-geometry-screen-v1"
RECEIPT_NAME: Final = "GNSS_ALL_TRACK_GEOMETRY_SCREEN_RECEIPT.json"
SCOPE_NAME: Final = "GNSS_ALL_TRACK_GEOMETRY_SCOPE.md"
SCOPE_COMMIT: Final = "33dba523f8c7c599b36b487e943486ad276926e0"
SCOPE_SHA256: Final = (
    "67e0a71156cf7e02326e74fd69e89dde4d3a7fbf63c7147bbfe8e809313986d5"
)

OUTCOME_SHORTLISTED: Final = (
    "ALL_TRACK_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED"
)
OUTCOME_NO_GEOMETRY: Final = "NO_ALL_TRACK_GEOMETRY_DISCRIMINATIVE"
OUTCOME_NO_INCLUSION: Final = "NO_VALUE_BLIND_TRACK_INCLUSION_RULE"

STEP_S: Final = 30.0
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
TRACK_COUNT: Final = 6
ASSIGNMENT_COUNT: Final = 720
HYPOTHESIS_COUNT: Final = 721
MINIMUM_ELEVATION_DEG: Final = 15.0
MAXIMUM_EVENT_TIME_ERROR_S: Final = 15.0
PAIRWISE_GUARD_M: Final = mechanism.PAIRWISE_GUARD_M
REQUIRED_EXACT_SEPARATION_M: Final = 3.0 * PAIRWISE_GUARD_M
SHORTLIST_SIZE: Final = 3


@dataclass(frozen=True, slots=True)
class StationCandidate:
    station_id: str
    latitude_deg: float
    longitude_deg: float
    height_m: float
    domes: str
    metadata_source: str


STATIONS: Final = (
    StationCandidate(
        "DRAO00CAN",
        49.322600,
        -119.625000,
        542.0,
        "40105M002",
        "FROZEN_IGS_METADATA_SNAPSHOT_2026_08_25",
    ),
    StationCandidate(
        "ALGO00CAN",
        45.955800,
        -78.071368,
        200.8294485278988,
        "40104M002",
        "FROZEN_IGS_METADATA_SNAPSHOT_2026_08_25",
    ),
    StationCandidate(
        "WES200USA",
        42.613336,
        -71.493328,
        85.0,
        "40440S020",
        "FROZEN_IGS_METADATA_SNAPSHOT_2026_08_25",
    ),
)

NAVIGATION_CANDIDATES: Final = tuple(
    navigation.NavigationCandidate(
        doy,
        gps_date,
        f"brdc{doy:03d}0.26n.gz",
        (
            "https://geodesy.noaa.gov/corsdata/rinex/2026/"
            f"{doy:03d}/brdc{doy:03d}0.26n.gz"
        ),
        "2.11",
        "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
    )
    for doy, gps_date in (
        (229, "2026-08-17"),
        (230, "2026-08-18"),
        (231, "2026-08-19"),
        (232, "2026-08-20"),
        (233, "2026-08-21"),
    )
)


class AllTrackGeometryScreenError(ValueError):
    """The frozen scope, model authority or numerical contract changed."""


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
        "numpy": importlib.metadata.version("numpy"),
        "python": platform.python_version(),
    }


def validate_scope(root: Path) -> dict[str, str]:
    path = Path(root) / SCOPE_NAME
    if not path.is_file() or canonical_sha256(path) != SCOPE_SHA256:
        raise AllTrackGeometryScreenError("FROZEN_SCOPE_CHANGED")
    if tuple(candidate.doy for candidate in NAVIGATION_CANDIDATES) != tuple(
        range(229, 234)
    ):
        raise AllTrackGeometryScreenError("NAVIGATION_SCOPE_CHANGED")
    if tuple(station.station_id for station in STATIONS) != (
        "DRAO00CAN",
        "ALGO00CAN",
        "WES200USA",
    ):
        raise AllTrackGeometryScreenError("STATION_SCOPE_CHANGED")
    return {
        "filename": SCOPE_NAME,
        "canonical_sha256": SCOPE_SHA256,
        "scope_commit": SCOPE_COMMIT,
    }


def manifest(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    result = {
        "schema": "gnss-all-track-geometry-screen-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "scope": validate_scope(base),
        "physical_question": (
            "DOES_ONE_PREDECLARED_STATION_DATE_CELL_SUPPORT_EXACTLY_SIX_"
            "COMPLETE_GPS_TRACKS_WITH_ROBUST_BLIND_ASSIGNMENT_MARGIN"
        ),
        "new_information": (
            "WHETHER_A_REAL_BROADCAST_ORBIT_GEOMETRY_CAN_INSTANTIATE_THE_"
            "SYNTHETIC_ALL_TRACK_ASSIGNMENT_MECHANISM"
        ),
        "why_existing_cannot_answer": (
            "THE_PRECEDING_RESULT_PROVED_ONLY_A_SYNTHETIC_SCORING_MECHANISM"
        ),
        "minimum_experiment": (
            "THREE_PREDECLARED_STATIONS_FIVE_PREDECLARED_NAVIGATION_DAYS_"
            "ZERO_OBSERVATION_PRODUCTS"
        ),
        "stop_condition": (
            "STOP_AFTER_THREE_ORBIT_ONLY_WINDOWS_OR_ONE_TYPED_CLOSURE_"
            "BEFORE_OBSERVATION_DISCOVERY"
        ),
        "stations": [asdict(station) for station in STATIONS],
        "navigation": [asdict(candidate) for candidate in NAVIGATION_CANDIDATES],
        "partition": {
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
        },
        "visibility": {
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "direct_time_offsets_s": [
                -MAXIMUM_EVENT_TIME_ERROR_S,
                0.0,
                MAXIMUM_EVENT_TIME_ERROR_S,
            ],
            "complete_window_required": True,
            "exact_complete_track_count": TRACK_COUNT,
            "seventh_complete_track": "CELL_INELIGIBLE",
        },
        "hypotheses": {
            "bijective_orbit_assignments": ASSIGNMENT_COUNT,
            "prefix_affine_nulls": 1,
            "total": HYPOTHESIS_COUNT,
            "identity_available_to_future_scorer": False,
        },
        "nuisance": {
            "common_mode": "PER_EPOCH_ENSEMBLE_CENTERING",
            "per_centered_track": ["PREFIX_CONSTANT", "PREFIX_RATE"],
            "effective_parameter_count": 2 * (TRACK_COUNT - 1),
            "heldout_refit": False,
            "free_time_phase": False,
            "time_warp": False,
        },
        "decision_envelope": {
            "historical_development_guard_m": PAIRWISE_GUARD_M,
            "required_exact_separation_m": REQUIRED_EXACT_SEPARATION_M,
            "robust_lower_bound": "EXACT_CONTROLLING_SEPARATION_MINUS_3_GUARDS",
            "reason": (
                "CORRECT_RESIDUAL_CAN_GROW_BY_ONE_GUARD_WRONG_RESIDUAL_CAN_"
                "SHRINK_BY_ONE_GUARD_AND_SCORER_REQUIRES_ONE_GUARD_PREFERENCE"
            ),
        },
        "value_blind_inclusion": {
            "rule": "ALL_STRUCTURALLY_COMPLETE_TRACKS_ON_FROZEN_GRID",
            "prn_selection": False,
            "measurement_value_selection": False,
            "required_future_count": TRACK_COUNT,
            "count_mismatch": "MEASUREMENT_ADMISSION_REFUSAL",
        },
        "observation_boundary": {
            "locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoders": 0,
        },
        "new_gate": False,
        "generic_framework": False,
        "primary_selected": False,
        "prospective_plan_frozen": False,
    }
    strict_json(result)
    return result


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(manifest(root)).encode("ascii")).hexdigest()


def _station(candidate: StationCandidate) -> geometry.Station:
    return geometry.Station(
        candidate.station_id,
        candidate.latitude_deg,
        candidate.longitude_deg,
        candidate.height_m,
        "UNKNOWN_NOT_REQUIRED_FOR_ORBIT_SCREEN",
        "NOT_USED",
        "NOT_USED",
        "NOT_USED",
        f"{candidate.station_id}_{candidate.domes}",
        candidate.metadata_source,
    )


def gps_day_grid(candidate: navigation.NavigationCandidate) -> tuple[datetime, ...]:
    gps_midnight = datetime.fromisoformat(candidate.gps_date).replace(
        tzinfo=timezone.utc
    )
    first_utc = gps_midnight - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    return tuple(
        first_utc + timedelta(seconds=index * STEP_S) for index in range(2_880)
    )


def _position_series(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    epochs: Sequence[datetime],
    offset_s: float,
) -> np.ndarray:
    result = np.full((len(epochs), 3), np.nan, dtype=np.float64)
    for index, epoch in enumerate(epochs):
        shifted = epoch + timedelta(seconds=offset_s)
        try:
            selected = geometry.select_ephemeris(records[satellite], shifted)
            result[index] = geometry.broadcast_ecef(selected, shifted)
        except (KeyError, geometry.GnssDoubleDifferenceError):
            continue
    return result


def prefix_project(matrix: Sequence[Sequence[float]]) -> tuple[np.ndarray, dict[str, object]]:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != RAW_EPOCHS:
        raise AllTrackGeometryScreenError("PREFIX_MATRIX_SHAPE_INVALID")
    if not np.all(np.isfinite(values)):
        raise AllTrackGeometryScreenError("PREFIX_MATRIX_NONFINITE")
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    prefix_x = elapsed[:PREFIX_EPOCHS]
    centered_x = prefix_x - float(np.mean(prefix_x))
    denominator = float(centered_x @ centered_x)
    if denominator <= 0.0:
        raise AllTrackGeometryScreenError("PREFIX_TIME_BASIS_INVALID")
    prefix = values[:, :PREFIX_EPOCHS]
    means = np.mean(prefix, axis=1)
    rates = ((prefix - means[:, None]) @ centered_x) / denominator
    constants = means - rates * float(np.mean(prefix_x))
    residual = values - constants[:, None] - rates[:, None] * elapsed[None, :]
    heldout = residual[:, PREFIX_EPOCHS:]
    metrics: dict[str, object] = {
        "heldout_peak_to_peak_m_by_row": [
            float(np.ptp(row)) for row in heldout
        ],
        "heldout_rms_m_by_row": [
            sqrt(float(np.mean(row * row))) for row in heldout
        ],
        "aggregate_heldout_rms_m": sqrt(float(np.mean(heldout * heldout))),
        "prefix_rms_m": sqrt(
            float(np.mean(residual[:, :PREFIX_EPOCHS] ** 2))
        ),
    }
    return residual, metrics


def evaluate_codebook(
    range_curves_m: Mapping[str, Sequence[float]],
) -> dict[str, object]:
    codes = tuple(sorted(range_curves_m))
    if len(codes) != TRACK_COUNT:
        raise AllTrackGeometryScreenError("CODEBOOK_MUST_HAVE_EXACTLY_SIX_TRACKS")
    matrix = np.stack(
        [np.asarray(range_curves_m[code], dtype=np.float64) for code in codes]
    )
    if matrix.shape != (TRACK_COUNT, RAW_EPOCHS) or not np.all(np.isfinite(matrix)):
        raise AllTrackGeometryScreenError("CODEBOOK_CURVE_INVALID")

    pair_rows: list[dict[str, object]] = []
    for left, right in combinations(range(TRACK_COUNT), 2):
        _, metrics = prefix_project([matrix[left] - matrix[right]])
        pair_rows.append(
            {
                "satellites": [codes[left], codes[right]],
                "heldout_peak_to_peak_m": float(
                    metrics["heldout_peak_to_peak_m_by_row"][0]
                ),
                "heldout_rms_m": float(metrics["heldout_rms_m_by_row"][0]),
            }
        )
    pair_rows.sort(
        key=lambda row: (
            float(row["heldout_peak_to_peak_m"]),
            list(row["satellites"]),
        )
    )
    nearest_pair = pair_rows[0]

    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    _, null_metrics = prefix_project(centered)
    null_ptp = [float(value) for value in null_metrics["heldout_peak_to_peak_m_by_row"]]
    null_maximum = max(null_ptp)
    null_controlling_index = min(
        index for index, value in enumerate(null_ptp) if value == null_maximum
    )
    affine_null = {
        "heldout_max_track_peak_to_peak_m": null_maximum,
        "aggregate_heldout_rms_m": float(null_metrics["aggregate_heldout_rms_m"]),
        "controlling_satellite": codes[null_controlling_index],
    }

    assignment_separation = float(nearest_pair["heldout_peak_to_peak_m"])
    if null_maximum <= assignment_separation:
        runner_class = "PREFIX_AFFINE_ONLY_NULL"
        controlling = null_maximum
        runner_detail: dict[str, object] = affine_null
    else:
        runner_class = "CLOSEST_NONIDENTITY_BIJECTION"
        controlling = assignment_separation
        runner_detail = nearest_pair
    robust_lower_bound = controlling - REQUIRED_EXACT_SEPARATION_M
    result = {
        "candidate_codebook": list(codes),
        "bijective_assignment_count": ASSIGNMENT_COUNT,
        "total_hypothesis_count": HYPOTHESIS_COUNT,
        "nearest_wrong_assignment": {
            "form": "SWAP_CLOSEST_PREFIX_PROJECTED_ORBIT_PAIR",
            **nearest_pair,
        },
        "prefix_affine_null": affine_null,
        "controlling_runner_class": runner_class,
        "controlling_runner": runner_detail,
        "exact_controlling_separation_m": controlling,
        "required_exact_separation_m": REQUIRED_EXACT_SEPARATION_M,
        "robust_scorer_margin_lower_bound_m": robust_lower_bound,
        "robustly_discriminative": robust_lower_bound > 0.0,
    }
    strict_json(result)
    matrix.fill(0.0)
    centered.fill(0.0)
    return result


def exhaustive_nonidentity_separation(
    range_curves_m: Mapping[str, Sequence[float]],
) -> float:
    """Regression helper: exhaust all 719 wrong bijections for six curves."""

    codes = tuple(sorted(range_curves_m))
    if len(codes) != TRACK_COUNT:
        raise AllTrackGeometryScreenError("CODEBOOK_MUST_HAVE_EXACTLY_SIX_TRACKS")
    matrix = np.stack([np.asarray(range_curves_m[code]) for code in codes])
    best = float("inf")
    identity = tuple(range(TRACK_COUNT))
    for order in permutations(range(TRACK_COUNT)):
        if order == identity:
            continue
        differences = matrix - matrix[list(order)]
        _, metrics = prefix_project(differences)
        score = max(float(value) for value in metrics["heldout_peak_to_peak_m_by_row"])
        best = min(best, score)
    if not np.isfinite(best):
        raise AllTrackGeometryScreenError("NO_NONIDENTITY_ASSIGNMENT")
    matrix.fill(0.0)
    return best


def classify_outcome(exact_six_windows: int, robust_windows: int) -> str:
    if exact_six_windows < 0 or robust_windows < 0:
        raise AllTrackGeometryScreenError("WINDOW_COUNT_INVALID")
    if robust_windows > exact_six_windows:
        raise AllTrackGeometryScreenError("ROBUST_WINDOW_COUNT_INVALID")
    if exact_six_windows == 0:
        return OUTCOME_NO_INCLUSION
    if robust_windows == 0:
        return OUTCOME_NO_GEOMETRY
    return OUTCOME_SHORTLISTED


def _window_rank_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        -float(row["robust_scorer_margin_lower_bound_m"]),
        -float(row["minimum_time_shifted_elevation_deg"]),
        str(row["station_id"]),
        int(row["doy"]),
        int(row["start_index"]),
    )


def compile_station_day(
    candidate: navigation.NavigationCandidate,
    station_candidate: StationCandidate,
    epochs: Sequence[datetime],
    nominal_positions: Mapping[str, np.ndarray],
    shifted_positions: Mapping[tuple[str, float], np.ndarray],
) -> dict[str, object]:
    station = _station(station_candidate)
    station_ecef = geometry.station_to_ecef(station)
    satellites = tuple(sorted(nominal_positions))
    possible_starts = len(epochs) - RAW_EPOCHS + 1
    kernel = np.ones(RAW_EPOCHS, dtype=np.int16)
    complete_rows: list[np.ndarray] = []
    robust_elevation: dict[str, np.ndarray] = {}
    nominal_range: dict[str, np.ndarray] = {}
    for satellite in satellites:
        elevations = []
        for offset in (
            -MAXIMUM_EVENT_TIME_ERROR_S,
            0.0,
            MAXIMUM_EVENT_TIME_ERROR_S,
        ):
            elevations.append(
                geometry.elevation_deg(
                    shifted_positions[(satellite, offset)], station, station_ecef
                )
            )
        robust = np.min(np.stack(elevations), axis=0)
        ranges = np.linalg.norm(nominal_positions[satellite] - station_ecef, axis=1)
        valid = np.isfinite(robust) & np.isfinite(ranges)
        complete = np.convolve(
            (valid & (robust >= MINIMUM_ELEVATION_DEG)).astype(np.int16),
            kernel,
            mode="valid",
        ) == RAW_EPOCHS
        if complete.shape != (possible_starts,):
            raise AllTrackGeometryScreenError("COMPLETE_WINDOW_SHAPE_INVALID")
        robust_elevation[satellite] = robust
        nominal_range[satellite] = ranges
        complete_rows.append(complete)

    complete_matrix = np.stack(complete_rows)
    counts = np.sum(complete_matrix, axis=0)
    exact_starts = np.flatnonzero(counts == TRACK_COUNT)
    rows: list[dict[str, object]] = []
    robust_rows: list[dict[str, object]] = []
    for start_value in exact_starts:
        start = int(start_value)
        stop = start + RAW_EPOCHS
        codebook = tuple(
            satellites[index]
            for index in np.flatnonzero(complete_matrix[:, start])
        )
        if len(codebook) != TRACK_COUNT:
            raise AllTrackGeometryScreenError("EXACT_SIX_VISIBILITY_INVARIANT_FAILED")
        evaluation = evaluate_codebook(
            {
                satellite: nominal_range[satellite][start:stop]
                for satellite in codebook
            }
        )
        row = {
            "station_id": station_candidate.station_id,
            "doy": candidate.doy,
            "gps_date": candidate.gps_date,
            "start_index": start,
            "raw_start_gps": geometry.format_gps(epochs[start]),
            "raw_stop_gps": geometry.format_gps(epochs[stop - 1]),
            "heldout_start_gps": geometry.format_gps(
                epochs[start + PREFIX_EPOCHS]
            ),
            "minimum_time_shifted_elevation_deg": min(
                float(np.min(robust_elevation[satellite][start:stop]))
                for satellite in codebook
            ),
            **evaluation,
        }
        rows.append(row)
        if bool(row["robustly_discriminative"]):
            robust_rows.append(row)

    robust_rows.sort(key=_window_rank_key)
    best_attempt = min(rows, key=_window_rank_key) if rows else None
    result = {
        "station_id": station_candidate.station_id,
        "doy": candidate.doy,
        "gps_date": candidate.gps_date,
        "healthy_gps_satellite_count": len(satellites),
        "possible_window_count": possible_starts,
        "minimum_complete_track_count": int(np.min(counts)),
        "maximum_complete_track_count": int(np.max(counts)),
        "exact_six_window_count": len(rows),
        "robust_exact_six_window_count": len(robust_rows),
        "selected_cell_window": robust_rows[0] if robust_rows else None,
        "best_attempt_descriptive_only": best_attempt,
    }
    for values in robust_elevation.values():
        values.fill(0.0)
    for values in nominal_range.values():
        values.fill(0.0)
    complete_matrix.fill(False)
    counts.fill(0)
    return result


def compile_day(
    candidate: navigation.NavigationCandidate,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
) -> dict[str, object]:
    epochs = gps_day_grid(candidate)
    satellites = tuple(
        satellite
        for satellite in sorted(records)
        if satellite.startswith("G") and len(satellite) == 3
    )
    if len(satellites) < TRACK_COUNT:
        raise AllTrackGeometryScreenError("TOO_FEW_HEALTHY_GPS_SATELLITES")
    offsets = (
        -MAXIMUM_EVENT_TIME_ERROR_S,
        0.0,
        MAXIMUM_EVENT_TIME_ERROR_S,
    )
    shifted_positions = {
        (satellite, offset): _position_series(records, satellite, epochs, offset)
        for satellite in satellites
        for offset in offsets
    }
    nominal_positions = {
        satellite: shifted_positions[(satellite, 0.0)] for satellite in satellites
    }
    station_results = [
        compile_station_day(
            candidate,
            station,
            epochs,
            nominal_positions,
            shifted_positions,
        )
        for station in STATIONS
    ]
    for values in shifted_positions.values():
        values.fill(0.0)
    return {
        "doy": candidate.doy,
        "gps_date": candidate.gps_date,
        "healthy_gps_satellites": list(satellites),
        "station_results": station_results,
    }


def compile_screen(payloads: Mapping[int, bytes], root: Path) -> dict[str, object]:
    scope = validate_scope(root)
    expected_doys = {candidate.doy for candidate in NAVIGATION_CANDIDATES}
    if set(payloads) != expected_doys:
        raise AllTrackGeometryScreenError("NAVIGATION_PAYLOAD_SET_CHANGED")
    day_results = []
    authorities = []
    for candidate in NAVIGATION_CANDIDATES:
        records, authority = navigation.parse_navigation_gzip(
            candidate, payloads[candidate.doy]
        )
        day_results.append(compile_day(candidate, records))
        authorities.append(authority)

    cells = [
        cell
        for day in day_results
        for cell in day["station_results"]
    ]
    exact_count = sum(int(cell["exact_six_window_count"]) for cell in cells)
    robust_count = sum(
        int(cell["robust_exact_six_window_count"]) for cell in cells
    )
    selected = [
        dict(cell["selected_cell_window"])
        for cell in cells
        if cell["selected_cell_window"] is not None
    ]
    selected.sort(key=_window_rank_key)
    shortlist = selected[:SHORTLIST_SIZE]
    outcome = classify_outcome(exact_count, robust_count)
    if (outcome == OUTCOME_SHORTLISTED) != bool(shortlist):
        raise AllTrackGeometryScreenError("OUTCOME_SHORTLIST_INCONSISTENT")
    result = {
        "schema": "gnss-all-track-geometry-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "scope": scope,
        "manifest_sha256": manifest_sha256(root),
        "navigation": authorities,
        "day_results": day_results,
        "exact_six_window_count": exact_count,
        "robust_exact_six_window_count": robust_count,
        "shortlist": shortlist,
        "outcome": outcome,
        "observation_access": {
            "locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoders": 0,
        },
        "navigation_payloads_retained": 0,
        "measurement_scored": False,
        "qualification_artifact_selected": False,
        "primary_selected": False,
        "prospective_plan_frozen": False,
        "maximum_authorized_claim": None,
        "next_maximum": (
            "REVIEW_BEFORE_ONE_STRUCTURAL_QUALIFICATION_ARTIFACT_SELECTION"
            if outcome == OUTCOME_SHORTLISTED
            else "ABANDON_FIXED_SIX_TRACK_ALL_TRACK_VERTICAL"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_DISCOVERY_OR_ACCESS",
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    if Path(path).exists():
        raise AllTrackGeometryScreenError("SCREEN_RECEIPT_ALREADY_EXISTS")
    Path(path).write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation-gzip", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, default=root / RECEIPT_NAME)
    args = parser.parse_args()
    supplied = {path.name: path for path in args.navigation_gzip}
    expected = {candidate.name: candidate for candidate in NAVIGATION_CANDIDATES}
    if len(supplied) != len(args.navigation_gzip) or set(supplied) != set(expected):
        raise SystemExit("SUPPLY_EXACTLY_THE_FIVE_FROZEN_NAVIGATION_PRODUCTS")
    payloads = {
        expected[name].doy: path.read_bytes() for name, path in supplied.items()
    }
    try:
        receipt = compile_screen(payloads, root)
    finally:
        payloads.clear()
    _write_json(args.output, receipt)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
