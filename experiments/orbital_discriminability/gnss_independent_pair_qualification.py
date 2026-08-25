"""One-shot ALGO/MDO DOY217 measurement-path qualification.

This experiment-specific executor accepts only the two products frozen by the
independent-pair qualification plan.  Both complete compressed products are
held and hashed in RAM before either is decoded.  Phase values exist only long
enough to evaluate model-blind continuity; persisted receipts contain artifact
identity, field topology, and aggregate health, never observation values.
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
import platform
import re
import subprocess
from typing import Final, Iterable, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_independent_pair_qualification_plan as frozen
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_structural_qualification as structural


QUALIFICATION_VERSION: Final = "algo-mdo-g22-g30-doy217-qualification-v1"
OUTCOME_NAME: Final = "GNSS_INDEPENDENT_PAIR_QUALIFICATION_OUTCOME.json"
COVERAGE_NAME: Final = "GNSS_INDEPENDENT_PAIR_QUALIFICATION_COVERAGE.jsonl"
SUMMARY_NAME: Final = "GNSS_INDEPENDENT_PAIR_QUALIFICATION_SUMMARY.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_ALGO_MDO_DOY217_QUALIFICATION_ONCE"
PROOF_PLAN_MANIFEST_SHA256: Final = (
    "9f6d2ec41717666910b82e03341dbfc9ba6dd8285d481a93f0699e912206c3e4"
)
PROOF_PLAN_SOURCE_SHA256: Final = (
    "7f5a0959b3280014ac8811efb614331135c26cbcfece61ea6685fca9f79147b0"
)
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 10_000_000

SATELLITES: Final = (frozen.TARGET, frozen.REFERENCE)
CORE_PHASE: Final = frozen.CORE_PHASE
SAME_PATH_CODE: Final = frozen.SAME_PATH_CODE
OPTIONAL_DIAGNOSTIC: Final = frozen.OPTIONAL_DIAGNOSTIC
OBSERVABLES: Final = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")

SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
GPS_L1_HZ: Final = 1_575_420_000.0
GPS_L2_HZ: Final = 1_227_600_000.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / GPS_L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / GPS_L2_HZ

PRESENT: Final = "PRESENT"
BLANK: Final = "BLANK"
TRAILING_FIELD_OMITTED: Final = "TRAILING_FIELD_OMITTED"
CONTINUATION_SUPPORTED: Final = "CONTINUATION_SUPPORTED"
CONTINUATION_UNSUPPORTED: Final = "CONTINUATION_UNSUPPORTED"
RECORD_INVALID: Final = "RECORD_INVALID"
_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


@dataclass(frozen=True, slots=True)
class ProductLocator:
    """One frozen qualification product and its descriptive HEAD metadata."""

    station: str
    name: str
    url: str
    head_content_length: int
    head_etag: str
    head_last_modified: str


PRODUCTS: Final = tuple(
    ProductLocator(
        item.station,
        item.name,
        item.url,
        item.content_length,
        item.etag,
        item.last_modified,
    )
    for item in frozen.PRODUCTS
)

EXPECTED_CONFIGURATION: Final = {
    root.station: {
        "receiver_serial": root.receiver_serial,
        "receiver_type": root.receiver_type.replace("_", " "),
        "receiver_version": root.receiver_firmware,
        "antenna_serial": root.antenna_serial,
        "antenna_type": root.antenna_type.replace("_NONE", " NONE").replace(
            "_SCIS", " SCIS"
        ),
    }
    for root in frozen.ROOTS
}


class QualificationFailure(ValueError):
    """A predeclared physical measurement-capability clause failed."""


class MaterializationError(RuntimeError):
    """A complete frozen artifact was not obtained and hashed."""


class DescriptionError(RuntimeError):
    """Software or receipt description failed without a physical refusal."""


@dataclass(frozen=True, slots=True)
class _Record:
    fields: tuple[bytes, ...]
    field_count: int


@dataclass(slots=True)
class StationScan:
    station: str
    header: dict[str, object]
    coverage: list[dict[str, object]]
    core_valid: np.ndarray
    code_present: np.ndarray
    phase_cycles: np.ndarray

    def erase(self) -> None:
        """Overwrite all arrays that could retain observation information."""

        self.core_valid.fill(False)
        self.code_present.fill(False)
        self.phase_cycles.fill(0.0)


class _LineReader:
    def __init__(self, payload: bytearray):
        self._stream = io.BytesIO(payload)

    def readline(self) -> bytes:
        return self._stream.readline()


def strict_json(value: object, *, pretty: bool = False) -> str:
    """Serialize receipts deterministically and reject non-finite values."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_sha256(path: Path) -> str:
    """Hash a text artifact after the repository CRLF-to-LF convention."""

    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    """Return the canonical hash of this experiment-specific executor."""

    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    """Return the source commit used for the one-shot execution."""

    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def dependency_versions() -> dict[str, str]:
    """Describe only dependencies participating in the decoding path."""

    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "hatanaka": getattr(hatanaka, "__version__", "UNKNOWN"),
    }


