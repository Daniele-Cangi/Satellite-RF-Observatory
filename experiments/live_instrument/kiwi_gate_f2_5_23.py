"""Gate F2.5.23: offline one-target prospective successor.

The successor accepts only injected, already-qualified topology and in-memory
artifacts. It has no connector, no default capture function and no live
authority. It integrates the F2.5.22 descriptive discovery receipt with a
target-excluded distributed retune witness, then freezes predictions and
controls for one future independent confirmation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
import json
import math
from typing import Callable, Sequence

import numpy as np

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5 as f25
from . import kiwi_gate_f2_5_20 as f2520
from . import kiwi_gate_f2_5_22 as f2522
from .models import strict_json_value


TRANSFORM_VERSION = "gate-f2.5.23-one-target-distributed-witness-successor-v1"
PARENT_OUTCOME_SHA256 = f2522.FROZEN_OUTCOME_SHA256
RAW_RF_PERSISTENCE = "ZERO"
PHASE_ORDER = (
    "DIRECT_DUAL_SND_QUALIFICATION",
    "ONE_TARGET_DISCOVERY",
    "DISTRIBUTED_RETUNE_QUALIFICATION",
    "PLAN_FREEZE",
    "ONE_CONFIRMATION",
)
ALLOWED_FUTURE_OUTCOMES = (
    "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED",
    "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED",
    "AMBIGUOUS",
    "INTERVENTION_INVALID",
    "NOT_DETECTABLE",
)


class F2523Exit(str, Enum):
    PREFREEZE_SUCCESSOR_MATERIALIZED_OFFLINE = (
        "PREFREEZE_SUCCESSOR_MATERIALIZED_OFFLINE"
    )


class PhaseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"
    NOT_EVALUATED = "NOT_EVALUATED"


class MaterializationOutcome(str, Enum):
    PREFREEZE_PLAN_MATERIALIZED_OFFLINE = "PREFREEZE_PLAN_MATERIALIZED_OFFLINE"
    NO_FALSIFIABLE_INTERVENTION = "NO_FALSIFIABLE_INTERVENTION"
    INTERVENTION_NOT_QUALIFIED = "INTERVENTION_NOT_QUALIFIED"
    QUALIFICATION_INCOMPLETE = "QUALIFICATION_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class F2523Envelope:
    parent_outcome_sha256: str
    phase_order: tuple[str, ...]
    thresholds: tuple[tuple[str, float], ...]
    discovery_rule: str
    witness_rule: str
    target_exclusion_rule: str
    confirmation_rule: str
    allowed_future_outcomes: tuple[str, ...]
    prefreeze_retry_budget: int
    postfreeze_retry_budget: int
    live_execution_authorised: bool
    capture_functions_required_injected: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.parent_outcome_sha256 != PARENT_OUTCOME_SHA256:
            raise ValueError("frozen F2.5.21 lineage changed")
        if self.phase_order != PHASE_ORDER:
            raise ValueError("prospective phase order changed")
        if self.allowed_future_outcomes != ALLOWED_FUTURE_OUTCOMES:
            raise ValueError("future physical outcome set changed")
        if self.prefreeze_retry_budget or self.postfreeze_retry_budget:
            raise ValueError("the successor permits no retry")
        if self.live_execution_authorised:
            raise ValueError("offline materialization cannot grant live authority")
        if not self.capture_functions_required_injected:
            raise ValueError("the offline successor cannot own a connector")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions[-1] != TRANSFORM_VERSION:
            raise ValueError("transform ledger changed")

    @property
    def envelope_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class TargetFingerprint:
    baseband_position_a_hz: float
    bandwidth_hz: float
    local_neighbourhood: tuple[float, ...]
    morphology_db: tuple[float, float, float]
    contrast_interval_db: tuple[float, float]
    uncertainty_hz: float
    cross_branch_correlation: float

    def __post_init__(self) -> None:
        values = (
            self.baseband_position_a_hz,
            self.bandwidth_hz,
            *self.local_neighbourhood,
            *self.morphology_db,
            *self.contrast_interval_db,
            self.uncertainty_hz,
            self.cross_branch_correlation,
        )
        if any(not math.isfinite(item) for item in values):
            raise ValueError("target fingerprint must be finite")
        if self.bandwidth_hz <= 0 or self.uncertainty_hz <= 0:
            raise ValueError("target geometry must be positive")
        if len(self.local_neighbourhood) < 3:
            raise ValueError("target neighbourhood is incomplete")
        if not 0 <= self.cross_branch_correlation <= 1:
            raise ValueError("target correlation is invalid")


@dataclass(frozen=True, slots=True)
class DiscoveryGeometry:
    target: TargetFingerprint
    center_a_hz: float
    delta_hz: float
    common_low_hz: float
    common_high_hz: float
    spectral_resolution_hz: float
    prediction_tolerance_hz: float


@dataclass(frozen=True, slots=True)
class PhaseReceipt:
    phase: str
    state: str
    statement: str
    artifact_hashes: tuple[str, ...]
    properties: tuple[tuple[str, str], ...]
    discovery_audit: f2522.DiscoveryAuditReceipt | None = None
    distributed_witness: f2522.DistributedWitnessReceipt | None = None
    raw_rf_persistence: str = RAW_RF_PERSISTENCE

    def __post_init__(self) -> None:
        if self.phase not in PHASE_ORDER:
            raise ValueError("unknown successor phase")
        if self.state not in {item.value for item in PhaseState}:
            raise ValueError("unknown successor phase state")
        if any(len(item) != 64 for item in self.artifact_hashes):
            raise ValueError("phase artifact hashes must be SHA-256 strings")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class WitnessQualification:
    orientation: int
    observed_translation_hz: float
    resolution_error_hz: float
    receipt: f2522.DistributedWitnessReceipt
    phase_receipt: PhaseReceipt

    def __post_init__(self) -> None:
        if self.orientation not in (-1, 1):
            raise ValueError("qualified witness requires one orientation")
        if not math.isfinite(self.observed_translation_hz):
            raise ValueError("observed translation must be finite")
        if self.receipt.state != f2522.WitnessState.QUALIFIED_AS_FUTURE_WITNESS.value:
            raise ValueError("an unresolved witness cannot enter plan freeze")


@dataclass(frozen=True, slots=True)
class F2523Plan:
    endpoint_identity: str
    reference_channel_id: str
    perturbed_channel_id: str
    center_a_hz: float
    delta_hz: float
    observed_translation_hz: float
    orientation: int
    target: TargetFingerprint
    prediction_intervals: tuple[tuple[str, float, float], ...]
    controls: tuple[tuple[str, float], ...]
    discovery_artifact_hashes: tuple[str, str]
    qualification_artifact_hashes: tuple[str, ...]
    thresholds: tuple[tuple[str, float], ...]
    confirmation_clauses: tuple[str, ...]
    allowed_outcomes: tuple[str, ...]
    frozen_at: datetime
    confirmation_event_not_before: datetime
    confirmation_windows: int
    postfreeze_retry_budget: int
    target_excluded_from_witness: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        f2._utc(self.frozen_at)
        f2._utc(self.confirmation_event_not_before)
        if self.confirmation_event_not_before < self.frozen_at:
            raise ValueError("confirmation cannot precede plan freeze")
        if self.reference_channel_id == self.perturbed_channel_id:
            raise ValueError("reference and perturbed channels must remain distinct")
        if self.orientation not in (-1, 1):
            raise ValueError("plan orientation is unresolved")
        if not self.target_excluded_from_witness:
            raise ValueError("target leakage into qualification is forbidden")
        if self.confirmation_windows != 1 or self.postfreeze_retry_budget != 0:
            raise ValueError("exactly one future confirmation and zero retry are required")
        if self.allowed_outcomes != ALLOWED_FUTURE_OUTCOMES:
            raise ValueError("future outcome set changed")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        intervals = {name: (low, high) for name, low, high in self.prediction_intervals}
        upstream = intervals["TARGET_UPSTREAM_B"]
        downstream = intervals["TARGET_CHANNEL_FIXED_B"]
        if max(upstream[0], downstream[0]) <= min(upstream[1], downstream[1]):
            raise ValueError("future hypotheses overlap")
        if self.transform_versions[-1] != TRANSFORM_VERSION:
            raise ValueError("plan transform ledger changed")

    @property
    def plan_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class F2523Result:
    envelope: F2523Envelope
    outcome: str
    phase_receipts: tuple[PhaseReceipt, ...]
    plan: F2523Plan | None
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class F2523Assessment:
    exit: F2523Exit
    parent_attribution_bound: bool
    one_target_allowed: bool
    orthogonal_witness_still_required: bool
    target_bins_excluded_from_all_witness_controls: bool
    fixed_reference_and_a2_required: bool
    thresholds_unchanged: bool
    injected_capture_only: bool
    confirmation_independent_and_single: bool
    confirmation_integration_required: bool
    post_commit_seal_required: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


@dataclass(frozen=True, slots=True)
class _DiscoveryContext:
    geometry: DiscoveryGeometry
    audit: f2522.DiscoveryAuditReceipt
    profiles: tuple[f2._SpectralProfile, f2._SpectralProfile]
    phase_receipt: PhaseReceipt


ProfileProvider = Callable[[object, f2.MotherPlan], f2._SpectralProfile]
CaptureDiscovery = Callable[[f25._TopologyContext], f24._DualArtifacts]
CaptureDiagnostic = Callable[[f25._TopologyContext, float], f24._DualArtifacts]


def _thresholds(mother: f2.MotherPlan) -> tuple[tuple[str, float], ...]:
    return (
        ("minimum_contrast_db", mother.minimum_contrast_db),
        ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
        ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
        ("minimum_delta_hz", mother.minimum_delta_hz),
        ("maximum_delta_hz", mother.maximum_delta_hz),
        ("prediction_tolerance_bins", mother.prediction_tolerance_bins),
    )


def build_envelope(mother: f2.MotherPlan | None = None) -> F2523Envelope:
    mother = mother or f2.MotherPlan()
    return F2523Envelope(
        PARENT_OUTCOME_SHA256,
        PHASE_ORDER,
        _thresholds(mother),
        "one or more stable common peaks; strongest falsification rank selects one target",
        "target-excluded distributed fingerprint, shared A state, fixed reference, unique perturbed translation and A2 return",
        "exclude target neighbourhood at zero, both signed delta and both signed half-delta positions on source and observed grids",
        "one independent post-freeze A1/B/A2; distributed witness rechecked before target hypotheses",
        ALLOWED_FUTURE_OUTCOMES,
        0,
        0,
        False,
        True,
        RAW_RF_PERSISTENCE,
        (f2522.TRANSFORM_VERSION, TRANSFORM_VERSION),
    )


def _common_grid(
    profiles: Sequence[f2._SpectralProfile],
) -> tuple[np.ndarray, tuple[np.ndarray, ...], float]:
    low = max(float(item.frequencies_hz[0]) for item in profiles)
    high = min(float(item.frequencies_hz[-1]) for item in profiles)
    bin_hz = max(float(item.bin_hz) for item in profiles)
    count = int(math.floor((high - low) / bin_hz)) + 1
    if count < 64:
        raise ValueError("no resolved common baseband grid")
    frequencies = low + np.arange(count, dtype=float) * bin_hz
    residuals = tuple(
        np.interp(frequencies, item.frequencies_hz, item.residual_db)
        for item in profiles
    )
    return frequencies, residuals, bin_hz


def _target_from_audit(
    audit: f2522.DiscoveryAuditReceipt,
    left: f2._SpectralProfile,
    right: f2._SpectralProfile,
    mother: f2.MotherPlan,
) -> TargetFingerprint:
    admitted = tuple(item for item in audit.candidates if item.state == "ADMITTED")
    if not admitted:
        raise ValueError("discovery contains no stable common target")

    def value(item: f2522.NumericObservation) -> float:
        if item.state != "FINITE" or item.value is None:
            raise ValueError("admitted target has an incomplete scalar receipt")
        return item.value

    def rank(item: f2522.CandidateReceipt) -> tuple[float, ...]:
        position = value(item.baseband_hz)
        first = value(item.first_half_min_contrast_db)
        second = value(item.second_half_min_contrast_db)
        edge = min(position - audit.common_grid_low_hz, audit.common_grid_high_hz - position)
        return (
            value(item.cross_branch_correlation),
            -abs(first - second),
            edge,
            min(first, second),
            value(item.joint_contrast_db),
            -abs(position),
        )

    selected = max(admitted, key=rank)
    frequencies, residuals, bin_hz = _common_grid((left, right))
    position = value(selected.baseband_hz)
    index = int(np.argmin(np.abs(frequencies - position)))
    left_patch = f2._normalized_neighbourhood(residuals[0], index)
    right_patch = f2._normalized_neighbourhood(residuals[1], index)
    if left_patch is None or right_patch is None:
        raise ValueError("selected target neighbourhood cannot be reconstructed")
    joint_patch = tuple(float((a + b) / 2.0) for a, b in zip(left_patch, right_patch))
    first = value(selected.first_half_min_contrast_db)
    second = value(selected.second_half_min_contrast_db)
    return TargetFingerprint(
        position,
        value(selected.bandwidth_hz),
        joint_patch,
        (first, second, abs(first - second)),
        (min(first, second), value(selected.joint_contrast_db)),
        mother.prediction_tolerance_bins * bin_hz,
        value(selected.cross_branch_correlation),
    )


def _orientation_neutral_delta(
    target: TargetFingerprint,
    low: float,
    high: float,
    bin_hz: float,
    mother: f2.MotherPlan,
) -> float:
    scale = max(target.bandwidth_hz, target.uncertainty_hz, bin_hz)
    lower = max(mother.minimum_delta_hz, 2.0 * scale, 5.0 * target.uncertainty_hz)
    edge = min(target.baseband_position_a_hz - low, high - target.baseband_position_a_hz)
    guard = mother.guard_bins * bin_hz + scale
    upper = min(mother.maximum_delta_hz, (edge - guard) / 2.5)
    if upper < lower:
        raise ValueError("one target leaves no orientation-neutral intervention geometry")
    delta = math.floor(upper / bin_hz) * bin_hz
    if delta < lower:
        raise ValueError("quantised delta violates the frozen detectability envelope")
    for sign in (-1.0, 1.0):
        positions = (
            target.baseband_position_a_hz,
            target.baseband_position_a_hz + sign * delta,
            target.baseband_position_a_hz - sign * delta,
            target.baseband_position_a_hz + sign * delta / 2.0,
            target.baseband_position_a_hz + sign * delta * 2.5,
        )
        if any(not low + guard <= item <= high - guard for item in positions):
            raise ValueError("one signed intervention leaves the common passband")
    return float(delta)


def discover_one_target(
    artifacts: f24._DualArtifacts,
    center_a_hz: float,
    mother: f2.MotherPlan,
    *,
    profile_provider: ProfileProvider = f2._capture_profile,
) -> _DiscoveryContext | PhaseReceipt:
    left = artifacts.reference["DISCOVERY_A"]
    right = artifacts.perturbed["DISCOVERY_A"]
    hashes = (left.artifact_hash, right.artifact_hash)
    try:
        profiles = (
            profile_provider(left.capture, mother),
            profile_provider(right.capture, mother),
        )
        audit = f2522.audit_profile_pair(profiles[0], profiles[1], hashes, mother)
        target = _target_from_audit(audit, profiles[0], profiles[1], mother)
        delta = _orientation_neutral_delta(
            target,
            audit.common_grid_low_hz,
            audit.common_grid_high_hz,
            audit.common_bin_hz,
            mother,
        )
        geometry = DiscoveryGeometry(
            target,
            center_a_hz,
            delta,
            audit.common_grid_low_hz,
            audit.common_grid_high_hz,
            audit.common_bin_hz,
            target.uncertainty_hz,
        )
        receipt = PhaseReceipt(
            "ONE_TARGET_DISCOVERY",
            PhaseState.SATISFIED.value,
            "one stable target selected; the intervention witness remains separate and distributed",
            hashes,
            (
                ("admitted_feature_count", str(audit.admitted_feature_count)),
                ("selected_target_baseband_hz", f"{target.baseband_position_a_hz:.9f}"),
                ("orientation_neutral_delta_hz", f"{delta:.9f}"),
                ("second_narrowband_peak_required", "FALSE"),
                ("orthogonal_witness_required", "TRUE"),
            ),
            discovery_audit=audit,
        )
        return _DiscoveryContext(geometry, audit, profiles, receipt)
    except ValueError as error:
        return PhaseReceipt(
            "ONE_TARGET_DISCOVERY",
            PhaseState.UNSATISFIED.value,
            f"no one-target falsifiable geometry: {error}",
            hashes,
            (("target_discovery", "UNSATISFIED"),),
        )
    except Exception as error:
        error_hash = f2._hash(
            {
                "phase": "one_target_discovery",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        return PhaseReceipt(
            "ONE_TARGET_DISCOVERY",
            PhaseState.QUALIFICATION_ERROR.value,
            f"discovery transform error: {type(error).__name__}: {error}",
            hashes + (error_hash,),
            (("target_discovery", "NOT_EVALUATED"),),
        )


def _diagnostic_profiles(
    artifacts: f24._DualArtifacts,
    mother: f2.MotherPlan,
    profile_provider: ProfileProvider,
) -> tuple[tuple[f2._SpectralProfile, ...], tuple[str, ...]]:
    ordered = tuple(
        artifacts.reference[name] for name in ("A1", "B", "A2")
    ) + tuple(artifacts.perturbed[name] for name in ("A1", "B", "A2"))
    return (
        tuple(profile_provider(item.capture, mother) for item in ordered),
        tuple(item.artifact_hash for item in ordered),
    )


def qualify_distributed_witness(
    discovery: _DiscoveryContext,
    diagnostic: f24._DualArtifacts,
    mother: f2.MotherPlan,
    *,
    profile_provider: ProfileProvider = f2._capture_profile,
) -> WitnessQualification | PhaseReceipt:
    try:
        profiles, hashes = _diagnostic_profiles(diagnostic, mother, profile_provider)
        frequencies, residuals, bin_hz = _common_grid(profiles)
        target_index = int(
            np.argmin(
                np.abs(frequencies - discovery.geometry.target.baseband_position_a_hz)
            )
        )
        delta_bins = int(round(discovery.geometry.delta_hz / bin_hz))
        effective_hz = delta_bins * bin_hz
        resolution_error = abs(effective_hz - discovery.geometry.delta_hz)
        if delta_bins <= 0 or resolution_error > discovery.geometry.prediction_tolerance_hz:
            raise ValueError("diagnostic grid cannot represent the frozen retune magnitude")
        target_radius = int(
            math.ceil(
                max(
                    discovery.geometry.target.bandwidth_hz,
                    discovery.geometry.target.uncertainty_hz,
                )
                / bin_hz
            )
        )
        witness = f2522.assess_distributed_witness(
            reference_a1=residuals[0],
            reference_b=residuals[1],
            reference_a2=residuals[2],
            perturbed_a1=residuals[3],
            perturbed_b=residuals[4],
            perturbed_a2=residuals[5],
            input_artifact_hashes=hashes,
            delta_bins=delta_bins,
            target_index=target_index,
            target_exclusion_radius=target_radius,
            minimum_fingerprint_correlation=mother.minimum_fingerprint_correlation,
        )
        satisfied = witness.state == f2522.WitnessState.QUALIFIED_AS_FUTURE_WITNESS.value
        receipt = PhaseReceipt(
            "DISTRIBUTED_RETUNE_QUALIFICATION",
            PhaseState.SATISFIED.value if satisfied else PhaseState.UNSATISFIED.value,
            (
                "target-excluded distributed fingerprint uniquely witnessed the perturbed retune"
                if satisfied
                else "distributed fingerprint did not qualify the per-channel retune"
            ),
            hashes,
            (
                ("target_evaluated", "FALSE"),
                ("target_bins_excluded", "TRUE"),
                ("witness_state", witness.state),
                ("resolution_error_hz", f"{resolution_error:.9f}"),
            ),
            distributed_witness=witness,
        )
        if not satisfied or witness.learned_orientation is None:
            return receipt
        return WitnessQualification(
            witness.learned_orientation,
            witness.learned_orientation * effective_hz,
            resolution_error,
            witness,
            receipt,
        )
    except ValueError as error:
        hashes = tuple(item.artifact_hash for item in diagnostic.receipts)
        return PhaseReceipt(
            "DISTRIBUTED_RETUNE_QUALIFICATION",
            PhaseState.UNSATISFIED.value,
            f"distributed witness is not admissible: {error}",
            hashes,
            (("target_evaluated", "FALSE"), ("retune_witness", "UNSATISFIED")),
        )
    except Exception as error:
        hashes = tuple(item.artifact_hash for item in diagnostic.receipts)
        error_hash = f2._hash(
            {
                "phase": "distributed_retune_qualification",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        return PhaseReceipt(
            "DISTRIBUTED_RETUNE_QUALIFICATION",
            PhaseState.QUALIFICATION_ERROR.value,
            f"distributed witness transform error: {type(error).__name__}: {error}",
            hashes + (error_hash,),
            (("target_evaluated", "FALSE"), ("retune_witness", "NOT_EVALUATED")),
        )


def freeze_plan(
    topology: f25._TopologyContext,
    discovery: _DiscoveryContext,
    witness: WitnessQualification,
    mother: f2.MotherPlan,
    *,
    frozen_at: datetime,
) -> F2523Plan:
    target = discovery.geometry.target
    translation = witness.observed_translation_hz
    tolerance = discovery.geometry.prediction_tolerance_hz
    upstream = target.baseband_position_a_hz + translation
    fixed = target.baseband_position_a_hz
    predictions = (
        ("TARGET_UPSTREAM_B", upstream - tolerance, upstream + tolerance),
        ("TARGET_CHANNEL_FIXED_B", fixed - tolerance, fixed + tolerance),
        ("TARGET_A2_RETURN", fixed - tolerance, fixed + tolerance),
        ("REFERENCE_TARGET_FIXED", fixed - tolerance, fixed + tolerance),
    )
    controls = (
        ("WRONG_SIGN_B", fixed - translation),
        ("HALF_MAGNITUDE_B", fixed + translation / 2.0),
        ("OFF_FEATURE_B", fixed + translation * 2.5),
    )
    low = discovery.geometry.common_low_hz
    high = discovery.geometry.common_high_hz
    if any(not low <= value <= high for _, value in controls):
        raise ValueError("a frozen negative control leaves the discovery grid")
    if any(not low <= value <= high for _, low_value, high_value in predictions for value in (low_value, high_value)):
        raise ValueError("a frozen prediction interval leaves the discovery grid")
    return F2523Plan(
        f"{topology.endpoint.host.lower()}:{topology.endpoint.port}",
        topology.dual.reference.channel_id,
        topology.dual.perturbed.channel_id,
        discovery.geometry.center_a_hz,
        discovery.geometry.delta_hz,
        translation,
        witness.orientation,
        target,
        predictions,
        controls,
        discovery.audit.input_artifact_hashes,
        witness.receipt.input_artifact_hashes,
        _thresholds(mother),
        (
            "distributed_witness_requalified_postfreeze",
            "target_detectable_on_both_A1_branches",
            "reference_target_fixed_through_A1_B_A2",
            "exactly_one_of_upstream_or_channel_fixed_matches_B",
            "wrong_sign_half_magnitude_and_off_feature_controls_absent",
            "target_returns_in_A2",
        ),
        ALLOWED_FUTURE_OUTCOMES,
        frozen_at,
        frozen_at,
        1,
        0,
        True,
        RAW_RF_PERSISTENCE,
        (f2522.TRANSFORM_VERSION, TRANSFORM_VERSION),
    )


def _not_evaluated(start_after: str) -> tuple[PhaseReceipt, ...]:
    index = PHASE_ORDER.index(start_after)
    return tuple(
        PhaseReceipt(
            phase,
            PhaseState.NOT_EVALUATED.value,
            "an upstream phase did not admit this phase",
            (),
            (("upstream_admission", "UNSATISFIED"),),
        )
        for phase in PHASE_ORDER[index + 1 :]
    )


def materialize_prefreeze_injected(
    qualification: f2520.F2520Qualification,
    *,
    capture_discovery: CaptureDiscovery,
    capture_diagnostic: CaptureDiagnostic,
    profile_provider: ProfileProvider = f2._capture_profile,
    mother: f2.MotherPlan | None = None,
    frozen_at: datetime | None = None,
) -> F2523Result:
    """Materialise the successor with required injected captures; never live by default."""

    mother = mother or f2.MotherPlan()
    envelope = build_envelope(mother)
    direct = qualification.result
    if not isinstance(direct, f25._TopologyContext):
        direct_state = (
            PhaseState.QUALIFICATION_ERROR.value
            if direct.state is f25.F25PhaseState.QUALIFICATION_ERROR
            else PhaseState.UNSATISFIED.value
        )
        receipt = PhaseReceipt(
            "DIRECT_DUAL_SND_QUALIFICATION",
            direct_state,
            direct.statement,
            direct.artifact_hashes,
            direct.properties,
        )
        phases = (receipt,) + _not_evaluated(receipt.phase)
        return F2523Result(
            envelope,
            MaterializationOutcome.QUALIFICATION_INCOMPLETE.value,
            phases,
            None,
            ("the injected topology did not admit the successor",),
            ("one-target discovery evaluated", "retune qualified", "physical hypothesis evaluated"),
        )
    receipts = [
        PhaseReceipt(
            "DIRECT_DUAL_SND_QUALIFICATION",
            PhaseState.SATISFIED.value,
            direct.phase_receipt.statement,
            direct.phase_receipt.artifact_hashes,
            direct.phase_receipt.properties,
        )
    ]
    try:
        discovery_artifacts = capture_discovery(direct)
        discovered = discover_one_target(
            discovery_artifacts,
            direct.center_hz,
            mother,
            profile_provider=profile_provider,
        )
        discovery_receipt = (
            discovered.phase_receipt
            if isinstance(discovered, _DiscoveryContext)
            else discovered
        )
        receipts.append(discovery_receipt)
        if not isinstance(discovered, _DiscoveryContext):
            receipts.extend(_not_evaluated(discovery_receipt.phase))
            outcome = (
                MaterializationOutcome.QUALIFICATION_INCOMPLETE
                if discovery_receipt.state == PhaseState.QUALIFICATION_ERROR.value
                else MaterializationOutcome.NO_FALSIFIABLE_INTERVENTION
            )
            return F2523Result(
                envelope,
                outcome.value,
                tuple(receipts),
                None,
                ("the admitted topology did not yield one target plus an orientation-neutral delta",),
                ("no signal existed", "retune qualified", "physical hypothesis evaluated"),
            )
        diagnostic_artifacts = capture_diagnostic(direct, discovered.geometry.delta_hz)
        qualified = qualify_distributed_witness(
            discovered,
            diagnostic_artifacts,
            mother,
            profile_provider=profile_provider,
        )
        witness_receipt = (
            qualified.phase_receipt
            if isinstance(qualified, WitnessQualification)
            else qualified
        )
        receipts.append(witness_receipt)
        if not isinstance(qualified, WitnessQualification):
            receipts.extend(_not_evaluated(witness_receipt.phase))
            outcome = (
                MaterializationOutcome.QUALIFICATION_INCOMPLETE
                if witness_receipt.state == PhaseState.QUALIFICATION_ERROR.value
                else MaterializationOutcome.INTERVENTION_NOT_QUALIFIED
            )
            return F2523Result(
                envelope,
                outcome.value,
                tuple(receipts),
                None,
                ("the target-independent witness did not qualify the intervention",),
                ("target physics evaluated", "retune is per-channel", "external RF proven"),
            )
        when = frozen_at or datetime.now(timezone.utc)
        plan = freeze_plan(direct, discovered, qualified, mother, frozen_at=when)
        receipts.append(
            PhaseReceipt(
                "PLAN_FREEZE",
                PhaseState.SATISFIED.value,
                "one target, distributed witness, predictions, controls and outcomes frozen",
                plan.discovery_artifact_hashes + plan.qualification_artifact_hashes,
                (
                    ("plan_hash", plan.plan_hash),
                    ("target_excluded_from_witness", "TRUE"),
                    ("confirmation_windows", "1"),
                    ("postfreeze_retry_budget", "0"),
                ),
            )
        )
        receipts.append(
            PhaseReceipt(
                "ONE_CONFIRMATION",
                PhaseState.NOT_EVALUATED.value,
                "future independent confirmation requires a separate post-commit seal and authority",
                (),
                (("live_execution_authorised", "FALSE"),),
            )
        )
        return F2523Result(
            envelope,
            MaterializationOutcome.PREFREEZE_PLAN_MATERIALIZED_OFFLINE.value,
            tuple(receipts),
            plan,
            ("a target-independent retune witness and future falsifiable target plan were materialized offline",),
            (
                "the live capability will expose the same fingerprint",
                "either target hypothesis is supported",
                "external RF proven",
                "future confirmation authorised",
            ),
        )
    finally:
        direct.close()


def assess_gate_f2_5_23() -> F2523Assessment:
    envelope = build_envelope()
    return F2523Assessment(
        F2523Exit.PREFREEZE_SUCCESSOR_MATERIALIZED_OFFLINE,
        f2522.audit_frozen_outcome().artifact_hash == PARENT_OUTCOME_SHA256,
        True,
        True,
        True,
        True,
        envelope.thresholds == f2522._thresholds(f2.MotherPlan()),
        True,
        True,
        True,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )


def strict_json(value: object) -> str:
    payload = strict_json_value(value)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def main() -> None:
    print(strict_json(assess_gate_f2_5_23()))


if __name__ == "__main__":
    main()
