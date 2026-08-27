from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_predictions as predictions,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_primary_plan as plan,
)


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / predictions.PREDICTIONS_NAME
SEAL = ROOT / predictions.SEAL_NAME


def test_compiler_is_exact_navigation_only_and_observation_blind() -> None:
    manifest = predictions.compiler_manifest()

    assert manifest["station_roots"] == [
        "ALGO00CAN_40104M002",
        "MDO100USA_40442M012",
    ]
    assert manifest["navigation"] == predictions.navigation_authority()
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
    assert "PRIMARY_LOCATOR_HEADER_PAYLOAD_OR_VALUE_ACCESS" in manifest[
        "forbidden"
    ]


def test_prediction_grid_hypotheses_and_scoring_are_exact() -> None:
    manifest = predictions.compiler_manifest()

    assert manifest["grid"]["raw_start_gps"] == (
        "2026-08-11T05:24:00.000000Z"
    )
    assert manifest["grid"]["raw_stop_gps"] == (
        "2026-08-11T06:33:00.000000Z"
    )
    assert manifest["grid"]["heldout_feature_indices_inclusive"] == [77, 136]
    assert manifest["hypotheses"] == {
        "ORBITAL_G22": "G22",
        "PREFIX_AFFINE": None,
        "WRONG_ORBIT_G01": "G01",
        "WRONG_ORBIT_G14": "G14",
        "WRONG_ORBIT_G17": "G17",
    }
    assert manifest["scoring"]["pairwise_decision_guard_m"] == pytest.approx(
        3_142.1641485601226
    )


def test_strict_json_refuses_nonfinite_values() -> None:
    assert json.loads(predictions.strict_json({"finite": 1.25})) == {
        "finite": 1.25
    }
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("inf")})


def test_navigation_hash_boundary_rejects_arbitrary_bytes() -> None:
    with pytest.raises(
        predictions.Doy223PredictionError,
        match="NAVIGATION_GZIP_SIZE_CHANGED",
    ):
        predictions.build_predictions_from_gzip(b"not the frozen navigation")


def test_manifest_is_bound_to_primary_plan_and_no_access_authority() -> None:
    manifest = predictions.compiler_manifest()

    assert manifest["plan_manifest_sha256"] == plan.manifest_sha256()
    assert plan.manifest_sha256() == (
        "2e7598068db8dd5c4fe27ee881340bb7096b8e878fda0a050048a11a70767055"
    )
    assert len(predictions.compiler_manifest_sha256()) == 64
    assert plan.plan()["access_at_freeze"] == {
        "observation_locator_requests": 0,
        "descriptive_head_requests": 0,
        "observation_headers_opened": 0,
        "observation_payload_bytes": 0,
        "observation_values": 0,
    }


def test_frozen_prediction_reproduces_doy223_screen_regressions() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    curves = predictions.validate_predictions(value)

    assert value["compiler_source_commit"] == (
        "6647fe3aa6e37f514dc399449a9f88354a3b8464"
    )
    assert value["compiler_source_sha256"] == (
        "0c05d4f5a0464e11fc6d79827adfb33a0f673c8d0be788800205077bafe3ef1e"
    )
    assert value["compiler_manifest_sha256"] == (
        "e15ace782755708541b21fa61dc31c25989880c965ce16e8932a4539d417591c"
    )
    assert value["curve_set_sha256"] == (
        "6ded9e22e1a32ce2fd4c24f9834a04fcd818f719d1f84465bef8f04c1b82323f"
    )
    assert set(curves) == set(predictions.HYPOTHESES)
    assert all(curve.shape == (137,) for curve in curves.values())
    assert value["minimum_model_elevation_deg"] == pytest.approx(
        22.66366007669533
    )
    regression = value["numerical_regression"]
    assert regression["controlling_null"] == "WRONG_ORBIT_G14"
    assert regression["controlling_heldout_separation_m"] == pytest.approx(
        54_990.701676848694
    )
    assert regression["pairwise_decision_guard_m"] == pytest.approx(
        3_142.1641485601226
    )
    assert regression["remaining_physical_margin_m"] == pytest.approx(
        51_848.53752828857
    )
    assert predictions.canonical_sha256(PREDICTIONS) == (
        "c45df3e1ca2a18bf52bd7f33e31fceaf6c15a9e83d83d1078c3f092c81cbf15b"
    )


def test_prediction_curve_tampering_is_refused() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    tampered = deepcopy(value)
    tampered["curves_m"]["ORBITAL_G22"][0] += 1.0

    with pytest.raises(
        predictions.Doy223PredictionError,
        match="PREDICTION_CURVE_HASH_CHANGED",
    ):
        predictions.validate_predictions(tampered)


def test_seal_grants_no_primary_access_authority() -> None:
    seal = json.loads(SEAL.read_text(encoding="utf-8"))

    assert predictions.canonical_sha256(SEAL) == (
        "4e94711d88a9c85c232585db83a3b7192713ba0b4900606076e8c386373c57fa"
    )
    assert seal["state"] == "PRIMARY_PLAN_AND_PREDICTION_FROZEN"
    assert seal["authority"] == {
        "primary_access_authorized_by_seal": False,
        "separate_review_required": True,
    }
    assert seal["access_at_seal"] == {
        "observation_locator_requests": 0,
        "descriptive_head_requests": 0,
        "observation_headers_opened": 0,
        "observation_payload_bytes": 0,
        "observation_values": 0,
    }
    assert seal["stop"] == (
        "STOP_BEFORE_ANY_PRIMARY_OBSERVATION_REQUEST_FOR_REVIEW"
    )
