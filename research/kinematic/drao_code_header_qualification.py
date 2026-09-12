"""One bounded, target-free DRAO code-coordinate header qualification.

The complete compressed artifact is hashed before parsing. The gzip reader
stops at END OF HEADER, so neither Hatanaka records nor observation values can
enter memory through this module.
"""
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

from .phase_transform_header_audit import (
    HeaderRejected,
    _collect_headers,
    _download,
    _external_corrections,
    _parse_epoch_header,
    extract_crinex_header,
)


TERMINALS = {
    "DRAO_CODE_HEADERS_QUALIFIED",
    "DRAO_CODE_HEADERS_NOT_QUALIFIED",
    "DRAO_CODE_HEADER_EXECUTION_INVALID",
}
REQUIRED_CODE = ("C1C", "C2W")
F1_HZ = 1_575_420_000.0
F2_HZ = 1_227_600_000.0


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_plan(plan: dict) -> None:
    if plan.get("schema") != "s2-drao-code-header-qualification-v1":
        raise ValueError("unsupported qualification plan")
    if date.fromisoformat(plan["date_gpst"]).timetuple().tm_yday != plan["day_of_year"]:
        raise ValueError("date/day-of-year mismatch")
    source = plan["source"]
    if (source["required_gps_code_observables"] != list(REQUIRED_CODE)
            or source["required_interval_s"] != 30.0
            or source["required_time_system"] != "GPS"):
        raise ValueError("frozen code coordinate differs")
    if source["minimum_archive_age_after_last_epoch_s"] < 86400:
        raise ValueError("full-day maturity bound is too short")
    if plan["station"] != {
            "id": "DRAO00CAN", "allowed_marker_names": ["DRAO", "DRAO00CAN"]}:
        raise ValueError("frozen station differs")
    if not all(plan["execution"][key] for key in (
            "one_attempt", "no_retry", "no_date_station_or_field_substitution",
            "complete_compressed_artifact_hashed_before_header_parse",
            "gzip_stream_stops_after_end_of_header", "hatanaka_body_decoder_forbidden",
            "target_identity_and_values_forbidden")):
        raise ValueError("bounded value-blind execution required")
    if set(plan["outcomes"]) != TERMINALS:
        raise ValueError("terminal set differs")


def admit_archive_age(plan: dict, *, now_utc: datetime | None = None) -> None:
    fields = plan["source"]["required_last_epoch"]
    whole = int(fields[5])
    last = datetime(*fields[:5], whole, tzinfo=timezone.utc)
    last += timedelta(seconds=fields[5] - whole)
    now = now_utc or datetime.now(timezone.utc)
    if now < last + timedelta(seconds=plan["source"]["minimum_archive_age_after_last_epoch_s"]):
        raise ValueError("FROZEN_FULL_DAY_PRODUCT_NOT_MATURE")


def _parse_code_scale_factors(rows: list[str], gps_types: list[str]) -> dict[str, int]:
    factors = {name: 1 for name in REQUIRED_CODE}
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
        names = [row[offset + 1:offset + 4].strip() for offset in range(10, 58, 4)]
        names = [name for name in names if name]
        pending["types"].extend(names)
        if len(pending["types"]) > pending["count"]:
            raise HeaderRejected("SCALE_FACTOR_COUNT_MISMATCH")
        if len(pending["types"]) == pending["count"]:
            if pending["system"] == "G":
                affected = gps_types if pending["count"] == 0 else pending["types"]
                if any(name not in gps_types for name in affected):
                    raise HeaderRejected("SCALE_FACTOR_SCOPE_MISMATCH")
                for name in REQUIRED_CODE:
                    if name in affected:
                        if name in assigned and assigned[name] != pending["factor"]:
                            raise HeaderRejected("CONFLICTING_SCALE_FACTOR")
                        assigned[name] = pending["factor"]
                        factors[name] = pending["factor"]
            pending = None
    if pending is not None:
        raise HeaderRejected("INCOMPLETE_SCALE_FACTOR")
    return factors


