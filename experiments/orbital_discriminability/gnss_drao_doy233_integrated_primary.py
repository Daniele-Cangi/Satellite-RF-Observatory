"""Frozen offline core for the unselected DRAO DOY233 primary.

This is an experiment-specific compiler and executor boundary, not a GNSS
framework.  It contains no product locator and refuses real execution while
the prospective plan leaves the artifact identity unselected.  Synthetic
fixtures may exercise the exact parser, admission and opaque-score boundary.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from itertools import permutations
import json
from math import isfinite
from pathlib import Path
from typing import Callable, Final, Mapping, Sequence

import numpy as np

from experiments.orbital_discriminability import gnss_all_track_clutter_scorer as scorer
from experiments.orbital_discriminability import gnss_drao_doy232_qualification as prior
from experiments.orbital_discriminability import gnss_drao_doy233_integrated_primary_plan as frozen
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_phase_short_window_qualification as rinex
from experiments.orbital_discriminability import gnss_structural_qualification as structural


EXECUTOR_VERSION: Final = "drao-doy233-integrated-primary-v1"
PLAN_SHA256: Final = "c6352b12c2a768a449cb73f3f62732e839c4e5d0633ff7de2ddb4e57a7b326cf"
BUNDLE_SHA256: Final = "1d8888b6a5cffdab6d6412d935c3b704e4ae42fa878b79bb90831e93f8431117"
REVEAL_SHA256: Final = "d75243571639b00d51d059f452ef08d4c493e210f0ad2c78ae4ba23d4c4ef07a"

L1_HZ: Final = 1_575_420_000.0
L2_HZ: Final = 1_227_600_000.0
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / L2_HZ
IF_L1: Final = 2.54572778016316
IF_L2: Final = -1.5457277801631601
REQUIRED: Final = frozen.CORE_PHASE + frozen.SAME_PATH_CODE


class PrimaryDescriptionError(RuntimeError):
    """A frozen input, identity description or implementation is invalid."""


class PrimaryMeasurementInvalid(ValueError):
    """The selected measurement cannot satisfy the frozen admission clauses."""


@dataclass(slots=True)
class PrimaryScan:
    header: dict[str, object]
    coverage: list[dict[str, object]]
    satellites: tuple[str, ...]
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
        raise PrimaryDescriptionError(f"NOT_A_JSON_OBJECT:{Path(path).name}")
    return value


def verify_frozen_inputs(root: Path) -> dict[str, str]:
    root = Path(root)
    expected = {
        frozen.PLAN_NAME: PLAN_SHA256,
        frozen.BUNDLE_NAME: BUNDLE_SHA256,
        frozen.REVEAL_NAME: REVEAL_SHA256,
        frozen.SCORER_NAME: frozen.SCORER_SHA256,
    }
    actual = {name: frozen.canonical_sha256(root / name) for name in expected}
    if actual != expected:
        raise PrimaryDescriptionError("DRAO_DOY233_FROZEN_INPUT_CHANGED")
    plan = _read_json(root / frozen.PLAN_NAME)
    candidate = plan.get("candidate", {})
    if (
        plan.get("state")
        != "DRAO_DOY233_INTEGRATED_PRIMARY_PLAN_FROZEN_ARTIFACT_UNSELECTED"
        or candidate.get("artifact_selected") is not False
        or candidate.get("locator") is not None
        or candidate.get("complete_artifact_sha256") is not None
        or candidate.get("observation_access_authorized") is not False
    ):
        raise PrimaryDescriptionError("DRAO_DOY233_PLAN_SELECTION_STATE_CHANGED")
    return actual


def expected_epochs() -> tuple[datetime, ...]:
    start = datetime(2026, 8, 21, 1, 14, 30, tzinfo=timezone.utc)
    result = tuple(
        start + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(result[-1]) != "2026-08-21T02:23:30.000000Z":
        raise PrimaryDescriptionError("DRAO_DOY233_GRID_CHANGED")
    return result


def executor_manifest(root: Path) -> dict[str, object]:
    inputs = verify_frozen_inputs(root)
    value = {
        "schema": "gnss-drao-doy233-integrated-primary-executor-manifest-v1",
        "version": EXECUTOR_VERSION,
        "state": "EXECUTOR_FROZEN_PRIMARY_ARTIFACT_UNSELECTED",
        "frozen_inputs": inputs,
        "window": {
            "start_gps": structural.format_gps_epoch(expected_epochs()[0]),
            "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
            "prefix_epochs": frozen.PREFIX_EPOCHS,
            "heldout_epochs": frozen.HELDOUT_EPOCHS,
        },
        "admission": {
            "complete_tracks": 7,
            "selection": "ALL_COMPLETE_GPS_TRACKS_NO_PRN_FILTER",
            "fields": list(REQUIRED),
            "zero_lli": list(frozen.CORE_PHASE),
            "geometry_free_second_difference_limit_m": 0.09514683639918244,
            "same_path_exclusions_evaluated": 7,
            "same_path_heldout_peak_to_peak_limit_m": 1_250.0,
        },
        "opaque_surface": {
            "orbital": scorer.ORBITAL_HYPOTHESIS_COUNT,
            "time_reversed": scorer.GEOMETRY_NULL_COUNT,
            "affine": scorer.AFFINE_NULL_COUNT,
            "total": scorer.HYPOTHESIS_COUNT,
            "prn_available_to_scorer": False,
        },
        "ordering": [
            "ADMISSION",
            "CODE_REVEAL_HASH_IN_RAM",
            "OPAQUE_SCORE",
            "OPAQUE_SCORE_RECEIPT_HASH",
            "IDENTITY_REVEAL",
            "ONE_OUTCOME",
        ],
        "persistence": {
            "observation_values": 0,
            "derived_series": 0,
            "compressed_primary": 0,
            "decoded_primary": 0,
        },
        "retry_after_complete_hash": 0,
        "artifact": {
            "logical_product": None,
            "locator": None,
            "sha256": None,
            "selected": False,
        },
        "access_at_freeze": {
            "network_requests": 0,
            "headers": 0,
            "payload_bytes": 0,
            "observation_values": 0,
            "scores": 0,
        },
        "new_gate": False,
    }
    strict_json(value)
    return value


def refuse_unselected_primary(root: Path) -> None:
    executor_manifest(root)
    raise PermissionError("PRIMARY_ARTIFACT_UNSELECTED")


def _opaque(prefix: str, payload: str) -> str:
    return prefix + sha256(payload.encode("ascii")).hexdigest()[:16].upper()


def hypothesis_surface(
    root: Path,
) -> tuple[tuple[scorer.OpaqueHypothesis, ...], dict[str, dict[str, object]]]:
    verify_frozen_inputs(root)
    bundle = _read_json(Path(root) / frozen.BUNDLE_NAME)
    raw_curves = bundle.get("opaque_model_curves_m")
    if not isinstance(raw_curves, Mapping) or len(raw_curves) != 6:
        raise PrimaryDescriptionError("OPAQUE_MODEL_BUNDLE_INVALID")
    model_ids = tuple(sorted(str(value) for value in raw_curves))
    curves = {
        identity: np.asarray(raw_curves[identity], dtype=np.float64)
        for identity in model_ids
    }
    if any(
        curve.shape != (frozen.RAW_EPOCHS,) or not np.all(np.isfinite(curve))
        for curve in curves.values()
    ):
        raise PrimaryDescriptionError("OPAQUE_MODEL_CURVE_INVALID")

    hypotheses: list[scorer.OpaqueHypothesis] = []
    registry: dict[str, dict[str, object]] = {}
    zero = np.zeros((scorer.EVALUATED_TRACK_COUNT, frozen.RAW_EPOCHS))
    try:
        for excluded in range(scorer.OBSERVED_TRACK_COUNT):
            included = tuple(index for index in range(7) if index != excluded)
            for assignment in permutations(model_ids):
                text = ",".join(assignment)
                orbital_id = _opaque("H_", f"ORBITAL:{excluded}:{text}")
                reverse_id = _opaque("H_", f"TIME_REVERSED:{excluded}:{text}")
                matrix = np.stack([curves[identity] for identity in assignment])
                hypotheses.append(
                    scorer.OpaqueHypothesis(
                        orbital_id, scorer.FAMILY_ORBITAL, included, matrix
                    )
                )
                hypotheses.append(
                    scorer.OpaqueHypothesis(
                        reverse_id,
                        scorer.FAMILY_GEOMETRY_NULL,
                        included,
                        matrix[:, ::-1].copy(),
                    )
                )
                registry[orbital_id] = {
                    "family": scorer.FAMILY_ORBITAL,
                    "excluded_index": excluded,
                    "assignment": list(assignment),
                }
                registry[reverse_id] = {
                    "family": scorer.FAMILY_GEOMETRY_NULL,
                    "excluded_index": excluded,
                    "assignment": list(assignment),
                }
            affine_id = _opaque("H_", f"AFFINE_ONLY:{excluded}")
            hypotheses.append(
                scorer.OpaqueHypothesis(
                    affine_id, scorer.FAMILY_AFFINE_NULL, included, zero.copy()
                )
            )
            registry[affine_id] = {
                "family": scorer.FAMILY_AFFINE_NULL,
                "excluded_index": excluded,
                "assignment": None,
            }
    finally:
        for curve in curves.values():
            curve.fill(0.0)
        zero.fill(0.0)
    if len(hypotheses) != scorer.HYPOTHESIS_COUNT or len(registry) != len(hypotheses):
        raise PrimaryDescriptionError("OPAQUE_HYPOTHESIS_SURFACE_INVALID")
    return tuple(hypotheses), registry


def _normalize(value: object) -> str:
    return " ".join(str(value).replace("_", " ").split())


def _validate_header(
    parsed: Mapping[str, object], artifact_site_id: str
) -> dict[str, object]:
    if artifact_site_id != frozen.STATION:
        raise PrimaryDescriptionError("FROZEN_ARTIFACT_SITE_ID_MISMATCH")
    if not 3.0 <= float(parsed["rinex_version"]) < 4.0:
        raise PrimaryDescriptionError("RINEX_VERSION_NOT_3")
    if _normalize(parsed.get("marker_number", "")) != frozen.DOMES:
        raise PrimaryDescriptionError("MARKER_DOMES_MISMATCH")
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != _normalize("SEPT_POLARX5"):
        raise PrimaryDescriptionError("RECEIVER_TYPE_MISMATCH")
    if _normalize(receiver["version_or_radome"]) != "5.2.0":
        raise PrimaryDescriptionError("RECEIVER_VERSION_MISMATCH")
    antenna_type = str(antenna["type"]).ljust(20)
    if _normalize(antenna_type[:16]) != "TWIVC6050":
        raise PrimaryDescriptionError("ANTENNA_TYPE_MISMATCH")
    if _normalize(antenna_type[16:20]) != "SCIS":
        raise PrimaryDescriptionError("ANTENNA_RADOME_MISMATCH")
    if float(parsed["interval_s"]) != float(frozen.STEP_S):
        raise PrimaryDescriptionError("INTERVAL_CHANGED")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise PrimaryDescriptionError("OBSERVATION_TIME_SYSTEM_NOT_GPS")
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise PrimaryDescriptionError("FROZEN_WINDOW_NOT_COVERED")
    if parsed["receiver_clock_offset_applied"] not in {0, 1}:
        raise PrimaryDescriptionError("RECEIVER_CLOCK_SEMANTICS_UNKNOWN")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(REQUIRED) - set(gps_types))
    if missing:
        raise PrimaryMeasurementInvalid(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{','.join(missing)}"
        )
    scales = prior.parse_scale_factors(parsed.get("scale_factor_records", ()), gps_types)
    return {
        "artifact_site_id": artifact_site_id,
        "marker_name": parsed.get("marker_name"),
        "marker_name_is_binding": False,
        "marker_number": parsed["marker_number"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna_type[:16]),
        "antenna_radome": _normalize(antenna_type[16:20]),
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "gps_observables": list(gps_types),
        "scale_factors": scales,
        "full_frozen_window_covered": True,
    }


def _parse_epoch_clock(line: bytes) -> tuple[datetime, int, int, float | None]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        whole = int(second)
        epoch = datetime(
            int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]),
            int(parts[5]), whole, int(round((second - whole) * 1_000_000)),
            tzinfo=timezone.utc,
        )
        clock = float(parts[9].replace("D", "E")) if len(parts) > 9 else None
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise PrimaryMeasurementInvalid("RECORD_INVALID:EPOCH") from exc
    if clock is not None and not isfinite(clock):
        raise PrimaryMeasurementInvalid("RECORD_INVALID:NONFINITE_RECEIVER_CLOCK")
    return epoch, int(parts[7]), int(parts[8]), clock


def _grid_index(epoch: datetime) -> tuple[int, float]:
    epochs = expected_epochs()
    elapsed = (epoch - epochs[0]).total_seconds() / frozen.STEP_S
    index = int(round(elapsed))
    if index < 0 or index >= len(epochs):
        raise PrimaryMeasurementInvalid("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    deviation = (epoch - epochs[index]).total_seconds()
    if abs(deviation) > 15.0:
        raise PrimaryMeasurementInvalid("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    if abs(abs(deviation) - 15.0) < 1.0e-9:
        raise PrimaryMeasurementInvalid("EVENT_TIME_GRID_ASSIGNMENT_AMBIGUOUS")
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
    start, stop = epochs[0] - timedelta(seconds=15), epochs[-1] + timedelta(seconds=15)
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
                raise PrimaryMeasurementInvalid("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        raw_epoch, flag, satellite_count, clock = _parse_epoch_clock(line)
        correction = (
            float(clock)
            if receiver_clock_offset_applied == 0 and clock is not None
            else 0.0
        )
        epoch = raw_epoch - timedelta(seconds=correction)
        in_window = start <= epoch <= stop
        grid: int | None = None
        if in_window:
            grid, deviation = _grid_index(epoch)
            if grid in flags:
                raise PrimaryMeasurementInvalid("RECORD_INVALID:DUPLICATE_GRID_EPOCH")
            flags[grid], deviations[grid], clocks[grid] = flag, deviation, correction
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise PrimaryMeasurementInvalid("RECORD_INVALID:TRUNCATED_SPECIAL_EVENT")
            continue
        if flag == 6:
            for _ in range(satellite_count):
                rinex._read_record(reader, system_types)
            continue
        if flag not in {0, 1}:
            raise PrimaryMeasurementInvalid(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            try:
                satellite, record = rinex._read_record(reader, system_types)
            except rinex.QualificationFailure as exc:
                raise PrimaryMeasurementInvalid(str(exc)) from exc
            if grid is None or not satellite.startswith("G"):
                continue
            key = grid, satellite
            if key in records:
                raise PrimaryMeasurementInvalid("RECORD_INVALID:DUPLICATE_SATELLITE_RECORD")
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


def _scan_decoded_fixture(decoded: bytearray, *, artifact_site_id: str) -> PrimaryScan:
    """Parse an already decoded synthetic fixture after an attributable identity."""

    reader = rinex._LineReader(decoded)
    try:
        parsed = headers.parse_header_lines(rinex._read_header(reader))
    except (headers.HeaderAdmissionError, rinex.QualificationFailure) as exc:
        raise PrimaryDescriptionError(f"HEADER_INVALID:{exc}") from exc
    header = _validate_header(parsed, artifact_site_id)
    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {observable: gps_types.index(observable) for observable in REQUIRED}
    records, flags, deviations, clocks = _read_window_records(
        reader, system_types, int(parsed["receiver_clock_offset_applied"])
    )
    satellites = tuple(sorted({satellite for _, satellite in records}))
    shape = (frozen.RAW_EPOCHS, len(satellites), 2)
    phase = np.full(shape, np.nan)
    code = np.full(shape, np.nan)
    phase_good = np.zeros(shape, dtype=np.bool_)
    code_good = np.zeros(shape, dtype=np.bool_)
    epoch_good = np.zeros(frozen.RAW_EPOCHS, dtype=np.bool_)
    coverage: list[dict[str, object]] = []
    scales = header["scale_factors"]
    for epoch_index, epoch in enumerate(expected_epochs()):
        flag = flags.get(epoch_index)
        epoch_good[epoch_index] = flag == 0
        for satellite_index, satellite in enumerate(satellites):
            record = records.get((epoch_index, satellite))
            for observable in REQUIRED:
                header_index = indices[observable]
                field = (
                    record.fields[header_index]
                    if record is not None and header_index < record.field_count
                    else None
                )
                if record is None:
                    state, field_count, continuation = "FIELD_ABSENT", 0, "NOT_APPLICABLE"
                elif header_index >= record.field_count:
                    state = "TRAILING_FIELD_OMITTED"
                    field_count, continuation = record.field_count, record.continuation_state
                elif not field[:14].strip():
                    state = "FIELD_BLANK"
                    field_count, continuation = record.field_count, record.continuation_state
                else:
                    state = "PRESENT"
                    field_count, continuation = record.field_count, record.continuation_state
                scalar = _finite_scalar(field)
                lli = (
                    rinex._parse_lli(field)
                    if field is not None and observable in frozen.CORE_PHASE
                    else "NOT_APPLICABLE"
                )
                if state == "PRESENT" and scalar is None:
                    state = "RECORD_INVALID"
                target = (frozen.CORE_PHASE if observable.startswith("L") else frozen.SAME_PATH_CODE).index(observable)
                if state == "PRESENT" and flag == 0:
                    dt = clocks.get(epoch_index, 0.0)
                    if observable.startswith("L") and lli == "ZERO_OR_BLANK":
                        frequency = L1_HZ if observable == "L1C" else L2_HZ
                        phase[epoch_index, satellite_index, target] = scalar / scales[observable] - dt * frequency
                        phase_good[epoch_index, satellite_index, target] = True
                    elif observable.startswith("C"):
                        code[epoch_index, satellite_index, target] = scalar / scales[observable] - dt * SPEED_OF_LIGHT_M_S
                        code_good[epoch_index, satellite_index, target] = True
                coverage.append(
                    {
                        "gps_epoch": structural.format_gps_epoch(epoch),
                        "opaque_track": frozen.opaque_track_id(satellite),
                        "observable": observable,
                        "state": state,
                        "header_declared_index": header_index,
                        "reconstructed_field_count": field_count,
                        "continuation_state": continuation,
                        "lli_state": lli,
                        "epoch_flag": flag,
                    }
                )
    complete_indices = [
        index
        for index in range(len(satellites))
        if np.all(phase_good[:, index, :]) and np.all(code_good[:, index, :])
    ]
    if not np.all(epoch_good):
        complete_indices = []
    if len(complete_indices) != 7:
        phase.fill(0.0)
        code.fill(0.0)
        phase_good.fill(False)
        code_good.fill(False)
        epoch_good.fill(False)
        raise PrimaryMeasurementInvalid(
            f"COMPLETE_OPAQUE_TRACK_COUNT_NOT_SEVEN:{len(complete_indices)}"
        )
    complete_satellites = tuple(satellites[index] for index in complete_indices)
    try:
        shifts = prior.parse_phase_shift_coverage(
            parsed.get("phase_shift_records", ()), complete_satellites
        )
    except prior.DraoQualificationError as exc:
        raise PrimaryMeasurementInvalid(f"PHASE_SHIFT_INVALID:{exc}") from exc
    header["phase_shift_records"] = {
        observable: [
            {
                "opaque_track": frozen.opaque_track_id(satellite),
                "cycles": shifts[observable][satellite],
            }
            for satellite in complete_satellites
        ]
        for observable in frozen.CORE_PHASE
    }
    header["phase_shift_numerically_applied_again"] = False
    header["event_time"] = {
        "state": "STRUCTURALLY_MAPPED" if len(deviations) == frozen.RAW_EPOCHS else "INCOMPLETE",
        "mapped_epochs": len(deviations),
        "maximum_absolute_grid_deviation_s": max((abs(value) for value in deviations.values()), default=None),
        "frozen_error_bound_s": [-15.0, 15.0],
        "qualification_reduces_bound": False,
        "receiver_clock_correction_epochs": sum(value != 0.0 for value in clocks.values()),
    }
    keep = np.asarray(complete_indices, dtype=np.int64)
    result = PrimaryScan(
        header,
        coverage,
        complete_satellites,
        phase[:, keep, :].copy(),
        code[:, keep, :].copy(),
        phase_good[:, keep, :].copy(),
        code_good[:, keep, :].copy(),
        epoch_good.copy(),
    )
    phase.fill(0.0)
    code.fill(0.0)
    phase_good.fill(False)
    code_good.fill(False)
    epoch_good.fill(False)
    return result


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


def admit(scan: PrimaryScan) -> tuple[dict[str, object], dict[str, np.ndarray]]:
    if len(scan.satellites) != 7 or not np.all(scan.epoch_good):
        raise PrimaryMeasurementInvalid("SEVEN_TRACK_CONTINUITY_NOT_SATISFIED")
    if not np.all(scan.phase_good) or not np.all(scan.code_good):
        raise PrimaryMeasurementInvalid("REQUIRED_TRACK_FIELDS_NOT_COMPLETE")
    track_ids = tuple(sorted(frozen.opaque_track_id(value) for value in scan.satellites))
    satellite_by_track = {
        frozen.opaque_track_id(satellite): satellite for satellite in scan.satellites
    }
    order = [scan.satellites.index(satellite_by_track[track]) for track in track_ids]
    phase = scan.phase_cycles[:, order, :]
    code = scan.code_m[:, order, :]

    geometry_rows = []
    for index, track in enumerate(track_ids):
        geometry_free = LAMBDA_L1_M * phase[:, index, 0] - LAMBDA_L2_M * phase[:, index, 1]
        second = np.diff(geometry_free, n=2)
        maximum = float(np.max(np.abs(second)))
        geometry_rows.append(
            {
                "opaque_track": track,
                "maximum_absolute_second_difference_m": maximum,
                "state": "SATISFIED" if maximum <= 0.09514683639918244 else "UNSATISFIED",
            }
        )
        geometry_free.fill(0.0)
        second.fill(0.0)
    if any(row["state"] != "SATISFIED" for row in geometry_rows):
        raise PrimaryMeasurementInvalid("GEOMETRY_FREE_CONTINUITY_UNSATISFIED")

    phase_if = IF_L1 * LAMBDA_L1_M * phase[:, :, 0] + IF_L2 * LAMBDA_L2_M * phase[:, :, 1]
    code_if = IF_L1 * code[:, :, 0] + IF_L2 * code[:, :, 1]
    witness = phase_if - code_if
    witness_rows = []
    try:
        for excluded in range(7):
            included = tuple(index for index in range(7) if index != excluded)
            selected = witness[:, included]
            centered = selected - np.mean(selected, axis=1, keepdims=True)
            for local, track_index in enumerate(included):
                residual = _prefix_affine(centered[:, local])
                heldout = residual[frozen.PREFIX_EPOCHS :]
                peak_to_peak = float(np.ptp(heldout))
                witness_rows.append(
                    {
                        "excluded_opaque_track": track_ids[excluded],
                        "included_opaque_track": track_ids[track_index],
                        "heldout_peak_to_peak_m": peak_to_peak,
                        "state": "SATISFIED" if peak_to_peak <= 1_250.0 else "UNSATISFIED",
                    }
                )
                residual.fill(0.0)
            centered.fill(0.0)
        if any(row["state"] != "SATISFIED" for row in witness_rows):
            raise PrimaryMeasurementInvalid("SAME_PATH_WITNESS_UNSATISFIED")
        tracks = {
            track: phase_if[:, index].copy() for index, track in enumerate(track_ids)
        }
        receipt = {
            "schema": "gnss-drao-doy233-model-blind-admission-v1",
            "state": "PRIMARY_MEASUREMENT_ADMITTED_FOR_OPAQUE_SCORE",
            "complete_opaque_tracks": list(track_ids),
            "structural_counts": dict(
                sorted(Counter(row["state"] for row in scan.coverage).items())
            ),
            "geometry_free": geometry_rows,
            "same_path_witness": {
                "exclusions_evaluated": 7,
                "rows": witness_rows,
                "heldout_refit": False,
            },
            "observation_values_persisted": 0,
            "orbital_model_used_for_admission": False,
        }
        strict_json(receipt)
        return receipt, tracks
    finally:
        phase_if.fill(0.0)
        code_if.fill(0.0)
        witness.fill(0.0)


def _final_outcome(
    score: Mapping[str, object],
    registry: Mapping[str, Mapping[str, object]],
    track_reveal: Mapping[str, str],
    model_reveal: Mapping[str, str],
) -> tuple[str, dict[str, object]]:
    state = str(score["score_state"])
    if state == "NONORBITAL_FAMILY_PREFERRED":
        return "DRAO_NONORBITAL_NULL_SUPPORTED", {}
    if state == "AMBIGUOUS":
        return "AMBIGUOUS", {}
    if state == "NO_ADMISSIBLE_HYPOTHESIS":
        return "NO_ADMISSIBLE_HYPOTHESIS", {}
    if state != "ORBITAL_INJECTION_PREFERRED":
        raise PrimaryDescriptionError("OPAQUE_SCORE_STATE_UNKNOWN")
    best = registry[str(score["best_orbital_opaque_id"])]
    track_ids = tuple(sorted(track_reveal))
    excluded = int(best["excluded_index"])
    included = tuple(index for index in range(7) if index != excluded)
    assignment = tuple(best["assignment"])
    pairs = [
        {
            "opaque_track": track_ids[track_index],
            "observed_prn": track_reveal[track_ids[track_index]],
            "predicted_prn": model_reveal[assignment[local]],
        }
        for local, track_index in enumerate(included)
    ]
    excluded_prn = track_reveal[track_ids[excluded]]
    concordant = all(row["observed_prn"] == row["predicted_prn"] for row in pairs)
    concordant = concordant and excluded_prn not in set(model_reveal.values())
    return (
        "DRAO_ONE_CLUTTER_ORBIT_CODE_CONCORDANT"
        if concordant
        else "DRAO_ONE_CLUTTER_ORBIT_CODE_DISCORDANT",
        {"assignment": pairs, "excluded_prn": excluded_prn},
    )


ScoreFunction = Callable[..., dict[str, object]]


def execute_admitted_scan(
    scan: PrimaryScan,
    root: Path,
    *,
    score_function: ScoreFunction = scorer.score_one_clutter_tracks,
) -> dict[str, object]:
    """Run admission, opaque score, receipt hash, then identity reveal once."""

    tracks: dict[str, np.ndarray] = {}
    hypotheses: tuple[scorer.OpaqueHypothesis, ...] = ()
    try:
        admission, tracks = admit(scan)
        track_reveal = {
            frozen.opaque_track_id(satellite): satellite for satellite in scan.satellites
        }
        reveal_hash = sha256(strict_json(track_reveal).encode("ascii")).hexdigest()
        hypotheses, registry = hypothesis_surface(root)
        score = score_function(
            tracks, hypotheses, pairwise_guard_m=frozen.PAIRWISE_GUARD_M
        )
        encoded_score = strict_json(score)
        if any(prn in encoded_score for prn in track_reveal.values()):
            raise PrimaryDescriptionError("TRACK_IDENTITY_LEAKED_INTO_SCORE_RECEIPT")
        score_hash = scorer.receipt_sha256(score)

        reveal_artifact = _read_json(Path(root) / frozen.REVEAL_NAME)
        if frozen.canonical_sha256(Path(root) / frozen.REVEAL_NAME) != REVEAL_SHA256:
            raise PrimaryDescriptionError("IDENTITY_REVEAL_CHANGED_AFTER_SCORE")
        model_reveal = {
            str(row["opaque_model_id"]): str(row["satellite"])
            for row in reveal_artifact["model_mapping"]
        }
        outcome, revealed = _final_outcome(
            score, registry, track_reveal, model_reveal
        )
        receipt = {
            "schema": "gnss-drao-doy233-integrated-primary-outcome-v1",
            "outcome": outcome,
            "admission": admission,
            "pre_score_code_reveal_sha256": reveal_hash,
            "score_receipt": score,
            "score_receipt_sha256_before_reveal": score_hash,
            "reveal_performed_after_score_hash": True,
            "revealed_assignment": revealed,
            "retry_after_complete_hash": 0,
            "observation_values_persisted": 0,
            "derived_series_persisted": 0,
        }
        strict_json(receipt)
        return receipt
    finally:
        for values in tracks.values():
            values.fill(0.0)
        for hypothesis in hypotheses:
            hypothesis.model_matrix_m.fill(0.0)
        scan.erase()


def main() -> None:
    refuse_unselected_primary(Path(__file__).resolve().parent)


if __name__ == "__main__":
    main()
