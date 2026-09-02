"""Orbit-only DORIS geometry spike for a future Sentinel-3A RINEX day.

This dedicated calculation consumes three pre-observation CNES extrapolated
SP3 products: the current Sentinel-3A forecast, its preceding forecast, and a
Sentinel-3B physical alternative.  It never opens a DORIS RINEX observation.
Station coordinates are the deliberately coarse, bounded public IDS table
coordinates; exact DPOD coordinates remain a later admission requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
from math import cos, radians, sin, sqrt
from pathlib import Path
from typing import Iterable, Mapping

import ncompress
import numpy as np

from experiments.live_instrument.models import strict_json_value


C_MPS = 299_792_458.0
DORIS_S_BAND_HZ = 2_036_250_000.0
TAI_MINUS_UTC_S = 37.0
INTERPOLATION_STEP_S = 10.0
MIN_ELEVATION_DEG = 10.0
MIN_JOINT_INTERVAL_S = 360.0
CALIBRATION_FRACTION = 0.25
MIN_CALIBRATION_S = 120.0
MIN_HELDOUT_S = 240.0
CANDIDATE_DAY_UTC = date(2026, 9, 2)  # DOY 245; no observation role is frozen.
FROZEN_ALONG_TRACK_SHIFTS_S = (-60.0, 60.0)

CURRENT_S3A_NAME = "exts3a30.b26243.e26246.D__.sp3.001.Z"
CURRENT_S3A_SHA256 = "1f8662c0d77b4fbc08dc35121108eb18a70cf22a94185944da652b06dfd97376"
CURRENT_S3A_BYTES = 278_021
PRIOR_S3A_NAME = "exts3a30.b26242.e26245.D__.sp3.001.Z"
PRIOR_S3A_SHA256 = "17cd7dfa11016f7e389237572190cd02530966764ebce36cbd2c12d0d00ebf7a"
PRIOR_S3A_BYTES = 280_545
ALTERNATIVE_S3B_NAME = "exts3b30.b26243.e26246.D__.sp3.001.Z"
ALTERNATIVE_S3B_SHA256 = "5c80e1374b9d2185b476c70ff51d8f46e2def0fba84ff7bef6f31b24ed4870e1"
ALTERNATIVE_S3B_BYTES = 279_938


class DorisGeometryError(ValueError):
    """Raised when a frozen orbit-only input violates the spike contract."""


@dataclass(frozen=True, slots=True)
class Station:
    code: str
    latitude_deg: float
    longitude_deg: float
    source_resolution_arcmin: float = 1.0
    height_m: float = 0.0


@dataclass(frozen=True, slots=True)
class Sp3Trajectory:
    satellite_id: str
    start_tai: datetime
    times_tai_s: np.ndarray
    positions_m: np.ndarray
    velocities_mps: np.ndarray
    header: str


# Four physically predeclared regional pairs.  Each contains a current DORIS
# beacon pair close enough for plausible simultaneous LEO visibility.  The
# values are exactly the minute-resolution coordinates published in the IDS
# public station table, not invented survey coordinates.
STATIONS: Mapping[str, Station] = {
    "TLSB": Station("TLSB", 43.0 + 33.0 / 60.0, 1.0 + 29.0 / 60.0),
    "GR4B": Station("GR4B", 43.0 + 45.0 / 60.0, 6.0 + 55.0 / 60.0),
    "WEUC": Station("WEUC", 49.0 + 9.0 / 60.0, 12.0 + 53.0 / 60.0),
    "DIOB": Station("DIOB", 38.0 + 5.0 / 60.0, 23.0 + 56.0 / 60.0),
    "PAUB": Station("PAUB", -(17.0 + 35.0 / 60.0), -(149.0 + 36.0 / 60.0)),
    "RIMC": Station("RIMC", -(23.0 + 8.0 / 60.0), -(134.0 + 58.0 / 60.0)),
    "KRWB": Station("KRWB", 5.0 + 6.0 / 60.0, -(52.0 + 38.0 / 60.0)),
    "LAPB": Station("LAPB", 14.0 + 36.0 / 60.0, -61.0),
}

PAIRS: tuple[tuple[str, str], ...] = (
    ("TLSB", "GR4B"),
    ("TLSB", "WEUC"),
    ("PAUB", "RIMC"),
    ("KRWB", "LAPB"),
)


def parse_frozen_sp3_z(
    path: Path,
    *,
    expected_name: str,
    expected_sha256: str,
    expected_satellite_id: str,
) -> Sp3Trajectory:
    """Hash, decompress in memory, and parse one exact CNES EXT SP3 product."""

    path = Path(path)
    if path.name != expected_name:
        raise DorisGeometryError("SP3 filename differs from frozen product")
    compressed = path.read_bytes()
    digest = sha256(compressed).hexdigest()
    if digest != expected_sha256:
        raise DorisGeometryError("SP3 SHA-256 differs from frozen product")
    try:
        lines = ncompress.decompress(compressed).decode("ascii").splitlines()
    except (ValueError, UnicodeDecodeError) as error:
        raise DorisGeometryError("SP3 .Z payload cannot be decoded") from error
    if not lines or " ORBIT ITRF  EXT CNES" not in lines[0]:
        raise DorisGeometryError("SP3 is not a CNES extrapolated ITRF orbit")
    if not any(line.startswith("%c ") and "TAI" in line for line in lines):
        raise DorisGeometryError("SP3 time system is not declared TAI")

    epochs: list[datetime] = []
    positions: list[tuple[float, float, float]] = []
    velocities: list[tuple[float, float, float]] = []
    pending_epoch: datetime | None = None
    pending_position: tuple[float, float, float] | None = None
    observed_satellite_ids: set[str] = set()
    for line in lines:
        if line.startswith("*"):
            parts = line[1:].split()
            if len(parts) != 6:
                raise DorisGeometryError("malformed SP3 epoch")
            second = float(parts[5])
            whole_second = int(second)
            pending_epoch = datetime(
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                int(parts[3]),
                int(parts[4]),
                whole_second,
                round((second - whole_second) * 1_000_000),
                tzinfo=timezone.utc,
            )
            pending_position = None
        elif line.startswith("P"):
            observed_satellite_ids.add(line[1:4])
            pending_position = tuple(
                float(line[start : start + 14]) * 1000.0
                for start in (4, 18, 32)
            )
        elif line.startswith("V"):
            satellite_id = line[1:4]
            observed_satellite_ids.add(satellite_id)
            if pending_epoch is None or pending_position is None:
                raise DorisGeometryError("SP3 velocity lacks matching epoch/position")
            velocity = tuple(
                float(line[start : start + 14]) * 0.1
                for start in (4, 18, 32)
            )
            epochs.append(pending_epoch)
            positions.append(pending_position)
            velocities.append(velocity)
            pending_epoch = None
            pending_position = None

    if observed_satellite_ids != {expected_satellite_id}:
        raise DorisGeometryError("SP3 satellite identity differs from frozen product")
    if len(epochs) < 2 or len(epochs) != len(positions) or len(epochs) != len(velocities):
        raise DorisGeometryError("SP3 trajectory is incomplete")
    start = epochs[0]
    times = np.array([(epoch - start).total_seconds() for epoch in epochs], dtype=float)
    if not np.allclose(np.diff(times), 60.0, rtol=0.0, atol=1.0e-6):
        raise DorisGeometryError("SP3 cadence is not the frozen 60 seconds")
    return Sp3Trajectory(
        satellite_id=expected_satellite_id,
        start_tai=start,
        times_tai_s=times,
        positions_m=np.asarray(positions, dtype=float),
        velocities_mps=np.asarray(velocities, dtype=float),
        header=lines[0],
    )


def interpolate_hermite(
    trajectory: Sp3Trajectory, requested_tai_s: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Interpolate position and velocity on the exact requested TAI grid."""

    requested = np.asarray(requested_tai_s, dtype=float)
    source = trajectory.times_tai_s
    if requested.ndim != 1 or requested.size == 0:
        raise DorisGeometryError("requested interpolation grid is empty")
    if requested[0] < source[0] or requested[-1] > source[-1]:
        raise DorisGeometryError("requested grid exceeds SP3 support")
    index = np.searchsorted(source, requested, side="right") - 1
    index = np.clip(index, 0, source.size - 2)
    t0 = source[index]
    t1 = source[index + 1]
    duration = t1 - t0
    u = (requested - t0) / duration
    p0 = trajectory.positions_m[index]
    p1 = trajectory.positions_m[index + 1]
    v0 = trajectory.velocities_mps[index]
    v1 = trajectory.velocities_mps[index + 1]
    u2 = u * u
    u3 = u2 * u
    h00 = 2.0 * u3 - 3.0 * u2 + 1.0
    h10 = u3 - 2.0 * u2 + u
    h01 = -2.0 * u3 + 3.0 * u2
    h11 = u3 - u2
    position = (
        h00[:, None] * p0
        + h10[:, None] * duration[:, None] * v0
        + h01[:, None] * p1
        + h11[:, None] * duration[:, None] * v1
    )
    dh00 = (6.0 * u2 - 6.0 * u) / duration
    dh10 = 3.0 * u2 - 4.0 * u + 1.0
    dh01 = (-6.0 * u2 + 6.0 * u) / duration
    dh11 = 3.0 * u2 - 2.0 * u
    velocity = (
        dh00[:, None] * p0
        + dh10[:, None] * v0
        + dh01[:, None] * p1
        + dh11[:, None] * v1
    )
    return position, velocity


