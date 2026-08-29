"""Tests for the pure identity-blind held-out scorer."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_opaque_orbit_scorer as scorer
from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_scorer_seal as seal,
)


ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = ROOT / scorer.BUNDLE_NAME


def _bundle() -> dict[str, object]:
    return scorer.load_exact_bundle(BUNDLE_PATH)


def _elapsed() -> np.ndarray:
    return np.arange(scorer.RAW_EPOCHS, dtype=np.float64) * scorer.STEP_S


def test_exact_bundle_is_the_only_accepted_model_surface() -> None:
    value = _bundle()

    assert scorer.canonical_sha256(BUNDLE_PATH) == scorer.BUNDLE_CANONICAL_SHA256
    assert scorer.bundle_manifest_sha256(value) == scorer.BUNDLE_MANIFEST_SHA256
    curves = scorer.validate_bundle(value)
    assert set(curves) == set(value["opaque_ids"])
    assert len(curves) == 6
    assert all(curve.shape == (139,) for curve in curves.values())


def test_scorer_source_has_no_identity_or_orbital_compiler_surface() -> None:
    source = Path(scorer.__file__).read_text(encoding="utf-8").lower()

    for forbidden in (
        "from experiments",
        "import requests",
        "import urllib",
        "import socket",
        "g22",
        "g30",
        "satellite",
        "mapping_seal",
        "gnss_blind_orbit_assignment_plan",
        "decode_observation",
    ):
        assert forbidden not in source


def test_exact_opaque_curve_is_preferred_after_same_prefix_fit() -> None:
    bundle = _bundle()
    identifier = "H_72E7F21DC8244653"
    observed = np.asarray(bundle["curves_m"][identifier], dtype=np.float64)
    observed = observed + 123.0 + 0.01 * _elapsed()

    receipt = scorer.score(observed, bundle)

    assert receipt["opaque_outcome"] == "OPAQUE_HYPOTHESIS_PREFERRED"
    assert receipt["best_opaque_id"] == identifier
    assert receipt["preference_margin_m"] == pytest.approx(
        18_763.71656478895, abs=1.0e-6
    )
    assert all(row["fitted_parameter_count"] == 2 for row in receipt["scores"])
    assert receipt["heldout_refit"] is False
    assert receipt["free_time_phase"] is False


def test_midpoint_between_controlling_curves_is_ambiguous() -> None:
    bundle = _bundle()
    left = np.asarray(
        bundle["curves_m"]["H_72E7F21DC8244653"], dtype=np.float64
    )
    right = np.asarray(
        bundle["curves_m"]["H_0F7B423DEE4445EB"], dtype=np.float64
    )
    observed = 0.5 * (left + right) + 12.0 - 0.005 * _elapsed()

    receipt = scorer.score(observed, bundle)

    assert receipt["opaque_outcome"] == "AMBIGUOUS"
    assert {receipt["best_opaque_id"], receipt["runner_up_opaque_id"]} == {
        "H_72E7F21DC8244653",
        "H_0F7B423DEE4445EB",
    }
    assert receipt["preference_margin_m"] == pytest.approx(0.0, abs=1.0e-8)


def test_tampered_curve_or_threshold_is_refused_before_scoring() -> None:
    bundle = _bundle()
    tampered_curve = deepcopy(bundle)
    tampered_curve["curves_m"][tampered_curve["opaque_ids"][0]][0] += 1.0
    with pytest.raises(
        scorer.OpaqueOrbitScorerError, match="BUNDLE_MANIFEST_HASH_CHANGED"
    ):
        scorer.validate_bundle(tampered_curve)

    tampered_guard = deepcopy(bundle)
    tampered_guard["scoring"]["pairwise_guard_m"] = 0.0
    with pytest.raises(
        scorer.OpaqueOrbitScorerError, match="BUNDLE_MANIFEST_HASH_CHANGED"
    ):
        scorer.validate_bundle(tampered_guard)


def test_invalid_observed_coordinate_is_refused() -> None:
    bundle = _bundle()

    with pytest.raises(
        scorer.OpaqueOrbitScorerError,
        match="OBSERVED_COORDINATE_SHAPE_INVALID",
    ):
        scorer.score([0.0] * 138, bundle)
    bad = [0.0] * 139
    bad[10] = float("nan")
    with pytest.raises(
        scorer.OpaqueOrbitScorerError,
        match="OBSERVED_COORDINATE_NONFINITE",
    ):
        scorer.score(bad, bundle)


def test_score_receipt_hash_precedes_any_identity_reveal_and_persists_no_values() -> None:
    bundle = _bundle()
    observed = np.asarray(
        bundle["curves_m"]["H_72E7F21DC8244653"], dtype=np.float64
    )
    receipt = scorer.score(observed, bundle)
    rendered = scorer.strict_json(receipt)
    digest = scorer.score_receipt_sha256(receipt)

    assert len(digest) == 64
    assert receipt["identity_reveal_performed"] is False
    assert receipt["observed_values_persisted"] == 0
    assert "curves_m" not in rendered
    assert "observed_m" not in rendered
    assert "NaN" not in rendered and "Infinity" not in rendered
    assert json.loads(rendered) == receipt


def test_seal_manifest_binds_exact_bundle_and_is_still_preprimary() -> None:
    manifest = seal.scorer_manifest(ROOT)

    assert manifest["prediction_bundle"] == {
        "filename": scorer.BUNDLE_NAME,
        "canonical_bytes": 20_849,
        "canonical_sha256": scorer.BUNDLE_CANONICAL_SHA256,
        "manifest_sha256": scorer.BUNDLE_MANIFEST_SHA256,
        "curve_set_sha256": seal.CURVE_SET_SHA256,
        "opaque_hypotheses": 6,
        "named_hypotheses": 0,
    }
    assert manifest["scorer"]["unexpected_import_roots"] == []
    assert manifest["scorer"]["named_hypothesis_tokens"] == 0
    assert manifest["receipt_order"] == {
        "score_receipt_contains_only_opaque_ids": True,
        "score_receipt_hash_before_identity_reveal": True,
        "identity_reveal_inside_scorer": False,
    }
    assert manifest["authority"] == {
        "primary_access": False,
        "primary_materialization": False,
        "observation_decode": False,
        "measurement_score": False,
        "executor": False,
        "separate_review_required": True,
    }
    assert manifest["synthetic_tests_only"] is True


def test_seal_manifest_is_deterministic_and_cli_summary_is_minimal() -> None:
    first = seal.scorer_manifest_sha256(ROOT)
    second = seal.scorer_manifest_sha256(ROOT)
    summary = seal.cli_summary(seal.scorer_manifest(ROOT))

    assert len(first) == 64
    assert first == second
    assert summary == {
        "state": "SCORER_MANIFEST_VALID",
        "scorer_manifest_sha256": "NOT_WRITTEN",
        "primary_access": {
            "locators_queried": 0,
            "headers_opened": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "orbital_scores_from_measurement": 0,
    }
