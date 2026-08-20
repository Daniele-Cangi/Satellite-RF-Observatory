"""Scoped two-way link predictor for the MAVEN/DSN RSR prospective audit.

This module does not read RSR products, select SPICE kernels, or estimate a
signal ridge.  It materializes only the causal transform that the prospective
plan requires.  All times and states supplied by the caller must use one
explicit inertial coordinate-time system; UTC-to-coordinate-time conversion is
therefore outside this small numerical kernel and must be receipted separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, sqrt
from typing import Callable, Iterable


SPEED_OF_LIGHT_M_S = 299_792_458.0
MAVEN_X_BAND_TURNAROUND_NUMERATOR = 880
MAVEN_X_BAND_TURNAROUND_DENOMINATOR = 749


class TwoWayPredictionError(ValueError):
    """Raised when a two-way prediction input is absent or inconsistent."""


@dataclass(frozen=True, slots=True)
class StateVector:
    """Position and velocity in one caller-declared inertial frame."""

    position_m: tuple[float, float, float]
    velocity_m_s: tuple[float, float, float]

    def validate(self) -> None:
        values = (*self.position_m, *self.velocity_m_s)
        if not all(isfinite(value) for value in values):
            raise TwoWayPredictionError("state vectors must be finite")
        if _norm(self.velocity_m_s) >= SPEED_OF_LIGHT_M_S:
            raise TwoWayPredictionError("state-vector speed must be subluminal")


StateProvider = Callable[[float], StateVector]


@dataclass(frozen=True, slots=True)
class RampSegment:
    """One PDS FUP segment, evaluated from its Earth-transmit epoch."""

    start_time_s: float
    stop_time_s: float
    start_frequency_hz: float
    rate_hz_s: float

    def validate(self) -> None:
        values = (
            self.start_time_s,
            self.stop_time_s,
            self.start_frequency_hz,
            self.rate_hz_s,
        )
        if not all(isfinite(value) for value in values):
            raise TwoWayPredictionError("ramp values must be finite")
        if self.stop_time_s <= self.start_time_s:
            raise TwoWayPredictionError("ramp segment must have positive duration")
        if self.start_frequency_hz <= 0.0:
            raise TwoWayPredictionError("ramp frequency must be positive")

    def evaluate(self, transmit_time_s: float) -> float:
        self.validate()
        if not self.start_time_s <= transmit_time_s < self.stop_time_s:
            raise TwoWayPredictionError("Earth-transmit time is outside ramp segment")
        return self.start_frequency_hz + self.rate_hz_s * (
            transmit_time_s - self.start_time_s
        )


@dataclass(frozen=True, slots=True)
class PiecewiseRamp:
    """Frozen ordered FUP segments; gaps and overlaps are refused."""

    segments: tuple[RampSegment, ...]

    def validate(self) -> None:
        if not self.segments:
            raise TwoWayPredictionError("at least one ramp segment is required")
        for segment in self.segments:
            segment.validate()
        for left, right in zip(self.segments, self.segments[1:]):
            if left.stop_time_s != right.start_time_s:
                raise TwoWayPredictionError(
                    "ramp segments must be contiguous and non-overlapping"
                )

    def evaluate(self, transmit_time_s: float) -> float:
        self.validate()
        for segment in self.segments:
            if segment.start_time_s <= transmit_time_s < segment.stop_time_s:
                return segment.evaluate(transmit_time_s)
        raise TwoWayPredictionError("Earth-transmit time is not covered by the ramp")


@dataclass(frozen=True, slots=True)
class RsrReceiverTransform:
    """Per-SFDU receiver state needed to predict recorded residual frequency.

    The NCO coefficients are the RSR fields F1, F2 and F3.  Frequency-rate,
    frequency-offset, sub-channel-offset and override controls are retained in
    the receipt but are not added a second time: the archived NCO coefficients
    already embody the controls that were active for that SFDU.
    """

    record_start_time_s: float
    rf_to_if_lo_hz: float
    ddc_lo_hz: float
    nco_f1_hz: float
    nco_f2_hz: float
    nco_f3_hz: float
    sample_rate_hz: int
    sample_resolution_bits: int
    receiver_id: str
    subchannel_id: int
    predicts_time_shift_s: float
    predicts_frequency_rate_hz_s: float
    predicts_frequency_offset_hz: float
    subchannel_frequency_offset_hz: float
    frequency_override_active: bool
    predicts_frequency_override_hz: float | None
    filter_bandwidth_hz: float | None
    decimation: int | None

    def validate(self) -> None:
        numeric = (
            self.record_start_time_s,
            self.rf_to_if_lo_hz,
            self.ddc_lo_hz,
            self.nco_f1_hz,
            self.nco_f2_hz,
            self.nco_f3_hz,
            self.predicts_time_shift_s,
            self.predicts_frequency_rate_hz_s,
            self.predicts_frequency_offset_hz,
            self.subchannel_frequency_offset_hz,
        )
        if not all(isfinite(value) for value in numeric):
            raise TwoWayPredictionError("RSR transform fields must be finite")
        if self.sample_rate_hz <= 0 or self.sample_resolution_bits <= 0:
            raise TwoWayPredictionError("RSR sample configuration must be positive")
        if not self.receiver_id or self.subchannel_id < 1:
            raise TwoWayPredictionError("RSR receiver and sub-channel are required")
        if self.frequency_override_active:
            if self.predicts_frequency_override_hz is None or not isfinite(
                self.predicts_frequency_override_hz
            ):
                raise TwoWayPredictionError(
                    "an active RSR frequency override requires its exact value"
                )
        elif self.predicts_frequency_override_hz is not None and not isfinite(
            self.predicts_frequency_override_hz
        ):
            raise TwoWayPredictionError("RSR frequency override must be finite")
        if self.filter_bandwidth_hz is not None and (
            not isfinite(self.filter_bandwidth_hz)
            or self.filter_bandwidth_hz <= 0.0
        ):
            raise TwoWayPredictionError("filter bandwidth must be positive")
        if self.decimation is not None and self.decimation <= 0:
            raise TwoWayPredictionError("decimation must be positive")

    def nco_frequency_hz(self, receive_time_s: float) -> float:
        """Evaluate the documented RSR polynomial at the millisecond midpoint."""

        self.validate()
        offset_s = receive_time_s - self.record_start_time_s
        if not 0.0 <= offset_s < 1.0:
            raise TwoWayPredictionError("sample time is outside the one-second SFDU")
        millisecond = min(999, floor(offset_s * 1000.0))
        u = (millisecond + 0.5) / 1000.0
        return self.nco_f1_hz + self.nco_f2_hz * u + self.nco_f3_hz * u * u

    def baseband_frequency_hz(
        self,
        receive_time_s: float,
        received_sky_frequency_hz: float,
    ) -> float:
        """Invert the RSR sky-frequency equation to the recorded residual."""

        if not isfinite(received_sky_frequency_hz):
            raise TwoWayPredictionError("received sky frequency must be finite")
        return (
            received_sky_frequency_hz
            - self.rf_to_if_lo_hz
            - self.ddc_lo_hz
            + self.nco_frequency_hz(receive_time_s)
        )


@dataclass(frozen=True, slots=True)
class TwoWayEvent:
    receive_time_s: float
    bounce_time_s: float
    transmit_time_s: float
    uplink_light_time_s: float
    downlink_light_time_s: float
    uplink_frequency_factor: float
    downlink_frequency_factor: float


@dataclass(frozen=True, slots=True)
class BasebandPrediction:
    receive_time_s: float
    transmit_time_s: float
    uplink_frequency_hz: float
    spacecraft_turnaround_frequency_hz: float
    received_sky_frequency_hz: float
    nco_frequency_hz: float
    recorded_baseband_frequency_hz: float
    uplink_light_time_s: float
    downlink_light_time_s: float


@dataclass(frozen=True, slots=True)
class FrozenNullPredictions:
    """The two required nulls after the identical ramp and RSR transform."""

    nominal: BasebandPrediction
    ramp_nco_only: BasebandPrediction
    geometry_destroying: BasebandPrediction


@dataclass(frozen=True, slots=True)
class ClockEnvelope:
    receive_time_s: float
    error_bound_s: float
    nominal_hz: float
    minus_bound_hz: float
    plus_bound_hz: float

    @property
    def maximum_deviation_hz(self) -> float:
        return max(
            abs(self.minus_bound_hz - self.nominal_hz),
            abs(self.plus_bound_hz - self.nominal_hz),
        )


def solve_two_way_event(
    receive_time_s: float,
    uplink_station: StateProvider,
    spacecraft: StateProvider,
    downlink_station: StateProvider,
    *,
    tolerance_s: float = 1e-9,
    maximum_iterations: int = 30,
) -> TwoWayEvent:
    """Solve transmit and bounce epochs by direct two-leg light-time iteration."""

    if not isfinite(receive_time_s):
        raise TwoWayPredictionError("receive time must be finite")
    if not isfinite(tolerance_s) or tolerance_s <= 0.0:
        raise TwoWayPredictionError("light-time tolerance must be positive")
    if maximum_iterations < 1:
        raise TwoWayPredictionError("light-time iteration count must be positive")

    down_state = _validated_state(downlink_station(receive_time_s))
    bounce_time_s = receive_time_s
    transmit_time_s = receive_time_s
    for _ in range(maximum_iterations):
        spacecraft_at_bounce = _validated_state(spacecraft(bounce_time_s))
        next_bounce = receive_time_s - _distance(
            spacecraft_at_bounce.position_m,
            down_state.position_m,
        ) / SPEED_OF_LIGHT_M_S
        spacecraft_at_next_bounce = _validated_state(spacecraft(next_bounce))
        uplink_state = _validated_state(uplink_station(transmit_time_s))
        next_transmit = next_bounce - _distance(
            uplink_state.position_m,
            spacecraft_at_next_bounce.position_m,
        ) / SPEED_OF_LIGHT_M_S
        if max(
            abs(next_bounce - bounce_time_s),
            abs(next_transmit - transmit_time_s),
        ) <= tolerance_s:
            bounce_time_s = next_bounce
            transmit_time_s = next_transmit
            break
        bounce_time_s = next_bounce
        transmit_time_s = next_transmit
    else:
        raise TwoWayPredictionError("two-way light-time solution did not converge")

    uplink_state = _validated_state(uplink_station(transmit_time_s))
    spacecraft_state = _validated_state(spacecraft(bounce_time_s))
    up_direction = _unit_direction(
        uplink_state.position_m,
        spacecraft_state.position_m,
    )
    down_direction = _unit_direction(
        spacecraft_state.position_m,
        down_state.position_m,
    )
    uplink_factor = _frequency_factor(
        uplink_state.velocity_m_s,
        spacecraft_state.velocity_m_s,
        up_direction,
    )
    downlink_factor = _frequency_factor(
        spacecraft_state.velocity_m_s,
        down_state.velocity_m_s,
        down_direction,
    )
    return TwoWayEvent(
        receive_time_s=receive_time_s,
        bounce_time_s=bounce_time_s,
        transmit_time_s=transmit_time_s,
        uplink_light_time_s=bounce_time_s - transmit_time_s,
        downlink_light_time_s=receive_time_s - bounce_time_s,
        uplink_frequency_factor=uplink_factor,
        downlink_frequency_factor=downlink_factor,
    )


def predict_two_way_baseband(
    receive_time_s: float,
    ramp: PiecewiseRamp,
    receiver: RsrReceiverTransform,
    uplink_station: StateProvider,
    spacecraft: StateProvider,
    downlink_station: StateProvider,
) -> BasebandPrediction:
    """Apply ramp, two-way geometry, turnaround, and the exact RSR transform."""

    event = solve_two_way_event(
        receive_time_s,
        uplink_station,
        spacecraft,
        downlink_station,
    )
    return _prediction_from_event(event, ramp, receiver, use_geometry=True)


def predict_frozen_nulls(
    receive_time_s: float,
    ramp: PiecewiseRamp,
    receiver: RsrReceiverTransform,
    uplink_station: StateProvider,
    nominal_spacecraft: StateProvider,
    geometry_destroying_spacecraft: StateProvider,
    downlink_station: StateProvider,
) -> FrozenNullPredictions:
    """Evaluate both predeclared nulls through the same control transforms."""

    nominal_event = solve_two_way_event(
        receive_time_s,
        uplink_station,
        nominal_spacecraft,
        downlink_station,
    )
    alternate_event = solve_two_way_event(
        receive_time_s,
        uplink_station,
        geometry_destroying_spacecraft,
        downlink_station,
    )
    return FrozenNullPredictions(
        nominal=_prediction_from_event(
            nominal_event,
            ramp,
            receiver,
            use_geometry=True,
        ),
        ramp_nco_only=_prediction_from_event(
            nominal_event,
            ramp,
            receiver,
            use_geometry=False,
        ),
        geometry_destroying=_prediction_from_event(
            alternate_event,
            ramp,
            receiver,
            use_geometry=True,
        ),
    )


def direct_clock_envelope(
    predictor: Callable[[float], float],
    receive_times_s: Iterable[float],
    error_bound_s: float,
) -> tuple[ClockEnvelope, ...]:
    """Evaluate direct t-Delta and t+Delta trajectories, never slope times Delta."""

    if not isfinite(error_bound_s) or error_bound_s < 0.0:
        raise TwoWayPredictionError("clock-error bound must be finite and non-negative")
    envelopes: list[ClockEnvelope] = []
    for receive_time_s in receive_times_s:
        if not isfinite(receive_time_s):
            raise TwoWayPredictionError("clock-envelope times must be finite")
        nominal = predictor(receive_time_s)
        minus = predictor(receive_time_s - error_bound_s)
        plus = predictor(receive_time_s + error_bound_s)
        if not all(isfinite(value) for value in (nominal, minus, plus)):
            raise TwoWayPredictionError("clock-envelope prediction must be finite")
        envelopes.append(
            ClockEnvelope(
                receive_time_s=receive_time_s,
                error_bound_s=error_bound_s,
                nominal_hz=nominal,
                minus_bound_hz=minus,
                plus_bound_hz=plus,
            )
        )
    return tuple(envelopes)


def _prediction_from_event(
    event: TwoWayEvent,
    ramp: PiecewiseRamp,
    receiver: RsrReceiverTransform,
    *,
    use_geometry: bool,
) -> BasebandPrediction:
    uplink_frequency = ramp.evaluate(event.transmit_time_s)
    uplink_factor = event.uplink_frequency_factor if use_geometry else 1.0
    downlink_factor = event.downlink_frequency_factor if use_geometry else 1.0
    turnaround = (
        uplink_frequency
        * uplink_factor
        * MAVEN_X_BAND_TURNAROUND_NUMERATOR
        / MAVEN_X_BAND_TURNAROUND_DENOMINATOR
    )
    received_sky = turnaround * downlink_factor
    nco = receiver.nco_frequency_hz(event.receive_time_s)
    baseband = receiver.baseband_frequency_hz(event.receive_time_s, received_sky)
    return BasebandPrediction(
        receive_time_s=event.receive_time_s,
        transmit_time_s=event.transmit_time_s,
        uplink_frequency_hz=uplink_frequency,
        spacecraft_turnaround_frequency_hz=turnaround,
        received_sky_frequency_hz=received_sky,
        nco_frequency_hz=nco,
        recorded_baseband_frequency_hz=baseband,
        uplink_light_time_s=event.uplink_light_time_s,
        downlink_light_time_s=event.downlink_light_time_s,
    )


def _frequency_factor(
    transmitter_velocity_m_s: tuple[float, float, float],
    receiver_velocity_m_s: tuple[float, float, float],
    propagation_direction: tuple[float, float, float],
) -> float:
    transmitter_beta = tuple(
        value / SPEED_OF_LIGHT_M_S for value in transmitter_velocity_m_s
    )
    receiver_beta = tuple(
        value / SPEED_OF_LIGHT_M_S for value in receiver_velocity_m_s
    )
    transmitter_gamma = 1.0 / sqrt(1.0 - _dot(transmitter_beta, transmitter_beta))
    receiver_gamma = 1.0 / sqrt(1.0 - _dot(receiver_beta, receiver_beta))
    numerator = receiver_gamma * (
        1.0 - _dot(propagation_direction, receiver_beta)
    )
    denominator = transmitter_gamma * (
        1.0 - _dot(propagation_direction, transmitter_beta)
    )
    factor = numerator / denominator
    if not isfinite(factor) or factor <= 0.0:
        raise TwoWayPredictionError("one-way frequency factor is invalid")
    return factor


def _validated_state(state: StateVector) -> StateVector:
    state.validate()
    return state


def _distance(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return _norm(tuple(r - l for l, r in zip(left, right)))


def _unit_direction(
    origin: tuple[float, float, float],
    destination: tuple[float, float, float],
) -> tuple[float, float, float]:
    delta = tuple(d - o for o, d in zip(origin, destination))
    length = _norm(delta)
    if length <= 0.0:
        raise TwoWayPredictionError("link endpoints must not be colocated")
    return tuple(value / length for value in delta)  # type: ignore[return-value]


def _dot(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
) -> float:
    return sum(l * r for l, r in zip(left, right))


def _norm(vector: tuple[float, float, float]) -> float:
    return sqrt(_dot(vector, vector))
