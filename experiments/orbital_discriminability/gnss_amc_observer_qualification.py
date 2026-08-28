"""One-shot value-blind structural qualification of AMC DOY222.

This bounded executor exists only to determine whether the already selected
AMC observer can preserve the frozen G22-minus-G30 phase coordinate.  It may
inspect RINEX framing, field occupancy and the one-character LLI flags.  It
never converts or persists phase, code, SNR, Doppler or other observation
scalars.  The distinct DOY221 primary candidate has no locator or input path.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import gc
from hashlib import md5, sha256
from importlib import import_module, metadata
import io
import json
from pathlib import Path
import platform
import subprocess
from typing import Any, Final, Iterable, Mapping, Sequence
from xml.etree import ElementTree

import hatanaka

from experiments.orbital_discriminability import gnss_observation_header as headers


QUALIFICATION_VERSION: Final = "amc-g22-g30-doy222-structural-qualification-v1"
OUTCOME_NAME: Final = "AMC_OBSERVER_QUALIFICATION_OUTCOME.json"
SUMMARY_NAME: Final = "AMC_OBSERVER_QUALIFICATION_SUMMARY.json"
COVERAGE_NAME: Final = "AMC_OBSERVER_QUALIFICATION_COVERAGE.jsonl"
EXECUTOR_SEAL_NAME: Final = "AMC_OBSERVER_QUALIFICATION_EXECUTOR_SEAL.json"
AUTHORITY_MARKER_NAME: Final = "AMC_OBSERVER_QUALIFICATION_AUTHORITY_CONSUMED.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_AMC_DOY222_STRUCTURAL_QUALIFICATION_ONCE"

PARENT_REPORT_NAME: Final = "AMC_OBSERVER_REPLICATION_METADATA_REPORT.md"
PARENT_REPORT_SHA256: Final = (
    "e0c8d9496448ead1ac5bfe07cd17a0f25623853c26c70b6f4a1edb32913929fa"
)
GEOMETRY_RECEIPT_NAME: Final = "GNSS_OBSERVER_TRANSFER_GEOMETRY_RECEIPT.json"
GEOMETRY_RECEIPT_SHA256: Final = (
    "4982a32459d880a17abab9cf726ee6e8f6383e1d0b570abbf77fd07341d459d5"
)

STEP_S: Final = 30
RAW_EPOCHS: Final = 139
QUALIFICATION_RAW_START_GPS: Final = datetime(
    2026, 8, 10, 5, 37, 30, tzinfo=timezone.utc
)
HELDOUT_BOUNDARY_GPS: Final = datetime(2026, 8, 10, 6, 17, 0, tzinfo=timezone.utc)
QUALIFICATION_RAW_STOP_GPS: Final = datetime(
    2026, 8, 10, 6, 46, 30, tzinfo=timezone.utc
)
SATELLITES: Final = ("G22", "G30")
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
OPTIONAL_DIAGNOSTIC: Final = ("S1C", "S2W")
OBSERVABLES: Final = ("C1C", "L1C", "S1C", "C2W", "L2W", "S2W")
CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (0, 78, 79, 138)

MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 10_000_000
EXPECTED_COMPRESSED_BYTES: Final = 3_455_043
EXPECTED_DIRECTORY_MODIFIED: Final = "2026-08-11 03:01:26"
EXPECTED_DIRECTORY_RESPONSE_SHA256: Final = (
    "207aece33d1d72add0da59228104de955f8b241416f07e9ae55d93f3c41dd573"
)
GSSC_WEB_ROOT: Final = "https://gssc.esa.int/webftp/"
GSSC_DIRECTORY_COMPONENTS: Final = ("gnss", "data", "daily", "2026", "222")
MAX_DIRECTORY_BYTES: Final = 5_000_000

PRESENT: Final = "PRESENT"
BLANK: Final = "BLANK"
TRAILING_FIELD_OMITTED: Final = "TRAILING_FIELD_OMITTED"
CONTINUATION_SUPPORTED: Final = "CONTINUATION_SUPPORTED"
CONTINUATION_UNSUPPORTED: Final = "CONTINUATION_UNSUPPORTED"
RECORD_INVALID: Final = "RECORD_INVALID"


@dataclass(frozen=True, slots=True)
class ProductLocator:
    station: str
    name: str
    url: str


QUALIFICATION_PRODUCT: Final = ProductLocator(
    station="AMC400USA",
    name="AMC400USA_R_20262220000_01D_30S_MO.crx.gz",
    url=(
        "https://cddis.nasa.gov/archive/gnss/data/daily/2026/222/26d/"
        "AMC400USA_R_20262220000_01D_30S_MO.crx.gz"
    ),
)

EXPECTED_CONFIGURATION: Final = {
    "marker_name": "AMC4",
    "receiver_serial": "3013929",
    "receiver_type": "SEPT POLARX5TR",
    "receiver_version": "5.6.0",
    "antenna_serial": "1364-10065",
    "antenna_type": "TPSCR.G5C NONE",
}


class StructuralRefusal(ValueError):
    """The actual AMC product fails a frozen structural clause."""


class MaterializationError(RuntimeError):
    """The complete qualification artifact was not obtained and hashed."""


class TransportInterruption(RuntimeError):
    """A retryable transport interruption before the complete-file hash."""


class DescriptionError(RuntimeError):
    """Software or receipt description failed without a physical refusal."""


@dataclass(frozen=True, slots=True)
class _Record:
    fields: tuple[bytes, ...]
    field_count: int


@dataclass(slots=True)
class StationScan:
    header: dict[str, object]
    coverage: list[dict[str, object]]
    issues: list[dict[str, object]]
    core_valid: dict[str, list[bool]]
    code_present: dict[tuple[str, str], list[bool]]
    epoch_present: list[bool]

    def erase(self) -> None:
        for values in self.core_valid.values():
            values[:] = [False] * len(values)
        for values in self.code_present.values():
            values[:] = [False] * len(values)
        self.epoch_present[:] = [False] * len(self.epoch_present)


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


def _format_epoch(epoch: datetime) -> str:
    return (
        epoch.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", " GPS")
    )


def expected_epochs() -> tuple[datetime, ...]:
    result = tuple(
        QUALIFICATION_RAW_START_GPS + timedelta(seconds=index * STEP_S)
        for index in range(RAW_EPOCHS)
    )
    if result[-1] != QUALIFICATION_RAW_STOP_GPS:
        raise DescriptionError("FROZEN_WINDOW_GRID_CHANGED")
    if result[79] != HELDOUT_BOUNDARY_GPS:
        raise DescriptionError("FROZEN_HELDOUT_BOUNDARY_CHANGED")
    return result


def verify_parent_artifacts(directory: Path) -> None:
    expected = {
        PARENT_REPORT_NAME: PARENT_REPORT_SHA256,
        GEOMETRY_RECEIPT_NAME: GEOMETRY_RECEIPT_SHA256,
    }
    for name, digest in expected.items():
        path = Path(directory) / name
        if not path.is_file() or canonical_sha256(path) != digest:
            raise DescriptionError(f"FROZEN_PARENT_CHANGED:{name}")


def manifest() -> dict[str, object]:
    result = {
        "schema": "amc-observer-structural-qualification-manifest-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "source_sha256": source_sha256(),
        "parents": {
            PARENT_REPORT_NAME: PARENT_REPORT_SHA256,
            GEOMETRY_RECEIPT_NAME: GEOMETRY_RECEIPT_SHA256,
        },
        "qualification_product": asdict(QUALIFICATION_PRODUCT),
        "descriptive_directory": {
            "declared_product_bytes": EXPECTED_COMPRESSED_BYTES,
            "modified": EXPECTED_DIRECTORY_MODIFIED,
            "directory_response_sha256": EXPECTED_DIRECTORY_RESPONSE_SHA256,
            "identity_authority": False,
            "directory_md5_field_is_checksum": False,
        },
        "transport_repair": {
            "reason": "CDDIS_GET_REDIRECTED_TO_EARTHDATA_LOGIN_HTML",
            "source": "GSSC_OFFICIAL_GLOBAL_DATA_CENTER",
            "authentication": "DOCUMENTED_ANONYMOUS_WEB_SESSION",
            "client": "REQUESTS_SESSION_WITH_EXPLICIT_COOKIE_CONTINUITY",
            "web_root": GSSC_WEB_ROOT,
            "directory_components": list(GSSC_DIRECTORY_COMPONENTS),
            "same_frozen_product_name": True,
            "physical_contract_changed": False,
        },
        "window": {
            "start_gps": _format_epoch(expected_epochs()[0]),
            "heldout_boundary_gps": _format_epoch(HELDOUT_BOUNDARY_GPS),
            "stop_gps": _format_epoch(expected_epochs()[-1]),
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
        },
        "signals": {
            "satellites": list(SATELLITES),
            "core_phase": list(CORE_PHASE),
            "same_path_code": list(SAME_PATH_CODE),
            "optional_diagnostic": list(OPTIONAL_DIAGNOSTIC),
        },
        "admission": {
            "core_phase_and_zero_or_blank_lli_required_every_epoch": True,
            "code_minimum_coverage_fraction_per_link": (CODE_MINIMUM_COVERAGE_FRACTION),
            "code_required_raw_indices": list(CODE_REQUIRED_RAW_INDICES),
            "optional_diagnostic_fatal": False,
            "interpolation": False,
            "gap_bridging": False,
        },
        "transport": {
            "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
            "timeout_s": HTTP_TIMEOUT_S,
            "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
            "maximum_directory_bytes": MAX_DIRECTORY_BYTES,
            "complete_file_hash_before_decompression": True,
            "retry_after_complete_hash": False,
        },
        "parser_boundary": (
            "HEADER_FRAMING_FIELD_OCCUPANCY_EPOCH_AND_LLI_ONLY_"
            "NO_OBSERVATION_SCALAR_CONVERSION"
        ),
        "persistence": {
            "compressed_artifact_bytes": 0,
            "decoded_observation_bytes": 0,
            "observation_values": 0,
            "structural_receipts_only": True,
        },
        "forbidden": [
            "DOY221 primary locator header body payload or value access",
            "phase code SNR Doppler or other observation scalar conversion",
            "orbital prediction null comparison or score",
            "qualification artifact persistence",
            "fallback observer date signal or product",
            "post-access threshold or window change",
        ],
    }
    encoded = strict_json(result)
    if "/221/" in encoded or "2026221" in encoded:
        raise DescriptionError("PRIMARY_LOCATOR_ENTERED_QUALIFICATION_MANIFEST")
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def build_executor_seal(root: Path) -> dict[str, object]:
    """Bind the unopened qualification executor without granting live authority."""

    verify_parent_artifacts(root)
    result = {
        "schema": "amc-observer-qualification-executor-seal-v1",
        "state": "AMC_OBSERVER_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED",
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "parents": {
            PARENT_REPORT_NAME: PARENT_REPORT_SHA256,
            GEOMETRY_RECEIPT_NAME: GEOMETRY_RECEIPT_SHA256,
        },
        "qualification_product": asdict(QUALIFICATION_PRODUCT),
        "dependencies": {
            "python": platform.python_version(),
            "hatanaka": getattr(hatanaka, "__version__", "UNKNOWN"),
            "requests": _dependency_version("requests"),
        },
        "access_at_seal": {
            "network_requests": 0,
            "qualification_headers": 0,
            "qualification_payload_bytes": 0,
            "qualification_values": 0,
            "primary_doy221_locator_requests": 0,
            "primary_doy221_headers": 0,
            "primary_doy221_payload_bytes": 0,
            "primary_doy221_values": 0,
        },
        "authority": {
            "live_execution_authorized_by_seal": False,
            "expected_seal_sha256_must_be_supplied": True,
            "one_shot_marker_before_network": True,
            "retry_scope": "TRANSPORT_INTERRUPTION_BEFORE_COMPLETE_HASH_ONLY",
            "retry_after_complete_hash": False,
        },
        "stop": "SEPARATE_EXPLICIT_LIVE_QUALIFICATION_AUTHORITY_REQUIRED",
    }
    encoded = strict_json(result)
    if "/221/" in encoded or "2026221" in encoded:
        raise DescriptionError("PRIMARY_LOCATOR_ENTERED_EXECUTOR_SEAL")
    return result


def validate_executor_seal(
    root: Path, seal_path: Path, expected_seal_sha256: str
) -> dict[str, object]:
    if (
        len(expected_seal_sha256) != 64
        or not Path(seal_path).is_file()
        or canonical_sha256(seal_path) != expected_seal_sha256
    ):
        raise DescriptionError("EXECUTOR_SEAL_HASH_MISMATCH")
    try:
        seal = json.loads(
            Path(seal_path).read_text(encoding="utf-8"),
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"NONFINITE_JSON:{value}")
            ),
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise DescriptionError("EXECUTOR_SEAL_INVALID_JSON") from exc
    verify_parent_artifacts(root)
    expected = {
        "schema": "amc-observer-qualification-executor-seal-v1",
        "state": "AMC_OBSERVER_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED",
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "parents": {
            PARENT_REPORT_NAME: PARENT_REPORT_SHA256,
            GEOMETRY_RECEIPT_NAME: GEOMETRY_RECEIPT_SHA256,
        },
        "qualification_product": asdict(QUALIFICATION_PRODUCT),
        "dependencies": {
            "python": platform.python_version(),
            "hatanaka": getattr(hatanaka, "__version__", "UNKNOWN"),
            "requests": _dependency_version("requests"),
        },
    }
    for key, value in expected.items():
        if seal.get(key) != value:
            raise DescriptionError(f"EXECUTOR_SEAL_FIELD_CHANGED:{key}")
    source_commit = seal.get("source_commit")
    if not isinstance(source_commit, str) or len(source_commit) != 40:
        raise DescriptionError("EXECUTOR_SEAL_SOURCE_COMMIT_INVALID")
    access = seal.get("access_at_seal")
    if not isinstance(access, dict) or any(access.values()):
        raise DescriptionError("EXECUTOR_SEAL_ACCESS_NOT_ZERO")
    authority = seal.get("authority")
    if not isinstance(authority, dict) or authority.get(
        "live_execution_authorized_by_seal"
    ):
        raise DescriptionError("EXECUTOR_SEAL_CANNOT_GRANT_LIVE_AUTHORITY")
    encoded = strict_json(seal)
    if "/221/" in encoded or "2026221" in encoded:
        raise DescriptionError("PRIMARY_LOCATOR_ENTERED_EXECUTOR_SEAL")
    return seal


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _read_header(stream: io.BytesIO) -> tuple[bytes, ...]:
    rows: list[bytes] = []
    for _ in range(headers.MAX_HEADER_LINES):
        line = stream.readline()
        if not line:
            raise StructuralRefusal("HEADER_INCOMPLETE")
        rows.append(line)
        if headers.header_label(line) == "END OF HEADER":
            return tuple(rows)
    raise StructuralRefusal("HEADER_LINE_LIMIT_EXCEEDED")


def _header_lineage(lines: Sequence[bytes], gps_types: Sequence[str]) -> dict[str, str]:
    classes: list[str] = []
    current_system: str | None = None
    for raw in lines:
        body = raw.rstrip(b"\r\n")
        label = body[60:80].decode("ascii", errors="strict").strip()
        if label != "SYS / # / OBS TYPES":
            continue
        continuation = body[:1] == b" "
        if not continuation:
            current_system = body[:1].decode("ascii", errors="strict")
        if current_system != "G":
            continue
        values = body[7:60].decode("ascii", errors="strict").split()
        classes.extend(
            [CONTINUATION_SUPPORTED if continuation else "HEADER_INITIAL"] * len(values)
        )
    if len(classes) != len(gps_types):
        raise StructuralRefusal("GPS_HEADER_LINEAGE_COUNT_CHANGED")
    return dict(zip(gps_types, classes, strict=True))


def _validate_header(parsed: Mapping[str, object]) -> dict[str, object]:
    station = QUALIFICATION_PRODUCT.station
    if not 3.0 <= float(parsed["rinex_version"]) < 5.0:
        raise StructuralRefusal("RINEX_VERSION_NOT_EXPLICIT")
    if _normalize(parsed["marker_name"]) != EXPECTED_CONFIGURATION["marker_name"]:
        raise StructuralRefusal("MARKER_IDENTITY_MISMATCH")
    if float(parsed["interval_s"]) != float(STEP_S):
        raise StructuralRefusal("INTERVAL_CHANGED")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise StructuralRefusal("OBSERVATION_TIME_SYSTEM_NOT_GPS")
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    if first > QUALIFICATION_RAW_START_GPS or last < QUALIFICATION_RAW_STOP_GPS:
        raise StructuralRefusal("FROZEN_WINDOW_NOT_COVERED")
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    comparisons = {
        "RECEIVER_SERIAL": (
            receiver["serial"],
            EXPECTED_CONFIGURATION["receiver_serial"],
        ),
        "RECEIVER_TYPE": (
            receiver["type"],
            EXPECTED_CONFIGURATION["receiver_type"],
        ),
        "RECEIVER_VERSION": (
            receiver["version_or_radome"],
            EXPECTED_CONFIGURATION["receiver_version"],
        ),
        "ANTENNA_SERIAL": (
            antenna["serial"],
            EXPECTED_CONFIGURATION["antenna_serial"],
        ),
        "ANTENNA_TYPE": (
            antenna["type"],
            EXPECTED_CONFIGURATION["antenna_type"],
        ),
    }
    for label, (actual, expected) in comparisons.items():
        if _normalize(actual) != _normalize(expected):
            raise StructuralRefusal(f"{label}_CHANGED")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise StructuralRefusal(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{','.join(missing)}"
        )
    if list(parsed.get("scale_factor_records", ())):
        raise StructuralRefusal("UNSUPPORTED_SCALE_FACTOR_RECORD")
    if parsed["receiver_clock_offset_applied"] not in (0, 1):
        raise StructuralRefusal("CLOCK_OFFSET_SEMANTICS_UNKNOWN")
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
        "receiver_clock_offset_provenance": parsed["receiver_clock_offset_provenance"],
        "gps_observables": list(gps_types),
        "phase_shift_records": list(parsed.get("phase_shift_records", ())),
        "applied_bias_records": list(parsed.get("applied_bias_records", ())),
        "full_frozen_window_covered": True,
    }


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        fields = line.decode("ascii", errors="strict").split()
        second = float(fields[6])
        integer = int(second)
        microsecond = int(round((second - integer) * 1_000_000))
        return (
            datetime(
                int(fields[1]),
                int(fields[2]),
                int(fields[3]),
                int(fields[4]),
                int(fields[5]),
                integer,
                microsecond,
                tzinfo=timezone.utc,
            ),
            int(fields[7]),
            int(fields[8]),
        )
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise StructuralRefusal("RECORD_INVALID:EPOCH") from exc


def _read_window_records(
    stream: io.BytesIO,
) -> tuple[
    dict[tuple[datetime, str], _Record], dict[datetime, int], list[dict[str, object]]
]:
    epochs = expected_epochs()
    epoch_set = set(epochs)
    records: dict[tuple[datetime, str], _Record] = {}
    flags: dict[datetime, int] = {}
    issues: list[dict[str, object]] = []
    while True:
        line = stream.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                issues.append({"state": RECORD_INVALID, "reason": "NON_EPOCH_LINE"})
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        if epoch > epochs[-1]:
            break
        in_window = epochs[0] <= epoch <= epochs[-1]
        if in_window:
            if epoch not in epoch_set:
                issues.append(
                    {
                        "state": RECORD_INVALID,
                        "reason": "OFF_GRID_EPOCH",
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
            elif epoch in flags:
                issues.append(
                    {
                        "state": RECORD_INVALID,
                        "reason": "DUPLICATE_EPOCH",
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
            else:
                flags[epoch] = flag
        if flag not in (0, 1):
            for _ in range(satellite_count):
                if not stream.readline():
                    issues.append(
                        {
                            "state": RECORD_INVALID,
                            "reason": "TRUNCATED_SPECIAL_EVENT_RECORD",
                            "gps_epoch": _format_epoch(epoch),
                        }
                    )
                    break
            continue
        for _ in range(satellite_count):
            record_line = stream.readline()
            if not record_line:
                issues.append(
                    {
                        "state": RECORD_INVALID,
                        "reason": "TRUNCATED_SATELLITE_RECORD",
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
                break
            valid_prefix = (
                len(record_line) >= 3
                and record_line[:1].isalpha()
                and record_line[1:3].isdigit()
            )
            if not valid_prefix:
                issues.append(
                    {
                        "state": (
                            CONTINUATION_UNSUPPORTED
                            if record_line.startswith(b"   ")
                            else RECORD_INVALID
                        ),
                        "reason": (
                            "NONSTANDARD_DATA_CONTINUATION"
                            if record_line.startswith(b"   ")
                            else "INVALID_SATELLITE_RECORD"
                        ),
                        "gps_epoch": _format_epoch(epoch),
                    }
                )
                continue
            satellite = record_line[:3].decode("ascii", errors="strict")
            if not in_window or epoch not in epoch_set or satellite not in SATELLITES:
                continue
            payload = record_line[3:].rstrip(b"\r\n")
            field_count = (len(payload) + 15) // 16
            padded = payload.ljust(field_count * 16, b" ")
            fields = tuple(
                padded[offset : offset + 16] for offset in range(0, len(padded), 16)
            )
            key = (epoch, satellite)
            if key in records:
                issues.append(
                    {
                        "state": RECORD_INVALID,
                        "reason": "DUPLICATE_SATELLITE_RECORD",
                        "gps_epoch": _format_epoch(epoch),
                        "satellite": satellite,
                    }
                )
            else:
                records[key] = _Record(fields=fields, field_count=field_count)
    return records, flags, issues


def _lli(field: bytes) -> str:
    token = field[14:15]
    if token in (b"", b" ", b"0"):
        return "ZERO_OR_BLANK"
    if token.isdigit():
        return "NONZERO"
    return "INVALID"


def _physical_role(observable: str) -> str:
    if observable in CORE_PHASE:
        return "CORE_PHASE"
    if observable in SAME_PATH_CODE:
        return "SAME_PATH_CODE_WITNESS"
    return "OPTIONAL_DIAGNOSTIC"


def scan_decoded(decoded: bytearray) -> StationScan:
    """Inspect framing, occupancy and LLI without converting any scalar."""

    stream = io.BytesIO(decoded)
    header_lines = _read_header(stream)
    try:
        parsed = headers.parse_header_lines(header_lines)
    except StructuralRefusal:
        raise
    except Exception as exc:
        raise DescriptionError("HEADER_DESCRIPTION_ERROR") from exc
    header_summary = _validate_header(parsed)
    gps_types = tuple(parsed["observable_types"]["G"])
    indices = {
        observable: gps_types.index(observable)
        for observable in OBSERVABLES
        if observable in gps_types
    }
    lineage = _header_lineage(header_lines, gps_types)
    records, flags, issues = _read_window_records(stream)
    epochs = expected_epochs()
    coverage: list[dict[str, object]] = []
    core_valid = {satellite: [False] * RAW_EPOCHS for satellite in SATELLITES}
    code_present = {
        (satellite, observable): [False] * RAW_EPOCHS
        for satellite in SATELLITES
        for observable in SAME_PATH_CODE
    }
    epoch_present = [False] * RAW_EPOCHS

    for row_index, epoch in enumerate(epochs):
        epoch_flag = flags.get(epoch)
        epoch_present[row_index] = epoch_flag == 0
        if epoch_flag not in (None, 0):
            issues.append(
                {
                    "state": RECORD_INVALID,
                    "reason": f"EPOCH_FLAG_NOT_ZERO_{epoch_flag}",
                    "gps_epoch": _format_epoch(epoch),
                }
            )
        for satellite in SATELLITES:
            record = records.get((epoch, satellite))
            phase_states: list[bool] = []
            for observable in OBSERVABLES:
                header_index = indices.get(observable)
                field: bytes | None = None
                if header_index is None:
                    state = BLANK
                    source = "OPTIONAL_OBSERVABLE_NOT_DECLARED"
                    field_count = record.field_count if record else 0
                    emitted_index = -1
                elif record is None:
                    state = BLANK
                    source = (
                        "SATELLITE_RECORD_ABSENT"
                        if epoch_flag == 0
                        else "EPOCH_ABSENT_OR_NONOBSERVATION"
                    )
                    field_count = 0
                    emitted_index = header_index
                elif header_index >= record.field_count:
                    state = TRAILING_FIELD_OMITTED
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    field_count = record.field_count
                    emitted_index = header_index
                else:
                    field = record.fields[header_index]
                    state = PRESENT if field[:14].strip() else BLANK
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    field_count = record.field_count
                    emitted_index = header_index
                lli_state = "NOT_APPLICABLE"
                if observable in CORE_PHASE:
                    lli_state = (
                        _lli(field)
                        if state == PRESENT and field is not None
                        else "UNAVAILABLE"
                    )
                    phase_states.append(
                        state == PRESENT
                        and lli_state == "ZERO_OR_BLANK"
                        and epoch_flag == 0
                    )
                elif observable in SAME_PATH_CODE:
                    code_present[(satellite, observable)][row_index] = state == PRESENT
                coverage.append(
                    {
                        "station": QUALIFICATION_PRODUCT.station,
                        "gps_epoch": _format_epoch(epoch),
                        "satellite": satellite,
                        "observable": observable,
                        "physical_role": _physical_role(observable),
                        "state": state,
                        "header_declared_index": emitted_index,
                        "reconstructed_field_count": field_count,
                        "source_line_class": source,
                        "header_line_class": lineage.get(observable, "NOT_DECLARED"),
                        "continuation_class": "RINEX_3_SINGLE_LINE_RECORD",
                        "lli_state": lli_state,
                        "epoch_flag": epoch_flag,
                    }
                )
            core_valid[satellite][row_index] = all(phase_states)

    expected_rows = RAW_EPOCHS * len(SATELLITES) * len(OBSERVABLES)
    if len(coverage) != expected_rows:
        raise DescriptionError(f"COVERAGE_ROW_COUNT_CHANGED:{len(coverage)}")
    for row in coverage:
        strict_json(row)
        if "value" in row:
            raise DescriptionError("OBSERVATION_VALUE_ENTERED_COVERAGE")
    return StationScan(
        header=header_summary,
        coverage=coverage,
        issues=issues,
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
                    "duration_s": (stop - start) * STEP_S,
                }
            )
            start = None
    return result


def evaluate(scan: StationScan) -> dict[str, object]:
    counts = Counter(row["state"] for row in scan.coverage)
    per_link: list[dict[str, object]] = []
    joint = [True] * RAW_EPOCHS
    for satellite in SATELLITES:
        valid = scan.core_valid[satellite]
        joint = [left and right for left, right in zip(joint, valid, strict=True)]
        per_link.append(
            {
                "station": QUALIFICATION_PRODUCT.station,
                "satellite": satellite,
                "maximal_segments": _segments(valid),
                "full_window": all(valid),
            }
        )
    code_rows: list[dict[str, object]] = []
    code_satisfied = True
    for satellite in SATELLITES:
        for observable in SAME_PATH_CODE:
            present = scan.code_present[(satellite, observable)]
            count = sum(present)
            fraction = count / RAW_EPOCHS
            boundaries = all(present[index] for index in CODE_REQUIRED_RAW_INDICES)
            admitted = fraction >= CODE_MINIMUM_COVERAGE_FRACTION and boundaries
            code_satisfied = code_satisfied and admitted
            code_rows.append(
                {
                    "station": QUALIFICATION_PRODUCT.station,
                    "satellite": satellite,
                    "observable": observable,
                    "present_epochs": count,
                    "total_epochs": RAW_EPOCHS,
                    "coverage_fraction": fraction,
                    "required_raw_indices": list(CODE_REQUIRED_RAW_INDICES),
                    "required_boundaries_present": boundaries,
                    "admitted": admitted,
                }
            )
    full_joint = all(joint)
    passed = full_joint and code_satisfied and not scan.issues
    result = {
        "schema": "amc-observer-structural-qualification-summary-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "outcome": (
            "AMC_OBSERVER_QUALIFICATION_PASSED"
            if passed
            else "AMC_OBSERVER_QUALIFICATION_FAILED"
        ),
        "window": {
            "start_gps": _format_epoch(expected_epochs()[0]),
            "heldout_boundary_gps": _format_epoch(HELDOUT_BOUNDARY_GPS),
            "stop_gps": _format_epoch(expected_epochs()[-1]),
            "step_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
        },
        "header": scan.header,
        "structural_counts": dict(sorted(counts.items())),
        "coverage_rows": len(scan.coverage),
        "parser_issues": scan.issues,
        "per_link_core_segments": per_link,
        "joint_core_segments": _segments(joint),
        "full_joint_window": full_joint,
        "same_path_code_witness": {
            "state": "SATISFIED" if code_satisfied else "UNSATISFIED",
            "minimum_coverage_fraction": CODE_MINIMUM_COVERAGE_FRACTION,
            "links": code_rows,
        },
        "optional_diagnostic_policy": "DESCRIPTIVE_ONLY_NEVER_FATAL",
        "geometry_free_phase_health": "NOT_EVALUATED_BY_VALUE_BLIND_AUTHORITY",
        "measurement_admission": "NOT_EVALUATED",
        "orbital_score": "NOT_EVALUATED",
        "observation_values_parsed": 0,
        "observation_values_persisted": 0,
        "observation_artifact_bytes_persisted": 0,
    }
    strict_json(result)
    return result


def _requests_module() -> Any:
    """Load the live-only transport dependency outside offline collection."""

    try:
        return import_module("requests")
    except ModuleNotFoundError as exc:
        raise DescriptionError("REQUESTS_DEPENDENCY_UNAVAILABLE") from exc


def _dependency_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "UNAVAILABLE"


def _bounded_response(response: Any, maximum: int, label: str) -> bytes:
    data = response.content
    if len(data) > maximum:
        raise MaterializationError(f"{label}_SIZE_LIMIT")
    return data


def _gssc_product_metadata(directory_xml: bytes) -> dict[str, object]:
    """Extract only exact-file metadata from one GSSC directory response."""

    try:
        root = ElementTree.fromstring(directory_xml)
    except ElementTree.ParseError as exc:
        raise MaterializationError("GSSC_DIRECTORY_XML_INVALID") from exc
    nowdir = root.findtext("nowdir", default="")
    expected_directory = "/" + "/".join(GSSC_DIRECTORY_COMPONENTS)
    if nowdir != expected_directory:
        raise MaterializationError(f"GSSC_DIRECTORY_CHANGED:{nowdir}")
    matches = []
    for row in root.findall("./dirdata/rowdata"):
        if row.findtext("name", default="") == QUALIFICATION_PRODUCT.name:
            matches.append(row)
    if len(matches) != 1:
        raise MaterializationError(f"GSSC_PRODUCT_MATCH_COUNT:{len(matches)}")
    row = matches[0]
    if row.findtext("dir", default="") != "0":
        raise MaterializationError("GSSC_PRODUCT_IS_NOT_FILE")
    try:
        size = int(row.findtext("size", default="-1"))
    except ValueError as exc:
        raise MaterializationError("GSSC_PRODUCT_SIZE_INVALID") from exc
    if size != EXPECTED_COMPRESSED_BYTES:
        raise MaterializationError("GSSC_DECLARED_SIZE_CHANGED")
    modified = row.findtext("date", default="")
    if modified != EXPECTED_DIRECTORY_MODIFIED:
        raise MaterializationError("GSSC_DIRECTORY_MODIFIED_CHANGED")
    return {
        "directory": nowdir,
        "name": QUALIFICATION_PRODUCT.name,
        "bytes": size,
        "modified": modified,
        "md5": row.findtext("md5", default=""),
        "permission": row.findtext("perm", default=""),
    }


def _new_gssc_session() -> Any:
    requests = _requests_module()
    session = requests.Session()
    try:
        response = session.post(
            GSSC_WEB_ROOT + "loginok.html",
            data={
                "username": "anonymous",
                "password": "",
                "username_val": "anonymous",
                "password_val": "",
            },
            headers={"User-Agent": "Satellite-RF-Observatory/qualification"},
            timeout=HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        session.close()
        raise TransportInterruption("GSSC_LOGIN_TRANSPORT_INTERRUPTED") from exc
    _bounded_response(response, 100_000, "GSSC_LOGIN_RESPONSE")
    # WingFTP may serve loginok.html itself or advance the response body.  The
    # exact, outcome-independent session witness is the first successful
    # chdir below, not a presentation-layer JavaScript token.
    return session


def _navigate_gssc(session: Any) -> dict[str, object]:
    requests = _requests_module()
    for index, component in enumerate(GSSC_DIRECTORY_COMPONENTS):
        requested = f"/{component}" if index == 0 else component
        try:
            response = session.post(
                GSSC_WEB_ROOT + "chdir.html",
                data={"dir": requested},
                headers={"User-Agent": "Satellite-RF-Observatory/qualification"},
                timeout=HTTP_TIMEOUT_S,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise TransportInterruption(
                f"GSSC_CHDIR_TRANSPORT_INTERRUPTED:{component}"
            ) from exc
        result = _bounded_response(response, 10_000, "GSSC_CHDIR_RESPONSE")
        if result.strip() != b"Operation successful!":
            raise MaterializationError(
                f"GSSC_CHDIR_FAILED:{component}:{result[:100]!r}"
            )
    try:
        response = session.get(
            GSSC_WEB_ROOT + "dir.html",
            headers={"User-Agent": "Satellite-RF-Observatory/qualification"},
            timeout=HTTP_TIMEOUT_S,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise TransportInterruption("GSSC_DIRECTORY_TRANSPORT_INTERRUPTED") from exc
    directory_xml = _bounded_response(
        response, MAX_DIRECTORY_BYTES, "GSSC_DIRECTORY_RESPONSE"
    )
    return _gssc_product_metadata(directory_xml)


def _download_gssc(
    session: Any,
) -> tuple[bytearray, Mapping[str, object]]:
    requests = _requests_module()
    try:
        response = session.get(
            _gssc_download_url(),
            headers={"User-Agent": "Satellite-RF-Observatory/qualification"},
            timeout=HTTP_TIMEOUT_S,
            stream=True,
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise TransportInterruption("GSSC_DOWNLOAD_TRANSPORT_INTERRUPTED") from exc
    payload = bytearray()
    try:
        for block in response.iter_content(chunk_size=1024 * 1024):
            if not block:
                continue
            payload.extend(block)
            if len(payload) > MAX_COMPRESSED_BYTES:
                raise MaterializationError("COMPRESSED_SIZE_LIMIT")
    except requests.exceptions.RequestException as exc:
        payload[:] = b"\x00" * len(payload)
        raise TransportInterruption("GSSC_DOWNLOAD_STREAM_INTERRUPTED") from exc
    if payload[:2] != b"\x1f\x8b":
        raise MaterializationError("GSSC_RESPONSE_NOT_GZIP")
    return payload, response.headers


def _gssc_download_url() -> str:
    """Preserve WingFTP's bare ``download`` query flag exactly."""

    return GSSC_WEB_ROOT + "?download&filename=" + QUALIFICATION_PRODUCT.name


