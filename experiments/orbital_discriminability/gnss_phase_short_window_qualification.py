"""Single-use DOY 217 qualification for the frozen G22/G30 phase plan.

Both complete compressed artifacts are hashed in RAM before decoding.  Phase
scalars exist only long enough to evaluate the predeclared model-blind
geometry-free continuity clause.  This module has no orbit-prediction surface
and cannot access the DOY 220 primary.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import gc
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import subprocess
from typing import Final, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_phase_short_window_plan as frozen
from experiments.orbital_discriminability import gnss_structural_qualification as structural


QUALIFICATION_VERSION: Final = "g22-g30-phase-short-window-doy217-v1"
OUTCOME_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_OUTCOME.json"
COVERAGE_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_COVERAGE.jsonl"
SUMMARY_NAME: Final = "GNSS_PHASE_SHORT_WINDOW_QUALIFICATION_SUMMARY.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_DOY217_SHORT_WINDOW_QUALIFICATION_ONCE"
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 20_000_000

SATELLITES: Final = ("G22", "G30")
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
OPTIONAL_DIAGNOSTIC: Final = ("S1C", "S2W")
OBSERVABLES: Final = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")

SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
GPS_L1_HZ: Final = 1_575_420_000.0
GPS_L2_HZ: Final = 1_227_600_000.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / GPS_L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / GPS_L2_HZ


@dataclass(frozen=True, slots=True)
class ProductLocator:
    station: str
    name: str
    url: str


PRODUCTS: Final = (
    ProductLocator(
        "GOLD00USA",
        "GOLD00USA_R_20262170000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/217/"
        "GOLD00USA_R_20262170000_01D_30S_MO.crx.gz",
    ),
    ProductLocator(
        "NLIB00USA",
        "NLIB00USA_R_20262170000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/217/"
        "NLIB00USA_R_20262170000_01D_30S_MO.crx.gz",
    ),
)

EXPECTED_CONFIGURATION: Final = {
    "GOLD00USA": {
        "receiver_type": "JAVAD TRE_G3TH DELTA",
        "receiver_version": "4.2.03",
        "antenna_type": "AOAD/M_T NONE",
    },
    "NLIB00USA": {
        "receiver_type": "SEPT POLARX5TR",
        "receiver_version": "5.7.0",
        "antenna_type": "JAVRINGANT_DM SCIS",
    },
}

PRESENT: Final = "PRESENT"
BLANK: Final = "BLANK"
TRAILING_FIELD_OMITTED: Final = "TRAILING_FIELD_OMITTED"
CONTINUATION_SUPPORTED: Final = "CONTINUATION_SUPPORTED"
CONTINUATION_UNSUPPORTED: Final = "CONTINUATION_UNSUPPORTED"
RECORD_INVALID: Final = "RECORD_INVALID"
_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


class QualificationFailure(ValueError):
    """A frozen measurement-capability clause failed."""


class MaterializationError(RuntimeError):
    """A complete predeclared artifact could not be obtained."""


class DescriptionError(RuntimeError):
    """Software or receipt description failed; not a physical rejection."""


@dataclass(frozen=True, slots=True)
class _Record:
    fields: tuple[bytes, ...]
    field_count: int
    continuation_state: str


@dataclass(slots=True)
class StationScan:
    station: str
    header: dict[str, object]
    coverage: list[dict[str, object]]
    core_valid: np.ndarray
    code_present: np.ndarray
    phase_cycles: np.ndarray

    def erase(self) -> None:
        self.core_valid.fill(False)
        self.code_present.fill(False)
        self.phase_cycles.fill(0.0)


class _LineReader:
    def __init__(self, payload: bytearray):
        self._stream = io.BytesIO(payload)
        self._pending: bytes | None = None

    def readline(self) -> bytes:
        if self._pending is not None:
            line, self._pending = self._pending, None
            return line
        return self._stream.readline()

    def push(self, line: bytes) -> None:
        if self._pending is not None:
            raise DescriptionError("MULTIPLE_LINE_PUSHBACK")
        self._pending = line


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def expected_epochs() -> tuple[datetime, ...]:
    start = frozen.QUALIFICATION_RAW_START
    result = tuple(
        start + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(result[-1]) != "2026-08-05T07:03:00.000000Z":
        raise DescriptionError("FROZEN_WINDOW_GRID_CHANGED")
    return result


def manifest() -> dict[str, object]:
    result = {
        "qualification_version": QUALIFICATION_VERSION,
        "proof_plan_manifest_sha256": frozen.manifest_sha256(),
        "duration_receipt_sha256": frozen.DURATION_RECEIPT_SHA256,
        "products": [asdict(product) for product in PRODUCTS],
        "window": {
            "start_gps": structural.format_gps_epoch(expected_epochs()[0]),
            "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
        },
        "signals": {
            "satellites": list(SATELLITES),
            "core_phase": list(CORE_PHASE),
            "same_path_code": list(SAME_PATH_CODE),
            "optional_diagnostic": list(OPTIONAL_DIAGNOSTIC),
        },
        "transport": {
            "maximum_attempts_per_locator": MAX_TRANSPORT_ATTEMPTS,
            "timeout_s": HTTP_TIMEOUT_S,
            "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
            "complete_hash_before_decode": True,
        },
        "health": {
            "geometry_free_second_difference_limit_m": (
                frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
            ),
            "orbital_model_available_to_qualification": False,
        },
        "persistence": {
            "compressed_artifact": 0,
            "decoded_rinex": 0,
            "observation_values": 0,
            "structural_and_aggregate_health_receipts_only": True,
        },
        "forbidden": [
            "DOY220 discovery URL header payload or value access",
            "orbital navigation prediction null or score",
            "qualification-window movement or substitute date",
            "phase code or SNR scalar persistence",
            "post-health threshold change",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _read_header(reader: _LineReader) -> tuple[bytes, ...]:
    lines: list[bytes] = []
    for _ in range(headers.MAX_HEADER_LINES):
        line = reader.readline()
        if not line:
            raise QualificationFailure("HEADER_INCOMPLETE")
        lines.append(line)
        if headers.header_label(line) == "END OF HEADER":
            return tuple(lines)
    raise QualificationFailure("HEADER_LINE_LIMIT_EXCEEDED")


def _validate_header(
    parsed: Mapping[str, object], locator: ProductLocator
) -> dict[str, object]:
    station = locator.station
    if str(parsed["marker_name"]) != station[:4]:
        raise QualificationFailure(f"MARKER_IDENTITY_MISMATCH:{station}")
    if float(parsed["interval_s"]) != float(frozen.STEP_S):
        raise QualificationFailure(f"INTERVAL_CHANGED:{station}")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise QualificationFailure(f"OBSERVATION_TIME_SYSTEM_NOT_GPS:{station}")
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise QualificationFailure(f"FROZEN_WINDOW_NOT_COVERED:{station}")
    expected = EXPECTED_CONFIGURATION[station]
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != expected["receiver_type"]:
        raise QualificationFailure(f"RECEIVER_TYPE_CHANGED:{station}")
    if _normalize(receiver["version_or_radome"]) != expected["receiver_version"]:
        raise QualificationFailure(f"RECEIVER_VERSION_CHANGED:{station}")
    if _normalize(antenna["type"]) != expected["antenna_type"]:
        raise QualificationFailure(f"ANTENNA_TYPE_CHANGED:{station}")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise QualificationFailure(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{station}:{','.join(missing)}"
        )
    return {
        "station": station,
        "marker_name": parsed["marker_name"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna["type"]),
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "gps_observables": list(gps_types),
        "full_frozen_window_covered": True,
    }


def _field_chunks(payload: bytes) -> tuple[bytes, ...]:
    payload = payload.rstrip(b"\r\n")
    if not payload:
        return ()
    count = (len(payload) + 15) // 16
    padded = payload.ljust(count * 16, b" ")
    return tuple(
        padded[index : index + 16] for index in range(0, len(padded), 16)
    )


def _read_record(
    reader: _LineReader, system_types: Mapping[str, Sequence[str]]
) -> tuple[str, _Record]:
    line = reader.readline()
    if not line or not _SATELLITE_PATTERN.match(line):
        if line.startswith(b"   "):
            raise QualificationFailure(CONTINUATION_UNSUPPORTED)
        raise QualificationFailure(f"{RECORD_INVALID}:SATELLITE_RECORD")
    satellite = line[:3].decode("ascii", errors="strict")
    system = satellite[0]
    if system not in system_types:
        raise QualificationFailure(f"{RECORD_INVALID}:UNDECLARED_SYSTEM_{system}")
    expected = len(system_types[system])
    fields = list(_field_chunks(line[3:]))
    continuation = False
    while len(fields) < expected:
        following = reader.readline()
        if not following:
            break
        if following.startswith(b">") or _SATELLITE_PATTERN.match(following):
            reader.push(following)
            break
        if not following.startswith(b"   "):
            raise QualificationFailure(CONTINUATION_UNSUPPORTED)
        continuation = True
        fields.extend(_field_chunks(following[3:]))
    if len(fields) > expected:
        raise QualificationFailure(f"{RECORD_INVALID}:FIELD_COUNT_OVERFLOW")
    return satellite, _Record(
        fields=tuple(fields),
        field_count=len(fields),
        continuation_state=(CONTINUATION_SUPPORTED if continuation else "NOT_REQUIRED"),
    )


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        integer = int(second)
        microsecond = int(round((second - integer) * 1_000_000))
        epoch = datetime(
            int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]),
            int(parts[5]), integer, microsecond, tzinfo=timezone.utc,
        )
        return epoch, int(parts[7]), int(parts[8])
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise QualificationFailure(f"{RECORD_INVALID}:EPOCH") from exc


def _parse_lli(field: bytes) -> str:
    token = field[14:15]
    if token in (b"", b" ", b"0"):
        return "ZERO_OR_BLANK"
    if token.isdigit():
        return "NONZERO"
    return "INVALID"


def _parse_phase(field: bytes) -> float:
    try:
        value = float(field[:14].strip().replace(b"D", b"E"))
    except ValueError as exc:
        raise QualificationFailure(f"{RECORD_INVALID}:PHASE_SCALAR") from exc
    if not np.isfinite(value):
        raise QualificationFailure(f"{RECORD_INVALID}:NONFINITE_PHASE")
    return value


def _read_window_records(
    reader: _LineReader, system_types: Mapping[str, Sequence[str]]
) -> tuple[dict[tuple[datetime, str], _Record], dict[datetime, int]]:
    epochs = expected_epochs()
    epoch_set = set(epochs)
    start, stop = epochs[0], epochs[-1]
    records: dict[tuple[datetime, str], _Record] = {}
    flags: dict[datetime, int] = {}
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise QualificationFailure(f"{RECORD_INVALID}:NON_EPOCH_LINE")
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        if epoch > stop:
            break
        in_window = start <= epoch <= stop
        if in_window:
            if epoch not in epoch_set:
                raise QualificationFailure(f"{RECORD_INVALID}:OFF_GRID_EPOCH")
            if epoch in flags:
                raise QualificationFailure(f"{RECORD_INVALID}:DUPLICATE_EPOCH")
            flags[epoch] = flag
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise QualificationFailure(
                        f"{RECORD_INVALID}:TRUNCATED_SPECIAL_EVENT"
                    )
            continue
        if flag == 6:
            for _ in range(satellite_count):
                _read_record(reader, system_types)
            continue
        if flag not in {0, 1}:
            raise QualificationFailure(f"{RECORD_INVALID}:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            satellite, record = _read_record(reader, system_types)
            if not in_window or satellite not in SATELLITES:
                continue
            key = epoch, satellite
            if key in records:
                raise QualificationFailure(
                    f"{RECORD_INVALID}:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = record
    return records, flags


def _physical_role(observable: str) -> str:
    if observable in CORE_PHASE:
        return "CORE_PHASE"
    if observable in SAME_PATH_CODE:
        return "SAME_PATH_CODE_WITNESS"
    return "OPTIONAL_DIAGNOSTIC"


def scan_decoded(decoded: bytearray, locator: ProductLocator) -> StationScan:
    reader = _LineReader(decoded)
    header_lines = _read_header(reader)
    parsed = headers.parse_header_lines(header_lines)
    header_summary = _validate_header(parsed, locator)
    system_types = {
        system: tuple(values)
        for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {
        observable: (
            gps_types.index(observable) if observable in gps_types else None
        )
        for observable in OBSERVABLES
    }
    records, flags = _read_window_records(reader, system_types)
    epochs = expected_epochs()
    satellite_index = {name: index for index, name in enumerate(SATELLITES)}
    phase_cycles = np.full(
        (frozen.RAW_EPOCHS, len(SATELLITES), len(CORE_PHASE)),
        np.nan,
        dtype=np.float64,
    )
    phase_good = np.zeros_like(phase_cycles, dtype=np.bool_)
    code_present = np.zeros(
        (frozen.RAW_EPOCHS, len(SATELLITES), len(SAME_PATH_CODE)),
        dtype=np.bool_,
    )
    coverage: list[dict[str, object]] = []
    for row, epoch in enumerate(epochs):
        epoch_flag = flags.get(epoch)
        for satellite in SATELLITES:
            sat = satellite_index[satellite]
            record = records.get((epoch, satellite))
            for observable in OBSERVABLES:
                header_index = indices[observable]
                field: bytes | None = None
                if header_index is None:
                    state = BLANK
                    source = "OPTIONAL_OBSERVABLE_NOT_DECLARED"
                    field_count = record.field_count if record else 0
                    continuation = "NOT_APPLICABLE"
                elif record is None:
                    state = BLANK
                    source = (
                        "SATELLITE_RECORD_ABSENT"
                        if epoch_flag == 0
                        else "EPOCH_ABSENT_OR_NONOBSERVATION"
                    )
                    field_count = 0
                    continuation = "NOT_APPLICABLE"
                elif header_index >= record.field_count:
                    state = TRAILING_FIELD_OMITTED
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    field_count = record.field_count
                    continuation = record.continuation_state
                else:
                    field = record.fields[header_index]
                    state = PRESENT if field[:14].strip() else BLANK
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    field_count = record.field_count
                    continuation = record.continuation_state
                lli_state = "NOT_APPLICABLE"
                if observable in CORE_PHASE:
                    phase = CORE_PHASE.index(observable)
                    if state == PRESENT and field is not None:
                        lli_state = _parse_lli(field)
                        if lli_state == "ZERO_OR_BLANK" and epoch_flag == 0:
                            phase_cycles[row, sat, phase] = _parse_phase(field)
                            phase_good[row, sat, phase] = True
                    else:
                        lli_state = "UNAVAILABLE"
                elif observable in SAME_PATH_CODE:
                    code = SAME_PATH_CODE.index(observable)
                    code_present[row, sat, code] = state == PRESENT
                coverage.append(
                    {
                        "station": locator.station,
                        "gps_epoch": structural.format_gps_epoch(epoch),
                        "satellite": satellite,
                        "observable": observable,
                        "physical_role": _physical_role(observable),
                        "state": state,
                        "header_declared_index": header_index,
                        "reconstructed_field_count": field_count,
                        "source_line_class": source,
                        "continuation_state": continuation,
                        "lli_state": lli_state,
                        "epoch_flag": epoch_flag,
                    }
                )
    core_valid = np.all(phase_good, axis=2)
    expected_rows = frozen.RAW_EPOCHS * len(SATELLITES) * len(OBSERVABLES)
    if len(coverage) != expected_rows:
        phase_cycles.fill(0.0)
        phase_good.fill(False)
        code_present.fill(False)
        raise DescriptionError(
            f"COVERAGE_ROW_COUNT_CHANGED:{locator.station}:{len(coverage)}"
        )
    phase_good.fill(False)
    return StationScan(
        station=locator.station,
        header=header_summary,
        coverage=coverage,
        core_valid=core_valid,
        code_present=code_present,
        phase_cycles=phase_cycles,
    )


def _segments(valid: np.ndarray) -> list[dict[str, object]]:
    epochs = expected_epochs()
    result: list[dict[str, object]] = []
    start: int | None = None
    for index, present in enumerate(valid.tolist() + [False]):
        if present and start is None:
            start = index
        elif not present and start is not None:
            stop = index - 1
            result.append(
                {
                    "start_gps": structural.format_gps_epoch(epochs[start]),
                    "stop_gps": structural.format_gps_epoch(epochs[stop]),
                    "epoch_count": stop - start + 1,
                    "duration_s": (stop - start) * frozen.STEP_S,
                }
            )
            start = None
    return result


def _geometry_free_health(scans: Sequence[StationScan]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    satisfied = True
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            valid = scan.core_valid[:, sat_index]
            evaluated = 0
            violations = 0
            maximum: float | None = None
            if np.all(valid):
                phase = scan.phase_cycles[:, sat_index, :]
                geometry_free = (
                    LAMBDA_L1_M * phase[:, 0] - LAMBDA_L2_M * phase[:, 1]
                )
                second_difference = np.diff(geometry_free, n=2)
                absolute = np.abs(second_difference)
                evaluated = int(absolute.size)
                maximum = float(np.max(absolute))
                violations = int(
                    np.count_nonzero(
                        absolute
                        > frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                    )
                )
                geometry_free.fill(0.0)
                second_difference.fill(0.0)
                absolute.fill(0.0)
            admitted = evaluated == frozen.RAW_EPOCHS - 2 and violations == 0
            satisfied = satisfied and admitted
            rows.append(
                {
                    "station": scan.station,
                    "satellite": satellite,
                    "evaluated_second_differences": evaluated,
                    "maximum_absolute_second_difference_m": maximum,
                    "violation_count": violations,
                    "admitted": admitted,
                }
            )
    return {
        "state": "SATISFIED" if satisfied else "UNSATISFIED",
        "threshold_m": frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
        "links": rows,
        "orbital_prediction_used": False,
        "phase_values_persisted": 0,
    }


def _code_witness(scans: Sequence[StationScan]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    satisfied = True
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            for code_index, observable in enumerate(SAME_PATH_CODE):
                present = scan.code_present[:, sat_index, code_index]
                count = int(np.count_nonzero(present))
                fraction = count / frozen.RAW_EPOCHS
                boundaries = all(
                    bool(present[index])
                    for index in frozen.CODE_REQUIRED_RAW_INDICES
                )
                admitted = (
                    fraction >= frozen.CODE_MINIMUM_COVERAGE_FRACTION
                    and boundaries
                )
                satisfied = satisfied and admitted
                rows.append(
                    {
                        "station": scan.station,
                        "satellite": satellite,
                        "observable": observable,
                        "present_epochs": count,
                        "total_epochs": frozen.RAW_EPOCHS,
                        "coverage_fraction": fraction,
                        "required_raw_indices": list(
                            frozen.CODE_REQUIRED_RAW_INDICES
                        ),
                        "required_boundaries_present": boundaries,
                        "admitted": admitted,
                    }
                )
    return {
        "state": "SATISFIED" if satisfied else "UNSATISFIED",
        "links": rows,
    }


def evaluate(scans: Sequence[StationScan]) -> dict[str, object]:
    if tuple(scan.station for scan in scans) != tuple(
        product.station for product in PRODUCTS
    ):
        raise DescriptionError("STATION_ORDER_CHANGED")
    joint = np.ones(frozen.RAW_EPOCHS, dtype=np.bool_)
    per_link = []
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            valid = scan.core_valid[:, sat_index]
            joint &= valid
            per_link.append(
                {
                    "station": scan.station,
                    "satellite": satellite,
                    "maximal_segments": _segments(valid),
                    "full_window": bool(np.all(valid)),
                }
            )
    joint_segments = _segments(joint)
    full_joint = bool(np.all(joint))
    health = _geometry_free_health(scans)
    code = _code_witness(scans)
    counts = Counter(row["state"] for scan in scans for row in scan.coverage)
    passed = (
        full_joint
        and health["state"] == "SATISFIED"
        and code["state"] == "SATISFIED"
    )
    finite_phase_count = sum(
        int(np.count_nonzero(np.isfinite(scan.phase_cycles))) for scan in scans
    )
    result = {
        "schema": "gnss-phase-short-window-qualification-summary-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "window": {
            "start_gps": structural.format_gps_epoch(expected_epochs()[0]),
            "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
        },
        "headers": [scan.header for scan in scans],
        "structural_counts": dict(sorted(counts.items())),
        "coverage_rows": sum(len(scan.coverage) for scan in scans),
        "per_link_core_segments": per_link,
        "joint_core_segments": joint_segments,
        "full_joint_window": full_joint,
        "same_path_code_witness": code,
        "geometry_free_phase_health": health,
        "optional_diagnostic_policy": "DESCRIPTIVE_ONLY_NEVER_FATAL",
        "phase_scalars_parsed_in_ram": finite_phase_count,
        "phase_scalars_persisted": 0,
        "code_or_snr_scalars_parsed": 0,
        "orbital_model_used": False,
        "orbital_scores_produced": 0,
        "outcome": (
            "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED"
            if passed
            else "GNSS_SHORT_WINDOW_QUALIFICATION_FAILED"
        ),
    }
    joint.fill(False)
    strict_json(result)
    return result


def materialize(locator: ProductLocator) -> tuple[bytearray, dict[str, object]]:
    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        payload = bytearray()
        try:
            request = Request(
                locator.url,
                headers={"User-Agent": "Satellite-RF-Observatory/qualification"},
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    payload.extend(block)
                    if len(payload) > MAX_COMPRESSED_BYTES:
                        raise MaterializationError(
                            f"COMPRESSED_SIZE_LIMIT:{locator.station}"
                        )
            if not payload:
                raise MaterializationError(f"EMPTY_ARTIFACT:{locator.station}")
            return payload, {
                "station": locator.station,
                "product": locator.name,
                "url": locator.url,
                "attempts": attempt,
                "complete_file_bytes": len(payload),
                "complete_file_sha256": sha256(payload).hexdigest(),
                "hash_before_any_decode": True,
            }
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            MaterializationError,
        ) as exc:
            payload[:] = b"\x00" * len(payload)
            failures.append(f"{type(exc).__name__}:{exc}")
    raise MaterializationError(
        f"ARTIFACT_MATERIALIZATION_FAILED:{locator.station}:"
        + "|".join(failures)
    )


def decode_in_memory(payload: bytearray, station: str) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise QualificationFailure(f"HATANAKA_DECODE_FAILED:{station}") from exc


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        strict_json(value, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.write_text(
        "".join(strict_json(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _base_outcome(
    outcome: str,
    artifacts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    return {
        "schema": "gnss-phase-short-window-qualification-outcome-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "outcome": outcome,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "proof_plan_manifest_sha256": frozen.manifest_sha256(),
        "duration_receipt_sha256": frozen.DURATION_RECEIPT_SHA256,
        "artifacts": list(artifacts),
        "persistence": {
            "compressed_rinex_bytes": 0,
            "decoded_rinex_bytes": 0,
            "observation_values": 0,
            "structural_and_aggregate_health_receipts_only": True,
        },
        "primary_doy220_access": {
            "products_discovered": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "orbital_prediction_access": 0,
        "orbital_scores_produced": 0,
        "substitute_date_authorized": False,
    }


def run_once(
    output_directory: Path, authority_token: str
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("DOY217_QUALIFICATION_AUTHORITY_REQUIRED")
    root = Path(__file__).resolve().parent
    frozen.verify_duration_receipt(root / frozen.DURATION_RECEIPT_NAME)
    directory = Path(output_directory)
    compressed_buffers: list[bytearray] = []
    decoded_buffers: list[bytearray] = []
    artifacts: list[dict[str, object]] = []
    scans: list[StationScan] = []
    try:
        for locator in PRODUCTS:
            payload, artifact = materialize(locator)
            compressed_buffers.append(payload)
            artifacts.append(artifact)
        for locator, payload in zip(PRODUCTS, compressed_buffers, strict=True):
            decoded = decode_in_memory(payload, locator.station)
            decoded_buffers.append(decoded)
            scans.append(scan_decoded(decoded, locator))
        summary = evaluate(scans)
        coverage_rows = [row for scan in scans for row in scan.coverage]
        coverage_path = directory / COVERAGE_NAME
        summary_path = directory / SUMMARY_NAME
        _write_jsonl(coverage_path, coverage_rows)
        _write_json(summary_path, summary)
        outcome = {
            **_base_outcome(summary["outcome"], artifacts),
            "coverage": {
                "name": COVERAGE_NAME,
                "rows": len(coverage_rows),
                "sha256": canonical_sha256(coverage_path),
            },
            "summary": {
                "name": SUMMARY_NAME,
                "sha256": canonical_sha256(summary_path),
            },
            "clause_states": {
                "artifact_materialization_and_hash": "SATISFIED",
                "header_configuration_and_window": "SATISFIED",
                "core_phase_and_lli": (
                    "SATISFIED" if summary["full_joint_window"] else "UNSATISFIED"
                ),
                "same_path_code_witness": summary[
                    "same_path_code_witness"
                ]["state"],
                "geometry_free_phase_health": summary[
                    "geometry_free_phase_health"
                ]["state"],
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "observation_access": {
                "qualification_products": len(PRODUCTS),
                "qualification_headers": len(scans),
                "compressed_bytes_in_ram": sum(
                    int(item["complete_file_bytes"]) for item in artifacts
                ),
                "decoded_rinex_bytes_in_ram": sum(
                    len(payload) for payload in decoded_buffers
                ),
                "phase_scalars_parsed_in_ram": summary[
                    "phase_scalars_parsed_in_ram"
                ],
                "phase_scalars_persisted": 0,
                "code_or_snr_scalars_parsed": 0,
            },
            "next_authority": (
                "PRIMARY_SEAL_REVIEW_ONLY"
                if summary["outcome"]
                == "GNSS_SHORT_WINDOW_QUALIFICATION_PASSED"
                else "NONE_ROLE_PAIR_CLOSED"
            ),
        }
    except MaterializationError as exc:
        outcome = {
            **_base_outcome(
                "GNSS_SHORT_WINDOW_ARTIFACT_MATERIALIZATION_FAILED", artifacts
            ),
            "reason": str(exc),
            "clause_states": {
                "artifact_materialization_and_hash": "UNSATISFIED",
                "measurement_qualification": "NOT_EVALUATED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "NONE_ROLE_PAIR_NOT_QUALIFIED",
        }
    except QualificationFailure as exc:
        outcome = {
            **_base_outcome("GNSS_SHORT_WINDOW_QUALIFICATION_FAILED", artifacts),
            "reason": str(exc),
            "clause_states": {
                "artifact_materialization_and_hash": (
                    "SATISFIED" if len(artifacts) == len(PRODUCTS) else "UNSATISFIED"
                ),
                "measurement_qualification": "UNSATISFIED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "NONE_ROLE_PAIR_CLOSED",
        }
    except Exception as exc:
        outcome = {
            **_base_outcome("GNSS_SHORT_WINDOW_DESCRIPTION_ERROR", artifacts),
            "reason": f"{type(exc).__name__}:{exc}",
            "clause_states": {
                "description": "UNSATISFIED",
                "measurement_qualification": "NOT_EVALUATED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "NONE_DESCRIPTION_REPAIR_ONLY",
        }
    finally:
        for scan in scans:
            scan.erase()
        for payload in decoded_buffers + compressed_buffers:
            payload[:] = b"\x00" * len(payload)
        gc.collect()
    strict_json(outcome)
    _write_json(directory / OUTCOME_NAME, outcome)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    if not args.execute_live:
        raise SystemExit("LIVE_QUALIFICATION_AUTHORITY_REQUIRED")
    print(strict_json(run_once(args.output_directory, args.authority)))


if __name__ == "__main__":
    main()
