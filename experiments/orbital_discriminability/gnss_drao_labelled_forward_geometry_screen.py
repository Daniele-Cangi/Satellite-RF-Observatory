"""Orbit-only DRAO screen for one labelled forward GNSS vertical.

Only five predeclared broadcast-navigation payloads are inputs.  The compiler
has no observation locator, decoder, header, measurement value or primary
authority.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
import importlib.metadata
from itertools import combinations
import json
from math import sqrt
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as geometry
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)


SCREEN_VERSION: Final = "gnss-drao-labelled-forward-geometry-screen-v1"
SCOPE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_GEOMETRY_SCOPE.md"
SCOPE_SHA256: Final = "fee2577189e47460bd7efe210e978c00e756c376ed4d7241316d16af95f8cf1c"
RECEIPT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_GEOMETRY_SCREEN.json"

OUTCOME_SELECTED: Final = "DRAO_LABELLED_FORWARD_GEOMETRY_SHORTLISTED"
OUTCOME_NONE: Final = "NO_FORWARD_LABELLED_GEOMETRY_ADMITTED"

STEP_S: Final = 30.0
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
TRACK_COUNT: Final = 6
START_STRIDE_EPOCHS: Final = 10
MINIMUM_ELEVATION_DEG: Final = 15.0
MAXIMUM_EVENT_TIME_ERROR_S: Final = 15.0
HISTORICAL_DRAO_GUARD_M: Final = 7_339.701234647398
REQUIRED_EXACT_SEPARATION_M: Final = 3.0 * HISTORICAL_DRAO_GUARD_M
SHORTLIST_SIZE: Final = 3


@dataclass(frozen=True, slots=True)
class Station:
    station_id: str = "DRAO00CAN"
    latitude_deg: float = 49.322600
    longitude_deg: float = -119.625000
    height_m: float = 542.0
    domes: str = "40105M002"
    metadata_source: str = "FROZEN_IGS_METADATA_SNAPSHOT_2026_08_25"


STATION: Final = Station()

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
        (234, "2026-08-22"),
        (235, "2026-08-23"),
        (236, "2026-08-24"),
        (237, "2026-08-25"),
        (238, "2026-08-26"),
    )
)


class LabelledForwardGeometryError(ValueError):
    """The bounded orbit-only screen or one of its inputs is invalid."""


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


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def validate_scope(root: Path) -> dict[str, object]:
    path = Path(root) / SCOPE_NAME
    if not path.is_file() or canonical_sha256(path) != SCOPE_SHA256:
        raise LabelledForwardGeometryError("FROZEN_SCOPE_CHANGED")
    if tuple(candidate.doy for candidate in NAVIGATION_CANDIDATES) != tuple(
        range(234, 239)
    ):
        raise LabelledForwardGeometryError("NAVIGATION_SCOPE_CHANGED")
    return {"filename": SCOPE_NAME, "canonical_sha256": SCOPE_SHA256}


def manifest(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    result = {
        "schema": "gnss-drao-labelled-forward-geometry-screen-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "scope": validate_scope(base),
        "physical_question": (
            "DO_SIX_ORBIT_ONLY_SELECTED_LABELLED_GPS_CURVES_RETAIN_HELDOUT_"
            "SEPARATION_FROM_AFFINE_AND_TIME_REVERSED_NULLS_AT_DRAO"
        ),
        "new_information": (
            "ONE_REAL_ORBITAL_GEOMETRY_FOR_A_LATER_MODEL_CONDITIONED_FORWARD_TEST"
        ),
        "why_existing_cannot_answer": (
            "DOY233_IS_CONSUMED_AND_ITS_INVERSE_SURFACE_REFUSED_BEFORE_SCORE"
        ),
        "minimum_experiment": (
            "ONE_DRAO_OBSERVER_FIVE_PREDECLARED_NAVIGATION_DAYS_ZERO_"
            "OBSERVATION_PRODUCT_ACCESS"
        ),
        "stop_condition": (
            "STOP_AFTER_ONE_ORBIT_ONLY_SHORTLIST_OR_TYPED_NO_GEOMETRY_OUTCOME"
        ),
        "station": asdict(STATION),
        "navigation": [asdict(candidate) for candidate in NAVIGATION_CANDIDATES],
        "partition": {
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "start_stride_epochs": START_STRIDE_EPOCHS,
        },
        "visibility": {
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "direct_time_offsets_s": [
                -MAXIMUM_EVENT_TIME_ERROR_S,
                0.0,
                MAXIMUM_EVENT_TIME_ERROR_S,
            ],
            "minimum_joint_track_count": TRACK_COUNT,
            "extra_tracks": "DESCRIPTIVE_NOT_FATAL_NOT_SCORED",
        },
        "selection": {
            "source": "ORBIT_GEOMETRY_ONLY",
            "every_six_of_visible": True,
            "daily_winners": 1,
            "shortlist_size": SHORTLIST_SIZE,
            "observation_values_used": False,
        },
        "coordinate": "PER_EPOCH_ENSEMBLE_CENTERED_STATION_RANGE",
        "nulls": ["PREFIX_AFFINE_ONLY", "TIME_REVERSED_GEOMETRY"],
        "nuisance": {
            "per_centered_track": ["PREFIX_CONSTANT", "PREFIX_RATE"],
            "heldout_refit": False,
            "free_time_phase": False,
            "time_warp": False,
        },
        "screening_envelope": {
            "historical_drao_guard_m": HISTORICAL_DRAO_GUARD_M,
            "required_exact_separation_m": REQUIRED_EXACT_SEPARATION_M,
            "direct_time_shift_must_fit_guard": True,
            "date_specific_physical_admission": "STILL_REQUIRED",
        },
        "observation_boundary": {
            "locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoders": 0,
        },
        "maximum_future_claim": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "identity_independently_established": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(manifest(root)).encode("ascii")).hexdigest()


def _geometry_station() -> geometry.Station:
    return geometry.Station(
        STATION.station_id,
        STATION.latitude_deg,
        STATION.longitude_deg,
        STATION.height_m,
        "UNKNOWN_NOT_REQUIRED_FOR_ORBIT_SCREEN",
        "NOT_USED",
        "NOT_USED",
        "NOT_USED",
        f"{STATION.station_id}_{STATION.domes}",
        STATION.metadata_source,
    )


def gps_day_grid(candidate: navigation.NavigationCandidate) -> tuple[datetime, ...]:
    midnight = datetime.fromisoformat(candidate.gps_date).replace(tzinfo=timezone.utc)
    first_utc = midnight - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    return tuple(
        first_utc + timedelta(seconds=index * STEP_S) for index in range(2_880)
    )


def parse_navigation_gzip(
    candidate: navigation.NavigationCandidate, payload: bytes | bytearray
) -> tuple[dict[str, tuple[geometry.GpsEphemeris, ...]], dict[str, object]]:
    if not payload:
        raise LabelledForwardGeometryError(f"NAVIGATION_EMPTY_DOY_{candidate.doy}")
    compressed = bytes(payload)
    compressed_sha256 = sha256(compressed).hexdigest()
    try:
        raw = gzip.decompress(compressed)
    except (EOFError, OSError) as exc:
        raise LabelledForwardGeometryError(
            f"NAVIGATION_GZIP_INVALID_DOY_{candidate.doy}"
        ) from exc
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise LabelledForwardGeometryError(
            f"NAVIGATION_ASCII_INVALID_DOY_{candidate.doy}"
        ) from exc
    try:
        start = next(
            index for index, line in enumerate(lines) if "END OF HEADER" in line
        ) + 1
    except StopIteration as exc:
        raise LabelledForwardGeometryError(
            f"NAVIGATION_HEADER_INCOMPLETE_DOY_{candidate.doy}"
        ) from exc

    parsed: dict[str, list[geometry.GpsEphemeris]] = {}
    for index in range(start, len(lines)):
        if not lines[index][:2].strip().isdigit():
            continue
        if index + 7 >= len(lines):
            raise LabelledForwardGeometryError(
                f"NAVIGATION_RECORD_TRUNCATED_DOY_{candidate.doy}"
            )
        record = navigation.parse_rinex2_gps_record(lines[index : index + 8])
        if record.sv_health == 0 and 0.0 <= record.eccentricity < 1.0:
            parsed.setdefault(record.satellite, []).append(record)
    records = {
        satellite: tuple(sorted(values, key=lambda value: value.toc_gps))
        for satellite, values in parsed.items()
    }
    if len(records) < TRACK_COUNT:
        raise LabelledForwardGeometryError(
            f"TOO_FEW_HEALTHY_GPS_SATELLITES_DOY_{candidate.doy}"
        )
    authority = {
        **asdict(candidate),
        "compressed_bytes": len(compressed),
        "compressed_sha256": compressed_sha256,
        "uncompressed_name": candidate.name.removesuffix(".gz"),
        "uncompressed_bytes": len(raw),
        "uncompressed_sha256": sha256(raw).hexdigest(),
        "healthy_gps_satellite_count": len(records),
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }
    raw = b""
    compressed = b""
    return records, authority


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
        raise LabelledForwardGeometryError("PREFIX_MATRIX_SHAPE_INVALID")
    if not np.all(np.isfinite(values)):
        raise LabelledForwardGeometryError("PREFIX_MATRIX_NONFINITE")
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    prefix_x = elapsed[:PREFIX_EPOCHS]
    centered_x = prefix_x - float(np.mean(prefix_x))
    denominator = float(centered_x @ centered_x)
    prefix = values[:, :PREFIX_EPOCHS]
    means = np.mean(prefix, axis=1)
    rates = ((prefix - means[:, None]) @ centered_x) / denominator
    constants = means - rates * float(np.mean(prefix_x))
    residual = values - constants[:, None] - rates[:, None] * elapsed[None, :]
    heldout = residual[:, PREFIX_EPOCHS:]
    metrics = {
        "heldout_peak_to_peak_m_by_track": [float(np.ptp(row)) for row in heldout],
        "heldout_rms_m": sqrt(float(np.mean(heldout * heldout))),
    }
    return residual, metrics


def _null_score(matrix: np.ndarray) -> dict[str, float]:
    residual, metrics = prefix_project(matrix)
    peak = max(float(value) for value in metrics["heldout_peak_to_peak_m_by_track"])
    residual.fill(0.0)
    return {"heldout_max_track_peak_to_peak_m": peak, "heldout_rms_m": float(metrics["heldout_rms_m"])}


def evaluate_codebook(
    range_curves_m: Mapping[str, Sequence[float]],
    shifted_range_curves_m: Mapping[tuple[str, float], Sequence[float]],
) -> dict[str, object]:
    codes = tuple(sorted(range_curves_m))
    if len(codes) != TRACK_COUNT:
        raise LabelledForwardGeometryError("CODEBOOK_MUST_HAVE_SIX_TRACKS")
    nominal = np.stack([np.asarray(range_curves_m[code], dtype=np.float64) for code in codes])
    if nominal.shape != (TRACK_COUNT, RAW_EPOCHS) or not np.all(np.isfinite(nominal)):
        raise LabelledForwardGeometryError("CODEBOOK_CURVE_INVALID")
    centered = nominal - np.mean(nominal, axis=0, keepdims=True)
    affine = _null_score(centered)
    reversed_geometry = centered[:, ::-1].copy()
    time_reversed = _null_score(centered - reversed_geometry)

    timing_rows = []
    for offset in (-MAXIMUM_EVENT_TIME_ERROR_S, MAXIMUM_EVENT_TIME_ERROR_S):
        shifted = np.stack(
            [np.asarray(shifted_range_curves_m[(code, offset)], dtype=np.float64) for code in codes]
        )
        if shifted.shape != nominal.shape or not np.all(np.isfinite(shifted)):
            raise LabelledForwardGeometryError("SHIFTED_CODEBOOK_CURVE_INVALID")
        shifted_centered = shifted - np.mean(shifted, axis=0, keepdims=True)
        score = _null_score(centered - shifted_centered)
        timing_rows.append({"offset_s": offset, **score})
        shifted.fill(0.0)
        shifted_centered.fill(0.0)

    controlling_name, controlling = min(
        (("PREFIX_AFFINE_ONLY", affine), ("TIME_REVERSED_GEOMETRY", time_reversed)),
        key=lambda item: (item[1]["heldout_max_track_peak_to_peak_m"], item[0]),
    )
    exact = float(controlling["heldout_max_track_peak_to_peak_m"])
    timing_envelope = max(
        float(row["heldout_max_track_peak_to_peak_m"]) for row in timing_rows
    )
    robust_lower = exact - REQUIRED_EXACT_SEPARATION_M
    result = {
        "candidate_codebook": list(codes),
        "prefix_affine_null": affine,
        "time_reversed_geometry_null": time_reversed,
        "controlling_null": controlling_name,
        "exact_controlling_separation_m": exact,
        "direct_time_shift_rows": timing_rows,
        "direct_time_shift_envelope_m": timing_envelope,
        "historical_drao_guard_m": HISTORICAL_DRAO_GUARD_M,
        "required_exact_separation_m": REQUIRED_EXACT_SEPARATION_M,
        "robust_margin_lower_bound_m": robust_lower,
        "robustly_discriminative": (
            robust_lower > 0.0 and timing_envelope <= HISTORICAL_DRAO_GUARD_M
        ),
    }
    strict_json(result)
    nominal.fill(0.0)
    centered.fill(0.0)
    reversed_geometry.fill(0.0)
    return result


def _rank_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        -float(row["robust_margin_lower_bound_m"]),
        -float(row["minimum_time_shifted_elevation_deg"]),
        int(row["doy"]),
        int(row["start_index"]),
        tuple(row["candidate_codebook"]),
    )


def compile_day(
    candidate: navigation.NavigationCandidate,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
) -> dict[str, object]:
    epochs = gps_day_grid(candidate)
    station = _geometry_station()
    station_ecef = geometry.station_to_ecef(station)
    satellites = tuple(sorted(records))
    offsets = (-MAXIMUM_EVENT_TIME_ERROR_S, 0.0, MAXIMUM_EVENT_TIME_ERROR_S)
    positions = {
        (satellite, offset): _position_series(records, satellite, epochs, offset)
        for satellite in satellites
        for offset in offsets
    }
    ranges = {
        key: np.linalg.norm(value - station_ecef, axis=1)
        for key, value in positions.items()
    }
    robust_elevation: dict[str, np.ndarray] = {}
    complete_rows = []
    kernel = np.ones(RAW_EPOCHS, dtype=np.int16)
    for satellite in satellites:
        elevation_rows = [
            geometry.elevation_deg(positions[(satellite, offset)], station, station_ecef)
            for offset in offsets
        ]
        robust = np.min(np.stack(elevation_rows), axis=0)
        valid = np.isfinite(robust) & np.isfinite(ranges[(satellite, 0.0)])
        complete = np.convolve(
            (valid & (robust >= MINIMUM_ELEVATION_DEG)).astype(np.int16),
            kernel,
            mode="valid",
        ) == RAW_EPOCHS
        robust_elevation[satellite] = robust
        complete_rows.append(complete)

    complete_matrix = np.stack(complete_rows)
    counts = np.sum(complete_matrix, axis=0)
    candidates: list[dict[str, object]] = []
    combination_evaluations = 0
    for start in range(0, len(counts), START_STRIDE_EPOCHS):
        visible_indices = tuple(int(value) for value in np.flatnonzero(complete_matrix[:, start]))
        if len(visible_indices) < TRACK_COUNT:
            continue
        stop = start + RAW_EPOCHS
        for chosen_indices in combinations(visible_indices, TRACK_COUNT):
            combination_evaluations += 1
            codebook = tuple(satellites[index] for index in chosen_indices)
            evaluated = evaluate_codebook(
                {code: ranges[(code, 0.0)][start:stop] for code in codebook},
                {
                    (code, offset): ranges[(code, offset)][start:stop]
                    for code in codebook
                    for offset in (-MAXIMUM_EVENT_TIME_ERROR_S, MAXIMUM_EVENT_TIME_ERROR_S)
                },
            )
            row = {
                "station_id": STATION.station_id,
                "doy": candidate.doy,
                "gps_date": candidate.gps_date,
                "start_index": start,
                "raw_start_gps": geometry.format_gps(epochs[start]),
                "raw_stop_gps": geometry.format_gps(epochs[stop - 1]),
                "heldout_start_gps": geometry.format_gps(epochs[start + PREFIX_EPOCHS]),
                "jointly_visible_track_count": len(visible_indices),
                "minimum_time_shifted_elevation_deg": min(
                    float(np.min(robust_elevation[code][start:stop])) for code in codebook
                ),
                **evaluated,
            }
            candidates.append(row)

    robust = [row for row in candidates if bool(row["robustly_discriminative"])]
    robust.sort(key=_rank_key)
    candidates.sort(key=_rank_key)
    result = {
        "doy": candidate.doy,
        "gps_date": candidate.gps_date,
        "healthy_gps_satellite_count": len(satellites),
        "sampled_window_count": len(range(0, len(counts), START_STRIDE_EPOCHS)),
        "windows_with_at_least_six_visible": int(
            np.sum(counts[::START_STRIDE_EPOCHS] >= TRACK_COUNT)
        ),
        "minimum_complete_track_count": int(np.min(counts)),
        "maximum_complete_track_count": int(np.max(counts)),
        "combination_evaluations": combination_evaluations,
        "robust_candidate_count": len(robust),
        "selected_daily_window": robust[0] if robust else None,
        "best_attempt_descriptive_only": candidates[0] if candidates else None,
    }
    for value in positions.values():
        value.fill(0.0)
    for value in ranges.values():
        value.fill(0.0)
    for value in robust_elevation.values():
        value.fill(0.0)
    complete_matrix.fill(False)
    counts.fill(0)
    return result


def compile_screen(payloads: Mapping[int, bytes | bytearray], root: Path) -> dict[str, object]:
    scope = validate_scope(root)
    expected = {candidate.doy for candidate in NAVIGATION_CANDIDATES}
    if set(payloads) != expected:
        raise LabelledForwardGeometryError("NAVIGATION_PAYLOAD_SET_CHANGED")
    days = []
    authorities = []
    for candidate in NAVIGATION_CANDIDATES:
        records, authority = parse_navigation_gzip(candidate, payloads[candidate.doy])
        days.append(compile_day(candidate, records))
        authorities.append(authority)
    selected = [
        dict(day["selected_daily_window"])
        for day in days
        if day["selected_daily_window"] is not None
    ]
    selected.sort(key=_rank_key)
    shortlist = selected[:SHORTLIST_SIZE]
    outcome = OUTCOME_SELECTED if shortlist else OUTCOME_NONE
    result = {
        "schema": "gnss-drao-labelled-forward-geometry-screen-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
        },
        "scope": scope,
        "manifest_sha256": manifest_sha256(root),
        "navigation": authorities,
        "day_results": days,
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
        "primary_selected": False,
        "prospective_plan_frozen": False,
        "maximum_authorized_claim": None,
        "next_maximum": (
            "DATE_CODEBOOK_SPECIFIC_PHYSICAL_ENVELOPE_AUDIT"
            if shortlist
            else "ABANDON_DRAO_LABELLED_FORWARD_ROUTE"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_QUERY_SELECTION_OR_ACCESS",
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    if Path(path).exists():
        raise LabelledForwardGeometryError("SCREEN_RECEIPT_ALREADY_EXISTS")
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
        expected[name].doy: bytearray(path.read_bytes()) for name, path in supplied.items()
    }
    try:
        receipt = compile_screen(payloads, root)
    finally:
        for payload in payloads.values():
            payload[:] = b"\x00" * len(payload)
        payloads.clear()
    _write_json(args.output, receipt)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
