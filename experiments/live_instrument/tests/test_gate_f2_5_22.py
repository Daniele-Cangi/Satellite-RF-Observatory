"""Offline tests for Gate F2.5.22 discoverability and witness audit."""

from __future__ import annotations

from dataclasses import asdict
import inspect
import json
from types import SimpleNamespace

import numpy as np

from experiments.live_instrument import kiwi_gate_f2 as f2
from experiments.live_instrument import kiwi_gate_f2_5_22 as f2522
from experiments.live_instrument.models import strict_json_value


def _hashes(count: int) -> tuple[str, ...]:
    return tuple(f"{index + 1:064x}" for index in range(count))


def _profile(
    peaks: tuple[tuple[float, float], ...],
    *,
    first_scale: float = 1.0,
    second_scale: float = 1.0,
    shape_scale: float = 1.0,
) -> f2._SpectralProfile:
    frequencies = np.arange(-4_000.0, 4_000.1, 10.0)
    residual = np.zeros_like(frequencies)
    for position, height in peaks:
        residual += height * np.exp(-0.5 * ((frequencies - position) / (20.0 * shape_scale)) ** 2)
    return f2._SpectralProfile(
        frequencies,
        residual.copy(),
        residual.copy(),
        residual * first_scale,
        residual * second_scale,
        10.0,
    )


def _shift(values: np.ndarray, lag: int) -> np.ndarray:
    result = np.zeros_like(values)
    if lag > 0:
        result[lag:] = values[:-lag]
    elif lag < 0:
        result[:lag] = values[-lag:]
    else:
        result[:] = values
    return result


def _distributed_profiles() -> tuple[np.ndarray, ...]:
    rng = np.random.default_rng(2522)
    base = rng.normal(0.0, 1.0, 401)
    base[195:206] += np.asarray([0.0, 0.2, 0.5, 1.0, 2.0, 5.0, 2.0, 1.0, 0.5, 0.2, 0.0])
    shifted = _shift(base, 20)
    return base, base.copy(), base.copy(), base.copy(), shifted, base.copy()


def test_frozen_failure_is_localised_but_not_attributable() -> None:
    attribution = f2522.audit_frozen_outcome()

    assert attribution.artifact_hash == f2522.FROZEN_OUTCOME_SHA256
    assert attribution.outcome == "NO_FALSIFIABLE_INTERVENTION"
    assert attribution.dual_snd_state == "SATISFIED"
    assert attribution.discovery_state == "UNSATISFIED"
    assert attribution.downstream_states == (
        ("PER_CHANNEL_RETUNE_QUALIFICATION", "NOT_EVALUATED"),
        ("PLAN_FREEZE", "NOT_EVALUATED"),
        ("ONE_CONFIRMATION", "NOT_EVALUATED"),
    )
    assert attribution.recorded_discovery_hash_kind == "ERROR_DESCRIPTION_HASH_ONLY"
    assert not attribution.capture_artifact_hashes_present
    assert not attribution.candidate_counts_present
    assert not attribution.candidate_margins_present
    assert "UNDERLYING_CAUSE_NOT_ATTRIBUTABLE" in attribution.classification
    assert "exactly one stable feature existed" in attribution.unauthorised_claims


def test_frozen_discovery_hash_is_the_error_description_not_an_iq_artifact() -> None:
    expected = f2._hash(
        {
            "endpoint": "dl1bajkiwisdr.ddns.net:8074",
            "phase": "local_iq_feature_discovery",
            "error_type": "ValueError",
            "error": "prospective discovery contains fewer than two distinct stable structures",
        }
    )

    assert expected == f2522.FROZEN_DISCOVERY_ERROR_HASH


