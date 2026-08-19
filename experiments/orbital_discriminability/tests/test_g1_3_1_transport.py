"""Offline tests for the Gate G1.3.1 independent search transport."""

from dataclasses import replace
import ast
from pathlib import Path

import pytest

from experiments.orbital_discriminability import g1_3_search as g13
from experiments.orbital_discriminability import g1_3_1_transport as g131


def _responses() -> tuple[g131.IndependentQueryResponse, ...]:
    return tuple(
        g131.IndependentQueryResponse(
            call_index=index,
            invocation_id=f"invocation-{index}",
            queries_in_call=(query,),
            state=g13.SearchState.SUCCESS.value,
            ordered_result_urls=(f"https://operator-{index}.invalid/doc",),
            detail="synthetic independent response",
        )
        for index, query in enumerate(g13.FROZEN_QUERIES, start=1)
    )


def test_transport_freeze_is_offline_and_binds_parent_plan() -> None:
    receipt = g131.freeze_transport(g131.G131TransportPlan())

    assert receipt.outcome == g131.TransportOutcome.SEARCH_TRANSPORT_FROZEN.value
    assert receipt.parent_plan_hash == g13.G13SearchPlan().plan_hash
    assert receipt.invocation_count == 4
    assert receipt.retry_count == 0
    assert receipt.result_page_requests == 0
    assert receipt.status_requests == 0
    assert receipt.raw_rf_activity == "ZERO"
    assert not receipt.persistent_catalog_created
    assert "live search provider" in receipt.unauthorized_claims[0]


def test_four_independent_calls_materialize_exact_g13_receipts() -> None:
    receipts = g131.materialize_query_receipts(
        g131.G131TransportPlan(), _responses()
    )

    assert tuple(item.query for item in receipts) == g13.FROZEN_QUERIES
    assert all(item.state == g13.SearchState.SUCCESS.value for item in receipts)
    assert all(item.result_count == 1 for item in receipts)
    assert all(len(item.ordered_result_set_sha256 or "") == 64 for item in receipts)
    assert all(not item.raw_search_artifact_persisted for item in receipts)


def test_input_order_cannot_change_call_order_or_hashes() -> None:
    forward = g131.materialize_query_receipts(
        g131.G131TransportPlan(), _responses()
    )
    reverse = g131.materialize_query_receipts(
        g131.G131TransportPlan(), tuple(reversed(_responses()))
    )

    assert forward == reverse


def test_bundled_query_call_is_refused() -> None:
    responses = list(_responses())
    responses[0] = replace(
        responses[0],
        queries_in_call=(g13.FROZEN_QUERIES[0], g13.FROZEN_QUERIES[1]),
    )

    with pytest.raises(ValueError, match="exactly its one frozen query"):
        g131.materialize_query_receipts(g131.G131TransportPlan(), responses)


def test_duplicate_invocation_identity_is_refused() -> None:
    responses = list(_responses())
    responses[1] = replace(responses[1], invocation_id=responses[0].invocation_id)

    with pytest.raises(ValueError, match="distinct invocation"):
        g131.materialize_query_receipts(g131.G131TransportPlan(), responses)


def test_search_error_remains_error_and_carries_no_urls() -> None:
    responses = list(_responses())
    responses[2] = replace(
        responses[2],
        state=g13.SearchState.SEARCH_ERROR.value,
        ordered_result_urls=(),
        detail="provider timeout",
    )
    receipts = g131.materialize_query_receipts(
        g131.G131TransportPlan(), responses
    )

    assert receipts[2].state == g13.SearchState.SEARCH_ERROR.value
    assert receipts[2].result_count == 0
    assert receipts[2].ordered_result_set_sha256 is None


@pytest.mark.parametrize(
    "mutation,match",
    (
        ({"call_index": 2}, "contiguous"),
        ({"invocation_id": ""}, "non-empty"),
        ({"raw_response_persisted": True}, "may not persist"),
        (
            {"ordered_result_urls": tuple(f"https://x.invalid/{i}" for i in range(6))},
            "exceeds",
        ),
        (
            {"ordered_result_urls": ("https://x.invalid/a", "https://x.invalid/a")},
            "duplicate",
        ),
        ({"ordered_result_urls": ("file:///tmp/result",)}, "public HTTP"),
        ({"ordered_result_urls": ("https://user@x.invalid/a",)}, "public HTTP"),
        ({"ordered_result_urls": ("https://x.invalid/a#fragment",)}, "public HTTP"),
    ),
)
def test_response_boundary_refuses_ambiguous_transport(
    mutation: dict[str, object],
    match: str,
) -> None:
    responses = list(_responses())
    responses[0] = replace(responses[0], **mutation)

    with pytest.raises(ValueError, match=match):
        g131.materialize_query_receipts(g131.G131TransportPlan(), responses)


@pytest.mark.parametrize(
    "mutation",
    (
        {"parent_plan_hash": "0" * 64},
        {"queries": tuple(reversed(g13.FROZEN_QUERIES))},
        {"invocation_mode": "BUNDLED"},
        {"invocation_count": 5},
        {"maximum_results_per_invocation": 6},
        {"retain_provider_order": False},
        {"require_distinct_invocation_ids": False},
        {"retry_count": 1},
        {"result_page_requests_allowed": True},
        {"status_requests_allowed": True},
        {"rf_requests_allowed": True},
    ),
)
def test_plan_refuses_surface_expansion(mutation: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(g131.G131TransportPlan(), **mutation).validate()


def test_module_has_no_network_client_or_persistence_imports() -> None:
    source = Path(g131.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    imports.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "urllib.request" not in imports
    assert not any(
        item.split(".")[0] in {"requests", "httpx", "socket", "websocket", "sqlite3"}
        for item in imports
    )
