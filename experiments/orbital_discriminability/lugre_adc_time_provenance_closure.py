"""Close the LuGRE route when public ADC-time provenance is insufficient.

This bounded audit consumes only already-public documentation and the frozen
LuGRE metadata receipt.  It has no network client, archive reader, IQ decoder,
telemetry parser, detector, orbit propagator or scorer.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence

from experiments.orbital_discriminability import lugre_prospective_metadata_audit


AUDIT_VERSION: Final = "lugre-adc-time-provenance-closure-v1"
RECEIPT_NAME: Final = "LUGRE_ADC_TIME_PROVENANCE_CLOSURE_RECEIPT.json"
PREVIOUS_RECEIPT_NAME: Final = "LUGRE_PROSPECTIVE_METADATA_AUDIT_RECEIPT.json"
PREVIOUS_RECEIPT_SHA256: Final = (
    "f44c6c92858b87adec65e86794403cdd70f834b6101567aa725526afb79a7730"
)
OUTCOME: Final = "LUGRE_ROUTE_CLOSED_BY_ABSOLUTE_TIME_PROVENANCE"


PUBLIC_EVIDENCE: Final = (
    {
        "role": "MISSION_TIME_ARCHITECTURE",
        "authority": "NASA_NTRS",
        "citation_id": "20240012279",
        "title": "Science Objectives and Investigations for the Lunar GNSS Receiver Experiment (LuGRE)",
        "url": (
            "https://ntrs.nasa.gov/api/citations/20240012279/downloads/"
            "ION_GNSS_2024_ScienceInvestigations_Paper_v1.pdf"
        ),
        "bytes": 1_638_343,
        "sha256": "e06a742766d748f215f65e2c3b818aa803814edd30317d602dd5c835a26de913",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
        "finding": (
            "RECEIVER_TIME_IS_COMMAND_INITIALIZED_THEN_GNSS_SYNCHRONIZED_AND_"
            "VCTCXO_PROPAGATED_BUT_NO_NUMERICAL_ADC_BINDING_OR_OPERATION_STATE_IS_GIVEN"
        ),
        "can_reduce_adc_time_envelope": False,
    },
    {
        "role": "PREFLIGHT_CLOCK_MODEL",
        "authority": "NASA_NTRS",
        "citation_id": "20220010106",
        "title": "Navigation Performance Analysis and Trades for LuGRE",
        "url": (
            "https://ntrs.nasa.gov/api/citations/20220010106/downloads/"
            "AAS_2022_LuGRE_Analysis_STRIVES_v2.pdf"
        ),
        "bytes": 1_906_135,
        "sha256": "660f4a5bd925381a9a4b2d2094a1375231c0b04290d9d0c020508d6714db3d13",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
        "finding": (
            "PREDICTED_TYPICAL_VCTCXO_ALLAN_DEVIATION_IS_FREQUENCY_STABILITY_NOT_"
            "ABSOLUTE_TIME_AND_THE_PAPER_DEFERS_FLIGHT_UNIT_MEASUREMENT"
        ),
        "can_reduce_adc_time_envelope": False,
    },
    {
        "role": "PREFLIGHT_QUALIFICATION_SCOPE",
        "authority": "POLITECNICO_DI_TORINO_INSTITUTIONAL_REPOSITORY",
        "doi": "10.1109/WISEE58383.2023.10289430",
        "title": "The Space Qualification Process of the LuGRE GNSS Payload",
        "url": (
            "https://iris.polito.it/retrieve/handle/11583/2986317/"
            "42ba7e80-0d36-4356-b310-f9d7c7ab8db4/"
            "The_Space_Qualification_Process_of_the_LuGRE_GNSS_Payload_Pulliero.pdf"
        ),
        "bytes": 422_417,
        "sha256": "285da7c1623bbe8237ff8479b311b1f15529a297487b7b4f2cc958ae32058c74",
        "provenance": "INDEPENDENT_OF_TARGET_RF",
        "finding": (
            "PUBLISHED_MANUSCRIPT_DESCRIBES_FUNCTIONAL_AND_ENVIRONMENTAL_QUALIFICATION_"
            "BUT_PUBLISHES_NO_END_TO_END_ADC_TIME_RESULT"
        ),
        "can_reduce_adc_time_envelope": False,
    },
    {
        "role": "GENERIC_RECEIVER_FAMILY_PERFORMANCE",
        "authority": "QASCOM",
        "title": "GNSS Receivers",
        "url": "https://www.qascom.com/products/gnss-receivers/",
        "retrieved_utc_date": "2026-08-30",
        "captured_utf8_bytes": 186_438,
        "captured_utf8_sha256": (
            "82144512af30fb0dc2146abe2d121f2990b02e8b62c1a115df5aec57695f1bde"
        ),
        "provenance": "INDEPENDENT_OF_TARGET_RF",
        "finding": (
            "GENERIC_QN400_S_TIMING_ACCURACY_50_NS_IS_NOT_BOUND_TO_LUGRE_FLIGHT_"
            "CONFIGURATION_IQS_CAPTURE_STATE_OR_ADC_SAMPLE_ZERO"
        ),
        "can_reduce_adc_time_envelope": False,
    },
)


TIME_CHAIN: Final = (
    {
        "edge": "ADC_SAMPLE_ZERO_TO_IQS_RXTIME_TAG",
        "semantics": "SC_START_IS_DESCRIBED_AS_ACTUAL_IQS_CAPTURE_START",
        "finite_error_bound_s": None,
        "state": "UNRESOLVED_LATENCY_AND_LATCH_ERROR",
    },
    {
        "edge": "IQS_RXTIME_TAG_TO_RECEIVER_REFERENCE_TIME",
        "semantics": "IQS_RXTIME_IS_RECEIVER_TIME",
        "finite_error_bound_s": None,
        "state": "UNRESOLVED_TAGGING_ERROR",
    },
    {
        "edge": "RECEIVER_REFERENCE_TIME_TO_GPST",
        "semantics": "COMMAND_INITIALIZED_OR_GNSS_SYNCHRONIZED_THEN_VCTCXO_PROPAGATED",
        "finite_error_bound_s": None,
        "state": "UNRESOLVED_OPERATION_SPECIFIC_SYNC_STATE_AND_RESIDUAL",
    },
    {
        "edge": "GPST_LABEL_TO_TRUE_GPST_UTC",
        "semantics": "MISSION_TELEMETRY_TIME_SCALE_IS_GPST",
        "finite_error_bound_s": None,
        "state": "UNRESOLVED_END_TO_END_ABSOLUTE_ERROR",
    },
)


REJECTED_SUBSTITUTES: Final = (
    {
        "candidate": "SDRX_AND_OPTABLE_MILLISECOND_FIELDS",
        "reason": "REPRESENTATION_AND_CONVENTION_DO_NOT_BOUND_ACCURACY",
    },
    {
        "candidate": "GENERIC_QN400_S_50_NS_TIMING_ACCURACY",
        "reason": "NO_LUGRE_IQS_ADC_SAMPLE_ZERO_APPLICABILITY",
    },
    {
        "candidate": "IDENTICAL_MODEL_OR_PREDICTED_VCTCXO_ALLAN_DEVIATION",
        "reason": "FREQUENCY_STABILITY_DOES_NOT_ESTABLISH_INITIAL_TIME_OFFSET_OR_ADC_LATCH",
    },
    {
        "candidate": "LANDER_TIME_COMMAND",
        "reason": "NO_COMMAND_TO_RECEIVER_TO_ADC_NUMERICAL_LATENCY_OR_JITTER_BOUND",
    },
    {
        "candidate": "POSTFLIGHT_PVT_CLOCK_BIAS_OR_STARTUP_TRANSIENT",
        "reason": "OUTCOME_CONDITIONED_AND_NOT_AN_INDEPENDENT_IQS_ADC_BINDING",
    },
    {
        "candidate": "TARGET_RF_FITTED_TIME_PHASE",
        "reason": "FORBIDDEN_OUTCOME_CONDITIONING_WOULD_WEAKEN_THE_HELD_OUT_TEST",
    },
)


def canonical_sha256(path: Path) -> str:
    """Hash a text artifact after normalizing checkout line endings."""

    return sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def compose_end_to_end_bound_s(edges: Sequence[Mapping[str, object]]) -> float | None:
    """Return a conservative sum only when every causal edge is numerically bounded."""

    total = 0.0
    for edge in edges:
        value = edge.get("finite_error_bound_s")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            return None
        total += float(value)
    return total


def build_receipt(root: Path, source_commit: str) -> dict[str, object]:
    previous = root / PREVIOUS_RECEIPT_NAME
    actual_previous_hash = canonical_sha256(previous)
    if actual_previous_hash != PREVIOUS_RECEIPT_SHA256:
        raise ValueError("FROZEN_LUGRE_METADATA_RECEIPT_HASH_MISMATCH")

    previous_value = json.loads(previous.read_text(encoding="utf-8"))
    if previous_value["outcome"] != lugre_prospective_metadata_audit.OUTCOME:
        raise ValueError("FROZEN_LUGRE_METADATA_OUTCOME_MISMATCH")

    bound = compose_end_to_end_bound_s(TIME_CHAIN)
    if bound is not None:
        raise ValueError("CLOSURE_OUTCOME_REQUIRES_AN_UNRESOLVED_TIME_CHAIN")

    result: dict[str, object] = {
        "schema": "satellite-rf-observatory/lugre-adc-time-provenance-closure/v1",
        "audit_version": AUDIT_VERSION,
        "source_commit": source_commit,
        "source_sha256": canonical_sha256(Path(__file__)),
        "physical_question": (
            "CAN_THE_PUBLIC_OUTCOME_INDEPENDENT_RECORD_NUMERICALLY_BIND_LUGRE_IQS_"
            "ADC_SAMPLE_ZERO_TO_TRUE_GPST_UTC"
        ),
        "information_value": (
            "DECIDES_WHETHER_THE_POSITIVE_OP76_GEOMETRY_CAN_SUPPORT_AN_INTERPRETABLE_"
            "PROSPECTIVE_NEGATIVE"
        ),
        "bounded_search_scope": {
            "archive_native_product_documents": True,
            "official_nasa_mission_and_clock_documents": True,
            "published_preflight_qualification_manuscript": True,
            "manufacturer_receiver_family_page": True,
            "operator_contact": False,
            "private_documents": False,
            "target_rf_or_telemetry": False,
            "global_nonexistence_claim": False,
        },
        "frozen_input": {
            "receipt": PREVIOUS_RECEIPT_NAME,
            "canonical_sha256": actual_previous_hash,
            "outcome": previous_value["outcome"],
            "controlling_primary_separation_hz": previous_value["detectability"][
                "controlling_primary_separation_hz"
            ],
            "maximum_symmetric_total_per_track_rms_envelope_hz": previous_value[
                "detectability"
            ]["maximum_symmetric_total_per_track_rms_envelope_hz"],
        },
        "public_evidence": list(PUBLIC_EVIDENCE),
        "adc_time_causal_ledger": list(TIME_CHAIN),
        "rejected_substitutes": list(REJECTED_SUBSTITUTES),
        "composed_adc_to_true_gpst_error_bound_s": bound,
        "timing_clause": {
            "state": "UNRESOLVED",
            "reason": "NO_PRODUCT_APPLICABLE_NUMERICAL_BOUND_IN_BOUNDED_PUBLIC_RECORD",
        },
        "candidate_roles": {
            "OP73": "CLOSED_UNOPENED_DEVELOPMENT_CANDIDATE",
            "OP76": "CLOSED_UNOPENED_PRIMARY_CANDIDATE",
            "OP74": "CLOSED_UNOPENED_RESERVE_CANDIDATE",
        },
        "access_boundary": {
            "new_iqs_compressed_payload_bytes": 0,
            "new_iqs_uncompressed_bytes": 0,
            "new_iq_sample_values": 0,
            "new_telemetry_bytes": 0,
            "new_signal_derived_diagnostics": 0,
            "all_three_candidate_products_opened": False,
            "detector_implemented": False,
            "orbital_score_recomputed": False,
        },
        "geometry_result": "PRESERVED_NOT_WEAKENED",
        "roles_frozen": False,
        "prospective_plan_frozen": False,
        "maximum_authorized_claim": (
            "THE_BOUNDED_PUBLIC_RECORD_ESTABLISHES_TIME_SEMANTICS_AND_CLOCK_"
            "MECHANISM_BUT_NOT_A_FINITE_PRODUCT_APPLICABLE_ADC_SAMPLE_ZERO_TO_TRUE_"
            "GPST_UTC_BOUND"
        ),
        "outcome": OUTCOME,
        "minimum_next_physical_route": (
            "SELECT_A_DIFFERENT_ORBIT_FIRST_RAW_IQ_FAMILY_WITH_PREEXISTING_NUMERICAL_"
            "SAMPLE_ZERO_TIME_PROVENANCE"
        ),
        "automatic_successor": False,
    }
    lugre_prospective_metadata_audit.strict_json(result)
    return result


def _git_commit(root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent
    )
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--source-commit")
    parser.add_argument(
        "--output", type=Path, default=Path(__file__).with_name(RECEIPT_NAME)
    )
    args = parser.parse_args(argv)
    receipt = build_receipt(
        args.root, args.source_commit or _git_commit(args.repo_root)
    )
    args.output.write_text(
        lugre_prospective_metadata_audit.strict_json(receipt, pretty=True) + "\n",
        encoding="ascii",
        newline="\n",
    )
    print(
        lugre_prospective_metadata_audit.strict_json(
            {
                "outcome": receipt["outcome"],
                "receipt": str(args.output),
                "iq_sample_bytes": 0,
                "telemetry_bytes": 0,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