def test_descriptive_audit_separates_peaks_features_and_pair_geometry() -> None:
    left = _profile(((-1_200.0, 9.0), (1_000.0, 8.0)))
    right = _profile(((-1_200.0, 8.5), (1_000.0, 7.5)))

    receipt = f2522.audit_profile_pair(left, right, _hashes(2))

    assert receipt.state == "TWO_FEATURE_PLAN_ELIGIBLE"
    assert receipt.raw_peak_count == 2
    assert receipt.patch_valid_count == 2
    assert receipt.correlation_pass_count == 2
    assert receipt.half_stability_pass_count == 2
    assert receipt.admitted_feature_count == 2
    assert receipt.eligible_pair_count_positive_axis > 0
    assert receipt.eligible_pair_count_negative_axis > 0
    assert receipt.selected_geometry_orientation_neutral
    assert {item.state for item in receipt.candidates} == {"ADMITTED"}
    assert receipt.input_artifact_hashes == _hashes(2)
    assert receipt.hashes_bound_before_first_spectral_transform
    assert receipt.raw_rf_persistence == "ZERO"
    assert "samples" not in f2522.strict_json(receipt).lower()
    strict_json_value(asdict(receipt))


def test_one_feature_is_described_without_becoming_a_physical_absence() -> None:
    receipt = f2522.audit_profile_pair(
        _profile(((-1_200.0, 9.0),)),
        _profile(((-1_200.0, 8.5),)),
        _hashes(2),
    )

    assert receipt.state == "ONE_STABLE_FEATURE_ONLY"
    assert receipt.raw_peak_count == 1
    assert receipt.admitted_feature_count == 1
    assert receipt.eligible_pair_count_positive_axis == 0
    assert receipt.eligible_pair_count_negative_axis == 0
    assert not receipt.selected_geometry_orientation_neutral


def test_half_window_rejection_retains_finite_margins_and_reason() -> None:
    left = _profile(((-1_200.0, 9.0),), first_scale=0.2)
    right = _profile(((-1_200.0, 8.5),), first_scale=0.2)

    receipt = f2522.audit_profile_pair(left, right, _hashes(2))
    candidate = receipt.candidates[0]

    assert receipt.state == "CANDIDATES_REJECTED"
    assert receipt.raw_peak_count == 1
    assert receipt.patch_valid_count == 1
    assert receipt.correlation_pass_count == 1
    assert receipt.half_stability_pass_count == 0
    assert candidate.state == "HALF_STABILITY_BELOW_THRESHOLD"
    assert candidate.half_stability_margin_db.state == "FINITE"
    assert candidate.half_stability_margin_db.value is not None
    assert candidate.half_stability_margin_db.value < 0.0


