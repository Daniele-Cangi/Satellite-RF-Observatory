"""Offline tests for the privileged opaque prediction compiler."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    gnss_blind_orbit_assignment_predictions as predictions,
)


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / predictions.BUNDLE_NAME
BUNDLE_SHA256 = "a36aed59f32ee9b409778e44a0b661aebbf83c0675c58473c6655ad562c82ee2"
CURVE_SET_SHA256 = "0e5eb9207a15574cf66d25f5f1eccdedb4e9ec4129a32abf5d23a066fdd9b2df"


def test_compiler_binds_plan_screen_mapping_and_zero_primary_access() -> None:
    manifest = predictions.compiler_manifest(ROOT)

    assert manifest["authority"] == {
        "plan_receipt_sha256": predictions.PLAN_RECEIPT_SHA256,
        "plan_manifest_sha256": predictions.PLAN_MANIFEST_SHA256,
        "screen_receipt_sha256": predictions.SCREEN_RECEIPT_SHA256,
        "mapping_sha256": predictions.MAPPING_SHA256,
        "primary_access": {
            "execution_authority": False,
            "executor_present": False,
            "measurement_scores": 0,
            "network_requests": 0,
            "prediction_bundle_present": False,
            "primary_headers_opened": 0,
            "primary_observation_values": 0,
            "primary_payload_bytes": 0,
            "product_locators_queried": 0,
            "scorer_present": False,
        },
    }
    assert manifest["output"] == {
        "opaque_hypotheses": 6,
        "named_hypotheses": 0,
        "mapping_rows": 0,
        "observer_or_product_metadata": 0,
    }
    assert not any(manifest["observation_boundary"].values())


def test_exact_navigation_authority_is_the_previously_screened_doy226() -> None:
    authority = predictions.navigation_authority(ROOT)

    assert authority["name"] == "brdc2260.26n.gz"
    assert authority["compressed_bytes"] == 71_489
    assert authority["compressed_sha256"] == (
        "d2b2006769aac07d40497c547edef37c1cf1a32780981dffab971c610ae5b0b9"
    )
    assert authority["uncompressed_bytes"] == 297_923
    assert authority["uncompressed_sha256"] == (
        "4042f7a4138aa16acd8b2700d88ccca799f7b4c6e5ffa9f47b79ae371f05d665"
    )
    assert authority["semantics"] == (
        "BROADCAST_EPHEMERIS_MODEL_NOT_RECEIVER_OBSERVATION"
    )


def test_grid_and_compiler_manifest_are_deterministic() -> None:
    manifest = predictions.compiler_manifest(ROOT)

    assert manifest["grid"] == {
        "time_system": "GPS",
        "raw_start": "2026-08-14T06:14:30 GPS",
        "raw_stop": "2026-08-14T07:23:30 GPS",
        "raw_epochs": 139,
        "step_s": 30.0,
        "prefix_epochs": 79,
        "heldout_epochs": 60,
        "anchor_index": 0,
    }
    first = predictions.compiler_manifest_sha256(ROOT)
    second = predictions.compiler_manifest_sha256(ROOT)
    assert len(first) == 64
    assert first == second


def test_invalid_navigation_is_refused_before_decompression() -> None:
    with pytest.raises(
        predictions.BlindOrbitPredictionError,
        match="NAVIGATION_GZIP_SIZE_CHANGED",
    ):
        predictions.build_bundle_from_gzip(b"not navigation", ROOT)


def test_compiler_has_no_network_observation_decoder_or_score_surface() -> None:
    source = Path(predictions.__file__).read_text(encoding="utf-8")

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "import hatanaka",
        "def score_observation",
        "def decode_observation",
    ):
        assert forbidden not in source
    assert '"network_capability": False' in source


def test_strict_json_rejects_nonfinite_values() -> None:
    assert json.loads(predictions.strict_json({"finite": 1.25})) == {
        "finite": 1.25
    }
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("nan")})
    with pytest.raises(ValueError):
        predictions.strict_json({"bad": float("inf")})


def test_frozen_bundle_is_exact_opaque_and_same_grid() -> None:
    canonical = BUNDLE.read_bytes().replace(b"\r\n", b"\n")
    value = json.loads(canonical)

    assert len(canonical) == 20_849
    assert predictions.canonical_sha256(BUNDLE) == BUNDLE_SHA256
    assert set(value) == {"schema", "grid", "opaque_ids", "curves_m", "scoring"}
    assert value["opaque_ids"] == sorted(value["curves_m"])
    assert len(value["opaque_ids"]) == 6
    assert len(set(value["opaque_ids"])) == 6
    assert all(identifier.startswith("H_") for identifier in value["opaque_ids"])
    assert all(len(curve) == 139 for curve in value["curves_m"].values())
    assert all(
        np.all(np.isfinite(np.asarray(curve, dtype=np.float64)))
        for curve in value["curves_m"].values()
    )
    assert sum(not any(curve) for curve in value["curves_m"].values()) == 1
    assert predictions.bundle_curve_set_sha256(value) == CURVE_SET_SHA256
    assert sha256(predictions.strict_json(value["curves_m"]).encode("ascii")).hexdigest() == (
        CURVE_SET_SHA256
    )


def test_frozen_bundle_discloses_no_identity_or_provenance_surface() -> None:
    rendered = BUNDLE.read_text(encoding="ascii").lower()

    for forbidden in (
        "g22",
        "g30",
        "satellite",
        "mapping",
        "observer",
        "product",
        "affine",
        "source_commit",
        "navigation",
    ):
        assert forbidden not in rendered


def test_frozen_compiler_source_and_manifest_are_exact() -> None:
    assert predictions.source_sha256() == (
        "3160bc4ab9c9fbbabca20457d7cfd4aa14d3d84f8a388ca850a6162504600544"
    )
    assert predictions.compiler_manifest_sha256(ROOT) == (
        "e87298ef2af0cc7359f8458249468b10a08491788305c6932ce7f79c3a5023f7"
    )
