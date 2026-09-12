"""Offline five-root local-information audit; no real target or observation data."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform

import numpy as np
import scipy
from scipy.linalg import block_diag, solve_triangular
from scipy.stats import chi2

from .phase_rates import interval_matrix
from .receiver_time import central_jacobian, cholesky_covariance, predict
from .synthetic import native

ROOT = Path(__file__).resolve().parents[2]
TERMINAL = "FIVE_ROOT_PROSPECTIVE_VERTICAL_INCOMPLETE"


def strict_json(value):
    text = json.dumps(native(value), sort_keys=True, allow_nan=False)
    return json.loads(text)


def load_plan(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    plan = json.loads(raw)
    if plan.get("schema") != "s2-five-root-local-feasibility-plan-v1":
        raise ValueError("unexpected plan schema")
    roots = plan.get("fit_roots", [])
    if len(roots) != 5 or len({row["station"] for row in roots}) != 5:
        raise ValueError("exactly five distinct fit roots required")
    excluded = plan.get("target_state_exclusion", {})
    if (excluded.get("target_identifier") is not None
            or excluded.get("target_date") is not None
            or excluded.get("target_orbit_or_radius_constraint") is not False
            or excluded.get("real_target_measurements") is not False):
        raise ValueError("target-state exclusion violated")
    stations = np.asarray([row["ecef_m"] for row in roots], float)
    if stations.shape != (5, 3) or not np.isfinite(stations).all():
        raise ValueError("five finite terrestrial coordinates required")
    if np.min([np.linalg.norm(a-b) for i, a in enumerate(stations)
               for b in stations[i+1:]]) < 1000:
        raise ValueError("distinct hardware roots require distinct coordinates")
    return plan, hashlib.sha256(raw).hexdigest()


def fibonacci_directions(count: int) -> np.ndarray:
    if not isinstance(count, int) or count < 4:
        raise ValueError("at least four deterministic directions required")
    index = np.arange(count, dtype=float)
    z = 1.0 - 2.0*(index+0.5)/count
    radius = np.sqrt(1.0-z*z)
    longitude = 2.0*np.pi*index/((1.0+np.sqrt(5.0))/2.0)
    return np.column_stack([radius*np.cos(longitude), radius*np.sin(longitude), z])


def tangent_basis(direction: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    axis = np.array([0.0, 0.0, 1.0])
    first = np.cross(axis, direction)
    if np.linalg.norm(first) < 0.1:
        first = np.cross(np.array([1.0, 0.0, 0.0]), direction)
    first /= np.linalg.norm(first)
    second = np.cross(direction, first)
    second /= np.linalg.norm(second)
    return first, second


def state_for(direction, radius_m, motion):
    direction = np.asarray(direction, float)
    first, second = tangent_basis(direction)
    velocity = (motion["tangent_1_speed_m_s"]*first
                + motion["tangent_2_speed_m_s"]*second)
    acceleration = -motion["inward_acceleration_m_s2"]*direction
    return np.r_[radius_m*direction, velocity, acceleration, 0.0, 0.0]


def minimum_elevation_deg(state, tags, stations):
    state, tags, stations = np.asarray(state), np.asarray(tags), np.asarray(stations)
    positions = (state[:3]+tags[:, None]*state[3:6]
                 + 0.5*tags[:, None]**2*state[6:9])
    delta = positions[:, None, :]-stations[None, :, :]
    unit = delta/np.linalg.norm(delta, axis=2)[..., None]
    up = stations/np.linalg.norm(stations, axis=1)[:, None]
    return float(np.degrees(np.arcsin(np.clip(np.sum(unit*up[None, :, :], axis=2), -1, 1))).min())


def measurement_design(plan):
    design = plan["conditional_measurement_design"]
    tags = np.asarray(plan["synthetic_family"]["endpoint_tags_s"], float)
    n, count = 5, len(tags)*5
    difference = interval_matrix(tags, n)
    raw = block_diag(
        design["endpoint_code_sigma_m"]**2*np.eye(count),
        design["endpoint_phase_path_sigma_m"]**2*np.eye(count),
        np.kron(np.eye(n), np.diag([
            design["receiver_clock_offset_sigma_m"]**2,
            design["receiver_clock_drift_sigma_m_s"]**2])),
        design["ground_coordinate_sigma_m"]**2*np.eye(3*n),
    )
    cross = (design["code_phase_correlation"]
             * design["endpoint_code_sigma_m"]
             * design["endpoint_phase_path_sigma_m"])
    raw[:count, count:2*count] = cross*np.eye(count)
    raw[count:2*count, :count] = cross*np.eye(count)
    modes = np.zeros((len(raw), 2*n))
    for root in range(n):
        modes[root:count:n, 2*root] = 5.0
        modes[2*count+2*root, 2*root] = 4.0
        modes[2*count+2*n+3*root, 2*root] = 0.2
        modes[root:count:n, 2*root+1] = tags*0.01
        modes[count+root:2*count:n, 2*root+1] = tags*0.01
        modes[2*count+2*root+1, 2*root+1] = 0.008
    raw += modes@modes.T
    transform = block_diag(np.eye(count), difference, np.eye(5*n))
    covariance = transform@raw@transform.T
    covariance = (covariance+covariance.T)/2
    nrate = len(difference)
    code_indices = np.r_[np.arange(count), np.arange(count+nrate, len(covariance))]
    return {"tags": tags, "difference": difference, "raw_covariance": raw,
            "covariance": covariance, "count": count, "nrate": nrate,
            "code_indices": code_indices}


def local_geometry(state, stations, design, plan, *, include_phase):
    tags, n = design["tags"], len(stations)
    count, nrate = design["count"], design["nrate"]
    clock_end = 11+2*n
    scale = np.r_[[1e7]*3, [1e3]*3, [1.]*3, 1e5, 10.,
                  np.tile([1000., 1.], n), np.full(3*n, 1e5)]
    point = np.r_[state, np.zeros(2*n+3*n)]

    def model(z):
        physical = z*scale
        pair = predict(physical[:11], tags,
                       stations+physical[clock_end:].reshape(n, 3),
                       physical[11:clock_end].reshape(n, 2))
        code = pair["code_m"].ravel()
        return np.r_[code, design["difference"]@code, physical[11:]]

    jacobian = central_jacobian(model, point/scale)/scale
    covariance = design["covariance"]
    indices = np.arange(len(covariance)) if include_phase else design["code_indices"]
    chol = cholesky_covariance(covariance[np.ix_(indices, indices)], len(indices))
    scaled = solve_triangular(chol, jacobian[indices]*scale, lower=True)
    u, singular, vh = np.linalg.svd(scaled, full_matrices=False)
    threshold = plan["frozen_clauses"]["maximum_scaled_condition"]
    full_rank = len(singular) == len(scale) and singular[-1] > singular[0]/threshold
    if not full_rank:
        return {"full_rank": False, "rank": int(np.sum(singular > singular[0]/threshold)),
                "parameter_count": len(scale),
                "scaled_condition": None if singular[-1] == 0 else float(singular[0]/singular[-1])}
    inverse = scale[:, None]*((vh.T/singular)@u.T)
    gain = inverse@solve_triangular(chol, np.eye(len(chol)), lower=True)
    parameter_covariance = inverse@inverse.T
    systematic = np.zeros((len(indices), 2*n))
    mapped_index = {raw: mapped for mapped, raw in enumerate(indices.tolist())}
    bounds = plan["conditional_measurement_design"]
    for root in range(n):
        for raw in range(root, count, n):
            if raw in mapped_index:
                systematic[mapped_index[raw], 2*root] = bounds["persistent_code_bias_box_m_per_root"]
        for raw in range(count+root, count+nrate, n):
            if raw in mapped_index:
                systematic[mapped_index[raw], 2*root+1] = bounds["persistent_interval_rate_bias_box_m_s_per_root"]
    response = gain@systematic
    metrics = {}
    for seconds in bounds["future_position_offsets_s"]:
        mapping = np.zeros((3, len(scale)))
        mapping[:, :3] = np.eye(3)
        mapping[:, 3:6] = seconds*np.eye(3)
        mapping[:, 6:9] = 0.5*seconds**2*np.eye(3)
        covariance_position = mapping@parameter_covariance@mapping.T
        gaussian = float(np.sqrt(chi2.ppf(0.95, 3)*max(0.0, np.linalg.eigvalsh(covariance_position)[-1])))
        affine = float(np.linalg.norm(mapping@response, axis=0).sum())
        metrics[f"t_plus_{int(seconds)}_s"] = {
            "local_gaussian_position_radius95_m": gaussian,
            "affine_box_position_norm_bound_m": affine,
            "conditional_local_position_envelope_m": gaussian+affine,
        }
    return {"full_rank": True, "rank": len(scale), "parameter_count": len(scale),
            "scaled_condition": float(singular[0]/singular[-1]), "position": metrics}


def summarize(values):
    array = np.asarray(values, float)
    return {"minimum": float(array.min()), "median": float(np.median(array)), "maximum": float(array.max())}


def run(plan_path: Path, source_commit: str):
    if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
        raise ValueError("exact lowercase source commit required")
    plan, plan_hash = load_plan(plan_path)
    stations = np.asarray([row["ecef_m"] for row in plan["fit_roots"]], float)
    design = measurement_design(plan)
    family = plan["synthetic_family"]
    cases, visible_count, rank_failures = [], 0, 0
    for direction_index, direction in enumerate(fibonacci_directions(family["fibonacci_direction_count"])):
        for radius in family["geocentric_radii_m"]:
            for motion in family["motion_templates"]:
                state = state_for(direction, radius, motion)
                elevation = minimum_elevation_deg(state, design["tags"], stations)
                if elevation < family["minimum_joint_elevation_deg"]:
                    continue
                visible_count += 1
                code = local_geometry(state, stations, design, plan, include_phase=False)
                phase = local_geometry(state, stations, design, plan, include_phase=True)
                rank_failures += int(not phase["full_rank"])
                cases.append({"direction_index": direction_index, "radius_m": radius,
                              "motion": motion["name"], "minimum_joint_elevation_deg": elevation,
                              "code_only": code, "code_and_interval_phase": phase})
    clauses = plan["frozen_clauses"]
    enough = visible_count >= clauses["minimum_joint_visible_synthetic_cases"]
    full_rank = enough and rank_failures == 0
    envelopes = [row["code_and_interval_phase"]["position"][key]["conditional_local_position_envelope_m"]
                 for row in cases if row["code_and_interval_phase"]["full_rank"]
                 for key in ("t_plus_0_s", "t_plus_60_s")]
    local_margin = (full_rank and bool(envelopes)
                    and max(envelopes) <= clauses["maximum_conditional_local_position_envelope_m"])
    metric_summary = {}
    for variant in ("code_only", "code_and_interval_phase"):
        admitted = [row[variant] for row in cases if row[variant]["full_rank"]]
        metric_summary[variant] = {
            "full_rank_cases": len(admitted),
            "scaled_condition": summarize([row["scaled_condition"] for row in admitted]) if admitted else None,
            "t_plus_0_s_envelope_m": summarize([row["position"]["t_plus_0_s"]["conditional_local_position_envelope_m"] for row in admitted]) if admitted else None,
            "t_plus_60_s_envelope_m": summarize([row["position"]["t_plus_60_s"]["conditional_local_position_envelope_m"] for row in admitted]) if admitted else None,
        }
    result = {
        "schema": "s2-five-root-local-feasibility-result-v1",
        "status": TERMINAL,
        "scope": plan["scope"],
        "freeze": {"plan_sha256": plan_hash, "source_commit": source_commit},
        "input_boundaries": {
            "fit_root_count": 5,
            "independent_heldout_root_count": 0,
            "target_state_or_orbit_used": False,
            "real_observation_values_read": False,
            "new_network_access": False,
            "station_coordinate_source_sha256": plan["station_coordinate_provenance"]["artifact_sha256"],
        },
        "synthetic_case_accounting": {
            "generated": family["fibonacci_direction_count"]*len(family["geocentric_radii_m"])*len(family["motion_templates"]),
            "joint_visible": visible_count,
            "rejected_by_joint_visibility": family["fibonacci_direction_count"]*len(family["geocentric_radii_m"])*len(family["motion_templates"])-visible_count,
            "phase_model_rank_failures": rank_failures,
        },
        "metric_summary": metric_summary,
        "clauses": {
            "LOCAL_FIT_IDENTIFIABILITY": "SATISFIED" if full_rank else "NOT_SATISFIED",
            "CONDITIONAL_LOCAL_MARGIN": "SATISFIED" if local_margin else "NOT_SATISFIED",
            "INDEPENDENT_HELDOUT_ROOT": "UNSATISFIED",
            "TOTAL_PHYSICAL_ERROR_ENVELOPE": "UNRESOLVED",
        },
        "interpretation": {
            "forward_vertical_complete": False,
            "minimum_missing_topology": "One distinct, predeclared and independently qualified code-coordinate root reserved exclusively for held-out prediction.",
            "remaining_physics": "Receiver, propagation, phase-continuity, model-truncation and nonlinear/global-branch envelopes remain unqualified.",
            "claim": "Synthetic local-design feasibility only; no real-satellite or S3 claim.",
        },
        "cases": cases,
        "environment": {"python": platform.python_version(), "numpy": np.__version__, "scipy": scipy.__version__},
        "sources_sha256": {
            name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ["research/kinematic/five_root_feasibility.py",
                         "research/kinematic/receiver_time.py",
                         "research/kinematic/phase_rates.py"]
        },
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
    print(json.dumps({"status": result["status"], "case_accounting": result["synthetic_case_accounting"],
                      "clauses": result["clauses"], "metrics": result["metric_summary"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
