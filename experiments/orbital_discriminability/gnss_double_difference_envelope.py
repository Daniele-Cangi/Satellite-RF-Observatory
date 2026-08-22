"""Physical-envelope compiler for the frozen GOLD/NLIB GNSS shortlist.

The compiler accepts only broadcast navigation and amplitude-blind header
receipts.  It never accepts carrier phase, code, SNR or LLI values.  Every
numeric nuisance is projected through the same calibration-prefix affine
operator as the orbital and wrong-orbit alternatives.
"""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from math import ceil, sin
from pathlib import Path
from typing import Final

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_observation_header as headers


COMPILER_VERSION: Final = "gnss-double-difference-physical-envelope-v1"
GPS_L1_HZ: Final = 1_575_420_000.0
GPS_L2_HZ: Final = 1_227_600_000.0
RINEX_PHASE_QUANTIZATION_CYCLES: Final = 0.001
MAX_STATION_EPOCH_ERROR_S: Final = 15.0
MAX_ZENITH_TROPOSPHERE_M: Final = 3.5
PAIRWISE_ENVELOPE_MULTIPLIER: Final = 2.0
OUTCOME_ADMITTED: Final = "GNSS_DIFFERENTIAL_PHYSICAL_MARGIN_ADMITTED"
OUTCOME_BLOCKED: Final = "GNSS_DIFFERENTIAL_PHYSICAL_MARGIN_BLOCKED"


GENERIC_PATH_BOUNDS_M: Final = (
    {
        "term": "BROADCAST_ORBIT_SV_ACCURACY",
        "per_link_path_bound_m": 4.0,
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "basis": "TWO_TIMES_THE_2_M_MAXIMUM_SV_ACCURACY_IN_FROZEN_NAVIGATION",
    },
    {
        "term": "HIGHER_ORDER_IONOSPHERE",
        "per_link_path_bound_m": 0.5,
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "basis": "CONSERVATIVE_IERS_CHAPTER_9_HIGHER_ORDER_PATH_INTERVAL",
    },
    {
        "term": "ANTENNA_PCV_AND_PHASE_WINDUP",
        "per_link_path_bound_m": 1.0,
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "basis": "CONSERVATIVE_BOUND_WITH_IGS_ROBOT_CALIBRATED_RECEIVER_ANTENNAS",
    },
    {
        "term": "MULTIPATH_AND_SIGNAL_SPECIFIC_HARDWARE",
        "per_link_path_bound_m": 1.0,
        "state": "CALIBRATION_ADMISSION_LIMIT",
        "provenance": "LEARNABLE_ON_CALIBRATION_PREFIX_ONLY",
        "basis": "FIXED_REJECTION_LIMIT_NOT_A_POSTERIOR_ERROR_ESTIMATE",
    },
    {
        "term": "STATION_DISPLACEMENT_EOP_AND_RELATIVITY",
        "per_link_path_bound_m": 1.0,
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "basis": "CONSERVATIVE_COMBINED_UNMODELED_PATH_INTERVAL",
    },
    {
        "term": "SATELLITE_CLOCK_RETARDED_TIME_REMAINDER",
        "per_link_path_bound_m": 1.0,
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "basis": "CONSERVATIVE_REMAINDER_AFTER_SAME_SATELLITE_STATION_DIFFERENCE",
    },
)


class EnvelopeError(ValueError):
    """The frozen header topology or physical envelope is inadmissible."""


