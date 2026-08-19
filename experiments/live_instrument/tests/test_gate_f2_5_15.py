"""Offline tests for the Gate F2.5.15 post-commit authority seal."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import struct
from threading import Lock
from types import SimpleNamespace

import pytest
import websocket

from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5_3_1 as f2531
from experiments.live_instrument import kiwi_gate_f2_5_14 as f2514
from experiments.live_instrument import kiwi_gate_f2_5_15 as f2515
from experiments.live_instrument.models import strict_json_value


class _Frame:
    def __init__(self, data: bytes):
        self.data = data


class _Socket:
    def __init__(self, frames: list[bytes | Exception]) -> None:
        self.frames = list(frames)
        self.sent: list[str] = []
        self.closed = False

    def connect(self, *args: object, **kwargs: object) -> "_Socket":
        del args, kwargs
        return self

    def send(self, command: str) -> None:
        self.sent.append(command)

    def recv_data_frame(self, control_frame: bool = False) -> tuple[int, _Frame]:
        assert control_frame
        if not self.frames:
            raise ConnectionError("synthetic stream exhausted")
        item = self.frames.pop(0)
        if isinstance(item, Exception):
            raise item
        return websocket.ABNF.OPCODE_BINARY, _Frame(item)

    def close(self) -> None:
        self.closed = True


class _Provider:
    def __init__(self, *, reject_all: bool = False) -> None:
        self.reject_all = reject_all
        self.calls: list[tuple[str, str]] = []
        self.sockets: list[_Socket] = []
        self._lock = Lock()

    def __call__(self, endpoint: object, role: str):  # type: ignore[no-untyped-def]
        identity = f"{endpoint.host.lower()}:{endpoint.port}"
        socket = _Socket(
            [b"MSG badp=5"]
            if self.reject_all
            else [_msg(7 if role == "reference" else 8), _snd(17 if role == "reference" else 29)]
        )
        with self._lock:
            self.calls.append((identity, role))
            self.sockets.append(socket)
        return socket.connect


def _msg(channel: int) -> bytes:
    return (
        f"MSG is_local={channel},0,0 badp=0 audio_rate=12000 sample_rate=12000"
    ).encode("ascii")


def _snd(sequence: int) -> bytes:
    return b"SND" + (
        struct.pack("<BI", 0x08, sequence)
        + struct.pack(">H", 1_000)
        + struct.pack("<BBII", 5, 0, 100_000, 250_000_000)
        + struct.pack(">hhhh", 100, -100, 200, -200)
    )


def test_authority_envelope_seals_commit_sources_environment_and_control() -> None:
    envelope = f2515.build_authority_envelope()

    json.dumps(strict_json_value(envelope), allow_nan=False)
    assert envelope.reviewed_f2514_commit == f2515.REVIEWED_F2514_COMMIT
    assert envelope.reviewed_control_surface_hash == (
        f2515.REVIEWED_CONTROL_SURFACE_HASH
    )
    assert envelope.causal_source_sha256 == f2515.EXPECTED_CAUSAL_SOURCE_SHA256
    assert envelope.expected_environment == f2515.EXPECTED_ENVIRONMENT
    assert envelope.public_caller_overrides == ("live_authorised",)
    assert envelope.retry_budget == 0
    assert envelope.postfreeze_retry_budget == 0
    assert envelope.raw_rf_persistence == "ZERO"
    paths = set(f2515.RUNTIME_CAUSAL_PATHS)
    assert "experiments/live_instrument/kiwi_gate_f2_5_2.py" in paths
    assert "experiments/live_instrument/kiwi_gate_f2_5_6.py" in paths
    assert "experiments/live_instrument/kiwi_gate_f2_5_14.py" in paths


def test_real_post_commit_guards_match_without_authorising_network() -> None:
    assessment = f2515.assess_gate_f2_5_15()

    assert assessment.exit is (
        f2515.F2515Exit.EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY
    )
    assert assessment.f2514_prerequisite_satisfied
    assert assessment.reviewed_commit_is_ancestor
    assert assessment.causal_git_diff_clean
    assert assessment.causal_source_hashes_match
    assert assessment.numerical_environment_matches
    assert assessment.working_directory_is_repository_root
    assert assessment.caller_overrides_removed
    assert not assessment.live_execution_authorised
    assert assessment.blockers == ()


def test_canonical_source_hash_is_independent_of_windows_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.py"
    crlf = tmp_path / "crlf.py"
    lf.write_bytes(b"x = 1\ny = 2\n")
    crlf.write_bytes(b"x = 1\r\ny = 2\r\n")

    assert f2515._canonical_source_sha256(lf) == f2515._canonical_source_sha256(crlf)


def test_any_source_hash_or_prerequisite_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    changed = list(f2515.EXPECTED_CAUSAL_SOURCE_SHA256)
    changed[-1] = (changed[-1][0], "0" * 64)
    monkeypatch.setattr(f2515, "current_causal_source_sha256", lambda: tuple(changed))
    assessment = f2515.assess_gate_f2_5_15()

    assert assessment.exit is f2515.F2515Exit.POST_COMMIT_SEAL_MISMATCH
    assert assessment.blockers == ("reviewed causal source SHA-256 changed",)

    prior = replace(
        f2514.assess_gate_f2_5_14(),
        two_branch_concurrency_materialized=False,
    )
    blocked = f2515.assess_gate_f2_5_15(prior)
    assert "F2.5.14 offline prerequisite failed" in blocked.blockers


def test_unauthorised_surface_refuses_before_assessment_receipt_or_connector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        f2515,
        "assess_gate_f2_5_15",
        lambda: pytest.fail("assessment cannot run before explicit authority"),
    )
    monkeypatch.setattr(
        f2515,
        "_execute_with_dependencies",
        lambda *_args, **_kwargs: pytest.fail("runtime cannot run without authority"),
    )
    monkeypatch.setattr(
        f2515,
        "default_receipt_path",
        lambda _created: pytest.fail("receipt path cannot be materialised"),
    )

    with pytest.raises(PermissionError, match="separate exact live authorisation"):
        f2515.run_reviewed_once()


def test_public_authority_surface_has_no_execution_override() -> None:
    signature = inspect.signature(f2515.run_reviewed_once)

    assert tuple(signature.parameters) == ("live_authorised",)
    assert signature.parameters["live_authorised"].default is False
    assert all(
        name not in signature.parameters
        for name in (
            "endpoint",
            "candidates",
            "frequency",
            "threshold",
            "retry",
            "receipt_path",
            "connector_provider",
            "websocket_module",
        )
    )


def test_authorised_surface_supplies_exact_dependencies_without_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    envelope = f2515.build_authority_envelope()
    ready = SimpleNamespace(
        exit=f2515.F2515Exit.EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY,
        envelope=envelope,
        blockers=(),
    )
    captured: dict[str, object] = {}

    def fake_execute(authority: object, **kwargs: object) -> object:
        captured["authority"] = authority
        captured.update(kwargs)
        return sentinel

    fixed_path = Path("fixed-receipt.jsonl")
    monkeypatch.setattr(f2515, "assess_gate_f2_5_15", lambda: ready)
    monkeypatch.setattr(f2515, "default_receipt_path", lambda _created: fixed_path)
    monkeypatch.setattr(f2515, "_execute_with_dependencies", fake_execute)

    result = f2515.run_reviewed_once(live_authorised=True)

    assert result is sentinel
    assert captured == {
        "authority": envelope,
        "connector_provider": f2515._live_connector_provider,
        "websocket_module": websocket,
        "receipt_path": fixed_path,
        "mirror_sink": print,
    }


def test_authorised_surface_still_refuses_if_post_commit_seal_drifted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocked = SimpleNamespace(
        exit=f2515.F2515Exit.POST_COMMIT_SEAL_MISMATCH,
        blockers=("fixture drift",),
    )
    monkeypatch.setattr(f2515, "assess_gate_f2_5_15", lambda: blocked)
    monkeypatch.setattr(
        f2515,
        "_execute_with_dependencies",
        lambda *_args, **_kwargs: pytest.fail("mismatched seal cannot execute"),
    )

    with pytest.raises(RuntimeError, match="fixture drift"):
        f2515.run_reviewed_once(live_authorised=True)


def test_injected_execution_writes_authority_as_first_event_and_one_outcome(
    tmp_path: Path,
) -> None:
    provider = _Provider()
    path = tmp_path / "reviewed.jsonl"
    authority = f2515.build_authority_envelope()

    result = f2515._execute_with_dependencies(
        authority,
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=path,
        mirror_sink=None,
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
    )
    assert len(result.physical_receipt.attempts) == 1
    assert len(provider.calls) == 2
    assert all(socket.closed for socket in provider.sockets)
    assert result.receipt_artifact.state is f2531.RetentionState.COMPLETE
    assert result.receipt_artifact.terminal_manifest_written
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert lines[0]["event"] == f"{f2515.EVENT_PREFIX}_authority_envelope_frozen"
    first_payload = lines[0]["payload"]
    assert first_payload["authority_envelope_hash"] == authority.receipt_hash
    assert first_payload["execution_control_surface_hash"] == (
        f2515.REVIEWED_CONTROL_SURFACE_HASH
    )
    assert lines[-1]["event"] == f2531.TERMINAL_EVENT
    encoded = path.read_text(encoding="utf-8").lower()
    assert '"raw_rf_persistence":"zero"' in encoded
    assert '"peer_close_status_code":1005' not in encoded


def test_all_explicit_second_channel_refusals_are_terminal_no_multi(tmp_path: Path) -> None:
    provider = _Provider(reject_all=True)
    result = f2515._execute_with_dependencies(
        f2515.build_authority_envelope(),
        connector_provider=provider,
        websocket_module=websocket,
        receipt_path=tmp_path / "negative.jsonl",
        mirror_sink=None,
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.NO_MULTI_CHANNEL_CAPABILITY
    )
    assert len(result.physical_receipt.attempts) == len(f24.ordered_candidates())
    assert len(provider.calls) == 2 * len(f24.ordered_candidates())


def test_receipt_description_failure_does_not_change_physical_outcome(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied.jsonl"
    occupied.write_text("occupied", encoding="utf-8")
    result = f2515._execute_with_dependencies(
        f2515.build_authority_envelope(),
        connector_provider=_Provider(),
        websocket_module=websocket,
        receipt_path=occupied,
        mirror_sink=None,
    )

    assert result.physical_receipt.outcome is (
        f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
    )
    assert result.receipt_artifact.state is f2531.RetentionState.DESCRIPTIVE_ERROR
    assert occupied.read_text(encoding="utf-8") == "occupied"


def test_module_has_no_top_level_execution_or_cli() -> None:
    source = Path(f2515.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_calls = [
        node
        for node in tree.body
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
    ]
    defined = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert top_level_calls == []
    assert "main" not in defined
    assert "run_live" not in defined
    assert "KiwiEndpoint(" not in source
    assert "fetch_kiwi_status" not in source
    assert "waterfall" not in source.lower()
