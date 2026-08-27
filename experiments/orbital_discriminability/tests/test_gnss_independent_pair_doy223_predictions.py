from __future__ import annotations

import json

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_predictions as predictions,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_doy223_primary_plan as plan,
)


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