def expected_epochs() -> tuple[datetime, ...]:
    """Return the immutable 139-epoch qualification grid."""

    result = tuple(
        frozen.QUALIFICATION_RAW_START
        + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(result[-1]) != "2026-08-05T07:03:00.000000Z":
        raise DescriptionError("FROZEN_WINDOW_GRID_CHANGED")
    return result


def manifest() -> dict[str, object]:
    """Build the frozen executor surface without opening any observation."""

    result = {
        "schema": "gnss-independent-pair-qualification-manifest-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "executor_source_sha256": source_sha256(),
        "proof_plan_manifest_sha256": PROOF_PLAN_MANIFEST_SHA256,
        "proof_plan_source_sha256": PROOF_PLAN_SOURCE_SHA256,
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
            "both_complete_hashes_before_first_decode": True,
            "resume_only_before_complete_hash_and_decode": True,
        },
        "header_identity": EXPECTED_CONFIGURATION,
        "transform_ledger": {
            "compression": "GZIP_PLUS_HATANAKA_CRINEX_STRICT_DECODE_IN_RAM",
            "rinex_scale_factor": "REJECT_IF_PRESENT_UNSUPPORTED",
            "rinex_phase_shift": (
                "RETAIN_DECLARATION_STATIC_OFFSET_IS_SECOND_DIFFERENCE_INVARIANT"
            ),
            "receiver_clock_offset": "RETAIN_EXPLICIT_OR_STANDARD_DEFAULT",
            "geometry_free": "LAMBDA_L1_TIMES_L1C_MINUS_LAMBDA_L2_TIMES_L2W",
            "health_operator": "SECOND_TIME_DIFFERENCE_PER_STATION_SATELLITE",
        },
        "health": {
            "geometry_free_second_difference_limit_m": (
                frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
            ),
            "code_minimum_coverage_fraction": (
                frozen.CODE_MINIMUM_COVERAGE_FRACTION
            ),
            "code_required_raw_indices": list(frozen.CODE_REQUIRED_RAW_INDICES),
            "orbital_model_available": False,
        },
        "persistence": {
            "compressed_artifact_bytes": 0,
            "decoded_rinex_bytes": 0,
            "observation_values": 0,
            "structural_and_aggregate_health_receipts_only": True,
        },
        "forbidden": [
            "DOY219 product discovery locator header payload or value access",
            "broadcast navigation orbital prediction null or score",
            "qualification-window movement substitute pair or substitute date",
            "phase code or signal-strength scalar persistence",
            "post-access threshold or feature change",
        ],
    }
    _validate_manifest(result)
    strict_json(result)
    return result


def _validate_manifest(value: Mapping[str, object]) -> None:
    """Reject primary leakage or drift from the reviewed proof plan."""

    if frozen.manifest_sha256() != PROOF_PLAN_MANIFEST_SHA256:
        raise DescriptionError("PROOF_PLAN_MANIFEST_CHANGED")
    if frozen.canonical_sha256(Path(frozen.__file__)) != PROOF_PLAN_SOURCE_SHA256:
        raise DescriptionError("PROOF_PLAN_SOURCE_CHANGED")
    encoded = strict_json(value)
    if "2026219" in encoded or "/219/" in encoded:
        raise DescriptionError("PRIMARY_LOCATOR_ENTERED_EXECUTOR")
    if [item["station"] for item in value["products"]] != [
        "ALGO00CAN",
        "MDO100USA",
    ]:
        raise DescriptionError("QUALIFICATION_PRODUCT_SET_CHANGED")
    if any("/217/" not in item["url"] for item in value["products"]):
        raise DescriptionError("QUALIFICATION_DATE_CHANGED")


