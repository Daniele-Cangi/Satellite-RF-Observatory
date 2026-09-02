"""Tests for the bounded six-track orbit-only geometry screen."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_all_track_geometry_screen as screen


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / screen.RECEIPT_NAME


def _curves(scale: float = 1.0) -> dict[str, np.ndarray]:
    elapsed = np.arange(screen.RAW_EPOCHS, dtype=np.float64) * screen.STEP_S
    centered = elapsed - float(np.mean(elapsed[: screen.PREFIX_EPOCHS]))
    return {
        f"G{index + 1:02d}": (
            scale * (index + 1) * 0.001 * centered**2
            + scale * (index + 1) ** 2 * 1.0e-7 * centered**3
        )
        for index in range(screen.TRACK_COUNT)
    }


def test_manifest_is_scope_bound_and_has_no_observation_surface() -> None:
    value = screen.manifest(ROOT)
    assert value["scope"]["scope_commit"] == screen.SCOPE_COMMIT
    assert value["visibility"]["exact_complete_track_count"] == 6
    assert value["hypotheses"]["bijective_orbit_assignments"] == 720
    assert value["decision_envelope"]["required_exact_separation_m"] == pytest.approx(
        3.0 * screen.PAIRWISE_GUARD_M
    )
    assert set(value["observation_boundary"].values()) == {0}
    assert value["primary_selected"] is False


def test_closest_wrong_bijection_equals_closest_pair_swap() -> None:
    curves = _curves(scale=10.0)
    evaluated = screen.evaluate_codebook(curves)
    exhaustive = screen.exhaustive_nonidentity_separation(curves)
    assert evaluated["nearest_wrong_assignment"][
        "heldout_peak_to_peak_m"
    ] == pytest.approx(exhaustive, rel=1e-12, abs=1e-8)


def test_affine_null_and_assignment_receive_same_prefix_projection() -> None:
    value = screen.evaluate_codebook(_curves(scale=100.0))
    assert value["bijective_assignment_count"] == 720
    assert value["total_hypothesis_count"] == 721
    assert value["controlling_runner_class"] in {
        "PREFIX_AFFINE_ONLY_NULL",
        "CLOSEST_NONIDENTITY_BIJECTION",
    }
    expected = (
        value["exact_controlling_separation_m"]
        - 3.0 * screen.PAIRWISE_GUARD_M
    )
    assert value["robust_scorer_margin_lower_bound_m"] == pytest.approx(expected)


def test_three_guard_boundary_is_strict() -> None:
    original = _curves(scale=1.0)
    base = screen.evaluate_codebook(original)["exact_controlling_separation_m"]
    boundary = screen.REQUIRED_EXACT_SEPARATION_M / base
    at_boundary = screen.evaluate_codebook(_curves(scale=boundary))
    below = screen.evaluate_codebook(_curves(scale=boundary * 0.999999))
    above = screen.evaluate_codebook(_curves(scale=boundary * 1.000001))
    assert at_boundary["robust_scorer_margin_lower_bound_m"] == pytest.approx(
        0.0, abs=1e-6
    )
    assert below["robustly_discriminative"] is False
    assert above["robustly_discriminative"] is True


def test_seventh_track_is_not_silently_subset_selected() -> None:
    curves = _curves()
    curves["G07"] = np.arange(screen.RAW_EPOCHS, dtype=np.float64) ** 2
    with pytest.raises(
        screen.AllTrackGeometryScreenError,
        match="CODEBOOK_MUST_HAVE_EXACTLY_SIX_TRACKS",
    ):
        screen.evaluate_codebook(curves)


@pytest.mark.parametrize(
    ("exact_count", "robust_count", "expected"),
    [
        (0, 0, screen.OUTCOME_NO_INCLUSION),
        (5, 0, screen.OUTCOME_NO_GEOMETRY),
        (5, 1, screen.OUTCOME_SHORTLISTED),
    ],
)
def test_outcome_semantics(
    exact_count: int, robust_count: int, expected: str
) -> None:
    assert screen.classify_outcome(exact_count, robust_count) == expected


def test_source_has_no_observation_or_network_input() -> None:
    parameters = inspect.signature(screen.compile_screen).parameters
    assert list(parameters) == ["payloads", "root"]
    source = Path(screen.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "import requests",
        "import urllib",
        "observation-gzip",
        "rinex observation",
        "phase_values",
        "primary_product",
    ):
        assert forbidden not in source


def test_committed_receipt_is_strict_and_zero_observation_if_present() -> None:
    if not RECEIPT.exists():
        pytest.skip("receipt is created only after the compiler commit")
    value = json.loads(RECEIPT.read_text(encoding="ascii"))
    assert value["source_sha256"] == screen.source_sha256()
    assert set(value["observation_access"].values()) == {0}
    assert value["navigation_payloads_retained"] == 0
    assert value["primary_selected"] is False
    encoded = screen.strict_json(value)
    assert "NaN" not in encoded and "Infinity" not in encoded
