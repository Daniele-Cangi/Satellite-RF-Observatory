from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_cross_family_bounded_screen as screen,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / screen.RECEIPT_NAME
RECEIPT_SHA256 = "59125fedbe1afbfa40255681f82d575a516589ca0f7d40186f601a23495e88f0"


def test_candidate_set_is_exact_bounded_and_consumed_roots_do_not_reenter() -> None:
    assert tuple(candidate.station_id for candidate in screen.CANDIDATES) == (
        "WES200USA",
        "WTZR00DEU",
        "ZIMM00CHE",
        "TSKB00JPN",
        "HOB200AUS",
    )
    assert len(screen.CANDIDATES) == 5
    assert not {candidate.station_id for candidate in screen.CANDIDATES} & {
        "GOLD00USA",
        "NLIB00USA",
        "ALGO00CAN",
        "MDO100USA",
    }
    screen.validate_scope(ROOT)


def test_metadata_authorities_are_exact_hash_bound_official_site_logs() -> None:
    assert all(candidate.metadata_state == "OFFICIAL_SITE_LOG_HASHED" for candidate in screen.CANDIDATES)
    assert all(candidate.station_log_url.startswith("https://network.igs.org/") for candidate in screen.CANDIDATES)
    assert all(candidate.station_log_bytes > 20_000 for candidate in screen.CANDIDATES)
    assert all(len(candidate.station_log_sha256) == 64 for candidate in screen.CANDIDATES)


def test_hob2_is_rejected_by_family_and_wes_refusal_is_not_reversed() -> None:
    by_id = {candidate.station_id: candidate for candidate in screen.CANDIDATES}
    assert by_id["HOB200AUS"].geometry_evaluated is False
    assert by_id["HOB200AUS"].admission_state == "CAPABILITY_REJECTED_RECEIVER_FAMILY"
    assert by_id["WES200USA"].admission_state == "CAPABILITY_REJECTED_SIGNAL_PRODUCT_SEMANTICS"
    assert screen._eligible(by_id["WES200USA"]) is False
    assert screen._eligible(by_id["WTZR00DEU"]) is True


def test_manifest_has_no_observation_surface_and_is_not_a_gate() -> None:
    manifest = screen.manifest(ROOT)

    assert manifest["candidate_scope_predeclared"] is True
    assert manifest["candidate_limit"] == 5
    assert manifest["new_gate"] is False
    assert manifest["generic_framework"] is False
    assert manifest["primary_selected"] is False
    assert set(manifest["observation_boundary"].values()) == {0, False}
    assert len(screen.manifest_sha256(ROOT)) == 64


def test_navigation_scope_remains_the_three_exact_frozen_days() -> None:
    assert tuple(candidate.doy for candidate in screen.NAVIGATION_CANDIDATES) == (
        221,
        222,
        223,
    )


def test_candidate_outcomes_separate_geometry_from_capability_refusal() -> None:
    candidates = screen.CANDIDATES
    cases = [
        {
            "station_id": "WES200USA",
            "joint_visible_epoch_count": 200,
            "case_admitted": True,
        },
        {
            "station_id": "WTZR00DEU",
            "joint_visible_epoch_count": 0,
            "case_admitted": False,
        },
    ]

    outcomes = {
        row["station_id"]: row
        for row in screen.candidate_outcomes(candidates, cases, set())
    }
    assert outcomes["WES200USA"]["state"] == (
        "GEOMETRY_POSITIVE_BUT_CAPABILITY_REJECTION_PRESERVED"
    )
    assert outcomes["WTZR00DEU"]["state"] == (
        "NO_COMPLETE_139_EPOCH_JOINT_VISIBILITY"
    )
    assert outcomes["HOB200AUS"]["state"] == (
        "NOT_EVALUATED_RECEIVER_FAMILY_REJECTED"
    )


def test_strict_json_rejects_nonfinite_numbers() -> None:
    assert json.loads(screen.strict_json(screen.manifest(ROOT))) == screen.manifest(ROOT)
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        screen.strict_json({"bad": float("inf")})


def test_frozen_receipt_stops_before_observation_access() -> None:
    payload = RECEIPT.read_bytes()
    frozen = json.loads(payload)

    assert len(payload) == 48_183
    assert sha256(payload).hexdigest() == RECEIPT_SHA256
    assert frozen["source_commit"] == (
        "f67e0d7e9c74a97eb4cbc211871d60140087a40a"
    )
    assert frozen["source_sha256"] == screen.source_sha256()
    assert frozen["manifest_sha256"] == screen.manifest_sha256(ROOT)
    assert frozen["outcome"] == screen.OUTCOME_NONE
    assert frozen["cross_family_shortlist"] == []
    assert frozen["recommended_qualification_root"] is None
    assert frozen["next_maximum"] == "STOP_TRADITIONAL_GNSS_REPLICATION"
    assert set(frozen["observation_access"].values()) == {0}
    assert frozen["qualification_artifact_selected"] is False
    assert frozen["primary_selected"] is False
    assert frozen["prospective_plan_frozen"] is False

    outcomes = {row["station_id"]: row for row in frozen["candidate_outcomes"]}
    assert outcomes["WES200USA"]["state"] == (
        "GEOMETRY_POSITIVE_BUT_CAPABILITY_REJECTION_PRESERVED"
    )
    assert outcomes["WTZR00DEU"]["maximum_joint_visible_epoch_count"] == 0
    assert outcomes["ZIMM00CHE"]["maximum_joint_visible_epoch_count"] == 0
    assert outcomes["TSKB00JPN"]["maximum_joint_visible_epoch_count"] == 113
    assert outcomes["HOB200AUS"]["state"] == (
        "NOT_EVALUATED_RECEIVER_FAMILY_REJECTED"
    )
