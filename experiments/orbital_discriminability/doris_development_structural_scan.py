"""Value-blind structural scan of one exact DORIS development product.

Only epoch time, station identity, record shape, and L1/L2/C1/C2 flag state
are represented.  The 14-character numerical portion of every observation
slot is checked only for blank/non-blank state and is never converted, stored,
or included in a receipt.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import ceil
from pathlib import Path
import subprocess
from typing import Callable, Final, Mapping

from experiments.live_instrument.models import strict_json_value
from experiments.orbital_discriminability import doris_development_header as header


SCANNER_VERSION: Final = "doris-development-structural-scan-v1"
EXPECTED_HEADER_SHA256: Final = (
    "47311d675dc0130a42676e423827bd63a4ac3b9083664c52741f5f75d185012a"
)
MAX_STATION_SAMPLE_GAP_S: Final = 10.0
CADENCE_TOLERANCE_S: Final = 1.0e-6
OBSERVABLE_COUNT: Final = 10
FIELDS_PER_LINE: Final = 5
FIELD_WIDTH: Final = 16
MAX_STREAM_LINES: Final = 2_000_000
ALLOWED_FLAG_BYTES: Final = frozenset(b" 0123456789")


@dataclass(frozen=True, slots=True)
class PairRule:
    left_code: str
    left_id: str
    right_code: str
    right_id: str
    minimum_duration_s: float

    @property
    def name(self) -> str:
        return f"{self.left_code}-{self.right_code}"


PAIR_RULES: Final = (
    PairRule("TLSB", "D49", "WEUC", "D47", 430.0),
    PairRule("PAUB", "D46", "RIMC", "D40", 480.0),
)


@dataclass(frozen=True, slots=True)
class FieldShape:
    present: bool
    flag1: str
    flag2: str


@dataclass(frozen=True, slots=True)
class StationShape:
    station_id: str
    l1: FieldShape
    l2: FieldShape
    c1: FieldShape
    c2: FieldShape


@dataclass(slots=True)
class SegmentAccumulator:
    start: datetime | None = None
    last: datetime | None = None
    count: int = 0

    def add(self, epoch: datetime) -> None:
        if self.start is None:
            self.start = epoch
        self.last = epoch
        self.count += 1

    def clear(self) -> None:
        self.start = None
        self.last = None
        self.count = 0


class DorisStructuralError(ValueError):
    """The development stream violates the frozen structural contract."""


def _flag_character(raw: bytes) -> str:
    if len(raw) != 1 or raw[0] not in ALLOWED_FLAG_BYTES:
        raise DorisStructuralError("STRUCTURAL_INVALID_OBSERVATION_FLAG")
    return raw.decode("ascii").strip()


def _field_shape(slot: bytes) -> FieldShape:
    if len(slot) != FIELD_WIDTH:
        raise DorisStructuralError("STRUCTURAL_INVALID_FIELD_WIDTH")
    return FieldShape(
        present=bool(slot[:14].strip()),
        flag1=_flag_character(slot[14:15]),
        flag2=_flag_character(slot[15:16]),
    )


def _leading_tokens(raw_line: bytes, count: int) -> tuple[bytes, ...]:
    """Return exactly ``count`` tokens without representing the line suffix."""

    tokens: list[bytes] = []
    index = 0
    whitespace = b" \t\r\n"
    while len(tokens) < count:
        while index < len(raw_line) and raw_line[index : index + 1] in whitespace:
            index += 1
        start = index
        while index < len(raw_line) and raw_line[index : index + 1] not in whitespace:
            index += 1
        if start == index:
            raise DorisStructuralError("STRUCTURAL_EPOCH_PREFIX_TOO_SHORT")
        tokens.append(raw_line[start:index])
    return tuple(tokens)


def _parse_epoch_prefix(raw_line: bytes) -> tuple[datetime, int, int]:
    if not raw_line.startswith(b">"):
        raise DorisStructuralError("STRUCTURAL_EPOCH_RECORD_EXPECTED")
    try:
        # DORIS files in the family use more second decimals than the generic
        # RINEX example.  Consume exactly the nine structural tokens and never
        # tokenize the optional receiver clock / oscillator suffix.
        prefix = [
            token.decode("ascii", errors="strict")
            for token in _leading_tokens(raw_line, 9)
        ]
        if len(prefix) != 9 or prefix[0] != ">":
            raise ValueError
        year, month, day, hour, minute = (int(value) for value in prefix[1:6])
        second = float(prefix[6])
        epoch_flag = int(prefix[7])
        record_count = int(prefix[8])
    except (UnicodeDecodeError, ValueError) as error:
        raise DorisStructuralError("STRUCTURAL_INVALID_EPOCH_PREFIX") from error
    whole_second = int(second)
    epoch = datetime(
        year,
        month,
        day,
        hour,
        minute,
        whole_second,
        round((second - whole_second) * 1_000_000),
        tzinfo=timezone.utc,
    )
    if record_count < 0 or record_count > 99:
        raise DorisStructuralError("STRUCTURAL_INVALID_EPOCH_RECORD_COUNT")
    return epoch, epoch_flag, record_count


def _record_fields(lines: list[bytes], station_id: str) -> list[FieldShape]:
    fields: list[FieldShape] = []
    for line_index, raw_line in enumerate(lines):
        body = raw_line.rstrip(b"\r\n")
        if line_index == 0:
            if body[:3].decode("ascii", errors="strict") != station_id:
                raise DorisStructuralError("STRUCTURAL_STATION_ID_CHANGED")
        elif body[:3].strip():
            raise DorisStructuralError("STRUCTURAL_CONTINUATION_PREFIX_NONBLANK")
        padded = body.ljust(3 + FIELDS_PER_LINE * FIELD_WIDTH, b" ")
        for field_index in range(FIELDS_PER_LINE):
            start = 3 + field_index * FIELD_WIDTH
            fields.append(_field_shape(padded[start : start + FIELD_WIDTH]))
    if len(fields) != OBSERVABLE_COUNT:
        raise DorisStructuralError("STRUCTURAL_OBSERVABLE_COUNT_MISMATCH")
    return fields


def _read_station_shape(next_line: Callable[[], bytes]) -> StationShape:
    first = next_line()
    body = first.rstrip(b"\r\n")
    if len(body) < 3:
        raise DorisStructuralError("STRUCTURAL_SHORT_STATION_RECORD")
    try:
        station_id = body[:3].decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise DorisStructuralError("STRUCTURAL_NON_ASCII_STATION_ID") from error
    if len(station_id) != 3 or not station_id.startswith("D") or not station_id[1:].isdigit():
        raise DorisStructuralError("STRUCTURAL_INVALID_STATION_ID")
    line_count = ceil(OBSERVABLE_COUNT / FIELDS_PER_LINE)
    lines = [first]
    for _ in range(line_count - 1):
        lines.append(next_line())
    fields = _record_fields(lines, station_id)
    return StationShape(
        station_id=station_id,
        l1=fields[0],
        l2=fields[1],
        c1=fields[2],
        c2=fields[3],
    )


def _phase_valid(shape: StationShape) -> tuple[bool, str]:
    if not shape.l1.present or not shape.l2.present:
        return False, "CORE_PHASE_ABSENT"
    if shape.l1.flag1 not in {"", "0", "1"} or shape.l2.flag1 not in {
        "",
        "0",
        "1",
    }:
        return False, "PHASE_CENTRAL_FREQUENCY_FLAG_UNSUPPORTED"
    if shape.l1.flag2 not in {"", "0"} or shape.l2.flag2 not in {"", "0"}:
        return False, "PHASE_DISCONTINUITY"
    return True, "VALID"


def _code_witness_valid(shape: StationShape) -> tuple[bool, str]:
    if not shape.c1.present or not shape.c2.present:
        return False, "CODE_WITNESS_ABSENT"
    if shape.c1.flag1 not in {"", "0"} or shape.c2.flag1 not in {"", "0"}:
        return False, "CODE_VALIDITY_FLAG_NONZERO"
    return True, "VALID"


def _segment_receipt(segment: SegmentAccumulator) -> dict[str, object]:
    if segment.start is None or segment.last is None or segment.count == 0:
        raise DorisStructuralError("STRUCTURAL_EMPTY_SEGMENT")
    return {
        "start_dor": segment.start.isoformat(),
        "end_dor": segment.last.isoformat(),
        "epoch_count": segment.count,
        "duration_s": (segment.last - segment.start).total_seconds(),
    }


def _finish_segment(
    accumulator: SegmentAccumulator, destination: list[dict[str, object]]
) -> None:
    if accumulator.count:
        destination.append(_segment_receipt(accumulator))
        accumulator.clear()


def _target_station_ids() -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            station_id
            for rule in PAIR_RULES
            for station_id in (rule.left_id, rule.right_id)
        )
    )


def _new_station_state() -> dict[str, object]:
    return {
        "core_current": SegmentAccumulator(),
        "witness_current": SegmentAccumulator(),
        "core_segments": [],
        "witness_segments": [],
        "core_break_reasons": Counter(),
        "witness_break_reasons": Counter(),
        "flag_counts": Counter(),
        "cadence_delta_counts": Counter(),
        "last_observed_epoch": None,
        "record_count": 0,
    }


def _finish_station_state(state: dict[str, object], reason: str) -> None:
    _finish_segment(state["core_current"], state["core_segments"])
    _finish_segment(state["witness_current"], state["witness_segments"])
    state["core_break_reasons"][reason] += 1
    state["witness_break_reasons"][reason] += 1


def _segment_overlaps(
    left_segments: list[dict[str, object]],
    right_segments: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Intersect independently sampled station coverage without interpolation."""

    left_ordered = sorted(left_segments, key=lambda row: row["start_dor"])
    right_ordered = sorted(right_segments, key=lambda row: row["start_dor"])
    overlaps: list[dict[str, object]] = []
    left_index = 0
    right_index = 0
    while left_index < len(left_ordered) and right_index < len(right_ordered):
        left = left_ordered[left_index]
        right = right_ordered[right_index]
        left_start = datetime.fromisoformat(str(left["start_dor"]))
        left_end = datetime.fromisoformat(str(left["end_dor"]))
        right_start = datetime.fromisoformat(str(right["start_dor"]))
        right_end = datetime.fromisoformat(str(right["end_dor"]))
        start = max(left_start, right_start)
        end = min(left_end, right_end)
        if end >= start:
            overlaps.append(
                {
                    "start_dor": start.isoformat(),
                    "end_dor": end.isoformat(),
                    "duration_s": (end - start).total_seconds(),
                    "left_epoch_count": left["epoch_count"],
                    "right_epoch_count": right["epoch_count"],
                    "sample_alignment": "INDEPENDENT_STATION_GRIDS_NO_INTERPOLATION",
                }
            )
        if left_end <= right_end:
            left_index += 1
        else:
            right_index += 1
    return overlaps


