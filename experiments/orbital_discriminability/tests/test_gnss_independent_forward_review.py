from __future__ import annotations

import json
from math import isclose
from pathlib import Path

import pytest

from experiments.orbital_discriminability import gnss_independent_forward_review as review


ROOT = Path(__file__).parents[1]
RECEIPT = ROOT / "GNSS_INDEPENDENT_FORWARD_REVIEW_RECEIPT.json"


def load_receipt() -> dict[str, object]:
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def pair(pair_id: str, state: str, margin_hz: float) -> dict[str, object]:
    return {
        "pair_id": pair_id,
        "stations": [],
        "pair_selection_state": state,
        "candidate_envelopes": [{"remaining_physical_margin_hz": margin_hz}],
    }


def test_manifest_and_receipt_are_strict_and_bound() -> None:
    receipt = load_receipt()
    assert receipt["review_manifest_sha256"] == review.review_manifest_sha256()
    assert review.strict_json(receipt)
    with pytest.raises(ValueError):
        review.strict_json({"bad": float("nan")})


def test_selection_prefers_falsification_power_after_provenance() -> None:
    selected = review.select_candidate(
        [
            pair("unknown_but_large", "EXCLUDED_ANTENNA_CALIBRATION_PROVENANCE_UNKNOWN", 9_000.0),
            pair("negative", "ELIGIBLE_FOR_NAVIGATION_ONLY_SELECTION", -1.0),
            pair("admitted", "ELIGIBLE_FOR_NAVIGATION_ONLY_SELECTION", 100.0),
        ]
    )
    assert selected is not None
    assert selected["pair_id"] == "admitted"
    assert review.select_candidate([pair("negative", "ELIGIBLE_FOR_NAVIGATION_ONLY_SELECTION", 0.0)]) is None


def test_real_navigation_result_is_numerically_regressed() -> None:
    receipt = load_receipt()
    selected = receipt["selected_candidate"]
    candidate = selected["candidate"]
    assert selected["pair_id"] == "KIRU_MAT1"
    assert (candidate["target"], candidate["reference"]) == ("G20", "G22")
    assert candidate["wrong_orbit_family"]["controlling_alternative"] == "G14"
    assert isclose(
        candidate["controlling_heldout_separation_hz"],
        6_233.797940337912,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert isclose(
        candidate["pairwise_comparison_envelope_hz"],
        709.7188745312208,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert isclose(
        candidate["remaining_physical_margin_hz"],
        5_524.079065806692,
        rel_tol=0.0,
        abs_tol=1e-9,
    )
    assert candidate["input_window"]["minimum_elevation_deg"]["KIRU00SWE"]["G22"] > 15.0


def test_qualification_and_primary_are_distinct_and_unopened() -> None:
    receipt = load_receipt()
    qualification = receipt["product_roles"]["qualification"]
    primary = receipt["product_roles"]["primary"]
    assert {item["station_id"] for item in qualification} == {"KIRU00SWE", "MAT100ITA"}
    assert {item["station_id"] for item in primary} == {"KIRU00SWE", "MAT100ITA"}
    assert {item["name"] for item in qualification}.isdisjoint(
        {item["name"] for item in primary}
    )
    for item in qualification + primary:
        assert item["sha256"] is None
        assert item["payload_opened"] is False
        assert item["header_opened"] is False
        assert item["head_is_not_field_topology_evidence"] is True


def test_review_grants_no_measurement_or_plan_authority() -> None:
    receipt = load_receipt()
    assert receipt["outcome"] == review.OUTCOME_READY
    assert set(receipt["measurement_access"].values()) == {0}
    assert receipt["qualification_access_authorized"] is False
    assert receipt["primary_access_authorized"] is False
    assert receipt["prospective_plan_frozen"] is False
    assert receipt["new_gate_created"] is False
    assert receipt["next_exact_blocker"] == (
        "QUALIFICATION_PRODUCT_FIELD_TOPOLOGY_AND_DECODER_NATIVE_CONTINUITY_UNPROVEN"
    )
