"""Gate F2.5.25: post-commit seal for one-target confirmation.

Assessment is offline. ``run_reviewed_once`` is the only live-capable surface
and refuses before receipt or connector access unless a separate authority is
asserted. The runner is intentionally specific: one same-session dual-SND
qualification, one-target discovery, target-excluded retune witness, freeze,
one confirmation and stop. No caller-controlled experiment dimension exists.
"""

from __future__ import annotations

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
import websocket

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_3_1 as f2531
from . import kiwi_gate_f2_5_20 as f2520
from . import kiwi_gate_f2_5_21 as f2521
from . import kiwi_gate_f2_5_23 as f2523
from . import kiwi_gate_f2_5_24 as f2524
from . import kiwi_probe as kiwi
from .models import strict_json_value


F2525_TRANSFORM_VERSION = "gate-f2.5.25-one-target-authority-seal-v1"
REVIEWED_F2524_COMMIT = "f08c4f2f8178a497c024dcc9f0cf64886e09d8ab"
REVIEWED_AT = datetime(2026, 8, 18, 18, 0, 0, tzinfo=timezone.utc)
REVIEWED_CONFIRMATION_SURFACE_HASH = (
    "c4310059594402fdc8b4570e4391487242ee50b5af11ea9a186cd5d1c8f0dac8"
)
REVIEWED_LIVE_SURFACE_HASH = (
    "34f641c54131b319e4fdb415f9daa0b6cdc94a9009fd7135df1c03d1777e7b80"
)
AUTHORITY_ENVELOPE_HASH = (
    "fa21168df4487508b63cba9aec1324c57a91c60e9e144d7d646a972a09a4953d"
)
EVENT_PREFIX = "gate_f2_5_25"
RAW_RF_PERSISTENCE = "ZERO"
EXPECTED_ENVIRONMENT = (
    ("python", "3.13.5"),
    ("numpy", "2.3.3"),
    ("scipy", "1.17.1"),
    ("websocket-client", "1.8.0"),
)
EXPECTED_CAUSAL_SOURCE_SHA256 = f2521.EXPECTED_CAUSAL_SOURCE_SHA256 + (
    (
        "experiments/live_instrument/kiwi_gate_f2_5_22.py",
        "71668a5e380183a10b636f75be5a4783e8888ebff0c91f18b9a3eb24cba2a2e5",
    ),
    (
        "experiments/live_instrument/kiwi_gate_f2_5_23.py",
        "87980f48caa9f60b07f5c6abe0b2bbf1f39be005da307670b8a5a07b42c3c0ef",
    ),
    (
        "experiments/live_instrument/kiwi_gate_f2_5_24.py",
        "7affffe6faa31701640491c09c9e1130b05f99230e88ba59fe55439aefc666a7",
    ),
)
RUNTIME_CAUSAL_PATHS = tuple(path for path, _digest in EXPECTED_CAUSAL_SOURCE_SHA256)


class F2525Exit(str, Enum):
    EXACT_ONE_TARGET_CONFIRMATION_READY_FOR_SEPARATE_AUTHORITY = (
        "EXACT_ONE_TARGET_CONFIRMATION_READY_FOR_SEPARATE_AUTHORITY"
    )
    POST_COMMIT_SEAL_MISMATCH = "POST_COMMIT_SEAL_MISMATCH"


