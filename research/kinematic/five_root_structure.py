"""Target-free structural qualification for four fit roots plus GOLD held out."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
import urllib.error

import hatanaka

from .phase_transform_header_audit import (
    HeaderRejected,
    _collect_headers,
    audit_header as audit_phase_header,
)
from .real_reference_qualification import _download
from .rinex_observations import _time


ROOT = Path(__file__).resolve().parents[2]
TERMINALS = {
    "FIVE_ROOT_STRUCTURE_QUALIFIED",
    "FIVE_ROOT_STRUCTURE_NOT_QUALIFIED",
    "FIVE_ROOT_STRUCTURE_EXECUTION_INVALID",
}
GPS_IDS = tuple(f"G{number:02d}" for number in range(1, 33))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def all_roots(plan: dict) -> list[dict]:
    return [*plan["fit_roots"], plan["heldout_root"]]


def validate_plan(plan: dict) -> None:
    if plan.get("schema") != "s2-five-root-structure-qualification-plan-v1":
        raise ValueError("unexpected structural plan")
    if date.fromisoformat(plan["date_gpst"]).timetuple().tm_yday != plan["day_of_year"]:
        raise ValueError("date/day-of-year mismatch")
    roots = all_roots(plan)
    if ([row["id"] for row in roots]
            != ["ALGO00CAN", "BOGT00COL", "MKEA00USA", "PIE100USA", "GOLD00USA"]):
        raise ValueError("frozen root topology differs")
    if len({row["id"] for row in roots}) != 5 or len(plan["fit_roots"]) != 4:
        raise ValueError("exact four-fit/one-heldout topology required")
    obs = plan["observation"]
    if (obs["fit_fields"] != ["C1C", "C2W", "L1C", "L2W"]
            or obs["heldout_fields"] != ["C1C", "C2W"]
            or obs["required_interval_s"] != 30.0
            or obs["required_time_system"] != "GPS"
            or not obs["no_interpolation"] or not obs["no_gap_bridging"]
            or obs["observation_numeric_conversion"]):
        raise ValueError("frozen structural coordinate differs")
    capacity = plan["structural_capacity"]
    if (capacity["endpoint_count"] != 11
            or capacity["minimum_non_target_reference_count_per_root"] != 4
            or capacity["candidate_identity_persisted"]
            or not capacity["qualification_is_not_target_selection"]):
        raise ValueError("structural capacity rule differs")
    artifact = plan["artifact_selection"]
    if (not artifact["not_a_date_search"] or not artifact["no_retry"]
            or not artifact["no_date_station_or_field_substitution"]
            or artifact["minimum_archive_age_after_last_epoch_s"] < 86400):
        raise ValueError("bounded artifact rule differs")
    if not all(plan["execution"].values()):
        raise ValueError("bounded execution clauses required")
    if set(plan["outcomes"]) != TERMINALS:
        raise ValueError("terminal set differs")
    frozen = plan["frozen_inputs"]
    for file_key, hash_key in (
        ("phase_header_result", "phase_header_result_sha256"),
        ("four_fit_one_heldout_result", "four_fit_one_heldout_result_sha256"),
    ):
        if sha256_path(ROOT / frozen[file_key]) != frozen[hash_key]:
            raise ValueError(file_key + " hash mismatch")


def admit_archive_age(plan: dict, now: datetime | None = None) -> None:
    values = plan["observation"]["required_last_epoch"]
    whole = int(values[5])
    last = datetime(*values[:5], whole, tzinfo=timezone.utc)
    last += timedelta(seconds=values[5] - whole)
    if (now or datetime.now(timezone.utc)) < last + timedelta(
            seconds=plan["artifact_selection"]["minimum_archive_age_after_last_epoch_s"]):
        raise ValueError("FROZEN_FULL_DAY_PRODUCT_NOT_MATURE")


def admit_git_freeze(plan_path: Path, source_commit: str) -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT, text=True
    )
    if status.strip():
        raise ValueError("working tree must be clean before source access")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != source_commit:
        raise ValueError("source commit differs from HEAD")
    for path in (plan_path, Path(__file__)):
        relative = path.resolve().relative_to(ROOT).as_posix()
        if subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT) != path.read_bytes():
            raise ValueError("frozen file differs from committed bytes:" + relative)


def _header_lines(content: str) -> list[str]:
    output = []
    for line in content.splitlines():
        output.append(line)
        if line[60:80].strip() == "END OF HEADER":
            return output
    raise HeaderRejected("MISSING_END_OF_HEADER")


def _header_plan(plan: dict) -> dict:
    obs = plan["observation"]
    return {"source": {
        "required_rinex_versions": obs["required_rinex_versions"],
        "required_time_system": obs["required_time_system"],
        "required_interval_s": obs["required_interval_s"],
        "required_first_epoch": obs["required_first_epoch"],
        "required_last_epoch": obs["required_last_epoch"],
    }}


def _admit_transform(ledger: dict, plan: dict) -> None:
    required = plan["transform_admission"]
    if ledger["stored_value_scale_divisor"] != required["stored_value_scale_divisor"]:
        raise HeaderRejected("NON_UNIT_REQUIRED_SCALE_FACTOR")
    phase = ledger["phase_shift"]
    for name, expected in required["required_phase_default_cycles"].items():
        if (phase[name]["default_cycles"] != expected
                or (not required["satellite_phase_overrides_allowed"]
                    and phase[name]["satellite_overrides_cycles"])):
            raise HeaderRejected("PHASE_SHIFT_DIFFERS_FROM_PLAN:" + name)
    if ledger["legacy_wavelength_factor"]["present"]:
        raise HeaderRejected("LEGACY_WAVELENGTH_HEADER_NOT_ADMITTED")
    if any(ledger["external_corrections"].values()):
        raise HeaderRejected("APPLIED_EXTERNAL_CORRECTION_NOT_ADMITTED")
    if ledger["receiver_clock_offset_applied"]:
        raise HeaderRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")


def _field_state(record: str, index: int) -> tuple[bool, str]:
    field = record[3 + 16 * index:3 + 16 * (index + 1)].ljust(16)
    return bool(field[:14].strip()), field[14]


def _seconds_in_frozen_day(epoch: list[float | int]) -> float:
    return float(epoch[3] * 3600 + epoch[4] * 60 + epoch[5])


def _aggregate_segments(eligible: dict[float, set[str]], step: float) -> dict:
    maxima = []
    for satellite in GPS_IDS:
        tags = sorted(tag for tag, values in eligible.items() if satellite in values)
        longest = current = 0
        previous = None
        for tag in tags:
            current = current + 1 if previous is not None and abs(tag - previous - step) <= 1e-7 else 1
            longest = max(longest, current)
            previous = tag
        if longest:
            maxima.append(longest)
    return {
        "gps_satellites_with_any_usable_row": len(maxima),
        "maximum_contiguous_endpoints": max(maxima, default=0),
        "satellites_with_at_least_11_contiguous_endpoints": sum(value >= 11 for value in maxima),
        "per_satellite_identity_persisted": False,
    }


def scan_structure(content: str, plan: dict, station_plan: dict, role: str) -> tuple[dict, dict]:
    lines = content.splitlines()
    header = _header_lines(content)
    header_result = audit_phase_header(header, _header_plan(plan), station_plan["id"])
    if header_result["marker_name"].upper() != station_plan["marker"]:
        raise HeaderRejected("MARKER_IDENTITY_DIFFERS")
    if header_result["receiver_identity"] != station_plan["expected_receiver"]:
        raise HeaderRejected("RECEIVER_IDENTITY_CHANGED")
    _admit_transform(header_result["transform_ledger"], plan)
    headers, systems = _collect_headers(header)
    for label in ("ANT # / TYPE", "APPROX POSITION XYZ", "ANTENNA: DELTA H/E/N"):
        if len(headers.get(label, [])) != 1:
            raise HeaderRejected("MISSING_OR_DUPLICATE_HEADER:" + label)
    try:
        geometry = [float(value) for label in ("APPROX POSITION XYZ", "ANTENNA: DELTA H/E/N")
                    for value in headers[label][0].split()]
    except ValueError as error:
        raise HeaderRejected("INVALID_STATION_GEOMETRY") from error
    if len(geometry) != 6 or not all(math.isfinite(value) for value in geometry):
        raise HeaderRejected("INVALID_STATION_GEOMETRY")
    types = systems.get("G", [])
    required = plan["observation"]["fit_fields" if role == "FIT" else "heldout_fields"]
    if any(name not in types for name in required):
        raise HeaderRejected("MISSING_REQUIRED_FIELDS_FOR_" + role)
    indices = {name: types.index(name) for name in required}
    header_end = len(header)
    eligible: dict[float, set[str]] = {}
    structural_counts = {
        "gps_rows": 0, "usable_rows": 0, "blank_required_field_rows": 0,
        "nonzero_phase_lli_rows": 0, "event_epoch_count": 0,
    }
    epoch_times, previous = [], None
    index = header_end
    while index < len(lines):
        epoch = lines[index]
        index += 1
        if not epoch.startswith(">"):
            raise HeaderRejected("EXPECTED_EPOCH_RECORD")
        fields = epoch[1:].split()
        if len(fields) not in (8, 9):
            raise HeaderRejected("INVALID_EPOCH_RECORD")
        tag = _time(fields[:6], plan["date_gpst"], 0)
        try:
            flag, count = int(fields[6]), int(fields[7])
        except ValueError as error:
            raise HeaderRejected("INVALID_EPOCH_RECORD") from error
        if previous is not None and tag <= previous:
            raise HeaderRejected("DUPLICATE_OR_UNORDERED_EPOCH")
        if count < 0 or index + count > len(lines):
            raise HeaderRejected("TRUNCATED_OR_INVALID_EPOCH_BLOCK")
        block, index = lines[index:index + count], index + count
        previous = tag
        epoch_times.append(tag)
        usable = set()
        if flag != 0:
            structural_counts["event_epoch_count"] += 1
            eligible[tag] = usable
            continue
        seen = set()
        for record in block:
            satellite = record[:3]
            if satellite not in GPS_IDS:
                continue
            if satellite in seen:
                raise HeaderRejected("DUPLICATE_GPS_SATELLITE_ROW")
            seen.add(satellite)
            structural_counts["gps_rows"] += 1
            states = {name: _field_state(record, indices[name]) for name in required}
            if not all(value[0] for value in states.values()):
                structural_counts["blank_required_field_rows"] += 1
                continue
            if role == "FIT" and any(states[name][1] not in (" ", "0") for name in ("L1C", "L2W")):
                structural_counts["nonzero_phase_lli_rows"] += 1
                continue
            usable.add(satellite)
            structural_counts["usable_rows"] += 1
        eligible[tag] = usable
    obs = plan["observation"]
    expected_first = _seconds_in_frozen_day(obs["required_first_epoch"])
    expected_last = _seconds_in_frozen_day(obs["required_last_epoch"])
    if (not epoch_times or epoch_times[0] != expected_first or epoch_times[-1] != expected_last):
        raise HeaderRejected("ACTUAL_EPOCHS_DO_NOT_COVER_FROZEN_DAY")
    gaps = [b - a for a, b in zip(epoch_times, epoch_times[1:])
            if abs(b - a - obs["required_interval_s"]) > 1e-7]
    summary = {
        "station": station_plan["id"], "role": role,
        "status": "STATION_STRUCTURE_SCANNED",
        "receiver_identity": header_result["receiver_identity"],
        "marker_name": header_result["marker_name"],
        "rinex_version": header_result["rinex_version"],
        "interval_s": header_result["interval_s"],
        "epoch_count": len(epoch_times), "first_epoch_s": epoch_times[0],
        "last_epoch_s": epoch_times[-1], "non_nominal_gap_count": len(gaps),
        "maximum_gap_s": max(gaps, default=obs["required_interval_s"]),
        "structural_counts": structural_counts,
        "segment_summary": _aggregate_segments(eligible, obs["required_interval_s"]),
        "transform_ledger": header_result["transform_ledger"],
        "observation_numbers_converted": 0,
    }
    return summary, eligible


def evaluate_capacity(structures: dict[str, dict[float, set[str]]], plan: dict) -> dict:
    step = plan["observation"]["required_interval_s"]
    count = plan["structural_capacity"]["endpoint_count"]
    roots = all_roots(plan)
    first = _seconds_in_frozen_day(plan["observation"]["required_first_epoch"])
    last = _seconds_in_frozen_day(plan["observation"]["required_last_epoch"])
    final_start = last - (count - 1) * step
    capable, max_candidates, earliest = 0, 0, None
    for start_index in range(int((final_start - first) / step) + 1):
        start = first + start_index * step
        tags = [start + offset * step for offset in range(count)]
        stable = {}
        for root in roots:
            station = root["id"]
            if any(tag not in structures[station] for tag in tags):
                stable = {}
                break
            stable[station] = set.intersection(*(structures[station][tag] for tag in tags))
        if len(stable) != len(roots) or any(len(values) < 5 for values in stable.values()):
            continue
        common = set.intersection(*stable.values())
        candidate_count = sum(all(len(values - {candidate}) >= 4 for values in stable.values())
                              for candidate in common)
        if candidate_count:
            capable += 1
            max_candidates = max(max_candidates, candidate_count)
            earliest = start if earliest is None else earliest
    return {
        "endpoint_count": count,
        "capable_window_count": capable,
        "earliest_capable_window_start_s": earliest,
        "maximum_unselected_common_candidate_count": max_candidates,
        "candidate_identity_persisted": False,
        "qualified": capable > 0,
    }


def run(plan_path: Path, source_commit: str) -> dict:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan)
    admit_archive_age(plan)
    admit_git_freeze(plan_path, source_commit)
    receipts, summaries, structures, failures = [], {}, {}, []
    execution_invalid = False
    artifact = plan["artifact_selection"]
    for index, station_plan in enumerate(all_roots(plan)):
        station = station_plan["id"]
        role = "FIT" if index < 4 else "HELDOUT_CODE"
        url = artifact["base_url"] + artifact["filename"].format(station=station)
        try:
            compressed, receipt = _download(url, artifact["maximum_compressed_bytes_per_station"])
            receipts.append({"station": station, **receipt})
        except urllib.error.HTTPError as error:
            receipts.append({"station": station, "url": url, "http_status": error.code,
                             "access_utc": utc_now(), "artifact_materialized": False})
            failures.append({"station": station, "stage": "SOURCE_MATERIALIZATION",
                             "classification": "CAPABILITY_REJECTED",
                             "reason": f"SOURCE_HTTP_{error.code}"})
            continue
        except Exception as error:
            execution_invalid = True
            failures.append({"station": station, "stage": "SOURCE_MATERIALIZATION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
            continue
        try:
            decoded = hatanaka.decompress(compressed, strict=True)
            if len(decoded) > artifact["maximum_decoded_bytes_per_station"]:
                raise ValueError("decoded artifact exceeds frozen byte bound")
            receipts[-1].update({"decoded_bytes": len(decoded),
                                 "decoded_sha256": sha256_bytes(decoded),
                                 "complete_artifact_hashed_before_decode": True})
            content = decoded.decode("ascii")
            summary, eligible = scan_structure(content, plan, station_plan, role)
            summaries[station], structures[station] = summary, eligible
        except HeaderRejected as error:
            failures.append({"station": station, "stage": "STRUCTURAL_ADMISSION",
                             "classification": "CAPABILITY_REJECTED", "reason": error.reason})
        except Exception as error:
            execution_invalid = True
            failures.append({"station": station, "stage": "STRUCTURAL_EXECUTION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
    capacity = evaluate_capacity(structures, plan) if len(structures) == 5 else None
    admitted = not failures and capacity is not None and capacity["qualified"]
    status = ("FIVE_ROOT_STRUCTURE_EXECUTION_INVALID" if execution_invalid
              else "FIVE_ROOT_STRUCTURE_QUALIFIED" if admitted
              else "FIVE_ROOT_STRUCTURE_NOT_QUALIFIED")
    result = {
        "schema": "s2-five-root-structure-qualification-result-v1",
        "qualification_id": plan["qualification_id"], "status": status,
        "scope": plan["scope"],
        "freeze": {"source_commit": source_commit,
                   "plan_sha256": sha256_path(plan_path),
                   "implementation_sha256": sha256_path(Path(__file__))},
        "source_receipts": receipts, "station_structures": summaries,
        "cross_root_capacity": capacity, "failures": failures,
        "clauses": {
            "COMPLETE_FIVE_ARTIFACT_SET": "SATISFIED" if len(receipts) == 5 and all("sha256" in row for row in receipts) else "NOT_SATISFIED",
            "HEADER_AND_TRANSFORM_ADMISSION": "SATISFIED" if len(summaries) == 5 else "NOT_SATISFIED",
            "STRUCTURAL_COMMON_WINDOW": "SATISFIED" if capacity and capacity["qualified"] else "NOT_EVALUATED" if capacity is None else "NOT_SATISFIED",
            "OBSERVATION_NUMERIC_ADMISSION": "NOT_EVALUATED",
            "TOTAL_PHYSICAL_ERROR_ENVELOPE": "NOT_EVALUATED",
        },
        "interpretation": {
            "target_selected": False, "target_identity_persisted": False,
            "observation_numbers_converted": 0, "s3_authorized": False,
            "next_step_if_qualified": "Freeze a distinct target-free reference-only numerical qualification; do not reuse this artifact as a primary.",
        },
        "persistence": plan["persistence"],
        "environment": {"python": platform.python_version(),
                        "hatanaka": getattr(hatanaka, "__version__", "unknown")},
    }
    if status not in TERMINALS:
        raise AssertionError("non-terminal result")
    json.dumps(result, allow_nan=False, sort_keys=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing result")
    result = run(args.plan, args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "failures": result["failures"],
                      "capacity": result["cross_root_capacity"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
