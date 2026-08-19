"""Trajectory and differential-observable invariants for Gate G0."""

from datetime import timedelta

import numpy as np
import pytest

from experiments.live_instrument.orbital_kernel import (
    SPEED_OF_LIGHT_KM_S,
    Observer,
    compute_orbital_state,
)
from experiments.orbital_discriminability.synthetic import (
    COPENHAGEN,
    ISS_OMM,
    ISS_TLE,
    LAYOUTS,
    PASS_START,
)
from experiments.orbital_discriminability.trajectory import (
    TrajectoryError,
    apply_carrier_to_envelope,
    apply_carrier_hz,
    differential_trajectory,
    pairwise_differentials,
    sample_observer_network,
    sample_orbital_ensemble,
    sample_orbital_trajectory,
)


@pytest.fixture(scope="module")
def network():  # type: ignore[no-untyped-def]
    return sample_observer_network(
        ISS_TLE,
        {"BERLIN": LAYOUTS["BERLIN"], "COPENHAGEN": COPENHAGEN},
        PASS_START,
        PASS_START + timedelta(minutes=5),
        10.0,
    )


def test_fractional_trajectory_matches_scalar_kernel(network) -> None:  # type: ignore[no-untyped-def]
    trajectory = network["COPENHAGEN"]
    index = 12
    state = compute_orbital_state(
        COPENHAGEN,
        ISS_TLE,
        trajectory.timestamps[index],
    )

    assert trajectory.sample_count == 31
    assert trajectory.range_rate_km_s[index] == pytest.approx(
        state.range_rate_km_s,
        abs=1e-12,
    )
    assert trajectory.fractional_doppler[index] == pytest.approx(
        -state.range_rate_km_s / SPEED_OF_LIGHT_KM_S,
        abs=1e-18,
    )
    assert all(np.isfinite(trajectory.fractional_slope_s_inv))
    assert all(np.isfinite(trajectory.fractional_curvature_s2_inv))
    assert trajectory.closest_approach_time in trajectory.timestamps
    assert trajectory.range_rate_zero_crossings


def test_carrier_is_applied_after_geometry(network) -> None:  # type: ignore[no-untyped-def]
    fractional = network["BERLIN"].fractional_doppler
    vhf = np.asarray(apply_carrier_hz(fractional, 137_500_000.0))
    uhf = np.asarray(apply_carrier_hz(fractional, 435_000_000.0))

    assert uhf == pytest.approx(vhf * (435_000_000.0 / 137_500_000.0))
    assert network["BERLIN"].fractional_doppler == fractional


def test_differential_observable_is_station_coupled(network) -> None:  # type: ignore[no-untyped-def]
    differential = differential_trajectory(
        "COPENHAGEN",
        network["COPENHAGEN"],
        "BERLIN",
        network["BERLIN"],
    )
    expected = np.asarray(network["COPENHAGEN"].fractional_doppler) - np.asarray(
        network["BERLIN"].fractional_doppler
    )

    assert differential.fractional_doppler == pytest.approx(expected)
    assert any(abs(value) > 0.0 for value in differential.fractional_curvature_s2_inv)
    assert any(differential.joint_visibility_mask)
    assert pairwise_differentials(network) == {
        ("BERLIN", "COPENHAGEN"): differential_trajectory(
            "BERLIN",
            network["BERLIN"],
            "COPENHAGEN",
            network["COPENHAGEN"],
        )
    }


def test_controlled_orbit_ensemble_produces_frequency_envelope() -> None:
    early = dict(ISS_OMM, MEAN_ANOMALY=85.6298)
    late = dict(ISS_OMM, MEAN_ANOMALY=85.6498)
    nominal, envelopes = sample_orbital_ensemble(
        ISS_TLE,
        {"mean_anomaly_low": early, "mean_anomaly_high": late},
        {"BERLIN": LAYOUTS["BERLIN"], "COPENHAGEN": COPENHAGEN},
        PASS_START,
        PASS_START + timedelta(minutes=1),
        10.0,
    )
    frequency = apply_carrier_to_envelope(envelopes["BERLIN"], 145_800_000.0)

    assert set(nominal) == set(envelopes) == {"BERLIN", "COPENHAGEN"}
    assert frequency.member_count == 3
    assert frequency.maximum_absolute_deviation_hz > 0.0
    assert all(
        low <= center <= high
        for low, center, high in zip(
            frequency.lower_hz,
            frequency.nominal_hz,
            frequency.upper_hz,
            strict=True,
        )
    )


@pytest.mark.parametrize(
    ("start", "end", "cadence", "message"),
    (
        (PASS_START.replace(tzinfo=None), PASS_START + timedelta(minutes=1), 5.0, "timezone-aware"),
        (PASS_START, PASS_START, 5.0, "after"),
        (PASS_START, PASS_START + timedelta(seconds=5), 5.0, "three samples"),
        (PASS_START, PASS_START + timedelta(minutes=1), 0.0, "positive"),
    ),
)
def test_trajectory_refuses_ambiguous_grids(start, end, cadence, message) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(TrajectoryError, match=message):
        sample_orbital_trajectory(ISS_TLE, COPENHAGEN, start, end, cadence)


def test_network_requires_two_named_observers() -> None:
    with pytest.raises(TrajectoryError, match="at least two"):
        sample_observer_network(
            ISS_TLE,
            {"only": Observer(0.0, 0.0)},
            PASS_START,
            PASS_START + timedelta(minutes=1),
            5.0,
        )
