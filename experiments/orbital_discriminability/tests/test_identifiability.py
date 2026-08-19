"""Held-out discriminability and no-leak tests for Gate G0."""

from dataclasses import asdict
import json

import numpy as np
import pytest

from experiments.orbital_discriminability.heldout import (
    G0Outcome,
    HeldoutPlan,
    evaluate_heldout,
)
from experiments.orbital_discriminability.null_models import (
    fit_frozen_nulls,
    fit_orbital_model,
)
from experiments.orbital_discriminability.nuisance import make_calibration_split
from experiments.orbital_discriminability.synthetic import (
    COPENHAGEN,
    LAYOUTS,
    add_holdout_curvature,
    make_nonorbital_observations,
    make_orbital_scenario,
    run_discriminability_sweep,
)


@pytest.fixture(scope="module")
def distributed():  # type: ignore[no-untyped-def]
    return make_orbital_scenario(
        {
            "COPENHAGEN": COPENHAGEN,
            "BERLIN": LAYOUTS["BERLIN"],
            "EINDHOVEN": LAYOUTS["EINDHOVEN"],
        },
        noise_sigma_hz=0.2,
    )


@pytest.fixture(scope="module")
def local_pair():  # type: ignore[no-untyped-def]
    return make_orbital_scenario(
        {"COPENHAGEN": COPENHAGEN, "LOCAL": LAYOUTS["LOCAL_10_KM"]},
        carrier_hz=137_500_000.0,
        noise_sigma_hz=0.2,
    )


def test_detectable_orbital_geometry_wins_one_independent_holdout(distributed) -> None:  # type: ignore[no-untyped-def]
    result = evaluate_heldout(
        distributed.elapsed_s,
        distributed.observations_hz,
        distributed.orbital_predictions_hz,
        HeldoutPlan(frequency_resolution_hz=5.0, maximum_clock_error_s=1.0),
    )

    assert result.outcome == G0Outcome.ORBITAL_MODEL_PREDICTIVELY_PREFERRED.value
    assert result.orbital_score.holdout_rmse_hz < result.best_null_holdout_rmse_hz
    assert result.preference_margin_hz >= result.required_preference_margin_hz
    assert result.detectability_margin_hz > 0.0
    assert result.calibrated_probability_used is False
    assert result.orbital_score.parameter_count == 2 * len(result.station_ids)


def test_coarse_or_time_uncertain_capability_is_not_detectable(local_pair) -> None:  # type: ignore[no-untyped-def]
    result = evaluate_heldout(
        local_pair.elapsed_s,
        local_pair.observations_hz,
        local_pair.orbital_predictions_hz,
        HeldoutPlan(frequency_resolution_hz=20.0, maximum_clock_error_s=5.0),
    )

    assert result.outcome == G0Outcome.ORBITAL_SIGNATURE_BELOW_DETECTABILITY.value
    assert result.detectability_margin_hz < 0.0
    assert result.orbital_score.holdout_rmse_hz < result.orbital_tolerance_hz


def test_common_transmitter_drift_cancels_in_differential_score(distributed) -> None:  # type: ignore[no-untyped-def]
    times = np.asarray(distributed.elapsed_s)
    normalized = times / times[-1]
    common_cubic = 250.0 * (normalized**2 - 0.4 * normalized**3)
    observations = {
        station: tuple(float(value) for value in np.asarray(values) + common_cubic)
        for station, values in distributed.observations_hz.items()
    }
    plan = HeldoutPlan(frequency_resolution_hz=5.0, maximum_clock_error_s=1.0)
    original = evaluate_heldout(
        distributed.elapsed_s,
        distributed.observations_hz,
        distributed.orbital_predictions_hz,
        plan,
    )
    with_common_drift = evaluate_heldout(
        distributed.elapsed_s,
        observations,
        distributed.orbital_predictions_hz,
        plan,
    )

    assert with_common_drift.outcome == G0Outcome.ORBITAL_MODEL_PREDICTIVELY_PREFERRED.value
    assert with_common_drift.orbital_score.holdout_rmse_hz == pytest.approx(
        original.orbital_score.holdout_rmse_hz,
        abs=1e-9,
    )


def test_nonorbital_data_rejects_orbital_prediction(distributed) -> None:  # type: ignore[no-untyped-def]
    observations = make_nonorbital_observations(
        distributed.elapsed_s,
        tuple(distributed.trajectories),
        mode="common_cubic",
    )
    result = evaluate_heldout(
        distributed.elapsed_s,
        observations,
        distributed.orbital_predictions_hz,
        HeldoutPlan(frequency_resolution_hz=5.0, maximum_clock_error_s=0.0),
    )

    assert result.outcome == G0Outcome.ORBITAL_PREDICTION_REJECTED.value
    # The common cubic cancels in the station difference, so the simpler
    # affine differential null is correctly sufficient.
    assert result.best_null_name == "N1_STATION_AFFINE"
    assert result.null_scores[1].holdout_rmse_hz == pytest.approx(
        result.null_scores[2].holdout_rmse_hz,
        abs=1e-12,
    )
    assert result.orbital_score.holdout_rmse_hz > result.orbital_tolerance_hz


