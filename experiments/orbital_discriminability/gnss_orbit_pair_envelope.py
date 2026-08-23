"""Candidate-specific physical envelope for the frozen G14/G17 geometry.

This bounded compiler accepts only the exact DOY-220 broadcast-navigation file
and the exact geometry-screen receipt.  It has no observation-product input
surface and cannot authorize measurement access.
"""

from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as old
from experiments.orbital_discriminability import gnss_double_difference_screen as base
from experiments.orbital_discriminability import gnss_orbit_pair_screen as pair


COMPILER_VERSION: Final = "gold-nlib-g14-g17-physical-envelope-v1"
SCREEN_RECEIPT_NAME: Final = "GNSS_ORBIT_PAIR_SCREEN_RECEIPT.json"
SCREEN_RECEIPT_BYTES: Final = 10_246
SCREEN_RECEIPT_SHA256: Final = (
    "bc6b172cd750a8071c5841dd187752c66c2b855e6abf2e77d8e54d2b4488a609"
)
SCREEN_SOURCE_COMMIT: Final = "4ea9fbcd78063d6c7a535b5c6e3917ceb5ef586f"
TARGET: Final = "G14"
REFERENCE: Final = "G17"
WRONG_TARGET: Final = "G22"
DOY: Final = 220
PRE_ROLL_START_GPS: Final = "2026-08-08T04:37:00 GPS"
RAW_START_GPS: Final = "2026-08-08T05:07:00 GPS"
RAW_STOP_GPS: Final = "2026-08-08T08:19:30 GPS"
FROZEN_CONTROLLING_SEPARATION_HZ: Final = 403.37545402996614
OUTCOME_ADMITTED: Final = "GNSS_ORBIT_PAIR_PHYSICAL_MARGIN_ADMITTED"
OUTCOME_BLOCKED: Final = "GNSS_ORBIT_PAIR_PHYSICAL_ENVELOPE_DOMINATES"


class OrbitPairEnvelopeError(ValueError):
    """An exact authority or frozen physical invariant changed."""


def manifest() -> dict[str, object]:
    return {
        "compiler_version": COMPILER_VERSION,
        "physical_question": (
            "CAN_THE_FROZEN_G14_G17_GEOMETRY_REMAIN_DISTINGUISHABLE_FROM_"
            "AFFINE_AND_G22_AFTER_THE_EXISTING_PHYSICAL_UNCERTAINTY_FAMILIES"
        ),
        "information_gain": (
            "WHETHER_A_NEGATIVE_FUTURE_MEASUREMENT_COULD_DAMAGE_THE_ORBITAL_"
            "HYPOTHESIS_RATHER_THAN_BE_ABSORBED_BY_PREDECLARED_NUISANCES"
        ),
        "screen_receipt": {
            "name": SCREEN_RECEIPT_NAME,
            "bytes": SCREEN_RECEIPT_BYTES,
            "sha256": SCREEN_RECEIPT_SHA256,
            "screen_source_commit": SCREEN_SOURCE_COMMIT,
        },
        "geometry": {
            "doy": DOY,
            "target": TARGET,
            "reference": REFERENCE,
            "wrong_target": WRONG_TARGET,
            "pre_roll_start_gps": PRE_ROLL_START_GPS,
            "raw_start_gps": RAW_START_GPS,
            "raw_stop_gps": RAW_STOP_GPS,
            "controlling_heldout_separation_hz": FROZEN_CONTROLLING_SEPARATION_HZ,
        },
        "coordinate": old.physical_coordinate(),
        "partition": {
            "raw_epochs": pair.RAW_EPOCHS,
            "feature_epochs": pair.FEATURE_EPOCHS,
            "calibration_epochs": pair.CALIBRATION_EPOCHS,
            "heldout_epochs": pair.HELDOUT_EPOCHS,
        },
        "physical_terms": [
            "STATION_EVENT_TIME_DIRECT_TRAJECTORY",
            "DIFFERENTIAL_TROPOSPHERE",
            "RINEX_CARRIER_PHASE_QUANTIZATION",
            *[definition["term"] for definition in old.GENERIC_PATH_BOUNDS_M],
        ],
        "combination": (
            "LINEAR_SUM_PER_MODEL_THEN_TWO_MODEL_PAIRWISE_COMPARISON_NO_"
            "PROBABILITY_OR_ROOT_SUM_SQUARE"
        ),
        "forbidden": [
            "observation product discovery selection header or payload access",
            "alternate satellite date window null or partition",
            "post-result bound reduction",
            "outcome-conditioned precise orbit products",
            "measurement authorization",
        ],
    }


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def validate_screen_receipt(path: Path) -> dict[str, object]:
    path = Path(path)
    if path.name != SCREEN_RECEIPT_NAME or not path.is_file():
        raise OrbitPairEnvelopeError("wrong geometry-screen receipt")
    if path.stat().st_size != SCREEN_RECEIPT_BYTES:
        raise OrbitPairEnvelopeError("geometry-screen receipt byte count changed")
    if base.file_sha256(path) != SCREEN_RECEIPT_SHA256:
        raise OrbitPairEnvelopeError("geometry-screen receipt SHA-256 changed")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    selected = receipt.get("selected_geometry")
    expected = {
        "doy": DOY,
        "target": TARGET,
        "reference": REFERENCE,
        "pre_roll_start_gps": PRE_ROLL_START_GPS,
        "raw_start_gps": RAW_START_GPS,
        "raw_stop_gps": RAW_STOP_GPS,
        "controlling_heldout_separation_hz": FROZEN_CONTROLLING_SEPARATION_HZ,
    }
    if not isinstance(selected, dict) or any(selected.get(key) != value for key, value in expected.items()):
        raise OrbitPairEnvelopeError("frozen geometry changed")
    if selected["wrong_orbit_null"]["controlling_alternative"] != WRONG_TARGET:
        raise OrbitPairEnvelopeError("frozen wrong-orbit null changed")
    if receipt.get("observation_access") != {
        "products_discovered": 0,
        "products_selected": 0,
        "headers_opened": 0,
        "payload_bytes": 0,
        "values_accessed": 0,
    }:
        raise OrbitPairEnvelopeError("observation access preceded envelope")
    return receipt