def materialize() -> tuple[bytearray, dict[str, object]]:
    """Fetch the complete DOY222 product in RAM and hash before decode."""

    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        payload = bytearray()
        session: Any | None = None
        try:
            session = _new_gssc_session()
            directory = _navigate_gssc(session)
            payload, response_headers = _download_gssc(session)
            if len(payload) != EXPECTED_COMPRESSED_BYTES:
                raise MaterializationError("COMPLETE_FILE_SIZE_CHANGED")
            actual_md5 = md5(payload, usedforsecurity=False).hexdigest()
            directory_md5 = str(directory["md5"]).lower()
            if len(directory_md5) == 32 and directory_md5 != actual_md5:
                raise MaterializationError("GSSC_DIRECTORY_MD5_MISMATCH")
            return payload, {
                "station": QUALIFICATION_PRODUCT.station,
                "product": QUALIFICATION_PRODUCT.name,
                "authority_url": QUALIFICATION_PRODUCT.url,
                "transport": "GSSC_DOCUMENTED_ANONYMOUS_WEB_SESSION",
                "transport_directory": directory["directory"],
                "attempts": attempt,
                "complete_file_bytes": len(payload),
                "complete_file_sha256": sha256(payload).hexdigest(),
                "complete_file_md5": actual_md5,
                "gssc_directory_md5": directory["md5"],
                "gssc_directory_md5_is_checksum": False,
                "gssc_directory_modified": directory["modified"],
                "preaccess_directory_response_sha256": (
                    EXPECTED_DIRECTORY_RESPONSE_SHA256
                ),
                "hash_before_any_decompression_or_record_scan": True,
                "descriptive_directory_was_not_identity_authority": True,
                "preaccess_declared_product_bytes": EXPECTED_COMPRESSED_BYTES,
                "response_content_length": response_headers.get("Content-Length"),
                "response_content_type": response_headers.get("Content-Type"),
            }
        except TransportInterruption as exc:
            payload[:] = b"\x00" * len(payload)
            failures.append(f"{type(exc).__name__}:{exc}")
        finally:
            if session is not None:
                session.close()
    raise MaterializationError(
        "AMC_ARTIFACT_MATERIALIZATION_FAILED:" + "|".join(failures)
    )


