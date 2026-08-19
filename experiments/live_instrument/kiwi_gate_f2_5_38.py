"""Gate F2.5.38: post-commit seal for the corrected F2.5.37 vertical.

Assessment is offline. ``run_reviewed_once`` is the sole live-capable surface
and refuses before assessment, receipt creation or connector access unless a
later, separate authority is asserted. This module grants and consumes none.
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
from typing import Callable

import numpy as np
import scipy

from . import kiwi_gate_f2_5_3_1 as receipt
from . import kiwi_gate_f2_5_31 as f2531
from . import kiwi_gate_f2_5_33 as f2533
from . import kiwi_gate_f2_5_35 as f2535
from . import kiwi_gate_f2_5_37 as f2537
from .models import strict_json_value


TRANSFORM_VERSION = "gate-f2.5.38-corrected-vertical-post-commit-seal-v1"
REVIEWED_F2537_COMMIT = "897a7f14bbf323bce1cf40009b93168c1c5d7676"
REVIEWED_AT = datetime(2026, 8, 19, 9, 0, 53, tzinfo=timezone.utc)
REVIEWED_F2537_SOURCE_SHA256 = (
    "1747833281b13525113ecd358446ba1cd828a34aa7eba3f22854d5f7de195d8b"
)
REVIEWED_F2537_PLAN_HASH = (
    "a400327530a1d1db0949197d65fbaed9b09723a4cd4f7608d7ebdef426520d78"
)
REVIEWED_CONTINUITY_SURFACE_HASH = (
    "cec12d24da7e4710d705d510085e49fd77b2b96189684c9e06b89fabc5e1e515"
)
REVIEWED_SCOPE_SURFACE_HASH = (
    "4c06a83f0e5c5cd417d45e46dd0d2279bd91efb34c48e976f6ed6d4cdb1bc366"
)
REVIEWED_INTEGRATION_SURFACE_HASH = (
    "a1fdfb2a626edc0c13b6c7f304cb243677a762fed9e451dab790be2183c474fd"
)
REVIEWED_F2533_CONNECTOR_SOURCE_SHA256 = (
    "a69f25b9a98482b84dc8c3b404984fe72c5b555a45f28efd27c5d0ae15e27917"
)
EXPECTED_LIVE_SURFACE_HASH = (
    "196c8bcf1f709f6116bb83599e856196c39683d189a14877fa408338b5720508"
)
AUTHORITY_ENVELOPE_HASH = (
    "e2a1ee4e835f32960a00986fbfbe514feb838af6026419d8e958cface127f91d"
)
EXPECTED_ENVIRONMENT = (
    ("python", "3.13.5"),
    ("numpy", "2.3.3"),
    ("scipy", "1.17.1"),
    ("websocket-client", "1.8.0"),
)
EVENT_PREFIX = "gate_f2_5_38"
RAW_RF_PERSISTENCE = "ZERO"


class F2538Exit(str, Enum):
    CORRECTED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY = (
        "CORRECTED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY"
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


def current_f2537_source_sha256() -> str:
    return _canonical_source_sha256(
        Path(__file__).resolve().parent / "kiwi_gate_f2_5_37.py"
    )


def current_f2533_connector_source_sha256() -> str:
    return _canonical_source_sha256(
        Path(__file__).resolve().parent / "kiwi_gate_f2_5_33.py"
    )


def current_continuity_surface_hash() -> str:
    return sha256(
        inspect.getsource(f2537.evaluate_full_session_continuity).encode()
    ).hexdigest()


def current_scope_surface_hash() -> str:
    return sha256(
        inspect.getsource(f2537._corrected_continuity_scope).encode()
    ).hexdigest()


def current_integration_surface_hash() -> str:
    return sha256(
        inspect.getsource(f2537._run_corrected_audited_injected).encode()
    ).hexdigest()


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
        "merge-base", "--is-ancestor", REVIEWED_F2537_COMMIT, "HEAD"
    )


def reviewed_source_git_diff_clean() -> bool:
    return _git_guard(
        "diff",
        "--quiet",
        REVIEWED_F2537_COMMIT,
        "--",
        "experiments/live_instrument/kiwi_gate_f2_5_37.py",
    )


@dataclass(frozen=True, slots=True)
class F2538AuthorityEnvelope:
    reviewed_f2537_commit: str
    reviewed_at: datetime
    reviewed_f2537_source_sha256: str
    reviewed_f2537_plan_hash: str
    reviewed_continuity_surface_hash: str
    reviewed_scope_surface_hash: str
    reviewed_integration_surface_hash: str
    reviewed_connector_source_sha256: str
    reviewed_live_surface_hash: str
    expected_environment: tuple[tuple[str, str], ...]
    authority_surface: str
    guard_order: tuple[str, ...]
    public_caller_overrides: tuple[str, ...]
    connector_policy: str
    endpoint_identity: str
    channel_topology: str
    experiment_scope: str
    continuity_policy: str
    threshold_policy: str
    audit_policy: str
    phase_order: tuple[str, ...]
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    outcome_windows: int
    stop_condition: str
    receipt_path_policy: str
    receipt_first_event: str
    receipt_content: str
    waterfall_role: str
    ext_api_role: str
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_f2537_commit != REVIEWED_F2537_COMMIT:
            raise ValueError("reviewed F2.5.37 commit changed")
        if self.reviewed_at != REVIEWED_AT:
            raise ValueError("review timestamp changed")
        comparisons = (
            (self.reviewed_f2537_source_sha256, REVIEWED_F2537_SOURCE_SHA256, "F2.5.37 source"),
            (self.reviewed_f2537_plan_hash, REVIEWED_F2537_PLAN_HASH, "F2.5.37 plan"),
            (self.reviewed_continuity_surface_hash, REVIEWED_CONTINUITY_SURFACE_HASH, "continuity surface"),
            (self.reviewed_scope_surface_hash, REVIEWED_SCOPE_SURFACE_HASH, "scope surface"),
            (self.reviewed_integration_surface_hash, REVIEWED_INTEGRATION_SURFACE_HASH, "integration surface"),
            (self.reviewed_connector_source_sha256, REVIEWED_F2533_CONNECTOR_SOURCE_SHA256, "connector source"),
            (self.reviewed_live_surface_hash, EXPECTED_LIVE_SURFACE_HASH, "live surface"),
        )
        for actual, expected, label in comparisons:
            if actual != expected:
                raise ValueError(f"reviewed {label} changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("numerical environment changed")
        if self.authority_surface != "run_reviewed_once(live_authorised=False)":
            raise ValueError("authority surface changed")
        if self.guard_order != (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "AUTHORITY_RECEIPT_FIRST",
            "TWO_FIXED_SND_CONNECTORS",
            "ONE_CORRECTED_F2537_OUTCOME",
        ):
            raise ValueError("authority guard order changed")
        if self.public_caller_overrides != ("live_authorised",):
            raise ValueError("caller-controlled experiment dimensions re-entered")
        if self.connector_policy != "REUSE_REVIEWED_F2533_DUAL_SND_CONNECTOR":
            raise ValueError("connector policy changed")
        if self.endpoint_identity != "dl1bajkiwisdr.ddns.net:8074":
            raise ValueError("reviewed endpoint changed")
        if self.channel_topology != "SAME_KIWI_DISTINCT_REFERENCE_AND_PERTURBED_DDC":
            raise ValueError("causal topology changed")
        if self.experiment_scope != "CORRECTED_AUDITED_A1_B_A2_ONE_OUTCOME":
            raise ValueError("authority expanded beyond the corrected vertical")
        if self.continuity_policy != "ONE_F2527_RULE_FOR_INITIAL_AND_FULL_SESSION":
            raise ValueError("timestamp semantics changed")
        if self.threshold_policy != "F2532_INHERITED_UNCHANGED_NO_RUNTIME_OVERRIDE":
            raise ValueError("threshold policy changed")
        if self.audit_policy != "DECISION_FIRST_SCALAR_SIBLING_NONAUTHORITATIVE":
            raise ValueError("audit policy changed")
        if self.phase_order != f2531.PHASE_ORDER:
            raise ValueError("phase order changed")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the corrected vertical permits no retry")
        if self.outcome_windows != 1 or self.stop_condition != "FIRST_TERMINAL_OUTCOME":
            raise ValueError("one-outcome stop changed")
        if self.receipt_path_policy != "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE":
            raise ValueError("receipt path policy changed")
        if self.receipt_first_event != f"{EVENT_PREFIX}_authority_envelope_frozen":
            raise ValueError("authority envelope must be first")
        if self.receipt_content != "DECISION_PLUS_SCALAR_AUDIT_HASHES_ONLY":
            raise ValueError("receipt content boundary changed")
        if self.waterfall_role != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("waterfall re-entered the causal path")
        if self.ext_api_role != "DESCRIPTIVE_HINT_UNUSED":
            raise ValueError("ext_api became multichannel truth")
        if self.live_execution_authorised:
            raise ValueError("offline seal cannot consume authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2535.TRANSFORM_VERSION,
            f2537.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("authority transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2538Assessment:
    exit: F2538Exit
    envelope: F2538AuthorityEnvelope
    f2537_prerequisite_satisfied: bool
    reviewed_commit_is_ancestor: bool
    reviewed_source_git_diff_clean: bool
    reviewed_source_hash_matches: bool
    reviewed_plan_hash_matches: bool
    continuity_surface_matches: bool
    scope_surface_matches: bool
    integration_surface_matches: bool
    connector_source_matches: bool
    live_surface_hash_matches: bool
    authority_envelope_hash_matches: bool
    numerical_environment_matches: bool
    working_directory_is_repository_root: bool
    caller_overrides_removed: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


@dataclass(frozen=True, slots=True)
class F2538RunResult:
    authority_envelope_hash: str
    corrected_result: f2535.F2535RunResult
    receipt_artifact: receipt.ClosedArtifactReceipt
    authority_consumed: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.authority_envelope_hash)
        if not self.authority_consumed:
            raise ValueError("live runner result requires consumed authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


ConnectorProvider = Callable[[str], object]


def build_authority_envelope() -> F2538AuthorityEnvelope:
    return F2538AuthorityEnvelope(
        REVIEWED_F2537_COMMIT,
        REVIEWED_AT,
        REVIEWED_F2537_SOURCE_SHA256,
        REVIEWED_F2537_PLAN_HASH,
        REVIEWED_CONTINUITY_SURFACE_HASH,
        REVIEWED_SCOPE_SURFACE_HASH,
        REVIEWED_INTEGRATION_SURFACE_HASH,
        REVIEWED_F2533_CONNECTOR_SOURCE_SHA256,
        EXPECTED_LIVE_SURFACE_HASH,
        EXPECTED_ENVIRONMENT,
        "run_reviewed_once(live_authorised=False)",
        (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "AUTHORITY_RECEIPT_FIRST",
            "TWO_FIXED_SND_CONNECTORS",
            "ONE_CORRECTED_F2537_OUTCOME",
        ),
        ("live_authorised",),
        "REUSE_REVIEWED_F2533_DUAL_SND_CONNECTOR",
        "dl1bajkiwisdr.ddns.net:8074",
        "SAME_KIWI_DISTINCT_REFERENCE_AND_PERTURBED_DDC",
        "CORRECTED_AUDITED_A1_B_A2_ONE_OUTCOME",
        "ONE_F2527_RULE_FOR_INITIAL_AND_FULL_SESSION",
        "F2532_INHERITED_UNCHANGED_NO_RUNTIME_OVERRIDE",
        "DECISION_FIRST_SCALAR_SIBLING_NONAUTHORITATIVE",
        f2531.PHASE_ORDER,
        0,
        0,
        1,
        "FIRST_TERMINAL_OUTCOME",
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE",
        f"{EVENT_PREFIX}_authority_envelope_frozen",
        "DECISION_PLUS_SCALAR_AUDIT_HASHES_ONLY",
        "ABSENT_FROM_CAUSAL_PATH",
        "DESCRIPTIVE_HINT_UNUSED",
        False,
        RAW_RF_PERSISTENCE,
        (f2535.TRANSFORM_VERSION, f2537.TRANSFORM_VERSION, TRANSFORM_VERSION),
    )


def _public_signature_is_exact() -> bool:
    signature = inspect.signature(run_reviewed_once)
    if tuple(signature.parameters) != ("live_authorised",):
        return False
    parameter = signature.parameters["live_authorised"]
    return (
        parameter.kind is inspect.Parameter.KEYWORD_ONLY
        and parameter.default is False
    )


def assess() -> F2538Assessment:
    envelope = build_authority_envelope()
    prerequisite = (
        f2537.assess().exit
        is f2537.F2537Exit.CONTINUITY_NORMALIZATION_INTEGRATED_OFFLINE
    )
    ancestor = reviewed_commit_is_ancestor()
    source_clean = reviewed_source_git_diff_clean()
    source_match = current_f2537_source_sha256() == REVIEWED_F2537_SOURCE_SHA256
    plan_match = f2537.build_plan().plan_hash == REVIEWED_F2537_PLAN_HASH
    continuity_match = current_continuity_surface_hash() == REVIEWED_CONTINUITY_SURFACE_HASH
    scope_match = current_scope_surface_hash() == REVIEWED_SCOPE_SURFACE_HASH
    integration_match = current_integration_surface_hash() == REVIEWED_INTEGRATION_SURFACE_HASH
    connector_match = current_f2533_connector_source_sha256() == REVIEWED_F2533_CONNECTOR_SOURCE_SHA256
    live_match = current_live_surface_hash() == EXPECTED_LIVE_SURFACE_HASH
    envelope_match = envelope.receipt_hash == AUTHORITY_ENVELOPE_HASH
    environment_match = current_environment() == EXPECTED_ENVIRONMENT
    cwd_match = Path.cwd().resolve() == _repository_root()
    signature_match = _public_signature_is_exact()
    checks = (
        (prerequisite, "F2.5.37 prerequisite no longer passes"),
        (ancestor, "reviewed F2.5.37 commit is not an ancestor"),
        (source_clean, "reviewed F2.5.37 source differs from its commit"),
        (source_match, "reviewed F2.5.37 source hash changed"),
        (plan_match, "reviewed F2.5.37 plan changed"),
        (continuity_match, "continuity normalization surface changed"),
        (scope_match, "continuity installation scope changed"),
        (integration_match, "corrected integration surface changed"),
        (connector_match, "reviewed connector source changed"),
        (live_match, "live execution surface changed"),
        (envelope_match, "authority envelope changed"),
        (environment_match, "numerical environment changed"),
        (cwd_match, "execution is not at repository root"),
        (signature_match, "public caller surface changed"),
    )
    blockers = tuple(message for condition, message in checks if not condition)
    return F2538Assessment(
        (
            F2538Exit.CORRECTED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY
            if not blockers
            else F2538Exit.POST_COMMIT_SEAL_MISMATCH
        ),
        envelope,
        prerequisite,
        ancestor,
        source_clean,
        source_match,
        plan_match,
        continuity_match,
        scope_match,
        integration_match,
        connector_match,
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
        / f"gate-f2-5-38-{stamp}.jsonl"
    )


def _execute_with_dependencies(
    authority: F2538AuthorityEnvelope,
    *,
    connector_provider: ConnectorProvider,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None,
) -> F2538RunResult:
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
        corrected = f2537._run_corrected_audited_injected(
            reference_socket=connected["reference"],
            perturbed_socket=connected["perturbed"],
        )
        emitter(f"{EVENT_PREFIX}_one_outcome", corrected)
        artifact = emitter.finalize()
        return F2538RunResult(
            authority.receipt_hash,
            corrected,
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


def run_reviewed_once(*, live_authorised: bool = False) -> F2538RunResult:
    """Run the exact corrected vertical once after a later separate authority."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.38 requires separate exact live authorisation")
    assessment = assess()
    if assessment.exit is not F2538Exit.CORRECTED_VERTICAL_READY_FOR_SEPARATE_AUTHORITY:
        raise RuntimeError(
            "post-commit authority seal no longer matches: "
            + "; ".join(assessment.blockers)
        )
    return _execute_with_dependencies(
        assessment.envelope,
        connector_provider=f2533._open_live_socket,
        receipt_path=default_receipt_path(datetime.now(timezone.utc)),
        mirror_sink=print,
    )


def current_live_surface_hash() -> str:
    source = "\n".join(
        (
            inspect.getsource(f2533._LiveSocketAdapter),
            inspect.getsource(f2533._selected_endpoint),
            inspect.getsource(f2533._open_live_socket),
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
    "F2538Assessment",
    "F2538AuthorityEnvelope",
    "F2538Exit",
    "F2538RunResult",
    "assess",
    "build_authority_envelope",
    "run_reviewed_once",
    "strict_json",
]
