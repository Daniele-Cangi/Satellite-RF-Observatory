"""One bounded real, non-target RINEX phase-path qualification.

The module is deliberately tied to the frozen S2 plan. Observation payloads
exist in memory only. G14 rows are removed before any observation number is
converted, and only aggregate residual metrics may reach the receipt.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import urllib.request

import hatanaka
import numpy as np
import scipy
from scipy.optimize import least_squares

from positioning.calibration import antenna_position, parse_reference_navigation, reference_model, strip_target_navigation
from positioning.context import Context
from .phase_rates import interval_matrix
from .reference_bridge import admit_navigation, reference_code
from .rinex_observations import METADATA
from .rinex_phase_observations import GPS, REQUIRED, RinexRejected, _time, parse_reference_phase_file


TERMINALS = {
    "REFERENCE_PHASE_PATH_QUALIFIED",
    "PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED",
    "QUALIFICATION_EXECUTION_INVALID",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _native(value):
    if isinstance(value, dict):
        return {str(key): _native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_native(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_native(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError("non-finite value cannot enter a qualification receipt")
    return value


def _download(url: str, maximum_bytes: int) -> tuple[bytes, dict]:
    if not url.startswith("https://igs.bkg.bund.de/root_ftp/IGS/"):
        raise ValueError("frozen qualification permits only its BKG HTTPS sources")
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


def validate_plan(plan: dict) -> None:
    if plan.get("schema") not in {
            "s2-real-reference-phase-qualification-v1",
            "s2-real-reference-phase-qualification-v2"}:
        raise ValueError("unsupported qualification plan")
    if plan.get("reserved_target") != "G14" or not GPS.fullmatch(plan["reserved_target"]):
        raise ValueError("frozen reserved target differs")
    if date.fromisoformat(plan["date_gpst"]).timetuple().tm_yday != plan["day_of_year"]:
        raise ValueError("date/day-of-year mismatch")
    obs, selection, admission = plan["observation"], plan["selection"], plan["admission"]
    if (obs["required_fields"] != list(REQUIRED)
            or obs["required_interval_s"] != 30.0
            or selection["endpoint_count"] != 11
            or selection["references_per_station"] != 4):
        raise ValueError("plan differs from implemented bounded design")
    if not all(admission[key] for key in (
            "require_complete_station_set", "require_unchanged_receiver_identity",
            "require_zero_reported_phase_lli", "require_no_gap_in_selected_window")):
        raise ValueError("required conservative admissions must remain enabled")
    stations = plan.get("stations", [])
    if len(stations) != 8 or len({item["id"] for item in stations}) != 8:
        raise ValueError("exact fixed eight-root set required")
    expected_terminals = (TERMINALS if plan["schema"].endswith("-v2")
                          else TERMINALS - {"QUALIFICATION_EXECUTION_INVALID"})
    if set(plan.get("outcomes", [])) != expected_terminals:
        raise ValueError("terminal set differs")


def _field_is_structurally_usable(record: str, types: list[str]) -> bool:
    fields = {}
    for name in REQUIRED:
        index = types.index(name)
        fields[name] = record[3 + 16 * index:3 + 16 * (index + 1)].ljust(16)
    if any(not field[:14].strip() for field in fields.values()):
        return False
    return all(fields[name][14] in (" ", "0") for name in ("L1C", "L2W"))


def _qualification_header(lines: list[str], plan: dict):
    """Parse only admission-relevant header fields; marker type is descriptive.

    This is intentionally separate from the synthetic bridge parser. The first
    execution demonstrated that importing its GEODETIC equality check would add
    an undeclared capability gate.
    """
    headers, systems, pending = {}, {}, None
    if not lines or lines[0][60:80].strip() != "RINEX VERSION / TYPE":
        raise RinexRejected("MISSING_RINEX_VERSION")
    for index, line in enumerate(lines):
        label, value = line[60:80].strip(), line[:60]
        declared_transforms = set(plan["observation"].get("disallowed_header_transforms", []))
        if label not in METADATA and label not in declared_transforms:
            raise RinexRejected("UNQUALIFIED_HEADER:" + label)
        headers.setdefault(label, []).append(value)
        if label == "SYS / # / OBS TYPES":
            system = value[:1]
            if system.strip():
                if pending is not None and len(systems[pending]["types"]) != systems[pending]["count"]:
                    raise RinexRejected("INCOMPLETE_OBSERVATION_TYPES")
                if system not in "GRECSJI" or system in systems:
                    raise RinexRejected("DUPLICATE_OR_UNKNOWN_SYSTEM")
                try:
                    count = int(value[3:6])
                except ValueError as error:
                    raise RinexRejected("INVALID_OBSERVATION_COUNT") from error
                systems[system] = {"count": count, "types": []}
                pending = system
            elif pending is None or value[:7].strip():
                raise RinexRejected("ORPHAN_OBSERVATION_CONTINUATION")
            types = value[7:60].split()
            if any(not re.fullmatch(r"[CLDS][1-9][A-Z]", name) for name in types):
                raise RinexRejected("INVALID_OBSERVATION_TYPE")
            systems[pending]["types"].extend(types)
        if label == "END OF HEADER":
            break
    else:
        raise RinexRejected("MISSING_END_OF_HEADER")
    for system in systems.values():
        if len(system["types"]) != system["count"] or len(set(system["types"])) != system["count"]:
            raise RinexRejected("INCOMPLETE_OR_DUPLICATE_OBSERVATION_TYPES")
    mandatory = (
        "RINEX VERSION / TYPE", "MARKER NAME", "REC # / TYPE / VERS",
        "ANT # / TYPE", "APPROX POSITION XYZ", "ANTENNA: DELTA H/E/N",
        "INTERVAL", "TIME OF FIRST OBS", "TIME OF LAST OBS",
    )
    for label in mandatory:
        if len(headers.get(label, [])) != 1:
            raise RinexRejected("MISSING_OR_DUPLICATE_HEADER:" + label)
    if len(headers.get("MARKER TYPE", [])) > 1:
        raise RinexRejected("DUPLICATE_HEADER:MARKER TYPE")
    version = headers["RINEX VERSION / TYPE"][0]
    if (version[:9].strip() not in plan["observation"]["required_rinex_versions"]
            or version[20:21] != "O" or version[40:41] not in ("G", "M")):
        raise RinexRejected("UNSUPPORTED_OBSERVATION_FORMAT")
    for label in plan["observation"].get("disallowed_header_transforms", []):
        if label in headers:
            raise RinexRejected("UNQUALIFIED_APPLIED_TRANSFORM:" + label)
    try:
        interval = float(headers["INTERVAL"][0])
    except ValueError as error:
        raise RinexRejected("INVALID_INTERVAL") from error
    if not np.isfinite(interval) or abs(interval - plan["observation"]["required_interval_s"]) > 1e-7:
        raise RinexRejected("INTERVAL_DIFFERS_FROM_PLAN")
    if headers["TIME OF FIRST OBS"][0][48:51] != plan["observation"]["required_time_system"]:
        raise RinexRejected("NON_GPST_TIME_SYSTEM")
    if headers["TIME OF LAST OBS"][0][48:51] != plan["observation"]["required_time_system"]:
        raise RinexRejected("NON_GPST_TIME_SYSTEM")
    if headers.get("RCV CLOCK OFFS APPL", ["0"])[0].strip() != "0":
        raise RinexRejected("APPLIED_RECEIVER_CLOCK_CORRECTION")
    identity_row = headers["REC # / TYPE / VERS"][0].ljust(60)
    identity = [identity_row[offset:offset + 20].strip() for offset in (0, 20, 40)]
    if not all(identity):
        raise RinexRejected("INCOMPLETE_RECEIVER_IDENTITY")
    try:
        station = antenna_position(headers)
    except (ValueError, ZeroDivisionError) as error:
        raise RinexRejected("INVALID_STATION_COORDINATES") from error
    if not np.isfinite(station).all():
        raise RinexRejected("INVALID_STATION_COORDINATES")
    first = _time(headers["TIME OF FIRST OBS"][0][:43].split(), plan["date_gpst"], 0)
    last = _time(headers["TIME OF LAST OBS"][0][:43].split(), plan["date_gpst"], 0)
    return index + 1, headers, systems, first, last, identity, station


def scan_reference_structure(content: str, *, plan: dict, station_plan: dict) -> dict:
    """Read headers, epoch topology and field presence, never measurement numbers."""
    obs = plan["observation"]
    lines = content.splitlines()
    start, headers, systems, first, last_header, identity, station = _qualification_header(lines, plan)
    if identity != station_plan["expected_receiver"]:
        raise RinexRejected("RECEIVER_IDENTITY_CHANGED")
    if (abs(first - obs["required_first_epoch_s"]) > 1e-7
            or abs(last_header - obs["required_last_epoch_s"]) > 1e-7):
        raise RinexRejected("HEADER_DOES_NOT_COVER_FROZEN_DAY")
    types = systems.get("G", {}).get("types", [])
    if not all(name in types for name in REQUIRED):
        raise RinexRejected("MISSING_REQUIRED_GPS_SIGNALS")

    eligible: dict[float, set[str]] = {}
    epoch_times: list[float] = []
    target_rows_discarded = 0
    previous = None
    index = start
    while index < len(lines):
        epoch = lines[index]
        index += 1
        if not epoch.startswith(">"):
            raise RinexRejected("EXPECTED_EPOCH_RECORD")
        fields = epoch[1:].split()
        if len(fields) not in (8, 9):
            raise RinexRejected("INVALID_EPOCH_RECORD")
        tag = _time(fields[:6], plan["date_gpst"], 0)
        try:
            flag, count = int(fields[6]), int(fields[7])
        except ValueError as error:
            raise RinexRejected("INVALID_EPOCH_RECORD") from error
        if previous is not None and tag <= previous:
            raise RinexRejected("DUPLICATE_OR_UNORDERED_EPOCH")
        if count < 0 or index + count > len(lines):
            raise RinexRejected("TRUNCATED_OR_INVALID_EPOCH_BLOCK")
        previous = tag
        block, index = lines[index:index + count], index + count
        usable: set[str] = set()
        seen: set[str] = set()
        for record in block:
            satellite = record[:3]
            if not isinstance(satellite, str) or len(satellite) != 3:
                raise RinexRejected("INVALID_SATELLITE_ROW")
            if satellite == plan["reserved_target"]:
                target_rows_discarded += 1
                continue  # Do not inspect any target field, including presence/LLI.
            if not GPS.fullmatch(satellite):
                continue
            if satellite in seen:
                raise RinexRejected("DUPLICATE_GPS_SATELLITE_ROW")
            seen.add(satellite)
            if flag == 0 and _field_is_structurally_usable(record, types):
                usable.add(satellite)
        epoch_times.append(tag)
        eligible[tag] = usable
    if (not epoch_times
            or abs(epoch_times[0] - obs["required_first_epoch_s"]) > 1e-7
            or abs(epoch_times[-1] - obs["required_last_epoch_s"]) > 1e-7):
        raise RinexRejected("ACTUAL_EPOCHS_DO_NOT_COVER_FROZEN_DAY")
    gaps = [b - a for a, b in zip(epoch_times, epoch_times[1:]) if abs((b - a) - obs["required_interval_s"]) > 1e-7]
    return {
        "station": station_plan["id"],
        "receiver_identity": identity,
        "reported_marker_type": headers.get("MARKER TYPE", [""])[0].strip() or None,
        "station_m": station,
        "epoch_count": len(epoch_times),
        "first_epoch_s": epoch_times[0],
        "last_epoch_s": epoch_times[-1],
        "non_nominal_gap_count": len(gaps),
        "maximum_gap_s": max(gaps, default=obs["required_interval_s"]),
        "target_rows_discarded_without_field_access": target_rows_discarded,
        "eligible": eligible,
    }


def strip_target_observations(content: str, target: str) -> tuple[str, int]:
    """Remove target rows using identity bytes only and repair epoch row counts."""
    lines = content.splitlines()
    try:
        header_end = next(i for i, row in enumerate(lines) if row[60:80].strip() == "END OF HEADER")
    except StopIteration as error:
        raise RinexRejected("MISSING_END_OF_HEADER") from error
    output = lines[:header_end + 1]
    removed = 0
    index = header_end + 1
    while index < len(lines):
        epoch = lines[index]
        index += 1
        if not epoch.startswith(">"):
            raise RinexRejected("EXPECTED_EPOCH_RECORD")
        fields = epoch.split()
        if len(fields) not in (9, 10):
            raise RinexRejected("INVALID_EPOCH_RECORD")
        try:
            count = int(fields[8])
        except ValueError as error:
            raise RinexRejected("INVALID_EPOCH_RECORD") from error
        if count < 0 or index + count > len(lines):
            raise RinexRejected("TRUNCATED_OR_INVALID_EPOCH_BLOCK")
        block, index = lines[index:index + count], index + count
        kept = []
        for row in block:
            if row[:3] == target:
                removed += 1
            else:
                kept.append(row)
        fields[8] = str(len(kept))
        output.append(" ".join(fields))
        output.extend(kept)
    return "\n".join(output) + "\n", removed


def _record_for(records: dict, satellite: str, midpoint_s: float, context: Context):
    candidates = [record for record in records.get(satellite, [])
                  if record.fit_interval_h is not None and record.fit_interval_h > 0]
    if not candidates:
        return None
    return min(candidates, key=lambda record: abs((record.toc_gps - context.day).total_seconds() - midpoint_s))


def select_window(plan: dict, structures: dict, navigation_text: str) -> dict | None:
    """Select using topology and non-target broadcast geometry, never magnitudes."""
    obs, selection = plan["observation"], plan["selection"]
    target, step = plan["reserved_target"], obs["required_interval_s"]
    context = Context(target, plan["date_gpst"])
    navigation = parse_reference_navigation(navigation_text, target)
    count = selection["endpoint_count"]
    final_start = obs["required_last_epoch_s"] - (count - 1) * step
    for start in np.arange(obs["required_first_epoch_s"], final_start + step / 2, step):
        tags = [float(start + index * step) for index in range(count)]
        chosen = {}
        for item in plan["stations"]:
            station_id = item["id"]
            structure = structures[station_id]
            if any(tag not in structure["eligible"] for tag in tags):
                break
            candidates = set.intersection(*(structure["eligible"][tag] for tag in tags))
            admitted = []
            for satellite in sorted(candidates):
                if satellite == target:
                    continue
                record = _record_for(navigation, satellite, start + (count - 1) * step / 2, context)
                if record is None:
                    continue
                try:
                    elevations = [reference_model(record, 23_000_000.0, tag,
                        structure["station_m"], 0.0, context)[1] for tag in tags]
                except ValueError:
                    continue
                if min(elevations) >= selection["minimum_reference_elevation_deg"]:
                    admitted.append(satellite)
            if len(admitted) < selection["references_per_station"]:
                break
            chosen[station_id] = admitted[:selection["references_per_station"]]
        if len(chosen) == len(plan["stations"]):
            return {"start_s": float(start), "tags_s": tags, "references": chosen}
    return None


def _station_metrics(plan: dict, structure: dict, sanitized: str,
                     navigation_text: str, selected: dict) -> dict:
    references, tags = selected["references"], selected["tags_s"]
    design = plan["design_covariance"]
    pair = np.diag([
        design["code_sigma_per_band_m"] ** 2,
        design["code_sigma_per_band_m"] ** 2,
        design["phase_sigma_per_band_cycles"] ** 2,
        design["phase_sigma_per_band_cycles"] ** 2,
    ])
    covariance = np.kron(np.eye(len(tags) * len(references)), pair)
    parsed = parse_reference_phase_file(
        sanitized,
        target=plan["reserved_target"],
        references=references,
        tags_s=tags,
        step_s=plan["observation"]["required_interval_s"],
        base_day=plan["date_gpst"],
        base_second=0,
        raw_covariance=covariance,
    )
    if parsed["status"] != "REFERENCE_PHASE_WINDOW_PARSED":
        return {"status": "STRUCTURAL_WINDOW_REJECTED", "reasons": parsed.get("reasons", [])}

    context = Context(plan["reserved_target"], plan["date_gpst"])
    records, admitted_navigation = admit_navigation(
        navigation_text, target=plan["reserved_target"], references=references
    )
    midpoint = (tags[0] + tags[-1]) / 2
    selected_records = {satellite: _record_for(records, satellite, midpoint, context)
                        for satellite in references}
    if any(record is None for record in selected_records.values()):
        return {"status": "REFERENCE_MODEL_UNAVAILABLE", "reason": "missing valid navigation record"}
    samples = parsed["samples"]
    codes = np.array([row["code_m"] for row in samples])

    def prediction(clock):
        return np.array([reference_code(
            selected_records[row["satellite"]], row["tag_s"], structure["station_m"], clock,
            context=context, base_second=0.0, propagation="nominal_troposphere",
            max_age_s=plan["navigation"]["maximum_record_age_s"],
        )[0] for row in samples])

    baseline = prediction([0.0, 0.0])
    design_matrix = np.column_stack([np.ones(len(samples)), [row["tag_s"] for row in samples]])
    initial = np.linalg.lstsq(design_matrix, codes - baseline, rcond=None)[0]
    fitted = least_squares(lambda clock: prediction(clock) - codes, initial,
                           x_scale=[1e4, 1.0], max_nfev=50,
                           ftol=1e-11, xtol=1e-11, gtol=1e-9)
    if not fitted.success:
        return {"status": "REFERENCE_MODEL_UNAVAILABLE", "reason": "clock fit did not converge"}
    predicted_code = prediction(fitted.x)
    code_residual = codes - predicted_code
    reference_count = len(references)
    split = []
    for index in range(len(tags)):
        row = code_residual[index * reference_count:(index + 1) * reference_count]
        split.append(abs(float(row[::2].mean() - row[1::2].mean())))
    predicted_rate = interval_matrix(tags, reference_count) @ predicted_code
    observed_rate = np.asarray(parsed["mean_phase_rate_m_s"], float).ravel()
    phase_residual = observed_rate - predicted_rate
    metrics = {
        "status": "STATION_REFERENCE_PATH_EVALUATED",
        "references": references,
        "admitted_observations_sha256": parsed["admitted_observations_sha256"],
        "admitted_navigation_sha256": _sha256(admitted_navigation.encode("ascii")),
        "code_absolute_max_m": float(np.max(np.abs(code_residual))),
        "code_rms_m": float(np.sqrt(np.mean(code_residual ** 2))),
        "alternating_reference_clock_difference_max_m": max(split),
        "phase_rate_absolute_max_m_s": float(np.max(np.abs(phase_residual))),
        "phase_rate_rms_m_s": float(np.sqrt(np.mean(phase_residual ** 2))),
        "phase_rate_median_absolute_m_s": float(np.median(np.abs(phase_residual))),
        "phase_rate_interval_count": len(phase_residual),
        "clock_fit_rank": int(np.linalg.matrix_rank(fitted.jac)),
    }
    limits = plan["admission"]
    checks = {
        "code_absolute": metrics["code_absolute_max_m"] <= limits["maximum_code_absolute_residual_m"],
        "code_rms": metrics["code_rms_m"] <= limits["maximum_code_rms_residual_m"],
        "alternating_reference_clock": metrics["alternating_reference_clock_difference_max_m"] <= limits["maximum_alternating_reference_clock_difference_m"],
        "phase_rate_absolute": metrics["phase_rate_absolute_max_m_s"] <= limits["maximum_phase_rate_absolute_residual_m_s"],
        "phase_rate_rms": metrics["phase_rate_rms_m_s"] <= limits["maximum_phase_rate_rms_residual_m_s"],
        "clock_rank": metrics["clock_fit_rank"] == 2,
    }
    return metrics | {"checks": checks, "admitted": all(checks.values())}


def run(plan_path: Path) -> dict:
    plan_bytes = plan_path.read_bytes()
    plan = json.loads(plan_bytes)
    validate_plan(plan)
    source_path = Path(__file__)
    source_bytes = source_path.read_bytes()
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source_path.resolve().parents[2], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError("source commit unavailable") from error
    freeze = {
        "freeze_utc": _utc_now(),
        "source_commit": commit,
        "plan_sha256": _sha256(plan_bytes),
        "implementation_sha256": _sha256(source_bytes),
        "target_measurement_numeric_access": False,
    }
    receipts, structures, decoded = [], {}, {}
    failures = []
    for station_plan in plan["stations"]:
        station = station_plan["id"]
        url = plan["observation"]["base_url"] + plan["observation"]["filename"].format(station=station)
        try:
            compressed, receipt = _download(url, plan["observation"]["maximum_compressed_bytes_per_station"])
            receipts.append({"station": station, **receipt})
            plain = hatanaka.decompress(compressed, strict=True)
            content = plain.decode("ascii")
            receipts[-1].update(decoded_bytes=len(plain), decoded_sha256=_sha256(plain))
            # Materialization identity is retained before any descriptive or
            # epistemic admission can fail. Receipt failure is never a veto.
            structure = scan_reference_structure(content, plan=plan, station_plan=station_plan)
            sanitized, removed = strip_target_observations(content, plan["reserved_target"])
            if removed != structure["target_rows_discarded_without_field_access"]:
                raise ValueError("target-removal count differs from structural scan")
            structures[station] = structure
            decoded[station] = sanitized
        except RinexRejected as error:
            failures.append({"station": station, "stage": "STRUCTURAL_ADMISSION",
                             "classification": "CAPABILITY_REJECTED", "reason": error.reason})
            break
        except Exception as error:  # one fixed set, no retries/substitution.
            failures.append({"station": station, "stage": "SOURCE_OR_EXECUTION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
            break

    navigation_text = None
    selection = None
    if not failures:
        try:
            compressed, navigation_receipt = _download(
                plan["navigation"]["url"], plan["navigation"]["maximum_compressed_bytes"]
            )
            raw_navigation = gzip.decompress(compressed).decode("ascii")
            navigation_text = strip_target_navigation(raw_navigation, plan["reserved_target"])
            navigation_receipt.update(
                admitted_reference_only_sha256=_sha256(navigation_text.encode("ascii")),
                target_blocks_removed_before_numeric_parse=True,
                raw_navigation_persisted=False,
            )
            selection = select_window(plan, structures, navigation_text)
            if selection is None:
                failures.append({"stage": "SELECTION", "reason": "NO_COMMON_REFERENCE_ONLY_WINDOW"})
        except Exception as error:
            navigation_receipt = None
            failures.append({"stage": "NAVIGATION_OR_SELECTION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
    else:
        navigation_receipt = None

    station_results = {}
    if not failures and selection is not None and navigation_text is not None:
        for station_plan in plan["stations"]:
            station = station_plan["id"]
            try:
                station_results[station] = _station_metrics(
                    plan, structures[station], decoded[station], navigation_text,
                    {"tags_s": selection["tags_s"], "references": selection["references"][station]},
                )
            except Exception as error:
                station_results[station] = {"status": "REFERENCE_MODEL_UNAVAILABLE", "reason": type(error).__name__ + ":" + str(error)}
        for station, result in station_results.items():
            if not result.get("admitted", False):
                failures.append({"station": station, "stage": "PHYSICAL_ADMISSION",
                                 "classification": "CAPABILITY_REJECTED",
                                 "reason": result.get("status", "THRESHOLD_NOT_MET")})

    admitted = not failures and len(station_results) == len(plan["stations"])
    maxima = [result["phase_rate_absolute_max_m_s"] for result in station_results.values()
              if "phase_rate_absolute_max_m_s" in result]
    structural_receipts = {
        station: {
            key: _native(value) for key, value in structure.items() if key != "eligible" and key != "station_m"
        } for station, structure in structures.items()
    }
    execution_invalid = any(item.get("classification") == "QUALIFICATION_ERROR" for item in failures)
    status = ("QUALIFICATION_EXECUTION_INVALID" if execution_invalid
              else "REFERENCE_PHASE_PATH_QUALIFIED" if admitted
              else "PHYSICAL_ERROR_ENVELOPE_NOT_SUPPORTED")
    report = {
        "schema": "s2-real-reference-phase-qualification-result-v1",
        "qualification_id": plan["qualification_id"],
        "status": status,
        "scope": plan["scope"],
        "freeze": freeze,
        "selection": selection,
        "source_receipts": receipts,
        "navigation_receipt": navigation_receipt,
        "structural_receipts": structural_receipts,
        "station_results": station_results,
        "failures": failures,
        "future_phase_rate_envelope_m_s": (
            plan["admission"]["future_envelope_multiplier"] * max(maxima) if admitted else None
        ),
        "unresolved": [
            "The empirical bound is conditional on this date, fixed roots, receiver configurations and selected reference geometry.",
            "Unflagged sub-threshold cycle slips, target-specific multipath/antenna response and future atmosphere are not converted to zero.",
            "No population coverage, target RF qualification, kinematic fit or S3 readiness is established.",
        ],
        "persistence": {
            "compressed_observation_payload": False,
            "decoded_observation_payload": False,
            "individual_observation_values": False,
            "aggregate_residual_metrics_only": True,
            "target_rows_removed_before_observation_numeric_parse": True,
            "raw_payload_bytes_persisted": 0,
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "hatanaka": getattr(hatanaka, "__version__", "unknown"),
        },
    }
    report = _native(report)
    if report["status"] not in TERMINALS:
        raise AssertionError("non-terminal result")
    json.dumps(report, allow_nan=False)
    return report


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