@dataclass(frozen=True, slots=True)
class F2525AuthorityEnvelope:
    reviewed_f2524_commit: str
    reviewed_at: datetime
    reviewed_confirmation_envelope: f2524.F2524Envelope
    reviewed_confirmation_surface_hash: str
    reviewed_live_surface_hash: str
    causal_source_sha256: tuple[tuple[str, str], ...]
    expected_environment: tuple[tuple[str, str], ...]
    authority_surface: str
    guard_order: tuple[str, ...]
    public_caller_overrides: tuple[str, ...]
    selected_endpoint_identity: str
    experiment_scope: str
    phase_order: tuple[str, ...]
    confirmation_windows: int
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    channel_lifetime: str
    command_ledger_boundary: str
    stop_condition: str
    receipt_path_policy: str
    receipt_first_event: str
    waterfall_role: str
    ext_api_role: str
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.reviewed_at)
        if self.reviewed_f2524_commit != REVIEWED_F2524_COMMIT:
            raise ValueError("reviewed F2.5.24 commit changed")
        if _confirmation_surface_hash() != REVIEWED_CONFIRMATION_SURFACE_HASH:
            raise ValueError("reviewed confirmation surface changed")
        if self.reviewed_confirmation_surface_hash != REVIEWED_CONFIRMATION_SURFACE_HASH:
            raise ValueError("confirmation surface seal changed")
        if self.reviewed_live_surface_hash != REVIEWED_LIVE_SURFACE_HASH:
            raise ValueError("live surface seal changed")
        if self.causal_source_sha256 != EXPECTED_CAUSAL_SOURCE_SHA256:
            raise ValueError("causal source seal changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("numerical environment seal changed")
        if self.authority_surface != "run_reviewed_once(live_authorised=False)":
            raise ValueError("authority surface changed")
        if self.guard_order != (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "F2524_CONFIRMATION_ENVELOPE",
            "AUTHORITY_RECEIPT_FIRST",
            "ONE_PROSPECTIVE_VERTICAL",
        ):
            raise ValueError("guard order changed")
        if self.public_caller_overrides != ("live_authorised",):
            raise ValueError("caller-controlled experiment dimensions re-entered")
        if self.selected_endpoint_identity != f2520.SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("the previously qualified capability changed")
        if self.experiment_scope != (
            "SAME_SESSION_DUAL_SND_ONE_TARGET_WITNESS_FREEZE_ONE_CONFIRMATION"
        ):
            raise ValueError("authority expanded beyond the reviewed vertical")
        if self.phase_order != f2523.PHASE_ORDER:
            raise ValueError("prospective phase order changed")
        if self.confirmation_windows != 1:
            raise ValueError("exactly one confirmation is required")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the reviewed experiment permits no retry")
        if self.channel_lifetime != "OPEN_FROM_REQUALIFICATION_THROUGH_CONFIRMATION":
            raise ValueError("same-session channel lifetime changed")
        if self.command_ledger_boundary != (
            "CLEAR_AFTER_WITNESS_QUALIFICATION_BEFORE_CONFIRMATION"
        ):
            raise ValueError("qualification commands can contaminate confirmation")
        if self.stop_condition != "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW":
            raise ValueError("single-outcome stop changed")
        if self.receipt_path_policy != "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE":
            raise ValueError("receipt path policy changed")
        if self.receipt_first_event != f"{EVENT_PREFIX}_authority_envelope_frozen":
            raise ValueError("authority envelope must be the first receipt")
        if self.waterfall_role != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("server waterfall cannot enter the experiment")
        if self.ext_api_role != "DESCRIPTIVE_HINT_UNUSED":
            raise ValueError("ext_api cannot become multichannel truth")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2523.TRANSFORM_VERSION,
            f2524.TRANSFORM_VERSION,
            F2525_TRANSFORM_VERSION,
        ):
            raise ValueError("authority transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2525Assessment:
    exit: F2525Exit
    envelope: F2525AuthorityEnvelope
    f2524_prerequisite_satisfied: bool
    reviewed_commit_is_ancestor: bool
    causal_git_diff_clean: bool
    causal_source_hashes_match: bool
    confirmation_surface_hash_matches: bool
    live_surface_hash_matches: bool
    numerical_environment_matches: bool
    working_directory_is_repository_root: bool
    caller_overrides_removed: bool
    same_session_lifetime_closed: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]


@dataclass(slots=True)
class _PreparedPrefreeze:
    result: f2523.F2523Result
    context: f25._TopologyContext | None
    control_receipt: object | None


@dataclass(frozen=True, slots=True)
class F2525RunResult:
    prefreeze: f2523.F2523Result
    confirmation: f2524.F2524Result | object | None
    receipt_artifact: f2531.ClosedArtifactReceipt
    authority_consumed: bool
    raw_rf_persistence: str


ReceiptSink = Callable[[str, object], None]
PrefreezeRunner = Callable[[ReceiptSink], _PreparedPrefreeze]
ConfirmationCapture = Callable[
    [f25._TopologyContext, f2523.F2523Plan], f24._DualArtifacts
]
ConfirmationEvaluator = Callable[..., object]


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
    return _git_guard("merge-base", "--is-ancestor", REVIEWED_F2524_COMMIT, "HEAD")


def causal_git_diff_clean() -> bool:
    return _git_guard(
        "diff", "--quiet", REVIEWED_F2524_COMMIT, "--", *RUNTIME_CAUSAL_PATHS
    )


def _confirmation_surface_hash() -> str:
    return f2._hash(asdict(f2524.build_envelope()))