def compile_envelope(
    navigation: Path,
    left_header: dict[str, object],
    right_header: dict[str, object],
) -> dict[str, object]:
    pair = headers.admit_pair(left_header, right_header)
    if pair["state"] != "PAIR_HEADER_ADMITTED":
        raise EnvelopeError("PAIR_HEADER_NOT_ADMITTED")
    if any(value != 0 for value in left_header["observation_access"].values()):
        raise EnvelopeError("LEFT_OBSERVATION_VALUES_ALREADY_ACCESSED")
    if any(value != 0 for value in right_header["observation_access"].values()):
        raise EnvelopeError("RIGHT_OBSERVATION_VALUES_ALREADY_ACCESSED")

    geometry = screen.screen_navigation(navigation)
    records = screen.parse_gps_navigation(navigation)
    epochs = screen.utc_grid(
        screen.WINDOW_START_UTC,
        screen.WINDOW_STOP_UTC,
        screen.GRID_STEP_S,
    )
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    station_ecef = {
        station.station_id: screen.station_to_ecef(station) for station in screen.STATIONS
    }
    satellites = tuple(sorted(records))
    position_cache: dict[tuple[str, float], np.ndarray] = {}

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, offset_s
        if key not in position_cache:
            shifted = tuple(epoch + timedelta(seconds=offset_s) for epoch in epochs)
            position_cache[key] = np.asarray(
                [
                    screen.broadcast_ecef(
                        screen.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in shifted
                ]
            )
        return position_cache[key]

    compiled = []
    for candidate in geometry["shortlist"]:
        compiled.append(
            compile_candidate(
                candidate,
                records,
                epochs,
                epoch_index,
                satellites,
                station_ecef,
                positions,
            )
        )
    compiled.sort(
        key=lambda row: (
            -row["remaining_physical_margin_hz"],
            row["start_utc"],
            row["target"],
            row["reference"],
        )
    )
    for rank, row in enumerate(compiled, start=1):
        row["physical_margin_rank"] = rank

    selected = compiled[0] if compiled and compiled[0]["remaining_physical_margin_hz"] > 0 else None
    outcome = OUTCOME_ADMITTED if selected is not None else OUTCOME_BLOCKED
    result = {
        "compiler_version": COMPILER_VERSION,
        "compiler_manifest_sha256": compiler_manifest_sha256(),
        "screen_manifest_sha256": geometry["screen_manifest_sha256"],
        "header_pair_state": pair,
        "physical_coordinate": physical_coordinate(),
        "envelope_policy": envelope_policy(),
        "candidate_envelopes": compiled,
        "selected_candidate": selected,
        "measurement_access": {
            "epoch_records_decoded": 0,
            "observation_fields_decoded": 0,
            "carrier_phase_values": 0,
            "code_values": 0,
            "snr_values": 0,
            "lli_values": 0,
        },
        "outcome": outcome,
        "prospective_plan_frozen": False,
        "measurement_authorized": False,
    }
    strict_json(result)
    return result


def compile_candidate(
    candidate,
    records,
    epochs,
    epoch_index,
    satellites,
    station_ecef,
    positions,
):
    target = candidate["target"]
    reference = candidate["reference"]
    start = epoch_index[screen.parse_utc(candidate["start_utc"])]
    stop = epoch_index[screen.parse_utc(candidate["stop_utc"])] + 1
    feature = slice(start + 1, stop - 1)
    feature_epochs = epochs[feature]
    count = len(feature_epochs)
    split = max(3, int(ceil(count * screen.CALIBRATION_FRACTION)))
    left, right = (station.station_id for station in screen.STATIONS)

    fractional = {}
    elevation = {}
    for satellite in satellites:
        for station in screen.STATIONS:
            station_id = station.station_id
            fractional[(station_id, satellite)] = screen.fractional_doppler(
                positions(satellite), station_ecef[station_id], screen.GRID_STEP_S
            )
            elevation[(station_id, satellite)] = screen.elevation_deg(
                positions(satellite), station, station_ecef[station_id]
            )

    nominal = screen.double_difference_hz(
        fractional[(left, target)],
        fractional[(left, reference)],
        fractional[(right, target)],
        fractional[(right, reference)],
    )[feature]
    affine = screen.prefix_affine_metrics(nominal, split, screen.GRID_STEP_S)
    wrong = wrong_orbit_metrics(
        target,
        reference,
        feature,
        split,
        satellites,
        fractional,
        elevation,
        left,
        right,
    )
    controlling = min(
        affine["heldout_peak_to_peak_hz"], wrong["minimum_heldout_peak_to_peak_hz"]
    )

    projection_gain = affine_projection_peak_to_peak_gain(count, split, screen.GRID_STEP_S)
    terms = [
        timing_term(
            target,
            reference,
            feature,
            split,
            records,
            epochs,
            station_ecef,
        ),
        troposphere_term(
            target,
            reference,
            feature,
            split,
            elevation,
            left,
            right,
        ),
        quantization_term(projection_gain),
    ]
    for definition in GENERIC_PATH_BOUNDS_M:
        terms.append(generic_path_term(definition, projection_gain))
    combined = float(sum(term["heldout_peak_to_peak_bound_hz"] for term in terms))
    pairwise = PAIRWISE_ENVELOPE_MULTIPLIER * combined
    remaining = float(controlling - pairwise)
    return {
        "target": target,
        "reference": reference,
        "start_utc": screen.format_utc(feature_epochs[0]),
        "stop_utc": screen.format_utc(feature_epochs[-1]),
        "start_observation_epoch_gps": screen.format_gps(feature_epochs[0]),
        "stop_observation_epoch_gps": screen.format_gps(feature_epochs[-1]),
        "feature_records": count,
        "calibration_records": split,
        "heldout_records": count - split,
        "prefix_affine_null": affine,
        "wrong_orbit_family": wrong,
        "controlling_heldout_separation_hz": float(controlling),
        "affine_projection_peak_to_peak_gain": projection_gain,
        "physical_terms": terms,
        "one_model_physical_envelope_hz": combined,
        "pairwise_comparison_envelope_hz": pairwise,
        "remaining_physical_margin_hz": remaining,
        "maximum_additional_unmodeled_peak_to_peak_hz": max(0.0, remaining),
        "negative_result_interpretable_if_measurement_admitted": remaining > 0,
    }


def wrong_orbit_metrics(
    target,
    reference,
    feature,
    split,
    satellites,
    fractional,
    elevation,
    left,
    right,
):
    target_curve = screen.double_difference_hz(
        fractional[(left, target)],
        fractional[(left, reference)],
        fractional[(right, target)],
        fractional[(right, reference)],
    )[feature]
    alternatives = []
    for alternative in satellites:
        if alternative in (target, reference):
            continue
        if not (
            np.all(elevation[(left, alternative)][feature] >= screen.MINIMUM_ELEVATION_DEG)
            and np.all(
                elevation[(right, alternative)][feature] >= screen.MINIMUM_ELEVATION_DEG
            )
        ):
            continue
        alternative_curve = screen.double_difference_hz(
            fractional[(left, alternative)],
            fractional[(left, reference)],
            fractional[(right, alternative)],
            fractional[(right, reference)],
        )[feature]
        metric = screen.prefix_affine_metrics(
            target_curve - alternative_curve, split, screen.GRID_STEP_S
        )
        alternatives.append(
            {
                "satellite": alternative,
                "heldout_peak_to_peak_hz": metric["heldout_peak_to_peak_hz"],
            }
        )
    alternatives.sort(key=lambda row: (row["heldout_peak_to_peak_hz"], row["satellite"]))
    if not alternatives:
        return {
            "minimum_heldout_peak_to_peak_hz": 0.0,
            "controlling_alternative": None,
            "alternatives": [],
        }
    return {
        "minimum_heldout_peak_to_peak_hz": alternatives[0]["heldout_peak_to_peak_hz"],
        "controlling_alternative": alternatives[0]["satellite"],
        "alternatives": alternatives,
    }


def timing_term(
    target,
    reference,
    feature,
    split,
    records,
    epochs,
    station_ecef,
):
    left, right = (station.station_id for station in screen.STATIONS)

    def station_fractional(station_id, satellite, offset_s):
        shifted = tuple(epoch + timedelta(seconds=offset_s) for epoch in epochs)
        shifted_position = np.asarray(
            [
                screen.broadcast_ecef(
                    screen.select_ephemeris(records[satellite], epoch), epoch
                )
                for epoch in shifted
            ]
        )
        return screen.fractional_doppler(
            shifted_position, station_ecef[station_id], screen.GRID_STEP_S
        )

    nominal = screen.double_difference_hz(
        station_fractional(left, target, 0.0),
        station_fractional(left, reference, 0.0),
        station_fractional(right, target, 0.0),
        station_fractional(right, reference, 0.0),
    )[feature]
    maximum = 0.0
    controlling = None
    for left_offset in (-MAX_STATION_EPOCH_ERROR_S, MAX_STATION_EPOCH_ERROR_S):
        for right_offset in (-MAX_STATION_EPOCH_ERROR_S, MAX_STATION_EPOCH_ERROR_S):
            shifted = screen.double_difference_hz(
                station_fractional(left, target, left_offset),
                station_fractional(left, reference, left_offset),
                station_fractional(right, target, right_offset),
                station_fractional(right, reference, right_offset),
            )[feature]
            metric = screen.prefix_affine_metrics(
                shifted - nominal, split, screen.GRID_STEP_S
            )["heldout_peak_to_peak_hz"]
            if metric > maximum:
                maximum = float(metric)
                controlling = [left_offset, right_offset]
    return {
        "term": "STATION_EVENT_TIME",
        "state": "MODELED_DIRECT_TRAJECTORY_ENVELOPE",
        "provenance": "STRUCTURAL_HALF_CADENCE_BOUND",
        "parameter_interval_s": [-MAX_STATION_EPOCH_ERROR_S, MAX_STATION_EPOCH_ERROR_S],
        "controlling_station_offsets_s": controlling,
        "heldout_peak_to_peak_bound_hz": maximum,
        "basis": "DIRECT_T_PLUS_OR_MINUS_DELTA_T_PROPAGATION_NOT_LOCAL_SLOPE",
    }


def troposphere_term(target, reference, feature, split, elevation, left, right):
    def mapping(station_id, satellite):
        radians = np.radians(elevation[(station_id, satellite)])
        return 1.0 / np.maximum(np.sin(radians), sin(np.radians(15.0)))

    left_shape = mapping(left, target) - mapping(left, reference)
    right_shape = mapping(right, target) - mapping(right, reference)
    maximum = 0.0
    controlling = None
    for left_ztd in (0.0, MAX_ZENITH_TROPOSPHERE_M):
        for right_ztd in (0.0, MAX_ZENITH_TROPOSPHERE_M):
            path = left_ztd * left_shape - right_ztd * right_shape
            frequency = (
                -GPS_L1_HZ
                / screen.SPEED_OF_LIGHT_M_S
                * np.gradient(path, screen.GRID_STEP_S, edge_order=2)
            )[feature]
            metric = screen.prefix_affine_metrics(
                frequency, split, screen.GRID_STEP_S
            )["heldout_peak_to_peak_hz"]
            if metric > maximum:
                maximum = float(metric)
                controlling = [left_ztd, right_ztd]
    return {
        "term": "DIFFERENTIAL_TROPOSPHERE",
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "zenith_delay_interval_m": [0.0, MAX_ZENITH_TROPOSPHERE_M],
        "controlling_station_zenith_delays_m": controlling,
        "heldout_peak_to_peak_bound_hz": maximum,
        "basis": "IERS_RADIO_DELAY_WITH_CONSERVATIVE_ONE_OVER_SINE_MAPPING",
        "source": "https://iers-conventions.obspm.fr/content/chapter9/icc9.pdf",
    }


def quantization_term(projection_gain: float):
    alpha, beta = ionosphere_free_coefficients()
    per_link = 0.5 * RINEX_PHASE_QUANTIZATION_CYCLES * (
        abs(alpha) * screen.SPEED_OF_LIGHT_M_S / GPS_L1_HZ
        + abs(beta) * screen.SPEED_OF_LIGHT_M_S / GPS_L2_HZ
    )
    raw = generic_path_frequency_bound(per_link)
    return {
        "term": "RINEX_CARRIER_PHASE_QUANTIZATION",
        "state": "KNOWN_FORMAT_BOUND",
        "provenance": "INDEPENDENT_OF_TARGET_OBSERVATION",
        "per_link_path_bound_m": per_link,
        "raw_frequency_bound_hz": raw,
        "heldout_peak_to_peak_bound_hz": raw * projection_gain,
        "basis": "HALF_OF_RINEX_F14_3_CYCLE_QUANTIZATION_AFTER_IONOSPHERE_FREE_COMBINATION",
    }


def generic_path_term(definition: dict[str, object], projection_gain: float):
    raw = generic_path_frequency_bound(definition["per_link_path_bound_m"])
    return {
        **definition,
        "raw_frequency_bound_hz": raw,
        "affine_projection_gain": projection_gain,
        "heldout_peak_to_peak_bound_hz": raw * projection_gain,
    }


def generic_path_frequency_bound(per_link_path_m: float) -> float:
    return float(
        8.0
        * per_link_path_m
        / screen.GRID_STEP_S
        * GPS_L1_HZ
        / screen.SPEED_OF_LIGHT_M_S
    )


def affine_projection_peak_to_peak_gain(count: int, split: int, step_s: float) -> float:
    elapsed = np.arange(count, dtype=np.float64) * step_s
    calibration = np.column_stack((np.ones(split), elapsed[:split]))
    heldout = np.column_stack((np.ones(count - split), elapsed[split:]))
    fit_weights = heldout @ np.linalg.pinv(calibration)
    row_l1 = 1.0 + np.sum(np.abs(fit_weights), axis=1)
    return float(2.0 * np.max(row_l1))


def ionosphere_free_coefficients() -> tuple[float, float]:
    denominator = GPS_L1_HZ**2 - GPS_L2_HZ**2
    return GPS_L1_HZ**2 / denominator, -(GPS_L2_HZ**2 / denominator)


def physical_coordinate() -> dict[str, object]:
    alpha, beta = ionosphere_free_coefficients()
    return {
        "signals": {"l1": "L1C", "l2": "L2W"},
        "same_path_witnesses": ["C1C", "C2W", "S1C", "S2W", "LLI_ON_L1C", "LLI_ON_L2W"],
        "ionosphere_free_range_m": f"{alpha:.17g}*L1C_METERS+({beta:.17g})*L2W_METERS",
        "station_satellite_order": "(GOLD_TARGET-GOLD_REFERENCE)-(NLIB_TARGET-NLIB_REFERENCE)",
        "frequency_coordinate": "-GPS_L1_HZ_OVER_C_TIMES_CENTRAL_TIME_DERIVATIVE",
        "derivative": "CENTRAL_TWO_EPOCH_60S_BASELINE_DROP_FIRST_AND_LAST_PER_CONTINUOUS_SEGMENT",
        "gap_rule": "NEVER_DIFFERENCE_ACROSS_A_MISSING_OR_NON_30S_EPOCH",
        "cycle_slip_rule": "ANY_LLI_OR_GEOMETRY_FREE_SLIP_IN_EIGHT_USED_PHASE_STREAMS_REFUSES_THE_SEGMENT",
        "snr_rule": "PRESENCE_CONTINUITY_ONLY_BECAUSE_GOLD_DOES_NOT_DECLARE_DBHZ_UNIT",
    }


def envelope_policy() -> dict[str, object]:
    return {
        "combination": "LINEAR_SUM_NOT_ROOT_SUM_SQUARE",
        "unresolved_as_zero": False,
        "calibration_prefix_fraction": screen.CALIBRATION_FRACTION,
        "nulls": ["PREFIX_AFFINE", "OTHER_JOINTLY_VISIBLE_GPS_BROADCAST_ORBITS"],
        "all_nulls_receive_same_coordinate_timing_and_physical_envelopes": True,
        "outcome_conditioned_products_may_reduce_envelope": False,
        "measurement_health_terms": {
            "cycle_slip": "OBSERVABLE_REQUIRED",
            "gap_continuity": "OBSERVABLE_REQUIRED",
            "same_path_code_and_snr_presence": "OBSERVABLE_REQUIRED",
        },
    }


def compiler_manifest() -> dict[str, object]:
    return {
        "compiler_version": COMPILER_VERSION,
        "screen_manifest_sha256": screen.screen_manifest_sha256(),
        "header_parser_version": headers.PARSER_VERSION,
        "authorities": [authority.sha256 for authority in headers.AUTHORITIES],
        "coordinate": physical_coordinate(),
        "policy": envelope_policy(),
        "constants": {
            "gps_l1_hz": GPS_L1_HZ,
            "gps_l2_hz": GPS_L2_HZ,
            "rinex_phase_quantization_cycles": RINEX_PHASE_QUANTIZATION_CYCLES,
            "maximum_station_epoch_error_s": MAX_STATION_EPOCH_ERROR_S,
            "maximum_zenith_troposphere_m": MAX_ZENITH_TROPOSPHERE_M,
            "pairwise_envelope_multiplier": PAIRWISE_ENVELOPE_MULTIPLIER,
            "generic_path_bounds": GENERIC_PATH_BOUNDS_M,
        },
        "forbidden": [
            "observation epoch decoding before plan freeze",
            "carrier phase, code, SNR or LLI access",
            "post-outcome target, reference or signal selection",
            "holdout nuisance fitting",
            "threshold or envelope reduction after measurement access",
        ],
    }


def compiler_manifest_sha256() -> str:
    return sha256(strict_json(compiler_manifest()).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