def decompress_in_memory(payload: bytearray) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise StructuralRefusal("HATANAKA_DECOMPRESSION_FAILED") from exc


def _base_outcome(
    outcome: str, artifact: Mapping[str, object] | None
) -> dict[str, object]:
    return {
        "schema": "amc-observer-structural-qualification-outcome-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "outcome": outcome,
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(),
        "parents": {
            PARENT_REPORT_NAME: PARENT_REPORT_SHA256,
            GEOMETRY_RECEIPT_NAME: GEOMETRY_RECEIPT_SHA256,
        },
        "dependencies": {
            "python": platform.python_version(),
            "hatanaka": getattr(hatanaka, "__version__", "UNKNOWN"),
            "requests": _dependency_version("requests"),
        },
        "artifact": dict(artifact) if artifact is not None else None,
        "persistence": {
            "compressed_rinex_bytes": 0,
            "decoded_rinex_bytes": 0,
            "observation_values": 0,
            "structural_receipts_only": True,
        },
        "primary_doy221_access": {
            "locator_requests": 0,
            "headers": 0,
            "payload_bytes": 0,
            "values": 0,
        },
        "orbital_prediction_access": 0,
        "orbital_scores_produced": 0,
        "fallback_selected": False,
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        strict_json(value, pretty=True) + "\n", encoding="utf-8", newline="\n"
    )


