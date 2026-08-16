"""Gate E: one prospective WWV/WWVH absence experiment, entirely in RAM.

This is deliberately not a receiver framework.  A short capability scout ranks
real Kiwi offers by the causal cuts they close.  One selected receiver then
stays connected and unchanged across minute 28 (positive control), minutes
29--30 (scheduled standard-tone silence), and minute 31 (recovery control).
The final plan is frozen inside that stream, before the target window opens.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
import math
from threading import Event
import time
from typing import Callable, Iterable
from urllib.parse import unquote

import numpy as np
from scipy import signal

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


WWV = "WWV"
WWVH = "WWVH"


class GateEOutcomeKind(str, Enum):
    FALSIFIABILITY_NOT_ENTERED = "FALSIFIABILITY_NOT_ENTERED"
    NOT_DETECTABLE = "NOT_DETECTABLE"
    NOT_DETECTED = "NOT_DETECTED"
    OBSERVATIONAL_PREDICTION_FALSIFIED = "OBSERVATIONAL_PREDICTION_FALSIFIED"
    RECEIPT_INVALIDATED = "RECEIPT_INVALIDATED"


@dataclass(frozen=True, slots=True)
class GateEMotherPlan:
    """Method frozen before discovery; no values are tuned after an outcome."""

    candidate_frequencies_hz: tuple[float, ...] = (
        5_000_000.0,
        10_000_000.0,
        15_000_000.0,
    )
    offer_ttl_s: float = 600.0
    scout_duration_s: float = 4.5
    scout_min_overlap_s: float = 3.0
    nperseg: int = 1024
    noverlap: int = 768
    maximum_gps_solution_age_s: int = 30
    minimum_tick_contrast_db: float = 4.0
    minimum_generic_path_contrast_db: float = 3.0
    minimum_tone_presence_contrast_db: float = 6.0
    maximum_tone_absence_contrast_db: float = 3.0
    maximum_witness_drop_db: float = 9.0
    maximum_recovery_drop_db: float = 6.0
    pre_window_seconds: tuple[float, float] = (3.0, 42.0)
    target_window_seconds: tuple[float, float] = (3.0, 42.0)
    post_window_seconds: tuple[float, float] = (3.0, 42.0)

    def __post_init__(self) -> None:
        if not self.candidate_frequencies_hz or any(
            value <= 0 for value in self.candidate_frequencies_hz
        ):
            raise ValueError("Gate E needs positive candidate frequencies")
        if self.offer_ttl_s <= 0 or self.scout_duration_s <= 0:
            raise ValueError("Gate E durations and TTL must be positive")
        if not 0 <= self.noverlap < self.nperseg:
            raise ValueError("invalid Gate E STFT geometry")
        if not self.maximum_tone_absence_contrast_db < self.minimum_tone_presence_contrast_db:
            raise ValueError("absence threshold must remain below presence threshold")

    @property
    def plan_hash(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class GateESchedule:
    hour_start: datetime
    stream_start: datetime
    pre_start: datetime
    pre_end: datetime
    target_start: datetime
    target_end: datetime
    post_start: datetime
    post_end: datetime

    @classmethod
    def for_hour(cls, hour_start: datetime, mother: GateEMotherPlan) -> "GateESchedule":
        hour_start = _utc(hour_start).replace(minute=0, second=0, microsecond=0)
        pre_low, pre_high = mother.pre_window_seconds
        target_low, target_high = mother.target_window_seconds
        post_low, post_high = mother.post_window_seconds
        return cls(
            hour_start,
            hour_start + timedelta(minutes=27, seconds=55),
            hour_start + timedelta(minutes=28, seconds=pre_low),
            hour_start + timedelta(minutes=28, seconds=pre_high),
            hour_start + timedelta(minutes=29, seconds=target_low),
            hour_start + timedelta(minutes=30, seconds=target_high),
            hour_start + timedelta(minutes=31, seconds=post_low),
            hour_start + timedelta(minutes=31, seconds=post_high),
        )


@dataclass(frozen=True, slots=True)
class SegmentMetrics:
    event_start: datetime
    event_end: datetime
    tone_500_contrast_db: float
    tone_600_contrast_db: float
    wwv_tick_contrast_db: float
    wwvh_tick_contrast_db: float
    carrier_contrast_db: float
    timecode_contrast_db: float

    def tone(self, frequency_hz: int) -> float:
        if frequency_hz == 500:
            return self.tone_500_contrast_db
        if frequency_hz == 600:
            return self.tone_600_contrast_db
        raise KeyError(frequency_hz)

    def tick(self, station: str) -> float:
        if station == WWV:
            return self.wwv_tick_contrast_db
        if station == WWVH:
            return self.wwvh_tick_contrast_db
        raise KeyError(station)


@dataclass(frozen=True, slots=True)
class GateECapabilityOffer:
    offer_id: str
    endpoint: kiwi.KiwiEndpoint
    center_frequency_hz: float
    verified_at: datetime
    expires_at: datetime
    stations_supported: tuple[str, ...]
    metrics: SegmentMetrics
    audit: kiwi.CaptureAudit
    same_path_witness: bool
    causal_cuts_closed: tuple[str, ...]
    robust_margin_db: float
    information_gain_proxy: float
    artifact_hash: str

    @property
    def falsification_rank(self) -> tuple[float, ...]:
        """Lexicographic: causal usability precedes generic signal richness."""

        return (
            float(self.audit.usable),
            float(self.same_path_witness),
            float(len(self.causal_cuts_closed)),
            self.robust_margin_db,
            float(bool(self.stations_supported)),
            self.expires_at.timestamp(),
            self.audit.overlap_ready_duration_s,
            self.information_gain_proxy,
            -self.center_frequency_hz,
        )


@dataclass(frozen=True, slots=True)
class GateEFrozenPlan:
    mother_plan_hash: str
    offer_id: str
    endpoint: kiwi.KiwiEndpoint
    center_frequency_hz: float
    stations_supported: tuple[str, ...]
    schedule: GateESchedule
    frozen_at: datetime
    tone_presence_min_db: float
    tone_absence_max_db: float
    tick_minima_db: tuple[tuple[str, float], ...]
    carrier_minimum_db: float
    timecode_minimum_db: float
    post_tone_minima_db: tuple[tuple[str, float], ...]
    pre_metrics: SegmentMetrics

    @property
    def plan_hash(self) -> str:
        return _hash(asdict(self))

    def tick_minimum(self, station: str) -> float:
        return dict(self.tick_minima_db)[station]

    def post_tone_minimum(self, station: str) -> float:
        return dict(self.post_tone_minima_db)[station]


@dataclass(frozen=True, slots=True)
class GateEOutcome:
    kind: GateEOutcomeKind
    mother_plan_hash: str
    selected_offer: GateECapabilityOffer | None
    frozen_plan: GateEFrozenPlan | None
    pre_metrics: SegmentMetrics | None
    target_metrics: SegmentMetrics | None
    post_metrics: SegmentMetrics | None
    evidence: EvidenceEvent
    belief: BeliefSnapshot


def gate_e_contract() -> DecisionContract:
    clauses = tuple(
        DecisionClause(name, requirement, (name,), 1)
        for name, requirement in (
            ("station_identity_supported", "station-specific 1000/1200 Hz markers identify the received path"),
            ("path_alive_before", "station-specific and generic witnesses are alive before the silence"),
            ("positive_control_before", "the station-specific minute-28 standard tone is present"),
            ("path_alive_during_target_window", "the same station-specific path remains alive in minutes 29-30"),
            ("standard_tone_absent", "500/600 Hz standard tones are absent in minutes 29-30"),
            ("positive_control_after", "the station-specific minute-31 standard tone returns"),
            ("receiver_health_continuous", "one unchanged GNSS-continuous receiver covers the frozen window"),
            ("negative_interpretable", "the scheduled absence is bracketed by same-path witnesses and controls"),
        )
    )
    return DecisionContract(
        Intent(
            "Do the WWV/WWVH standard tones disappear on schedule while the same source paths remain observable?",
            target="WWV/WWVH scheduled modulation",
        ),
        clauses,
        max_measurement_age_s=30.0,
    )


def offer_from_capture(
    mother: GateEMotherPlan,
    capture: kiwi.KiwiCapture,
    now: datetime,
) -> GateECapabilityOffer:
    now = _utc(now)
    audit_plan = kiwi.ScoutPlan(
        center_frequencies_hz=(capture.center_frequency_hz,),
        scout_duration_s=mother.scout_duration_s,
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        min_overlap_s=mother.scout_min_overlap_s,
        max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
    )
    audit = kiwi.audit_capture(capture, audit_plan)
    if audit.blocks:
        metrics = measure_segment(
            capture,
            audit,
            audit.blocks[0].event_start,
            audit.blocks[-1].event_end,
        )
    else:
        metrics = _empty_metrics(capture.arrived_start, capture.arrived_end)
    stations = tuple(
        station
        for station in (WWV, WWVH)
        if metrics.tick(station) >= mother.minimum_tick_contrast_db
    )
    cuts: list[str] = []
    if stations:
        cuts.append("station_specific_marker")
    if metrics.carrier_contrast_db >= mother.minimum_generic_path_contrast_db:
        cuts.append("carrier_path")
    if metrics.timecode_contrast_db >= mother.minimum_generic_path_contrast_db:
        cuts.append("timecode_path")
    margins = [
        metrics.tick(station) - mother.minimum_tick_contrast_db
        for station in stations
    ]
    if "carrier_path" in cuts:
        margins.append(metrics.carrier_contrast_db - mother.minimum_generic_path_contrast_db)
    if "timecode_path" in cuts:
        margins.append(metrics.timecode_contrast_db - mother.minimum_generic_path_contrast_db)
    robust_margin = min(margins) if margins else -math.inf
    same_path = audit.usable and bool(stations)
    offer_id = (
        f"kiwi:{capture.endpoint.name}:{capture.center_frequency_hz:.0f}:"
        f"{kiwi._capture_hash(capture)[:12]}"
    )
    return GateECapabilityOffer(
        offer_id,
        capture.endpoint,
        capture.center_frequency_hz,
        now,
        now + timedelta(seconds=mother.offer_ttl_s),
        stations,
        metrics,
        audit,
        same_path,
        tuple(cuts),
        robust_margin,
        max(
            metrics.tone_500_contrast_db,
            metrics.tone_600_contrast_db,
            metrics.wwv_tick_contrast_db,
            metrics.wwvh_tick_contrast_db,
        ),
        kiwi._capture_hash(capture),
    )


def select_capability_offer(
    offers: Iterable[GateECapabilityOffer],
    *,
    now: datetime,
    required_until: datetime,
) -> GateECapabilityOffer | None:
    now = _utc(now)
    required_until = _utc(required_until)
    eligible = [
        offer
        for offer in offers
        if offer.verified_at <= now
        and offer.expires_at >= required_until
        and offer.audit.usable
        and offer.same_path_witness
        and "station_specific_marker" in offer.causal_cuts_closed
    ]
    return max(eligible, key=lambda offer: (offer.falsification_rank, offer.offer_id), default=None)


def freeze_plan_after_positive_control(
    mother: GateEMotherPlan,
    offer: GateECapabilityOffer,
    schedule: GateESchedule,
    pre: SegmentMetrics,
    frozen_at: datetime,
) -> GateEFrozenPlan:
    frozen_at = _utc(frozen_at)
    if frozen_at >= schedule.target_start:
        raise ValueError("the Gate E plan was not frozen before the target window")
    stations = tuple(
        station
        for station in offer.stations_supported
        if pre.tick(station) >= mother.minimum_tick_contrast_db
    )
    if not stations:
        raise ValueError("station identity is not supported in the positive-control stream")
    for station in stations:
        expected = _standard_tone(station, minute=28)
        if pre.tone(expected) < mother.minimum_tone_presence_contrast_db:
            raise ValueError(
                f"minute-28 positive control for {station} at {expected} Hz is absent"
            )
    if pre.carrier_contrast_db < mother.minimum_generic_path_contrast_db:
        raise ValueError("carrier witness is absent before the target window")
    if pre.timecode_contrast_db < mother.minimum_generic_path_contrast_db:
        raise ValueError("time-code witness is absent before the target window")
    tick_minima = tuple(
        (
            station,
            max(
                mother.minimum_tick_contrast_db,
                pre.tick(station) - mother.maximum_witness_drop_db,
            ),
        )
        for station in stations
    )
    post_minima = tuple(
        (
            station,
            max(
                mother.minimum_tone_presence_contrast_db,
                pre.tone(_standard_tone(station, minute=28))
                - mother.maximum_recovery_drop_db,
            ),
        )
        for station in stations
    )
    return GateEFrozenPlan(
        mother.plan_hash,
        offer.offer_id,
        offer.endpoint,
        offer.center_frequency_hz,
        stations,
        schedule,
        frozen_at,
        mother.minimum_tone_presence_contrast_db,
        mother.maximum_tone_absence_contrast_db,
        tick_minima,
        max(
            mother.minimum_generic_path_contrast_db,
            pre.carrier_contrast_db - mother.maximum_witness_drop_db,
        ),
        max(
            mother.minimum_generic_path_contrast_db,
            pre.timecode_contrast_db - mother.maximum_witness_drop_db,
        ),
        post_minima,
        pre,
    )


def evaluate_frozen_window(
    mother: GateEMotherPlan,
    offer: GateECapabilityOffer,
    frozen: GateEFrozenPlan,
    capture: kiwi.KiwiCapture,
    pre: SegmentMetrics,
    target: SegmentMetrics,
    post: SegmentMetrics,
    *,
    now: datetime,
) -> GateEOutcome:
    """Produce the only outcome.  No branch changes thresholds or receiver."""

    now = _utc(now)
    contract = gate_e_contract()
    same_apparatus = (
        capture.endpoint == frozen.endpoint
        and abs(capture.center_frequency_hz - frozen.center_frequency_hz) <= 0.5
        and frozen.mother_plan_hash == mother.plan_hash
        and frozen.offer_id == offer.offer_id
    )
    audit_plan = kiwi.ScoutPlan(
        center_frequencies_hz=(frozen.center_frequency_hz,),
        scout_duration_s=(frozen.schedule.post_end - frozen.schedule.stream_start).total_seconds(),
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        min_overlap_s=(frozen.schedule.post_end - frozen.schedule.pre_start).total_seconds(),
        max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
    )
    audit = kiwi.audit_capture(capture, audit_plan)
    continuous_coverage = (
        audit.usable
        and bool(audit.blocks)
        and audit.blocks[0].event_start <= frozen.schedule.pre_start
        and audit.blocks[-1].event_end >= frozen.schedule.post_end
        and audit.sequence_gap_count == 0
        and audit.timestamp_gap_count == 0
        and audit.dropped_block_count == 0
    )
    receiver_health = same_apparatus and continuous_coverage
    identity_supported = bool(frozen.stations_supported)
    path_before = (
        identity_supported
        and all(pre.tick(station) >= frozen.tick_minimum(station) for station in frozen.stations_supported)
        and pre.carrier_contrast_db >= frozen.carrier_minimum_db
        and pre.timecode_contrast_db >= frozen.timecode_minimum_db
    )
    positive_before = path_before and all(
        pre.tone(_standard_tone(station, minute=28)) >= frozen.tone_presence_min_db
        for station in frozen.stations_supported
    )
    path_during = (
        receiver_health
        and all(target.tick(station) >= frozen.tick_minimum(station) for station in frozen.stations_supported)
        and target.carrier_contrast_db >= frozen.carrier_minimum_db
        and target.timecode_contrast_db >= frozen.timecode_minimum_db
    )
    tone_absent = (
        target.tone_500_contrast_db <= frozen.tone_absence_max_db
        and target.tone_600_contrast_db <= frozen.tone_absence_max_db
    )
    positive_after = (
        receiver_health
        and all(post.tick(station) >= frozen.tick_minimum(station) for station in frozen.stations_supported)
        and post.carrier_contrast_db >= frozen.carrier_minimum_db
        and post.timecode_contrast_db >= frozen.timecode_minimum_db
        and all(
            post.tone(_standard_tone(station, minute=31)) >= frozen.post_tone_minimum(station)
            for station in frozen.stations_supported
        )
    )
    negative_interpretable = (
        receiver_health
        and identity_supported
        and path_before
        and positive_before
        and path_during
        and tone_absent
        and positive_after
    )

    if not same_apparatus or not continuous_coverage:
        kind = GateEOutcomeKind.RECEIPT_INVALIDATED
    elif tone_absent and not (path_during and positive_after):
        kind = GateEOutcomeKind.NOT_DETECTABLE
    elif negative_interpretable:
        kind = GateEOutcomeKind.NOT_DETECTED
    elif not tone_absent:
        kind = GateEOutcomeKind.OBSERVATIONAL_PREDICTION_FALSIFIED
    else:
        kind = GateEOutcomeKind.NOT_DETECTABLE

    root = (f"kiwi:{capture.endpoint.name}",)
    statuses = {
        "station_identity_supported": (identity_supported, False),
        "path_alive_before": (path_before, False),
        "positive_control_before": (positive_before, False),
        "path_alive_during_target_window": (path_during, not receiver_health),
        "standard_tone_absent": (tone_absent, not receiver_health),
        "positive_control_after": (positive_after, not receiver_health),
        "receiver_health_continuous": (receiver_health, False),
        "negative_interpretable": (negative_interpretable, not receiver_health),
    }
    assessments = tuple(
        ClauseAssessment(
            clause,
            ClauseStatus.SATISFIED
            if satisfied
            else (ClauseStatus.UNOBSERVABLE if unobservable else ClauseStatus.UNSATISFIED),
            _clause_statement(clause, satisfied, unobservable),
            root if satisfied else (),
        )
        for clause, (satisfied, unobservable) in statuses.items()
    )
    receipt = ConstraintReceipt(
        branch="kiwi-gate-e-wwv-absence",
        event_start=frozen.schedule.pre_start,
        event_end=frozen.schedule.post_end,
        constraints=(
            Constraint("mother_plan_hash", "sha256", mother.plan_hash, None, "method fixed before discovery", "serialized GateEMotherPlan"),
            Constraint("frozen_plan_hash", "sha256", frozen.plan_hash, None, "apparatus, station identity, baselines and thresholds frozen before minute 29", "serialized GateEFrozenPlan"),
            Constraint("same_apparatus", "==", same_apparatus, None, "disconnect or retune invalidates the receipt", "endpoint and center-frequency identity"),
            Constraint("stations_supported", "marker", frozen.stations_supported, None, "1000 Hz identifies WWV; 1200 Hz identifies WWVH", "UTC-aligned second pulses"),
            Constraint("pre_metrics", "measured", pre, "dB contrast", "minute 28 positive control", "same live stream"),
            Constraint("target_metrics", "measured", target, "dB contrast", "minutes 29-30 scheduled silence", "same live stream"),
            Constraint("post_metrics", "measured", post, "dB contrast", "minute 31 recovery control", "same live stream"),
            Constraint("outcome", "classified", kind, None, "one outcome; no retry", "frozen Gate E semantics"),
        ),
        transforms=(
            Transform("kiwi_rf_chain", "partial", "antenna, HF propagation, analog front-end, ADC/DDC and fixed AGC"),
            Transform("am_envelope", "known_lossy", "complex phase discarded; AM modulation retained"),
            Transform("utc_marker_projection", "known", "station-specific 5 ms second pulses projected at 1000/1200 Hz"),
            Transform("standard_tone_contrast", "known", "500/600 Hz envelope projections compared with fixed neighboring frequencies"),
            Transform("same_stream_bracketing", "known", "minute 28, minutes 29-30 and minute 31 use one unchanged connection"),
        ),
        measurement_roots=root,
        model_roots=(
            "nist:wwv-wwvh-broadcast-format",
            f"gate-e:mother:{mother.plan_hash[:16]}",
            f"gate-e:frozen:{frozen.plan_hash[:16]}",
        ),
        artifact_hashes=(kiwi._capture_hash(capture),),
        caveats=(
            "HF selective fading can affect modulation components differently from the carrier",
            "an undiagnosed co-channel interferer at exactly 500 or 600 Hz can falsify the observational prediction",
            "one station-specific witness can support a strong negative without requiring two measurement roots",
        ),
    )
    evidence = EvidenceEvent("kiwi-gate-e-live-iq", capture.arrived_end, receipt)
    belief = contract.snapshot_from_evidence(
        receipt,
        valid_at=now,
        clause_assessments=assessments,
        uncertainty=receipt.caveats,
        active_model_roots=receipt.model_roots,
    )
    return GateEOutcome(kind, mother.plan_hash, offer, frozen, pre, target, post, evidence, belief)


def falsifiability_not_entered(
    mother: GateEMotherPlan,
    offer: GateECapabilityOffer | None,
    event_start: datetime,
    event_end: datetime,
    reason: str,
    *,
    now: datetime,
) -> GateEOutcome:
    contract = gate_e_contract()
    event_start, event_end, now = _utc(event_start), _utc(event_end), _utc(now)
    receipt = ConstraintReceipt(
        "kiwi-gate-e-wwv-absence",
        event_start,
        event_end,
        (
            Constraint("falsifiability_entry", "refused", reason, None, "no target-window interpretation is permitted", "Gate E precondition"),
            Constraint("mother_plan_hash", "sha256", mother.plan_hash, None, "method fixed before discovery", "serialized GateEMotherPlan"),
        ),
        (Transform("capability_preflight", "incomplete", reason),),
        () if offer is None else (f"kiwi:{offer.endpoint.name}",),
        ("nist:wwv-wwvh-broadcast-format", f"gate-e:mother:{mother.plan_hash[:16]}"),
        () if offer is None else (offer.artifact_hash,),
        (reason, "no second execution is opened after this outcome"),
    )
    assessments = tuple(
        ClauseAssessment(
            clause.name,
            ClauseStatus.UNOBSERVABLE,
            f"Gate E did not enter the falsifiable state: {reason}",
            (),
        )
        for clause in contract.clauses
    )
    evidence = EvidenceEvent("kiwi-gate-e-preflight", now, receipt)
    belief = contract.snapshot_from_evidence(
        receipt,
        valid_at=now,
        clause_assessments=assessments,
        uncertainty=receipt.caveats,
        active_model_roots=receipt.model_roots,
    )
    return GateEOutcome(
        GateEOutcomeKind.FALSIFIABILITY_NOT_ENTERED,
        mother.plan_hash,
        offer,
        None,
        None,
        None,
        None,
        evidence,
        belief,
    )


def invalidated_after_freeze(
    mother: GateEMotherPlan,
    offer: GateECapabilityOffer,
    frozen: GateEFrozenPlan,
    pre: SegmentMetrics,
    capture: kiwi.KiwiCapture,
    reason: str,
    *,
    now: datetime,
) -> GateEOutcome:
    """A post-freeze disconnect is invalidation, never a negative result."""

    now = _utc(now)
    contract = gate_e_contract()
    root = (f"kiwi:{capture.endpoint.name}",)
    pre_path = all(
        pre.tick(station) >= frozen.tick_minimum(station)
        for station in frozen.stations_supported
    )
    pre_positive = pre_path and all(
        pre.tone(_standard_tone(station, minute=28)) >= frozen.tone_presence_min_db
        for station in frozen.stations_supported
    )
    pre_status = {
        "station_identity_supported": bool(frozen.stations_supported),
        "path_alive_before": pre_path,
        "positive_control_before": pre_positive,
    }
    assessments = tuple(
        ClauseAssessment(
            clause.name,
            (
                ClauseStatus.SATISFIED
                if pre_status.get(clause.name, False)
                else (
                    ClauseStatus.UNSATISFIED
                    if clause.name == "receiver_health_continuous"
                    else ClauseStatus.UNOBSERVABLE
                )
            ),
            reason if clause.name == "receiver_health_continuous" else _clause_statement(
                clause.name,
                pre_status.get(clause.name, False),
                clause.name not in pre_status,
            ),
            root if pre_status.get(clause.name, False) else (),
        )
        for clause in contract.clauses
    )
    receipt = ConstraintReceipt(
        "kiwi-gate-e-wwv-absence",
        frozen.schedule.pre_start,
        capture.event_end,
        (
            Constraint("frozen_plan_hash", "sha256", frozen.plan_hash, None, "plan was frozen before interruption", "serialized GateEFrozenPlan"),
            Constraint("stream_continuity", "invalidated", reason, None, "no target absence may be interpreted", "same live connection"),
            Constraint("outcome", "classified", GateEOutcomeKind.RECEIPT_INVALIDATED, None, "no retry", "Gate E semantics"),
        ),
        (
            Transform("same_stream_bracketing", "incomplete", reason),
            Transform("kiwi_rf_chain", "partial", "the stream did not cover all frozen windows"),
        ),
        root,
        (
            "nist:wwv-wwvh-broadcast-format",
            f"gate-e:mother:{mother.plan_hash[:16]}",
            f"gate-e:frozen:{frozen.plan_hash[:16]}",
        ),
        (kiwi._capture_hash(capture),),
        (reason, "post-freeze interruption invalidates rather than weakens the receipt"),
    )
    evidence = EvidenceEvent("kiwi-gate-e-interrupted-iq", capture.arrived_end, receipt)
    belief = contract.snapshot_from_evidence(
        receipt,
        valid_at=now,
        clause_assessments=assessments,
        uncertainty=receipt.caveats,
        active_model_roots=receipt.model_roots,
    )
    return GateEOutcome(
        GateEOutcomeKind.RECEIPT_INVALIDATED,
        mother.plan_hash,
        offer,
        frozen,
        pre,
        None,
        None,
        evidence,
        belief,
    )


def measure_segment(
    capture: kiwi.KiwiCapture,
    audit: kiwi.CaptureAudit,
    event_start: datetime,
    event_end: datetime,
) -> SegmentMetrics:
    event_start, event_end = _utc(event_start), _utc(event_end)
    samples, actual_start = _continuous_samples(capture, audit, event_start, event_end)
    if len(samples) < capture.sample_rate_hz:
        raise ValueError("Gate E segment is shorter than one second")
    envelope = np.abs(samples).astype(np.float64)
    envelope -= np.median(envelope)
    return SegmentMetrics(
        event_start,
        event_end,
        _continuous_audio_contrast(envelope, capture.sample_rate_hz, actual_start, 500.0),
        _continuous_audio_contrast(envelope, capture.sample_rate_hz, actual_start, 600.0),
        _tick_contrast(envelope, capture.sample_rate_hz, actual_start, 1000.0),
        _tick_contrast(envelope, capture.sample_rate_hz, actual_start, 1200.0),
        _carrier_contrast(samples, capture.sample_rate_hz),
        _continuous_audio_contrast(envelope, capture.sample_rate_hz, actual_start, 100.0),
    )


def run_gate_e_once(
    *,
    endpoints: tuple[kiwi.KiwiEndpoint, ...] = (
        kiwi.KiwiEndpoint("n8ga-ohio", "hill.n8ga.org", 8073),
        kiwi.KiwiEndpoint("blair-washington", "kiwisdr2blair.ddns.net", 8073),
        kiwi.KiwiEndpoint("kfs-california", "kiwisdr.kfsdr.com", 8074),
        kiwi.KiwiEndpoint("va6ok-alberta", "va6ok.ddns.net", 8073),
    ),
    mother: GateEMotherPlan | None = None,
    sink: Callable[[str], None] = print,
) -> GateEOutcome:
    """Scout once, run one continuous 28--31 stream, emit one outcome, stop."""

    mother = mother or GateEMotherPlan()
    now = datetime.now(timezone.utc)
    schedule = _next_schedule(now, mother)
    discovery_start = schedule.stream_start - timedelta(minutes=5)
    emit_jsonl("gate_e_mother_plan_frozen", mother, sink=sink)
    emit_jsonl("gate_e_schedule_registered", schedule, sink=sink)
    _wait_until(discovery_start, "capability_discovery", sink)

    offers: list[GateECapabilityOffer] = []
    for endpoint in endpoints:
        for frequency in mother.candidate_frequencies_hz:
            if datetime.now(timezone.utc) >= schedule.stream_start - timedelta(seconds=15):
                break
            try:
                capture = _capture_one_short(
                    endpoint,
                    frequency,
                    mother.scout_duration_s,
                    mother.maximum_gps_solution_age_s,
                )
                offer = offer_from_capture(mother, capture, datetime.now(timezone.utc))
                offers.append(offer)
                emit_jsonl("gate_e_capability_offer", _offer_value(offer), sink=sink)
            except Exception as error:
                emit_jsonl(
                    "gate_e_capability_refused",
                    {"endpoint": asdict(endpoint), "center_frequency_hz": frequency, "reason": str(error)},
                    sink=sink,
                )
        if datetime.now(timezone.utc) >= schedule.stream_start - timedelta(seconds=15):
            break

    selected = select_capability_offer(
        offers,
        now=datetime.now(timezone.utc),
        required_until=schedule.post_end,
    )
    if selected is None:
        outcome = falsifiability_not_entered(
            mother,
            None,
            now,
            datetime.now(timezone.utc),
            "no fresh capability offer closes a station-specific causal path through minute 31",
            now=datetime.now(timezone.utc),
        )
        emit_jsonl("gate_e_first_outcome", outcome, sink=sink)
        return outcome
    emit_jsonl("gate_e_capability_selected", _offer_value(selected), sink=sink)
    _wait_until(schedule.stream_start - timedelta(seconds=5), "continuous_stream", sink)
    try:
        outcome = _capture_gate_e_stream(mother, selected, schedule, sink)
    except Exception as error:
        outcome = falsifiability_not_entered(
            mother,
            selected,
            schedule.stream_start,
            datetime.now(timezone.utc),
            f"continuous stream failed before a valid outcome: {error}",
            now=datetime.now(timezone.utc),
        )
    emit_jsonl("gate_e_confirmation_evidence", outcome.evidence.receipt, sink=sink)
    emit_jsonl("gate_e_first_outcome", {"kind": outcome.kind, "belief": outcome.belief}, sink=sink)
    return outcome


def _capture_gate_e_stream(
    mother: GateEMotherPlan,
    offer: GateECapabilityOffer,
    schedule: GateESchedule,
    sink: Callable[[str], None],
) -> GateEOutcome:
    import websocket

    endpoint = offer.endpoint
    status = kiwi.fetch_kiwi_status(endpoint)
    if int(status.get("ext_api", "0") or 0) <= 0:
        raise RuntimeError("selected Kiwi no longer offers an external API slot")
    token = (int(time.time()) + (hash((endpoint.name, "gate-e")) & 0xFFFF)) & 0xFFFFFFFF
    ws = websocket.create_connection(
        f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
    )
    ws.send("SET auth t=kiwi p=")
    sample_rate = 0.0
    blocks: list[kiwi.IQBlock] = []
    arrived_start: datetime | None = None
    arrived_end: datetime | None = None
    frozen: GateEFrozenPlan | None = None
    pre: SegmentMetrics | None = None
    last_keepalive = 0.0
    stream_error: str | None = None
    try:
        try:
            while True:
                message = ws.recv()
                arrival = datetime.now(timezone.utc)
                if isinstance(message, str):
                    message = message.encode("latin-1")
                if not isinstance(message, bytes) or len(message) < 3:
                    continue
                tag, body = message[:3], message[3:]
                if tag == b"MSG":
                    params = _msg_params(body[1:])
                    if params.get("too_busy") is not None:
                        raise RuntimeError("selected Kiwi became busy")
                    if params.get("badp") not in (None, "0"):
                        raise RuntimeError(f"selected Kiwi rejected the public connection: badp={params['badp']}")
                    if "audio_rate" in params:
                        ws.send(f"SET AR OK in={int(float(params['audio_rate']))} out=44100")
                    if "sample_rate" in params and sample_rate == 0.0:
                        sample_rate = float(params["sample_rate"])
                        frequency_khz = offer.center_frequency_hz / 1000.0
                        for command in (
                            "SET squelch=0 max=0",
                            "SET genattn=0",
                            "SET gen=0 mix=-1",
                            "SET ident_user=Satellite-RF-Observatory_Gate_E",
                            f"SET mod=iq low_cut=-5000 high_cut=5000 freq={frequency_khz:.3f}",
                            "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50",
                            "SET compression=0",
                            "SET keepalive",
                        ):
                            ws.send(command)
                elif tag == b"SND" and sample_rate > 0.0:
                    block = kiwi._decode_iq_block(body, sample_rate, arrival)
                    if block.event_end >= schedule.stream_start:
                        blocks.append(block)
                        arrived_start = arrived_start or arrival
                        arrived_end = arrival
                    if frozen is None and block.event_end >= schedule.pre_end:
                        partial = _capture_from_blocks(endpoint, offer.center_frequency_hz, sample_rate, status, blocks, arrived_start, arrived_end)
                        partial_audit = _full_window_audit(
                            mother,
                            partial,
                            (schedule.pre_end - schedule.stream_start).total_seconds(),
                        )
                        pre = measure_segment(partial, partial_audit, schedule.pre_start, schedule.pre_end)
                        try:
                            frozen = freeze_plan_after_positive_control(
                                mother,
                                offer,
                                schedule,
                                pre,
                                datetime.now(timezone.utc),
                            )
                        except ValueError as error:
                            return falsifiability_not_entered(
                                mother,
                                offer,
                                schedule.pre_start,
                                block.event_end,
                                str(error),
                                now=datetime.now(timezone.utc),
                            )
                        emit_jsonl("gate_e_plan_frozen_before_target", frozen, sink=sink)
                    if frozen is not None and block.event_end >= schedule.post_end:
                        break
                monotonic_now = time.monotonic()
                if monotonic_now - last_keepalive >= 1.0:
                    ws.send("SET keepalive")
                    last_keepalive = monotonic_now
        except Exception as error:
            stream_error = str(error)
    finally:
        try:
            ws.close()
        except Exception:
            pass
    if stream_error is not None:
        if frozen is None or pre is None or not blocks:
            raise RuntimeError(stream_error)
        partial = _capture_from_blocks(
            endpoint,
            offer.center_frequency_hz,
            sample_rate,
            status,
            blocks,
            arrived_start,
            arrived_end,
        )
        return invalidated_after_freeze(
            mother,
            offer,
            frozen,
            pre,
            partial,
            stream_error,
            now=datetime.now(timezone.utc),
        )
    if frozen is None or pre is None:
        raise RuntimeError("stream ended before the plan could be frozen")
    capture = _capture_from_blocks(
        endpoint,
        offer.center_frequency_hz,
        sample_rate,
        status,
        blocks,
        arrived_start,
        arrived_end,
    )
    audit = _full_window_audit(
        mother,
        capture,
        (schedule.post_end - schedule.pre_start).total_seconds(),
    )
    target = measure_segment(capture, audit, schedule.target_start, schedule.target_end)
    post = measure_segment(capture, audit, schedule.post_start, schedule.post_end)
    return evaluate_frozen_window(
        mother,
        offer,
        frozen,
        capture,
        pre,
        target,
        post,
        now=datetime.now(timezone.utc),
    )


def _capture_one_short(
    endpoint: kiwi.KiwiEndpoint,
    center_frequency_hz: float,
    duration_s: float,
    max_gps_solution_age_s: int,
) -> kiwi.KiwiCapture:
    start = Event()
    ready = Event()
    start.set()
    return kiwi._capture_one(
        endpoint,
        center_frequency_hz,
        duration_s,
        start,
        ready,
        max_gps_solution_age_s,
    )


def _continuous_samples(
    capture: kiwi.KiwiCapture,
    audit: kiwi.CaptureAudit,
    event_start: datetime,
    event_end: datetime,
) -> tuple[np.ndarray, datetime]:
    if not audit.blocks:
        raise ValueError("no continuous blocks are available")
    segment_start = audit.blocks[0].event_start
    samples = np.concatenate([block.samples for block in audit.blocks])
    begin = int(round((event_start - segment_start).total_seconds() * capture.sample_rate_hz))
    finish = int(round((event_end - segment_start).total_seconds() * capture.sample_rate_hz))
    if begin < 0 or finish > len(samples) or finish <= begin:
        raise ValueError("requested Gate E interval is outside the continuous stream")
    return samples[begin:finish], segment_start + timedelta(seconds=begin / capture.sample_rate_hz)


def _continuous_audio_contrast(
    envelope: np.ndarray,
    sample_rate_hz: float,
    event_start: datetime,
    frequency_hz: float,
) -> float:
    controls = tuple(
        candidate
        for candidate in (
            frequency_hz - 137.0,
            frequency_hz - 83.0,
            frequency_hz + 83.0,
            frequency_hz + 137.0,
        )
        if candidate >= 25.0
    )
    target_amplitudes: list[float] = []
    control_amplitudes: list[float] = []
    start_ts = event_start.timestamp()
    end_ts = start_ts + len(envelope) / sample_rate_hz
    for second in range(math.ceil(start_ts), math.floor(end_ts)):
        second_in_minute = datetime.fromtimestamp(second, tz=timezone.utc).second
        if not 3 <= second_in_minute <= 40:
            continue
        begin = int(round((second + 0.10 - start_ts) * sample_rate_hz))
        finish = int(round((second + 0.80 - start_ts) * sample_rate_hz))
        if begin < 0 or finish > len(envelope) or finish - begin < 64:
            continue
        values = envelope[begin:finish]
        values = signal.detrend(values, type="linear")
        window = signal.windows.hann(len(values), sym=False)
        weighted = values * window
        times = np.arange(len(values), dtype=float) / sample_rate_hz
        target_amplitudes.append(_projection_amplitude(weighted, times, frequency_hz))
        control_amplitudes.extend(
            _projection_amplitude(weighted, times, control) for control in controls
        )
    if not target_amplitudes or not control_amplitudes:
        return -math.inf
    target = float(np.median(target_amplitudes))
    control = float(np.median(control_amplitudes))
    return 20.0 * math.log10((target + 1e-12) / (control + 1e-12))


def _tick_contrast(
    envelope: np.ndarray,
    sample_rate_hz: float,
    event_start: datetime,
    frequency_hz: float,
) -> float:
    pulse_samples = max(16, int(round(0.005 * sample_rate_hz)))
    start_ts = event_start.timestamp()
    end_ts = start_ts + len(envelope) / sample_rate_hz
    event_powers: list[float] = []
    null_powers: list[float] = []
    relative_times = np.arange(pulse_samples, dtype=float) / sample_rate_hz
    template = np.exp(-2j * np.pi * frequency_hz * relative_times)
    for second in range(math.ceil(start_ts), math.floor(end_ts)):
        second_number = datetime.fromtimestamp(second, tz=timezone.utc).second
        if second_number in (0, 29, 59):
            continue
        candidates: list[float] = []
        for delay_ms in range(0, 51):
            begin = int(round((second + delay_ms / 1000.0 - start_ts) * sample_rate_hz))
            finish = begin + pulse_samples
            if begin < 0 or finish > len(envelope):
                continue
            values = envelope[begin:finish] - np.mean(envelope[begin:finish])
            candidates.append(float(abs(np.vdot(template, values)) ** 2))
        if candidates:
            event_powers.append(max(candidates))
        for offset_s in (0.20, 0.40, 0.60, 0.80):
            begin = int(round((second + offset_s - start_ts) * sample_rate_hz))
            finish = begin + pulse_samples
            if begin < 0 or finish > len(envelope):
                continue
            values = envelope[begin:finish] - np.mean(envelope[begin:finish])
            null_powers.append(float(abs(np.vdot(template, values)) ** 2))
    if not event_powers or not null_powers:
        return -math.inf
    return 10.0 * math.log10(
        (float(np.median(event_powers)) + 1e-18)
        / (float(np.median(null_powers)) + 1e-18)
    )


def _carrier_contrast(samples: np.ndarray, sample_rate_hz: float) -> float:
    nperseg = min(len(samples), 16_384)
    if nperseg < 256:
        return -math.inf
    frequencies, power = signal.welch(
        samples,
        fs=sample_rate_hz,
        window="hann",
        nperseg=nperseg,
        noverlap=nperseg // 2,
        return_onesided=False,
        scaling="spectrum",
    )
    signal_mask = np.abs(frequencies) <= 20.0
    control_mask = (np.abs(frequencies) >= 80.0) & (np.abs(frequencies) <= 300.0)
    if not np.any(signal_mask) or not np.any(control_mask):
        return -math.inf
    carrier = float(np.max(power[signal_mask]))
    floor = float(np.median(power[control_mask]))
    return 10.0 * math.log10((carrier + 1e-18) / (floor + 1e-18))


def _projection_amplitude(values: np.ndarray, times: np.ndarray, frequency_hz: float) -> float:
    return float(abs(np.vdot(np.exp(-2j * np.pi * frequency_hz * times), values)))


def _standard_tone(station: str, *, minute: int) -> int:
    if minute == 28:
        return 500 if station == WWV else 600
    if minute == 31:
        return 600 if station == WWV else 500
    raise ValueError("Gate E defines station-specific tones only for minutes 28 and 31")


def _full_window_audit(
    mother: GateEMotherPlan,
    capture: kiwi.KiwiCapture,
    minimum_duration_s: float,
) -> kiwi.CaptureAudit:
    return kiwi.audit_capture(
        capture,
        kiwi.ScoutPlan(
            center_frequencies_hz=(capture.center_frequency_hz,),
            scout_duration_s=max(minimum_duration_s, 1.0),
            nperseg=mother.nperseg,
            noverlap=mother.noverlap,
            min_overlap_s=minimum_duration_s,
            max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
        ),
    )


def _capture_from_blocks(
    endpoint: kiwi.KiwiEndpoint,
    center_frequency_hz: float,
    sample_rate_hz: float,
    status: dict[str, str],
    blocks: list[kiwi.IQBlock],
    arrived_start: datetime | None,
    arrived_end: datetime | None,
) -> kiwi.KiwiCapture:
    if not blocks or arrived_start is None or arrived_end is None:
        raise RuntimeError("Gate E stream returned no GNSS IQ blocks")
    return kiwi.KiwiCapture(
        endpoint,
        center_frequency_hz,
        sample_rate_hz,
        status,
        tuple(blocks),
        arrived_start,
        arrived_end,
    )


def _msg_params(body: bytes) -> dict[str, str | None]:
    values: dict[str, str | None] = {}
    for token in body.decode("ascii", errors="replace").split():
        if "=" in token:
            name, value = token.split("=", 1)
            values[name] = unquote(value)
        else:
            values[token] = None
    return values


def _next_schedule(now: datetime, mother: GateEMotherPlan) -> GateESchedule:
    now = _utc(now)
    hour = now.replace(minute=0, second=0, microsecond=0)
    candidate = GateESchedule.for_hour(hour, mother)
    if now >= candidate.stream_start - timedelta(minutes=6):
        candidate = GateESchedule.for_hour(hour + timedelta(hours=1), mother)
    return candidate


def _wait_until(when: datetime, phase: str, sink: Callable[[str], None]) -> None:
    when = _utc(when)
    remaining = (when - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        return
    emit_jsonl(
        "gate_e_waiting",
        {"phase": phase, "until": when, "remaining_s": remaining},
        sink=sink,
    )
    while True:
        remaining = (when - datetime.now(timezone.utc)).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 30.0))


def _offer_value(offer: GateECapabilityOffer) -> dict[str, object]:
    value = asdict(offer)
    value["audit"].pop("blocks", None)  # type: ignore[union-attr]
    value["audit"]["selected_block_count"] = len(offer.audit.blocks)  # type: ignore[index]
    value["falsification_rank"] = offer.falsification_rank
    return value


def _clause_statement(clause: str, satisfied: bool, unobservable: bool) -> str:
    if unobservable:
        return f"{clause} cannot be evaluated because continuous same-apparatus evidence is unavailable."
    if satisfied:
        return f"{clause} is supported by the frozen same-stream receipt."
    return f"{clause} is not supported by the frozen same-stream receipt."


def _empty_metrics(start: datetime, end: datetime) -> SegmentMetrics:
    return SegmentMetrics(_utc(start), _utc(end), *([-math.inf] * 6))


def _hash(value: object) -> str:
    payload = json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(value: object):
    if isinstance(value, datetime):
        return _utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def main() -> None:
    run_gate_e_once()


if __name__ == "__main__":
    main()
