from __future__ import annotations

from hashlib import sha256
import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import (
    cassini_sagr3_pretransition_open_term_audit as audit,
)
from experiments.orbital_discriminability import (
    cassini_sagr3_distributed_geometry as geometry,
)


def test_transition_receipt_and_seven_term_ledger_are_frozen():
    receipt = audit.validate_transition_receipt()

    assert receipt["transition_cause"] == "UNRESOLVED"
    assert audit.CONTROLLING_SEPARATION_HZ == 0.07231370056321107
    assert len(audit.OPEN_TERM_NAMES) == 7
    assert geometry.PRETRANSITION_RECORDS == 10_651
    assert geometry.PRETRANSITION_CALIBRATION_RECORDS == 3_360


def test_media_models_cover_both_independent_receive_complexes():
    assert audit.ION_MODELS["DSS-25"].complex_id == "C10"
    assert audit.ION_MODELS["DSS-65"].complex_id == "C60"
    assert audit.TRO_CORRECTIONS["DSS-25"].complex_id == "C10"
    assert audit.TRO_CORRECTIONS["DSS-65"].complex_id == "C60"
    assert (
        audit.ION_MODELS["DSS-25"].coefficients_m_at_s_band
        != audit.ION_MODELS["DSS-65"].coefficients_m_at_s_band
    )


def test_normalized_calibration_rejects_incomplete_coverage():
    epochs = np.asarray([10.0, 11.0, 12.0])
    values = audit._normalized_delay(epochs, 10.0, 12.0, (1.0, 2.0))

    assert values.tolist() == pytest.approx([-1.0, 1.0, 3.0])
    with pytest.raises(
        audit.CassiniSagr3OpenTermAuditError,
        match="does not cover",
    ):
        audit._normalized_delay(epochs, 10.5, 12.0, (1.0,))