def manifest_sha256() -> str:
    """Return the immutable executor manifest hash."""

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
    if not 3.0 <= float(parsed["rinex_version"]) < 5.0:
        raise QualificationFailure(f"RINEX_VERSION_NOT_EXPLICIT:{station}")
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
    comparisons = {
        "RECEIVER_SERIAL": (receiver["serial"], expected["receiver_serial"]),
        "RECEIVER_TYPE": (receiver["type"], expected["receiver_type"]),
        "RECEIVER_VERSION": (
            receiver["version_or_radome"],
            expected["receiver_version"],
        ),
        "ANTENNA_SERIAL": (antenna["serial"], expected["antenna_serial"]),
        "ANTENNA_TYPE": (antenna["type"], expected["antenna_type"]),
    }
    for label, (actual, wanted) in comparisons.items():
        if _normalize(actual) != _normalize(wanted):
            raise QualificationFailure(f"{label}_CHANGED:{station}")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise QualificationFailure(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{station}:{','.join(missing)}"
        )
    scale_records = list(parsed.get("scale_factor_records", ()))
    if scale_records:
        raise QualificationFailure(f"UNSUPPORTED_SCALE_FACTOR_RECORD:{station}")
    if parsed["receiver_clock_offset_applied"] not in (0, 1):
        raise QualificationFailure(f"CLOCK_OFFSET_SEMANTICS_UNKNOWN:{station}")
    return {
        "station": station,
        "rinex_version": float(parsed["rinex_version"]),
        "marker_name": parsed["marker_name"],
        "receiver": receiver,
        "antenna": antenna,
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "receiver_clock_offset_provenance": parsed[
            "receiver_clock_offset_provenance"
        ],
        "gps_observables": list(gps_types),
        "scale_factor_records": scale_records,
        "phase_shift_records": list(parsed.get("phase_shift_records", ())),
        "applied_bias_records": list(parsed.get("applied_bias_records", ())),
        "full_frozen_window_covered": True,
    }


def _gps_observable_line_classes(
    header_lines: Iterable[bytes], gps_types: Sequence[str]
) -> dict[str, str]:
    classes: list[str] = []
    current_system: str | None = None
    for raw in header_lines:
        body = raw.rstrip(b"\r\n")
        label = body[60:80].decode("ascii").strip() if len(body) >= 60 else ""
        if label != "SYS / # / OBS TYPES":
            continue
        continuation = body[:1] == b" "
        if not continuation:
            current_system = body[:1].decode("ascii")
        if current_system != "G":
            continue
        values = body[7:60].decode("ascii").split()
        classes.extend(
            [CONTINUATION_SUPPORTED if continuation else "HEADER_INITIAL"]
            * len(values)
        )
    if len(classes) != len(gps_types):
        raise DescriptionError("GPS_HEADER_LINEAGE_COUNT_CHANGED")
    return dict(zip(gps_types, classes, strict=True))


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        integer = int(second)
        microsecond = int(round((second - integer) * 1_000_000))
        epoch = datetime(
            int(parts[1]),
            int(parts[2]),
            int(parts[3]),
            int(parts[4]),
            int(parts[5]),
            integer,
            microsecond,
            tzinfo=timezone.utc,
        )
        return epoch, int(parts[7]), int(parts[8])
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise QualificationFailure(f"{RECORD_INVALID}:EPOCH") from exc