def build_authority_envelope() -> F2525AuthorityEnvelope:
    return F2525AuthorityEnvelope(
        REVIEWED_F2524_COMMIT,
        REVIEWED_AT,
        f2524.build_envelope(),
        REVIEWED_CONFIRMATION_SURFACE_HASH,
        REVIEWED_LIVE_SURFACE_HASH,
        EXPECTED_CAUSAL_SOURCE_SHA256,
        EXPECTED_ENVIRONMENT,
        "run_reviewed_once(live_authorised=False)",
        (
            "EXPLICIT_AUTHORITY",
            "POST_COMMIT_SEAL",
            "F2524_CONFIRMATION_ENVELOPE",
            "AUTHORITY_RECEIPT_FIRST",
            "ONE_PROSPECTIVE_VERTICAL",
        ),
        ("live_authorised",),
        f2520.SELECTED_ENDPOINT_IDENTITY,
        "SAME_SESSION_DUAL_SND_ONE_TARGET_WITNESS_FREEZE_ONE_CONFIRMATION",
        f2523.PHASE_ORDER,
        1,
        0,
        0,
        "OPEN_FROM_REQUALIFICATION_THROUGH_CONFIRMATION",
        "CLEAR_AFTER_WITNESS_QUALIFICATION_BEFORE_CONFIRMATION",
        "FIRST_TERMINAL_OUTCOME_NO_SECOND_WINDOW",
        "DEFAULT_REPOSITORY_SESSION_RECEIPT_NO_OVERRIDE",
        f"{EVENT_PREFIX}_authority_envelope_frozen",
        "ABSENT_FROM_CAUSAL_PATH",
        "DESCRIPTIVE_HINT_UNUSED",
        RAW_RF_PERSISTENCE,
        (
            f2523.TRANSFORM_VERSION,
            f2524.TRANSFORM_VERSION,
            F2525_TRANSFORM_VERSION,
        ),
    )


def assess_gate_f2_5_25() -> F2525Assessment:
    prior = f2524.assess_gate_f2_5_24()
    envelope = build_authority_envelope()
    prior_ready = bool(
        prior.gate23_commit_bound
        and prior.all_outcomes_implemented
        and prior.witness_precedes_target
        and prior.invalid_intervention_blocks_target
        and prior.not_detectable_distinct_from_ambiguous
        and prior.controls_predeclared
        and prior.injected_artifacts_only
        and prior.post_commit_seal_required
        and not prior.live_execution_authorised
        and prior.raw_rf_persistence == RAW_RF_PERSISTENCE
    )
    ancestor = reviewed_commit_is_ancestor()
    git_clean = causal_git_diff_clean()
    try:
        causal_match = current_causal_source_sha256() == EXPECTED_CAUSAL_SOURCE_SHA256
    except (OSError, UnicodeError):
        causal_match = False
    confirmation_match = _confirmation_surface_hash() == REVIEWED_CONFIRMATION_SURFACE_HASH
    live_match = current_live_surface_hash() == REVIEWED_LIVE_SURFACE_HASH
    environment_match = current_environment() == EXPECTED_ENVIRONMENT
    cwd_match = Path.cwd().resolve() == _repository_root()
    envelope_match = envelope.receipt_hash == AUTHORITY_ENVELOPE_HASH
    blockers = tuple(
        message
        for condition, message in (
            (prior_ready, "F2.5.24 offline prerequisite failed"),
            (ancestor, "reviewed F2.5.24 commit is not an ancestor of HEAD"),
            (git_clean, "reviewed causal files have a Git diff"),
            (causal_match, "reviewed causal source SHA-256 changed"),
            (confirmation_match, "reviewed confirmation surface changed"),
            (live_match, "reviewed live-surface source changed"),
            (environment_match, "reviewed numerical environment changed"),
            (cwd_match, "working directory is not the repository root"),
            (envelope_match, "authority envelope hash changed"),
        )
        if not condition
    )
    return F2525Assessment(
        (
            F2525Exit.EXACT_ONE_TARGET_CONFIRMATION_READY_FOR_SEPARATE_AUTHORITY
            if not blockers
            else F2525Exit.POST_COMMIT_SEAL_MISMATCH
        ),
        envelope,
        prior_ready,
        ancestor,
        git_clean,
        causal_match,
        confirmation_match,
        live_match,
        environment_match,
        cwd_match,
        True,
        True,
        False,
        blockers,
    )


