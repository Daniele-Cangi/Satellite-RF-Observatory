"""Deterministic, model-blind carrier tracker for the DSS-45 RSR fixture.

The tracking function accepts only recorded complex samples, their sample
rate, recorded-baseband coordinates and the verified receiver configuration.
It has no link-prediction or spacecraft-geometry input.  The artifact loader
hashes the complete file before opening any sample record for decoding.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite, log10
from pathlib import Path
from typing import Final, Literal

import numpy as np

from experiments.orbital_discriminability.maven_rsr_header import (
    DEVELOPMENT_LIDVID,
    RSR_HEADER_BYTES,
    RSR_RECORD_BYTES,
    parse_dss45_header,
)


TRACKER_VERSION: Final = "maven-dss45-model-blind-carrier-tracker-v1"
EXPECTED_RECORDS: Final = 1_080
COMPLEX_SAMPLES_PER_RECORD: Final = 1_000
DATA_BYTES_PER_RECORD: Final = 4_000


class CarrierTrackerError(ValueError):
    """The verified artifact or detector input violates the frozen contract."""


@dataclass(frozen=True, slots=True)
class RecordedBasebandCoordinates:
    center_hz: float = 0.0
    lower_hz: float = -500.0
    upper_hz: float = 500.0
    frequency_sign: str = "positive_fft_frequency_of_I_plus_jQ"


@dataclass(frozen=True, slots=True)
class FrozenReceiverConfiguration:
    development_lidvid: str
    first_sample_utc: str
    record_count: int
    first_record_sequence: int
    last_record_sequence: int
    record_duration_s: float
    sequence_continuous: bool
    timestamp_continuous: bool
    station_id: int
    rsr_id: int
    subchannel_id: int
    sample_rate_hz: int
    sample_resolution_bits: int
    sample_encoding: str
    complex_convention: str
    filter_coefficient_state: str
    fir_treatment: str


@dataclass(frozen=True, slots=True)
class VerifiedDevelopmentArtifact:
    samples: np.ndarray
    sample_rate_hz: int
    baseband: RecordedBasebandCoordinates
    receiver: FrozenReceiverConfiguration
    artifact_sha256: str
    artifact_bytes: int
    clipped_scalar_count: int


@dataclass(frozen=True, slots=True)
class CarrierTrackerParameters:
    expected_sample_rate_hz: int = 1_000
    sample_encoding: str = "signed_int16_msb_Q_then_I"
    complex_convention: str = "I_plus_jQ"
    stft_window: str = "periodic_hann"
    stft_length_samples: int = 4_096
    stft_hop_samples: int = 1_000
    zero_padding_samples: int = 0
    frame_time_reference: str = "midpoint_of_first_and_last_sample_timestamps"
    passband_edge_guard_hz: float = 50.0
    local_background_half_width_hz: float = 50.0
    candidate_exclusion_half_width_hz: float = 2.0
    minimum_peak_snr_db: float = 20.0
    minimum_ambiguity_margin_db: float = 10.0
    maximum_slew_hz_s: float = 1.0
    maximum_gap_frames: int = 0
    minimum_contiguous_frames: int = 30
    maximum_clipped_scalar_fraction: float = 0.0001
    frequency_estimator: str = "strongest_native_fft_bin_no_subbin_fit"
    background_estimator: str = "local_median_linear_power"
    unknown_fir_policy: str = (
        "no_coefficient_inference; no_amplitude_response_claim; use_interior_band_only"
    )

    @property
    def native_bin_spacing_hz(self) -> float:
        return self.expected_sample_rate_hz / self.stft_length_samples

    @property
    def effective_frequency_resolution_hz(self) -> float:
        # Equivalent-noise bandwidth of a periodic Hann window.
        return 1.5 * self.native_bin_spacing_hz

    @property
    def frame_hop_s(self) -> float:
        return self.stft_hop_samples / self.expected_sample_rate_hz

    @property
    def frame_first_offset_s(self) -> float:
        return (self.stft_length_samples - 1) / (
            2.0 * self.expected_sample_rate_hz
        )

    def validate(self) -> None:
        if self.expected_sample_rate_hz != 1_000:
            raise CarrierTrackerError("the frozen detector accepts only 1 ksps")
        if self.sample_encoding != "signed_int16_msb_Q_then_I":
            raise CarrierTrackerError("the frozen sample packing changed")
        if self.complex_convention != "I_plus_jQ":
            raise CarrierTrackerError("the frozen complex convention changed")
        if self.stft_window != "periodic_hann":
            raise CarrierTrackerError("the frozen window changed")
        if self.zero_padding_samples != 0:
            raise CarrierTrackerError("the frozen detector does not zero-pad")
        if self.frame_time_reference != (
            "midpoint_of_first_and_last_sample_timestamps"
        ):
            raise CarrierTrackerError("the frame-time convention changed")
        if self.frequency_estimator != "strongest_native_fft_bin_no_subbin_fit":
            raise CarrierTrackerError("the frozen frequency estimator changed")
        if self.background_estimator != "local_median_linear_power":
            raise CarrierTrackerError("the frozen background estimator changed")
        if self.maximum_gap_frames != 0:
            raise CarrierTrackerError("the frozen tracker never bridges a gap")
        if self.minimum_contiguous_frames < 2:
            raise CarrierTrackerError("minimum run length must be at least two")
        if self.stft_length_samples < 4 or self.stft_hop_samples < 1:
            raise CarrierTrackerError("invalid STFT geometry")
        positive = (
            self.passband_edge_guard_hz,
            self.local_background_half_width_hz,
            self.candidate_exclusion_half_width_hz,
            self.minimum_peak_snr_db,
            self.minimum_ambiguity_margin_db,
            self.maximum_slew_hz_s,
        )
        if not all(isfinite(value) and value > 0.0 for value in positive):
            raise CarrierTrackerError("detector bounds must be finite and positive")
        if not 0.0 <= self.maximum_clipped_scalar_fraction < 1.0:
            raise CarrierTrackerError("clipping fraction must be in [0, 1)")


@dataclass(frozen=True, slots=True)
class CarrierPoint:
    frame_index: int
    event_time_offset_s: float
    baseband_frequency_hz: float
    peak_snr_db: float
    ambiguity_margin_db: float


@dataclass(frozen=True, slots=True)
class CarrierSegment:
    points: tuple[CarrierPoint, ...]

    @property
    def duration_s(self) -> float:
        if len(self.points) < 2:
            return 0.0
        return self.points[-1].event_time_offset_s - self.points[0].event_time_offset_s


@dataclass(frozen=True, slots=True)
class CarrierTrackerResult:
    status: Literal["CARRIER_ADMITTED", "CARRIER_NOT_ADMITTED", "MEASUREMENT_INVALID"]
    statement: str
    sample_count: int
    complete_frame_count: int
    admitted_frame_count: int
    below_snr_frame_count: int
    ambiguous_frame_count: int
    edge_frame_count: int
    clipped_frame_count: int
    clipped_scalar_fraction: float
    segments: tuple[CarrierSegment, ...]
    selected_segment_index: int | None
    orbital_model_input_used: bool = False
    gap_policy: str = "split_immediately_never_interpolate"

    @property
    def selected_segment(self) -> CarrierSegment | None:
        if self.selected_segment_index is None:
            return None
        return self.segments[self.selected_segment_index]


@dataclass(frozen=True, slots=True)
class _FrameCandidate:
    point: CarrierPoint | None
    rejection: Literal["NONE", "SNR", "AMBIGUOUS", "EDGE", "CLIPPED"]


PARAMETERS = CarrierTrackerParameters()


def verify_and_decode_development_artifact(
    artifact_path: str | Path,
    authority_path: str | Path,
) -> VerifiedDevelopmentArtifact:
    """Hash the complete authorized file, then and only then decode samples."""

    artifact = Path(artifact_path)
    authority = _read_authority(Path(authority_path))
    expected = authority["development_product"]["payload"]
    if artifact.name != expected["filename"]:
        raise CarrierTrackerError("artifact filename differs from frozen identity")
    actual_bytes = artifact.stat().st_size
    if actual_bytes != expected["bytes"]:
        raise CarrierTrackerError("complete artifact byte count differs from authority")
    actual_sha256 = _file_sha256(artifact)
    if actual_sha256 != expected["sha256"]:
        raise CarrierTrackerError("complete artifact SHA-256 differs from authority")

    # This is the first sample access in this function.  Identity, length and
    # complete-file SHA-256 have already succeeded.
    raw_file = artifact.read_bytes()
    if len(raw_file) % RSR_RECORD_BYTES:
        raise CarrierTrackerError("artifact ends inside an RSR record")
    record_count = len(raw_file) // RSR_RECORD_BYTES
    if record_count != EXPECTED_RECORDS:
        raise CarrierTrackerError("artifact does not contain the frozen record count")

    samples = np.empty(record_count * COMPLEX_SAMPLES_PER_RECORD, dtype=np.complex64)
    receipts = []
    clipped_scalars = 0
    int16_min = np.iinfo(np.int16).min
    int16_max = np.iinfo(np.int16).max
    for record_index in range(record_count):
        start = record_index * RSR_RECORD_BYTES
        record = memoryview(raw_file)[start : start + RSR_RECORD_BYTES]
        receipt = parse_dss45_header(record[:RSR_HEADER_BYTES])
        receipts.append(receipt)
        encoded = np.frombuffer(
            record,
            dtype=">i2",
            count=2 * COMPLEX_SAMPLES_PER_RECORD,
            offset=RSR_HEADER_BYTES,
        ).reshape(COMPLEX_SAMPLES_PER_RECORD, 2)
        if encoded.nbytes != DATA_BYTES_PER_RECORD:
            raise CarrierTrackerError("record has an unexpected sample payload length")
        clipped_scalars += int(
            np.count_nonzero((encoded == int16_min) | (encoded == int16_max))
        )
        q = encoded[:, 0].astype(np.float32)
        i = encoded[:, 1].astype(np.float32)
        sample_start = record_index * COMPLEX_SAMPLES_PER_RECORD
        samples[sample_start : sample_start + COMPLEX_SAMPLES_PER_RECORD] = i + 1j * q

    _validate_record_continuity(
        tuple(receipt.record_sequence_number for receipt in receipts),
        tuple(receipt.first_sample_utc for receipt in receipts),
        record_duration_s=1.0,
    )
    first = receipts[0]
    invariant_fields = (
        "deep_space_station_id",
        "rsr_id",
        "subchannel_id",
        "sample_rate_hz",
        "sample_resolution_bits",
    )
    for receipt in receipts[1:]:
        if any(getattr(receipt, name) != getattr(first, name) for name in invariant_fields):
            raise CarrierTrackerError("receiver configuration changed inside artifact")

    samples.flags.writeable = False
    baseband = RecordedBasebandCoordinates(
        center_hz=0.0,
        lower_hz=-first.sample_rate_hz / 2.0,
        upper_hz=first.sample_rate_hz / 2.0,
    )
    receiver = FrozenReceiverConfiguration(
        development_lidvid=DEVELOPMENT_LIDVID,
        first_sample_utc=first.first_sample_utc,
        record_count=record_count,
        first_record_sequence=receipts[0].record_sequence_number,
        last_record_sequence=receipts[-1].record_sequence_number,
        record_duration_s=1.0,
        sequence_continuous=True,
        timestamp_continuous=True,
        station_id=first.deep_space_station_id,
        rsr_id=first.rsr_id,
        subchannel_id=first.subchannel_id,
        sample_rate_hz=first.sample_rate_hz,
        sample_resolution_bits=first.sample_resolution_bits,
        sample_encoding="signed_int16_msb_Q_then_I",
        complex_convention="I_plus_jQ",
        filter_coefficient_state=first.filter_decimation.coefficient_state,
        fir_treatment=(
            "coefficients_not_encoded; no inference; no amplitude-response claim"
        ),
    )
    return VerifiedDevelopmentArtifact(
        samples=samples,
        sample_rate_hz=first.sample_rate_hz,
        baseband=baseband,
        receiver=receiver,
        artifact_sha256=actual_sha256,
        artifact_bytes=actual_bytes,
        clipped_scalar_count=clipped_scalars,
    )


def track_narrowband_carrier(
    samples: np.ndarray,
    sample_rate_hz: int,
    baseband: RecordedBasebandCoordinates,
    receiver: FrozenReceiverConfiguration,
    parameters: CarrierTrackerParameters = PARAMETERS,
) -> CarrierTrackerResult:
    """Track one narrowband carrier without a physical or orbital prediction."""

    parameters.validate()
    values = np.asarray(samples)
    _validate_detector_inputs(values, sample_rate_hz, baseband, receiver, parameters)
    if values.size < parameters.stft_length_samples:
        raise CarrierTrackerError("samples contain no complete analysis frame")

    frame_count = 1 + (
        values.size - parameters.stft_length_samples
    ) // parameters.stft_hop_samples
    window = np.hanning(parameters.stft_length_samples + 1)[:-1]
    frequency_axis = baseband.center_hz + np.fft.fftshift(
        np.fft.fftfreq(parameters.stft_length_samples, d=1.0 / sample_rate_hz)
    )
    candidates: list[CarrierPoint] = []
    below_snr = ambiguous = edge = clipped = 0
    total_clipped_scalars = _clipped_scalar_count(values)

    for frame_index in range(frame_count):
        sample_start = frame_index * parameters.stft_hop_samples
        frame = values[sample_start : sample_start + parameters.stft_length_samples]
        frame_time = (
            sample_start + (parameters.stft_length_samples - 1) / 2.0
        ) / sample_rate_hz
        outcome = _candidate_from_frame(
            frame,
            frequency_axis,
            event_time_offset_s=frame_time,
            frame_index=frame_index,
            baseband=baseband,
            parameters=parameters,
        )
        if outcome.point is not None:
            candidates.append(outcome.point)
        elif outcome.rejection == "SNR":
            below_snr += 1
        elif outcome.rejection == "AMBIGUOUS":
            ambiguous += 1
        elif outcome.rejection == "EDGE":
            edge += 1
        elif outcome.rejection == "CLIPPED":
            clipped += 1

    clipped_fraction = total_clipped_scalars / (2.0 * values.size)
    if clipped_fraction > parameters.maximum_clipped_scalar_fraction:
        return CarrierTrackerResult(
            status="MEASUREMENT_INVALID",
            statement="clipped scalar fraction exceeds the frozen whole-artifact limit",
            sample_count=int(values.size),
            complete_frame_count=frame_count,
            admitted_frame_count=0,
            below_snr_frame_count=below_snr,
            ambiguous_frame_count=ambiguous,
            edge_frame_count=edge,
            clipped_frame_count=clipped,
            clipped_scalar_fraction=clipped_fraction,
            segments=(),
            selected_segment_index=None,
        )

    segments = _continuous_segments(candidates, parameters)
    selected_index = _select_segment(segments, parameters.minimum_contiguous_frames)
    return CarrierTrackerResult(
        status="CARRIER_ADMITTED" if selected_index is not None else "CARRIER_NOT_ADMITTED",
        statement=(
            "one model-blind narrowband carrier clears all frozen rules"
            if selected_index is not None
            else "no carrier run clears all frozen admission rules"
        ),
        sample_count=int(values.size),
        complete_frame_count=frame_count,
        admitted_frame_count=len(candidates),
        below_snr_frame_count=below_snr,
        ambiguous_frame_count=ambiguous,
        edge_frame_count=edge,
        clipped_frame_count=clipped,
        clipped_scalar_fraction=clipped_fraction,
        segments=segments,
        selected_segment_index=selected_index,
    )


def development_result_object(
    artifact: VerifiedDevelopmentArtifact,
    result: CarrierTrackerResult,
    parameters: CarrierTrackerParameters = PARAMETERS,
) -> dict[str, object]:
    selected = result.selected_segment
    return {
        "result_version": "maven-dss45-detector-development-result-v1",
        "scope": "DSS45_DEVELOPMENT_ONLY_MODEL_BLIND",
        "tracker_version": TRACKER_VERSION,
        "development_artifact": {
            "bytes": artifact.artifact_bytes,
            "sha256": artifact.artifact_sha256,
        },
        "receiver_configuration": asdict(artifact.receiver),
        "recorded_baseband_coordinates": asdict(artifact.baseband),
        "parameters": parameter_manifest(parameters),
        "measurement": {
            "status": result.status,
            "statement": result.statement,
            "sample_count": result.sample_count,
            "complete_frame_count": result.complete_frame_count,
            "admitted_frame_count": result.admitted_frame_count,
            "below_snr_frame_count": result.below_snr_frame_count,
            "ambiguous_frame_count": result.ambiguous_frame_count,
            "edge_frame_count": result.edge_frame_count,
            "clipped_frame_count": result.clipped_frame_count,
            "clipped_scalar_fraction": result.clipped_scalar_fraction,
            "segment_lengths": [len(segment.points) for segment in result.segments],
            "selected_segment_index": result.selected_segment_index,
            "selected_segment": None if selected is None else {
                "point_count": len(selected.points),
                "duration_s": selected.duration_s,
                "first_event_time_offset_s": selected.points[0].event_time_offset_s,
                "last_event_time_offset_s": selected.points[-1].event_time_offset_s,
                "minimum_baseband_frequency_hz": min(
                    point.baseband_frequency_hz for point in selected.points
                ),
                "maximum_baseband_frequency_hz": max(
                    point.baseband_frequency_hz for point in selected.points
                ),
                "minimum_peak_snr_db": min(point.peak_snr_db for point in selected.points),
                "minimum_ambiguity_margin_db": min(
                    point.ambiguity_margin_db for point in selected.points
                ),
                "maximum_observed_slew_hz_s": _maximum_slew(selected.points),
                "points": [asdict(point) for point in selected.points],
            },
            "orbital_model_input_used": result.orbital_model_input_used,
            "gap_policy": result.gap_policy,
        },
        "claim_limit": (
            "carrier admission only; no orbital, identity, amplitude-response, "
            "or independent-prediction claim"
        ),
    }


def parameter_manifest(
    parameters: CarrierTrackerParameters = PARAMETERS,
) -> dict[str, object]:
    parameters.validate()
    value = asdict(parameters)
    value.update(
        {
            "native_bin_spacing_hz": parameters.native_bin_spacing_hz,
            "effective_frequency_resolution_hz": (
                parameters.effective_frequency_resolution_hz
            ),
            "frame_hop_s": parameters.frame_hop_s,
            "frame_first_offset_s": parameters.frame_first_offset_s,
            "overlap_samples": (
                parameters.stft_length_samples - parameters.stft_hop_samples
            ),
        }
    )
    return value


def strict_json(value: object, *, indent: int | None = None) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=indent,
        separators=None if indent is not None else (",", ":"),
        sort_keys=True,
    )


def _candidate_from_frame(
    frame: np.ndarray,
    frequency_axis: np.ndarray,
    *,
    event_time_offset_s: float,
    frame_index: int,
    baseband: RecordedBasebandCoordinates,
    parameters: CarrierTrackerParameters,
) -> _FrameCandidate:
    frame_clipped = _clipped_scalar_count(frame) / (2.0 * frame.size)
    if frame_clipped > parameters.maximum_clipped_scalar_fraction:
        return _FrameCandidate(None, "CLIPPED")
    spectrum = np.fft.fftshift(np.fft.fft(frame * np.hanning(frame.size + 1)[:-1]))
    power = np.square(np.abs(spectrum))
    if not np.all(np.isfinite(power)):
        raise CarrierTrackerError("non-finite frame power")

    strongest_index = int(np.argmax(power))
    strongest_frequency = float(frequency_axis[strongest_index])
    lower = baseband.lower_hz + parameters.passband_edge_guard_hz
    upper = baseband.upper_hz - parameters.passband_edge_guard_hz
    if not lower <= strongest_frequency <= upper:
        return _FrameCandidate(None, "EDGE")

    separation = np.abs(frequency_axis - strongest_frequency)
    background_mask = (
        (separation <= parameters.local_background_half_width_hz)
        & (separation > parameters.candidate_exclusion_half_width_hz)
        & (frequency_axis >= lower)
        & (frequency_axis <= upper)
    )
    background_values = power[background_mask]
    if background_values.size < 8:
        raise CarrierTrackerError("too few local background bins")
    background = float(np.median(background_values))
    peak = float(power[strongest_index])
    if background <= 0.0 or peak <= 0.0:
        return _FrameCandidate(None, "SNR")
    snr_db = 10.0 * log10(peak / background)
    if snr_db < parameters.minimum_peak_snr_db:
        return _FrameCandidate(None, "SNR")

    competitor_mask = (
        (separation > parameters.candidate_exclusion_half_width_hz)
        & (frequency_axis >= lower)
        & (frequency_axis <= upper)
    )
    competitor = float(np.max(power[competitor_mask]))
    ambiguity_margin_db = 10.0 * log10(peak / max(competitor, np.finfo(float).tiny))
    if ambiguity_margin_db < parameters.minimum_ambiguity_margin_db:
        return _FrameCandidate(None, "AMBIGUOUS")
    return _FrameCandidate(
        CarrierPoint(
            frame_index=frame_index,
            event_time_offset_s=event_time_offset_s,
            baseband_frequency_hz=strongest_frequency,
            peak_snr_db=snr_db,
            ambiguity_margin_db=ambiguity_margin_db,
        ),
        "NONE",
    )


def _continuous_segments(
    candidates: list[CarrierPoint],
    parameters: CarrierTrackerParameters,
) -> tuple[CarrierSegment, ...]:
    if not candidates:
        return ()
    ordered = sorted(candidates, key=lambda point: point.frame_index)
    raw_segments: list[list[CarrierPoint]] = [[ordered[0]]]
    for point in ordered[1:]:
        previous = raw_segments[-1][-1]
        frame_gap = point.frame_index - previous.frame_index - 1
        elapsed = point.event_time_offset_s - previous.event_time_offset_s
        slew = abs(point.baseband_frequency_hz - previous.baseband_frequency_hz) / elapsed
        if frame_gap <= parameters.maximum_gap_frames and slew <= parameters.maximum_slew_hz_s:
            raw_segments[-1].append(point)
        else:
            raw_segments.append([point])
    return tuple(CarrierSegment(tuple(points)) for points in raw_segments)


def _select_segment(
    segments: tuple[CarrierSegment, ...], minimum_frames: int
) -> int | None:
    eligible = [
        (index, segment)
        for index, segment in enumerate(segments)
        if len(segment.points) >= minimum_frames
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda item: (-len(item[1].points), item[1].points[0].frame_index),
    )[0]


def _maximum_slew(points: tuple[CarrierPoint, ...]) -> float:
    if len(points) < 2:
        return 0.0
    return max(
        abs(right.baseband_frequency_hz - left.baseband_frequency_hz)
        / (right.event_time_offset_s - left.event_time_offset_s)
        for left, right in zip(points, points[1:])
    )


def _validate_detector_inputs(
    samples: np.ndarray,
    sample_rate_hz: int,
    baseband: RecordedBasebandCoordinates,
    receiver: FrozenReceiverConfiguration,
    parameters: CarrierTrackerParameters,
) -> None:
    if samples.ndim != 1 or not np.iscomplexobj(samples):
        raise CarrierTrackerError("samples must be one-dimensional complex values")
    if not np.all(np.isfinite(samples.real)) or not np.all(np.isfinite(samples.imag)):
        raise CarrierTrackerError("samples contain non-finite values")
    if np.any(samples.real < -32768) or np.any(samples.real > 32767):
        raise CarrierTrackerError("I samples exceed signed-int16 range")
    if np.any(samples.imag < -32768) or np.any(samples.imag > 32767):
        raise CarrierTrackerError("Q samples exceed signed-int16 range")
    if sample_rate_hz != parameters.expected_sample_rate_hz:
        raise CarrierTrackerError("sample rate differs from frozen detector")
    if receiver.sample_rate_hz != sample_rate_hz:
        raise CarrierTrackerError("sample rate conflicts with receiver header")
    if receiver.sample_encoding != parameters.sample_encoding:
        raise CarrierTrackerError("sample encoding conflicts with detector")
    if receiver.complex_convention != parameters.complex_convention:
        raise CarrierTrackerError("complex convention conflicts with detector")
    if not receiver.sequence_continuous or not receiver.timestamp_continuous:
        raise CarrierTrackerError("gapped input may not be concatenated")
    expected_lower = baseband.center_hz - sample_rate_hz / 2.0
    expected_upper = baseband.center_hz + sample_rate_hz / 2.0
    if baseband.lower_hz != expected_lower or baseband.upper_hz != expected_upper:
        raise CarrierTrackerError("recorded-baseband coordinates conflict with sample rate")


def _clipped_scalar_count(samples: np.ndarray) -> int:
    minimum = np.iinfo(np.int16).min
    maximum = np.iinfo(np.int16).max
    return int(
        np.count_nonzero((samples.real == minimum) | (samples.real == maximum))
        + np.count_nonzero((samples.imag == minimum) | (samples.imag == maximum))
    )


def _validate_record_continuity(
    sequences: tuple[int, ...],
    first_sample_tags: tuple[str, ...],
    *,
    record_duration_s: float,
) -> None:
    if not sequences or len(sequences) != len(first_sample_tags):
        raise CarrierTrackerError("record continuity inputs are empty or unequal")
    instants = tuple(_parse_utc(value) for value in first_sample_tags)
    for index in range(1, len(sequences)):
        if sequences[index] != sequences[index - 1] + 1:
            raise CarrierTrackerError("RSR record sequence gap or reordering")
        if instants[index] - instants[index - 1] != timedelta(seconds=record_duration_s):
            raise CarrierTrackerError("RSR first-sample timestamp gap or reordering")


def _parse_utc(value: str) -> datetime:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CarrierTrackerError("invalid UTC timestamp") from exc
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise CarrierTrackerError("timestamp must be timezone-aware")
    return instant.astimezone(timezone.utc)


def _read_authority(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CarrierTrackerError("development authority is unreadable") from exc
    if value.get("authority_version") != "maven-dss45-development-artifact-authority-v1":
        raise CarrierTrackerError("development authority version changed")
    if value.get("development_product", {}).get("role") != "DEVELOPMENT_ONLY":
        raise CarrierTrackerError("authority does not designate a development product")
    return value


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


__all__ = [
    "CarrierPoint",
    "CarrierSegment",
    "CarrierTrackerError",
    "CarrierTrackerParameters",
    "CarrierTrackerResult",
    "FrozenReceiverConfiguration",
    "PARAMETERS",
    "RecordedBasebandCoordinates",
    "TRACKER_VERSION",
    "VerifiedDevelopmentArtifact",
    "development_result_object",
    "parameter_manifest",
    "strict_json",
    "track_narrowband_carrier",
    "verify_and_decode_development_artifact",
]
