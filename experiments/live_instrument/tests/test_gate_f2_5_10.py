"""Offline tests for Gate F2.5.10 exact execution-envelope review."""

from __future__ import annotations

import ast
from dataclasses import replace
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_1 as f251
from experiments.live_instrument import kiwi_gate_f2_5_9 as f259
from experiments.live_instrument import kiwi_gate_f2_5_10 as f2510
from experiments.live_instrument.models import strict_json_value


def test_execution_envelope_freezes_all_pre_live_control_dimensions() -> None:
    envelope = f2510.build_execution_envelope()
    mother = f2.MotherPlan()

    json.dumps(strict_json_value(envelope), allow_nan=False)
    assert envelope.reviewed_physical_runtime_commit == f2510.REVIEWED_PHYSICAL_RUNTIME_COMMIT
    assert envelope.mother_plan_hash == mother.plan_hash
    assert envelope.candidate_set_hash == f24.candidate_set_hash()
    assert envelope.candidate_order == f24.ordered_candidate_identities()
    assert envelope.qualification_budget_s == 420.0
    assert envelope.retry_budget == 2
    assert envelope.maximum_retry_per_endpoint == 1
    assert envelope.maximum_candidate_attempts == 8
    assert envelope.endpoints_in_parallel == 1
    assert envelope.simultaneous_snd_slots == 2
    assert envelope.websocket_connect_timeout_s == 8.0
    assert envelope.ordered_control_deadline_s == 12.0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.raw_rf_persistence == "ZERO"
    assert envelope.stop_condition == "FIRST_OUTCOME_THEN_CLOSE"


def test_capture_dwell_separates_prefreeze_and_confirmation() -> None:
    envelope = f2510.build_execution_envelope()

    assert envelope.topology_duration_s == 1.5
    assert envelope.discovery_duration_s == 4.0
    assert envelope.retune_qualification_duration_s == pytest.approx(9.1)
    assert envelope.prefreeze_capture_duration_s == pytest.approx(14.6)
    assert envelope.confirmation_duration_s == pytest.approx(10.6)
    assert envelope.maximum_admitted_capture_duration_s == pytest.approx(25.2)


def test_bootstrap_centers_are_exact_targetless_endpoint_coordinates() -> None:
    envelope = f2510.build_execution_envelope()
    candidates = f24.ordered_candidates()

    assert tuple(identity for identity, _center in envelope.bootstrap_centers_hz) == (
        f24.ordered_candidate_identities()
    )
    assert tuple(center for _identity, center in envelope.bootstrap_centers_hz) == tuple(
        f251.bootstrap_center(endpoint, {}) for endpoint in candidates
    )
    assert tuple(center for _identity, center in envelope.bootstrap_centers_hz) == tuple(
        f251.bootstrap_center(endpoint, {"bandwidth": "1", "ext_api": "99"})
        for endpoint in candidates
    )


def test_envelope_rejects_threshold_duration_or_persistence_drift() -> None:
    envelope = f2510.build_execution_envelope()

    with pytest.raises(ValueError, match="MotherPlan"):
        replace(envelope, mother_plan_hash="0" * 64)
    with pytest.raises(ValueError, match="capture duration"):
        replace(envelope, confirmation_duration_s=11.0)
    with pytest.raises(ValueError, match="RF persistence"):
        replace(envelope, raw_rf_persistence="SAMPLES")
    with pytest.raises(ValueError, match="post-freeze retry"):
        replace(envelope, postfreeze_retry_budget=1)


def test_real_offline_guards_match_reviewed_sources_and_environment() -> None:
    assert f2510.current_environment() == f2510.EXPECTED_ENVIRONMENT
    assert f2510.causal_sources_unchanged()
    assert Path.cwd().resolve() == f2510._repository_root()


def test_assessment_is_ready_but_does_not_authorise_live() -> None:
    assessment = f2510.assess_gate_f2_5_10()

    assert assessment.exit is (
        f2510.F2510Exit.REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.ordered_runner_prerequisite_satisfied
    assert assessment.causal_sources_unchanged
    assert assessment.numerical_environment_unchanged
    assert assessment.caller_overrides_removed
    assert assessment.working_directory_is_repository_root
    assert assessment.one_outcome_stop_preserved
    assert not assessment.live_execution_authorised
    assert assessment.blockers == ()


def test_any_guard_failure_blocks_before_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(f2510, "causal_sources_unchanged", lambda: False)
    assessment = f2510.assess_gate_f2_5_10()

    assert assessment.exit is f2510.F2510Exit.EXECUTION_ENVELOPE_MISMATCH
    assert assessment.blockers == ("reviewed causal source files changed",)
    assert not assessment.live_execution_authorised

    prior = replace(
        f259.assess_gate_f2_5_9(),
        exit=f259.F259Exit.ORDERED_RECEIPT_PREREQUISITE_FAILED,
        ordered_opener_is_active=False,
    )
    blocked = f2510.assess_gate_f2_5_10(prior)
    assert "ordered F2.5.9 runner prerequisite failed" in blocked.blockers


def test_unauthorised_shim_refuses_before_assessment_or_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        f2510,
        "assess_gate_f2_5_10",
        lambda: pytest.fail("assessment must not run without authority"),
    )
    monkeypatch.setattr(
        f2510.f25,
        "run_once",
        lambda **_kwargs: pytest.fail("runtime must not run without authority"),
    )

    with pytest.raises(PermissionError, match="separate live authorisation"):
        f2510.run_reviewed_once()


