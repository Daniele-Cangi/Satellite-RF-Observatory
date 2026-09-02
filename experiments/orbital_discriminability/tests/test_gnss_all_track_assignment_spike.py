"""Tests for the synthetic identity-blind all-track assignment spike."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_all_track_assignment_scorer as blind
from experiments.orbital_discriminability import gnss_all_track_assignment_spike as spike


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / spike.RECEIPT_NAME


def _receipt() -> dict[str, object]:
    return spike.build_receipt(ROOT)


def _scenarios() -> dict[str, dict[str, object]]:
    return {row["name"]: row for row in _receipt()["scenarios"]}


def test_scorer_interface_contains_no_identity_or_reveal_surface() -> None:
    assert list(inspect.signature(blind.score_anonymous_tracks).parameters) == [
        "tracks_m",
        "hypotheses_m",
        "pairwise_guard_m",
    ]
    source = Path(blind.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "g22",
        "g30",
        "g06",
        "prn",
        "code_identity",
        "mapping_seal",
        "import requests",
        "import urllib",
        "import socket",
        "observation decoder",
    ):
        assert forbidden not in source


def test_surface_is_all_bijections_plus_one_non_orbital_null() -> None:
    track_ids, surface, reveal = spike.hypothesis_surface(ROOT)
    assignments = [
        tuple(row["assignment_by_track_order"])
        for row in reveal.values()
        if row["model_class"] == "BIJECTIVE_ORBIT_ASSIGNMENT"
    ]
    nulls = [
        row
        for row in reveal.values()
        if row["model_class"] == "PREFIX_AFFINE_ONLY_NULL"
    ]
    assert len(track_ids) == blind.TRACK_COUNT == 6
    assert len(assignments) == len(set(assignments)) == 720
    assert all(set(assignment) == set(spike.MODEL_CODES) for assignment in assignments)
    assert len(nulls) == 1
    assert len(surface) == blind.HYPOTHESIS_COUNT == 721


def test_correct_assignment_and_track_permutation_are_concordant() -> None:
    scenarios = _scenarios()
    for name in ("complete_correct_assignment", "track_slot_permutation"):
        row = scenarios[name]
        assert row["score_receipt"]["orbital_score_state"] == (
            "OPAQUE_ASSIGNMENT_PREFERRED"
        )
        assert row["reveal_after_score_hash"]["state"] == "ORBIT_CODE_CONCORDANT"


def test_discordant_code_witness_cannot_override_orbital_assignment() -> None:
    row = _scenarios()["complete_code_discordance"]
    assert row["score_receipt"]["orbital_score_state"] == (
        "OPAQUE_ASSIGNMENT_PREFERRED"
    )
    assert row["reveal_after_score_hash"]["state"] == "ORBIT_CODE_DISCORDANT"


def test_non_orbital_affine_control_selects_the_frozen_null() -> None:
    row = _scenarios()["prefix_affine_tracks"]
    assert row["score_receipt"]["orbital_score_state"] == (
        "OPAQUE_ASSIGNMENT_PREFERRED"
    )
    assert row["reveal_after_score_hash"]["best_model"]["model_class"] == (
        "PREFIX_AFFINE_ONLY_NULL"
    )
    assert row["reveal_after_score_hash"]["state"] == "NON_ORBITAL_NULL_SUPPORTED"


def test_absolute_fit_and_ambiguity_controls_prevent_forced_assignment() -> None:
    scenarios = _scenarios()
    mismatch = scenarios["out_of_family_curvature"]
    midpoint = scenarios["assignment_midpoint"]
    assert mismatch["score_receipt"]["orbital_score_state"] == (
        "NO_ADMISSIBLE_OPAQUE_ASSIGNMENT"
    )
    assert mismatch["score_receipt"][
        "best_heldout_max_track_peak_to_peak_m"
    ] > spike.PAIRWISE_GUARD_M
    assert midpoint["score_receipt"]["orbital_score_state"] == "AMBIGUOUS"
    assert midpoint["score_receipt"]["preference_margin_m"] == pytest.approx(0.0)
    assert mismatch["reveal_after_score_hash"]["state"] == (
        "ORBIT_ASSIGNMENT_UNRESOLVED"
    )
    assert midpoint["reveal_after_score_hash"]["state"] == (
        "ORBIT_ASSIGNMENT_UNRESOLVED"
    )


def test_missing_track_and_nonfinite_epoch_are_measurement_refusals() -> None:
    track_ids, surface, _ = spike.hypothesis_surface(ROOT)
    curves = spike._fixture_curves(ROOT)
    tracks = spike._synthetic_tracks(track_ids, spike.MODEL_CODES, curves)
    missing = dict(tracks)
    missing.pop(track_ids[0])
    with pytest.raises(blind.AllTrackScorerError, match="OPAQUE_TRACK_SET_INVALID"):
        blind.score_anonymous_tracks(
            missing, surface, pairwise_guard_m=spike.PAIRWISE_GUARD_M
        )
    tracks[track_ids[0]][10] = np.nan
    with pytest.raises(blind.AllTrackScorerError, match="TRACK_GAP_OR_NONFINITE"):
        blind.score_anonymous_tracks(
            tracks, surface, pairwise_guard_m=spike.PAIRWISE_GUARD_M
        )


def test_score_receipts_are_hashed_before_reveal_and_contain_no_identity() -> None:
    for scenario in _receipt()["scenarios"]:
        score = scenario["score_receipt"]
        rendered = blind.strict_json(score)
        assert scenario["score_receipt_sha256_before_reveal"] == (
            blind.receipt_sha256(score)
        )
        assert score["identity_reveal_performed"] is False
        assert score["track_or_observation_values_persisted"] == 0
        assert score["opaque_hypothesis_count"] == 721
        for forbidden in (*spike.MODEL_CODES, "code_identity"):
            assert forbidden not in rendered


def test_frozen_receipt_is_reproducible_source_bound_and_zero_access() -> None:
    actual = json.loads(RECEIPT.read_text(encoding="utf-8"))
    expected = json.loads(spike.strict_json(_receipt()))
    assert actual == expected
    assert actual["source"]["spike_sha256"] == spike.canonical_sha256(
        Path(spike.__file__)
    )
    assert actual["source"]["scorer_sha256"] == spike.canonical_sha256(
        Path(blind.__file__)
    )
    assert set(actual["observation_access"].values()) == {0}
    assert actual["primary_selected"] is False
    encoded = spike.strict_json(actual)
    assert "NaN" not in encoded and "Infinity" not in encoded
