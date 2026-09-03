"""One-shot value-blind structural qualification of the frozen ALGO artifact.

The scanner observes RINEX framing, field occupancy and LLI characters only.
It never converts or persists an observation scalar.  GPS satellite labels are
used internally only to keep records joined; the independent structural
receipt exposes first-seen opaque track identifiers and is hashed before a
separate, non-independent PRN reveal is written.
"""

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


SCAN_VERSION: Final = "algo-doy229-all-track-structural-qualification-v1"
PLAN_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_PLAN.md"
SELECTION_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_SELECTION_RECEIPT.json"
COVERAGE_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_COVERAGE.jsonl"
STRUCTURE_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_STRUCTURE.json"
REVEAL_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_REVEAL.json"
OUTCOME_NAME: Final = "GNSS_ALL_TRACK_QUALIFICATION_OUTCOME.json"

STATION: Final = "ALGO00CAN"
PRODUCT_NAME: Final = "ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz"
PRODUCT_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/229/"
    "ALGO00CAN_R_20262290000_01D_30S_MO.crx.gz"
)
EXPECTED_COMPRESSED_BYTES: Final = 4_317_738
MAX_COMPRESSED_BYTES: Final = EXPECTED_COMPRESSED_BYTES
MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 60.0

STEP_S: Final = 30.0
WINDOW_START_GPS: Final = datetime(2026, 8, 17, 12, 49, 30, tzinfo=timezone.utc)
WINDOW_STOP_GPS: Final = datetime(2026, 8, 17, 13, 58, 30, tzinfo=timezone.utc)
EPOCH_COUNT: Final = 139
COMPLETE_TRACK_COUNT_REQUIRED: Final = 6
CORE_PHASE: Final = ("L1C", "L2W")
SAME_PATH_CODE: Final = ("C1C", "C2W")
RETAINED_OBSERVABLES: Final = CORE_PHASE + SAME_PATH_CODE
ORBIT_CODEBOOK: Final = frozenset(("G05", "G15", "G18", "G20", "G21", "G29"))

EXPECTED_RECEIVER_TYPE: Final = "SEPT POLARX5"
EXPECTED_RECEIVER_VERSION: Final = "5.3.2"
EXPECTED_ANTENNA_TYPE: Final = "AOAD/M_T"
EXPECTED_RADOME: Final = "NONE"


class StructuralRefusal(ValueError):
    """The readable product does not materialize the frozen topology."""


class DescriptionError(ValueError):
    """The product or receipt cannot be described; not a physical refusal."""


class MaterializationError(RuntimeError):
    """The complete exact artifact could not be obtained and identified."""


@dataclass(frozen=True, slots=True)
class ProductLocator:
    station: str = STATION
    name: str = PRODUCT_NAME
    url: str = PRODUCT_URL
    expected_bytes: int = EXPECTED_COMPRESSED_BYTES


@dataclass(slots=True)
class TrackState:
    opaque_id: str
    prn: str
    first_seen_index: int
    record_present: list[bool]
    core_valid: list[bool]
    code_present: dict[str, list[bool]]

    def erase(self) -> None:
        self.prn = ""
        self.record_present[:] = [False] * len(self.record_present)
        self.core_valid[:] = [False] * len(self.core_valid)
        for values in self.code_present.values():
            values[:] = [False] * len(values)


@dataclass(slots=True)
class StructuralScan:
    header: dict[str, object]
    coverage: list[dict[str, object]]
    issues: list[dict[str, object]]
    tracks: list[TrackState]
    epoch_valid: list[bool]

    def erase(self) -> None:
        for track in self.tracks:
            track.erase()
        self.epoch_valid[:] = [False] * len(self.epoch_valid)


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


def expected_epochs() -> tuple[datetime, ...]:
    result = tuple(
        WINDOW_START_GPS + timedelta(seconds=index * STEP_S)
        for index in range(EPOCH_COUNT)
    )
    if result[-1] != WINDOW_STOP_GPS:
        raise DescriptionError("FROZEN_WINDOW_GRID_CHANGED")
    return result


def _format_epoch(epoch: datetime) -> str:
    return epoch.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", " GPS"
    )


def _normalize(value: object) -> str:
    return " ".join(str(value).split())


