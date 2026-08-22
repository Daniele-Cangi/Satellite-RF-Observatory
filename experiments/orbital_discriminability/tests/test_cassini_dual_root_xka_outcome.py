from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.orbital_discriminability import (
    cassini_dual_root_xka_compiler as compiler,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "CASSINI_DUAL_ROOT_XKA_COMPILER_RECEIPT.json"


def _receipt():
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def test_outcome_is_bound_by_the_frozen_preaccess_authority():
    receipt = _receipt()
    assert receipt["source_commit"] == (
        "a7ddd39062e8ebe79e47eed607d53b4fe94c644a"
    )
    assert receipt["compiler_manifest_sha256"] == (
        "b4c103d40e9a43d5704f4a63e1e59b78c6e3117886fec8ae92c87ece1c4f3823"
    )
    assert receipt["canonical_compiler_source_sha256"] == (
        "ea3f3ee640a579c85a70dc9c9388ada34d6f9f1ee1f08569e8d6c3ec3c021508"
    )
    assert receipt["outcome"] == compiler.OUTCOME_BLOCKED


def test_exact_geometry_survives_but_physical_margin_is_not_admitted():
    geometry = _receipt()["geometry_and_nulls"]
    assert geometry["records"] == 5_279
    assert geometry["calibration_records"] == 1_056
    assert geometry["holdout_records"] == 4_223
    assert geometry["joint_visibility"] is True
    assert geometry["controlling_heldout_peak_to_peak_hz"] == pytest.approx(
        0.2995923735627999, abs=1e-15
    )
    assert geometry["timing_envelope"]["four_stream_weighted_hz"] == (
        pytest.approx(2.04165223073319e-05, abs=1e-18)
    )
    assert (
        geometry["nulls"]["saturn_barycenter_geometry_destroying"][
            "heldout_peak_to_peak_hz"
        ]
        < geometry["nulls"]["prefix_affine"]["heldout_peak_to_peak_hz"]
    )


def test_first_order_cancellation_is_structural_not_an_rf_measurement():
    receipt = _receipt()
    geometry = receipt["geometry_and_nulls"]
    coefficient = geometry["composition_weights"][
        "maximum_first_order_plasma_coefficient_abs"
    ]
    assert coefficient["DSS25"] < 1e-35
    assert coefficient["DSS55"] < 1e-35
    assert geometry["rf_or_plasma_observed"] is False
    assert receipt["nco_semantics"] == (
        "RECEIVER_STEERING_METADATA_NOT_RF_MEASUREMENT"
    )


def test_all_seven_unresolved_terms_block_detector_resolution():
    receipt = _receipt()
    ledger = receipt["seven_term_physical_ledger"]
    assert [row["name"] for row in ledger] == list(compiler.OPEN_TERM_NAMES)
    assert all(row["bound_state"] == "UNAVAILABLE" for row in ledger)
    assert receipt["correlated_envelope"]["unresolved_is_zero"] is False
    assert receipt["correlated_envelope"]["root_sum_square_used"] is False
    assert (
        receipt["correlated_envelope"][
            "maximum_admissible_detector_resolution_hz"
        ]
        is None
    )


def test_access_boundary_remained_header_only_and_ephemeral():
    receipt = _receipt()
    assert receipt["access"] == {
        "sfdu_control_header_bytes": 5_491_200,
        "data_chdo_bytes_requested": 0,
        "data_chdo_bytes_read": 0,
        "iq_bytes_accessed": 0,
        "amplitude_or_signal_diagnostics_represented": False,
        "raw_headers_persisted": False,
        "detector_implemented": False,
    }
    assert receipt["iq_access_authorized"] is False
    assert all(
        item["raw_headers_persisted"] is False
        and len(item["derived_coordinate_artifact_sha256"]) == 64
        for item in receipt["coordinate_artifacts"]
    )
