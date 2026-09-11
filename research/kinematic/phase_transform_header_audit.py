"""Bounded, header-only phase-transform audit for one frozen RINEX set.

The complete compressed artifact is hashed in RAM before parsing.  Only the
gzip/CRINEX header is exposed: Hatanaka observation decoding is deliberately
absent, and neither observation records nor their values are represented.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import gzip
import hashlib
import io
import json
from pathlib import Path
import platform
import re
import subprocess
import urllib.error
import urllib.request


TERMINALS = {
    "PHASE_TRANSFORM_HEADERS_QUALIFIED",
    "PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED",
    "HEADER_AUDIT_EXECUTION_INVALID",
}
REQUIRED = ("C1C", "C2W", "L1C", "L2W")
PHASE_REQUIRED = ("L1C", "L2W")
GPS = re.compile(r"G(?:0[1-9]|[12][0-9]|3[0-2])")
OBSERVABLE = re.compile(r"[CLDS][1-9][A-Z]")
KNOWN_HEADERS = {
    "RINEX VERSION / TYPE", "PGM / RUN BY / DATE", "COMMENT", "MARKER NAME",
    "MARKER NUMBER", "MARKER TYPE", "OBSERVER / AGENCY", "REC # / TYPE / VERS",
    "ANT # / TYPE", "APPROX POSITION XYZ", "ANTENNA: DELTA H/E/N",
    "ANTENNA: PHASECENTER", "ANTENNA: B.SIGHT XYZ", "ANTENNA: ZERODIR AZI",
    "ANTENNA: ZERODIR XYZ", "CENTER OF MASS: XYZ", "SYS / # / OBS TYPES",
    "INTERVAL", "TIME OF FIRST OBS", "TIME OF LAST OBS", "RCV CLOCK OFFS APPL",
    "SYS / SCALE FACTOR", "SYS / PHASE SHIFT", "SYS / DCBS APPLIED",
    "SYS / PCVS APPLIED", "WAVELENGTH FACT L1/2", "SIGNAL STRENGTH UNIT",
    "GLONASS SLOT / FRQ #", "GLONASS COD/PHS/BIS", "LEAP SECONDS",
    "# OF SATELLITES", "PRN / # OF OBS", "END OF HEADER", "DOI", "LICENSE OF USE",
    "STATION INFORMATION",
}


class HeaderRejected(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strict_json(value) -> str:
    return json.dumps(value, allow_nan=False, sort_keys=True)


def validate_plan(plan: dict) -> None:
    if plan.get("schema") not in {
            "s2-phase-transform-header-audit-v1",
            "s2-phase-transform-header-audit-v2"}:
        raise ValueError("unsupported audit plan")
    if plan.get("reserved_target") != "G14":
        raise ValueError("reserved target differs")
    if date.fromisoformat(plan["date_gpst"]).timetuple().tm_yday != plan["day_of_year"]:
        raise ValueError("date/day-of-year mismatch")
    source = plan["source"]
    if (source["required_gps_observables"] != list(REQUIRED)
            or source["required_interval_s"] != 30.0
            or source["required_time_system"] != "GPS"):
        raise ValueError("required coordinate differs")
    stations = plan.get("stations", [])
    if len(stations) != 8 or len(set(stations)) != 8:
        raise ValueError("exact fixed eight-root set required")
    execution = plan["execution"]
    if not all(execution[key] for key in (
            "one_attempt_per_station", "continue_through_all_predeclared_stations",
            "no_retry", "no_station_or_date_substitution",
            "compressed_artifact_materialized_and_hashed_before_header_parse",
            "gzip_stream_stops_after_end_of_header", "hatanaka_body_decoder_forbidden")):
        raise ValueError("bounded header-only execution required")
    if set(plan.get("outcomes", [])) != TERMINALS:
        raise ValueError("terminal set differs")


def _download(url: str, maximum_bytes: int) -> tuple[bytes, dict]:
    if not url.startswith("https://igs.bkg.bund.de/root_ftp/IGS/obs/"):
        raise ValueError("only the frozen BKG observation source is allowed")
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read(maximum_bytes + 1)
        status = response.status
    if len(data) > maximum_bytes:
        raise ValueError("source exceeds frozen byte bound")
    return data, {
        "url": url,
        "http_status": status,
        "bytes": len(data),
        "sha256": _sha256(data),
        "access_utc": _utc_now(),
    }


def extract_crinex_header(compressed: bytes, *, maximum_lines: int) -> tuple[list[str], dict]:
    """Return only CRINEX/RINEX header lines, never the first body line."""
    raw_header = bytearray()
    preamble: list[str] = []
    rinex: list[str] = []
    with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
        for index in range(maximum_lines):
            raw = stream.readline(258)
            if not raw:
                raise HeaderRejected("TRUNCATED_HEADER")
            if len(raw) > 256 or not raw.endswith((b"\n", b"\r")):
                raise HeaderRejected("INVALID_HEADER_LINE")
            try:
                line = raw.rstrip(b"\r\n").decode("ascii")
            except UnicodeDecodeError as error:
                raise HeaderRejected("NON_ASCII_HEADER") from error
            raw_header.extend(raw)
            label = line[60:80].strip() if len(line) >= 60 else ""
            if not rinex:
                if label == "RINEX VERSION / TYPE":
                    rinex.append(line)
                else:
                    preamble.append(label)
                continue
            rinex.append(line)
            if label == "END OF HEADER":
                break
        else:
            raise HeaderRejected("HEADER_LINE_BOUND_EXCEEDED")
    if preamble != ["CRINEX VERS   / TYPE", "CRINEX PROG / DATE"]:
        raise HeaderRejected("UNSUPPORTED_CRINEX_PREAMBLE")
    return rinex, {
        "crinex_preamble": preamble,
        "header_line_count": len(rinex),
        "decompressed_header_bytes": len(raw_header),
        "decompressed_header_sha256": _sha256(bytes(raw_header)),
        "observation_body_lines_exposed": 0,
    }


def _collect_headers(lines: list[str]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    headers: dict[str, list[str]] = {}
    systems: dict[str, dict] = {}
    pending = None
    for line in lines:
        label, value = line[60:80].strip(), line[:60].ljust(60)
        if label not in KNOWN_HEADERS:
            raise HeaderRejected("UNCLASSIFIED_HEADER:" + label)
        headers.setdefault(label, []).append(value)
        if label == "SYS / # / OBS TYPES":
            system = value[0]
            if system.strip():
                if pending is not None and len(systems[pending]["types"]) != systems[pending]["count"]:
                    raise HeaderRejected("INCOMPLETE_OBSERVATION_TYPES")
                try:
                    count = int(value[3:6])
                except ValueError as error:
                    raise HeaderRejected("INVALID_OBSERVATION_COUNT") from error
                if system not in "GRECSJI" or system in systems or not 1 <= count <= 99:
                    raise HeaderRejected("DUPLICATE_OR_UNKNOWN_SYSTEM")
                systems[system] = {"count": count, "types": []}
                pending = system
            elif pending is None or value[:7].strip():
                raise HeaderRejected("ORPHAN_OBSERVATION_CONTINUATION")
            types = value[7:60].split()
            if any(not OBSERVABLE.fullmatch(name) for name in types):
                raise HeaderRejected("INVALID_OBSERVATION_TYPE")
            systems[pending]["types"].extend(types)
        if label == "END OF HEADER":
            break
    else:
        raise HeaderRejected("MISSING_END_OF_HEADER")
    for item in systems.values():
        if len(item["types"]) != item["count"] or len(set(item["types"])) != item["count"]:
            raise HeaderRejected("INCOMPLETE_OR_DUPLICATE_OBSERVATION_TYPES")
    return headers, {key: value["types"] for key, value in systems.items()}


def _parse_scale_factors(rows: list[str], gps_types: list[str]) -> dict:
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
        values = [item for item in values if item]
        if any(not OBSERVABLE.fullmatch(item) for item in values):
            raise HeaderRejected("INVALID_SCALE_FACTOR_OBSERVABLE")
        pending["types"].extend(values)
        if len(pending["types"]) > pending["count"]:
            raise HeaderRejected("SCALE_FACTOR_COUNT_MISMATCH")
        if len(pending["types"]) == pending["count"]:
            if pending["system"] == "G":
                affected = gps_types if pending["count"] == 0 else pending["types"]
                if not affected or any(item not in gps_types for item in affected):
                    raise HeaderRejected("SCALE_FACTOR_SCOPE_MISMATCH")
                for item in affected:
                    if item in assigned and assigned[item] != pending["factor"]:
                        raise HeaderRejected("CONFLICTING_SCALE_FACTOR")
                    assigned[item] = pending["factor"]
                    factors[item] = pending["factor"]
            pending = None
    if pending is not None:
        raise HeaderRejected("INCOMPLETE_SCALE_FACTOR")
    return {name: factors[name] for name in REQUIRED}


def _parse_phase_shifts(rows: list[str]) -> dict:
    shifts = {name: {"default_cycles": 0.0, "satellite_overrides_cycles": {}}
              for name in PHASE_REQUIRED}
    declared = set()
    pending = None
    for row in rows:
        system = row[0]
        if system.strip():
            if system not in "GRECSJI":
                raise HeaderRejected("INVALID_PHASE_SHIFT_SYSTEM")
            code = row[2:5].strip()
            if not code:
                if system == "G":
                    raise HeaderRejected("UNKNOWN_GPS_PHASE_ALIGNMENT")
                pending = None
                continue
            if not re.fullmatch(r"L[1-9][A-Z]", code):
                raise HeaderRejected("INVALID_PHASE_SHIFT_OBSERVABLE")
            raw_shift = row[6:14].strip()
            raw_count = row[16:18].strip()
            try:
                shift = float(raw_shift) if raw_shift else 0.0
                count = int(raw_count or "0")
            except ValueError as error:
                raise HeaderRejected("INVALID_PHASE_SHIFT") from error
            if not (-1.0 <= shift <= 1.0) or count < 0:
                raise HeaderRejected("INVALID_PHASE_SHIFT")
            pending = {"system": system, "code": code, "shift": shift,
                       "count": count, "satellites": []}
        elif pending is None or row[:18].strip():
            raise HeaderRejected("ORPHAN_PHASE_SHIFT_CONTINUATION")
        satellites = [row[offset + 1:offset + 4].strip() for offset in range(18, 58, 4)]
        satellites = [item for item in satellites if item]
        if pending["system"] == "G" and any(not GPS.fullmatch(item) for item in satellites):
            raise HeaderRejected("INVALID_PHASE_SHIFT_SATELLITE")
        pending["satellites"].extend(satellites)
        if len(pending["satellites"]) > pending["count"]:
            raise HeaderRejected("PHASE_SHIFT_COUNT_MISMATCH")
        if len(pending["satellites"]) == pending["count"]:
            if pending["system"] == "G" and pending["code"] in PHASE_REQUIRED:
                code = pending["code"]
                if pending["count"] == 0:
                    if code in declared:
                        raise HeaderRejected("DUPLICATE_PHASE_SHIFT")
                    shifts[code]["default_cycles"] = pending["shift"]
                else:
                    for satellite in pending["satellites"]:
                        if satellite in shifts[code]["satellite_overrides_cycles"]:
                            raise HeaderRejected("DUPLICATE_PHASE_SHIFT_SATELLITE")
                        shifts[code]["satellite_overrides_cycles"][satellite] = pending["shift"]
                declared.add(code)
            pending = None
    if pending is not None:
        raise HeaderRejected("INCOMPLETE_PHASE_SHIFT")
    missing = set(PHASE_REQUIRED) - declared
    if missing:
        raise HeaderRejected("MISSING_REQUIRED_PHASE_SHIFT:" + ",".join(sorted(missing)))
    return shifts


def _parse_legacy_wavelength(rows: list[str]) -> dict:
    default = {"L1": 1, "L2": 1}
    overrides: dict[str, dict[str, int]] = {}
    saw_default = False
    for row in rows:
        try:
            l1 = int(row[0:6])
            l2 = int(row[6:12])
            count = int(row[12:18].strip() or "0")
        except ValueError as error:
            raise HeaderRejected("INVALID_LEGACY_WAVELENGTH_FACTOR") from error
        if l1 not in {1, 2} or l2 not in {0, 1, 2} or not 0 <= count <= 7:
            raise HeaderRejected("INVALID_LEGACY_WAVELENGTH_FACTOR")
        satellites = [row[offset + 3:offset + 6].strip() for offset in range(18, 60, 6)]
        satellites = [item for item in satellites if item]
        if len(satellites) != count or any(not GPS.fullmatch(item) for item in satellites):
            raise HeaderRejected("LEGACY_WAVELENGTH_SCOPE_MISMATCH")
        if count == 0:
            if saw_default or overrides:
                raise HeaderRejected("LEGACY_WAVELENGTH_DEFAULT_ORDER")
            default, saw_default = {"L1": l1, "L2": l2}, True
        else:
            if not saw_default:
                raise HeaderRejected("LEGACY_WAVELENGTH_DEFAULT_MISSING")
            for satellite in satellites:
                if satellite in overrides:
                    raise HeaderRejected("DUPLICATE_LEGACY_WAVELENGTH_SATELLITE")
                overrides[satellite] = {"L1": l1, "L2": l2}
    if default["L2"] == 0 or any(item["L2"] == 0 for item in overrides.values()):
        raise HeaderRejected("REQUIRED_L2_WAVELENGTH_UNAVAILABLE")
    return {
        "present": bool(rows),
        "numeric_phase_unit": "carrier_cycles",
        "default_ambiguity_wavelength_divisor": default,
        "satellite_overrides": overrides,
        "numeric_phase_rescaling_authorized": False,
        "future_nonzero_lli_breaks_segment": True,
    }


def _external_corrections(headers: dict[str, list[str]]) -> dict:
    output = {}
    for label in ("SYS / DCBS APPLIED", "SYS / PCVS APPLIED"):
        entries = []
        for row in headers.get(label, []):
            system = row[0]
            if system not in "GRECSJI":
                raise HeaderRejected("INVALID_EXTERNAL_CORRECTION_HEADER:" + label)
            program, source = row[2:19].strip(), row[20:60].strip()
            entries.append({"system": system, "program": program, "source": source})
            if system == "G" and (program or source):
                raise HeaderRejected("UNQUALIFIED_APPLIED_EXTERNAL_CORRECTION:" + label)
        output[label] = entries
    return output


def _parse_epoch_header(row: str, label: str) -> list[float | int | str]:
    fields = row[:43].split()
    if len(fields) != 6:
        raise HeaderRejected("INVALID_" + label.replace(" ", "_"))
    try:
        values = [int(item) for item in fields[:5]] + [float(fields[5])]
    except ValueError as error:
        raise HeaderRejected("INVALID_" + label.replace(" ", "_")) from error
    return values


def audit_header(lines: list[str], plan: dict, station: str) -> dict:
    headers, systems = _collect_headers(lines)
    mandatory = (
        "RINEX VERSION / TYPE", "MARKER NAME", "REC # / TYPE / VERS",
        "INTERVAL", "TIME OF FIRST OBS", "TIME OF LAST OBS", "END OF HEADER",
    )
    for label in mandatory:
        if len(headers.get(label, [])) != 1:
            raise HeaderRejected("MISSING_OR_DUPLICATE_HEADER:" + label)
    version = headers["RINEX VERSION / TYPE"][0]
    if (version[:9].strip() not in plan["source"]["required_rinex_versions"]
            or version[20:21] != "O" or version[40:41] not in ("G", "M")):
        raise HeaderRejected("UNSUPPORTED_OBSERVATION_FORMAT")
    gps_types = systems.get("G", [])
    if not all(item in gps_types for item in REQUIRED):
        raise HeaderRejected("MISSING_REQUIRED_GPS_OBSERVABLE")
    try:
        interval = float(headers["INTERVAL"][0])
    except ValueError as error:
        raise HeaderRejected("INVALID_INTERVAL") from error
    if interval != plan["source"]["required_interval_s"]:
        raise HeaderRejected("INTERVAL_DIFFERS_FROM_PLAN")
    first_row, last_row = headers["TIME OF FIRST OBS"][0], headers["TIME OF LAST OBS"][0]
    if (first_row[48:51] != plan["source"]["required_time_system"]
            or last_row[48:51] != plan["source"]["required_time_system"]):
        raise HeaderRejected("NON_GPST_TIME_SYSTEM")
    first = _parse_epoch_header(first_row, "TIME_OF_FIRST_OBS")
    last = _parse_epoch_header(last_row, "TIME_OF_LAST_OBS")
    if first != plan["source"]["required_first_epoch"] or last != plan["source"]["required_last_epoch"]:
        raise HeaderRejected("HEADER_DOES_NOT_COVER_FROZEN_DAY")
    clock_rows = headers.get("RCV CLOCK OFFS APPL", [])
    if len(clock_rows) > 1 or (clock_rows and clock_rows[0].strip() != "0"):
        raise HeaderRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")
    receiver = headers["REC # / TYPE / VERS"][0]
    identity = [receiver[offset:offset + 20].strip() for offset in (0, 20, 40)]
    if not all(identity):
        raise HeaderRejected("INCOMPLETE_RECEIVER_IDENTITY")
    scale = _parse_scale_factors(headers.get("SYS / SCALE FACTOR", []), gps_types)
    phase_shift = _parse_phase_shifts(headers.get("SYS / PHASE SHIFT", []))
    wavelength = _parse_legacy_wavelength(headers.get("WAVELENGTH FACT L1/2", []))
    external = _external_corrections(headers)
    return {
        "station": station,
        "status": "HEADER_PHASE_TRANSFORMS_QUALIFIED",
        "rinex_version": version[:9].strip(),
        "marker_name": headers["MARKER NAME"][0].strip(),
        "marker_type": headers.get("MARKER TYPE", [""])[0].strip() or None,
        "receiver_identity": identity,
        "interval_s": interval,
        "first_observation_gpst": first,
        "last_observation_gpst": last,
        "gps_observation_types": gps_types,
        "transform_ledger": {
            "stored_value_scale_divisor": scale,
            "phase_shift": phase_shift,
            "legacy_wavelength_factor": wavelength,
            "external_corrections": external,
            "receiver_clock_offset_applied": False,
        },
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
        committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
        if committed != path.read_bytes():
            raise ValueError("frozen file differs from committed bytes:" + relative)
    return {
        "freeze_utc": _utc_now(),
        "source_commit": commit,
        "plan_sha256": _sha256(plan_path.read_bytes()),
        "implementation_sha256": _sha256(source_path.read_bytes()),
        "observation_record_access": False,
    }


def run(plan_path: Path) -> dict:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan)
    source_path = Path(__file__)
    root = source_path.resolve().parents[2]
    freeze = _git_freeze(root, plan_path, source_path)
    receipts, station_results, failures = [], {}, []
    execution_invalid = False
    for station in plan["stations"]:
        url = plan["source"]["base_url"] + plan["source"]["filename"].format(station=station)
        try:
            compressed, receipt = _download(url, plan["source"]["maximum_compressed_bytes_per_station"])
            receipts.append({"station": station, **receipt})
        except urllib.error.HTTPError as error:
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
            lines, header_receipt = extract_crinex_header(
                compressed, maximum_lines=plan["source"]["maximum_header_lines"]
            )
            receipts[-1].update(header_receipt)
            station_results[station] = audit_header(lines, plan, station)
        except HeaderRejected as error:
            failures.append({"station": station, "stage": "HEADER_ADMISSION",
                             "classification": "CAPABILITY_REJECTED", "reason": error.reason})
        except Exception as error:
            execution_invalid = True
            failures.append({"station": station, "stage": "HEADER_EXECUTION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
    admitted = not failures and len(station_results) == len(plan["stations"])
    status = ("HEADER_AUDIT_EXECUTION_INVALID" if execution_invalid
              else "PHASE_TRANSFORM_HEADERS_QUALIFIED" if admitted
              else "PHASE_TRANSFORM_HEADERS_NOT_QUALIFIED")
    result = {
        "schema": "s2-phase-transform-header-audit-result-v1",
        "audit_id": plan["audit_id"],
        "status": status,
        "scope": plan["scope"],
        "freeze": freeze,
        "source_receipts": receipts,
        "station_results": station_results,
        "failures": failures,
        "physical_interpretation": {
            "observation_measurements_qualified": False,
            "phase_error_envelope_qualified": False,
            "inverse_experiment_authorized": False,
            "next_possible_step_if_admitted": "A separately frozen, distinct-date reference-only value qualification using exactly these transform semantics.",
        },
        "persistence": plan["persistence"],
        "environment": {"python": platform.python_version()},
    }
    if status not in TERMINALS:
        raise AssertionError("non-terminal result")
    _strict_json(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing audit result")
    result = run(args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"status": result["status"], "failures": result["failures"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
