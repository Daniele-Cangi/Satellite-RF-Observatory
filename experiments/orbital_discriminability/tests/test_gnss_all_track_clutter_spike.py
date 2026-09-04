"""Tests for the closed seven-track, one-clutter synthetic mechanism."""

from __future__ import annotations

import inspect
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_all_track_clutter_scorer as scorer
from experiments.orbital_discriminability import gnss_all_track_clutter_spike as spike


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def receipt() -> dict[str, object]:
    return spike.build_receipt(ROOT)


def scenarios(receipt: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["name"]: row for row in receipt["scenarios"]}


def test_scorer_has_no_signal_identity_or_network_surface() -> None:
    assert list(inspect.signature(scorer.score_one_clutter_tracks).parameters) == [
        "tracks_m",
        "hypotheses",
        "pairwise_guard_m",
    ]
    source = Path(scorer.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "prn",
        "g06",
        "g14",
        "g17",
        "g19",
        "g22",
        "g30",
        "code_identity",
        "mapping_seal",
        "import requests",
        "import urllib",
        "import socket",
    ):
        assert forbidden not in source


def test_surface_is_symmetric_and_bounded(receipt: dict[str, object]) -> None:
    surface = receipt["opaque_surface"]
    selection = receipt["selection_boundary"]

    assert surface["observed_tracks"] == 7
    assert surface["orbital_injections"] == 7 * 720 == 5_040
    assert surface["time_reversed_geometry_nulls"] == 7 * 720 == 5_040
    assert surface["affine_only_nulls"] == 7
    assert surface["hypothesis_count"] == 10_087
    assert surface["mapping_available_to_scorer"] is False
    assert selection["clutter_budget"] == 1
    assert selection["tracks_evaluated_per_hypothesis"] == 6
    assert selection["prn_available_to_scorer"] is False
    assert selection["posthoc_track_exclusion"] is False
    assert selection["all_exclusions_enumerated"] is True
    assert selection["same_exclusion_budget_for_orbital_and_null_families"] is True


def test_positive_and_permutation_controls_are_concordant(
    receipt: dict[str, object],
) -> None:
    rows = scenarios(receipt)
    for name in (
        "six_orbits_plus_one_arbitrary_clutter",
        "track_and_clutter_slot_permutation",
        "six_orbits_plus_independent_compiled_orbital_shape",
    ):
        row = rows[name]
        score = row["score_receipt"]
        assert score["score_state"] == "ORBITAL_INJECTION_PREFERRED"
        assert row["reveal_after_score_hash"]["state"] == (
            "ORBITAL_INJECTION_CONCORDANT"
        )
        assert score["orbital_assignment_margin_m"] > spike.PAIRWISE_GUARD_M
        assert score["orbital_vs_best_null_margin_m"] > spike.PAIRWISE_GUARD_M


def test_affine_and_destroyed_geometry_controls_select_nulls(
    receipt: dict[str, object],
) -> None:
    rows = scenarios(receipt)
    affine = rows["all_tracks_prefix_affine"]
    reversed_geometry = rows["time_reversed_geometry"]

    assert affine["score_receipt"]["score_state"] == "NONORBITAL_FAMILY_PREFERRED"
    assert affine["score_receipt"]["preferred_family"] == (scorer.FAMILY_AFFINE_NULL)
    assert reversed_geometry["score_receipt"]["score_state"] == (
        "NONORBITAL_FAMILY_PREFERRED"
    )
    assert reversed_geometry["score_receipt"]["preferred_family"] == (
        scorer.FAMILY_GEOMETRY_NULL
    )
    assert affine["reveal_after_score_hash"]["state"] == "NONORBITAL_NULL_SUPPORTED"
    assert reversed_geometry["reveal_after_score_hash"]["state"] == (
        "NONORBITAL_NULL_SUPPORTED"
    )


