"""Model-blind ridge extractor developed only on the RSP-03 2026-02-08 IQ.

The extractor consumes sample format, sample rate, RF center and frozen signal
processing parameters.  It has no orbital-element or trajectory input and does
not select a feature by proximity to an orbital prediction.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, log10
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.signal.windows import hann


class DetectorInputError(ValueError):
    """Raised before feature extraction when the materialized IQ is invalid."""


@dataclass(frozen=True, slots=True)
class RSP03DetectorParameters:
    sample_rate_hz: int = 1_000_000
    recording_center_hz: int = 436_950_000
    nominal_carrier_hz: int = 437_050_000
    datatype: str = "ci16_le"
    bytes_per_complex_sample: int = 4
    channel_low_rf_hz: int = 437_015_000
    channel_high_rf_hz: int = 437_085_000
    decimation_factor: int = 1
    stft_window: str = "periodic_hann"
    stft_length_samples: int = 125_000
    stft_hop_samples: int = 125_000
    stft_subwindows_per_frame: int = 8
    output_frame_samples: int = 1_000_000
    output_frame_time_reference: str = "center_sample"
    frequency_smoothing_bins: int = 31
    background_estimator: str = "channel_linear_power_median"
    component_threshold_db: float = 5.0
    binary_closing_bins: int = 65
    minimum_component_width_hz: float = 5_000.0
    maximum_component_width_hz: float = 30_000.0
    channel_edge_guard_hz: float = 2_000.0
    minimum_integrated_snr_db: float = 7.5
    ambiguity_score_ratio: float = 0.5
    ridge_quantization_hz: float = 250.0
    maximum_slew_hz_s: float = 500.0
    maximum_gap_frames: int = 2
    minimum_segment_points: int = 10
    minimum_total_points: int = 120
    minimum_coverage_fraction: float = 0.25
    maximum_clipped_scalar_fraction: float = 0.0001

    @property
    def native_frequency_resolution_hz(self) -> float:
        return self.sample_rate_hz / self.stft_length_samples

    @property
    def effective_frequency_resolution_hz(self) -> float:
        return self.ridge_quantization_hz

    @property
    def output_frame_duration_s(self) -> float:
        return self.output_frame_samples / self.sample_rate_hz

    def validate(self) -> None:
        if self.datatype != "ci16_le" or self.bytes_per_complex_sample != 4:
            raise DetectorInputError("the frozen detector accepts only ci16_le")
        if self.sample_rate_hz != 1_000_000:
            raise DetectorInputError("the frozen detector accepts only 1 Msps")
        if self.decimation_factor != 1:
            raise DetectorInputError("the frozen detector has no resampling stage")
        if self.stft_window != "periodic_hann":
            raise DetectorInputError("the frozen analysis window changed")
        if self.stft_hop_samples != self.stft_length_samples:
            raise DetectorInputError("the frozen STFT subwindows must not overlap")
        if self.stft_length_samples * self.stft_subwindows_per_frame != (
            self.output_frame_samples
        ):
            raise DetectorInputError("STFT subwindows must exactly cover each frame")
        if self.output_frame_time_reference != "center_sample":
            raise DetectorInputError("frame timing convention changed")
        positive = (
            self.component_threshold_db,
            self.minimum_component_width_hz,
            self.maximum_component_width_hz,
            self.channel_edge_guard_hz,
            self.minimum_integrated_snr_db,
            self.ambiguity_score_ratio,
            self.ridge_quantization_hz,
            self.maximum_slew_hz_s,
            self.minimum_coverage_fraction,
        )
        if not all(isfinite(value) and value > 0.0 for value in positive):
            raise DetectorInputError("detector thresholds must be finite and positive")
        if not 0.0 < self.ambiguity_score_ratio <= 1.0:
            raise DetectorInputError("ambiguity ratio must be in (0, 1]")
        if not 0.0 < self.minimum_coverage_fraction <= 1.0:
            raise DetectorInputError("coverage fraction must be in (0, 1]")
        if not 0.0 <= self.maximum_clipped_scalar_fraction < 1.0:
            raise DetectorInputError("clipping fraction must be in [0, 1)")
        if min(
            self.frequency_smoothing_bins,
            self.binary_closing_bins,
            self.minimum_segment_points,
            self.minimum_total_points,
        ) < 1:
            raise DetectorInputError("detector counts must be positive")
        if self.maximum_gap_frames < 0:
            raise DetectorInputError("gap allowance must be non-negative")


@dataclass(frozen=True, slots=True)
class RidgePoint:
    frame_index: int
    event_time_offset_s: float
    rf_frequency_hz: float
    occupied_bandwidth_hz: float
    integrated_snr_db: float
    excess_score: float


@dataclass(frozen=True, slots=True)
class RidgeSegment:
    points: tuple[RidgePoint, ...]

    @property
    def duration_s(self) -> float:
        if len(self.points) < 2:
            return 0.0
        return self.points[-1].event_time_offset_s - self.points[0].event_time_offset_s


@dataclass(frozen=True, slots=True)
class DetectorResult:
    status: str
    statement: str
    sample_count: int
    complete_frame_count: int
    trailing_sample_count: int
    candidate_frame_count: int
    ambiguous_frame_count: int
    clipped_frame_count: int
    clipped_scalar_fraction: float
    admitted_point_count: int
    admitted_coverage_fraction: float
    segments: tuple[RidgeSegment, ...]
    gap_observability: str = "RAW_SIGMF_HAS_NO_PACKET_SEQUENCE_METADATA"
    orbital_model_input_used: bool = False


@dataclass(frozen=True, slots=True)
class _Candidate:
    frame_index: int
    event_time_offset_s: float
    rf_frequency_hz: float
    occupied_bandwidth_hz: float
    integrated_snr_db: float
    excess_score: float


PARAMETERS = RSP03DetectorParameters()


def extract_development_file(
    path: str | Path,
    *,
    expected_bytes: int,
    parameters: RSP03DetectorParameters = PARAMETERS,
) -> DetectorResult:
    """Extract the frozen broad-band ridge without any orbital input."""

    parameters.validate()
    artifact = Path(path)
    actual_bytes = artifact.stat().st_size
    _validate_artifact_byte_count(
        actual_bytes,
        expected_bytes,
        parameters.bytes_per_complex_sample,
    )
    raw = np.memmap(artifact, dtype="<i2", mode="r")
    if raw.size % 2:
        raise DetectorInputError("artifact contains an odd number of int16 scalars")
    return _extract_memmap(raw, parameters)


def _validate_artifact_byte_count(
    actual_bytes: int,
    expected_bytes: int,
    bytes_per_complex_sample: int,
) -> None:
    if actual_bytes != expected_bytes:
        raise DetectorInputError(
            f"complete artifact length {actual_bytes} does not match {expected_bytes}"
        )
    if actual_bytes % bytes_per_complex_sample:
        raise DetectorInputError("artifact ends inside one ci16_le complex sample")


def _extract_memmap(
    raw: np.memmap,
    parameters: RSP03DetectorParameters,
) -> DetectorResult:
    sample_count = raw.size // 2
    frame_samples = parameters.output_frame_samples
    frame_count = sample_count // frame_samples
    trailing_samples = sample_count - frame_count * frame_samples
    if frame_count < 1:
        raise DetectorInputError("artifact contains no complete analysis frame")

    window = hann(parameters.stft_length_samples, sym=False).astype(np.float32)
    offsets = np.fft.fftfreq(
        parameters.stft_length_samples,
        d=1.0 / parameters.sample_rate_hz,
    )
    rf_axis = parameters.recording_center_hz + offsets
    channel_indices = np.flatnonzero(
        (rf_axis >= parameters.channel_low_rf_hz)
        & (rf_axis <= parameters.channel_high_rf_hz)
    )
    channel_rf = rf_axis[channel_indices]
    if channel_indices.size < 3:
        raise DetectorInputError("frozen channel contains fewer than three FFT bins")

    candidates: list[_Candidate] = []
    ambiguous_frames = 0
    clipped_frames = 0
    clipped_scalars = 0
    total_scalars = raw.size
    int16_min = np.iinfo(np.int16).min
    int16_max = np.iinfo(np.int16).max

    for frame_index in range(frame_count):
        frame_start = frame_index * frame_samples
        scalar_start = 2 * frame_start
        scalar_stop = scalar_start + 2 * frame_samples
        frame_scalars = raw[scalar_start:scalar_stop]
        frame_clipped = int(
            np.count_nonzero(
                (frame_scalars == int16_min) | (frame_scalars == int16_max)
            )
        )
        clipped_scalars += frame_clipped
        frame_clipped_fraction = frame_clipped / frame_scalars.size
        if frame_clipped_fraction > parameters.maximum_clipped_scalar_fraction:
            clipped_frames += 1
            continue

        power = np.zeros(channel_indices.size, dtype=np.float64)
        for subwindow_index in range(parameters.stft_subwindows_per_frame):
            sample_start = (
                frame_start + subwindow_index * parameters.stft_hop_samples
            )
            scalars = np.asarray(
                raw[
                    2 * sample_start : 2
                    * (sample_start + parameters.stft_length_samples)
                ],
                dtype=np.float32,
            ).reshape(-1, 2)
            complex_samples = (scalars[:, 0] + 1j * scalars[:, 1]) * window
            spectrum = np.fft.fft(complex_samples)
            power += np.square(np.abs(spectrum[channel_indices]))
        power /= parameters.stft_subwindows_per_frame

        frame_time = (
            frame_start + parameters.output_frame_samples / 2
        ) / parameters.sample_rate_hz
        candidate, ambiguous = _candidate_from_power(
            power,
            channel_rf,
            frame_index=frame_index,
            event_time_offset_s=frame_time,
            parameters=parameters,
        )
        if ambiguous:
            ambiguous_frames += 1
        elif candidate is not None:
            candidates.append(candidate)

    if trailing_samples:
        trailing = raw[2 * frame_count * frame_samples :]
        clipped_scalars += int(
            np.count_nonzero((trailing == int16_min) | (trailing == int16_max))
        )
    clipped_fraction = clipped_scalars / total_scalars
    if clipped_fraction > parameters.maximum_clipped_scalar_fraction:
        return DetectorResult(
            status="MEASUREMENT_INVALID",
            statement="clipped scalar fraction exceeds the frozen limit",
            sample_count=sample_count,
            complete_frame_count=frame_count,
            trailing_sample_count=trailing_samples,
            candidate_frame_count=len(candidates),
            ambiguous_frame_count=ambiguous_frames,
            clipped_frame_count=clipped_frames,
            clipped_scalar_fraction=clipped_fraction,
            admitted_point_count=0,
            admitted_coverage_fraction=0.0,
            segments=(),
        )

    segments = _continuous_segments(candidates, parameters)
    admitted_count = sum(len(segment.points) for segment in segments)
    coverage = admitted_count / frame_count
    admitted = (
        admitted_count >= parameters.minimum_total_points
        and coverage >= parameters.minimum_coverage_fraction
    )
    return DetectorResult(
        status="RIDGE_ADMITTED" if admitted else "RIDGE_NOT_ADMITTED",
        statement=(
            "one model-blind broad-band ridge family clears the frozen rules"
            if admitted
            else "the frozen broad-band ridge rules do not admit enough points"
        ),
        sample_count=sample_count,
        complete_frame_count=frame_count,
        trailing_sample_count=trailing_samples,
        candidate_frame_count=len(candidates),
        ambiguous_frame_count=ambiguous_frames,
        clipped_frame_count=clipped_frames,
        clipped_scalar_fraction=clipped_fraction,
        admitted_point_count=admitted_count,
        admitted_coverage_fraction=coverage,
        segments=segments,
    )


def _candidate_from_power(
    power: np.ndarray,
    channel_rf_hz: np.ndarray,
    *,
    frame_index: int,
    event_time_offset_s: float,
    parameters: RSP03DetectorParameters,
) -> tuple[_Candidate | None, bool]:
    if power.ndim != 1 or channel_rf_hz.shape != power.shape:
        raise DetectorInputError("power and RF axis must be equal one-dimensional vectors")
    if not np.all(np.isfinite(power)) or np.any(power < 0.0):
        raise DetectorInputError("frame power must be finite and non-negative")
    background = float(np.median(power))
    if not isfinite(background) or background <= 0.0:
        return None, False
    relative_db = 10.0 * np.log10(np.maximum(power / background, 1e-30))
    smoothed_db = ndimage.uniform_filter1d(
        relative_db.astype(np.float32),
        size=parameters.frequency_smoothing_bins,
        mode="nearest",
    )
    occupied = ndimage.binary_closing(
        smoothed_db >= parameters.component_threshold_db,
        structure=np.ones(parameters.binary_closing_bins, dtype=bool),
    )
    labels, label_count = ndimage.label(occupied)
    native_bin_hz = parameters.native_frequency_resolution_hz
    candidates: list[_Candidate] = []
    for label in range(1, label_count + 1):
        indices = np.flatnonzero(labels == label)
        if indices.size == 0:
            continue
        bandwidth = (indices[-1] - indices[0] + 1) * native_bin_hz
        if not (
            parameters.minimum_component_width_hz
            <= bandwidth
            <= parameters.maximum_component_width_hz
        ):
            continue
        if (
            channel_rf_hz[indices[0]] - channel_rf_hz[0]
            < parameters.channel_edge_guard_hz
            or channel_rf_hz[-1] - channel_rf_hz[indices[-1]]
            < parameters.channel_edge_guard_hz
        ):
            continue
        weights = np.maximum(
            relative_db[indices] - parameters.component_threshold_db,
            0.0,
        )
        score = float(np.sum(weights))
        if score <= 0.0:
            continue
        integrated_snr = 10.0 * log10(
            max(float(np.mean(power[indices])) / background, 1e-30)
        )
        if integrated_snr < parameters.minimum_integrated_snr_db:
            continue
        centroid = float(np.sum(channel_rf_hz[indices] * weights) / score)
        quantized = (
            floor(centroid / parameters.ridge_quantization_hz + 0.5)
            * parameters.ridge_quantization_hz
        )
        candidates.append(
            _Candidate(
                frame_index=frame_index,
                event_time_offset_s=event_time_offset_s,
                rf_frequency_hz=quantized,
                occupied_bandwidth_hz=bandwidth,
                integrated_snr_db=integrated_snr,
                excess_score=score,
            )
        )
    candidates.sort(key=lambda item: (-item.excess_score, item.rf_frequency_hz))
    if not candidates:
        return None, False
    ambiguous = (
        len(candidates) > 1
        and candidates[1].excess_score
        >= parameters.ambiguity_score_ratio * candidates[0].excess_score
    )
    return (None, True) if ambiguous else (candidates[0], False)


def _continuous_segments(
    candidates: list[_Candidate],
    parameters: RSP03DetectorParameters,
) -> tuple[RidgeSegment, ...]:
    if not candidates:
        return ()
    ordered = sorted(candidates, key=lambda item: item.frame_index)
    raw_segments: list[list[_Candidate]] = []
    current = [ordered[0]]
    for candidate in ordered[1:]:
        previous = current[-1]
        frame_difference = candidate.frame_index - previous.frame_index
        elapsed = candidate.event_time_offset_s - previous.event_time_offset_s
        gap_frames = frame_difference - 1
        slew = abs(candidate.rf_frequency_hz - previous.rf_frequency_hz) / elapsed
        if gap_frames <= parameters.maximum_gap_frames and slew <= (
            parameters.maximum_slew_hz_s
        ):
            current.append(candidate)
        else:
            raw_segments.append(current)
            current = [candidate]
    raw_segments.append(current)
    return tuple(
        RidgeSegment(
            tuple(
                RidgePoint(
                    frame_index=item.frame_index,
                    event_time_offset_s=item.event_time_offset_s,
                    rf_frequency_hz=item.rf_frequency_hz,
                    occupied_bandwidth_hz=item.occupied_bandwidth_hz,
                    integrated_snr_db=item.integrated_snr_db,
                    excess_score=item.excess_score,
                )
                for item in segment
            )
        )
        for segment in raw_segments
        if len(segment) >= parameters.minimum_segment_points
    )


__all__ = [
    "DetectorInputError",
    "DetectorResult",
    "PARAMETERS",
    "RSP03DetectorParameters",
    "RidgePoint",
    "RidgeSegment",
    "extract_development_file",
]
