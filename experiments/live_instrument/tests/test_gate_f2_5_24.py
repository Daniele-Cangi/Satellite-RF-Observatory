"""Offline tests for the Gate F2.5.24 post-freeze evaluator."""

from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import inspect
import json

import numpy as np

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_4 as f24
from experiments.live_instrument import kiwi_gate_f2_5_22 as f2522
from experiments.live_instrument import kiwi_gate_f2_5_23 as f2523
from experiments.live_instrument import kiwi_gate_f2_5_24 as f2524
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import strict_json_value


NOW = datetime(2026, 8, 18, 17, 0, tzinfo=timezone.utc)
FREQUENCIES = np.arange(-4_000.0, 4_000.1, 10.0)
TARGET_A_HZ = -1_200.0
DELTA_HZ = 1_000.0


def _profile(residual: np.ndarray) -> f2._SpectralProfile:
    return f2._SpectralProfile(
        FREQUENCIES,
        residual.copy(),
        residual.copy(),
        residual.copy(),
        residual.copy(),
        10.0,
    )


def _shift(values: np.ndarray, lag: int) -> np.ndarray:
    shifted = np.zeros_like(values)
    shifted[lag:] = values[:-lag]
    return shifted


def _peak(position_hz: float, height: float = 12.0) -> np.ndarray:
    return height * np.exp(-0.5 * ((FREQUENCIES - position_hz) / 20.0) ** 2)


def _plan(background: np.ndarray) -> f2523.F2523Plan:
    target_profile = background + _peak(TARGET_A_HZ)
    target_index = int(np.argmin(np.abs(FREQUENCIES - TARGET_A_HZ)))
    neighbourhood = f2._normalized_neighbourhood(target_profile, target_index)
    assert neighbourhood is not None
    target = f2523.TargetFingerprint(
        TARGET_A_HZ,
        40.0,
        neighbourhood,
        (12.0, 12.0, 0.0),
        (11.0, 13.0),
        25.0,
        1.0,
    )
    translation = DELTA_HZ
    tolerance = target.uncertainty_hz
    return f2523.F2523Plan(
        "fixture.invalid:8073",
        "rx:7",
        "rx:8",
        10_000_000.0,
        DELTA_HZ,
        translation,
        1,
        target,
        (
            ("TARGET_UPSTREAM_B", TARGET_A_HZ + translation - tolerance, TARGET_A_HZ + translation + tolerance),
            ("TARGET_CHANNEL_FIXED_B", TARGET_A_HZ - tolerance, TARGET_A_HZ + tolerance),
            ("TARGET_A2_RETURN", TARGET_A_HZ - tolerance, TARGET_A_HZ + tolerance),
            ("REFERENCE_TARGET_FIXED", TARGET_A_HZ - tolerance, TARGET_A_HZ + tolerance),
        ),
        (
            ("WRONG_SIGN_B", TARGET_A_HZ - translation),
            ("HALF_MAGNITUDE_B", TARGET_A_HZ + translation / 2.0),
            ("OFF_FEATURE_B", TARGET_A_HZ + translation * 2.5),
        ),
        (f2._hash("discovery-reference"), f2._hash("discovery-perturbed")),
        tuple(f2._hash(f"qualification-{index}") for index in range(6)),
        f2523._thresholds(f2.MotherPlan()),
        (
            "distributed_witness_requalified_postfreeze",
            "target_detectable_on_both_A1_branches",
            "reference_target_fixed_through_A1_B_A2",
            "exactly_one_of_upstream_or_channel_fixed_matches_B",
            "wrong_sign_half_magnitude_and_off_feature_controls_absent",
            "target_returns_in_A2",
        ),
        f2523.ALLOWED_FUTURE_OUTCOMES,
        NOW,
        NOW,
        1,
        0,
        True,
        "ZERO",
        (f2522.TRANSFORM_VERSION, f2523.TRANSFORM_VERSION),
    )