def test_excess_and_orbit_like_clutter_do_not_force_confirmation(
    receipt: dict[str, object],
) -> None:
    rows = scenarios(receipt)
    excess = rows["two_arbitrary_clutter_tracks_with_budget_one"]
    missing = rows["missing_expected_candidate_plus_two_compiled_orbital_shapes"]
    duplicate = rows["orbit_like_duplicate_clutter"]
    near_duplicate = rows["locally_time_shifted_orbit_like_clutter"]

    assert excess["score_receipt"]["score_state"] == "NO_ADMISSIBLE_HYPOTHESIS"
    assert missing["score_receipt"]["score_state"] == "NO_ADMISSIBLE_HYPOTHESIS"
    assert duplicate["score_receipt"]["score_state"] == "AMBIGUOUS"
    assert near_duplicate["score_receipt"]["score_state"] == "AMBIGUOUS"
    assert duplicate["score_receipt"]["orbital_assignment_margin_m"] == 0.0
    assert (
        0.0
        < near_duplicate["score_receipt"]["orbital_assignment_margin_m"]
        < spike.PAIRWISE_GUARD_M
    )
    assert excess["reveal_after_score_hash"]["state"] == (
        "ORBITAL_INJECTION_UNRESOLVED"
    )
    assert missing["reveal_after_score_hash"]["state"] == (
        "ORBITAL_INJECTION_UNRESOLVED"
    )
    assert duplicate["reveal_after_score_hash"]["state"] == (
        "ORBITAL_INJECTION_UNRESOLVED"
    )
    assert near_duplicate["reveal_after_score_hash"]["state"] == (
        "ORBITAL_INJECTION_UNRESOLVED"
    )


def test_post_score_identity_witness_can_veto_physical_confirmation(
    receipt: dict[str, object],
) -> None:
    row = scenarios(receipt)["post_score_code_witness_disagrees_with_selected_orbits"]

    assert row["score_receipt"]["score_state"] == "ORBITAL_INJECTION_PREFERRED"
    assert row["reveal_after_score_hash"]["state"] == ("ORBITAL_INJECTION_DISCORDANT")


def test_structured_clutter_fixture_is_hash_bound_and_model_only(
    receipt: dict[str, object],
) -> None:
    fixture = receipt["closed_development_fixture"]["structured_clutter_fixture"]

    assert fixture["artifact"] == spike.STRUCTURED_CLUTTER_FIXTURE_NAME
    assert fixture["sha256"] == spike.STRUCTURED_CLUTTER_FIXTURE_SHA256
    assert fixture["curve_names"] == list(spike.STRUCTURED_CLUTTER_CURVES)
    assert fixture["raw_epoch_count"] == 139
    assert fixture["same_observer_or_pass_as_synthetic_tracks"] is False
    assert fixture["concurrent_visibility_claim"] is False
    assert fixture["observation_values_used"] == 0


def test_score_receipts_are_value_free_identity_blind_and_pre_reveal(
    receipt: dict[str, object],
) -> None:
    for row in receipt["scenarios"]:
        score = row["score_receipt"]
        encoded = scorer.strict_json(score).lower()
        assert row["score_receipt_sha256_before_reveal"] == (
            scorer.receipt_sha256(score)
        )
        assert score["identity_reveal_performed"] is False
        assert score["track_or_observation_values_persisted"] == 0
        assert score["opaque_hypothesis_count"] == scorer.HYPOTHESIS_COUNT
        assert score["metric_quantization_decimal_places"] == 6
        assert "code_identity" not in encoded
        for code in spike.MODEL_CODES:
            assert code.lower() not in encoded


def test_spike_is_offline_development_only(receipt: dict[str, object]) -> None:
    assert receipt["outcome"] == spike.OUTCOME_DISCRIMINATIVE
    assert set(receipt["observation_access"].values()) == {0}
    assert receipt["closed_development_fixture"]["network_requests"] == 0
    assert receipt["closed_development_fixture"]["algo_observation_values_used"] == 0
    assert (
        receipt["closed_development_fixture"][
            "consumed_algo_receipts_used_as_numerical_input"
        ]
        is False
    )
    assert receipt["algo_retry_consumed_again"] is False
    assert receipt["real_measurement_score"] == "NOT_EVALUATED"
    assert receipt["primary_selected"] is False
    assert receipt["new_gate"] is False


def test_missing_or_nonfinite_seventh_track_is_refused_before_surface_use() -> None:
    track_ids = tuple(
        sorted(f"T_{index:016X}" for index in range(scorer.OBSERVED_TRACK_COUNT))
    )
    tracks = {track_id: np.zeros(139, dtype=np.float64) for track_id in track_ids}
    missing = dict(tracks)
    missing.pop(track_ids[0])

    with pytest.raises(
        scorer.ClutterScorerError, match="OPAQUE_SEVEN_TRACK_SET_INVALID"
    ):
        scorer.score_one_clutter_tracks(
            missing, (), pairwise_guard_m=spike.PAIRWISE_GUARD_M
        )

    tracks[track_ids[0]][10] = np.nan
    with pytest.raises(scorer.ClutterScorerError, match="TRACK_GAP_OR_NONFINITE"):
        scorer.score_one_clutter_tracks(
            tracks, (), pairwise_guard_m=spike.PAIRWISE_GUARD_M
        )