def _prefreeze_result(
    receipts: list[f2523.PhaseReceipt],
    outcome: f2523.MaterializationOutcome,
    authorised: str,
    unauthorised: tuple[str, ...],
    *,
    plan: f2523.F2523Plan | None = None,
) -> f2523.F2523Result:
    return f2523.F2523Result(
        f2523.build_envelope(),
        outcome.value,
        tuple(receipts),
        plan,
        (authorised,),
        unauthorised,
    )


def _blocked_prefreeze(
    receipt: f2523.PhaseReceipt,
    outcome: f2523.MaterializationOutcome,
    authorised: str,
    unauthorised: tuple[str, ...],
    sink: ReceiptSink,
) -> f2523.F2523Result:
    receipts = [receipt, *f2523._not_evaluated(receipt.phase)]
    for item in receipts[1:]:
        sink(f"{EVENT_PREFIX}_phase_not_evaluated", item)
    return _prefreeze_result(
        receipts,
        outcome,
        authorised,
        unauthorised,
    )


def _capture_live_discovery(context: f25._TopologyContext) -> f24._DualArtifacts:
    return f24._capture_dual(
        context.dual,
        sequence=False,
        center_a_hz=context.center_hz,
        delta_f_hz=0.0,
        segment_duration_s=f25.DISCOVERY_DURATION_S,
        settling_s=0.0,
    )


def _capture_live_diagnostic(
    context: f25._TopologyContext,
    delta_hz: float,
) -> f24._DualArtifacts:
    mother = f2.MotherPlan()
    return f24._capture_dual(
        context.dual,
        sequence=True,
        center_a_hz=context.center_hz,
        delta_f_hz=delta_hz,
        segment_duration_s=mother.diagnostic_segment_s,
        settling_s=mother.settling_s,
    )


def _capture_live_confirmation(
    context: f25._TopologyContext,
    plan: f2523.F2523Plan,
) -> f24._DualArtifacts:
    mother = f2.MotherPlan()
    return f24._capture_dual(
        context.dual,
        sequence=True,
        center_a_hz=plan.center_a_hz,
        delta_f_hz=plan.delta_hz,
        segment_duration_s=mother.confirmation_segment_s,
        settling_s=mother.settling_s,
        event_not_before=plan.confirmation_event_not_before,
    )


