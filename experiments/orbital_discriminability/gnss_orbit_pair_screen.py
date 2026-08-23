"""Bounded orbit-only GOLD/NLIB GPS-pair comparison.

The only accepted artifacts are five exact-hash broadcast-navigation files.
No observation product name, header or payload is part of the input surface.
The result selects at most one geometry for later physical-envelope work; it
does not qualify a measurement and does not freeze a prospective experiment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_screen as base


SCREEN_VERSION: Final = "gold-nlib-broadcast-pair-screen-v1"
RAW_EPOCHS: Final = 386
FEATURE_EPOCHS: Final = 384
CALIBRATION_EPOCHS: Final = 77
HELDOUT_EPOCHS: Final = 307
PRE_ROLL_EPOCHS: Final = 60
GUARDED_BLOCK_EPOCHS: Final = PRE_ROLL_EPOCHS + RAW_EPOCHS
OUTCOME_SELECTED: Final = "GNSS_ORBIT_PAIR_GEOMETRY_SELECTED"
OUTCOME_NONE: Final = "NO_GOLD_NLIB_GEOMETRY_GUARDED_PAIR"


@dataclass(frozen=True, slots=True)
class NavigationAuthority:
    doy: int
    gps_date: str
    name: str
    bytes: int
    sha256: str
    compressed_bytes: int
    compressed_sha256: str


AUTHORITIES: Final = (
    NavigationAuthority(
        216,
        "2026-08-04",
        "BRDM00DLR_S_20262160000_01D_MN.rnx",
        8_458_713,
        "b20021fdfc4119f843e8f35414037fe629759568a0a1a3e268dd84799ddfd1e6",
        1_401_853,
        "53c2083bb1d1ec046486dc0e6d4a18547f367bcf486629a6282d62950d85c704",
    ),
    NavigationAuthority(
        217,
        "2026-08-05",
        "BRDM00DLR_S_20262170000_01D_MN.rnx",
        8_362_647,
        "40c5c1619f6d5cb1a9cb00b33025529d81f826ee1e9fb60738f0193e992325b9",
        1_352_449,
        "8cbfca665122e6920f5f9ca224de9f83f267144d963240b0c3de9d36cde0ee8e",
    ),
    NavigationAuthority(
        218,
        "2026-08-06",
        "BRDM00DLR_S_20262180000_01D_MN.rnx",
        8_375_526,
        "6ef0bbe17c20b3bfba7065a154230fcac95ef5094b3d0c08bb0709d8c3fe9413",
        1_354_010,
        "cb1a8c14f39b823cfb12c1f9cca35f816b6eb867594ff04b88d0ffaf5d474d5c",
    ),
    NavigationAuthority(
        219,
        "2026-08-07",
        "BRDM00DLR_S_20262190000_01D_MN.rnx",
        8_383_950,
        "8d5126ae5a7a8ad1e718c11a1c575c0961de1c57845ca15da4081e65e5709b5d",
        1_391_036,
        "12246e0e614f0a16c9bd7329ddd637fb541d478160d944131023aa9faeffcc3d",
    ),
    NavigationAuthority(
        220,
        "2026-08-08",
        "BRDM00DLR_S_20262200000_01D_MN.rnx",
        8_285_778,
        "8ac8cd5327b84295436875b57cd88f6d7a45fa666acc5094be13fe56990d0df3",
        1_373_719,
        "13993e96bebf24c5bc515ac2a0f75170804e41bc3aadf066a9ec1b4e41c34b32",
    ),
)


class OrbitPairScreenError(ValueError):
    """The frozen orbit-only comparison authority or grid is invalid."""


def manifest() -> dict[str, object]:
    return {
        "screen_version": SCREEN_VERSION,
        "physical_question": (
            "DOES_ANY_HEALTHY_GPS_PAIR_OVER_FIXED_GOLD_NLIB_GEOMETRY_SUPPORT_"
            "THE_UNCHANGED_386_EPOCH_HELDOUT_TEST_AFTER_A_30_MINUTE_GUARD"
        ),
        "information_gain": (
            "WHETHER_THE_G11_G21_FAILURE_IS_PAIR_SPECIFIC_OR_CLOSES_THE_"
            "GOLD_NLIB_GEOMETRY_AT_THE_FROZEN_DURATION"
        ),
        "navigation": [asdict(authority) for authority in AUTHORITIES],
        "stations": [station.station_id for station in base.STATIONS],
        "parameters": {
            "grid_step_s": base.GRID_STEP_S,
            "minimum_elevation_deg": base.MINIMUM_ELEVATION_DEG,
            "pre_roll_epochs": PRE_ROLL_EPOCHS,
            "pre_roll_duration_s": PRE_ROLL_EPOCHS * base.GRID_STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "feature_epochs": FEATURE_EPOCHS,
            "calibration_epochs": CALIBRATION_EPOCHS,
            "heldout_epochs": HELDOUT_EPOCHS,
            "central_derivative_edge_epochs_dropped": 2,
        },
        "window_selection": (
            "FOR_EACH_UNORDERED_PAIR_AND_DATE_MAXIMIZE_THE_MINIMUM_FOUR_LINK_"
            "ELEVATION_OVER_PRE_ROLL_PLUS_RAW_WINDOW_EARLIEST_TIE"
        ),
        "ranking": (
            "DESCENDING_MIN_OF_PREFIX_AFFINE_AND_CLOSEST_JOINTLY_VISIBLE_"
            "WRONG_TARGET_ORBIT_HELDOUT_PEAK_TO_PEAK_THEN_GUARD_MARGIN_"
            "THEN_DATE_AND_PRN"
        ),
        "nulls": [
            "PREFIX_AFFINE_FIT_ON_FIRST_77_FEATURE_EPOCHS_ONLY",
            "OTHER_TARGET_GPS_BROADCAST_ORBIT_ON_IDENTICAL_307_EPOCH_HELDOUT",
        ],
        "forbidden": [
            "observation product discovery or selection",
            "observation header or payload access",
            "window shortening",
            "holdout nuisance refit",
            "physical-envelope admission",
            "measurement authorization",
        ],
    }


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def validate_navigation_set(paths: Sequence[Path]) -> dict[int, Path]:
    supplied = {Path(path).name: Path(path) for path in paths}
    if len(supplied) != len(paths) or set(supplied) != {
        authority.name for authority in AUTHORITIES
    }:
        raise OrbitPairScreenError("navigation set does not match frozen authority")
    validated: dict[int, Path] = {}
    for authority in AUTHORITIES:
        path = supplied[authority.name]
        if not path.is_file() or path.stat().st_size != authority.bytes:
            raise OrbitPairScreenError(f"navigation size changed for DOY {authority.doy}")
        if base.file_sha256(path) != authority.sha256:
            raise OrbitPairScreenError(f"navigation SHA-256 changed for DOY {authority.doy}")
        validated[authority.doy] = path
    return validated


def gps_day_grid(authority: NavigationAuthority) -> tuple[datetime, ...]:
    gps_midnight = datetime.fromisoformat(authority.gps_date).replace(tzinfo=timezone.utc)
    first_utc = gps_midnight - timedelta(seconds=base.GPS_UTC_OFFSET_S)
    return tuple(
        first_utc + timedelta(seconds=index * base.GRID_STEP_S)
        for index in range(2_880)
    )


def select_guarded_block(
    four_link_minimum_deg: Sequence[float],
) -> tuple[int, float] | None:
    values = np.asarray(four_link_minimum_deg, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise OrbitPairScreenError("invalid joint-elevation series")
    best: tuple[float, int] | None = None
    for segment_start, segment_stop in base.contiguous_true_segments(
        values >= base.MINIMUM_ELEVATION_DEG
    ):
        if segment_stop - segment_start < GUARDED_BLOCK_EPOCHS:
            continue
        windows = np.lib.stride_tricks.sliding_window_view(
            values[segment_start:segment_stop], GUARDED_BLOCK_EPOCHS
        )
        minima = np.min(windows, axis=1)
        local_start = int(np.argmax(minima))
        candidate = (float(minima[local_start]), segment_start + local_start)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        return None
    return best[1], best[0]


def prefix_affine(curve: Sequence[float]) -> dict[str, float]:
    values = np.asarray(curve, dtype=np.float64)
    if values.shape != (FEATURE_EPOCHS,):
        raise OrbitPairScreenError("feature grid changed")
    return base.prefix_affine_metrics(values, CALIBRATION_EPOCHS, base.GRID_STEP_S)


def wrong_orbit_null(
    target: str,
    reference: str,
    block: slice,
    feature: slice,
    satellites: Sequence[str],
    fractional: Mapping[tuple[str, str], np.ndarray],
    elevation: Mapping[tuple[str, str], np.ndarray],
) -> dict[str, object]:
    left, right = (station.station_id for station in base.STATIONS)
    nominal = base.double_difference_hz(
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
            np.all(elevation[(left, alternative)][block] >= base.MINIMUM_ELEVATION_DEG)
            and np.all(elevation[(right, alternative)][block] >= base.MINIMUM_ELEVATION_DEG)
        ):
            continue
        curve = base.double_difference_hz(
            fractional[(left, alternative)],
            fractional[(left, reference)],
            fractional[(right, alternative)],
            fractional[(right, reference)],
        )[feature]
        metric = prefix_affine(nominal - curve)
        alternatives.append(
            {
                "satellite": alternative,
                "heldout_peak_to_peak_hz": metric["heldout_peak_to_peak_hz"],
                "heldout_rms_hz": metric["heldout_rms_hz"],
            }
        )
    alternatives.sort(key=lambda row: (row["heldout_peak_to_peak_hz"], row["satellite"]))
    if not alternatives:
        return {
            "controlling_alternative": None,
            "minimum_heldout_peak_to_peak_hz": 0.0,
            "alternatives": [],
        }
    return {
        "controlling_alternative": alternatives[0]["satellite"],
        "minimum_heldout_peak_to_peak_hz": alternatives[0]["heldout_peak_to_peak_hz"],
        "alternatives": alternatives,
    }


def screen_day(path: Path, authority: NavigationAuthority) -> dict[str, object]:
    records = base.parse_gps_navigation(path)
    epochs = gps_day_grid(authority)
    satellites = tuple(sorted(records))
    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    positions = {
        satellite: np.asarray(
            [
                base.broadcast_ecef(base.select_ephemeris(records[satellite], epoch), epoch)
                for epoch in epochs
            ]
        )
        for satellite in satellites
    }
    fractional = {
        (station.station_id, satellite): base.fractional_doppler(
            positions[satellite], station_ecef[station.station_id], base.GRID_STEP_S
        )
        for station in base.STATIONS
        for satellite in satellites
    }
    elevation = {
        (station.station_id, satellite): base.elevation_deg(
            positions[satellite], station, station_ecef[station.station_id]
        )
        for station in base.STATIONS
        for satellite in satellites
    }
    left, right = (station.station_id for station in base.STATIONS)
    candidates = []
    rejected_guard = 0
    rejected_null = 0
    for target, reference in combinations(satellites, 2):
        four_link_minimum = np.minimum.reduce(
            (
                elevation[(left, target)],
                elevation[(right, target)],
                elevation[(left, reference)],
                elevation[(right, reference)],
            )
        )
        selected = select_guarded_block(four_link_minimum)
        if selected is None:
            rejected_guard += 1
            continue
        block_start, block_minimum = selected
        raw_start = block_start + PRE_ROLL_EPOCHS
        raw_stop = raw_start + RAW_EPOCHS
        block = slice(block_start, raw_stop)
        feature = slice(raw_start + 1, raw_stop - 1)
        nominal = base.double_difference_hz(
            fractional[(left, target)],
            fractional[(left, reference)],
            fractional[(right, target)],
            fractional[(right, reference)],
        )[feature]
        affine = prefix_affine(nominal)
        wrong = wrong_orbit_null(
            target,
            reference,
            block,
            feature,
            satellites,
            fractional,
            elevation,
        )
        if wrong["controlling_alternative"] is None:
            rejected_null += 1
            continue
        controlling = min(
            affine["heldout_peak_to_peak_hz"],
            wrong["minimum_heldout_peak_to_peak_hz"],
        )
        candidates.append(
            {
                "doy": authority.doy,
                "target": target,
                "reference": reference,
                "pre_roll_start_gps": base.format_gps(epochs[block_start]),
                "raw_start_gps": base.format_gps(epochs[raw_start]),
                "raw_stop_gps": base.format_gps(epochs[raw_stop - 1]),
                "feature_start_gps": base.format_gps(epochs[raw_start + 1]),
                "feature_stop_gps": base.format_gps(epochs[raw_stop - 2]),
                "guarded_block_minimum_elevation_deg": block_minimum,
                "pre_roll_minimum_elevation_deg": float(
                    np.min(four_link_minimum[block_start:raw_start])
                ),
                "raw_minimum_elevation_deg": float(
                    np.min(four_link_minimum[raw_start:raw_stop])
                ),
                "prefix_affine_null": affine,
                "wrong_orbit_null": wrong,
                "controlling_heldout_separation_hz": float(controlling),
            }
        )
    return {
        "doy": authority.doy,
        "healthy_satellites": list(satellites),
        "unordered_pairs_evaluated": len(satellites) * (len(satellites) - 1) // 2,
        "rejected_no_guarded_block": rejected_guard,
        "rejected_no_jointly_visible_wrong_orbit": rejected_null,
        "rankable_candidates": candidates,
    }


def screen_navigation_set(paths: Sequence[Path]) -> dict[str, object]:
    validated = validate_navigation_set(paths)
    days = []
    candidates = []
    for authority in AUTHORITIES:
        day = screen_day(validated[authority.doy], authority)
        candidates.extend(day.pop("rankable_candidates"))
        days.append(day)
    candidates.sort(
        key=lambda row: (
            -row["controlling_heldout_separation_hz"],
            -row["guarded_block_minimum_elevation_deg"],
            row["doy"],
            row["target"],
            row["reference"],
        )
    )
    shortlist = candidates[:3]
    for rank, candidate in enumerate(shortlist, start=1):
        candidate["rank"] = rank
        candidate["selection_state"] = (
            "FROZEN_GEOMETRY_CANDIDATE" if rank == 1 else "LOWER_RANKED_NOT_SELECTED"
        )
    selected = shortlist[0] if shortlist else None
    result = {
        "schema": "gnss-orbit-pair-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "manifest_sha256": manifest_sha256(),
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_PRODUCTS_UNDISCOVERED",
        "navigation_sources": [asdict(authority) for authority in AUTHORITIES],
        "stations": [asdict(station) for station in base.STATIONS],
        "parameters": manifest()["parameters"],
        "day_summaries": days,
        "rankable_candidate_count": len(candidates),
        "shortlist": shortlist,
        "selected_geometry": selected,
        "selection_limit": 1,
        "remaining_blocker": (
            "CANDIDATE_SPECIFIC_PHYSICAL_ENVELOPE_AND_STRUCTURAL_QUALIFICATION_"
            "MUST_PASS_BEFORE_ANY_PROSPECTIVE_PLAN_OR_OBSERVATION_ACCESS"
            if selected
            else "NO_PAIR_SUSTAINS_THE_FROZEN_GUARDED_GEOMETRY_AND_NULL_DISCIPLINE"
        ),
        "observation_access": {
            "products_discovered": 0,
            "products_selected": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
        },
        "physical_envelope_compiled": False,
        "prospective_plan_frozen": False,
        "measurement_authorized": False,
        "outcome": OUTCOME_SELECTED if selected else OUTCOME_NONE,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("navigation", type=Path, nargs=5)
    print(strict_json(screen_navigation_set(parser.parse_args().navigation)))