def _read_window_records(
    reader: _LineReader,
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
                slip_record = reader.readline()
                if not slip_record or not _SATELLITE_PATTERN.match(slip_record):
                    raise QualificationFailure(f"{RECORD_INVALID}:CYCLE_SLIP_RECORD")
            continue
        if flag not in {0, 1}:
            raise QualificationFailure(f"{RECORD_INVALID}:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            record_line = reader.readline()
            if not record_line or not _SATELLITE_PATTERN.match(record_line):
                if record_line.startswith(b"   "):
                    raise QualificationFailure(CONTINUATION_UNSUPPORTED)
                raise QualificationFailure(f"{RECORD_INVALID}:SATELLITE_RECORD")
            satellite = record_line[:3].decode("ascii")
            if not in_window or satellite not in SATELLITES:
                continue
            payload = record_line[3:].rstrip(b"\r\n")
            field_count = (len(payload) + 15) // 16
            padded = payload.ljust(field_count * 16, b" ")
            fields = tuple(
                padded[offset : offset + 16]
                for offset in range(0, len(padded), 16)
            )
            key = epoch, satellite
            if key in records:
                raise QualificationFailure(
                    f"{RECORD_INVALID}:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = _Record(fields=fields, field_count=field_count)
    return records, flags


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


def _physical_role(observable: str) -> str:
    if observable in CORE_PHASE:
        return "CORE_PHASE"
    if observable in SAME_PATH_CODE:
        return "SAME_PATH_CODE_WITNESS"
    return "OPTIONAL_DIAGNOSTIC"


def scan_decoded(decoded: bytearray, locator: ProductLocator) -> StationScan:
    """Scan one decoded station while retaining no observation scalar."""

    reader = _LineReader(decoded)
    header_lines = _read_header(reader)
    try:
        parsed = headers.parse_header_lines(header_lines)
    except QualificationFailure:
        raise
    except Exception as exc:
        raise DescriptionError(f"HEADER_DESCRIPTION_ERROR:{locator.station}") from exc
    header_summary = _validate_header(parsed, locator)
    gps_types = tuple(parsed["observable_types"]["G"])
    indices = {
        observable: gps_types.index(observable) if observable in gps_types else None
        for observable in OBSERVABLES
    }
    line_classes = _gps_observable_line_classes(header_lines, gps_types)
    records, flags = _read_window_records(reader)
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
                    continuation = "NOT_REQUIRED"
                else:
                    field = record.fields[header_index]
                    state = PRESENT if field[:14].strip() else BLANK
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    continuation = line_classes.get(observable, "HEADER_INITIAL")
                    field_count = record.field_count
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
                        absolute > frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
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
        "minimum_coverage_fraction": frozen.CODE_MINIMUM_COVERAGE_FRACTION,
        "links": rows,
    }


def evaluate(scans: Sequence[StationScan]) -> dict[str, object]:
    """Evaluate only the clauses frozen before observation access."""

    if tuple(scan.station for scan in scans) != tuple(
        product.station for product in PRODUCTS
    ):
        raise DescriptionError("STATION_ORDER_CHANGED")
    joint = np.ones(frozen.RAW_EPOCHS, dtype=np.bool_)
    per_link: list[dict[str, object]] = []
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
        "schema": "gnss-independent-pair-qualification-summary-v1",
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
            "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
            if passed
            else "GNSS_INDEPENDENT_PAIR_QUALIFICATION_FAILED"
        ),
    }
    joint.fill(False)
    strict_json(result)
    return result


