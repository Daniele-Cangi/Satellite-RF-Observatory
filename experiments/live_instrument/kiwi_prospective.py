"""One prospective targetless Kiwi experiment after Checkpoint 3 discovery.

This is deliberately a single experiment, not a source framework.  Checkpoint
3 is frozen as discovery.  The band audit, model reveal, prediction and all
controls are emitted before a new dual-receiver window is opened.  The process
stops after its first confirmation outcome and never stores IQ samples.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Callable

import numpy as np

from . import kiwi_probe as kiwi
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
    Transform,
    emit_jsonl,
)


@dataclass(frozen=True, slots=True)
class DiscoveryRecord:
    checkpoint_commit: str
    scout_plan_hash: str
    candidate_centers_hz: tuple[float, ...]
    candidate_scores: tuple[float, ...]
    selected_center_hz: float
    selected_frequency_low_hz: float
    selected_frequency_high_hz: float
    selected_duration_s: float
    discovery_event_end: datetime
    artifact_hashes: tuple[str, str]

    @property
    def record_hash(self) -> str:
        payload = json.dumps(
            _jsonable(asdict(self)), sort_keys=True, separators=(",", ":")
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BandSelectionAudit:
    discovery_record_hash: str
    center_search_repeated_inside_checkpoint_3_null: bool
    within_band_search_repeated_inside_checkpoint_3_null: bool
    center_scout_and_checkpoint_3_comparison_used_distinct_windows: bool
    prospective_confirmation_band_fixed_before_samples: bool
    conclusion: str
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProspectivePlan:
    discovery_record_hash: str
    center_frequency_hz: float
    target_frequency_low_hz: float
    target_frequency_high_hz: float
    confirmation_duration_s: float = 12.0
    nperseg: int = 512
    noverlap: int = 384
    positive_threshold: float = 2.0
    negative_threshold: float = 0.5
    state_frames: int = 3
    maximum_transition_separation_s: float = 2.0
    frequency_control_offsets_hz: tuple[float, ...] = (
        -1_500.0,
        -750.0,
        750.0,
        1_500.0,
    )
    time_control_shifts_frames: tuple[int, ...] = (-192, -128, -64, 64, 128, 192)
    minimum_overlap_s: float = 8.0
    maximum_measurement_age_s: float = 30.0

    def __post_init__(self) -> None:
        if not self.discovery_record_hash:
            raise ValueError("a prospective plan must bind one frozen discovery")
        if not self.target_frequency_low_hz < self.target_frequency_high_hz:
            raise ValueError("target frequency interval must be ordered")
        half_sample_band_hz = 6_000.0
        if (
            self.target_frequency_low_hz
            < self.center_frequency_hz - half_sample_band_hz
            or self.target_frequency_high_hz
            > self.center_frequency_hz + half_sample_band_hz
        ):
            raise ValueError("target interval falls outside the prospective IQ passband")
        if not self.negative_threshold < self.positive_threshold:
            raise ValueError("negative threshold must be below positive threshold")
        if self.state_frames < 2 or self.maximum_transition_separation_s <= 0:
            raise ValueError("transition geometry must be positive")
        if not self.frequency_control_offsets_hz or 0.0 in self.frequency_control_offsets_hz:
            raise ValueError("frequency controls must be predeclared and non-zero")
        if not self.time_control_shifts_frames or 0 in self.time_control_shifts_frames:
            raise ValueError("time controls must be predeclared and non-zero")

    @property
    def plan_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelReveal:
    revealed_at: datetime
    plan_hash: str
    state_variable: str
    positive_state: str
    negative_state: str
    transition_order: tuple[str, str]
    controls: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProspectivePrediction:
    registered_at: datetime
    plan_hash: str
    statement: str
    positive_transition_required: bool
    subsequent_negative_transition_required: bool
    controls_must_remain_below_target: bool


@dataclass(frozen=True, slots=True)
class Transition:
    kind: str
    event_time: datetime
    before_level: float
    after_level: float
    magnitude: float


@dataclass(frozen=True, slots=True)
class TransitionPair:
    positive: Transition | None
    negative: Transition | None
    score: float


@dataclass(frozen=True, slots=True)
class ProspectiveResult:
    discovery: DiscoveryRecord
    band_audit: BandSelectionAudit
    model_reveal: ModelReveal
    prediction: ProspectivePrediction
    target_pair: TransitionPair
    frequency_control_scores: tuple[tuple[float, float], ...]
    time_control_scores: tuple[tuple[int, float], ...]
    controls_passed: bool
    evidence: EvidenceEvent
    belief: BeliefSnapshot


def checkpoint_3_discovery() -> DiscoveryRecord:
    """Return only the immutable, non-IQ facts frozen at Checkpoint 3."""

    return DiscoveryRecord(
        checkpoint_commit="90d345b",
        scout_plan_hash="d69c40dfdd761221b6b93ff65c4012d839d763f354cb110bd8a944a5880ea7d2",
        candidate_centers_hz=(5_000_000.0, 10_000_000.0, 15_000_000.0),
        candidate_scores=(2.500652, 0.739011, 0.872034),
        selected_center_hz=5_000_000.0,
        selected_frequency_low_hz=4_995_887.109997,
        selected_frequency_high_hz=4_996_051.158748,
        selected_duration_s=0.085341,
        discovery_event_end=datetime.fromisoformat(
            "2026-08-15T23:48:49.708322+00:00"
        ),
        artifact_hashes=(
            "8f0c8bf60064893a4eb38f3ee79f07408bda8efd8dbf049f459a808355ebffeb",
            "fda12b94de2d4795a7dde259e7ea8142ddb15747c5e96f4c2b6a4d5aa4cfe2dc",
        ),
    )


def audit_checkpoint_3_band_selection(
    discovery: DiscoveryRecord,
) -> BandSelectionAudit:
    """State exactly which look-elsewhere choices the CP3 null did cover."""

    return BandSelectionAudit(
        discovery_record_hash=discovery.record_hash,
        center_search_repeated_inside_checkpoint_3_null=False,
        within_band_search_repeated_inside_checkpoint_3_null=True,
        center_scout_and_checkpoint_3_comparison_used_distinct_windows=True,
        prospective_confirmation_band_fixed_before_samples=True,
        conclusion=(
            "Checkpoint 3 p-values are conditional on the selected 5 MHz acquisition "
            "band: their max-stat null repeated the within-band region search, not the "
            "earlier 5/10/15 MHz center choice. The prospective confirmation removes "
            "that center look-elsewhere choice by freezing the band before new samples."
        ),
        limitations=(
            "the CP3 center grid had only three predeclared candidates",
            "the CP3 p=0.01 resolution came from 99 shifts per null family",
            "independent confirmation tests recurrence, not transmitter identity",
        ),
    )


def default_prospective_plan(discovery: DiscoveryRecord) -> ProspectivePlan:
    return ProspectivePlan(
        discovery_record_hash=discovery.record_hash,
        center_frequency_hz=discovery.selected_center_hz,
        target_frequency_low_hz=discovery.selected_frequency_low_hz,
        target_frequency_high_hz=discovery.selected_frequency_high_hz,
    )


def prospective_contract(plan: ProspectivePlan) -> DecisionContract:
    return DecisionContract(
        Intent(
            "Does the frozen targetless RF morphology recur prospectively in two receivers?",
            target=None,
        ),
        (
            DecisionClause(
                "measurement_availability",
                "one fresh continuous dual-Kiwi confirmation window",
                ("dual_station_iq", "gnss_event_time"),
                2,
            ),
            DecisionClause(
                "positive_transition",
                "both stations move from the frozen low state to the frozen high state",
                ("positive_transition",),
                2,
            ),
            DecisionClause(
                "negative_transition",
                "both stations subsequently return from high to low",
                ("negative_transition",),
                2,
            ),
            DecisionClause(
                "prospective_confirmation",
                "the ordered pair exceeds every predeclared control",
                ("transition_pair", "controls"),
                2,
            ),
            DecisionClause(
                "common_physical_cause",
                "one physical cause after HF propagation ambiguities",
                ("causal_support",),
                2,
            ),
        ),
        plan.maximum_measurement_age_s,
    )


def reveal_model(plan: ProspectivePlan, revealed_at: datetime) -> ModelReveal:
    return ModelReveal(
        _utc(revealed_at),
        plan.plan_hash,
        "minimum of the two station-normalized fixed-band salience states",
        (
            f"both stations >= {plan.positive_threshold} for "
            f"{plan.state_frames} frames"
        ),
        (
            f"both stations <= {plan.negative_threshold} for "
            f"{plan.state_frames} frames"
        ),
        ("positive", "subsequent_negative"),
        (
            f"frequency offsets {plan.frequency_control_offsets_hz} Hz",
            f"right-stream frame shifts {plan.time_control_shifts_frames}",
        ),
    )


def register_prediction(
    plan: ProspectivePlan,
    registered_at: datetime,
) -> ProspectivePrediction:
    return ProspectivePrediction(
        _utc(registered_at),
        plan.plan_hash,
        (
            "In the next independent window, the frozen band will show at least one "
            "two-station low-to-high transition followed by high-to-low, and its pair "
            "score will exceed all fixed wrong-frequency and wrong-time controls."
        ),
        True,
        True,
        True,
    )


def evaluate_confirmation(
    discovery: DiscoveryRecord,
    band_audit: BandSelectionAudit,
    plan: ProspectivePlan,
    model_reveal: ModelReveal,
    prediction: ProspectivePrediction,
    left: kiwi.KiwiCapture,
    right: kiwi.KiwiCapture,
    now: datetime,
) -> ProspectiveResult:
    """Evaluate exactly one post-registration window under the frozen plan."""

    if plan.discovery_record_hash != discovery.record_hash:
        raise ValueError("prospective plan is not bound to the frozen discovery")
    if model_reveal.plan_hash != plan.plan_hash or prediction.plan_hash != plan.plan_hash:
        raise ValueError("model and prediction must use the immutable plan hash")
    now = _utc(now)
    audit_plan = kiwi.ScoutPlan(
        center_frequencies_hz=(plan.center_frequency_hz,),
        scout_duration_s=plan.confirmation_duration_s,
        nperseg=plan.nperseg,
        noverlap=plan.noverlap,
        min_overlap_s=plan.minimum_overlap_s,
    )
    audits = (kiwi.audit_capture(left, audit_plan), kiwi.audit_capture(right, audit_plan))
    event_start = max(left.event_start, right.event_start)
    event_end = min(left.event_end, right.event_end)
    independent_window = (
        event_start > discovery.discovery_event_end
        and event_start > prediction.registered_at
    )
    contract = prospective_contract(plan)
    measurement_available = (
        all(audit.usable for audit in audits)
        and independent_window
        and (event_end - event_start).total_seconds() >= plan.minimum_overlap_s
        and contract.accepts_age(event_end, now)
        and abs(left.center_frequency_hz - plan.center_frequency_hz) <= 0.5
        and abs(right.center_frequency_hz - plan.center_frequency_hz) <= 0.5
    )

    target_pair = TransitionPair(None, None, 0.0)
    frequency_controls: tuple[tuple[float, float], ...] = ()
    time_controls: tuple[tuple[int, float], ...] = ()
    controls_passed = False
    analysis_failure: str | None = None
    if measurement_available:
        try:
            (
                left_dynamic,
                right_dynamic,
                frequencies_hz,
                event_times_s,
                _time_step_s,
                _frequency_step_hz,
            ) = kiwi._common_spectral_grids(left, right, audits, audit_plan)
            left_target, right_target = _band_series(
                left_dynamic,
                right_dynamic,
                frequencies_hz,
                plan.target_frequency_low_hz,
                plan.target_frequency_high_hz,
            )
            target_pair = _find_transition_pair(
                left_target, right_target, event_times_s, plan
            )
            frequency_controls = tuple(
                (
                    offset,
                    _find_transition_pair(
                        *_band_series(
                            left_dynamic,
                            right_dynamic,
                            frequencies_hz,
                            plan.target_frequency_low_hz + offset,
                            plan.target_frequency_high_hz + offset,
                        ),
                        event_times_s,
                        plan,
                    ).score,
                )
                for offset in plan.frequency_control_offsets_hz
            )
            time_controls = tuple(
                (
                    shift,
                    _find_transition_pair(
                        left_target,
                        _shift_without_wrap(right_target, shift),
                        event_times_s,
                        plan,
                    ).score,
                )
                for shift in plan.time_control_shifts_frames
            )
            control_max = max(
                (score for _control, score in (*frequency_controls, *time_controls)),
                default=0.0,
            )
            controls_passed = (
                target_pair.positive is not None
                and target_pair.negative is not None
                and target_pair.score > control_max
            )
        except ValueError as error:
            analysis_failure = str(error)
            measurement_available = False

    measurement_roots = (f"kiwi:{left.endpoint.name}", f"kiwi:{right.endpoint.name}")
    model_roots = (
        "kiwi:shared-hardware-protocol-ddc",
        f"probe-b:prospective-plan:{plan.plan_hash[:16]}",
        f"probe-b:discovery:{discovery.record_hash[:16]}",
    )
    receipt = ConstraintReceipt(
        branch="dual-kiwi-prospective",
        event_start=event_start,
        event_end=event_end,
        constraints=(
            Constraint("independent_confirmation_window", "==", independent_window, None, "event time must follow both discovery and prediction registration", "GNSS event time"),
            Constraint("immutable_plan", "sha256", plan.plan_hash, None, "any parameter change is a different experiment", "serialized ProspectivePlan"),
            Constraint("band_selection_audit", "recorded", band_audit, None, "CP3 center selection was not inside its shift null", "frozen Checkpoint 3 facts"),
            Constraint("positive_transition", "required", target_pair.positive, None, "fixed thresholds and frame count", "fixed target band"),
            Constraint("subsequent_negative_transition", "required", target_pair.negative, None, "must follow the positive transition", "fixed target band"),
            Constraint("target_transition_pair_score", ">controls", target_pair.score, None, "first qualifying ordered pair; no threshold tuning", "minimum onset/offset contrast"),
            Constraint("frequency_controls", "predeclared", frequency_controls, None, "same transition detector in wrong bands", "fixed offsets from target band"),
            Constraint("time_controls", "predeclared", time_controls, None, "right stream shifted without wrap", "fixed frame shifts"),
            Constraint("controls_passed", "==", controls_passed, None, "target must exceed every control", "frozen prospective rule"),
            Constraint("analysis_failure", "is_none", analysis_failure, None, "no recovery by changing the plan", "confirmation evaluator"),
        ),
        transforms=(
            Transform("kiwi_rf_chain", "partial", "independent front-ends use common Kiwi ADC/DDC design"),
            Transform("gnss_continuity_audit", "known", "gaps and overflow split the stream before comparison"),
            Transform("fixed_band_stft", "known_lossy", "phase discarded; band fixed before confirmation", model_roots[1:]),
            Transform("prospective_transition_controls", "known", "one detector applied to target and every predeclared control", model_roots[1:]),
        ),
        measurement_roots=measurement_roots,
        model_roots=model_roots,
        artifact_hashes=(kiwi._capture_hash(left), kiwi._capture_hash(right)),
        caveats=(
            "confirmation is conditional on one station pair and one frozen RF band",
            "HF propagation and common interference can preserve recurrence without one emitter",
            "no identity, TDoA, phase comparison or propagation correction is attempted",
        ),
    )
    evidence = EvidenceEvent(
        "dual-kiwi-prospective-iq",
        max(left.arrived_end, right.arrived_end),
        receipt,
    )
    positive_found = measurement_available and target_pair.positive is not None
    negative_found = measurement_available and target_pair.negative is not None
    belief = contract.snapshot_from_evidence(
        receipt,
        valid_at=now,
        clause_assessments=(
            _assessment(
                "measurement_availability",
                ClauseStatus.SATISFIED if measurement_available else ClauseStatus.UNOBSERVABLE,
                "A fresh post-registration dual-Kiwi window is available." if measurement_available else "The prospective confirmation window is not usable.",
                measurement_roots if measurement_available else (),
            ),
            _assessment(
                "positive_transition",
                ClauseStatus.SATISFIED if positive_found else (ClauseStatus.UNSATISFIED if measurement_available else ClauseStatus.UNOBSERVABLE),
                "The frozen low-to-high transition was observed." if positive_found else "The frozen low-to-high transition was not observed.",
                measurement_roots if measurement_available else (),
            ),
            _assessment(
                "negative_transition",
                ClauseStatus.SATISFIED if negative_found else (ClauseStatus.UNSATISFIED if measurement_available else ClauseStatus.UNOBSERVABLE),
                "A frozen high-to-low transition followed the onset." if negative_found else "No qualifying high-to-low transition followed the onset.",
                measurement_roots if measurement_available else (),
            ),
            _assessment(
                "prospective_confirmation",
                ClauseStatus.SATISFIED if controls_passed else (ClauseStatus.UNSATISFIED if measurement_available else ClauseStatus.UNOBSERVABLE),
                "The ordered transition pair exceeded every predeclared control." if controls_passed else "The prospective prediction was not confirmed under all frozen controls.",
                measurement_roots if measurement_available else (),
            ),
            _assessment(
                "common_physical_cause",
                ClauseStatus.UNRESOLVED if measurement_available else ClauseStatus.UNOBSERVABLE,
                "Prospective recurrence does not by itself resolve a common physical cause.",
                measurement_roots if measurement_available else (),
            ),
        ),
        uncertainty=receipt.caveats,
        active_model_roots=model_roots,
    )
    return ProspectiveResult(
        discovery,
        band_audit,
        model_reveal,
        prediction,
        target_pair,
        frequency_controls,
        time_controls,
        controls_passed,
        evidence,
        belief,
    )


def run_first_prospective_outcome(
    *,
    endpoints: tuple[kiwi.KiwiEndpoint, kiwi.KiwiEndpoint] = (
        kiwi.KiwiEndpoint("hooksiel", "dl1bajkiwisdr.ddns.net", 8074),
        kiwi.KiwiEndpoint("doncaster", "g0ghk.uk", 8050),
    ),
    sink: Callable[[str], None] = print,
) -> ProspectiveResult:
    """Reveal, register, open one new window, emit one outcome, then stop."""

    discovery = checkpoint_3_discovery()
    band_audit = audit_checkpoint_3_band_selection(discovery)
    plan = default_prospective_plan(discovery)
    revealed_at = datetime.now(timezone.utc)
    model_reveal = reveal_model(plan, revealed_at)
    prediction = register_prediction(plan, datetime.now(timezone.utc))
    emit_jsonl("discovery_frozen", discovery, sink=sink)
    emit_jsonl("band_selection_audited", band_audit, sink=sink)
    emit_jsonl("model_revealed", model_reveal, sink=sink)
    emit_jsonl("prediction_registered", prediction, sink=sink)
    captures = kiwi.capture_dual_kiwi(
        endpoints,
        center_frequency_hz=plan.center_frequency_hz,
        duration_s=plan.confirmation_duration_s,
        max_gps_solution_age_s=30,
    )
    result = evaluate_confirmation(
        discovery,
        band_audit,
        plan,
        model_reveal,
        prediction,
        captures[0],
        captures[1],
        datetime.now(timezone.utc),
    )
    emit_jsonl("confirmation_evidence", result.evidence.receipt, sink=sink)
    emit_jsonl("first_prospective_outcome", result.belief, sink=sink)
    return result


def _band_series(
    left: np.ndarray,
    right: np.ndarray,
    frequencies_hz: np.ndarray,
    low_hz: float,
    high_hz: float,
) -> tuple[np.ndarray, np.ndarray]:
    mask = (frequencies_hz >= low_hz) & (frequencies_hz <= high_hz)
    if np.count_nonzero(mask) < 2:
        raise ValueError(f"control band {low_hz}..{high_hz} Hz has fewer than two bins")
    return np.mean(left[mask], axis=0), np.mean(right[mask], axis=0)


def _find_transition_pair(
    left: np.ndarray,
    right: np.ndarray,
    event_times_s: np.ndarray,
    plan: ProspectivePlan,
) -> TransitionPair:
    frames = plan.state_frames
    if len(left) != len(right) or len(left) != len(event_times_s):
        raise ValueError("transition series must share one event-time grid")
    positive: Transition | None = None
    positive_index: int | None = None
    for index in range(frames, len(left) - frames + 1):
        before_left = left[index - frames:index]
        before_right = right[index - frames:index]
        after_left = left[index:index + frames]
        after_right = right[index:index + frames]
        before_level = float(max(np.mean(before_left), np.mean(before_right)))
        after_level = float(min(np.mean(after_left), np.mean(after_right)))
        if before_level <= plan.negative_threshold and after_level >= plan.positive_threshold:
            positive = Transition(
                "positive",
                datetime.fromtimestamp(event_times_s[index], tz=timezone.utc),
                before_level,
                after_level,
                after_level - before_level,
            )
            positive_index = index
            break
    if positive is None or positive_index is None:
        return TransitionPair(None, None, 0.0)

    negative: Transition | None = None
    maximum_frames = max(
        frames,
        int(
            round(
                plan.maximum_transition_separation_s
                / max(float(np.median(np.diff(event_times_s))), 1e-9)
            )
        ),
    )
    stop = min(len(left) - frames + 1, positive_index + maximum_frames)
    for index in range(positive_index + frames, stop):
        before_level = float(
            min(
                np.mean(left[index - frames:index]),
                np.mean(right[index - frames:index]),
            )
        )
        after_level = float(
            max(
                np.mean(left[index:index + frames]),
                np.mean(right[index:index + frames]),
            )
        )
        if before_level >= plan.positive_threshold and after_level <= plan.negative_threshold:
            negative = Transition(
                "negative",
                datetime.fromtimestamp(event_times_s[index], tz=timezone.utc),
                before_level,
                after_level,
                before_level - after_level,
            )
            break
    if negative is None:
        return TransitionPair(positive, None, 0.0)
    return TransitionPair(positive, negative, min(positive.magnitude, negative.magnitude))


def _shift_without_wrap(values: np.ndarray, shift: int) -> np.ndarray:
    shifted = np.full(values.shape, np.nan, dtype=float)
    if shift > 0:
        shifted[shift:] = values[:-shift]
    else:
        shifted[:shift] = values[-shift:]
    return shifted


def _assessment(
    clause: str,
    status: ClauseStatus,
    statement: str,
    roots: tuple[str, ...],
) -> ClauseAssessment:
    return ClauseAssessment(clause, status, statement, roots)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _jsonable(value):
    if isinstance(value, datetime):
        return _utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def main() -> None:
    run_first_prospective_outcome()


if __name__ == "__main__":
    main()
