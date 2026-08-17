"""Gate F2.5.10: exact offline execution-envelope review.

The module adds no acquisition logic.  It removes caller-controlled overrides
from the future authority surface and verifies that the reviewed causal files
and numerical environment still match before delegating once to F2.5.9.
Importing and assessing it perform no network activity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import importlib.metadata
from pathlib import Path
import platform
import subprocess

import numpy as np
import scipy

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_1 as f251
from . import kiwi_gate_f2_5_3_1 as f2531
from . import kiwi_gate_f2_5_9 as f259


F2510_TRANSFORM_VERSION = "gate-f2.5.10-exact-execution-envelope-v1"
REVIEWED_PHYSICAL_RUNTIME_COMMIT = "4eed64a2adc53e7535adbb8d5f7e8967d204b6a8"
EVENT_PREFIX = "gate_f2_5_10"
TERMINAL_INSTRUMENT = "gate-f2.5.10-reviewed-ordered-dual-snd"
EXPECTED_ENVIRONMENT = (
    ("python", "3.13.5"),
    ("numpy", "2.3.3"),
    ("scipy", "1.17.1"),
    ("websocket-client", "1.8.0"),
)
RUNTIME_CAUSAL_PATHS = (
    "experiments/live_instrument/models.py",
    "experiments/live_instrument/kiwi_probe.py",
    "experiments/live_instrument/kiwi_gate_f2.py",
    "experiments/live_instrument/kiwi_gate_f2_2.py",
    "experiments/live_instrument/kiwi_gate_f2_3.py",
    "experiments/live_instrument/kiwi_gate_f2_4.py",
    "experiments/live_instrument/kiwi_gate_f2_5.py",
    "experiments/live_instrument/kiwi_gate_f2_5_1.py",
    "experiments/live_instrument/kiwi_gate_f2_5_3.py",
    "experiments/live_instrument/kiwi_gate_f2_5_3_1.py",
    "experiments/live_instrument/kiwi_gate_f2_5_7.py",
    "experiments/live_instrument/kiwi_gate_f2_5_8.py",
    "experiments/live_instrument/kiwi_gate_f2_5_9.py",
)


class F2510Exit(str, Enum):
    REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY = (
        "REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY"
    )
    EXECUTION_ENVELOPE_MISMATCH = "EXECUTION_ENVELOPE_MISMATCH"


@dataclass(frozen=True, slots=True)
class F2510ExecutionEnvelope:
    reviewed_physical_runtime_commit: str
    runtime_causal_paths: tuple[str, ...]
    expected_environment: tuple[tuple[str, str], ...]
    mother_plan_hash: str
    candidate_set_hash: str
    candidate_order: tuple[str, ...]
    bootstrap_centers_hz: tuple[tuple[str, float], ...]
    center_policy: str
    qualification_budget_s: float
    retry_budget: int
    maximum_retry_per_endpoint: int
    maximum_candidate_attempts: int
    endpoints_in_parallel: int
    simultaneous_snd_slots: int
    websocket_connect_timeout_s: float
    ordered_control_deadline_s: float
    topology_duration_s: float
    discovery_duration_s: float
    retune_qualification_duration_s: float
    prefreeze_capture_duration_s: float
    confirmation_duration_s: float
    maximum_admitted_capture_duration_s: float
    postfreeze_retry_budget: int
    waterfall_semantics: str
    ext_api_semantics: str
    feature_selection: str
    receipt_path_policy: str
    receipt_content_policy: str
    raw_rf_persistence: str
    stop_condition: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        mother = f2.MotherPlan()
        expected_candidates = f24.ordered_candidate_identities()
        expected_centers = tuple(
            (
                identity,
                f251.bootstrap_center(endpoint, {}),
            )
            for identity, endpoint in zip(
                expected_candidates,
                f24.ordered_candidates(),
            )
        )
        if self.reviewed_physical_runtime_commit != REVIEWED_PHYSICAL_RUNTIME_COMMIT:
            raise ValueError("reviewed physical runtime commit changed")
        if self.runtime_causal_paths != RUNTIME_CAUSAL_PATHS:
            raise ValueError("runtime causal source set changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("reviewed numerical environment changed")
        if self.mother_plan_hash != mother.plan_hash:
            raise ValueError("MotherPlan changed after review")
        if self.candidate_set_hash != f24.candidate_set_hash():
            raise ValueError("candidate set changed after review")
        if self.candidate_order != expected_candidates:
            raise ValueError("candidate order changed after review")
        if self.bootstrap_centers_hz != expected_centers:
            raise ValueError("targetless bootstrap centers changed after review")
        if self.center_policy != f251.CENTER_POLICY:
            raise ValueError("bootstrap center policy changed after review")
        if (
            self.qualification_budget_s != f24.QUALIFICATION_BUDGET_S
            or self.retry_budget != f24.RETRY_BUDGET
            or self.maximum_retry_per_endpoint != f24.MAX_RETRY_PER_ENDPOINT
            or self.maximum_candidate_attempts
            != len(expected_candidates) + f24.RETRY_BUDGET
        ):
            raise ValueError("qualification or retry envelope changed")
        if (self.endpoints_in_parallel, self.simultaneous_snd_slots) != (1, 2):
            raise ValueError("responsible-access concurrency changed")
        if (self.websocket_connect_timeout_s, self.ordered_control_deadline_s) != (
            8.0,
            12.0,
        ):
            raise ValueError("ordered opener timing guard changed")
        diagnostic = 3.0 * mother.diagnostic_segment_s + 2.0 * mother.settling_s
        confirmation = 3.0 * mother.confirmation_segment_s + 2.0 * mother.settling_s
        prefreeze = f25.TOPOLOGY_DURATION_S + f25.DISCOVERY_DURATION_S + diagnostic
        if (
            self.topology_duration_s != f25.TOPOLOGY_DURATION_S
            or self.discovery_duration_s != f25.DISCOVERY_DURATION_S
            or self.retune_qualification_duration_s != diagnostic
            or self.prefreeze_capture_duration_s != prefreeze
            or self.confirmation_duration_s != confirmation
            or self.maximum_admitted_capture_duration_s != prefreeze + confirmation
        ):
            raise ValueError("capture duration envelope changed")
        if self.postfreeze_retry_budget != 0:
            raise ValueError("post-freeze retry is forbidden")
        if self.waterfall_semantics != "OPTIONAL_AND_OUTSIDE_CAUSAL_PATH":
            raise ValueError("waterfall re-entered the causal path")
        if self.ext_api_semantics != "DESCRIPTIVE_HINT_ONLY":
            raise ValueError("ext_api became a qualification gate")
        if self.feature_selection != "LOCAL_EPHEMERAL_IQ_STFT_PSD":
            raise ValueError("feature selection surface changed")
        if self.receipt_path_policy != "DEFAULT_REPOSITORY_SESSION_RECEIPT_ONLY":
            raise ValueError("caller-controlled receipt path is forbidden")
        if self.receipt_content_policy != "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY":
            raise ValueError("receipt content policy changed")
        if self.raw_rf_persistence != "ZERO":
            raise ValueError("raw RF persistence is forbidden")
        if self.stop_condition != "FIRST_OUTCOME_THEN_CLOSE":
            raise ValueError("one-outcome stop condition changed")
        if self.transform_versions[-2:] != (
            f259.F259_TRANSFORM_VERSION,
            F2510_TRANSFORM_VERSION,
        ):
            raise ValueError("review transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2510Assessment:
    exit: F2510Exit
    envelope: F2510ExecutionEnvelope
    ordered_runner_prerequisite_satisfied: bool
    causal_sources_unchanged: bool
    numerical_environment_unchanged: bool
    caller_overrides_removed: bool
    working_directory_is_repository_root: bool
    one_outcome_stop_preserved: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def current_environment() -> tuple[tuple[str, str], ...]:
    return (
        ("python", platform.python_version()),
        ("numpy", np.__version__),
        ("scipy", scipy.__version__),
        ("websocket-client", importlib.metadata.version("websocket-client")),
    )


def causal_sources_unchanged() -> bool:
    try:
        result = subprocess.run(
            (
                "git",
                "diff",
                "--quiet",
                REVIEWED_PHYSICAL_RUNTIME_COMMIT,
                "--",
                *RUNTIME_CAUSAL_PATHS,
            ),
            cwd=_repository_root(),
            check=False,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def build_execution_envelope() -> F2510ExecutionEnvelope:
    mother = f2.MotherPlan()
    candidates = f24.ordered_candidate_identities()
    diagnostic = 3.0 * mother.diagnostic_segment_s + 2.0 * mother.settling_s
    confirmation = 3.0 * mother.confirmation_segment_s + 2.0 * mother.settling_s
    prefreeze = f25.TOPOLOGY_DURATION_S + f25.DISCOVERY_DURATION_S + diagnostic
    inherited_transforms = f259.build_bootstrap_receipt(
        runtime_commit="0" * 40,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ).transform_versions
    return F2510ExecutionEnvelope(
        REVIEWED_PHYSICAL_RUNTIME_COMMIT,
        RUNTIME_CAUSAL_PATHS,
        EXPECTED_ENVIRONMENT,
        mother.plan_hash,
        f24.candidate_set_hash(),
        candidates,
        tuple(
            (identity, f251.bootstrap_center(endpoint, {}))
            for identity, endpoint in zip(candidates, f24.ordered_candidates())
        ),
        f251.CENTER_POLICY,
        f24.QUALIFICATION_BUDGET_S,
        f24.RETRY_BUDGET,
        f24.MAX_RETRY_PER_ENDPOINT,
        len(candidates) + f24.RETRY_BUDGET,
        1,
        2,
        8.0,
        12.0,
        f25.TOPOLOGY_DURATION_S,
        f25.DISCOVERY_DURATION_S,
        diagnostic,
        prefreeze,
        confirmation,
        prefreeze + confirmation,
        0,
        "OPTIONAL_AND_OUTSIDE_CAUSAL_PATH",
        "DESCRIPTIVE_HINT_ONLY",
        "LOCAL_EPHEMERAL_IQ_STFT_PSD",
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_ONLY",
        "STRICT_JSONL_RECEIPTS_AND_HASHES_ONLY",
        "ZERO",
        "FIRST_OUTCOME_THEN_CLOSE",
        inherited_transforms + (F2510_TRANSFORM_VERSION,),
    )


def assess_gate_f2_5_10(
    prerequisite: f259.F259Assessment | None = None,
) -> F2510Assessment:
    prior = prerequisite or f259.assess_gate_f2_5_9()
    envelope = build_execution_envelope()
    prior_ready = (
        prior.exit is f259.F259Exit.ORDERED_ONE_SHOT_RUNNER_MATERIALIZED
        and prior.ordered_opener_is_active
        and prior.legacy_opener_is_unreachable
    )
    source_guard = causal_sources_unchanged()
    environment_guard = current_environment() == EXPECTED_ENVIRONMENT
    cwd_guard = Path.cwd().resolve() == _repository_root()
    blockers = tuple(
        message
        for condition, message in (
            (prior_ready, "ordered F2.5.9 runner prerequisite failed"),
            (source_guard, "reviewed causal source files changed"),
            (environment_guard, "reviewed numerical environment changed"),
            (cwd_guard, "working directory is not the repository root"),
        )
        if not condition
    )
    ready = not blockers
    return F2510Assessment(
        F2510Exit.REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY
        if ready
        else F2510Exit.EXECUTION_ENVELOPE_MISMATCH,
        envelope,
        prior_ready,
        source_guard,
        environment_guard,
        True,
        cwd_guard,
        True,
        False,
        blockers,
        (
            "the exact one-shot envelope is reproducible without caller overrides",
            "the reviewed causal files and numerical environment currently match",
            "a later separately authorised call can execute at most one outcome",
        )
        if ready
        else ("the execution envelope failed closed before network entry",),
        (
            "a Kiwi endpoint has been contacted",
            "a capability is live now",
            "a DDC hypothesis has been evaluated",
            "this offline review itself authorises live execution",
        ),
    )


def default_receipt_path(created_at: datetime) -> Path:
    stamp = f2._utc(created_at).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        _repository_root()
        / "experiments"
        / "live_instrument"
        / "session_receipts"
        / f"gate-f2-5-10-{stamp}.jsonl"
    )


def run_reviewed_once(*, live_authorised: bool = False) -> f259.F259Result:
    """Narrow authority shim: no MotherPlan, path, commit or retry overrides."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.10 requires separate live authorisation")
    assessment = assess_gate_f2_5_10()
    if assessment.exit is not F2510Exit.REVIEWED_ONE_SHOT_READY_FOR_SEPARATE_AUTHORITY:
        raise RuntimeError(
            "reviewed execution envelope no longer matches: "
            + "; ".join(assessment.blockers)
        )
    commit = f22.runtime_commit()
    created_at = datetime.now(timezone.utc)
    bootstrap = f259.build_bootstrap_receipt(
        runtime_commit=commit,
        created_at=created_at,
    )
    emitter = f2531.TerminalReceiptEmitter(default_receipt_path(created_at))
    emitter(
        f"{EVENT_PREFIX}_execution_envelope_frozen",
        {
            "envelope": assessment.envelope,
            "envelope_hash": assessment.envelope.receipt_hash,
            "authority_surface": "run_reviewed_once",
            "separate_live_authority_asserted": True,
        },
    )
    try:
        physical = f25.run_once(
            mother=f2.MotherPlan(),
            runtime_commit=commit,
            bootstrap_receipt=bootstrap,  # type: ignore[arg-type]
            direct_qualifier=f259.direct_ordered_snd_qualification,
            event_prefix=EVENT_PREFIX,
            terminal_instrument=TERMINAL_INSTRUMENT,
            retry_selector=f259.ordered_retryable_phase,
            event_emitter=emitter,
        )
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    return f259.F259Result(physical, emitter.finalize())
