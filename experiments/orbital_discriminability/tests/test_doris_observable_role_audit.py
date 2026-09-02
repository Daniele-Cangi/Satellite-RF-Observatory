"""Offline tests for the DORIS compound-observable causal audit."""

from __future__ import annotations

from fractions import Fraction
import inspect

from experiments.orbital_discriminability import doris_observable_role_audit as audit


def test_ionosphere_free_phase_coefficients_preserve_geometry() -> None:
    alpha, beta = audit.ionosphere_free_coefficients()

    assert alpha + beta == 1


def test_ionosphere_free_phase_coefficients_cancel_inverse_frequency_squared() -> None:
    alpha, beta = audit.ionosphere_free_coefficients()

    ionosphere_gain = (
        alpha * Fraction(1, audit.S_BAND_HZ**2)
        + beta * Fraction(1, audit.UHF_BAND_HZ**2)
    )
    assert ionosphere_gain == 0


def test_receiver_clock_cancels_only_for_exact_coepoch_pair() -> None:
    simultaneous = audit.same_epoch_pair_coefficients()
    asynchronous = audit.asynchronous_pair_coefficients()

    assert simultaneous["SHARED_RECEIVER_CLOCK_AT_COMMON_EPOCH"] == 0
    assert asynchronous["SHARED_RECEIVER_CLOCK_AT_LEFT_EPOCH"] == 1
    assert asynchronous["SHARED_RECEIVER_CLOCK_AT_RIGHT_EPOCH"] == -1


def test_audit_narrows_code_witness_and_refuses_current_admission() -> None:
    receipt = audit.build_audit()

    assert receipt["outcome"] == (
        "DORIS_DUAL_PHASE_DIFFERENTIAL_REQUIRES_COEPOCH_REQUALIFICATION"
    )
    assert receipt["preferred_conditional_pair"]["pair"] == ["PAUB", "RIMC"]
    assert receipt["decision"]["old_per_target_code_witness"] == (
        "NOT_UNIVERSAL_REPLACE_WITH_CLAIM_SCOPED_TIME_BRIDGE"
    )
    assert receipt["decision"]["current_measurement_admission"] == "NOT_EVALUATED"
    assert receipt["scope"]["observation_artifact_access"] == "ZERO"
    assert receipt["scope"]["candidate_day_access"] == "ZERO"
    assert "COMMON_RECEPTION_EPOCH_ERROR_TO_FIRST_ORDER_IF_SAME_TAG" in receipt[
        "same_epoch_pair_terms"
    ]["conditional_common_mode_reduction"]
    assert "COMMON_RECEPTION_EPOCH_ERROR_TO_FIRST_ORDER_IF_SAME_TAG" not in receipt[
        "same_epoch_pair_terms"
    ]["cancelled_exactly_in_symbolic_model"]


def test_audit_has_no_artifact_or_network_surface() -> None:
    source = inspect.getsource(audit)

    assert "s3arx26242" not in source
    assert "s3arx26245" not in source
    assert "requests" not in source
    assert "ftplib" not in source
    assert "subprocess" not in source
    assert "open(" not in source
