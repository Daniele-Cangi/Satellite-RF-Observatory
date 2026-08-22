"""One-shot evaluator for the frozen GOLD/NLIB G11/G21 experiment.

Only the exact-hash CRINEX artifacts, six frozen observables, two satellites,
and one epoch window are accepted. Decompressed RINEX and observations remain
in RAM and are overwritten; the output receipt contains scalars only.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import io
import json
from pathlib import Path
import re
from typing import Final, Sequence

import hatanaka
import numpy as np

from experiments.orbital_discriminability import (
    gnss_double_difference_envelope as envelope,
)
from experiments.orbital_discriminability import gnss_double_difference_screen as screen
from experiments.orbital_discriminability import gnss_observation_header as headers


DECODER_VERSION: Final = "gnss-dd-frozen-measurement-v1"
PLAN_NAME: Final = "GNSS_DOUBLE_DIFFERENCE_PROSPECTIVE_PLAN.md"
PLAN_SHA256: Final = "e3eaa0d1974ce4b415182aaa47451174aaa9296b61e31c296f2cda1e8eda86f4"
AUTHORITY_TOKEN: Final = "USER_AUTHORIZED_FROZEN_PLAN_FC3A605"
TARGET: Final = "G11"
REFERENCE: Final = "G21"
WRONG_TARGET: Final = "G12"
SATELLITES: Final = (TARGET, REFERENCE)
OBSERVABLES: Final = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
PHASE_OBSERVABLES: Final = ("L1C", "L2W")
RAW_START_GPS: Final = datetime(2026, 8, 3, 10, 1, 30, tzinfo=timezone.utc)
RAW_STOP_GPS: Final = datetime(2026, 8, 3, 13, 14, 0, tzinfo=timezone.utc)
RAW_RECORDS: Final = 386
FEATURE_RECORDS: Final = 384
CALIBRATION_RECORDS: Final = 77
HELDOUT_RECORDS: Final = 307
STEP_S: Final = 30.0
DERIVATIVE_BASELINE_S: Final = 60.0
GPS_MINUS_UTC_S: Final = 18.0
ONE_MODEL_ADMISSION_ENVELOPE_HZ: Final = 363.08560578999004
PAIRWISE_DECISION_GUARD_HZ: Final = 726.1712115799801
MINIMUM_WAVELENGTH_M: Final = min(
    screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L1_HZ,
    screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L2_HZ,
)
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.5 * MINIMUM_WAVELENGTH_M
ALLOWED_OUTCOMES: Final = (
    "MEASUREMENT_INVALID",
    "NOT_DETECTABLE",
    "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
    "PREFIX_AFFINE_NULL_PREFERRED",
    "WRONG_ORBIT_G12_PREFERRED",
    "AMBIGUOUS",
)


class MeasurementInvalid(ValueError):
    """A frozen physical-measurement admission clause failed."""


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
            raise RuntimeError("only one line of pushback is permitted")
        self._pending = line


def frozen_epoch_grid() -> tuple[datetime, ...]:
    epochs = []
    current = RAW_START_GPS
    while current <= RAW_STOP_GPS:
        epochs.append(current)
        current += timedelta(seconds=STEP_S)
    if len(epochs) != RAW_RECORDS:
        raise RuntimeError("frozen raw epoch count changed")
    return tuple(epochs)


def decoder_manifest() -> dict[str, object]:
    return {
        "decoder_version": DECODER_VERSION,
        "plan": {"name": PLAN_NAME, "sha256": PLAN_SHA256},
        "dependencies": {
            "python_package_hatanaka": "2.8.1",
            "python_package_ncompress": "1.0.2",
            "numpy": importlib.metadata.version("numpy"),
        },
        "artifacts": [
            {
                "station_id": authority.station_id,
                "name": authority.name,
                "bytes": authority.bytes,
                "sha256": authority.sha256,
            }
            for authority in headers.AUTHORITIES
        ],
        "coordinate": envelope.physical_coordinate(),
        "parameters": {
            "target": TARGET,
            "reference": REFERENCE,
            "wrong_target": WRONG_TARGET,
            "observables": list(OBSERVABLES),
            "raw_start_gps": format_gps_label(RAW_START_GPS),
            "raw_stop_gps": format_gps_label(RAW_STOP_GPS),
            "raw_records": RAW_RECORDS,
            "feature_records": FEATURE_RECORDS,
            "calibration_records": CALIBRATION_RECORDS,
            "heldout_records": HELDOUT_RECORDS,
            "epoch_step_s": STEP_S,
            "central_derivative_baseline_s": DERIVATIVE_BASELINE_S,
            "gps_minus_utc_s": GPS_MINUS_UTC_S,
            "geometry_free_slip_coordinate": (
                "ABS_SECOND_DIFFERENCE_OF_LAMBDA1_L1C_MINUS_LAMBDA2_L2W"
            ),
            "geometry_free_second_difference_limit_m": GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
            "geometry_free_limit_basis": "HALF_OF_SHORTEST_USED_CARRIER_WAVELENGTH",
            "signal_strength_rule": "PRESENCE_AND_CONTINUITY_ONLY",
            "one_model_admission_envelope_hz": ONE_MODEL_ADMISSION_ENVELOPE_HZ,
            "pairwise_decision_guard_hz": PAIRWISE_DECISION_GUARD_HZ,
        },
        "scoring": (
            "HELDOUT_PEAK_TO_PEAK_AFTER_CONSTANT_AND_SLOPE_FIT_ON_FIRST_77_FEATURES_ONLY"
        ),
        "zero_persistence": {
            "decompressed_rinex": "RAM_BYTEARRAY_OVERWRITTEN_IN_FINALLY",
            "observation_arrays": "OVERWRITTEN_IN_FINALLY",
            "receipt": "HASHES_COUNTS_AND_SCALARS_ONLY",
        },
        "forbidden": [
            "alternate station target reference signal or epoch window",
            "suffix nuisance fitting",
            "post-access threshold changes",
            "interpolation across missing epochs",
            "persistence of decompressed RINEX or observation arrays",
            "satellite identity claim",
        ],
    }


def decoder_manifest_sha256() -> str:
    return sha256(strict_json(decoder_manifest()).encode("ascii")).hexdigest()


def decode_exact_station(
    path: Path, authority: headers.ProductAuthority
) -> StationWindow:
    path = Path(path)
    headers.validate_artifact(path, authority)
    try:
        decoded_bytes = hatanaka.decompress(path, strict=True)
    except Exception as exc:
        raise MeasurementInvalid("HATANAKA_DECODING_FAILED") from exc
    decoded = bytearray(decoded_bytes)
    del decoded_bytes
    try:
        return parse_plain_rinex_window(
            decoded, authority.station_id, frozen_epoch_grid()
        )
    finally:
        decoded[:] = b"\x00" * len(decoded)


def parse_plain_rinex_window(
    decoded: bytearray,
    station_id: str,
    expected_epochs: Sequence[datetime],
) -> StationWindow:
    reader = _LineReader(decoded)
    system_types = _read_observation_types(reader)
    gps_types = system_types.get("G")
    if gps_types is None or any(item not in gps_types for item in OBSERVABLES):
        raise MeasurementInvalid("FROZEN_GPS_SIGNAL_FAMILY_MISSING")
    selected_index = {name: gps_types.index(name) for name in OBSERVABLES}
    epoch_index = {epoch: index for index, epoch in enumerate(expected_epochs)}
    if len(epoch_index) != len(expected_epochs):
        raise MeasurementInvalid("DUPLICATE_EXPECTED_EPOCH")
    values = np.full((len(expected_epochs), 2, 6), np.nan, dtype=np.float64)
    lli = np.full((len(expected_epochs), 2, 2), -1, dtype=np.int8)
    try:
        _fill_window(
            reader,
            system_types,
            selected_index,
            tuple(expected_epochs),
            epoch_index,
            values,
            lli,
        )
    except Exception:
        values.fill(0.0)
        lli.fill(0)
        raise
    return StationWindow(station_id, tuple(expected_epochs), values, lli)


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
    first_expected, last_expected = expected_epochs[0], expected_epochs[-1]
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise MeasurementInvalid("AMBIGUOUS_NON_EPOCH_RECORD")
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
                    raise MeasurementInvalid("TRUNCATED_SPECIAL_EVENT_RECORD")
            continue
        for _ in range(satellite_count):
            satellite, fields = _read_satellite_record(reader, system_types)
            if not in_window or satellite not in SATELLITES:
                continue
            row = epoch_index[epoch]
            sat_index = SATELLITES.index(satellite)
            for obs_index, observable in enumerate(OBSERVABLES):
                field_index = selected_index[observable]
                if field_index >= len(fields):
                    raise MeasurementInvalid("TRUNCATED_REQUIRED_OBSERVATION_RECORD")
                value, field_lli = _parse_observation_field(fields[field_index])
                if value is None or not np.isfinite(value):
                    raise MeasurementInvalid(
                        "MISSING_OR_NONFINITE_REQUIRED_OBSERVATION"
                    )
                values[row, sat_index, obs_index] = value
                if observable in PHASE_OBSERVABLES:
                    lli[row, sat_index, PHASE_OBSERVABLES.index(observable)] = field_lli
    if seen_epochs != set(expected_epochs):
        raise MeasurementInvalid("MISSING_FROZEN_EPOCH")
    if not np.all(np.isfinite(values)) or np.any(lli < 0):
        raise MeasurementInvalid("MISSING_FROZEN_LINK_OR_OBSERVABLE")


def _read_observation_types(reader: _LineReader) -> dict[str, tuple[str, ...]]:
    collected: dict[str, list[str]] = {}
    expected: dict[str, int] = {}
    current_system: str | None = None
    while True:
        line = reader.readline()
        if not line:
            raise MeasurementInvalid("DECOMPRESSED_HEADER_INCOMPLETE")
        body = line.rstrip(b"\r\n")
        label = body[60:80].decode("ascii").strip() if len(body) >= 60 else ""
        if label == "SYS / # / OBS TYPES":
            if body[:1] != b" ":
                current_system = body[:1].decode("ascii")
                try:
                    expected[current_system] = int(body[3:6])
                except ValueError as exc:
                    raise MeasurementInvalid("INVALID_OBSERVATION_TYPE_COUNT") from exc
                collected[current_system] = []
            if current_system is None:
                raise MeasurementInvalid("ORPHAN_OBSERVATION_TYPE_CONTINUATION")
            collected[current_system].extend(body[7:60].decode("ascii").split())
        if label == "END OF HEADER":
            break
    result = {}
    for system, count in expected.items():
        if len(collected[system]) < count:
            raise MeasurementInvalid("INCOMPLETE_OBSERVATION_TYPE_DECLARATION")
        result[system] = tuple(collected[system][:count])
    return result


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        parts = line.decode("ascii").split()
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
    except (IndexError, ValueError) as exc:
        if isinstance(exc, MeasurementInvalid):
            raise
        raise MeasurementInvalid("INVALID_RINEX_EPOCH_RECORD") from exc


_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


def _read_satellite_record(
    reader: _LineReader,
    system_types: dict[str, tuple[str, ...]],
) -> tuple[str, tuple[bytes, ...]]:
    line = reader.readline()
    if not line or not _SATELLITE_PATTERN.match(line):
        raise MeasurementInvalid("INVALID_SATELLITE_RECORD")
    satellite = line[:3].decode("ascii")
    system = satellite[0]
    if system not in system_types:
        raise MeasurementInvalid("UNDECLARED_SATELLITE_SYSTEM")
    expected_fields = len(system_types[system])
    fields = list(_field_chunks(line[3:]))
    while len(fields) < expected_fields:
        continuation = reader.readline()
        if not continuation:
            break
        if continuation.startswith(b">") or _SATELLITE_PATTERN.match(continuation):
            reader.push(continuation)
            break
        if not continuation.startswith(b"   "):
            raise MeasurementInvalid("AMBIGUOUS_OBSERVATION_CONTINUATION")
        fields.extend(_field_chunks(continuation[3:]))
    return satellite, tuple(fields[:expected_fields])


def _field_chunks(payload: bytes) -> tuple[bytes, ...]:
    payload = payload.rstrip(b"\r\n")
    if not payload:
        return ()
    count = (len(payload) + 15) // 16
    padded = payload.ljust(count * 16, b" ")
    return tuple(padded[index : index + 16] for index in range(0, len(padded), 16))


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
    if window.values.shape != (RAW_RECORDS, 2, 6) or window.lli.shape != (
        RAW_RECORDS,
        2,
        2,
    ):
        raise MeasurementInvalid("FROZEN_ARRAY_SHAPE_CHANGED")
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
        "required_link_observation_fields": RAW_RECORDS * 2 * len(OBSERVABLES),
        "nonzero_lli": 0,
        "maximum_geometry_free_second_difference_m": maximum,
        "geometry_free_limit_m": GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
        "code_witnesses": "PRESENT_ALL_LINKS_ALL_EPOCHS",
        "snr_witnesses": "PRESENT_ALL_LINKS_ALL_EPOCHS_NO_MAGNITUDE_THRESHOLD",
    }


def observed_coordinate(left: StationWindow, right: StationWindow) -> np.ndarray:
    alpha, beta = envelope.ionosphere_free_coefficients()
    wavelength_l1 = screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L1_HZ
    wavelength_l2 = screen.SPEED_OF_LIGHT_M_S / envelope.GPS_L2_HZ

    def ionosphere_free(window: StationWindow) -> np.ndarray:
        l1 = window.values[:, :, OBSERVABLES.index("L1C")]
        l2 = window.values[:, :, OBSERVABLES.index("L2W")]
        return alpha * wavelength_l1 * l1 + beta * wavelength_l2 * l2

    left_if = ionosphere_free(left)
    right_if = ionosphere_free(right)
    path_dd = (left_if[:, 0] - left_if[:, 1]) - (right_if[:, 0] - right_if[:, 1])
    frequency = (
        -envelope.GPS_L1_HZ
        / screen.SPEED_OF_LIGHT_M_S
        * (path_dd[2:] - path_dd[:-2])
        / DERIVATIVE_BASELINE_S
    )
    left_if.fill(0.0)
    right_if.fill(0.0)
    path_dd.fill(0.0)
    if frequency.size != FEATURE_RECORDS or not np.all(np.isfinite(frequency)):
        frequency.fill(0.0)
        raise MeasurementInvalid("OBSERVED_COORDINATE_INVALID")
    return frequency


def prediction_curves(navigation: Path) -> dict[str, np.ndarray]:
    screen.validate_navigation(navigation)
    records = screen.parse_gps_navigation(navigation)
    epochs_utc = tuple(
        epoch - timedelta(seconds=GPS_MINUS_UTC_S) for epoch in frozen_epoch_grid()
    )
    station_ecef = {
        station.station_id: screen.station_to_ecef(station)
        for station in screen.STATIONS
    }
    fractional: dict[tuple[str, str], np.ndarray] = {}
    for satellite in (TARGET, REFERENCE, WRONG_TARGET):
        positions = np.asarray(
            [
                screen.broadcast_ecef(
                    screen.select_ephemeris(records[satellite], epoch), epoch
                )
                for epoch in epochs_utc
            ]
        )
        for station in screen.STATIONS:
            fractional[(station.station_id, satellite)] = screen.fractional_doppler(
                positions, station_ecef[station.station_id], STEP_S
            )
        positions.fill(0.0)
    left, right = (station.station_id for station in screen.STATIONS)

    def curve(target: str) -> np.ndarray:
        return screen.double_difference_hz(
            fractional[(left, target)],
            fractional[(left, REFERENCE)],
            fractional[(right, target)],
            fractional[(right, REFERENCE)],
        )[1:-1].copy()

    nominal = curve(TARGET)
    wrong = curve(WRONG_TARGET)
    for item in fractional.values():
        item.fill(0.0)
    return {"H_G11": nominal, "H_AFFINE": np.zeros_like(nominal), "H_G12": wrong}


def score_hypothesis(observed: np.ndarray, hypothesis: np.ndarray) -> dict[str, float]:
    if observed.shape != (FEATURE_RECORDS,) or hypothesis.shape != observed.shape:
        raise MeasurementInvalid("SCORE_GRID_CHANGED")
    residual = observed - hypothesis
    elapsed = np.arange(FEATURE_RECORDS, dtype=np.float64) * STEP_S
    design = np.column_stack(
        (np.ones(CALIBRATION_RECORDS), elapsed[:CALIBRATION_RECORDS])
    )
    coefficients, *_ = np.linalg.lstsq(
        design, residual[:CALIBRATION_RECORDS], rcond=None
    )
    projected = residual - (coefficients[0] + coefficients[1] * elapsed)
    calibration = projected[:CALIBRATION_RECORDS]
    heldout = projected[CALIBRATION_RECORDS:]
    result = {
        "prefix_constant_hz": float(coefficients[0]),
        "prefix_slope_hz_s": float(coefficients[1]),
        "calibration_peak_to_peak_hz": float(np.ptp(calibration)),
        "calibration_rms_hz": float(np.sqrt(np.mean(calibration * calibration))),
        "heldout_peak_to_peak_hz": float(np.ptp(heldout)),
        "heldout_rms_hz": float(np.sqrt(np.mean(heldout * heldout))),
    }
    residual.fill(0.0)
    elapsed.fill(0.0)
    design.fill(0.0)
    projected.fill(0.0)
    return result


def evaluate_observed(
    observed: np.ndarray,
    hypotheses: dict[str, np.ndarray],
) -> tuple[str, dict[str, dict[str, float]], dict[str, float]]:
    names = ("H_G11", "H_AFFINE", "H_G12")
    scores = {name: score_hypothesis(observed, hypotheses[name]) for name in names}
    if scores["H_G11"]["calibration_peak_to_peak_hz"] > ONE_MODEL_ADMISSION_ENVELOPE_HZ:
        return "NOT_DETECTABLE", scores, {}
    heldout = {name: score["heldout_peak_to_peak_hz"] for name, score in scores.items()}
    margins = {
        name: float(
            min(value for other, value in heldout.items() if other != name)
            - heldout[name]
        )
        for name in heldout
    }
    preferred = [
        name for name, margin in margins.items() if margin > PAIRWISE_DECISION_GUARD_HZ
    ]
    if preferred == ["H_G11"]:
        outcome = "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
    elif preferred == ["H_AFFINE"]:
        outcome = "PREFIX_AFFINE_NULL_PREFERRED"
    elif preferred == ["H_G12"]:
        outcome = "WRONG_ORBIT_G12_PREFERRED"
    else:
        outcome = "AMBIGUOUS"
    return outcome, scores, margins


def verify_seal(path: Path, source_path: Path) -> tuple[dict[str, object], str]:
    raw = Path(path).read_bytes()
    manifest_sha = sha256(raw).hexdigest()
    try:
        manifest = json.loads(
            raw.decode("utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("FROZEN_DECODER_MANIFEST_INVALID") from exc
    if manifest.get("runtime_manifest_sha256") != decoder_manifest_sha256():
        raise RuntimeError("RUNTIME_MANIFEST_CHANGED")
    if manifest.get("detector_source_sha256") != file_sha256(source_path):
        raise RuntimeError("DETECTOR_SOURCE_CHANGED")
    if manifest.get("plan_sha256") != PLAN_SHA256:
        raise RuntimeError("PLAN_BINDING_CHANGED")
    return manifest, manifest_sha


def run_once(
    gold_path: Path,
    nlib_path: Path,
    navigation: Path,
    seal_path: Path,
    output_path: Path,
    authority_token: str,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise RuntimeError("MEASUREMENT_AUTHORITY_REQUIRED")
    seal, seal_sha = verify_seal(seal_path, Path(__file__))
    windows: list[StationWindow] = []
    observed: np.ndarray | None = None
    hypotheses: dict[str, np.ndarray] = {}
    outcome: str
    try:
        try:
            gold = decode_exact_station(gold_path, headers.GOLD_AUTHORITY)
            windows.append(gold)
            nlib = decode_exact_station(nlib_path, headers.NLIB_AUTHORITY)
            windows.append(nlib)
            health = [validate_station(window) for window in windows]
            observed = observed_coordinate(gold, nlib)
            hypotheses = prediction_curves(navigation)
            outcome, scores, margins = evaluate_observed(observed, hypotheses)
            receipt = {
                "schema": "gnss-double-difference-measurement-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "decoder_seal": {
                    "file": Path(seal_path).name,
                    "sha256": seal_sha,
                    "source_commit": seal["source_commit"],
                    "detector_source_sha256": seal["detector_source_sha256"],
                    "runtime_manifest_sha256": seal["runtime_manifest_sha256"],
                },
                "artifacts": [
                    {
                        "station_id": item.station_id,
                        "name": item.name,
                        "bytes": item.bytes,
                        "sha256": item.sha256,
                    }
                    for item in headers.AUTHORITIES
                ],
                "navigation": {
                    "name": screen.NAVIGATION_NAME,
                    "bytes": screen.NAVIGATION_BYTES,
                    "sha256": screen.NAVIGATION_SHA256,
                },
                "measurement_health": health,
                "observation_access": {
                    "epoch_records_decoded": RAW_RECORDS * 2,
                    "observation_fields_decoded": RAW_RECORDS
                    * 2
                    * 2
                    * len(OBSERVABLES),
                    "carrier_phase_values": RAW_RECORDS * 2 * 2 * 2,
                    "code_values": RAW_RECORDS * 2 * 2 * 2,
                    "snr_values": RAW_RECORDS * 2 * 2 * 2,
                    "lli_values": RAW_RECORDS * 2 * 2 * 2,
                },
                "feature_records": FEATURE_RECORDS,
                "calibration_records": CALIBRATION_RECORDS,
                "heldout_records": HELDOUT_RECORDS,
                "scores": scores,
                "preference_margins_hz": margins,
                "pairwise_decision_guard_hz": PAIRWISE_DECISION_GUARD_HZ,
                "clauses": {
                    "artifact_hashes": "SATISFIED",
                    "epoch_continuity": "SATISFIED",
                    "required_phase_code_snr": "SATISFIED",
                    "lli_and_geometry_free_cycle_slip": "SATISFIED",
                    "calibration_detectability": (
                        "SATISFIED" if outcome != "NOT_DETECTABLE" else "UNSATISFIED"
                    ),
                    "heldout_model_comparison": (
                        "EVALUATED" if outcome != "NOT_DETECTABLE" else "NOT_EVALUATED"
                    ),
                },
                "outcome": outcome,
                "claims": claim_scope(outcome),
                "raw_observation_persisted": False,
                "decompressed_rinex_persisted": False,
                "alternate_run_authorized": False,
            }
        except MeasurementInvalid as exc:
            outcome = "MEASUREMENT_INVALID"
            receipt = {
                "schema": "gnss-double-difference-measurement-outcome-v1",
                "plan_sha256": PLAN_SHA256,
                "decoder_seal_sha256": seal_sha,
                "clauses": {"measurement_admission": "UNSATISFIED", "reason": str(exc)},
                "downstream_clauses": {
                    "calibration_detectability": "NOT_EVALUATED",
                    "heldout_model_comparison": "NOT_EVALUATED",
                },
                "outcome": outcome,
                "claims": claim_scope(outcome),
                "raw_observation_persisted": False,
                "decompressed_rinex_persisted": False,
                "alternate_run_authorized": False,
            }
        if outcome not in ALLOWED_OUTCOMES:
            raise RuntimeError("NON_FROZEN_TERMINAL_OUTCOME")
        Path(output_path).write_text(
            strict_json(receipt) + "\n", encoding="ascii", newline="\n"
        )
        return receipt
    finally:
        for window in windows:
            window.erase()
        if observed is not None:
            observed.fill(0.0)
        for hypothesis in hypotheses.values():
            hypothesis.fill(0.0)


def claim_scope(outcome: str) -> dict[str, object]:
    evaluated = {
        "ORBITAL_MODEL_PREDICTIVELY_PREFERRED",
        "PREFIX_AFFINE_NULL_PREFERRED",
        "WRONG_ORBIT_G12_PREFERRED",
        "AMBIGUOUS",
    }
    return {
        "authorized": (
            "MODEL_CONDITIONED_FORWARD_COMPARISON_FOR_FROZEN_COORDINATE"
            if outcome in evaluated
            else "MEASUREMENT_PATH_OUTCOME_ONLY"
        ),
        "not_authorized": [
            "SATELLITE_IDENTITY",
            "ORBIT_RECONSTRUCTION",
            "REPEATED_PASS_GENERALIZATION",
            "CLAIM_OUTSIDE_GOLD_NLIB_G11_G21_COORDINATE",
        ],
    }


def format_gps_label(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S GPS")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--nlib", type=Path, required=True)
    parser.add_argument("--navigation", type=Path, required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--authority", required=True)
    args = parser.parse_args()
    receipt = run_once(
        args.gold, args.nlib, args.navigation, args.seal, args.output, args.authority
    )
    print(strict_json(receipt))


if __name__ == "__main__":
    main()
