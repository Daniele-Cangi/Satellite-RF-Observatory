"""One-off offline audit of a prospective target/reference differential observable."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np

from . import calibration_transfer
from .reference_target_transfer_audit import load_strict_json_bytes


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PLAN_SHA256 = "c9049569df361b3cdc9ae4d868c44d3147de7281df997db95048f40d455ba261"
EXPECTED_TERMS = [
    "future target-direction antenna phase-center variation",
    "future target-direction multipath",
    "unflagged sub-threshold cycle slips",
    "future atmosphere outside the selected reference rays",
    "broadcast-reference orbit and clock error transfer",
    "reference-to-target receiver correlation",
]
EXPECTED_INPUTS = {
    "research/kinematic/results/s2_reference_target_transfer_audit_v3.json": (
        "e209a9d00b70e360be6ba1330574a830ca331a5e2b3690c33d8b53c96f04170b"
    ),
    "research/kinematic/results/calibration_transfer_study_v1.json": (
        "526db8c0d03861879753769037491e2573e0fe84e3082980ee8d280e2f44935b"
    ),
}
TERMINALS = {
    "DIFFERENTIAL_OBSERVABLE_ENVELOPE_CLOSED",
    "DIFFERENTIAL_OBSERVABLE_HAS_ABSORBING_UNRESOLVED_TERM",
    "DIFFERENTIAL_OBSERVABLE_AUDIT_EXECUTION_INVALID",
}


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_plan(plan: dict, plan_bytes: bytes) -> None:
    if sha256_bytes(plan_bytes) != EXPECTED_PLAN_SHA256:
        raise ValueError("complete differential-audit plan hash mismatch")
    if plan != load_strict_json_bytes(plan_bytes):
        raise ValueError("supplied plan object differs from frozen bytes")
    if plan.get("schema") != "s2-differential-observable-audit-plan-v1":
        raise ValueError("unexpected differential-audit plan")
    inputs = {
        row.get("path"): row.get("sha256") for row in plan.get("frozen_inputs", [])
    }
    if inputs != EXPECTED_INPUTS:
        raise ValueError("frozen input set differs")
    if [row.get("term") for row in plan.get("terms", [])] != EXPECTED_TERMS:
        raise ValueError("causal term order or identity differs")
    if set(plan.get("outcomes", [])) != TERMINALS:
        raise ValueError("terminal set differs")
    topology = plan.get("declared_topology", {})
    if topology.get("target_measurements_available") is not False:
        raise ValueError("target measurements entered the audit")
    if topology.get("target_identity_selected") is not False:
        raise ValueError("target identity entered the audit")
    if topology.get("target_orbit_available") is not False:
        raise ValueError("target orbit entered the audit")
    for term in plan["terms"]:
        if not term.get("components"):
            raise ValueError("term has no causal components:" + term["term"])
        for component in term["components"]:
            state = component.get("classification")
            if state == "UNRESOLVED":
                if not component.get("missing_quantity"):
                    raise ValueError("unresolved component lacks missing quantity")
                if component.get("can_absorb_any_finite_margin") is not True:
                    raise ValueError("unresolved component was silently bounded")
            elif state == "MODELED":
                bound = component.get("finite_bound")
                if not isinstance(bound, (int, float)) or not math.isfinite(bound):
                    raise ValueError("modeled component lacks a finite bound")
                if bound != 0.0 or not component.get("transform_response", "").startswith(
                    "EXACTLY_CANCELLED"
                ):
                    raise ValueError("this audit admits only proved exact invariants")
            elif state == "OBSERVABLE":
                if not component.get("required_witness"):
                    raise ValueError("observable component lacks a same-path witness")
            else:
                raise ValueError("unknown epistemic state")
    forbidden = set(plan.get("forbidden_actions", []))
    if {
        "network or source access",
        "target identity, target state or target orbit access",
        "assigning zero to an unresolved contribution",
        "authorizing S3 from a partial cancellation",
    } - forbidden:
        raise ValueError("causal boundary weakened")


def admit_git_freeze(
    source_commit: str,
    frozen_files: list[tuple[Path, bytes]],
) -> None:
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
    ).strip():
        raise ValueError("working tree must be clean before audit execution")
    actual = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if actual != source_commit:
        raise ValueError("source commit differs from HEAD")
    for path, frozen_bytes in frozen_files:
        relative = path.resolve().relative_to(ROOT).as_posix()
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT
        )
        if committed != frozen_bytes:
            raise ValueError("frozen file differs from committed bytes:" + relative)


def load_frozen_input(relative: str, expected_sha256: str) -> tuple[dict, str]:
    content = (ROOT / relative).read_bytes()
    digest = sha256_bytes(content)
    if digest != expected_sha256:
        raise ValueError("frozen input hash mismatch:" + relative)
    return load_strict_json_bytes(content), digest


def validate_input_receipts(receipts: dict[str, dict]) -> None:
    transfer = receipts[
        "research/kinematic/results/s2_reference_target_transfer_audit_v3.json"
    ]
    if transfer.get("status") != (
        "FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT"
    ):
        raise ValueError("upstream causal outcome differs")
    flags = transfer.get("inputs", {})
    for key in (
        "source_or_network_access",
        "new_numeric_measurements",
        "target_selected",
        "target_state_or_orbit_accessed",
    ):
        if flags.get(key) is not False:
            raise ValueError("upstream causal boundary differs:" + key)
    algebra = receipts[
        "research/kinematic/results/calibration_transfer_study_v1.json"
    ]
    if algebra.get("schema") != "calibration-transfer-synthetic-study-v1":
        raise ValueError("unexpected algebra witness")
    if algebra.get("real_rf_qualified") is not False:
        raise ValueError("synthetic algebra was relabelled as RF qualification")
    if algebra.get("physical_amplitudes_established") is not False:
        raise ValueError("synthetic algebra was relabelled as a physical amplitude")
    expected_module = sha256_bytes(Path(calibration_transfer.__file__).read_bytes())
    if algebra.get("sources_sha256", {}).get(
        "research/kinematic/calibration_transfer.py"
    ) != expected_module:
        raise ValueError("calibration-transfer implementation differs from witness")


def normalized_algebra_witness() -> dict:
    """Prove cancellation only inside the declared common affine subspace."""
    tags = np.repeat(np.arange(-150.0, 151.0, 30.0), 4)
    reference_design = np.column_stack([np.ones(len(tags)), tags])
    target_design = np.eye(2)
    op = calibration_transfer.operators(
        reference_design,
        target_design,
        np.eye(len(tags)),
    )
    basis = np.eye(2)
    common = op["joint_to_target"] @ np.vstack(
        [reference_design @ basis, target_design @ basis]
    )
    reference_only = op["joint_to_target"] @ np.vstack(
        [reference_design @ basis, np.zeros((2, 2))]
    )
    target_only = op["joint_to_target"] @ np.vstack(
        [np.zeros((len(tags), 2)), target_design @ basis]
    )
    if np.max(np.abs(common)) > 1e-12:
        raise ValueError("declared common affine invariant did not cancel")
    if not np.allclose(reference_only, -np.eye(2), atol=1e-12):
        raise ValueError("reference-only normalized mode response differs")
    if not np.allclose(target_only, np.eye(2), atol=1e-12):
        raise ValueError("target-only normalized mode response differs")
    return {
        "coordinate": "normalized algebraic basis; no physical amplitude or unit",
        "common_affine_response": common.tolist(),
        "common_affine_max_abs": float(np.max(np.abs(common))),
        "reference_only_response": reference_only.tolist(),
        "target_only_response": target_only.tolist(),
        "interpretation": (
            "Only the identical A/B affine receiver mode cancels. Reference-only "
            "and target-only modes remain fully visible and require physical bounds."
        ),
    }


def assess_terms(plan: dict) -> tuple[list[dict], list[str]]:
    assessments = []
    absorbing = []
    for term in plan["terms"]:
        component_results = []
        for component in term["components"]:
            state = component["classification"]
            currently_closed = state == "MODELED" or (
                state == "OBSERVABLE"
                and component.get("availability") == "CURRENT_EVIDENCE"
                and component.get("detectability_rule_frozen") is True
            )
            row = dict(component)
            row["currently_closes_component"] = currently_closed
            component_results.append(row)
            if state == "UNRESOLVED" and component["can_absorb_any_finite_margin"]:
                absorbing.append(term["term"] + " :: " + component["component"])
        term_closed = all(row["currently_closes_component"] for row in component_results)
        assessments.append(
            {
                "term": term["term"],
                "state": "CLOSED" if term_closed else "UNRESOLVED",
                "components": component_results,
            }
        )
    return assessments, absorbing


def run(plan_path: Path, source_commit: str) -> dict:
    if not source_commit:
        raise ValueError("source commit is required")
    plan_bytes = plan_path.read_bytes()
    implementation_path = Path(__file__)
    implementation_bytes = implementation_path.read_bytes()
    transfer_module_path = Path(calibration_transfer.__file__)
    transfer_module_bytes = transfer_module_path.read_bytes()
    plan = load_strict_json_bytes(plan_bytes)
    validate_plan(plan, plan_bytes)
    admit_git_freeze(
        source_commit,
        [
            (plan_path, plan_bytes),
            (implementation_path, implementation_bytes),
            (transfer_module_path, transfer_module_bytes),
        ],
    )
    receipts = {}
    input_hashes = {}
    for relative, expected in EXPECTED_INPUTS.items():
        receipts[relative], input_hashes[relative] = load_frozen_input(relative, expected)
    validate_input_receipts(receipts)
    witness = normalized_algebra_witness()
    assessments, absorbing = assess_terms(plan)
    all_closed = all(row["state"] == "CLOSED" for row in assessments)
    status = (
        "DIFFERENTIAL_OBSERVABLE_ENVELOPE_CLOSED"
        if all_closed and not absorbing
        else "DIFFERENTIAL_OBSERVABLE_HAS_ABSORBING_UNRESOLVED_TERM"
    )
    result = {
        "schema": "s2-differential-observable-audit-result-v1",
        "audit_id": plan["audit_id"],
        "status": status,
        "scope": plan["scope"],
        "inputs": {
            "source_commit": source_commit,
            "plan_sha256": sha256_bytes(plan_bytes),
            "implementation_sha256": sha256_bytes(implementation_bytes),
            "calibration_transfer_sha256": sha256_bytes(transfer_module_bytes),
            "receipts_sha256": input_hashes,
            "source_or_network_access": False,
            "new_observation_or_navigation_decoding": False,
            "target_selected": False,
            "target_state_or_orbit_accessed": False,
        },
        "declared_topology": plan["declared_topology"],
        "normalized_algebra_witness": witness,
        "term_assessments": assessments,
        "absorbing_unresolved_components": absorbing,
        "composition": {
            "performed": False,
            "total_future_target_physical_envelope": None,
            "reason": (
                "At least one unbounded differential component can absorb every "
                "finite prospective margin. Exact common-mode cancellations do not "
                "bound the remaining components."
            ),
        },
        "claim_boundary": {
            "authorized": [
                "the identical same-station affine receiver clock mode cancels in the declared linear calibration subspace",
                "the ideal first-order same-ray dual-frequency ionosphere term cancels under its explicit assumptions",
                "the prospective differential topology exposes same-path continuity witnesses but has not observed them",
            ],
            "not_authorized": [
                "a physical amplitude for any normalized algebraic response",
                "zero antenna, multipath, missed-slip, media, reference-product or differential receiver error",
                "a finite total future-target envelope",
                "target selection, a primary or S3 acquisition",
            ],
            "s3_authorized": False,
        },
        "minimum_next_evidence": [
            "direction-resolved antenna/site response or a conservative directional bound",
            "target-side continuity witness with a frozen missed-slip sensitivity",
            "neutral and higher-order media uncertainty in the target coordinate",
            "non-target reference-product covariance projected through calibration and the inverse fit",
            "differential receiver hardware uncertainty and reference-target cross covariance",
        ],
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
    print(
        json.dumps(
            {
                "status": result["status"],
                "unresolved_term_count": sum(
                    row["state"] == "UNRESOLVED"
                    for row in result["term_assessments"]
                ),
                "absorbing_component_count": len(
                    result["absorbing_unresolved_components"]
                ),
                "s3_authorized": result["claim_boundary"]["s3_authorized"],
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
