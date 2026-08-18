"""Gate F2.5.24: offline post-freeze confirmation evaluator.

The evaluator accepts one immutable F2.5.23 plan and one injected A1/B/A2
artifact set. It first validates event time, channel/tuning ledger, continuity
and the target-excluded distributed witness. Target hypotheses are evaluated
only after those clauses admit the confirmation. No connector or live runner
exists in this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
import json
import math
from typing import Callable

import numpy as np

from . import kiwi_gate_f2 as f2
from . import kiwi_gate_f2_4 as f24
from . import kiwi_gate_f2_5_22 as f2522
from . import kiwi_gate_f2_5_23 as f2523
from .models import strict_json_value


TRANSFORM_VERSION = "gate-f2.5.24-offline-confirmation-evaluator-v1"
REVIEWED_F2523_COMMIT = "7e8cfe39bcb9afec295ea520018d47260e67416b"
RAW_RF_PERSISTENCE = "ZERO"
CLAUSE_ORDER = (
    "confirmation_event_after_freeze",
    "six_distinct_artifacts",
    "channel_and_tuning_ledger_valid",
    "streams_event_time_valid_continuous_clean",
    "distributed_witness_requalified_postfreeze",
    "witness_orientation_matches_plan",
    "target_detectable_on_both_A1_branches",
    "reference_target_fixed_through_A1_B_A2",
    "target_matches_upstream_prediction_B",
    "target_matches_channel_fixed_prediction_B",
    "negative_controls_absent",
    "target_returns_A2",
)


class F2524Exit(str, Enum):
    CONFIRMATION_EVALUATOR_MATERIALIZED_OFFLINE = (
        "CONFIRMATION_EVALUATOR_MATERIALIZED_OFFLINE"
    )


class Outcome(str, Enum):
    UPSTREAM_OF_CHANNEL_DDC_SUPPORTED = "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    DOWNSTREAM_CHANNEL_FIXED_SUPPORTED = "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    INTERVENTION_INVALID = "INTERVENTION_INVALID"
    NOT_DETECTABLE = "NOT_DETECTABLE"


class ClauseState(str, Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(frozen=True, slots=True)
class F2524Envelope:
    reviewed_f2523_commit: str
    plan_transform_version: str
    evaluator_transform_version: str
    clause_order: tuple[str, ...]
    allowed_outcomes: tuple[str, ...]
    witness_precedes_target: bool
    target_excluded_from_witness: bool
    confirmation_windows: int
    postfreeze_retry_budget: int
    capture_artifacts_required_injected: bool
    live_execution_authorised: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if self.reviewed_f2523_commit != REVIEWED_F2523_COMMIT:
            raise ValueError("Gate F2.5.23 lineage changed")
        if self.plan_transform_version != f2523.TRANSFORM_VERSION:
            raise ValueError("one-target plan transform changed")
        if self.evaluator_transform_version != TRANSFORM_VERSION:
            raise ValueError("confirmation transform changed")
        if self.clause_order != CLAUSE_ORDER:
            raise ValueError("confirmation clause order changed")
        if self.allowed_outcomes != f2523.ALLOWED_FUTURE_OUTCOMES:
            raise ValueError("confirmation outcome set changed")
        if not self.witness_precedes_target or not self.target_excluded_from_witness:
            raise ValueError("target-independent intervention admission is mandatory")
        if self.confirmation_windows != 1 or self.postfreeze_retry_budget != 0:
            raise ValueError("one confirmation and zero retry are mandatory")
        if not self.capture_artifacts_required_injected or self.live_execution_authorised:
            raise ValueError("offline evaluator cannot own or authorize capture")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")

    @property
    def envelope_hash(self) -> str:
        return f2._hash(asdict(self))


@dataclass(frozen=True, slots=True)
class ClauseReceipt:
    clause: str
    state: str
    statement: str
    artifact_hashes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.clause not in CLAUSE_ORDER:
            raise ValueError("unknown confirmation clause")
        if self.state not in {item.value for item in ClauseState}:
            raise ValueError("unknown clause state")
        if any(len(item) != 64 for item in self.artifact_hashes):
            raise ValueError("clause artifact hashes must be SHA-256 strings")


@dataclass(frozen=True, slots=True)
class TargetMatchReceipt:
    label: str
    matched: bool
    expected_baseband_hz: float
    observed_baseband_hz: f2522.NumericObservation
    contrast_db: f2522.NumericObservation
    fingerprint_correlation: f2522.NumericObservation
    reason: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.expected_baseband_hz):
            raise ValueError("target expectation must be finite")
        if self.matched and (
            self.observed_baseband_hz.state != "FINITE"
            or self.contrast_db.state != "FINITE"
            or self.fingerprint_correlation.state != "FINITE"
        ):
            raise ValueError("matched target requires finite observations")


@dataclass(frozen=True, slots=True)
class InterventionLedgerReceipt:
    reference_command_count: int
    perturbed_command_count: int
    expected_commands_hash: str
    observed_commands_hash: str
    command_sequence_exact: bool
    centers_exact: bool
    channel_ids_exact: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        if any(len(item) != 64 for item in (self.expected_commands_hash, self.observed_commands_hash)):
            raise ValueError("command ledger hashes must be SHA-256 strings")
        if self.reference_command_count < 0 or self.perturbed_command_count < 0:
            raise ValueError("command counts cannot be negative")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2524Result:
    envelope_hash: str
    plan_hash: str
    outcome: str
    evaluated_at: datetime
    segment_receipts: tuple[f24.F24SegmentReceipt, ...]
    intervention_ledger: InterventionLedgerReceipt
    distributed_witness: f2522.DistributedWitnessReceipt | None
    target_matches: tuple[TargetMatchReceipt, ...]
    clause_receipts: tuple[ClauseReceipt, ...]
    authorised_claims: tuple[str, ...]
    unauthorised_claims: tuple[str, ...]
    physical_decision_affected_by_description: bool
    raw_rf_persistence: str

    def __post_init__(self) -> None:
        f2._utc(self.evaluated_at)
        if self.outcome not in {item.value for item in Outcome}:
            raise ValueError("unknown confirmation outcome")
        if tuple(item.clause for item in self.clause_receipts) != CLAUSE_ORDER:
            raise ValueError("confirmation clauses must be complete and ordered")
        if self.physical_decision_affected_by_description:
            raise ValueError("descriptive receipt cannot modify the physical decision")
        if self.raw_rf_persistence != RAW_RF_PERSISTENCE:
            raise ValueError("RF persistence is forbidden")


@dataclass(frozen=True, slots=True)
class F2524Assessment:
    exit: F2524Exit
    gate23_commit_bound: bool
    all_outcomes_implemented: bool
    witness_precedes_target: bool
    invalid_intervention_blocks_target: bool
    not_detectable_distinct_from_ambiguous: bool
    controls_predeclared: bool
    injected_artifacts_only: bool
    post_commit_seal_required: bool
    live_execution_authorised: bool
    raw_rf_persistence: str


ProfileProvider = Callable[[object, f2.MotherPlan], f2._SpectralProfile]


def build_envelope() -> F2524Envelope:
    return F2524Envelope(
        REVIEWED_F2523_COMMIT,
        f2523.TRANSFORM_VERSION,
        TRANSFORM_VERSION,
        CLAUSE_ORDER,
        f2523.ALLOWED_FUTURE_OUTCOMES,
        True,
        True,
        1,
        0,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )


def _clause(
    name: str,
    value: bool | None,
    statement: str,
    hashes: tuple[str, ...],
) -> ClauseReceipt:
    state = (
        ClauseState.NOT_EVALUATED
        if value is None
        else ClauseState.SATISFIED if value else ClauseState.UNSATISFIED
    )
    return ClauseReceipt(name, state.value, statement, hashes)


def _ordered_artifacts(
    artifacts: f24._DualArtifacts,
) -> tuple[f24._MemoryArtifact, ...]:
    return tuple(artifacts.reference[name] for name in ("A1", "B", "A2")) + tuple(
        artifacts.perturbed[name] for name in ("A1", "B", "A2")
    )


def _ledger_receipt(
    plan: f2523.F2523Plan,
    artifacts: f24._DualArtifacts,
) -> InterventionLedgerReceipt:
    expected_commands = (
        f2._tune_command(plan.center_a_hz + plan.delta_hz),
        f2._tune_command(plan.center_a_hz),
    )
    observed_commands = tuple(command for command, _when in artifacts.perturbed_commands)
    reference_commands = tuple(command for command, _when in artifacts.reference_commands)
    reference = artifacts.reference
    perturbed = artifacts.perturbed
    centers_exact = all(
        math.isclose(
            reference[name].declared_tuning_hz,
            plan.center_a_hz,
            rel_tol=0.0,
            abs_tol=1e-6,
        )
        and math.isclose(
            perturbed[name].declared_tuning_hz,
            plan.center_a_hz + (plan.delta_hz if name == "B" else 0.0),
            rel_tol=0.0,
            abs_tol=1e-6,
        )
        for name in ("A1", "B", "A2")
    )
    channel_ids_exact = all(
        reference[name].channel_id == plan.reference_channel_id
        and perturbed[name].channel_id == plan.perturbed_channel_id
        for name in ("A1", "B", "A2")
    )
    command_sequence_exact = not reference_commands and observed_commands == expected_commands
    return InterventionLedgerReceipt(
        len(reference_commands),
        len(observed_commands),
        f2._hash(expected_commands),
        f2._hash(observed_commands),
        command_sequence_exact,
        centers_exact,
        channel_ids_exact,
        RAW_RF_PERSISTENCE,
    )


def _stream_integrity(
    artifacts: f24._DualArtifacts,
    mother: f2.MotherPlan,
) -> bool:
    reference_rate = artifacts.reference["A1"].capture.sample_rate_hz
    perturbed_rate = artifacts.perturbed["A1"].capture.sample_rate_hz
    ref_event, ref_continuous, ref_clean = f24._integrity(
        artifacts.reference_all_blocks,
        reference_rate,
        mother,
    )
    pert_event, pert_continuous, pert_clean = f24._integrity(
        artifacts.perturbed_all_blocks,
        perturbed_rate,
        mother,
    )
    return all(
        (
            ref_event,
            ref_continuous,
            ref_clean,
            pert_event,
            pert_continuous,
            pert_clean,
            math.isclose(reference_rate, perturbed_rate, rel_tol=0.0, abs_tol=1e-6),
        )
    )


def _frozen_mother(plan: f2523.F2523Plan) -> f2.MotherPlan:
    """Recover the reviewed transform constants and reject threshold drift."""

    mother = f2.MotherPlan()
    if plan.thresholds != f2523._thresholds(mother):
        raise ValueError("confirmation thresholds differ from the reviewed frozen plan")
    return mother


def _target_match(
    profile: f2._SpectralProfile,
    target: f2523.TargetFingerprint,
    expected_hz: float,
    tolerance_hz: float,
    mother: f2.MotherPlan,
    label: str,
) -> TargetMatchReceipt:
    frequencies = profile.frequencies_hz
    indices = np.flatnonzero(np.abs(frequencies - expected_hz) <= tolerance_hz)
    best: tuple[float, float, int] | None = None
    for raw_index in indices:
        index = int(raw_index)
        patch = f2._normalized_neighbourhood(
            profile.residual_db,
            index,
            radius=(len(target.local_neighbourhood) - 1) // 2,
        )
        if patch is None or len(patch) != len(target.local_neighbourhood):
            continue
        correlation = f2._correlation(target.local_neighbourhood, patch)
        contrast = float(profile.residual_db[index])
        candidate = (correlation, contrast, index)
        if best is None or candidate > best:
            best = candidate
    if best is None:
        return TargetMatchReceipt(
            label,
            False,
            expected_hz,
            f2522._not_evaluated("Hz", "no complete patch in prediction interval"),
            f2522._not_evaluated("dB", "no complete patch in prediction interval"),
            f2522._not_evaluated("ratio", "no complete patch in prediction interval"),
            "no complete target patch in the frozen interval",
        )
    correlation, contrast, index = best
    matched = (
        correlation >= mother.minimum_fingerprint_correlation
        and contrast >= mother.minimum_contrast_db
    )
    return TargetMatchReceipt(
        label,
        matched,
        expected_hz,
        f2522._finite(float(frequencies[index]), "Hz", "best frozen-interval candidate"),
        f2522._finite(contrast, "dB", "profile residual at candidate"),
        f2522._finite(correlation, "ratio", "frozen target fingerprint correlation"),
        "frozen target fingerprint and contrast satisfied" if matched else "target fingerprint or contrast below frozen threshold",
    )


def _not_evaluated_matches(
    plan: f2523.F2523Plan,
) -> tuple[TargetMatchReceipt, ...]:
    labels = (
        ("reference_A1", plan.target.baseband_position_a_hz),
        ("perturbed_A1", plan.target.baseband_position_a_hz),
        ("reference_B", plan.target.baseband_position_a_hz),
        ("perturbed_B_upstream", plan.target.baseband_position_a_hz + plan.observed_translation_hz),
        ("perturbed_B_channel_fixed", plan.target.baseband_position_a_hz),
        ("wrong_sign_B", dict(plan.controls)["WRONG_SIGN_B"]),
        ("half_magnitude_B", dict(plan.controls)["HALF_MAGNITUDE_B"]),
        ("off_feature_B", dict(plan.controls)["OFF_FEATURE_B"]),
        ("reference_A2", plan.target.baseband_position_a_hz),
        ("perturbed_A2", plan.target.baseband_position_a_hz),
    )
    return tuple(
        TargetMatchReceipt(
            label,
            False,
            expected,
            f2522._not_evaluated("Hz", "upstream confirmation clause did not admit target evaluation"),
            f2522._not_evaluated("dB", "upstream confirmation clause did not admit target evaluation"),
            f2522._not_evaluated("ratio", "upstream confirmation clause did not admit target evaluation"),
            "NOT_EVALUATED",
        )
        for label, expected in labels
    )


def _terminal_without_target(
    *,
    envelope: F2524Envelope,
    plan: f2523.F2523Plan,
    outcome: Outcome,
    evaluated_at: datetime,
    segments: tuple[f24.F24SegmentReceipt, ...],
    ledger: InterventionLedgerReceipt,
    witness: f2522.DistributedWitnessReceipt | None,
    clauses: list[ClauseReceipt],
    statement: str,
) -> F2524Result:
    known = {item.clause for item in clauses}
    hashes = tuple(item.artifact_hash for item in segments)
    for name in CLAUSE_ORDER:
        if name not in known:
            clauses.append(_clause(name, None, "an upstream confirmation clause did not admit target evaluation", hashes))
    return F2524Result(
        envelope.envelope_hash,
        plan.plan_hash,
        outcome.value,
        evaluated_at,
        segments,
        ledger,
        witness,
        _not_evaluated_matches(plan),
        tuple(clauses),
        (statement,),
        (
            "either target hypothesis is supported",
            "external RF proven",
            "transmitter identity",
            "a second confirmation is permitted",
        ),
        False,
        RAW_RF_PERSISTENCE,
    )


def evaluate_confirmation_injected(
    plan: f2523.F2523Plan,
    artifacts: f24._DualArtifacts,
    *,
    profile_provider: ProfileProvider = f2._capture_profile,
    evaluated_at: datetime,
) -> F2524Result:
    """Evaluate exactly one injected confirmation artifact set, offline."""

    mother = _frozen_mother(plan)
    envelope = build_envelope()
    ordered = _ordered_artifacts(artifacts)
    segments = tuple(item.receipt() for item in ordered)
    hashes = tuple(item.artifact_hash for item in ordered)
    ledger = _ledger_receipt(plan, artifacts)
    event_after_freeze = bool(
        len(ordered) == 6
        and all(
            item.capture.event_start >= plan.confirmation_event_not_before
            for item in ordered
        )
    )
    distinct_artifacts = len(hashes) == 6 and len(set(hashes)) == 6
    ledger_valid = all(
        (
            ledger.command_sequence_exact,
            ledger.centers_exact,
            ledger.channel_ids_exact,
        )
    )
    stream_valid = _stream_integrity(artifacts, mother)
    clauses = [
        _clause("confirmation_event_after_freeze", event_after_freeze, "all six event-time intervals begin after plan freeze", hashes),
        _clause("six_distinct_artifacts", distinct_artifacts, "six pre-analysis hashes bind reference/perturbed A1/B/A2", hashes),
        _clause("channel_and_tuning_ledger_valid", ledger_valid, "reference has no tune command; perturbed B/A2 commands and centers match the plan", hashes),
        _clause("streams_event_time_valid_continuous_clean", stream_valid, "both event-time streams are continuous, aligned-rate and overflow-free", hashes),
    ]
    if not all((event_after_freeze, distinct_artifacts, ledger_valid, stream_valid)):
        return _terminal_without_target(
            envelope=envelope,
            plan=plan,
            outcome=Outcome.INTERVENTION_INVALID,
            evaluated_at=evaluated_at,
            segments=segments,
            ledger=ledger,
            witness=None,
            clauses=clauses,
            statement="the post-freeze intervention or measurement topology was invalid",
        )

    profiles = tuple(profile_provider(item.capture, mother) for item in ordered)
    frequencies, residuals, bin_hz = f2523._common_grid(profiles)
    target_index = int(
        np.argmin(np.abs(frequencies - plan.target.baseband_position_a_hz))
    )
    delta_bins = int(round(plan.delta_hz / bin_hz))
    target_radius = int(
        math.ceil(max(plan.target.bandwidth_hz, plan.target.uncertainty_hz) / bin_hz)
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
    witness_satisfied = witness.state == f2522.WitnessState.QUALIFIED_AS_FUTURE_WITNESS.value
    orientation_matches = bool(
        witness_satisfied
        and witness.learned_orientation == plan.orientation
        and math.isclose(
            witness.learned_orientation * delta_bins * bin_hz,
            plan.observed_translation_hz,
            rel_tol=0.0,
            abs_tol=plan.target.uncertainty_hz,
        )
    )
    clauses.extend(
        (
            _clause("distributed_witness_requalified_postfreeze", witness_satisfied, "target-excluded fingerprint must translate uniquely and return in A2", hashes),
            _clause("witness_orientation_matches_plan", orientation_matches if witness_satisfied else None, "post-freeze translation must preserve the pre-freeze orientation", hashes),
        )
    )
    if witness.state == f2522.WitnessState.NOT_DETECTABLE.value:
        return _terminal_without_target(
            envelope=envelope,
            plan=plan,
            outcome=Outcome.NOT_DETECTABLE,
            evaluated_at=evaluated_at,
            segments=segments,
            ledger=ledger,
            witness=witness,
            clauses=clauses,
            statement="the intervention witness was not detectable in the confirmation window",
        )
    if not witness_satisfied or not orientation_matches:
        return _terminal_without_target(
            envelope=envelope,
            plan=plan,
            outcome=Outcome.INTERVENTION_INVALID,
            evaluated_at=evaluated_at,
            segments=segments,
            ledger=ledger,
            witness=witness,
            clauses=clauses,
            statement="the post-freeze intervention was not uniquely witnessed",
        )

    tolerance = plan.target.uncertainty_hz
    expected = {
        "reference_A1": plan.target.baseband_position_a_hz,
        "perturbed_A1": plan.target.baseband_position_a_hz,
        "reference_B": plan.target.baseband_position_a_hz,
        "perturbed_B_upstream": plan.target.baseband_position_a_hz + plan.observed_translation_hz,
        "perturbed_B_channel_fixed": plan.target.baseband_position_a_hz,
        "wrong_sign_B": dict(plan.controls)["WRONG_SIGN_B"],
        "half_magnitude_B": dict(plan.controls)["HALF_MAGNITUDE_B"],
        "off_feature_B": dict(plan.controls)["OFF_FEATURE_B"],
        "reference_A2": plan.target.baseband_position_a_hz,
        "perturbed_A2": plan.target.baseband_position_a_hz,
    }
    profile_by_label = {
        "reference_A1": profiles[0],
        "perturbed_A1": profiles[3],
        "reference_B": profiles[1],
        "perturbed_B_upstream": profiles[4],
        "perturbed_B_channel_fixed": profiles[4],
        "wrong_sign_B": profiles[4],
        "half_magnitude_B": profiles[4],
        "off_feature_B": profiles[4],
        "reference_A2": profiles[2],
        "perturbed_A2": profiles[5],
    }
    matches = tuple(
        _target_match(
            profile_by_label[label],
            plan.target,
            position,
            tolerance,
            mother,
            label,
        )
        for label, position in expected.items()
    )
    matched = {item.label: item.matched for item in matches}
    a1_detectable = matched["reference_A1"] and matched["perturbed_A1"]
    reference_fixed = (
        matched["reference_A1"]
        and matched["reference_B"]
        and matched["reference_A2"]
    )
    target_return = matched["perturbed_A2"] and matched["reference_A2"]
    controls_absent = not any(
        matched[name]
        for name in ("wrong_sign_B", "half_magnitude_B", "off_feature_B")
    )
    upstream = matched["perturbed_B_upstream"]
    channel_fixed = matched["perturbed_B_channel_fixed"]
    clauses.extend(
        (
            _clause("target_detectable_on_both_A1_branches", a1_detectable, "target must be detectable on both branches before B", hashes),
            _clause("reference_target_fixed_through_A1_B_A2", reference_fixed, "fixed reference must preserve target detectability", hashes),
            _clause("target_matches_upstream_prediction_B", upstream if a1_detectable and reference_fixed else None, "perturbed B target tested only in frozen upstream interval", hashes),
            _clause("target_matches_channel_fixed_prediction_B", channel_fixed if a1_detectable and reference_fixed else None, "perturbed B target tested only in frozen channel-fixed interval", hashes),
            _clause("negative_controls_absent", controls_absent if a1_detectable and reference_fixed else None, "wrong-sign, half-magnitude and off-feature intervals must remain empty", hashes),
            _clause("target_returns_A2", target_return if a1_detectable and reference_fixed else None, "target must return on perturbed and remain on reference A2", hashes),
        )
    )
    if not (a1_detectable and reference_fixed and target_return):
        outcome = Outcome.NOT_DETECTABLE
        authorised = ("the target detectability envelope was not preserved through confirmation",)
    elif upstream and not channel_fixed and controls_absent:
        outcome = Outcome.UPSTREAM_OF_CHANNEL_DDC_SUPPORTED
        authorised = ("the target followed the sample-witnessed channel translation while the reference remained fixed",)
    elif channel_fixed and not upstream and controls_absent:
        outcome = Outcome.DOWNSTREAM_CHANNEL_FIXED_SUPPORTED
        authorised = ("the target remained channel-fixed while the independent distributed witness translated",)
    else:
        outcome = Outcome.AMBIGUOUS
        authorised = ("the valid confirmation did not uniquely select either frozen target prediction",)
    return F2524Result(
        envelope.envelope_hash,
        plan.plan_hash,
        outcome.value,
        evaluated_at,
        segments,
        ledger,
        witness,
        matches,
        tuple(clauses),
        authorised,
        (
            "same emitter confirmed",
            "external RF proven",
            "antenna/front-end/ADC artifacts excluded",
            "transmitter identity",
            "a second confirmation is permitted",
        ),
        False,
        RAW_RF_PERSISTENCE,
    )


def assess_gate_f2_5_24() -> F2524Assessment:
    envelope = build_envelope()
    return F2524Assessment(
        F2524Exit.CONFIRMATION_EVALUATOR_MATERIALIZED_OFFLINE,
        envelope.reviewed_f2523_commit == REVIEWED_F2523_COMMIT,
        set(envelope.allowed_outcomes) == {item.value for item in Outcome},
        True,
        True,
        True,
        True,
        True,
        True,
        False,
        RAW_RF_PERSISTENCE,
    )


def strict_json(value: object) -> str:
    return json.dumps(
        strict_json_value(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def main() -> None:
    print(strict_json(assess_gate_f2_5_24()))


if __name__ == "__main__":
    main()
