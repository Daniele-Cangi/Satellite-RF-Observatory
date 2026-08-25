"""Single-use value-blind scan of the frozen G22/G30 DOY 216 locators."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import argparse
import gc
import io
import json
from pathlib import Path
import subprocess
from typing import Final, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka

from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_phase_structural_contract as contract


SCAN_VERSION: Final = "g22-g30-doy216-value-blind-structural-scan-v1"
PLAN_NAME: Final = "GNSS_PHASE_STRUCTURAL_SCAN_PLAN.md"
COVERAGE_NAME: Final = "GNSS_PHASE_STRUCTURE_COVERAGE.jsonl"
SUMMARY_NAME: Final = "GNSS_PHASE_STRUCTURE_SUMMARY.json"
OUTCOME_NAME: Final = "GNSS_PHASE_STRUCTURE_OUTCOME.json"
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 60.0
MAX_COMPRESSED_BYTES: Final = 20_000_000
SATELLITES: Final = ("G22", "G30")
OBSERVABLES: Final = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")


@dataclass(frozen=True, slots=True)
class ProductLocator:
    station: str
    name: str
    url: str


PRODUCTS: Final = (
    ProductLocator(
        "GOLD00USA",
        "GOLD00USA_R_20262160000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/216/"
        "GOLD00USA_R_20262160000_01D_30S_MO.crx.gz",
    ),
    ProductLocator(
        "NLIB00USA",
        "NLIB00USA_R_20262160000_01D_30S_MO.crx.gz",
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/216/"
        "NLIB00USA_R_20262160000_01D_30S_MO.crx.gz",
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


class StructuralRefusal(ValueError):
    """Actual header or record topology violates a frozen clause."""


class DescriptionError(ValueError):
    """Receipt/software description failed; not a structural refusal."""


class MaterializationError(RuntimeError):
    """A complete predeclared artifact could not be obtained."""


@dataclass(slots=True)
class StationScan:
    station: str
    header: dict[str, object]
    coverage: list[dict[str, object]]
    parser_issues: list[dict[str, object]]
    core_valid: dict[str, list[bool]]
    code_present: dict[tuple[str, str], list[bool]]
    epoch_present: list[bool]

    def erase(self) -> None:
        for values in self.core_valid.values():
            values[:] = [False] * len(values)
        for values in self.code_present.values():
            values[:] = [False] * len(values)
        self.epoch_present[:] = [False] * len(self.epoch_present)


def expected_epochs() -> tuple[datetime, ...]:
    result = tuple(
        contract.QUALIFICATION_RAW_START_GPS
        + timedelta(seconds=index * contract.STEP_S)
        for index in range(contract.RAW_EPOCHS)
    )
    if result[-1] != contract.QUALIFICATION_RAW_STOP_GPS:
        raise DescriptionError("FROZEN_WINDOW_GRID_CHANGED")
    return result


def strict_json(value: object, *, pretty: bool = False) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
        sort_keys=True,
    )


def canonical_file_sha256(path: Path) -> str:
    return sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def source_sha256() -> str:
    return canonical_file_sha256(Path(__file__))


def manifest() -> dict[str, object]:
    result = {
        "scan_version": SCAN_VERSION,
        "contract_manifest_sha256": contract.contract_sha256(),
        "plan_canonical_sha256": canonical_file_sha256(
            Path(__file__).resolve().parent / PLAN_NAME
        ),
        "products": [asdict(product) for product in PRODUCTS],
        "satellites": list(SATELLITES),
        "observables": list(OBSERVABLES),
        "raw_window_gps": [
            contract.contract()["roles"]["qualification"]["raw_start_gps"],
            contract.contract()["roles"]["qualification"]["raw_stop_gps"],
        ],
        "raw_epochs": contract.RAW_EPOCHS,
        "step_s": contract.STEP_S,
        "maximum_transport_attempts_per_locator": MAX_TRANSPORT_ATTEMPTS,
        "http_timeout_s": HTTP_TIMEOUT_S,
        "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
        "parser_boundary": (
            "FIELD_OCCUPANCY_LLI_EPOCH_AND_HEADER_ONLY_NO_OBSERVATION_SCALAR_"
            "CONVERSION"
        ),
        "forbidden": [
            "DOY220 URL header payload or retry",
            "phase code SNR Doppler or other observation scalar conversion",
            "geometry-free health evaluation",
            "orbital prediction or score",
            "artifact persistence",
            "post-hash retry or candidate substitution",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _format_epoch(epoch: datetime) -> str:
    return epoch.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", " GPS"
    )


def _read_header(stream: io.BytesIO) -> list[bytes]:
    rows: list[bytes] = []
    for _ in range(headers.MAX_HEADER_LINES):
        line = stream.readline()
        if not line:
            raise StructuralRefusal("HEADER_INCOMPLETE")
        rows.append(line)
        body = line.rstrip(b"\r\n")
        label = (
            body[60:80].decode("ascii", errors="strict").strip()
            if len(body) >= 60
            else ""
        )
        if label == "END OF HEADER":
            return rows
    raise StructuralRefusal("HEADER_LINE_LIMIT_EXCEEDED")


def _header_lineage(
    lines: Sequence[bytes], gps_types: Sequence[str]
) -> dict[str, str]:
    current_system: str | None = None
    classes: list[str] = []
    for raw in lines:
        body = raw.rstrip(b"\r\n")
        label = (
            body[60:80].decode("ascii", errors="strict").strip()
            if len(body) >= 60
            else ""
        )
        if label != "SYS / # / OBS TYPES":
            continue
        continuation = body[:1] == b" "
        if not continuation:
            current_system = body[:1].decode("ascii", errors="strict")
        if current_system != "G":
            continue
        values = body[7:60].decode("ascii", errors="strict").split()
        classes.extend(
            ["CONTINUATION_SUPPORTED" if continuation else "HEADER_INITIAL"]
            * len(values)
        )
    if len(classes) != len(gps_types):
        raise StructuralRefusal("GPS_HEADER_LINEAGE_COUNT_CHANGED")
    return dict(zip(gps_types, classes, strict=True))


def _validate_header(
    parsed: dict[str, object], locator: ProductLocator
) -> dict[str, object]:
    station = locator.station
    if str(parsed["marker_name"]) != station[:4]:
        raise StructuralRefusal(f"MARKER_IDENTITY_MISMATCH:{station}")
    if float(parsed["interval_s"]) != float(contract.STEP_S):
        raise StructuralRefusal(f"INTERVAL_CHANGED:{station}")
    first = headers.parse_utc(parsed["time_of_first_observation"]["utc_like_epoch"])
    last = headers.parse_utc(parsed["time_of_last_observation"]["utc_like_epoch"])
    if parsed["time_of_first_observation"]["time_system"] != "GPS":
        raise StructuralRefusal(f"FIRST_OBS_NOT_GPS:{station}")
    if parsed["time_of_last_observation"]["time_system"] != "GPS":
        raise StructuralRefusal(f"LAST_OBS_NOT_GPS:{station}")
    if (
        first > contract.QUALIFICATION_RAW_START_GPS
        or last < contract.QUALIFICATION_RAW_STOP_GPS
    ):
        raise StructuralRefusal(f"FROZEN_WINDOW_NOT_COVERED:{station}")
    expected = EXPECTED_CONFIGURATION[station]
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != expected["receiver_type"]:
        raise StructuralRefusal(f"RECEIVER_TYPE_CHANGED:{station}")
    if _normalize(receiver["version_or_radome"]) != expected["receiver_version"]:
        raise StructuralRefusal(f"RECEIVER_VERSION_CHANGED:{station}")
    if _normalize(antenna["type"]) != expected["antenna_type"]:
        raise StructuralRefusal(f"ANTENNA_TYPE_CHANGED:{station}")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise StructuralRefusal(
            f"REQUIRED_OBSERVABLE_NOT_DECLARED:{station}:{','.join(missing)}"
        )
    return {
        "station": station,
        "marker_name": parsed["marker_name"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna["type"]),
        "interval_s": parsed["interval_s"],
        "time_of_first_observation": parsed["time_of_first_observation"],
        "time_of_last_observation": parsed["time_of_last_observation"],
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "gps_observables": list(gps_types),
        "full_frozen_window_covered": True,
    }


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        fields = line.decode("ascii", errors="strict").split()
        second = float(fields[6])
        integer = int(second)
        microsecond = int(round((second - integer) * 1_000_000))
        epoch = datetime(
            int(fields[1]), int(fields[2]), int(fields[3]), int(fields[4]),
            int(fields[5]), integer, microsecond, tzinfo=timezone.utc,
        )
        return epoch, int(fields[7]), int(fields[8])
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise StructuralRefusal("RECORD_INVALID:EPOCH") from exc


def _lli(field: bytes) -> str:
    token = field[14:15]
    if token in (b"", b" ", b"0"):
        return "ZERO_OR_BLANK"
    if token.isdigit():
        return "NONZERO"
    return "INVALID"


def _field_role(observable: str) -> str:
    if observable in CORE_PHASE:
        return "CORE_PHASE"
    if observable in SAME_PATH_CODE:
        return "SAME_PATH_CODE_WITNESS"
    return "OPTIONAL_DIAGNOSTIC"


def _row(
    station: str,
    epoch: datetime,
    satellite: str,
    observable: str,
    header_index: int,
    field_count: int,
    source: str,
    header_line_class: str,
    state: str,
    lli_state: str,
) -> dict[str, object]:
    result = {
        "station": station,
        "gps_epoch": _format_epoch(epoch),
        "satellite": satellite,
        "observable": observable,
        "physical_role": _field_role(observable),
        "header_declared_index": header_index,
        "reconstructed_field_count": field_count,
        "source_line_class": source,
        "header_line_class": header_line_class,
        "continuation_class": "RINEX_3_SINGLE_LINE_RECORD",
        "state": state,
        "lli_state": lli_state,
    }
    strict_json(result)
    return result


def scan_decoded(decoded: bytearray, locator: ProductLocator) -> StationScan:
    """Scan record topology and LLI without converting observation scalars."""

    stream = io.BytesIO(decoded)
    header_lines = _read_header(stream)
    parsed = headers.parse_header_lines(header_lines)
    header_summary = _validate_header(parsed, locator)
    gps_types = tuple(parsed["observable_types"]["G"])
    indices = {
        observable: gps_types.index(observable)
        for observable in OBSERVABLES
        if observable in gps_types
    }
    lineage = _header_lineage(header_lines, gps_types)
    epochs = expected_epochs()
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    coverage: list[dict[str, object]] = []
    issues: list[dict[str, object]] = []
    epoch_present = [False] * contract.RAW_EPOCHS
    record_present = {
        (satellite, index): False
        for satellite in SATELLITES
        for index in range(contract.RAW_EPOCHS)
    }
    core_fields = {
        (satellite, observable): [False] * contract.RAW_EPOCHS
        for satellite in SATELLITES
        for observable in CORE_PHASE
    }
    code_present = {
        (satellite, observable): [False] * contract.RAW_EPOCHS
        for satellite in SATELLITES
        for observable in SAME_PATH_CODE
    }

    while True:
        line = stream.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                issues.append(
                    {"state": "RECORD_INVALID", "reason": "NON_EPOCH_SOURCE_LINE"}
                )
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        row_index = epoch_index.get(epoch)
        in_window = (
            contract.QUALIFICATION_RAW_START_GPS
            <= epoch
            <= contract.QUALIFICATION_RAW_STOP_GPS
        )
        if in_window and row_index is None:
            issues.append(
                {
                    "state": "RECORD_INVALID",
                    "reason": "OFF_GRID_EPOCH",
                    "gps_epoch": _format_epoch(epoch),
                }
            )
        if row_index is not None:
            if epoch_present[row_index]:
                issues.append(
                    {
                        "state": "RECORD_INVALID",
                        "reason": "DUPLICATE_EPOCH",
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
            epoch_present[row_index] = flag == 0
            if flag != 0:
                issues.append(
                    {
                        "state": "RECORD_INVALID",
                        "reason": f"EPOCH_FLAG_NOT_ZERO_{flag}",
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
        if flag not in (0, 1):
            for _ in range(satellite_count):
                if not stream.readline():
                    issues.append(
                        {
                            "state": "RECORD_INVALID",
                            "reason": "TRUNCATED_SPECIAL_EVENT_RECORD",
                            "gps_epoch": _format_epoch(epoch),
                        }
                    )
                    break
            continue
        for _ in range(satellite_count):
            record = stream.readline()
            if not record:
                issues.append(
                    {
                        "state": "RECORD_INVALID",
                        "reason": "TRUNCATED_SATELLITE_RECORD",
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
                break
            valid_prefix = (
                len(record) >= 3
                and record[:1].isalpha()
                and record[1:3].isdigit()
            )
            if not valid_prefix:
                continuation = record.startswith(b"   ")
                issues.append(
                    {
                        "state": (
                            "CONTINUATION_UNSUPPORTED"
                            if continuation
                            else "RECORD_INVALID"
                        ),
                        "reason": (
                            "NONSTANDARD_DATA_CONTINUATION"
                            if continuation
                            else "INVALID_SATELLITE_RECORD"
                        ),
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
                continue
            satellite = record[:3].decode("ascii", errors="strict")
            if (
                row_index is None
                or flag != 0
                or satellite not in SATELLITES
            ):
                continue
            key = (satellite, row_index)
            if record_present[key]:
                issues.append(
                    {
                        "state": "RECORD_INVALID",
                        "reason": "DUPLICATE_SATELLITE_RECORD",
                        "gps_epoch": _format_epoch(epoch),
                        "satellite": satellite,
                    }
                )
                continue
            record_present[key] = True
            payload = record[3:].rstrip(b"\r\n")
            field_count = (len(payload) + 15) // 16
            if field_count > len(gps_types):
                issues.append(
                    {
                        "state": "RECORD_INVALID",
                        "reason": "FIELD_COUNT_OVERFLOW",
                        "gps_epoch": _format_epoch(epoch),
                        "satellite": satellite,
                    }
                )
            padded = payload.ljust(field_count * 16, b" ")
            fields = tuple(
                padded[offset : offset + 16]
                for offset in range(0, len(padded), 16)
            )
            for observable in OBSERVABLES:
                header_index = indices.get(observable)
                if header_index is None:
                    state = "BLANK"
                    lli_state = "NOT_APPLICABLE"
                    source = "OPTIONAL_OBSERVABLE_NOT_DECLARED"
                    emitted_index = -1
                elif header_index >= field_count:
                    state = "TRAILING_FIELD_OMITTED"
                    lli_state = "NOT_APPLICABLE"
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    emitted_index = header_index
                else:
                    field = fields[header_index]
                    state = "PRESENT" if field[:14].strip() else "BLANK"
                    lli_state = (
                        _lli(field)
                        if observable in CORE_PHASE and state == "PRESENT"
                        else "NOT_APPLICABLE"
                    )
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    emitted_index = header_index
                coverage.append(
                    _row(
                        locator.station,
                        epoch,
                        satellite,
                        observable,
                        emitted_index,
                        field_count,
                        source,
                        lineage.get(observable, "NOT_DECLARED"),
                        state,
                        lli_state,
                    )
                )
                if observable in CORE_PHASE:
                    core_fields[(satellite, observable)][row_index] = (
                        state == "PRESENT" and lli_state == "ZERO_OR_BLANK"
                    )
                elif observable in SAME_PATH_CODE:
                    code_present[(satellite, observable)][row_index] = (
                        state == "PRESENT"
                    )

    for row_index, epoch in enumerate(epochs):
        for satellite in SATELLITES:
            if record_present[(satellite, row_index)]:
                continue
            for observable in OBSERVABLES:
                coverage.append(
                    _row(
                        locator.station,
                        epoch,
                        satellite,
                        observable,
                        indices.get(observable, -1),
                        0,
                        (
                            "SATELLITE_RECORD_ABSENT"
                            if epoch_present[row_index]
                            else "EPOCH_ABSENT_OR_NONOBSERVATION"
                        ),
                        lineage.get(observable, "NOT_DECLARED"),
                        "BLANK",
                        "NOT_APPLICABLE",
                    )
                )

    sat_order = {value: index for index, value in enumerate(SATELLITES)}
    obs_order = {value: index for index, value in enumerate(OBSERVABLES)}
    coverage.sort(
        key=lambda row: (
            row["gps_epoch"],
            sat_order[row["satellite"]],
            obs_order[row["observable"]],
        )
    )
    expected_rows = contract.RAW_EPOCHS * len(SATELLITES) * len(OBSERVABLES)
    if len(coverage) != expected_rows:
        raise DescriptionError(
            f"COVERAGE_ROW_COUNT_CHANGED:{locator.station}:{len(coverage)}"
        )
    core_valid = {
        satellite: [
            all(
                core_fields[(satellite, observable)][index]
                for observable in CORE_PHASE
            )
            for index in range(contract.RAW_EPOCHS)
        ]
        for satellite in SATELLITES
    }
    return StationScan(
        station=locator.station,
        header=header_summary,
        coverage=coverage,
        parser_issues=issues,
        core_valid=core_valid,
        code_present=code_present,
        epoch_present=epoch_present,
    )


def _segments(valid: Sequence[bool]) -> list[dict[str, object]]:
    epochs = expected_epochs()
    result: list[dict[str, object]] = []
    start: int | None = None
    for index, present in enumerate(list(valid) + [False]):
        if present and start is None:
            start = index
        elif not present and start is not None:
            stop = index - 1
            result.append(
                {
                    "start_gps": _format_epoch(epochs[start]),
                    "stop_gps": _format_epoch(epochs[stop]),
                    "epoch_count": stop - start + 1,
                    "duration_s": (stop - start) * contract.STEP_S,
                }
            )
            start = None
    return result


def evaluate(scans: Sequence[StationScan]) -> dict[str, object]:
    if tuple(scan.station for scan in scans) != tuple(
        product.station for product in PRODUCTS
    ):
        raise DescriptionError("STATION_ORDER_CHANGED")
    counts = Counter(row["state"] for scan in scans for row in scan.coverage)
    per_link: list[dict[str, object]] = []
    joint = [True] * contract.RAW_EPOCHS
    for station_scan in scans:
        for satellite in SATELLITES:
            valid = station_scan.core_valid[satellite]
            joint = [
                left and right
                for left, right in zip(joint, valid, strict=True)
            ]
            per_link.append(
                {
                    "station": station_scan.station,
                    "satellite": satellite,
                    "maximal_segments": _segments(valid),
                    "full_window": all(valid),
                }
            )
    code_rows: list[dict[str, object]] = []
    code_satisfied = True
    for station_scan in scans:
        for satellite in SATELLITES:
            for observable in SAME_PATH_CODE:
                present = station_scan.code_present[(satellite, observable)]
                count = sum(present)
                fraction = count / contract.RAW_EPOCHS
                boundaries = all(
                    present[index] for index in contract.CODE_REQUIRED_RAW_INDICES
                )
                admitted = (
                    fraction >= contract.CODE_MINIMUM_COVERAGE_FRACTION
                    and boundaries
                )
                code_satisfied = code_satisfied and admitted
                code_rows.append(
                    {
                        "station": station_scan.station,
                        "satellite": satellite,
                        "observable": observable,
                        "present_epochs": count,
                        "total_epochs": contract.RAW_EPOCHS,
                        "coverage_fraction": fraction,
                        "required_raw_indices": list(
                            contract.CODE_REQUIRED_RAW_INDICES
                        ),
                        "required_boundaries_present": boundaries,
                        "admitted": admitted,
                    }
                )
    issues = [issue for station_scan in scans for issue in station_scan.parser_issues]
    full_joint = all(joint)
    structural_pass = full_joint and code_satisfied and not issues
    outcome = (
        "GNSS_PHASE_STRUCTURE_READY_FOR_HEALTH_REVIEW"
        if structural_pass
        else "GNSS_PHASE_STRUCTURE_REJECTED"
    )
    summary = {
        "schema": "gnss-phase-structure-summary-v1",
        "outcome": outcome,
        "structural_counts": dict(sorted(counts.items())),
        "coverage_rows": sum(len(scan.coverage) for scan in scans),
        "headers": [scan.header for scan in scans],
        "parser_issues": issues,
        "per_link_core_segments": per_link,
        "joint_core_segments": _segments(joint),
        "full_joint_window": full_joint,
        "same_path_code_witness": {
            "state": "SATISFIED" if code_satisfied else "UNSATISFIED",
            "links": code_rows,
        },
        "geometry_free_phase_health": (
            "NOT_EVALUATED_BY_STRUCTURAL_ONLY_AUTHORITY"
        ),
        "measurement_admission": "NOT_EVALUATED",
        "orbital_score": "NOT_EVALUATED",
        "observation_values_parsed": 0,
        "observation_values_persisted": 0,
        "observation_artifact_bytes_persisted": 0,
    }
    strict_json(summary)
    return summary


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
                "hash_before_decompression": True,
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


def _decompress(payload: bytearray, station: str) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise StructuralRefusal(
            f"HATANAKA_DECOMPRESSION_FAILED:{station}"
        ) from exc


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        strict_json(value, pretty=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.write_text(
        "".join(strict_json(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def materialization_failure_receipt(reason: str) -> dict[str, object]:
    result = {
        "schema": "gnss-phase-structure-outcome-v1",
        "outcome": "GNSS_PHASE_ARTIFACT_MATERIALIZATION_FAILED",
        "reason": reason,
        "structure": "NOT_EVALUATED",
        "geometry_free_phase_health": "NOT_EVALUATED",
        "measurement_admission": "NOT_EVALUATED",
        "orbital_score": "NOT_EVALUATED",
        "observation_values_parsed": 0,
        "observation_values_persisted": 0,
        "observation_artifact_bytes_persisted": 0,
    }
    strict_json(result)
    return result


def run_once(output_directory: Path) -> dict[str, object]:
    directory = Path(output_directory)
    scans: list[StationScan] = []
    artifacts: list[dict[str, object]] = []
    compressed_buffers: list[bytearray] = []
    decoded_buffers: list[bytearray] = []
    try:
        for locator in PRODUCTS:
            compressed, artifact = materialize(locator)
            compressed_buffers.append(compressed)
            artifacts.append(artifact)
            decoded = _decompress(compressed, locator.station)
            decoded_buffers.append(decoded)
            scans.append(scan_decoded(decoded, locator))
        summary = evaluate(scans)
        coverage_rows = [row for scan in scans for row in scan.coverage]
        _write_jsonl(directory / COVERAGE_NAME, coverage_rows)
        coverage_sha = canonical_file_sha256(directory / COVERAGE_NAME)
        _write_json(directory / SUMMARY_NAME, summary)
        summary_sha = canonical_file_sha256(directory / SUMMARY_NAME)
        outcome = {
            "schema": "gnss-phase-structure-outcome-v1",
            "outcome": summary["outcome"],
            "source_commit": _git_commit(),
            "source_sha256": source_sha256(),
            "manifest_sha256": manifest_sha256(),
            "contract_manifest_sha256": contract.contract_sha256(),
            "artifacts": artifacts,
            "coverage": {
                "name": COVERAGE_NAME,
                "rows": len(coverage_rows),
                "sha256": coverage_sha,
            },
            "summary": {"name": SUMMARY_NAME, "sha256": summary_sha},
            "clause_states": {
                "header_and_field_topology": (
                    "SATISFIED"
                    if summary["outcome"].endswith("HEALTH_REVIEW")
                    else "UNSATISFIED"
                ),
                "lli_and_epoch_continuity": (
                    "SATISFIED" if summary["full_joint_window"] else "UNSATISFIED"
                ),
                "same_path_code_witness": summary[
                    "same_path_code_witness"
                ]["state"],
                "geometry_free_phase_health": "NOT_EVALUATED",
                "measurement_admission": "NOT_EVALUATED",
                "orbital_score": "NOT_EVALUATED",
            },
            "persistence": {
                "compressed_artifact_bytes": 0,
                "decoded_observation_bytes": 0,
                "observation_values": 0,
                "structural_receipts_only": True,
            },
            "primary_doy220_access": {
                "headers": 0,
                "payload_bytes": 0,
                "values": 0,
            },
        }
        _write_json(directory / OUTCOME_NAME, outcome)
        return outcome
    except MaterializationError as exc:
        outcome = materialization_failure_receipt(str(exc))
        _write_json(directory / OUTCOME_NAME, outcome)
        return outcome
    except StructuralRefusal as exc:
        outcome = {
            **materialization_failure_receipt(str(exc)),
            "outcome": "GNSS_PHASE_STRUCTURE_REJECTED",
            "structure": "UNSATISFIED",
            "artifacts": artifacts,
        }
        _write_json(directory / OUTCOME_NAME, outcome)
        return outcome
    except Exception as exc:
        outcome = {
            **materialization_failure_receipt(f"{type(exc).__name__}:{exc}"),
            "outcome": "GNSS_PHASE_STRUCTURE_DESCRIPTION_ERROR",
        }
        _write_json(directory / OUTCOME_NAME, outcome)
        return outcome
    finally:
        for station_scan in scans:
            station_scan.erase()
        for payload in decoded_buffers + compressed_buffers:
            payload[:] = b"\x00" * len(payload)
        gc.collect()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    if not args.execute_live:
        raise SystemExit("LIVE_AUTHORITY_REQUIRED")
    contract.verify_geometry_receipt(
        Path(__file__).resolve().parent / contract.GEOMETRY_RECEIPT_NAME
    )
    print(strict_json(run_once(args.output_directory)))


if __name__ == "__main__":
    main()