def _materialize_live_prefreeze(
    sink: ReceiptSink,
    *,
    connector_provider: object,
    websocket_module: object,
) -> _PreparedPrefreeze:
    qualification = f2520.qualify_selected_capability_injected(
        connector_provider=connector_provider,  # type: ignore[arg-type]
        websocket_module=websocket_module,
    )
    sink(f"{EVENT_PREFIX}_phase_aware_control_receipt", qualification.control_receipt)
    direct = qualification.result
    if not isinstance(direct, f25._TopologyContext):
        state = (
            f2523.PhaseState.QUALIFICATION_ERROR.value
            if direct.state is f25.F25PhaseState.QUALIFICATION_ERROR
            else f2523.PhaseState.UNSATISFIED.value
        )
        receipt = f2523.PhaseReceipt(
            "DIRECT_DUAL_SND_QUALIFICATION",
            state,
            direct.statement,
            direct.artifact_hashes,
            direct.properties,
        )
        sink(f"{EVENT_PREFIX}_direct_dual_snd_qualification", receipt)
        result = _blocked_prefreeze(
            receipt,
            f2523.MaterializationOutcome.QUALIFICATION_INCOMPLETE,
            "same-session dual-SND topology did not admit discovery",
            (
                "one-target discovery evaluated",
                "retune qualified",
                "physical hypothesis evaluated",
            ),
            sink,
        )
        return _PreparedPrefreeze(result, None, qualification.control_receipt)

    context = direct
    receipts = [
        f2523.PhaseReceipt(
            "DIRECT_DUAL_SND_QUALIFICATION",
            f2523.PhaseState.SATISFIED.value,
            direct.phase_receipt.statement,
            direct.phase_receipt.artifact_hashes,
            direct.phase_receipt.properties,
        )
    ]
    sink(f"{EVENT_PREFIX}_direct_dual_snd_qualification", receipts[0])
    try:
        discovery_artifacts = _capture_live_discovery(context)
        discovered = f2523.discover_one_target(
            discovery_artifacts,
            context.center_hz,
            f2.MotherPlan(),
        )
        discovery_receipt = (
            discovered.phase_receipt
            if isinstance(discovered, f2523._DiscoveryContext)
            else discovered
        )
        receipts.append(discovery_receipt)
        sink(f"{EVENT_PREFIX}_one_target_discovery", discovery_receipt)
        if not isinstance(discovered, f2523._DiscoveryContext):
            outcome = (
                f2523.MaterializationOutcome.QUALIFICATION_INCOMPLETE
                if discovery_receipt.state == f2523.PhaseState.QUALIFICATION_ERROR.value
                else f2523.MaterializationOutcome.NO_FALSIFIABLE_INTERVENTION
            )
            result = _blocked_prefreeze(
                discovery_receipt,
                outcome,
                "the admitted topology did not yield one target plus a usable delta",
                ("no signal existed", "retune qualified", "physical hypothesis evaluated"),
                sink,
            )
            result = f2523.F2523Result(
                result.envelope,
                result.outcome,
                tuple(receipts[:1]) + result.phase_receipts,
                None,
                result.authorised_claims,
                result.unauthorised_claims,
            )
            return _PreparedPrefreeze(result, context, qualification.control_receipt)

        diagnostic_artifacts = _capture_live_diagnostic(
            context,
            discovered.geometry.delta_hz,
        )
        qualified = f2523.qualify_distributed_witness(
            discovered,
            diagnostic_artifacts,
            f2.MotherPlan(),
        )
        witness_receipt = (
            qualified.phase_receipt
            if isinstance(qualified, f2523.WitnessQualification)
            else qualified
        )
        receipts.append(witness_receipt)
        sink(f"{EVENT_PREFIX}_distributed_retune_qualification", witness_receipt)
        if not isinstance(qualified, f2523.WitnessQualification):
            outcome = (
                f2523.MaterializationOutcome.QUALIFICATION_INCOMPLETE
                if witness_receipt.state == f2523.PhaseState.QUALIFICATION_ERROR.value
                else f2523.MaterializationOutcome.INTERVENTION_NOT_QUALIFIED
            )
            result = _blocked_prefreeze(
                witness_receipt,
                outcome,
                "the target-independent witness did not qualify the intervention",
                ("target physics evaluated", "retune is per-channel", "external RF proven"),
                sink,
            )
            result = f2523.F2523Result(
                result.envelope,
                result.outcome,
                tuple(receipts[:-1]) + result.phase_receipts,
                None,
                result.authorised_claims,
                result.unauthorised_claims,
            )
            return _PreparedPrefreeze(result, context, qualification.control_receipt)

        frozen_at = datetime.now(timezone.utc)
        plan = f2523.freeze_plan(
            context,
            discovered,
            qualified,
            f2.MotherPlan(),
            frozen_at=frozen_at,
        )
        plan_receipt = f2523.PhaseReceipt(
            "PLAN_FREEZE",
            f2523.PhaseState.SATISFIED.value,
            "one target, distributed witness, predictions, controls and outcomes frozen",
            plan.discovery_artifact_hashes + plan.qualification_artifact_hashes,
            (
                ("plan_hash", plan.plan_hash),
                ("target_excluded_from_witness", "TRUE"),
                ("confirmation_windows", "1"),
                ("postfreeze_retry_budget", "0"),
            ),
        )
        pending = f2523.PhaseReceipt(
            "ONE_CONFIRMATION",
            f2523.PhaseState.NOT_EVALUATED.value,
            "confirmation cannot enter before the immutable plan exists",
            (),
            (("plan_frozen", "TRUE"),),
        )
        receipts.extend((plan_receipt, pending))
        sink(f"{EVENT_PREFIX}_plan_frozen", {"plan": plan, "plan_hash": plan.plan_hash})
        return _PreparedPrefreeze(
            _prefreeze_result(
                receipts,
                f2523.MaterializationOutcome.PREFREEZE_PLAN_MATERIALIZED_OFFLINE,
                "one target and an independent intervention witness admitted one confirmation",
                (
                    "either target hypothesis is supported",
                    "external RF proven",
                    "a second confirmation is permitted",
                ),
                plan=plan,
            ),
            context,
            qualification.control_receipt,
        )
    except BaseException:
        context.close()
        raise


def default_receipt_path(created_at: datetime) -> Path:
    stamp = f2._utc(created_at).strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        _repository_root()
        / "experiments"
        / "live_instrument"
        / "session_receipts"
        / f"gate-f2-5-25-{stamp}.jsonl"
    )


def _live_connector_provider(
    _endpoint: kiwi.KiwiEndpoint,
    _role: str,
) -> Callable[..., object]:
    return websocket.create_connection