def test_detectable_but_weak_local_geometry_is_not_discriminative(local_pair) -> None:  # type: ignore[no-untyped-def]
    result = evaluate_heldout(
        local_pair.elapsed_s,
        local_pair.observations_hz,
        local_pair.orbital_predictions_hz,
        HeldoutPlan(
            frequency_resolution_hz=20.0,
            maximum_clock_error_s=0.0,
            minimum_signature_bins=1.0,
        ),
    )

    assert result.detectability_margin_hz > 0.0
    assert result.orbital_score.holdout_rmse_hz <= result.orbital_tolerance_hz
    assert result.outcome == G0Outcome.ORBITAL_MODEL_NOT_DISCRIMINATIVE.value
    assert result.preference_margin_hz < result.required_preference_margin_hz


def test_holdout_changes_cannot_refit_orbital_nuisance(distributed) -> None:  # type: ignore[no-untyped-def]
    plan = HeldoutPlan(frequency_resolution_hz=5.0, maximum_clock_error_s=0.0)
    split = make_calibration_split(
        len(distributed.elapsed_s),
        plan.calibration_fraction,
        minimum_calibration_samples=plan.minimum_calibration_samples,
        minimum_holdout_samples=plan.minimum_holdout_samples,
    )
    original = fit_orbital_model(
        distributed.elapsed_s,
        distributed.observations_hz,
        distributed.orbital_predictions_hz,
        split,
    )
    corrupted_observations = add_holdout_curvature(
        distributed,
        plan.calibration_fraction,
        amplitude_hz=5_000.0,
    )
    corrupted = fit_orbital_model(
        distributed.elapsed_s,
        corrupted_observations,
        distributed.orbital_predictions_hz,
        split,
    )
    result = evaluate_heldout(
        distributed.elapsed_s,
        corrupted_observations,
        distributed.orbital_predictions_hz,
        plan,
    )

    assert corrupted.prediction_hz == original.prediction_hz
    assert corrupted.calibration_rmse_hz == pytest.approx(original.calibration_rmse_hz)
    assert result.outcome == G0Outcome.ORBITAL_PREDICTION_REJECTED.value


def test_declared_dropouts_reduce_receipt_support_without_imputation(distributed) -> None:  # type: ignore[no-untyped-def]
    observations = {
        station: np.asarray(values, dtype=np.float64).copy()
        for station, values in distributed.observations_hz.items()
    }
    observations["BERLIN"][20:24] = np.nan
    observations["EINDHOVEN"][32:35] = np.nan
    result = evaluate_heldout(
        distributed.elapsed_s,
        observations,
        distributed.orbital_predictions_hz,
        HeldoutPlan(frequency_resolution_hz=5.0, maximum_clock_error_s=1.0),
    )

    full_pair_samples = result.split.holdout_count * 3
    assert result.outcome == G0Outcome.ORBITAL_MODEL_PREDICTIVELY_PREFERRED.value
    assert 0 < result.orbital_score.holdout_valid_count < full_pair_samples


def test_nulls_are_frozen_declared_and_use_the_same_split(distributed) -> None:  # type: ignore[no-untyped-def]
    split = make_calibration_split(len(distributed.elapsed_s), 0.2)
    nulls = fit_frozen_nulls(
        distributed.elapsed_s,
        distributed.observations_hz,
        distributed.orbital_predictions_hz,
        split,
    )

    assert [item.name for item in nulls] == [
        "N0_STATION_CONSTANT",
        "N1_STATION_AFFINE",
        "N2_COMMON_CUBIC_PLUS_STATION_AFFINE",
        "N3_STATION_LABELS_PERMUTED",
        "N4_OBSERVER_COORDINATES_PERMUTED",
    ]
    assert [item.parameter_count for item in nulls] == [3, 6, 8, 6, 6]
    assert all(item.calibration_valid_count == split.calibration_count * 3 for item in nulls)
    assert nulls[3].prediction_hz != nulls[4].prediction_hz


def test_receipt_is_deterministic_strict_finite_json(distributed) -> None:  # type: ignore[no-untyped-def]
    plan = HeldoutPlan(frequency_resolution_hz=5.0, maximum_clock_error_s=1.0)
    first = evaluate_heldout(
        distributed.elapsed_s,
        distributed.observations_hz,
        distributed.orbital_predictions_hz,
        plan,
    )
    second = evaluate_heldout(
        distributed.elapsed_s,
        distributed.observations_hz,
        distributed.orbital_predictions_hz,
        plan,
    )
    encoded = json.dumps(asdict(first), allow_nan=False, sort_keys=True)

    assert first == second
    assert first.plan_hash == plan.plan_hash
    assert len(first.plan_hash) == 64
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_sweep_maps_both_usable_and_unusable_capability_regions() -> None:
    cases = run_discriminability_sweep()
    outcomes = {item.outcome for item in cases}

    assert len(cases) == 4 * 2 * 4 * 4
    assert G0Outcome.ORBITAL_MODEL_PREDICTIVELY_PREFERRED.value in outcomes
    assert G0Outcome.ORBITAL_SIGNATURE_BELOW_DETECTABILITY.value in outcomes
    assert all(np.isfinite(item.detectability_margin_hz) for item in cases)
    assert all(item.baseline_km > 0.0 for item in cases)
