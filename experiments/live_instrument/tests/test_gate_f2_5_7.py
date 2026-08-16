"""Offline tests for the Gate F2.5.7 server-wire necessity audit."""

from __future__ import annotations

from dataclasses import asdict, replace
import ast
import json
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_6 as f256
from experiments.live_instrument import kiwi_gate_f2_5_7 as f257
from experiments.live_instrument.models import strict_json_value


DIGEST = "a" * 64


def _event(
    role: str,
    ordinal: int,
    kind: f257.WireEventKind,
    **kwargs: object,
) -> f257.WireEvent:
    return f257.WireEvent(role, ordinal, ordinal * 10, kind, **kwargs)


def _ready(role: str, channel_id: int, sequence: int = 17) -> f257.WireTranscript:
    kinds = f257.WireEventKind
    return f257.WireTranscript(
        role,
        (
            _event(role, 0, kinds.WEBSOCKET_OPENED),
            _event(role, 1, kinds.AUTH_SENT_REDACTED),
            _event(role, 2, kinds.CHANNEL_ALLOCATED_OBSERVED, channel_id=channel_id),
            _event(role, 3, kinds.BADP_OK_OBSERVED),
            _event(role, 4, kinds.AUDIO_RATE_OBSERVED, numeric_value=12_000.0),
            _event(role, 5, kinds.SAMPLE_RATE_OBSERVED, numeric_value=11_998.9),
            _event(role, 6, kinds.MOD_IQ_SENT),
            _event(
                role,
                7,
                kinds.IQ_FRAME_OBSERVED,
                artifact_hash=DIGEST,
                sequence=sequence,
            ),
        ),
    )


def test_current_gate_selects_server_wire_contract_without_client_source() -> None:
    source = f256.assess_gate_f2_5_6()
    assessment = f257.assess_gate_f2_5_7(source_assessment=source)

    assert f257.PARENT_GATE_COMMIT == "9bab5148b830c8a164f096d995e068f2626b1403"
    assert source.server_source_reproducible
    assert not source.client_source_reproducible
    assert assessment.exit is f257.F257Exit.SERVER_WIRE_CONTRACT_SUFFICIENT
    assert assessment.server_source_reproducible
    assert not assessment.official_client_source_required
    assert assessment.wire_contract_complete
    assert assessment.receipt_implementation_authorised
    assert not assessment.live_execution_authorised


def test_every_wire_event_has_a_gate_specific_claim_bridge() -> None:
    witnesses = {
        witness
        for bridge in f257.claim_bridges()
        for witness in bridge.required_receipt_witnesses
    }

    assert witnesses == set(f257.WireEventKind)
    assert all(not bridge.official_client_source_required for bridge in f257.claim_bridges())


def test_missing_server_finding_fails_closed() -> None:
    assessment = f257.assess_gate_f2_5_7(
        available_server_findings={"AUTH_GATE_ORDER"}
    )

    assert assessment.exit is f257.F257Exit.PROTOCOL_WITNESS_INCOMPLETE
    assert assessment.missing_server_findings
    assert not assessment.receipt_implementation_authorised
    assert not assessment.live_execution_authorised


def test_invalid_server_archive_fails_before_client_necessity() -> None:
    source = replace(
        f256.assess_gate_f2_5_6(),
        server_source_reproducible=False,
    )

    assessment = f257.assess_gate_f2_5_7(source_assessment=source)

    assert assessment.exit is f257.F257Exit.PROTOCOL_WITNESS_INCOMPLETE
    assert not assessment.receipt_implementation_authorised


def test_a_real_client_source_dependency_would_remain_blocked() -> None:
    bridges = list(f257.claim_bridges())
    bridges[0] = replace(bridges[0], official_client_source_required=True)

    assessment = f257.assess_gate_f2_5_7(bridges=bridges)

    assert assessment.exit is f257.F257Exit.CLIENT_SOURCE_REQUIRED
    assert assessment.official_client_source_required
    assert not assessment.receipt_implementation_authorised
    assert not assessment.live_execution_authorised


def test_allowlisted_msg_decode_preserves_order_and_real_channel_shape() -> None:
    fields = f257.decode_allowlisted_server_fields(
        "ignored=secret rx_chans=8 is_local=7,0,0 max_camp=4 badp=0 "
        "audio_rate=12000 sample_rate=11998.9"
    )

    assert [field.name for field in fields] == [
        "rx_chans",
        "is_local",
        "max_camp",
        "badp",
        "audio_rate",
        "sample_rate",
    ]
    assert [field.ordinal for field in fields] == [1, 2, 3, 4, 5, 6]
    channel = next(field for field in fields if field.name == "is_local")
    badp = next(field for field in fields if field.name == "badp")
    assert channel.channel_id == 7
    assert badp.state == "OK" and badp.numeric_value == 0.0
    assert "secret" not in json.dumps(strict_json_value(fields), allow_nan=False)


@pytest.mark.parametrize(
    "body,match",
    [
        ("badp=NaN", "integer"),
        ("badp=13", "range"),
        ("is_local=7,0", "channel, locality"),
        ("is_local=7,2,0", "outside"),
        ("sample_rate=NaN", "positive and finite"),
        ("too_busy=0", "positive"),
    ],
)
def test_malformed_allowlisted_field_is_description_error_not_rejection(
    body: str,
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        f257.decode_allowlisted_server_fields(body)


def test_two_distinct_ready_channels_make_only_the_wire_topology_ready() -> None:
    pair = f257.assess_pair_wire(
        _ready("reference", 3, 41),
        _ready("perturbed", 6, 91),
    )

    assert pair.state is f257.PairWireState.DUAL_WIRE_READY
    assert pair.reference.state is f257.BranchWireState.WIRE_READY
    assert pair.perturbed.state is f257.BranchWireState.WIRE_READY
    assert pair.reference.channel_id == 3
    assert pair.perturbed.channel_id == 6
    assert "DDC" not in pair.statement


def test_same_reported_channel_is_not_an_admissible_dual_topology() -> None:
    pair = f257.assess_pair_wire(
        _ready("reference", 3),
        _ready("perturbed", 3),
    )

    assert pair.state is f257.PairWireState.ADMISSIBLE_TOPOLOGY_MISSING


def test_local_mod_iq_before_remote_prerequisites_is_invalid_even_if_iq_arrives() -> None:
    kinds = f257.WireEventKind
    role = "reference"
    transcript = f257.WireTranscript(
        role,
        (
            _event(role, 0, kinds.WEBSOCKET_OPENED),
            _event(role, 1, kinds.AUTH_SENT_REDACTED),
            _event(role, 2, kinds.SAMPLE_RATE_OBSERVED, numeric_value=12_000.0),
            _event(role, 3, kinds.MOD_IQ_SENT),
            _event(role, 4, kinds.CHANNEL_ALLOCATED_OBSERVED, channel_id=2),
            _event(role, 5, kinds.BADP_OK_OBSERVED),
            _event(
                role,
                6,
                kinds.IQ_FRAME_OBSERVED,
                artifact_hash=DIGEST,
                sequence=8,
            ),
        ),
    )

    branch = f257.assess_branch_wire(transcript)

    assert branch.state is f257.BranchWireState.CONTROL_ORDER_INVALID
    assert "before" in branch.statement


def test_iq_before_local_mod_iq_cannot_witness_the_command() -> None:
    kinds = f257.WireEventKind
    role = "reference"
    transcript = f257.WireTranscript(
        role,
        (
            _event(role, 0, kinds.WEBSOCKET_OPENED),
            _event(role, 1, kinds.AUTH_SENT_REDACTED),
            _event(role, 2, kinds.BADP_OK_OBSERVED),
            _event(role, 3, kinds.CHANNEL_ALLOCATED_OBSERVED, channel_id=2),
            _event(role, 4, kinds.SAMPLE_RATE_OBSERVED, numeric_value=12_000.0),
            _event(
                role,
                5,
                kinds.IQ_FRAME_OBSERVED,
                artifact_hash=DIGEST,
                sequence=8,
            ),
            _event(role, 6, kinds.MOD_IQ_SENT),
        ),
    )

    assert (
        f257.assess_branch_wire(transcript).state
        is f257.BranchWireState.CONTROL_ORDER_INVALID
    )


def test_explicit_badp_rejection_wins_without_inferred_remote_cause() -> None:
    kinds = f257.WireEventKind
    role = "perturbed"
    transcript = f257.WireTranscript(
        role,
        (
            _event(role, 0, kinds.WEBSOCKET_OPENED),
            _event(role, 1, kinds.AUTH_SENT_REDACTED),
            _event(role, 2, kinds.BADP_REJECTION_OBSERVED, numeric_value=5.0),
            _event(
                role,
                3,
                kinds.WEBSOCKET_CLOSE_OBSERVED,
                close_code=1000,
                artifact_hash=DIGEST,
            ),
        ),
    )

    branch = f257.assess_branch_wire(transcript)

    assert branch.state is f257.BranchWireState.SERVER_REJECTED
    assert "refusal or capacity" in branch.statement


def test_clean_close_and_typed_transport_loss_remain_distinct_and_incomplete() -> None:
    kinds = f257.WireEventKind
    prefix = (
        _event("reference", 0, kinds.WEBSOCKET_OPENED),
        _event("reference", 1, kinds.AUTH_SENT_REDACTED),
        _event("reference", 2, kinds.BADP_OK_OBSERVED),
    )
    clean = f257.WireTranscript(
        "reference",
        prefix
        + (
            _event(
                "reference",
                3,
                kinds.WEBSOCKET_CLOSE_OBSERVED,
                close_code=1000,
                artifact_hash=DIGEST,
            ),
        ),
    )
    loss = f257.WireTranscript(
        "reference",
        prefix
        + (
            _event(
                "reference",
                3,
                kinds.TRANSPORT_LOSS_OBSERVED,
                error_type="WebSocketConnectionClosedException",
            ),
        ),
    )

    assert clean.events[-1].kind is kinds.WEBSOCKET_CLOSE_OBSERVED
    assert loss.events[-1].kind is kinds.TRANSPORT_LOSS_OBSERVED
    assert f257.assess_branch_wire(clean).state is f257.BranchWireState.TERMINATED_WITHOUT_IQ
    assert f257.assess_branch_wire(loss).state is f257.BranchWireState.TERMINATED_WITHOUT_IQ


def test_terminal_event_must_end_the_transcript() -> None:
    kinds = f257.WireEventKind
    with pytest.raises(ValueError, match="final"):
        f257.WireTranscript(
            "reference",
            (
                _event("reference", 0, kinds.WEBSOCKET_OPENED),
                _event("reference", 1, kinds.AUTH_SENT_REDACTED),
                _event(
                    "reference",
                    2,
                    kinds.TRANSPORT_LOSS_OBSERVED,
                    error_type="ConnectionError",
                ),
                _event("reference", 3, kinds.BADP_OK_OBSERVED),
            ),
        )


def test_receipts_are_strict_json_and_have_no_raw_rf_surface() -> None:
    payload = {
        "gate": asdict(f257.assess_gate_f2_5_7()),
        "pair": asdict(
            f257.assess_pair_wire(
                _ready("reference", 3),
                _ready("perturbed", 6),
            )
        ),
    }
    encoded = json.dumps(strict_json_value(payload), allow_nan=False, sort_keys=True)

    assert "NaN" not in encoded and "Infinity" not in encoded
    for forbidden in ("samples", "waterfall", "password", "raw_msg", "raw_command"):
        assert forbidden not in encoded


def test_module_has_no_live_runtime_or_network_surface() -> None:
    source = Path(f257.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }

    assert not ({"socket", "requests", "websocket", "urllib"} & imported)
    assert "create_connection" not in source
    assert "run_live" not in source
    assert "_atomic_open_channel" not in source
    assert "kiwi_gate_f2_5_2" not in source
