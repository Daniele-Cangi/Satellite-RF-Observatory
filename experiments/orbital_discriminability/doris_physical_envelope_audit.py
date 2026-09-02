"""Offline physical-envelope audit for the qualified PAUB--RIMC topology.

This module consumes only four frozen scalar/structural receipts.  It has no
observation-product, orbit-product, network, or detector input.  In particular,
it never turns a documented central value or performance scale into an
uncertainty bound.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping, Sequence

from experiments.live_instrument.models import strict_json_value


AUDIT_VERSION: Final = "doris-paub-rimc-physical-envelope-audit-v1"
OUTCOME_BOUND_UNAVAILABLE: Final = "DORIS_PHYSICAL_ENVELOPE_BOUND_UNAVAILABLE"

ROOT: Final = Path(__file__).resolve().parent
FROZEN_RECEIPTS: Final = {
    "geometry": (
        ROOT / "DORIS_FORWARD_GEOMETRY_RECEIPT.json",
        "b342b64a2166f89d2adc05e1ee68e04e1abcccf234e8060449853b890a5e1117",
    ),
    "header": (
        ROOT / "DORIS_DEVELOPMENT_HEADER_RECEIPT.json",
        "b7e48ee0efb2e23be0981ead04df8894c57e23136bfe5facaeaa9fa70bdb0c5a",
    ),
    "observable_role": (
        ROOT / "DORIS_OBSERVABLE_ROLE_AUDIT_RECEIPT.json",
        "e509870fd01b4fac75b450fdb48beaecef9b544dbff789f09fb5a2424607388d",
    ),
    "topology": (
        ROOT / "DORIS_EXACT_COEPOCH_REQUALIFICATION_RECEIPT.json",
        "d1668fccc982d550a949faf68131436b2713d12f28374617eaee82585bf67c9d",
    ),
}

S_BAND_HZ: Final = 2_036_250_000.0
C_MPS: Final = 299_792_458.0
PAIR: Final = ("PAUB", "RIMC")
STATION_IDS: Final = ("D46", "D40")
DEVELOPMENT_START_DOR: Final = "2026-08-30T19:12:45.229949+00:00"
DEVELOPMENT_END_DOR: Final = "2026-08-30T19:23:18.229949+00:00"
DEVELOPMENT_DURATION_S: Final = 633.0
DEVELOPMENT_EPOCHS: Final = 128
CANDIDATE_DAY_UTC: Final = "2026-09-02"
CONTROLLING_GEOMETRY_SEPARATION_HZ: Final = 18_147.76648921784
FORECAST_NONAFFINE_ENVELOPE_HZ: Final = 2.966989671657788
PRELIMINARY_GEOMETRY_MARGIN_HZ: Final = 18_144.79949954618


SOURCES: Final = {
    "models_and_solutions": {
        "url": "https://ids-doris.org/documents/BC/data/DORIS_models%26solutions_v1.0.pdf",
        "role": "PHASE_CAUSAL_EQUATION_AND_USO_NUISANCE_STRUCTURE",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    "rinex_doris_3": {
        "url": "https://ids-doris.org/documents/BC/data/RINEX_DORIS.pdf",
        "role": "TIME_PHASE_FLAG_AND_HEADER_SEMANTICS",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    "doris_for_beginners": {
        "url": "https://ids-doris.org/documents/BC/WhatIsDORIS.pdf",
        "role": "DESCRIPTIVE_RECEIVER_SYNCHRONISATION_SCALE",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    "uso_system_description": {
        "url": "https://ids-doris.org/documents/1991-DORISnewsletter-2.pdf",
        "role": "DESCRIPTIVE_USO_PERFORMANCE_SCALE",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
    "sentinel3_phase_center_review": {
        "url": "https://ids-doris.org/resources/presentations/ids-meetings/i03-2026-4618.html",
        "role": "SENTINEL_3_PHASE_CENTER_MODEL_DEPENDENCE",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
    },
}


class DorisEnvelopeError(ValueError):
    """A frozen receipt or envelope invariant is inconsistent."""


@dataclass(frozen=True, slots=True)
class OpenTerm:
    name: str
    epistemic_class: str
    state: str
    provenance: str
    central_or_scale: str
    finite_outcome_independent_bound_hz: float | None
    affine_projection: str
    missing_for_bound: tuple[str, ...]
    causal_role: str


def _load_strict_receipt(path: Path, expected_sha256: str) -> dict[str, object]:
    raw = path.read_bytes()
    canonical = raw.replace(b"\r\n", b"\n")
    if sha256(canonical).hexdigest() != expected_sha256:
        raise DorisEnvelopeError(f"frozen receipt hash changed: {path.name}")
    try:
        value = json.loads(
            raw,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
        )
    except (json.JSONDecodeError, ValueError) as error:
        raise DorisEnvelopeError(f"invalid strict JSON: {path.name}") from error
    if not isinstance(value, dict):
        raise DorisEnvelopeError(f"receipt root is not an object: {path.name}")
    return value


def load_frozen_receipts() -> dict[str, dict[str, object]]:
    receipts = {
        name: _load_strict_receipt(path, digest)
        for name, (path, digest) in FROZEN_RECEIPTS.items()
    }
    _validate_receipt_invariants(receipts)
    return receipts


def _validate_receipt_invariants(
    receipts: Mapping[str, Mapping[str, object]],
) -> None:
    geometry = receipts["geometry"]
    topology = receipts["topology"]
    role = receipts["observable_role"]
    header = receipts["header"]

    shortlist = geometry.get("shortlist")
    if not isinstance(shortlist, list):
        raise DorisEnvelopeError("geometry shortlist is absent")
    selected = next(
        (
            row
            for row in shortlist
            if isinstance(row, dict) and tuple(row.get("pair", ())) == PAIR
        ),
        None,
    )
    pair = topology.get("pair")
    coefficients = (
        role.get("causal_topologies", {})
        .get("exact_coepoch_inter_beacon_phase_difference", {})
        .get("receiver_side_coefficients", {})
    )
    shortlist_metadata = header.get("shortlist_station_metadata", {})
    checks = (
        geometry.get("outcome")
        == "DORIS_FORWARD_GEOMETRY_SHORTLISTED_MEASUREMENT_UNADMITTED",
        selected is not None,
        selected is not None
        and selected.get("controlling_geometry_separation_hz")
        == CONTROLLING_GEOMETRY_SEPARATION_HZ,
        selected is not None
        and selected.get("forecast_non_affine_envelope_peak_to_peak_hz")
        == FORECAST_NONAFFINE_ENVELOPE_HZ,
        selected is not None
        and selected.get("preliminary_geometry_margin_hz")
        == PRELIMINARY_GEOMETRY_MARGIN_HZ,
        topology.get("outcome") == "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED",
        isinstance(pair, dict) and tuple(pair.get("codes", ())) == PAIR,
        isinstance(pair, dict) and tuple(pair.get("station_ids", ())) == STATION_IDS,
        isinstance(pair, dict)
        and pair.get("maximum_exact_coepoch_segment_s") == DEVELOPMENT_DURATION_S,
        isinstance(pair, dict) and pair.get("topology_qualified") is True,
        coefficients.get("FIRST_ORDER_IONOSPHERE_AFTER_DUAL_FREQUENCY_COMBINATION")
        == 0,
        coefficients.get("SHARED_RECEIVER_CLOCK_AT_COMMON_EPOCH") == 0,
        coefficients.get("SHARED_RECEIVER_PROPER_TIME_AT_COMMON_EPOCH") == 0,
        shortlist_metadata.get("PAUB", {}).get("frequency_shift_k") == 0,
        shortlist_metadata.get("RIMC", {}).get("frequency_shift_k") == 0,
        header.get("observation_access", {}).get("phase_values") == 0,
    )
    if not all(checks):
        raise DorisEnvelopeError("frozen receipts no longer express the audited topology")


def range_rate_scale_hz(range_rate_mps: float) -> float:
    """Convert a descriptive S-band range-rate scale to a frequency scale."""

    if range_rate_mps < 0.0:
        raise DorisEnvelopeError("range-rate scale must be nonnegative")
    return S_BAND_HZ * range_rate_mps / C_MPS


def open_terms() -> tuple[OpenTerm, ...]:
    """Return the exact surviving term family without manufacturing bounds."""

    common = "INDEPENDENT_OF_TARGET_RF"
    return (
        OpenTerm(
            "ABSOLUTE_DOR_TO_COORDINATE_TIME_ERROR_BOUND",
            "UNRESOLVED",
            "UNRESOLVED",
            common,
            "RECEIVER_SYNCHRONISATION_DESCRIBED_AS_AROUND_10_MICROSECONDS_NOT_A_FINITE_BOUND",
            None,
            "NOT_PROJECTABLE_AS_A_FREE_TIME_PHASE",
            (
                "NUMERICAL_ADC_PHASE_EVENT_TO_COORDINATE_TIME_BOUND",
                "DIRECT_T_MINUS_DELTA_T_AND_T_PLUS_DELTA_T_TRAJECTORY_ENVELOPE",
            ),
            "Binds each common DOR receiver epoch to the orbit evaluation epoch.",
        ),
        OpenTerm(
            "HIGHER_ORDER_IONOSPHERE",
            "UNRESOLVED",
            "UNRESOLVED_AFTER_EXACT_FIRST_ORDER_CANCELLATION",
            common,
            "FIRST_ORDER_1_OVER_F_SQUARED_COEFFICIENT_IS_EXACTLY_ZERO",
            None,
            "PREFIX_AFFINE_MAY_REMOVE_ONLY_CONSTANT_AND_RATE_NOT_HIGHER_ORDER_MEDIA",
            (
                "OUTCOME_INDEPENDENT_HIGHER_ORDER_IONOSPHERE_FAMILY",
                "PATH_SPECIFIC_MAGNETIC_FIELD_AND_ELECTRON_CONTENT_LIMITS",
            ),
            "Residual dispersive phase after the exact rational L1/L2 combination.",
        ),
        OpenTerm(
            "DIFFERENTIAL_TROPOSPHERE",
            "UNRESOLVED",
            "MODELED_FORM_UNRESOLVED_UNCERTAINTY",
            common,
            "STANDARD_DORIS_SOLUTIONS_ESTIMATE_ZENITH_TROPOSPHERE_BUT_NO_PAIR_WINDOW_BOUND_IS_FROZEN",
            None,
            "PREFIX_AFFINE_DOES_NOT_REMOVE_ELEVATION_DEPENDENT_CURVATURE",
            (
                "EXACT_BEACON_COORDINATES_AND_HEIGHTS",
                "SLANT_DELAY_MODEL_AND_RESIDUAL_INTERVAL_FOR_BOTH_PATHS",
            ),
            "Nondispersive beacon-specific propagation curvature.",
        ),
        OpenTerm(
            "STATION_PHASE_CENTERS_AND_ANTENNA_MAPS",
            "UNRESOLVED",
            "PARTIAL_METADATA_UNRESOLVED_UNCERTAINTY",
            common,
            "SATELLITE_PCO_VECTOR_IS_DECLARED_BUT_EXACT_GROUND_PCO_PCV_AND_ATTITUDE_MAPPING_ARE_NOT_FROZEN",
            None,
            "CONSTANT_PART_ONLY_MAY_PROJECT_OUT",
            (
                "EXACT_DPOD_COORDINATES_AND_HEIGHTS",
                "GROUND_AND_SPACE_ANTENNA_PCO_PCV_WITH_ATTITUDE_LINEAGE",
            ),
            "Maps geometric line of sight to the electrical phase path.",
        ),
        OpenTerm(
            "PHASE_WINDUP",
            "UNRESOLVED",
            "MODELED_FORM_UNRESOLVED_INPUTS",
            common,
            "PHASE_MODEL_REQUIRES_WINDUP_BUT_NO_SENTINEL_3A_ATTITUDE_POLARIZATION_GRID_IS_FROZEN",
            None,
            "NOT_GUARANTEED_AFFINE",
            (
                "SPACECRAFT_ATTITUDE_AND_ANTENNA_ORIENTATION",
                "BEACON_ANTENNA_ORIENTATION_AND_WINDUP_CONVENTION",
            ),
            "Orientation-dependent carrier-phase rotation.",
        ),
        OpenTerm(
            "SHAPIRO_AND_ONE_WAY_RELATIVITY",
            "UNRESOLVED",
            "MODELED_FORM_UNRESOLVED_UNCERTAINTY",
            common,
            "GROUND_PROPER_TIME_BIAS_AND_RATE_CAN_SHARE_THE_AFFINE_NUISANCE_BUT_PATH_REMAINDERS_REQUIRE_EXACT_GEOMETRY",
            None,
            "ONLY_PREDECLARED_CONSTANT_AND_RATE_ARE_PROJECTED",
            (
                "EXACT_ONE_WAY_LIGHT_TIME_AND_EARTH_ROTATION_MODEL",
                "SHAPIRO_AND_NONAFFINE_PROPER_TIME_REMAINDER_INTERVAL",
            ),
            "Coordinate/proper-time and relativistic propagation bridge.",
        ),
        OpenTerm(
            "NONAFFINE_GROUND_OSCILLATOR_BEHAVIOR",
            "UNRESOLVED",
            "MODELED_STOCHASTIC_FAMILY_UNRESOLVED_BOUND",
            common,
            "PUBLISHED_USO_PERFORMANCE_AND_0_3_MM_PER_S_SYSTEM_SCALE_ARE_DESCRIPTIVE_NOT_PRODUCT_SPECIFIC_HARD_BOUNDS",
            None,
            "OFFSET_AND_AFFINE_AGING_ONLY_PROJECTED_FROM_CALIBRATION_PREFIX",
            (
                "PAUB_AND_RIMC_SESSION_SPECIFIC_NONAFFINE_USO_INTERVAL",
                "FROZEN_PREFIX_TO_SUFFIX_STABILITY_RULE",
            ),
            "Differential transmitter phase/frequency curvature that can mimic orbit.",
        ),
        OpenTerm(
            "CHANNEL_SWITCH_OR_RECEIVER_NONCOMMON_BIAS",
            "UNRESOLVED",
            "UNRESOLVED",
            "UNKNOWN",
            "EXACT_COEPOCH_AND_LLI_CONTINUITY_PROVE_TOPOLOGY_NOT_ANALOG_OR_PROCESSING_UNIT_BIAS",
            None,
            "CONSTANT_BIAS_MAY_PROJECT_OUT_BUT_SWITCH_OR_CURVATURE_DOES_NOT",
            (
                "PROCESSING_UNIT_ASSIGNMENT_AND_SWITCH_CONTINUITY",
                "PRODUCT_SPECIFIC_NONCOMMON_PHASE_BIAS_INTERVAL",
            ),
            "Channel-specific receiver transform after the shared antenna/clock boundary.",
        ),
    )


def conservative_envelope(
    terms: Sequence[OpenTerm],
) -> dict[str, object]:
    """Minkowski-sum finite bounds, or refuse if any required term is open."""

    missing = [
        term.name
        for term in terms
        if term.finite_outcome_independent_bound_hz is None
    ]
    if missing:
        return {
            "state": "UNAVAILABLE",
            "heldout_peak_to_peak_hz": None,
            "missing_terms": missing,
            "combination_rule": "CONSERVATIVE_MINKOWSKI_SUM_ONLY_AFTER_EVERY_TERM_IS_BOUNDED",
        }
    total = sum(
        term.finite_outcome_independent_bound_hz or 0.0 for term in terms
    )
    return {
        "state": "BOUNDED",
        "heldout_peak_to_peak_hz": total,
        "missing_terms": [],
        "combination_rule": "CONSERVATIVE_MINKOWSKI_SUM",
    }


def audit_manifest_payload() -> dict[str, object]:
    return {
        "audit_version": AUDIT_VERSION,
        "frozen_receipt_sha256": {
            name: digest for name, (_, digest) in FROZEN_RECEIPTS.items()
        },
        "pair": list(PAIR),
        "station_ids": list(STATION_IDS),
        "development_segment": {
            "start_dor": DEVELOPMENT_START_DOR,
            "end_dor": DEVELOPMENT_END_DOR,
            "duration_s": DEVELOPMENT_DURATION_S,
            "epochs": DEVELOPMENT_EPOCHS,
        },
        "candidate_day_utc": CANDIDATE_DAY_UTC,
        "preliminary_geometry_margin_hz": PRELIMINARY_GEOMETRY_MARGIN_HZ,
        "source_urls": {name: item["url"] for name, item in SOURCES.items()},
        "open_term_names": [term.name for term in open_terms()],
    }


def audit_manifest_sha256() -> str:
    return sha256(strict_json(audit_manifest_payload()).encode("utf-8")).hexdigest()


def build_audit() -> dict[str, object]:
    load_frozen_receipts()
    terms = open_terms()
    envelope = conservative_envelope(terms)
    if envelope["state"] != "UNAVAILABLE":
        raise DorisEnvelopeError("audit unexpectedly produced a complete envelope")

    system_accuracy_scale_hz = range_rate_scale_hz(0.0003)
    result: dict[str, object] = {
        "outcome": OUTCOME_BOUND_UNAVAILABLE,
        "audit_version": AUDIT_VERSION,
        "audit_manifest_sha256": audit_manifest_sha256(),
        "scope": {
            "observation_products_accessed": 0,
            "observation_values_accessed": 0,
            "orbit_products_accessed": 0,
            "candidate_day_access": "ZERO",
            "network_access_required_by_audit": False,
            "g0_g1_changes": "ZERO",
            "detector_implemented": False,
            "orbital_score": "NOT_EVALUATED",
        },
        "frozen_receipts": {
            name: {"filename": path.name, "sha256": digest}
            for name, (path, digest) in FROZEN_RECEIPTS.items()
        },
        "coordinate": {
            "name": "EXACT_COEPOCH_PAUB_MINUS_RIMC_IONOSPHERE_FREE_PHASE",
            "first_order_ionosphere": "CANCELLED_EXACTLY",
            "shared_receiver_clock": "CANCELLED_EXACTLY_AT_COMMON_EPOCH",
            "shared_receiver_proper_time": "CANCELLED_EXACTLY_AT_COMMON_EPOCH",
            "frequency_shift_k": [0, 0],
            "prefix_nuisance": "CONSTANT_AND_AFFINE_ONLY_NO_SUFFIX_REFIT",
        },
        "cross_date_boundary": {
            "development_topology": {
                "date_utc": "2026-08-30",
                "start_dor": DEVELOPMENT_START_DOR,
                "end_dor": DEVELOPMENT_END_DOR,
                "duration_s": DEVELOPMENT_DURATION_S,
                "epochs": DEVELOPMENT_EPOCHS,
                "claim": "CAPABILITY_TOPOLOGY_ONLY",
            },
            "prospective_geometry": {
                "date_utc": CANDIDATE_DAY_UTC,
                "controlling_separation_hz": CONTROLLING_GEOMETRY_SEPARATION_HZ,
                "forecast_nonaffine_envelope_hz": FORECAST_NONAFFINE_ENVELOPE_HZ,
                "preliminary_margin_hz": PRELIMINARY_GEOMETRY_MARGIN_HZ,
                "claim": "ORBIT_ONLY_SCREENING_CEILING_NOT_MEASUREMENT_MARGIN",
            },
            "same_grid": False,
            "transfer_rule": "STRUCTURAL_CAPABILITY_MAY_TRANSFER_ONLY_AFTER_CANDIDATE_WINDOW_REQUALIFICATION",
        },
        "descriptive_scales_not_bounds": {
            "published_system_accuracy_0_3_mm_per_s_single_link_hz": system_accuracy_scale_hz,
            "symmetric_two_link_scale_hz": 2.0 * system_accuracy_scale_hz,
            "receiver_synchronisation_wording": "AROUND_10_MICROSECONDS",
            "phase_noise_wording": "A_FEW_MILLIMETRES",
            "policy": "NONE_OF_THESE_VALUES_REDUCES_THE_UNCERTAINTY_ENVELOPE",
        },
        "terms": [asdict(term) for term in terms],
        "combined_envelope": envelope,
        "decision": {
            "remaining_physical_margin_hz": None,
            "maximum_admissible_detector_resolution_hz": None,
            "negative_result_interpretable": False,
            "why": "AT_LEAST_ONE_REQUIRED_CAUSAL_TERM_LACKS_A_FINITE_OUTCOME_INDEPENDENT_BOUND",
            "next_measurement_access_authorized": False,
        },
        "sources": SOURCES,
    }
    strict_json(result)
    return result


def strict_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> int:
    print(strict_json(build_audit()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
