"""Offline Gate F2 tests: immutable frame predictions and one-shot semantics."""

from dataclasses import fields
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_probe as kiwi
from experiments.live_instrument.models import ClauseStatus, strict_json_value


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)


def _fingerprint(position: float, absolute: float, relative: float = -700.0) -> f2.FeatureFingerprint:
    patch = np.asarray([-0.08, -0.12, -0.04, 0.12, 0.45, 0.78, 0.45, 0.12, -0.04, -0.12, -0.08])
    patch = patch / np.linalg.norm(patch)
    return f2.FeatureFingerprint(
        position,
        absolute,
        40.0,
        tuple(float(value) for value in patch),
        relative,
        (8.0, 7.5, 0.5),
        (7.5, 9.0),
        20.0,
    )


def _plan(*, delta: float = 400.0, tolerance: float = 40.0) -> f2.FrozenPlan:
    mother = f2.MotherPlan()
    target = _fingerprint(100.0, 5_000_100.0)
    witness = _fingerprint(800.0, 5_000_800.0, 700.0)
    return f2.freeze_plan(
        mother,
        kiwi.KiwiEndpoint("reference", "reference.invalid", 8073),
        kiwi.KiwiEndpoint("perturbed", "perturbed.invalid", 8073),
        5_000_000.0,
        delta,
        1,
        target,
        witness,
        frozen_at=NOW,
        prediction_tolerance_hz=tolerance,
    )


def _match(value: bool, observed: float, expected: float) -> f2.FeatureMatch:
    return f2.FeatureMatch(value, observed, expected, 8.0 if value else 1.0, 0.9 if value else 0.1, "fixture")


def _facts(plan: f2.FrozenPlan, *, rf: bool = True, baseband: bool = False) -> f2.ConfirmationFacts:
    good_witness = _match(True, plan.witness.baseband_position_a_hz - plan.delta_f_hz, plan.witness.baseband_position_a_hz - plan.delta_f_hz)
    return f2.ConfirmationFacts(
        True, True, True, True, True, True, True, True, True,
        good_witness,
        _match(True, plan.target.baseband_position_a_hz, plan.target.baseband_position_a_hz),
        _match(rf, plan.rf_frame_target_b_hz, plan.rf_frame_target_b_hz),
        _match(baseband, plan.baseband_frame_target_b_hz, plan.baseband_frame_target_b_hz),
        _match(True, plan.target.baseband_position_a_hz, plan.target.baseband_position_a_hz),
        _match(True, plan.witness.baseband_position_a_hz, plan.witness.baseband_position_a_hz),
        True, True,
    )


def _segment_receipts(plan: f2.FrozenPlan) -> tuple[f2.SegmentReceipt, ...]:
    receipts = []
    for root in ("reference", "perturbed"):
        for index, phase in enumerate(("A1", "B", "A2")):
            start = NOW + timedelta(seconds=index * 4)
            receipts.append(
                f2.SegmentReceipt(
                    f"kiwi:{root}", phase, f"{root}-{phase}-hash", NOW - timedelta(seconds=1),
                    4096, start, start + timedelta(seconds=3),
                    plan.center_b_hz if root == "perturbed" and phase == "B" else plan.center_a_hz,
                    12_000.0, (index * 10, index * 10 + 9), 0, 0, f2.TRANSFORM_VERSION,
                )
            )
    return tuple(receipts)


def test_protocol_audit_places_retune_after_adc_in_fpga_nco() -> None:
    audit = f2.protocol_audit()
    assert "ADC -> [FPGA per-channel RX NCO/DDC intervention]" in audit.causal_interval
    assert "CmdSetRXFreq" in audit.exact_verified_point
    assert audit.hardware_lo_changed is False
    assert audit.acknowledgement_available is False
    assert audit.source_commit == f2.KIWI_SERVER_COMMIT


def test_axis_orientation_is_learned_only_from_witness_fixture() -> None:
    mother = f2.MotherPlan(minimum_witness_contrast_db=2.0, minimum_fingerprint_correlation=0.6)
    witness = _fingerprint(800.0, 5_000_800.0)
    frequencies = np.arange(-1500.0, 1500.1, 10.0)
    residual = np.zeros_like(frequencies)
    expected = 400.0
    index = int(np.argmin(np.abs(frequencies - expected)))
    patch = np.asarray(witness.local_spectral_neighbourhood_db) * 10.0
    residual[index - 5 : index + 6] = patch
    profile = f2._SpectralProfile(frequencies, residual.copy(), residual, residual.copy(), residual.copy(), 10.0)
    orientation, match = f2.learn_axis_orientation_from_witness(witness, profile, 400.0, 20.0, mother)
    assert orientation == 1
    assert match.matched
    assert match.observed_baseband_hz == 400.0


