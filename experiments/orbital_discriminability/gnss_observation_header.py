"""Amplitude-blind admission of two exact GNSS observation headers.

The complete gzip artifacts are hashed before decompression.  Decompression
then stops at the first ``END OF HEADER`` record.  Bytes emitted after that
record by the final zlib call are counted and structurally discarded without
being decoded or represented.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Final, Iterable
import zlib


PARSER_VERSION: Final = "rinex-crinex-header-whitelist-v1"
EXPECTED_INTERVAL_S: Final = 30.0
FROZEN_WINDOW_START_GPS: Final = datetime(
    2026, 8, 3, 10, 1, 30, tzinfo=timezone.utc
)
FROZEN_WINDOW_STOP_GPS: Final = datetime(
    2026, 8, 3, 13, 14, 0, tzinfo=timezone.utc
)
MAX_HEADER_LINES: Final = 512
MAX_COMPRESSED_BYTES_FOR_HEADER: Final = 262_144
GPS_PHASE_PREFERENCES: Final = (
    ("L1C", "L2W"),
    ("L1W", "L2W"),
    ("L1C", "L2X"),
    ("L1X", "L2X"),
    ("L1C", "L2L"),
    ("L1C", "L2S"),
)


@dataclass(frozen=True, slots=True)
class ProductAuthority:
    station_id: str
    name: str
    url: str
    bytes: int
    sha256: str


GOLD_AUTHORITY: Final = ProductAuthority(
    station_id="GOLD00USA",
    name="GOLD00USA_R_20262150000_01D_30S_MO.crx.gz",
    url=(
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/215/"
        "GOLD00USA_R_20262150000_01D_30S_MO.crx.gz"
    ),
    bytes=2_197_353,
    sha256="815176b9eb57c9032e4007db6c4b639aeeb9225cc4b992b38d16b1b6f773e027",
)
NLIB_AUTHORITY: Final = ProductAuthority(
    station_id="NLIB00USA",
    name="NLIB00USA_R_20262150000_01D_30S_MO.crx.gz",
    url=(
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/215/"
        "NLIB00USA_R_20262150000_01D_30S_MO.crx.gz"
    ),
    bytes=2_534_492,
    sha256="cdc57171392b0f855fc7a7458e8b2ba8bd68951085e5f01cdfbdb848a7481ac5",
)
AUTHORITIES: Final = (GOLD_AUTHORITY, NLIB_AUTHORITY)


ALLOWED_HEADER_LABELS: Final = frozenset(
    {
        "RINEX VERSION / TYPE",
        "CRINEX VERS / TYPE",
        "CRINEX VERS   / TYPE",
        "CRINEX PROG / DATE",
        "PGM / RUN BY / DATE",
        "COMMENT",
        "MARKER NAME",
        "MARKER NUMBER",
        "MARKER TYPE",
        "OBSERVER / AGENCY",
        "REC # / TYPE / VERS",
        "ANT # / TYPE",
        "APPROX POSITION XYZ",
        "ANTENNA: DELTA H/E/N",
        "ANTENNA: DELTA X/Y/Z",
        "ANTENNA: PHASECENTER",
        "ANTENNA: B.SIGHT XYZ",
        "ANTENNA: ZERODIR AZI",
        "ANTENNA: ZERODIR XYZ",
        "CENTER OF MASS: XYZ",
        "DOI",
        "LICENSE OF USE",
        "STATION INFORMATION",
        "SYS / # / OBS TYPES",
        "SIGNAL STRENGTH UNIT",
        "INTERVAL",
        "TIME OF FIRST OBS",
        "TIME OF LAST OBS",
        "RCV CLOCK OFFS APPL",
        "SYS / DCBS APPLIED",
        "SYS / PCVS APPLIED",
        "SYS / SCALE FACTOR",
        "SYS / PHASE SHIFT",
        "GLONASS SLOT / FRQ #",
        "GLONASS COD/PHS/BIS",
        "LEAP SECONDS",
        "# OF SATELLITES",
        "PRN / # OF OBS",
        "END OF HEADER",
    }
)


class HeaderAdmissionError(ValueError):
    """The exact artifact or its header cannot support the frozen coordinate."""


def parse_exact_header(path: Path, authority: ProductAuthority) -> dict[str, object]:
    path = Path(path)
    validate_artifact(path, authority)
    lines, boundary = read_whitelisted_header(path)
    header = parse_header_lines(lines)
    receipt = {
        "parser_version": PARSER_VERSION,
        "authority": asdict(authority),
        "artifact_materialized": True,
        "artifact_hash_verified_before_header": True,
        "header": header,
        "header_boundary": boundary,
        "observation_access": {
            "epoch_records_decoded": 0,
            "observation_fields_decoded": 0,
            "carrier_phase_values": 0,
            "doppler_values": 0,
            "snr_values": 0,
            "lli_values": 0,
        },
    }
    strict_json(receipt)
    return receipt


def validate_artifact(path: Path, authority: ProductAuthority) -> None:
    if path.name != authority.name or not path.is_file():
        raise HeaderAdmissionError("WRONG_OBSERVATION_PRODUCT")
    if path.stat().st_size != authority.bytes:
        raise HeaderAdmissionError("OBSERVATION_BYTE_COUNT_CHANGED")
    if file_sha256(path) != authority.sha256:
        raise HeaderAdmissionError("OBSERVATION_SHA256_CHANGED")


def read_whitelisted_header(path: Path) -> tuple[tuple[bytes, ...], dict[str, int | str]]:
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    pending = bytearray()
    lines: list[bytes] = []
    compressed_consumed = 0
    discarded_after_boundary = 0
    found = False
    with Path(path).open("rb") as stream:
        while compressed_consumed < MAX_COMPRESSED_BYTES_FOR_HEADER:
            chunk = stream.read(1)
            if not chunk:
                break
            compressed_consumed += 1
            pending.extend(decompressor.decompress(chunk))
            while b"\n" in pending:
                newline = pending.index(10) + 1
                raw_line = bytes(pending[:newline])
                del pending[:newline]
                lines.append(raw_line)
                if len(lines) > MAX_HEADER_LINES:
                    raise HeaderAdmissionError("HEADER_LINE_LIMIT_EXCEEDED")
                label = header_label(raw_line)
                if label not in ALLOWED_HEADER_LABELS:
                    raise HeaderAdmissionError(f"UNRECOGNIZED_HEADER_LABEL:{label}")
                if label == "END OF HEADER":
                    discarded_after_boundary = len(pending)
                    pending.clear()
                    found = True
                    break
            if found:
                break
    if not found:
        raise HeaderAdmissionError("END_OF_HEADER_NOT_FOUND_WITHIN_BOUND")
    raw_header = b"".join(lines)
    return tuple(lines), {
        "header_lines": len(lines),
        "header_decompressed_bytes": len(raw_header),
        "header_sha256": sha256(raw_header).hexdigest(),
        "compressed_bytes_consumed_to_boundary": compressed_consumed,
        "post_header_decompressed_bytes_discarded": discarded_after_boundary,
        "boundary": "FIRST_END_OF_HEADER_NEWLINE",
    }


def header_label(raw_line: bytes) -> str:
    body = raw_line.rstrip(b"\r\n")
    if len(body) < 60:
        raise HeaderAdmissionError("SHORT_HEADER_LINE")
    try:
        return body[60:80].decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as exc:
        raise HeaderAdmissionError("NON_ASCII_HEADER") from exc


def parse_header_lines(lines: Iterable[bytes]) -> dict[str, object]:
    labels: Counter[str] = Counter()
    observable_types: dict[str, list[str]] = {}
    observable_counts: dict[str, int] = {}
    scale_factors: list[str] = []
    phase_shifts: list[str] = []
    applied_biases: list[str] = []
    parsed: dict[str, object] = {}
    current_system: str | None = None
    for raw in lines:
        body = raw.rstrip(b"\r\n").decode("ascii", errors="strict").ljust(80)
        label = body[60:80].strip()
        labels[label] += 1
        data = body[:60]
        if label == "RINEX VERSION / TYPE":
            parsed["rinex_version"] = float(data[:9])
            parsed["file_type"] = data[20:21].strip()
            parsed["satellite_system"] = data[40:41].strip()
        elif label in {"CRINEX VERS / TYPE", "CRINEX VERS   / TYPE"}:
            parsed["crinex_version"] = data[:20].strip()
            parsed["crinex_type"] = data[20:40].strip()
        elif label == "MARKER NAME":
            parsed["marker_name"] = data.strip()
        elif label == "MARKER NUMBER":
            parsed["marker_number"] = data.strip()
        elif label == "MARKER TYPE":
            parsed["marker_type"] = data.strip()
        elif label == "REC # / TYPE / VERS":
            parsed["receiver"] = split_twenty(data)
        elif label == "ANT # / TYPE":
            parsed["antenna"] = split_twenty(data)
        elif label == "APPROX POSITION XYZ":
            parsed["approx_position_xyz_m"] = floats(data, 3)
        elif label == "ANTENNA: DELTA H/E/N":
            parsed["antenna_delta_hen_m"] = floats(data, 3)
        elif label == "INTERVAL":
            parsed["interval_s"] = float(data.split()[0])
        elif label == "TIME OF FIRST OBS":
            parsed["time_of_first_observation"] = parse_observation_time(data)
        elif label == "TIME OF LAST OBS":
            parsed["time_of_last_observation"] = parse_observation_time(data)
        elif label == "RCV CLOCK OFFS APPL":
            parsed["receiver_clock_offset_applied"] = int(data[:6])
            parsed["receiver_clock_offset_provenance"] = "EXPLICIT_HEADER_RECORD"
        elif label == "SIGNAL STRENGTH UNIT":
            parsed["signal_strength_unit"] = data.strip()
        elif label == "SYS / # / OBS TYPES":
            system = data[0:1].strip() or current_system
            if system is None:
                raise HeaderAdmissionError("OBS_TYPES_CONTINUATION_WITHOUT_SYSTEM")
            current_system = system
            declared = data[3:6].strip()
            if declared:
                observable_counts[system] = int(declared)
            observable_types.setdefault(system, []).extend(data[7:60].split())
        elif label == "SYS / SCALE FACTOR":
            scale_factors.append(data.rstrip())
        elif label == "SYS / PHASE SHIFT":
            phase_shifts.append(data.rstrip())
        elif label in {"SYS / DCBS APPLIED", "SYS / PCVS APPLIED"}:
            applied_biases.append(f"{label}:{data.rstrip()}")

    if "receiver_clock_offset_applied" not in parsed:
        parsed["receiver_clock_offset_applied"] = 0
        parsed["receiver_clock_offset_provenance"] = (
            "RINEX_3_04_TABLE_A2_STANDARD_DEFAULT_NO"
        )
        parsed["receiver_clock_offset_semantics_source"] = (
            "https://files.igs.org/pub/data/format/rinex304.pdf"
        )

    required = {
        "rinex_version",
        "file_type",
        "marker_name",
        "receiver",
        "antenna",
        "approx_position_xyz_m",
        "interval_s",
        "time_of_first_observation",
        "time_of_last_observation",
        "receiver_clock_offset_applied",
    }
    missing = sorted(required - parsed.keys())
    if missing:
        raise HeaderAdmissionError(f"MISSING_REQUIRED_HEADER_FIELDS:{','.join(missing)}")
    if parsed["file_type"] != "O":
        raise HeaderAdmissionError("NOT_AN_OBSERVATION_FILE")
    for system, expected in observable_counts.items():
        actual = len(observable_types.get(system, []))
        if actual != expected:
            raise HeaderAdmissionError(
                f"OBSERVABLE_COUNT_MISMATCH:{system}:{expected}:{actual}"
            )
    parsed["observable_types"] = {
        system: values for system, values in sorted(observable_types.items())
    }
    parsed["scale_factor_records"] = scale_factors
    parsed["phase_shift_records"] = phase_shifts
    parsed["applied_bias_records"] = applied_biases
    parsed["labels_seen"] = dict(sorted(labels.items()))
    return parsed


def admit_pair(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    receipts = (left, right)
    refusals = []
    for receipt in receipts:
        authority = receipt["authority"]
        header = receipt["header"]
        station = authority["station_id"]
        if str(header["marker_name"]) != station[:4]:
            refusals.append(f"MARKER_IDENTITY_MISMATCH:{station}")
        if header["interval_s"] != EXPECTED_INTERVAL_S:
            refusals.append(f"INTERVAL_NOT_30S:{station}")
        first = parse_utc(header["time_of_first_observation"]["utc_like_epoch"])
        last = parse_utc(header["time_of_last_observation"]["utc_like_epoch"])
        if first > last:
            refusals.append(f"OBSERVATION_TIME_ORDER_INVALID:{station}")
        if first > FROZEN_WINDOW_START_GPS or last < FROZEN_WINDOW_STOP_GPS:
            refusals.append(f"FROZEN_WINDOW_NOT_COVERED:{station}")
        if header["time_of_first_observation"]["time_system"] != "GPS":
            refusals.append(f"TIME_SYSTEM_NOT_GPS:{station}")
        if header["time_of_last_observation"]["time_system"] != "GPS":
            refusals.append(f"LAST_OBS_TIME_SYSTEM_NOT_GPS:{station}")
        if header["receiver_clock_offset_applied"] not in (0, 1):
            refusals.append(f"CLOCK_OFFSET_SEMANTICS_UNKNOWN:{station}")

    left_gps = set(left["header"]["observable_types"].get("G", []))
    right_gps = set(right["header"]["observable_types"].get("G", []))
    common = left_gps & right_gps
    chosen = None
    for l1_phase, l2_phase in GPS_PHASE_PREFERENCES:
        required = signal_family(l1_phase) | signal_family(l2_phase)
        if required <= common:
            signal_strength = sorted(
                item for item in (f"S{l1_phase[1:]}", f"S{l2_phase[1:]}")
                if item in common
            )
            chosen = {
                "l1_phase": l1_phase,
                "l2_phase": l2_phase,
                "core_phase_observables": [l1_phase, l2_phase],
                "cycle_slip_continuity_witnesses": [
                    f"LLI_ON_{l1_phase}",
                    f"LLI_ON_{l2_phase}",
                    "EPOCH_CONTINUITY",
                ],
                "same_path_code_witnesses": sorted(
                    item for item in required if item.startswith("C")
                ),
                "optional_signal_strength_diagnostics": signal_strength,
            }
            break
    if chosen is None:
        refusals.append("NO_COMMON_L1_L2_PHASE_AND_CODE_FAMILY")
    state = "PAIR_HEADER_ADMITTED" if not refusals else "PAIR_HEADER_REJECTED"
    result = {
        "state": state,
        "refusals": refusals,
        "chosen_signal_family": chosen,
        "common_gps_observable_types": sorted(common),
        "measurement_values_accessed": 0,
    }
    strict_json(result)
    return result


def signal_family(phase_code: str) -> set[str]:
    suffix = phase_code[1:]
    return {f"C{suffix}", phase_code}


def split_twenty(data: str) -> dict[str, str]:
    return {
        "serial": data[:20].strip(),
        "type": data[20:40].strip(),
        "version_or_radome": data[40:60].strip(),
    }


def floats(data: str, count: int) -> list[float]:
    values = [float(value) for value in data.split()]
    if len(values) != count:
        raise HeaderAdmissionError("NUMERIC_HEADER_FIELD_COUNT_MISMATCH")
    return values


def parse_observation_time(data: str) -> dict[str, str]:
    values = data[:43].split()
    if len(values) != 6:
        raise HeaderAdmissionError("INVALID_OBSERVATION_TIME")
    year, month, day, hour, minute = (int(value) for value in values[:5])
    second = float(values[5])
    epoch = datetime(year, month, day, hour, minute, tzinfo=timezone.utc) + timedelta(
        seconds=second
    )
    return {
        "utc_like_epoch": epoch.isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "time_system": data[48:51].strip(),
        "semantics": "RINEX_DECLARED_TIME_SYSTEM_NOT_YET_CONVERTED_TO_UTC",
    }


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(value, allow_nan=False, ensure_ascii=True, sort_keys=True)


def parser_manifest() -> dict[str, object]:
    return {
        "parser_version": PARSER_VERSION,
        "authorities": [asdict(authority) for authority in AUTHORITIES],
        "allowed_header_labels": sorted(ALLOWED_HEADER_LABELS),
        "expected_interval_s": EXPECTED_INTERVAL_S,
        "frozen_window_start_gps": FROZEN_WINDOW_START_GPS.isoformat(),
        "frozen_window_stop_gps": FROZEN_WINDOW_STOP_GPS.isoformat(),
        "gps_phase_preferences": GPS_PHASE_PREFERENCES,
        "maximum_header_lines": MAX_HEADER_LINES,
        "maximum_compressed_bytes_for_header": MAX_COMPRESSED_BYTES_FOR_HEADER,
        "boundary": "FIRST_END_OF_HEADER_NEWLINE",
        "post_boundary_policy": "COUNT_AND_STRUCTURALLY_DISCARD_WITHOUT_DECODE",
        "forbidden": [
            "epoch record decoding",
            "observation field decoding",
            "carrier phase, code, Doppler, SNR or LLI representation",
            "signal-family selection outside the frozen preference order",
        ],
    }


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("ascii")).hexdigest()
