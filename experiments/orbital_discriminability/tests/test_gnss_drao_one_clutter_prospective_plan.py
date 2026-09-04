"""Tests for the unopened DRAO seven-track prospective proof."""

from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_one_clutter_prospective_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def frozen() -> dict[str, object]:
    return plan.build_plan(ROOT)


def test_plan_selects_unconsumed_drao_geometry_without_artifact(
    frozen: dict[str, object],
) -> None:
    assert frozen["outcome"] == plan.OUTCOME
    assert frozen["observer"]["station_id"] == "DRAO00CAN"
    assert frozen["roles"]["qualification"]["doy"] == 230
    assert frozen["roles"]["primary"]["doy"] == 231
    assert frozen["roles"]["qualification"]["artifact_locator"] is None
    assert frozen["roles"]["primary"]["artifact_locator"] is None
    assert frozen["roles"]["reserve"] is None
    assert set(frozen["artifact_access"].values()) == {0}
    assert frozen["retry_policy"]["before_artifact_selection"] == "ZERO"
    assert frozen["retry_policy"]["post_primary_freeze"] == (
        "ZERO_RETRY_ZERO_NEW_WINDOW_ZERO_REFIT"
    )


def test_route_review_does_not_reopen_consumed_or_rejected_paths(
    frozen: dict[str, object],
) -> None:
    routes = {row["route"]: row for row in frozen["bounded_route_review"]}

    assert routes["ALGO00CAN"]["state"] == ("EXCLUDED_CONSUMED_AND_OUTCOME_CONDITIONED")
    assert routes["WES200USA"]["state"] == ("EXCLUDED_SIGNAL_PRODUCT_SEMANTICS")
    assert routes["DRAO00CAN"]["state"] == ("SELECTED_FROM_EXISTING_ORBIT_ONLY_SCOPE")


def test_geometry_and_three_guard_regression_are_frozen(
    frozen: dict[str, object],
) -> None:
    geometry = frozen["geometry"]

    assert geometry["candidate_codebook"] == list(plan.EXPECTED_CODEBOOK)
    assert geometry["codebook_available_to_scorer"] is False
    assert geometry["raw_epochs"] == 139
    assert geometry["prefix_epochs"] == 79
    assert geometry["heldout_epochs"] == 60
    assert geometry["primary_exact_controlling_separation_m"] == pytest.approx(
        49_319.268201329585
    )
    assert geometry["primary_robust_lower_margin_m"] == pytest.approx(
        27_300.16449738739
    )
    assert geometry["primary_robust_lower_margin_m"] == pytest.approx(
        geometry["primary_exact_controlling_separation_m"]
        - geometry["three_guard_required_separation_m"]
    )


def test_one_clutter_surface_is_symmetric_and_fixed(
    frozen: dict[str, object],
) -> None:
    topology = frozen["root_topology"]

    assert topology == {
        "observed_tracks_required": 7,
        "evaluated_tracks_per_hypothesis": 6,
        "clutter_budget": 1,
        "all_exclusions_enumerated": True,
        "posthoc_track_removal": False,
        "orbital_hypotheses": 5_040,
        "time_reversed_null_hypotheses": 5_040,
        "affine_null_hypotheses": 7,
        "total_hypotheses": 10_087,
        "same_exclusion_budget_for_every_family": True,
    }


def test_physical_envelope_must_pass_before_artifact_selection(
    frozen: dict[str, object],
) -> None:
    admission = frozen["pre_artifact_admission"]

    assert admission["state"] == "REQUIRED_NOT_YET_EVALUATED"
    assert admission["maximum_aggregate_effect_m"] == plan.PAIRWISE_GUARD_M
    assert admission["artifact_selection_allowed_before_admission"] is False
    assert len(admission["terms_that_cannot_default_to_zero"]) == 8
    assert admission["failure_terminal"] == "DRAO_PHYSICAL_ENVELOPE_NOT_ADMITTED"


def test_identity_and_claim_boundaries_remain_narrow(
    frozen: dict[str, object],
) -> None:
    measurement = frozen["measurement_contract"]
    outcomes = set(frozen["future_outcomes"])

    assert measurement["identity_boundary"] == (
        "PRN_LABELS_SEALED_UNTIL_AFTER_OPAQUE_SCORE_RECEIPT_HASH"
    )
    assert measurement["persisted_observation_values"] == 0
    assert "AMBIGUOUS" in outcomes
    assert "ORBITAL_INJECTION_DISCORDANT" in outcomes
    assert "ORBITAL_INJECTION_CONCORDANT" in outcomes
    assert frozen["observer"]["receiver_family_independence_claimed"] is False
    assert "CODE_FREE_IDENTITY" in frozen["claim_exclusions"]
    assert "MULTI_OBSERVER_GEOMETRY" in frozen["claim_exclusions"]


def test_plan_has_no_network_or_observation_product_surface() -> None:
    source = inspect.getsource(plan).lower()

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        ".crx",
        ".rnx",
        "root_ftp",
        "product_url",
    ):
        assert forbidden not in source


def test_persisted_plan_matches_builder_and_source(frozen: dict[str, object]) -> None:
    path = ROOT / plan.PLAN_NAME
    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert persisted == frozen
    assert path.stat().st_size == 7_729
    assert sha256(path.read_bytes()).hexdigest() == (
        "a26dcc8e2f2ef00c345d93f2e64132a2536349fcfe0790ba198ae50046e9bb58"
    )
    assert frozen["frozen_sources"]["plan_source_canonical_sha256"] == (
        plan.canonical_sha256(Path(plan.__file__))
    )


def test_frozen_input_hash_change_is_refused(tmp_path: Path) -> None:
    for name in (
        plan.GEOMETRY_NAME,
        plan.ROOTS_NAME,
        plan.ALGO_TERMINAL_NAME,
        plan.WES_TERMINAL_NAME,
    ):
        (tmp_path / name).write_bytes((ROOT / name).read_bytes())
    path = tmp_path / plan.GEOMETRY_NAME
    path.write_bytes(path.read_bytes() + b"\n")

    with pytest.raises(plan.DraoPlanError, match="FROZEN_RECEIPT_HASH_CHANGED"):
        plan.build_plan(tmp_path)
