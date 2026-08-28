from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_amc_observer_predictions as predictions,
)


ROOT = Path(__file__).resolve().parents[1]
PREDICTIONS = ROOT / predictions.PREDICTIONS_NAME
SEAL = ROOT / predictions.SEAL_NAME


def test_manifest_is_exact_navigation_only_and_observation_blind() -> None:
    manifest = predictions.compiler_manifest(ROOT)

    assert manifest["plan_manifest_sha256"] == (
        "0a3c1e3768566da6242d6aaffd6c751a23d6bf167c7f54d0498fe75f365609b0"
    )
    assert manifest["observer_root"] == "AMC400USA_40472S005"
    assert manifest["navigation"] == {
        "doy": 221,
        "gps_date": "2026-08-09",
        "name": "brdc2210.26n.gz",
        "provider": "NOAA_NGS_DAILY_GLOBAL_NAVIGATION_FILE",
        "rinex_version": "2.11",
        "url": "https://geodesy.noaa.gov/corsdata/rinex/2026/221/brdc2210.26n.gz",
        "compressed_bytes": 71_457,
        "compressed_sha256": (
            "ac512aaaa875a9807c152785427f0e40316710fad1d72d5d6c584389c997963e"
        ),
        "uncompressed_bytes": 294_875,
        "uncompressed_sha256": (
            "762c18808dac8cc85b252ce6efe05a2ca87caefb8ebf286e9aabbb475470b771"
        ),
        "uncompressed_name": "brdc2210.26n",
        "semantics": "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION",
    }
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
        "raw_start_gps": "2026-08-09T05:41:30 GPS",
        "raw_stop_gps": "2026-08-09T06:50:30 GPS",
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

    assert authority["canonical_sha256"] == (
        "615cce5046e218f583483175c8774357680d80450d5b97928685f728fb2fb89b"
    )
    assert authority["manifest_sha256"] == (
        "0a3c1e3768566da6242d6aaffd6c751a23d6bf167c7f54d0498fe75f365609b0"
    )
    assert authority["outcome"] == "AMC_OBSERVER_PRIMARY_PLAN_FROZEN"


def test_strict_json_and_navigation_hash_boundary_refuse_invalid_input() -> None:
    assert json.loads(predictions.strict_json({"finite": 1.25})) == {"finite": 1.25}
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("inf")})
    with pytest.raises(
        predictions.AmcPredictionError,
        match="NAVIGATION_GZIP_SIZE_CHANGED",
    ):
        predictions.build_predictions_from_gzip(b"not navigation", ROOT)


def test_compiler_exposes_no_observation_transport_decoder_or_score_surface() -> None:
    source = Path(predictions.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "import hatanaka",
        "observation_values_m",
        "score_observation",
    ):
        assert forbidden not in source
    assert 'network_capability": False' in source


def test_frozen_prediction_reproduces_amc_geometry() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    curves = predictions.validate_predictions(value, ROOT)

    assert value["compiler_source_commit"] == (
        "d254526da7e0cd17ec2335992c61f8e6c628d1bb"
    )
    assert value["compiler_source_sha256"] == (
        "94a0206cfd9d76f495a76256a500d41ac1feb2d8f56a7adf9499d1e8a8164d8c"
    )
    assert value["compiler_manifest_sha256"] == (
        "1d277ed619b69bbb6b113e924202c8c7a6901e0816fd8aeedfa4bc696ef92a4e"
    )
    assert value["curve_set_sha256"] == (
        "5ca0813f5951b4cf8242b69654170db4153e56bfc9c90b0b0fb76cc55d3f0154"
    )
    assert value["timing_curve_set_sha256"] == (
        "e61db141bc507b0a19fcd91cba1a2a4db60c5819c89b9bc8c3709f573c469550"
    )
    assert predictions.canonical_sha256(PREDICTIONS) == (
        "c9f7236f3cc221cb8485fe82f0a739e720ee3725f9dbf7c7fcc54c4167794155"
    )
    assert set(curves) == set(predictions.HYPOTHESES)
    assert all(curve.shape == (139,) for curve in curves.values())
    regression = value["numerical_regression"]
    assert regression["controlling_null"] == "FROZEN_AFFINE_NULL"
    assert regression["controlling_heldout_separation_m"] == pytest.approx(
        162_247.192926376
    )
    assert regression["direct_timing_envelope_m"] == pytest.approx(
        1_138.6249408759177
    )
    assert regression["pairwise_decision_guard_m"] == pytest.approx(
        7_339.701234647398
    )
    assert regression["remaining_physical_margin_m"] == pytest.approx(
        154_907.49169172862
    )
    assert value["minimum_time_shifted_model_elevation_deg"] == pytest.approx(
        25.72562823684935
    )
    assert value["orbital_scores_produced"] == 0


def test_prediction_curve_tampering_is_refused() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    tampered = deepcopy(value)
    tampered["curves_m"]["ORBITAL_G22"][0] += 1.0

    with pytest.raises(
        predictions.AmcPredictionError,
        match="PREDICTION_CURVE_HASH_CHANGED",
    ):
        predictions.validate_predictions(tampered, ROOT)


def test_direct_timing_curve_tampering_is_refused() -> None:
    value = json.loads(PREDICTIONS.read_text(encoding="utf-8"))
    tampered = deepcopy(value)
    first = next(iter(tampered["direct_timing_envelope_curves_m"].values()))
    first[0] += 1.0

    with pytest.raises(
        predictions.AmcPredictionError,
        match="PREDICTION_TIMING_HASH_CHANGED",
    ):
        predictions.validate_predictions(tampered, ROOT)


def test_seal_grants_no_observation_or_executor_authority() -> None:
    seal = json.loads(SEAL.read_text(encoding="utf-8"))

    assert predictions.canonical_sha256(SEAL) == (
        "83a52b2fbaa8f921532684cc87f292ffb976fb8972e595d21ffa0a645b4bb2f5"
    )
    assert seal["state"] == "AMC_OBSERVER_PRIMARY_PREDICTION_FROZEN"
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
