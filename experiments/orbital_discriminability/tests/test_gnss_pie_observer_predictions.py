from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_pie_observer_predictions as predictions,
)


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / predictions.PREDICTIONS_NAME
SEAL = ROOT / predictions.SEAL_NAME


def test_manifest_is_exact_navigation_only_and_observation_blind() -> None:
    manifest = predictions.compiler_manifest(ROOT)

    assert manifest["plan_manifest_sha256"] == (
        "5fef155739849280fced56a5967460df7be0b6e9ae1522aadbc61b6d667a6867"
    )
    assert manifest["observer_root"] == "PIE100USA_40456M001"
    assert manifest["navigation"]["compressed_sha256"] == (
        "deaea8679fc2fd816d0d127ae11a7c83f3956cdf51b969e99bddb0f381437478"
    )
    assert manifest["navigation_input"]["network_capability"] is False
    assert manifest["observation_boundary"] == {
        "locator_requests": 0,
        "descriptive_head_requests": 0,
        "headers_opened": 0,
        "payload_bytes": 0,
        "values_accessed": 0,
        "network_capability": False,
        "observation_decoder_present": False,
    }


def test_grid_hypotheses_timing_and_scoring_are_frozen() -> None:
    manifest = predictions.compiler_manifest(ROOT)

    assert manifest["grid"] == {
        "time_system": "GPS",
        "raw_start_gps": "2026-08-11T05:42:00 GPS",
        "raw_stop_gps": "2026-08-11T06:51:00 GPS",
        "step_s": 30.0,
        "raw_epochs": 139,
        "anchor_index": 0,
        "witness_prefix_raw_indices_inclusive": [0, 78],
        "heldout_raw_indices_inclusive": [79, 138],
    }
    assert manifest["hypotheses"] == predictions.HYPOTHESES
    assert manifest["timing_envelope"]["offsets_s"] == [-15.0, 15.0]
    assert manifest["scoring"]["nuisance_fit_parameters"] == 0


def test_plan_receipt_and_live_manifest_are_exact() -> None:
    authority = predictions.verify_plan(ROOT)

    assert authority["canonical_sha256"] == predictions.PLAN_RECEIPT_SHA256
    assert authority["manifest_sha256"] == (
        "5fef155739849280fced56a5967460df7be0b6e9ae1522aadbc61b6d667a6867"
    )
    assert authority["outcome"] == "PIE_OBSERVER_PRIMARY_PLAN_FROZEN"


def test_strict_json_and_navigation_hash_boundary_refuse_invalid_input() -> None:
    assert json.loads(predictions.strict_json({"finite": 1.25})) == {"finite": 1.25}
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("inf")})
    with pytest.raises(
        predictions.PiePredictionError,
        match="NAVIGATION_GZIP_SIZE_CHANGED",
    ):
        predictions.build_predictions_from_gzip(b"not navigation", ROOT)


def test_frozen_prediction_reproduces_pie_geometry() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    curves = predictions.validate_predictions(value, ROOT)

    assert value["compiler_source_commit"] == (
        "db0ff58c092f48cb5cea09bffd494b7a639be848"
    )
    assert value["compiler_source_sha256"] == (
        "b1cecd12f2a72fad4526d824713f7f1a716f6e0b69bc8e40f4370a05ab5b382e"
    )
    assert value["compiler_manifest_sha256"] == (
        "59bd0270787d61de1bcb73200f20ba93521fa9a1f366c567914899151c1dc5c0"
    )
    assert value["curve_set_sha256"] == (
        "acdf11390aa6ce4d7506fc733d53f968ac0cdfb977b99ef43dfe388d77d39586"
    )
    assert value["timing_curve_set_sha256"] == (
        "048315df7a536a7e71fce6e0f0fbdd54e8a1ce60d1b2bc7d0cefdc8d9421dff8"
    )
    assert predictions.canonical_sha256(PREDICTIONS) == (
        "a86a360fcbf9e1aa05e112bae1e2d1158b729f6e2fe9b4418a89883c72aacbc9"
    )
    assert set(curves) == set(predictions.HYPOTHESES)
    assert all(curve.shape == (139,) for curve in curves.values())
    regression = value["numerical_regression"]
    assert regression["controlling_null"] == "FROZEN_AFFINE_NULL"
    assert regression["controlling_heldout_separation_m"] == pytest.approx(
        190_232.34133512143
    )
    assert regression["direct_timing_envelope_m"] == pytest.approx(1_418.1455840170383)
    assert regression["pairwise_decision_guard_m"] == pytest.approx(7_899.820878397492)
    assert regression["remaining_physical_margin_m"] == pytest.approx(
        182_332.52045672393
    )
    assert value["minimum_time_shifted_model_elevation_deg"] == pytest.approx(
        17.801627769079243
    )
    assert value["orbital_scores_produced"] == 0


def test_prediction_curve_tampering_is_refused() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    tampered = deepcopy(value)
    tampered["curves_m"]["ORBITAL_G22"][0] += 1.0

    with pytest.raises(
        predictions.PiePredictionError,
        match="PREDICTION_CURVE_HASH_CHANGED",
    ):
        predictions.validate_predictions(tampered, ROOT)


def test_direct_timing_curve_tampering_is_refused() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    tampered = deepcopy(value)
    first = next(iter(tampered["direct_timing_envelope_curves_m"].values()))
    first[0] += 1.0

    with pytest.raises(
        predictions.PiePredictionError,
        match="PREDICTION_TIMING_HASH_CHANGED",
    ):
        predictions.validate_predictions(tampered, ROOT)


def test_seal_grants_no_observation_or_executor_authority() -> None:
    seal = json.loads(SEAL.read_text(encoding="utf-8"))

    assert predictions.canonical_sha256(SEAL) == (
        "446b65682cf9bfe7eac5d4fe63a1c709dc0ebaf9f75a681214f925b0f111e4e9"
    )
    assert seal["state"] == "PIE_OBSERVER_PRIMARY_PREDICTION_FROZEN"
    assert seal["authority"] == {
        "primary_access_authorized_by_seal": False,
        "executor_authorized_by_seal": False,
        "separate_review_required": True,
    }
    assert seal["primary"]["headers_opened"] == 0
    assert seal["primary"]["payload_bytes"] == 0
    assert seal["primary"]["observation_values"] == 0
    assert seal["orbital_scores_produced"] == 0
    assert seal["stop"] == (
        "STOP_BEFORE_EXECUTOR_OR_PRIMARY_OBSERVATION_ACCESS_FOR_REVIEW"
    )


def test_no_nonfinite_values_reach_frozen_artifacts() -> None:
    predictions_value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    seal_value = json.loads(SEAL.read_text(encoding="utf-8"))

    assert "NaN" not in predictions.strict_json(predictions_value)
    assert "Infinity" not in predictions.strict_json(predictions_value)
    assert np.isfinite(
        predictions_value["numerical_regression"]["remaining_physical_margin_m"]
    )
    assert json.loads(predictions.strict_json(seal_value)) == seal_value