def _write_json_exclusive(path: Path, value: object) -> None:
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.write_text(
        "".join(strict_json(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def run_once(
    output_directory: Path,
    authority_token: str,
    expected_seal_sha256: str,
    executor_seal_path: Path,
    *,
    materializer: Any = materialize,
    decompressor: Any = decompress_in_memory,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("AMC_DOY222_QUALIFICATION_AUTHORITY_REQUIRED")
    directory = Path(output_directory)
    outcome_path = directory / OUTCOME_NAME
    marker_path = directory / AUTHORITY_MARKER_NAME
    if outcome_path.exists() or marker_path.exists():
        raise PermissionError("AMC_DOY222_QUALIFICATION_AUTHORITY_ALREADY_CONSUMED")
    root = Path(__file__).resolve().parent
    seal = validate_executor_seal(root, executor_seal_path, expected_seal_sha256)
    marker = {
        "schema": "amc-observer-qualification-authority-consumed-v1",
        "state": "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK",
        "executor_seal_sha256": expected_seal_sha256,
        "source_commit": seal["source_commit"],
        "network_requests_before_marker": 0,
        "qualification_headers_before_marker": 0,
        "qualification_payload_bytes_before_marker": 0,
        "qualification_values_before_marker": 0,
        "primary_doy221_access_before_marker": 0,
    }
    _write_json_exclusive(marker_path, marker)

    def sealed_base(
        state: str, artifact_receipt: Mapping[str, object] | None
    ) -> dict[str, object]:
        result = _base_outcome(state, artifact_receipt)
        result.update(
            {
                "executor_seal_sha256": expected_seal_sha256,
                "source_commit": seal["source_commit"],
                "source_sha256": seal["source_sha256"],
            }
        )
        return result

    compressed: bytearray | None = None
    decoded: bytearray | None = None
    scan: StationScan | None = None
    artifact: dict[str, object] | None = None
    summary: dict[str, object] | None = None
    try:
        compressed, artifact = materializer()
        if not artifact.get("complete_file_sha256"):
            raise MaterializationError("COMPLETE_HASH_REQUIRED_BEFORE_DECODE")
        decoded = decompressor(compressed)
        scan = scan_decoded(decoded)
        summary = evaluate(scan)
        outcome = {
            **sealed_base(str(summary["outcome"]), artifact),
            "clause_states": {
                "artifact_materialization_and_hash": "SATISFIED",
                "header_configuration_and_window": "SATISFIED",
                "core_phase_and_lli": (
                    "SATISFIED" if summary["full_joint_window"] else "UNSATISFIED"
                ),
                "same_path_code_witness": summary["same_path_code_witness"]["state"],
                "measurement_admission": "NOT_EVALUATED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "observation_access": {
                "qualification_products": 1,
                "qualification_headers": 1,
                "compressed_bytes_in_ram": artifact["complete_file_bytes"],
                "decoded_rinex_bytes_in_ram": len(decoded),
                "observation_values_parsed": 0,
                "observation_values_persisted": 0,
            },
            "next_authority": (
                "PROSPECTIVE_PLAN_REVIEW_ONLY"
                if summary["outcome"] == "AMC_OBSERVER_QUALIFICATION_PASSED"
                else "NONE_AMC_ROLE_CLOSED"
            ),
        }
    except MaterializationError as exc:
        outcome = {
            **sealed_base("AMC_OBSERVER_ARTIFACT_MATERIALIZATION_FAILED", artifact),
            "reason": str(exc),
            "clause_states": {
                "artifact_materialization_and_hash": "UNSATISFIED",
                "measurement_qualification": "NOT_EVALUATED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "MATERIALIZATION_REPAIR_ONLY",
        }
    except StructuralRefusal as exc:
        outcome = {
            **sealed_base("AMC_OBSERVER_QUALIFICATION_FAILED", artifact),
            "reason": str(exc),
            "clause_states": {
                "artifact_materialization_and_hash": (
                    "SATISFIED" if artifact is not None else "UNSATISFIED"
                ),
                "measurement_qualification": "UNSATISFIED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "NONE_AMC_ROLE_CLOSED",
        }
    except Exception as exc:
        outcome = {
            **sealed_base("AMC_OBSERVER_QUALIFICATION_DESCRIPTION_ERROR", artifact),
            "reason": f"{type(exc).__name__}:{exc}",
            "clause_states": {
                "description": "UNSATISFIED",
                "measurement_qualification": "NOT_EVALUATED",
                "primary_orbital_comparison": "NOT_EVALUATED",
            },
            "next_authority": "DESCRIPTION_REPAIR_ONLY",
        }
    finally:
        if scan is not None:
            scan.erase()
        for payload in (decoded, compressed):
            if payload is not None:
                payload[:] = b"\x00" * len(payload)
        gc.collect()
    strict_json(outcome)
    try:
        if summary is not None and scan is not None:
            coverage_path = directory / COVERAGE_NAME
            summary_path = directory / SUMMARY_NAME
            _write_jsonl(coverage_path, scan.coverage)
            _write_json(summary_path, summary)
            outcome["coverage"] = {
                "name": COVERAGE_NAME,
                "rows": len(scan.coverage),
                "sha256": canonical_sha256(coverage_path),
            }
            outcome["summary"] = {
                "name": SUMMARY_NAME,
                "sha256": canonical_sha256(summary_path),
            }
        _write_json(outcome_path, outcome)
    except Exception as exc:
        raise DescriptionError(
            f"RECEIPT_WRITE_FAILED_PHYSICAL_DECISION_RETAINED:{outcome['outcome']}"
        ) from exc
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-executor-seal", action="store_true")
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--executor-seal-sha256", default="")
    parser.add_argument("--executor-seal", type=Path)
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.write_executor_seal:
        _write_json(
            args.output_directory / EXECUTOR_SEAL_NAME,
            build_executor_seal(root),
        )
        print(
            strict_json(
                {
                    "outcome": ("AMC_OBSERVER_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED"),
                    "qualification_observation_access": 0,
                    "primary_doy221_observation_access": 0,
                    "live_execution_authorized": False,
                }
            )
        )
        return
    if not args.execute_live or args.executor_seal is None:
        raise SystemExit("OFFLINE_EXECUTOR_FREEZE_OR_SEPARATE_LIVE_AUTHORITY_REQUIRED")
    print(
        strict_json(
            run_once(
                args.output_directory,
                args.authority,
                args.executor_seal_sha256,
                args.executor_seal,
            )
        )
    )


if __name__ == "__main__":
    main()
