"""Navigation-only design for a KIRU/MAT1 native-Doppler forward test.

The module accepts only three predeclared broadcast-navigation products.  It
never accepts an observation file.  It ranks one robustly jointly visible
window per day by prefix-affine and wrong-orbit separation after a direct
independent station-clock trajectory audit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from typing import Final, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_independent_forward_review as review


DESIGN_VERSION: Final = "gnss-kiru-mat1-native-doppler-design-v1"
EXPANSION_VERSION: Final = "gnss-kiru-mat1-native-doppler-expansion-v1"
ORBITALITY_VERSION: Final = "gnss-kiru-mat1-native-doppler-orbitality-v1"
DEVELOPMENT_DOY: Final = 214
CLOSED_PRIMARY_DOY: Final = 215
CANDIDATE_DOYS: Final = (216, 217, 218)
EXPANSION_CANDIDATE_DOYS: Final = tuple(range(219, 233))
STATION_IDS: Final = ("KIRU00SWE", "MAT100ITA")
OBSERVABLES: Final = ("C1C", "D1C", "S1C", "C2W", "D2W", "S2W")
STEP_S: Final = 30.0
WINDOW_RECORDS: Final = 380
CALIBRATION_RECORDS: Final = 76
HELDOUT_RECORDS: Final = 304
SEARCH_STRIDE_RECORDS: Final = 20
MINIMUM_ELEVATION_DEG: Final = 15.0
CLOCK_ERROR_S: Final = 15.0
CLOCK_SHIFTS_S: Final = (-CLOCK_ERROR_S, 0.0, CLOCK_ERROR_S)
GPS_MINUS_UTC_S: Final = 18.0
RINEX_DOPPLER_SIGN: Final = "POSITIVE_FOR_APPROACHING_SATELLITES"
RINEX_SPECIFICATION_URL: Final = (
    "https://files.igs.org/pub/data/format/rinex304.pdf"
)
QUALIFICATION_RECEIPT_SHA256: Final = (
    "5e2d319ba633dce788bfa0a8b8961fa228a4b6ffd0ed47787b92c59520b37f0d"
)
CLOSED_PRIMARY_OUTCOME_SHA256: Final = (
    "5e4e54c1cae1f431eacc8101bb995de18c548e4ea7dcb46a71313517e90ea02b"
)
INITIAL_DESIGN_RECEIPT_SHA256: Final = (
    "561ef4c5954d1652702d954315071088ed2d66c021b10e7dd4bdda15fba51afb"
)
EXPANSION_RECEIPT_SHA256: Final = (
    "a0c0b1d34b251315c1daf0e043d6bfec1e2c51dc9096c78c8da35352ff2f7292"
)


class DopplerDesignError(ValueError):
    """The bounded navigation-only design cannot be completed."""


@dataclass(frozen=True, slots=True)
class Candidate:
    doy: int
    target: str
    reference: str
    wrong_orbit: str
    start: int
    stop: int
    separation_from_affine_hz: float
    separation_from_wrong_orbit_hz: float
    controlling_separation_hz: float
    minimum_direct_shift_elevation_deg: float


@dataclass(frozen=True, slots=True)
class AffineCandidate:
    doy: int
    target: str
    reference: str
    start: int
    stop: int
    separation_from_affine_hz: float
    minimum_direct_shift_elevation_deg: float


@dataclass(frozen=True, slots=True)
class DayModel:
    doy: int
    navigation_source: dict[str, object]
    gps_epochs: tuple[datetime, ...]
    utc_epochs: tuple[datetime, ...]
    satellites: tuple[str, ...]
    fractional: dict[tuple[str, str, float], np.ndarray]
    elevation: dict[tuple[str, str, float], np.ndarray]


def expected_navigation_name(
    doy: int,
    allowed_doys: Sequence[int] = CANDIDATE_DOYS,
) -> str:
    if doy not in allowed_doys:
        raise DopplerDesignError("DAY_OUTSIDE_PREDECLARED_SET")
    return f"BRDM00DLR_S_2026{doy:03d}0000_01D_MN.rnx"


def calendar_date_for_doy(doy: int) -> date:
    if not 1 <= doy <= 365:
        raise DopplerDesignError("INVALID_2026_DAY_OF_YEAR")
    return date(2026, 1, 1) + timedelta(days=doy - 1)


def gps_epoch_grid(day: date) -> tuple[datetime, ...]:
    first = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return tuple(
        first + timedelta(seconds=STEP_S * index)
        for index in range(24 * 60 * 2)
    )


def ionosphere_free_doppler_l1_equivalent(
    d1_hz: Sequence[float] | np.ndarray,
    d2_hz: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Map positive-approach RINEX D1/D2 to first-order IF L1 hertz."""
    d1 = np.asarray(d1_hz, dtype=np.float64)
    d2 = np.asarray(d2_hz, dtype=np.float64)
    if d1.shape != d2.shape or not np.all(np.isfinite(d1)) or not np.all(
        np.isfinite(d2)
    ):
        raise DopplerDesignError("INVALID_NATIVE_DOPPLER_ARRAYS")
    alpha, beta = envelope.ionosphere_free_coefficients()
    return alpha * d1 + beta * (envelope.GPS_L1_HZ / envelope.GPS_L2_HZ) * d2


