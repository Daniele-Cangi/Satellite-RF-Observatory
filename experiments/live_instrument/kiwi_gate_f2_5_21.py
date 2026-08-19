"""Gate F2.5.21: post-commit seal for one prospective DDC intervention.

Assessment is offline. ``run_reviewed_once`` is the only live-capable surface
and refuses before receipt or connector access unless a separate authority is
asserted.  The caller cannot override endpoint, center, feature, delta,
threshold, duration, connector, receipt path, retry or outcome policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import importlib.metadata
import inspect
from pathlib import Path
import platform
import subprocess
from typing import Callable

import numpy as np
import scipy
import websocket

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_5_20 as f2520
from . import kiwi_probe as kiwi


F2521_TRANSFORM_VERSION = "gate-f2.5.21-prospective-authority-seal-v1"
REVIEWED_F2520_COMMIT = "92ef1e8500b6418f2ffe4c5232cbe010269b0178"
REVIEWED_AT = datetime(2026, 8, 18, 10, 50, 0, tzinfo=timezone.utc)
REVIEWED_CONTROL_SURFACE_HASH = (
    "a823572e04063ff24e7030b2531dc2351c52e1efad2c260cb77589214018224d"
)
REVIEWED_LIVE_SURFACE_HASH = (
    "fa4ab9e9dccd363b81f72998c89d3f986c1ed9506539d6a620a00822d443a315"
)
AUTHORITY_ENVELOPE_HASH = (
    "9299f8da2d66efb4d0b06a288b151110bb38c75a5254bf903af8ea03e66510d7"
)
EVENT_PREFIX = "gate_f2_5_21"
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
    ("experiments/live_instrument/kiwi_gate_f2_5_17.py", "a50791d750f2f4605f2d185b88d22364c8686ac465ceb0193c0c868c77cf2c3c"),
    ("experiments/live_instrument/kiwi_gate_f2_5_18.py", "c27be21031d3be5ce4a746cdeb9875c1bcee3a1d355a1d0d7e4b84e036bc18cd"),
    ("experiments/live_instrument/kiwi_gate_f2_5_20.py", "60067ab416089f32c7bbf7edcda1c859b595ca02b9ffbc2511ffca8dc181f662"),
    ("experiments/live_instrument/protocol_sources/gate_f2_5_17/manifest.json", "71a2e5f5748a99508377eeeb99404c5b72a81f0d580c4f7a84c1df62a60f4597"),
    ("experiments/live_instrument/protocol_sources/gate_f2_5_17/rx_sound_cmd.h", "351e40f6a10940ad9239e99bd1d62b406d93d7dd50b8a8f7cd2974f76b549b64"),
)
RUNTIME_CAUSAL_PATHS = tuple(path for path, _digest in EXPECTED_CAUSAL_SOURCE_SHA256)


class F2521Exit(str, Enum):
    EXACT_PROSPECTIVE_INTERVENTION_READY_FOR_SEPARATE_AUTHORITY = (
        "EXACT_PROSPECTIVE_INTERVENTION_READY_FOR_SEPARATE_AUTHORITY"
    )
    POST_COMMIT_SEAL_MISMATCH = "POST_COMMIT_SEAL_MISMATCH"


@dataclass(frozen=True, slots=True)
class F2521AuthorityEnvelope:
    reviewed_f2520_commit: str
    reviewed_at: datetime
    reviewed_prospective_envelope: f2520.F2520Envelope
    reviewed_control_surface_hash: str
    reviewed_live_surface_hash: str
    causal_source_sha256: tuple[tuple[str, str], ...]
    expected_environment: tuple[tuple[str, str], ...]
    authority_surface: str
    guard_order: tuple[str, ...]
    public_caller_overrides: tuple[str, ...]
    selected_endpoint_identity: str
    experiment_scope: str
    phase_order: tuple[str, ...]
    retry_budget: int
    postfreeze_retry_budget: int
    stop_condition: str
    receipt_path_policy: str
    receipt_first_event: str
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.reviewed_at)
        if self.reviewed_f2520_commit != REVIEWED_F2520_COMMIT:
            raise ValueError("reviewed F2.5.20 commit changed")
        if _control_surface_hash(self.reviewed_prospective_envelope) != (
            REVIEWED_CONTROL_SURFACE_HASH
        ):
            raise ValueError("reviewed prospective control surface changed")
        if self.reviewed_control_surface_hash != REVIEWED_CONTROL_SURFACE_HASH:
            raise ValueError("reviewed control-surface hash changed")
        if self.reviewed_live_surface_hash != REVIEWED_LIVE_SURFACE_HASH:
            raise ValueError("reviewed live-surface source hash changed")
        if self.causal_source_sha256 != EXPECTED_CAUSAL_SOURCE_SHA256:
            raise ValueError("causal-source seal changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("reviewed numerical environment changed")
        if self.authority_surface != "run_reviewed_once(live_authorised=False)":
            raise ValueError("authority surface changed")
        if self.guard_order != (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "PARENT_OUTCOME_HASH",
            "TERMINAL_RECEIPT_WITH_AUTHORITY_FIRST",
            "ONE_PROSPECTIVE_VERTICAL",
        ):
            raise ValueError("guard order changed")
        if self.public_caller_overrides != ("live_authorised",):
            raise ValueError("caller-controlled execution dimensions re-entered")
        if self.selected_endpoint_identity != f2520.SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("the qualified endpoint changed")
        if self.experiment_scope != (
            "REQUALIFY_DISCOVER_WITNESS_RETUNE_FREEZE_ONE_A1_B_A2"
        ):
            raise ValueError("authority expanded beyond the prospective vertical")
        if self.phase_order != f2520.PHASE_ORDER:
            raise ValueError("prospective phase order changed")
        if self.retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the reviewed experiment admits no retry")
        if self.stop_condition != "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW":
            raise ValueError("one-outcome stop changed")
        if self.receipt_path_policy != "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE":
            raise ValueError("receipt path policy changed")
        if self.receipt_first_event != f"{EVENT_PREFIX}_authority_envelope_frozen":
            raise ValueError("authority envelope must be the first receipt event")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2520.F2520_TRANSFORM_VERSION,
            F2521_TRANSFORM_VERSION,
        ):
            raise ValueError("authority transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2521Assessment:
    exit: F2521Exit
    envelope: F2521AuthorityEnvelope
    f2520_prerequisite_satisfied: bool
    reviewed_commit_is_ancestor: bool
    causal_git_diff_clean: bool
    causal_source_hashes_match: bool
    live_surface_hash_matches: bool
    numerical_environment_matches: bool
    working_directory_is_repository_root: bool
    parent_outcome_hash_matches: bool
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
    return _git_guard("merge-base", "--is-ancestor", REVIEWED_F2520_COMMIT, "HEAD")


def causal_git_diff_clean() -> bool:
    return _git_guard(
        "diff", "--quiet", REVIEWED_F2520_COMMIT, "--", *RUNTIME_CAUSAL_PATHS
    )


def _control_surface_hash(envelope: f2520.F2520Envelope) -> str:
    payload = asdict(envelope)
    del payload["created_at"]
    return f2._hash(payload)


def build_authority_envelope() -> F2521AuthorityEnvelope:
    reviewed = f2520.build_envelope(created_at=REVIEWED_AT)
    return F2521AuthorityEnvelope(
        REVIEWED_F2520_COMMIT,
        REVIEWED_AT,
        reviewed,
        _control_surface_hash(reviewed),
        REVIEWED_LIVE_SURFACE_HASH,
        EXPECTED_CAUSAL_SOURCE_SHA256,
        EXPECTED_ENVIRONMENT,
        "run_reviewed_once(live_authorised=False)",
        (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "PARENT_OUTCOME_HASH",
            "TERMINAL_RECEIPT_WITH_AUTHORITY_FIRST",
            "ONE_PROSPECTIVE_VERTICAL",
        ),
        ("live_authorised",),
        f2520.SELECTED_ENDPOINT_IDENTITY,
        "REQUALIFY_DISCOVER_WITNESS_RETUNE_FREEZE_ONE_A1_B_A2",
        f2520.PHASE_ORDER,
        0,
        0,
        "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW",
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE",
        f"{EVENT_PREFIX}_authority_envelope_frozen",
        RAW_RF_PERSISTENCE,
        (f2520.F2520_TRANSFORM_VERSION, F2521_TRANSFORM_VERSION),
    )


def assess_gate_f2_5_21() -> F2521Assessment:
    prior = f2520.assess_gate_f2_5_20()
    envelope = build_authority_envelope()
    prior_ready = (
        prior.exit
        is f2520.F2520Exit.PROSPECTIVE_VERTICAL_MATERIALIZED_OFFLINE
        and prior.parent_outcome_hash_matches
        and prior.corrected_dual_snd_reused
        and prior.discovery_is_new_and_ephemeral
        and prior.retune_uses_witness_before_target
        and prior.confirmation_is_postfreeze_and_single
        and prior.zero_retry
        and prior.post_commit_review_required
        and not prior.live_execution_authorised
    )
    ancestor = reviewed_commit_is_ancestor()
    git_clean = causal_git_diff_clean()
    try:
        hashes_match = current_causal_source_sha256() == EXPECTED_CAUSAL_SOURCE_SHA256
    except (OSError, UnicodeError):
        hashes_match = False
    live_surface_match = current_live_surface_hash() == REVIEWED_LIVE_SURFACE_HASH
    environment_match = current_environment() == EXPECTED_ENVIRONMENT
    cwd_match = Path.cwd().resolve() == _repository_root()
    parent_match = f2520.verify_parent_outcome()
    authority_hash_match = envelope.receipt_hash == AUTHORITY_ENVELOPE_HASH
    blockers = tuple(
        message
        for condition, message in (
            (prior_ready, "F2.5.20 offline prerequisite failed"),
            (ancestor, "reviewed F2.5.20 commit is not an ancestor of HEAD"),
            (git_clean, "reviewed causal files have a Git diff"),
            (hashes_match, "reviewed causal source SHA-256 changed"),
            (live_surface_match, "reviewed live-surface source changed"),
            (environment_match, "reviewed numerical environment changed"),
            (cwd_match, "working directory is not the repository root"),
            (parent_match, "frozen F2.5.19 outcome artifact changed"),
            (authority_hash_match, "authority envelope hash changed"),
        )
        if not condition
    )
    return F2521Assessment(
        (
            F2521Exit.EXACT_PROSPECTIVE_INTERVENTION_READY_FOR_SEPARATE_AUTHORITY
            if not blockers
            else F2521Exit.POST_COMMIT_SEAL_MISMATCH
        ),
        envelope,
        prior_ready,
        ancestor,
        git_clean,
        hashes_match,
        live_surface_match,
        environment_match,
        cwd_match,
        parent_match,
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
        / f"gate-f2-5-21-{stamp}.jsonl"
    )


def _live_connector_provider(
    _endpoint: kiwi.KiwiEndpoint,
    _role: str,
) -> Callable[..., object]:
    return websocket.create_connection


def _execute_reviewed(
    authority: F2521AuthorityEnvelope,
    *,
    connector_provider: object,
    websocket_module: object,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None,
) -> f2520.F2520Result:
    current = f2520.build_envelope(created_at=datetime.now(timezone.utc))
    if _control_surface_hash(current) != authority.reviewed_control_surface_hash:
        raise RuntimeError("prospective execution envelope diverged after assessment")
    return f2520.execute_prospective_injected(
        qualifier=lambda: f2520.qualify_selected_capability_injected(
            connector_provider=connector_provider,  # type: ignore[arg-type]
            websocket_module=websocket_module,
        ),
        receipt_path=receipt_path,
        mirror_sink=mirror_sink,
        authority_event=(
            authority.receipt_first_event,
            {
                "authority_envelope": authority,
                "authority_envelope_hash": authority.receipt_hash,
                "reviewed_control_surface_hash": authority.reviewed_control_surface_hash,
                "reviewed_live_surface_hash": authority.reviewed_live_surface_hash,
                "separate_live_authority_asserted": True,
            },
        ),
    )


def run_reviewed_once(*, live_authorised: bool = False) -> f2520.F2520Result:
    """Run exactly one sealed prospective vertical after separate authority."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.21 requires separate exact live authorisation")
    assessment = assess_gate_f2_5_21()
    if assessment.exit is not (
        F2521Exit.EXACT_PROSPECTIVE_INTERVENTION_READY_FOR_SEPARATE_AUTHORITY
    ):
        raise RuntimeError(
            "post-commit prospective seal no longer matches: "
            + "; ".join(assessment.blockers)
        )
    return _execute_reviewed(
        assessment.envelope,
        connector_provider=_live_connector_provider,
        websocket_module=websocket,
        receipt_path=default_receipt_path(datetime.now(timezone.utc)),
        mirror_sink=print,
    )


_LIVE_SURFACE_MEMBERS = (
    build_authority_envelope,
    assess_gate_f2_5_21,
    default_receipt_path,
    _live_connector_provider,
    _execute_reviewed,
    run_reviewed_once,
)


def current_live_surface_hash() -> str:
    source = "\n".join(
        inspect.getsource(member).replace("\r\n", "\n")
        for member in _LIVE_SURFACE_MEMBERS
    )
    return sha256(source.encode("utf-8")).hexdigest()
