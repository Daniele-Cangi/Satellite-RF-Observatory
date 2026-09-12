"""Offline tests for the DOY240 reference-to-target causal audit."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from research.kinematic import reference_target_transfer_audit as audit
from research.kinematic.reference_target_transfer_audit import (
    EXPECTED_PLAN_SHA256,
    EXPECTED_TERMS,
    load_strict_json,
    run,
    validate_plan,
    validate_receipt,
    validate_receipt_fields,
)


ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = ROOT / "research/kinematic/reference_target_transfer_audit_plan.json"
RECEIPT_PATH = (
    ROOT / "research/kinematic/results/s2_five_root_reference_envelope_2026240_v1.json"
)


def test_plan_is_exactly_bounded_to_frozen_aggregate_receipt():
    plan = load_strict_json(PLAN_PATH)
    validate_plan(plan, PLAN_PATH)
    assert hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest() == EXPECTED_PLAN_SHA256
    assert plan["frozen_input"]["sha256"] == hashlib.sha256(
        RECEIPT_PATH.read_bytes()
    ).hexdigest()
    assert "network or source access" in plan["forbidden_evidence_or_actions"]
    assert "target identity, target state or target orbit" in plan[
        "forbidden_evidence_or_actions"
    ]


def test_every_unresolved_term_has_an_explicit_missing_causal_quantity():
    plan = load_strict_json(PLAN_PATH)
    assert [row["term"] for row in plan["terms"]] == EXPECTED_TERMS
    assert all(row["required_for_transfer"] for row in plan["terms"])
    assert all(row["missing_from_receipt"] for row in plan["terms"])


def test_changed_input_hash_or_term_is_rejected():
    plan = load_strict_json(PLAN_PATH)
    changed = deepcopy(plan)
    changed["frozen_input"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="supplied plan object differs"):
        validate_plan(changed, PLAN_PATH)
    changed = deepcopy(plan)
    changed["composition_rule"] = "silently add every term"
    with pytest.raises(ValueError, match="supplied plan object differs"):
        validate_plan(changed, PLAN_PATH)


def test_target_or_individual_value_contamination_is_rejected():
    plan = load_strict_json(PLAN_PATH)
    receipt = load_strict_json(RECEIPT_PATH)
    changed = deepcopy(receipt)
    changed["interpretation"]["target_orbit_accessed"] = True
    with pytest.raises(ValueError, match="target orbit"):
        validate_receipt_fields(plan, changed)
    changed = deepcopy(receipt)
    changed["persistence"]["individual_observation_values"] = True
    with pytest.raises(ValueError, match="individual observation"):
        validate_receipt_fields(plan, changed)
    assert validate_receipt(plan, RECEIPT_PATH) == receipt


def test_strict_json_rejects_nan_and_duplicate_keys(tmp_path: Path):
    nonfinite = tmp_path / "nonfinite.json"
    nonfinite.write_text('{"value": NaN}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite"):
        load_strict_json(nonfinite)
    overflow = tmp_path / "overflow.json"
    overflow.write_text('{"value": 1e309}', encoding="utf-8")
    with pytest.raises(ValueError, match="non-finite JSON number"):
        load_strict_json(overflow)
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"value": 1, "value": 2}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        load_strict_json(duplicate)


def _unit_run(monkeypatch: pytest.MonkeyPatch) -> dict:
    observed = []
    monkeypatch.setattr(
        audit,
        "admit_git_freeze",
        lambda plan_path, source_commit: observed.append((plan_path, source_commit)),
    )
    result = run(PLAN_PATH, "unit-test-source-commit")
    assert observed == [(PLAN_PATH, "unit-test-source-commit")]
    assert result["inputs"]["source_commit"] == "unit-test-source-commit"
    return result


def test_audit_never_composes_or_zeroes_unresolved_terms(monkeypatch):
    result = _unit_run(monkeypatch)
    assert result["status"] == (
        "FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT"
    )
    assert result["composition"]["composition_performed"] is False
    assert result["composition"]["total_future_target_physical_envelope"] is None
    assert result["composition"]["bounded_future_target_terms"] == []
    assert len(result["term_assessments"]) == 6
    assert all(row["assessment"] == "NOT_IDENTIFIABLE_FROM_RECEIPT"
               for row in result["term_assessments"])
    assert all(row["evidence_role"] == "DIAGNOSTIC_ONLY"
               for row in result["term_assessments"])
    assert all(row["numeric_bound_from_receipt"] is None
               for row in result["term_assessments"])
    assert all(row["may_be_assigned_zero"] is False
               for row in result["term_assessments"])
    assert result["claim_boundary"]["s3_authorized"] is False


def test_reference_bounds_are_preserved_in_their_original_coordinates(monkeypatch):
    result = _unit_run(monkeypatch)
    assert result["composition"]["fit_phase_rate_reference_envelope_m_s"] == (
        0.037339025487426625
    )
    assert result["composition"]["gold_code_reference_envelope_m"] == (
        15.121046550571918
    )
    assert result["preserved_reference_path_evidence"][
        "conditional_reference_envelopes"
    ]["population_coverage_claim"] is False


def test_frozen_audit_result_is_hash_bound_and_authorizes_no_primary():
    path = ROOT / "research/kinematic/results/s2_reference_target_transfer_audit_v1.json"
    result = load_strict_json(path)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "20113de41579269e10d0260abb97aa739499069afffc14adb4063ecaf7f1c99c"
    )
    assert result["status"] == (
        "FUTURE_TARGET_ENVELOPE_NOT_IDENTIFIABLE_FROM_REFERENCE_RECEIPT"
    )
    assert result["inputs"]["source_commit"] == (
        "32955325987ca92dadf91d83b1a5185d8d5ca5e9"
    )
    assert result["inputs"]["implementation_sha256"] == (
        "f18051a39a7ed3d1e21ce7beb0da0b4bfc8ee45fac91b7790309f1cf43faa0d5"
    )
    assert result["inputs"]["source_or_network_access"] is False
    assert result["inputs"]["new_numeric_measurements"] is False
    assert result["inputs"]["target_selected"] is False
    assert result["inputs"]["target_state_or_orbit_accessed"] is False
    assert result["composition"]["total_future_target_physical_envelope"] is None
    assert result["clauses"]["TOTAL_FUTURE_TARGET_PHYSICAL_ENVELOPE"] == (
        "UNRESOLVED"
    )
    assert result["claim_boundary"]["s3_authorized"] is False
    source_commit = result["inputs"]["source_commit"]
    implementation_at_freeze = subprocess.check_output(
        ["git", "show", f"{source_commit}:research/kinematic/reference_target_transfer_audit.py"],
        cwd=ROOT,
    )
    assert result["inputs"]["plan_sha256"] == hashlib.sha256(
        PLAN_PATH.read_bytes()
    ).hexdigest()
    assert result["inputs"]["reference_receipt_sha256"] == hashlib.sha256(
        RECEIPT_PATH.read_bytes()
    ).hexdigest()
    assert result["inputs"]["implementation_sha256"] == hashlib.sha256(
        implementation_at_freeze
    ).hexdigest()
