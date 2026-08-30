"""Observation-blind LuGRE constellation-snapshot geometry screen.

The compiler accepts historical GPS broadcast navigation and CLPS SPICE
kernels only.  It has no LuGRE artifact locator, header parser, sample decoder,
track value or code-identity input.  It asks whether the *shape* of four
simultaneous L1 Doppler coordinates can survive a common offset and scale and
remain distinct from other GPS subsets and frozen non-orbital nulls.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import gzip
from hashlib import sha256
import importlib
import importlib.metadata
from itertools import combinations
import json
from math import acos, pi, sin, sqrt
from pathlib import Path
import platform
import subprocess
from typing import Callable, Final, Mapping, Sequence

import numpy as np
from scipy.spatial import cKDTree

from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as rinex2,
)


SCREEN_VERSION: Final = "lugre-constellation-snapshot-discriminability-v1"
RECEIPT_NAME: Final = "LUGRE_SNAPSHOT_DISCRIMINABILITY_RECEIPT.json"
OUTCOME_POSITIVE: Final = "LUGRE_SNAPSHOT_GEOMETRY_DISCRIMINATIVE"
OUTCOME_NONE: Final = "NO_SNAPSHOT_DISCRIMINABILITY"

GPS_L1_HZ: Final = 1_575_420_000.0
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
EARTH_OCCULTATION_RADIUS_M: Final = 6_378_137.0
LIGHT_TIME_TOLERANCE_S: Final = 1.0e-11
LIGHT_TIME_ITERATIONS: Final = 12
RANGE_DERIVATIVE_HALF_STEP_S: Final = 0.5
SIGNALS_PER_SNAPSHOT: Final = 4
MINIMUM_CANDIDATE_POOL: Final = 5
TIMING_SHIFTS_S: Final = (-60.0, -10.0, -1.0, -0.1, 0.1, 1.0, 10.0, 60.0)


@dataclass(frozen=True, slots=True)
class FileAuthority:
    name: str
    url: str
    bytes: int
    sha256: str
    role: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    operation: str
    utc: str
    advertised_duration_ms: int
    duration_state: str
    doy: int
    observer_target: str
    observer_source: str
    observer_independence: str


NAVIGATION: Final = (
    FileAuthority(
        "brdc0550.25n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2025/055/brdc0550.25n.gz",
        71_994,
        "8fb1012f925d8ca7f8f67fccf08cdab9f39337c147fcd88c5177ac53a0c796a1",
        "OUTCOME_INDEPENDENT_GPS_BROADCAST_NAVIGATION",
    ),
    FileAuthority(
        "brdc0580.25n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2025/058/brdc0580.25n.gz",
        73_469,
        "b5199bb55f7077f8cf3f8113f2017f8069d9c3e0ef4a9be18c3e5402fb61ae94",
        "OUTCOME_INDEPENDENT_GPS_BROADCAST_NAVIGATION",
    ),
    FileAuthority(
        "brdc0620.25n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2025/062/brdc0620.25n.gz",
        70_276,
        "6ddfae0fd29ed4c3ae9dd06af201741ffa1b5b4daf5d5fa2d57a13a476f96c5f",
        "OUTCOME_INDEPENDENT_GPS_BROADCAST_NAVIGATION",
    ),
    FileAuthority(
        "brdc0630.25n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2025/063/brdc0630.25n.gz",
        71_061,
        "f5bb70ecf2ea2c8f1f59c29c9db6514a0f0c38bacf4845a489ff89a0276cb3d7",
        "OUTCOME_INDEPENDENT_GPS_BROADCAST_NAVIGATION",
    ),
    FileAuthority(
        "brdc0730.25n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2025/073/brdc0730.25n.gz",
        72_351,
        "9720ee334e6c24e2a71e3db1ef16cbcee6c13cf7323ed60d881fec7895855390",
        "OUTCOME_INDEPENDENT_GPS_BROADCAST_NAVIGATION",
    ),
    FileAuthority(
        "brdc0740.25n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2025/074/brdc0740.25n.gz",
        70_462,
        "fa2827b8575f84d11a1b515e88dd99b79c4e8ad88bf5da5eef51ba1041dc45fa",
        "OUTCOME_INDEPENDENT_GPS_BROADCAST_NAVIGATION",
    ),
)

SPICE: Final = (
    FileAuthority(
        "naif0012.tls",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/lsk/naif0012.tls",
        5_257,
        "678e32bdb5a744117a467cd9601cd6b373f0e9bc9bbde1371d5eee39600a039b",
        "UTC_ET_CONVERSION",
    ),
    FileAuthority(
        "pck00011.tpc",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/pck/pck00011.tpc",
        131_226,
        "3dff7b1dbeceaa01f25467767d3fa25816051c85d162d1edf04acb310ee28bb1",
        "PLANETARY_CONSTANTS",
    ),
    FileAuthority(
        "earth_000101_260530_260303.bpc",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/pck/earth_000101_260530_260303.bpc",
        5_030_912,
        "0f25cf76320979dc1ea3dae007c1592f61e7b71b151cdb6ff58e2357463cf9b3",
        "ARCHIVED_EARTH_ORIENTATION_INDEPENDENT_OF_LUGRE_RF",
    ),
    FileAuthority(
        "earth_assoc_itrf93.tf",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/fk/earth_assoc_itrf93.tf",
        7_522,
        "aab7bbc19b8a69bad11988ee1b4812a3963812a03a029c2776863e680719b336",
        "ITRF93_FRAME_ASSOCIATION",
    ),
    FileAuthority(
        "moon_pa_de440_200625.bpc",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/pck/moon_pa_de440_200625.bpc",
        12_863_488,
        "60cd55aa401ea2ea97360636f567554bfe4e37bb829f901b4460a455dfaf783f",
        "LUNAR_ORIENTATION",
    ),
    FileAuthority(
        "moon_de440_250416.tf",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/fk/moon_de440_250416.tf",
        19_478,
        "a47c71e9c9f33796bdafb2c9d69a7ee447b6016ecad80f71cd6f3e479f9cf768",
        "LUNAR_FRAME",
    ),
    FileAuthority(
        "moon_assoc_me.tf",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/fk/moon_assoc_me.tf",
        8_468,
        "52c622043ce0447d575e59ee01642f1894921e68c10f934ceff065f362da6c1c",
        "LUNAR_FRAME_ASSOCIATION",
    ),
    FileAuthority(
        "de440s.bsp",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/spk/de440s.bsp",
        32_726_016,
        "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2",
        "EARTH_MOON_EPHEMERIS",
    ),
    FileAuthority(
        "clps_to19d_bgm1_cru_rec_250115_250302_v01.bsp",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/spk/clps_to19d_bgm1_cru_rec_250115_250302_v01.bsp",
        23_833_600,
        "0f12c2f0709fcbb53f8c5bcfbdf6bd45bf0007b30b8ce5707b2927c91d361abe",
        "RECONSTRUCTED_BLUE_GHOST_CRUISE_OBSERVER_NOT_GNSS_TRANSMITTER_ORBIT",
    ),
    FileAuthority(
        "clps_to19d_bgm1_ls_250302_v01.bsp",
        "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/clps/clps_spice/spice_kernels/spk/clps_to19d_bgm1_ls_250302_v01.bsp",
        8_192,
        "36308426e78c3f5fe0287161972ee542b321bc89bcae072bd9b59df446a8917a",
        "ACTUAL_LANDING_SITE_OBSERVER_NOT_GNSS_TRANSMITTER_ORBIT",
    ),
)

SNAPSHOTS: Final = (
    Snapshot(
        "OP32",
        "2025-02-24T12:04:49Z",
        300,
        "ARCHIVE_LISTING",
        55,
        "-2711",
        "RECONSTRUCTED_CRUISE_SPK",
        "INDEPENDENT_OF_TARGET_RF_BUT_NOT_PROSPECTIVE_OBSERVER_ORBIT",
    ),
    Snapshot(
        "OP37",
        "2025-02-27T16:09:37Z",
        300,
        "ARCHIVE_LISTING",
        58,
        "-2711",
        "RECONSTRUCTED_CRUISE_SPK",
        "INDEPENDENT_OF_TARGET_RF_BUT_NOT_PROSPECTIVE_OBSERVER_ORBIT",
    ),
    Snapshot(
        "OP38",
        "2025-03-03T06:13:00Z",
        300,
        "ARCHIVE_LISTING",
        62,
        "-2711900",
        "ACTUAL_LANDING_SITE_SPK",
        "INDEPENDENT_OF_TARGET_RF",
    ),
    Snapshot(
        "OP40",
        "2025-03-04T07:03:23Z",
        300,
        "ARCHIVE_LISTING_L1_BIN_300MS_SDRX_400MS_CONFLICT",
        63,
        "-2711900",
        "ACTUAL_LANDING_SITE_SPK",
        "INDEPENDENT_OF_TARGET_RF",
    ),
    Snapshot(
        "OP73",
        "2025-03-14T10:09:45Z",
        2_000,
        "ARCHIVE_LISTING",
        73,
        "-2711900",
        "ACTUAL_LANDING_SITE_SPK",
        "INDEPENDENT_OF_TARGET_RF",
    ),
    Snapshot(
        "OP74",
        "2025-03-14T12:47:17Z",
        500,
        "ARCHIVE_LISTING",
        73,
        "-2711900",
        "ACTUAL_LANDING_SITE_SPK",
        "INDEPENDENT_OF_TARGET_RF",
    ),
    Snapshot(
        "OP76",
        "2025-03-15T13:07:27Z",
        2_000,
        "ARCHIVE_LISTING",
        74,
        "-2711900",
        "ACTUAL_LANDING_SITE_SPK",
        "INDEPENDENT_OF_TARGET_RF",
    ),
)


class LuGreSnapshotError(ValueError):
    """A frozen authority or numerical invariant changed."""


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


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def _validate_file(root: Path, authority: FileAuthority) -> Path:
    path = Path(root) / authority.name
    if not path.is_file():
        raise LuGreSnapshotError(f"AUTHORITY_MISSING_{authority.name}")
    payload = path.read_bytes()
    if len(payload) != authority.bytes:
        raise LuGreSnapshotError(f"AUTHORITY_SIZE_CHANGED_{authority.name}")
    if sha256(payload).hexdigest() != authority.sha256:
        raise LuGreSnapshotError(f"AUTHORITY_HASH_CHANGED_{authority.name}")
    return path


def parse_navigation_payload(
    payload: bytes,
) -> dict[str, tuple[geometry.GpsEphemeris, ...]]:
    try:
        lines = gzip.decompress(payload).decode("ascii").splitlines()
    except (EOFError, OSError, UnicodeDecodeError) as exc:
        raise LuGreSnapshotError("NAVIGATION_DECODE_FAILED") from exc
    try:
        start = next(i for i, line in enumerate(lines) if "END OF HEADER" in line) + 1
    except StopIteration as exc:
        raise LuGreSnapshotError("NAVIGATION_HEADER_INCOMPLETE") from exc
    parsed: dict[str, list[geometry.GpsEphemeris]] = {}
    for index in range(start, len(lines)):
        if not lines[index][:2].strip().isdigit():
            continue
        if index + 7 >= len(lines):
            raise LuGreSnapshotError("NAVIGATION_RECORD_TRUNCATED")
        record = rinex2.parse_rinex2_gps_record(lines[index : index + 8])
        if record.sv_health == 0 and 0.0 <= record.eccentricity < 1.0:
            parsed.setdefault(record.satellite, []).append(record)
    if len(parsed) < MINIMUM_CANDIDATE_POOL:
        raise LuGreSnapshotError("TOO_FEW_HEALTHY_GPS_EPHEMERIDES")
    return {
        satellite: tuple(sorted(rows, key=lambda row: row.toc_gps))
        for satellite, rows in parsed.items()
    }


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise LuGreSnapshotError("SNAPSHOT_TIME_NOT_UTC")
    return parsed.astimezone(timezone.utc)


def _spice_utc(utc: datetime) -> str:
    return utc.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f UTC")


def _clock_bias_s(record: geometry.GpsEphemeris, utc: datetime) -> float:
    gps = utc + timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    dt = (gps - record.toc_gps).total_seconds()
    week, sow = geometry.gps_week_sow(utc)
    tk = (week - record.gps_week) * 604_800.0 + sow - record.toe_sow
    while tk > 302_400.0:
        tk -= 604_800.0
    while tk < -302_400.0:
        tk += 604_800.0
    semi_major = record.sqrt_a_m_sqrt**2
    mean_motion = sqrt(geometry.GPS_MU_M3_S2 / semi_major**3) + record.delta_n_rad_s
    mean_anomaly = record.m0_rad + mean_motion * tk
    eccentric = mean_anomaly
    for _ in range(20):
        updated = mean_anomaly + record.eccentricity * sin(eccentric)
        if abs(updated - eccentric) < 1.0e-13:
            eccentric = updated
            break
        eccentric = updated
    relativistic = (
        -4.442807633e-10 * record.eccentricity * record.sqrt_a_m_sqrt * sin(eccentric)
    )
    return (
        record.af0_s
        + record.af1_s_s * dt
        + record.af2_s_s2 * dt * dt
        + relativistic
        - record.tgd_s
    )


def _earth_occulted(satellite_m: np.ndarray, observer_m: np.ndarray) -> bool:
    delta = observer_m - satellite_m
    denominator = float(delta @ delta)
    if denominator <= 0.0:
        raise LuGreSnapshotError("DEGENERATE_EARTH_OCCULTATION_LINE")
    fraction = float(np.clip(-(satellite_m @ delta) / denominator, 0.0, 1.0))
    closest = satellite_m + fraction * delta
    return bool(
        0.0 < fraction < 1.0 and np.linalg.norm(closest) <= EARTH_OCCULTATION_RADIUS_M
    )


def _off_boresight_deg(satellite_m: np.ndarray, observer_m: np.ndarray) -> float:
    earthward = -satellite_m
    receiverward = observer_m - satellite_m
    cosine = float(
        (earthward @ receiverward)
        / (np.linalg.norm(earthward) * np.linalg.norm(receiverward))
    )
    return 180.0 / pi * acos(float(np.clip(cosine, -1.0, 1.0)))


def _center_and_normalize(
    rows: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(rows, dtype=np.float64)
    centered = values - np.mean(values, axis=1, keepdims=True)
    norms = np.linalg.norm(centered, axis=1)
    valid = norms > 1.0e-12
    normalized = np.zeros_like(centered)
    normalized[valid] = centered[valid] / norms[valid, None]
    return centered, norms, normalized


def affine_residual_rmse_hz(target: Sequence[float], model: Sequence[float]) -> float:
    y = np.asarray(target, dtype=np.float64)
    x = np.asarray(model, dtype=np.float64)
    if y.shape != x.shape or y.ndim != 1 or y.size < 3:
        raise LuGreSnapshotError("AFFINE_COORDINATE_SHAPE_INVALID")
    if not np.all(np.isfinite(y)) or not np.all(np.isfinite(x)):
        raise LuGreSnapshotError("AFFINE_COORDINATE_NONFINITE")
    yc = y - np.mean(y)
    xc = x - np.mean(x)
    denominator = float(xc @ xc)
    if denominator <= 1.0e-24:
        return float(np.sqrt(np.mean(yc * yc)))
    scale = max(0.0, float(yc @ xc) / denominator)
    residual = yc - scale * xc
    return float(np.sqrt(np.mean(residual * residual)))


def _codebook(
    values_hz: Mapping[str, float],
) -> tuple[tuple[tuple[str, ...], ...], np.ndarray]:
    satellites = tuple(sorted(values_hz))
    identities = tuple(combinations(satellites, SIGNALS_PER_SNAPSHOT))
    rows = np.asarray(
        [
            sorted(float(values_hz[satellite]) for satellite in identity)
            for identity in identities
        ],
        dtype=np.float64,
    )
    return identities, rows


def codebook_separation(values_hz: Mapping[str, float]) -> dict[str, object]:
    identities, rows = _codebook(values_hz)
    if len(identities) < 2:
        raise LuGreSnapshotError("TOO_FEW_SNAPSHOT_HYPOTHESES")
    _, _, normalized = _center_and_normalize(rows)
    distances, indices = cKDTree(normalized).query(normalized, k=2)
    metrics = []
    for index, competitor_index in enumerate(indices[:, 1]):
        residual = affine_residual_rmse_hz(rows[index], rows[int(competitor_index)])
        metrics.append(
            (residual, index, int(competitor_index), float(distances[index, 1]))
        )
    controlling = min(
        metrics, key=lambda item: (item[0], identities[item[1]], identities[item[2]])
    )
    strongest = max(
        metrics, key=lambda item: (item[0], tuple(reversed(identities[item[1]])))
    )

    def describe(item: tuple[float, int, int, float]) -> dict[str, object]:
        residual, left, right, shape_distance = item
        return {
            "true_subset": list(identities[left]),
            "nearest_wrong_subset": list(identities[right]),
            "affine_projected_rmse_hz": residual,
            "normalized_shape_distance": shape_distance,
            "maximum_total_per_track_rms_envelope_hz": residual / 2.0,
        }

    return {
        "candidate_satellites": sorted(values_hz),
        "candidate_count": len(values_hz),
        "hypothesis_count": len(identities),
        "signals_per_hypothesis": SIGNALS_PER_SNAPSHOT,
        "controlling_assignment": describe(controlling),
        "strongest_assignment": describe(strongest),
    }


def subset_separation(
    values_hz: Mapping[str, float], true_subset: Sequence[str]
) -> dict[str, object]:
    identities, rows = _codebook(values_hz)
    identity = tuple(sorted(true_subset))
    if identity not in identities:
        raise LuGreSnapshotError("TRUE_SUBSET_OUTSIDE_CODEBOOK")
    index = identities.index(identity)
    _, _, normalized = _center_and_normalize(rows)
    _, nearest = cKDTree(normalized).query(normalized[index], k=2)
    competitor = int(nearest[1])
    residual = affine_residual_rmse_hz(rows[index], rows[competitor])
    return {
        "true_subset": list(identity),
        "nearest_wrong_subset": list(identities[competitor]),
        "affine_projected_rmse_hz": residual,
        "maximum_total_per_track_rms_envelope_hz": residual / 2.0,
    }


def null_separation(
    true_values_hz: Mapping[str, float], null_values_hz: Mapping[str, float]
) -> dict[str, object]:
    true_identities, true_rows = _codebook(true_values_hz)
    null_identities, null_rows = _codebook(null_values_hz)
    _, null_norms, null_normalized = _center_and_normalize(null_rows)
    keep = null_norms > 1.0e-12
    if not np.any(keep):
        residuals = np.std(true_rows, axis=1)
        nearest = np.zeros(len(true_rows), dtype=np.int64)
        kept_identities = ((),)
    else:
        kept_rows = null_rows[keep]
        kept_identities = tuple(
            identity
            for identity, valid in zip(null_identities, keep, strict=True)
            if valid
        )
        tree = cKDTree(null_normalized[keep])
        _, nearest = tree.query(_center_and_normalize(true_rows)[2], k=1)
        residuals = np.asarray(
            [
                affine_residual_rmse_hz(true_rows[i], kept_rows[int(j)])
                for i, j in enumerate(nearest)
            ],
            dtype=np.float64,
        )
    index = int(np.argmin(residuals))
    return {
        "controlling_true_subset": list(true_identities[index]),
        "nearest_null_subset": list(kept_identities[int(nearest[index])])
        if kept_identities[0]
        else [],
        "affine_projected_rmse_hz": float(residuals[index]),
        "maximum_total_per_track_rms_envelope_hz": float(residuals[index] / 2.0),
    }


def subset_null_separation(
    true_values_hz: Mapping[str, float],
    true_subset: Sequence[str],
    null_values_hz: Mapping[str, float],
) -> dict[str, object]:
    identity = tuple(sorted(true_subset))
    observed = np.asarray(
        [sorted(float(true_values_hz[satellite]) for satellite in identity)],
        dtype=np.float64,
    )
    null_identities, null_rows = _codebook(null_values_hz)
    _, null_norms, null_normalized = _center_and_normalize(null_rows)
    keep = null_norms > 1.0e-12
    if not np.any(keep):
        residual = float(np.std(observed[0]))
        nearest_identity: tuple[str, ...] = ()
    else:
        kept_rows = null_rows[keep]
        kept_identities = tuple(
            candidate
            for candidate, valid in zip(null_identities, keep, strict=True)
            if valid
        )
        _, nearest = cKDTree(null_normalized[keep]).query(
            _center_and_normalize(observed)[2][0], k=1
        )
        nearest_index = int(nearest)
        nearest_identity = kept_identities[nearest_index]
        residual = affine_residual_rmse_hz(observed[0], kept_rows[nearest_index])
    return {
        "true_subset": list(identity),
        "nearest_null_subset": list(nearest_identity),
        "affine_projected_rmse_hz": residual,
        "maximum_total_per_track_rms_envelope_hz": residual / 2.0,
    }


def rank_affine_null(values_hz: Mapping[str, float]) -> dict[str, object]:
    identities, rows = _codebook(values_hz)
    rank = np.arange(SIGNALS_PER_SNAPSHOT, dtype=np.float64)
    residuals = np.asarray([affine_residual_rmse_hz(row, rank) for row in rows])
    index = int(np.argmin(residuals))
    return {
        "controlling_true_subset": list(identities[index]),
        "affine_projected_rmse_hz": float(residuals[index]),
        "maximum_total_per_track_rms_envelope_hz": float(residuals[index] / 2.0),
    }


def subset_rank_affine_null(
    values_hz: Mapping[str, float], true_subset: Sequence[str]
) -> dict[str, object]:
    identity = tuple(sorted(true_subset))
    row = sorted(float(values_hz[satellite]) for satellite in identity)
    residual = affine_residual_rmse_hz(
        row, np.arange(SIGNALS_PER_SNAPSHOT, dtype=np.float64)
    )
    return {
        "true_subset": list(identity),
        "affine_projected_rmse_hz": residual,
        "maximum_total_per_track_rms_envelope_hz": residual / 2.0,
    }


class SpiceGeometry:
    """Small SPICE boundary used only by this frozen screen."""

    def __init__(self, kernel_root: Path):
        self.spice = importlib.import_module("spiceypy")
        self.paths = [_validate_file(kernel_root, authority) for authority in SPICE]
        self.spice.kclear()
        for path in self.paths:
            self.spice.furnsh(str(path))

    def close(self) -> None:
        self.spice.kclear()

    def observer_state_m(self, snapshot: Snapshot, utc: datetime) -> np.ndarray:
        state_km, _ = self.spice.spkezr(
            snapshot.observer_target,
            self.spice.str2et(_spice_utc(utc)),
            "J2000",
            "NONE",
            "EARTH",
        )
        state = np.asarray(state_km, dtype=np.float64) * 1_000.0
        if state.shape != (6,) or not np.all(np.isfinite(state)):
            raise LuGreSnapshotError("OBSERVER_STATE_INVALID")
        return state

    def satellite_position_m(
        self,
        records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
        satellite: str,
        utc: datetime,
    ) -> np.ndarray:
        record = geometry.select_ephemeris(records[satellite], utc)
        ecef = geometry.broadcast_ecef(record, utc)
        rotation = np.asarray(
            self.spice.pxform("ITRF93", "J2000", self.spice.str2et(_spice_utc(utc))),
            dtype=np.float64,
        )
        return rotation @ ecef


def _range_m(
    spice: SpiceGeometry,
    snapshot: Snapshot,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    receive_utc: datetime,
    observer_state: Callable[[datetime], np.ndarray],
) -> tuple[float, np.ndarray, np.ndarray, datetime]:
    observer = observer_state(receive_utc)[:3]
    transmit = receive_utc - timedelta(seconds=1.3)
    previous = 0.0
    satellite_position = np.zeros(3, dtype=np.float64)
    for _ in range(LIGHT_TIME_ITERATIONS):
        satellite_position = spice.satellite_position_m(records, satellite, transmit)
        distance = float(np.linalg.norm(satellite_position - observer))
        light_time = distance / SPEED_OF_LIGHT_M_S
        transmit = receive_utc - timedelta(seconds=light_time)
        if abs(light_time - previous) <= LIGHT_TIME_TOLERANCE_S:
            return distance, satellite_position, observer, transmit
        previous = light_time
    raise LuGreSnapshotError("ONE_WAY_LIGHT_TIME_DID_NOT_CONVERGE")


def _frequency_hz(
    spice: SpiceGeometry,
    snapshot: Snapshot,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    utc: datetime,
    mode: str,
) -> tuple[float, dict[str, float | bool]]:
    nominal_state = spice.observer_state_m(snapshot, utc)

    def observer(query: datetime) -> np.ndarray:
        if mode == "NOMINAL":
            return spice.observer_state_m(snapshot, query)
        if mode == "STATIC_OBSERVER":
            result = nominal_state.copy()
            result[3:] = 0.0
            return result
        if mode == "EARTH_CENTER":
            return np.zeros(6, dtype=np.float64)
        raise LuGreSnapshotError("UNKNOWN_OBSERVER_NULL")

    half = RANGE_DERIVATIVE_HALF_STEP_S
    minus = utc - timedelta(seconds=half)
    plus = utc + timedelta(seconds=half)
    range_minus, _, _, tx_minus = _range_m(
        spice, snapshot, records, satellite, minus, observer
    )
    range_plus, _, _, tx_plus = _range_m(
        spice, snapshot, records, satellite, plus, observer
    )
    range_nominal, satellite_position, observer_position, tx_nominal = _range_m(
        spice, snapshot, records, satellite, utc, observer
    )
    range_rate = (range_plus - range_minus) / (2.0 * half)
    record = geometry.select_ephemeris(records[satellite], tx_nominal)
    clock_rate = (_clock_bias_s(record, tx_plus) - _clock_bias_s(record, tx_minus)) / (
        2.0 * half
    )
    frequency = GPS_L1_HZ * (-range_rate / SPEED_OF_LIGHT_M_S + clock_rate)
    return frequency, {
        "range_m": range_nominal,
        "range_rate_m_s": range_rate,
        "broadcast_clock_rate_s_s": clock_rate,
        "earth_occulted": _earth_occulted(satellite_position, observer_position),
        "off_boresight_deg": _off_boresight_deg(satellite_position, observer_position),
    }


def _values_for_mode(
    spice: SpiceGeometry,
    snapshot: Snapshot,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    utc: datetime,
    mode: str,
    satellites: Sequence[str] | None = None,
) -> tuple[dict[str, float], dict[str, dict[str, float | bool]]]:
    population = tuple(sorted(records)) if satellites is None else tuple(satellites)
    values: dict[str, float] = {}
    diagnostics: dict[str, dict[str, float | bool]] = {}
    for satellite in population:
        try:
            frequency, row = _frequency_hz(
                spice, snapshot, records, satellite, utc, mode
            )
        except geometry.GnssDoubleDifferenceError:
            continue
        diagnostics[satellite] = row
        if mode != "NOMINAL" or not bool(row["earth_occulted"]):
            values[satellite] = frequency
    return values, diagnostics


def _timing_sensitivity(
    spice: SpiceGeometry,
    snapshot: Snapshot,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    nominal_values: Mapping[str, float],
    subset: Sequence[str],
) -> list[dict[str, object]]:
    identities, rows = _codebook(nominal_values)
    _, _, normalized = _center_and_normalize(rows)
    tree = cKDTree(normalized)
    identity = tuple(sorted(subset))
    correct_index = identities.index(identity)
    result = []
    for shift in TIMING_SHIFTS_S:
        shifted, _ = _values_for_mode(
            spice,
            snapshot,
            records,
            parse_utc(snapshot.utc) + timedelta(seconds=shift),
            "NOMINAL",
            subset,
        )
        if set(shifted) != set(identity):
            result.append(
                {"shift_s": shift, "state": "EPHEMERIS_OR_VISIBILITY_UNAVAILABLE"}
            )
            continue
        observed = np.asarray([sorted(shifted.values())], dtype=np.float64)
        _, _, observed_normalized = _center_and_normalize(observed)
        _, nearest = tree.query(observed_normalized, k=2)
        best = int(nearest[0, 0])
        runner = int(nearest[0, 1])
        correct_rmse = affine_residual_rmse_hz(observed[0], rows[correct_index])
        wrong_rmse = affine_residual_rmse_hz(
            observed[0], rows[runner if best == correct_index else best]
        )
        result.append(
            {
                "shift_s": shift,
                "state": "CORRECT_SUBSET_REMAINS_BEST"
                if best == correct_index
                else "WRONG_SUBSET_BECOMES_BEST",
                "correct_subset_rmse_hz": correct_rmse,
                "nearest_wrong_subset": list(
                    identities[runner if best == correct_index else best]
                ),
                "nearest_wrong_rmse_hz": wrong_rmse,
                "preference_margin_rmse_hz": wrong_rmse - correct_rmse,
            }
        )
    return result


def compile_snapshot(
    spice: SpiceGeometry,
    snapshot: Snapshot,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
) -> dict[str, object]:
    utc = parse_utc(snapshot.utc)
    nominal, diagnostics = _values_for_mode(spice, snapshot, records, utc, "NOMINAL")
    if len(nominal) < MINIMUM_CANDIDATE_POOL:
        return {
            **asdict(snapshot),
            "state": "TOO_FEW_UNOCCULTED_HEALTHY_GPS_SATELLITES",
            "candidate_count": len(nominal),
        }
    assignment = codebook_separation(nominal)
    satellites = tuple(sorted(nominal))
    earth_center, _ = _values_for_mode(
        spice, snapshot, records, utc, "EARTH_CENTER", satellites
    )
    static, _ = _values_for_mode(
        spice, snapshot, records, utc, "STATIC_OBSERVER", satellites
    )
    nulls = {
        "RANK_AFFINE": rank_affine_null(nominal),
        "EARTH_CENTER_OBSERVER": null_separation(nominal, earth_center),
        "STATIC_OBSERVER": null_separation(nominal, static),
    }
    assignment_margin = float(
        assignment["controlling_assignment"]["affine_projected_rmse_hz"]  # type: ignore[index]
    )
    controlling_null_name, controlling_null = min(
        nulls.items(), key=lambda item: float(item[1]["affine_projected_rmse_hz"])
    )
    controlling_separation = min(
        assignment_margin, float(controlling_null["affine_projected_rmse_hz"])
    )
    controlling_source = (
        "NEAREST_WRONG_GPS_SUBSET"
        if assignment_margin <= float(controlling_null["affine_projected_rmse_hz"])
        else controlling_null_name
    )
    boresight = {
        satellite: float(diagnostics[satellite]["off_boresight_deg"])
        for satellite in satellites
    }
    selected_subset = tuple(
        satellite
        for satellite, _ in sorted(
            boresight.items(), key=lambda item: (item[1], item[0])
        )[:SIGNALS_PER_SNAPSHOT]
    )
    selected_assignment = subset_separation(nominal, selected_subset)
    selected_nulls = {
        "RANK_AFFINE": subset_rank_affine_null(nominal, selected_subset),
        "EARTH_CENTER_OBSERVER": subset_null_separation(
            nominal, selected_subset, earth_center
        ),
        "STATIC_OBSERVER": subset_null_separation(nominal, selected_subset, static),
    }
    selected_null_name, selected_null = min(
        selected_nulls.items(),
        key=lambda item: float(item[1]["affine_projected_rmse_hz"]),
    )
    selected_assignment_margin = float(selected_assignment["affine_projected_rmse_hz"])
    selected_null_margin = float(selected_null["affine_projected_rmse_hz"])
    selected_controlling = min(selected_assignment_margin, selected_null_margin)
    selected_source = (
        "NEAREST_WRONG_GPS_SUBSET"
        if selected_assignment_margin <= selected_null_margin
        else selected_null_name
    )
    return {
        **asdict(snapshot),
        "state": "GEOMETRY_COMPILED",
        "candidate_pool": {
            "selection": "ALL_HEALTHY_BROADCAST_GPS_NOT_EARTH_OCCULTED_NO_RF_POWER_CLAIM",
            "satellites": list(satellites),
            "count": len(satellites),
            "off_boresight_deg": boresight,
            "minimum_deg": min(boresight.values()),
            "maximum_deg": max(boresight.values()),
        },
        "assignment_codebook": assignment,
        "nulls": nulls,
        "complete_pool_stress_controlling_separation": {
            "source": controlling_source,
            "affine_projected_rmse_hz": controlling_separation,
            "maximum_total_per_track_rms_envelope_hz": controlling_separation / 2.0,
            "geometry_only_maximum_detector_bin_width_hz": controlling_separation,
        },
        "geometry_selected_candidate_family": {
            "selection": "FOUR_MINIMUM_TRANSMIT_OFF_BORESIGHT_AMONG_UNOCCULTED_HEALTHY_GPS",
            "selection_uses_rf_values": False,
            "satellites": list(selected_subset),
            "off_boresight_deg": {
                satellite: boresight[satellite] for satellite in selected_subset
            },
            "transmit_gain_or_received_power_inferred": False,
            "assignment": selected_assignment,
            "nulls": selected_nulls,
            "controlling_separation": {
                "source": selected_source,
                "affine_projected_rmse_hz": selected_controlling,
                "maximum_total_per_track_rms_envelope_hz": selected_controlling / 2.0,
                "geometry_only_maximum_detector_bin_width_hz": selected_controlling,
            },
        },
        "timing_sensitivity_for_controlling_true_subset": _timing_sensitivity(
            spice, snapshot, records, nominal, selected_subset
        ),
    }


def manifest() -> dict[str, object]:
    value = {
        "schema": "lugre-snapshot-discriminability-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "physical_question": "CAN_ONE_SIMULTANEOUS_ANONYMOUS_GPS_DOPPLER_SET_RETAIN_ORBITAL_IDENTITY_AFTER_COMMON_CLOCK_AND_SCALE_PROJECTION",
        "new_information": "EXACT_OPERATION_GEOMETRY_CODEBOOK_AND_ORBIT_VERSUS_NONORBITAL_NULL_MARGIN_BEFORE_LUGRE_ACCESS",
        "minimum_experiment": "SEVEN_PUBLIC_OPERATION_TIMES_HISTORICAL_BROADCAST_GPS_ARCHIVED_BLUE_GHOST_GEOMETRY_FOUR_SIGNAL_CODEBOOK_ZERO_RF",
        "stop_condition": "STOP_NO_SNAPSHOT_DISCRIMINABILITY_IF_EVERY_CONTROLLING_MARGIN_IS_NONPOSITIVE_OR_REQUIRES_TARGET_RF_DERIVED_GEOMETRY",
        "snapshots": [asdict(snapshot) for snapshot in SNAPSHOTS],
        "navigation": [asdict(authority) for authority in NAVIGATION],
        "spice": [asdict(authority) for authority in SPICE],
        "coordinate": {
            "band": "GPS_L1",
            "carrier_hz": GPS_L1_HZ,
            "signals_per_snapshot": SIGNALS_PER_SNAPSHOT,
            "common_offset": "PROJECTED",
            "common_positive_scale": "PROJECTED_WITH_EQUAL_COMPLEXITY_FOR_ALL_HYPOTHESES",
            "receiver_spectrum_sign": "MUST_BE_HEADER_DECLARED_BEFORE_FUTURE_SCORE",
            "one_way_light_time": "ITERATED",
            "broadcast_clock_rate": "INCLUDED_FROM_SAME_HISTORICAL_NAVIGATION",
        },
        "candidate_population": "ALL_HEALTHY_GPS_IN_DAILY_BROADCAST_FILE_WITH_UNOCCULTED_EARTH_LINE_OF_SIGHT",
        "candidate_family_selection": "FOUR_MINIMUM_TRANSMIT_OFF_BORESIGHT_WITHOUT_USING_GAIN_OR_RF_VALUES",
        "rf_detectability": "NOT_INFERRED_FROM_BORESIGHT_OR_GEOMETRY",
        "nulls": [
            "NEAREST_WRONG_GPS_SUBSET",
            "RANK_AFFINE",
            "EARTH_CENTER_OBSERVER",
            "STATIC_OBSERVER",
        ],
        "open_terms": [
            "PRODUCT_APPLICABLE_ADC_TO_GPST_ERROR",
            "SAMPLE_RATE_ACCURACY_AND_NONAFFINE_OSCILLATOR",
            "PER_SIGNAL_TRANSMITTER_CLOCK_RESIDUAL_AFTER_BROADCAST_MODEL",
            "DIFFERENTIAL_MEDIA_AFTER_ANY_L1_L5_WITNESS",
            "TRACKER_AND_FREQUENCY_RESOLUTION",
            "ACTUAL_FOUR_SIGNAL_AVAILABILITY_IN_FROZEN_CODEBOOK",
        ],
        "observation_boundary": {
            "lugre_archive_requests": 0,
            "lugre_headers": 0,
            "lugre_payload_bytes": 0,
            "iq_bytes": 0,
            "telemetry_bytes": 0,
            "signal_derived_values": 0,
            "orbital_scores_from_measurement": 0,
        },
        "prospective_plan_frozen": False,
        "primary_selected": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def compile_sweep(input_root: Path) -> dict[str, object]:
    paths = {
        authority.name: _validate_file(input_root, authority)
        for authority in NAVIGATION
    }
    records_by_doy = {
        int(authority.name[4:7]): parse_navigation_payload(
            paths[authority.name].read_bytes()
        )
        for authority in NAVIGATION
    }
    spice = SpiceGeometry(input_root)
    try:
        rows = [
            compile_snapshot(spice, snapshot, records_by_doy[snapshot.doy])
            for snapshot in SNAPSHOTS
        ]
    finally:
        spice.close()
    compiled = [row for row in rows if row["state"] == "GEOMETRY_COMPILED"]
    positive = [
        row
        for row in compiled
        if float(
            row["geometry_selected_candidate_family"]["controlling_separation"][  # type: ignore[index]
                "affine_projected_rmse_hz"
            ]
        )
        > 0.0
    ]
    ranked = sorted(
        positive,
        key=lambda row: (
            -float(
                row["geometry_selected_candidate_family"][  # type: ignore[index]
                    "controlling_separation"
                ]["affine_projected_rmse_hz"]
            ),
            str(row["utc"]),
        ),
    )
    result = {
        "schema": "lugre-snapshot-discriminability-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": canonical_sha256(Path(__file__)),
        "dependencies": {
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "spiceypy": importlib.metadata.version("spiceypy"),
            "python": platform.python_version(),
        },
        "manifest": manifest(),
        "rows": rows,
        "ranked_operations": [
            {
                "rank": rank,
                "operation": row["operation"],
                "utc": row["utc"],
                "candidate_family": row["geometry_selected_candidate_family"],
            }
            for rank, row in enumerate(ranked, 1)
        ],
        "outcome": OUTCOME_POSITIVE if ranked else OUTCOME_NONE,
        "measurement_admission": "NOT_EVALUATED_OPEN_TERMS",
        "maximum_authorized_claim": "BOUNDED_GEOMETRY_MECHANISM_ONLY_NO_LUGRE_SIGNAL_OR_ORBITAL_MEASUREMENT_CLAIM"
        if ranked
        else None,
        "observation_access": manifest()["observation_boundary"],
    }
    strict_json(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name(RECEIPT_NAME)
    )
    args = parser.parse_args()
    receipt = compile_sweep(args.input_root)
    args.output.write_text(
        strict_json(receipt, pretty=True) + "\n", encoding="ascii", newline="\n"
    )
    print(
        strict_json(
            {
                "outcome": receipt["outcome"],
                "receipt": str(args.output),
                "lugre_payload_bytes": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