def test_common_source_gravitational_rate_cancels_from_identical_branches():
    rows = 3
    station = np.tile(np.asarray([[7.0e6, 0.0, 0.0]]), (rows, 1))
    spacecraft = np.tile(np.asarray([[1.0e12, 2.0e11, 0.0]]), (rows, 1))
    sun = np.tile(np.asarray([[0.0, 0.0, 0.0]]), (rows, 1))
    earth = np.tile(np.asarray([[1.0e6, 0.0, 0.0]]), (rows, 1))
    saturn = np.tile(np.asarray([[1.1e12, 0.0, 0.0]]), (rows, 1))
    compiled = {
        "left_station": station,
        "right_station": station.copy(),
        "spacecraft": spacecraft,
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

    differential = audit._proper_time_gravity_differential(compiled)

    assert np.array_equal(differential, np.zeros(rows))


def test_exact_sr_factor_owns_endpoint_kinetic_proper_time():
    transverse_speed = 30_000.0
    factor = audit.one_way._frequency_factor(
        (0.0, 0.0, 0.0),
        (0.0, transverse_speed, 0.0),
        (1.0, 0.0, 0.0),
    )
    beta = transverse_speed / audit.one_way.SPEED_OF_LIGHT_M_S

    assert factor == pytest.approx(1.0 / np.sqrt(1.0 - beta * beta))
    gravitational_source = inspect.getsource(
        audit._endpoint_gravitational_rate
    )
    assert "velocity" not in gravitational_source
    assert "kinetic" not in gravitational_source


def test_proper_time_family_propagates_the_frozen_affine_worst_case():
    assert audit._prefix_affine_pointwise_bound_gain(4, 2) == pytest.approx(6.0)

    family = audit._proper_time_uncertainty_family()

    assert family["differential_raw_absolute_fractional_bound"] == 2e-15
    assert family["prefix_affine_maximum_absolute_gain"] == pytest.approx(
        9.040589085582225
    )
    assert family["heldout_non_affine_peak_to_peak_bound_hz"] == pytest.approx(
        0.000304667852184121
    )
    assert (
        family["heldout_non_affine_peak_to_peak_bound_hz"]
        < audit.CONTROLLING_SEPARATION_HZ
    )


def test_troposphere_delay_sigma_does_not_invent_frequency_covariance():
    family = audit._troposphere_candidate_uncertainty_family()

    assert family["zenith_delay_one_sigma_m"] == 0.01
    assert family["frequency_family_state"] == "UNAVAILABLE"
    assert family["promoted_to_bound"] is False
    assert (
        "temporal covariance or Allan-deviation model for both paths"
        in family["missing"]
    )


def test_prefix_projection_is_frozen_and_never_refits_holdout():
    elapsed = np.arange(geometry.PRETRANSITION_RECORDS, dtype=np.float64)
    curve = 4.0 + 0.1 * elapsed
    curve[geometry.PRETRANSITION_CALIBRATION_RECORDS :] += np.linspace(
        0.0,
        1.0,
        geometry.PRETRANSITION_HOLDOUT_RECORDS,
    ) ** 2

    metrics = audit._projected_metrics(curve)

    assert metrics["peak_to_peak_hz"] == pytest.approx(1.0, abs=1e-10)
    assert metrics["rms_hz"] > 0.0


def test_central_or_partial_curve_cannot_be_promoted_to_a_bound():
    term = audit._term(
        audit.OPEN_TERM_NAMES[2],
        audit.PROVENANCE_INDEPENDENT,
        None,
        "incomplete central model",
        partial_diagnostic={"peak_to_peak_hz": 0.1, "rms_hz": 0.05},
        epistemic_class=audit.EPISTEMIC_UNRESOLVED,
    )

    assert term["bound_state"] == "UNAVAILABLE"
    assert term["epistemic_class"] == "UNRESOLVED"
    assert term["central_or_partial_model_reduces_envelope"] is False
    assert term["admitted_heldout_peak_to_peak_bound_hz"] is None


def test_modeled_requires_a_family_and_unresolved_cannot_receive_a_bound():
    with pytest.raises(
        audit.CassiniSagr3OpenTermAuditError,
        match="MODELED requires",
    ):
        audit._term(
            audit.OPEN_TERM_NAMES[0],
            audit.PROVENANCE_INDEPENDENT,
            None,
            "missing family",
            epistemic_class=audit.EPISTEMIC_MODELED,
        )

    with pytest.raises(
        audit.CassiniSagr3OpenTermAuditError,
        match="MODELED requires",
    ):
        audit._term(
            audit.OPEN_TERM_NAMES[0],
            audit.PROVENANCE_INDEPENDENT,
            None,
            "bound without family",
            epistemic_class=audit.EPISTEMIC_MODELED,
            admitted_peak_to_peak_bound_hz=0.001,
        )

    with pytest.raises(
        audit.CassiniSagr3OpenTermAuditError,
        match="only MODELED",
    ):
        audit._term(
            audit.OPEN_TERM_NAMES[2],
            audit.PROVENANCE_INDEPENDENT,
            None,
            "invented bound",
            epistemic_class=audit.EPISTEMIC_UNRESOLVED,
            admitted_peak_to_peak_bound_hz=0.001,
        )


def test_manifest_is_strict_deterministic_and_amplitude_blind():
    first = audit.audit_manifest_sha256()
    second = audit.audit_manifest_sha256()
    signature = inspect.signature(audit.audit_open_terms)
    source = inspect.getsource(audit.audit_open_terms)

    assert first == second
    assert len(first) == 64
    assert sha256(bytes.fromhex(first)).hexdigest() != first
    assert set(signature.parameters) == {"spice", "kernel_paths"}
    assert "read_bytes" not in source
    assert "fromfile" not in source
    assert "decode" not in source.casefold()
    assert json.loads(audit.strict_json({"value": 1.0})) == {"value": 1.0}
    with pytest.raises(ValueError):
        audit.strict_json({"value": float("nan")})


def test_frozen_receipt_separates_modeled_from_unresolved_terms():
    path = Path(audit.__file__).with_name(
        "CASSINI_SAGR3_PRETRANSITION_OPEN_TERM_AUDIT_RECEIPT.json"
    )
    raw = path.read_text(encoding="utf-8")
    receipt = json.loads(
        raw,
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
    )

    assert receipt["audit_manifest_sha256"] == audit.audit_manifest_sha256()
    assert receipt["outcome"] == "CASSINI_OPEN_TERM_BOUND_UNAVAILABLE"
    assert len(receipt["terms"]) == 7
    proper_time = receipt["terms"][0]
    troposphere = receipt["terms"][2]
    assert proper_time["epistemic_class"] == "MODELED"
    assert proper_time["bound_state"] == "BOUNDED_UNCERTAINTY_FAMILY"
    assert proper_time["central_model_heldout_non_affine"][
        "peak_to_peak_hz"
    ] == 0.0005846983090055662
    assert proper_time["admitted_heldout_peak_to_peak_bound_hz"] == (
        0.000304667852184121
    )
    assert troposphere["epistemic_class"] == "UNRESOLVED"
    assert troposphere["bound_state"] == "UNAVAILABLE"
    assert troposphere["uncertainty_family"]["promoted_to_bound"] is False
    assert receipt["scientific_correction"]["error"] == (
        "KINETIC_ENDPOINT_TERM_DOUBLE_COUNTED_AFTER_EXACT_SR_GAMMA"
    )
    combination = receipt["conservative_combination"]
    assert combination["admitted_modeled_term_names"] == [
        "PROPER_TIME_AND_GRAVITATIONAL_FREQUENCY"
    ]
    assert combination["admitted_modeled_peak_to_peak_bound_hz"] == (
        0.000304667852184121
    )
    assert combination["combined_open_term_envelope_state"] == "UNAVAILABLE"
    assert combination["remaining_physical_margin_hz"] is None
    assert combination["maximum_admissible_detector_resolution_hz"] is None
    assert receipt["iq_access_authorized"] is False
    assert receipt["detector_implementation_authorized"] is False
