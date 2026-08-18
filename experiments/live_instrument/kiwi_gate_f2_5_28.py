"""Gate F2.5.28: injected one-shot integration for relative timing.

This module has no connector and no live authority.  It binds the reviewed
Gate F2.5.27 plan, hashes each injected SND artifact before decoding, keeps IQ
only in ephemeral RAM, gates discovery and retune on temporal admission, and
zeroizes every decoded array in ``finally``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
import importlib.metadata
import inspect
import json
import math
from pathlib import Path
import platform
import struct
from typing import Callable, Sequence

import numpy as np

from . import kiwi_gate_f2_5_26 as f2526
from . import kiwi_gate_f2_5_27 as f2527


TRANSFORM_VERSION = "gate-f2.5.28-injected-relative-time-one-shot-v1"
REVIEWED_F2527_COMMIT = "3b678173d5836c8f72696c0a9ea1a7c6a3d25ff8"
EXPECTED_CAUSAL_SOURCE_SHA256 = (
    (
        "experiments/live_instrument/kiwi_gate_f2_5_26.py",
        "ccb1a279e00bfa4502c1f9692974d89ec6fe13ae1e2863eed120f1b4f01ac39f",
    ),
    (
        "experiments/live_instrument/kiwi_gate_f2_5_27.py",
        "abc0da606b4d78228643c93672b6fe9a436e7da28418df5c9e0b47765fdba76d",
    ),
)
EXPECTED_ENVIRONMENT = (
    ("python", "3.13.5"),
    ("numpy", "2.3.3"),
)
EXPECTED_FRAME_SURFACE_HASH = (
    "be34af4c95ce5b6fa188c46baca2f9fcd7d0919058b73f361baa76c64fbea70d"
)
EXPECTED_ONE_SHOT_SURFACE_HASH = (
    "b1f3076b21712532cb76a37711cd9bab952dc7c806c371ae3707c226f0af3ea8"
)
RAW_RF_PERSISTENCE = "ZERO"

PHASE_ORDER = (
    "RELATIVE_DUAL_SND_QUALIFICATION",
    "ONE_TARGET_DISCOVERY",
    "DISTRIBUTED_RETUNE_QUALIFICATION",
    "PLAN_FREEZE",
    "ONE_CONFIRMATION",
)

_FORBIDDEN_RECEIPT_KEYS = {
    "blocks",
    "frames",
    "iq",
    "iq_array",
    "iq_samples",
    "raw_body",
    "raw_frame",
    "raw_frames",
    "raw_message",
    "samples",
    "stft",
    "waterfall",
}


class F2528Exit(str, Enum):
    INJECTED_ONE_SHOT_INTEGRATED_OFFLINE = "INJECTED_ONE_SHOT_INTEGRATED_OFFLINE"
    SEAL_MISMATCH = "SEAL_MISMATCH"


class FrameState(str, Enum):
    SCALAR_RECEIPT_AND_EPHEMERAL_IQ_READY = (
        "SCALAR_RECEIPT_AND_EPHEMERAL_IQ_READY"
    )
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class PhaseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"
    NOT_EVALUATED = "NOT_EVALUATED"


class OneShotOutcome(str, Enum):
    RETUNE_QUALIFIED_OFFLINE = "RETUNE_QUALIFIED_OFFLINE"
    NO_FALSIFIABLE_INTERVENTION = "NO_FALSIFIABLE_INTERVENTION"
    INTERVENTION_NOT_QUALIFIED = "INTERVENTION_NOT_QUALIFIED"
    TEMPORAL_NOT_ADMITTED = "TEMPORAL_NOT_ADMITTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


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


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _canonical_source_sha256(path: Path) -> str:
    source = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    return sha256(source.encode()).hexdigest()


def current_causal_source_sha256() -> tuple[tuple[str, str], ...]:
    root = _repository_root()
    return tuple(
        (relative, _canonical_source_sha256(root / relative))
        for relative, _expected in EXPECTED_CAUSAL_SOURCE_SHA256
    )


def current_environment() -> tuple[tuple[str, str], ...]:
    return (
        ("python", platform.python_version()),
        ("numpy", importlib.metadata.version("numpy")),
    )


@dataclass(frozen=True, slots=True)
class F2528Envelope:
    reviewed_f2527_commit: str
    reviewed_temporal_plan_hash: str
    causal_source_sha256: tuple[tuple[str, str], ...]
    expected_environment: tuple[tuple[str, str], ...]
    frame_surface_hash: str
    one_shot_surface_hash: str
    phase_order: tuple[str, ...]
    temporal_gate_precedes_discovery: bool
    discovery_precedes_retune: bool
    boundary_witnesses_required_for_retune: tuple[str, str]
    frame_hash_precedes_decode: bool
    iq_lifetime: str
    zeroization_boundary: str
    input_mode: str
    live_execution_authorised: bool
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_f2527_commit != REVIEWED_F2527_COMMIT:
            raise ValueError("Gate F2.5.27 lineage changed")
        if self.reviewed_temporal_plan_hash != f2527.build_plan().plan_hash:
            raise ValueError("reviewed temporal plan changed")
        if self.causal_source_sha256 != EXPECTED_CAUSAL_SOURCE_SHA256:
            raise ValueError("causal source seal changed")
        if self.expected_environment != EXPECTED_ENVIRONMENT:
            raise ValueError("numerical environment seal changed")
        if self.frame_surface_hash != EXPECTED_FRAME_SURFACE_HASH:
            raise ValueError("frame integration surface changed")
        if self.one_shot_surface_hash != EXPECTED_ONE_SHOT_SURFACE_HASH:
            raise ValueError("one-shot integration surface changed")
        if self.phase_order != PHASE_ORDER:
            raise ValueError("one-shot phase order changed")
        if not self.temporal_gate_precedes_discovery or not self.discovery_precedes_retune:
            raise ValueError("downstream phase order changed")
        if self.boundary_witnesses_required_for_retune != ("A1_TO_B", "B_TO_A2"):
            raise ValueError("both intervention boundaries are mandatory")
        if not self.frame_hash_precedes_decode:
            raise ValueError("artifact hashing must precede frame analysis")
        if self.iq_lifetime != "INJECTED_RAM_ONLY_UNTIL_FINALLY":
            raise ValueError("ephemeral IQ lifetime changed")
        if self.zeroization_boundary != "ALWAYS_BEFORE_RESULT_RETURN":
            raise ValueError("zeroization boundary changed")
        if self.input_mode != "INJECTED_TRANSIENT_SND_AND_CALLBACKS_ONLY":
            raise ValueError("a connector entered the offline integration")
        if self.live_execution_authorised:
            raise ValueError("Gate F2.5.28 cannot grant live authority")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the one-shot integration permits no retry")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2526.TRANSFORM_VERSION,
            f2527.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("integration transform ledger changed")

    @property
    def envelope_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(slots=True)
class TransientSNDInput:
    monotonic_arrival_ns: int
    raw_message: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if self.monotonic_arrival_ns < 0:
            raise ValueError("monotonic arrival cannot be negative")
        if not isinstance(self.raw_message, bytes):
            raise TypeError("transient SND input must be bytes")


@dataclass(frozen=True, slots=True)
class FrameQualificationErrorReceipt:
    artifact_hash_before_analysis: str
    artifact_byte_count: int
    branch_role: str
    error_type: str
    description_hash: str
    state: str
    physical_decision_affected: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.artifact_hash_before_analysis)
        _sha256(self.description_hash)
        if self.branch_role not in {"reference", "perturbed"}:
            raise ValueError("unknown branch role")
        if self.state != FrameState.QUALIFICATION_ERROR.value:
            raise ValueError("frame error receipt state changed")
        if self.physical_decision_affected:
            raise ValueError("description cannot alter a physical decision")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(slots=True)
class _EphemeralDecodedFrame:
    receipt: f2527.ScalarFrameReceipt
    samples: np.ndarray = field(repr=False)

    def zeroize(self) -> int:
        count = int(self.samples.size)
        self.samples.fill(0)
        return count


@dataclass(frozen=True, slots=True)
class _EphemeralDualIQView:
    reference_receipts: tuple[f2527.ScalarFrameReceipt, ...]
    perturbed_receipts: tuple[f2527.ScalarFrameReceipt, ...]
    reference_iq: tuple[np.ndarray, ...] = field(repr=False)
    perturbed_iq: tuple[np.ndarray, ...] = field(repr=False)


@dataclass(frozen=True, slots=True)
class DiscoveryProbeResult:
    eligible: bool
    artifact_hashes: tuple[str, ...]
    statement: str
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        for item in self.artifact_hashes:
            _sha256(item)
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class RetuneProbeResult:
    claimed_qualified: bool
    boundary_receipts: tuple[f2527.BoundaryWitnessReceipt, ...]
    witness_artifact_hashes: tuple[str, ...]
    statement: str
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        for item in self.witness_artifact_hashes:
            _sha256(item)
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class DownstreamErrorReceipt:
    stage: str
    error_type: str
    description_hash: str
    physical_decision_affected: bool

    def __post_init__(self) -> None:
        if self.stage not in {"ONE_TARGET_DISCOVERY", "DISTRIBUTED_RETUNE_QUALIFICATION"}:
            raise ValueError("unknown downstream error stage")
        _sha256(self.description_hash)
        if self.physical_decision_affected:
            raise ValueError("descriptive error cannot change physical inference")


@dataclass(frozen=True, slots=True)
class PhaseReceipt:
    phase: str
    state: str
    statement: str
    evidence_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.phase not in PHASE_ORDER:
            raise ValueError("unknown one-shot phase")
        if self.state not in {item.value for item in PhaseState}:
            raise ValueError("unknown phase state")
        for item in self.evidence_hashes:
            _sha256(item)


@dataclass(frozen=True, slots=True)
class ZeroizationReceipt:
    ephemeral_frame_count: int
    ephemeral_sample_count: int
    all_arrays_zeroized: bool
    artifact_set_hash: str
    zeroized_before_result_return: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.artifact_set_hash)
        if not self.all_arrays_zeroized or not self.zeroized_before_result_return:
            raise ValueError("every ephemeral IQ array must be zeroized")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2528RunResult:
    envelope_hash: str
    outcome: str
    temporal_admission: f2527.RelativeTimingAdmissionReceipt | None
    frame_errors: tuple[FrameQualificationErrorReceipt, ...]
    downstream_errors: tuple[DownstreamErrorReceipt, ...]
    boundary_receipts: tuple[f2527.BoundaryWitnessReceipt, ...]
    phases: tuple[PhaseReceipt, ...]
    discovery_call_count: int
    retune_call_count: int
    zeroization: ZeroizationReceipt
    physical_hypothesis_state: str
    physical_decision_affected_by_description: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.envelope_hash)
        if self.outcome not in {item.value for item in OneShotOutcome}:
            raise ValueError("unknown one-shot outcome")
        if tuple(item.phase for item in self.phases) != PHASE_ORDER:
            raise ValueError("one-shot phases must be complete and ordered")
        if self.physical_hypothesis_state != "NOT_EVALUATED":
            raise ValueError("offline integration cannot decide DDC location")
        if self.physical_decision_affected_by_description:
            raise ValueError("description cannot alter physical inference")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2528Assessment:
    exit: F2528Exit
    envelope: F2528Envelope | None
    causal_source_hashes_match: bool
    numerical_environment_matches: bool
    integration_surfaces_match: bool
    hash_precedes_decode: bool
    temporal_failure_blocks_discovery: bool
    temporal_failure_blocks_retune: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


DiscoveryProbe = Callable[[_EphemeralDualIQView], DiscoveryProbeResult]
RetuneProbe = Callable[[_EphemeralDualIQView], RetuneProbeResult]


def _frame_surface_hash() -> str:
    return sha256(inspect.getsource(observe_relative_snd).encode()).hexdigest()


def _one_shot_surface_hash() -> str:
    return sha256(inspect.getsource(run_one_shot_injected).encode()).hexdigest()


def build_envelope() -> F2528Envelope:
    return F2528Envelope(
        reviewed_f2527_commit=REVIEWED_F2527_COMMIT,
        reviewed_temporal_plan_hash=f2527.build_plan().plan_hash,
        causal_source_sha256=EXPECTED_CAUSAL_SOURCE_SHA256,
        expected_environment=EXPECTED_ENVIRONMENT,
        frame_surface_hash=EXPECTED_FRAME_SURFACE_HASH,
        one_shot_surface_hash=EXPECTED_ONE_SHOT_SURFACE_HASH,
        phase_order=PHASE_ORDER,
        temporal_gate_precedes_discovery=True,
        discovery_precedes_retune=True,
        boundary_witnesses_required_for_retune=("A1_TO_B", "B_TO_A2"),
        frame_hash_precedes_decode=True,
        iq_lifetime="INJECTED_RAM_ONLY_UNTIL_FINALLY",
        zeroization_boundary="ALWAYS_BEFORE_RESULT_RETURN",
        input_mode="INJECTED_TRANSIENT_SND_AND_CALLBACKS_ONLY",
        live_execution_authorised=False,
        prefreeze_retry_budget=0,
        postfreeze_retry_budget=0,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
        transform_versions=(
            f2526.TRANSFORM_VERSION,
            f2527.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ),
    )


def _frame_error(
    *,
    artifact_hash: str,
    artifact_byte_count: int,
    branch_role: str,
    error_type: str,
) -> FrameQualificationErrorReceipt:
    return FrameQualificationErrorReceipt(
        artifact_hash_before_analysis=artifact_hash,
        artifact_byte_count=artifact_byte_count,
        branch_role=branch_role,
        error_type=error_type,
        description_hash=_strict_hash(
            {
                "artifact_hash": artifact_hash,
                "branch_role": branch_role,
                "stage": "SND_SCALAR_AND_IQ_DECODE",
                "error_type": error_type,
            }
        ),
        state=FrameState.QUALIFICATION_ERROR.value,
        physical_decision_affected=False,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


def observe_relative_snd(
    transient: TransientSNDInput,
    *,
    endpoint_identity: str,
    branch_role: str,
    channel_id: int,
    sample_rate_hz: float,
) -> _EphemeralDecodedFrame | FrameQualificationErrorReceipt:
    """Hash first, then decode one transient SND frame into RAM and scalars."""

    raw_message = transient.raw_message
    artifact_hash = sha256(raw_message).hexdigest()
    artifact_byte_count = len(raw_message)
    samples: np.ndarray | None = None
    try:
        if branch_role not in {"reference", "perturbed"}:
            raise ValueError("UnknownBranchRole")
        if not endpoint_identity or channel_id < 0:
            raise ValueError("InvalidChannelIdentity")
        if not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0.0:
            raise ValueError("InvalidSampleRate")
        if len(raw_message) < 20 or raw_message[:3] != b"SND":
            raise ValueError("MalformedSNDFrame")
        body = raw_message[3:]
        if len(body) < 17:
            raise ValueError("ShortSNDHeader")
        flags, sequence = struct.unpack("<BI", body[:5])
        if not flags & 0x08:
            raise ValueError("NonIQSNDFrame")
        gps_solution_age_s, _dummy, gps_seconds, gps_nanoseconds = struct.unpack(
            "<BBII", body[7:17]
        )
        payload = body[17:]
        if not payload or len(payload) % 4:
            raise ValueError("InvalidIQPayloadGeometry")
        words = np.frombuffer(payload, dtype=">i2")
        samples = np.empty(words.size // 2, dtype=np.complex64)
        samples.real[:] = words[0::2]
        samples.imag[:] = words[1::2]
        receipt = f2527.ScalarFrameReceipt(
            artifact_hash_before_analysis=artifact_hash,
            artifact_byte_count=artifact_byte_count,
            endpoint_identity=endpoint_identity,
            branch_role=branch_role,
            channel_id=channel_id,
            sequence=int(sequence),
            server_gps_seconds=int(gps_seconds),
            server_gps_nanoseconds=int(gps_nanoseconds),
            gps_solution_age_s=int(gps_solution_age_s),
            decoded_sample_count=int(samples.size),
            sample_rate_hz=float(sample_rate_hz),
            monotonic_arrival_ns=transient.monotonic_arrival_ns,
        )
        del words, payload, body
        return _EphemeralDecodedFrame(receipt, samples)
    except Exception as error:
        if samples is not None:
            samples.fill(0)
        return _frame_error(
            artifact_hash=artifact_hash,
            artifact_byte_count=artifact_byte_count,
            branch_role=branch_role,
            error_type=str(error) or type(error).__name__,
        )


def _phase(
    phase: str,
    state: PhaseState,
    statement: str,
    evidence_hashes: tuple[str, ...] = (),
) -> PhaseReceipt:
    return PhaseReceipt(phase, state.value, statement, evidence_hashes)


def _not_evaluated_phases(start: int, statement: str) -> list[PhaseReceipt]:
    return [
        _phase(name, PhaseState.NOT_EVALUATED, statement)
        for name in PHASE_ORDER[start:]
    ]


def _decode_inputs(
    inputs: Sequence[TransientSNDInput],
    *,
    endpoint_identity: str,
    branch_role: str,
    channel_id: int,
    sample_rate_hz: float,
) -> tuple[list[_EphemeralDecodedFrame], list[FrameQualificationErrorReceipt]]:
    decoded: list[_EphemeralDecodedFrame] = []
    errors: list[FrameQualificationErrorReceipt] = []
    for transient in inputs:
        observed = observe_relative_snd(
            transient,
            endpoint_identity=endpoint_identity,
            branch_role=branch_role,
            channel_id=channel_id,
            sample_rate_hz=sample_rate_hz,
        )
        if isinstance(observed, FrameQualificationErrorReceipt):
            errors.append(observed)
        else:
            decoded.append(observed)
    return decoded, errors


def _view(
    reference: Sequence[_EphemeralDecodedFrame],
    perturbed: Sequence[_EphemeralDecodedFrame],
) -> _EphemeralDualIQView:
    reference_views = tuple(item.samples.view() for item in reference)
    perturbed_views = tuple(item.samples.view() for item in perturbed)
    for item in reference_views + perturbed_views:
        item.setflags(write=False)
    return _EphemeralDualIQView(
        tuple(item.receipt for item in reference),
        tuple(item.receipt for item in perturbed),
        reference_views,
        perturbed_views,
    )


def _retune_boundaries_valid(result: RetuneProbeResult) -> bool:
    by_transition = {item.transition: item for item in result.boundary_receipts}
    return (
        set(by_transition) == {"A1_TO_B", "B_TO_A2"}
        and len(by_transition) == len(result.boundary_receipts)
        and all(
            item.state == f2527.BoundaryState.BOUNDARY_WITNESSED.value
            for item in by_transition.values()
        )
    )


def run_one_shot_injected(
    *,
    reference_inputs: Sequence[TransientSNDInput],
    perturbed_inputs: Sequence[TransientSNDInput],
    endpoint_identity: str,
    reference_channel_id: int,
    perturbed_channel_id: int,
    sample_rate_hz: float,
    discovery_probe: DiscoveryProbe,
    retune_probe: RetuneProbe,
    temporal_plan: f2527.F2527TemporalPlan | None = None,
) -> F2528RunResult:
    """Run the reviewed phase gate with injected transient inputs only."""

    envelope = build_envelope()
    plan = temporal_plan or f2527.build_plan()
    reference: list[_EphemeralDecodedFrame] = []
    perturbed: list[_EphemeralDecodedFrame] = []
    frame_errors: list[FrameQualificationErrorReceipt] = []
    downstream_errors: list[DownstreamErrorReceipt] = []
    boundary_receipts: tuple[f2527.BoundaryWitnessReceipt, ...] = ()
    phases: list[PhaseReceipt] = []
    temporal: f2527.RelativeTimingAdmissionReceipt | None = None
    discovery_calls = 0
    retune_calls = 0
    outcome = OneShotOutcome.QUALIFICATION_ERROR

    try:
        reference, reference_errors = _decode_inputs(
            reference_inputs,
            endpoint_identity=endpoint_identity,
            branch_role="reference",
            channel_id=reference_channel_id,
            sample_rate_hz=sample_rate_hz,
        )
        perturbed, perturbed_errors = _decode_inputs(
            perturbed_inputs,
            endpoint_identity=endpoint_identity,
            branch_role="perturbed",
            channel_id=perturbed_channel_id,
            sample_rate_hz=sample_rate_hz,
        )
        frame_errors.extend(reference_errors + perturbed_errors)
        scalar_hashes = tuple(
            item.receipt.receipt_hash for item in reference + perturbed
        )
        if frame_errors or not reference or not perturbed:
            phases.append(
                _phase(
                    PHASE_ORDER[0],
                    PhaseState.QUALIFICATION_ERROR,
                    "one or more transient SND frames lacked a scalar/IQ receipt",
                    tuple(item.artifact_hash_before_analysis for item in frame_errors),
                )
            )
            phases.extend(
                _not_evaluated_phases(
                    1, "temporal qualification error blocked every downstream phase"
                )
            )
            outcome = OneShotOutcome.QUALIFICATION_ERROR
        else:
            temporal = f2527.evaluate_relative_timing(
                tuple(item.receipt for item in reference),
                tuple(item.receipt for item in perturbed),
                plan=plan,
            )
            if temporal.state != (
                f2527.AdmissionState.ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT.value
            ):
                phases.append(
                    _phase(
                        PHASE_ORDER[0],
                        PhaseState.UNSATISFIED,
                        "relative sample-time clauses did not admit feature analysis",
                        scalar_hashes,
                    )
                )
                phases.extend(
                    _not_evaluated_phases(
                        1, "temporal refusal blocked discovery and retune"
                    )
                )
                outcome = OneShotOutcome.TEMPORAL_NOT_ADMITTED
            else:
                phases.append(
                    _phase(
                        PHASE_ORDER[0],
                        PhaseState.SATISFIED,
                        "relative sample-time clauses admitted ephemeral IQ",
                        scalar_hashes,
                    )
                )
                ephemeral_view = _view(reference, perturbed)
                try:
                    discovery_calls += 1
                    discovery = discovery_probe(ephemeral_view)
                    if not isinstance(discovery, DiscoveryProbeResult):
                        raise TypeError("discovery probe returned an invalid receipt")
                except Exception as error:
                    error_type = type(error).__name__
                    downstream_errors.append(
                        DownstreamErrorReceipt(
                            PHASE_ORDER[1],
                            error_type,
                            _strict_hash(
                                {"stage": PHASE_ORDER[1], "error_type": error_type}
                            ),
                            False,
                        )
                    )
                    phases.append(
                        _phase(
                            PHASE_ORDER[1],
                            PhaseState.QUALIFICATION_ERROR,
                            "injected discovery raised a descriptive error",
                        )
                    )
                    phases.extend(
                        _not_evaluated_phases(
                            2, "discovery error blocked retune and later phases"
                        )
                    )
                    outcome = OneShotOutcome.QUALIFICATION_ERROR
                else:
                    if not discovery.eligible:
                        phases.append(
                            _phase(
                                PHASE_ORDER[1],
                                PhaseState.UNSATISFIED,
                                discovery.statement,
                                discovery.artifact_hashes,
                            )
                        )
                        phases.extend(
                            _not_evaluated_phases(
                                2, "no eligible target blocked retune and later phases"
                            )
                        )
                        outcome = OneShotOutcome.NO_FALSIFIABLE_INTERVENTION
                    else:
                        phases.append(
                            _phase(
                                PHASE_ORDER[1],
                                PhaseState.SATISFIED,
                                discovery.statement,
                                discovery.artifact_hashes,
                            )
                        )
                        try:
                            retune_calls += 1
                            retune = retune_probe(ephemeral_view)
                            if not isinstance(retune, RetuneProbeResult):
                                raise TypeError("retune probe returned an invalid receipt")
                        except Exception as error:
                            error_type = type(error).__name__
                            downstream_errors.append(
                                DownstreamErrorReceipt(
                                    PHASE_ORDER[2],
                                    error_type,
                                    _strict_hash(
                                        {
                                            "stage": PHASE_ORDER[2],
                                            "error_type": error_type,
                                        }
                                    ),
                                    False,
                                )
                            )
                            phases.append(
                                _phase(
                                    PHASE_ORDER[2],
                                    PhaseState.QUALIFICATION_ERROR,
                                    "injected retune raised a descriptive error",
                                )
                            )
                            phases.extend(
                                _not_evaluated_phases(
                                    3, "retune error blocked plan freeze and confirmation"
                                )
                            )
                            outcome = OneShotOutcome.QUALIFICATION_ERROR
                        else:
                            boundary_receipts = retune.boundary_receipts
                            retune_valid = (
                                retune.claimed_qualified
                                and _retune_boundaries_valid(retune)
                            )
                            phases.append(
                                _phase(
                                    PHASE_ORDER[2],
                                    (
                                        PhaseState.SATISFIED
                                        if retune_valid
                                        else PhaseState.UNSATISFIED
                                    ),
                                    retune.statement,
                                    retune.witness_artifact_hashes
                                    + tuple(
                                        item.anchor_receipt_hash
                                        for item in retune.boundary_receipts
                                    ),
                                )
                            )
                            phases.extend(
                                _not_evaluated_phases(
                                    3,
                                    "Gate F2.5.28 stops before plan freeze and confirmation",
                                )
                            )
                            outcome = (
                                OneShotOutcome.RETUNE_QUALIFIED_OFFLINE
                                if retune_valid
                                else OneShotOutcome.INTERVENTION_NOT_QUALIFIED
                            )
    finally:
        ephemeral_frames = reference + perturbed
        sample_count = sum(item.zeroize() for item in ephemeral_frames)
        zeroized = all(
            bool(np.all(item.samples == 0)) for item in ephemeral_frames
        )
        artifact_set_hash = _strict_hash(
            tuple(sorted(item.receipt.artifact_hash_before_analysis for item in ephemeral_frames))
        )
        zeroization = ZeroizationReceipt(
            ephemeral_frame_count=len(ephemeral_frames),
            ephemeral_sample_count=sample_count,
            all_arrays_zeroized=zeroized,
            artifact_set_hash=artifact_set_hash,
            zeroized_before_result_return=True,
            raw_rf_persistence=RAW_RF_PERSISTENCE,
        )

    return F2528RunResult(
        envelope_hash=envelope.envelope_hash,
        outcome=outcome.value,
        temporal_admission=temporal,
        frame_errors=tuple(frame_errors),
        downstream_errors=tuple(downstream_errors),
        boundary_receipts=boundary_receipts,
        phases=tuple(phases),
        discovery_call_count=discovery_calls,
        retune_call_count=retune_calls,
        zeroization=zeroization,
        physical_hypothesis_state="NOT_EVALUATED",
        physical_decision_affected_by_description=False,
        authorised_claims=(
            "temporal admission controls access to ephemeral feature analysis",
            "both command boundaries are required before retune qualification",
            "all decoded IQ arrays are zeroized before the result returns",
        ),
        unauthorised_claims=(
            "a live Kiwi satisfies the new temporal contract",
            "the frozen Gate F2.5.25 outcome changed",
            "the retune was applied on a live channel",
            "a physical feature was found",
            "the feature is upstream or downstream of the channel DDC",
        ),
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


def assess() -> F2528Assessment:
    blockers: list[str] = []
    causal_match = current_causal_source_sha256() == EXPECTED_CAUSAL_SOURCE_SHA256
    environment_match = current_environment() == EXPECTED_ENVIRONMENT
    surfaces_match = (
        _frame_surface_hash() == EXPECTED_FRAME_SURFACE_HASH
        and _one_shot_surface_hash() == EXPECTED_ONE_SHOT_SURFACE_HASH
    )
    if not causal_match:
        blockers.append("CAUSAL_SOURCE_HASH_MISMATCH")
    if not environment_match:
        blockers.append("NUMERICAL_ENVIRONMENT_MISMATCH")
    if not surfaces_match:
        blockers.append("INTEGRATION_SURFACE_HASH_MISMATCH")
    envelope: F2528Envelope | None = None
    if not blockers:
        envelope = build_envelope()
    return F2528Assessment(
        exit=(
            F2528Exit.INJECTED_ONE_SHOT_INTEGRATED_OFFLINE
            if not blockers
            else F2528Exit.SEAL_MISMATCH
        ),
        envelope=envelope,
        causal_source_hashes_match=causal_match,
        numerical_environment_matches=environment_match,
        integration_surfaces_match=surfaces_match,
        hash_precedes_decode=True,
        temporal_failure_blocks_discovery=True,
        temporal_failure_blocks_retune=True,
        live_execution_authorised=False,
        blockers=tuple(blockers),
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )
