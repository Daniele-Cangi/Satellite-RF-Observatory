"""Offline causal audit of the minimum DORIS orbital observable.

This module contains only published frequency constants, symbolic linear
coefficients, and already frozen structural facts.  It cannot open a DORIS
artifact and cannot evaluate an orbital prediction or observation value.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from fractions import Fraction
import json
from typing import Final, Mapping

from experiments.live_instrument.models import strict_json_value


AUDIT_VERSION: Final = "doris-observable-role-audit-v1"
S_BAND_HZ: Final = 2_036_250_000
UHF_BAND_HZ: Final = 401_250_000


@dataclass(frozen=True, slots=True)
class FrozenPairFact:
    pair: tuple[str, str]
    station_ids: tuple[str, str]
    frequency_shift_k: tuple[int, int]
    required_duration_s: float
    joint_core_overlap_s: float
    time_reference_valid_code_overlap_s: float


PAIR_FACTS: Final = (
    FrozenPairFact(
        ("TLSB", "WEUC"),
        ("D49", "D47"),
        (0, 18),
        430.0,
        393.0,
        0.0,
    ),
    FrozenPairFact(
        ("PAUB", "RIMC"),
        ("D46", "D40"),
        (0, 0),
        480.0,
        633.0,
        0.0,
    ),
)


def ionosphere_free_coefficients() -> tuple[Fraction, Fraction]:
    """Return exact coefficients for range-equivalent dual-frequency phase."""

    denominator = S_BAND_HZ**2 - UHF_BAND_HZ**2
    return (
        Fraction(S_BAND_HZ**2, denominator),
        Fraction(-(UHF_BAND_HZ**2), denominator),
    )


def _fraction_receipt(value: Fraction) -> dict[str, object]:
    with localcontext() as context:
        context.prec = 30
        decimal_value = Decimal(value.numerator) / Decimal(value.denominator)
        return {
            "numerator": value.numerator,
            "denominator": value.denominator,
            "decimal": format(decimal_value, ".18f"),
        }


def same_epoch_pair_coefficients() -> dict[str, int]:
    """Symbolic coefficients after left-minus-right phase differencing."""

    return {
        "LEFT_GEOMETRY_AND_NONDISPERSIVE_PATH": 1,
        "RIGHT_GEOMETRY_AND_NONDISPERSIVE_PATH": -1,
        "LEFT_TRANSMITTER_CLOCK_AND_PROPER_TIME": -1,
        "RIGHT_TRANSMITTER_CLOCK_AND_PROPER_TIME": 1,
        "LEFT_PASS_PHASE_BIAS": 1,
        "RIGHT_PASS_PHASE_BIAS": -1,
        "SHARED_RECEIVER_CLOCK_AT_COMMON_EPOCH": 0,
        "SHARED_RECEIVER_PROPER_TIME_AT_COMMON_EPOCH": 0,
        "FIRST_ORDER_IONOSPHERE_AFTER_DUAL_FREQUENCY_COMBINATION": 0,
    }


def asynchronous_pair_coefficients() -> dict[str, int]:
    """Symbolic receiver terms when station samples are not co-epoch."""

    return {
        "SHARED_RECEIVER_CLOCK_AT_LEFT_EPOCH": 1,
        "SHARED_RECEIVER_CLOCK_AT_RIGHT_EPOCH": -1,
        "SHARED_RECEIVER_PROPER_TIME_AT_LEFT_EPOCH": 1,
        "SHARED_RECEIVER_PROPER_TIME_AT_RIGHT_EPOCH": -1,
    }


def build_audit() -> dict[str, object]:
    alpha, beta = ionosphere_free_coefficients()
    receipt: dict[str, object] = {
        "outcome": "DORIS_DUAL_PHASE_DIFFERENTIAL_REQUIRES_COEPOCH_REQUALIFICATION",
        "audit_version": AUDIT_VERSION,
        "scope": {
            "observation_artifact_access": "ZERO",
            "candidate_day_access": "ZERO",
            "observation_values": "NEVER_ACCESSED",
            "orbital_prediction": "NOT_EVALUATED",
            "null_score": "NOT_EVALUATED",
            "changes_to_g0_or_g1": "ZERO",
        },
        "published_frequency_constants_hz": {
            "phase_l1_s_band": S_BAND_HZ,
            "phase_l2_uhf": UHF_BAND_HZ,
        },
        "ionosphere_free_phase": {
            "coordinate": "Q_IF=alpha*(lambda1*L1)+beta*(lambda2*L2)",
            "alpha": _fraction_receipt(alpha),
            "beta": _fraction_receipt(beta),
            "invariants": {
                "nondispersive_gain": "alpha+beta=1_EXACT",
                "first_order_ionosphere": (
                    "alpha/f1^2+beta/f2^2=0_EXACT"
                ),
                "l1_l2_reception_epoch": "SYNCHRONOUS_BY_RECEIVER_DESIGN",
            },
        },
        "causal_topologies": {
            "single_station_or_asynchronous_pair": {
                "receiver_clock": "DOES_NOT_CANCEL",
                "minimum_time_bridge": (
                    "IONOSPHERE_FREE_C1_C2_OR_INDEPENDENT_BOUNDED_RECEIVER_CLOCK_MODEL"
                ),
                "target_station_code_flag_role": (
                    "TIME_REFERENCE_VALIDITY_NOT_GENERIC_FIELD_PRESENCE"
                ),
                "claim": "NOT_ADMITTED_BY_CURRENT_STRUCTURAL_RECEIPT",
            },
            "exact_coepoch_inter_beacon_phase_difference": {
                "receiver_side_coefficients": same_epoch_pair_coefficients(),
                "per_target_c1_c2_time_reference_witness": (
                    "NOT_CAUSALLY_REQUIRED_FOR_COMMON_RECEIVER_CLOCK_CANCELLATION"
                ),
                "remaining_required_event_time": (
                    "ABSOLUTE_DOR_TO_COORDINATE_TIME_BOUND_FOR_ORBIT_EVALUATION"
                ),
                "claim": "CONDITIONALLY_PLAUSIBLE_NOT_STRUCTURALLY_QUALIFIED",
            },
            "overlapping_but_noncoepoch_station_streams": {
                "receiver_side_coefficients": asynchronous_pair_coefficients(),
                "current_633_second_overlap": (
                    "INSUFFICIENT_TO_PROVE_RECEIVER_CLOCK_CANCELLATION"
                ),
                "claim": "NOT_ADMITTED",
            },
        },
        "physical_roles": {
            "L1_L2": (
                "CORE_RANGE_EQUIVALENT_PHASE_AND_FIRST_ORDER_IONOSPHERE_CONTROL"
            ),
            "L1_L2_FLAG1": "DESCRIPTIVE_CENTRAL_FREQUENCY_STATE",
            "L1_L2_FLAG2": "FATAL_PHASE_CONTINUITY_LLI",
            "C1_C2": (
                "RECEIVER_TIME_CLOCK_SOLUTION_AND_OPTIONAL_SAME_PATH_DIAGNOSTIC"
            ),
            "C1_C2_FLAG1": "VALIDITY_FOR_TIME_REFERENCE_USE",
            "C1_C2_FLAG2": "PROCESSING_UNIT_IDENTITY_NOT_VALIDITY",
            "EPOCH_CLOCK_OFFSET": (
                "ALTERNATIVE_RECEIVER_TIME_BRIDGE_REQUIRING_NUMERICAL_PROVENANCE"
            ),
        },
        "same_epoch_pair_terms": {
            "cancelled_exactly_in_symbolic_model": [
                "FIRST_ORDER_IONOSPHERE",
                "SHARED_RECEIVER_CLOCK",
                "SHARED_RECEIVER_PROPER_TIME",
            ],
            "conditional_common_mode_reduction": [
                "COMMON_RECEPTION_EPOCH_ERROR_TO_FIRST_ORDER_IF_SAME_TAG",
            ],
            "prefix_affine_nuisance_candidates": [
                "LEFT_MINUS_RIGHT_GROUND_OSCILLATOR_OFFSET",
                "LEFT_MINUS_RIGHT_GROUND_OSCILLATOR_AFFINE_AGING",
                "CONSTANT_INTERFREQUENCY_AND_PASS_PHASE_BIASES",
            ],
            "must_remain_explicit_or_bounded": [
                "ABSOLUTE_EVENT_TIME_ERROR_AGAINST_ORBIT",
                "HIGHER_ORDER_IONOSPHERE",
                "DIFFERENTIAL_TROPOSPHERE",
                "STATION_PHASE_CENTERS_AND_ANTENNA_MAPS",
                "PHASE_WINDUP",
                "SHAPIRO_AND_ONE_WAY_RELATIVITY",
                "NONAFFINE_GROUND_OSCILLATOR_BEHAVIOR",
                "CHANNEL_SWITCH_OR_RECEIVER_NONCOMMON_BIAS",
            ],
        },
        "frozen_structural_facts": [asdict(fact) for fact in PAIR_FACTS],
        "preferred_conditional_pair": {
            "pair": ["PAUB", "RIMC"],
            "why": [
                "CORE_OVERLAP_633_S_EXCEEDS_480_S_REQUIREMENT",
                "BOTH_BEACON_FREQUENCY_SHIFT_FACTORS_K_ARE_ZERO",
                "NO_SHIFTED_FREQUENCY_PHASE_CORRECTION_REQUIRED",
            ],
            "unproved_clause": (
                "CONTIGUOUS_EXACT_COEPOCH_L1_L2_COVERAGE_FOR_FROZEN_WINDOW"
            ),
        },
        "decision": {
            "old_per_target_code_witness": (
                "NOT_UNIVERSAL_REPLACE_WITH_CLAIM_SCOPED_TIME_BRIDGE"
            ),
            "dual_phase_core": (
                "SUFFICIENT_ONLY_FOR_EXACT_COEPOCH_INTER_BEACON_DIFFERENTIAL_"
                "AFTER_REMAINING_TERMS_ARE_BOUNDED"
            ),
            "current_measurement_admission": "NOT_EVALUATED",
            "next_minimum_action": (
                "VALUE_BLIND_EXACT_COEPOCH_TOPOLOGY_REQUALIFICATION_OF_DEVELOPMENT_"
                "ARTIFACT_REQUIRES_SEPARATE_AUTHORITY"
            ),
        },
    }
    strict_json(receipt)
    return receipt


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
