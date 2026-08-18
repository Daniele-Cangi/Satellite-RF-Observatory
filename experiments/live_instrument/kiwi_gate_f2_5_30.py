"""Gate F2.5.30: post-commit sealability audit, offline only.

The reviewed F2.5.29 bridge is exact and useful, but it is not a sealable live
A1/B/A2 runtime: both injected branch sockets are closed before discovery and
retune callbacks run, and those callbacks receive no control handle.  This
module freezes that finding instead of manufacturing a nominal authority bit.
It has no connector, live runner, receipt writer or network import.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import inspect
import json
from pathlib import Path
import subprocess

from . import kiwi_gate_f2_5_28 as f2528
from . import kiwi_gate_f2_5_29 as f2529


TRANSFORM_VERSION = "gate-f2.5.30-live-surface-sealability-audit-v1"
REVIEWED_F2529_COMMIT = "c59a2f9bb6a6b72ea34d42dee936184bef5358fe"
REVIEWED_AT = datetime(2026, 8, 18, 22, 19, 3, tzinfo=timezone.utc)
REVIEWED_F2529_SOURCE_SHA256 = (
    "2defe3b394bc10ee2b238e4dc20022d1af697884785cfb39c156695c9c79bc22"
)
REVIEWED_F2529_ENVELOPE_HASH = (
    "da82ce3fa6f0608d8cc1bddce02cf4928f09795cd159ca8d421f5792a848b50d"
)
REVIEWED_F2529_INTEGRATION_SURFACE_HASH = f2529.EXPECTED_INTEGRATION_SURFACE_HASH
EXPECTED_AUDIT_SURFACE_HASH = (
    "d7739727eddd2ae1f6bd35237bbbd085b26c50205771e0140fbb7c273dd47832"
)
AUDIT_ENVELOPE_HASH = (
    "1f2fc9e84aa582d11aa841efba7400942a9305f6135025a25f086b7c9fea5e15"
)
RAW_RF_PERSISTENCE = "ZERO"

CLAUSE_ORDER = (
    "post_commit_lineage_exact",
    "relative_dual_snd_boundary_reusable",
    "channels_open_through_discovery",
    "channels_open_through_a1_b_a2",
    "retune_callback_has_control_handle",
    "public_authority_surface_sealable",
)


class F2530Exit(str, Enum):
    LIVE_SURFACE_NOT_SEALABLE = "LIVE_SURFACE_NOT_SEALABLE"
    POST_COMMIT_SEAL_MISMATCH = "POST_COMMIT_SEAL_MISMATCH"


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


def _strict_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value,
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
    return sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest()


def current_f2529_source_sha256() -> str:
    return _canonical_source_sha256(
        _repository_root()
        / "experiments"
        / "live_instrument"
        / "kiwi_gate_f2_5_29.py"
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
    return _git_guard("merge-base", "--is-ancestor", REVIEWED_F2529_COMMIT, "HEAD")


def reviewed_source_git_diff_clean() -> bool:
    return _git_guard(
        "diff",
        "--quiet",
        REVIEWED_F2529_COMMIT,
        "--",
        "experiments/live_instrument/kiwi_gate_f2_5_29.py",
    )


@dataclass(frozen=True, slots=True)
class ClauseReceipt:
    clause: str
    state: str
    statement: str
    evidence_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.clause not in CLAUSE_ORDER:
            raise ValueError("unknown sealability clause")
        if self.state not in {item.value for item in ClauseState}:
            raise ValueError("unknown clause state")
        for item in self.evidence_hashes:
            _sha256(item)


@dataclass(frozen=True, slots=True)
class F2530AuditEnvelope:
    reviewed_f2529_commit: str
    reviewed_at: datetime
    reviewed_f2529_source_sha256: str
    reviewed_f2529_envelope_hash: str
    reviewed_f2529_integration_surface_hash: str
    audit_surface_hash: str
    required_public_authority_surface: str
    permitted_public_caller_overrides: tuple[str, ...]
    required_channel_lifetime: str
    observed_channel_lifetime: str
    required_retune_control_path: str
    observed_retune_callback_surface: str
    public_execution_surface_materialized: bool
    live_execution_authorised: bool
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_f2529_commit != REVIEWED_F2529_COMMIT:
            raise ValueError("reviewed F2.5.29 commit changed")
        if self.reviewed_at != REVIEWED_AT:
            raise ValueError("review timestamp changed")
        if self.reviewed_f2529_source_sha256 != REVIEWED_F2529_SOURCE_SHA256:
            raise ValueError("reviewed source seal changed")
        if self.reviewed_f2529_envelope_hash != REVIEWED_F2529_ENVELOPE_HASH:
            raise ValueError("reviewed envelope seal changed")
        if self.reviewed_f2529_integration_surface_hash != (
            REVIEWED_F2529_INTEGRATION_SURFACE_HASH
        ):
            raise ValueError("reviewed integration surface changed")
        if self.audit_surface_hash != EXPECTED_AUDIT_SURFACE_HASH:
            raise ValueError("sealability audit surface changed")
        if self.required_public_authority_surface != (
            "run_reviewed_once(live_authorised=False)"
        ):
            raise ValueError("required authority boundary changed")
        if self.permitted_public_caller_overrides != ("live_authorised",):
            raise ValueError("caller-controlled experiment dimensions re-entered")
        if self.required_channel_lifetime != (
            "OPEN_FROM_DUAL_SND_THROUGH_DISCOVERY_AND_BOTH_A1_B_A2_BOUNDARIES"
        ):
            raise ValueError("required channel lifetime changed")
        if self.observed_channel_lifetime != (
            "CLOSED_AFTER_INITIAL_SND_BEFORE_DISCOVERY_AND_RETUNE"
        ):
            raise ValueError("observed channel lifetime changed")
        if self.required_retune_control_path != (
            "INTERNAL_FIXED_REFERENCE_AND_PERTURBED_BRANCH_HANDLES"
        ):
            raise ValueError("required retune control path changed")
        if self.observed_retune_callback_surface != "EPHEMERAL_IQ_VIEW_ONLY":
            raise ValueError("observed retune callback surface changed")
        if self.public_execution_surface_materialized:
            raise ValueError("an unsealable public execution surface was exposed")
        if self.live_execution_authorised:
            raise ValueError("offline audit cannot grant live authority")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the reviewed experiment permits no retry")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2528.TRANSFORM_VERSION,
            f2529.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("audit transform ledger changed")

    @property
    def envelope_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2530Assessment:
    exit: F2530Exit
    envelope: F2530AuditEnvelope | None
    reviewed_commit_is_ancestor: bool
    reviewed_source_git_diff_clean: bool
    reviewed_source_hash_matches: bool
    reviewed_parent_assessment_ready: bool
    reviewed_parent_envelope_matches: bool
    reviewed_integration_surface_matches: bool
    audit_surface_matches: bool
    audit_envelope_hash_matches: bool
    collector_closes_socket_before_return: bool
    one_shot_runs_after_both_collectors_return: bool
    callback_receives_control_handle: bool
    clauses: tuple[ClauseReceipt, ...]
    authority_surface_sealable: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    minimum_successor_change: tuple[str, ...]
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if tuple(item.clause for item in self.clauses) != CLAUSE_ORDER:
            raise ValueError("sealability clauses must be complete and ordered")
        if self.authority_surface_sealable or self.live_execution_authorised:
            raise ValueError("failed sealability cannot authorize execution")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


def _collector_closes_before_return() -> bool:
    source = inspect.getsource(f2529._collect_injected_branch)
    return "finally:" in source and "socket.close()" in source


def _one_shot_after_collections() -> bool:
    source = inspect.getsource(f2529._run_injected_phase_aware)
    return (
        source.index("reference_future.result()")
        < source.index("perturbed_future.result()")
        < source.index("f2528.run_one_shot_injected(")
    )


def _callback_has_control_handle() -> bool:
    source = inspect.getsource(f2528._EphemeralDualIQView)
    forbidden = ("socket", "connection", "send", "command_ledger")
    return any(item in source for item in forbidden)


def _audit_surface_hash() -> str:
    return sha256(inspect.getsource(assess).encode()).hexdigest()


def build_audit_envelope() -> F2530AuditEnvelope:
    return F2530AuditEnvelope(
        reviewed_f2529_commit=REVIEWED_F2529_COMMIT,
        reviewed_at=REVIEWED_AT,
        reviewed_f2529_source_sha256=REVIEWED_F2529_SOURCE_SHA256,
        reviewed_f2529_envelope_hash=REVIEWED_F2529_ENVELOPE_HASH,
        reviewed_f2529_integration_surface_hash=(
            REVIEWED_F2529_INTEGRATION_SURFACE_HASH
        ),
        audit_surface_hash=EXPECTED_AUDIT_SURFACE_HASH,
        required_public_authority_surface="run_reviewed_once(live_authorised=False)",
        permitted_public_caller_overrides=("live_authorised",),
        required_channel_lifetime=(
            "OPEN_FROM_DUAL_SND_THROUGH_DISCOVERY_AND_BOTH_A1_B_A2_BOUNDARIES"
        ),
        observed_channel_lifetime=(
            "CLOSED_AFTER_INITIAL_SND_BEFORE_DISCOVERY_AND_RETUNE"
        ),
        required_retune_control_path=(
            "INTERNAL_FIXED_REFERENCE_AND_PERTURBED_BRANCH_HANDLES"
        ),
        observed_retune_callback_surface="EPHEMERAL_IQ_VIEW_ONLY",
        public_execution_surface_materialized=False,
        live_execution_authorised=False,
        prefreeze_retry_budget=0,
        postfreeze_retry_budget=0,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
        transform_versions=(
            f2528.TRANSFORM_VERSION,
            f2529.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ),
    )


def assess() -> F2530Assessment:
    parent = f2529.assess()
    ancestor = reviewed_commit_is_ancestor()
    git_clean = reviewed_source_git_diff_clean()
    source_match = current_f2529_source_sha256() == REVIEWED_F2529_SOURCE_SHA256
    parent_ready = (
        parent.exit is f2529.F2529Exit.INJECTED_PHASE_BRIDGE_READY
        and parent.envelope is not None
    )
    parent_envelope_match = bool(
        parent.envelope is not None
        and parent.envelope.envelope_hash == REVIEWED_F2529_ENVELOPE_HASH
    )
    integration_match = (
        f2529._integration_surface_hash()
        == REVIEWED_F2529_INTEGRATION_SURFACE_HASH
    )
    surface_match = _audit_surface_hash() == EXPECTED_AUDIT_SURFACE_HASH
    candidate_envelope = build_audit_envelope()
    envelope_hash_match = candidate_envelope.envelope_hash == AUDIT_ENVELOPE_HASH
    collector_closes = _collector_closes_before_return()
    one_shot_after = _one_shot_after_collections()
    callback_control = _callback_has_control_handle()
    seal_blockers = tuple(
        message
        for condition, message in (
            (ancestor, "reviewed F2.5.29 commit is not an ancestor"),
            (git_clean, "reviewed F2.5.29 source has a Git diff"),
            (source_match, "reviewed F2.5.29 source SHA-256 changed"),
            (parent_ready, "reviewed F2.5.29 assessment failed"),
            (parent_envelope_match, "reviewed F2.5.29 envelope changed"),
            (integration_match, "reviewed integration surface changed"),
            (surface_match, "F2.5.30 audit surface changed"),
            (envelope_hash_match, "F2.5.30 audit envelope changed"),
        )
        if not condition
    )
    envelope = candidate_envelope if not seal_blockers else None
    evidence = (
        REVIEWED_F2529_SOURCE_SHA256,
        REVIEWED_F2529_ENVELOPE_HASH,
        REVIEWED_F2529_INTEGRATION_SURFACE_HASH,
    )
    clauses = (
        ClauseReceipt(
            CLAUSE_ORDER[0],
            (
                ClauseState.SATISFIED.value
                if not seal_blockers
                else ClauseState.UNSATISFIED.value
            ),
            "commit, source, envelope and integration lineage are exact",
            evidence,
        ),
        ClauseReceipt(
            CLAUSE_ORDER[1],
            ClauseState.SATISFIED.value if parent_ready else ClauseState.UNSATISFIED.value,
            "the injected relative dual-SND gate remains reusable offline",
            (REVIEWED_F2529_ENVELOPE_HASH,),
        ),
        ClauseReceipt(
            CLAUSE_ORDER[2],
            ClauseState.UNSATISFIED.value,
            "both branch collectors close their sockets before discovery",
            (REVIEWED_F2529_INTEGRATION_SURFACE_HASH,),
        ),
        ClauseReceipt(
            CLAUSE_ORDER[3],
            ClauseState.UNSATISFIED.value,
            "closed branches cannot witness live A1_TO_B and B_TO_A2 commands",
            (REVIEWED_F2529_INTEGRATION_SURFACE_HASH,),
        ),
        ClauseReceipt(
            CLAUSE_ORDER[4],
            ClauseState.UNSATISFIED.value,
            "the retune callback receives an IQ view and no branch control handle",
            (REVIEWED_F2529_SOURCE_SHA256,),
        ),
        ClauseReceipt(
            CLAUSE_ORDER[5],
            ClauseState.NOT_EVALUATED.value,
            "no public authority surface may be sealed until channel lifetime is fixed",
            (),
        ),
    )
    return F2530Assessment(
        exit=(
            F2530Exit.POST_COMMIT_SEAL_MISMATCH
            if seal_blockers
            else F2530Exit.LIVE_SURFACE_NOT_SEALABLE
        ),
        envelope=envelope,
        reviewed_commit_is_ancestor=ancestor,
        reviewed_source_git_diff_clean=git_clean,
        reviewed_source_hash_matches=source_match,
        reviewed_parent_assessment_ready=parent_ready,
        reviewed_parent_envelope_matches=parent_envelope_match,
        reviewed_integration_surface_matches=integration_match,
        audit_surface_matches=surface_match,
        audit_envelope_hash_matches=envelope_hash_match,
        collector_closes_socket_before_return=collector_closes,
        one_shot_runs_after_both_collectors_return=one_shot_after,
        callback_receives_control_handle=callback_control,
        clauses=clauses,
        authority_surface_sealable=False,
        live_execution_authorised=False,
        blockers=seal_blockers,
        authorised_claims=(
            "F2.5.29 is exact and its relative-time boundary is reusable",
            "the current branch lifetime ends before discovery and retune",
            "the current callback surface cannot issue or witness a live retune",
            "no authority surface was materialized",
        ),
        unauthorised_claims=(
            "F2.5.29 can execute a live A1/B/A2 intervention",
            "a live_authorised bit would reach a physical outcome",
            "the selected endpoint is currently reachable",
            "any RF feature or DDC-location hypothesis was evaluated",
        ),
        minimum_successor_change=(
            "return two owned branch control handles from initial dual-SND admission",
            "keep both handles open through discovery and both retune boundaries",
            "allow only an internal frozen command executor to retune the perturbed branch",
            "close and release both branches in one outer finally after the terminal outcome",
            "then seal exactly one default-refusing authority bit",
        ),
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


__all__ = [
    "ClauseReceipt",
    "ClauseState",
    "F2530Assessment",
    "F2530AuditEnvelope",
    "F2530Exit",
    "assess",
    "build_audit_envelope",
]
