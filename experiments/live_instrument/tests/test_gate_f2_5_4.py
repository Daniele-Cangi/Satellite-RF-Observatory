"""Offline tests for Gate F2.5.4 control-boundary attribution."""

from __future__ import annotations

from dataclasses import asdict
import ast
from hashlib import sha256
import json
from pathlib import Path

from experiments.live_instrument import kiwi_gate_f2_5_4 as f254
from experiments.live_instrument.models import strict_json_value


OUTCOME_PATH = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "gate-f2-5-3-1-20260816T204247.641290Z.jsonl"
)


def _documents() -> tuple[dict[str, object], ...]:
    assert sha256(OUTCOME_PATH.read_bytes()).hexdigest() == f254.OUTCOME_ARTIFACT_HASH
    return tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in OUTCOME_PATH.read_text(encoding="utf-8").splitlines()
    )


def _branch(
    *,
    endpoint: str = "fixture.invalid:8073",
    role: str = "reference",
    state: str = "CAPABILITY_REJECTED",
    error_type: str | None = "BranchCapabilityRejected",
    configured: bool = True,
    messages: int = 7,
    frames: int = 0,
) -> f254.BranchControlReceipt:
    return f254.BranchControlReceipt(
        endpoint,
        role,
        state,
        True,
        messages,
        configured,
        12_000.0 if messages else None,
        frames,
        error_type,
    )


def test_frozen_outcome_has_expected_atomic_control_population() -> None:
    receipts = f254.atomic_branch_receipts(_documents())
    audit = f254.audit_session(receipts)

    assert len(receipts) == 16
    assert audit.branch_count == 16
    assert audit.endpoint_count == 6
    assert audit.configured_branch_count == 15
    assert audit.ready_branch_count == 0
    assert audit.iq_frame_count == 0
    assert dict(audit.attribution_counts) == {
        f254.FailureAttribution.NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT.value: 11,
        f254.FailureAttribution.SERVER_REPORTED_CAPABILITY_REJECTION.value: 4,
        f254.FailureAttribution.TRANSPORT_TIMEOUT_BEFORE_HANDSHAKE.value: 1,
    }
    assert dict(audit.observed_stage_counts) == {
        f254.ObservedControlStage.CONFIGURATION_SENT_EXPLICIT_REJECTION.value: 4,
        f254.ObservedControlStage.CONFIGURATION_SENT_NO_IQ.value: 11,
        f254.ObservedControlStage.WEBSOCKET_OPEN_NO_SERVER_MESSAGE.value: 1,
    }
    assert audit.exit is f254.SessionExit.STOP_PENDING_CONTROL_DISCRIMINATORS


def test_configuration_sent_does_not_prove_remote_acceptance() -> None:
    receipts = f254.atomic_branch_receipts(_documents())
    configured_rejections = [
        receipt
        for receipt in receipts
        if receipt.configuration_sent
        and receipt.error_type == "BranchCapabilityRejected"
    ]
    assert len(configured_rejections) == 4
    assert all(
        f254.audit_branch(receipt).attribution
        is f254.FailureAttribution.SERVER_REPORTED_CAPABILITY_REJECTION
        for receipt in configured_rejections
    )


def test_transport_closures_remain_not_diagnosable() -> None:
    receipts = f254.atomic_branch_receipts(_documents())
    closed = [
        receipt
        for receipt in receipts
        if receipt.error_type == "WebSocketConnectionClosedException"
    ]
    assert len(closed) == 11
    assert all(receipt.configuration_sent for receipt in closed)
    audits = tuple(f254.audit_branch(receipt) for receipt in closed)
    assert all(
        item.observed_stage is f254.ObservedControlStage.CONFIGURATION_SENT_NO_IQ
        for item in audits
    )
    assert all(
        item.attribution is f254.FailureAttribution.NOT_DIAGNOSABLE_WITH_CURRENT_RECEIPT
        for item in audits
    )
    assert all("accepted" not in item.maximum_authorised_claim for item in audits)


def test_endpoints_are_not_independent_for_a_shared_client_failure_hypothesis() -> None:
    audit = f254.audit_session(f254.atomic_branch_receipts(_documents()))
    assert len(audit.endpoint_roots) == 6
    assert audit.common_client_root == f254.COMMON_CLIENT_ROOT
    assert audit.endpoint_failures_independent_for_client_hypothesis is False


def test_local_shape_is_only_consistent_with_prior_single_channel_path() -> None:
    audit = f254.protocol_surface_audit()
    assert audit.shape_matches_prior_local_single_channel_path
    assert audit.current_post_sample_command_kinds == (
        "squelch",
        "genattn",
        "gen",
        "ident_user",
        "mod",
        "agc",
        "compression",
        "keepalive",
    )
    assert (
        audit.official_source_basis
        is f254.OfficialSourceBasisStatus.REFERENCED_BUT_NOT_PRESENT_IN_REPOSITORY
    )
    assert "NOT_OFFICIALLY_REPRODUCIBLE" in audit.conformance_conclusion


def test_exit_semantics_require_explicit_evidence() -> None:
    all_rejected = (
        _branch(role="reference"),
        _branch(role="perturbed"),
    )
    assert f254.audit_session(all_rejected).exit is f254.SessionExit.NO_CAPABILITY_ADMITTED
    assert (
        f254.audit_session((all_rejected[0],)).exit
        is f254.SessionExit.STOP_PENDING_CONTROL_DISCRIMINATORS
    )

    ready_reference = _branch(
        state="READY",
        error_type=None,
        frames=1,
        messages=16,
    )
    ready_perturbed = _branch(
        role="perturbed",
        state="READY",
        error_type=None,
        frames=1,
        messages=16,
    )
    assert (
        f254.audit_session((ready_reference,)).exit
        is f254.SessionExit.STOP_PENDING_CONTROL_DISCRIMINATORS
    )
    assert (
        f254.audit_session((ready_reference, ready_perturbed)).exit
        is f254.SessionExit.PHYSICAL_EXPERIMENT_MAY_PROCEED
    )
    assert all(
        result.exit is not f254.SessionExit.CLIENT_CORRECTION_REQUIRED
        for result in (
            f254.audit_session(all_rejected),
            f254.audit_session((ready_reference, ready_perturbed)),
            f254.audit_session(f254.atomic_branch_receipts(_documents())),
        )
    )


def test_audit_is_strict_json_serializable() -> None:
    session = f254.audit_session(f254.atomic_branch_receipts(_documents()))
    surface = f254.protocol_surface_audit()
    encoded = json.dumps(
        strict_json_value({"session": asdict(session), "surface": asdict(surface)}),
        allow_nan=False,
        sort_keys=True,
    )
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert f254.SessionExit.STOP_PENDING_CONTROL_DISCRIMINATORS.value in encoded


def test_module_has_no_import_time_io_or_network_surface() -> None:
    source = Path(f254.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    assert top_level_calls == []
    assert "create_connection" not in source
    assert "requests." not in source
    assert "read_text" not in source
    assert "read_bytes" not in source
    assert "write_text" not in source
    assert "write_bytes" not in source
