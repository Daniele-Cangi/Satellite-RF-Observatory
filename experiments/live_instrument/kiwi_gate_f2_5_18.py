"""Gate F2.5.18: dual phase-aware SND composition, offline only.

This module composes exactly two Gate F2.5.17 branches on one candidate and
reuses the already-tested pair topology and candidate-outcome semantics.  All
connectors and WebSocket framing remain mandatory injections.  There is no
live entry point or default connector.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_1 as f251
from . import kiwi_gate_f2_5_2 as f252
from . import kiwi_gate_f2_5_3_1 as f2531
from . import kiwi_gate_f2_5_8 as f258
from . import kiwi_gate_f2_5_12 as f2512
from . import kiwi_gate_f2_5_14 as f2514
from . import kiwi_gate_f2_5_17 as f2517
from . import kiwi_probe as kiwi


F2518_TRANSFORM_VERSION = "gate-f2.5.18-dual-phase-aware-candidate-loop-v1"
PARENT_GATE_COMMIT = "9b8e680857964fadb9002fedf11e1b908633f6f8"
EVENT_PREFIX = "gate_f2_5_18"
BRANCH_ROLES = ("reference", "perturbed")
RAW_RF_PERSISTENCE = "ZERO"


class F2518Exit(str, Enum):
    DUAL_PHASE_AWARE_ENVELOPE_MATERIALIZED_OFFLINE = (
        "DUAL_PHASE_AWARE_ENVELOPE_MATERIALIZED_OFFLINE"
    )


@dataclass(frozen=True, slots=True)
class F2518ExecutionEnvelope:
    created_at: datetime
    parent_gate_commit: str
    candidate_set_hash: str
    candidate_order: tuple[str, ...]
    branch_roles: tuple[str, str]
    branch_composition: str
    maximum_parallel_branches: int
    maximum_parallel_endpoints: int
    attempts_per_candidate: int
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    center_policy: str
    maximum_gps_solution_age_s: int
    status_precondition: str
    waterfall_precondition: str
    connector_policy: str
    control_plan_hash: str
    stop_condition: str
    terminal_receipt_required: bool
    post_commit_review_state: str
    transform_versions: tuple[str, ...]
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        f2._utc(self.created_at)
        if self.parent_gate_commit != PARENT_GATE_COMMIT:
            raise ValueError("Gate F2.5.17 lineage changed")
        if self.candidate_set_hash != f24.candidate_set_hash():
            raise ValueError("candidate set changed")
        if self.candidate_order != f24.ordered_candidate_identities():
            raise ValueError("candidate order changed")
        if self.branch_roles != BRANCH_ROLES:
            raise ValueError("dual branch roles changed")
        if self.branch_composition != "TWO_THREADS_ONE_ENDPOINT_PHASE_AWARE_SND":
            raise ValueError("dual phase-aware composition changed")
        if (
            self.maximum_parallel_branches != 2
            or self.maximum_parallel_endpoints != 1
            or self.attempts_per_candidate != 1
        ):
            raise ValueError("parallelism or attempt budget changed")
        if self.prefreeze_retry_budget != 0 or self.postfreeze_retry_budget != 0:
            raise ValueError("the phase-aware qualification admits no retry")
        if self.center_policy != f251.CENTER_POLICY:
            raise ValueError("data-independent center policy changed")
        if self.maximum_gps_solution_age_s != f2514.MAXIMUM_GPS_SOLUTION_AGE_S:
            raise ValueError("GPS age clause changed")
        if self.status_precondition != "NONE_BEFORE_DIRECT_SND":
            raise ValueError("status cannot become a direct-SND gate")
        if self.waterfall_precondition != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("waterfall cannot return to the causal path")
        if self.connector_policy != "MANDATORY_INJECTION_NO_DEFAULT":
            raise ValueError("live connector cannot enter the offline envelope")
        if self.control_plan_hash != f2517.control_plan_hash():
            raise ValueError("phase-aware control plan changed")
        if self.stop_condition != "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED":
            raise ValueError("one-outcome stop changed")
        if not self.terminal_receipt_required:
            raise ValueError("terminal receipt closure is mandatory")
        if self.post_commit_review_state != "REQUIRED_BEFORE_LIVE_AUTHORITY":
            raise ValueError("post-commit review cannot be skipped")
        if self.transform_versions != (
            f2517.F2517_TRANSFORM_VERSION,
            F2518_TRANSFORM_VERSION,
        ):
            raise ValueError("phase-aware transform ledger changed")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def envelope_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class PhaseAwareDualReceipt:
    semantic_pair: f2514.DualSemanticReceipt
    branch_controls: tuple[
        f2517.PhaseAwareBranchReceipt, f2517.PhaseAwareBranchReceipt
    ]
    control_plan_hash: str
    pre_setup_keepalive_count: int
    remote_setup_acknowledgement_clause: f2512.ClauseEvaluation
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2518_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if tuple(
            item.integrated_receipt.role for item in self.branch_controls
        ) != BRANCH_ROLES:
            raise ValueError("phase-aware pair requires ordered branch roles")
        if tuple(
            item.integrated_receipt.receipt_hash for item in self.branch_controls
        ) != tuple(item.receipt_hash for item in self.semantic_pair.branch_receipts):
            raise ValueError("phase and semantic pair receipts diverged")
        if self.control_plan_hash != f2517.control_plan_hash():
            raise ValueError("pair control plan changed")
        if self.pre_setup_keepalive_count != sum(
            item.pre_setup_keepalive_count for item in self.branch_controls
        ):
            raise ValueError("pair pre-setup keepalive count diverged")
        if self.pre_setup_keepalive_count != 0:
            raise ValueError("dual qualification forbids pre-setup keepalive")
        if self.remote_setup_acknowledgement_clause is not (
            f2512.ClauseEvaluation.NOT_EVALUATED
        ):
            raise ValueError("local branch sends cannot become remote acknowledgement")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(slots=True)
class PhaseAwareDualOpenResult:
    connections: f24._DualConnections | None
    receipt: PhaseAwareDualReceipt

    def close(self) -> None:
        if self.connections is not None:
            self.connections.close()
            self.connections = None


@dataclass(frozen=True, slots=True)
class PhaseAwareCandidateLoopReceipt:
    semantic_outcome: f2514.CandidateLoopReceipt
    attempts: tuple[PhaseAwareDualReceipt, ...]
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2518_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if tuple(item.semantic_pair for item in self.attempts) != (
            self.semantic_outcome.attempts
        ):
            raise ValueError("phase-aware attempts diverged from semantic outcome")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2518Result:
    envelope: F2518ExecutionEnvelope
    physical_receipt: PhaseAwareCandidateLoopReceipt
    receipt_artifact: f2531.ClosedArtifactReceipt


@dataclass(frozen=True, slots=True)
class F2518Assessment:
    exit: F2518Exit
    two_branch_concurrency_materialized: bool
    phase_aware_control_bound_to_both_branches: bool
    pair_topology_preserved: bool
    candidate_loop_materialized: bool
    terminal_receipt_materialized: bool
    post_commit_review_required: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


ConnectorProvider = Callable[[kiwi.KiwiEndpoint, str], Callable[..., object]]


def build_execution_envelope(*, created_at: datetime) -> F2518ExecutionEnvelope:
    return F2518ExecutionEnvelope(
        f2._utc(created_at),
        PARENT_GATE_COMMIT,
        f24.candidate_set_hash(),
        f24.ordered_candidate_identities(),
        BRANCH_ROLES,
        "TWO_THREADS_ONE_ENDPOINT_PHASE_AWARE_SND",
        2,
        1,
        1,
        0,
        0,
        f251.CENTER_POLICY,
        f2514.MAXIMUM_GPS_SOLUTION_AGE_S,
        "NONE_BEFORE_DIRECT_SND",
        "ABSENT_FROM_CAUSAL_PATH",
        "MANDATORY_INJECTION_NO_DEFAULT",
        f2517.control_plan_hash(),
        "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED",
        True,
        "REQUIRED_BEFORE_LIVE_AUTHORITY",
        (f2517.F2517_TRANSFORM_VERSION, F2518_TRANSFORM_VERSION),
    )


def _connector_for_role(
    provider: ConnectorProvider,
    endpoint: kiwi.KiwiEndpoint,
    role: str,
) -> Callable[..., object]:
    def connect(*args: object, **kwargs: object) -> object:
        return provider(endpoint, role)(*args, **kwargs)

    return connect


def open_dual_phase_aware_injected(
    endpoint: kiwi.KiwiEndpoint,
    *,
    connector_provider: ConnectorProvider,
    websocket_module: object,
) -> PhaseAwareDualOpenResult:
    """Open exactly two concurrent corrected branches through injection."""

    started = datetime.now(timezone.utc)
    mother = f2.MotherPlan()
    center_hz = f251.bootstrap_center(endpoint, {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            role: pool.submit(
                f2517.open_channel_phase_aware_injected,
                endpoint,
                role,
                center_hz,
                {},
                mother,
                connector=_connector_for_role(connector_provider, endpoint, role),
                websocket_module=websocket_module,
            )
            for role in BRANCH_ROLES
        }
        results = {role: futures[role].result() for role in BRANCH_ROLES}

    reference = results["reference"]
    perturbed = results["perturbed"]
    controls = (reference.receipt, perturbed.receipt)
    receipts = tuple(item.integrated_receipt for item in controls)
    branch_clauses = tuple(f2514._branch_clause(item) for item in receipts)
    both_ready = all(item.state is f258.F258BranchState.READY for item in receipts)
    overlap_s = f2514._event_overlap_s(*receipts) if both_ready else None
    distinct_ids = (
        both_ready
        and receipts[0].observed_channel_id is not None
        and receipts[1].observed_channel_id is not None
        and receipts[0].observed_channel_id != receipts[1].observed_channel_id
    )
    distinct_connections = (
        both_ready
        and reference.connection is not None
        and perturbed.connection is not None
        and reference.connection.ws is not perturbed.connection.ws
    )
    separate_sequences = both_ready and all(
        item.readiness_sequence is not None for item in receipts
    )
    separate_receipts = receipts[0].receipt_hash != receipts[1].receipt_hash
    topology_ready = (
        both_ready
        and distinct_connections
        and distinct_ids
        and overlap_s is not None
        and overlap_s > 0.0
        and separate_sequences
        and separate_receipts
    )

    connections: f24._DualConnections | None = None
    if topology_ready:
        assert reference.connection is not None and perturbed.connection is not None
        disposition = f252.PairDisposition.ADMITTED_TO_PAIR
        state = f2514.PairState.DUAL_READY
        statement = "two corrected concurrent SND branches satisfy the same-Kiwi topology"
        connections = f24._DualConnections(reference.connection, perturbed.connection)
    elif both_ready:
        reference.connection.close()  # type: ignore[union-attr]
        perturbed.connection.close()  # type: ignore[union-attr]
        disposition = f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION
        state = f2514.PairState.TOPOLOGY_REJECTED
        statement = "two corrected branches opened but pair topology was not witnessed"
    else:
        for result in (reference, perturbed):
            if result.connection is not None:
                result.connection.close()
        disposition = f252.PairDisposition.CLOSED_AFTER_PEER_FAILURE
        if f2512.ClauseEvaluation.QUALIFICATION_ERROR in branch_clauses:
            state = f2514.PairState.QUALIFICATION_INCOMPLETE
            statement = "software or transport left corrected dual-SND availability unresolved"
        else:
            state = f2514.PairState.EXPLICIT_PAIR_REJECTED
            statement = "an explicit response rejected at least one corrected SND branch"

    adjusted_controls = tuple(
        replace(
            item,
            integrated_receipt=replace(
                item.integrated_receipt, pair_disposition=disposition
            ),
        )
        for item in controls
    )
    adjusted = tuple(item.integrated_receipt for item in adjusted_controls)
    not_evaluated = f2512.ClauseEvaluation.NOT_EVALUATED
    semantic = f2514.DualSemanticReceipt(
        receipts[0].endpoint_identity,
        center_hz,
        started,
        datetime.now(timezone.utc),
        state,
        adjusted,  # type: ignore[arg-type]
        True,
        True,
        f2512.ClauseEvaluation.SATISFIED,
        branch_clauses[0],
        branch_clauses[1],
        (
            f2512.ClauseEvaluation.SATISFIED
            if distinct_connections
            else f2512.ClauseEvaluation.UNSATISFIED
            if both_ready
            else not_evaluated
        ),
        (
            f2512.ClauseEvaluation.SATISFIED
            if distinct_ids
            else f2512.ClauseEvaluation.UNSATISFIED
            if both_ready
            else not_evaluated
        ),
        (
            f2512.ClauseEvaluation.SATISFIED
            if overlap_s is not None and overlap_s > 0.0
            else f2512.ClauseEvaluation.UNSATISFIED
            if both_ready
            else not_evaluated
        ),
        (
            f2512.ClauseEvaluation.SATISFIED
            if separate_sequences
            else f2512.ClauseEvaluation.UNSATISFIED
            if both_ready
            else not_evaluated
        ),
        (
            f2512.ClauseEvaluation.SATISFIED
            if separate_receipts
            else f2512.ClauseEvaluation.UNSATISFIED
        ),
        overlap_s,
        statement,
    )
    receipt = PhaseAwareDualReceipt(
        semantic,
        adjusted_controls,  # type: ignore[arg-type]
        f2517.control_plan_hash(),
        sum(item.pre_setup_keepalive_count for item in adjusted_controls),
        f2512.ClauseEvaluation.NOT_EVALUATED,
    )
    return PhaseAwareDualOpenResult(connections, receipt)


def execute_candidate_loop_injected(
    *,
    connector_provider: ConnectorProvider,
    websocket_module: object,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None = None,
) -> F2518Result:
    """Run the frozen candidate loop with corrected injected branches."""

    envelope = build_execution_envelope(created_at=datetime.now(timezone.utc))
    emitter = f2531.TerminalReceiptEmitter(receipt_path, mirror_sink=mirror_sink)
    attempts: list[PhaseAwareDualReceipt] = []
    selected: str | None = None
    try:
        emitter(f"{EVENT_PREFIX}_execution_envelope", envelope)
        for endpoint in f24.ordered_candidates():
            opened = open_dual_phase_aware_injected(
                endpoint,
                connector_provider=connector_provider,
                websocket_module=websocket_module,
            )
            attempts.append(opened.receipt)
            emitter(f"{EVENT_PREFIX}_candidate_pair", opened.receipt)
            if opened.receipt.semantic_pair.state is f2514.PairState.DUAL_READY:
                selected = opened.receipt.semantic_pair.endpoint_identity
                opened.close()
                break
            opened.close()
        frozen_attempts = tuple(attempts)
        semantic_attempts = tuple(item.semantic_pair for item in frozen_attempts)
        semantic = f2514.CandidateLoopReceipt(
            envelope.envelope_hash,
            (
                f2514.CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
                if selected is not None
                else f2514._negative_outcome(semantic_attempts)
            ),
            semantic_attempts,
            selected,
            True,
        )
        physical = PhaseAwareCandidateLoopReceipt(semantic, frozen_attempts)
        emitter(f"{EVENT_PREFIX}_one_outcome", physical)
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    return F2518Result(envelope, physical, emitter.finalize())


def assess_gate_f2_5_18() -> F2518Assessment:
    return F2518Assessment(
        F2518Exit.DUAL_PHASE_AWARE_ENVELOPE_MATERIALIZED_OFFLINE,
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )
