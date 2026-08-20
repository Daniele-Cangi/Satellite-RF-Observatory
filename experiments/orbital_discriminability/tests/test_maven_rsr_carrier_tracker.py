"""Offline tests for the frozen model-blind DSS-45 carrier tracker."""

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import maven_rsr_carrier_tracker as tracker


def _receiver() -> tracker.FrozenReceiverConfiguration:
    return tracker.FrozenReceiverConfiguration(
        development_lidvid="development-fixture",
        first_sample_utc="2016-07-12T12:42:01.000000Z",
        record_count=20,
        first_record_sequence=1,
        last_record_sequence=20,
        record_duration_s=1.0,
        sequence_continuous=True,
        timestamp_continuous=True,
        station_id=45,
        rsr_id=2,
        subchannel_id=1,
        sample_rate_hz=1_000,
        sample_resolution_bits=16,
        sample_encoding="signed_int16_msb_Q_then_I",
        complex_convention="I_plus_jQ",
        filter_coefficient_state="NOT_ENCODED_IN_SFDU",
        fir_treatment="no inference and no amplitude-response claim",
    )


def _parameters(**changes: object) -> tracker.CarrierTrackerParameters:
    return replace(tracker.PARAMETERS, minimum_contiguous_frames=5, **changes)


def _samples(
    *,
    duration_s: int = 16,
    frequency_hz: float = 35.0,
    slew_hz_s: float = 0.05,
    amplitude: float = 4_000.0,
    second_frequency_hz: float | None = None,
    second_amplitude: float = 0.0,
) -> np.ndarray:
    rng = np.random.default_rng(20442)
    count = duration_s * 1_000
    time_s = np.arange(count, dtype=np.float64) / 1_000.0
    phase = 2.0 * np.pi * (frequency_hz * time_s + 0.5 * slew_hz_s * time_s**2)
    values = amplitude * np.exp(1j * phase)
    if second_frequency_hz is not None:
        values += second_amplitude * np.exp(2j * np.pi * second_frequency_hz * time_s)
    noise = 50.0 * (rng.standard_normal(count) + 1j * rng.standard_normal(count))
    return np.asarray(values + noise, dtype=np.complex64)


def _run(
    samples: np.ndarray,
    parameters: tracker.CarrierTrackerParameters | None = None,
) -> tracker.CarrierTrackerResult:
    return tracker.track_narrowband_carrier(
        samples,
        1_000,
        tracker.RecordedBasebandCoordinates(),
        _receiver(),
        parameters or _parameters(),
    )


def test_frozen_parameters_bind_resolution_overlap_and_time_reference() -> None:
    parameters = tracker.PARAMETERS
    parameters.validate()
    assert parameters.native_bin_spacing_hz == 0.244140625
    assert parameters.effective_frequency_resolution_hz == 0.3662109375
    assert parameters.stft_hop_samples == 1_000
    assert parameters.frame_first_offset_s == 2.0475
    assert tracker.parameter_manifest(parameters)["overlap_samples"] == 3_096


def test_model_blind_chirp_is_admitted() -> None:
    result = _run(_samples())
    assert result.status == "CARRIER_ADMITTED"
    segment = result.selected_segment
    assert segment is not None
    assert len(segment.points) >= 5
    assert all(30.0 <= point.baseband_frequency_hz <= 45.0 for point in segment.points)
    assert not result.orbital_model_input_used


def test_noise_is_not_admitted() -> None:
    rng = np.random.default_rng(39378)
    noise = 100.0 * (
        rng.standard_normal(16_000) + 1j * rng.standard_normal(16_000)
    )
    assert _run(np.asarray(noise, dtype=np.complex64)).status == "CARRIER_NOT_ADMITTED"


def test_comparable_second_carrier_is_ambiguous() -> None:
    result = _run(
        _samples(
            slew_hz_s=0.0,
            second_frequency_hz=120.0,
            second_amplitude=3_800.0,
        )
    )
    assert result.status == "CARRIER_NOT_ADMITTED"
    assert result.ambiguous_frame_count == result.complete_frame_count


def test_excess_slew_cannot_form_an_admitted_run() -> None:
    result = _run(_samples(slew_hz_s=3.0))
    assert result.status == "CARRIER_NOT_ADMITTED"
    assert all(len(segment.points) < 5 for segment in result.segments)


def test_clipping_invalidates_measurement() -> None:
    clipped = np.full(16_000, 32767.0 + 32767.0j, dtype=np.complex64)
    result = _run(clipped)
    assert result.status == "MEASUREMENT_INVALID"
    assert result.clipped_scalar_fraction == 1.0


def test_passband_edge_feature_is_rejected() -> None:
    result = _run(_samples(frequency_hz=480.0, slew_hz_s=0.0))
    assert result.status == "CARRIER_NOT_ADMITTED"
    assert result.edge_frame_count == result.complete_frame_count


def test_gap_and_reordering_are_never_hidden() -> None:
    tags = tuple(f"2016-07-12T12:42:{second:02d}.000000Z" for second in range(1, 4))
    tracker._validate_record_continuity((1, 2, 3), tags, record_duration_s=1.0)
    with pytest.raises(tracker.CarrierTrackerError, match="sequence gap"):
        tracker._validate_record_continuity((1, 3, 4), tags, record_duration_s=1.0)
    with pytest.raises(tracker.CarrierTrackerError, match="timestamp gap"):
        tracker._validate_record_continuity(
            (1, 2, 3),
            (tags[0], tags[1], "2016-07-12T12:42:04.000000Z"),
            record_duration_s=1.0,
        )


def test_tracker_source_has_no_prediction_dependency_or_curve() -> None:
    source = Path(tracker.__file__).read_text(encoding="utf-8")
    forbidden = (
        "maven_dsn_two_way",
        "MAVEN_DSS45_METADATA_RESULT",
        "spiceypy",
        "27.398",
        "50.809",
    )
    assert all(token not in source for token in forbidden)
