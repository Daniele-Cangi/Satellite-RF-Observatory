"""Offline tests for Gate F2.5.9 ordered one-shot materialisation."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_2 as f252
from experiments.live_instrument import kiwi_gate_f2_5_3_1 as f2531
from experiments.live_instrument import kiwi_gate_f2_5_7 as f257
from experiments.live_instrument import kiwi_gate_f2_5_8 as f258
from experiments.live_instrument import kiwi_gate_f2_5_9 as f259
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 17, 18, 0, tzinfo=timezone.utc)
DIGEST = "a" * 64
ENDPOINT = kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073)


def _ready_transcript(role: str, channel: int) -> f257.WireTranscript:
    kinds = f257.WireEventKind

    def event(ordinal: int, kind: f257.WireEventKind, **kwargs: object) -> f257.WireEvent:
        return f257.WireEvent(role, ordinal, ordinal, kind, **kwargs)

    return f257.WireTranscript(
        role,
        (
            event(0, kinds.WEBSOCKET_OPENED),
            event(1, kinds.AUTH_SENT_REDACTED),
            event(2, kinds.CHANNEL_ALLOCATED_OBSERVED, channel_id=channel),
            event(3, kinds.BADP_OK_OBSERVED),
            event(4, kinds.SAMPLE_RATE_OBSERVED, numeric_value=1000.0),
            event(5, kinds.MOD_IQ_SENT),
            event(6, kinds.IQ_FRAME_OBSERVED, artifact_hash=DIGEST, sequence=17),
        ),
    )


def _ready_receipt(
    role: str,
    channel: int,
    *,
    disposition: f252.PairDisposition = f252.PairDisposition.ADMITTED_TO_PAIR,
) -> f258.F258BranchReceipt:
    transcript = _ready_transcript(role, channel)
    return f258.F258BranchReceipt(
        "fixture.invalid:8073",
        role,
        f258.F258BranchState.READY,
        NOW,
        NOW + timedelta(seconds=1),
        transcript,
        f257.assess_branch_wire(transcript),
        1,
        20,
        DIGEST,
        (DIGEST,),
        (DIGEST,),
        DIGEST,
        NOW,
        NOW + timedelta(seconds=0.1),
        17,
        1,
        None,
        None,
        disposition,
    )


def _failed_receipt(
    role: str,
    state: f258.F258BranchState,
    error_type: str,
) -> f258.F258BranchReceipt:
    return f258.F258BranchReceipt(
        "fixture.invalid:8073",
        role,
        state,
        NOW,
        NOW + timedelta(seconds=1),
        None,
        None,
        0,
        0,
        None,
        (),
        (),
        None,
        None,
        None,
        None,
        None,
        error_type,
        DIGEST,
        f252.PairDisposition.CLOSED_ON_BRANCH_FAILURE,
    )


def _phase(
    *,
    state: f25.F25PhaseState = f25.F25PhaseState.QUALIFICATION_ERROR,
    error_types: tuple[str, ...] = (),
) -> f25.PhaseReceipt:
    return f25.PhaseReceipt(
        "fixture.invalid:8073",
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        state,
        NOW,
        NOW,
        "fixture aggregate result",
        (),
        (("direct_second_channel_attempt", "COMPLETED"),),
        qualification_error_types=error_types,
    )


def test_bootstrap_binds_ordered_active_path_without_weakening_history() -> None:
    receipt = f259.build_bootstrap_receipt(runtime_commit="b" * 40, created_at=NOW)
    json.dumps(strict_json_value(receipt), allow_nan=False)

    assert receipt.parent_gate_commit == f259.PARENT_GATE_COMMIT
    assert receipt.active_branch_receipt_transform == f258.F258_TRANSFORM_VERSION
    assert receipt.active_runner_transform == f259.F259_TRANSFORM_VERSION
    assert receipt.ordered_branch_opener_required
    assert not receipt.legacy_branch_opener_enabled
    assert receipt.retry_budget == f24.RETRY_BUDGET
    assert receipt.terminal_manifest_required
    assert receipt.raw_rf_persistence == "ZERO"


def test_direct_qualification_injects_only_ordered_opener(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipts = (_ready_receipt("reference", 3), _ready_receipt("perturbed", 6))
    sentinel_dual = object()
    observed: dict[str, object] = {}

    def ordered(*args: object) -> tuple[object, tuple[f258.F258BranchReceipt, ...]]:
        observed["ordered_args"] = args
        return sentinel_dual, receipts

    def legacy(*_args: object) -> object:
        raise AssertionError("legacy opener was reachable")

    def parent(
        endpoint: kiwi.KiwiEndpoint,
        mother: f2.MotherPlan,
        *,
        center_resolver: object,
        dual_opener: object,
    ) -> f25.PhaseReceipt:
        assert callable(center_resolver) and callable(dual_opener)
        center = center_resolver(endpoint, {})
        observed["center"] = center
        assert dual_opener(endpoint, center, {}, mother) is sentinel_dual
        return _phase(state=f25.F25PhaseState.SATISFIED)

    monkeypatch.setattr(f258, "_open_dual_ordered", ordered)
    monkeypatch.setattr(f252, "_atomic_open_dual", legacy)
    monkeypatch.setattr(f25, "direct_dual_snd_qualification", parent)

    result = f259.direct_ordered_snd_qualification(ENDPOINT, f2.MotherPlan())

    assert isinstance(result, f25.PhaseReceipt)
    assert result.state is f25.F25PhaseState.SATISFIED
    assert result.direct_reference_opened and result.direct_perturbed_opened
    assert result.atomic_branch_receipts == receipts
    assert observed["ordered_args"]


def test_ordered_failure_semantics_override_aggregate_exception_prose() -> None:
    timeout = _failed_receipt(
        "reference",
        f258.F258BranchState.QUALIFICATION_ERROR,
        "TimeoutError",
    )
    rejected = _failed_receipt(
        "perturbed",
        f258.F258BranchState.CAPABILITY_REJECTED,
        "BranchCapabilityRejected",
    )
    result = f259._decorate_ordered_result(
        _phase(error_types=("OrderedDualOpenError",)),
        (timeout, rejected),
    )

    assert isinstance(result, f25.PhaseReceipt)
    assert result.state is f25.F25PhaseState.QUALIFICATION_ERROR
    assert result.qualification_error_types[-1] == "TimeoutError"
    assert f259.ordered_retryable_phase(result)

    physical_rejection = f259._decorate_ordered_result(
        _phase(error_types=("OrderedDualOpenError",)),
        (
            _failed_receipt(
                "reference",
                f258.F258BranchState.CAPABILITY_REJECTED,
                "BranchCapabilityRejected",
            ),
            _failed_receipt(
                "perturbed",
                f258.F258BranchState.CAPABILITY_REJECTED,
                "BranchCapabilityRejected",
            ),
        ),
    )
    assert isinstance(physical_rejection, f25.PhaseReceipt)
    assert physical_rejection.state is f25.F25PhaseState.UNSATISFIED
    assert not f259.ordered_retryable_phase(physical_rejection)


def test_same_channel_topology_is_unsatisfied_not_software_error() -> None:
    receipts = (
        _ready_receipt(
            "reference",
            3,
            disposition=f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION,
        ),
        _ready_receipt(
            "perturbed",
            3,
            disposition=f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION,
        ),
    )
    result = f259._decorate_ordered_result(_phase(), receipts)

    assert isinstance(result, f25.PhaseReceipt)
    assert result.state is f25.F25PhaseState.UNSATISFIED
    assert result.direct_reference_opened and result.direct_perturbed_opened
    assert not f259.ordered_retryable_phase(result)


def test_nonretryable_ordered_description_cannot_consume_retry() -> None:
    malformed = _failed_receipt(
        "reference",
        f258.F258BranchState.QUALIFICATION_ERROR,
        "ValueError",
    )
    peer = _failed_receipt(
        "perturbed",
        f258.F258BranchState.QUALIFICATION_ERROR,
        "ValueError",
    )
    result = f259._decorate_ordered_result(_phase(), (malformed, peer))

    assert isinstance(result, f25.PhaseReceipt)
    assert not f259.ordered_retryable_phase(result)


def test_unauthorised_run_refuses_before_receipt_or_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "must-not-exist.jsonl"
    monkeypatch.setattr(
        f259.f25,
        "run_once",
        lambda **_kwargs: pytest.fail("physical runtime must not be entered"),
    )

    with pytest.raises(PermissionError, match="separate authorisation"):
        f259.run_once(receipt_path=path, mirror_sink=None)

    assert not path.exists()


def test_authorised_materialisation_preserves_injection_and_terminal_closure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "ordered.jsonl"
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_runtime(**kwargs: object) -> object:
        captured.update(kwargs)
        emitter = kwargs["event_emitter"]
        assert callable(emitter)
        emitter("gate_f2_5_9_fixture", {"artifact_hash": DIGEST})
        return sentinel

    monkeypatch.setattr(f259.f25, "run_once", fake_runtime)
    result = f259.run_once(
        live_authorised=True,
        runtime_commit="c" * 40,
        receipt_path=path,
        mirror_sink=None,
    )

    assert result.physical_result is sentinel
    assert captured["direct_qualifier"] is f259.direct_ordered_snd_qualification
    assert captured["retry_selector"] is f259.ordered_retryable_phase
    assert captured["event_prefix"] == f259.EVENT_PREFIX
    assert captured["terminal_instrument"] == f259.TERMINAL_INSTRUMENT
    assert result.receipt_artifact.state is f2531.RetentionState.COMPLETE
    assert result.receipt_artifact.terminal_manifest_written
    documents = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert documents[-1]["event"] == f2531.TERMINAL_EVENT


def test_runtime_failure_still_closes_ordered_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "failed.jsonl"

    def fail(**kwargs: object) -> object:
        emitter = kwargs["event_emitter"]
        assert callable(emitter)
        emitter("gate_f2_5_9_before_failure", {"artifact_hash": DIGEST})
        raise RuntimeError("synthetic runtime failure")

    monkeypatch.setattr(f259.f25, "run_once", fail)
    with pytest.raises(RuntimeError, match="synthetic runtime failure"):
        f259.run_once(
            live_authorised=True,
            runtime_commit="d" * 40,
            receipt_path=path,
            mirror_sink=None,
        )

    documents = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    terminal = documents[-1]
    assert terminal["event"] == f2531.TERMINAL_EVENT
    assert terminal["payload"]["state"] == f2531.RetentionState.DESCRIPTIVE_ERROR.value


def test_assessment_authorises_review_not_live_execution() -> None:
    assessment = f259.assess_gate_f2_5_9()

    assert assessment.exit is f259.F259Exit.ORDERED_ONE_SHOT_RUNNER_MATERIALIZED
    assert assessment.ordered_opener_is_active
    assert assessment.legacy_opener_is_unreachable
    assert assessment.typed_retry_is_ordered_receipt_aware
    assert assessment.terminal_receipt_closure_preserved
    assert assessment.one_outcome_stop_preserved
    assert not assessment.live_execution_authorised

    failed_prior = replace(
        f258.assess_gate_f2_5_8(),
        exit=f258.F258Exit.SERVER_WIRE_PREREQUISITE_FAILED,
        receipt_implementation_complete=False,
    )
    blocked = f259.assess_gate_f2_5_9(failed_prior)
    assert blocked.exit is f259.F259Exit.ORDERED_RECEIPT_PREREQUISITE_FAILED
    assert not blocked.live_execution_authorised


def test_module_has_no_legacy_opener_cli_or_import_time_io() -> None:
    source = Path(f259.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    attribute_names = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }

    assert top_level_calls == []
    assert "_atomic_open_dual" not in attribute_names
    assert "if __name__" not in source
    assert "def main" not in source
    assert "write_bytes" not in source
    assert "write_text" not in source
