"""Bounded broadcast-only geometry screen for the continuous-phase quotient.

The candidate set is frozen to the existing exact-hash DOY 216--220
navigation authorities and GOLD/NLIB observer geometry. Observation products
are not inputs. Historical G14 and G17 are excluded entirely and the closed
G11/G21 pair is excluded as a pair.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as old
from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair
from experiments.orbital_discriminability import gnss_phase_quotient_spike as phase


SCREEN_VERSION: Final = "gold-nlib-continuous-phase-geometry-screen-v1"
PHASE_SPIKE_RECEIPT_NAME: Final = "GNSS_PHASE_QUOTIENT_SPIKE_RECEIPT.json"
PHASE_SPIKE_RECEIPT_CANONICAL_BYTES: Final = 8_811
PHASE_SPIKE_RECEIPT_SHA256: Final = (
    "12a93c7f52799042d062747e322568d78d2197721ce05cb84c6214ed36a431e1"
)
EXCLUDED_SATELLITES: Final = frozenset({"G14", "G17"})
EXCLUDED_PAIRS: Final = (frozenset({"G11", "G21"}),)
SHORTLIST_SIZE: Final = 3
OUTCOME_SELECTED: Final = "GNSS_PHASE_GEOMETRY_SELECTED"
OUTCOME_NONE: Final = "NO_POSITIVE_PHASE_GEOMETRY_IN_BOUNDED_SET"


class PhaseGeometryScreenError(ValueError):
    """The frozen candidate set, mechanism receipt or numerical result changed."""


def manifest() -> dict[str, object]:
    return {
        "screen_version": SCREEN_VERSION,
        "physical_question": (
            "DOES_A_NEW_GOLD_NLIB_GPS_GEOMETRY_RETAIN_POSITIVE_CONTINUOUS_"
            "PHASE_MARGIN_AGAINST_PREFIX_AFFINE_AND_JOINTLY_VISIBLE_WRONG_"
            "ORBITS_AFTER_THE_COMPLETE_FROZEN_PHYSICAL_ENVELOPE"
        ),
        "new_information": (
            "WHICH_NEW_ORBIT_PAIR_IF_ANY_CAN_SUPPORT_A_FUTURE_INTERPRETABLE_"
            "NEGATIVE_IN_THE_PHASE_COORDINATE"
        ),
        "why_existing_cannot_answer": (
            "G14_G17_IS_POST_SELECTION_DEVELOPMENT_ONLY_AND_THE_OLD_SCREEN_"
            "RANKED_FREQUENCY_SEPARATION_BEFORE_PHYSICAL_MARGIN"
        ),
        "minimum_experiment": (
            "FIVE_EXACT_HASH_BROADCAST_NAV_FILES_TWO_FIXED_OBSERVER_GEOMETRIES_"
            "NO_OBSERVATION_PRODUCT"
        ),
        "stop_condition": (
            "STOP_BEFORE_PRODUCT_DISCOVERY_IF_NO_CANDIDATE_HAS_STRICT_POSITIVE_"
            "PHASE_PHYSICAL_MARGIN"
        ),
        "navigation": [asdict(authority) for authority in pair.AUTHORITIES],
        "stations": [station.station_id for station in base.STATIONS],
        "signal_family": {
            "core_phase": ["L1C", "L2W"],
            "continuity": ["LLI_L1C", "LLI_L2W", "GEOMETRY_FREE_PHASE"],
            "same_path_code": ["C1C", "C2W"],
            "optional_diagnostic": ["S1C", "S2W"],
        },
        "excluded_satellites": sorted(EXCLUDED_SATELLITES),
        "excluded_pairs": [sorted(value) for value in EXCLUDED_PAIRS],
        "candidate_window_rule": (
            "ONE_GUARD_MAXIMIZING_60_PREROLL_PLUS_386_RAW_EPOCH_WINDOW_PER_"
            "UNORDERED_PAIR_AND_DATE_IDENTICAL_TO_FROZEN_ORBIT_PAIR_SCREEN"
        ),
        "partition": {
            "grid_step_s": base.GRID_STEP_S,
            "minimum_elevation_deg": base.MINIMUM_ELEVATION_DEG,
            "pre_roll_epochs": pair.PRE_ROLL_EPOCHS,
            "raw_epochs": pair.RAW_EPOCHS,
            "feature_epochs": pair.FEATURE_EPOCHS,
            "calibration_epochs": pair.CALIBRATION_EPOCHS,
            "heldout_epochs": pair.HELDOUT_EPOCHS,
        },
        "coordinate_manifest_sha256": phase.manifest_sha256(),
        "phase_spike_receipt": {
            "name": PHASE_SPIKE_RECEIPT_NAME,
            "canonical_bytes": PHASE_SPIKE_RECEIPT_CANONICAL_BYTES,
            "canonical_sha256": PHASE_SPIKE_RECEIPT_SHA256,
        },
        "nulls": [
            "PREFIX_CONSTANT_PLUS_RANGE_RATE_FIT_ON_FIRST_77_EPOCHS_ONLY",
            "EVERY_OTHER_JOINTLY_VISIBLE_HEALTHY_GPS_ORBIT_ON_SAME_WINDOW",
        ],
        "ranking": (
            "STRICT_POSITIVE_REMAINING_PHASE_PHYSICAL_MARGIN_DESCENDING_THEN_"
            "CONTROLLING_SEPARATION_GUARD_DATE_TARGET_REFERENCE_DISTINCT_PAIRS"
        ),
        "measurement_envelope": {
            "rinex_phase_quantization": "INCLUDED",
            "event_time_half_cadence": "INCLUDED_DIRECT_TRAJECTORY",
            "structural_coverage_and_witnesses": "NOT_EVALUATED",
        },
        "forbidden": [
            "G14 or G17 candidate participation",
            "closed G11 G21 pair reuse",
            "observation product discovery selection header or payload access",
            "ranking by raw separation alone",
            "post-result candidate window signal null or bound change",
            "prospective plan freeze or measurement authority",
            "new gate or generic framework",
        ],
    }


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def validate_phase_spike_receipt(path: Path) -> dict[str, object]:
    path = Path(path)
    if path.name != PHASE_SPIKE_RECEIPT_NAME or not path.is_file():
        raise PhaseGeometryScreenError("wrong phase-spike receipt")
    canonical = path.read_bytes().replace(b"\r\n", b"\n")
    if len(canonical) != PHASE_SPIKE_RECEIPT_CANONICAL_BYTES:
        raise PhaseGeometryScreenError("phase-spike receipt byte count changed")
    if sha256(canonical).hexdigest() != PHASE_SPIKE_RECEIPT_SHA256:
        raise PhaseGeometryScreenError("phase-spike receipt SHA-256 changed")
    receipt = json.loads(canonical)
    if receipt.get("outcome") != phase.OUTCOME_DISCRIMINATIVE:
        raise PhaseGeometryScreenError("phase mechanism is not discriminative")
    if receipt.get("fixture_role") != "HISTORICAL_DEVELOPMENT_ONLY_NEVER_PRIMARY":
        raise PhaseGeometryScreenError("historical fixture role changed")
    if any(receipt.get("observation_access", {}).values()):
        raise PhaseGeometryScreenError("phase-spike observation boundary changed")
    if receipt.get("new_candidate_selected") is not False:
        raise PhaseGeometryScreenError("phase spike already selected a candidate")
    return receipt


def candidate_is_allowed(candidate: Mapping[str, object]) -> tuple[bool, str | None]:
    target = str(candidate["target"])
    reference = str(candidate["reference"])
    if target in EXCLUDED_SATELLITES or reference in EXCLUDED_SATELLITES:
        return False, "HISTORICAL_PHASE_DEVELOPMENT_SATELLITE_EXCLUDED"
    if frozenset((target, reference)) in EXCLUDED_PAIRS:
        return False, "CLOSED_G11_G21_PAIR_EXCLUDED"
    return True, None


def _gps_index(epochs: Sequence, label: str) -> int:
    matches = [
        index for index, epoch in enumerate(epochs) if base.format_gps(epoch) == label
    ]
    if len(matches) != 1:
        raise PhaseGeometryScreenError(f"candidate GPS epoch missing: {label}")
    return matches[0]


def _rank_candidates(candidates: Sequence[dict[str, object]]) -> list[dict[str, object]]:
    positive = [
        dict(candidate)
        for candidate in candidates
        if float(candidate["remaining_physical_margin_m"]) > 0.0
    ]
    positive.sort(
        key=lambda row: (
            -float(row["remaining_physical_margin_m"]),
            -float(row["controlling_heldout_separation_m"]),
            -float(row["guarded_block_minimum_elevation_deg"]),
            int(row["doy"]),
            str(row["target"]),
            str(row["reference"]),
        )
    )
    distinct = base.distinct_shortlist(positive, SHORTLIST_SIZE)
    for rank, row in enumerate(distinct, start=1):
        row["rank"] = rank
        row["selection_state"] = (
            "PHASE_GEOMETRY_SELECTED" if rank == 1 else "LOWER_RANKED_NOT_SELECTED"
        )
    return distinct


def _compile_day(path: Path, authority: pair.NavigationAuthority) -> dict[str, object]:
    rate_day = pair.screen_day(path, authority)
    raw_candidates = rate_day.pop("rankable_candidates")
    allowed = []
    exclusions: dict[str, int] = {}
    for candidate in raw_candidates:
        admitted, reason = candidate_is_allowed(candidate)
        if admitted:
            allowed.append(candidate)
        else:
            exclusions[reason] = exclusions.get(reason, 0) + 1

    records = base.parse_gps_navigation(path)
    epochs = pair.gps_day_grid(authority)
    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    position_cache: dict[tuple[str, float], np.ndarray] = {}

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, offset_s
        if key not in position_cache:
            shifted_epochs = tuple(
                epoch + timedelta(seconds=offset_s) for epoch in epochs
            )
            position_cache[key] = np.asarray(
                [
                    base.broadcast_ecef(
                        base.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in shifted_epochs
                ]
            )
        return position_cache[key]

    left, right = (station.station_id for station in base.STATIONS)

    def curve(
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

    projection_gain = old.affine_projection_peak_to_peak_gain(
        pair.FEATURE_EPOCHS,
        pair.CALIBRATION_EPOCHS,
        base.GRID_STEP_S,
    )
    compiled = []
    for candidate in allowed:
        target = str(candidate["target"])
        reference = str(candidate["reference"])
        raw_start = _gps_index(epochs, str(candidate["raw_start_gps"]))
        raw_stop = _gps_index(epochs, str(candidate["raw_stop_gps"])) + 1
        feature = slice(raw_start + 1, raw_stop - 1)
        nominal = curve(target, reference)[feature]
        affine = phase.phase_prefix_metrics(nominal)

        alternatives = []
        for old_alternative in candidate["wrong_orbit_null"]["alternatives"]:
            satellite = str(old_alternative["satellite"])
            alternative = curve(satellite, reference)[feature]
            score = phase.phase_prefix_metrics(nominal - alternative)
            alternatives.append(
                {
                    "satellite": satellite,
                    "heldout_peak_to_peak_m": score["heldout_peak_to_peak_m"],
                    "heldout_rms_m": score["heldout_rms_m"],
                }
            )
        alternatives.sort(
            key=lambda row: (row["heldout_peak_to_peak_m"], row["satellite"])
        )
        if not alternatives:
            raise PhaseGeometryScreenError("frozen candidate lost wrong-orbit nulls")
        wrong = alternatives[0]
        controlling = min(
            affine["heldout_peak_to_peak_m"], wrong["heldout_peak_to_peak_m"]
        )
        controlling_null = (
            "PREFIX_AFFINE"
            if affine["heldout_peak_to_peak_m"] <= wrong["heldout_peak_to_peak_m"]
            else f"WRONG_ORBIT_{wrong['satellite']}"
        )

        elevation = {
            (station.station_id, satellite): base.elevation_deg(
                positions(satellite),
                station,
                station_ecef[station.station_id],
            )
            for station in base.STATIONS
            for satellite in (target, reference)
        }

        def fixed_reference_curve(
            target_satellite: str,
            left_offset_s: float,
            right_offset_s: float,
        ) -> np.ndarray:
            return curve(
                target_satellite,
                reference,
                left_offset_s,
                right_offset_s,
            )

        terms = [
            phase.timing_term(
                fixed_reference_curve,
                feature,
                target=target,
            ),
            phase.troposphere_term(
                elevation,
                feature,
                target=target,
                reference=reference,
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
        compiled.append(
            {
                "doy": authority.doy,
                "target": target,
                "reference": reference,
                "pre_roll_start_gps": candidate["pre_roll_start_gps"],
                "raw_start_gps": candidate["raw_start_gps"],
                "raw_stop_gps": candidate["raw_stop_gps"],
                "feature_start_gps": candidate["feature_start_gps"],
                "feature_stop_gps": candidate["feature_stop_gps"],
                "guarded_block_minimum_elevation_deg": candidate[
                    "guarded_block_minimum_elevation_deg"
                ],
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
                "legacy_frequency_controlling_separation_hz": candidate[
                    "controlling_heldout_separation_hz"
                ],
                "physical_terms": terms,
                **decision,
                "measurement_structure": "NOT_EVALUATED",
            }
        )
    return {
        **rate_day,
        "phase_candidate_windows_before_exclusion": len(raw_candidates),
        "phase_candidate_windows_after_exclusion": len(allowed),
        "exclusions": exclusions,
        "compiled_candidates": compiled,
    }


def screen_navigation_set(
    navigation_paths: Sequence[Path],
    phase_spike_receipt: Path,
) -> dict[str, object]:
    validate_phase_spike_receipt(phase_spike_receipt)
    validated = pair.validate_navigation_set(navigation_paths)
    days = []
    candidates = []
    for authority in pair.AUTHORITIES:
        day = _compile_day(validated[authority.doy], authority)
        candidates.extend(day.pop("compiled_candidates"))
        days.append(day)
    shortlist = _rank_candidates(candidates)
    selected = shortlist[0] if shortlist else None
    result = {
        "schema": "gnss-continuous-phase-geometry-screen-receipt-v1",
        "screen_version": SCREEN_VERSION,
        "manifest_sha256": manifest_sha256(),
        "phase_spike_receipt_sha256": PHASE_SPIKE_RECEIPT_SHA256,
        "scope": "BROADCAST_NAVIGATION_ONLY_OBSERVATION_PRODUCTS_UNDISCOVERED",
        "candidate_set": {
            "navigation": [asdict(authority) for authority in pair.AUTHORITIES],
            "stations": [asdict(station) for station in base.STATIONS],
            "signals": manifest()["signal_family"],
            "excluded_satellites": sorted(EXCLUDED_SATELLITES),
            "excluded_pairs": [sorted(value) for value in EXCLUDED_PAIRS],
        },
        "parameters": manifest()["partition"],
        "day_summaries": days,
        "compiled_candidate_count": len(candidates),
        "positive_margin_candidate_count": sum(
            float(candidate["remaining_physical_margin_m"]) > 0.0
            for candidate in candidates
        ),
        "shortlist": shortlist,
        "selected_geometry": selected,
        "selection_limit": 1,
        "outcome": OUTCOME_SELECTED if selected else OUTCOME_NONE,
        "remaining_blocker": (
            "PHASE_SIGNAL_FAMILY_STRUCTURAL_COVERAGE_AND_WITNESSES_NOT_"
            "EVALUATED_NO_OBSERVATION_PRODUCT_MAY_BE_SELECTED_YET"
            if selected
            else "NO_CANDIDATE_IN_THE_BOUNDED_SET_HAS_POSITIVE_PHYSICAL_MARGIN"
        ),
        "observation_access": {
            "products_discovered": 0,
            "products_selected": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values_accessed": 0,
        },
        "prospective_plan_frozen": False,
        "measurement_authorized": False,
        "new_gate_created": False,
    }
    strict_json(result)
    return result


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("phase_spike_receipt", type=Path)
    parser.add_argument("navigation", nargs=len(pair.AUTHORITIES), type=Path)
    arguments = parser.parse_args()
    print(
        strict_json(
            screen_navigation_set(
                arguments.navigation,
                arguments.phase_spike_receipt,
            )
        )
    )
