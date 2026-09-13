"""Regressions for the one-off target/reference differential audit."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from research.kinematic import differential_observable_audit as audit
from research.kinematic.reference_target_transfer_audit import load_strict_json_bytes


ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = ROOT / "research/kinematic/differential_observable_audit_plan.json"


def load_plan() -> tuple[dict, bytes]:
    content = PLAN_PATH.read_bytes()
    return load_strict_json_bytes(content), content


def test_plan_is_hash_bound_and_target_free():
    plan, content = load_plan()
    audit.validate_plan(plan, content)
    assert hashlib.sha256(content).hexdigest() == audit.EXPECTED_PLAN_SHA256
    topology = plan["declared_topology"]
    assert topology["target_measurements_available"] is False
    assert topology["target_identity_selected"] is False
    assert topology["target_orbit_available"] is False


def test_normalized_algebra_cancels_only_the_identical_common_mode():
    witness = audit.normalized_algebra_witness()
    assert witness["coordinate"].startswith("normalized algebraic basis")
    assert witness["common_affine_max_abs"] < 1e-12
    np.testing.assert_allclose(
        witness["common_affine_response"], np.zeros((2, 2)), atol=1e-12
    )
    np.testing.assert_allclose(
        witness["reference_only_response"], -np.eye(2), atol=1e-12
    )
    np.testing.assert_allclose(
        witness["target_only_response"], np.eye(2), atol=1e-12
    )


def test_prospective_witness_and_partial_cancellations_do_not_close_terms():
    plan, _ = load_plan()
    assessments, absorbing = audit.assess_terms(plan)
    assert [row["term"] for row in assessments] == audit.EXPECTED_TERMS
    assert all(row["state"] == "UNRESOLVED" for row in assessments)
    slip = assessments[2]
    observable = next(
        row for row in slip["components"] if row["classification"] == "OBSERVABLE"
    )
    assert observable["availability"] == "FUTURE_PRIMARY_ONLY"
    assert observable["currently_closes_component"] is False
    modeled = [
        component
        for term in assessments
        for component in term["components"]
        if component["classification"] == "MODELED"
    ]
    assert len(modeled) == 2
    assert all(component["finite_bound"] == 0.0 for component in modeled)
    assert len(absorbing) == 6


def test_unresolved_component_cannot_be_relabelled_zero():
    plan, content = load_plan()
    changed = deepcopy(plan)
    component = changed["terms"][0]["components"][0]
    component["classification"] = "MODELED"
    component["finite_bound"] = 0.0
    with pytest.raises(ValueError, match="supplied plan object differs"):
        audit.validate_plan(changed, content)


def test_noninvariant_modeled_bound_is_rejected_after_exact_reencoding(monkeypatch):
    plan, content = load_plan()
    changed = deepcopy(plan)
    component = changed["terms"][0]["components"][0]
    component["classification"] = "MODELED"
    component["finite_bound"] = 0.0
    component["transform_response"] = "ASSUMED_SMALL"
    changed_bytes = json.dumps(changed, separators=(",", ":")).encode()
    monkeypatch.setattr(audit, "EXPECTED_PLAN_SHA256", audit.sha256_bytes(changed_bytes))
    with pytest.raises(ValueError, match="only proved exact invariants"):
        audit.validate_plan(changed, changed_bytes)


def test_unit_run_stops_without_composition_or_s3(monkeypatch):
    observed = []
    monkeypatch.setattr(
        audit,
        "admit_git_freeze",
        lambda source_commit, frozen_files: observed.append(
            (source_commit, frozen_files)
        ),
    )
    result = audit.run(PLAN_PATH, "unit-test-source-commit")
    assert len(observed) == 1
    assert observed[0][0] == "unit-test-source-commit"
    assert len(observed[0][1]) == 3
    assert result["status"] == (
        "DIFFERENTIAL_OBSERVABLE_HAS_ABSORBING_UNRESOLVED_TERM"
    )
    assert result["composition"]["performed"] is False
    assert result["composition"]["total_future_target_physical_envelope"] is None
    assert result["claim_boundary"]["s3_authorized"] is False
    assert result["inputs"]["source_or_network_access"] is False
    assert result["inputs"]["new_observation_or_navigation_decoding"] is False
    assert result["inputs"]["target_selected"] is False
    assert result["inputs"]["target_state_or_orbit_accessed"] is False


@pytest.mark.parametrize("changed_index", (0, 1, 2))
def test_git_freeze_rejects_each_changed_buffer(monkeypatch, changed_index: int):
    source_commit = "1" * 40
    files = [
        (PLAN_PATH, PLAN_PATH.read_bytes()),
        (Path(audit.__file__).resolve(), Path(audit.__file__).read_bytes()),
        (
            Path(audit.calibration_transfer.__file__).resolve(),
            Path(audit.calibration_transfer.__file__).read_bytes(),
        ),
    ]
    committed = {
        path.resolve().relative_to(ROOT).as_posix(): content
        for path, content in files
    }

    def fake_check_output(args, **kwargs):
        if args[1:3] == ["status", "--porcelain"]:
            return ""
        if args[1:3] == ["rev-parse", "HEAD"]:
            return source_commit + "\n"
        if args[1] == "show":
            return committed[args[2].removeprefix("HEAD:")]
        raise AssertionError(f"unexpected git invocation: {args}")

    monkeypatch.setattr(audit.subprocess, "check_output", fake_check_output)
    changed = list(files)
    changed[changed_index] = (changed[changed_index][0], changed[changed_index][1] + b"\n")
    with pytest.raises(ValueError, match="frozen file differs from committed bytes"):
        audit.admit_git_freeze(source_commit, changed)