def materialize(locator: ProductLocator) -> tuple[bytearray, dict[str, object]]:
    """Fetch one complete artifact in RAM and hash it before returning."""

    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        payload = bytearray()
        try:
            request = Request(
                locator.url,
                headers={"User-Agent": "Satellite-RF-Observatory/qualification"},
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                response_headers = getattr(response, "headers", {})
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
                "head_metadata_was_descriptive_not_identity": True,
                "preaccess_head_content_length": locator.head_content_length,
                "response_content_length": response_headers.get("Content-Length"),
                "response_etag": response_headers.get("ETag"),
                "response_last_modified": response_headers.get("Last-Modified"),
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
    """Decode one already-hashed artifact without filesystem persistence."""

    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise QualificationFailure(f"HATANAKA_DECODE_FAILED:{station}") from exc


def _base_outcome(
    outcome: str, artifacts: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    return {
        "schema": "gnss-independent-pair-qualification-outcome-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "outcome": outcome,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "proof_plan_manifest_sha256": PROOF_PLAN_MANIFEST_SHA256,
        "proof_plan_source_sha256": PROOF_PLAN_SOURCE_SHA256,
        "dependencies": dependency_versions(),
        "artifacts": list(artifacts),
        "persistence": {
            "compressed_rinex_bytes": 0,
            "decoded_rinex_bytes": 0,
            "observation_values": 0,
            "structural_and_aggregate_health_receipts_only": True,
        },
        "future_primary_doy219_access": {
            "products_discovered": 0,
            "locators": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "orbital_prediction_access": 0,
        "orbital_scores_produced": 0,
        "fallback_pair_or_date_selected": False,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        strict_json(value, pretty=True) + "\n", encoding="utf-8", newline="\n"
    )


def _write_jsonl(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.write_text(
        "".join(strict_json(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def run_once(output_directory: Path, authority_token: str) -> dict[str, object]:
    """Perform the one authorised model-blind qualification execution."""

    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("ALGO_MDO_DOY217_QUALIFICATION_AUTHORITY_REQUIRED")
    root = Path(__file__).resolve().parent
    frozen.verify_screen_receipt(root / frozen.SCREEN_RECEIPT_NAME)
    manifest()
    directory = Path(output_directory)
    compressed_buffers: list[bytearray] = []
    decoded_buffers: list[bytearray] = []
    artifacts: list[dict[str, object]] = []
    scans: list[StationScan] = []
    coverage_rows: list[dict[str, object]] = []
    summary: dict[str, object] | None = None
    try:
        for locator in PRODUCTS:
            payload, artifact = materialize(locator)
            compressed_buffers.append(payload)
            artifacts.append(artifact)
        if len(artifacts) != len(PRODUCTS):
            raise DescriptionError("FIRST_DECODE_BEFORE_BOTH_COMPLETE_HASHES")
        for locator, payload in zip(PRODUCTS, compressed_buffers, strict=True):
            decoded = decode_in_memory(payload, locator.station)
            decoded_buffers.append(decoded)
            scans.append(scan_decoded(decoded, locator))
        summary = evaluate(scans)
        coverage_rows = [row for scan in scans for row in scan.coverage]
        outcome = {
            **_base_outcome(summary["outcome"], artifacts),
            "clause_states": {
                "artifact_materialization_and_hash": "SATISFIED",
                "header_configuration_and_window": "SATISFIED",
                "core_phase_and_lli": (
                    "SATISFIED" if summary["full_joint_window"] else "UNSATISFIED"
                ),
                "same_path_code_witness": summary["same_path_code_witness"][
                    "state"
                ],
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
                "PRIMARY_SELECTION_REVIEW_ONLY"
                if summary["outcome"]
                == "GNSS_INDEPENDENT_PAIR_QUALIFICATION_PASSED"
                else "NONE_ALGO_MDO_ROLE_CLOSED"
            ),
        }
    except MaterializationError as exc:
        outcome = {
            **_base_outcome(
                "GNSS_INDEPENDENT_PAIR_ARTIFACT_MATERIALIZATION_FAILED",
                artifacts,
            ),
            "reason": str(exc),
            "clause_states": {
                "artifact_materialization_and_hash": "UNSATISFIED",
                "measurement_qualification": "NOT_EVALUATED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "NONE_MATERIALIZATION_REPAIR_ONLY",
        }
    except QualificationFailure as exc:
        outcome = {
            **_base_outcome(
                "GNSS_INDEPENDENT_PAIR_QUALIFICATION_FAILED", artifacts
            ),
            "reason": str(exc),
            "clause_states": {
                "artifact_materialization_and_hash": (
                    "SATISFIED" if len(artifacts) == len(PRODUCTS) else "UNSATISFIED"
                ),
                "measurement_qualification": "UNSATISFIED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "NONE_ALGO_MDO_ROLE_CLOSED",
        }
    except Exception as exc:
        outcome = {
            **_base_outcome("GNSS_INDEPENDENT_PAIR_DESCRIPTION_ERROR", artifacts),
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
    try:
        if summary is not None:
            coverage_path = directory / COVERAGE_NAME
            summary_path = directory / SUMMARY_NAME
            _write_jsonl(coverage_path, coverage_rows)
            _write_json(summary_path, summary)
            outcome["coverage"] = {
                "name": COVERAGE_NAME,
                "rows": len(coverage_rows),
                "sha256": canonical_sha256(coverage_path),
            }
            outcome["summary"] = {
                "name": SUMMARY_NAME,
                "sha256": canonical_sha256(summary_path),
            }
        _write_json(directory / OUTCOME_NAME, outcome)
    except Exception as exc:
        raise DescriptionError(
            f"RECEIPT_WRITE_FAILED_PHYSICAL_DECISION_RETAINED:{outcome['outcome']}"
        ) from exc
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
