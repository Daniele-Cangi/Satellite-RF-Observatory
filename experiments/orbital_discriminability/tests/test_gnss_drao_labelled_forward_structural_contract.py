"""Tests for the unopened DRAO labelled-forward structural contract."""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_structural_contract as contract,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / contract.OUTPUT_NAME


def compiled() -> dict[str, object]:
    return contract.contract(ROOT)


def test_authorities_bind_admitted_envelope_and_station_root() -> None:
    values = contract.verify_authorities(ROOT)
    assert set(values) == {
        contract.MARKDOWN_NAME,
        contract.ENVELOPE_NAME,
        contract.ROOT_METADATA_NAME,
    }
    assert values[contract.ENVELOPE_NAME]["role"] == "ADMITTED_PHYSICAL_ENVELOPE"


def test_candidate_is_fixed_but_artifact_and_access_are_unselected() -> None:
    value = compiled()
    candidate = value["candidate"]
    assert value["state"] == contract.CONTRACT_STATE
    assert candidate["station"] == "DRAO00CAN"
    assert candidate["doy"] == 237
    assert candidate["artifact_selected"] is False
    assert candidate["artifact_filename"] is None
    assert candidate["locator"] is None
    assert candidate["network_authority"] is False
    assert candidate["payload_authority"] is False
    assert set(value["access_at_freeze"].values()) == {0}


def test_exact_six_labelled_tracks_and_full_grid_are_required() -> None:
    value = compiled()
    window = value["window"]
    scan = value["structural_scan"]
    assert window["satellites"] == ["G14", "G15", "G17", "G20", "G24", "G30"]
    assert window["raw_epochs"] == 139
    assert window["required_satellite_epoch_pairs"] == 834
    assert scan["required_fields_each_satellite_epoch"] == [
        "L1C",
        "L2W",
        "C1C",
        "C2W",
    ]
    assert scan["complete_window_scan_even_after_first_failure"] is True
    assert scan["required_prn_substitution"] == "FORBIDDEN"
    assert scan["extra_tracks"] == "DESCRIPTIVE_NOT_FATAL_NOT_SCORED"
    assert scan["interpolation"] == "FORBIDDEN"
    assert scan["gap_bridging"] == "FORBIDDEN"


def test_structure_does_not_pretend_to_satisfy_physical_clauses() -> None:
    value = compiled()
    deferred = value["physical_clauses_deferred_not_satisfied"]
    assert deferred["geometry_free_phase_continuity"]["state"] == "NOT_EVALUATED"
    assert deferred["phase_minus_code_same_path_witness"]["state"] == "NOT_EVALUATED"
    assert deferred["multipath_hardware_and_receiver_implementation"]["state"] == "NOT_EVALUATED"
    assert deferred["orbital_affine_and_time_reversed_scores"]["state"] == "NOT_EVALUATED"
    assert value["physical_envelope_binding"][
        "structure_alone_activates_conditional_reserve"
    ] is False


def test_description_error_is_not_measurement_or_topology_rejection() -> None:
    value = compiled()
    semantics = value["outcome_semantics"]
    assert "NO_MEASUREMENT_REJECTION" in semantics["description_error"]
    assert "PARSED" in semantics["topology_rejected"]
    assert "PHYSICAL_WITNESS" in semantics["ready"]


def test_receipt_surface_excludes_observation_values_and_orbit() -> None:
    value = compiled()
    receipt = value["future_structural_receipt"]
    assert receipt["numeric_observation_values"] == 0
    assert receipt["derived_measurement_series"] == 0
    assert receipt["orbital_prediction_available_to_scanner"] is False
    assert receipt["orbital_scores"] == 0
    assert set(value["persistence"].values()) == {0}


def test_no_retry_or_fallback_after_complete_hash() -> None:
    value = compiled()
    retry = value["retry_policy"]
    assert retry["before_complete_transport_hash"] == [
        "TIMEOUT",
        "TRANSPORT_INTERRUPTION",
    ]
    assert retry["after_complete_transport_hash"] == 0
    assert retry["after_decompression"] == 0
    assert retry["fallback_date_endpoint_or_artifact"] is False


def test_contract_has_no_network_decoder_or_score_surface() -> None:
    source = inspect.getsource(contract).casefold()
    for forbidden in (
        "requests.get",
        "urllib.request",
        "hatanaka.decompress",
        "georinex",
        "score_observation",
    ):
        assert forbidden not in source


def test_strict_json_rejects_nonfinite() -> None:
    with pytest.raises(ValueError):
        contract.strict_json({"bad": float("nan")})


@pytest.mark.skipif(not OUTPUT.exists(), reason="generated after source freeze")
def test_generated_contract_matches_compiler_exactly() -> None:
    persisted = json.loads(OUTPUT.read_text(encoding="ascii"))
    assert persisted == compiled()
    assert persisted["state"] == contract.CONTRACT_STATE
    assert persisted["new_gate"] is False
    assert persisted["generic_framework"] is False
