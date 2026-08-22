from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "GNSS_DOUBLE_DIFFERENCE_PROSPECTIVE_PLAN.md"
RECEIPT = ROOT / "GNSS_DOUBLE_DIFFERENCE_PROSPECTIVE_PLAN_RECEIPT.json"


def test_ionosphere_free_coefficients_preserve_geometric_range() -> None:
    alpha, beta = envelope.ionosphere_free_coefficients()

    assert alpha + beta == pytest.approx(1.0)
    assert alpha > 1.0
    assert beta < 0.0


def test_affine_projection_gain_is_finite_and_conservative() -> None:
    gain = envelope.affine_projection_peak_to_peak_gain(100, 20, 30.0)
    error = np.ones(100)

    assert gain > 2.0
    assert np.ptp(error[20:]) <= gain


def test_generic_path_bound_increases_linearly() -> None:
    one = envelope.generic_path_frequency_bound(1.0)
    four = envelope.generic_path_frequency_bound(4.0)

    assert one > 0.0
    assert four == pytest.approx(4.0 * one)


def test_quantization_bound_is_nonzero_and_format_driven() -> None:
    term = envelope.quantization_term(10.0)

    assert term["state"] == "KNOWN_FORMAT_BOUND"
    assert 0.0 < term["per_link_path_bound_m"] < 0.001
    assert term["heldout_peak_to_peak_bound_hz"] > term["raw_frequency_bound_hz"]


def test_manifest_forbids_measurement_access_and_post_outcome_changes() -> None:
    manifest = envelope.compiler_manifest()

    assert "carrier phase, code, SNR or LLI access" in manifest["forbidden"]
    assert "threshold or envelope reduction after measurement access" in manifest["forbidden"]
    assert manifest["policy"]["unresolved_as_zero"] is False
    assert manifest["policy"]["combination"] == "LINEAR_SUM_NOT_ROOT_SUM_SQUARE"
    assert envelope.compiler_manifest_sha256() == (
        "6428cd6b4de8bba5bfa11de79466a914472f38ce8df1fceae67bed973aa80218"
    )


def test_frozen_plan_receipt_binds_plan_and_keeps_measurements_sealed() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    plan_hash = sha256(PLAN.read_bytes()).hexdigest()

    assert plan_hash == receipt["plan_markdown"]["sha256"]
    assert receipt["outcome"] == "READY_FOR_GNSS_MEASUREMENT_AUTHORITY"
    assert receipt["prospective_plan_frozen"] is True
    assert receipt["measurement_authorized"] is False
    assert set(receipt["observation_access"].values()) == {0}
    selected = receipt["physical_envelope_ranking"][0]
    assert selected["target"] == "G11"
    assert selected["reference"] == "G21"
    assert selected["remaining_margin_hz"] == pytest.approx(1420.6255973372763)


def test_strict_json_refuses_nonfinite() -> None:
    with pytest.raises(ValueError):
        envelope.strict_json({"value": float("nan")})
