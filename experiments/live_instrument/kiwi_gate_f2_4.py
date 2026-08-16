"""Gate F2.4: one live, same-Kiwi, two-channel DDC intervention.

This is a disposable vertical runner.  It uses only the six Gate F2.2 session
affordances, persists no RF data, freezes at most one plan, performs at most
one post-freeze A1->B->A2 sequence, and then stops.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import math
import re
import struct
from threading import Event
import time
from typing import Callable, Sequence

import numpy as np
from scipy import signal

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_2 as f22
from . import kiwi_gate_f2_3 as f23
from . import kiwi_probe as kiwi
from .models import (
    ClauseAssessment,
    ClauseStatus,
    Constraint,
    ConstraintReceipt,
    DescriptiveSerializationError,
    Transform,
    emit_jsonl,
    strict_json_value,
)


F24_TRANSFORM_VERSION = "gate-f2.4-same-kiwi-ddc-v1"
QUALIFICATION_BUDGET_S = 420.0
RETRY_BUDGET = 2
MAX_RETRY_PER_ENDPOINT = 1
TECHNICAL_DELTA_HZ = 750.0
WATERFALL_FRAMES = 3
WATERFALL_FINE_ZOOM = 5
DISCOVERY_DURATION_S = 4.0
SELECTION_POLICY = "gate-f2.4-stability-guard-fingerprint-before-strength-v1"
IDENT = "Satellite-RF-Observatory_Gate_F2_4"


class PropertyState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class QualificationProperty:
    name: str
    state: PropertyState
    statement: str
    artifact_hashes: tuple[str, ...] = ()


QUALIFICATION_PROPERTIES = (
    "status_access",
    "same_server_instance",
    "two_simultaneous_channel_slots",
    "distinct_channel_ids",
    "simultaneous_IQ_streams",
    "event_time_valid",
    "sequence_ranges_distinct",
    "shared_clock_alignment",
    "reference_channel_continuity",
    "per_channel_retune_available",
    "fixed_channel_unaffected_by_retune",
    "retune_transform_witnessed",
)


CONFIRMATION_CLAUSES = (
    "same_server_instance",
    "simultaneous_channel_branches",
    "distinct_channel_ids",
    "event_time_valid",
    "reference_continuous",
    "perturbed_continuous",
    "axis_orientation_known",
    "transform_ledger_complete",
    "target_detectable_A1",
    "witness_detectable_A1",
    "per_channel_intervention_applied",
    "reference_unaffected",
    "witness_translation_valid_B",
    "target_detectable_on_reference_B",
    "upstream_prediction_match_B",
    "downstream_prediction_match_B",
    "target_recovery_A2",
    "witness_recovery_A2",
    "no_invalidating_gap",
    "no_invalidating_overflow",
)


@dataclass(frozen=True, slots=True)
class BootstrapReceipt:
    created_at: datetime
    candidate_set_hash: str
    candidate_order: tuple[str, ...]
    qualification_budget_s: float
    retry_budget: int
    maximum_retry_per_endpoint: int
    runtime_commit: str
    transform_versions: tuple[str, ...]
    selection_policy: str
    mother_plan_hash: str

    def __post_init__(self) -> None:
        f2._utc(self.created_at)
        expected = ordered_candidate_identities()
        if self.candidate_order != expected or self.candidate_set_hash != candidate_set_hash():
            raise ValueError("Gate F2.4 candidate set and order are immutable")
        if self.qualification_budget_s != QUALIFICATION_BUDGET_S:
            raise ValueError("Gate F2.4 qualification budget changed")
        if self.retry_budget != RETRY_BUDGET or self.maximum_retry_per_endpoint != MAX_RETRY_PER_ENDPOINT:
            raise ValueError("Gate F2.4 retry policy changed")
        if re.fullmatch(r"[0-9a-f]{40}", self.runtime_commit) is None:
            raise ValueError("runtime commit must be a full Git commit")
        if self.selection_policy != SELECTION_POLICY:
            raise ValueError("Gate F2.4 selection policy changed")
        if self.transform_versions != (f2.TRANSFORM_VERSION, F24_TRANSFORM_VERSION):
            raise ValueError("Gate F2.4 transform ledger changed")

    @property
    def receipt_hash(self) -> str:
        return f2._hash(asdict(self))


def ordered_candidates() -> tuple[kiwi.KiwiEndpoint, ...]:
    return tuple(item.endpoint for item in f22.SESSION_AFFORDANCES)


def _endpoint_identity(endpoint: kiwi.KiwiEndpoint) -> str:
    return f"{endpoint.host.lower()}:{endpoint.port}"


def ordered_candidate_identities() -> tuple[str, ...]:
    return tuple(_endpoint_identity(endpoint) for endpoint in ordered_candidates())


def candidate_set_hash() -> str:
    return f2._hash(
        tuple(
            {
                "endpoint": _endpoint_identity(item.endpoint),
                "name": item.endpoint.name,
                "provenance": item.provenance,
            }
            for item in f22.SESSION_AFFORDANCES
        )
    )


def build_bootstrap_receipt(*, runtime_commit: str, created_at: datetime) -> BootstrapReceipt:
    mother = f2.MotherPlan()
    return BootstrapReceipt(
        f2._utc(created_at),
        candidate_set_hash(),
        ordered_candidate_identities(),
        QUALIFICATION_BUDGET_S,
        RETRY_BUDGET,
        MAX_RETRY_PER_ENDPOINT,
        runtime_commit,
        (f2.TRANSFORM_VERSION, F24_TRANSFORM_VERSION),
        SELECTION_POLICY,
        mother.plan_hash,
    )


@dataclass(frozen=True, slots=True)
class ServerInstanceReceipt:
    endpoint_identity: str
    status_hash: str
    stable_metadata: tuple[tuple[str, str], ...]
    reference_handshake_hash: str
    perturbed_handshake_hash: str
    reference_channel_id: str
    perturbed_channel_id: str
    channel_id_basis: str
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class EndpointQualification:
    endpoint: kiwi.KiwiEndpoint
    attempt: int
    properties: tuple[QualificationProperty, ...]
    status_hash: str | None
    artifact_hashes: tuple[str, ...]
    server_instance_receipt: ServerInstanceReceipt | None
    center_a_hz: float | None
    axis_orientation: int | None
    reason: str
    qualified_at: datetime
    expires_at: datetime

    @property
    def multi_channel_demonstrated(self) -> bool:
        return all(
            self.property(name).state is PropertyState.SATISFIED
            for name in ("two_simultaneous_channel_slots", "simultaneous_IQ_streams")
        )

    @property
    def topology_admissible(self) -> bool:
        return all(item.state is PropertyState.SATISFIED for item in self.properties)

    def property(self, name: str) -> QualificationProperty:
        return next(item for item in self.properties if item.name == name)

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.properties)
        if names != QUALIFICATION_PROPERTIES:
            raise ValueError("qualification properties must be complete and ordered")
        if f2._utc(self.expires_at) <= f2._utc(self.qualified_at):
            raise ValueError("qualification receipt TTL must be positive")


@dataclass(frozen=True, slots=True)
class F24SegmentReceipt:
    endpoint_identity: str
    channel_id: str
    channel_role: str
    segment: str
    artifact_hash: str
    byte_count: int
    event_time_start: datetime
    event_time_end: datetime
    sequence_start: int
    sequence_end: int
    sample_rate_hz: float
    declared_tuning_hz: float
    gap_count: int
    overflow_count: int
    transform_version: str = F24_TRANSFORM_VERSION


@dataclass(frozen=True, slots=True)
class F24InterventionReceipt:
    transition: str
    perturbed_channel_id: str
    command_issued_at: datetime
    old_center_hz: float
    requested_new_center_hz: float
    acknowledgement_state: str
    sample_witness_state: str
    reference_command_count: int
    transform_version: str = F24_TRANSFORM_VERSION


@dataclass(frozen=True, slots=True)
class F24Plan:
    endpoint: kiwi.KiwiEndpoint
    server_instance_receipt: ServerInstanceReceipt
    reference_channel_id: str
    perturbed_channel_id: str
    center_a_hz: float
    center_b_hz: float
    delta_f_hz: float
    axis_orientation: int
    expected_translation_hz: float
    target_fingerprint: f2.FeatureFingerprint
    witness_fingerprint: f2.FeatureFingerprint
    discovery_artifact_hashes: tuple[str, ...]
    a1_duration_s: float
    settling_duration_s: float
    b_duration_s: float
    a2_duration_s: float
    prediction_intervals: tuple[tuple[str, float, float], ...]
    wrong_sign_control_hz: float
    wrong_magnitude_control_hz: float
    off_feature_control_hz: float
    thresholds: tuple[tuple[str, float], ...]
    frozen_at: datetime
    expires_at: datetime
    ttl_s: float
    transform_versions: tuple[str, ...]
    artifact_policy: str
    hypotheses: tuple[str, ...] = (
        "H_UPSTREAM_OF_CHANNEL_DDC",
        "H_DOWNSTREAM_CHANNEL_FIXED",
        "H_UNRESOLVED",
    )

    def __post_init__(self) -> None:
        if self.axis_orientation not in (-1, 1):
            raise ValueError("axis orientation must be frozen as +1 or -1")
        if not math.isclose(self.center_b_hz - self.center_a_hz, self.delta_f_hz, abs_tol=1e-9):
            raise ValueError("center B must equal center A plus delta")
        if not math.isclose(
            self.expected_translation_hz,
            self.axis_orientation * (-self.delta_f_hz),
            abs_tol=1e-9,
        ):
            raise ValueError("expected translation has the wrong frozen sign")
        if self.reference_channel_id == self.perturbed_channel_id:
            raise ValueError("reference and perturbed channel ids must differ")
        if self.reference_channel_id != self.server_instance_receipt.reference_channel_id:
            raise ValueError("reference channel is not bound to the server receipt")
        if self.perturbed_channel_id != self.server_instance_receipt.perturbed_channel_id:
            raise ValueError("perturbed channel is not bound to the server receipt")
        if len(self.discovery_artifact_hashes) != 2 or any(
            re.fullmatch(r"[0-9a-f]{64}", item) is None for item in self.discovery_artifact_hashes
        ):
            raise ValueError("plan must bind both ephemeral discovery artifacts")
        if min(self.a1_duration_s, self.b_duration_s, self.a2_duration_s, self.ttl_s) <= 0:
            raise ValueError("plan durations and TTL must be positive")
        if self.settling_duration_s < 0 or f2._utc(self.expires_at) <= f2._utc(self.frozen_at):
            raise ValueError("plan time envelope is invalid")
        tolerance = dict(self.thresholds)["prediction_tolerance_hz"]
        if abs(self.expected_translation_hz) <= 2.0 * tolerance:
            raise ValueError("upstream and downstream prediction intervals overlap")
        minimum = 2.0 * max(
            self.target_fingerprint.bandwidth_hz,
            self.witness_fingerprint.bandwidth_hz,
            self.target_fingerprint.uncertainty_hz,
            self.witness_fingerprint.uncertainty_hz,
            dict(self.thresholds)["spectral_resolution_hz"],
        )
        if abs(self.delta_f_hz) < minimum:
            raise ValueError("delta does not satisfy the detectability envelope")
        if self.transform_versions != (f2.TRANSFORM_VERSION, F24_TRANSFORM_VERSION):
            raise ValueError("plan transform versions changed")
        if "zero RF persistence" not in self.artifact_policy:
            raise ValueError("plan must preserve zero RF persistence")

    @property
    def plan_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F24Result:
    outcome: f23.F23Outcome
    phase: str
    plan_hash: str | None
    endpoint_qualifications: tuple[EndpointQualification, ...]
    clause_assessments: tuple[ClauseAssessment, ...]
    segment_receipts: tuple[F24SegmentReceipt, ...]
    intervention_receipts: tuple[F24InterventionReceipt, ...]
    evidence_receipt: ConstraintReceipt
    observations: tuple[str, ...]
    transform_derivations: tuple[str, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    abstraction_eliminated: str
    shock: str


@dataclass(slots=True)
class _MemoryArtifact:
    capture: kiwi.KiwiCapture
    artifact_hash: str
    byte_count: int
    channel_id: str
    channel_role: str
    segment: str
    declared_tuning_hz: float

    def receipt(self) -> F24SegmentReceipt:
        blocks = self.capture.blocks
        tolerance_s = max(2.0 / self.capture.sample_rate_hz, 0.001)
        gaps = sum(
            current.sequence != ((previous.sequence + 1) & 0xFFFFFFFF)
            or abs((current.event_start - previous.event_end).total_seconds()) > tolerance_s
            for previous, current in zip(blocks, blocks[1:])
        )
        return F24SegmentReceipt(
            _endpoint_identity(self.capture.endpoint),
            self.channel_id,
            self.channel_role,
            self.segment,
            self.artifact_hash,
            self.byte_count,
            self.capture.event_start,
            self.capture.event_end,
            blocks[0].sequence,
            blocks[-1].sequence,
            self.capture.sample_rate_hz,
            self.declared_tuning_hz,
            gaps,
            sum(block.adc_overflow for block in blocks),
        )


@dataclass(slots=True)
class _ChannelConnection:
    endpoint: kiwi.KiwiEndpoint
    role: str
    token: int
    channel_id: str
    channel_id_basis: str
    ws: object
    sample_rate_hz: float
    status: dict[str, str]
    handshake: dict[str, str | None]
    handshake_hash: str
    command_ledger: list[tuple[str, datetime]]

    def close(self) -> None:
        try:
            self.ws.close()  # type: ignore[attr-defined]
        except Exception:
            pass


@dataclass(slots=True)
class _DualConnections:
    reference: _ChannelConnection
    perturbed: _ChannelConnection

    def close(self) -> None:
        self.reference.close()
        self.perturbed.close()


@dataclass(slots=True)
class _DualArtifacts:
    reference: dict[str, _MemoryArtifact]
    perturbed: dict[str, _MemoryArtifact]
    reference_all_blocks: tuple[kiwi.IQBlock, ...]
    perturbed_all_blocks: tuple[kiwi.IQBlock, ...]
    reference_commands: tuple[tuple[str, datetime], ...] = ()
    perturbed_commands: tuple[tuple[str, datetime], ...] = ()

    @property
    def receipts(self) -> tuple[F24SegmentReceipt, ...]:
        items: list[F24SegmentReceipt] = []
        for artifacts in (self.reference, self.perturbed):
            for name in artifacts:
                items.append(artifacts[name].receipt())
        return tuple(items)


@dataclass(slots=True)
class _WaterfallArtifact:
    frames: np.ndarray
    low_hz: float
    high_hz: float
    artifact_hash: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class _QualificationSuccess:
    receipt: EndpointQualification
    center_a_hz: float
    axis_orientation: int


@dataclass(slots=True)
class _RetryState:
    remaining: int = RETRY_BUDGET
    retried_endpoints: set[str] | None = None

    def __post_init__(self) -> None:
        if self.retried_endpoints is None:
            self.retried_endpoints = set()


def _properties(
    states: dict[str, tuple[PropertyState, str]],
    artifact_hashes: tuple[str, ...],
) -> tuple[QualificationProperty, ...]:
    return tuple(
        QualificationProperty(
            name,
            states.get(name, (PropertyState.NOT_EVALUATED, "an upstream qualification property was not satisfied"))[0],
            states.get(name, (PropertyState.NOT_EVALUATED, "an upstream qualification property was not satisfied"))[1],
            artifact_hashes if name in states else (),
        )
        for name in QUALIFICATION_PROPERTIES
    )


def _qualification_receipt(
    endpoint: kiwi.KiwiEndpoint,
    attempt: int,
    states: dict[str, tuple[PropertyState, str]],
    *,
    artifact_hashes: tuple[str, ...] = (),
    status_hash: str | None = None,
    server: ServerInstanceReceipt | None = None,
    center_a_hz: float | None = None,
    axis_orientation: int | None = None,
    reason: str,
) -> EndpointQualification:
    now = datetime.now(timezone.utc)
    return EndpointQualification(
        endpoint,
        attempt,
        _properties(states, artifact_hashes),
        status_hash,
        tuple(dict.fromkeys(artifact_hashes)),
        server,
        center_a_hz,
        axis_orientation,
        reason,
        now,
        now + timedelta(seconds=f2.MotherPlan().offer_ttl_s),
    )


def _stable_server_metadata(status: dict[str, str]) -> tuple[tuple[str, str], ...]:
    keys = (
        "name",
        "sdr_hw",
        "version_maj",
        "version_min",
        "firmware",
        "serial",
        "bandwidth",
    )
    return tuple((key, status[key]) for key in keys if status.get(key))


def _declares_limited_access(status: dict[str, str]) -> bool:
    for key in ("auth", "password", "require_password", "locked", "private"):
        value = str(status.get(key, "")).strip().lower()
        if value not in ("", "0", "false", "no", "none"):
            return True
    return False


def _capture_waterfall(
    endpoint: kiwi.KiwiEndpoint,
    *,
    zoom: int,
    center_hz: float | None,
    frames: int = WATERFALL_FRAMES,
) -> _WaterfallArtifact:
    import websocket

    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, "f24-wf", zoom))) & 0xFFFFFFFF
    ws = websocket.create_connection(
        f"ws://{endpoint.host}:{endpoint.port}/{token}/W/F",
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
    )
    ws.send("SET auth t=kiwi p=")
    captured: list[np.ndarray] = []
    digest = sha256()
    byte_count = 0
    bandwidth_hz = 30_000_000.0
    configured = False
    actual_center = center_hz
    try:
        while len(captured) < frames:
            message = ws.recv()
            if isinstance(message, str):
                message = message.encode("latin-1")
            if not isinstance(message, bytes) or len(message) < 4:
                continue
            tag, body = message[:3], message[3:]
            if tag == b"MSG":
                params = kiwi._msg_params(body[1:])
                if params.get("too_busy") is not None:
                    raise RuntimeError(f"{endpoint.name} waterfall is busy")
                if params.get("badp") not in (None, "0"):
                    raise PermissionError(f"{endpoint.name} rejected public waterfall access")
                if "bandwidth" in params:
                    bandwidth_hz = float(params["bandwidth"])
                if "wf_setup" in params and not configured:
                    if actual_center is None:
                        actual_center = bandwidth_hz / 2.0
                    for command in (
                        f"SET ident_user={IDENT}",
                        f"SET zoom={zoom} cf={actual_center / 1000.0:.6f}",
                        "SET maxdb=-10 mindb=-110",
                        "SET wf_comp=0",
                        "SET wf_speed=1",
                        "SET interp=13",
                        "SET keepalive",
                    ):
                        ws.send(command)
                    configured = True
            elif tag == b"W/F" and configured and len(body) >= 13:
                payload = body[1:]
                _x_bin, _flags_zoom, _sequence = struct.unpack("<III", payload[:12])
                data = payload[12:]
                if len(data) < 512:
                    continue
                digest.update(body)
                byte_count += len(body)
                captured.append(np.frombuffer(data, dtype=np.uint8).astype(float).copy())
            ws.send("SET keepalive")
    finally:
        try:
            ws.close()
        except Exception:
            pass
    if not captured or actual_center is None:
        raise RuntimeError("waterfall returned no usable frames")
    width = min(len(frame) for frame in captured)
    span = bandwidth_hz / (2**zoom)
    low = max(0.0, actual_center - span / 2.0)
    high = min(bandwidth_hz, actual_center + span / 2.0)
    return _WaterfallArtifact(
        np.stack([frame[:width] for frame in captured]),
        low,
        high,
        digest.hexdigest(),
        byte_count,
    )


def _salient_waterfall_frequency(artifact: _WaterfallArtifact) -> float:
    frames = artifact.frames
    median = np.median(frames, axis=0)
    temporal_mad = np.median(np.abs(frames - median[None, :]), axis=0)
    global_median = float(np.median(median))
    global_mad = float(np.median(np.abs(median - global_median)))
    salience = (median - global_median) / max(1.0, 1.4826 * global_mad)
    frequencies = np.linspace(artifact.low_hz, artifact.high_hz, len(median), endpoint=False)
    frequencies += (artifact.high_hz - artifact.low_hz) / len(median) / 2.0
    edge = max(8, len(median) // 50)
    valid = np.ones(len(median), dtype=bool)
    valid[:edge] = False
    valid[-edge:] = False
    peaks, _ = signal.find_peaks(np.where(valid, salience, -1e9), height=2.5, distance=3)
    if len(peaks) == 0:
        raise ValueError("waterfall has no stable salient region under the frozen selector")
    span_mid = (artifact.low_hz + artifact.high_hz) / 2.0
    span_half = (artifact.high_hz - artifact.low_hz) / 2.0
    ranked = sorted(
        (int(index) for index in peaks),
        key=lambda index: (
            -float(temporal_mad[index]),
            min(frequencies[index] - artifact.low_hz, artifact.high_hz - frequencies[index]) / span_half,
            float(salience[index]),
            -abs(float(frequencies[index]) - span_mid),
        ),
        reverse=True,
    )
    return float(frequencies[ranked[0]])


def _automatic_center(endpoint: kiwi.KiwiEndpoint) -> tuple[float, tuple[str, ...]]:
    coarse = _capture_waterfall(endpoint, zoom=0, center_hz=None)
    coarse_center = _salient_waterfall_frequency(coarse)
    fine = _capture_waterfall(endpoint, zoom=WATERFALL_FINE_ZOOM, center_hz=coarse_center)
    center = _salient_waterfall_frequency(fine)
    hashes = (coarse.artifact_hash, fine.artifact_hash)
    del coarse, fine
    return center, hashes


def _initial_channel_commands(center_hz: float) -> tuple[str, ...]:
    return (
        "SET squelch=0 max=0",
        "SET genattn=0",
        "SET gen=0 mix=-1",
        f"SET ident_user={IDENT}",
        f2._tune_command(center_hz),
        "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50",
        "SET compression=0",
        "SET keepalive",
    )


def _open_channel(
    endpoint: kiwi.KiwiEndpoint,
    role: str,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
) -> _ChannelConnection:
    import websocket

    token = (time.time_ns() ^ hash((endpoint.host, endpoint.port, role))) & 0xFFFFFFFF
    ws = websocket.create_connection(
        f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
        enable_multithread=True,
    )
    ws.send("SET auth t=kiwi p=")
    sample_rate = 0.0
    handshake: dict[str, str | None] = {}
    configured = False
    deadline = time.monotonic() + 12.0
    try:
        while time.monotonic() < deadline:
            message = ws.recv()
            arrival = datetime.now(timezone.utc)
            if isinstance(message, str):
                message = message.encode("latin-1")
            if not isinstance(message, bytes) or len(message) < 3:
                continue
            tag, body = message[:3], message[3:]
            if tag == b"MSG":
                params = kiwi._msg_params(body[1:])
                handshake.update(params)
                if params.get("too_busy") is not None:
                    raise RuntimeError(f"{endpoint.name} is busy")
                if params.get("badp") not in (None, "0"):
                    raise PermissionError(f"{endpoint.name} rejected public SND access")
                if "audio_rate" in params:
                    ws.send(f"SET AR OK in={int(float(params['audio_rate']))} out=44100")
                if "sample_rate" in params and not configured:
                    sample_rate = float(params["sample_rate"])
                    for command in _initial_channel_commands(center_hz):
                        ws.send(command)
                    configured = True
            elif tag == b"SND" and sample_rate > 0.0:
                block = kiwi._decode_iq_block(body, sample_rate, arrival)
                if block.gps_timestamp_available and block.gps_solution_age_s <= mother.maximum_gps_solution_age_s:
                    explicit = next(
                        (
                            str(handshake[key])
                            for key in ("rx_chan", "chan", "channel")
                            if handshake.get(key) not in (None, "")
                        ),
                        None,
                    )
                    if explicit is not None:
                        channel_id = f"rx:{explicit}"
                        basis = "explicit server handshake channel identifier"
                    else:
                        channel_id = f"snd-allocation:{token:08x}"
                        basis = "distinct simultaneous SND allocation token plus frozen one-connection/one-RX-channel server audit"
                    return _ChannelConnection(
                        endpoint,
                        role,
                        token,
                        channel_id,
                        basis,
                        ws,
                        sample_rate,
                        status,
                        handshake,
                        f2._hash(handshake),
                        [],
                    )
            ws.send("SET keepalive")
    except Exception:
        try:
            ws.close()
        except Exception:
            pass
        raise
    try:
        ws.close()
    except Exception:
        pass
    raise TimeoutError(f"{endpoint.name} did not reach GNSS IQ readiness")


def _open_dual(
    endpoint: kiwi.KiwiEndpoint,
    center_hz: float,
    status: dict[str, str],
    mother: f2.MotherPlan,
) -> _DualConnections:
    connections: list[_ChannelConnection] = []
    errors: list[Exception] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(_open_channel, endpoint, "reference", center_hz, status, mother),
            pool.submit(_open_channel, endpoint, "perturbed", center_hz, status, mother),
        )
        for future in futures:
            try:
                connections.append(future.result())
            except Exception as error:
                errors.append(error)
    if errors:
        for connection in connections:
            connection.close()
        raise errors[0]
    try:
        dual = _DualConnections(connections[0], connections[1])
        if dual.reference.channel_id == dual.perturbed.channel_id:
            dual.close()
            raise ValueError("server did not expose distinct channel allocations")
        return dual
    except Exception:
        for connection in connections:
            connection.close()
        raise


def _receive_artifacts(
    connection: _ChannelConnection,
    *,
    sequence: bool,
    center_a_hz: float,
    delta_f_hz: float,
    segment_duration_s: float,
    settling_s: float,
    event_not_before: datetime | None,
    start: Event,
    ready: Event,
) -> tuple[dict[str, _MemoryArtifact], tuple[kiwi.IQBlock, ...]]:
    phases = ("A1", "B", "A2") if sequence else ("DISCOVERY_A",)
    digests = {name: sha256() for name in phases}
    raw_bytes = {name: 0 for name in phases}
    blocks_by_phase: dict[str, list[kiwi.IQBlock]] = {name: [] for name in phases}
    all_blocks: list[kiwi.IQBlock] = []
    ready.set()
    if not start.wait(12.0):
        raise TimeoutError("dual capture start barrier timed out")
    started: float | None = None
    sent_b = False
    sent_a2 = False
    last_keepalive = 0.0
    total = segment_duration_s if not sequence else 3.0 * segment_duration_s + 2.0 * settling_s
    while True:
        message = connection.ws.recv()  # type: ignore[attr-defined]
        arrival = datetime.now(timezone.utc)
        now_mono = time.monotonic()
        if isinstance(message, str):
            message = message.encode("latin-1")
        if not isinstance(message, bytes) or len(message) < 3:
            continue
        tag, body = message[:3], message[3:]
        if tag == b"MSG":
            params = kiwi._msg_params(body[1:])
            if params.get("too_busy") is not None:
                raise RuntimeError(f"{connection.endpoint.name} became busy")
            if params.get("badp") not in (None, "0"):
                raise PermissionError("public SND connection was revoked")
        elif tag == b"SND":
            block = kiwi._decode_iq_block(body, connection.sample_rate_hz, arrival)
            if event_not_before is not None and block.event_start < f2._utc(event_not_before):
                continue
            if started is None:
                started = now_mono
            elapsed = now_mono - started
            if not sequence:
                phase = "DISCOVERY_A" if elapsed < total else None
            else:
                if connection.role == "perturbed" and elapsed >= segment_duration_s and not sent_b:
                    command = f2._tune_command(center_a_hz + delta_f_hz)
                    connection.ws.send(command)  # type: ignore[attr-defined]
                    connection.command_ledger.append((command, datetime.now(timezone.utc)))
                    sent_b = True
                second_boundary = 2.0 * segment_duration_s + settling_s
                if connection.role == "perturbed" and elapsed >= second_boundary and not sent_a2:
                    command = f2._tune_command(center_a_hz)
                    connection.ws.send(command)  # type: ignore[attr-defined]
                    connection.command_ledger.append((command, datetime.now(timezone.utc)))
                    sent_a2 = True
                if elapsed < segment_duration_s:
                    phase = "A1"
                elif elapsed < segment_duration_s + settling_s:
                    phase = None
                elif elapsed < 2.0 * segment_duration_s + settling_s:
                    phase = "B"
                elif elapsed < 2.0 * segment_duration_s + 2.0 * settling_s:
                    phase = None
                elif elapsed < total:
                    phase = "A2"
                else:
                    phase = None
            all_blocks.append(block)
            if phase is not None:
                blocks_by_phase[phase].append(block)
                digests[phase].update(body)
                raw_bytes[phase] += len(body)
            if elapsed >= total:
                break
        if now_mono - last_keepalive >= 1.0:
            connection.ws.send("SET keepalive")  # type: ignore[attr-defined]
            last_keepalive = now_mono
    artifacts: dict[str, _MemoryArtifact] = {}
    for phase in phases:
        blocks = tuple(blocks_by_phase[phase])
        if not blocks:
            raise RuntimeError(f"{connection.role} produced no {phase} IQ")
        center = center_a_hz + delta_f_hz if sequence and phase == "B" and connection.role == "perturbed" else center_a_hz
        capture = kiwi.KiwiCapture(
            connection.endpoint,
            center,
            connection.sample_rate_hz,
            connection.status,
            blocks,
            blocks[0].arrived_at or datetime.now(timezone.utc),
            blocks[-1].arrived_at or datetime.now(timezone.utc),
        )
        artifacts[phase] = _MemoryArtifact(
            capture,
            digests[phase].hexdigest(),
            raw_bytes[phase],
            connection.channel_id,
            connection.role,
            phase,
            center,
        )
    return artifacts, tuple(all_blocks)


def _capture_dual(
    dual: _DualConnections,
    *,
    sequence: bool,
    center_a_hz: float,
    delta_f_hz: float,
    segment_duration_s: float,
    settling_s: float,
    event_not_before: datetime | None = None,
) -> _DualArtifacts:
    start = Event()
    ready = (Event(), Event())
    with ThreadPoolExecutor(max_workers=2) as pool:
        ref_future = pool.submit(
            _receive_artifacts,
            dual.reference,
            sequence=sequence,
            center_a_hz=center_a_hz,
            delta_f_hz=delta_f_hz,
            segment_duration_s=segment_duration_s,
            settling_s=settling_s,
            event_not_before=event_not_before,
            start=start,
            ready=ready[0],
        )
        pert_future = pool.submit(
            _receive_artifacts,
            dual.perturbed,
            sequence=sequence,
            center_a_hz=center_a_hz,
            delta_f_hz=delta_f_hz,
            segment_duration_s=segment_duration_s,
            settling_s=settling_s,
            event_not_before=event_not_before,
            start=start,
            ready=ready[1],
        )
        if not ready[0].wait(2.0) or not ready[1].wait(2.0):
            start.set()
            raise TimeoutError("dual streams did not reach the capture barrier")
        start.set()
        reference, reference_blocks = ref_future.result()
        perturbed, perturbed_blocks = pert_future.result()
    return _DualArtifacts(
        reference,
        perturbed,
        reference_blocks,
        perturbed_blocks,
        tuple(dual.reference.command_ledger),
        tuple(dual.perturbed.command_ledger),
    )


def _server_instance_receipt(
    endpoint: kiwi.KiwiEndpoint,
    status: dict[str, str],
    dual: _DualConnections,
) -> ServerInstanceReceipt:
    status_hash = f2._hash(status)
    payload = {
        "endpoint_identity": _endpoint_identity(endpoint),
        "status_hash": status_hash,
        "stable_metadata": _stable_server_metadata(status),
        "reference_handshake_hash": dual.reference.handshake_hash,
        "perturbed_handshake_hash": dual.perturbed.handshake_hash,
        "reference_channel_id": dual.reference.channel_id,
        "perturbed_channel_id": dual.perturbed.channel_id,
        "channel_id_basis": f"reference={dual.reference.channel_id_basis}; perturbed={dual.perturbed.channel_id_basis}",
    }
    return ServerInstanceReceipt(**payload, receipt_hash=f2._hash(payload))


def _integrity(
    blocks: Sequence[kiwi.IQBlock],
    sample_rate_hz: float,
    mother: f2.MotherPlan,
) -> tuple[bool, bool, bool]:
    if not blocks:
        return False, False, False
    tolerance = max(2.0 / sample_rate_hz, 0.001)
    event_valid = all(
        block.gps_timestamp_available
        and block.gps_solution_age_s <= mother.maximum_gps_solution_age_s
        and block.arrived_at is not None
        and -tolerance <= (block.arrived_at - block.event_end).total_seconds() <= mother.maximum_arrival_latency_s
        for block in blocks
    )
    continuous = all(
        current.sequence == ((previous.sequence + 1) & 0xFFFFFFFF)
        and abs((current.event_start - previous.event_end).total_seconds()) <= tolerance
        for previous, current in zip(blocks, blocks[1:])
    )
    no_overflow = not any(block.adc_overflow for block in blocks)
    return event_valid, continuous, no_overflow


def _simultaneous(left: _MemoryArtifact, right: _MemoryArtifact, minimum_s: float = 1.0) -> bool:
    start = max(left.capture.event_start, right.capture.event_start)
    end = min(left.capture.event_end, right.capture.event_end)
    return (end - start).total_seconds() >= minimum_s


def _joint_feature_geometries(
    left: kiwi.KiwiCapture,
    right: kiwi.KiwiCapture,
    mother: f2.MotherPlan,
) -> tuple[tuple[f2._FeatureGeometry, ...], float, float, float]:
    if abs(left.center_frequency_hz - right.center_frequency_hz) > 0.5:
        raise ValueError("simultaneous branches do not share center A")
    lp = f2._capture_profile(left, mother)
    rp = f2._capture_profile(right, mother)
    low = max(float(lp.frequencies_hz[0]), float(rp.frequencies_hz[0]))
    high = min(float(lp.frequencies_hz[-1]), float(rp.frequencies_hz[-1]))
    bin_hz = max(lp.bin_hz, rp.bin_hz)
    count = int(math.floor((high - low) / bin_hz)) + 1
    if count < 64:
        raise ValueError("no resolved common baseband grid")
    frequencies = low + np.arange(count, dtype=float) * bin_hz
    l_med, l_first, l_second = f2._profile_on_grid(lp, frequencies)
    r_med, r_first, r_second = f2._profile_on_grid(rp, frequencies)
    joint = np.minimum(l_med, r_med)
    margin = max(mother.guard_bins, 6)
    valid = np.ones(len(joint), dtype=bool)
    valid[:margin] = False
    valid[-margin:] = False
    valid[np.abs(frequencies) <= mother.guard_bins * bin_hz] = False
    masked = np.where(valid, joint, -1e9)
    peaks, _ = signal.find_peaks(
        masked,
        height=mother.minimum_contrast_db,
        distance=max(3, mother.guard_bins // 2),
    )
    widths = signal.peak_widths(masked, peaks, rel_height=0.5)[0] if len(peaks) else np.asarray([])
    ranked: list[tuple[tuple[float, ...], f2._FeatureGeometry]] = []
    for ordinal, raw_index in enumerate(peaks):
        index = int(raw_index)
        l_patch = f2._normalized_neighbourhood(l_med, index)
        r_patch = f2._normalized_neighbourhood(r_med, index)
        if l_patch is None or r_patch is None:
            continue
        correlation = f2._correlation(l_patch, r_patch)
        first = float(min(l_first[index], r_first[index]))
        second = float(min(l_second[index], r_second[index]))
        if correlation < mother.minimum_fingerprint_correlation:
            continue
        if min(first, second) < mother.minimum_half_contrast_db:
            continue
        geometry = f2._FeatureGeometry(
            float(frequencies[index]),
            float(max(bin_hz, widths[ordinal] * bin_hz)),
            tuple(float((a + b) / 2.0) for a, b in zip(l_patch, r_patch)),
            (first, second, abs(first - second)),
            (min(first, second), float(joint[index])),
            mother.prediction_tolerance_bins * bin_hz,
            correlation,
        )
        edge_guard = min(geometry.baseband_hz - low, high - geometry.baseband_hz)
        rank = (
            correlation,
            -abs(first - second),
            edge_guard,
            min(first, second),
            float(joint[index]),
            -abs(geometry.baseband_hz),
        )
        ranked.append((rank, geometry))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return tuple(item[1] for item in ranked), low, high, bin_hz


def _qualification_witness(
    diagnostic: _DualArtifacts,
    mother: f2.MotherPlan,
    delta_hz: float,
) -> tuple[f2.FeatureFingerprint, int, f2.FeatureMatch, bool]:
    geometries, low, high, _bin_hz = _joint_feature_geometries(
        diagnostic.reference["A1"].capture,
        diagnostic.perturbed["A1"].capture,
        mother,
    )
    profile_b = f2._capture_profile(diagnostic.perturbed["B"].capture, mother)
    reference_profiles = {
        name: f2._capture_profile(diagnostic.reference[name].capture, mother)
        for name in ("A1", "B", "A2")
    }
    perturbed_a2 = f2._capture_profile(diagnostic.perturbed["A2"].capture, mother)
    for geometry in geometries:
        guard = max(geometry.bandwidth_hz, geometry.uncertainty_hz) + mother.guard_bins * _bin_hz
        if not (low + guard <= geometry.baseband_hz - delta_hz <= high - guard):
            continue
        if not (low + guard <= geometry.baseband_hz + delta_hz <= high - guard):
            continue
        provisional = f2._fingerprint_from_geometry(geometry, geometry, diagnostic.reference["A1"].capture.center_frequency_hz, 1)
        try:
            orientation, witness_b = f2.learn_axis_orientation_from_witness(
                provisional,
                profile_b,
                delta_hz,
                geometry.uncertainty_hz,
                mother,
            )
        except ValueError:
            continue
        fingerprint = replace(
            provisional,
            absolute_rf_estimate_a_hz=(
                diagnostic.reference["A1"].capture.center_frequency_hz
                + orientation * geometry.baseband_hz
            ),
        )
        reference_stable = all(
            f2.match_feature(
                profile,
                fingerprint,
                fingerprint.baseband_position_a_hz,
                geometry.uncertainty_hz,
                mother,
                witness=True,
            ).matched
            for profile in reference_profiles.values()
        )
        a2_return = f2.match_feature(
            perturbed_a2,
            fingerprint,
            fingerprint.baseband_position_a_hz,
            geometry.uncertainty_hz,
            mother,
            witness=True,
        ).matched
        if reference_stable and a2_return:
            return fingerprint, orientation, witness_b, True
    raise ValueError("no independent qualification structure uniquely witnesses the retune and fixed reference")


def _qualify_endpoint_once(
    endpoint: kiwi.KiwiEndpoint,
    mother: f2.MotherPlan,
    *,
    attempt: int,
) -> EndpointQualification:
    states: dict[str, tuple[PropertyState, str]] = {}
    hashes: list[str] = []
    status_hash: str | None = None
    dual: _DualConnections | None = None
    try:
        status = kiwi.fetch_kiwi_status(endpoint, timeout_s=5.0)
        status_hash = f2._hash(status)
        hashes.append(status_hash)
        states["status_access"] = (PropertyState.SATISFIED, "direct /status document received and hashed")
        if _declares_limited_access(status):
            states["two_simultaneous_channel_slots"] = (
                PropertyState.UNSATISFIED,
                "endpoint explicitly declares restricted access; no stream was opened",
            )
            return _qualification_receipt(
                endpoint,
                attempt,
                states,
                artifact_hashes=tuple(hashes),
                status_hash=status_hash,
                reason="declared access restriction",
            )
        slots = int(status.get("ext_api", "0") or 0)
        if slots < 2:
            states["two_simultaneous_channel_slots"] = (
                PropertyState.UNSATISFIED,
                f"status exposes {slots} external API slots; two are required",
            )
            return _qualification_receipt(
                endpoint,
                attempt,
                states,
                artifact_hashes=tuple(hashes),
                status_hash=status_hash,
                reason="fewer than two declared public channel slots",
            )
        center, waterfall_hashes = _automatic_center(endpoint)
        hashes.extend(waterfall_hashes)
        dual = _open_dual(endpoint, center, status, mother)
        server = _server_instance_receipt(endpoint, status, dual)
        states["same_server_instance"] = (
            PropertyState.SATISFIED,
            "same endpoint/status instance and two concurrent SND handshakes bound by one server receipt",
        )
        states["two_simultaneous_channel_slots"] = (
            PropertyState.SATISFIED,
            "two public SND connections were simultaneously accepted",
        )
        states["distinct_channel_ids"] = (
            PropertyState.SATISFIED,
            server.channel_id_basis,
        )
        diagnostic = _capture_dual(
            dual,
            sequence=True,
            center_a_hz=center,
            delta_f_hz=TECHNICAL_DELTA_HZ,
            segment_duration_s=mother.diagnostic_segment_s,
            settling_s=mother.settling_s,
        )
        receipts = diagnostic.receipts
        hashes.extend(receipt.artifact_hash for receipt in receipts)
        simultaneous = all(
            _simultaneous(diagnostic.reference[name], diagnostic.perturbed[name])
            for name in ("A1", "B", "A2")
        )
        ref_event, ref_continuous, ref_clean = _integrity(
            diagnostic.reference_all_blocks,
            dual.reference.sample_rate_hz,
            mother,
        )
        pert_event, pert_continuous, pert_clean = _integrity(
            diagnostic.perturbed_all_blocks,
            dual.perturbed.sample_rate_hz,
            mother,
        )
        shared_clock = (
            math.isclose(dual.reference.sample_rate_hz, dual.perturbed.sample_rate_hz, rel_tol=0.0, abs_tol=1e-6)
            and simultaneous
        )
        states["simultaneous_IQ_streams"] = (
            PropertyState.SATISFIED if simultaneous else PropertyState.UNSATISFIED,
            "all A1/B/A2 event-time intervals overlap" if simultaneous else "dual IQ intervals lack required overlap",
        )
        states["event_time_valid"] = (
            PropertyState.SATISFIED if ref_event and pert_event else PropertyState.UNSATISFIED,
            "GNSS sample event time and arrival latency valid on both streams",
        )
        states["sequence_ranges_distinct"] = (
            PropertyState.SATISFIED,
            "separate channel-addressed sequence receipts retained; numeric counter overlap is permitted",
        )
        states["shared_clock_alignment"] = (
            PropertyState.SATISFIED if shared_clock else PropertyState.UNSATISFIED,
            "common sample rate and overlapping GNSS timebase" if shared_clock else "streams cannot be aligned on the shared timebase",
        )
        states["reference_channel_continuity"] = (
            PropertyState.SATISFIED if ref_continuous and ref_clean else PropertyState.UNSATISFIED,
            "reference sequence/event time continuous and overflow-free",
        )
        states["per_channel_retune_available"] = (
            PropertyState.SATISFIED if len(dual.perturbed.command_ledger) == 2 and not dual.reference.command_ledger else PropertyState.UNSATISFIED,
            "only the perturbed connection received A->B->A frequency commands",
        )
        try:
            _witness, orientation, witness_b, fixed = _qualification_witness(
                diagnostic,
                mother,
                TECHNICAL_DELTA_HZ,
            )
        except ValueError as error:
            states["fixed_channel_unaffected_by_retune"] = (
                PropertyState.UNSATISFIED,
                str(error),
            )
            states["retune_transform_witnessed"] = (
                PropertyState.UNSATISFIED,
                "retune metadata was not promoted to sample evidence",
            )
            return _qualification_receipt(
                endpoint,
                attempt,
                states,
                artifact_hashes=tuple(hashes),
                status_hash=status_hash,
                server=server,
                center_a_hz=center,
                reason="sample witness did not close the causal topology",
            )
        states["fixed_channel_unaffected_by_retune"] = (
            PropertyState.SATISFIED if fixed else PropertyState.UNSATISFIED,
            "qualification witness remained fixed on the reference branch through A1/B/A2",
        )
        states["retune_transform_witnessed"] = (
            PropertyState.SATISFIED if witness_b.matched and pert_continuous and pert_clean else PropertyState.UNSATISFIED,
            "independent qualification feature translated uniquely and returned in A2",
        )
        receipt = _qualification_receipt(
            endpoint,
            attempt,
            states,
            artifact_hashes=tuple(hashes),
            status_hash=status_hash,
            server=server,
            center_a_hz=center,
            axis_orientation=orientation,
            reason="same-server two-channel DDC topology qualified",
        )
        del diagnostic
        return receipt
    except Exception as error:
        first_missing = next((name for name in QUALIFICATION_PROPERTIES if name not in states), "status_access")
        states[first_missing] = (
            PropertyState.QUALIFICATION_ERROR,
            f"{type(error).__name__}: {error}",
        )
        error_hash = f2._hash(
            {
                "endpoint": _endpoint_identity(endpoint),
                "attempt": attempt,
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        hashes.append(error_hash)
        return _qualification_receipt(
            endpoint,
            attempt,
            states,
            artifact_hashes=tuple(hashes),
            status_hash=status_hash,
            reason=f"qualification software/transport error: {type(error).__name__}: {error}",
        )
    finally:
        if dual is not None:
            dual.close()


@dataclass(frozen=True, slots=True)
class _PlanGeometry:
    target: f2._FeatureGeometry
    witness: f2._FeatureGeometry
    delta_hz: float
    tolerance_hz: float
    spectral_resolution_hz: float
    wrong_sign_hz: float
    wrong_magnitude_hz: float
    off_feature_hz: float
    rank: tuple[float, ...]


def _select_plan_geometry(
    discovery: _DualArtifacts,
    mother: f2.MotherPlan,
    axis_orientation: int,
) -> _PlanGeometry:
    left = discovery.reference["DISCOVERY_A"].capture
    right = discovery.perturbed["DISCOVERY_A"].capture
    geometries, low, high, bin_hz = _joint_feature_geometries(left, right, mother)
    if len(geometries) < 2:
        raise ValueError("prospective discovery contains fewer than two distinct stable structures")
    candidates: list[_PlanGeometry] = []
    for target in geometries:
        for witness in geometries:
            if target is witness:
                continue
            tolerance = max(target.uncertainty_hz, witness.uncertainty_hz)
            separation = abs(target.baseband_hz - witness.baseband_hz)
            if separation <= 4.0 * tolerance:
                continue
            feature_scale = max(
                target.bandwidth_hz,
                witness.bandwidth_hz,
                bin_hz,
                target.uncertainty_hz,
                witness.uncertainty_hz,
            )
            lower = max(mother.minimum_delta_hz, 2.0 * feature_scale, 5.0 * tolerance)
            target_edge = min(target.baseband_hz - low, high - target.baseband_hz)
            witness_edge = min(witness.baseband_hz - low, high - witness.baseband_hz)
            guard = mother.guard_bins * bin_hz + feature_scale
            upper = min(
                mother.maximum_delta_hz,
                target_edge - guard,
                witness_edge - guard,
                (target_edge - guard) / 2.5,
            )
            if upper < lower:
                continue
            delta = math.floor(upper / bin_hz) * bin_hz
            if delta < lower:
                continue
            translation = axis_orientation * (-delta)
            upstream = target.baseband_hz + translation
            downstream = target.baseband_hz
            wrong_sign = target.baseband_hz - translation
            wrong_magnitude = target.baseband_hz + translation / 2.0
            off_feature = target.baseband_hz + translation * 2.5
            positions = (
                upstream,
                downstream,
                wrong_sign,
                wrong_magnitude,
                off_feature,
                witness.baseband_hz + translation,
            )
            if any(not low + guard <= position <= high - guard for position in positions):
                continue
            if min(
                abs(upstream - downstream),
                abs(upstream - wrong_sign),
                abs(upstream - wrong_magnitude),
                abs(downstream - wrong_magnitude),
            ) <= 2.0 * tolerance:
                continue
            rank = (
                min(target.cross_root_correlation, witness.cross_root_correlation),
                -max(target.morphology_db[2], witness.morphology_db[2]),
                min(target_edge, witness_edge),
                delta / feature_scale,
                separation,
                min(target.contrast_interval_db[0], witness.contrast_interval_db[0]),
                target.contrast_interval_db[1] + witness.contrast_interval_db[1],
            )
            candidates.append(
                _PlanGeometry(
                    target,
                    witness,
                    float(delta),
                    float(tolerance),
                    float(bin_hz),
                    float(wrong_sign),
                    float(wrong_magnitude),
                    float(off_feature),
                    rank,
                )
            )
    if not candidates:
        raise ValueError("no target/witness/delta combination satisfies the frozen detectability envelope")
    return max(candidates, key=lambda item: item.rank)


def freeze_plan(
    endpoint: kiwi.KiwiEndpoint,
    status: dict[str, str],
    dual: _DualConnections,
    discovery: _DualArtifacts,
    axis_orientation: int,
    mother: f2.MotherPlan,
    *,
    frozen_at: datetime,
) -> F24Plan:
    geometry = _select_plan_geometry(discovery, mother, axis_orientation)
    center = discovery.reference["DISCOVERY_A"].capture.center_frequency_hz
    target = f2._fingerprint_from_geometry(geometry.target, geometry.witness, center, axis_orientation)
    witness = f2._fingerprint_from_geometry(geometry.witness, geometry.target, center, axis_orientation)
    translation = axis_orientation * (-geometry.delta_hz)
    upstream = target.baseband_position_a_hz + translation
    downstream = target.baseband_position_a_hz
    witness_b = witness.baseband_position_a_hz + translation
    tolerance = geometry.tolerance_hz
    intervals = (
        ("TARGET_UPSTREAM_B", upstream - tolerance, upstream + tolerance),
        ("TARGET_DOWNSTREAM_B", downstream - tolerance, downstream + tolerance),
        ("WITNESS_UPSTREAM_B", witness_b - tolerance, witness_b + tolerance),
        ("TARGET_A_RETURN", target.baseband_position_a_hz - tolerance, target.baseband_position_a_hz + tolerance),
        ("WITNESS_A_RETURN", witness.baseband_position_a_hz - tolerance, witness.baseband_position_a_hz + tolerance),
    )
    frozen = f2._utc(frozen_at)
    return F24Plan(
        endpoint,
        _server_instance_receipt(endpoint, status, dual),
        dual.reference.channel_id,
        dual.perturbed.channel_id,
        center,
        center + geometry.delta_hz,
        geometry.delta_hz,
        axis_orientation,
        translation,
        target,
        witness,
        (
            discovery.reference["DISCOVERY_A"].artifact_hash,
            discovery.perturbed["DISCOVERY_A"].artifact_hash,
        ),
        mother.confirmation_segment_s,
        mother.settling_s,
        mother.confirmation_segment_s,
        mother.confirmation_segment_s,
        intervals,
        geometry.wrong_sign_hz,
        geometry.wrong_magnitude_hz,
        geometry.off_feature_hz,
        (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_witness_contrast_db", mother.minimum_witness_contrast_db),
            ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
            ("prediction_tolerance_hz", geometry.tolerance_hz),
            ("spectral_resolution_hz", geometry.spectral_resolution_hz),
            ("maximum_arrival_latency_s", mother.maximum_arrival_latency_s),
        ),
        frozen,
        frozen + timedelta(seconds=mother.offer_ttl_s),
        mother.offer_ttl_s,
        (f2.TRANSFORM_VERSION, F24_TRANSFORM_VERSION),
        "SHA-256 before analysis and destruction; zero RF persistence; receipts and hashes only",
    )


def _clause_assessments(
    values: dict[str, bool],
    prerequisites: dict[str, tuple[str, ...]],
    roots: tuple[str, ...],
) -> tuple[ClauseAssessment, ...]:
    statuses: dict[str, ClauseStatus] = {}
    assessments: list[ClauseAssessment] = []
    for name in CONFIRMATION_CLAUSES:
        blocked = any(statuses.get(dependency) is not ClauseStatus.SATISFIED for dependency in prerequisites.get(name, ()))
        if blocked:
            status = ClauseStatus.NOT_EVALUATED
            statement = "upstream causal or observational precondition was not satisfied"
            measurement_roots: tuple[str, ...] = ()
        else:
            status = ClauseStatus.SATISFIED if values[name] else ClauseStatus.UNSATISFIED
            statement = "frozen clause satisfied" if values[name] else "frozen clause not satisfied"
            measurement_roots = roots if values[name] else ()
        statuses[name] = status
        assessments.append(ClauseAssessment(name, status, statement, measurement_roots))
    return tuple(assessments)


def evaluate_confirmation(
    plan: F24Plan,
    confirmation: _DualArtifacts,
    qualification_receipts: tuple[EndpointQualification, ...],
    mother: f2.MotherPlan,
) -> F24Result:
    reference_profiles = {
        name: f2._capture_profile(confirmation.reference[name].capture, mother)
        for name in ("A1", "B", "A2")
    }
    perturbed_profiles = {
        name: f2._capture_profile(confirmation.perturbed[name].capture, mother)
        for name in ("A1", "B", "A2")
    }
    tolerance = dict(plan.thresholds)["prediction_tolerance_hz"]
    target = plan.target_fingerprint
    witness = plan.witness_fingerprint
    target_a1_ref = f2.match_feature(reference_profiles["A1"], target, target.baseband_position_a_hz, tolerance, mother)
    target_a1_pert = f2.match_feature(perturbed_profiles["A1"], target, target.baseband_position_a_hz, tolerance, mother)
    witness_a1_ref = f2.match_feature(reference_profiles["A1"], witness, witness.baseband_position_a_hz, tolerance, mother, witness=True)
    witness_a1_pert = f2.match_feature(perturbed_profiles["A1"], witness, witness.baseband_position_a_hz, tolerance, mother, witness=True)
    target_ref_b = f2.match_feature(reference_profiles["B"], target, target.baseband_position_a_hz, tolerance, mother)
    witness_ref_b = f2.match_feature(reference_profiles["B"], witness, witness.baseband_position_a_hz, tolerance, mother, witness=True)
    expected_witness_b = witness.baseband_position_a_hz + plan.expected_translation_hz
    witness_b = f2.match_feature(perturbed_profiles["B"], witness, expected_witness_b, tolerance, mother, witness=True)
    upstream_b = f2.match_feature(
        perturbed_profiles["B"],
        target,
        target.baseband_position_a_hz + plan.expected_translation_hz,
        tolerance,
        mother,
    )
    downstream_b = f2.match_feature(
        perturbed_profiles["B"], target, target.baseband_position_a_hz, tolerance, mother
    )
    wrong_sign = f2.match_feature(
        perturbed_profiles["B"], target, plan.wrong_sign_control_hz, tolerance, mother
    )
    wrong_magnitude = f2.match_feature(
        perturbed_profiles["B"], target, plan.wrong_magnitude_control_hz, tolerance, mother
    )
    off_feature = f2.match_feature(
        perturbed_profiles["B"], target, plan.off_feature_control_hz, tolerance, mother
    )
    target_a2 = f2.match_feature(
        perturbed_profiles["A2"], target, target.baseband_position_a_hz, tolerance, mother
    )
    witness_a2 = f2.match_feature(
        perturbed_profiles["A2"], witness, witness.baseband_position_a_hz, tolerance, mother, witness=True
    )
    reference_a2_target = f2.match_feature(
        reference_profiles["A2"], target, target.baseband_position_a_hz, tolerance, mother
    )
    reference_a2_witness = f2.match_feature(
        reference_profiles["A2"], witness, witness.baseband_position_a_hz, tolerance, mother, witness=True
    )
    reference_blocks = confirmation.reference_all_blocks
    perturbed_blocks = confirmation.perturbed_all_blocks
    ref_event, ref_continuous, ref_clean = _integrity(reference_blocks, confirmation.reference["A1"].capture.sample_rate_hz, mother)
    pert_event, pert_continuous, pert_clean = _integrity(perturbed_blocks, confirmation.perturbed["A1"].capture.sample_rate_hz, mother)
    simultaneous = all(
        _simultaneous(confirmation.reference[name], confirmation.perturbed[name])
        for name in ("A1", "B", "A2")
    )
    prospective_event_time = (
        min(
            confirmation.reference["A1"].capture.event_start,
            confirmation.perturbed["A1"].capture.event_start,
        )
        >= plan.frozen_at
        and max(
            confirmation.reference["A2"].capture.event_end,
            confirmation.perturbed["A2"].capture.event_end,
        )
        <= plan.expires_at
    )
    qualification = next(item for item in reversed(qualification_receipts) if item.topology_admissible)
    reference_unaffected = (
        witness_a1_ref.matched
        and witness_ref_b.matched
        and reference_a2_witness.matched
    )
    controls_exclusive = not (wrong_sign.matched or wrong_magnitude.matched or off_feature.matched)
    roots = (
        f"kiwi:{_endpoint_identity(plan.endpoint)}:channel:{plan.reference_channel_id}",
        f"kiwi:{_endpoint_identity(plan.endpoint)}:channel:{plan.perturbed_channel_id}",
    )
    values = {
        "same_server_instance": qualification.property("same_server_instance").state is PropertyState.SATISFIED,
        "simultaneous_channel_branches": simultaneous,
        "distinct_channel_ids": plan.reference_channel_id != plan.perturbed_channel_id,
        "event_time_valid": ref_event and pert_event and prospective_event_time,
        "reference_continuous": ref_continuous,
        "perturbed_continuous": pert_continuous,
        "axis_orientation_known": plan.axis_orientation in (-1, 1),
        "transform_ledger_complete": plan.transform_versions == (f2.TRANSFORM_VERSION, F24_TRANSFORM_VERSION),
        "target_detectable_A1": target_a1_ref.matched and target_a1_pert.matched,
        "witness_detectable_A1": witness_a1_ref.matched and witness_a1_pert.matched,
        "per_channel_intervention_applied": (
            not confirmation.reference_commands and len(confirmation.perturbed_commands) == 2
        ),
        "reference_unaffected": reference_unaffected,
        "witness_translation_valid_B": witness_b.matched,
        "target_detectable_on_reference_B": target_ref_b.matched,
        "upstream_prediction_match_B": upstream_b.matched and controls_exclusive,
        "downstream_prediction_match_B": downstream_b.matched and controls_exclusive,
        "target_recovery_A2": target_a2.matched and reference_a2_target.matched,
        "witness_recovery_A2": witness_a2.matched and reference_a2_witness.matched,
        "no_invalidating_gap": ref_continuous and pert_continuous,
        "no_invalidating_overflow": ref_clean and pert_clean,
    }
    prerequisites = {
        "simultaneous_channel_branches": ("same_server_instance",),
        "distinct_channel_ids": ("simultaneous_channel_branches",),
        "event_time_valid": ("distinct_channel_ids",),
        "reference_continuous": ("event_time_valid",),
        "perturbed_continuous": ("event_time_valid",),
        "axis_orientation_known": ("event_time_valid",),
        "transform_ledger_complete": ("axis_orientation_known",),
        "target_detectable_A1": ("reference_continuous", "perturbed_continuous"),
        "witness_detectable_A1": ("reference_continuous", "perturbed_continuous"),
        "per_channel_intervention_applied": ("transform_ledger_complete", "witness_detectable_A1"),
        "reference_unaffected": ("per_channel_intervention_applied",),
        "witness_translation_valid_B": ("per_channel_intervention_applied", "reference_unaffected"),
        "target_detectable_on_reference_B": ("reference_unaffected", "target_detectable_A1"),
        "upstream_prediction_match_B": ("witness_translation_valid_B", "target_detectable_on_reference_B"),
        "downstream_prediction_match_B": ("witness_translation_valid_B", "target_detectable_on_reference_B"),
        "target_recovery_A2": ("witness_translation_valid_B",),
        "witness_recovery_A2": ("witness_translation_valid_B",),
        "no_invalidating_gap": ("event_time_valid",),
        "no_invalidating_overflow": ("event_time_valid",),
    }
    assessments = _clause_assessments(values, prerequisites, roots)
    status = {item.clause: item.status for item in assessments}
    intervention_valid = (
        status["reference_unaffected"] is ClauseStatus.SATISFIED
        and status["witness_translation_valid_B"] is ClauseStatus.SATISFIED
    )
    detectable = (
        status["target_detectable_on_reference_B"] is ClauseStatus.SATISFIED
        and status["no_invalidating_gap"] is ClauseStatus.SATISFIED
        and status["no_invalidating_overflow"] is ClauseStatus.SATISFIED
    )
    recovered = (
        status["target_recovery_A2"] is ClauseStatus.SATISFIED
        and status["witness_recovery_A2"] is ClauseStatus.SATISFIED
    )
    upstream = status["upstream_prediction_match_B"] is ClauseStatus.SATISFIED
    downstream = status["downstream_prediction_match_B"] is ClauseStatus.SATISFIED
    if not intervention_valid:
        outcome = f23.F23Outcome.INTERVENTION_INVALID
        authorised = ("the frozen intervention was not valid for a coordinate-frame decision",)
    elif not detectable:
        outcome = f23.F23Outcome.NOT_DETECTABLE
        authorised = ("the target receipt did not preserve the frozen detectability envelope",)
    elif upstream and not downstream and recovered:
        outcome = f23.F23Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED
        authorised = ("feature upstream of the per-channel DDC boundary",)
    elif downstream and not upstream and recovered:
        outcome = f23.F23Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED
        authorised = ("feature remained fixed in the perturbed channel baseband frame",)
    else:
        outcome = f23.F23Outcome.AMBIGUOUS
        authorised = ("neither frozen DDC-boundary hypothesis was uniquely supported",)
    receipts = confirmation.receipts
    commands = confirmation.perturbed_commands[-2:]
    interventions = (
        (
            F24InterventionReceipt(
                "A_TO_B",
                plan.perturbed_channel_id,
                commands[0][1],
                plan.center_a_hz,
                plan.center_b_hz,
                "NOT_AVAILABLE_IN_KIWI_PROTOCOL",
                "WITNESSED_IN_SAMPLES" if witness_b.matched else "UNRESOLVED",
                len(confirmation.reference_commands),
            ),
            F24InterventionReceipt(
                "B_TO_A",
                plan.perturbed_channel_id,
                commands[1][1],
                plan.center_b_hz,
                plan.center_a_hz,
                "NOT_AVAILABLE_IN_KIWI_PROTOCOL",
                "WITNESSED_IN_SAMPLES" if witness_a2.matched else "UNRESOLVED",
                len(confirmation.reference_commands),
            ),
        )
        if len(commands) == 2
        else ()
    )
    event_start = min(item.event_time_start for item in receipts)
    event_end = max(item.event_time_end for item in receipts)
    evidence = ConstraintReceipt(
        "gate-f2.4-same-kiwi-channel-ddc",
        event_start,
        event_end,
        tuple(
            Constraint(item.clause, "clause_status", item.status, None, item.statement, "frozen Gate F2.4 plan")
            for item in assessments
        )
        + (
            Constraint(
                "frozen_negative_controls",
                "exclusive",
                controls_exclusive,
                None,
                "wrong-sign, wrong-magnitude and off-feature controls must not match",
                "frozen prediction intervals",
            ),
        ),
        (
            Transform("raw_IQ", "ephemeral_hashed", "raw SND bodies hashed before spectral analysis and destroyed"),
            Transform("baseband_spectrum", "derived", "frozen STFT geometry and local fingerprint"),
            Transform("retune", "sample_witnessed" if witness_b.matched else "unresolved", f2.protocol_audit().exact_verified_point),
            Transform("absolute_RF_coordinate", "derived_after_baseband_match", "never used for free search in B"),
        ),
        roots,
        (f"kiwi-server:{f2.KIWI_SERVER_COMMIT}", f"kiwiclient:{f2.KIWI_CLIENT_COMMIT}"),
        tuple(item.artifact_hash for item in receipts),
        (
            "upstream of channel DDC includes shared front-end, ADC and clock artifacts",
            "no transmitter identity, external-RF origin, geolocation or common cause is inferred",
        ),
    )
    strict_json_value(evidence)
    return F24Result(
        outcome,
        "EXPERIMENT",
        plan.plan_hash,
        qualification_receipts,
        assessments,
        receipts,
        interventions,
        evidence,
        (
            "two simultaneous SND branches from one server instance",
            "GNSS event-time sequence and artifact hashes for A1/B/A2",
            "target and distinct intervention witness evaluated only in frozen intervals",
        ),
        (
            f"expected_translation_hz={plan.expected_translation_hz:.6f}",
            f"axis_orientation={plan.axis_orientation} learned only in qualification",
            "absolute RF coordinates projected only after baseband matching",
        ),
        authorised,
        (
            "external RF proven",
            "transmitter identified",
            "common physical cause confirmed",
            "geolocation or TDoA",
        ),
        "universal independent_hardware_roots requirement",
        "sharing ADC and clock improves the intervention comparison while preserving coherent upstream-artifact ambiguity",
    )


def _terminal_before_plan(
    outcome: f23.F23Outcome,
    phase: str,
    reason: str,
    qualifications: tuple[EndpointQualification, ...],
) -> F24Result:
    now = datetime.now(timezone.utc)
    assessments = tuple(
        ClauseAssessment(name, ClauseStatus.NOT_EVALUATED, "plan freeze was not reached", ())
        for name in CONFIRMATION_CLAUSES
    )
    artifact_hashes = tuple(
        dict.fromkeys(
            artifact_hash
            for qualification in qualifications
            for artifact_hash in qualification.artifact_hashes
        )
    )
    receipt = ConstraintReceipt(
        "gate-f2.4-same-kiwi-channel-ddc",
        now,
        now,
        (
            Constraint("terminal_phase", "stopped_before_plan", phase, None, reason, "Gate F2.4 one-shot policy"),
            Constraint("terminal_outcome", "first_outcome", outcome, None, reason, "Gate F2.4 outcome semantics"),
        ),
        (Transform("qualification", "stopped", reason),),
        (),
        (f"kiwi-server:{f2.KIWI_SERVER_COMMIT}",),
        artifact_hashes,
        ("no prospective A1/B/A2 confirmation samples exist",),
    )
    strict_json_value(receipt)
    return F24Result(
        outcome,
        phase,
        None,
        qualifications,
        assessments,
        (),
        (),
        receipt,
        ("only qualification descriptions, hashes and property assessments exist",),
        ("no DDC-boundary hypothesis was evaluated",),
        (reason,),
        (
            "external RF proven",
            "transmitter identified",
            "either DDC-boundary hypothesis supported",
        ),
        "universal independent_hardware_roots requirement",
        "a candidate endpoint is not a two-channel experimental instrument until the live causal topology is witnessed",
    )


def _postfreeze_failure(
    plan: F24Plan,
    qualifications: tuple[EndpointQualification, ...],
    reason: str,
) -> F24Result:
    now = datetime.now(timezone.utc)
    pre_satisfied = {
        "same_server_instance",
        "simultaneous_channel_branches",
        "distinct_channel_ids",
        "axis_orientation_known",
        "transform_ledger_complete",
    }
    roots = (
        f"kiwi:{_endpoint_identity(plan.endpoint)}:channel:{plan.reference_channel_id}",
        f"kiwi:{_endpoint_identity(plan.endpoint)}:channel:{plan.perturbed_channel_id}",
    )
    assessments = tuple(
        ClauseAssessment(
            name,
            ClauseStatus.SATISFIED if name in pre_satisfied else ClauseStatus.NOT_EVALUATED,
            "satisfied before confirmation" if name in pre_satisfied else "confirmation failed before this clause could be evaluated",
            roots if name in pre_satisfied else (),
        )
        for name in CONFIRMATION_CLAUSES
    )
    receipt = ConstraintReceipt(
        "gate-f2.4-same-kiwi-channel-ddc",
        now,
        now,
        (Constraint("confirmation", "not_detectable", f23.F23Outcome.NOT_DETECTABLE, None, reason, "zero retry after plan freeze"),),
        (Transform("confirmation_stream", "interrupted", reason),),
        (),
        (f"kiwi-server:{f2.KIWI_SERVER_COMMIT}",),
        plan.discovery_artifact_hashes,
        ("no second acquisition, endpoint, frequency or feature is authorised",),
    )
    return F24Result(
        f23.F23Outcome.NOT_DETECTABLE,
        "EXPERIMENT",
        plan.plan_hash,
        qualifications,
        assessments,
        (),
        (),
        receipt,
        ("plan was frozen before confirmation failed",),
        ("no coordinate-frame result was derived",),
        ("confirmation was not detectable under the frozen plan",),
        ("external RF proven", "either DDC-boundary hypothesis supported"),
        "universal independent_hardware_roots requirement",
        "zero post-freeze retry preserves the meaning of a failed prospective window",
    )


def _retryable(receipt: EndpointQualification) -> bool:
    errors = " ".join(
        item.statement for item in receipt.properties if item.state is PropertyState.QUALIFICATION_ERROR
    ).lower()
    if not errors:
        return False
    if any(token in errors for token in ("busy", "rejected", "permission", "restricted", "password")):
        return False
    return any(
        token in errors
        for token in (
            "timeout",
            "timed out",
            "connection",
            "closed",
            "reset",
            "transport",
            "decode",
            "description",
            "serialization",
            "transform",
            "oserror",
            "urlerror",
        )
    )


def _prefreeze_discovery(
    endpoint: kiwi.KiwiEndpoint,
    status: dict[str, str],
    center_hz: float,
    axis_orientation: int,
    mother: f2.MotherPlan,
) -> tuple[_DualConnections, _DualArtifacts, F24Plan]:
    dual = _open_dual(endpoint, center_hz, status, mother)
    try:
        discovery = _capture_dual(
            dual,
            sequence=False,
            center_a_hz=center_hz,
            delta_f_hz=0.0,
            segment_duration_s=DISCOVERY_DURATION_S,
            settling_s=0.0,
        )
        plan = freeze_plan(
            endpoint,
            status,
            dual,
            discovery,
            axis_orientation,
            mother,
            frozen_at=datetime.now(timezone.utc),
        )
        return dual, discovery, plan
    except Exception:
        dual.close()
        raise


def run_once(
    *,
    mother: f2.MotherPlan | None = None,
    runtime_commit: str | None = None,
    sink: Callable[[str], None] = print,
) -> F24Result:
    """Run one Gate F2.4 session, freeze at most one plan and stop once."""

    mother = mother or f2.MotherPlan()
    commit = runtime_commit or f22.runtime_commit()
    bootstrap = build_bootstrap_receipt(runtime_commit=commit, created_at=datetime.now(timezone.utc))
    strict_json_value(bootstrap)
    emit_jsonl(
        "gate_f2_4_bootstrap_frozen",
        {
            "receipt": bootstrap,
            "receipt_hash": bootstrap.receipt_hash,
            "root_topology_requirement": f23.gate_f2_root_topology_requirement(),
            "responsible_access": "one endpoint at a time; at most two simultaneous SND slots; close immediately",
        },
        sink=sink,
    )
    deadline = time.monotonic() + bootstrap.qualification_budget_s
    retries = _RetryState()
    qualifications: list[EndpointQualification] = []
    saw_multi = False
    saw_topology = False
    for endpoint in ordered_candidates():
        if time.monotonic() >= deadline:
            break
        identity = _endpoint_identity(endpoint)
        receipt = _qualify_endpoint_once(endpoint, mother, attempt=0)
        qualifications.append(receipt)
        emit_jsonl("gate_f2_4_endpoint_qualification", receipt, sink=sink)
        if (
            _retryable(receipt)
            and retries.remaining > 0
            and identity not in retries.retried_endpoints  # type: ignore[operator]
        ):
            retries.remaining -= 1
            retries.retried_endpoints.add(identity)  # type: ignore[union-attr]
            emit_jsonl(
                "gate_f2_4_prefreeze_retry",
                {"endpoint": identity, "attempt": 1, "global_retries_remaining": retries.remaining},
                sink=sink,
            )
            receipt = _qualify_endpoint_once(endpoint, mother, attempt=1)
            qualifications.append(receipt)
            emit_jsonl("gate_f2_4_endpoint_qualification", receipt, sink=sink)
        saw_multi = saw_multi or receipt.multi_channel_demonstrated
        if not receipt.topology_admissible:
            continue
        saw_topology = True
        if receipt.center_a_hz is None or receipt.axis_orientation not in (-1, 1):
            continue
        dual: _DualConnections | None = None
        discovery: _DualArtifacts | None = None
        try:
            status = kiwi.fetch_kiwi_status(endpoint, timeout_s=5.0)
            if _declares_limited_access(status) or int(status.get("ext_api", "0") or 0) < 2:
                continue
            dual, discovery, plan = _prefreeze_discovery(
                endpoint,
                status,
                receipt.center_a_hz,
                receipt.axis_orientation,
                mother,
            )
        except ValueError as error:
            emit_jsonl(
                "gate_f2_4_no_falsifiable_intervention_candidate",
                {"endpoint": identity, "reason": str(error)},
                sink=sink,
            )
            continue
        except Exception as error:
            emit_jsonl(
                "gate_f2_4_prefreeze_failure",
                {"endpoint": identity, "error_type": type(error).__name__, "reason": str(error), "retry_authorized": False},
                sink=sink,
            )
            continue
        emit_jsonl(
            "gate_f2_4_plan_frozen",
            {
                "plan": plan,
                "plan_hash": plan.plan_hash,
                "zero_postfreeze_retry": True,
                "selection_policy": bootstrap.selection_policy,
            },
            sink=sink,
        )
        try:
            # Same allocated channels as discovery: their ids are already in plan.
            confirmation = _capture_dual(
                dual,
                sequence=True,
                center_a_hz=plan.center_a_hz,
                delta_f_hz=plan.delta_f_hz,
                segment_duration_s=plan.a1_duration_s,
                settling_s=plan.settling_duration_s,
                event_not_before=plan.frozen_at,
            )
            result = evaluate_confirmation(plan, confirmation, tuple(qualifications), mother)
            del confirmation
        except Exception as error:
            result = _postfreeze_failure(
                plan,
                tuple(qualifications),
                f"single confirmation failed with no retry: {type(error).__name__}: {error}",
            )
        finally:
            if dual is not None:
                dual.close()
            if discovery is not None:
                del discovery
        emit_jsonl("gate_f2_4_first_outcome", result, sink=sink)
        return result

    frozen_qualifications = tuple(qualifications)
    if not saw_multi:
        result = _terminal_before_plan(
            f23.F23Outcome.NO_MULTI_CHANNEL_CAPABILITY,
            "QUALIFICATION",
            "no frozen candidate demonstrated two simultaneous public IQ channels in this session",
            frozen_qualifications,
        )
    elif not saw_topology:
        result = _terminal_before_plan(
            f23.F23Outcome.NO_ADMISSIBLE_CAUSAL_TOPOLOGY,
            "QUALIFICATION",
            "two-stream availability existed but no candidate demonstrated the fixed/perturbed sample-witnessed topology",
            frozen_qualifications,
        )
    else:
        result = _terminal_before_plan(
            f23.F23Outcome.NO_FALSIFIABLE_INTERVENTION,
            "ADMISSION",
            "an admissible two-channel topology existed but no target/witness/delta envelope produced a frozen plan",
            frozen_qualifications,
        )
    emit_jsonl("gate_f2_4_first_outcome", result, sink=sink)
    return result


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
