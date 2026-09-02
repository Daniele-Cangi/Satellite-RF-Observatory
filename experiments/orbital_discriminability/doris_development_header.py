"""Header-only DORIS development-product qualification.

The exact compressed artifact is fully hashed before a streaming ``gzip -dc``
process is allowed to expose bytes.  The parser reads through the first
``END OF HEADER`` newline and then terminates the process.  Observation records
are neither read from the pipe nor decoded, represented, counted, or retained.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
from typing import Final, Iterable, Mapping

from experiments.live_instrument.models import strict_json_value


PARSER_VERSION: Final = "doris-rinex-header-whitelist-v1"
DEVELOPMENT_NAME: Final = "s3arx26242.001.Z"
DEVELOPMENT_BYTES: Final = 1_869_420
DEVELOPMENT_SHA256: Final = (
    "240d84518beb409dceb5cf1816f02621e9def8c9bf750c9c340cad4f6fbd7add"
)
DEVELOPMENT_URL: Final = (
    "ftp://doris.ign.fr/pub/doris/data/s3a/2026/s3arx26242.001.Z"
)
REMOTE_LAST_MODIFIED_UTC: Final = "2026-08-31T22:20:14Z"
MAX_HEADER_LINES: Final = 512
MAX_HEADER_BYTES: Final = 128_000
EXPECTED_SATELLITE_NAMES: Final = frozenset({"SENTINEL-3A", "SENTINEL-3A "})
EXPECTED_COSPAR: Final = "2016-011A"
REQUIRED_CORE_OBSERVABLES: Final = frozenset({"L1", "L2"})
REQUIRED_CODE_WITNESSES: Final = frozenset({"C1", "C2"})
SHORTLIST_PAIRS: Final = (
    ("KRWB", "LAPB"),
    ("TLSB", "WEUC"),
    ("PAUB", "RIMC"),
)


@dataclass(frozen=True, slots=True)
class ProductAuthority:
    name: str
    url: str
    bytes: int
    sha256: str
    remote_last_modified_utc: str
    role: str


DEVELOPMENT_AUTHORITY: Final = ProductAuthority(
    name=DEVELOPMENT_NAME,
    url=DEVELOPMENT_URL,
    bytes=DEVELOPMENT_BYTES,
    sha256=DEVELOPMENT_SHA256,
    remote_last_modified_utc=REMOTE_LAST_MODIFIED_UTC,
    role="DEVELOPMENT_HEADER_ONLY_NEVER_PRIMARY",
)


ALLOWED_HEADER_LABELS: Final = frozenset(
    {
        "RINEX VERSION / TYPE",
        "PGM / RUN BY / DATE",
        "COMMENT",
        "SATELLITE NAME",
        "COSPAR NUMBER",
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
        "SYS / # / OBS TYPES",
        "SIGNAL STRENGTH UNIT",
        "INTERVAL",
        "TIME OF FIRST OBS",
        "TIME OF LAST OBS",
        "RCV CLOCK OFFS APPL",
        "SYS / DCBS APPLIED",
        "SYS / SCALE FACTOR",
        "L2 / L1 DATE OFFSET",
        "LEAP SECONDS",
        "# OF STATIONS",
        "STATION REFERENCE",
        "# TIME REF STATIONS",
        "TIME REF STATION",
        "TIME REF STAT DATE",
        "# OF SATELLITES",
        "PRN / # OF OBS",
        "END OF HEADER",
    }
)


class DorisHeaderError(ValueError):
    """The artifact identity or whitelisted header boundary is invalid."""


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_artifact(path: Path, authority: ProductAuthority) -> None:
    path = Path(path)
    if path.name != authority.name or not path.is_file():
        raise DorisHeaderError("WRONG_DEVELOPMENT_PRODUCT")
    if path.stat().st_size != authority.bytes:
        raise DorisHeaderError("DEVELOPMENT_BYTE_COUNT_CHANGED")
    if file_sha256(path) != authority.sha256:
        raise DorisHeaderError("DEVELOPMENT_SHA256_CHANGED")


def resolve_gzip(executable: str | None = None) -> str:
    if executable:
        candidate = Path(executable)
        if not candidate.is_file():
            raise DorisHeaderError("GZIP_EXECUTABLE_NOT_FOUND")
        return str(candidate)
    discovered = shutil.which("gzip")
    if discovered:
        return discovered
    windows_git_gzip = Path(r"C:\Program Files\Git\usr\bin\gzip.exe")
    if windows_git_gzip.is_file():
        return str(windows_git_gzip)
    raise DorisHeaderError("GZIP_EXECUTABLE_NOT_FOUND")


def header_label(raw_line: bytes) -> str:
    body = raw_line.rstrip(b"\r\n")
    if len(body) < 60:
        raise DorisHeaderError("SHORT_HEADER_LINE")
    try:
        return body[60:80].decode("ascii", errors="strict").strip()
    except UnicodeDecodeError as error:
        raise DorisHeaderError("NON_ASCII_HEADER") from error


def read_whitelisted_header(
    path: Path, *, gzip_executable: str | None = None
) -> tuple[tuple[bytes, ...], dict[str, object]]:
    """Expose only complete header lines through the first boundary newline."""

    command = [resolve_gzip(gzip_executable), "-dc", str(Path(path))]
    process = subprocess.Popen(  # noqa: S603 - exact local executable and file
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise DorisHeaderError("GZIP_PIPE_UNAVAILABLE")
    lines: list[bytes] = []
    exposed_bytes = 0
    found = False
    try:
        while len(lines) < MAX_HEADER_LINES and exposed_bytes < MAX_HEADER_BYTES:
            raw_line = process.stdout.readline(MAX_HEADER_BYTES - exposed_bytes + 1)
            if not raw_line:
                break
            exposed_bytes += len(raw_line)
            if exposed_bytes > MAX_HEADER_BYTES:
                raise DorisHeaderError("HEADER_BYTE_LIMIT_EXCEEDED")
            if not raw_line.endswith(b"\n"):
                raise DorisHeaderError("UNTERMINATED_HEADER_LINE")
            label = header_label(raw_line)
            if label not in ALLOWED_HEADER_LABELS:
                raise DorisHeaderError(f"DESCRIPTION_ERROR_UNKNOWN_HEADER_LABEL:{label}")
            lines.append(raw_line)
            if label == "END OF HEADER":
                found = True
                break
        if not found:
            raise DorisHeaderError("END_OF_HEADER_NOT_FOUND_WITHIN_BOUND")
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
        process.stderr.close()
    raw_header = b"".join(lines)
    return tuple(lines), {
        "boundary": "FIRST_END_OF_HEADER_NEWLINE",
        "header_lines": len(lines),
        "header_decompressed_bytes_exposed": len(raw_header),
        "header_sha256": sha256(raw_header).hexdigest(),
        "post_header_bytes_read_from_pipe": 0,
        "compressed_bytes_consumed_by_subprocess": "NOT_EXPOSED",
        "subprocess_terminated_at_boundary": True,
    }


def _body(raw_line: bytes) -> tuple[str, str]:
    decoded = raw_line.rstrip(b"\r\n").decode("ascii", errors="strict").ljust(80)
    return decoded[:60], decoded[60:80].strip()


def _split_twenty(data: str, count: int) -> list[str]:
    return [data[index * 20 : (index + 1) * 20].strip() for index in range(count)]


def _fixed_floats(data: str, width: int, count: int) -> list[float]:
    try:
        return [float(data[index * width : (index + 1) * width]) for index in range(count)]
    except ValueError as error:
        raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_FIXED_FLOAT") from error


def _observation_time(data: str) -> dict[str, object]:
    try:
        year, month, day, hour, minute = [
            int(data[index * 6 : (index + 1) * 6]) for index in range(5)
        ]
        second = float(data[30:43])
    except ValueError as error:
        raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_OBSERVATION_TIME") from error
    whole_second = int(second)
    timestamp = datetime(
        year,
        month,
        day,
        hour,
        minute,
        whole_second,
        round((second - whole_second) * 1_000_000),
        tzinfo=timezone.utc,
    )
    return {
        "tag": timestamp.isoformat(),
        "declared_time_system": data[48:51].strip() or "DOR_DEFAULT_FOR_PURE_DORIS",
        "semantic": "DORIS_RECEIVER_PROPER_TIME_MONITORED_AGAINST_TAI",
    }


def _station_reference(data: str) -> dict[str, object]:
    try:
        station_type_text = data[51:52].strip()
        shift_text = data[53:56].strip()
        return {
            "internal_id": data[0:3].strip(),
            "station_code": data[5:9].strip(),
            "station_name": data[10:40].strip(),
            "domes": data[40:50].strip(),
            "station_type": int(station_type_text) if station_type_text else None,
            "frequency_shift_k": int(shift_text) if shift_text else 0,
        }
    except ValueError as error:
        raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_STATION_REFERENCE") from error


def parse_header_lines(lines: Iterable[bytes]) -> dict[str, object]:
    labels: Counter[str] = Counter()
    parsed: dict[str, object] = {}
    observables: list[str] = []
    expected_observable_count: int | None = None
    stations: list[dict[str, object]] = []
    time_reference_stations: list[dict[str, object]] = []
    scale_factors: list[dict[str, object]] = []
    for raw_line in lines:
        data, label = _body(raw_line)
        labels[label] += 1
        if label == "RINEX VERSION / TYPE":
            try:
                parsed["rinex_version"] = float(data[:9])
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_RINEX_VERSION") from error
            parsed["file_type"] = data[20:21].strip()
            parsed["satellite_system"] = data[40:41].strip()
        elif label == "PGM / RUN BY / DATE":
            parsed["producer"] = _split_twenty(data, 3)
        elif label == "SATELLITE NAME":
            parsed["satellite_name"] = data[:20].strip()
        elif label == "COSPAR NUMBER":
            parsed["cospar"] = data[:20].strip()
        elif label == "MARKER TYPE":
            parsed["marker_type"] = data[:20].strip()
        elif label == "REC # / TYPE / VERS":
            parsed["receiver"] = _split_twenty(data, 3)
        elif label == "ANT # / TYPE":
            parsed["antenna"] = _split_twenty(data, 2)
        elif label == "APPROX POSITION XYZ":
            parsed["antenna_phase_center_xyz_m"] = _fixed_floats(data, 14, 3)
        elif label == "CENTER OF MASS: XYZ":
            parsed["center_of_mass_xyz_m"] = _fixed_floats(data, 14, 3)
        elif label == "SYS / # / OBS TYPES":
            system = data[0:1].strip()
            if system:
                if system != "D":
                    raise DorisHeaderError("DESCRIPTION_ERROR_NON_DORIS_OBSERVABLE_SYSTEM")
                try:
                    expected_observable_count = int(data[3:6])
                except ValueError as error:
                    raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_OBSERVABLE_COUNT") from error
            observables.extend(data[index : index + 3].strip() for index in range(7, 60, 4))
            observables = [value for value in observables if value]
        elif label == "SIGNAL STRENGTH UNIT":
            parsed["signal_strength_unit"] = data[:20].strip()
        elif label == "INTERVAL":
            try:
                parsed["interval_s"] = float(data[:10])
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_INTERVAL") from error
        elif label == "TIME OF FIRST OBS":
            parsed["time_of_first_observation"] = _observation_time(data)
        elif label == "TIME OF LAST OBS":
            parsed["time_of_last_observation"] = _observation_time(data)
        elif label == "RCV CLOCK OFFS APPL":
            try:
                parsed["receiver_clock_offset_applied"] = int(data[:6])
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_CLOCK_POLICY") from error
        elif label == "SYS / SCALE FACTOR":
            try:
                scale_factors.append(
                    {
                        "system": data[0:1].strip(),
                        "factor": int(data[2:6]),
                        "count": int(data[8:10]) if data[8:10].strip() else 0,
                        "observables": [
                            data[index : index + 3].strip()
                            for index in range(11, 60, 4)
                            if data[index : index + 3].strip()
                        ],
                    }
                )
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_SCALE_FACTOR") from error
        elif label == "L2 / L1 DATE OFFSET":
            try:
                parsed["l2_l1_date_offset_us"] = float(data[3:17])
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_L2_L1_OFFSET") from error
        elif label == "# OF STATIONS":
            try:
                parsed["declared_station_count"] = int(data[:6])
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_STATION_COUNT") from error
        elif label == "STATION REFERENCE":
            stations.append(_station_reference(data))
        elif label == "# TIME REF STATIONS":
            try:
                parsed["declared_time_reference_station_count"] = int(data[:6])
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_TIME_REF_COUNT") from error
        elif label == "TIME REF STATION":
            try:
                time_reference_stations.append(
                    {
                        "internal_id": data[0:3].strip(),
                        "tai_bias_us": float(data[5:19]),
                        "frequency_shift_1e_minus_14": float(data[21:35]),
                    }
                )
            except ValueError as error:
                raise DorisHeaderError("DESCRIPTION_ERROR_INVALID_TIME_REFERENCE") from error
        elif label == "TIME REF STAT DATE":
            parsed["time_reference_date"] = _observation_time(data)

    if expected_observable_count is None or len(observables) != expected_observable_count:
        raise DorisHeaderError("DESCRIPTION_ERROR_OBSERVABLE_COUNT_MISMATCH")
    parsed["observable_types"] = observables
    parsed["scale_factors"] = scale_factors
    parsed["stations"] = stations
    parsed["time_reference_stations"] = time_reference_stations
    parsed["label_counts"] = dict(sorted(labels.items()))
    return parsed


def qualify_header(header: Mapping[str, object]) -> dict[str, object]:
    refusals: list[str] = []
    required_fields = (
        "rinex_version",
        "file_type",
        "satellite_system",
        "satellite_name",
        "cospar",
        "marker_type",
        "receiver",
        "antenna",
        "time_of_first_observation",
        "time_of_last_observation",
        "interval_s",
        "l2_l1_date_offset_us",
        "declared_station_count",
        "stations",
    )
    for field in required_fields:
        if field not in header:
            refusals.append(f"MISSING_REQUIRED_HEADER_FIELD:{field}")
    if float(header.get("rinex_version", 0.0)) != 3.0:
        refusals.append("UNEXPECTED_RINEX_VERSION")
    if header.get("file_type") != "O" or header.get("satellite_system") != "D":
        refusals.append("NOT_DORIS_OBSERVATION_PRODUCT")
    if header.get("satellite_name") not in EXPECTED_SATELLITE_NAMES:
        refusals.append("WRONG_SATELLITE_NAME")
    if header.get("cospar") != EXPECTED_COSPAR:
        refusals.append("WRONG_COSPAR")
    if header.get("marker_type") != "SPACEBORNE":
        refusals.append("MARKER_NOT_SPACEBORNE")
    observable_types = set(header.get("observable_types", []))
    if not REQUIRED_CORE_OBSERVABLES.issubset(observable_types):
        refusals.append("DUAL_PHASE_CORE_NOT_DECLARED")
    if not REQUIRED_CODE_WITNESSES.issubset(observable_types):
        refusals.append("DUAL_CODE_WITNESSES_NOT_DECLARED")
    stations = list(header.get("stations", []))
    if header.get("declared_station_count") != len(stations):
        refusals.append("STATION_REFERENCE_COUNT_MISMATCH")
    station_codes = {
        str(station.get("station_code"))
        for station in stations
        if isinstance(station, Mapping)
    }
    supported_pairs = [
        list(pair) for pair in SHORTLIST_PAIRS if set(pair).issubset(station_codes)
    ]
    if not supported_pairs:
        refusals.append("NO_SHORTLIST_PAIR_DECLARED_IN_DEVELOPMENT_HEADER")
    open_terms = [
        "NUMERICAL_ADC_PHASE_CENTER_EVENT_TIME_ERROR_BOUND",
        "OBSERVATION_RECORD_CONTINUITY_AND_PHASE_FLAGS",
        "SIMULTANEOUS_SHORTLIST_PAIR_WINDOW_COVERAGE",
        "EXACT_DPOD_COORDINATES_HEIGHTS_AND_PHASE_CENTERS",
        "ONE_WAY_RELATIVISTIC_AND_MEDIA_MODEL",
        "SHARED_RECEIVER_AND_CHANNEL_DIFFERENTIAL_BIAS",
    ]
    state = (
        "DORIS_DEVELOPMENT_HEADER_QUALIFIED_MEASUREMENT_UNADMITTED"
        if not refusals
        else "DORIS_DEVELOPMENT_HEADER_REJECTED"
    )
    return {
        "state": state,
        "refusals": refusals,
        "supported_shortlist_pairs": supported_pairs,
        "open_terms": open_terms,
        "measurement_admission": "NOT_EVALUATED",
    }


def parse_exact_development_header(
    path: Path,
    authority: ProductAuthority = DEVELOPMENT_AUTHORITY,
    *,
    gzip_executable: str | None = None,
) -> dict[str, object]:
    validate_artifact(path, authority)
    lines, boundary = read_whitelisted_header(
        path, gzip_executable=gzip_executable
    )
    header = parse_header_lines(lines)
    qualification = qualify_header(header)
    receipt: dict[str, object] = {
        "parser_version": PARSER_VERSION,
        "authority": asdict(authority),
        "artifact_hash_verified_before_decompression": True,
        "header_boundary": boundary,
        "header": header,
        "qualification": qualification,
        "observation_access": {
            "epoch_records_read": 0,
            "observation_records_read": 0,
            "phase_values": 0,
            "pseudorange_values": 0,
            "power_values": 0,
            "oscillator_values": 0,
            "meteorological_values": 0,
            "flags": 0,
        },
        "candidate_day_product_access": "ZERO",
        "orbital_score": "NOT_EVALUATED",
        "ephemeral_uncompressed_header_retention": "ZERO_AFTER_RECEIPT",
    }
    strict_json(receipt)
    return receipt


def strict_json(payload: Mapping[str, object]) -> str:
    return json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> int:
    path = Path(".quarantine-doris-development") / DEVELOPMENT_NAME
    print(strict_json(parse_exact_development_header(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
