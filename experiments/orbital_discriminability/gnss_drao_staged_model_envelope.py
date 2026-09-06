"""Compile the model-side DRAO envelope before observation-product selection."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite, radians, sin, sqrt
from pathlib import Path
import sys
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_all_track_geometry_screen as screen,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_drao_physical_envelope_audit as closed,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)


COMPILER_VERSION: Final = "drao-staged-model-side-envelope-v1"
OUTCOME_ADMITTED: Final = "DRAO_MODEL_SIDE_ENVELOPE_ADMITTED"
OUTCOME_BLOCKED: Final = "DRAO_MODEL_SIDE_ENVELOPE_DOMINATES"
RECEIPT_NAME: Final = "GNSS_DRAO_STAGED_MODEL_ENVELOPE.json"
REPORT_NAME: Final = "GNSS_DRAO_STAGED_MODEL_ENVELOPE.md"

SCOPE_NAME: Final = "GNSS_DRAO_STAGED_MODEL_SCOPE.md"
SCOPE_SHA256: Final = (
    "f74894c7e12e311565ec4a7eb021d352527b3bc07bfdbc1df3df90611a9604a9"
)
CLOSED_AUDIT_NAME: Final = closed.AUDIT_NAME
CLOSED_AUDIT_SHA256: Final = (
    "88b3871b2ba978359a640ce05d00f1a1fd0b3d0bceed4bbeb2686780f8b65d52"
)
GEOMETRY_NAME: Final = screen.RECEIPT_NAME
GEOMETRY_SHA256: Final = (
    "09456cae2dcb97550f44a16e45d8cb4b0b5d28a19e0a5b3ef25893c45710089c"
)

STATION_ID: Final = "DRAO00CAN"
STATION_LATITUDE_DEG: Final = 49.3226
STATION_LONGITUDE_DEG: Final = -119.625
STATION_HEIGHT_M: Final = 542.0
QUALIFICATION_DOY: Final = 232
PRIMARY_DOY: Final = 233
CODEBOOK: Final = ("G07", "G08", "G09", "G21", "G27", "G30")
GPS_START: Final = datetime(2026, 8, 21, 1, 14, 30, tzinfo=timezone.utc)
GPS_STOP: Final = datetime(2026, 8, 21, 2, 23, 30, tzinfo=timezone.utc)
STEP_S: Final = 30.0
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
TIMING_OFFSETS_S: Final = (-15.0, 15.0)
EXPECTED_EXACT_SEPARATION_M: Final = 49_091.54489091561
EXPECTED_MINIMUM_SHIFTED_ELEVATION_DEG: Final = 22.577489381782506

NAVIGATION_NAME: Final = "brdc2330.26n.gz"
NAVIGATION_BYTES: Final = 70_893
NAVIGATION_SHA256: Final = (
    "35e51e28aee55160723444c5f3a19a9f5048ca8c49e07fa90e2a16e832003bbf"
)
NAVIGATION_RAW_BYTES: Final = 294_845
NAVIGATION_RAW_SHA256: Final = (
    "f81333d83325df29e734936ea65474d64c4cc8d37049bf80d39e9ccf2dc241f8"
)

GUARD_M: Final = closed.GUARD_M
ZENITH_DELAY_MAX_M: Final = 3.5
STATION_EOP_RELATIVITY_COMMON_MODE_BOUND_M: Final = 4.0
CONDITIONAL_HIGHER_IONOSPHERE_M: Final = 2.0
CONDITIONAL_ANTENNA_WINDUP_M: Final = 4.0
CONDITIONAL_COMPLETE_CODE_WITNESS_M: Final = 2_500.0
CONDITIONAL_RINEX_QUANTIZATION_M: Final = 0.0017238368006440115
CONDITIONAL_RESERVE_M: Final = (
    CONDITIONAL_HIGHER_IONOSPHERE_M
    + CONDITIONAL_ANTENNA_WINDUP_M
    + CONDITIONAL_COMPLETE_CODE_WITNESS_M
    + CONDITIONAL_RINEX_QUANTIZATION_M
)


class DraoStagedEnvelopeError(ValueError):
    """A frozen scope, model input or numerical invariant changed."""


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


def _reject_nonfinite(token: str) -> object:
    raise DraoStagedEnvelopeError(f"NONFINITE_FROZEN_ARTIFACT:{token}")


def _load_exact(root: Path, name: str, digest: str) -> dict[str, object]:
    path = Path(root) / name
    if canonical_sha256(path) != digest:
        raise DraoStagedEnvelopeError(f"FROZEN_ARTIFACT_HASH_CHANGED:{name}")
    value = json.loads(path.read_text(encoding="ascii"), parse_constant=_reject_nonfinite)
    if not isinstance(value, dict):
        raise DraoStagedEnvelopeError(f"FROZEN_ARTIFACT_NOT_OBJECT:{name}")
    return value


def _validate_scope(root: Path) -> dict[str, object]:
    if canonical_sha256(Path(root) / SCOPE_NAME) != SCOPE_SHA256:
        raise DraoStagedEnvelopeError("FROZEN_SCOPE_CHANGED")
    prior = _load_exact(root, CLOSED_AUDIT_NAME, CLOSED_AUDIT_SHA256)
    geometry_receipt = _load_exact(root, GEOMETRY_NAME, GEOMETRY_SHA256)
    if prior.get("outcome") != closed.OUTCOME:
        raise DraoStagedEnvelopeError("CLOSED_DRAO_OUTCOME_CHANGED")
    if prior.get("route_state") != "CLOSED_BEFORE_DRAO_ARTIFACT_SELECTION":
        raise DraoStagedEnvelopeError("CLOSED_DRAO_ROUTE_CHANGED")
    if set(prior.get("artifact_access", {}).values()) != {0}:
        raise DraoStagedEnvelopeError("CLOSED_DRAO_ACCESS_CHANGED")
    if geometry_receipt.get("outcome") != screen.OUTCOME_SHORTLISTED:
        raise DraoStagedEnvelopeError("GEOMETRY_OUTCOME_CHANGED")
    return {
        "scope": {"name": SCOPE_NAME, "canonical_sha256": SCOPE_SHA256},
        "closed_audit": {
            "name": CLOSED_AUDIT_NAME,
            "canonical_sha256": CLOSED_AUDIT_SHA256,
            "outcome": prior["outcome"],
            "reopened": False,
        },
        "geometry": {
            "name": GEOMETRY_NAME,
            "canonical_sha256": GEOMETRY_SHA256,
        },
    }


def _navigation_candidate() -> navigation.NavigationCandidate:
    values = tuple(
        candidate
        for candidate in screen.NAVIGATION_CANDIDATES
        if candidate.doy == PRIMARY_DOY
    )
    if len(values) != 1 or values[0].name != NAVIGATION_NAME:
        raise DraoStagedEnvelopeError("NAVIGATION_CANDIDATE_CHANGED")
    return values[0]


def parse_navigation(payload: bytes) -> tuple[
    dict[str, tuple[geometry.GpsEphemeris, ...]], dict[str, object]
]:
    if len(payload) != NAVIGATION_BYTES or sha256(payload).hexdigest() != NAVIGATION_SHA256:
        raise DraoStagedEnvelopeError("NAVIGATION_COMPRESSED_IDENTITY_CHANGED")
    records, authority = navigation.parse_navigation_gzip(
        _navigation_candidate(), payload
    )
    if (
        authority.get("uncompressed_bytes") != NAVIGATION_RAW_BYTES
        or authority.get("uncompressed_sha256") != NAVIGATION_RAW_SHA256
    ):
        raise DraoStagedEnvelopeError("NAVIGATION_RAW_IDENTITY_CHANGED")
    missing = set(CODEBOOK) - set(records)
    if missing:
        raise DraoStagedEnvelopeError(
            f"CODEBOOK_EPHEMERIS_MISSING:{','.join(sorted(missing))}"
        )
    return records, authority


def expected_utc_epochs() -> tuple[datetime, ...]:
    gps_epochs = tuple(
        GPS_START + timedelta(seconds=index * STEP_S) for index in range(RAW_EPOCHS)
    )
    if gps_epochs[-1] != GPS_STOP:
        raise DraoStagedEnvelopeError("PRIMARY_GRID_CHANGED")
    return tuple(
        epoch - timedelta(seconds=geometry.GPS_UTC_OFFSET_S) for epoch in gps_epochs
    )


def _station() -> geometry.Station:
    return geometry.Station(
        STATION_ID,
        STATION_LATITUDE_DEG,
        STATION_LONGITUDE_DEG,
        STATION_HEIGHT_M,
        "UNKNOWN_NOT_REQUIRED_FOR_MODEL_SIDE_ENVELOPE",
        "SEPT_POLARX5_5.2.0_METADATA_ONLY",
        "TWIVC6050_SCIS_METADATA_ONLY",
        "NOT_USED",
        "DRAO00CAN_40105M002",
        "FROZEN_IGS_METADATA_SNAPSHOT_2026_08_25",
    )


def _positions(
    records: Mapping[str, Sequence[geometry.GpsEphemeris]],
    satellite: str,
    epochs: Sequence[datetime],
    offset_s: float,
) -> np.ndarray:
    shifted = tuple(epoch + timedelta(seconds=offset_s) for epoch in epochs)
    return np.asarray(
        [
            geometry.broadcast_ecef(
                geometry.select_ephemeris(records[satellite], epoch), epoch
            )
            for epoch in shifted
        ],
        dtype=np.float64,
    )


def _rotate_transmit_ecef_to_receive_ecef(
    satellite_ecef_m: np.ndarray, light_time_s: float
) -> np.ndarray:
    angle = geometry.EARTH_ROTATION_RAD_S * light_time_s
    cosine = np.cos(angle)
    sine = np.sin(angle)
    x, y, z = (float(value) for value in satellite_ecef_m)
    return np.asarray(
        [cosine * x + sine * y, -sine * x + cosine * y, z],
        dtype=np.float64,
    )


def _retarded_range_and_transmit_epoch(
    records: Sequence[geometry.GpsEphemeris],
    receive_utc: datetime,
    station_ecef_m: np.ndarray,
) -> tuple[float, datetime]:
    receive_position = geometry.broadcast_ecef(
        geometry.select_ephemeris(records, receive_utc), receive_utc
    )
    light_time_s = float(np.linalg.norm(receive_position - station_ecef_m))
    light_time_s /= geometry.SPEED_OF_LIGHT_M_S
    for _ in range(12):
        transmit_utc = receive_utc - timedelta(seconds=light_time_s)
        transmit_position = geometry.broadcast_ecef(
            geometry.select_ephemeris(records, transmit_utc), transmit_utc
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
            )
        light_time_s = updated
    raise DraoStagedEnvelopeError("RETARDED_RANGE_DID_NOT_CONVERGE")


def _retarded_range_series(
    records: Sequence[geometry.GpsEphemeris],
    receive_epochs: Sequence[datetime],
    station_ecef_m: np.ndarray,
    offset_s: float,
) -> tuple[np.ndarray, tuple[datetime, ...]]:
    ranges = []
    transmit_epochs = []
    for epoch in receive_epochs:
        value, transmit = _retarded_range_and_transmit_epoch(
            records,
            epoch + timedelta(seconds=offset_s),
            station_ecef_m,
        )
        ranges.append(value)
        transmit_epochs.append(transmit)
    return np.asarray(ranges, dtype=np.float64), tuple(transmit_epochs)


def _center(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    if values.shape != (6, RAW_EPOCHS) or not np.all(np.isfinite(values)):
        raise DraoStagedEnvelopeError("SIX_TRACK_MATRIX_INVALID")
    return values - np.mean(values, axis=0, keepdims=True)


def _prefix_residual(matrix: np.ndarray) -> tuple[np.ndarray, dict[str, object]]:
    return screen.prefix_project(matrix)


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
    return (
        record.af0_s
        + record.af1_s_s * dt
        + record.af2_s_s2 * dt * dt
        + relativistic_s
    )


def _serial_rows(matrix: np.ndarray) -> dict[str, list[float]]:
    return {
        satellite: [float(value) for value in matrix[index]]
        for index, satellite in enumerate(CODEBOOK)
    }


def _term(name: str, value_m: float, basis: str) -> dict[str, object]:
    if not isfinite(value_m) or value_m < 0.0:
        raise DraoStagedEnvelopeError(f"MODEL_TERM_INVALID:{name}")
    return {
        "term": name,
        "state": "MODELED_OUTCOME_INDEPENDENT",
        "common_mode_heldout_peak_to_peak_bound_m": float(value_m),
        "basis": basis,
    }


def compile_envelope(payload: bytes, root: Path) -> dict[str, object]:
    authority = _validate_scope(Path(root))
    records, navigation_authority = parse_navigation(payload)
    epochs = expected_utc_epochs()
    station = _station()
    station_ecef = geometry.station_to_ecef(station)

    position = {
        (satellite, offset): _positions(records, satellite, epochs, offset)
        for satellite in CODEBOOK
        for offset in (0.0, *TIMING_OFFSETS_S)
    }
    ranges = {
        offset: np.stack(
            [
                np.linalg.norm(position[(satellite, offset)] - station_ecef, axis=1)
                for satellite in CODEBOOK
            ]
        )
        for offset in (0.0, *TIMING_OFFSETS_S)
    }
    retarded_rows: dict[float, list[np.ndarray]] = {
        offset: [] for offset in (0.0, *TIMING_OFFSETS_S)
    }
    transmit_epochs: dict[tuple[str, float], tuple[datetime, ...]] = {}
    for offset in (0.0, *TIMING_OFFSETS_S):
        for satellite in CODEBOOK:
            row, transmit = _retarded_range_series(
                records[satellite], epochs, station_ecef, offset
            )
            retarded_rows[offset].append(row)
            transmit_epochs[(satellite, offset)] = transmit
    retarded_ranges = {
        offset: np.stack(rows) for offset, rows in retarded_rows.items()
    }
    nominal = ranges[0.0]
    regenerated = screen.evaluate_codebook(
        {satellite: nominal[index] for index, satellite in enumerate(CODEBOOK)}
    )
    exact = float(regenerated["exact_controlling_separation_m"])
    if abs(exact - EXPECTED_EXACT_SEPARATION_M) > 1.0e-6:
        raise DraoStagedEnvelopeError("DOY233_GEOMETRY_REGRESSION_CHANGED")

    corrected_geometry = retarded_ranges[0.0]
    corrected_evaluation = screen.evaluate_codebook(
        {
            satellite: corrected_geometry[index]
            for index, satellite in enumerate(CODEBOOK)
        }
    )
    timing_curves: dict[str, dict[str, list[float]]] = {}
    timing_metrics: list[dict[str, object]] = []
    centered_nominal = _center(corrected_geometry)
    for offset in TIMING_OFFSETS_S:
        error = _center(retarded_ranges[offset]) - centered_nominal
        residual, metrics = _prefix_residual(error)
        name = f"{offset:+.1f}s"
        timing_curves[name] = _serial_rows(residual)
        timing_metrics.append(
            {
                "offset_s": offset,
                "heldout_peak_to_peak_m_by_satellite": {
                    satellite: float(metrics["heldout_peak_to_peak_m_by_row"][index])
                    for index, satellite in enumerate(CODEBOOK)
                },
                "common_mode_bound_m": max(
                    float(value)
                    for value in metrics["heldout_peak_to_peak_m_by_row"]
                ),
            }
        )
    timing_bound = max(float(row["common_mode_bound_m"]) for row in timing_metrics)

    clock_paths = np.stack(
        [
            np.asarray(
                [
                    -geometry.SPEED_OF_LIGHT_M_S
                    * _clock_bias_s(
                        geometry.select_ephemeris(records[satellite], transmit),
                        transmit,
                    )
                    for transmit in transmit_epochs[(satellite, 0.0)]
                ],
                dtype=np.float64,
            )
            for satellite in CODEBOOK
        ]
    )
    clock_residual, clock_metrics = _prefix_residual(_center(clock_paths))
    clock_bound = max(
        float(value) for value in clock_metrics["heldout_peak_to_peak_m_by_row"]
    )
    propagation_correction, propagation_metrics = _prefix_residual(
        _center(corrected_geometry - nominal)
    )

    accuracy_by_satellite = {
        satellite: max(
            float(
                geometry.select_ephemeris(records[satellite], epoch).sv_accuracy_m
            )
            for epoch in epochs
        )
        for satellite in CODEBOOK
    }
    max_accuracy = max(accuracy_by_satellite.values())
    broadcast_accuracy_bound = 8.0 * max_accuracy

    elevation_by_model_offset = {
        f"{satellite}_{offset:+.1f}s": geometry.elevation_deg(
            position[(satellite, offset)], station, station_ecef
        )
        for satellite in CODEBOOK
        for offset in (0.0, *TIMING_OFFSETS_S)
    }
    minimum_elevation = min(
        float(np.min(values)) for values in elevation_by_model_offset.values()
    )
    if abs(minimum_elevation - EXPECTED_MINIMUM_SHIFTED_ELEVATION_DEG) > 1.0e-9:
        raise DraoStagedEnvelopeError("DOY233_VISIBILITY_REGRESSION_CHANGED")
    troposphere_bound = 2.0 * ZENITH_DELAY_MAX_M / sin(radians(minimum_elevation))

    model_terms = [
        _term(
            "EVENT_TIME_DIRECT_TRAJECTORY_ENVELOPE",
            timing_bound,
            "SIX_TRAJECTORIES_EVALUATED_AT_T_PLUS_MINUS_15_S_THEN_COMMON_MODE_AND_PREFIX_PROJECTION",
        ),
        _term(
            "BROADCAST_ORBIT_USER_RANGE_ACCURACY_FAMILY",
            broadcast_accuracy_bound,
            "EIGHT_TIMES_MAXIMUM_SELECTED_EPHEMERIS_SV_ACCURACY_UNDER_THE_FROZEN_COMMON_MODE_INTERVAL_RULE",
        ),
        _term(
            "OMITTED_BROADCAST_SATELLITE_CLOCK_NONAFFINITY",
            clock_bound,
            "AF0_AF1_AF2_RELATIVISTIC_AND_TGD_CLOCK_PATH_COMMON_MODE_THEN_PREFIX_PROJECTION",
        ),
        _term(
            "DIFFERENTIAL_TROPOSPHERE",
            troposphere_bound,
            "ZERO_TO_3_5_M_ZENITH_INTERVAL_ONE_OVER_SINE_AT_FROZEN_MINIMUM_SHIFTED_ELEVATION",
        ),
        _term(
            "STATION_DISPLACEMENT_EOP_AND_RELATIVITY",
            STATION_EOP_RELATIVITY_COMMON_MODE_BOUND_M,
            "FROZEN_OUTCOME_INDEPENDENT_COMMON_MODE_INTERVAL",
        ),
    ]
    model_side = sum(
        float(row["common_mode_heldout_peak_to_peak_bound_m"])
        for row in model_terms
    )
    total = model_side + CONDITIONAL_RESERVE_M
    remaining = GUARD_M - total
    outcome = OUTCOME_ADMITTED if remaining > 0.0 else OUTCOME_BLOCKED

    serial_nominal = _serial_rows(nominal)
    serial_corrected = _serial_rows(corrected_geometry)
    serial_propagation = _serial_rows(propagation_correction)
    serial_clock = _serial_rows(clock_residual)
    retained_curves = {
        "screen_receive_epoch_range_m_by_satellite": serial_nominal,
        "retarded_earth_rotation_corrected_range_m_by_satellite": (
            serial_corrected
        ),
        "projected_retarded_geometry_correction_m_by_satellite": (
            serial_propagation
        ),
        "projected_timing_error_m_by_offset_and_satellite": timing_curves,
        "projected_omitted_clock_path_m_by_satellite": serial_clock,
    }
    result = {
        "schema": "gnss-drao-staged-model-side-envelope-v1",
        "version": COMPILER_VERSION,
        "outcome": outcome,
        "physical_question": (
            "DOES_THE_DOY233_MODEL_SIDE_COMMON_MODE_ENVELOPE_LEAVE_ROOM_FOR_"
            "A_COMPLETE_ALL_EPOCH_MEASUREMENT_WITNESS"
        ),
        "new_information": (
            "EXACT_DRAO_TIMING_AND_OMITTED_CLOCK_NONAFFINITY_ON_THE_UNUSED_"
            "DOY233_HELDOUT_GEOMETRY"
        ),
        "authority": authority,
        "navigation": navigation_authority,
        "roles": {
            "closed": {"qualification_doy": 230, "primary_doy": 231},
            "qualification_candidate": {
                "doy": QUALIFICATION_DOY,
                "artifact_locator": None,
            },
            "possible_primary": {
                "doy": PRIMARY_DOY,
                "artifact_locator": None,
                "frozen": False,
            },
        },
        "geometry": {
            "station": STATION_ID,
            "codebook": list(CODEBOOK),
            "gps_start": geometry.format_gps(epochs[0]),
            "gps_stop": geometry.format_gps(epochs[-1]),
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": RAW_EPOCHS - PREFIX_EPOCHS,
            "screen_exact_controlling_separation_m": exact,
            "retarded_geometry_exact_controlling_separation_m": float(
                corrected_evaluation["exact_controlling_separation_m"]
            ),
            "minimum_direct_time_shifted_elevation_deg": minimum_elevation,
            "screen_regenerated_result": regenerated,
            "retarded_geometry_result": corrected_evaluation,
            "one_way_light_time": (
                "ITERATED_RELATIVE_LIGHT_TIME_WITH_EARTH_ROTATION_DURING_TRANSIT"
            ),
        },
        "common_mode": {
            "operator": "C=I-(1/6)11T",
            "epoch_common_receiver_clock_bound_m": 0.0,
            "track_dependent_implementation_assumed_common": False,
        },
        "model_side_terms": model_terms,
        "timing_metrics": timing_metrics,
        "broadcast_sv_accuracy_m_by_satellite": accuracy_by_satellite,
        "clock_heldout_peak_to_peak_m_by_satellite": {
            satellite: float(clock_metrics["heldout_peak_to_peak_m_by_row"][index])
            for index, satellite in enumerate(CODEBOOK)
        },
        "retarded_geometry_correction_heldout_peak_to_peak_m_by_satellite": {
            satellite: float(
                propagation_metrics["heldout_peak_to_peak_m_by_row"][index]
            )
            for index, satellite in enumerate(CODEBOOK)
        },
        "satellite_clock_transform": {
            "fields": ["AF0", "AF1", "AF2", "RELATIVISTIC_ECCENTRICITY_TERM"],
            "evaluated_at": "ITERATED_TRANSMIT_EPOCH",
            "tgd_included": False,
            "reason_tgd_excluded": "GROUP_DELAY_NOT_CARRIER_PHASE_CLOCK_TERM",
            "used_as_assignment_feature": False,
            "treated_as_omitted_nonaffine_envelope": True,
        },
        "capability_conditional_reserve": {
            "state": "NOT_YET_ADMITTED_RESERVED_BEFORE_QUALIFICATION",
            "complete_same_path_code_witness_required": True,
            "minimum_coverage_fraction_per_track": 1.0,
            "missing_epoch_bound": 0,
            "terms_m": {
                "HIGHER_ORDER_IONOSPHERE": CONDITIONAL_HIGHER_IONOSPHERE_M,
                "ANTENNA_PCV_AND_PHASE_WINDUP": CONDITIONAL_ANTENNA_WINDUP_M,
                "MULTIPATH_SIGNAL_AND_IMPLEMENTATION": (
                    CONDITIONAL_COMPLETE_CODE_WITNESS_M
                ),
                "RINEX_F14_3_QUANTIZATION": CONDITIONAL_RINEX_QUANTIZATION_M,
            },
            "total_m": CONDITIONAL_RESERVE_M,
            "qualification_may_change_reserved_numbers": False,
            "failure_to_prove_conditions": "QUALIFICATION_NOT_ADMITTED",
        },
        "envelope": {
            "model_side_m": model_side,
            "conditional_capability_reserve_m": CONDITIONAL_RESERVE_M,
            "combined_if_capability_conditions_pass_m": total,
            "guard_m": GUARD_M,
            "remaining_margin_m": remaining,
            "model_side_admitted_for_qualification_review": remaining > 0.0,
        },
        "retained_model_curves": retained_curves,
        "retained_model_curves_sha256": sha256(
            strict_json(retained_curves).encode("ascii")
        ).hexdigest(),
        "navigation_payloads_retained": 0,
        "observation_access": {
            "qualification_locators": 0,
            "qualification_headers": 0,
            "qualification_payload_bytes": 0,
            "primary_locators": 0,
            "primary_headers": 0,
            "primary_payload_bytes": 0,
            "observation_values": 0,
        },
        "orbital_scores_produced": 0,
        "prospective_primary_plan_frozen": False,
        "next_maximum": (
            "REVIEW_ONE_DOY232_QUALIFICATION_CONTRACT"
            if outcome == OUTCOME_ADMITTED
            else "STOP_DRAO_STAGED_ROUTE_BEFORE_OBSERVATION"
        ),
        "new_gate": False,
    }
    strict_json(result)
    for values in position.values():
        values.fill(0.0)
    for values in ranges.values():
        values.fill(0.0)
    for values in retarded_ranges.values():
        values.fill(0.0)
    nominal.fill(0.0)
    centered_nominal.fill(0.0)
    clock_paths.fill(0.0)
    clock_residual.fill(0.0)
    propagation_correction.fill(0.0)
    return result


def render_report(value: Mapping[str, object]) -> str:
    envelope = value["envelope"]
    rows = [
        (
            f"| {term['term']} | "
            f"{float(term['common_mode_heldout_peak_to_peak_bound_m']):.9f} m |"
        )
        for term in value["model_side_terms"]
    ]
    return "\n".join(
        [
            "# DRAO staged model-side envelope",
            "",
            f"**{value['outcome']}**",
            "",
            "This compiler used only the exact-hash DOY233 broadcast-navigation model and committed model/proof artifacts. No DRAO observation product was selected or accessed.",
            "",
            "## Model-side terms",
            "",
            "| Term | common-mode held-out p-p bound |",
            "|---|---:|",
            *rows,
            "",
            f"Model-side total: `{float(envelope['model_side_m']):.9f} m`.",
            f"Predeclared complete-witness reserve: `{float(envelope['conditional_capability_reserve_m']):.9f} m`.",
            f"Combined conditional envelope: `{float(envelope['combined_if_capability_conditions_pass_m']):.9f} m` against `{float(envelope['guard_m']):.9f} m`.",
            f"Remaining margin: `{float(envelope['remaining_margin_m']):.9f} m`.",
            "",
            "The reserve is not a measured capability. It becomes active only if a distinct DOY232 qualification proves the exact signal/scale format and a future primary requires C1C/C2W at every core-phase epoch. No missing witness epoch may be bridged.",
            "",
            "The closed DOY230/DOY231 route remains immutable. A positive result authorizes only review of one qualification contract; it does not freeze or authorize a DOY233 primary.",
            "",
            "Observation locators, headers, payload bytes, values and orbital scores: **0**.",
            "",
        ]
    )


def write_artifacts(payload: bytes, root: Path) -> tuple[Path, Path]:
    root = Path(root)
    value = compile_envelope(payload, root)
    receipt = root / RECEIPT_NAME
    report = root / REPORT_NAME
    receipt.write_text(
        strict_json(value, pretty=True) + "\n", encoding="utf-8", newline="\n"
    )
    report.write_text(render_report(value), encoding="utf-8", newline="\n")
    return receipt, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--navigation-gzip", type=Path)
    source.add_argument("--navigation-gzip-stdin", action="store_true")
    args = parser.parse_args()
    payload = (
        sys.stdin.buffer.read()
        if args.navigation_gzip_stdin
        else args.navigation_gzip.read_bytes()
    )
    try:
        write_artifacts(payload, Path(__file__).resolve().parent)
    finally:
        payload = b""
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
