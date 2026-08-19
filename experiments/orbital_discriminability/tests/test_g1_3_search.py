"""Offline tests for the frozen Gate G1.3 search closure."""

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import ast
from pathlib import Path

import pytest

from experiments.orbital_discriminability import g1_2_inventory as g12
from experiments.orbital_discriminability import g1_3_search as g13


NOW = datetime(2026, 8, 19, 15, 0, 0, tzinfo=timezone.utc)


def _searches(*, failed_query: str | None = None) -> tuple[g13.SearchQueryReceipt, ...]:
    receipts = []
    for index, query in enumerate(g13.FROZEN_QUERIES):
        urls = ("https://operator-0.invalid/inventory-doc",) if index == 0 else ()
        failed = query == failed_query
        receipts.append(
            g13.SearchQueryReceipt(
                query=query,
                state=(
                    g13.SearchState.SEARCH_ERROR.value
                    if failed
                    else g13.SearchState.SUCCESS.value
                ),
                result_count=len(urls),
                ordered_result_set_sha256=(
                    None if failed else g13.ordered_result_hash(urls)
                ),
                candidate_document_urls=urls,
                detail="synthetic search receipt",
            )
        )
    return tuple(receipts)


def _inventory(mechanism_id: str, *, admissible: bool) -> g12.InventoryMechanismReceipt:
    candidate = g12.operator_manifest_contract_fixture(observed_at=NOW)
    candidate = replace(
        candidate,
        mechanism_id=mechanism_id,
        evidence_basis=g12.EvidenceBasis.OBSERVED_ARTIFACT.value,
    )
    if not admissible:
        candidate = replace(candidate, automation_permission_reference=None)
    return candidate


def _audit(
    *,
    rank: int = 1,
    admissible: bool = False,
    document_url: str = "https://operator-0.invalid/inventory-doc",
) -> g13.CandidateMechanismAudit:
    document = b"operator documentation fixture"
    mechanism_id = g13.mechanism_id_for_url(document_url)
    return g13.CandidateMechanismAudit(
        mechanism_id=mechanism_id,
        search_query=g13.FROZEN_QUERIES[0],
        discovery_rank=rank,
        operator_document_url=document_url,
        operator_document_sha256=sha256(document).hexdigest(),
        inventory_url="https://operator.invalid/inventory.json",
        state=g13.CandidateAuditState.EVALUATED.value,
        inventory_receipt=_inventory(mechanism_id, admissible=admissible),
        detail="synthetic evaluated candidate",
    )


def test_all_evaluated_refusals_produce_only_bounded_no_inventory() -> None:
    result = g13.finalize_inventory_search(
        g13.G13SearchPlan(),
        _searches(),
        (_audit(),),
        evaluated_at=NOW,
    )

    assert result.outcome == g13.G13Outcome.NO_LEGITIMATE_INVENTORY_FOUND.value
    assert result.admitted_mechanisms == ()
    assert result.capability_admission_state == "NOT_EVALUATED"
    assert result.status_request_count == 0
    assert result.raw_rf_activity == "ZERO"
    assert not result.persistent_catalog_created
    assert "anywhere on the Internet" in result.unauthorized_claims[0]


def test_one_observed_admissible_mechanism_is_not_receiver_admission() -> None:
    result = g13.finalize_inventory_search(
        g13.G13SearchPlan(),
        _searches(),
        (_audit(admissible=True),),
        evaluated_at=NOW,
    )

    assert result.outcome == g13.G13Outcome.LEGITIMATE_INVENTORY_FOUND.value
    assert result.admitted_mechanisms == (
        g13.mechanism_id_for_url("https://operator-0.invalid/inventory-doc"),
    )
    assert result.capability_admission_state == "NOT_EVALUATED"


def test_search_error_prevents_absence_claim() -> None:
    result = g13.finalize_inventory_search(
        g13.G13SearchPlan(),
        _searches(failed_query=g13.FROZEN_QUERIES[2]),
        (_audit(),),
        evaluated_at=NOW,
    )

    assert result.outcome == g13.G13Outcome.INVENTORY_SEARCH_INCOMPLETE.value


def test_candidate_qualification_error_prevents_absence_claim() -> None:
    audit = replace(
        _audit(),
        state=g13.CandidateAuditState.QUALIFICATION_ERROR.value,
        inventory_receipt=None,
        detail="document fetch timed out",
    )
    result = g13.finalize_inventory_search(
        g13.G13SearchPlan(), _searches(), (audit,), evaluated_at=NOW
    )

    assert result.outcome == g13.G13Outcome.INVENTORY_SEARCH_INCOMPLETE.value
    assert result.candidate_assessments[0].mechanism_assessment is None


