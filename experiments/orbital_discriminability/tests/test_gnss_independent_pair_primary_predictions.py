from __future__ import annotations

import json

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_plan as plan,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_predictions as predictions,
)


def test_compiler_surface_is_navigation_only_and_observation_blind() -> None:
    manifest = predictions.compiler_manifest()

    assert manifest["station_roots"] == [
        "ALGO00CAN_40104M002",
        "MDO100USA_40442M012",
    ]
    assert manifest["navigation_input"]["network_capability"] is False
    assert manifest["observation_boundary"] == {
        "head_metadata_in_plan": 2,
        "headers_opened": 0,
        "payload_bytes": 0,
        "values_accessed": 0,
        "network_capability": False,
        "observation_decoder_present": False,
    }
    assert "PRIMARY_HEADER_PAYLOAD_OR_VALUE_ACCESS" in manifest["forbidden"]


def test_prediction_grid_and_hypotheses_are_exact() -> None:
    manifest = predictions.compiler_manifest()

    assert manifest["grid"]["raw_start_gps"] == (
        "2026-08-07T05:46:00.000000Z"
    )
    assert manifest["grid"]["raw_stop_gps"] == (
        "2026-08-07T06:55:00.000000Z"
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
        3_542.2570672266515
    )


def test_strict_json_refuses_nonfinite_values() -> None:
    assert json.loads(predictions.strict_json({"finite": 1.25})) == {
        "finite": 1.25
    }
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("inf")})


def test_navigation_hash_boundary_rejects_arbitrary_bytes() -> None:
    with pytest.raises(Exception) as exc:
        predictions.build_predictions_from_gzip(b"not the frozen navigation")
    assert "GZIP_SIZE_CHANGED" in str(exc.value)


def test_manifest_is_bound_to_primary_plan() -> None:
    manifest = predictions.compiler_manifest()

    assert manifest["plan_manifest_sha256"] == plan.manifest_sha256()
    assert len(predictions.compiler_manifest_sha256()) == 64
