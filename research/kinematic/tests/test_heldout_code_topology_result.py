"""Frozen result regressions for the target-free code-heldout topology audit."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT/"research/kinematic/heldout_code_topology_plan.json"
RESULT = ROOT/"research/kinematic/results/s2_heldout_code_topology_v1.json"


def test_result_identity_and_access_boundaries():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["status"] == "HELDOUT_CODE_TOPOLOGY_CONDITIONALLY_AVAILABLE"
    assert result["freeze"]["source_commit"] == "e57e4634f4ca9f755b90690ba52040c512397585"
    assert result["freeze"]["plan_sha256"] == hashlib.sha256(PLAN.read_bytes()).hexdigest()
    assert result["input_boundaries"] == {
        "candidate_artifacts_accessed": False,
        "new_network_access": False,
        "observation_values_read": False,
        "target_or_orbit_used": False,
    }


def test_result_preserves_conditional_ranking_and_unresolved_physics():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["candidate_ranking"] == ["DRAO00CAN", "YELL00CAN", "STJO00CAN"]
    drao = result["candidates"][0]
    assert drao["visible_predecessor_cases"] == 181
    assert drao["cases_with_positive_slack_at_both_endpoints"] == 180
    assert drao["physical_affine_slack_m"] == {
        "maximum": 19.735002589884886,
        "median": 12.530271457963948,
        "minimum": -1.363475247934609,
    }
    assert result["clauses"]["SIXTH_ROOT_CODE_COORDINATE"] == "UNRESOLVED_NOT_ACCESSED"
    assert result["clauses"]["TOTAL_PHYSICAL_ERROR_ENVELOPE"] == "UNRESOLVED"
    assert not result["interpretation"]["ranking_is_receiver_admission"]
    assert not result["interpretation"]["s3_authorized"]
    assert any(row["state"] == "UNRESOLVED" for row in result["physical_envelope_ledger"])


def test_result_source_hashes_match_checkout():
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    for name, expected in result["sources_sha256"].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected
