"""Offline tests for the metadata-only Cassini DSS-26 open-term audit."""

import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import cassini_dss26_open_term_audit as audit


def test_exact_grid_is_reconstructed_only_from_frozen_receipt_contract() -> None:
    grid = audit.exact_frozen_grid()
    assert len(grid) == 9_651
    assert audit._format_utc(grid[0]) == "2005-06-06T17:50:01.500500Z"
    assert audit._format_utc(grid[-1]) == "2005-06-06T20:30:51.500500Z"
    assert all((right - left).total_seconds() == 1.0 for left, right in zip(grid, grid[1:]))


def test_authoritative_receipt_keeps_affine_null_and_exact_seven_terms() -> None:
    receipt = audit.validate_authoritative_receipt()
    assert receipt["causal_scope"]["affine_baseband_null"] == (
        "CONTROLLING_NONORBITAL_COMPARISON"
    )
    assert receipt["prediction"][
        "heldout_orbital_vs_affine_baseband_peak_to_peak_hz"
    ] == pytest.approx(0.06391264328448062, abs=0.0)
    assert tuple(receipt["open_terms_without_numerical_bound"]) == audit.OPEN_TERM_NAMES


def test_prefix_affine_projection_does_not_create_nonlinearity() -> None:
    elapsed = np.arange(audit.GRID_RECORDS, dtype=np.float64)
    metrics = audit._projected_metrics(19.0 - 0.0017 * elapsed)
    assert metrics["peak_to_peak_hz"] < 1e-11
    assert metrics["rms_hz"] < 1e-11


def test_unavailable_term_never_receives_an_invented_bound() -> None:
    term = audit._unavailable_term(
        audit.OPEN_TERM_NAMES[0],
        audit.PROVENANCE_UNKNOWN,
        {"peak_to_peak_hz": 1.0, "rms_hz": 0.2, "maximum_absolute_hz": 0.8},
        "no hard bound",
    )
    assert term["central_model_reduces_envelope"] is False
    assert term["admitted_heldout_peak_to_peak_bound_hz"] is None
    assert term["admitted_heldout_rms_bound_hz"] is None
    audit.strict_json(term)


def test_source_has_no_rsr_or_detector_access_path() -> None:
    source = Path(audit.__file__).read_text(encoding="utf-8").lower()
    forbidden = (
        "read_verified_headers(",
        "verify_development_artifact(",
        "decode_iq",
        "carrier_tracker",
        "s11sags2005_157_1750nnnx26rd.dat",
    )
    assert all(token not in source for token in forbidden)


def test_manifest_binds_frozen_scope_deterministically() -> None:
    digest = audit.audit_manifest_sha256()
    assert len(digest) == 64
    assert digest == audit.audit_manifest_sha256()


def test_frozen_audit_receipt_has_one_refusal_and_no_invented_resolution() -> None:
    path = Path(audit.__file__).with_name("CASSINI_DSS26_OPEN_TERM_AUDIT_RECEIPT.json")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    assert receipt["outcome"] == audit.OUTCOME_BOUND_UNAVAILABLE
    assert len(receipt["terms"]) == 7
    assert receipt["conservative_combination"][
        "maximum_admissible_detector_resolution_hz"
    ] is None
    assert all(term["bound_state"] == "UNAVAILABLE" for term in receipt["terms"])
    audit.strict_json(receipt)
