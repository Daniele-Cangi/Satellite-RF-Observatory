"""Sealed one-shot evaluator for the frozen KIRU/MAT1 GNSS primary.

This experiment-specific module has no network surface and does not authorize
primary access. Complete-file identity and a separate authority receipt are
verified before the first decompression byte.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import io
import json
import math
from pathlib import Path
import re
from typing import Final, Sequence

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_double_difference_envelope as envelope
from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_independent_forward_review as review
from experiments.orbital_discriminability.gnss_observation_header import ProductAuthority


EVALUATOR_VERSION: Final = "gnss-kiru-mat1-primary-evaluator-v1"
PLAN_NAME: Final = "GNSS_INDEPENDENT_PRIMARY_PROSPECTIVE_PLAN.md"
PLAN_SHA256: Final = "763fa4c5c2b5ea77faaedc75c753c360fd848294ab789a8868d1e91458b2c000"
PLAN_RECEIPT_SHA256: Final = "d9874543fd22d91d638846f94d6b7887962c565a089b0a88cbab74dfa5d10d65"
QUALIFICATION_RECEIPT_SHA256: Final = "5e2d319ba633dce788bfa0a8b8961fa228a4b6ffd0ed47787b92c59520b37f0d"
QUALIFICATION_MANIFEST_SHA256: Final = "bcd504f9e3a0e2b70bf62ee566fdcdc6154e43a7063d6bbe8921ad2ba292210c"
QUALIFICATION_SOURCE_SHA256: Final = "ada26cf0ac30ea556af480cf3590b5ff7b61b0e26bb762e766a87de95114be18"

TARGET: Final = "G20"
REFERENCE: Final = "G22"
WRONG_TARGET: Final = "G14"
SATELLITES: Final = (TARGET, REFERENCE)
HYPOTHESES: Final = ("H_G20", "H_AFFINE", "H_G14")
OBSERVABLES: Final = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
PHASE_OBSERVABLES: Final = ("L1C", "L2W")
RAW_START_GPS: Final = datetime(2026, 8, 3, 16, 2, 30, tzinfo=timezone.utc)
RAW_STOP_GPS: Final = datetime(2026, 8, 3, 19, 12, 0, tzinfo=timezone.utc)
RAW_RECORDS: Final = 380
FEATURE_RECORDS: Final = 378
CALIBRATION_RECORDS: Final = 76
HELDOUT_RECORDS: Final = 302
STEP_S: Final = 30.0
DERIVATIVE_BASELINE_S: Final = 60.0
GPS_MINUS_UTC_S: Final = 18.0
ONE_MODEL_ADMISSION_ENVELOPE_HZ: Final = 354.8594372656104
PAIRWISE_DECISION_GUARD_HZ: Final = 709.7188745312208
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.09514683639918244

ALLOWED_PHYSICAL_OUTCOMES: Final = (
    "MEASUREMENT_INVALID",
    "NOT_DETECTABLE",
    "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
    "PREFIX_AFFINE_NULL_PREFERRED",
    "WRONG_ORBIT_G14_PREFERRED",
    "AMBIGUOUS",
)
PRIMARY_PRODUCTS: Final = (
    {
        "station_id": "KIRU00SWE",
        "measurement_root": "KIRU00SWE_RECEIVER_ANTENNA_CLOCK",
        "name": "KIRU00SWE_R_20262150000_01D_30S_MO.crx.gz",
        "bytes": 5_113_772,
    },
    {
        "station_id": "MAT100ITA",
        "measurement_root": "MAT100ITA_RECEIVER_ANTENNA_CLOCK",
        "name": "MAT100ITA_R_20262150000_01D_30S_MO.crx.gz",
        "bytes": 4_255_324,
    },
)


class ArtifactMaterializationFailed(ValueError):
    """Complete artifact identity was not established before decompression."""


class MeasurementInvalid(ValueError):
    """A frozen physical measurement-admission clause failed."""


class PrimaryEvaluationError(RuntimeError):
    """The frozen evaluator could not describe or complete the run."""


@dataclass(slots=True)
class StationWindow:
    station_id: str
    epochs_gps: tuple[datetime, ...]
    values: np.ndarray
    lli: np.ndarray

    def erase(self) -> None:
        self.values.fill(0.0)
        self.lli.fill(0)


class _LineReader:
    def __init__(self, buffer: bytearray):
        self._stream = io.BytesIO(buffer)
        self._pending: bytes | None = None

    def readline(self) -> bytes:
        if self._pending is not None:
            line, self._pending = self._pending, None
            return line
        return self._stream.readline()

    def push(self, line: bytes) -> None:
        if self._pending is not None:
            raise PrimaryEvaluationError("MULTIPLE_LINE_PUSHBACK")
        self._pending = line


def frozen_epoch_grid() -> tuple[datetime, ...]:
    epochs: list[datetime] = []
    current = RAW_START_GPS
    while current <= RAW_STOP_GPS:
        epochs.append(current)
        current += timedelta(seconds=STEP_S)
    if len(epochs) != RAW_RECORDS:
        raise RuntimeError("FROZEN_RAW_EPOCH_COUNT_CHANGED")
    return tuple(epochs)


def runtime_manifest() -> dict[str, object]:
    """Return the canonical executable experiment description."""
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "plan": {"name": PLAN_NAME, "sha256": PLAN_SHA256},
        "plan_receipt_sha256": PLAN_RECEIPT_SHA256,
        "qualification": {
            "receipt_sha256": QUALIFICATION_RECEIPT_SHA256,
            "manifest_sha256": QUALIFICATION_MANIFEST_SHA256,
            "parser_source_sha256": QUALIFICATION_SOURCE_SHA256,
        },
        "dependencies": {
            "hatanaka": importlib.metadata.version("hatanaka"),
            "ncompress": importlib.metadata.version("ncompress"),
            "numpy": importlib.metadata.version("numpy"),
        },
        "parameters": {
            "stations": [item["station_id"] for item in PRIMARY_PRODUCTS],
            "measurement_roots": [
                item["measurement_root"] for item in PRIMARY_PRODUCTS
            ],
            "target": TARGET,
            "reference": REFERENCE,
            "wrong_orbit": WRONG_TARGET,
            "observables": list(OBSERVABLES),
            "raw_start_gps": format_gps_label(RAW_START_GPS),
            "raw_stop_gps": format_gps_label(RAW_STOP_GPS),
            "raw_records": RAW_RECORDS,
            "feature_records": FEATURE_RECORDS,
            "calibration_records": CALIBRATION_RECORDS,
            "heldout_records": HELDOUT_RECORDS,
            "step_s": STEP_S,
            "derivative_baseline_s": DERIVATIVE_BASELINE_S,
            "gps_minus_utc_s": GPS_MINUS_UTC_S,
            "l1_hz": envelope.GPS_L1_HZ,
            "l2_hz": envelope.GPS_L2_HZ,
            "ionosphere_free_coefficients": list(
                envelope.ionosphere_free_coefficients()
            ),
            "geometry_free_second_difference_limit_m": (
                GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
            ),
            "one_model_admission_envelope_hz": ONE_MODEL_ADMISSION_ENVELOPE_HZ,
            "pairwise_decision_guard_hz": PAIRWISE_DECISION_GUARD_HZ,
        },
        "hypotheses": list(HYPOTHESES),
        "scoring": (
            "PREFIX_ONLY_CONSTANT_AND_SLOPE; NOMINAL_PREFIX_DETECTABILITY_BEFORE_"
            "ANY_HELDOUT_SCORE; HELDOUT_RESIDUAL_PEAK_TO_PEAK; STRICT_PAIRWISE_GUARD"
        ),
        "outcomes": list(ALLOWED_PHYSICAL_OUTCOMES),
        "zero_persistence": {
            "compressed_primary": "QUARANTINE_ONLY_EXTERNAL_TO_EVALUATOR",
            "decompressed_rinex": "RAM_BYTEARRAY_OVERWRITTEN_IN_FINALLY",
            "measurement_and_hypothesis_arrays": "OVERWRITTEN_IN_FINALLY",
            "receipt": "HASHES_COUNTS_AND_FINITE_SCALARS_ONLY",
        },
        "forbidden": [
            "network access",
            "primary access without separately bound authority",
            "alternate station satellite signal or epoch window",
            "suffix nuisance fitting or free time phase",
            "missing-data interpolation or cycle-slip repair",
            "retry after decompression begins",
            "raw or derived measurement persistence",
            "satellite identity or orbit reconstruction claim",
        ],
    }


def runtime_manifest_sha256() -> str:
    return sha256(strict_json(runtime_manifest()).encode("ascii")).hexdigest()


def parse_plain_rinex_window(
    decoded: bytearray,
    station_id: str,
    expected_epochs: Sequence[datetime] | None = None,
) -> StationWindow:
    """Parse the exact numeric surface needed by the frozen coordinate."""
    epochs = tuple(expected_epochs or frozen_epoch_grid())
    reader = _LineReader(decoded)
    system_types, header = _read_header(reader)
    _validate_header(header, station_id)
    gps_types = system_types.get("G")
    if gps_types is None or any(item not in gps_types for item in OBSERVABLES):
        raise MeasurementInvalid("FROZEN_GPS_SIGNAL_FAMILY_MISSING")
    selected_index = {name: gps_types.index(name) for name in OBSERVABLES}
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    if len(epoch_index) != len(epochs):
        raise PrimaryEvaluationError("DUPLICATE_EXPECTED_EPOCH")
    values = np.full(
        (len(epochs), 2, len(OBSERVABLES)), np.nan, dtype=np.float64
    )
    lli = np.full(
        (len(epochs), 2, len(PHASE_OBSERVABLES)), -1, dtype=np.int8
    )
    try:
        _fill_window(
            reader, system_types, selected_index, epochs, epoch_index, values, lli
        )
    except Exception:
        values.fill(0.0)
        lli.fill(0)
        raise
    return StationWindow(station_id, epochs, values, lli)


def _read_header(
    reader: _LineReader,
) -> tuple[dict[str, tuple[str, ...]], dict[str, object]]:
    collected: dict[str, list[str]] = {}
    expected: dict[str, int] = {}
    current_system: str | None = None
    header: dict[str, object] = {"rcv_clock_offsets_applied": 0}
    while True:
        line = reader.readline()
        if not line:
            raise PrimaryEvaluationError("DECOMPRESSED_HEADER_INCOMPLETE")
        body = line.rstrip(b"\r\n")
        if len(body) < 60:
            raise PrimaryEvaluationError("SHORT_DECOMPRESSED_HEADER_LINE")
        try:
            label = body[60:80].decode("ascii", errors="strict").strip()
            data = body[:60].decode("ascii", errors="strict")
        except UnicodeDecodeError as exc:
            raise PrimaryEvaluationError("NON_ASCII_DECOMPRESSED_HEADER") from exc
        if label == "MARKER NAME":
            header["marker_name"] = data.strip()
        elif label == "INTERVAL":
            try:
                header["interval_s"] = float(data[:10])
            except ValueError as exc:
                raise PrimaryEvaluationError("INVALID_HEADER_INTERVAL") from exc
        elif label == "TIME OF FIRST OBS":
            header["time_system"] = data[48:51].strip()
        elif label == "RCV CLOCK OFFS APPL":
            try:
                header["rcv_clock_offsets_applied"] = int(data[:6])
            except ValueError as exc:
                raise PrimaryEvaluationError("INVALID_CLOCK_OFFSET_FLAG") from exc
        elif label == "SYS / # / OBS TYPES":
            if body[:1] != b" ":
                current_system = data[:1]
                try:
                    expected[current_system] = int(data[3:6])
                except ValueError as exc:
                    raise PrimaryEvaluationError(
                        "INVALID_OBSERVATION_TYPE_COUNT"
                    ) from exc
                collected[current_system] = []
            if current_system is None:
                raise PrimaryEvaluationError(
                    "ORPHAN_OBSERVATION_TYPE_CONTINUATION"
                )
            collected[current_system].extend(data[7:60].split())
        if label == "END OF HEADER":
            break
    result: dict[str, tuple[str, ...]] = {}
    for system, count in expected.items():
        if len(collected[system]) < count:
            raise PrimaryEvaluationError(
                "INCOMPLETE_OBSERVATION_TYPE_DECLARATION"
            )
        result[system] = tuple(collected[system][:count])
    return result, header


def _validate_header(header: dict[str, object], station_id: str) -> None:
    marker = str(header.get("marker_name", "")).upper()
    if marker not in {station_id.upper(), station_id[:4].upper()}:
        raise MeasurementInvalid("STATION_MARKER_MISMATCH")
    if header.get("interval_s") != STEP_S:
        raise MeasurementInvalid("NON_30S_HEADER_INTERVAL")
    if header.get("time_system") != "GPS":
        raise MeasurementInvalid("NON_GPS_OBSERVATION_TIME_SYSTEM")
    if header.get("rcv_clock_offsets_applied") != 0:
        raise MeasurementInvalid("RECEIVER_CLOCK_OFFSETS_APPLIED")


def _fill_window(
    reader: _LineReader,
    system_types: dict[str, tuple[str, ...]],
    selected_index: dict[str, int],
    expected_epochs: tuple[datetime, ...],
    epoch_index: dict[datetime, int],
    values: np.ndarray,
    lli: np.ndarray,
) -> None:
    seen_epochs: set[datetime] = set()
    seen_links: set[tuple[datetime, str]] = set()
    first_expected, last_expected = expected_epochs[0], expected_epochs[-1]
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise PrimaryEvaluationError("AMBIGUOUS_NON_EPOCH_RECORD")
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        in_window = first_expected <= epoch <= last_expected
        if in_window:
            if epoch not in epoch_index:
                raise MeasurementInvalid("NON_30S_EPOCH_IN_FROZEN_WINDOW")
            if epoch in seen_epochs:
                raise MeasurementInvalid("DUPLICATE_EPOCH_IN_FROZEN_WINDOW")
            if flag != 0:
                raise MeasurementInvalid("NON_OBSERVATION_EPOCH_FLAG")
            seen_epochs.add(epoch)
        elif epoch > last_expected:
            break
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise PrimaryEvaluationError("TRUNCATED_SPECIAL_EVENT_RECORD")
            continue
        if flag not in {0, 1, 6}:
            raise PrimaryEvaluationError(f"UNSUPPORTED_EPOCH_FLAG:{flag}")
        for _ in range(satellite_count):
            satellite, fields = _read_satellite_record(reader, system_types)
            if not in_window or satellite not in SATELLITES:
                continue
            link = (epoch, satellite)
            if link in seen_links:
                raise MeasurementInvalid("DUPLICATE_TARGET_SATELLITE_RECORD")
            seen_links.add(link)
            row = epoch_index[epoch]
            satellite_index = SATELLITES.index(satellite)
            for observation_index, observable in enumerate(OBSERVABLES):
                field_index = selected_index[observable]
                if field_index >= len(fields):
                    raise MeasurementInvalid(
                        "MISSING_REQUIRED_OBSERVATION_FIELD"
                    )
                value, field_lli = _parse_observation_field(fields[field_index])
                if value is None or not np.isfinite(value):
                    raise MeasurementInvalid(
                        "MISSING_OR_NONFINITE_REQUIRED_OBSERVATION"
                    )
                values[row, satellite_index, observation_index] = value
                if observable in PHASE_OBSERVABLES:
                    phase_index = PHASE_OBSERVABLES.index(observable)
                    lli[row, satellite_index, phase_index] = field_lli
    if seen_epochs != set(expected_epochs):
        raise MeasurementInvalid("MISSING_FROZEN_EPOCH")
    required_links = {
        (epoch, satellite)
        for epoch in expected_epochs
        for satellite in SATELLITES
    }
    if seen_links != required_links:
        raise MeasurementInvalid("MISSING_FROZEN_LINK")
    if not np.all(np.isfinite(values)) or np.any(lli < 0):
        raise MeasurementInvalid("MISSING_FROZEN_LINK_OR_OBSERVABLE")


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        integer_second = int(round(second))
        if abs(second - integer_second) > 1e-7:
            raise MeasurementInvalid("SUBSECOND_EPOCH_IN_FROZEN_WINDOW")
        epoch = datetime(
            int(parts[1]),
            int(parts[2]),
            int(parts[3]),
            int(parts[4]),
            int(parts[5]),
            integer_second,
            tzinfo=timezone.utc,
        )
        return epoch, int(parts[7]), int(parts[8])
    except MeasurementInvalid:
        raise
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise PrimaryEvaluationError("INVALID_RINEX_EPOCH_RECORD") from exc


_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


def _read_satellite_record(
    reader: _LineReader,
    system_types: dict[str, tuple[str, ...]],
) -> tuple[str, tuple[bytes, ...]]:
    line = reader.readline()
    if not line or _SATELLITE_PATTERN.match(line[:3]) is None:
        raise PrimaryEvaluationError("INVALID_SATELLITE_RECORD")
    satellite = line[:3].decode("ascii")
    system = satellite[0]
    if system not in system_types:
        raise PrimaryEvaluationError("UNDECLARED_SATELLITE_SYSTEM")
    declared_fields = len(system_types[system])
    fields = list(_field_chunks(line[3:]))
    while len(fields) < declared_fields:
        continuation = reader.readline()
        if not continuation:
            break
        if continuation.startswith(b">") or _SATELLITE_PATTERN.match(
            continuation[:3]
        ):
            reader.push(continuation)
            break
        if not continuation.startswith(b"   "):
            raise PrimaryEvaluationError("AMBIGUOUS_OBSERVATION_CONTINUATION")
        fields.extend(_field_chunks(continuation[3:]))
    if len(fields) > declared_fields:
        raise PrimaryEvaluationError(
            "OBSERVATION_FIELD_COUNT_EXCEEDS_DECLARATION"
        )
    return satellite, tuple(fields)


def _field_chunks(payload: bytes) -> tuple[bytes, ...]:
    payload = payload.rstrip(b"\r\n")
    if not payload:
        return ()
    full_fields, remainder = divmod(len(payload), 16)
    if remainder not in (0, 14):
        raise PrimaryEvaluationError(
            "PARTIAL_FIXED_WIDTH_OBSERVATION_FIELD"
        )
    count = full_fields + int(remainder > 0)
    padded = payload.ljust(count * 16, b" ")
    return tuple(
        padded[index : index + 16]
        for index in range(0, len(padded), 16)
    )


def _parse_observation_field(field: bytes) -> tuple[float | None, int]:
    value_bytes = field[:14].strip()
    if not value_bytes:
        return None, 0
    try:
        value = float(value_bytes.replace(b"D", b"E"))
    except ValueError as exc:
        raise MeasurementInvalid("AMBIGUOUS_OBSERVATION_SCALAR") from exc
    lli_byte = field[14:15]
    if lli_byte in (b"", b" "):
        lli = 0
    elif lli_byte.isdigit():
        lli = int(lli_byte)
    else:
        raise MeasurementInvalid("AMBIGUOUS_LLI")
    return value, lli


def validate_station(window: StationWindow) -> dict[str, object]:
    expected_shape = (RAW_RECORDS, 2, len(OBSERVABLES))
    if window.values.shape != expected_shape:
        raise MeasurementInvalid("FROZEN_ARRAY_SHAPE_CHANGED")
    if window.lli.shape != (RAW_RECORDS, 2, len(PHASE_OBSERVABLES)):
        raise MeasurementInvalid("FROZEN_LLI_ARRAY_SHAPE_CHANGED")
    if np.any(window.lli != 0):
        raise MeasurementInvalid("NONZERO_LLI_IN_USED_PHASE_STREAM")
    phase_l1 = window.values[:, :, OBSERVABLES.index("L1C")]
    phase_l2 = window.values[:, :, OBSERVABLES.index("L2W")]
    geometry_free_m = (
        screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L1_HZ * phase_l1
        - screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L2_HZ * phase_l2
    )
    second_difference = np.diff(geometry_free_m, n=2, axis=0)
    maximum = float(np.max(np.abs(second_difference)))
    geometry_free_m.fill(0.0)
    second_difference.fill(0.0)
    if maximum > GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M:
        raise MeasurementInvalid("GEOMETRY_FREE_PHASE_DISCONTINUITY")
    return {
        "station_id": window.station_id,
        "epoch_records": RAW_RECORDS,
        "required_link_observation_fields": (
            RAW_RECORDS * 2 * len(OBSERVABLES)
        ),
        "nonzero_lli": 0,
        "maximum_geometry_free_second_difference_m": maximum,
        "geometry_free_limit_m": GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
        "code_witnesses": "PRESENT_ALL_LINKS_ALL_EPOCHS",
        "snr_witnesses": (
            "PRESENT_ALL_LINKS_ALL_EPOCHS_NO_MAGNITUDE_THRESHOLD"
        ),
    }


def observed_coordinate(left: StationWindow, right: StationWindow) -> np.ndarray:
    if left.epochs_gps != right.epochs_gps:
        raise MeasurementInvalid("STATION_EPOCH_GRIDS_DIFFER")
    alpha, beta = envelope.ionosphere_free_coefficients()
    wavelength_l1 = screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L1_HZ
    wavelength_l2 = screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L2_HZ

    def ionosphere_free(window: StationWindow) -> np.ndarray:
        l1 = window.values[:, :, OBSERVABLES.index("L1C")]
        l2 = window.values[:, :, OBSERVABLES.index("L2W")]
        return alpha * wavelength_l1 * l1 + beta * wavelength_l2 * l2

    left_if = ionosphere_free(left)
    right_if = ionosphere_free(right)
    path_dd = (
        (left_if[:, 0] - left_if[:, 1])
        - (right_if[:, 0] - right_if[:, 1])
    )
    frequency = (
        -envelope.GPS_L1_HZ
        / screen.SPEED_OF_LIGHT_M_S
        * (path_dd[2:] - path_dd[:-2])
        / DERIVATIVE_BASELINE_S
    )
    left_if.fill(0.0)
    right_if.fill(0.0)
    path_dd.fill(0.0)
    if frequency.shape != (FEATURE_RECORDS,) or not np.all(
        np.isfinite(frequency)
    ):
        frequency.fill(0.0)
        raise MeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    return frequency


def prediction_curves(navigation: Path) -> dict[str, np.ndarray]:
    """Compile frozen broadcast hypotheses without observation input."""
    try:
        screen.validate_navigation(navigation)
        records = screen.parse_gps_navigation(navigation)
        epochs_utc = tuple(
            epoch - timedelta(seconds=GPS_MINUS_UTC_S)
            for epoch in frozen_epoch_grid()
        )
        stations = (
            review.STATIONS["KIRU00SWE"],
            review.STATIONS["MAT100ITA"],
        )
        station_ecef = {
            station.station_id: screen.station_to_ecef(station)
            for station in stations
        }
        fractional: dict[tuple[str, str], np.ndarray] = {}
        for satellite in (TARGET, REFERENCE, WRONG_TARGET):
            if satellite not in records:
                raise PrimaryEvaluationError(
                    f"NAVIGATION_SATELLITE_MISSING:{satellite}"
                )
            positions = np.asarray(
                [
                    screen.broadcast_ecef(
                        screen.select_ephemeris(records[satellite], epoch),
                        epoch,
                    )
                    for epoch in epochs_utc
                ],
                dtype=np.float64,
            )
            for station in stations:
                fractional[(station.station_id, satellite)] = (
                    screen.fractional_doppler(
                        positions, station_ecef[station.station_id], STEP_S
                    )
                )
            positions.fill(0.0)
        left_id, right_id = (station.station_id for station in stations)

        def curve(target: str) -> np.ndarray:
            return screen.double_difference_hz(
                fractional[(left_id, target)],
                fractional[(left_id, REFERENCE)],
                fractional[(right_id, target)],
                fractional[(right_id, REFERENCE)],
            )[1:-1].copy()

        nominal = curve(TARGET)
        wrong = curve(WRONG_TARGET)
        if nominal.shape != (FEATURE_RECORDS,) or wrong.shape != nominal.shape:
            raise PrimaryEvaluationError("PREDICTION_GRID_CHANGED")
        if not np.all(np.isfinite(nominal)) or not np.all(np.isfinite(wrong)):
            raise PrimaryEvaluationError("NONFINITE_PREDICTION")
        return {
            "H_G20": nominal,
            "H_AFFINE": np.zeros_like(nominal),
            "H_G14": wrong,
        }
    except PrimaryEvaluationError:
        raise
    except Exception as exc:
        raise PrimaryEvaluationError("NAVIGATION_COMPILATION_FAILED") from exc
    finally:
        if "fractional" in locals():
            for item in fractional.values():
                item.fill(0.0)


def prefix_calibration(
    observed: np.ndarray, hypothesis: np.ndarray
) -> dict[str, object]:
    if observed.shape != (FEATURE_RECORDS,) or hypothesis.shape != observed.shape:
        raise PrimaryEvaluationError("SCORE_GRID_CHANGED")
    residual = observed - hypothesis
    elapsed = np.arange(FEATURE_RECORDS, dtype=np.float64) * STEP_S
    design = np.column_stack(
        (np.ones(CALIBRATION_RECORDS), elapsed[:CALIBRATION_RECORDS])
    )
    coefficients, *_ = np.linalg.lstsq(
        design, residual[:CALIBRATION_RECORDS], rcond=None
    )
    prefix = residual[:CALIBRATION_RECORDS] - design @ coefficients
    result: dict[str, object] = {
        "coefficients": coefficients.copy(),
        "prefix_constant_hz": float(coefficients[0]),
        "prefix_slope_hz_s": float(coefficients[1]),
        "calibration_peak_to_peak_hz": float(np.ptp(prefix)),
        "calibration_rms_hz": float(
            np.sqrt(np.mean(prefix * prefix))
        ),
    }
    residual.fill(0.0)
    elapsed.fill(0.0)
    design.fill(0.0)
    coefficients.fill(0.0)
    prefix.fill(0.0)
    return result


def score_hypothesis(
    observed: np.ndarray,
    hypothesis: np.ndarray,
    calibration: dict[str, object] | None = None,
) -> dict[str, float]:
    fitted = calibration or prefix_calibration(observed, hypothesis)
    coefficients = np.asarray(
        fitted["coefficients"], dtype=np.float64
    ).copy()
    residual = observed - hypothesis
    elapsed = np.arange(FEATURE_RECORDS, dtype=np.float64) * STEP_S
    projected = residual - (
        coefficients[0] + coefficients[1] * elapsed
    )
    heldout = projected[CALIBRATION_RECORDS:]
    result = {
        "prefix_constant_hz": float(fitted["prefix_constant_hz"]),
        "prefix_slope_hz_s": float(fitted["prefix_slope_hz_s"]),
        "calibration_peak_to_peak_hz": float(
            fitted["calibration_peak_to_peak_hz"]
        ),
        "calibration_rms_hz": float(fitted["calibration_rms_hz"]),
        "heldout_peak_to_peak_hz": float(np.ptp(heldout)),
        "heldout_rms_hz": float(
            np.sqrt(np.mean(heldout * heldout))
        ),
    }
    coefficients.fill(0.0)
    residual.fill(0.0)
    elapsed.fill(0.0)
    projected.fill(0.0)
    if calibration is None:
        original = fitted.get("coefficients")
        if isinstance(original, np.ndarray):
            original.fill(0.0)
    return result


def evaluate_observed(
    observed: np.ndarray,
    hypotheses: dict[str, np.ndarray],
) -> tuple[
    str,
    dict[str, dict[str, float]],
    dict[str, float],
    dict[str, float | str],
]:
    if tuple(hypotheses) != HYPOTHESES:
        raise PrimaryEvaluationError("HYPOTHESIS_ORDER_CHANGED")
    nominal_prefix = prefix_calibration(observed, hypotheses["H_G20"])
    try:
        nominal_peak = float(
            nominal_prefix["calibration_peak_to_peak_hz"]
        )
        detectability: dict[str, float | str] = {
            "nominal_prefix_peak_to_peak_hz": nominal_peak,
            "nominal_prefix_rms_hz": float(
                nominal_prefix["calibration_rms_hz"]
            ),
            "maximum_admissible_peak_to_peak_hz": (
                ONE_MODEL_ADMISSION_ENVELOPE_HZ
            ),
        }
        if nominal_peak > ONE_MODEL_ADMISSION_ENVELOPE_HZ:
            detectability["clause"] = "UNSATISFIED"
            return "NOT_DETECTABLE", {}, {}, detectability
        detectability["clause"] = "SATISFIED"
        scores = {
            "H_G20": score_hypothesis(
                observed, hypotheses["H_G20"], nominal_prefix
            ),
            "H_AFFINE": score_hypothesis(
                observed, hypotheses["H_AFFINE"]
            ),
            "H_G14": score_hypothesis(
                observed, hypotheses["H_G14"]
            ),
        }
    finally:
        coefficients = nominal_prefix.get("coefficients")
        if isinstance(coefficients, np.ndarray):
            coefficients.fill(0.0)
    heldout = {
        name: score["heldout_peak_to_peak_hz"]
        for name, score in scores.items()
    }
    margins = {
        name: float(
            min(value for other, value in heldout.items() if other != name)
            - heldout[name]
        )
        for name in HYPOTHESES
    }
    preferred = [
        name
        for name, margin in margins.items()
        if margin > PAIRWISE_DECISION_GUARD_HZ
    ]
    if preferred == ["H_G20"]:
        outcome = "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    elif preferred == ["H_AFFINE"]:
        outcome = "PREFIX_AFFINE_NULL_PREFERRED"
    elif preferred == ["H_G14"]:
        outcome = "WRONG_ORBIT_G14_PREFERRED"
    else:
        outcome = "AMBIGUOUS"
    return outcome, scores, margins, detectability


def load_strict_json(path: Path, failure: str) -> tuple[dict[str, object], str]:
    raw = Path(path).read_bytes()
    digest = sha256(raw).hexdigest()
    try:
        value = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise PrimaryEvaluationError(failure) from exc
    if not isinstance(value, dict):
        raise PrimaryEvaluationError(failure)
    return value, digest


def verify_seal(
    seal_path: Path, source_path: Path
) -> tuple[dict[str, object], str]:
    seal, seal_sha256 = load_strict_json(
        seal_path, "FROZEN_EVALUATOR_MANIFEST_INVALID"
    )
    if seal.get("schema") != "gnss-independent-primary-evaluator-seal-v1":
        raise PrimaryEvaluationError("FROZEN_EVALUATOR_MANIFEST_INVALID")
    if seal.get("runtime_manifest_sha256") != runtime_manifest_sha256():
        raise PrimaryEvaluationError("RUNTIME_MANIFEST_CHANGED")
    if seal.get("evaluator_source_sha256") != file_sha256(source_path):
        raise PrimaryEvaluationError("EVALUATOR_SOURCE_CHANGED")
    if seal.get("plan_sha256") != PLAN_SHA256:
        raise PrimaryEvaluationError("PLAN_BINDING_CHANGED")
    if not re.fullmatch(r"[0-9a-f]{40}", str(seal.get("source_commit", ""))):
        raise PrimaryEvaluationError("SOURCE_COMMIT_BINDING_INVALID")
    return seal, seal_sha256


def verify_authority(
    authority_path: Path,
    seal: dict[str, object],
    seal_sha256: str,
) -> tuple[dict[str, object], str]:
    authority, authority_sha256 = load_strict_json(
        authority_path, "PRIMARY_ACCESS_AUTHORITY_INVALID"
    )
    expected = {
        "schema": "gnss-independent-primary-access-authority-v1",
        "state": "PRIMARY_ACCESS_AUTHORIZED",
        "plan_sha256": PLAN_SHA256,
        "prospective_markdown_sha256": PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "evaluator_source_sha256": seal["evaluator_source_sha256"],
        "source_commit": seal["source_commit"],
        "single_run": True,
        "products": [item["name"] for item in PRIMARY_PRODUCTS],
    }
    for name, value in expected.items():
        if authority.get(name) != value:
            raise PrimaryEvaluationError(
                f"PRIMARY_ACCESS_AUTHORITY_BINDING_CHANGED:{name}"
            )
    return authority, authority_sha256


def validate_materialization(
    materialization_path: Path,
    product_paths: dict[str, Path],
) -> tuple[tuple[ProductAuthority, ...], str]:
    try:
        materialization, receipt_sha256 = load_strict_json(
            materialization_path, "PRIMARY_MATERIALIZATION_RECEIPT_INVALID"
        )
    except PrimaryEvaluationError as exc:
        raise ArtifactMaterializationFailed(str(exc)) from exc
    if (
        materialization.get("schema")
        != "gnss-independent-primary-materialization-v1"
        or materialization.get("state") != "PRIMARY_ARTIFACTS_MATERIALIZED"
        or materialization.get("plan_sha256") != PLAN_SHA256
        or materialization.get("hashes_completed_before_decompression")
        is not True
    ):
        raise ArtifactMaterializationFailed(
            "PRIMARY_MATERIALIZATION_BINDING_CHANGED"
        )
    entries = materialization.get("artifacts")
    if not isinstance(entries, list) or len(entries) != len(
        PRIMARY_PRODUCTS
    ):
        raise ArtifactMaterializationFailed(
            "PRIMARY_MATERIALIZATION_ARTIFACTS_INVALID"
        )
    by_station = {
        item.get("station_id"): item
        for item in entries
        if isinstance(item, dict)
    }
    authorities: list[ProductAuthority] = []
    for spec in PRIMARY_PRODUCTS:
        station_id = str(spec["station_id"])
        entry = by_station.get(station_id)
        path = Path(product_paths[station_id])
        if not isinstance(entry, dict):
            raise ArtifactMaterializationFailed(
                f"MATERIALIZATION_STATION_MISSING:{station_id}"
            )
        digest = entry.get("sha256")
        if not isinstance(digest, str) or re.fullmatch(
            r"[0-9a-f]{64}", digest
        ) is None:
            raise ArtifactMaterializationFailed(
                f"MATERIALIZATION_SHA256_INVALID:{station_id}"
            )
        if (
            entry.get("name") != spec["name"]
            or entry.get("bytes") != spec["bytes"]
            or path.name != spec["name"]
            or not path.is_file()
        ):
            raise ArtifactMaterializationFailed(
                f"PRIMARY_PRODUCT_IDENTITY_CHANGED:{station_id}"
            )
        if path.stat().st_size != spec["bytes"]:
            raise ArtifactMaterializationFailed(
                f"PRIMARY_BYTE_COUNT_CHANGED:{station_id}"
            )
        if file_sha256(path) != digest:
            raise ArtifactMaterializationFailed(
                f"PRIMARY_SHA256_CHANGED:{station_id}"
            )
        authorities.append(
            ProductAuthority(
                station_id=station_id,
                name=str(spec["name"]),
                url="SEALED_HISTORICAL_PRODUCT_NO_NETWORK_SURFACE",
                bytes=int(spec["bytes"]),
                sha256=digest,
            )
        )
    if len(by_station) != len(PRIMARY_PRODUCTS):
        raise ArtifactMaterializationFailed(
            "PRIMARY_MATERIALIZATION_PRODUCT_SET_CHANGED"
        )
    return tuple(authorities), receipt_sha256


def decode_exact_station(
    path: Path, authority: ProductAuthority
) -> StationWindow:
    try:
        decompressed = hatanaka.decompress(Path(path), strict=True)
    except Exception as exc:
        raise PrimaryEvaluationError("HATANAKA_DECODING_FAILED") from exc
    decoded = bytearray(decompressed)
    del decompressed
    try:
        return parse_plain_rinex_window(
            decoded, authority.station_id, frozen_epoch_grid()
        )
    finally:
        decoded[:] = b"\x00" * len(decoded)


def claim_scope(outcome: str) -> dict[str, object]:
    compared = {
        "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "PREFIX_AFFINE_NULL_PREFERRED",
        "WRONG_ORBIT_G14_PREFERRED",
        "AMBIGUOUS",
    }
    return {
        "authorized": (
            "MODEL_CONDITIONED_FORWARD_COMPARISON_FOR_FROZEN_KIRU_MAT1_COORDINATE"
            if outcome in compared
            else "MEASUREMENT_PATH_OUTCOME_ONLY"
        ),
        "not_authorized": [
            "SATELLITE_IDENTITY",
            "ORBIT_RECONSTRUCTION",
            "REPEATED_PASS_GENERALIZATION",
            "CLAIM_OUTSIDE_KIRU_MAT1_G20_G22_COORDINATE",
        ],
    }


def materialization_failure_receipt(
    reason: str,
    seal_sha256: str,
    authority_sha256: str,
) -> dict[str, object]:
    return {
        "schema": "gnss-independent-primary-premeasurement-outcome-v1",
        "plan_sha256": PLAN_SHA256,
        "evaluator_seal_sha256": seal_sha256,
        "authority_receipt_sha256": authority_sha256,
        "outcome": "ARTIFACT_MATERIALIZATION_FAILED",
        "reason": reason,
        "physical_decision": "NOT_EVALUATED",
        "decompression_started": False,
        "measurement_clauses": {
            "artifact_materialization": "UNSATISFIED",
            "header_and_measurement_admission": "NOT_EVALUATED",
            "calibration_detectability": "NOT_EVALUATED",
            "heldout_model_comparison": "NOT_EVALUATED",
        },
        "claims": {
            "authorized": "PREMEASUREMENT_FAILURE_ONLY",
            "not_authorized": list(claim_scope("MEASUREMENT_INVALID")["not_authorized"]),
        },
        "retry": "SAME_PRODUCTS_TRANSPORT_RESUME_PERMITTED_BEFORE_DECOMPRESSION",
    }


def run_once(
    kiru_path: Path,
    mat1_path: Path,
    navigation_path: Path,
    seal_path: Path,
    authority_path: Path,
    materialization_path: Path,
    output_path: Path,
) -> dict[str, object]:
    """Execute exactly one authorized primary comparison.

    Seal, authority, complete-file hashes, and navigation are checked before
    decompression. The caller must provide a new output path; this module never
    deletes or overwrites a receipt.
    """
    output_path = Path(output_path)
    if output_path.exists():
        raise PrimaryEvaluationError("PRIMARY_OUTPUT_ALREADY_EXISTS")
    seal, seal_sha256 = verify_seal(seal_path, Path(__file__))
    _, authority_sha256 = verify_authority(
        authority_path, seal, seal_sha256
    )
    try:
        authorities, materialization_sha256 = validate_materialization(
            materialization_path,
            {
                "KIRU00SWE": Path(kiru_path),
                "MAT100ITA": Path(mat1_path),
            },
        )
    except ArtifactMaterializationFailed as exc:
        receipt = materialization_failure_receipt(
            str(exc), seal_sha256, authority_sha256
        )
        write_receipt_exclusive(output_path, receipt)
        return receipt

    try:
        navigation = screen.validate_navigation(navigation_path)
        hypotheses = prediction_curves(navigation_path)
    except Exception as exc:
        for hypothesis in locals().get("hypotheses", {}).values():
            hypothesis.fill(0.0)
        if isinstance(exc, PrimaryEvaluationError):
            raise
        raise PrimaryEvaluationError(
            "PREMEASUREMENT_NAVIGATION_COMPILATION_FAILED"
        ) from exc

    windows: list[StationWindow] = []
    observed: np.ndarray | None = None
    decompression_started = False
    try:
        try:
            decompression_started = True
            kiru = decode_exact_station(kiru_path, authorities[0])
            windows.append(kiru)
            mat1 = decode_exact_station(mat1_path, authorities[1])
            windows.append(mat1)
            health = [
                validate_station(window) for window in windows
            ]
            observed = observed_coordinate(kiru, mat1)
            outcome, scores, margins, detectability = evaluate_observed(
                observed, hypotheses
            )
            receipt: dict[str, object] = {
                "schema": "gnss-independent-primary-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "evaluator_seal": {
                    "sha256": seal_sha256,
                    "source_commit": seal["source_commit"],
                    "evaluator_source_sha256": seal[
                        "evaluator_source_sha256"
                    ],
                    "runtime_manifest_sha256": seal[
                        "runtime_manifest_sha256"
                    ],
                },
                "authority_receipt_sha256": authority_sha256,
                "materialization_receipt_sha256": (
                    materialization_sha256
                ),
                "artifacts": [
                    {
                        "station_id": item.station_id,
                        "name": item.name,
                        "bytes": item.bytes,
                        "sha256": item.sha256,
                    }
                    for item in authorities
                ],
                "navigation": navigation,
                "measurement_health": health,
                "observation_access": {
                    "station_epoch_records_decoded": RAW_RECORDS * 2,
                    "required_observation_values_decoded": (
                        RAW_RECORDS
                        * 2
                        * 2
                        * len(OBSERVABLES)
                    ),
                    "feature_records_constructed_in_ram": (
                        FEATURE_RECORDS
                    ),
                },
                "feature_records": FEATURE_RECORDS,
                "calibration_records": CALIBRATION_RECORDS,
                "heldout_records": HELDOUT_RECORDS,
                "detectability": detectability,
                "scores": scores,
                "preference_margins_hz": margins,
                "pairwise_decision_guard_hz": (
                    PAIRWISE_DECISION_GUARD_HZ
                ),
                "clauses": {
                    "artifact_hashes": "SATISFIED",
                    "primary_header_semantics": "SATISFIED",
                    "exact_epoch_continuity": "SATISFIED",
                    "required_phase_code_snr": "SATISFIED",
                    "finite_numeric_values": "SATISFIED",
                    "zero_lli": "SATISFIED",
                    "geometry_free_phase_continuity": "SATISFIED",
                    "calibration_detectability": detectability["clause"],
                    "heldout_model_comparison": (
                        "NOT_EVALUATED"
                        if outcome == "NOT_DETECTABLE"
                        else "EVALUATED"
                    ),
                },
                "outcome": outcome,
                "claims": claim_scope(outcome),
                "decompression_started": decompression_started,
                "raw_or_derived_measurement_persisted": False,
                "alternate_run_authorized": False,
            }
            strict_json(receipt)
        except MeasurementInvalid as exc:
            outcome = "MEASUREMENT_INVALID"
            receipt = {
                "schema": "gnss-independent-primary-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "evaluator_seal_sha256": seal_sha256,
                "authority_receipt_sha256": authority_sha256,
                "materialization_receipt_sha256": (
                    materialization_sha256
                ),
                "outcome": outcome,
                "reason": str(exc),
                "clauses": {
                    "measurement_admission": "UNSATISFIED",
                    "calibration_detectability": "NOT_EVALUATED",
                    "heldout_model_comparison": "NOT_EVALUATED",
                },
                "claims": claim_scope(outcome),
                "decompression_started": decompression_started,
                "raw_or_derived_measurement_persisted": False,
                "alternate_run_authorized": False,
            }
        except PrimaryEvaluationError as exc:
            outcome = "PRIMARY_EVALUATION_ERROR"
            receipt = {
                "schema": "gnss-independent-primary-nonphysical-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "evaluator_seal_sha256": seal_sha256,
                "authority_receipt_sha256": authority_sha256,
                "materialization_receipt_sha256": (
                    materialization_sha256
                ),
                "outcome": outcome,
                "reason": str(exc),
                "physical_decision": "NOT_EVALUATED",
                "clauses": {
                    "measurement_admission": "NOT_EVALUATED",
                    "calibration_detectability": "NOT_EVALUATED",
                    "heldout_model_comparison": "NOT_EVALUATED",
                },
                "decompression_started": decompression_started,
                "raw_or_derived_measurement_persisted": False,
                "alternate_run_authorized": False,
            }
        except Exception as exc:
            outcome = "PRIMARY_EVALUATION_ERROR"
            receipt = {
                "schema": "gnss-independent-primary-nonphysical-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "evaluator_seal_sha256": seal_sha256,
                "outcome": outcome,
                "reason": f"UNEXPECTED_EVALUATOR_FAILURE:{type(exc).__name__}",
                "physical_decision": "NOT_EVALUATED",
                "clauses": {
                    "measurement_admission": "NOT_EVALUATED",
                    "calibration_detectability": "NOT_EVALUATED",
                    "heldout_model_comparison": "NOT_EVALUATED",
                },
                "decompression_started": decompression_started,
                "raw_or_derived_measurement_persisted": False,
                "alternate_run_authorized": False,
            }
        if (
            outcome not in ALLOWED_PHYSICAL_OUTCOMES
            and outcome != "PRIMARY_EVALUATION_ERROR"
        ):
            raise PrimaryEvaluationError("NON_FROZEN_TERMINAL_OUTCOME")
        write_receipt_exclusive(output_path, receipt)
        return receipt
    finally:
        for window in windows:
            window.erase()
        if observed is not None:
            observed.fill(0.0)
        for hypothesis in hypotheses.values():
            hypothesis.fill(0.0)


def write_receipt_exclusive(
    path: Path, receipt: dict[str, object]
) -> None:
    payload = strict_json(receipt) + "\n"
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        stream.write(payload)


def format_gps_label(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S GPS")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    _validate_standard_json(value)
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _validate_standard_json(value: object) -> None:
    if isinstance(value, np.generic):
        raise TypeError("NUMPY_SCALAR_NOT_ALLOWED_IN_RECEIPT")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NONFINITE_SCALAR_NOT_ALLOWED_IN_RECEIPT")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("NON_STRING_JSON_KEY")
            _validate_standard_json(item)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_standard_json(item)
        return
    raise TypeError(f"NON_STANDARD_JSON_VALUE:{type(value).__name__}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kiru", type=Path, required=True)
    parser.add_argument("--mat1", type=Path, required=True)
    parser.add_argument("--navigation", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--materialization", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = run_once(
        args.kiru,
        args.mat1,
        args.navigation,
        args.seal,
        args.authority,
        args.materialization,
        args.output,
    )
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
