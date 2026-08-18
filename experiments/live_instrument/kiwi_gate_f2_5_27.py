"""Gate F2.5.27: topology-derived relative-time admission, offline only.

The module is deliberately specific to one KiwiSDR, two simultaneous SND/IQ
channels and a per-channel DDC intervention.  It materialises scalar receipts
and evaluates synthetic fixtures.  It owns no connector, capture function,
live authority or RF persistence path.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from typing import Any, Sequence

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_5_26 as f2526


TRANSFORM_VERSION = "gate-f2.5.27-same-adc-relative-time-admission-v1"
REVIEWED_F2526_COMMIT = "319f8d3300ff58ae6aca0191eb5ee3c67f96f927"
PARENT_OUTCOME = f2526.FROZEN_OUTCOME
PARENT_RECEIPT_SHA256 = f2526.FROZEN_RECEIPT_SHA256
RAW_RF_PERSISTENCE = "ZERO"
GPS_WEEK_SECONDS = 604_800
GPS_WEEK_NS = GPS_WEEK_SECONDS * 1_000_000_000
HALF_GPS_WEEK_NS = GPS_WEEK_NS // 2
SEQUENCE_MODULUS = 1 << 32

CLAUSE_ORDER = (
    "pinned_same_adc_topology",
    "same_endpoint_distinct_channels",
    "scalar_metadata_complete",
    "reference_sequence_continuity",
    "perturbed_sequence_continuity",
    "reference_sample_clock_continuity",
    "perturbed_sample_clock_continuity",
    "server_clock_error_codes_absent",
    "same_sample_rate",
    "common_server_time_overlap",
    "absolute_gnss_freshness",
)

REQUIRED_FUTURE_SCALAR_FIELDS = (
    "artifact_hash_before_analysis",
    "artifact_byte_count",
    "endpoint_identity",
    "branch_role",
    "channel_id",
    "sequence",
    "server_gps_seconds",
    "server_gps_nanoseconds",
    "gps_solution_age_s",
    "decoded_sample_count",
    "sample_rate_hz",
    "monotonic_arrival_ns",
)

REQUIRED_COMMAND_BOUNDARY_FIELDS = (
    "transition",
    "command_hash",
    "command_issued_monotonic_ns",
    "settling_complete_monotonic_ns",
    "last_precommand_perturbed_frame_hash",
    "first_postsettling_perturbed_frame_hash",
    "reference_before_frame_hash",
    "reference_after_frame_hash",
)

_FORBIDDEN_RF_KEYS = {
    "blocks",
    "frames",
    "iq",
    "iq_array",
    "iq_samples",
    "raw_body",
    "raw_frame",
    "raw_frames",
    "samples",
    "stft",
    "waterfall",
}


class F2527Exit(str, Enum):
    RELATIVE_TIME_ADMISSION_MATERIALIZED_OFFLINE = (
        "RELATIVE_TIME_ADMISSION_MATERIALIZED_OFFLINE"
    )


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_EVALUATED = "NOT_EVALUATED"


class AdmissionState(str, Enum):
    ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT = (
        "ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT"
    )
    NOT_ADMISSIBLE = "NOT_ADMISSIBLE"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class BoundaryState(str, Enum):
    BOUNDARY_WITNESSED = "BOUNDARY_WITNESSED"
    BOUNDARY_NOT_WITNESSED = "BOUNDARY_NOT_WITNESSED"


def _strict_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda item: item.value if isinstance(item, Enum) else str(item),
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _sha256(value: str) -> None:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("a SHA-256 lowercase hex string is required")


@dataclass(frozen=True, slots=True)
class F2527TemporalPlan:
    reviewed_f2526_commit: str
    parent_outcome: str
    parent_receipt_sha256: str
    intervention_boundary: str
    shared_upstream_components: tuple[str, ...]
    independent_downstream_branches: tuple[str, str]
    time_coordinate: str
    absolute_utc_role: str
    nperseg: int
    noverlap: int
    minimum_common_samples: int
    maximum_timestamp_step_residual_samples: float
    maximum_sample_rate_difference_hz: float
    required_scalar_fields: tuple[str, ...]
    required_command_boundary_fields: tuple[str, ...]
    initial_zero_timestamp_rule: str
    gps_week_rollover_rule: str
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.reviewed_f2526_commit != REVIEWED_F2526_COMMIT:
            raise ValueError("Gate F2.5.26 lineage changed")
        if self.parent_outcome != PARENT_OUTCOME:
            raise ValueError("the frozen outcome cannot be reclassified")
        if self.parent_receipt_sha256 != PARENT_RECEIPT_SHA256:
            raise ValueError("the frozen receipt lineage changed")
        if self.intervention_boundary != "SAME_KIWI_PER_CHANNEL_DDC":
            raise ValueError("the temporal plan cannot generalise beyond the DDC cut")
        if self.shared_upstream_components != (
            "antenna",
            "front_end",
            "adc",
            "adc_sample_clock",
            "server_gps_clock_state",
        ):
            raise ValueError("shared causal topology changed")
        if self.independent_downstream_branches != (
            "fixed_reference_ddc_stream",
            "controllably_retuned_ddc_stream",
        ):
            raise ValueError("the required channel branches changed")
        if self.time_coordinate != "SERVER_SAMPLE_TIMESTAMP_WITHIN_GPS_WEEK":
            raise ValueError("relative server sample time is mandatory")
        if self.absolute_utc_role != "DESCRIPTIVE_NOT_REQUIRED_FOR_THIS_CAUSAL_CUT":
            raise ValueError("absolute UTC cannot silently re-enter admission")
        if not 0 <= self.noverlap < self.nperseg:
            raise ValueError("invalid STFT geometry")
        if self.minimum_common_samples != 2 * self.nperseg:
            raise ValueError("minimum overlap must support two existing STFT windows")
        if self.maximum_timestamp_step_residual_samples != 1.0:
            raise ValueError("continuity tolerance must remain one sample period")
        if self.maximum_sample_rate_difference_hz != 1e-6:
            raise ValueError("same-clock rate tolerance changed")
        if self.required_scalar_fields != REQUIRED_FUTURE_SCALAR_FIELDS:
            raise ValueError("future scalar receipt surface changed")
        if self.required_command_boundary_fields != REQUIRED_COMMAND_BOUNDARY_FIELDS:
            raise ValueError("command-boundary receipt surface changed")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("this successor permits no retry")
        if self.live_execution_authorised:
            raise ValueError("offline Gate F2.5.27 cannot grant live authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2526.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("temporal transform ledger changed")

    @property
    def plan_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class ScalarFrameReceipt:
    artifact_hash_before_analysis: str
    artifact_byte_count: int
    endpoint_identity: str
    branch_role: str
    channel_id: int
    sequence: int
    server_gps_seconds: int
    server_gps_nanoseconds: int
    gps_solution_age_s: int
    decoded_sample_count: int
    sample_rate_hz: float
    monotonic_arrival_ns: int
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        _sha256(self.artifact_hash_before_analysis)
        if self.artifact_byte_count <= 17:
            raise ValueError("a scalar receipt requires one complete SND frame")
        if not self.endpoint_identity:
            raise ValueError("endpoint identity is required")
        if self.branch_role not in {"reference", "perturbed"}:
            raise ValueError("unknown DDC branch role")
        if self.channel_id < 0:
            raise ValueError("server channel ID cannot be negative")
        if not 0 <= self.sequence < SEQUENCE_MODULUS:
            raise ValueError("SND sequence is outside uint32")
        if not 0 <= self.server_gps_seconds < GPS_WEEK_SECONDS:
            raise ValueError("GPS seconds must be within one week")
        if not 0 <= self.server_gps_nanoseconds < 1_000_000_000:
            raise ValueError("GPS nanoseconds are invalid")
        if not 0 <= self.gps_solution_age_s <= 255:
            raise ValueError("GPS solution-age byte is invalid")
        if self.decoded_sample_count <= 0:
            raise ValueError("decoded sample count must be positive")
        if not math.isfinite(self.sample_rate_hz) or self.sample_rate_hz <= 0.0:
            raise ValueError("sample rate must be positive and finite")
        if self.monotonic_arrival_ns < 0:
            raise ValueError("monotonic arrival cannot be negative")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))

    @property
    def raw_server_time_ns(self) -> int:
        return self.server_gps_seconds * 1_000_000_000 + self.server_gps_nanoseconds

    @property
    def sample_duration_ns(self) -> int:
        return round(self.decoded_sample_count * 1_000_000_000 / self.sample_rate_hz)


@dataclass(frozen=True, slots=True)
class ClauseReceipt:
    clause: str
    state: str
    statement: str
    evidence_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.clause not in CLAUSE_ORDER:
            raise ValueError("unknown relative-time clause")
        if self.state not in {item.value for item in ClauseState}:
            raise ValueError("unknown clause state")
        for item in self.evidence_hashes:
            _sha256(item)


@dataclass(frozen=True, slots=True)
class BranchTimingAudit:
    role: str
    channel_id: int | None
    input_frame_count: int
    usable_frame_count: int
    leading_zero_timestamp_count: int
    first_sequence: int | None
    last_sequence: int | None
    sequence_gap_count: int
    arrival_order_violation_count: int
    timestamp_step_violation_count: int
    server_clock_error_code_count: int
    maximum_timestamp_step_residual_samples: float | None
    sample_rate_hz: float | None
    unwrapped_start_ns: int | None
    unwrapped_end_ns: int | None
    artifact_hashes: tuple[str, ...]
    state: str


@dataclass(frozen=True, slots=True)
class RelativeTimingAdmissionReceipt:
    plan_hash: str
    state: str
    clauses: tuple[ClauseReceipt, ...]
    branches: tuple[BranchTimingAudit, BranchTimingAudit]
    common_start_ns: int | None
    common_end_ns: int | None
    common_duration_ns: int | None
    common_sample_count_floor: int | None
    gps_solution_age_role: str
    physical_hypothesis_state: str
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    physical_decision_affected: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.plan_hash)
        if self.state not in {item.value for item in AdmissionState}:
            raise ValueError("unknown temporal admission state")
        if tuple(item.clause for item in self.clauses) != CLAUSE_ORDER:
            raise ValueError("relative-time clauses must be complete and ordered")
        if self.physical_hypothesis_state != "NOT_EVALUATED":
            raise ValueError("temporal qualification cannot decide DDC location")
        if self.physical_decision_affected:
            raise ValueError("descriptive receipt cannot alter physical inference")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class CommandBoundaryAnchor:
    transition: str
    command_hash: str
    command_issued_monotonic_ns: int
    settling_complete_monotonic_ns: int
    last_precommand_perturbed_frame_hash: str
    first_postsettling_perturbed_frame_hash: str
    reference_before_frame_hash: str
    reference_after_frame_hash: str
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        if self.transition not in {"A1_TO_B", "B_TO_A2"}:
            raise ValueError("unknown A1/B/A2 transition")
        for item in (
            self.command_hash,
            self.last_precommand_perturbed_frame_hash,
            self.first_postsettling_perturbed_frame_hash,
            self.reference_before_frame_hash,
            self.reference_after_frame_hash,
        ):
            _sha256(item)
        if not 0 <= self.command_issued_monotonic_ns < self.settling_complete_monotonic_ns:
            raise ValueError("command and settling order is invalid")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class BoundaryWitnessReceipt:
    transition: str
    state: str
    command_hash: str
    anchor_receipt_hash: str
    local_order_satisfied: bool
    perturbed_server_time_advanced: bool
    reference_spanned_boundary: bool
    settling_duration_ns: int
    server_time_gap_ns: int | None
    reference_server_time_gap_ns: int | None
    statement: str
    physical_hypothesis_state: str
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.state not in {item.value for item in BoundaryState}:
            raise ValueError("unknown boundary-witness state")
        _sha256(self.command_hash)
        _sha256(self.anchor_receipt_hash)
        if self.physical_hypothesis_state != "NOT_EVALUATED":
            raise ValueError("boundary timing cannot decide DDC location")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2527Assessment:
    exit: F2527Exit
    plan: F2527TemporalPlan
    parent_outcome_preserved: bool
    absolute_freshness_removed_only_from_new_causal_cut: bool
    sample_geometry_defines_continuity_tolerance: bool
    server_timestamp_values_required: bool
    command_boundaries_predeclared: bool
    injected_scalar_receipts_only: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


def build_plan() -> F2527TemporalPlan:
    mother = f2.MotherPlan()
    return F2527TemporalPlan(
        reviewed_f2526_commit=REVIEWED_F2526_COMMIT,
        parent_outcome=PARENT_OUTCOME,
        parent_receipt_sha256=PARENT_RECEIPT_SHA256,
        intervention_boundary="SAME_KIWI_PER_CHANNEL_DDC",
        shared_upstream_components=(
            "antenna",
            "front_end",
            "adc",
            "adc_sample_clock",
            "server_gps_clock_state",
        ),
        independent_downstream_branches=(
            "fixed_reference_ddc_stream",
            "controllably_retuned_ddc_stream",
        ),
        time_coordinate="SERVER_SAMPLE_TIMESTAMP_WITHIN_GPS_WEEK",
        absolute_utc_role="DESCRIPTIVE_NOT_REQUIRED_FOR_THIS_CAUSAL_CUT",
        nperseg=mother.nperseg,
        noverlap=mother.noverlap,
        minimum_common_samples=2 * mother.nperseg,
        maximum_timestamp_step_residual_samples=1.0,
        maximum_sample_rate_difference_hz=1e-6,
        required_scalar_fields=REQUIRED_FUTURE_SCALAR_FIELDS,
        required_command_boundary_fields=REQUIRED_COMMAND_BOUNDARY_FIELDS,
        initial_zero_timestamp_rule=(
            "leading all-zero timestamps are excluded and counted; an all-zero "
            "timestamp after a near-week-end anchor is interpreted as rollover"
        ),
        gps_week_rollover_rule="unwrap only forward jumps larger than half a GPS week",
        prefreeze_retry_budget=0,
        postfreeze_retry_budget=0,
        live_execution_authorised=False,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
        transform_versions=(f2526.TRANSFORM_VERSION, TRANSFORM_VERSION),
    )


def _unwrap_start_times(
    frames: tuple[ScalarFrameReceipt, ...],
) -> tuple[tuple[ScalarFrameReceipt, ...], tuple[int, ...], int]:
    leading_zero = 0
    usable_start = 0
    for frame in frames:
        if frame.raw_server_time_ns == 0:
            leading_zero += 1
            usable_start += 1
        else:
            break
    usable = frames[usable_start:]
    if not usable:
        return (), (), leading_zero
    unwrapped: list[int] = []
    week_offset = 0
    previous_raw: int | None = None
    for frame in usable:
        raw = frame.raw_server_time_ns
        if previous_raw is not None and raw < previous_raw:
            if previous_raw - raw > HALF_GPS_WEEK_NS:
                week_offset += GPS_WEEK_NS
        unwrapped.append(raw + week_offset)
        previous_raw = raw
    return usable, tuple(unwrapped), leading_zero


def _branch_audit(
    role: str,
    frames: Sequence[ScalarFrameReceipt],
    plan: F2527TemporalPlan,
) -> BranchTimingAudit:
    ordered = tuple(frames)
    hashes = tuple(item.receipt_hash for item in ordered)
    if not ordered:
        return BranchTimingAudit(
            role=role,
            channel_id=None,
            input_frame_count=0,
            usable_frame_count=0,
            leading_zero_timestamp_count=0,
            first_sequence=None,
            last_sequence=None,
            sequence_gap_count=0,
            arrival_order_violation_count=0,
            timestamp_step_violation_count=0,
            server_clock_error_code_count=0,
            maximum_timestamp_step_residual_samples=None,
            sample_rate_hz=None,
            unwrapped_start_ns=None,
            unwrapped_end_ns=None,
            artifact_hashes=(),
            state="QUALIFICATION_ERROR",
        )
    role_valid = all(item.branch_role == role for item in ordered)
    channel_ids = {item.channel_id for item in ordered}
    endpoint_ids = {item.endpoint_identity for item in ordered}
    arrival_violations = sum(
        current.monotonic_arrival_ns <= previous.monotonic_arrival_ns
        for previous, current in zip(ordered, ordered[1:])
    )
    usable, starts, leading_zero = _unwrap_start_times(ordered)
    sequence_gaps = sum(
        current.sequence != ((previous.sequence + 1) % SEQUENCE_MODULUS)
        for previous, current in zip(usable, usable[1:])
    )
    timestamp_violations = 0
    clock_error_codes = sum(item.gps_solution_age_s > 252 for item in usable)
    residuals: list[float] = []
    for previous, current, previous_start, current_start in zip(
        usable, usable[1:], starts, starts[1:]
    ):
        expected_ns = previous.sample_duration_ns
        residual_ns = abs((current_start - previous_start) - expected_ns)
        sample_period_ns = 1_000_000_000 / previous.sample_rate_hz
        residual_samples = residual_ns / sample_period_ns
        residuals.append(residual_samples)
        timestamp_violations += int(
            residual_samples > plan.maximum_timestamp_step_residual_samples
        )
    rates = {item.sample_rate_hz for item in usable}
    scalar_valid = (
        role_valid
        and len(channel_ids) == 1
        and len(endpoint_ids) == 1
        and len(rates) == 1
        and bool(usable)
    )
    satisfied = (
        scalar_valid
        and sequence_gaps == 0
        and arrival_violations == 0
        and timestamp_violations == 0
        and clock_error_codes == 0
    )
    final_end = starts[-1] + usable[-1].sample_duration_ns if usable else None
    return BranchTimingAudit(
        role=role,
        channel_id=next(iter(channel_ids)) if len(channel_ids) == 1 else None,
        input_frame_count=len(ordered),
        usable_frame_count=len(usable),
        leading_zero_timestamp_count=leading_zero,
        first_sequence=usable[0].sequence if usable else None,
        last_sequence=usable[-1].sequence if usable else None,
        sequence_gap_count=sequence_gaps,
        arrival_order_violation_count=arrival_violations,
        timestamp_step_violation_count=timestamp_violations,
        server_clock_error_code_count=clock_error_codes,
        maximum_timestamp_step_residual_samples=(
            max(residuals) if residuals else 0.0 if usable else None
        ),
        sample_rate_hz=usable[0].sample_rate_hz if scalar_valid else None,
        unwrapped_start_ns=starts[0] if starts else None,
        unwrapped_end_ns=final_end,
        artifact_hashes=hashes,
        state="SATISFIED" if satisfied else "UNSATISFIED",
    )


def _clause(
    name: str,
    state: ClauseState,
    statement: str,
    hashes: tuple[str, ...],
) -> ClauseReceipt:
    return ClauseReceipt(name, state.value, statement, hashes)


def evaluate_relative_timing(
    reference_frames: Sequence[ScalarFrameReceipt],
    perturbed_frames: Sequence[ScalarFrameReceipt],
    *,
    plan: F2527TemporalPlan | None = None,
) -> RelativeTimingAdmissionReceipt:
    """Evaluate relative time using scalar receipts only."""

    plan = plan or build_plan()
    reference = _branch_audit("reference", reference_frames, plan)
    perturbed = _branch_audit("perturbed", perturbed_frames, plan)
    all_hashes = reference.artifact_hashes + perturbed.artifact_hashes
    all_frames = tuple(reference_frames) + tuple(perturbed_frames)
    endpoint_ids = {item.endpoint_identity for item in all_frames}
    channels = {
        item.branch_role: {frame.channel_id for frame in all_frames if frame.branch_role == item.branch_role}
        for item in all_frames
    }
    topology_ok = (
        f2526.PINNED_SERVER_COMMIT
        == "c40ecb471dced33689e335689f8ffd35a54f47fa"
        and sha256(f2526.PINNED_SERVER_ARCHIVE_PATH.read_bytes()).hexdigest()
        == f2526.PINNED_SERVER_ARCHIVE_SHA256
    )
    branches_ok = (
        len(endpoint_ids) == 1
        and set(channels) == {"reference", "perturbed"}
        and all(len(value) == 1 for value in channels.values())
        and next(iter(channels["reference"])) != next(iter(channels["perturbed"]))
    )
    metadata_ok = bool(all_frames) and all(
        item.raw_rf_persistence == RAW_RF_PERSISTENCE for item in all_frames
    )
    ref_sequence_ok = reference.usable_frame_count > 0 and reference.sequence_gap_count == 0
    pert_sequence_ok = perturbed.usable_frame_count > 0 and perturbed.sequence_gap_count == 0
    ref_clock_ok = (
        reference.state == "SATISFIED"
        and reference.timestamp_step_violation_count == 0
    )
    pert_clock_ok = (
        perturbed.state == "SATISFIED"
        and perturbed.timestamp_step_violation_count == 0
    )
    clock_codes_ok = (
        reference.server_clock_error_code_count == 0
        and perturbed.server_clock_error_code_count == 0
    )
    rate_ok = (
        reference.sample_rate_hz is not None
        and perturbed.sample_rate_hz is not None
        and math.isclose(
            reference.sample_rate_hz,
            perturbed.sample_rate_hz,
            rel_tol=0.0,
            abs_tol=plan.maximum_sample_rate_difference_hz,
        )
    )
    common_start: int | None = None
    common_end: int | None = None
    common_duration: int | None = None
    common_samples: int | None = None
    overlap_ok = False
    if (
        reference.unwrapped_start_ns is not None
        and reference.unwrapped_end_ns is not None
        and perturbed.unwrapped_start_ns is not None
        and perturbed.unwrapped_end_ns is not None
        and rate_ok
    ):
        common_start = max(reference.unwrapped_start_ns, perturbed.unwrapped_start_ns)
        common_end = min(reference.unwrapped_end_ns, perturbed.unwrapped_end_ns)
        common_duration = max(0, common_end - common_start)
        common_samples = math.floor(
            common_duration * reference.sample_rate_hz / 1_000_000_000
        )
        overlap_ok = common_samples >= plan.minimum_common_samples

    clauses = (
        _clause(
            "pinned_same_adc_topology",
            ClauseState.SATISFIED if topology_ok else ClauseState.UNSATISFIED,
            "pinned server source maps both SND channels to the shared ADC clock",
            all_hashes,
        ),
        _clause(
            "same_endpoint_distinct_channels",
            ClauseState.SATISFIED if branches_ok else ClauseState.UNSATISFIED,
            "one endpoint must expose distinct fixed and perturbed server channels",
            all_hashes,
        ),
        _clause(
            "scalar_metadata_complete",
            ClauseState.SATISFIED if metadata_ok else ClauseState.UNSATISFIED,
            "hash, sequence, server timestamp, sample geometry and arrival are retained",
            all_hashes,
        ),
        _clause(
            "reference_sequence_continuity",
            ClauseState.SATISFIED if ref_sequence_ok else ClauseState.UNSATISFIED,
            "reference sequence is contiguous after explicitly counted initial zeros",
            reference.artifact_hashes,
        ),
        _clause(
            "perturbed_sequence_continuity",
            ClauseState.SATISFIED if pert_sequence_ok else ClauseState.UNSATISFIED,
            "perturbed sequence is contiguous after explicitly counted initial zeros",
            perturbed.artifact_hashes,
        ),
        _clause(
            "reference_sample_clock_continuity",
            ClauseState.SATISFIED if ref_clock_ok else ClauseState.UNSATISFIED,
            "reference timestamp steps agree with decoded sample counts within one sample",
            reference.artifact_hashes,
        ),
        _clause(
            "perturbed_sample_clock_continuity",
            ClauseState.SATISFIED if pert_clock_ok else ClauseState.UNSATISFIED,
            "perturbed timestamp steps agree with decoded sample counts within one sample",
            perturbed.artifact_hashes,
        ),
        _clause(
            "server_clock_error_codes_absent",
            ClauseState.SATISFIED if clock_codes_ok else ClauseState.UNSATISFIED,
            "reserved server clock states 253 through 255 cannot enter relative timing",
            all_hashes,
        ),
        _clause(
            "same_sample_rate",
            ClauseState.SATISFIED if rate_ok else ClauseState.UNSATISFIED,
            "both DDC branches expose the same shared-clock sample rate",
            all_hashes,
        ),
        _clause(
            "common_server_time_overlap",
            ClauseState.SATISFIED if overlap_ok else ClauseState.UNSATISFIED,
            "common continuous time must contain at least two existing STFT windows",
            all_hashes,
        ),
        _clause(
            "absolute_gnss_freshness",
            ClauseState.NOT_REQUIRED,
            "absolute UTC freshness is outside this same-clock DDC causal cut",
            all_hashes,
        ),
    )
    evaluated = tuple(
        item.state for item in clauses if item.state != ClauseState.NOT_REQUIRED.value
    )
    state = (
        AdmissionState.ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT
        if evaluated and all(item == ClauseState.SATISFIED.value for item in evaluated)
        else AdmissionState.QUALIFICATION_ERROR
        if not all_frames
        else AdmissionState.NOT_ADMISSIBLE
    )
    return RelativeTimingAdmissionReceipt(
        plan_hash=plan.plan_hash,
        state=state.value,
        clauses=clauses,
        branches=(reference, perturbed),
        common_start_ns=common_start,
        common_end_ns=common_end,
        common_duration_ns=common_duration,
        common_sample_count_floor=common_samples,
        gps_solution_age_role="DESCRIPTIVE_ONLY_NOT_AN_ADMISSION_SUBSTITUTE",
        physical_hypothesis_state="NOT_EVALUATED",
        authorised_claims=(
            "relative sample-time admission state is evaluated from scalar receipts",
            "absolute UTC freshness is not required by this specific same-clock cut",
        ),
        unauthorised_claims=(
            "absolute UTC is accurate",
            "the frozen Gate F2.5.25 session would have passed",
            "the retune was applied",
            "a spectral feature exists",
            "the feature is upstream or downstream of the channel DDC",
        ),
        physical_decision_affected=False,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


def _forward_delta_ns(before: ScalarFrameReceipt, after: ScalarFrameReceipt) -> int:
    delta = after.raw_server_time_ns - before.raw_server_time_ns
    if delta < -HALF_GPS_WEEK_NS:
        delta += GPS_WEEK_NS
    return delta


def evaluate_command_boundary(
    anchor: CommandBoundaryAnchor,
    *,
    last_precommand_perturbed: ScalarFrameReceipt,
    first_postsettling_perturbed: ScalarFrameReceipt,
    reference_before: ScalarFrameReceipt,
    reference_after: ScalarFrameReceipt,
) -> BoundaryWitnessReceipt:
    """Evaluate one predeclared A1/B/A2 boundary without looking at IQ."""

    hashes_match = (
        anchor.last_precommand_perturbed_frame_hash
        == last_precommand_perturbed.artifact_hash_before_analysis
        and anchor.first_postsettling_perturbed_frame_hash
        == first_postsettling_perturbed.artifact_hash_before_analysis
        and anchor.reference_before_frame_hash
        == reference_before.artifact_hash_before_analysis
        and anchor.reference_after_frame_hash
        == reference_after.artifact_hash_before_analysis
    )
    roles_match = (
        last_precommand_perturbed.branch_role == "perturbed"
        and first_postsettling_perturbed.branch_role == "perturbed"
        and reference_before.branch_role == "reference"
        and reference_after.branch_role == "reference"
    )
    endpoint_match = len(
        {
            last_precommand_perturbed.endpoint_identity,
            first_postsettling_perturbed.endpoint_identity,
            reference_before.endpoint_identity,
            reference_after.endpoint_identity,
        }
    ) == 1
    channel_topology = (
        last_precommand_perturbed.channel_id
        == first_postsettling_perturbed.channel_id
        and reference_before.channel_id == reference_after.channel_id
        and last_precommand_perturbed.channel_id != reference_before.channel_id
    )
    local_order = (
        last_precommand_perturbed.monotonic_arrival_ns
        <= anchor.command_issued_monotonic_ns
        < anchor.settling_complete_monotonic_ns
        <= first_postsettling_perturbed.monotonic_arrival_ns
    )
    reference_server_gap = (
        _forward_delta_ns(reference_before, reference_after)
        - reference_before.sample_duration_ns
    )
    server_gap = (
        _forward_delta_ns(
            last_precommand_perturbed, first_postsettling_perturbed
        )
        - last_precommand_perturbed.sample_duration_ns
    )
    settling = anchor.settling_complete_monotonic_ns - anchor.command_issued_monotonic_ns
    server_advanced = server_gap >= settling
    reference_spans = (
        reference_before.monotonic_arrival_ns
        <= anchor.command_issued_monotonic_ns
        < anchor.settling_complete_monotonic_ns
        <= reference_after.monotonic_arrival_ns
        and reference_server_gap >= settling
    )
    valid = all(
        (
            hashes_match,
            roles_match,
            endpoint_match,
            channel_topology,
            local_order,
            reference_spans,
            server_advanced,
        )
    )
    return BoundaryWitnessReceipt(
        transition=anchor.transition,
        state=(
            BoundaryState.BOUNDARY_WITNESSED.value
            if valid
            else BoundaryState.BOUNDARY_NOT_WITNESSED.value
        ),
        command_hash=anchor.command_hash,
        anchor_receipt_hash=anchor.receipt_hash,
        local_order_satisfied=local_order,
        perturbed_server_time_advanced=server_advanced,
        reference_spanned_boundary=reference_spans,
        settling_duration_ns=settling,
        server_time_gap_ns=server_gap,
        reference_server_time_gap_ns=reference_server_gap,
        statement=(
            "command and settling boundary is bracketed by both channel streams"
            if valid
            else "the scalar receipt does not close the command-boundary timing cut"
        ),
        physical_hypothesis_state="NOT_EVALUATED",
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )


def assess() -> F2527Assessment:
    return F2527Assessment(
        exit=F2527Exit.RELATIVE_TIME_ADMISSION_MATERIALIZED_OFFLINE,
        plan=build_plan(),
        parent_outcome_preserved=True,
        absolute_freshness_removed_only_from_new_causal_cut=True,
        sample_geometry_defines_continuity_tolerance=True,
        server_timestamp_values_required=True,
        command_boundaries_predeclared=True,
        injected_scalar_receipts_only=True,
        live_execution_authorised=False,
        raw_rf_persistence=RAW_RF_PERSISTENCE,
    )