def _artifact(
    role: str,
    phase: str,
    phase_index: int,
    profile_key: str,
    *,
    event_offset_s: float = 1.0,
) -> f24._MemoryArtifact:
    start = NOW + timedelta(seconds=event_offset_s + phase_index)
    end = start + timedelta(seconds=1.0)
    samples = np.zeros(1_024, dtype=np.complex64)
    sequence = (100 if role == "reference" else 200) + phase_index
    block = kiwi.IQBlock(
        start,
        end,
        samples,
        -70.0,
        0,
        True,
        False,
        sequence,
        end + timedelta(milliseconds=100),
    )
    center = 10_000_000.0 + (
        DELTA_HZ if role == "perturbed" and phase == "B" else 0.0
    )
    capture = kiwi.KiwiCapture(
        kiwi.KiwiEndpoint("fixture", "fixture.invalid", 8073),
        center,
        12_000.0,
        {"profile_key": profile_key},
        (block,),
        block.arrived_at,  # type: ignore[arg-type]
        block.arrived_at,  # type: ignore[arg-type]
    )
    return f24._MemoryArtifact(
        capture,
        f2._hash({"role": role, "phase": phase, "profile": profile_key}),
        int(samples.nbytes),
        "rx:7" if role == "reference" else "rx:8",
        role,
        phase,
        center,
    )


class _Fixture:
    def __init__(
        self,
        mode: str,
        *,
        event_offset_s: float = 1.0,
        command_ledger_valid: bool = True,
    ) -> None:
        rng = np.random.default_rng(2524)
        self.background = rng.normal(0.0, 0.6, len(FREQUENCIES))
        self.plan = _plan(self.background)
        a_target = self.background + _peak(TARGET_A_HZ)
        profiles: dict[str, f2._SpectralProfile] = {}
        for role in ("reference", "perturbed"):
            for phase in ("A1", "B", "A2"):
                profiles[f"{role}:{phase}"] = _profile(a_target)

        translated_background = _shift(self.background, int(DELTA_HZ / 10.0))
        if mode == "upstream":
            perturbed_b = translated_background + _peak(TARGET_A_HZ + DELTA_HZ)
        elif mode == "channel_fixed":
            perturbed_b = translated_background + _peak(TARGET_A_HZ)
        elif mode == "both":
            perturbed_b = (
                translated_background
                + _peak(TARGET_A_HZ)
                + _peak(TARGET_A_HZ + DELTA_HZ)
            )
        elif mode == "control":
            perturbed_b = (
                translated_background
                + _peak(TARGET_A_HZ + DELTA_HZ)
                + _peak(TARGET_A_HZ - DELTA_HZ)
            )
        elif mode == "neither":
            perturbed_b = translated_background
        elif mode == "intervention_unresolved":
            perturbed_b = self.background + _peak(TARGET_A_HZ)
        elif mode == "witness_not_detectable":
            target_only = np.zeros_like(self.background)
            for key in profiles:
                profiles[key] = _profile(target_only)
            perturbed_b = target_only
        elif mode == "target_not_detectable":
            perturbed_b = translated_background + _peak(TARGET_A_HZ + DELTA_HZ)
            profiles["perturbed:A1"] = _profile(self.background)
        else:
            raise ValueError(mode)
        profiles["perturbed:B"] = _profile(perturbed_b)
        self.profiles = profiles

        reference = {
            phase: _artifact("reference", phase, index, f"reference:{phase}", event_offset_s=event_offset_s)
            for index, phase in enumerate(("A1", "B", "A2"))
        }
        perturbed = {
            phase: _artifact("perturbed", phase, index, f"perturbed:{phase}", event_offset_s=event_offset_s)
            for index, phase in enumerate(("A1", "B", "A2"))
        }
        expected_commands = (
            (f2._tune_command(self.plan.center_a_hz + self.plan.delta_hz), NOW + timedelta(seconds=2)),
            (f2._tune_command(self.plan.center_a_hz), NOW + timedelta(seconds=3)),
        )
        if not command_ledger_valid:
            expected_commands = expected_commands[:1]
        self.artifacts = f24._DualArtifacts(
            reference,
            perturbed,
            tuple(reference[phase].capture.blocks[0] for phase in ("A1", "B", "A2")),
            tuple(perturbed[phase].capture.blocks[0] for phase in ("A1", "B", "A2")),
            (),
            expected_commands,
        )
        self.profile_calls = 0

    def provider(self, capture: object, mother: f2.MotherPlan) -> f2._SpectralProfile:
        del mother
        self.profile_calls += 1
        return self.profiles[capture.status["profile_key"]]  # type: ignore[attr-defined]

    def evaluate(self) -> f2524.F2524Result:
        return f2524.evaluate_confirmation_injected(
            self.plan,
            self.artifacts,
            profile_provider=self.provider,
            evaluated_at=NOW + timedelta(seconds=10),
        )