def test_artifact_wrapper_binds_both_hashes_before_profile_transform(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    profiles = iter(
        (
            _profile(((-1_200.0, 9.0),)),
            _profile(((-1_200.0, 8.5),)),
        )
    )
    monkeypatch.setattr(f2, "_capture_profile", lambda *_args: next(profiles))
    artifacts = SimpleNamespace(
        reference={
            "DISCOVERY_A": SimpleNamespace(capture=object(), artifact_hash=_hashes(2)[0])
        },
        perturbed={
            "DISCOVERY_A": SimpleNamespace(capture=object(), artifact_hash=_hashes(2)[1])
        },
    )

    receipt = f2522.audit_discovery_artifacts(artifacts)

    assert receipt.input_artifact_hashes == _hashes(2)
    assert receipt.hashes_bound_before_first_spectral_transform


def test_distributed_fingerprint_can_replace_a_second_peak_but_not_the_witness() -> None:
    reference_a1, reference_b, reference_a2, perturbed_a1, perturbed_b, perturbed_a2 = (
        _distributed_profiles()
    )

    receipt = f2522.assess_distributed_witness(
        reference_a1=reference_a1,
        reference_b=reference_b,
        reference_a2=reference_a2,
        perturbed_a1=perturbed_a1,
        perturbed_b=perturbed_b,
        perturbed_a2=perturbed_a2,
        input_artifact_hashes=_hashes(6),
        delta_bins=20,
        target_index=200,
        target_exclusion_radius=5,
    )

    assert receipt.state == "QUALIFIED_AS_FUTURE_WITNESS"
    assert receipt.learned_orientation == 1
    assert receipt.target_bins_excluded
    assert receipt.usable_bin_count >= 64
    assert dict(receipt.clauses) == {
        "minimum_64_out_of_target_bins": "SATISFIED",
        "cross_branch_A_state": "SATISFIED",
        "fixed_reference_branch": "SATISFIED",
        "perturbed_A2_return": "SATISFIED",
        "unique_nonzero_translation": "SATISFIED",
        "even_odd_translation_consistency": "SATISFIED",
        "target_bins_excluded": "SATISFIED",
    }
    assert "target upstream/downstream hypothesis" in receipt.does_not_prove
    assert "samples" not in f2522.strict_json(receipt).lower()
    strict_json_value(asdict(receipt))


def test_channel_fixed_background_leaves_intervention_unresolved() -> None:
    base, _, _, _, _, _ = _distributed_profiles()

    receipt = f2522.assess_distributed_witness(
        reference_a1=base,
        reference_b=base,
        reference_a2=base,
        perturbed_a1=base,
        perturbed_b=base,
        perturbed_a2=base,
        input_artifact_hashes=_hashes(6),
        delta_bins=20,
        target_index=200,
        target_exclusion_radius=5,
    )

    assert receipt.state == "INTERVENTION_UNRESOLVED"
    assert receipt.learned_orientation is None
    assert dict(receipt.clauses)["fixed_reference_branch"] == "SATISFIED"
    assert dict(receipt.clauses)["unique_nonzero_translation"] == "UNSATISFIED"


def test_target_and_all_predeclared_translations_cannot_change_witness_scores() -> None:
    profiles = list(_distributed_profiles())
    baseline = f2522.assess_distributed_witness(
        reference_a1=profiles[0],
        reference_b=profiles[1],
        reference_a2=profiles[2],
        perturbed_a1=profiles[3],
        perturbed_b=profiles[4],
        perturbed_a2=profiles[5],
        input_artifact_hashes=_hashes(6),
        delta_bins=20,
        target_index=200,
        target_exclusion_radius=5,
    )
    for ordinal, profile in enumerate(profiles):
        for centre in (180, 190, 200, 210, 220):
            profile[centre - 5 : centre + 6] = (ordinal + 1) * 1_000.0
    altered = f2522.assess_distributed_witness(
        reference_a1=profiles[0],
        reference_b=profiles[1],
        reference_a2=profiles[2],
        perturbed_a1=profiles[3],
        perturbed_b=profiles[4],
        perturbed_a2=profiles[5],
        input_artifact_hashes=_hashes(6),
        delta_bins=20,
        target_index=200,
        target_exclusion_radius=5,
    )

    assert altered.state == baseline.state
    assert altered.learned_orientation == baseline.learned_orientation
    assert altered.usable_bin_count == baseline.usable_bin_count
    assert altered.correlations == baseline.correlations
    assert altered.clauses == baseline.clauses


def test_flat_or_unstable_background_is_not_detectable() -> None:
    flat = np.zeros(401)

    receipt = f2522.assess_distributed_witness(
        reference_a1=flat,
        reference_b=flat,
        reference_a2=flat,
        perturbed_a1=flat,
        perturbed_b=flat,
        perturbed_a2=flat,
        input_artifact_hashes=_hashes(6),
        delta_bins=20,
        target_index=200,
        target_exclusion_radius=5,
    )

    assert receipt.state == "NOT_DETECTABLE"
    assert receipt.learned_orientation is None


def test_gate_is_offline_strict_json_and_changes_no_frozen_threshold() -> None:
    assessment = f2522.assess_gate_f2_5_22()
    source = inspect.getsource(f2522)
    encoded = f2522.strict_json(assessment)

    assert assessment.exit is (
        f2522.GateF2522Exit.OFFLINE_DISCOVERABILITY_AUDIT_COMPLETE
    )
    assert assessment.two_peak_requirement == "SUFFICIENT_BUT_NOT_CAUSALLY_NECESSARY"
    assert assessment.orthogonal_witness_requirement == (
        "STILL_REQUIRED_AND_MUST_NOT_USE_TARGET_BINS"
    )
    assert not assessment.alternative_live_qualified
    assert not assessment.old_thresholds_changed
    assert not assessment.old_outcome_changed
    assert not assessment.live_execution_authorised
    assert assessment.raw_rf_persistence == "ZERO"
    assert "fetch_kiwi_status" not in source
    assert "_capture_dual" not in source
    assert "websocket" not in source
    assert json.loads(encoded)["live_execution_authorised"] is False
    strict_json_value(asdict(assessment))