def validate_navigation(path: Path) -> pair.NavigationAuthority:
    authority = next(authority for authority in pair.AUTHORITIES if authority.doy == DOY)
    path = Path(path)
    if path.name != authority.name or not path.is_file():
        raise OrbitPairEnvelopeError("wrong DOY-220 navigation artifact")
    if path.stat().st_size != authority.bytes:
        raise OrbitPairEnvelopeError("DOY-220 navigation byte count changed")
    if base.file_sha256(path) != authority.sha256:
        raise OrbitPairEnvelopeError("DOY-220 navigation SHA-256 changed")
    return authority


def _gps_index(epochs: Sequence, label: str) -> int:
    matches = [index for index, epoch in enumerate(epochs) if base.format_gps(epoch) == label]
    if len(matches) != 1:
        raise OrbitPairEnvelopeError(f"frozen GPS epoch missing: {label}")
    return matches[0]


def combine_terms(
    controlling_separation_hz: float,
    terms: Sequence[dict[str, object]],
) -> dict[str, float | str | bool]:
    if controlling_separation_hz <= 0.0:
        raise OrbitPairEnvelopeError("non-positive frozen separation")
    contributions = [float(term["heldout_peak_to_peak_bound_hz"]) for term in terms]
    if not contributions or any(not np.isfinite(value) or value < 0.0 for value in contributions):
        raise OrbitPairEnvelopeError("invalid physical-envelope contribution")
    one_model = float(sum(contributions))
    pairwise = float(old.PAIRWISE_ENVELOPE_MULTIPLIER * one_model)
    remaining = float(controlling_separation_hz - pairwise)
    return {
        "one_model_physical_envelope_hz": one_model,
        "pairwise_comparison_envelope_hz": pairwise,
        "remaining_physical_margin_hz": remaining,
        "negative_result_interpretable_if_measurement_admitted": remaining > 0.0,
        "outcome": OUTCOME_ADMITTED if remaining > 0.0 else OUTCOME_BLOCKED,
    }