def _states(result: f2524.F2524Result) -> dict[str, str]:
    return {item.clause: item.state for item in result.clause_receipts}


def test_envelope_is_offline_bound_and_has_no_live_surface() -> None:
    envelope = f2524.build_envelope()
    assessment = f2524.assess_gate_f2_5_24()
    source = inspect.getsource(f2524)

    assert envelope.reviewed_f2523_commit == f2524.REVIEWED_F2523_COMMIT
    assert envelope.clause_order == f2524.CLAUSE_ORDER
    assert envelope.allowed_outcomes == f2523.ALLOWED_FUTURE_OUTCOMES
    assert envelope.confirmation_windows == 1
    assert envelope.postfreeze_retry_budget == 0
    assert not envelope.live_execution_authorised
    assert assessment.all_outcomes_implemented
    assert assessment.post_commit_seal_required
    assert "websocket" not in source
    assert "_capture_dual(" not in source
    assert "run_live" not in source


def test_upstream_prediction_is_selected_only_after_witness_and_controls() -> None:
    result = _Fixture("upstream").evaluate()
    states = _states(result)

    assert result.outcome == "UPSTREAM_OF_CHANNEL_DDC_SUPPORTED"
    assert states["target_matches_upstream_prediction_B"] == "SATISFIED"
    assert states["target_matches_channel_fixed_prediction_B"] == "UNSATISFIED"
    assert all(
        state == "SATISFIED"
        for name, state in states.items()
        if name != "target_matches_channel_fixed_prediction_B"
    )
    assert result.distributed_witness is not None
    assert result.distributed_witness.state == "QUALIFIED_AS_FUTURE_WITNESS"
    assert dict((item.label, item.matched) for item in result.target_matches)["perturbed_B_upstream"]
    assert not dict((item.label, item.matched) for item in result.target_matches)["perturbed_B_channel_fixed"]


def test_channel_fixed_prediction_is_the_other_unique_supported_outcome() -> None:
    result = _Fixture("channel_fixed").evaluate()
    states = _states(result)

    assert result.outcome == "DOWNSTREAM_CHANNEL_FIXED_SUPPORTED"
    assert states["target_matches_upstream_prediction_B"] == "UNSATISFIED"
    assert states["target_matches_channel_fixed_prediction_B"] == "SATISFIED"
    assert states["negative_controls_absent"] == "SATISFIED"


def test_nonunique_predictions_or_a_positive_control_are_ambiguous() -> None:
    both = _Fixture("both").evaluate()
    control = _Fixture("control").evaluate()
    neither = _Fixture("neither").evaluate()

    assert {both.outcome, control.outcome, neither.outcome} == {"AMBIGUOUS"}
    assert _states(both)["target_matches_upstream_prediction_B"] == "SATISFIED"
    assert _states(both)["target_matches_channel_fixed_prediction_B"] == "SATISFIED"
    assert _states(control)["negative_controls_absent"] == "UNSATISFIED"
    assert _states(neither)["target_matches_upstream_prediction_B"] == "UNSATISFIED"
    assert _states(neither)["target_matches_channel_fixed_prediction_B"] == "UNSATISFIED"


def test_invalid_intervention_blocks_every_target_clause() -> None:
    fixture = _Fixture("intervention_unresolved")
    result = fixture.evaluate()
    states = _states(result)

    assert result.outcome == "INTERVENTION_INVALID"
    assert states["distributed_witness_requalified_postfreeze"] == "UNSATISFIED"
    assert all(states[name] == "NOT_EVALUATED" for name in f2524.CLAUSE_ORDER[5:])
    assert all(item.reason == "NOT_EVALUATED" for item in result.target_matches)


