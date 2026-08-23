"""Bounded broadcast-only screen for a future GNSS double-difference test.

Only one exact-hash RINEX navigation file enters.  Observation RINEX, carrier
phase, Doppler, signal strength and receiver diagnostics are outside this
module's input surface.  The screen ranks joint geometry; it is not evidence.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import atan2, cos, sin, sqrt
from pathlib import Path
from typing import Final, Sequence

import numpy as np


SCREEN_VERSION: Final = "gps-broadcast-double-difference-screen-v1"
NAVIGATION_NAME: Final = "BRDM00DLR_S_20262150000_01D_MN.rnx"
NAVIGATION_BYTES: Final = 8_503_101
NAVIGATION_SHA256: Final = (
    "a8be80bbc5ad857381b8b4d662a08c9fb56a015b78c928d084f32799077aeb24"
)
NAVIGATION_GZIP_BYTES: Final = 1_406_096
NAVIGATION_GZIP_SHA256: Final = (
    "261225401bdeaae1c5ea102c76b5b663fa999c6945821b10b6b4967731fe0f78"
)
NAVIGATION_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/215/"
    "BRDM00DLR_S_20262150000_01D_MN.rnx.gz"
)
WINDOW_START_UTC: Final = "2026-08-02T23:59:42Z"
WINDOW_STOP_UTC: Final = "2026-08-03T23:59:42Z"
OBSERVATION_TIME_SYSTEM: Final = "GPS"
GRID_STEP_S: Final = 30.0
MINIMUM_ELEVATION_DEG: Final = 15.0
MINIMUM_WINDOW_S: Final = 2_400.0
CALIBRATION_FRACTION: Final = 0.2
GPS_UTC_OFFSET_S: Final = 18.0
MAX_EPHEMERIS_AGE_S: Final = 14_400.0
REFERENCE_CARRIER_HZ: Final = 1_575_420_000.0
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
GPS_MU_M3_S2: Final = 3.986005e14
EARTH_ROTATION_RAD_S: Final = 7.2921151467e-5
OUTCOME_SHORTLIST: Final = "GNSS_DOUBLE_DIFFERENCE_GEOMETRY_SHORTLISTED"
OUTCOME_NONE: Final = "NO_GNSS_DOUBLE_DIFFERENCE_WINDOW"


@dataclass(frozen=True, slots=True)
class Station:
    station_id: str
    latitude_deg: float
    longitude_deg: float
    height_m: float
    clock: str
    receiver: str
    antenna: str
    antenna_calibration: str
    measurement_root: str
    source: str


STATIONS: Final = (
    Station(
        "GOLD00USA",
        35.425156,
        -116.889250,
        986.6779,
        "EXTERNAL_H_MASER",
        "JAVAD_TRE_G3TH_DELTA_4.2.03",
        "AOAD_M_T_NONE",
        "ROBOT",
        "GOLDSTONE_GOLD00USA_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/GOLD00USA",
    ),
    Station(
        "NLIB00USA",
        41.771592,
        -91.574892,
        207.0648,
        "EXTERNAL_H_MASER",
        "SEPT_POLARX5TR_5.7.0",
        "JAVRINGANT_DM_SCIS",
        "ROBOT",
        "NORTH_LIBERTY_NLIB00USA_RECEIVER_ANTENNA_CLOCK",
        "https://network.igs.org/NLIB00USA",
    ),
)


@dataclass(frozen=True, slots=True)
class GpsEphemeris:
    satellite: str
    toc_gps: datetime
    af0_s: float
    af1_s_s: float
    af2_s_s2: float
    iode: float
    crs_m: float
    delta_n_rad_s: float
    m0_rad: float
    cuc_rad: float
    eccentricity: float
    cus_rad: float
    sqrt_a_m_sqrt: float
    toe_sow: float
    cic_rad: float
    omega0_rad: float
    cis_rad: float
    i0_rad: float
    crc_m: float
    argument_perigee_rad: float
    omega_dot_rad_s: float
    idot_rad_s: float
    gps_week: int
    sv_accuracy_m: float
    sv_health: int
    tgd_s: float
    transmission_sow: float
    fit_interval_h: float | None


class GnssDoubleDifferenceError(ValueError):
    """The frozen navigation source or screening geometry is invalid."""


def screen_navigation(path: Path) -> dict[str, object]:
    source = validate_navigation(path)
    records = parse_gps_navigation(path)
    epochs = utc_grid(WINDOW_START_UTC, WINDOW_STOP_UTC, GRID_STEP_S)
    satellites = tuple(sorted(records))
    if len(satellites) < 4:
        raise GnssDoubleDifferenceError("too few healthy GPS satellites")

    station_ecef = {station.station_id: station_to_ecef(station) for station in STATIONS}
    position = {
        satellite: np.asarray(
            [broadcast_ecef(select_ephemeris(records[satellite], epoch), epoch) for epoch in epochs]
        )
        for satellite in satellites
    }
    fractional = {
        (station.station_id, satellite): fractional_doppler(
            position[satellite], station_ecef[station.station_id], GRID_STEP_S
        )
        for station in STATIONS
        for satellite in satellites
    }
    elevation = {
        (station.station_id, satellite): elevation_deg(
            position[satellite], station, station_ecef[station.station_id]
        )
        for station in STATIONS
        for satellite in satellites
    }

    candidates = []
    left, right = (station.station_id for station in STATIONS)
    for target_index, target in enumerate(satellites):
        for reference in satellites[target_index + 1 :]:
            visible = (
                (elevation[(left, target)] >= MINIMUM_ELEVATION_DEG)
                & (elevation[(right, target)] >= MINIMUM_ELEVATION_DEG)
                & (elevation[(left, reference)] >= MINIMUM_ELEVATION_DEG)
                & (elevation[(right, reference)] >= MINIMUM_ELEVATION_DEG)
            )
            target_curve = double_difference_hz(
                fractional[(left, target)],
                fractional[(left, reference)],
                fractional[(right, target)],
                fractional[(right, reference)],
            )
            for start, stop in contiguous_true_segments(visible):
                duration = (stop - start - 1) * GRID_STEP_S
                if duration < MINIMUM_WINDOW_S:
                    continue
                curve = target_curve[start:stop]
                split = max(3, int(np.ceil(curve.size * CALIBRATION_FRACTION)))
                affine = prefix_affine_metrics(curve, split, GRID_STEP_S)
                wrong = wrong_orbit_family(
                    target,
                    reference,
                    start,
                    stop,
                    split,
                    satellites,
                    fractional,
                    elevation,
                    left,
                    right,
                )
                controlling = min(
                    affine["heldout_peak_to_peak_hz"],
                    wrong["minimum_heldout_peak_to_peak_hz"],
                )
                candidates.append(
                    {
                        "target": target,
                        "reference": reference,
                        "start_utc": format_utc(epochs[start]),
                        "stop_utc": format_utc(epochs[stop - 1]),
                        "start_observation_epoch_gps": format_gps(epochs[start]),
                        "stop_observation_epoch_gps": format_gps(epochs[stop - 1]),
                        "records": stop - start,
                        "calibration_records": split,
                        "holdout_records": stop - start - split,
                        "duration_s": duration,
                        "minimum_elevation_deg": {
                            station_id: {
                                target: float(np.min(elevation[(station_id, target)][start:stop])),
                                reference: float(np.min(elevation[(station_id, reference)][start:stop])),
                            }
                            for station_id in (left, right)
                        },
                        "raw_double_difference_hz": metrics(curve),
                        "prefix_affine_null": affine,
                        "wrong_orbit_family": wrong,
                        "controlling_heldout_separation_hz": controlling,
                    }
                )
    candidates.sort(
        key=lambda item: (
            -item["controlling_heldout_separation_hz"],
            item["start_utc"],
            item["target"],
            item["reference"],
        )
    )
    shortlist = distinct_shortlist(candidates, 3)
    result = {
        "screen_version": SCREEN_VERSION,
        "screen_manifest_sha256": screen_manifest_sha256(),
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_RINEX_UNOPENED",
        "navigation_source": source,
        "stations": [asdict(station) for station in STATIONS],
        "physical_question": (
            "CAN_A_FROZEN_BROADCAST_ORBIT_PREDICT_HELDOUT_DUAL_FREQUENCY_"
            "TWO_STATION_DOUBLE_DIFFERENCE_DYNAMICS_BETTER_THAN_FROZEN_NULLS"
        ),
        "observable": {
            "screening_coordinate": (
                "L1_SCALED_[(GOLD_TARGET-GOLD_REFERENCE)-"
                "(NLIB_TARGET-NLIB_REFERENCE)]_FRACTIONAL_DOPPLER"
            ),
            "future_measurement_coordinate": (
                "TIME_DERIVATIVE_OF_DUAL_FREQUENCY_IONOSPHERE_FREE_"
                "CARRIER_PHASE_DOUBLE_DIFFERENCE"
            ),
            "screening_is_measurement": False,
        },
        "causal_cancellations": {
            "receiver_clock": "CANCELLED_BY_SAME_EPOCH_SATELLITE_DIFFERENCE",
            "satellite_clock": "CANCELLED_BY_STATION_DIFFERENCE_UP_TO_RETARDED_TIME_REMAINDER",
            "integer_phase_ambiguity": "CANCELLED_BY_TIME_DIFFERENCE_WITHOUT_CYCLE_SLIP",
            "first_order_ionosphere": "CANCELLED_BY_FROZEN_DUAL_FREQUENCY_COMBINATION",
            "common_receiver_frequency_reference": "CANCELLED_TO_FIRST_ORDER_BY_SATELLITE_DIFFERENCE",
            "troposphere_and_signal_specific_bias": "REMAINS_MODELED_OR_BOUNDED",
        },
        "screen_parameters": screen_manifest()["parameters"],
        "healthy_gps_satellites": list(satellites),
        "candidate_windows": len(candidates),
        "shortlist": shortlist,
        "observation_access": {
            "rinex_observation_files_opened": 0,
            "carrier_phase_values_accessed": 0,
            "doppler_values_accessed": 0,
            "snr_values_accessed": 0,
        },
        "remaining_blockers": [
            "OBSERVATION_PRODUCT_CONTENT_HASHES_UNAVAILABLE_BECAUSE_UNOPENED",
            "BOTH_STATIONS_MUST_EXPOSE_MATCHING_DUAL_FREQUENCY_TARGET_AND_REFERENCE_PHASE",
            "LOSS_OF_LOCK_AND_CYCLE_SLIP_FREE_CALIBRATION_AND_HELDOUT",
            "TROPOSPHERE_RETARDED_TIME_AND_SIGNAL_SPECIFIC_HARDWARE_ENVELOPE",
            "FROZEN_OBSERVATION_QUANTIZATION_AND_CADENCE",
            "NO_OBSERVATION_FILE_MAY_BE_OPENED_BEFORE_PROSPECTIVE_PLAN_FREEZE",
        ],
        "outcome": OUTCOME_SHORTLIST if shortlist else OUTCOME_NONE,
        "measurement_authorized": False,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def validate_navigation(path: Path) -> dict[str, object]:
    path = Path(path)
    if path.name != NAVIGATION_NAME or not path.is_file():
        raise GnssDoubleDifferenceError("wrong frozen navigation product")
    if path.stat().st_size != NAVIGATION_BYTES:
        raise GnssDoubleDifferenceError("navigation byte count changed")
    digest = file_sha256(path)
    if digest != NAVIGATION_SHA256:
        raise GnssDoubleDifferenceError("navigation SHA-256 changed")
    return {
        "name": NAVIGATION_NAME,
        "url": NAVIGATION_URL,
        "bytes": NAVIGATION_BYTES,
        "sha256": digest,
        "compressed_bytes": NAVIGATION_GZIP_BYTES,
        "compressed_sha256": NAVIGATION_GZIP_SHA256,
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }


def parse_gps_navigation(path: Path) -> dict[str, tuple[GpsEphemeris, ...]]:
    lines = Path(path).read_text(encoding="ascii").splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if "END OF HEADER" in line) + 1
    except StopIteration as exc:
        raise GnssDoubleDifferenceError("RINEX header is incomplete") from exc
    records: dict[str, list[GpsEphemeris]] = {}
    for index in range(start, len(lines)):
        line = lines[index]
        if not line.startswith("G"):
            continue
        if index + 7 >= len(lines):
            raise GnssDoubleDifferenceError("truncated GPS navigation record")
        record = parse_gps_record(lines[index : index + 8])
        if record.sv_health == 0 and 0.0 <= record.eccentricity < 1.0:
            records.setdefault(record.satellite, []).append(record)
    if not records:
        raise GnssDoubleDifferenceError("no healthy GPS ephemeris found")
    return {
        satellite: tuple(sorted(values, key=lambda value: value.toc_gps))
        for satellite, values in records.items()
    }


def parse_gps_record(lines: Sequence[str]) -> GpsEphemeris:
    if len(lines) != 8 or not lines[0].startswith("G"):
        raise GnssDoubleDifferenceError("not one RINEX-3 GPS record")
    epoch_fields = lines[0][3:23].split()
    if len(epoch_fields) != 6:
        raise GnssDoubleDifferenceError("invalid GPS toc")
    year, month, day, hour, minute = (int(value) for value in epoch_fields[:5])
    second = float(epoch_fields[5])
    toc = datetime(year, month, day, hour, minute, tzinfo=timezone.utc) + timedelta(seconds=second)
    first = fixed_fields(lines[0], 23)
    rows = [fixed_fields(line, 4) for line in lines[1:]]
    fit_interval = None if len(rows[6]) < 2 or rows[6][1] == 0.0 else rows[6][1]
    return GpsEphemeris(
        lines[0][:3], toc, first[0], first[1], first[2],
        rows[0][0], rows[0][1], rows[0][2], rows[0][3],
        rows[1][0], rows[1][1], rows[1][2], rows[1][3],
        rows[2][0], rows[2][1], rows[2][2], rows[2][3],
        rows[3][0], rows[3][1], rows[3][2], rows[3][3],
        rows[4][0], int(round(rows[4][2])), rows[5][0], int(round(rows[5][1])),
        rows[5][2], rows[6][0], fit_interval,
    )


def fixed_fields(line: str, start: int) -> tuple[float, ...]:
    fields = []
    for offset in range(start, len(line), 19):
        text = line[offset : offset + 19].strip().replace("D", "E")
        if text:
            fields.append(float(text))
    return tuple(fields)


def select_ephemeris(records: Sequence[GpsEphemeris], utc: datetime) -> GpsEphemeris:
    gps_epoch = utc + timedelta(seconds=GPS_UTC_OFFSET_S)
    eligible = [record for record in records if record.toc_gps <= gps_epoch]
    record = eligible[-1] if eligible else records[0]
    if abs((gps_epoch - record.toc_gps).total_seconds()) > MAX_EPHEMERIS_AGE_S:
        raise GnssDoubleDifferenceError(f"stale broadcast ephemeris for {record.satellite}")
    return record


def broadcast_ecef(record: GpsEphemeris, utc: datetime) -> np.ndarray:
    week, sow = gps_week_sow(utc)
    tk = (week - record.gps_week) * 604_800.0 + sow - record.toe_sow
    while tk > 302_400.0:
        tk -= 604_800.0
    while tk < -302_400.0:
        tk += 604_800.0
    semi_major = record.sqrt_a_m_sqrt**2
    mean_motion = sqrt(GPS_MU_M3_S2 / semi_major**3) + record.delta_n_rad_s
    mean_anomaly = record.m0_rad + mean_motion * tk
    eccentric_anomaly = mean_anomaly
    for _ in range(20):
        updated = mean_anomaly + record.eccentricity * sin(eccentric_anomaly)
        if abs(updated - eccentric_anomaly) < 1e-13:
            eccentric_anomaly = updated
            break
        eccentric_anomaly = updated
    true_anomaly = atan2(
        sqrt(1.0 - record.eccentricity**2) * sin(eccentric_anomaly),
        cos(eccentric_anomaly) - record.eccentricity,
    )
    phi = true_anomaly + record.argument_perigee_rad
    du = record.cus_rad * sin(2.0 * phi) + record.cuc_rad * cos(2.0 * phi)
    dr = record.crs_m * sin(2.0 * phi) + record.crc_m * cos(2.0 * phi)
    di = record.cis_rad * sin(2.0 * phi) + record.cic_rad * cos(2.0 * phi)
    u = phi + du
    radius = semi_major * (1.0 - record.eccentricity * cos(eccentric_anomaly)) + dr
    inclination = record.i0_rad + record.idot_rad_s * tk + di
    orbital_x = radius * cos(u)
    orbital_y = radius * sin(u)
    node = (
        record.omega0_rad
        + (record.omega_dot_rad_s - EARTH_ROTATION_RAD_S) * tk
        - EARTH_ROTATION_RAD_S * record.toe_sow
    )
    return np.asarray(
        [
            orbital_x * cos(node) - orbital_y * cos(inclination) * sin(node),
            orbital_x * sin(node) + orbital_y * cos(inclination) * cos(node),
            orbital_y * sin(inclination),
        ],
        dtype=np.float64,
    )


def gps_week_sow(utc: datetime) -> tuple[int, float]:
    gps = utc + timedelta(seconds=GPS_UTC_OFFSET_S)
    delta = (gps - datetime(1980, 1, 6, tzinfo=timezone.utc)).total_seconds()
    week = int(delta // 604_800.0)
    return week, delta - week * 604_800.0


def station_to_ecef(station: Station) -> np.ndarray:
    latitude = np.radians(station.latitude_deg)
    longitude = np.radians(station.longitude_deg)
    semi_major = 6_378_137.0
    flattening = 1.0 / 298.257223563
    eccentricity_sq = flattening * (2.0 - flattening)
    prime_vertical = semi_major / sqrt(1.0 - eccentricity_sq * sin(latitude) ** 2)
    return np.asarray(
        [
            (prime_vertical + station.height_m) * cos(latitude) * cos(longitude),
            (prime_vertical + station.height_m) * cos(latitude) * sin(longitude),
            (prime_vertical * (1.0 - eccentricity_sq) + station.height_m) * sin(latitude),
        ]
    )


def elevation_deg(position: np.ndarray, station: Station, station_ecef: np.ndarray) -> np.ndarray:
    line = position - station_ecef
    unit = line / np.linalg.norm(line, axis=1)[:, None]
    latitude = np.radians(station.latitude_deg)
    longitude = np.radians(station.longitude_deg)
    up = np.asarray(
        [cos(latitude) * cos(longitude), cos(latitude) * sin(longitude), sin(latitude)]
    )
    return np.degrees(np.arcsin(np.clip(unit @ up, -1.0, 1.0)))


def fractional_doppler(position: np.ndarray, station_ecef: np.ndarray, step_s: float) -> np.ndarray:
    ranges = np.linalg.norm(position - station_ecef, axis=1)
    range_rate = np.gradient(ranges, step_s, edge_order=2)
    return -range_rate / SPEED_OF_LIGHT_M_S


def double_difference_hz(left_target, left_reference, right_target, right_reference):
    return REFERENCE_CARRIER_HZ * (
        (np.asarray(left_target) - np.asarray(left_reference))
        - (np.asarray(right_target) - np.asarray(right_reference))
    )


def contiguous_true_segments(mask: Sequence[bool]) -> tuple[tuple[int, int], ...]:
    values = np.asarray(mask, dtype=bool)
    edges = np.diff(np.concatenate(([False], values, [False])).astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    stops = np.flatnonzero(edges == -1)
    return tuple(zip(starts.tolist(), stops.tolist(), strict=True))


def prefix_affine_metrics(curve: Sequence[float], split: int, step_s: float) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    elapsed = np.arange(values.size, dtype=np.float64) * step_s
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(design, values[:split], rcond=None)
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[split:]
    return {
        "constant_hz": float(coefficients[0]),
        "slope_hz_s": float(coefficients[1]),
        "heldout_peak_to_peak_hz": float(np.ptp(heldout)),
        "heldout_rms_hz": float(sqrt(float(np.mean(heldout * heldout)))),
        "calibration_prefix_rmse_hz": float(
            sqrt(float(np.mean(residual[:split] * residual[:split])))
        ),
    }


def wrong_orbit_family(
    target,
    reference,
    start,
    stop,
    split,
    satellites,
    fractional,
    elevation,
    left,
    right,
):
    target_curve = double_difference_hz(
        fractional[(left, target)], fractional[(left, reference)],
        fractional[(right, target)], fractional[(right, reference)],
    )[start:stop]
    alternatives = []
    for alternative in satellites:
        if alternative in (target, reference):
            continue
        alternative_visible = (
            np.all(elevation[(left, alternative)][start:stop] >= MINIMUM_ELEVATION_DEG)
            and np.all(elevation[(right, alternative)][start:stop] >= MINIMUM_ELEVATION_DEG)
        )
        if not alternative_visible:
            continue
        alternative_curve = double_difference_hz(
            fractional[(left, alternative)], fractional[(left, reference)],
            fractional[(right, alternative)], fractional[(right, reference)],
        )[start:stop]
        scored = prefix_affine_metrics(target_curve - alternative_curve, split, GRID_STEP_S)
        alternatives.append(
            {"satellite": alternative, "heldout_peak_to_peak_hz": scored["heldout_peak_to_peak_hz"]}
        )
    if not alternatives:
        return {"minimum_heldout_peak_to_peak_hz": 0.0, "controlling_alternative": None, "alternatives": []}
    alternatives.sort(key=lambda item: (item["heldout_peak_to_peak_hz"], item["satellite"]))
    return {
        "minimum_heldout_peak_to_peak_hz": alternatives[0]["heldout_peak_to_peak_hz"],
        "controlling_alternative": alternatives[0]["satellite"],
        "alternatives": alternatives,
    }


def distinct_shortlist(candidates: Sequence[dict[str, object]], count: int):
    selected = []
    pairs = set()
    for candidate in candidates:
        pair = (candidate["target"], candidate["reference"])
        if pair in pairs:
            continue
        selected.append(candidate)
        pairs.add(pair)
        if len(selected) == count:
            break
    return selected


def metrics(values: Sequence[float]) -> dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "minimum_hz": float(np.min(array)),
        "maximum_hz": float(np.max(array)),
        "peak_to_peak_hz": float(np.ptp(array)),
        "rms_hz": float(sqrt(float(np.mean(array * array)))),
    }


def utc_grid(start: str, stop: str, step_s: float) -> tuple[datetime, ...]:
    first = parse_utc(start)
    last = parse_utc(stop)
    count = int((last - first).total_seconds() // step_s)
    return tuple(first + timedelta(seconds=index * step_s) for index in range(count))


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_gps(value: datetime) -> str:
    gps = value.astimezone(timezone.utc) + timedelta(seconds=GPS_UTC_OFFSET_S)
    return f"{gps.isoformat(timespec='seconds').replace('+00:00', '')} GPS"


def screen_manifest() -> dict[str, object]:
    return {
        "screen_version": SCREEN_VERSION,
        "navigation_sha256": NAVIGATION_SHA256,
        "stations": [asdict(station) for station in STATIONS],
        "parameters": {
            "window_start_utc": WINDOW_START_UTC,
            "window_stop_utc": WINDOW_STOP_UTC,
            "observation_time_system": OBSERVATION_TIME_SYSTEM,
            "gps_minus_utc_s": GPS_UTC_OFFSET_S,
            "grid_step_s": GRID_STEP_S,
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "minimum_window_s": MINIMUM_WINDOW_S,
            "calibration_fraction": CALIBRATION_FRACTION,
            "maximum_ephemeris_age_s": MAX_EPHEMERIS_AGE_S,
            "reference_carrier_hz": REFERENCE_CARRIER_HZ,
        },
        "nulls": ["PREFIX_AFFINE", "OTHER_JOINTLY_VISIBLE_GPS_BROADCAST_ORBITS"],
        "forbidden": [
            "RINEX observation access",
            "carrier phase or Doppler access",
            "SNR or loss-of-lock inspection",
            "post-outcome target or reference selection",
            "precise post-pass orbit products",
            "threshold change after observation",
        ],
    }


def screen_manifest_sha256() -> str:
    return sha256(strict_json(screen_manifest()).encode("ascii")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("navigation", type=Path)
    print(strict_json(screen_navigation(parser.parse_args().navigation)))
