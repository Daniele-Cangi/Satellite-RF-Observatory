"""Orbit-only visibility screen for the frozen DORIS time-reference pairs.

This bounded calculation reuses the exact-hash pre-observation SP3 products
and the frozen G0/DORIS visibility rules.  It cannot open DORIS observations.
If joint visibility is absent, orbital-versus-null scoring is not defined.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import acos, cos, degrees, radians
from pathlib import Path
from typing import Final, Mapping

import numpy as np

from experiments.live_instrument.models import strict_json_value
from experiments.orbital_discriminability import doris_forward_geometry_spike as base


SCREEN_VERSION: Final = "doris-time-reference-geometry-screen-v1"
OUTCOME_NO_JOINT_VISIBILITY: Final = (
    "DORIS_TIME_REFERENCE_TOPOLOGY_NO_JOINT_VISIBILITY"
)
FROZEN_PARENT_COMMIT: Final = "4c9fa63bbfba46a5ec6893abfb08df8221e4e75c"
TOPOLOGY_RECEIPT_SHA256: Final = (
    "2367428de48c354dca71a008754895d4d5af1967d9936d406d9d9b1d899007a7"
)

ROOT: Final = Path(__file__).resolve().parent
TOPOLOGY_RECEIPT: Final = ROOT / "DORIS_OBSERVABLE_TOPOLOGY_REVIEW_RECEIPT.json"

# Minute-resolution geographic coordinates from the public IDS station table,
# last updated 2026-06-03. Height remains deliberately unresolved at screening.
STATIONS: Final[Mapping[str, base.Station]] = {
    "ADHC": base.Station("ADHC", -(66.0 + 40.0 / 60.0), 140.0),
    "HBMB": base.Station("HBMB", -(25.0 + 53.0 / 60.0), 27.0 + 42.0 / 60.0),
    "PAUB": base.Station("PAUB", -(17.0 + 35.0 / 60.0), -(149.0 + 36.0 / 60.0)),
    "TLSB": base.Station("TLSB", 43.0 + 33.0 / 60.0, 1.0 + 29.0 / 60.0),
}

PAIRS: Final = (
    ("ADHC", "HBMB"),
    ("ADHC", "PAUB"),
    ("ADHC", "TLSB"),
    ("HBMB", "PAUB"),
    ("HBMB", "TLSB"),
    ("PAUB", "TLSB"),
)


class DorisTimeReferenceGeometryError(ValueError):
    """Raised when a frozen input or geometric invariant is violated."""


def canonical_sha256(path: Path) -> str:
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def validate_topology_receipt() -> dict[str, object]:
    if canonical_sha256(TOPOLOGY_RECEIPT) != TOPOLOGY_RECEIPT_SHA256:
        raise DorisTimeReferenceGeometryError("TOPOLOGY_RECEIPT_HASH_MISMATCH")
    receipt = json.loads(TOPOLOGY_RECEIPT.read_text(encoding="utf-8"))
    if receipt["outcome"] != (
        "DORIS_TIME_REFERENCE_PAIR_SELECTED_GEOMETRY_UNEVALUATED"
    ):
        raise DorisTimeReferenceGeometryError("UNEXPECTED_TOPOLOGY_OUTCOME")
    frozen_pairs = tuple(
        tuple(pair)
        for pair in receipt["time_reference_scope"][
            "bounded_pair_set_for_later_geometry_only_review"
        ]
    )
    if frozen_pairs != PAIRS:
        raise DorisTimeReferenceGeometryError("TIME_REFERENCE_PAIR_SCOPE_CHANGED")
    return receipt


def _common_day_grid(
    trajectories: tuple[base.Sp3Trajectory, ...],
) -> tuple[np.ndarray, np.ndarray]:
    day_start_utc = datetime.combine(
        base.CANDIDATE_DAY_UTC, datetime.min.time(), timezone.utc
    )
    day_end_utc = day_start_utc + timedelta(days=1)
    day_start_tai = day_start_utc + timedelta(seconds=base.TAI_MINUS_UTC_S)
    day_end_tai = day_end_utc + timedelta(seconds=base.TAI_MINUS_UTC_S)
    starts = tuple(
        trajectory.start_tai
        + timedelta(seconds=float(trajectory.times_tai_s[0]))
        for trajectory in trajectories
    )
    ends = tuple(
        trajectory.start_tai
        + timedelta(seconds=float(trajectory.times_tai_s[-1]))
        for trajectory in trajectories
    )
    start_tai = max(day_start_tai, *starts)
    end_tai = min(day_end_tai, *ends)
    if end_tai <= start_tai:
        raise DorisTimeReferenceGeometryError("FROZEN_ORBITS_HAVE_NO_COMMON_DAY_GRID")

    current = trajectories[0]
    start_s = (start_tai - current.start_tai).total_seconds()
    end_s = (end_tai - current.start_tai).total_seconds()
    grid = np.arange(
        start_s,
        end_s + base.INTERPOLATION_STEP_S * 0.5,
        base.INTERPOLATION_STEP_S,
        dtype=float,
    )
    utc = np.array(
        [
            current.start_tai
            + timedelta(seconds=float(value) - base.TAI_MINUS_UTC_S)
            for value in grid
        ],
        dtype=object,
    )
    return grid, utc


def _angle_deg(left: np.ndarray, right: np.ndarray) -> float:
    cosine = float(
        np.dot(left, right) / (np.linalg.norm(left) * np.linalg.norm(right))
    )
    return degrees(acos(float(np.clip(cosine, -1.0, 1.0))))


def station_geometry(station: base.Station) -> tuple[np.ndarray, float, float]:
    position, normal = base.station_ecef(station)
    radius_m = float(np.linalg.norm(position))
    normal_offset_deg = _angle_deg(position, normal)
    return position, radius_m, normal_offset_deg


def conservative_visibility_cap_deg(
    *,
    station_radius_m: float,
    satellite_radius_ceiling_m: float,
    minimum_elevation_deg: float,
    normal_offset_deg: float,
) -> float:
    """Bound the geocentric station-to-subsatellite angle continuously.

    The geodetic normal may tilt away from the station radius.  Reducing the
    elevation cutoff by that exact station-specific angle makes the cap more
    permissive and therefore safe for an impossibility proof.
    """

    radial_elevation_deg = minimum_elevation_deg - normal_offset_deg
    if radial_elevation_deg <= 0.0:
        raise DorisTimeReferenceGeometryError("NONPOSITIVE_RADIAL_ELEVATION_BOUND")
    ratio = station_radius_m / satellite_radius_ceiling_m
    if not 0.0 < ratio < 1.0:
        raise DorisTimeReferenceGeometryError("INVALID_ORBIT_RADIUS_CEILING")
    elevation = radians(radial_elevation_deg)
    return degrees(acos(ratio * cos(elevation))) - radial_elevation_deg


def _longest_joint_duration_s(mask: np.ndarray) -> float:
    segments = base.contiguous_true_segments(mask)
    if not segments:
        return 0.0
    return max(
        (end - start) * base.INTERPOLATION_STEP_S for start, end in segments
    )


def evaluate_visibility(
    current: base.Sp3Trajectory,
    prior: base.Sp3Trajectory,
    alternative: base.Sp3Trajectory,
) -> dict[str, object]:
    validate_topology_receipt()
    grid, utc = _common_day_grid((current, prior, alternative))
    position, velocity = base.interpolate_hermite(current, grid)
    satellite_radius_ceiling_m = float(np.max(np.linalg.norm(position, axis=1)))
    coordinates = {
        code: base.station_coordinate(station, position, velocity)
        for code, station in STATIONS.items()
    }

    station_geometry_by_code = {
        code: station_geometry(station) for code, station in STATIONS.items()
    }
    rows: list[dict[str, object]] = []
    for left, right in PAIRS:
        left_position, left_radius, left_offset = station_geometry_by_code[left]
        right_position, right_radius, right_offset = station_geometry_by_code[right]
        separation_deg = _angle_deg(left_position, right_position)
        left_cap = conservative_visibility_cap_deg(
            station_radius_m=left_radius,
            satellite_radius_ceiling_m=satellite_radius_ceiling_m,
            minimum_elevation_deg=base.MIN_ELEVATION_DEG,
            normal_offset_deg=left_offset,
        )
        right_cap = conservative_visibility_cap_deg(
            station_radius_m=right_radius,
            satellite_radius_ceiling_m=satellite_radius_ceiling_m,
            minimum_elevation_deg=base.MIN_ELEVATION_DEG,
            normal_offset_deg=right_offset,
        )
        excess_separation_deg = separation_deg - left_cap - right_cap
        left_elevation = coordinates[left]["elevation_deg"]
        right_elevation = coordinates[right]["elevation_deg"]
        joint_minimum_elevation = np.minimum(left_elevation, right_elevation)
        best_index = int(np.argmax(joint_minimum_elevation))
        joint_mask = (
            (left_elevation >= base.MIN_ELEVATION_DEG)
            & (right_elevation >= base.MIN_ELEVATION_DEG)
        )
        rows.append(
            {
                "pair": [left, right],
                "station_geocentric_separation_deg": separation_deg,
                "conservative_joint_cap_deg": left_cap + right_cap,
                "continuous_impossibility_excess_deg": excess_separation_deg,
                "maximum_grid_minimum_elevation_deg": float(
                    joint_minimum_elevation[best_index]
                ),
                "maximum_grid_minimum_elevation_utc": utc[best_index].isoformat(),
                "joint_grid_sample_count": int(np.count_nonzero(joint_mask)),
                "longest_joint_duration_s": _longest_joint_duration_s(joint_mask),
                "minimum_required_joint_duration_s": base.MIN_JOINT_INTERVAL_S,
                "visibility_state": (
                    "CONTINUOUSLY_IMPOSSIBLE_AT_FROZEN_ELEVATION_AND_ORBIT_RADIUS"
                    if excess_separation_deg > 0.0
                    else "REQUIRES_GRID_EVALUATION"
                ),
            }
        )

    ranked = sorted(
        rows,
        key=lambda row: float(row["continuous_impossibility_excess_deg"]),
    )
    any_joint = any(int(row["joint_grid_sample_count"]) > 0 for row in rows)
    all_continuously_impossible = all(
        float(row["continuous_impossibility_excess_deg"]) > 0.0 for row in rows
    )
    if any_joint or not all_continuously_impossible:
        raise DorisTimeReferenceGeometryError("UNEXPECTED_JOINT_VISIBILITY")

    result: dict[str, object] = {
        "outcome": OUTCOME_NO_JOINT_VISIBILITY,
        "screen_version": SCREEN_VERSION,
        "frozen_parent_commit": FROZEN_PARENT_COMMIT,
        "topology_receipt_sha256": TOPOLOGY_RECEIPT_SHA256,
        "physical_question": (
            "CAN_ANY_FROZEN_PAIR_OF_HEADER_DECLARED_TIME_REFERENCE_BEACONS_"
            "SUPPORT_A_JOINT_HELDOUT_SENTINEL_3A_ORBITAL_COORDINATE"
        ),
        "scope": {
            "candidate": "SENTINEL_3A_NORAD_41335",
            "candidate_day_utc": base.CANDIDATE_DAY_UTC.isoformat(),
            "time_reference_pairs": [list(pair) for pair in PAIRS],
            "orbit_product_access": "THREE_PREVIOUSLY_FROZEN_EXACT_HASH_SP3_FILES",
            "rinex_artifact_access": "ZERO",
            "observation_values_access": "ZERO",
            "orbital_score": "NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW",
            "new_gate": "NONE",
        },
        "station_source": {
            "authority": "IDS_CURRENT_STATION_TABLE",
            "url": "https://ids-doris.org/network-stations/sites.html",
            "last_updated": "2026-06-03",
            "coordinate_resolution_arcmin": 1.0,
            "height_state": "UNRESOLVED_SCREENING_ZERO_ONLY",
            "coordinates": {
                code: {
                    "latitude_deg": station.latitude_deg,
                    "longitude_deg": station.longitude_deg,
                }
                for code, station in STATIONS.items()
            },
        },
        "frozen_rules": {
            "grid_s": base.INTERPOLATION_STEP_S,
            "minimum_elevation_deg": base.MIN_ELEVATION_DEG,
            "minimum_joint_interval_s": base.MIN_JOINT_INTERVAL_S,
            "calibration_fraction": base.CALIBRATION_FRACTION,
            "minimum_calibration_s": base.MIN_CALIBRATION_S,
            "minimum_heldout_s": base.MIN_HELDOUT_S,
            "affine_null": "FROZEN_NOT_EVALUATED_NO_JOINT_WINDOW",
            "along_track_nulls_s": list(base.FROZEN_ALONG_TRACK_SHIFTS_S),
            "wrong_orbit_null": "SENTINEL_3B_FROZEN_NOT_EVALUATED_NO_JOINT_WINDOW",
            "forecast_envelope": "PRIOR_S3A_FROZEN_NOT_EVALUATED_NO_JOINT_WINDOW",
        },
        "continuous_visibility_proof": {
            "satellite_radius_ceiling_m": satellite_radius_ceiling_m,
            "radius_source": "MAXIMUM_ON_EXACT_CURRENT_SP3_COMMON_DAY_GRID",
            "normal_policy": (
                "STATION_SPECIFIC_GEODETIC_TO_GEOCENTRIC_NORMAL_OFFSET_"
                "SUBTRACTED_FROM_ELEVATION_CUTOFF"
            ),
            "pair_results": rows,
            "diagnostic_ranking_only": [row["pair"] for row in ranked],
        },
        "null_evaluation": {
            "state": "NOT_EVALUATED_NO_ADMISSIBLE_JOINT_WINDOW",
            "reason": (
                "NULL_COMPARISON_REQUIRES_A_CALIBRATION_PREFIX_AND_HELDOUT_"
                "SUFFIX_INSIDE_JOINT_VISIBILITY"
            ),
            "thresholds_changed": False,
        },
        "decision": {
            "time_reference_pair_topology": (
                "CLOSED_FOR_FROZEN_SENTINEL_3A_CANDIDATE_GEOMETRY"
            ),
            "shortlist": [],
            "measurement_access_authorized": False,
            "next_action": "CHANGE_OF_ABSTRACTION_REVIEW_REQUIRED",
            "forbidden_next_action": (
                "SEARCH_FOR_CONVENIENT_DORIS_OBSERVATION_OR_WEAKEN_VISIBILITY"
            ),
        },
        "input_artifacts": [
            {
                "name": base.CURRENT_S3A_NAME,
                "bytes": base.CURRENT_S3A_BYTES,
                "sha256": base.CURRENT_S3A_SHA256,
                "role": "CURRENT_PRE_OBSERVATION_S3A_FORECAST",
            },
            {
                "name": base.PRIOR_S3A_NAME,
                "bytes": base.PRIOR_S3A_BYTES,
                "sha256": base.PRIOR_S3A_SHA256,
                "role": "PRIOR_S3A_FORECAST_ENVELOPE_FROZEN_NOT_SCORED",
            },
            {
                "name": base.ALTERNATIVE_S3B_NAME,
                "bytes": base.ALTERNATIVE_S3B_BYTES,
                "sha256": base.ALTERNATIVE_S3B_SHA256,
                "role": "WRONG_ORBIT_NULL_FROZEN_NOT_SCORED",
            },
        ],
        "ephemeral_orbit_artifact_retention": "ZERO_AFTER_HASHED_ANALYSIS",
        "shock": (
            "THE_ONLY_HEADER_DECLARED_TIME_REFERENCE_ROOTS_ARE_GEOGRAPHICALLY_"
            "TOO_SEPARATED_FOR_THE_SHARED_LEO_RECEIVER_TO_OBSERVE_ANY_PAIR;_"
            "CLOCK_QUALITY_AND_JOINT_VISIBILITY_ARE_ANTI_CORRELATED_IN_THIS_SCOPE"
        ),
    }
    strict_json(result)
    return result


def run_from_directory(directory: Path) -> dict[str, object]:
    directory = Path(directory)
    current = base.parse_frozen_sp3_z(
        directory / base.CURRENT_S3A_NAME,
        expected_name=base.CURRENT_S3A_NAME,
        expected_sha256=base.CURRENT_S3A_SHA256,
        expected_satellite_id="L74",
    )
    prior = base.parse_frozen_sp3_z(
        directory / base.PRIOR_S3A_NAME,
        expected_name=base.PRIOR_S3A_NAME,
        expected_sha256=base.PRIOR_S3A_SHA256,
        expected_satellite_id="L74",
    )
    alternative = base.parse_frozen_sp3_z(
        directory / base.ALTERNATIVE_S3B_NAME,
        expected_name=base.ALTERNATIVE_S3B_NAME,
        expected_sha256=base.ALTERNATIVE_S3B_SHA256,
        expected_satellite_id="L98",
    )
    return evaluate_visibility(current, prior, alternative)


def strict_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> int:
    quarantine = Path(".quarantine-doris-time-reference-geometry")
    print(strict_json(run_from_directory(quarantine)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