def compile_envelope(navigation: Path, screen_receipt: Path) -> dict[str, object]:
    validate_screen_receipt(screen_receipt)
    authority = validate_navigation(navigation)
    records = base.parse_gps_navigation(navigation)
    for satellite in (TARGET, REFERENCE, WRONG_TARGET):
        if satellite not in records:
            raise OrbitPairEnvelopeError(f"frozen satellite absent: {satellite}")
    epochs = pair.gps_day_grid(authority)
    raw_start = _gps_index(epochs, RAW_START_GPS)
    raw_stop = _gps_index(epochs, RAW_STOP_GPS) + 1
    if raw_stop - raw_start != pair.RAW_EPOCHS:
        raise OrbitPairEnvelopeError("raw grid changed")
    feature = slice(raw_start + 1, raw_stop - 1)
    if len(epochs[feature]) != pair.FEATURE_EPOCHS:
        raise OrbitPairEnvelopeError("feature grid changed")

    station_ecef = {
        station.station_id: base.station_to_ecef(station) for station in base.STATIONS
    }
    position_cache: dict[tuple[str, float], np.ndarray] = {}

    def positions(satellite: str, offset_s: float = 0.0) -> np.ndarray:
        key = satellite, offset_s
        if key not in position_cache:
            shifted = tuple(epoch + timedelta(seconds=offset_s) for epoch in epochs)
            position_cache[key] = np.asarray(
                [
                    base.broadcast_ecef(
                        base.select_ephemeris(records[satellite], epoch), epoch
                    )
                    for epoch in shifted
                ]
            )
        return position_cache[key]

    fractional = {}
    elevation = {}
    for satellite in (TARGET, REFERENCE, WRONG_TARGET):
        for station in base.STATIONS:
            station_id = station.station_id
            fractional[(station_id, satellite)] = base.fractional_doppler(
                positions(satellite), station_ecef[station_id], base.GRID_STEP_S
            )
            elevation[(station_id, satellite)] = base.elevation_deg(
                positions(satellite), station, station_ecef[station_id]
            )
    left, right = (station.station_id for station in base.STATIONS)

    def curve(target: str) -> np.ndarray:
        return base.double_difference_hz(
            fractional[(left, target)],
            fractional[(left, REFERENCE)],
            fractional[(right, target)],
            fractional[(right, REFERENCE)],
        )[feature]

    nominal = curve(TARGET)
    alternative = curve(WRONG_TARGET)
    affine = pair.prefix_affine(nominal)
    wrong = pair.prefix_affine(nominal - alternative)
    controlling = min(
        affine["heldout_peak_to_peak_hz"], wrong["heldout_peak_to_peak_hz"]
    )
    if abs(controlling - FROZEN_CONTROLLING_SEPARATION_HZ) > 1e-9:
        raise OrbitPairEnvelopeError("frozen controlling separation changed")

    projection_gain = old.affine_projection_peak_to_peak_gain(
        pair.FEATURE_EPOCHS, pair.CALIBRATION_EPOCHS, base.GRID_STEP_S
    )
    terms = [
        old.timing_term(
            TARGET,
            REFERENCE,
            feature,
            pair.CALIBRATION_EPOCHS,
            records,
            epochs,
            station_ecef,
        ),
        old.troposphere_term(
            TARGET,
            REFERENCE,
            feature,
            pair.CALIBRATION_EPOCHS,
            elevation,
            left,
            right,
        ),
        old.quantization_term(projection_gain),
    ]
    terms.extend(
        old.generic_path_term(definition, projection_gain)
        for definition in old.GENERIC_PATH_BOUNDS_M
    )
    decision = combine_terms(controlling, terms)
    for term in terms:
        term["pairwise_contribution_hz"] = float(
            old.PAIRWISE_ENVELOPE_MULTIPLIER
            * term["heldout_peak_to_peak_bound_hz"]
        )
    ranked_terms = sorted(
        terms, key=lambda term: (-term["pairwise_contribution_hz"], term["term"])
    )
    result = {
        "schema": "gnss-orbit-pair-physical-envelope-receipt-v1",
        "compiler_version": COMPILER_VERSION,
        "manifest_sha256": manifest_sha256(),
        "screen_receipt_sha256": SCREEN_RECEIPT_SHA256,
        "navigation": {
            "doy": authority.doy,
            "name": authority.name,
            "bytes": authority.bytes,
            "sha256": authority.sha256,
        },
        "geometry": manifest()["geometry"],
        "coordinate": old.physical_coordinate(),
        "partition": manifest()["partition"],
        "null_scores": {
            "prefix_affine": affine,
            "wrong_orbit_g22": wrong,
            "controlling_heldout_separation_hz": controlling,
            "controlling_null": "WRONG_ORBIT_G22",
        },
        "affine_projection_peak_to_peak_gain": projection_gain,
        "physical_terms": ranked_terms,
        "combination": manifest()["combination"],
        **decision,
        "interpretation": (
            "CONSERVATIVE_COMBINED_PHYSICAL_FAMILY_CAN_ABSORB_FROZEN_"
            "ORBITAL_VERSUS_G22_SEPARATION"
            if decision["outcome"] == OUTCOME_BLOCKED
            else "FROZEN_SEPARATION_EXCEEDS_PAIRWISE_PHYSICAL_ENVELOPE"
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
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("navigation", type=Path)
    parser.add_argument("screen_receipt", type=Path)
    print(strict_json(compile_envelope(**vars(parser.parse_args()))))
