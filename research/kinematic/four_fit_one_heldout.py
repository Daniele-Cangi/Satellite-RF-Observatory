"""Target-free leave-one-root-out information audit for the five qualified roots."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess

import numpy as np
import scipy
from scipy.linalg import block_diag, solve_triangular
from scipy.stats import chi2

from .five_root_feasibility import (
    fibonacci_directions,
    load_plan as load_five_root_plan,
    minimum_elevation_deg,
    state_for,
    strict_json,
)
from .heldout_code_topology import heldout_code_metric
from .phase_rates import interval_matrix
from .receiver_time import central_jacobian, cholesky_covariance, predict


ROOT = Path(__file__).resolve().parents[2]
TERMINALS = {
    "FOUR_FIT_ONE_HELDOUT_CONDITIONALLY_AVAILABLE",
    "FOUR_FIT_ONE_HELDOUT_NOT_SUPPORTED",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def admit_git_freeze(root: Path, plan_path: Path, source_commit: str) -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"], cwd=root, text=True
    )
    if status.strip():
        raise ValueError("working tree must be clean before execution")
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if actual != source_commit:
        raise ValueError("source commit differs from current HEAD")
    for path in (plan_path, Path(__file__)):
        relative = path.resolve().relative_to(root.resolve()).as_posix()
        committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=root)
        if committed != path.read_bytes():
            raise ValueError("frozen file differs from committed bytes:" + relative)


def load_plan(path: Path) -> tuple[dict, str, dict, dict, dict]:
    raw = path.read_bytes()
    plan = json.loads(raw)
    if plan.get("schema") != "s2-four-fit-one-heldout-topology-plan-v1":
        raise ValueError("unexpected plan schema")
    frozen = plan["frozen_inputs"]
    bindings = (
        ("five_root_plan", "five_root_plan_sha256"),
        ("five_root_result", "five_root_result_sha256"),
        ("heldout_topology_plan", "heldout_topology_plan_sha256"),
        ("heldout_topology_result", "heldout_topology_result_sha256"),
    )
    for file_key, hash_key in bindings:
        if sha256(ROOT / frozen[file_key]) != frozen[hash_key]:
            raise ValueError(file_key + " hash mismatch")
    five_plan, _ = load_five_root_plan(ROOT / frozen["five_root_plan"])
    five_result = json.loads((ROOT / frozen["five_root_result"]).read_text())
    heldout_plan = json.loads((ROOT / frozen["heldout_topology_plan"]).read_text())
    heldout_result = json.loads((ROOT / frozen["heldout_topology_result"]).read_text())
    allocation = plan["root_allocation"]
    expected = [row["station"] for row in five_plan["fit_roots"]]
    if (allocation["root_ids"] != expected or allocation["partition_count"] != 5
            or allocation["fit_root_count"] != 4 or allocation["heldout_root_count"] != 1):
        raise ValueError("leave-one-root-out allocation differs")
    boundary = plan["selection_boundary"]
    if (boundary["target_identifier"] is not None or boundary["target_date"] is not None
            or boundary["target_orbit_or_radius_constraint"] is not False
            or boundary["real_observation_values"] is not False
            or boundary["new_network_access"] is not False):
        raise ValueError("target/access boundary violated")
    if five_result["status"] != "FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE":
        raise ValueError("unexpected five-root predecessor")
    if heldout_result["status"] != "HELDOUT_CODE_TOPOLOGY_CONDITIONALLY_AVAILABLE":
        raise ValueError("unexpected heldout predecessor")
    measurement = plan["measurement_design"]
    inherited = heldout_plan["heldout_prediction"]
    if (measurement["heldout_receive_tags_s"] != inherited["receive_tags_s"]
            or measurement["minimum_elevation_deg"] != inherited["minimum_elevation_deg"]
            or measurement["absolute_heldout_range_equivalent_limit_m"]
            != inherited["absolute_range_equivalent_limit_m"]
            or measurement["maximum_fit_position_envelope_m"]
            != five_plan["frozen_clauses"]["maximum_conditional_local_position_envelope_m"]
            or measurement["minimum_conditionally_usable_synthetic_cases"]
            != five_plan["frozen_clauses"]["minimum_joint_visible_synthetic_cases"]
            or not measurement["reuse_five_root_endpoint_tags_and_error_assumptions"]
            or measurement["holdout_fitted_offset_allowed"]):
        raise ValueError("inherited measurement design differs")
    if set(plan["outcomes"]) != TERMINALS:
        raise ValueError("terminal set differs")
    return plan, hashlib.sha256(raw).hexdigest(), five_plan, five_result, heldout_plan


def measurement_design(five_plan: dict, root_count: int) -> dict:
    design = five_plan["conditional_measurement_design"]
    tags = np.asarray(five_plan["synthetic_family"]["endpoint_tags_s"], float)
    count = len(tags) * root_count
    difference = interval_matrix(tags, root_count)
    raw = block_diag(
        design["endpoint_code_sigma_m"] ** 2 * np.eye(count),
        design["endpoint_phase_path_sigma_m"] ** 2 * np.eye(count),
        np.kron(np.eye(root_count), np.diag([
            design["receiver_clock_offset_sigma_m"] ** 2,
            design["receiver_clock_drift_sigma_m_s"] ** 2,
        ])),
        design["ground_coordinate_sigma_m"] ** 2 * np.eye(3 * root_count),
    )
    cross = (design["code_phase_correlation"] * design["endpoint_code_sigma_m"]
             * design["endpoint_phase_path_sigma_m"])
    raw[:count, count:2 * count] = cross * np.eye(count)
    raw[count:2 * count, :count] = cross * np.eye(count)
    modes = np.zeros((len(raw), 2 * root_count))
    for root in range(root_count):
        modes[root:count:root_count, 2 * root] = 5.0
        modes[2 * count + 2 * root, 2 * root] = 4.0
        modes[2 * count + 2 * root_count + 3 * root, 2 * root] = 0.2
        modes[root:count:root_count, 2 * root + 1] = tags * 0.01
        modes[count + root:2 * count:root_count, 2 * root + 1] = tags * 0.01
        modes[2 * count + 2 * root + 1, 2 * root + 1] = 0.008
    raw += modes @ modes.T
    transform = block_diag(np.eye(count), difference, np.eye(5 * root_count))
    covariance = transform @ raw @ transform.T
    covariance = (covariance + covariance.T) / 2
    return {
        "tags": tags,
        "count": count,
        "nrate": len(difference),
        "difference": difference,
        "covariance": covariance,
    }


def fit_response(state: np.ndarray, stations: np.ndarray, design: dict, five_plan: dict) -> dict:
    tags, root_count = design["tags"], len(stations)
    count, nrate = design["count"], design["nrate"]
    clock_end = 11 + 2 * root_count
    scale = np.r_[
        [1e7] * 3, [1e3] * 3, [1.0] * 3, 1e5, 10.0,
        np.tile([1000.0, 1.0], root_count), np.full(3 * root_count, 1e5),
    ]
    point = np.r_[state, np.zeros(5 * root_count)]

    def model(z):
        physical = z * scale
        pair = predict(
            physical[:11], tags,
            stations + physical[clock_end:].reshape(root_count, 3),
            physical[11:clock_end].reshape(root_count, 2),
        )
        code = pair["code_m"].ravel()
        return np.r_[code, design["difference"] @ code, physical[11:]]

    jacobian = central_jacobian(model, point / scale) / scale
    chol = cholesky_covariance(design["covariance"], len(design["covariance"]))
    scaled = solve_triangular(chol, jacobian * scale, lower=True)
    u, singular, vh = np.linalg.svd(scaled, full_matrices=False)
    threshold = five_plan["frozen_clauses"]["maximum_scaled_condition"]
    rank = int(np.sum(singular > singular[0] / threshold))
    if len(singular) != len(scale) or rank != len(scale):
        return {"full_rank": False, "rank": rank, "parameter_count": len(scale)}
    inverse = scale[:, None] * ((vh.T / singular) @ u.T)
    gain = inverse @ solve_triangular(chol, np.eye(len(chol)), lower=True)
    parameter_covariance = inverse @ inverse.T
    bounds = five_plan["conditional_measurement_design"]
    systematic = np.zeros((len(design["covariance"]), 2 * root_count))
    for root in range(root_count):
        systematic[root:count:root_count, 2 * root] = bounds["persistent_code_bias_box_m_per_root"]
        systematic[count + root:count + nrate:root_count, 2 * root + 1] = (
            bounds["persistent_interval_rate_bias_box_m_s_per_root"]
        )
    return {
        "full_rank": True,
        "rank": len(scale),
        "parameter_count": len(scale),
        "scale": scale,
        "covariance": parameter_covariance,
        "systematic_parameter_modes": gain @ systematic,
        "scaled_condition": float(singular[0] / singular[-1]),
    }


def position_envelope(response: dict, seconds: float) -> dict:
    mapping = np.zeros((3, len(response["scale"])))
    mapping[:, :3] = np.eye(3)
    mapping[:, 3:6] = seconds * np.eye(3)
    mapping[:, 6:9] = 0.5 * seconds ** 2 * np.eye(3)
    covariance = mapping @ response["covariance"] @ mapping.T
    gaussian = float(np.sqrt(chi2.ppf(0.95, 3) * max(0.0, np.linalg.eigvalsh(covariance)[-1])))
    affine = float(np.linalg.norm(mapping @ response["systematic_parameter_modes"], axis=0).sum())
    return {
        "receive_tag_s": seconds,
        "local_gaussian_position_radius95_m": gaussian,
        "affine_box_position_norm_bound_m": affine,
        "conditional_local_position_envelope_m": gaussian + affine,
    }


def summarize(values: list[float]) -> dict | None:
    array = np.asarray(values, float)
    if not len(array):
        return None
    return {"minimum": float(array.min()), "median": float(np.median(array)),
            "maximum": float(array.max())}


def run(plan_path: Path, source_commit: str) -> dict:
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("exact lowercase source commit required")
    admit_git_freeze(ROOT, plan_path, source_commit)
    plan, plan_hash, five_plan, five_result, heldout_plan = load_plan(plan_path)
    roots = five_plan["fit_roots"]
    directions = fibonacci_directions(five_plan["synthetic_family"]["fibonacci_direction_count"])
    motions = {row["name"]: row for row in five_plan["synthetic_family"]["motion_templates"]}
    cases = five_result["cases"]
    partitions = []
    fit_limit = plan["measurement_design"]["maximum_fit_position_envelope_m"]
    heldout_tags = plan["measurement_design"]["heldout_receive_tags_s"]
    for heldout_index, heldout_root in enumerate(roots):
        fit_roots = [row for index, row in enumerate(roots) if index != heldout_index]
        fit_stations = np.asarray([row["ecef_m"] for row in fit_roots], float)
        heldout_station = np.asarray(heldout_root["ecef_m"], float)
        design = measurement_design(five_plan, len(fit_roots))
        rows, rank_failures = [], 0
        for old in cases:
            state = state_for(
                directions[old["direction_index"]], old["radius_m"], motions[old["motion"]]
            )
            response = fit_response(state, fit_stations, design, five_plan)
            if not response["full_rank"]:
                rank_failures += 1
                rows.append({"direction_index": old["direction_index"], "radius_m": old["radius_m"],
                             "motion": old["motion"], "fit_full_rank": False,
                             "conditionally_usable": False})
                continue
            fit_metrics = [position_envelope(response, seconds) for seconds in (0.0, 60.0)]
            fit_margin = all(row["conditional_local_position_envelope_m"] <= fit_limit
                             for row in fit_metrics)
            heldout_elevation = minimum_elevation_deg(state, heldout_tags, [heldout_station])
            visible = heldout_elevation >= plan["measurement_design"]["minimum_elevation_deg"]
            endpoint_metrics = ([heldout_code_metric(
                state, heldout_station, seconds, response, heldout_plan
            ) for seconds in heldout_tags] if visible else [])
            positive = bool(endpoint_metrics) and all(row["positive_physical_slack"]
                                                       for row in endpoint_metrics)
            rows.append({
                "direction_index": old["direction_index"], "radius_m": old["radius_m"],
                "motion": old["motion"], "fit_full_rank": True,
                "scaled_condition": response["scaled_condition"],
                "fit_position": fit_metrics,
                "heldout_minimum_elevation_deg": heldout_elevation,
                "heldout_visible": visible,
                "heldout_endpoints": endpoint_metrics,
                "conditionally_usable": bool(fit_margin and visible and positive),
            })
        usable = sum(row["conditionally_usable"] for row in rows)
        visible = sum(row.get("heldout_visible", False) for row in rows)
        slacks = [endpoint["remaining_physical_affine_slack_m"] for row in rows
                  for endpoint in row.get("heldout_endpoints", [])]
        fit_60 = [row["fit_position"][1]["conditional_local_position_envelope_m"]
                  for row in rows if row["fit_full_rank"]]
        partitions.append({
            "heldout_root": heldout_root["station"],
            "fit_roots": [row["station"] for row in fit_roots],
            "predecessor_cases": len(rows),
            "rank_failures": rank_failures,
            "heldout_visible_cases": visible,
            "conditionally_usable_cases": usable,
            "fit_t_plus_60_envelope_m": summarize(fit_60),
            "heldout_physical_slack_m": summarize(slacks),
            "cases": rows,
        })
    ranked = sorted(partitions, key=lambda row: (
        row["conditionally_usable_cases"], row["heldout_visible_cases"],
        row["heldout_physical_slack_m"]["median"] if row["heldout_physical_slack_m"] else -np.inf,
    ), reverse=True)
    minimum = plan["measurement_design"]["minimum_conditionally_usable_synthetic_cases"]
    available = bool(ranked and ranked[0]["rank_failures"] == 0
                     and ranked[0]["conditionally_usable_cases"] >= minimum)
    status = ("FOUR_FIT_ONE_HELDOUT_CONDITIONALLY_AVAILABLE" if available
              else "FOUR_FIT_ONE_HELDOUT_NOT_SUPPORTED")
    result = {
        "schema": "s2-four-fit-one-heldout-topology-result-v1",
        "status": status,
        "scope": plan["scope"],
        "freeze": {"source_commit": source_commit, "plan_sha256": plan_hash,
                   **{key: plan["frozen_inputs"][key] for key in plan["frozen_inputs"] if key.endswith("sha256")}},
        "input_boundaries": {
            "target_or_orbit_used": False,
            "observation_values_read": False,
            "new_network_access": False,
            "all_five_partitions_retained": True,
        },
        "partition_ranking": [row["heldout_root"] for row in ranked],
        "partitions": ranked,
        "clauses": {
            "FOUR_ROOT_LOCAL_IDENTIFIABILITY": "SATISFIED" if all(row["rank_failures"] == 0 for row in ranked) else "NOT_SATISFIED",
            "CONDITIONAL_FIT_AND_HELDOUT_MARGIN": "SATISFIED" if available else "NOT_SATISFIED",
            "REAL_MEASUREMENT_ADMISSION": "UNRESOLVED",
            "TOTAL_PHYSICAL_ERROR_ENVELOPE": "UNRESOLVED",
        },
        "interpretation": {
            "forward_vertical_complete": False,
            "partition_ranking_is_target_or_receiver_admission": False,
            "s3_authorized": False,
            "claim": "Synthetic local leave-one-out topology only; no target, real-measurement or orbit claim.",
        },
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "sources_sha256": {name: sha256(ROOT / name) for name in [
            "research/kinematic/four_fit_one_heldout.py",
            "research/kinematic/five_root_feasibility.py",
            "research/kinematic/heldout_code_topology.py",
            "research/kinematic/receiver_time.py",
        ]},
    }
    if status not in TERMINALS:
        raise AssertionError("non-terminal result")
    return strict_json(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source-commit", required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing report")
    result = run(args.plan, args.source_commit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({
        "status": result["status"], "partition_ranking": result["partition_ranking"],
        "partitions": [{key: row[key] for key in (
            "heldout_root", "rank_failures", "heldout_visible_cases",
            "conditionally_usable_cases", "fit_t_plus_60_envelope_m",
            "heldout_physical_slack_m")}
            for row in result["partitions"]], "clauses": result["clauses"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
