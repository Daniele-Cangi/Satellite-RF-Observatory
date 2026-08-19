"""Offline tests for Gate F2.5.3.1 terminal receipt closure."""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5 as f25
from experiments.live_instrument import kiwi_gate_f2_5_3 as f253
from experiments.live_instrument import kiwi_gate_f2_5_3_1 as f2531
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 16, 23, 30, tzinfo=timezone.utc)


def _phase(endpoint: kiwi.KiwiEndpoint, *, invalid_atomic: bool = False) -> f25.PhaseReceipt:
    return f25.PhaseReceipt(
        f"{endpoint.host.lower()}:{endpoint.port}",
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        f25.F25PhaseState.QUALIFICATION_ERROR,
        NOW,
        NOW,
        "fixture semantic failure",
        ("a" * 64,),
        (("direct_second_channel_attempt", "COMPLETED"),),
        None,
        True,
        True,
        False,
        False,
        (np.array([1.0]),) if invalid_atomic else (),
        ("FixtureSemanticError",),
    )


def _terminal_document(path: Path) -> tuple[list[bytes], dict[str, object]]:
    lines = path.read_bytes().splitlines(keepends=True)
    document = json.loads(lines[-1])
    assert document["event"] == f2531.TERMINAL_EVENT
    return lines, document


def _decision_signature(result: f25.F25Result) -> tuple[object, ...]:
    return (
        result.outcome,
        tuple((item.endpoint_identity, item.phase, item.state) for item in result.phase_receipts),
        result.authorised_claims,
        result.unauthorised_claims,
    )


def test_bootstrap_binds_f253_and_terminal_closure_policy() -> None:
    receipt = f2531.build_bootstrap_receipt(runtime_commit="a" * 40, created_at=NOW)
    json.dumps(strict_json_value(receipt), allow_nan=False)
    assert receipt.parent_gate_commit == f2531.PARENT_GATE_COMMIT
    assert receipt.retry_budget == f24.RETRY_BUDGET
    assert receipt.terminal_manifest_required
    assert receipt.prefix_hash_required
    assert receipt.cli_close_receipt_required
    assert receipt.raw_rf_persistence == "ZERO"
    assert receipt.transform_versions[-1] == f2531.F2531_TRANSFORM_VERSION


def test_terminal_manifest_commits_to_every_preceding_line(tmp_path: Path) -> None:
    path = tmp_path / "complete.jsonl"
    emitter = f2531.TerminalReceiptEmitter(path, mirror_sink=None)
    emitter("receipt_one", {"receipt_hash": "1" * 64})
    emitter("receipt_two", {"artifact_hash": "2" * 64})
    receipt = emitter.finalize()

    lines, terminal = _terminal_document(path)
    prefix = b"".join(lines[:-1])
    payload = terminal["payload"]
    assert receipt.state is f2531.RetentionState.COMPLETE
    assert receipt.terminal_manifest_written
    assert receipt.retention_complete
    assert receipt.line_count == 3
    assert receipt.prefix_hash == sha256(prefix).hexdigest()
    assert payload["prefix_hash"] == receipt.prefix_hash
    assert payload["event_line_count"] == 2
    assert payload["event_byte_count"] == len(prefix)
    assert receipt.artifact_hash == sha256(path.read_bytes()).hexdigest()
    assert receipt.raw_rf_persistence == "ZERO"


def test_serialization_failure_is_visible_in_terminal_manifest(tmp_path: Path) -> None:
    path = tmp_path / "serialization.jsonl"
    emitter = f2531.TerminalReceiptEmitter(path, mirror_sink=None)
    emitter("invalid", {"samples": np.array([1.0, 2.0])})
    receipt = emitter.finalize()

    _lines, terminal = _terminal_document(path)
    payload = terminal["payload"]
    assert receipt.state is f2531.RetentionState.DESCRIPTIVE_ERROR
    assert receipt.error_count == 1
    assert receipt.retention_complete is False
    assert payload["retention_complete"] is False
    assert payload["error_count"] == 1
    assert any(value.startswith("SERIALIZATION_ERROR:") for value in payload["error_types"])
    assert payload["error_ledger_hash"] == receipt.error_ledger_hash


def test_mirror_failure_is_recorded_but_retained_artifact_is_complete(tmp_path: Path) -> None:
    path = tmp_path / "mirror.jsonl"

    def broken_mirror(_line: str) -> None:
        raise OSError("fixture stdout unavailable")

    emitter = f2531.TerminalReceiptEmitter(path, mirror_sink=broken_mirror)
    emitter("valid", {"receipt_hash": "3" * 64})
    receipt = emitter.finalize()
    _lines, terminal = _terminal_document(path)

    assert receipt.state is f2531.RetentionState.DESCRIPTIVE_ERROR
    assert receipt.retention_complete
    assert terminal["payload"]["retention_complete"] is True
    assert any(value.startswith("MIRROR_ERROR:") for value in receipt.error_types)


