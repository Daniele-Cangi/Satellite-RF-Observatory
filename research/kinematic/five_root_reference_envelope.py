"""Bounded reference-only residual envelope for the five-root S2 topology."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import urllib.error

import hatanaka
import numpy as np
import scipy
from scipy.optimize import least_squares

from positioning.calibration import (
    antenna_position,
    parse_reference_navigation,
    strip_target_navigation,
)
from positioning.context import Context
from .doppler import ALPHA, BETA, F1_HZ, F2_HZ
from .five_root_role_structure import scan_structure
from .five_root_structure import ROOT, all_roots, sha256_bytes, sha256_path, utc_now
from .phase_transform_header_audit import HeaderRejected, _collect_headers
from .real_reference_qualification import _download, _record_for, strip_target_observations
from .reference_bridge import admit_navigation, reference_code
from .receiver_time import C
from .rinex_observations import RinexRejected, _time


TERMINALS = {
    "FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_QUALIFIED",
    "FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_NOT_SUPPORTED",
    "FIVE_ROOT_REFERENCE_ENVELOPE_EXECUTION_INVALID",
}


class MeasurementRejected(ValueError):
    """Expected source/measurement refusal, never a software-error alias."""


def validate_plan(plan: dict) -> None:
    if plan.get("schema") != "s2-five-root-reference-residual-envelope-plan-v1":
        raise ValueError("unexpected reference-envelope plan")
    if plan.get("qualification_id") != "S2_FIVE_ROOT_REFERENCE_ENVELOPE_2026240":
        raise ValueError("qualification identity differs")
    if plan.get("date_gpst") != "2026-08-28" or plan.get("day_of_year") != 240:
        raise ValueError("frozen distinct day differs")
    if date.fromisoformat(plan["date_gpst"]).timetuple().tm_yday != 240:
        raise ValueError("date/day-of-year mismatch")
    if plan.get("excluded_identity") != "G14":
        raise ValueError("excluded identity differs")
    expected_pool = {f"G{number:02d}" for number in range(1, 33)} - {"G14"}
    if set(plan.get("reference_candidate_pool", [])) != expected_pool:
        raise ValueError("reference candidate pool differs")
    expected_roots = [
        {"id": "ALGO00CAN", "marker": "ALGO",
         "expected_receiver": ["3015995", "SEPT POLARX5", "5.3.2"]},
        {"id": "BOGT00COL", "marker": "BOGT",
         "expected_receiver": ["01972", "JAVAD TRE_3 DELTA", "4.6.00"]},
        {"id": "MKEA00USA", "marker": "MKEA",
         "expected_receiver": ["3013571", "SEPT POLARX5", "5.7.0"]},
        {"id": "PIE100USA", "marker": "PIE1",
         "expected_receiver": ["4100427", "SEPT POLARX5TR", "5.7.0"]},
        {"id": "GOLD00USA", "marker": "GOLD",
         "expected_receiver": ["01538", "JAVAD TRE_G3TH DELTA", "4.2.03"]},
    ]
    if all_roots(plan) != expected_roots:
        raise ValueError("root topology differs")
    selection = plan["selection"]
    if (selection["endpoint_count"] != 11 or selection["references_per_station"] != 4
            or selection["minimum_reference_elevation_deg"] != 15.0
            or not selection["no_reselection_after_numeric_access"]):
        raise ValueError("selection rule differs")
    source = plan["artifact_selection"]
    if (not source["not_a_date_search"] or source["previously_accessed_for_this_qualification"]
            or source["forbidden_days"] != [241, 242] or not source["no_retry"]
            or not source["no_date_station_field_or_reference_substitution"]
            or source["base_url"] != "https://igs.bkg.bund.de/root_ftp/IGS/obs/2026/240/"
            or source["filename"] != "{station}_R_20262400000_01D_30S_MO.crx.gz"
            or source["minimum_archive_age_after_last_epoch_s"] < 86400):
        raise ValueError("bounded source rule differs")
    obs = plan["observation"]
    if (obs["fit_fields"] != ["C1C", "C2W", "L1C", "L2W"]
            or obs["heldout_fields"] != ["C1C", "C2W"]
            or obs["required_rinex_versions"] != ["3.04", "3.05"]
            or obs["required_time_system"] != "GPS"
            or obs["required_interval_s"] != 30.0
            or obs["required_first_epoch"] != [2026, 8, 28, 0, 0, 0.0]
            or obs["required_last_epoch"] != [2026, 8, 28, 23, 59, 30.0]
            or not obs["no_interpolation"] or not obs["no_gap_bridging"]):
        raise ValueError("observable coordinate differs")
    transform = plan["transform_admission"]
    if (transform["fit"]["stored_value_scale_divisor"]
            != {"C1C": 1, "C2W": 1, "L1C": 1, "L2W": 1}
            or transform["fit"]["phase_shift_semantics"]
            != "DECLARED_STATIC_OFFSETS_RETAINED_AND_REVERSIBLE"
            or not transform["fit"]["same_satellite_interval_difference_cancels_stable_offset"]
            or not transform["fit"]["satellite_phase_overrides_allowed_if_declared"]
            or transform["fit"]["legacy_wavelength_header_allowed"]
            or transform["fit"]["applied_gps_dcb_or_pcv_allowed"]
            or transform["fit"]["receiver_clock_offset_applied"]
            or transform["heldout_code"]["stored_value_scale_divisor"]
            != {"C1C": 1, "C2W": 1}
            or transform["heldout_code"]["phase_transform_in_causal_path"]
            or transform["heldout_code"]["phase_transform_headers_interpreted"]):
        raise ValueError("role transform semantics differ")
    navigation = plan["navigation"]
    if (navigation["url"]
            != "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/2026/240/BRDM00DLR_S_20262400000_01D_MN.rnx.gz"
            or navigation["maximum_record_age_s"] != 7200.0
            or not navigation["target_blocks_removed_before_numeric_parse"]):
        raise ValueError("navigation boundary differs")
    limits = plan["admission"]
    exact_limits = {
        "maximum_code_absolute_residual_m": 50.0,
        "maximum_code_rms_residual_m": 20.0,
        "maximum_alternating_reference_clock_difference_m": 30.0,
        "maximum_fit_phase_rate_absolute_residual_m_s": 0.05,
        "maximum_fit_phase_rate_rms_residual_m_s": 0.02,
        "future_envelope_multiplier": 2.0,
    }
    if any(limits[key] != value for key, value in exact_limits.items()):
        raise ValueError("inherited numerical limit differs")
    if not all(limits[key] for key in (
            "require_complete_station_set", "require_unchanged_receiver_identity",
            "require_zero_reported_phase_lli", "require_no_gap_in_selected_window")):
        raise ValueError("required admission disabled")
    if set(plan.get("outcomes", [])) != TERMINALS:
        raise ValueError("terminal set differs")
    frozen = plan["frozen_inputs"]
    for file_key, hash_key in (
        ("role_structure_result", "role_structure_result_sha256"),
        ("inherited_threshold_plan", "inherited_threshold_plan_sha256"),
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
    if subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT, text=True).strip():
        raise ValueError("working tree must be clean before source access")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if actual != source_commit:
        raise ValueError("source commit differs from HEAD")
    for path in (plan_path, Path(__file__)):
        relative = path.resolve().relative_to(ROOT).as_posix()
        if subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT) != path.read_bytes():
            raise ValueError("frozen file differs from committed bytes:" + relative)


def _station_position(content: str) -> np.ndarray:
    lines = content.splitlines()
    end = next(index for index, row in enumerate(lines)
               if row[60:80].strip() == "END OF HEADER")
    headers, _ = _collect_headers(lines[:end + 1])
    position = np.asarray(antenna_position(headers), float)
    if position.shape != (3,) or not np.isfinite(position).all():
        raise ValueError("invalid station position")
    return position


def _navigation_target_block_count(content: str, target: str) -> int:
    lines = content.splitlines()
    start = next(index for index, row in enumerate(lines)
                 if row[60:80].strip() == "END OF HEADER") + 1
    count, index = 0, start
    while index < len(lines):
        if lines[index].startswith("G"):
            count += lines[index][:3] == target
            index += 8
        else:
            index += 1
    return int(count)


def select_window(plan: dict, structures: dict, positions: dict,
                  navigation_text: str) -> dict | None:
    """Select using field topology and non-target geometry, never magnitudes."""
    target = plan["excluded_identity"]
    context = Context(target, plan["date_gpst"])
    navigation = parse_reference_navigation(navigation_text, target)
    step = plan["observation"]["required_interval_s"]
    count = plan["selection"]["endpoint_count"]
    first = 0.0
    last = 86370.0 - (count - 1) * step
    pool = set(plan["reference_candidate_pool"])
    for start in np.arange(first, last + step / 2, step):
        tags = [float(start + index * step) for index in range(count)]
        chosen = {}
        for root in all_roots(plan):
            station = root["id"]
            eligible = structures[station]
            if any(tag not in eligible for tag in tags):
                break
            candidates = set.intersection(*(eligible[tag] for tag in tags)) & pool
            admitted = []
            for satellite in sorted(candidates):
                record = _record_for(navigation, satellite, start + (count - 1) * step / 2,
                                     context)
                if record is None:
                    continue
                try:
                    elevations = [reference_code(
                        record, tag, positions[station], [0.0, 0.0], context=context,
                        base_second=0.0, propagation="nominal_troposphere",
                        max_age_s=plan["navigation"]["maximum_record_age_s"],
                    )[1] for tag in tags]
                except ValueError:
                    continue
                if min(elevations) >= plan["selection"]["minimum_reference_elevation_deg"]:
                    admitted.append(satellite)
            if len(admitted) < plan["selection"]["references_per_station"]:
                break
            chosen[station] = admitted[:plan["selection"]["references_per_station"]]
        if len(chosen) == len(all_roots(plan)):
            return {"start_s": float(start), "tags_s": tags, "references": chosen,
                    "selection_uses_observation_magnitudes": False}
    return None


def parse_numeric_window(content: str, plan: dict, references: list[str],
                         tags: list[float], role: str) -> dict:
    """Decode only selected non-target fields after textual target removal."""
    lines = content.splitlines()
    end = next(index for index, row in enumerate(lines)
               if row[60:80].strip() == "END OF HEADER")
    _, systems = _collect_headers(lines[:end + 1])
    types = systems["G"]
    names = ["C1C", "C2W"] + (["L1C", "L2W"] if role == "FIT" else [])
    indices = {name: types.index(name) for name in names}
    tag_index = {round(tag, 7): index for index, tag in enumerate(tags)}
    collected: dict[tuple[int, str], list[float]] = {}
    index = end + 1
    while index < len(lines):
        epoch = lines[index]
        index += 1
        fields = epoch[1:].split()
        tag = _time(fields[:6], plan["date_gpst"], 0)
        flag, count = int(fields[6]), int(fields[7])
        block, index = lines[index:index + count], index + count
        key = round(tag, 7)
        if key not in tag_index:
            continue
        if flag != 0:
            raise MeasurementRejected("EVENT_FLAG_IN_SELECTED_WINDOW")
        rows = {row[:3]: row for row in block if row[:3] in references}
        for satellite in references:
            row = rows.get(satellite)
            if row is None:
                raise MeasurementRejected("SELECTED_REFERENCE_ROW_ABSENT")
            values = []
            for name in names:
                field = row[3 + 16 * indices[name]:3 + 16 * (indices[name] + 1)].ljust(16)
                try:
                    value = float(field[:14])
                except ValueError as error:
                    raise MeasurementRejected("INVALID_SELECTED_FIELD:" + name) from error
                if not np.isfinite(value) or value == 0.0:
                    raise MeasurementRejected("INVALID_SELECTED_FIELD:" + name)
                if name.startswith("C") and value < 0.0:
                    raise MeasurementRejected("NEGATIVE_SELECTED_CODE")
                if name.startswith("L") and field[14] not in (" ", "0"):
                    raise MeasurementRejected("NONZERO_SELECTED_PHASE_LLI")
                values.append(value)
            collected[(tag_index[key], satellite)] = values
    ordered = [(index, satellite) for index in range(len(tags)) for satellite in references]
    if set(collected) != set(ordered):
        raise MeasurementRejected("SELECTED_NUMERIC_GRID_INCOMPLETE")
    raw = np.asarray([collected[key] for key in ordered], float)
    code = ALPHA * raw[:, 0] + BETA * raw[:, 1]
    result = {"code_m": code, "admitted_values_sha256": hashlib.sha256(
        json.dumps(raw.tolist(), sort_keys=True, allow_nan=False).encode()).hexdigest()}
    if role == "FIT":
        phase_path = ALPHA * C / F1_HZ * raw[:, 2] + BETA * C / F2_HZ * raw[:, 3]
        result["phase_path_m"] = phase_path
    return result


def station_metrics(plan: dict, station: str, role: str, position: np.ndarray,
                    parsed: dict, references: list[str], tags: list[float],
                    navigation_text: str) -> dict:
    context = Context(plan["excluded_identity"], plan["date_gpst"])
    try:
        records, admitted_navigation = admit_navigation(
            navigation_text, target=plan["excluded_identity"], references=references)
    except ValueError as error:
        raise MeasurementRejected("REFERENCE_NAVIGATION_NOT_ADMITTED:" + str(error)) from error
    midpoint = (tags[0] + tags[-1]) / 2
    selected = {satellite: _record_for(records, satellite, midpoint, context)
                for satellite in references}
    if any(record is None for record in selected.values()):
        raise MeasurementRejected("SELECTED_REFERENCE_NAVIGATION_UNAVAILABLE")
    ordered = [(tag, satellite) for tag in tags for satellite in references]

    def prediction(clock: np.ndarray) -> np.ndarray:
        return np.asarray([reference_code(
            selected[satellite], tag, position, clock, context=context, base_second=0.0,
            propagation="nominal_troposphere",
            max_age_s=plan["navigation"]["maximum_record_age_s"],
        )[0] for tag, satellite in ordered])

    baseline = prediction(np.array([0.0, 0.0]))
    design = np.column_stack([np.ones(len(ordered)), [tag for tag, _ in ordered]])
    initial = np.linalg.lstsq(design, parsed["code_m"] - baseline, rcond=None)[0]
    fitted = least_squares(lambda clock: prediction(clock) - parsed["code_m"], initial,
                           x_scale=[1e4, 1.0], max_nfev=50,
                           ftol=1e-11, xtol=1e-11, gtol=1e-9)
    if not fitted.success or np.linalg.matrix_rank(fitted.jac) != 2:
        raise MeasurementRejected("REFERENCE_CLOCK_FIT_UNAVAILABLE")
    model = prediction(fitted.x)
    code_residual = parsed["code_m"] - model
    per_epoch = code_residual.reshape(len(tags), len(references))
    split = np.abs(per_epoch[:, ::2].mean(axis=1) - per_epoch[:, 1::2].mean(axis=1))
    output = {
        "station": station, "role": role, "status": "REFERENCE_PATH_EVALUATED",
        "references": references,
        "admitted_observations_sha256": parsed["admitted_values_sha256"],
        "admitted_navigation_sha256": sha256_bytes(admitted_navigation.encode("ascii")),
        "code_absolute_max_m": float(np.max(np.abs(code_residual))),
        "code_rms_m": float(np.sqrt(np.mean(code_residual ** 2))),
        "alternating_reference_clock_difference_max_m": float(np.max(split)),
        "clock_fit_rank": int(np.linalg.matrix_rank(fitted.jac)),
        "individual_observations_persisted": False,
        "individual_residuals_persisted": False,
    }
    limits = plan["admission"]
    checks = {
        "code_absolute": output["code_absolute_max_m"] <= limits["maximum_code_absolute_residual_m"],
        "code_rms": output["code_rms_m"] <= limits["maximum_code_rms_residual_m"],
        "alternating_reference_clock": output["alternating_reference_clock_difference_max_m"] <= limits["maximum_alternating_reference_clock_difference_m"],
        "clock_rank": output["clock_fit_rank"] == 2,
    }
    if role == "FIT":
        observed_rate = np.diff(parsed["phase_path_m"].reshape(
            len(tags), len(references)), axis=0) / np.diff(tags)[:, None]
        predicted_rate = np.diff(model.reshape(len(tags), len(references)), axis=0) / np.diff(tags)[:, None]
        phase_residual = observed_rate - predicted_rate
        output.update({
            "phase_rate_absolute_max_m_s": float(np.max(np.abs(phase_residual))),
            "phase_rate_rms_m_s": float(np.sqrt(np.mean(phase_residual ** 2))),
            "phase_rate_interval_count": int(phase_residual.size),
        })
        checks.update({
            "phase_rate_absolute": output["phase_rate_absolute_max_m_s"] <= limits["maximum_fit_phase_rate_absolute_residual_m_s"],
            "phase_rate_rms": output["phase_rate_rms_m_s"] <= limits["maximum_fit_phase_rate_rms_residual_m_s"],
        })
    output["checks"] = checks
    output["admitted"] = all(checks.values())
    return output


def run(plan_path: Path, source_commit: str) -> dict:
    plan = json.loads(plan_path.read_bytes())
    validate_plan(plan)
    admit_archive_age(plan)
    admit_git_freeze(plan_path, source_commit)
    receipts, summaries, structures, positions, sanitized = [], {}, {}, {}, {}
    failures = []
    execution_invalid = False
    source = plan["artifact_selection"]
    for index, root in enumerate(all_roots(plan)):
        station = root["id"]
        role = "FIT" if index < 4 else "HELDOUT_CODE"
        url = source["base_url"] + source["filename"].format(station=station)
        try:
            compressed, receipt = _download(url, source["maximum_compressed_bytes_per_station"])
            receipts.append({"station": station, **receipt})
            decoded = hatanaka.decompress(compressed, strict=True)
            if len(decoded) > source["maximum_decoded_bytes_per_station"]:
                raise ValueError("decoded artifact exceeds frozen byte bound")
            content = decoded.decode("ascii")
            target_free, removed = strip_target_observations(content, plan["excluded_identity"])
            summary, eligible = scan_structure(target_free, plan, root, role)
            receipts[-1].update({"decoded_bytes": len(decoded),
                                 "decoded_sha256": sha256_bytes(decoded),
                                 "target_rows_removed_before_numeric_parse": removed,
                                 "complete_artifact_hashed_before_decode": True})
            summaries[station], structures[station] = summary, eligible
            positions[station], sanitized[station] = _station_position(target_free), target_free
        except urllib.error.HTTPError as error:
            receipts.append({"station": station, "url": url, "http_status": error.code,
                             "access_utc": utc_now(), "artifact_materialized": False})
            failures.append({"station": station, "stage": "SOURCE_MATERIALIZATION",
                             "classification": "CAPABILITY_REJECTED",
                             "reason": f"SOURCE_HTTP_{error.code}"})
        except (HeaderRejected, RinexRejected) as error:
            reason = getattr(error, "reason", str(error))
            failures.append({"station": station, "stage": "STRUCTURAL_ADMISSION",
                             "classification": "CAPABILITY_REJECTED", "reason": reason})
        except Exception as error:
            execution_invalid = True
            failures.append({"station": station, "stage": "STRUCTURAL_EXECUTION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
    navigation_text, navigation_receipt, selection = None, None, None
    if not failures:
        try:
            compressed, navigation_receipt = _download(
                plan["navigation"]["url"], plan["navigation"]["maximum_compressed_bytes"])
            raw_navigation = gzip.decompress(compressed).decode("ascii")
            removed = _navigation_target_block_count(raw_navigation, plan["excluded_identity"])
            navigation_text = strip_target_navigation(raw_navigation, plan["excluded_identity"])
            navigation_receipt.update({
                "target_blocks_removed_before_numeric_parse": removed,
                "admitted_reference_only_sha256": sha256_bytes(navigation_text.encode("ascii")),
                "raw_navigation_persisted": False,
            })
            selection = select_window(plan, structures, positions, navigation_text)
            if selection is None:
                failures.append({"stage": "SELECTION", "classification": "CAPABILITY_REJECTED",
                                 "reason": "NO_COMMON_REFERENCE_ONLY_WINDOW"})
        except Exception as error:
            execution_invalid = True
            failures.append({"stage": "NAVIGATION_OR_SELECTION",
                             "classification": "QUALIFICATION_ERROR",
                             "reason": type(error).__name__ + ":" + str(error)})
    station_results = {}
    if not failures and selection is not None and navigation_text is not None:
        for index, root in enumerate(all_roots(plan)):
            station = root["id"]
            role = "FIT" if index < 4 else "HELDOUT_CODE"
            try:
                parsed = parse_numeric_window(sanitized[station], plan,
                                              selection["references"][station],
                                              selection["tags_s"], role)
                result = station_metrics(plan, station, role, positions[station], parsed,
                                         selection["references"][station],
                                         selection["tags_s"], navigation_text)
                station_results[station] = result
                if not result["admitted"]:
                    failures.append({"station": station, "stage": "REFERENCE_RESIDUAL_ADMISSION",
                                     "classification": "CAPABILITY_REJECTED",
                                     "reason": "FROZEN_RESIDUAL_LIMIT_NOT_MET"})
            except MeasurementRejected as error:
                failures.append({"station": station, "stage": "NUMERIC_ADMISSION",
                                 "classification": "CAPABILITY_REJECTED",
                                 "reason": str(error)})
            except Exception as error:
                execution_invalid = True
                failures.append({"station": station, "stage": "NUMERIC_EXECUTION",
                                 "classification": "QUALIFICATION_ERROR",
                                 "reason": type(error).__name__ + ":" + str(error)})
    admitted = not failures and len(station_results) == 5
    status = ("FIVE_ROOT_REFERENCE_ENVELOPE_EXECUTION_INVALID" if execution_invalid
              else "FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_QUALIFIED" if admitted
              else "FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_NOT_SUPPORTED")
    fit_phase = [row["phase_rate_absolute_max_m_s"] for row in station_results.values()
                 if row["role"] == "FIT" and "phase_rate_absolute_max_m_s" in row]
    gold = station_results.get("GOLD00USA", {})
    multiplier = plan["admission"]["future_envelope_multiplier"]
    report = {
        "schema": "s2-five-root-reference-residual-envelope-result-v1",
        "qualification_id": plan["qualification_id"], "status": status,
        "scope": plan["scope"],
        "freeze": {"source_commit": source_commit, "plan_sha256": sha256_path(plan_path),
                   "implementation_sha256": sha256_path(Path(__file__))},
        "source_receipts": receipts, "navigation_receipt": navigation_receipt,
        "structural_receipts": summaries, "selection": selection,
        "station_results": station_results, "failures": failures,
        "conditional_reference_envelopes": {
            "fit_phase_rate_m_s": multiplier * max(fit_phase) if admitted else None,
            "gold_code_m": multiplier * gold["code_absolute_max_m"] if admitted else None,
            "multiplier": multiplier,
            "population_coverage_claim": False,
        },
        "clauses": {
            "COMPLETE_ROLE_SPECIFIC_STRUCTURE": "SATISFIED" if len(summaries) == 5 else "NOT_SATISFIED",
            "TARGET_EXCLUSION_BEFORE_NUMERIC_PARSE": "SATISFIED" if len(summaries) == 5 and navigation_receipt else "NOT_EVALUATED",
            "REFERENCE_RESIDUAL_ENVELOPE": "SATISFIED" if admitted else "NOT_SATISFIED" if station_results else "NOT_EVALUATED",
            "TOTAL_FUTURE_TARGET_PHYSICAL_ENVELOPE": "UNRESOLVED",
        },
        "unresolved_terms": plan["unresolved_terms"],
        "interpretation": {"target_selected": False, "target_orbit_accessed": False,
                           "excluded_identity_used_only_as_text_filter": True,
                           "s3_authorized": False},
        "persistence": plan["persistence"],
        "environment": {"python": platform.python_version(), "numpy": np.__version__,
                        "scipy": scipy.__version__,
                        "hatanaka": getattr(hatanaka, "__version__", "unknown")},
    }
    json.dumps(report, allow_nan=False, sort_keys=True)
    return report


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
                      "selection": result["selection"],
                      "envelopes": result["conditional_reference_envelopes"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
