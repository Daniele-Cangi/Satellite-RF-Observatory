"""Metadata-only physical-envelope audit for the frozen Cassini DSS-26 spike.

This module reconstructs the already frozen one-second header time grid from
the committed receipt.  It never opens the RSR artifact and has no sample or
amplitude input.  Central curves are diagnostics unless an outcome-independent
source also supplies a deterministic numerical error bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import asin, ceil, cos, isfinite, log, pi, sin, sqrt
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import cassini_dss26_one_way as one_way


AUDIT_VERSION: Final = "cassini-dss26-open-term-envelope-audit-v1"
CONTROLLING_SEPARATION_HZ: Final = 0.06391264328448062
RECEIPT_PATH: Final = Path(__file__).with_name("CASSINI_DSS26_HEADER_SPIKE_RECEIPT.json")
FIRST_SAMPLE_UTC: Final = "2005-06-06T17:50:01.000000Z"
LAST_FIRST_SAMPLE_UTC: Final = "2005-06-06T20:30:51.000000Z"
GRID_RECORDS: Final = 9_651
CALIBRATION_RECORDS: Final = 1_931
REPRESENTATIVE_SAMPLE_OFFSET_S: Final = 0.5005
RSR_TIMING_BOUND_S: Final = 100e-9
REST_FREQUENCY_HZ: Final = 8_425_000_000.0
S_BAND_ION_REFERENCE_HZ: Final = 2_295_000_000.0
DETECTOR_BINS_REQUIRED: Final = 3.0

OUTCOME_BOUND_UNAVAILABLE: Final = "CASSINI_OPEN_TERM_BOUND_UNAVAILABLE"
OUTCOME_ENVELOPE_DOMINATES: Final = "CASSINI_OPEN_TERM_ENVELOPE_DOMINATES"
OUTCOME_DETECTOR_IMPLAUSIBLE: Final = "CASSINI_DETECTOR_REQUIREMENT_NOT_PLAUSIBLE"
OUTCOME_MARGIN_ADMITTED: Final = "CASSINI_BASEBAND_PHYSICAL_MARGIN_ADMITTED"

PROVENANCE_INDEPENDENT: Final = "INDEPENDENT_OF_TARGET_RF"
PROVENANCE_OUTCOME_CONDITIONED: Final = "OUTCOME_CONDITIONED"
PROVENANCE_UNKNOWN: Final = "UNKNOWN"

OPEN_TERM_NAMES: Final = (
    "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY",
    "RELATIVISTIC_PROPAGATION_LIGHT_TIME",
    "EARTH_TROPOSPHERE",
    "EARTH_IONOSPHERE",
    "INTERPLANETARY_PLASMA",
    "STATION_HARDWARE_DELAY",
    "AVAILABLE_MEDIA_CALIBRATION",
)

SOURCES: Final = {
    "iers_proper_time": "https://iers-conventions.obspm.fr/content/chapter10/tn36_c10.pdf",
    "iers_gravitational_delay": (
        "https://iers-conventions.obspm.fr/content/chapter11/tn36_c11.pdf"
    ),
    "dsn_frequency_timing": "https://deepspace.jpl.nasa.gov/dsndocs/810-005/304/304C.pdf",
    "dsn_media_interface": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/"
        "cors_0103/document/trk_2_23_000531.txt"
    ),
    "ion_product": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/"
        "cors_0103/sagr1_ancillary/ion/s11sags2005_152_2005_181.ion"
    ),
    "tro_product": (
        "https://atmos.nmsu.edu/pdsd/archive/data/co-s-rss-1-sagr1-v10/"
        "cors_0103/sagr1_ancillary/tro/s11sags2005_152_2005_184.tro"
    ),
    "jpl_gm": "https://ssd.jpl.nasa.gov/astro_par.html",
}

SOURCE_IDENTITIES: Final = {
    "dsn_media_interface": {
        "bytes": 25_915,
        "sha256": "e2f8617eb454b0b057c3277806aaab339ff937bc3410495f2d0f0bac5b23ca22",
    },
    "ion_product": {
        "bytes": 29_484,
        "sha256": "21fb22a0ea5bc9da710c6385ea0e36095d21e58cbbf86627e077554d82c91dd6",
    },
    "tro_product": {
        "bytes": 109_194,
        "sha256": "467616e3a092d7643c73e0f645de82c1167ba21b9f0d7de0f61527558829cc10",
    },
}

# JPL DE440 system GMs, converted from km^3/s^2 to m^3/s^2.  They are used
# only for an explicitly incomplete central diagnostic; they are not promoted
# to a deterministic uncertainty bound.
GM_SUN: Final = 1.32712440041279419e20
GM_EARTH: Final = 398_600.435507e9
GM_SATURN_SYSTEM: Final = 37_940_584.841800e9

# Exact applicable PDS/TSAC line-of-sight ionosphere calibration for DSCC 10,
# SCID 82.  TRK-2-23 states that these are one-way range-delay metres at
# 2295 MHz and defines the normalized-power argument.
ION_INTERVAL_START: Final = "2005-06-06T15:35:00Z"
ION_INTERVAL_END: Final = "2005-06-07T05:40:00Z"
ION_COEFFICIENTS_M: Final = (
    1.4535,
    0.5757,
    -0.5330,
    -2.5776,
    7.0765,
    8.6385,
    -7.7325,
    -14.3139,
    3.0158,
    7.9586,
)
ION_FITSIG_M: Final = 0.0269351

# DSCC 10 seasonal zenith models reproduced by TRK-2-23 Figure 3-2.
TRO_SEASONAL_PERIOD_S: Final = 31_557_600.0
TRO_SEASONAL_REFERENCE: Final = "1972-01-01T00:00:00Z"
TRO_SEASONAL_WET_M: Final = (
    0.0870,
    -0.0360,
    -0.0336,
    0.0002,
    0.0200,
    0.0008,
    -0.0021,
    -0.0036,
    -0.0002,
)
TRO_SEASONAL_DRY_M: Final = (
    2.0521,
    0.0082,
    -0.0005,
    -0.0004,
    0.0033,
    -0.0015,
    0.0005,
    -0.0011,
    0.0036,
)


@dataclass(frozen=True, slots=True)
class TroCorrection:
    start_utc: str
    end_utc: str
    wet_coefficients_m: tuple[float, ...]
    dry_coefficients_m: tuple[float, ...]
    wet_fitsig_m: float
    dry_fitsig_m: float


TRO_CORRECTIONS: Final = (
    TroCorrection(
        "2005-06-06T06:00:00.001000Z",
        "2005-06-06T18:00:00.000000Z",
        (-0.0666, 0.0285, 0.0052, -0.0860, 0.0051, 0.0761, -0.0074, -0.0209),
        (0.0034, 0.0072, -0.0021, -0.0030, 0.0018),
        0.0011311,
        0.0005324,
    ),
    TroCorrection(
        "2005-06-06T18:00:00.001000Z",
        "2005-06-07T06:00:00.000000Z",
        (-0.0730, 0.0021, 0.0158, 0.0141, 0.0176, -0.0254, -0.0515, 0.0081, 0.0230),
        (0.0087, 0.0015),
        0.0010107,
        0.00003883,
    ),
)


class CassiniOpenTermAuditError(ValueError):
    """The frozen metadata or physical-envelope inputs are inconsistent."""


def exact_frozen_grid() -> tuple[datetime, ...]:
    """Reconstruct the committed 9651-record grid without opening the RSR."""

    first = _parse_utc(FIRST_SAMPLE_UTC) + timedelta(seconds=REPRESENTATIVE_SAMPLE_OFFSET_S)
    grid = tuple(first + timedelta(seconds=index) for index in range(GRID_RECORDS))
    expected_last = _parse_utc(LAST_FIRST_SAMPLE_UTC) + timedelta(
        seconds=REPRESENTATIVE_SAMPLE_OFFSET_S
    )
    if grid[-1] != expected_last:
        raise CassiniOpenTermAuditError("frozen grid endpoints do not agree")
    return grid


def validate_authoritative_receipt(path: Path = RECEIPT_PATH) -> dict[str, object]:
    """Validate only the committed descriptive receipt, never the RSR artifact."""

    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    continuity = receipt["header_continuity"]
    prediction = receipt["prediction"]
    if continuity["record_count"] != GRID_RECORDS:
        raise CassiniOpenTermAuditError("receipt record count changed")
    if continuity["first_sample_utc"] != FIRST_SAMPLE_UTC:
        raise CassiniOpenTermAuditError("receipt first epoch changed")
    if continuity["last_first_sample_utc"] != LAST_FIRST_SAMPLE_UTC:
        raise CassiniOpenTermAuditError("receipt last epoch changed")
    if continuity["non_one_second_time_steps"] != 0:
        raise CassiniOpenTermAuditError("receipt no longer proves a one-second grid")
    if prediction["calibration_records"] != CALIBRATION_RECORDS:
        raise CassiniOpenTermAuditError("calibration prefix changed")
    separation = prediction["heldout_orbital_vs_affine_baseband_peak_to_peak_hz"]
    if separation != CONTROLLING_SEPARATION_HZ:
        raise CassiniOpenTermAuditError("controlling affine-null separation changed")
    if tuple(receipt["open_terms_without_numerical_bound"]) != OPEN_TERM_NAMES:
        raise CassiniOpenTermAuditError("the seven-term frozen ledger changed")
    return receipt


def audit_open_terms(*, spice, kernel_paths: Mapping[str, Path]) -> dict[str, object]:
    """Evaluate independent central models and preserve unavailable bounds."""

    receipt = validate_authoritative_receipt()
    grid = exact_frozen_grid()
    geometry = _compile_geometry(spice, kernel_paths, grid)

    proper_curve = _proper_time_gravity_curve(geometry)
    relativistic_curve = _relativistic_delay_frequency_curve(geometry)
    ion_curve = _ionosphere_frequency_curve(grid)
    tro_curve = _troposphere_frequency_curve(grid, geometry["elevation_rad"])
    media_curve = ion_curve + tro_curve

    central_metrics = {
        "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY": _projected_metrics(proper_curve),
        "RELATIVISTIC_PROPAGATION_LIGHT_TIME": _projected_metrics(relativistic_curve),
        "EARTH_TROPOSPHERE": _projected_metrics(tro_curve),
        "EARTH_IONOSPHERE": _projected_metrics(ion_curve),
        "AVAILABLE_MEDIA_CALIBRATION": _projected_metrics(media_curve),
    }
    terms = [
        _unavailable_term(
            "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY",
            PROVENANCE_INDEPENDENT,
            central_metrics["PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY"],
            "IERS weak-field central model evaluated for Sun/Earth/Saturn only; "
            "no mission-specific truncation/error product supplies a deterministic bound",
        ),
        _unavailable_term(
            "RELATIVISTIC_PROPAGATION_LIGHT_TIME",
            PROVENANCE_INDEPENDENT,
            central_metrics["RELATIVISTIC_PROPAGATION_LIGHT_TIME"],
            "IERS Sun/Earth/Saturn gravitational-delay central model is not a bound on "
            "all gravitating bodies and higher-order path terms",
        ),
        _unavailable_term(
            "EARTH_TROPOSPHERE",
            PROVENANCE_INDEPENDENT,
            central_metrics["EARTH_TROPOSPHERE"],
            "TSAC TRO central product and seasonal model are independent of target RF, "
            "but FITSIG and approximate mapping are not deterministic error bounds",
        ),
        _unavailable_term(
            "EARTH_IONOSPHERE",
            PROVENANCE_INDEPENDENT,
            central_metrics["EARTH_IONOSPHERE"],
            "TSAC line-of-sight ION product is independent of target RF, but FITSIG is "
            "not a deterministic bound on residual dispersive frequency",
        ),
        _unavailable_term(
            "INTERPLANETARY_PLASMA",
            PROVENANCE_UNKNOWN,
            None,
            "SAGR1 contains no applicable solar-plasma calibration and no public "
            "outcome-independent finite density bound was found for this ray path",
        ),
        _unavailable_term(
            "STATION_HARDWARE_DELAY",
            PROVENANCE_UNKNOWN,
            None,
            "DSN handbook stability values are statistical or generic; no pass-specific "
            "DSS-26 end-to-end receiver-delay calibration with a hard bound was found",
        ),
        _unavailable_term(
            "AVAILABLE_MEDIA_CALIBRATION",
            PROVENANCE_INDEPENDENT,
            central_metrics["AVAILABLE_MEDIA_CALIBRATION"],
            "ION and TRO products exist and were evaluated, but this ledger item is a "
            "non-additive calibration-coverage control and their residual uncertainty "
            "has no deterministic bound",
            combination_role="NON_ADDITIVE_CONTROL_DO_NOT_DOUBLE_COUNT",
        ),
    ]

    timing = geometry["timing_envelope"]
    unresolved = [term["name"] for term in terms if term["bound_state"] == "UNAVAILABLE"]
    # G0/G1's frozen rule requires three detector bins plus the two-sided
    # timing envelope to fit inside the physical separation.  Because the
    # seven-term envelope is unavailable, this is only an optimistic ceiling,
    # not an admitted detector requirement.
    best_case_remaining = CONTROLLING_SEPARATION_HZ - 2.0 * timing["maximum_absolute_hz"]
    best_case_resolution = max(0.0, best_case_remaining / DETECTOR_BINS_REQUIRED)
    result = {
        "audit_version": AUDIT_VERSION,
        "scope": "DSS26_DEVELOPMENT_METADATA_ONLY_NO_RSR_ACCESS",
        "authoritative_prior_outcome": receipt["outcome"],
        "controlling_comparison": "REAL_NCO_ORBITAL_VERSUS_PREFIX_AFFINE_BASEBAND",
        "controlling_heldout_peak_to_peak_hz": CONTROLLING_SEPARATION_HZ,
        "larger_null_separations_control_claim": False,
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
        "outcome_conditioned_products_used": [],
        "terms": terms,
        "timing_envelope": timing,
        "conservative_combination": {
            "admitted_open_term_peak_to_peak_hz": 0.0,
            "admitted_open_term_names": [],
            "unresolved_open_term_names": unresolved,
            "combined_open_term_envelope_state": "UNAVAILABLE",
            "timing_two_sided_peak_to_peak_hz": 2.0 * timing["maximum_absolute_hz"],
            "remaining_physical_margin_hz": None,
            "maximum_admissible_detector_resolution_hz": None,
            "detector_criterion": "signature > 3 * R_f + 2 * E_t + open_term_envelope",
            "best_case_upper_ceiling_if_every_unavailable_term_were_zero_hz": (
                best_case_resolution
            ),
            "best_case_ceiling_is_admission_requirement": False,
        },
        "outcome": OUTCOME_BOUND_UNAVAILABLE,
        "iq_access_authorized": False,
        "detector_implementation_authorized": False,
        "sealed_roles": {
            "development_dss26": "CLOSED_AFTER_METADATA_AUDIT",
            "primary_dss14": "SEALED_UNOPENED",
            "reserve_dss14": "SEALED_UNOPENED",
        },
        "next_smallest_physical_step": (
            "HEADER_ONLY_EVALUATION_OF_REMAINING_CASSINI_CANDIDATES_AFTER_EXPLICIT_"
            "ROLE_REASSIGNMENT; CURRENT_PRIMARY_AND_RESERVE_REMAIN_SEALED"
        ),
    }
    strict_json(result)
    return result


def audit_manifest_sha256() -> str:
    manifest = {
        "audit_version": AUDIT_VERSION,
        "controlling_separation_hz": CONTROLLING_SEPARATION_HZ,
        "grid": [
            FIRST_SAMPLE_UTC,
            LAST_FIRST_SAMPLE_UTC,
            GRID_RECORDS,
            CALIBRATION_RECORDS,
            REPRESENTATIVE_SAMPLE_OFFSET_S,
        ],
        "timing_bound_s": RSR_TIMING_BOUND_S,
        "open_terms": list(OPEN_TERM_NAMES),
        "source_identities": SOURCE_IDENTITIES,
        "forbidden": [
            "RSR artifact access",
            "IQ decoding",
            "detector implementation",
            "affine-null removal",
            "DSS-14 primary access",
            "DSS-14 reserve access",
        ],
    }
    return sha256(strict_json(manifest).encode("ascii")).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


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
    factor: list[float] = []
    timing_max = 0.0

    with one_way._loaded_frozen_kernels(spice, kernel_paths):
        station = one_way._spice_state_provider(spice, one_way.DEVELOPMENT_STATION)
        cassini = one_way._spice_state_provider(spice, one_way.SPACECRAFT)
        earth = one_way._spice_state_provider(spice, "EARTH")
        sun = one_way._spice_state_provider(spice, "SUN")
        saturn = one_way._spice_state_provider(spice, "SATURN BARYCENTER")
        first_et = float(spice.utc2et(_format_utc(grid[0])))
        for index in range(len(grid)):
            et = first_et + float(index)
            event = one_way.solve_one_way_event(et, station, cassini)
            minus = one_way.solve_one_way_event(et - RSR_TIMING_BOUND_S, station, cassini)
            plus = one_way.solve_one_way_event(et + RSR_TIMING_BOUND_S, station, cassini)
            timing_max = max(
                timing_max,
                REST_FREQUENCY_HZ
                * abs(minus.kinematic_frequency_factor - event.kinematic_frequency_factor),
                REST_FREQUENCY_HZ
                * abs(plus.kinematic_frequency_factor - event.kinematic_frequency_factor),
            )
            receive_et.append(et)
            transmit_et.append(event.transmit_et_tdb_s)
            factor.append(event.kinematic_frequency_factor)
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
        "receive_et": np.asarray(receive_et),
        "transmit_et": np.asarray(transmit_et),
        "factor": np.asarray(factor),
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


def _proper_time_gravity_curve(geometry) -> np.ndarray:
    station = geometry["station"]
    spacecraft = geometry["spacecraft"]
    receive_potential = (
        GM_SUN / _row_norm(station - geometry["sun_receive"])
        + GM_EARTH / _row_norm(station - geometry["earth_receive"])
        + GM_SATURN_SYSTEM / _row_norm(station - geometry["saturn_receive"])
    )
    transmit_potential = (
        GM_SUN / _row_norm(spacecraft - geometry["sun_transmit"])
        + GM_EARTH / _row_norm(spacecraft - geometry["earth_transmit"])
        + GM_SATURN_SYSTEM / _row_norm(spacecraft - geometry["saturn_transmit"])
    )
    return REST_FREQUENCY_HZ * (receive_potential - transmit_potential) / (
        one_way.SPEED_OF_LIGHT_M_S**2
    )


def _relativistic_delay_frequency_curve(geometry) -> np.ndarray:
    total_delay = np.zeros(GRID_RECORDS, dtype=np.float64)
    for gm, receive_key in (
        (GM_SUN, "sun_receive"),
        (GM_EARTH, "earth_receive"),
        (GM_SATURN_SYSTEM, "saturn_receive"),
    ):
        # Use a common body epoch for the static IERS logarithmic diagnostic.
        # Mixing a moving body's transmit and receive positions violates the
        # Euclidean triangle used by that expression.  The omitted moving-body
        # correction is one reason this central curve cannot reduce the bound.
        body = geometry[receive_key]
        receiver_radius = _row_norm(geometry["station"] - body)
        transmitter_radius = _row_norm(geometry["spacecraft"] - body)
        endpoint_range = _row_norm(geometry["spacecraft"] - geometry["station"])
        numerator = receiver_radius + transmitter_radius + endpoint_range
        denominator = receiver_radius + transmitter_radius - endpoint_range
        if np.any(denominator <= 0.0):
            raise CassiniOpenTermAuditError("invalid gravitational-delay geometry")
        total_delay += (2.0 * gm / one_way.SPEED_OF_LIGHT_M_S**3) * np.log(
            numerator / denominator
        )
    return -REST_FREQUENCY_HZ * np.gradient(total_delay, 1.0, edge_order=2)


def _ionosphere_frequency_curve(grid: Sequence[datetime]) -> np.ndarray:
    start = _parse_utc(ION_INTERVAL_START)
    end = _parse_utc(ION_INTERVAL_END)
    seconds = np.asarray([(instant - start).total_seconds() for instant in grid])
    span = (end - start).total_seconds()
    if seconds.min() < 0.0 or seconds.max() > span:
        raise CassiniOpenTermAuditError("ION calibration does not cover frozen grid")
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
    seasonal_reference = _parse_utc(TRO_SEASONAL_REFERENCE)
    seconds = np.asarray(
        [(instant - seasonal_reference).total_seconds() for instant in grid]
    )
    angle = 2.0 * pi * seconds / TRO_SEASONAL_PERIOD_S
    wet = _trig_series(TRO_SEASONAL_WET_M, angle)
    dry = _trig_series(TRO_SEASONAL_DRY_M, angle)
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
        raise CassiniOpenTermAuditError("TRO corrections do not cover frozen grid")
    if np.any(elevation_rad <= 0.0):
        raise CassiniOpenTermAuditError("frozen track is below the geometric horizon")
    # TRK-2-23 documents approximately 1/sin(elevation); ODP uses a more
    # complete mapping function.  This is deliberately a central diagnostic,
    # never an uncertainty-reducing bound.
    slant_delay_m = (wet + dry) / np.sin(elevation_rad)
    return -(REST_FREQUENCY_HZ / one_way.SPEED_OF_LIGHT_M_S) * np.gradient(
        slant_delay_m, 1.0, edge_order=2
    )


def _projected_metrics(curve: Sequence[float]) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if values.shape != (GRID_RECORDS,) or not np.all(np.isfinite(values)):
        raise CassiniOpenTermAuditError("term curve is not finite on the exact grid")
    elapsed = np.arange(GRID_RECORDS, dtype=np.float64)
    design = np.column_stack((np.ones(CALIBRATION_RECORDS), elapsed[:CALIBRATION_RECORDS]))
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


def _unavailable_term(
    name: str,
    provenance: str,
    central_metrics: dict[str, float] | None,
    reason: str,
    *,
    combination_role: str = "ADDITIVE_PHYSICAL_TERM",
) -> dict[str, object]:
    if name not in OPEN_TERM_NAMES:
        raise CassiniOpenTermAuditError("term is outside the frozen seven-entry ledger")
    return {
        "name": name,
        "provenance": provenance,
        "central_model_heldout_non_affine": central_metrics,
        "central_model_reduces_envelope": False,
        "bound_state": "UNAVAILABLE",
        "admitted_heldout_peak_to_peak_bound_hz": None,
        "admitted_heldout_rms_bound_hz": None,
        "combination_role": combination_role,
        "reason": reason,
    }


def _power_series(coefficients: Sequence[float], x: np.ndarray) -> np.ndarray:
    result = np.zeros_like(x, dtype=np.float64)
    for coefficient in reversed(coefficients):
        result = result * x + coefficient
    return result


def _trig_series(coefficients: Sequence[float], angle: np.ndarray) -> np.ndarray:
    if len(coefficients) % 2 != 1:
        raise CassiniOpenTermAuditError("TRIG series must contain A0 and A/B pairs")
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
        raise CassiniOpenTermAuditError("UTC value is not explicit UTC")
    return instant.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
