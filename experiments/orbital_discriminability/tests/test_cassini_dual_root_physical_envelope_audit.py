from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    cassini_dual_root_physical_envelope_audit as audit,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "CASSINI_DUAL_ROOT_PHYSICAL_ENVELOPE_AUDIT_RECEIPT.json"


def _receipt():
    return json.loads(
        RECEIPT.read_text(encoding="ascii"),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )


def test_parent_authority_and_frozen_comparison_are_unchanged():
    parent = audit.validate_parent_receipt()

    assert parent["outcome"] == "CASSINI_DUAL_ROOT_PHYSICAL_ENVELOPE_UNAVAILABLE"
    assert audit.CONTROLLING_SEPARATION_HZ == 0.2995923735627999
    assert audit.TIMING_ENVELOPE_HZ == 2.04165223073319e-05
    assert audit.GRID_RECORDS == 5_279
    assert audit.CALIBRATION_RECORDS == 1_056


def test_common_spacecraft_clock_contribution_cancels_between_equal_roots():
    rows = 4
    station = np.tile(np.asarray([[7.0e6, 0.0, 0.0]]), (rows, 1))
    spacecraft = np.tile(np.asarray([[1.0e12, 2.0e11, 0.0]]), (rows, 1))
    zero = np.zeros((rows, 3))
    sun = np.tile(np.asarray([[0.0, 0.0, 0.0]]), (rows, 1))
    earth = np.tile(np.asarray([[1.0e6, 0.0, 0.0]]), (rows, 1))
    saturn = np.tile(np.asarray([[1.1e12, 0.0, 0.0]]), (rows, 1))
    compiled = {
        "left_station": station,
        "right_station": station.copy(),
        "left_station_velocity": zero,
        "right_station_velocity": zero.copy(),
        "spacecraft": spacecraft,
        "spacecraft_velocity": zero.copy(),
        "sun_transmit": sun,
        "earth_transmit": earth,
        "saturn_transmit": saturn,
        "sun_left_receive": sun,
        "sun_right_receive": sun.copy(),
        "earth_left_receive": earth,
        "earth_right_receive": earth.copy(),
        "saturn_left_receive": saturn,
        "saturn_right_receive": saturn.copy(),
    }

    assert np.array_equal(
        audit._proper_time_gravity_differential(compiled),
        np.zeros(rows),
    )


def test_prefix_projection_cannot_refit_the_heldout_suffix():
    elapsed = np.arange(audit.GRID_RECORDS, dtype=np.float64)
    curve = 3.0 + 0.02 * elapsed
    curve[audit.CALIBRATION_RECORDS :] += np.linspace(
        0.0,
        1.0,
        audit.GRID_RECORDS - audit.CALIBRATION_RECORDS,
    ) ** 2

    metrics = audit._projected_metrics(curve)

    assert metrics["peak_to_peak_hz"] == pytest.approx(1.0, abs=1e-10)
    assert metrics["rms_hz"] > 0.0


def test_central_and_partial_models_never_become_uncertainty_bounds():
    term = audit._unresolved_term(
        "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY",
        "MODELED_CENTRAL_UNCERTAINTY_UNRESOLVED",
        audit.PROVENANCE_INDEPENDENT,
        {"peak_to_peak_hz": 0.08},
        "central is not uncertainty",
        partial={"peak_to_peak_hz": 0.001},
    )

    assert term["bound_state"] == "UNAVAILABLE"
    assert term["central_or_partial_model_reduces_envelope"] is False
    assert term["admitted_heldout_peak_to_peak_bound_hz"] is None


def test_amplitude_blind_input_surface_and_manifest_are_frozen():
    signature = inspect.signature(audit.audit_physical_envelope)
    source = inspect.getsource(audit.audit_physical_envelope).casefold()
    first = audit.audit_manifest_sha256()

    assert set(signature.parameters) == {"spice", "kernel_paths"}
    assert "read_bytes" not in source
    assert "header" not in signature.parameters
    assert "sample" not in signature.parameters
    assert "amplitude" not in signature.parameters
    assert first == audit.audit_manifest_sha256()
    assert len(first) == 64
    assert sha256(bytes.fromhex(first)).hexdigest() != first
    with pytest.raises(ValueError):
        audit.strict_json({"value": float("nan")})


def test_committed_outcome_closes_the_vertical_without_physical_claim():
    receipt = _receipt()

    assert receipt["audit_manifest_sha256"] == audit.audit_manifest_sha256()
    assert receipt["outcome"] == audit.OUTCOME_CLOSED
    assert receipt["frozen_comparison"]["changed"] is False
    assert len(receipt["terms"]) == 7
    assert all(term["bound_state"] == "UNAVAILABLE" for term in receipt["terms"])
    assert receipt["terms"][0]["central_model_heldout_non_affine"][
        "peak_to_peak_hz"
    ] == pytest.approx(0.08274380021596595, abs=1e-15)
    assert receipt["conservative_combination"][
        "combined_open_term_envelope_state"
    ] == "UNAVAILABLE"
    assert receipt["conservative_combination"][
        "maximum_admissible_detector_resolution_hz"
    ] is None
    assert receipt["causal_state_semantics"]["unresolved_is_zero"] is False
    assert receipt["causal_state_semantics"]["root_sum_square_used"] is False
    assert receipt["header_accessed"] is False
    assert receipt["iq_bytes_accessed"] == 0
    assert receipt["iq_access_authorized"] is False
    assert receipt["detector_implementation_authorized"] is False
