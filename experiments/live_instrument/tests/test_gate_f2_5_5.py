"""Offline tests for Gate F2.5.5 source and control-receipt contract."""

from __future__ import annotations

from dataclasses import asdict
import ast
import json
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_5 as f255
from experiments.live_instrument.models import strict_json_value


DIGEST = "a" * 64


def _open(role: str = "reference", ordinal: int = 0) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.TRANSPORT,
        f255.ControlEventKind.WEBSOCKET_OPENED,
    )


def _auth(role: str = "reference", ordinal: int = 1) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.LOCAL_CLIENT,
        f255.ControlEventKind.AUTH_COMMAND_RESULT,
        command_kind="auth_redacted",
        command_digest=DIGEST,
        command_result=f255.CommandResult.SUCCEEDED,
    )


def _sample(role: str = "reference", ordinal: int = 2) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.REMOTE_ENDPOINT,
        f255.ControlEventKind.SERVER_FIELD_OBSERVED,
        server_field=f255.ServerField.SAMPLE_RATE,
        value_state=f255.ValueState.POSITIVE_FINITE,
        numeric_value=11_998.9,
    )


def _tune(role: str = "reference", ordinal: int = 3) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.LOCAL_CLIENT,
        f255.ControlEventKind.CONFIG_COMMAND_RESULT,
        command_kind="mod_iq",
        command_digest=DIGEST,
        command_result=f255.CommandResult.SUCCEEDED,
    )


def _badp(role: str = "reference", ordinal: int = 4) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.REMOTE_ENDPOINT,
        f255.ControlEventKind.SERVER_FIELD_OBSERVED,
        server_field=f255.ServerField.BADP,
        value_state=f255.ValueState.NONZERO,
    )


def _close(role: str = "reference", ordinal: int = 4) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.TRANSPORT,
        f255.ControlEventKind.WEBSOCKET_CLOSE_OBSERVED,
        close_code=1000,
        detail_digest=DIGEST,
    )


def _loss(role: str = "reference", ordinal: int = 4) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.TRANSPORT,
        f255.ControlEventKind.TCP_LOSS_OBSERVED,
        error_type="WebSocketConnectionClosedException",
    )


def _iq(role: str = "reference", ordinal: int = 4) -> f255.SndControlEventReceipt:
    return f255.SndControlEventReceipt(
        role,
        ordinal,
        ordinal * 10,
        f255.ControlOrigin.REMOTE_ENDPOINT,
        f255.ControlEventKind.IQ_FRAME_OBSERVED,
        detail_digest=DIGEST,
    )


def test_default_gate_fails_closed_on_missing_official_source_material() -> None:
    assessment = f255.assess_gate_f2_5_5()
    assert assessment.exit is f255.F255Exit.SOURCE_BASIS_INCOMPLETE
    assert assessment.source_basis_reproducible is False
    assert assessment.receipt_contract_complete is True
    assert len(assessment.missing_source_material) == 5
    assert assessment.implementation_authorised is False
    assert assessment.live_execution_authorised is False
    assert "the local client is conformant or nonconformant" in assessment.unauthorised_claims


def test_hashes_without_local_artifacts_do_not_make_source_reproducible() -> None:
    hashes_only = f255.OfficialSourceRequirement(
        project="fixture",
        repository="https://example.invalid/source",
        commit="b" * 40,
        required_locations=("src/protocol.cpp:1-2",),
        retained_artifact_hashes=(DIGEST,),
    )
    assert hashes_only.locally_reproducible is False
    assert (
        f255.assess_gate_f2_5_5((hashes_only,)).exit
        is f255.F255Exit.SOURCE_BASIS_INCOMPLETE
    )
    assert (
        f255.assess_gate_f2_5_5(()).exit
        is f255.F255Exit.SOURCE_BASIS_INCOMPLETE
    )


def test_complete_declared_basis_still_requires_review_before_implementation() -> None:
    requirement = f255.OfficialSourceRequirement(
        project="fixture",
        repository="https://example.invalid/source",
        commit="b" * 40,
        required_locations=("src/protocol.cpp:1-2",),
        retained_artifact_paths=("protocol_sources/protocol.cpp",),
        retained_artifact_hashes=(DIGEST,),
    )
    assessment = f255.assess_gate_f2_5_5((requirement,))
    assert assessment.exit is f255.F255Exit.CONTROL_SPEC_READY_FOR_IMPLEMENTATION_REVIEW
    assert assessment.source_basis_reproducible
    assert assessment.implementation_authorised is False
    assert assessment.live_execution_authorised is False


def test_contract_preserves_discriminators_without_rf_or_secrets() -> None:
    contract = f255.control_receipt_contract()
    assert contract.complete
    assert set(contract.required_event_kinds) == set(f255.ControlEventKind)
    assert "password" in contract.persisted_fields_forbidden
    assert "raw_msg" in contract.persisted_fields_forbidden
    assert "rf_samples" in contract.persisted_fields_forbidden
    assert "iq_samples" in contract.persisted_fields_forbidden
    assert "waterfall" in contract.persisted_fields_forbidden
    assert "credential-redacted" in contract.command_digest_scope


def test_configuration_then_rejection_is_ordered_without_claiming_acceptance() -> None:
    trace = f255.SndControlTrace(
        "reference",
        (_open(), _auth(), _sample(), _tune(), _badp(), _close(ordinal=5)),
    )
    assert f255.classify_trace(trace) is f255.TraceObservation.SERVER_REFUSAL_SIGNAL_OBSERVED
    assert trace.events[3].event_kind is f255.ControlEventKind.CONFIG_COMMAND_RESULT
    assert trace.events[4].server_field is f255.ServerField.BADP


def test_close_frame_and_tcp_loss_are_distinct_observations() -> None:
    prefix = (_open(), _auth(), _sample(), _tune())
    close_trace = f255.SndControlTrace("reference", prefix + (_close(),))
    loss_trace = f255.SndControlTrace("reference", prefix + (_loss(),))
    assert (
        f255.classify_trace(close_trace)
        is f255.TraceObservation.WEBSOCKET_CLOSED_WITHOUT_IQ
    )
    assert (
        f255.classify_trace(loss_trace)
        is f255.TraceObservation.TRANSPORT_LOST_WITHOUT_IQ
    )


def test_iq_readiness_requires_prior_sample_rate_and_successful_tune() -> None:
    trace = f255.SndControlTrace(
        "reference",
        (_open(), _auth(), _sample(), _tune(), _iq()),
    )
    assert f255.classify_trace(trace) is f255.TraceObservation.IQ_READY_OBSERVED

    with pytest.raises(ValueError, match="prior sample-rate"):
        f255.SndControlTrace("reference", (_open(), _auth(), _tune(ordinal=2)))
    with pytest.raises(ValueError, match="successful mod_iq"):
        f255.SndControlTrace("reference", (_open(), _auth(), _sample(), _iq(ordinal=3)))


def test_receipt_rejects_raw_auth_kind_nonfinite_values_and_mixed_origins() -> None:
    with pytest.raises(ValueError, match="redacted command kind"):
        f255.SndControlEventReceipt(
            "reference",
            1,
            10,
            f255.ControlOrigin.LOCAL_CLIENT,
            f255.ControlEventKind.AUTH_COMMAND_RESULT,
            command_kind="auth p=secret",
            command_digest=DIGEST,
            command_result=f255.CommandResult.SUCCEEDED,
        )
    with pytest.raises(ValueError, match="finite"):
        f255.SndControlEventReceipt(
            "reference",
            2,
            20,
            f255.ControlOrigin.REMOTE_ENDPOINT,
            f255.ControlEventKind.SERVER_FIELD_OBSERVED,
            server_field=f255.ServerField.SAMPLE_RATE,
            value_state=f255.ValueState.POSITIVE_FINITE,
            numeric_value=float("nan"),
        )
    with pytest.raises(ValueError, match="remote server-field"):
        f255.SndControlEventReceipt(
            "reference",
            2,
            20,
            f255.ControlOrigin.LOCAL_CLIENT,
            f255.ControlEventKind.SERVER_FIELD_OBSERVED,
            server_field=f255.ServerField.BADP,
            value_state=f255.ValueState.ZERO,
        )


def test_failed_command_result_is_typed_and_cannot_masquerade_as_success() -> None:
    failed_auth = f255.SndControlEventReceipt(
        "reference",
        1,
        10,
        f255.ControlOrigin.LOCAL_CLIENT,
        f255.ControlEventKind.AUTH_COMMAND_RESULT,
        command_kind="auth_redacted",
        command_digest=DIGEST,
        command_result=f255.CommandResult.FAILED,
        error_type="WebSocketSendException",
    )
    trace = f255.SndControlTrace("reference", (_open(), failed_auth))
    assert f255.classify_trace(trace) is f255.TraceObservation.CONTROL_INCOMPLETE

    with pytest.raises(ValueError, match="typed local error"):
        f255.SndControlEventReceipt(
            "reference",
            1,
            10,
            f255.ControlOrigin.LOCAL_CLIENT,
            f255.ControlEventKind.AUTH_COMMAND_RESULT,
            command_kind="auth_redacted",
            command_digest=DIGEST,
            command_result=f255.CommandResult.SUCCEEDED,
            error_type="ImpossibleSuccessError",
        )


def test_trace_rejects_mixed_roles_backwards_time_and_events_after_close() -> None:
    with pytest.raises(ValueError, match="mix"):
        f255.SndControlTrace("reference", (_open(), _auth(role="perturbed")))
    backwards = (_open(), _auth(), _sample())
    backwards = backwards[:2] + (
        f255.SndControlEventReceipt(
            "reference",
            2,
            5,
            f255.ControlOrigin.REMOTE_ENDPOINT,
            f255.ControlEventKind.SERVER_FIELD_OBSERVED,
            server_field=f255.ServerField.SAMPLE_RATE,
            value_state=f255.ValueState.POSITIVE_FINITE,
            numeric_value=12_000.0,
        ),
    )
    with pytest.raises(ValueError, match="backwards"):
        f255.SndControlTrace("reference", backwards)
    with pytest.raises(ValueError, match="terminal"):
        f255.SndControlTrace(
            "reference",
            (_open(), _auth(), _close(ordinal=2), _sample(ordinal=3)),
        )


def test_assessment_and_contract_are_strict_json_serializable() -> None:
    payload = {
        "assessment": asdict(f255.assess_gate_f2_5_5()),
        "contract": asdict(f255.control_receipt_contract()),
    }
    encoded = json.dumps(strict_json_value(payload), allow_nan=False, sort_keys=True)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert f255.F255Exit.SOURCE_BASIS_INCOMPLETE.value in encoded


def test_module_has_no_import_time_io_network_or_runtime_surface() -> None:
    source = Path(f255.__file__).read_text(encoding="utf-8")
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
