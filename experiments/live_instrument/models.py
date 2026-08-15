"""Small in-memory epistemic model shared by the two Gate B probes.

This is data, not a source framework. SatNOGS and Kiwi keep separate probe
implementations and only exchange the records that the first experiments have
actually shown to be common.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any, Callable


class ClauseStatus(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    UNRESOLVED = "UNRESOLVED"


class ModelAvailability(str, Enum):
    MODEL_AVAILABLE = "MODEL_AVAILABLE"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class Intent:
    """A question may name a target, but target-first is no longer mandatory."""

    question: str
    target: str | None = None


@dataclass(frozen=True, slots=True)
class DecisionClause:
    name: str
    requirement: str
    required_observables: tuple[str, ...] = ()
    minimum_measurement_roots: int = 1


@dataclass(frozen=True, slots=True)
class DecisionContract:
    intent: Intent
    clauses: tuple[DecisionClause, ...]
    max_measurement_age_s: float | None

    def __post_init__(self) -> None:
        names = [clause.name for clause in self.clauses]
        if not names or len(names) != len(set(names)):
            raise ValueError("a DecisionContract needs uniquely named clauses")
        if self.max_measurement_age_s is not None and self.max_measurement_age_s < 0:
            raise ValueError("measurement TTL cannot be negative")

    def measurement_age_s(self, event_end: datetime, now: datetime) -> float:
        return (_utc(now) - _utc(event_end)).total_seconds()

    def accepts_age(self, event_end: datetime, now: datetime) -> bool:
        age = self.measurement_age_s(event_end, now)
        return age >= 0.0 and (
            self.max_measurement_age_s is None
            or age <= self.max_measurement_age_s
        )

    def snapshot_from_evidence(
        self,
        receipt: "ConstraintReceipt",
        *,
        valid_at: datetime,
        clause_assessments: tuple["ClauseAssessment", ...],
        uncertainty: tuple[str, ...],
        active_model_roots: tuple[str, ...],
    ) -> "BeliefSnapshot":
        """Build the only runtime belief form and enforce TTL/contract invariants."""

        expected = {clause.name: clause for clause in self.clauses}
        actual = {assessment.clause: assessment for assessment in clause_assessments}
        if len(actual) != len(clause_assessments) or set(actual) != set(expected):
            raise ValueError("clause assessments must match the DecisionContract exactly")
        for name, assessment in actual.items():
            minimum_roots = expected[name].minimum_measurement_roots
            if (
                assessment.status is ClauseStatus.SATISFIED
                and len(set(assessment.measurement_roots)) < minimum_roots
            ):
                raise ValueError(f"clause {name!r} lacks its required measurement roots")

        valid_at = _utc(valid_at)
        age = self.measurement_age_s(receipt.event_end, valid_at)
        if not self.accepts_age(receipt.event_end, valid_at) and any(
            assessment.status is ClauseStatus.SATISFIED
            for assessment in clause_assessments
        ):
            raise ValueError("expired evidence cannot satisfy a DecisionContract clause")
        return BeliefSnapshot(
            valid_at=valid_at,
            measurement_age_s=age,
            clause_assessments=clause_assessments,
            uncertainty=uncertainty,
            active_measurement_roots=receipt.measurement_roots,
            active_model_roots=active_model_roots,
            target=self.intent.target,
        )


@dataclass(frozen=True, slots=True)
class Transform:
    name: str
    state: str
    detail: str
    model_roots: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Constraint:
    name: str
    relation: str
    value: Any
    unit: str | None
    uncertainty: str
    basis: str


@dataclass(frozen=True, slots=True)
class ConstraintReceipt:
    branch: str
    event_start: datetime
    event_end: datetime
    constraints: tuple[Constraint, ...]
    transforms: tuple[Transform, ...]
    measurement_roots: tuple[str, ...]
    model_roots: tuple[str, ...]
    artifact_hashes: tuple[str, ...]
    caveats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EvidenceEvent:
    source: str
    arrived_at: datetime
    receipt: ConstraintReceipt


@dataclass(frozen=True, slots=True)
class ClauseAssessment:
    clause: str
    status: ClauseStatus
    statement: str
    measurement_roots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BeliefSnapshot:
    valid_at: datetime
    measurement_age_s: float
    clause_assessments: tuple[ClauseAssessment, ...]
    uncertainty: tuple[str, ...]
    active_measurement_roots: tuple[str, ...]
    active_model_roots: tuple[str, ...]
    target: str | None

    def assessment(self, clause: str) -> ClauseAssessment:
        for assessment in self.clause_assessments:
            if assessment.clause == clause:
                return assessment
        raise KeyError(clause)


@dataclass(frozen=True, slots=True)
class ModelSnapshot:
    status: ModelAvailability
    valid_at: datetime
    statement: str
    model_roots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CausalNode:
    node_id: str
    kind: str
    detail: str


@dataclass(frozen=True, slots=True)
class CausalEdge:
    effect: str
    cause: str
    relation: str


@dataclass(slots=True)
class CausalGraph:
    """A deliberately tiny RAM-only causal graph."""

    nodes: dict[str, CausalNode] = field(default_factory=dict)
    edges: list[CausalEdge] = field(default_factory=list)

    def add_node(self, node_id: str, kind: str, detail: str) -> None:
        existing = self.nodes.get(node_id)
        candidate = CausalNode(node_id, kind, detail)
        if existing is not None and existing != candidate:
            raise ValueError(f"causal node {node_id!r} was redefined")
        self.nodes[node_id] = candidate

    def add_dependency(self, effect: str, cause: str, relation: str) -> None:
        if effect not in self.nodes or cause not in self.nodes:
            raise ValueError("both causal nodes must exist before adding an edge")
        edge = CausalEdge(effect, cause, relation)
        if edge not in self.edges:
            self.edges.append(edge)

    def root_ids(self, kind: str) -> tuple[str, ...]:
        return tuple(sorted(node.node_id for node in self.nodes.values() if node.kind == kind))

    def snapshot(self) -> dict[str, Any]:
        return {
            "nodes": [_jsonable(node) for node in self.nodes.values()],
            "edges": [_jsonable(edge) for edge in self.edges],
        }


def emit_jsonl(
    event_type: str,
    payload: Any,
    *,
    sink: Callable[[str], None] = print,
) -> None:
    sink(
        json.dumps(
            {"event": event_type, "payload": _jsonable(payload)},
            allow_nan=False,
            sort_keys=True,
        )
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set)):
        return [_jsonable(item) for item in value]
    return value
