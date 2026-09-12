"""Audit what the frozen DOY240 reference receipt can transfer to a future target."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
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


def load_strict_json(path: Path) -> dict:
    def unique_object(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key:" + key)
            result[key] = value
        return result

    value = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=unique_object,
    )
    if not isinstance(value, dict):
        raise ValueError("top-level JSON value must be an object")
    return value


def validate_plan(plan: dict) -> None:
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


def validate_receipt(plan: dict, receipt: dict, receipt_path: Path) -> None:
    frozen = plan["frozen_input"]
    if sha256_path(receipt_path) != frozen["sha256"]:
        raise ValueError("frozen receipt hash mismatch")
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


def run(plan_path: Path) -> dict:
    plan = load_strict_json(plan_path)
    validate_plan(plan)
    receipt_path = ROOT / plan["frozen_input"]["path"]
    receipt = load_strict_json(receipt_path)
    validate_receipt(plan, receipt, receipt_path)

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
        "schema": "s2-reference-to-target-transfer-audit-result-v1",
        "audit_id": plan["audit_id"],
        "status": status,
        "scope": plan["scope"],
        "inputs": {
            "plan_sha256": sha256_path(plan_path),
            "reference_receipt": plan["frozen_input"]["path"],
            "reference_receipt_sha256": sha256_path(receipt_path),
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
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite an existing result")
    result = run(args.plan)
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
