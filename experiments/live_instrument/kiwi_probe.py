"""Probe B: simultaneous targetless KiwiSDR IQ capture and RF-structure test.

The implementation intentionally knows only the small SND/IQ protocol surface
used by this experiment. It is not a generic Internet source or Kiwi framework.
Samples live in bounded RAM ring buffers and are never written to disk.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import struct
from threading import Event
import time
from typing import Any
from urllib.parse import unquote
from urllib.request import Request, urlopen

import numpy as np
from scipy import signal

from .models import (
    BeliefSnapshot,
    CausalGraph,
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


GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
GPS_WEEK_S = 604_800.0
ASSUMED_GPS_MINUS_UTC_S = 18.0
USER_AGENT = "Satellite-RF-Observatory-Gate-B/0.1"


@dataclass(frozen=True, slots=True)
class KiwiEndpoint:
    name: str
    host: str
    port: int = 8073


@dataclass(frozen=True, slots=True)
class IQBlock:
    event_start: datetime
    event_end: datetime
    samples: np.ndarray
    rssi_db: float
    gps_solution_age_s: int
    gps_timestamp_available: bool
    adc_overflow: bool
    sequence: int
    arrived_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class KiwiCapture:
    endpoint: KiwiEndpoint
    center_frequency_hz: float
    sample_rate_hz: float
    status: dict[str, str]
    blocks: tuple[IQBlock, ...]
    arrived_start: datetime
    arrived_end: datetime

    @property
    def event_start(self) -> datetime:
        return self.blocks[0].event_start

    @property
    def event_end(self) -> datetime:
        return self.blocks[-1].event_end

    @property
    def samples(self) -> np.ndarray:
        return np.concatenate([block.samples for block in self.blocks])


@dataclass(frozen=True, slots=True)
class ScoutPlan:
    """Frozen CP3 search/calibration plan; changing it creates a new trial."""

    center_frequencies_hz: tuple[float, ...] = (
        5_000_000.0,
        10_000_000.0,
        15_000_000.0,
    )
    scout_duration_s: float = 2.5
    nperseg: int = 512
    noverlap: int = 384
    region_shapes: tuple[tuple[int, int], ...] = ((7, 8), (15, 16))
    null_shift_count: int = 99
    significance_alpha: float = 0.01
    max_gps_solution_age_s: int = 30
    max_arrival_latency_s: float = 5.0
    min_overlap_s: float = 2.0
    salience_clip: float = 12.0

    def __post_init__(self) -> None:
        if not self.center_frequencies_hz or any(
            frequency <= 0 for frequency in self.center_frequencies_hz
        ):
            raise ValueError("the scout needs positive predeclared center frequencies")
        if self.scout_duration_s <= 0 or self.min_overlap_s <= 0:
            raise ValueError("scout and overlap durations must be positive")
        if self.nperseg <= 0 or not 0 <= self.noverlap < self.nperseg:
            raise ValueError("invalid STFT geometry")
        if self.null_shift_count < 1 or not 0 < self.significance_alpha <= 1:
            raise ValueError("invalid frozen null-test rule")
        if any(frequency_bins < 1 or time_frames < 2 for frequency_bins, time_frames in self.region_shapes):
            raise ValueError("region shapes must contain positive frequency/time extents")

    @property
    def plan_hash(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CaptureAudit:
    usable: bool
    reasons: tuple[str, ...]
    blocks: tuple[IQBlock, ...]
    sequence_gap_count: int
    timestamp_gap_count: int
    dropped_block_count: int
    overlap_ready_duration_s: float
    effective_sample_rate_hz: float
    sample_rate_drift_ppm: float
    cumulative_timing_drift_s: float
    arrival_latency_median_s: float | None
    arrival_latency_p95_s: float | None
    gps_solution_age_max_s: int | None


@dataclass(frozen=True, slots=True)
class ScoutRegion:
    event_start: datetime
    event_end: datetime
    frequency_low_hz: float
    frequency_high_hz: float
    score: float
    frequency_bins: int
    time_frames: int


@dataclass(frozen=True, slots=True)
class ScoutResult:
    region: ScoutRegion | None
    observed_score: float | None
    left_score: float | None
    right_score: float | None
    time_null_p: float | None
    frequency_null_p: float | None
    time_null_count: int
    frequency_null_count: int
    self_consistent: bool
    even_odd_frequency_iou: float | None
    relative_frequency_offset_hz: float | None
    relative_frequency_drift_hz_s: float | None
    alignable: bool
    similarity_exceeds_null: bool
    failures: tuple[str, ...]
    plan_hash: str


@dataclass(frozen=True, slots=True)
class _SpectralGrid:
    frequencies_hz: np.ndarray
    event_times_s: np.ndarray
    log_power: np.ndarray
    dynamic: np.ndarray
    time_step_s: float
    frequency_step_hz: float


@dataclass(frozen=True, slots=True)
class _RegionIndex:
    frequency_start: int
    time_start: int
    frequency_bins: int
    time_frames: int
    score: float


class IQBlockRing:
    """A time-bounded in-memory ring; blocks are evicted by GNSS event time."""

    def __init__(self, max_seconds: float):
        if max_seconds <= 0:
            raise ValueError("ring duration must be positive")
        self.max_seconds = max_seconds
        self._blocks: deque[IQBlock] = deque()

    def append(self, block: IQBlock) -> None:
        self._blocks.append(block)
        while (
            len(self._blocks) > 1
            and (self._blocks[-1].event_end - self._blocks[0].event_start).total_seconds()
            > self.max_seconds
        ):
            self._blocks.popleft()

    def snapshot(self) -> tuple[IQBlock, ...]:
        return tuple(self._blocks)


def fetch_kiwi_status(endpoint: KiwiEndpoint, timeout_s: float = 8.0) -> dict[str, str]:
    request = Request(
        f"http://{endpoint.host}:{endpoint.port}/status",
        headers={"User-Agent": USER_AGENT, "Accept": "text/plain"},
    )
    with urlopen(request, timeout=timeout_s) as response:
        body = response.read().decode("utf-8", errors="replace")
    fields: dict[str, str] = {}
    for token in body.replace("\n", " ").split():
        if "=" in token:
            name, value = token.split("=", 1)
            fields[name] = unquote(value)
    return fields


def capture_dual_kiwi(
    endpoints: tuple[KiwiEndpoint, KiwiEndpoint],
    *,
    center_frequency_hz: float,
    duration_s: float = 8.0,
    ready_timeout_s: float = 18.0,
    max_gps_solution_age_s: int = 30,
) -> tuple[KiwiCapture, KiwiCapture]:
    """Open both receivers concurrently and retain only a synchronized RAM window."""

    start_event = Event()
    ready_events = (Event(), Event())
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="kiwi-probe") as pool:
        futures = [
            pool.submit(
                _capture_one,
                endpoint,
                center_frequency_hz,
                duration_s,
                start_event,
                ready_events[index],
                max_gps_solution_age_s,
            )
            for index, endpoint in enumerate(endpoints)
        ]
        deadline = time.monotonic() + ready_timeout_s
        for ready in ready_events:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not ready.wait(remaining):
                start_event.set()
                raise RuntimeError("dual Kiwi receivers did not become ready together")
        start_event.set()
        captures = tuple(future.result(timeout=duration_s + ready_timeout_s) for future in futures)
    return captures  # type: ignore[return-value]


def compare_rf_structure(
    contract: DecisionContract,
    left: KiwiCapture,
    right: KiwiCapture,
    now: datetime,
    *,
    plan: ScoutPlan | None = None,
) -> tuple[EvidenceEvent, BeliefSnapshot, CausalGraph]:
    """Run the first and only calibrated comparison under a frozen plan."""

    if plan is None:
        plan = replace(
            ScoutPlan(),
            center_frequencies_hz=(left.center_frequency_hz,),
        )
    left_audit = audit_capture(left, plan)
    right_audit = audit_capture(right, plan)
    overlap_start = max(
        left_audit.blocks[0].event_start if left_audit.blocks else left.event_start,
        right_audit.blocks[0].event_start if right_audit.blocks else right.event_start,
    )
    overlap_end = min(
        left_audit.blocks[-1].event_end if left_audit.blocks else left.event_end,
        right_audit.blocks[-1].event_end if right_audit.blocks else right.event_end,
    )
    if overlap_end < overlap_start:
        overlap_end = overlap_start
    overlap_s = (overlap_end - overlap_start).total_seconds()
    fresh = contract.accepts_age(overlap_end, now)
    same_acquisition_band = math_isclose(
        left.center_frequency_hz, right.center_frequency_hz, absolute=0.5
    )
    measurement_available = (
        left_audit.usable
        and right_audit.usable
        and overlap_s >= plan.min_overlap_s
        and fresh
        and same_acquisition_band
    )
    if measurement_available:
        scout = scout_targetless_region(
            left,
            right,
            plan,
            audits=(left_audit, right_audit),
        )
    else:
        failures = list(left_audit.reasons + right_audit.reasons)
        if overlap_s < plan.min_overlap_s:
            failures.append("insufficient common continuous GNSS interval")
        if not fresh:
            failures.append("measurement expired by event time")
        if not same_acquisition_band:
            failures.append("receivers were not tuned to one acquisition band")
        scout = _empty_scout(plan, failures)
    similarity_exceeds_null = measurement_available and scout.similarity_exceeds_null

    measurement_roots = (
        f"kiwi:{left.endpoint.name}",
        f"kiwi:{right.endpoint.name}",
    )
    conditioning_roots = (
        "kiwi:shared-hardware-protocol-ddc",
        "probe-b:targetless-scout-null-code",
        f"probe-b:scout-plan:{plan.plan_hash[:16]}",
    )
    constraints = (
        Constraint("frozen_scout_plan", "sha256", plan.plan_hash, None, "parameters are fixed before live samples; a changed hash is a new trial", "serialized ScoutPlan"),
        Constraint("left_capture_audit", "must_be_usable", _audit_value(left_audit), None, "one block cannot independently estimate rate drift", "IQ sequence, GNSS headers, arrival and sample geometry"),
        Constraint("right_capture_audit", "must_be_usable", _audit_value(right_audit), None, "one block cannot independently estimate rate drift", "IQ sequence, GNSS headers, arrival and sample geometry"),
        Constraint("temporal_overlap", ">=", overlap_s, "s", "only the longest common gap-free segment is compared", "GNSS event-time intersection"),
        Constraint("measurement_fresh", "==", fresh, None, "event end, never arrival time", "DecisionContract age rule"),
        Constraint("same_acquisition_band", "prerequisite_only", same_acquisition_band, None, "nominal tuning is control, never evidence", f"{left.center_frequency_hz} / {right.center_frequency_hz} Hz"),
        Constraint("targetless_region", "selected_by_joint_salience", _region_value(scout.region), None, "the region has no assigned transmitter or target", "maximum of the frozen simultaneous min-salience search"),
        Constraint("time_shift_null", "p<=frozen_alpha", scout.time_null_p, None, "in-session shifts preserve station-local structure", f"{scout.time_null_count} shifts; alpha={plan.significance_alpha}"),
        Constraint("frequency_shift_null", "p<=frozen_alpha", scout.frequency_null_p, None, "wrong-frequency shifts test specificity without retuning", f"{scout.frequency_null_count} shifts; alpha={plan.significance_alpha}"),
        Constraint("self_consistency", "even_odd_frequency_overlap", scout.self_consistent, None, "interleaved folds are not independent roots", f"frequency IoU={scout.even_odd_frequency_iou}"),
        Constraint("frequency_alignability", "one_resolution_element", scout.alignable, None, "offset and drift are diagnostics, never post-hoc corrections", f"offset={scout.relative_frequency_offset_hz} Hz; drift={scout.relative_frequency_drift_hz_s} Hz/s"),
        Constraint("shared_structure_beyond_null", "resolved_or_unresolved", similarity_exceeds_null, None, "the in-session null is conditional on this band, plan and session", "; ".join(scout.failures) or "both frozen nulls and consistency checks passed"),
        Constraint("common_physical_cause", "unresolved", None, None, "no identity, emitter geometry, TDoA or propagation model", "similarity beyond the null is support, not causal identification"),
    )
    transforms = (
        Transform("kiwi_rf_chain", "partial", "independent antennas/front-ends feed common Kiwi ADC/DDC design"),
        Transform("iq_tuning", "known_conditioned", "the predeclared live scout picks an acquisition band; one later pair is calibrated"),
        Transform("gnss_timestamp", "partial", "seconds-of-week is real; absolute GPS week is inferred from arrival"),
        Transform("continuity_audit", "known", "invalid/overflow blocks split segments and are never interpolated across"),
        Transform("targetless_stft_region", "known_lossy", "phase is discarded; station log power is mapped to a common event-time/RF grid and robustly normalized", conditioning_roots[1:]),
        Transform("in_session_nulls", "known", "the complete region selector is repeated at frozen wrong-time and wrong-frequency shifts", conditioning_roots[1:]),
    )
    receipt = ConstraintReceipt(
        branch="dual-kiwi",
        event_start=overlap_start,
        event_end=overlap_end,
        constraints=constraints,
        transforms=transforms,
        measurement_roots=measurement_roots,
        model_roots=conditioning_roots,
        artifact_hashes=(_capture_hash(left), _capture_hash(right)),
        caveats=(
            "the acquisition center and selected region are controls/observables, never identity evidence",
            "HF multipath, selective fading, polarization, path delay, Doppler, and local interference can decorrelate one real emitter",
            "two unrelated emitters or common impulsive interference can imitate short structural agreement",
            "no time lag is optimized and no TDoA or propagation-delay correction is attempted",
            "shared Kiwi hardware/protocol and scout code remain common conditioning roots",
        ),
    )
    evidence = EvidenceEvent(
        source="dual-kiwi-live-iq",
        arrived_at=max(left.arrived_end, right.arrived_end),
        receipt=receipt,
    )
    belief = contract.snapshot_from_evidence(
        receipt,
        valid_at=now,
        clause_assessments=(
            ClauseAssessment(
                clause="measurement_availability",
                status=(
                    ClauseStatus.SATISFIED
                    if measurement_available
                    else ClauseStatus.UNOBSERVABLE
                ),
                statement=(
                    "Two receivers produced fresh, continuous and defensibly timed simultaneous RF measurements."
                    if measurement_available
                    else "The capture lacks a fresh, continuous, alignable dual-receiver measurement."
                ),
                measurement_roots=measurement_roots if measurement_available else (),
            ),
            ClauseAssessment(
                clause="shared_structure_beyond_null",
                status=(
                    ClauseStatus.SATISFIED
                    if similarity_exceeds_null
                    else (
                        ClauseStatus.UNRESOLVED
                        if measurement_available
                        else ClauseStatus.UNOBSERVABLE
                    )
                ),
                statement=(
                    "One targetless time-frequency region beats both frozen in-session nulls."
                    if similarity_exceeds_null
                    else "The available measurements do not exceed both frozen in-session nulls."
                ),
                measurement_roots=measurement_roots if measurement_available else (),
            ),
            ClauseAssessment(
                clause="common_physical_cause",
                status=(
                    ClauseStatus.UNRESOLVED
                    if measurement_available
                    else ClauseStatus.UNOBSERVABLE
                ),
                statement=(
                    "Similarity beyond the null supports, but does not resolve, a common physical cause under the remaining HF ambiguities."
                    if measurement_available
                    else "A common physical cause cannot be evaluated without usable dual measurements."
                ),
                measurement_roots=measurement_roots if measurement_available else (),
            ),
        ),
        uncertainty=receipt.caveats,
        active_model_roots=conditioning_roots,
    )
    graph = _kiwi_graph(left, right, conditioning_roots)
    return evidence, belief, graph


def run_probe_b(
    contract: DecisionContract,
    *,
    endpoints: tuple[KiwiEndpoint, KiwiEndpoint] = (
        KiwiEndpoint("hooksiel", "dl1bajkiwisdr.ddns.net", 8074),
        KiwiEndpoint("doncaster", "g0ghk.uk", 8050),
    ),
    center_frequency_hz: float | None = None,
    duration_s: float = 8.0,
    plan: ScoutPlan | None = None,
) -> tuple[EvidenceEvent, BeliefSnapshot, CausalGraph]:
    """Scout a frozen center grid, then stop after one calibrated IQ comparison."""

    plan = plan or ScoutPlan()
    if center_frequency_hz is not None:
        plan = replace(plan, center_frequencies_hz=(center_frequency_hz,))
    emit_jsonl("intent_received", contract.intent)
    emit_jsonl(
        "capability_probe",
        {
            "source": "dual-kiwi",
            "endpoints": [endpoint.name for endpoint in endpoints],
            "center_frequency_candidates_hz": plan.center_frequencies_hz,
            "scout_duration_s": plan.scout_duration_s,
            "comparison_duration_s": duration_s,
            "plan_hash": plan.plan_hash,
        },
    )
    scout_candidates: list[tuple[float, float]] = []
    for candidate_frequency_hz in plan.center_frequencies_hz:
        short_captures = capture_dual_kiwi(
            endpoints,
            center_frequency_hz=candidate_frequency_hz,
            duration_s=plan.scout_duration_s,
            max_gps_solution_age_s=plan.max_gps_solution_age_s,
        )
        score, reason = _quick_joint_scout_score(short_captures, plan)
        emit_jsonl(
            "capability_offer" if score is not None else "capability_rejected",
            {
                "source": "dual-kiwi-scout",
                "center_frequency_hz": candidate_frequency_hz,
                "joint_salience": score,
                "reason": reason,
                "plan_hash": plan.plan_hash,
            },
        )
        if score is not None:
            scout_candidates.append((score, candidate_frequency_hz))
    if not scout_candidates:
        raise RuntimeError("no predeclared center produced an auditable dual-station scout")
    _score, winner_frequency_hz = max(
        scout_candidates,
        key=lambda item: (item[0], -item[1]),
    )
    emit_jsonl(
        "lease_acquired",
        {
            "source": "dual-kiwi",
            "center_frequency_hz": winner_frequency_hz,
            "reason": "highest joint salience in frozen center grid",
            "plan_hash": plan.plan_hash,
        },
    )
    captures = capture_dual_kiwi(
        endpoints,
        center_frequency_hz=winner_frequency_hz,
        duration_s=duration_s,
        max_gps_solution_age_s=plan.max_gps_solution_age_s,
    )
    for capture in captures:
        emit_jsonl(
            "evidence_received",
            {
                "receiver": capture.endpoint.name,
                "event_start": capture.event_start,
                "event_end": capture.event_end,
                "arrival_start": capture.arrived_start,
                "arrival_end": capture.arrived_end,
                "sample_rate_hz": capture.sample_rate_hz,
                "sample_count": int(sum(len(block.samples) for block in capture.blocks)),
                "gps_solution_ages_s": sorted({block.gps_solution_age_s for block in capture.blocks}),
                "adc_overflow_blocks": sum(block.adc_overflow for block in capture.blocks),
                "ring_duration_s": (capture.event_end - capture.event_start).total_seconds(),
            },
        )
    now = datetime.now(timezone.utc)
    evidence, belief, graph = compare_rf_structure(
        contract,
        captures[0],
        captures[1],
        now,
        plan=plan,
    )
    emit_jsonl("evidence_assimilated", evidence.receipt)
    emit_jsonl("belief_updated", belief)
    emit_jsonl("causal_graph_snapshot", graph.snapshot())
    return evidence, belief, graph


def _capture_one(
    endpoint: KiwiEndpoint,
    center_frequency_hz: float,
    duration_s: float,
    start_event: Event,
    ready_event: Event,
    max_gps_solution_age_s: int,
) -> KiwiCapture:
    import websocket

    status = fetch_kiwi_status(endpoint)
    ext_api = int(status.get("ext_api", "0") or 0)
    if ext_api <= 0:
        raise RuntimeError(f"{endpoint.name} does not currently offer an external API slot")
    timestamp = (int(time.time()) + (hash(endpoint.name) & 0xFFFF)) & 0xFFFFFFFF
    url = f"ws://{endpoint.host}:{endpoint.port}/{timestamp}/SND"
    ws = websocket.create_connection(
        url,
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
    )
    ws.send("SET auth t=kiwi p=")
    ring = IQBlockRing(max_seconds=duration_s + 1.0)
    sample_rate = 0.0
    capture_started: float | None = None
    arrived_start: datetime | None = None
    arrived_end: datetime | None = None
    last_keepalive = 0.0
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
                    raise RuntimeError(f"{endpoint.name} is busy")
                if params.get("badp") not in (None, "0"):
                    raise RuntimeError(f"{endpoint.name} rejected the public connection: badp={params['badp']}")
                if "audio_rate" in params:
                    ws.send(f"SET AR OK in={int(float(params['audio_rate']))} out=44100")
                if "sample_rate" in params and sample_rate == 0.0:
                    sample_rate = float(params["sample_rate"])
                    frequency_khz = center_frequency_hz / 1000.0
                    for command in (
                        "SET squelch=0 max=0",
                        "SET genattn=0",
                        "SET gen=0 mix=-1",
                        "SET ident_user=Satellite-RF-Observatory_Gate_B",
                        f"SET mod=iq low_cut=-5000 high_cut=5000 freq={frequency_khz:.3f}",
                        "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50",
                        "SET compression=0",
                        "SET keepalive",
                    ):
                        ws.send(command)
            elif tag == b"SND" and sample_rate > 0.0:
                block = _decode_iq_block(body, sample_rate, arrival)
                if (
                    block.gps_timestamp_available
                    and block.gps_solution_age_s <= max_gps_solution_age_s
                ):
                    ready_event.set()
                if start_event.is_set():
                    if capture_started is None:
                        capture_started = time.monotonic()
                        arrived_start = arrival
                    ring.append(block)
                    arrived_end = arrival
                    if time.monotonic() - capture_started >= duration_s:
                        break
            now_monotonic = time.monotonic()
            if now_monotonic - last_keepalive >= 1.0:
                ws.send("SET keepalive")
                last_keepalive = now_monotonic
    finally:
        try:
            ws.close()
        except Exception:
            pass
    blocks = tuple(block for block in ring.snapshot() if block.gps_timestamp_available)
    if not blocks or arrived_start is None or arrived_end is None:
        raise RuntimeError(f"{endpoint.name} returned no GNSS-timestamped IQ blocks")
    return KiwiCapture(
        endpoint=endpoint,
        center_frequency_hz=center_frequency_hz,
        sample_rate_hz=sample_rate,
        status=status,
        blocks=blocks,
        arrived_start=arrived_start,
        arrived_end=arrived_end,
    )


def _decode_iq_block(body: bytes, sample_rate_hz: float, arrival: datetime) -> IQBlock:
    if len(body) < 17:
        raise RuntimeError("short Kiwi SND block")
    flags, sequence = struct.unpack("<BI", body[:5])
    (smeter,) = struct.unpack(">H", body[5:7])
    if not flags & 0x08:
        raise RuntimeError("Kiwi stream is not in stereo IQ mode")
    gps_solution_age_s, _dummy, gps_seconds, gps_nanoseconds = struct.unpack("<BBII", body[7:17])
    interleaved = np.frombuffer(body[17:], dtype=">i2").astype(np.float32)
    if len(interleaved) % 2:
        interleaved = interleaved[:-1]
    samples = (interleaved[0::2] + 1j * interleaved[1::2]).astype(np.complex64) / 32768.0
    event_start = _gps_seconds_of_week_to_utc(
        gps_seconds + 1e-9 * gps_nanoseconds,
        arrival,
    )
    event_end = event_start + timedelta(seconds=len(samples) / sample_rate_hz)
    return IQBlock(
        event_start=event_start,
        event_end=event_end,
        samples=samples,
        rssi_db=0.1 * smeter - 127.0,
        gps_solution_age_s=int(gps_solution_age_s),
        gps_timestamp_available=gps_seconds > 0 and gps_solution_age_s <= 252,
        adc_overflow=bool(flags & 0x02),
        sequence=int(sequence),
        arrived_at=arrival,
    )


def _gps_seconds_of_week_to_utc(seconds_of_week: float, arrival: datetime) -> datetime:
    arrival = arrival.astimezone(timezone.utc)
    elapsed_gps_s = (arrival - GPS_EPOCH).total_seconds() + ASSUMED_GPS_MINUS_UTC_S
    approximate_week = int(elapsed_gps_s // GPS_WEEK_S)
    options = [
        GPS_EPOCH
        + timedelta(seconds=(approximate_week + delta) * GPS_WEEK_S + seconds_of_week - ASSUMED_GPS_MINUS_UTC_S)
        for delta in (-1, 0, 1)
    ]
    return min(options, key=lambda candidate: abs((candidate - arrival).total_seconds()))


def _msg_params(body: bytes) -> dict[str, str | None]:
    text = body.decode("ascii", errors="replace")
    params: dict[str, str | None] = {}
    for token in text.split():
        if "=" in token:
            name, value = token.split("=", 1)
            params[name] = unquote(value)
        else:
            params[token] = None
    return params


def audit_capture(capture: KiwiCapture, plan: ScoutPlan) -> CaptureAudit:
    """Choose one defensible continuous segment and expose every dropped block."""

    if capture.sample_rate_hz <= 0 or not capture.blocks:
        return CaptureAudit(
            False,
            ("capture has no positive sample rate or IQ blocks",),
            (),
            0,
            0,
            len(capture.blocks),
            0.0,
            capture.sample_rate_hz,
            0.0,
            0.0,
            None,
            None,
            None,
        )
    tolerance_s = max(2.0 / capture.sample_rate_hz, 0.001)
    segments: list[list[IQBlock]] = []
    current: list[IQBlock] = []
    sequence_gaps = 0
    timestamp_gaps = 0
    dropped = 0
    arrival_latencies: list[float] = []
    gps_ages: list[int] = []

    def finish_segment() -> None:
        nonlocal current
        if current:
            segments.append(current)
            current = []

    for block in capture.blocks:
        gps_ages.append(block.gps_solution_age_s)
        valid = (
            block.gps_timestamp_available
            and block.gps_solution_age_s <= plan.max_gps_solution_age_s
            and not block.adc_overflow
            and len(block.samples) > 0
        )
        if block.arrived_at is not None:
            latency = (block.arrived_at - block.event_end).total_seconds()
            arrival_latencies.append(latency)
            valid = valid and -tolerance_s <= latency <= plan.max_arrival_latency_s
        if not valid:
            dropped += 1
            finish_segment()
            continue
        if current:
            previous = current[-1]
            expected_sequence = (previous.sequence + 1) & 0xFFFFFFFF
            sequence_ok = block.sequence == expected_sequence
            gap_s = (block.event_start - previous.event_end).total_seconds()
            timestamp_ok = abs(gap_s) <= tolerance_s
            if not sequence_ok or not timestamp_ok:
                sequence_gaps += int(not sequence_ok)
                timestamp_gaps += int(not timestamp_ok)
                finish_segment()
        current.append(block)
    finish_segment()
    if not segments:
        reasons = ("no GNSS-recent, overflow-free continuous IQ segment",)
        return CaptureAudit(
            False,
            reasons,
            (),
            sequence_gaps,
            timestamp_gaps,
            dropped,
            0.0,
            capture.sample_rate_hz,
            0.0,
            0.0,
            _median_or_none(arrival_latencies),
            _percentile_or_none(arrival_latencies, 95),
            max(gps_ages) if gps_ages else None,
        )
    chosen = max(
        segments,
        key=lambda blocks: (
            (blocks[-1].event_end - blocks[0].event_start).total_seconds(),
            len(blocks),
        ),
    )
    duration_s = (chosen[-1].event_end - chosen[0].event_start).total_seconds()
    rate_estimates = []
    for previous, current_block in zip(chosen, chosen[1:]):
        delta_s = (current_block.event_start - previous.event_start).total_seconds()
        if delta_s > 0:
            rate_estimates.append(len(previous.samples) / delta_s)
    effective_rate = (
        float(np.median(rate_estimates))
        if rate_estimates
        else capture.sample_rate_hz
    )
    drift_ppm = 1e6 * (effective_rate - capture.sample_rate_hz) / capture.sample_rate_hz
    cumulative_drift_s = (
        abs(effective_rate - capture.sample_rate_hz)
        / capture.sample_rate_hz
        * duration_s
    )
    hop_s = (plan.nperseg - plan.noverlap) / capture.sample_rate_hz
    reasons_list: list[str] = []
    if duration_s < plan.min_overlap_s:
        reasons_list.append("longest continuous segment is shorter than the frozen minimum")
    if rate_estimates and cumulative_drift_s > hop_s / 2.0:
        reasons_list.append("sample-clock drift exceeds half an STFT hop")
    return CaptureAudit(
        not reasons_list,
        tuple(reasons_list),
        tuple(chosen),
        sequence_gaps,
        timestamp_gaps,
        dropped + sum(len(segment) for segment in segments if segment is not chosen),
        duration_s,
        effective_rate,
        drift_ppm,
        cumulative_drift_s,
        _median_or_none(arrival_latencies),
        _percentile_or_none(arrival_latencies, 95),
        max(gps_ages) if gps_ages else None,
    )


def scout_targetless_region(
    left: KiwiCapture,
    right: KiwiCapture,
    plan: ScoutPlan,
    *,
    audits: tuple[CaptureAudit, CaptureAudit] | None = None,
) -> ScoutResult:
    """Select one simultaneous region and calibrate it against frozen nulls."""

    audits = audits or (audit_capture(left, plan), audit_capture(right, plan))
    if not all(audit.usable for audit in audits):
        return _empty_scout(
            plan,
            audits[0].reasons + audits[1].reasons,
        )
    try:
        (
            left_dynamic,
            right_dynamic,
            frequencies_hz,
            event_times_s,
            time_step_s,
            frequency_step_hz,
        ) = _common_spectral_grids(left, right, audits, plan)
    except ValueError as error:
        return _empty_scout(plan, (str(error),))
    joint = np.minimum(left_dynamic, right_dynamic)
    selected = _select_region(joint, plan.region_shapes)
    if selected is None:
        return _empty_scout(plan, ("no frozen region shape fits the common grid",))

    time_shifts = _frozen_shifts(
        joint.shape[1],
        max(time_frames for _frequency_bins, time_frames in plan.region_shapes),
        plan.null_shift_count,
    )
    frequency_shifts = _frozen_shifts(
        joint.shape[0],
        max(frequency_bins for frequency_bins, _time_frames in plan.region_shapes),
        plan.null_shift_count,
    )
    failures: list[str] = []
    if len(time_shifts) < plan.null_shift_count:
        failures.append("insufficient in-session time shifts for the frozen null")
    if len(frequency_shifts) < plan.null_shift_count:
        failures.append("insufficient in-session frequency shifts for the frozen null")
    time_scores = _shift_null_scores(
        left_dynamic,
        right_dynamic,
        axis=1,
        shifts=time_shifts,
        shapes=plan.region_shapes,
    )
    frequency_scores = _shift_null_scores(
        left_dynamic,
        right_dynamic,
        axis=0,
        shifts=frequency_shifts,
        shapes=plan.region_shapes,
    )
    time_p = _empirical_p(selected.score, time_scores)
    frequency_p = _empirical_p(selected.score, frequency_scores)
    self_consistent, fold_iou = _self_consistency(
        left_dynamic,
        right_dynamic,
        selected,
        plan.region_shapes,
    )
    offset_hz, drift_hz_s, frequency_alignable = _relative_frequency_motion(
        left_dynamic,
        right_dynamic,
        frequencies_hz,
        event_times_s,
        selected,
        frequency_step_hz,
    )
    timing_alignable = max(
        audits[0].cumulative_timing_drift_s,
        audits[1].cumulative_timing_drift_s,
    ) <= time_step_s / 2.0
    alignable = timing_alignable and frequency_alignable
    if not self_consistent:
        failures.append("selected region is not self-consistent across even/odd frames")
    if not alignable:
        failures.append("timestamp/frequency drift is not alignable at scout resolution")
    if time_p is None or time_p > plan.significance_alpha:
        failures.append("time-shift null is not exceeded at the frozen alpha")
    if frequency_p is None or frequency_p > plan.significance_alpha:
        failures.append("frequency-shift null is not exceeded at the frozen alpha")
    if selected.score <= 0:
        failures.append("best simultaneous region is not positively salient at both stations")

    f_start = selected.frequency_start
    f_stop = f_start + selected.frequency_bins
    t_start = selected.time_start
    t_stop = t_start + selected.time_frames
    region = ScoutRegion(
        event_start=datetime.fromtimestamp(
            event_times_s[t_start] - time_step_s / 2.0,
            tz=timezone.utc,
        ),
        event_end=datetime.fromtimestamp(
            event_times_s[t_stop - 1] + time_step_s / 2.0,
            tz=timezone.utc,
        ),
        frequency_low_hz=float(frequencies_hz[f_start] - frequency_step_hz / 2.0),
        frequency_high_hz=float(frequencies_hz[f_stop - 1] + frequency_step_hz / 2.0),
        score=round(selected.score, 6),
        frequency_bins=selected.frequency_bins,
        time_frames=selected.time_frames,
    )
    left_score = float(np.mean(left_dynamic[f_start:f_stop, t_start:t_stop]))
    right_score = float(np.mean(right_dynamic[f_start:f_stop, t_start:t_stop]))
    return ScoutResult(
        region,
        round(selected.score, 6),
        round(left_score, 6),
        round(right_score, 6),
        None if time_p is None else round(time_p, 6),
        None if frequency_p is None else round(frequency_p, 6),
        len(time_scores),
        len(frequency_scores),
        self_consistent,
        None if fold_iou is None else round(fold_iou, 6),
        None if offset_hz is None else round(offset_hz, 3),
        None if drift_hz_s is None else round(drift_hz_s, 6),
        alignable,
        not failures,
        tuple(failures),
        plan.plan_hash,
    )


def _quick_joint_scout_score(
    captures: tuple[KiwiCapture, KiwiCapture],
    plan: ScoutPlan,
) -> tuple[float | None, str]:
    audits = tuple(audit_capture(capture, plan) for capture in captures)
    if not all(audit.usable for audit in audits):
        return None, "; ".join(audits[0].reasons + audits[1].reasons)
    try:
        left, right, _frequencies, _times, _dt, _df = _common_spectral_grids(
            captures[0], captures[1], audits, plan  # type: ignore[arg-type]
        )
    except ValueError as error:
        return None, str(error)
    region = _select_region(np.minimum(left, right), plan.region_shapes)
    if region is None:
        return None, "no frozen region shape fits"
    return round(region.score, 6), "joint targetless salience; not yet calibrated"


def _common_spectral_grids(
    left: KiwiCapture,
    right: KiwiCapture,
    audits: tuple[CaptureAudit, CaptureAudit],
    plan: ScoutPlan,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float, float]:
    overlap_start = max(audits[0].blocks[0].event_start, audits[1].blocks[0].event_start)
    overlap_end = min(audits[0].blocks[-1].event_end, audits[1].blocks[-1].event_end)
    if (overlap_end - overlap_start).total_seconds() < plan.min_overlap_s:
        raise ValueError("not enough common gap-free GNSS overlap")
    left_grid = _spectral_grid(left, audits[0].blocks, overlap_start, overlap_end, plan)
    right_grid = _spectral_grid(right, audits[1].blocks, overlap_start, overlap_end, plan)
    time_step_s = max(left_grid.time_step_s, right_grid.time_step_s)
    frequency_step_hz = max(left_grid.frequency_step_hz, right_grid.frequency_step_hz)
    time_low = max(left_grid.event_times_s[0], right_grid.event_times_s[0])
    time_high = min(left_grid.event_times_s[-1], right_grid.event_times_s[-1])
    frequency_low = max(left_grid.frequencies_hz[0], right_grid.frequencies_hz[0])
    frequency_high = min(left_grid.frequencies_hz[-1], right_grid.frequencies_hz[-1])
    event_times_s = np.arange(time_low, time_high + 0.25 * time_step_s, time_step_s)
    frequencies_hz = np.arange(
        frequency_low,
        frequency_high + 0.25 * frequency_step_hz,
        frequency_step_hz,
    )
    if event_times_s.size < max(shape[1] for shape in plan.region_shapes):
        raise ValueError("common event-time grid is too short for the frozen scout")
    if frequencies_hz.size < max(shape[0] for shape in plan.region_shapes):
        raise ValueError("common RF grid is too narrow for the frozen scout")
    left_log = _interpolate_grid(left_grid, frequencies_hz, event_times_s)
    right_log = _interpolate_grid(right_grid, frequencies_hz, event_times_s)
    left_dynamic = np.clip(
        _robust_z(left_log, axis=1),
        -plan.salience_clip,
        plan.salience_clip,
    )
    right_dynamic = np.clip(
        _robust_z(right_log, axis=1),
        -plan.salience_clip,
        plan.salience_clip,
    )
    return (
        left_dynamic,
        right_dynamic,
        frequencies_hz,
        event_times_s,
        time_step_s,
        frequency_step_hz,
    )


def _spectral_grid(
    capture: KiwiCapture,
    blocks: tuple[IQBlock, ...],
    start: datetime,
    end: datetime,
    plan: ScoutPlan,
) -> _SpectralGrid:
    samples = np.concatenate([block.samples for block in blocks])
    segment_start = blocks[0].event_start
    begin = max(0, int(round((start - segment_start).total_seconds() * capture.sample_rate_hz)))
    finish = min(len(samples), int(round((end - segment_start).total_seconds() * capture.sample_rate_hz)))
    samples = samples[begin:finish]
    if samples.size < plan.nperseg:
        raise ValueError("continuous IQ segment is shorter than one frozen STFT window")
    frequency_offsets, frame_times, spectrum = signal.spectrogram(
        samples,
        fs=capture.sample_rate_hz,
        window="hann",
        nperseg=plan.nperseg,
        noverlap=plan.noverlap,
        detrend=False,
        return_onesided=False,
        scaling="spectrum",
        mode="magnitude",
    )
    frequency_offsets = np.fft.fftshift(frequency_offsets)
    spectrum = np.fft.fftshift(spectrum, axes=0)
    power = np.abs(spectrum) ** 2 + 1e-15
    actual_start = segment_start + timedelta(seconds=begin / capture.sample_rate_hz)
    return _SpectralGrid(
        capture.center_frequency_hz + frequency_offsets,
        actual_start.timestamp() + frame_times,
        10.0 * np.log10(power),
        np.empty((0, 0)),
        (plan.nperseg - plan.noverlap) / capture.sample_rate_hz,
        capture.sample_rate_hz / plan.nperseg,
    )


def _interpolate_grid(
    source: _SpectralGrid,
    target_frequencies_hz: np.ndarray,
    target_times_s: np.ndarray,
) -> np.ndarray:
    by_time = np.vstack(
        [
            np.interp(target_times_s, source.event_times_s, row)
            for row in source.log_power
        ]
    )
    return np.column_stack(
        [
            np.interp(target_frequencies_hz, source.frequencies_hz, by_time[:, index])
            for index in range(by_time.shape[1])
        ]
    )


def _select_region(
    joint: np.ndarray,
    shapes: tuple[tuple[int, int], ...],
) -> _RegionIndex | None:
    best: _RegionIndex | None = None
    for frequency_bins, time_frames in shapes:
        means = _window_means(joint, frequency_bins, time_frames)
        if means.size == 0 or not np.isfinite(means).any():
            continue
        flat_index = int(np.nanargmax(means))
        frequency_start, time_start = np.unravel_index(flat_index, means.shape)
        candidate = _RegionIndex(
            int(frequency_start),
            int(time_start),
            frequency_bins,
            time_frames,
            float(means[frequency_start, time_start]),
        )
        if best is None or candidate.score > best.score:
            best = candidate
    return best


def _window_means(values: np.ndarray, height: int, width: int) -> np.ndarray:
    if values.shape[0] < height or values.shape[1] < width:
        return np.empty((0, 0))
    finite = np.isfinite(values)
    clean = np.where(finite, values, 0.0)
    total = np.pad(clean, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    count = np.pad(finite.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    sums = total[height:, width:] - total[:-height, width:] - total[height:, :-width] + total[:-height, :-width]
    counts = count[height:, width:] - count[:-height, width:] - count[height:, :-width] + count[:-height, :-width]
    return np.where(counts == height * width, sums / (height * width), -np.inf)


def _frozen_shifts(size: int, guard: int, count: int) -> tuple[int, ...]:
    limit = size // 3
    positive = list(range(guard + 1, limit + 1))
    candidates = [-value for value in reversed(positive)] + positive
    if len(candidates) <= count:
        return tuple(candidates)
    indices = np.linspace(0, len(candidates) - 1, count, dtype=int)
    return tuple(candidates[int(index)] for index in indices)


def _shift_null_scores(
    left: np.ndarray,
    right: np.ndarray,
    *,
    axis: int,
    shifts: tuple[int, ...],
    shapes: tuple[tuple[int, int], ...],
) -> tuple[float, ...]:
    scores: list[float] = []
    for shift in shifts:
        shifted = np.roll(right, shift, axis=axis).copy()
        invalid = [slice(None), slice(None)]
        invalid[axis] = slice(0, shift) if shift > 0 else slice(shift, None)
        shifted[tuple(invalid)] = np.nan
        region = _select_region(np.minimum(left, shifted), shapes)
        if region is not None and np.isfinite(region.score):
            scores.append(region.score)
    return tuple(scores)


def _empirical_p(observed: float, null_scores: tuple[float, ...]) -> float | None:
    if not null_scores:
        return None
    return (1.0 + sum(score >= observed for score in null_scores)) / (1.0 + len(null_scores))


def _self_consistency(
    left: np.ndarray,
    right: np.ndarray,
    selected: _RegionIndex,
    shapes: tuple[tuple[int, int], ...],
) -> tuple[bool, float | None]:
    selected_joint = np.minimum(left, right)[
        selected.frequency_start:selected.frequency_start + selected.frequency_bins,
        selected.time_start:selected.time_start + selected.time_frames,
    ]
    even_score = float(np.mean(selected_joint[:, 0::2]))
    odd_score = float(np.mean(selected_joint[:, 1::2]))
    folded_shapes = tuple(
        (frequency_bins, max(2, (time_frames + 1) // 2))
        for frequency_bins, time_frames in shapes
    )
    even = _select_region(np.minimum(left[:, 0::2], right[:, 0::2]), folded_shapes)
    odd = _select_region(np.minimum(left[:, 1::2], right[:, 1::2]), folded_shapes)
    if even is None or odd is None:
        return False, None
    even_set = set(range(even.frequency_start, even.frequency_start + even.frequency_bins))
    odd_set = set(range(odd.frequency_start, odd.frequency_start + odd.frequency_bins))
    union = even_set | odd_set
    iou = len(even_set & odd_set) / len(union) if union else 0.0
    return bool(even_score > 0.0 and odd_score > 0.0 and iou > 0.0), iou


def _relative_frequency_motion(
    left: np.ndarray,
    right: np.ndarray,
    frequencies_hz: np.ndarray,
    event_times_s: np.ndarray,
    selected: _RegionIndex,
    frequency_step_hz: float,
) -> tuple[float | None, float | None, bool]:
    f_slice = slice(selected.frequency_start, selected.frequency_start + selected.frequency_bins)
    t_slice = slice(selected.time_start, selected.time_start + selected.time_frames)
    frequency = frequencies_hz[f_slice]
    left_weights = np.clip(left[f_slice, t_slice], 0.0, None)
    right_weights = np.clip(right[f_slice, t_slice], 0.0, None)
    left_sum = left_weights.sum(axis=0)
    right_sum = right_weights.sum(axis=0)
    valid = (left_sum > 1e-9) & (right_sum > 1e-9)
    if np.count_nonzero(valid) < 3:
        return None, None, False
    left_centroid = (left_weights[:, valid] * frequency[:, None]).sum(axis=0) / left_sum[valid]
    right_centroid = (right_weights[:, valid] * frequency[:, None]).sum(axis=0) / right_sum[valid]
    offsets = left_centroid - right_centroid
    times = event_times_s[t_slice][valid]
    relative_times = times - times[0]
    slope, intercept = np.polyfit(relative_times, offsets, 1)
    residual = offsets - (slope * relative_times + intercept)
    residual_scale = 1.4826 * np.median(np.abs(residual - np.median(residual)))
    total_motion = abs(float(slope)) * max(float(relative_times[-1]), 0.0) + residual_scale
    bandwidth_hz = selected.frequency_bins * frequency_step_hz
    alignable = (
        abs(float(np.median(offsets))) <= bandwidth_hz
        and total_motion <= frequency_step_hz
    )
    return float(np.median(offsets)), float(slope), bool(alignable)


def _robust_z(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    median = np.median(values, axis=axis, keepdims=True)
    mad = np.median(np.abs(values - median), axis=axis, keepdims=True)
    return (values - median) / (1.4826 * mad + 1e-9)


def _empty_scout(plan: ScoutPlan, failures: tuple[str, ...] | list[str]) -> ScoutResult:
    return ScoutResult(
        None,
        None,
        None,
        None,
        None,
        None,
        0,
        0,
        False,
        None,
        None,
        None,
        False,
        False,
        tuple(dict.fromkeys(failures)),
        plan.plan_hash,
    )


def _audit_value(audit: CaptureAudit) -> dict[str, Any]:
    value = asdict(audit)
    value.pop("blocks", None)
    value["selected_block_count"] = len(audit.blocks)
    return value


def _region_value(region: ScoutRegion | None) -> dict[str, Any] | None:
    return None if region is None else asdict(region)


def _median_or_none(values: list[float]) -> float | None:
    return None if not values else float(np.median(values))


def _percentile_or_none(values: list[float], percentile: float) -> float | None:
    return None if not values else float(np.percentile(values, percentile))


def math_isclose(left: float, right: float, *, absolute: float) -> bool:
    return abs(left - right) <= absolute


def _capture_hash(capture: KiwiCapture) -> str:
    digest = sha256()
    for block in capture.blocks:
        digest.update(block.event_start.isoformat().encode())
        digest.update(block.samples.tobytes())
    return digest.hexdigest()


def _kiwi_graph(
    left: KiwiCapture,
    right: KiwiCapture,
    conditioning_roots: tuple[str, ...],
) -> CausalGraph:
    graph = CausalGraph()
    for root in conditioning_roots:
        graph.add_node(root, "model_root", root)
    for capture in (left, right):
        station = f"kiwi:{capture.endpoint.name}"
        evidence = f"evidence:kiwi:{capture.endpoint.name}"
        graph.add_node(station, "measurement_root", f"{capture.endpoint.host}:{capture.endpoint.port}")
        graph.add_node(evidence, "evidence", f"RAM IQ at {capture.center_frequency_hz} Hz")
        graph.add_dependency(evidence, station, "received_by")
        for root in conditioning_roots:
            graph.add_dependency(evidence, root, "conditioned_or_compared_by")
    return graph


def main() -> None:
    contract = DecisionContract(
        intent=Intent(
            question="Are two receivers observing RF structure compatible with the same physical phenomenon in one interval?",
            target=None,
        ),
        clauses=(
            DecisionClause(
                "measurement_availability",
                "two fresh, defensibly timed IQ streams are available",
                ("dual_station_iq", "gnss_event_time"),
                2,
            ),
            DecisionClause(
                "shared_structure_beyond_null",
                "the simultaneous similarity exceeds an in-session null model",
                ("rf_structure",),
                2,
            ),
            DecisionClause(
                "common_physical_cause",
                "one physical cause remains plausible after propagation ambiguities",
                ("causal_support",),
                2,
            ),
        ),
        max_measurement_age_s=30.0,
    )
    run_probe_b(contract)


if __name__ == "__main__":
    main()
