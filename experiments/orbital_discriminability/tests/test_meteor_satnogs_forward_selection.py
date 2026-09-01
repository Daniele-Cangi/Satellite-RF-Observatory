"""Offline tests for the bounded METEOR SatNOGS geometry selection."""

from __future__ import annotations

import inspect
import json

import pytest

from experiments.orbital_discriminability import meteor_satnogs_forward_selection as selection


RECEIPT = selection.evaluate_selection()


def test_receipt_is_strict_and_accesses_no_rf() -> None:
    receipt = RECEIPT
    encoded = selection.strict_json(receipt)

    assert receipt["outcome"] == selection.OUTCOME
    assert receipt["rf_artifact_requests"] == 0
    assert receipt["rf_bytes_accessed"] == 0
    assert receipt["audio_requests"] == 0
    assert receipt["decoded_data_requests"] == 0
    assert len(receipt["receipt_sha256"]) == 64
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert json.loads(encoded)["measurement_admission"]["state"] == "UNRESOLVED"


def test_only_frozen_records_enter_the_bounded_selection() -> None:
    receipt = RECEIPT

    assert [item["observation_id"] for item in receipt["development_records"]] == [
        14904366,
        14907984,
    ]
    assert {
        item["observation_id"] for item in receipt["sealed_primary_records"]
    } == {14919555, 14919561, 14919551, 14919554}
    assert len(receipt["ranked_primary_pairs"]) == 6
    assert all(item["payload_access"] == "ZERO" for item in receipt["development_records"])
    assert all(
        item["payload_access"] == "ZERO" for item in receipt["sealed_primary_records"]
    )


def test_geometry_ranking_uses_joint_visibility_and_frozen_nulls() -> None:
    receipt = RECEIPT
    pairs = receipt["ranked_primary_pairs"]

    assert [item["rank"] for item in pairs] == list(range(1, 7))
    assert all(item["joint_visible_calibration_samples"] >= 6 for item in pairs)
    assert all(item["joint_visible_holdout_samples"] >= 16 for item in pairs)
    assert all(item["differential_signature_span_hz"] > 0.0 for item in pairs)
    assert all(item["controlling_null_heldout_rmse_hz"] > 0.0 for item in pairs)
    assert all(item["instrument_envelope"] == "UNKNOWN_NOT_SUBTRACTED" for item in pairs)
    assert all(
        {score["name"] for score in item["frozen_null_scores"]}
        == {
            "N0_STATION_CONSTANT",
            "N1_STATION_AFFINE",
            "N2_STATION_QUADRATIC",
            "N3_OBSERVER_GEOMETRY_PERMUTED",
        }
        for item in pairs
    )


def test_frozen_top_three_geometry_regression() -> None:
    top = RECEIPT["ranked_primary_pairs"][:3]

    assert [item["observation_ids"] for item in top] == [
        [14919555, 14919561],
        [14919554, 14919561],
        [14919551, 14919555],
    ]
    assert [item["geometry_only_resolution_ceiling_hz"] for item in top] == pytest.approx(
        [1017.9052626349511, 903.7055726592781, 805.8311301300853],
        rel=0.0,
        abs=1.0e-9,
    )
    assert [item["differential_signature_span_hz"] for item in top] == pytest.approx(
        [4506.363745881999, 4103.047084050584, 2933.4581080545586],
        rel=0.0,
        abs=1.0e-9,
    )


def test_doppler_control_is_a_required_transform_not_silently_ignored() -> None:
    receipt = RECEIPT
    audit = receipt["source_transform_audit"]["doppler_control"]

    assert audit["topology"] == "soapy source -> Doppler compensation -> waterfall sink"
    assert audit["applied_control_samples_or_polynomial"] == (
        "NOT_EXPOSED_IN_OBSERVATION_METADATA"
    )
    assert receipt["measurement_admission"]["state"] == "UNRESOLVED"


def test_module_has_no_network_or_payload_client() -> None:
    source = inspect.getsource(selection)

    for forbidden in (
        "import requests",
        "import urllib",
        "import websocket",
        "import socket",
        "waterfall_url",
        "audio_url",
        "urlopen",
    ):
        assert forbidden not in source
