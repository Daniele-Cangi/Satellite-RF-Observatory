"""Value-blind RINEX structural qualification for the closed GOLD/NLIB run.

This module is a bounded parser repair, not a measurement decoder.  It may
inspect record framing and field occupancy, but it never converts, returns or
serializes an observation value.  RINEX 3 observation records are treated as
variable-length single lines; empty trailing fields may therefore be omitted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import io
import json
import re
from typing import Final, Iterable, Sequence

import hatanaka

from experiments.orbital_discriminability import gnss_observation_header as headers


PARSER_VERSION: Final = "rinex-3-value-blind-structural-qualification-v1"
RINEX_SPECIFICATION: Final = "https://files.igs.org/pub/data/format/rinex304.pdf"
PARENT_OUTCOME_SHA256: Final = (
    "4060e8e3046696f6433ce5226e3d7f524d430cbbd49261fd1041554ab76b5172"
)
PARENT_TERMINAL: Final = (
    "MEASUREMENT_INVALID",
    "TRUNCATED_REQUIRED_OBSERVATION_RECORD",
)
FORENSIC_ARTIFACT_ROLES: Final = (
    "FORENSIC_DEVELOPMENT_ONLY",
    "NEVER_PRIMARY_AGAIN",
    "NEVER_SCORED_AGAIN",
)
REQUIRED_SATELLITES: Final = ("G11", "G21")
HISTORICAL_REQUIRED_OBSERVABLES: Final = (
    "C1C",
    "L1C",
    "S1C",
    "C2W",
    "L2W",
    "S2W",
)


class StructuralState(StrEnum):
    FIELD_PRESENT = "FIELD_PRESENT"
    FIELD_ABSENT = "FIELD_ABSENT"
    FIELD_BLANK = "FIELD_BLANK"
    TRAILING_FIELD_OMITTED = "TRAILING_FIELD_OMITTED"
    CONTINUATION_SUPPORTED = "CONTINUATION_SUPPORTED"
    CONTINUATION_UNSUPPORTED = "CONTINUATION_UNSUPPORTED"
    DESCRIPTION_ERROR = "DESCRIPTION_ERROR"
    RECORD_INVALID = "RECORD_INVALID"


DIAGNOSTIC_KEYS: Final = frozenset(
    {
        "station",
        "gps_epoch",
        "satellite",
        "required_observable",
        "header_declared_index",
        "reconstructed_field_count",
        "source_line_class",
        "continuation_class",
        "typed_structural_state",
    }
)


@dataclass(frozen=True, slots=True)
class StructuralDiagnostic:
    station: str
    gps_epoch: str | None
    satellite: str | None
    required_observable: str
    header_declared_index: int | None
    reconstructed_field_count: int
    source_line_class: str
    continuation_class: str
    typed_structural_state: str

    def receipt(self) -> dict[str, object]:
        result = asdict(self)
        if set(result) != DIAGNOSTIC_KEYS:
            raise StructuralDescriptionError("DIAGNOSTIC_SCHEMA_CHANGED")
        if self.typed_structural_state not in {state.value for state in StructuralState}:
            raise StructuralDescriptionError("UNKNOWN_STRUCTURAL_STATE")
        strict_json(result)
        return result


@dataclass(frozen=True, slots=True)
class ObservationTypeDeclaration:
    observables: tuple[str, ...]
    line_classes: tuple[str, ...]


class StructuralQualificationError(ValueError):
    """The RINEX structure cannot be admitted."""


class StructuralDescriptionError(ValueError):
    """A receipt could not be described; this is not a physical refusal."""


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
            raise StructuralQualificationError("MULTIPLE_LINE_PUSHBACK")
        self._pending = line


_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


def strict_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def sha256_bytes(payload: bytes | bytearray) -> str:
    return sha256(payload).hexdigest()


def format_gps_epoch(epoch: datetime) -> str:
    if epoch.tzinfo is None or epoch.utcoffset() is None:
        raise StructuralDescriptionError("GPS_EPOCH_MUST_BE_TIMEZONE_AWARE")
    return epoch.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def decode_exact_artifact_in_memory(
    compressed: bytearray,
    authority: headers.ProductAuthority,
) -> bytearray:
    """Hash then decompress an exact artifact; both buffers remain caller-owned."""

    if len(compressed) != authority.bytes:
        raise StructuralQualificationError("OBSERVATION_BYTE_COUNT_CHANGED")
    if sha256_bytes(compressed) != authority.sha256:
        raise StructuralQualificationError("OBSERVATION_SHA256_CHANGED")
    try:
        plain = hatanaka.decompress(bytes(compressed), strict=True)
    except Exception as exc:  # pragma: no cover - exact codec error text is external
        raise StructuralQualificationError("HATANAKA_DECODING_FAILED") from exc
    return bytearray(plain)


def scan_plain_rinex_structure(
    decoded: bytearray,
    *,
    station: str,
    required_satellites: Sequence[str],
    required_observables: Sequence[str],
    window_start_gps: datetime,
    window_stop_gps: datetime,
    first_failure_only: bool = True,
) -> dict[str, object]:
    """Inspect only RINEX framing and field occupancy on a frozen GPS window."""

    if window_start_gps > window_stop_gps:
        raise StructuralDescriptionError("WINDOW_ORDER_INVALID")
    reader = _LineReader(decoded)
    declarations, header_diagnostics = _read_observation_type_declarations(
        reader, station, required_observables
    )
    gps = declarations.get("G")
    diagnostics = list(header_diagnostics)
    if gps is None:
        for observable in required_observables:
            diagnostics.append(
                _diagnostic(
                    station,
                    None,
                    None,
                    observable,
                    None,
                    0,
                    "RINEX_3_SYS_OBS_TYPES_HEADER",
                    "NO_DECLARATION",
                    StructuralState.FIELD_ABSENT,
                )
            )
        return _scan_receipt(station, diagnostics, 0)

    indices = {name: index for index, name in enumerate(gps.observables)}
    for observable in required_observables:
        if observable not in indices:
            diagnostics.append(
                _diagnostic(
                    station,
                    None,
                    "G",
                    observable,
                    None,
                    len(gps.observables),
                    "RINEX_3_SYS_OBS_TYPES_HEADER",
                    "DECLARATION_COMPLETE",
                    StructuralState.FIELD_ABSENT,
                )
            )
            if first_failure_only:
                return _scan_receipt(station, diagnostics, 0)

    records_examined = 0
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                diagnostics.append(
                    _diagnostic(
                        station,
                        None,
                        None,
                        "",
                        None,
                        0,
                        "NON_EPOCH_SOURCE_LINE",
                        "NOT_APPLICABLE",
                        StructuralState.RECORD_INVALID,
                    )
                )
                return _scan_receipt(station, diagnostics, records_examined)
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        if epoch > window_stop_gps:
            break
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    diagnostics.append(
                        _diagnostic(
                            station,
                            epoch,
                            None,
                            "",
                            None,
                            0,
                            "RINEX_3_SPECIAL_EVENT_RECORD",
                            "NOT_APPLICABLE",
                            StructuralState.RECORD_INVALID,
                        )
                    )
                    return _scan_receipt(station, diagnostics, records_examined)
            continue
        for _ in range(satellite_count):
            record = reader.readline()
            if not record or not _SATELLITE_PATTERN.match(record):
                state = (
                    StructuralState.CONTINUATION_UNSUPPORTED
                    if record.startswith(b"   ")
                    else StructuralState.RECORD_INVALID
                )
                diagnostics.append(
                    _diagnostic(
                        station,
                        epoch,
                        None,
                        "",
                        None,
                        0,
                        "RINEX_3_OBSERVATION_DATA_RECORD",
                        (
                            "NONSTANDARD_THREE_SPACE_DATA_CONTINUATION"
                            if state is StructuralState.CONTINUATION_UNSUPPORTED
                            else "NOT_APPLICABLE"
                        ),
                        state,
                    )
                )
                return _scan_receipt(station, diagnostics, records_examined)
            satellite = record[:3].decode("ascii", errors="strict")
            system = satellite[0]
            declaration = declarations.get(system)
            if declaration is None:
                diagnostics.append(
                    _diagnostic(
                        station,
                        epoch,
                        satellite,
                        "",
                        None,
                        0,
                        "RINEX_3_OBSERVATION_DATA_RECORD",
                        "NOT_APPLICABLE",
                        StructuralState.RECORD_INVALID,
                    )
                )
                return _scan_receipt(station, diagnostics, records_examined)
            payload = record[3:].rstrip(b"\r\n")
            expected_field_count = len(declaration.observables)
            reconstructed_field_count = (len(payload) + 15) // 16
            if reconstructed_field_count > expected_field_count:
                diagnostics.append(
                    _diagnostic(
                        station,
                        epoch,
                        satellite,
                        "",
                        None,
                        reconstructed_field_count,
                        "RINEX_3_OBSERVATION_DATA_RECORD",
                        "SINGLE_LINE_RECORD",
                        StructuralState.RECORD_INVALID,
                    )
                )
                return _scan_receipt(station, diagnostics, records_examined)

            if reconstructed_field_count < expected_field_count:
                following = reader.readline()
                if following.startswith(b"   "):
                    first_unserialized = declaration.observables[
                        reconstructed_field_count
                    ]
                    diagnostics.append(
                        _diagnostic(
                            station,
                            epoch,
                            satellite,
                            first_unserialized,
                            reconstructed_field_count,
                            reconstructed_field_count,
                            "RINEX_3_OBSERVATION_DATA_RECORD",
                            "NONSTANDARD_THREE_SPACE_DATA_CONTINUATION",
                            StructuralState.CONTINUATION_UNSUPPORTED,
                        )
                    )
                    return _scan_receipt(station, diagnostics, records_examined)
                if following:
                    reader.push(following)

            if not (window_start_gps <= epoch <= window_stop_gps):
                continue
            if satellite not in required_satellites:
                continue
            records_examined += 1
            padded = payload.ljust(reconstructed_field_count * 16, b" ")
            fields = tuple(
                padded[offset : offset + 16]
                for offset in range(0, len(padded), 16)
            )
            for observable in required_observables:
                index = indices.get(observable)
                if index is None:
                    continue
                if index >= reconstructed_field_count:
                    state = StructuralState.TRAILING_FIELD_OMITTED
                elif not fields[index][:14].strip():
                    state = StructuralState.FIELD_BLANK
                else:
                    state = StructuralState.FIELD_PRESENT
                if state is not StructuralState.FIELD_PRESENT:
                    diagnostics.append(
                        _diagnostic(
                            station,
                            epoch,
                            satellite,
                            observable,
                            index,
                            reconstructed_field_count,
                            "RINEX_3_OBSERVATION_DATA_RECORD",
                            "SINGLE_LINE_VARIABLE_LENGTH_RECORD",
                            state,
                        )
                    )
                    if first_failure_only:
                        return _scan_receipt(station, diagnostics, records_examined)
    return _scan_receipt(station, diagnostics, records_examined)


def _read_observation_type_declarations(
    reader: _LineReader,
    station: str,
    required_observables: Sequence[str],
) -> tuple[dict[str, ObservationTypeDeclaration], tuple[dict[str, object], ...]]:
    collected: dict[str, list[str]] = {}
    line_classes: dict[str, list[str]] = {}
    expected: dict[str, int] = {}
    current_system: str | None = None
    continuation_diagnostics: list[dict[str, object]] = []
    while True:
        line = reader.readline()
        if not line:
            raise StructuralQualificationError("DECOMPRESSED_HEADER_INCOMPLETE")
        body = line.rstrip(b"\r\n")
        label = body[60:80].decode("ascii", errors="strict").strip() if len(body) >= 60 else ""
        if label == "SYS / # / OBS TYPES":
            continuation = body[:1] == b" "
            if not continuation:
                current_system = body[:1].decode("ascii", errors="strict")
                try:
                    expected[current_system] = int(body[3:6])
                except ValueError as exc:
                    raise StructuralQualificationError(
                        "INVALID_OBSERVATION_TYPE_COUNT"
                    ) from exc
                collected[current_system] = []
                line_classes[current_system] = []
            if current_system is None:
                raise StructuralQualificationError(
                    "ORPHAN_OBSERVATION_TYPE_CONTINUATION"
                )
            observables = body[7:60].decode("ascii", errors="strict").split()
            collected[current_system].extend(observables)
            line_class = (
                "RINEX_3_SYS_OBS_TYPES_CONTINUATION"
                if continuation
                else "RINEX_3_SYS_OBS_TYPES_INITIAL"
            )
            line_classes[current_system].extend([line_class] * len(observables))
        if label == "END OF HEADER":
            break
    declarations: dict[str, ObservationTypeDeclaration] = {}
    for system, count in expected.items():
        if len(collected[system]) != count:
            raise StructuralQualificationError(
                f"OBSERVABLE_COUNT_MISMATCH:{system}:{count}:{len(collected[system])}"
            )
        declaration = ObservationTypeDeclaration(
            tuple(collected[system]), tuple(line_classes[system])
        )
        declarations[system] = declaration
        if system == "G":
            for observable in required_observables:
                if observable not in declaration.observables:
                    continue
                index = declaration.observables.index(observable)
                if declaration.line_classes[index].endswith("CONTINUATION"):
                    continuation_diagnostics.append(
                        _diagnostic(
                            station,
                            None,
                            "G",
                            observable,
                            index,
                            len(declaration.observables),
                            "RINEX_3_SYS_OBS_TYPES_HEADER",
                            "SPEC_SUPPORTED_HEADER_CONTINUATION",
                            StructuralState.CONTINUATION_SUPPORTED,
                        )
                    )
    return declarations, tuple(continuation_diagnostics)


def _parse_epoch(line: bytes) -> tuple[datetime, int, int]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        integer_second = int(second)
        microsecond = int(round((second - integer_second) * 1_000_000))
        if microsecond == 1_000_000:
            integer_second += 1
            microsecond = 0
        epoch = datetime(
            int(parts[1]),
            int(parts[2]),
            int(parts[3]),
            int(parts[4]),
            int(parts[5]),
            integer_second,
            microsecond,
            tzinfo=timezone.utc,
        )
        return epoch, int(parts[7]), int(parts[8])
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise StructuralQualificationError("INVALID_RINEX_EPOCH_RECORD") from exc


def _diagnostic(
    station: str,
    epoch: datetime | None,
    satellite: str | None,
    observable: str,
    index: int | None,
    field_count: int,
    source_line_class: str,
    continuation_class: str,
    state: StructuralState,
) -> dict[str, object]:
    return StructuralDiagnostic(
        station=station,
        gps_epoch=format_gps_epoch(epoch) if epoch is not None else None,
        satellite=satellite,
        required_observable=observable,
        header_declared_index=index,
        reconstructed_field_count=field_count,
        source_line_class=source_line_class,
        continuation_class=continuation_class,
        typed_structural_state=state.value,
    ).receipt()


def _scan_receipt(
    station: str,
    diagnostics: Iterable[dict[str, object]],
    records_examined: int,
) -> dict[str, object]:
    rows = list(diagnostics)
    failure_states = {
        StructuralState.FIELD_ABSENT.value,
        StructuralState.FIELD_BLANK.value,
        StructuralState.TRAILING_FIELD_OMITTED.value,
        StructuralState.CONTINUATION_UNSUPPORTED.value,
        StructuralState.RECORD_INVALID.value,
    }
    state = "STRUCTURE_REFUSED" if any(
        row["typed_structural_state"] in failure_states for row in rows
    ) else "STRUCTURE_QUALIFIED"
    receipt = {
        "schema": "gnss-value-blind-structural-scan-v1",
        "parser_version": PARSER_VERSION,
        "station": station,
        "state": state,
        "records_examined": records_examined,
        "diagnostics": rows,
        "observation_values_retained": 0,
        "orbital_scores_produced": 0,
    }
    strict_json(receipt)
    return receipt


def description_error_receipt(station: str, source_class: str) -> dict[str, object]:
    """Describe a receipt failure without converting it into physical refusal."""

    diagnostic = _diagnostic(
        station,
        None,
        None,
        "",
        None,
        0,
        source_class,
        "NOT_APPLICABLE",
        StructuralState.DESCRIPTION_ERROR,
    )
    receipt = {
        "schema": "gnss-value-blind-structural-description-error-v1",
        "station": station,
        "description_state": "DESCRIPTION_ERROR",
        "measurement_admission_state": "NOT_EVALUATED",
        "diagnostics": [diagnostic],
        "observation_values_retained": 0,
        "orbital_scores_produced": 0,
    }
    strict_json(receipt)
    return receipt


def parser_manifest() -> dict[str, object]:
    manifest = {
        "parser_version": PARSER_VERSION,
        "parent_terminal": list(PARENT_TERMINAL),
        "parent_outcome_sha256": PARENT_OUTCOME_SHA256,
        "artifact_roles": list(FORENSIC_ARTIFACT_ROLES),
        "rinex_specification": RINEX_SPECIFICATION,
        "diagnostic_keys": sorted(DIAGNOSTIC_KEYS),
        "structural_states": [state.value for state in StructuralState],
        "rinex_semantics": {
            "observation_record": "VARIABLE_LENGTH_SINGLE_LINE_NO_80_COLUMN_LIMIT",
            "trailing_empty_fields": "MAY_BE_OMITTED",
            "missing_observation": "ZERO_OR_BLANK",
            "header_observable_continuation": "SUPPORTED",
            "observation_data_continuation": "UNSUPPORTED_BY_RINEX_3_04_TABLE_A3",
        },
        "forbidden": [
            "observation scalar conversion",
            "observation value serialization",
            "orbital prediction",
            "orbital scoring",
            "primary reuse",
        ],
    }
    strict_json(manifest)
    return manifest


def parser_manifest_sha256() -> str:
    return sha256(strict_json(parser_manifest()).encode("ascii")).hexdigest()
