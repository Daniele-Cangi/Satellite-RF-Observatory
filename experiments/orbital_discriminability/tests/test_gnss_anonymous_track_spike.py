"""Tests for the closed anonymous-track/code-witness mechanism spike."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_anonymous_track_scorer as blind
from experiments.orbital_discriminability import gnss_anonymous_track_spike as spike


ROOT = Path(__file__).resolve().parents[1]


def _receipt() -> dict[str, object]:
    return spike.build_receipt(ROOT)


def _scenarios() -> dict[str, dict[str, object]]:
    return {row["name"]: row for row in _receipt()["scenarios"]}


def test_pure_scorer_has_no_identity_mapping_or_orbital_compiler_surface() -> None:
    signature = inspect.signature(blind.score_anonymous_pair)
    assert list(signature.parameters) == [
        "track_a_m",
        "track_b_m",
        "hypotheses_m",
        "pairwise_guard_m",
    ]
    source = Path(blind.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "g22",
        "g30",
        "g06",
        "mapping_seal",
        "code_identity",
        "import requests",
        "import urllib",
        "import socket",
        "gnss_blind_orbit_assignment",
    ):
        assert forbidden not in source


def test_surface_contains_normal_and_reversed_opaque_families() -> None:
    surface, reveal, by_model = spike.hypothesis_surface(ROOT)

    assert len(surface) == blind.HYPOTHESIS_COUNT == 11
    assert len(reveal) == 11
    assert len(by_model) == 6
    assert sum(
        row["orientation"] == "TRACK_B_MINUS_TRACK_A" for row in reveal.values()
    ) == 5
    assert all(blind.OPAQUE_ID_PATTERN.fullmatch(value) for value in surface)


def test_positive_and_wrong_orbit_controls_do_not_auto_confirm_target() -> None:
    scenarios = _scenarios()
    positive = scenarios["correct_model"]
    wrong = scenarios["wrong_orbit_truth"]

    assert positive["reveal_after_score_receipt_hash"]["model"] == spike.TARGET_MODEL
    assert positive["reveal_after_score_receipt_hash"]["state"] == (
        "ORBIT_CODE_CONCORDANT"
    )
    assert wrong["reveal_after_score_receipt_hash"]["model"] == (
        spike.WRONG_ORBIT_MODEL
    )
    assert wrong["reveal_after_score_receipt_hash"]["state"] == (
        "ORBIT_CODE_CONCORDANT"
    )


def test_code_orbit_discordance_remains_a_negative_control() -> None:
    row = _scenarios()["code_orbit_discordance"]

    assert row["score_receipt"]["orbital_score_state"] == (
        "OPAQUE_HYPOTHESIS_PREFERRED"
    )
    assert row["reveal_after_score_receipt_hash"]["model"] == spike.TARGET_MODEL
    assert row["reveal_after_score_receipt_hash"]["state"] == (
        "ORBIT_CODE_DISCORDANT"
    )


def test_track_order_is_an_explicit_hypothesis_not_posthoc_sign_flip() -> None:
    row = _scenarios()["track_order_reversed"]

    assert row["score_receipt"]["orbital_score_state"] == (
        "OPAQUE_HYPOTHESIS_PREFERRED"
    )
    assert row["reveal_after_score_receipt_hash"]["orientation"] == (
        "TRACK_B_MINUS_TRACK_A"
    )
    assert row["reveal_after_score_receipt_hash"]["state"] == (
        "ORBIT_CODE_CONCORDANT"
    )


def test_midpoint_is_unresolved_and_threshold_is_not_weakened() -> None:
    row = _scenarios()["below_detectability_midpoint"]

    assert row["score_receipt"]["orbital_score_state"] == "AMBIGUOUS"
    assert row["score_receipt"]["preference_margin_m"] < spike.DEVELOPMENT_GUARD_M
    assert row["reveal_after_score_receipt_hash"]["state"] == (
        "ORBIT_ASSIGNMENT_UNRESOLVED"
    )


def test_score_receipt_is_hashed_before_reveal_and_contains_no_identity() -> None:
    for scenario in _receipt()["scenarios"]:
        score = scenario["score_receipt"]
        rendered = blind.strict_json(score)
        assert scenario["score_receipt_sha256_before_reveal"] == (
            blind.receipt_sha256(score)
        )
        assert score["identity_reveal_performed"] is False
        assert score["track_or_observation_values_persisted"] == 0
        for forbidden in ("G22", "G30", "G06", "code_identity"):
            assert forbidden not in rendered


def test_gap_nonfinite_and_changed_surface_are_refused() -> None:
    surface, _, by_model = spike.hypothesis_surface(ROOT)
    target = surface[by_model[spike.TARGET_MODEL]]
    track_a, track_b = spike._synthetic_tracks(target)
    bad = track_a.copy()
    bad[80] = np.nan
    with pytest.raises(blind.AnonymousTrackScorerError, match="GAP_OR_NONFINITE"):
        blind.score_anonymous_pair(
            bad,
            track_b,
            surface,
            pairwise_guard_m=spike.DEVELOPMENT_GUARD_M,
        )
    reduced = dict(surface)
    reduced.pop(next(iter(reduced)))
    with pytest.raises(
        blind.AnonymousTrackScorerError, match="OPAQUE_HYPOTHESIS_COUNT_CHANGED"
    ):
        blind.score_anonymous_pair(
            track_a,
            track_b,
            reduced,
            pairwise_guard_m=spike.DEVELOPMENT_GUARD_M,
        )


def test_real_capability_terms_remain_open_and_never_become_zero() -> None:
    receipt = _receipt()
    boundary = receipt["derived_detectability_boundary"]
    states = {row["term"]: row["state"] for row in receipt["real_capability_terms"]}

    assert receipt["real_capability_admission"] == "NOT_EVALUATED_OPEN_TERMS"
    assert boundary["exact_fixture_preference_margin_m"] > (
        boundary["development_guard_m"]
    )
    assert boundary["remaining_synthetic_margin_m"] > 0.0
    assert states["sample_zero_event_time_and_sample_rate"] == "OPEN_TERM"
    assert states["differential_nonaffine_oscillator"] == "OPEN_TERM"
    assert states["ionosphere_and_propagation"] == "OPEN_TERM"
    assert all(row["state"] != 0 for row in receipt["real_capability_terms"])


def test_development_guard_cannot_exceed_exact_fixture_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(spike, "DEVELOPMENT_GUARD_M", 1.0e12)

    with pytest.raises(
        spike.AnonymousTrackSpikeError,
        match="DEVELOPMENT_GUARD_NOT_BELOW_EXACT_FIXTURE_MARGIN",
    ):
        spike.build_receipt(ROOT)


def test_receipt_is_deterministic_strict_and_observation_blind() -> None:
    first = _receipt()
    second = _receipt()
    rendered = spike.strict_json(first)

    assert first == second
    assert first["outcome"] == (
        "ANONYMOUS_TRACK_SEALED_WITNESS_MECHANISM_DISCRIMINATIVE"
    )
    assert first["closed_development_fixture"]["observation_values_used"] == 0
    assert first["closed_development_fixture"][
        "consumed_primary_reopened_or_rescored"
    ] is False
    assert all(value == 0 for value in first["observation_access"].values())
    assert "NaN" not in rendered and "Infinity" not in rendered
    assert json.loads(rendered) == first