def prefix_affine_projection(
    values: Sequence[float] | np.ndarray,
    split: int = CALIBRATION_RECORDS,
) -> tuple[np.ndarray, tuple[float, float]]:
    array = np.asarray(values, dtype=np.float64)
    if (
        array.ndim != 1
        or array.size != WINDOW_RECORDS
        or not np.all(np.isfinite(array))
        or split <= 1
        or split >= array.size
    ):
        raise DopplerDesignError("INVALID_PREFIX_AFFINE_INPUT")
    elapsed = np.arange(array.size, dtype=np.float64) * STEP_S
    design = np.column_stack((np.ones(split), elapsed[:split]))
    coefficients, *_ = np.linalg.lstsq(design, array[:split], rcond=None)
    residual = array - (coefficients[0] + coefficients[1] * elapsed)
    return residual, (float(coefficients[0]), float(coefficients[1]))


def heldout_non_affine_peak_to_peak(
    left: Sequence[float] | np.ndarray,
    right: Sequence[float] | np.ndarray,
) -> float:
    difference = np.asarray(left, dtype=np.float64) - np.asarray(
        right, dtype=np.float64
    )
    residual, _ = prefix_affine_projection(difference)
    return float(np.ptp(residual[CALIBRATION_RECORDS:]))


def contiguous_segments(mask: Sequence[bool]) -> tuple[tuple[int, int], ...]:
    return screen.contiguous_true_segments(mask)


def window_starts(start: int, stop: int) -> tuple[int, ...]:
    last = stop - WINDOW_RECORDS
    if last < start:
        return ()
    values = list(range(start, last + 1, SEARCH_STRIDE_RECORDS))
    if not values or values[-1] != last:
        values.append(last)
    return tuple(values)


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


def design_manifest() -> dict[str, object]:
    alpha, beta = envelope.ionosphere_free_coefficients()
    return {
        "design_version": DESIGN_VERSION,
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_VALUES_UNOPENED",
        "capability_set": [asdict(review.STATIONS[item]) for item in STATION_IDS],
        "roles": {
            "numeric_detector_development_doy": DEVELOPMENT_DOY,
            "closed_invalid_primary_doy": CLOSED_PRIMARY_DOY,
            "navigation_geometry_candidate_doys": list(CANDIDATE_DOYS),
        },
        "measurement_coordinate": {
            "rinex_observables": list(OBSERVABLES),
            "doppler_sign": RINEX_DOPPLER_SIGN,
            "dual_frequency_l1_equivalent": (
                f"{alpha:.17g}*D1C+({beta:.17g})*(GPS_L1_HZ/GPS_L2_HZ)*D2W"
            ),
            "station_satellite_order": (
                "(KIRU_TARGET-KIRU_REFERENCE)-(MAT1_TARGET-MAT1_REFERENCE)"
            ),
            "nulls": ["PREFIX_AFFINE", "WRONG_JOINTLY_VISIBLE_BROADCAST_ORBIT"],
            "same_epoch_and_visibility_mask_for_all_hypotheses": True,
        },
        "parameters": {
            "grid_step_s": STEP_S,
            "window_records": WINDOW_RECORDS,
            "calibration_records": CALIBRATION_RECORDS,
            "heldout_records": HELDOUT_RECORDS,
            "search_stride_records": SEARCH_STRIDE_RECORDS,
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "independent_station_clock_error_interval_s": [
                -CLOCK_ERROR_S,
                CLOCK_ERROR_S,
            ],
            "clock_envelope_method": (
                "DIRECT_SHIFTED_TRAJECTORIES_WITH_PREFIX_AFFINE_PROJECTION"
            ),
            "gps_minus_utc_s": GPS_MINUS_UTC_S,
        },
        "lineage": {
            "rinex_specification": RINEX_SPECIFICATION_URL,
            "d1c_d2w_header_qualification_receipt_sha256": (
                QUALIFICATION_RECEIPT_SHA256
            ),
            "closed_doy215_primary_outcome_sha256": CLOSED_PRIMARY_OUTCOME_SHA256,
        },
        "forbidden": [
            "DOY214 numeric observation access during geometry selection",
            "DOY215 reuse after measurement invalidation",
            "future observation product access before a new frozen plan",
            "post-measurement target reference window or threshold selection",
            "precise post-pass orbit products",
        ],
    }


def design_manifest_sha256() -> str:
    return sha256(strict_json(design_manifest()).encode("ascii")).hexdigest()


def expansion_manifest() -> dict[str, object]:
    original = design_manifest()
    return {
        "expansion_version": EXPANSION_VERSION,
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_VALUES_UNOPENED",
        "physical_question": (
            "DOES_A_BOUNDED_TWO_WEEK_NAVIGATION_SET_CONTAIN_THREE_FROZEN_"
            "KIRU_MAT1_NATIVE_DOPPLER_WINDOWS_WITH_FULL_WRONG_ORBIT_SUPPORT"
        ),
        "frozen_from": {
            "initial_design_version": DESIGN_VERSION,
            "initial_design_manifest_sha256": design_manifest_sha256(),
            "initial_design_receipt_sha256": INITIAL_DESIGN_RECEIPT_SHA256,
            "initial_outcome": (
                "NO_NATIVE_DOPPLER_GEOMETRY_WITH_FROZEN_NULL_SUPPORT"
            ),
        },
        "candidate_doys": list(EXPANSION_CANDIDATE_DOYS),
        "capability_set": original["capability_set"],
        "measurement_coordinate": original["measurement_coordinate"],
        "parameters": original["parameters"],
        "lineage": original["lineage"],
        "post_result_changes_forbidden": [
            "window length",
            "calibration or heldout records",
            "minimum elevation",
            "clock shifts",
            "null family",
            "capability set",
            "measurement coordinate",
        ],
        "observation_access_forbidden": True,
    }