def test_undetectable_witness_is_not_relabelled_invalid_or_ambiguous() -> None:
    result = _Fixture("witness_not_detectable").evaluate()
    states = _states(result)

    assert result.outcome == "NOT_DETECTABLE"
    assert states["distributed_witness_requalified_postfreeze"] == "UNSATISFIED"
    assert states["target_detectable_on_both_A1_branches"] == "NOT_EVALUATED"


def test_target_detectability_envelope_can_fail_after_valid_witness() -> None:
    result = _Fixture("target_not_detectable").evaluate()
    states = _states(result)

    assert result.outcome == "NOT_DETECTABLE"
    assert states["distributed_witness_requalified_postfreeze"] == "SATISFIED"
    assert states["witness_orientation_matches_plan"] == "SATISFIED"
    assert states["target_detectable_on_both_A1_branches"] == "UNSATISFIED"
    assert states["target_matches_upstream_prediction_B"] == "NOT_EVALUATED"


def test_pre_target_event_or_bad_command_ledger_stops_before_profiles() -> None:
    stale = _Fixture("upstream", event_offset_s=-1.0)
    stale_result = stale.evaluate()
    bad_ledger = _Fixture("upstream", command_ledger_valid=False)
    bad_result = bad_ledger.evaluate()

    assert stale_result.outcome == "INTERVENTION_INVALID"
    assert bad_result.outcome == "INTERVENTION_INVALID"
    assert stale.profile_calls == 0
    assert bad_ledger.profile_calls == 0
    assert _states(stale_result)["confirmation_event_after_freeze"] == "UNSATISFIED"
    assert _states(bad_result)["channel_and_tuning_ledger_valid"] == "UNSATISFIED"


def test_every_allowed_outcome_is_reachable_without_changing_the_plan() -> None:
    outcomes = {
        _Fixture("upstream").evaluate().outcome,
        _Fixture("channel_fixed").evaluate().outcome,
        _Fixture("both").evaluate().outcome,
        _Fixture("intervention_unresolved").evaluate().outcome,
        _Fixture("witness_not_detectable").evaluate().outcome,
    }

    assert outcomes == set(f2523.ALLOWED_FUTURE_OUTCOMES)


def test_receipt_is_strict_metadata_with_hashes_and_zero_rf_persistence() -> None:
    result = _Fixture("upstream").evaluate()
    encoded = f2524.strict_json(result)
    document = json.loads(encoded)

    strict_json_value(asdict(result))
    assert len(document["segment_receipts"]) == 6
    assert all(len(item["artifact_hash"]) == 64 for item in document["segment_receipts"])
    assert document["raw_rf_persistence"] == "ZERO"
    assert not document["physical_decision_affected_by_description"]
    assert "samples" not in encoded.lower()
    assert "stft" not in encoded.lower()
    assert '"waterfall":' not in encoded.lower()
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_plan_mutation_is_a_distinct_trial() -> None:
    fixture = _Fixture("upstream")
    changed = replace(fixture.plan, confirmation_event_not_before=NOW + timedelta(seconds=1))

    assert changed.plan_hash != fixture.plan.plan_hash


def test_threshold_mutation_cannot_enter_confirmation_analysis() -> None:
    fixture = _Fixture("upstream")
    changed = replace(
        fixture.plan,
        thresholds=tuple(
            (name, value + 0.1 if name == "minimum_contrast_db" else value)
            for name, value in fixture.plan.thresholds
        ),
    )

    try:
        f2524.evaluate_confirmation_injected(
            changed,
            fixture.artifacts,
            profile_provider=fixture.provider,
            evaluated_at=NOW + timedelta(seconds=10),
        )
    except ValueError as error:
        assert "thresholds differ" in str(error)
    else:
        raise AssertionError("threshold drift entered confirmation analysis")
    assert fixture.profile_calls == 0