def scan_exact_development_structure(
    path: Path,
    *,
    authority: header.ProductAuthority = header.DEVELOPMENT_AUTHORITY,
    expected_header_sha256: str = EXPECTED_HEADER_SHA256,
    gzip_executable: str | None = None,
) -> dict[str, object]:
    """Scan the full exact stream while retaining no observation magnitude."""

    path = Path(path)
    header.validate_artifact(path, authority)
    command = [header.resolve_gzip(gzip_executable), "-dc", str(path)]
    process = subprocess.Popen(  # noqa: S603 - exact local executable and file
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise DorisStructuralError("STRUCTURAL_GZIP_PIPE_UNAVAILABLE")

    digest = sha256()
    decompressed_bytes = 0
    line_count = 0

    def next_line() -> bytes:
        nonlocal decompressed_bytes, line_count
        raw_line = process.stdout.readline()
        if not raw_line:
            raise DorisStructuralError("STRUCTURAL_UNEXPECTED_END_OF_STREAM")
        digest.update(raw_line)
        decompressed_bytes += len(raw_line)
        line_count += 1
        if line_count > MAX_STREAM_LINES:
            raise DorisStructuralError("STRUCTURAL_STREAM_LINE_LIMIT_EXCEEDED")
        return raw_line

    target_station_ids = _target_station_ids()
    station_state = {
        station_id: _new_station_state() for station_id in target_station_ids
    }
    header_lines: list[bytes] = []
    epoch_count = 0
    special_event_epoch_count = 0
    power_failure_epoch_count = 0
    station_record_count = 0
    continuation_line_count = 0
    previous_epoch: datetime | None = None
    first_epoch: datetime | None = None
    last_epoch: datetime | None = None
    cadence_counts: Counter[str] = Counter()
    completed = False
    try:
        while True:
            raw_line = next_line()
            header_lines.append(raw_line)
            if header.header_label(raw_line) == "END OF HEADER":
                break
        raw_header = b"".join(header_lines)
        if sha256(raw_header).hexdigest() != expected_header_sha256:
            raise DorisStructuralError("STRUCTURAL_FROZEN_HEADER_SHA256_CHANGED")
        header_lines.clear()

        while True:
            raw_line = process.stdout.readline()
            if not raw_line:
                completed = True
                break
            digest.update(raw_line)
            decompressed_bytes += len(raw_line)
            line_count += 1
            if line_count > MAX_STREAM_LINES:
                raise DorisStructuralError("STRUCTURAL_STREAM_LINE_LIMIT_EXCEEDED")
            epoch, epoch_flag, record_count = _parse_epoch_prefix(raw_line)
            if first_epoch is None:
                first_epoch = epoch
            last_epoch = epoch
            epoch_count += 1
            if previous_epoch is not None:
                delta = (epoch - previous_epoch).total_seconds()
                cadence_counts[f"{delta:.6f}"] += 1
            previous_epoch = epoch

            if epoch_flag not in {0, 1}:
                special_event_epoch_count += 1
                for _ in range(record_count):
                    next_line()
                for state in station_state.values():
                    _finish_station_state(state, "SPECIAL_EPOCH_FLAG")
                continue

            if epoch_flag == 1:
                power_failure_epoch_count += 1
                for state in station_state.values():
                    _finish_station_state(state, "EPOCH_FLAG_1_POWER_FAILURE")

            epoch_shapes: dict[str, StationShape] = {}
            for _ in range(record_count):
                station_shape = _read_station_shape(next_line)
                continuation_line_count += ceil(OBSERVABLE_COUNT / FIELDS_PER_LINE) - 1
                station_record_count += 1
                if station_shape.station_id in target_station_ids:
                    if station_shape.station_id in epoch_shapes:
                        raise DorisStructuralError(
                            "STRUCTURAL_DUPLICATE_STATION_IN_EPOCH"
                        )
                    epoch_shapes[station_shape.station_id] = station_shape

            # Other stations' interleaved epochs do not break a target
            # station's own phase-continuity chain.  Each target stream is
            # qualified independently and pair coverage is intersected later.
            for station_id, shape in epoch_shapes.items():
                state = station_state[station_id]
                state["record_count"] += 1
                for name, field in (
                    ("L1", shape.l1),
                    ("L2", shape.l2),
                    ("C1", shape.c1),
                    ("C2", shape.c2),
                ):
                    state["flag_counts"][f"{name}_FLAG1_{field.flag1 or 'BLANK'}"] += 1
                    state["flag_counts"][f"{name}_FLAG2_{field.flag2 or 'BLANK'}"] += 1
                previous_station_epoch = state["last_observed_epoch"]
                if previous_station_epoch is not None:
                    delta = (epoch - previous_station_epoch).total_seconds()
                    state["cadence_delta_counts"][f"{delta:.6f}"] += 1
                    consecutive = (
                        delta > 0.0
                        and delta
                        <= MAX_STATION_SAMPLE_GAP_S + CADENCE_TOLERANCE_S
                    )
                else:
                    consecutive = True
                state["last_observed_epoch"] = epoch
                if not consecutive:
                    _finish_segment(state["core_current"], state["core_segments"])
                    _finish_segment(
                        state["witness_current"], state["witness_segments"]
                    )
                    state["core_break_reasons"][
                        "STATION_SAMPLE_GAP_EXCEEDED"
                    ] += 1
                    state["witness_break_reasons"][
                        "STATION_SAMPLE_GAP_EXCEEDED"
                    ] += 1
                phase_valid, phase_reason = _phase_valid(shape)
                code_valid, code_reason = _code_witness_valid(shape)
                if phase_valid:
                    state["core_current"].add(epoch)
                else:
                    _finish_segment(state["core_current"], state["core_segments"])
                    state["core_break_reasons"][phase_reason] += 1
                if phase_valid and code_valid:
                    state["witness_current"].add(epoch)
                else:
                    _finish_segment(
                        state["witness_current"], state["witness_segments"]
                    )
                    witness_reason = phase_reason if not phase_valid else code_reason
                    state["witness_break_reasons"][witness_reason] += 1
    finally:
        process.stdout.close()
        if process.poll() is None:
            if completed:
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=5.0)
            else:
                process.terminate()
                process.wait(timeout=5.0)
        stderr = process.stderr.read()
        process.stderr.close()

    if not completed:
        raise DorisStructuralError("STRUCTURAL_SCAN_DID_NOT_REACH_STREAM_END")
    if process.returncode != 0:
        raise DorisStructuralError(
            f"STRUCTURAL_GZIP_FAILED:{stderr.decode('ascii', errors='replace').strip()}"
        )
    for state in station_state.values():
        _finish_segment(state["core_current"], state["core_segments"])
        _finish_segment(state["witness_current"], state["witness_segments"])
    if first_epoch is None or last_epoch is None:
        raise DorisStructuralError("STRUCTURAL_NO_EPOCHS")

    pair_receipts: list[dict[str, object]] = []
    any_pair_admitted = False
    for rule in PAIR_RULES:
        left_state = station_state[rule.left_id]
        right_state = station_state[rule.right_id]
        core_overlaps = sorted(
            _segment_overlaps(
                left_state["core_segments"], right_state["core_segments"]
            ),
            key=lambda row: row["duration_s"],
            reverse=True,
        )
        witness_overlaps = sorted(
            _segment_overlaps(
                left_state["witness_segments"], right_state["witness_segments"]
            ),
            key=lambda row: row["duration_s"],
            reverse=True,
        )
        maximum_core = core_overlaps[0]["duration_s"] if core_overlaps else 0.0
        maximum_witness = (
            witness_overlaps[0]["duration_s"] if witness_overlaps else 0.0
        )
        admitted = maximum_witness >= rule.minimum_duration_s
        any_pair_admitted = any_pair_admitted or admitted
        pair_receipts.append(
            {
                "pair": [rule.left_code, rule.right_code],
                "station_ids": [rule.left_id, rule.right_id],
                "minimum_required_duration_s": rule.minimum_duration_s,
                "maximum_core_phase_segment_s": maximum_core,
                "maximum_same_path_witnessed_segment_s": maximum_witness,
                "structurally_admitted": admitted,
                "longest_joint_core_coverage": core_overlaps[:5],
                "longest_joint_same_path_witnessed_coverage": witness_overlaps[:5],
                "pair_semantic": (
                    "INTERSECTION_OF_INDEPENDENT_10_SECOND_STATION_STREAMS_"
                    "MAX_GAP_NO_INTERPOLATION"
                ),
            }
        )

    station_receipts: dict[str, dict[str, object]] = {}
    for station_id, state in station_state.items():
        core_segments = sorted(
            state["core_segments"], key=lambda row: row["duration_s"], reverse=True
        )
        witness_segments = sorted(
            state["witness_segments"],
            key=lambda row: row["duration_s"],
            reverse=True,
        )
        cadence_nonconforming = sum(
            count
            for delta, count in state["cadence_delta_counts"].items()
            if float(delta) <= 0.0
            or float(delta) > MAX_STATION_SAMPLE_GAP_S + CADENCE_TOLERANCE_S
        )
        station_receipts[station_id] = {
            "record_count": state["record_count"],
            "maximum_station_sample_gap_s": MAX_STATION_SAMPLE_GAP_S,
            "cadence_delta_counts": dict(
                sorted(state["cadence_delta_counts"].items())
            ),
            "nonconforming_delta_count": cadence_nonconforming,
            "flag_counts": dict(sorted(state["flag_counts"].items())),
            "longest_core_segments": core_segments[:5],
            "longest_same_path_witnessed_segments": witness_segments[:5],
            "core_break_reasons": dict(
                sorted(state["core_break_reasons"].items())
            ),
            "same_path_witness_break_reasons": dict(
                sorted(state["witness_break_reasons"].items())
            ),
        }

    outcome = (
        "DORIS_DEVELOPMENT_STRUCTURE_QUALIFIED_MEASUREMENT_UNADMITTED"
        if any_pair_admitted
        else "DORIS_DEVELOPMENT_STRUCTURE_INSUFFICIENT"
    )
    receipt: dict[str, object] = {
        "outcome": outcome,
        "scanner_version": SCANNER_VERSION,
        "authority": asdict(authority),
        "artifact_hash_verified_before_decompression": True,
        "frozen_header_sha256": expected_header_sha256,
        "stream": {
            "complete_stream_scanned": True,
            "decompressed_bytes": decompressed_bytes,
            "decompressed_sha256": digest.hexdigest(),
            "line_count": line_count,
            "ephemeral_uncompressed_retention": "ZERO_AFTER_RECEIPT",
        },
        "epochs": {
            "count": epoch_count,
            "special_event_count": special_event_epoch_count,
            "power_failure_epoch_count": power_failure_epoch_count,
            "first_dor": first_epoch.isoformat(),
            "last_dor": last_epoch.isoformat(),
            "global_interleaved_cadence_delta_counts": dict(
                sorted(cadence_counts.items())
            ),
            "station_cadence_semantic": "EVALUATED_PER_STATION_NOT_GLOBALLY",
        },
        "records": {
            "station_record_count": station_record_count,
            "continuation_line_count": continuation_line_count,
            "observable_count_per_station": OBSERVABLE_COUNT,
            "numeric_observation_values_decoded": 0,
            "numeric_observation_values_persisted": 0,
        },
        "stations": station_receipts,
        "pairs": pair_receipts,
        "candidate_day_product_access": "ZERO",
        "orbital_prediction_access": "ZERO",
        "orbital_score": "NOT_EVALUATED",
        "measurement_admission": "NOT_EVALUATED",
        "open_terms": [
            "NUMERICAL_DOR_TO_TAI_PHASE_CENTER_EVENT_TIME_ERROR_BOUND",
            "EXACT_DPOD_COORDINATES_HEIGHTS_AND_PHASE_CENTERS",
            "ONE_WAY_RELATIVISTIC_AND_MEDIA_MODEL",
            "SHARED_RECEIVER_AND_CHANNEL_DIFFERENTIAL_BIAS",
        ],
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
    path = Path(".quarantine-doris-development") / header.DEVELOPMENT_NAME
    print(strict_json(scan_exact_development_structure(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
