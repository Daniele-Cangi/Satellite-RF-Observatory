"""Role-specific target-free structural qualification for four fit roots and GOLD."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import platform
import subprocess
import urllib.error

import hatanaka

from .five_root_structure import (
    GPS_IDS,
    ROOT,
    _aggregate_segments,
    _field_state,
    _header_lines,
    _seconds_in_frozen_day,
    all_roots,
    evaluate_capacity,
    sha256_bytes,
    sha256_path,
    utc_now,
)
from .phase_transform_header_audit import (
    HeaderRejected,
    _collect_headers,
    _external_corrections,
    _parse_epoch_header,
    audit_header as audit_phase_header,
)
from .real_reference_qualification import _download
from .rinex_observations import _time


TERMINALS = {
    "FIVE_ROOT_ROLE_STRUCTURE_QUALIFIED",
    "FIVE_ROOT_ROLE_STRUCTURE_NOT_QUALIFIED",
    "FIVE_ROOT_ROLE_STRUCTURE_EXECUTION_INVALID",
}


def _header_plan(plan: dict) -> dict:
    obs = plan["observation"]
    return {"source": {
        "required_rinex_versions": obs["required_rinex_versions"],
        "required_time_system": obs["required_time_system"],
        "required_interval_s": obs["required_interval_s"],
        "required_first_epoch": obs["required_first_epoch"],
        "required_last_epoch": obs["required_last_epoch"],
    }}


def validate_plan(plan: dict) -> None:
    if plan.get("schema") != "s2-five-root-role-structure-qualification-plan-v1":
        raise ValueError("unexpected role-specific structural plan")
    if plan.get("qualification_id") != "S2_FIVE_ROOT_ROLE_STRUCTURE_2026241":
        raise ValueError("qualification identity differs")
    if plan.get("date_gpst") != "2026-08-29" or plan.get("day_of_year") != 241:
        raise ValueError("distinct frozen day differs")
    if date.fromisoformat(plan["date_gpst"]).timetuple().tm_yday != 241:
        raise ValueError("date/day-of-year mismatch")
    roots = all_roots(plan)
    if [row["id"] for row in roots] != [
            "ALGO00CAN", "BOGT00COL", "MKEA00USA", "PIE100USA", "GOLD00USA"]:
        raise ValueError("frozen root topology differs")
    if len(plan["fit_roots"]) != 4 or len({row["id"] for row in roots}) != 5:
        raise ValueError("exact four-fit/one-heldout topology required")
    obs = plan["observation"]
    if (obs["fit_fields"] != ["C1C", "C2W", "L1C", "L2W"]
            or obs["heldout_fields"] != ["C1C", "C2W"]
            or obs["required_interval_s"] != 30.0
            or obs["required_time_system"] != "GPS"
            or not obs["no_interpolation"] or not obs["no_gap_bridging"]
            or obs["observation_numeric_conversion"]):
        raise ValueError("frozen structural coordinate differs")
    selection = plan["artifact_selection"]
    if (not selection["not_a_date_search"]
            or selection["previously_accessed_for_this_topology"]
            or selection["forbidden_retry_day_of_year"] != 242
            or not selection["no_retry"]
            or not selection["no_date_station_or_field_substitution"]
            or selection["base_url"] != "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/241/"
            or selection["filename"] != "{station}_R_20262410000_01D_30S_MO.crx.gz"
            or selection["minimum_archive_age_after_last_epoch_s"] < 86400):
        raise ValueError("bounded distinct-artifact rule differs")
    semantics = plan["transform_admission"]
    fit = semantics["fit"]
    heldout = semantics["heldout_code"]
    if (fit["stored_value_scale_divisor"]
            != {"C1C": 1, "C2W": 1, "L1C": 1, "L2W": 1}
            or fit["phase_shift_semantics"]
            != "DECLARED_STATIC_OFFSETS_RETAINED_AND_REVERSIBLE"
            or not fit["same_satellite_interval_difference_cancels_stable_offset"]
            or not fit["satellite_phase_overrides_allowed_if_declared"]
            or fit["legacy_wavelength_header_allowed"]
            or fit["applied_gps_dcb_or_pcv_allowed"]
            or fit["receiver_clock_offset_applied"]):
        raise ValueError("fit transform semantics differ")
    if (heldout["stored_value_scale_divisor"] != {"C1C": 1, "C2W": 1}
            or heldout["phase_transform_in_causal_path"]
            or heldout["phase_transform_headers_interpreted"]
            or heldout["applied_gps_dcb_or_pcv_allowed"]
            or heldout["receiver_clock_offset_applied"]):
        raise ValueError("heldout code transform semantics differ")
    capacity = plan["structural_capacity"]
    if (capacity["endpoint_count"] != 11
            or capacity["minimum_non_target_reference_count_per_root"] != 4
            or capacity["candidate_identity_persisted"]
            or not capacity["qualification_is_not_target_selection"]):
        raise ValueError("structural capacity rule differs")
    if not all(plan["execution"].values()) or set(plan["outcomes"]) != TERMINALS:
        raise ValueError("bounded execution or terminal set differs")
    frozen = plan["frozen_inputs"]
    for file_key, hash_key in (
        ("phase_header_result", "phase_header_result_sha256"),
        ("four_fit_one_heldout_result", "four_fit_one_heldout_result_sha256"),
        ("closed_doy242_failure_attribution", "closed_doy242_failure_attribution_sha256"),
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


def _parse_code_scale_factors(rows: list[str], gps_types: list[str]) -> dict[str, int]:
    factors = {name: 1 for name in gps_types}
    assigned: dict[str, int] = {}
    pending = None
    for row in rows:
        system = row[0]
        if system.strip():
            try:
                factor = int(row[2:6])
                count = int(row[8:10].strip() or "0")
            except ValueError as error:
                raise HeaderRejected("INVALID_SCALE_FACTOR") from error
            if system not in "GRECSJI" or factor not in {1, 10, 100, 1000} or count < 0:
                raise HeaderRejected("INVALID_SCALE_FACTOR")
            pending = {"system": system, "factor": factor, "count": count, "types": []}
        elif pending is None or row[:10].strip():
            raise HeaderRejected("ORPHAN_SCALE_FACTOR_CONTINUATION")
        values = [row[offset + 1:offset + 4].strip() for offset in range(10, 58, 4)]
        pending["types"].extend(item for item in values if item)
        if len(pending["types"]) > pending["count"]:
            raise HeaderRejected("SCALE_FACTOR_COUNT_MISMATCH")
        if len(pending["types"]) == pending["count"]:
            if pending["system"] == "G":
                affected = gps_types if pending["count"] == 0 else pending["types"]
                if any(item not in gps_types for item in affected):
                    raise HeaderRejected("SCALE_FACTOR_SCOPE_MISMATCH")
                for item in affected:
                    if item in assigned and assigned[item] != pending["factor"]:
                        raise HeaderRejected("CONFLICTING_SCALE_FACTOR")
                    assigned[item] = pending["factor"]
                    factors[item] = pending["factor"]
            pending = None
    if pending is not None:
        raise HeaderRejected("INCOMPLETE_SCALE_FACTOR")
    return {name: factors[name] for name in ("C1C", "C2W")}


def _audit_code_header(lines: list[str], plan: dict, station: str) -> dict:
    headers, systems = _collect_headers(lines)
    mandatory = (
        "RINEX VERSION / TYPE", "MARKER NAME", "REC # / TYPE / VERS", "INTERVAL",
        "TIME OF FIRST OBS", "TIME OF LAST OBS", "END OF HEADER",
    )
    for label in mandatory:
        if len(headers.get(label, [])) != 1:
            raise HeaderRejected("MISSING_OR_DUPLICATE_HEADER:" + label)
    version = headers["RINEX VERSION / TYPE"][0]
    if (version[:9].strip() not in plan["observation"]["required_rinex_versions"]
            or version[20:21] != "O" or version[40:41] not in ("G", "M")):
        raise HeaderRejected("UNSUPPORTED_OBSERVATION_FORMAT")
    gps_types = systems.get("G", [])
    if any(name not in gps_types for name in ("C1C", "C2W")):
        raise HeaderRejected("MISSING_REQUIRED_GPS_CODE_OBSERVABLE")
    try:
        interval = float(headers["INTERVAL"][0])
    except ValueError as error:
        raise HeaderRejected("INVALID_INTERVAL") from error
    if interval != plan["observation"]["required_interval_s"]:
        raise HeaderRejected("INTERVAL_DIFFERS_FROM_PLAN")
    first_row, last_row = headers["TIME OF FIRST OBS"][0], headers["TIME OF LAST OBS"][0]
    if (first_row[48:51] != "GPS" or last_row[48:51] != "GPS"):
        raise HeaderRejected("NON_GPST_TIME_SYSTEM")
    first = _parse_epoch_header(first_row, "TIME_OF_FIRST_OBS")
    last = _parse_epoch_header(last_row, "TIME_OF_LAST_OBS")
    if (first != plan["observation"]["required_first_epoch"]
            or last != plan["observation"]["required_last_epoch"]):
        raise HeaderRejected("HEADER_DOES_NOT_COVER_FROZEN_DAY")
    clock_rows = headers.get("RCV CLOCK OFFS APPL", [])
    if len(clock_rows) > 1 or (clock_rows and clock_rows[0].strip() != "0"):
        raise HeaderRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")
    receiver = headers["REC # / TYPE / VERS"][0]
    identity = [receiver[offset:offset + 20].strip() for offset in (0, 20, 40)]
    if not all(identity):
        raise HeaderRejected("INCOMPLETE_RECEIVER_IDENTITY")
    scale = _parse_code_scale_factors(headers.get("SYS / SCALE FACTOR", []), gps_types)
    external = _external_corrections(headers)
    return {
        "station": station,
        "status": "HEADER_CODE_TRANSFORMS_QUALIFIED",
        "rinex_version": version[:9].strip(),
        "marker_name": headers["MARKER NAME"][0].strip(),
        "receiver_identity": identity,
        "interval_s": interval,
        "first_observation_gpst": first,
        "last_observation_gpst": last,
        "gps_observation_types": gps_types,
        "transform_ledger": {
            "stored_value_scale_divisor": scale,
            "external_corrections": external,
            "receiver_clock_offset_applied": False,
            "phase_transform": "NOT_INTERPRETED_OUTSIDE_CAUSAL_PATH",
        },
    }


def _admit_fit_transform(ledger: dict, plan: dict) -> None:
    required = plan["transform_admission"]["fit"]
    if ledger["stored_value_scale_divisor"] != required["stored_value_scale_divisor"]:
        raise HeaderRejected("NON_UNIT_REQUIRED_SCALE_FACTOR")
    for name in ("L1C", "L2W"):
        item = ledger["phase_shift"][name]
        values = [item["default_cycles"], *item["satellite_overrides_cycles"].values()]
        if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
            raise HeaderRejected("NON_STATIC_OR_INVALID_PHASE_SHIFT:" + name)
    if ledger["legacy_wavelength_factor"]["present"]:
        raise HeaderRejected("LEGACY_WAVELENGTH_HEADER_NOT_ADMITTED")
    if any(ledger["external_corrections"].values()):
        raise HeaderRejected("APPLIED_EXTERNAL_CORRECTION_NOT_ADMITTED")
    if ledger["receiver_clock_offset_applied"]:
        raise HeaderRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")


def _admit_code_transform(ledger: dict, plan: dict) -> None:
    required = plan["transform_admission"]["heldout_code"]
    if ledger["stored_value_scale_divisor"] != required["stored_value_scale_divisor"]:
        raise HeaderRejected("NON_UNIT_REQUIRED_CODE_SCALE_FACTOR")
    if any(ledger["external_corrections"].values()):
        raise HeaderRejected("APPLIED_EXTERNAL_CODE_CORRECTION_NOT_ADMITTED")
    if ledger["receiver_clock_offset_applied"]:
        raise HeaderRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")


def scan_structure(content: str, plan: dict, station_plan: dict, role: str) -> tuple[dict, dict]:
    lines = content.splitlines()
    header = _header_lines(content)
    if role == "FIT":
        header_result = audit_phase_header(header, _header_plan(plan), station_plan["id"])
        _admit_fit_transform(header_result["transform_ledger"], plan)
    elif role == "HELDOUT_CODE":
        header_result = _audit_code_header(header, plan, station_plan["id"])
        _admit_code_transform(header_result["transform_ledger"], plan)
    else:
        raise ValueError("unknown role")
    if header_result["marker_name"].upper() != station_plan["marker"]:
        raise HeaderRejected("MARKER_IDENTITY_DIFFERS")
    if header_result["receiver_identity"] != station_plan["expected_receiver"]:
        raise HeaderRejected("RECEIVER_IDENTITY_CHANGED")
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
    eligible: dict[float, set[str]] = {}
    counts = {"gps_rows": 0, "usable_rows": 0, "blank_required_field_rows": 0,
              "nonzero_phase_lli_rows": 0, "event_epoch_count": 0}
    epoch_times, previous = [], None
    index = len(header)
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
            counts["event_epoch_count"] += 1
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
            counts["gps_rows"] += 1
            states = {name: _field_state(record, indices[name]) for name in required}
            if not all(value[0] for value in states.values()):
                counts["blank_required_field_rows"] += 1
                continue
            if role == "FIT" and any(states[name][1] not in (" ", "0")
                                     for name in ("L1C", "L2W")):
                counts["nonzero_phase_lli_rows"] += 1
                continue
            usable.add(satellite)
            counts["usable_rows"] += 1
        eligible[tag] = usable
    obs = plan["observation"]
    expected_first = _seconds_in_frozen_day(obs["required_first_epoch"])
    expected_last = _seconds_in_frozen_day(obs["required_last_epoch"])
    if not epoch_times or epoch_times[0] != expected_first or epoch_times[-1] != expected_last:
        raise HeaderRejected("ACTUAL_EPOCHS_DO_NOT_COVER_FROZEN_DAY")
    gaps = [b - a for a, b in zip(epoch_times, epoch_times[1:])
            if abs(b - a - obs["required_interval_s"]) > 1e-7]
    summary = {
        "station": station_plan["id"], "role": role,
        "status": "STATION_ROLE_STRUCTURE_SCANNED",
        "receiver_identity": header_result["receiver_identity"],
        "marker_name": header_result["marker_name"],
        "rinex_version": header_result["rinex_version"],
        "interval_s": header_result["interval_s"],
        "epoch_count": len(epoch_times), "first_epoch_s": epoch_times[0],
        "last_epoch_s": epoch_times[-1], "non_nominal_gap_count": len(gaps),
        "maximum_gap_s": max(gaps, default=obs["required_interval_s"]),
        "structural_counts": counts,
        "segment_summary": _aggregate_segments(eligible, obs["required_interval_s"]),
        "transform_ledger": header_result["transform_ledger"],
        "observation_numbers_converted": 0,
    }
    return summary, eligible


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
            summary, eligible = scan_structure(decoded.decode("ascii"), plan, station_plan, role)
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
    status = ("FIVE_ROOT_ROLE_STRUCTURE_EXECUTION_INVALID" if execution_invalid
              else "FIVE_ROOT_ROLE_STRUCTURE_QUALIFIED" if admitted
              else "FIVE_ROOT_ROLE_STRUCTURE_NOT_QUALIFIED")
    result = {
        "schema": "s2-five-root-role-structure-qualification-result-v1",
        "qualification_id": plan["qualification_id"], "status": status,
        "scope": plan["scope"],
        "freeze": {"source_commit": source_commit, "plan_sha256": sha256_path(plan_path),
                   "implementation_sha256": sha256_path(Path(__file__))},
        "source_receipts": receipts, "station_structures": summaries,
        "cross_root_capacity": capacity, "failures": failures,
        "clauses": {
            "COMPLETE_FIVE_ARTIFACT_SET": "SATISFIED" if len(receipts) == 5 and all("sha256" in row for row in receipts) else "NOT_SATISFIED",
            "ROLE_SPECIFIC_HEADER_AND_TRANSFORM_ADMISSION": "SATISFIED" if len(summaries) == 5 else "NOT_SATISFIED",
            "STRUCTURAL_COMMON_WINDOW": "SATISFIED" if capacity and capacity["qualified"] else "NOT_EVALUATED" if capacity is None else "NOT_SATISFIED",
            "OBSERVATION_NUMERIC_ADMISSION": "NOT_EVALUATED",
            "TOTAL_PHYSICAL_ERROR_ENVELOPE": "NOT_EVALUATED",
        },
        "interpretation": {
            "target_selected": False, "target_identity_persisted": False,
            "observation_numbers_converted": 0, "s3_authorized": False,
            "closed_doy242_retried_or_rescored": False,
            "next_step_if_qualified": "Freeze a distinct target-free reference-only physical-envelope qualification; do not reuse this artifact as a primary.",
        },
        "persistence": plan["persistence"],
        "environment": {"python": platform.python_version(),
                        "hatanaka": getattr(hatanaka, "__version__", "unknown")},
    }
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
