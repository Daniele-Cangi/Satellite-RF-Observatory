"""Exact model-side envelope for the pre-ranked, unconsumed DRAO DOY238 cell.

This one-use compiler accepts only the exact-hash broadcast-navigation model
input.  It contains no observation locator, decoder, measurement or scorer.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from math import isfinite
from pathlib import Path
import platform
import subprocess
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_geometry_screen as screen,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_physical_envelope as rank1,
)
from experiments.orbital_discriminability import gnss_double_difference_screen as geometry


VERSION: Final = "gnss-drao-labelled-forward-rank2-physical-envelope-v1"
SCOPE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_ENVELOPE_SCOPE.md"
SCOPE_SHA256: Final = "ae2f36efdf907a725e559ee04b239da9e7c64fd06e239c1c396c414f3b90db7f"
PARENT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_GEOMETRY_SCREEN.json"
PARENT_SHA256: Final = "06161af57ada12e081faef7cf470e540ea5fff5dd7cf2f6614077b738852ed62"
RECEIPT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_ENVELOPE.json"
REPORT_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_ENVELOPE_REPORT.md"

OUTCOME_ADMITTED: Final = "DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_MARGIN_ADMITTED"
OUTCOME_DOMINATES: Final = "DRAO_LABELLED_FORWARD_RANK2_PHYSICAL_ENVELOPE_DOMINATES"

RANK: Final = 2
DOY: Final = 238
GPS_DATE: Final = "2026-08-26"
CODEBOOK: Final = ("G14", "G15", "G17", "G20", "G24", "G30")
GPS_START: Final = datetime(2026, 8, 26, 4, 50, 0, tzinfo=timezone.utc)
GPS_STOP: Final = datetime(2026, 8, 26, 5, 59, 0, tzinfo=timezone.utc)
EXPECTED_SCREEN_SEPARATION_M: Final = 36_418.3839726951
EXPECTED_SCREEN_TIMING_ENVELOPE_M: Final = 1_392.8069935469507
EXPECTED_SCREEN_MINIMUM_ELEVATION_DEG: Final = 15.49185774596078

NAVIGATION_NAME: Final = "brdc2380.26n.gz"
NAVIGATION_BYTES: Final = 71_505
NAVIGATION_SHA256: Final = "456036b3e4f247c96d834476cb51cbd88d420e37a6abdae6e6d8b2f7d3526e26"
NAVIGATION_RAW_SHA256: Final = "a3481251cb013f84e12f0442f63d3190afa146b990550e59dafdd74149a26ee1"


class Rank2EnvelopeError(ValueError):
    """A frozen authority, model input or numerical invariant changed."""


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


def _read_json(path: Path) -> dict[str, object]:
    def reject(token: str) -> object:
        raise Rank2EnvelopeError(f"NONFINITE_PARENT:{token}")

    value = json.loads(Path(path).read_text(encoding="ascii"), parse_constant=reject)
    if not isinstance(value, dict):
        raise Rank2EnvelopeError("PARENT_NOT_JSON_OBJECT")
    return value


def _close(actual: float, expected: float, name: str) -> None:
    if not isfinite(actual) or abs(actual - expected) > 1.0e-9:
        raise Rank2EnvelopeError(f"{name}_CHANGED")


def validate_frozen_authority(root: Path) -> dict[str, object]:
    base = Path(root)
    if canonical_sha256(base / SCOPE_NAME) != SCOPE_SHA256:
        raise Rank2EnvelopeError("FROZEN_SCOPE_CHANGED")
    if canonical_sha256(base / PARENT_NAME) != PARENT_SHA256:
        raise Rank2EnvelopeError("FROZEN_PARENT_CHANGED")
    parent = _read_json(base / PARENT_NAME)
    shortlist = parent.get("shortlist")
    if parent.get("outcome") != screen.OUTCOME_SELECTED:
        raise Rank2EnvelopeError("PARENT_OUTCOME_CHANGED")
    if not isinstance(shortlist, list) or len(shortlist) < RANK:
        raise Rank2EnvelopeError("PARENT_RANK2_MISSING")
    selected = shortlist[RANK - 1]
    expected = {
        "doy": DOY,
        "gps_date": GPS_DATE,
        "raw_start_gps": "2026-08-26T04:50:00 GPS",
        "raw_stop_gps": "2026-08-26T05:59:00 GPS",
        "heldout_start_gps": "2026-08-26T05:29:30 GPS",
        "candidate_codebook": list(CODEBOOK),
        "controlling_null": "TIME_REVERSED_GEOMETRY",
    }
    for key, value in expected.items():
        if selected.get(key) != value:
            raise Rank2EnvelopeError(f"PARENT_RANK2_{key.upper()}_CHANGED")
    _close(float(selected["exact_controlling_separation_m"]), EXPECTED_SCREEN_SEPARATION_M, "SCREEN_SEPARATION")
    _close(float(selected["direct_time_shift_envelope_m"]), EXPECTED_SCREEN_TIMING_ENVELOPE_M, "SCREEN_TIMING")
    _close(float(selected["minimum_time_shifted_elevation_deg"]), EXPECTED_SCREEN_MINIMUM_ELEVATION_DEG, "SCREEN_ELEVATION")
    if any(int(value) != 0 for value in parent["observation_access"].values()):
        raise Rank2EnvelopeError("PARENT_OBSERVATION_ACCESS_CHANGED")
    return {
        "scope": {"filename": SCOPE_NAME, "canonical_sha256": SCOPE_SHA256},
        "parent": {
            "filename": PARENT_NAME,
            "canonical_sha256": PARENT_SHA256,
            "outcome": parent["outcome"],
            "rank": RANK,
        },
        "selection_rule": "HIGHEST_RANKED_UNCONSUMED_GEOMETRY_FROM_PRE_OBSERVATION_SHORTLIST",
        "doy237_reopened": False,
    }


def manifest(root: Path) -> dict[str, object]:
    value = {
        "schema": f"{VERSION}-manifest",
        "authority": validate_frozen_authority(root),
        "physical_question": "DOES_PRE_RANKED_DOY238_RETAIN_POSITIVE_EXACT_PHYSICAL_MARGIN",
        "geometry": {
            "station": screen.STATION.station_id,
            "doy": DOY,
            "gps_date": GPS_DATE,
            "codebook": list(CODEBOOK),
            "raw_start_gps": "2026-08-26T04:50:00 GPS",
            "raw_stop_gps": "2026-08-26T05:59:00 GPS",
            "heldout_start_gps": "2026-08-26T05:29:30 GPS",
            "prefix_epochs": screen.PREFIX_EPOCHS,
            "raw_epochs": screen.RAW_EPOCHS,
        },
        "navigation": {
            "filename": NAVIGATION_NAME,
            "bytes": NAVIGATION_BYTES,
            "sha256": NAVIGATION_SHA256,
            "raw_sha256": NAVIGATION_RAW_SHA256,
            "role": "TRANSIENT_BROADCAST_EPHEMERIS_MODEL_ONLY",
        },
        "transform": {
            "one_way_light_time": "ITERATED_RELATIVE_LIGHT_TIME",
            "earth_rotation_during_light_time": True,
            "prefix_nuisance": ["CONSTANT", "RATE"],
            "heldout_refit": False,
            "free_time_phase": False,
        },
        "decision": {
            "rule": "RETARDED_CONTROLLING_SEPARATION_STRICTLY_GREATER_THAN_3B",
            "multiplier": rank1.DECISION_MULTIPLIER,
        },
        "observation_access": {
            "locators": 0,
            "products": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
            "scores": 0,
        },
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def _navigation_candidate():
    matches = tuple(c for c in screen.NAVIGATION_CANDIDATES if c.doy == DOY)
    if len(matches) != 1 or matches[0].name != NAVIGATION_NAME:
        raise Rank2EnvelopeError("NAVIGATION_CANDIDATE_CHANGED")
    return matches[0]


def parse_navigation(payload: bytes | bytearray):
    compressed = bytes(payload)
    if len(compressed) != NAVIGATION_BYTES:
        raise Rank2EnvelopeError("NAVIGATION_COMPRESSED_BYTES_CHANGED")
    if sha256(compressed).hexdigest() != NAVIGATION_SHA256:
        raise Rank2EnvelopeError("NAVIGATION_COMPRESSED_HASH_CHANGED")
    records, authority = screen.parse_navigation_gzip(_navigation_candidate(), compressed)
    if authority.get("uncompressed_sha256") != NAVIGATION_RAW_SHA256:
        raise Rank2EnvelopeError("NAVIGATION_RAW_HASH_CHANGED")
    missing = tuple(sorted(set(CODEBOOK) - set(records)))
    if missing:
        raise Rank2EnvelopeError(f"CODEBOOK_EPHEMERIS_MISSING:{','.join(missing)}")
    return records, authority


def expected_utc_epochs() -> tuple[datetime, ...]:
    start = GPS_START - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    stop = GPS_STOP - timedelta(seconds=geometry.GPS_UTC_OFFSET_S)
    epochs = tuple(start + timedelta(seconds=i * screen.STEP_S) for i in range(screen.RAW_EPOCHS))
    if epochs[-1] != stop:
        raise Rank2EnvelopeError("FROZEN_GRID_CHANGED")
    return epochs


def compile_envelope(payload: bytes | bytearray, root: Path) -> dict[str, object]:
    authority = validate_frozen_authority(root)
    records, nav_authority = parse_navigation(payload)
    epochs = expected_utc_epochs()
    station = rank1._station()
    station_ecef = geometry.station_to_ecef(station)

    retarded: dict[float, np.ndarray] = {}
    transmit: dict[tuple[str, float], tuple[datetime, ...]] = {}
    positions: dict[tuple[str, float], np.ndarray] = {}
    for offset in (0.0, *rank1.TIMING_OFFSETS_S):
        rows = []
        for satellite in CODEBOOK:
            ranges, times, receive_frame = rank1._retarded_series(
                records[satellite], epochs, station_ecef, offset
            )
            rows.append(ranges)
            transmit[(satellite, offset)] = times
            positions[(satellite, offset)] = receive_frame
        retarded[offset] = np.stack(rows)

    shifted = {
        (satellite, offset): retarded[offset][index]
        for offset in rank1.TIMING_OFFSETS_S
        for index, satellite in enumerate(CODEBOOK)
    }
    corrected = screen.evaluate_codebook(
        {satellite: retarded[0.0][index] for index, satellite in enumerate(CODEBOOK)},
        shifted,
    )
    clock_paths = np.stack(
        [
            np.asarray(
                [
                    -geometry.SPEED_OF_LIGHT_M_S
                    * rank1._clock_bias_s(
                        geometry.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in transmit[(satellite, 0.0)]
                ],
                dtype=np.float64,
            )
            for satellite in CODEBOOK
        ]
    )
    _, clock_metrics = rank1._projected_metrics(rank1._center(clock_paths))
    accuracy = {
        satellite: max(
            float(geometry.select_ephemeris(records[satellite], epoch).sv_accuracy_m)
            for epoch in epochs
        )
        for satellite in CODEBOOK
    }
    if any(not isfinite(value) or value < 0.0 for value in accuracy.values()):
        raise Rank2EnvelopeError("BROADCAST_ACCURACY_UNAVAILABLE")

    elevation = {
        offset: np.stack(
            [
                geometry.elevation_deg(positions[(satellite, offset)], station, station_ecef)
                for satellite in CODEBOOK
            ]
        )
        for offset in (0.0, *rank1.TIMING_OFFSETS_S)
    }
    robust_elevation = np.min(np.stack(tuple(elevation.values())), axis=0)
    if np.any(robust_elevation <= 0.0) or not np.all(np.isfinite(robust_elevation)):
        raise Rank2EnvelopeError("RETARDED_ELEVATION_INVALID")
    slant_upper = rank1.ZENITH_DELAY_MAX_M / np.sin(np.radians(robust_elevation))
    tropo_bound, tropo_by_satellite = rank1.transformed_box_peak_to_peak_bound(slant_upper)

    terms = [
        rank1._term("EVENT_TIME_DIRECT_RETARDED_TRAJECTORY_ENVELOPE", float(corrected["direct_time_shift_envelope_m"]), "MODELED_DIRECT_TRAJECTORY_ENVELOPE", "T_PLUS_MINUS_15_S_ON_EACH_RETARDED_TRAJECTORY_THEN_CENTER_AND_PREFIX_PROJECT"),
        rank1._term("BROADCAST_ORBIT_USER_RANGE_ACCURACY_FAMILY", 8.0 * max(accuracy.values()), "MODELED_CONSERVATIVE_INTERVAL", "EIGHT_TIMES_MAXIMUM_SELECTED_EPHEMERIS_SV_ACCURACY_AS_FROZEN_DRAO_FAMILY"),
        rank1._term("OMITTED_BROADCAST_SATELLITE_CLOCK_NONAFFINITY", float(clock_metrics["heldout_max_track_peak_to_peak_m"]), "MODELED_FROM_BROADCAST_CLOCK_FIELDS", "AF0_AF1_AF2_AND_ECCENTRICITY_RELATIVITY_AT_ITERATED_TRANSMIT_TIME"),
        rank1._term("DIFFERENTIAL_TROPOSPHERE_RELAXED_BOX", tropo_bound, "MODELED_CONSERVATIVE_INTERVAL", "PER_EPOCH_ZERO_TO_3_5_M_OVER_SIN_ELEVATION_BOX_PROPAGATED_THROUGH_FULL_LINEAR_OPERATOR"),
        rank1._term("STATION_DISPLACEMENT_EOP_AND_RELATIVITY", rank1.STATION_EOP_RELATIVITY_BOUND_M, "MODELED_CONSERVATIVE_INTERVAL", "FROZEN_DRAO_COMMON_MODE_HELDOUT_INTERVAL"),
    ]
    model_side = sum(float(term["heldout_max_track_peak_to_peak_bound_m"]) for term in terms)
    one_model = model_side + rank1.CAPABILITY_CONDITIONAL_RESERVE_M
    required = rank1.DECISION_MULTIPLIER * one_model
    exact = float(corrected["exact_controlling_separation_m"])
    margin = exact - required
    outcome = OUTCOME_ADMITTED if margin > 0.0 else OUTCOME_DOMINATES

    result = {
        "schema": VERSION,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "dependencies": {
            "python": platform.python_version(),
            "numpy": importlib.metadata.version("numpy"),
        },
        "authority": authority,
        "manifest_sha256": sha256(strict_json(manifest(root)).encode("ascii")).hexdigest(),
        "outcome": outcome,
        "navigation": nav_authority,
        "geometry": {
            "station": screen.STATION.station_id,
            "doy": DOY,
            "gps_date": GPS_DATE,
            "codebook": list(CODEBOOK),
            "raw_start_gps": "2026-08-26T04:50:00 GPS",
            "raw_stop_gps": "2026-08-26T05:59:00 GPS",
            "heldout_start_gps": "2026-08-26T05:29:30 GPS",
            "screen_controlling_separation_m": EXPECTED_SCREEN_SEPARATION_M,
            "retarded_controlling_null": corrected["controlling_null"],
            "retarded_controlling_separation_m": exact,
            "retarded_prefix_affine_separation_m": corrected["prefix_affine_null"]["heldout_max_track_peak_to_peak_m"],
            "retarded_time_reversed_separation_m": corrected["time_reversed_geometry_null"]["heldout_max_track_peak_to_peak_m"],
            "minimum_retarded_nominal_elevation_deg": float(np.min(elevation[0.0])),
            "minimum_retarded_time_shifted_elevation_deg": float(np.min(robust_elevation)),
        },
        "model_side_terms": terms,
        "event_time_metrics": corrected["direct_time_shift_rows"],
        "broadcast_sv_accuracy_m_by_satellite": accuracy,
        "satellite_clock_metrics": clock_metrics,
        "troposphere": {
            "zenith_delay_interval_m": [0.0, rank1.ZENITH_DELAY_MAX_M],
            "heldout_box_bound_m_by_satellite": tropo_by_satellite,
            "heldout_max_track_peak_to_peak_bound_m": tropo_bound,
        },
        "conditional_measurement_reserve": {
            "state": "NOT_YET_ADMITTED",
            "total_m": rank1.CAPABILITY_CONDITIONAL_RESERVE_M,
            "geometry_free_second_difference_limit_m": rank1.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
            "phase_minus_code_per_track_peak_to_peak_limit_m": rank1.CODE_PHASE_PER_SATELLITE_PTP_LIMIT_M,
            "all_six_tracks_all_139_epochs_required": True,
        },
        "envelope": {
            "model_side_m": model_side,
            "conditional_measurement_reserve_m": rank1.CAPABILITY_CONDITIONAL_RESERVE_M,
            "one_model_bound_b_m": one_model,
            "required_separation_3b_m": required,
            "retarded_controlling_separation_m": exact,
            "remaining_physical_margin_m": margin,
        },
        "claim_boundary": {
            "maximum_future_positive_claim": "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
            "receiver_labels_model_conditioned": True,
            "specific_identity_independently_established": False,
        },
        "observation_access": {"locators": 0, "products": 0, "headers": 0, "payload_bytes": 0, "values": 0, "scores": 0},
        "navigation_payloads_retained": 0,
        "primary_selected": False,
        "next_if_admitted": "FREEZE_ONE_INTEGRATED_DOY238_PLAN_BEFORE_OBSERVATION_ARTIFACT_SELECTION",
        "stop": "NO_DOY238_OBSERVATION_QUERY_SELECTION_OR_ACCESS",
    }
    strict_json(result)
    return result


def render_report(value: Mapping[str, object]) -> str:
    geometry_value = value["geometry"]
    envelope = value["envelope"]
    lines = [
        "# DRAO labelled-forward rank-2 physical envelope",
        "",
        f"**{value['outcome']}**",
        "",
        "This audit regenerated only the exact-hash DOY238 broadcast model. It",
        "queried or opened no receiver observation product.",
        "",
        "## Frozen geometry",
        "",
        f"- station: `{geometry_value['station']}`;",
        f"- window: `{geometry_value['raw_start_gps']}--{geometry_value['raw_stop_gps']}`;",
        f"- codebook: `{'/'.join(geometry_value['codebook'])}`;",
        f"- controlling null: `{geometry_value['retarded_controlling_null']}`;",
        f"- exact retarded separation: `{envelope['retarded_controlling_separation_m']:.6f} m`.",
        "",
        "## Envelope",
        "",
        f"- model-side bound: `{envelope['model_side_m']:.6f} m`;",
        f"- conditional measurement reserve: `{envelope['conditional_measurement_reserve_m']:.6f} m`;",
        f"- one-model `B`: `{envelope['one_model_bound_b_m']:.6f} m`;",
        f"- required `3B`: `{envelope['required_separation_3b_m']:.6f} m`;",
        f"- remaining margin: `{envelope['remaining_physical_margin_m']:.6f} m`.",
        "",
        "The measurement reserve remains conditional. This result admits no",
        "measurement, primary, receiver artifact or orbital claim.",
        "",
        "## Stop",
        "",
        "Stop before any DOY238 observation lookup. If admitted, the next maximum",
        "action is one offline integrated-plan freeze, not another structural gate.",
        "",
    ]
    return "\n".join(lines)


def _write_once(path: Path, content: str) -> None:
    if path.exists():
        raise Rank2EnvelopeError(f"REFUSE_OVERWRITE:{path.name}")
    path.write_text(content, encoding="ascii", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("navigation_gzip", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    if args.navigation_gzip.name != NAVIGATION_NAME:
        raise SystemExit("SUPPLY_EXACT_FROZEN_DOY238_NAVIGATION_PRODUCT")
    result = compile_envelope(args.navigation_gzip.read_bytes(), args.output_dir)
    _write_once(args.output_dir / RECEIPT_NAME, strict_json(result, pretty=True) + "\n")
    _write_once(args.output_dir / REPORT_NAME, render_report(result))
    print(result["outcome"])


if __name__ == "__main__":
    main()
