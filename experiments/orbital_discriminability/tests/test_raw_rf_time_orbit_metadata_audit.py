from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RECEIPT = (
    ROOT
    / "experiments"
    / "orbital_discriminability"
    / "RAW_RF_TIME_ORBIT_METADATA_AUDIT_RECEIPT.json"
)

EXPECTED_CANDIDATES = {
    "BREAKTHROUGH_LISTEN_VOYAGER1_GBT_SIGMF",
    "CAMRAS_DSLWPB_DWINGELOO_RELEASE_V1",
    "CAMRAS_SLIM_LEV1_LANDING_SIGMF",
    "CAMRAS_ARTEMIS1_TRACKING_SIGMF",
    "ROSETTA_RSI_OPEN_LOOP_PDS",
}


def _receipt() -> dict:
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_terminal_outcome_keeps_frozen_five_family_boundary() -> None:
    receipt = _receipt()
    candidates = receipt["candidates"]

    assert receipt["outcome"] == "NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL"
    assert receipt["candidate_count"] == 5
    assert receipt["sixth_candidate_allowed"] is False
    assert {item["candidate_id"] for item in candidates} == EXPECTED_CANDIDATES
    assert receipt["prospective_plan_synthesized"] is False
    assert receipt["orbital_score_produced"] is False


def test_no_iq_or_signal_derived_value_enters_admission() -> None:
    receipt = _receipt()
    access = receipt["access_accounting"]

    assert access["iq_payload_get_requests"] == 0
    assert access["iq_payload_bytes_read"] == 0
    assert access["iq_samples_decoded"] == 0
    assert access["spectrum_or_waterfall_requests"] == 0
    assert access["signal_derived_values_used_in_admission"] == 0
    assert access["persistent_rf_bytes"] == 0


def test_description_error_is_disclosed_but_cannot_change_physical_decision() -> None:
    receipt = _receipt()
    deviation = receipt["procedural_deviation"]

    assert deviation["typed_state"] == "DESCRIPTION_ERROR"
    assert deviation["persisted"] is False
    assert deviation["used_in_candidate_clause"] is False
    assert deviation["used_in_candidate_decision"] is False
    assert deviation["physical_decision_influence"] is False
    assert receipt["outcome"] == "NO_TIME_AND_ORBIT_QUALIFIED_RAW_RF_VERTICAL"


def test_downstream_discriminability_is_not_evaluated_after_upstream_refusal() -> None:
    receipt = _receipt()

    for candidate in receipt["candidates"]:
        assert candidate["clause_states"]["heldout_signature_above_envelopes"] == "NOT_EVALUATED"
        assert candidate["predicted_heldout_signature"] is None
        assert candidate["maximum_admissible_timing_error_s"] is None

    assert receipt["physical_ranking"]["state"] == "NOT_AUTHORIZED"
    assert receipt["physical_ranking"]["numeric_scores"] == []


def test_unknown_timing_and_orbit_quantities_are_not_replaced_with_zero() -> None:
    receipt = _receipt()
    by_id = {item["candidate_id"]: item for item in receipt["candidates"]}

    assert by_id["BREAKTHROUGH_LISTEN_VOYAGER1_GBT_SIGMF"][
        "documented_numeric_adc_utc_bound_s"
    ] is None
    assert by_id["CAMRAS_SLIM_LEV1_LANDING_SIGMF"]["time_source"] == "internal"
    assert by_id["CAMRAS_ARTEMIS1_TRACKING_SIGMF"][
        "documented_numeric_adc_utc_bound_s"
    ] is None
    assert by_id["CAMRAS_ARTEMIS1_TRACKING_SIGMF"]["orbit_authority"][
        "applicable_numeric_uncertainty"
    ] is None

