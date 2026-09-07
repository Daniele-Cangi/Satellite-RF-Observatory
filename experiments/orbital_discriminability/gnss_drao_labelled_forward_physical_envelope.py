"""Bounded model-side physical envelope for the fixed DRAO DOY237 cell.

The only transient payload accepted is the exact shortlisted broadcast-
navigation product.  This module has no observation locator, observation
decoder, carrier-phase input or scoring surface.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from math import isfinite, radians, sin, sqrt
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_geometry_screen as screen,
)
from experiments.orbital_discriminability import gnss_double_difference_screen as geometry


AUDIT_VERSION: Final = "gnss-drao-labelled-forward-physical-envelope-v1"
SCOPE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_PHYSICAL_ENVELOPE_SCOPE.md"
SCOPE_SHA256: Final = "61db6ed5c1f57aa2c358cbd873c115c048e028160f1ff8459e0921a21da05817"
PARENT_NAME: Final = screen.RECEIPT_NAME
PARENT_SHA256: Final = "06161af57ada12e081faef7cf470e540ea5fff5dd7cf2f6614077b738852ed62"
RECEIPT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_PHYSICAL_ENVELOPE.json"
REPORT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_PHYSICAL_ENVELOPE_REPORT.md"

OUTCOME_ADMITTED: Final = "DRAO_LABELLED_FORWARD_PHYSICAL_MARGIN_ADMITTED"
OUTCOME_DOMINATES: Final = "DRAO_LABELLED_FORWARD_PHYSICAL_ENVELOPE_DOMINATES"
OUTCOME_UNAVAILABLE: Final = "DRAO_LABELLED_FORWARD_PHYSICAL_BOUND_UNAVAILABLE"

DOY: Final = 237
GPS_DATE: Final = "2026-08-25"
CODEBOOK: Final = ("G14", "G15", "G17", "G20", "G24", "G30")
GPS_START: Final = datetime(2026, 8, 25, 4, 55, 0, tzinfo=timezone.utc)
GPS_STOP: Final = datetime(2026, 8, 25, 6, 4, 0, tzinfo=timezone.utc)
EXPECTED_SCREEN_SEPARATION_M: Final = 36_546.47062947322
EXPECTED_SCREEN_TIMING_ENVELOPE_M: Final = 1_396.8700135458348
EXPECTED_SCREEN_MINIMUM_ELEVATION_DEG: Final = 15.103639282444858

NAVIGATION_NAME: Final = "brdc2370.26n.gz"
NAVIGATION_BYTES: Final = 71_512
NAVIGATION_SHA256: Final = "7676ce71221f4a0313f5ba2981886826c87ff346782b0993b9505b0dc0722ca8"
NAVIGATION_RAW_SHA256: Final = "09ebad2417413c30f507c4f7a784b8f67c61a129b4246d45e1d58803d1cddb22"

TIMING_OFFSETS_S: Final = (-15.0, 15.0)
ZENITH_DELAY_MAX_M: Final = 3.5
STATION_EOP_RELATIVITY_BOUND_M: Final = 4.0
HIGHER_ORDER_IONOSPHERE_RESERVE_M: Final = 2.0
ANTENNA_WINDUP_RESERVE_M: Final = 4.0
COMPLETE_CODE_WITNESS_RESERVE_M: Final = 2_500.0
RINEX_F14_3_QUANTIZATION_M: Final = 0.0017238368006440115
CAPABILITY_CONDITIONAL_RESERVE_M: Final = (
    HIGHER_ORDER_IONOSPHERE_RESERVE_M
    + ANTENNA_WINDUP_RESERVE_M
    + COMPLETE_CODE_WITNESS_RESERVE_M
    + RINEX_F14_3_QUANTIZATION_M
)
DECISION_MULTIPLIER: Final = 3.0
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244
CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M: Final = 1_250.0


class DraoLabelledEnvelopeError(ValueError):
    """A frozen authority, physical input or numerical invariant changed."""


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


def _reject_nonfinite(token: str) -> object:
    raise DraoLabelledEnvelopeError(f"NONFINITE_PARENT:{token}")


def _read_strict_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"), parse_constant=_reject_nonfinite
    )
    if not isinstance(value, dict):
        raise DraoLabelledEnvelopeError(f"NOT_JSON_OBJECT:{Path(path).name}")
    return value


def _close(actual: float, expected: float, name: str, tolerance: float = 1.0e-9) -> None:
    if not isfinite(actual) or abs(actual - expected) > tolerance:
        raise DraoLabelledEnvelopeError(f"{name}_CHANGED")


def validate_frozen_authority(root: Path) -> dict[str, object]:
    base = Path(root)
    scope = base / SCOPE_NAME
    parent_path = base / PARENT_NAME
    if canonical_sha256(scope) != SCOPE_SHA256:
        raise DraoLabelledEnvelopeError("FROZEN_SCOPE_CHANGED")
    if canonical_sha256(parent_path) != PARENT_SHA256:
        raise DraoLabelledEnvelopeError("FROZEN_PARENT_CHANGED")
    parent = _read_strict_json(parent_path)
    if parent.get("outcome") != screen.OUTCOME_SELECTED:
        raise DraoLabelledEnvelopeError("PARENT_OUTCOME_CHANGED")
    shortlist = parent.get("shortlist")
    if not isinstance(shortlist, list) or not shortlist:
        raise DraoLabelledEnvelopeError("PARENT_SHORTLIST_MISSING")
    selected = shortlist[0]
    expected = {
        "doy": DOY,
        "gps_date": GPS_DATE,
        "raw_start_gps": geometry.format_gps(
            GPS_START - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
        ),
        "raw_stop_gps": geometry.format_gps(
            GPS_STOP - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
        ),
        "candidate_codebook": list(CODEBOOK),
        "controlling_null": "TIME_REVERSED_GEOMETRY",
    }
    for key, value in expected.items():
        if selected.get(key) != value:
            raise DraoLabelledEnvelopeError(f"PARENT_RANK1_{key.upper()}_CHANGED")
    _close(
        float(selected["exact_controlling_separation_m"]),
        EXPECTED_SCREEN_SEPARATION_M,
        "PARENT_SCREEN_SEPARATION",
    )
    _close(
        float(selected["direct_time_shift_envelope_m"]),
        EXPECTED_SCREEN_TIMING_ENVELOPE_M,
        "PARENT_SCREEN_TIMING",
    )
    _close(
        float(selected["minimum_time_shifted_elevation_deg"]),
        EXPECTED_SCREEN_MINIMUM_ELEVATION_DEG,
        "PARENT_SCREEN_ELEVATION",
    )
    if any(int(value) != 0 for value in parent["observation_access"].values()):
        raise DraoLabelledEnvelopeError("PARENT_OBSERVATION_ACCESS_CHANGED")
    return {
        "scope": {"filename": SCOPE_NAME, "canonical_sha256": SCOPE_SHA256},
        "parent": {
            "filename": PARENT_NAME,
            "canonical_sha256": PARENT_SHA256,
            "outcome": parent["outcome"],
            "rank": 1,
        },
    }


def manifest(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    value = {
        "schema": "gnss-drao-labelled-forward-physical-envelope-manifest-v1",
        "audit_version": AUDIT_VERSION,
        "authority": validate_frozen_authority(base),
        "physical_question": (
            "DOES_THE_FIXED_DOY237_LABELLED_GEOMETRY_RETAIN_POSITIVE_HELDOUT_"
            "SEPARATION_AFTER_A_DATE_SPECIFIC_PHYSICAL_ENVELOPE"
        ),
        "new_information": (
            "WHETHER_RANK1_IS_PHYSICALLY_WORTH_ONE_LATER_STRUCTURAL_QUALIFICATION"
        ),
        "geometry": {
            "station": screen.STATION.station_id,
            "doy": DOY,
            "gps_date": GPS_DATE,
            "codebook": list(CODEBOOK),
            "raw_start_gps": "2026-08-25T04:55:00 GPS",
            "raw_stop_gps": "2026-08-25T06:04:00 GPS",
            "heldout_start_gps": "2026-08-25T05:34:30 GPS",
            "step_s": screen.STEP_S,
            "raw_epochs": screen.RAW_EPOCHS,
            "prefix_epochs": screen.PREFIX_EPOCHS,
            "nulls": ["PREFIX_AFFINE_ONLY", "TIME_REVERSED_GEOMETRY"],
        },
        "navigation": {
            "filename": NAVIGATION_NAME,
            "compressed_bytes": NAVIGATION_BYTES,
            "compressed_sha256": NAVIGATION_SHA256,
            "uncompressed_sha256": NAVIGATION_RAW_SHA256,
            "role": "TRANSIENT_BROADCAST_EPHEMERIS_MODEL_ONLY",
        },
        "transform": {
            "one_way_light_time": "ITERATED_RELATIVE_LIGHT_TIME",
            "earth_rotation_during_light_time": True,
            "ensemble_centering": "C=I-(1/6)11T",
            "prefix_nuisance": ["CONSTANT", "RATE"],
            "heldout_refit": False,
            "free_time_phase": False,
            "interpolation": False,
        },
        "decision": {
            "one_model_envelope_symbol": "B",
            "rule": "RETARDED_EXACT_CONTROLLING_SEPARATION_STRICTLY_GREATER_THAN_3B",
            "multiplier": DECISION_MULTIPLIER,
        },
        "observation_boundary": {
            "locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoders": 0,
            "scores": 0,
        },
        "next_if_admitted": "REVIEW_ONE_STRUCTURAL_ONLY_QUALIFICATION_CONTRACT",
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(manifest(root)).encode("ascii")).hexdigest()


def _navigation_candidate():
    matches = tuple(c for c in screen.NAVIGATION_CANDIDATES if c.doy == DOY)
    if len(matches) != 1 or matches[0].name != NAVIGATION_NAME:
        raise DraoLabelledEnvelopeError("NAVIGATION_CANDIDATE_CHANGED")
    return matches[0]


def parse_navigation(payload: bytes | bytearray):
    compressed = bytes(payload)
    if len(compressed) != NAVIGATION_BYTES:
        raise DraoLabelledEnvelopeError("NAVIGATION_COMPRESSED_BYTES_CHANGED")
    if sha256(compressed).hexdigest() != NAVIGATION_SHA256:
        raise DraoLabelledEnvelopeError("NAVIGATION_COMPRESSED_HASH_CHANGED")
    records, authority = screen.parse_navigation_gzip(_navigation_candidate(), compressed)
    if authority.get("uncompressed_sha256") != NAVIGATION_RAW_SHA256:
        raise DraoLabelledEnvelopeError("NAVIGATION_RAW_HASH_CHANGED")
    missing = tuple(sorted(set(CODEBOOK) - set(records)))
    if missing:
        raise DraoLabelledEnvelopeError(
            f"CODEBOOK_EPHEMERIS_MISSING:{','.join(missing)}"
        )
    return records, authority


def expected_utc_epochs() -> tuple[datetime, ...]:
    start = GPS_START - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    stop = GPS_STOP - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    epochs = tuple(
        start + timedelta(seconds=index * screen.STEP_S)
        for index in range(screen.RAW_EPOCHS)
    )
    if epochs[-1] != stop:
        raise DraoLabelledEnvelopeError("FROZEN_GRID_CHANGED")
    return epochs


def _station() -> geometry.Station:
    return geometry.Station(
        screen.STATION.station_id,
        screen.STATION.latitude_deg,
        screen.STATION.longitude_deg,
        screen.STATION.height_m,
        "UNKNOWN_NOT_USED_IN_MODEL_SIDE_AUDIT",
        "SEPT_POLARX5_5.2.0_METADATA_ONLY",
        "TWIVC6050_SCIS_METADATA_ONLY",
        "NOT_USED_BEFORE_OBSERVATION_QUALIFICATION",
        f"{screen.STATION.station_id}_{screen.STATION.domes}",
        screen.STATION.metadata_source,
    )


def _rotate_transmit_ecef_to_receive_ecef(
    satellite_ecef_m: np.ndarray, light_time_s: float
) -> np.ndarray:
    angle = geometry.EARTH_ROTATION_RAD_S * light_time_s
    cosine = np.cos(angle)
    sine = np.sin(angle)
    x, y, z = (float(value) for value in satellite_ecef_m)
    return np.asarray(
        [cosine * x + sine * y, -sine * x + cosine * y, z], dtype=np.float64
    )


def _retarded_state(
    records: Sequence[geometry.GpsEphemeris],
    receive_utc: datetime,
    station_ecef_m: np.ndarray,
) -> tuple[float, datetime, np.ndarray]:
    position = geometry.broadcast_ecef(
        geometry.select_ephemeris(records, receive_utc), receive_utc
    )
    light_time_s = float(np.linalg.norm(position - station_ecef_m))
    light_time_s /= geometry.SPEED_OF_LIGHT_M_S
    for _ in range(12):
        transmit = receive_utc - timedelta(seconds=light_time_s)
        transmit_position = geometry.broadcast_ecef(
            geometry.select_ephemeris(records, transmit), transmit
        )
        receive_frame_position = _rotate_transmit_ecef_to_receive_ecef(
            transmit_position, light_time_s
        )
        updated = float(np.linalg.norm(receive_frame_position - station_ecef_m))
        updated /= geometry.SPEED_OF_LIGHT_M_S
        if abs(updated - light_time_s) <= 1.0e-12:
            return (
                updated * geometry.SPEED_OF_LIGHT_M_S,
                receive_utc - timedelta(seconds=updated),
                receive_frame_position,
            )
        light_time_s = updated
    raise DraoLabelledEnvelopeError("RETARDED_LIGHT_TIME_DID_NOT_CONVERGE")


def _retarded_series(
    records: Sequence[geometry.GpsEphemeris],
    epochs: Sequence[datetime],
    station_ecef_m: np.ndarray,
    offset_s: float,
) -> tuple[np.ndarray, tuple[datetime, ...], np.ndarray]:
    ranges: list[float] = []
    transmit_epochs: list[datetime] = []
    positions: list[np.ndarray] = []
    for epoch in epochs:
        value, transmit, position = _retarded_state(
            records, epoch + timedelta(seconds=offset_s), station_ecef_m
        )
        ranges.append(value)
        transmit_epochs.append(transmit)
        positions.append(position)
    return (
        np.asarray(ranges, dtype=np.float64),
        tuple(transmit_epochs),
        np.stack(positions),
    )


def _center(values: np.ndarray) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    expected = (len(CODEBOOK), screen.RAW_EPOCHS)
    if matrix.shape != expected or not np.all(np.isfinite(matrix)):
        raise DraoLabelledEnvelopeError("SIX_TRACK_MATRIX_INVALID")
    return matrix - np.mean(matrix, axis=0, keepdims=True)


def _projected_metrics(matrix: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    residual, metrics = screen.prefix_project(matrix)
    by_track = [float(value) for value in metrics["heldout_peak_to_peak_m_by_track"]]
    if not by_track or any(not isfinite(value) for value in by_track):
        raise DraoLabelledEnvelopeError("PROJECTED_METRIC_INVALID")
    return residual, {
        "heldout_peak_to_peak_m_by_satellite": dict(zip(CODEBOOK, by_track)),
        "heldout_max_track_peak_to_peak_m": max(by_track),
        "heldout_rms_m": float(metrics["heldout_rms_m"]),
    }


def prefix_projection_operator() -> np.ndarray:
    identity = np.eye(screen.RAW_EPOCHS, dtype=np.float64)
    residual, _ = screen.prefix_project(identity)
    return residual


def transformed_box_peak_to_peak_bound(
    upper_by_track_epoch: np.ndarray,
    *,
    projection: np.ndarray | None = None,
) -> tuple[float, dict[str, float]]:
    """Propagate independent zero-to-upper boxes through centering/projection.

    Relaxing the physical slant terms to independent values at every epoch is
    conservative.  The returned bound is exact for that relaxed linear box.
    """

    upper = np.asarray(upper_by_track_epoch, dtype=np.float64)
    expected = (len(CODEBOOK), screen.RAW_EPOCHS)
    if upper.shape != expected or np.any(upper < 0.0) or not np.all(np.isfinite(upper)):
        raise DraoLabelledEnvelopeError("BOX_UPPER_INVALID")
    operator = prefix_projection_operator() if projection is None else np.asarray(projection)
    if operator.shape != (screen.RAW_EPOCHS, screen.RAW_EPOCHS):
        raise DraoLabelledEnvelopeError("PROJECTION_OPERATOR_INVALID")
    centering = np.eye(len(CODEBOOK)) - np.ones((len(CODEBOOK), len(CODEBOOK))) / len(CODEBOOK)
    heldout = range(screen.PREFIX_EPOCHS, screen.RAW_EPOCHS)
    result: dict[str, float] = {}
    for target_index, satellite in enumerate(CODEBOOK):
        maximum = 0.0
        weights = np.abs(centering[target_index])
        for left in heldout:
            for right in range(left + 1, screen.RAW_EPOCHS):
                temporal = np.abs(operator[:, left] - operator[:, right])
                bound = float(np.sum(weights[:, None] * upper * temporal[None, :]))
                maximum = max(maximum, bound)
        result[satellite] = maximum
    return max(result.values()), result


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
    mean_motion = sqrt(geometry.GPS_MU_M3_S2 / semi_major**3)
    mean_motion += record.delta_n_rad_s
    mean_anomaly = record.m0_rad + mean_motion * tk
    eccentric = mean_anomaly
    for _ in range(20):
        updated = mean_anomaly + record.eccentricity * sin(eccentric)
        if abs(updated - eccentric) < 1.0e-13:
            eccentric = updated
            break
        eccentric = updated
    relativistic_s = (
        -4.442807633e-10
        * record.eccentricity
        * record.sqrt_a_m_sqrt
        * sin(eccentric)
    )
    return record.af0_s + record.af1_s_s * dt + record.af2_s_s2 * dt * dt + relativistic_s


def _term(name: str, value_m: float, state: str, basis: str) -> dict[str, object]:
    if not isfinite(value_m) or value_m < 0.0:
        raise DraoLabelledEnvelopeError(f"TERM_BOUND_INVALID:{name}")
    return {
        "term": name,
        "state": state,
        "provenance": "INDEPENDENT_OF_FUTURE_TARGET_OBSERVATION",
        "heldout_max_track_peak_to_peak_bound_m": float(value_m),
        "basis": basis,
    }


def compile_envelope(payload: bytes | bytearray, root: Path) -> dict[str, object]:
    authority = validate_frozen_authority(Path(root))
    records, navigation_authority = parse_navigation(payload)
    epochs = expected_utc_epochs()
    station = _station()
    station_ecef = geometry.station_to_ecef(station)

    retarded: dict[float, np.ndarray] = {}
    transmit: dict[tuple[str, float], tuple[datetime, ...]] = {}
    positions: dict[tuple[str, float], np.ndarray] = {}
    for offset in (0.0, *TIMING_OFFSETS_S):
        rows = []
        for satellite in CODEBOOK:
            ranges, times, receive_frame = _retarded_series(
                records[satellite], epochs, station_ecef, offset
            )
            rows.append(ranges)
            transmit[(satellite, offset)] = times
            positions[(satellite, offset)] = receive_frame
        retarded[offset] = np.stack(rows)

    shifted = {
        (satellite, offset): retarded[offset][index]
        for offset in TIMING_OFFSETS_S
        for index, satellite in enumerate(CODEBOOK)
    }
    corrected_geometry = screen.evaluate_codebook(
        {
            satellite: retarded[0.0][index]
            for index, satellite in enumerate(CODEBOOK)
        },
        shifted,
    )
    timing_bound = float(corrected_geometry["direct_time_shift_envelope_m"])

    clock_paths = np.stack(
        [
            np.asarray(
                [
                    -geometry.SPEED_OF_LIGHT_M_S
                    * _clock_bias_s(
                        geometry.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in transmit[(satellite, 0.0)]
                ],
                dtype=np.float64,
            )
            for satellite in CODEBOOK
        ]
    )
    clock_residual, clock_metrics = _projected_metrics(_center(clock_paths))
    clock_bound = float(clock_metrics["heldout_max_track_peak_to_peak_m"])

    accuracy_by_satellite = {
        satellite: max(
            float(geometry.select_ephemeris(records[satellite], epoch).sv_accuracy_m)
            for epoch in epochs
        )
        for satellite in CODEBOOK
    }
    if any(not isfinite(value) or value < 0.0 for value in accuracy_by_satellite.values()):
        raise DraoLabelledEnvelopeError("BROADCAST_ACCURACY_UNAVAILABLE")
    broadcast_bound = 8.0 * max(accuracy_by_satellite.values())

    elevation_by_offset = {
        offset: np.stack(
            [
                geometry.elevation_deg(
                    positions[(satellite, offset)], station, station_ecef
                )
                for satellite in CODEBOOK
            ]
        )
        for offset in (0.0, *TIMING_OFFSETS_S)
    }
    robust_elevation = np.min(np.stack(tuple(elevation_by_offset.values())), axis=0)
    if np.any(robust_elevation <= 0.0) or not np.all(np.isfinite(robust_elevation)):
        raise DraoLabelledEnvelopeError("RETARDED_ELEVATION_INVALID")
    slant_upper = ZENITH_DELAY_MAX_M / np.sin(np.radians(robust_elevation))
    troposphere_bound, troposphere_by_satellite = transformed_box_peak_to_peak_bound(
        slant_upper
    )

    terms = [
        _term(
            "EVENT_TIME_DIRECT_RETARDED_TRAJECTORY_ENVELOPE",
            timing_bound,
            "MODELED_DIRECT_TRAJECTORY_ENVELOPE",
            "T_PLUS_MINUS_15_S_ON_EACH_RETARDED_TRAJECTORY_THEN_CENTER_AND_PREFIX_PROJECT",
        ),
        _term(
            "BROADCAST_ORBIT_USER_RANGE_ACCURACY_FAMILY",
            broadcast_bound,
            "MODELED_CONSERVATIVE_INTERVAL",
            "EIGHT_TIMES_MAXIMUM_SELECTED_EPHEMERIS_SV_ACCURACY_AS_FROZEN_DRAO_FAMILY",
        ),
        _term(
            "OMITTED_BROADCAST_SATELLITE_CLOCK_NONAFFINITY",
            clock_bound,
            "MODELED_FROM_BROADCAST_CLOCK_FIELDS",
            "AF0_AF1_AF2_AND_ECCENTRICITY_RELATIVITY_AT_ITERATED_TRANSMIT_TIME",
        ),
        _term(
            "DIFFERENTIAL_TROPOSPHERE_RELAXED_BOX",
            troposphere_bound,
            "MODELED_CONSERVATIVE_INTERVAL",
            "PER_EPOCH_ZERO_TO_3_5_M_OVER_SIN_ELEVATION_BOX_PROPAGATED_THROUGH_FULL_LINEAR_OPERATOR",
        ),
        _term(
            "STATION_DISPLACEMENT_EOP_AND_RELATIVITY",
            STATION_EOP_RELATIVITY_BOUND_M,
            "MODELED_CONSERVATIVE_INTERVAL",
            "FROZEN_DRAO_COMMON_MODE_HELDOUT_INTERVAL",
        ),
    ]
    model_side = sum(float(term["heldout_max_track_peak_to_peak_bound_m"]) for term in terms)
    one_model = model_side + CAPABILITY_CONDITIONAL_RESERVE_M
    required = DECISION_MULTIPLIER * one_model
    exact = float(corrected_geometry["exact_controlling_separation_m"])
    margin = exact - required
    outcome = OUTCOME_ADMITTED if margin > 0.0 else OUTCOME_DOMINATES

    result = {
        "schema": "gnss-drao-labelled-forward-physical-envelope-v1",
        "audit_version": AUDIT_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
        },
        "authority": authority,
        "manifest_sha256": manifest_sha256(root),
        "outcome": outcome,
        "navigation": navigation_authority,
        "geometry": {
            "station": screen.STATION.station_id,
            "doy": DOY,
            "codebook": list(CODEBOOK),
            "raw_start_gps": "2026-08-25T04:55:00 GPS",
            "raw_stop_gps": "2026-08-25T06:04:00 GPS",
            "heldout_start_gps": "2026-08-25T05:34:30 GPS",
            "screen_controlling_separation_m": EXPECTED_SCREEN_SEPARATION_M,
            "retarded_controlling_null": corrected_geometry["controlling_null"],
            "retarded_controlling_separation_m": exact,
            "retarded_prefix_affine_separation_m": corrected_geometry[
                "prefix_affine_null"
            ]["heldout_max_track_peak_to_peak_m"],
            "retarded_time_reversed_separation_m": corrected_geometry[
                "time_reversed_geometry_null"
            ]["heldout_max_track_peak_to_peak_m"],
            "minimum_retarded_nominal_elevation_deg": float(
                np.min(elevation_by_offset[0.0])
            ),
            "minimum_retarded_time_shifted_elevation_deg": float(
                np.min(robust_elevation)
            ),
        },
        "model_side_terms": terms,
        "event_time_metrics": corrected_geometry["direct_time_shift_rows"],
        "broadcast_sv_accuracy_m_by_satellite": accuracy_by_satellite,
        "satellite_clock_metrics": clock_metrics,
        "troposphere": {
            "zenith_delay_interval_m": [0.0, ZENITH_DELAY_MAX_M],
            "relaxation": "INDEPENDENT_PER_TRACK_PER_EPOCH_ZERO_TO_SLANT_UPPER",
            "heldout_box_bound_m_by_satellite": troposphere_by_satellite,
            "heldout_max_track_peak_to_peak_bound_m": troposphere_bound,
        },
        "capability_conditional_reserve": {
            "state": "NOT_YET_ADMITTED_PREDECLARED_RESERVE",
            "terms_m": {
                "HIGHER_ORDER_IONOSPHERE": HIGHER_ORDER_IONOSPHERE_RESERVE_M,
                "ANTENNA_PCV_AND_PHASE_WINDUP": ANTENNA_WINDUP_RESERVE_M,
                "MULTIPATH_SIGNAL_SPECIFIC_HARDWARE_AND_IMPLEMENTATION": COMPLETE_CODE_WITNESS_RESERVE_M,
                "RINEX_F14_3_CARRIER_PHASE_QUANTIZATION": RINEX_F14_3_QUANTIZATION_M,
            },
            "total_m": CAPABILITY_CONDITIONAL_RESERVE_M,
            "all_six_tracks_all_139_epochs_required": True,
            "core_fields": ["L1C", "L2W"],
            "same_path_code_witness": ["C1C", "C2W"],
            "optional_diagnostics": ["S1C", "S2W"],
            "lli_blank_or_zero_required": True,
            "geometry_free_second_difference_limit_m": GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
            "per_satellite_phase_minus_code_peak_to_peak_limit_m": CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M,
            "missing_epoch_bound": 0,
            "interpolation_or_gap_bridging": False,
            "failure_to_prove": "QUALIFICATION_NOT_ADMITTED",
        },
        "envelope": {
            "model_side_m": model_side,
            "capability_conditional_reserve_m": CAPABILITY_CONDITIONAL_RESERVE_M,
            "one_model_bound_b_m": one_model,
            "decision_multiplier": DECISION_MULTIPLIER,
            "required_separation_3b_m": required,
            "retarded_controlling_separation_m": exact,
            "remaining_physical_margin_m": margin,
            "conditional_on_later_measurement_clauses": True,
        },
        "common_mode": {
            "operator": "C=I-(1/6)11T",
            "epoch_common_receiver_clock_bound_m": 0.0,
            "track_or_signal_dependent_implementation_cancels": False,
        },
        "claim_boundary": {
            "maximum_future_positive_claim": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "receiver_labels_model_conditioned": True,
            "independent_identity_evidence": False,
            "g14_g17_temporal_not_satellite_family_independence": True,
        },
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
        "orbital_scores_produced": 0,
        "next_maximum": (
            "REVIEW_ONE_STRUCTURAL_ONLY_QUALIFICATION_CONTRACT"
            if outcome == OUTCOME_ADMITTED
            else "ABANDON_DRAO_DOY237_LABELLED_FORWARD_ROUTE"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_QUERY_SELECTION_OR_ACCESS",
        "new_gate_created": False,
    }
    strict_json(result)

    for value in retarded.values():
        value.fill(0.0)
    for value in positions.values():
        value.fill(0.0)
    for value in elevation_by_offset.values():
        value.fill(0.0)
    robust_elevation.fill(0.0)
    slant_upper.fill(0.0)
    clock_paths.fill(0.0)
    clock_residual.fill(0.0)
    return result


def render_report(value: Mapping[str, object]) -> str:
    geometry_value = value["geometry"]
    envelope = value["envelope"]
    rows = [
        "| Term | State | Held-out bound m |",
        "|---|---|---:|",
    ]
    rows.extend(
        f"| {term['term']} | {term['state']} | "
        f"{float(term['heldout_max_track_peak_to_peak_bound_m']):.9f} |"
        for term in value["model_side_terms"]
    )
    return "\n".join(
        [
            "# DRAO labelled-forward rank-1 physical envelope",
            "",
            "## Outcome",
            "",
            "```text",
            str(value["outcome"]),
            "```",
            "",
            "This audit regenerated only the exact-hash DOY237 broadcast model. "
            "No observation product was queried, selected or opened.",
            "",
            "## Corrected geometry",
            "",
            f"- fixed codebook: `{'/'.join(geometry_value['codebook'])}`;",
            f"- controlling null: `{geometry_value['retarded_controlling_null']}`;",
            f"- screened separation: `{float(geometry_value['screen_controlling_separation_m']):.9f} m`;",
            f"- retarded separation: `{float(geometry_value['retarded_controlling_separation_m']):.9f} m`;",
            f"- prefix-affine separation: `{float(geometry_value['retarded_prefix_affine_separation_m']):.9f} m`;",
            f"- time-reversed separation: `{float(geometry_value['retarded_time_reversed_separation_m']):.9f} m`;",
            f"- minimum nominal retarded elevation: `{float(geometry_value['minimum_retarded_nominal_elevation_deg']):.9f} deg`;",
            f"- minimum `t+/-15 s` retarded elevation: `{float(geometry_value['minimum_retarded_time_shifted_elevation_deg']):.9f} deg`.",
            "",
            "## Date-specific model-side bounds",
            "",
            *rows,
            "",
            "The troposphere term is deliberately stronger than a constant-delay "
            "approximation: every satellite and epoch is relaxed independently "
            "inside its 0--3.5 m zenith-mapped slant interval, then propagated "
            "through the exact centering and prefix projection.",
            "",
            "## Decision",
            "",
            f"- model-side total: `{float(envelope['model_side_m']):.9f} m`;",
            f"- conditional measurement reserve: `{float(envelope['capability_conditional_reserve_m']):.9f} m`;",
            f"- one-model bound `B`: `{float(envelope['one_model_bound_b_m']):.9f} m`;",
            f"- required `3B`: `{float(envelope['required_separation_3b_m']):.9f} m`;",
            f"- remaining physical margin: `{float(envelope['remaining_physical_margin_m']):.9f} m`.",
            "",
            "A positive margin is conditional, not a capability result. It is "
            "usable only if a later distinct structural qualification proves all "
            "six L1C/L2W tracks, zero/blank LLI, complete C1C/C2W witnesses, "
            "geometry-free continuity and exact timing/format coverage over all "
            "139 epochs. Extra tracks remain descriptive.",
            "",
            "## Claim boundary",
            "",
            "A later positive can reach only `ORBITAL_MODEL_PREDICTIVELY_PREFERRED` "
            "for receiver-labelled tracks. It cannot independently establish PRN "
            "identity. G14/G17 provide temporal, not satellite-family, independence.",
            "",
            "## Stop",
            "",
            "Observation locators, products, headers, payload bytes, values, "
            "decoders and scores: `0`. Stop before any DOY237 observation lookup.",
            "",
        ]
    )


def _write_once(path: Path, payload: bytes) -> None:
    if Path(path).exists():
        raise DraoLabelledEnvelopeError(f"OUTPUT_ALREADY_EXISTS:{Path(path).name}")
    Path(path).write_bytes(payload)


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation-gzip", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, default=root / RECEIPT_NAME)
    parser.add_argument("--report", type=Path, default=root / REPORT_NAME)
    args = parser.parse_args()
    if args.navigation_gzip.name != NAVIGATION_NAME:
        raise SystemExit("SUPPLY_EXACT_FROZEN_DOY237_NAVIGATION_PRODUCT")
    payload = bytearray(args.navigation_gzip.read_bytes())
    try:
        result = compile_envelope(payload, root)
    finally:
        payload[:] = b"\x00" * len(payload)
        payload.clear()
    _write_once(args.receipt, (strict_json(result, pretty=True) + "\n").encode("ascii"))
    _write_once(args.report, render_report(result).encode("ascii"))
    print(strict_json(result))


if __name__ == "__main__":
    main()