def expansion_manifest_sha256() -> str:
    return sha256(strict_json(expansion_manifest()).encode("ascii")).hexdigest()


def orbitality_manifest() -> dict[str, object]:
    expanded = expansion_manifest()
    coordinate = dict(expanded["measurement_coordinate"])
    coordinate["nulls"] = ["PREFIX_AFFINE"]
    return {
        "orbitality_version": ORBITALITY_VERSION,
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_VALUES_UNOPENED",
        "physical_question": (
            "CAN_ONE_KIRU_MAT1_NATIVE_DOPPLER_WINDOW_DISCRIMINATE_A_"
            "FROZEN_ORBITAL_CURVE_FROM_A_PREFIX_CALIBRATED_AFFINE_NULL"
        ),
        "claim_ceiling": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "specific_orbit_claim_authorized": False,
        "wrong_orbit_null_present": False,
        "reason_for_narrower_claim": (
            "ORBITALITY_AND_SPECIFIC_ORBIT_IDENTITY_ARE_DISTINCT_CLAIM_LADDER_STEPS"
        ),
        "frozen_from": {
            "expansion_version": EXPANSION_VERSION,
            "expansion_manifest_sha256": expansion_manifest_sha256(),
            "expansion_receipt_sha256": EXPANSION_RECEIPT_SHA256,
            "expansion_outcome": (
                "NO_NATIVE_DOPPLER_GEOMETRY_SHORTLIST_IN_EXPANDED_SET"
            ),
        },
        "candidate_doys": list(EXPANSION_CANDIDATE_DOYS),
        "capability_set": expanded["capability_set"],
        "measurement_coordinate": coordinate,
        "parameters": expanded["parameters"],
        "selection_rule": (
            "ONE_BEST_POSITIVE_DIRECT_CLOCK_MARGIN_WINDOW_PER_DAY_THEN_TOP_THREE"
        ),
        "post_result_changes_forbidden": expanded["post_result_changes_forbidden"],
        "observation_access_forbidden": True,
    }


def orbitality_manifest_sha256() -> str:
    return sha256(strict_json(orbitality_manifest()).encode("ascii")).hexdigest()


def validate_navigation_inputs(
    paths: Sequence[Path],
    candidate_doys: Sequence[int] = CANDIDATE_DOYS,
) -> dict[int, Path]:
    if len(paths) != len(candidate_doys):
        raise DopplerDesignError("EXACT_PREDECLARED_NAVIGATION_SET_REQUIRED")
    by_day: dict[int, Path] = {}
    for raw_path in paths:
        path = Path(raw_path)
        matching = [
            doy
            for doy in candidate_doys
            if path.name == expected_navigation_name(doy, candidate_doys)
        ]
        if len(matching) != 1:
            raise DopplerDesignError("NAVIGATION_PRODUCT_OUTSIDE_PREDECLARED_SET")
        doy = matching[0]
        if doy in by_day:
            raise DopplerDesignError("DUPLICATE_NAVIGATION_DAY")
        if not path.is_file():
            raise DopplerDesignError("NAVIGATION_PRODUCT_MISSING")
        by_day[doy] = path
    if set(by_day) != set(candidate_doys):
        raise DopplerDesignError("INCOMPLETE_NAVIGATION_DAY_SET")
    return by_day


def broadcast_positions_with_gaps(
    records: Sequence[screen.GpsEphemeris],
    epochs: Sequence[datetime],
) -> np.ndarray:
    positions = np.full((len(epochs), 3), np.nan, dtype=np.float64)
    for index, epoch in enumerate(epochs):
        try:
            ephemeris = screen.select_ephemeris(records, epoch)
        except screen.GnssDoubleDifferenceError:
            continue
        positions[index] = screen.broadcast_ecef(ephemeris, epoch)
    return positions


def compile_day_model(
    doy: int,
    path: Path,
    allowed_doys: Sequence[int] = CANDIDATE_DOYS,
) -> DayModel:
    if path.name != expected_navigation_name(doy, allowed_doys):
        raise DopplerDesignError("NAVIGATION_IDENTITY_MISMATCH")
    records = screen.parse_gps_navigation(path)
    satellites = tuple(sorted(records))
    if len(satellites) < 4:
        raise DopplerDesignError("TOO_FEW_HEALTHY_GPS_SATELLITES")
    gps_epochs = gps_epoch_grid(calendar_date_for_doy(doy))
    utc_epochs = tuple(
        epoch - timedelta(seconds=GPS_MINUS_UTC_S) for epoch in gps_epochs
    )
    station_ecef = {
        station_id: screen.station_to_ecef(review.STATIONS[station_id])
        for station_id in STATION_IDS
    }
    fractional: dict[tuple[str, str, float], np.ndarray] = {}
    elevation: dict[tuple[str, str, float], np.ndarray] = {}
    for satellite in satellites:
        for shift_s in CLOCK_SHIFTS_S:
            shifted = tuple(
                epoch + timedelta(seconds=shift_s) for epoch in utc_epochs
            )
            positions = broadcast_positions_with_gaps(records[satellite], shifted)
            for station_id in STATION_IDS:
                station = review.STATIONS[station_id]
                fractional[(station_id, satellite, shift_s)] = screen.fractional_doppler(
                    positions, station_ecef[station_id], STEP_S
                )
                elevation[(station_id, satellite, shift_s)] = screen.elevation_deg(
                    positions, station, station_ecef[station_id]
                )
    gzip_path = path.with_name(f"{path.name}.gz")
    return DayModel(
        doy=doy,
        navigation_source={
            "name": path.name,
            "url": (
                f"https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/{doy:03d}/"
                f"{path.name}.gz"
            ),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
            "compressed_bytes": gzip_path.stat().st_size if gzip_path.is_file() else None,
            "compressed_sha256": file_sha256(gzip_path) if gzip_path.is_file() else None,
            "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
        },
        gps_epochs=gps_epochs,
        utc_epochs=utc_epochs,
        satellites=satellites,
        fractional=fractional,
        elevation=elevation,
    )