def test_b_matching_uses_frozen_baseband_intervals_not_reconstructed_rf() -> None:
    mother = f2.MotherPlan(minimum_contrast_db=2.0, minimum_fingerprint_correlation=0.6)
    plan = _plan()
    frequencies = np.arange(-1000.0, 1000.1, 10.0)
    residual = np.zeros_like(frequencies)
    index = int(np.argmin(np.abs(frequencies - plan.rf_frame_target_b_hz)))
    residual[index - 5 : index + 6] = np.asarray(plan.target.local_spectral_neighbourhood_db) * 10.0
    profile = f2._SpectralProfile(frequencies, residual.copy(), residual, residual.copy(), residual.copy(), 10.0)
    rf = f2.match_feature(profile, plan.target, plan.rf_frame_target_b_hz, 20.0, mother)
    baseband = f2.match_feature(profile, plan.target, plan.baseband_frame_target_b_hz, 20.0, mother)
    assert rf.matched
    assert not baseband.matched
    assert rf.expected_baseband_hz == -300.0
    assert plan.target.absolute_rf_estimate_a_hz not in profile.frequencies_hz


def test_plan_refuses_overlapping_rf_and_baseband_predictions() -> None:
    with pytest.raises(ValueError, match="overlap"):
        _plan(delta=50.0, tolerance=30.0)


@pytest.mark.parametrize(
    ("rf", "baseband", "expected"),
    [
        (True, False, f2.OutcomeKind.RF_FRAME_PREDICTION_SUPPORTED),
        (False, True, f2.OutcomeKind.BASEBAND_FRAME_PREDICTION_SUPPORTED),
        (True, True, f2.OutcomeKind.AMBIGUOUS),
        (False, False, f2.OutcomeKind.AMBIGUOUS),
    ],
)
def test_frame_outcomes_are_set_valued_and_deterministic(rf: bool, baseband: bool, expected: f2.OutcomeKind) -> None:
    plan = _plan()
    result = f2.classify_confirmation(plan, _facts(plan, rf=rf, baseband=baseband), _segment_receipts(plan), (), evaluated_at=NOW)
    assert result.outcome is expected
    assert result.does_not_support == (
        "same emitter confirmed",
        "external RF proven",
        "common physical cause confirmed",
    )
    strict_json_value(result)


def test_invalid_witness_blocks_every_target_frame_clause() -> None:
    plan = _plan()
    facts = replace_facts(
        _facts(plan),
        witness_b=_match(False, 0.0, plan.witness.baseband_position_a_hz - plan.delta_f_hz),
    )
    result = f2.classify_confirmation(plan, facts, _segment_receipts(plan), (), evaluated_at=NOW)
    assert result.outcome is f2.OutcomeKind.INTERVENTION_INVALID
    statuses = {assessment.clause: assessment.status for assessment in result.clause_assessments}
    assert statuses["witness_translation_valid"] is ClauseStatus.UNSATISFIED
    assert statuses["target_matches_RF-frame_prediction_B"] is ClauseStatus.NOT_EVALUATED
    assert statuses["target_matches_baseband-frame_prediction_B"] is ClauseStatus.NOT_EVALUATED
    assert statuses["target_returns_to_A_prediction"] is ClauseStatus.NOT_EVALUATED


def test_reference_loss_is_not_detectable_not_a_negative_frame_result() -> None:
    plan = _plan()
    facts = replace_facts(
        _facts(plan),
        target_reference_b=_match(False, 0.0, plan.target.baseband_position_a_hz),
    )
    result = f2.classify_confirmation(plan, facts, _segment_receipts(plan), (), evaluated_at=NOW)
    assert result.outcome is f2.OutcomeKind.NOT_DETECTABLE
    assert set(result.hypotheses_remaining) == {"H_RF_FRAME", "H_BASEBAND_FRAME", "H_OTHER_OR_UNRESOLVED"}