def test_terminal_reserve_survives_event_capacity_failure(tmp_path: Path) -> None:
    path = tmp_path / "bounded.jsonl"
    maximum = f2531.TERMINAL_RESERVE_BYTES + 2048
    emitter = f2531.TerminalReceiptEmitter(path, maximum_bytes=maximum, mirror_sink=None)
    emitter("too_large", {"description": "x" * 4096})
    receipt = emitter.finalize()
    lines, terminal = _terminal_document(path)

    assert len(lines) == 1
    assert receipt.byte_count <= maximum
    assert receipt.terminal_manifest_written
    assert receipt.retention_complete is False
    assert terminal["payload"]["event_line_count"] == 0
    assert any(value.startswith("RECEIPT_WRITE_ERROR:") for value in receipt.error_types)


def test_existing_path_is_neither_overwritten_nor_claimed(tmp_path: Path) -> None:
    path = tmp_path / "existing.jsonl"
    path.write_text('{"preexisting":true}\n', encoding="utf-8")
    before = path.read_bytes()
    emitter = f2531.TerminalReceiptEmitter(path, mirror_sink=None)
    emitter("new", {"receipt_hash": "4" * 64})
    receipt = emitter.finalize()

    assert path.read_bytes() == before
    assert receipt.state is f2531.RetentionState.DESCRIPTIVE_ERROR
    assert receipt.terminal_manifest_written is False
    assert receipt.artifact_hash is None
    assert receipt.retention_complete is False


def test_runtime_exception_still_closes_with_terminal_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "runtime-error.jsonl"

    def fail(**kwargs: object) -> object:
        emitter = kwargs["event_emitter"]
        assert callable(emitter)
        emitter("before_failure", {"receipt_hash": "5" * 64})
        raise RuntimeError("fixture unexpected runtime failure")

    monkeypatch.setattr(f2531.f25, "run_once", fail)
    with pytest.raises(RuntimeError, match="unexpected runtime failure"):
        f2531.run_once(runtime_commit="b" * 40, receipt_path=path, mirror_sink=None)

    _lines, terminal = _terminal_document(path)
    payload = terminal["payload"]
    assert payload["state"] == f2531.RetentionState.DESCRIPTIVE_ERROR.value
    assert payload["retention_complete"] is True
    assert any(value.startswith("RUNTIME_ERROR:") for value in payload["error_types"])


def test_receipt_errors_cannot_change_the_physical_decision(tmp_path: Path) -> None:
    def run(name: str, *, invalid_atomic: bool) -> tuple[f25.F25Result, f2531.ClosedArtifactReceipt]:
        def qualifier(endpoint: kiwi.KiwiEndpoint, _mother: f2.MotherPlan) -> f25.PhaseReceipt:
            return _phase(endpoint, invalid_atomic=invalid_atomic)

        emitter = f2531.TerminalReceiptEmitter(tmp_path / f"{name}.jsonl", mirror_sink=None)
        bootstrap = f2531.build_bootstrap_receipt(runtime_commit="c" * 40, created_at=NOW)
        physical = f25.run_once(
            runtime_commit="c" * 40,
            bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
            direct_qualifier=qualifier,
            retry_selector=f253.structured_retryable_phase,
            event_emitter=emitter,
        )
        return physical, emitter.finalize()

    baseline, baseline_artifact = run("baseline", invalid_atomic=False)
    failed, failed_artifact = run("failed", invalid_atomic=True)
    assert _decision_signature(failed) == _decision_signature(baseline)
    assert baseline_artifact.state is f2531.RetentionState.COMPLETE
    assert failed_artifact.state is f2531.RetentionState.DESCRIPTIVE_ERROR
    assert failed_artifact.physical_decision_affected is False


def test_main_exposes_closed_artifact_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = f2531.ClosedArtifactReceipt(
        f2531.RetentionState.COMPLETE,
        "fixture.jsonl",
        1,
        100,
        "6" * 64,
        "7" * 64,
        True,
        0,
        sha256().hexdigest(),
        (),
        (),
        True,
        f2531.MAXIMUM_BYTES,
    )
    monkeypatch.setattr(
        f2531,
        "run_once",
        lambda: SimpleNamespace(physical_result=object(), receipt_artifact=artifact),
    )
    captured: list[tuple[str, object]] = []
    monkeypatch.setattr(
        f2531,
        "emit_jsonl",
        lambda event, payload: captured.append((event, payload)),
    )
    f2531.main()
    assert captured == [("gate_f2_5_3_1_artifact_closed", artifact)]


def test_terminal_artifact_contains_no_rf_or_nonstandard_json(tmp_path: Path) -> None:
    path = tmp_path / "strict.jsonl"
    emitter = f2531.TerminalReceiptEmitter(path, mirror_sink=None)
    emitter("numeric", {"value": float("inf"), "artifact_hash": "8" * 64})
    receipt = emitter.finalize()
    documents = [
        json.loads(line, parse_constant=lambda value: pytest.fail(value))
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert receipt.state is f2531.RetentionState.COMPLETE
    assert documents[0]["payload"]["value"] == {"numeric_state": "POSITIVE_INFINITY"}
    serialized = path.read_text(encoding="utf-8").lower()
    assert not any(f'"{key}"' in serialized for key in f253.FORBIDDEN_RF_KEYS)


def test_module_has_no_import_time_network_or_rf_write_surface() -> None:
    source = Path(f2531.__file__).read_text(encoding="utf-8")
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
