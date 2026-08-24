"""Broadcast-only duration sensitivity for the selected G22/G30 geometry."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as old
from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair
from experiments.orbital_discriminability import gnss_phase_quotient_spike as phase


COMPILER_VERSION: Final = "g22-g30-phase-duration-sensitivity-v1"
PLAN_NAME: Final = "GNSS_PHASE_DURATION_SENSITIVITY_PLAN.md"
STRUCTURAL_OUTCOME_NAME: Final = "GNSS_PHASE_STRUCTURE_OUTCOME.json"
STRUCTURAL_OUTCOME_SHA256: Final = (
    "7b7efb4fc3fb81e029f85bebde1e9f53520a49ffb9f5909a200ea4da4ec571d8"
)
TARGET: Final = "G22"
REFERENCE: Final = "G30"
ELIGIBLE_DOYS: Final = (217, 218, 219, 220)
HELDOUT_EPOCH_GRID: Final = (60, 120, 180, 240, 307)
CALIBRATION_EPOCHS: Final = 77
PRE_ROLL_EPOCHS: Final = 60
OUTCOME_AVAILABLE: Final = "PHASE_SHORTER_WINDOW_PHYSICALLY_AVAILABLE"
OUTCOME_NONE: Final = "NO_SHORTER_WINDOW_PHYSICAL_MARGIN"


class DurationSensitivityError(ValueError):
    """A frozen input or numerical invariant changed."""


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def authorities() -> tuple[pair.NavigationAuthority, ...]:
    result = tuple(
        authority for authority in pair.AUTHORITIES if authority.doy in ELIGIBLE_DOYS
    )
    if tuple(authority.doy for authority in result) != ELIGIBLE_DOYS:
        raise DurationSensitivityError("ELIGIBLE_NAVIGATION_SET_CHANGED")
    return result


def manifest() -> dict[str, object]:
    result = {
        "compiler_version": COMPILER_VERSION,
        "plan_sha256": canonical_sha256(Path(__file__).resolve().parent / PLAN_NAME),
        "closed_structural_outcome": {
            "name": STRUCTURAL_OUTCOME_NAME,
            "canonical_sha256": STRUCTURAL_OUTCOME_SHA256,
            "allowed_fields": ["outcome", "primary_doy220_access"],
            "coverage_and_summary_as_numerical_inputs": "FORBIDDEN",
        },
        "navigation": [asdict(authority) for authority in authorities()],
        "stations": [station.station_id for station in base.STATIONS],
        "target": TARGET,
        "reference": REFERENCE,
        "eligible_doys": list(ELIGIBLE_DOYS),
        "excluded_doy": {
            "doy": 216,
            "reason": "MEASUREMENT_STRUCTURE_ALREADY_OBSERVED",
        },
        "grid": {
            "step_s": base.GRID_STEP_S,
            "pre_roll_epochs": PRE_ROLL_EPOCHS,
            "calibration_epochs": CALIBRATION_EPOCHS,
            "heldout_epochs": list(HELDOUT_EPOCH_GRID),
            "raw_epoch_formula": "CALIBRATION_PLUS_HELDOUT_PLUS_TWO_ENDPOINTS",
        },
        "window_rule": (
            "ONE_GEOMETRY_ONLY_GUARD_MAXIMIZING_BLOCK_PER_DATE_DURATION_"
            "EARLIEST_TIE"
        ),
        "minimum_elevation_deg": base.MINIMUM_ELEVATION_DEG,
        "nulls": [
            "PREFIX_CONSTANT_PLUS_RATE_FIT_ON_FIXED_77_EPOCH_PREFIX",
            "EVERY_OTHER_GPS_ORBIT_JOINTLY_VISIBLE_ON_THE_SAME_GUARDED_BLOCK",
        ],
        "physical_envelope": {
            "station_event_time": "DIRECT_PLUS_MINUS_15_SECOND_TRAJECTORIES",
            "troposphere": "BOUNDED_ONE_OVER_SINE_MAPPING",
            "quantization": "RINEX_CARRIER_PHASE_FORMAT_BOUND",
            "generic_path_terms": [item["term"] for item in old.GENERIC_PATH_BOUNDS_M],
            "combination": "LINEAR_SUM_THEN_PAIRWISE_MULTIPLIER_TWO",
        },
        "role_pair_rule": (
            "SHORTEST_TESTED_DURATION_WITH_POSITIVE_COMPLETE_MARGIN_ON_AT_"
            "LEAST_TWO_DISTINCT_UNOPENED_DATES"
        ),
        "forbidden": [
            "DOY216 candidate participation",
            "RINEX product discovery header payload or value access",
            "use of structural coverage gap positions in window selection",
            "calibration null envelope station satellite or duration-grid change",
            "qualification primary or reserve role assignment",
            "prospective plan freeze",
            "new gate or generic framework",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def validate_structural_closure(path: Path) -> None:
    if canonical_sha256(path) != STRUCTURAL_OUTCOME_SHA256:
        raise DurationSensitivityError("STRUCTURAL_OUTCOME_CHANGED")
    outcome = json.loads(Path(path).read_text(encoding="utf-8"))
    if outcome.get("outcome") != "GNSS_PHASE_STRUCTURE_REJECTED":
        raise DurationSensitivityError("OLD_TOPOLOGY_NOT_CLOSED")
    if outcome.get("primary_doy220_access") != {
        "headers": 0,
        "payload_bytes": 0,
        "values": 0,
    }:
        raise DurationSensitivityError("DOY220_PRIMARY_NOT_SEALED")


def validate_navigation(paths: Sequence[Path]) -> dict[int, Path]:
    supplied = {Path(path).name: Path(path) for path in paths}
    expected = {authority.name for authority in authorities()}
    if len(supplied) != len(paths) or set(supplied) != expected:
        raise DurationSensitivityError("NAVIGATION_SET_CHANGED")
    result: dict[int, Path] = {}
    for authority in authorities():
        path = supplied[authority.name]
        if not path.is_file() or path.stat().st_size != authority.bytes:
            raise DurationSensitivityError(f"NAVIGATION_SIZE_CHANGED:{authority.doy}")
        if base.file_sha256(path) != authority.sha256:
            raise DurationSensitivityError(f"NAVIGATION_SHA256_CHANGED:{authority.doy}")
        result[authority.doy] = path
    return result


def select_guarded_block(
    four_link_minimum_deg: Sequence[float], block_epochs: int
) -> tuple[int, float] | None:
    values = np.asarray(four_link_minimum_deg, dtype=np.float64)
    if values.ndim != 1 or block_epochs < 1:
        raise DurationSensitivityError("INVALID_GUARDED_BLOCK_INPUT")
    values = np.where(np.isfinite(values), values, -np.inf)
    best: tuple[float, int] | None = None
    for start, stop in base.contiguous_true_segments(
        values >= base.MINIMUM_ELEVATION_DEG
    ):
        if stop - start < block_epochs:
            continue
        windows = np.lib.stride_tricks.sliding_window_view(
            values[start:stop], block_epochs
        )
        minima = np.min(windows, axis=1)
        local = int(np.argmax(minima))
        candidate = (float(minima[local]), start + local)
        if best is None or candidate[0] > best[0]:
            best = candidate
    return None if best is None else (best[1], best[0])


def compile_day(path: Path, authority: pair.NavigationAuthority) -> list[dict[str, object]]:
    records = base.parse_gps_navigation(path)
    epochs = pair.gps_day_grid(authority)
    satellites = tuple(sorted(records))
    if TARGET not in satellites or REFERENCE not in satellites:
        raise DurationSensitivityError(f"TARGET_OR_REFERENCE_MISSING:{authority.doy}")
    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    position_cache: dict[tuple[str, float], np.ndarray] = {}

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, offset_s
        if key not in position_cache:
            rows = []
            for epoch in epochs:
                shifted = epoch + timedelta(seconds=offset_s)
                try:
                    row = base.broadcast_ecef(
                        base.select_ephemeris(records[satellite], shifted), shifted
                    )
                except base.GnssDoubleDifferenceError:
                    row = np.full(3, np.nan, dtype=np.float64)
                rows.append(row)
            position_cache[key] = np.asarray(rows)
        return position_cache[key]

    left, right = (station.station_id for station in base.STATIONS)

    def range_curve(
        target: str,
        reference: str,
        left_offset_s: float = 0.0,
        right_offset_s: float = 0.0,
    ) -> np.ndarray:
        return phase.double_difference_range_m(
            phase.range_to_station_m(
                positions(target, left_offset_s), station_ecef[left]
            ),
            phase.range_to_station_m(
                positions(reference, left_offset_s), station_ecef[left]
            ),
            phase.range_to_station_m(
                positions(target, right_offset_s), station_ecef[right]
            ),
            phase.range_to_station_m(
                positions(reference, right_offset_s), station_ecef[right]
            ),
        )

    elevation_cache: dict[tuple[str, str], np.ndarray] = {}

    def elevation(station_id: str, satellite: str) -> np.ndarray:
        key = station_id, satellite
        if key not in elevation_cache:
            station = next(
                item for item in base.STATIONS if item.station_id == station_id
            )
            elevation_cache[key] = base.elevation_deg(
                positions(satellite), station, station_ecef[station_id]
            )
        return elevation_cache[key]

    four_link = np.minimum.reduce(
        (
            elevation(left, TARGET),
            elevation(right, TARGET),
            elevation(left, REFERENCE),
            elevation(right, REFERENCE),
        )
    )
    if not np.all(np.isfinite(positions(TARGET))) or not np.all(
        np.isfinite(positions(REFERENCE))
    ):
        raise DurationSensitivityError(
            f"TARGET_OR_REFERENCE_EPHEMERIS_INCOMPLETE:{authority.doy}"
        )
    rows: list[dict[str, object]] = []
    for heldout_epochs in HELDOUT_EPOCH_GRID:
        feature_epochs = CALIBRATION_EPOCHS + heldout_epochs
        raw_epochs = feature_epochs + 2
        block_epochs = PRE_ROLL_EPOCHS + raw_epochs
        selected = select_guarded_block(four_link, block_epochs)
        if selected is None:
            rows.append(
                {
                    "doy": authority.doy,
                    "heldout_epochs": heldout_epochs,
                    "feature_epochs": feature_epochs,
                    "raw_epochs": raw_epochs,
                    "state": "NO_GUARDED_WINDOW",
                    "remaining_physical_margin_m": None,
                }
            )
            continue
        block_start, block_minimum = selected
        raw_start = block_start + PRE_ROLL_EPOCHS
        raw_stop = raw_start + raw_epochs
        block = slice(block_start, raw_stop)
        feature = slice(raw_start + 1, raw_stop - 1)
        nominal = range_curve(TARGET, REFERENCE)[feature]
        if nominal.size != feature_epochs:
            raise DurationSensitivityError("FEATURE_EPOCH_COUNT_CHANGED")
        affine = phase.phase_prefix_metrics(
            nominal, split=CALIBRATION_EPOCHS, step_s=base.GRID_STEP_S
        )
        alternatives = []
        for satellite in satellites:
            if satellite in (TARGET, REFERENCE):
                continue
            if not np.all(np.isfinite(positions(satellite))):
                continue
            visible = (
                np.all(
                    elevation(left, satellite)[block]
                    >= base.MINIMUM_ELEVATION_DEG
                )
                and np.all(
                    elevation(right, satellite)[block]
                    >= base.MINIMUM_ELEVATION_DEG
                )
            )
            if not visible:
                continue
            alternative = range_curve(satellite, REFERENCE)[feature]
            score = phase.phase_prefix_metrics(
                nominal - alternative,
                split=CALIBRATION_EPOCHS,
                step_s=base.GRID_STEP_S,
            )
            alternatives.append(
                {
                    "satellite": satellite,
                    "heldout_peak_to_peak_m": score["heldout_peak_to_peak_m"],
                    "heldout_rms_m": score["heldout_rms_m"],
                }
            )
        alternatives.sort(
            key=lambda item: (
                float(item["heldout_peak_to_peak_m"]),
                str(item["satellite"]),
            )
        )
        if not alternatives:
            rows.append(
                {
                    "doy": authority.doy,
                    "heldout_epochs": heldout_epochs,
                    "feature_epochs": feature_epochs,
                    "raw_epochs": raw_epochs,
                    "state": "NO_JOINTLY_VISIBLE_WRONG_ORBIT",
                    "remaining_physical_margin_m": None,
                }
            )
            continue
        wrong = alternatives[0]
        controlling = min(
            affine["heldout_peak_to_peak_m"],
            float(wrong["heldout_peak_to_peak_m"]),
        )
        controlling_null = (
            "PREFIX_AFFINE"
            if affine["heldout_peak_to_peak_m"]
            <= float(wrong["heldout_peak_to_peak_m"])
            else f"WRONG_ORBIT_{wrong['satellite']}"
        )
        projection_gain = old.affine_projection_peak_to_peak_gain(
            feature_epochs, CALIBRATION_EPOCHS, base.GRID_STEP_S
        )

        def fixed_reference_curve(
            target_satellite: str, left_offset_s: float, right_offset_s: float
        ) -> np.ndarray:
            return range_curve(
                target_satellite,
                REFERENCE,
                left_offset_s,
                right_offset_s,
            )

        target_reference_elevation = {
            (station.station_id, satellite): elevation(
                station.station_id, satellite
            )
            for station in base.STATIONS
            for satellite in (TARGET, REFERENCE)
        }
        terms = [
            phase.timing_term(fixed_reference_curve, feature, target=TARGET),
            phase.troposphere_term(
                target_reference_elevation,
                feature,
                target=TARGET,
                reference=REFERENCE,
            ),
            phase.quantization_term(projection_gain),
        ]
        terms.extend(
            phase.per_link_interval_term(definition, projection_gain)
            for definition in old.GENERIC_PATH_BOUNDS_M
        )
        decision = phase.combine_terms(controlling, terms)
        for term in terms:
            term["pairwise_contribution_m"] = float(
                old.PAIRWISE_ENVELOPE_MULTIPLIER
                * float(term["heldout_peak_to_peak_bound_m"])
            )
        terms.sort(
            key=lambda term: (
                -float(term["pairwise_contribution_m"]),
                str(term["term"]),
            )
        )
        rows.append(
            {
                "doy": authority.doy,
                "heldout_epochs": heldout_epochs,
                "heldout_budget_s": heldout_epochs * base.GRID_STEP_S,
                "heldout_sample_span_s": (heldout_epochs - 1)
                * base.GRID_STEP_S,
                "feature_epochs": feature_epochs,
                "raw_epochs": raw_epochs,
                "raw_elapsed_s": (raw_epochs - 1) * base.GRID_STEP_S,
                "pre_roll_start_gps": base.format_gps(epochs[block_start]),
                "raw_start_gps": base.format_gps(epochs[raw_start]),
                "raw_stop_gps": base.format_gps(epochs[raw_stop - 1]),
                "feature_start_gps": base.format_gps(epochs[raw_start + 1]),
                "feature_stop_gps": base.format_gps(epochs[raw_stop - 2]),
                "heldout_start_gps": base.format_gps(
                    epochs[raw_start + 1 + CALIBRATION_EPOCHS]
                ),
                "guarded_block_minimum_elevation_deg": block_minimum,
                "raw_minimum_elevation_deg": float(
                    np.min(four_link[raw_start:raw_stop])
                ),
                "prefix_affine_null": affine,
                "wrong_orbit_null": {
                    "controlling_alternative": wrong["satellite"],
                    "minimum_heldout_peak_to_peak_m": wrong[
                        "heldout_peak_to_peak_m"
                    ],
                    "alternatives": alternatives,
                },
                "controlling_null": controlling_null,
                "controlling_heldout_separation_m": controlling,
                "affine_projection_peak_to_peak_gain": projection_gain,
                "physical_terms": terms,
                **decision,
                "state": "PHYSICAL_MARGIN_COMPILED",
            }
        )
    return rows


def summarize(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    expected = {
        (doy, heldout)
        for doy in ELIGIBLE_DOYS
        for heldout in HELDOUT_EPOCH_GRID
    }
    observed = {
        (int(row["doy"]), int(row["heldout_epochs"])) for row in rows
    }
    if observed != expected or len(rows) != len(expected):
        raise DurationSensitivityError("DURATION_MATRIX_INCOMPLETE")

    summaries: list[dict[str, object]] = []
    selected_heldout: int | None = None
    for heldout in HELDOUT_EPOCH_GRID:
        duration_rows = [
            row for row in rows if int(row["heldout_epochs"]) == heldout
        ]
        compiled = [
            row
            for row in duration_rows
            if row["state"] == "PHYSICAL_MARGIN_COMPILED"
        ]
        positive = [
            row
            for row in compiled
            if float(row["remaining_physical_margin_m"]) > 0.0
        ]
        role_pair_available = (
            heldout < HELDOUT_EPOCH_GRID[-1] and len(positive) >= 2
        )
        if role_pair_available and selected_heldout is None:
            selected_heldout = heldout
        summaries.append(
            {
                "heldout_epochs": heldout,
                "heldout_budget_s": heldout * base.GRID_STEP_S,
                "heldout_sample_span_s": (heldout - 1) * base.GRID_STEP_S,
                "compiled_dates": [int(row["doy"]) for row in compiled],
                "positive_margin_dates": [int(row["doy"]) for row in positive],
                "positive_margin_date_count": len(positive),
                "minimum_positive_margin_m": (
                    min(float(row["remaining_physical_margin_m"]) for row in positive)
                    if positive
                    else None
                ),
                "maximum_guard_deg": (
                    max(
                        float(row["guarded_block_minimum_elevation_deg"])
                        for row in compiled
                    )
                    if compiled
                    else None
                ),
                "role_pair_physically_available": role_pair_available,
            }
        )

    ranked: list[dict[str, object]] = []
    if selected_heldout is not None:
        selected_rows = [
            dict(row)
            for row in rows
            if int(row["heldout_epochs"]) == selected_heldout
            and row["state"] == "PHYSICAL_MARGIN_COMPILED"
            and float(row["remaining_physical_margin_m"]) > 0.0
        ]
        selected_rows.sort(
            key=lambda row: (
                -float(row["guarded_block_minimum_elevation_deg"]),
                -float(row["remaining_physical_margin_m"]),
                int(row["doy"]),
            )
        )
        for rank, row in enumerate(selected_rows, start=1):
            ranked.append({**row, "diagnostic_rank": rank})

    result = {
        "outcome": OUTCOME_AVAILABLE if selected_heldout is not None else OUTCOME_NONE,
        "duration_summaries": summaries,
        "shortest_available_heldout_epochs": selected_heldout,
        "shortest_available_heldout_budget_s": (
            None
            if selected_heldout is None
            else selected_heldout * base.GRID_STEP_S
        ),
        "diagnostic_date_ranking": ranked,
        "roles_assigned": False,
        "prospective_plan_frozen": False,
    }
    strict_json(result)
    return result


def run(
    navigation_paths: Sequence[Path], structural_outcome_path: Path
) -> dict[str, object]:
    validate_structural_closure(structural_outcome_path)
    paths_by_doy = validate_navigation(navigation_paths)
    rows = [
        row
        for authority in authorities()
        for row in compile_day(paths_by_doy[authority.doy], authority)
    ]
    decision = summarize(rows)
    result = {
        "schema": "gnss-phase-duration-sensitivity-receipt-v1",
        "compiler_version": COMPILER_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "structural_closure": {
            "name": STRUCTURAL_OUTCOME_NAME,
            "canonical_sha256": STRUCTURAL_OUTCOME_SHA256,
            "terminal_outcome": "GNSS_PHASE_STRUCTURE_REJECTED",
            "numerical_inputs_imported": [],
        },
        "navigation": [asdict(authority) for authority in authorities()],
        "scope": (
            "BROADCAST_NAVIGATION_ONLY_NO_RINEX_DISCOVERY_HEADER_PAYLOAD_OR_VALUE_ACCESS"
        ),
        "observation_access": {
            "products_discovered": 0,
            "products_selected": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
        },
        "candidate_roles": {
            "qualification": None,
            "primary": None,
            "reserve": None,
        },
        "duration_rows": rows,
        **decision,
        "next_authority": "NONE_STOP_AFTER_DURATION_TABLE",
    }
    strict_json(result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("navigation", nargs=4, type=Path)
    parser.add_argument("--structural-outcome", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = run(args.navigation, args.structural_outcome)
    args.output.write_text(
        json.dumps(
            receipt,
            allow_nan=False,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