def robust_visibility(model: DayModel, satellite: str) -> np.ndarray:
    visible = np.ones(len(model.utc_epochs), dtype=bool)
    for station_id in STATION_IDS:
        for shift_s in CLOCK_SHIFTS_S:
            visible &= (
                model.elevation[(station_id, satellite, shift_s)]
                >= MINIMUM_ELEVATION_DEG
            )
    return visible


def network_curve(
    model: DayModel,
    target: str,
    reference: str,
    left_shift_s: float = 0.0,
    right_shift_s: float = 0.0,
) -> np.ndarray:
    left, right = STATION_IDS
    return envelope.GPS_L1_HZ * (
        (
            model.fractional[(left, target, left_shift_s)]
            - model.fractional[(left, reference, left_shift_s)]
        )
        - (
            model.fractional[(right, target, right_shift_s)]
            - model.fractional[(right, reference, right_shift_s)]
        )
    )


def minimum_shifted_elevation(
    model: DayModel,
    satellites: Sequence[str],
    feature: slice,
) -> float:
    return float(
        min(
            np.min(model.elevation[(station_id, satellite, shift_s)][feature])
            for satellite in satellites
            for station_id in STATION_IDS
            for shift_s in CLOCK_SHIFTS_S
        )
    )


def pair_curve(
    curves: dict[tuple[str, str], np.ndarray],
    target: str,
    reference: str,
) -> np.ndarray:
    if target < reference:
        return curves[(target, reference)]
    return -curves[(reference, target)]


def raw_day_candidates(model: DayModel) -> list[Candidate]:
    visibility = {
        satellite: robust_visibility(model, satellite)
        for satellite in model.satellites
    }
    curves = {
        (target, reference): network_curve(model, target, reference)
        for target_index, target in enumerate(model.satellites)
        for reference in model.satellites[target_index + 1 :]
    }
    candidates: list[Candidate] = []
    zero = np.zeros(WINDOW_RECORDS, dtype=np.float64)
    for target_index, target in enumerate(model.satellites):
        for reference in model.satellites[target_index + 1 :]:
            common = visibility[target] & visibility[reference]
            for segment_start, segment_stop in contiguous_segments(common):
                for start in window_starts(segment_start, segment_stop):
                    stop = start + WINDOW_RECORDS
                    feature = slice(start, stop)
                    nominal = pair_curve(curves, target, reference)[feature]
                    affine = heldout_non_affine_peak_to_peak(nominal, zero)
                    alternatives: list[tuple[float, str]] = []
                    for alternative in model.satellites:
                        if alternative in (target, reference):
                            continue
                        if not np.all(visibility[alternative][feature]):
                            continue
                        separation = heldout_non_affine_peak_to_peak(
                            nominal,
                            pair_curve(curves, alternative, reference)[feature],
                        )
                        alternatives.append((separation, alternative))
                    if not alternatives:
                        continue
                    wrong_separation, wrong_orbit = min(
                        alternatives, key=lambda item: (item[0], item[1])
                    )
                    controlling = min(affine, wrong_separation)
                    candidates.append(
                        Candidate(
                            doy=model.doy,
                            target=target,
                            reference=reference,
                            wrong_orbit=wrong_orbit,
                            start=start,
                            stop=stop,
                            separation_from_affine_hz=float(affine),
                            separation_from_wrong_orbit_hz=float(wrong_separation),
                            controlling_separation_hz=float(controlling),
                            minimum_direct_shift_elevation_deg=minimum_shifted_elevation(
                                model,
                                (target, reference, wrong_orbit),
                                feature,
                            ),
                        )
                    )
    candidates.sort(
        key=lambda row: (
            -row.controlling_separation_hz,
            row.start,
            row.target,
            row.reference,
        )
    )
    return candidates


def direct_clock_envelope_hz(
    model: DayModel,
    target: str,
    reference: str,
    feature: slice,
) -> tuple[float, tuple[float, float]]:
    nominal = network_curve(model, target, reference)[feature]
    maximum = -1.0
    controlling = (0.0, 0.0)
    for left_shift_s in CLOCK_SHIFTS_S:
        for right_shift_s in CLOCK_SHIFTS_S:
            shifted = network_curve(
                model, target, reference, left_shift_s, right_shift_s
            )[feature]
            value = heldout_non_affine_peak_to_peak(shifted, nominal)
            if value > maximum:
                maximum = value
                controlling = (left_shift_s, right_shift_s)
    return float(maximum), controlling


def audit_candidate(model: DayModel, candidate: Candidate) -> dict[str, object]:
    feature = slice(candidate.start, candidate.stop)
    nominal_timing, nominal_offsets = direct_clock_envelope_hz(
        model, candidate.target, candidate.reference, feature
    )
    wrong_timing, wrong_offsets = direct_clock_envelope_hz(
        model, candidate.wrong_orbit, candidate.reference, feature
    )
    affine_remaining = candidate.separation_from_affine_hz - nominal_timing
    wrong_pair_envelope = nominal_timing + wrong_timing
    wrong_remaining = candidate.separation_from_wrong_orbit_hz - wrong_pair_envelope
    remaining = min(affine_remaining, wrong_remaining)
    gps_start = model.gps_epochs[candidate.start]
    gps_stop = model.gps_epochs[candidate.stop - 1]
    utc_start = model.utc_epochs[candidate.start]
    utc_stop = model.utc_epochs[candidate.stop - 1]
    return {
        "doy": candidate.doy,
        "target": candidate.target,
        "reference": candidate.reference,
        "start_observation_epoch_gps": (
            f"{gps_start.isoformat(timespec='seconds').replace('+00:00', '')} GPS"
        ),
        "stop_observation_epoch_gps": (
            f"{gps_stop.isoformat(timespec='seconds').replace('+00:00', '')} GPS"
        ),
        "start_model_epoch_utc": screen.format_utc(utc_start),
        "stop_model_epoch_utc": screen.format_utc(utc_stop),
        "records": WINDOW_RECORDS,
        "duration_s": (WINDOW_RECORDS - 1) * STEP_S,
        "calibration_records": CALIBRATION_RECORDS,
        "heldout_records": HELDOUT_RECORDS,
        "minimum_elevation_across_stations_and_clock_shifts_deg": (
            candidate.minimum_direct_shift_elevation_deg
        ),
        "prefix_affine_null": {
            "heldout_non_affine_peak_to_peak_hz": (
                candidate.separation_from_affine_hz
            )
        },
        "wrong_orbit_null": {
            "satellite": candidate.wrong_orbit,
            "heldout_non_affine_peak_to_peak_hz": (
                candidate.separation_from_wrong_orbit_hz
            ),
        },
        "controlling_geometry_separation_hz": candidate.controlling_separation_hz,
        "direct_clock_envelope": {
            "nominal_model_heldout_peak_to_peak_hz": nominal_timing,
            "nominal_controlling_station_offsets_s": list(nominal_offsets),
            "wrong_orbit_model_heldout_peak_to_peak_hz": wrong_timing,
            "wrong_orbit_controlling_station_offsets_s": list(wrong_offsets),
            "wrong_orbit_pairwise_bound_hz": wrong_pair_envelope,
        },
        "remaining_after_direct_clock_envelope_hz": float(remaining),
        "negative_result_interpretable": False,
        "reason_negative_not_yet_interpretable": (
            "NATIVE_DOPPLER_MEASUREMENT_ENVELOPE_NOT_YET_DEVELOPED"
        ),
    }


def select_day_candidate(model: DayModel) -> dict[str, object] | None:
    audited = [audit_candidate(model, candidate) for candidate in raw_day_candidates(model)]
    audited.sort(
        key=lambda row: (
            -float(row["remaining_after_direct_clock_envelope_hz"]),
            str(row["start_observation_epoch_gps"]),
            str(row["target"]),
            str(row["reference"]),
        )
    )
    return audited[0] if audited else None


def raw_affine_day_candidates(model: DayModel) -> list[AffineCandidate]:
    visibility = {
        satellite: robust_visibility(model, satellite)
        for satellite in model.satellites
    }
    zero = np.zeros(WINDOW_RECORDS, dtype=np.float64)
    candidates: list[AffineCandidate] = []
    for target_index, target in enumerate(model.satellites):
        for reference in model.satellites[target_index + 1 :]:
            common = visibility[target] & visibility[reference]
            curve = network_curve(model, target, reference)
            for segment_start, segment_stop in contiguous_segments(common):
                for start in window_starts(segment_start, segment_stop):
                    stop = start + WINDOW_RECORDS
                    feature = slice(start, stop)
                    separation = heldout_non_affine_peak_to_peak(
                        curve[feature], zero
                    )
                    candidates.append(
                        AffineCandidate(
                            doy=model.doy,
                            target=target,
                            reference=reference,
                            start=start,
                            stop=stop,
                            separation_from_affine_hz=separation,
                            minimum_direct_shift_elevation_deg=minimum_shifted_elevation(
                                model,
                                (target, reference),
                                feature,
                            ),
                        )
                    )
    candidates.sort(
        key=lambda row: (
            -row.separation_from_affine_hz,
            row.start,
            row.target,
            row.reference,
        )
    )
    return candidates


