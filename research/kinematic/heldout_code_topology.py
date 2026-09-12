"""Target-free offline audit of one code-only root held out from a five-root fit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import solve_triangular
from scipy.stats import norm

from .five_root_feasibility import (
    fibonacci_directions,
    load_plan as load_five_root_plan,
    measurement_design,
    minimum_elevation_deg,
    state_for,
    strict_json,
)
from .receiver_time import central_jacobian, cholesky_covariance, predict

ROOT = Path(__file__).resolve().parents[2]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_plan(path: Path) -> tuple[dict, str, dict, dict]:
    raw = path.read_bytes()
    plan = json.loads(raw)
    if plan.get("schema") != "s2-heldout-code-topology-plan-v1":
        raise ValueError("unexpected topology plan schema")
    frozen = plan["frozen_inputs"]
    five_plan_path = ROOT/frozen["five_root_plan"]
    five_result_path = ROOT/frozen["five_root_result"]
    if sha256(five_plan_path) != frozen["five_root_plan_sha256"]:
        raise ValueError("five-root plan hash mismatch")
    if sha256(five_result_path) != frozen["five_root_result_sha256"]:
        raise ValueError("five-root result hash mismatch")
    five_plan, _ = load_five_root_plan(five_plan_path)
    five_result = json.loads(five_result_path.read_text(encoding="utf-8"))
    if five_result["status"] != "FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE":
        raise ValueError("unexpected predecessor terminal")
    candidates = plan.get("candidate_roots", [])
    if len(candidates) != 3 or len({row["station"] for row in candidates}) != 3:
        raise ValueError("exactly three distinct frozen candidates required")
    if any(row["code_capability_status"] != "UNKNOWN_NOT_ACCESSED" for row in candidates):
        raise ValueError("candidate capability must remain unknown")
    boundary = plan["selection_boundary"]
    if (boundary["target_identifier"] is not None or boundary["target_date"] is not None
            or boundary["target_orbit_or_radius_constraint"] is not False
            or boundary["candidate_artifact_access"] is not False):
        raise ValueError("target/access boundary violated")
    return plan, hashlib.sha256(raw).hexdigest(), five_plan, five_result


def fit_response(state, stations, design, five_plan):
    """Reproduce the frozen five-root local response and retain its gain."""
    tags, n = design["tags"], len(stations)
    count, nrate = design["count"], design["nrate"]
    clock_end = 11+2*n
    scale = np.r_[[1e7]*3, [1e3]*3, [1.]*3, 1e5, 10.,
                  np.tile([1000., 1.], n), np.full(3*n, 1e5)]
    point = np.r_[state, np.zeros(5*n)]

    def model(z):
        physical = z*scale
        pair = predict(physical[:11], tags,
                       stations+physical[clock_end:].reshape(n, 3),
                       physical[11:clock_end].reshape(n, 2))
        code = pair["code_m"].ravel()
        return np.r_[code, design["difference"]@code, physical[11:]]

    jacobian = central_jacobian(model, point/scale)/scale
    covariance = design["covariance"]
    chol = cholesky_covariance(covariance, len(covariance))
    scaled = solve_triangular(chol, jacobian*scale, lower=True)
    u, singular, vh = np.linalg.svd(scaled, full_matrices=False)
    threshold = five_plan["frozen_clauses"]["maximum_scaled_condition"]
    if len(singular) != len(scale) or singular[-1] <= singular[0]/threshold:
        raise ValueError("frozen predecessor case lost full local rank")
    inverse = scale[:, None]*((vh.T/singular)@u.T)
    gain = inverse@solve_triangular(chol, np.eye(len(chol)), lower=True)
    covariance_parameter = inverse@inverse.T
    bounds = five_plan["conditional_measurement_design"]
    systematic = np.zeros((len(covariance), 2*n))
    for root in range(n):
        systematic[root:count:n, 2*root] = bounds["persistent_code_bias_box_m_per_root"]
        systematic[count+root:count+nrate:n, 2*root+1] = bounds["persistent_interval_rate_bias_box_m_s_per_root"]
    return {"scale": scale, "covariance": covariance_parameter,
            "systematic_parameter_modes": gain@systematic,
            "scaled_condition": float(singular[0]/singular[-1])}


def heldout_code_metric(state, heldout_station, seconds, response, topology_plan):
    state_scale = response["scale"][:11]
    state_gradient = central_jacobian(
        lambda z: predict(z*state_scale, [seconds], [heldout_station], [[0.0, 0.0]])["code_m"].ravel(),
        state/state_scale,
    )[0]/state_scale
    parameter_gradient = np.zeros(len(response["scale"]))
    parameter_gradient[:11] = state_gradient
    fit_variance = float(parameter_gradient@response["covariance"]@parameter_gradient)
    fit_affine_modes = parameter_gradient@response["systematic_parameter_modes"]

    heldout = topology_plan["heldout_prediction"]
    clock_scale = np.array([1000.0, 1.0])
    clock_gradient = central_jacobian(
        lambda z: predict(state, [seconds], [heldout_station], [z*clock_scale])["code_m"].ravel(),
        np.zeros(2),
    )[0]/clock_scale
    station_gradient = central_jacobian(
        lambda station: predict(state, [seconds], [station], [[0.0, 0.0]])["code_m"].ravel(),
        np.asarray(heldout_station), step=1.0,
    )[0]
    direct_variance = (
        heldout["independent_code_sigma_m"]**2
        + (clock_gradient[0]*heldout["independent_receiver_clock_offset_sigma_m"])**2
        + (clock_gradient[1]*heldout["independent_receiver_clock_drift_sigma_m_s"])**2
        + heldout["independent_ground_coordinate_sigma_m"]**2*np.dot(station_gradient, station_gradient)
    )
    sigma = float(np.sqrt(max(0.0, fit_variance+direct_variance)))
    gaussian = float(norm.ppf((1+heldout["gaussian_two_sided_probability"])/2)*sigma)
    affine = float(np.sum(np.abs(fit_affine_modes)))
    slack = heldout["absolute_range_equivalent_limit_m"]-gaussian-affine
    return {"receive_tag_s": seconds, "conditional_gaussian_halfwidth95_m": gaussian,
            "fit_root_affine_box_bound_m": affine,
            "remaining_physical_affine_slack_m": float(slack),
            "positive_physical_slack": bool(slack > 0)}


def summary(values):
    array = np.asarray(values, float)
    return {"minimum": float(array.min()), "median": float(np.median(array)),
            "maximum": float(array.max())} if len(array) else None


def run(plan_path: Path, source_commit: str):
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("exact lowercase source commit required")
    plan, plan_hash, five_plan, five_result = load_plan(plan_path)
    fit_stations = np.asarray([row["ecef_m"] for row in five_plan["fit_roots"]], float)
    directions = fibonacci_directions(five_plan["synthetic_family"]["fibonacci_direction_count"])
    motions = {row["name"]: row for row in five_plan["synthetic_family"]["motion_templates"]}
    design = measurement_design(five_plan)
    predecessor = {(row["direction_index"], row["radius_m"], row["motion"]): row
                   for row in five_result["cases"]}
    responses = {}
    for key, old in predecessor.items():
        direction_index, radius, motion_name = key
        state = state_for(directions[direction_index], radius, motions[motion_name])
        responses[key] = (state, fit_response(state, fit_stations, design, five_plan))
        if abs(responses[key][1]["scaled_condition"]
               - old["code_and_interval_phase"]["scaled_condition"]) > 1e-6:
            raise ValueError("predecessor geometry reproduction mismatch")

    candidates = []
    for candidate in plan["candidate_roots"]:
        station = np.asarray(candidate["ecef_m"], float)
        rows = []
        for key, (state, response) in responses.items():
            elevation = minimum_elevation_deg(
                state, plan["heldout_prediction"]["receive_tags_s"], [station])
            if elevation < plan["heldout_prediction"]["minimum_elevation_deg"]:
                continue
            endpoints = [heldout_code_metric(state, station, seconds, response, plan)
                         for seconds in plan["heldout_prediction"]["receive_tags_s"]]
            rows.append({"direction_index": key[0], "radius_m": key[1], "motion": key[2],
                         "minimum_heldout_elevation_deg": elevation, "endpoints": endpoints,
                         "all_endpoints_positive_physical_slack": all(row["positive_physical_slack"] for row in endpoints)})
        all_slack = [endpoint["remaining_physical_affine_slack_m"]
                     for row in rows for endpoint in row["endpoints"]]
        positive_cases = sum(row["all_endpoints_positive_physical_slack"] for row in rows)
        candidates.append({"station": candidate["station"],
                           "capability_status": candidate["code_capability_status"],
                           "visible_predecessor_cases": len(rows),
                           "cases_with_positive_slack_at_both_endpoints": positive_cases,
                           "physical_affine_slack_m": summary(all_slack),
                           "cases": rows})
    ranked = sorted(candidates, key=lambda row: (
        row["cases_with_positive_slack_at_both_endpoints"],
        row["visible_predecessor_cases"],
        row["physical_affine_slack_m"]["median"] if row["physical_affine_slack_m"] else -np.inf,
    ), reverse=True)
    available = bool(ranked and ranked[0]["cases_with_positive_slack_at_both_endpoints"])
    status = ("HELDOUT_CODE_TOPOLOGY_CONDITIONALLY_AVAILABLE" if available
              else "HELDOUT_CODE_TOPOLOGY_NOT_SUPPORTED")
    result = {
        "schema": "s2-heldout-code-topology-result-v1", "status": status,
        "scope": plan["scope"],
        "freeze": {"plan_sha256": plan_hash, "source_commit": source_commit,
                   "predecessor_plan_sha256": plan["frozen_inputs"]["five_root_plan_sha256"],
                   "predecessor_result_sha256": plan["frozen_inputs"]["five_root_result_sha256"]},
        "input_boundaries": {"target_or_orbit_used": False, "observation_values_read": False,
                             "candidate_artifacts_accessed": False, "new_network_access": False},
        "candidate_ranking": [row["station"] for row in ranked],
        "candidates": ranked,
        "clauses": {
            "FIVE_ROOT_LOCAL_IDENTIFIABILITY": "SATISFIED",
            "FIVE_ROOT_UNIFORM_10KM_MARGIN": "NOT_SATISFIED",
            "SIXTH_ROOT_GEOMETRIC_TOPOLOGY": "CONDITIONALLY_AVAILABLE" if available else "NOT_SUPPORTED",
            "SIXTH_ROOT_CODE_COORDINATE": "UNRESOLVED_NOT_ACCESSED",
            "TOTAL_PHYSICAL_ERROR_ENVELOPE": "UNRESOLVED",
        },
        "interpretation": {
            "ranking_is_receiver_admission": False,
            "primary_or_target_selected": False,
            "s3_authorized": False,
            "next_minimum_step": "Freeze and execute one distinct header/structure-only code-coordinate qualification for the top ground-only candidate, without target values; stop on any unresolved transform or coverage clause.",
        },
        "physical_envelope_ledger": plan["physical_envelope_ledger"],
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "sources_sha256": {name: sha256(ROOT/name) for name in [
            "research/kinematic/heldout_code_topology.py",
            "research/kinematic/five_root_feasibility.py",
            "research/kinematic/receiver_time.py"]},
    }
    return strict_json(result)


def main():
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
    print(json.dumps({"status": result["status"], "ranking": result["candidate_ranking"],
                      "candidates": [{k: row[k] for k in ("station", "visible_predecessor_cases",
                          "cases_with_positive_slack_at_both_endpoints", "physical_affine_slack_m")}
                          for row in result["candidates"]], "clauses": result["clauses"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
