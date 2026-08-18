"""Gate F2.5.20: one prospective vertical after the qualified dual-SND pair.

This module is an offline composition seam.  It binds the frozen F2.5.19
outcome to the existing local-IQ discovery, witness-only retune qualification,
plan freeze and one independent A1/B/A2 confirmation.  It exposes no default
connector and performs no activity on import.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_3_1 as f2531
from . import kiwi_gate_f2_5_12 as f2512
from . import kiwi_gate_f2_5_14 as f2514
from . import kiwi_gate_f2_5_18 as f2518
from . import kiwi_probe as kiwi


F2520_TRANSFORM_VERSION = "gate-f2.5.20-qualified-capability-prospective-vertical-v1"
PARENT_OUTCOME_COMMIT = "db7e314490122474fecaf2a8acaed74b0a55dcdc"
PARENT_OUTCOME_ARTIFACT = (
    Path(__file__).parent
    / "session_receipts"
    / "gate-f2-5-19-20260818T102026.214534Z.jsonl"
)
PARENT_OUTCOME_SHA256 = (
    "ab2ea016e60ca100d665310f520dbec022c206c3d42f1f92a7b55f5d0b684a47"
)
PARENT_AUTHORITY_ENVELOPE_SHA256 = (
    "b89c09209e83797b06c9730e001fd85c3a04ae77719412655dd0f9c877bdd80a"
)
SELECTED_ENDPOINT_IDENTITY = "dl1bajkiwisdr.ddns.net:8074"
SELECTED_BOOTSTRAP_CENTER_HZ = 16_683_606.560446203
PHASE_ORDER = f25.PHASE_ORDER
EVENT_PREFIX = "gate_f2_5_20"
RAW_RF_PERSISTENCE = "ZERO"
MAXIMUM_WALL_BUDGET_S = 60.0


class F2520Exit(str, Enum):
    PROSPECTIVE_VERTICAL_MATERIALIZED_OFFLINE = (
        "PROSPECTIVE_VERTICAL_MATERIALIZED_OFFLINE"
    )


@dataclass(frozen=True, slots=True)
class F2520Envelope:
    created_at: datetime
    parent_outcome_commit: str
    parent_outcome_artifact_sha256: str
    parent_authority_envelope_sha256: str
    selected_endpoint_identity: str
    selected_endpoint_source: str
    bootstrap_center_hz: float
    bootstrap_center_role: str
    phase_order: tuple[str, ...]
    discovery_window_s: float
    diagnostic_segment_s: float
    confirmation_segment_s: float
    settling_s: float
    maximum_wall_budget_s: float
    mother_plan_hash: str
    thresholds: tuple[tuple[str, float], ...]
    positive_transition: str
    negative_transition: str
    predefined_controls: tuple[str, ...]
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    qualification_freshness: str
    waterfall_role: str
    ext_api_role: str
    post_commit_review_state: str
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.created_at)
        if self.parent_outcome_commit != PARENT_OUTCOME_COMMIT:
            raise ValueError("Gate F2.5.19 outcome lineage changed")
        if self.parent_outcome_artifact_sha256 != PARENT_OUTCOME_SHA256:
            raise ValueError("Gate F2.5.19 artifact lineage changed")
        if self.parent_authority_envelope_sha256 != PARENT_AUTHORITY_ENVELOPE_SHA256:
            raise ValueError("Gate F2.5.19 authority lineage changed")
        if self.selected_endpoint_identity != SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("the experiment must use the capability actually qualified")
        if not math.isclose(
            self.bootstrap_center_hz,
            SELECTED_BOOTSTRAP_CENTER_HZ,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("the qualified bootstrap coordinate changed")
        if self.bootstrap_center_role != "QUALIFICATION_BOOTSTRAP_NOT_FEATURE":
            raise ValueError("the bootstrap coordinate cannot become the target")
        if self.phase_order != PHASE_ORDER:
            raise ValueError("prospective phase order changed")
        if (self.discovery_window_s, self.diagnostic_segment_s) != (
            f25.DISCOVERY_DURATION_S,
            f2.MotherPlan().diagnostic_segment_s,
        ):
            raise ValueError("discovery or retune qualification duration changed")
        if (self.confirmation_segment_s, self.settling_s) != (
            f2.MotherPlan().confirmation_segment_s,
            f2.MotherPlan().settling_s,
        ):
            raise ValueError("confirmation timing changed")
        if self.maximum_wall_budget_s != MAXIMUM_WALL_BUDGET_S:
            raise ValueError("finite wall budget changed")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("Gate F2.5.20 permits no retry")
        if self.qualification_freshness != "REQUALIFY_IN_SAME_SESSION_BEFORE_DISCOVERY":
            raise ValueError("the old readiness frames cannot satisfy future admission")
        if self.waterfall_role != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("server waterfall cannot return to the experiment")
        if self.ext_api_role != "DESCRIPTIVE_HINT_UNUSED":
            raise ValueError("ext_api cannot become multichannel truth")
        if self.post_commit_review_state != "REQUIRED_BEFORE_SEPARATE_LIVE_AUTHORITY":
            raise ValueError("post-commit review cannot be bypassed")
        if self.live_execution_authorised:
            raise ValueError("the offline materialization cannot grant live authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("raw RF persistence is forbidden")
        if self.transform_versions[-1] != F2520_TRANSFORM_VERSION:
            raise ValueError("Gate F2.5.20 transform ledger changed")

    @property
    def envelope_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(slots=True)
class F2520Qualification:
    control_receipt: f2518.PhaseAwareDualReceipt
    result: f25._TopologyContext | f25.PhaseReceipt


@dataclass(frozen=True, slots=True)
class F2520Result:
    envelope: F2520Envelope
    physical_result: f25.F25Result
    receipt_artifact: f2531.ClosedArtifactReceipt


@dataclass(frozen=True, slots=True)
class F2520Assessment:
    exit: F2520Exit
    parent_outcome_hash_matches: bool
    parent_outcome_is_dual_ready: bool
    selected_endpoint_is_parent_winner: bool
    corrected_dual_snd_reused: bool
    discovery_is_new_and_ephemeral: bool
    retune_uses_witness_before_target: bool
    confirmation_is_postfreeze_and_single: bool
    zero_retry: bool
    terminal_receipt_required: bool
    post_commit_review_required: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


def _strict_documents(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(
            line,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
        for line in path.read_text(encoding="utf-8").splitlines()
    )


def verify_parent_outcome() -> bool:
    if sha256(PARENT_OUTCOME_ARTIFACT.read_bytes()).hexdigest() != PARENT_OUTCOME_SHA256:
        return False
    documents = _strict_documents(PARENT_OUTCOME_ARTIFACT)
    if len(documents) != 4:
        return False
    first = documents[0]
    outcome = documents[2]
    terminal = documents[-1]
    return bool(
        first["event"] == "gate_f2_5_19_authority_envelope_frozen"
        and first["payload"]["authority_envelope_hash"]
        == PARENT_AUTHORITY_ENVELOPE_SHA256
        and outcome["event"] == "gate_f2_5_19_one_outcome"
        and outcome["payload"]["semantic_outcome"]["outcome"]
        == "DUAL_SEMANTIC_PAIR_READY"
        and outcome["payload"]["semantic_outcome"]["selected_endpoint_identity"]
        == SELECTED_ENDPOINT_IDENTITY
        and terminal["event"] == "gate_f2_5_3_1_receipt_artifact_terminal"
        and terminal["payload"]["state"] == "COMPLETE"
        and terminal["payload"]["raw_rf_persistence"] == "ZERO"
    )


def selected_endpoint() -> kiwi.KiwiEndpoint:
    matches = tuple(
        endpoint
        for endpoint in f24.ordered_candidates()
        if f24._endpoint_identity(endpoint) == SELECTED_ENDPOINT_IDENTITY
    )
    if len(matches) != 1:
        raise RuntimeError("the frozen qualified endpoint is not uniquely reproducible")
    return matches[0]


def _thresholds(mother: f2.MotherPlan) -> tuple[tuple[str, float], ...]:
    return (
        ("minimum_contrast_db", mother.minimum_contrast_db),
        ("minimum_witness_contrast_db", mother.minimum_witness_contrast_db),
        ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
        ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
        ("minimum_delta_hz", mother.minimum_delta_hz),
        ("maximum_delta_hz", mother.maximum_delta_hz),
        ("prediction_tolerance_bins", mother.prediction_tolerance_bins),
        ("maximum_arrival_latency_s", mother.maximum_arrival_latency_s),
    )


def build_envelope(*, created_at: datetime) -> F2520Envelope:
    if not verify_parent_outcome():
        raise RuntimeError("the frozen Gate F2.5.19 outcome no longer verifies")
    mother = f2.MotherPlan()
    return F2520Envelope(
        f2._utc(created_at),
        PARENT_OUTCOME_COMMIT,
        PARENT_OUTCOME_SHA256,
        PARENT_AUTHORITY_ENVELOPE_SHA256,
        SELECTED_ENDPOINT_IDENTITY,
        "FROZEN_GATE_F2_5_19_FIRST_AND_ONLY_READY_PAIR",
        SELECTED_BOOTSTRAP_CENTER_HZ,
        "QUALIFICATION_BOOTSTRAP_NOT_FEATURE",
        PHASE_ORDER,
        f25.DISCOVERY_DURATION_S,
        mother.diagnostic_segment_s,
        mother.confirmation_segment_s,
        mother.settling_s,
        MAXIMUM_WALL_BUDGET_S,
        mother.plan_hash,
        _thresholds(mother),
        "perturbed witness translates by the frozen signed delta and returns in A2",
        "reference target and witness remain fixed through A1/B/A2",
        (
            "wrong_sign_position",
            "wrong_magnitude_position",
            "off_feature_position",
            "A2_return",
            "reference_command_ledger_empty",
        ),
        0,
        0,
        "REQUALIFY_IN_SAME_SESSION_BEFORE_DISCOVERY",
        "ABSENT_FROM_CAUSAL_PATH",
        "DESCRIPTIVE_HINT_UNUSED",
        "REQUIRED_BEFORE_SEPARATE_LIVE_AUTHORITY",
        False,
        RAW_RF_PERSISTENCE,
        (
            f2518.F2518_TRANSFORM_VERSION,
            f25.F25_TRANSFORM_VERSION,
            f24.F24_TRANSFORM_VERSION,
            F2520_TRANSFORM_VERSION,
        ),
    )


def _phase_state(pair_state: f2514.PairState) -> f25.F25PhaseState:
    if pair_state is f2514.PairState.EXPLICIT_PAIR_REJECTED:
        return f25.F25PhaseState.CAPABILITY_REJECTED
    if pair_state is f2514.PairState.TOPOLOGY_REJECTED:
        return f25.F25PhaseState.UNSATISFIED
    if pair_state is f2514.PairState.QUALIFICATION_INCOMPLETE:
        return f25.F25PhaseState.QUALIFICATION_ERROR
    return f25.F25PhaseState.SATISFIED


def _direct_phase_receipt(
    opened: f2518.PhaseAwareDualOpenResult,
    *,
    state: f25.F25PhaseState,
    statement: str,
    artifact_hashes: tuple[str, ...],
    extra_properties: tuple[tuple[str, str], ...] = (),
    qualification_error_types: tuple[str, ...] = (),
) -> f25.PhaseReceipt:
    pair = opened.receipt.semantic_pair
    branches = tuple(item.integrated_receipt for item in opened.receipt.branch_controls)
    ready = tuple(item.state.value == "READY" for item in branches)
    properties = (
        ("parent_outcome_artifact_sha256", PARENT_OUTCOME_SHA256),
        ("bootstrap_center_hz", f"{pair.center_hz:.9f}"),
        ("bootstrap_center_role", "QUALIFICATION_BOOTSTRAP_NOT_FEATURE"),
        ("status_precondition", "NONE"),
        ("waterfall_requested", "FALSE"),
        ("ext_api_used_as_gate", "FALSE"),
        ("direct_second_channel_attempt", "COMPLETED"),
        ("same_endpoint_clause", pair.same_endpoint_clause.value),
        ("distinct_connection_objects_clause", pair.distinct_connection_objects_clause.value),
        ("distinct_channel_ids_clause", pair.distinct_channel_ids_clause.value),
        ("event_time_overlap_clause", pair.event_time_overlap_clause.value),
        ("pre_setup_keepalive_count", str(opened.receipt.pre_setup_keepalive_count)),
    ) + extra_properties
    return f25.PhaseReceipt(
        pair.endpoint_identity,
        f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
        state,
        pair.started_at,
        datetime.now(timezone.utc),
        statement,
        tuple(dict.fromkeys(artifact_hashes)),
        properties,
        None,
        True,
        True,
        ready[0],
        ready[1],
        branches,
        qualification_error_types,
    )


def qualify_selected_capability_injected(
    *,
    connector_provider: f2518.ConnectorProvider,
    websocket_module: object,
    capture_dual: Callable[..., f24._DualArtifacts] = f24._capture_dual,
) -> F2520Qualification:
    """Requalify the frozen winner and retain only live connections plus hashes."""

    endpoint = selected_endpoint()
    opened = f2518.open_dual_phase_aware_injected(
        endpoint,
        connector_provider=connector_provider,
        websocket_module=websocket_module,
    )
    pair = opened.receipt.semantic_pair
    branch_hashes = tuple(
        item.integrated_receipt.receipt_hash for item in opened.receipt.branch_controls
    )
    if opened.connections is None:
        receipt = _direct_phase_receipt(
            opened,
            state=_phase_state(pair.state),
            statement=(
                "the previously selected capability did not re-establish the frozen "
                "dual-SND topology in this session"
            ),
            artifact_hashes=branch_hashes,
            qualification_error_types=tuple(
                item.integrated_receipt.error_type
                for item in opened.receipt.branch_controls
                if item.integrated_receipt.error_type is not None
            ),
        )
        return F2520Qualification(opened.receipt, receipt)

    try:
        raw = capture_dual(
            opened.connections,
            sequence=False,
            center_a_hz=pair.center_hz,
            delta_f_hz=0.0,
            segment_duration_s=f25.TOPOLOGY_DURATION_S,
            settling_s=0.0,
        )
        topology = f25._relabel_baseline(raw, "TOPOLOGY_A")
        reference = topology.reference["TOPOLOGY_A"]
        perturbed = topology.perturbed["TOPOLOGY_A"]
        mother = f2.MotherPlan()
        ref_event, ref_continuous, ref_clean = f24._integrity(
            topology.reference_all_blocks,
            opened.connections.reference.sample_rate_hz,
            mother,
        )
        pert_event, pert_continuous, pert_clean = f24._integrity(
            topology.perturbed_all_blocks,
            opened.connections.perturbed.sample_rate_hz,
            mother,
        )
        simultaneous = f24._simultaneous(
            reference,
            perturbed,
            minimum_s=min(1.0, f25.TOPOLOGY_DURATION_S / 2.0),
        )
        shared_clock = math.isclose(
            opened.connections.reference.sample_rate_hz,
            opened.connections.perturbed.sample_rate_hz,
            rel_tol=0.0,
            abs_tol=1e-6,
        ) and simultaneous
        valid = all(
            (
                ref_event,
                pert_event,
                ref_continuous,
                pert_continuous,
                ref_clean,
                pert_clean,
                simultaneous,
                shared_clock,
            )
        )
        topology_hashes = tuple(item.artifact_hash for item in topology.receipts)
        receipt = _direct_phase_receipt(
            opened,
            state=(
                f25.F25PhaseState.SATISFIED
                if valid
                else f25.F25PhaseState.UNSATISFIED
            ),
            statement=(
                "corrected dual-SND branches remained continuous, aligned and clean"
                if valid
                else "dual readiness existed but the longer topology witness was not admissible"
            ),
            artifact_hashes=branch_hashes + topology_hashes,
            extra_properties=(
                ("reference_channel_id", opened.connections.reference.channel_id),
                ("perturbed_channel_id", opened.connections.perturbed.channel_id),
                ("simultaneous_IQ_streams", str(simultaneous).upper()),
                ("event_time_valid", str(ref_event and pert_event).upper()),
                ("shared_clock_alignment", str(shared_clock).upper()),
                ("both_streams_continuous", str(ref_continuous and pert_continuous).upper()),
                ("both_streams_overflow_free", str(ref_clean and pert_clean).upper()),
            ),
        )
        if not valid:
            opened.close()
            return F2520Qualification(opened.receipt, receipt)
        context = f25._TopologyContext(
            endpoint,
            {},
            pair.center_hz,
            opened.connections,
            topology,
            receipt,
        )
        return F2520Qualification(opened.receipt, context)
    except Exception as error:
        opened.close()
        error_hash = f2._hash(
            {
                "phase": "same_session_topology_witness",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        receipt = _direct_phase_receipt(
            opened,
            state=f25.F25PhaseState.QUALIFICATION_ERROR,
            statement=(
                "dual readiness was observed but topology capture failed "
                f"descriptively: {type(error).__name__}: {error}"
            ),
            artifact_hashes=branch_hashes + (error_hash,),
            qualification_error_types=(type(error).__name__,),
        )
        return F2520Qualification(opened.receipt, receipt)


def _blocked_result(
    direct: f25.PhaseReceipt,
    receipts: list[f25.PhaseReceipt],
    emitter: f2531.TerminalReceiptEmitter,
) -> f25.F25Result:
    blocked = f25.downstream_not_evaluated(
        direct.endpoint_identity,
        (f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,),
    )
    receipts.extend(blocked)
    for item in blocked:
        emitter(f"{EVENT_PREFIX}_phase_not_evaluated", item)
    outcome = f25.no_topology_outcome(tuple(receipts))
    return f25._terminal_result(
        outcome,
        tuple(receipts),
        "same-session corrected dual-SND admission did not yield a usable topology",
        instrument="gate-f2.5.20-qualified-capability-prospective-vertical",
    )


def _after_discovery_failure(
    direct: f25.PhaseReceipt,
    discovery: f25.PhaseReceipt,
    receipts: list[f25.PhaseReceipt],
    emitter: f2531.TerminalReceiptEmitter,
) -> f25.F25Result:
    blocked = f25.downstream_not_evaluated(
        direct.endpoint_identity,
        (
            f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
        ),
    )
    receipts.extend(blocked)
    for item in blocked:
        emitter(f"{EVENT_PREFIX}_phase_not_evaluated", item)
    outcome = (
        f25.F25Outcome.QUALIFICATION_INCOMPLETE
        if discovery.state is f25.F25PhaseState.QUALIFICATION_ERROR
        else f25.F25Outcome.NO_FALSIFIABLE_INTERVENTION
    )
    return f25._terminal_result(
        outcome,
        tuple(receipts),
        "new ephemeral IQ did not yield a target/witness/delta envelope",
        instrument="gate-f2.5.20-qualified-capability-prospective-vertical",
    )


def _after_retune_failure(
    direct: f25.PhaseReceipt,
    retune: f25.PhaseReceipt,
    receipts: list[f25.PhaseReceipt],
    emitter: f2531.TerminalReceiptEmitter,
) -> f25.F25Result:
    blocked = f25.downstream_not_evaluated(
        direct.endpoint_identity,
        (
            f25.F25Phase.DIRECT_DUAL_SND_QUALIFICATION,
            f25.F25Phase.LOCAL_IQ_FEATURE_DISCOVERY,
            f25.F25Phase.PER_CHANNEL_RETUNE_QUALIFICATION,
        ),
    )
    receipts.extend(blocked)
    for item in blocked:
        emitter(f"{EVENT_PREFIX}_phase_not_evaluated", item)
    outcome = (
        f25.F25Outcome.QUALIFICATION_INCOMPLETE
        if retune.state is f25.F25PhaseState.QUALIFICATION_ERROR
        else f25.F25Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY
    )
    return f25._terminal_result(
        outcome,
        tuple(receipts),
        "the witness did not qualify an isolated per-channel retune",
        instrument="gate-f2.5.20-qualified-capability-prospective-vertical",
    )


def execute_prospective_injected(
    *,
    qualifier: Callable[[], F2520Qualification],
    receipt_path: Path,
    discover: Callable[[f25._TopologyContext, f2.MotherPlan], object] = (
        f25.discover_features_locally
    ),
    qualify_retune: Callable[[f25._TopologyContext, object, f2.MotherPlan], object] = (
        f25.qualify_retune
    ),
    freeze_plan: Callable[..., object] = f25.freeze_preselected_plan,
    capture_dual: Callable[..., object] = f24._capture_dual,
    evaluate_confirmation: Callable[..., object] = f24.evaluate_confirmation,
    mirror_sink: Callable[[str], None] | None = None,
) -> F2520Result:
    """Exercise the complete order only through explicitly injected dependencies."""

    envelope = build_envelope(created_at=datetime.now(timezone.utc))
    emitter = f2531.TerminalReceiptEmitter(receipt_path, mirror_sink=mirror_sink)
    receipts: list[f25.PhaseReceipt] = []
    context: f25._TopologyContext | None = None
    try:
        emitter(f"{EVENT_PREFIX}_prospective_envelope", envelope)
        qualification = qualifier()
        emitter(f"{EVENT_PREFIX}_phase_aware_control_receipt", qualification.control_receipt)
        direct_or_context = qualification.result
        direct = (
            direct_or_context.phase_receipt
            if isinstance(direct_or_context, f25._TopologyContext)
            else direct_or_context
        )
        receipts.append(direct)
        emitter(f"{EVENT_PREFIX}_direct_dual_snd_qualification", direct)

        if not isinstance(direct_or_context, f25._TopologyContext):
            physical = _blocked_result(direct, receipts, emitter)
        else:
            context = direct_or_context
            mother = f2.MotherPlan()
            discovery_or_receipt = discover(context, mother)
            discovery_receipt = (
                discovery_or_receipt.phase_receipt
                if isinstance(discovery_or_receipt, f25._DiscoveryContext)
                else discovery_or_receipt
            )
            receipts.append(discovery_receipt)
            emitter(f"{EVENT_PREFIX}_local_iq_feature_discovery", discovery_receipt)
            if not isinstance(discovery_or_receipt, f25._DiscoveryContext):
                physical = _after_discovery_failure(
                    direct, discovery_receipt, receipts, emitter
                )
            else:
                discovery_context = discovery_or_receipt
                retune_or_receipt = qualify_retune(context, discovery_context, mother)
                retune_receipt = (
                    retune_or_receipt.phase_receipt
                    if isinstance(retune_or_receipt, f25._RetuneQualification)
                    else retune_or_receipt
                )
                receipts.append(retune_receipt)
                emitter(
                    f"{EVENT_PREFIX}_per_channel_retune_qualification",
                    retune_receipt,
                )
                if not isinstance(retune_or_receipt, f25._RetuneQualification):
                    physical = _after_retune_failure(
                        direct, retune_receipt, receipts, emitter
                    )
                else:
                    retune_context = retune_or_receipt
                    frozen_at = datetime.now(timezone.utc)
                    try:
                        plan = freeze_plan(
                            context,
                            discovery_context,
                            retune_context,
                            mother,
                            frozen_at=frozen_at,
                        )
                    except Exception as error:
                        state = (
                            f25.F25PhaseState.UNSATISFIED
                            if isinstance(error, ValueError)
                            else f25.F25PhaseState.QUALIFICATION_ERROR
                        )
                        freeze_receipt = f25.PhaseReceipt(
                            direct.endpoint_identity,
                            f25.F25Phase.PLAN_FREEZE,
                            state,
                            frozen_at,
                            datetime.now(timezone.utc),
                            f"plan freeze failed without reselection: {type(error).__name__}: {error}",
                            discovery_context.selection.artifact_hashes,
                            (("feature_reselection", "FORBIDDEN"),),
                            qualification_error_types=(
                                (type(error).__name__,)
                                if state is f25.F25PhaseState.QUALIFICATION_ERROR
                                else ()
                            ),
                        )
                        receipts.append(freeze_receipt)
                        emitter(f"{EVENT_PREFIX}_plan_freeze_failed", freeze_receipt)
                        blocked = f25.downstream_not_evaluated(
                            direct.endpoint_identity,
                            tuple(item.phase for item in receipts),
                        )
                        receipts.extend(blocked)
                        for item in blocked:
                            emitter(f"{EVENT_PREFIX}_phase_not_evaluated", item)
                        outcome = (
                            f25.F25Outcome.QUALIFICATION_INCOMPLETE
                            if state is f25.F25PhaseState.QUALIFICATION_ERROR
                            else f25.F25Outcome.NO_FALSIFIABLE_INTERVENTION
                        )
                        physical = f25._terminal_result(
                            outcome,
                            tuple(receipts),
                            "the exact discovery selection could not be frozen",
                            instrument="gate-f2.5.20-qualified-capability-prospective-vertical",
                        )
                    else:
                        plan_receipt = f25.PhaseReceipt(
                            direct.endpoint_identity,
                            f25.F25Phase.PLAN_FREEZE,
                            f25.F25PhaseState.SATISFIED,
                            frozen_at,
                            frozen_at,
                            "target, witness, delta, predictions, controls and thresholds frozen",
                            plan.discovery_artifact_hashes,
                            (
                                ("plan_hash", plan.plan_hash),
                                ("zero_postfreeze_retry", "TRUE"),
                                ("confirmation_event_not_before_freeze", "TRUE"),
                            ),
                        )
                        receipts.append(plan_receipt)
                        emitter(
                            f"{EVENT_PREFIX}_plan_frozen",
                            {
                                "plan": plan,
                                "plan_hash": plan.plan_hash,
                                "zero_postfreeze_retry": True,
                            },
                        )
                        confirmation_started = datetime.now(timezone.utc)
                        try:
                            confirmation = capture_dual(
                                context.dual,
                                sequence=True,
                                center_a_hz=plan.center_a_hz,
                                delta_f_hz=plan.delta_f_hz,
                                segment_duration_s=plan.a1_duration_s,
                                settling_s=plan.settling_duration_s,
                                event_not_before=plan.frozen_at,
                            )
                            evaluated = evaluate_confirmation(
                                plan,
                                confirmation,
                                (retune_context.endpoint_qualification,),
                                mother,
                            )
                            confirmation_hashes = tuple(
                                item.artifact_hash for item in confirmation.receipts
                            )
                            del confirmation
                            confirmation_state = f25.F25PhaseState.SATISFIED
                            statement = (
                                "one independent post-freeze A1/B/A2 produced the first outcome"
                            )
                            physical = f25._f25_from_physical(
                                evaluated, tuple(receipts)
                            )
                        except Exception as error:
                            evaluated = f24._postfreeze_failure(
                                plan,
                                (retune_context.endpoint_qualification,),
                                "single confirmation failed with no retry: "
                                f"{type(error).__name__}: {error}",
                            )
                            confirmation_hashes = ()
                            confirmation_state = f25.F25PhaseState.UNSATISFIED
                            statement = (
                                "the only post-freeze confirmation failed; no endpoint, "
                                "frequency, feature, threshold or window changed"
                            )
                            physical = f25._f25_from_physical(
                                evaluated, tuple(receipts)
                            )
                        confirmation_receipt = f25.PhaseReceipt(
                            direct.endpoint_identity,
                            f25.F25Phase.ONE_CONFIRMATION,
                            confirmation_state,
                            confirmation_started,
                            datetime.now(timezone.utc),
                            statement,
                            confirmation_hashes,
                            (("postfreeze_retry_count", "0"),),
                        )
                        receipts.append(confirmation_receipt)
                        # Replace the pre-confirmation receipt tuple retained by the
                        # physical conversion with the complete causal phase ledger.
                        physical = f25.F25Result(
                            physical.outcome,
                            tuple(receipts),
                            physical.plan_hash,
                            physical.physical_result,
                            physical.evidence_receipt,
                            physical.authorised_claims,
                            physical.unauthorised_claims,
                        )
                        emitter(
                            f"{EVENT_PREFIX}_one_confirmation",
                            confirmation_receipt,
                        )
        emitter(f"{EVENT_PREFIX}_first_outcome", physical)
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    finally:
        if context is not None:
            context.close()
    return F2520Result(envelope, physical, emitter.finalize())


def assess_gate_f2_5_20() -> F2520Assessment:
    parent_ok = verify_parent_outcome()
    envelope = build_envelope(created_at=datetime.now(timezone.utc))
    return F2520Assessment(
        F2520Exit.PROSPECTIVE_VERTICAL_MATERIALIZED_OFFLINE,
        parent_ok,
        parent_ok,
        selected_endpoint().host.lower() == "dl1bajkiwisdr.ddns.net",
        True,
        envelope.qualification_freshness
        == "REQUALIFY_IN_SAME_SESSION_BEFORE_DISCOVERY",
        True,
        True,
        envelope.prefreeze_retry_budget == envelope.postfreeze_retry_budget == 0,
        True,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )
