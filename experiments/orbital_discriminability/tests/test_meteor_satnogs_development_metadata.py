"""Tests for the amplitude-blind SatNOGS development metadata parser."""

from __future__ import annotations

from datetime import datetime, timezone
import inspect
import json
from pathlib import Path
import struct
import zlib

import h5py
import numpy as np
import pytest

from experiments.orbital_discriminability import meteor_satnogs_development_metadata as metadata


def _hdf5_fixture(path: Path, observation_id: int = 14904366) -> None:
    with h5py.File(path, "w") as artifact:
        artifact.attrs["artifact_version"] = 2
        artifact.attrs["metadata"] = json.dumps(
            {
                "observation_id": observation_id,
                "tle": "fixture",
                "frequency": 137_900_000,
                "location": {"latitude": 1.0, "longitude": 2.0, "altitude": 3.0},
            }
        )
        waterfall = artifact.create_group("waterfall")
        waterfall.attrs["start_time"] = "2026-08-29 T13:21:42.000000 Z"
        waterfall.attrs["relative_time_unit"] = "seconds"
        waterfall.attrs["absolute_time_unit"] = "seconds"
        waterfall.attrs["frequency_unit"] = "kHz"
        waterfall.create_dataset("relative_time", data=np.array([0.0, 1.0, 2.0]))
        waterfall.create_dataset("absolute_time", data=np.array([0, 1_000_000, 2_000_000]))
        waterfall.create_dataset("frequency", data=np.array([-2.0, 0.0, 2.0, 4.0]))
        waterfall.create_dataset("data", data=np.full((3, 4), 91, dtype=np.uint8))
        waterfall.create_dataset("offset", data=np.full(4, -123.0))
        waterfall.create_dataset("scale", data=np.full(4, 0.25))


def _chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(payload, crc) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", crc)


def _png_fixture(path: Path, observation_id: int = 14907984) -> None:
    ihdr = struct.pack(">IIBBBBB", 8, 16, 8, 2, 0, 0, 0)
    text = json.dumps(
        {
            "observation_id": observation_id,
            "nchan": "1024",
            "samp_rate": "48000",
            "nfft_per_row": "10",
            "center_freq": "137900000",
            "timestamp": "2026-08-29T13:22:48.269677Z",
        }
    ).encode("latin-1")
    path.write_bytes(
        metadata.PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"tEXt", b"satnogs:wf-dat\0" + text)
        + _chunk(b"IDAT", b"RF_PIXEL_SENTINEL_MUST_NOT_BE_DECOMPRESSED")
        + _chunk(b"IEND", b"")
    )


def test_hdf5_reads_coordinates_but_never_signal_datasets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "fixture.h5"
    _hdf5_fixture(path)
    original = h5py.Dataset.__getitem__

    def guarded(dataset, key):  # type: ignore[no-untyped-def]
        if dataset.name.rsplit("/", 1)[-1] in metadata.FORBIDDEN_HDF5_VALUES:
            raise AssertionError("signal-derived HDF5 dataset value was read")
        return original(dataset, key)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", guarded)
    receipt = metadata.characterize_hdf5(path, 14904366)

    assert receipt["signal_value_access"] == "ZERO"
    assert receipt["time_coordinate"]["absolute_time_stored_semantics"] == (
        "MICROSECONDS_RELATIVE_TO_START_TIME"
    )
    assert receipt["time_coordinate"]["declared_absolute_unit_consistent"] is False
    assert receipt["frequency_coordinate"]["declared_unit_consistent"] is False
    assert receipt["data_axis_mapping"] == "AXIS_0_TIME_AXIS_1_FREQUENCY"
    assert receipt["dataset_structure"]["data"]["values_read"] is False


def test_hdf5_refuses_wrong_observation_identity(tmp_path: Path) -> None:
    path = tmp_path / "wrong.h5"
    _hdf5_fixture(path, observation_id=14907984)

    with pytest.raises(metadata.MetadataPathError, match="does not match"):
        metadata.characterize_hdf5(path, 14904366)


def test_time_scale_uses_whole_duration_when_event_cadence_is_irregular() -> None:
    receipt = metadata._time_receipt(
        "2026-08-29T13:21:45.191884Z",
        np.array([0.0, 0.096, 0.192, 0.288]),
        np.array([118_106, 207_369, 299_420, 407_007]),
        "seconds",
        "seconds",
    )

    assert receipt["absolute_time_stored_semantics"] == (
        "MICROSECONDS_RELATIVE_TO_START_TIME"
    )
    assert receipt["declared_absolute_unit_consistent"] is False
    assert receipt["nominal_median_row_cadence_s"] == pytest.approx(0.096)
    assert receipt["event_time_median_row_cadence_s"] == pytest.approx(0.092051)


def test_png_skips_idat_and_reads_only_satnogs_text(tmp_path: Path) -> None:
    path = tmp_path / "fixture.png"
    _png_fixture(path)
    receipt = metadata.characterize_png(path, 14907984)

    assert receipt["pixel_value_access"] == "ZERO"
    assert receipt["native_coordinate_status"] == (
        "NATIVE_HEADER_CONFIGURATION_ONLY"
    )
    assert receipt["native_header_configuration"]["native_bin_spacing_hz"] == 46.875
    assert receipt["native_header_configuration"][
        "nominal_native_row_cadence_s"
    ] == pytest.approx(10 * 1024 / 48000)
    assert receipt["native_row_event_time_sequence"] == "NOT_EXPOSED"
    assert receipt["idat"]["chunk_count"] == 1
    assert receipt["idat"]["byte_count_skipped_without_decompression"] == 42
    assert receipt["allowed_text_metadata"]["satnogs:wf-dat"]["nchan"] == "1024"


def test_png_without_text_remains_display_raster_only(tmp_path: Path) -> None:
    path = tmp_path / "legacy.png"
    ihdr = struct.pack(">IIBBBBB", 8, 16, 8, 2, 0, 0, 0)
    path.write_bytes(
        metadata.PNG_SIGNATURE
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", b"opaque")
        + _chunk(b"IEND", b"")
    )

    receipt = metadata.characterize_png(path, 14904366)

    assert receipt["native_coordinate_status"] == "DISPLAY_RASTER_ONLY"
    assert receipt["allowed_text_metadata"] == {}


def test_combined_receipt_does_not_admit_without_control_trace(tmp_path: Path) -> None:
    hdf5_path = tmp_path / "fixture.h5"
    png_path = tmp_path / "fixture.png"
    _hdf5_fixture(hdf5_path)
    _png_fixture(png_path)
    hdf5 = metadata.characterize_hdf5(hdf5_path, 14904366)
    png = metadata.characterize_png(png_path, 14907984)

    receipt = metadata.combine_development_receipts((hdf5,), (png,))

    assert receipt["native_coordinate_pair"] is False
    assert receipt["applied_control_pair"] is False
    assert receipt["outcome"] == metadata.OUTCOME_BLOCKED
    assert receipt["primary_artifact_access"] == "ZERO"


def test_parser_is_bounded_and_has_no_network_or_image_decoder() -> None:
    source = inspect.getsource(metadata)

    assert metadata.EXPECTED_DEVELOPMENT_IDS == {14904366, 14907984}
    for forbidden in (
        "import requests",
        "import urllib",
        "Image.open",
        "PIL",
        "14919555",
        "14919561",
        "14919551",
        "14919554",
    ):
        assert forbidden not in source


def test_receipts_are_strict_json(tmp_path: Path) -> None:
    path = tmp_path / "fixture.png"
    _png_fixture(path)
    receipt = metadata.characterize_png(path, 14907984)
    encoded = metadata.strict_json(receipt)

    assert datetime.now(timezone.utc).tzinfo is not None
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert json.loads(encoded)["observation_id"] == 14907984


def test_frozen_development_receipt_preserves_refusal_and_access_boundary() -> None:
    path = Path(metadata.__file__).with_name(
        "METEOR_SATNOGS_DEVELOPMENT_METADATA_RECEIPT.json"
    )
    receipt = json.loads(path.read_text(encoding="utf-8"))

    assert receipt["outcome"] == metadata.OUTCOME_BLOCKED
    assert receipt["authority"]["primary_artifact_access"] == "ZERO"
    assert receipt["authority"]["signal_value_access"] == "ZERO"
    assert receipt["pair_admission"]["native_row_event_time_sequence_pair"] is False
    assert receipt["pair_admission"]["applied_doppler_control_pair"] is False
    assert receipt["pair_admission"]["detector_authorized"] is False
    assert receipt["persistence"]["rf_artifacts_retained"] == 0
    assert receipt["artifacts"][0]["sha256"] == (
        "cbf9ec168433144454853fe4190e9070d278d8c5e5bf68aaf3bfdbf98c60a750"
    )
