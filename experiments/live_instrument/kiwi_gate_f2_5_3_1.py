"""Gate F2.5.3.1: terminal receipt manifest, prepared offline.

The frozen F2.5.3 runtime remains reproducible at its commit.  This module
changes only receipt-artifact closure: the same strict JSONL file ends with a
terminal manifest that commits to every preceding line.  Importing it opens no
file and performs no network activity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_2 as f252
from . import kiwi_gate_f2_5_3 as f253
from .models import emit_jsonl


F2531_TRANSFORM_VERSION = "gate-f2.5.3.1-terminal-receipt-manifest-v1"
PARENT_GATE_COMMIT = "d067b1e66989532bba4846f29eaa509609f66edf"
TERMINAL_EVENT = "gate_f2_5_3_1_receipt_artifact_terminal"
MAXIMUM_BYTES = f253.MAX_RECEIPT_ARTIFACT_BYTES
TERMINAL_RESERVE_BYTES = 16 * 1024
MAX_RETAINED_ERROR_HASHES = 64


class RetentionState(str, Enum):
    COMPLETE = "COMPLETE"
    DESCRIPTIVE_ERROR = "DESCRIPTIVE_ERROR"


@dataclass(frozen=True, slots=True)
class TerminalManifest:
    state: RetentionState
    event_line_count: int
    event_byte_count: int
    prefix_hash: str
    error_count: int
    error_ledger_hash: str
    retained_error_hashes: tuple[str, ...]
    error_hashes_truncated: bool
    error_types: tuple[str, ...]
    retention_complete: bool
    maximum_bytes: int
    terminal_reserve_bytes: int
    content_policy: str = "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY"
    raw_rf_persistence: str = "ZERO"
    physical_decision_affected: bool = False


@dataclass(frozen=True, slots=True)
class ClosedArtifactReceipt:
    state: RetentionState
    path: str
    line_count: int
    byte_count: int
    artifact_hash: str | None
    prefix_hash: str | None
    terminal_manifest_written: bool
    error_count: int
    error_ledger_hash: str
    retained_error_hashes: tuple[str, ...]
    error_types: tuple[str, ...]
    retention_complete: bool
    maximum_bytes: int
    content_policy: str = "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY"
    raw_rf_persistence: str = "ZERO"
    physical_decision_affected: bool = False


@dataclass(frozen=True, slots=True)
class F2531BootstrapReceipt:
    inherited_f253: f253.F253BootstrapReceipt
    runtime_commit: str
    parent_gate_commit: str
    terminal_event: str
    terminal_reserve_bytes: int
    terminal_manifest_required: bool
    prefix_hash_required: bool
    cli_close_receipt_required: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be a full Git SHA-1")
        if self.inherited_f253.runtime_commit != self.runtime_commit:
            raise ValueError("inherited F2.5.3 bootstrap must bind the same runtime")
        if self.parent_gate_commit != PARENT_GATE_COMMIT:
            raise ValueError("Gate F2.5.3 lineage changed")
        if self.terminal_event != TERMINAL_EVENT:
            raise ValueError("terminal event changed")
        if self.terminal_reserve_bytes != TERMINAL_RESERVE_BYTES:
            raise ValueError("terminal reserve changed")
        if not all(
            (
                self.terminal_manifest_required,
                self.prefix_hash_required,
                self.cli_close_receipt_required,
            )
        ):
            raise ValueError("terminal receipt closure cannot be weakened")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("raw RF persistence is forbidden")
        if self.transform_versions[-1] != F2531_TRANSFORM_VERSION:
            raise ValueError("Gate F2.5.3.1 transform ledger changed")

    @property
    def retry_budget(self) -> int:
        return self.inherited_f253.retry_budget

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2531Result:
    physical_result: f25.F25Result
    receipt_artifact: ClosedArtifactReceipt


def build_bootstrap_receipt(*, runtime_commit: str, created_at: datetime) -> F2531BootstrapReceipt:
    inherited = f253.build_bootstrap_receipt(runtime_commit=runtime_commit, created_at=created_at)
    return F2531BootstrapReceipt(
        inherited,
        runtime_commit,
        PARENT_GATE_COMMIT,
        TERMINAL_EVENT,
        TERMINAL_RESERVE_BYTES,
        True,
        True,
        True,
        "ZERO",
        inherited.transform_versions + (F2531_TRANSFORM_VERSION,),
    )


class _TerminalWriter:
    def __init__(self, path: Path, maximum_bytes: int) -> None:
        if maximum_bytes <= TERMINAL_RESERVE_BYTES:
            raise ValueError("receipt artifact cap must leave room for its terminal manifest")
        self.path = path
        self.maximum_bytes = maximum_bytes
        self.line_count = 0
        self.byte_count = 0
        self._hash = sha256()
        self._stream = path.open("x", encoding="utf-8", newline="\n")

    @property
    def digest(self) -> str:
        return self._hash.hexdigest()

    def write_event(self, line: str) -> None:
        encoded = (line + "\n").encode("utf-8")
        if self.byte_count + len(encoded) > self.maximum_bytes - TERMINAL_RESERVE_BYTES:
            raise ValueError("receipt event would consume the frozen terminal reserve")
        self._write(line, encoded)

    def write_terminal(self, line: str) -> None:
        encoded = (line + "\n").encode("utf-8")
        if self.byte_count + len(encoded) > self.maximum_bytes:
            raise ValueError("terminal receipt manifest exceeds the artifact cap")
        self._write(line, encoded)

    def _write(self, line: str, encoded: bytes) -> None:
        self._stream.write(line + "\n")
        self._stream.flush()
        self._hash.update(encoded)
        self.byte_count += len(encoded)
        self.line_count += 1

    def close(self) -> str:
        self._stream.close()
        return self.digest


class TerminalReceiptEmitter:
    """Non-interfering event sink with an in-band terminal completeness witness."""

    def __init__(
        self,
        path: Path,
        *,
        maximum_bytes: int = MAXIMUM_BYTES,
        mirror_sink: Callable[[str], None] | None = print,
    ) -> None:
        self.path = path
        self.maximum_bytes = maximum_bytes
        self.mirror_sink = mirror_sink
        self._writer: _TerminalWriter | None = None
        self._owned_path = False
        self._finalized = False
        self._error_count = 0
        self._error_hasher = sha256()
        self._error_hashes: list[str] = []
        self._error_types: set[str] = set()
        self._retention_complete = True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = _TerminalWriter(path, maximum_bytes)
            self._owned_path = True
        except Exception as error:
            self._record("ARTIFACT_OPEN_ERROR", "receipt_artifact_open", error, affects_retention=True)

    def _record(
        self,
        category: str,
        event_type: str,
        error: Exception,
        *,
        affects_retention: bool,
    ) -> None:
        description_hash = f2._hash(
            {
                "category": category,
                "event_type": event_type,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        encoded = description_hash.encode("ascii")
        self._error_hasher.update(len(encoded).to_bytes(8, "big"))
        self._error_hasher.update(encoded)
        self._error_count += 1
        if len(self._error_hashes) < MAX_RETAINED_ERROR_HASHES:
            self._error_hashes.append(description_hash)
        self._error_types.add(f"{category}:{type(error).__name__}")
        if affects_retention:
            self._retention_complete = False

    def record_runtime_error(self, error: BaseException) -> None:
        wrapped = RuntimeError(f"{type(error).__name__}: {error}")
        self._record("RUNTIME_ERROR", "gate_f2_5_3_1_runtime", wrapped, affects_retention=False)

    def __call__(self, event_type: str, payload: object) -> None:
        if self._finalized:
            self._record(
                "WRITE_AFTER_FINALIZE",
                event_type,
                RuntimeError("receipt emitter is already finalized"),
                affects_retention=True,
            )
            return
        try:
            line = f253._strict_event_line(event_type, payload)
        except Exception as error:
            self._record("SERIALIZATION_ERROR", event_type, error, affects_retention=True)
            return
        if self._writer is not None:
            try:
                self._writer.write_event(line)
            except Exception as error:
                self._record("RECEIPT_WRITE_ERROR", event_type, error, affects_retention=True)
        if self.mirror_sink is not None:
            try:
                self.mirror_sink(line)
            except Exception as error:
                self._record("MIRROR_ERROR", event_type, error, affects_retention=False)

    def _manifest(self, prefix_hash: str, event_lines: int, event_bytes: int) -> TerminalManifest:
        errors = self._error_count > 0
        return TerminalManifest(
            RetentionState.DESCRIPTIVE_ERROR if errors else RetentionState.COMPLETE,
            event_lines,
            event_bytes,
            prefix_hash,
            self._error_count,
            self._error_hasher.hexdigest(),
            tuple(self._error_hashes),
            self._error_count > len(self._error_hashes),
            tuple(sorted(self._error_types)),
            self._retention_complete,
            self.maximum_bytes,
            TERMINAL_RESERVE_BYTES,
        )

    def finalize(self) -> ClosedArtifactReceipt:
        if self._finalized:
            raise RuntimeError("receipt emitter may be finalized only once")
        self._finalized = True
        artifact_hash: str | None = None
        prefix_hash: str | None = None
        terminal_written = False
        line_count = 0
        byte_count = 0
        if self._writer is not None:
            prefix_hash = self._writer.digest
            event_lines = self._writer.line_count
            event_bytes = self._writer.byte_count
            try:
                terminal_line = f253._strict_event_line(
                    TERMINAL_EVENT,
                    self._manifest(prefix_hash, event_lines, event_bytes),
                )
                self._writer.write_terminal(terminal_line)
                terminal_written = True
            except Exception as error:
                self._record(
                    "TERMINAL_MANIFEST_ERROR",
                    TERMINAL_EVENT,
                    error,
                    affects_retention=True,
                )
            line_count = self._writer.line_count
            byte_count = self._writer.byte_count
            try:
                artifact_hash = self._writer.close()
            except Exception as error:
                self._record("ARTIFACT_CLOSE_ERROR", TERMINAL_EVENT, error, affects_retention=True)
            finally:
                self._writer = None
        state = (
            RetentionState.COMPLETE
            if self._error_count == 0 and terminal_written
            else RetentionState.DESCRIPTIVE_ERROR
        )
        return ClosedArtifactReceipt(
            state,
            str(self.path),
            line_count,
            byte_count,
            artifact_hash,
            prefix_hash,
            terminal_written,
            self._error_count,
            self._error_hasher.hexdigest(),
            tuple(self._error_hashes),
            tuple(sorted(self._error_types)),
            self._retention_complete and terminal_written,
            self.maximum_bytes,
        )


def default_receipt_path(created_at: datetime) -> Path:
    stamp = f2._utc(created_at).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        Path("experiments")
        / "live_instrument"
        / "session_receipts"
        / f"gate-f2-5-3-1-{stamp}.jsonl"
    )


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    receipt_path: Path | None = None,
    mirror_sink: Callable[[str], None] | None = print,
) -> F2531Result:
    """Future single session; this offline gate does not invoke it."""

    commit = runtime_commit or f22.runtime_commit()
    created_at = datetime.now(timezone.utc)
    bootstrap = build_bootstrap_receipt(runtime_commit=commit, created_at=created_at)
    emitter = TerminalReceiptEmitter(
        receipt_path or default_receipt_path(created_at),
        mirror_sink=mirror_sink,
    )
    try:
        physical = f25.run_once(
            mother=mother,
            runtime_commit=commit,
            bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
            direct_qualifier=f252.direct_dual_snd_qualification,
            event_prefix="gate_f2_5_3_1",
            terminal_instrument="gate-f2.5.3.1-terminal-receipt",
            retry_selector=f253.structured_retryable_phase,
            event_emitter=emitter,
        )
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    return F2531Result(physical, emitter.finalize())


def main() -> None:
    result = run_once()
    emit_jsonl("gate_f2_5_3_1_artifact_closed", result.receipt_artifact)


if __name__ == "__main__":
    main()
