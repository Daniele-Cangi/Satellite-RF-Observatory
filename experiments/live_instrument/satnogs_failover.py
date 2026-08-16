"""Checkpoint 3: clause-driven SatNOGS failover in memory.

The older Probe A receipt fused two stations into one evidence object.  That
made a station revocation impossible to express honestly: removing one root
would invalidate an indivisible two-root receipt.  This experiment instead
makes each downloaded waterfall one atomic receipt with one hardware root.
Decision contracts compose those atoms at evaluation time.

The controlled SatNOGS job identity is used only to keep candidate artifacts
comparable.  It is never counted as RF evidence for emitter identity.  All
offer, lease, revocation, and belief state is process-local and ephemeral.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from time import perf_counter
from typing import Callable, Iterable, Sequence

from .models import (
    BeliefSnapshot,
    ClauseAssessment,
    ClauseStatus,
    Constraint,
    ConstraintReceipt,
    DecisionClause,
    DecisionContract,
    EvidenceEvent,
    Intent,
    ModelAvailability,
    ModelSnapshot,
    Transform,
    emit_jsonl,
)
from .orbital_kernel import (
    Observer,
    OrbitalKernelError,
    TLEElements,
    compute_orbital_state,
)
from .satnogs_probe import (
    SatnogsObservation,
    WaterfallArtifact,
    fetch_recent_observations,
    fetch_waterfall,
    rank_fresh_pairs,
)


RF_STRUCTURE = "structured_rf_energy"
EVENT_TIME = "event_time"


@dataclass(frozen=True, slots=True)
class CapabilityOffer:
    """A verified, short-lived offer backed by one atomic waterfall receipt."""

    offer_id: str
    evidence: EvidenceEvent
    provided_observables: tuple[str, ...]
    control_context: tuple[int, str]
    request_count: int
    bytes_received: int
    model_propagable: bool

    @property
    def receipt(self) -> ConstraintReceipt:
        return self.evidence.receipt

    @property
    def measurement_root(self) -> str:
        roots = self.receipt.measurement_roots
        if len(roots) != 1:
            raise ValueError("an atomic SatNOGS offer must have exactly one measurement root")
        return roots[0]


@dataclass(frozen=True, slots=True)
class ObservationLease:
    """Process-local authority to use one offer for one decision contract."""

    lease_id: str
    offer: CapabilityOffer
    acquired_at: datetime


@dataclass(frozen=True, slots=True)
class TransformDeficits:
    """Explicit deficits used for ranking, never a truth/confidence score."""

    unknown: int
    partial: int
    model_conditioned: int
    lossy: int

    def sort_key(self) -> tuple[int, int, int, int]:
        return (self.unknown, self.partial, self.model_conditioned, self.lossy)


@dataclass(frozen=True, slots=True)
class CandidateScore:
    offer_id: str
    restored_clauses: tuple[str, ...]
    clause_root_gain: int
    remaining_ttl_s: float | None
    new_measurement_roots: int
    shared_model_roots: int
    transform_deficits: TransformDeficits
    value_per_cost: float
    request_count: int
    bytes_received: int

    def sort_key(self) -> tuple[object, ...]:
        ttl_for_sort = float("inf") if self.remaining_ttl_s is None else self.remaining_ttl_s
        return (
            -len(self.restored_clauses),
            -self.clause_root_gain,
            -ttl_for_sort,
            -self.new_measurement_roots,
            self.shared_model_roots,
            *self.transform_deficits.sort_key(),
            -self.value_per_cost,
            self.request_count,
            self.bytes_received,
            self.offer_id,
        )


@dataclass(frozen=True, slots=True)
class CandidateRejection:
    offer_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReplacementDecision:
    selected: CapabilityOffer | None
    selected_score: CandidateScore | None
    ranked_scores: tuple[CandidateScore, ...]
    rejections: tuple[CandidateRejection, ...]


@dataclass(frozen=True, slots=True)
class ContractEvaluation:
    contract: DecisionContract
    belief: BeliefSnapshot
    supporting_offer_ids: tuple[str, ...]
    expired_offer_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FailoverResult:
    revoked_offer_id: str
    lost_clauses: tuple[str, ...]
    before: ContractEvaluation
    after_revocation: ContractEvaluation
    decision: ReplacementDecision
    replacement_lease: ObservationLease | None
    after_replacement: ContractEvaluation
    model_snapshot: ModelSnapshot
    candidates_considered: int
    replacement_requests: int
    replacement_bytes: int


@dataclass(frozen=True, slots=True)
class LiveFailoverResult:
    continuity_contract: DecisionContract
    corroboration_contract: DecisionContract
    continuity_failover: FailoverResult
    corroboration_after_revocation: ContractEvaluation


def continuity_contract(max_measurement_age_s: float = 600.0) -> DecisionContract:
    """Contract for maintaining at least one fresh physical measurement root."""

    return DecisionContract(
        intent=Intent("Is fresh structured RF evidence continuously observable?"),
        clauses=(
            DecisionClause(
                "measurement_continuity",
                "fresh structured RF and event time from at least one station root",
                (RF_STRUCTURE, EVENT_TIME),
                1,
            ),
        ),
        max_measurement_age_s=max_measurement_age_s,
    )


def corroboration_contract(max_measurement_age_s: float = 600.0) -> DecisionContract:
    """Contract for two distinct hardware roots observing comparable context."""

    return DecisionContract(
        intent=Intent(
            "Is fresh structured RF evidence corroborated by independent station roots?",
            target="SatNOGS job identity retained only as control context",
        ),
        clauses=(
            DecisionClause(
                "measurement_corroboration",
                "fresh structured RF and event time from two distinct station roots",
                (RF_STRUCTURE, EVENT_TIME),
                2,
            ),
        ),
        max_measurement_age_s=max_measurement_age_s,
    )


def atomic_offer_from_artifact(artifact: WaterfallArtifact) -> CapabilityOffer:
    """Turn one real waterfall into one-root evidence and an ephemeral offer."""

    observation = artifact.observation
    structured_fraction = float(artifact.constraints.get("structured_time_fraction", 0.0))
    provided = (EVENT_TIME,)
    if structured_fraction > 0.0:
        provided = (RF_STRUCTURE, EVENT_TIME)

    gp_fingerprint = sha256(f"{observation.tle1}|{observation.tle2}".encode()).hexdigest()[:16]
    measurement_root = f"station:{observation.station_id}"
    model_roots = (
        "satnogs:network-flowgraph-storage",
        f"satnogs-db:transmitter:{observation.transmitter_uuid}",
        f"gp-control-family:{gp_fingerprint}",
    )
    transforms = (
        Transform(
            "station_rf_chain",
            "partial",
            "antenna/front-end/clock calibration is not fully published",
        ),
        Transform(
            "tuning",
            "partial",
            "job/client tuning is known; oscillator truth is not",
        ),
        Transform(
            "doppler_compensation",
            "model_conditioned",
            "flowgraph conditions the observable on GP control",
            model_roots[-1:],
        ),
        Transform(
            "fft_waterfall_png",
            "known_lossy",
            "FFT output was color-mapped and rasterized",
        ),
        Transform(
            "upload",
            "known",
            "arrival and optional HTTP publication time remain distinct from event time",
        ),
    )
    constraints = (
        Constraint(
            RF_STRUCTURE,
            "present" if structured_fraction > 0.0 else "not_detected",
            artifact.constraints,
            None,
            "PNG raster/colormap and axes are lossy",
            "image-domain structure only; not calibrated IQ, power, or absolute frequency",
        ),
        Constraint(
            EVENT_TIME,
            "recorded_as",
            {"start": observation.start, "end": observation.end},
            None,
            "event window is SatNOGS control metadata",
            "measurement age is always computed from event end",
        ),
        Constraint(
            "target_identity",
            "not_inferred",
            observation.norad_id,
            None,
            "job identity is circular control metadata",
            "selection label retained only to compare controlled observations",
        ),
    )
    receipt = ConstraintReceipt(
        branch="satnogs-waterfall-atomic",
        event_start=observation.start,
        event_end=observation.end,
        constraints=constraints,
        transforms=transforms,
        measurement_roots=(measurement_root,),
        model_roots=model_roots,
        artifact_hashes=(artifact.sha256_hex,),
        caveats=(
            "one waterfall is one atomic hardware-root receipt",
            "SatNOGS software, storage, transmitter catalog, and GP control remain shared roots",
            "target identity is not a provided observable",
        ),
    )
    evidence = EvidenceEvent(
        source="satnogs-network",
        arrived_at=_utc(artifact.arrived_at),
        receipt=receipt,
    )
    return CapabilityOffer(
        offer_id=f"satnogs:{observation.observation_id}",
        evidence=evidence,
        provided_observables=provided,
        control_context=(observation.norad_id, observation.transmitter_uuid),
        request_count=1,
        bytes_received=artifact.content_length,
        model_propagable=_model_is_propagable(observation),
    )


def evaluate_contract(
    contract: DecisionContract,
    active_offers: Sequence[CapabilityOffer],
    now: datetime,
) -> ContractEvaluation:
    """Evaluate clauses from atomic offers without creating composite evidence."""

    now = _utc(now)
    offers = tuple(_deduplicate_offers(active_offers))
    expired = tuple(
        sorted(
            offer.offer_id
            for offer in offers
            if not contract.accepts_age(offer.receipt.event_end, now)
        )
    )
    assessments: list[ClauseAssessment] = []
    supporting_ids: set[str] = set()
    active_roots: set[str] = set()
    active_model_roots: set[str] = set()
    supporting_ages: list[float] = []

    for clause in contract.clauses:
        eligible = [
            offer
            for offer in offers
            if contract.accepts_age(offer.receipt.event_end, now)
            and set(clause.required_observables).issubset(offer.provided_observables)
        ]
        # Evidence from unrelated jobs/passes must not be pooled merely to make
        # a root count.  The best set has one fresh offer per hardware root,
        # one control context, and a non-empty common event window.
        selected = _select_compatible_support(eligible)
        roots = tuple(sorted(offer.measurement_root for offer in selected))
        satisfied = len(roots) >= clause.minimum_measurement_roots
        status = ClauseStatus.SATISFIED if satisfied else ClauseStatus.UNOBSERVABLE
        assessments.append(
            ClauseAssessment(
                clause=clause.name,
                status=status,
                statement=(
                    f"{len(roots)} independent measurement root(s) provide "
                    f"{', '.join(clause.required_observables)}; "
                    f"{clause.minimum_measurement_roots} required."
                ),
                measurement_roots=roots,
            )
        )
        for offer in selected:
            supporting_ids.add(offer.offer_id)
            active_roots.add(offer.measurement_root)
            active_model_roots.update(offer.receipt.model_roots)
            supporting_ages.append(contract.measurement_age_s(offer.receipt.event_end, now))

    if supporting_ages:
        measurement_age_s = max(supporting_ages)
    else:
        historical_ages = [
            contract.measurement_age_s(offer.receipt.event_end, now) for offer in offers
        ]
        measurement_age_s = min(historical_ages) if historical_ages else 0.0

    belief = BeliefSnapshot(
        valid_at=now,
        measurement_age_s=measurement_age_s,
        clause_assessments=tuple(assessments),
        uncertainty=(
            "waterfalls are model-conditioned lossy residual artifacts",
            "distinct station hardware roots share SatNOGS software and catalog lineage",
            "controlled target identity is not inferred from job metadata",
        ),
        active_measurement_roots=tuple(sorted(active_roots)),
        active_model_roots=tuple(sorted(active_model_roots)),
        target=contract.intent.target,
    )
    return ContractEvaluation(
        contract=contract,
        belief=belief,
        supporting_offer_ids=tuple(sorted(supporting_ids)),
        expired_offer_ids=expired,
    )


def model_snapshot(offers: Sequence[CapabilityOffer], now: datetime) -> ModelSnapshot:
    """Report model availability separately; it never satisfies measurement clauses."""

    roots = tuple(
        sorted(
            {
                root
                for offer in offers
                if offer.model_propagable
                for root in offer.receipt.model_roots
            }
        )
    )
    available = bool(roots)
    return ModelSnapshot(
        status=(
            ModelAvailability.MODEL_AVAILABLE
            if available
            else ModelAvailability.MODEL_UNAVAILABLE
        ),
        valid_at=_utc(now),
        statement=(
            "A model-conditioned orbital/control context remains available, but it is not a physical measurement."
            if available
            else "No model context is available."
        ),
        model_roots=roots,
    )


def select_replacement(
    contract: DecisionContract,
    active_offers: Sequence[CapabilityOffer],
    candidates: Sequence[CapabilityOffer],
    now: datetime,
    *,
    revoked_offer_ids: frozenset[str] = frozenset(),
    revoked_measurement_roots: frozenset[str] = frozenset(),
    lost_clauses: Sequence[str] | None = None,
) -> ReplacementDecision:
    """Select a replacement by clause value and evidence properties, never ID."""

    now = _utc(now)
    active = tuple(_deduplicate_offers(active_offers))
    active_ids = {offer.offer_id for offer in active}
    active_roots = {offer.measurement_root for offer in active}
    active_model_roots = {root for offer in active for root in offer.receipt.model_roots}
    baseline = evaluate_contract(contract, active, now)
    lost = tuple(
        lost_clauses
        if lost_clauses is not None
        else (
            item.clause
            for item in baseline.belief.clause_assessments
            if item.status is ClauseStatus.UNOBSERVABLE
        )
    )
    contract_clause_names = {clause.name for clause in contract.clauses}
    if not set(lost).issubset(contract_clause_names):
        raise ValueError("lost_clauses must name clauses in the DecisionContract")

    scores: list[CandidateScore] = []
    rejections: list[CandidateRejection] = []
    for candidate in _deduplicate_offers(candidates):
        reasons: list[str] = []
        if candidate.offer_id in active_ids:
            reasons.append("offer is already leased")
        if candidate.offer_id in revoked_offer_ids:
            reasons.append("offer was revoked")
        if candidate.measurement_root in revoked_measurement_roots:
            reasons.append("measurement root was revoked")
        if not contract.accepts_age(candidate.receipt.event_end, now):
            reasons.append("offer expired by event_end TTL")
        if active and not _compatible_control_context(active, candidate):
            reasons.append("control context or event window is incompatible")

        relevant_observables = {
            observable
            for clause in contract.clauses
            if clause.name in lost
            for observable in clause.required_observables
        }
        missing = sorted(relevant_observables.difference(candidate.provided_observables))
        if missing:
            reasons.append(f"missing observables: {', '.join(missing)}")

        if reasons:
            rejections.append(CandidateRejection(candidate.offer_id, tuple(reasons)))
            continue

        augmented = (*active, candidate)
        after = evaluate_contract(contract, augmented, now)
        before_by_name = {
            assessment.clause: assessment for assessment in baseline.belief.clause_assessments
        }
        after_by_name = {
            assessment.clause: assessment for assessment in after.belief.clause_assessments
        }
        restored = tuple(
            name
            for name in lost
            if before_by_name[name].status is not ClauseStatus.SATISFIED
            and after_by_name[name].status is ClauseStatus.SATISFIED
        )
        root_gain = sum(
            max(
                0,
                len(set(after_by_name[name].measurement_roots))
                - len(set(before_by_name[name].measurement_roots)),
            )
            for name in lost
        )
        if root_gain == 0:
            rejections.append(
                CandidateRejection(
                    candidate.offer_id,
                    ("candidate adds no independent root toward a lost clause",),
                )
            )
            continue

        ttl = _remaining_ttl_s(contract, candidate.receipt.event_end, now)
        deficits = _transform_deficits(candidate.receipt.transforms)
        new_roots = int(candidate.measurement_root not in active_roots)
        shared_models = len(active_model_roots.intersection(candidate.receipt.model_roots))
        normalized_cost = candidate.request_count + candidate.bytes_received / 1_000_000.0
        value_per_cost = root_gain / max(normalized_cost, 1e-12)
        scores.append(
            CandidateScore(
                offer_id=candidate.offer_id,
                restored_clauses=restored,
                clause_root_gain=root_gain,
                remaining_ttl_s=ttl,
                new_measurement_roots=new_roots,
                shared_model_roots=shared_models,
                transform_deficits=deficits,
                value_per_cost=value_per_cost,
                request_count=candidate.request_count,
                bytes_received=candidate.bytes_received,
            )
        )

    scores.sort(key=CandidateScore.sort_key)
    selected_score = scores[0] if scores else None
    by_id = {offer.offer_id: offer for offer in candidates}
    selected = None if selected_score is None else by_id[selected_score.offer_id]
    rejections.sort(key=lambda item: item.offer_id)
    return ReplacementDecision(
        selected=selected,
        selected_score=selected_score,
        ranked_scores=tuple(scores),
        rejections=tuple(rejections),
    )


def failover_once(
    contract: DecisionContract,
    active_leases: Sequence[ObservationLease],
    candidates: Sequence[CapabilityOffer],
    primary_offer_id: str,
    now: datetime,
) -> FailoverResult:
    """Revoke one primary, attempt one replan, and stop after the first result."""

    now = _utc(now)
    active = tuple(lease.offer for lease in active_leases)
    primary = next((offer for offer in active if offer.offer_id == primary_offer_id), None)
    if primary is None:
        raise ValueError("primary_offer_id must name an active lease")

    before = evaluate_contract(contract, active, now)
    remaining = tuple(offer for offer in active if offer.offer_id != primary_offer_id)
    after_revocation = evaluate_contract(contract, remaining, now)
    before_status = {
        item.clause: item.status for item in before.belief.clause_assessments
    }
    after_status = {
        item.clause: item.status
        for item in after_revocation.belief.clause_assessments
    }
    lost = tuple(
        clause.name
        for clause in contract.clauses
        if before_status[clause.name] is ClauseStatus.SATISFIED
        and after_status[clause.name] is not ClauseStatus.SATISFIED
    )
    decision = select_replacement(
        contract,
        remaining,
        candidates,
        now,
        revoked_offer_ids=frozenset({primary_offer_id}),
        revoked_measurement_roots=frozenset({primary.measurement_root}),
        lost_clauses=lost,
    )
    lease = None
    final_offers = remaining
    if decision.selected is not None:
        lease = ObservationLease(
            lease_id=f"lease:{contract.clauses[0].name}:{decision.selected.offer_id}",
            offer=decision.selected,
            acquired_at=now,
        )
        final_offers = (*remaining, decision.selected)
    after_replacement = evaluate_contract(contract, final_offers, now)
    return FailoverResult(
        revoked_offer_id=primary_offer_id,
        lost_clauses=lost,
        before=before,
        after_revocation=after_revocation,
        decision=decision,
        replacement_lease=lease,
        after_replacement=after_replacement,
        model_snapshot=model_snapshot((*active, *candidates), now),
        candidates_considered=len(decision.ranked_scores) + len(decision.rejections),
        replacement_requests=0 if decision.selected is None else decision.selected.request_count,
        replacement_bytes=0 if decision.selected is None else decision.selected.bytes_received,
    )


def run_live_satnogs_failover(
    *,
    now: datetime | None = None,
    max_measurement_age_s: float = 600.0,
    max_pairs_to_try: int = 6,
    sink: Callable[[str], None] = print,
) -> LiveFailoverResult:
    """Use current SatNOGS data, revoke the preferred root, and stop at failover 1.

    At most ``max_pairs_to_try`` pairs are inspected.  Nothing is written to
    disk or retained after process exit.  A pair is control-compatible, not
    proof of emitter identity.
    """

    now = datetime.now(timezone.utc) if now is None else _utc(now)
    continuity = continuity_contract(max_measurement_age_s)
    corroboration = corroboration_contract(max_measurement_age_s)
    emit_jsonl("intent_received", continuity.intent, sink=sink)
    emit_jsonl("intent_received", corroboration.intent, sink=sink)
    emit_jsonl(
        "capability_probe",
        {"source": "satnogs", "ttl_s": max_measurement_age_s},
        sink=sink,
    )
    pairs = rank_fresh_pairs(fetch_recent_observations(now), corroboration, now)
    if not pairs:
        emit_jsonl(
            "belief_unobservable",
            {"reason": "no fresh two-station control-compatible SatNOGS pair"},
            sink=sink,
        )
        raise RuntimeError("no fresh two-station SatNOGS pair is available")

    cache: dict[int, CapabilityOffer] = {}
    selected_pair: tuple[CapabilityOffer, CapabilityOffer] | None = None
    for pair in pairs[:max_pairs_to_try]:
        offers: list[CapabilityOffer] = []
        for observation in pair:
            emit_jsonl(
                "capability_offer",
                {
                    "offer_id": f"satnogs:{observation.observation_id}",
                    "measurement_root": f"station:{observation.station_id}",
                    "event_end": observation.end,
                    "expires_at": observation.end
                    + timedelta(seconds=max_measurement_age_s),
                },
                sink=sink,
            )
            if observation.observation_id not in cache:
                try:
                    artifact = fetch_waterfall(observation)
                    cache[observation.observation_id] = atomic_offer_from_artifact(artifact)
                except (OSError, ValueError) as error:
                    emit_jsonl(
                        "capability_rejected",
                        {
                            "offer_id": f"satnogs:{observation.observation_id}",
                            "reason": str(error),
                        },
                        sink=sink,
                    )
                    continue
            offer = cache[observation.observation_id]
            emit_jsonl("evidence_received", offer.evidence, sink=sink)
            if RF_STRUCTURE not in offer.provided_observables:
                emit_jsonl(
                    "evidence_rejected",
                    {"offer_id": offer.offer_id, "reason": "no robust image-domain RF structure"},
                    sink=sink,
                )
                continue
            offers.append(offer)
        if len(offers) == 2:
            selected_pair = (offers[0], offers[1])
            break
    if selected_pair is None:
        emit_jsonl(
            "belief_unobservable",
            {"reason": "fresh pairs existed but two atomic structured artifacts were not accessible"},
            sink=sink,
        )
        raise RuntimeError("no accessible fresh pair contained two structured waterfalls")

    initial_choice = select_replacement(continuity, (), selected_pair, now)
    if initial_choice.selected is None:
        raise RuntimeError("no initial continuity offer satisfies the contract")
    primary = initial_choice.selected
    secondary = next(offer for offer in selected_pair if offer.offer_id != primary.offer_id)
    continuity_lease = ObservationLease(
        f"lease:measurement_continuity:{primary.offer_id}", primary, now
    )
    corroboration_leases = (
        ObservationLease(f"lease:measurement_corroboration:{primary.offer_id}", primary, now),
        ObservationLease(f"lease:measurement_corroboration:{secondary.offer_id}", secondary, now),
    )
    for lease in (continuity_lease, *corroboration_leases):
        emit_jsonl("lease_acquired", lease, sink=sink)
    emit_jsonl(
        "belief_updated",
        evaluate_contract(continuity, (primary,), now),
        sink=sink,
    )
    emit_jsonl(
        "belief_updated",
        evaluate_contract(corroboration, selected_pair, now),
        sink=sink,
    )

    emit_jsonl(
        "source_revoked",
        {"offer_id": primary.offer_id, "measurement_root": primary.measurement_root},
        sink=sink,
    )
    corroboration_after = evaluate_contract(corroboration, (secondary,), now)
    emit_jsonl("belief_unobservable", corroboration_after, sink=sink)
    emit_jsonl(
        "replan_started",
        {"contract": "measurement_continuity", "lost_clause": "measurement_continuity"},
        sink=sink,
    )
    started = perf_counter()
    result = failover_once(
        continuity,
        (continuity_lease,),
        selected_pair,
        primary.offer_id,
        now,
    )
    elapsed_s = perf_counter() - started
    for rejection in result.decision.rejections:
        emit_jsonl("capability_rejected", rejection, sink=sink)
    if result.replacement_lease is None:
        emit_jsonl("belief_unobservable", result.after_replacement, sink=sink)
    else:
        emit_jsonl(
            "replan_replaced",
            {
                "revoked_offer_id": primary.offer_id,
                "selected_offer_id": result.replacement_lease.offer.offer_id,
                "reason": result.decision.selected_score,
                "replacement_time_s": elapsed_s,
                "requests": result.replacement_requests,
                "bytes": result.replacement_bytes,
                "candidates_considered": result.candidates_considered,
            },
            sink=sink,
        )
        emit_jsonl("belief_updated", result.after_replacement, sink=sink)
    emit_jsonl("model_available", result.model_snapshot, sink=sink)

    expiry_now = max(offer.receipt.event_end for offer in selected_pair) + timedelta(
        seconds=max_measurement_age_s + 1.0
    )
    expired_continuity = evaluate_contract(continuity, selected_pair, expiry_now)
    expired_corroboration = evaluate_contract(corroboration, selected_pair, expiry_now)
    emit_jsonl(
        "all_measurements_expired",
        {
            "valid_at": expiry_now,
            "continuity": expired_continuity.belief.clause_assessments,
            "corroboration": expired_corroboration.belief.clause_assessments,
        },
        sink=sink,
    )
    emit_jsonl(
        "model_available",
        model_snapshot(selected_pair, expiry_now),
        sink=sink,
    )
    return LiveFailoverResult(
        continuity_contract=continuity,
        corroboration_contract=corroboration,
        continuity_failover=result,
        corroboration_after_revocation=corroboration_after,
    )


def _deduplicate_offers(offers: Iterable[CapabilityOffer]) -> list[CapabilityOffer]:
    by_id: dict[str, CapabilityOffer] = {}
    for offer in offers:
        existing = by_id.get(offer.offer_id)
        if existing is not None and existing != offer:
            raise ValueError(f"offer {offer.offer_id!r} was redefined")
        by_id[offer.offer_id] = offer
    return [by_id[key] for key in sorted(by_id)]


def _model_is_propagable(observation: SatnogsObservation) -> bool:
    try:
        compute_orbital_state(
            Observer(
                observation.station_lat,
                observation.station_lng,
                observation.station_alt_m,
            ),
            TLEElements(observation.tle1, observation.tle2),
            observation.end,
            observation.carrier_hz,
        )
    except (OrbitalKernelError, ValueError):
        return False
    return True


def _compatible_control_context(
    active: Sequence[CapabilityOffer], candidate: CapabilityOffer
) -> bool:
    if any(offer.control_context != candidate.control_context for offer in active):
        return False
    event_start = max(offer.receipt.event_start for offer in (*active, candidate))
    event_end = min(offer.receipt.event_end for offer in (*active, candidate))
    return event_end > event_start


def _select_compatible_support(
    offers: Sequence[CapabilityOffer],
) -> tuple[CapabilityOffer, ...]:
    """Choose the largest deterministic same-context interval intersection."""

    choices: list[tuple[CapabilityOffer, ...]] = []
    contexts = sorted({offer.control_context for offer in offers})
    for context in contexts:
        contextual = tuple(offer for offer in offers if offer.control_context == context)
        # Every maximal interval intersection contains at least one interval
        # start, so these pivots enumerate all relevant overlap cliques.
        for pivot in sorted({offer.receipt.event_start for offer in contextual}):
            covering = [
                offer
                for offer in contextual
                if offer.receipt.event_start <= pivot < offer.receipt.event_end
            ]
            by_root: dict[str, CapabilityOffer] = {}
            for offer in sorted(
                covering,
                key=lambda item: (-item.receipt.event_end.timestamp(), item.offer_id),
            ):
                by_root.setdefault(offer.measurement_root, offer)
            if by_root:
                choices.append(tuple(by_root[root] for root in sorted(by_root)))
    if not choices:
        return ()
    choices.sort(
        key=lambda group: (
            -len(group),
            -min(offer.receipt.event_end.timestamp() for offer in group),
            tuple(offer.offer_id for offer in group),
        )
    )
    return choices[0]


def _remaining_ttl_s(
    contract: DecisionContract, event_end: datetime, now: datetime
) -> float | None:
    if contract.max_measurement_age_s is None:
        return None
    expires_at = _utc(event_end) + timedelta(seconds=contract.max_measurement_age_s)
    return max(0.0, (expires_at - _utc(now)).total_seconds())


def _transform_deficits(transforms: Sequence[Transform]) -> TransformDeficits:
    states = tuple(transform.state.lower() for transform in transforms)
    return TransformDeficits(
        unknown=sum("unknown" in state for state in states),
        partial=sum("partial" in state for state in states),
        model_conditioned=sum("conditioned" in state for state in states),
        lossy=sum("lossy" in state for state in states),
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def main() -> None:
    run_live_satnogs_failover()


if __name__ == "__main__":
    main()
