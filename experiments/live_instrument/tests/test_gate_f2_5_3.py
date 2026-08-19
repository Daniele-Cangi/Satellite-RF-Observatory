"""Offline tests for Gate F2.5.3 structured control and receipt retention."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_2 as f252
from experiments.live_instrument import kiwi_gate_f2_5_3 as f253
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 16, 23, 0, tzinfo=timezone.utc)


def _phase(
    endpoint: kiwi.KiwiEndpoint,
    *,
    state: f25.F25PhaseState = f25.F25PhaseState.QUALIFICATION_ERROR,
    statement: str = "descriptive fixture",
    error_types: tuple[str, ...] = ("TimeoutError",),
    atomic: tuple[object, ...] = (),
) -> f25.PhaseReceipt:
    return f25.PhaseReceipt(
        f"{endpoint.host.lower()}:{endpoint.port}",
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        state,
        NOW,
        NOW,
        statement,
        ("a" * 64,),
        (("direct_second_channel_attempt", "COMPLETED"),),
        None,
        True,
        True,
        False,
        False,
        atomic,
        error_types,
    )


def _decision_signature(result: f25.F25Result) -> tuple[object, ...]:
    return (
        result.outcome,
        tuple((item.endpoint_identity, item.phase, item.state) for item in result.phase_receipts),
        result.authorised_claims,
        result.unauthorised_claims,
    )


def _failed_branch(
    role: str,
    state: f252.BranchOpenState,
    error_type: str,
) -> f252.BranchOpenReceipt:
    return f252.BranchOpenReceipt(
        endpoint_identity="fixture.invalid:8073",
        role=role,
        state=state,
        started_at=NOW,
        completed_at=NOW,
        attempted=True,
        websocket_opened=False,
        handshake_message_count=0,
        handshake_hash=None,
        configuration_sent=False,
        sample_rate_hz=None,
        channel_id=None,
        channel_id_basis=None,
        iq_frame_count=0,
        iq_raw_bytes=0,
        iq_stream_artifact_hash=None,
        readiness_frame_artifact_hash=None,
        readiness_event_start=None,
        readiness_event_end=None,
        readiness_sequence=None,
        readiness_gps_solution_age_s=None,
        error_type=error_type,
        error_message="fixture branch failure",
        error_description_hash=("1" if role == "reference" else "2") * 64,
        pair_disposition=f252.PairDisposition.CLOSED_ON_BRANCH_FAILURE,
    )


def test_bootstrap_freezes_parent_control_and_strict_receipt_policy() -> None:
    receipt = f253.build_bootstrap_receipt(runtime_commit="a" * 40, created_at=NOW)
    value = strict_json_value(receipt)
    json.dumps(value, allow_nan=False)
    assert receipt.parent_runtime_commit == f253.PARENT_RUNTIME_COMMIT
    assert receipt.parent_outcome_commit == f253.PARENT_OUTCOME_COMMIT
    assert receipt.retry_budget == f24.RETRY_BUDGET == 2
    assert receipt.retry_basis == "ATOMIC_BRANCH_STATE_AND_TYPED_ERROR_ONLY"
    assert receipt.raw_rf_persistence == "ZERO"
    assert receipt.receipt_artifact_maximum_bytes == f253.MAX_RECEIPT_ARTIFACT_BYTES


def test_structured_retry_ignores_aggregate_prose_and_requires_typed_error() -> None:
    endpoint = f24.ordered_candidates()[0]
    prose_only = _phase(endpoint, statement="connection timeout closed", error_types=())
    typed = _phase(endpoint, statement="words deliberately carry no retry hint", error_types=("TimeoutError",))
    rejected = _phase(
        endpoint,
        state=f25.F25PhaseState.UNSATISFIED,
        statement="TimeoutError is merely descriptive here",
        error_types=("TimeoutError",),
    )
    unknown = _phase(endpoint, error_types=("FixtureSemanticError",))

    assert not f253.structured_retryable_phase(prose_only)
    assert f253.structured_retryable_phase(typed)
    assert not f253.structured_retryable_phase(rejected)
    assert not f253.structured_retryable_phase(unknown)


def test_atomic_branch_state_is_the_retry_authority() -> None:
    endpoint = f24.ordered_candidates()[0]
    base = _phase(endpoint, statement="atomic summary only", error_types=())
    transport = _failed_branch(
        "reference",
        f252.BranchOpenState.QUALIFICATION_ERROR,
        "TimeoutError",
    )
    refusal = _failed_branch(
        "perturbed",
        f252.BranchOpenState.CAPABILITY_REJECTED,
        "PermissionError",
    )
    decorated = f252._decorate_direct_result(base, (transport, refusal))
    assert isinstance(decorated, f25.PhaseReceipt)
    assert decorated.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert decorated.qualification_error_types == ("TimeoutError",)
    assert f253.structured_retryable_phase(decorated)

    only_refusals = f252._decorate_direct_result(
        base,
        (
            _failed_branch("reference", f252.BranchOpenState.CAPABILITY_REJECTED, "PermissionError"),
            refusal,
        ),
    )
    assert isinstance(only_refusals, f25.PhaseReceipt)
    assert only_refusals.state is f25.F25PhaseState.UNSATISFIED
    assert not f253.structured_retryable_phase(only_refusals)


def test_runner_materialises_exact_global_and_per_endpoint_retry_budget() -> None:
    calls: dict[str, int] = {}
    events: list[tuple[str, object]] = []

    def qualifier(endpoint: kiwi.KiwiEndpoint, _mother: f2.MotherPlan) -> f25.PhaseReceipt:
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        calls[identity] = calls.get(identity, 0) + 1
        return _phase(endpoint, statement="no text hint", error_types=("ConnectionError",))

    bootstrap = f253.build_bootstrap_receipt(runtime_commit="b" * 40, created_at=NOW)
    result = f25.run_once(
        runtime_commit="b" * 40,
        bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
        direct_qualifier=qualifier,
        retry_selector=f253.structured_retryable_phase,
        event_emitter=lambda event, payload: events.append((event, payload)),
        event_prefix="fixture",
    )

    ordered = f24.ordered_candidate_identities()
    assert tuple(calls) == ordered
    assert tuple(calls.values()) == (2, 2) + (1,) * (len(ordered) - 2)
    assert sum(value - 1 for value in calls.values()) == f24.RETRY_BUDGET
    assert max(calls.values()) - 1 == f24.MAX_RETRY_PER_ENDPOINT
    retries = [payload for event, payload in events if event == "fixture_prefreeze_retry"]
    assert len(retries) == 2
    assert result.outcome is f25.F25Outcome.QUALIFICATION_INCOMPLETE


def test_bounded_artifact_is_strict_jsonl_receipts_and_hashes_only(tmp_path: Path) -> None:
    path = tmp_path / "session.jsonl"
    emitter = f253.SafeReceiptEmitter(path, mirror_sink=None)
    emitter("gate_fixture_receipt", {"receipt_hash": "a" * 64, "state": "READY"})
    emitter("gate_fixture_numeric", {"value": float("nan")})
    receipt = emitter.finalize()

    assert receipt.state is f253.ReceiptArtifactState.COMPLETE
    assert receipt.raw_rf_persistence == "ZERO"
    assert receipt.physical_decision_affected is False
    assert receipt.line_count == 2
    assert receipt.byte_count == path.stat().st_size
    assert receipt.artifact_hash is not None
    lines = path.read_text(encoding="utf-8").splitlines()
    documents = [json.loads(line, parse_constant=lambda value: pytest.fail(value)) for line in lines]
    assert documents[1]["payload"]["value"] == {"numeric_state": "NOT_A_NUMBER"}
    serialized = path.read_text(encoding="utf-8").lower()
    assert not any(f'"{key}"' in serialized for key in f253.FORBIDDEN_RF_KEYS)


@pytest.mark.parametrize(
    "payload",
    (
        {"samples": [1, 2]},
        {"raw_frame": "not-even-real-rf"},
        {"receipt": {"stft": [[1.0]]}},
        {"value": np.array([1.0, 2.0])},
    ),
)
def test_rf_or_array_payload_is_refused_descriptively(tmp_path: Path, payload: object) -> None:
    path = tmp_path / f"refused-{len(list(tmp_path.iterdir()))}.jsonl"
    emitter = f253.SafeReceiptEmitter(path, mirror_sink=None)
    emitter("forbidden_fixture", payload)
    receipt = emitter.finalize()
    assert receipt.state is f253.ReceiptArtifactState.DESCRIPTIVE_ERROR
    assert receipt.line_count == 0
    assert receipt.physical_decision_affected is False
    assert path.read_bytes() == b""


def test_sink_and_serialization_failures_cannot_change_physical_decision(tmp_path: Path) -> None:
    def run(*, invalid_atomic: bool, mirror_failure: bool, name: str) -> f25.F25Result:
        def qualifier(endpoint: kiwi.KiwiEndpoint, _mother: f2.MotherPlan) -> f25.PhaseReceipt:
            atomic = (np.array([1.0]),) if invalid_atomic else ()
            return _phase(endpoint, error_types=("FixtureSemanticError",), atomic=atomic)

        def mirror(_line: str) -> None:
            if mirror_failure:
                raise OSError("fixture mirror unavailable")

        emitter = f253.SafeReceiptEmitter(tmp_path / f"{name}.jsonl", mirror_sink=mirror)
        bootstrap = f253.build_bootstrap_receipt(runtime_commit="c" * 40, created_at=NOW)
        result = f25.run_once(
            runtime_commit="c" * 40,
            bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
            direct_qualifier=qualifier,
            retry_selector=f253.structured_retryable_phase,
            event_emitter=emitter,
        )
        artifact = emitter.finalize()
        if invalid_atomic or mirror_failure:
            assert artifact.state is f253.ReceiptArtifactState.DESCRIPTIVE_ERROR
            assert artifact.physical_decision_affected is False
        return result

    baseline = run(invalid_atomic=False, mirror_failure=False, name="baseline")
    failed = run(invalid_atomic=True, mirror_failure=True, name="failed")
    assert _decision_signature(failed) == _decision_signature(baseline)


def test_bounded_sink_failure_is_descriptive_and_never_exceeds_cap(tmp_path: Path) -> None:
    path = tmp_path / "bounded.jsonl"
    emitter = f253.SafeReceiptEmitter(path, maximum_bytes=96, mirror_sink=None)
    emitter("oversized", {"receipt_hash": "a" * 256})
    receipt = emitter.finalize()
    assert receipt.state is f253.ReceiptArtifactState.DESCRIPTIVE_ERROR
    assert receipt.byte_count <= 96
    assert receipt.physical_decision_affected is False


def test_existing_receipt_path_is_not_overwritten_or_claimed(tmp_path: Path) -> None:
    path = tmp_path / "existing.jsonl"
    path.write_text('{"preexisting":true}\n', encoding="utf-8")
    before = path.read_bytes()
    emitter = f253.SafeReceiptEmitter(path, mirror_sink=None)
    emitter("new", {"receipt_hash": "b" * 64})
    receipt = emitter.finalize()
    assert receipt.state is f253.ReceiptArtifactState.DESCRIPTIVE_ERROR
    assert receipt.artifact_hash is None
    assert path.read_bytes() == before


def test_module_has_no_import_time_network_or_rf_persistence_surface() -> None:
    source = Path(f253.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    assert top_level_calls == []
    assert "write_bytes" not in source
    assert "write_text" not in source
    assert "np.save" not in source
    assert "waterfall" not in source.lower().replace('"waterfall"', "")
