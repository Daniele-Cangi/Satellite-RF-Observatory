"""Gate F2: one targetless, prospective Kiwi retuning intervention.

This is a disposable vertical experiment, not a Kiwi adapter or a planner.
Capabilities, RF artifacts and candidate features exist only in RAM.  At most
one frozen plan and one A->B->A confirmation may be produced by ``run_once``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from hashlib import sha256
import json
import math
import re
import struct
from threading import Event
import time
from typing import Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import numpy as np
from scipy import signal

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


KIWI_SERVER_COMMIT = "c40ecb471dced33689e335689f8ffd35a54f47fa"
KIWI_CLIENT_COMMIT = "4eb733e6b6147f7fbeb97ced64cdac029b202d18"
TRANSFORM_VERSION = f"gate-f2:{KIWI_SERVER_COMMIT[:12]}:{KIWI_CLIENT_COMMIT[:12]}:1"
DIRECTORY_URL = "https://kiwisdr.com/.public/"

CLAUSE_NAMES = (
    "independent_hardware_roots",
    "event_time_valid",
    "reference_root_continuous",
    "perturbed_root_continuous",
    "axis_orientation_known",
    "transform_ledger_complete",
    "target_detectable_A1",
    "witness_detectable_A1",
    "intervention_command_applied",
    "witness_translation_valid",
    "target_remains_detectable_on_reference_root",
    "target_matches_RF-frame_prediction_B",
    "target_matches_baseband-frame_prediction_B",
    "target_returns_to_A_prediction",
    "witness_returns_to_A_prediction",
    "no_invalidating_gap",
    "no_invalidating_overflow",
)

PHASE_CLAUSE_NAMES = (
    "qualification_completed",
    "capability_admitted",
    "falsifiable_intervention_available",
)


class CapabilityState(str, Enum):
    CAPABILITY_DISCOVERED = "CAPABILITY_DISCOVERED"
    CAPABILITY_QUALIFIED = "CAPABILITY_QUALIFIED"
    CAPABILITY_ADMITTED = "CAPABILITY_ADMITTED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"


class GatePhase(str, Enum):
    BOOTSTRAP = "BOOTSTRAP"
    DISCOVERY = "DISCOVERY"
    QUALIFICATION = "QUALIFICATION"
    ADMISSION = "ADMISSION"
    PLAN_FREEZE = "PLAN_FREEZE"
    EXPERIMENT = "EXPERIMENT"


class DiscoveryResponseStatus(str, Enum):
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    PROTOCOL_ERROR = "PROTOCOL_ERROR"
    DESCRIPTION_ERROR = "DESCRIPTION_ERROR"
    VALID_EMPTY_RESULT = "VALID_EMPTY_RESULT"
    VALID_CANDIDATE_RESULT = "VALID_CANDIDATE_RESULT"


class DiscoveryOutcomeKind(str, Enum):
    DISCOVERY_PATH_FAILED = "DISCOVERY_PATH_FAILED"
    NO_CAPABILITY_DISCOVERED = "NO_CAPABILITY_DISCOVERED"
    CANDIDATES_DISCOVERED = "CANDIDATES_DISCOVERED"


class OutcomeKind(str, Enum):
    DISCOVERY_PATH_FAILED = "DISCOVERY_PATH_FAILED"
    NO_CAPABILITY_DISCOVERED = "NO_CAPABILITY_DISCOVERED"
    NO_CAPABILITY_QUALIFIED = "NO_CAPABILITY_QUALIFIED"
    NO_CAPABILITY_ADMITTED = "NO_CAPABILITY_ADMITTED"
    NO_FALSIFIABLE_EXPERIMENT_AVAILABLE = "NO_FALSIFIABLE_EXPERIMENT_AVAILABLE"
    RF_FRAME_PREDICTION_SUPPORTED = "RF_FRAME_PREDICTION_SUPPORTED"
    BASEBAND_FRAME_PREDICTION_SUPPORTED = "BASEBAND_FRAME_PREDICTION_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_DETECTABLE = "NOT_DETECTABLE"
    INTERVENTION_INVALID = "INTERVENTION_INVALID"


@dataclass(frozen=True, slots=True)
class ProtocolAudit:
    command: str
    causal_interval: str
    exact_verified_point: str
    hardware_lo_changed: bool
    acknowledgement_available: bool
    iq_wire_order: str
    orientation_rule: str
    source_commit: str
    source_locations: tuple[str, ...]
    caveats: tuple[str, ...]


def protocol_audit() -> ProtocolAudit:
    """The immutable pre-network audit of the protocol used by this probe."""

    return ProtocolAudit(
        command="SET mod=iq low_cut=-5000 high_cut=5000 freq=<kHz>",
        causal_interval="antenna/front-end -> ADC -> [FPGA per-channel RX NCO/DDC intervention] -> IQ passband FIR -> AGC -> SND IQ stream",
        exact_verified_point="rx_sound_cmd() calls rx_sound_set_freq(); a 48-bit phase word is sent with CmdSetRXFreq over SPI to the selected FPGA RX channel",
        hardware_lo_changed=False,
        acknowledgement_available=False,
        iq_wire_order="big-endian signed int16 real followed by imaginary; client decodes real + j*imag",
        orientation_rule="axis_orientation is learned from an orthogonal witness during qualification; confirmation target samples cannot set it",
        source_commit=KIWI_SERVER_COMMIT,
        source_locations=(
            "rx/rx_sound_cmd.cpp:67-79",
            "rx/rx_sound_cmd.cpp:151-175",
            "rx/rx_sound.cpp:568-596",
            "rx/rx_sound.cpp:1082-1136",
        ),
        caveats=(
            "the websocket protocol returns no tune acknowledgement",
            "server configuration can select spectral inversion",
            "reported or requested center frequency alone is not evidence that new samples entered the stream",
        ),
    )


@dataclass(frozen=True, slots=True)
class MotherPlan:
    """Method and limits frozen before Gate F2 capability discovery."""

    directory_url: str = DIRECTORY_URL
    offer_ttl_s: float = 600.0
    prefreeze_budget_s: float = 720.0
    maximum_directory_candidates: int = 20
    maximum_pairs: int = 3
    maximum_iq_centers: int = 8
    waterfall_frames: int = 3
    qualification_duration_s: float = 3.5
    diagnostic_segment_s: float = 2.5
    confirmation_segment_s: float = 3.0
    settling_s: float = 0.8
    nperseg: int = 1024
    noverlap: int = 512
    minimum_contrast_db: float = 5.0
    minimum_witness_contrast_db: float = 5.0
    minimum_fingerprint_correlation: float = 0.65
    minimum_half_contrast_db: float = 3.0
    minimum_delta_hz: float = 300.0
    maximum_delta_hz: float = 1500.0
    guard_bins: int = 8
    prediction_tolerance_bins: float = 2.5
    maximum_gps_solution_age_s: int = 30
    maximum_arrival_latency_s: float = 5.0
    minimum_hardware_separation_km: float = 1.0
    maximum_pair_separation_km: float = 1200.0
    maximum_prefreeze_retries: int = 2

    def __post_init__(self) -> None:
        if self.offer_ttl_s <= 0 or self.prefreeze_budget_s <= 0:
            raise ValueError("Gate F2 budgets and TTL must be positive")
        if self.maximum_directory_candidates < 2 or self.maximum_pairs < 1:
            raise ValueError("Gate F2 needs at least one pair candidate")
        if not 0 <= self.noverlap < self.nperseg:
            raise ValueError("invalid Gate F2 STFT geometry")
        if not 0 < self.minimum_fingerprint_correlation <= 1:
            raise ValueError("invalid fingerprint correlation")
        if self.minimum_delta_hz <= 0 or self.maximum_delta_hz < self.minimum_delta_hz:
            raise ValueError("invalid intervention delta interval")
        if self.maximum_prefreeze_retries != 2:
            raise ValueError("Gate F2 freezes exactly two total pre-freeze retries")

    @property
    def plan_hash(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class DiscoveryReceipt:
    """One transport attempt against one ephemeral inventory path."""

    provider: str
    inventory_root: str
    transport_route: str
    access_mode: str
    started_at: datetime
    completed_at: datetime
    response_status: DiscoveryResponseStatus
    candidate_count: int
    response_hash: str | None
    error_class: str | None
    error_detail: str | None
    retry_index: int
    expires_at: datetime

    def __post_init__(self) -> None:
        started = _utc(self.started_at)
        completed = _utc(self.completed_at)
        expires = _utc(self.expires_at)
        if not all((self.provider, self.inventory_root, self.transport_route, self.access_mode)):
            raise ValueError("discovery lineage fields cannot be empty")
        if not isinstance(self.response_status, DiscoveryResponseStatus):
            raise ValueError("response_status must be a DiscoveryResponseStatus")
        if completed < started:
            raise ValueError("discovery completion precedes its start")
        if expires <= completed:
            raise ValueError("discovery receipt must expire after completion")
        if self.candidate_count < 0 or self.retry_index < 0:
            raise ValueError("discovery counts cannot be negative")
        valid = self.response_status in (
            DiscoveryResponseStatus.VALID_EMPTY_RESULT,
            DiscoveryResponseStatus.VALID_CANDIDATE_RESULT,
        )
        if self.response_status is DiscoveryResponseStatus.TRANSPORT_ERROR and self.response_hash is not None:
            raise ValueError("a transport failure without a response cannot invent a response hash")
        if self.response_hash is not None and re.fullmatch(r"[0-9a-f]{64}", self.response_hash) is None:
            raise ValueError("response_hash must be a lowercase SHA-256 digest")
        if self.response_status is DiscoveryResponseStatus.VALID_EMPTY_RESULT and self.candidate_count != 0:
            raise ValueError("VALID_EMPTY_RESULT requires zero candidates")
        if self.response_status is DiscoveryResponseStatus.VALID_CANDIDATE_RESULT and self.candidate_count <= 0:
            raise ValueError("VALID_CANDIDATE_RESULT requires at least one candidate")
        if valid and self.response_hash is None:
            raise ValueError("a valid discovery response requires its response hash")
        if valid and (self.error_class is not None or self.error_detail is not None):
            raise ValueError("a valid discovery result cannot carry an error")
        if not valid and (not self.error_class or not self.error_detail):
            raise ValueError("a discovery error requires class and detail")

    @property
    def successful(self) -> bool:
        return self.response_status in (
            DiscoveryResponseStatus.VALID_EMPTY_RESULT,
            DiscoveryResponseStatus.VALID_CANDIDATE_RESULT,
        )


@dataclass(frozen=True, slots=True)
class DiscoveryAttempt:
    receipt: DiscoveryReceipt
    candidates: tuple[kiwi.KiwiEndpoint, ...]

    def __post_init__(self) -> None:
        if len(self.candidates) != self.receipt.candidate_count:
            raise ValueError("candidate payload does not match its atomic discovery receipt")


@dataclass(frozen=True, slots=True)
class GateProgress:
    phase_reached: GatePhase
    successful_discovery_paths: int
    candidates_discovered: int
    qualifications_completed: int
    capabilities_admitted: int

    def __post_init__(self) -> None:
        counts = (
            self.successful_discovery_paths,
            self.candidates_discovered,
            self.qualifications_completed,
            self.capabilities_admitted,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Gate phase counts cannot be negative")
        if self.candidates_discovered > 0 and self.successful_discovery_paths == 0:
            raise ValueError("candidates require a successful discovery path")
        if self.qualifications_completed > self.candidates_discovered:
            raise ValueError("completed qualifications cannot exceed discovered candidates")
        if self.capabilities_admitted > self.qualifications_completed:
            raise ValueError("admitted capabilities require completed qualifications")
        phase_rank = {
            GatePhase.BOOTSTRAP: 0,
            GatePhase.DISCOVERY: 1,
            GatePhase.QUALIFICATION: 2,
            GatePhase.ADMISSION: 3,
            GatePhase.PLAN_FREEZE: 4,
            GatePhase.EXPERIMENT: 5,
        }
        reached = phase_rank[self.phase_reached]
        if self.candidates_discovered > 0 and reached < phase_rank[GatePhase.QUALIFICATION]:
            raise ValueError("discovered candidates require entry into qualification")
        if self.qualifications_completed > 0 and reached < phase_rank[GatePhase.ADMISSION]:
            raise ValueError("completed qualifications require entry into admission")
        if self.capabilities_admitted > 0 and reached < phase_rank[GatePhase.ADMISSION]:
            raise ValueError("admitted capabilities require the admission phase")


@dataclass(frozen=True, slots=True)
class CapabilityLineage:
    """Causal identities remain distinct; listing diversity is not hardware diversity."""

    inventory_root: str
    listing_transport: str
    endpoint_identity: str | None = None
    hardware_root: str | None = None
    direct_probe_succeeded: bool = False
    measurement_root: str | None = None

    def __post_init__(self) -> None:
        if self.direct_probe_succeeded and (self.endpoint_identity is None or self.hardware_root is None):
            raise ValueError("a successful direct probe must establish endpoint and hardware identities")
        if self.hardware_root is not None and not self.direct_probe_succeeded:
            raise ValueError("a listing cannot establish a hardware root")
        if self.measurement_root is not None and not self.direct_probe_succeeded:
            raise ValueError("an endpoint becomes a measurement root only after a successful direct probe")


def inventory_root_count(lineages: Sequence[CapabilityLineage]) -> int:
    """Transport mirrors of one registry contribute one inventory root."""

    return len({lineage.inventory_root for lineage in lineages})


def discovery_outcome(
    receipts: Sequence[DiscoveryReceipt],
    *,
    unique_candidate_count: int,
) -> DiscoveryOutcomeKind:
    if unique_candidate_count < 0:
        raise ValueError("unique candidate count cannot be negative")
    successful = [receipt for receipt in receipts if receipt.successful]
    if not successful:
        if unique_candidate_count:
            raise ValueError("candidates cannot emerge without a valid discovery result")
        return DiscoveryOutcomeKind.DISCOVERY_PATH_FAILED
    if unique_candidate_count == 0:
        return DiscoveryOutcomeKind.NO_CAPABILITY_DISCOVERED
    if not any(receipt.response_status is DiscoveryResponseStatus.VALID_CANDIDATE_RESULT for receipt in successful):
        raise ValueError("candidate count conflicts with valid discovery receipts")
    return DiscoveryOutcomeKind.CANDIDATES_DISCOVERED


def validate_prefreeze_outcome(outcome: OutcomeKind, progress: GateProgress) -> None:
    """Prevent a downstream absence label from crossing an unreached phase."""

    if outcome is OutcomeKind.DISCOVERY_PATH_FAILED:
        valid = progress.successful_discovery_paths == 0
        expected_phase = GatePhase.DISCOVERY
    elif outcome is OutcomeKind.NO_CAPABILITY_DISCOVERED:
        valid = progress.successful_discovery_paths > 0 and progress.candidates_discovered == 0
        expected_phase = GatePhase.DISCOVERY
    elif outcome is OutcomeKind.NO_CAPABILITY_QUALIFIED:
        valid = progress.candidates_discovered > 0 and progress.qualifications_completed == 0
        expected_phase = GatePhase.QUALIFICATION
    elif outcome is OutcomeKind.NO_CAPABILITY_ADMITTED:
        valid = progress.qualifications_completed > 0 and progress.capabilities_admitted == 0
        expected_phase = GatePhase.ADMISSION
    elif outcome is OutcomeKind.NO_FALSIFIABLE_EXPERIMENT_AVAILABLE:
        valid = progress.capabilities_admitted > 0
        expected_phase = GatePhase.ADMISSION
    else:
        raise ValueError("outcome is not a pre-freeze stop outcome")
    if not valid:
        raise ValueError(f"{outcome.value} is inconsistent with the recorded phase counts")
    if progress.phase_reached is not expected_phase:
        raise ValueError(f"{outcome.value} requires phase_reached={expected_phase.value}")


def _phase_stop_assessments(outcome: OutcomeKind) -> tuple[ClauseAssessment, ...]:
    if outcome in (OutcomeKind.DISCOVERY_PATH_FAILED, OutcomeKind.NO_CAPABILITY_DISCOVERED):
        statuses = (
            ClauseStatus.NOT_EVALUATED,
            ClauseStatus.NOT_EVALUATED,
            ClauseStatus.NOT_EVALUATED,
        )
    elif outcome is OutcomeKind.NO_CAPABILITY_QUALIFIED:
        statuses = (
            ClauseStatus.UNSATISFIED,
            ClauseStatus.NOT_EVALUATED,
            ClauseStatus.NOT_EVALUATED,
        )
    elif outcome is OutcomeKind.NO_CAPABILITY_ADMITTED:
        statuses = (
            ClauseStatus.SATISFIED,
            ClauseStatus.UNSATISFIED,
            ClauseStatus.NOT_EVALUATED,
        )
    elif outcome is OutcomeKind.NO_FALSIFIABLE_EXPERIMENT_AVAILABLE:
        statuses = (
            ClauseStatus.SATISFIED,
            ClauseStatus.SATISFIED,
            ClauseStatus.UNSATISFIED,
        )
    else:
        raise ValueError("phase stop assessments require a pre-freeze stop outcome")
    statements = {
        ClauseStatus.SATISFIED: "phase gate completed positively",
        ClauseStatus.UNSATISFIED: "phase was entered but its gate was not satisfied",
        ClauseStatus.NOT_EVALUATED: "previous phase was not completed; this gate was not evaluated",
    }
    return tuple(
        ClauseAssessment(name, status, statements[status], ())
        for name, status in zip(PHASE_CLAUSE_NAMES, statuses)
    )


@dataclass(frozen=True, slots=True)
class EndpointCapability:
    endpoint: kiwi.KiwiEndpoint
    state: CapabilityState
    verified_at: datetime
    status_hash: str
    ext_api_slots: int | None
    gps_good: bool | None
    location: tuple[float, float] | None
    reason: str
    expires_at: datetime

    def __post_init__(self) -> None:
        if _utc(self.expires_at) <= _utc(self.verified_at):
            raise ValueError("candidate capability receipt must have a positive TTL")


@dataclass(frozen=True, slots=True)
class FeatureFingerprint:
    baseband_position_a_hz: float
    absolute_rf_estimate_a_hz: float
    bandwidth_hz: float
    local_spectral_neighbourhood_db: tuple[float, ...]
    relative_position_to_witness_hz: float
    temporal_morphology_db: tuple[float, float, float]
    contrast_interval_db: tuple[float, float]
    uncertainty_hz: float


@dataclass(frozen=True, slots=True)
class FrozenPlan:
    mother_plan_hash: str
    protocol_audit_hash: str
    reference_endpoint: kiwi.KiwiEndpoint
    perturbed_endpoint: kiwi.KiwiEndpoint
    center_a_hz: float
    center_b_hz: float
    delta_f_hz: float
    axis_orientation: int
    target: FeatureFingerprint
    witness: FeatureFingerprint
    rf_frame_target_b_hz: float
    baseband_frame_target_b_hz: float
    wrong_sign_target_b_hz: float
    wrong_magnitude_target_b_hz: float
    off_feature_baseband_hz: float
    prediction_tolerance_hz: float
    settling_s: float
    segment_duration_s: float
    frozen_at: datetime
    expires_at: datetime
    hypotheses: tuple[str, ...] = (
        "H_RF_FRAME: target precedes tuning/DDC and translates in baseband while remaining RF-fixed",
        "H_BASEBAND_FRAME: target follows tuning/DDC and remains baseband-fixed",
        "H_OTHER_OR_UNRESOLVED: neither frozen translation is uniquely supported or detectability fails",
    )
    controls: tuple[str, ...] = (
        "RF-frame expected translation",
        "baseband-fixed translation = 0",
        "wrong-sign translation",
        "wrong-magnitude translation",
        "off-feature spectral region",
        "reference-root continuity",
        "relative target/witness spacing",
    )

    def __post_init__(self) -> None:
        if self.axis_orientation not in (-1, 1):
            raise ValueError("axis_orientation must be +1 or -1")
        expected = self.axis_orientation * (-self.delta_f_hz)
        if not math.isclose(
            self.rf_frame_target_b_hz - self.target.baseband_position_a_hz,
            expected,
            abs_tol=1e-9,
        ):
            raise ValueError("RF-frame prediction has the wrong frozen sign")
        if not math.isclose(
            self.baseband_frame_target_b_hz,
            self.target.baseband_position_a_hz,
            abs_tol=1e-9,
        ):
            raise ValueError("baseband-frame prediction must be zero translation")
        if abs(self.rf_frame_target_b_hz - self.baseband_frame_target_b_hz) <= 2 * self.prediction_tolerance_hz:
            raise ValueError("RF-frame and baseband-frame decision regions overlap")
        if _utc(self.expires_at) <= _utc(self.frozen_at):
            raise ValueError("frozen plan must have a future expiry")

    @property
    def plan_hash(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True, slots=True)
class SegmentReceipt:
    root_id: str
    segment: str
    artifact_hash: str
    hashed_before_analysis_at: datetime
    byte_count: int
    event_start: datetime
    event_end: datetime
    center_frequency_hz: float
    sample_rate_hz: float
    sequence_range: tuple[int, int]
    transform_version: str


@dataclass(frozen=True, slots=True)
class InterventionReceipt:
    transition: str
    command_issued_at: datetime
    command_acknowledged_at: datetime | None
    acknowledgement_state: str
    old_center_frequency_hz: float
    requested_new_center_frequency_hz: float
    reported_new_center_frequency_hz: float | None
    requested_delta_f_hz: float
    effective_delta_f_hz: float | None
    effective_delta_basis: str
    last_old_tune_sample_event_time: datetime | None
    first_new_tune_sample_event_time: datetime | None
    settling_window_s: float
    stream_gap_s: float | None
    transform_version: str
    intervention_artifact_hashes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FeatureMatch:
    matched: bool
    observed_baseband_hz: float | None
    expected_baseband_hz: float
    contrast_db: float | None
    fingerprint_correlation: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class ConfirmationFacts:
    independent_roots: bool
    event_time_valid: bool
    reference_continuous: bool
    perturbed_continuous: bool
    axis_known: bool
    transform_complete: bool
    target_a1: bool
    witness_a1: bool
    command_applied: bool
    witness_b: FeatureMatch
    target_reference_b: FeatureMatch
    target_rf_b: FeatureMatch
    target_baseband_b: FeatureMatch
    target_a2: FeatureMatch
    witness_a2: FeatureMatch
    no_gap: bool
    no_overflow: bool
    controls_exclusive: bool = True


@dataclass(frozen=True, slots=True)
class GateF2Result:
    outcome: OutcomeKind
    plan_hash: str | None
    hypotheses_remaining: tuple[str, ...]
    clause_assessments: tuple[ClauseAssessment, ...]
    segment_receipts: tuple[SegmentReceipt, ...]
    intervention_receipts: tuple[InterventionReceipt, ...]
    evidence_receipt: ConstraintReceipt
    observed: tuple[str, ...]
    derived_from_transform_ledger: tuple[str, ...]
    decided_before_confirmation: tuple[str, ...]
    supports: tuple[str, ...]
    does_not_support: tuple[str, ...]
    abstractions_surviving: tuple[str, ...]
    abstraction_eliminated: str
    shock: str
    phase_reached: GatePhase = GatePhase.EXPERIMENT
    progress: GateProgress | None = None
    phase_clause_assessments: tuple[ClauseAssessment, ...] = ()
    discovery_receipts: tuple[DiscoveryReceipt, ...] = ()


@dataclass(slots=True)
class _SpectralProfile:
    frequencies_hz: np.ndarray
    median_db: np.ndarray
    residual_db: np.ndarray
    first_half_residual_db: np.ndarray
    second_half_residual_db: np.ndarray
    bin_hz: float


@dataclass(slots=True)
class _SegmentArtifact:
    root_id: str
    segment: str
    capture: kiwi.KiwiCapture
    artifact_hash: str
    hashed_before_analysis_at: datetime
    byte_count: int

    def receipt(self) -> SegmentReceipt:
        return SegmentReceipt(
            root_id=self.root_id,
            segment=self.segment,
            artifact_hash=self.artifact_hash,
            hashed_before_analysis_at=self.hashed_before_analysis_at,
            byte_count=self.byte_count,
            event_start=self.capture.event_start,
            event_end=self.capture.event_end,
            center_frequency_hz=self.capture.center_frequency_hz,
            sample_rate_hz=self.capture.sample_rate_hz,
            sequence_range=(self.capture.blocks[0].sequence, self.capture.blocks[-1].sequence),
            transform_version=TRANSFORM_VERSION,
        )


@dataclass(slots=True)
class _RootSequence:
    endpoint: kiwi.KiwiEndpoint
    root_id: str
    sample_rate_hz: float
    status: dict[str, str]
    segments: dict[str, _SegmentArtifact]
    all_blocks: tuple[kiwi.IQBlock, ...]
    command_times: dict[str, datetime]
    requested_centers: dict[str, float]


@dataclass(slots=True)
class _SequenceArtifacts:
    reference: _RootSequence
    perturbed: _RootSequence

    @property
    def segment_receipts(self) -> tuple[SegmentReceipt, ...]:
        receipts: list[SegmentReceipt] = []
        for root in (self.reference, self.perturbed):
            receipts.extend(root.segments[name].receipt() for name in ("A1", "B", "A2"))
        return tuple(receipts)


@dataclass(frozen=True, slots=True)
class _FeatureGeometry:
    baseband_hz: float
    bandwidth_hz: float
    neighbourhood_db: tuple[float, ...]
    morphology_db: tuple[float, float, float]
    contrast_interval_db: tuple[float, float]
    uncertainty_hz: float
    cross_root_correlation: float


@dataclass(frozen=True, slots=True)
class _PairGeometry:
    target: _FeatureGeometry
    witness: _FeatureGeometry
    center_a_hz: float
    delta_f_hz: float
    prediction_tolerance_hz: float
    baseline_hashes: tuple[str, str]
    falsification_rank: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class _QualificationCandidate:
    reference: kiwi.KiwiEndpoint
    perturbed: kiwi.KiwiEndpoint
    geometry: _PairGeometry
    axis_orientation: int
    target: FeatureFingerprint
    witness: FeatureFingerprint
    qualification_hashes: tuple[str, ...]
    qualified_at: datetime
    expires_at: datetime


def _capture_profile(capture: kiwi.KiwiCapture, mother: MotherPlan) -> _SpectralProfile:
    audit_plan = kiwi.ScoutPlan(
        center_frequencies_hz=(capture.center_frequency_hz,),
        scout_duration_s=mother.qualification_duration_s,
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        region_shapes=((3, 2),),
        null_shift_count=1,
        significance_alpha=1.0,
        max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
        max_arrival_latency_s=mother.maximum_arrival_latency_s,
        min_overlap_s=min(1.5, mother.qualification_duration_s / 2.0),
    )
    audit = kiwi.audit_capture(capture, audit_plan)
    if not audit.usable or not audit.blocks:
        raise ValueError("capture does not contain one auditable continuous IQ segment")
    samples = np.concatenate([block.samples for block in audit.blocks])
    if len(samples) < mother.nperseg * 2:
        raise ValueError("capture is too short for the frozen fingerprint geometry")
    frequencies, _times, spectrum = signal.stft(
        samples,
        fs=capture.sample_rate_hz,
        window="hann",
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        return_onesided=False,
        boundary=None,
        padded=False,
    )
    frequencies = np.fft.fftshift(frequencies)
    spectrum = np.fft.fftshift(spectrum, axes=0)
    power_db = 10.0 * np.log10(np.maximum(np.abs(spectrum) ** 2, 1e-15))
    median_db = np.median(power_db, axis=1)
    half = max(1, power_db.shape[1] // 2)
    first = np.median(power_db[:, :half], axis=1)
    second = np.median(power_db[:, half:], axis=1)
    kernel = min(63, len(median_db) // 2 * 2 - 1)
    kernel = max(5, kernel)
    if kernel % 2 == 0:
        kernel -= 1
    baseline = signal.medfilt(median_db, kernel_size=kernel)
    first_baseline = signal.medfilt(first, kernel_size=kernel)
    second_baseline = signal.medfilt(second, kernel_size=kernel)
    bin_hz = float(np.median(np.diff(frequencies)))
    return _SpectralProfile(
        frequencies.astype(float),
        median_db.astype(float),
        (median_db - baseline).astype(float),
        (first - first_baseline).astype(float),
        (second - second_baseline).astype(float),
        abs(bin_hz),
    )


def _normalized_neighbourhood(values: np.ndarray, index: int, radius: int = 5) -> tuple[float, ...] | None:
    if index - radius < 0 or index + radius >= len(values):
        return None
    patch = values[index - radius : index + radius + 1].astype(float)
    patch -= float(np.median(patch))
    scale = float(np.linalg.norm(patch))
    if scale <= 1e-12:
        return None
    return tuple(float(value / scale) for value in patch)


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    a = np.asarray(left, dtype=float)
    b = np.asarray(right, dtype=float)
    if len(a) != len(b) or len(a) < 3 or np.std(a) <= 1e-12 or np.std(b) <= 1e-12:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def _profile_on_grid(profile: _SpectralProfile, frequencies: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    return (
        np.interp(frequencies, profile.frequencies_hz, profile.residual_db),
        np.interp(frequencies, profile.frequencies_hz, profile.first_half_residual_db),
        np.interp(frequencies, profile.frequencies_hz, profile.second_half_residual_db),
    )


def find_target_and_witness(
    left: kiwi.KiwiCapture,
    right: kiwi.KiwiCapture,
    mother: MotherPlan,
) -> _PairGeometry:
    """Select two stable common structures; signal strength is the last tie-break."""

    if left.endpoint.host == right.endpoint.host and left.endpoint.port == right.endpoint.port:
        raise ValueError("the two measurement roots are not independent")
    if abs(left.center_frequency_hz - right.center_frequency_hz) > 0.5:
        raise ValueError("baseline roots do not share a declared acquisition center")
    # Both ephemeral artifacts are hashed before the first spectral transform.
    baseline_hashes = (kiwi._capture_hash(left), kiwi._capture_hash(right))
    lp = _capture_profile(left, mother)
    rp = _capture_profile(right, mother)
    low = max(float(lp.frequencies_hz[0]), float(rp.frequencies_hz[0]))
    high = min(float(lp.frequencies_hz[-1]), float(rp.frequencies_hz[-1]))
    common_bin = max(lp.bin_hz, rp.bin_hz)
    count = int(math.floor((high - low) / common_bin)) + 1
    if count < 64:
        raise ValueError("no sufficiently resolved common baseband grid")
    frequencies = low + np.arange(count, dtype=float) * common_bin
    l_med, l_first, l_second = _profile_on_grid(lp, frequencies)
    r_med, r_first, r_second = _profile_on_grid(rp, frequencies)
    joint = np.minimum(l_med, r_med)
    margin = max(mother.guard_bins, 6)
    valid = np.ones(len(joint), dtype=bool)
    valid[:margin] = False
    valid[-margin:] = False
    valid[np.abs(frequencies) <= mother.guard_bins * common_bin] = False
    masked = np.where(valid, joint, -1e9)
    peak_indices, properties = signal.find_peaks(
        masked,
        height=mother.minimum_contrast_db,
        distance=max(3, mother.guard_bins // 2),
    )
    geometries: list[_FeatureGeometry] = []
    peak_widths = (
        signal.peak_widths(masked, peak_indices, rel_height=0.5)[0]
        if len(peak_indices)
        else np.asarray([], dtype=float)
    )
    for ordinal, index in enumerate(peak_indices):
        left_patch = _normalized_neighbourhood(l_med, int(index))
        right_patch = _normalized_neighbourhood(r_med, int(index))
        if left_patch is None or right_patch is None:
            continue
        corr = _correlation(left_patch, right_patch)
        first_contrast = float(min(l_first[index], r_first[index]))
        second_contrast = float(min(l_second[index], r_second[index]))
        if corr < mother.minimum_fingerprint_correlation:
            continue
        if min(first_contrast, second_contrast) < mother.minimum_half_contrast_db:
            continue
        joint_patch = tuple(float((a + b) / 2.0) for a, b in zip(left_patch, right_patch))
        geometries.append(
            _FeatureGeometry(
                float(frequencies[index]),
                float(max(common_bin, peak_widths[ordinal] * common_bin)),
                joint_patch,
                (first_contrast, second_contrast, abs(first_contrast - second_contrast)),
                (min(first_contrast, second_contrast), float(joint[index])),
                mother.prediction_tolerance_bins * common_bin,
                corr,
            )
        )
    if len(geometries) < 2:
        raise ValueError("baseline does not contain two distinct stable common structures")

    candidates: list[_PairGeometry] = []
    nyquist_guard = min(abs(low), abs(high)) - mother.guard_bins * common_bin
    for target in geometries:
        for witness in geometries:
            if target is witness:
                continue
            separation = abs(target.baseband_hz - witness.baseband_hz)
            tolerance = max(target.uncertainty_hz, witness.uncertainty_hz)
            if separation <= 4.0 * tolerance:
                continue
            shift_guard = min(
                nyquist_guard - abs(target.baseband_hz),
                nyquist_guard - abs(witness.baseband_hz),
            )
            upper = min(mother.maximum_delta_hz, shift_guard)
            lower = max(mother.minimum_delta_hz, 5.0 * tolerance)
            if upper < lower:
                continue
            delta_bins = math.floor(upper / common_bin)
            delta = delta_bins * common_bin
            if delta < lower:
                continue
            # Strength is deliberately the final component of the rank.
            rank = (
                min(target.cross_root_correlation, witness.cross_root_correlation),
                min(target.contrast_interval_db[0], witness.contrast_interval_db[0]),
                shift_guard,
                separation,
                target.contrast_interval_db[1] + witness.contrast_interval_db[1],
            )
            candidates.append(
                _PairGeometry(
                    target,
                    witness,
                    left.center_frequency_hz,
                    float(delta),
                    tolerance,
                    baseline_hashes,
                    rank,
                )
            )
    if not candidates:
        raise ValueError("no target/witness pair leaves non-overlapping retune predictions and guard band")
    return max(candidates, key=lambda candidate: candidate.falsification_rank)


def _fingerprint_from_geometry(
    geometry: _FeatureGeometry,
    witness_geometry: _FeatureGeometry,
    center_hz: float,
    axis_orientation: int,
) -> FeatureFingerprint:
    return FeatureFingerprint(
        geometry.baseband_hz,
        center_hz + axis_orientation * geometry.baseband_hz,
        geometry.bandwidth_hz,
        geometry.neighbourhood_db,
        geometry.baseband_hz - witness_geometry.baseband_hz,
        geometry.morphology_db,
        geometry.contrast_interval_db,
        geometry.uncertainty_hz,
    )


def match_feature(
    profile: _SpectralProfile,
    fingerprint: FeatureFingerprint,
    expected_baseband_hz: float,
    tolerance_hz: float,
    mother: MotherPlan,
    *,
    witness: bool = False,
) -> FeatureMatch:
    """Search only inside a frozen baseband interval, never on an RF axis."""

    indices = np.flatnonzero(np.abs(profile.frequencies_hz - expected_baseband_hz) <= tolerance_hz)
    if len(indices) == 0:
        return FeatureMatch(False, None, expected_baseband_hz, None, None, "prediction interval is outside the baseband grid")
    best: tuple[float, float, int] | None = None
    for index in indices:
        patch = _normalized_neighbourhood(profile.residual_db, int(index))
        if patch is None:
            continue
        corr = _correlation(fingerprint.local_spectral_neighbourhood_db, patch)
        contrast = float(profile.residual_db[index])
        candidate = (corr, contrast, int(index))
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None:
        return FeatureMatch(False, None, expected_baseband_hz, None, None, "no complete local fingerprint patch in prediction interval")
    corr, contrast, index = best
    contrast_floor = mother.minimum_witness_contrast_db if witness else mother.minimum_contrast_db
    matched = corr >= mother.minimum_fingerprint_correlation and contrast >= contrast_floor
    return FeatureMatch(
        matched,
        float(profile.frequencies_hz[index]),
        expected_baseband_hz,
        contrast,
        corr,
        "frozen fingerprint and contrast satisfied" if matched else "frozen fingerprint or contrast not satisfied",
    )


def learn_axis_orientation_from_witness(
    witness: FeatureFingerprint,
    profile_b: _SpectralProfile,
    delta_f_hz: float,
    tolerance_hz: float,
    mother: MotherPlan,
) -> tuple[int, FeatureMatch]:
    """Use only the orthogonal witness to choose one of the two signed axes."""

    plus_orientation = match_feature(
        profile_b,
        witness,
        witness.baseband_position_a_hz - delta_f_hz,
        tolerance_hz,
        mother,
        witness=True,
    )
    minus_orientation = match_feature(
        profile_b,
        witness,
        witness.baseband_position_a_hz + delta_f_hz,
        tolerance_hz,
        mother,
        witness=True,
    )
    if plus_orientation.matched == minus_orientation.matched:
        raise ValueError("qualification witness does not uniquely determine axis orientation")
    return (1, plus_orientation) if plus_orientation.matched else (-1, minus_orientation)


@dataclass(slots=True)
class _WaterfallArtifact:
    endpoint: kiwi.KiwiEndpoint
    bandwidth_hz: float
    frames: np.ndarray
    artifact_hash: str
    byte_count: int
    arrived_start: datetime
    arrived_end: datetime


def _parse_directory_endpoints(text: str, mother: MotherPlan) -> tuple[kiwi.KiwiEndpoint, ...]:
    urls = re.findall(r"https?://[^\s<>\"']+", text)
    endpoints: dict[tuple[str, int], kiwi.KiwiEndpoint] = {}
    for raw in urls:
        parsed = urlparse(raw.rstrip("/),;"))
        if parsed.scheme != "http" or not parsed.hostname:
            continue
        port = parsed.port or 80
        key = (parsed.hostname.lower(), port)
        endpoints[key] = kiwi.KiwiEndpoint(parsed.hostname.lower(), parsed.hostname, port)
    # Directory order must not become an implicit planner preference.
    ordered = sorted(endpoints.values(), key=lambda endpoint: sha256(f"{endpoint.host}:{endpoint.port}".encode()).hexdigest())
    return tuple(ordered[: mother.maximum_directory_candidates])


def discover_directory_attempt(
    mother: MotherPlan,
    *,
    retry_index: int,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> DiscoveryAttempt:
    """Read one listing route and return an atomic result, including failures."""

    provider = "KiwiSDR public directory"
    inventory_root = "kiwisdr-public-registry"
    access_mode = "public HTTPS GET"
    started = _utc(now())
    try:
        request = Request(mother.directory_url, headers={"User-Agent": "Satellite-RF-Observatory-Gate-F2/0.1"})
        with urlopen(request, timeout=8.0) as response:
            payload = response.read()
            status_code = getattr(response, "status", 200)
        completed = _utc(now())
        response_hash = sha256(payload).hexdigest()
        if status_code is not None and not 200 <= int(status_code) < 300:
            receipt = DiscoveryReceipt(
                provider, inventory_root, mother.directory_url, access_mode,
                started, completed, DiscoveryResponseStatus.PROTOCOL_ERROR, 0,
                response_hash, "HTTPStatusError", f"HTTP status {status_code}",
                retry_index, completed + timedelta(seconds=mother.offer_ttl_s),
            )
            return DiscoveryAttempt(receipt, ())
        try:
            text = payload.decode("utf-8", errors="strict")
            endpoints = _parse_directory_endpoints(text, mother)
        except Exception as error:
            receipt = DiscoveryReceipt(
                provider, inventory_root, mother.directory_url, access_mode,
                started, completed, DiscoveryResponseStatus.DESCRIPTION_ERROR, 0,
                response_hash, type(error).__name__, str(error), retry_index,
                completed + timedelta(seconds=mother.offer_ttl_s),
            )
            return DiscoveryAttempt(receipt, ())
        result_status = (
            DiscoveryResponseStatus.VALID_CANDIDATE_RESULT
            if endpoints
            else DiscoveryResponseStatus.VALID_EMPTY_RESULT
        )
        receipt = DiscoveryReceipt(
            provider, inventory_root, mother.directory_url, access_mode,
            started, completed, result_status, len(endpoints), response_hash,
            None, None, retry_index,
            completed + timedelta(seconds=mother.offer_ttl_s),
        )
        return DiscoveryAttempt(receipt, endpoints)
    except HTTPError as error:
        completed = _utc(now())
        try:
            payload = error.read()
        except Exception:
            payload = None
        receipt = DiscoveryReceipt(
            provider, inventory_root, mother.directory_url, access_mode,
            started, completed, DiscoveryResponseStatus.PROTOCOL_ERROR, 0,
            sha256(payload).hexdigest() if payload is not None else None,
            type(error).__name__, str(error), retry_index,
            completed + timedelta(seconds=mother.offer_ttl_s),
        )
        return DiscoveryAttempt(receipt, ())
    except (URLError, OSError, TimeoutError) as error:
        completed = _utc(now())
        receipt = DiscoveryReceipt(
            provider, inventory_root, mother.directory_url, access_mode,
            started, completed, DiscoveryResponseStatus.TRANSPORT_ERROR, 0,
            None, type(error).__name__, str(error), retry_index,
            completed + timedelta(seconds=mother.offer_ttl_s),
        )
        return DiscoveryAttempt(receipt, ())
    except Exception as error:
        completed = _utc(now())
        receipt = DiscoveryReceipt(
            provider, inventory_root, mother.directory_url, access_mode,
            started, completed, DiscoveryResponseStatus.DESCRIPTION_ERROR, 0,
            None, type(error).__name__, str(error), retry_index,
            completed + timedelta(seconds=mother.offer_ttl_s),
        )
        return DiscoveryAttempt(receipt, ())


def discover_directory_endpoints(mother: MotherPlan) -> tuple[kiwi.KiwiEndpoint, ...]:
    """Compatibility helper: one atomic attempt, with no hidden retry."""

    attempt = discover_directory_attempt(mother, retry_index=0)
    if not attempt.receipt.successful:
        raise RuntimeError(
            f"{attempt.receipt.response_status.value}: "
            f"{attempt.receipt.error_class}: {attempt.receipt.error_detail}"
        )
    return attempt.candidates


def _status_location(status: dict[str, str]) -> tuple[float, float] | None:
    for key in ("gps", "loc", "location"):
        value = status.get(key)
        if not value:
            continue
        numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", value)
        if len(numbers) >= 2:
            lat, lon = float(numbers[0]), float(numbers[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    return None


def qualify_endpoint_descriptions(
    endpoints: Sequence[kiwi.KiwiEndpoint],
    mother: MotherPlan,
) -> tuple[EndpointCapability, ...]:
    def one(endpoint: kiwi.KiwiEndpoint) -> EndpointCapability:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=mother.offer_ttl_s)
        try:
            status = kiwi.fetch_kiwi_status(endpoint, timeout_s=5.0)
            artifact_hash = _hash(status)
            ext_api = int(status.get("ext_api", "0") or 0)
            gps_good_value = status.get("gps_good")
            gps_good = None if gps_good_value is None else int(gps_good_value or 0) > 0
            location = _status_location(status)
            if ext_api <= 0:
                return EndpointCapability(endpoint, CapabilityState.CAPABILITY_REJECTED, now, artifact_hash, ext_api, gps_good, location, "no external API slot", expires_at)
            if gps_good is False:
                return EndpointCapability(endpoint, CapabilityState.CAPABILITY_REJECTED, now, artifact_hash, ext_api, gps_good, location, "GNSS status is not good", expires_at)
            if location is None:
                return EndpointCapability(endpoint, CapabilityState.CAPABILITY_REJECTED, now, artifact_hash, ext_api, gps_good, location, "hardware location unavailable; independence cannot be checked", expires_at)
            return EndpointCapability(endpoint, CapabilityState.CAPABILITY_QUALIFIED, now, artifact_hash, ext_api, gps_good, location, "description closes API/GNSS/location admission", expires_at)
        except Exception as error:
            return EndpointCapability(endpoint, CapabilityState.QUALIFICATION_ERROR, now, _hash({"endpoint": asdict(endpoint), "error_type": type(error).__name__}), None, None, None, str(error), expires_at)

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(endpoints)))) as pool:
        futures = [pool.submit(one, endpoint) for endpoint in endpoints]
        return tuple(future.result() for future in as_completed(futures))


def _haversine_km(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, left)
    lat2, lon2 = map(math.radians, right)
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0 * 2.0 * math.asin(min(1.0, math.sqrt(value)))


def enumerate_hardware_pairs(
    capabilities: Sequence[EndpointCapability],
    mother: MotherPlan,
    *,
    at: datetime | None = None,
) -> tuple[tuple[EndpointCapability, EndpointCapability], ...]:
    evaluated_at = _utc(at or datetime.now(timezone.utc))
    qualified = [
        item for item in capabilities
        if item.state is CapabilityState.CAPABILITY_QUALIFIED
        and item.location is not None
        and _utc(item.expires_at) > evaluated_at
    ]
    pairs: list[tuple[float, str, EndpointCapability, EndpointCapability]] = []
    for index, left in enumerate(qualified):
        for right in qualified[index + 1 :]:
            if left.endpoint.host.lower() == right.endpoint.host.lower():
                continue
            distance = _haversine_km(left.location, right.location)  # type: ignore[arg-type]
            if not mother.minimum_hardware_separation_km <= distance <= mother.maximum_pair_separation_km:
                continue
            tie = f"{left.endpoint.host}:{left.endpoint.port}|{right.endpoint.host}:{right.endpoint.port}"
            pairs.append((distance, tie, left, right))
    pairs.sort(key=lambda item: (item[0], item[1]))
    return tuple((left, right) for _distance, _tie, left, right in pairs[: mother.maximum_pairs])


def _capture_waterfall(endpoint: kiwi.KiwiEndpoint, frame_count: int) -> _WaterfallArtifact:
    import websocket

    token = (int(time.time()) + (hash((endpoint.host, endpoint.port, "gate-f2-wf")) & 0xFFFF)) & 0xFFFFFFFF
    ws = websocket.create_connection(
        f"ws://{endpoint.host}:{endpoint.port}/{token}/W/F",
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
    )
    ws.send("SET auth t=kiwi p=")
    frames: list[np.ndarray] = []
    digest = sha256()
    byte_count = 0
    bandwidth_hz = 30_000_000.0
    arrived_start: datetime | None = None
    arrived_end: datetime | None = None
    configured = False
    try:
        while len(frames) < frame_count:
            message = ws.recv()
            arrival = datetime.now(timezone.utc)
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
                    raise RuntimeError(f"{endpoint.name} rejected waterfall access")
                if "bandwidth" in params:
                    bandwidth_hz = float(params["bandwidth"])
                if "wf_setup" in params and not configured:
                    center_khz = bandwidth_hz / 2000.0
                    for command in (
                        "SET ident_user=Satellite-RF-Observatory_Gate_F2",
                        f"SET zoom=0 cf={center_khz:.6f}",
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
                frames.append(np.frombuffer(data, dtype=np.uint8).astype(float).copy())
                arrived_start = arrived_start or arrival
                arrived_end = arrival
            ws.send("SET keepalive")
    finally:
        try:
            ws.close()
        except Exception:
            pass
    if not frames or arrived_start is None or arrived_end is None:
        raise RuntimeError(f"{endpoint.name} produced no waterfall frames")
    width = min(len(frame) for frame in frames)
    return _WaterfallArtifact(
        endpoint,
        bandwidth_hz,
        np.stack([frame[:width] for frame in frames]),
        digest.hexdigest(),
        byte_count,
        arrived_start,
        arrived_end,
    )


def waterfall_center_candidates(
    left: _WaterfallArtifact,
    right: _WaterfallArtifact,
    mother: MotherPlan,
) -> tuple[float, ...]:
    common_high = min(left.bandwidth_hz, right.bandwidth_hz)
    bins = min(left.frames.shape[1], right.frames.shape[1])
    frequencies = np.linspace(0.0, common_high, bins, endpoint=False) + common_high / bins / 2.0
    left_profile = np.median(left.frames, axis=0)
    right_profile = np.median(right.frames, axis=0)

    def robust(values: np.ndarray) -> np.ndarray:
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        return (values - median) / max(1.0, 1.4826 * mad)

    joint = np.minimum(robust(left_profile), robust(right_profile))
    valid = (frequencies >= 50_000.0) & (frequencies <= common_high - 50_000.0)
    peaks, _properties = signal.find_peaks(np.where(valid, joint, -1e9), height=2.5, distance=2)
    ranked = sorted(peaks, key=lambda index: (joint[index], -frequencies[index]), reverse=True)
    bin_hz = common_high / bins
    centers: list[float] = []
    # Three deterministic sub-bin centers avoid treating a 30 kHz waterfall bin
    # as a precise frequency estimate. This expansion is frozen before data.
    for index in ranked:
        for offset in (-bin_hz / 3.0, 0.0, bin_hz / 3.0):
            center = float(frequencies[index] + offset)
            if 10_000.0 <= center <= common_high - 10_000.0 and all(abs(center - old) > 1000.0 for old in centers):
                centers.append(center)
            if len(centers) >= mother.maximum_iq_centers:
                return tuple(centers)
    return tuple(centers)


@dataclass(slots=True)
class _SegmentAccumulator:
    blocks: list[kiwi.IQBlock]
    digest: object
    byte_count: int = 0

    @classmethod
    def create(cls) -> "_SegmentAccumulator":
        return cls([], sha256(), 0)

    def append(self, block: kiwi.IQBlock, raw_body: bytes) -> None:
        self.blocks.append(block)
        self.digest.update(raw_body)  # type: ignore[attr-defined]
        self.byte_count += len(raw_body)


def _tune_command(center_hz: float) -> str:
    return f"SET mod=iq low_cut=-5000 high_cut=5000 freq={center_hz / 1000.0:.6f}"


def _capture_sequence_root(
    endpoint: kiwi.KiwiEndpoint,
    center_a_hz: float,
    delta_f_hz: float,
    segment_duration_s: float,
    settling_s: float,
    perturbed: bool,
    start_event: Event,
    ready_event: Event,
    mother: MotherPlan,
) -> _RootSequence:
    import websocket

    status = kiwi.fetch_kiwi_status(endpoint)
    if int(status.get("ext_api", "0") or 0) <= 0:
        raise RuntimeError(f"{endpoint.name} has no external API slot")
    token = (int(time.time()) + (hash((endpoint.host, endpoint.port, "gate-f2-seq", perturbed)) & 0xFFFF)) & 0xFFFFFFFF
    ws = websocket.create_connection(
        f"ws://{endpoint.host}:{endpoint.port}/{token}/SND",
        timeout=8.0,
        origin=f"http://{endpoint.host}:{endpoint.port}",
        http_proxy_host=None,
        enable_multithread=True,
    )
    ws.send("SET auth t=kiwi p=")
    sample_rate = 0.0
    start_monotonic: float | None = None
    sent_b = False
    sent_a2 = False
    command_times: dict[str, datetime] = {}
    requested_centers = {"A1": center_a_hz, "B": center_a_hz + delta_f_hz if perturbed else center_a_hz, "A2": center_a_hz}
    accumulators = {name: _SegmentAccumulator.create() for name in ("A1", "B", "A2")}
    all_blocks: list[kiwi.IQBlock] = []
    last_keepalive = 0.0
    total_duration = 3.0 * segment_duration_s + 2.0 * settling_s
    try:
        while True:
            message = ws.recv()
            arrival = datetime.now(timezone.utc)
            now_monotonic = time.monotonic()
            if isinstance(message, str):
                message = message.encode("latin-1")
            if not isinstance(message, bytes) or len(message) < 3:
                continue
            tag, body = message[:3], message[3:]
            if tag == b"MSG":
                params = kiwi._msg_params(body[1:])
                if params.get("too_busy") is not None:
                    raise RuntimeError(f"{endpoint.name} is busy")
                if params.get("badp") not in (None, "0"):
                    raise RuntimeError(f"{endpoint.name} rejected the public connection: badp={params['badp']}")
                if "audio_rate" in params:
                    ws.send(f"SET AR OK in={int(float(params['audio_rate']))} out=44100")
                if "sample_rate" in params and sample_rate == 0.0:
                    sample_rate = float(params["sample_rate"])
                    for command in (
                        "SET squelch=0 max=0",
                        "SET genattn=0",
                        "SET gen=0 mix=-1",
                        "SET ident_user=Satellite-RF-Observatory_Gate_F2",
                        _tune_command(center_a_hz),
                        "SET agc=1 hang=0 thresh=-100 slope=6 decay=1000 manGain=50",
                        "SET compression=0",
                        "SET keepalive",
                    ):
                        ws.send(command)
            elif tag == b"SND" and sample_rate > 0.0:
                block = kiwi._decode_iq_block(body, sample_rate, arrival)
                if block.gps_timestamp_available and block.gps_solution_age_s <= mother.maximum_gps_solution_age_s:
                    ready_event.set()
                if start_event.is_set() and start_monotonic is None:
                    start_monotonic = now_monotonic
                if start_monotonic is not None:
                    elapsed = now_monotonic - start_monotonic
                    if perturbed and elapsed >= segment_duration_s and not sent_b:
                        ws.send(_tune_command(center_a_hz + delta_f_hz))
                        command_times["A_TO_B"] = datetime.now(timezone.utc)
                        sent_b = True
                    second_boundary = 2.0 * segment_duration_s + settling_s
                    if perturbed and elapsed >= second_boundary and not sent_a2:
                        ws.send(_tune_command(center_a_hz))
                        command_times["B_TO_A"] = datetime.now(timezone.utc)
                        sent_a2 = True
                    if elapsed < segment_duration_s:
                        phase = "A1"
                    elif elapsed < segment_duration_s + settling_s:
                        phase = None
                    elif elapsed < 2.0 * segment_duration_s + settling_s:
                        phase = "B"
                    elif elapsed < 2.0 * segment_duration_s + 2.0 * settling_s:
                        phase = None
                    elif elapsed < total_duration:
                        phase = "A2"
                    else:
                        break
                    all_blocks.append(block)
                    if phase is not None:
                        accumulators[phase].append(block, body)
            if now_monotonic - last_keepalive >= 1.0:
                ws.send("SET keepalive")
                last_keepalive = now_monotonic
    finally:
        try:
            ws.close()
        except Exception:
            pass

    if sample_rate <= 0 or not all_blocks:
        raise RuntimeError(f"{endpoint.name} returned no sequence IQ")
    root_id = f"kiwi:{endpoint.host}:{endpoint.port}"
    artifacts: dict[str, _SegmentArtifact] = {}
    hashed_at = datetime.now(timezone.utc)
    for phase, accumulator in accumulators.items():
        if not accumulator.blocks:
            raise RuntimeError(f"{endpoint.name} has no {phase} blocks")
        blocks = tuple(accumulator.blocks)
        capture = kiwi.KiwiCapture(
            endpoint,
            requested_centers[phase],
            sample_rate,
            status,
            blocks,
            blocks[0].arrived_at or hashed_at,
            blocks[-1].arrived_at or hashed_at,
        )
        artifacts[phase] = _SegmentArtifact(
            root_id,
            phase,
            capture,
            accumulator.digest.hexdigest(),  # type: ignore[attr-defined]
            hashed_at,
            accumulator.byte_count,
        )
    return _RootSequence(endpoint, root_id, sample_rate, status, artifacts, tuple(all_blocks), command_times, requested_centers)


def capture_dual_sequence(
    endpoints: tuple[kiwi.KiwiEndpoint, kiwi.KiwiEndpoint],
    center_a_hz: float,
    delta_f_hz: float,
    segment_duration_s: float,
    settling_s: float,
    mother: MotherPlan,
) -> _SequenceArtifacts:
    start_event = Event()
    ready = (Event(), Event())
    with ThreadPoolExecutor(max_workers=2) as pool:
        reference_future = pool.submit(
            _capture_sequence_root,
            endpoints[0], center_a_hz, delta_f_hz, segment_duration_s, settling_s, False,
            start_event, ready[0], mother,
        )
        perturbed_future = pool.submit(
            _capture_sequence_root,
            endpoints[1], center_a_hz, delta_f_hz, segment_duration_s, settling_s, True,
            start_event, ready[1], mother,
        )
        if not ready[0].wait(12.0) or not ready[1].wait(12.0):
            start_event.set()
            raise RuntimeError("dual sequence did not reach GNSS temporal readiness")
        start_event.set()
        reference = reference_future.result()
        perturbed_root = perturbed_future.result()
    return _SequenceArtifacts(reference, perturbed_root)


def _sequence_integrity(root: _RootSequence, mother: MotherPlan) -> tuple[bool, bool, bool]:
    blocks = root.all_blocks
    if not blocks:
        return False, False, False
    tolerance_s = max(2.0 / root.sample_rate_hz, 0.001)
    event_valid = all(
        block.gps_timestamp_available
        and block.gps_solution_age_s <= mother.maximum_gps_solution_age_s
        and block.arrived_at is not None
        and -tolerance_s <= (block.arrived_at - block.event_end).total_seconds() <= mother.maximum_arrival_latency_s
        for block in blocks
    )
    continuous = True
    for previous, current in zip(blocks, blocks[1:]):
        if current.sequence != ((previous.sequence + 1) & 0xFFFFFFFF):
            continuous = False
        if abs((current.event_start - previous.event_end).total_seconds()) > tolerance_s:
            continuous = False
    no_overflow = not any(block.adc_overflow for block in blocks)
    return event_valid, continuous, no_overflow


def _boundary_from_command(root: _RootSequence, command_at: datetime) -> tuple[datetime | None, datetime | None, float | None]:
    before = [block for block in root.all_blocks if block.arrived_at is not None and block.arrived_at <= command_at]
    after = [block for block in root.all_blocks if block.arrived_at is not None and block.arrived_at > command_at]
    last = before[-1].event_end if before else None
    first = after[0].event_start if after else None
    gap = None if last is None or first is None else (first - last).total_seconds()
    return last, first, gap


def _intervention_receipts(
    plan: FrozenPlan,
    sequence: _SequenceArtifacts,
    witness_b: FeatureMatch,
    witness_a2: FeatureMatch,
) -> tuple[InterventionReceipt, InterventionReceipt]:
    perturbed = sequence.perturbed
    b_hash = perturbed.segments["B"].artifact_hash
    a1_hash = perturbed.segments["A1"].artifact_hash
    a2_hash = perturbed.segments["A2"].artifact_hash
    command_ab = perturbed.command_times.get("A_TO_B")
    command_ba = perturbed.command_times.get("B_TO_A")
    if command_ab is None or command_ba is None:
        raise ValueError("confirmation did not record both retune commands")
    last_ab, first_ab_wire, gap_ab = _boundary_from_command(perturbed, command_ab)
    last_ba, first_ba_wire, gap_ba = _boundary_from_command(perturbed, command_ba)
    first_b_evidence = perturbed.segments["B"].capture.event_start if witness_b.matched else None
    first_a2_evidence = perturbed.segments["A2"].capture.event_start if witness_a2.matched else None
    observed_b_translation = (
        None if witness_b.observed_baseband_hz is None
        else witness_b.observed_baseband_hz - plan.witness.baseband_position_a_hz
    )
    effective_ab = None if observed_b_translation is None else -plan.axis_orientation * observed_b_translation
    observed_return_translation = (
        None
        if witness_b.observed_baseband_hz is None or witness_a2.observed_baseband_hz is None
        else witness_a2.observed_baseband_hz - witness_b.observed_baseband_hz
    )
    effective_ba = None if observed_return_translation is None else -plan.axis_orientation * observed_return_translation
    return (
        InterventionReceipt(
            "A_TO_B", command_ab, None, "NOT_AVAILABLE_IN_KIWI_PROTOCOL",
            plan.center_a_hz, plan.center_b_hz, None, plan.delta_f_hz,
            effective_ab, "sample-derived from frozen witness translation" if effective_ab is not None else "UNRESOLVED",
            last_ab, first_b_evidence or first_ab_wire, plan.settling_s, gap_ab,
            TRANSFORM_VERSION, (a1_hash, b_hash),
        ),
        InterventionReceipt(
            "B_TO_A", command_ba, None, "NOT_AVAILABLE_IN_KIWI_PROTOCOL",
            plan.center_b_hz, plan.center_a_hz, None, -plan.delta_f_hz,
            effective_ba, "sample-derived from frozen witness return" if effective_ba is not None else "UNRESOLVED",
            last_ba, first_a2_evidence or first_ba_wire, plan.settling_s, gap_ba,
            TRANSFORM_VERSION, (b_hash, a2_hash),
        ),
    )


def qualify_geometry_orientation(
    endpoints: tuple[kiwi.KiwiEndpoint, kiwi.KiwiEndpoint],
    geometry: _PairGeometry,
    mother: MotherPlan,
) -> _QualificationCandidate:
    # Absolute RF is intentionally not used here. The provisional fingerprint
    # only supplies the witness's frozen raw-bin neighbourhood.
    provisional_witness = _fingerprint_from_geometry(
        geometry.witness, geometry.target, geometry.center_a_hz, 1
    )
    diagnostic = capture_dual_sequence(
        endpoints,
        geometry.center_a_hz,
        geometry.delta_f_hz,
        mother.diagnostic_segment_s,
        mother.settling_s,
        mother,
    )
    try:
        profile_b = _capture_profile(diagnostic.perturbed.segments["B"].capture, mother)
        orientation, witness_b = learn_axis_orientation_from_witness(
            provisional_witness,
            profile_b,
            geometry.delta_f_hz,
            geometry.prediction_tolerance_hz,
            mother,
        )
        profile_a1 = _capture_profile(diagnostic.perturbed.segments["A1"].capture, mother)
        profile_a2 = _capture_profile(diagnostic.perturbed.segments["A2"].capture, mother)
        if not match_feature(profile_a1, provisional_witness, provisional_witness.baseband_position_a_hz, geometry.prediction_tolerance_hz, mother, witness=True).matched:
            raise ValueError("qualification witness is not detectable in diagnostic A1")
        if not match_feature(profile_a2, provisional_witness, provisional_witness.baseband_position_a_hz, geometry.prediction_tolerance_hz, mother, witness=True).matched:
            raise ValueError("qualification witness does not return in diagnostic A2")
        target = _fingerprint_from_geometry(geometry.target, geometry.witness, geometry.center_a_hz, orientation)
        witness = _fingerprint_from_geometry(geometry.witness, geometry.target, geometry.center_a_hz, orientation)
        hashes = geometry.baseline_hashes + tuple(receipt.artifact_hash for receipt in diagnostic.segment_receipts)
        qualified_at = datetime.now(timezone.utc)
        return _QualificationCandidate(
            endpoints[0], endpoints[1], geometry, orientation, target, witness,
            tuple(dict.fromkeys(hashes)), qualified_at,
            qualified_at + timedelta(seconds=mother.offer_ttl_s),
        )
    finally:
        del diagnostic


def evaluate_sequence(
    plan: FrozenPlan,
    sequence: _SequenceArtifacts,
    mother: MotherPlan,
) -> GateF2Result:
    reference_profiles = {
        name: _capture_profile(sequence.reference.segments[name].capture, mother)
        for name in ("A1", "B", "A2")
    }
    perturbed_profiles = {
        name: _capture_profile(sequence.perturbed.segments[name].capture, mother)
        for name in ("A1", "B", "A2")
    }
    target_a1_ref = match_feature(reference_profiles["A1"], plan.target, plan.target.baseband_position_a_hz, plan.prediction_tolerance_hz, mother)
    target_a1_perturbed = match_feature(perturbed_profiles["A1"], plan.target, plan.target.baseband_position_a_hz, plan.prediction_tolerance_hz, mother)
    witness_a1 = match_feature(perturbed_profiles["A1"], plan.witness, plan.witness.baseband_position_a_hz, plan.prediction_tolerance_hz, mother, witness=True)
    expected_witness_b = plan.witness.baseband_position_a_hz + plan.axis_orientation * (-plan.delta_f_hz)
    witness_b = match_feature(perturbed_profiles["B"], plan.witness, expected_witness_b, plan.prediction_tolerance_hz, mother, witness=True)
    target_reference_b = match_feature(reference_profiles["B"], plan.target, plan.target.baseband_position_a_hz, plan.prediction_tolerance_hz, mother)
    target_rf_b = match_feature(perturbed_profiles["B"], plan.target, plan.rf_frame_target_b_hz, plan.prediction_tolerance_hz, mother)
    target_baseband_b = match_feature(perturbed_profiles["B"], plan.target, plan.baseband_frame_target_b_hz, plan.prediction_tolerance_hz, mother)
    wrong_sign_b = match_feature(perturbed_profiles["B"], plan.target, plan.wrong_sign_target_b_hz, plan.prediction_tolerance_hz, mother)
    wrong_magnitude_b = match_feature(perturbed_profiles["B"], plan.target, plan.wrong_magnitude_target_b_hz, plan.prediction_tolerance_hz, mother)
    off_feature_b = match_feature(perturbed_profiles["B"], plan.target, plan.off_feature_baseband_hz, plan.prediction_tolerance_hz, mother)
    if witness_b.observed_baseband_hz is not None:
        if target_rf_b.observed_baseband_hz is not None:
            observed_spacing = target_rf_b.observed_baseband_hz - witness_b.observed_baseband_hz
            expected_spacing = plan.target.baseband_position_a_hz - plan.witness.baseband_position_a_hz
            if abs(observed_spacing - expected_spacing) > 2.0 * plan.prediction_tolerance_hz:
                target_rf_b = replace(target_rf_b, matched=False, reason="relative target/witness spacing violates RF-frame control")
        if target_baseband_b.observed_baseband_hz is not None:
            observed_spacing = target_baseband_b.observed_baseband_hz - witness_b.observed_baseband_hz
            expected_spacing = (
                plan.target.baseband_position_a_hz
                - plan.witness.baseband_position_a_hz
                + plan.axis_orientation * plan.delta_f_hz
            )
            if abs(observed_spacing - expected_spacing) > 2.0 * plan.prediction_tolerance_hz:
                target_baseband_b = replace(target_baseband_b, matched=False, reason="relative target/witness spacing violates baseband-frame control")
    target_a2 = match_feature(perturbed_profiles["A2"], plan.target, plan.target.baseband_position_a_hz, plan.prediction_tolerance_hz, mother)
    witness_a2 = match_feature(perturbed_profiles["A2"], plan.witness, plan.witness.baseband_position_a_hz, plan.prediction_tolerance_hz, mother, witness=True)
    ref_event, ref_continuous, ref_overflow = _sequence_integrity(sequence.reference, mother)
    pert_event, pert_continuous, pert_overflow = _sequence_integrity(sequence.perturbed, mother)
    interventions = _intervention_receipts(plan, sequence, witness_b, witness_a2)
    facts = ConfirmationFacts(
        sequence.reference.root_id != sequence.perturbed.root_id,
        ref_event and pert_event,
        ref_continuous,
        pert_continuous,
        plan.axis_orientation in (-1, 1),
        protocol_audit().exact_verified_point != "" and all(receipt.transform_version == TRANSFORM_VERSION for receipt in sequence.segment_receipts),
        target_a1_ref.matched and target_a1_perturbed.matched,
        witness_a1.matched,
        len(sequence.perturbed.command_times) == 2,
        witness_b,
        target_reference_b,
        target_rf_b,
        target_baseband_b,
        target_a2,
        witness_a2,
        ref_continuous and pert_continuous,
        ref_overflow and pert_overflow,
        not (wrong_sign_b.matched or wrong_magnitude_b.matched or off_feature_b.matched),
    )
    return classify_confirmation(
        plan,
        facts,
        sequence.segment_receipts,
        interventions,
        evaluated_at=datetime.now(timezone.utc),
    )


def freeze_plan(
    mother: MotherPlan,
    reference: kiwi.KiwiEndpoint,
    perturbed: kiwi.KiwiEndpoint,
    center_a_hz: float,
    delta_f_hz: float,
    axis_orientation: int,
    target: FeatureFingerprint,
    witness: FeatureFingerprint,
    *,
    frozen_at: datetime,
    prediction_tolerance_hz: float,
) -> FrozenPlan:
    expected_translation = axis_orientation * (-delta_f_hz)
    return FrozenPlan(
        mother.plan_hash,
        _hash(asdict(protocol_audit())),
        reference,
        perturbed,
        center_a_hz,
        center_a_hz + delta_f_hz,
        delta_f_hz,
        axis_orientation,
        target,
        witness,
        target.baseband_position_a_hz + expected_translation,
        target.baseband_position_a_hz,
        target.baseband_position_a_hz - expected_translation,
        target.baseband_position_a_hz + expected_translation / 2.0,
        target.baseband_position_a_hz + expected_translation * 2.5,
        prediction_tolerance_hz,
        mother.settling_s,
        mother.confirmation_segment_s,
        _utc(frozen_at),
        _utc(frozen_at) + timedelta(seconds=mother.offer_ttl_s),
    )


def classify_confirmation(
    plan: FrozenPlan,
    facts: ConfirmationFacts,
    segment_receipts: tuple[SegmentReceipt, ...],
    intervention_receipts: tuple[InterventionReceipt, ...],
    *,
    evaluated_at: datetime,
) -> GateF2Result:
    """Clause-driven, deterministic classification of the one frozen window."""

    values = {
        "independent_hardware_roots": facts.independent_roots,
        "event_time_valid": facts.event_time_valid,
        "reference_root_continuous": facts.reference_continuous,
        "perturbed_root_continuous": facts.perturbed_continuous,
        "axis_orientation_known": facts.axis_known,
        "transform_ledger_complete": facts.transform_complete,
        "target_detectable_A1": facts.target_a1,
        "witness_detectable_A1": facts.witness_a1,
        "intervention_command_applied": facts.command_applied,
        "witness_translation_valid": facts.witness_b.matched,
        "target_remains_detectable_on_reference_root": facts.target_reference_b.matched,
        "target_matches_RF-frame_prediction_B": facts.target_rf_b.matched,
        "target_matches_baseband-frame_prediction_B": facts.target_baseband_b.matched,
        "target_returns_to_A_prediction": facts.target_a2.matched,
        "witness_returns_to_A_prediction": facts.witness_a2.matched,
        "no_invalidating_gap": facts.no_gap,
        "no_invalidating_overflow": facts.no_overflow,
    }
    prerequisites = {
        "event_time_valid": ("independent_hardware_roots",),
        "reference_root_continuous": ("event_time_valid",),
        "perturbed_root_continuous": ("event_time_valid",),
        "axis_orientation_known": ("event_time_valid",),
        "transform_ledger_complete": ("axis_orientation_known",),
        "target_detectable_A1": ("reference_root_continuous", "perturbed_root_continuous"),
        "witness_detectable_A1": ("perturbed_root_continuous",),
        "intervention_command_applied": ("transform_ledger_complete", "witness_detectable_A1"),
        "witness_translation_valid": ("intervention_command_applied",),
        "target_remains_detectable_on_reference_root": ("target_detectable_A1",),
        "target_matches_RF-frame_prediction_B": (
            "witness_translation_valid",
            "target_remains_detectable_on_reference_root",
        ),
        "target_matches_baseband-frame_prediction_B": (
            "witness_translation_valid",
            "target_remains_detectable_on_reference_root",
        ),
        "target_returns_to_A_prediction": ("witness_translation_valid",),
        "witness_returns_to_A_prediction": ("witness_translation_valid",),
        "no_invalidating_gap": ("event_time_valid",),
        "no_invalidating_overflow": ("event_time_valid",),
    }
    roots = (
        f"kiwi:{plan.reference_endpoint.host}:{plan.reference_endpoint.port}",
        f"kiwi:{plan.perturbed_endpoint.host}:{plan.perturbed_endpoint.port}",
    )
    assessments: list[ClauseAssessment] = []
    statuses: dict[str, ClauseStatus] = {}
    for name in CLAUSE_NAMES:
        blocked = any(statuses.get(dep) is not ClauseStatus.SATISFIED for dep in prerequisites.get(name, ()))
        if blocked:
            status = ClauseStatus.NOT_EVALUATED
            statement = "not evaluated because an upstream admission or causal precondition failed"
            measurement_roots: tuple[str, ...] = ()
        else:
            status = ClauseStatus.SATISFIED if values[name] else ClauseStatus.UNSATISFIED
            statement = "frozen clause satisfied" if values[name] else "frozen clause not satisfied"
            measurement_roots = roots if values[name] else ()
        statuses[name] = status
        assessments.append(ClauseAssessment(name, status, statement, measurement_roots))

    witness_valid = statuses["witness_translation_valid"] is ClauseStatus.SATISFIED
    detectable = (
        statuses["target_remains_detectable_on_reference_root"] is ClauseStatus.SATISFIED
        and statuses["no_invalidating_gap"] is ClauseStatus.SATISFIED
        and statuses["no_invalidating_overflow"] is ClauseStatus.SATISFIED
    )
    returned = (
        statuses["target_returns_to_A_prediction"] is ClauseStatus.SATISFIED
        and statuses["witness_returns_to_A_prediction"] is ClauseStatus.SATISFIED
    )
    rf = statuses["target_matches_RF-frame_prediction_B"] is ClauseStatus.SATISFIED
    baseband = statuses["target_matches_baseband-frame_prediction_B"] is ClauseStatus.SATISFIED

    if not witness_valid:
        outcome = OutcomeKind.INTERVENTION_INVALID
        hypotheses = ("H_OTHER_OR_UNRESOLVED",)
        supports = ("the frozen intervention could not be used to distinguish coordinate frames",)
    elif not detectable:
        outcome = OutcomeKind.NOT_DETECTABLE
        hypotheses = ("H_RF_FRAME", "H_BASEBAND_FRAME", "H_OTHER_OR_UNRESOLVED")
        supports = ("the target prediction was not evaluated because its detectability envelope failed",)
    elif rf and not baseband and returned and facts.controls_exclusive:
        outcome = OutcomeKind.RF_FRAME_PREDICTION_SUPPORTED
        hypotheses = ("H_RF_FRAME",)
        supports = ("the target matched only the frozen RF-frame translation and returned in A2",)
    elif baseband and not rf and returned and facts.controls_exclusive:
        outcome = OutcomeKind.BASEBAND_FRAME_PREDICTION_SUPPORTED
        hypotheses = ("H_BASEBAND_FRAME",)
        supports = ("the target matched only the frozen baseband-fixed prediction and returned in A2",)
    else:
        outcome = OutcomeKind.AMBIGUOUS
        hypotheses = ("H_OTHER_OR_UNRESOLVED",)
        supports = ("neither frozen coordinate-frame hypothesis was uniquely supported",)

    event_start = min(receipt.event_start for receipt in segment_receipts)
    event_end = max(receipt.event_end for receipt in segment_receipts)
    receipt = ConstraintReceipt(
        branch="gate-f2-targetless-retune",
        event_start=event_start,
        event_end=event_end,
        constraints=tuple(
            Constraint(item.clause, "clause_status", item.status, None, item.statement, "frozen Gate F2 plan")
            for item in assessments
        ) + (
            Constraint(
                "frozen_negative_controls",
                "exclusive",
                facts.controls_exclusive,
                None,
                "wrong-sign, wrong-magnitude and off-feature regions must not contain an equally compatible fingerprint",
                "frozen Gate F2 controls",
            ),
        ),
        transforms=(
            Transform("raw_spectral_bin", "preserved", "target matching starts in unshifted FFT-bin/baseband coordinates"),
            Transform("baseband_frequency", "derived", "scipy FFT frequency axis; orientation not applied"),
            Transform("receiver_center", "declared_only", "commanded center is not tune evidence"),
            Transform("retune", "witnessed" if witness_valid else "unverified", protocol_audit().exact_verified_point),
            Transform("absolute_RF_frequency", "derived_after_match", "center + axis_orientation * baseband; never used to search B"),
        ),
        measurement_roots=roots,
        model_roots=(f"kiwi-server:{KIWI_SERVER_COMMIT}", f"kiwiclient:{KIWI_CLIENT_COMMIT}"),
        artifact_hashes=tuple(receipt.artifact_hash for receipt in segment_receipts),
        caveats=(
            "no transmitter identity or common emitter is inferred",
            "a remote reference does not remove site-specific HF fading",
            "artifact hashes provide evidentiary continuity, not a reproducible capture",
        ),
    )
    # Enforce the strict descriptive boundary before returning the physical decision.
    strict_json_value(receipt)
    return GateF2Result(
        outcome,
        plan.plan_hash,
        hypotheses,
        tuple(assessments),
        segment_receipts,
        intervention_receipts,
        receipt,
        observed=(
            "GNSS event-time IQ segment hashes and byte/sequence ranges",
            "target and witness fingerprint matches in raw baseband regions",
            "reference-root target continuity during B",
        ),
        derived_from_transform_ledger=(
            f"axis_orientation={plan.axis_orientation} from qualification witness",
            f"RF-frame B interval around {plan.rf_frame_target_b_hz:.6f} Hz baseband",
            "absolute RF coordinates projected only after baseband matching",
        ),
        decided_before_confirmation=(
            f"plan_hash={plan.plan_hash}",
            f"delta_f_hz={plan.delta_f_hz}",
            f"prediction_tolerance_hz={plan.prediction_tolerance_hz}",
            *plan.controls,
        ),
        supports=supports,
        does_not_support=(
            "same emitter confirmed",
            "external RF proven",
            "common physical cause confirmed",
        ),
        abstractions_surviving=(
            "atomic clause evaluation",
            "event time and TTL",
            "transform ledger",
            "causal lineage",
            "strict descriptive boundary",
            "artifact hash without RF persistence",
        ),
        abstraction_eliminated="central planner",
        shock="a verified control transformation can create more falsification power than source identity or signal strength",
    )


def no_experiment_result(
    outcome: OutcomeKind,
    reason: str,
    *,
    progress: GateProgress,
    discovery_receipts: tuple[DiscoveryReceipt, ...],
    candidate_hashes: tuple[str, ...] = (),
    evaluated_at: datetime | None = None,
) -> GateF2Result:
    validate_prefreeze_outcome(outcome, progress)
    if not discovery_receipts:
        raise ValueError("a pre-freeze stop requires atomic discovery receipts")
    successful_paths = len({
        (receipt.provider, receipt.inventory_root, receipt.transport_route)
        for receipt in discovery_receipts
        if receipt.successful
    })
    if successful_paths != progress.successful_discovery_paths:
        raise ValueError("successful discovery path count conflicts with discovery receipts")
    described_candidates = sum(receipt.candidate_count for receipt in discovery_receipts if receipt.successful)
    if progress.candidates_discovered > described_candidates:
        raise ValueError("discovered candidate count exceeds the atomic discovery receipts")
    now = _utc(evaluated_at or datetime.now(timezone.utc))
    assessments = tuple(
        ClauseAssessment(name, ClauseStatus.NOT_EVALUATED, "plan freeze was not reached", ())
        for name in CLAUSE_NAMES
    )
    phase_assessments = _phase_stop_assessments(outcome)
    model_roots = tuple(sorted({
        f"inventory:{item.inventory_root}" for item in discovery_receipts
    }))
    if progress.qualifications_completed > 0:
        model_roots += (f"kiwi-server:{KIWI_SERVER_COMMIT}",)
    receipt = ConstraintReceipt(
        "gate-f2-targetless-retune",
        now,
        now,
        (
            Constraint("phase_reached", "terminal_phase", progress.phase_reached, None, reason, "Gate F2.1 phase ledger"),
            Constraint("terminal_outcome", "stopped_before_freeze", outcome, None, reason, "Gate F2.1 phase invariants"),
        ),
        (Transform(progress.phase_reached.value.lower(), "stopped", reason),),
        (),
        model_roots,
        candidate_hashes,
        ("no confirmation samples exist",),
    )
    return GateF2Result(
        outcome,
        None,
        ("H_OTHER_OR_UNRESOLVED",),
        assessments,
        (),
        (),
        receipt,
        (f"atomic discovery receipts; terminal phase={progress.phase_reached.value}",),
        ("no physical frame classification was derived",),
        ("mother method, budget, admission order and retry policy",),
        (reason,),
        ("no RF/baseband hypothesis was evaluated", "same emitter confirmed", "external RF proven"),
        ("atomic receipts", "strict descriptive boundary", "artifact hashes"),
        "central planner",
        "correct termination without an experiment is itself an epistemic result",
        phase_reached=progress.phase_reached,
        progress=progress,
        phase_clause_assessments=phase_assessments,
        discovery_receipts=discovery_receipts,
    )


def _hash(value: object) -> str:
    payload = json.dumps(strict_json_value(value), allow_nan=False, sort_keys=True, separators=(",", ":"))
    return sha256(payload.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc)


def _post_freeze_not_detectable(plan: FrozenPlan, reason: str, *, evaluated_at: datetime) -> GateF2Result:
    now = _utc(evaluated_at)
    roots = (
        f"kiwi:{plan.reference_endpoint.host}:{plan.reference_endpoint.port}",
        f"kiwi:{plan.perturbed_endpoint.host}:{plan.perturbed_endpoint.port}",
    )
    assessments = []
    for name in CLAUSE_NAMES:
        upstream = name in ("independent_hardware_roots", "axis_orientation_known", "transform_ledger_complete")
        assessments.append(
            ClauseAssessment(
                name,
                ClauseStatus.SATISFIED if upstream else ClauseStatus.NOT_EVALUATED,
                "satisfied before confirmation" if upstream else "confirmation failed before physical evaluation",
                roots if upstream else (),
            )
        )
    receipt = ConstraintReceipt(
        "gate-f2-targetless-retune", now, now,
        (Constraint("confirmation", "not_detectable", OutcomeKind.NOT_DETECTABLE, None, reason, "zero retry after plan freeze"),),
        (Transform("confirmation_stream", "interrupted", reason),),
        (), (f"kiwi-server:{KIWI_SERVER_COMMIT}",), (),
        ("no second window or retry is authorized",),
    )
    return GateF2Result(
        OutcomeKind.NOT_DETECTABLE, plan.plan_hash,
        ("H_RF_FRAME", "H_BASEBAND_FRAME", "H_OTHER_OR_UNRESOLVED"),
        tuple(assessments), (), (), receipt,
        ("the plan was frozen before the confirmation failure",),
        ("no coordinate-frame result was derived",),
        (f"plan_hash={plan.plan_hash}", "zero post-freeze retry"),
        ("the confirmation was not detectable",),
        ("same emitter confirmed", "external RF proven", "either coordinate-frame hypothesis"),
        ("clause gating", "immutable plan", "strict separation of description and physics"),
        "central planner",
        "an immutable stop is more informative than silently replacing a failed confirmation window",
    )


def _retryable_prefreeze_error(error: Exception) -> bool:
    if isinstance(error, (DescriptiveSerializationError, json.JSONDecodeError, struct.error)):
        return True
    if isinstance(error, ValueError):
        return False
    text = str(error).lower()
    if any(token in text for token in ("busy", "rejected", "no external api", "no gnss", "no target", "no witness")):
        return False
    return isinstance(error, (OSError, TimeoutError)) or any(
        token in text
        for token in ("timeout", "timed out", "connection", "closed", "reset", "handshake", "transport", "decode", "transform")
    )


@dataclass(slots=True)
class _RetryBudget:
    remaining: int
    retried_keys: set[str]


def _discover_directory_with_retry(
    mother: MotherPlan,
    budget: _RetryBudget,
    sink: Callable[[str], None],
) -> tuple[tuple[kiwi.KiwiEndpoint, ...], tuple[DiscoveryReceipt, ...]]:
    """Run one transport path with at most one predeclared retry."""

    key = "directory"
    receipts: list[DiscoveryReceipt] = []
    for retry_index in range(2):
        attempt = discover_directory_attempt(mother, retry_index=retry_index)
        receipts.append(attempt.receipt)
        emit_jsonl("gate_f2_discovery_receipt", attempt.receipt, sink=sink)
        if attempt.receipt.successful:
            return attempt.candidates, tuple(receipts)
        can_retry = retry_index == 0 and budget.remaining > 0 and key not in budget.retried_keys
        emit_jsonl(
            "gate_f2_prefreeze_failure",
            {
                "candidate_key": key,
                "error_type": attempt.receipt.error_class,
                "reason": attempt.receipt.error_detail,
                "response_status": attempt.receipt.response_status,
                "retry_authorized": can_retry,
            },
            sink=sink,
        )
        if not can_retry:
            break
        budget.remaining -= 1
        budget.retried_keys.add(key)
        emit_jsonl("gate_f2_prefreeze_retry", {"candidate_key": key, "retries_remaining": budget.remaining}, sink=sink)
    return (), tuple(receipts)


def _prefreeze_call(
    key: str,
    operation: Callable[[], object],
    budget: _RetryBudget,
    sink: Callable[[str], None],
) -> object:
    try:
        return operation()
    except Exception as error:
        can_retry = _retryable_prefreeze_error(error) and budget.remaining > 0 and key not in budget.retried_keys
        emit_jsonl(
            "gate_f2_prefreeze_failure",
            {"candidate_key": key, "error_type": type(error).__name__, "reason": str(error), "retry_authorized": can_retry},
            sink=sink,
        )
        if not can_retry:
            raise
        budget.remaining -= 1
        budget.retried_keys.add(key)
        emit_jsonl("gate_f2_prefreeze_retry", {"candidate_key": key, "retries_remaining": budget.remaining}, sink=sink)
        return operation()


def run_once(*, mother: MotherPlan | None = None, sink: Callable[[str], None] = print) -> GateF2Result:
    """Discover, qualify, freeze at most one plan, execute once and stop."""

    mother = mother or MotherPlan()
    deadline = time.monotonic() + mother.prefreeze_budget_s
    retries = _RetryBudget(mother.maximum_prefreeze_retries, set())
    audit = protocol_audit()
    emit_jsonl("gate_f2_protocol_audit_frozen", audit, sink=sink)
    emit_jsonl("gate_f2_mother_plan_frozen", mother, sink=sink)

    endpoints, discovery_receipts = _discover_directory_with_retry(mother, retries, sink)
    discovery_terminal = discovery_outcome(discovery_receipts, unique_candidate_count=len(endpoints))
    emit_jsonl("gate_f2_discovery_outcome", discovery_terminal, sink=sink)
    successful_discovery_paths = len({
        (receipt.provider, receipt.inventory_root, receipt.transport_route)
        for receipt in discovery_receipts
        if receipt.successful
    })
    if discovery_terminal is DiscoveryOutcomeKind.DISCOVERY_PATH_FAILED:
        reason = "all frozen discovery transport attempts failed before producing a valid inventory response"
        result = no_experiment_result(
            OutcomeKind.DISCOVERY_PATH_FAILED,
            reason,
            progress=GateProgress(GatePhase.DISCOVERY, 0, 0, 0, 0),
            discovery_receipts=discovery_receipts,
        )
        emit_jsonl("gate_f2_first_outcome", result, sink=sink)
        return result
    if discovery_terminal is DiscoveryOutcomeKind.NO_CAPABILITY_DISCOVERED:
        reason = "at least one frozen discovery path returned a valid empty candidate inventory"
        result = no_experiment_result(
            OutcomeKind.NO_CAPABILITY_DISCOVERED,
            reason,
            progress=GateProgress(GatePhase.DISCOVERY, successful_discovery_paths, 0, 0, 0),
            discovery_receipts=discovery_receipts,
        )
        emit_jsonl("gate_f2_first_outcome", result, sink=sink)
        return result
    emit_jsonl("gate_f2_capabilities_discovered", {"count": len(endpoints), "directory": mother.directory_url}, sink=sink)
    descriptions = qualify_endpoint_descriptions(endpoints, mother)
    for description in descriptions:
        emit_jsonl("gate_f2_capability_description", description, sink=sink)
    description_hashes = tuple(item.status_hash for item in descriptions)
    qualifications_completed = sum(
        item.state is CapabilityState.CAPABILITY_QUALIFIED for item in descriptions
    )
    if qualifications_completed == 0:
        result = no_experiment_result(
            OutcomeKind.NO_CAPABILITY_QUALIFIED,
            "candidates were discovered, but no direct description probe completed qualification positively",
            progress=GateProgress(
                GatePhase.QUALIFICATION,
                successful_discovery_paths,
                len(endpoints),
                0,
                0,
            ),
            discovery_receipts=discovery_receipts,
            candidate_hashes=description_hashes,
        )
        emit_jsonl("gate_f2_first_outcome", result, sink=sink)
        return result
    pairs = enumerate_hardware_pairs(descriptions, mother)
    if not pairs:
        result = no_experiment_result(
            OutcomeKind.NO_CAPABILITY_ADMITTED,
            "no two current descriptions establish independent, GNSS-capable hardware roots within the frozen path-separation envelope",
            progress=GateProgress(
                GatePhase.ADMISSION,
                successful_discovery_paths,
                len(endpoints),
                qualifications_completed,
                0,
            ),
            discovery_receipts=discovery_receipts,
            candidate_hashes=description_hashes,
        )
        emit_jsonl("gate_f2_first_outcome", result, sink=sink)
        return result

    saw_physically_qualified_pair = False
    qualification_hashes: list[str] = list(description_hashes)
    for pair_index, (left_description, right_description) in enumerate(pairs):
        if time.monotonic() >= deadline:
            break
        endpoints_pair = (left_description.endpoint, right_description.endpoint)
        pair_key = f"pair:{pair_index}:{endpoints_pair[0].host}:{endpoints_pair[1].host}"
        try:
            def waterfall_operation() -> tuple[_WaterfallArtifact, _WaterfallArtifact]:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    artifacts = tuple(pool.map(lambda endpoint: _capture_waterfall(endpoint, mother.waterfall_frames), endpoints_pair))
                return artifacts  # type: ignore[return-value]

            waterfall = _prefreeze_call(f"{pair_key}:waterfall", waterfall_operation, retries, sink)
            left_waterfall, right_waterfall = waterfall  # type: ignore[misc]
            qualification_hashes.extend((left_waterfall.artifact_hash, right_waterfall.artifact_hash))
            centers = waterfall_center_candidates(left_waterfall, right_waterfall, mother)
            emit_jsonl(
                "gate_f2_pair_waterfall_qualified",
                {
                    "pair": [asdict(endpoint) for endpoint in endpoints_pair],
                    "artifact_hashes": [left_waterfall.artifact_hash, right_waterfall.artifact_hash],
                    "candidate_center_count": len(centers),
                },
                sink=sink,
            )
            del waterfall, left_waterfall, right_waterfall
        except Exception as error:
            emit_jsonl("gate_f2_pair_qualification_error", {"pair_key": pair_key, "reason": str(error)}, sink=sink)
            continue
        if not centers:
            emit_jsonl("gate_f2_capability_rejected", {"pair_key": pair_key, "reason": "no simultaneously salient coarse RF region"}, sink=sink)
            continue
        saw_physically_qualified_pair = True
        for center_index, center_hz in enumerate(centers):
            if time.monotonic() >= deadline:
                break
            center_key = f"{pair_key}:center:{center_index}:{center_hz:.3f}"
            preanalysis_hashes: tuple[str, ...] = ()
            try:
                captures = _prefreeze_call(
                    center_key,
                    lambda: kiwi.capture_dual_kiwi(
                        endpoints_pair,
                        center_frequency_hz=center_hz,
                        duration_s=mother.qualification_duration_s,
                        max_gps_solution_age_s=mother.maximum_gps_solution_age_s,
                    ),
                    retries,
                    sink,
                )
                left_capture, right_capture = captures  # type: ignore[misc]
                preanalysis_hashes = (kiwi._capture_hash(left_capture), kiwi._capture_hash(right_capture))
                qualification_hashes.extend(preanalysis_hashes)
                try:
                    geometry = find_target_and_witness(left_capture, right_capture, mother)
                finally:
                    # RF samples never survive the candidate analysis iteration.
                    del captures, left_capture, right_capture
            except ValueError as error:
                emit_jsonl("gate_f2_capability_rejected", {"candidate_key": center_key, "reason": str(error), "artifact_hashes": preanalysis_hashes}, sink=sink)
                continue
            except Exception as error:
                emit_jsonl("gate_f2_qualification_error", {"candidate_key": center_key, "reason": str(error), "artifact_hashes": preanalysis_hashes}, sink=sink)
                continue
            try:
                candidate = _prefreeze_call(
                    f"{center_key}:orientation",
                    lambda: qualify_geometry_orientation(endpoints_pair, geometry, mother),
                    retries,
                    sink,
                )
                qualification_hashes.extend(candidate.qualification_hashes)  # type: ignore[attr-defined]
                frozen_at = datetime.now(timezone.utc)
                if frozen_at >= candidate.expires_at:  # type: ignore[attr-defined]
                    raise ValueError("qualification offer expired before plan freeze")
                plan = freeze_plan(
                    mother,
                    candidate.reference, candidate.perturbed,  # type: ignore[attr-defined]
                    candidate.geometry.center_a_hz, candidate.geometry.delta_f_hz,  # type: ignore[attr-defined]
                    candidate.axis_orientation, candidate.target, candidate.witness,  # type: ignore[attr-defined]
                    frozen_at=frozen_at,
                    prediction_tolerance_hz=candidate.geometry.prediction_tolerance_hz,  # type: ignore[attr-defined]
                )
                emit_jsonl("gate_f2_plan_frozen", plan, sink=sink)
            except ValueError as error:
                emit_jsonl("gate_f2_capability_rejected", {"candidate_key": center_key, "reason": str(error)}, sink=sink)
                continue
            except Exception as error:
                emit_jsonl("gate_f2_qualification_error", {"candidate_key": center_key, "reason": str(error)}, sink=sink)
                continue

            # Irreversible freeze boundary: one confirmation and no retry.
            try:
                confirmation = capture_dual_sequence(
                    (plan.reference_endpoint, plan.perturbed_endpoint),
                    plan.center_a_hz, plan.delta_f_hz,
                    plan.segment_duration_s, plan.settling_s, mother,
                )
                result = evaluate_sequence(plan, confirmation, mother)
                del confirmation
            except Exception as error:
                result = _post_freeze_not_detectable(
                    plan,
                    f"single confirmation failed with no retry: {type(error).__name__}: {error}",
                    evaluated_at=datetime.now(timezone.utc),
                )
            emit_jsonl("gate_f2_first_outcome", result, sink=sink)
            return result

    reason = (
        "qualified roots exposed coarse RF structure, but no capability completed the full admission envelope before the frozen deadline"
        if saw_physically_qualified_pair
        else "no capability pair completed the full admission envelope before the frozen deadline"
    )
    result = no_experiment_result(
        OutcomeKind.NO_CAPABILITY_ADMITTED,
        reason,
        progress=GateProgress(
            GatePhase.ADMISSION,
            successful_discovery_paths,
            len(endpoints),
            qualifications_completed,
            0,
        ),
        discovery_receipts=discovery_receipts,
        candidate_hashes=tuple(dict.fromkeys(qualification_hashes)),
    )
    emit_jsonl("gate_f2_first_outcome", result, sink=sink)
    return result


def main() -> None:
    run_once()


if __name__ == "__main__":
    main()
