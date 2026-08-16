"""Offline tests for the Gate F2.3 causal-topology audit."""

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2_3 as f23


def _qualified() -> f23.CapabilityQualification:
    return f23.CapabilityQualification(
        endpoint_status_available=True,
        external_api_slots=2,
        simultaneous_iq_supported=True,
        reference_stream_valid=True,
        perturbed_stream_valid=True,
        distinct_stream_sequences_and_receipts=True,
        per_channel_retune_witnessable=True,
        fixed_reference_branch_witnessable=True,
        target_and_witness_fit_passband=True,
    )


def _evidence() -> f23.ConfirmationEvidence:
    return f23.ConfirmationEvidence(
        both_streams_continuous=True,
        gnss_event_time_aligned=True,
        adc_clean_and_transform_complete=True,
        reference_command_ledger_clean=True,
        reference_branch_stable=True,
        retune_command_routed_to_perturbed_only=True,
        retune_effect_witnessed=True,
        target_detectable_in_a1_b_a2=True,
        a2_return_matches=True,
        upstream_prediction_matches=True,
        downstream_prediction_matches=False,
    )


def test_three_topologies_have_different_causal_cuts_and_claim_limits() -> None:
    audits = f23.topology_audits()
    assert tuple(audit.topology for audit in audits) == tuple(f23.TopologyKind)
    assert len({audit.causal_cut for audit in audits}) == 3
    assert "independent apparatus" in audits[0].maximum_authorised_claim
    assert "external RF" in audits[1].maximum_authorised_claim
    assert "cannot localise" in audits[2].maximum_authorised_claim
    assert audits[0].required_independence.startswith("hardware")
    assert audits[1].required_independence.startswith("simultaneous downstream channel")
    assert audits[2].required_independence.startswith("temporal reversibility")
    assert not any(audit.geographic_location_required for audit in audits)


def test_root_topology_is_derived_from_the_channel_ddc_intervention() -> None:
    requirement = f23.gate_f2_root_topology_requirement()
    assert requirement.intervention_boundary == "FPGA per-channel RX NCO/DDC"
    assert {"antenna", "ADC", "ADC sample clock"} <= set(requirement.shared_upstream_components)
    assert requirement.simultaneous_required
    assert requirement.channel_independence_required
    assert requirement.independent_stream_receipts_required
    assert not requirement.hardware_independence_required
    assert not requirement.geographic_location_required
    assert "external-RF" in requirement.claim_scope

    with pytest.raises(ValueError, match="two distinct downstream"):
        replace(
            requirement,
            independent_downstream_branches=("same", "same"),
            fixed_reference_branch="same",
            perturbed_branch="same",
        )
    with pytest.raises(ValueError, match="second hardware root"):
        replace(requirement, hardware_independence_required=True)


def test_code_audit_separates_verified_source_facts_from_live_availability() -> None:
    audit = f23.multi_channel_code_audit()
    assert len(audit.server_commit) == 40
    assert len(audit.client_commit) == 40
    retune = next(item for item in audit.evidence if "48-bit phase word" in item.proposition)
    assert retune.status == "VERIFIED_FROM_FROZEN_OFFICIAL_SOURCE_AUDIT"
    assert "no protocol tune acknowledgement" in retune.limit
    process = next(item for item in audit.evidence if "one process" in item.proposition)
    assert "same-endpoint availability remains a qualification fact" in process.limit
    timestamp = next(item for item in audit.evidence if "sequence field" in item.proposition)
    assert "not evidence of independent clocks" in timestamp.limit
    assert "ext_api can expose fewer than two free public slots" in audit.operator_limits


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        ({"external_api_slots": 1}, f23.F23Outcome.NO_MULTI_CHANNEL_CAPABILITY),
        ({"reference_stream_valid": False}, f23.F23Outcome.NO_MULTI_CHANNEL_CAPABILITY),
        ({"distinct_stream_sequences_and_receipts": False}, f23.F23Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY),
        ({"per_channel_retune_witnessable": False}, f23.F23Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY),
        ({"target_and_witness_fit_passband": False}, f23.F23Outcome.NO_FALSIFIABLE_INTERVENTION),
    ),
)
def test_qualification_distinguishes_capacity_topology_and_falsifiability(change, expected) -> None:
    assert f23.qualification_blocker(replace(_qualified(), **change)) is expected
    assert f23.qualification_blocker(_qualified()) is None


def test_hypotheses_use_ddc_boundary_not_external_rf_synonym() -> None:
    consequences = {item.hypothesis: item for item in f23.frozen_hypothesis_consequences()}
    upstream = consequences[f23.F23Hypothesis.H_UPSTREAM_OF_CHANNEL_DDC]
    downstream = consequences[f23.F23Hypothesis.H_DOWNSTREAM_CHANNEL_FIXED]
    assert "absolute-RF coordinate remains invariant" in upstream.reconstructed_rf_prediction
    assert "moves" in upstream.perturbed_baseband_prediction
    assert "same perturbed-channel baseband position" in downstream.perturbed_baseband_prediction
    assert "changes" in downstream.reconstructed_rf_prediction
    assert all("external RF" not in item.perturbed_baseband_prediction for item in consequences.values())


def test_vertical_probe_requires_two_simultaneous_channels_and_zero_postfreeze_retry() -> None:
    probe = f23.minimal_vertical_probe()
    assert probe.receiver_count == 1
    assert probe.simultaneous_snd_slots == 2
    assert probe.connection_roles == ("fixed_reference", "controllably_retuned")
    assert probe.phases == ("A1", "B", "A2")
    assert probe.post_freeze_retry_budget == 0
    assert "zero RF" in probe.persistence_policy
    assert "hash every ephemeral" in probe.artifact_policy
    assert "per_channel_retune_testimoniable" in probe.qualification_clauses


@pytest.mark.parametrize(
    ("change", "expected"),
    (
        ({"reference_command_ledger_clean": False}, f23.F23Outcome.INTERVENTION_INVALID),
        ({"reference_branch_stable": False}, f23.F23Outcome.INTERVENTION_INVALID),
        ({"retune_effect_witnessed": False}, f23.F23Outcome.INTERVENTION_INVALID),
        ({"both_streams_continuous": False}, f23.F23Outcome.NOT_DETECTABLE),
        ({"target_detectable_in_a1_b_a2": False}, f23.F23Outcome.NOT_DETECTABLE),
        ({}, f23.F23Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED),
        (
            {"upstream_prediction_matches": False, "downstream_prediction_matches": True},
            f23.F23Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED,
        ),
        ({"downstream_prediction_matches": True}, f23.F23Outcome.AMBIGUOUS),
        ({"upstream_prediction_matches": False}, f23.F23Outcome.AMBIGUOUS),
    ),
)
def test_confirmation_semantics_never_rescue_invalid_or_undetectable_data(change, expected) -> None:
    assert f23.classify_confirmation(replace(_evidence(), **change)) is expected


def test_gate_f2_3_module_has_no_network_or_acquisition_surface() -> None:
    source = Path(f23.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = (
        "urlopen",
        "websocket",
        "create_connection",
        "fetch_kiwi_status",
        "capture_dual_sequence",
        "run_once",
        "DIRECTORY_URL",
    )
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not any(token in imported or token in called for token in forbidden)
    names = set(vars(f23))
    assert not {"Planner", "InternetSource", "Database", "Catalog", "Scanner"} & names


def test_shock_preserves_the_unexpected_shared_root_ambiguity() -> None:
    primary, consequence = f23.shock_answer()
    assert "not required" in primary
    assert "same-ADC simultaneous intervention" in primary
    assert "coherent clock spur" in consequence
    assert "without proving external RF" in consequence
