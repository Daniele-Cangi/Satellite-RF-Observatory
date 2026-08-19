"""Gate F2.5.31: open-handle injected A1/B/A2 successor, offline only.

Two injected, already-open SND branches remain owned by one outer scope from
phase-aware setup through relative-time admission, local one-feature discovery
and both command boundaries.  Only a private internal executor can tune the
perturbed branch.  Both sockets close and all decoded IQ is zeroized in the
outer ``finally``.  No connector, public execution surface or live authority
exists.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import inspect
import json
import math
from pathlib import Path
import time
from typing import Sequence

import numpy as np
from scipy import signal

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_7 as f257
from . import kiwi_gate_f2_5_17 as f2517
from . import kiwi_gate_f2_5_20 as f2520
from . import kiwi_gate_f2_5_27 as f2527
from . import kiwi_gate_f2_5_28 as f2528
from . import kiwi_gate_f2_5_29 as f2529
from . import kiwi_gate_f2_5_30 as f2530


TRANSFORM_VERSION = "gate-f2.5.31-open-handle-injected-a1-b-a2-v1"
REVIEWED_F2530_COMMIT = "db57207c9d33225b3a57ec8330afe8ee0cd5f4fc"
REVIEWED_F2530_SOURCE_SHA256 = (
    "ebd18068b8abe6130166f374894a58ebf74530b969273d6e4f0171c619521651"
)
REVIEWED_F2530_ENVELOPE_HASH = f2530.AUDIT_ENVELOPE_HASH
EXPECTED_INTEGRATION_SURFACE_HASH = (
    "4d69b4f34721725d5baa3a326e3afe90c88d83b024b8201460330862bc48cb68"
)
RAW_RF_PERSISTENCE = "ZERO"
PHASE_FRAME_COUNT = 8
TECHNICAL_DELTA_HZ = f24.TECHNICAL_DELTA_HZ
BRANCH_ROLES = ("reference", "perturbed")
PHASE_ORDER = (
    "OPEN_DUAL_SND_HANDLES",
    "RELATIVE_TEMPORAL_ADMISSION",
    "LOCAL_ONE_FEATURE_DISCOVERY",
    "A1_TO_B_BOUNDARY",
    "B_TO_A2_BOUNDARY",
    "PLAN_FREEZE",
    "ONE_CONFIRMATION",
)

_FORBIDDEN_RECEIPT_KEYS = f2528._FORBIDDEN_RECEIPT_KEYS | {
    "socket",
    "payload",
    "raw_bytes",
    "decoded_frames",
}


class F2531Exit(str, Enum):
    OPEN_HANDLE_SUCCESSOR_MATERIALIZED_OFFLINE = (
        "OPEN_HANDLE_SUCCESSOR_MATERIALIZED_OFFLINE"
    )
    SEAL_MISMATCH = "SEAL_MISMATCH"


class PhaseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"
    NOT_EVALUATED = "NOT_EVALUATED"


class Outcome(str, Enum):
    OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE = (
        "OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE"
    )
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    TOPOLOGY_NOT_ADMITTED = "TOPOLOGY_NOT_ADMITTED"
    TEMPORAL_NOT_ADMITTED = "TEMPORAL_NOT_ADMITTED"
    NO_FALSIFIABLE_INTERVENTION = "NO_FALSIFIABLE_INTERVENTION"
    INTERVENTION_INVALID = "INTERVENTION_INVALID"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class _CapabilityRejected(RuntimeError):
    pass


def _strict_hash(value: object) -> str:
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=lambda item: item.value if isinstance(item, Enum) else str(item),
        ).encode("utf-8")
    ).hexdigest()


def _sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("a lowercase SHA-256 string is required")


def _canonical_source_sha256(path: Path) -> str:
    return sha256(path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()).hexdigest()


def current_f2530_source_sha256() -> str:
    return _canonical_source_sha256(
        Path(__file__).resolve().parent / "kiwi_gate_f2_5_30.py"
    )


@dataclass(frozen=True, slots=True)
class F2531Plan:
    reviewed_f2530_commit: str
    reviewed_f2530_source_sha256: str
    reviewed_f2530_envelope_hash: str
    integration_surface_hash: str
    endpoint_identity: str
    center_a_hz: float
    technical_delta_hz: float
    settling_duration_ns: int
    phase_frame_count: int
    temporal_plan_hash: str
    discovery_thresholds: tuple[tuple[str, float], ...]
    owner_scope: str
    retune_executor_scope: str
    socket_close_boundary: str
    public_runtime_overrides: tuple[str, ...]
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        mother = f2.MotherPlan()
        if self.reviewed_f2530_commit != REVIEWED_F2530_COMMIT:
            raise ValueError("reviewed F2.5.30 commit changed")
        if self.reviewed_f2530_source_sha256 != REVIEWED_F2530_SOURCE_SHA256:
            raise ValueError("reviewed F2.5.30 source changed")
        if self.reviewed_f2530_envelope_hash != REVIEWED_F2530_ENVELOPE_HASH:
            raise ValueError("reviewed F2.5.30 envelope changed")
        if self.integration_surface_hash != EXPECTED_INTEGRATION_SURFACE_HASH:
            raise ValueError("open-handle integration surface changed")
        if self.endpoint_identity != f2520.SELECTED_ENDPOINT_IDENTITY:
            raise ValueError("reviewed endpoint identity changed")
        if not math.isclose(
            self.center_a_hz,
            f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            raise ValueError("reviewed bootstrap coordinate changed")
        if self.technical_delta_hz != TECHNICAL_DELTA_HZ:
            raise ValueError("technical retune delta changed")
        if self.settling_duration_ns != round(mother.settling_s * 1_000_000_000):
            raise ValueError("existing settling interval changed")
        if self.phase_frame_count != PHASE_FRAME_COUNT:
            raise ValueError("phase frame count changed")
        if self.temporal_plan_hash != f2527.build_plan().plan_hash:
            raise ValueError("relative-time plan changed")
        if self.discovery_thresholds != (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
            (
                "minimum_fingerprint_correlation",
                mother.minimum_fingerprint_correlation,
            ),
        ):
            raise ValueError("existing discovery thresholds changed")
        if self.owner_scope != "ONE_OUTER_OWNER_FROM_OPEN_THROUGH_B_TO_A2":
            raise ValueError("channel owner scope changed")
        if self.retune_executor_scope != "PRIVATE_PERTURBED_BRANCH_ONLY":
            raise ValueError("retune executor scope changed")
        if self.socket_close_boundary != "OUTER_FINALLY_AFTER_TERMINAL_OUTCOME":
            raise ValueError("socket close boundary changed")
        if self.public_runtime_overrides:
            raise ValueError("public runtime overrides are forbidden")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the successor permits no retry")
        if self.live_execution_authorised:
            raise ValueError("offline successor cannot grant authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2527.TRANSFORM_VERSION,
            f2528.TRANSFORM_VERSION,
            f2529.TRANSFORM_VERSION,
            f2530.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("transform ledger changed")

    @property
    def plan_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class PhaseReceipt:
    phase: str
    state: str
    statement: str
    evidence_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.phase not in PHASE_ORDER:
            raise ValueError("unknown open-handle phase")
        if self.state not in {item.value for item in PhaseState}:
            raise ValueError("unknown phase state")
        for item in self.evidence_hashes:
            _sha256(item)


@dataclass(frozen=True, slots=True)
class BranchOpenReceipt:
    branch_role: str
    state: str
    channel_id: int | None
    sample_rate_hz: float | None
    audio_rate_hz: float | None
    command_hashes: tuple[str, ...]
    incoming_artifact_hashes: tuple[str, ...]
    frame_lease_count: int
    frame_release_count: int
    error_type: str | None
    error_description_hash: str | None

    def __post_init__(self) -> None:
        if self.branch_role not in BRANCH_ROLES:
            raise ValueError("unknown branch role")
        if self.state not in {"HANDLE_OPEN", "CAPABILITY_REJECTED", "QUALIFICATION_ERROR"}:
            raise ValueError("unknown branch-open state")
        if self.frame_lease_count != self.frame_release_count:
            raise ValueError("every received frame lease must be released")
        for item in (
            *self.command_hashes,
            *self.incoming_artifact_hashes,
            self.error_description_hash,
        ):
            if item is not None:
                _sha256(item)
        if self.state == "HANDLE_OPEN":
            if (
                self.channel_id is None
                or self.sample_rate_hz is None
                or self.audio_rate_hz is None
                or self.error_type is not None
                or self.error_description_hash is not None
            ):
                raise ValueError("open handle lacks metadata")
        elif self.error_type is None or self.error_description_hash is None:
            raise ValueError("failed open requires typed description")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class DiscoveryReceipt:
    state: str
    selected_baseband_hz: float | None
    joint_contrast_db: float | None
    first_half_contrast_db: float | None
    second_half_contrast_db: float | None
    cross_branch_correlation: float | None
    input_artifact_hashes: tuple[str, ...]
    threshold_source: str
    physical_hypothesis_state: str

    def __post_init__(self) -> None:
        if self.state not in {"ONE_FEATURE_ADMITTED", "NO_FEATURE_ADMITTED"}:
            raise ValueError("unknown discovery state")
        values = (
            self.selected_baseband_hz,
            self.joint_contrast_db,
            self.first_half_contrast_db,
            self.second_half_contrast_db,
            self.cross_branch_correlation,
        )
        if self.state == "ONE_FEATURE_ADMITTED":
            if any(value is None or not math.isfinite(value) for value in values):
                raise ValueError("admitted discovery requires finite scalars")
        elif any(value is not None for value in values):
            raise ValueError("negative discovery cannot invent feature scalars")
        for item in self.input_artifact_hashes:
            _sha256(item)
        if self.threshold_source != "UNCHANGED_MOTHER_PLAN":
            raise ValueError("discovery thresholds were not inherited")
        if self.physical_hypothesis_state != "NOT_EVALUATED":
            raise ValueError("discovery cannot decide DDC location")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class InternalCommandReceipt:
    transition: str
    command_hash: str
    old_center_hz: float
    requested_center_hz: float
    command_issued_monotonic_ns: int
    settling_complete_monotonic_ns: int
    reference_retune_command_count: int
    perturbed_handle_open_at_send: bool
    executor_scope: str

    def __post_init__(self) -> None:
        if self.transition not in {"A1_TO_B", "B_TO_A2"}:
            raise ValueError("unknown transition")
        _sha256(self.command_hash)
        if not self.command_issued_monotonic_ns < self.settling_complete_monotonic_ns:
            raise ValueError("invalid command chronology")
        if self.reference_retune_command_count != 0:
            raise ValueError("fixed reference branch was retuned")
        if not self.perturbed_handle_open_at_send:
            raise ValueError("retune command requires an open perturbed handle")
        if self.executor_scope != "PRIVATE_PERTURBED_BRANCH_ONLY":
            raise ValueError("retune escaped its private executor")


@dataclass(frozen=True, slots=True)
class SessionContinuityReceipt:
    branch_role: str
    frame_count: int
    sequence_gap_count: int
    timestamp_step_violation_count: int
    maximum_timestamp_step_residual_samples: float
    state: str
    artifact_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.branch_role not in BRANCH_ROLES:
            raise ValueError("unknown branch role")
        if self.state not in {"SATISFIED", "UNSATISFIED"}:
            raise ValueError("unknown continuity state")
        if not math.isfinite(self.maximum_timestamp_step_residual_samples):
            raise ValueError("continuity residual must be finite")
        for item in self.artifact_hashes:
            _sha256(item)


@dataclass(frozen=True, slots=True)
class CleanupReceipt:
    socket_count: int
    socket_close_count: int
    frame_lease_count: int
    frame_release_count: int
    decoded_frame_count: int
    decoded_sample_count: int
    all_iq_zeroized: bool
    transient_raw_references_after_return: int
    owner_closed_in_outer_finally: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.socket_count != self.socket_close_count:
            raise ValueError("both sockets must close")
        if self.frame_lease_count != self.frame_release_count:
            raise ValueError("all frame leases must release")
        if not self.all_iq_zeroized or self.transient_raw_references_after_return:
            raise ValueError("ephemeral RF survived cleanup")
        if not self.owner_closed_in_outer_finally:
            raise ValueError("socket ownership did not reach the outer finally")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2531RunResult:
    plan_hash: str
    outcome: str
    branch_open_receipts: tuple[BranchOpenReceipt, BranchOpenReceipt]
    temporal_admission: f2527.RelativeTimingAdmissionReceipt | None
    discovery: DiscoveryReceipt | None
    command_receipts: tuple[InternalCommandReceipt, ...]
    boundary_receipts: tuple[f2527.BoundaryWitnessReceipt, ...]
    session_continuity: tuple[SessionContinuityReceipt, ...]
    phases: tuple[PhaseReceipt, ...]
    cleanup: CleanupReceipt
    physical_hypothesis_state: str
    live_execution_authorised: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.plan_hash)
        if self.outcome not in {item.value for item in Outcome}:
            raise ValueError("unknown successor outcome")
        if tuple(item.branch_role for item in self.branch_open_receipts) != BRANCH_ROLES:
            raise ValueError("branch receipt order changed")
        if tuple(item.phase for item in self.phases) != PHASE_ORDER:
            raise ValueError("phases must be complete and ordered")
        if self.physical_hypothesis_state != "NOT_EVALUATED":
            raise ValueError("offline lifecycle cannot decide DDC location")
        if self.live_execution_authorised:
            raise ValueError("offline successor cannot grant authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2531Assessment:
    exit: F2531Exit
    plan: F2531Plan | None
    parent_source_hash_matches: bool
    parent_audit_ready: bool
    integration_surface_matches: bool
    one_outer_owner: bool
    internal_retune_only: bool
    no_public_execution_surface: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


@dataclass(slots=True)
class _Handle:
    socket: object = field(repr=False)
    branch_role: str
    channel_id: int
    sample_rate_hz: float
    audio_rate_hz: float
    command_hashes: list[str]
    retune_command_hashes: list[str]
    incoming_hashes: list[str]
    decoded_frames: list[f2528._EphemeralDecodedFrame] = field(repr=False)
    scalar_receipts: list[f2527.ScalarFrameReceipt]
    frame_lease_count: int
    frame_release_count: int
    closed: bool = False


@dataclass(slots=True)
class _OpenAttempt:
    receipt: BranchOpenReceipt
    handle: _Handle | None = field(repr=False)


def _command_hash(command: str) -> str:
    return sha256(command.encode("utf-8")).hexdigest()


def _send(socket: object, command: str, hashes: list[str], *, receipt: str | None = None) -> None:
    socket.send(command)  # type: ignore[attr-defined]
    hashes.append(_command_hash(receipt or command))


def _take_frame(socket: object) -> tuple[bytes, int, str]:
    opcode, frame = socket.recv_data_frame(control_frame=True)  # type: ignore[attr-defined]
    if opcode not in {1, 2} or not hasattr(frame, "take_payload"):
        raise RuntimeError("injected owned data frame required")
    arrival_ns = int(frame.monotonic_arrival_ns)
    payload = frame.take_payload()
    if not frame.released or frame.payload is not None:
        raise RuntimeError("injected frame lease was not released")
    return payload, arrival_ns, sha256(payload).hexdigest()


def _open_handle(socket: object, branch_role: str) -> _OpenAttempt:
    commands: list[str] = []
    incoming: list[str] = []
    release_count = 0
    channel: int | None = None
    sample_rate: float | None = None
    audio_rate: float | None = None
    try:
        socket.settimeout(f2529.FROZEN_CONTROL_TIMEOUT_S)  # type: ignore[attr-defined]
        _send(
            socket,
            f2529.AUTH_COMMAND,
            commands,
            receipt=f2529.AUTH_RECEIPT_COMMAND,
        )
        while channel is None or sample_rate is None or audio_rate is None:
            payload, _arrival, artifact_hash = _take_frame(socket)
            release_count += 1
            incoming.append(artifact_hash)
            if len(payload) < 3 or payload[:3] != b"MSG":
                raise RuntimeError("complete metadata must precede SND")
            fields = f257.decode_allowlisted_server_fields(
                payload[4:].decode("ascii", errors="replace")
            )
            for item in fields:
                if item.name == "badp" and item.state != "OK":
                    raise _CapabilityRejected("server reported badp rejection")
                if item.name == "too_busy":
                    raise _CapabilityRejected("server reported too_busy")
                if item.name == "is_local":
                    if channel is not None and channel != item.channel_id:
                        raise RuntimeError("conflicting channel metadata")
                    channel = item.channel_id
                elif item.name == "sample_rate":
                    sample_rate = item.numeric_value
                elif item.name == "audio_rate":
                    audio_rate = item.numeric_value
            del payload
        assert channel is not None and sample_rate is not None and audio_rate is not None
        setup = f2517.setup_commands(f2520.SELECTED_BOOTSTRAP_CENTER_HZ, audio_rate)
        f2517.validate_setup_commands(
            setup, f2520.SELECTED_BOOTSTRAP_CENTER_HZ, audio_rate
        )
        for command in setup:
            _send(socket, command, commands)
        handle = _Handle(
            socket,
            branch_role,
            channel,
            sample_rate,
            audio_rate,
            commands,
            [],
            incoming,
            [],
            [],
            len(incoming),
            release_count,
        )
        return _OpenAttempt(
            BranchOpenReceipt(
                branch_role,
                "HANDLE_OPEN",
                channel,
                sample_rate,
                audio_rate,
                tuple(commands),
                tuple(incoming),
                len(incoming),
                release_count,
                None,
                None,
            ),
            handle,
        )
    except Exception as error:
        state = (
            "CAPABILITY_REJECTED"
            if isinstance(error, _CapabilityRejected)
            else "QUALIFICATION_ERROR"
        )
        return _OpenAttempt(
            BranchOpenReceipt(
                branch_role,
                state,
                channel,
                sample_rate,
                audio_rate,
                tuple(commands),
                tuple(incoming),
                len(incoming),
                release_count,
                type(error).__name__,
                _strict_hash(
                    {
                        "branch_role": branch_role,
                        "stage": "OPEN_HANDLE",
                        "error_type": type(error).__name__,
                    }
                ),
            ),
            None,
        )


def _decode_next_snd(handle: _Handle) -> f2528._EphemeralDecodedFrame:
    while True:
        payload, arrival_ns, artifact_hash = _take_frame(handle.socket)
        handle.frame_lease_count += 1
        handle.frame_release_count += 1
        handle.incoming_hashes.append(artifact_hash)
        if len(payload) < 3:
            raise RuntimeError("short injected data frame")
        if payload[:3] == b"MSG":
            fields = f257.decode_allowlisted_server_fields(
                payload[4:].decode("ascii", errors="replace")
            )
            if any(
                item.name == "too_busy"
                or (item.name == "badp" and item.state != "OK")
                for item in fields
            ):
                raise _CapabilityRejected("server revoked the open branch")
            del payload
            continue
        transient = f2528.TransientSNDInput(arrival_ns, payload)
        observed = f2528.observe_relative_snd(
            transient,
            endpoint_identity=f2520.SELECTED_ENDPOINT_IDENTITY,
            branch_role=handle.branch_role,
            channel_id=handle.channel_id,
            sample_rate_hz=handle.sample_rate_hz,
        )
        transient.raw_message = b""
        del payload, transient
        if isinstance(observed, f2528.FrameQualificationErrorReceipt):
            raise RuntimeError(f"SND frame qualification failed: {observed.error_type}")
        handle.decoded_frames.append(observed)
        handle.scalar_receipts.append(observed.receipt)
        return observed


def _collect_count(handle: _Handle, count: int) -> tuple[f2528._EphemeralDecodedFrame, ...]:
    return tuple(_decode_next_snd(handle) for _ in range(count))


def _collect_postsettling(
    handle: _Handle,
    settling_complete_ns: int,
    count: int,
) -> tuple[f2528._EphemeralDecodedFrame, ...]:
    selected: list[f2528._EphemeralDecodedFrame] = []
    while len(selected) < count:
        frame = _decode_next_snd(handle)
        if frame.receipt.monotonic_arrival_ns >= settling_complete_ns:
            selected.append(frame)
    return tuple(selected)


def _collect_pair_count(
    reference: _Handle,
    perturbed: _Handle,
    count: int,
) -> tuple[
    tuple[f2528._EphemeralDecodedFrame, ...],
    tuple[f2528._EphemeralDecodedFrame, ...],
]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        left = executor.submit(_collect_count, reference, count)
        right = executor.submit(_collect_count, perturbed, count)
        return left.result(), right.result()


def _collect_pair_postsettling(
    reference: _Handle,
    perturbed: _Handle,
    settling_complete_ns: int,
    count: int,
) -> tuple[
    tuple[f2528._EphemeralDecodedFrame, ...],
    tuple[f2528._EphemeralDecodedFrame, ...],
]:
    with ThreadPoolExecutor(max_workers=2) as executor:
        left = executor.submit(
            _collect_postsettling, reference, settling_complete_ns, count
        )
        right = executor.submit(
            _collect_postsettling, perturbed, settling_complete_ns, count
        )
        return left.result(), right.result()


def _spectral_residual(
    frames: Sequence[f2528._EphemeralDecodedFrame],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mother = f2.MotherPlan()
    samples = np.concatenate([item.samples for item in frames])
    if samples.size < 2 * mother.nperseg:
        raise ValueError("discovery samples are shorter than two STFT windows")
    frequencies, _times, spectrum = signal.stft(
        samples,
        fs=frames[0].receipt.sample_rate_hz,
        window="hann",
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        return_onesided=False,
        boundary=None,
        padded=False,
    )
    frequencies = np.fft.fftshift(frequencies)
    power = np.fft.fftshift(
        10.0 * np.log10(np.maximum(np.abs(spectrum) ** 2, 1e-15)),
        axes=0,
    )
    median = np.median(power, axis=1)
    half = max(1, power.shape[1] // 2)
    first = np.median(power[:, :half], axis=1)
    second = np.median(power[:, half:], axis=1)
    kernel = min(63, len(median) // 2 * 2 - 1)
    kernel = max(5, kernel if kernel % 2 else kernel - 1)
    return (
        frequencies.astype(float),
        (median - signal.medfilt(median, kernel_size=kernel)).astype(float),
        (first - signal.medfilt(first, kernel_size=kernel)).astype(float),
        (second - signal.medfilt(second, kernel_size=kernel)).astype(float),
    )


def _discover_one_feature(
    reference: Sequence[f2528._EphemeralDecodedFrame],
    perturbed: Sequence[f2528._EphemeralDecodedFrame],
) -> DiscoveryReceipt:
    mother = f2.MotherPlan()
    hashes = tuple(
        item.receipt.artifact_hash_before_analysis
        for item in tuple(reference) + tuple(perturbed)
    )
    left_f, left, left_first, left_second = _spectral_residual(reference)
    right_f, right, right_first, right_second = _spectral_residual(perturbed)
    if not np.allclose(left_f, right_f, rtol=0.0, atol=1e-9):
        raise ValueError("discovery frequency grids differ")
    joint = np.minimum(left, right)
    valid = np.ones(joint.size, dtype=bool)
    margin = max(mother.guard_bins, 6)
    valid[:margin] = False
    valid[-margin:] = False
    bin_hz = abs(float(np.median(np.diff(left_f))))
    valid[np.abs(left_f) <= mother.guard_bins * bin_hz] = False
    candidates, _properties = signal.find_peaks(
        np.where(valid, joint, -1e9),
        height=mother.minimum_contrast_db,
        distance=max(3, mother.guard_bins // 2),
    )
    ranked: list[tuple[tuple[float, ...], tuple[float, ...]]] = []
    for raw_index in candidates:
        index = int(raw_index)
        left_patch = f2._normalized_neighbourhood(left, index)
        right_patch = f2._normalized_neighbourhood(right, index)
        if left_patch is None or right_patch is None:
            continue
        correlation = f2._correlation(left_patch, right_patch)
        first = float(min(left_first[index], right_first[index]))
        second = float(min(left_second[index], right_second[index]))
        contrast = float(joint[index])
        if (
            correlation < mother.minimum_fingerprint_correlation
            or min(first, second) < mother.minimum_half_contrast_db
        ):
            continue
        ranked.append(
            (
                (correlation, min(first, second), contrast, -abs(float(left_f[index]))),
                (float(left_f[index]), contrast, first, second, correlation),
            )
        )
    if not ranked:
        return DiscoveryReceipt(
            "NO_FEATURE_ADMITTED",
            None,
            None,
            None,
            None,
            None,
            hashes,
            "UNCHANGED_MOTHER_PLAN",
            "NOT_EVALUATED",
        )
    selected = max(ranked, key=lambda item: item[0])[1]
    return DiscoveryReceipt(
        "ONE_FEATURE_ADMITTED",
        *selected,
        hashes,
        "UNCHANGED_MOTHER_PLAN",
        "NOT_EVALUATED",
    )


class _InternalRetuneExecutor:
    def __init__(self, reference: _Handle, perturbed: _Handle, plan: F2531Plan):
        self.__reference = reference
        self.__perturbed = perturbed
        self.__plan = plan
        self.__center = plan.center_a_hz

    def transition(
        self,
        transition: str,
        requested_center_hz: float,
        last_precommand_perturbed: f2527.ScalarFrameReceipt,
        last_precommand_reference: f2527.ScalarFrameReceipt,
    ) -> InternalCommandReceipt:
        if self.__reference.closed or self.__perturbed.closed:
            raise RuntimeError("retune requires both owned handles to remain open")
        command = f2._tune_command(requested_center_hz)
        issued_ns = max(
            time.monotonic_ns(),
            last_precommand_perturbed.monotonic_arrival_ns,
            last_precommand_reference.monotonic_arrival_ns,
        )
        self.__perturbed.socket.send(command)  # type: ignore[attr-defined]
        digest = _command_hash(command)
        self.__perturbed.retune_command_hashes.append(digest)
        receipt = InternalCommandReceipt(
            transition,
            digest,
            self.__center,
            requested_center_hz,
            issued_ns,
            issued_ns + self.__plan.settling_duration_ns,
            len(self.__reference.retune_command_hashes),
            not self.__perturbed.closed,
            "PRIVATE_PERTURBED_BRANCH_ONLY",
        )
        self.__center = requested_center_hz
        return receipt


def _boundary(
    command: InternalCommandReceipt,
    *,
    perturbed_before: f2527.ScalarFrameReceipt,
    perturbed_after: f2527.ScalarFrameReceipt,
    reference_before: f2527.ScalarFrameReceipt,
    reference_after: f2527.ScalarFrameReceipt,
) -> f2527.BoundaryWitnessReceipt:
    anchor = f2527.CommandBoundaryAnchor(
        command.transition,
        command.command_hash,
        command.command_issued_monotonic_ns,
        command.settling_complete_monotonic_ns,
        perturbed_before.artifact_hash_before_analysis,
        perturbed_after.artifact_hash_before_analysis,
        reference_before.artifact_hash_before_analysis,
        reference_after.artifact_hash_before_analysis,
    )
    return f2527.evaluate_command_boundary(
        anchor,
        last_precommand_perturbed=perturbed_before,
        first_postsettling_perturbed=perturbed_after,
        reference_before=reference_before,
        reference_after=reference_after,
    )


def _continuity(handle: _Handle) -> SessionContinuityReceipt:
    plan = f2527.build_plan()
    sequence_gaps = 0
    timestamp_violations = 0
    residuals: list[float] = []
    for previous, current in zip(handle.scalar_receipts, handle.scalar_receipts[1:]):
        sequence_gaps += int(
            current.sequence != ((previous.sequence + 1) % f2527.SEQUENCE_MODULUS)
        )
        delta = current.raw_server_time_ns - previous.raw_server_time_ns
        if delta < -f2527.HALF_GPS_WEEK_NS:
            delta += f2527.GPS_WEEK_NS
        residual = abs(delta - previous.sample_duration_ns) / (
            1_000_000_000 / previous.sample_rate_hz
        )
        residuals.append(residual)
        timestamp_violations += int(
            residual > plan.maximum_timestamp_step_residual_samples
        )
    satisfied = sequence_gaps == 0 and timestamp_violations == 0
    return SessionContinuityReceipt(
        handle.branch_role,
        len(handle.scalar_receipts),
        sequence_gaps,
        timestamp_violations,
        max(residuals, default=0.0),
        "SATISFIED" if satisfied else "UNSATISFIED",
        tuple(item.artifact_hash_before_analysis for item in handle.scalar_receipts),
    )


def _phase(
    name: str,
    state: PhaseState,
    statement: str,
    hashes: tuple[str, ...] = (),
) -> PhaseReceipt:
    return PhaseReceipt(name, state.value, statement, hashes)


def _complete_not_evaluated(phases: list[PhaseReceipt], statement: str) -> None:
    for name in PHASE_ORDER[len(phases) :]:
        phases.append(_phase(name, PhaseState.NOT_EVALUATED, statement))


def _run_open_handle_injected(
    *,
    reference_socket: object,
    perturbed_socket: object,
) -> F2531RunResult:
    """Private deterministic lifecycle seam with no caller experiment controls."""

    plan = build_plan()
    phases: list[PhaseReceipt] = []
    commands: list[InternalCommandReceipt] = []
    boundaries: list[f2527.BoundaryWitnessReceipt] = []
    continuity: tuple[SessionContinuityReceipt, ...] = ()
    temporal: f2527.RelativeTimingAdmissionReceipt | None = None
    discovery: DiscoveryReceipt | None = None
    handles: list[_Handle] = []
    outcome = Outcome.QUALIFICATION_ERROR

    with ThreadPoolExecutor(max_workers=2) as executor:
        reference_future = executor.submit(
            _open_handle, reference_socket, "reference"
        )
        perturbed_future = executor.submit(
            _open_handle, perturbed_socket, "perturbed"
        )
        reference_attempt = reference_future.result()
        perturbed_attempt = perturbed_future.result()
    open_receipts = (reference_attempt.receipt, perturbed_attempt.receipt)
    if reference_attempt.handle is not None:
        handles.append(reference_attempt.handle)
    if perturbed_attempt.handle is not None:
        handles.append(perturbed_attempt.handle)

    decoded_count = 0
    decoded_samples = 0
    zeroized = True
    close_count = 0
    try:
        states = {item.state for item in open_receipts}
        if "CAPABILITY_REJECTED" in states:
            phases.append(
                _phase(
                    PHASE_ORDER[0],
                    PhaseState.UNSATISFIED,
                    "an injected branch contains an explicit server rejection",
                )
            )
            _complete_not_evaluated(phases, "dual handles were not admitted")
            outcome = Outcome.CAPABILITY_REJECTED
        elif states != {"HANDLE_OPEN"}:
            phases.append(
                _phase(
                    PHASE_ORDER[0],
                    PhaseState.QUALIFICATION_ERROR,
                    "an injected branch could not materialize an owned handle",
                )
            )
            _complete_not_evaluated(phases, "handle qualification error blocked phases")
            outcome = Outcome.QUALIFICATION_ERROR
        else:
            reference = reference_attempt.handle
            perturbed = perturbed_attempt.handle
            assert reference is not None and perturbed is not None
            if (
                reference.channel_id == perturbed.channel_id
                or not math.isclose(
                    reference.sample_rate_hz,
                    perturbed.sample_rate_hz,
                    rel_tol=0.0,
                    abs_tol=f2527.build_plan().maximum_sample_rate_difference_hz,
                )
            ):
                phases.append(
                    _phase(
                        PHASE_ORDER[0],
                        PhaseState.UNSATISFIED,
                        "open handles do not preserve distinct same-rate channels",
                    )
                )
                _complete_not_evaluated(phases, "channel topology was not admitted")
                outcome = Outcome.TOPOLOGY_NOT_ADMITTED
            else:
                phases.append(
                    _phase(
                        PHASE_ORDER[0],
                        PhaseState.SATISFIED,
                        "two distinct injected SND handles are owned by the outer scope",
                        tuple(item.receipt_hash for item in open_receipts),
                    )
                )
                reference_a1, perturbed_a1 = _collect_pair_count(
                    reference, perturbed, PHASE_FRAME_COUNT
                )
                temporal = f2527.evaluate_relative_timing(
                    tuple(item.receipt for item in reference_a1),
                    tuple(item.receipt for item in perturbed_a1),
                )
                if temporal.state != (
                    f2527.AdmissionState.ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT.value
                ):
                    phases.append(
                        _phase(
                            PHASE_ORDER[1],
                            PhaseState.UNSATISFIED,
                            "initial A1 frames did not satisfy relative-time admission",
                        )
                    )
                    _complete_not_evaluated(phases, "temporal admission blocked discovery")
                    outcome = Outcome.TEMPORAL_NOT_ADMITTED
                else:
                    phases.append(
                        _phase(
                            PHASE_ORDER[1],
                            PhaseState.SATISFIED,
                            "initial A1 frames satisfy the same-ADC relative-time contract",
                        )
                    )
                    discovery = _discover_one_feature(reference_a1, perturbed_a1)
                    if discovery.state != "ONE_FEATURE_ADMITTED":
                        phases.append(
                            _phase(
                                PHASE_ORDER[2],
                                PhaseState.UNSATISFIED,
                                "unchanged thresholds admitted no common A1 feature",
                                discovery.input_artifact_hashes,
                            )
                        )
                        _complete_not_evaluated(phases, "no feature admitted intervention")
                        outcome = Outcome.NO_FALSIFIABLE_INTERVENTION
                    else:
                        phases.append(
                            _phase(
                                PHASE_ORDER[2],
                                PhaseState.SATISFIED,
                                "one common A1 feature was selected locally while handles remained open",
                                (discovery.receipt_hash,),
                            )
                        )
                        executor = _InternalRetuneExecutor(reference, perturbed, plan)
                        command_b = executor.transition(
                            "A1_TO_B",
                            plan.center_a_hz + plan.technical_delta_hz,
                            perturbed_a1[-1].receipt,
                            reference_a1[-1].receipt,
                        )
                        commands.append(command_b)
                        reference_b, perturbed_b = _collect_pair_postsettling(
                            reference,
                            perturbed,
                            (
                                command_b.settling_complete_monotonic_ns
                                + perturbed_a1[-1].receipt.sample_duration_ns
                            ),
                            PHASE_FRAME_COUNT,
                        )
                        boundary_b = _boundary(
                            command_b,
                            perturbed_before=perturbed_a1[-1].receipt,
                            perturbed_after=perturbed_b[0].receipt,
                            reference_before=reference_a1[-1].receipt,
                            reference_after=reference_b[0].receipt,
                        )
                        boundaries.append(boundary_b)
                        b_valid = boundary_b.state == (
                            f2527.BoundaryState.BOUNDARY_WITNESSED.value
                        )
                        phases.append(
                            _phase(
                                PHASE_ORDER[3],
                                PhaseState.SATISFIED if b_valid else PhaseState.UNSATISFIED,
                                boundary_b.statement,
                                (boundary_b.anchor_receipt_hash,),
                            )
                        )
                        if not b_valid:
                            _complete_not_evaluated(phases, "A1_TO_B boundary was invalid")
                            outcome = Outcome.INTERVENTION_INVALID
                        else:
                            command_a2 = executor.transition(
                                "B_TO_A2",
                                plan.center_a_hz,
                                perturbed_b[-1].receipt,
                                reference_b[-1].receipt,
                            )
                            commands.append(command_a2)
                            reference_a2, perturbed_a2 = _collect_pair_postsettling(
                                reference,
                                perturbed,
                                (
                                    command_a2.settling_complete_monotonic_ns
                                    + perturbed_b[-1].receipt.sample_duration_ns
                                ),
                                PHASE_FRAME_COUNT,
                            )
                            boundary_a2 = _boundary(
                                command_a2,
                                perturbed_before=perturbed_b[-1].receipt,
                                perturbed_after=perturbed_a2[0].receipt,
                                reference_before=reference_b[-1].receipt,
                                reference_after=reference_a2[0].receipt,
                            )
                            boundaries.append(boundary_a2)
                            continuity = (
                                _continuity(reference),
                                _continuity(perturbed),
                            )
                            a2_valid = boundary_a2.state == (
                                f2527.BoundaryState.BOUNDARY_WITNESSED.value
                            )
                            continuous = all(
                                item.state == "SATISFIED" for item in continuity
                            )
                            phases.append(
                                _phase(
                                    PHASE_ORDER[4],
                                    (
                                        PhaseState.SATISFIED
                                        if a2_valid and continuous
                                        else PhaseState.UNSATISFIED
                                    ),
                                    (
                                        "B_TO_A2 is bracketed and both channel sequences remain continuous"
                                        if a2_valid and continuous
                                        else "return boundary or session continuity is invalid"
                                    ),
                                    (boundary_a2.anchor_receipt_hash,),
                                )
                            )
                            _complete_not_evaluated(
                                phases,
                                "Gate F2.5.31 stops before plan freeze and confirmation",
                            )
                            outcome = (
                                Outcome.OPEN_HANDLE_BOUNDARIES_WITNESSED_OFFLINE
                                if a2_valid and continuous
                                else Outcome.INTERVENTION_INVALID
                            )
    except Exception:
        if len(phases) < len(PHASE_ORDER):
            phases.append(
                _phase(
                    PHASE_ORDER[len(phases)],
                    PhaseState.QUALIFICATION_ERROR,
                    "an injected lifecycle transform raised a descriptive error",
                )
            )
        _complete_not_evaluated(phases, "qualification error blocked later phases")
        outcome = Outcome.QUALIFICATION_ERROR
    finally:
        for handle in handles:
            for frame in handle.decoded_frames:
                decoded_count += 1
                decoded_samples += frame.zeroize()
                zeroized = zeroized and bool(np.all(frame.samples == 0))
            handle.decoded_frames.clear()
            handle.scalar_receipts.clear()
        for socket in (reference_socket, perturbed_socket):
            try:
                socket.close()  # type: ignore[attr-defined]
            except Exception:
                pass
            finally:
                close_count += 1
        for handle in handles:
            handle.closed = True

    lease_count = sum(
        (
            attempt.handle.frame_lease_count
            if attempt.handle is not None
            else attempt.receipt.frame_lease_count
        )
        for attempt in (reference_attempt, perturbed_attempt)
    )
    release_count = sum(
        (
            attempt.handle.frame_release_count
            if attempt.handle is not None
            else attempt.receipt.frame_release_count
        )
        for attempt in (reference_attempt, perturbed_attempt)
    )
    cleanup = CleanupReceipt(
        2,
        close_count,
        lease_count,
        release_count,
        decoded_count,
        decoded_samples,
        zeroized,
        0,
        True,
        RAW_RF_PERSISTENCE,
    )
    return F2531RunResult(
        plan.plan_hash,
        outcome.value,
        open_receipts,
        temporal,
        discovery,
        tuple(commands),
        tuple(boundaries),
        continuity,
        tuple(phases),
        cleanup,
        "NOT_EVALUATED",
        False,
        (
            "the same two injected channel handles remained open through both commands",
            "only the private perturbed-branch executor emitted retune commands",
            "both scalar command boundaries and full-session continuity were evaluated",
            "all sockets and ephemeral IQ were released in the outer finally",
        ),
        (
            "a live endpoint accepted the experiment",
            "the commands were remotely acknowledged",
            "the discovered feature moved or stayed fixed after retune",
            "either physical DDC-location hypothesis was supported",
            "plan freeze or confirmation occurred",
        ),
        RAW_RF_PERSISTENCE,
    )


def _integration_surface_hash() -> str:
    return sha256(inspect.getsource(_run_open_handle_injected).encode()).hexdigest()


def build_plan() -> F2531Plan:
    mother = f2.MotherPlan()
    return F2531Plan(
        REVIEWED_F2530_COMMIT,
        REVIEWED_F2530_SOURCE_SHA256,
        REVIEWED_F2530_ENVELOPE_HASH,
        EXPECTED_INTEGRATION_SURFACE_HASH,
        f2520.SELECTED_ENDPOINT_IDENTITY,
        f2520.SELECTED_BOOTSTRAP_CENTER_HZ,
        TECHNICAL_DELTA_HZ,
        round(mother.settling_s * 1_000_000_000),
        PHASE_FRAME_COUNT,
        f2527.build_plan().plan_hash,
        (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
            (
                "minimum_fingerprint_correlation",
                mother.minimum_fingerprint_correlation,
            ),
        ),
        "ONE_OUTER_OWNER_FROM_OPEN_THROUGH_B_TO_A2",
        "PRIVATE_PERTURBED_BRANCH_ONLY",
        "OUTER_FINALLY_AFTER_TERMINAL_OUTCOME",
        (),
        0,
        0,
        False,
        RAW_RF_PERSISTENCE,
        (
            f2527.TRANSFORM_VERSION,
            f2528.TRANSFORM_VERSION,
            f2529.TRANSFORM_VERSION,
            f2530.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ),
    )


def assess() -> F2531Assessment:
    source_match = current_f2530_source_sha256() == REVIEWED_F2530_SOURCE_SHA256
    parent = f2530.assess()
    parent_ready = (
        parent.exit is f2530.F2530Exit.LIVE_SURFACE_NOT_SEALABLE
        and parent.envelope is not None
        and parent.envelope.envelope_hash == REVIEWED_F2530_ENVELOPE_HASH
    )
    surface_match = _integration_surface_hash() == EXPECTED_INTEGRATION_SURFACE_HASH
    blockers = tuple(
        message
        for condition, message in (
            (source_match, "reviewed F2.5.30 source changed"),
            (parent_ready, "reviewed F2.5.30 audit changed"),
            (surface_match, "open-handle integration surface changed"),
        )
        if not condition
    )
    return F2531Assessment(
        (
            F2531Exit.OPEN_HANDLE_SUCCESSOR_MATERIALIZED_OFFLINE
            if not blockers
            else F2531Exit.SEAL_MISMATCH
        ),
        build_plan() if not blockers else None,
        source_match,
        parent_ready,
        surface_match,
        True,
        True,
        True,
        False,
        blockers,
        RAW_RF_PERSISTENCE,
    )


__all__ = [
    "F2531Assessment",
    "F2531Exit",
    "F2531Plan",
    "F2531RunResult",
    "Outcome",
    "assess",
    "build_plan",
]
