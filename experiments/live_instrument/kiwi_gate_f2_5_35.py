"""Gate F2.5.35: decision-independent scalar discovery audit.

The frozen Gate F2.5.31--34 sources are not modified.  This offline successor
replays the same one-feature selector over injected ephemeral IQ and emits two
sibling receipts: the authoritative selection decision and a scalar-only
description of every admission stage.  Description failure cannot change the
decision or the downstream physical control flow.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import Enum
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Callable, Sequence

import numpy as np
from scipy import signal

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_5_22 as f2522
from . import kiwi_gate_f2_5_27 as f2527
from . import kiwi_gate_f2_5_28 as f2528
from . import kiwi_gate_f2_5_31 as f2531
from . import kiwi_gate_f2_5_32 as f2532
from . import kiwi_gate_f2_5_34 as f2534
from .models import strict_json_value


TRANSFORM_VERSION = "gate-f2.5.35-decision-independent-discovery-audit-v1"
REVIEWED_F2534_COMMIT = "f8d003c44cf4b9e98cea2ff6fd3c746bbb61b1e4"
REVIEWED_F2534_SOURCE_SHA256 = (
    "96ff3d14bce70e6874841d33a0329ba23739277d3289415e9df7d842eccedeb0"
)
REVIEWED_F2532_SOURCE_SHA256 = (
    "d38a3bdf4669ed7b0e27d9cff1399d9fd2744b4bdc909e7e687cb88a2b7daf1b"
)
RAW_RF_PERSISTENCE = "ZERO"


class AuditState(str, Enum):
    COMPLETE = "COMPLETE"
    DESCRIPTION_ERROR = "DESCRIPTION_ERROR"


class F2535Exit(str, Enum):
    SCALAR_AUDIT_INTEGRATED_OFFLINE = "SCALAR_AUDIT_INTEGRATED_OFFLINE"
    SOURCE_SEAL_MISMATCH = "SOURCE_SEAL_MISMATCH"


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
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("a lowercase SHA-256 string is required")


def _canonical_source_sha256(path: Path) -> str:
    return sha256(
        path.read_text(encoding="utf-8").replace("\r\n", "\n").encode()
    ).hexdigest()


def current_f2534_source_sha256() -> str:
    return _canonical_source_sha256(Path(__file__).parent / "kiwi_gate_f2_5_34.py")


def current_f2532_source_sha256() -> str:
    return _canonical_source_sha256(Path(__file__).parent / "kiwi_gate_f2_5_32.py")


def _finite_or_not_evaluated(
    value: float | None,
    unit: str,
    reason: str,
) -> f2522.NumericObservation:
    if value is None:
        return f2522.NumericObservation("NOT_EVALUATED", None, unit, reason)
    if not math.isfinite(value):
        raise ValueError("audit scalars must be finite or explicitly not evaluated")
    return f2522.NumericObservation("FINITE", float(value), unit, reason)


@dataclass(frozen=True, slots=True)
class ScalarDiscoveryAuditReceipt:
    transform_version: str
    decision_receipt_hash: str
    decision_state: str
    input_artifact_hashes: tuple[str, ...]
    hashes_bound_before_analysis: bool
    thresholds: tuple[tuple[str, float], ...]
    stft_geometry: tuple[tuple[str, int], ...]
    valid_grid_bin_count: int
    raw_peak_count: int
    patch_incomplete_count: int
    patch_valid_count: int
    correlation_below_threshold_count: int
    correlation_pass_count: int
    half_stability_below_threshold_count: int
    half_stability_pass_count: int
    admitted_feature_count: int
    best_valid_joint_contrast_db: f2522.NumericObservation
    best_joint_contrast_margin_db: f2522.NumericObservation
    best_patch_correlation: f2522.NumericObservation
    best_correlation_margin: f2522.NumericObservation
    best_correlation_pass_half_contrast_db: f2522.NumericObservation
    best_half_stability_margin_db: f2522.NumericObservation
    selector_authoritative: bool
    audit_can_change_decision: bool
    candidate_arrays_persisted: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.decision_receipt_hash)
        if self.decision_state not in {"ONE_FEATURE_ADMITTED", "NO_FEATURE_ADMITTED"}:
            raise ValueError("unknown discovery decision state")
        if len(self.input_artifact_hashes) != 2 * f2531.PHASE_FRAME_COUNT:
            raise ValueError("audit must bind every A1 frame from both branches")
        for item in self.input_artifact_hashes:
            _sha256(item)
        if not self.hashes_bound_before_analysis:
            raise ValueError("post-analysis-only lineage is forbidden")
        counts = (
            self.valid_grid_bin_count,
            self.raw_peak_count,
            self.patch_incomplete_count,
            self.patch_valid_count,
            self.correlation_below_threshold_count,
            self.correlation_pass_count,
            self.half_stability_below_threshold_count,
            self.half_stability_pass_count,
            self.admitted_feature_count,
        )
        if any(item < 0 for item in counts):
            raise ValueError("audit counts cannot be negative")
        if self.raw_peak_count != self.patch_incomplete_count + self.patch_valid_count:
            raise ValueError("patch-stage counts do not close")
        if self.patch_valid_count != (
            self.correlation_below_threshold_count + self.correlation_pass_count
        ):
            raise ValueError("correlation-stage counts do not close")
        if self.correlation_pass_count != (
            self.half_stability_below_threshold_count + self.half_stability_pass_count
        ):
            raise ValueError("half-stability-stage counts do not close")
        if self.half_stability_pass_count != self.admitted_feature_count:
            raise ValueError("admitted count does not close")
        expected_state = (
            "ONE_FEATURE_ADMITTED" if self.admitted_feature_count else "NO_FEATURE_ADMITTED"
        )
        if self.decision_state != expected_state:
            raise ValueError("audit counts conflict with the authoritative decision")
        if not self.selector_authoritative or self.audit_can_change_decision:
            raise ValueError("descriptive audit leaked into selection authority")
        if self.candidate_arrays_persisted or self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF-derived arrays cannot persist")

    @property
    def receipt_hash(self) -> str:
        return _strict_hash(asdict(self))


@dataclass(frozen=True, slots=True)
class DiscoveryAuditEnvelope:
    state: AuditState
    decision_receipt_hash: str
    input_artifact_hashes: tuple[str, ...]
    receipt: ScalarDiscoveryAuditReceipt | None
    description_error_type: str | None
    description_error_hash: str | None
    physical_decision_affected: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        _sha256(self.decision_receipt_hash)
        for item in self.input_artifact_hashes:
            _sha256(item)
        if self.state is AuditState.COMPLETE:
            if self.receipt is None or self.description_error_type is not None or self.description_error_hash is not None:
                raise ValueError("complete audit envelope is inconsistent")
            if self.receipt.decision_receipt_hash != self.decision_receipt_hash:
                raise ValueError("audit receipt is not a sibling of this decision")
        else:
            if self.receipt is not None or self.description_error_type is None or self.description_error_hash is None:
                raise ValueError("description error envelope is incomplete")
            _sha256(self.description_error_hash)
        if self.physical_decision_affected:
            raise ValueError("description cannot change the physical decision")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class _DiscoveryTrace:
    input_artifact_hashes: tuple[str, ...]
    valid_grid_bin_count: int
    raw_peak_count: int
    patch_incomplete_count: int
    patch_valid_count: int
    correlation_below_threshold_count: int
    correlation_pass_count: int
    half_stability_below_threshold_count: int
    half_stability_pass_count: int
    admitted_feature_count: int
    best_valid_joint_contrast_db: float | None
    best_patch_correlation: float | None
    best_correlation_pass_half_contrast_db: float | None


def _build_scalar_audit(
    decision: f2531.DiscoveryReceipt,
    trace: _DiscoveryTrace,
) -> ScalarDiscoveryAuditReceipt:
    mother = f2.MotherPlan()
    best_joint = trace.best_valid_joint_contrast_db
    best_correlation = trace.best_patch_correlation
    best_half = trace.best_correlation_pass_half_contrast_db
    return ScalarDiscoveryAuditReceipt(
        TRANSFORM_VERSION,
        decision.receipt_hash,
        decision.state,
        trace.input_artifact_hashes,
        True,
        (
            ("minimum_contrast_db", mother.minimum_contrast_db),
            ("minimum_half_contrast_db", mother.minimum_half_contrast_db),
            ("minimum_fingerprint_correlation", mother.minimum_fingerprint_correlation),
        ),
        (("nperseg", mother.nperseg), ("noverlap", mother.noverlap)),
        trace.valid_grid_bin_count,
        trace.raw_peak_count,
        trace.patch_incomplete_count,
        trace.patch_valid_count,
        trace.correlation_below_threshold_count,
        trace.correlation_pass_count,
        trace.half_stability_below_threshold_count,
        trace.half_stability_pass_count,
        trace.admitted_feature_count,
        _finite_or_not_evaluated(best_joint, "dB", "maximum valid joint residual"),
        _finite_or_not_evaluated(
            None if best_joint is None else best_joint - mother.minimum_contrast_db,
            "dB",
            "relative to the frozen joint-contrast threshold",
        ),
        _finite_or_not_evaluated(
            best_correlation,
            "ratio",
            "maximum correlation among patch-valid candidates",
        ),
        _finite_or_not_evaluated(
            None if best_correlation is None else best_correlation - mother.minimum_fingerprint_correlation,
            "ratio",
            "relative to the frozen correlation threshold",
        ),
        _finite_or_not_evaluated(
            best_half,
            "dB",
            "maximum minimum-half contrast among correlation-passing candidates",
        ),
        _finite_or_not_evaluated(
            None if best_half is None else best_half - mother.minimum_half_contrast_db,
            "dB",
            "relative to the frozen half-stability threshold",
        ),
        True,
        False,
        False,
        RAW_RF_PERSISTENCE,
    )


AuditBuilder = Callable[
    [f2531.DiscoveryReceipt, _DiscoveryTrace],
    ScalarDiscoveryAuditReceipt,
]


def _decision_and_trace(
    reference: Sequence[f2528._EphemeralDecodedFrame],
    perturbed: Sequence[f2528._EphemeralDecodedFrame],
) -> tuple[f2531.DiscoveryReceipt, _DiscoveryTrace]:
    """Run the unchanged selector and retain only scalar sufficient statistics."""

    mother = f2.MotherPlan()
    hashes = tuple(
        item.receipt.artifact_hash_before_analysis
        for item in tuple(reference) + tuple(perturbed)
    )
    left_f, left, left_first, left_second = f2531._spectral_residual(reference)
    right_f, right, right_first, right_second = f2531._spectral_residual(perturbed)
    arrays = (
        left_f,
        left,
        left_first,
        left_second,
        right_f,
        right,
        right_first,
        right_second,
    )
    try:
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
        patch_incomplete = 0
        patch_valid = 0
        correlation_below = 0
        correlation_pass = 0
        half_below = 0
        half_pass = 0
        correlations: list[float] = []
        correlation_pass_halves: list[float] = []
        for raw_index in candidates:
            index = int(raw_index)
            left_patch = f2._normalized_neighbourhood(left, index)
            right_patch = f2._normalized_neighbourhood(right, index)
            if left_patch is None or right_patch is None:
                patch_incomplete += 1
                continue
            patch_valid += 1
            correlation = f2._correlation(left_patch, right_patch)
            correlations.append(correlation)
            first = float(min(left_first[index], right_first[index]))
            second = float(min(left_second[index], right_second[index]))
            contrast = float(joint[index])
            if correlation < mother.minimum_fingerprint_correlation:
                correlation_below += 1
                continue
            correlation_pass += 1
            minimum_half = min(first, second)
            correlation_pass_halves.append(minimum_half)
            if minimum_half < mother.minimum_half_contrast_db:
                half_below += 1
                continue
            half_pass += 1
            ranked.append(
                (
                    (correlation, minimum_half, contrast, -abs(float(left_f[index]))),
                    (float(left_f[index]), contrast, first, second, correlation),
                )
            )
        if not ranked:
            decision = f2531.DiscoveryReceipt(
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
        else:
            selected = max(ranked, key=lambda item: item[0])[1]
            decision = f2531.DiscoveryReceipt(
                "ONE_FEATURE_ADMITTED",
                *selected,
                hashes,
                "UNCHANGED_MOTHER_PLAN",
                "NOT_EVALUATED",
            )
        valid_values = joint[valid]
        trace = _DiscoveryTrace(
            hashes,
            int(np.count_nonzero(valid)),
            len(candidates),
            patch_incomplete,
            patch_valid,
            correlation_below,
            correlation_pass,
            half_below,
            half_pass,
            len(ranked),
            float(np.max(valid_values)) if valid_values.size else None,
            max(correlations) if correlations else None,
            max(correlation_pass_halves) if correlation_pass_halves else None,
        )
        return decision, trace
    finally:
        for array in arrays:
            array.fill(0)
        if "joint" in locals():
            joint.fill(0)


def discover_with_scalar_audit(
    reference: Sequence[f2528._EphemeralDecodedFrame],
    perturbed: Sequence[f2528._EphemeralDecodedFrame],
    *,
    _audit_builder: AuditBuilder = _build_scalar_audit,
) -> tuple[f2531.DiscoveryReceipt, DiscoveryAuditEnvelope]:
    """Return decision first; convert any audit failure into description state."""

    decision, trace = _decision_and_trace(reference, perturbed)
    try:
        audit = _audit_builder(decision, trace)
    except Exception as error:
        description = f"{type(error).__name__}:{error}"
        envelope = DiscoveryAuditEnvelope(
            AuditState.DESCRIPTION_ERROR,
            decision.receipt_hash,
            trace.input_artifact_hashes,
            None,
            type(error).__name__,
            sha256(description.encode("utf-8", errors="replace")).hexdigest(),
            False,
            RAW_RF_PERSISTENCE,
        )
    else:
        envelope = DiscoveryAuditEnvelope(
            AuditState.COMPLETE,
            decision.receipt_hash,
            trace.input_artifact_hashes,
            audit,
            None,
            None,
            False,
            RAW_RF_PERSISTENCE,
        )
    return decision, envelope


@dataclass(frozen=True, slots=True)
class F2535RunResult:
    physical_result: f2532.F2532RunResult
    discovery_audit: DiscoveryAuditEnvelope | None
    live_execution_authorised: bool
    physical_decision_affected_by_description: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.discovery_audit is not None:
            if self.physical_result.discovery is None:
                raise ValueError("audit exists without a discovery decision")
            if self.discovery_audit.decision_receipt_hash != self.physical_result.discovery.receipt_hash:
                raise ValueError("decision and audit are not siblings")
        if self.live_execution_authorised or self.physical_decision_affected_by_description:
            raise ValueError("offline audit cannot grant authority or alter physics")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2535Assessment:
    exit: F2535Exit
    reviewed_f2534_commit: str
    f2534_source_hash_matches: bool
    f2532_source_hash_matches: bool
    frozen_outcome_still_attributable: bool
    sibling_receipt_boundary: bool
    audit_failure_decision_independent: bool
    thresholds_unchanged: bool
    connector_surface_present: bool
    live_execution_authorised: bool
    blockers: tuple[str, ...]


def assess() -> F2535Assessment:
    f2534_match = current_f2534_source_sha256() == REVIEWED_F2534_SOURCE_SHA256
    f2532_match = current_f2532_source_sha256() == REVIEWED_F2532_SOURCE_SHA256
    frozen_attributable = False
    try:
        frozen_attributable = (
            f2534.assess_frozen().outcome == "NO_FALSIFIABLE_INTERVENTION"
        )
    except (OSError, ValueError, TypeError, KeyError):
        pass
    blockers = tuple(
        message
        for condition, message in (
            (f2534_match, "reviewed F2.5.34 source changed"),
            (f2532_match, "reviewed F2.5.32 source changed"),
            (frozen_attributable, "frozen F2.5.33 outcome no longer attributes"),
        )
        if not condition
    )
    return F2535Assessment(
        F2535Exit.SCALAR_AUDIT_INTEGRATED_OFFLINE if not blockers else F2535Exit.SOURCE_SEAL_MISMATCH,
        REVIEWED_F2534_COMMIT,
        f2534_match,
        f2532_match,
        frozen_attributable,
        True,
        True,
        True,
        False,
        False,
        blockers,
    )


def _run_audited_open_handle_rf_injected(
    *,
    reference_socket: object,
    perturbed_socket: object,
    _audit_builder: AuditBuilder = _build_scalar_audit,
) -> F2535RunResult:
    """Private full vertical using sibling discovery receipts; offline only."""

    plan = f2532.build_plan()
    phases: list[f2531.PhaseReceipt] = []
    commands: list[f2531.InternalCommandReceipt] = []
    boundaries: list[f2527.BoundaryWitnessReceipt] = []
    continuity: tuple[f2531.SessionContinuityReceipt, ...] = ()
    temporal: f2527.RelativeTimingAdmissionReceipt | None = None
    discovery: f2531.DiscoveryReceipt | None = None
    discovery_audit: DiscoveryAuditEnvelope | None = None
    physical: f2532._PhysicalEvaluation | None = None
    handles: list[f2531._Handle] = []
    outcome = f2532.Outcome.QUALIFICATION_ERROR

    with ThreadPoolExecutor(max_workers=2) as pool:
        reference_future = pool.submit(
            f2531._open_handle, reference_socket, "reference"
        )
        perturbed_future = pool.submit(
            f2531._open_handle, perturbed_socket, "perturbed"
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
                f2531._phase(
                    f2531.PHASE_ORDER[0],
                    f2531.PhaseState.UNSATISFIED,
                    "an injected branch contains an explicit server rejection",
                )
            )
            f2531._complete_not_evaluated(phases, "dual handles were not admitted")
            outcome = f2532.Outcome.CAPABILITY_REJECTED
        elif states != {"HANDLE_OPEN"}:
            phases.append(
                f2531._phase(
                    f2531.PHASE_ORDER[0],
                    f2531.PhaseState.QUALIFICATION_ERROR,
                    "an injected branch could not materialize an owned handle",
                )
            )
            f2531._complete_not_evaluated(
                phases, "handle qualification error blocked phases"
            )
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
                phases.append(
                    f2531._phase(
                        f2531.PHASE_ORDER[0],
                        f2531.PhaseState.UNSATISFIED,
                        "open handles do not preserve distinct same-rate channels",
                    )
                )
                f2531._complete_not_evaluated(
                    phases, "channel topology was not admitted"
                )
                outcome = f2532.Outcome.TOPOLOGY_NOT_ADMITTED
            else:
                phases.append(
                    f2531._phase(
                        f2531.PHASE_ORDER[0],
                        f2531.PhaseState.SATISFIED,
                        "two distinct SND handles are owned by one outer scope",
                        tuple(item.receipt_hash for item in open_receipts),
                    )
                )
                reference_a1, perturbed_a1 = f2531._collect_pair_count(
                    reference, perturbed, f2531.PHASE_FRAME_COUNT
                )
                temporal = f2527.evaluate_relative_timing(
                    tuple(item.receipt for item in reference_a1),
                    tuple(item.receipt for item in perturbed_a1),
                )
                if temporal.state != (
                    f2527.AdmissionState.ADMISSIBLE_FOR_RELATIVE_TIME_EXPERIMENT.value
                ):
                    phases.append(
                        f2531._phase(
                            f2531.PHASE_ORDER[1],
                            f2531.PhaseState.UNSATISFIED,
                            "initial A1 frames failed relative-time admission",
                        )
                    )
                    f2531._complete_not_evaluated(
                        phases, "temporal admission blocked discovery"
                    )
                    outcome = f2532.Outcome.TEMPORAL_NOT_ADMITTED
                else:
                    phases.append(
                        f2531._phase(
                            f2531.PHASE_ORDER[1],
                            f2531.PhaseState.SATISFIED,
                            "initial A1 frames satisfy relative-time admission",
                        )
                    )
                    discovery, discovery_audit = discover_with_scalar_audit(
                        reference_a1,
                        perturbed_a1,
                        _audit_builder=_audit_builder,
                    )
                    if discovery.state != "ONE_FEATURE_ADMITTED":
                        phases.append(
                            f2531._phase(
                                f2531.PHASE_ORDER[2],
                                f2531.PhaseState.UNSATISFIED,
                                "unchanged thresholds admitted no common A1 feature",
                                discovery.input_artifact_hashes,
                            )
                        )
                        f2531._complete_not_evaluated(
                            phases, "no feature admitted intervention"
                        )
                        outcome = f2532.Outcome.NO_FALSIFIABLE_INTERVENTION
                    else:
                        phases.append(
                            f2531._phase(
                                f2531.PHASE_ORDER[2],
                                f2531.PhaseState.SATISFIED,
                                "one common A1 feature was selected before either command",
                                (discovery.receipt_hash,),
                            )
                        )
                        executor = f2531._InternalRetuneExecutor(
                            reference, perturbed, f2531.build_plan()
                        )
                        command_b = executor.transition(
                            "A1_TO_B",
                            f2531.build_plan().center_a_hz
                            + f2531.TECHNICAL_DELTA_HZ,
                            perturbed_a1[-1].receipt,
                            reference_a1[-1].receipt,
                        )
                        commands.append(command_b)
                        reference_b, perturbed_b = (
                            f2531._collect_pair_postsettling(
                                reference,
                                perturbed,
                                command_b.settling_complete_monotonic_ns
                                + perturbed_a1[-1].receipt.sample_duration_ns,
                                f2531.PHASE_FRAME_COUNT,
                            )
                        )
                        boundary_b = f2531._boundary(
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
                            f2531._phase(
                                f2531.PHASE_ORDER[3],
                                (
                                    f2531.PhaseState.SATISFIED
                                    if b_valid
                                    else f2531.PhaseState.UNSATISFIED
                                ),
                                boundary_b.statement,
                                (boundary_b.anchor_receipt_hash,),
                            )
                        )
                        if not b_valid:
                            f2531._complete_not_evaluated(
                                phases, "A1_TO_B boundary was invalid"
                            )
                            outcome = f2532.Outcome.INTERVENTION_INVALID
                        else:
                            command_a2 = executor.transition(
                                "B_TO_A2",
                                f2531.build_plan().center_a_hz,
                                perturbed_b[-1].receipt,
                                reference_b[-1].receipt,
                            )
                            commands.append(command_a2)
                            reference_a2, perturbed_a2 = (
                                f2531._collect_pair_postsettling(
                                    reference,
                                    perturbed,
                                    command_a2.settling_complete_monotonic_ns
                                    + perturbed_b[-1].receipt.sample_duration_ns,
                                    f2531.PHASE_FRAME_COUNT,
                                )
                            )
                            boundary_a2 = f2531._boundary(
                                command_a2,
                                perturbed_before=perturbed_b[-1].receipt,
                                perturbed_after=perturbed_a2[0].receipt,
                                reference_before=reference_b[-1].receipt,
                                reference_after=reference_a2[0].receipt,
                            )
                            boundaries.append(boundary_a2)
                            continuity = (
                                f2531._continuity(reference),
                                f2531._continuity(perturbed),
                            )
                            a2_valid = boundary_a2.state == (
                                f2527.BoundaryState.BOUNDARY_WITNESSED.value
                            )
                            continuous = all(
                                item.state == "SATISFIED" for item in continuity
                            )
                            phases.append(
                                f2531._phase(
                                    f2531.PHASE_ORDER[4],
                                    (
                                        f2531.PhaseState.SATISFIED
                                        if a2_valid and continuous
                                        else f2531.PhaseState.UNSATISFIED
                                    ),
                                    (
                                        "B_TO_A2 and full-session continuity are valid"
                                        if a2_valid and continuous
                                        else "return boundary or session continuity is invalid"
                                    ),
                                    (boundary_a2.anchor_receipt_hash,),
                                )
                            )
                            if not (a2_valid and continuous):
                                f2531._complete_not_evaluated(
                                    phases, "command/time topology was invalid"
                                )
                                outcome = f2532.Outcome.INTERVENTION_INVALID
                            else:
                                physical = f2532._evaluate_rf_response(
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
                                    phases.append(
                                        f2531._phase(
                                            f2531.PHASE_ORDER[5],
                                            f2531.PhaseState.NOT_EVALUATED,
                                            "target-independent intervention admission blocked plan freeze",
                                        )
                                    )
                                    phases.append(
                                        f2531._phase(
                                            f2531.PHASE_ORDER[6],
                                            f2531.PhaseState.NOT_EVALUATED,
                                            "target feature was not revealed",
                                        )
                                    )
                                else:
                                    phases.append(
                                        f2531._phase(
                                            f2531.PHASE_ORDER[5],
                                            f2531.PhaseState.SATISFIED,
                                            "target predictions and controls were immutably hashed before target reveal",
                                            (physical.frozen_target_plan.plan_hash,),
                                        )
                                    )
                                    phases.append(
                                        f2531._phase(
                                            f2531.PHASE_ORDER[6],
                                            f2531.PhaseState.SATISFIED,
                                            physical.statement,
                                            tuple(
                                                item.receipt.artifact_hash_before_analysis
                                                for item in reference_a2 + perturbed_a2
                                            ),
                                        )
                                    )
    except Exception as error:
        if len(phases) < len(f2531.PHASE_ORDER):
            phases.append(
                f2531._phase(
                    f2531.PHASE_ORDER[len(phases)],
                    f2531.PhaseState.QUALIFICATION_ERROR,
                    f"offline RF transform error: {type(error).__name__}",
                )
            )
        f2531._complete_not_evaluated(
            phases, "qualification error blocked later phases"
        )
        outcome = f2532.Outcome.QUALIFICATION_ERROR
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
    f2532._complete_clauses(
        clauses, "an upstream lifecycle clause blocked RF evaluation"
    )
    physical_outcomes = {
        f2532.Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED,
        f2532.Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED,
        f2532.Outcome.AMBIGUOUS,
    }
    physical_result = f2532.F2532RunResult(
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
            "the scalar discovery audit was emitted beside, not inside, the selector decision",
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
    return F2535RunResult(
        physical_result,
        discovery_audit,
        False,
        False,
        RAW_RF_PERSISTENCE,
    )
