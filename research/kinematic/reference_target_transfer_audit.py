"""Audit what the frozen DOY240 reference receipt can transfer to a future target."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
EXPECTED_PLAN_SHA256 = "afcd036c429f8ea45f293d233fa0d6f8be5f50bbc01fe036ab10b9784118ad01"
TERMINALS = {
    "FUTURE_TARGET_ENVELOPE_IDENTIFIED",
    "FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT",
    "REFERENCE_TARGET_TRANSFER_AUDIT_EXECUTION_INVALID",
}
EXPECTED_TERMS = [
    "future target-direction antenna phase-center variation",
    "future target-direction multipath",
    "unflagged sub-threshold cycle slips",
    "future atmosphere outside the selected reference rays",
    "broadcast-reference orbit and clock error transfer",
    "reference-to-target receiver correlation",
]


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON constant:" + value)


def _finite_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite JSON number:" + value)
    return parsed


def load_strict_json_bytes(content: bytes) -> dict:
    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key:" + key)
            result[key] = value
        return result

    value = json.loads(
        content.decode("utf-8"),
        parse_constant=_reject_constant,
        parse_float=_finite_float,
        object_pairs_hook=unique_object,
    )
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def load_strict_json(path: Path) -> dict:
    return load_strict_json_bytes(path.read_bytes())


def admit_git_freeze(
    plan_path: Path,
    source_commit: str,
    plan_bytes: bytes,
    implementation_bytes: bytes,
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
    for path, frozen_bytes in (
        (plan_path, plan_bytes),
        (Path(__file__), implementation_bytes),
    ):
        relative = path.resolve().relative_to(ROOT).as_posix()
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{relative}"], cwd=ROOT
        )
        if committed != frozen_bytes:
            raise ValueError("frozen file differs from committed bytes:" + relative)


def validate_plan(plan: dict, plan_bytes: bytes) -> None:
    if hashlib.sha256(plan_bytes).hexdigest() != EXPECTED_PLAN_SHA256:
        raise ValueError("complete frozen plan hash mismatch")
    if plan != load_strict_json_bytes(plan_bytes):
        raise ValueError("supplied plan object differs from frozen plan bytes")
    if plan.get("schema") != "s2-reference-to-target-transfer-audit-plan-v1":
        raise ValueError("unexpected transfer-audit plan")
    if plan.get("audit_id") != "S2_REFERENCE_TO_TARGET_TRANSFER_AUDIT_DOY240":
        raise ValueError("audit identity differs")
    frozen = plan.get("frozen_input", {})
    expected = {
        "path": "research/kinematic/results/s2_five_root_reference_envelope_2026240_v1.json",
        "sha256": "3a0f2f0225feded686787484fcc3809062371a0a0358d6018b062e6c92e1dc2f",
        "required_status": "FIVE_ROOT_REFERENCE_RESIDUAL_ENVELOPE_QUALIFIED",
        "required_target_envelope_state": "UNRESOLVED",
    }
    if frozen != expected:
        raise ValueError("frozen input differs")
    terms = plan.get("terms", [])
    if [row.get("term") for row in terms] != EXPECTED_TERMS:
        raise ValueError("unresolved-term order or identity differs")
    for row in terms:
        if not row.get("receipt_evidence"):
            raise ValueError("receipt evidence missing:" + row["term"])
        if not row.get("required_for_transfer") or not row.get("missing_from_receipt"):
            raise ValueError("transfer topology incomplete:" + row["term"])
    if set(plan.get("outcomes", [])) != TERMINALS:
        raise ValueError("terminal set differs")
    forbidden = set(plan.get("forbidden_evidence_or_actions", []))
    required_forbidden = {
        "network or source access",
        "target identity, target state or target orbit",
        "treating an unresolved contribution as zero",
        "combining quantities with incompatible units",
    }
    if not required_forbidden <= forbidden:
        raise ValueError("causal boundary weakened")


def validate_receipt_fields(plan: dict, receipt: dict) -> None:
    frozen = plan["frozen_input"]
    if receipt.get("status") != frozen["required_status"]:
        raise ValueError("frozen receipt status differs")
    if receipt.get("clauses", {}).get("TOTAL_FUTURE_TARGET_PHYSICAL_ENVELOPE") != (
        frozen["required_target_envelope_state"]
    ):
        raise ValueError("frozen target-envelope clause differs")
    if receipt.get("unresolved_terms") != EXPECTED_TERMS:
        raise ValueError("frozen unresolved-term set differs")
    interpretation = receipt.get("interpretation", {})
    if interpretation.get("target_selected") is not False:
        raise ValueError("target selection entered the frozen receipt")
    if interpretation.get("target_orbit_accessed") is not False:
        raise ValueError("target orbit entered the frozen receipt")
    persistence = receipt.get("persistence", {})
    if persistence.get("individual_observation_values") is not False:
        raise ValueError("individual observation values entered the receipt")
    if persistence.get("individual_residuals") is not False:
        raise ValueError("individual residuals entered the receipt")
    envelopes = receipt.get("conditional_reference_envelopes", {})
    if envelopes.get("fit_phase_rate_m_s") != 0.037339025487426625:
        raise ValueError("fit reference envelope differs")
    if envelopes.get("gold_code_m") != 15.121046550571918:
        raise ValueError("heldout reference envelope differs")
    if envelopes.get("population_coverage_claim") is not False:
        raise ValueError("unexpected population-coverage claim")


def validate_receipt(plan: dict, receipt_path: Path) -> tuple[dict, str]:
    frozen = plan["frozen_input"]
    receipt_bytes = receipt_path.read_bytes()
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_sha256 != frozen["sha256"]:
        raise ValueError("frozen receipt hash mismatch")
    receipt = load_strict_json_bytes(receipt_bytes)
    validate_receipt_fields(plan, receipt)
    return receipt, receipt_sha256


def run(plan_path: Path, source_commit: str) -> dict:
    if not source_commit:
        raise ValueError("source commit is required")
    plan_bytes = plan_path.read_bytes()
    implementation_bytes = Path(__file__).read_bytes()
    plan = load_strict_json_bytes(plan_bytes)
    validate_plan(plan, plan_bytes)
    admit_git_freeze(plan_path, source_commit, plan_bytes, implementation_bytes)
    receipt_path = ROOT / plan["frozen_input"]["path"]
    receipt, receipt_sha256 = validate_receipt(plan, receipt_path)

    assessments = []
    for row in plan["terms"]:
        assessments.append({
            "term": row["term"],
            "causal_class": row["causal_class"],
            "receipt_evidence": row["receipt_evidence"],
            "evidence_role": "DIAGNOSTIC_ONLY",
            "required_for_transfer": row["required_for_transfer"],
            "missing_from_receipt": row["missing_from_receipt"],
            "assessment": "NOT_IDENTIFIABLE_FROM_RECEIPT",
            "physical_state": "UNRESOLVED",
            "numeric_bound_from_receipt": None,
            "may_be_assigned_zero": False,
        })

    all_bounded = all(
        row["assessment"] == "BOUNDED_BY_RECEIPT" for row in assessments
    )
    status = (
        "FUTURE_TARGET_ENVELOPE_IDENTIFIED"
        if all_bounded
        else "FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT"
    )
    result = {
        "schema": "s2-reference-to-target-transfer-audit-result-v3",
        "audit_id": plan["audit_id"],
        "status": status,
        "scope": plan["scope"],
        "supersedes": {
            "path": "research/kinematic/results/s2_reference_target_transfer_audit_v2.json",
            "sha256": "9a4e2c859a9eb1e096f62f8cf09accc6743ab91a76428f6d684c85419673142b",
            "reason": "Second post-merge integrity repair: single-read hash/parse coupling and commit-resolved implementation provenance in full-history CI.",
        },
        "inputs": {
            "source_commit": source_commit,
            "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
            "implementation_sha256": hashlib.sha256(implementation_bytes).hexdigest(),
            "reference_receipt": plan["frozen_input"]["path"],
            "reference_receipt_sha256": receipt_sha256,
            "source_or_network_access": False,
            "new_numeric_measurements": False,
            "target_selected": False,
            "target_state_or_orbit_accessed": False,
        },
        "preserved_reference_path_evidence": {
            "status": receipt["status"],
            "conditional_reference_envelopes": receipt["conditional_reference_envelopes"],
            "interpretation": "These values remain conditional bounds on the observed reference path and are not target-direction bounds.",
        },
        "term_assessments": assessments,
        "composition": {
            "bounded_future_target_terms": [],
            "unresolved_future_target_terms": [row["term"] for row in assessments],
            "fit_phase_rate_reference_envelope_m_s": receipt[
                "conditional_reference_envelopes"
            ]["fit_phase_rate_m_s"],
            "gold_code_reference_envelope_m": receipt[
                "conditional_reference_envelopes"
            ]["gold_code_m"],
            "total_future_target_physical_envelope": None,
            "composition_performed": False,
            "reason": "Every future-target transfer term lacks at least one required causal quantity; the two reference envelopes also have different coordinates and are not added.",
        },
        "clauses": {
            "REFERENCE_RECEIPT_INTEGRITY": "SATISFIED",
            "CONDITIONAL_REFERENCE_PATH_ENVELOPE": "SATISFIED",
            "DIRECTIONAL_TARGET_TRANSFER": "UNRESOLVED",
            "TEMPORAL_TARGET_TRANSFER": "UNRESOLVED",
            "REFERENCE_TARGET_COVARIANCE": "UNRESOLVED",
            "TOTAL_FUTURE_TARGET_PHYSICAL_ENVELOPE": "UNRESOLVED",
        },
        "claim_boundary": {
            "authorized": [
                "DOY240 reference-path aggregate residuals met their frozen deterministic limits",
                "the frozen aggregate receipt cannot identify a total future-target physical envelope",
            ],
            "not_authorized": [
                "any unresolved term is negligible or zero",
                "the conditional reference envelopes cover a future target",
                "a primary, target or S3 campaign is admissible",
                "population coverage or a calibrated probability statement",
            ],
            "s3_authorized": False,
        },
        "minimum_new_evidence_classes": [
            "direction-resolved antenna/site response with uncertainty",
            "target-side continuity detection with a missed-slip bound",
            "future-path atmosphere uncertainty",
            "reference orbit/clock covariance projected through calibration",
            "predeclared reference-target shared/differential covariance",
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
    print(json.dumps({
        "status": result["status"],
        "clauses": result["clauses"],
        "unresolved_term_count": len(result["composition"]["unresolved_future_target_terms"]),
    }, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
