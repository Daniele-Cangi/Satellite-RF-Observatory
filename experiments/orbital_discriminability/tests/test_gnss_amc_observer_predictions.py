from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_amc_observer_predictions as predictions,
)


ROOT = Path(__file__).resolve().parents[1]


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