def _execute_reviewed(
    authority: F2525AuthorityEnvelope,
    *,
    prepare_prefreeze: PrefreezeRunner,
    capture_confirmation: ConfirmationCapture,
    evaluate_confirmation: ConfirmationEvaluator,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None,
) -> F2525RunResult:
    emitter = f2531.TerminalReceiptEmitter(receipt_path, mirror_sink=mirror_sink)
    prepared: _PreparedPrefreeze | None = None
    finalised = False

    def close_context_descriptively() -> None:
        nonlocal prepared
        if prepared is None or prepared.context is None:
            return
        try:
            prepared.context.close()
        except Exception as close_error:
            emitter.record_runtime_error(close_error)
        finally:
            prepared.context = None

    try:
        emitter(
            authority.receipt_first_event,
            {
                "authority_envelope": authority,
                "authority_envelope_hash": authority.receipt_hash,
                "reviewed_confirmation_surface_hash": authority.reviewed_confirmation_surface_hash,
                "reviewed_live_surface_hash": authority.reviewed_live_surface_hash,
                "separate_live_authority_asserted": True,
            },
        )
        prepared = prepare_prefreeze(emitter)
        emitter(f"{EVENT_PREFIX}_prefreeze_outcome", prepared.result)
        if prepared.result.plan is None:
            close_context_descriptively()
            artifact = emitter.finalize()
            finalised = True
            return F2525RunResult(
                prepared.result,
                None,
                artifact,
                True,
                RAW_RF_PERSISTENCE,
            )
        if prepared.context is None:
            raise RuntimeError("a frozen plan has no same-session channel context")

        reference_qualification_commands = len(
            prepared.context.dual.reference.command_ledger
        )
        perturbed_qualification_commands = len(
            prepared.context.dual.perturbed.command_ledger
        )
        prepared.context.dual.reference.command_ledger.clear()
        prepared.context.dual.perturbed.command_ledger.clear()
        emitter(
            f"{EVENT_PREFIX}_qualification_ledger_closed",
            {
                "reference_commands_removed": reference_qualification_commands,
                "perturbed_commands_removed": perturbed_qualification_commands,
                "confirmation_reference_ledger_count": 0,
                "confirmation_perturbed_ledger_count": 0,
                "target_evaluated": False,
            },
        )
        confirmation_artifacts = capture_confirmation(
            prepared.context,
            prepared.result.plan,
        )
        evaluated = evaluate_confirmation(
            prepared.result.plan,
            confirmation_artifacts,
            evaluated_at=datetime.now(timezone.utc),
        )
        del confirmation_artifacts
        emitter(f"{EVENT_PREFIX}_one_confirmation_outcome", evaluated)
        close_context_descriptively()
        artifact = emitter.finalize()
        finalised = True
        return F2525RunResult(
            prepared.result,
            evaluated,
            artifact,
            True,
            RAW_RF_PERSISTENCE,
        )
    except BaseException as error:
        emitter.record_runtime_error(error)
        close_context_descriptively()
        if not finalised:
            emitter.finalize()
            finalised = True
        raise


def run_reviewed_once(*, live_authorised: bool = False) -> F2525RunResult:
    """Consume exactly one sealed one-target prospective vertical."""

    if not live_authorised:
        raise PermissionError("Gate F2.5.25 requires separate exact live authorisation")
    assessment = assess_gate_f2_5_25()
    if assessment.exit is not (
        F2525Exit.EXACT_ONE_TARGET_CONFIRMATION_READY_FOR_SEPARATE_AUTHORITY
    ):
        raise RuntimeError(
            "post-commit one-target seal no longer matches: "
            + "; ".join(assessment.blockers)
        )
    return _execute_reviewed(
        assessment.envelope,
        prepare_prefreeze=lambda sink: _materialize_live_prefreeze(
            sink,
            connector_provider=_live_connector_provider,
            websocket_module=websocket,
        ),
        capture_confirmation=_capture_live_confirmation,
        evaluate_confirmation=f2524.evaluate_confirmation_injected,
        receipt_path=default_receipt_path(datetime.now(timezone.utc)),
        mirror_sink=print,
    )


_LIVE_SURFACE_MEMBERS = (
    build_authority_envelope,
    assess_gate_f2_5_25,
    _capture_live_discovery,
    _capture_live_diagnostic,
    _capture_live_confirmation,
    _materialize_live_prefreeze,
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


def strict_json(value: object) -> str:
    return json.dumps(
        strict_json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def main() -> None:
    print(strict_json(assess_gate_f2_5_25()))


if __name__ == "__main__":
    main()
