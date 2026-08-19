"""Gate F2.5.33: post-commit seal for the F2.5.32 vertical.

Assessment is offline. ``run_reviewed_once`` is the sole live-capable surface
and refuses before assessment, receipt creation or connector access unless a
separate authority is asserted.  The public caller can change no endpoint,
frequency, timing, threshold, retry, connector, receipt path or experiment
phase.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import importlib.metadata
import inspect
import json
from pathlib import Path
import platform
import subprocess
import time
from typing import Callable

import numpy as np
import scipy
import websocket

from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_3_1 as receipt
from . import kiwi_gate_f2_5_20 as f2520
from . import kiwi_gate_f2_5_29 as f2529
from . import kiwi_gate_f2_5_31 as f2531
from . import kiwi_gate_f2_5_32 as f2532
from .models import strict_json_value


TRANSFORM_VERSION = "gate-f2.5.33-post-commit-authority-seal-v1"
REVIEWED_F2532_COMMIT = "eae4d753b3c5f8d9ffd8247fc3758afb9c1ff15d"
REVIEWED_AT = datetime(2026, 8, 18, 23, 23, 21, tzinfo=timezone.utc)
REVIEWED_F2532_SOURCE_SHA256 = (
    "d38a3bdf4669ed7b0e27d9cff1399d9fd2744b4bdc909e7e687cb88a2b7daf1b"
)
REVIEWED_F2532_PLAN_HASH = (
    "45c9d39c8d2ede4ebbf456bce400e0ac113aee305b81601c2734ffd5a96741d3"
)
REVIEWED_F2532_INTEGRATION_SURFACE_HASH = (
    "a1e4c9fb619690d934f2287084a3217434713ce0d7807ce4e8b9f0b4155804f9"
)
EXPECTED_LIVE_SURFACE_HASH = (
    "0b402e4420b178fabd92fc413be400ac3fda541f44acb66d37821e2b3551110d"
)
AUTHORITY_ENVELOPE_HASH = (
    "3f052af8686b37be6e04b85543a5fca30ad05e8536a8d57d796034cc98c6ab52"
)
EVENT_PREFIX = "gate_f2_5_33"
RAW_RF_PERSISTENCE = "ZERO"
EXPECTED_ENVIRONMENT = (
    ("python", "3.13.5"),
    ("numpy", "2.3.3"),
    ("scipy", "1.17.1"),
    ("websocket-client", "1.8.0"),
)


class F2533Exit(str, Enum):
    EXACT_RF_RESPONSE_READY_FOR_SEPARATE_AUTHORITY = (
        "EXACT_RF_RESPONSE_READY_FOR_SEPARATE_AUTHORITY"
    )
    POST_COMMIT_SEAL_MISMATCH = "POST_COMMIT_SEAL_MISMATCH"


def _strict_hash(value: object) -> str:
    return sha256(
        json.dumps(
            strict_json_value(value),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=lambda item: item.value if isinstance(item, Enum) else str(item),
        ).encode("utf-8")
    ).hexdigest()


def _sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("a lowercase SHA-256 string is required")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_source_sha256(path: Path) -> str:
    return sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def current_f2532_source_sha256() -> str:
    return _canonical_source_sha256(
        _repository_root()
        / "experiments"
        / "live_instrument"
        / "kiwi_gate_f2_5_32.py"
    )


def current_environment() -> tuple[tuple[str, str], ...]:
    return (
        ("python", platform.python_version()),
        ("numpy", np.__version__),
        ("scipy", scipy.__version__),
        ("websocket-client", importlib.metadata.version("websocket-client")),
    )


def _git_guard(*arguments: str) -> bool:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=_repository_root(),
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def reviewed_commit_is_ancestor() -> bool:
    return _git_guard(
        "merge-base", "--is-ancestor", REVIEWED_F2532_COMMIT, "HEAD"
    )


def reviewed_source_git_diff_clean() -> bool:
    return _git_guard(
        "diff",
        "--quiet",
        REVIEWED_F2532_COMMIT,
        "--",
        "experiments/live_instrument/kiwi_gate_f2_5_32.py",
    )


@dataclass(frozen=True, slots=True)
class F2533AuthorityEnvelope:
    reviewed_f2532_commit: str
    reviewed_at: datetime
    reviewed_f2532_source_sha256: str
    reviewed_f2532_plan_hash: str
    reviewed_f2532_integration_surface_hash: str
    reviewed_live_surface_hash: str
    expected_environment: tuple[tuple[str, str], ...]
    authority_surface: str
    guard_order: tuple[str, ...]
    public_caller_overrides: tuple[str, ...]
    connector_policy: str
    endpoint_identity: str
    channel_topology: str
    experiment_scope: str
    threshold_policy: str
    phase_order: tuple[str, ...]
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    outcome_windows: int
    stop_condition: str
    receipt_path_policy: str
    receipt_first_event: str
    waterfall_role: str
    ext_api_role: str
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_f2532_commit != REVIEWED_F2532_COMMIT:
            raise ValueError("reviewed F2.5.32 commit changed")
        if self.reviewed_at != REVIEWED_AT:
            raise ValueError("review timestamp changed")
        if self.reviewed_f2532_source_sha256 != REVIEWED_F2532_SOURCE_SHA256:
            raise ValueError("reviewed F2.5.32 source changed")
        if self.reviewed_f2532_plan_hash != REVIEWED_F2532_PLAN_HASH:
            raise ValueError("reviewed F2.5.32 plan changed")
        if self.reviewed_f2532_integration_surface_hash != REVIEWED_F2532_INTEGRATION_SURFACE_HASH:
            raise ValueError("reviewed F2.5.32 integration surface changed")
        if self.reviewed_live_surface_hash != EXPECTED_LIVE_SURFACE_HASH:
            raise ValueError("live surface seal changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("numerical environment changed")
        if self.authority_surface != "run_reviewed_once(live_authorised=False)":
            raise ValueError("authority surface changed")
        if self.guard_order != (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "AUTHORITY_RECEIPT_FIRST",
            "TWO_FIXED_SND_CONNECTORS",
            "ONE_F2532_OUTCOME",
        ):
            raise ValueError("authority guard order changed")
        if self.public_caller_overrides != ("live_authorised",):
            raise ValueError("caller-controlled experiment dimensions re-entered")
        if self.connector_policy != "TWO_SIMULTANEOUS_SND_CONNECTIONS_ONE_FROZEN_ENDPOINT":
            raise ValueError("connector policy changed")
        if self.endpoint_identity != f2520.SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("reviewed endpoint changed")
        if self.channel_topology != "SAME_KIWI_DISTINCT_REFERENCE_AND_PERTURBED_DDC":
            raise ValueError("causal topology changed")
        if self.experiment_scope != "OPEN_HANDLE_A1_B_A2_DISTRIBUTED_WITNESS_THEN_TARGET":
            raise ValueError("authority expanded beyond the reviewed vertical")
        if self.threshold_policy != "F2532_INHERITED_UNCHANGED_NO_RUNTIME_OVERRIDE":
            raise ValueError("threshold policy changed")
        if self.phase_order != f2531.PHASE_ORDER:
            raise ValueError("reviewed phase order changed")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the reviewed vertical permits no retry")
        if self.outcome_windows != 1 or self.stop_condition != "FIRST_TERMINAL_OUTCOME":
            raise ValueError("one-outcome stop changed")
        if self.receipt_path_policy != "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE":
            raise ValueError("receipt path policy changed")
        if self.receipt_first_event != f"{EVENT_PREFIX}_authority_envelope_frozen":
            raise ValueError("authority envelope must be the first receipt")
        if self.waterfall_role != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("waterfall re-entered the causal path")
        if self.ext_api_role != "DESCRIPTIVE_HINT_UNUSED":
            raise ValueError("ext_api became multichannel truth")
        if self.live_execution_authorised:
            raise ValueError("offline seal cannot consume authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (f2532.TRANSFORM_VERSION, TRANSFORM_VERSION):
            raise ValueError("authority transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2533Assessment:
    exit: F2533Exit
    envelope: F2533AuthorityEnvelope
    f2532_prerequisite_satisfied: bool
    reviewed_commit_is_ancestor: bool
    reviewed_source_git_diff_clean: bool
    reviewed_source_hash_matches: bool
    reviewed_plan_hash_matches: bool
    reviewed_integration_surface_matches: bool
    live_surface_hash_matches: bool
    authority_envelope_hash_matches: bool
    numerical_environment_matches: bool
    working_directory_is_repository_root: bool
    caller_overrides_removed: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


@dataclass(frozen=True, slots=True)
class F2533RunResult:
    authority_envelope_hash: str
    physical_result: f2532.F2532RunResult
    receipt_artifact: receipt.ClosedArtifactReceipt
    authority_consumed: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.authority_envelope_hash)
        if not self.authority_consumed:
            raise ValueError("live runner result requires consumed authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


class _LiveSocketAdapter:
    """Transfer one websocket-client frame into the reviewed lease boundary."""

    __slots__ = ("_socket", "_closed")

    def __init__(self, socket: object) -> None:
        self._socket = socket
        self._closed = False

    def settimeout(self, value: float) -> None:
        self._socket.settimeout(value)  # type: ignore[attr-defined]

    def send(self, command: str) -> None:
        if self._closed:
            raise RuntimeError("send after close")
        self._socket.send(command)  # type: ignore[attr-defined]

    def recv_data_frame(self, *, control_frame: bool) -> tuple[int, f2529._InjectedFrameLease]:
        if self._closed:
            raise RuntimeError("receive after close")
        opcode, frame = self._socket.recv_data_frame(  # type: ignore[attr-defined]
            control_frame=control_frame
        )
        if not hasattr(frame, "data"):
            raise RuntimeError("websocket-client frame has no data payload")
        value = frame.data
        if isinstance(value, str):
            payload = bytearray(value.encode("latin-1"))
        elif isinstance(value, bytes):
            payload = bytearray(value)
        elif isinstance(value, bytearray):
            payload = bytearray(value)
            value[:] = b"\x00" * len(value)
        elif isinstance(value, memoryview):
            payload = bytearray(value)
            if not value.readonly:
                value[:] = b"\x00" * len(value)
        else:
            raise TypeError("websocket-client returned an unsupported payload")
        return (
            int(opcode),
            f2529._InjectedFrameLease(
                int(opcode), time.monotonic_ns(), payload
            ),
        )

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._socket.close()  # type: ignore[attr-defined]


ConnectorProvider = Callable[[str], object]


def _selected_endpoint() -> object:
    selected = tuple(
        endpoint
        for endpoint in f24.ordered_candidates()
        if f24._endpoint_identity(endpoint) == f2520.SELECTED_ENDPOINT_IDENTITY
    )
    if len(selected) != 1:
        raise RuntimeError("the reviewed endpoint is absent or duplicated")
    return selected[0]


def _open_live_socket(role: str) -> _LiveSocketAdapter:
    if role not in f2531.BRANCH_ROLES:
        raise ValueError("unknown branch role")
    endpoint = _selected_endpoint()
    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, role))) & 0xFFFFFFFF
    opened = websocket.create_connection(
        f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
        enable_multithread=True,
    )
    return _LiveSocketAdapter(opened)


def build_authority_envelope() -> F2533AuthorityEnvelope:
    return F2533AuthorityEnvelope(
        REVIEWED_F2532_COMMIT,
        REVIEWED_AT,
        REVIEWED_F2532_SOURCE_SHA256,
        REVIEWED_F2532_PLAN_HASH,
        REVIEWED_F2532_INTEGRATION_SURFACE_HASH,
        EXPECTED_LIVE_SURFACE_HASH,
        EXPECTED_ENVIRONMENT,
        "run_reviewed_once(live_authorised=False)",
        (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "AUTHORITY_RECEIPT_FIRST",
            "TWO_FIXED_SND_CONNECTORS",
            "ONE_F2532_OUTCOME",
        ),
        ("live_authorised",),
        "TWO_SIMULTANEOUS_SND_CONNECTIONS_ONE_FROZEN_ENDPOINT",
        f2520.SELECTED_ENDPOINT_IDENTITY,
        "SAME_KIWI_DISTINCT_REFERENCE_AND_PERTURBED_DDC",
        "OPEN_HANDLE_A1_B_A2_DISTRIBUTED_WITNESS_THEN_TARGET",
        "F2532_INHERITED_UNCHANGED_NO_RUNTIME_OVERRIDE",
        f2531.PHASE_ORDER,
        0,
        0,
        1,
        "FIRST_TERMINAL_OUTCOME",
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE",
        f"{EVENT_PREFIX}_authority_envelope_frozen",
        "ABSENT_FROM_CAUSAL_PATH",
        "DESCRIPTIVE_HINT_UNUSED",
        False,
        RAW_RF_PERSISTENCE,
        (f2532.TRANSFORM_VERSION, TRANSFORM_VERSION),
    )


def _public_signature_is_exact() -> bool:
    parameters = tuple(inspect.signature(run_reviewed_once).parameters.values())
    return bool(
        len(parameters) == 1
        and parameters[0].name == "live_authorised"
        and parameters[0].kind is inspect.Parameter.KEYWORD_ONLY
        and parameters[0].default is False
    )


def assess() -> F2533Assessment:
    parent = f2532.assess()
    envelope = build_authority_envelope()
    parent_ready = bool(
        parent.exit is f2532.F2532Exit.RF_RESPONSE_INTEGRATED_OFFLINE
        and parent.plan is not None
        and parent.distributed_witness_reused
        and parent.target_reveal_order_enforced
        and parent.all_physical_outcomes_implemented
        and parent.no_public_execution_surface
        and not parent.live_execution_authorised
        and parent.raw_rf_persistence == RAW_RF_PERSISTENCE
    )
    ancestor = reviewed_commit_is_ancestor()
    git_clean = reviewed_source_git_diff_clean()
    source_match = current_f2532_source_sha256() == REVIEWED_F2532_SOURCE_SHA256
    plan_match = f2532.build_plan().plan_hash == REVIEWED_F2532_PLAN_HASH
    integration_match = (
        f2532._integration_surface_hash()
        == REVIEWED_F2532_INTEGRATION_SURFACE_HASH
    )
    live_match = current_live_surface_hash() == EXPECTED_LIVE_SURFACE_HASH
    envelope_match = envelope.receipt_hash == AUTHORITY_ENVELOPE_HASH
    environment_match = current_environment() == EXPECTED_ENVIRONMENT
    cwd_match = Path.cwd().resolve() == _repository_root()
    signature_match = _public_signature_is_exact()
    blockers = tuple(
        message
        for condition, message in (
            (parent_ready, "F2.5.32 offline prerequisite failed"),
            (ancestor, "reviewed F2.5.32 commit is not an ancestor"),
            (git_clean, "reviewed F2.5.32 source has a Git diff"),
            (source_match, "reviewed F2.5.32 source SHA-256 changed"),
            (plan_match, "reviewed F2.5.32 plan hash changed"),
            (integration_match, "reviewed F2.5.32 integration surface changed"),
            (live_match, "reviewed live authority surface changed"),
            (envelope_match, "authority envelope hash changed"),
            (environment_match, "reviewed numerical environment changed"),
            (cwd_match, "working directory is not the repository root"),
            (signature_match, "public caller overrides changed"),
        )
        if not condition
    )
    return F2533Assessment(
        (
            F2533Exit.EXACT_RF_RESPONSE_READY_FOR_SEPARATE_AUTHORITY
            if not blockers
            else F2533Exit.POST_COMMIT_SEAL_MISMATCH
        ),
        envelope,
        parent_ready,
        ancestor,
        git_clean,
        source_match,
        plan_match,
        integration_match,
        live_match,
        envelope_match,
        environment_match,
        cwd_match,
        signature_match,
        False,
        blockers,
        RAW_RF_PERSISTENCE,
    )


def default_receipt_path(created_at: datetime) -> Path:
    stamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        _repository_root()
        / "experiments"
        / "live_instrument"
        / "session_receipts"
        / f"gate-f2-5-33-{stamp}.jsonl"
    )


def _execute_with_dependencies(
    authority: F2533AuthorityEnvelope,
    *,
    connector_provider: ConnectorProvider,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None,
) -> F2533RunResult:
    """Internal deterministic seam; public execution fixes every dependency."""

    emitter = receipt.TerminalReceiptEmitter(receipt_path, mirror_sink=mirror_sink)
    opened: list[object] = []
    try:
        emitter(
            authority.receipt_first_event,
            {
                "authority_envelope": authority,
                "authority_envelope_hash": authority.receipt_hash,
                "separate_live_authority_asserted": True,
            },
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {
                role: pool.submit(connector_provider, role)
                for role in f2531.BRANCH_ROLES
            }
            connected: dict[str, object] = {}
            connection_errors: list[BaseException] = []
            for role in f2531.BRANCH_ROLES:
                try:
                    connected[role] = futures[role].result()
                    opened.append(connected[role])
                except BaseException as error:
                    connection_errors.append(error)
            if connection_errors:
                raise connection_errors[0]
            reference_socket = connected["reference"]
            perturbed_socket = connected["perturbed"]
        physical = f2532._run_open_handle_rf_injected(
            reference_socket=reference_socket,
            perturbed_socket=perturbed_socket,
        )
        emitter(f"{EVENT_PREFIX}_one_outcome", physical)
        artifact = emitter.finalize()
        return F2533RunResult(
            authority.receipt_hash,
            physical,
            artifact,
            True,
            RAW_RF_PERSISTENCE,
        )
    except BaseException as error:
        for socket in opened:
            try:
                socket.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise


def run_reviewed_once(*, live_authorised: bool = False) -> F2533RunResult:
    """Run the exact F2.5.32 vertical once after separate authority."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.33 requires separate exact live authorisation")
    assessment = assess()
    if assessment.exit is not F2533Exit.EXACT_RF_RESPONSE_READY_FOR_SEPARATE_AUTHORITY:
        raise RuntimeError(
            "post-commit authority seal no longer matches: "
            + "; ".join(assessment.blockers)
        )
    return _execute_with_dependencies(
        assessment.envelope,
        connector_provider=_open_live_socket,
        receipt_path=default_receipt_path(datetime.now(timezone.utc)),
        mirror_sink=print,
    )


def current_live_surface_hash() -> str:
    source = "\n".join(
        (
            inspect.getsource(_LiveSocketAdapter),
            inspect.getsource(_selected_endpoint),
            inspect.getsource(_open_live_socket),
            inspect.getsource(_execute_with_dependencies),
            inspect.getsource(run_reviewed_once),
        )
    )
    return sha256(source.encode()).hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        strict_json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


__all__ = [
    "F2533Assessment",
    "F2533AuthorityEnvelope",
    "F2533Exit",
    "F2533RunResult",
    "assess",
    "build_authority_envelope",
    "run_reviewed_once",
    "strict_json",
]
