"""Bounded orbit-only ranking for one held-out GNSS observer C.

The compiler evaluates four station coordinates already frozen in a prior IGS
metadata receipt and three already frozen broadcast-navigation days.  It has
no observation-product locator, header, decoder, carrier-phase value or
capability-discovery input surface.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
import importlib.metadata
import json
from math import sin
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as inherited,
)
from experiments.orbital_discriminability import (
    gnss_double_difference_screen as geometry,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_next_primary_screen as navigation,
)
from experiments.orbital_discriminability import (
    gnss_observer_transfer_spike as transfer,
)
from experiments.orbital_discriminability import (
    gnss_phase_independent_pair_screen as station_scope,
)


SCREEN_VERSION: Final = "gnss-observer-transfer-geometry-v1"
RECEIPT_NAME: Final = "GNSS_OBSERVER_TRANSFER_GEOMETRY_RECEIPT.json"
OUTCOME_SHORTLISTED: Final = "OBSERVER_TRANSFER_GEOMETRY_SHORTLISTED"
OUTCOME_NONE: Final = "NO_OBSERVER_TRANSFER_GEOMETRY"

OBSERVER_SPIKE_RECEIPT: Final = transfer.RECEIPT_NAME
OBSERVER_SPIKE_SHA256: Final = (
    "e60e130e051626ebbae02aa655ade26071fd1dddd7f79a4f7ff131d476d3f4c5"
)
STATION_SCOPE_RECEIPT: Final = station_scope.RECEIPT_NAME
STATION_SCOPE_SHA256: Final = (
    "24ea926f667749500cd380ebf3c2bd68d730e7faaa84572b0b0bc31bfaba679c"
)
NAVIGATION_SCOPE_RECEIPT: Final = navigation.RECEIPT_NAME
NAVIGATION_SCOPE_SHA256: Final = (
    "2e5af124d25475900eb8b8f88535bb5ac70da10f6f2f3a796fe6f66699b330b3"
)

TARGET: Final = "G22"
REFERENCE: Final = "G30"
WRONG_ORBITS: Final = ("G01", "G14", "G17")
MODEL_SATELLITES: Final = (TARGET, REFERENCE, *WRONG_ORBITS)
STEP_S: Final = 30.0
RAW_EPOCHS: Final = transfer.SAMPLE_COUNT
WITNESS_PREFIX_EPOCHS: Final = transfer.WITNESS_PREFIX_EPOCHS
CONFIRMATION_EPOCHS: Final = transfer.CONFIRMATION_EPOCHS
CONFIRMATION_START: Final = transfer.CONFIRMATION_START
SHORTLIST_SIZE: Final = 3

CANDIDATE_IDS: Final = (
    "DRAO00CAN",
    "WES200USA",
    "PIE100USA",
    "AMC400USA",
)
CANDIDATES: Final = tuple(
    candidate
    for candidate in station_scope.CANDIDATES
    if candidate.station_id in CANDIDATE_IDS
)
NAVIGATION_CANDIDATES: Final = navigation.NAVIGATION_CANDIDATES

EXPECTED_NAVIGATION: Final = {
    221: {
        "compressed_bytes": 71_457,
        "compressed_sha256": (
            "ac512aaaa875a9807c152785427f0e40316710fad1d72d5d6c584389c997963e"
        ),
        "uncompressed_bytes": 294_875,
        "uncompressed_sha256": (
            "762c18808dac8cc85b252ce6efe05a2ca87caefb8ebf286e9aabbb475470b771"
        ),
    },
    222: {
        "compressed_bytes": 71_479,
        "compressed_sha256": (
            "e56961025c43476f57a4c087adc20b9ce7f073192394607a17f57a26ff34a025"
        ),
        "uncompressed_bytes": 299_914,
        "uncompressed_sha256": (
            "b6aabea7c103341c39b2cb90a15501b4096280e897d08c71a9f0c5067c513179"
        ),
    },
    223: {
        "compressed_bytes": 71_403,
        "compressed_sha256": (
            "deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478"
        ),
        "uncompressed_bytes": 298_710,
        "uncompressed_sha256": (
            "340bf5e84504420d6770476c8f3c9cda78722fcc283cd34385f47b77ba6f4d2e"
        ),
    },
}


class ObserverGeometryError(ValueError):
    """A parent authority, bounded scope or numerical invariant changed."""


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


def _validate_candidate_scope() -> None:
    ids = tuple(candidate.station_id for candidate in CANDIDATES)
    if ids != CANDIDATE_IDS:
        raise ObserverGeometryError("CANDIDATE_OBSERVER_SCOPE_CHANGED")
    if set(ids) & {"GOLD00USA", "NLIB00USA", "ALGO00CAN", "MDO100USA"}:
        raise ObserverGeometryError("CONSUMED_OBSERVER_REENTERED")
    if tuple(candidate.doy for candidate in NAVIGATION_CANDIDATES) != (221, 222, 223):
        raise ObserverGeometryError("NAVIGATION_DAY_SCOPE_CHANGED")


def validate_parent_receipts(root: Path) -> dict[str, dict[str, object]]:
    expected = (
        (
            OBSERVER_SPIKE_RECEIPT,
            OBSERVER_SPIKE_SHA256,
            transfer.OUTCOME_DISCRIMINATIVE,
        ),
        (
            STATION_SCOPE_RECEIPT,
            STATION_SCOPE_SHA256,
            station_scope.OUTCOME_SHORTLISTED,
        ),
        (
            NAVIGATION_SCOPE_RECEIPT,
            NAVIGATION_SCOPE_SHA256,
            navigation.OUTCOME_SELECTED,
        ),
    )
    result: dict[str, dict[str, object]] = {}
    for name, digest, outcome in expected:
        path = Path(root) / name
        if not path.is_file() or canonical_sha256(path) != digest:
            raise ObserverGeometryError(f"PARENT_RECEIPT_CHANGED:{name}")
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
        if value.get("outcome") != outcome:
            raise ObserverGeometryError(f"PARENT_OUTCOME_CHANGED:{name}")
        result[name] = {
            "canonical_sha256": digest,
            "outcome": outcome,
            "role": "CLOSED_AGGREGATE_AUTHORITY_NO_OBSERVATION_VALUES_REOPENED",
        }
    return result


def _station(candidate: station_scope.CandidateStation) -> geometry.Station:
    return geometry.Station(
        candidate.station_id,
        candidate.latitude_deg,
        candidate.longitude_deg,
        candidate.height_m,
        "UNKNOWN_NOT_REQUIRED_FOR_ORBIT_ONLY_RANKING",
        candidate.receiver,
        candidate.antenna,
        "ROBOT",
        f"{candidate.station_id}_{candidate.domes}",
        candidate.station_page_url,
    )


def manifest() -> dict[str, object]:
    _validate_candidate_scope()
    value = {
        "schema": "gnss-observer-transfer-geometry-manifest-v1",
        "screen_version": SCREEN_VERSION,
        "physical_question": (
            "DOES_THE_FROZEN_G22_MINUS_G30_PHASE_PREDICTION_RETAIN_POSITIVE_"
            "ORBITAL_VERSUS_NULL_MARGIN_AT_ONE_UNSEEN_OBSERVER_C"
        ),
        "new_information": (
            "WHICH_UNUSED_OBSERVER_AND_POST_AB_DATE_HAS_THE_STRONGEST_COMPLETE_"
            "ONE_ANCHOR_HELDOUT_ORBITAL_DISCRIMINABILITY"
        ),
        "why_existing_experiment_cannot_answer": (
            "GOLD_NLIB_REPEATED_THE_RESULT_ON_THE_SAME_ROOTS_AND_THE_SYNTHETIC_"
            "SPIKE_DID_NOT_TEST_REAL_OBSERVER_GEOMETRY"
        ),
        "minimum_experiment": (
            "FOUR_PREDECLARED_UNUSED_OBSERVERS_TIMES_THREE_FROZEN_BROADCAST_"
            "NAVIGATION_DAYS_WITHOUT_OBSERVATION_PRODUCT_DISCOVERY"
        ),
        "stop_condition": (
            "STOP_WITH_THREE_DISTINCT_OBSERVER_CASES_OR_NO_POSITIVE_GEOMETRY_"
            "BEFORE_CAPABILITY_DISCOVERY"
        ),
        "parent_receipts": {
            OBSERVER_SPIKE_RECEIPT: OBSERVER_SPIKE_SHA256,
            STATION_SCOPE_RECEIPT: STATION_SCOPE_SHA256,
            NAVIGATION_SCOPE_RECEIPT: NAVIGATION_SCOPE_SHA256,
        },
        "candidate_observers": [asdict(candidate) for candidate in CANDIDATES],
        "candidate_navigation": [
            asdict(candidate) for candidate in NAVIGATION_CANDIDATES
        ],
        "candidate_scope_predeclared": True,
        "excluded_roots": {
            "GOLD00USA_NLIB00USA": "DISCOVERY_AND_REPLICATION_OBSERVERS_A_B",
            "ALGO00CAN_MDO100USA": "CONSUMED_FAILED_PRIMARY_PATHS",
        },
        "hypotheses": {
            "target": TARGET,
            "reference": REFERENCE,
            "frozen_affine": (
                "ZERO_INTERCEPT_RATE_DERIVED_FROM_TARGET_PREDICTION_ONLY_"
                "BEFORE_ANY_OBSERVER_VALUE"
            ),
            "wrong_orbits": list(WRONG_ORBITS),
        },
        "coordinate": {
            **transfer.manifest()["coordinate"],
            "station_satellite_order": "C_G22_MINUS_C_G30",
        },
        "partition": {
            "raw_epochs": RAW_EPOCHS,
            "cadence_s": STEP_S,
            "witness_prefix_epochs": WITNESS_PREFIX_EPOCHS,
            "confirmation_epochs": CONFIRMATION_EPOCHS,
            "confirmation_start_index": CONFIRMATION_START,
            "window_shortening": "FORBIDDEN",
        },
        "visibility": {
            "minimum_elevation_deg": geometry.MINIMUM_ELEVATION_DEG,
            "required_satellites": list(MODEL_SATELLITES),
            "scope": (
                "ALL_139_EPOCHS_AT_ONE_OBSERVER_FOR_EVERY_MODEL_AND_"
                "DIRECT_TIME_SHIFT"
            ),
        },
        "physical_envelope": {
            "event_time_offsets_s": [
                -inherited.MAX_STATION_EPOCH_ERROR_S,
                inherited.MAX_STATION_EPOCH_ERROR_S,
            ],
            "direct_shifted_trajectories": True,
            "common_receiver_clock": "CANCELS",
            "signal_specific_hardware": (
                "REQUIRES_PREDECLARED_C_PREFIX_ADMISSION"
            ),
            "pairwise_multiplier": inherited.PAIRWISE_ENVELOPE_MULTIPLIER,
        },
        "selection_rule": [
            "STRICT_POSITIVE_REMAINING_PHYSICAL_MARGIN",
            "BEST_DATE_WINDOW_PER_OBSERVER",
            "DISTINCT_OBSERVERS_ONLY",
            "MAXIMUM_REMAINING_PHYSICAL_MARGIN",
            "MAXIMUM_CONTROLLING_HELDOUT_SEPARATION",
            "MAXIMUM_MINIMUM_MODEL_ELEVATION",
            "EARLIEST_GPS_START",
        ],
        "observation_boundary": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "decoder_present": False,
            "network_capability": False,
        },
        "prospective_plan_frozen": False,
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


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
            record = geometry.select_ephemeris(records[satellite], shifted)
            result[index] = geometry.broadcast_ecef(record, shifted)
        except (KeyError, geometry.GnssDoubleDifferenceError):
            continue
    return result


def _format_utc(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def _format_gps(value: datetime) -> str:
    gps = value + timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    return gps.isoformat(timespec="seconds").replace("+00:00", " GPS")


def _troposphere_term(
    target_elevation_deg: Sequence[float],
    reference_elevation_deg: Sequence[float],
) -> dict[str, object]:
    target = np.asarray(target_elevation_deg, dtype=np.float64)
    reference = np.asarray(reference_elevation_deg, dtype=np.float64)
    floor = sin(np.radians(geometry.MINIMUM_ELEVATION_DEG))
    shape = 1.0 / np.maximum(np.sin(np.radians(target)), floor)
    shape -= 1.0 / np.maximum(np.sin(np.radians(reference)), floor)
    maximum_curve = transfer.anchored_coordinate(
        inherited.MAX_ZENITH_TROPOSPHERE_M * shape
    )
    return {
        "term": "STATION_C_DIFFERENTIAL_TROPOSPHERE",
        "state": "MODELED_INTERVAL",
        "provenance": "INDEPENDENT_OF_FUTURE_C_OBSERVATION",
        "zenith_delay_interval_m": [0.0, inherited.MAX_ZENITH_TROPOSPHERE_M],
        "heldout_peak_to_peak_bound_m": float(
            np.ptp(maximum_curve[CONFIRMATION_START:])
        ),
        "basis": "CONSERVATIVE_ONE_OVER_SINE_TARGET_MINUS_REFERENCE_MAPPING",
    }


def _case_sort_key(row: Mapping[str, object]) -> tuple[float, float, float, str]:
    return (
        -float(row["remaining_physical_margin_m"]),
        -float(row["controlling_heldout_separation_m"]),
        -float(row["minimum_model_elevation_deg"]),
        str(row["raw_start_gps"]),
    )


def rank_distinct_observers(
    cases: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    best_by_observer: dict[str, dict[str, object]] = {}
    for source in cases:
        row = dict(source)
        if (
            not bool(row["joint_visibility_complete"])
            or float(row["remaining_physical_margin_m"]) <= 0.0
        ):
            continue
        station = str(row["station_id"])
        current = best_by_observer.get(station)
        if current is None or _case_sort_key(row) < _case_sort_key(current):
            best_by_observer[station] = row
    ranked = sorted(
        best_by_observer.values(),
        key=lambda row: (
            -float(row["remaining_physical_margin_m"]),
            -float(row["controlling_heldout_separation_m"]),
            -float(row["minimum_model_elevation_deg"]),
            str(row["raw_start_gps"]),
            str(row["station_id"]),
        ),
    )
    return ranked


def compile_station_day(
    candidate: navigation.NavigationCandidate,
    records: Mapping[str, tuple[geometry.GpsEphemeris, ...]],
    observer_authority: station_scope.CandidateStation,
    position_cache: dict[tuple[str, float], np.ndarray] | None = None,
) -> dict[str, object]:
    epochs = navigation.gps_day_grid(candidate)
    observer = _station(observer_authority)
    station_ecef = geometry.station_to_ecef(observer)
    offsets = (
        -inherited.MAX_STATION_EPOCH_ERROR_S,
        0.0,
        inherited.MAX_STATION_EPOCH_ERROR_S,
    )
    owns_cache = position_cache is None
    cache: dict[tuple[str, float], np.ndarray] = (
        {} if position_cache is None else position_cache
    )

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, float(offset_s)
        if key not in cache:
            cache[key] = _position_series(records, satellite, epochs, offset_s)
        return cache[key]

    for satellite in MODEL_SATELLITES:
        for offset in offsets:
            positions(satellite, offset)

    shifted_elevations = {
        (satellite, offset): geometry.elevation_deg(
            positions(satellite, offset), observer, station_ecef
        )
        for satellite in MODEL_SATELLITES
        for offset in offsets
    }
    elevations = {
        satellite: shifted_elevations[(satellite, 0.0)]
        for satellite in MODEL_SATELLITES
    }
    visible = np.ones(len(epochs), dtype=bool)
    for values in shifted_elevations.values():
        visible &= np.isfinite(values)
        visible &= values >= geometry.MINIMUM_ELEVATION_DEG
    starts = navigation.candidate_window_starts(visible)

    def full_coordinate(target: str, offset_s: float = 0.0) -> np.ndarray:
        target_range = np.linalg.norm(
            positions(target, offset_s) - station_ecef, axis=1
        )
        reference_range = np.linalg.norm(
            positions(REFERENCE, offset_s) - station_ecef, axis=1
        )
        return transfer.single_observer_quotient_m(target_range, reference_range)

    nominal = {
        satellite: full_coordinate(satellite)
        for satellite in (TARGET, *WRONG_ORBITS)
    }
    timing = {
        (satellite, offset): full_coordinate(satellite, offset)
        for satellite in (TARGET, *WRONG_ORBITS)
        for offset in offsets
    }
    elapsed = np.arange(RAW_EPOCHS, dtype=np.float64) * STEP_S
    best: dict[str, object] | None = None

    for start in starts:
        window = slice(start, start + RAW_EPOCHS)
        target = nominal[TARGET][window]
        affine, affine_rate = transfer.frozen_adversarial_affine_null(
            target, elapsed
        )
        nulls: list[dict[str, object]] = [
            {
                "name": "FROZEN_AFFINE_NULL",
                **transfer.separation_metrics(target, affine),
            }
        ]
        for satellite in WRONG_ORBITS:
            nulls.append(
                {
                    "name": f"WRONG_ORBIT_{satellite}",
                    **transfer.separation_metrics(target, nominal[satellite][window]),
                }
            )
        nulls.sort(
            key=lambda row: (
                float(row["heldout_peak_to_peak_m"]), str(row["name"])
            )
        )
        controlling = nulls[0]
        timing_candidates = []
        for satellite in (TARGET, *WRONG_ORBITS):
            nominal_model = transfer.anchored_coordinate(
                nominal[satellite][window]
            )
            for offset in (
                -inherited.MAX_STATION_EPOCH_ERROR_S,
                inherited.MAX_STATION_EPOCH_ERROR_S,
            ):
                delta = (
                    transfer.anchored_coordinate(timing[(satellite, offset)][window])
                    - nominal_model
                )
                timing_candidates.append(
                    (
                        float(np.ptp(delta[CONFIRMATION_START:])),
                        satellite,
                        float(offset),
                    )
                )
        timing_bound, timing_model, timing_offset = max(timing_candidates)
        timing_term = {
            "term": "STATION_C_EVENT_TIME",
            "state": "MODELED_DIRECT_TRAJECTORY_ENVELOPE",
            "provenance": "STRUCTURAL_HALF_CADENCE_BOUND",
            "parameter_interval_s": [
                -inherited.MAX_STATION_EPOCH_ERROR_S,
                inherited.MAX_STATION_EPOCH_ERROR_S,
            ],
            "controlling_model_family": timing_model,
            "controlling_offset_s": timing_offset,
            "heldout_peak_to_peak_bound_m": timing_bound,
            "basis": (
                "COMMON_C_TIMESTAMP_SHIFT_APPLIED_DIRECTLY_TO_BOTH_TRAJECTORIES"
            ),
        }
        troposphere_candidates = []
        for satellite in (TARGET, *WRONG_ORBITS):
            term = _troposphere_term(
                elevations[satellite][window], elevations[REFERENCE][window]
            )
            troposphere_candidates.append(
                (float(term["heldout_peak_to_peak_bound_m"]), satellite, term)
            )
        _, troposphere_model, troposphere_term = max(troposphere_candidates)
        troposphere_term["controlling_model_family"] = troposphere_model
        terms = [
            timing_term,
            troposphere_term,
            transfer.quantization_term(),
        ]
        terms.extend(
            transfer.per_link_interval_term(definition)
            for definition in inherited.GENERIC_PATH_BOUNDS_M
        )
        decision = transfer.combine_envelope(
            float(controlling["heldout_peak_to_peak_m"]), terms
        )
        for term in terms:
            term["pairwise_contribution_m"] = float(
                inherited.PAIRWISE_ENVELOPE_MULTIPLIER
                * float(term["heldout_peak_to_peak_bound_m"])
            )
        terms.sort(
            key=lambda term: (
                -float(term["pairwise_contribution_m"]), str(term["term"])
            )
        )
        minimum_by_satellite = {
            satellite: float(np.min(elevations[satellite][window]))
            for satellite in MODEL_SATELLITES
        }
        minimum_shifted = float(
            min(
                np.min(values[window])
                for values in shifted_elevations.values()
            )
        )
        start_utc = epochs[start]
        stop_utc = epochs[start + RAW_EPOCHS - 1]
        row = {
            "station_id": observer_authority.station_id,
            "doy": candidate.doy,
            "gps_date": candidate.gps_date,
            "raw_start_gps": _format_gps(start_utc),
            "raw_stop_gps": _format_gps(stop_utc),
            "raw_start_utc": _format_utc(start_utc),
            "raw_stop_utc": _format_utc(stop_utc),
            "heldout_start_gps": _format_gps(
                start_utc + timedelta(seconds=CONFIRMATION_START * STEP_S)
            ),
            "joint_visibility_complete": True,
            "minimum_elevation_deg_by_model_satellite": minimum_by_satellite,
            "minimum_model_elevation_deg": min(minimum_by_satellite.values()),
            "minimum_time_shifted_model_elevation_deg": minimum_shifted,
            "frozen_affine_rate_m_s": affine_rate,
            "nulls": nulls,
            "controlling_null": controlling["name"],
            "controlling_heldout_separation_m": controlling[
                "heldout_peak_to_peak_m"
            ],
            "physical_terms": terms,
            **decision,
        }
        if best is None or _case_sort_key(row) < _case_sort_key(best):
            best = row

    if owns_cache:
        for values in cache.values():
            values.fill(0.0)
    return {
        "station_id": observer_authority.station_id,
        "doy": candidate.doy,
        "gps_date": candidate.gps_date,
        "joint_visible_epoch_count": int(np.sum(visible)),
        "candidate_window_count": len(starts),
        "best_window": best,
        "case_admitted": (
            best is not None
            and float(best["remaining_physical_margin_m"]) > 0.0
        ),
    }


def _parse_navigation_payloads(
    payloads: Mapping[int, bytes],
) -> tuple[
    dict[int, Mapping[str, tuple[geometry.GpsEphemeris, ...]]],
    list[dict[str, object]],
]:
    expected_doys = {candidate.doy for candidate in NAVIGATION_CANDIDATES}
    if set(payloads) != expected_doys:
        raise ObserverGeometryError("NAVIGATION_PAYLOAD_SET_CHANGED")
    parsed: dict[int, Mapping[str, tuple[geometry.GpsEphemeris, ...]]] = {}
    authorities: list[dict[str, object]] = []
    for candidate in NAVIGATION_CANDIDATES:
        records, authority = navigation.parse_navigation_gzip(
            candidate, payloads[candidate.doy]
        )
        frozen = EXPECTED_NAVIGATION[candidate.doy]
        for field, expected in frozen.items():
            if authority[field] != expected:
                raise ObserverGeometryError(
                    f"NAVIGATION_AUTHORITY_CHANGED_DOY_{candidate.doy}:{field}"
                )
        parsed[candidate.doy] = records
        authorities.append(authority)
    return parsed, authorities


def compile_screen(
    payloads: Mapping[int, bytes],
    root: Path,
) -> dict[str, object]:
    _validate_candidate_scope()
    parents = validate_parent_receipts(root)
    records_by_doy, navigation_authority = _parse_navigation_payloads(payloads)
    cases = []
    for candidate in NAVIGATION_CANDIDATES:
        day_cache: dict[tuple[str, float], np.ndarray] = {}
        for observer in CANDIDATES:
            cases.append(
                compile_station_day(
                    candidate,
                    records_by_doy[candidate.doy],
                    observer,
                    day_cache,
                )
            )
        for values in day_cache.values():
            values.fill(0.0)
    best_windows = [
        case["best_window"]
        for case in cases
        if case["best_window"] is not None
    ]
    ranked = rank_distinct_observers(best_windows)
    shortlist = ranked[:SHORTLIST_SIZE]
    result = {
        "schema": "gnss-observer-transfer-geometry-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": dependency_versions(),
        "manifest_sha256": manifest_sha256(),
        "parent_receipts": parents,
        "navigation": navigation_authority,
        "case_results": cases,
        "observer_ranking": ranked,
        "shortlist": shortlist,
        "selected": shortlist[0] if shortlist else None,
        "outcome": OUTCOME_SHORTLISTED if shortlist else OUTCOME_NONE,
        "observation_access": {
            "product_locators": 0,
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "prospective_plan_frozen": False,
        "capability_selected": False,
        "next_maximum": (
            "REVIEW_BEFORE_ONE_OBSERVER_CAPABILITY_DISCOVERY"
            if shortlist
            else "STOP_NO_POSITIVE_OBSERVER_TRANSFER_GEOMETRY"
        ),
        "stop": "NO_OBSERVATION_PRODUCT_DISCOVERY_OR_ACCESS",
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def _write_json(path: Path, value: object) -> None:
    if Path(path).exists():
        raise ObserverGeometryError("GEOMETRY_RECEIPT_ALREADY_EXISTS")
    Path(path).write_bytes((strict_json(value, pretty=True) + "\n").encode("ascii"))


def main() -> None:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--navigation-gzip", type=Path, action="append", required=True
    )
    parser.add_argument("--output", type=Path, default=root / RECEIPT_NAME)
    args = parser.parse_args()
    supplied = {path.name: path for path in args.navigation_gzip}
    expected = {candidate.name: candidate for candidate in NAVIGATION_CANDIDATES}
    if len(supplied) != len(args.navigation_gzip) or set(supplied) != set(expected):
        raise SystemExit("SUPPLY_EXACTLY_THE_THREE_FROZEN_NAVIGATION_PRODUCTS")
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
