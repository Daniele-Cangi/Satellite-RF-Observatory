from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    cassini_dss14_rank1_open_term_audit as audit,
)


def test_exact_grid_and_ranked_receipt_are_frozen():
    grid = audit.exact_frozen_grid()
    receipt = audit.validate_ranked_receipt()

    assert len(grid) == 10_800
    assert audit._format_utc(grid[0]) == "2006-09-08T12:00:01.500500Z"
    assert audit._format_utc(grid[-1]) == "2006-09-08T15:00:00.500500Z"
    assert receipt["candidates"][0]["rank"] == 1
    assert (
        receipt["candidates"][0]["prediction"]["heldout_peak_to_peak_hz"]
        == pytest.approx(0.18576614507706193, abs=0.0)
    )


def test_prefix_affine_projection_does_not_refit_the_holdout():
    elapsed = np.arange(audit.GRID_RECORDS, dtype=np.float64)
    curve = 7.0 + 0.25 * elapsed
    curve[audit.CALIBRATION_RECORDS :] += np.linspace(
        0.0, 1.0, audit.GRID_RECORDS - audit.CALIBRATION_RECORDS
    ) ** 2

    metrics = audit._projected_metrics(curve)

    assert metrics["peak_to_peak_hz"] == pytest.approx(1.0, abs=1e-10)
    assert metrics["rms_hz"] > 0.0


def test_central_curve_cannot_be_promoted_to_a_bound():
    term = audit._term(
        audit.OPEN_TERM_NAMES[0],
        audit.PROVENANCE_INDEPENDENT,
        {"peak_to_peak_hz": 0.1, "rms_hz": 0.05},
        "central model only",
    )

    assert term["bound_state"] == "UNAVAILABLE"
    assert term["central_model_reduces_envelope"] is False
    assert term["admitted_heldout_peak_to_peak_bound_hz"] is None


def test_manifest_is_strict_and_deterministic():
    first = audit.audit_manifest_sha256()
    second = audit.audit_manifest_sha256()

    assert first == second
    assert len(first) == 64
    assert sha256(bytes.fromhex(first)).hexdigest() != first
    assert json.loads(audit.strict_json({"value": 1.0})) == {"value": 1.0}
    with pytest.raises(ValueError):
        audit.strict_json({"value": float("nan")})


def test_audit_path_has_no_rsr_or_detector_input():
    signature = inspect.signature(audit.audit_open_terms)
    source = inspect.getsource(audit.audit_open_terms)

    assert set(signature.parameters) == {"spice", "kernel_paths"}
    assert "read_bytes" not in source
    assert "fromfile" not in source
    assert "decode" not in source.casefold()


def test_frozen_receipt_refuses_without_inventing_a_detector_requirement():
    path = Path(audit.__file__).with_name(
        "CASSINI_DSS14_RANK1_OPEN_TERM_AUDIT_RECEIPT.json"
    )
    raw = path.read_text(encoding="utf-8")
    receipt = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(
        ValueError(value)
    ))

    assert receipt["outcome"] == "CASSINI_OPEN_TERM_BOUND_UNAVAILABLE"
    assert receipt["iq_access_authorized"] is False
    assert receipt["detector_implementation_authorized"] is False
    assert receipt["conservative_combination"]["remaining_physical_margin_hz"] is None
    assert (
        receipt["conservative_combination"]
        ["maximum_admissible_detector_resolution_hz"]
        is None
    )
    assert len(receipt["terms"]) == 7
    assert all(term["bound_state"] == "UNAVAILABLE" for term in receipt["terms"])
