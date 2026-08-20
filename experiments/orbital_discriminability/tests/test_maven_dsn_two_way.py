"""Offline tests for the scoped MAVEN/DSN two-way predictor."""

from dataclasses import FrozenInstanceError, replace

import pytest

from experiments.orbital_discriminability.maven_dsn_two_way import (
    MAVEN_X_BAND_TURNAROUND_DENOMINATOR,
    MAVEN_X_BAND_TURNAROUND_NUMERATOR,
    PiecewiseRamp,
    RampSegment,
    RsrReceiverTransform,
    SPEED_OF_LIGHT_M_S,
    StateVector,
    TwoWayPredictionError,
    direct_clock_envelope,
    predict_frozen_nulls,
    predict_two_way_baseband,
    solve_two_way_event,
)


def _linear(position_x_m: float, velocity_x_m_s: float = 0.0):
    return lambda time: StateVector(
        (position_x_m + velocity_x_m_s * time, 0.0, 0.0),
        (velocity_x_m_s, 0.0, 0.0),
    )


def _ramp() -> PiecewiseRamp:
    return PiecewiseRamp(
        (
            RampSegment(-100.0, 0.0, 7_180_000_000.0, 2.0),
            RampSegment(0.0, 100.0, 7_180_000_200.0, -1.0),
        )
    )


def _receiver() -> RsrReceiverTransform:
    return RsrReceiverTransform(
        record_start_time_s=20.0,
        rf_to_if_lo_hz=8_100_000_000.0,
        ddc_lo_hz=320_000_000.0,
        nco_f1_hz=10_000.0,
        nco_f2_hz=20.0,
        nco_f3_hz=-4.0,
        sample_rate_hz=1_000,
        sample_resolution_bits=16,
        receiver_id="1B",
        subchannel_id=1,
        predicts_time_shift_s=0.0,
        predicts_frequency_rate_hz_s=0.0,
        predicts_frequency_offset_hz=0.0,
        subchannel_frequency_offset_hz=0.0,
        frequency_override_active=False,
        predicts_frequency_override_hz=None,
        filter_bandwidth_hz=1_000.0,
        decimation=16_000,
    )


def test_stationary_two_way_light_time_and_turnaround() -> None:
    station = _linear(0.0)
    spacecraft = _linear(10.0 * SPEED_OF_LIGHT_M_S)
    event = solve_two_way_event(20.25, station, spacecraft, station)
    assert event.bounce_time_s == pytest.approx(10.25, abs=1e-12)
    assert event.transmit_time_s == pytest.approx(0.25, abs=1e-12)
    assert event.uplink_frequency_factor == pytest.approx(1.0, abs=1e-15)
    assert event.downlink_frequency_factor == pytest.approx(1.0, abs=1e-15)

    prediction = predict_two_way_baseband(
        20.25,
        _ramp(),
        _receiver(),
        station,
        spacecraft,
        station,
    )
    expected_uplink = 7_180_000_200.0 - 0.25
    expected_sky = (
        expected_uplink
        * MAVEN_X_BAND_TURNAROUND_NUMERATOR
        / MAVEN_X_BAND_TURNAROUND_DENOMINATOR
    )
    u = 0.2505
    expected_nco = 10_000.0 + 20.0 * u - 4.0 * u * u
    expected_baseband = expected_sky - 8_100_000_000.0 - 320_000_000.0 + expected_nco
    assert prediction.uplink_frequency_hz == pytest.approx(expected_uplink, abs=1e-9)
    assert prediction.nco_frequency_hz == pytest.approx(expected_nco, abs=1e-12)
    assert prediction.recorded_baseband_frequency_hz == pytest.approx(
        expected_baseband,
        abs=1e-6,
    )


def test_rsr_nco_uses_documented_millisecond_midpoint_and_sky_sign() -> None:
    receiver = _receiver()
    at_start = receiver.nco_frequency_hz(20.0)
    assert at_start == pytest.approx(
        10_000.0 + 20.0 * 0.0005 - 4.0 * 0.0005**2,
        abs=1e-15,
    )
    sky = 8_420_005_000.0
    assert receiver.baseband_frequency_hz(20.0, sky) == pytest.approx(
        5_000.0 + at_start,
        abs=1e-9,
    )
    with pytest.raises(TwoWayPredictionError):
        receiver.nco_frequency_hz(21.0)


def test_relative_motion_changes_both_legs_and_not_the_control_transform() -> None:
    station = _linear(0.0)
    receding_spacecraft = _linear(10.0 * SPEED_OF_LIGHT_M_S, 1_000.0)
    prediction = predict_two_way_baseband(
        20.25,
        _ramp(),
        _receiver(),
        station,
        receding_spacecraft,
        station,
    )
    no_motion = predict_two_way_baseband(
        20.25,
        _ramp(),
        _receiver(),
        station,
        _linear(10.0 * SPEED_OF_LIGHT_M_S),
        station,
    )
    assert prediction.received_sky_frequency_hz < no_motion.received_sky_frequency_hz
    assert prediction.nco_frequency_hz == no_motion.nco_frequency_hz


def test_nulls_share_ramp_timing_and_receiver_transform() -> None:
    station = _linear(0.0)
    nominal = _linear(10.0 * SPEED_OF_LIGHT_M_S, 1_000.0)
    mars_center = _linear(9.0 * SPEED_OF_LIGHT_M_S, 0.0)
    predictions = predict_frozen_nulls(
        20.25,
        _ramp(),
        _receiver(),
        station,
        nominal,
        mars_center,
        station,
    )
    assert predictions.nominal.transmit_time_s == pytest.approx(
        predictions.ramp_nco_only.transmit_time_s,
        abs=0.0,
    )
    assert predictions.nominal.uplink_frequency_hz == pytest.approx(
        predictions.ramp_nco_only.uplink_frequency_hz,
        abs=0.0,
    )
    assert {
        predictions.nominal.nco_frequency_hz,
        predictions.ramp_nco_only.nco_frequency_hz,
        predictions.geometry_destroying.nco_frequency_hz,
    } == {predictions.nominal.nco_frequency_hz}
    assert predictions.nominal.recorded_baseband_frequency_hz != (
        predictions.ramp_nco_only.recorded_baseband_frequency_hz
    )


def test_direct_clock_envelope_is_not_local_slope_times_error() -> None:
    envelopes = direct_clock_envelope(lambda time: time**3, (2.0,), 1.0)
    envelope = envelopes[0]
    assert envelope.minus_bound_hz == 1.0
    assert envelope.nominal_hz == 8.0
    assert envelope.plus_bound_hz == 27.0
    assert envelope.maximum_deviation_hz == 19.0
    assert envelope.maximum_deviation_hz != 12.0


def test_missing_exact_override_and_bad_ramp_topology_are_refused() -> None:
    with pytest.raises(TwoWayPredictionError):
        replace(
            _receiver(),
            frequency_override_active=True,
            predicts_frequency_override_hz=None,
        ).validate()
    with pytest.raises(TwoWayPredictionError):
        PiecewiseRamp(
            (
                RampSegment(0.0, 1.0, 1.0, 0.0),
                RampSegment(2.0, 3.0, 1.0, 0.0),
            )
        ).validate()


def test_scoped_inputs_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        _receiver().sample_rate_hz = 2_000  # type: ignore[misc]
