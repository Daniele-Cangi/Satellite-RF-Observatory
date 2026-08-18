"""Gate F2.5.32: offline RF-response integration on open SND handles.

The module is a deliberately narrow successor to Gate F2.5.31.  It keeps the
same two injected SND handles alive through A1/B/A2, qualifies the already
reviewed target-excluded distributed RF witness, freezes the resulting target
predictions and only then evaluates the target feature.  It has no connector,
live authority or caller-controlled experiment parameters.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import inspect
import json
import math
from pathlib import Path

import numpy as np

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_5_22 as f2522
from . import kiwi_gate_f2_5_23 as f2523
from . import kiwi_gate_f2_5_24 as f2524
from . import kiwi_gate_f2_5_27 as f2527
from . import kiwi_gate_f2_5_31 as f2531
from .models import strict_json_value


TRANSFORM_VERSION = "gate-f2.5.32-open-handle-rf-response-v1"
REVIEWED_F2531_COMMIT = "70d5e51df3474cf59ffc8a8d645e7e50ecea6bec"
REVIEWED_F2531_SOURCE_SHA256 = (
    "dd447450510bd17d5b7ad1502fab84f86f5b129194d3b97550842ab5f8257672"
)
RAW_RF_PERSISTENCE = "ZERO"

CLAUSE_ORDER = (
    "command_time_topology",
    "target_excluded_distributed_witness",
    "witness_orientation_resolved",
    "target_plan_frozen_before_target_reveal",
    "target_detectable_on_both_A1_branches",
    "reference_target_fixed_through_A1_B_A2",
    "target_matches_upstream_prediction_B",
    "target_matches_channel_fixed_prediction_B",
    "negative_controls_absent",
    "target_returns_A2",
)


class F2532Exit(str, Enum):
    RF_RESPONSE_INTEGRATED_OFFLINE = "RF_RESPONSE_INTEGRATED_OFFLINE"
    SEAL_MISMATCH = "SEAL_MISMATCH"


class Outcome(str, Enum):
    CAPABILITY_REJECTED = "CAPABILITY_REJECTED"
    TOPOLOGY_NOT_ADMITTED = "TOPOLOGY_NOT_ADMITTED"
    TEMPORAL_NOT_ADMITTED = "TEMPORAL_NOT_ADMITTED"
    NO_FALSIFIABLE_INTERVENTION = "NO_FALSIFIABLE_INTERVENTION"
    INTERVENTION_INVALID = "INTERVENTION_INVALID"
    NOT_DETECTABLE = "NOT_DETECTABLE"
    UPSTREAM_OF_CHANNEL_DDC_SUPPORTED = "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    DOWNSTREAM_CHANNEL_FIXED_SUPPORTED = "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    QUALIFICATION_ERROR = "QUALIFICATION_ERROR"


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


def _canonical_source_sha256(path: Path) -> str:
    return sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def current_f2531_source_sha256() -> str:
    return _canonical_source_sha256(
        Path(__file__).resolve().parent / "kiwi_gate_f2_5_31.py"
    )


def _strict_hash(value: object) -> str:
    return sha256(
        json.dumps(
            strict_json_value(value),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            default=lambda item: item.value if isinstance(item, Enum) else str(item),
        ).encode("utf-8")
    ).hexdigest()


def _sha256(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("a lowercase SHA-256 string is required")


@dataclass(frozen=True, slots=True)
class F2532Plan:
    reviewed_f2531_commit: str
    reviewed_f2531_source_sha256: str
    reviewed_f2531_plan_hash: str
    technical_delta_hz: float
    phase_frame_count: int
    thresholds: tuple[tuple[str, float], ...]
    witness_transform_version: str
    target_evaluator_transform_version: str
    witness_precedes_target_reveal: bool
    target_excluded_from_witness: bool
    postfreeze_retry_budget: int
    public_runtime_overrides: tuple[str, ...]
    live_execution_authorised: bool
    raw_rf_persistence: str
    transform_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        mother = f2.MotherPlan()
        parent = f2531.build_plan()
        if self.reviewed_f2531_commit != REVIEWED_F2531_COMMIT:
            raise ValueError("reviewed F2.5.31 commit changed")
        if self.reviewed_f2531_source_sha256 != REVIEWED_F2531_SOURCE_SHA256:
            raise ValueError("reviewed F2.5.31 source changed")
        if self.reviewed_f2531_plan_hash != parent.plan_hash:
            raise ValueError("reviewed F2.5.31 plan changed")
        if self.technical_delta_hz != parent.technical_delta_hz:
            raise ValueError("technical delta changed")
        if self.phase_frame_count != parent.phase_frame_count:
            raise ValueError("phase frame count changed")
        expected = (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
            ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
            ("prediction_tolerance_bins", mother.prediction_tolerance_bins),
        )
        if self.thresholds != expected:
            raise ValueError("reviewed numerical thresholds changed")
        if self.witness_transform_version != f2522.TRANSFORM_VERSION:
            raise ValueError("distributed witness transform changed")
        if self.target_evaluator_transform_version != f2524.TRANSFORM_VERSION:
            raise ValueError("target evaluator transform changed")
        if not self.witness_precedes_target_reveal or not self.target_excluded_from_witness:
            raise ValueError("target-independent intervention admission is mandatory")
        if self.postfreeze_retry_budget or self.public_runtime_overrides:
            raise ValueError("retry and runtime overrides are forbidden")
        if self.live_execution_authorised:
            raise ValueError("offline integration cannot grant authority")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        if self.transform_versions != (
            f2531.TRANSFORM_VERSION,
            f2522.TRANSFORM_VERSION,
            f2524.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ):
            raise ValueError("transform ledger changed")

    @property
    def plan_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class FrozenTargetPlan:
    discovery_receipt_hash: str
    target: f2523.TargetFingerprint
    observed_translation_hz: float
    witness_orientation: int
    prediction_intervals: tuple[tuple[str, float, float], ...]
    controls: tuple[tuple[str, float], ...]
    thresholds: tuple[tuple[str, float], ...]
    qualification_artifact_hashes: tuple[str, ...]
    target_excluded_during_qualification: bool
    target_B_A2_revealed_after_plan_hash: bool
    postfreeze_retry_budget: int
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.discovery_receipt_hash)
        for item in self.qualification_artifact_hashes:
            _sha256(item)
        if self.witness_orientation not in (-1, 1):
            raise ValueError("frozen target plan needs a resolved orientation")
        if not math.isfinite(self.observed_translation_hz):
            raise ValueError("translation must be finite")
        if not self.target_excluded_during_qualification:
            raise ValueError("target leaked into intervention qualification")
        if not self.target_B_A2_revealed_after_plan_hash:
            raise ValueError("target reveal must follow plan hash materialisation")
        if self.postfreeze_retry_budget:
            raise ValueError("post-freeze retry is forbidden")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")
        intervals = {name: (low, high) for name, low, high in self.prediction_intervals}
        left = intervals["TARGET_UPSTREAM_B"]
        right = intervals["TARGET_CHANNEL_FIXED_B"]
        if max(left[0], right[0]) <= min(left[1], right[1]):
            raise ValueError("physical predictions overlap")

    @property
    def plan_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class ClauseReceipt:
    clause: str
    state: str
    statement: str
    artifact_hashes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.clause not in CLAUSE_ORDER:
            raise ValueError("unknown F2.5.32 clause")
        if self.state not in {item.value for item in ClauseState}:
            raise ValueError("unknown clause state")
        for item in self.artifact_hashes:
            _sha256(item)


@dataclass(frozen=True, slots=True)
class F2532RunResult:
    plan_hash: str
    frozen_target_plan: FrozenTargetPlan | None
    outcome: str
    branch_open_receipts: tuple[f2531.BranchOpenReceipt, f2531.BranchOpenReceipt]
    temporal_admission: f2527.RelativeTimingAdmissionReceipt | None
    discovery: f2531.DiscoveryReceipt | None
    command_receipts: tuple[f2531.InternalCommandReceipt, ...]
    boundary_receipts: tuple[f2527.BoundaryWitnessReceipt, ...]
    session_continuity: tuple[f2531.SessionContinuityReceipt, ...]
    distributed_witness: f2522.DistributedWitnessReceipt | None
    target_matches: tuple[f2524.TargetMatchReceipt, ...]
    clause_receipts: tuple[ClauseReceipt, ...]
    phases: tuple[f2531.PhaseReceipt, ...]
    cleanup: f2531.CleanupReceipt
    physical_hypothesis_state: str
    live_execution_authorised: bool
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    physical_decision_affected_by_description: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.plan_hash)
        if self.outcome not in {item.value for item in Outcome}:
            raise ValueError("unknown F2.5.32 outcome")
        if tuple(item.clause for item in self.clause_receipts) != CLAUSE_ORDER:
            raise ValueError("clauses must be complete and ordered")
        if tuple(item.phase for item in self.phases) != f2531.PHASE_ORDER:
            raise ValueError("lifecycle phases must be complete and ordered")
        physical = {
            Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED.value,
            Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED.value,
            Outcome.AMBIGUOUS.value,
        }
        expected_state = self.outcome if self.outcome in physical else "NOT_EVALUATED"
        if self.physical_hypothesis_state != expected_state:
            raise ValueError("physical state is inconsistent with the outcome")
        if self.live_execution_authorised or self.physical_decision_affected_by_description:
            raise ValueError("offline authority or descriptive decision leakage is forbidden")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2532Assessment:
    exit: F2532Exit
    plan: F2532Plan | None
    parent_commit_bound: bool
    parent_source_hash_matches: bool
    parent_plan_matches: bool
    distributed_witness_reused: bool
    target_reveal_order_enforced: bool
    all_physical_outcomes_implemented: bool
    no_public_execution_surface: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]
    raw_rf_persistence: str


@dataclass(frozen=True, slots=True)
class _PhysicalEvaluation:
    outcome: Outcome
    frozen_target_plan: FrozenTargetPlan | None
    witness: f2522.DistributedWitnessReceipt
    matches: tuple[f2524.TargetMatchReceipt, ...]
    clauses: tuple[ClauseReceipt, ...]
    statement: str


def _clause(
    name: str,
    value: bool | None,
    statement: str,
    hashes: tuple[str, ...] = (),
) -> ClauseReceipt:
    state = (
        ClauseState.NOT_EVALUATED
        if value is None
        else ClauseState.SATISFIED if value else ClauseState.UNSATISFIED
    )
    return ClauseReceipt(name, state.value, statement, hashes)


def _complete_clauses(receipts: list[ClauseReceipt], reason: str) -> None:
    known = {item.clause for item in receipts}
    for name in CLAUSE_ORDER:
        if name not in known:
            receipts.append(_clause(name, None, reason))


def _profile(
    frames: tuple[object, ...],
) -> f2._SpectralProfile:
    frequencies, residual, first, second = f2531._spectral_residual(frames)
    bin_hz = abs(float(np.median(np.diff(frequencies))))
    return f2._SpectralProfile(
        frequencies,
        residual.copy(),
        residual,
        first,
        second,
        bin_hz,
    )


def _phase_hash(frames: tuple[object, ...]) -> str:
    return _strict_hash(
        tuple(item.receipt.artifact_hash_before_analysis for item in frames)
    )


def _target_from_a1(
    discovery: f2531.DiscoveryReceipt,
    reference: f2._SpectralProfile,
    perturbed: f2._SpectralProfile,
) -> f2523.TargetFingerprint:
    if discovery.selected_baseband_hz is None:
        raise ValueError("target plan requires one admitted discovery feature")
    if not np.allclose(
        reference.frequencies_hz,
        perturbed.frequencies_hz,
        rtol=0.0,
        atol=1e-9,
    ):
        raise ValueError("A1 target grids differ")
    frequencies = reference.frequencies_hz
    index = int(np.argmin(np.abs(frequencies - discovery.selected_baseband_hz)))
    left = f2._normalized_neighbourhood(reference.residual_db, index)
    right = f2._normalized_neighbourhood(perturbed.residual_db, index)
    if left is None or right is None:
        raise ValueError("admitted target neighbourhood is incomplete")
    neighbourhood = tuple(float((a + b) / 2.0) for a, b in zip(left, right))
    bin_hz = reference.bin_hz
    mother = f2.MotherPlan()
    first = float(discovery.first_half_contrast_db)
    second = float(discovery.second_half_contrast_db)
    contrast = float(discovery.joint_contrast_db)
    correlation = float(discovery.cross_branch_correlation)
    return f2523.TargetFingerprint(
        float(frequencies[index]),
        bin_hz,
        neighbourhood,
        (first, second, abs(first - second)),
        (min(first, second), contrast),
        mother.prediction_tolerance_bins * bin_hz,
        correlation,
    )


def _freeze_target_plan(
    discovery: f2531.DiscoveryReceipt,
    target: f2523.TargetFingerprint,
    witness: f2522.DistributedWitnessReceipt,
    observed_translation_hz: float,
) -> FrozenTargetPlan:
    tolerance = target.uncertainty_hz
    position = target.baseband_position_a_hz
    predictions = (
        (
            "TARGET_UPSTREAM_B",
            position + observed_translation_hz - tolerance,
            position + observed_translation_hz + tolerance,
        ),
        ("TARGET_CHANNEL_FIXED_B", position - tolerance, position + tolerance),
        ("TARGET_A2_RETURN", position - tolerance, position + tolerance),
        ("REFERENCE_TARGET_FIXED", position - tolerance, position + tolerance),
    )
    controls = (
        ("WRONG_SIGN_B", position - observed_translation_hz),
        ("HALF_MAGNITUDE_B", position + observed_translation_hz / 2.0),
        ("OFF_FEATURE_B", position + observed_translation_hz * 2.5),
    )
    mother = f2.MotherPlan()
    return FrozenTargetPlan(
        discovery.receipt_hash,
        target,
        observed_translation_hz,
        int(witness.learned_orientation),
        predictions,
        controls,
        (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
            ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
            ("prediction_tolerance_bins", mother.prediction_tolerance_bins),
        ),
        witness.input_artifact_hashes,
        True,
        True,
        0,
        RAW_RF_PERSISTENCE,
    )


def _evaluate_rf_response(
    *,
    discovery: f2531.DiscoveryReceipt,
    reference_a1: tuple[object, ...],
    reference_b: tuple[object, ...],
    reference_a2: tuple[object, ...],
    perturbed_a1: tuple[object, ...],
    perturbed_b: tuple[object, ...],
    perturbed_a2: tuple[object, ...],
) -> _PhysicalEvaluation:
    """Qualify intervention first; reveal B/A2 target only after plan freeze."""

    frames = (
        reference_a1,
        reference_b,
        reference_a2,
        perturbed_a1,
        perturbed_b,
        perturbed_a2,
    )
    # Bind six phase-level artifact identities from the already pre-decode SND
    # hashes before the first spectral transform touches IQ.
    hashes = tuple(_phase_hash(item) for item in frames)
    profiles = tuple(_profile(item) for item in frames)
    frequencies = profiles[0].frequencies_hz
    if any(
        not np.allclose(frequencies, item.frequencies_hz, rtol=0.0, atol=1e-9)
        for item in profiles[1:]
    ):
        raise ValueError("A1/B/A2 frequency grids differ")
    target = _target_from_a1(discovery, profiles[0], profiles[3])
    target_index = int(
        np.argmin(np.abs(frequencies - target.baseband_position_a_hz))
    )
    bin_hz = profiles[0].bin_hz
    delta_bins = int(round(f2531.TECHNICAL_DELTA_HZ / bin_hz))
    effective_delta_hz = delta_bins * bin_hz
    if delta_bins <= 0 or abs(effective_delta_hz - f2531.TECHNICAL_DELTA_HZ) > target.uncertainty_hz:
        raise ValueError("STFT grid cannot represent the reviewed retune delta")
    target_radius = max(
        (len(target.local_neighbourhood) - 1) // 2,
        int(math.ceil(max(target.bandwidth_hz, target.uncertainty_hz) / bin_hz)),
    )
    witness = f2522.assess_distributed_witness(
        reference_a1=profiles[0].residual_db,
        reference_b=profiles[1].residual_db,
        reference_a2=profiles[2].residual_db,
        perturbed_a1=profiles[3].residual_db,
        perturbed_b=profiles[4].residual_db,
        perturbed_a2=profiles[5].residual_db,
        input_artifact_hashes=hashes,
        delta_bins=delta_bins,
        target_index=target_index,
        target_exclusion_radius=target_radius,
        minimum_fingerprint_correlation=f2.MotherPlan().minimum_fingerprint_correlation,
    )
    clauses = [
        _clause(
            "command_time_topology",
            True,
            "both scalar boundaries and full-session continuity admitted RF analysis",
            hashes,
        ),
        _clause(
            "target_excluded_distributed_witness",
            witness.state == f2522.WitnessState.QUALIFIED_AS_FUTURE_WITNESS.value,
            "the distributed witness used only bins outside all target control positions",
            hashes,
        ),
    ]
    if witness.state == f2522.WitnessState.NOT_DETECTABLE.value:
        clauses.append(
            _clause(
                "witness_orientation_resolved",
                None,
                "the target-excluded RF structure was not detectable",
                hashes,
            )
        )
        _complete_clauses(clauses, "intervention admission blocked target reveal")
        return _PhysicalEvaluation(
            Outcome.NOT_DETECTABLE,
            None,
            witness,
            (),
            tuple(clauses),
            "the target-independent intervention witness was not detectable",
        )
    if witness.state != f2522.WitnessState.QUALIFIED_AS_FUTURE_WITNESS.value:
        clauses.append(
            _clause(
                "witness_orientation_resolved",
                False,
                "no unique non-zero perturbed-branch translation survived the controls",
                hashes,
            )
        )
        _complete_clauses(clauses, "invalid intervention blocked target reveal")
        return _PhysicalEvaluation(
            Outcome.INTERVENTION_INVALID,
            None,
            witness,
            (),
            tuple(clauses),
            "the RF response did not uniquely witness the per-channel retune",
        )

    assert witness.learned_orientation is not None
    observed_translation_hz = witness.learned_orientation * effective_delta_hz
    frozen = _freeze_target_plan(
        discovery, target, witness, observed_translation_hz
    )
    # The immutable hash is materialised before any target match reads B/A2.
    frozen.plan_hash
    clauses.extend(
        (
            _clause(
                "witness_orientation_resolved",
                True,
                "the target-excluded fingerprint selected one retune orientation",
                hashes,
            ),
            _clause(
                "target_plan_frozen_before_target_reveal",
                True,
                "prediction intervals and negative controls were hashed before target matching",
                (frozen.plan_hash,),
            ),
        )
    )

    position = target.baseband_position_a_hz
    controls = dict(frozen.controls)
    expected = (
        ("reference_A1", profiles[0], position),
        ("perturbed_A1", profiles[3], position),
        ("reference_B", profiles[1], position),
        ("perturbed_B_upstream", profiles[4], position + observed_translation_hz),
        ("perturbed_B_channel_fixed", profiles[4], position),
        ("wrong_sign_B", profiles[4], controls["WRONG_SIGN_B"]),
        ("half_magnitude_B", profiles[4], controls["HALF_MAGNITUDE_B"]),
        ("off_feature_B", profiles[4], controls["OFF_FEATURE_B"]),
        ("reference_A2", profiles[2], position),
        ("perturbed_A2", profiles[5], position),
    )
    mother = f2.MotherPlan()
    matches = tuple(
        f2524._target_match(
            profile,
            target,
            expected_hz,
            target.uncertainty_hz,
            mother,
            label,
        )
        for label, profile, expected_hz in expected
    )
    matched = {item.label: item.matched for item in matches}
    a1_detectable = matched["reference_A1"] and matched["perturbed_A1"]
    reference_fixed = all(
        matched[item] for item in ("reference_A1", "reference_B", "reference_A2")
    )
    target_return = matched["reference_A2"] and matched["perturbed_A2"]
    upstream = matched["perturbed_B_upstream"]
    downstream = matched["perturbed_B_channel_fixed"]
    controls_absent = not any(
        matched[item]
        for item in ("wrong_sign_B", "half_magnitude_B", "off_feature_B")
    )
    clauses.extend(
        (
            _clause("target_detectable_on_both_A1_branches", a1_detectable, "the frozen fingerprint is present on both A1 branches", hashes),
            _clause("reference_target_fixed_through_A1_B_A2", reference_fixed, "the fixed branch preserves the target through all phases", hashes),
            _clause("target_matches_upstream_prediction_B", upstream if a1_detectable and reference_fixed else None, "B is tested only in the frozen upstream interval", hashes),
            _clause("target_matches_channel_fixed_prediction_B", downstream if a1_detectable and reference_fixed else None, "B is tested only in the frozen channel-fixed interval", hashes),
            _clause("negative_controls_absent", controls_absent if a1_detectable and reference_fixed else None, "wrong-sign, half-delta and off-feature controls remain empty", hashes),
            _clause("target_returns_A2", target_return if a1_detectable and reference_fixed else None, "the target returns on the perturbed A2 branch", hashes),
        )
    )
    if not (a1_detectable and reference_fixed and target_return):
        outcome = Outcome.NOT_DETECTABLE
        statement = "the frozen target detectability envelope was not preserved"
    elif upstream and not downstream and controls_absent:
        outcome = Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED
        statement = "the feature followed the witnessed DDC coordinate translation"
    elif downstream and not upstream and controls_absent:
        outcome = Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED
        statement = "the feature remained channel-fixed while the distributed witness translated"
    else:
        outcome = Outcome.AMBIGUOUS
        statement = "the valid intervention did not uniquely select one frozen prediction"
    return _PhysicalEvaluation(
        outcome,
        frozen,
        witness,
        matches,
        tuple(clauses),
        statement,
    )


def _run_open_handle_rf_injected(
    *,
    reference_socket: object,
    perturbed_socket: object,
) -> F2532RunResult:
    """Private synthetic lifecycle seam; it has no network or authority surface."""

    plan = build_plan()
    phases: list[f2531.PhaseReceipt] = []
    commands: list[f2531.InternalCommandReceipt] = []
    boundaries: list[f2527.BoundaryWitnessReceipt] = []
    continuity: tuple[f2531.SessionContinuityReceipt, ...] = ()
    temporal: f2527.RelativeTimingAdmissionReceipt | None = None
    discovery: f2531.DiscoveryReceipt | None = None
    physical: _PhysicalEvaluation | None = None
    handles: list[f2531._Handle] = []
    outcome = Outcome.QUALIFICATION_ERROR

    with ThreadPoolExecutor(max_workers=2) as pool:
        reference_future = pool.submit(f2531._open_handle, reference_socket, "reference")
        perturbed_future = pool.submit(f2531._open_handle, perturbed_socket, "perturbed")
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
            phases.append(f2531._phase(f2531.PHASE_ORDER[0], f2531.PhaseState.UNSATISFIED, "an injected branch contains an explicit server rejection"))
            f2531._complete_not_evaluated(phases, "dual handles were not admitted")
            outcome = Outcome.CAPABILITY_REJECTED
        elif states != {"HANDLE_OPEN"}:
            phases.append(f2531._phase(f2531.PHASE_ORDER[0], f2531.PhaseState.QUALIFICATION_ERROR, "an injected branch could not materialize an owned handle"))
            f2531._complete_not_evaluated(phases, "handle qualification error blocked phases")
        else:
            reference = reference_attempt.handle
            perturbed = perturbed_attempt.handle
            assert reference is not None and perturbed is not None
            if reference.channel_id == perturbed.channel_id or not math.isclose(
                reference.sample_rate_hz,
                perturbed.sample_rate_hz,
                rel_tol=0.0,
                abs_tol=f2527.build_plan().maximum_sample_rate_difference_hz,
            ):
                phases.append(f2531._phase(f2531.PHASE_ORDER[0], f2531.PhaseState.UNSATISFIED, "open handles do not preserve distinct same-rate channels"))
                f2531._complete_not_evaluated(phases, "channel topology was not admitted")
                outcome = Outcome.TOPOLOGY_NOT_ADMITTED
            else:
                phases.append(f2531._phase(f2531.PHASE_ORDER[0], f2531.PhaseState.SATISFIED, "two distinct SND handles are owned by one outer scope", tuple(item.receipt_hash for item in open_receipts)))
                reference_a1, perturbed_a1 = f2531._collect_pair_count(reference, perturbed, f2531.PHASE_FRAME_COUNT)
                temporal = f2527.evaluate_relative_timing(
                    tuple(item.receipt for item in reference_a1),
                    tuple(item.receipt for item in perturbed_a1),
                )
                if temporal.state != f2527.AdmissionState.ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT.value:
                    phases.append(f2531._phase(f2531.PHASE_ORDER[1], f2531.PhaseState.UNSATISFIED, "initial A1 frames failed relative-time admission"))
                    f2531._complete_not_evaluated(phases, "temporal admission blocked discovery")
                    outcome = Outcome.TEMPORAL_NOT_ADMITTED
                else:
                    phases.append(f2531._phase(f2531.PHASE_ORDER[1], f2531.PhaseState.SATISFIED, "initial A1 frames satisfy relative-time admission"))
                    discovery = f2531._discover_one_feature(reference_a1, perturbed_a1)
                    if discovery.state != "ONE_FEATURE_ADMITTED":
                        phases.append(f2531._phase(f2531.PHASE_ORDER[2], f2531.PhaseState.UNSATISFIED, "unchanged thresholds admitted no common A1 feature", discovery.input_artifact_hashes))
                        f2531._complete_not_evaluated(phases, "no feature admitted intervention")
                        outcome = Outcome.NO_FALSIFIABLE_INTERVENTION
                    else:
                        phases.append(f2531._phase(f2531.PHASE_ORDER[2], f2531.PhaseState.SATISFIED, "one common A1 feature was selected before either command", (discovery.receipt_hash,)))
                        executor = f2531._InternalRetuneExecutor(reference, perturbed, f2531.build_plan())
                        command_b = executor.transition("A1_TO_B", f2531.build_plan().center_a_hz + f2531.TECHNICAL_DELTA_HZ, perturbed_a1[-1].receipt, reference_a1[-1].receipt)
                        commands.append(command_b)
                        reference_b, perturbed_b = f2531._collect_pair_postsettling(reference, perturbed, command_b.settling_complete_monotonic_ns + perturbed_a1[-1].receipt.sample_duration_ns, f2531.PHASE_FRAME_COUNT)
                        boundary_b = f2531._boundary(command_b, perturbed_before=perturbed_a1[-1].receipt, perturbed_after=perturbed_b[0].receipt, reference_before=reference_a1[-1].receipt, reference_after=reference_b[0].receipt)
                        boundaries.append(boundary_b)
                        b_valid = boundary_b.state == f2527.BoundaryState.BOUNDARY_WITNESSED.value
                        phases.append(f2531._phase(f2531.PHASE_ORDER[3], f2531.PhaseState.SATISFIED if b_valid else f2531.PhaseState.UNSATISFIED, boundary_b.statement, (boundary_b.anchor_receipt_hash,)))
                        if not b_valid:
                            f2531._complete_not_evaluated(phases, "A1_TO_B boundary was invalid")
                            outcome = Outcome.INTERVENTION_INVALID
                        else:
                            command_a2 = executor.transition("B_TO_A2", f2531.build_plan().center_a_hz, perturbed_b[-1].receipt, reference_b[-1].receipt)
                            commands.append(command_a2)
                            reference_a2, perturbed_a2 = f2531._collect_pair_postsettling(reference, perturbed, command_a2.settling_complete_monotonic_ns + perturbed_b[-1].receipt.sample_duration_ns, f2531.PHASE_FRAME_COUNT)
                            boundary_a2 = f2531._boundary(command_a2, perturbed_before=perturbed_b[-1].receipt, perturbed_after=perturbed_a2[0].receipt, reference_before=reference_b[-1].receipt, reference_after=reference_a2[0].receipt)
                            boundaries.append(boundary_a2)
                            continuity = (f2531._continuity(reference), f2531._continuity(perturbed))
                            a2_valid = boundary_a2.state == f2527.BoundaryState.BOUNDARY_WITNESSED.value
                            continuous = all(item.state == "SATISFIED" for item in continuity)
                            phases.append(f2531._phase(f2531.PHASE_ORDER[4], f2531.PhaseState.SATISFIED if a2_valid and continuous else f2531.PhaseState.UNSATISFIED, "B_TO_A2 and full-session continuity are valid" if a2_valid and continuous else "return boundary or session continuity is invalid", (boundary_a2.anchor_receipt_hash,)))
                            if not (a2_valid and continuous):
                                f2531._complete_not_evaluated(phases, "command/time topology was invalid")
                                outcome = Outcome.INTERVENTION_INVALID
                            else:
                                physical = _evaluate_rf_response(
                                    discovery=discovery,
                                    reference_a1=reference_a1,
                                    reference_b=reference_b,
                                    reference_a2=reference_a2,
                                    perturbed_a1=perturbed_a1,
                                    perturbed_b=perturbed_b,
                                    perturbed_a2=perturbed_a2,
                                )
                                outcome = physical.outcome
                                if physical.frozen_target_plan is None:
                                    phases.append(f2531._phase(f2531.PHASE_ORDER[5], f2531.PhaseState.NOT_EVALUATED, "target-independent intervention admission blocked plan freeze"))
                                    phases.append(f2531._phase(f2531.PHASE_ORDER[6], f2531.PhaseState.NOT_EVALUATED, "target feature was not revealed"))
                                else:
                                    phases.append(f2531._phase(f2531.PHASE_ORDER[5], f2531.PhaseState.SATISFIED, "target predictions and controls were immutably hashed before target reveal", (physical.frozen_target_plan.plan_hash,)))
                                    phases.append(f2531._phase(f2531.PHASE_ORDER[6], f2531.PhaseState.SATISFIED, physical.statement, tuple(item.receipt.artifact_hash_before_analysis for item in reference_a2 + perturbed_a2)))
    except Exception as error:
        if len(phases) < len(f2531.PHASE_ORDER):
            phases.append(f2531._phase(f2531.PHASE_ORDER[len(phases)], f2531.PhaseState.QUALIFICATION_ERROR, f"offline RF transform error: {type(error).__name__}"))
        f2531._complete_not_evaluated(phases, "qualification error blocked later phases")
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
        attempt.handle.frame_lease_count if attempt.handle is not None else attempt.receipt.frame_lease_count
        for attempt in (reference_attempt, perturbed_attempt)
    )
    release_count = sum(
        attempt.handle.frame_release_count if attempt.handle is not None else attempt.receipt.frame_release_count
        for attempt in (reference_attempt, perturbed_attempt)
    )
    cleanup = f2531.CleanupReceipt(
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
    clauses = list(physical.clauses if physical is not None else ())
    _complete_clauses(clauses, "an upstream lifecycle clause blocked RF evaluation")
    physical_outcomes = {
        Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED,
        Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED,
        Outcome.AMBIGUOUS,
    }
    return F2532RunResult(
        plan.plan_hash,
        physical.frozen_target_plan if physical is not None else None,
        outcome.value,
        open_receipts,
        temporal,
        discovery,
        tuple(commands),
        tuple(boundaries),
        continuity,
        physical.witness if physical is not None else None,
        physical.matches if physical is not None else (),
        tuple(clauses),
        tuple(phases),
        cleanup,
        outcome.value if outcome in physical_outcomes else "NOT_EVALUATED",
        False,
        (
            (
                f"within injected synthetic IQ: {physical.statement}"
                if physical is not None
                else "RF hypotheses were not evaluated"
            ),
            "the target-excluded witness was evaluated before any target B/A2 match",
            "all RF arrays were destroyed before return",
        ),
        (
            "external RF origin",
            "transmitter identity",
            "remote command acknowledgement",
            "a live Kiwi outcome",
            "a second confirmation",
        ),
        False,
        RAW_RF_PERSISTENCE,
    )


def build_plan() -> F2532Plan:
    mother = f2.MotherPlan()
    return F2532Plan(
        REVIEWED_F2531_COMMIT,
        REVIEWED_F2531_SOURCE_SHA256,
        f2531.build_plan().plan_hash,
        f2531.TECHNICAL_DELTA_HZ,
        f2531.PHASE_FRAME_COUNT,
        (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
            ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
            ("prediction_tolerance_bins", mother.prediction_tolerance_bins),
        ),
        f2522.TRANSFORM_VERSION,
        f2524.TRANSFORM_VERSION,
        True,
        True,
        0,
        (),
        False,
        RAW_RF_PERSISTENCE,
        (
            f2531.TRANSFORM_VERSION,
            f2522.TRANSFORM_VERSION,
            f2524.TRANSFORM_VERSION,
            TRANSFORM_VERSION,
        ),
    )


def assess() -> F2532Assessment:
    commit_bound = REVIEWED_F2531_COMMIT == "70d5e51df3474cf59ffc8a8d645e7e50ecea6bec"
    source_match = current_f2531_source_sha256() == REVIEWED_F2531_SOURCE_SHA256
    parent = f2531.assess()
    parent_match = (
        parent.exit is f2531.F2531Exit.OPEN_HANDLE_SUCCESSOR_MATERIALIZED_OFFLINE
        and parent.plan is not None
        and parent.plan.plan_hash == f2531.build_plan().plan_hash
    )
    blockers = tuple(
        message
        for condition, message in (
            (commit_bound, "reviewed F2.5.31 commit changed"),
            (source_match, "reviewed F2.5.31 source changed"),
            (parent_match, "reviewed F2.5.31 plan changed"),
        )
        if not condition
    )
    return F2532Assessment(
        F2532Exit.RF_RESPONSE_INTEGRATED_OFFLINE if not blockers else F2532Exit.SEAL_MISMATCH,
        build_plan() if not blockers else None,
        commit_bound,
        source_match,
        parent_match,
        True,
        True,
        True,
        True,
        False,
        blockers,
        RAW_RF_PERSISTENCE,
    )


def strict_json(value: object) -> str:
    return json.dumps(
        strict_json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _integration_surface_hash() -> str:
    return sha256(inspect.getsource(_run_open_handle_rf_injected).encode()).hexdigest()


__all__ = [
    "F2532Assessment",
    "F2532Exit",
    "F2532Plan",
    "F2532RunResult",
    "Outcome",
    "assess",
    "build_plan",
    "strict_json",
]
