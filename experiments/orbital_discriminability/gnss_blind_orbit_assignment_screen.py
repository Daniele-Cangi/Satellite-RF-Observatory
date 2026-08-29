"""Observation-blind screen for one bounded GPS orbit-assignment challenge.

Only five predeclared broadcast-navigation products enter this compiler.  It
has no observation locator, header, decoder, measurement value or scoring
input.  The output may shortlist one difficult geometry; it cannot freeze or
execute a prospective measurement.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_amc_observer_primary_plan as amc,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)


SCREEN_VERSION: Final = "gnss-bounded-blind-orbit-assignment-screen-v1"
RECEIPT_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_SCREEN_RECEIPT.json"
SCOPE_NAME: Final = "GNSS_BLIND_ORBIT_ASSIGNMENT_SCOPE.md"
SCOPE_COMMIT: Final = "00bb74da2ad2a494c2e6bf0b92d45a124c46680f"
SCOPE_SHA256: Final = (
    "2b57ac1b19f41cba70585bae1bf09b0834349872d5a3db540ca5aac1d2cd3ebf"
)

OUTCOME_SHORTLISTED: Final = "BLIND_ASSIGNMENT_GEOMETRY_SHORTLISTED"
OUTCOME_NONE: Final = "NO_DIFFICULT_FAMILY_WITH_POSITIVE_MARGIN"

TARGET: Final = "G22"
REFERENCE: Final = "G30"
STEP_S: Final = 30.0
RAW_EPOCHS: Final = 139
PREFIX_EPOCHS: Final = 79
HELDOUT_EPOCHS: Final = 60
MAXIMUM_EVENT_TIME_ERROR_S: Final = 15.0
MINIMUM_ELEVATION_DEG: Final = 15.0
ALTERNATIVE_COUNT: Final = 4
PAIRWISE_GUARD_M: Final = amc.REVISED_PAIRWISE_GUARD_M
ROBUST_SEPARATION_M: Final = 2.0 * PAIRWISE_GUARD_M

STATION: Final = geometry.Station(
    "AMC400USA",
    amc.STATION_LATITUDE_DEG,
    amc.STATION_LONGITUDE_DEG,
    amc.STATION_HEIGHT_M,
    "EXISTING_AMC_QUALIFIED_TIME_REFERENCE",
    "SEPT_POLARX5TR_3013929_5.6.0",
    "TPSCR.G5C_NONE_1364-10065",
    "ROBOT",
    "AMC400USA_40472S005",
    "https://network.igs.org/AMC400USA",
)

NAVIGATION_CANDIDATES: Final = (
    navigation.NavigationCandidate(
        224,
        "2026-08-12",
        "brdc2240.26n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2026/224/brdc2240.26n.gz",
        "2.11",
        "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
    ),
    navigation.NavigationCandidate(
        225,
        "2026-08-13",
        "brdc2250.26n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2026/225/brdc2250.26n.gz",
        "2.11",
        "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
    ),
    navigation.NavigationCandidate(
        226,
        "2026-08-14",
        "brdc2260.26n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2026/226/brdc2260.26n.gz",
        "2.11",
        "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
    ),
    navigation.NavigationCandidate(
        227,
        "2026-08-15",
        "brdc2270.26n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2026/227/brdc2270.26n.gz",
        "2.11",
        "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
    ),
    navigation.NavigationCandidate(
        228,
        "2026-08-16",
        "brdc2280.26n.gz",
        "https://geodesy.noaa.gov/corsdata/rinex/2026/228/brdc2280.26n.gz",
        "2.11",
        "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
    ),
)


class BlindAssignmentScreenError(ValueError):
    """A frozen scope, orbit authority or numerical invariant changed."""


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


def dependency_versions() -> dict[str, str]:
    return {
        "numpy": importlib.metadata.version("numpy"),
        "python": platform.python_version(),
    }


def validate_scope(root: Path) -> dict[str, str]:
    path = Path(root) / SCOPE_NAME
    if not path.is_file() or canonical_sha256(path) != SCOPE_SHA256:
        raise BlindAssignmentScreenError("FROZEN_SCOPE_CHANGED")
    if tuple(candidate.doy for candidate in NAVIGATION_CANDIDATES) != (
        224,
        225,
        226,
        227,
        228,
    ):
        raise BlindAssignmentScreenError("NAVIGATION_DAY_SCOPE_CHANGED")
    if len(NAVIGATION_CANDIDATES) != 5:
        raise BlindAssignmentScreenError("NAVIGATION_SCOPE_NOT_FIVE_DAYS")
    return {
        "filename": SCOPE_NAME,
        "canonical_sha256": SCOPE_SHA256,
        "scope_commit": SCOPE_COMMIT,
    }


def manifest(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    result = {
        "schema": "gnss-blind-orbit-assignment-screen-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "scope": validate_scope(base),
        "physical_question": (
            "CAN_G22_RELATIVE_TO_G30_BE_DISTINGUISHED_FROM_FOUR_CLOSE_"
            "PREFIX_CALIBRATED_GPS_ORBIT_ALTERNATIVES"
        ),
        "new_information": (
            "WHETHER_ONE_DIFFICULT_BUT_PHYSICALLY_DISCRIMINABLE_BOUNDED_"
            "ORBIT_ASSIGNMENT_PROBLEM_EXISTS_BEFORE_OBSERVATION_SELECTION"
        ),
        "why_existing_experiments_cannot_answer": (
            "PIE_AND_AMC_TESTED_FORWARD_G22_WITH_THREE_LARGE_SEPARATION_"
            "WRONG_ORBITS_NOT_A_CLOSE_BLIND_ASSIGNMENT_FAMILY"
        ),
        "minimum_experiment": (
            "FIVE_PREDECLARED_BROADCAST_NAVIGATION_DAYS_ONE_AMC_GEOMETRY_"
            "FIVE_ORBITAL_HYPOTHESES_ONE_AFFINE_NULL_ZERO_OBSERVATIONS"
        ),
        "stop_condition": (
            "STOP_BEFORE_OBSERVATION_DISCOVERY_IF_THE_FOUR_NEAREST_VISIBLE_"
            "ALTERNATIVES_OR_AFFINE_NULL_FAIL_THE_DOUBLE_GUARD_RULE"
        ),
        "observer": asdict(STATION),
        "navigation": [asdict(candidate) for candidate in NAVIGATION_CANDIDATES],
        "population": {
            "system": "GPS",
            "target": TARGET,
            "reference": REFERENCE,
            "alternatives": "ALL_HEALTHY_G01_TO_G32_EXCEPT_G22_AND_G30",
            "family_size": 1 + ALTERNATIVE_COUNT,
            "selection": "FOUR_SMALLEST_HELDOUT_SEPARATIONS_THEN_PRN",
            "nonpositive_alternative_may_be_discarded": False,
        },
        "partition": {
            "cadence_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "prefix_epochs": PREFIX_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "anchor_index": 0,
        },
        "visibility": {
            "minimum_elevation_deg": MINIMUM_ELEVATION_DEG,
            "direct_common_time_offsets_s": [
                -MAXIMUM_EVENT_TIME_ERROR_S,
                0.0,
                MAXIMUM_EVENT_TIME_ERROR_S,
            ],
            "complete_window_required": True,
            "required_for_target_reference_and_all_four_alternatives": True,
        },
        "nuisance": {
            "per_hypothesis_parameters": ["PREFIX_CONSTANT", "PREFIX_RATE"],
            "fit_indices_inclusive": [0, PREFIX_EPOCHS - 1],
            "heldout_refit": False,
            "free_time_phase": False,
            "time_warp": False,
            "candidate_dependent_complexity": False,
        },
        "guard": {
            "unchanged_amc_pairwise_decision_guard_m": PAIRWISE_GUARD_M,
            "robust_minimum_separation_m": ROBUST_SEPARATION_M,
            "rule": "SEPARATION_AT_LEAST_TWO_GUARDS",
        },
        "ranking": [
            "MINIMUM_MAXIMUM_NEAREST_FOUR_SEPARATION",
            "MAXIMUM_MINIMUM_REMAINING_MARGIN",
            "MAXIMUM_MINIMUM_TIME_SHIFTED_ELEVATION",
            "EARLIEST_DATE_AND_START",
        ],
        "future_blindness": {
            "scorer_hypotheses": "OPAQUE_IDENTIFIERS_REQUIRED_BEFORE_PRIMARY",
            "mapping_outside_scorer": True,
            "upstream_receiver_prn_correlation_removed": False,
            "maximum_future_claim": (
                "BOUNDED_ORBIT_ASSIGNMENT_PREFERRED_WITHIN_FROZEN_CANDIDATE_SET"
            ),
        },
        "observation_boundary": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoders": 0,
        },
        "prospective_plan_frozen": False,
        "primary_selected": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(result)
    return result


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(manifest(root)).encode("ascii")).hexdigest()


def gps_day_grid(candidate: navigation.NavigationCandidate) -> tuple[datetime, ...]:
    gps_midnight = datetime.fromisoformat(candidate.gps_date).replace(
        tzinfo=timezone.utc
    )
    first_utc = gps_midnight - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    return tuple(
        first_utc + timedelta(seconds=index * STEP_S) for index in range(2_880)
    )


def _position_series(
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    satellite: str,
    epochs: Sequence[datetime],
    offset_s: float,
) -> np.ndarray:
    result = np.full((len(epochs), 3), np.nan, dtype=np.float64)
    for index, epoch in enumerate(epochs):
        shifted = epoch + timedelta(seconds=offset_s)
        try:
            selected = geometry.select_ephemeris(records[satellite], shifted)
            result[index] = geometry.broadcast_ecef(selected, shifted)
        except (KeyError, geometry.GnssDoubleDifferenceError):
            continue
    return result


def prefix_affine_separation(curve: Sequence[float]) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if values.shape != (RAW_EPOCHS,) or not np.all(np.isfinite(values)):
        raise BlindAssignmentScreenError("INVALID_PREFIX_AFFINE_CURVE")
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    prefix_x = elapsed[:PREFIX_EPOCHS]
    prefix_y = values[:PREFIX_EPOCHS]
    x_mean = float(np.mean(prefix_x))
    y_mean = float(np.mean(prefix_y))
    centered_x = prefix_x - x_mean
    denominator = float(centered_x @ centered_x)
    if denominator <= 0.0:
        raise BlindAssignmentScreenError("INVALID_PREFIX_TIME_BASIS")
    slope = float(centered_x @ (prefix_y - y_mean) / denominator)
    intercept = y_mean - slope * x_mean
    residual = values - (intercept + slope * elapsed)
    heldout = residual[PREFIX_EPOCHS:]
    return {
        "prefix_constant_m": float(intercept),
        "prefix_rate_m_s": float(slope),
        "heldout_peak_to_peak_m": float(np.ptp(heldout)),
        "heldout_rms_m": float(np.sqrt(np.mean(heldout * heldout))),
        "prefix_rmse_m": float(
            np.sqrt(np.mean(residual[:PREFIX_EPOCHS] ** 2))
        ),
    }


def select_nearest_family(
    alternatives: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    if len(alternatives) < ALTERNATIVE_COUNT:
        return ()
    ranked = sorted(
        (dict(row) for row in alternatives),
        key=lambda row: (
            float(row["heldout_peak_to_peak_m"]),
            str(row["satellite"]),
        ),
    )
    return tuple(ranked[:ALTERNATIVE_COUNT])


def _window_rank_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        float(row["maximum_family_separation_m"]),
        -float(row["minimum_remaining_margin_m"]),
        -float(row["minimum_time_shifted_elevation_deg"]),
        int(row["doy"]),
        int(row["start_index"]),
    )


def rank_admissible_windows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    admitted = [dict(row) for row in rows if bool(row["robustly_admissible"])]
    admitted.sort(key=_window_rank_key)
    return admitted


def _best_attempt_key(row: Mapping[str, object]) -> tuple[object, ...]:
    return (
        -float(row["minimum_combined_remaining_margin_m"]),
        -float(row["minimum_time_shifted_elevation_deg"]),
        int(row["doy"]),
        int(row["start_index"]),
    )


def compile_day(
    candidate: navigation.NavigationCandidate,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
) -> dict[str, object]:
    if TARGET not in records or REFERENCE not in records:
        raise BlindAssignmentScreenError(
            f"TARGET_OR_REFERENCE_MISSING_DOY_{candidate.doy}"
        )
    satellites = tuple(
        satellite
        for satellite in sorted(records)
        if satellite.startswith("G") and len(satellite) == 3
    )
    alternatives = tuple(
        satellite
        for satellite in satellites
        if satellite not in {TARGET, REFERENCE}
    )
    if len(alternatives) < ALTERNATIVE_COUNT:
        raise BlindAssignmentScreenError(
            f"TOO_FEW_HEALTHY_ALTERNATIVES_DOY_{candidate.doy}"
        )

    epochs = gps_day_grid(candidate)
    station_ecef = geometry.station_to_ecef(STATION)
    nominal_range: dict[str, np.ndarray] = {}
    shifted_elevation: dict[str, np.ndarray] = {}
    for satellite in satellites:
        elevations = []
        for offset in (
            -MAXIMUM_EVENT_TIME_ERROR_S,
            0.0,
            MAXIMUM_EVENT_TIME_ERROR_S,
        ):
            positions = _position_series(records, satellite, epochs, offset)
            elevations.append(geometry.elevation_deg(positions, STATION, station_ecef))
            if offset == 0.0:
                nominal_range[satellite] = np.linalg.norm(
                    positions - station_ecef, axis=1
                )
            positions.fill(0.0)
        shifted_elevation[satellite] = np.min(np.vstack(elevations), axis=0)

    complete_window: dict[str, np.ndarray] = {}
    kernel = np.ones(RAW_EPOCHS, dtype=np.int16)
    for satellite in satellites:
        visible = (
            np.isfinite(shifted_elevation[satellite])
            & (shifted_elevation[satellite] >= MINIMUM_ELEVATION_DEG)
            & np.isfinite(nominal_range[satellite])
        )
        complete_window[satellite] = (
            np.convolve(visible.astype(np.int16), kernel, mode="valid")
            == RAW_EPOCHS
        )

    rows: list[dict[str, object]] = []
    target_reference_curve = nominal_range[TARGET] - nominal_range[REFERENCE]
    possible_starts = len(epochs) - RAW_EPOCHS + 1
    target_reference_window_count = 0
    for start in range(possible_starts):
        if not (
            complete_window[TARGET][start]
            and complete_window[REFERENCE][start]
        ):
            continue
        target_reference_window_count += 1
        visible_alternatives = tuple(
            satellite
            for satellite in alternatives
            if complete_window[satellite][start]
        )
        if len(visible_alternatives) < ALTERNATIVE_COUNT:
            continue
        stop = start + RAW_EPOCHS
        target_curve = target_reference_curve[start:stop]
        affine = prefix_affine_separation(target_curve)
        evaluated = []
        for satellite in visible_alternatives:
            alternative_curve = (
                nominal_range[satellite][start:stop]
                - nominal_range[REFERENCE][start:stop]
            )
            metrics = prefix_affine_separation(target_curve - alternative_curve)
            separation = float(metrics["heldout_peak_to_peak_m"])
            evaluated.append(
                {
                    "satellite": satellite,
                    **metrics,
                    "remaining_margin_m": separation - PAIRWISE_GUARD_M,
                    "robust_double_guard_pass": separation >= ROBUST_SEPARATION_M,
                }
            )
        nearest = select_nearest_family(evaluated)
        if not nearest:
            continue
        family_satellites = (TARGET, REFERENCE) + tuple(
            str(row["satellite"]) for row in nearest
        )
        minimum_elevation = min(
            float(np.min(shifted_elevation[satellite][start:stop]))
            for satellite in family_satellites
        )
        minimum_family_margin = min(
            float(row["remaining_margin_m"]) for row in nearest
        )
        affine_separation = float(affine["heldout_peak_to_peak_m"])
        affine_remaining = affine_separation - PAIRWISE_GUARD_M
        robust = (
            affine_separation >= ROBUST_SEPARATION_M
            and all(bool(row["robust_double_guard_pass"]) for row in nearest)
        )
        rows.append(
            {
                "doy": candidate.doy,
                "gps_date": candidate.gps_date,
                "start_index": start,
                "raw_start_gps": geometry.format_gps(epochs[start]),
                "raw_stop_gps": geometry.format_gps(epochs[stop - 1]),
                "heldout_start_gps": geometry.format_gps(
                    epochs[start + PREFIX_EPOCHS]
                ),
                "visible_alternative_count": len(visible_alternatives),
                "candidate_family": [TARGET]
                + [str(row["satellite"]) for row in nearest],
                "nearest_four_alternatives": list(nearest),
                "affine_null": {
                    **affine,
                    "remaining_margin_m": affine_remaining,
                    "robust_double_guard_pass": (
                        affine_separation >= ROBUST_SEPARATION_M
                    ),
                },
                "maximum_family_separation_m": max(
                    float(row["heldout_peak_to_peak_m"]) for row in nearest
                ),
                "minimum_remaining_margin_m": minimum_family_margin,
                "minimum_combined_remaining_margin_m": min(
                    minimum_family_margin, affine_remaining
                ),
                "minimum_time_shifted_elevation_deg": minimum_elevation,
                "robustly_admissible": robust,
            }
        )

    ranked = rank_admissible_windows(rows)
    best_attempt = min(rows, key=_best_attempt_key) if rows else None
    result = {
        "doy": candidate.doy,
        "gps_date": candidate.gps_date,
        "healthy_gps_satellites": list(satellites),
        "healthy_gps_satellite_count": len(satellites),
        "target_reference_complete_window_count": target_reference_window_count,
        "nearest_four_evaluated_window_count": len(rows),
        "robust_window_count": len(ranked),
        "selected_day_window": ranked[0] if ranked else None,
        "best_margin_attempt_descriptive_only": best_attempt,
    }
    for values in nominal_range.values():
        values.fill(0.0)
    for values in shifted_elevation.values():
        values.fill(0.0)
    return result


def compile_screen(
    payloads: Mapping[int, bytes], root: Path
) -> dict[str, object]:
    scope = validate_scope(root)
    expected_doys = {candidate.doy for candidate in NAVIGATION_CANDIDATES}
    if set(payloads) != expected_doys:
        raise BlindAssignmentScreenError("NAVIGATION_PAYLOAD_SET_CHANGED")
    days = []
    authorities = []
    for candidate in NAVIGATION_CANDIDATES:
        records, authority = navigation.parse_navigation_gzip(
            candidate, payloads[candidate.doy]
        )
        days.append(compile_day(candidate, records))
        authorities.append(authority)

    selected_candidates = [
        day["selected_day_window"]
        for day in days
        if day["selected_day_window"] is not None
    ]
    ranked = rank_admissible_windows(selected_candidates)
    selected = ranked[0] if ranked else None
    result = {
        "schema": "gnss-blind-orbit-assignment-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "scope": scope,
        "manifest_sha256": manifest_sha256(root),
        "navigation": authorities,
        "day_results": days,
        "shortlist": ranked[:3],
        "selected": selected,
        "outcome": OUTCOME_SHORTLISTED if selected is not None else OUTCOME_NONE,
        "observation_access": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "consumed_outcomes_reopened": 0,
        },
        "orbital_scores_from_measurements": 0,
        "qualification_artifact_selected": False,
        "primary_selected": False,
        "prospective_plan_frozen": False,
        "maximum_authorized_claim": None,
        "next_maximum": (
            "REVIEW_BEFORE_OPAQUE_HYPOTHESIS_PLAN_AND_ONE_NEW_PRIMARY_SELECTION"
            if selected is not None
            else "ABANDON_THIS_COORDINATE_FOR_BOUNDED_BLIND_ASSIGNMENT"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_DISCOVERY_OR_ACCESS",
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    if Path(path).exists():
        raise BlindAssignmentScreenError("SCREEN_RECEIPT_ALREADY_EXISTS")
    Path(path).write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--navigation-gzip", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, default=root / RECEIPT_NAME)
    args = parser.parse_args()
    supplied = {path.name: path for path in args.navigation_gzip}
    expected = {candidate.name: candidate for candidate in NAVIGATION_CANDIDATES}
    if len(supplied) != len(args.navigation_gzip) or set(supplied) != set(expected):
        raise SystemExit("SUPPLY_EXACTLY_THE_FIVE_FROZEN_NAVIGATION_PRODUCTS")
    payloads = {
        expected[name].doy: path.read_bytes() for name, path in supplied.items()
    }
    try:
        receipt = compile_screen(payloads, root)
    finally:
        payloads.clear()
    _write_json(args.output, receipt)
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
