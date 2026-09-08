"""Frozen offline executor core for the unselected DRAO DOY238 vertical.

This module is specific to the already frozen six-PRN experiment.  It has no
artifact locator, transport or fallback.  Its command-line entry point stops
while the separate artifact-selection receipt does not exist.  Synthetic
fixtures can exercise the complete identity, transform, witness and score
path without granting observation access.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from math import isfinite
from pathlib import Path
from typing import Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_doy238_integrated_plan as frozen,
)
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import (
    gnss_phase_short_window_qualification as rinex,
)
from experiments.orbital_discriminability import gnss_structural_qualification as structural


EXECUTOR_VERSION: Final = "drao-labelled-forward-doy238-executor-v1"
PLAN_RAW_SHA256: Final = "81e894a403066bc35187cfe9dd463ac5602eae5b80c7d278b270065449802d26"
BUNDLE_RAW_SHA256: Final = "52fa87052c01f407cfe7d4ba09131bdaaf38846106afcf7ae3dbcc27a8e9dbc5"
SELECTION_RECEIPT_NAME: Final = (
    "GNSS_DRAO_LABELLED_FORWARD_DOY238_ARTIFACT_SELECTION.json"
)

L1_HZ: Final = 1_575_420_000.0
L2_HZ: Final = 1_227_600_000.0
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / L2_HZ
IF_L1: Final = 2.54572778016316
IF_L2: Final = -1.5457277801631601
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
REQUIRED_FIELDS: Final = ("L1C", "L2W", "C1C", "C2W")
GEOMETRY_FREE_LIMIT_M: Final = 0.09514683639918244
SAME_PATH_LIMIT_M: Final = 1_250.0
FAMILY_ORBITAL: Final = "ORBITAL"
FAMILY_AFFINE: Final = "PREFIX_AFFINE_ONLY"
FAMILY_REVERSED: Final = "TIME_REVERSED_GEOMETRY"


class ForwardDescriptionError(RuntimeError):
    """A frozen input, description or transform ledger is invalid."""


class ForwardMeasurementInvalid(ValueError):
    """The measurement cannot enter the frozen physical comparison."""


@dataclass(slots=True)
class ForwardScan:
    header: dict[str, object]
    coverage: list[dict[str, object]]
    phase_cycles: np.ndarray
    code_m: np.ndarray
    phase_good: np.ndarray
    code_good: np.ndarray
    epoch_good: np.ndarray

    def erase(self) -> None:
        self.phase_cycles.fill(0.0)
        self.code_m.fill(0.0)
        self.phase_good.fill(False)
        self.code_good.fill(False)
        self.epoch_good.fill(False)


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise ForwardDescriptionError(f"NOT_A_JSON_OBJECT:{Path(path).name}")
    return value


def file_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes()).hexdigest()


def source_sha256() -> str:
    return sha256(Path(__file__).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def dependency_versions() -> dict[str, str]:
    return {"numpy": importlib.metadata.version("numpy")}


def verify_frozen_inputs(root: Path) -> dict[str, str]:
    root = Path(root)
    expected = {
        frozen.PLAN_NAME: PLAN_RAW_SHA256,
        frozen.BUNDLE_NAME: BUNDLE_RAW_SHA256,
    }
    actual = {name: file_sha256(root / name) for name in expected}
    if actual != expected:
        raise ForwardDescriptionError("DRAO_DOY238_FROZEN_INPUT_CHANGED")
    plan = _read_json(root / frozen.PLAN_NAME)
    candidate = plan.get("candidate", {})
    if (
        plan.get("state")
        != "DRAO_DOY238_INTEGRATED_PLAN_FROZEN_ARTIFACT_UNSELECTED"
        or candidate.get("artifact_selected") is not False
        or candidate.get("artifact_name") is not None
        or candidate.get("locator") is not None
        or candidate.get("artifact_sha256") is not None
        or candidate.get("observation_access_authorized") is not False
    ):
        raise ForwardDescriptionError("DRAO_DOY238_PLAN_SELECTION_STATE_CHANGED")
    return actual


def expected_epochs() -> tuple[datetime, ...]:
    start = datetime(2026, 8, 26, 4, 50, 0, tzinfo=timezone.utc)
    epochs = tuple(
        start + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(epochs[-1]) != "2026-08-26T05:59:00.000000Z":
        raise ForwardDescriptionError("DRAO_DOY238_GRID_CHANGED")
    return epochs


def executor_manifest(root: Path) -> dict[str, object]:
    inputs = verify_frozen_inputs(root)
    value = {
        "schema": "gnss-drao-labelled-forward-doy238-executor-manifest-v1",
        "version": EXECUTOR_VERSION,
        "state": "DRAO_DOY238_EXECUTOR_FROZEN_ARTIFACT_UNSELECTED",
        "frozen_inputs": inputs,
        "selection_receipt": {
            "name": SELECTION_RECEIPT_NAME,
            "present_at_freeze": False,
            "required_before_observation_network_or_file_access": True,
        },
        "window": {
            "start_gps": structural.format_gps_epoch(expected_epochs()[0]),
            "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
            "prefix_indices": [0, frozen.PREFIX_EPOCHS - 1],
            "heldout_indices": [frozen.PREFIX_EPOCHS, frozen.RAW_EPOCHS - 1],
        },
        "identity": {
            "archive_site_id": frozen.STATION,
            "domes": frozen.DOMES,
            "receiver": "SEPT_POLARX5_5.2.0",
            "antenna_radome": "TWIVC6050_SCIS",
            "marker_name": "DESCRIPTIVE_NOT_LITERAL_BINDING",
        },
        "required": {
            "prns": list(frozen.CODEBOOK),
            "fields": list(REQUIRED_FIELDS),
            "normal_epochs": frozen.RAW_EPOCHS,
            "pairs": frozen.RAW_EPOCHS * len(frozen.CODEBOOK),
            "lli": "ZERO_OR_BLANK_ON_L1C_AND_L2W",
            "extra_tracks": "DESCRIPTIVE_NOT_FATAL_NOT_SCORED",
        },
        "transform_ledger": {
            "SYS_SCALE_FACTOR": (
                "EXPLICIT_OR_SPEC_DEFINED_ABSENCE_UNITY;"
                "PHYSICAL_VALUE_EQUALS_STORED_VALUE_DIVIDED_BY_FACTOR"
            ),
            "SYS_PHASE_SHIFT": (
                "EXPLICIT_OR_SPEC_DEFINED_ABSENCE;STORED_PHASE_ALREADY_INCLUDES_"
                "DECLARED_CORRECTION;NEVER_APPLY_AGAIN"
            ),
            "RCV_CLOCK_OFFS_APPL": (
                "EXPLICIT_OR_SPEC_DEFAULT_ZERO;EVENT_AND_MEASUREMENT_CORRECTION_"
                "EXACTLY_ONCE"
            ),
            "malformed_conflict_incomplete_are_typed": True,
        },
        "model_blind_witnesses": {
            "geometry_free_second_difference_limit_m": GEOMETRY_FREE_LIMIT_M,
            "phase_minus_code_heldout_peak_to_peak_limit_m_per_track": (
                SAME_PATH_LIMIT_M
            ),
            "prediction_bundle_available": False,
        },
        "score": {
            "coordinate": "IONOSPHERE_FREE_L1C_L2W_PHASE_RANGE_M",
            "spatial_operator": "SIX_TRACK_EPOCHWISE_ENSEMBLE_CENTER",
            "nuisance": "PER_TRACK_PREFIX_ONLY_CONSTANT_PLUS_RATE",
            "families": [FAMILY_ORBITAL, FAMILY_AFFINE, FAMILY_REVERSED],
            "controlling_metric": "MAX_TRACK_HELDOUT_PEAK_TO_PEAK_M",
            "noncontrolling_metric": "MAX_TRACK_HELDOUT_RMS_M",
            "guard_b_m": frozen.ONE_MODEL_BOUND_M,
            "heldout_refit": False,
            "free_time_phase": False,
        },
        "access_at_freeze": {
            "observation_locator_requests": 0,
            "observation_file_opens": 0,
            "observation_payload_bytes": 0,
            "observation_values": 0,
            "orbital_scores": 0,
        },
        "persistence": {
            "observation_values": 0,
            "derived_series": 0,
            "compressed_observation": 0,
            "decoded_observation": 0,
        },
        "new_gate": False,
        "generic_framework": False,
    }
    strict_json(value)
    return value


def refuse_unselected_artifact(root: Path) -> None:
    executor_manifest(root)
    if (Path(root) / SELECTION_RECEIPT_NAME).exists():
        raise ForwardDescriptionError("UNREVIEWED_SELECTION_RECEIPT_PRESENT")
    raise PermissionError("DRAO_DOY238_ARTIFACT_UNSELECTED")


def _normalize(value: object) -> str:
    return " ".join(str(value).replace("_", " ").split())


def _scale_ledger(
    records: Sequence[str], gps_observables: Sequence[str]
) -> tuple[dict[str, int], dict[str, object]]:
    factors = {observable: 1 for observable in gps_observables}
    if not records:
        return factors, {
            "state": "SPEC_DEFINED_ABSENCE_UNITY",
            "factors": factors.copy(),
            "numerical_rule": "DIVIDE_STORED_VALUE_BY_FACTOR",
        }
    assigned: dict[str, int] = {}
    index = 0
    try:
        while index < len(records):
            raw = records[index].ljust(60)
            system = raw[0:1].strip()
            if not system:
                raise ForwardDescriptionError("SCALE_FACTOR_MALFORMED_CONTINUATION")
            factor = int(raw[2:6])
            count = int(raw[8:10].strip() or "0")
            if factor not in {1, 10, 100, 1000}:
                raise ForwardDescriptionError("SCALE_FACTOR_UNSUPPORTED")
            observables = raw[11:60].split()
            while count and len(observables) < count:
                index += 1
                if index >= len(records):
                    raise ForwardDescriptionError("SCALE_FACTOR_INCOMPLETE")
                continuation = records[index].ljust(60)
                if continuation[0:10].strip():
                    raise ForwardDescriptionError("SCALE_FACTOR_MALFORMED_CONTINUATION")
                observables.extend(continuation[11:60].split())
            if count and len(observables) != count:
                raise ForwardDescriptionError("SCALE_FACTOR_INCOMPLETE")
            targets = tuple(observables) if count else tuple(gps_observables)
            if system == "G":
                for observable in targets:
                    if observable not in factors:
                        raise ForwardDescriptionError(
                            f"SCALE_FACTOR_UNKNOWN_OBSERVABLE:{observable}"
                        )
                    if observable in assigned and assigned[observable] != factor:
                        raise ForwardDescriptionError(
                            f"SCALE_FACTOR_CONFLICT:{observable}"
                        )
                    assigned[observable] = factor
                    factors[observable] = factor
            index += 1
    except ValueError as exc:
        raise ForwardDescriptionError("SCALE_FACTOR_MALFORMED") from exc
    return factors, {
        "state": "EXPLICIT_RECORD",
        "factors": factors.copy(),
        "explicit_gps_observables": sorted(assigned),
        "numerical_rule": "DIVIDE_STORED_VALUE_BY_FACTOR",
    }


def _phase_shift_ledger(
    records: Sequence[str], satellites: Sequence[str]
) -> tuple[dict[str, dict[str, float]], dict[str, object]]:
    empty = {
        observable: {satellite: 0.0 for satellite in satellites}
        for observable in CORE_PHASE
    }
    if not records:
        return empty, {
            "state": "SPEC_DEFINED_ABSENCE",
            "coverage": {observable: list(satellites) for observable in CORE_PHASE},
            "numerical_rule": "DO_NOT_APPLY_TO_STORED_PHASE",
        }
    values: dict[str, dict[str, float]] = {observable: {} for observable in CORE_PHASE}
    index = 0
    try:
        while index < len(records):
            raw = records[index].ljust(60)
            system = raw[0:1].strip()
            observable = raw[2:5].strip()
            if not system or not observable:
                raise ForwardDescriptionError("PHASE_SHIFT_MALFORMED_IDENTITY")
            correction = float(raw[6:14].strip().replace("D", "E"))
            count = int(raw[16:18].strip() or "0")
            if not isfinite(correction):
                raise ForwardDescriptionError("PHASE_SHIFT_NONFINITE")
            covered = raw[19:60].split()
            while count and len(covered) < count:
                index += 1
                if index >= len(records):
                    raise ForwardDescriptionError("PHASE_SHIFT_INCOMPLETE")
                continuation = records[index].ljust(60)
                if continuation[0:18].strip():
                    raise ForwardDescriptionError("PHASE_SHIFT_MALFORMED_CONTINUATION")
                covered.extend(continuation[19:60].split())
            if count and len(covered) != count:
                raise ForwardDescriptionError("PHASE_SHIFT_INCOMPLETE")
            if system == "G" and observable in values:
                targets = tuple(covered) if count else tuple(satellites)
                for satellite in targets:
                    if satellite not in satellites:
                        continue
                    previous = values[observable].get(satellite)
                    if previous is not None and previous != correction:
                        raise ForwardDescriptionError(
                            f"PHASE_SHIFT_CONFLICT:{observable}:{satellite}"
                        )
                    values[observable][satellite] = correction
            index += 1
    except ValueError as exc:
        raise ForwardDescriptionError("PHASE_SHIFT_MALFORMED") from exc
    for observable, coverage in values.items():
        missing = sorted(set(satellites) - set(coverage))
        if missing:
            raise ForwardDescriptionError(
                f"PHASE_SHIFT_INCOMPLETE:{observable}:{','.join(missing)}"
            )
    return values, {
        "state": "EXPLICIT_RECORD",
        "coverage": {observable: list(satellites) for observable in CORE_PHASE},
        "declared_cycles": values,
        "numerical_rule": "DO_NOT_APPLY_TO_STORED_PHASE",
    }


def _validate_header(
    parsed: Mapping[str, object], *, archive_site_id: str
) -> dict[str, object]:
    if archive_site_id != frozen.STATION:
        raise ForwardDescriptionError("ARCHIVE_SITE_ID_MISMATCH")
    if not 3.0 <= float(parsed["rinex_version"]) < 4.0:
        raise ForwardDescriptionError("RINEX_VERSION_NOT_3")
    if _normalize(parsed.get("marker_number", "")) != frozen.DOMES:
        raise ForwardDescriptionError("MARKER_DOMES_MISMATCH")
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != "SEPT POLARX5":
        raise ForwardDescriptionError("RECEIVER_TYPE_MISMATCH")
    if _normalize(receiver["version_or_radome"]) != "5.2.0":
        raise ForwardDescriptionError("RECEIVER_VERSION_MISMATCH")
    antenna_type = str(antenna["type"]).ljust(20)
    if _normalize(antenna_type[:16]) != "TWIVC6050":
        raise ForwardDescriptionError("ANTENNA_TYPE_MISMATCH")
    if _normalize(antenna_type[16:20]) != "SCIS":
        raise ForwardDescriptionError("ANTENNA_RADOME_MISMATCH")
    if float(parsed["interval_s"]) != float(frozen.STEP_S):
        raise ForwardDescriptionError("INTERVAL_CHANGED")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise ForwardDescriptionError("OBSERVATION_TIME_SYSTEM_NOT_GPS")
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise ForwardDescriptionError("FROZEN_WINDOW_NOT_COVERED")
    clock = int(parsed["receiver_clock_offset_applied"])
    if clock not in {0, 1}:
        raise ForwardDescriptionError("RECEIVER_CLOCK_SEMANTICS_UNKNOWN")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(REQUIRED_FIELDS) - set(gps_types))
    if missing:
        raise ForwardMeasurementInvalid(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{','.join(missing)}"
        )
    factors, scale_ledger = _scale_ledger(
        parsed.get("scale_factor_records", ()), gps_types
    )
    shifts, phase_ledger = _phase_shift_ledger(
        parsed.get("phase_shift_records", ()), frozen.CODEBOOK
    )
    clock_provenance = str(parsed.get("receiver_clock_offset_provenance", ""))
    clock_state = (
        "EXPLICIT_RECORD"
        if clock_provenance == "EXPLICIT_HEADER_RECORD"
        else "SPEC_DEFINED_DEFAULT_ZERO"
    )
    return {
        "archive_site_id": archive_site_id,
        "marker_name": parsed.get("marker_name"),
        "marker_name_role": "DESCRIPTIVE_NOT_LITERAL_BINDING",
        "marker_number": parsed["marker_number"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna_type[:16]),
        "antenna_radome": _normalize(antenna_type[16:20]),
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "full_frozen_window_covered": True,
        "gps_observables": list(gps_types),
        "transforms": {
            "scale_factor": scale_ledger,
            "phase_shift": phase_ledger,
            "receiver_clock": {
                "state": clock_state,
                "applied_flag": clock,
                "event_time_rule": "TIME_EQUALS_TIME_R_MINUS_DT_IF_FLAG_ZERO",
                "measurement_rule": (
                    "PHASE_EQUALS_PHASE_R_MINUS_DT_TIMES_FREQUENCY_AND_"
                    "CODE_EQUALS_CODE_R_MINUS_DT_TIMES_C_IF_FLAG_ZERO"
                ),
                "correction_count": "EXACTLY_ONCE",
            },
        },
        "_scale_factors": factors,
        "_phase_shifts": shifts,
    }


def _parse_epoch_clock(line: bytes) -> tuple[datetime, int, int, float | None]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        whole = int(second)
        epoch = datetime(
            int(parts[1]),
            int(parts[2]),
            int(parts[3]),
            int(parts[4]),
            int(parts[5]),
            whole,
            int(round((second - whole) * 1_000_000)),
            tzinfo=timezone.utc,
        )
        clock = float(parts[9].replace("D", "E")) if len(parts) > 9 else None
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise ForwardMeasurementInvalid("RECORD_INVALID:EPOCH") from exc
    if clock is not None and not isfinite(clock):
        raise ForwardMeasurementInvalid("RECORD_INVALID:NONFINITE_RECEIVER_CLOCK")
    return epoch, int(parts[7]), int(parts[8]), clock


def _grid_index(epoch: datetime) -> tuple[int, float]:
    epochs = expected_epochs()
    elapsed = (epoch - epochs[0]).total_seconds() / frozen.STEP_S
    index = int(round(elapsed))
    if index < 0 or index >= len(epochs):
        raise ForwardMeasurementInvalid("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    deviation = (epoch - epochs[index]).total_seconds()
    if abs(deviation) > 15.0:
        raise ForwardMeasurementInvalid("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    if abs(abs(deviation) - 15.0) < 1.0e-9:
        raise ForwardMeasurementInvalid("EVENT_TIME_GRID_ASSIGNMENT_AMBIGUOUS")
    return index, float(deviation)


def _read_window_records(
    reader: rinex._LineReader,
    system_types: Mapping[str, Sequence[str]],
    receiver_clock_offset_applied: int,
) -> tuple[
    dict[tuple[int, str], rinex._Record],
    dict[int, int],
    dict[int, float],
    dict[int, float],
]:
    epochs = expected_epochs()
    start = epochs[0] - timedelta(seconds=15)
    stop = epochs[-1] + timedelta(seconds=15)
    records: dict[tuple[int, str], rinex._Record] = {}
    flags: dict[int, int] = {}
    deviations: dict[int, float] = {}
    clocks: dict[int, float] = {}
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise ForwardMeasurementInvalid("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        raw_epoch, flag, satellite_count, clock = _parse_epoch_clock(line)
        correction = (
            float(clock)
            if receiver_clock_offset_applied == 0 and clock is not None
            else 0.0
        )
        epoch = raw_epoch - timedelta(seconds=correction)
        grid: int | None = None
        if start <= epoch <= stop:
            grid, deviation = _grid_index(epoch)
            if grid in flags:
                raise ForwardMeasurementInvalid("RECORD_INVALID:DUPLICATE_GRID_EPOCH")
            flags[grid] = flag
            deviations[grid] = deviation
            clocks[grid] = correction
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise ForwardMeasurementInvalid(
                        "RECORD_INVALID:TRUNCATED_SPECIAL_EVENT"
                    )
            continue
        if flag == 6:
            for _ in range(satellite_count):
                rinex._read_record(reader, system_types)
            continue
        if flag not in {0, 1}:
            raise ForwardMeasurementInvalid(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            try:
                satellite, record = rinex._read_record(reader, system_types)
            except rinex.QualificationFailure as exc:
                raise ForwardMeasurementInvalid(str(exc)) from exc
            if grid is None or not satellite.startswith("G"):
                continue
            key = grid, satellite
            if key in records:
                raise ForwardMeasurementInvalid(
                    "RECORD_INVALID:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = record
    return records, flags, deviations, clocks


def _finite_scalar(field: bytes | None) -> float | None:
    if field is None:
        return None
    token = field[:14].strip().replace(b"D", b"E")
    if not token:
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    return float(value) if isfinite(value) else None


def scan_decoded_fixture(decoded: bytearray, *, archive_site_id: str) -> ForwardScan:
    """Parse one already-decoded synthetic RINEX fixture in volatile memory."""

    reader = rinex._LineReader(decoded)
    try:
        parsed = headers.parse_header_lines(rinex._read_header(reader))
    except (headers.HeaderAdmissionError, rinex.QualificationFailure) as exc:
        raise ForwardDescriptionError(f"HEADER_INVALID:{exc}") from exc
    header = _validate_header(parsed, archive_site_id=archive_site_id)
    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {observable: gps_types.index(observable) for observable in REQUIRED_FIELDS}
    records, flags, deviations, clocks = _read_window_records(
        reader, system_types, int(parsed["receiver_clock_offset_applied"])
    )
    shape = (frozen.RAW_EPOCHS, len(frozen.CODEBOOK), 2)
    phase = np.full(shape, np.nan)
    code = np.full(shape, np.nan)
    phase_good = np.zeros(shape, dtype=np.bool_)
    code_good = np.zeros(shape, dtype=np.bool_)
    epoch_good = np.zeros(frozen.RAW_EPOCHS, dtype=np.bool_)
    coverage: list[dict[str, object]] = []
    scales = header.pop("_scale_factors")
    header.pop("_phase_shifts")
    for epoch_index, epoch in enumerate(expected_epochs()):
        flag = flags.get(epoch_index)
        epoch_good[epoch_index] = flag == 0
        for satellite_index, satellite in enumerate(frozen.CODEBOOK):
            record = records.get((epoch_index, satellite))
            for observable in REQUIRED_FIELDS:
                declared_index = indices[observable]
                field = (
                    record.fields[declared_index]
                    if record is not None and declared_index < record.field_count
                    else None
                )
                if record is None:
                    state, count, continuation = "FIELD_ABSENT", 0, "NOT_APPLICABLE"
                elif declared_index >= record.field_count:
                    state = "TRAILING_FIELD_OMITTED"
                    count, continuation = record.field_count, record.continuation_state
                elif not field[:14].strip():
                    state = "FIELD_BLANK"
                    count, continuation = record.field_count, record.continuation_state
                else:
                    state = "PRESENT"
                    count, continuation = record.field_count, record.continuation_state
                scalar = _finite_scalar(field)
                lli = (
                    rinex._parse_lli(field)
                    if field is not None and observable in CORE_PHASE
                    else "NOT_APPLICABLE"
                )
                if state == "PRESENT" and scalar is None:
                    state = "RECORD_INVALID"
                axis = (CORE_PHASE if observable.startswith("L") else SAME_PATH_CODE).index(
                    observable
                )
                if state == "PRESENT" and flag == 0:
                    dt = clocks.get(epoch_index, 0.0)
                    value = scalar / scales[observable]
                    if observable.startswith("L") and lli == "ZERO_OR_BLANK":
                        frequency = L1_HZ if observable == "L1C" else L2_HZ
                        phase[epoch_index, satellite_index, axis] = (
                            value - dt * frequency
                        )
                        phase_good[epoch_index, satellite_index, axis] = True
                    elif observable.startswith("C"):
                        code[epoch_index, satellite_index, axis] = (
                            value - dt * SPEED_OF_LIGHT_M_S
                        )
                        code_good[epoch_index, satellite_index, axis] = True
                coverage.append(
                    {
                        "gps_epoch": structural.format_gps_epoch(epoch),
                        "satellite": satellite,
                        "observable": observable,
                        "state": state,
                        "header_declared_index": declared_index,
                        "reconstructed_field_count": count,
                        "continuation_state": continuation,
                        "lli_state": lli,
                        "epoch_flag": flag,
                    }
                )
    if not np.all(epoch_good):
        count = int(np.count_nonzero(epoch_good))
        phase.fill(0.0)
        code.fill(0.0)
        raise ForwardMeasurementInvalid(f"COMPLETE_NORMAL_EPOCH_COUNT_NOT_139:{count}")
    if not np.all(phase_good) or not np.all(code_good):
        phase.fill(0.0)
        code.fill(0.0)
        raise ForwardMeasurementInvalid("REQUIRED_LABELLED_TOPOLOGY_INCOMPLETE")
    header["event_time"] = {
        "state": (
            "STRUCTURALLY_MAPPED"
            if len(deviations) == frozen.RAW_EPOCHS
            else "INCOMPLETE"
        ),
        "mapped_epochs": len(deviations),
        "maximum_absolute_grid_deviation_s": max(
            (abs(value) for value in deviations.values()), default=None
        ),
        "frozen_error_bound_s": [-15.0, 15.0],
        "receiver_clock_correction_epochs": sum(
            value != 0.0 for value in clocks.values()
        ),
    }
    header["extra_gps_tracks"] = sorted(
        {satellite for _, satellite in records if satellite not in frozen.CODEBOOK}
    )
    return ForwardScan(
        header,
        coverage,
        phase,
        code,
        phase_good,
        code_good,
        epoch_good,
    )


def _prefix_affine(values: np.ndarray) -> np.ndarray:
    elapsed = np.arange(frozen.RAW_EPOCHS, dtype=np.float64) * frozen.STEP_S
    centered = elapsed - float(np.mean(elapsed[: frozen.PREFIX_EPOCHS]))
    design = np.column_stack(
        [np.ones(frozen.PREFIX_EPOCHS), centered[: frozen.PREFIX_EPOCHS]]
    )
    coefficients, *_ = np.linalg.lstsq(
        design, values[: frozen.PREFIX_EPOCHS], rcond=None
    )
    residual = values - (coefficients[0] + coefficients[1] * centered)
    elapsed.fill(0.0)
    centered.fill(0.0)
    design.fill(0.0)
    coefficients.fill(0.0)
    return residual


def admit_model_blind(scan: ForwardScan) -> tuple[dict[str, object], np.ndarray]:
    if not np.all(scan.epoch_good):
        raise ForwardMeasurementInvalid("COMPLETE_NORMAL_EPOCHS_REQUIRED")
    if not np.all(scan.phase_good) or not np.all(scan.code_good):
        raise ForwardMeasurementInvalid("REQUIRED_LABELLED_FIELDS_NOT_COMPLETE")
    geometry_rows: list[dict[str, object]] = []
    for index, satellite in enumerate(frozen.CODEBOOK):
        coordinate = (
            LAMBDA_L1_M * scan.phase_cycles[:, index, 0]
            - LAMBDA_L2_M * scan.phase_cycles[:, index, 1]
        )
        second = np.diff(coordinate, n=2)
        maximum = float(np.max(np.abs(second)))
        geometry_rows.append(
            {
                "satellite": satellite,
                "maximum_absolute_second_difference_m": maximum,
                "state": (
                    "SATISFIED" if maximum <= GEOMETRY_FREE_LIMIT_M else "UNSATISFIED"
                ),
            }
        )
        coordinate.fill(0.0)
        second.fill(0.0)
    if any(row["state"] != "SATISFIED" for row in geometry_rows):
        raise ForwardMeasurementInvalid("GEOMETRY_FREE_CONTINUITY_UNSATISFIED")

    phase_if = (
        IF_L1 * LAMBDA_L1_M * scan.phase_cycles[:, :, 0]
        + IF_L2 * LAMBDA_L2_M * scan.phase_cycles[:, :, 1]
    )
    code_if = IF_L1 * scan.code_m[:, :, 0] + IF_L2 * scan.code_m[:, :, 1]
    witness = phase_if - code_if
    centered_witness = witness - np.mean(witness, axis=1, keepdims=True)
    witness_rows: list[dict[str, object]] = []
    try:
        for index, satellite in enumerate(frozen.CODEBOOK):
            residual = _prefix_affine(centered_witness[:, index])
            peak_to_peak = float(np.ptp(residual[frozen.PREFIX_EPOCHS :]))
            witness_rows.append(
                {
                    "satellite": satellite,
                    "heldout_peak_to_peak_m": peak_to_peak,
                    "state": (
                        "SATISFIED"
                        if peak_to_peak <= SAME_PATH_LIMIT_M
                        else "UNSATISFIED"
                    ),
                }
            )
            residual.fill(0.0)
        if any(row["state"] != "SATISFIED" for row in witness_rows):
            raise ForwardMeasurementInvalid("SAME_PATH_WITNESS_UNSATISFIED")
        centered_phase = phase_if - np.mean(phase_if, axis=1, keepdims=True)
        receipt = {
            "schema": "gnss-drao-labelled-forward-doy238-admission-v1",
            "state": "DRAO_DOY238_MEASUREMENT_ADMITTED_FOR_FROZEN_SCORE",
            "required_prns": list(frozen.CODEBOOK),
            "structural_counts": dict(
                sorted(Counter(row["state"] for row in scan.coverage).items())
            ),
            "geometry_free": geometry_rows,
            "same_path_witness": witness_rows,
            "prediction_bundle_available_during_admission": False,
            "observation_values_persisted": 0,
        }
        strict_json(receipt)
        return receipt, centered_phase
    finally:
        phase_if.fill(0.0)
        code_if.fill(0.0)
        witness.fill(0.0)
        centered_witness.fill(0.0)


def _load_model_families(root: Path) -> dict[str, np.ndarray]:
    verify_frozen_inputs(root)
    bundle = _read_json(Path(root) / frozen.BUNDLE_NAME)
    raw = bundle.get("labelled_model_curves_m")
    if not isinstance(raw, Mapping) or tuple(sorted(raw)) != tuple(sorted(frozen.CODEBOOK)):
        raise ForwardDescriptionError("PREDICTION_CODEBOOK_CHANGED")
    nominal = np.column_stack(
        [np.asarray(raw[satellite], dtype=np.float64) for satellite in frozen.CODEBOOK]
    )
    if nominal.shape != (frozen.RAW_EPOCHS, len(frozen.CODEBOOK)):
        raise ForwardDescriptionError("PREDICTION_SHAPE_CHANGED")
    if not np.all(np.isfinite(nominal)):
        raise ForwardDescriptionError("PREDICTION_NONFINITE")
    nominal -= np.mean(nominal, axis=1, keepdims=True)
    return {
        FAMILY_ORBITAL: nominal,
        FAMILY_AFFINE: np.zeros_like(nominal),
        FAMILY_REVERSED: nominal[::-1, :].copy(),
    }


def _classify_family_metrics(
    rows: Mapping[str, Mapping[str, object]],
) -> tuple[str, str, float]:
    """Apply the frozen decision table to already computed family metrics."""

    if set(rows) != {FAMILY_ORBITAL, FAMILY_AFFINE, FAMILY_REVERSED}:
        raise ForwardDescriptionError("SCORE_FAMILY_SET_CHANGED")
    orbital_prefix = float(rows[FAMILY_ORBITAL]["controlling_prefix_peak_to_peak_m"])
    scores = {
        family: float(row["controlling_heldout_peak_to_peak_m"])
        for family, row in rows.items()
    }
    if not all(isfinite(value) and value >= 0.0 for value in (*scores.values(), orbital_prefix)):
        raise ForwardDescriptionError("SCORE_METRIC_INVALID")
    ordered = sorted(scores, key=lambda family: (scores[family], family))
    best, second = ordered[:2]
    margin = scores[second] - scores[best]
    uniquely_preferred = margin > frozen.ONE_MODEL_BOUND_M
    orbital_heldout = scores[FAMILY_ORBITAL]
    if orbital_prefix > frozen.ONE_MODEL_BOUND_M:
        outcome = "NOT_DETECTABLE"
    elif uniquely_preferred and best == FAMILY_ORBITAL:
        outcome = (
            "ORBITAL_MODEL_PREDICTIVELY_PREFERRED"
            if orbital_heldout <= frozen.ONE_MODEL_BOUND_M
            else "ORBITAL_PREDICTION_REJECTED"
        )
    elif uniquely_preferred and best == FAMILY_AFFINE:
        outcome = "PREFIX_AFFINE_NULL_PREFERRED"
    elif uniquely_preferred and best == FAMILY_REVERSED:
        outcome = "TIME_REVERSED_GEOMETRY_NULL_PREFERRED"
    elif orbital_heldout > frozen.ONE_MODEL_BOUND_M:
        outcome = "ORBITAL_PREDICTION_REJECTED"
    else:
        outcome = "AMBIGUOUS"
    return outcome, best, float(margin)


def score_admitted_coordinate(
    centered_observed_m: np.ndarray, root: Path
) -> dict[str, object]:
    if centered_observed_m.shape != (frozen.RAW_EPOCHS, len(frozen.CODEBOOK)):
        raise ForwardMeasurementInvalid("OBSERVED_COORDINATE_SHAPE_INVALID")
    if not np.all(np.isfinite(centered_observed_m)):
        raise ForwardMeasurementInvalid("OBSERVED_COORDINATE_NONFINITE")
    families = _load_model_families(root)
    rows: dict[str, dict[str, object]] = {}
    try:
        for family, model in families.items():
            per_track = []
            for index, satellite in enumerate(frozen.CODEBOOK):
                residual = _prefix_affine(centered_observed_m[:, index] - model[:, index])
                prefix = residual[: frozen.PREFIX_EPOCHS]
                heldout = residual[frozen.PREFIX_EPOCHS :]
                per_track.append(
                    {
                        "satellite": satellite,
                        "prefix_peak_to_peak_m": float(np.ptp(prefix)),
                        "heldout_peak_to_peak_m": float(np.ptp(heldout)),
                        "heldout_rms_m": float(np.sqrt(np.mean(heldout * heldout))),
                    }
                )
                residual.fill(0.0)
            rows[family] = {
                "controlling_heldout_peak_to_peak_m": max(
                    row["heldout_peak_to_peak_m"] for row in per_track
                ),
                "noncontrolling_heldout_rms_m": max(
                    row["heldout_rms_m"] for row in per_track
                ),
                "controlling_prefix_peak_to_peak_m": max(
                    row["prefix_peak_to_peak_m"] for row in per_track
                ),
                "tracks": per_track,
            }
        outcome, best, margin = _classify_family_metrics(rows)
        orbital_heldout = float(
            rows[FAMILY_ORBITAL]["controlling_heldout_peak_to_peak_m"]
        )
        result = {
            "schema": "gnss-drao-labelled-forward-doy238-score-v1",
            "outcome": outcome,
            "family_metrics": rows,
            "best_family": best,
            "preference_margin_m": float(margin),
            "preference_requires_strictly_more_than_b": True,
            "guard_b_m": frozen.ONE_MODEL_BOUND_M,
            "orbital_positive_absolute_bound_satisfied": (
                orbital_heldout <= frozen.ONE_MODEL_BOUND_M
            ),
            "heldout_refit": False,
            "free_time_phase": False,
        }
        strict_json(result)
        return result
    finally:
        for model in families.values():
            model.fill(0.0)


def execute_synthetic_fixture(
    decoded: bytearray, *, archive_site_id: str, root: Path
) -> dict[str, object]:
    """Exercise the frozen path for tests; never persists decoded values."""

    scan: ForwardScan | None = None
    coordinate: np.ndarray | None = None
    try:
        scan = scan_decoded_fixture(decoded, archive_site_id=archive_site_id)
        admission, coordinate = admit_model_blind(scan)
        score = score_admitted_coordinate(coordinate, root)
        receipt = {
            "schema": "gnss-drao-labelled-forward-doy238-synthetic-outcome-v1",
            "outcome": score["outcome"],
            "identity_and_transform": scan.header,
            "admission": admission,
            "score": score,
            "observation_values_persisted": 0,
            "derived_series_persisted": 0,
        }
        strict_json(receipt)
        return receipt
    finally:
        if coordinate is not None:
            coordinate.fill(0.0)
        if scan is not None:
            scan.erase()
        decoded[:] = b"\x00" * len(decoded)


def main() -> None:
    refuse_unselected_artifact(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