def _read_strict_json(path: Path) -> dict[str, object]:
    def reject_constant(token: str) -> None:
        raise DescriptionError(f"NONFINITE_JSON_CONSTANT:{token}")

    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DescriptionError(f"SELECTION_RECEIPT_UNREADABLE:{type(exc).__name__}") from exc
    if not isinstance(value, dict):
        raise DescriptionError("SELECTION_RECEIPT_NOT_OBJECT")
    return value


def verify_frozen_selection(root: Path) -> dict[str, object]:
    plan = root / PLAN_NAME
    selection_path = root / SELECTION_NAME
    selection = _read_strict_json(selection_path)
    try:
        if selection["state"] != "QUALIFICATION_ARTIFACT_SELECTED_PAYLOAD_UNOPENED":
            raise DescriptionError("SELECTION_STATE_CHANGED")
        if selection["primary_selected"] is not False:
            raise DescriptionError("PRIMARY_ROLE_ALREADY_ASSIGNED")
        artifact = selection["artifact"]
        if artifact["name"] != PRODUCT_NAME or artifact["url"] != PRODUCT_URL:
            raise DescriptionError("PRODUCT_LOCATOR_CHANGED")
        if artifact["content_length_hint_bytes"] != EXPECTED_COMPRESSED_BYTES:
            raise DescriptionError("CONTENT_LENGTH_HINT_CHANGED")
        frozen_plan_hash = selection["plan"]["canonical_sha256"]
    except (KeyError, TypeError) as exc:
        raise DescriptionError("SELECTION_RECEIPT_SCHEMA_CHANGED") from exc
    if canonical_file_sha256(plan) != frozen_plan_hash:
        raise DescriptionError("QUALIFICATION_PLAN_HASH_CHANGED")
    return selection


def manifest() -> dict[str, object]:
    root = Path(__file__).resolve().parent
    result = {
        "scan_version": SCAN_VERSION,
        "plan_canonical_sha256": canonical_file_sha256(root / PLAN_NAME),
        "selection_receipt_canonical_sha256": canonical_file_sha256(
            root / SELECTION_NAME
        ),
        "product": asdict(ProductLocator()),
        "window_gps": {
            "start": _format_epoch(WINDOW_START_GPS),
            "stop": _format_epoch(WINDOW_STOP_GPS),
            "step_s": STEP_S,
            "epoch_count": EPOCH_COUNT,
        },
        "complete_track_count_required": COMPLETE_TRACK_COUNT_REQUIRED,
        "track_identity": "OPAQUE_FIRST_SEEN_ORDER_WITHIN_FROZEN_WINDOW",
        "core_phase": list(CORE_PHASE),
        "same_path_code_descriptive": list(SAME_PATH_CODE),
        "maximum_transport_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
        "post_complete_hash_retry": 0,
        "parser_boundary": (
            "RINEX_FRAMING_FIELD_OCCUPANCY_AND_LLI_CHARACTERS_ONLY_"
            "NO_OBSERVATION_SCALAR_CONVERSION"
        ),
        "forbidden": [
            "PRN filtering or PRN-conditioned membership",
            "observation scalar conversion or persistence",
            "Doppler or signal-strength field reads",
            "orbit prediction or orbital scoring",
            "primary or reserve selection",
            "compressed or decompressed observation persistence",
            "gap bridging or interpolation",
        ],
    }
    strict_json(result)
    return result


def manifest_sha256() -> str:
    return sha256(strict_json(manifest()).encode("ascii")).hexdigest()


def _read_header(stream: io.BytesIO) -> tuple[bytes, ...]:
    rows: list[bytes] = []
    for _ in range(headers.MAX_HEADER_LINES):
        line = stream.readline()
        if not line:
            raise DescriptionError("HEADER_INCOMPLETE")
        rows.append(line)
        body = line.rstrip(b"\r\n")
        label = (
            body[60:80].decode("ascii", errors="strict").strip()
            if len(body) >= 60
            else ""
        )
        if label == "END OF HEADER":
            return tuple(rows)
    raise DescriptionError("HEADER_LINE_LIMIT_EXCEEDED")


def _header_lineage(lines: Sequence[bytes], gps_types: Sequence[str]) -> dict[str, str]:
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
        raise DescriptionError("GPS_HEADER_LINEAGE_COUNT_CHANGED")
    return dict(zip(gps_types, classes, strict=True))


