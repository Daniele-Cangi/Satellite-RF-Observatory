"""Pass-specific physical-envelope audit for the rank-1 Cassini DSS-14 path.

The exact header grid is reconstructed from its frozen descriptive receipt.
No RSR product, header, sample, amplitude, or detector input is accepted.
Central physical models never reduce an envelope without a documented hard
bound independent of the target RF outcome.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import ceil, pi, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way
from experiments.orbital_discriminability import cassini_dss26_open_term_audit as prior
from experiments.orbital_discriminability import cassini_dss14_header_evaluation as header_eval


AUDIT_VERSION: Final = "cassini-dss14-rank1-open-term-envelope-audit-v1"
RECEIPT_PATH: Final = Path(__file__).with_name("CASSINI_DSS14_HEADER_EVALUATION_RECEIPT.json")
FIRST_SAMPLE_UTC: Final = "2006-09-08T12:00:01.000000Z"
LAST_FIRST_SAMPLE_UTC: Final = "2006-09-08T15:00:00.000000Z"
GRID_RECORDS: Final = 10_800
CALIBRATION_RECORDS: Final = 2_160
REPRESENTATIVE_SAMPLE_OFFSET_S: Final = 0.5005
CONTROLLING_SEPARATION_HZ: Final = 0.18576614507706193
RSR_TIMING_BOUND_S: Final = 100e-9
REST_FREQUENCY_HZ: Final = 8_425_000_000.0
S_BAND_ION_REFERENCE_HZ: Final = 2_295_000_000.0
DETECTOR_BINS_REQUIRED: Final = 3.0
OUTCOME_BOUND_UNAVAILABLE: Final = "CASSINI_OPEN_TERM_BOUND_UNAVAILABLE"

OPEN_TERM_NAMES: Final = prior.OPEN_TERM_NAMES
PROVENANCE_INDEPENDENT: Final = prior.PROVENANCE_INDEPENDENT
PROVENANCE_UNKNOWN: Final = prior.PROVENANCE_UNKNOWN

SOURCES: Final = {
    "iers_proper_time": prior.SOURCES["iers_proper_time"],
    "iers_gravitational_delay": prior.SOURCES["iers_gravitational_delay"],
    "dsn_frequency_timing": prior.SOURCES["dsn_frequency_timing"],
    "dsn_media_interface": prior.SOURCES["dsn_media_interface"],
    "ion_product": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/"
        "sagr3_ancillary/ion/s23sagf2006_244_2006_273.ion"
    ),
    "tro_product": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/cors_0147/"
        "sagr3_ancillary/tro/s23sagf2006_244_2006_262.tro"
    ),
    "calibration_inventory": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr3-v10/"
        "cors_0147/calib/calinfo.txt"
    ),
    "jpl_gm": prior.SOURCES["jpl_gm"],
}

SOURCE_IDENTITIES: Final = {
    "dsn_media_interface": prior.SOURCE_IDENTITIES["dsn_media_interface"],
    "ion_product": {
        "bytes": 29_160,
        "sha256": "d643911892ee9a9d5b9f366e038d6705fd50769d9aa29c80f9192553c02c6aad",
        "label_sha256": "8c83f8ffc7e8b753260342c5ce89dde1e0decedb920d213e2f380a5513a2903f",
    },
    "tro_product": {
        "bytes": 133_236,
        "sha256": "5a3b116405157715e094075d99c4cb28c2c289490bfa93901a427faf52378dcb",
        "label_sha256": "abef1e1564f37ea30a13119f31887cfc201afe3beb81ba2bf23a85a4a712bcf0",
        "label_start_year_state": "INCONSISTENT_2005_IN_LABEL_CONTENT_USES_2006",
    },
    "calibration_inventory": {
        "bytes": 1_996,
        "sha256": "afc3866c51a62292600bfb93c30372c60702be4353fbc70ec76a474c3160f3b3",
    },
}

ION_INTERVAL_START: Final = "2006-09-08T11:21:00Z"
ION_INTERVAL_END: Final = "2006-09-09T00:52:00Z"
ION_COEFFICIENTS_M: Final = (
    1.0108, 0.0558, 2.1951, 0.3994, -4.9116,
    4.9861, 5.6071, -7.3999, -2.2253, 2.9873,
)
ION_FITSIG_M: Final = 0.0154957

TRO_CORRECTIONS: Final = (
    prior.TroCorrection(
        "2006-09-08T09:00:00.001000Z",
        "2006-09-08T15:00:00.000000Z",
        (-0.0796, -0.0233, 0.0120, 0.0686, -0.0215, -0.1134, 0.0104, 0.0796, -0.0013, -0.0193),
        (0.0014, 0.0013, 0.0005),
        0.0006464,
        0.0002454,
    ),
    prior.TroCorrection(
        "2006-09-08T15:00:00.001000Z",
        "2006-09-08T21:00:00.000000Z",
        (-0.0818, -0.0038, -0.0125, 0.0246, 0.0196, -0.0273, -0.0167, 0.0081, 0.0053),
        (0.0043, -0.0015, -0.0029, 0.0003, 0.0007),
        0.0007260,
        0.0002116,
    ),
)


class CassiniDss14OpenTermAuditError(ValueError):
    """The frozen rank-1 grid or physical metadata are inconsistent."""


def exact_frozen_grid() -> tuple[datetime, ...]:
    first = _parse_utc(FIRST_SAMPLE_UTC) + timedelta(seconds=REPRESENTATIVE_SAMPLE_OFFSET_S)
    grid = tuple(first + timedelta(seconds=index) for index in range(GRID_RECORDS))
    expected_last = _parse_utc(LAST_FIRST_SAMPLE_UTC) + timedelta(seconds=REPRESENTATIVE_SAMPLE_OFFSET_S)
    if grid[-1] != expected_last:
        raise CassiniDss14OpenTermAuditError("frozen grid endpoints do not agree")
    return grid


def validate_ranked_receipt(path: Path = RECEIPT_PATH) -> dict[str, object]:
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    if receipt["outcome"] != "CASSINI_DSS14_REAL_NCO_SIGNATURE_RANKED":
        raise CassiniDss14OpenTermAuditError("header ranking outcome changed")
    candidate = receipt["candidates"][0]
    if candidate["role"] != "HEADER_CANDIDATE_A" or candidate["rank"] != 1:
        raise CassiniDss14OpenTermAuditError("rank-1 candidate changed")
    header = candidate["header"]
    prediction = candidate["prediction"]
    checks = (
        header["record_count"] == GRID_RECORDS,
        header["first_sample_utc"] == FIRST_SAMPLE_UTC,
        header["last_first_sample_utc"] == LAST_FIRST_SAMPLE_UTC,
        header["non_one_second_steps"] == 0,
        prediction["calibration_records"] == CALIBRATION_RECORDS,
        prediction["heldout_peak_to_peak_hz"] == CONTROLLING_SEPARATION_HZ,
        receipt["claim_scope"]["controlling_null"] == "CALIBRATION_PREFIX_AFFINE_RECORDED_BASEBAND",
    )
    if not all(checks):
        raise CassiniDss14OpenTermAuditError("rank-1 receipt no longer matches frozen audit")
    return receipt


def audit_open_terms(*, spice, kernel_paths: Mapping[str, Path]) -> dict[str, object]:
    receipt = validate_ranked_receipt()
    grid = exact_frozen_grid()
    geometry = _compile_geometry(spice, kernel_paths, grid)
    proper_curve = prior._proper_time_gravity_curve(geometry)
    relativistic_curve = _relativistic_delay_frequency_curve(geometry)
    ion_curve = _ionosphere_frequency_curve(grid)
    tro_curve = _troposphere_frequency_curve(grid, geometry["elevation_rad"])
    media_curve = ion_curve + tro_curve
    diagnostics = {
        "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY": _projected_metrics(proper_curve),
        "RELATIVISTIC_PROPAGATION_LIGHT_TIME": _projected_metrics(relativistic_curve),
        "EARTH_TROPOSPHERE": _projected_metrics(tro_curve),
        "EARTH_IONOSPHERE": _projected_metrics(ion_curve),
        "AVAILABLE_MEDIA_CALIBRATION": _projected_metrics(media_curve),
    }
    terms = (
        _term(OPEN_TERM_NAMES[0], PROVENANCE_INDEPENDENT, diagnostics[OPEN_TERM_NAMES[0]],
              "Outcome-independent IERS central model has no mission/pass-specific hard truncation bound"),
        _term(OPEN_TERM_NAMES[1], PROVENANCE_INDEPENDENT, diagnostics[OPEN_TERM_NAMES[1]],
              "Outcome-independent IERS central model omits unbounded moving-body and higher-order terms"),
        _term(OPEN_TERM_NAMES[2], PROVENANCE_INDEPENDENT, diagnostics[OPEN_TERM_NAMES[2]],
              "Applicable TSAC TRO exists; FITSIG and approximate elevation mapping are not hard bounds"),
        _term(OPEN_TERM_NAMES[3], PROVENANCE_INDEPENDENT, diagnostics[OPEN_TERM_NAMES[3]],
              "Applicable TSAC ION exists; FITSIG is not a hard residual-frequency bound"),
        _term(OPEN_TERM_NAMES[4], PROVENANCE_UNKNOWN, None,
              "No applicable outcome-independent finite interplanetary ray-path plasma bound was found"),
        _term(OPEN_TERM_NAMES[5], PROVENANCE_UNKNOWN, None,
              "No pass-specific DSS-14 end-to-end receiver-delay/frequency hard bound was found"),
        _term(OPEN_TERM_NAMES[6], PROVENANCE_INDEPENDENT, diagnostics[OPEN_TERM_NAMES[6]],
              "ION/TRO coverage is complete but their residual error has no deterministic bound",
              role="NON_ADDITIVE_CONTROL_DO_NOT_DOUBLE_COUNT"),
    )
    timing = geometry["timing_envelope"]
    best_case = max(
        0.0,
        (CONTROLLING_SEPARATION_HZ - 2.0 * timing["maximum_absolute_hz"])
        / DETECTOR_BINS_REQUIRED,
    )
    result = {
        "audit_version": AUDIT_VERSION,
        "audit_manifest_sha256": audit_manifest_sha256(),
        "scope": "DSS14_2006_RANK1_METADATA_ONLY_NO_RSR_ACCESS",
        "authoritative_prior_outcome": receipt["outcome"],
        "controlling_comparison": "REAL_NCO_ORBITAL_VERSUS_PREFIX_AFFINE_BASEBAND",
        "controlling_heldout_peak_to_peak_hz": CONTROLLING_SEPARATION_HZ,
        "grid": {
            "first_representative_utc": _format_utc(grid[0]),
            "last_representative_utc": _format_utc(grid[-1]),
            "records": GRID_RECORDS,
            "cadence_s": 1.0,
            "calibration_records": CALIBRATION_RECORDS,
            "holdout_records": GRID_RECORDS - CALIBRATION_RECORDS,
            "suffix_refit": "PROHIBITED",
        },
        "source_identities": SOURCE_IDENTITIES,
        "sources": SOURCES,
        "kernel_lineage": geometry["kernel_lineage"],
        "outcome_conditioned_products_used": [],
        "terms": list(terms),
        "timing_envelope": timing,
        "conservative_combination": {
            "admitted_open_term_names": [],
            "admitted_open_term_peak_to_peak_hz": 0.0,
            "unresolved_open_term_names": list(OPEN_TERM_NAMES),
            "combined_open_term_envelope_state": "UNAVAILABLE",
            "timing_two_sided_peak_to_peak_hz": 2.0 * timing["maximum_absolute_hz"],
            "remaining_physical_margin_hz": None,
            "maximum_admissible_detector_resolution_hz": None,
            "detector_criterion": "signature > 3 * R_f + 2 * E_t + open_term_envelope",
            "best_case_upper_ceiling_if_every_unavailable_term_were_zero_hz": best_case,
            "best_case_ceiling_is_admission_requirement": False,
        },
        "outcome": OUTCOME_BOUND_UNAVAILABLE,
        "iq_access_authorized": False,
        "detector_implementation_authorized": False,
        "payload_role": "UNASSIGNED_AND_PROHIBITED",
        "next_smallest_physical_step": "MULTI_FREQUENCY_DIFFERENCING",
        "next_step_rationale": (
            "A phase-continuous detector changes sensitivity but does not bound the "
            "physical nuisance terms; fixed NCO enlarges steering separation but does "
            "not close those terms; both remaining DSS-14 headers were already ranked. "
            "A predeclared simultaneous multi-frequency observable can instead cancel "
            "non-dispersive terms and expose dispersive plasma as a measured coordinate."
        ),
    }
    strict_json(result)
    return result


def audit_manifest_sha256() -> str:
    manifest = {
        "audit_version": AUDIT_VERSION,
        "grid": [FIRST_SAMPLE_UTC, LAST_FIRST_SAMPLE_UTC, GRID_RECORDS, CALIBRATION_RECORDS, REPRESENTATIVE_SAMPLE_OFFSET_S],
        "controlling_separation_hz": CONTROLLING_SEPARATION_HZ,
        "timing_bound_s": RSR_TIMING_BOUND_S,
        "open_terms": list(OPEN_TERM_NAMES),
        "source_identities": SOURCE_IDENTITIES,
        "forbidden": ["RSR access", "IQ decoding", "detector implementation", "affine-null removal", "suffix refit"],
    }
    return sha256(strict_json(manifest).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _compile_geometry(spice, kernel_paths: Mapping[str, Path], grid: Sequence[datetime]):
    receive_et: list[float] = []
    transmit_et: list[float] = []
    station_positions: list[tuple[float, float, float]] = []
    spacecraft_positions: list[tuple[float, float, float]] = []
    earth_receive: list[tuple[float, float, float]] = []
    earth_transmit: list[tuple[float, float, float]] = []
    sun_receive: list[tuple[float, float, float]] = []
    sun_transmit: list[tuple[float, float, float]] = []
    saturn_receive: list[tuple[float, float, float]] = []
    saturn_transmit: list[tuple[float, float, float]] = []
    timing_max = 0.0

    with header_eval._loaded_exact_kernels(
        spice, "HEADER_CANDIDATE_A", kernel_paths
    ) as lineage:
        station = one_way._spice_state_provider(spice, "DSS-14")
        cassini = one_way._spice_state_provider(spice, "CASSINI")
        earth = one_way._spice_state_provider(spice, "EARTH")
        sun = one_way._spice_state_provider(spice, "SUN")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        first_et = float(spice.utc2et(_format_utc(grid[0])))
        for index in range(len(grid)):
            et = first_et + float(index)
            event = one_way.solve_one_way_event(et, station, cassini)
            minus = one_way.solve_one_way_event(
                et - RSR_TIMING_BOUND_S, station, cassini
            )
            plus = one_way.solve_one_way_event(
                et + RSR_TIMING_BOUND_S, station, cassini
            )
            timing_max = max(
                timing_max,
                REST_FREQUENCY_HZ
                * abs(
                    minus.kinematic_frequency_factor
                    - event.kinematic_frequency_factor
                ),
                REST_FREQUENCY_HZ
                * abs(
                    plus.kinematic_frequency_factor
                    - event.kinematic_frequency_factor
                ),
            )
            receive_et.append(et)
            transmit_et.append(event.transmit_et_tdb_s)
            station_positions.append(station(et).position_m)
            spacecraft_positions.append(cassini(event.transmit_et_tdb_s).position_m)
            earth_receive.append(earth(et).position_m)
            earth_transmit.append(earth(event.transmit_et_tdb_s).position_m)
            sun_receive.append(sun(et).position_m)
            sun_transmit.append(sun(event.transmit_et_tdb_s).position_m)
            saturn_receive.append(saturn(et).position_m)
            saturn_transmit.append(saturn(event.transmit_et_tdb_s).position_m)

    station_array = np.asarray(station_positions, dtype=np.float64)
    spacecraft_array = np.asarray(spacecraft_positions, dtype=np.float64)
    earth_array = np.asarray(earth_receive, dtype=np.float64)
    line = spacecraft_array - station_array
    zenith = station_array - earth_array
    line /= np.linalg.norm(line, axis=1)[:, None]
    zenith /= np.linalg.norm(zenith, axis=1)[:, None]
    elevation = np.arcsin(np.clip(np.sum(line * zenith, axis=1), -1.0, 1.0))
    return {
        "kernel_lineage": list(lineage),
        "receive_et": np.asarray(receive_et),
        "transmit_et": np.asarray(transmit_et),
        "station": station_array,
        "spacecraft": spacecraft_array,
        "earth_receive": earth_array,
        "earth_transmit": np.asarray(earth_transmit),
        "sun_receive": np.asarray(sun_receive),
        "sun_transmit": np.asarray(sun_transmit),
        "saturn_receive": np.asarray(saturn_receive),
        "saturn_transmit": np.asarray(saturn_transmit),
        "elevation_rad": elevation,
        "timing_envelope": {
            "event_time_bound_s": RSR_TIMING_BOUND_S,
            "method": "DIRECT_TRAJECTORY_EVALUATION_AT_T_MINUS_AND_PLUS_BOUND",
            "maximum_absolute_hz": timing_max,
            "numerical_policy": (
                "CONSERVATIVE_BINARY64_RESULT_INCLUDES_SUB_MICROHERTZ_"
                "CANCELLATION_FLOOR"
            ),
            "provenance": PROVENANCE_INDEPENDENT,
        },
    }


def _relativistic_delay_frequency_curve(geometry) -> np.ndarray:
    total_delay = np.zeros(GRID_RECORDS, dtype=np.float64)
    for gm, receive_key in (
        (prior.GM_SUN, "sun_receive"),
        (prior.GM_EARTH, "earth_receive"),
        (prior.GM_SATURN_SYSTEM, "saturn_receive"),
    ):
        body = geometry[receive_key]
        receiver_radius = _row_norm(geometry["station"] - body)
        transmitter_radius = _row_norm(geometry["spacecraft"] - body)
        endpoint_range = _row_norm(
            geometry["spacecraft"] - geometry["station"]
        )
        numerator = receiver_radius + transmitter_radius + endpoint_range
        denominator = receiver_radius + transmitter_radius - endpoint_range
        if np.any(denominator <= 0.0):
            raise CassiniDss14OpenTermAuditError(
                "invalid gravitational-delay geometry"
            )
        total_delay += (
            2.0 * gm / one_way.SPEED_OF_LIGHT_M_S**3
        ) * np.log(numerator / denominator)
    return -REST_FREQUENCY_HZ * np.gradient(total_delay, 1.0, edge_order=2)


def _ionosphere_frequency_curve(grid: Sequence[datetime]) -> np.ndarray:
    start = _parse_utc(ION_INTERVAL_START)
    end = _parse_utc(ION_INTERVAL_END)
    seconds = np.asarray([(instant - start).total_seconds() for instant in grid])
    span = (end - start).total_seconds()
    if seconds.min() < 0.0 or seconds.max() > span:
        raise CassiniDss14OpenTermAuditError(
            "ION calibration does not cover frozen grid"
        )
    x = 2.0 * seconds / span - 1.0
    delay_s_band_m = _power_series(ION_COEFFICIENTS_M, x)
    delay_x_band_m = delay_s_band_m * (
        S_BAND_ION_REFERENCE_HZ / REST_FREQUENCY_HZ
    ) ** 2
    return (REST_FREQUENCY_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        delay_x_band_m, 1.0, edge_order=2
    )


def _troposphere_frequency_curve(
    grid: Sequence[datetime], elevation_rad: np.ndarray
) -> np.ndarray:
    seasonal_reference = _parse_utc(prior.TRO_SEASONAL_REFERENCE)
    seconds = np.asarray(
        [(instant - seasonal_reference).total_seconds() for instant in grid]
    )
    angle = 2.0 * pi * seconds / prior.TRO_SEASONAL_PERIOD_S
    wet = _trig_series(prior.TRO_SEASONAL_WET_M, angle)
    dry = _trig_series(prior.TRO_SEASONAL_DRY_M, angle)
    assigned = np.zeros(GRID_RECORDS, dtype=bool)
    for correction in TRO_CORRECTIONS:
        start = _parse_utc(correction.start_utc)
        end = _parse_utc(correction.end_utc)
        mask = np.asarray([start <= instant <= end for instant in grid])
        if not np.any(mask):
            continue
        local_seconds = np.asarray(
            [(instant - start).total_seconds() for instant in grid]
        )
        span = (end - start).total_seconds()
        x = 2.0 * local_seconds[mask] / span - 1.0
        wet[mask] += _power_series(correction.wet_coefficients_m, x)
        dry[mask] += _power_series(correction.dry_coefficients_m, x)
        assigned[mask] = True
    if not np.all(assigned):
        raise CassiniDss14OpenTermAuditError(
            "TRO corrections do not cover frozen grid"
        )
    if np.any(elevation_rad <= 0.0):
        raise CassiniDss14OpenTermAuditError(
            "frozen track is below the geometric horizon"
        )
    slant_delay_m = (wet + dry) / np.sin(elevation_rad)
    return -(REST_FREQUENCY_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        slant_delay_m, 1.0, edge_order=2
    )


def _projected_metrics(curve: Sequence[float]) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if values.shape != (GRID_RECORDS,) or not np.all(np.isfinite(values)):
        raise CassiniDss14OpenTermAuditError(
            "term curve is not finite on the exact grid"
        )
    elapsed = np.arange(GRID_RECORDS, dtype=np.float64)
    design = np.column_stack(
        (np.ones(CALIBRATION_RECORDS), elapsed[:CALIBRATION_RECORDS])
    )
    coefficients, *_ = np.linalg.lstsq(
        design, values[:CALIBRATION_RECORDS], rcond=None
    )
    residual = values - (coefficients[0] + coefficients[1] * elapsed)
    heldout = residual[CALIBRATION_RECORDS:]
    return {
        "peak_to_peak_hz": float(np.ptp(heldout)),
        "rms_hz": float(sqrt(float(np.mean(heldout * heldout)))),
        "maximum_absolute_hz": float(np.max(np.abs(heldout))),
    }


def _term(
    name: str,
    provenance: str,
    central_metrics: dict[str, float] | None,
    reason: str,
    *,
    role: str = "ADDITIVE_PHYSICAL_TERM",
) -> dict[str, object]:
    if name not in OPEN_TERM_NAMES:
        raise CassiniDss14OpenTermAuditError(
            "term is outside the frozen seven-entry ledger"
        )
    return {
        "name": name,
        "provenance": provenance,
        "central_model_heldout_non_affine": central_metrics,
        "central_model_reduces_envelope": False,
        "bound_state": "UNAVAILABLE",
        "admitted_heldout_peak_to_peak_bound_hz": None,
        "admitted_heldout_rms_bound_hz": None,
        "combination_role": role,
        "reason": reason,
    }


def _power_series(coefficients: Sequence[float], x: np.ndarray) -> np.ndarray:
    result = np.zeros_like(x, dtype=np.float64)
    for coefficient in reversed(coefficients):
        result = result * x + coefficient
    return result


def _trig_series(coefficients: Sequence[float], angle: np.ndarray) -> np.ndarray:
    if len(coefficients) % 2 != 1:
        raise CassiniDss14OpenTermAuditError(
            "TRIG series must contain A0 and A/B pairs"
        )
    result = np.full_like(angle, coefficients[0], dtype=np.float64)
    harmonic = 1
    for index in range(1, len(coefficients), 2):
        result += coefficients[index] * np.cos(harmonic * angle)
        result += coefficients[index + 1] * np.sin(harmonic * angle)
        harmonic += 1
    return result


def _row_norm(values: np.ndarray) -> np.ndarray:
    return np.linalg.norm(values, axis=1)


def _parse_utc(value: str) -> datetime:
    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None or instant.utcoffset() != timedelta(0):
        raise CassiniDss14OpenTermAuditError("UTC value is not explicit UTC")
    return instant.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")
