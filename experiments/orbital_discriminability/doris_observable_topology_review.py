"""Offline algebraic review of candidate compound DORIS observables.

The review uses only symbolic coefficients and frozen descriptive receipts.
It has no network, orbit-product, RINEX-artifact, or observation-value surface.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from typing import Final, Iterable, Mapping

from experiments.live_instrument.models import strict_json_value


REVIEW_VERSION: Final = "doris-observable-topology-review-v1"
OUTCOME: Final = "DORIS_TIME_REFERENCE_PAIR_SELECTED_GEOMETRY_UNEVALUATED"
FROZEN_PARENT_COMMIT: Final = "d41635bd3b22f26f45dd6a4e4ab0ff70200e4fc0"

ROOT: Final = Path(__file__).resolve().parent
HEADER_RECEIPT: Final = ROOT / "DORIS_DEVELOPMENT_HEADER_RECEIPT.json"
ROLE_RECEIPT: Final = ROOT / "DORIS_OBSERVABLE_ROLE_AUDIT_RECEIPT.json"
ENVELOPE_RECEIPT: Final = ROOT / "DORIS_PHYSICAL_ENVELOPE_AUDIT_RECEIPT.json"

FROZEN_RECEIPT_HASHES: Final = {
    "development_header": (
        "b7e48ee0efb2e23be0981ead04df8894c57e23136bfe5facaeaa9fa70bdb0c5a"
    ),
    "observable_role": (
        "e509870fd01b4fac75b450fdb48beaecef9b544dbff789f09fb5a2424607388d"
    ),
    "physical_envelope": (
        "7f41c3f10b3206f1f7aa420da5d2c63101192c05ecfca34e026f6c25e08eef66"
    ),
}


class DorisTopologyError(ValueError):
    """Raised when a frozen receipt or symbolic topology is inconsistent."""


@dataclass(frozen=True, slots=True)
class Link:
    """One ionosphere-free DORIS phase coordinate on a named event grid."""

    satellite: str
    beacon: str
    receive_event: str
    transmit_event: str
    channel: str


Term = tuple[str, str, str]


def _hash(path: Path) -> str:
    canonical = path.read_bytes().replace(b"\r\n", b"\n")
    return sha256(canonical).hexdigest()


def load_frozen_inputs() -> dict[str, object]:
    paths = {
        "development_header": HEADER_RECEIPT,
        "observable_role": ROLE_RECEIPT,
        "physical_envelope": ENVELOPE_RECEIPT,
    }
    for name, path in paths.items():
        actual = _hash(path)
        if actual != FROZEN_RECEIPT_HASHES[name]:
            raise DorisTopologyError(f"FROZEN_RECEIPT_HASH_MISMATCH:{name}")

    payloads = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    if payloads["physical_envelope"]["outcome"] != (
        "DORIS_PHYSICAL_ENVELOPE_BOUND_UNAVAILABLE"
    ):
        raise DorisTopologyError("UNEXPECTED_PARENT_OUTCOME")
    return payloads


def link_terms(link: Link) -> dict[Term, int]:
    """Return the exact unit coefficients of one range-equivalent link.

    First-order ionosphere is absent because the input coordinate is the
    already frozen exact rational L1/L2 ionosphere-free phase combination.
    Event identifiers are deliberately part of clock keys: equal hardware is
    not equal clock state when the physical epochs differ.
    """

    return {
        ("GEOMETRY_AND_NONDISPERSIVE_PATH", link.satellite, link.beacon): 1,
        ("RECEIVER_CLOCK", link.satellite, link.receive_event): 1,
        ("RECEIVER_PROPER_TIME", link.satellite, link.receive_event): 1,
        ("TRANSMITTER_CLOCK", link.beacon, link.transmit_event): -1,
        ("TRANSMITTER_PROPER_TIME", link.beacon, link.transmit_event): -1,
        ("CHANNEL_NONCOMMON_BIAS", link.satellite, link.channel): 1,
        ("HIGHER_ORDER_IONOSPHERE", link.satellite, link.beacon): 1,
        ("TROPOSPHERE", link.satellite, link.beacon): 1,
        ("ANTENNA_AND_WINDUP", link.satellite, link.beacon): 1,
        ("ONE_WAY_RELATIVITY", link.satellite, link.beacon): 1,
    }


def combine(weighted_links: Iterable[tuple[int, Link]]) -> dict[Term, int]:
    coefficients: defaultdict[Term, int] = defaultdict(int)
    for weight, link in weighted_links:
        if weight not in (-1, 1):
            raise DorisTopologyError("ONLY_UNIT_DIFFERENCE_WEIGHTS_ARE_SUPPORTED")
        for term, coefficient in link_terms(link).items():
            coefficients[term] += weight * coefficient
    return {
        term: coefficient
        for term, coefficient in sorted(coefficients.items())
        if coefficient != 0
    }


def family_coefficients(coefficients: Mapping[Term, int], family: str) -> dict[str, int]:
    return {
        "/".join(term[1:]): coefficient
        for term, coefficient in coefficients.items()
        if term[0] == family
    }


def one_satellite_pair() -> dict[Term, int]:
    return combine(
        (
            (1, Link("S0", "B1", "R0", "E01", "C1")),
            (-1, Link("S0", "B2", "R0", "E02", "C2")),
        )
    )


def four_link_same_receive_epochs() -> dict[Term, int]:
    """Two satellites and two beacons, coepoch only at each receiver."""

    return combine(
        (
            (1, Link("S1", "B1", "R1", "E11", "C11")),
            (-1, Link("S1", "B2", "R1", "E12", "C12")),
            (-1, Link("S2", "B1", "R2", "E21", "C21")),
            (1, Link("S2", "B2", "R2", "E22", "C22")),
        )
    )


def four_link_same_transmit_epochs() -> dict[Term, int]:
    """The same four links aligned by beacon emission rather than reception."""

    return combine(
        (
            (1, Link("S1", "B1", "R11", "E1", "C11")),
            (-1, Link("S1", "B2", "R12", "E2", "C12")),
            (-1, Link("S2", "B1", "R21", "E1", "C21")),
            (1, Link("S2", "B2", "R22", "E2", "C22")),
        )
    )


def _coefficient_summary(coefficients: Mapping[Term, int]) -> dict[str, object]:
    families = (
        "RECEIVER_CLOCK",
        "RECEIVER_PROPER_TIME",
        "TRANSMITTER_CLOCK",
        "TRANSMITTER_PROPER_TIME",
        "CHANNEL_NONCOMMON_BIAS",
        "GEOMETRY_AND_NONDISPERSIVE_PATH",
    )
    return {
        family: family_coefficients(coefficients, family)
        for family in families
    }


def _time_reference_scope(header: Mapping[str, object]) -> dict[str, object]:
    rows = header["metadata"]["time_reference_stations"]
    codes = sorted(str(row["station_code"]) for row in rows)
    return {
        "header_declared_stations": codes,
        "bounded_pair_set_for_later_geometry_only_review": [
            list(pair) for pair in combinations(codes, 2)
        ],
        "station_count": len(codes),
        "pair_count": len(list(combinations(codes, 2))),
        "current_numerical_calibration_state": (
            "DESCRIPTIVE_BIAS_AND_FREQUENCY_SHIFT_PRESENT; FINITE_HELDOUT_"
            "UNCERTAINTY_AND_APPLICABILITY_NOT_YET_PROVED"
        ),
    }


def build_review() -> dict[str, object]:
    inputs = load_frozen_inputs()
    pair = one_satellite_pair()
    four_receive = four_link_same_receive_epochs()
    four_transmit = four_link_same_transmit_epochs()

    receipt: dict[str, object] = {
        "outcome": OUTCOME,
        "review_version": REVIEW_VERSION,
        "frozen_parent_commit": FROZEN_PARENT_COMMIT,
        "frozen_input_receipt_sha256": FROZEN_RECEIPT_HASHES,
        "scope": {
            "network_access": "ZERO",
            "orbit_product_access": "ZERO",
            "rinex_artifact_access": "ZERO",
            "observation_values_access": "ZERO",
            "orbital_score": "NOT_EVALUATED",
            "geometry_search": "NOT_EVALUATED",
            "new_gate": "NONE",
        },
        "physical_question": (
            "WHICH_COMPOUND_DORIS_OBSERVABLE_PRESERVES_ORBITAL_GEOMETRY_"
            "WHILE_REMOVING_OR_INDEPENDENTLY_WITNESSING_CLOCK_AND_CHANNEL_TERMS"
        ),
        "frozen_coordinate": {
            "input": "EXACT_RATIONAL_L1_L2_IONOSPHERE_FREE_PHASE",
            "first_order_ionosphere": "CANCELLED_EXACTLY_PER_LINK",
            "event_key_rule": (
                "CLOCK_STATES_CANCEL_ONLY_WHEN_HARDWARE_OWNER_AND_PHYSICAL_"
                "EVENT_ARE_IDENTICAL"
            ),
        },
        "topologies": {
            "one_satellite_two_time_reference_beacons": {
                "coefficients": _coefficient_summary(pair),
                "exact_cuts": [
                    "FIRST_ORDER_IONOSPHERE_PER_LINK",
                    "SHARED_RECEIVER_CLOCK_AT_COMMON_RECEIVE_EPOCH",
                    "SHARED_RECEIVER_PROPER_TIME_AT_COMMON_RECEIVE_EPOCH",
                ],
                "transmitter_clock_role": (
                    "NOT_CANCELLED; POTENTIALLY_OBSERVABLE_AGAINST_EXTERNAL_TIME_"
                    "REFERENCE_IF_APPLICABLE_UNCERTAINTY_IS_FINITE"
                ),
                "channel_role": (
                    "NOT_CANCELLED; REQUIRES_FIXED_PROCESSING_UNIT_IDENTITY_AND_"
                    "FINITE_NONCOMMON_STABILITY_BOUND"
                ),
                "claim_ceiling": (
                    "ORBITAL_VERSUS_FROZEN_NULL_AFTER_GEOMETRY_AND_ALL_REMAINING_"
                    "FINITE_ENVELOPES_ARE_ADMITTED"
                ),
                "rank": 1,
            },
            "two_satellites_two_beacons_same_receive_epoch_per_satellite": {
                "coefficients": _coefficient_summary(four_receive),
                "exact_cuts": [
                    "FIRST_ORDER_IONOSPHERE_PER_LINK",
                    "EACH_SATELLITE_RECEIVER_CLOCK_AT_ITS_COMMON_RECEIVE_EPOCH",
                    "EACH_SATELLITE_RECEIVER_PROPER_TIME_AT_ITS_COMMON_RECEIVE_EPOCH",
                ],
                "transmitter_clock_role": (
                    "NOT_CANCELLED; EACH_BEACON_REMAINS_A_DIFFERENCE_BETWEEN_TWO_"
                    "RETARDED_EMISSION_EPOCHS"
                ),
                "channel_role": "FOUR_NONCOMMON_BRANCH_TERMS_REMAIN",
                "claim_ceiling": (
                    "CROSS_SATELLITE_CONSISTENCY_OR_SHORT_LAG_USO_TEST; NOT_AN_"
                    "USO_FREE_ORBITAL_OBSERVABLE"
                ),
                "rank": 2,
            },
            "two_satellites_two_beacons_same_transmit_epoch_per_beacon": {
                "coefficients": _coefficient_summary(four_transmit),
                "exact_cuts": [
                    "FIRST_ORDER_IONOSPHERE_PER_LINK",
                    "EACH_BEACON_CLOCK_AT_ITS_COMMON_TRANSMIT_EPOCH",
                    "EACH_BEACON_PROPER_TIME_AT_ITS_COMMON_TRANSMIT_EPOCH",
                ],
                "receiver_clock_role": (
                    "NOT_CANCELLED; EACH_SATELLITE_IS_EVALUATED_AT_DIFFERENT_"
                    "RECEIVE_EPOCHS_FOR_THE_TWO_BEACONS"
                ),
                "channel_role": "FOUR_NONCOMMON_BRANCH_TERMS_REMAIN",
                "claim_ceiling": "CLOCK_TRADE_ONLY; NOT_A_CLOCK_FREE_OBSERVABLE",
                "rank": 3,
            },
            "limited_c1_c2_time_witness": {
                "exact_cuts": [],
                "receiver_clock_role": (
                    "REDUNDANT_FOR_AN_EXACT_COEPOCH_INTER_BEACON_PHASE_"
                    "DIFFERENCE_WHERE_RECEIVER_CLOCK_ALREADY_CANCELS"
                ),
                "transmitter_clock_role": (
                    "STANDARD_BEACON_USO_IS_NOT_INDEPENDENTLY_IDENTIFIED_BY_CODE_"
                    "ON_THE_SAME_LINK"
                ),
                "minimum_if_used": (
                    "TIME_REFERENCE_VALID_CODE_PLUS_MULTI_BEACON_CLOCK_SOLUTION;"
                    "LIKELY_FULL_DORIS_TIME_OR_POD_SCOPE"
                ),
                "claim_ceiling": "SAME_PATH_DIAGNOSTIC_WITHOUT_A_SEPARATE_CLOCK_MODEL",
                "rank": 4,
            },
        },
        "noncommutation_result": {
            "same_receive_epoch": (
                "CANCELS_RECEIVER_CLOCKS_BUT_NOT_BEACON_CLOCKS_AT_RETARDED_EPOCHS"
            ),
            "same_transmit_epoch": (
                "CANCELS_BEACON_CLOCKS_BUT_NOT_RECEIVER_CLOCKS_AT_LINK_DEPENDENT_"
                "RECEPTION_EPOCHS"
            ),
            "consequence": (
                "TWO_SATELLITES_DO_NOT_BY_THEMSELVES_CREATE_A_CLOCK_FREE_FOUR_"
                "LINK_OBSERVABLE_IN_NONDEGENERATE_GEOMETRY"
            ),
        },
        "time_reference_scope": _time_reference_scope(inputs["development_header"]),
        "selection": {
            "recommended_topology": "ONE_SATELLITE_TWO_TIME_REFERENCE_BEACONS",
            "why": [
                "PRESERVES_DISTRIBUTED_BEACON_GEOMETRY",
                "CANCELS_SHARED_RECEIVER_CLOCK_AND_PROPER_TIME_EXACTLY",
                "REPLACES_UNCHARACTERIZED_STANDARD_BEACON_USO_WITH_AN_EXTERNAL_"
                "TIME_REFERENCE_PATH_RATHER_THAN_AN_ALGEBRAIC_APPROXIMATION",
                "ADDS_NO_SECOND_SPACEBORNE_RECEIVER_OR_FOUR_EXTRA_CHANNEL_CUTS",
            ],
            "not_yet_admitted": [
                "NO_ORBITAL_GEOMETRY_HAS_BEEN_EVALUATED_FOR_THE_SIX_FROZEN_PAIRS",
                "TIME_REFERENCE_CALIBRATION_UNCERTAINTY_AND_HELDOUT_APPLICABILITY",
                "PROCESSING_UNIT_IDENTITY_AND_NONCOMMON_CHANNEL_STABILITY",
                "ABSOLUTE_EVENT_TIME_AND_REMAINING_PATH_ENVELOPES",
            ],
            "maximum_next_action": (
                "ORBIT_ONLY_DISCRIMINABILITY_SCREEN_OF_THE_SIX_FROZEN_HEADER_"
                "DECLARED_TIME_REFERENCE_PAIRS; NO_OBSERVATION_ACCESS"
            ),
        },
        "shock": (
            "ADDING_A_SECOND_SATELLITE_MOVES_THE_BEACON_CLOCK_TO_A_RETARDED_TIME_"
            "DIFFERENCE_BUT_DOES_NOT_CANCEL_IT; RECEIVE_EPOCH_AND_TRANSMIT_EPOCH_"
            "CLOCK_CANCELLATIONS_DO_NOT_COMMUTE"
        ),
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
    print(strict_json(build_review()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
