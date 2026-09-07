"""Frozen model-blind DRAO DOY232 measurement-path qualification.

This is one experiment-specific executor, not a GNSS framework.  It accepts
only the exact compressed qualification artifact whose content-blind receipt
is already frozen.  A separately authorised execution may decode observations
in RAM, emit structural rows and aggregate health metrics, and then erase all
artifact and observation buffers.  It has no orbital-model or DOY233 surface.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import gc
from hashlib import sha256
import importlib.metadata
import json
from pathlib import Path
import subprocess
from typing import Final, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import hatanaka
import numpy as np

from experiments.orbital_discriminability import gnss_drao_doy232_qualification_contract as frozen
from experiments.orbital_discriminability import gnss_observation_header as headers
from experiments.orbital_discriminability import gnss_phase_short_window_qualification as rinex
from experiments.orbital_discriminability import gnss_structural_qualification as structural


EXECUTOR_VERSION: Final = "drao-doy232-model-blind-qualification-v1"
ARTIFACT_NAME: Final = "DRAO00CAN_R_20262320000_01D_30S_MO.crx.gz"
ARTIFACT_URL: Final = (
    "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/232/" + ARTIFACT_NAME
)
ARTIFACT_BYTES: Final = 2_904_457
ARTIFACT_SHA256: Final = (
    "fca688310e9bd48a70452e0f9409a24d4b036add44ee31024ca1d76e130fe8d3"
)
CONTRACT_NAME: Final = "GNSS_DRAO_DOY232_QUALIFICATION_CONTRACT.json"
CONTRACT_SHA256: Final = (
    "f0a02eb1d49b7ea01db6db263a1fb81af0d317fd959d1c78c3aece822c842df1"
)
REPLAY_AUTHORITY_NAME: Final = "GNSS_DRAO_DOY232_RECEIPT_REPLAY_AUTHORITY.json"
REPLAY_AUTHORITY_SHA256: Final = (
    "1d63f1b7f12b933ad67c19d8bbc0ee1a2f4510b475f32e28de901bd8b75f30f0"
)
REPLAY_RECEIPT_NAME: Final = "GNSS_DRAO_DOY232_RECEIPT_REPLAY.json"
REPLAY_RECEIPT_SHA256: Final = (
    "10e6c002333080087c5d87787d74a7882175ae72f875f55162ee53653d3341b0"
)
SELECTION_NAME: Final = "GNSS_DRAO_DOY232_ARTIFACT_SELECTION.json"
SELECTION_SHA256: Final = (
    "b11ba459b97a13f47992f0f5ed9645d6be5a25a1dbdcf4e1885c4562f33f0ca0"
)
SEAL_NAME: Final = "GNSS_DRAO_DOY232_QUALIFICATION_EXECUTOR_SEAL.json"
OUTCOME_NAME: Final = "GNSS_DRAO_DOY232_QUALIFICATION_OUTCOME.json"
COVERAGE_NAME: Final = "GNSS_DRAO_DOY232_QUALIFICATION_COVERAGE.jsonl"
SUMMARY_NAME: Final = "GNSS_DRAO_DOY232_QUALIFICATION_SUMMARY.json"
AUTHORITY_MARKER_NAME: Final = "GNSS_DRAO_DOY232_QUALIFICATION_AUTHORITY_CONSUMED.json"
AUTHORITY_TOKEN: Final = "AUTHORIZE_DRAO_DOY232_MODEL_BLIND_QUALIFICATION_ONCE"

MAX_TRANSPORT_ATTEMPTS: Final = 2
HTTP_TIMEOUT_S: Final = 120.0
MAX_COMPRESSED_BYTES: Final = 4_000_000
RINEX_SEMANTICS_SOURCE: Final = "https://files.igs.org/pub/data/format/rinex304.pdf"

SATELLITES: Final = frozen.SATELLITES
CORE_PHASE: Final = frozen.CORE_PHASE
SAME_PATH_CODE: Final = frozen.SAME_PATH_CODE
OPTIONAL_DIAGNOSTICS: Final = frozen.OPTIONAL_DIAGNOSTICS
OBSERVABLES: Final = CORE_PHASE + SAME_PATH_CODE + OPTIONAL_DIAGNOSTICS
LAMBDA_L1_M: Final = frozen.SPEED_OF_LIGHT_M_S / frozen.L1_HZ
LAMBDA_L2_M: Final = frozen.SPEED_OF_LIGHT_M_S / frozen.L2_HZ

PRESENT: Final = "PRESENT"
BLANK: Final = "BLANK"
TRAILING_FIELD_OMITTED: Final = "TRAILING_FIELD_OMITTED"
RECORD_INVALID: Final = "RECORD_INVALID"


class DraoQualificationError(ValueError):
    """The frozen executor, input identity or qualification is invalid."""


class MaterializationError(RuntimeError):
    """The exact compressed artifact was not completely materialized."""


class DescriptionError(RuntimeError):
    """Software/description failure that cannot reject the physical path."""


@dataclass(slots=True)
class QualificationScan:
    header: dict[str, object]
    coverage: list[dict[str, object]]
    phase_cycles: np.ndarray
    code_m: np.ndarray
    phase_good: np.ndarray
    code_good: np.ndarray
    epoch_good: np.ndarray

    def erase(self) -> None:
        self.phase_cycles.fill(0.0)
        self.code_m.fill(0.0)
        self.phase_good.fill(False)
        self.code_good.fill(False)
        self.epoch_good.fill(False)


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


def file_sha256(path: Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(64 * 1024):
            digest.update(block)
    return digest.hexdigest()


def source_sha256() -> str:
    return canonical_sha256(Path(__file__))


def _git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
    ).strip()


def dependency_versions() -> dict[str, str]:
    return {
        "hatanaka": importlib.metadata.version("hatanaka"),
        "numpy": importlib.metadata.version("numpy"),
    }


def expected_epochs() -> tuple[datetime, ...]:
    epochs = tuple(
        frozen.RAW_START + timedelta(seconds=index * frozen.STEP_S)
        for index in range(frozen.RAW_EPOCHS)
    )
    if structural.format_gps_epoch(epochs[-1]) != "2026-08-20T02:28:00.000000Z":
        raise DescriptionError("FROZEN_DRAO_GRID_CHANGED")
    return epochs


def _read_strict_json(path: Path) -> dict[str, object]:
    value = json.loads(
        Path(path).read_text(encoding="ascii"),
        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)),
    )
    if not isinstance(value, dict):
        raise DescriptionError(f"NOT_A_JSON_OBJECT:{Path(path).name}")
    return value


def verify_frozen_inputs(root: Path) -> dict[str, str]:
    root = Path(root)
    expected = {
        CONTRACT_NAME: CONTRACT_SHA256,
        REPLAY_AUTHORITY_NAME: REPLAY_AUTHORITY_SHA256,
        REPLAY_RECEIPT_NAME: REPLAY_RECEIPT_SHA256,
        SELECTION_NAME: SELECTION_SHA256,
    }
    actual = {name: file_sha256(root / name) for name in expected}
    if actual != expected:
        raise DescriptionError("FROZEN_DRAO_INPUT_HASH_CHANGED")
    receipt = _read_strict_json(root / REPLAY_RECEIPT_NAME)
    artifact = receipt.get("artifact", {})
    if receipt.get("outcome") != "DRAO_DOY232_RECEIPT_REPLAY_MATERIALIZED":
        raise DescriptionError("DRAO_RECEIPT_REPLAY_NOT_COMPLETE")
    if (
        artifact.get("name") != ARTIFACT_NAME
        or artifact.get("actual_complete_bytes") != ARTIFACT_BYTES
        or artifact.get("complete_sha256") != ARTIFACT_SHA256
    ):
        raise DescriptionError("DRAO_RECEIPT_ARTIFACT_IDENTITY_CHANGED")
    if receipt.get("cleanup", {}).get("payload_retained") is not False:
        raise DescriptionError("DRAO_REPLAY_PAYLOAD_STILL_RETAINED")
    if any(receipt.get("access", {}).get(key, 0) for key in (
        "decompression_attempted",
        "observation_headers_parsed",
        "observation_values_accessed",
        "primary_headers_parsed",
        "primary_payload_bytes",
        "primary_values_accessed",
    )):
        raise DescriptionError("DRAO_RECEIPT_REPLAY_EXCEEDED_CONTENT_BLIND_AUTHORITY")
    frozen.verify_authorities(root)
    return actual


def executor_manifest(root: Path) -> dict[str, object]:
    inputs = verify_frozen_inputs(root)
    value = {
        "schema": "gnss-drao-doy232-qualification-executor-manifest-v1",
        "executor_version": EXECUTOR_VERSION,
        "physical_question": frozen.contract()["physical_question"],
        "new_information": frozen.contract()["new_physical_information_if_executed"],
        "frozen_inputs": inputs,
        "product": {
            "station": frozen.STATION,
            "doy": frozen.QUALIFICATION_DOY,
            "name": ARTIFACT_NAME,
            "url": ARTIFACT_URL,
            "bytes": ARTIFACT_BYTES,
            "sha256": ARTIFACT_SHA256,
            "role": "MODEL_BLIND_CAPABILITY_QUALIFICATION_NEVER_SCORED",
            "fallback": False,
        },
        "window": {
            "start_gps": structural.format_gps_epoch(expected_epochs()[0]),
            "stop_gps": structural.format_gps_epoch(expected_epochs()[-1]),
            "step_s": frozen.STEP_S,
            "raw_epochs": frozen.RAW_EPOCHS,
            "prefix_epochs": frozen.PREFIX_EPOCHS,
            "heldout_epochs": frozen.HELDOUT_EPOCHS,
            "event_time_bound_s": [-15.0, 15.0],
            "qualification_may_reduce_event_time_bound": False,
        },
        "signals": {
            "satellites": list(SATELLITES),
            "core_phase": list(CORE_PHASE),
            "same_path_code": list(SAME_PATH_CODE),
            "optional_diagnostics": list(OPTIONAL_DIAGNOSTICS),
        },
        "rinex_transform": {
            "source": RINEX_SEMANTICS_SOURCE,
            "scale_factor": "DIVIDE_STORED_VALUE_BY_DECLARED_FACTOR;UNITY_IF_ABSENT",
            "phase_shift": (
                "RINEX_VALUE_ALREADY_EQUALS_ORIGINAL_PLUS_DECLARED_SHIFT;"
                "VALIDATE_COVERAGE_AND_DO_NOT_APPLY_A_SECOND_TIME"
            ),
            "receiver_clock_not_applied": (
                "TIME=TIME_R-DT;CODE=CODE_R-DT*C;PHASE=PHASE_R-DT*FREQUENCY"
            ),
            "receiver_clock_applied": "NO_SECOND_CORRECTION",
            "event_time_mapping_tolerance_s": 15.0,
            "mapping_tolerance_does_not_shrink_frozen_event_time_envelope": True,
            "tgd_applied_to_phase": False,
        },
        "health": {
            "geometry_free_second_difference_limit_m": (
                frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
            ),
            "same_path_operator": "C=I-(1/6)11T",
            "prefix_projection": "PER_TRACK_CONSTANT_PLUS_RATE_FIRST_79_ONLY",
            "heldout_refit": False,
            "per_track_heldout_peak_to_peak_limit_m": (
                frozen.PER_TRACK_WITNESS_LIMIT_M
            ),
            "orbital_model_available": False,
            "orbital_scores_produced": 0,
        },
        "transport": {
            "maximum_attempts_before_complete_hash": MAX_TRANSPORT_ATTEMPTS,
            "retry_reasons": ["TIMEOUT", "TRANSPORT_INTERRUPTION"],
            "complete_known_sha256_before_decode": True,
            "retry_after_complete_hash_or_decode": 0,
            "maximum_compressed_bytes": MAX_COMPRESSED_BYTES,
        },
        "persistence": {
            "compressed_artifact": 0,
            "decoded_rinex": 0,
            "observation_values": 0,
            "derived_series": 0,
            "structural_rows_and_aggregate_metrics_only": True,
        },
        "access_at_freeze": {
            "network_requests": 0,
            "qualification_decompressions": 0,
            "qualification_headers": 0,
            "qualification_values": 0,
            "primary_locators": 0,
            "primary_headers": 0,
            "primary_payload_bytes": 0,
            "primary_values": 0,
        },
        "live_execution_authorized": False,
        "new_gate": False,
        "generic_framework": False,
        "stop": "STOP_BEFORE_DRAO_DOY232_DECODE_FOR_SEPARATE_REVIEW",
    }
    strict_json(value)
    return value


def manifest_sha256(root: Path) -> str:
    return sha256(strict_json(executor_manifest(root)).encode("ascii")).hexdigest()


def build_executor_seal(root: Path) -> dict[str, object]:
    manifest = executor_manifest(root)
    value = {
        "schema": "gnss-drao-doy232-qualification-executor-seal-v1",
        "state": "DRAO_DOY232_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED",
        "source_commit": _git_commit(),
        "source_sha256": source_sha256(),
        "manifest_sha256": sha256(strict_json(manifest).encode("ascii")).hexdigest(),
        "dependencies": dependency_versions(),
        "frozen_inputs": manifest["frozen_inputs"],
        "product": manifest["product"],
        "authority": {
            "live_execution_authorized_by_seal": False,
            "separate_review_and_one_use_token_required": True,
        },
        "access_at_seal": manifest["access_at_freeze"],
        "stop": "STOP_BEFORE_DRAO_DOY232_DECODE_FOR_SEPARATE_REVIEW",
    }
    strict_json(value)
    return value


def validate_executor_seal(root: Path, seal_path: Path, expected_sha256: str) -> dict[str, object]:
    if len(expected_sha256) != 64 or file_sha256(seal_path) != expected_sha256:
        raise DescriptionError("EXECUTOR_SEAL_SHA256_CHANGED")
    seal = _read_strict_json(seal_path)
    if seal.get("state") != "DRAO_DOY232_QUALIFICATION_EXECUTOR_FROZEN_UNOPENED":
        raise DescriptionError("EXECUTOR_SEAL_STATE_CHANGED")
    if seal.get("source_sha256") != source_sha256():
        raise DescriptionError("EXECUTOR_SOURCE_CHANGED")
    if seal.get("manifest_sha256") != manifest_sha256(root):
        raise DescriptionError("EXECUTOR_MANIFEST_CHANGED")
    if seal.get("dependencies") != dependency_versions():
        raise DescriptionError("EXECUTOR_DEPENDENCIES_CHANGED")
    if seal.get("authority", {}).get("live_execution_authorized_by_seal") is not False:
        raise DescriptionError("EXECUTOR_SEAL_GRANTED_LIVE_AUTHORITY")
    if any(seal.get("access_at_seal", {}).values()):
        raise DescriptionError("EXECUTOR_SEAL_USED_OBSERVATION")
    return seal


def parse_scale_factors(
    records: Sequence[str], gps_observables: Sequence[str]
) -> dict[str, int]:
    """Compile RINEX 3.04 scale records for the GPS observable set."""

    result = {observable: 1 for observable in gps_observables}
    assigned: set[str] = set()
    index = 0
    while index < len(records):
        raw = records[index].ljust(60)
        system = raw[0:1].strip()
        if not system:
            raise DraoQualificationError("SCALE_FACTOR_CONTINUATION_WITHOUT_RECORD")
        try:
            factor = int(raw[2:6])
            count = int(raw[8:10].strip() or "0")
        except ValueError as exc:
            raise DraoQualificationError("SCALE_FACTOR_RECORD_INVALID") from exc
        if factor not in {1, 10, 100, 1000}:
            raise DraoQualificationError("SCALE_FACTOR_NOT_SUPPORTED")
        observables = raw[11:60].split()
        while count and len(observables) < count:
            index += 1
            if index >= len(records):
                raise DraoQualificationError("SCALE_FACTOR_CONTINUATION_MISSING")
            continuation = records[index].ljust(60)
            if continuation[0:10].strip():
                raise DraoQualificationError("SCALE_FACTOR_CONTINUATION_INVALID")
            observables.extend(continuation[11:60].split())
        if count and len(observables) != count:
            raise DraoQualificationError("SCALE_FACTOR_OBSERVABLE_COUNT_MISMATCH")
        targets = tuple(observables) if count else tuple(gps_observables)
        if system == "G":
            for observable in targets:
                if observable not in result:
                    raise DraoQualificationError(
                        f"SCALE_FACTOR_UNKNOWN_GPS_OBSERVABLE:{observable}"
                    )
                if observable in assigned and result[observable] != factor:
                    raise DraoQualificationError(
                        f"SCALE_FACTOR_CONFLICT:{observable}"
                    )
                result[observable] = factor
                assigned.add(observable)
        index += 1
    return result


def parse_phase_shift_coverage(
    records: Sequence[str], satellites: Sequence[str]
) -> dict[str, dict[str, float]]:
    """Validate explicit L1C/L2W phase-shift coverage without double applying it."""

    result: dict[str, dict[str, float]] = {observable: {} for observable in CORE_PHASE}
    index = 0
    while index < len(records):
        raw = records[index].ljust(60)
        system = raw[0:1].strip()
        observable = raw[2:5].strip()
        if not system or not observable:
            raise DraoQualificationError("PHASE_SHIFT_RECORD_IDENTITY_INVALID")
        try:
            correction = float(raw[6:14].strip().replace("D", "E"))
            count = int(raw[16:18].strip() or "0")
        except ValueError as exc:
            raise DraoQualificationError("PHASE_SHIFT_RECORD_INVALID") from exc
        if not np.isfinite(correction):
            raise DraoQualificationError("PHASE_SHIFT_NONFINITE")
        covered = raw[19:60].split()
        while count and len(covered) < count:
            index += 1
            if index >= len(records):
                raise DraoQualificationError("PHASE_SHIFT_CONTINUATION_MISSING")
            continuation = records[index].ljust(60)
            if continuation[0:18].strip():
                raise DraoQualificationError("PHASE_SHIFT_CONTINUATION_INVALID")
            covered.extend(continuation[19:60].split())
        if count and len(covered) != count:
            raise DraoQualificationError("PHASE_SHIFT_SATELLITE_COUNT_MISMATCH")
        if system == "G" and observable in result:
            targets = tuple(covered) if count else tuple(satellites)
            for satellite in targets:
                if satellite not in satellites:
                    continue
                existing = result[observable].get(satellite)
                if existing is not None and existing != correction:
                    raise DraoQualificationError(
                        f"PHASE_SHIFT_CONFLICT:{observable}:{satellite}"
                    )
                result[observable][satellite] = correction
        index += 1
    for observable, coverage in result.items():
        missing = sorted(set(satellites) - set(coverage))
        if missing:
            raise DraoQualificationError(
                f"PHASE_SHIFT_COVERAGE_INCOMPLETE:{observable}:{','.join(missing)}"
            )
    return result


def _normalize(value: object) -> str:
    return " ".join(str(value).replace("_", " ").split())


def _validate_header(parsed: Mapping[str, object]) -> dict[str, object]:
    if not 3.0 <= float(parsed["rinex_version"]) < 4.0:
        raise DraoQualificationError("RINEX_VERSION_NOT_3")
    if _normalize(parsed["marker_name"]) != "DRAO":
        raise DraoQualificationError("MARKER_NAME_MISMATCH")
    if _normalize(parsed.get("marker_number", "")) != "40105M002":
        raise DraoQualificationError("MARKER_DOMES_MISMATCH")
    receiver = parsed["receiver"]
    antenna = parsed["antenna"]
    if _normalize(receiver["type"]) != _normalize("SEPT_POLARX5"):
        raise DraoQualificationError("RECEIVER_TYPE_MISMATCH")
    if _normalize(receiver["version_or_radome"]) != "5.2.0":
        raise DraoQualificationError("RECEIVER_VERSION_MISMATCH")
    antenna_type = str(antenna["type"]).ljust(20)
    if _normalize(antenna_type[:16]) != "TWIVC6050":
        raise DraoQualificationError("ANTENNA_TYPE_MISMATCH")
    if _normalize(antenna_type[16:20]) != "SCIS":
        raise DraoQualificationError("ANTENNA_RADOME_MISMATCH")
    if float(parsed["interval_s"]) != float(frozen.STEP_S):
        raise DraoQualificationError("INTERVAL_CHANGED")
    first_info = parsed["time_of_first_observation"]
    last_info = parsed["time_of_last_observation"]
    if first_info["time_system"] != "GPS" or last_info["time_system"] != "GPS":
        raise DraoQualificationError("OBSERVATION_TIME_SYSTEM_NOT_GPS")
    first = headers.parse_utc(first_info["utc_like_epoch"])
    last = headers.parse_utc(last_info["utc_like_epoch"])
    epochs = expected_epochs()
    if first > epochs[0] or last < epochs[-1]:
        raise DraoQualificationError("FROZEN_WINDOW_NOT_COVERED")
    if parsed["receiver_clock_offset_applied"] not in {0, 1}:
        raise DraoQualificationError("RECEIVER_CLOCK_SEMANTICS_UNKNOWN")
    gps_types = tuple(parsed["observable_types"].get("G", ()))
    missing = sorted(set(CORE_PHASE + SAME_PATH_CODE) - set(gps_types))
    if missing:
        raise DraoQualificationError(
            f"REQUIRED_SIGNAL_FAMILY_NOT_DECLARED:{','.join(missing)}"
        )
    scales = parse_scale_factors(parsed.get("scale_factor_records", ()), gps_types)
    shifts = parse_phase_shift_coverage(
        parsed.get("phase_shift_records", ()), SATELLITES
    )
    return {
        "station": frozen.STATION,
        "marker_name": parsed["marker_name"],
        "marker_number": parsed["marker_number"],
        "receiver_type": _normalize(receiver["type"]),
        "receiver_version": _normalize(receiver["version_or_radome"]),
        "antenna_type": _normalize(antenna_type[:16]),
        "antenna_radome": _normalize(antenna_type[16:20]),
        "interval_s": float(parsed["interval_s"]),
        "time_of_first_observation": first_info,
        "time_of_last_observation": last_info,
        "receiver_clock_offset_applied": parsed["receiver_clock_offset_applied"],
        "gps_observables": list(gps_types),
        "scale_factors": scales,
        "phase_shift_records": {
            observable: [
                {"satellite": satellite, "cycles": shifts[observable][satellite]}
                for satellite in SATELLITES
            ]
            for observable in CORE_PHASE
        },
        "phase_shift_numerically_applied_again": False,
        "full_frozen_window_covered": True,
    }


def _parse_epoch_clock(line: bytes) -> tuple[datetime, int, int, float | None]:
    try:
        parts = line.decode("ascii", errors="strict").split()
        second = float(parts[6])
        whole = int(second)
        epoch = datetime(
            int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4]),
            int(parts[5]), whole,
            int(round((second - whole) * 1_000_000)),
            tzinfo=timezone.utc,
        )
        clock = float(parts[9].replace("D", "E")) if len(parts) > 9 else None
    except (IndexError, UnicodeDecodeError, ValueError) as exc:
        raise DraoQualificationError("RECORD_INVALID:EPOCH") from exc
    if clock is not None and not np.isfinite(clock):
        raise DraoQualificationError("RECORD_INVALID:NONFINITE_RECEIVER_CLOCK")
    return epoch, int(parts[7]), int(parts[8]), clock


def _grid_index(epoch: datetime) -> tuple[int, float]:
    epochs = expected_epochs()
    distances = [abs((epoch - candidate).total_seconds()) for candidate in epochs]
    ordered = sorted(range(len(epochs)), key=lambda index: (distances[index], index))
    if distances[ordered[0]] > 15.0:
        raise DraoQualificationError("EVENT_TIME_OUTSIDE_FROZEN_BOUND")
    if len(ordered) > 1 and distances[ordered[0]] == distances[ordered[1]]:
        raise DraoQualificationError("EVENT_TIME_GRID_ASSIGNMENT_AMBIGUOUS")
    index = ordered[0]
    return index, float((epoch - epochs[index]).total_seconds())


def _read_window_records(
    reader: rinex._LineReader,
    system_types: Mapping[str, Sequence[str]],
    receiver_clock_offset_applied: int,
) -> tuple[
    dict[tuple[int, str], rinex._Record],
    dict[int, int],
    dict[int, float],
    dict[int, float],
]:
    epochs = expected_epochs()
    start = epochs[0] - timedelta(seconds=15)
    stop = epochs[-1] + timedelta(seconds=15)
    records: dict[tuple[int, str], rinex._Record] = {}
    flags: dict[int, int] = {}
    deviations: dict[int, float] = {}
    clock_corrections: dict[int, float] = {}
    while True:
        line = reader.readline()
        if not line:
            break
        if not line.startswith(b">"):
            if line.strip():
                raise DraoQualificationError("RECORD_INVALID:NON_EPOCH_LINE")
            continue
        raw_epoch, flag, satellite_count, clock = _parse_epoch_clock(line)
        applied_correction = (
            float(clock) if receiver_clock_offset_applied == 0 and clock is not None else 0.0
        )
        epoch = raw_epoch - timedelta(seconds=applied_correction)
        in_window = start <= epoch <= stop
        grid_index: int | None = None
        if in_window:
            grid_index, deviation = _grid_index(epoch)
            if grid_index in flags:
                raise DraoQualificationError("RECORD_INVALID:DUPLICATE_GRID_EPOCH")
            flags[grid_index] = flag
            deviations[grid_index] = deviation
            clock_corrections[grid_index] = applied_correction
        if flag in {2, 3, 4, 5}:
            for _ in range(satellite_count):
                if not reader.readline():
                    raise DraoQualificationError("RECORD_INVALID:TRUNCATED_SPECIAL_EVENT")
            continue
        if flag == 6:
            for _ in range(satellite_count):
                rinex._read_record(reader, system_types)
            continue
        if flag not in {0, 1}:
            raise DraoQualificationError(f"RECORD_INVALID:EPOCH_FLAG_{flag}")
        for _ in range(satellite_count):
            satellite, record = rinex._read_record(reader, system_types)
            if grid_index is None or satellite not in SATELLITES:
                continue
            key = grid_index, satellite
            if key in records:
                raise DraoQualificationError(
                    "RECORD_INVALID:DUPLICATE_SATELLITE_RECORD"
                )
            records[key] = record
    return records, flags, deviations, clock_corrections


def _finite_scalar(field: bytes) -> float | None:
    token = field[:14].strip().replace(b"D", b"E")
    if not token:
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    return float(value) if np.isfinite(value) else None


def _role(observable: str) -> str:
    if observable in CORE_PHASE:
        return "CORE_PHASE"
    if observable in SAME_PATH_CODE:
        return "SAME_PATH_CODE_WITNESS"
    return "OPTIONAL_DIAGNOSTIC"


def scan_decoded(decoded: bytearray) -> QualificationScan:
    reader = rinex._LineReader(decoded)
    try:
        parsed = headers.parse_header_lines(rinex._read_header(reader))
        header = _validate_header(parsed)
    except (headers.HeaderAdmissionError, rinex.QualificationFailure) as exc:
        raise DraoQualificationError(f"HEADER_INVALID:{exc}") from exc
    system_types = {
        system: tuple(values) for system, values in parsed["observable_types"].items()
    }
    gps_types = system_types["G"]
    indices = {
        observable: gps_types.index(observable) if observable in gps_types else None
        for observable in OBSERVABLES
    }
    try:
        records, flags, deviations, clocks = _read_window_records(
            reader, system_types, int(parsed["receiver_clock_offset_applied"])
        )
    except rinex.QualificationFailure as exc:
        raise DraoQualificationError(str(exc)) from exc
    shape = (frozen.RAW_EPOCHS, len(SATELLITES), 2)
    phase = np.full(shape, np.nan, dtype=np.float64)
    code = np.full(shape, np.nan, dtype=np.float64)
    phase_good = np.zeros(shape, dtype=np.bool_)
    code_good = np.zeros(shape, dtype=np.bool_)
    epoch_good = np.zeros(frozen.RAW_EPOCHS, dtype=np.bool_)
    coverage: list[dict[str, object]] = []
    scales = header["scale_factors"]
    for row, epoch in enumerate(expected_epochs()):
        flag = flags.get(row)
        epoch_good[row] = flag == 0
        for sat_index, satellite in enumerate(SATELLITES):
            record = records.get((row, satellite))
            for observable in OBSERVABLES:
                header_index = indices[observable]
                field: bytes | None = None
                if header_index is None:
                    state = BLANK
                    source = "OPTIONAL_OBSERVABLE_NOT_DECLARED"
                    field_count = record.field_count if record else 0
                    continuation = "NOT_APPLICABLE"
                elif record is None:
                    state = BLANK
                    source = "SATELLITE_OR_EPOCH_RECORD_ABSENT"
                    field_count = 0
                    continuation = "NOT_APPLICABLE"
                elif header_index >= record.field_count:
                    state = TRAILING_FIELD_OMITTED
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    field_count = record.field_count
                    continuation = record.continuation_state
                else:
                    field = record.fields[header_index]
                    state = PRESENT if field[:14].strip() else BLANK
                    source = "RINEX_3_OBSERVATION_DATA_RECORD"
                    field_count = record.field_count
                    continuation = record.continuation_state
                lli_state = "NOT_APPLICABLE"
                scalar = _finite_scalar(field) if field is not None else None
                if state == PRESENT and scalar is None:
                    state = RECORD_INVALID
                if observable in CORE_PHASE:
                    target = CORE_PHASE.index(observable)
                    lli_state = rinex._parse_lli(field) if field is not None else "UNAVAILABLE"
                    if state == PRESENT and lli_state == "ZERO_OR_BLANK" and flag == 0:
                        dt = clocks.get(row, 0.0)
                        frequency = frozen.L1_HZ if observable == "L1C" else frozen.L2_HZ
                        phase[row, sat_index, target] = (
                            scalar / scales[observable] - dt * frequency
                        )
                        phase_good[row, sat_index, target] = True
                elif observable in SAME_PATH_CODE:
                    target = SAME_PATH_CODE.index(observable)
                    if state == PRESENT and flag == 0:
                        dt = clocks.get(row, 0.0)
                        code[row, sat_index, target] = (
                            scalar / scales[observable]
                            - dt * frozen.SPEED_OF_LIGHT_M_S
                        )
                        code_good[row, sat_index, target] = True
                coverage.append(
                    {
                        "station": frozen.STATION,
                        "gps_epoch": structural.format_gps_epoch(epoch),
                        "satellite": satellite,
                        "observable": observable,
                        "physical_role": _role(observable),
                        "state": state,
                        "header_declared_index": header_index,
                        "reconstructed_field_count": field_count,
                        "source_line_class": source,
                        "continuation_state": continuation,
                        "lli_state": lli_state,
                        "epoch_flag": flag,
                    }
                )
    expected_rows = frozen.RAW_EPOCHS * len(SATELLITES) * len(OBSERVABLES)
    if len(coverage) != expected_rows:
        phase.fill(0.0)
        code.fill(0.0)
        raise DescriptionError("DRAO_COVERAGE_ROW_COUNT_CHANGED")
    header["event_time"] = {
        "state": "STRUCTURALLY_MAPPED" if len(deviations) == frozen.RAW_EPOCHS else "INCOMPLETE",
        "mapped_epochs": len(deviations),
        "maximum_absolute_grid_deviation_s": (
            max(abs(value) for value in deviations.values()) if deviations else None
        ),
        "frozen_error_bound_s": [-15.0, 15.0],
        "qualification_reduces_bound": False,
        "receiver_clock_correction_epochs": sum(value != 0.0 for value in clocks.values()),
    }
    return QualificationScan(header, coverage, phase, code, phase_good, code_good, epoch_good)


def _fit_prefix_affine(values: np.ndarray) -> np.ndarray:
    x = np.arange(frozen.RAW_EPOCHS, dtype=np.float64) * frozen.STEP_S
    centered_x = x - float(np.mean(x[: frozen.PREFIX_EPOCHS]))
    design = np.column_stack(
        [np.ones(frozen.PREFIX_EPOCHS, dtype=np.float64), centered_x[: frozen.PREFIX_EPOCHS]]
    )
    coefficients, *_ = np.linalg.lstsq(
        design, values[: frozen.PREFIX_EPOCHS], rcond=None
    )
    fitted = coefficients[0] + coefficients[1] * centered_x
    residual = values - fitted
    x.fill(0.0)
    centered_x.fill(0.0)
    design.fill(0.0)
    coefficients.fill(0.0)
    fitted.fill(0.0)
    return residual


def evaluate(scan: QualificationScan) -> dict[str, object]:
    counts = Counter(row["state"] for row in scan.coverage)
    phase_complete = bool(np.all(scan.phase_good) and np.all(scan.epoch_good))
    code_complete = bool(np.all(scan.code_good) and np.all(scan.epoch_good))
    geometry_rows: list[dict[str, object]] = []
    geometry_state = "NOT_EVALUATED"
    if phase_complete:
        geometry_state = "SATISFIED"
        for sat_index, satellite in enumerate(SATELLITES):
            coordinate = (
                LAMBDA_L1_M * scan.phase_cycles[:, sat_index, 0]
                - LAMBDA_L2_M * scan.phase_cycles[:, sat_index, 1]
            )
            second = np.diff(coordinate, n=2)
            maximum = float(np.max(np.abs(second)))
            violations = int(
                np.count_nonzero(
                    np.abs(second) > frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M
                )
            )
            if violations:
                geometry_state = "UNSATISFIED"
            geometry_rows.append(
                {
                    "satellite": satellite,
                    "evaluated_second_differences": int(second.size),
                    "maximum_absolute_second_difference_m": maximum,
                    "violation_count": violations,
                }
            )
            coordinate.fill(0.0)
            second.fill(0.0)

    witness_rows: list[dict[str, object]] = []
    witness_state = "NOT_EVALUATED"
    if phase_complete and code_complete and geometry_state == "SATISFIED":
        phase_if = (
            frozen.IF_L1 * LAMBDA_L1_M * scan.phase_cycles[:, :, 0]
            + frozen.IF_L2 * LAMBDA_L2_M * scan.phase_cycles[:, :, 1]
        )
        code_if = (
            frozen.IF_L1 * scan.code_m[:, :, 0]
            + frozen.IF_L2 * scan.code_m[:, :, 1]
        )
        witness = phase_if - code_if
        centered = witness - np.mean(witness, axis=1, keepdims=True)
        witness_state = "SATISFIED"
        for sat_index, satellite in enumerate(SATELLITES):
            residual = _fit_prefix_affine(centered[:, sat_index])
            heldout = residual[frozen.PREFIX_EPOCHS :]
            peak_to_peak = float(np.ptp(heldout))
            rms = float(np.sqrt(np.mean(heldout**2)))
            state = (
                "SATISFIED"
                if peak_to_peak <= frozen.PER_TRACK_WITNESS_LIMIT_M
                else "UNSATISFIED"
            )
            if state == "UNSATISFIED":
                witness_state = "UNSATISFIED"
            witness_rows.append(
                {
                    "satellite": satellite,
                    "heldout_peak_to_peak_m": peak_to_peak,
                    "heldout_rms_m": rms,
                    "limit_m": frozen.PER_TRACK_WITNESS_LIMIT_M,
                    "state": state,
                }
            )
            residual.fill(0.0)
        phase_if.fill(0.0)
        code_if.fill(0.0)
        witness.fill(0.0)
        centered.fill(0.0)

    if not phase_complete or not code_complete or geometry_state == "UNSATISFIED":
        outcome = "QUALIFICATION_TOPOLOGY_REJECTED"
    elif witness_state == "UNSATISFIED":
        outcome = "QUALIFICATION_PHYSICAL_WITNESS_REJECTED"
    elif witness_state == "SATISFIED":
        outcome = "DRAO_QUALIFICATION_PASSED_PRIMARY_STILL_SEALED"
    else:
        raise DescriptionError("DRAO_OUTCOME_NOT_TOTAL")
    result = {
        "schema": "gnss-drao-doy232-qualification-summary-v1",
        "outcome": outcome,
        "window": executor_manifest(Path(__file__).resolve().parent)["window"],
        "header": scan.header,
        "structural_counts": dict(sorted(counts.items())),
        "coverage_rows": len(scan.coverage),
        "clauses": {
            "artifact_identity": "SATISFIED",
            "header_identity_and_time": "SATISFIED",
            "complete_core_phase": "SATISFIED" if phase_complete else "UNSATISFIED",
            "complete_same_path_code": "SATISFIED" if code_complete else "UNSATISFIED",
            "cycle_slip_and_continuity": geometry_state,
            "physical_same_path_witness": witness_state,
        },
        "geometry_free_phase_health": {
            "state": geometry_state,
            "limit_m": frozen.GEOMETRY_FREE_SECOND_DIFFERENCE_LIMIT_M,
            "links": geometry_rows,
        },
        "same_path_code_phase_witness": {
            "state": witness_state,
            "common_mode_operator": "C=I-(1/6)11T",
            "prefix_epochs": frozen.PREFIX_EPOCHS,
            "heldout_epochs": frozen.HELDOUT_EPOCHS,
            "heldout_refit": False,
            "links": witness_rows,
        },
        "observation_values": {
            "parsed_in_ram": int(np.count_nonzero(np.isfinite(scan.phase_cycles)))
            + int(np.count_nonzero(np.isfinite(scan.code_m))),
            "persisted": 0,
        },
        "derived_series_persisted": 0,
        "orbital_model_used": False,
        "orbital_scores_produced": 0,
        "possible_primary_doy233": "UNSELECTED_UNFROZEN_UNAUTHORISED",
    }
    strict_json(result)
    return result


def materialize() -> tuple[bytearray, dict[str, object]]:
    failures: list[str] = []
    for attempt in range(1, MAX_TRANSPORT_ATTEMPTS + 1):
        payload = bytearray()
        try:
            request = Request(
                ARTIFACT_URL,
                headers={
                    "Accept-Encoding": "identity",
                    "User-Agent": "Satellite-RF-Observatory/DRAO-qualification",
                },
                method="GET",
            )
            with urlopen(request, timeout=HTTP_TIMEOUT_S) as response:
                if int(response.status) != 200 or response.geturl() != ARTIFACT_URL:
                    raise MaterializationError("QUALIFICATION_ARTIFACT_IDENTITY_CHANGED")
                while block := response.read(64 * 1024):
                    payload.extend(block)
                    if len(payload) > MAX_COMPRESSED_BYTES:
                        raise MaterializationError("QUALIFICATION_ARTIFACT_SIZE_LIMIT")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            payload[:] = b"\x00" * len(payload)
            failures.append(f"{type(exc).__name__}:{exc}")
            continue
        if len(payload) != ARTIFACT_BYTES:
            actual = len(payload)
            payload[:] = b"\x00" * len(payload)
            raise MaterializationError(
                f"QUALIFICATION_COMPLETE_BYTE_COUNT_CHANGED:{actual}:{ARTIFACT_BYTES}"
            )
        digest = sha256(payload).hexdigest()
        if digest != ARTIFACT_SHA256:
            payload[:] = b"\x00" * len(payload)
            raise MaterializationError("QUALIFICATION_COMPLETE_SHA256_CHANGED")
        return payload, {
            "name": ARTIFACT_NAME,
            "url": ARTIFACT_URL,
            "attempts": attempt,
            "complete_file_bytes": len(payload),
            "complete_file_sha256": digest,
            "hash_verified_before_decode": True,
        }
    raise MaterializationError(
        "QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED:" + "|".join(failures)
    )


def decompress_in_memory(payload: bytearray) -> bytearray:
    try:
        return bytearray(hatanaka.decompress(bytes(payload), strict=True))
    except Exception as exc:
        raise DescriptionError("HATANAKA_DECOMPRESSION_FAILED") from exc


def _write_json(path: Path, value: object, *, exclusive: bool = False) -> None:
    mode = "x" if exclusive else "w"
    with Path(path).open(mode, encoding="ascii", newline="\n") as stream:
        stream.write(strict_json(value, pretty=True) + "\n")


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        for row in rows:
            stream.write(strict_json(row) + "\n")


def run_once(
    output_directory: Path,
    authority_token: str,
    expected_seal_sha256: str,
    seal_path: Path,
) -> dict[str, object]:
    if authority_token != AUTHORITY_TOKEN:
        raise PermissionError("DRAO_DOY232_QUALIFICATION_AUTHORITY_REQUIRED")
    output = Path(output_directory)
    outcome_path = output / OUTCOME_NAME
    marker_path = output / AUTHORITY_MARKER_NAME
    if outcome_path.exists() or marker_path.exists():
        raise PermissionError("DRAO_DOY232_QUALIFICATION_AUTHORITY_ALREADY_CONSUMED")
    root = Path(__file__).resolve().parent
    seal = validate_executor_seal(root, seal_path, expected_seal_sha256)
    marker = {
        "schema": "gnss-drao-doy232-qualification-authority-consumed-v1",
        "state": "ONE_SHOT_AUTHORITY_CONSUMED_BEFORE_NETWORK",
        "executor_seal_sha256": expected_seal_sha256,
        "source_commit": seal["source_commit"],
        "network_requests_before_marker": 0,
        "qualification_decompressions_before_marker": 0,
        "qualification_values_before_marker": 0,
        "primary_access": 0,
    }
    _write_json(marker_path, marker, exclusive=True)
    compressed: bytearray | None = None
    decoded: bytearray | None = None
    scan: QualificationScan | None = None
    artifact: dict[str, object] | None = None
    try:
        compressed, artifact = materialize()
        decoded = decompress_in_memory(compressed)
        decoded_sha256 = sha256(decoded).hexdigest()
        scan = scan_decoded(decoded)
        summary = evaluate(scan)
        _write_jsonl(output / COVERAGE_NAME, scan.coverage)
        _write_json(output / SUMMARY_NAME, summary, exclusive=True)
        outcome = {
            "schema": "gnss-drao-doy232-qualification-outcome-v1",
            "outcome": summary["outcome"],
            "executor_seal_sha256": expected_seal_sha256,
            "source_commit": seal["source_commit"],
            "source_sha256": seal["source_sha256"],
            "artifact": artifact,
            "decoded_artifact_sha256": decoded_sha256,
            "coverage": {
                "name": COVERAGE_NAME,
                "rows": len(scan.coverage),
                "sha256": file_sha256(output / COVERAGE_NAME),
            },
            "summary": {
                "name": SUMMARY_NAME,
                "sha256": file_sha256(output / SUMMARY_NAME),
            },
            "clauses": summary["clauses"],
            "persistence": {
                "compressed_artifact": 0,
                "decoded_rinex": 0,
                "observation_values": 0,
                "derived_series": 0,
            },
            "orbital_model_used": False,
            "orbital_scores_produced": 0,
            "primary": {
                "doy": 233,
                "state": "UNSELECTED_UNFROZEN_UNAUTHORISED",
                "locators": 0,
                "headers": 0,
                "payload_bytes": 0,
                "values": 0,
            },
        }
    except MaterializationError as exc:
        outcome = {
            "schema": "gnss-drao-doy232-qualification-outcome-v1",
            "outcome": "QUALIFICATION_ARTIFACT_MATERIALIZATION_FAILED",
            "reason": str(exc),
            "clauses": {
                "artifact_identity": "UNSATISFIED",
                "header_identity_and_time": "NOT_EVALUATED",
                "complete_core_phase": "NOT_EVALUATED",
                "complete_same_path_code": "NOT_EVALUATED",
                "cycle_slip_and_continuity": "NOT_EVALUATED",
                "physical_same_path_witness": "NOT_EVALUATED",
            },
            "physical_decision": "NOT_EVALUATED",
        }
    except DraoQualificationError as exc:
        outcome = {
            "schema": "gnss-drao-doy232-qualification-outcome-v1",
            "outcome": "QUALIFICATION_TOPOLOGY_REJECTED",
            "reason": str(exc),
            "physical_decision": "MEASUREMENT_PATH_REJECTED",
            "downstream_clauses": "NOT_EVALUATED",
        }
    except Exception as exc:
        outcome = {
            "schema": "gnss-drao-doy232-qualification-outcome-v1",
            "outcome": "QUALIFICATION_DESCRIPTION_ERROR",
            "reason": f"{type(exc).__name__}:{exc}",
            "physical_decision": "NOT_EVALUATED",
            "downstream_clauses": "NOT_EVALUATED",
        }
    finally:
        if scan is not None:
            scan.erase()
        for payload in (decoded, compressed):
            if payload is not None:
                payload[:] = b"\x00" * len(payload)
        gc.collect()
    strict_json(outcome)
    _write_json(outcome_path, outcome, exclusive=True)
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-seal", type=Path)
    parser.add_argument("--execute-live", action="store_true")
    parser.add_argument("--authority", default="")
    parser.add_argument("--seal", type=Path)
    parser.add_argument("--seal-sha256", default="")
    parser.add_argument(
        "--output-directory", type=Path, default=Path(__file__).resolve().parent
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    if args.write_seal is not None:
        _write_json(args.write_seal, build_executor_seal(root), exclusive=True)
        return
    if args.execute_live:
        if args.seal is None:
            raise SystemExit("EXECUTOR_SEAL_REQUIRED")
        print(
            strict_json(
                run_once(
                    args.output_directory,
                    args.authority,
                    args.seal_sha256,
                    args.seal,
                )
            )
        )
        return
    print(strict_json(executor_manifest(root), pretty=True))


if __name__ == "__main__":
    main()
