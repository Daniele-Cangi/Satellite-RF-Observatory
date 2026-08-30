"""Offline tests for the bounded LuGRE ADC-time provenance closure."""

from __future__ import annotations

import json
from pathlib import Path

from experiments.orbital_discriminability import lugre_adc_time_provenance_closure as audit


ROOT = Path(__file__).resolve().parents[1]


def test_incomplete_causal_chain_has_no_finite_bound() -> None:
    assert audit.compose_end_to_end_bound_s(audit.TIME_CHAIN) is None


def test_complete_synthetic_chain_sums_conservative_bounds() -> None:
    edges = (
        {"finite_error_bound_s": 0.001},
        {"finite_error_bound_s": 0.002},
        {"finite_error_bound_s": 0.004},
    )
    assert audit.compose_end_to_end_bound_s(edges) == 0.007


def test_resolution_stability_and_generic_performance_are_not_bounds() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)
    rejected = {row["candidate"] for row in value["rejected_substitutes"]}

    assert "SDRX_AND_OPTABLE_MILLISECOND_FIELDS" in rejected
    assert "GENERIC_QN400_S_50_NS_TIMING_ACCURACY" in rejected
    assert "IDENTICAL_MODEL_OR_PREDICTED_VCTCXO_ALLAN_DEVIATION" in rejected
    assert value["composed_adc_to_true_gpst_error_bound_s"] is None


def test_every_public_source_is_outcome_independent_but_non_admitting() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)

    assert all(
        row["provenance"] == "INDEPENDENT_OF_TARGET_RF"
        for row in value["public_evidence"]
    )
    assert not any(row["can_reduce_adc_time_envelope"] for row in value["public_evidence"])


def test_route_closes_without_weakening_geometry_or_freezing_roles() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)

    assert value["outcome"] == audit.OUTCOME
    assert value["geometry_result"] == "PRESERVED_NOT_WEAKENED"
    assert value["timing_clause"]["state"] == "UNRESOLVED"
    assert value["roles_frozen"] is False
    assert value["prospective_plan_frozen"] is False
    assert value["automatic_successor"] is False


def test_access_boundary_remains_zero_measurement_bytes() -> None:
    value = audit.build_receipt(ROOT, "0" * 40)
    access = value["access_boundary"]

    assert access["new_iqs_compressed_payload_bytes"] == 0
    assert access["new_iqs_uncompressed_bytes"] == 0
    assert access["new_iq_sample_values"] == 0
    assert access["new_telemetry_bytes"] == 0
    assert access["new_signal_derived_diagnostics"] == 0
    assert access["all_three_candidate_products_opened"] is False
    assert access["detector_implemented"] is False
    assert access["orbital_score_recomputed"] is False


def test_source_has_no_network_decoder_detector_or_scorer() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8").lower()

    for forbidden in (
        "import requests",
        "import urllib",
        "import socket",
        "def decode_iq",
        "frombuffer",
        "spiceypy",
        "import skyfield",
        "from sgp4",
        "tlm_nav",
        "stft",
    ):
        assert forbidden not in source


def test_receipt_is_strict_json_when_materialized(tmp_path: Path) -> None:
    output = tmp_path / audit.RECEIPT_NAME
    assert audit.main(["--root", str(ROOT), "--source-commit", "0" * 40, "--output", str(output)]) == 0

    value = json.loads(output.read_text(encoding="ascii"))
    assert value["outcome"] == audit.OUTCOME
    assert value["composed_adc_to_true_gpst_error_bound_s"] is None