def test_no_plan_marks_all_downstream_clauses_not_evaluated() -> None:
    discovery = f2.DiscoveryReceipt(
        "fixture", "inventory", "https://inventory.invalid/list", "fixture",
        NOW - timedelta(seconds=2), NOW - timedelta(seconds=1),
        f2.DiscoveryResponseStatus.VALID_CANDIDATE_RESULT, 2, "0" * 64,
        None, None, 0, NOW + timedelta(seconds=599),
    )
    result = f2.no_experiment_result(
        f2.OutcomeKind.NO_FALSIFIABLE_EXPERIMENT_AVAILABLE,
        "no witness",
        progress=f2.GateProgress(f2.GatePhase.ADMISSION, 1, 2, 2, 1),
        discovery_receipts=(discovery,),
        candidate_hashes=("description-hash",),
        evaluated_at=NOW,
    )
    assert all(item.status is ClauseStatus.NOT_EVALUATED for item in result.clause_assessments)
    assert result.evidence_receipt.artifact_hashes == ("description-hash",)
    assert result.segment_receipts == ()


def test_receipts_contain_only_hashes_not_rf_samples() -> None:
    plan = _plan()
    result = f2.classify_confirmation(plan, _facts(plan), _segment_receipts(plan), (), evaluated_at=NOW)
    assert result.evidence_receipt.artifact_hashes
    assert all("samples" not in {field.name for field in fields(receipt)} for receipt in result.segment_receipts)
    encoded = strict_json_value(result)
    assert "samples" not in str(encoded).lower()


def test_synthetic_dual_capture_finds_target_and_witness_without_identity() -> None:
    mother = f2.MotherPlan(
        nperseg=512,
        noverlap=256,
        qualification_duration_s=3.0,
        minimum_contrast_db=3.0,
        minimum_witness_contrast_db=3.0,
        minimum_half_contrast_db=2.0,
        minimum_fingerprint_correlation=0.55,
        minimum_delta_hz=300.0,
        maximum_delta_hz=900.0,
        prediction_tolerance_bins=1.5,
    )
    left = _synthetic_capture("left", -1200.0, 900.0, seed=11)
    right = _synthetic_capture("right", -1200.0, 900.0, seed=23)
    geometry = f2.find_target_and_witness(left, right, mother)
    assert geometry.target.baseband_hz != geometry.witness.baseband_hz
    assert geometry.delta_f_hz >= mother.minimum_delta_hz
    assert geometry.baseline_hashes == (kiwi._capture_hash(left), kiwi._capture_hash(right))


def test_module_does_not_reintroduce_general_planner_or_instrument_class() -> None:
    names = set(vars(f2))
    assert not {"Planner", "InternetSource", "Instrument", "DetectabilityContract"} & names


def replace_facts(facts: f2.ConfirmationFacts, **changes) -> f2.ConfirmationFacts:
    values = {field.name: getattr(facts, field.name) for field in fields(facts)}
    values.update(changes)
    return f2.ConfirmationFacts(**values)


def _synthetic_capture(name: str, tone_a: float, tone_b: float, *, seed: int) -> kiwi.KiwiCapture:
    sample_rate = 12_000.0
    count = 48_000
    rng = np.random.default_rng(seed)
    t = np.arange(count) / sample_rate
    samples = (
        0.65 * np.exp(2j * np.pi * tone_a * t)
        + 0.45 * np.exp(2j * np.pi * tone_b * t)
        + 0.03 * (rng.normal(size=count) + 1j * rng.normal(size=count))
    ).astype(np.complex64)
    block_size = 512
    blocks = []
    start = NOW - timedelta(seconds=5)
    for sequence, begin in enumerate(range(0, count, block_size)):
        chunk = samples[begin : begin + block_size]
        event_start = start + timedelta(seconds=begin / sample_rate)
        event_end = event_start + timedelta(seconds=len(chunk) / sample_rate)
        blocks.append(
            kiwi.IQBlock(
                event_start, event_end, chunk, -70.0, 1, True, False, sequence,
                event_end + timedelta(seconds=0.1),
            )
        )
    endpoint = kiwi.KiwiEndpoint(name, f"{name}.invalid", 8073)
    return kiwi.KiwiCapture(
        endpoint, 5_000_000.0, sample_rate, {"ext_api": "1"}, tuple(blocks),
        blocks[0].arrived_at, blocks[-1].arrived_at,
    )