def audit_affine_candidate(
    model: DayModel,
    candidate: AffineCandidate,
) -> dict[str, object]:
    feature = slice(candidate.start, candidate.stop)
    timing, offsets = direct_clock_envelope_hz(
        model,
        candidate.target,
        candidate.reference,
        feature,
    )
    remaining = candidate.separation_from_affine_hz - timing
    gps_start = model.gps_epochs[candidate.start]
    gps_stop = model.gps_epochs[candidate.stop - 1]
    utc_start = model.utc_epochs[candidate.start]
    utc_stop = model.utc_epochs[candidate.stop - 1]
    return {
        "doy": candidate.doy,
        "target": candidate.target,
        "reference": candidate.reference,
        "start_observation_epoch_gps": (
            f"{gps_start.isoformat(timespec='seconds').replace('+00:00', '')} GPS"
        ),
        "stop_observation_epoch_gps": (
            f"{gps_stop.isoformat(timespec='seconds').replace('+00:00', '')} GPS"
        ),
        "start_model_epoch_utc": screen.format_utc(utc_start),
        "stop_model_epoch_utc": screen.format_utc(utc_stop),
        "records": WINDOW_RECORDS,
        "duration_s": (WINDOW_RECORDS - 1) * STEP_S,
        "calibration_records": CALIBRATION_RECORDS,
        "heldout_records": HELDOUT_RECORDS,
        "minimum_elevation_across_stations_and_clock_shifts_deg": (
            candidate.minimum_direct_shift_elevation_deg
        ),
        "prefix_affine_null": {
            "heldout_non_affine_peak_to_peak_hz": (
                candidate.separation_from_affine_hz
            )
        },
        "direct_clock_envelope": {
            "heldout_peak_to_peak_hz": timing,
            "controlling_station_offsets_s": list(offsets),
            "basis": "DIRECT_SHIFTED_TRAJECTORIES_NOT_LOCAL_SLOPE",
        },
        "remaining_after_direct_clock_envelope_hz": float(remaining),
        "instrumental_envelope_assessed": False,
        "negative_result_interpretable": False,
        "reason_negative_not_yet_interpretable": (
            "NATIVE_DOPPLER_MEASUREMENT_ENVELOPE_NOT_YET_DEVELOPED"
        ),
    }


def select_affine_day_candidate(model: DayModel) -> dict[str, object] | None:
    audited = [
        audit_affine_candidate(model, candidate)
        for candidate in raw_affine_day_candidates(model)
    ]
    audited.sort(
        key=lambda row: (
            -float(row["remaining_after_direct_clock_envelope_hz"]),
            str(row["start_observation_epoch_gps"]),
            str(row["target"]),
            str(row["reference"]),
        )
    )
    return audited[0] if audited else None


def day_continuity_diagnostic(model: DayModel) -> dict[str, object]:
    visibility = {
        satellite: robust_visibility(model, satellite)
        for satellite in model.satellites
    }

    def ranked(group_size: int) -> list[tuple[int, tuple[str, ...]]]:
        rows = []
        for satellites in combinations(model.satellites, group_size):
            common = np.logical_and.reduce([visibility[item] for item in satellites])
            longest = max(
                (stop - start for start, stop in contiguous_segments(common)),
                default=0,
            )
            rows.append((longest, satellites))
        rows.sort(key=lambda item: (-item[0], item[1]))
        return rows

    pairs = ranked(2)
    triples = ranked(3)
    pair_max, pair_satellites = pairs[0]
    triple_max, triple_satellites = triples[0]
    return {
        "doy": model.doy,
        "required_window_records": WINDOW_RECORDS,
        "maximum_two_satellite_continuity_records": pair_max,
        "controlling_two_satellite_set": list(pair_satellites),
        "two_satellite_sets_meeting_window": sum(
            records >= WINDOW_RECORDS for records, _ in pairs
        ),
        "maximum_three_satellite_continuity_records": triple_max,
        "controlling_three_satellite_set": list(triple_satellites),
        "three_satellite_sets_meeting_window": sum(
            records >= WINDOW_RECORDS for records, _ in triples
        ),
        "state": (
            "GEOMETRY_ADMISSIBLE_FOR_WRONG_ORBIT_NULL"
            if triple_max >= WINDOW_RECORDS
            else "NO_THREE_SATELLITE_ROBUST_WINDOW_FOR_FROZEN_LENGTH"
        ),
    }