def station_ecef(station: Station) -> tuple[np.ndarray, np.ndarray]:
    """Return WGS84 ECEF position and geodetic up vector."""

    a = 6_378_137.0
    flattening = 1.0 / 298.257_223_563
    eccentricity_sq = flattening * (2.0 - flattening)
    latitude = radians(station.latitude_deg)
    longitude = radians(station.longitude_deg)
    sin_latitude = sin(latitude)
    cos_latitude = cos(latitude)
    normal_radius = a / sqrt(1.0 - eccentricity_sq * sin_latitude**2)
    position = np.array(
        [
            (normal_radius + station.height_m) * cos_latitude * cos(longitude),
            (normal_radius + station.height_m) * cos_latitude * sin(longitude),
            (normal_radius * (1.0 - eccentricity_sq) + station.height_m)
            * sin_latitude,
        ],
        dtype=float,
    )
    up = np.array(
        [cos_latitude * cos(longitude), cos_latitude * sin(longitude), sin_latitude],
        dtype=float,
    )
    return position, up


def station_coordinate(
    station: Station, satellite_position_m: np.ndarray, satellite_velocity_mps: np.ndarray
) -> dict[str, np.ndarray]:
    station_position, up = station_ecef(station)
    line_of_sight = satellite_position_m - station_position
    ranges = np.linalg.norm(line_of_sight, axis=1)
    unit = line_of_sight / ranges[:, None]
    elevation = np.degrees(np.arcsin(np.clip(unit @ up, -1.0, 1.0)))
    range_rate = np.sum(unit * satellite_velocity_mps, axis=1)
    fractional_doppler = -range_rate / C_MPS
    return {
        "elevation_deg": elevation,
        "range_m": ranges,
        "range_rate_mps": range_rate,
        "fractional_doppler": fractional_doppler,
        "s_band_doppler_hz": fractional_doppler * DORIS_S_BAND_HZ,
    }


