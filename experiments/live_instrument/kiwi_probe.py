"""Probe B: simultaneous targetless KiwiSDR IQ capture and RF-structure test.

The implementation intentionally knows only the small SND/IQ protocol surface
used by this experiment. It is not a generic Internet source or Kiwi framework.
Samples live in bounded RAM ring buffers and are never written to disk.
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import math
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
) -> tuple[EvidenceEvent, BeliefSnapshot, CausalGraph]:
    """Test same-phenomenon plausibility; equal tuning alone never passes."""

    overlap_start = max(left.event_start, right.event_start)
    overlap_end = min(left.event_end, right.event_end)
    overlap_s = (overlap_end - overlap_start).total_seconds()
    fresh = contract.accepts_age(overlap_end, now)
    gps_recent = all(
        block.gps_timestamp_available and block.gps_solution_age_s <= 30
        for capture in (left, right)
        for block in capture.blocks
    )
    overflow_fractions = tuple(
        sum(block.adc_overflow for block in capture.blocks) / len(capture.blocks)
        for capture in (left, right)
    )
    adc_clean_enough = all(fraction <= 0.05 for fraction in overflow_fractions)
    features = _paired_features(left, right, overlap_start, overlap_end)
    supporting = sum(
        (
            features["envelope_correlation"] >= 0.45,
            features["entropy_correlation"] >= 0.35,
            features["spectral_dynamics_correlation"] >= 0.35,
            features["shared_transient_fraction"] >= 0.05,
        )
    )
    plausible_same_phenomenon = (
        overlap_s >= 2.0
        and gps_recent
        and adc_clean_enough
        and fresh
        and supporting >= 2
        and left.center_frequency_hz == right.center_frequency_hz
    )

    measurement_roots = (
        f"kiwi:{left.endpoint.name}",
        f"kiwi:{right.endpoint.name}",
    )
    conditioning_roots = ("kiwi:shared-hardware-protocol-ddc", "probe-b:stft-feature-code")
    constraints = (
        Constraint("gnss_event_time", "recent_for_all_blocks", gps_recent, None, "solution age must be <=30 s; GPS week is inferred from arrival with a fixed 18 s offset", "Kiwi IQ block headers"),
        Constraint("adc_overflow_fraction", "<=0.05_each", overflow_fractions, "fraction", "the receiver flag detects ADC overload, not every downstream distortion", "Kiwi IQ block flags"),
        Constraint("temporal_overlap", ">=", overlap_s, "s", "block boundary/sample-rate approximation", "GNSS-aligned interval intersection"),
        Constraint("measurement_fresh", "==", fresh, None, "event end, never arrival time", "DecisionContract age rule"),
        Constraint("same_tuned_band", "prerequisite_only", left.center_frequency_hz, "Hz", "receiver oscillators and DDC can differ", "control setting; never sufficient"),
        Constraint("envelope_correlation", ">=0.45_supports", features["envelope_correlation"], None, "HF fading can erase or fabricate envelope similarity", "maximum lagged correlation"),
        Constraint("spectral_entropy_correlation", ">=0.35_supports", features["entropy_correlation"], None, "different SNR/front-ends bias entropy", "maximum lagged correlation"),
        Constraint("spectral_dynamics_correlation", ">=0.35_supports", features["spectral_dynamics_correlation"], None, "frequency-shift search reduces specificity", "robust station-normalized STFT correlation"),
        Constraint("best_frequency_alignment", "estimated", features["best_frequency_shift_hz"], "Hz", "receiver oscillators, propagation and binning are confounded", "bounded shift maximizing dynamic spectral agreement"),
        Constraint("shared_transient_fraction", ">=0.05_supports", features["shared_transient_fraction"], "fraction", "local impulsive noise can overlap by chance", "simultaneous robust envelope excursions"),
        Constraint("same_physical_phenomenon", "plausible_not_proven", plausible_same_phenomenon, None, "no transmitter identity or propagation model", f"{supporting}/4 structural properties support"),
    )
    transforms = (
        Transform("kiwi_rf_chain", "partial", "independent antennas/front-ends feed common Kiwi ADC/DDC design"),
        Transform("iq_tuning", "known_conditioned", "same nominal center and IQ passband; oscillator truth differs"),
        Transform("gnss_timestamp", "partial", "seconds-of-week is real; absolute GPS week is inferred from arrival"),
        Transform("ring_buffer", "known", "bounded RAM only; older blocks are evicted"),
        Transform("stft_features", "known_lossy", "phase is discarded and station spectra are robustly normalized", conditioning_roots[-1:]),
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
            "equal frequency is only a control prerequisite, never a coincidence claim",
            "HF multipath, selective fading, polarization, path delay, Doppler, and local interference can decorrelate one real emitter",
            "two unrelated emitters or common impulsive interference can imitate short structural agreement",
            "unknown transmitter geometry prevents propagation-delay compensation",
            "IQ phase is not comparable across unsynchronized receiver oscillators",
        ),
    )
    evidence = EvidenceEvent(
        source="dual-kiwi-live-iq",
        arrived_at=max(left.arrived_end, right.arrived_end),
        receipt=receipt,
    )
    measurement_available = (
        overlap_s >= 2.0 and gps_recent and adc_clean_enough and fresh
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
                    else ClauseStatus.UNSATISFIED
                ),
                statement=(
                    "Two receivers produced fresh, defensibly timed simultaneous RF measurements."
                    if measurement_available
                    else "The capture lacks enough fresh, defensibly timed dual-receiver measurement."
                ),
                measurement_roots=measurement_roots if measurement_available else (),
            ),
            ClauseAssessment(
                clause="common_physical_cause",
                status=(
                    ClauseStatus.SATISFIED
                    if plausible_same_phenomenon
                    else ClauseStatus.UNRESOLVED
                ),
                statement=(
                    "Temporally aligned RF structure is compatible with one physical phenomenon; identity is neither required nor inferred."
                    if plausible_same_phenomenon
                    else "The available measurements do not resolve whether both receivers observed one physical phenomenon."
                ),
                measurement_roots=measurement_roots,
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
    center_frequency_hz: float = 9_996_000.0,
    duration_s: float = 8.0,
) -> tuple[EvidenceEvent, BeliefSnapshot, CausalGraph]:
    emit_jsonl("intent_received", contract.intent)
    emit_jsonl(
        "capability_probe",
        {
            "source": "dual-kiwi",
            "endpoints": [endpoint.name for endpoint in endpoints],
            "center_frequency_hz": center_frequency_hz,
            "duration_s": duration_s,
        },
    )
    captures = capture_dual_kiwi(
        endpoints,
        center_frequency_hz=center_frequency_hz,
        duration_s=duration_s,
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
    evidence, belief, graph = compare_rf_structure(contract, captures[0], captures[1], now)
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
                    ready_event.set()
            elif tag == b"SND" and sample_rate > 0.0:
                block = _decode_iq_block(body, sample_rate, arrival)
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


def _paired_features(
    left: KiwiCapture,
    right: KiwiCapture,
    overlap_start: datetime,
    overlap_end: datetime,
) -> dict[str, float]:
    left_samples = _trim_to_interval(left, overlap_start, overlap_end)
    right_samples = _trim_to_interval(right, overlap_start, overlap_end)
    left_features = _spectral_features(left_samples, left.sample_rate_hz)
    right_features = _spectral_features(right_samples, right.sample_rate_hz)
    length = min(left_features["envelope"].size, right_features["envelope"].size)
    if length < 8:
        raise ValueError("not enough overlapping spectrogram frames")
    envelope_corr = _max_lag_correlation(left_features["envelope"][:length], right_features["envelope"][:length])
    entropy_corr = _max_lag_correlation(left_features["entropy"][:length], right_features["entropy"][:length])
    left_z = left_features["dynamic"][:, :length]
    right_z = right_features["dynamic"][:, :length]
    bins = min(left_z.shape[0], right_z.shape[0])
    left_z, right_z = left_z[:bins], right_z[:bins]
    spectral_corr, best_shift_bins = _max_spectral_shift_correlation(left_z, right_z)
    shift_resolution_hz = min(left.sample_rate_hz, right.sample_rate_hz) / 512.0
    left_transient = _robust_z(left_features["envelope"][:length]) > 2.0
    right_transient = _robust_z(right_features["envelope"][:length]) > 2.0
    shared_transient = float(np.mean(left_transient & right_transient))
    return {
        "envelope_correlation": round(envelope_corr, 6),
        "entropy_correlation": round(entropy_corr, 6),
        "spectral_dynamics_correlation": round(spectral_corr, 6),
        "best_frequency_shift_hz": round(best_shift_bins * shift_resolution_hz, 3),
        "shared_transient_fraction": round(shared_transient, 6),
    }


def _trim_to_interval(capture: KiwiCapture, start: datetime, end: datetime) -> np.ndarray:
    samples = capture.samples
    begin = max(0, int((start - capture.event_start).total_seconds() * capture.sample_rate_hz))
    finish = min(len(samples), int((end - capture.event_start).total_seconds() * capture.sample_rate_hz))
    return samples[begin:finish]


def _spectral_features(samples: np.ndarray, sample_rate_hz: float) -> dict[str, np.ndarray]:
    _freq, _time, spectrum = signal.spectrogram(
        samples,
        fs=sample_rate_hz,
        window="hann",
        nperseg=512,
        noverlap=384,
        detrend=False,
        return_onesided=False,
        scaling="spectrum",
        mode="magnitude",
    )
    power = np.abs(spectrum) ** 2 + 1e-15
    log_power = 10.0 * np.log10(power)
    dynamic = _robust_z(log_power, axis=1)
    normalized = power / power.sum(axis=0, keepdims=True)
    entropy = -np.sum(normalized * np.log(normalized + 1e-15), axis=0) / math.log(power.shape[0])
    envelope = 10.0 * np.log10(power.sum(axis=0))
    return {"dynamic": dynamic, "entropy": entropy, "envelope": envelope}


def _robust_z(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    median = np.median(values, axis=axis, keepdims=True)
    mad = np.median(np.abs(values - median), axis=axis, keepdims=True)
    return (values - median) / (1.4826 * mad + 1e-9)


def _max_lag_correlation(left: np.ndarray, right: np.ndarray, max_lag: int = 6) -> float:
    scores = []
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            a, b = left[-lag:], right[:lag]
        elif lag > 0:
            a, b = left[:-lag], right[lag:]
        else:
            a, b = left, right
        if len(a) >= 4:
            scores.append(_correlation(a, b))
    return float(max(scores)) if scores else 0.0


def _max_spectral_shift_correlation(
    left: np.ndarray,
    right: np.ndarray,
    max_shift_bins: int = 24,
) -> tuple[float, int]:
    best = (-1.0, 0)
    for shift in range(-max_shift_bins, max_shift_bins + 1):
        if shift < 0:
            first, second = left[-shift:, :], right[:shift, :]
        elif shift > 0:
            first, second = left[:-shift, :], right[shift:, :]
        else:
            first, second = left, right
        if first.shape[0] < 16:
            continue
        score = float(np.nanmedian([
            _correlation(first[:, index], second[:, index])
            for index in range(first.shape[1])
        ]))
        if score > best[0]:
            best = (score, shift)
    return best


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if np.std(left) < 1e-12 or np.std(right) < 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


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
                "common_physical_cause",
                "the simultaneous similarity exceeds an in-session null model",
                ("rf_structure",),
                2,
            ),
        ),
        max_measurement_age_s=30.0,
    )
    run_probe_b(contract)


if __name__ == "__main__":
    main()
