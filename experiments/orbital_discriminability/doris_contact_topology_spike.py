"""Offline sufficiency audit for a DORIS contact-topology observable.

The spike asks whether already frozen descriptive receipts retain enough
structure to compare observed beacon-contact order and duration with an orbit.
It has no network, orbit-product, RINEX-artifact, or observation-value surface.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Mapping

from experiments.live_instrument.models import strict_json_value


SPIKE_VERSION: Final = "doris-contact-topology-spike-v1"
OUTCOME: Final = (
    "DORIS_STRUCTURAL_VISIBILITY_NOT_FALSIFIABLE_FROM_RETAINED_RECEIPT"
)
FROZEN_PARENT_COMMIT: Final = "27b24e9ab5d3e55cd3c4756df663d7fef7956b89"

ROOT: Final = Path(__file__).resolve().parent
HEADER_RECEIPT: Final = ROOT / "DORIS_DEVELOPMENT_HEADER_RECEIPT.json"
STRUCTURAL_RECEIPT: Final = ROOT / "DORIS_DEVELOPMENT_STRUCTURAL_RECEIPT.json"
COEPOCH_RECEIPT: Final = ROOT / "DORIS_EXACT_COEPOCH_REQUALIFICATION_RECEIPT.json"
GEOMETRY_RECEIPT: Final = ROOT / "DORIS_TIME_REFERENCE_GEOMETRY_SCREEN_RECEIPT.json"
STRUCTURAL_SCANNER: Final = ROOT / "doris_development_structural_scan.py"

FROZEN_INPUT_HASHES: Final = {
    "development_header": (
        "b7e48ee0efb2e23be0981ead04df8894c57e23136bfe5facaeaa9fa70bdb0c5a"
    ),
    "development_structure": (
        "8514b7d2df4a832adbecb184c852bca53e261279cf9f87b0d8174348d4377fef"
    ),
    "exact_coepoch": (
        "d1668fccc982d550a949faf68131436b2713d12f28374617eaee82585bf67c9d"
    ),
    "time_reference_geometry": (
        "6f7319cd796fbd9c502438f3c6cfcda2afab98056e869805a8a8e95a0d83016d"
    ),
}
AUDITED_SCANNER_SHA256: Final = (
    "9042f81f04d54136325506c411ec0568db4046841f23c6ed43e5ec6b2ecb140c"
)
FROZEN_EXECUTED_SCANNER_SOURCE_SHA256: Final = (
    "84a0d8171fd780bde03903e6018fb777b99430ad3bca5177aee8911ea7dc16ef"
)


class DorisContactTopologyError(ValueError):
    """Raised when a frozen input or retention invariant has changed."""


def canonical_sha256(path: Path) -> str:
    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def load_frozen_inputs() -> dict[str, object]:
    paths = {
        "development_header": HEADER_RECEIPT,
        "development_structure": STRUCTURAL_RECEIPT,
        "exact_coepoch": COEPOCH_RECEIPT,
        "time_reference_geometry": GEOMETRY_RECEIPT,
    }
    for name, path in paths.items():
        if canonical_sha256(path) != FROZEN_INPUT_HASHES[name]:
            raise DorisContactTopologyError(f"FROZEN_RECEIPT_HASH_MISMATCH:{name}")
    if canonical_sha256(STRUCTURAL_SCANNER) != AUDITED_SCANNER_SHA256:
        raise DorisContactTopologyError("AUDITED_STRUCTURAL_SCANNER_CHANGED")

    payloads = {
        name: json.loads(path.read_text(encoding="utf-8"))
        for name, path in paths.items()
    }
    expected_outcomes = {
        "development_header": "DORIS_DEVELOPMENT_HEADER_REJECTED",
        "development_structure": "DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT",
        "exact_coepoch": "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED",
        "time_reference_geometry": (
            "DORIS_TIME_REFERENCE_TOPOLOGY_NO_JOINT_VISIBILITY"
        ),
    }
    for name, expected in expected_outcomes.items():
        if payloads[name]["outcome"] != expected:
            raise DorisContactTopologyError(f"UNEXPECTED_PARENT_OUTCOME:{name}")
    if payloads["development_structure"]["scanner"]["source_sha256"] != (
        FROZEN_EXECUTED_SCANNER_SOURCE_SHA256
    ):
        raise DorisContactTopologyError("EXECUTED_STRUCTURAL_SCANNER_HASH_CHANGED")
    return payloads


def _retained_evidence(inputs: Mapping[str, object]) -> dict[str, object]:
    header = inputs["development_header"]
    structure = inputs["development_structure"]
    coepoch = inputs["exact_coepoch"]
    declared = list(header["metadata"]["station_codes"])
    summarized = sorted(structure["stations"])
    longest_lists = {
        station_id: len(row["longest_core_segments"])
        for station_id, row in sorted(structure["stations"].items())
    }
    total_summarized_records = sum(
        int(row["record_count"]) for row in structure["stations"].values()
    )
    return {
        "header_declared_station_count": int(
            header["metadata"]["declared_station_count"]
        ),
        "header_station_code_count": len(declared),
        "structurally_summarized_station_ids": summarized,
        "structurally_summarized_station_count": len(summarized),
        "all_station_record_count": int(structure["records"]["station_record_count"]),
        "summarized_station_record_count": total_summarized_records,
        "complete_all_station_presence_sequence_retained": False,
        "retained_longest_core_segment_count_by_station": longest_lists,
        "segment_retention_rule": "FIVE_LONGEST_PER_PRESELECTED_STATION",
        "segment_boundary_semantic": (
            "PHASE_CONTINUITY_LLI_OR_STATION_SAMPLE_GAP; NOT_GEOMETRIC_RISE_SET"
        ),
        "exact_coepoch_subset": {
            "pair": list(coepoch["pair"]["codes"]),
            "both_present_epoch_count": int(
                coepoch["pair"]["target_epoch_presence_counts"]["BOTH"]
            ),
            "scope": "PRESELECTED_PAIR_ONLY_NOT_A_NETWORK_CONTACT_SEQUENCE",
        },
        "header_coverage_descriptors": {
            "time_of_first_observation": "PRESENT_DOR_TIME",
            "time_of_last_observation": "ABSENT",
            "interval": "ABSENT",
        },
        "event_time_bound_to_tai": "UNRESOLVED",
        "numerical_observation_values_decoded": int(
            structure["records"]["numeric_observation_values_decoded"]
        ),
        "numerical_observation_values_persisted": int(
            structure["records"]["numeric_observation_values_persisted"]
        ),
    }


def build_spike() -> dict[str, object]:
    inputs = load_frozen_inputs()
    evidence = _retained_evidence(inputs)
    receipt: dict[str, object] = {
        "outcome": OUTCOME,
        "spike_version": SPIKE_VERSION,
        "spike_source_sha256": source_sha256(),
        "frozen_parent_commit": FROZEN_PARENT_COMMIT,
        "frozen_input_sha256": FROZEN_INPUT_HASHES,
        "audited_structural_scanner_sha256": AUDITED_SCANNER_SHA256,
        "executed_structural_scanner": {
            "commit": inputs["development_structure"]["scanner"]["frozen_commit"],
            "source_sha256": FROZEN_EXECUTED_SCANNER_SOURCE_SHA256,
            "retention_rule_still_present_in_audited_current_source": True,
        },
        "scope": {
            "network_access": "ZERO",
            "new_observation_access": "ZERO",
            "rinex_artifact_access": "ZERO",
            "orbit_artifact_access": "ZERO",
            "observation_values_access": "ZERO",
            "orbital_score": "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY",
            "new_gate": "NONE",
        },
        "physical_question": (
            "CAN_BEACON_CONTACT_ORDER_AND_DURATION_FORM_A_HELDOUT_ORBITAL_"
            "OBSERVABLE_WITHOUT_SIMULTANEOUS_BEACON_VISIBILITY"
        ),
        "candidate_observable": {
            "definition": (
                "ORDERED_PER_STATION_CONTACT_INTERVALS_WITH_ACQUISITION_AND_LOSS_"
                "EVENT_TIMES_AND_DURATIONS"
            ),
            "causal_chain": [
                "CANDIDATE_ORBIT_AND_BEACON_GEOMETRY",
                "PREDICTED_VISIBILITY_INTERVALS",
                "RECEIVER_ACQUISITION_AND_RETENTION",
                "STRUCTURAL_STATION_RECORD_PRESENCE",
                "HELDOUT_CONTACT_ORDER_AND_DURATION",
                "ORBITAL_MODEL_VERSUS_FROZEN_NULLS",
            ],
            "terms_not_required_if_admitted": [
                "PHASE_MAGNITUDE",
                "CARRIER_FREQUENCY",
                "GROUND_BEACON_USO_PHASE",
                "SPACEBORNE_RECEIVER_CLOCK_PHASE",
                "IONOSPHERIC_PHASE_CORRECTION",
                "AMPLITUDE_CALIBRATION",
            ],
            "claim_ceiling": (
                "ORBITAL_VISIBILITY_TOPOLOGY_PREFERRED_WITHIN_A_PREDECLARED_"
                "RECEIVER_ACQUISITION_MODEL; NOT_RF_PHASE_OR_IDENTITY"
            ),
        },
        "retained_evidence": evidence,
        "clause_evaluation": {
            "positive_record_semantic": {
                "state": "PARTIALLY_SUPPORTED",
                "evidence": (
                    "A_RETAINED_STATION_RECORD_PROVES_RECEIVER_OUTPUT_FOR_THAT_"
                    "STATION_AT_THE_TAGGED_DOR_EPOCH"
                ),
                "limit": (
                    "IT_DOES_NOT_IDENTIFY_GEOMETRIC_ACQUISITION_OR_A_RISE_EVENT"
                ),
            },
            "negative_record_semantic": {
                "state": "UNRESOLVED",
                "missing": [
                    "TRACKING_CHANNEL_ALLOCATION_POLICY",
                    "BEACON_ACQUISITION_AND_DROPOUT_POLICY",
                    "TELEMETRY_SELECTION_AND_GROUND_EDITING_POLICY",
                    "RECEIVER_SENSITIVITY_OR_LINK_MARGIN_BOUND",
                ],
                "consequence": "ABSENCE_CANNOT_BE_MAPPED_TO_NOT_VISIBLE",
            },
            "complete_network_event_sequence": {
                "state": "NOT_RETAINED",
                "evidence": (
                    "FOUR_OF_56_STATIONS_SUMMARIZED_AND_ONLY_FIVE_LONGEST_"
                    "SEGMENTS_RETAINED_PER_STATION"
                ),
            },
            "rise_set_event_identification": {
                "state": "NOT_RETAINED",
                "evidence": (
                    "RETAINED_SEGMENT_BREAKS_ARE_PHASE_LLI_OR_SAMPLE_GAPS_NOT_"
                    "GEOMETRIC_CONTACT_BOUNDARIES"
                ),
            },
            "finite_event_time_mapping": {
                "state": "UNRESOLVED",
                "evidence": (
                    "DOR_EPOCH_TAGS_EXIST_BUT_NO_NUMERICAL_DOR_TO_TAI_PHASE_"
                    "CENTER_ERROR_BOUND_WAS_ADMITTED"
                ),
            },
            "matching_development_orbit_grid": {
                "state": "NOT_RETAINED",
                "evidence": (
                    "NO_EXACT_DEVELOPMENT_DAY_ORBIT_TRAJECTORY_IS_BOUND_IN_THE_"
                    "DESCRIPTIVE_RECEIPTS"
                ),
            },
        },
        "open_causal_cuts": [
            "GEOMETRIC_VISIBILITY_TO_RECEIVER_ACQUISITION",
            "ACQUISITION_TO_TRACKING_CHANNEL_ALLOCATION",
            "TRACKING_TO_TELEMETRY_RETENTION",
            "RECORD_ABSENCE_TO_PHYSICAL_NONVISIBILITY",
            "DOR_EVENT_TIME_TO_ORBIT_COORDINATE_TIME",
        ],
        "frozen_null_families": {
            "time_shifted_orbit": "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY",
            "wrong_orbit": "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY",
            "station_identity_permutation": (
                "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY"
            ),
            "schedule_or_coverage_only": (
                "NOT_EVALUATED_INSUFFICIENT_EVENT_TOPOLOGY"
            ),
            "common_reason": (
                "NO_COMPLETE_PREDECLARED_CONTACT_EVENT_SEQUENCE_WITH_"
                "INTERPRETABLE_ABSENCES"
            ),
        },
        "decision": {
            "retrospective_score_authorized": False,
            "measurement_access_authorized": False,
            "primary_selection_authorized": False,
            "thresholds_changed": False,
            "doris_contact_topology_state": (
                "CONCEPTUALLY_PHYSICAL_BUT_NOT_FALSIFIABLE_FROM_RETAINED_RECEIPT"
            ),
            "action": "STOP_WITHOUT_ORBITAL_SCORE_OR_NEW_DATA_ACCESS",
        },
        "minimum_future_contract_not_executed": {
            "structural_retention": [
                "EVERY_STATION_ID_AT_EVERY_RECEIVER_EPOCH",
                "PRESENCE_ABSENCE_AND_CONTINUATION_STATE",
                "ALL_CONTACT_INTERVALS_NOT_TOP_K_SEGMENTS",
                "EXPLICIT_PRODUCT_START_END_AND_GAPS",
            ],
            "causal_admission": [
                "PREDECLARED_TRACKING_CHANNEL_AND_SCHEDULING_POLICY",
                "OUTCOME_INDEPENDENT_ACQUISITION_AND_DROPOUT_ENVELOPE",
                "FINITE_DOR_TO_ORBIT_EVENT_TIME_BOUND",
                "FROZEN_ORBIT_AND_STATION_GEOMETRY_BEFORE_PRIMARY",
            ],
            "still_forbidden": [
                "OBSERVATION_MAGNITUDES",
                "POST_OUTCOME_CONTACT_SELECTION",
                "INTERPRETING_AN_UNMODELED_ABSENCE_AS_NONVISIBILITY",
            ],
        },
        "shock": (
            "STRUCTURE_DISCARDED_AS_NONMEASUREMENT_FOR_THE_PHASE_QUESTION_"
            "BECOMES_THE_MEASUREMENT_FOR_CONTACT_TOPOLOGY; EVIDENCE_RETENTION_"
            "IS_HYPOTHESIS_DEPENDENT"
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
    # A trusted caller may materialize build_spike(); the CLI emits no receipt
    # fields and cannot open an observation or orbit artifact.
    build_spike()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