def contiguous_true_segments(mask: np.ndarray) -> list[tuple[int, int]]:
    """Return inclusive contiguous true-index intervals."""

    indices = np.flatnonzero(mask)
    if not indices.size:
        return []
    breaks = np.flatnonzero(np.diff(indices) != 1) + 1
    chunks = np.split(indices, breaks)
    return [(int(chunk[0]), int(chunk[-1])) for chunk in chunks]


def prefix_affine_residual(values: np.ndarray, calibration_count: int) -> np.ndarray:
    """Fit offset/rate on a prefix and return untouched suffix residuals."""

    if calibration_count < 3 or calibration_count >= values.size:
        raise DorisGeometryError("invalid calibration split")
    time = np.arange(values.size, dtype=float) * INTERPOLATION_STEP_S
    design = np.column_stack((np.ones(calibration_count), time[:calibration_count]))
    coefficients, *_ = np.linalg.lstsq(design, values[:calibration_count], rcond=None)
    prediction = coefficients[0] + coefficients[1] * time
    return values[calibration_count:] - prediction[calibration_count:]


def _peak_to_peak(values: np.ndarray) -> float:
    return float(np.max(values) - np.min(values))


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(values))))


def evaluate_geometry(
    current: Sp3Trajectory,
    prior: Sp3Trajectory,
    alternative: Sp3Trajectory,
) -> dict[str, object]:
    """Rank future joint-visibility intervals without observation access."""

    day_start_utc = datetime.combine(CANDIDATE_DAY_UTC, datetime.min.time(), timezone.utc)
    day_end_utc = day_start_utc + timedelta(days=1)
    day_start_tai = day_start_utc + timedelta(seconds=TAI_MINUS_UTC_S)
    day_end_tai = day_end_utc + timedelta(seconds=TAI_MINUS_UTC_S)
    support_starts = (
        current.start_tai + timedelta(seconds=float(current.times_tai_s[0])),
        prior.start_tai + timedelta(seconds=float(prior.times_tai_s[0])),
        alternative.start_tai + timedelta(seconds=float(alternative.times_tai_s[0])),
    )
    support_ends = (
        current.start_tai + timedelta(seconds=float(current.times_tai_s[-1])),
        prior.start_tai + timedelta(seconds=float(prior.times_tai_s[-1])),
        alternative.start_tai + timedelta(seconds=float(alternative.times_tai_s[-1])),
    )
    common_start_tai = max(day_start_tai, *support_starts)
    common_end_tai = min(day_end_tai, *support_ends)
    if common_end_tai <= common_start_tai:
        raise DorisGeometryError("forecast products do not overlap the primary day")
    start_s = (common_start_tai - current.start_tai).total_seconds()
    end_s = (common_end_tai - current.start_tai).total_seconds()
    grid = np.arange(
        start_s,
        end_s + INTERPOLATION_STEP_S * 0.5,
        INTERPOLATION_STEP_S,
        dtype=float,
    )
    utc = np.array(
        [
            current.start_tai
            + timedelta(seconds=float(value) - TAI_MINUS_UTC_S)
            for value in grid
        ],
        dtype=object,
    )
    current_position, current_velocity = interpolate_hermite(current, grid)
    prior_grid = np.array(
        [
            (
                current.start_tai
                + timedelta(seconds=float(value))
                - prior.start_tai
            ).total_seconds()
            for value in grid
        ],
        dtype=float,
    )
    alternative_grid = np.array(
        [
            (
                current.start_tai
                + timedelta(seconds=float(value))
                - alternative.start_tai
            ).total_seconds()
            for value in grid
        ],
        dtype=float,
    )
    prior_position, prior_velocity = interpolate_hermite(prior, prior_grid)
    alt_position, alt_velocity = interpolate_hermite(alternative, alternative_grid)
    current_coordinates = {
        code: station_coordinate(station, current_position, current_velocity)
        for code, station in STATIONS.items()
    }
    prior_coordinates = {
        code: station_coordinate(station, prior_position, prior_velocity)
        for code, station in STATIONS.items()
    }
    alternative_coordinates = {
        code: station_coordinate(station, alt_position, alt_velocity)
        for code, station in STATIONS.items()
    }

    candidates: list[dict[str, object]] = []
    for left, right in PAIRS:
        joint = (
            (current_coordinates[left]["elevation_deg"] >= MIN_ELEVATION_DEG)
            & (current_coordinates[right]["elevation_deg"] >= MIN_ELEVATION_DEG)
        )
        for start_index, end_index in contiguous_true_segments(joint):
            count = end_index - start_index + 1
            duration_s = (count - 1) * INTERPOLATION_STEP_S
            if duration_s < MIN_JOINT_INTERVAL_S:
                continue
            calibration_count = max(
                int(np.ceil(count * CALIBRATION_FRACTION)),
                int(MIN_CALIBRATION_S / INTERPOLATION_STEP_S) + 1,
            )
            heldout_duration_s = (count - calibration_count) * INTERPOLATION_STEP_S
            if heldout_duration_s < MIN_HELDOUT_S:
                continue
            selection = slice(start_index, end_index + 1)
            current_delta = (
                current_coordinates[left]["s_band_doppler_hz"][selection]
                - current_coordinates[right]["s_band_doppler_hz"][selection]
            )
            prior_delta = (
                prior_coordinates[left]["s_band_doppler_hz"][selection]
                - prior_coordinates[right]["s_band_doppler_hz"][selection]
            )
            alternative_delta = (
                alternative_coordinates[left]["s_band_doppler_hz"][selection]
                - alternative_coordinates[right]["s_band_doppler_hz"][selection]
            )
            affine_residual = prefix_affine_residual(current_delta, calibration_count)
            forecast_residual = prefix_affine_residual(
                current_delta - prior_delta, calibration_count
            )
            wrong_orbit_residual = prefix_affine_residual(
                current_delta - alternative_delta, calibration_count
            )
            along_track_separations: dict[str, float] = {}
            for shift_s in FROZEN_ALONG_TRACK_SHIFTS_S:
                offset = int(round(shift_s / INTERPOLATION_STEP_S))
                shifted_start = start_index + offset
                shifted_end = end_index + offset
                if shifted_start < 0 or shifted_end >= grid.size:
                    raise DorisGeometryError("frozen along-track alternative exceeds grid")
                shifted_selection = slice(shifted_start, shifted_end + 1)
                shifted_delta = (
                    current_coordinates[left]["s_band_doppler_hz"][shifted_selection]
                    - current_coordinates[right]["s_band_doppler_hz"][shifted_selection]
                )
                shifted_residual = prefix_affine_residual(
                    current_delta - shifted_delta, calibration_count
                )
                along_track_separations[f"{shift_s:+.0f}"] = _peak_to_peak(
                    shifted_residual
                )
            affine_separation = _peak_to_peak(affine_residual)
            wrong_orbit_separation = _peak_to_peak(wrong_orbit_residual)
            closest_along_track_separation = min(along_track_separations.values())
            forecast_envelope = _peak_to_peak(forecast_residual)
            controlling_separation = min(
                affine_separation, closest_along_track_separation
            )
            preliminary_margin = controlling_separation - forecast_envelope
            candidates.append(
                {
                    "pair": [left, right],
                    "joint_start_utc": utc[start_index].isoformat(),
                    "joint_end_utc": utc[end_index].isoformat(),
                    "joint_duration_s": duration_s,
                    "calibration_count": calibration_count,
                    "calibration_end_utc": utc[
                        start_index + calibration_count - 1
                    ].isoformat(),
                    "heldout_count": count - calibration_count,
                    "heldout_duration_s": heldout_duration_s,
                    "minimum_elevation_deg": float(
                        min(
                            np.min(current_coordinates[left]["elevation_deg"][selection]),
                            np.min(current_coordinates[right]["elevation_deg"][selection]),
                        )
                    ),
                    "differential_doppler_peak_to_peak_hz": _peak_to_peak(
                        current_delta
                    ),
                    "affine_null_heldout_peak_to_peak_hz": affine_separation,
                    "wrong_orbit_heldout_peak_to_peak_hz": wrong_orbit_separation,
                    "along_track_alternative_heldout_peak_to_peak_hz": (
                        along_track_separations
                    ),
                    "closest_along_track_heldout_peak_to_peak_hz": (
                        closest_along_track_separation
                    ),
                    "forecast_non_affine_envelope_peak_to_peak_hz": forecast_envelope,
                    "forecast_non_affine_envelope_rms_hz": _rms(forecast_residual),
                    "controlling_geometry_separation_hz": controlling_separation,
                    "preliminary_geometry_margin_hz": preliminary_margin,
                }
            )
    ranked = sorted(
        candidates,
        key=lambda item: float(item["preliminary_geometry_margin_hz"]),
        reverse=True,
    )
    receipt: dict[str, object] = {
        "outcome": (
            "DORIS_FORWARD_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED"
            if ranked and float(ranked[0]["preliminary_geometry_margin_hz"]) > 0.0
            else "DORIS_FORWARD_GEOMETRY_NOT_DISCRIMINATIVE"
        ),
        "physical_question": (
            "Can a pre-pass Sentinel-3A orbit predict simultaneous, beacon-dependent "
            "DORIS S-band phase dynamics better than affine and wrong-orbit alternatives?"
        ),
        "candidate": {
            "satellite": "Sentinel-3A",
            "cospar": "2016-011A",
            "norad": 41335,
            "candidate_day_utc": CANDIDATE_DAY_UTC.isoformat(),
            "orbit_product": CURRENT_S3A_NAME,
            "orbit_sha256": CURRENT_S3A_SHA256,
            "orbit_class": "CNES_EXTRAPOLATED_PRE_OBSERVATION",
        },
        "forecast_envelope_product": {
            "name": PRIOR_S3A_NAME,
            "sha256": PRIOR_S3A_SHA256,
        },
        "physical_alternative": {
            "satellite": "Sentinel-3B",
            "product": ALTERNATIVE_S3B_NAME,
            "sha256": ALTERNATIVE_S3B_SHA256,
        },
        "input_artifacts": [
            {
                "name": CURRENT_S3A_NAME,
                "bytes": CURRENT_S3A_BYTES,
                "sha256": CURRENT_S3A_SHA256,
                "role": "CURRENT_PRE_OBSERVATION_S3A_FORECAST",
            },
            {
                "name": PRIOR_S3A_NAME,
                "bytes": PRIOR_S3A_BYTES,
                "sha256": PRIOR_S3A_SHA256,
                "role": "PRIOR_S3A_FORECAST_ENVELOPE",
            },
            {
                "name": ALTERNATIVE_S3B_NAME,
                "bytes": ALTERNATIVE_S3B_BYTES,
                "sha256": ALTERNATIVE_S3B_SHA256,
                "role": "PHYSICALLY_DISTINCT_WRONG_ORBIT_ALTERNATIVE",
            },
        ],
        "station_scope": {
            "source": "IDS_CURRENT_STATION_TABLE_MINUTE_RESOLUTION",
            "coordinate_bound": "PLUS_MINUS_0_5_ARCMIN_HORIZONTAL; HEIGHT_UNRESOLVED",
            "pairs": [list(pair) for pair in PAIRS],
        },
        "rules": {
            "grid_s": INTERPOLATION_STEP_S,
            "minimum_elevation_deg": MIN_ELEVATION_DEG,
            "minimum_joint_interval_s": MIN_JOINT_INTERVAL_S,
            "calibration_fraction": CALIBRATION_FRACTION,
            "minimum_calibration_s": MIN_CALIBRATION_S,
            "minimum_heldout_s": MIN_HELDOUT_S,
            "carrier_hz": DORIS_S_BAND_HZ,
            "frozen_along_track_shifts_s": list(FROZEN_ALONG_TRACK_SHIFTS_S),
            "time_system": "SP3_TAI_TO_UTC_WITH_FROZEN_37_SECOND_OFFSET",
        },
        "shortlist": ranked[:3],
        "candidate_interval_count": len(ranked),
        "observation_rinex_access": "ZERO",
        "observation_values_access": "ZERO",
        "ephemeral_orbit_artifact_retention": "ZERO_AFTER_HASHED_ANALYSIS",
        "measurement_admission": "NOT_EVALUATED",
        "open_terms": [
            "EXACT_DPOD_BEACON_COORDINATES_HEIGHTS_AND_PHASE_CENTERS",
            "ONE_WAY_LIGHT_TIME_SAGNAC_SHAPIRO_AND_PROPER_TIME",
            "TROPOSPHERE_IONOSPHERE_AND_ANTENNA_MAPS",
            "RINEX_HEADER_FREQUENCY_SHIFT_K_AND_RECEIVER_CLOCK_SEMANTICS",
            "L1_L2_PHASE_CONTINUITY_PSEUDORANGE_AND_TIME_REFERENCE",
            "ONBOARD_SHARED_RECEIVER_AND_CHANNEL_DIFFERENTIAL_BIASES",
            "ACTUAL_PRODUCT_COVERAGE_AND_EVENT_TIME_BOUND",
        ],
        "root_topology": {
            "independent_upstream_roots": "DORIS_GROUND_BEACON_TRANSMITTERS",
            "shared_downstream_components": (
                "SENTINEL_3A_ANTENNA_DGXX_RECEIVER_CLOCK_AND_RINEX_GENERATION"
            ),
            "independent_receive_hardware_roots": False,
            "claim_boundary": (
                "BEACON_DEPENDENT_DISTRIBUTED_PROPAGATION_GEOMETRY; "
                "NOT_INDEPENDENT_RECEIVER_CONFIRMATION"
            ),
        },
        "claim_scope": "ORBIT_ONLY_GEOMETRY_SPIKE",
    }
    strict_json(receipt)
    return receipt


def run_from_directory(directory: Path) -> dict[str, object]:
    directory = Path(directory)
    current = parse_frozen_sp3_z(
        directory / CURRENT_S3A_NAME,
        expected_name=CURRENT_S3A_NAME,
        expected_sha256=CURRENT_S3A_SHA256,
        expected_satellite_id="L74",
    )
    prior = parse_frozen_sp3_z(
        directory / PRIOR_S3A_NAME,
        expected_name=PRIOR_S3A_NAME,
        expected_sha256=PRIOR_S3A_SHA256,
        expected_satellite_id="L74",
    )
    alternative = parse_frozen_sp3_z(
        directory / ALTERNATIVE_S3B_NAME,
        expected_name=ALTERNATIVE_S3B_NAME,
        expected_sha256=ALTERNATIVE_S3B_SHA256,
        expected_satellite_id="L98",
    )
    return evaluate_geometry(current, prior, alternative)


def strict_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main(arguments: Iterable[str] | None = None) -> int:
    del arguments
    quarantine = Path(".quarantine-doris-geometry")
    print(strict_json(run_from_directory(quarantine)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
