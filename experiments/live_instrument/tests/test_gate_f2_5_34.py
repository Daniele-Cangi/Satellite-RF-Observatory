"""Offline receipt-only failure-attribution tests for Gate F2.5.34."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import inspect
import json

import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5_22 as f2522
from experiments.live_instrument import kiwi_gate_f2_5_34 as f2534


def test_exact_receipt_lineage_and_terminal_state_are_bound() -> None:
    attribution = f2534.assess_frozen()

    assert sha256(f2534.FROZEN_RECEIPT_PATH.read_bytes()).hexdigest() == (
        f2534.FROZEN_RECEIPT_SHA256
    )
    assert attribution.reviewed_outcome_commit == (
        "51c43c78f7e69d937e2ac25cdbd60b84df415ecf"
    )
    assert attribution.reviewed_runtime_seal_commit == (
        "77a5f733725e83e758560eb1af7db4ee1a4d3d25"
    )
    assert attribution.receipt_event_order == f2534.EXPECTED_EVENTS
    assert attribution.receipt_retention_state == "COMPLETE"
    assert attribution.receipt_error_count == 0
    assert attribution.authority_envelope_hash == (
        f2534.FROZEN_AUTHORITY_ENVELOPE_HASH
    )
    assert attribution.source_seals_match is True


def test_sensor_operation_is_not_mistaken_for_hypothesis_support() -> None:
    attribution = f2534.assess_frozen()

    assert attribution.sensor_capability_state == (
        "MEASUREMENT_AVAILABLE_BUT_NO_FALSIFIABLE_FEATURE_ADMITTED"
    )
    assert attribution.outcome == "NO_FALSIFIABLE_INTERVENTION"
    assert attribution.physical_hypothesis_state == "NOT_EVALUATED"
    evidence = " ".join(attribution.sensor_operational_evidence)
    assert "two distinct simultaneous" in evidence
    assert "zero gaps" in evidence
    assert "253937919 ns" in evidence
    assert "8192 IQ samples were zeroized" in evidence


def test_only_composite_failure_is_observable_not_its_internal_cut() -> None:
    stages = {item.stage: item for item in f2534.assess_frozen().discovery_stages}

    assert stages["spectral_residual_transform"].state is f2534.StageState.EXECUTED
    for name in (
        "joint_contrast_peak",
        "normalised_patch_validity",
        "cross_branch_structure",
        "half_window_stability",
    ):
        assert stages[name].receipt_observable is False
        assert stages[name].state is f2534.StageState.UNRESOLVED_FROM_RECEIPT
    assert stages["composite_feature_admission"].receipt_observable is True
    assert stages["composite_feature_admission"].state is (
        f2534.StageState.UNSATISFIED
    )
    assert stages["ddc_intervention_prediction"].state is (
        f2534.StageState.NOT_EVALUATED
    )


def test_epistemic_classification_is_scoped_and_does_not_infer_a_cause() -> None:
    conclusions = {
        item.scope: item for item in f2534.assess_frozen().scoped_conclusions
    }

    assert conclusions["frozen_composite_discovery_proposition"].classification is (
        f2534.EpistemicClassification.FALSIFYING
    )
    assert conclusions["specific_discovery_rejection_stage"].classification is (
        f2534.EpistemicClassification.INCONCLUSIVE
    )
    assert conclusions[
        "upstream_vs_downstream_channel_ddc_hypothesis"
    ].classification is (
        f2534.EpistemicClassification.NOT_FALSIFIABLE_WITH_THIS_RECEIPT
    )
    assert all(
        item.state is f2534.StageState.UNRESOLVED_FROM_RECEIPT
        for item in f2534.assess_frozen().discovery_stages[1:5]
    )


def test_thresholds_and_minimum_detectable_structure_are_frozen() -> None:
    mother = f2.MotherPlan()
    attribution = f2534.assess_frozen()

    assert dict(attribution.frozen_thresholds) == {
        "minimum_joint_contrast_db": mother.minimum_contrast_db,
        "minimum_half_contrast_db": mother.minimum_half_contrast_db,
        "minimum_cross_branch_correlation": mother.minimum_fingerprint_correlation,
    }
    assert dict(attribution.frozen_stft_geometry) == {
        "nperseg": mother.nperseg,
        "noverlap": mother.noverlap,
    }
    assert attribution.thresholds_changed is False
    assert any("5.0 dB" in item.minimum_detectable_structure for item in attribution.discovery_stages)
    assert any("0.65" in item.minimum_detectable_structure for item in attribution.discovery_stages)
    assert any("3.0 dB" in item.minimum_detectable_structure for item in attribution.discovery_stages)


def test_prior_scalar_audit_already_contains_the_minimal_future_fields() -> None:
    fields = f2522.DiscoveryAuditReceipt.__dataclass_fields__
    attribution = f2534.assess_frozen()

    assert attribution.legacy_audit_already_expresses_needed_fields is True
    assert {
        "raw_peak_count",
        "patch_valid_count",
        "correlation_pass_count",
        "half_stability_pass_count",
        "admitted_feature_count",
        "input_artifact_hashes",
        "raw_rf_persistence",
    } <= fields.keys()
    assert "add a decision-independent scalar DiscoveryAuditReceipt beside the existing DiscoveryReceipt" in (
        attribution.minimal_future_descriptive_change
    )


def test_tamper_and_nonfinite_json_fail_closed() -> None:
    raw = f2534.FROZEN_RECEIPT_PATH.read_bytes()
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        f2534._strict_documents(raw + b" ", f2534.FROZEN_RECEIPT_SHA256)

    invalid = b'{"event":NaN}\n'
    digest = sha256(invalid).hexdigest()
    with pytest.raises(ValueError, match="non-finite JSON"):
        f2534._strict_documents(invalid, digest)


def test_description_cannot_change_the_frozen_physical_decision() -> None:
    attribution = f2534.assess_frozen()
    altered_description = replace(
        attribution,
        minimal_future_descriptive_change=("synthetic alternative description",),
        possible_false_negative_conditions=("synthetic unproven possibility",),
    )

    assert altered_description.outcome == attribution.outcome
    assert altered_description.physical_hypothesis_state == (
        attribution.physical_hypothesis_state
    )
    assert altered_description.physical_decision_affected is False
    assert attribution.physical_decision_affected is False


def test_strict_output_has_no_rf_payload_or_nonstandard_numbers() -> None:
    attribution = f2534.assess_frozen()
    encoded = attribution.to_strict_json()
    decoded = json.loads(
        encoded,
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )

    assert decoded["raw_rf_persistence"] == "ZERO"
    assert decoded["live_execution_authorised"] is False
    assert "NaN" not in encoded and "Infinity" not in encoded
    forbidden = ("samples", "iq_payload", "waterfall", "stft_matrix", "spectrum")
    assert all(key not in decoded for key in forbidden)
    assert attribution.physical_decision_affected is False


def test_gate_has_no_live_connector_or_acquisition_surface() -> None:
    source = inspect.getsource(f2534)

    assert "websocket" not in source
    assert "create_connection" not in source
    assert "requests." not in source
    assert "urlopen" not in source
    assert "run_reviewed_once" not in source
    assert f2534.RAW_RF_PERSISTENCE == "ZERO"
