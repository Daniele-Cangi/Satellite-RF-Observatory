"""Value-blind exact-coepoch requalification of one DORIS development pair.

The scanner represents only receiver epoch tags, station identities, L1/L2
presence and their two flag characters. Numerical observation magnitudes are
never decoded, returned or persisted. This module cannot access the candidate
day and cannot evaluate an orbital model.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from typing import Callable, Final, Mapping

from experiments.live_instrument.models import strict_json_value
from experiments.orbital_discriminability import doris_development_header as header
from experiments.orbital_discriminability import (
    doris_development_structural_scan as structural,
)


SCANNER_VERSION: Final = "doris-exact-coepoch-requalification-v1"
PAIR: Final = structural.PairRule("PAUB", "D46", "RIMC", "D40", 480.0)
EXPECTED_HEADER_SHA256: Final = structural.EXPECTED_HEADER_SHA256
EXPECTED_DECOMPRESSED_SHA256: Final = (
    "9edb37c8a354602c20985a07edb87c594bcd9678d496e6e70ee0b4ee4f20db64"
)
EXPECTED_DECOMPRESSED_BYTES: Final = 7_564_590
EXPECTED_STREAM_LINES: Final = 94_830
EXPECTED_EPOCHS: Final = 16_704
EXPECTED_STATION_RECORDS: Final = 39_024
TARGET_STATION_IDS: Final = frozenset({PAIR.left_id, PAIR.right_id})


class DorisCoepochError(ValueError):
    """The stream cannot support the frozen exact-coepoch qualification."""


@dataclass(frozen=True, slots=True)
class PhaseShape:
    """Only the two authorized phase-field shapes for one station record."""

    station_id: str
    l1: structural.FieldShape
    l2: structural.FieldShape


def _read_phase_shape(next_line: Callable[[], bytes]) -> PhaseShape:
    """Consume one record while representing only station identity and L1/L2."""

    read_line = next_line
    first = read_line()
    body = first.rstrip(b"\r\n")
    if len(body) < 3:
        raise DorisCoepochError("COEPOCH_SHORT_STATION_RECORD")
    try:
        station_id = body[:3].decode("ascii", errors="strict")
    except UnicodeDecodeError as error:
        raise DorisCoepochError("COEPOCH_NON_ASCII_STATION_ID") from error
    if (
        len(station_id) != 3
        or not station_id.startswith("D")
        or not station_id[1:].isdigit()
    ):
        raise DorisCoepochError("COEPOCH_INVALID_STATION_ID")

    padded = body.ljust(
        3 + structural.FIELDS_PER_LINE * structural.FIELD_WIDTH,
        b" ",
    )
    l1_start = 3
    l2_start = l1_start + structural.FIELD_WIDTH
    l1 = structural._field_shape(
        padded[l1_start : l1_start + structural.FIELD_WIDTH]
    )
    l2 = structural._field_shape(
        padded[l2_start : l2_start + structural.FIELD_WIDTH]
    )

    continuation = read_line().rstrip(b"\r\n")
    if continuation[:3].strip():
        raise DorisCoepochError("COEPOCH_CONTINUATION_PREFIX_NONBLANK")
    return PhaseShape(station_id=station_id, l1=l1, l2=l2)


def _phase_valid(shape: PhaseShape) -> tuple[bool, str]:
    """Apply the frozen L1/L2 presence and discontinuity rules only."""

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


def _segment_receipt(
    start: datetime,
    end: datetime,
    epoch_count: int,
) -> dict[str, object]:
    return {
        "start_dor": start.isoformat(),
        "end_dor": end.isoformat(),
        "epoch_count": epoch_count,
        "duration_s": (end - start).total_seconds(),
    }


def scan_exact_coepoch_topology(
    path: Path,
    *,
    authority: header.ProductAuthority = header.DEVELOPMENT_AUTHORITY,
    expected_header_sha256: str = EXPECTED_HEADER_SHA256,
    expected_decompressed_sha256: str = EXPECTED_DECOMPRESSED_SHA256,
    expected_decompressed_bytes: int = EXPECTED_DECOMPRESSED_BYTES,
    expected_stream_lines: int = EXPECTED_STREAM_LINES,
    expected_epochs: int = EXPECTED_EPOCHS,
    expected_station_records: int = EXPECTED_STATION_RECORDS,
    gzip_executable: str | None = None,
) -> dict[str, object]:
    """Scan one exact artifact and retain only coepoch structural summaries."""

    path = Path(path)
    header.validate_artifact(path, authority)
    command = [header.resolve_gzip(gzip_executable), "-dc", str(path)]
    process = subprocess.Popen(  # noqa: S603 - exact executable and artifact
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.stdout is None or process.stderr is None:
        process.kill()
        raise DorisCoepochError("COEPOCH_GZIP_PIPE_UNAVAILABLE")

    digest = sha256()
    decompressed_bytes = 0
    line_count = 0

    def next_line(*, allow_eof: bool = False) -> bytes:
        nonlocal decompressed_bytes, line_count
        raw_line = process.stdout.readline()
        if not raw_line:
            if allow_eof:
                return b""
            raise DorisCoepochError("COEPOCH_UNEXPECTED_END_OF_STREAM")
        digest.update(raw_line)
        decompressed_bytes += len(raw_line)
        line_count += 1
        if line_count > structural.MAX_STREAM_LINES:
            raise DorisCoepochError("COEPOCH_STREAM_LINE_LIMIT_EXCEEDED")
        return raw_line

    segment_start: datetime | None = None
    segment_last: datetime | None = None
    segment_count = 0
    segments: list[dict[str, object]] = []
    break_reasons: Counter[str] = Counter()
    coepoch_pair_count = 0
    valid_coepoch_pair_count = 0
    epoch_count = 0
    station_record_count = 0
    continuation_line_count = 0
    special_event_count = 0
    power_failure_count = 0
    target_presence_counts: Counter[str] = Counter()
    first_epoch: datetime | None = None
    last_epoch: datetime | None = None
    completed = False

    def finish_segment(reason: str | None = None) -> None:
        nonlocal segment_start, segment_last, segment_count
        if segment_start is not None and segment_last is not None and segment_count:
            segments.append(
                _segment_receipt(segment_start, segment_last, segment_count)
            )
        segment_start = None
        segment_last = None
        segment_count = 0
        if reason is not None:
            break_reasons[reason] += 1

    try:
        header_lines: list[bytes] = []
        while True:
            raw_line = next_line()
            header_lines.append(raw_line)
            if header.header_label(raw_line) == "END OF HEADER":
                break
        if sha256(b"".join(header_lines)).hexdigest() != expected_header_sha256:
            raise DorisCoepochError("COEPOCH_FROZEN_HEADER_SHA256_CHANGED")
        header_lines.clear()

        while True:
            raw_line = next_line(allow_eof=True)
            if not raw_line:
                completed = True
                break

            epoch, epoch_flag, record_count = structural._parse_epoch_prefix(raw_line)
            epoch_count += 1
            if first_epoch is None:
                first_epoch = epoch
            last_epoch = epoch

            if epoch_flag not in {0, 1}:
                special_event_count += 1
                for _ in range(record_count):
                    next_line()
                finish_segment("SPECIAL_EPOCH_FLAG")
                continue

            if epoch_flag == 1:
                power_failure_count += 1
                finish_segment("EPOCH_FLAG_1_POWER_FAILURE")

            epoch_shapes: dict[str, PhaseShape] = {}
            for _ in range(record_count):
                shape = _read_phase_shape(next_line)
                continuation_line_count += 1
                station_record_count += 1
                if shape.station_id in TARGET_STATION_IDS:
                    if shape.station_id in epoch_shapes:
                        raise DorisCoepochError(
                            "COEPOCH_DUPLICATE_TARGET_STATION_IN_EPOCH"
                        )
                    epoch_shapes[shape.station_id] = shape

            left_present = PAIR.left_id in epoch_shapes
            right_present = PAIR.right_id in epoch_shapes
            presence_state = (
                "BOTH"
                if left_present and right_present
                else "LEFT_ONLY"
                if left_present
                else "RIGHT_ONLY"
                if right_present
                else "NEITHER"
            )
            target_presence_counts[presence_state] += 1
            if not left_present or not right_present:
                continue

            coepoch_pair_count += 1
            left_valid, left_reason = _phase_valid(epoch_shapes[PAIR.left_id])
            right_valid, right_reason = _phase_valid(epoch_shapes[PAIR.right_id])
            if not left_valid or not right_valid:
                reason = (
                    f"LEFT_{left_reason}"
                    if not left_valid
                    else f"RIGHT_{right_reason}"
                )
                finish_segment(reason)
                continue

            if segment_last is not None:
                gap_s = (epoch - segment_last).total_seconds()
                if (
                    gap_s <= 0.0
                    or gap_s > structural.MAX_STATION_SAMPLE_GAP_S
                ):
                    finish_segment("EXACT_COEPOCH_SAMPLE_GAP_EXCEEDED")
            if segment_start is None:
                segment_start = epoch
            segment_last = epoch
            segment_count += 1
            valid_coepoch_pair_count += 1
    finally:
        process.stdout.close()
        if process.poll() is None:
            if completed:
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    structural._terminate_with_kill_fallback(process)
            else:
                structural._terminate_with_kill_fallback(process)
        stderr = process.stderr.read()
        process.stderr.close()

    if not completed:
        raise DorisCoepochError("COEPOCH_SCAN_DID_NOT_REACH_STREAM_END")
    if process.returncode != 0:
        detail = stderr.decode("ascii", errors="replace").strip()
        raise DorisCoepochError(f"COEPOCH_GZIP_FAILED:{detail}")
    finish_segment()
    if first_epoch is None or last_epoch is None:
        raise DorisCoepochError("COEPOCH_NO_EPOCHS")

    actual_digest = digest.hexdigest()
    frozen_counts = {
        "decompressed_sha256": (
            actual_digest,
            expected_decompressed_sha256,
            "COEPOCH_DECOMPRESSED_SHA256_CHANGED",
        ),
        "decompressed_bytes": (
            decompressed_bytes,
            expected_decompressed_bytes,
            "COEPOCH_DECOMPRESSED_BYTE_COUNT_CHANGED",
        ),
        "line_count": (
            line_count,
            expected_stream_lines,
            "COEPOCH_STREAM_LINE_COUNT_CHANGED",
        ),
        "epoch_count": (
            epoch_count,
            expected_epochs,
            "COEPOCH_EPOCH_COUNT_CHANGED",
        ),
        "station_record_count": (
            station_record_count,
            expected_station_records,
            "COEPOCH_STATION_RECORD_COUNT_CHANGED",
        ),
    }
    for actual, expected, refusal in frozen_counts.values():
        if actual != expected:
            raise DorisCoepochError(refusal)

    ordered_segments = sorted(
        segments,
        key=lambda item: (-float(item["duration_s"]), str(item["start_dor"])),
    )
    maximum_duration_s = (
        float(ordered_segments[0]["duration_s"]) if ordered_segments else 0.0
    )
    qualified = maximum_duration_s >= PAIR.minimum_duration_s
    outcome = (
        "DORIS_EXACT_COEPOCH_TOPOLOGY_QUALIFIED"
        if qualified
        else "DORIS_EXACT_COEPOCH_TOPOLOGY_INSUFFICIENT"
    )
    receipt: dict[str, object] = {
        "outcome": outcome,
        "scanner_version": SCANNER_VERSION,
        "authority": {
            **asdict(authority),
            "execution_role": (
                "DEVELOPMENT_EXACT_COEPOCH_REQUALIFICATION_ONLY_NEVER_PRIMARY"
            ),
        },
        "artifact_hash_verified_before_decompression": True,
        "frozen_header_sha256": expected_header_sha256,
        "stream": {
            "complete_stream_scanned": True,
            "decompressed_bytes": decompressed_bytes,
            "decompressed_sha256": actual_digest,
            "line_count": line_count,
            "compressed_retention_after_receipt": "ZERO_REQUIRED",
            "uncompressed_retention": "ZERO",
        },
        "epochs": {
            "count": epoch_count,
            "first_dor": first_epoch.isoformat(),
            "last_dor": last_epoch.isoformat(),
            "special_event_count": special_event_count,
            "power_failure_epoch_count": power_failure_count,
        },
        "records": {
            "station_record_count": station_record_count,
            "continuation_line_count": continuation_line_count,
            "numeric_observation_values_decoded": 0,
            "numeric_observation_values_persisted": 0,
        },
        "pair": {
            "codes": [PAIR.left_code, PAIR.right_code],
            "station_ids": [PAIR.left_id, PAIR.right_id],
            "frequency_shift_k": [0, 0],
            "minimum_required_duration_s": PAIR.minimum_duration_s,
            "coepoch_pair_count": coepoch_pair_count,
            "valid_coepoch_pair_count": valid_coepoch_pair_count,
            "target_epoch_presence_counts": dict(
                sorted(target_presence_counts.items())
            ),
            "maximum_exact_coepoch_segment_s": maximum_duration_s,
            "longest_exact_coepoch_segments": ordered_segments[:5],
            "break_reasons": dict(sorted(break_reasons.items())),
            "sample_semantic": (
                "IDENTICAL_DOR_EPOCH_TAG_NO_INTERPOLATION_MAX_10_SECOND_GAP"
            ),
            "topology_qualified": qualified,
        },
        "scope": {
            "candidate_day_product_access": "ZERO",
            "observation_magnitudes": "NEVER_DECODED_NEVER_PERSISTED",
            "c1_c2_values_or_flags": "NOT_RETAINED_NOT_EVALUATED",
            "orbital_prediction": "NOT_EVALUATED",
            "null_score": "NOT_EVALUATED",
            "measurement_admission": "NOT_EVALUATED",
        },
        "remaining_open_terms": [
            "ABSOLUTE_DOR_TO_COORDINATE_TIME_ERROR_BOUND",
            "HIGHER_ORDER_IONOSPHERE",
            "DIFFERENTIAL_TROPOSPHERE",
            "STATION_PHASE_CENTERS_AND_ANTENNA_MAPS",
            "PHASE_WINDUP",
            "SHAPIRO_AND_ONE_WAY_RELATIVITY",
            "NONAFFINE_GROUND_OSCILLATOR_BEHAVIOR",
            "CHANNEL_SWITCH_OR_RECEIVER_NONCOMMON_BIAS",
        ],
    }
    strict_json(receipt)
    return receipt


def strict_json(payload: Mapping[str, object]) -> str:
    """Serialize a receipt with the repository's strict JSON boundary."""

    return json.dumps(
        strict_json_value(payload),
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def main() -> int:
    """Run the frozen scanner against the exact quarantine location."""

    path = Path(".quarantine-doris-coepoch") / header.DEVELOPMENT_NAME
    print(strict_json(scan_exact_coepoch_topology(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
