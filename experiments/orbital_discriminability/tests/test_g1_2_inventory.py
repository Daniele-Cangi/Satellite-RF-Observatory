"""Offline tests for the Gate G1.2 inventory-mechanism boundary."""

from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import ast
import json
from pathlib import Path

import numpy as np
import pytest

from experiments.orbital_discriminability import g1_2_inventory as g12


NOW = datetime(2026, 8, 19, 14, 0, 0, tzinfo=timezone.utc)
RECEIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "session_receipts"
    / "g1_1_status_outcome_1.jsonl"
)


def _g11_candidate() -> g12.InventoryMechanismReceipt:
    payload = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    return g12.candidate_from_g11_receipt(payload)


def _clause(
    assessment: g12.InventoryMechanismAssessment,
    clause_id: str,
) -> g12.InventoryClause:
    return next(item for item in assessment.clauses if item.clause_id == clause_id)


def test_frozen_g11_directory_is_rejected_as_inventory_not_as_capability() -> None:
    candidate = _g11_candidate()
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(),
        candidate,
        evaluated_at=NOW,
    )

    assert candidate.artifact_sha256 == (
        "f59bd5d1e54a3dcb33a99ffb651254bfa11154b5adcb0f30891170dcf3aa7b14"
    )
    assert not assessment.mechanism_admissible
    assert _clause(assessment, "artifact_integrity").state == "SATISFIED"
    assert _clause(assessment, "noninteractive_route").state == "UNSATISFIED"
    assert _clause(assessment, "automation_intent").state == "UNSATISFIED"
    assert _clause(assessment, "temporal_validity").state == "UNSATISFIED"
    assert "no receiver absence follows" in assessment.claim_scope


def test_remembered_endpoints_are_not_current_selection_evidence() -> None:
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(),
        g12.remembered_endpoint_fixture(),
        evaluated_at=NOW,
    )

    assert not assessment.mechanism_admissible
    assert _clause(assessment, "current_artifact_basis").state == "UNSATISFIED"
    assert _clause(assessment, "artifact_integrity").state == "UNSATISFIED"
    assert _clause(assessment, "declared_coverage").state == "UNSATISFIED"


@pytest.mark.parametrize(
    "factory,expected_kind",
    (
        (
            g12.operator_manifest_contract_fixture,
            g12.InventoryMechanismKind.OPERATOR_MANIFEST.value,
        ),
        (
            g12.dns_service_contract_fixture,
            g12.InventoryMechanismKind.DNS_SERVICE_DISCOVERY.value,
        ),
    ),
)
def test_two_distinct_contract_forms_are_admissible_in_principle(
    factory,
    expected_kind: str,
) -> None:
    receipt = factory(observed_at=NOW)
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(),
        receipt,
        evaluated_at=NOW,
    )

    assert assessment.mechanism_kind == expected_kind
    assert assessment.mechanism_admissible
    assert all(item.state == "SATISFIED" for item in assessment.clauses)
    assert "does not assert that the route or endpoints exist" in assessment.claim_scope


def test_https_origin_cannot_rescue_interactive_custom_authorization() -> None:
    candidate = replace(
        g12.operator_manifest_contract_fixture(observed_at=NOW),
        interaction_required=True,
        browser_state_or_custom_auth_required=True,
    )
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(),
        candidate,
        evaluated_at=NOW,
    )

    assert not assessment.mechanism_admissible
    assert _clause(assessment, "authority_binding").state == "SATISFIED"
    assert _clause(assessment, "noninteractive_route").state == "UNSATISFIED"


@pytest.mark.parametrize(
    "mutation,failed_clause",
    (
        ({"raw_artifact_persisted": True}, "ephemeral_artifact"),
        ({"ttl_s": 601.0}, "temporal_validity"),
        ({"ttl_s": 100.0}, "temporal_validity"),
        ({"complete_for_declared_scope": False}, "declared_coverage"),
        ({"endpoint_count": 21}, "deterministic_endpoint_binding"),
        ({"endpoint_set_sha256": None}, "deterministic_endpoint_binding"),
        ({"hashed_before_parsing": False}, "artifact_integrity"),
        ({"rf_activity": "SND"}, "descriptive_only"),
    ),
)
def test_each_boundary_refuses_without_promoting_capability(
    mutation: dict[str, object],
    failed_clause: str,
) -> None:
    candidate = replace(
        g12.operator_manifest_contract_fixture(observed_at=NOW),
        **mutation,
    )
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(),
        candidate,
        evaluated_at=NOW,
    )

    assert not assessment.mechanism_admissible
    assert _clause(assessment, failed_clause).state == "UNSATISFIED"


def test_snapshot_must_cover_future_qualification_budget_not_only_be_fresh_now() -> None:
    candidate = replace(
        g12.operator_manifest_contract_fixture(observed_at=NOW - timedelta(seconds=190)),
        ttl_s=300.0,
    )
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(),
        candidate,
        evaluated_at=NOW,
    )

    assert not assessment.mechanism_admissible
    assert _clause(assessment, "temporal_validity").state == "UNSATISFIED"


