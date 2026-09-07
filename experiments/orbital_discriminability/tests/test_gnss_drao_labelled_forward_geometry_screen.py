"""Tests for the bounded DRAO labelled-forward orbit-only screen."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_geometry_screen as screen,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / screen.RECEIPT_NAME


def _curves(scale: float = 1.0) -> dict[str, np.ndarray]:
    elapsed = np.arange(screen.RAW_EPOCHS, dtype=np.float64) * screen.STEP_S
    centered = elapsed - float(np.mean(elapsed[: screen.PREFIX_EPOCHS]))
    return {
        f"G{index + 1:02d}": scale
        * (
            (index + 1) * 0.001 * centered**2
            + (index + 1) ** 2 * 1.0e-7 * centered**3
        )
        for index in range(screen.TRACK_COUNT)
    }


def _shifted(curves: dict[str, np.ndarray]) -> dict[tuple[str, float], np.ndarray]:
    return {
        (code, offset): values.copy()
        for code, values in curves.items()
        for offset in (-screen.MAXIMUM_EVENT_TIME_ERROR_S, screen.MAXIMUM_EVENT_TIME_ERROR_S)
    }


def test_manifest_is_bounded_and_has_zero_observation_surface() -> None:
    value = screen.manifest(ROOT)
    assert value["station"]["station_id"] == "DRAO00CAN"
    assert [row["doy"] for row in value["navigation"]] == list(range(234, 239))
    assert value["visibility"]["minimum_joint_track_count"] == 6
    assert value["visibility"]["extra_tracks"] == "DESCRIPTIVE_NOT_FATAL_NOT_SCORED"
    assert value["nulls"] == ["PREFIX_AFFINE_ONLY", "TIME_REVERSED_GEOMETRY"]
    assert set(value["observation_boundary"].values()) == {0}
    assert value["identity_independently_established"] is False


def test_affine_tracks_do_not_create_an_orbital_margin() -> None:
    elapsed = np.arange(screen.RAW_EPOCHS, dtype=np.float64)
    curves = {
        f"G{index + 1:02d}": 100.0 * index + (index + 1) * elapsed
        for index in range(screen.TRACK_COUNT)
    }
    value = screen.evaluate_codebook(curves, _shifted(curves))
    assert value["exact_controlling_separation_m"] == pytest.approx(0.0, abs=1e-8)
    assert value["robustly_discriminative"] is False


def test_curved_tracks_are_compared_to_both_frozen_nulls() -> None:
    curves = _curves(scale=100.0)
    value = screen.evaluate_codebook(curves, _shifted(curves))
    assert value["prefix_affine_null"]["heldout_max_track_peak_to_peak_m"] > 0.0
    assert value["time_reversed_geometry_null"]["heldout_max_track_peak_to_peak_m"] > 0.0
    assert value["controlling_null"] in {
        "PREFIX_AFFINE_ONLY",
        "TIME_REVERSED_GEOMETRY",
    }
    assert value["direct_time_shift_envelope_m"] == pytest.approx(0.0, abs=1e-8)
    assert value["robust_margin_lower_bound_m"] == pytest.approx(
        value["exact_controlling_separation_m"]
        - 3.0 * screen.HISTORICAL_DRAO_GUARD_M
    )


def test_direct_time_shift_can_refuse_an_otherwise_positive_cell() -> None:
    curves = _curves(scale=100.0)
    shifted = _shifted(curves)
    elapsed = np.arange(screen.RAW_EPOCHS, dtype=np.float64)
    nonlinear = 100.0 * screen.HISTORICAL_DRAO_GUARD_M * (elapsed / elapsed[-1]) ** 2
    shifted[("G01", screen.MAXIMUM_EVENT_TIME_ERROR_S)] += nonlinear
    value = screen.evaluate_codebook(curves, shifted)
    assert value["direct_time_shift_envelope_m"] > screen.HISTORICAL_DRAO_GUARD_M
    assert value["robustly_discriminative"] is False


def test_codebook_is_six_but_total_visible_cardinality_is_not_frozen() -> None:
    value = screen.manifest(ROOT)
    assert value["selection"]["every_six_of_visible"] is True
    source = Path(screen.__file__).read_text(encoding="utf-8")
    assert "counts == TRACK_COUNT" not in source
    assert "len(visible_indices) < TRACK_COUNT" in source


def test_source_accepts_only_navigation_payloads() -> None:
    assert list(inspect.signature(screen.compile_screen).parameters) == [
        "payloads",
        "root",
    ]
    source = Path(screen.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "import requests",
        "import urllib",
        "observation-gzip",
        "hatanaka",
        "primary_product",
        "phase_values",
    ):
        assert forbidden not in source


def test_scope_hash_and_strict_json() -> None:
    assert screen.canonical_sha256(ROOT / screen.SCOPE_NAME) == screen.SCOPE_SHA256
    encoded = screen.strict_json(screen.manifest(ROOT))
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_committed_receipt_is_zero_observation_if_present() -> None:
    if not RECEIPT.exists():
        pytest.skip("receipt is created only after the frozen compiler runs")
    value = json.loads(RECEIPT.read_text(encoding="ascii"))
    assert value["source_sha256"] == screen.source_sha256()
    assert set(value["observation_access"].values()) == {0}
    assert value["navigation_payloads_retained"] == 0
    assert value["primary_selected"] is False
