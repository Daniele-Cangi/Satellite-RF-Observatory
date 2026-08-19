"""Offline tests for the scoped, model-blind RSP-03 ridge extractor."""

from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import rsp03_ridge_detector as detector


def _broad_component_power(
    *,
    centers_hz: tuple[float, ...],
    widths_hz: tuple[float, ...],
    amplitudes: tuple[float, ...],
) -> tuple[np.ndarray, np.ndarray]:
    parameters = detector.PARAMETERS
    rf = np.arange(
        parameters.channel_low_rf_hz,
        parameters.channel_high_rf_hz + parameters.native_frequency_resolution_hz,
        parameters.native_frequency_resolution_hz,
    )
    power = np.ones(rf.size, dtype=np.float64)
    for center, width, amplitude in zip(centers_hz, widths_hz, amplitudes, strict=True):
        power[np.abs(rf - center) <= width / 2.0] += amplitude
    return power, rf


def test_parameters_freeze_native_and_effective_resolution() -> None:
    parameters = detector.PARAMETERS
    parameters.validate()
    assert parameters.decimation_factor == 1
    assert parameters.stft_window == "periodic_hann"
    assert parameters.stft_length_samples == 125_000
    assert parameters.stft_hop_samples == 125_000
    assert parameters.stft_subwindows_per_frame == 8
    assert parameters.native_frequency_resolution_hz == 8.0
    assert parameters.effective_frequency_resolution_hz == 250.0


def test_broad_component_wins_over_narrow_interferer_without_orbit() -> None:
    power, rf = _broad_component_power(
        centers_hz=(437_058_000.0, 437_050_000.0),
        widths_hz=(8_000.0, 500.0),
        amplitudes=(30.0, 200.0),
    )
    candidate, ambiguous = detector._candidate_from_power(
        power,
        rf,
        frame_index=4,
        event_time_offset_s=4.5,
        parameters=detector.PARAMETERS,
    )
    assert not ambiguous
    assert candidate is not None
    assert candidate.rf_frequency_hz == pytest.approx(437_058_000.0, abs=250.0)
    assert candidate.occupied_bandwidth_hz >= 5_000.0


def test_two_comparable_broad_components_are_ambiguous() -> None:
    power, rf = _broad_component_power(
        centers_hz=(437_035_000.0, 437_065_000.0),
        widths_hz=(6_000.0, 6_000.0),
        amplitudes=(30.0, 28.0),
    )
    candidate, ambiguous = detector._candidate_from_power(
        power,
        rf,
        frame_index=1,
        event_time_offset_s=1.5,
        parameters=detector.PARAMETERS,
    )
    assert candidate is None
    assert ambiguous


def test_continuity_splits_large_slew_and_never_interpolates_gap() -> None:
    parameters = detector.PARAMETERS
    candidates = [
        detector._Candidate(i, i + 0.5, 437_060_000.0 - i * 250.0, 8_000.0, 10.0, 50.0)
        for i in range(12)
    ]
    candidates.extend(
        detector._Candidate(i, i + 0.5, 437_040_000.0, 8_000.0, 10.0, 50.0)
        for i in range(15, 27)
    )
    segments = detector._continuous_segments(candidates, parameters)
    assert tuple(len(segment.points) for segment in segments) == (12, 12)
    assert segments[0].points[-1].frame_index == 11
    assert segments[1].points[0].frame_index == 15


def test_materialized_length_is_checked_before_memmap() -> None:
    with pytest.raises(detector.DetectorInputError, match="complete artifact length"):
        detector._validate_artifact_byte_count(12, 16, 4)


def test_detector_source_has_no_orbital_model_dependency() -> None:
    source = Path(detector.__file__).read_text(encoding="utf-8")
    forbidden = ("TLEElements", "compute_orbital_state", "trajectory.py", "skyfield")
    assert all(token not in source for token in forbidden)
