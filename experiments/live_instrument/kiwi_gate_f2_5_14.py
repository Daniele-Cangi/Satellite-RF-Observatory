"""Gate F2.5.14: compose two semantic SND branches, offline only.

The module materialises the exact candidate loop and terminal-receipt boundary
needed by a future reviewed execution.  It has no connector default, imports no
WebSocket implementation and exposes no autonomous live entry point.  Tests
must inject both the connector provider and the framing constants.
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
from . import kiwi_gate_f2_5_13 as f2513
from . import kiwi_probe as kiwi


F2514_TRANSFORM_VERSION = "gate-f2.5.14-dual-semantic-candidate-loop-v1"
PARENT_GATE_COMMIT = "9b093d201cdd95890de723d8f85f3cecdf38df15"
BRANCH_ROLES = ("reference", "perturbed")
EVENT_PREFIX = "gate_f2_5_14"
RAW_RF_PERSISTENCE = "ZERO"
MAXIMUM_GPS_SOLUTION_AGE_S = 30


class PairState(str, Enum):
    DUAL_READY = "DUAL_READY"
    EXPLICIT_PAIR_REJECTED = "EXPLICIT_PAIR_REJECTED"
    QUALIFICATION_INCOMPLETE = "QUALIFICATION_INCOMPLETE"
    TOPOLOGY_REJECTED = "TOPOLOGY_REJECTED"


class CandidateLoopOutcome(str, Enum):
    DUAL_SEMANTIC_PAIR_READY = "DUAL_SEMANTIC_PAIR_READY"
    NO_MULTI_CHANNEL_CAPABILITY = "NO_MULTI_CHANNEL_CAPABILITY"
    NO_ADMISSIBLE_CAUSAL_TOPOLOGY = "NO_ADMISSIBLE_CAUSAL_TOPOLOGY"
    QUALIFICATION_INCOMPLETE = "QUALIFICATION_INCOMPLETE"


class F2514Exit(str, Enum):
    DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE = (
        "DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE"
    )


@dataclass(frozen=True, slots=True)
class F2514ExecutionEnvelope:
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
    endpoint_status_precondition: str
    ext_api_semantics: str
    waterfall_semantics: str
    connector_semantics: str
    candidate_stop_condition: str
    terminal_receipt_required: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]
    post_commit_review_state: str

    def __post_init__(self) -> None:
        f2._utc(self.created_at)
        if self.parent_gate_commit != PARENT_GATE_COMMIT:
            raise ValueError("Gate F2.5.13 lineage changed")
        if self.candidate_set_hash != f24.candidate_set_hash():
            raise ValueError("candidate set changed")
        if self.candidate_order != f24.ordered_candidate_identities():
            raise ValueError("candidate order changed")
        if self.branch_roles != BRANCH_ROLES:
            raise ValueError("the fixed/perturbed branch roles changed")
        if self.branch_composition != "TWO_THREADS_ONE_ENDPOINT_TWO_SEMANTIC_SND_BRANCHES":
            raise ValueError("the dual-SND branch composition changed")
        if (
            self.maximum_parallel_branches != 2
            or self.maximum_parallel_endpoints != 1
            or self.attempts_per_candidate != 1
        ):
            raise ValueError("the dual-SND concurrency envelope changed")
        if self.prefreeze_retry_budget != 0 or self.postfreeze_retry_budget != 0:
            raise ValueError("Gate F2.5.14 admits no retry")
        if self.center_policy != f251.CENTER_POLICY:
            raise ValueError("the data-independent center policy changed")
        if self.maximum_gps_solution_age_s != MAXIMUM_GPS_SOLUTION_AGE_S:
            raise ValueError("the semantic GPS-age clause changed")
        if self.endpoint_status_precondition != "NONE_BEFORE_DIRECT_SND":
            raise ValueError("status cannot become a pre-SND gate")
        if self.ext_api_semantics != "NOT_ACCESSED_NOT_A_GATE":
            raise ValueError("ext_api cannot become a qualification gate")
        if self.waterfall_semantics != "ABSENT_FROM_CAUSAL_PATH":
            raise ValueError("waterfall cannot return to the causal path")
        if self.connector_semantics != "MANDATORY_INJECTION_NO_DEFAULT":
            raise ValueError("the module cannot acquire a live connector")
        if self.candidate_stop_condition != "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED":
            raise ValueError("candidate stop semantics changed")
        if not self.terminal_receipt_required:
            raise ValueError("terminal receipt closure is required")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2512.F2512_TRANSFORM_VERSION,
            f2513.F2513_TRANSFORM_VERSION,
            F2514_TRANSFORM_VERSION,
        ):
            raise ValueError("Gate F2.5.14 transform ledger changed")
        if self.post_commit_review_state != "REQUIRED_BEFORE_LIVE_AUTHORITY":
            raise ValueError("post-commit causal-source review cannot be skipped")

    @property
    def envelope_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class DualSemanticReceipt:
    endpoint_identity: str
    center_hz: float
    started_at: datetime
    completed_at: datetime
    state: PairState
    branch_receipts: tuple[
        f2513.IntegratedBranchReceipt, f2513.IntegratedBranchReceipt
    ]
    direct_reference_attempted: bool
    direct_perturbed_attempted: bool
    same_endpoint_clause: f2512.ClauseEvaluation
    reference_ready_clause: f2512.ClauseEvaluation
    perturbed_ready_clause: f2512.ClauseEvaluation
    distinct_connection_objects_clause: f2512.ClauseEvaluation
    distinct_channel_ids_clause: f2512.ClauseEvaluation
    event_time_overlap_clause: f2512.ClauseEvaluation
    separate_stream_sequences_clause: f2512.ClauseEvaluation
    separate_branch_receipts_clause: f2512.ClauseEvaluation
    overlap_s: float | None
    statement: str
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2514_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        f2._utc(self.started_at)
        f2._utc(self.completed_at)
        if self.completed_at < self.started_at:
            raise ValueError("pair receipt time is reversed")
        if tuple(item.role for item in self.branch_receipts) != BRANCH_ROLES:
            raise ValueError("pair receipt roles must be complete and ordered")
        if any(item.endpoint_identity != self.endpoint_identity for item in self.branch_receipts):
            raise ValueError("pair branches must come from one endpoint")
        if not self.direct_reference_attempted or not self.direct_perturbed_attempted:
            raise ValueError("a pair receipt requires two direct branch attempts")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        topology = (
            self.same_endpoint_clause,
            self.reference_ready_clause,
            self.perturbed_ready_clause,
            self.distinct_connection_objects_clause,
            self.distinct_channel_ids_clause,
            self.event_time_overlap_clause,
            self.separate_stream_sequences_clause,
            self.separate_branch_receipts_clause,
        )
        if self.state is PairState.DUAL_READY and any(
            item is not f2512.ClauseEvaluation.SATISFIED for item in topology
        ):
            raise ValueError("DUAL_READY requires every pair-topology clause")
        if self.state is PairState.DUAL_READY and self.overlap_s is None:
            raise ValueError("DUAL_READY requires event-time overlap")
        if self.state is PairState.QUALIFICATION_INCOMPLETE and (
            f2512.ClauseEvaluation.QUALIFICATION_ERROR
            not in (self.reference_ready_clause, self.perturbed_ready_clause)
        ):
            raise ValueError("QUALIFICATION_INCOMPLETE requires a descriptive branch error")
        if self.state is PairState.EXPLICIT_PAIR_REJECTED and (
            f2512.ClauseEvaluation.QUALIFICATION_ERROR
            in (self.reference_ready_clause, self.perturbed_ready_clause)
            or f2512.ClauseEvaluation.UNSATISFIED
            not in (self.reference_ready_clause, self.perturbed_ready_clause)
        ):
            raise ValueError("explicit pair rejection requires a physical branch refusal")
        if self.state is PairState.TOPOLOGY_REJECTED and (
            self.reference_ready_clause is not f2512.ClauseEvaluation.SATISFIED
            or self.perturbed_ready_clause is not f2512.ClauseEvaluation.SATISFIED
        ):
            raise ValueError("topology rejection requires two ready branches")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(slots=True)
class DualSemanticOpenResult:
    connections: f24._DualConnections | None
    receipt: DualSemanticReceipt

    def close(self) -> None:
        if self.connections is not None:
            self.connections.close()
            self.connections = None


@dataclass(frozen=True, slots=True)
class CandidateLoopReceipt:
    envelope_hash: str
    outcome: CandidateLoopOutcome
    attempts: tuple[DualSemanticReceipt, ...]
    selected_endpoint_identity: str | None
    stopped_after_first_outcome: bool
    raw_rf_persistence: str = RAW_RF_PERSISTENCE
    transform_version: str = F2514_TRANSFORM_VERSION

    def __post_init__(self) -> None:
        if len(self.envelope_hash) != 64 or any(
            character not in "0123456789abcdef" for character in self.envelope_hash
        ):
            raise ValueError("candidate loop requires the frozen envelope SHA-256")
        if not self.attempts:
            raise ValueError("candidate loop must attempt at least one endpoint")
        expected = f24.ordered_candidate_identities()[: len(self.attempts)]
        if tuple(item.endpoint_identity for item in self.attempts) != expected:
            raise ValueError("candidate attempts must preserve frozen order")
        ready = tuple(item for item in self.attempts if item.state is PairState.DUAL_READY)
        if self.outcome is CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY:
            if len(ready) != 1 or ready[-1] is not self.attempts[-1]:
                raise ValueError("candidate loop must stop at the first ready pair")
            if self.selected_endpoint_identity != ready[0].endpoint_identity:
                raise ValueError("selected endpoint does not match the ready pair")
        elif ready or self.selected_endpoint_identity is not None:
            raise ValueError("a negative loop outcome cannot select an endpoint")
        if self.outcome is CandidateLoopOutcome.NO_MULTI_CHANNEL_CAPABILITY and (
            len(self.attempts) != len(f24.ordered_candidates())
            or any(
                item.state is not PairState.EXPLICIT_PAIR_REJECTED
                for item in self.attempts
            )
        ):
            raise ValueError("NO_MULTI requires exhausted explicit two-branch refusals")
        if self.outcome is CandidateLoopOutcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY and (
            len(self.attempts) != len(f24.ordered_candidates())
            or not any(item.state is PairState.TOPOLOGY_REJECTED for item in self.attempts)
            or any(
                item.state is PairState.QUALIFICATION_INCOMPLETE
                for item in self.attempts
            )
        ):
            raise ValueError("NO_ADMISSIBLE requires exhausted, evaluable topology attempts")
        if self.outcome is CandidateLoopOutcome.QUALIFICATION_INCOMPLETE and (
            len(self.attempts) != len(f24.ordered_candidates())
            or not any(
                item.state is PairState.QUALIFICATION_INCOMPLETE
                for item in self.attempts
            )
        ):
            raise ValueError("QUALIFICATION_INCOMPLETE requires exhausted unresolved attempts")
        if not self.stopped_after_first_outcome:
            raise ValueError("the one-outcome stop is mandatory")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2514Result:
    envelope: F2514ExecutionEnvelope
    physical_receipt: CandidateLoopReceipt
    receipt_artifact: f2531.ClosedArtifactReceipt


@dataclass(frozen=True, slots=True)
class F2514Assessment:
    exit: F2514Exit
    two_branch_concurrency_materialized: bool
    candidate_loop_materialized: bool
    terminal_receipt_materialized: bool
    exact_envelope_materialized: bool
    post_commit_review_required: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


ConnectorProvider = Callable[
    [kiwi.KiwiEndpoint, str], Callable[..., object]
]


def build_execution_envelope(*, created_at: datetime) -> F2514ExecutionEnvelope:
    return F2514ExecutionEnvelope(
        f2._utc(created_at),
        PARENT_GATE_COMMIT,
        f24.candidate_set_hash(),
        f24.ordered_candidate_identities(),
        BRANCH_ROLES,
        "TWO_THREADS_ONE_ENDPOINT_TWO_SEMANTIC_SND_BRANCHES",
        2,
        1,
        1,
        0,
        0,
        f251.CENTER_POLICY,
        MAXIMUM_GPS_SOLUTION_AGE_S,
        "NONE_BEFORE_DIRECT_SND",
        "NOT_ACCESSED_NOT_A_GATE",
        "ABSENT_FROM_CAUSAL_PATH",
        "MANDATORY_INJECTION_NO_DEFAULT",
        "FIRST_DUAL_READY_OR_CANDIDATES_EXHAUSTED",
        True,
        RAW_RF_PERSISTENCE,
        (
            f2512.F2512_TRANSFORM_VERSION,
            f2513.F2513_TRANSFORM_VERSION,
            F2514_TRANSFORM_VERSION,
        ),
        "REQUIRED_BEFORE_LIVE_AUTHORITY",
    )


def _branch_clause(
    receipt: f2513.IntegratedBranchReceipt,
) -> f2512.ClauseEvaluation:
    if receipt.state is f258.F258BranchState.READY:
        return f2512.ClauseEvaluation.SATISFIED
    if receipt.state is f258.F258BranchState.CAPABILITY_REJECTED:
        return f2512.ClauseEvaluation.UNSATISFIED
    return f2512.ClauseEvaluation.QUALIFICATION_ERROR


def _event_overlap_s(
    left: f2513.IntegratedBranchReceipt,
    right: f2513.IntegratedBranchReceipt,
) -> float | None:
    bounds = (
        left.readiness_event_start,
        left.readiness_event_end,
        right.readiness_event_start,
        right.readiness_event_end,
    )
    if any(value is None for value in bounds):
        return None
    left_start, left_end, right_start, right_end = bounds
    assert left_start is not None and left_end is not None
    assert right_start is not None and right_end is not None
    return max(
        0.0,
        (min(left_end, right_end) - max(left_start, right_start)).total_seconds(),
    )


def _connector_for_role(
    provider: ConnectorProvider,
    endpoint: kiwi.KiwiEndpoint,
    role: str,
) -> Callable[..., object]:
    def connect(*args: object, **kwargs: object) -> object:
        connector = provider(endpoint, role)
        return connector(*args, **kwargs)

    return connect


def open_dual_semantic_injected(
    endpoint: kiwi.KiwiEndpoint,
    *,
    connector_provider: ConnectorProvider,
    websocket_module: object,
) -> DualSemanticOpenResult:
    """Attempt both SND branches concurrently through mandatory injection."""

    started = datetime.now(timezone.utc)
    mother = f2.MotherPlan()
    if mother.maximum_gps_solution_age_s != MAXIMUM_GPS_SOLUTION_AGE_S:
        raise RuntimeError("the frozen semantic GPS-age clause changed")
    center_hz = f251.bootstrap_center(endpoint, {})
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            role: pool.submit(
                f2513.open_channel_semantic_injected,
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
    receipts = (reference.receipt, perturbed.receipt)
    branch_clauses = tuple(_branch_clause(item) for item in receipts)
    both_ready = all(
        item.state is f258.F258BranchState.READY for item in receipts
    )
    overlap_s = _event_overlap_s(*receipts) if both_ready else None
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
        state = PairState.DUAL_READY
        statement = (
            "two concurrent semantic SND branches expose distinct channel allocations "
            "and overlapping event-time IQ readiness"
        )
        connections = f24._DualConnections(reference.connection, perturbed.connection)
    elif both_ready:
        reference.connection.close()  # type: ignore[union-attr]
        perturbed.connection.close()  # type: ignore[union-attr]
        disposition = f252.PairDisposition.CLOSED_AFTER_TOPOLOGY_REJECTION
        state = PairState.TOPOLOGY_REJECTED
        statement = "both branches opened but the required same-Kiwi channel topology was not witnessed"
    else:
        for result in (reference, perturbed):
            if result.connection is not None:
                result.connection.close()
        disposition = f252.PairDisposition.CLOSED_AFTER_PEER_FAILURE
        if f2512.ClauseEvaluation.QUALIFICATION_ERROR in branch_clauses:
            state = PairState.QUALIFICATION_INCOMPLETE
            statement = "software or transport left simultaneous channel availability unresolved"
        else:
            state = PairState.EXPLICIT_PAIR_REJECTED
            statement = "an explicit server control response rejected at least one direct SND branch"

    adjusted = tuple(
        replace(item, pair_disposition=disposition) for item in receipts
    )
    not_evaluated = f2512.ClauseEvaluation.NOT_EVALUATED
    receipt = DualSemanticReceipt(
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
    return DualSemanticOpenResult(connections, receipt)


def _negative_outcome(
    attempts: tuple[DualSemanticReceipt, ...],
) -> CandidateLoopOutcome:
    states = {item.state for item in attempts}
    if PairState.QUALIFICATION_INCOMPLETE in states:
        return CandidateLoopOutcome.QUALIFICATION_INCOMPLETE
    if PairState.TOPOLOGY_REJECTED in states:
        return CandidateLoopOutcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY
    return CandidateLoopOutcome.NO_MULTI_CHANNEL_CAPABILITY


def execute_candidate_loop_injected(
    *,
    connector_provider: ConnectorProvider,
    websocket_module: object,
    receipt_path: Path,
    mirror_sink: Callable[[str], None] | None = None,
) -> F2514Result:
    """Exercise the frozen loop with injected sockets and close one terminal receipt."""

    created_at = datetime.now(timezone.utc)
    envelope = build_execution_envelope(created_at=created_at)
    emitter = f2531.TerminalReceiptEmitter(receipt_path, mirror_sink=mirror_sink)
    attempts: list[DualSemanticReceipt] = []
    selected: str | None = None
    try:
        emitter(f"{EVENT_PREFIX}_execution_envelope", envelope)
        for endpoint in f24.ordered_candidates():
            opened = open_dual_semantic_injected(
                endpoint,
                connector_provider=connector_provider,
                websocket_module=websocket_module,
            )
            attempts.append(opened.receipt)
            emitter(f"{EVENT_PREFIX}_candidate_pair", opened.receipt)
            if opened.receipt.state is PairState.DUAL_READY:
                selected = opened.receipt.endpoint_identity
                opened.close()
                break
            opened.close()
        frozen_attempts = tuple(attempts)
        outcome = (
            CandidateLoopOutcome.DUAL_SEMANTIC_PAIR_READY
            if selected is not None
            else _negative_outcome(frozen_attempts)
        )
        physical = CandidateLoopReceipt(
            envelope.envelope_hash,
            outcome,
            frozen_attempts,
            selected,
            True,
        )
        emitter(f"{EVENT_PREFIX}_one_outcome", physical)
    except BaseException as error:
        emitter.record_runtime_error(error)
        emitter.finalize()
        raise
    return F2514Result(envelope, physical, emitter.finalize())


def assess_gate_f2_5_14() -> F2514Assessment:
    return F2514Assessment(
        F2514Exit.DUAL_ONE_SHOT_ENVELOPE_MATERIALIZED_OFFLINE,
        True,
        True,
        True,
        True,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )
