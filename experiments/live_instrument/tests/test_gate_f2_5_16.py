"""Offline control-sequence attribution for frozen Gate F2.5.15."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256

from experiments.live_instrument import kiwi_gate_f2_5_16 as gate


def _clauses() -> dict[str, gate.AttributionClause]:
    return {item.clause_id: item for item in gate.audit_frozen_outcome().clauses}


def test_frozen_artifacts_and_local_control_source_are_hash_bound() -> None:
    result = gate.audit_frozen_outcome()

    assert result.receipt_sha256 == gate.FROZEN_RECEIPT_SHA256
    assert result.receipt_prefix_sha256 == gate.FROZEN_PREFIX_SHA256
    assert sha256(gate.PINNED_SERVER_ARCHIVE_PATH.read_bytes()).hexdigest() == (
        gate.PINNED_SERVER_ARCHIVE_SHA256
    )
    assert gate._canonical_source_sha256(gate.PINNED_LOCAL_CONTROL_PATH) == (
        gate.PINNED_LOCAL_CONTROL_SHA256
    )


def test_allocated_branches_exceeded_the_pinned_guard_before_ar_ok() -> None:
    allocated = tuple(
        branch for branch in gate.audit_frozen_outcome().branches if branch.channel_allocated
    )

    assert len(allocated) == 8
    assert Counter(item.keepalive_count_before_ar_ok for item in allocated) == {
        15: 7,
        16: 1,
    }
    assert all(
        item.keepalive_count_before_ar_ok > gate.PINNED_KEEPALIVE_GUARD
        for item in allocated
    )
    assert all(item.ar_ok_command_index in {23, 24} for item in allocated)


def test_receipt_proves_zero_snd_after_allocation_not_remote_cause() -> None:
    result = gate.audit_frozen_outcome()
    allocated = tuple(item for item in result.branches if item.channel_allocated)

    assert result.zero_snd_branch_count == 8
    assert all(item.snd_frame_count == 0 for item in allocated)
    assert all(item.close_payload_state == "EMPTY_NO_STATUS" for item in allocated)
    assert result.remote_close_cause is gate.RemoteCauseAssessment.INCONCLUSIVE


def test_pinned_source_contains_the_control_path_but_not_all_definitions() -> None:
    server = gate.audit_frozen_outcome().pinned_server

    assert server.pinned_commit == gate.PINNED_SERVER_COMMIT
    assert server.keepalive_counter_increment_present
    assert server.incomplete_setup_guard_present
    assert server.audio_gate_present
    assert server.ar_ok_setup_bit_present
    assert not server.cmd_snd_all_definition_retained


def test_live_receipt_does_not_bind_the_remote_server_revision() -> None:
    result = gate.audit_frozen_outcome()

    assert not result.pinned_server.remote_revision_bound_by_receipt
    assert _clauses()["REMOTE_SERVER_REVISION_BOUND"].state is (
        gate.ClauseState.NOT_EVALUATED
    )
    assert _clauses()["REMOTE_COMMAND_RECEIPT_ORDER_OBSERVED"].state is (
        gate.ClauseState.NOT_EVALUATED
    )
    assert _clauses()["REMOTE_CMD_RECV_AT_CLOSE_OBSERVED"].state is (
        gate.ClauseState.NOT_EVALUATED
    )


def test_local_plan_and_physical_capability_have_different_assessments() -> None:
    result = gate.audit_frozen_outcome()

    assert result.local_plan_assessment is (
        gate.LocalPlanAssessment.FALSIFIED_BY_PINNED_CONTROL_INVARIANT
    )
    assert result.physical_dual_snd_capability is (
        gate.PhysicalCapabilityAssessment.NOT_EVALUATED
    )
    assert _clauses()["PHYSICAL_DUAL_SND_CAPABILITY"].state is (
        gate.ClauseState.NOT_EVALUATED
    )


def test_authorised_and_unauthorised_claim_boundaries_are_explicit() -> None:
    result = gate.audit_frozen_outcome()

    assert any("unsafe" in claim for claim in result.authorised_claims)
    assert any("caused" in claim for claim in result.unauthorised_claims)
    assert any("lack multichannel" in claim for claim in result.unauthorised_claims)
    assert "The pinned incomplete-setup guard caused the remote closes." not in (
        result.authorised_claims
    )


def test_offline_audit_has_no_connector_and_persists_no_rf() -> None:
    before = tuple(
        (path.name, sha256(path.read_bytes()).hexdigest())
        for path in sorted(gate.FROZEN_RECEIPT_PATH.parent.glob("*.jsonl"))
    )
    result = gate.audit_frozen_outcome()
    after = tuple(
        (path.name, sha256(path.read_bytes()).hexdigest())
        for path in sorted(gate.FROZEN_RECEIPT_PATH.parent.glob("*.jsonl"))
    )

    assert before == after
    assert result.raw_rf_persistence == "ZERO"
    assert not hasattr(gate, "run_live")
    assert not hasattr(gate, "run_reviewed_once")
    assert not hasattr(gate, "websocket")