def audit_header(lines: list[str], plan: dict) -> dict:
    if not lines or lines[0][60:80].strip() != "RINEX VERSION / TYPE":
        raise HeaderRejected("MISSING_RINEX_VERSION")
    version_row = lines[0].ljust(80)
    if (version_row[:9].strip() not in plan["source"]["required_rinex_versions"]
            or version_row[20:21] != "O" or version_row[40:41] not in ("G", "M")):
        raise HeaderRejected("UNSUPPORTED_NAMED_CODE_FORMAT")
    headers, systems = _collect_headers(lines)
    mandatory = (
        "RINEX VERSION / TYPE", "MARKER NAME", "REC # / TYPE / VERS",
        "ANT # / TYPE", "APPROX POSITION XYZ", "ANTENNA: DELTA H/E/N",
        "INTERVAL", "TIME OF FIRST OBS", "TIME OF LAST OBS", "END OF HEADER",
    )
    for label in mandatory:
        if len(headers.get(label, [])) != 1:
            raise HeaderRejected("MISSING_OR_DUPLICATE_HEADER:" + label)
    gps_types = systems.get("G", [])
    if not all(name in gps_types for name in REQUIRED_CODE):
        raise HeaderRejected("MISSING_REQUIRED_GPS_CODE_OBSERVABLE")
    marker = headers["MARKER NAME"][0].strip().upper()
    if marker not in plan["station"]["allowed_marker_names"]:
        raise HeaderRejected("MARKER_IDENTITY_DIFFERS")
    try:
        interval = float(headers["INTERVAL"][0])
        xyz = [float(value) for value in headers["APPROX POSITION XYZ"][0].split()]
        delta = [float(value) for value in headers["ANTENNA: DELTA H/E/N"][0].split()]
    except ValueError as error:
        raise HeaderRejected("INVALID_NUMERIC_HEADER") from error
    if interval != plan["source"]["required_interval_s"]:
        raise HeaderRejected("INTERVAL_DIFFERS_FROM_PLAN")
    if len(xyz) != 3 or len(delta) != 3 or not all(math.isfinite(x) for x in xyz + delta):
        raise HeaderRejected("INVALID_STATION_GEOMETRY")
    first_row = headers["TIME OF FIRST OBS"][0]
    last_row = headers["TIME OF LAST OBS"][0]
    if (first_row[48:51] != plan["source"]["required_time_system"]
            or last_row[48:51] != plan["source"]["required_time_system"]):
        raise HeaderRejected("NON_GPST_TIME_SYSTEM")
    first = _parse_epoch_header(first_row, "TIME_OF_FIRST_OBS")
    last = _parse_epoch_header(last_row, "TIME_OF_LAST_OBS")
    if (first != plan["source"]["required_first_epoch"]
            or last != plan["source"]["required_last_epoch"]):
        raise HeaderRejected("HEADER_DOES_NOT_COVER_FROZEN_DAY")
    clock_rows = headers.get("RCV CLOCK OFFS APPL", [])
    if len(clock_rows) > 1 or (clock_rows and clock_rows[0].strip() != "0"):
        raise HeaderRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")
    receiver = headers["REC # / TYPE / VERS"][0].ljust(60)
    receiver_identity = [receiver[offset:offset + 20].strip() for offset in (0, 20, 40)]
    antenna = headers["ANT # / TYPE"][0].ljust(60)
    antenna_identity = [antenna[offset:offset + 20].strip() for offset in (0, 20)]
    if not all(receiver_identity) or not all(antenna_identity):
        raise HeaderRejected("INCOMPLETE_HARDWARE_IDENTITY")
    scale = _parse_code_scale_factors(headers.get("SYS / SCALE FACTOR", []), gps_types)
    external = _external_corrections(headers)
    denominator = F1_HZ * F1_HZ - F2_HZ * F2_HZ
    return {
        "station": plan["station"]["id"],
        "status": "HEADER_CODE_COORDINATE_QUALIFIED",
        "rinex_version": version_row[:9].strip(),
        "marker_name": marker,
        "marker_type": headers.get("MARKER TYPE", [""])[0].strip() or None,
        "receiver_identity": receiver_identity,
        "antenna_identity": antenna_identity,
        "approx_position_xyz_m": xyz,
        "antenna_delta_hen_m": delta,
        "interval_s": interval,
        "first_observation_gpst": first,
        "last_observation_gpst": last,
        "gps_observation_types": gps_types,
        "transform_ledger": {
            "stored_value_scale_divisor": scale,
            "ionosphere_free_code": {
                "input": ["C1C", "C2W"],
                "coefficients": {
                    "C1C": F1_HZ * F1_HZ / denominator,
                    "C2W": -F2_HZ * F2_HZ / denominator,
                },
                "output_unit": "metres",
            },
            "external_corrections": external,
            "receiver_clock_offset_applied": False,
            "phase_transform_headers_inspected_for_admission": False,
        },
        "coverage_semantics": "HEADER_DECLARATION_ONLY",
    }


