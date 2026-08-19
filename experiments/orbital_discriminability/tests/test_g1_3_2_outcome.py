import json
from pathlib import Path

import pytest


RECEIPT = (
    Path(__file__).parents[1]
    / "session_receipts"
    / "g1_3_2_search_outcome_1.jsonl"
)


def _payload() -> dict[str, object]:
    lines = RECEIPT.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    return json.loads(lines[0], parse_constant=lambda value: pytest.fail(value))


def test_frozen_outcome_is_scoped_negative_not_capability_absence() -> None:
    payload = _payload()
    assert payload["outcome"] == "NO_LEGITIMATE_INVENTORY_FOUND"
    assert payload["admitted_mechanisms"] == []
    assert payload["capability_admission_state"] == "NOT_EVALUATED"
    assert payload["status_request_count"] == 0
    assert payload["raw_rf_activity"] == "ZERO"
    assert payload["persistent_catalog_created"] is False


def test_every_query_and_round_robin_candidate_is_evaluated() -> None:
    payload = _payload()
    searches = payload["search_receipts"]
    candidates = payload["candidate_assessments"]
    assert len(searches) == 4
    assert all(item["state"] == "SUCCESS" for item in searches)
    assert all(item["result_count"] == 5 for item in searches)
    assert all(item["raw_search_artifact_persisted"] is False for item in searches)
    assert len(candidates) == 6
    assert all(item["state"] == "EVALUATED" for item in candidates)


def test_artifact_integrity_never_makes_a_mechanism_admissible() -> None:
    payload = _payload()
    for candidate in payload["candidate_assessments"]:
        assessment = candidate["mechanism_assessment"]
        clauses = {item["clause_id"]: item for item in assessment["clauses"]}
        assert clauses["artifact_integrity"]["state"] == "SATISFIED"
        assert clauses["ephemeral_artifact"]["state"] == "SATISFIED"
        assert clauses["descriptive_only"]["state"] == "SATISFIED"
        assert clauses["machine_readable_schema"]["state"] == "UNSATISFIED"
        assert clauses["declared_coverage"]["state"] == "UNSATISFIED"
        assert clauses["deterministic_endpoint_binding"]["state"] == "UNSATISFIED"
        assert assessment["mechanism_admissible"] is False
