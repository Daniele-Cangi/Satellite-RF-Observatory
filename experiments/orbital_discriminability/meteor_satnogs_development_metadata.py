"""Amplitude-blind metadata characterization for two METEOR SatNOGS fixtures.

This one-off parser has no network client.  HDF5 access is restricted to
attributes and the three coordinate datasets needed to reconstruct time and
frequency.  Signal-derived ``data``, ``offset`` and ``scale`` datasets are
described structurally but their values are never indexed.  PNG ``IDAT``
chunks are skipped without decompression; only IHDR and textual metadata are
interpreted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import struct
from typing import Any, Mapping
import zlib

import h5py
import numpy as np

from experiments.live_instrument.models import strict_json_value


OUTCOME_ADMITTED = "SATNOGS_DEVELOPMENT_METADATA_COORDINATES_ADMITTED"
OUTCOME_BLOCKED = "SATNOGS_DEVELOPMENT_METADATA_PATH_BLOCKED"
ALLOWED_HDF5_COORDINATES = frozenset(
    {"relative_time", "absolute_time", "frequency"}
)
FORBIDDEN_HDF5_VALUES = frozenset({"data", "offset", "scale"})
ALLOWED_PNG_TEXT_KEYS = frozenset({"satnogs:wf-dat", "satnogs:wf-plot"})
EXPECTED_DEVELOPMENT_IDS = frozenset({14904366, 14907984})
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class MetadataPathError(ValueError):
    """Raised when the structural product cannot support the frozen audit."""


@dataclass(frozen=True, slots=True)
class FileIdentity:
    sha256: str
    byte_count: int


def file_identity(path: Path) -> FileIdentity:
    digest = sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            byte_count += len(chunk)
    return FileIdentity(digest.hexdigest(), byte_count)


def characterize_hdf5(path: Path, expected_observation_id: int) -> dict[str, object]:
    """Inspect one SatNOGS HDF5 artifact without reading RF-derived values."""

    _require_development_id(expected_observation_id)
    identity = file_identity(path)
    with h5py.File(path, "r") as artifact:
        if "waterfall" not in artifact or not isinstance(artifact["waterfall"], h5py.Group):
            raise MetadataPathError("HDF5 artifact has no waterfall group")
        root_attrs = _attributes(artifact.attrs)
        metadata = _metadata_json(root_attrs.get("metadata"))
        observed_id = _observation_id(root_attrs, metadata)
        if observed_id != expected_observation_id:
            raise MetadataPathError(
                f"artifact observation {observed_id} does not match {expected_observation_id}"
            )

        waterfall = artifact["waterfall"]
        group_attrs = _attributes(waterfall.attrs)
        missing = ALLOWED_HDF5_COORDINATES.difference(waterfall.keys())
        if missing:
            raise MetadataPathError(f"HDF5 coordinate datasets missing: {sorted(missing)}")

        # This is the complete value-read boundary.  No signal-derived dataset
        # name can reach it.
        coordinates = {
            name: _read_coordinate(waterfall, name)
            for name in sorted(ALLOWED_HDF5_COORDINATES)
        }
        relative = coordinates["relative_time"]
        absolute_raw = coordinates["absolute_time"]
        frequency_raw = coordinates["frequency"]
        time_receipt = _time_receipt(
            group_attrs.get("start_time"),
            relative,
            absolute_raw,
            group_attrs.get("relative_time_unit"),
            group_attrs.get("absolute_time_unit"),
        )
        frequency_receipt = _frequency_receipt(
            frequency_raw,
            group_attrs.get("frequency_unit"),
        )
        dataset_structure = {
            name: _dataset_structure(dataset)
            for name, dataset in sorted(waterfall.items())
            if isinstance(dataset, h5py.Dataset)
        }
        _validate_signal_dataset_boundary(dataset_structure)
        axis_mapping = _axis_mapping(
            dataset_structure.get("data"),
            int(time_receipt["row_count"]),
            int(frequency_receipt["bin_count"]),
        )

    receipt: dict[str, object] = {
        "product": "SATNOGS_HDF5_ARTIFACT",
        "observation_id": expected_observation_id,
        "file_identity": asdict(identity),
        "artifact_version": root_attrs.get("artifact_version"),
        "observation_metadata": _allowed_observation_metadata(metadata),
        "time_coordinate": time_receipt,
        "frequency_coordinate": frequency_receipt,
        "dataset_structure": dataset_structure,
        "data_axis_mapping": axis_mapping,
        "signal_value_access": "ZERO",
        "forbidden_value_datasets": sorted(FORBIDDEN_HDF5_VALUES),
    }
    strict_json(receipt)
    return receipt


def characterize_png(path: Path, expected_observation_id: int) -> dict[str, object]:
    """Read PNG structure/text while skipping every image-data chunk."""

    _require_development_id(expected_observation_id)
    identity = file_identity(path)
    width: int | None = None
    height: int | None = None
    bit_depth: int | None = None
    color_type: int | None = None
    text: dict[str, str] = {}
    idat_chunks = 0
    idat_bytes = 0
    chunk_types: list[str] = []

    with path.open("rb") as handle:
        if handle.read(8) != PNG_SIGNATURE:
            raise MetadataPathError("invalid PNG signature")
        while True:
            header = handle.read(8)
            if len(header) != 8:
                raise MetadataPathError("truncated PNG chunk header")
            length, chunk_type_raw = struct.unpack(">I4s", header)
            chunk_type = chunk_type_raw.decode("ascii", errors="strict")
            chunk_types.append(chunk_type)
            if chunk_type == "IDAT":
                handle.seek(length, 1)
                idat_chunks += 1
                idat_bytes += length
                payload = None
            else:
                payload = handle.read(length)
                if len(payload) != length:
                    raise MetadataPathError("truncated PNG chunk payload")
            crc = handle.read(4)
            if len(crc) != 4:
                raise MetadataPathError("truncated PNG chunk CRC")
            if payload is not None:
                expected_crc = struct.unpack(">I", crc)[0]
                actual_crc = zlib.crc32(chunk_type_raw)
                actual_crc = zlib.crc32(payload, actual_crc) & 0xFFFFFFFF
                if actual_crc != expected_crc:
                    raise MetadataPathError(f"invalid PNG CRC for {chunk_type}")
            if chunk_type == "IHDR":
                if payload is None or len(payload) != 13:
                    raise MetadataPathError("invalid PNG IHDR")
                width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                    ">IIBBBBB", payload
                )
            elif chunk_type in {"tEXt", "zTXt", "iTXt"}:
                if payload is None:
                    raise MetadataPathError("PNG text payload missing")
                key, value = _png_text(chunk_type, payload)
                if key in ALLOWED_PNG_TEXT_KEYS:
                    text[key] = value
            elif chunk_type == "IEND":
                break

    if width is None or height is None:
        raise MetadataPathError("PNG has no IHDR")
    parsed_text = {
        key: _strict_json_object(value, key) for key, value in sorted(text.items())
    }
    wf_dat = parsed_text.get("satnogs:wf-dat")
    if isinstance(wf_dat, Mapping):
        _validate_png_observation_metadata(wf_dat, expected_observation_id)
    native_header = _png_native_header_receipt(wf_dat)
    receipt: dict[str, object] = {
        "product": "SATNOGS_WATERFALL_PNG",
        "observation_id": expected_observation_id,
        "file_identity": asdict(identity),
        "display_raster": {
            "width_px": width,
            "height_px": height,
            "bit_depth": bit_depth,
            "color_type": color_type,
        },
        "chunk_types": chunk_types,
        "idat": {
            "chunk_count": idat_chunks,
            "byte_count_skipped_without_decompression": idat_bytes,
        },
        "allowed_text_metadata": parsed_text,
        "native_header_configuration": native_header,
        "native_coordinate_status": (
            "NATIVE_HEADER_CONFIGURATION_ONLY"
            if native_header is not None
            else "DISPLAY_RASTER_ONLY"
        ),
        "native_row_event_time_sequence": "NOT_EXPOSED",
        "pixel_to_native_bin_mapping": "NOT_EXPOSED",
        "display_compression": "PNG_DEFLATE",
        "pixel_value_access": "ZERO",
    }
    strict_json(receipt)
    return receipt


def combine_development_receipts(
    hdf5_receipts: tuple[Mapping[str, object], ...],
    png_receipts: tuple[Mapping[str, object], ...],
) -> dict[str, object]:
    """Classify whether both development roots preserve needed coordinates."""

    products = (*hdf5_receipts, *png_receipts)
    observed_ids = {int(item["observation_id"]) for item in products}
    if not observed_ids.issubset(EXPECTED_DEVELOPMENT_IDS):
        raise MetadataPathError("receipt includes a non-development observation")
    per_observation: list[dict[str, object]] = []
    for observation_id in sorted(EXPECTED_DEVELOPMENT_IDS):
        hdf5 = next(
            (item for item in hdf5_receipts if item["observation_id"] == observation_id),
            None,
        )
        png = next(
            (item for item in png_receipts if item["observation_id"] == observation_id),
            None,
        )
        native_header = bool(
            png
            and png.get("native_coordinate_status")
            == "NATIVE_HEADER_CONFIGURATION_ONLY"
        )
        native_coordinates = hdf5 is not None
        per_observation.append(
            {
                "observation_id": observation_id,
                "hdf5_available": hdf5 is not None,
                "png_available": png is not None,
                "native_header_configuration_available": native_header,
                "native_coordinates_available": native_coordinates,
                "native_row_event_time_sequence_available": hdf5 is not None,
                "applied_doppler_control_trace": "NOT_EXPOSED",
            }
        )
    coordinate_pair = all(item["native_coordinates_available"] for item in per_observation)
    control_pair = all(
        item["applied_doppler_control_trace"] != "NOT_EXPOSED"
        for item in per_observation
    )
    outcome = OUTCOME_ADMITTED if coordinate_pair and control_pair else OUTCOME_BLOCKED
    receipt: dict[str, object] = {
        "outcome": outcome,
        "per_observation": per_observation,
        "native_coordinate_pair": coordinate_pair,
        "applied_control_pair": control_pair,
        "physical_interpretation": (
            "a post-Doppler held-out comparison is admissible"
            if outcome == OUTCOME_ADMITTED
            else "the native row grid and model-controlled baseband transform are not both available for both roots"
        ),
        "primary_artifact_access": "ZERO",
        "signal_value_access": "ZERO",
        "persistent_rf_artifacts": 0,
    }
    strict_json(receipt)
    return receipt


def _read_coordinate(group: h5py.Group, name: str) -> np.ndarray:
    if name not in ALLOWED_HDF5_COORDINATES:
        raise MetadataPathError(f"HDF5 value access forbidden for {name}")
    values = np.asarray(group[name][...], dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise MetadataPathError(f"coordinate {name} must be one finite vector")
    return values


def _time_receipt(
    start_time_raw: object,
    relative: np.ndarray,
    absolute_raw: np.ndarray,
    declared_relative_unit: object,
    declared_absolute_unit: object,
) -> dict[str, object]:
    if relative.shape != absolute_raw.shape:
        raise MetadataPathError("time coordinates have different lengths")
    if not (np.all(np.diff(relative) > 0.0) and np.all(np.diff(absolute_raw) > 0.0)):
        raise MetadataPathError("time coordinates are not strictly increasing")
    start = _parse_start_time(start_time_raw)
    relative_steps = np.diff(relative)
    absolute_steps = np.diff(absolute_raw)
    relative_duration = float(relative[-1] - relative[0])
    absolute_duration = float(absolute_raw[-1] - absolute_raw[0])
    if relative_duration <= 0.0:
        raise MetadataPathError("relative time duration is not positive")
    candidates = (
        (1_000_000.0, "MICROSECONDS_RELATIVE_TO_START_TIME"),
        (1.0, "SECONDS_RELATIVE_TO_START_TIME"),
    )
    absolute_scale, stored_absolute_semantics = min(
        candidates,
        key=lambda candidate: abs(
            absolute_duration / candidate[0] - relative_duration
        ),
    )
    duration_error = abs(absolute_duration / absolute_scale - relative_duration)
    if duration_error > max(0.1, relative_duration * 0.05):
        raise MetadataPathError("absolute/relative time scale cannot be reconciled")
    absolute_seconds = absolute_raw / absolute_scale
    disagreement = np.abs(absolute_seconds - relative)
    event_median_step = float(np.median(absolute_steps) / absolute_scale)
    nominal_median_step = float(np.median(relative_steps))
    gap_threshold = 1.5 * nominal_median_step
    gap_count = int(np.count_nonzero((absolute_steps / absolute_scale) > gap_threshold))
    return {
        "row_count": int(relative.size),
        "start_time": start.isoformat(),
        "first_event_time": (start + timedelta(seconds=float(absolute_seconds[0]))).isoformat(),
        "last_event_time": (start + timedelta(seconds=float(absolute_seconds[-1]))).isoformat(),
        "relative_time_declared_unit": _scalar(declared_relative_unit),
        "absolute_time_declared_unit": _scalar(declared_absolute_unit),
        "absolute_time_stored_semantics": stored_absolute_semantics,
        "declared_absolute_unit_consistent": (
            str(_scalar(declared_absolute_unit)).lower().startswith("micro")
            if absolute_scale == 1_000_000.0
            else str(_scalar(declared_absolute_unit)).lower().startswith("second")
        ),
        "nominal_median_row_cadence_s": nominal_median_step,
        "event_time_median_row_cadence_s": event_median_step,
        "minimum_row_cadence_s": float(np.min(absolute_steps) / absolute_scale),
        "maximum_row_cadence_s": float(np.max(absolute_steps) / absolute_scale),
        "absolute_duration_vs_relative_duration_error_s": duration_error,
        "relative_absolute_max_disagreement_s": float(np.max(disagreement)),
        "gap_count_above_1_5x_median": gap_count,
        "explicit_sequence_number": False,
        "continuity_witness": "MONOTONIC_ROW_EVENT_TIME_ONLY",
    }


def _frequency_receipt(values: np.ndarray, declared_unit: object) -> dict[str, object]:
    steps = np.diff(values)
    if not np.all(steps > 0.0):
        raise MetadataPathError("frequency coordinate is not strictly increasing")
    spacing = float(np.median(steps))
    if not np.allclose(steps, spacing, rtol=1.0e-9, atol=1.0e-9):
        raise MetadataPathError("frequency coordinate is not uniformly spaced")
    inferred_sample_rate = spacing * values.size
    # The client constructs this vector directly from samp_rate in hertz.  The
    # legacy HDF5 attribute says kHz; retain both rather than silently scaling.
    stored_semantics = "HZ_FROM_CLIENT_CONSTRUCTION"
    declared = str(_scalar(declared_unit))
    return {
        "bin_count": int(values.size),
        "first_bin_stored": float(values[0]),
        "last_bin_stored": float(values[-1]),
        "bin_spacing_stored": spacing,
        "declared_unit": declared,
        "stored_semantics": stored_semantics,
        "declared_unit_consistent": declared.lower() in {"hz", "hertz"},
        "effective_bin_spacing_hz": spacing,
        "inferred_sample_rate_hz": inferred_sample_rate,
        "center_frequency_role": "RELATIVE_BASEBAND_AXIS",
    }


def _dataset_structure(dataset: h5py.Dataset) -> dict[str, object]:
    return {
        "shape": [int(value) for value in dataset.shape],
        "dtype": str(dataset.dtype),
        "dimension_labels": [str(dimension.label) for dimension in dataset.dims],
        "chunks": (
            [int(value) for value in dataset.chunks]
            if dataset.chunks is not None
            else None
        ),
        "compression": dataset.compression,
        "compression_options": _scalar(dataset.compression_opts),
        "shuffle": bool(dataset.shuffle),
        "fletcher32": bool(dataset.fletcher32),
        "scaleoffset": dataset.scaleoffset,
        "values_read": dataset.name.rsplit("/", 1)[-1] in ALLOWED_HDF5_COORDINATES,
    }


def _png_native_header_receipt(
    metadata: Mapping[str, object] | None,
) -> dict[str, object] | None:
    if metadata is None:
        return None
    required = {"timestamp", "nchan", "samp_rate", "nfft_per_row", "center_freq"}
    if not required.issubset(metadata):
        return None
    try:
        nchan = int(metadata["nchan"])
        sample_rate = float(metadata["samp_rate"])
        nfft_per_row = int(metadata["nfft_per_row"])
        center_frequency = float(metadata["center_freq"])
    except (TypeError, ValueError) as error:
        raise MetadataPathError("PNG native header has non-numeric fields") from error
    if (
        nchan <= 0
        or nfft_per_row <= 0
        or not isfinite(sample_rate)
        or sample_rate <= 0.0
        or not isfinite(center_frequency)
    ):
        raise MetadataPathError("PNG native header has invalid coordinate fields")
    start = _parse_start_time(metadata["timestamp"])
    return {
        "start_time": start.isoformat(),
        "center_frequency_hz": center_frequency,
        "native_bin_count": nchan,
        "sample_rate_hz": sample_rate,
        "native_bin_spacing_hz": sample_rate / nchan,
        "ffts_per_native_row": nfft_per_row,
        "nominal_native_row_cadence_s": nfft_per_row * nchan / sample_rate,
        "endianness": metadata.get("endianness"),
        "overlap": "NOT_EXPOSED",
        "actual_row_event_times": "NOT_EXPOSED",
    }


def _validate_signal_dataset_boundary(structure: Mapping[str, Mapping[str, object]]) -> None:
    for name in FORBIDDEN_HDF5_VALUES:
        if name in structure and structure[name]["values_read"] is not False:
            raise MetadataPathError(f"signal-derived HDF5 values were exposed for {name}")


def _axis_mapping(
    data: Mapping[str, object] | None,
    time_count: int,
    frequency_count: int,
) -> str:
    if data is None:
        return "NO_DATASET"
    shape = tuple(int(item) for item in data["shape"])
    if shape == (time_count, frequency_count):
        return "AXIS_0_TIME_AXIS_1_FREQUENCY"
    if shape == (frequency_count, time_count):
        return "AXIS_0_FREQUENCY_AXIS_1_TIME"
    return "UNRESOLVED_SHAPE_MISMATCH"


def _attributes(attributes: h5py.AttributeManager) -> dict[str, object]:
    return {str(key): _scalar(value) for key, value in attributes.items()}


def _scalar(value: object) -> object:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if value.ndim != 0:
            raise MetadataPathError("non-scalar HDF5 attribute is outside the whitelist")
        return value.item()
    return value


def _metadata_json(value: object) -> dict[str, object]:
    if value is None:
        return {}
    if not isinstance(value, str):
        raise MetadataPathError("artifact metadata attribute is not JSON text")
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise MetadataPathError("artifact metadata is not a JSON object")
    return parsed


def _observation_id(
    root_attrs: Mapping[str, object], metadata: Mapping[str, object]
) -> int:
    value = metadata.get("observation_id", root_attrs.get("observation_id"))
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise MetadataPathError("artifact has no valid observation ID") from error


def _allowed_observation_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    allowed = {"observation_id", "tle", "frequency", "location"}
    return {str(key): value for key, value in metadata.items() if key in allowed}


def _parse_start_time(value: object) -> datetime:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if not isinstance(value, str):
        raise MetadataPathError("waterfall start_time is not text")
    candidate = value.strip().replace(" T", "T")
    if candidate.endswith(" Z"):
        candidate = candidate[:-2] + "+00:00"
    elif candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise MetadataPathError("waterfall start_time is not ISO-8601") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _png_text(chunk_type: str, payload: bytes) -> tuple[str, str]:
    if chunk_type == "tEXt":
        keyword, value = payload.split(b"\0", 1)
        return keyword.decode("latin-1"), value.decode("latin-1")
    if chunk_type == "zTXt":
        keyword, remainder = payload.split(b"\0", 1)
        if not remainder or remainder[0] != 0:
            raise MetadataPathError("unsupported PNG zTXt compression")
        return keyword.decode("latin-1"), zlib.decompress(remainder[1:]).decode("latin-1")
    keyword, remainder = payload.split(b"\0", 1)
    if len(remainder) < 2:
        raise MetadataPathError("truncated PNG iTXt")
    compressed, method = remainder[0], remainder[1]
    language, translated, value = remainder[2:].split(b"\0", 2)
    del language, translated
    if compressed:
        if method != 0:
            raise MetadataPathError("unsupported PNG iTXt compression")
        value = zlib.decompress(value)
    return keyword.decode("latin-1"), value.decode("utf-8")


def _strict_json_object(value: str, key: str) -> dict[str, object]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise MetadataPathError(f"PNG {key} is not a JSON object")
    return parsed


def _validate_png_observation_metadata(
    metadata: Mapping[str, object], expected_observation_id: int
) -> None:
    value = metadata.get("observation_id")
    if value is not None and int(value) != expected_observation_id:
        raise MetadataPathError("PNG metadata observation ID mismatch")


def _require_development_id(observation_id: int) -> None:
    if observation_id not in EXPECTED_DEVELOPMENT_IDS:
        raise MetadataPathError("only the two frozen development IDs are authorized")


def strict_json(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if any(token in encoded for token in ("NaN", "Infinity", "-Infinity")):
        raise MetadataPathError("strict JSON contains a non-finite scalar")
    return encoded
