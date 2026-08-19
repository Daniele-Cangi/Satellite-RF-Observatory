"""Gate F2.5.3: structured retry control and bounded receipt retention.

This is a narrow offline correction to the control surface exposed by the
first F2.5.2 outcome.  It does not change candidates, tuning, thresholds, the
physical question, or any frozen outcome.  Importing the module opens no file
and performs no network activity.
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
from .models import strict_json_value


F253_TRANSFORM_VERSION = "gate-f2.5.3-structured-control-receipt-sink-v1"
PARENT_RUNTIME_COMMIT = "64a717b8dcd13ec0c09cd7b87388986bdb2ffbb3"
PARENT_OUTCOME_COMMIT = "fffb1068e987bdcb135d053abf18195211fe7458"
MAX_RECEIPT_ARTIFACT_BYTES = 4 * 1024 * 1024
STRUCTURED_RETRYABLE_ERROR_TYPES = frozenset(
    {
        "ConnectionError",
        "ConnectionResetError",
        "OSError",
        "TimeoutError",
        "URLError",
        "WebSocketConnectionClosedException",
        "WebSocketTimeoutException",
    }
)
FORBIDDEN_RF_KEYS = frozenset(
    {
        "blocks",
        "frames",
        "iq",
        "iq_array",
        "iq_samples",
        "raw_body",
        "raw_frame",
        "raw_frames",
        "samples",
        "stft",
        "waterfall",
    }
)


class ReceiptArtifactState(str, Enum):
    COMPLETE = "COMPLETE"
    DESCRIPTIVE_ERROR = "DESCRIPTIVE_ERROR"


@dataclass(frozen=True, slots=True)
class ReceiptEmissionError:
    event_type: str
    error_type: str
    description_hash: str


@dataclass(frozen=True, slots=True)
class ReceiptArtifactReceipt:
    state: ReceiptArtifactState
    path: str
    line_count: int
    byte_count: int
    artifact_hash: str | None
    maximum_bytes: int
    errors: tuple[ReceiptEmissionError, ...]
    content_policy: str = "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY"
    raw_rf_persistence: str = "ZERO"
    physical_decision_affected: bool = False


@dataclass(frozen=True, slots=True)
class F253BootstrapReceipt:
    inherited_f252: f252.F252BootstrapReceipt
    runtime_commit: str
    parent_runtime_commit: str
    parent_outcome_commit: str
    retry_basis: str
    retryable_error_types: tuple[str, ...]
    receipt_artifact_maximum_bytes: int
    receipt_content_policy: str
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be a full Git SHA-1")
        if self.inherited_f252.runtime_commit != self.runtime_commit:
            raise ValueError("inherited F2.5.2 bootstrap must bind the same runtime")
        if self.parent_runtime_commit != PARENT_RUNTIME_COMMIT:
            raise ValueError("Gate F2.5.2 runtime lineage changed")
        if self.parent_outcome_commit != PARENT_OUTCOME_COMMIT:
            raise ValueError("Gate F2.5.2 outcome lineage changed")
        if self.retry_basis != "ATOMIC_BRANCH_STATE_AND_TYPED_ERROR_ONLY":
            raise ValueError("aggregate prose cannot control retry")
        if self.retryable_error_types != tuple(sorted(STRUCTURED_RETRYABLE_ERROR_TYPES)):
            raise ValueError("structured retry allowlist changed")
        if self.receipt_artifact_maximum_bytes != MAX_RECEIPT_ARTIFACT_BYTES:
            raise ValueError("bounded receipt artifact changed")
        if self.receipt_content_policy != "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY":
            raise ValueError("receipt sink content policy changed")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("raw RF persistence is forbidden")
        if self.transform_versions[-1] != F253_TRANSFORM_VERSION:
            raise ValueError("Gate F2.5.3 transform ledger changed")

    @property
    def retry_budget(self) -> int:
        return self.inherited_f252.retry_budget

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F253Result:
    physical_result: f25.F25Result
    receipt_artifact: ReceiptArtifactReceipt


def build_bootstrap_receipt(*, runtime_commit: str, created_at: datetime) -> F253BootstrapReceipt:
    inherited = f252.build_bootstrap_receipt(runtime_commit=runtime_commit, created_at=created_at)
    return F253BootstrapReceipt(
        inherited,
        runtime_commit,
        PARENT_RUNTIME_COMMIT,
        PARENT_OUTCOME_COMMIT,
        "ATOMIC_BRANCH_STATE_AND_TYPED_ERROR_ONLY",
        tuple(sorted(STRUCTURED_RETRYABLE_ERROR_TYPES)),
        MAX_RECEIPT_ARTIFACT_BYTES,
        "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY",
        "ZERO",
        inherited.transform_versions + (F253_TRANSFORM_VERSION,),
    )


def structured_retryable_phase(receipt: f25.PhaseReceipt) -> bool:
    """Admit retries from typed qualification failures, never prose."""

    if receipt.state is not f25.F25PhaseState.QUALIFICATION_ERROR:
        return False
    if receipt.atomic_branch_receipts:
        error_types = tuple(
            item.error_type
            for item in receipt.atomic_branch_receipts
            if isinstance(item, f252.BranchOpenReceipt)
            and item.state is f252.BranchOpenState.QUALIFICATION_ERROR
            and item.error_type is not None
        )
    else:
        error_types = receipt.qualification_error_types
    if not error_types:
        return False
    return any(
        error_type in STRUCTURED_RETRYABLE_ERROR_TYPES
        for error_type in error_types
    )


def _assert_receipt_only(value: object, *, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_RF_KEYS:
                location = ".".join(path + (str(key),))
                raise ValueError(f"raw RF field is forbidden in receipt artifact: {location}")
            _assert_receipt_only(item, path=path + (str(key),))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_receipt_only(item, path=path + (str(index),))


def _strict_event_line(event_type: str, payload: object) -> str:
    envelope = strict_json_value({"event": event_type, "payload": payload})
    _assert_receipt_only(envelope)
    return json.dumps(envelope, allow_nan=False, separators=(",", ":"), sort_keys=True)


class _BoundedReceiptWriter:
    """Exclusive, incremental JSONL writer; it never accepts sample material."""

    def __init__(self, path: Path, maximum_bytes: int) -> None:
        self.path = path
        self.maximum_bytes = maximum_bytes
        self.line_count = 0
        self.byte_count = 0
        self._hash = sha256()
        self._stream = path.open("x", encoding="utf-8", newline="\n")

    def write(self, line: str) -> None:
        encoded = (line + "\n").encode("utf-8")
        if self.byte_count + len(encoded) > self.maximum_bytes:
            raise ValueError("bounded receipt artifact capacity exceeded")
        self._stream.write(line + "\n")
        self._stream.flush()
        self._hash.update(encoded)
        self.byte_count += len(encoded)
        self.line_count += 1

    def close(self) -> str:
        self._stream.close()
        return self._hash.hexdigest()


class SafeReceiptEmitter:
    """Capture descriptive failures without feeding them into physical control."""

    def __init__(
        self,
        path: Path,
        *,
        maximum_bytes: int = MAX_RECEIPT_ARTIFACT_BYTES,
        mirror_sink: Callable[[str], None] | None = print,
    ) -> None:
        self.path = path
        self.maximum_bytes = maximum_bytes
        self.mirror_sink = mirror_sink
        self.errors: list[ReceiptEmissionError] = []
        self._writer: _BoundedReceiptWriter | None = None
        self._owned_path = False
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = _BoundedReceiptWriter(path, maximum_bytes)
            self._owned_path = True
        except Exception as error:
            self._record("receipt_artifact_open", error)

    def _record(self, event_type: str, error: Exception) -> None:
        self.errors.append(
            ReceiptEmissionError(
                event_type,
                type(error).__name__,
                f2._hash(
                    {
                        "event_type": event_type,
                        "error_type": type(error).__name__,
                        "error": str(error),
                    }
                ),
            )
        )

    def __call__(self, event_type: str, payload: object) -> None:
        try:
            line = _strict_event_line(event_type, payload)
        except Exception as error:
            self._record(event_type, error)
            return
        if self._writer is not None:
            try:
                self._writer.write(line)
            except Exception as error:
                self._record(event_type, error)
                try:
                    self._writer.close()
                finally:
                    self._writer = None
        if self.mirror_sink is not None:
            try:
                self.mirror_sink(line)
            except Exception as error:
                self._record(event_type, error)

    def finalize(self) -> ReceiptArtifactReceipt:
        artifact_hash: str | None = None
        line_count = 0
        byte_count = 0
        if self._writer is not None:
            line_count = self._writer.line_count
            byte_count = self._writer.byte_count
            try:
                artifact_hash = self._writer.close()
            except Exception as error:
                self._record("receipt_artifact_close", error)
            finally:
                self._writer = None
        elif self._owned_path and self.path.exists():
            # The incremental writer may have been closed after a bounded-sink
            # error. Re-hashing a receipt-only file does not touch RF data.
            try:
                data = self.path.read_bytes()
                byte_count = len(data)
                line_count = data.count(b"\n")
                artifact_hash = sha256(data).hexdigest()
            except Exception as error:
                self._record("receipt_artifact_describe", error)
        return ReceiptArtifactReceipt(
            ReceiptArtifactState.DESCRIPTIVE_ERROR if self.errors else ReceiptArtifactState.COMPLETE,
            str(self.path),
            line_count,
            byte_count,
            artifact_hash,
            self.maximum_bytes,
            tuple(self.errors),
        )


def default_receipt_path(created_at: datetime) -> Path:
    stamp = f2._utc(created_at).strftime("%Y%m%dT%H%M%S.%fZ")
    return Path("experiments") / "live_instrument" / "session_receipts" / f"gate-f2-5-3-{stamp}.jsonl"


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    receipt_path: Path | None = None,
    mirror_sink: Callable[[str], None] | None = print,
) -> F253Result:
    """Future single session; this offline gate does not invoke it."""

    commit = runtime_commit or f22.runtime_commit()
    created_at = datetime.now(timezone.utc)
    bootstrap = build_bootstrap_receipt(runtime_commit=commit, created_at=created_at)
    emitter = SafeReceiptEmitter(receipt_path or default_receipt_path(created_at), mirror_sink=mirror_sink)
    physical = f25.run_once(
        mother=mother,
        runtime_commit=commit,
        bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
        direct_qualifier=f252.direct_dual_snd_qualification,
        event_prefix="gate_f2_5_3",
        terminal_instrument="gate-f2.5.3-structured-dual-snd",
        retry_selector=structured_retryable_phase,
        event_emitter=emitter,
    )
    return F253Result(physical, emitter.finalize())


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