def test_contract_fixture_and_remembered_state_cannot_enter_live_search() -> None:
    for basis in (
        g12.EvidenceBasis.CONTRACT_FIXTURE.value,
        g12.EvidenceBasis.REMEMBERED_STATE.value,
    ):
        audit = _audit()
        audit = replace(
            audit,
            inventory_receipt=replace(audit.inventory_receipt, evidence_basis=basis),
        )
        with pytest.raises(ValueError, match="observed current-session"):
            g13.finalize_inventory_search(
                g13.G13SearchPlan(), _searches(), (audit,), evaluated_at=NOW
            )


def test_search_receipts_match_every_frozen_query_and_hash() -> None:
    with pytest.raises(ValueError, match="every frozen query"):
        g13.finalize_inventory_search(
            g13.G13SearchPlan(), _searches()[:-1], (), evaluated_at=NOW
        )

    first, *rest = _searches()
    altered = replace(first, ordered_result_set_sha256="0" * 64)
    with pytest.raises(ValueError, match="does not match"):
        g13.finalize_inventory_search(
            g13.G13SearchPlan(), (altered, *rest), (), evaluated_at=NOW
        )


def test_candidate_bounds_order_and_identity_are_frozen() -> None:
    seven = tuple(
        _audit(
            rank=index + 1,
            document_url=f"https://operator-{index}.invalid/inventory-doc",
        )
        for index in range(7)
    )
    with pytest.raises(ValueError, match="count exceeds"):
        g13.finalize_inventory_search(
            g13.G13SearchPlan(), _searches(), seven, evaluated_at=NOW
        )

    noncontiguous = (_audit(rank=2),)
    with pytest.raises(ValueError, match="contiguous"):
        g13.finalize_inventory_search(
            g13.G13SearchPlan(), _searches(), noncontiguous, evaluated_at=NOW
        )


def test_strict_json_contains_no_response_body_or_nonstandard_number() -> None:
    result = g13.finalize_inventory_search(
        g13.G13SearchPlan(),
        _searches(),
        (_audit(),),
        evaluated_at=NOW,
    )
    encoded = result.strict_json()

    assert "operator documentation fixture" not in encoded
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert len(result.plan_hash) == 64


def test_round_robin_selection_is_frozen_across_query_families() -> None:
    searches = []
    for index, query in enumerate(g13.FROZEN_QUERIES):
        urls = tuple(
            f"https://family-{index}.invalid/result-{rank}" for rank in range(2)
        )
        searches.append(
            g13.SearchQueryReceipt(
                query,
                g13.SearchState.SUCCESS.value,
                len(urls),
                g13.ordered_result_hash(urls),
                urls,
                "synthetic",
            )
        )

    selected = g13.select_candidate_document_urls(
        g13.G13SearchPlan(), tuple(searches)
    )
    assert selected == (
        "https://family-0.invalid/result-0",
        "https://family-1.invalid/result-0",
        "https://family-2.invalid/result-0",
        "https://family-3.invalid/result-0",
        "https://family-0.invalid/result-1",
        "https://family-1.invalid/result-1",
    )


def test_candidate_audit_cannot_be_substituted_after_search() -> None:
    substituted = _audit(document_url="https://substitute.invalid/inventory-doc")
    with pytest.raises(ValueError, match="round-robin"):
        g13.finalize_inventory_search(
            g13.G13SearchPlan(), _searches(), (substituted,), evaluated_at=NOW
        )


@pytest.mark.parametrize(
    "mutation",
    (
        {"queries": tuple(reversed(g13.FROZEN_QUERIES))},
        {"maximum_results_per_query": 6},
        {"maximum_candidate_mechanisms": 7},
        {"maximum_documents_per_candidate": 3},
        {"maximum_document_bytes": 1_048_577},
        {"request_timeout_s": 16.0},
        {"retry_count": 1},
        {"status_requests_allowed": True},
        {"rf_requests_allowed": True},
    ),
)
def test_plan_refuses_surface_expansion(mutation: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(g13.G13SearchPlan(), **mutation).validate()


def test_gate_receipt_module_has_no_network_or_persistence_imports() -> None:
    source = Path(g13.__file__).read_text(encoding="utf-8")
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