def _validate_header(parsed: dict[str, object], lines: Sequence[bytes]) -> dict[str, object]:
    try:
        receiver = parsed["receiver"]
        antenna = parsed["antenna"]
        gps_types = tuple(parsed["observable_types"].get("G", ()))
        first_record = parsed["time_of_first_observation"]
        last_record = parsed["time_of_last_observation"]
    except (KeyError, TypeError) as exc:
        raise DescriptionError("REQUIRED_HEADER_DESCRIPTION_MISSING") from exc
    if str(parsed["marker_name"]) != STATION[:4]:
        raise DescriptionError("MARKER_IDENTITY_MISMATCH")
    if float(parsed["interval_s"]) != STEP_S:
        raise DescriptionError("INTERVAL_CHANGED")
    first = headers.parse_utc(first_record["utc_like_epoch"])
    last = headers.parse_utc(last_record["utc_like_epoch"])
    if first_record["time_system"] != "GPS" or last_record["time_system"] != "GPS":
        raise DescriptionError("OBSERVATION_TIME_SYSTEM_NOT_GPS")
    if first > WINDOW_START_GPS or last < WINDOW_STOP_GPS:
        raise DescriptionError("FROZEN_WINDOW_NOT_COVERED")
    if _normalize(receiver["type"]) != EXPECTED_RECEIVER_TYPE:
        raise DescriptionError("RECEIVER_TYPE_CHANGED")
    if _normalize(receiver["version_or_radome"]) != EXPECTED_RECEIVER_VERSION:
        raise DescriptionError("RECEIVER_VERSION_CHANGED")
    if _normalize(antenna["type"]) != EXPECTED_ANTENNA_TYPE:
        raise DescriptionError("ANTENNA_TYPE_CHANGED")
    if _normalize(antenna["version_or_radome"]) != EXPECTED_RADOME:
        raise DescriptionError("ANTENNA_RADOME_CHANGED")
    missing = sorted(set(RETAINED_OBSERVABLES) - set(gps_types))
    if missing:
        raise DescriptionError(f"REQUIRED_GPS_OBSERVABLE_NOT_DECLARED:{','.join(missing)}")
    lineage = _header_lineage(lines, gps_types)
    return {
        "station": STATION,
        "marker_name": parsed["marker_name"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna["type"]),
        "antenna_radome": _normalize(antenna["version_or_radome"]),
        "interval_s": parsed["interval_s"],
        "time_of_first_observation": first_record,
        "time_of_last_observation": last_record,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "gps_observable_count": len(gps_types),
        "retained_observable_indices": {
            observable: gps_types.index(observable) for observable in RETAINED_OBSERVABLES
        },
        "retained_observable_header_lineage": {
            observable: lineage[observable] for observable in RETAINED_OBSERVABLES
        },
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


def _new_track(prn: str, row_index: int, ordinal: int) -> TrackState:
    return TrackState(
        opaque_id=f"T{ordinal:03d}",
        prn=prn,
        first_seen_index=row_index,
        record_present=[False] * EPOCH_COUNT,
        core_valid=[False] * EPOCH_COUNT,
        code_present={observable: [False] * EPOCH_COUNT for observable in SAME_PATH_CODE},
    )


def _coverage_row(
    *,
    epoch: datetime,
    event_flag: int | None,
    track: TrackState,
    observable: str,
    header_index: int,
    field_count: int,
    record_state: str,
    field_state: str,
    lli_state: str,
    source_line_class: str,
    header_line_class: str,
) -> dict[str, object]:
    result = {
        "station": STATION,
        "gps_epoch": _format_epoch(epoch),
        "event_flag": event_flag,
        "opaque_track": track.opaque_id,
        "record_state": record_state,
        "observable": observable,
        "physical_role": (
            "CORE_PHASE" if observable in CORE_PHASE else "SAME_PATH_CODE_WITNESS"
        ),
        "header_declared_index": header_index,
        "reconstructed_field_count": field_count,
        "source_line_class": source_line_class,
        "header_line_class": header_line_class,
        "continuation_class": "RINEX_3_SINGLE_LINE_RECORD",
        "state": field_state,
        "lli_state": lli_state,
    }
    strict_json(result)
    return result


def scan_decoded(decoded: bytearray) -> StructuralScan:
    """Scan all GPS records on the frozen grid without converting scalars."""

    stream = io.BytesIO(decoded)
    header_lines = _read_header(stream)
    try:
        parsed = headers.parse_header_lines(header_lines)
    except (headers.HeaderAdmissionError, UnicodeError, ValueError) as exc:
        raise DescriptionError(f"HEADER_DESCRIPTION_ERROR:{exc}") from exc
    header = _validate_header(parsed, header_lines)
    gps_types = tuple(parsed["observable_types"]["G"])
    indices = {observable: gps_types.index(observable) for observable in RETAINED_OBSERVABLES}
    lineage = _header_lineage(header_lines, gps_types)
    epochs = expected_epochs()
    epoch_index = {epoch: index for index, epoch in enumerate(epochs)}
    epoch_flags: list[int | None] = [None] * EPOCH_COUNT
    epoch_valid = [False] * EPOCH_COUNT
    tracks_by_prn: dict[str, TrackState] = {}
    tracks: list[TrackState] = []
    observed_rows: dict[tuple[str, int, str], dict[str, object]] = {}
    issues: list[dict[str, object]] = []

    while True:
        line = stream.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                issues.append({"state": "RECORD_INVALID", "reason": "NON_EPOCH_SOURCE_LINE"})
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        if epoch > WINDOW_STOP_GPS:
            break
        row_index = epoch_index.get(epoch)
        in_window = WINDOW_START_GPS <= epoch <= WINDOW_STOP_GPS
        if in_window and row_index is None:
            issues.append({
                "state": "RECORD_INVALID",
                "reason": "OFF_GRID_EPOCH",
                "gps_epoch": _format_epoch(epoch),
            })
        if row_index is not None:
            if epoch_flags[row_index] is not None:
                issues.append({
                    "state": "RECORD_INVALID",
                    "reason": "DUPLICATE_EPOCH",
                    "gps_epoch": _format_epoch(epoch),
                })
            epoch_flags[row_index] = flag
            epoch_valid[row_index] = flag == 0
            if flag != 0:
                issues.append({
                    "state": "RECORD_INVALID",
                    "reason": f"EPOCH_FLAG_NOT_ZERO_{flag}",
                    "gps_epoch": _format_epoch(epoch),
                })
        if flag not in (0, 1):
            for _ in range(satellite_count):
                if not stream.readline():
                    issues.append({
                        "state": "RECORD_INVALID",
                        "reason": "TRUNCATED_SPECIAL_EVENT_RECORD",
                        "gps_epoch": _format_epoch(epoch),
                    })
                    break
            continue
        for _ in range(satellite_count):
            record = stream.readline()
            if not record:
                issues.append({
                    "state": "RECORD_INVALID",
                    "reason": "TRUNCATED_SATELLITE_RECORD",
                    "gps_epoch": _format_epoch(epoch),
                })
                break
            valid_prefix = len(record) >= 3 and record[:1].isalpha() and record[1:3].isdigit()
            if not valid_prefix:
                issues.append({
                    "state": "CONTINUATION_UNSUPPORTED" if record.startswith(b"   ") else "RECORD_INVALID",
                    "reason": "NONSTANDARD_DATA_CONTINUATION" if record.startswith(b"   ") else "INVALID_SATELLITE_RECORD",
                    "gps_epoch": _format_epoch(epoch),
                })
                continue
            prn = record[:3].decode("ascii", errors="strict")
            if row_index is None or not prn.startswith("G"):
                continue
            track = tracks_by_prn.get(prn)
            if track is None:
                track = _new_track(prn, row_index, len(tracks) + 1)
                tracks_by_prn[prn] = track
                tracks.append(track)
            if track.record_present[row_index]:
                issues.append({
                    "state": "RECORD_INVALID",
                    "reason": "DUPLICATE_OPAQUE_TRACK_RECORD",
                    "gps_epoch": _format_epoch(epoch),
                    "opaque_track": track.opaque_id,
                })
                continue
            track.record_present[row_index] = True
            payload = record[3:].rstrip(b"\r\n")
            field_count = (len(payload) + 15) // 16
            if field_count > len(gps_types):
                issues.append({
                    "state": "RECORD_INVALID",
                    "reason": "FIELD_COUNT_OVERFLOW",
                    "gps_epoch": _format_epoch(epoch),
                    "opaque_track": track.opaque_id,
                })
            padded = payload.ljust(field_count * 16, b" ")
            fields = tuple(padded[offset : offset + 16] for offset in range(0, len(padded), 16))
            core_states: list[bool] = []
            for observable in RETAINED_OBSERVABLES:
                header_index = indices[observable]
                if header_index >= field_count:
                    state = "TRAILING_FIELD_OMITTED"
                    lli_state = "NOT_APPLICABLE"
                else:
                    field = fields[header_index]
                    state = "PRESENT" if field[:14].strip() else "BLANK"
                    lli_state = (
                        _lli(field)
                        if observable in CORE_PHASE and state == "PRESENT"
                        else "NOT_APPLICABLE"
                    )
                row = _coverage_row(
                    epoch=epoch,
                    event_flag=flag,
                    track=track,
                    observable=observable,
                    header_index=header_index,
                    field_count=field_count,
                    record_state="PRESENT",
                    field_state=state,
                    lli_state=lli_state,
                    source_line_class="RINEX_3_OBSERVATION_DATA_RECORD",
                    header_line_class=lineage[observable],
                )
                observed_rows[(track.opaque_id, row_index, observable)] = row
                if observable in CORE_PHASE:
                    core_states.append(
                        state == "PRESENT" and lli_state == "ZERO_OR_BLANK" and flag == 0
                    )
                else:
                    track.code_present[observable][row_index] = state == "PRESENT"
            track.core_valid[row_index] = all(core_states)

    coverage: list[dict[str, object]] = []
    for row_index, epoch in enumerate(epochs):
        for track in tracks:
            for observable in RETAINED_OBSERVABLES:
                key = (track.opaque_id, row_index, observable)
                row = observed_rows.get(key)
                if row is None:
                    row = _coverage_row(
                        epoch=epoch,
                        event_flag=epoch_flags[row_index],
                        track=track,
                        observable=observable,
                        header_index=indices[observable],
                        field_count=0,
                        record_state="ABSENT",
                        field_state="FIELD_ABSENT",
                        lli_state="NOT_APPLICABLE",
                        source_line_class=(
                            "GPS_RECORD_ABSENT" if epoch_flags[row_index] == 0
                            else "EPOCH_ABSENT_OR_NONOBSERVATION"
                        ),
                        header_line_class=lineage[observable],
                    )
                coverage.append(row)
    expected_rows = EPOCH_COUNT * len(tracks) * len(RETAINED_OBSERVABLES)
    if len(coverage) != expected_rows:
        raise DescriptionError(f"COVERAGE_ROW_COUNT_CHANGED:{len(coverage)}:{expected_rows}")
    return StructuralScan(header, coverage, issues, tracks, epoch_valid)


def _segments(valid: Sequence[bool]) -> list[dict[str, object]]:
    epochs = expected_epochs()
    result: list[dict[str, object]] = []
    start: int | None = None
    for index, present in enumerate(list(valid) + [False]):
        if present and start is None:
            start = index
        elif not present and start is not None:
            stop = index - 1
            result.append({
                "start_gps": _format_epoch(epochs[start]),
                "stop_gps": _format_epoch(epochs[stop]),
                "epoch_count": stop - start + 1,
                "duration_s": (stop - start) * STEP_S,
            })
            start = None
    return result


def evaluate(scan: StructuralScan) -> dict[str, object]:
    complete_tracks = [track for track in scan.tracks if all(track.core_valid)]
    track_summaries = []
    code_summaries = []
    for track in scan.tracks:
        track_summaries.append({
            "opaque_track": track.opaque_id,
            "first_seen_grid_index": track.first_seen_index,
            "record_present_epochs": sum(track.record_present),
            "core_valid_epochs": sum(track.core_valid),
            "maximal_core_segments": _segments(track.core_valid),
            "complete_frozen_window": all(track.core_valid),
        })
        for observable in SAME_PATH_CODE:
            present = track.code_present[observable]
            code_summaries.append({
                "opaque_track": track.opaque_id,
                "observable": observable,
                "present_epochs": sum(present),
                "total_epochs": EPOCH_COUNT,
                "coverage_fraction": sum(present) / EPOCH_COUNT,
                "role": "DESCRIPTIVE_NOT_FATAL",
            })
    epoch_grid_complete = all(scan.epoch_valid)
    count_satisfied = len(complete_tracks) == COMPLETE_TRACK_COUNT_REQUIRED
    passed = epoch_grid_complete and not scan.issues and count_satisfied
    outcome = (
        "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_PASSED"
        if passed
        else "GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED"
    )
    result = {
        "schema": "gnss-all-track-qualification-structure-v1",
        "outcome": outcome,
        "station": STATION,
        "header": scan.header,
        "window": manifest()["window_gps"],
        "epoch_grid_complete": epoch_grid_complete,
        "epoch_present_count": sum(scan.epoch_valid),
        "gps_tracks_seen": len(scan.tracks),
        "complete_track_count": len(complete_tracks),
        "complete_track_count_required": COMPLETE_TRACK_COUNT_REQUIRED,
        "complete_opaque_tracks": [track.opaque_id for track in complete_tracks],
        "count_clause": "SATISFIED" if count_satisfied else "UNSATISFIED",
        "parser_issues": scan.issues,
        "structural_state_counts": dict(
            sorted(Counter(row["state"] for row in scan.coverage).items())
        ),
        "track_summaries": track_summaries,
        "same_path_code_witness": {
            "state": "DESCRIPTIVE_NOT_ADMISSION_CLAUSE",
            "tracks": code_summaries,
        },
        "prn_identity": "SEALED_UNTIL_THIS_RECEIPT_IS_HASHED",
        "measurement_admission": "NOT_EVALUATED",
        "orbital_score": "NOT_EVALUATED",
        "primary_selection": "NOT_EVALUATED",
        "observation_values_parsed": 0,
        "observation_values_persisted": 0,
        "observation_artifact_bytes_persisted": 0,
    }
    strict_json(result)
    return result


def reveal_after_structural_hash(
    scan: StructuralScan, structural_sha256: str
) -> dict[str, object]:
    mapping = [
        {"opaque_track": track.opaque_id, "receiver_prn": track.prn}
        for track in scan.tracks
    ]
    complete_prns = {
        track.prn for track in scan.tracks if all(track.core_valid)
    }
    result = {
        "schema": "gnss-all-track-qualification-reveal-v1",
        "authority": "NON_INDEPENDENT_DESCRIPTIVE_WITNESS_ONLY",
        "structural_receipt_sha256_before_reveal": structural_sha256,
        "mapping": mapping,
        "complete_receiver_prns": sorted(complete_prns),
        "orbit_codebook": sorted(ORBIT_CODEBOOK),
        "codebook_relation": (
            "CONCORDANT" if complete_prns == ORBIT_CODEBOOK else "DISCORDANT"
        ),
        "membership_changed_by_reveal": False,
        "qualification_rescued_by_reveal": False,
        "orbital_score": "NOT_EVALUATED",
    }
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
                response_length = response.headers.get("Content-Length")
                etag = response.headers.get("ETag")
                last_modified = response.headers.get("Last-Modified")
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    payload.extend(block)
                    if len(payload) > MAX_COMPRESSED_BYTES:
                        observed_bytes = len(payload)
                        payload[:] = b"\x00" * observed_bytes
                        raise MaterializationError("COMPRESSED_SIZE_LIMIT_EXCEEDED")
            if not payload:
                raise MaterializationError("EMPTY_ARTIFACT")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            payload[:] = b"\x00" * len(payload)
            failures.append(f"{type(exc).__name__}:{exc}")
            continue
        complete_sha256 = sha256(payload).hexdigest()
        if len(payload) != locator.expected_bytes:
            payload[:] = b"\x00" * len(payload)
            raise MaterializationError(
                f"COMPLETE_FILE_BYTE_COUNT_CHANGED:{len(payload)}:{locator.expected_bytes}"
            )
        return payload, {
            "station": locator.station,
            "product": locator.name,
            "url": locator.url,
            "attempts": attempt,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": complete_sha256,
            "hash_completed_before_decompression": True,
            "response_content_length": response_length,
            "response_etag": etag,
            "response_last_modified": last_modified,
        }
    raise MaterializationError("ARTIFACT_MATERIALIZATION_FAILED:" + "|".join(failures))


def _decompress(payload: bytearray) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise DescriptionError("HATANAKA_DECOMPRESSION_FAILED") from exc


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def _write_json(path: Path, value: object) -> None:
    path.write_text(strict_json(value, pretty=True) + "\n", encoding="utf-8", newline="\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.write_text(
        "".join(strict_json(row) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def _failure_outcome(outcome: str, reason: str) -> dict[str, object]:
    result = {
        "schema": "gnss-all-track-qualification-outcome-v1",
        "outcome": outcome,
        "reason": reason,
        "structure": "NOT_EVALUATED",
        "measurement_admission": "NOT_EVALUATED",
        "orbital_score": "NOT_EVALUATED",
        "primary_selection": "NOT_EVALUATED",
        "observation_values_parsed": 0,
        "observation_values_persisted": 0,
        "observation_artifact_bytes_persisted": 0,
    }
    strict_json(result)
    return result


def run_once(output_directory: Path) -> dict[str, object]:
    directory = Path(output_directory)
    outcome_path = directory / OUTCOME_NAME
    if outcome_path.exists():
        raise DescriptionError("QUALIFICATION_EXECUTION_ALREADY_RECORDED")
    verify_frozen_selection(Path(__file__).resolve().parent)
    compressed = bytearray()
    decoded = bytearray()
    scan: StructuralScan | None = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materialize(ProductLocator())
        decoded = _decompress(compressed)
        scan = scan_decoded(decoded)
        structure = evaluate(scan)
        _write_jsonl(directory / COVERAGE_NAME, scan.coverage)
        coverage_sha = canonical_file_sha256(directory / COVERAGE_NAME)
        structure["coverage"] = {
            "name": COVERAGE_NAME,
            "rows": len(scan.coverage),
            "sha256": coverage_sha,
        }
        _write_json(directory / STRUCTURE_NAME, structure)
        structural_sha = canonical_file_sha256(directory / STRUCTURE_NAME)
        reveal = reveal_after_structural_hash(scan, structural_sha)
        _write_json(directory / REVEAL_NAME, reveal)
        reveal_sha = canonical_file_sha256(directory / REVEAL_NAME)
        outcome = {
            "schema": "gnss-all-track-qualification-outcome-v1",
            "outcome": structure["outcome"],
            "source_commit": _git_commit(),
            "source_sha256": source_sha256(),
            "manifest_sha256": manifest_sha256(),
            "artifact": artifact,
            "structure": {"name": STRUCTURE_NAME, "sha256": structural_sha},
            "coverage": {"name": COVERAGE_NAME, "sha256": coverage_sha},
            "reveal": {
                "name": REVEAL_NAME,
                "sha256": reveal_sha,
                "created_after_structural_hash": True,
                "membership_changed": False,
            },
            "clause_states": {
                "header_description": "SATISFIED",
                "complete_grid": "SATISFIED" if structure["epoch_grid_complete"] else "UNSATISFIED",
                "exact_six_complete_tracks": structure["count_clause"],
                "same_path_code": "DESCRIPTIVE_NOT_ADMISSION_CLAUSE",
                "measurement_admission": "NOT_EVALUATED",
                "orbital_score": "NOT_EVALUATED",
                "primary_selection": "NOT_EVALUATED",
            },
            "persistence": {
                "compressed_artifact_bytes": 0,
                "decompressed_observation_bytes": 0,
                "observation_values": 0,
                "structural_receipts_only": True,
            },
        }
        _write_json(outcome_path, outcome)
        return outcome
    except MaterializationError as exc:
        outcome = _failure_outcome("QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED", str(exc))
        _write_json(outcome_path, outcome)
        return outcome
    except StructuralRefusal as exc:
        outcome = _failure_outcome("GNSS_ALL_TRACK_STRUCTURAL_QUALIFICATION_FAILED", str(exc))
        outcome["structure"] = "UNSATISFIED"
        if artifact is not None:
            outcome["artifact"] = artifact
        _write_json(outcome_path, outcome)
        return outcome
    except DescriptionError as exc:
        outcome = _failure_outcome("QUALIFICATION_DESCRIPTION_ERROR", str(exc))
        if artifact is not None:
            outcome["artifact"] = artifact
        _write_json(outcome_path, outcome)
        return outcome
    except Exception as exc:
        outcome = _failure_outcome(
            "QUALIFICATION_DESCRIPTION_ERROR", f"{type(exc).__name__}:{exc}"
        )
        if artifact is not None:
            outcome["artifact"] = artifact
        _write_json(outcome_path, outcome)
        return outcome
    finally:
        if scan is not None:
            scan.erase()
        decoded[:] = b"\x00" * len(decoded)
        compressed[:] = b"\x00" * len(compressed)
        gc.collect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-authorized", action="store_true")
    parser.add_argument(
        "--output-directory", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    if not args.execute_authorized:
        raise SystemExit("EXPLICIT_QUALIFICATION_AUTHORITY_REQUIRED")
    print(strict_json(run_once(args.output_directory)))


if __name__ == "__main__":
    main()