def _git_freeze(root: Path, plan_path: Path, source_path: Path) -> dict:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True
    )
    if status.strip():
        raise ValueError("working tree must be clean before source access")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for path in (plan_path, source_path):
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        if subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root) != path.read_bytes():
            raise ValueError("frozen file differs from committed bytes:" + relative)
    return {
        "freeze_utc": _utc_now(),
        "source_commit": commit,
        "plan_sha256": _sha256(plan_path.read_bytes()),
        "implementation_sha256": _sha256(source_path.read_bytes()),
        "observation_record_access": False,
        "target_identity_or_value_access": False,
    }


def run(plan_path: Path) -> dict:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan)
    admit_archive_age(plan)
    source_path = Path(__file__)
    root = source_path.resolve().parents[2]
    freeze = _git_freeze(root, plan_path, source_path)
    receipt, header_result, failures = None, None, []
    execution_invalid = False
    try:
        compressed, receipt = _download(
            plan["source"]["url"], plan["source"]["maximum_compressed_bytes"]
        )
        receipt = {"station": plan["station"]["id"], **receipt}
    except urllib.error.HTTPError as error:
        receipt = {"station": plan["station"]["id"], "url": plan["source"]["url"],
                   "http_status": error.code, "access_utc": _utc_now(),
                   "artifact_materialized": False}
        failures.append({"stage": "SOURCE_MATERIALIZATION",
                         "classification": "SOURCE_PRODUCT_UNAVAILABLE",
                         "reason": f"SOURCE_HTTP_{error.code}"})
    except Exception as error:
        execution_invalid = True
        failures.append({"stage": "SOURCE_MATERIALIZATION",
                         "classification": "QUALIFICATION_ERROR",
                         "reason": type(error).__name__ + ":" + str(error)})
    if receipt and receipt.get("artifact_materialized", True) is not False:
        try:
            lines, header_receipt = extract_crinex_header(
                compressed, maximum_lines=plan["source"]["maximum_header_lines"]
            )
            receipt.update(header_receipt)
            header_result = audit_header(lines, plan)
        except HeaderRejected as error:
            failures.append({"stage": "HEADER_ADMISSION", "classification": "CAPABILITY_REJECTED",
                             "reason": error.reason})
        except Exception as error:
            execution_invalid = True
            failures.append({"stage": "HEADER_EXECUTION", "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
    status = ("DRAO_CODE_HEADER_EXECUTION_INVALID" if execution_invalid
              else "DRAO_CODE_HEADERS_QUALIFIED" if header_result and not failures
              else "DRAO_CODE_HEADERS_NOT_QUALIFIED")
    result = {
        "schema": "s2-drao-code-header-qualification-result-v1",
        "qualification_id": plan["qualification_id"],
        "status": status,
        "scope": plan["scope"],
        "freeze": freeze,
        "source_receipt": receipt,
        "header_result": header_result,
        "failures": failures,
        "physical_interpretation": {
            "code_header_coordinate_qualified": status == "DRAO_CODE_HEADERS_QUALIFIED",
            "observation_structure_qualified": False,
            "observation_measurements_qualified": False,
            "physical_error_envelope_qualified": False,
            "s3_authorized": False,
        },
        "persistence": plan["persistence"],
        "environment": {"python": platform.python_version()},
    }
    if status not in TERMINALS:
        raise AssertionError("non-terminal result")
    json.dumps(result, allow_nan=False, sort_keys=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing qualification result")
    result = run(args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "failures": result["failures"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
