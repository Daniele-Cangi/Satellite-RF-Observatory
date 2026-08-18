"""Offline post-commit seal tests for Gate F2.5.25."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.live_instrument import kiwi_gate_f2_5_23 as f2523
from experiments.live_instrument import kiwi_gate_f2_5_24 as f2524
from experiments.live_instrument import kiwi_gate_f2_5_25 as f2525
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 18, 18, 30, tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class _SyntheticPlan:
    plan_hash: str = "a" * 64
    center_a_hz: float = 10_000_000.0
    delta_hz: float = 1_000.0
    confirmation_event_not_before: datetime = NOW


class _Branch:
    def __init__(self, commands: list[object]) -> None:
        self.command_ledger = commands


class _Dual:
    def __init__(self) -> None:
        self.reference = _Branch(["diagnostic-reference"])
        self.perturbed = _Branch(["diagnostic-B", "diagnostic-A2"])


class _Context:
    def __init__(self, *, close_fails: bool = False) -> None:
        self.dual = _Dual()
        self.closed = False
        self.close_fails = close_fails

    def close(self) -> None:
        self.closed = True
        if self.close_fails:
            raise OSError("synthetic close failure")


def _direct_receipt(state: str = "SATISFIED") -> f2523.PhaseReceipt:
    return f2523.PhaseReceipt(
        "DIRECT_DUAL_SND_QUALIFICATION",
        state,
        "synthetic direct-SND receipt",
        ("b" * 64,),
        (("synthetic", "TRUE"),),
    )


def _blocked_prefreeze() -> f2523.F2523Result:
    direct = _direct_receipt("UNSATISFIED")
    return f2523.F2523Result(
        f2523.build_envelope(),
        f2523.MaterializationOutcome.QUALIFICATION_INCOMPLETE.value,
        (direct,) + f2523._not_evaluated(direct.phase),
        None,
        ("synthetic topology did not admit discovery",),
        ("target evaluated",),
    )


def _planned_prefreeze(plan: object) -> f2523.F2523Result:
    phases = (
        _direct_receipt(),
        f2523.PhaseReceipt(
            "ONE_TARGET_DISCOVERY",
            "SATISFIED",
            "synthetic target",
            ("c" * 64, "d" * 64),
            (),
        ),
        f2523.PhaseReceipt(
            "DISTRIBUTED_RETUNE_QUALIFICATION",
            "SATISFIED",
            "synthetic witness",
            tuple(chr(101 + index) * 64 for index in range(6)),
            (("target_evaluated", "FALSE"),),
        ),
        f2523.PhaseReceipt(
            "PLAN_FREEZE",
            "SATISFIED",
            "synthetic freeze",
            ("a" * 64,),
            (("plan_hash", "a" * 64),),
        ),
        f2523.PhaseReceipt(
            "ONE_CONFIRMATION",
            "NOT_EVALUATED",
            "future confirmation",
            (),
            (),
        ),
    )
    return f2523.F2523Result(
        f2523.build_envelope(),
        f2523.MaterializationOutcome.PREFREEZE_PLAN_MATERIALIZED_OFFLINE.value,
        phases,
        plan,  # type: ignore[arg-type]
        ("synthetic plan frozen",),
        ("physical hypothesis evaluated",),
    )


def test_authority_envelope_binds_commit_scope_and_zero_retry() -> None:
    envelope = f2525.build_authority_envelope()

    assert envelope.reviewed_f2524_commit == f2525.REVIEWED_F2524_COMMIT
    assert envelope.reviewed_confirmation_surface_hash == (
        f2525.REVIEWED_CONFIRMATION_SURFACE_HASH
    )
    assert envelope.reviewed_live_surface_hash == f2525.REVIEWED_LIVE_SURFACE_HASH
    assert envelope.receipt_hash == f2525.AUTHORITY_ENVELOPE_HASH
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.confirmation_windows == 1
    assert envelope.prefreeze_retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.channel_lifetime == "OPEN_FROM_REQUALIFICATION_THROUGH_CONFIRMATION"
    assert envelope.command_ledger_boundary == (
        "CLEAR_AFTER_WITNESS_QUALIFICATION_BEFORE_CONFIRMATION"
    )
    assert envelope.waterfall_role == "ABSENT_FROM_CAUSAL_PATH"
    assert envelope.ext_api_role == "DESCRIPTIVE_HINT_UNUSED"
    assert envelope.raw_rf_persistence == "ZERO"


def test_causal_environment_and_live_surface_seals_match() -> None:
    assessment = f2525.assess_gate_f2_5_25()

    assert assessment.exit is (
        f2525.F2525Exit.EXACT_ONE_TARGET_CONFIRMATION_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.f2524_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.causal_git_diff_clean
    assert assessment.causal_source_hashes_match
    assert assessment.confirmation_surface_hash_matches
    assert assessment.live_surface_hash_matches
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.caller_overrides_removed
    assert assessment.same_session_lifetime_closed
    assert not assessment.live_execution_authorised
    assert assessment.blockers == ()
    assert f2525.current_causal_source_sha256() == (
        f2525.EXPECTED_CAUSAL_SOURCE_SHA256
    )
    assert f2525.current_environment() == f2525.EXPECTED_ENVIRONMENT
    assert f2525.current_live_surface_hash() == f2525.REVIEWED_LIVE_SURFACE_HASH


def test_public_surface_refuses_before_assessment_receipt_or_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_dir = f2525.default_receipt_path(NOW).parent
    before = tuple(path.name for path in receipt_dir.glob("gate-f2-5-25-*.jsonl"))

    def forbidden(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("work occurred before explicit authority")

    monkeypatch.setattr(f2525, "assess_gate_f2_5_25", forbidden)
    monkeypatch.setattr(f2525.websocket, "create_connection", forbidden)
    with pytest.raises(PermissionError, match="separate exact live"):
        f2525.run_reviewed_once()
    after = tuple(path.name for path in receipt_dir.glob("gate-f2-5-25-*.jsonl"))
    assert before == after


def test_blocked_prefreeze_stops_without_confirmation(tmp_path: Path) -> None:
    capture_calls = 0

    def prepare(sink: f2525.ReceiptSink) -> f2525._PreparedPrefreeze:
        sink("synthetic_control", {"state": "SATISFIED"})
        return f2525._PreparedPrefreeze(_blocked_prefreeze(), None, None)

    def forbidden_capture(*args: object) -> object:
        nonlocal capture_calls
        del args
        capture_calls += 1
        raise AssertionError("confirmation entered after blocked prefreeze")

    path = tmp_path / "blocked.jsonl"
    result = f2525._execute_reviewed(
        f2525.build_authority_envelope(),
        prepare_prefreeze=prepare,
        capture_confirmation=forbidden_capture,  # type: ignore[arg-type]
        evaluate_confirmation=lambda *_args, **_kwargs: None,
        receipt_path=path,
        mirror_sink=None,
    )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())

    assert capture_calls == 0
    assert result.confirmation is None
    assert result.authority_consumed
    assert result.raw_rf_persistence == "ZERO"
    assert documents[0]["event"] == "gate_f2_5_25_authority_envelope_frozen"
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"


def test_confirmation_starts_with_clean_ledger_and_closes_context(
    tmp_path: Path,
) -> None:
    context = _Context()
    plan = _SyntheticPlan()
    order: list[str] = []

    def prepare(_sink: f2525.ReceiptSink) -> f2525._PreparedPrefreeze:
        order.append("prepare")
        return f2525._PreparedPrefreeze(_planned_prefreeze(plan), context, None)  # type: ignore[arg-type]

    def capture(captured_context: object, captured_plan: object) -> object:
        order.append("capture")
        assert captured_context is context
        assert captured_plan is plan
        assert context.dual.reference.command_ledger == []
        assert context.dual.perturbed.command_ledger == []
        context.dual.perturbed.command_ledger.extend(["confirmation-B", "confirmation-A2"])
        return {"artifact_hashes": tuple(str(index) * 64 for index in range(1, 7))}

    confirmation = f2524.assess_gate_f2_5_24()

    def evaluate(captured_plan: object, artifacts: object, *, evaluated_at: datetime) -> object:
        order.append("evaluate")
        assert captured_plan is plan
        assert isinstance(artifacts, dict)
        assert evaluated_at.tzinfo is timezone.utc
        return confirmation

    path = tmp_path / "confirmation.jsonl"
    result = f2525._execute_reviewed(
        f2525.build_authority_envelope(),
        prepare_prefreeze=prepare,
        capture_confirmation=capture,  # type: ignore[arg-type]
        evaluate_confirmation=evaluate,
        receipt_path=path,
        mirror_sink=None,
    )
    documents = tuple(json.loads(line) for line in path.read_text().splitlines())

    assert order == ["prepare", "capture", "evaluate"]
    assert context.closed
    assert result.confirmation is confirmation
    assert documents[0]["event"] == "gate_f2_5_25_authority_envelope_frozen"
    assert any(
        item["event"] == "gate_f2_5_25_qualification_ledger_closed"
        and item["payload"]["reference_commands_removed"] == 1
        and item["payload"]["perturbed_commands_removed"] == 2
        for item in documents
    )
    assert documents[-1]["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"


def test_live_confirmation_capture_keeps_frozen_geometry_and_event_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = object()
    context = SimpleNamespace(dual=object())
    plan = _SyntheticPlan()
    observed: dict[str, object] = {}

    def capture(dual: object, **kwargs: object) -> object:
        observed["dual"] = dual
        observed.update(kwargs)
        return marker

    monkeypatch.setattr(f2525.f24, "_capture_dual", capture)
    result = f2525._capture_live_confirmation(context, plan)  # type: ignore[arg-type]

    assert result is marker
    assert observed["dual"] is context.dual
    assert observed["sequence"] is True
    assert observed["center_a_hz"] == plan.center_a_hz
    assert observed["delta_f_hz"] == plan.delta_hz
    assert observed["event_not_before"] == plan.confirmation_event_not_before


def test_close_description_error_cannot_replace_confirmation_decision(
    tmp_path: Path,
) -> None:
    context = _Context(close_fails=True)
    plan = _SyntheticPlan()
    confirmation = f2524.assess_gate_f2_5_24()

    result = f2525._execute_reviewed(
        f2525.build_authority_envelope(),
        prepare_prefreeze=lambda _sink: f2525._PreparedPrefreeze(
            _planned_prefreeze(plan),  # type: ignore[arg-type]
            context,  # type: ignore[arg-type]
            None,
        ),
        capture_confirmation=lambda *_args: {"artifact": "ephemeral"},  # type: ignore[arg-type]
        evaluate_confirmation=lambda *_args, **_kwargs: confirmation,
        receipt_path=tmp_path / "close-error.jsonl",
        mirror_sink=None,
    )

    assert context.closed
    assert result.confirmation is confirmation
    assert result.receipt_artifact.state.value == "DESCRIPTIVE_ERROR"
    assert result.receipt_artifact.error_count == 1


def test_seal_does_not_reuse_the_context_closing_offline_materializer() -> None:
    source = inspect.getsource(f2525._materialize_live_prefreeze)

    assert "materialize_prefreeze_injected" not in source
    assert "discover_one_target" in source
    assert "qualify_distributed_witness" in source
    assert "freeze_plan" in source


def test_public_signature_exposes_only_authority_bit() -> None:
    signature = inspect.signature(f2525.run_reviewed_once)
    parameters = tuple(signature.parameters.values())

    assert len(parameters) == 1
    assert parameters[0].name == "live_authorised"
    assert parameters[0].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters[0].default is False


def test_assessment_is_strict_metadata_and_contains_no_rf_arrays() -> None:
    assessment = f2525.assess_gate_f2_5_25()
    encoded = f2525.strict_json(assessment)

    strict_json_value(asdict(assessment))
    assert json.loads(encoded)["envelope"]["raw_rf_persistence"] == "ZERO"
    assert "samples" not in encoded.lower()
    assert "stft" not in encoded.lower()
    assert '"waterfall":' not in encoded.lower()
    assert "NaN" not in encoded and "Infinity" not in encoded
