"""Gate F2.5.15: post-commit seal and exact authority surface.

Import and assessment are offline.  ``run_reviewed_once`` is the sole public
authority surface and refuses before receipt creation or connector access
unless the caller supplies a separate live authorisation.  The function has no
endpoint, plan, path, threshold, retry, connector or framing override.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import importlib.metadata
from pathlib import Path
import platform
import subprocess
from typing import Callable

import numpy as np
import scipy
import websocket

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_3_1 as f2531
from . import kiwi_gate_f2_5_14 as f2514
from . import kiwi_probe as kiwi


F2515_TRANSFORM_VERSION = "gate-f2.5.15-post-commit-authority-seal-v1"
REVIEWED_F2514_COMMIT = "d32dba647a9a49d8d980325567a0ae09f3a08c20"
REVIEWED_AT = datetime(2026, 8, 17, tzinfo=timezone.utc)
REVIEWED_CONTROL_SURFACE_HASH = (
    "9104f5ff98a5415a558112a38992d2d598b5f7c467c474198a080c96cf531bf0"
)
EVENT_PREFIX = "gate_f2_5_15"
RAW_RF_PERSISTENCE = "ZERO"
EXPECTED_ENVIRONMENT = (
    ("python", "3.13.5"),
    ("numpy", "2.3.3"),
    ("scipy", "1.17.1"),
    ("websocket-client", "1.8.0"),
)
EXPECTED_CAUSAL_SOURCE_SHA256 = (
    ("experiments/live_instrument/models.py", "26bc294a0ab7a64a61af36ab20bac91e589feca805ef4c9659ea0845f4a59cf7"),
    ("experiments/live_instrument/kiwi_probe.py", "85e861a112be31330827c17d902e377c12f9e19bda4e69d2ca1f0c01b93b752a"),
    ("experiments/live_instrument/kiwi_gate_f2.py", "7f9335c4182df4889ecfb7edcb0b035c36f251581d158d21bc5938f4a8d4fb37"),
    ("experiments/live_instrument/kiwi_gate_f2_2.py", "6b2c25b725f838b8049e0db4e68d6570d5ec86c95c4220f680e605b8d43090a6"),
    ("experiments/live_instrument/kiwi_gate_f2_3.py", "d99def61da0dcf267c4c3d952103fec652a5c09af5e3bc680751da2879f3b200"),
    ("experiments/live_instrument/kiwi_gate_f2_4.py", "229466f44c978da7b06c061a54f2d451c43717b5ccc4057aa41a2eb228db04d8"),
    ("experiments/live_instrument/kiwi_gate_f2_5.py", "83917073205563a14a571ef348fac9f36c391983537cbe846d2719f710d38c4c"),
    ("experiments/live_instrument/kiwi_gate_f2_5_1.py", "89ecd6111b27423d60de9b85dbd89a0a595d19384f65b91e142b654d0c3e8186"),
    ("experiments/live_instrument/kiwi_gate_f2_5_2.py", "b838c0c86e2ef93ed5187cf7ed93d85dc19b30116734eeb03bf0ee528f7a6120"),
    ("experiments/live_instrument/kiwi_gate_f2_5_3.py", "338826c7dc437e1e2d55436f42d799ae83ac553c027355a6ad9262406f260420"),
    ("experiments/live_instrument/kiwi_gate_f2_5_3_1.py", "d7c14204ce40c0854fa72e539d499fc04a2d458b0c933bef34e65e52fb6e0615"),
    ("experiments/live_instrument/kiwi_gate_f2_5_6.py", "aeab954b2a5e10706e7cad826e1203ab893c6bb7655b685d0a9f02268b1af35d"),
    ("experiments/live_instrument/kiwi_gate_f2_5_7.py", "e53f75df69f5636002e95df1f095a3023d5785feb2dbf16e5b8e1d05c4b07e55"),
    ("experiments/live_instrument/kiwi_gate_f2_5_8.py", "3aac09c72725171e1cebcb442a0d3bab36b12cc07099318ebc0b5645873d4b3c"),
    ("experiments/live_instrument/kiwi_gate_f2_5_12.py", "11aabcb0bd05ea2353cfbc184bb8e9a889fd72757625aa33861a66e38aec1323"),
    ("experiments/live_instrument/kiwi_gate_f2_5_13.py", "147b966aa792270093bbf468bc2b391f04885f5e104486b0d3e880a90dcfa433"),
    ("experiments/live_instrument/kiwi_gate_f2_5_14.py", "5031f93517b552c3ab713a5a590bd145378307fb5cad230beeff830a10780a45"),
)
RUNTIME_CAUSAL_PATHS = tuple(path for path, _digest in EXPECTED_CAUSAL_SOURCE_SHA256)


class F2515Exit(str, Enum):
    EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY = (
        "EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY"
    )
    POST_COMMIT_SEAL_MISMATCH = "POST_COMMIT_SEAL_MISMATCH"


@dataclass(frozen=True, slots=True)
class F2515AuthorityEnvelope:
    reviewed_f2514_commit: str
    reviewed_at: datetime
    reviewed_control_envelope: f2514.F2514ExecutionEnvelope
    reviewed_control_surface_hash: str
    causal_source_sha256: tuple[tuple[str, str], ...]
    expected_environment: tuple[tuple[str, str], ...]
    authority_surface: str
    guard_order: tuple[str, ...]
    connector_policy: str
    receipt_path_policy: str
    receipt_first_event: str
    public_caller_overrides: tuple[str, ...]
    retry_budget: int
    postfreeze_retry_budget: int
    stop_condition: str
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.reviewed_at)
        if self.reviewed_f2514_commit != REVIEWED_F2514_COMMIT:
            raise ValueError("reviewed F2.5.14 commit changed")
        if self.reviewed_at != REVIEWED_AT:
            raise ValueError("review timestamp changed")
        if _control_surface_hash(self.reviewed_control_envelope) != (
            REVIEWED_CONTROL_SURFACE_HASH
        ):
            raise ValueError("reviewed F2.5.14 control surface changed")
        if self.reviewed_control_surface_hash != REVIEWED_CONTROL_SURFACE_HASH:
            raise ValueError("reviewed control hash changed")
        if self.causal_source_sha256 != EXPECTED_CAUSAL_SOURCE_SHA256:
            raise ValueError("causal-source seal changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("reviewed environment changed")
        if self.authority_surface != "run_reviewed_once(live_authorised=False)":
            raise ValueError("authority surface changed")
        if self.guard_order != (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "TERMINAL_RECEIPT_OPEN",
            "DIRECT_DUAL_SND_CONNECTORS",
        ):
            raise ValueError("guard order changed")
        if self.connector_policy != "WEBSOCKET_CREATE_CONNECTION_PER_ROLE_NO_OVERRIDE":
            raise ValueError("connector policy changed")
        if self.receipt_path_policy != "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE":
            raise ValueError("receipt path policy changed")
        if self.receipt_first_event != f"{EVENT_PREFIX}_authority_envelope_frozen":
            raise ValueError("authority envelope must be the first receipt event")
        if self.public_caller_overrides != ("live_authorised",):
            raise ValueError("caller-controlled execution dimensions re-entered")
        if self.retry_budget != 0 or self.postfreeze_retry_budget != 0:
            raise ValueError("the reviewed execution admits no retry")
        if self.stop_condition != "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED":
            raise ValueError("one-outcome stop changed")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2514.F2514_TRANSFORM_VERSION,
            F2515_TRANSFORM_VERSION,
        ):
            raise ValueError("authority transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2515Assessment:
    exit: F2515Exit
    envelope: F2515AuthorityEnvelope
    f2514_prerequisite_satisfied: bool
    reviewed_commit_is_ancestor: bool
    causal_git_diff_clean: bool
    causal_source_hashes_match: bool
    numerical_environment_matches: bool
    working_directory_is_repository_root: bool
    caller_overrides_removed: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_source_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return sha256(text.encode("utf-8")).hexdigest()


def current_causal_source_sha256() -> tuple[tuple[str, str], ...]:
    root = _repository_root()
    return tuple(
        (relative, _canonical_source_sha256(root / relative))
        for relative in RUNTIME_CAUSAL_PATHS
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
    return _git_guard("merge-base", "--is-ancestor", REVIEWED_F2514_COMMIT, "HEAD")


def causal_git_diff_clean() -> bool:
    return _git_guard(
        "diff",
        "--quiet",
        REVIEWED_F2514_COMMIT,
        "--",
        *RUNTIME_CAUSAL_PATHS,
    )


def _control_surface_hash(envelope: f2514.F2514ExecutionEnvelope) -> str:
    payload = asdict(envelope)
    del payload["created_at"]
    return f2._hash(payload)


def build_authority_envelope() -> F2515AuthorityEnvelope:
    reviewed = f2514.build_execution_envelope(created_at=REVIEWED_AT)
    return F2515AuthorityEnvelope(
        REVIEWED_F2514_COMMIT,
        REVIEWED_AT,
        reviewed,
        _control_surface_hash(reviewed),
        EXPECTED_CAUSAL_SOURCE_SHA256,
        EXPECTED_ENVIRONMENT,
        "run_reviewed_once(live_authorised=False)",
        (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "TERMINAL_RECEIPT_OPEN",
            "DIRECT_DUAL_SND_CONNECTORS",
        ),
        "WEBSOCKET_CREATE_CONNECTION_PER_ROLE_NO_OVERRIDE",
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE",
        f"{EVENT_PREFIX}_authority_envelope_frozen",
        ("live_authorised",),
        0,
        0,
        "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED",
        RAW_RF_PERSISTENCE,
        (f2514.F2514_TRANSFORM_VERSION, F2515_TRANSFORM_VERSION),
    )


def assess_gate_f2_5_15(
    prerequisite: f2514.F2514Assessment | None = None,
) -> F2515Assessment:
    prior = prerequisite or f2514.assess_gate_f2_5_14()
    envelope = build_authority_envelope()
    prior_ready = (
        prior.exit
        is f2514.F2514Exit.DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE
        and prior.two_branch_concurrency_materialized
        and prior.candidate_loop_materialized
        and prior.terminal_receipt_materialized
        and not prior.live_execution_authorised
    )
    ancestor = reviewed_commit_is_ancestor()
    git_clean = causal_git_diff_clean()
    try:
        hashes_match = current_causal_source_sha256() == EXPECTED_CAUSAL_SOURCE_SHA256
    except (OSError, UnicodeError):
        hashes_match = False
    environment_match = current_environment() == EXPECTED_ENVIRONMENT
    cwd_match = Path.cwd().resolve() == _repository_root()
    blockers = tuple(
        message
        for condition, message in (
            (prior_ready, "F2.5.14 offline prerequisite failed"),
            (ancestor, "reviewed F2.5.14 commit is not an ancestor of HEAD"),
            (git_clean, "reviewed causal files have a Git diff"),
            (hashes_match, "reviewed causal source SHA-256 changed"),
            (environment_match, "reviewed numerical environment changed"),
            (cwd_match, "working directory is not the repository root"),
        )
        if not condition
    )
    return F2515Assessment(
        (
            F2515Exit.EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY
            if not blockers
            else F2515Exit.POST_COMMIT_SEAL_MISMATCH
        ),
        envelope,
        prior_ready,
        ancestor,
        git_clean,
        hashes_match,
        environment_match,
        cwd_match,
        True,
        False,
        blockers,
    )


def default_receipt_path(created_at: datetime) -> Path:
    stamp = f2._utc(created_at).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        _repository_root()
        / "experiments"
        / "live_instrument"
        / "session_receipts"
        / f"gate-f2-5-15-{stamp}.jsonl"
    )


def _live_connector_provider(
    _endpoint: kiwi.KiwiEndpoint,
    _role: str,
) -> Callable[..., object]:
    return websocket.create_connection


def _execute_with_dependencies(
    authority: F2515AuthorityEnvelope,
    *,
    connector_provider: f2514.ConnectorProvider,
    websocket_module: object,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None,
) -> f2514.F2514Result:
    """Internal synthetic seam; the public authority surface supplies all values."""

    created_at = datetime.now(timezone.utc)
    execution = f2514.build_execution_envelope(created_at=created_at)
    if _control_surface_hash(execution) != authority.reviewed_control_surface_hash:
        raise RuntimeError("live execution envelope diverged after assessment")
    emitter = f2531.TerminalReceiptEmitter(receipt_path, mirror_sink=mirror_sink)
    attempts: list[f2514.DualSemanticReceipt] = []
    selected: str | None = None
    try:
        emitter(
            authority.receipt_first_event,
            {
                "authority_envelope": authority,
                "authority_envelope_hash": authority.receipt_hash,
                "execution_envelope": execution,
                "execution_control_surface_hash": _control_surface_hash(execution),
                "separate_live_authority_asserted": True,
            },
        )
        for endpoint in f24.ordered_candidates():
            opened = f2514.open_dual_semantic_injected(
                endpoint,
                connector_provider=connector_provider,
                websocket_module=websocket_module,
            )
            attempts.append(opened.receipt)
            emitter(f"{EVENT_PREFIX}_candidate_pair", opened.receipt)
            if opened.receipt.state is f2514.PairState.DUAL_READY:
                selected = opened.receipt.endpoint_identity
                opened.close()
                break
            opened.close()
        frozen_attempts = tuple(attempts)
        physical = f2514.CandidateLoopReceipt(
            execution.envelope_hash,
            (
                f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
                if selected is not None
                else f2514._negative_outcome(frozen_attempts)
            ),
            frozen_attempts,
            selected,
            True,
        )
        emitter(f"{EVENT_PREFIX}_one_outcome", physical)
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    return f2514.F2514Result(execution, physical, emitter.finalize())


def run_reviewed_once(*, live_authorised: bool = False) -> f2514.F2514Result:
    """Execute the sealed candidate loop once, after exact separate authority."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.15 requires separate exact live authorisation")
    assessment = assess_gate_f2_5_15()
    if assessment.exit is not (
        F2515Exit.EXACT_AUTHORITY_SURFACE_READY_FOR_SEPARATE_AUTHORITY
    ):
        raise RuntimeError(
            "post-commit authority seal no longer matches: "
            + "; ".join(assessment.blockers)
        )
    created_at = datetime.now(timezone.utc)
    return _execute_with_dependencies(
        assessment.envelope,
        connector_provider=_live_connector_provider,
        websocket_module=websocket,
        receipt_path=default_receipt_path(created_at),
        mirror_sink=print,
    )