def design_forward(paths: Sequence[Path]) -> dict[str, object]:
    by_day = validate_navigation_inputs(paths)
    models = {
        doy: compile_day_model(doy, by_day[doy]) for doy in CANDIDATE_DOYS
    }
    selected = [select_day_candidate(models[doy]) for doy in CANDIDATE_DOYS]
    diagnostics = [day_continuity_diagnostic(models[doy]) for doy in CANDIDATE_DOYS]
    shortlist = [item for item in selected if item is not None]
    shortlist.sort(
        key=lambda row: (
            -float(row["remaining_after_direct_clock_envelope_hz"]),
            int(row["doy"]),
        )
    )
    roles = ("primary_candidate", "reserve_1", "reserve_2")
    for rank, (role, item) in enumerate(zip(roles, shortlist), start=1):
        item["prospective_role"] = role
        item["geometry_rank"] = rank
    positive = bool(
        len(shortlist) == 3
        and all(
            float(item["remaining_after_direct_clock_envelope_hz"]) > 0.0
            for item in shortlist
        )
    )
    result = {
        "design_version": DESIGN_VERSION,
        "design_manifest_sha256": design_manifest_sha256(),
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_VALUES_UNOPENED",
        "physical_question": (
            "CAN_NATIVE_DUAL_FREQUENCY_DOPPLER_SUPPORT_A_FUTURE_HELDOUT_"
            "KIRU_MAT1_ORBITAL_VERSUS_FROZEN_NULL_TEST"
        ),
        "navigation_sources": [
            models[doy].navigation_source for doy in CANDIDATE_DOYS
        ],
        "capability_set": list(STATION_IDS),
        "observable": design_manifest()["measurement_coordinate"],
        "shortlist": shortlist,
        "selection_stage": "ROBUST_JOINT_VISIBILITY_FOR_WRONG_ORBIT_NULL",
        "instrumental_assessment_reached": False,
        "day_admission_diagnostics": diagnostics,
        "measurement_envelope_status": "OPEN_UNTIL_DOY214_NUMERIC_DEVELOPMENT",
        "measurement_access": {
            "observation_products_opened": 0,
            "observation_bytes_accessed": 0,
            "observation_epochs_decoded": 0,
            "doppler_values_decoded": 0,
            "carrier_phase_values_decoded": 0,
        },
        "authority": {
            "development_numeric_access_authorized": False,
            "future_primary_access_authorized": False,
            "closed_doy215_reopened": False,
            "prospective_plan_frozen": False,
        },
        "next_exact_blocker": (
            "SEPARATE_AUTHORITY_FOR_DOY214_NATIVE_DOPPLER_NUMERIC_DEVELOPMENT"
            if positive
            else "PREDECLARED_NAVIGATION_SET_HAS_NO_380_EPOCH_THREE_SATELLITE_ROBUST_WINDOW"
        ),
        "outcome": (
            "NATIVE_DOPPLER_GEOMETRY_SHORTLIST_READY"
            if positive
            else "NO_NATIVE_DOPPLER_GEOMETRY_WITH_FROZEN_NULL_SUPPORT"
        ),
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def design_expansion(paths: Sequence[Path]) -> dict[str, object]:
    by_day = validate_navigation_inputs(paths, EXPANSION_CANDIDATE_DOYS)
    models = {
        doy: compile_day_model(
            doy,
            by_day[doy],
            EXPANSION_CANDIDATE_DOYS,
        )
        for doy in EXPANSION_CANDIDATE_DOYS
    }
    day_winners = {
        doy: select_day_candidate(models[doy]) for doy in EXPANSION_CANDIDATE_DOYS
    }
    diagnostics = [
        day_continuity_diagnostic(models[doy]) for doy in EXPANSION_CANDIDATE_DOYS
    ]
    positive = [
        candidate
        for candidate in day_winners.values()
        if candidate is not None
        and float(candidate["remaining_after_direct_clock_envelope_hz"]) > 0.0
    ]
    positive.sort(
        key=lambda row: (
            -float(row["remaining_after_direct_clock_envelope_hz"]),
            int(row["doy"]),
        )
    )
    shortlist = positive[:3]
    roles = ("primary_candidate", "reserve_1", "reserve_2")
    for rank, (role, item) in enumerate(zip(roles, shortlist), start=1):
        item["prospective_role"] = role
        item["geometry_rank"] = rank
    summaries = []
    for doy in EXPANSION_CANDIDATE_DOYS:
        candidate = day_winners[doy]
        if candidate is None:
            summaries.append({"doy": doy, "candidate_found": False})
            continue
        summaries.append(
            {
                "doy": doy,
                "candidate_found": True,
                "target": candidate["target"],
                "reference": candidate["reference"],
                "wrong_orbit": candidate["wrong_orbit_null"]["satellite"],
                "start_observation_epoch_gps": candidate[
                    "start_observation_epoch_gps"
                ],
                "remaining_after_direct_clock_envelope_hz": candidate[
                    "remaining_after_direct_clock_envelope_hz"
                ],
            }
        )
    admitted = len(shortlist) == 3
    result = {
        "expansion_version": EXPANSION_VERSION,
        "expansion_manifest_sha256": expansion_manifest_sha256(),
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_VALUES_UNOPENED",
        "candidate_doys": list(EXPANSION_CANDIDATE_DOYS),
        "navigation_sources": [
            models[doy].navigation_source for doy in EXPANSION_CANDIDATE_DOYS
        ],
        "capability_set": list(STATION_IDS),
        "observable": expansion_manifest()["measurement_coordinate"],
        "day_admission_diagnostics": diagnostics,
        "day_candidate_summaries": summaries,
        "shortlist": shortlist,
        "measurement_envelope_status": "OPEN_UNTIL_DOY214_NUMERIC_DEVELOPMENT",
        "instrumental_assessment_reached": False,
        "measurement_access": {
            "observation_products_opened": 0,
            "observation_bytes_accessed": 0,
            "observation_epochs_decoded": 0,
            "doppler_values_decoded": 0,
            "carrier_phase_values_decoded": 0,
        },
        "authority": {
            "development_numeric_access_authorized": False,
            "future_primary_access_authorized": False,
            "closed_doy215_reopened": False,
            "prospective_plan_frozen": False,
        },
        "next_exact_blocker": (
            "SEPARATE_AUTHORITY_FOR_DOY214_NATIVE_DOPPLER_NUMERIC_DEVELOPMENT"
            if admitted
            else "EXPANDED_NAVIGATION_SET_HAS_FEWER_THAN_THREE_ADMISSIBLE_WINDOWS"
        ),
        "outcome": (
            "NATIVE_DOPPLER_GEOMETRY_SHORTLIST_READY"
            if admitted
            else "NO_NATIVE_DOPPLER_GEOMETRY_SHORTLIST_IN_EXPANDED_SET"
        ),
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def day_pair_diagnostic(model: DayModel) -> dict[str, object]:
    visibility = {
        satellite: robust_visibility(model, satellite)
        for satellite in model.satellites
    }
    rows = []
    for target, reference in combinations(model.satellites, 2):
        common = visibility[target] & visibility[reference]
        longest = max(
            (stop - start for start, stop in contiguous_segments(common)),
            default=0,
        )
        rows.append((longest, target, reference))
    rows.sort(key=lambda item: (-item[0], item[1], item[2]))
    longest, target, reference = rows[0]
    return {
        "doy": model.doy,
        "required_window_records": WINDOW_RECORDS,
        "maximum_two_satellite_continuity_records": longest,
        "controlling_two_satellite_set": [target, reference],
        "two_satellite_sets_meeting_window": sum(
            records >= WINDOW_RECORDS for records, _, _ in rows
        ),
        "state": (
            "GEOMETRY_ADMISSIBLE_FOR_AFFINE_ONLY_ORBITALITY"
            if longest >= WINDOW_RECORDS
            else "NO_TWO_SATELLITE_ROBUST_WINDOW_FOR_FROZEN_LENGTH"
        ),
    }


def design_orbitality(paths: Sequence[Path]) -> dict[str, object]:
    by_day = validate_navigation_inputs(paths, EXPANSION_CANDIDATE_DOYS)
    models = {
        doy: compile_day_model(
            doy,
            by_day[doy],
            EXPANSION_CANDIDATE_DOYS,
        )
        for doy in EXPANSION_CANDIDATE_DOYS
    }
    day_winners = {
        doy: select_affine_day_candidate(models[doy])
        for doy in EXPANSION_CANDIDATE_DOYS
    }
    positive = [
        candidate
        for candidate in day_winners.values()
        if candidate is not None
        and float(candidate["remaining_after_direct_clock_envelope_hz"]) > 0.0
    ]
    positive.sort(
        key=lambda row: (
            -float(row["remaining_after_direct_clock_envelope_hz"]),
            int(row["doy"]),
        )
    )
    shortlist = positive[:3]
    roles = ("primary_candidate", "reserve_1", "reserve_2")
    for rank, (role, item) in enumerate(zip(roles, shortlist), start=1):
        item["prospective_role"] = role
        item["geometry_rank"] = rank
    summaries = []
    for doy in EXPANSION_CANDIDATE_DOYS:
        candidate = day_winners[doy]
        if candidate is None:
            summaries.append({"doy": doy, "candidate_found": False})
            continue
        summaries.append(
            {
                "doy": doy,
                "candidate_found": True,
                "target": candidate["target"],
                "reference": candidate["reference"],
                "start_observation_epoch_gps": candidate[
                    "start_observation_epoch_gps"
                ],
                "affine_separation_hz": candidate["prefix_affine_null"][
                    "heldout_non_affine_peak_to_peak_hz"
                ],
                "direct_clock_envelope_hz": candidate["direct_clock_envelope"][
                    "heldout_peak_to_peak_hz"
                ],
                "remaining_after_direct_clock_envelope_hz": candidate[
                    "remaining_after_direct_clock_envelope_hz"
                ],
            }
        )
    admitted = len(shortlist) == 3
    result = {
        "orbitality_version": ORBITALITY_VERSION,
        "orbitality_manifest_sha256": orbitality_manifest_sha256(),
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_VALUES_UNOPENED",
        "physical_question": orbitality_manifest()["physical_question"],
        "claim_ceiling": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "specific_orbit_claim_authorized": False,
        "wrong_orbit_null_present": False,
        "candidate_doys": list(EXPANSION_CANDIDATE_DOYS),
        "navigation_sources": [
            models[doy].navigation_source for doy in EXPANSION_CANDIDATE_DOYS
        ],
        "capability_set": list(STATION_IDS),
        "observable": orbitality_manifest()["measurement_coordinate"],
        "day_admission_diagnostics": [
            day_pair_diagnostic(models[doy]) for doy in EXPANSION_CANDIDATE_DOYS
        ],
        "day_candidate_summaries": summaries,
        "shortlist": shortlist,
        "measurement_envelope_status": "OPEN_UNTIL_DOY214_NUMERIC_DEVELOPMENT",
        "instrumental_assessment_reached": False,
        "measurement_access": {
            "observation_products_opened": 0,
            "observation_bytes_accessed": 0,
            "observation_epochs_decoded": 0,
            "doppler_values_decoded": 0,
            "carrier_phase_values_decoded": 0,
        },
        "authority": {
            "development_numeric_access_authorized": False,
            "future_primary_access_authorized": False,
            "closed_doy215_reopened": False,
            "prospective_plan_frozen": False,
        },
        "next_exact_blocker": (
            "SEPARATE_AUTHORITY_FOR_DOY214_NATIVE_DOPPLER_NUMERIC_DEVELOPMENT"
            if admitted
            else "AFFINE_ONLY_ORBITALITY_SET_HAS_FEWER_THAN_THREE_POSITIVE_WINDOWS"
        ),
        "outcome": (
            "NATIVE_DOPPLER_ORBITALITY_GEOMETRY_SHORTLIST_READY"
            if admitted
            else "NO_NATIVE_DOPPLER_ORBITALITY_GEOMETRY_SHORTLIST"
        ),
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--expanded", action="store_true")
    mode.add_argument("--orbitality", action="store_true")
    parser.add_argument("navigation", nargs="+", type=Path)
    args = parser.parse_args()
    if args.orbitality:
        result = design_orbitality(args.navigation)
    elif args.expanded:
        result = design_expansion(args.navigation)
    else:
        result = design_forward(args.navigation)
    print(strict_json(result))


if __name__ == "__main__":
    main()