def test_comparison_is_order_invariant_and_does_not_select_a_fixture_as_live() -> None:
    receipts = (
        _g11_candidate(),
        g12.remembered_endpoint_fixture(),
        g12.operator_manifest_contract_fixture(observed_at=NOW),
        g12.dns_service_contract_fixture(observed_at=NOW),
    )
    forward = g12.compare_inventory_mechanisms(
        g12.G12InventoryPlan(), receipts, evaluated_at=NOW
    )
    reverse = g12.compare_inventory_mechanisms(
        g12.G12InventoryPlan(), tuple(reversed(receipts)), evaluated_at=NOW
    )

    assert forward == reverse
    assert forward.outcome == g12.G12Outcome.NO_LEGITIMATE_INVENTORY_MECHANISM.value
    assert forward.observed_admissible_mechanisms == ()
    assert forward.admissible_contract_fixtures == (
        "fixture:dnssec-service-discovery",
        "fixture:operator-manifest",
    )
    assert forward.capability_admission_state == "NOT_EVALUATED"
    assert forward.status_request_count == 0
    assert forward.raw_rf_activity == "ZERO"
    assert not forward.persistent_catalog_created


def test_empty_comparison_cannot_create_a_vacuous_absence_claim() -> None:
    with pytest.raises(ValueError, match="at least one receipt"):
        g12.compare_inventory_mechanisms(
            g12.G12InventoryPlan(), (), evaluated_at=NOW
        )


def test_g11_import_refuses_a_different_terminal_route() -> None:
    payload = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    payload["fetch_receipts"][-1]["requested_url"] = "http://remembered.invalid"

    with pytest.raises(ValueError, match="frozen directory route"):
        g12.candidate_from_g11_receipt(payload)


def test_observed_valid_receipt_admits_only_the_inventory_mechanism() -> None:
    observed = replace(
        g12.operator_manifest_contract_fixture(observed_at=NOW),
        mechanism_id="observed:operator-manifest",
        evidence_basis=g12.EvidenceBasis.OBSERVED_ARTIFACT.value,
    )
    result = g12.compare_inventory_mechanisms(
        g12.G12InventoryPlan(), (observed,), evaluated_at=NOW
    )

    assert result.outcome == g12.G12Outcome.INVENTORY_MECHANISM_ADMISSIBLE.value
    assert result.observed_admissible_mechanisms == ("observed:operator-manifest",)
    assert result.capability_admission_state == "NOT_EVALUATED"
    assert "a receiver or receiver pair satisfies Gate G1" in result.unauthorized_claims


def test_complete_empty_scope_is_meaningful_but_still_only_admits_mechanism() -> None:
    observed = replace(
        g12.operator_manifest_contract_fixture(observed_at=NOW),
        mechanism_id="observed:empty-operator-manifest",
        evidence_basis=g12.EvidenceBasis.OBSERVED_ARTIFACT.value,
        endpoint_count=0,
        endpoint_set_sha256=sha256(b"[]").hexdigest(),
    )
    result = g12.compare_inventory_mechanisms(
        g12.G12InventoryPlan(), (observed,), evaluated_at=NOW
    )

    assert result.outcome == g12.G12Outcome.INVENTORY_MECHANISM_ADMISSIBLE.value
    assert result.capability_admission_state == "NOT_EVALUATED"
    assert result.status_request_count == 0


def test_strict_json_normalizes_numpy_scalars_and_rejects_nonfinite_numbers() -> None:
    candidate = replace(
        g12.operator_manifest_contract_fixture(observed_at=NOW),
        endpoint_count=np.int64(2),
        artifact_byte_count=np.int64(63),
    )
    result = g12.compare_inventory_mechanisms(
        g12.G12InventoryPlan(), (candidate,), evaluated_at=NOW
    )
    encoded = result.strict_json()

    assert "NaN" not in encoded and "Infinity" not in encoded
    assert json.loads(encoded)["assessments"][0]["mechanism_admissible"] is True
    bad = replace(candidate, ttl_s=float("nan"))
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(), bad, evaluated_at=NOW
    )
    assert not assessment.mechanism_admissible
    assert _clause(assessment, "temporal_validity").state == "UNSATISFIED"


def test_receipt_hash_binds_description_without_endpoint_or_artifact_payloads() -> None:
    receipt = g12.operator_manifest_contract_fixture(observed_at=NOW)
    assessment = g12.evaluate_inventory_mechanism(
        g12.G12InventoryPlan(), receipt, evaluated_at=NOW
    )
    encoded = json.dumps(asdict(assessment), sort_keys=True)

    assert len(assessment.receipt_hash) == 64
    assert receipt.endpoint_set_sha256 is not None
    assert '["a","b"]' not in encoded


@pytest.mark.parametrize(
    "mutation",
    (
        {"qualification_budget_s": 121.0},
        {"maximum_snapshot_ttl_s": 601.0},
        {"maximum_endpoints": 21},
        {"required_endpoint_fields": ("host",)},
        {"retry_count": 1},
    ),
)
def test_plan_refuses_scope_expansion(mutation: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(g12.G12InventoryPlan(), **mutation).validate()


def test_frozen_g11_receipt_itself_remains_byte_exact() -> None:
    assert sha256(RECEIPT_PATH.read_bytes()).hexdigest() == (
        "a91f1a8b7fabf047f8cc70d0bf55732e2b1b0639241f190a73bd56fb29951504"
    )


def test_gate_module_has_no_network_or_persistence_imports() -> None:
    source = Path(g12.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    modules.update(
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert modules.isdisjoint(
        {"urllib", "requests", "httpx", "socket", "websocket", "pathlib", "sqlite3"}
    )
