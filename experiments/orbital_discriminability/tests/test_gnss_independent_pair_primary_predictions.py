from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_plan as plan,
)
from experiments.orbital_discriminability import (
    gnss_independent_pair_primary_predictions as predictions,
)


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / predictions.PREDICTIONS_NAME
SEAL = ROOT / predictions.SEAL_NAME


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
    assert plan.manifest_sha256() == (
        "4bae4d9aa655579263de00e84b6d374a8263b8196122ef024bd39ccfdd804756"
    )
    assert len(predictions.compiler_manifest_sha256()) == 64


def test_frozen_prediction_artifact_reproduces_the_screen_regression() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    curves = predictions.validate_predictions(value)

    assert value["compiler_source_commit"] == (
        "24dd303dcb5395bf158f4e8fed025e4b54ff4609"
    )
    assert value["compiler_source_sha256"] == (
        "922a974a8670812a949b61d2bd4573d93ba5ba003733948e23edd4ae367bef12"
    )
    assert value["compiler_manifest_sha256"] == (
        "ace14f2c6809a11dccc843398a3d4e9a96be67dae0b779a68146cef2739db17c"
    )
    assert value["curve_set_sha256"] == (
        "cdccb4fcef936c9256b11893b4f9af9b9c5c95400d70cfb4649e576ffe9a5ce1"
    )
    assert set(curves) == set(predictions.HYPOTHESES)
    assert all(curve.shape == (137,) for curve in curves.values())
    regression = value["numerical_regression"]
    assert regression["controlling_null"] == "WRONG_ORBIT_G14"
    assert regression["controlling_heldout_separation_m"] == pytest.approx(
        51_370.2989916536
    )
    assert regression["pairwise_decision_guard_m"] == pytest.approx(
        3_542.2570672266515
    )
    assert regression["remaining_physical_margin_m"] == pytest.approx(
        47_828.04192442695
    )
    assert predictions.canonical_sha256(PREDICTIONS) == (
        "f88b7a9185203fea00a4587335b2018172c5a894409bb5cb13d481d3e9996c0c"
    )


def test_prediction_curve_tampering_is_refused() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    tampered = deepcopy(value)
    tampered["curves_m"]["ORBITAL_G22"][0] += 1.0

    with pytest.raises(
        predictions.IndependentPairPredictionError,
        match="PREDICTION_CURVE_HASH_CHANGED",
    ):
        predictions.validate_predictions(tampered)


def test_seal_grants_no_primary_authority() -> None:
    seal = json.loads(SEAL.read_text(encoding="utf-8"))

    assert predictions.canonical_sha256(SEAL) == (
        "f8585632bc5f5ea6f3f94441fae35d58b53ab181bcbeeda32c3daf8747e07793"
    )
    assert seal["state"] == "PRIMARY_PLAN_AND_PREDICTION_FROZEN"
    assert seal["authority"] == {
        "primary_access_authorized_by_seal": False,
        "separate_review_required": True,
    }
    assert seal["access_at_seal"] == {
        "descriptive_head_requests": 2,
        "observation_headers_opened": 0,
        "observation_payload_bytes": 0,
        "observation_values": 0,
    }
