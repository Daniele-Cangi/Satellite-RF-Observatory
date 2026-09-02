"""Offline tests for the bounded DORIS physical-envelope audit."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from experiments.orbital_discriminability import doris_physical_envelope_audit as audit


RECEIPT = (
    Path(__file__).parents[1] / "DORIS_PHYSICAL_ENVELOPE_AUDIT_RECEIPT.json"
)


def test_frozen_parent_receipts_and_cross_date_boundary_are_exact() -> None:
    receipts = audit.load_frozen_receipts()
    assert receipts["topology"]["outcome"] == (
        "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED"
    )
    result = audit.build_audit()
    assert result["cross_date_boundary"]["same_grid"] is False
    assert result["cross_date_boundary"]["development_topology"]["duration_s"] == 633.0
    assert result["cross_date_boundary"]["prospective_geometry"][
        "preliminary_margin_hz"
    ] == pytest.approx(18_144.79949954618)


def test_exact_cancellations_are_not_confused_with_open_terms() -> None:
    coordinate = audit.build_audit()["coordinate"]
    assert coordinate["first_order_ionosphere"] == "CANCELLED_EXACTLY"
    assert coordinate["shared_receiver_clock"] == (
        "CANCELLED_EXACTLY_AT_COMMON_EPOCH"
    )
    assert coordinate["shared_receiver_proper_time"] == (
        "CANCELLED_EXACTLY_AT_COMMON_EPOCH"
    )
    assert coordinate["frequency_shift_k"] == [0, 0]


def test_all_eight_surviving_families_remain_explicit() -> None:
    terms = audit.open_terms()
    assert len(terms) == 8
    assert {term.name for term in terms} == {
        "ABSOLUTE_DOR_TO_COORDINATE_TIME_ERROR_BOUND",
        "HIGHER_ORDER_IONOSPHERE",
        "DIFFERENTIAL_TROPOSPHERE",
        "STATION_PHASE_CENTERS_AND_ANTENNA_MAPS",
        "PHASE_WINDUP",
        "SHAPIRO_AND_ONE_WAY_RELATIVITY",
        "NONAFFINE_GROUND_OSCILLATOR_BEHAVIOR",
        "CHANNEL_SWITCH_OR_RECEIVER_NONCOMMON_BIAS",
    }
    assert {term.epistemic_class for term in terms} == {"UNRESOLVED"}
    assert all(term.finite_outcome_independent_bound_hz is None for term in terms)


def test_unresolved_term_cannot_become_zero_or_a_physical_decision() -> None:
    envelope = audit.conservative_envelope(audit.open_terms())
    assert envelope["state"] == "UNAVAILABLE"
    assert envelope["heldout_peak_to_peak_hz"] is None
    assert len(envelope["missing_terms"]) == 8

    result = audit.build_audit()
    assert result["outcome"] == audit.OUTCOME_BOUND_UNAVAILABLE
    assert result["decision"]["remaining_physical_margin_hz"] is None
    assert result["decision"]["maximum_admissible_detector_resolution_hz"] is None
    assert result["decision"]["negative_result_interpretable"] is False
    assert result["decision"]["next_measurement_access_authorized"] is False


def test_documented_performance_scale_is_not_used_as_a_bound() -> None:
    result = audit.build_audit()
    scales = result["descriptive_scales_not_bounds"]
    assert scales["published_system_accuracy_0_3_mm_per_s_single_link_hz"] == (
        pytest.approx(audit.S_BAND_HZ * 0.0003 / audit.C_MPS)
    )
    assert scales["policy"] == (
        "NONE_OF_THESE_VALUES_REDUCES_THE_UNCERTAINTY_ENVELOPE"
    )
    assert result["combined_envelope"]["heldout_peak_to_peak_hz"] is None


def test_receipt_is_strict_json_and_reproducible() -> None:
    expected = json.loads(audit.strict_json(audit.build_audit()))
    actual = json.loads(RECEIPT.read_text(encoding="utf-8"))
    for key, value in expected.items():
        assert actual[key] == value
    source = Path(audit.__file__).read_bytes().replace(b"\r\n", b"\n")
    assert actual["audit_source_sha256"] == sha256(source).hexdigest()
    assert actual["audit_source_commit"] == (
        "f731b44c08f5304253940547e486c6ea15a907ca"
    )
    encoded = audit.strict_json(expected)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded


def test_negative_range_rate_scale_is_rejected() -> None:
    with pytest.raises(audit.DorisEnvelopeError):
        audit.range_rate_scale_hz(-0.001)
