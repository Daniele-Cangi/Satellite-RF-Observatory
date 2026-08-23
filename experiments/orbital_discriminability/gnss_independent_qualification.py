"""One bounded, value-ephemeral GNSS structural qualification.

The fixed 2026-08-02 GOLD/NLIB products are a qualification pair only.  The
module emits field topology and deterministic segment summaries; raw
observations and decoded RINEX never leave RAM.  No orbit or null model is
accepted by this module.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
from typing import Final, Iterable, Sequence
from urllib.request import urlopen

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_structural_qualification as structural


QUALIFICATION_VERSION: Final = "gnss-independent-qualification-doy214-v1"
PLAN_NAME: Final = "GNSS_INDEPENDENT_QUALIFICATION_PLAN.md"
PLAN_SHA256: Final = "5a084367f58e3715565e71bb2f6dc88032e4c5e5013a82f6d71faa2d9fbbf61c"
OUTCOME_NAME: Final = "GNSS_INDEPENDENT_QUALIFICATION_OUTCOME.json"
COVERAGE_NAME: Final = "GNSS_INDEPENDENT_QUALIFICATION_COVERAGE.jsonl"
SUMMARY_NAME: Final = "GNSS_INDEPENDENT_QUALIFICATION_SUMMARY.json"

GOLD_PRODUCT: Final = headers.ProductAuthority(
    station_id="GOLD00USA",
    name="GOLD00USA_R_20262140000_01D_30S_MO.crx.gz",
    url=(
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/"
        "GOLD00USA_R_20262140000_01D_30S_MO.crx.gz"
    ),
    bytes=2_175_246,
    sha256="0da86ed0b7fd2b4436d8e8fa5a4b2abeeadd8590af83544be9e98d1911517fe6",
)
NLIB_PRODUCT: Final = headers.ProductAuthority(
    station_id="NLIB00USA",
    name="NLIB00USA_R_20262140000_01D_30S_MO.crx.gz",
    url=(
        "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/"
        "NLIB00USA_R_20262140000_01D_30S_MO.crx.gz"
    ),
    bytes=2_485_603,
    sha256="3a0313973e040adf619a0fb6e1e12415aa8c790d65606bffc1fe84e1545c10fc",
)
PRODUCTS: Final = (GOLD_PRODUCT, NLIB_PRODUCT)

FROZEN_CONFIGURATION: Final = {
    "GOLD00USA": {
        "receiver": {
            "serial": "01538",
            "type": "JAVAD TRE_G3TH DELTA",
            "version_or_radome": "4.2.03",
        },
        "antenna": {
            "serial": "401-B",
            "type": "AOAD/M_T        NONE",
            "version_or_radome": "",
        },
        "site_log": "https://files.igs.org/pub/station/log/gold00usa_20250130.log",
    },
    "NLIB00USA": {
        "receiver": {
            "serial": "3013995",
            "type": "SEPT POLARX5TR",
            "version_or_radome": "5.7.0",
        },
        "antenna": {
            "serial": "00841",
            "type": "JAVRINGANT_DM   SCIS",
            "version_or_radome": "",
        },
        "site_log": "https://files.igs.org/pub/station/log/nlib00usa_20260310.log",
    },
}

WINDOW_START_GPS: Final = datetime(2026, 8, 2, 10, 5, 30, tzinfo=timezone.utc)
WINDOW_STOP_GPS: Final = datetime(2026, 8, 2, 13, 18, 0, tzinfo=timezone.utc)
STEP_S: Final = 30.0
RAW_EPOCHS: Final = 386
FEATURE_EPOCHS: Final = 384
CALIBRATION_FEATURE_EPOCHS: Final = 77
HELDOUT_FEATURE_EPOCHS: Final = 307
SATELLITES: Final = ("G11", "G21")

CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
OPTIONAL_DIAGNOSTIC: Final = ("S1C", "S2W")
RELEVANT_OBSERVABLES: Final = (
    "C1C",
    "L1C",
    "S1C",
    "C2W",
    "L2W",
    "S2W",
)
PHYSICAL_ROLES: Final = {
    "L1C": "CORE",
    "L2W": "CORE",
    "C1C": "SAME_PATH_CODE_WITNESS",
    "C2W": "SAME_PATH_CODE_WITNESS",
    "S1C": "OPTIONAL_DIAGNOSTIC",
    "S2W": "OPTIONAL_DIAGNOSTIC",
}

PRESENT: Final = "PRESENT"
BLANK: Final = "BLANK"
TRAILING_FIELD_OMITTED: Final = "TRAILING_FIELD_OMITTED"
CONTINUATION_SUPPORTED: Final = "CONTINUATION_SUPPORTED"
CONTINUATION_UNSUPPORTED: Final = "CONTINUATION_UNSUPPORTED"
RECORD_INVALID: Final = "RECORD_INVALID"
FIELD_STATES: Final = (
    PRESENT,
    BLANK,
    TRAILING_FIELD_OMITTED,
    CONTINUATION_SUPPORTED,
    CONTINUATION_UNSUPPORTED,
    RECORD_INVALID,
)

SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
GPS_L1_HZ: Final = 1_575_420_000.0
GPS_L2_HZ: Final = 1_227_600_000.0
LAMBDA_L1_M: Final = SPEED_OF_LIGHT_M_S / GPS_L1_HZ
LAMBDA_L2_M: Final = SPEED_OF_LIGHT_M_S / GPS_L2_HZ
GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M: Final = 0.5 * min(
    LAMBDA_L1_M, LAMBDA_L2_M
)

CODE_MINIMUM_COVERAGE_FRACTION: Final = 0.95
CODE_REQUIRED_RAW_INDICES: Final = (1, 77, 78, 384)
ALLOWED_OUTCOMES: Final = (
    "GNSS_INDEPENDENT_QUALIFICATION_PASSED",
    "GNSS_INDEPENDENT_QUALIFICATION_FAILED",
)

_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


class QualificationError(ValueError):
    """A frozen qualification clause failed."""


@dataclass(slots=True)
class StationScan:
    station: str
    coverage: list[dict[str, object]]
    core_valid: np.ndarray
    code_present: np.ndarray
    phase_cycles: np.ndarray
    epoch_records_present: np.ndarray
    header_summary: dict[str, object]

    def erase(self) -> None:
        self.core_valid.fill(False)
        self.code_present.fill(False)
        self.phase_cycles.fill(0.0)
        self.epoch_records_present.fill(False)


@dataclass(frozen=True, slots=True)
class _Record:
    satellite: str
    fields: tuple[bytes, ...]
    field_count: int
    source_line_class: str
    continuation_state: str


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
            raise QualificationError("MULTIPLE_LINE_PUSHBACK")
        self._pending = line


def expected_epochs() -> tuple[datetime, ...]:
    epochs = tuple(
        WINDOW_START_GPS + timedelta(seconds=STEP_S * index)
        for index in range(RAW_EPOCHS)
    )
    if epochs[-1] != WINDOW_STOP_GPS:
        raise RuntimeError("FROZEN_WINDOW_GRID_CHANGED")
    return epochs


def field_role(observable: str) -> str:
    return PHYSICAL_ROLES[observable]


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_text_sha256(path: Path) -> str:
    """Hash frozen text independently of the checkout newline convention."""
    payload = Path(path).read_bytes().replace(b"\r\n", b"\n")
    return sha256(payload).hexdigest()


def decode_exact_in_memory(
    compressed: bytearray, authority: headers.ProductAuthority
) -> bytearray:
    if len(compressed) != authority.bytes:
        raise QualificationError(
            f"ARTIFACT_BYTE_COUNT_CHANGED:{authority.station_id}"
        )
    if sha256(compressed).hexdigest() != authority.sha256:
        raise QualificationError(f"ARTIFACT_SHA256_CHANGED:{authority.station_id}")
    try:
        plain = hatanaka.decompress(bytes(compressed), strict=True)
    except Exception as exc:  # pragma: no cover - codec diagnostics are external
        raise QualificationError(
            f"HATANAKA_DECODING_FAILED:{authority.station_id}"
        ) from exc
    return bytearray(plain)


def scan_plain_station(
    decoded: bytearray,
    authority: headers.ProductAuthority,
) -> StationScan:
    reader = _LineReader(decoded)
    header_lines = _read_header_lines(reader)
    parsed_header = headers.parse_header_lines(header_lines)
    _validate_header(parsed_header, authority)
    gps_types = tuple(parsed_header["observable_types"].get("G", ()))
    if any(observable not in gps_types for observable in CORE_PHASE + SAME_PATH_CODE):
        raise QualificationError(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{authority.station_id}"
        )
    indices = {
        observable: (gps_types.index(observable) if observable in gps_types else None)
        for observable in RELEVANT_OBSERVABLES
    }
    line_classes = _gps_observable_line_classes(header_lines, gps_types)
    records, epoch_flags = _read_window_records(reader, gps_types)
    epochs = expected_epochs()
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    satellite_index = {satellite: index for index, satellite in enumerate(SATELLITES)}
    observable_index = {
        observable: index for index, observable in enumerate(RELEVANT_OBSERVABLES)
    }
    coverage: list[dict[str, object]] = []
    core_valid = np.ones((RAW_EPOCHS, len(SATELLITES)), dtype=np.bool_)
    code_present = np.zeros(
        (RAW_EPOCHS, len(SATELLITES), len(SAME_PATH_CODE)), dtype=np.bool_
    )
    phase_cycles = np.full(
        (RAW_EPOCHS, len(SATELLITES), len(CORE_PHASE)), np.nan, dtype=np.float64
    )
    epoch_records_present = np.zeros(
        (RAW_EPOCHS, len(SATELLITES)), dtype=np.bool_
    )
    for epoch in epochs:
        row = epoch_index[epoch]
        for satellite in SATELLITES:
            sat = satellite_index[satellite]
            record = records.get((epoch, satellite))
            epoch_records_present[row, sat] = record is not None
            for observable in RELEVANT_OBSERVABLES:
                obs = observable_index[observable]
                header_index = indices[observable]
                lli_state = "NOT_APPLICABLE"
                if header_index is None:
                    state = BLANK
                    field = None
                    field_count = record.field_count if record is not None else 0
                    source = "OBSERVABLE_NOT_DECLARED_OPTIONAL"
                    continuation = "NOT_APPLICABLE"
                elif record is None:
                    state = BLANK
                    field = None
                    field_count = 0
                    source = "SATELLITE_RECORD_ABSENT"
                    continuation = "NOT_APPLICABLE"
                elif record.continuation_state == CONTINUATION_UNSUPPORTED:
                    state = CONTINUATION_UNSUPPORTED
                    field = None
                    field_count = record.field_count
                    source = record.source_line_class
                    continuation = record.continuation_state
                elif header_index >= record.field_count:
                    state = TRAILING_FIELD_OMITTED
                    field = None
                    field_count = record.field_count
                    source = record.source_line_class
                    continuation = record.continuation_state
                else:
                    field = record.fields[header_index]
                    field_count = record.field_count
                    source = record.source_line_class
                    continuation = (
                        CONTINUATION_SUPPORTED
                        if line_classes.get(observable) == "HEADER_CONTINUATION"
                        else "NOT_REQUIRED"
                    )
                    state = BLANK if not field[:14].strip() else PRESENT
                if observable in CORE_PHASE:
                    phase = CORE_PHASE.index(observable)
                    if state == PRESENT and field is not None:
                        lli_state = _parse_lli_state(field)
                        if lli_state == "ZERO_OR_BLANK":
                            phase_cycles[row, sat, phase] = _parse_phase(field)
                        else:
                            core_valid[row, sat] = False
                    else:
                        lli_state = "UNAVAILABLE"
                        core_valid[row, sat] = False
                    if epoch_flags.get(epoch, 0) != 0:
                        core_valid[row, sat] = False
                if observable in SAME_PATH_CODE:
                    code = SAME_PATH_CODE.index(observable)
                    code_present[row, sat, code] = state == PRESENT
                coverage.append(
                    {
                        "station": authority.station_id,
                        "gps_epoch": structural.format_gps_epoch(epoch),
                        "satellite": satellite,
                        "observable": observable,
                        "physical_role": field_role(observable),
                        "state": state,
                        "header_declared_index": header_index,
                        "reconstructed_field_count": field_count,
                        "source_line_class": source,
                        "continuation_state": continuation,
                        "lli_state": lli_state,
                        "epoch_flag": epoch_flags.get(epoch),
                    }
                )
    core_valid &= np.all(np.isfinite(phase_cycles), axis=2)
    return StationScan(
        station=authority.station_id,
        coverage=coverage,
        core_valid=core_valid,
        code_present=code_present,
        phase_cycles=phase_cycles,
        epoch_records_present=epoch_records_present,
        header_summary={
            "receiver": parsed_header["receiver"],
            "antenna": parsed_header["antenna"],
            "interval_s": parsed_header["interval_s"],
            "time_of_first_observation": parsed_header["time_of_first_observation"],
            "time_of_last_observation": parsed_header["time_of_last_observation"],
            "receiver_clock_offset_applied": parsed_header[
                "receiver_clock_offset_applied"
            ],
            "signal_strength_unit": parsed_header.get(
                "signal_strength_unit", "UNKNOWN_NOT_DECLARED"
            ),
            "gps_observable_types": list(gps_types),
        },
    )


def evaluate_scans(scans: Sequence[StationScan]) -> dict[str, object]:
    if tuple(scan.station for scan in scans) != tuple(
        product.station_id for product in PRODUCTS
    ):
        raise QualificationError("STATION_ORDER_OR_IDENTITY_CHANGED")
    epochs = expected_epochs()
    per_link_segments: list[dict[str, object]] = []
    joint_valid = np.ones(RAW_EPOCHS, dtype=np.bool_)
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            valid = scan.core_valid[:, sat_index]
            joint_valid &= valid
            per_link_segments.append(
                {
                    "station": scan.station,
                    "satellite": satellite,
                    "segments": _segment_receipts(valid, epochs),
                }
            )
    joint_segments = _segment_receipts(joint_valid, epochs)
    full_joint_window = (
        len(joint_segments) == 1
        and joint_segments[0]["epoch_count"] == RAW_EPOCHS
        and joint_segments[0]["start_gps"] == structural.format_gps_epoch(epochs[0])
        and joint_segments[0]["stop_gps"] == structural.format_gps_epoch(epochs[-1])
    )
    geometry_free = _geometry_free_receipt(scans)
    code_witness = _code_witness_receipt(scans)
    structural_counts = _structural_counts(scans)
    invalid_states = structural_counts.get(CONTINUATION_UNSUPPORTED, 0) + structural_counts.get(
        RECORD_INVALID, 0
    )
    passed = (
        full_joint_window
        and geometry_free["state"] == "SATISFIED"
        and code_witness["state"] == "SATISFIED"
        and invalid_states == 0
    )
    outcome = ALLOWED_OUTCOMES[0] if passed else ALLOWED_OUTCOMES[1]
    summary = {
        "schema": "gnss-independent-qualification-summary-v1",
        "qualification_version": QUALIFICATION_VERSION,
        "window": {
            "start_gps": structural.format_gps_epoch(epochs[0]),
            "stop_gps": structural.format_gps_epoch(epochs[-1]),
            "interval_s": STEP_S,
            "raw_epochs": RAW_EPOCHS,
            "feature_epochs": FEATURE_EPOCHS,
            "calibration_feature_epochs": CALIBRATION_FEATURE_EPOCHS,
            "heldout_feature_epochs": HELDOUT_FEATURE_EPOCHS,
        },
        "field_roles": {
            "core": list(CORE_PHASE),
            "cycle_slip_continuity": [
                "LLI_ON_L1C",
                "LLI_ON_L2W",
                "GEOMETRY_FREE_PHASE_CONTINUITY",
            ],
            "same_path_code_witness": list(SAME_PATH_CODE),
            "optional_diagnostic": list(OPTIONAL_DIAGNOSTIC),
        },
        "structural_counts": structural_counts,
        "per_link_maximal_segments": per_link_segments,
        "joint_maximal_segments": joint_segments,
        "full_joint_window": full_joint_window,
        "geometry_free_phase_continuity": geometry_free,
        "same_path_code_witness": code_witness,
        "optional_diagnostic_policy": (
            "DESCRIPTIVE_ONLY_NEVER_FATAL_NO_MAGNITUDE_RULE"
        ),
        "segment_selection": (
            "FULL_PREDECLARED_WINDOW_OR_FAIL_NO_ALTERNATIVE_SEGMENT_SELECTION"
        ),
        "observation_values_persisted": 0,
        "orbital_scores_produced": 0,
        "outcome": outcome,
    }
    strict_json(summary)
    return summary


def run_once(output_directory: Path) -> dict[str, object]:
    output_directory = Path(output_directory)
    plan_path = output_directory / PLAN_NAME
    if not plan_path.is_file():
        raise QualificationError("FROZEN_PLAN_MISSING")
    if canonical_text_sha256(plan_path) != PLAN_SHA256:
        raise QualificationError("FROZEN_PLAN_HASH_CHANGED")
    compressed_buffers: list[bytearray] = []
    decoded_buffers: list[bytearray] = []
    scans: list[StationScan] = []
    try:
        for authority in PRODUCTS:
            with urlopen(authority.url, timeout=120) as response:
                compressed = bytearray(response.read())
            compressed_buffers.append(compressed)
            decoded = decode_exact_in_memory(compressed, authority)
            decoded_buffers.append(decoded)
            scans.append(scan_plain_station(decoded, authority))
        summary = evaluate_scans(scans)
        coverage_rows = [row for scan in scans for row in scan.coverage]
        coverage_text = "".join(strict_json(row) + "\n" for row in coverage_rows)
        coverage_path = output_directory / COVERAGE_NAME
        summary_path = output_directory / SUMMARY_NAME
        outcome_path = output_directory / OUTCOME_NAME
        coverage_path.write_text(coverage_text, encoding="ascii", newline="\n")
        summary_path.write_text(strict_json(summary) + "\n", encoding="ascii", newline="\n")
        outcome = {
            "schema": "gnss-independent-qualification-outcome-v1",
            "qualification_version": QUALIFICATION_VERSION,
            "plan": {
                "name": PLAN_NAME,
                "sha256": PLAN_SHA256,
                "newline_canonicalization": "CRLF_TO_LF_BEFORE_SHA256",
            },
            "products": [asdict(product) for product in PRODUCTS],
            "coverage": {
                "name": COVERAGE_NAME,
                "rows": len(coverage_rows),
                "sha256": sha256(coverage_text.encode("ascii")).hexdigest(),
            },
            "summary": {
                "name": SUMMARY_NAME,
                "sha256": sha256((strict_json(summary) + "\n").encode("ascii")).hexdigest(),
            },
            "artifact_persistence": {
                "compressed_rinex": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
            },
            "primary_selected": False,
            "primary_accessed": False,
            "orbital_measurement_performed": False,
            "historical_gold_nlib_rerun": False,
            "outcome": summary["outcome"],
        }
        outcome_path.write_text(strict_json(outcome) + "\n", encoding="ascii", newline="\n")
        return outcome
    finally:
        for scan in scans:
            scan.erase()
        for decoded in decoded_buffers:
            decoded[:] = b"\x00" * len(decoded)
        for compressed in compressed_buffers:
            compressed[:] = b"\x00" * len(compressed)


def _read_header_lines(reader: _LineReader) -> tuple[bytes, ...]:
    lines: list[bytes] = []
    while True:
        line = reader.readline()
        if not line:
            raise QualificationError("DECOMPRESSED_HEADER_INCOMPLETE")
        lines.append(line)
        if headers.header_label(line) == "END OF HEADER":
            return tuple(lines)


def _validate_header(
    parsed: dict[str, object], authority: headers.ProductAuthority
) -> None:
    expected = FROZEN_CONFIGURATION[authority.station_id]
    if parsed["receiver"] != expected["receiver"]:
        raise QualificationError(f"RECEIVER_CONFIGURATION_CHANGED:{authority.station_id}")
    if parsed["antenna"] != expected["antenna"]:
        raise QualificationError(f"ANTENNA_CONFIGURATION_CHANGED:{authority.station_id}")
    if parsed["interval_s"] != STEP_S:
        raise QualificationError(f"INTERVAL_CHANGED:{authority.station_id}")
    first = headers.parse_utc(parsed["time_of_first_observation"]["utc_like_epoch"])
    last = headers.parse_utc(parsed["time_of_last_observation"]["utc_like_epoch"])
    if parsed["time_of_first_observation"]["time_system"] != "GPS":
        raise QualificationError(f"FIRST_OBS_NOT_GPS:{authority.station_id}")
    if parsed["time_of_last_observation"]["time_system"] != "GPS":
        raise QualificationError(f"LAST_OBS_NOT_GPS:{authority.station_id}")
    if first > WINDOW_START_GPS or last < WINDOW_STOP_GPS:
        raise QualificationError(f"FROZEN_WINDOW_NOT_COVERED:{authority.station_id}")


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
            ["HEADER_CONTINUATION" if continuation else "HEADER_INITIAL"]
            * len(values)
        )
    if len(classes) != len(gps_types):
        raise QualificationError("GPS_HEADER_LINEAGE_COUNT_CHANGED")
    return dict(zip(gps_types, classes, strict=True))


def _read_window_records(
    reader: _LineReader, gps_types: Sequence[str]
) -> tuple[dict[tuple[datetime, str], _Record], dict[datetime, int]]:
    records: dict[tuple[datetime, str], _Record] = {}
    epoch_flags: dict[datetime, int] = {}
    frozen_epochs = set(expected_epochs())
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise QualificationError("RECORD_INVALID:NON_EPOCH_SOURCE_LINE")
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        if WINDOW_START_GPS <= epoch <= WINDOW_STOP_GPS:
            if epoch not in frozen_epochs:
                raise QualificationError("RECORD_INVALID:NON_30S_FROZEN_EPOCH")
            if epoch in epoch_flags:
                raise QualificationError("RECORD_INVALID:DUPLICATE_EPOCH")
            epoch_flags[epoch] = flag
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise QualificationError("RECORD_INVALID:TRUNCATED_SPECIAL_EVENT")
            continue
        if flag == 6:
            for _ in range(satellite_count):
                slip_record = reader.readline()
                if not slip_record or not _SATELLITE_PATTERN.match(slip_record):
                    raise QualificationError("RECORD_INVALID:CYCLE_SLIP_RECORD")
            continue
        if flag not in {0, 1}:
            raise QualificationError(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            record_line = reader.readline()
            if not record_line or not _SATELLITE_PATTERN.match(record_line):
                if record_line.startswith(b"   "):
                    raise QualificationError("CONTINUATION_UNSUPPORTED")
                raise QualificationError("RECORD_INVALID:SATELLITE_RECORD")
            satellite = record_line[:3].decode("ascii")
            if satellite[0] != "G" or satellite not in SATELLITES:
                continue
            if not (WINDOW_START_GPS <= epoch <= WINDOW_STOP_GPS):
                continue
            payload = record_line[3:].rstrip(b"\r\n")
            field_count = (len(payload) + 15) // 16
            if field_count > len(gps_types):
                raise QualificationError("RECORD_INVALID:FIELD_COUNT_OVERFLOW")
            padded = payload.ljust(field_count * 16, b" ")
            fields = tuple(
                padded[offset : offset + 16]
                for offset in range(0, len(padded), 16)
            )
            key = (epoch, satellite)
            if key in records:
                raise QualificationError("RECORD_INVALID:DUPLICATE_SATELLITE_RECORD")
            records[key] = _Record(
                satellite=satellite,
                fields=fields,
                field_count=field_count,
                source_line_class="RINEX_3_OBSERVATION_DATA_RECORD",
                continuation_state="NOT_REQUIRED",
            )
    return records, epoch_flags


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        parts = line.decode("ascii").split()
        second = float(parts[6])
        base_second = int(second)
        microsecond = int(round((second - base_second) * 1_000_000))
        epoch = datetime(
            int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]),
            int(parts[5]), base_second, microsecond, tzinfo=timezone.utc,
        )
        return epoch, int(parts[7]), int(parts[8])
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise QualificationError("RECORD_INVALID:EPOCH") from exc


def _parse_lli_state(field: bytes) -> str:
    value = field[14:15]
    if value in (b"", b" ", b"0"):
        return "ZERO_OR_BLANK"
    if value.isdigit():
        return "NONZERO"
    return "INVALID"


def _parse_phase(field: bytes) -> float:
    try:
        value = float(field[:14].strip().replace(b"D", b"E"))
    except ValueError as exc:
        raise QualificationError("RECORD_INVALID:PHASE_SCALAR") from exc
    if not np.isfinite(value):
        raise QualificationError("RECORD_INVALID:NONFINITE_PHASE")
    return value


def _segment_receipts(
    valid: np.ndarray, epochs: Sequence[datetime]
) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    start: int | None = None
    for index, is_valid in enumerate(valid.tolist() + [False]):
        if is_valid and start is None:
            start = index
        elif not is_valid and start is not None:
            stop = index - 1
            segments.append(
                {
                    "start_gps": structural.format_gps_epoch(epochs[start]),
                    "stop_gps": structural.format_gps_epoch(epochs[stop]),
                    "epoch_count": stop - start + 1,
                    "duration_s": (stop - start) * STEP_S,
                }
            )
            start = None
    return segments


def _geometry_free_receipt(scans: Sequence[StationScan]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    total_violations = 0
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            phase = scan.phase_cycles[:, sat_index, :]
            valid = scan.core_valid[:, sat_index]
            violations = 0
            evaluated = 0
            if np.all(valid):
                geometry_free = LAMBDA_L1_M * phase[:, 0] - LAMBDA_L2_M * phase[:, 1]
                second_difference = np.diff(geometry_free, n=2)
                violations = int(
                    np.count_nonzero(
                        np.abs(second_difference)
                        > GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                    )
                )
                evaluated = int(second_difference.size)
                geometry_free.fill(0.0)
                second_difference.fill(0.0)
            total_violations += violations
            rows.append(
                {
                    "station": scan.station,
                    "satellite": satellite,
                    "evaluated_second_differences": evaluated,
                    "violation_count": violations,
                }
            )
    return {
        "state": "SATISFIED" if total_violations == 0 and all(
            row["evaluated_second_differences"] == RAW_EPOCHS - 2 for row in rows
        ) else "UNSATISFIED",
        "threshold_m": GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
        "links": rows,
        "observed_phase_values_persisted": 0,
    }


def _code_witness_receipt(scans: Sequence[StationScan]) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    satisfied = True
    for scan in scans:
        for sat_index, satellite in enumerate(SATELLITES):
            for code_index, observable in enumerate(SAME_PATH_CODE):
                present = scan.code_present[:, sat_index, code_index]
                count = int(np.count_nonzero(present))
                fraction = count / RAW_EPOCHS
                boundaries = all(bool(present[index]) for index in CODE_REQUIRED_RAW_INDICES)
                admitted = fraction >= CODE_MINIMUM_COVERAGE_FRACTION and boundaries
                satisfied &= admitted
                rows.append(
                    {
                        "station": scan.station,
                        "satellite": satellite,
                        "observable": observable,
                        "present_epochs": count,
                        "total_epochs": RAW_EPOCHS,
                        "coverage_fraction": fraction,
                        "required_boundary_indices": list(CODE_REQUIRED_RAW_INDICES),
                        "required_boundaries_present": boundaries,
                        "admitted": admitted,
                    }
                )
    return {
        "state": "SATISFIED" if satisfied else "UNSATISFIED",
        "minimum_coverage_fraction": CODE_MINIMUM_COVERAGE_FRACTION,
        "rule": "COVERAGE_AND_FROZEN_PARTITION_BOUNDARIES_NOT_EVERY_EPOCH",
        "links": rows,
    }


def _structural_counts(scans: Sequence[StationScan]) -> dict[str, int]:
    counts = {state: 0 for state in FIELD_STATES}
    for scan in scans:
        for row in scan.coverage:
            counts[row["state"]] = counts.get(row["state"], 0) + 1
    return counts


def main() -> None:
    directory = Path(__file__).resolve().parent
    outcome = run_once(directory)
    print(strict_json(outcome))


if __name__ == "__main__":
    main()
