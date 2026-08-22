"""Value-blind DOY-214 qualification for the KIRU/MAT1 GNSS vertical.

This is a bounded parser for two exact artifacts, two GPS satellites and the
field topology needed by the already selected forward coordinate.  It hashes
each complete CRINEX artifact before decompression.  Observation scalars,
LLI/SSI values and signal magnitudes are never decoded or returned.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import re
from typing import Final, Iterable

import hatanaka

from experiments.orbital_discriminability import gnss_independent_forward_review as review
from experiments.orbital_discriminability import gnss_observation_header as headers


QUALIFICATION_VERSION: Final = "gnss-kiru-mat1-structure-v1"
OUTCOME_ADMITTED: Final = "GNSS_QUALIFICATION_ADMITTED"
OUTCOME_ERROR: Final = "QUALIFICATION_ERROR"
OUTCOME_REJECTED: Final = "CAPABILITY_REJECTED"
TARGETS: Final = ("G20", "G22")
EXPECTED_INTERVAL_S: Final = 30.0
PRIMARY_REQUIRED_RECORDS: Final = 380
MAX_EPOCH_RECORDS: Final = 3_000
PARSER_SEMANTICS: Final = (
    "RINEX_FIXED_WIDTH_16_CHARACTER_FIELDS; THREE_CHARACTER_SATELLITE_PREFIX; "
    "THREE_SPACE_CONTINUATION_PREFIX; A FINAL_SERIALIZED_FIELD_MAY_END_AFTER_"
    "ITS_14_VALUE_CHARACTERS_WHEN_LLI_AND_SSI_ARE_BLANK; TRAILING_UNSERIALIZED_"
    "DECLARED_FIELDS_ARE_STRUCTURALLY_ABSENT; FIELD_OCCUPANCY_TESTS_CHARACTERS_"
    "1_TO_14_FOR_NONSPACE_WITHOUT_NUMERIC_CONVERSION"
)


AUTHORITIES: Final = (
    headers.ProductAuthority(
        station_id="KIRU00SWE",
        name="KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz",
        url=(
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/"
            "KIRU00SWE_R_20262140000_01D_30S_MO.crx.gz"
        ),
        bytes=5_126_492,
        sha256="06db32b758483448fa4420758a0783a1ede144e6812e794f2b5311aeef0547c0",
    ),
    headers.ProductAuthority(
        station_id="MAT100ITA",
        name="MAT100ITA_R_20262140000_01D_30S_MO.crx.gz",
        url=(
            "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/214/"
            "MAT100ITA_R_20262140000_01D_30S_MO.crx.gz"
        ),
        bytes=4_237_763,
        sha256="3e1a55a4be23ec5a6b7c62589366f444cd0d3777a9a7ad37daad4757e28dfae2",
    ),
)


class QualificationError(ValueError):
    """The bounded software path could not describe the artifact."""


class CapabilityRejected(ValueError):
    """A parsed capability failed one predeclared physical admission clause."""


@dataclass(frozen=True, slots=True)
class StructuralResult:
    station_id: str
    summary: dict[str, object]
    usable_epochs: frozenset[datetime]


class _Cursor:
    """Line cursor over one erasable bytearray without observation-line copies."""

    def __init__(self, buffer: bytearray):
        self._buffer = buffer
        self._position = 0
        self._pending: memoryview | None = None

    def readline(self) -> memoryview:
        if self._pending is not None:
            line, self._pending = self._pending, None
            return line
        if self._position >= len(self._buffer):
            return memoryview(self._buffer)[0:0]
        newline = self._buffer.find(b"\n", self._position)
        stop = len(self._buffer) if newline < 0 else newline + 1
        line = memoryview(self._buffer)[self._position:stop]
        self._position = stop
        return line

    def push(self, line: memoryview) -> None:
        if self._pending is not None:
            raise QualificationError("MULTIPLE_LINE_PUSHBACK")
        self._pending = line


_SATELLITE_PATTERN: Final = re.compile(rb"^[A-Z][0-9]{2}")


def qualification_manifest() -> dict[str, object]:
    return {
        "qualification_version": QUALIFICATION_VERSION,
        "parser_code_sha256": file_sha256(Path(__file__)),
        "dependencies": {
            "hatanaka": importlib.metadata.version("hatanaka"),
            "ncompress": importlib.metadata.version("ncompress"),
        },
        "authorities": [asdict(item) for item in AUTHORITIES],
        "targets": list(TARGETS),
        "signal_family_selection": [list(item) for item in headers.GPS_PHASE_PREFERENCES],
        "expected_interval_s": EXPECTED_INTERVAL_S,
        "primary_required_records": PRIMARY_REQUIRED_RECORDS,
        "parser_semantics": PARSER_SEMANTICS,
        "timing_convention": {
            "epoch_labels": "RINEX_DECLARED_GPS_SYSTEM_TIME",
            "utc_conversion": "NOT_PERFORMED_DURING_QUALIFICATION",
            "same_epoch_satellite_records": "ONE_RECEIVER_EPOCH_RECORD",
            "absolute_clock_error": "NOT_MEASURED; RETAINS_EXISTING_DIRECT_PLUS_OR_MINUS_15_S_ENVELOPE",
        },
        "forbidden": [
            "DOY_215_PRIMARY_ACCESS",
            "NUMERIC_OBSERVATION_CONVERSION",
            "LLI_OR_SSI_VALUE_DECODING",
            "SIGNAL_MAGNITUDE_OR_FEATURE_EXTRACTION",
            "PRIMARY_PLAN_FREEZE",
            "ORBITAL_OR_RF_CLAIM",
            "PERSISTENCE_OF_DECOMPRESSED_RINEX",
        ],
    }


def qualification_manifest_sha256() -> str:
    return sha256(strict_json(qualification_manifest()).encode("ascii")).hexdigest()


def qualify_pair(root: Path, source_parent_commit: str) -> dict[str, object]:
    """Qualify only the two exact DOY-214 products under the frozen topology."""

    root = Path(root)
    header_receipts: list[dict[str, object]] = []
    try:
        for authority in AUTHORITIES:
            header_receipts.append(
                headers.parse_exact_header(root / authority.name, authority)
            )
        signal_family = _admit_headers(header_receipts)
        required = tuple(signal_family["same_path_observables"])
        structures = [
            decode_exact_structure(root / authority.name, authority, required)
            for authority in AUTHORITIES
        ]
        common_epochs = set.intersection(
            *(set(item.usable_epochs) for item in structures)
        )
        longest = longest_contiguous_run(common_epochs, EXPECTED_INTERVAL_S)
        if len(longest) < PRIMARY_REQUIRED_RECORDS:
            raise CapabilityRejected(
                f"INSUFFICIENT_COMMON_CONTINUOUS_RECORDS:{len(longest)}:"
                f"{PRIMARY_REQUIRED_RECORDS}"
            )
        clauses = {
            "exact_artifacts_hashed_before_analysis": "SATISFIED",
            "common_dual_frequency_phase_code_snr_family": "SATISFIED",
            "gps_epoch_semantics_explicit": "SATISFIED",
            "receiver_clock_offset_state_explicit_or_standard_default": "SATISFIED",
            "decoder_native_continuation_and_trailing_blank_semantics": "SATISFIED",
            "all_epoch_records_monotonic_at_30_s": "SATISFIED",
            "g20_g22_complete_common_run_at_least_380_records": "SATISFIED",
            "numeric_values_excluded_from_qualification": "SATISFIED",
            "primary_remains_sealed": "SATISFIED",
        }
        result = {
            "outcome": OUTCOME_ADMITTED,
            "qualification_version": QUALIFICATION_VERSION,
            "source_parent_commit": source_parent_commit,
            "parent_review_receipt_sha256": (
                "87a869afa1fa6a66e0cc4144c2ca7f261364e33867fe5ced9b9ee9620257df78"
            ),
            "qualification_manifest_sha256": qualification_manifest_sha256(),
            "qualification_manifest": qualification_manifest(),
            "clauses": clauses,
            "chosen_signal_family": signal_family,
            "header_evidence": [header_evidence(item) for item in header_receipts],
            "products": [item.summary for item in structures],
            "common_structurally_usable_epochs": len(common_epochs),
            "longest_common_continuous_run": run_receipt(longest),
            "primary_requirement": {
                "records": PRIMARY_REQUIRED_RECORDS,
                "duration_between_first_and_last_s": (
                    (PRIMARY_REQUIRED_RECORDS - 1) * EXPECTED_INTERVAL_S
                ),
                "qualification_surplus_records": len(longest)
                - PRIMARY_REQUIRED_RECORDS,
            },
            "measurement_access": {
                "qualification_payloads_opened": 2,
                "qualification_artifact_bytes_opened": sum(
                    item.bytes for item in AUTHORITIES
                ),
                "numeric_observation_values_decoded": 0,
                "observation_value_text_retained": 0,
                "lli_values_decoded": 0,
                "ssi_values_decoded": 0,
                "snr_magnitudes_decoded": 0,
                "decompressed_rinex_persisted_bytes": 0,
                "primary_payload_bytes_opened": 0,
                "primary_headers_opened": 0,
            },
            "primary_products": review.product_roles()["primary"],
            "qualification_access_authorized": True,
            "primary_access_authorized": False,
            "prospective_plan_frozen": False,
            "new_gate_created": False,
            "claim_scope": (
                "DOY_214_PROVES_THE_EXACT_KIRU_MAT1_RINEX_PATH_CAN_MATERIALIZE_"
                "THE_PREDECLARED_G20_G22_DUAL_FREQUENCY_FIELD_TOPOLOGY_FOR_AT_"
                "LEAST_THE_PRIMARY_WINDOW_LENGTH; IT_DOES_NOT_PROVE_PRIMARY_"
                "OCCUPANCY_MEASUREMENT_VALIDITY_OR_ORBITAL_PREFERENCE"
            ),
            "next_exact_blocker": (
                "FREEZE_ONE_PRIMARY_PLAN_AND_OBTAIN_SEPARATE_DOY_215_ACCESS_AUTHORITY"
            ),
        }
    except CapabilityRejected as exc:
        result = refusal_receipt(OUTCOME_REJECTED, str(exc), source_parent_commit)
    except (QualificationError, headers.HeaderAdmissionError, OSError) as exc:
        result = refusal_receipt(OUTCOME_ERROR, str(exc), source_parent_commit)
    strict_json(result)
    return result


def _admit_headers(receipts: Iterable[dict[str, object]]) -> dict[str, object]:
    receipts = tuple(receipts)
    common: set[str] | None = None
    for receipt in receipts:
        authority = receipt["authority"]
        header = receipt["header"]
        marker = str(header["marker_name"])
        station = str(authority["station_id"])
        if marker not in {station, station[:4]}:
            raise CapabilityRejected(f"MARKER_IDENTITY_MISMATCH:{station}")
        if header["interval_s"] != EXPECTED_INTERVAL_S:
            raise CapabilityRejected(f"INTERVAL_NOT_30S:{station}")
        first = header["time_of_first_observation"]
        if first["time_system"] != "GPS":
            raise CapabilityRejected(f"TIME_SYSTEM_NOT_GPS:{station}")
        if header["receiver_clock_offset_applied"] not in (0, 1):
            raise CapabilityRejected(f"CLOCK_OFFSET_SEMANTICS_UNKNOWN:{station}")
        station_gps = set(header["observable_types"].get("G", ()))
        common = station_gps if common is None else common & station_gps
    common = common or set()
    for l1_phase, l2_phase in headers.GPS_PHASE_PREFERENCES:
        required = headers.signal_family(l1_phase) | headers.signal_family(l2_phase)
        if required <= common:
            return {
                "selection_order_frozen_before_occupancy_scan": True,
                "l1_phase": l1_phase,
                "l2_phase": l2_phase,
                "same_path_observables": sorted(required),
            }
    raise CapabilityRejected("NO_COMMON_L1_L2_PHASE_CODE_SNR_WITNESS_FAMILY")


def header_evidence(receipt: dict[str, object]) -> dict[str, object]:
    authority = receipt["authority"]
    header = receipt["header"]
    boundary = receipt["header_boundary"]
    return {
        "station_id": authority["station_id"],
        "header_sha256": boundary["header_sha256"],
        "rinex_version": header["rinex_version"],
        "crinex_version": header.get("crinex_version"),
        "marker_name": header["marker_name"],
        "receiver": header["receiver"],
        "antenna": header["antenna"],
        "interval_s": header["interval_s"],
        "time_of_first_observation": header["time_of_first_observation"],
        "time_of_last_observation": header.get("time_of_last_observation"),
        "receiver_clock_offset_applied": header["receiver_clock_offset_applied"],
        "receiver_clock_offset_provenance": header[
            "receiver_clock_offset_provenance"
        ],
        "signal_strength_unit": header.get("signal_strength_unit"),
        "gps_observable_types": header["observable_types"]["G"],
    }


def decode_exact_structure(
    path: Path,
    authority: headers.ProductAuthority,
    required_observables: tuple[str, ...],
) -> StructuralResult:
    headers.validate_artifact(path, authority)
    try:
        immutable = hatanaka.decompress(path, strict=True)
    except Exception as exc:  # decoder errors are descriptive, not physical
        raise QualificationError("HATANAKA_DECODING_FAILED") from exc
    decoded = bytearray(immutable)
    del immutable
    decoded_sha256 = sha256(decoded).hexdigest()
    decoded_bytes = len(decoded)
    try:
        return parse_decompressed_structure(
            decoded,
            authority,
            required_observables,
            decoded_sha256=decoded_sha256,
            decoded_bytes=decoded_bytes,
        )
    finally:
        decoded[:] = b"\x00" * len(decoded)


def parse_decompressed_structure(
    decoded: bytearray,
    authority: headers.ProductAuthority,
    required_observables: tuple[str, ...],
    *,
    decoded_sha256: str = "SYNTHETIC",
    decoded_bytes: int | None = None,
) -> StructuralResult:
    cursor = _Cursor(decoded)
    system_types, header_lines = _read_observation_types(cursor)
    gps_types = system_types.get("G")
    if gps_types is None:
        raise CapabilityRejected("GPS_OBSERVATION_TYPES_MISSING")
    try:
        selected_index = {name: gps_types.index(name) for name in required_observables}
    except ValueError as exc:
        raise CapabilityRejected("SELECTED_SIGNAL_FAMILY_MISSING") from exc

    epoch_count = 0
    observation_epoch_count = 0
    satellite_records = 0
    continuation_lines = 0
    trailing_omission_records = 0
    partial_field_lines = 0
    previous_epoch: datetime | None = None
    first_epoch: datetime | None = None
    last_epoch: datetime | None = None
    step_counts: Counter[str] = Counter()
    flag_counts: Counter[str] = Counter()
    topology_counts: Counter[tuple[str, int, int]] = Counter()
    target_record_counts: Counter[str] = Counter()
    target_presence_counts = {
        target: Counter({name: 0 for name in required_observables})
        for target in TARGETS
    }
    usable_epochs: set[datetime] = set()

    while True:
        line = cursor.readline()
        if len(line) == 0:
            break
        if line[0] != ord(">"):
            if any(byte not in (10, 13, 32) for byte in line):
                raise QualificationError("NON_EPOCH_RECORD_AFTER_HEADER")
            continue
        epoch, flag, satellite_count = _parse_epoch(line)
        epoch_count += 1
        if epoch_count > MAX_EPOCH_RECORDS:
            raise QualificationError("EPOCH_RECORD_LIMIT_EXCEEDED")
        flag_counts[str(flag)] += 1
        if first_epoch is None:
            first_epoch = epoch
        if previous_epoch is not None:
            delta_s = (epoch - previous_epoch).total_seconds()
            if delta_s <= 0:
                raise CapabilityRejected("NON_MONOTONIC_OR_DUPLICATE_EPOCH")
            step_counts[f"{delta_s:.6f}"] += 1
        previous_epoch = epoch
        last_epoch = epoch

        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if len(cursor.readline()) == 0:
                    raise QualificationError("TRUNCATED_SPECIAL_EVENT")
            continue
        if flag != 0:
            raise CapabilityRejected(f"UNSUPPORTED_EPOCH_FLAG:{flag}")
        observation_epoch_count += 1
        epoch_targets: dict[str, dict[str, bool]] = {}
        for _ in range(satellite_count):
            record = _read_structural_satellite(
                cursor, system_types, selected_index
            )
            satellite_records += 1
            continuation_lines += record["continuation_lines"]
            partial_field_lines += record["partial_field_lines"]
            serialized = record["serialized_fields"]
            declared = record["declared_fields"]
            topology_counts[(record["system"], declared, serialized)] += 1
            if serialized < declared:
                trailing_omission_records += 1
            satellite = record["satellite"]
            if satellite in TARGETS:
                if satellite in epoch_targets:
                    raise QualificationError("DUPLICATE_TARGET_SATELLITE_RECORD")
                target_record_counts[satellite] += 1
                presence = record["selected_presence"]
                epoch_targets[satellite] = presence
                for observable, present in presence.items():
                    if present:
                        target_presence_counts[satellite][observable] += 1
        if all(
            target in epoch_targets and all(epoch_targets[target].values())
            for target in TARGETS
        ):
            usable_epochs.add(epoch)

    if epoch_count == 0 or first_epoch is None or last_epoch is None:
        raise CapabilityRejected("NO_OBSERVATION_EPOCHS")
    if partial_field_lines:
        raise QualificationError("PARTIAL_FIXED_WIDTH_OBSERVATION_FIELD")
    expected_step = f"{EXPECTED_INTERVAL_S:.6f}"
    if set(step_counts) != {expected_step}:
        raise CapabilityRejected("NON_30S_OR_GAPPED_EPOCH_SEQUENCE")

    topology = [
        {
            "system": system,
            "declared_fields": declared,
            "serialized_fields": serialized,
            "records": count,
        }
        for (system, declared, serialized), count in sorted(topology_counts.items())
    ]
    summary = {
        "station_id": authority.station_id,
        "artifact": asdict(authority),
        "artifact_hash_verified_before_decompression": True,
        "decompressed_ephemeral_artifact": {
            "bytes": len(decoded) if decoded_bytes is None else decoded_bytes,
            "sha256": decoded_sha256,
            "persisted": False,
            "erasure_policy": "BYTEARRAY_OVERWRITTEN_IN_CALLER_FINALLY",
        },
        "header_lines": header_lines,
        "declared_observation_fields_by_system": {
            system: len(values) for system, values in sorted(system_types.items())
        },
        "epoch_records": epoch_count,
        "observation_epoch_records": observation_epoch_count,
        "first_epoch_gps": format_gps_epoch(first_epoch),
        "last_epoch_gps": format_gps_epoch(last_epoch),
        "epoch_flag_counts": dict(sorted(flag_counts.items())),
        "epoch_step_counts_s": dict(sorted(step_counts.items())),
        "satellite_records": satellite_records,
        "continuation_lines": continuation_lines,
        "records_with_unserialized_trailing_declared_fields": trailing_omission_records,
        "trailing_field_semantics": "ABSENT_BLANK_NOT_TRUNCATION_ERROR",
        "record_topology": topology,
        "target_record_counts": {
            target: target_record_counts[target] for target in TARGETS
        },
        "selected_field_presence_counts": {
            target: dict(target_presence_counts[target]) for target in TARGETS
        },
        "structurally_usable_target_epochs": len(usable_epochs),
        "value_blindness": {
            "field_occupancy_predicate": "ANY_NONSPACE_IN_CHARACTERS_1_TO_14",
            "numeric_observation_values_decoded": 0,
            "observation_value_text_retained": 0,
            "lli_values_decoded": 0,
            "ssi_values_decoded": 0,
            "snr_magnitudes_decoded": 0,
        },
    }
    return StructuralResult(authority.station_id, summary, frozenset(usable_epochs))


def _read_observation_types(
    cursor: _Cursor,
) -> tuple[dict[str, tuple[str, ...]], int]:
    collected: dict[str, list[str]] = {}
    expected: dict[str, int] = {}
    current_system: str | None = None
    lines = 0
    while True:
        line = cursor.readline()
        if len(line) == 0:
            raise QualificationError("DECOMPRESSED_HEADER_INCOMPLETE")
        lines += 1
        body = bytes(line).rstrip(b"\r\n")
        if len(body) < 60:
            raise QualificationError("SHORT_DECOMPRESSED_HEADER_LINE")
        label = body[60:80].decode("ascii", errors="strict").strip()
        if label == "SYS / # / OBS TYPES":
            if body[:1] != b" ":
                current_system = body[:1].decode("ascii")
                try:
                    expected[current_system] = int(body[3:6])
                except ValueError as exc:
                    raise QualificationError("INVALID_OBSERVATION_TYPE_COUNT") from exc
                collected[current_system] = []
            if current_system is None:
                raise QualificationError("ORPHAN_OBSERVATION_TYPE_CONTINUATION")
            collected[current_system].extend(body[7:60].decode("ascii").split())
        if label == "END OF HEADER":
            break
    result: dict[str, tuple[str, ...]] = {}
    for system, count in expected.items():
        if len(collected[system]) < count:
            raise QualificationError("INCOMPLETE_OBSERVATION_TYPE_DECLARATION")
        result[system] = tuple(collected[system][:count])
    return result, lines


def _parse_epoch(line: memoryview) -> tuple[datetime, int, int]:
    try:
        parts = bytes(line).decode("ascii").split()
        second = float(parts[6])
        whole_second = int(second)
        microsecond = round((second - whole_second) * 1_000_000)
        epoch = datetime(
            int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]),
            int(parts[5]), whole_second, microsecond, tzinfo=timezone.utc,
        )
        return epoch, int(parts[7]), int(parts[8])
    except (IndexError, ValueError) as exc:
        raise QualificationError("INVALID_RINEX_EPOCH_RECORD") from exc


def _read_structural_satellite(
    cursor: _Cursor,
    system_types: dict[str, tuple[str, ...]],
    selected_index: dict[str, int],
) -> dict[str, object]:
    line = cursor.readline()
    if not _is_satellite_record(line):
        raise QualificationError("INVALID_SATELLITE_RECORD")
    satellite = bytes(line[:3]).decode("ascii")
    system = satellite[0]
    if system not in system_types:
        raise QualificationError("UNDECLARED_SATELLITE_SYSTEM")
    declared = len(system_types[system])
    serialized = 0
    continuation_lines = 0
    partial_field_lines = 0
    selected_presence = {name: False for name in selected_index}

    while True:
        field_count, partial = _scan_structural_fields(
            line, serialized, selected_index, selected_presence
        )
        serialized += field_count
        partial_field_lines += int(partial)
        if serialized >= declared:
            break
        following = cursor.readline()
        if len(following) == 0:
            break
        if following[0] == ord(">") or _is_satellite_record(following):
            cursor.push(following)
            break
        if len(following) < 3 or bytes(following[:3]) != b"   ":
            raise QualificationError("AMBIGUOUS_OBSERVATION_CONTINUATION")
        continuation_lines += 1
        line = following
    if serialized > declared:
        raise QualificationError("OBSERVATION_FIELD_COUNT_EXCEEDS_DECLARATION")
    return {
        "satellite": satellite,
        "system": system,
        "declared_fields": declared,
        "serialized_fields": serialized,
        "continuation_lines": continuation_lines,
        "partial_field_lines": partial_field_lines,
        "selected_presence": selected_presence,
    }


def _scan_structural_fields(
    line: memoryview,
    global_start: int,
    selected_index: dict[str, int],
    selected_presence: dict[str, bool],
) -> tuple[int, bool]:
    stop = len(line)
    while stop and line[stop - 1] in (10, 13):
        stop -= 1
    payload_length = max(0, stop - 3)
    field_count, remainder = divmod(payload_length, 16)
    if remainder:
        field_count += 1
    for observable, wanted in selected_index.items():
        local = wanted - global_start
        if local < 0 or local >= field_count:
            continue
        begin = 3 + local * 16
        value_stop = min(begin + 14, stop)
        selected_presence[observable] = any(
            line[index] != 32 for index in range(begin, value_stop)
        )
    # Real Hatanaka 2.8.1 output removes blank LLI/SSI characters at the end
    # of a satellite line.  A remainder of 14 is therefore one complete
    # value-width field with its two optional indicator blanks omitted, not a
    # truncated value.  Other remainders are a descriptive parser failure.
    return field_count, remainder not in (0, 14)


def _is_satellite_record(line: memoryview) -> bool:
    return len(line) >= 3 and _SATELLITE_PATTERN.match(bytes(line[:3])) is not None


def longest_contiguous_run(
    epochs: Iterable[datetime], step_s: float
) -> tuple[datetime, ...]:
    best: list[datetime] = []
    current: list[datetime] = []
    expected = timedelta(seconds=step_s)
    for epoch in sorted(set(epochs)):
        if current and epoch - current[-1] != expected:
            if len(current) > len(best):
                best = current
            current = []
        current.append(epoch)
    if len(current) > len(best):
        best = current
    return tuple(best)


def run_receipt(run: tuple[datetime, ...]) -> dict[str, object]:
    if not run:
        return {"records": 0, "start_gps": None, "stop_gps": None, "duration_s": 0.0}
    return {
        "records": len(run),
        "start_gps": format_gps_epoch(run[0]),
        "stop_gps": format_gps_epoch(run[-1]),
        "duration_s": (run[-1] - run[0]).total_seconds(),
    }


def refusal_receipt(
    outcome: str, reason: str, source_parent_commit: str
) -> dict[str, object]:
    return {
        "outcome": outcome,
        "reason": reason,
        "qualification_version": QUALIFICATION_VERSION,
        "source_parent_commit": source_parent_commit,
        "qualification_manifest_sha256": qualification_manifest_sha256(),
        "primary_products": review.product_roles()["primary"],
        "qualification_access_authorized": True,
        "primary_access_authorized": False,
        "prospective_plan_frozen": False,
        "measurement_access": {
            "numeric_observation_values_decoded": 0,
            "decompressed_rinex_persisted_bytes": 0,
            "primary_payload_bytes_opened": 0,
            "primary_headers_opened": 0,
        },
    }


def format_gps_epoch(epoch: datetime) -> str:
    return epoch.strftime("%Y-%m-%dT%H:%M:%S.%f GPS")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(value: object) -> str:
    return json.dumps(
        value, allow_nan=False, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--source-parent-commit", required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    payload = strict_json(
        qualify_pair(arguments.root, arguments.source_parent_commit)
    ) + "\n"
    if arguments.output is None:
        print(payload, end="")
    else:
        arguments.output.write_text(payload, encoding="ascii", newline="\n")
