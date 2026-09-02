"""Tests for the bounded offline DORIS observable-topology review."""

from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

from experiments.orbital_discriminability import doris_observable_topology_review as review


RECEIPT = (
    Path(__file__).parents[1] / "DORIS_OBSERVABLE_TOPOLOGY_REVIEW_RECEIPT.json"
)


def test_one_satellite_pair_cancels_only_shared_receiver_terms() -> None:
    coefficients = review.one_satellite_pair()
    assert review.family_coefficients(coefficients, "RECEIVER_CLOCK") == {}
    assert review.family_coefficients(coefficients, "RECEIVER_PROPER_TIME") == {}
    assert review.family_coefficients(coefficients, "TRANSMITTER_CLOCK") == {
        "B1/E01": -1,
        "B2/E02": 1,
    }
    assert len(review.family_coefficients(coefficients, "CHANNEL_NONCOMMON_BIAS")) == 2


def test_four_link_receive_coepoch_does_not_cancel_retarded_transmitter_clock() -> None:
    coefficients = review.four_link_same_receive_epochs()
    assert review.family_coefficients(coefficients, "RECEIVER_CLOCK") == {}
    assert review.family_coefficients(coefficients, "RECEIVER_PROPER_TIME") == {}
    assert review.family_coefficients(coefficients, "TRANSMITTER_CLOCK") == {
        "B1/E11": -1,
        "B1/E21": 1,
        "B2/E12": 1,
        "B2/E22": -1,
    }


def test_four_link_transmit_coepoch_trades_for_receiver_clock_residual() -> None:
    coefficients = review.four_link_same_transmit_epochs()
    assert review.family_coefficients(coefficients, "TRANSMITTER_CLOCK") == {}
    assert review.family_coefficients(coefficients, "TRANSMITTER_PROPER_TIME") == {}
    assert review.family_coefficients(coefficients, "RECEIVER_CLOCK") == {
        "S1/R11": 1,
        "S1/R12": -1,
        "S2/R21": -1,
        "S2/R22": 1,
    }


def test_review_selects_only_a_future_geometry_question() -> None:
    result = review.build_review()
    assert result["outcome"] == review.OUTCOME
    assert result["selection"]["recommended_topology"] == (
        "ONE_SATELLITE_TWO_TIME_REFERENCE_BEACONS"
    )
    assert result["time_reference_scope"]["header_declared_stations"] == [
        "ADHC",
        "HBMB",
        "PAUB",
        "TLSB",
    ]
    assert result["time_reference_scope"]["pair_count"] == 6
    assert result["scope"]["orbital_score"] == "NOT_EVALUATED"
    assert result["scope"]["observation_values_access"] == "ZERO"


def test_parent_receipt_hashes_are_line_ending_canonical() -> None:
    expected = review.FROZEN_RECEIPT_HASHES["development_header"]
    raw = review.HEADER_RECEIPT.read_bytes()
    canonical = raw.replace(b"\r\n", b"\n")
    assert sha256(canonical).hexdigest() == expected


def test_limited_code_witness_is_not_promoted_to_clock_solution() -> None:
    topology = review.build_review()["topologies"]["limited_c1_c2_time_witness"]
    assert topology["rank"] == 4
    assert topology["exact_cuts"] == []
    assert "FULL_DORIS_TIME_OR_POD_SCOPE" in topology["minimum_if_used"]


def test_review_has_no_network_or_measurement_surface() -> None:
    source = inspect.getsource(review)
    for forbidden in (
        "requests",
        "urllib",
        "ftplib",
        "subprocess",
        "spiceypy",
        "numpy",
        "scipy",
        "s3arx26245",
    ):
        assert forbidden not in source


def test_receipt_is_strict_reproducible_and_source_bound() -> None:
    actual = json.loads(RECEIPT.read_text(encoding="utf-8"))
    expected = json.loads(review.strict_json(review.build_review()))
    assert RECEIPT.read_text(encoding="utf-8").count('"shock"') == 1
    for key, value in expected.items():
        assert actual[key] == value
    source = Path(review.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert actual["review_source_sha256"] == sha256(source).hexdigest()
    encoded = review.strict_json(actual)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
