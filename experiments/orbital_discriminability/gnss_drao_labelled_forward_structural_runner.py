"""One-use value-blind structural scan of the selected DRAO DOY237 artifact.

This experiment-specific runner never converts or persists an observation
scalar.  It may inspect RINEX header metadata, field occupancy, LLI characters,
epoch flags and sequence topology.  It has no orbital prediction or scoring
surface.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import gc
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Final, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka

from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import (
    gnss_drao_doy232_qualification as transform_semantics,
)
from experiments.orbital_discriminability import (
    gnss_drao_labelled_forward_structural_contract as frozen,
)
from experiments.orbital_discriminability import gnss_structural_qualification as structural


RUNNER_VERSION: Final = "drao-labelled-forward-doy237-structural-runner-v1"
SELECTION_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_ARTIFACT_SELECTION.json"
SELECTION_SHA256: Final = (
    "5baa794f71c83068081c6ba766df31b6e66475b93a072e1da565e3a3d93eba09"
)
CONTRACT_NAME: Final = frozen.OUTPUT_NAME
CONTRACT_SHA256: Final = (
    "e98644daf1611f52ea744fb23e696250217bafa19e239405f39ae26a6f8bda74"
)
ARTIFACT_NAME: Final = "DRAO00CAN_R_20262370000_01D_30S_MO.crx.gz"
ARTIFACT_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/237/" + ARTIFACT_NAME
)
DECLARED_BYTES: Final = 2_849_014
DECLARED_ETAG: Final = '"2b78f6-659ef7024f09a"'
AUTHORITY_TOKEN: Final = "AUTHORIZE_DRAO_DOY237_VALUE_BLIND_STRUCTURE_ONCE"
AUTHORITY_MARKER_NAME: Final = (
    "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_AUTHORITY_CONSUMED.json"
)
MATERIALIZATION_NAME: Final = (
    "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_MATERIALIZATION.json"
)
DECODE_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_DECODE.json"
OUTCOME_NAME: Final = "GNSS_DRAO_LABELLED_FORWARD_STRUCTURAL_OUTCOME.json"

MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 4_000_000
SATELLITES: Final = frozen.SATELLITES
REQUIRED_FIELDS: Final = frozen.CORE_PHASE + frozen.SAME_PATH_CODE
CORE_PHASE: Final = frozen.CORE_PHASE
_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")

PRESENT: Final = "PRESENT"
BLANK: Final = "BLANK"
TRAILING_FIELD_OMITTED: Final = "TRAILING_FIELD_OMITTED"
FIELD_ABSENT: Final = "FIELD_ABSENT"
CONTINUATION_UNSUPPORTED: Final = "CONTINUATION_UNSUPPORTED"
RECORD_INVALID: Final = "RECORD_INVALID"


class StructuralTopologyError(ValueError):
    """The selected product cannot satisfy the frozen structural contract."""


class MaterializationError(RuntimeError):
    """The exact compressed artifact was not completely materialized."""


class DescriptionError(RuntimeError):
    """Software or receipt description failed; this is not a physical refusal."""


class _LineReader:
    """Read one line at a time without retaining an observation-line collection."""

    def __init__(self, payload: bytearray):
        self._payload = payload
        self._position = 0
        self._pending: bytes | None = None

    def readline(self) -> bytes:
        if self._pending is not None:
            line, self._pending = self._pending, None
            return line
        if self._position >= len(self._payload):
            return b""
        newline = self._payload.find(b"\n", self._position)
        stop = len(self._payload) if newline < 0 else newline + 1
        line = bytes(self._payload[self._position : stop])
        self._position = stop
        return line

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


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


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


def _source_is_clean() -> bool:
    completed = subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", str(Path(__file__))],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
    )
    return completed.returncode == 0


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise DescriptionError(f"NOT_JSON_OBJECT:{Path(path).name}")
    return value


def expected_epochs() -> tuple[datetime, ...]:
    start = datetime(2026, 8, 25, 4, 55, 0, tzinfo=timezone.utc)
    epochs = tuple(
        start + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(epochs[-1]) != "2026-08-25T06:04:00.000000Z":
        raise DescriptionError("FROZEN_WINDOW_GRID_CHANGED")
    return epochs


def verify_frozen_inputs(root: Path) -> dict[str, str]:
    root = Path(root)
    actual = {
        SELECTION_NAME: file_sha256(root / SELECTION_NAME),
        CONTRACT_NAME: file_sha256(root / CONTRACT_NAME),
    }
    expected = {
        SELECTION_NAME: SELECTION_SHA256,
        CONTRACT_NAME: CONTRACT_SHA256,
    }
    if actual != expected:
        raise DescriptionError("FROZEN_SELECTION_OR_CONTRACT_CHANGED")
    selection = _read_json(root / SELECTION_NAME)
    artifact = selection.get("artifact", {})
    if selection.get("state") != "DRAO_LABELLED_FORWARD_ARTIFACT_SELECTED_UNOPENED":
        raise DescriptionError("ARTIFACT_SELECTION_NOT_UNOPENED")
    if (
        artifact.get("name") != ARTIFACT_NAME
        or artifact.get("url") != ARTIFACT_URL
        or artifact.get("body_access_authorized") is not False
        or selection.get("http_head_receipt", {}).get("content_length")
        != DECLARED_BYTES
    ):
        raise DescriptionError("FROZEN_ARTIFACT_IDENTITY_CHANGED")
    contract = _read_json(root / CONTRACT_NAME)
    if contract.get("state") != frozen.CONTRACT_STATE:
        raise DescriptionError("STRUCTURAL_CONTRACT_STATE_CHANGED")
    frozen.verify_authorities(root)
    return actual


def manifest(root: Path | None = None) -> dict[str, object]:
    base = Path(__file__).resolve().parent if root is None else Path(root)
    value = {
        "schema": "gnss-drao-labelled-forward-structural-runner-manifest-v1",
        "runner_version": RUNNER_VERSION,
        "frozen_inputs": verify_frozen_inputs(base),
        "artifact": {
            "name": ARTIFACT_NAME,
            "url": ARTIFACT_URL,
            "declared_bytes": DECLARED_BYTES,
            "declared_etag": DECLARED_ETAG,
            "fallback": False,
        },
        "window": {
            "start_gps": structural.format_gps_epoch(expected_epochs()[0]),
            "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]),
            "cadence_s": frozen.STEP_S,
            "epochs": frozen.RAW_EPOCHS,
            "satellites": list(SATELLITES),
            "required_satellite_epoch_pairs": frozen.RAW_EPOCHS * len(SATELLITES),
        },
        "inspection_surface": {
            "header_metadata": True,
            "epoch_and_satellite_framing": True,
            "field_occupancy": list(REQUIRED_FIELDS),
            "lli_characters": list(CORE_PHASE),
            "observation_scalar_conversion": False,
            "observation_value_serialization": False,
            "orbital_model_available": False,
            "orbital_scores": 0,
        },
        "transport": {
            "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
            "retry_reasons": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "complete_transport_hash_before_decompression": True,
            "complete_decoded_hash_before_record_traversal": True,
            "post_hash_retry": 0,
        },
        "persistence": {
            "compressed_artifact_after_outcome": 0,
            "decoded_rinex_after_outcome": 0,
            "observation_values": 0,
            "derived_measurement_series": 0,
            "receipts_only": True,
        },
        "outcomes": list(frozen.contract(base)["future_outcomes"]),
        "new_gate": False,
        "stop": "ONE_STRUCTURAL_OUTCOME_BEFORE_PHYSICAL_WITNESS_OR_SCORE",
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path | None = None) -> str:
    return sha256(strict_json(manifest(root)).encode("ascii")).hexdigest()


def _header_lines(reader: _LineReader) -> tuple[bytes, ...]:
    lines: list[bytes] = []
    for _ in range(headers.MAX_HEADER_LINES):
        line = reader.readline()
        if not line:
            raise StructuralTopologyError("HEADER_INCOMPLETE")
        lines.append(line)
        if headers.header_label(line) == "END OF HEADER":
            return tuple(lines)
    raise StructuralTopologyError("HEADER_LINE_LIMIT_EXCEEDED")


def _normalize(value: object) -> str:
    return " ".join(str(value).replace("_", " ").split())


def _validate_header(parsed: Mapping[str, object]) -> tuple[dict[str, str], tuple[str, ...]]:
    clauses: dict[str, str] = {}

    def clause(name: str, passed: bool) -> None:
        clauses[name] = "SATISFIED" if passed else "UNSATISFIED"

    receiver = parsed.get("receiver", {})
    antenna = parsed.get("antenna", {})
    antenna_type = str(antenna.get("type", "")).ljust(20)
    first_info = parsed.get("time_of_first_observation", {})
    last_info = parsed.get("time_of_last_observation", {})
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_epochs()
    gps_types = tuple(parsed.get("observable_types", {}).get("G", ()))

    clause("RINEX_VERSION_3", 3.0 <= float(parsed.get("rinex_version", 0.0)) < 4.0)
    clause("MARKER_SITE_DRAO", _normalize(parsed.get("marker_name", "")) == "DRAO")
    clause("DOMES_40105M002", _normalize(parsed.get("marker_number", "")) == frozen.DOMES)
    clause("RECEIVER_SEPT_POLARX5", _normalize(receiver.get("type", "")) == "SEPT POLARX5")
    clause("RECEIVER_VERSION_5_2_0", _normalize(receiver.get("version_or_radome", "")) == "5.2.0")
    clause("ANTENNA_TWIVC6050", _normalize(antenna_type[:16]) == "TWIVC6050")
    clause("RADOME_SCIS", _normalize(antenna_type[16:20]) == "SCIS")
    clause("INTERVAL_30_SECONDS", float(parsed.get("interval_s", -1.0)) == frozen.STEP_S)
    clause(
        "GPS_TIME_SYSTEM",
        first_info.get("time_system") == "GPS" and last_info.get("time_system") == "GPS",
    )
    clause("TIME_OF_FIRST_OBS_COVERS_WINDOW", first <= epochs[0])
    clause("TIME_OF_LAST_OBS_COVERS_WINDOW", last >= epochs[-1])
    clause(
        "REQUIRED_GPS_FIELDS_DECLARED",
        set(REQUIRED_FIELDS).issubset(gps_types),
    )
    clause(
        "RECEIVER_CLOCK_SEMANTICS_SUPPORTED",
        parsed.get("receiver_clock_offset_applied") in {0, 1},
    )
    try:
        transform_semantics.parse_scale_factors(
            parsed.get("scale_factor_records", ()), gps_types
        )
        transform_semantics.parse_phase_shift_coverage(
            parsed.get("phase_shift_records", ()), SATELLITES
        )
    except Exception:
        clause("SCALE_AND_PHASE_SHIFT_SEMANTICS_SUPPORTED", False)
    else:
        clause("SCALE_AND_PHASE_SHIFT_SEMANTICS_SUPPORTED", True)
    return clauses, gps_types


def _parse_epoch(line: bytes) -> tuple[datetime, int, int, float | None]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        whole = int(second)
        microsecond = int(round((second - whole) * 1_000_000))
        epoch = datetime(
            int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]),
            int(parts[5]), whole, microsecond, tzinfo=timezone.utc,
        )
        clock = float(parts[9].replace("D", "E")) if len(parts) > 9 else None
        if clock is not None and not (-1.0 < clock < 1.0):
            raise ValueError("receiver clock outside structural bound")
        return epoch, int(parts[7]), int(parts[8]), clock
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise StructuralTopologyError("RECORD_INVALID:EPOCH") from exc


def _field_chunks(payload: bytes) -> tuple[bytes, ...]:
    body = payload.rstrip(b"\r\n")
    if not body:
        return ()
    count = (len(body) + 15) // 16
    padded = body.ljust(count * 16, b" ")
    return tuple(padded[index : index + 16] for index in range(0, len(padded), 16))


def _read_record(
    reader: _LineReader, system_types: Mapping[str, Sequence[str]]
) -> tuple[str, tuple[bytes, ...], bool]:
    line = reader.readline()
    if not line or not _SATELLITE_PATTERN.match(line):
        if line.startswith(b"   "):
            return "", (), True
        raise StructuralTopologyError("RECORD_INVALID:SATELLITE_RECORD")
    satellite = line[:3].decode("ascii", errors="strict")
    expected = len(system_types.get(satellite[0], ()))
    if expected == 0:
        raise StructuralTopologyError(f"RECORD_INVALID:UNDECLARED_SYSTEM:{satellite[0]}")
    fields = _field_chunks(line[3:])
    if len(fields) > expected:
        raise StructuralTopologyError("RECORD_INVALID:FIELD_COUNT_OVERFLOW")
    return satellite, fields, False


def _grid_index(epoch: datetime) -> tuple[int, float]:
    epochs = expected_epochs()
    elapsed = (epoch - epochs[0]).total_seconds() / frozen.STEP_S
    index = int(round(elapsed))
    if index < 0 or index >= len(epochs):
        raise StructuralTopologyError("EVENT_TIME_OUTSIDE_FROZEN_WINDOW")
    deviation = float((epoch - epochs[index]).total_seconds())
    if abs(deviation) > 15.0:
        raise StructuralTopologyError("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    if abs(abs(deviation) - 15.0) < 1.0e-9:
        raise StructuralTopologyError("EVENT_TIME_GRID_ASSIGNMENT_AMBIGUOUS")
    return index, deviation


def _field_state(fields: Sequence[bytes], index: int | None) -> tuple[str, bytes | None]:
    if index is None:
        return FIELD_ABSENT, None
    if index >= len(fields):
        return TRAILING_FIELD_OMITTED, None
    field = fields[index]
    return (PRESENT, field) if field[:14].strip() else (BLANK, field)


def _lli_state(field: bytes | None, state: str) -> str:
    if state != PRESENT or field is None:
        return "UNAVAILABLE"
    token = field[14:15]
    if token in {b"", b" ", b"0"}:
        return "ZERO_OR_BLANK"
    if token.isdigit():
        return "NONZERO"
    return "INVALID"


def _segments(valid: Sequence[bool]) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    start: int | None = None
    for index, present in enumerate(list(valid) + [False]):
        if present and start is None:
            start = index
        elif not present and start is not None:
            stop = index - 1
            result.append(
                {"first_index": start, "last_index": stop, "epoch_count": stop - start + 1}
            )
            start = None
    return result


def scan_decoded(decoded: bytearray) -> dict[str, object]:
    """Return structural aggregates without converting an observation scalar."""

    reader = _LineReader(decoded)
    try:
        header_lines = _header_lines(reader)
        header_hash = sha256(b"".join(header_lines)).hexdigest()
        parsed = headers.parse_header_lines(header_lines)
        header_clauses, gps_types = _validate_header(parsed)
    except (headers.HeaderAdmissionError, KeyError, TypeError, ValueError) as exc:
        raise StructuralTopologyError(f"HEADER_INVALID:{exc}") from exc

    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
    }
    indices = {
        observable: gps_types.index(observable) if observable in gps_types else None
        for observable in REQUIRED_FIELDS
    }
    receiver_clock_applied = int(parsed["receiver_clock_offset_applied"])
    start = expected_epochs()[0] - timedelta(seconds=15)
    stop = expected_epochs()[-1] + timedelta(seconds=15)
    pairs: dict[tuple[int, str], dict[str, object]] = {}
    epoch_flags: dict[int, int] = {}
    deviations: dict[int, float] = {}
    extra_track_records = 0
    continuation_unsupported = 0
    record_invalid_reasons: list[str] = []

    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                record_invalid_reasons.append("NON_EPOCH_SOURCE_LINE")
            continue
        try:
            raw_epoch, flag, satellite_count, clock = _parse_epoch(line)
        except StructuralTopologyError as exc:
            record_invalid_reasons.append(str(exc))
            break
        correction = float(clock) if receiver_clock_applied == 0 and clock is not None else 0.0
        epoch = raw_epoch - timedelta(seconds=correction)
        if epoch > stop:
            break
        in_window = start <= epoch <= stop
        grid_index: int | None = None
        if in_window:
            try:
                grid_index, deviation = _grid_index(epoch)
            except StructuralTopologyError as exc:
                record_invalid_reasons.append(str(exc))
            else:
                if grid_index in epoch_flags:
                    record_invalid_reasons.append("RECORD_INVALID:DUPLICATE_GRID_EPOCH")
                else:
                    epoch_flags[grid_index] = flag
                    deviations[grid_index] = deviation
        epoch_records: dict[str, tuple[bytes, ...]] = {}
        for _ in range(satellite_count):
            try:
                satellite, fields, unsupported = _read_record(reader, system_types)
            except StructuralTopologyError as exc:
                record_invalid_reasons.append(str(exc))
                break
            if unsupported:
                continuation_unsupported += 1
                continue
            if grid_index is None:
                continue
            if satellite in SATELLITES:
                if satellite in epoch_records:
                    record_invalid_reasons.append("RECORD_INVALID:DUPLICATE_SATELLITE_RECORD")
                epoch_records[satellite] = fields
            elif satellite.startswith("G"):
                extra_track_records += 1
        if grid_index is None:
            continue
        for satellite in SATELLITES:
            fields = epoch_records.get(satellite)
            field_states: dict[str, str] = {}
            lli_states: dict[str, str] = {}
            for observable in REQUIRED_FIELDS:
                state, field = (
                    _field_state(fields, indices[observable])
                    if fields is not None
                    else (FIELD_ABSENT, None)
                )
                field_states[observable] = state
                if observable in CORE_PHASE:
                    lli_states[observable] = _lli_state(field, state)
            pairs[(grid_index, satellite)] = {
                "field_states": field_states,
                "lli_states": lli_states,
                "epoch_flag": flag,
            }

    field_counts = {
        observable: Counter() for observable in REQUIRED_FIELDS
    }
    lli_counts = {observable: Counter() for observable in CORE_PHASE}
    valid_by_satellite = {satellite: [] for satellite in SATELLITES}
    for index in range(frozen.RAW_EPOCHS):
        for satellite in SATELLITES:
            pair = pairs.get((index, satellite))
            if pair is None:
                states = {observable: FIELD_ABSENT for observable in REQUIRED_FIELDS}
                llis = {observable: "UNAVAILABLE" for observable in CORE_PHASE}
                flag = epoch_flags.get(index)
            else:
                states = pair["field_states"]
                llis = pair["lli_states"]
                flag = pair["epoch_flag"]
            for observable, state in states.items():
                field_counts[observable][state] += 1
            for observable, state in llis.items():
                lli_counts[observable][state] += 1
            valid_by_satellite[satellite].append(
                flag == 0
                and all(states[observable] == PRESENT for observable in REQUIRED_FIELDS)
                and all(llis[observable] == "ZERO_OR_BLANK" for observable in CORE_PHASE)
            )

    typed_refusals: list[str] = []
    for name, state in sorted(header_clauses.items()):
        if state != "SATISFIED":
            typed_refusals.append(f"HEADER_CLAUSE_UNSATISFIED:{name}")
    if len(epoch_flags) != frozen.RAW_EPOCHS:
        typed_refusals.append(f"EPOCH_GRID_INCOMPLETE:{len(epoch_flags)}:{frozen.RAW_EPOCHS}")
    nonzero_flags = sum(flag != 0 for flag in epoch_flags.values())
    if nonzero_flags:
        typed_refusals.append(f"NONZERO_EPOCH_FLAGS:{nonzero_flags}")
    if continuation_unsupported:
        typed_refusals.append(f"CONTINUATION_UNSUPPORTED:{continuation_unsupported}")
    typed_refusals.extend(sorted(set(record_invalid_reasons)))
    for observable in REQUIRED_FIELDS:
        missing = frozen.RAW_EPOCHS * len(SATELLITES) - field_counts[observable][PRESENT]
        if missing:
            typed_refusals.append(f"FIELD_NOT_PRESENT:{observable}:{missing}")
    for observable in CORE_PHASE:
        bad = sum(
            count for state, count in lli_counts[observable].items()
            if state != "ZERO_OR_BLANK"
        )
        if bad:
            typed_refusals.append(f"LLI_NOT_ZERO_OR_BLANK:{observable}:{bad}")

    segments = {}
    for satellite, valid in valid_by_satellite.items():
        rows = _segments(valid)
        maximum = max(rows, key=lambda row: row["epoch_count"], default=None)
        segments[satellite] = {
            "maximal_segment": maximum,
            "full_window": bool(maximum and maximum["epoch_count"] == frozen.RAW_EPOCHS),
        }

    ready = not typed_refusals and all(
        row["full_window"] for row in segments.values()
    )
    result = {
        "schema": "gnss-drao-labelled-forward-structural-scan-v1",
        "state": (
            "DRAO_LABELLED_FORWARD_STRUCTURE_READY_FOR_INTEGRATED_PROOF"
            if ready
            else "DRAO_STRUCTURE_TOPOLOGY_REJECTED"
        ),
        "header_sha256": header_hash,
        "header_lines": len(header_lines),
        "header_clause_states": dict(sorted(header_clauses.items())),
        "epoch_grid": {
            "expected": frozen.RAW_EPOCHS,
            "observed": len(epoch_flags),
            "normal_flags": sum(flag == 0 for flag in epoch_flags.values()),
            "maximum_absolute_grid_deviation_s": (
                max((abs(value) for value in deviations.values()), default=None)
            ),
            "frozen_event_time_bound_s": [-15.0, 15.0],
            "bound_reduced_by_scan": False,
        },
        "required_satellite_epoch_pairs": frozen.RAW_EPOCHS * len(SATELLITES),
        "field_state_counts": {
            observable: dict(sorted(counts.items()))
            for observable, counts in field_counts.items()
        },
        "lli_state_counts": {
            observable: dict(sorted(counts.items()))
            for observable, counts in lli_counts.items()
        },
        "segments": segments,
        "extra_gps_track_records_descriptive_only": extra_track_records,
        "typed_refusal_reasons": typed_refusals,
        "physical_clauses": {
            "geometry_free_phase_continuity": "NOT_EVALUATED",
            "phase_minus_code_same_path_witness": "NOT_EVALUATED",
            "multipath_hardware_receiver": "NOT_EVALUATED",
            "orbital_null_comparison": "NOT_EVALUATED",
        },
        "observation_scalar_conversions": 0,
        "observation_values_persisted": 0,
        "derived_measurement_series_persisted": 0,
        "orbital_scores": 0,
    }
    strict_json(result)
    return result


def _write_once(path: Path, value: Mapping[str, object]) -> None:
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def _consume_authority(root: Path, token: str) -> dict[str, object]:
    if token != AUTHORITY_TOKEN:
        raise DescriptionError("EXACT_ONE_USE_AUTHORITY_REQUIRED")
    if not _source_is_clean():
        raise DescriptionError("RUNNER_SOURCE_NOT_COMMITTED")
    value = {
        "schema": "gnss-drao-labelled-forward-structural-authority-v1",
        "state": "AUTHORITY_CONSUMED_BEFORE_NETWORK",
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": manifest_sha256(root),
        "selection_sha256": SELECTION_SHA256,
        "contract_sha256": CONTRACT_SHA256,
        "artifact": ARTIFACT_NAME,
        "fallback": False,
    }
    _write_once(root / AUTHORITY_MARKER_NAME, value)
    return value


def _download_once(path: Path) -> dict[str, object]:
    request = Request(ARTIFACT_URL, headers={"User-Agent": "Satellite-RF-Observatory/1"})
    with urlopen(request, timeout=HTTP_TIMEOUT_S) as response, Path(path).open("xb") as stream:
        status = int(getattr(response, "status", 200))
        content_length = int(response.headers.get("Content-Length", "0"))
        etag = response.headers.get("ETag")
        if status != 200 or content_length != DECLARED_BYTES or etag != DECLARED_ETAG:
            raise MaterializationError("FROZEN_HTTP_IDENTITY_CHANGED")
        received = 0
        while block := response.read(64 * 1024):
            received += len(block)
            if received > MAX_COMPRESSED_BYTES:
                raise MaterializationError("COMPRESSED_SIZE_LIMIT_EXCEEDED")
            stream.write(block)
    if received != DECLARED_BYTES or Path(path).stat().st_size != DECLARED_BYTES:
        raise MaterializationError("INCOMPLETE_ARTIFACT")
    return {
        "status": status,
        "content_length": content_length,
        "etag": etag,
        "received_bytes": received,
    }


def _materialize(path: Path) -> tuple[dict[str, object], int]:
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        try:
            metadata = _download_once(path)
            return metadata, attempt
        except (TimeoutError, URLError, HTTPError) as exc:
            if Path(path).exists():
                Path(path).unlink()
            if attempt == MAX_TRANSPORT_ATTEMPTS:
                raise MaterializationError(f"TRANSPORT_INTERRUPTION:{type(exc).__name__}") from exc
    raise AssertionError("unreachable")


def execute(root: Path, authority_token: str) -> dict[str, object]:
    root = Path(root)
    inputs = verify_frozen_inputs(root)
    authority = _consume_authority(root, authority_token)
    compressed = bytearray()
    decoded = bytearray()
    final: dict[str, object]
    try:
        with tempfile.TemporaryDirectory(prefix="drao-doy237-") as directory:
            artifact_path = Path(directory) / ARTIFACT_NAME
            try:
                http, attempts = _materialize(artifact_path)
                artifact_hash = file_sha256(artifact_path)
                materialization = {
                    "schema": "gnss-drao-labelled-forward-materialization-v1",
                    "state": "COMPLETE_ARTIFACT_HASHED_BEFORE_DECOMPRESSION",
                    "artifact": {
                        "name": ARTIFACT_NAME,
                        "bytes": DECLARED_BYTES,
                        "sha256": artifact_hash,
                    },
                    "http": http,
                    "transport_attempts": attempts,
                    "decompressions_at_receipt": 0,
                    "headers_at_receipt": 0,
                    "observation_values_at_receipt": 0,
                }
                _write_once(root / MATERIALIZATION_NAME, materialization)
            except MaterializationError as exc:
                final = {
                    "schema": "gnss-drao-labelled-forward-structural-outcome-v1",
                    "outcome": "DRAO_STRUCTURE_ARTIFACT_MATERIALIZATION_FAILED",
                    "reason": str(exc),
                    "authority": authority,
                    "frozen_inputs": inputs,
                    "physical_clauses": "NOT_EVALUATED",
                    "observation_values_persisted": 0,
                    "orbital_scores": 0,
                }
                _write_once(root / OUTCOME_NAME, final)
                return final

            compressed = bytearray(artifact_path.read_bytes())
            try:
                decoded = bytearray(hatanaka.decompress(bytes(compressed), strict=True))
            except Exception as exc:
                raise DescriptionError("HATANAKA_DECOMPRESSION_FAILED") from exc
            decoded_receipt = {
                "schema": "gnss-drao-labelled-forward-decode-v1",
                "state": "COMPLETE_DECODE_HASHED_BEFORE_RECORD_TRAVERSAL",
                "decoded_bytes": len(decoded),
                "decoded_sha256": sha256(decoded).hexdigest(),
                "hatanaka_version": importlib.metadata.version("hatanaka"),
                "record_traversals_at_receipt": 0,
                "observation_values_at_receipt": 0,
            }
            _write_once(root / DECODE_NAME, decoded_receipt)
            scan = scan_decoded(decoded)
            final = {
                "schema": "gnss-drao-labelled-forward-structural-outcome-v1",
                "outcome": scan["state"],
                "authority": authority,
                "frozen_inputs": inputs,
                "artifact": materialization["artifact"],
                "decoded": {
                    "bytes": decoded_receipt["decoded_bytes"],
                    "sha256": decoded_receipt["decoded_sha256"],
                },
                "structural_scan": scan,
                "cleanup": {
                    "compressed_artifact_retained": False,
                    "decoded_rinex_retained": False,
                    "observation_values_persisted": 0,
                    "derived_measurement_series_persisted": 0,
                },
            }
            _write_once(root / OUTCOME_NAME, final)
            return final
    except StructuralTopologyError as exc:
        final = {
            "schema": "gnss-drao-labelled-forward-structural-outcome-v1",
            "outcome": "DRAO_STRUCTURE_TOPOLOGY_REJECTED",
            "reason": str(exc),
            "authority": authority,
            "frozen_inputs": inputs,
            "physical_clauses": "NOT_EVALUATED",
            "observation_values_persisted": 0,
            "orbital_scores": 0,
        }
        _write_once(root / OUTCOME_NAME, final)
        return final
    except DescriptionError as exc:
        final = {
            "schema": "gnss-drao-labelled-forward-structural-outcome-v1",
            "outcome": "DRAO_STRUCTURE_DESCRIPTION_ERROR",
            "reason": str(exc),
            "authority": authority,
            "frozen_inputs": inputs,
            "physical_clauses": "NOT_EVALUATED",
            "observation_values_persisted": 0,
            "orbital_scores": 0,
        }
        _write_once(root / OUTCOME_NAME, final)
        return final
    finally:
        compressed[:] = b"\x00" * len(compressed)
        decoded[:] = b"\x00" * len(decoded)
        gc.collect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-token", required=True)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    value = execute(args.root, args.authority_token)
    print(strict_json(value))


if __name__ == "__main__":
    main()