def test_authorised_shim_has_no_plan_path_commit_or_retry_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    artifact = object()
    captured: dict[str, object] = {}
    events: list[tuple[str, object]] = []
    finalized: list[bool] = []
    envelope = f2510.build_execution_envelope()
    ready = SimpleNamespace(
        exit=f2510.F2510Exit.REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY,
        blockers=(),
        envelope=envelope,
    )

    def fake_runtime(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    class FakeEmitter:
        def __init__(self, _path: Path) -> None:
            pass

        def __call__(self, event: str, payload: object) -> None:
            events.append((event, payload))

        def record_runtime_error(self, _error: BaseException) -> None:
            pytest.fail("successful fixture cannot record runtime error")

        def finalize(self) -> object:
            finalized.append(True)
            return artifact

    monkeypatch.setattr(f2510, "assess_gate_f2_5_10", lambda: ready)
    monkeypatch.setattr(f2510.f22, "runtime_commit", lambda: "c" * 40)
    monkeypatch.setattr(f2510.f2531, "TerminalReceiptEmitter", FakeEmitter)
    monkeypatch.setattr(f2510.f25, "run_once", fake_runtime)
    result = f2510.run_reviewed_once(live_authorised=True)

    assert result.physical_result is sentinel
    assert result.receipt_artifact is artifact
    assert set(captured) == {
        "mother",
        "runtime_commit",
        "bootstrap_receipt",
        "direct_qualifier",
        "event_prefix",
        "terminal_instrument",
        "retry_selector",
        "event_emitter",
    }
    assert isinstance(captured["mother"], f2.MotherPlan)
    assert captured["mother"].plan_hash == f2.MotherPlan().plan_hash
    assert captured["runtime_commit"] == "c" * 40
    assert captured["direct_qualifier"] is f259.direct_ordered_snd_qualification
    assert captured["retry_selector"] is f259.ordered_retryable_phase
    assert captured["event_prefix"] == f2510.EVENT_PREFIX
    assert captured["terminal_instrument"] == f2510.TERMINAL_INSTRUMENT
    assert events[0][0] == "gate_f2_5_10_execution_envelope_frozen"
    payload = events[0][1]
    assert isinstance(payload, dict)
    assert payload["envelope"] is envelope
    assert payload["envelope_hash"] == envelope.receipt_hash
    assert finalized == [True]
    signature = inspect.signature(f2510.run_reviewed_once)
    assert tuple(signature.parameters) == ("live_authorised",)


def test_authorised_shim_still_fails_closed_if_review_drifted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = SimpleNamespace(
        exit=f2510.F2510Exit.EXECUTION_ENVELOPE_MISMATCH,
        blockers=("fixture drift",),
    )
    monkeypatch.setattr(f2510, "assess_gate_f2_5_10", lambda: blocked)
    monkeypatch.setattr(
        f2510.f25,
        "run_once",
        lambda **_kwargs: pytest.fail("mismatched runtime must not execute"),
    )

    with pytest.raises(RuntimeError, match="fixture drift"):
        f2510.run_reviewed_once(live_authorised=True)


def test_runtime_exception_is_recorded_and_terminal_emitter_is_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = f2510.build_execution_envelope()
    ready = SimpleNamespace(
        exit=f2510.F2510Exit.REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY,
        blockers=(),
        envelope=envelope,
    )
    recorded: list[BaseException] = []
    finalized: list[bool] = []

    class FakeEmitter:
        def __init__(self, _path: Path) -> None:
            pass

        def __call__(self, _event: str, _payload: object) -> None:
            pass

        def record_runtime_error(self, error: BaseException) -> None:
            recorded.append(error)

        def finalize(self) -> object:
            finalized.append(True)
            return object()

    monkeypatch.setattr(f2510, "assess_gate_f2_5_10", lambda: ready)
    monkeypatch.setattr(f2510.f22, "runtime_commit", lambda: "d" * 40)
    monkeypatch.setattr(f2510.f2531, "TerminalReceiptEmitter", FakeEmitter)
    monkeypatch.setattr(
        f2510.f25,
        "run_once",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("fixture failure")),
    )

    with pytest.raises(RuntimeError, match="fixture failure"):
        f2510.run_reviewed_once(live_authorised=True)

    assert len(recorded) == 1
    assert isinstance(recorded[0], RuntimeError)
    assert finalized == [True]


def test_module_adds_no_endpoint_cli_or_network_implementation() -> None:
    source = Path(f2510.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    defined = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert top_level_calls == []
    assert "main" not in defined
    assert "run_live" not in defined
    assert "KiwiEndpoint(" not in source
    assert "create_connection" not in source
    assert "urlopen" not in source
    assert "_open_channel" not in source
    assert "_capture_dual" not in source
